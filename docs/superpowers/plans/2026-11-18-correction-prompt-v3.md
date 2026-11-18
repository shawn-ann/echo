# 纠错提示词 V3 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把纠错提示词换成 V3（`category` 分类学 + 判定优先级 + OUT OF SCOPE），并让 schema、前端、笔记分组与评测脚本全部对齐新输出契约。

**Architecture:** 提示词仍是 `build_system_prompt(style)` 返回的单个字符串常量（`style` 仅做校验）。`ErrorBlock` 的 `error_type` 更名为 `category`；`has_errors` 不再由模型输出，改为 `CorrectionBody` 上由 `errors` 派生的 computed field；`rewrite` 改为必填。历史报告（DB 里 `error_type` + 可能为 `null` 的 `rewrite`）在**前端读取时归一化**，不做数据迁移。

**Tech Stack:** Python 3.12 / FastAPI / Pydantic v2 / pytest；React 19 + TypeScript + Vite；Playwright E2E。

**Spec:** `docs/superpowers/specs/2026-11-18-correction-prompt-v3-design.md`（§3 是逐字使用的提示词）

## Global Constraints

- API 前缀 `/api/v1`，错误响应统一 `{code, message, details}`，不新增错误码。
- 中文是文档与 commit message 的工作语言；commit 风格 `type(scope): 中文描述`。
- 后端无 lint/typecheck 配置；前端“类型检查”就是 `npm run build`（`tsc -b && vite build`）。
- 后端测试需要运行中的 PostgreSQL（`echo` + `echo_test`），命令在 `backend/` 下执行：`.venv/bin/pytest -v`。
- 前端命令在 `web/` 下执行，需 Node 24：`source ~/.nvm/nvm.sh && nvm use 24`。
- 不推送任何分支（推 `v0.1` 会触发生产部署）。
- 不新增 `severity` / `category_l1` / `operation` 字段；不改 `correction_reports` 表结构。

## Review Focus

1. **模型漏掉 `rewrite` 字段**（无错误时最容易漏）：schema 必填 → `502 LLM_RESPONSE_INVALID`。必须有一条“缺 rewrite 被拒绝”的测试，并在提示词里保留逐字契约。
2. **历史报告打开**：旧记录是 `error_type`、`rewrite: null`，前端归一化后不能崩、不能显示空白标签。
3. **删除类修正**（`correction: ""`）：卡片不能渲染成空的 “✅”。
4. **无错误但有 `natural` 改写**：绿色卡片下方必须能看到改写，否则数据是死的。
5. **笔记分组的 `error_root`**：新词表里 `母语者不这么说` / `技术术语误用` 等值会直接成为笔记根因，分组必须按 `category` 生效且不丢错误。

---

### Task 0: 备份当前代码

**Files:** 无（仅 git 操作）

- [ ] **Step 1: 确认工作区干净**

Run: `git status --short`
Expected: 无输出（若有未提交改动，先让人类伙伴确认是否提交）

- [ ] **Step 2: 从当前 HEAD 建备份分支**

```bash
git branch backup/pre-prompt-v3-2026-11-18
git branch --list 'backup/pre-prompt-v3*'
```

Expected: 输出 `backup/pre-prompt-v3-2026-11-18`

- [ ] **Step 3: 在备份分支上验证可回滚**

Run: `git log --oneline -1 backup/pre-prompt-v3-2026-11-18`
Expected: 与 `git log --oneline -1 HEAD` 同一个 commit

> 不 push。备份分支只存在于本地。

---

### Task 1: 替换提示词

**Files:**
- Modify: `backend/app/prompts/correction_prompt.py`（整体替换）
- Test: `backend/tests/test_correction_prompt.py`（整体替换）

**Interfaces:**
- Produces: `build_system_prompt(style: str = "casual") -> str`（非法 style 抛 `ValueError`）、`SYSTEM_PROMPT: str = build_system_prompt("casual")`
- Produces: 提示词文本不含 `{{input}}`、`error_type`、`has_errors`

- [ ] **Step 1: 重写提示词测试**

`backend/tests/test_correction_prompt.py`：

