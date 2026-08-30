# 记笔记异步化设计（notes-async-save）

**所属**：地道英语纠错 · 智能笔记本 | **版本**：V0.1 | **状态**：草稿 | **日期**：2026-08-30
**依赖**：`backend/app/prompts/correction_prompt.py`、`backend/app/schemas/correction.py`、`backend/app/services/correction_service.py`、`backend/app/services/note_service.py`、`backend/app/routers/notes.py`、`backend/app/schemas/note.py`、`backend/app/services/llm_client.py`、`web/src/components/correction/ErrorCard.tsx`、`web/src/components/correction/CorrectionReportCard.tsx`

> 本文档定义记笔记功能的架构演进：**纠错链路移除 learnings 段**，笔记规则生成改为**第二次异步 LLM 调用**，从而缩短纠错请求的同步响应时间。前序设计见 `notes-feature-design.md`（08-29）与 `notes-examples-dedup-design.md`（08-30），本文档在其基础上做增量设计，**不推翻已确认的规则粒度/去重/数据模型**。

## 〇、背景与根因

记笔记已上线（F-02）。当前实现有两个耦合点导致纠错响应慢：

1. **纠错提示词同时产出 learnings**（规则+例证），增加了输入 token 与单次 LLM 输出的生成时间，全部落在用户等待的**同步链路**里。
2. **保存笔记时又同步调一次 LLM**（`POST /notes/save`，`save_notes` 内 `_call_llm_and_parse`），这次调用同样阻塞在点击"记笔记"后的前端请求里。

核心矛盾：**笔记生成属于"可稍后"的任务，却占用了"用户正在等待"的同步链路两次。**

本文档把两处都拆出去：

| 现状 | 演进后 |
|------|--------|
| 纠错提示词输出 `errors`+`rewrite`+`learnings` | 纠错提示词只输出 `errors`+`rewrite`（移除 learnings） |
| `POST /notes/save` 同步等 LLM 生成规则后返回 | 同步返回成功码，LLM 规则生成**改后台异步**，刷新列表页后可见 |

## 一、已确认决策

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 纠错 learnings | **移除**：纠错提示词/输出契约/前端展示删掉 learnings 段 |
| 2 | 笔记规则生成时机 | **第二次独立 LLM 调用**（异步），不依赖纠错时的 learnings |
| 3 | 异步化方式 | **前端触发 + 后台非阻塞执行**：接口同步返回成功码，LLM 生成与入库在后台完成 |
| 4 | 入库时效 | **不要求秒级**；用户点击 "记笔记" 后乐观反馈，刷新笔记列表页后可见最终结果 |
| 5 | API 返回语义 | `POST /notes/save` **同步返回成功码 + 后台入账**（202 语义，无 job 轮询） |
| 6 | 第二次 LLM 输入 | 喂 `errors` 结构（error_type/fragment/explanation/correction）+ source_text，**非裸文本** |
| 7 | 去重逻辑 | **不变**：`notes.rule_title` 精确匹配决定新建/追加；DB 唯一约束 `(note_id,user_id,source_text,fragment)` 兜底 |
| 8 | prompt 复用 | 复用 `note_prompt.py` 现有 `build_note_system_prompt`/`build_note_user_content`（已含 examples+references+去重契约） |
| 9 | 数据模型 | **不变**（`notes`+`note_cases`，`examples` JSONB，fragment/correction 两列，唯一约束） |

## 二、变更 #1：移除纠错 learnings

### 2.1 纠错提示词（`correction_prompt.py`）

- `SYSTEM_PROMPT` 中删除 `### learnings` 段（§`### 改写与学习要点` 下第 99-102 行）。
- 输出字段说明删除 `learnings（数组）` 一行（第 109 行）。

### 2.2 纠错输出契约（`schemas/correction.py`）

- `CorrectionBody` 删除 `learnings: list[Learning]` 字段（第 35 行）。
- 删除 `Learning` 模型定义（`rule`/`example`）。
- 报告结构 `version` 保持 1（learnings 为非破坏性移除，前端本就逐字段解析，详情见 §2.4）。

### 2.3 Mock 输出（`services/llm_client.py`）

- `_default_responder` 中纠错响应的 `"learnings": [...]` 载荷移除（第 99 行、118 行附近）。

### 2.4 前端

