# 多轮追问 + Checkpointer + Span 校验 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 在同一 `thread_id` 下同时支持“新文本纠错”和“针对已有错误追问”，用 span/error_id 让重复片段可指代，用 checkpointer 让追问跳过定位。

**Architecture:** 顶层图 `route → reset/error_locate/validate/rewrite` 或 `route → explain`，图在首次请求时编译并共享 `MemorySaver`。`/api/v1/chat/stream` 是唯一入口；SSE 增加 `thread`、`intent`、`explanation`。本轮不拆编译子图，用扁平图 + 逻辑分支降低流式映射复杂度。

**Tech Stack:** Python 3.12、FastAPI、Pydantic v2、LangGraph 1.2.24、`MemorySaver`、httpx、React 19、TypeScript、Playwright。

**Spec:** `docs/superpowers/specs/2026-11-22-followup-checkpointer-design.md`

## Global Constraints

- 单入口：只使用 `POST /api/v1/chat/stream`，不新增 followup 端点。
- 本轮只做 `correct` / `followup` 两种意图；笔记、复习只预留。
- `MemorySaver` 仅本地单进程 MVP；重启/多 worker 丢状态，文档必须标注。
- 不做认证、限流、DB 落库、历史、笔记生成、逐条错误流式。
- 错误模型输出：`category / fragment / span_start / span_end / correction / explanation`。
- `span_start` 0-based，`span_end` exclusive；span 只是提示，最终由后端按 `fragment` 校正。
- `error_id` 由后端生成：按最终 span 排序后 `e1/e2/...`。
- 不引入 `occurrence`，不引入 `confidence`，`category` 就是 `error_type`。
- 追问不经过 `error_locate`；`explain` 只解释，不做局部改写。
- 流式节点参数保持：locate `high/0.1`，minimal `low/0.1`，fluency `low/0.3`；explain 用 `low/0.2`。
- 后端命令在 `backend/` 下执行，前端命令在 `web/` 下执行；Node 24。
- 提交格式：`type(scope): 中文描述`。

## Review Focus

- **模型 span 差一位或指到重复片段的另一处**：后端必须按 `fragment` 校正；无法唯一确定时丢弃并记录，不能猜。
- **同一 span 出现冲突修正**：重叠消解后只能保留一条可被 `error_id` 指代的错误，避免追问歧义。
- **新纠错与追问共用线程**：新纠错必须清空旧 errors/改写，追问必须保留旧 errors，且不调用 `error_locate`。
- **不同 `thread_id` 状态隔离**：A 线程的追问不能读到 B 线程的错误。
- **无 checkpoint / 无 errors 的追问**：必须返回明确错误，不能退化成重新定位。
- **SSE 顺序与前端状态**：`thread → intent → ... → done`；追问不能渲染成纠错报告，新纠错不能被旧解释覆盖。

---

### Task 1: Span 校正、稳定 error_id、重叠消解

**Files:**
- Modify: `backend/app/prompts/locate_prompt.py`
- Modify: `backend/app/services/error_validation.py`
- Modify: `backend/app/services/llm_client.py`（只改 `_default_responder` 的 locate JSON）
- Modify: `backend/tests/test_error_validation.py`
- Modify: `backend/tests/test_chat_prompts.py`
- Modify: `backend/tests/test_chat_graph.py`（期望错误对象补 `error_id/span`）

**Interfaces:**
- Consumes: `CANONICAL_CATEGORIES`。
- Produces:
  - `validate_errors(raw_errors: Any, text: str, *, request_id: str = "-") -> list[dict[str, Any]]`
  - 每条返回包含：`error_id`、`category`、`fragment`、`correction`、`explanation`、`span_start`、`span_end`。
- 模型输出新增 `span_start`/`span_end`；不新增 occurrence。

- [x] **Step 1: 改写现有校验测试**

`backend/tests/test_error_validation.py` 的现有断言要改为包含 `error_id/span`。新增用例：

