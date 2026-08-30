# 记笔记功能实现计划（notes-feature）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现记笔记功能——用户从纠错结果保存「学到的规则」为规则笔记（以规则为主体、累积多个错误案例），新增左侧 sidebar 导航 + 笔记列表页，为后续复习功能（F-03）提供数据基础。

**Architecture:** 后端新增 `notes`（全局规则库）+ `note_cases`（用户案例）双表；保存时单次 LLM 调用同时完成去重匹配 + 规则生成（复用现有 `LLMClient`）；前端新增 `AppLayout`（左侧 sidebar + 右上角退出）包裹纠错/笔记页，`ErrorCard` 加「记笔记」按钮，`CorrectionReportCard` 加「全部记笔记」按钮，新增 `/notes` 笔记列表页。

**Tech Stack:** 后端 FastAPI + SQLAlchemy(async) + Pydantic + Alembic；前端 React 19 + React Router 7 + TailwindCSS + shadcn/ui

**依赖文档:** `docs/superpowers/specs/2026-08-29-notes-feature-design.md`

---

### Task 1: Note / NoteCase 数据模型

**Files:**
- Create: `backend/app/models/note.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models_note.py`

- [ ] **Step 1: 编写失败的模型测试**

Create `backend/tests/test_models_note.py`:

```python
import uuid

import pytest
from sqlalchemy import select

from app.db import async_session_factory, Base
from app.models.note import Note, NoteCase
from app.models.user import User


async def _demo_user_id() -> uuid.UUID:
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        return user.id


async def test_create_note_and_case():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(rule_title="介词后加 -ing 形式", description="介词后接动词用动名词形式")
        s.add(note)
        await s.flush()
        case = NoteCase(
            note_id=note.id,
            user_id=uid,
            example="interested in read → interested in reading",
            source_text="I interested in read",
        )
        s.add(case)
        await s.commit()
        assert note.id is not None
        assert case.id is not None
        assert note.created_at is not None
        assert note.updated_at is not None


async def test_note_case_cascade_delete_note():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(rule_title="to 不定式接原形", description="to 作不定式时后接动词原形")
        s.add(note)
        await s.flush()
        case_id = uuid.uuid4()
        s.add(NoteCase(
            id=case_id,
            note_id=note.id,
            user_id=uid,
            example="to began → to begin",
            source_text="I want to began",
        ))
        await s.commit()
        await s.delete(note)
        await s.commit()
    async with async_session_factory() as s:
        assert (await s.get(NoteCase, case_id)) is None


async def test_delete_message_keeps_case():
    """source_message_id 用 SET NULL：删消息不删案例"""
    from app.models.conversation import SessionConversation
    from app.models.message import Message, MessageRole, MessageType

    uid = await _demo_user_id()
    async with async_session_factory() as s:
        conv = SessionConversation(user_id=uid)
        s.add(conv)
        await s.flush()
        msg = Message(
            conversation_id=conv.id,
            role=MessageRole.user,
            type=MessageType.correction,
            content="test",
        )
        s.add(msg)
        await s.flush()
        note = Note(rule_title="测试规则", description="测试")
        s.add(note)
        await s.flush()
        case = NoteCase(
            note_id=note.id,
            user_id=uid,
            example="wrong → right",
            source_text="test",
            source_message_id=msg.id,
        )
        s.add(case)
        await s.commit()
        case_id = case.id
        await s.delete(msg)
        await s.commit()
    async with async_session_factory() as s:
        refreshed = await s.get(NoteCase, case_id)
        assert refreshed is not None
        assert refreshed.source_message_id is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_models_note.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.note'`

- [ ] **Step 3: 实现 Note / NoteCase 模型**

Create `backend/app/models/note.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NoteCase(Base):
    __tablename__ = "note_cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notes.id", name="fk_note_cases_note_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", name="fk_note_cases_user_id", ondelete="CASCADE"), nullable=False
    )
    example: Mapped[str] = mapped_column(Text, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", name="fk_note_cases_message_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 4: 注册模型到 `__init__.py`**

Modify `backend/app/models/__init__.py` to:

```python
from app.models.user import User
from app.models.session import AuthSession
from app.models.conversation import SessionConversation
from app.models.message import Message
from app.models.report import CorrectionReport
from app.models.note import Note, NoteCase

__all__ = ["User", "AuthSession", "SessionConversation", "Message", "CorrectionReport", "Note", "NoteCase"]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_models_note.py -v`
Expected: 3 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/note.py backend/app/models/__init__.py backend/tests/test_models_note.py
git commit -m "feat(notes): 新增 Note/NoteCase 数据模型"
```

---

### Task 2: Alembic 迁移 + conftest 清理扩展

**Files:**
- Create: `backend/alembic/versions/<hash>_add_notes_and_note_cases.py`（自动生成）
- Modify: `backend/tests/conftest.py:15-24,60-65`

- [ ] **Step 1: 生成迁移文件**

Run: `cd backend && source .venv/bin/activate && alembic revision --autogenerate -m "add notes and note_cases tables"`

- [ ] **Step 2: 检查生成的迁移文件**

打开新生成的迁移文件，确认 `upgrade()` 包含 `op.create_table('notes', ...)` 和 `op.create_table('note_cases', ...)`，字段与模型一致（含外键约束、`ondelete='CASCADE'`/`SET NULL`、`server_default=sa.text('now()')`）。确认 `downgrade()` 包含 `op.drop_table('note_cases')` 和 `op.drop_table('notes')`（先删 note_cases 再删 notes，符合外键依赖顺序）。

- [ ] **Step 3: 应用迁移验证**

Run: `cd backend && source .venv/bin/activate && alembic upgrade head`
Expected: 无错误

- [ ] **Step 4: 扩展 conftest 清理逻辑**

Modify `backend/tests/conftest.py` 的 `drop_all_tables` 函数，在 `messages` 之前加入 `note_cases` 和 `notes`：

```python
async def drop_all_tables():
    async with engine.begin() as conn:
        for name in (
            "note_cases",
            "notes",
            "messages",
            "correction_reports",
            "session_conversations",
            "sessions",
            "users",
        ):
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
```

Modify `backend/tests/conftest.py` 的 `clean_sessions` fixture，扩展 truncate：

```python
@pytest_asyncio.fixture(autouse=True)
async def clean_sessions():
    async with async_session_factory() as session:
        await session.execute(text("TRUNCATE note_cases, notes, sessions, messages, correction_reports, session_conversations"))
        await session.commit()
    yield
```

- [ ] **Step 5: 运行全量后端测试确认无回归**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: 全部 PASS（含新增的 test_models_note.py + 现有测试）

- [ ] **Step 6: 提交**

```bash
git add backend/alembic/versions/ backend/tests/conftest.py
git commit -m "feat(notes): 新增 notes/note_cases 迁移 + conftest 清理扩展"
```

---

### Task 3: 保存时 LLM Prompt + Pydantic Schema

**Files:**
- Create: `backend/app/prompts/note_prompt.py`
- Create: `backend/app/schemas/note.py`
- Test: `backend/tests/test_note_prompt.py`

- [ ] **Step 1: 编写失败的 prompt 测试**

Create `backend/tests/test_note_prompt.py`:

