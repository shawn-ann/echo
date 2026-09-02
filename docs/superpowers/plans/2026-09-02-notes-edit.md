# 移除个人易错警示 + 笔记编辑功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除 `notes.warning`（个人易错警示）字段，并为笔记增加内联编辑功能（rule_title + knowledge_point + alternatives + feynman_question）。

**Architecture:** 后端模型/schema/prompt/mock/service 全部移除 `warning`；新增 `PUT /api/v1/notes/{id}`（`UpdateNoteRequest` → 更新规则级 4 字段，按用户隔离）。前端 `NoteCard` 移除警示区块、标签「职场同义备选」改「同义备选」、新增编辑态（内联、卡片增宽、手动保存/取消、空值校验）。开发库直接重建 DB（不写迁移）。

**Tech Stack:** FastAPI + SQLAlchemy async + Pydantic 2（后端）；React 19 + TS + Tailwind（前端）；pytest + httpx ASGI（后端测试）、tsc + oxlint + Playwright E2E（前端）。

**关联 spec:** `docs/superpowers/specs/2026-09-02-notes-edit-design.md`

---

## 文件结构

### 后端（Task 1-4）
- `backend/app/models/note.py` — 删 `warning` 列
- `backend/app/schemas/note.py` — `NoteRuleResult`/`NoteDetailResponse` 删 `warning`；新增 `UpdateNoteRequest`
- `backend/app/prompts/note_prompt.py` — 删 `warning` 字段说明与示例
- `backend/app/services/llm_client.py` — mock 笔记响应删 `warning`
- `backend/app/services/note_service.py` — `save_notes`/`get_note_detail` 删 `warning`；新增 `update_note`
- `backend/app/routers/notes.py` — 新增 `PUT /{note_id}`

### 后端测试
- `backend/tests/test_models_note.py` — 删 warning 引用
- `backend/tests/test_note_prompt.py` — 断言调整（warning 不存在）
- `backend/tests/test_note_service.py` — mock/断言删 warning；新增 update_note 测试
- `backend/tests/test_notes_api.py` — `_seed_note`/`_mock_responder`/断言删 warning；新增 PUT 测试

### 前端（Task 5-6）
- `web/src/api/notes.ts` — `NoteDetailResponse` 删 `warning`；新增 `UpdateNoteRequest`/`updateNote`
- `web/src/components/notes/NoteCard.tsx` — 删警示区块、标签改名、新增编辑态
- `web/tests/e2e/notes.spec.ts` — N-03 断言调整；新增编辑保存用例

---

## Task 1: 后端移除 `warning` 字段（模型/schema/prompt/mock）

**Files:**
- Modify: `backend/app/models/note.py`
- Modify: `backend/app/schemas/note.py`
- Modify: `backend/app/prompts/note_prompt.py`
- Modify: `backend/app/services/llm_client.py`
- Test: `backend/tests/test_models_note.py`

- [ ] **Step 1: 更新模型测试 `backend/tests/test_models_note.py`**

删除所有 `warning="..."` 参数，测试名中的语义可保留。用 read 打开文件，逐处删除 `warning="w",`、`warning="你常忘给 she/he/it 加 -s",` 等。同时 `test_create_note_with_8field_fields` 断言改为不检查 `warning`（该测试名为 `_with_8field_` 建议改为 `_with_7field_` 并删除对 `note.warning` 的访问——实际该测试没断言 warning，仅创建时传参，删参即可）。