```python
TEXT = "Yesterday I go to school."

def test_unique_fragment_gets_span_and_error_id():
    raw = [{"category": "时态错误", "fragment": "go", "correction": "went",
            "explanation": "x", "span_start": 0, "span_end": 0}]
    result = validate_errors(raw, TEXT)
    start = TEXT.index("go")
    assert result == [{
        "error_id": "e1", "category": "时态错误", "fragment": "go",
        "correction": "went", "explanation": "x",
        "span_start": start, "span_end": start + 2,
    }]

def test_missing_span_uses_unique_fragment():
    raw = [{"category": "时态错误", "fragment": "go", "correction": "went",
            "explanation": "x"}]
    assert validate_errors(raw, TEXT)[0]["error_id"] == "e1"

def test_duplicate_fragment_uses_span_hint():
    text = "I go now and I go later."
    second = text.index("go", text.index("go") + 1)
    raw = [{"category": "时态错误", "fragment": "go", "correction": "went",
            "explanation": "x", "span_start": second, "span_end": second + 2}]
    result = validate_errors(raw, text)
    assert result[0]["span_start"] == second

def test_duplicate_fragment_without_span_is_dropped():
    text = "I go now and I go later."
    raw = [{"category": "时态错误", "fragment": "go", "correction": "went",
            "explanation": "x"}]
    assert validate_errors(raw, text) == []

def test_overlap_keeps_larger_span():
    text = "She go to school yesterday."
    raw = [
        {"category": "时态错误", "fragment": "She go to school yesterday",
         "correction": "She went to school yesterday", "explanation": "x",
         "span_start": 0, "span_end": len("She go to school yesterday")},
        {"category": "主谓不一致", "fragment": "She go",
         "correction": "She goes", "explanation": "y", "span_start": 0, "span_end": 6},
    ]
    result = validate_errors(raw, text)
    assert len(result) == 1
    assert result[0]["fragment"] == "She go to school yesterday"

def test_emoji_span_uses_python_codepoints():
    text = "I 😀 go now."
    raw = [{"category": "时态错误", "fragment": "go", "correction": "went",
            "explanation": "x"}]
    start = text.index("go")
    assert validate_errors(raw, text)[0]["span_start"] == start
```

同时保留并更新现有的幻觉、非法 category、删除类 correction、去重、空输入测试。

- [x] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_error_validation.py -v`
Expected: FAIL，返回对象缺少 `error_id/span` 或 span 未校正

- [x] **Step 3: 实现 span 校正与 error_id**

`validate_errors` 按以下顺序：

1. 基本校验：`fragment` 非空、`category` 合法、`correction` 合法、`explanation` 非空。
2. 计算 `fragment` 的所有出现位置。
3. span 采用顺序：
   - 合法且 `text[start:end] == fragment` → 直接采用
   - 只有一个匹配 → 采用
   - 多个匹配 → 选离模型 `span_start` 最近的；距离阈值 `max(2, len(fragment))`；唯一最近才采用
   - 无匹配 / 多个等距 → 丢弃并 `logging.warning`
4. 强制重算 `span_end = span_start + len(fragment)`。
5. 去重键改为 `(span_start, span_end, correction, category)`。
6. 按 `span_start` 升序、`span_end` 降序排序。
7. 重叠消解：保留覆盖更大的 span；被覆盖且修正冲突的小 span 丢弃；同 span 冲突保留排序靠前的一条。
8. 分配 `error_id = e1/e2/...`。

- [x] **Step 4: 更新提示词**

`locate_prompt.py` 的输出 schema 增加：

```json
"span_start": "<integer, 0-based>",
"span_end": "<integer, exclusive>"
```

并在 HARD RULES 写明：span 应尽量覆盖 `fragment`；不确定时给最佳估计，后端会校正。更新 `test_chat_prompts.py` 断言 `"span_start"`/`"span_end"` 存在。

同时更新 `_default_responder` 的 locate JSON，补上 span（可给 `0/0`，由校验校正）。

- [x] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_error_validation.py tests/test_chat_prompts.py -v`
Expected: 全 PASS

- [x] **Step 6: 提交**

```bash
git add backend/app/prompts/locate_prompt.py backend/app/services/error_validation.py backend/app/services/llm_client.py backend/tests/test_error_validation.py backend/tests/test_chat_prompts.py backend/tests/test_chat_graph.py
git commit -m "feat(chat): span 校正、error_id 与重叠消解"
```

---

### Task 2: 路由、重置、追问节点与 explain 提示词

**Files:**
- Modify: `backend/app/graph/state.py`
- Modify: `backend/app/graph/nodes.py`
- Create: `backend/app/prompts/explain_prompt.py`
- Modify: `backend/app/services/llm_client.py`（Mock 增加 explain 分支）
- Modify: `backend/tests/chat_fakes.py`
- Modify: `backend/tests/test_chat_graph.py`
- Modify: `backend/tests/test_chat_prompts.py`

