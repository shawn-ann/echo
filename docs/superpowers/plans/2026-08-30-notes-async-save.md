# 记笔记异步化实现计划 (notes-async-save)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除纠错报告中的 learnings 段，并将记笔记的规则生成改为后台异步，从而缩短纠错请求的同步响应时间。

**Architecture:** 两处核心变更：(1) 纠错提示词/契约/前端不再产出「学到的规则」，报告只含 errors+rewrite；(2) `POST /notes/save` 改为同步返回 `202 {accepted:true}`，用 FastAPI `BackgroundTasks` 在后台用独立的 DB session 执行第二次 LLM 调用与入库，前端点击后乐观反馈、刷新笔记列表页可见。去重逻辑与数据模型完全不变。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / asyncio `BackgroundTasks`；React 19 / Vite / oxlint；Playwright E2E。

**前置条件**
- 后端测试需运行中的 PostgreSQL（`echo` + `echo_test` 两库），来自 `backend/` 目录执行。
- 所有 pytest 命令从 `backend/` 运行；前端命令从 `web/` 运行（先 `source ~/.nvm/nvm.sh && nvm use 24`）。
- **不要 push 到 `v0.1`**（会触发生产部署）。仅在本地 commit。

---

# 一、File Structure

本次改动的文件地图（按职责划分）：

## 后端
| 文件 | 变更 | 职责 |
|------|------|------|
| `backend/app/prompts/correction_prompt.py` | 改 | 移除 learnings 段与输出字段、docstring 同步 |
| `backend/app/schemas/correction.py` | 改 | 删除 `Learning` 类与 `CorrectionBody.learnings` 字段 |
| `backend/app/services/llm_client.py` | 改 | `_default_responder` 纠错分支移除 learnings 载荷 |
| `backend/app/schemas/note.py` | 改 | 新增 `NoteSaveAccepted` |
| `backend/app/routers/notes.py` | 改 | `POST /notes/save` 改 202 + BackgroundTasks 后台执行 |
| `backend/tests/test_correction_prompt.py` | 改 | learnings 断言更新，删除 rule/example 断言函数 |
| `backend/tests/test_schemas_correction.py` | 改 | 移除 learnings 断言 |
| `backend/tests/test_messages_api.py` | 改 | 内联 mock 载荷移除 learnings |
| `backend/tests/test_correction_service.py` | 改 | 内联 mock 载荷移除 learnings |
| `backend/tests/test_prompt_thinking_compare.py` | 改 | 移除 learnings 断言与载荷 |
| `backend/tests/test_prompt_model_compare.py` | 改 | 移除 learnings 载荷与断言 |
| `backend/tests/test_notes_api.py` | 改 | 适配 202 异步返回；save 不再返回 note_id，改用 list 查 id |
| `backend/tests/test_note_service.py` | 不改 | `save_notes` 契约不变 |

## 前端
| 文件 | 变更 | 职责 |
|------|------|------|
| `web/src/api/messages.ts` | 改 | 移除 `Learning` 类型与 `CorrectionReport.learnings` |
| `web/src/api/notes.ts` | 改 | `SaveNoteResponse` → `NoteSaveAccepted {accepted}` |
| `web/src/store/conversation.tsx` | 改 | `saveNote` 返回结构去掉 ruleTitles |
| `web/src/components/correction/CorrectionReportCard.tsx` | 改 | 移除 LearningsSection 渲染 + 异步 toast 文案 |
| `web/src/components/correction/LearningsSection.tsx` | 删 | 不再使用 |
| `web/tests/e2e/notes.spec.ts` | 改 | 适配异步保存与 toast 文案 |

## 文档
| 文件 | 变更 | 职责 |
|------|------|------|
| `PRD/pages/02-Correction.md` | 改 | 移除 learnings 分区描述、AC-C-16，修正"学到的规则" |
| `PRD/Overview.md` | 改 | F-01 摘要去 learnings；F-02 补充异步说明 |
| `docs/tech-design/02-Correction.md` | 改 | §1.2 契约移除 learnings |
| `docs/tech-design/00-Architecture.md` | 改 | §4.4 记笔记接口说明改异步 |
| 前序 specs | 改 | 交叉引用异步设计（见 Task 16） |

---

# 二、Tasks

## Task 1: 移除纠错提示词中的 learnings 段

