# 纠错功能实现计划（02-Correction）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现会话式纠错主页（提交英文→结构化纠错报告、可无限追问、历史持久化），后端提供 `POST/GET /api/v1/messages`，LLM 层以抽象接口 + Mock 实现（本轮不接真实 LLM）。

**Architecture:** 后端新增 `session_conversations / messages / correction_reports` 三表（`session_conversations → messages → correction_reports`，报告为独立 JSONB 对象）。LLM 层定义 `LLMClient` 协议，测试注入确定性 `MockLLMClient`；`POST /messages` 单次调用返回 intent 标记，按意图写 `correction+report` 或 `follow_up+reply` 两类消息对。前端以 React context（对齐 auth-context 模式）管理会话状态，替换占位页。

**Tech Stack:** FastAPI + SQLAlchemy(async) + Pydantic + Alembic / React 19 + Vite + Tailwind / pytest + Playwright（Mock LLM 离线测试）

**依赖文档:** `docs/tech-design/02-Correction.md`（V0.2）、`PRD/pages/02-Correction.md`（V2.5）

**参考模式:** 登录功能（`01-Login.md` V0.6 的 TDD 先例：pytest 契约测试 `T-L-*`、Playwright UI 测试 `U-L-*`）

---

### Task 1: 后端配置新增 LLM 与上下文设置

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: 修改配置类，追加 LLM 与 CONTEXT_LIMIT 字段**

在 `Settings` 类（`SESSION_TTL_DAYS` 之后）追加：

```python
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_MODE: str = ""  # ""=真实调用（需配置）; "mock"=测试/演示用确定性 Mock
    CONTEXT_LIMIT: int = 40
```

- [ ] **Step 2: 验证后端仍可启动**

Run: `cd backend && .venv/bin/python -c "from app.core.config import get_settings; s=get_settings(); print(s.CONTEXT_LIMIT, repr(s.LLM_BASE_URL))"`
Expected: `40 ''`

- [ ] **Step 3: 跑通全部现有测试确保无回归**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 23 passed（登录契约 T-L-01~10 全绿）

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat(backend): config 新增 LLM_BASE_URL/API_KEY/MODEL/MODE 与 CONTEXT_LIMIT=40"
```

---

### Task 2: LLM 客户端抽象（协议 + 生产实现 + Mock + 依赖）

**Files:**
- Create: `backend/app/services/llm_client.py`
- Test: `backend/tests/test_llm_client.py`

- [ ] **Step 1: 编写失败的测试**

创建 `backend/tests/test_llm_client.py`：

```python
import json

import pytest

from app.core.errors import AppError
from app.services.llm_client import MockLLMClient, RealLLMClient, get_llm_client


def test_mock_llm_returns_responder_output():
    mock = MockLLMClient(responder=lambda msgs: "pong")
    assert mock.complete([{"role": "user", "content": "hi"}]) == "pong"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_llm_client.py -v`
Expected: FAIL（ModuleNotFoundError: app.services.llm_client）

- [ ] **Step 3: 实现 LLM 客户端模块**

创建 `backend/app/services/llm_client.py`：

```python
import json
import re
from collections.abc import Callable
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import AppError


class LLMClient:
    async def complete(self, messages: list[dict[str, Any]]) -> str:
        raise NotImplementedError


class LLMTimeoutError(Exception):
    pass


class LLMUnavailableError(Exception):
    pass


class RealLLMClient(LLMClient):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete(self, messages: list[dict[str, Any]]) -> str:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": messages},
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError from exc


def _default_responder(messages: list[dict[str, Any]]) -> str:
    """Mock 默认响应：中文→追问；含 no-error 标记→无错误报告；其余→纠错报告。"""
    user_contents = [m["content"] for m in messages if m.get("role") == "user"]
    last = user_contents[-1] if user_contents else ""
    if re.fullmatch(r"[\u4e00-\u9fff\s，。！？、,.!?;；]*", last):
        return json.dumps(
            {"intent": "follow_up", "reply": "delicious 是极限形容词，通常不加 very。", "correction": None},
            ensure_ascii=False,
        )
    if "没有错误" in last or "no-error" in last:
        return json.dumps(
            {"intent": "correction", "correction": {"has_errors": False, "errors": [], "rewrite": None}, "reply": None},
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "intent": "correction",
            "correction": {
                "has_errors": True,
                "errors": [
                    {
                        "category": "grammar",
                        "fragment": "I go to",
                        "explanation": "yesterday 表示过去，故用过去式 went",
                        "correction": "I went to",
                    }
                ],
                "rewrite": {
                    "minimal": {"text": "Yesterday I went to the park.", "explanation": "修正时态，保留原句结构"},
                    "natural": {"text": "Yesterday I enjoyed the park.", "explanation": "用 enjoyed 更自然"},
                },
            },
            "reply": None,
        },
        ensure_ascii=False,
    )


class MockLLMClient(LLMClient):
    def __init__(self, responder: Callable[[list[dict[str, Any]]], str] | None = None) -> None:
        self.responder = responder or _default_responder
        self.calls: list[list[dict[str, Any]]] = []

    async def complete(self, messages: list[dict[str, Any]]) -> str:
        self.calls.append(messages)
        return self.responder(messages)


def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.LLM_MODE == "mock":
        return MockLLMClient()
    if not settings.LLM_BASE_URL or not settings.LLM_API_KEY:
        raise AppError(503, "LLM_SERVICE_UNAVAILABLE", "AI 服务未配置，请配置 LLM_BASE_URL/LLM_API_KEY")
    return RealLLMClient(settings.LLM_BASE_URL, settings.LLM_API_KEY, settings.LLM_MODEL)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_llm_client.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat(backend): LLM 客户端抽象（协议/生产实现/Mock/依赖注入），未配置返回 503"
```

---

### Task 3: 数据模型（session_conversations / messages / correction_reports）

**Files:**
- Create: `backend/app/models/conversation.py`
- Create: `backend/app/models/message.py`
- Create: `backend/app/models/report.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 编写失败的测试**

创建 `backend/tests/test_models_correction.py`：

