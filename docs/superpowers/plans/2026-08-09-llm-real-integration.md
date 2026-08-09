# 真实 LLM 调用接入实现计划（llm-real-integration）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将纠错 LLM 层从 Mock 切换为真实调用——RealLLMClient 对齐验收配置（temperature=0 + 重试），新增真实冒烟脚本，保持测试隔离。

**Architecture:** 沿用 `LLM_MODE` 切换（mock=Mock，空/non-mock=真实）。`RealLLMClient.complete` 加 `temperature=0` + 最多 3 次重试（timeout 120s），对齐验收脚本。新增 `llm_smoke.py` 冒烟脚本（复用 `prompt_acceptance.build_messages` 与 `get_llm_client`）。单测保持 Mock 注入，E2E 保持 mock。

**Tech Stack:** Python + httpx（含 `httpx.MockTransport` 测试）；pytest 单测

**依赖文档:** `docs/superpowers/specs/2026-08-09-llm-real-integration-design.md`

---

### Task 1: RealLLMClient 对齐验收（temperature=0 + 重试）

**Files:**
- Modify: `backend/app/services/llm_client.py:25-44`
- Test: `backend/tests/test_llm_client.py`

- [ ] **Step 1: 编写失败的测试（httpx.MockTransport 模拟重试）**

修改 `backend/tests/test_llm_client.py` 为：

```python
import httpx

from app.services.llm_client import (
    LLMTimeoutError,
    LLMUnavailableError,
    MockLLMClient,
    RealLLMClient,
)


async def test_mock_llm_returns_responder_output():
    mock = MockLLMClient(responder=lambda msgs: "pong")
    assert await mock.complete([{"role": "user", "content": "hi"}]) == "pong"


async def test_real_llm_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    transport = httpx.MockTransport(handler)
    client = RealLLMClient("https://api.example.com", "test-key", "test-model", transport=transport)
    result = await client.complete([{"role": "user", "content": "hi"}])
    assert result == "ok"
    assert calls["n"] == 3


async def test_real_llm_all_fail_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(handler)
    client = RealLLMClient("https://api.example.com", "test-key", "test-model", transport=transport)
    try:
        await client.complete([{"role": "user", "content": "hi"}])
        assert False, "应抛异常"
    except LLMUnavailableError:
        pass


async def test_real_llm_timeout_raises_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow")

    transport = httpx.MockTransport(handler)
    client = RealLLMClient("https://api.example.com", "test-key", "test-model", transport=transport)
    try:
        await client.complete([{"role": "user", "content": "hi"}])
        assert False, "应抛异常"
    except LLMTimeoutError:
        pass
```

> 注：`httpx.MockTransport` 的 handler 若 `raise httpx.ReadTimeout`，httpx 会把它当作传输异常抛给调用方（经 AsyncClient 包装）。若实现中捕获 `httpx.TimeoutException`，则映射为 `LLMTimeoutError`。实现时需验证 MockTransport 抛 Timeout 的行为，必要时改用 `httpx.ConnectTimeout`。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_llm_client.py -v`
Expected: FAIL——`TypeError: RealLLMClient.__init__() got an unexpected keyword argument 'transport'`

- [ ] **Step 3: 实现 RealLLMClient（temperature=0 + 重试 + transport 注入）**

修改 `backend/app/services/llm_client.py` 中 `RealLLMClient`：

```python
class RealLLMClient(LLMClient):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._transport = transport

    async def complete(self, messages: list[dict[str, Any]]) -> str:
        last_exc: Exception | None = None
        for _attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120, transport=self._transport) as client:
                    r = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={"model": self.model, "messages": messages, "temperature": 0},
                    )
                    r.raise_for_status()
                    return r.json()["choices"][0]["message"]["content"]
            except httpx.TimeoutException as exc:
                last_exc = exc
                continue
            except httpx.HTTPError as exc:
                last_exc = exc
                continue
        if isinstance(last_exc, httpx.TimeoutException):
            raise LLMTimeoutError from last_exc
        raise LLMUnavailableError from last_exc