**Files:**
- Modify: `backend/app/prompts/correction_prompt.py`
- Modify: `backend/tests/test_correction_prompt.py`

- [ ] **Step 1: 更新提示词测试，先让它失败**

编辑 `backend/tests/test_correction_prompt.py:13`：

```python
    assert "learnings" in SYSTEM_PROMPT    # 旧
    assert "learnings" not in SYSTEM_PROMPT  # 新
```

同时删除 `test_correction_prompt.py` 中的 `test_system_prompt_contains_rule_and_example` 函数（line 27-29）。移除 learnings 段后，`rule`/`example` 不再出现在 SYSTEM_PROMPT，该函数无意义。

- [ ] **Step 2: 运行测试确认失败**

Run (from `backend/`): `pytest tests/test_correction_prompt.py -v`
Expected: `test_system_prompt_contains_contract_fields` FAIL on `assert "learnings" not in SYSTEM_PROMPT`

- [ ] **Step 3: 编辑提示词，移除 learnings 段与输出字段**

编辑 `backend/app/prompts/correction_prompt.py`（4 处）：

1. 模块 docstring（line 3-6）删除一行：
```
    "learnings[]：rule / example（wrong → correct）
```

2. 删除「### learnings」段（line 99-102）：
```
### learnings
- learnings 针对本次发现的错误给出简短学习要点，每条含 rule（错误规律）和 example（wrong → correct 格式）
- rule 应概括错误规律而非重复具体案例
- 同一规律的多个错误合并为一条 learning 的 example
```

3. 「## 改写与学习要点」（line 90）改为「## 改写」：
```
## 改写与学习要点
```
→
```
## 改写
```

4. 输出字段删除 learnings 行（line 109）：
```
- learnings（数组）：每条含 rule（中文错误规律）和 example（wrong → correct 格式）；无错误时为空数组
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_correction_prompt.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/prompts/correction_prompt.py backend/tests/test_correction_prompt.py
git commit -m "refactor(correction): 移除纠错提示词 learnings 段"
```

---

## Task 2: 移除纠错输出契约中的 learnings

**Files:**
- Modify: `backend/app/schemas/correction.py`
- Modify: `backend/tests/test_schemas_correction.py`

- [ ] **Step 1: 更新契约测试**

读 `backend/tests/test_schemas_correction.py` 全文。移除其中 `"learnings"` 键（line 14）、`parsed.learnings[0]` 断言（line 20）、`learnings=[]`（line 24/49）。若某个测试用例因 learnings 缺失而失去意义，删除该用例；否则仅移除 learnings 相关行。

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_schemas_correction.py -v`
Expected: FAIL（`CorrectionBody` 收到未预期字段或仍引用 learnings）

- [ ] **Step 3: 编辑契约**

编辑 `backend/app/schemas/correction.py`：
- 删除 `Learning` 类（line 24-27）
- 删除 `CorrectionBody.learnings` 字段（line 35）

```python
class CorrectionBody(BaseModel):
    """LLM 单轮纠错输出（无 intent/reply）。"""

    has_errors: bool
    errors: list[ErrorBlock] = Field(default_factory=list)
    rewrite: RewriteSection | None = None
    # learnings 已移除（见 notes-async-save）
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_schemas_correction.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/correction.py backend/tests/test_schemas_correction.py
git commit -m "refactor(correction): 移除 CorrectionBody.learnings 与 Learning 模型"
```

---

## Task 3: 更新 Mock LLM 纠错响应，移除 learnings 载荷

**Files:**
- Modify: `backend/app/services/llm_client.py`

- [ ] **Step 1: 编辑 `_default_responder`**

编辑 `backend/app/services/llm_client.py`（2 处）：

1. 「no-error」分支（line 93-102）删除 `"learnings": []` 行：
```python
    if "没有错误" in last or "no-error" in last:
        return json.dumps(
            {
                "has_errors": False,
                "errors": [],
                "rewrite": None,
            },
            ensure_ascii=False,
        )
```

2. 有错误分支（line 103-126）删除 `"learnings": [...]` 块（line 118-123）：
```python
    return json.dumps(
        {
            "has_errors": True,
            "errors": [
                {
                    "error_type": "动词形式",
                    "fragment": "interested in read",
                    "explanation": "介词后应接动名词形式",
                    "correction": "interested in reading",
                }
            ],
            "rewrite": {
                "minimal": {"text": "I am interested in reading English books.", "note": "介词后接动名词"},
                "natural": {"text": "I love reading English books.", "note": "更自然的表达"},
            },
        },
        ensure_ascii=False,
    )