- `CorrectionReportCard.tsx`：删除「📚 学到的规则」分区（`LearningsSection`）渲染。
- 报告解析中不再读取 `learnings` 字段（防御：忽略即可，不因缺失报错）。
- **验收一致性**：`PRD/pages/02-Correction.md` 需同步移除 learnings 分区的规则卡描述与 AC-C-16；对应技术设计 `docs/tech-design/02-Correction.md` §1.2 契约移除 learnings。

### 2.5 测试联动

- `tests/test_correction_service.py`：构造的 LLM 原始响应去掉 learnings 字段。
- `tests/test_messages_api.py`：报告断言去掉 `"learnings":[]`。
- `tests/test_schemas_correction.py`：去掉 learnings 解析断言。
- `tests/test_correction_prompt.py`：断言不再要求 learnings；新增断言 `learnings` 不在 SYSTEM_PROMPT。
- prompt 评估脚本 `scripts/prompt_model_compare.py` / `prompt_thinking_compare.py`：`_summarize_result` 去掉 learnings 计数（或保留但恒为 0，脚本升级时清理）。

> 注意：`golden_cases.json` 中的 `ref_learnings_min` 用于 prompt 质量评估，移除 learnings 后这些 key 失去意义，评估脚本改为只看 errors 命中率。

## 三、变更 #2：笔记保存异步化

### 3.1 目标时序

```
点击「记笔记 / 全部记笔记」
        │ 前端乐观反馈（立即）
        ▼
POST /notes/save ──→ 202 {accepted:true}（毫秒级返回）
        │
        └─ 后台任务（非阻塞）：
            调用第二次 LLM（note_prompt.py）→ 解析 → 按 rule_title 去重 → 写 notes/note_cases
            （入库完成前，笔记列表页查不到该条；刷新后可见）
```

### 3.2 API 契约调整（`routers/notes.py`）

**现状**：`POST /notes/save` 同步执行 `note_service.save_notes`，返回 `SaveNoteResponse(saved_notes=[...])`，等待 LLM 完成。

**演进后**：

- 路由先**在校验请求后立即返回** `NoteSaveAccepted`，把实际生成/入库调度到后台。
- 返回体改为同步成功码，不含具体 note/case 明细（历史见 notes-feature-design §4.4 的"返回精简结构"——异步化后前端连精简结构也不需要，因最终数据靠列表页拉取）。

```json
// POST /api/v1/notes/save
// 请求（不变）
{
  "message_id": "uuid",
  "source_text": "I interested in read...",
  "errors": [
    {"error_type":"动词形式","fragment":"interested in read","explanation":"...","correction":"interested in reading"}
  ]
}

// 响应（改为）
HTTP 202
{
  "accepted": true
}
```

### 3.3 后台执行实现

**关键约束——DB Session 生命周期**：FastAPI 的 `Depends(get_db)` session 随请求生命周期结束而关闭（`db.py: async_session_factory` 的上下文管理器 yield 后即 close）。后台任务不能复用该 session。需为后台任务**新建独立 session**（在任务内部通过 `async_session_factory()` 建立并自行关闭）。

**MVP 无消息队列/独立 worker**，用 **`FastAPI.BackgroundTasks`** 在进程内调度（单用户、自用优先）。伪代码：

```python
# routers/notes.py
from fastapi import BackgroundTasks
from app.db import async_session_factory
from app.services.llm_client import get_llm_client

@router.post("/save", response_model=NoteSaveAccepted, status_code=202)
async def save_note(
    payload: SaveNoteRequest,
    user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    background_tasks.add_task(
        _run_save_notes_async,
        user.id,
        payload.message_id,
        payload.source_text,
        [e.model_dump() for e in payload.errors],
    )
    return NoteSaveAccepted(accepted=True)


async def _run_save_notes_async(user_id, source_message_id, source_text, errors):
    # 新建独立 session：get_db 的 session 随请求结束即关闭，后台任务必须自建
    async with async_session_factory() as session:
        llm_client = get_llm_client()  # 任务内解析，不依赖请求作用域（见 §3.5）
        await note_service.save_notes(
            session, user_id, source_message_id, source_text, errors, llm_client
        )
```