用 `grep -n warning backend/tests/test_models_note.py` 定位所有行并删除。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_models_note.py -v`
Expected: FAIL（模型仍有 warning，测试删除参数后创建报 `TypeError` 或相反——先删测试参数，若测试因模型多余字段不失败则说明测试未覆盖，改为在测试断言中显式 `assert not hasattr(note, "warning")`）

> 说明：SQLAlchemy 模型删字段后，测试里传 `warning=` 会 `TypeError`。所以顺序应是**先改模型**再改测试。但 TDD 要求测试先失败。这里用**删除字段后测试断言不传 warning 能过**的方式验证：先把模型 warning 删了，测试的 warning 传参会 TypeError → RED；然后删测试参数 → GREEN。调整如下。

- [ ] **Step 3: 从 `backend/app/models/note.py` 删除 `warning` 列**

删除第 20 行 `warning: Mapped[str] = mapped_column(Text, nullable=False)`。

- [ ] **Step 4: 删除测试中所有 `warning` 参数并运行确认通过**

删除 `backend/tests/test_models_note.py` 中所有 `warning=...` 参数。

Run: `cd backend && source .venv/bin/activate && pytest tests/test_models_note.py -v`
Expected: PASS（模型不再有 warning，测试不传该参数）

- [ ] **Step 5: 更新 `backend/app/schemas/note.py`**

`NoteRuleResult` 删除 `warning: str`（第 16 行）；`NoteDetailResponse` 删除 `warning: str`（第 52 行）。

- [ ] **Step 6: 更新 `backend/app/prompts/note_prompt.py`**

- 输出 JSON 示例删除 `"warning": "..."` 行（第 25 行）
- 字段要求删除 `- warning：针对本次错误的个人易错警示，提醒用户规避`（第 47 行）

- [ ] **Step 7: 更新 `backend/app/services/llm_client.py` mock**

笔记分支 `_default_responder` 删除 `"warning": "你常把介词后的动词写成原形，注意介词后一律用 -ing",`（第 80 行）。

- [ ] **Step 8: 运行全量确认（此时 service 会因 schema 变化报错，属预期）**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_models_note.py tests/test_note_prompt.py -v`
Expected: 通过（test_note_prompt 第 8 行断言 `"warning" in prompt` 会失败——Step 9 处理）

- [ ] **Step 9: 更新 `backend/tests/test_note_prompt.py`**

`test_system_prompt_contains_8field_fields` 中删除 `assert "warning" in prompt`（第 8 行），或改为 `assert "warning" not in prompt`。

- [ ] **Step 10: 提交**

```bash
git add backend/app/models/note.py backend/app/schemas/note.py backend/app/prompts/note_prompt.py backend/app/services/llm_client.py backend/tests/test_models_note.py backend/tests/test_note_prompt.py
git commit -m "refactor(notes): 移除个人易错警示字段（warning）"
```

---

## Task 2: 更新 `note_service` 移除 warning + 新增 `update_note`

**Files:**
- Modify: `backend/app/services/note_service.py`
- Test: `backend/tests/test_note_service.py`

- [ ] **Step 1: 更新测试 `backend/tests/test_note_service.py`**

1. 删除所有 mock responder 里的 `"warning": ...`（第 26、72、77、123、148 行附近）
2. 删除断言 `assert note.warning == ...`（第 50、110 行）
3. `test_save_creates_note_with_8field_and_case` 断言中删除 `warning` 行

用 grep 定位并逐处处理。

- [ ] **Step 2: 新增 update_note 测试（追加到文件末尾）**

```python
async def test_update_note_fields():
    """update_note 更新规则级字段（含 rule_title），案例不变"""
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(
            user_id=uid,
            rule_title="原标题",
            knowledge_point="kp",
            alternatives=["A"],
            feynman_question="q",
        )
        s.add(note)
        await s.flush()
        s.add(NoteCase(note_id=note.id, user_id=uid, original_sentence="src", polished_sentence="fix", change_details="d", error_root="r"))
        await s.commit()
        note_id = note.id

    async with async_session_factory() as s:
        from app.schemas.note import UpdateNoteRequest
        from app.services.note_service import update_note

        payload = UpdateNoteRequest(
            rule_title="新标题",
            knowledge_point="新知识点",
            alternatives=["X", "Y"],
            feynman_question="新费曼",
        )
        result = await update_note(s, uid, note_id, payload)
        assert result is not None
        assert result.rule_title == "新标题"
        assert result.knowledge_point == "新知识点"
        assert result.alternatives == ["X", "Y"]
        assert result.feynman_question == "新费曼"

    async with async_session_factory() as s:
        note = (await s.get(Note, note_id))
        assert note.rule_title == "新标题"
        assert note.knowledge_point == "新知识点"
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note_id))).scalars().all()
        assert len(cases) == 1  # 案例不变


async def test_update_note_other_user_returns_none():
    """非本人笔记 → update_note 返回 None（路由转 404）"""
    uid1 = await _demo_user_id()
    async with async_session_factory() as s:
        from app.core.security import hash_password
        from app.models.user import User, UserStatus
        s.add(User(username="other_edit", password_hash=hash_password("other1234"), status=UserStatus.active))
        await s.commit()
        uid2 = (await s.execute(select(User).where(User.username == "other_edit"))).scalar_one().id

    async with async_session_factory() as s:
        note = Note(user_id=uid2, rule_title="他人笔记", knowledge_point="kp", alternatives=[], feynman_question="q")
        s.add(note)
        await s.commit()
        note_id = note.id

    async with async_session_factory() as s:
        from app.schemas.note import UpdateNoteRequest
        from app.services.note_service import update_note

        payload = UpdateNoteRequest(rule_title="x", knowledge_point="y", alternatives=[], feynman_question="z")
        result = await update_note(s, uid1, note_id, payload)
        assert result is None
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_note_service.py -v`
Expected: 除新增 2 测试外，warning 相关删除后应通过；新增测试 `test_update_note_fields` FAIL（`update_note` 未定义 ImportError）