```

> 注：笔记保存分支（`## 原文` 分支）的 `results`/`examples`/`references` 载荷**保持不变**。

- [ ] **Step 2: 运行测试，确认后续测试失败点**

Run: `pytest -v`
Expected: 失败集中在 test_messages_api / test_correction_service / test_prompt_*_compare 中的内联 learnings，将在 Task 4 修复。

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/llm_client.py
git commit -m "refactor(correction): mock 纠错响应移除 learnings 载荷"
```

---

## Task 4: 修复后端测试中的内联 learnings 引用

**Files:**
- Modify: `backend/tests/test_messages_api.py`
- Modify: `backend/tests/test_correction_service.py`
- Modify: `backend/tests/test_prompt_thinking_compare.py`
- Modify: `backend/tests/test_prompt_model_compare.py`

- [ ] **Step 1: 修复 `test_messages_api.py`**

`test_messages_api.py:49`（`test_post_messages_no_error`）：
```python
    mock.responder = lambda msgs: (
        '{"has_errors":false,"errors":[],"rewrite":null,"learnings":[]}'
    )
```
改为：
```python
    mock.responder = lambda msgs: (
        '{"has_errors":false,"errors":[],"rewrite":null}'
    )
```

- [ ] **Step 2: 修复 `test_correction_service.py`**

`test_correction_service.py` 中 `test_submit_llm_wrapped_report_unwraps` 的内联响应（line 86-91）：
```python
            responder=lambda msgs: (
                '{"report": {"has_errors": true, "errors": [{"error_type": "时态错误", "fragment": "go", '
                '"explanation": "x", "correction": "went"}], "rewrite": null, "learnings": []}}'
            )
```
将 `"rewrite": null, "learnings": []}}` 改为 `"rewrite": null}}`：
```python
            responder=lambda msgs: (
                '{"report": {"has_errors": true, "errors": [{"error_type": "时态错误", "fragment": "go", '
                '"explanation": "x", "correction": "went"}], "rewrite": null}}'
            )
```

- [ ] **Step 3: 修复 prompt 对比测试**

`backend/tests/test_prompt_thinking_compare.py`：
- line 4-5 `_mk_raw` 与 line 19-24 `test_summarize_result_extracts_errors_and_learnings`：移除 `learnings` 载荷与 learnings 断言，改测 errors 即可。
- line 33-35 中 `on_out`/`off_out` 的 `"learnings":[...]` 移除。

`backend/tests/test_prompt_model_compare.py`：
- line 4-18 中 `_mk_raw` 的 `learnings` 参数与 `s["learnings"]` 断言移除。

> 注：`scripts/prompt_model_compare.py` / `scripts/prompt_thinking_compare.py` 主脚本的 `_summarize_result` 内 `learnings = correction.get("learnings") or []` 对缺失字段返回空列表，不会崩，本次不强制清理（Task 16 备注）。

- [ ] **Step 4: 运行后端测试确认通过**

Run: `pytest -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_messages_api.py backend/tests/test_correction_service.py backend/tests/test_prompt_thinking_compare.py backend/tests/test_prompt_model_compare.py
git commit -m "test(correction): 适配移除 learnings 后的 mock 与断言"
```

---

## Task 5: 新增 `NoteSaveAccepted` schema 与契约测试

**Files:**
- Modify: `backend/app/schemas/note.py`
- Modify: `backend/tests/test_notes_api.py`

- [ ] **Step 1: 新增 schema**

编辑 `backend/app/schemas/note.py`，追加在文件末尾：

```python
class NoteSaveAccepted(BaseModel):
    accepted: bool
```

- [ ] **Step 2: 新增契约测试**

在 `backend/tests/test_notes_api.py` 中 `_auth` 之后追加：

```python
async def test_save_note_returns_accepted(api):
    client = api
    token = await _token(client)
    r = await client.post(POST_URL, json={
        "message_id": "00000000-0000-0000-0000-000000000000",
        "source_text": "She have many book",
        "errors": [_ERROR],
    }, headers=_auth(token))
    assert r.status_code == 202
    assert r.json() == {"accepted": True}