```python
import pytest

from app.prompts.correction_prompt import SYSTEM_PROMPT, build_system_prompt


def test_system_prompt_contains_new_contract_fields():
    for token in ("category", "fragment", "correction", "explanation", "rewrite", "minimal", "natural", "note"):
        assert token in SYSTEM_PROMPT


def test_system_prompt_removed_old_contract_fields():
    assert "error_type" not in SYSTEM_PROMPT
    assert "has_errors" not in SYSTEM_PROMPT
    assert "{{input}}" not in SYSTEM_PROMPT
    assert "=== USER INPUT ===" not in SYSTEM_PROMPT
    assert "learnings" not in SYSTEM_PROMPT


def test_system_prompt_contains_taxonomy_and_boundaries():
    for section in ("CANONICAL LIST", "JUDGMENT BOUNDARIES", "OUT OF SCOPE", "HARD RULES", "REWRITE RULES"):
        assert section in SYSTEM_PROMPT


def test_system_prompt_has_no_out_of_list_category_names():
    # 规则里只能引用词表内的类别名
    assert "语域错配" not in SYSTEM_PROMPT
    assert "表达不地道" not in SYSTEM_PROMPT


def test_system_prompt_no_markdown_fence():
    assert "```" not in SYSTEM_PROMPT


def test_build_system_prompt_styles_return_same():
    assert build_system_prompt("casual") == build_system_prompt("formal")


def test_build_system_prompt_invalid_style():
    with pytest.raises(ValueError):
        build_system_prompt("bogus")


def test_system_prompt_default_is_casual():
    assert SYSTEM_PROMPT == build_system_prompt("casual")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_correction_prompt.py -v`
Expected: FAIL（`assert "error_type" not in SYSTEM_PROMPT` 等）

- [ ] **Step 3: 用 spec §3 的定稿文本替换 `correction_prompt.py`**

- 模块 docstring 更新为「V3：分类学 + 判定优先级」。
- 保留 `_VALID_STYLES = {"casual", "formal"}`、`build_system_prompt(style)` 的校验逻辑、`SYSTEM_PROMPT` 兼容常量。
- `_NEW_SYSTEM_PROMPT` 的内容**逐字**取自 spec §3（去掉 `=== USER INPUT === / {{input}}`，spec §3 已不含该段）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_correction_prompt.py -v`
Expected: 8 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/prompts/correction_prompt.py backend/tests/test_correction_prompt.py
git commit -m "feat(prompts): 纠错提示词切换为 V3 分类学版本"
```

---

### Task 2: 输出契约改造

**Files:**
- Modify: `backend/app/schemas/correction.py:7-29`
- Test: `backend/tests/test_schemas_correction.py`（整体替换）

**Interfaces:**
- Produces: `ErrorBlock(category: str, fragment: str, explanation: str, correction: str)`
- Produces: `RewriteSection(minimal: RewriteOption, natural: RewriteOption)`
- Produces: `CorrectionBody(errors: list[ErrorBlock] = [], rewrite: RewriteSection)`，`has_errors: bool` 为只读 computed field，`model_dump()` 含 `has_errors`
- Consumes: 无

- [ ] **Step 1: 重写 schema 测试**

`backend/tests/test_schemas_correction.py`：

```python
import pytest
from pydantic import ValidationError

from app.schemas.correction import CorrectionBody, SubmitRequest

REWRITE = {
    "minimal": {"text": "a", "note": "n1"},
    "natural": {"text": "b", "note": "n2"},
}


def test_correction_body_valid_with_category():
    parsed = CorrectionBody.model_validate(
        {
            "errors": [
                {"category": "时态错误", "fragment": "I go to", "explanation": "x", "correction": "I went to"}
            ],
            "rewrite": REWRITE,
        }
    )
    assert parsed.has_errors is True
    assert parsed.errors[0].category == "时态错误"
    assert parsed.rewrite.minimal.note == "n1"


def test_correction_body_no_errors_derives_has_errors_false():
    parsed = CorrectionBody.model_validate({"errors": [], "rewrite": REWRITE})
    assert parsed.has_errors is False
    assert parsed.model_dump()["has_errors"] is False


def test_correction_body_missing_category_rejected():
    with pytest.raises(ValidationError):
        CorrectionBody.model_validate(
            {"errors": [{"fragment": "a", "explanation": "b", "correction": "c"}], "rewrite": REWRITE}
        )


def test_correction_body_missing_rewrite_rejected():
    with pytest.raises(ValidationError):
        CorrectionBody.model_validate({"errors": []})


def test_correction_body_ignores_model_supplied_has_errors():
    # 模型即使多输出 has_errors，也以 errors 为准
    parsed = CorrectionBody.model_validate({"has_errors": False, "errors": [], "rewrite": REWRITE})
    assert parsed.has_errors is False


