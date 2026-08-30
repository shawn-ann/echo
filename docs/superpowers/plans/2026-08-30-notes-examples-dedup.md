# 笔记示例与错误案例去重实现计划（notes-examples-dedup）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解决笔记案例重复引用问题——新增 AI 通用示例（examples），错误案例数据源从 LLM 自由生成的 example 字符串改为结构化 fragment + correction（透传自纠错报告），用 DB 唯一约束从根上消除重复。

**Architecture:** `notes` 表新增 `examples` JSONB 列（3 个 AI 生成通用示例）；`note_cases` 表 `example` 列改造为 `fragment` 并新增 `correction` 列，加唯一约束 `(note_id, user_id, source_text, fragment)`；LLM 输出契约改为 `references`（仅 fragment 数组，透传不改写），correction 由后端从 errors 匹配；保存前先查重。存量数据清空重建。

**Tech Stack:** Python FastAPI + SQLAlchemy(async) + Alembic + Pydantic；React 19 + TypeScript + TailwindCSS

**依赖文档:** `docs/superpowers/specs/2026-08-30-notes-examples-dedup-design.md`

---

### Task 1: Note/NoteCase 模型变更 + 迁移

**Files:**
- Modify: `backend/app/models/note.py`
- Test: `backend/tests/test_models_note.py`

- [ ] **Step 1: 更新模型测试（examples 默认 + fragment/correction + 唯一约束）**

Rewrite `backend/tests/test_models_note.py` to:

```python
import uuid

from sqlalchemy import select

from app.db import async_session_factory
from app.models.note import Note, NoteCase
from app.models.user import User


async def _demo_user_id() -> uuid.UUID:
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        return user.id


async def test_create_note_with_examples():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(
            rule_title="第三人称单数主谓一致",
            description="一般现在时中，第三人称单数主语动词加 -s/-es",
            examples=[
                {"text": "She plays tennis.", "note": "play → plays"},
                {"text": "He goes to work.", "note": "go → goes"},
            ],
        )
        s.add(note)
        await s.flush()
        case = NoteCase(
            note_id=note.id,
            user_id=uid,
            fragment="She have",
            correction="She has",
            source_text="She have many book",
        )
        s.add(case)
        await s.commit()
        assert note.id is not None
        assert note.examples == [
            {"text": "She plays tennis.", "note": "play → plays"},
            {"text": "He goes to work.", "note": "go → goes"},
        ]
        assert case.fragment == "She have"
        assert case.correction == "She has"


async def test_note_examples_default_empty():
    async with async_session_factory() as s:
        note = Note(rule_title="测试规则", description="测试")
        s.add(note)
        await s.commit()
        assert note.examples == []


async def test_note_case_unique_dedup():
    """同 (note, user, source_text, fragment) 唯一：重复插入抛 IntegrityError"""
    from sqlalchemy.exc import IntegrityError

    import pytest

    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(rule_title="唯一约束规则", description="测试")
        s.add(note)
        await s.flush()
        s.add(NoteCase(note_id=note.id, user_id=uid, fragment="She have", correction="She has", source_text="src"))
        await s.commit()
    async with async_session_factory() as s:
        with pytest.raises(IntegrityError):
            s.add(NoteCase(note_id=note.id, user_id=uid, fragment="She have", correction="She has", source_text="src"))
            await s.commit()


async def test_note_case_cascade_delete_note():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(rule_title="级联规则", description="测试")
        s.add(note)
        await s.flush()
        case_id = uuid.uuid4()
        s.add(NoteCase(id=case_id, note_id=note.id, user_id=uid, fragment="f", correction="c", source_text="src"))
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
        note = Note(rule_title="消息规则", description="测试")
        s.add(note)
        await s.flush()
        case = NoteCase(note_id=note.id, user_id=uid, fragment="f", correction="c", source_text="src", source_message_id=msg.id)
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
Expected: FAIL（Note.examples 不存在、NoteCase 无 fragment/correction、无唯一约束）

- [ ] **Step 3: 更新 Note/NoteCase 模型**

Rewrite `backend/app/models/note.py` to:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    examples: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
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
            "note_id", "user_id", "source_text", "fragment",
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
    fragment: Mapped[str] = mapped_column(Text, nullable=False)
    correction: Mapped[str] = mapped_column(Text, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", name="fk_note_cases_message_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_models_note.py -v`