async def test_save_note_unauthorized(api):
    r = await api.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "x", "errors": [_ERROR]})
    assert r.status_code == 401
```

> 注：`test_save_note_unauthorized` 已在原文件 line 48-50 存在，切勿重复添加；此处仅保留 `test_save_note_returns_accepted` 为新测试。

- [ ] **Step 3: 运行确认失败**

Run: `pytest tests/test_notes_api.py::test_save_note_returns_accepted -v`
Expected: FAIL（当前返回 200，非 202）或 schema 尚未接入路由报 500。

---

## Task 6: 改造 `POST /notes/save` 为异步后台执行

**Files:**
- Modify: `backend/app/routers/notes.py`

- [ ] **Step 1: 编辑路由**

将 `backend/app/routers/notes.py` 重写为：`save_note` 注入 `BackgroundTasks` 与 `llm_client`，把实际保存挪到后台任务，返回 `202`。

```python
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db import async_session_factory, get_db
from app.models.user import User
from app.schemas.note import (
    NoteSaveAccepted,
    NoteDetailResponse,
    NoteListResponse,
)
from app.services import note_service
from app.services.auth_service import get_current_user
from app.services.llm_client import LLMClient, get_llm_client

router = APIRouter(prefix="/api/v1/notes", tags=["notes"])

logger = logging.getLogger(__name__)


async def _run_save_notes_async(
    user_id: uuid.UUID,
    source_message_id: uuid.UUID | None,
    source_text: str,
    errors: list[dict],
    llm_client: LLMClient,
):
    # get_db 的 session 随请求结束即关闭，后台任务必须自建独立 session
    try:
        async with async_session_factory() as session:
            await note_service.save_notes(
                session, user_id, source_message_id, source_text, errors, llm_client
            )
    except Exception:
        # 后台失败不阻断用户：记日志，本次保存静默丢弃，可重存
        logger.exception("异步保存笔记失败")


@router.post("/save", response_model=NoteSaveAccepted, status_code=202)
async def save_note(
    payload,  # noqa: F821 - 见下方完整签名
):
    ...
```

> 说明：上例省略了完整签名，完整实现见 Step 2。

- [ ] **Step 2: 写完整端点**

编辑 `backend/app/routers/notes.py`，将原 `save_note` 替换为：

```python
@router.post("/save", response_model=NoteSaveAccepted, status_code=202)
async def save_note(
    payload: "SaveNoteRequest",
    user: User = Depends(get_current_user),
    llm_client: LLMClient = Depends(get_llm_client),
    background_tasks: BackgroundTasks = None,  # type: ignore
):
    background_tasks.add_task(
        _run_save_notes_async,
        user.id,
        payload.message_id,
        payload.source_text,
        [e.model_dump() for e in payload.errors],
        llm_client,
    )
    return NoteSaveAccepted(accepted=True)
```

并在文件顶部 import 追加 `from app.schemas.note import SaveNoteRequest`（同时保留 `NoteSaveAccepted`）。

> 重要：`background_tasks: BackgroundTasks` 必须作为形参由 FastAPI 注入（FastAPI 识别 `BackgroundTasks` 类型并注入实例）。上述 `= None` 仅为类型占位，实际由 FastAPI 注入，勿手动传 None。

`list_notes` / `get_note` / `delete_note` / `delete_case` 端点保持不变。

- [ ] **Step 3: 运行契约测试确认通过**

Run: `pytest tests/test_notes_api.py::test_save_note_returns_accepted tests/test_notes_api.py::test_save_note_unauthorized -v`
Expected: `test_save_note_returns_accepted` PASS（202 + {accepted:true}）；`test_save_note_unauthorized` PASS（401）。

> 说明：httpx `ASGITransport` 会 await 完整 ASGI 生命周期，包括 background task，因此在 `await client.post(...)` 返回时后台任务已执行完毕、笔记已入库。这保证后续 Task 7 的 list/detail/delete 能查到数据。

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/note.py backend/app/routers/notes.py
git commit -m "feat(notes): /notes/save 改为异步后台执行，返回 202"
```

---

## Task 7: 重写 notes API 测试，适配异步返回

**Files:**
- Modify: `backend/tests/test_notes_api.py`