**Interfaces:**
- Consumes: `validate_errors`、`LLMClient`。
- Produces:
  - `route_node(state: CorrectionState) -> dict[str, Any]`
  - `resolve_target_node(state: CorrectionState) -> dict[str, Any]`
  - `reset_correction_node(state: CorrectionState) -> dict[str, Any]`
  - `make_explain_node(client: LLMClient)`
  - `build_explain_messages(turns, question, turn_id, error_id) -> list[dict[str, str]]`
- `CorrectionState` 扩展为本轮的 chat state，新增：`content`、`question`、`hint_intent`、`turn_id`、`error_id`、`intent`、`turns`、`turn_seq`、`current_turn_id`、`resolution_status`、`resolved_turn_id`、`resolved_error_id`、`candidate_refs`、`target_error`、`explanation`、`explanation_turn_id`、`explanation_error_id`、`explanation_error`、`thread_id`。
- `turns` 为最近 10 轮：`list[{turn_id, text, errors}]`。
- `text` 仍表示“被纠错的原文”；`content` 是当前轮用户输入。

- [x] **Step 1: 写路由测试**

```python
def test_route_explicit_followup():
    state = {"content": "为什么", "hint_intent": "followup", "errors": [{"error_id": "e1"}]}
    assert route_node(state)["intent"] == "followup"

def test_route_no_errors_is_correct():
    assert route_node({"content": "I go to school."})["intent"] == "correct"

def test_route_question_with_errors_is_followup():
    state = {"content": "第二个为什么这么改？", "errors": [{"error_id": "e1"}, {"error_id": "e2"}]}
    assert route_node(state)["intent"] == "followup"

def test_route_english_sentence_with_errors_is_correct():
    state = {"content": "She go to school.", "errors": [{"error_id": "e1"}]}
    assert route_node(state)["intent"] == "correct"

def test_route_error_id_forces_followup():
    state = {"content": "解释一下", "error_id": "e2", "errors": [{"error_id": "e1"}]}
    assert route_node(state)["intent"] == "followup"

def test_resolve_target_direct_by_explicit_ref():
    assert resolve_target_node({
        "turns": TURNS, "turn_id": "t1", "error_id": "e1", "content": "解释",
    }) == {
        "resolution_status": "direct",
        "resolved_turn_id": "t1",
        "resolved_error_id": "e1",
        "candidate_refs": [],
        "target_error": None,
    }

def test_resolve_target_pair_match():
    result = resolve_target_node({
        "turns": TURNS, "content": "为什么 go 改成 went？",
    })
    assert result["resolution_status"] == "unique"
    assert (result["resolved_turn_id"], result["resolved_error_id"]) == ("t1", "e1")

def test_resolve_target_ambiguous_returns_candidates():
    turns = [
        {"turn_id": "t1", "text": TEXT, "errors": [{"error_id": "e1", "fragment": "go", "correction": "went"}]},
        {"turn_id": "t2", "text": TEXT, "errors": [{"error_id": "e1", "fragment": "go", "correction": "goes"}]},
    ]
    result = resolve_target_node({"turns": turns, "content": "为什么 go 要改？"})
    assert result["resolution_status"] == "ambiguous"
    assert result["candidate_refs"] == ["t2:e1", "t1:e1"]  # 最近轮次优先

def test_resolve_target_none_when_no_match():
    result = resolve_target_node({"turns": TURNS, "content": "为什么 xxx 要改？"})
    assert result["resolution_status"] == "none"
    assert result["candidate_refs"] == []
```

- [x] **Step 2: 写 explain 节点测试**

在 `chat_fakes.py` 增加 `EXPLAIN_MARKER` 和 `explain` 参数；`ScriptedLLMClient` 识别 `TASK: EXPLAIN_ERROR`。