def test_correction_body_model_dump_matches_contract():
    body = CorrectionBody(
        errors=[{"category": "冠词缺失", "fragment": "job", "explanation": "x", "correction": "a job"}],
        rewrite=REWRITE,
    )
    dumped = body.model_dump()
    assert dumped["has_errors"] is True
    assert "category" in dumped["errors"][0]
    assert "error_type" not in dumped["errors"][0]
    assert dumped["rewrite"]["minimal"]["text"] == "a"


def test_submit_request_length_boundaries():
    assert SubmitRequest(content="a").content == "a"
    assert SubmitRequest(content="x" * 2000).content == "x" * 2000
    with pytest.raises(ValidationError):
        SubmitRequest(content="")
    with pytest.raises(ValidationError):
        SubmitRequest(content="x" * 2001)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_schemas_correction.py -v`
Expected: FAIL（Unexpected keyword / `category` 属性不存在）

- [ ] **Step 3: 改 `schemas/correction.py`**

```python
from pydantic import BaseModel, Field, computed_field


class ErrorBlock(BaseModel):
    category: str
    fragment: str
    explanation: str
    correction: str


class CorrectionBody(BaseModel):
    """LLM 单轮纠错输出（V3：category 分类学，无 has_errors 字段）。"""

    errors: list[ErrorBlock] = Field(default_factory=list)
    rewrite: RewriteSection

    @computed_field
    @property
    def has_errors(self) -> bool:
        return bool(self.errors)
```

`RewriteOption` / `RewriteSection` 保持不动；`MessageOut` / `SubmitRequest` / `SubmitResponse` / `HistoryResponse` 不动。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_schemas_correction.py -v`
Expected: 7 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/correction.py backend/tests/test_schemas_correction.py
git commit -m "refactor(correction): 输出契约改用 category，has_errors 由 errors 派生"
```

---

### Task 3: Mock 与纠错链路测试适配

**Files:**
- Modify: `backend/app/services/llm_client.py:74-125`（`_default_responder`）
- Modify: `backend/tests/test_correction_service.py`、`backend/tests/test_messages_api.py`、`backend/tests/test_llm_smoke.py`
- Test: 同上

**Interfaces:**
- Consumes: Task 2 的 `CorrectionBody`、`ErrorBlock.category`
- Produces: Mock 默认响应（纠错分支）为新契约：

```json
{"errors":[{"category":"动词形式错误","fragment":"interested in read","explanation":"介词后应接动名词","correction":"interested in reading"}],
 "rewrite":{"minimal":{"text":"I am interested in reading English books.","note":"介词后接动名词"},
            "natural":{"text":"I love reading English books.","note":"更自然的表达"}}}
```

- Produces: `no-error` 分支响应 `{"errors":[],"rewrite":{"minimal":{"text":"<原文>","note":"原文已无问题"},"natural":{"text":"<原文>","note":"无需改写"}}}`

- [ ] **Step 1: 改测试里的内联 mock 响应与断言**

- `test_correction_service.py`：`ai_out.report["has_errors"] is True` 保留（derived 后仍在 dump 中）；`report["errors"][0]["error_type"]` → `["category"]`；内联 responder 的 JSON 里 `error_type` → `category`，并给 `{"report": {...}}` 包装用例补 `rewrite` 字段；第 78 行 `assert "has_errors" in ctx[1]["content"]`（历史报告注入上下文）改为 `assert "category" in ctx[1]["content"]`。
- `test_messages_api.py`：把三处 `'{"has_errors":false,"errors":[],"rewrite":null}'` 改为 `'{"errors":[],"rewrite":{"minimal":{...},"natural":{...}}}'`；`report["has_errors"]` 断言保留。
- `test_llm_smoke.py`：responder 字符串改成新契约（含 `rewrite`）。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_correction_service.py tests/test_messages_api.py tests/test_llm_smoke.py -v`
Expected: FAIL（Mock 返回含 `has_errors`/`error_type`，schema 校验失败 → 502）

- [ ] **Step 3: 改 `llm_client._default_responder`**