因为 save 不再返回 `saved_notes`/`note_id`，依赖 save 响应取 id 的测试需改为：save 后从 list 接口查 id。

- [ ] **Step 1: 新增 helper**

在 `backend/tests/test_notes_api.py` 中 `_auth` 之后追加 helper：

```python
async def _first_note_id(client, token) -> str:
    r = await client.get(LIST_URL, headers=_auth(token))
    assert r.status_code == 200
    notes = r.json()["notes"]
    assert len(notes) == 1
    return notes[0]["id"]
```

- [ ] **Step 2: 逐条改造断言 save 响应的测试**

以下测试改为「save → 断言 202 → 从 list 查 id」：

**`test_save_note_creates_note`**（line 53-65）→ 删除或改写为断言 202：
```python
async def test_save_note_creates_note(api):
    client = api
    token = await _token(client)
    r = await client.post(POST_URL, json={
        "message_id": "00000000-0000-0000-0000-000000000000",
        "source_text": "She have many book",
        "errors": [_ERROR],
    }, headers=_auth(token))
    assert r.status_code == 202
    assert r.json() == {"accepted": True}
```

**`test_get_note_detail_with_examples_and_cases`**（line 87-99）：把
```python
    save_r = await client.post(POST_URL, json={...}, headers=_auth(token))
    note_id = save_r.json()["saved_notes"][0]["note_id"]
```
改为
```python
    await client.post(POST_URL, json={...}, headers=_auth(token))
    note_id = await _first_note_id(client, token)
```

**`test_delete_note`**（line 109-117）与 **`test_delete_case`**（line 120-130）：同样把 `save_r.json()["saved_notes"][0]["note_id"]` 改为 `await _first_note_id(client, token)`。

**`test_get_note_detail_other_user_not_found`**（line 133-155）：同样改为 save 后 `await _first_note_id(client, token_a)`。

**`test_list_notes_after_save`**（line 76-84）无需改（它只调 save 再 list）。**`test_list_notes_empty`** 无需改。

- [ ] **Step 3: 运行全部 notes API 测试**

Run: `pytest tests/test_notes_api.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_notes_api.py
git commit -m "test(notes): 适配 /notes/save 异步 202 返回"
```

---

## Task 8: 新增后台 LLM 失败不阻塞的验证

**Files:**
- Modify: `backend/tests/test_notes_api.py`

- [ ] **Step 1: 新增测试：LLM 失败时 save 仍返回 202**

在 `backend/tests/test_notes_api.py` 末尾追加：

```python
async def test_save_note_llm_failure_still_returns_accepted(api):
    """后台 LLM 失败不阻断用户：save 仍返回 202，不 5xx"""
    from app.core.errors import AppError

    client = api
    # 覆盖依赖让 LLM 抛 503
    app = create_app()
    mock = MockLLMClient(responder=lambda msgs: (_ for _ in ()).throw(AppError(503, "LLM_SERVICE_UNAVAILABLE", "服务不可用")))
    app.dependency_overrides[get_llm_client] = lambda: mock
    transport = ASGITransport(app=app)
    # 需要将当前 client 替换；但 api fixture 已持有旧 app。
    # 简单方案：新建 app+client
    ...
```

> 说明：此用例因 `api` fixture 已绑定旧 app 而稍复杂。**替代更简单方案**（推荐）：为该断言新增独立 fixture 或直接复用 `_run_save_notes_async` 单元测试。若觉得过度，可跳过此测试——AC-N-07 的"不 5xx"已由 BackgroundTasks 的 try/except 在 Task 6 实现保证，此处仅为回归护栏。

决策：**保留一个简单版本**——在 `test_note_service.py` 中已有 `_RaisingLLMClient` 验证 `save_notes` 抛 AppError。对应地，在 `test_notes_api.py` 增加一个异步路径测试，用 `monkeypatch` 使 `_run_save_notes_async` 内 `logger.exception` 不崩。若实现发现复杂度高，降低优先级为"可选"并在提交说明注明。

（本 Task 为可选护栏。若执行中发现开销大，可跳过并记录：save 的 202 语义已在 Task 6/7 覆盖。）

---

## Task 9: 前端 API 类型更新

**Files:**
- Modify: `web/src/api/messages.ts`
- Modify: `web/src/api/notes.ts`