```python
EXPLAIN_OK = '{"text": "go 是过去时间，所以用 went。", "turn_id": "t1", "error_id": "e1"}'

TURNS = [{
    "turn_id": "t1",
    "text": TEXT,
    "errors": [{"error_id": "e1", "category": "时态错误", "fragment": "go",
                "correction": "went", "explanation": "x", "span_start": 12, "span_end": 14}],
}]

async def test_explain_uses_selected_error():
    fake = ScriptedLLMClient(locate=LOCATE_OK, explain=EXPLAIN_OK)
    node = make_explain_node(fake)
    result = await node({
        "turns": TURNS,
        "question": "为什么？",
        "resolution_status": "direct",
        "resolved_turn_id": "t1",
        "resolved_error_id": "e1",
        "candidate_refs": [],
    })
    assert result["explanation"] == "go 是过去时间，所以用 went。"
    assert result["explanation_turn_id"] == "t1"
    assert result["explanation_error_id"] == "e1"

async def test_explain_resolves_by_fragment_across_turns():
    fake = ScriptedLLMClient(locate=LOCATE_OK, explain=EXPLAIN_OK)
    result = await make_explain_node(fake)({
        "turns": TURNS,
        "question": "为什么 go 改成 went？",
        "resolution_status": "unique",
        "resolved_turn_id": "t1",
        "resolved_error_id": "e1",
        "candidate_refs": [],
    })
    assert result["explanation_error_id"] == "e1"

async def test_explain_without_history_returns_error():
    fake = ScriptedLLMClient(locate=LOCATE_OK)
    result = await make_explain_node(fake)({"turns": [], "question": "为什么"})
    assert result["explanation_error"]

async def test_explain_invalid_resolved_ids_returns_error():
    fake = ScriptedLLMClient(locate=LOCATE_OK, explain='{"text": "x", "turn_id": "t9", "error_id": "e9"}')
    result = await make_explain_node(fake)({
        "turns": TURNS,
        "question": "为什么",
        "resolution_status": "direct",
        "resolved_turn_id": "t1",
        "resolved_error_id": "e1",
        "candidate_refs": [],
    })
    assert result["explanation_error"]
```

- [x] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_chat_graph.py -v`
Expected: FAIL，`route_node` / `make_explain_node` 不存在

- [x] **Step 4: 实现状态、路由、重置、explain**

- `state.py` 增加字段；`text` 保持“原文”，`content` 是当前输入。
- `route_node` 规则顺序：
  1. `hint_intent` 为 `correct`/`followup` → 使用
  2. 有 `turn_id` 或 `error_id` → `followup`
  3. 无 `turns`/`errors` → `correct`
  4. `_looks_like_followup(content)` → `followup`（中文疑问/指代 + 中文占比高）
  5. 其他 → `correct`
  返回 `{"intent": ..., "question": content if followup else ""}`。
- `resolve_target_node`：
  - 显式 `turn_id + error_id` 在 `turns` 中存在 → `direct`
  - 只有 `error_id` → 最新轮查找 → `direct`；找不到 → `none`
  - 显式引用找不到 → `resolution_status="none"` + `target_error="找不到指定的错误条目"`
  - 无显式 ID → 在 `turns` 中按问题里的 `fragment`/`correction` 匹配 pair/单边
  - 唯一 → `unique`；多个 → `ambiguous` + `candidate_refs`（最近轮次优先）；无 → `none`
  - 不调用 LLM
- `reset_correction_node`：`text=content`；`turn_seq += 1`；`current_turn_id=f"t{turn_seq}"`；清空 latest `errors`/改写/解释，但保留 `turns`。
- `validate_errors` 完成后：append `{turn_id: current_turn_id, text, errors}` 到 `turns`；裁剪最近 10 轮；返回更新包含 `turn_id`，供 SSE `errors` 事件使用。
- `explain_prompt.py`：系统消息含 `TASK: EXPLAIN_ERROR`；输入最近 10 轮 `turns`（带 `turn_id/error_id`）+ 可选目标 + 问题；输出 `{"text": "...", "turn_id": "t2", "error_id": "e2"}`；要求不新增错误、不改写原文、无法确定时反问、可评估替代写法但不应用。
- `make_explain_node`：
  - 无 `turns` → `explanation_error="没有可追问的错误"`
  - `resolution_status` 为 `direct`/`unique` → 只解释 `resolved_*`
  - `ambiguous` → 提示词带 `candidate_refs`，要求选择或反问
  - `none` → 允许在最近 10 轮语义兜底；仍无法确定则反问
  - 调用 `thinking=True, json_mode=True, reasoning_effort="low", temperature=0.2`
  - 解析结果后回查 `turns`；`turn_id/error_id` 不合法 → 改为反问或 `explanation_error`
  - 异常 → `explanation_error="解释生成失败"`
- `_default_responder` 增加 `TASK: EXPLAIN_ERROR` 分支，返回固定解释和 `turn_id/error_id`。

- [x] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_chat_graph.py tests/test_chat_prompts.py tests/test_llm_client.py -v`
Expected: 全 PASS