Expected: 5 PASS

- [ ] **Step 5: 生成迁移**

Run: `cd backend && source .venv/bin/activate && alembic revision --autogenerate -m "add note examples and refactor note_cases"`

- [ ] **Step 6: 检查并调整迁移脚本**

打开生成的迁移文件，确认 `upgrade()`：
1. `notes` 表新增 `examples` JSONB 列（`server_default` 为 `'[]'` 或 Python 侧 default——若 autogenerate 未生成 server_default，手动加 `sa.text("'[]'::jsonb")`）
2. `note_cases` 表：`example` 列改名 `fragment` + 新增 `correction` 列 + 新增 `uq_note_cases_dedup` 唯一约束
3. 若 autogenerate 因已有数据无法加约束，先 `TRUNCATE note_cases` 再加约束

如果 autogenerate 生成的迁移不理想（列改名/约束顺序），手动重写迁移脚本为：

```python
def upgrade() -> None:
    # notes 新增 examples
    op.add_column('notes', sa.Column('examples', sa.dialects.postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    # note_cases 清空（存量 example 清空重建，用户已确认）
    op.execute("TRUNCATE TABLE note_cases")
    # example 改名 fragment
    op.alter_column('note_cases', 'example', new_column_name='fragment')
    # 新增 correction 列
    op.add_column('note_cases', sa.Column('correction', sa.Text(), nullable=False, server_default=''))
    op.alter_column('note_cases', 'correction', server_default=None)
    # 新增唯一约束
    op.create_unique_constraint('uq_note_cases_dedup', 'note_cases', ['note_id', 'user_id', 'source_text', 'fragment'])


def downgrade() -> None:
    op.drop_constraint('uq_note_cases_dedup', 'note_cases', type_='unique')
    op.drop_column('note_cases', 'correction')
    op.alter_column('note_cases', 'fragment', new_column_name='example')
    op.drop_column('notes', 'examples')
```

- [ ] **Step 7: 应用迁移验证**

Run: `cd backend && source .venv/bin/activate && alembic upgrade head`
Expected: 无错误

- [ ] **Step 8: 运行全量测试确认无回归**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: 通过。注意：`test_note_service.py` / `test_notes_api.py` 中引用旧 `example` 字段的用例可能失败——**这是预期的**（Task 3/4 会更新它们）。本步骤只需确认 `test_models_note.py` 通过、且除 notes 相关测试外无其他回归。

- [ ] **Step 9: 提交**

```bash
git add backend/app/models/note.py backend/alembic/versions/ backend/tests/test_models_note.py
git commit -m "feat(notes): Note 加 examples + NoteCase 重构为 fragment/correction + 唯一约束"
```

---

### Task 2: Pydantic Schema 更新

**Files:**
- Modify: `backend/app/schemas/note.py`
- Test: `backend/tests/test_notes_api.py`（先更新以暴露 schema 变更）

- [ ] **Step 1: 更新 NoteRuleResult（LLM 输出）**

Modify `backend/app/schemas/note.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.correction import ErrorBlock


class SaveNoteRequest(BaseModel):
    message_id: uuid.UUID
    source_text: str = Field(min_length=1, max_length=2000)
    errors: list[ErrorBlock] = Field(min_length=1)


class NoteExample(BaseModel):
    text: str
    note: str


class NoteRuleResult(BaseModel):
    rule_title: str
    description: str
    examples: list[NoteExample] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


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
    fragment: str
    correction: str
    source_text: str
    created_at: datetime


class NoteDetailResponse(BaseModel):
    id: uuid.UUID
    rule_title: str
    description: str
    examples: list[NoteExample]
    cases: list[NoteCaseItem]
```