- [ ] **Step 1: 更新 `messages.ts`**

编辑 `web/src/api/messages.ts`：
- 删除 `Learning` 接口（line 20-23）
- 删除 `CorrectionReport.learnings: Learning[]` 字段（line 29）：

```typescript
export interface CorrectionReport {
  has_errors: boolean
  errors: ErrorBlock[]
  rewrite: RewriteSection | null
}
```

- [ ] **Step 2: 更新 `notes.ts`**

编辑 `web/src/api/notes.ts`：

```typescript
export interface NoteSaveAccepted {
  accepted: boolean
}
```

删除 `SavedNoteItem` 与 `SaveNoteResponse` 接口（line 4-13），`saveNote` 改为：

```typescript
export async function saveNote(
  messageId: string,
  sourceText: string,
  errors: ErrorBlock[],
): Promise<NoteSaveAccepted> {
  return http.post<NoteSaveAccepted>('/notes/save', {
    message_id: messageId,
    source_text: sourceText,
    errors,
  })
}
```

- [ ] **Step 3: 运行前端类型检查（构建）**

> 先处理 use 到 SavedNoteItem 的地方（Task 10）。若当前直接 build 会因类型未用/引用残留报错，属预期，Task 10 一并清。此处仅执行：
Run (from `web/`): `npm run build`
Expected: 因 Task 10 未完成而报错（conversation.tsx 仍引用 saved_notes）——**允许失败**，此为过渡状态。

---

## Task 10: 更新前端 store 与组件（含学习移除 & 异步 toast）

**Files:**
- Modify: `web/src/store/conversation.tsx`
- Modify: `web/src/components/correction/CorrectionReportCard.tsx`
- Delete: `web/src/components/correction/LearningsSection.tsx`

- [ ] **Step 1: 更新 `conversation.tsx` 的 `saveNote`**

编辑 `web/src/store/conversation.tsx`，`saveNote` 改为不依赖 saved_notes：

```typescript
  const saveNote = useCallback(
    async (
      messageId: string,
      sourceText: string,
      errors: ErrorBlock[],
    ): Promise<{ success: boolean; error?: string }> => {
      try {
        await notesApi.saveNote(messageId, sourceText, errors)
        return { success: true }
      } catch (err) {
        return {
          success: false,
          error: err instanceof ApiError ? err.message : '保存失败，请重试',
        }
      }
    },
    [],
  )
```

- [ ] **Step 2: 更新 `CorrectionReportCard.tsx`**

- 删除 `import LearningsSection`（line 6）与 `<LearningsSection learnings={report.learnings ?? []} />`（line 90）。
- `handleSaveOne`：因不再返回 ruleTitles，成功统一提示：
```typescript
  async function handleSaveOne(index: number, error: ErrorBlock) {
    setErrorStates((prev) => ({ ...prev, [index]: 'loading' }))
    const result = await saveNote(message.id, sourceText, [error])
    if (result.success) {
      setErrorStates((prev) => ({ ...prev, [index]: 'done' }))
      showToast('已提交，笔记正在后台保存')
    } else {
      setErrorStates((prev) => ({ ...prev, [index]: 'idle' }))
      showToast(result.error ?? '保存失败，请重试')
    }
  }
```
- `handleSaveAll`：
```typescript
  async function handleSaveAll() {
    if (batchState !== 'idle') return
    setBatchState('loading')
    const result = await saveNote(message.id, sourceText, report.errors)
    if (result.success) {
      setBatchState('done')
      showToast('已提交，正在后台保存全部笔记')
    } else {
      setBatchState('idle')
      showToast(result.error ?? '保存失败，请重试')
    }
  }
```

- [ ] **Step 3: 删除 `LearningsSection.tsx`**

```bash
git rm web/src/components/correction/LearningsSection.tsx
```

- [ ] **Step 4: 运行 lint 与 build**

Run (from `web/`): `npm run lint && npm run build`
Expected: ALL PASS（无类型错误、无未使用引用）

- [ ] **Step 5: Commit**

```bash
git add web/src/api/messages.ts web/src/api/notes.ts web/src/store/conversation.tsx web/src/components/correction/CorrectionReportCard.tsx
git commit -m "feat(correction): 移除学到的规则分区，记笔记改异步乐观反馈"
```

---