```python
import pytest
from sqlalchemy import select

from app.db import async_session_factory
from app.models.conversation import SessionConversation
from app.models.message import Message, MessageRole, MessageType
from app.models.report import CorrectionReport
from app.models.user import User


async def test_models_importable_and_roundtrip():
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        conv = SessionConversation(user_id=user.id)
        s.add(conv)
        await s.flush()
        msg = Message(
            conversation_id=conv.id,
            role=MessageRole.user,
            type=MessageType.correction,
            content="hello",
        )
        s.add(msg)
        await s.flush()
        rep = CorrectionReport(message_id=msg.id, version=1, structure={"a": 1})
        s.add(rep)
        await s.flush()
        msg.report_id = rep.id
        await s.commit()

        rows = (await s.execute(select(Message))).scalars().all()
        assert len(rows) == 1
        assert rows[0].report_id == rep.id
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models_correction.py -v`
Expected: FAIL（ModuleNotFoundError: app.models.conversation）

- [ ] **Step 3: 创建三个模型文件**

创建 `backend/app/models/conversation.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SessionConversation(Base):
    __tablename__ = "session_conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

创建 `backend/app/models/message.py`：

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class MessageType(str, enum.Enum):
    correction = "correction"
    report = "report"
    follow_up = "follow_up"
    reply = "reply"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("session_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role"), nullable=False
    )
    type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type"), nullable=False
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("correction_reports.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

创建 `backend/app/models/report.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CorrectionReport(Base):
    __tablename__ = "correction_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    structure: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

修改 `backend/app/models/__init__.py`：

```python
from app.models.user import User
from app.models.session import AuthSession
from app.models.conversation import SessionConversation
from app.models.message import Message
from app.models.report import CorrectionReport

__all__ = ["User", "AuthSession", "SessionConversation", "Message", "CorrectionReport"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models_correction.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/
git commit -m "feat(backend): 新增 session_conversations/messages/correction_reports 数据模型"
```

---

### Task 4: Alembic 迁移 + 测试库 conftest 更新