```python
from app.prompts.note_prompt import build_note_system_prompt, build_note_user_content


def test_system_prompt_contains_granularity_rules():
    prompt = build_note_system_prompt(existing_rules=[])
    assert "可单独测试的规则点" in prompt
    assert "介词后加 -ing 形式" in prompt
    assert "过去时" in prompt  # 反例
    assert "原样返回" in prompt  # 去重指令


def test_system_prompt_includes_existing_rules():
    prompt = build_note_system_prompt(existing_rules=["介词后加 -ing 形式", "to 不定式接原形"])
    assert "介词后加 -ing 形式" in prompt
    assert "to 不定式接原形" in prompt


def test_user_content_contains_source_and_errors():
    content = build_note_user_content(
        source_text="I interested in read",
        errors=[{"error_type": "动词形式", "fragment": "interested in read", "explanation": "介词后加 ing", "correction": "interested in reading"}],
    )
    assert "I interested in read" in content
    assert "interested in read" in content
    assert "interested in reading" in content
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_note_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.prompts.note_prompt'`

- [ ] **Step 3: 实现 note_prompt.py**

Create `backend/app/prompts/note_prompt.py`:

```python
"""保存笔记时 LLM 提示词：从错误生成/匹配规则笔记。"""


def build_note_system_prompt(existing_rules: list[str]) -> str:
    rules_list = "\n".join(f"- {r}" for r in existing_rules) if existing_rules else "（暂无已有规则）"
    return f"""你是英语语法规则归纳助手。根据用户提交的英文原文和错误列表，归纳出对应的语法规则笔记。

## 已有规则库
以下是系统中已存在的规则，新错误若属于其中某条，必须原样返回那条的 rule_title：
{rules_list}

## 输出格式
输出 JSON 对象，含 results 数组，每个元素对应一条规则（同类错误合并为一条）：
```json
{{
  "results": [
    {{
      "rule_title": "介词后加 -ing 形式",
      "description": "英语中介词后接动词时需用动名词形式(-ing)而非不定式...",
      "example": "interested in read → interested in reading"
    }}
  ]
}}
```

## rule_title 粒度要求
- 标题描述一个【可单独测试的规则点】，不是语法范畴
- ✅ 好："介词后加 -ing 形式"、"to 不定式接动词原形"、"可数名词单数需加冠词"
- ❌ 坏："过去时"、"冠词"、"时态"、"介词"（太宽泛，含多个不相关练习点）
- ❌ 坏："in 后加 ing"（太碎片，应泛化到所有介词）

## 合并指令
同类错误合并为一条 result（如 2 个时态错误 → 1 条规则）

## 去重指令
若新错误的规则与已有规则库中某条语义相同，必须原样返回那条的 rule_title（不得修改、不得编造）。description 字段始终生成（匹配已有规则时后端会忽略，仅用于新建规则）。

## example 格式
「错误写法 → 正确写法」，从本次 errors 中提炼

## description 要求
包含规则说明、构成方式、常见情况、边界/例外情况，一段完整讲解
"""


def build_note_user_content(source_text: str, errors: list[dict]) -> str:
    import json

    return f"""## 原文
{source_text}

## 错误列表
{json.dumps(errors, ensure_ascii=False, indent=2)}
"""
```

- [ ] **Step 4: 实现 schemas/note.py**

Create `backend/app/schemas/note.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ErrorBlockInput(BaseModel):
    error_type: str
    fragment: str
    explanation: str
    correction: str


class SaveNoteRequest(BaseModel):
    message_id: uuid.UUID
    source_text: str = Field(min_length=1, max_length=2000)
    errors: list[ErrorBlockInput] = Field(min_length=1)


class NoteRuleResult(BaseModel):
    rule_title: str
    description: str
    example: str


class NoteLLMResponse(BaseModel):
    results: list[NoteRuleResult]


class SavedNoteItem(BaseModel):
    note_id: uuid.UUID
    rule_title: str
    is_new: bool
    case_id: uuid.UUID


class SaveNoteResponse(BaseModel):
    saved_notes: list[SavedNoteItem]


class NoteListItem(BaseModel):
    id: uuid.UUID
    rule_title: str
    description: str
    case_count: int
    updated_at: datetime


class NoteListResponse(BaseModel):
    notes: list[NoteListItem]


class NoteCaseItem(BaseModel):
    id: uuid.UUID
    example: str
    source_text: str
    created_at: datetime


class NoteDetailResponse(BaseModel):
    id: uuid.UUID
    rule_title: str
    description: str
    cases: list[NoteCaseItem]
```

- [ ] **Step 5: 运行 prompt 测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_note_prompt.py -v`
Expected: 3 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/prompts/note_prompt.py backend/app/schemas/note.py backend/tests/test_note_prompt.py
git commit -m "feat(notes): 保存时 LLM prompt + Pydantic schema"
```

---

### Task 4: note_service 保存逻辑（LLM 调用 + 去重 + 新建/追加）

**Files:**
- Create: `backend/app/services/note_service.py`
- Test: `backend/tests/test_note_service.py`

- [ ] **Step 1: 编写失败的 service 测试**

Create `backend/tests/test_note_service.py`:

```python
import json
import uuid

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.db import async_session_factory
from app.models.note import Note, NoteCase
from app.models.user import User
from app.services.llm_client import LLMTimeoutError, LLMUnavailableError, MockLLMClient
from app.services.note_service import save_notes


async def _demo_user_id() -> uuid.UUID:
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        return user.id


def _mock_responder_new_rule(msgs):
    return json.dumps({
        "results": [{
            "rule_title": "介词后加 -ing 形式",
            "description": "介词后接动词用动名词形式",
            "example": "interested in read → interested in reading",
        }]
    }, ensure_ascii=False)


async def test_save_new_rule_creates_note_and_case():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        result = await save_notes(
            s, uid, None, "I interested in read",
            [{"error_type": "动词形式", "fragment": "interested in read",
              "explanation": "介词后加 ing", "correction": "interested in reading"}],
            mock,
        )
        assert len(result) == 1
        assert result[0].is_new is True
        assert result[0].rule_title == "介词后加 -ing 形式"


def _mock_responder_existing_rule(msgs):
    return json.dumps({
        "results": [{
            "rule_title": "介词后加 -ing 形式",
            "description": "（后端忽略，已有规则）",
            "example": "good at swim → good at swimming",
        }]
    }, ensure_ascii=False)


async def test_save_existing_rule_appends_case():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(
            s, uid, None, "I interested in read",
            [{"error_type": "动词形式", "fragment": "interested in read",
              "explanation": "x", "correction": "interested in reading"}],
            mock,
        )

    async with async_session_factory() as s:
        mock2 = MockLLMClient(responder=_mock_responder_existing_rule)
        result = await save_notes(
            s, uid, None, "She is good at swim",
            [{"error_type": "动词形式", "fragment": "good at swim",
              "explanation": "x", "correction": "good at swimming"}],
            mock2,
        )
        assert len(result) == 1
        assert result[0].is_new is False

    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "介词后加 -ing 形式"))).scalar_one()
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 2


def _mock_responder_two_rules(msgs):
    return json.dumps({
        "results": [
            {"rule_title": "介词后加 -ing 形式", "description": "d1", "example": "e1 → e2"},
            {"rule_title": "to 不定式接原形", "description": "d2", "example": "e3 → e4"},
        ]
    }, ensure_ascii=False)


async def test_save_batch_creates_multiple_rules():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_two_rules)
        result = await save_notes(
            s, uid, None, "source text",
            [
                {"error_type": "动词形式", "fragment": "f1", "explanation": "x", "correction": "c1"},
                {"error_type": "动词形式", "fragment": "f2", "explanation": "x", "correction": "c2"},
            ],
            mock,
        )
        assert len(result) == 2
        assert all(r.is_new for r in result)


class _RaisingLLMClient:
    def __init__(self, exc):
        self._exc = exc

    async def complete(self, messages):
        raise self._exc


async def test_save_timeout_raises_504():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = _RaisingLLMClient(LLMTimeoutError())
        with pytest.raises(AppError) as exc_info:
            await save_notes(s, uid, None, "x", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 504


async def test_save_llm_unavailable_raises_503():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = _RaisingLLMClient(LLMUnavailableError())
        with pytest.raises(AppError) as exc_info:
            await save_notes(s, uid, None, "x", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 503


def _mock_responder_invalid(msgs):
    return "not-json"


async def test_save_invalid_llm_response_raises_502():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_invalid)
        with pytest.raises(AppError) as exc_info:
            await save_notes(s, uid, None, "x", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 502
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_note_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.note_service'`