- [x] **Step 6: 提交**

```bash
git add backend/app/graph/state.py backend/app/graph/nodes.py backend/app/prompts/explain_prompt.py backend/app/services/llm_client.py backend/tests/chat_fakes.py backend/tests/test_chat_graph.py backend/tests/test_chat_prompts.py
git commit -m "feat(chat): 增加意图路由与追问解释节点"
```

---

### Task 3: 顶层图 + MemorySaver + 图提供者

**Files:**
- Modify: `backend/app/graph/build.py`
- Modify: `backend/app/routers/chat.py`（增加 `get_chat_graph`）
- Modify: `backend/tests/test_chat_graph.py`
- Modify: `backend/tests/test_chat_graph.py` 的 `ScriptedLLMClient` 使用方式

**Interfaces:**
- Produces:
  - `build_graph(client: LLMClient, checkpointer: BaseCheckpointSaver | None = None)`
  - `get_chat_graph(request: Request)`，首次请求构建并缓存到 `request.app.state.chat_graph`
- 顶层图节点：`route`、`reset_correction`、`error_locate`、`validate_errors`、`minimal_edit`、`minimal_passthrough`、`native_fluency`、`resolve_target`、`explain`。
- 条件边：`route` → `reset_correction` / `resolve_target`；`resolve_target` → `explain`；`validate_errors` → minimal 分支 + fluency。

- [x] **Step 1: 更新现有图测试并写 checkpointer 测试**

现有 `test_chat_graph.py` 里的 `ainvoke({"text": TEXT, ...})` 改为 `ainvoke({"content": TEXT, ...})`；`text` 由 `reset_correction` 写入。保留 `request_id`。

```python
from langgraph.checkpoint.memory import MemorySaver

async def test_followup_reuses_errors_without_locate():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    graph = build_graph(fake, MemorySaver())
    config = {"configurable": {"thread_id": "t1"}}
    await graph.ainvoke({"content": TEXT}, config=config)
    fake.calls.clear()
    result = await graph.ainvoke(
        {"content": "为什么 go 改成 went？"}, config=config
    )
    assert result["intent"] == "followup"
    assert result["explanation"] == "go 是过去时间，所以用 went。"
    assert result["explanation_turn_id"] == "t1"
    assert result["explanation_error_id"] == "e1"
    assert result["turns"]
    assert "locate" not in fake.calls

async def test_new_correction_clears_old_errors():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    graph = build_graph(fake, MemorySaver())
    config = {"configurable": {"thread_id": "t2"}}
    await graph.ainvoke({"content": TEXT}, config=config)
    fake.locate = '{"errors":[{"category":"主谓不一致","fragment":"She go","correction":"She goes","explanation":"第三人称单数","span_start":0,"span_end":6}]}'
    result = await graph.ainvoke({"content": "She go home."}, config=config)
    assert result["intent"] == "correct"
    assert result["errors"][0]["fragment"] == "She go"
    assert result["errors"][0]["error_id"] == "e1"
    assert result["explanation"] in (None, "")

async def test_history_keeps_last_ten_turns():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    graph = build_graph(fake, MemorySaver())
    config = {"configurable": {"thread_id": "t3"}}
    for _ in range(11):
        await graph.ainvoke({"content": TEXT}, config=config)
    state = await graph.aget_state(config)
    assert len(state.values["turns"]) == 10
    assert state.values["turns"][0]["turn_id"] == "t2"
    assert state.values["turns"][-1]["turn_id"] == "t11"

async def test_threads_are_isolated():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    graph = build_graph(fake, MemorySaver())
    await graph.ainvoke({"content": TEXT}, config={"configurable": {"thread_id": "a"}})
    result = await graph.ainvoke(
        {"content": "为什么？", "error_id": "e1"}, config={"configurable": {"thread_id": "b"}}
    )
    assert result["intent"] == "followup"
    assert result["explanation_error"]
```

- [x] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_chat_graph.py -v`
Expected: FAIL，`build_graph` 不接受 checkpointer / 没有 route 分支

- [x] **Step 3: 实现顶层图**

- `build_graph(client, checkpointer=None)` 使用 `StateGraph(CorrectionState)`，加入全部节点。
- `route` 条件边返回 `"correct"`/`"followup"`，映射到 `reset_correction`/`resolve_target`。
- `resolve_target → explain`；`resolve_target` 不清空 `turns`。
- `reset_correction → error_locate → validate_errors`；`validate_errors` 保留条件边 + 普通边到 fluency。
- 所有终端连 `END`。
- `compile(checkpointer=checkpointer)`。
- `chat.py` 增加：

```python
def get_chat_graph(request: Request):
    graph = getattr(request.app.state, "chat_graph", None)
    if graph is None:
        graph = build_graph(get_llm_client(), MemorySaver())
        request.app.state.chat_graph = graph
    return graph