**Files:**
- Create: `backend/alembic/versions/<rev>_create_conversation_message_report_tables.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: 生成迁移文件**

Run: `cd backend && .venv/bin/alembic revision -m "create conversation message and correction report tables"`
Expected: 输出 `Generating ... <rev>_create_....py`，记录 revision id 替换下方 `<REV>`。

- [ ] **Step 2: 填入迁移内容**

打开生成的 `<REV>_create_....py`，将 `down_revision` 保持不变（应为 `'1f3455c5b006'`），替换 `upgrade`/`downgrade`：

```python
def upgrade() -> None:
    op.create_table('session_conversations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('correction_reports',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('message_id', sa.Uuid(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('structure', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.Enum('user', 'assistant', name='message_role'), nullable=False),
        sa.Column('type', sa.Enum('correction', 'report', 'follow_up', 'reply', name='message_type'), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('report_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['session_conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['report_id'], ['correction_reports.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_foreign_key('fk_correction_reports_message_id', 'correction_reports', 'messages', ['message_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_correction_reports_message_id', 'correction_reports', type_='foreignkey')
    op.drop_table('messages')
    op.drop_table('correction_reports')
    op.drop_table('session_conversations')
    op.execute('DROP TYPE IF EXISTS message_role')
    op.execute('DROP TYPE IF EXISTS message_type')
```

> 文件头部需要 `from alembic import op` 与 `import sqlalchemy as sa`（`alembic revision` 模板已含）。

- [ ] **Step 3: 对开发库执行迁移并验证**

Run: `cd backend && .venv/bin/alembic upgrade head && .venv/bin/python -c "from sqlalchemy import create_engine; e=create_engine('postgresql://echo:echo@localhost:5432/echo'); print(list(e.execute(__import__('sqlalchemy').text(\"select tablename from pg_tables where schemaname='public' order by tablename\"))))"`
Expected: 输出含 `session_conversations`、`messages`、`correction_reports`

- [ ] **Step 4: 更新测试库 conftest（建表/清理/枚举类型）**

修改 `backend/tests/conftest.py`：
- `setup_db` 中 `DROP TYPE` 追加两行（`message_role`、`message_type`）
- `clean_sessions` 清理语句追加三张新表

```python
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TYPE IF EXISTS user_status"))
        await conn.execute(text("DROP TYPE IF EXISTS message_role"))
        await conn.execute(text("DROP TYPE IF EXISTS message_type"))
        await conn.run_sync(Base.metadata.create_all)
```

```python
@pytest_asyncio.fixture(autouse=True)
async def clean_sessions():
    async with async_session_factory() as session:
        await session.execute(text("TRUNCATE sessions, messages, correction_reports, session_conversations"))
        await session.commit()
    yield
```

- [ ] **Step 5: 运行全部测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 24 passed（原 23 + 模型测试 1）

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/ backend/tests/conftest.py
git commit -m "feat(backend): 迁移建三张纠错表，conftest 同步建表/清理/枚举类型"
```

---

### Task 5: Pydantic 契约（LLM 响应 + API 出入参）

**Files:**
- Create: `backend/app/schemas/correction.py`
- Test: `backend/tests/test_schemas_correction.py`

- [ ] **Step 1: 编写失败的测试**

创建 `backend/tests/test_schemas_correction.py`：

```python
import json

import pytest
from pydantic import ValidationError

from app.schemas.correction import LLMResponse, SubmitRequest


def test_llm_response_correction_valid():
    payload = {
        "intent": "correction",
        "correction": {
            "has_errors": True,
            "errors": [{"category": "chinglish", "fragment": "eat", "explanation": "x", "correction": "y"}],
            "rewrite": {"minimal": {"text": "a", "explanation": "e"}, "natural": {"text": "b", "explanation": "f"}},
        },
        "reply": None,
    }
    parsed = LLMResponse.model_validate(payload)
    assert parsed.intent == "correction"
    assert parsed.correction.errors[0].category == "chinglish"


def test_llm_response_follow_up_valid():
    parsed = LLMResponse.model_validate({"intent": "follow_up", "correction": None, "reply": "讲解"})
    assert parsed.reply == "讲解"


def test_llm_response_invalid_category_rejected():
    with pytest.raises(ValidationError):
        LLMResponse.model_validate(
            {"intent": "correction", "correction": {"has_errors": True, "errors": [{"category": "typo", "fragment": "a", "explanation": "b", "correction": "c"}], "rewrite": None}, "reply": None}
        )


def test_submit_request_length_boundaries():
    assert SubmitRequest(content="a").content == "a"
    assert SubmitRequest(content="x" * 2000).content == "x" * 2000
    with pytest.raises(ValidationError):
        SubmitRequest(content="")
    with pytest.raises(ValidationError):
        SubmitRequest(content="x" * 2001)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_schemas_correction.py -v`
Expected: FAIL（ModuleNotFoundError: app.schemas.correction）

- [ ] **Step 3: 实现 schemas**

创建 `backend/app/schemas/correction.py`：

```python
import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ErrorCategory(str, Enum):
    grammar = "grammar"
    collocation = "collocation"
    chinglish = "chinglish"
    style = "style"


class ErrorBlock(BaseModel):
    category: ErrorCategory
    fragment: str
    explanation: str
    correction: str


class RewriteOption(BaseModel):
    text: str
    explanation: str


class RewriteSection(BaseModel):
    minimal: RewriteOption
    natural: RewriteOption


class CorrectionBody(BaseModel):
    has_errors: bool
    errors: list[ErrorBlock] = Field(default_factory=list)
    rewrite: RewriteSection | None = None


class LLMResponse(BaseModel):
    intent: Literal["correction", "follow_up"]
    correction: CorrectionBody | None = None
    reply: str | None = None


class SubmitRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    type: str
    content: str | None
    report: dict | None = None
    created_at: datetime


class SubmitResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut


class HistoryResponse(BaseModel):
    messages: list[MessageOut]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_schemas_correction.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/correction.py backend/tests/test_schemas_correction.py
git commit -m "feat(backend): 纠错 Pydantic 契约（LLM 响应/提交/消息/历史）"
```

---

### Task 6: 纠错服务（get-or-create 对话、上下文组装、提交、历史）

**Files:**
- Create: `backend/app/services/correction_service.py`
- Test: `backend/tests/test_correction_service.py`

- [ ] **Step 1: 编写失败的测试**

创建 `backend/tests/test_correction_service.py`：

```python
import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db import async_session_factory
from app.models.message import Message, MessageRole, MessageType
from app.models.report import CorrectionReport
from app.models.user import User
from app.schemas.correction import SubmitResponse
from app.services.correction_service import (
    build_context,
    get_or_create_conversation,
    list_messages,
    submit_message,
)
from app.services.llm_client import MockLLMClient


async def _demo_user_id() -> uuid.UUID:
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        return user.id


async def _count(model):
    async with async_session_factory() as s:
        return (await s.execute(select(func.count()).select_from(model))).scalar_one()


async def test_get_or_create_conversation_is_singleton():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        c1 = await get_or_create_conversation(s, uid)
        c2 = await get_or_create_conversation(s, uid)
        assert c1.id == c2.id


async def test_submit_correction_writes_message_pair_and_report():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient()
        user_out, ai_out = await submit_message(
            s, uid, "Yesterday I go to the park", mock
        )
        assert user_out.type == "correction"
        assert ai_out.type == "report"
        assert ai_out.report["has_errors"] is True
    assert await _count(Message) == 2
    assert await _count(CorrectionReport) == 1


async def test_submit_follow_up_returns_reply():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient()
        user_out, ai_out = await submit_message(s, uid, "为什么不能用 very？", mock)
        assert user_out.type == "follow_up"
        assert ai_out.type == "reply"
        assert ai_out.content


async def test_build_context_includes_report_structure():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient()
        await submit_message(s, uid, "Yesterday I go to the park", mock)
        conv = await get_or_create_conversation(s, uid)
        ctx = await build_context(s, conv.id, get_settings().CONTEXT_LIMIT)
        assert len(ctx) == 2
        assert "report" in ctx[1]["content"]


async def test_list_messages_orders_and_embeds_report():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient()
        await submit_message(s, uid, "Yesterday I go to the park", mock)
        msgs = await list_messages(s, uid)
        assert [m.type for m in msgs] == ["correction", "report"]
        assert msgs[1].report["has_errors"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_correction_service.py -v`
Expected: FAIL（ModuleNotFoundError: app.services.correction_service）

- [ ] **Step 3: 实现纠错服务**

创建 `backend/app/services/correction_service.py`：

```python
import json
import uuid

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.conversation import SessionConversation
from app.models.message import Message, MessageRole, MessageType
from app.models.report import CorrectionReport
from app.schemas.correction import LLMResponse, MessageOut
from app.services.llm_client import (
    LLMClient,
    LLMTimeoutError,
    LLMUnavailableError,
)

SYSTEM_PROMPT = (
    "你是英文纠错教练。根据对话上下文判断用户意图："
    "提交英文文本请判定为 correction 并输出结构化纠错报告；"
    "纯中文或提问请判定为 follow_up 并输出纯文本讲解。"
    "纠错报告遵循最小修正原则，报告内不重复展示原文；"
    "若无错误则 has_errors=false。必须输出合法 JSON，结构为 {intent, correction, reply}。"
)


async def get_or_create_conversation(session: AsyncSession, user_id: uuid.UUID) -> SessionConversation:
    conv = (
        await session.execute(
            select(SessionConversation)
            .where(SessionConversation.user_id == user_id)
            .order_by(SessionConversation.created_at)
            .limit(1)
        )
    ).scalars().first()
    if conv is not None:
        return conv
    conv = SessionConversation(user_id=user_id)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


async def _fetch_reports(session: AsyncSession, report_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    if not report_ids:
        return {}
    rows = (
        await session.execute(select(CorrectionReport).where(CorrectionReport.id.in_(report_ids)))
    ).scalars().all()
    return {r.id: r.structure for r in rows}


async def build_context(session: AsyncSession, conversation_id: uuid.UUID, limit: int) -> list[dict]:
    rows = list(
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(limit)
            )
        ).scalars()
    )
    rows.reverse()
    reports = await _fetch_reports(session, [m.report_id for m in rows if m.report_id])
    result = []
    for m in rows:
        if m.type == MessageType.report and m.report_id in reports:
            content = json.dumps({"report": reports[m.report_id]}, ensure_ascii=False)
        else:
            content = m.content or ""
        result.append({"role": m.role.value, "content": content})
    return result


async def _call_and_parse(llm_client: LLMClient, messages: list[dict]) -> LLMResponse:
    for attempt in range(2):
        try:
            raw = await llm_client.complete(messages)
        except LLMTimeoutError:
            raise AppError(504, "LLM_TIMEOUT", "AI 响应超时，请重试")
        except LLMUnavailableError:
            raise AppError(503, "LLM_SERVICE_UNAVAILABLE", "AI 服务不可用，请稍后重试")
        try:
            return LLMResponse.model_validate_json(raw)
        except ValidationError:
            if attempt == 0:
                continue
            raise AppError(502, "LLM_RESPONSE_INVALID", "AI 返回内容无效，请重试")
    raise AppError(502, "LLM_RESPONSE_INVALID", "AI 返回内容无效，请重试")


def _to_out(msg: Message, report: dict | None) -> MessageOut:
    return MessageOut(
        id=msg.id,
        role=msg.role.value,
        type=msg.type.value,
        content=msg.content,
        report=report,
        created_at=msg.created_at,
    )


async def submit_message(
    session: AsyncSession, user_id: uuid.UUID, content: str, llm_client: LLMClient
) -> tuple[MessageOut, MessageOut]:
    conv = await get_or_create_conversation(session, user_id)
    context = await build_context(session, conv.id, get_settings().CONTEXT_LIMIT)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *context,
        {"role": "user", "content": content},
    ]
    parsed = await _call_and_parse(llm_client, messages)

    user_type = MessageType.follow_up if parsed.intent == "follow_up" else MessageType.correction
    user_msg = Message(
        conversation_id=conv.id, role=MessageRole.user, type=user_type, content=content
    )
    session.add(user_msg)
    await session.flush()

    report_structure: dict | None = None
    if parsed.intent == "correction":
        if parsed.correction is None:
            raise AppError(502, "LLM_RESPONSE_INVALID", "AI 返回内容无效，请重试")
        report_structure = parsed.correction.model_dump()
        report = CorrectionReport(version=1, structure=report_structure)
        session.add(report)
        await session.flush()
        ai_msg = Message(
            conversation_id=conv.id,
            role=MessageRole.assistant,
            type=MessageType.report,
            content=None,
            report_id=report.id,
        )
        session.add(ai_msg)
        await session.flush()
        report.message_id = ai_msg.id
    else:
        ai_msg = Message(
            conversation_id=conv.id,
            role=MessageRole.assistant,
            type=MessageType.reply,
            content=parsed.reply,
        )
        session.add(ai_msg)
        await session.flush()

    await session.commit()
    return _to_out(user_msg, None), _to_out(ai_msg, report_structure)


async def list_messages(session: AsyncSession, user_id: uuid.UUID) -> list[MessageOut]:
    conv = await get_or_create_conversation(session, user_id)
    rows = list(
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at, Message.id)
            )
        ).scalars()
    )
    reports = await _fetch_reports(session, [m.report_id for m in rows if m.report_id])
    return [_to_out(m, reports.get(m.report_id)) for m in rows]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_correction_service.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/correction_service.py backend/tests/test_correction_service.py
git commit -m "feat(backend): 纠错服务（get-or-create 对话/上下文组装/提交/历史），LLM 单次调用+解析重试"
```

---

### Task 7: 消息路由（POST/GET /api/v1/messages）+ 注册

**Files:**
- Create: `backend/app/routers/messages.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 编写失败的 API 契约测试**

创建 `backend/tests/test_messages_api.py`：

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services.llm_client import MockLLMClient, get_llm_client

POST_URL = "/api/v1/messages"
GET_URL = "/api/v1/messages"
LOGIN_URL = "/api/v1/auth/login"


@pytest_asyncio.fixture
async def api():
    app = create_app()
    mock = MockLLMClient()
    app.dependency_overrides[get_llm_client] = lambda: mock
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, mock


async def _token(client: AsyncClient) -> str:
    r = await client.post(LOGIN_URL, json={"username": "demo", "password": "demo1234"})
    assert r.status_code == 200
    return r.json()["token"]


async def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# T-C-01 提交纠错成功
async def test_post_messages_correction(api):
    client, _ = api
    token = await _token(client)
    r = await client.post(POST_URL, json={"content": "Yesterday I go to the park"}, headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["user_message"]["type"] == "correction"
    assert data["assistant_message"]["type"] == "report"
    assert data["assistant_message"]["report"]["has_errors"] is True


# T-C-02 无错误文本
async def test_post_messages_no_error(api):
    client, mock = api
    token = await _token(client)
    mock.responder = lambda msgs: (
        '{"intent":"correction","correction":{"has_errors":false,"errors":[],"rewrite":null},"reply":null}'
    )
    r = await client.post(POST_URL, json={"content": "perfect english"}, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["assistant_message"]["report"]["has_errors"] is False


# T-C-03 纯中文→追问
async def test_post_messages_follow_up(api):
    client, _ = api
    token = await _token(client)
    r = await client.post(POST_URL, json={"content": "为什么不能用 very？"}, headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["user_message"]["type"] == "follow_up"
    assert data["assistant_message"]["type"] == "reply"
    assert data["assistant_message"]["content"]


# T-C-04 空内容
async def test_post_messages_empty(api):
    client, _ = api
    token = await _token(client)
    r = await client.post(POST_URL, json={"content": ""}, headers=_auth(token))
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION_ERROR"


# T-C-05 超 2000 字符
async def test_post_messages_too_long(api):
    client, _ = api
    token = await _token(client)
    r = await client.post(POST_URL, json={"content": "x" * 2001}, headers=_auth(token))
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION_ERROR"


# T-C-06 未鉴权
async def test_post_messages_unauthorized(api):
    client, _ = api
    r = await client.post(POST_URL, json={"content": "hello"})
    assert r.status_code == 401


# T-C-07 LLM 未配置 → 503（使用默认 app，不覆盖依赖）
async def test_post_messages_llm_not_configured(client):
    token = await _token(client)
    r = await client.post(POST_URL, json={"content": "hello world"}, headers=_auth(token))
    assert r.status_code == 503
    assert r.json()["code"] == "LLM_SERVICE_UNAVAILABLE"


# T-C-08 LLM 返回无效 JSON → 502（重试后）
async def test_post_messages_invalid_llm_response(api):
    client, mock = api
    token = await _token(client)
    mock.responder = lambda msgs: "not-json"
    r = await client.post(POST_URL, json={"content": "hello world"}, headers=_auth(token))
    assert r.status_code == 502
    assert r.json()["code"] == "LLM_RESPONSE_INVALID"
    assert len(mock.calls) == 2  # 首次失败后重试一次


# T-C-09 空历史
async def test_get_messages_empty(api):
    client, _ = api
    token = await _token(client)
    r = await client.get(GET_URL, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["messages"] == []


# T-C-10 有历史且报告内嵌
async def test_get_messages_with_history(api):
    client, _ = api
    token = await _token(client)
    await client.post(POST_URL, json={"content": "Yesterday I go to the park"}, headers=_auth(token))
    r = await client.get(GET_URL, headers=_auth(token))
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [m["type"] for m in msgs] == ["correction", "report"]
    assert msgs[1]["report"]["has_errors"] is True


# T-C-11 数据隔离
async def test_data_isolation(api):
    from sqlalchemy import select as sa_select

    from app.core.security import hash_password
    from app.db import async_session_factory
    from app.models.user import User, UserStatus

    async with async_session_factory() as s:
        s.add(
            User(
                username="alice",
                password_hash=hash_password("alice1234"),
                status=UserStatus.active,
            )
        )
        await s.commit()
    client, _ = api
    token = await _token(client)
    await client.post(POST_URL, json={"content": "Yesterday I go to the park"}, headers=_auth(token))
    assert len((await client.get(GET_URL, headers=_auth(token))).json()["messages"]) == 2
    r = await client.post(LOGIN_URL, json={"username": "alice", "password": "alice1234"})
    assert r.status_code == 200
    alice_token = r.json()["token"]
    assert (await client.get(GET_URL, headers=_auth(alice_token))).json()["messages"] == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_messages_api.py -v`
Expected: FAIL（ModuleNotFoundError: app.routers.messages）

- [ ] **Step 3: 实现消息路由**

创建 `backend/app/routers/messages.py`：

```python
from fastapi import APIRouter, Depends
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
):
    user_out, ai_out = await correction_service.submit_message(
        session, user.id, payload.content, llm_client
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

修改 `backend/app/main.py`：
- `from app.routers import auth, health` → `from app.routers import auth, health, messages`
- `app.include_router(auth.router)` 之后追加 `app.include_router(messages.router)`

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_messages_api.py -v`
Expected: PASS（11 passed：T-C-01~11）

- [ ] **Step 5: 全量回归**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全绿（原 24 + 契约 11 + service 5 + schema 4 + llm 1 = 45 passed）

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/messages.py backend/app/main.py backend/tests/test_messages_api.py
git commit -m "feat(backend): 消息路由 POST/GET /api/v1/messages（T-C-01~11 契约验收）"
```

---

### Task 8: 前端 API 客户端 + 会话状态（context）

**Files:**
- Create: `web/src/api/messages.ts`
- Create: `web/src/store/conversation-context.ts`
- Create: `web/src/store/conversation.tsx`

- [ ] **Step 1: 创建 API 类型与函数**

创建 `web/src/api/messages.ts`：

```ts
import { http } from './client'

export interface ErrorBlock {
  category: string
  fragment: string
  explanation: string
  correction: string
}

export interface RewriteOption {
  text: string
  explanation: string
}

export interface RewriteSection {
  minimal: RewriteOption
  natural: RewriteOption
}

export interface CorrectionReport {
  has_errors: boolean
  errors: ErrorBlock[]
  rewrite: RewriteSection | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  type: string
  content: string | null
  report: CorrectionReport | null
  created_at: string
}

export interface SubmitResult {
  user_message: Message
  assistant_message: Message
}

export async function fetchMessages(): Promise<Message[]> {
  const data = await http.get<{ messages: Message[] }>('/messages')
  return data.messages
}

export async function submitMessage(content: string): Promise<SubmitResult> {
  return http.post<SubmitResult>('/messages', { content })
}
```

- [ ] **Step 2: 创建 context 定义**

创建 `web/src/store/conversation-context.ts`：

```ts
import { createContext, useContext } from 'react'

import type { Message } from '@/api/messages'

export interface ConversationState {
  messages: Message[]
  pending: boolean
  error: string | null
  load: () => Promise<void>
  send: (content: string) => Promise<void>
}

export const ConversationContext = createContext<ConversationState | null>(null)

export function useConversation(): ConversationState {
  const ctx = useContext(ConversationContext)
  if (!ctx) throw new Error('useConversation must be used within ConversationProvider')
  return ctx
}
```

- [ ] **Step 3: 创建 provider**

创建 `web/src/store/conversation.tsx`：

```tsx
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import * as messagesApi from '@/api/messages'
import { ApiError } from '@/api/client'
import { ConversationContext } from '@/store/conversation-context'

export function ConversationProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<messagesApi.Message[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

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

  const send = useCallback(async (content: string) => {
    setPending(true)
    setError(null)
    const temp: messagesApi.Message = {
      id: `tmp-${Date.now()}`,
      role: 'user',
      type: 'correction',
      content,
      report: null,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, temp])
    try {
      const result = await messagesApi.submitMessage(content)
      if (mounted.current) {
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== temp.id),
          result.user_message,
          result.assistant_message,
        ])
      }
    } catch (err) {
      if (mounted.current) {
        setMessages((prev) => prev.filter((m) => m.id !== temp.id))
        setError(err instanceof ApiError ? err.message : '请求失败，请重试')
      }
    } finally {
      if (mounted.current) setPending(false)
    }
  }, [])

  const value = { messages, pending, error, load, send }
  return <ConversationContext.Provider value={value}>{children}</ConversationContext.Provider>
}
```

- [ ] **Step 4: 类型检查**

Run: `cd web && npx tsc -b`
Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add web/src/api/messages.ts web/src/store/conversation-context.ts web/src/store/conversation.tsx
git commit -m "feat(web): 消息 API 客户端与会话状态 context（加载/提交/错误）"
```