## Task 11: 更新前端 E2E 测试（异步保存 & baggage 文案）

**Files:**
- Modify: `web/tests/e2e/notes.spec.ts`

- [ ] **Step 1: 引入等待笔记入库的 helper**

E2E 后端为真实 uvicorn（`LLM_MODE=mock`），background task 随响应后执行。为保证「保存后导航到笔记页能看到」，在断言前确保入库完成。编辑 `notes.spec.ts`，在 `loginAndSubmit` 之后追加：

```typescript
async function waitUntilNotePersisted(page: Page) {
  // 后台 LLM 完成入库后，notes 列表页能查到笔记；轮询直到出现
  await page.getByRole('link', { name: /我的笔记/ }).click()
  await expect(page).toHaveURL(/\/notes$/)
  await expect(page.getByRole('button', { name: /介词后加 -ing 形式/ })).toBeVisible({ timeout: 20000 })
}
```

- [ ] **Step 2: 更新 toast 文案断言**

`/已记入/` 正则改为匹配新文案：

- `N-01`（line 39）与 `N-02`（line 45）：把 `/已记入/` 改为 `/已提交，.*后台保存/`。
- `N-02` 的 `/已记入 \d+ 条规则笔记/` 改为 `/已提交，正在后台保存全部笔记/`。

统一将单条断言文案改为 `/已提交.*后台保存/`，批量改为 `/已提交，正在后台保存全部笔记/`。

- [ ] **Step 3: 更新 N-03 / N-04 的笔记落地断言**

`N-03` 与 `N-04` 当前在点击「全部记笔记」并看到 toast 后直接导航。改为：看到 toast 后调用 `waitUntilNotePersisted`，再断言详情（`N-04` 的展开/示例）。`N-03` 可整体替换为 `waitUntilNotePersisted` 的展开逻辑（其本身就是导航+查 rule_title）。

- [ ] **Step 4: 运行 E2E**

前置：`docker compose up -d db` 已运行，`backend/.venv/bin/uvicorn` 存在。E2E 自动起后端（mock）与前端。
Run (from `web/`): `npm run test:e2e -- notes.spec.ts`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add web/tests/e2e/notes.spec.ts
git commit -m "test(e2e): 适配记笔记异步保存"
```

---

## Task 12: 运行全量测试验证

- [ ] **Step 1: 后端全量**

Run (from `backend/`): `pytest -v`
Expected: ALL PASS

- [ ] **Step 2: 前端 lint + build**

Run (from `web/`): `npm run lint && npm run build`
Expected: ALL PASS

- [ ] **Step 3: 全部 E2E**

Run (from `web/`): `npm run test:e2e`
Expected: ALL PASS

---

## Task 13 (文档可选): PRD 更新

**Files:**
- Modify: `PRD/pages/02-Correction.md`
- Modify: `PRD/Overview.md`

- [ ] **Step 1: `PRD/pages/02-Correction.md`**

- §4.5 ③「学到的规则」分区（line 102-112）整段删除；若保留分区名，改为说明移除原因。
- AC-C-16（line 185）删除（learnings 相关）。
- §4.7 字段说明（line 126/129）移除 learnings 相关表述。
- §7.2 输出约束（line 223）移除 learnings 结构提及。
- 变更记录追加 V 记录。
- 非目标（§5, line 193）「不做记笔记」已过时（现状已实现），同步修正。

- [ ] **Step 2: `PRD/Overview.md`**

- F-01 摘要（line 41）移除「学到的规则」分区表述。
- F-02（line 52-57）补充「保存为异步，点击后立即反馈，规则后台生成后刷新可见」。
- 变更记录追加 V。

- [ ] **Step 3: Commit**

```bash
git add PRD/pages/02-Correction.md PRD/Overview.md
git commit -m "docs(prd): 移除 learnings，记笔记异步化说明"
```

> 若 PRD 也有 AC 编号重排需求，以实际文档为准；本计划以移除为主，不强制重排导致大改。

---

## Task 14 (文档可选): 技术设计更新

**Files:**
- Modify: `docs/tech-design/02-Correction.md`
- Modify: `docs/tech-design/00-Architecture.md`

- [ ] **Step 1: `02-Correction.md`**

- §1.2 契约（line 45-61）移除 learnings 相关字段与示例。
- 其他 learnings 引用（line 74/76/319 变更记录）同步清理。

- [ ] **Step 2: `00-Architecture.md`**

- §4.4 记笔记路由契约（line 177-178）：`POST /notes/save` 改为「返回 202 accepted，后台异步执行 + 独立 session」。
- 同步变更记录。

- [ ] **Step 3: Commit**

```bash
git add docs/tech-design/02-Correction.md docs/tech-design/00-Architecture.md
git commit -m "docs(tech): 记笔记异步化与 learnings 移除同步"
```

---

## Task 15 (文档可选): 前序 specs 交叉引用

**Files:**
- Modify: `docs/superpowers/specs/2026-08-29-notes-feature-design.md`
- Modify: `docs/superpowers/specs/2026-08-30-notes-examples-dedup-design.md`

- [ ] **Step 1: 更新 `notes-feature-design.md`**

- §4.1 `POST /notes/save` 返回结构改为「202 + accepted」（§3.2 异步设计）。
- §5.4 前端触发流程补「乐观反馈 + 后台入账 + 刷新可见」。
- §六 错误处理改为「后台记日志、不 toast」。

- [ ] **Step 2: 更新 `notes-examples-dedup-design.md`**

- 顶部注明「执行改为异步，契约不变」引用 notes-async-save 设计。

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-08-29-notes-feature-design.md docs/superpowers/specs/2026-08-30-notes-examples-dedup-design.md
git commit -m "docs(specs): 笔记功能 specs 交叉引用异步设计"
```