```

- [x] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_chat_graph.py -v`
Expected: 全 PASS

- [x] **Step 5: 提交**

```bash
git add backend/app/graph/build.py backend/app/routers/chat.py backend/tests/test_chat_graph.py
git commit -m "feat(chat): 顶层路由图与 MemorySaver"
```

---

### Task 4: 单入口 SSE 契约与 thread/intent/explanation

**Files:**
- Modify: `backend/app/schemas/chat.py`
- Modify: `backend/app/services/chat_stream.py`
- Modify: `backend/app/routers/chat.py`
- Modify: `backend/tests/test_chat_stream.py`
- Modify: `backend/tests/test_chat_stream_api.py`

**Interfaces:**
- Consumes: `get_chat_graph`、`events_from_update`、`format_sse`。
- Produces:
  - `ChatRequest` 增加 `thread_id: str | None`、`intent: Literal["correct", "followup"] | None`、`turn_id: str | None`、`error_id: str | None`。
  - `stream_chat_events(content, graph, request, *, thread_id, intent, turn_id, error_id) -> AsyncIterator[str]`
  - 事件：`thread`、`intent`、`errors`、`minimal`、`fluency`、`rewrite_degraded`、`explanation`、`error`、`done`。

- [x] **Step 1: 写 SSE 契约测试**

在 `test_chat_stream.py` 增加：

```python
def test_route_update_maps_to_intent():
    assert events_from_update("route", {"intent": "followup"}) == [
        ("intent", {"intent": "followup"})
    ]

def test_explain_update_maps_to_explanation():
    assert events_from_update(
        "explain",
        {"explanation": "因为...", "explanation_turn_id": "t2", "explanation_error_id": "e3"},
    ) == [
        ("explanation", {"text": "因为...", "turn_id": "t2", "error_id": "e3"})
    ]

def test_explain_error_maps_to_error():
    assert events_from_update("explain", {"explanation_error": "没有可追问的错误"}) == [
        ("error", {"code": "EXPLAIN_FAILED", "message": "没有可追问的错误"})
    ]
```

在 `test_chat_stream_api.py` 增加：

```python
async def test_stream_emits_thread_and_intent():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    app = _app(fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/chat/stream", json={"content": TEXT})
    names = [e for e, _ in _events(r.text)]
    assert names[0] == "thread"
    assert names[1] == "intent"
    assert names[-1] == "done"

async def test_stream_followup_uses_same_thread():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    app = _app(fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        first = await c.post("/api/v1/chat/stream", json={"content": TEXT})
        thread_id = next(payload["thread_id"] for e, payload in _events(first.text) if e == "thread")
        fake.calls.clear()
        second = await c.post(
            "/api/v1/chat/stream",
            json={"content": "为什么 go 改成 went？", "thread_id": thread_id, "turn_id": "t1", "error_id": "e1"},
        )
    events = _events(second.text)
    names = [e for e, _ in events]
    assert names == ["thread", "intent", "explanation", "done"]
    assert events[1][1]["intent"] == "followup"
    assert fake.calls == ["explain"]
```