- [ ] **Step 3: 实现 note_service.py 的 save_notes**

Create `backend/app/services/note_service.py`:

```python
import json
import uuid

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.note import Note, NoteCase
from app.prompts.note_prompt import build_note_system_prompt, build_note_user_content
from app.schemas.note import NoteLLMResponse, NoteListItem, NoteCaseItem, NoteDetailResponse, SavedNoteItem
from app.services.llm_client import LLMClient, LLMTimeoutError, LLMUnavailableError


async def _get_existing_rule_titles(session: AsyncSession) -> list[str]:
    rows = (await session.execute(select(Note.rule_title))).scalars().all()
    return list(rows)


async def _call_llm_and_parse(
    llm_client: LLMClient, existing_rules: list[str], source_text: str, errors: list[dict]
) -> NoteLLMResponse:
    messages = [
        {"role": "system", "content": build_note_system_prompt(existing_rules)},
        {"role": "user", "content": build_note_user_content(source_text, errors)},
    ]
    for attempt in range(2):
        try:
            raw = await llm_client.complete(messages)
        except LLMTimeoutError:
            raise AppError(504, "LLM_TIMEOUT", "AI 响应超时，请重试")
        except LLMUnavailableError:
            raise AppError(503, "LLM_SERVICE_UNAVAILABLE", "AI 服务不可用，请稍后重试")
        try:
            return NoteLLMResponse.model_validate_json(raw)
        except ValidationError:
            pass
        if attempt == 0:
            continue
        raise AppError(502, "LLM_RESPONSE_INVALID", "AI 返回内容无效，请重试")
    raise AssertionError("unreachable")


async def save_notes(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_message_id: uuid.UUID | None,
    source_text: str,
    errors: list[dict],
    llm_client: LLMClient,
) -> list[SavedNoteItem]:
    existing_rules = await _get_existing_rule_titles(session)
    parsed = await _call_llm_and_parse(llm_client, existing_rules, source_text, errors)

    saved: list[SavedNoteItem] = []
    for result in parsed.results:
        note = (
            await session.execute(select(Note).where(Note.rule_title == result.rule_title))
        ).scalar_one_or_none()
        if note is not None:
            case = NoteCase(
                note_id=note.id,
                user_id=user_id,
                example=result.example,
                source_text=source_text,
                source_message_id=source_message_id,
            )
            session.add(case)
            await session.flush()
            saved.append(SavedNoteItem(note_id=note.id, rule_title=note.rule_title, is_new=False, case_id=case.id))
        else:
            note = Note(rule_title=result.rule_title, description=result.description)
            session.add(note)
            await session.flush()
            case = NoteCase(
                note_id=note.id,
                user_id=user_id,
                example=result.example,
                source_text=source_text,
                source_message_id=source_message_id,
            )
            session.add(case)
            await session.flush()
            saved.append(SavedNoteItem(note_id=note.id, rule_title=note.rule_title, is_new=True, case_id=case.id))

    await session.commit()
    return saved
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_note_service.py -v`
Expected: 6 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/note_service.py backend/tests/test_note_service.py
git commit -m "feat(notes): save_notes 保存逻辑（LLM 去重 + 新建/追加案例）"
```

---

### Task 5: note_service 查询/删除逻辑

**Files:**
- Modify: `backend/app/services/note_service.py`（追加函数）
- Modify: `backend/tests/test_note_service.py`（追加测试）

- [ ] **Step 1: 编写失败的查询/删除测试**

Append to `backend/tests/test_note_service.py`:

```python
from app.services.note_service import list_notes, get_note_detail, delete_note, delete_case


async def test_list_notes_returns_user_notes_with_count():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_two_rules)
        await save_notes(s, uid, None, "src", [
            {"error_type": "t", "fragment": "f1", "explanation": "e", "correction": "c"},
            {"error_type": "t", "fragment": "f2", "explanation": "e", "correction": "c"},
        ], mock)
    async with async_session_factory() as s:
        notes = await list_notes(s, uid)
        assert len(notes) == 2
        assert all(n.case_count == 1 for n in notes)


async def test_list_notes_isolates_by_user():
    from app.core.security import hash_password
    from app.models.user import UserStatus

    async with async_session_factory() as s:
        s.add(User(username="alice2", password_hash=hash_password("a1234"), status=UserStatus.active))
        await s.commit()
        alice = (await s.execute(select(User).where(User.username == "alice2"))).scalar_one()
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "src", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
    async with async_session_factory() as s:
        alice_notes = await list_notes(s, alice.id)
        assert alice_notes == []


async def test_get_note_detail_includes_cases():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "I interested in read", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
    async with async_session_factory() as s:
        notes = await list_notes(s, uid)
        detail = await get_note_detail(s, uid, notes[0].id)
        assert detail.rule_title == "介词后加 -ing 形式"
        assert len(detail.cases) == 1
        assert detail.cases[0].source_text == "I interested in read"


async def test_get_note_detail_other_user_returns_none():
    from app.core.security import hash_password
    from app.models.user import UserStatus

    async with async_session_factory() as s:
        s.add(User(username="bob2", password_hash=hash_password("b1234"), status=UserStatus.active))
        await s.commit()
        bob = (await s.execute(select(User).where(User.username == "bob2"))).scalar_one()
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "src", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        notes = await list_notes(s, uid)
        note_id = notes[0].id
    async with async_session_factory() as s:
        detail = await get_note_detail(s, bob.id, note_id)
        assert detail is None


async def test_delete_note_removes_user_cases_keeps_global():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "src", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        notes = await list_notes(s, uid)
        note_id = notes[0].id
    async with async_session_factory() as s:
        await delete_note(s, uid, note_id)
    async with async_session_factory() as s:
        assert await s.get(Note, note_id) is not None  # 全局规则保留
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note_id))).scalars().all()
        assert all(c.user_id != uid for c in cases)


async def test_delete_case_removes_single_case():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "first", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
    async with async_session_factory() as s:
        mock2 = MockLLMClient(responder=_mock_responder_existing_rule)
        await save_notes(s, uid, None, "second", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock2)
    async with async_session_factory() as s:
        notes = await list_notes(s, uid)
        detail = await get_note_detail(s, uid, notes[0].id)
        case_id = detail.cases[0].id
        await delete_case(s, uid, case_id)
    async with async_session_factory() as s:
        notes = await list_notes(s, uid)
        assert notes[0].case_count == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_note_service.py -v`
Expected: 新增的 6 个测试 FAIL（`ImportError` 或函数不存在）

- [ ] **Step 3: 追加查询/删除函数到 note_service.py**

在 `backend/app/services/note_service.py` 文件末尾追加：

```python
async def list_notes(session: AsyncSession, user_id: uuid.UUID) -> list[NoteListItem]:
    rows = (
        await session.execute(
            select(
                Note.id,
                Note.rule_title,
                Note.description,
                func.count(NoteCase.id).label("case_count"),
                Note.updated_at,
            )
            .join(NoteCase, NoteCase.note_id == Note.id)
            .where(NoteCase.user_id == user_id)
            .group_by(Note.id)
            .order_by(Note.updated_at.desc())
        )
    ).all()
    return [
        NoteListItem(
            id=r.id, rule_title=r.rule_title, description=r.description,
            case_count=r.case_count, updated_at=r.updated_at,
        )
        for r in rows
    ]