```

> 注意：`httpx.AsyncClient(timeout=120, transport=None)` 传 `None` 时 httpx 使用默认 transport（真实网络），与现有行为一致；传 `MockTransport` 时用于测试。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_llm_client.py -v`
Expected: PASS（4 passed：mock + retries + unavailable + timeout）

> 若 timeout 测试失败（MockTransport 抛 ReadTimeout 行为差异），将 handler 改用 `raise httpx.ConnectTimeout("too slow")` 重试。

- [ ] **Step 5: 全量回归**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全绿（原 63 + 新增 3 = 66 passed）

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat(llm): RealLLMClient 对齐验收——temperature=0 + 最多3次重试 + transport 注入（可测）"
```

---

### Task 2: 真实冒烟脚本（llm_smoke.py）

**Files:**
- Create: `backend/app/scripts/llm_smoke.py`
- Test: `backend/tests/test_llm_smoke.py`

- [ ] **Step 1: 编写失败的测试**

创建 `backend/tests/test_llm_smoke.py`：

```python
import asyncio

from app.scripts.llm_smoke import build_smoke_messages, run_smoke


def test_build_smoke_messages_uses_system_prompt():
    msgs = build_smoke_messages("She go to school yesterday.", "casual")
    assert msgs[0]["role"] == "system"
    assert "correction" in msgs[0]["content"]
    assert msgs[-1] == {"role": "user", "content": "She go to school yesterday."}