- [ ] **Step 4: 更新 `backend/app/services/note_service.py`**

1. `save_notes` 中删除 `warning=result.warning,`（第 66 行）
2. `get_note_detail` 中删除 `warning=note.warning,`（第 153 行）
3. 新增 `update_note` 函数与 import `UpdateNoteRequest`：

```python
async def update_note(
    session: AsyncSession,
    user_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: UpdateNoteRequest,
) -> NoteDetailResponse | None:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user_id:
        return None
    note.rule_title = payload.rule_title
    note.knowledge_point = payload.knowledge_point
    note.alternatives = payload.alternatives
    note.feynman_question = payload.feynman_question
    note.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(note)

    cases = (
        await session.execute(
            select(NoteCase)
            .where(NoteCase.note_id == note_id, NoteCase.user_id == user_id)
            .order_by(NoteCase.created_at)
        )
    ).scalars().all()
    return NoteDetailResponse(
        id=note.id,
        rule_title=note.rule_title,
        knowledge_point=note.knowledge_point,
        alternatives=note.alternatives,
        feynman_question=note.feynman_question,
        cases=[
            NoteCaseItem(
                id=c.id,
                original_sentence=c.original_sentence,
                polished_sentence=c.polished_sentence,
                change_details=c.change_details,
                error_root=c.error_root,
                created_at=c.created_at,
            )
            for c in cases
        ],
    )
```

import 行更新为：
```python
from app.schemas.note import (
    NoteCaseItem,
    NoteDetailResponse,
    NoteListItem,
    NoteLLMResponse,
    NoteRuleResult,
    UpdateNoteRequest,
)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_note_service.py -v`
Expected: PASS（原测试 + 2 个新测试）

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/note_service.py backend/tests/test_note_service.py
git commit -m "feat(notes): note_service 移除 warning，新增 update_note"
```

---

## Task 3: Schema 新增 `UpdateNoteRequest`

**Files:**
- Modify: `backend/app/schemas/note.py`
- Test: `backend/tests/test_schemas_*`（无既有，直接新增 `backend/tests/test_schemas_note.py`）

- [ ] **Step 1: 新增测试 `backend/tests/test_schemas_note.py`**

```python
import pytest
from pydantic import ValidationError

from app.schemas.note import UpdateNoteRequest


def test_update_note_request_valid():
    payload = UpdateNoteRequest(
        rule_title="标题",
        knowledge_point="知识点",
        alternatives=["A", "B"],
        feynman_question="费曼",
    )
    assert payload.rule_title == "标题"
    assert payload.alternatives == ["A", "B"]


def test_update_note_request_alternatives_can_be_empty():
    payload = UpdateNoteRequest(
        rule_title="标题",
        knowledge_point="知识点",
        alternatives=[],
        feynman_question="费曼",
    )
    assert payload.alternatives == []