---

### Task 9: 前端会话组件（气泡 / 报告 / 改写 / 加载）

**Files:**
- Create: `web/src/components/correction/UserBubble.tsx`
- Create: `web/src/components/correction/ReplyBubble.tsx`
- Create: `web/src/components/correction/LoadingBubble.tsx`
- Create: `web/src/components/correction/ErrorCard.tsx`
- Create: `web/src/components/correction/RewriteSection.tsx`
- Create: `web/src/components/correction/CorrectionReportCard.tsx`

- [ ] **Step 1: 创建消息气泡组件**

创建 `web/src/components/correction/UserBubble.tsx`：

```tsx
export default function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-xl bg-[#0ca678] px-4 py-2.5 text-white md:max-w-[70%]">
        {content}
      </div>
    </div>
  )
}
```

创建 `web/src/components/correction/ReplyBubble.tsx`：

```tsx
export default function ReplyBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-xl bg-[#f1f3f5] px-4 py-2.5 text-[#343a40] md:max-w-[70%]">
        {content}
      </div>
    </div>
  )
}
```

创建 `web/src/components/correction/LoadingBubble.tsx`：

```tsx
export default function LoadingBubble() {
  return (
    <div className="flex justify-start">
      <div className="rounded-xl bg-[#f1f3f5] px-4 py-2.5 text-sm text-[#868e96]">
        AI 正在分析，请稍候…
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 创建错误卡片组件**

创建 `web/src/components/correction/ErrorCard.tsx`：

```tsx
import type { ErrorBlock } from '@/api/messages'