- [x] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_chat_stream.py tests/test_chat_stream_api.py -v`
Expected: FAIL，事件不存在或请求 schema 不接受新字段

- [x] **Step 3: 实现 schema、事件映射、流函数**

- `ChatRequest` 增加字段；`thread_id` 限制 `^[A-Za-z0-9_-]{1,64}$`，`error_id` 限制 `^e\d+$`。
- `events_from_update` 增加：
  - `route` → `intent`
  - `validate_errors` → `errors`，payload 增加 `turn_id`
  - `explain` → `explanation`（带 `turn_id/error_id`）
  - `explain` 的 `explanation_error` → `error` `EXPLAIN_FAILED`
- `stream_chat_events`：
  - 参数改为 `content, graph, request, *, thread_id, intent, error_id`
  - 先 `yield format_sse("thread", {"thread_id": thread_id})`
  - 输入 `{"content": content, "hint_intent": intent, "turn_id": turn_id, "error_id": error_id, "thread_id": thread_id}`
  - `config={"configurable": {"thread_id": thread_id}}`
  - 跟踪 `intent`、`has_errors`，`done` 发送 `{"intent": intent, "has_errors": has_errors}`
  - 心跳/300 秒超时/断连取消保持
- `chat.py` 端点：
  - 生成或使用 `thread_id`
  - 注入 `graph = Depends(get_chat_graph)`
  - 调用 `stream_chat_events(...)`
- 测试 `_app(fake)` 改成：

```python
from langgraph.checkpoint.memory import MemorySaver
app.state.chat_graph = build_graph(fake, MemorySaver())
```

- 现有 API 测试的事件断言要更新：`names[0]` 从 `errors` 改为 `thread`，`names[1]` 为 `intent`；`done` 仍在最后。`errors` payload 增加 `turn_id`。现有断连测试改为先构建 graph，再调用新的 `stream_chat_events` 签名。

- [x] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_chat_stream.py tests/test_chat_stream_api.py -v`
Expected: 全 PASS

- [x] **Step 5: 提交**

```bash
git add backend/app/schemas/chat.py backend/app/services/chat_stream.py backend/app/routers/chat.py backend/tests/test_chat_stream.py backend/tests/test_chat_stream_api.py
git commit -m "feat(chat): 单入口 SSE 支持 thread、intent 与追问解释"
```

---

### Task 5: 前端追问交互与 E2E

**Files:**
- Modify: `web/src/api/chat.ts`
- Modify: `web/src/components/correction/ErrorCard.tsx`
- Modify: `web/src/pages/StreamCorrectionPage.tsx`
- Modify: `web/tests/e2e/stream.spec.ts`

**Interfaces:**
- `ChatError` 增加 `error_id: string`、`span_start: number`、`span_end: number`
- `ChatEvent` 增加/修改：
  - `{type:'thread'; thread_id:string}`
  - `{type:'intent'; intent:'correct'|'followup'}`
  - `{type:'errors'; turn_id:string; has_errors:boolean; errors:ChatError[]}`
  - `{type:'explanation'; text:string; turn_id:string|null; error_id:string|null}`
- `done` 事件类型改为 `{type:'done'; intent:'correct'|'followup'; has_errors:boolean}`
- `streamCorrection(..., options?: {threadId?:string; intent?:'correct'|'followup'; turnId?:string; errorId?:string})`
- `ErrorCard` 增加可选 `onAsk?: () => void`，渲染“追问这条”按钮。
- 前端保留 `reports: Array<{turnId, text, errors}>`，最多 10 轮；追问时传 `turnId + errorId`。

- [x] **Step 1: 写失败 E2E**

```ts
test('U-S-03 纠错后追问返回解释', async ({ page }) => {
  await page.goto('/stream')
  await page.getByPlaceholder('输入英文，开始流式纠错').fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '开始' }).click()
  await expect(page.getByTestId('stream-errors')).toContainText('时态错误')
  await page.getByRole('button', { name: '追问这条' }).first().click()
  await page.getByPlaceholder('输入追问，例如：为什么这么改？').fill('为什么这么改？')
  await page.getByRole('button', { name: '发送追问' }).click()
  await expect(page.getByTestId('stream-explanation')).toContainText('go 是过去时间')
})

test('U-S-04 跨轮自由追问按片段解析', async ({ page }) => {
  await page.goto('/stream')
  const input = page.getByPlaceholder('输入英文，开始流式纠错')
  await input.fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '开始' }).click()
  await expect(page.getByTestId('stream-errors')).toContainText('时态错误')
  await input.fill('She go to work.')
  await page.getByRole('button', { name: '开始' }).click()
  await expect(page.getByTestId('stream-errors').last()).toBeVisible()
  await page.getByPlaceholder('输入追问，例如：为什么这么改？').fill('为什么 go 改成 went？')
  await page.getByRole('button', { name: '发送追问' }).click()
  await expect(page.getByTestId('stream-explanation')).toContainText('go 是过去时间')
})
```

- [x] **Step 2: 运行确认失败**

Run: `npm run test:e2e -- --grep "U-S-03"`
Expected: FAIL，按钮/输入框不存在

- [x] **Step 3: 实现前端**