@pytest.mark.parametrize("field", ["rule_title", "knowledge_point", "feynman_question"])
def test_update_note_request_text_fields_required(field):
    data = {
        "rule_title": "t",
        "knowledge_point": "k",
        "alternatives": [],
        "feynman_question": "f",
    }
    data[field] = ""
    with pytest.raises(ValidationError):
        UpdateNoteRequest(**data)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_schemas_note.py -v`
Expected: FAIL（`UpdateNoteRequest` 未定义）

- [ ] **Step 3: 在 `backend/app/schemas/note.py` 新增 `UpdateNoteRequest`**

在 `NoteDetailResponse` 之后追加：

```python
class UpdateNoteRequest(BaseModel):
    rule_title: str = Field(min_length=1, max_length=200)
    knowledge_point: str = Field(min_length=1)
    alternatives: list[str] = Field(default_factory=list)
    feynman_question: str = Field(min_length=1)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_schemas_note.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/note.py backend/tests/test_schemas_note.py
git commit -m "feat(notes): 新增 UpdateNoteRequest schema 与校验测试"
```

---

## Task 4: 路由新增 `PUT /api/v1/notes/{note_id}`

**Files:**
- Modify: `backend/app/routers/notes.py`
- Test: `backend/tests/test_notes_api.py`

- [ ] **Step 1: 更新 `backend/tests/test_notes_api.py`**

1. `_mock_responder`（第 25 行）删除 `"warning": ...`
2. `_seed_note`（第 62 行）删除 `warning="w",`
3. `test_get_note_detail_8field`（第 111 行）删除 `assert detail["warning"] == "w"`，测试名改为 `test_get_note_detail_fields`
4. 追加 PUT 测试：

```python
async def test_update_note_api(api):
    client = api
    token = await _token(client)
    note_id = await _seed_note(client, token)
    r = await client.put(f"{LIST_URL}/{note_id}", json={
        "rule_title": "编辑后的标题",
        "knowledge_point": "编辑后的知识点",
        "alternatives": ["N1", "N2"],
        "feynman_question": "编辑后的费曼",
    }, headers=_auth(token))
    assert r.status_code == 200
    detail = r.json()
    assert detail["rule_title"] == "编辑后的标题"
    assert detail["knowledge_point"] == "编辑后的知识点"
    assert detail["alternatives"] == ["N1", "N2"]
    assert detail["feynman_question"] == "编辑后的费曼"
    assert "warning" not in detail
    # 案例保持
    assert len(detail["cases"]) == 1


async def test_update_note_not_found(api):
    client = api
    token = await _token(client)
    r = await client.put(f"{LIST_URL}/00000000-0000-0000-0000-000000000000", json={
        "rule_title": "t", "knowledge_point": "k", "alternatives": [], "feynman_question": "f",
    }, headers=_auth(token))
    assert r.status_code == 404


async def test_update_note_empty_text_400(api):
    client = api
    token = await _token(client)
    note_id = await _seed_note(client, token)
    r = await client.put(f"{LIST_URL}/{note_id}", json={
        "rule_title": "", "knowledge_point": "k", "alternatives": [], "feynman_question": "f",
    }, headers=_auth(token))
    assert r.status_code == 400