- [ ] **Step 2: 更新 note_prompt 测试**

Rewrite `backend/tests/test_note_prompt.py` to:

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


def test_system_prompt_mentions_references_passthrough():
    prompt = build_note_system_prompt(existing_rules=[])
    assert "references" in prompt
    assert "原样选取" in prompt  # 透传指令


def test_user_content_contains_source_and_errors():
    content = build_note_user_content(
        source_text="I interested in read",
        errors=[{"error_type": "动词形式", "fragment": "interested in read", "explanation": "介词后加 ing", "correction": "interested in reading"}],
    )
    assert "I interested in read" in content
    assert "interested in read" in content
    assert "interested in reading" in content
```

- [ ] **Step 3: 更新 note_prompt.py 输出契约**

Rewrite `backend/app/prompts/note_prompt.py` to:

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
      "rule_title": "第三人称单数主谓一致",
      "description": "一般现在时中，主语为第三人称单数时，实义动词加 -s/-es，助动词用 has...",
      "examples": [
        {{"text": "She plays tennis every day.", "note": "play → plays"}},
        {{"text": "He goes to work by bus.", "note": "go → goes"}}
      ],
      "references": ["She have", "she go"]
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
若新错误的规则与已有规则库中某条语义相同，必须原样返回那条的 rule_title（不得修改、不得编造）。

## references 生成
- references 是字符串数组，每个元素是**原样选取自输入「错误列表」中 fragment 字段**的文本
- 一条规则可对应多个 references（如 She have / she go 同属主谓一致）
- **不得改写** fragment 文本，**不得补充**不在错误列表中的文本

## examples 要求
- 给出 3 个**正确用法**的完整英文句子，不参考用户错误
- 每条含 text（英文句子）和 note（简短中文说明，如 play → plays）
- 覆盖该规则的典型场景

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

- [ ] **Step 4: 运行 prompt 测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_note_prompt.py -v`
Expected: 4 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/note.py backend/app/prompts/note_prompt.py backend/tests/test_note_prompt.py
git commit -m "feat(notes): schema/prompt 契约更新——examples + references"
```

---

### Task 3: note_service 保存逻辑（examples 存储 + correction 匹配 + 先查重）

**Files:**
- Modify: `backend/app/services/note_service.py`
- Modify: `backend/tests/test_note_service.py`

- [ ] **Step 1: 更新 service 测试（保存逻辑新契约）**

Rewrite `backend/tests/test_note_service.py` to:

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
            "rule_title": "第三人称单数主谓一致",
            "description": "一般现在时中，第三人称单数主语动词加 -s/-es",
            "examples": [
                {"text": "She plays tennis.", "note": "play → plays"},
                {"text": "He goes to work.", "note": "go → goes"},
                {"text": "It rains a lot.", "note": "rain → rains"},
            ],
            "references": ["She have", "she go"],
        }]
    }, ensure_ascii=False)


async def test_save_new_rule_creates_note_with_examples_and_cases():
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She have", "explanation": "x", "correction": "She has"},
        {"error_type": "主谓不一致", "fragment": "she go", "explanation": "x", "correction": "she goes"},
    ]
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        result = await save_notes(s, uid, None, "She have many book and she go to school", errors, mock)
        assert len(result) == 2
        assert all(r.is_new for r in result)
        assert all(r.rule_title == "第三人称单数主谓一致" for r in result)

    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "第三人称单数主谓一致"))).scalar_one()
        assert len(note.examples) == 3
        assert note.examples[0]["text"] == "She plays tennis."
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 2
        by_fragment = {c.fragment: c.correction for c in cases}
        assert by_fragment["She have"] == "She has"
        assert by_fragment["she go"] == "she goes"


def _mock_responder_existing_rule(msgs):
    return json.dumps({
        "results": [{
            "rule_title": "第三人称单数主谓一致",
            "description": "（后端忽略，已有规则）",
            "examples": [{"text": "ignored", "note": "ignored"}],
            "references": ["She have"],
        }]
    }, ensure_ascii=False)


async def test_save_existing_rule_ignores_examples_and_appends_case():
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She have", "explanation": "x", "correction": "She has"},
        {"error_type": "主谓不一致", "fragment": "she go", "explanation": "x", "correction": "she goes"},
    ]
    # 先新建规则
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "She have many book and she go to school", errors, mock)
    # 再用已有规则保存（新原文，references 不同）
    async with async_session_factory() as s:
        mock2 = MockLLMClient(responder=_mock_responder_existing_rule)
        result = await save_notes(s, uid, None, "He have a car", [{"error_type": "主谓不一致", "fragment": "He have", "explanation": "x", "correction": "He has"}], mock2)
        assert len(result) == 1
        assert result[0].is_new is False
    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "第三人称单数主谓一致"))).scalar_one()
        assert len(note.examples) == 3  # 未被覆盖（忽略 LLM 的 examples）
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 3  # 2 (首建) + 1 (追加)


async def test_save_dedup_same_source_and_fragment():
    """同一原文+同一错误段重复保存：只保留一条（先查重 + 唯一约束兜底）"""
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She have", "explanation": "x", "correction": "She has"},
        {"error_type": "主谓不一致", "fragment": "she go", "explanation": "x", "correction": "she goes"},
    ]
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        # 保存两次同一原文同一错误
        await save_notes(s, uid, None, "She have many book and she go to school", errors, mock)
        result = await save_notes(s, uid, None, "She have many book and she go to school", errors, mock)
        assert len(result) == 0  # 全部重复，跳过
    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "第三人称单数主谓一致"))).scalar_one()
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 2  # 仍只有 2 条


async def test_save_reference_without_matching_error_skipped():
    """LLM references 含不在 errors 中的 fragment：静默跳过"""
    uid = await _demo_user_id()
    errors = [{"error_type": "主谓不一致", "fragment": "She have", "explanation": "x", "correction": "She has"}]
    responder = lambda msgs: json.dumps({
        "results": [{
            "rule_title": "测试规则",
            "description": "d",
            "examples": [],
            "references": ["She have", "not in errors"],
        }]
    }, ensure_ascii=False)
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=responder)
        result = await save_notes(s, uid, None, "She have many book", errors, mock)
        assert len(result) == 1  # 只有 She have 匹配到 correction
    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "测试规则"))).scalar_one()
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 1


def _mock_responder_two_rules(msgs):
    return json.dumps({
        "results": [
            {"rule_title": "主谓一致规则", "description": "d1", "examples": [], "references": ["She have"]},
            {"rule_title": "单复数规则", "description": "d2", "examples": [], "references": ["many book"]},
        ]
    }, ensure_ascii=False)


async def test_save_batch_creates_multiple_rules():
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She have", "explanation": "x", "correction": "She has"},
        {"error_type": "单复数错误", "fragment": "many book", "explanation": "x", "correction": "many books"},
    ]
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_two_rules)
        result = await save_notes(s, uid, None, "She have many book", errors, mock)
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
Expected: FAIL（save_notes 仍用旧 example 逻辑）

- [ ] **Step 3: 更新 save_notes 逻辑**

Modify `backend/app/services/note_service.py` 的 `save_notes` 函数（以及 `_call_llm_and_parse` 无需改，schema 已变）。替换 `save_notes` 为：

```python
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

    # source_message_id 仅作溯源链接；若消息不存在则置空，避免外键违约
    if source_message_id is not None and (await session.get(Message, source_message_id)) is None:
        source_message_id = None

    # correction 由后端从 errors 匹配（取第一个匹配）
    errors_by_fragment = {e["fragment"]: e["correction"] for e in errors}

    saved: list[SavedNoteItem] = []
    for result in parsed.results:
        note = (
            await session.execute(select(Note).where(Note.rule_title == result.rule_title))
        ).scalars().first()
        if note is not None:
            is_new = False  # 已有规则：忽略 examples
        else:
            note = Note(
                rule_title=result.rule_title,
                description=result.description,
                examples=[ex.model_dump() for ex in result.examples],
            )
            session.add(note)
            await session.flush()
            is_new = True

        for fragment in result.references:
            correction = errors_by_fragment.get(fragment)
            if not correction:
                continue  # 防御：LLM 归组了不在 errors 中的文本

            # 先查重：同 (note, user, source_text, fragment) 已存在则跳过
            existing_case = (
                await session.execute(
                    select(NoteCase.id).where(
                        NoteCase.note_id == note.id,
                        NoteCase.user_id == user_id,
                        NoteCase.source_text == source_text,
                        NoteCase.fragment == fragment,
                    )
                )
            ).scalars().first()
            if existing_case is not None:
                continue  # 重复案例，静默跳过

            case = NoteCase(
                note_id=note.id,
                user_id=user_id,
                fragment=fragment,
                correction=correction,
                source_text=source_text,
                source_message_id=source_message_id,
            )
            session.add(case)
            await session.flush()
            note.updated_at = datetime.now(timezone.utc)
            saved.append(SavedNoteItem(note_id=note.id, rule_title=note.rule_title, is_new=is_new, case_id=case.id))

    await session.commit()
    return saved
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_note_service.py -v`
Expected: 11 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/note_service.py backend/tests/test_note_service.py
git commit -m "feat(notes): save_notes 存 examples + correction 匹配 + 先查重去重"
```

