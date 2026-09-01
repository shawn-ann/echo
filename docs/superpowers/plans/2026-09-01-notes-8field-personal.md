# 笔记功能重构：8 字段 AI 初稿 + 个人化 + 自动保存 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将笔记功能重构为个人化 8 字段 AI 初稿 + 纠错后自动保存，移除全局规则库与手动「记笔记」按钮。

**Architecture:** 后端 `notes`/`note_cases` 表重构（个人化 + 8 字段），笔记 LLM prompt 重写（按 `error_type` 分组输出规则级 4 字段 + `change_details`），`POST /messages` 成功后后台自动触发笔记保存（复用现有 `BackgroundTasks` + 独立 session 模式），删除 `POST /notes/save` 接口。前端移除「记笔记」按钮、笔记页展示 8 字段。

**Tech Stack:** FastAPI + SQLAlchemy(async) + Pydantic 2 + Alembic + PostgreSQL（后端）；React 19 + TypeScript + TailwindCSS（前端）。测试：pytest + httpx ASGITransport（后端）、tsc + oxlint（前端）。

**关联 spec:** `docs/superpowers/specs/2026-09-01-notes-8field-personal-design.md`

---

## 文件结构

### 后端
- `backend/app/models/note.py` — 重写：`notes` 加 `user_id` + 规则级 4 字段；`note_cases` 改案例级 4 字段
- `backend/alembic/versions/xxx_add_user_id_and_8field_notes.py` — 新建迁移（清数据重建）
- `backend/app/schemas/note.py` — 重写：`NoteLLMResponse`/`NoteListItem`/`NoteDetailResponse`/`NoteCaseItem` 8 字段；删 `NoteExample`/`SavedNoteItem`/`NoteSaveAccepted`
- `backend/app/prompts/note_prompt.py` — 重写：8 字段输出 + 按 `error_type` 分组
- `backend/app/services/note_service.py` — 重写：`save_notes` 个人化入库（含 `polished_sentence` 参数）；`list_notes`/`get_note_detail`/删除保留
- `backend/app/routers/notes.py` — 删 `POST /save`；`GET`/`DELETE` 保留
- `backend/app/routers/messages.py` — `POST /messages` 成功后后台触发笔记保存
- `backend/app/services/llm_client.py` — 更新 `_default_responder` 笔记 mock 为 8 字段结构

### 后端测试
- `backend/tests/test_models_note.py` — 重写为新模型
- `backend/tests/test_note_prompt.py` — 重写为新 prompt
- `backend/tests/test_note_service.py` — 重写为新 `save_notes`
- `backend/tests/test_notes_api.py` — 删 `POST /save` 用例；列表/详情/删除适配新字段
- `backend/tests/test_messages_api.py` — 新增「纠错自动触发笔记」用例

### 前端
- `web/src/api/notes.ts` — 删 `saveNote`/`NoteSaveAccepted`/`NoteExample`；更新类型
- `web/src/api/messages.ts` — 不变
- `web/src/store/conversation.tsx` — 删 `saveNote`
- `web/src/store/conversation-context.ts` — 删 `saveNote`
- `web/src/components/correction/CorrectionReportCard.tsx` — 删「记笔记」按钮逻辑
- `web/src/components/correction/ErrorCard.tsx` — 删 `onSave`/`state`
- `web/src/components/notes/NoteCard.tsx` — 展示 8 字段（knowledge_point 摘要 + 展开详情）
- `web/src/components/notes/NoteCaseItem.tsx` — 展示案例级 4 字段
- `web/src/pages/NotesPage.tsx` — 空态文案更新

---

## Task 1: 重写 `notes` / `note_cases` 数据模型

**Files:**
- Modify: `backend/app/models/note.py`
- Test: `backend/tests/test_models_note.py`

- [ ] **Step 1: 重写测试 `backend/tests/test_models_note.py`**