async def get_note_detail(
    session: AsyncSession, user_id: uuid.UUID, note_id: uuid.UUID
) -> NoteDetailResponse | None:
    note = await session.get(Note, note_id)
    if note is None:
        return None
    cases = (
        await session.execute(
            select(NoteCase)
            .where(NoteCase.note_id == note_id, NoteCase.user_id == user_id)
            .order_by(NoteCase.created_at)
        )
    ).scalars().all()
    if not cases:
        return None
    return NoteDetailResponse(
        id=note.id,
        rule_title=note.rule_title,
        description=note.description,
        cases=[
            NoteCaseItem(id=c.id, example=c.example, source_text=c.source_text, created_at=c.created_at)
            for c in cases
        ],
    )


async def delete_note(session: AsyncSession, user_id: uuid.UUID, note_id: uuid.UUID) -> None:
    cases = (
        await session.execute(
            select(NoteCase).where(NoteCase.note_id == note_id, NoteCase.user_id == user_id)
        )
    ).scalars().all()
    for c in cases:
        await session.delete(c)
    await session.commit()


async def delete_case(session: AsyncSession, user_id: uuid.UUID, case_id: uuid.UUID) -> None:
    case = await session.get(NoteCase, case_id)
    if case is None or case.user_id != user_id:
        return
    await session.delete(case)
    await session.commit()
```

同时在文件顶部 import 区追加：

```python
from app.schemas.note import NoteListItem, NoteCaseItem, NoteDetailResponse
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_note_service.py -v`
Expected: 全部 12 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/note_service.py backend/tests/test_note_service.py
git commit -m "feat(notes): list/detail/delete 查询删除逻辑"
```

---

### Task 6: notes API 路由 + 注册

**Files:**
- Create: `backend/app/routers/notes.py`
- Modify: `backend/app/main.py:43-45`
- Test: `backend/tests/test_notes_api.py`

- [ ] **Step 1: 编写失败的 API 测试**

Create `backend/tests/test_notes_api.py`:

```python
import json

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services.llm_client import MockLLMClient, get_llm_client

POST_URL = "/api/v1/notes/save"
LIST_URL = "/api/v1/notes"
LOGIN_URL = "/api/v1/auth/login"

_ERROR = {"error_type": "动词形式", "fragment": "interested in read", "explanation": "介词后加 ing", "correction": "interested in reading"}


@pytest_asyncio.fixture
async def api():
    app = create_app()
    mock = MockLLMClient(responder=lambda msgs: json.dumps({
        "results": [{
            "rule_title": "介词后加 -ing 形式",
            "description": "介词后接动词用动名词形式",
            "example": "interested in read → interested in reading",
        }]
    }, ensure_ascii=False))
    app.dependency_overrides[get_llm_client] = lambda: mock
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _token(client: AsyncClient) -> str:
    r = await client.post(LOGIN_URL, json={"username": "demo", "password": "demo1234"})
    assert r.status_code == 200
    return r.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_save_note_unauthorized(api):
    r = await api.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "x", "errors": [_ERROR]})
    assert r.status_code == 401


async def test_save_note_creates_note(api):
    client = api
    token = await _token(client)
    r = await client.post(POST_URL, json={
        "message_id": "00000000-0000-0000-0000-000000000000",
        "source_text": "I interested in read",
        "errors": [_ERROR],
    }, headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert len(data["saved_notes"]) == 1
    assert data["saved_notes"][0]["is_new"] is True
    assert data["saved_notes"][0]["rule_title"] == "介词后加 -ing 形式"


async def test_list_notes_empty(api):
    client = api
    token = await _token(client)
    r = await client.get(LIST_URL, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["notes"] == []


async def test_list_notes_after_save(api):
    client = api
    token = await _token(client)
    await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    r = await client.get(LIST_URL, headers=_auth(token))
    assert r.status_code == 200
    notes = r.json()["notes"]
    assert len(notes) == 1
    assert notes[0]["case_count"] == 1


async def test_get_note_detail(api):
    client = api
    token = await _token(client)
    save_r = await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    note_id = save_r.json()["saved_notes"][0]["note_id"]
    r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 200
    assert len(r.json()["cases"]) == 1


async def test_get_note_detail_not_found(api):
    client = api
    token = await _token(client)
    r = await client.get(f"{LIST_URL}/00000000-0000-0000-0000-000000000000", headers=_auth(token))
    assert r.status_code == 404


async def test_delete_note(api):
    client = api
    token = await _token(client)
    save_r = await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    note_id = save_r.json()["saved_notes"][0]["note_id"]
    r = await client.delete(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 204
    r2 = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r2.status_code == 404


async def test_delete_case(api):
    client = api
    token = await _token(client)
    save_r = await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    note_id = save_r.json()["saved_notes"][0]["note_id"]
    detail_r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    case_id = detail_r.json()["cases"][0]["id"]
    r = await client.delete(f"{LIST_URL}/{note_id}/cases/{case_id}", headers=_auth(token))
    assert r.status_code == 204
    r2 = await client.get(LIST_URL, headers=_auth(token))
    assert r2.json()["notes"] == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_notes_api.py -v`
Expected: FAIL with 404 或路由不存在

- [ ] **Step 3: 实现 notes 路由**

Create `backend/app/routers/notes.py`:

```python
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db import get_db
from app.models.user import User
from app.schemas.note import (
    SaveNoteRequest,
    SaveNoteResponse,
    NoteListResponse,
    NoteDetailResponse,
)
from app.services import note_service
from app.services.auth_service import get_current_user
from app.services.llm_client import LLMClient, get_llm_client

router = APIRouter(prefix="/api/v1/notes", tags=["notes"])


@router.post("/save", response_model=SaveNoteResponse, status_code=200)
async def save_note(
    payload: SaveNoteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
):
    saved = await note_service.save_notes(
        session, user.id, payload.message_id, payload.source_text,
        [e.model_dump() for e in payload.errors], llm_client,
    )
    return SaveNoteResponse(saved_notes=saved)


@router.get("", response_model=NoteListResponse)
async def list_notes(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    notes = await note_service.list_notes(session, user.id)
    return NoteListResponse(notes=notes)


@router.get("/{note_id}", response_model=NoteDetailResponse)
async def get_note(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    detail = await note_service.get_note_detail(session, user.id, note_id)
    if detail is None:
        raise AppError(404, "NOTE_NOT_FOUND", "笔记不存在")
    return detail


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await note_service.delete_note(session, user.id, note_id)
    return None


@router.delete("/{note_id}/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    note_id: uuid.UUID,
    case_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await note_service.delete_case(session, user.id, case_id)
    return None
```

- [ ] **Step 4: 注册 router 到 main.py**

Modify `backend/app/main.py`，在 `from app.routers import auth, health, messages` 改为：

```python
from app.routers import auth, health, messages, notes
```

在 `app.include_router(messages.router)` 之后追加：

```python
    app.include_router(notes.router)
```

- [ ] **Step 5: 运行 API 测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_notes_api.py -v`
Expected: 8 PASS

- [ ] **Step 6: 运行全量后端测试确认无回归**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: 全部 PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/routers/notes.py backend/app/main.py backend/tests/test_notes_api.py
git commit -m "feat(notes): notes API 路由（save/list/detail/delete）"
```

---