---

### Task 4: note_service 查询逻辑（examples 返回）+ API 测试更新

**Files:**
- Modify: `backend/app/services/note_service.py`（get_note_detail）
- Modify: `backend/tests/test_notes_api.py`

- [ ] **Step 1: 更新 API 测试（新契约）**

Rewrite `backend/tests/test_notes_api.py` to:

```python
import json

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services.llm_client import MockLLMClient, get_llm_client

POST_URL = "/api/v1/notes/save"
LIST_URL = "/api/v1/notes"
LOGIN_URL = "/api/v1/auth/login"

_ERROR = {"error_type": "主谓不一致", "fragment": "She have", "explanation": "主语 she 第三人称单数", "correction": "She has"}


@pytest_asyncio.fixture
async def api():
    app = create_app()
    mock = MockLLMClient(responder=lambda msgs: json.dumps({
        "results": [{
            "rule_title": "第三人称单数主谓一致",
            "description": "一般现在时中，第三人称单数主语动词加 -s/-es",
            "examples": [
                {"text": "She plays tennis.", "note": "play → plays"},
                {"text": "He goes to work.", "note": "go → goes"},
                {"text": "It rains a lot.", "note": "rain → rains"},
            ],
            "references": ["She have"],
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
        "source_text": "She have many book",
        "errors": [_ERROR],
    }, headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert len(data["saved_notes"]) == 1
    assert data["saved_notes"][0]["is_new"] is True
    assert data["saved_notes"][0]["rule_title"] == "第三人称单数主谓一致"


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


async def test_get_note_detail_with_examples_and_cases(api):
    client = api
    token = await _token(client)
    save_r = await client.post(POST_URL, json={"message_id": "00000000-0000-0000-0000-000000000000", "source_text": "src", "errors": [_ERROR]}, headers=_auth(token))
    note_id = save_r.json()["saved_notes"][0]["note_id"]
    r = await client.get(f"{LIST_URL}/{note_id}", headers=_auth(token))
    assert r.status_code == 200
    detail = r.json()
    assert len(detail["examples"]) == 3
    assert detail["examples"][0]["text"] == "She plays tennis."
    assert len(detail["cases"]) == 1
    assert detail["cases"][0]["fragment"] == "She have"
    assert detail["cases"][0]["correction"] == "She has"


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
Expected: FAIL（get_note_detail 未返回 examples；case 字段不匹配）

- [ ] **Step 3: 更新 get_note_detail 返回 examples**

Modify `backend/app/services/note_service.py` 的 `get_note_detail`：

```python
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
        examples=[NoteExample.model_validate(ex) for ex in note.examples],
        cases=[
            NoteCaseItem(
                id=c.id, fragment=c.fragment, correction=c.correction,
                source_text=c.source_text, created_at=c.created_at,
            )
            for c in cases
        ],
    )