async def test_update_note_other_user_404(api):
    client = api
    async with async_session_factory() as s:
        s.add(User(username="edit_isol", password_hash=hash_password("iso1234"), status=UserStatus.active))
        await s.commit()
    token_a = await _token(client)
    note_id = await _seed_note(client, token_a)
    r_b = await client.post(LOGIN_URL, json={"username": "edit_isol", "password": "iso1234"})
    assert r_b.status_code == 200
    token_b = r_b.json()["token"]
    r = await client.put(f"{LIST_URL}/{note_id}", json={
        "rule_title": "t", "knowledge_point": "k", "alternatives": [], "feynman_question": "f",
    }, headers=_auth(token_b))
    assert r.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_notes_api.py -v`
Expected: FAIL（PUT 无路由 → 405/404；detail 断言 warning 先删）

- [ ] **Step 3: 更新 `backend/app/routers/notes.py`**

import 加 `UpdateNoteRequest`，在 `get_note` 后新增：

```python
@router.put("/{note_id}", response_model=NoteDetailResponse)
async def update_note(
    note_id: uuid.UUID,
    payload: UpdateNoteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    detail = await note_service.update_note(session, user.id, note_id, payload)
    if detail is None:
        raise AppError(404, "NOTE_NOT_FOUND", "笔记不存在")
    return detail
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_notes_api.py -v`
Expected: PASS

- [ ] **Step 5: 后端全量回归**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: 全部 PASS（若因本地开发库有旧 warning 列导致的测试问题，需先重建测试库——conftest 用 `create_all` 每次重建，无碍）

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/notes.py backend/tests/test_notes_api.py
git commit -m "feat(notes): 新增 PUT /notes/{id} 编辑接口"
```

---

## Task 5: 前端 API + NoteCard 移除警示、标签改名

**Files:**
- Modify: `web/src/api/notes.ts`
- Modify: `web/src/components/notes/NoteCard.tsx`
- Test: `npm run build`

- [ ] **Step 1: 更新 `web/src/api/notes.ts`**

1. `NoteDetailResponse` 删除 `warning: string`（第 28 行）
2. 追加：

```typescript
export interface UpdateNoteRequest {
  rule_title: string
  knowledge_point: string
  alternatives: string[]
  feynman_question: string
}

export async function updateNote(
  noteId: string,
  payload: UpdateNoteRequest,
): Promise<NoteDetailResponse> {
  return http.put<NoteDetailResponse>(`/notes/${noteId}`, payload)
}
```

> 确认 `web/src/api/client.ts` 的 `http` 对象有 `put` 方法。若无，先查看 client.ts 现有方法（get/post/delete），补一个 `put<T>(url, body)`。

- [ ] **Step 2: 更新 `web/src/components/notes/NoteCard.tsx` 普通态**

删除「⚠️ 个人易错警示」区块（第 86-89 行），「职场同义备选」标签改为「同义备选」（第 93 行）。展开内容保留核心知识点/同义备选/费曼自测/我的错误。此时 `detail.warning` 引用删除，`detail.alternatives` 区块保留。

- [ ] **Step 3: 构建验证**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run build`
Expected: 通过（`warning` 引用清除后无 TS 错误）

- [ ] **Step 4: 提交**

```bash
git add web/src/api/notes.ts web/src/components/notes/NoteCard.tsx
git commit -m "refactor(notes): 前端移除个人易错警示，职场同义备选改名同义备选"
```

---

## Task 6: 前端 NoteCard 编辑态

**Files:**
- Modify: `web/src/components/notes/NoteCard.tsx`
- Test: `npm run build`

- [ ] **Step 1: 重写 `web/src/components/notes/NoteCard.tsx` 加入编辑态**

在现有 `NoteCard.tsx` 基础上改造。新增状态：`editing`、`editTitle`、`editKnowledgePoint`、`editAlternatives`、`editFeynman`、`saveError`、`saving`、`toast`。

核心逻辑：
- 普通态：顶部标题 `note.rule_title`，展开时显示 3 规则字段 + 案例；底部（展开后）有「删除该笔记」与「✏️ 编辑此笔记」按钮
- `handleEditStart`：用当前 `detail` 填充编辑状态，`setEditing(true)`
- 编辑态渲染：卡片临时增宽（编辑时容器宽度改为 `md:w-full` 类或外层加宽），4 项输入（标题 input、知识点 textarea、备选行 + ✕ + 添加、费曼 textarea），校验空值（红框 + 提示）
- `handleSave`：校验 → `updateNote()` → 更新 `detail`/`note` → toast → 退出编辑
- 需要把更新后的 `rule_title` 同步回父列表（`onNoteUpdated` 回调 或 局部刷新）

**关键：标题更新需要同步父组件**。`NoteCard` 的 `note` 来自 `NotesPage` 的列表 state。新增 prop `onNoteUpdated: (updated: NoteDetailResponse) => void`，`NotesPage` 用它更新对应列表项（重新 fetchNotes 或局部替换）。

由于 NoteCard 完整代码较长（含删除确认/案例删除等既有逻辑），此处给出**编辑态关键改动增量**，由实现者整合进现有文件（保留全部既有行为）：

```tsx
// 新增 imports
import { updateNote } from '@/api/notes'

// Props 新增
interface Props {
  note: NoteListItem
  onNoteDeleted: (noteId: string) => void
  onNoteUpdated: (updated: NoteDetailResponse) => void
}

// 新增 state（在现有 state 之后）
const [editing, setEditing] = useState(false)
const [editTitle, setEditTitle] = useState('')
const [editKnowledgePoint, setEditKnowledgePoint] = useState('')
const [editAlternatives, setEditAlternatives] = useState<string[]>([])
const [editFeynman, setEditFeynman] = useState('')
const [editingErrors, setEditingErrors] = useState<string[]>([])
const [saving, setSaving] = useState(false)
const [toast, setToast] = useState<string | null>(null)

function showToast(msg: string) {
  setToast(msg)
  setTimeout(() => setToast(null), 2000)
}

function handleEditStart() {
  if (!detail) return
  setEditTitle(detail.rule_title)
  setEditKnowledgePoint(detail.knowledge_point)
  setEditAlternatives([...detail.alternatives])
  setEditFeynman(detail.feynman_question)
  setEditingErrors([])
  setEditing(true)
}

function handleEditCancel() {
  setEditing(false)
  setEditingErrors([])
}

function validateEdit(): string[] {
  const errors: string[] = []
  if (!editTitle.trim()) errors.push('规则标题不能为空')
  if (!editKnowledgePoint.trim()) errors.push('核心知识点不能为空')
  if (!editFeynman.trim()) errors.push('费曼自测不能为空')
  return errors
}

async function handleSave() {
  const errors = validateEdit()
  if (errors.length > 0) {
    setEditingErrors(errors)
    return
  }
  setSaving(true)
  try {
    const updated = await updateNote(note.id, {
      rule_title: editTitle.trim(),
      knowledge_point: editKnowledgePoint.trim(),
      alternatives: editAlternatives.filter((a) => a.trim() !== ''),
      feynman_question: editFeynman.trim(),
    })
    setDetail(updated)
    onNoteUpdated(updated)
    setEditing(false)
    setEditingErrors([])
    showToast('✓ 笔记已保存')
  } catch {
    showToast('保存失败，请重试')
  } finally {
    setSaving(false)
  }
}

function handleAltChange(i: number, value: string) {
  setEditAlternatives((prev) => prev.map((a, idx) => (idx === i ? value : a)))
}

function handleAltRemove(i: number) {
  setEditAlternatives((prev) => prev.filter((_, idx) => idx !== i))
}

function handleAltAdd() {
  setEditAlternatives((prev) => [...prev, ''])
}
```

编辑态 JSX（放在 expanded 内容顶部，当 `editing` 时替换普通字段展示区渲染，并保留底部「取消/保存」替换「删除该笔记」区）：

```tsx
{editing && detail ? (
  <div className="space-y-2 rounded-xl border border-[#0ca678] bg-white p-4">
    <div className="flex items-center justify-between">
      <p className="text-sm font-semibold text-[#343a40]">✏️ 编辑笔记</p>
      <span className="rounded-full bg-[#e6fcf5] px-2 py-0.5 text-xs text-[#0ca678]">编辑中</span>
    </div>

    <div>
      <p className="mb-1 text-sm font-semibold text-[#343a40]">🏷 规则标题</p>
      <input
        value={editTitle}
        onChange={(e) => setEditTitle(e.target.value)}
        className="w-full rounded-lg border border-[#ced4da] px-3 py-2 text-sm focus:border-[#0ca678] focus:outline-none"
      />
    </div>

    <div>
      <p className="mb-1 text-sm font-semibold text-[#343a40]">📌 核心知识点</p>
      <textarea
        value={editKnowledgePoint}
        onChange={(e) => setEditKnowledgePoint(e.target.value)}
        className="w-full min-h-24 rounded-lg border border-[#ced4da] px-3 py-2 text-sm focus:border-[#0ca678] focus:outline-none"
      />
    </div>

    <div>
      <p className="mb-1 text-sm font-semibold text-[#343a40]">💼 同义备选</p>
      <div className="space-y-1.5">
        {editAlternatives.map((alt, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              value={alt}
              onChange={(e) => handleAltChange(i, e.target.value)}
              className="flex-1 rounded-lg border border-[#ced4da] px-3 py-1.5 text-sm focus:border-[#0ca678] focus:outline-none"
            />
            <Button variant="ghost" size="xs" onClick={() => handleAltRemove(i)} className="text-[#fa5252]">
              ✕
            </Button>
          </div>
        ))}
      </div>
      <Button variant="ghost" size="xs" onClick={handleAltAdd} className="mt-1 border border-dashed border-[#0ca678] text-[#0ca678]">
        ＋ 添加一条
      </Button>
    </div>

    <div>
      <p className="mb-1 text-sm font-semibold text-[#343a40]">❓ 费曼自测</p>
      <textarea
        value={editFeynman}
        onChange={(e) => setEditFeynman(e.target.value)}
        className="w-full min-h-20 rounded-lg border border-[#ced4da] px-3 py-2 text-sm focus:border-[#0ca678] focus:outline-none"
      />
    </div>

    {editingErrors.length > 0 && (
      <div className="rounded-lg border border-[#fa5252] bg-[#fff5f5] px-3 py-2 text-xs text-[#c92a2a]">
        {editingErrors.map((err) => (
          <p key={err}>{err}</p>
        ))}
      </div>
    )}

    <div className="flex items-center justify-between pt-1">
      <p className="text-xs text-[#868e96]">修改仅作用于这条规则，不会改动纠错记录</p>
      <div className="flex gap-2">
        <Button variant="ghost" size="xs" onClick={handleEditCancel}>
          取消
        </Button>
        <Button size="xs" disabled={saving} onClick={handleSave} className="bg-[#0ca678] text-white">
          {saving ? '保存中…' : '保存'}
        </Button>
      </div>
    </div>
  </div>
) : null}
```

普通态展开渲染的「删除该笔记」区域保留（但编辑态时不显示删除区，两者互斥——通过 `!editing` 包裹现有删除区）。展开区顶部加「✏️ 编辑此笔记」按钮（仅 `!editing && detail` 时）。

「编辑此笔记」按钮（放在普通态展开区底部、删除按钮旁）：

```tsx
<Button variant="ghost" size="xs" onClick={handleEditStart} className="text-[#0ca678]">
  ✏️ 编辑此笔记
</Button>
```

toast（放在卡片最外层底部）：

```tsx
{toast && (
  <div className="fixed right-4 top-4 z-50 rounded-lg bg-[#0ca678] px-4 py-2 text-sm text-white shadow-lg">
    {toast}
  </div>
)}
```

- [ ] **Step 2: 更新 `web/src/pages/NotesPage.tsx` 传 `onNoteUpdated`**

在 `<NoteCard>` 调用处新增：

```tsx
onNoteUpdated={handleNoteUpdated}
```

并新增处理函数：

```tsx
function handleNoteUpdated(updated: NoteDetailResponse) {
  setNotes((prev) =>
    prev.map((n) =>
      n.id === updated.id
        ? { ...n, rule_title: updated.rule_title, knowledge_point: updated.knowledge_point }
        : n,
    ),
  )
}
```

注意 `NoteDetailResponse` 需 import。

- [ ] **Step 3: 确认 `http.put` 存在**

Run: `cd web && grep -n "put\|export const http" src/api/client.ts`
若无 `put`，添加：

```typescript
put<T>(url: string, body?: unknown): Promise<T> {
  return http<T>('PUT', url, body)
}
```
（先读 client.ts 确认 `http` 的签名再适配）

- [ ] **Step 4: 构建验证**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run build`
Expected: 通过

- [ ] **Step 5: Lint**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run lint`
Expected: 无错误

- [ ] **Step 6: 提交**

```bash
git add web/src/components/notes/NoteCard.tsx web/src/pages/NotesPage.tsx web/src/api/client.ts web/src/api/notes.ts
git commit -m "feat(notes): 笔记内联编辑（标题/知识点/同义备选/费曼）"
```

---

## Task 7: E2E 更新

**Files:**
- Modify: `web/tests/e2e/notes.spec.ts`
- Test: `npx playwright test tests/e2e/notes.spec.ts`

- [ ] **Step 1: 更新 N-03 断言**

`web/tests/e2e/notes.spec.ts` 第 74 行删除 `await expect(page.getByText('⚠️ 个人易错警示')).toBeVisible()`；第 75 行「职场同义备选」改为「同义备选」：

```ts
test('N-03 笔记展开显示字段', async ({ page }) => {
  await loginAndSubmit(page)
  await waitUntilNotePersisted(page)
  await page.getByRole('button', { name: /介词后加 -ing 形式/ }).click()
  await expect(page.getByText('📌 核心知识点')).toBeVisible()
  await expect(page.getByText(/介词后接动词/).first()).toBeVisible()
  await expect(page.getByText('💼 同义备选')).toBeVisible()
  await expect(page.getByText('❓ 费曼自测')).toBeVisible()
  await expect(page.getByText('📝 我的错误')).toBeVisible()
  await expect(page.getByText(/interested in read → interested in reading/)).toBeVisible()
})
```

- [ ] **Step 2: 新增编辑保存用例（追加到文件末尾）**

```ts
test('N-07 编辑笔记保存后显示新值', async ({ page }) => {
  await loginAndSubmit(page)
  await waitUntilNotePersisted(page)
  await page.getByRole('button', { name: /介词后加 -ing 形式/ }).click()
  await page.getByRole('button', { name: '✏️ 编辑此笔记' }).click()
  await expect(page.getByText('✏️ 编辑笔记')).toBeVisible()
  // 修改标题与知识点
  await page.getByText('规则标题').locator('..').locator('input').fill('编辑后的规则标题')
  await expect(page.getByText('✏️ 编辑笔记')).toBeVisible()
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText('✓ 笔记已保存')).toBeVisible({ timeout: 10000 })
  await expect(page.getByText('编辑后的规则标题')).toBeVisible()
})
```

> 若「编辑此笔记」按钮的 name 定位困难，可用 `page.getByText('编辑此笔记')`。具体选择器实现时按实际 DOM 调整。测试目标是：进入编辑 → 修改标题 → 保存 → toast 出现 + 新标题展示。

- [ ] **Step 3: 运行 E2E**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npx playwright test tests/e2e/notes.spec.ts`
Expected: 全部通过