### Task 7: 前端 notes API 客户端 + 类型导出

**Files:**
- Create: `web/src/api/notes.ts`
- Modify: `web/src/api/messages.ts:3-8`（导出 ErrorBlock 类型）

- [ ] **Step 1: 导出 ErrorBlock 类型**

Modify `web/src/api/messages.ts`，将 `interface ErrorBlock` 改为 `export interface ErrorBlock`（已是 export，确认即可）。无需改动。

- [ ] **Step 2: 扩展 http 客户端支持 DELETE**

Modify `web/src/api/client.ts`，在 `export const http` 对象中追加 `delete` 方法：

```typescript
export const http = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, {
      method: 'POST',
      body: data === undefined ? undefined : JSON.stringify(data),
    }),
  delete: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),
}
```

- [ ] **Step 3: 创建 notes API 客户端**

Create `web/src/api/notes.ts`:

```typescript
import { http } from './client'
import type { ErrorBlock } from './messages'

export interface SavedNoteItem {
  note_id: string
  rule_title: string
  is_new: boolean
  case_id: string
}

export interface SaveNoteResponse {
  saved_notes: SavedNoteItem[]
}

export interface NoteListItem {
  id: string
  rule_title: string
  description: string
  case_count: number
  updated_at: string
}

export interface NoteListResponse {
  notes: NoteListItem[]
}

export interface NoteCaseItem {
  id: string
  example: string
  source_text: string
  created_at: string
}

export interface NoteDetailResponse {
  id: string
  rule_title: string
  description: string
  cases: NoteCaseItem[]
}

export async function saveNote(
  messageId: string,
  sourceText: string,
  errors: ErrorBlock[],
): Promise<SaveNoteResponse> {
  return http.post<SaveNoteResponse>('/notes/save', {
    message_id: messageId,
    source_text: sourceText,
    errors,
  })
}

export async function fetchNotes(): Promise<NoteListItem[]> {
  const data = await http.get<NoteListResponse>('/notes')
  return data.notes
}

export async function fetchNoteDetail(noteId: string): Promise<NoteDetailResponse> {
  return http.get<NoteDetailResponse>(`/notes/${noteId}`)
}

export async function deleteNote(noteId: string): Promise<void> {
  await http.delete<void>(`/notes/${noteId}`)
}

export async function deleteNoteCase(
  noteId: string,
  caseId: string,
): Promise<void> {
  await http.delete<void>(`/notes/${noteId}/cases/${caseId}`)
}
```

- [ ] **Step 4: 运行前端 lint + build 确认无错误**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run lint && npm run build`
Expected: 无错误

- [ ] **Step 5: 提交**

```bash
git add web/src/api/notes.ts web/src/api/client.ts
git commit -m "feat(notes): 前端 notes API 客户端 + http DELETE 支持"
```

---

### Task 8: AppLayout 组件（左侧 sidebar + 顶部退出）

**Files:**
- Create: `web/src/components/AppLayout.tsx`
- Create: `web/src/components/Sidebar.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/pages/CorrectionPage.tsx`

- [ ] **Step 1: 创建 Sidebar 组件**

Create `web/src/components/Sidebar.tsx`:

```tsx
import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/correction', label: '纠错', icon: '✏️' },
  { to: '/notes', label: '我的笔记', icon: '📖' },
]

export default function Sidebar() {
  return (
    <nav className="flex flex-col gap-1 p-3">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              isActive
                ? 'bg-[#0ca678] text-white'
                : 'text-[#495057] hover:bg-[#f1f3f5]'
            }`
          }
        >
          <span>{item.icon}</span>
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
```

- [ ] **Step 2: 创建 AppLayout 组件**

Create `web/src/components/AppLayout.tsx`:

```tsx
import { useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/store/auth-context'

export default function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [drawerOpen, setDrawerOpen] = useState(false)

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-screen bg-[#f0fdfa]">
      {/* 桌面 sidebar */}
      <aside className="hidden w-[200px] shrink-0 flex-col border-r border-[#dee2e6] bg-white md:flex">
        <div className="flex items-center gap-2 px-4 py-4">
          <div className="flex size-7 items-center justify-center rounded-lg bg-[#0ca678] text-xs font-semibold text-white">
            E
          </div>
          <span className="text-base font-semibold text-[#0a7053]">Echo</span>
        </div>
        <Sidebar />
      </aside>

      {/* 移动端抽屉 */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="absolute left-0 top-0 h-full w-[200px] bg-white">
            <div className="flex items-center gap-2 px-4 py-4">
              <div className="flex size-7 items-center justify-center rounded-lg bg-[#0ca678] text-xs font-semibold text-white">
                E
              </div>
              <span className="text-base font-semibold text-[#0a7053]">Echo</span>
            </div>
            <div onClick={() => setDrawerOpen(false)}>
              <Sidebar />
            </div>
          </aside>
        </div>
      )}

      {/* 主内容区 */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-[#dee2e6] bg-white px-4 md:px-6">
          <button
            type="button"
            className="text-xl text-[#495057] md:hidden"
            onClick={() => setDrawerOpen(true)}
            aria-label="打开菜单"
          >
            ☰
          </button>
          <div className="hidden md:block" />
          <div className="flex items-center gap-3">
            <span className="text-sm text-[#495057]">{user?.username ?? ''}</span>
            <Button
              variant="outline"
              onClick={handleLogout}
              className="h-8 border-[#ced4da] bg-white px-3 text-[#343a40] hover:bg-[#f1f3f5]"
            >
              退出
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 更新 App.tsx 路由**

Modify `web/src/App.tsx` 为：

```tsx
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthGuard, GuestGuard } from '@/components/AuthGuard'
import AppLayout from '@/components/AppLayout'
import CorrectionPage from '@/pages/CorrectionPage'
import Login from '@/pages/Login'
import { useAuth } from '@/store/auth-context'
import { AuthProvider } from '@/store/auth'
import { ConversationProvider } from '@/store/conversation'
import NotesPage from '@/pages/NotesPage'