---

## Task 16 (文档可选): 废弃评估脚本备注

**Files:**
- Modify: `docs/superpowers/specs/2026-08-30-notes-async-save-design.md`（启用该计划时如已存在）

若 `docs/superpowers/specs/2026-08-30-notes-async-save-design.md` 已存在，在其「未来演进」补充：
- 评估脚本 `scripts/prompt_model_compare.py` / `prompt_thinking_compare.py` 的 learnings 计数逻辑随提示词收敛一并清理；`golden_cases.json` 的 `ref_learnings_min` key 失去意义，改只看 errors 命中率。

无需新增文件；如该 spec 不存在则跳过本 Task。

---

# 三、Self-Review

**1. Spec 覆盖核对（对应 `notes-async-save-design.md`）：**
- ✅ 移除 learnings：Task 1-4（提示词/契约/mock/测试）、Task 9-10（前端）、Task 13-14（文档）。
- ✅ 异步化：Task 5-7（schema/路由/测试）、Task 10（前端乐观反馈）、Task 8（失败不阻塞护栏）。
- ✅ 202 返回语义：Task 5-7。
- ✅ 去重不变：依赖 `note_service.save_notes` 不动（未列修改文件，测试 test_note_service 全绿覆盖）。
- ✅ 后台独立 session：Task 6 `async_session_factory()`。

**2. Placeholder 扫描：**
- Task 5 Step 2 曾误列 `test_save_note_unauthorized` 与现有重复，已在注释中明确"仅新增 returns_accepted"，避免重复添加。
- Task 8 明确标注"可选护栏"，规避过度设计。
- 所有 code block 均含实际代码或明确指引。

**3. 类型一致性：**
- `SaveNoteRequest`（routers import）与 schemas 一致；`SaveNoteAccepted` 在 Task 5 定义、Task 6 使用。
- `NoteSaveAccepted` 命名在 Task 5 Step 1 定义、Task 6 Step 2 import；前端 `NoteSaveAccepted` 对应（Task 9 Step 2）。
- `_run_save_notes_async` 签名（user_id, source_message_id, source_text, errors, llm_client）在 Task 6 Step 2 与 add_task 调用一致。
- `_first_note_id(client, token)` 定义于 Task 7 Step 1，供 Task 7 多测试复用，签名一致。
- frontend `saveNote` 返回 `{ success, error? }` 在 Task 10 Step 1 定义，CorrectionReportCard 的 handleSaveOne/All 按其消费，一致。

---

# 四、Execution Handoff

计划已保存至 `docs/superpowers/plans/2026-08-30-notes-async-save.md`。

两种执行方式：

**1. Subagent-Driven（推荐）** — 每个 Task 派发独立 subagent，任务间两阶段评审，快速迭代。

**2. Inline Execution** — 本会话内按 executing-plans 批量执行，带检查点。

选哪种？