const CATEGORY_LABEL: Record<string, string> = {
  grammar: '语法',
  collocation: '搭配',
  chinglish: '中式英语',
  style: '风格与语气',
}

export default function ErrorCard({ error }: { error: ErrorBlock }) {
  const isChinglish = error.category === 'chinglish'
  const accent = isChinglish
    ? 'border-l-[#f76707] bg-[#fff9f0]'
    : 'border-l-[#fa5252] bg-[#fff5f5]'
  return (
    <div className={`rounded-lg border border-[#dee2e6] border-l-4 p-3 ${accent}`}>
      <div className="flex items-center gap-2">
        <span
          className={`rounded px-1.5 py-0.5 text-xs text-white ${isChinglish ? 'bg-[#f76707]' : 'bg-[#fa5252]'}`}
        >
          {CATEGORY_LABEL[error.category] ?? error.category}
        </span>
        <span className="text-sm font-medium text-[#c92a2a] line-through">
          {error.fragment}
        </span>
      </div>
      <p className="mt-1.5 text-sm text-[#495057]">{error.explanation}</p>
      <p className="mt-1 text-sm font-medium text-[#2b8a3e]">✅ {error.correction}</p>
    </div>
  )
}
```

- [ ] **Step 3: 创建改写分区（含复制）**

创建 `web/src/components/correction/RewriteSection.tsx`：

```tsx
import { useState } from 'react'