```python
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import async_session_factory
from app.models.note import Note, NoteCase
from app.models.user import User


async def _demo_user_id() -> uuid.UUID:
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        return user.id


async def test_create_note_with_8field_fields():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(
            user_id=uid,
            rule_title="第三人称单数主谓一致",
            knowledge_point="一般现在时中，第三人称单数主语动词加 -s/-es",
            warning="你常忘给 she/he/it 加 -s",
            alternatives=["She runs.", "He goes."],
            feynman_question="主语是 she/he/it 时动词怎么变？",
        )
        s.add(note)
        await s.flush()
        case = NoteCase(
            note_id=note.id,
            user_id=uid,
            original_sentence="She go to school.",
            polished_sentence="She goes to school.",
            change_details="She go → She goes",
            error_root="主谓不一致",
        )
        s.add(case)
        await s.commit()
        assert note.id is not None
        assert note.user_id == uid
        assert note.alternatives == ["She runs.", "He goes."]
        assert case.original_sentence == "She go to school."
        assert case.polished_sentence == "She goes to school."
        assert case.change_details == "She go → She goes"
        assert case.error_root == "主谓不一致"


async def test_notes_unique_user_rule_title():
    """同 (user_id, rule_title) 唯一：重复插入抛 IntegrityError"""
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        s.add(Note(user_id=uid, rule_title="重复规则", knowledge_point="kp"))
        await s.commit()
    async with async_session_factory() as s:
        with pytest.raises(IntegrityError):
            s.add(Note(user_id=uid, rule_title="重复规则", knowledge_point="kp"))
            await s.commit()


async def test_note_cases_unique_note_user_original():
    """同 (note_id, user_id, original_sentence) 唯一：重复插入抛 IntegrityError"""
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(user_id=uid, rule_title="唯一约束规则", knowledge_point="kp")
        s.add(note)
        await s.flush()
        s.add(NoteCase(note_id=note.id, user_id=uid, original_sentence="src", polished_sentence="fix", change_details="d", error_root="r"))
        await s.commit()
    async with async_session_factory() as s:
        with pytest.raises(IntegrityError):
            s.add(NoteCase(note_id=note.id, user_id=uid, original_sentence="src", polished_sentence="fix", change_details="d", error_root="r"))
            await s.commit()


async def test_note_case_cascade_delete_note():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(user_id=uid, rule_title="级联规则", knowledge_point="kp")
        s.add(note)
        await s.flush()
        case_id = uuid.uuid4()
        s.add(NoteCase(id=case_id, note_id=note.id, user_id=uid, original_sentence="src", polished_sentence="fix", change_details="d", error_root="r"))
        await s.commit()
        await s.delete(note)
        await s.commit()
    async with async_session_factory() as s:
        assert (await s.get(NoteCase, case_id)) is None


async def test_delete_message_keeps_case():
    from app.models.conversation import SessionConversation
    from app.models.message import Message, MessageRole, MessageType

    uid = await _demo_user_id()
    async with async_session_factory() as s:
        conv = SessionConversation(user_id=uid)
        s.add(conv)
        await s.flush()
        msg = Message(conversation_id=conv.id, role=MessageRole.user, type=MessageType.correction, content="test")
        s.add(msg)
        await s.flush()
        note = Note(user_id=uid, rule_title="消息规则", knowledge_point="kp")
        s.add(note)
        await s.flush()
        case = NoteCase(note_id=note.id, user_id=uid, original_sentence="src", polished_sentence="fix", change_details="d", error_root="r", source_message_id=msg.id)
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

Run: `pytest tests/test_models_note.py -v`
Expected: FAIL（`note.user_id` 属性不存在、`NoteCase.original_sentence` 不存在等）

- [ ] **Step 3: 重写 `backend/app/models/note.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (
        UniqueConstraint("user_id", "rule_title", name="uq_notes_user_rule_title"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", name="fk_notes_user_id", ondelete="CASCADE"), nullable=False
    )
    rule_title: Mapped[str] = mapped_column(String(200), nullable=False)
    knowledge_point: Mapped[str] = mapped_column(Text, nullable=False)
    warning: Mapped[str] = mapped_column(Text, nullable=False)
    alternatives: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    feynman_question: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NoteCase(Base):
    __tablename__ = "note_cases"
    __table_args__ = (
        UniqueConstraint(
            "note_id", "user_id", "original_sentence",
            name="uq_note_cases_dedup",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notes.id", name="fk_note_cases_note_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", name="fk_note_cases_user_id", ondelete="CASCADE"), nullable=False
    )
    original_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    polished_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    change_details: Mapped[str] = mapped_column(Text, nullable=False)
    error_root: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", name="fk_note_cases_message_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_models_note.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/note.py backend/tests/test_models_note.py
git commit -m "refactor(notes): notes/note_cases 模型重构为个人化 8 字段"
```

---

## Task 2: 新建 Alembic 迁移（清数据重建）

**Files:**
- Create: `backend/alembic/versions/<rev>_notes_8field_rebuild.py`
- Test: 无（验证通过 `alembic upgrade head`）

- [ ] **Step 1: 生成迁移骨架**

Run: `alembic revision -m "notes 8field rebuild"`
Expected: 生成 `<rev>_notes_8field_rebuild.py`，`down_revision=f1fd79983847`

- [ ] **Step 2: 填入迁移内容（编辑新文件）**

```python
"""notes 8field rebuild

Revision ID: <rev>
Revises: f1fd79983847
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '<rev>'
down_revision: Union[str, Sequence[str], None] = 'f1fd79983847'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('note_cases')
    op.drop_table('notes')

    op.create_table('notes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('rule_title', sa.String(length=200), nullable=False),
    sa.Column('knowledge_point', sa.Text(), nullable=False),
    sa.Column('warning', sa.Text(), nullable=False),
    sa.Column('alternatives', postgresql.JSONB(), nullable=False),
    sa.Column('feynman_question', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_notes_user_id', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'rule_title', name='uq_notes_user_rule_title')
    )
    op.create_table('note_cases',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('note_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('original_sentence', sa.Text(), nullable=False),
    sa.Column('polished_sentence', sa.Text(), nullable=False),
    sa.Column('change_details', sa.Text(), nullable=False),
    sa.Column('error_root', sa.Text(), nullable=False),
    sa.Column('source_message_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['note_id'], ['notes.id'], name='fk_note_cases_note_id', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_message_id'], ['messages.id'], name='fk_note_cases_message_id', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_note_cases_user_id', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('note_id', 'user_id', 'original_sentence', name='uq_note_cases_dedup')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('note_cases')
    op.drop_table('notes')
    op.create_table('notes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('rule_title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('examples', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('note_cases',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('note_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('fragment', sa.Text(), nullable=False),
    sa.Column('correction', sa.Text(), nullable=False),
    sa.Column('source_text', sa.Text(), nullable=False),
    sa.Column('source_message_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['note_id'], ['notes.id'], name='fk_note_cases_note_id', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_message_id'], ['messages.id'], name='fk_note_cases_message_id', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_note_cases_user_id', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('note_id', 'user_id', 'source_text', 'fragment', name='uq_note_cases_dedup')
    )
```

- [ ] **Step 3: 验证迁移（需本地 db 运行）**

Run: `alembic upgrade head`
Expected: 迁移成功，`notes`/`note_cases` 重建为新结构

- [ ] **Step 4: 提交**

```bash
git add backend/alembic/versions/<rev>_notes_8field_rebuild.py
git commit -m "migrate(notes): 重建 notes/note_cases 为个人化 8 字段结构"
```

---

## Task 3: 重写笔记 Schema

**Files:**
- Modify: `backend/app/schemas/note.py`
- Test: 由 Task 4-6 覆盖，本任务无独立测试

- [ ] **Step 1: 重写 `backend/app/schemas/note.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NoteRuleCase(BaseModel):
    """LLM 输出的单个规则下的案例（change_details 由 LLM 生成）"""
    change_details: str


class NoteRuleResult(BaseModel):
    """LLM 输出的单个规则（8 字段中的规则级字段 + 案例）"""
    rule_title: str
    knowledge_point: str
    warning: str
    alternatives: list[str] = Field(default_factory=list)
    feynman_question: str
    error_root: str
    cases: list[NoteRuleCase] = Field(default_factory=list)


class NoteLLMResponse(BaseModel):
    results: list[NoteRuleResult]


class NoteListItem(BaseModel):
    id: uuid.UUID
    rule_title: str
    knowledge_point: str
    case_count: int
    updated_at: datetime


class NoteListResponse(BaseModel):
    notes: list[NoteListItem]


class NoteCaseItem(BaseModel):
    id: uuid.UUID
    original_sentence: str
    polished_sentence: str
    change_details: str
    error_root: str
    created_at: datetime


class NoteDetailResponse(BaseModel):
    id: uuid.UUID
    rule_title: str
    knowledge_point: str
    warning: str
    alternatives: list[str]
    feynman_question: str
    cases: list[NoteCaseItem]
```

> 删除 `SaveNoteRequest`、`NoteExample`、`SavedNoteItem`、`NoteSaveAccepted`、`NoteCaseItem`（旧版）。

- [ ] **Step 2: 提交**

```bash
git add backend/app/schemas/note.py
git commit -m "refactor(notes): 重写笔记 schema 为 8 字段结构"
```

---

## Task 4: 重写笔记 LLM prompt

**Files:**
- Modify: `backend/app/prompts/note_prompt.py`
- Test: `backend/tests/test_note_prompt.py`

- [ ] **Step 1: 重写测试 `backend/tests/test_note_prompt.py`**

```python
from app.prompts.note_prompt import build_note_system_prompt, build_note_user_content


def test_system_prompt_contains_8field_fields():
    prompt = build_note_system_prompt()
    assert "rule_title" in prompt
    assert "knowledge_point" in prompt
    assert "warning" in prompt
    assert "alternatives" in prompt
    assert "feynman_question" in prompt
    assert "error_root" in prompt
    assert "change_details" in prompt


def test_system_prompt_group_by_error_type():
    prompt = build_note_system_prompt()
    assert "error_type" in prompt
    assert "合并" in prompt


def test_system_prompt_no_dedup():
    prompt = build_note_system_prompt()
    assert "已有规则" not in prompt


def test_user_content_contains_source_and_errors():
    content = build_note_user_content(
        source_text="She go to school. He go home.",
        errors=[
            {"error_type": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"},
            {"error_type": "主谓不一致", "fragment": "He go", "explanation": "x", "correction": "He goes"},
        ],
    )
    assert "She go to school. He go home." in content
    assert "She go" in content
    assert "She goes" in content
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_note_prompt.py -v`
Expected: FAIL（`build_note_system_prompt` 仍要求 `existing_rules` 参数）

- [ ] **Step 3: 重写 `backend/app/prompts/note_prompt.py`**

```python
"""保存笔记时 LLM 提示词：从错误生成 8 字段笔记初稿。"""


def build_note_system_prompt() -> str:
    return """你是英语学习笔记生成助手。根据用户提交的英文原文和错误列表，按错误类型生成标准化学习笔记初稿。

## 输入
- 原文：用户手写的英文句子
- 错误列表：每条含 error_type（中文错误类型词表）、fragment（原文错误片段）、explanation、correction（最小修正）

## 分组规则
- 按 error_type 分组：相同 error_type 的错误归入同一条 result
- 不同 error_type 的错误生成不同 result
- 每个 result 的 error_root 必须原样取该组的 error_type 值

## 输出格式
输出 JSON 对象，含 results 数组，每个元素对应一个错误类型分组：
```json
{
  "results": [
    {
      "rule_title": "第三人称单数主谓一致",
      "knowledge_point": "一般现在时中，主语为第三人称单数时，实义动词加 -s/-es。如 She goes、He runs。",
      "warning": "你常忘给 she/he/it 加 -s，写邮件时先检查主语",
      "alternatives": [
        "She runs the daily report.",
        "He handles the tickets."
      ],
      "feynman_question": "主语是 she/he/it 时，动词该怎么变？为什么？",
      "error_root": "主谓不一致",
      "cases": [
        {
          "change_details": "She go → She goes; He go → He goes"
        }
      ]
    }
  ]
}
```

## 字段要求
- rule_title：描述一个【可单独测试的规则点】，不是语法范畴
  - ✅ 好："介词后加 -ing 形式"、"to 不定式接动词原形"、"可数名词单数需加冠词"
  - ❌ 坏："过去时"、"冠词"、"时态"、"介词"（太宽泛）
- knowledge_point：规则说明、构成方式、常见情况、边界/例外，一段完整讲解
- warning：针对本次错误的个人易错警示，提醒用户规避
- alternatives：2-3 条完整英文句子，覆盖不同正式程度的职场替换表达
- feynman_question：1 个闭卷自测问题，用于复盘巩固
- error_root：原样取该组的 error_type 值
- change_details：该组内每个错误的 `fragment → correction`，用分号 `;` 串联
  - 例如："She go → She goes; He go → He goes"
  - fragment 必须原样取自错误列表，不得改写
  - 仅保留本组错误相关的修改，不得混入其他错误类型的修改

## 约束
- 不得合并不同 error_type 的错误
- change_details 中每个错误只出现一次
"""


def build_note_user_content(source_text: str, errors: list[dict]) -> str:
    import json

    return f"""## 原文
{source_text}

## 错误列表
{json.dumps(errors, ensure_ascii=False, indent=2)}
"""
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_note_prompt.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/prompts/note_prompt.py backend/tests/test_note_prompt.py
git commit -m "refactor(notes): 笔记 prompt 重写为 8 字段 + 按 error_type 分组"
```

---

## Task 5: 更新 Mock LLM 响应

**Files:**
- Modify: `backend/app/services/llm_client.py`
- Test: 由 Task 6-8 覆盖

- [ ] **Step 1: 更新 `_default_responder` 中笔记分支为 8 字段结构**

替换 `backend/app/services/llm_client.py:72-90` 的笔记保存分支：

```python
    # 笔记保存请求（note_prompt 的 user content 含「## 原文」标记）
    if "## 原文" in last and "## 错误列表" in last:
        return json.dumps(
            {
                "results": [
                    {
                        "rule_title": "介词后加 -ing 形式",
                        "knowledge_point": "介词后接动词时需用动名词形式(-ing)而非不定式。如 be interested in reading、good at swimming。",
                        "warning": "你常把介词后的动词写成原形，注意介词后一律用 -ing",
                        "alternatives": [
                            "She is interested in reading technical docs.",
                            "He is good at presenting in meetings.",
                            "The team is responsible for shipping the release.",
                        ],
                        "feynman_question": "介词后接动词用什么形式？为什么不能用不定式？",
                        "error_root": "动词形式",
                        "cases": [
                            {"change_details": "interested in read → interested in reading"}
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        )
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/llm_client.py
git commit -m "refactor(notes): mock LLM 响应适配 8 字段笔记结构"
```

---

## Task 6: 重写 `note_service.save_notes`（个人化 + 8 字段入库）

**Files:**
- Modify: `backend/app/services/note_service.py`
- Test: `backend/tests/test_note_service.py`

- [ ] **Step 1: 重写测试 `backend/tests/test_note_service.py`**

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


def _mock_responder(msgs):
    return json.dumps({
        "results": [{
            "rule_title": "第三人称单数主谓一致",
            "knowledge_point": "一般现在时中，第三人称单数主语动词加 -s/-es",
            "warning": "你常忘给 she/he/it 加 -s",
            "alternatives": ["She runs.", "He goes."],
            "feynman_question": "主语是 she/he/it 时动词怎么变？",
            "error_root": "主谓不一致",
            "cases": [{"change_details": "She go → She goes; He go → He goes"}],
        }]
    }, ensure_ascii=False)


async def test_save_creates_note_with_8field_and_case():
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"},
        {"error_type": "主谓不一致", "fragment": "He go", "explanation": "x", "correction": "He goes"},
    ]
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder)
        result = await save_notes(s, uid, None, "She go to school. He go home.", "She goes to school. He goes home.", errors, mock)
        assert len(result) == 1

    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "第三人称单数主谓一致"))).scalar_one()
        assert note.user_id == uid
        assert note.knowledge_point == "一般现在时中，第三人称单数主语动词加 -s/-es"
        assert note.warning == "你常忘给 she/he/it 加 -s"
        assert note.alternatives == ["She runs.", "He goes."]
        assert note.feynman_question == "主语是 she/he/it 时动词怎么变？"
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 1
        case = cases[0]
        assert case.original_sentence == "She go to school. He go home."
        assert case.polished_sentence == "She goes to school. He goes home."
        assert case.change_details == "She go → She goes; He go → He goes"
        assert case.error_root == "主谓不一致"


async def test_save_group_by_error_type_creates_multiple_notes():
    """不同 error_type 生成多条笔记"""
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"},
        {"error_type": "冠词缺失", "fragment": "a apple", "explanation": "x", "correction": "an apple"},
    ]
    responder = lambda msgs: json.dumps({
        "results": [
            {
                "rule_title": "主谓一致规则", "knowledge_point": "kp", "warning": "w",
                "alternatives": ["A"], "feynman_question": "q", "error_root": "主谓不一致",
                "cases": [{"change_details": "She go → She goes"}],
            },
            {
                "rule_title": "元音音素前用 an", "knowledge_point": "kp2", "warning": "w2",
                "alternatives": ["B"], "feynman_question": "q2", "error_root": "冠词缺失",
                "cases": [{"change_details": "a apple → an apple"}],
            },
        ]
    }, ensure_ascii=False)
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=responder)
        result = await save_notes(s, uid, None, "She go to school and eat a apple", "She goes to school and eats an apple", errors, mock)
        assert len(result) == 2
    async with async_session_factory() as s:
        notes = (await s.execute(select(Note).where(Note.user_id == uid))).scalars().all()
        assert len(notes) == 2
        roots = {c.error_root for n in notes for c in (await s.execute(select(NoteCase).where(NoteCase.note_id == n.id))).scalars().all()}
        assert roots == {"主谓不一致", "冠词缺失"}


async def test_save_reuses_note_by_user_rule_title():
    """同 (user_id, rule_title) 复用笔记，追加案例"""
    uid = await _demo_user_id()
    errors1 = [{"error_type": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"}]
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder)
        await save_notes(s, uid, None, "She go to school.", "She goes to school.", errors1, mock)
    async with async_session_factory() as s:
        mock2 = MockLLMClient(responder=_mock_responder)
        result = await save_notes(s, uid, None, "He go home.", "He goes home.", errors1, mock2)
        assert len(result) == 1
    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "第三人称单数主谓一致"))).scalar_one()
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 2


async def test_save_different_user_creates_separate_note():
    """不同用户的同 rule_title 是独立笔记"""
    uid1 = await _demo_user_id()
    async with async_session_factory() as s:
        from app.core.security import hash_password
        from app.models.user import User, UserStatus
        s.add(User(username="other_u", password_hash=hash_password("other1234"), status=UserStatus.active))
        await s.commit()
        uid2 = (await s.execute(select(User).where(User.username == "other_u"))).scalar_one().id
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder)
        await save_notes(s, uid1, None, "She go to school.", "She goes to school.", [{"error_type": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"}], mock)
        await save_notes(s, uid2, None, "He go home.", "He goes home.", [{"error_type": "主谓不一致", "fragment": "He go", "explanation": "x", "correction": "He goes"}], mock)
    async with async_session_factory() as s:
        notes = (await s.execute(select(Note))).scalars().all()
        assert len(notes) == 2
        assert {n.user_id for n in notes} == {uid1, uid2}


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
            await save_notes(s, uid, None, "x", "y", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 504


async def test_save_llm_unavailable_raises_503():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = _RaisingLLMClient(LLMUnavailableError())
        with pytest.raises(AppError) as exc_info:
            await save_notes(s, uid, None, "x", "y", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 503


async def test_save_invalid_llm_response_raises_502():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=lambda msgs: "not-json")
        with pytest.raises(AppError) as exc_info:
            await save_notes(s, uid, None, "x", "y", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 502
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_note_service.py -v`
Expected: FAIL（`save_notes` 签名不匹配、新字段不存在）

- [ ] **Step 3: 重写 `backend/app/services/note_service.py`**

```python
import json
import uuid
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.message import Message
from app.models.note import Note, NoteCase
from app.prompts.note_prompt import build_note_system_prompt, build_note_user_content
from app.schemas.note import (
    NoteCaseItem,
    NoteDetailResponse,
    NoteListItem,
    NoteLLMResponse,
    NoteRuleResult,
)
from app.services.llm_client import LLMClient, LLMTimeoutError, LLMUnavailableError


async def _call_llm_and_parse(
    llm_client: LLMClient, source_text: str, errors: list[dict]
) -> NoteLLMResponse:
    messages = [
        {"role": "system", "content": build_note_system_prompt()},
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
    polished_sentence: str,
    errors: list[dict],
    llm_client: LLMClient,
) -> list[NoteRuleResult]:
    parsed = await _call_llm_and_parse(llm_client, source_text, errors)

    if source_message_id is not None and (await session.get(Message, source_message_id)) is None:
        source_message_id = None

    saved: list[NoteRuleResult] = []
    for result in parsed.results:
        note = (
            await session.execute(
                select(Note).where(
                    Note.user_id == user_id, Note.rule_title == result.rule_title
                )
            )
        ).scalars().first()
        if note is None:
            note = Note(
                user_id=user_id,
                rule_title=result.rule_title,
                knowledge_point=result.knowledge_point,
                warning=result.warning,
                alternatives=result.alternatives,
                feynman_question=result.feynman_question,
            )
            session.add(note)
            await session.flush()

        for case in result.cases:
            existing_case = (
                await session.execute(
                    select(NoteCase.id).where(
                        NoteCase.note_id == note.id,
                        NoteCase.user_id == user_id,
                        NoteCase.original_sentence == source_text,
                    )
                )
            ).scalars().first()
            if existing_case is not None:
                continue
            session.add(
                NoteCase(
                    note_id=note.id,
                    user_id=user_id,
                    original_sentence=source_text,
                    polished_sentence=polished_sentence,
                    change_details=case.change_details,
                    error_root=result.error_root,
                    source_message_id=source_message_id,
                )
            )
            note.updated_at = datetime.now(timezone.utc)

        saved.append(result)

    await session.commit()
    return saved


async def list_notes(session: AsyncSession, user_id: uuid.UUID) -> list[NoteListItem]:
    rows = (
        await session.execute(
            select(
                Note.id,
                Note.rule_title,
                Note.knowledge_point,
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
            id=r.id, rule_title=r.rule_title, knowledge_point=r.knowledge_point,
            case_count=r.case_count, updated_at=r.updated_at,
        )
        for r in rows
    ]


async def get_note_detail(
    session: AsyncSession, user_id: uuid.UUID, note_id: uuid.UUID
) -> NoteDetailResponse | None:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user_id:
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
        knowledge_point=note.knowledge_point,
        warning=note.warning,
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


async def delete_note(session: AsyncSession, user_id: uuid.UUID, note_id: uuid.UUID) -> None:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user_id:
        return
    await session.delete(note)
    await session.commit()


async def delete_case(session: AsyncSession, user_id: uuid.UUID, case_id: uuid.UUID) -> None:
    case = await session.get(NoteCase, case_id)
    if case is None or case.user_id != user_id:
        return
    await session.delete(case)
    await session.commit()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_note_service.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/note_service.py backend/tests/test_note_service.py
git commit -m "refactor(notes): save_notes 个人化 8 字段入库，同用户同规则复用"
```

---

## Task 7: 更新笔记路由（删 `/notes/save`）

**Files:**
- Modify: `backend/app/routers/notes.py`
- Test: `backend/tests/test_notes_api.py`

- [ ] **Step 1: 重写测试 `backend/tests/test_notes_api.py`（删 POST /save 用例，适配新字段）**

```python
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db import async_session_factory
from app.main import create_app
from app.models.note import Note, NoteCase
from app.models.user import User, UserStatus
from app.services.llm_client import MockLLMClient, get_llm_client

LIST_URL = "/api/v1/notes"
LOGIN_URL = "/api/v1/auth/login"


def _mock_responder(msgs):
    import json

    return json.dumps({
        "results": [{
            "rule_title": "第三人称单数主谓一致",
            "knowledge_point": "一般现在时中，第三人称单数主语动词加 -s/-es",
            "warning": "你常忘给 she/he/it 加 -s",
            "alternatives": ["She runs.", "He goes."],
            "feynman_question": "主语是 she/he/it 时动词怎么变？",
            "error_root": "主谓不一致",
            "cases": [{"change_details": "She go → She goes"}],
        }]
    }, ensure_ascii=False)


@pytest_asyncio.fixture
async def api():
    app = create_app()
    mock = MockLLMClient(responder=_mock_responder)
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


async def _seed_note(client, token, source_text="She go to school.", polished="She goes to school.") -> uuid.UUID:
    """直接入库一条笔记（模拟自动保存结果）"""
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        note = Note(
            user_id=user.id,
            rule_title="第三人称单数主谓一致",
            knowledge_point="一般现在时中，第三人称单数主语动词加 -s/-es",
            warning="w", alternatives=["A"], feynman_question="q",
        )
        s.add(note)
        await s.flush()
        s.add(NoteCase(
            note_id=note.id, user_id=user.id,
            original_sentence=source_text, polished_sentence=polished,
            change_details="She go → She goes", error_root="主谓不一致",
        ))
        await s.commit()
        return note.id


async def test_save_note_route_deleted(api):
    """POST /notes/save 已删除 → 404"""
    client = api
    token = await _token(client)
    r = await client.post("/api/v1/notes/save", json={}, headers=_auth(token))
    assert r.status_code == 404


async def test_list_notes_empty(api):
    client = api
    token = await _token(client)
    r = await client.get(LIST_URL, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["notes"] == []


async def test_list_notes_after_auto_save(api):
    client = api
    token = await _token(client)
    await _seed_note(client, token)
    r = await client.get(LIST_URL, headers=_auth(token))
    assert r.status_code == 200
    notes = r.json()["notes"]
    assert len(notes) == 1
    assert notes[0]["case_count"] == 1
    assert notes[0]["knowledge_point"] == "一般现在时中，第三人称单数主语动词加 -s/-es"


async def test_get_note_detail_8field(api):
    client = api
    token = await _token(client)
    note_id = await _seed_note(client, token)
    r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 200
    detail = r.json()
    assert detail["knowledge_point"] == "一般现在时中，第三人称单数主语动词加 -s/-es"
    assert detail["warning"] == "w"
    assert detail["alternatives"] == ["A"]
    assert detail["feynman_question"] == "q"
    assert len(detail["cases"]) == 1
    case = detail["cases"][0]
    assert case["original_sentence"] == "She go to school."
    assert case["polished_sentence"] == "She goes to school."
    assert case["change_details"] == "She go → She goes"
    assert case["error_root"] == "主谓不一致"


async def test_get_note_detail_not_found(api):
    client = api
    token = await _token(client)
    r = await client.get(f"{LIST_URL}/00000000-0000-0000-0000-000000000000", headers=_auth(token))
    assert r.status_code == 404


async def test_delete_note(api):
    client = api
    token = await _token(client)
    note_id = await _seed_note(client, token)
    r = await client.delete(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 204
    r2 = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r2.status_code == 404


async def test_delete_case(api):
    client = api
    token = await _token(client)
    note_id = await _seed_note(client, token)
    detail_r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    case_id = detail_r.json()["cases"][0]["id"]
    r = await client.delete(f"{LIST_URL}/{note_id}/cases/{case_id}", headers=_auth(token))
    assert r.status_code == 204
    r2 = await client.get(LIST_URL, headers=_auth(token))
    assert r2.json()["notes"] == []


async def test_get_note_detail_other_user_not_found(api):
    client = api
    async with async_session_factory() as s:
        s.add(User(username="isol_user", password_hash=hash_password("iso1234"), status=UserStatus.active))
        await s.commit()
    token_a = await _token(client)
    note_id = await _seed_note(client, token_a)
    r_b = await client.post(LOGIN_URL, json={"username": "isol_user", "password": "iso1234"})
    assert r_b.status_code == 200
    token_b = r_b.json()["token"]
    r2 = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token_b))
    assert r2.status_code == 404


async def test_delete_case_no_cases_note_gone(api):
    """删空所有案例后笔记不再展示"""
    client = api
    token = await _token(client)
    note_id = await _seed_note(client, token)
    detail_r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    case_id = detail_r.json()["cases"][0]["id"]
    await client.delete(f"{LIST_URL}/{note_id}/cases/{case_id}", headers=_auth(token))
    # 案例删空后 note 仍存在但详情返回 404（现有语义）
    r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_notes_api.py -v`
Expected: FAIL（`/notes/save` 仍存在、字段不匹配）

- [ ] **Step 3: 重写 `backend/app/routers/notes.py`**

```python
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db import get_db
from app.models.user import User
from app.schemas.note import (
    NoteDetailResponse,
    NoteListResponse,
)
from app.services import note_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/v1/notes", tags=["notes"])


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

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_notes_api.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/notes.py backend/tests/test_notes_api.py
git commit -m "refactor(notes): 删除 POST /notes/save，列表/详情/删除适配 8 字段"
```

---

## Task 8: 纠错成功后自动触发笔记保存

**Files:**
- Modify: `backend/app/routers/messages.py`
- Modify: `backend/app/services/correction_service.py`
- Test: `backend/tests/test_messages_api.py`

- [ ] **Step 1: 新增测试 `backend/tests/test_messages_api.py`**

追加到文件末尾：

```python
async def test_post_messages_triggers_auto_note_save(api):
    """纠错成功且 has_errors=true → 后台自动生成笔记"""
    client, mock = api
    token = await _token(client)
    r = await client.post(POST_URL, json={"content": "Yesterday I go to the park"}, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["assistant_message"]["report"]["has_errors"] is True

    # 后台任务在 ASGI 同步请求内完成（BackgroundTasks 在响应后执行）
    from sqlalchemy import select

    from app.db import async_session_factory
    from app.models.note import Note

    async with async_session_factory() as s:
        notes = (await s.execute(select(Note))).scalars().all()
        assert len(notes) >= 1
        note = notes[0]
        assert note.user_id is not None
        assert note.knowledge_point != ""
        assert note.rule_title != ""


async def test_post_messages_no_error_no_note(api):
    """has_errors=false → 不触发笔记保存"""
    client, mock = api
    token = await _token(client)
    mock.responder = lambda msgs: '{"has_errors":false,"errors":[],"rewrite":null}'
    r = await client.post(POST_URL, json={"content": "perfect english"}, headers=_auth(token))
    assert r.status_code == 200
    from sqlalchemy import select

    from app.db import async_session_factory
    from app.models.note import Note

    async with async_session_factory() as s:
        notes = (await s.execute(select(Note))).scalars().all()
        assert len(notes) == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_messages_api.py::test_post_messages_triggers_auto_note_save -v`
Expected: FAIL（无笔记生成）

- [ ] **Step 3: 修改 `backend/app/services/correction_service.py`**

新增导入与后台任务函数：

```python
import logging
...
from app.services import note_service

logger = logging.getLogger(__name__)


async def _run_note_save_async(
    user_id: uuid.UUID,
    source_message_id: uuid.UUID | None,
    source_text: str,
    polished_sentence: str,
    errors: list[dict],
    llm_client: LLMClient,
):
    from app.db import async_session_factory

    try:
        async with async_session_factory() as session:
            await note_service.save_notes(
                session,
                user_id,
                source_message_id,
                source_text,
                polished_sentence,
                errors,
                llm_client,
            )
    except Exception:
        logger.exception("自动保存笔记失败")
```

- [ ] **Step 4: 修改 `backend/app/routers/messages.py` 自动触发**

```python
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.schemas.correction import (
    HistoryResponse,
    SubmitRequest,
    SubmitResponse,
)
from app.services import correction_service
from app.services.auth_service import get_current_user
from app.services.llm_client import LLMClient, get_llm_client

router = APIRouter(prefix="/api/v1", tags=["messages"])


@router.post("/messages", response_model=SubmitResponse, status_code=200)
async def submit_message(
    payload: SubmitRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    user_out, ai_out = await correction_service.submit_message(
        session, user.id, payload.content, llm_client
    )
    report = ai_out.report or {}
    if report.get("has_errors"):
        rewrite = report.get("rewrite") or {}
        polished = (rewrite.get("minimal") or {}).get("text") or ""
        if polished:
            background_tasks.add_task(
                correction_service._run_note_save_async,
                user.id,
                ai_out.id,
                payload.content,
                polished,
                report.get("errors", []),
                llm_client,
            )
    return SubmitResponse(user_message=user_out, assistant_message=ai_out)


@router.get("/messages", response_model=HistoryResponse)
async def get_messages(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    msgs = await correction_service.list_messages(session, user.id)
    return HistoryResponse(messages=msgs)
```

> **关键点**：`ai_out.id` 即报告的 `ai_msg.id`（`correction_service.submit_message` 返回的 assistant message），作为 `source_message_id` 溯源。`polished_sentence` 取 `report.structure.rewrite.minimal.text`。`has_errors=false` 或 `rewrite.minimal` 缺失（`polished` 空）时不触发。

- [ ] **Step 5: 运行新增测试确认通过**

Run: `pytest tests/test_messages_api.py::test_post_messages_triggers_auto_note_save tests/test_messages_api.py::test_post_messages_no_error_no_note -v`
Expected: PASS

- [ ] **Step 6: 运行完整消息测试确认无回归**

Run: `pytest tests/test_messages_api.py -v`
Expected: 全部 PASS（含原 T-C-01~11）

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/correction_service.py backend/app/routers/messages.py backend/tests/test_messages_api.py
git commit -m "feat(notes): 纠错成功后后台自动触发笔记保存"
```

---

## Task 9: 后端全量回归

**Files:**
- 无（仅运行测试）

- [ ] **Step 1: 运行全部后端测试**

Run: `pytest -v`
Expected: 全部 PASS

- [ ] **Step 2: 提交（若有未提交变更）**

```bash
git status
git add -A
git commit -m "chore: 后端全量回归通过"
```
（若无变更则跳过）

---

## Task 10: 前端 — 移除「记笔记」交互

**Files:**
- Modify: `web/src/api/notes.ts`
- Modify: `web/src/store/conversation.tsx`
- Modify: `web/src/store/conversation-context.ts`
- Modify: `web/src/components/correction/CorrectionReportCard.tsx`
- Modify: `web/src/components/correction/ErrorCard.tsx`
- Test: `npm run build` + `npm run lint`

- [ ] **Step 1: 更新 `web/src/api/notes.ts`**

删除 `saveNote`/`NoteSaveAccepted`/`NoteExample`/`NoteCaseItem`（旧字段），更新类型：

```typescript
import { http } from './client'

export interface NoteListItem {
  id: string
  rule_title: string
  knowledge_point: string
  case_count: number
  updated_at: string
}

export interface NoteListResponse {
  notes: NoteListItem[]
}

export interface NoteCaseItem {
  id: string
  original_sentence: string
  polished_sentence: string
  change_details: string
  error_root: string
  created_at: string
}

export interface NoteDetailResponse {
  id: string
  rule_title: string
  knowledge_point: string
  warning: string
  alternatives: string[]
  feynman_question: string
  cases: NoteCaseItem[]
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

- [ ] **Step 2: 更新 `web/src/store/conversation-context.ts`**

删除 `saveNote` 定义及 `ErrorBlock` import：

```typescript
import { createContext, useContext } from 'react'

import type { Message } from '@/api/messages'

export interface ConversationState {
  messages: Message[]
  pending: boolean
  error: string | null
  sessionExpired: boolean
  load: () => Promise<void>
  send: (content: string) => Promise<boolean>
  retry: (tempId: string, content: string) => Promise<boolean>
  relogin: () => void
}

export const ConversationContext = createContext<ConversationState | null>(null)

export function useConversation(): ConversationState {
  const ctx = useContext(ConversationContext)
  if (!ctx) throw new Error('useConversation must be used within ConversationProvider')
  return ctx
}
```

- [ ] **Step 3: 更新 `web/src/store/conversation.tsx`**

删除 `saveNote` useCallback、`notesApi` import、`ErrorBlock` import、`saveNote` 从 value 移除：

```tsx
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useNavigate } from 'react-router-dom'

import * as messagesApi from '@/api/messages'
import { ApiError } from '@/api/client'
import { useAuth } from '@/store/auth-context'
import { ConversationContext } from '@/store/conversation-context'

export function ConversationProvider({ children }: { children: ReactNode }) {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [messages, setMessages] = useState<messagesApi.Message[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionExpired, setSessionExpired] = useState(false)
  const mounted = useRef(true)
  const tempIdRef = useRef(0)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const load = useCallback(async () => {
    try {
      const data = await messagesApi.fetchMessages()
      if (mounted.current) setMessages(data)
    } catch {
      // 历史加载失败：保持空态，发送时重试
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const submit = useCallback(
    async (tempId: string, content: string): Promise<boolean> => {
      setPending(true)
      setError(null)
      setSessionExpired(false)
      try {
        const result = await messagesApi.submitMessage(content)
        if (mounted.current) {
          setMessages((prev) => [
            ...prev.filter((m) => m.id !== tempId),
            result.user_message,
            result.assistant_message,
          ])
        }
        return true
      } catch (err) {
        if (mounted.current) {
          if (err instanceof ApiError && err.status === 401) {
            setSessionExpired(true)
            setError('会话已过期，请重新登录')
          } else {
            setError(err instanceof ApiError ? err.message : '请求失败，请重试')
          }
        }
        return false
      } finally {
        if (mounted.current) setPending(false)
      }
    },
    [],
  )

  const send = useCallback(
    async (content: string): Promise<boolean> => {
      tempIdRef.current += 1
      const tempId = `tmp-${tempIdRef.current}`
      const temp: messagesApi.Message = {
        id: tempId,
        role: 'user',
        type: 'correction',
        content,
        report: null,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, temp])
      return submit(tempId, content)
    },
    [submit],
  )

  const retry = useCallback(
    async (tempId: string, content: string): Promise<boolean> => {
      return submit(tempId, content)
    },
    [submit],
  )

  const relogin = useCallback(async () => {
    await logout()
    navigate('/login', { replace: true })
  }, [logout, navigate])

  const value = useMemo(
    () => ({ messages, pending, error, sessionExpired, load, send, retry, relogin }),
    [messages, pending, error, sessionExpired, load, send, retry, relogin],
  )
  return <ConversationContext.Provider value={value}>{children}</ConversationContext.Provider>
}
```

- [ ] **Step 4: 更新 `web/src/components/correction/CorrectionReportCard.tsx`**

删除 `saveNote`、`batchState`、`errorStates`、`toast`、`handleSaveOne`、`handleSaveAll` 逻辑及「全部记笔记」按钮：

```tsx
import type { CorrectionReport } from '@/api/messages'
import ErrorCard from '@/components/correction/ErrorCard'
import RewriteSection from '@/components/correction/RewriteSection'

interface Props {
  report: CorrectionReport
}

export default function CorrectionReportCard({ report }: Props) {
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
              <ErrorCard key={`${i}-${e.fragment}`} error={e} />
            ))}
          </div>
        </div>
        {report.rewrite && (
          <div className="mt-2 rounded-lg border border-[#dee2e6] p-3">
            <p className="mb-2 text-sm font-semibold text-[#343a40]">改写</p>
            <RewriteSection rewrite={report.rewrite} />
          </div>
        )}
      </div>
    </div>
  )
}
```

> 注意 `Props` 从 `{ report, message, sourceText }` 改为 `{ report }`——`message`/`sourceText` 不再需要。需检查调用处（`MessageList.tsx`）同步。

- [ ] **Step 5: 更新 `web/src/components/correction/ErrorCard.tsx`**

删除 `onSave`/`state`：

```tsx
import type { ErrorBlock } from '@/api/messages'

interface Props {
  error: ErrorBlock
}

export default function ErrorCard({ error }: Props) {
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
      <div className="mt-1">
        <p className="text-sm font-medium text-[#2b8a3e]">✅ {error.correction}</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: 检查 `MessageList.tsx` 调用处**

Run: `grep -n "CorrectionReportCard" web/src/components/correction/MessageList.tsx`
检查 `<CorrectionReportCard report={...} message={...} sourceText={...} />` 调用，改为 `<CorrectionReportCard report={...} />`。

- [ ] **Step 7: 构建验证**

Run: `source ~/.nvm/nvm.sh && nvm use 24 && npm run build`
Expected: `tsc -b && vite build` 成功，无类型错误

- [ ] **Step 8: Lint**

Run: `npm run lint`
Expected: 无错误

- [ ] **Step 9: 提交**

```bash
git add web/src
git commit -m "refactor(correction): 移除手动记笔记按钮，适配自动保存"
```

---

## Task 11: 前端 — 笔记页展示 8 字段

**Files:**
- Modify: `web/src/components/notes/NoteCard.tsx`
- Modify: `web/src/components/notes/NoteCaseItem.tsx`
- Modify: `web/src/pages/NotesPage.tsx`
- Test: `npm run build` + `npm run lint`

- [ ] **Step 1: 更新 `web/src/components/notes/NoteCaseItem.tsx`**

```tsx
import { useState } from 'react'

import type { NoteCaseItem } from '@/api/notes'
import { Button } from '@/components/ui/button'

interface Props {
  caseItem: NoteCaseItem
  noteId: string
  onDeleted: (caseId: string) => Promise<boolean>
}

export default function NoteCaseItem({ caseItem, onDeleted }: Props) {
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)

  async function handleDelete() {
    setDeleting(true)
    const ok = await onDeleted(caseItem.id)
    if (!ok) {
      setDeleting(false)
      setConfirming(false)
    }
  }

  return (
    <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-[#fff5f5] px-2 py-0.5 text-xs text-[#c92a2a]">
          {caseItem.original_sentence} ❌
        </span>
        <span className="text-[#adb5bd]">→</span>
        <span className="rounded bg-[#e6fcf5] px-2 py-0.5 text-xs text-[#2b8a3e]">
          {caseItem.polished_sentence} ✅
        </span>
      </div>
      <p className="mt-1.5 text-xs text-[#495057]">
        <span className="text-[#868e96]">修改明细：</span>
        {caseItem.change_details}
      </p>
      <p className="mt-0.5 text-xs text-[#868e96]">
        根源：{caseItem.error_root}
      </p>
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

- [ ] **Step 2: 更新 `web/src/components/notes/NoteCard.tsx`**

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
  const [caseCount, setCaseCount] = useState(note.case_count)

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

  async function handleCaseDeleted(caseId: string): Promise<boolean> {
    try {
      await deleteNoteCase(note.id, caseId)
      if (detail) {
        const newCases = detail.cases.filter((c) => c.id !== caseId)
        if (newCases.length === 0) {
          onNoteDeleted(note.id)
        } else {
          setDetail({ ...detail, cases: newCases })
          setCaseCount((prev) => prev - 1)
        }
      }
      return true
    } catch {
      return false
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
          <p className="mt-0.5 line-clamp-1 text-xs text-[#868e96]">{note.knowledge_point}</p>
          <p className="mt-1 text-xs text-[#adb5bd]">
            {caseCount} 个案例 · 最近更新 {new Date(note.updated_at).toLocaleDateString()}
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
              <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
                <p className="mb-1 text-sm font-semibold text-[#343a40]">📌 核心知识点</p>
                <p className="text-sm text-[#495057]">{detail.knowledge_point}</p>
              </div>

              <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
                <p className="mb-1 text-sm font-semibold text-[#343a40]">⚠️ 个人易错警示</p>
                <p className="text-sm text-[#495057]">{detail.warning}</p>
              </div>

              {detail.alternatives.length > 0 && (
                <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
                  <p className="mb-2 text-sm font-semibold text-[#343a40]">💼 职场同义备选</p>
                  <div className="space-y-1.5">
                    {detail.alternatives.map((alt, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm">
                        <span className="text-[#0ca678]">•</span>
                        <span className="text-[#212529]">{alt}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
                <p className="mb-1 text-sm font-semibold text-[#343a40]">❓ 费曼自测</p>
                <p className="text-sm text-[#495057]">{detail.feynman_question}</p>
              </div>

              {detail.cases.length > 0 && (
                <p className="pt-1 text-sm font-semibold text-[#343a40]">📝 我的错误</p>
              )}
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

- [ ] **Step 3: 更新 `web/src/pages/NotesPage.tsx` 空态文案**

`NotesPage.tsx` 第 52 行按钮文案改为：

```tsx
去纠错页写一段英文，AI 会自动为你沉淀笔记
```

- [ ] **Step 4: 构建验证**

Run: `source ~/.nvm/nvm.sh && nvm use 24 && npm run build`
Expected: `tsc -b && vite build` 成功

- [ ] **Step 5: Lint**

Run: `npm run lint`
Expected: 无错误

- [ ] **Step 6: 提交**

```bash
git add web/src
git commit -m "feat(notes): 笔记页展示 8 字段（规则级 + 案例级）"
```

---

## Task 12: E2E 回归

**Files:**
- 无（运行 Playwright）

- [ ] **Step 1: 确保 db 运行**

Run: `docker compose up -d db`

- [ ] **Step 2: 运行 E2E**

Run: `source ~/.nvm/nvm.sh && nvm use 24 && npm run test:e2e`
Expected: 通过（登录走查不受影响）

> 注意：`playwright.config.ts` 自动起后端（`LLM_MODE=mock`）。mock 的笔记响应已更新为 8 字段（Task 5），自动保存不会破坏 E2E。

- [ ] **Step 3: 提交（若有变更）**

```bash
git status
```
（一般无变更，跳过）

---

## 自审检查

- **Spec 覆盖**：8 字段模型（Task 1-3）✓ · LLM 8 字段 prompt + 分组（Task 4-5）✓ · 个人化入库 + 同用户复用（Task 6）✓ · 删 `/notes/save`（Task 7）✓ · 自动触发（Task 8）✓ · 前端移除按钮（Task 10）✓ · 前端 8 字段展示（Task 11）✓ · 数据迁移（Task 2）✓ · 测试（Task 3/6/7/8 内嵌 + Task 9/12 回归）✓
- **Placeholder 扫描**：无 TBD/TODO；所有代码完整给出。
- **类型一致性**：`save_notes` 签名 `(session, user_id, source_message_id, source_text, polished_sentence, errors, llm_client)` 在 Task 6 实现、Task 8 调用处一致。`NoteRuleResult`/`NoteCaseItem`/`NoteDetailResponse`/`NoteListItem` 在 Task 3 schema 与 Task 6 服务、Task 7 路由、Task 10-11 前端类型间一致。`_run_note_save_async` 在 Task 8 定义与调用一致。`error_root`/`change_details`/`original_sentence`/`polished_sentence` 字段名全局一致。