- `chat.ts` 事件解析增加 `thread`/`intent`/`explanation`；`streamCorrection` 请求体附带 `thread_id`/`intent`/`error_id`。
- `ErrorCard` 增加“追问这条”按钮，点击回调。
- `StreamCorrectionPage`：
  - 保存 `threadId`、`reports`（最近 10 轮）、`selectedTurnId`、`selectedErrorId`、`followupText`、`explanation`。
  - `thread` 事件保存 threadId。
  - `intent` 事件：`followup` 时设置 phase=`followup`；`correct` 时正常。
  - `errors` 事件把本轮 `{turnId, text, errors}` 追加到 `reports`，最多 10 轮。
  - 点击任意一轮错误卡片设置 `selectedTurnId + selectedErrorId`，追问输入框聚焦。
  - 发送追问时传 `{threadId, intent:'followup', turnId, errorId}`。
  - 自由追问不传 turnId/errorId，由后端按历史解析。
  - `explanation` 事件渲染 `data-testid="stream-explanation"` 卡片，并显示解析到的轮次/错误。
  - 新纠错追加报告，不清空历史；只清空 `explanation`/选中项。
  - `done` 事件按 `intent` 收尾；错误不能被 done 覆盖。
- Mock 默认响应增加 `TASK: EXPLAIN_ERROR` 固定解释，保证 E2E 通过。

- [x] **Step 4: 运行 lint、build、E2E**

Run: `npm run lint && npm run build`
Expected: 无错误

Run: `npm run test:e2e -- tests/e2e/stream.spec.ts --workers=1`
Expected: U-S-01/02/03/04 全 PASS

- [x] **Step 5: 提交**

```bash
git add web/src/api/chat.ts web/src/components/correction/ErrorCard.tsx web/src/pages/StreamCorrectionPage.tsx web/tests/e2e/stream.spec.ts
git commit -m "feat(web): 支持点击错误追问并渲染解释"
```

---

### Task 6: 文档、全量验证与真实冒烟

**Files:**
- Modify: `docs/superpowers/specs/2026-11-22-followup-checkpointer-design.md`（状态改“已实现”）
- Modify: `docs/superpowers/plans/2026-11-22-followup-checkpointer.md`（勾选）
- Optionally: `docs/superpowers/specs/2026-11-21-correction-stream-mvp-design.md`（补追问说明）

- [x] **Step 1: 更新文档状态**

- 设计文档状态改为 `已实现（2026-11-22）`。
- 明确写出：`MemorySaver` 仅本地单进程，重启/多 worker 丢状态，后续替换 `PostgresSaver`。
- 记录本轮仍不做笔记/复习/认证/DB。
- 记录 note 未来扩展：默认保存当前轮、独立 `resolve_note_scope`、本轮不复用 `resolve_target`、只预留不实现。

- [x] **Step 2: 跑全量后端测试**

Run: `pytest -q`
Expected: 全 PASS（含新增 span/route/checkpointer/SSE 测试）

- [x] **Step 3: 跑前端 lint、build、全量 E2E**

Run: `npm run lint && npm run build && npm run test:e2e`
Expected: 全 PASS；原有纠错/笔记/登录 E2E 不回归。

- [x] **Step 4: 真实模型手动冒烟**

用 GLM-5.3 当前配置：

```text
1. 输入 "She go to school yesterday and I very like it."
2. 确认 errors 包含 span/error_id
3. 点击第一条追问，问 "为什么这么改？"
4. 确认 explanation 引用了正确条目
5. 输入 "为什么 go 改成 went？" 不传 turn_id/error_id，确认跨轮解析到正确条目
6. 在同一线程输入新英文句子，再问 "为什么这里用 an？"，确认历史轮次仍可追问
7. 确认新纠错追加报告，不清空历史
8. 制造同一片段跨多轮出现，确认候选冲突时反问而不是猜
```

- [x] **Step 5: 提交**

```bash
git add docs/superpowers/specs/2026-11-22-followup-checkpointer-design.md docs/superpowers/plans/2026-11-22-followup-checkpointer.md
git commit -m "docs(chat): 记录多轮追问 MVP 实现与 MemorySaver 限制"
```

---

## 完成标准

- `pytest -q` 全绿，覆盖 span/error_id/overlap/route/checkpointer/SSE。
- `npm run lint && npm run build` 通过。
- `npm run test:e2e` 全绿，包含 U-S-03 追问。
- 真实 GLM-5.3 手动冒烟通过：纠错、点击追问、自由追问、新纠错清空旧状态。
- 文档明确 `MemorySaver` 仅 MVP，重启/多 worker 丢状态。