async def test_run_smoke_with_fake_llm():
    async def fake_llm(messages):
        return '{"intent":"correction","correction":{"has_errors":true,"errors":[],"rewrite":{"minimal":{"text":"ok","explanation":""},"natural":{"text":"ok","explanation":""}},"learnings":[]},"reply":null}'

    result = await run_smoke(fake_llm, "She go to school yesterday.", "casual")
    assert result["ok"] is True
    assert "correction" in result["raw"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_llm_smoke.py -v`
Expected: FAIL（ModuleNotFoundError: app.scripts.llm_smoke）

- [ ] **Step 3: 实现冒烟脚本**

创建 `backend/app/scripts/llm_smoke.py`：

```python
"""真实 LLM 冒烟脚本：发一条英文纠错请求，验证真实调用链路与提示词效果。

用法：
    cd backend
    .venv/bin/python -m app.scripts.llm_smoke                # 用 .env 配置真实调用
    .venv/bin/python -m app.scripts.llm_smoke --text "She go to school yesterday."

依赖 .env 中 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL（config.py 提供默认值）。
注意：不要设 LLM_MODE=mock（否则走 MockLLMClient）。退出码 0=成功，1=失败。
"""

import argparse
import asyncio

from app.core.config import get_settings
from app.prompts.correction_prompt import build_system_prompt
from app.services.llm_client import get_llm_client


def build_smoke_messages(input_text: str, style: str = "casual") -> list[dict]:
    """构建冒烟 messages：system prompt（按场景）+ 用户原文。"""
    return [
        {"role": "system", "content": build_system_prompt(style)},
        {"role": "user", "content": input_text},
    ]


async def run_smoke(llm_call, input_text: str, style: str) -> dict:
    """用给定 llm_call 跑一次纠错。返回 {ok, raw, error}。"""
    try:
        raw = await llm_call(build_smoke_messages(input_text, style))
        return {"ok": True, "raw": raw, "error": None}
    except Exception as exc:  # noqa: BLE001 - 冒烟脚本需兜底所有异常
        return {"ok": False, "raw": "", "error": f"{type(exc).__name__}: {exc}"}


async def main() -> int:
    parser = argparse.ArgumentParser(description="真实 LLM 纠错冒烟")
    parser.add_argument("--text", default="She go to school yesterday.", help="要纠错的英文文本")
    args = parser.parse_args()

    settings = get_settings()
    client = get_llm_client()
    result = await run_smoke(client.complete, args.text, settings.CORRECTION_STYLE)

    if result["ok"]:
        print("=== 冒烟成功 ===")
        print(result["raw"])
        return 0
    print("=== 冒烟失败 ===")
    print(result["error"])
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_llm_smoke.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 全量回归**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全绿（68 passed）

- [ ] **Step 6: Commit**

```bash
git add backend/app/scripts/llm_smoke.py backend/tests/test_llm_smoke.py
git commit -m "feat(scripts): 真实 LLM 冒烟脚本（复用 build_system_prompt + get_llm_client，退出码 0/1）"
```

---

### Task 3: 真实冒烟运行验证

**Files:**
- （无新增代码；运行冒烟 + 全链路验证）

- [ ] **Step 1: 确认 .env 配置且不设 LLM_MODE**

Run: `cd backend && grep -c "LLM_MODE" .env 2>/dev/null; .venv/bin/python -c "from app.core.config import get_settings; s=get_settings(); print('mode:', repr(s.LLM_MODE), 'key:', bool(s.LLM_API_KEY), 'model:', s.LLM_MODEL)"`
Expected: `.env` 无 LLM_MODE（或为空），`mode: ''`，`key: True`，`model: deepseek-v4-flash`

- [ ] **Step 2: 运行真实冒烟**

Run: `cd backend && .venv/bin/python -m app.scripts.llm_smoke`
Expected: 输出 `=== 冒烟成功 ===` + 完整纠错 JSON（含 intent/correction/errors/rewrite/learnings），退出码 0

> 若网络失败，脚本自动重试 3 次（RealLLMClient）。若仍失败，检查 `.env` 的 key/url。

- [ ] **Step 3: 浏览器真实走查（可选）**

启动后端**不设 LLM_MODE**：
Run: `lsof -ti :8000 | xargs kill 2>/dev/null; sleep 1; cd backend && nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/echo_backend.log 2>&1 & cd ../web && nohup npm run dev > /tmp/echo_web.log 2>&1 &`

浏览器打开 `http://localhost:5173`，登录后提交英文（如 `She go to school yesterday.`）→ 观察**真实 LLM** 返回的纠错报告（含错误分析/改写/学到的规则）。

> 说明：此步为真实链路验证；若真实 LLM 响应慢或波动，属预期（提示词验收时已确认 LLM 识别集合偶有波动）。

- [ ] **Step 4: 恢复 mock 供 E2E（保持测试隔离）**

E2E 用 playwright webServer 的 `LLM_MODE=mock`（已配置，无需改）。真实走查后如需继续用 mock 演示，重启后端时设 `LLM_MODE=mock`。

- [ ] **Step 5: 文档状态更新**

如实现与 `docs/superpowers/specs/2026-08-09-llm-real-integration-design.md` 有出入，更新 spec 后提交。

---

## Self-Review 检查表

- **Spec 覆盖**：§三 RealLLMClient 重构 → Task 1；§四 llm_smoke.py → Task 2；§五 测试补充（MockTransport 重试/超时/不可用）→ Task 1 Step 1；§六 验证（单测/冒烟/E2E/浏览器）→ Task 1 Step 5 + Task 3。
- **占位符扫描**：无 TBD/TODO；所有步骤含完整代码与命令。Task 1 Step 1 中有一段「当前实现验证」占位性注释——它标注了测试前置理解，最终以 Step 3 实现为准，测试文件以三个 transport 测试为主体。
- **类型一致性**：`RealLLMClient.__init__(base_url, api_key, model, transport=None)` 在 Task 1 定义、测试用；`llm_smoke.build_smoke_messages(input_text, style) -> list[dict]`、`run_smoke(llm_call, input_text, style) -> dict` 在 Task 2 定义与测试一致；`get_llm_client()` 返回的 client 有 `.complete`（Task 2 冒烟用 `client.complete`）。