function RootRedirect() {
  const { user, ready } = useAuth()
  if (!ready) return null
  return <Navigate to={user ? '/correction' : '/login'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route element={<GuestGuard />}>
            <Route path="/login" element={<Login />} />
          </Route>
          <Route element={<AuthGuard />}>
            <Route element={<AppLayout />}>
              <Route
                path="/correction"
                element={
                  <ConversationProvider>
                    <CorrectionPage />
                  </ConversationProvider>
                }
              />
              <Route path="/notes" element={<NotesPage />} />
            </Route>
          </Route>
          <Route path="*" element={<RootRedirect />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
```

- [ ] **Step 4: 简化 CorrectionPage（移除 header）**

Modify `web/src/pages/CorrectionPage.tsx` 为：

```tsx
import Composer from '@/components/correction/Composer'
import MessageList from '@/components/correction/MessageList'

export default function CorrectionPage() {
  return (
    <div className="flex h-full flex-col">
      <MessageList />
      <Composer />
    </div>
  )
}
```

- [ ] **Step 5: 创建占位 NotesPage（Task 10 完善）**

Create `web/src/pages/NotesPage.tsx`:

```tsx
export default function NotesPage() {
  return (
    <div className="flex h-full items-center justify-center text-[#868e96]">
      笔记页（待实现）
    </div>
  )
}
```

- [ ] **Step 6: 运行 lint + build 确认无错误**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run lint && npm run build`
Expected: 无错误

- [ ] **Step 7: 提交**

```bash
git add web/src/components/AppLayout.tsx web/src/components/Sidebar.tsx web/src/App.tsx web/src/pages/CorrectionPage.tsx web/src/pages/NotesPage.tsx
git commit -m "feat(layout): 左侧 sidebar 导航 + AppLayout 包裹纠错/笔记页"
```

---

### Task 9: ErrorCard + CorrectionReportCard 记笔记按钮

**Files:**
- Modify: `web/src/components/correction/ErrorCard.tsx`
- Modify: `web/src/components/correction/CorrectionReportCard.tsx`
- Modify: `web/src/store/conversation.tsx`（暴露记笔记方法）

- [ ] **Step 1: 在 conversation store 暴露 saveNote 方法**

Modify `web/src/store/conversation.tsx`，在 `ConversationProvider` 中新增 `saveNote` 方法。在文件顶部 import 区追加：

```tsx
import * as notesApi from '@/api/notes'
import type { ErrorBlock } from '@/api/messages'
```

在 `value` useMemo 前追加：

```tsx
const saveNote = useCallback(
  async (
    messageId: string,
    sourceText: string,
    errors: ErrorBlock[],
  ): Promise<{ success: boolean; ruleTitles?: string[]; error?: string }> => {
    try {
      const result = await notesApi.saveNote(messageId, sourceText, errors)
      return {
        success: true,
        ruleTitles: result.saved_notes.map((n) => n.rule_title),
      }
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

在 `value` useMemo 的依赖数组中追加 `saveNote`，并在返回对象中追加 `saveNote`。

Modify `web/src/store/conversation-context.ts`，在 `ConversationState` 接口中追加 `saveNote` 字段：

```typescript
import { createContext, useContext } from 'react'

import type { ErrorBlock, Message } from '@/api/messages'

export interface ConversationState {
  messages: Message[]
  pending: boolean
  error: string | null
  sessionExpired: boolean
  load: () => Promise<void>
  send: (content: string) => Promise<boolean>
  retry: (tempId: string, content: string) => Promise<boolean>
  relogin: () => void
  saveNote: (
    messageId: string,
    sourceText: string,
    errors: ErrorBlock[],
  ) => Promise<{ success: boolean; ruleTitles?: string[]; error?: string }>
}

export const ConversationContext = createContext<ConversationState | null>(null)

export function useConversation(): ConversationState {
  const ctx = useContext(ConversationContext)
  if (!ctx) throw new Error('useConversation must be used within ConversationProvider')
  return ctx
}
```

- [ ] **Step 2: ErrorCard 改为受控组件（接收 state + onSave props）**

Modify `web/src/components/correction/ErrorCard.tsx` 为：

```tsx
import type { ErrorBlock } from '@/api/messages'
import { Button } from '@/components/ui/button'

type SaveState = 'idle' | 'loading' | 'done'

interface Props {
  error: ErrorBlock
  state: SaveState
  onSave?: () => void
}

export default function ErrorCard({ error, state, onSave }: Props) {
  return (
    <div className="rounded-lg border border-[#dee2e6] border-l-4 border-l-[#fa5252] bg-white p-3">
      <div className="flex items-center gap-2">
        <span className="rounded bg-[#fa5252] px-1.5 py-0.5 text-xs text-white">
          {error.error_type}
        </span>
        <span className="text-sm font-medium text-[#c92a2a] line-through">
          {error.fragment}
        </span>
      </div>
      <p className="mt-1.5 text-sm text-[#495057]">{error.explanation}</p>
      <div className="mt-1 flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-[#2b8a3e]">✅ {error.correction}</p>
        {onSave && (
          <Button
            variant="ghost"
            size="xs"
            disabled={state !== 'idle'}
            onClick={onSave}
            className="shrink-0 text-[#0ca678] hover:bg-[#f0fdfa]"
          >
            {state === 'done' ? '已记录 ✓' : state === 'loading' ? '保存中…' : '📝 记笔记'}
          </Button>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: CorrectionReportCard 加「全部记笔记」+ 单个保存编排**

Modify `web/src/components/correction/CorrectionReportCard.tsx` 为：

```tsx
import { useState } from 'react'

import { useConversation } from '@/store/conversation-context'
import type { CorrectionReport, ErrorBlock, Message } from '@/api/messages'
import ErrorCard from '@/components/correction/ErrorCard'
import LearningsSection from '@/components/correction/LearningsSection'
import RewriteSection from '@/components/correction/RewriteSection'
import { Button } from '@/components/ui/button'

type SaveState = 'idle' | 'loading' | 'done'

interface Props {
  report: CorrectionReport
  message: Message
}

export default function CorrectionReportCard({ report, message }: Props) {
  const { saveNote } = useConversation()
  const [batchState, setBatchState] = useState<SaveState>('idle')
  const [errorStates, setErrorStates] = useState<Record<number, SaveState>>({})
  const [toast, setToast] = useState<string | null>(null)

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 2000)
  }

  async function handleSaveOne(index: number, error: ErrorBlock) {
    setErrorStates((prev) => ({ ...prev, [index]: 'loading' }))
    const result = await saveNote(message.id, message.content ?? '', [error])
    if (result.success && result.ruleTitles) {
      setErrorStates((prev) => ({ ...prev, [index]: 'done' }))
      showToast(`已记入「${result.ruleTitles[0]}」`)
    } else {
      setErrorStates((prev) => ({ ...prev, [index]: 'idle' }))
      showToast(result.error ?? '保存失败，请重试')
    }
  }

  async function handleSaveAll() {
    if (batchState !== 'idle') return
    setBatchState('loading')
    const result = await saveNote(message.id, message.content ?? '', report.errors)
    if (result.success) {
      setBatchState('done')
      showToast(`已记入 ${result.ruleTitles?.length ?? 0} 条规则笔记`)
    } else {
      setBatchState('idle')
      showToast(result.error ?? '保存失败，请重试')
    }
  }

  if (!report.has_errors) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-xl bg-[#e6fcf5] px-4 py-2.5 text-[#0a7053] md:max-w-[90%]">
          🎉 这段英文写得不错，没有发现语法或不地道的表达！
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[90%] rounded-xl border border-[#dee2e6] bg-white p-3">
        <div className="rounded-lg border border-[#dee2e6] p-3">
          <p className="mb-2 text-sm font-semibold text-[#343a40]">错误分析</p>
          <div className="space-y-2">
            {report.errors.map((e, i) => (
              <ErrorCard
                key={`${i}-${e.fragment}`}
                error={e}
                state={errorStates[i] ?? 'idle'}
                onSave={() => handleSaveOne(i, e)}
              />
            ))}
          </div>
        </div>
        {report.rewrite && (
          <div className="mt-2 rounded-lg border border-[#dee2e6] p-3">
            <p className="mb-2 text-sm font-semibold text-[#343a40]">改写</p>
            <RewriteSection rewrite={report.rewrite} />
          </div>
        )}
        <div className="mt-2">
          <LearningsSection learnings={report.learnings ?? []} />
        </div>
        <div className="mt-2 flex justify-end">
          <Button
            variant="outline"
            size="sm"
            disabled={batchState !== 'idle'}
            onClick={handleSaveAll}
            className="border-[#0ca678] text-[#0ca678] hover:bg-[#f0fdfa]"
          >
            {batchState === 'done' ? '已记录 ✓' : batchState === 'loading' ? '保存中…' : '📝 全部记笔记'}
          </Button>
        </div>
        {toast && (
          <div className="mt-2 rounded-lg bg-[#f1f3f5] px-3 py-1.5 text-sm text-[#495057]">
            {toast}
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: 更新 MessageList 传递 sourceText 到 CorrectionReportCard**

`CorrectionReportCard` 需要 `source_text`（用户提交的原文），但当前 `MessageList` 只传 `report`（assistant 消息，content 为 null）。用户消息排在 assistant 消息前一条。修改 `MessageList` 从前一条 user 消息提取 `content` 作为 `sourceText`：

Modify `web/src/components/correction/MessageList.tsx` 的 `messages.map` 部分：

```tsx
{messages.map((m, i) =>
  m.role === 'user' ? (
    <UserBubble key={m.id} content={m.content ?? ''} />
  ) : m.report ? (
    <CorrectionReportCard
      key={m.id}
      report={m.report}
      message={m}
      sourceText={messages[i - 1]?.content ?? ''}
    />
  ) : null,
)}
```

同步更新 `CorrectionReportCard` 的 `Props` 接口，追加 `sourceText: string`，并使用 `sourceText` 替代 `message.content ?? ''`：

```tsx
interface Props {
  report: CorrectionReport
  message: Message
  sourceText: string
}

// 在 handleSaveOne / handleSaveAll 中：
const result = await saveNote(message.id, sourceText, [error])
```

- [ ] **Step 5: 运行 lint + build**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run lint && npm run build`
Expected: 无错误

- [ ] **Step 6: 提交**

```bash
git add web/src/components/correction/ErrorCard.tsx web/src/components/correction/CorrectionReportCard.tsx web/src/store/conversation.tsx web/src/store/conversation-context.ts web/src/components/correction/MessageList.tsx
git commit -m "feat(notes): ErrorCard 记笔记按钮 + CorrectionReportCard 全部记笔记"
```

---

### Task 10: NotesPage 笔记列表页

**Files:**
- Modify: `web/src/pages/NotesPage.tsx`（完善占位）
- Create: `web/src/components/notes/NoteCard.tsx`
- Create: `web/src/components/notes/NoteCaseItem.tsx`

- [ ] **Step 1: 创建 NoteCaseItem 组件**

Create `web/src/components/notes/NoteCaseItem.tsx`:

```tsx
import { useState } from 'react'

import type { NoteCaseItem } from '@/api/notes'
import { Button } from '@/components/ui/button'

interface Props {
  caseItem: NoteCaseItem
  noteId: string
  onDeleted: (caseId: string) => void
}

export default function NoteCaseItem({ caseItem, onDeleted }: Props) {
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [wrong, right] = caseItem.example.split('→').map((s) => s.trim())

  async function handleDelete() {
    setDeleting(true)
    onDeleted(caseItem.id)
  }

  return (
    <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-[#fff5f5] px-2 py-0.5 text-xs text-[#c92a2a]">
          {wrong ?? caseItem.example} ❌
        </span>
        <span className="text-[#adb5bd]">→</span>
        <span className="rounded bg-[#e6fcf5] px-2 py-0.5 text-xs text-[#2b8a3e]">
          {right ?? ''} ✅
        </span>
      </div>
      <p className="mt-1.5 text-xs text-[#868e96]">原文：{caseItem.source_text}</p>
      <div className="mt-2 flex justify-end">
        {confirming ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#868e96]">确认删除？</span>
            <Button variant="destructive" size="xs" disabled={deleting} onClick={handleDelete}>
              {deleting ? '删除中…' : '确认'}
            </Button>
            <Button variant="ghost" size="xs" onClick={() => setConfirming(false)}>
              取消
            </Button>
          </div>
        ) : (
          <Button variant="ghost" size="xs" onClick={() => setConfirming(true)} className="text-[#868e96]">
            ×
          </Button>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 创建 NoteCard 组件**

Create `web/src/components/notes/NoteCard.tsx`:

```tsx
import { useState } from 'react'

import { deleteNote, deleteNoteCase, fetchNoteDetail } from '@/api/notes'
import type { NoteListItem, NoteDetailResponse } from '@/api/notes'
import { Button } from '@/components/ui/button'
import NoteCaseItem from '@/components/notes/NoteCaseItem'

interface Props {
  note: NoteListItem
  onNoteDeleted: (noteId: string) => void
}

export default function NoteCard({ note, onNoteDeleted }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [detail, setDetail] = useState<NoteDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  async function toggleExpand() {
    if (!expanded && !detail) {
      setLoading(true)
      try {
        const d = await fetchNoteDetail(note.id)
        setDetail(d)
      } catch {
        // 静默
      } finally {
        setLoading(false)
      }
    }
    setExpanded(!expanded)
  }

  async function handleCaseDeleted(caseId: string) {
    try {
      await deleteNoteCase(note.id, caseId)
      if (detail) {
        const newCases = detail.cases.filter((c) => c.id !== caseId)
        if (newCases.length === 0) {
          onNoteDeleted(note.id)
        } else {
          setDetail({ ...detail, cases: newCases })
        }
      }
    } catch {
      // 静默
    }
  }

  async function handleDeleteNote() {
    try {
      await deleteNote(note.id)
      onNoteDeleted(note.id)
    } catch {
      // 静默
    }
  }

  return (
    <div className="rounded-xl border border-[#dee2e6] bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        <button type="button" onClick={toggleExpand} className="flex-1 text-left">
          <p className="text-sm font-semibold text-[#343a40]">{note.rule_title}</p>
          <p className="mt-0.5 line-clamp-1 text-xs text-[#868e96]">{note.description}</p>
          <p className="mt-1 text-xs text-[#adb5bd]">
            {note.case_count} 个案例 · 最近更新 {new Date(note.updated_at).toLocaleDateString()}
          </p>
        </button>
        <span className="text-[#adb5bd]">{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div className="mt-3 space-y-2">
          {loading ? (
            <p className="text-sm text-[#868e96]">加载中…</p>
          ) : detail ? (
            <>
              <p className="text-sm text-[#495057]">{detail.description}</p>
              {detail.cases.map((c) => (
                <NoteCaseItem
                  key={c.id}
                  caseItem={c}
                  noteId={note.id}
                  onDeleted={handleCaseDeleted}
                />
              ))}
              <div className="flex justify-end pt-2">
                {confirmDelete ? (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#868e96]">确认删除该笔记？</span>
                    <Button variant="destructive" size="xs" onClick={handleDeleteNote}>
                      确认
                    </Button>
                    <Button variant="ghost" size="xs" onClick={() => setConfirmDelete(false)}>
                      取消
                    </Button>
                  </div>
                ) : (
                  <Button variant="ghost" size="xs" onClick={() => setConfirmDelete(true)} className="text-[#fa5252]">
                    删除该笔记
                  </Button>
                )}
              </div>
            </>
          ) : null}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 完善 NotesPage**

Modify `web/src/pages/NotesPage.tsx` 为：

```tsx
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchNotes } from '@/api/notes'
import type { NoteListItem } from '@/api/notes'
import { Button } from '@/components/ui/button'
import NoteCard from '@/components/notes/NoteCard'

export default function NotesPage() {
  const [notes, setNotes] = useState<NoteListItem[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchNotes()
      setNotes(data)
    } catch {
      // 静默
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  function handleNoteDeleted(noteId: string) {
    setNotes((prev) => prev.filter((n) => n.id !== noteId))
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-[#868e96]">
        加载中…
      </div>
    )
  }

  if (notes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 text-[#868e96]">
        <p>还没有笔记</p>
        <Button
          variant="outline"
          onClick={() => navigate('/correction')}
          className="border-[#0ca678] text-[#0ca678] hover:bg-[#f0fdfa]"
        >
          去纠错页记下你的第一条规则
        </Button>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-4 md:p-6">
      <div className="mx-auto max-w-2xl space-y-3">
        <h1 className="text-lg font-semibold text-[#343a40]">我的笔记</h1>
        {notes.map((note) => (
          <NoteCard key={note.id} note={note} onNoteDeleted={handleNoteDeleted} />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: 运行 lint + build**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run lint && npm run build`
Expected: 无错误

- [ ] **Step 5: 提交**

```bash
git add web/src/pages/NotesPage.tsx web/src/components/notes/NoteCard.tsx web/src/components/notes/NoteCaseItem.tsx
git commit -m "feat(notes): 笔记列表页（展开/删除案例/删除笔记）"
```

---

### Task 11: E2E 测试扩展

**Files:**
- Modify: `backend/app/services/llm_client.py`（MockLLMClient 扩展笔记保存响应）
- Create: `web/tests/e2e/notes.spec.ts`

- [ ] **Step 1: 扩展 MockLLMClient 支持笔记保存响应**

修改 `backend/app/services/llm_client.py` 的 `_default_responder`，根据 user content 判断是纠错还是笔记保存请求，返回不同 mock 响应：

```python
def _default_responder(messages: list[dict[str, Any]]) -> str:
    """Mock 默认响应：区分纠错请求与笔记保存请求。"""
    user_contents = [m["content"] for m in messages if m.get("role") == "user"]
    last = user_contents[-1] if user_contents else ""

    # 笔记保存请求（note_prompt 的 user content 含「## 原文」标记）
    if "## 原文" in last and "## 错误列表" in last:
        return json.dumps(
            {
                "results": [
                    {
                        "rule_title": "介词后加 -ing 形式",
                        "description": "英语中介词后接动词时需用动名词形式(-ing)而非不定式。",
                        "example": "interested in read → interested in reading",
                    }
                ]
            },
            ensure_ascii=False,
        )

    # 纠错请求
    if "没有错误" in last or "no-error" in last:
        return json.dumps(
            {"has_errors": False, "errors": [], "rewrite": None, "learnings": []},
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "has_errors": True,
            "errors": [
                {
                    "error_type": "时态错误",
                    "fragment": "I go to",
                    "explanation": "yesterday 表示过去，故用过去式 went",
                    "correction": "I went to",
                }
            ],
            "rewrite": {
                "minimal": {"text": "Yesterday I went to the park.", "note": "修正时态，保留原句结构"},
                "natural": {"text": "Yesterday I enjoyed the park.", "note": "用 enjoyed 更自然"},
            },
            "learnings": [
                {
                    "rule": "yesterday 表示过去时间，主句动词应用过去式（go→went）。",
                    "example": "I go to → I went to",
                }
            ],
        },
        ensure_ascii=False,
    )
```

- [ ] **Step 2: 编写 E2E 测试**

Create `web/tests/e2e/notes.spec.ts`:

```typescript
import { expect, test, type Page } from '@playwright/test'

const USERNAME = 'shawn'
const PASSWORD = 'shawn!QAZ1qaz'

async function loginAndSubmit(page: Page) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(USERNAME)
  await page.getByLabel('密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page).toHaveURL(/\/correction$/)
  // 提交一句有错误的英文
  await page.getByPlaceholder('输入英文，AI 将为你纠错').fill('Yesterday I go to the park')
  await page.getByRole('button', { name: '发送' }).click()
  // 等待纠错报告出现
  await expect(page.getByText('错误分析')).toBeVisible({ timeout: 15000 })
}

test('N-01 单个错误记笔记', async ({ page }) => {
  await loginAndSubmit(page)
  // 点击第一个 ErrorCard 的「记笔记」按钮
  await page.getByRole('button', { name: '📝 记笔记' }).first().click()
  await expect(page.getByText(/已记入/)).toBeVisible({ timeout: 15000 })
})

test('N-02 全部记笔记', async ({ page }) => {
  await loginAndSubmit(page)
  await page.getByRole('button', { name: '📝 全部记笔记' }).click()
  await expect(page.getByText(/已记入 \d+ 条规则笔记/)).toBeVisible({ timeout: 15000 })
})

test('N-03 笔记列表页显示笔记', async ({ page }) => {
  await loginAndSubmit(page)
  await page.getByRole('button', { name: '📝 全部记笔记' }).click()
  await expect(page.getByText(/已记入/)).toBeVisible({ timeout: 15000 })
  // 导航到笔记页
  await page.getByRole('link', { name: /我的笔记/ }).click()
  await expect(page).toHaveURL(/\/notes$/)
  await expect(page.getByText('介词后加 -ing 形式')).toBeVisible()
})

test('N-04 笔记展开显示案例', async ({ page }) => {
  await loginAndSubmit(page)
  await page.getByRole('button', { name: '📝 全部记笔记' }).click()
  await expect(page.getByText(/已记入/)).toBeVisible({ timeout: 15000 })
  await page.getByRole('link', { name: /我的笔记/ }).click()
  await expect(page).toHaveURL(/\/notes$/)
  // 点击展开
  await page.getByText('介词后加 -ing 形式').click()
  await expect(page.getByText(/原文/)).toBeVisible()
})

test('N-05 笔记列表空态', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(USERNAME)
  await page.getByLabel('密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await page.getByRole('link', { name: /我的笔记/ }).click()
  await expect(page).toHaveURL(/\/notes$/)
  await expect(page.getByText('还没有笔记')).toBeVisible()
})

test('N-06 导航切换纠错↔笔记', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(USERNAME)
  await page.getByLabel('密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page).toHaveURL(/\/correction$/)
  await page.getByRole('link', { name: /我的笔记/ }).click()
  await expect(page).toHaveURL(/\/notes$/)
  await page.getByRole('link', { name: /纠错/ }).click()
  await expect(page).toHaveURL(/\/correction$/)
})
```

- [ ] **Step 3: 运行 E2E 测试**

前置：确保 db 容器运行 `docker compose up -d db`

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run test:e2e`
Expected: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/llm_client.py web/tests/e2e/notes.spec.ts
git commit -m "test(notes): E2E 测试（记笔记/笔记列表/导航切换）+ mock 扩展"
```

---

### Task 12: 全量回归 + 文档同步

**Files:**
- Modify: `PRD/Overview.md`（更新 F-02 状态）
- Modify: `docs/tech-design/00-Architecture.md`（数据模型补充）

- [ ] **Step 1: 后端全量测试**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: 全部 PASS

- [ ] **Step 2: 前端 lint + build + E2E**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run lint && npm run build && npm run test:e2e`
Expected: 全部 PASS

- [ ] **Step 3: 更新 PRD Overview F-02 状态**

Modify `PRD/Overview.md` §1.2，将「记笔记」从「后期版本增加」标注为「已实现（V0.1）」。

- [ ] **Step 4: 更新技术设计文档数据模型**

Modify `docs/tech-design/00-Architecture.md` §4.1 实体总览，追加 `notes` / `note_cases` 实体说明。

- [ ] **Step 5: 提交**

```bash
git add PRD/Overview.md docs/tech-design/00-Architecture.md
git commit -m "docs(notes): 同步 F-02 记笔记功能实现状态 + 数据模型"
```

---

## 验证清单

完成所有 Task 后，执行以下验证：

- [ ] **后端**: `cd backend && source .venv/bin/activate && pytest -v` — 全部 PASS
- [ ] **前端 lint**: `cd web && npm run lint` — 无错误
- [ ] **前端 build**: `cd web && npm run build` — 无错误
- [ ] **E2E**: `cd web && npm run test:e2e` — 全部 PASS
- [ ] **手动冒烟**: 启动本地全栈，登录 → 提交英文 → 单个记笔记 → 全部记笔记 → 查看笔记列表 → 展开笔记 → 删除案例 → 删除笔记 → 导航切换