> 用 `FastAPI.BackgroundTasks`（`starlette.background`）而非裸 `asyncio.create_task`：前者由 ASGI 管理、请求结束后统一 await 完成或未完成；后者在请求返回后被 GC 可能取消未完成协程。`BackgroundTasks` 默认在**响应发送之后**由 server 调度执行，符合"同步返回 + 后台入账"语义。
>
> 但注意：`BackgroundTasks` 默认在**响应发送后立即同步执行**（对用户仍是"等响应完成后立刻跑"）。MVP 单用户可接受；若响应后后台任务偶发拖慢 worker，可改为显式 `asyncio.create_task` + 任务引用持有，或引入独立 worker 进程（见 §六 演进）。

### 3.4 LLM 错误处理（后台任务内）

后台任务中的 LLM 错误不再能被前端 toast 直接捕获。处理口径：

| 场景 | 后台处理 |
|------|---------|
| LLM 超时 504 | 记录日志，本次保存静默丢弃（可后续重试/补录） |
| LLM 不可用 503 | 记录日志，静默丢弃 |
| LLM 响应无效 502（重试 1 次仍失败） | 记录日志，静默丢弃 |

- 复用 `save_notes` 内已有的 `AppError` 抛错逻辑，在后台任务外层 `try/except AppError` 捕获并记日志，不向上传播导致任务崩溃。
- 前端不感知失败（乐观反馈已给）；用户可通过刷新列表页发现"没记上"，可再次点击重存。

> 取舍说明：MVP 不引入"保存失败任务表 + 重试队列"。日志留痕、可手动重试，成本最低且满足"自用优先"定位。

### 3.5 依赖注入注意

- `get_llm_client()`（`llm_client.py:139`）只读 `get_settings()`（mock/real 判断），**不依赖请求作用域**，可直接在后台任务协程内调用解析客户端。无需重构。

### 3.6 response_model（`schemas/note.py`）

新增 `NoteSaveAccepted`：

```python
class NoteSaveAccepted(BaseModel):
    accepted: bool
```

原 `SaveNoteResponse`/`SavedNoteItem` 仍在 `note_service.save_notes` 内部使用（返回值用于测试/日志），仅路由响应模型从 `SaveNoteResponse` 切换为 `NoteSaveAccepted`。

## 四、对前序文档的关系

| 文档 | 本设计的影响 |
|------|-------------|
| `notes-feature-design.md`（08-29） | §4.1 `POST /notes/save` 返回结构改为 §3.2 的 accepted；§5.4 前端触发流程补充"乐观反馈 + 后台入账"；§六 错误处理改为"后台记日志，不 toast" |
| `notes-examples-dedup-design.md`（08-30） | 生成契约（examples+references+correction 匹配、去重）**全部保留**，仅把执行从同步挪到异步 |

## 五、验收标准

- AC-N-01：纠错提示词不再要求/产出 learnings 字段。
- AC-N-02：纠错报告响应不再包含 learnings；前端「学到的规则」分区移除。
- AC-N-03：`POST /notes/save` 返回 HTTP 202 + `{accepted:true}`，响应时间不依赖 LLM 生成。
- AC-N-04：点击"记笔记"后前端立即反馈（按钮变"已记录"禁用态 + 提示），不等 LLM。
- AC-N-05：后台任务完成规则生成与入库后，刷新笔记列表页能查到新笔记/新案例。
- AC-N-06：去重逻辑不变——同一用户同 source_text+同 fragment 不重复入库。
- AC-N-07：LLM 失败时后台记日志、不崩溃、不 block 用户；列表页保持原状。

## 六、未来演进

1. **独立 worker**：若后台任务拖慢 ASGI 事件循环，拆独立进程/队列（Celery/RQ/arq），`POST /notes/save` 投递消息即返。
2. **失败重试**：引入保存任务表 + 重试，失败可前台提示或自动补录。
3. **移除纠错 learnings 后续**：评估脚本 `backend/app/scripts/prompt_model_compare.py` / `prompt_thinking_compare.py` 中的 learnings 计数逻辑（`_summarize_result`）随提示词收敛一并清理；`golden_cases.json` 的 `ref_learnings_min` key 已失去意义（learnings 不再产出），评估改为只看 errors 命中率。

---

**变更记录**

- V0.1 · 2026-08-30 · 初稿：纠错移除 learnings + 笔记保存异步化（同步成功码 + 后台入账，BackgroundTasks，去重不变）