纠错分支返回 Task 3 Interfaces 里的新 JSON；`## 原文` 笔记分支不动（Task 4 处理）；`no-error` 分支返回空 `errors` + 原文回填的 `rewrite`（用最后一条 user content 作为原文）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_correction_service.py tests/test_messages_api.py tests/test_llm_smoke.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/llm_client.py backend/tests/test_correction_service.py backend/tests/test_messages_api.py backend/tests/test_llm_smoke.py
git commit -m "test(correction): mock 与链路测试适配 V3 输出契约"
```

---

### Task 4: 笔记分组改用 category

**Files:**
- Modify: `backend/app/prompts/note_prompt.py:7-16,41-58`
- Modify: `backend/tests/test_note_prompt.py`、`backend/tests/test_note_service.py`

**Interfaces:**
- Consumes: 纠错报告的 `errors[]`，每条含 `category`
- Produces: `build_note_user_content(source_text: str, errors: list[dict]) -> str` 不变，但输入 errors 的键为 `category`

- [ ] **Step 1: 改测试**

`test_note_prompt.py`：`test_system_prompt_group_by_error_type` 改名为 `test_system_prompt_group_by_category`，断言 `"category" in prompt` 且 `"error_type" not in prompt`；用例 errors 字典的 `error_type` 改 `category`，并断言渲染结果里出现该 `category` 字符串。

`test_note_service.py`：两处 `{"error_type": "主谓不一致", ...}` 改 `{"category": "主谓不一致", ...}`。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_note_prompt.py tests/test_note_service.py -v`
Expected: FAIL

- [ ] **Step 3: 改 `note_prompt.py`**

- `## 输入`：`错误列表：每条含 category（中文错误类型词表）、fragment、explanation、correction`
- `## 分组规则`：`按 category 分组` / `每个 result 的 error_root 必须原样取该组的 category 值`
- `## 字段要求`：`error_root：原样取该组的 category 值`
- 约束段同步改。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_note_prompt.py tests/test_note_service.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/prompts/note_prompt.py backend/tests/test_note_prompt.py backend/tests/test_note_service.py
git commit -m "refactor(notes): 笔记分组字段由 error_type 改为 category"
```

---

### Task 5: 评测脚本兼容新旧字段

**Files:**
- Modify: `backend/app/scripts/eval_ground_truth.py:130-200,300-340`
- Modify: `backend/app/scripts/prompt_model_compare.py:50-60,120-130`
- Modify: `backend/app/scripts/prompt_thinking_compare.py:35-100`
- Test: `backend/tests/test_eval_ground_truth.py`（若不存在则新建最小用例）

**Interfaces:**
- Consumes: 采集 JSON 里每条 error 可能是 `category`（新）或 `error_type`（旧产物）
- Produces: 模块内 helper `_model_category(err: dict) -> str`，返回 `err.get("category") or err.get("error_type") or ""`

- [ ] **Step 1: 写测试**

`backend/tests/test_eval_ground_truth.py`：

```python
from app.scripts.eval_ground_truth import _model_category


def test_model_category_prefers_new_field():
    assert _model_category({"category": "冠词缺失", "error_type": "旧值"}) == "冠词缺失"


def test_model_category_falls_back_to_legacy_field():
    assert _model_category({"error_type": "词序不当"}) == "词序不当"


def test_model_category_missing_returns_empty():
    assert _model_category({}) == ""
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_eval_ground_truth.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实施**