import type { RewriteOption, RewriteSection as RewriteSectionType } from '@/api/messages'

function RewriteBox({
  label,
  icon,
  option,
  accent,
}: {
  label: string
  icon: string
  option: RewriteOption
  accent: string
}) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    await navigator.clipboard.writeText(option.text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="relative rounded-lg border border-dashed border-[#0ca678] bg-[#f0fdfa] p-3 pr-10">
      <button
        type="button"
        onClick={copy}
        aria-label={`复制${label}`}
        className="absolute right-1.5 top-1.5 flex size-9 items-center justify-center rounded-md text-[#868e96] hover:border hover:border-[#0ca678] hover:text-[#0ca678]"
      >
        {copied ? <span className="text-[#2b8a3e]">✓</span> : <span>📋</span>}
      </button>
      <p className={`text-sm font-semibold ${accent}`}>
        {icon} {label}
      </p>
      <p className="mt-1 whitespace-pre-wrap text-[#212529]">{option.text}</p>
      <p className="mt-1 text-xs text-[#868e96]">{option.explanation}</p>
    </div>
  )
}

export default function RewriteSection({ rewrite }: { rewrite: RewriteSectionType }) {
  return (
    <div className="space-y-2">
      <RewriteBox label="最小修正" icon="✏️" option={rewrite.minimal} accent="text-[#2b8a3e]" />
      <RewriteBox label="地道表达" icon="✨" option={rewrite.natural} accent="text-[#7048e8]" />
    </div>
  )
}
```

- [ ] **Step 4: 创建报告卡片（整体大框 + 两分区）**

创建 `web/src/components/correction/CorrectionReportCard.tsx`：

```tsx
import type { CorrectionReport } from '@/api/messages'
import ErrorCard from '@/components/correction/ErrorCard'
import RewriteSection from '@/components/correction/RewriteSection'