```

在文件顶部 import 区追加 `NoteExample`：

```python
from app.schemas.note import (
    NoteCaseItem,
    NoteDetailResponse,
    NoteExample,
    NoteListItem,
    NoteLLMResponse,
    SavedNoteItem,
)
```

- [ ] **Step 4: 运行 API 测试确认通过**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_notes_api.py -v`
Expected: 8 PASS

- [ ] **Step 5: 运行全量后端测试确认无回归**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/note_service.py backend/tests/test_notes_api.py
git commit -m "feat(notes): get_note_detail 返回 examples + API 契约更新"
```

---

### Task 5: 前端 API 类型 + NoteCaseItem 改造 + NoteCard 示例区

**Files:**
- Modify: `web/src/api/notes.ts`
- Modify: `web/src/components/notes/NoteCaseItem.tsx`
- Modify: `web/src/components/notes/NoteCard.tsx`

- [ ] **Step 1: 更新前端 API 类型**

Modify `web/src/api/notes.ts`:

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

export interface NoteExample {
  text: string
  note: string
}

export interface NoteCaseItem {
  id: string
  fragment: string
  correction: string
  source_text: string
  created_at: string
}

export interface NoteDetailResponse {
  id: string
  rule_title: string
  description: string
  examples: NoteExample[]
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

- [ ] **Step 2: 改造 NoteCaseItem 直接用 fragment/correction**

Modify `web/src/components/notes/NoteCaseItem.tsx`:

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
          {caseItem.fragment} ❌
        </span>
        <span className="text-[#adb5bd]">→</span>
        <span className="rounded bg-[#e6fcf5] px-2 py-0.5 text-xs text-[#2b8a3e]">
          {caseItem.correction} ✅
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

- [ ] **Step 3: NoteCard 新增示例区渲染**

Modify `web/src/components/notes/NoteCard.tsx` 的展开部分。在 `detail.description` 之后插入示例区，并将「我的错误」标题放在 cases 之前。删除笔记确认逻辑保持现状（仅调整展开块结构）。最终 `expanded` 块替换为：

```tsx
      {expanded && (
        <div className="mt-3 space-y-2">
          {loading ? (
            <p className="text-sm text-[#868e96]">加载中…</p>
          ) : detail ? (
            <>
              <p className="text-sm text-[#495057]">{detail.description}</p>

              {/* AI 通用示例 */}
              {detail.examples.length > 0 && (
                <div className="rounded-lg border border-[#dee2e6] bg-white p-3">
                  <p className="mb-2 text-sm font-semibold text-[#343a40]">✨ 示例</p>
                  <div className="space-y-1.5">
                    {detail.examples.map((ex, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm">
                        <span className="text-[#0ca678]">•</span>
                        <div>
                          <span className="text-[#212529]">{ex.text}</span>
                          <span className="ml-2 text-xs text-[#868e96]">{ex.note}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 用户错误案例 */}
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
```

保留 NoteCard 的其余部分（state 声明、toggleExpand、handleCaseDeleted、handleDeleteNote、折叠态头部）不变。

- [ ] **Step 4: 运行前端 lint + build**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run lint && npm run build`
Expected: 无错误

- [ ] **Step 5: 提交**

```bash
git add web/src/api/notes.ts web/src/components/notes/NoteCaseItem.tsx web/src/components/notes/NoteCard.tsx
git commit -m "feat(notes): 前端类型更新 + NoteCaseItem 用 fragment/correction + NoteCard 示例区"
```

---

### Task 6: MockLLM 扩展 + E2E 更新 + 全量回归

**Files:**
- Modify: `backend/app/services/llm_client.py`
- Modify: `web/tests/e2e/notes.spec.ts`

- [ ] **Step 1: 更新 MockLLM 笔记保存响应**

Modify `backend/app/services/llm_client.py` 的 `_default_responder` 中笔记保存分支：

```python
    # 笔记保存请求（note_prompt 的 user content 含「## 原文」标记）
    if "## 原文" in last and "## 错误列表" in last:
        return json.dumps(
            {
                "results": [
                    {
                        "rule_title": "介词后加 -ing 形式",
                        "description": "英语中介词后接动词时需用动名词形式(-ing)而非不定式。",
                        "examples": [
                            {"text": "She is interested in reading.", "note": "介词后接动名词"},
                            {"text": "He is good at swimming.", "note": "at 后接动名词"},
                            {"text": "I am tired of waiting.", "note": "of 后接动名词"},
                        ],
                        "references": ["interested in read"],
                    }
                ]
            },
            ensure_ascii=False,
        )
```

注意：`references` 需与 mock 纠错报告的 fragment 一致。mock 纠错响应（`_default_responder` 的纠错分支）的 fragment 是 `"I go to"`。为确保 E2E 端到端通，将 mock 纠错报告的 fragment 改为 `"interested in read"`、correction 改为 `"interested in reading"`（这样保存笔记时 references 能匹配到 correction）。

Modify `backend/app/services/llm_client.py` 的纠错分支：

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
            "learnings": [
                {
                    "rule": "介词后接动词时用动名词形式（-ing）。",
                    "example": "interested in read → interested in reading",
                }
            ],
        },
        ensure_ascii=False,
    )
```

- [ ] **Step 2: 更新 E2E 测试断言**

Modify `web/tests/e2e/notes.spec.ts`：

- N-03：`介词后加 -ing 形式` 规则标题不变，断言可保留
- N-04：展开后增加示例区断言：

```typescript
test('N-04 笔记展开显示示例和案例', async ({ page }) => {
  await loginAndSubmit(page)
  await page.getByRole('button', { name: '📝 全部记笔记' }).first().click()
  await expect(page.getByText(/已记入/)).toBeVisible({ timeout: 15000 })
  await page.getByRole('link', { name: /我的笔记/ }).click()
  await expect(page).toHaveURL(/\/notes$/)
  await page.getByRole('button', { name: /介词后加 -ing 形式/ }).click()
  await expect(page.getByText('✨ 示例')).toBeVisible()
  await expect(page.getByText('She is interested in reading.')).toBeVisible()
  await expect(page.getByText(/原文/).first()).toBeVisible()
})
```

- [ ] **Step 3: 运行 E2E 测试**

前置：`docker compose up -d db` 且后端/前端未占用 8000/5173（若有残留，先 pkill）

Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run test:e2e`
Expected: 全部 PASS

- [ ] **Step 4: 全量回归**

后端：Run: `cd backend && source .venv/bin/activate && pytest -v`
前端：Run: `cd web && source ~/.nvm/nvm.sh && nvm use 24 && npm run lint && npm run build`

Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/llm_client.py web/tests/e2e/notes.spec.ts
git commit -m "test(notes): mock 更新为新契约 + E2E 断言更新"
```

---

## 验证清单

完成后执行：

- [ ] **后端**: `cd backend && source .venv/bin/activate && pytest -v` — 全部 PASS
- [ ] **前端 lint**: `cd web && npm run lint` — 无错误
- [ ] **前端 build**: `cd web && npm run build` — 无错误
- [ ] **E2E**: `cd web && npm run test:e2e` — 全部 PASS
- [ ] **手动冒烟**: 提交英文 → 全部记笔记 → 笔记详情展示示例区 + 错误区 → 重复保存同一纠错不产生重复案例 → 删除案例/笔记