- `eval_ground_truth.py` 加 `_model_category`，把 `me.get("error_type", "")` 全部替换为 `_model_category(me)`；报告渲染里的 `e['error_type']` 改 `_model_category(e)`。
- 两个 compare 脚本里 `e.get("error_type")` 改 `e.get("category") or e.get("error_type")`。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_eval_ground_truth.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/scripts/eval_ground_truth.py backend/app/scripts/prompt_model_compare.py backend/app/scripts/prompt_thinking_compare.py backend/tests/test_eval_ground_truth.py
git commit -m "fix(eval): 评测脚本兼容 category 与旧 error_type"
```

---

### Task 6: 前端类型、历史归一化与卡片渲染

**Files:**
- Modify: `web/src/api/messages.ts`
- Modify: `web/src/components/correction/ErrorCard.tsx`
- Modify: `web/src/components/correction/CorrectionReportCard.tsx`
- Test: `web/tests/e2e/correction.spec.ts`（补一条断言）

**Interfaces:**
- Produces: `interface ErrorBlock { category: string; fragment: string; explanation: string; correction: string }`
- Produces: `function normalizeReport(raw: unknown): CorrectionReport | null`（内部使用）：`category ?? error_type`；`has_errors` 缺失时按 `errors.length > 0` 计算；`rewrite` 缺失为 `null`
- Consumes: Task 2 的 `has_errors`（computed，仍在 JSON 里）

- [ ] **Step 1: 改类型与归一化**

`web/src/api/messages.ts`：`ErrorBlock.error_type` → `category`；新增归一化并在 `fetchMessages()` 的返回、`submitMessage()` 的两个 message 上应用：

```ts
function normalizeReport(raw: any): CorrectionReport | null {
  if (!raw) return null
  const errors = (raw.errors ?? []).map((e: any) => ({
    category: e.category ?? e.error_type ?? '',
    fragment: e.fragment ?? '',
    explanation: e.explanation ?? '',
    correction: e.correction ?? '',
  }))
  return {
    has_errors: typeof raw.has_errors === 'boolean' ? raw.has_errors : errors.length > 0,
    errors,
    rewrite: raw.rewrite ?? null,
  }
}
```

- [ ] **Step 2: 改 ErrorCard**

- 标签渲染 `{error.category}`。
- `correction === ''` 时渲染 `（建议删除）`（灰色文字）而不是 `✅ ` 空行。

- [ ] **Step 3: 改 CorrectionReportCard**

- `!report.has_errors` 分支：保留绿色文案（含「这段英文写得不错」，E2E 依赖），若 `report.rewrite?.natural` 存在，则在其下渲染 `<RewriteSection rewrite={...} only natural>`。
- 为不改 `RewriteSection` 的公开接口，`RewriteSection` 增加可选 prop `show?: 'both' | 'natural-only'`（默认 `both`）。

- [ ] **Step 4: 补 E2E 断言**

`web/tests/e2e/correction.spec.ts` 的 `U-C-03` 追加：

```ts
await expect(page.getByText('地道表达').first()).toBeVisible()
```

（Mock 的 no-error 分支已返回 `natural`，见 Task 3。）

- [ ] **Step 5: 构建 + E2E 验证**

Run:
```bash
cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run lint && npm run build && npm run test:e2e
```
Expected: lint 无 error、build 成功、E2E 全部通过

- [ ] **Step 6: 提交**

```bash
git add web/src/api/messages.ts web/src/components/correction/ErrorCard.tsx web/src/components/correction/CorrectionReportCard.tsx web/src/components/correction/RewriteSection.tsx web/tests/e2e/correction.spec.ts
git commit -m "feat(web): 纠错报告适配 category 契约并展示无错误时的地道改写"
```

---

### Task 7: 文档同步

**Files:**
- Modify: `docs/tech-design/02-Correction.md`（§1.2 契约 JSON 与字段说明、§1.2 末尾提示词描述）
- Modify: `PRD/pages/02-Correction.md`（若有 `error_type`/`has_errors` 描述）
- Test: 无（人工核对）

- [ ] **Step 1: 定位待改内容**

Run: `grep -n "error_type\|has_errors\|rewrite.*null\|提示词" docs/tech-design/02-Correction.md PRD/pages/02-Correction.md`

- [ ] **Step 2: 同步契约**

- JSON 示例的 `error_type` 改 `category`，示例值取自 spec §3 词表。
- 说明 `has_errors` 由后端派生、`rewrite` 必出、无错误时 `natural` 也可改写、删除类用空 `correction`。
- 提示词描述改为「V3 分类学 + 判定优先级 + OUT OF SCOPE」，删掉旧的「编程标识符/名词链/口语正常表达」描述。

- [ ] **Step 3: 提交**

```bash
git add docs/tech-design/02-Correction.md PRD/pages/02-Correction.md
git commit -m "docs(correction): 同步 V3 输出契约与提示词说明"
```

---

### Task 8: 全量验证

**Files:** 无

- [ ] **Step 1: 后端全量测试**

Run: `cd backend && .venv/bin/pytest -v`
Expected: 全部 PASS（需要 `docker compose up -d db`）

- [ ] **Step 2: 前端构建 + E2E**

Run:
```bash
cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run lint && npm run build && npm run test:e2e
```
Expected: 全部通过

- [ ] **Step 3: 确认不推送**

Run: `git status --short && git log --oneline -8`
Expected: 工作区干净；本地提交存在；`git branch -vv` 显示未 push

- [ ] **Step 4: 可选——用 mock 手动冒烟一次真实链路**

Run:
```bash
cd backend && LLM_MODE=mock .venv/bin/uvicorn app.main:app --port 8000
```
Expected: 提交一句话返回 `report.errors[].category` 与 `report.rewrite.natural`；无错误输入返回 `has_errors: false` 且 `rewrite.natural.text` 非空