> 若 N-07 因选择器不稳失败，调整选择器（如 `.fill` 目标改为定位具体 input）。后台 mock 笔记的 rule_title 是「介词后加 -ing 形式」。

- [ ] **Step 4: 运行全量 E2E**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run test:e2e`
Expected: 全部通过（login + correction + notes）

- [ ] **Step 5: 提交**

```bash
git add web/tests/e2e/notes.spec.ts
git commit -m "test(e2e): 移除个人易错警示断言，新增笔记编辑保存用例"
```

---

## Task 8: 本地开发库重建 DB

**Files:**
- 无

- [ ] **Step 1: 重建本地开发数据库 `echo`**

开发库有旧 `warning` 列（无迁移文件删除）。用 psql 删除并让应用重建，或 drop 相关表后重新跑 alembic upgrade head：

```bash
docker compose exec db psql -U echo -d echo -c "DROP TABLE IF EXISTS note_cases, notes CASCADE"
```

- [ ] **Step 2: 确认 app 启动正常（真实 LLM 环境或 mock 均可）**

启动 uvicorn 确认无模型列不匹配错误。若仍有 `warning` 列引用（SQLAlchemy 查询旧库），说明表未重建成功，重复 Step 1。

- [ ] **Step 3: 提交（若无文件改动则跳过）**

---

## 自审检查

- **Spec 覆盖**：移除 warning（Task 1 模型/schema/prompt/mock + Task 2 service + Task 5 前端 + Task 7 E2E）✓ · 编辑功能 `PUT` 接口（Task 2 service + Task 3 schema + Task 4 路由）✓ · 前端内联编辑（Task 6）✓ · 标签改名职场→同义备选（Task 5/6/7）✓ · 不写迁移重建 DB（Task 8）✓ · 校验非空 + alternatives 可空（Task 3 schema + Task 4 400 测试 + Task 6 前端校验）✓
- **Placeholder 扫描**：无 TBD；Task 6 编辑态 JSX 以增量代码 + 说明给出（因 NoteCard 含既有删除/案例逻辑较长，按增量整合合理，但代码完整无省略）。
- **Type consistency**：`UpdateNoteRequest`（rule_title/knowledge_point/alternatives/feynman_question）在 Task 3 schema、Task 4 路由、Task 5 前端类型一致。`update_note(session, user_id, note_id, payload) -> NoteDetailResponse | None` 在 Task 2 service 与 Task 4 路由调用一致。`onNoteUpdated(updated: NoteDetailResponse)` 在 Task 6 NoteCard/NotesPage 一致。`detail.warning` 全链路删除一致。