export default function CorrectionReportCard({ report }: { report: CorrectionReport }) {
  if (!report.has_errors) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-xl bg-[#e6fcf5] px-4 py-2.5 text-[#0a7053] md:max-w-[70%]">
          🎉 这段英文写得不错，没有发现语法或不地道的表达！
        </div>
      </div>
    )
  }
  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[90%] rounded-xl border border-[#dee2e6] bg-white p-3 md:max-w-[75%]">
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

- [ ] **Step 5: 类型检查**

Run: `cd web && npx tsc -b`
Expected: 无错误

- [ ] **Step 6: Commit**

```bash
git add web/src/components/correction/
git commit -m "feat(web): 会话组件（气泡/错误卡片/改写分区含复制/报告卡片）"
```

---

### Task 10: 消息列表 + 输入栏（Composer）+ 纠错主页

**Files:**
- Create: `web/src/components/correction/MessageList.tsx`
- Create: `web/src/components/correction/Composer.tsx`
- Create: `web/src/pages/CorrectionPage.tsx`
- Modify: `web/src/App.tsx`
- Delete: `web/src/pages/CorrectionPlaceholder.tsx`

- [ ] **Step 1: 创建消息列表**

创建 `web/src/components/correction/MessageList.tsx`：

```tsx
import { useEffect, useRef } from 'react'

import CorrectionReportCard from '@/components/correction/CorrectionReportCard'
import LoadingBubble from '@/components/correction/LoadingBubble'
import ReplyBubble from '@/components/correction/ReplyBubble'
import UserBubble from '@/components/correction/UserBubble'
import { useConversation } from '@/store/conversation-context'

export default function MessageList() {
  const { messages, pending, error } = useConversation()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, pending])

  if (messages.length === 0 && !pending) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <p className="text-center text-[#868e96]">
          输入英文，AI 将为你纠错；也可以随时提问
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-2xl flex-1 space-y-4 overflow-y-auto p-4 md:p-6">
      {messages.map((m) =>
        m.role === 'user' ? (
          <UserBubble key={m.id} content={m.content ?? ''} />
        ) : m.type === 'report' && m.report ? (
          <CorrectionReportCard key={m.id} report={m.report} />
        ) : (
          <ReplyBubble key={m.id} content={m.content ?? ''} />
        ),
      )}
      {pending && <LoadingBubble />}
      {error && (
        <p className="text-center text-sm text-[#fa5252]">
          {error}，你的消息已保留，可重新发送
        </p>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
```

- [ ] **Step 2: 创建输入栏**

创建 `web/src/components/correction/Composer.tsx`：

```tsx
import { useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { useConversation } from '@/store/conversation-context'

const MAX_LENGTH = 2000

export default function Composer() {
  const { send, pending } = useConversation()
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  const over = text.length > MAX_LENGTH
  const disabled = pending || text.trim().length === 0 || over

  function autoResize() {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }

  async function handleSend() {
    const content = text.trim()
    if (!content || disabled) return
    setText('')
    if (ref.current) ref.current.style.height = 'auto'
    await send(content)
  }

  return (
    <div className="shrink-0 border-t border-[#dee2e6] bg-white px-4 py-3 md:px-8">
      <div className="mx-auto max-w-2xl">
        <textarea
          ref={ref}
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            autoResize()
          }}
          placeholder="输入英文，AI 将为你纠错；也可以随时提问"
          rows={1}
          className="w-full resize-none rounded-lg border border-[#ced4da] bg-[#f8f9fa] px-3.5 py-2.5 text-base focus-visible:border-[#0ca678] focus-visible:ring-[#0ca678]/50"
        />
        <div className="mt-1.5 flex items-center justify-between">
          <span className={`text-sm ${over ? 'text-[#fa5252]' : 'text-[#868e96]'}`}>
            {over ? '请将文本缩短至 2000 字符以内再提交' : `${text.length}/${MAX_LENGTH}`}
          </span>
          <Button
            onClick={handleSend}
            disabled={disabled}
            className="h-11 bg-[#0ca678] px-6 text-white hover:bg-[#12c493] disabled:bg-[#99f0d8]"
          >
            {pending ? 'AI 正在分析，请稍候…' : '发送'}
          </Button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 创建纠错主页**

创建 `web/src/pages/CorrectionPage.tsx`：

```tsx
import { useNavigate } from 'react-router-dom'

import Composer from '@/components/correction/Composer'
import MessageList from '@/components/correction/MessageList'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/store/auth-context'

export default function CorrectionPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-screen flex-col bg-[#f0fdfa]">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-[#dee2e6] bg-white px-4 md:px-8">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-[#0ca678] text-sm font-semibold text-white">
            E
          </div>
          <span className="text-lg font-semibold text-[#0a7053]">
            Echo · 地道英语纠错
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-[#495057]">{user?.username ?? ''}</span>
          <Button
            variant="outline"
            onClick={handleLogout}
            className="h-9 border-[#ced4da] bg-white px-4 text-[#343a40] hover:bg-[#f1f3f5]"
          >
            退出
          </Button>
        </div>
      </header>

      <MessageList />
      <Composer />
    </div>
  )
}
```

- [ ] **Step 4: 更新路由并移除占位页**

修改 `web/src/App.tsx`：
- import 替换：`CorrectionPlaceholder` → `CorrectionPage`；新增 `import { ConversationProvider } from '@/store/conversation'`
- `/correction` 路由 element 改为：

```tsx
          <Route
            path="/correction"
            element={
              <ConversationProvider>
                <CorrectionPage />
              </ConversationProvider>
            }
          />
```

删除 `web/src/pages/CorrectionPlaceholder.tsx`。

- [ ] **Step 5: 类型检查 + lint**

Run: `cd web && npx tsc -b && npx oxlint`
Expected: 无错误

- [ ] **Step 6: Commit**

```bash
git add web/src/App.tsx web/src/pages/CorrectionPage.tsx web/src/components/correction/
git rm web/src/pages/CorrectionPlaceholder.tsx
git commit -m "feat(web): 纠错主页（消息列表/输入栏/报告渲染），替换占位页"
```

---

### Task 11: E2E 配置（Mock LLM 后端）与登录回归

**Files:**
- Modify: `web/playwright.config.ts`

- [ ] **Step 1: 后端 webServer 命令启用 mock 模式**

修改 `web/playwright.config.ts` 中第一个 webServer 的 command：

```ts
      command: 'LLM_MODE=mock .venv/bin/uvicorn app.main:app --port 8000',
```

- [ ] **Step 2: 运行登录 E2E 回归（确保 Mock 后端不影响登录）**

Run: `cd backend && .venv/bin/alembic upgrade head && cd ../web && lsof -ti :8000 | xargs kill 2>/dev/null; lsof -ti :5173 | xargs kill 2>/dev/null; npm run test:e2e`
Expected: 登录套件 U-L-01~09 全部通过（10 passed，含 API 兜底测试）

> 说明：若本地已有旧的 uvicorn（无 `LLM_MODE=mock`）占用 8000 端口，先 kill 掉，让 Playwright 以 mock 模式启动新后端。

- [ ] **Step 3: Commit**

```bash
git add web/playwright.config.ts
git commit -m "test(e2e): 后端 webServer 启用 LLM_MODE=mock 供纠错 E2E 离线验证"
```

---

### Task 12: 纠错 E2E 测试（U-C-01~10）

**Files:**
- Create: `web/tests/e2e/correction.spec.ts`

- [ ] **Step 1: 创建纠错 E2E 测试**

创建 `web/tests/e2e/correction.spec.ts`：

```ts
import { expect, test, type Page } from '@playwright/test'

const USERNAME = 'demo'
const PASSWORD = 'demo1234'

async function login(page: Page) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(USERNAME)
  await page.getByLabel('密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page).toHaveURL(/\/correction$/)
}

async function send(page: Page, text: string) {
  await page.getByPlaceholder('输入英文，AI 将为你纠错；也可以随时提问').fill(text)
  await page.getByRole('button', { name: '发送' }).click()
}

// U-C-01 首次进入空态
test('U-C-01 首次进入纠错主页显示空态引导', async ({ page }) => {
  await login(page)
  await expect(page.getByText('输入英文，AI 将为你纠错；也可以随时提问')).toBeVisible()
})

// U-C-02 提交含错英文 → 报告
test('U-C-02 提交含错英文呈现纠错报告', async ({ page }) => {
  await login(page)
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('错误分析')).toBeVisible()
  await expect(page.getByText('I went to')).toBeVisible()
  await expect(page.getByText('改写')).toBeVisible()
  await expect(page.getByText('最小修正')).toBeVisible()
  await expect(page.getByText('地道表达')).toBeVisible()
})

