# 真实 LLM 调用接入设计文档（llm-real-integration）

**所属**：地道英语纠错 · 智能笔记本 | **版本**：V0.1 | **状态**：草稿 | **日期**：2026年8月
**对应功能**：F-01 会话式文本纠错 · 真实 LLM 调用接入
**依赖**：`backend/app/services/llm_client.py`、`backend/app/prompts/correction_prompt.py`、`backend/app/core/config.py`、`backend/app/scripts/prompt_acceptance.py`

> 本文档定义将 LLM 层从 Mock 切换为**真实调用**的设计。探索发现真实调用链路已基本就绪，本方案为最小改动：对齐验收配置、新增冒烟脚本、保持测试隔离。

## 〇、背景与目标

- 产品 LLM 层用确定性 Mock（`LLM_MODE=mock`）供测试/演示；真实调用提示词已在 `correction_prompt.py` 完成并经验收（casual/formal 场景参数化）。
- 目标：将真实 LLM 调用接入产品链路，产出稳定、可验证的真实纠错。
- 范围边界：不改提示词、不改 schema/前端；单测保持 Mock 注入；E2E 保持 mock；新增可选真实冒烟脚本。

## 一、已确认决策

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 触发方式 | 沿用 `LLM_MODE` 切换：mock=Mock，空/non-mock=真实调用（`get_llm_client` 已支持） |
| 2 | 对齐验收 | `RealLLMClient.complete` 加 `temperature=0` + 网络重试（timeout 120s，最多 3 次，对齐验收脚本） |
| 3 | 测试策略 | 单测保持 MockLLMClient 注入；E2E 保持 mock（避免不稳定）；新增可选真实冒烟脚本 |
| 4 | 冒烟形式 | 独立 `backend/app/scripts/llm_smoke.py`（真实发一条纠错，打印 JSON，退出码 0/非0） |

## 二、现状与改动范围

### 2.1 现状（探索发现）

真实调用链路已基本就绪：

```
correction_service.submit_message
  → build_system_prompt(CORRECTION_STYLE)   ← 已是测试好的提示词（casual/formal）
  → _call_and_parse(llm_client, messages)   ← LLMClient 抽象（mock/真实）
  → get_llm_client()                        ← LLM_MODE 决定 mock/真实
```

- `RealLLMClient` 已实现（调 `/chat/completions`），但无 `temperature`、无重试
- `.env` 已配置 `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`（deepseek-v4-flash）
- 测试全部通过 `MockLLMClient` 注入或 `app.dependency_overrides[get_llm_client]`

### 2.2 改动清单（4 处，聚焦最小）

| 文件 | 操作 | 内容 |
|------|------|------|
| `backend/app/services/llm_client.py` | 修改 | `RealLLMClient.complete` 加 `temperature=0` + 最多 3 次重试（timeout 120s） |
| `backend/app/scripts/llm_smoke.py` | 新建 | 真实冒烟脚本 |
| `backend/app/core/config.py` | 无 | LLM_MODE 已支持；真实调用即不设 mock |
| `backend/app/services/correction_service.py` | 无 | 已用 build_system_prompt |

## 三、RealLLMClient.complete 重构

```python
class RealLLMClient(LLMClient):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete(self, messages: list[dict[str, Any]]) -> str:
        last_exc: Exception | None = None
        for _attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120) as client:
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

要点：
- `temperature: 0`：对齐验收脚本，输出稳定
- 最多 3 次重试：对齐验收脚本 run_case
- 超时（120s）→ `LLMTimeoutError`；其他 HTTP 错误重试后 → `LLMUnavailableError`（供 `_call_and_parse` 映射 504/503）

## 四、llm_smoke.py 设计

```python
"""真实 LLM 冒烟脚本：发一条英文纠错请求，验证真实调用链路与提示词效果。

用法：
    cd backend
    .venv/bin/python -m app.scripts.llm_smoke                # 用 .env 配置真实调用
    .venv/bin/python -m app.scripts.llm_smoke --text "She go to school yesterday."

依赖 .env 中 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL（config.py 提供默认值）。
注意：不要设 LLM_MODE=mock（否则走 MockLLMClient）。退出码 0=成功，1=失败。
"""
```

- `main()`：读 `CORRECTION_STYLE` → `build_system_prompt(style)` → 复用 `prompt_acceptance.build_messages`（DRY）→ `RealLLMClient`（或 `get_llm_client` 非 mock）调用 → 打印完整 JSON → 退出码
- `--text` 参数默认 `"She go to school yesterday."`
- 用 `get_llm_client()` 而非直接实例化 RealLLMClient——保持与产品链路一致（只要不设 LLM_MODE=mock 即真实）

## 五、测试补充

- `backend/tests/test_llm_client.py`：保留现有 MockLLMClient 测试；新增 RealLLMClient 重试测试（用 `httpx.MockTransport` 模拟：超时→重试→成功；3 次失败→ LLMUnavailableError；3 次超时→ LLMTimeoutError），无需真实网络
- `backend/tests/test_prompt_acceptance.py`：不受影响
- 不新增对真实 LLM 的自动化测试（慢、不稳定、耗 token）

## 六、验证

1. `cd backend && .venv/bin/python -m pytest -q` → 全绿（含新增 RealLLMClient 重试测试）
2. 真实冒烟：`cd backend && .venv/bin/python -m app.scripts.llm_smoke` → 返回真实纠错 JSON（含 learnings）
3. E2E 保持 mock：`cd web && npm run test:e2e` → 22 passed
4. 浏览器真实走查：后端**不设 LLM_MODE** 启动，前端提交英文 → 真实 LLM 纠错（casual 场景）

---

**变更记录**

- V0.1 · 2026-08 · 初稿：探索确认真实调用链路已基本就绪；定稿最小改动（RealLLMClient 对齐验收 + 冒烟脚本 + 测试隔离）；决策 4 项