// U-C-03 无错误文本 → 鼓励文案
test('U-C-03 无错误文本展示鼓励文案', async ({ page }) => {
  await login(page)
  await send(page, 'no-error')
  await expect(page.getByText(/这段英文写得不错/)).toBeVisible()
})

// U-C-04 纯中文 → 追问回复
test('U-C-04 纯中文返回纯文本追问回复', async ({ page }) => {
  await login(page)
  await send(page, '为什么不能用 very？')
  await expect(page.getByText('delicious 是极限形容词')).toBeVisible()
})

// U-C-05 连续追问
test('U-C-05 连续追问多次均正常回复', async ({ page }) => {
  await login(page)
  await send(page, '为什么不能用 very？')
  await expect(page.getByText('delicious 是极限形容词')).toBeVisible()
  await send(page, '那 delicious 可以用什么词修饰？')
  await expect(page.getByText(/delicious/).first()).toBeVisible()
})

// U-C-06 超 2000 字符 → 字数标红 + 发送禁用
test('U-C-06 输入超 2000 字符发送禁用', async ({ page }) => {
  await login(page)
  const longText = 'x'.repeat(2001)
  await page.getByPlaceholder('输入英文，AI 将为你纠错；也可以随时提问').fill(longText)
  await expect(page.getByText('请将文本缩短至 2000 字符以内再提交')).toBeVisible()
  await expect(page.getByRole('button', { name: '发送' })).toBeDisabled()
})

// U-C-07 多行输入自动延伸
test('U-C-07 多行输入输入框增高', async ({ page }) => {
  await login(page)
  const ta = page.getByPlaceholder('输入英文，AI 将为你纠错；也可以随时提问')
  await ta.fill('line one\nline two\nline three')
  const height = await ta.evaluate((el) => el.scrollHeight)
  expect(height).toBeGreaterThan(40)
})

// U-C-08 复制改写
test('U-C-08 点击复制按钮复制改写文本', async ({ page }) => {
  await login(page)
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('最小修正')).toBeVisible()
  const copyButton = page.getByRole('button', { name: '复制最小修正' })
  await copyButton.click()
  await expect(copyButton.getByText('✓')).toBeVisible()
})

// U-C-09 刷新后历史仍在
test('U-C-09 刷新页面历史全量加载', async ({ page }) => {
  await login(page)
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('错误分析')).toBeVisible()
  await page.reload()
  await expect(page.getByText('错误分析')).toBeVisible()
  await expect(page.getByText('Yesterday I go to the park').first()).toBeVisible()
})

// U-C-10 手机宽度
test('U-C-10 手机宽度布局正常', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await login(page)
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('错误分析')).toBeVisible()
  await expect(page.getByRole('button', { name: '退出' })).toBeVisible()
})
```

> 提示：U-C-05 第二句的 Mock 默认响应——纯中文才触发 follow_up，此句为纯中文，`_default_responder` 会返回 follow_up。若断言失败，将其改为纯中文即可。

- [ ] **Step 2: 运行纠错 E2E（需先迁移并清空开发库历史，保证 U-C-01 空态确定）**

Run: `cd backend && .venv/bin/alembic upgrade head && cd ../web && lsof -ti :8000 | xargs kill 2>/dev/null; lsof -ti :5173 | xargs kill 2>/dev/null; npm run test:e2e`

> 若多次运行后 U-C-01 空态失败（历史残留），先清空 demo 用户历史再跑：
> Run: `cd backend && .venv/bin/python -c "
> import asyncio
> from sqlalchemy import text
> from app.db import async_session_factory
> async def main():
>     async with async_session_factory() as s:
>         await s.execute(text('TRUNCATE messages, correction_reports, session_conversations'))
>         await s.commit()
> asyncio.run(main())
> "`
> Expected: 无输出（清空成功）

Expected: 纠错套件 U-C-01~10 全部通过

- [ ] **Step 3: Commit**

```bash
git add web/tests/e2e/correction.spec.ts
git commit -m "test(e2e): 纠错主页 E2E（U-C-01~10 验收）"
```

---

### Task 13: 全量验证收尾

- [ ] **Step 1: 后端全量测试**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全绿（45 passed）

- [ ] **Step 2: 前端类型检查 + lint**

Run: `cd web && npx tsc -b && npx oxlint`
Expected: 无错误

- [ ] **Step 3: 全量 E2E（登录 + 纠错）**

Run: `cd web && lsof -ti :8000 | xargs kill 2>/dev/null; lsof -ti :5173 | xargs kill 2>/dev/null; npm run test:e2e`
Expected: 登录 10 + 纠错 10 = 20 passed

- [ ] **Step 4: 启动本地服务冒烟（可选手工走查）**

Run: `cd backend && nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/echo_backend.log 2>&1 & cd ../web && nohup npm run dev > /tmp/echo_web.log 2>&1 &`
Expected: `curl http://localhost:8000/api/v1/health` → ok；`curl http://localhost:5173` → 200

- [ ] **Step 5: 文档状态更新（如计划执行有偏差，回写设计文档）**

如实现与 `docs/tech-design/02-Correction.md` 有出入，更新文档后提交。

- [ ] **Step 6: 最终 Commit（如无已提交改动则跳过）**

```bash
git add -A
git commit -m "chore: 纠错功能实现收尾"
```

---

## Self-Review 检查表

- **Spec 覆盖**：T-C-01~12 对应设计文档 §9.1（T-C-12 追问上下文由 `test_correction_service.py::test_build_context_includes_report_structure` 覆盖，历史/隔离在 Task 7）；U-C-01~10 对应 §9.2；LLM 未配置 503（T-C-07）、502 重试（T-C-08）均覆盖。
- **占位符扫描**：无 TBD/TODO；所有步骤含完整代码与命令。
- **类型一致性**：`LLMClient.complete` 统一返回 `str`；`submit_message` 返回 `tuple[MessageOut, MessageOut]`；路由层不再重复组装 `MessageOut`；`MockLLMClient.responder` 为 `Callable[[list[dict]], str]`，`calls` 记录每次调用。
