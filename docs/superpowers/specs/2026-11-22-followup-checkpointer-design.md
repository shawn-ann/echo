# 多轮追问 + Checkpointer + Span 校验设计（下一轮）

**日期**：2026-11-22
**分支**：`feat/correction-stream-mvp`（后续可另开 `feat/followup`）
**状态**：已实现（2026-11-22）
**前置**：`2026-11-21-correction-stream-mvp-design.md` 的流式纠错 MVP

## 1. 意图

把当前“一次性纠错”升级为“同一会话内可纠错、可追问”的最小多轮闭环：

- 单入口 `/api/v1/chat/stream`，用户可以在同一对话里提交新文本或追问
- 顶层图用 `route` 判断意图，纠错与追问走不同分支
- 纠错子图沿用现有 `error_locate → validate_errors → minimal/fluency`
- 追问分支读取 checkpoint 中已有的 `errors`，**不重新定位**
- 保留最近 10 轮纠错历史，允许用户按原文片段/修正结果追问，不要求显式指定轮次
- 用 `MemorySaver` 保存线程状态，为后续 `PostgresSaver` 留出替换点

本轮不是通用 Agent：只有 `correct` / `followup` 两种意图，笔记、复习只预留枚举。

## 2. 目标 / 非目标

### 目标

- 同一 `thread_id` 下，追问不重跑 `error_locate`
- 错误条目有稳定 `error_id`、`span_start/span_end`
- 重复片段、重叠片段可校验、可消解、可指代
- 纠错请求继续走原流式链路；追问只走轻量 `explain`
- 前端可以点击某条错误追问，也可以自由输入追问
- 支持最近 10 轮内按 `fragment` / `correction` 自由引用，例如“为什么 go 改成 went”“为什么这里用 an”

### 非目标

- 不做笔记、复习、多轮学习计划
- 不做 DB 持久化；`MemorySaver` 仅本地单进程
- 不做认证、限流、历史回放
- 不做真正的逐条错误流式；`errors` 仍一次返回完整数组
- 不做局部 Fluency 重写；追问只解释
- 不做通用意图分类器；只做规则路由

## 3. 方案对比

| 方案 | 做法 | 优点 | 代价 | 结论 |
|---|---|---|---|---|
| A | 扁平顶层图：`route` + 条件边到纠错/追问节点组 | SSE 事件映射简单；checkpointer 直接生效 | 不是物理子图，后续拆分要重构 | **本轮选择** |
| B | 编译子图作为节点，嵌套流式 | 结构最清晰，便于多能力扩展 | 需要 `subgraphs=True` 和嵌套事件映射；checkpoint 配置更复杂 | 后续再拆 |
| C | 多接口（纠错 / 追问分开） | 实现最简单 | 偏离单入口智能体方向；前端要自己判断意图 | 不采纳 |

本轮选 A：逻辑上仍是“路由 + 两个能力分支”，物理上先用一个图，避免嵌套流式带来的调试成本。

## 4. 已确认决策

| # | 决策 | 结论 |
|---|---|---|
| D1 | 单入口 | 只用 `/api/v1/chat/stream` |
| D2 | 路由 | 规则优先：显式 `intent` / `error_id` → 规则 → 默认 correct |
| D3 | Checkpointer | `MemorySaver`，编译一次，单进程 MVP |
| D4 | `thread_id` | 请求可带；不带则服务端生成，SSE `thread` 事件返回 |
| D5 | Span | 模型输出 `span_start/span_end` 作为提示，后端以 `fragment` 为准校正 |
| D6 | `error_id` | 后端在 span 校正、去重、重叠消解后生成 `e1/e2...` |
| D7 | `occurrence` | 不引入；重复片段靠 span 提示 + fragment 校正 |
| D8 | 追问 | 只做解释，不重新定位、不做局部改写 |
| D9 | 事件 | 增加 `thread` / `intent` / `explanation` |
| D10 | 前端 | `/stream` 页增加追问输入和解释卡片 |

## 5. API 与 SSE 契约

### 请求

```http
POST /api/v1/chat/stream
Content-Type: application/json

{
  "content": "为什么 go 要改成 went？",
  "thread_id": "可选，首次不传则服务端生成",
  "intent": "correct | followup，可选",
  "turn_id": "可选，点击历史错误时传",
  "error_id": "可选，点击错误卡片时传"
}
```

- `content`：1–2000 字符
- `thread_id`：同一对话复用；新对话可新建
- `turn_id` + `error_id`：存在时优先判定为追问；默认最新一轮
- `intent`：显式意图优先于规则

### SSE 事件

| 事件 | 载荷 | 时机 |
|---|---|---|
| `thread` | `{thread_id}` | 流开始，最先发送 |
| `intent` | `{intent}` | route 完成后 |
| `errors` | `{turn_id, has_errors, errors[]}` | 纠错分支 validate 后 |
| `minimal` | `{text, note}` | Minimal 完成 |
| `fluency` | `{text, note}` | Fluency 完成 |
| `rewrite_degraded` | `{stage, message}` | 改写失败 |
| `explanation` | `{text, turn_id?, error_id?}` | 追问分支完成；带解析到的轮次/错误 |
| `error` | `{code, message}` | 终止错误 |
| `done` | `{intent}` | 正常结束 |

事件序列：

```text
纠错：thread → intent(correct) → errors → minimal/fluency → done
追问：thread → intent(followup) → explanation → done
错误：thread → intent → error → done
```

## 6. State 设计

```python
class TurnState(TypedDict):
    turn_id: str          # t1, t2...
    text: str
    errors: list[dict]    # 含 error_id/span/category/fragment/correction/explanation
    minimal_text: str
    minimal_note: str
    fluency_text: str
    fluency_note: str

class ChatState(TypedDict, total=False):
    thread_id: str
    content: str          # 当前轮用户输入
    question: str         # 追问文本
    hint_intent: str      # 请求显式 intent
    turn_id: str          # 追问目标轮次（显式）
    error_id: str         # 追问目标错误（显式）
    rewrite_variant: str  # 追问目标改写：minimal / fluency / both
    intent: str           # 本轮最终意图

    text: str             # 当前被纠错原文
    errors: list[dict]    # 最新一轮错误（兼容既有节点）
    has_errors: bool
    turns: list[TurnState]  # 最近 10 轮
    turn_seq: int          # 单调递增，避免 cap 后 ID 复用
    current_turn_id: str

    minimal_text: str
    minimal_note: str
    fluency_text: str
    fluency_note: str
    minimal_error: str | None
    fluency_error: str | None

    resolution_status: str      # direct / turn / rewrite / fuzzy / none
    resolved_turn_id: str | None
    resolved_error_id: str | None
    resolved_variant: str | None
    candidate_refs: list[str]   # 预留给后续，当前恒空
    target_error: str | None

    explanation: str
    explanation_turn_id: str | None
    explanation_error_id: str | None
    explanation_error: str | None
```

- `route` 写入 `intent`；correct 分支清空“最新一轮”字段，但**不清空 `turns`**
- `reset_correction` 设置 `text=content`、`turn_seq += 1`、`current_turn_id=f"t{turn_seq}"`
- `validate_errors` 在完成 span 校正后，把 `{turn_id, text, errors}` append 到 `turns`，并裁剪到最近 10 轮
- followup 保留 `turns`/`errors`，只写 `question`/`turn_id`/`error_id`/`explanation`
- 新纠错不会覆盖历史轮次；最新一轮 `errors` 只用于默认追问
- `thread_id` 同时通过 LangGraph config 传入，state 里保留一份便于事件输出

## 7. 图结构

```text
START
  │
  ▼
route（规则）
  │
  ├─ correct ──► reset_correction
  │                 │
  │                 ▼
  │            error_locate
  │                 │
  │                 ▼
  │            validate_errors
  │                 │
  │        ┌────────┴────────┐
  │        ▼                 ▼
  │   minimal_edit     native_fluency
  │        └────────┬────────┘
  │                 ▼
  │                END
  │
  └─ followup ──► resolve_target ──► explain ──► END
```

- `route` 只判断 correct/followup，不解析具体错误
- `resolve_target` 是纯代码节点，负责显式引用校验和历史匹配
- `explain` 只消费 `resolved_*` / `candidate_refs` / `turns`

- `reset_correction` 是纯代码节点，清空“最新一轮”字段并分配新 `turn_id`，但保留 `turns` 历史
- `validate_errors` 在 span 校正后把本轮 `{turn_id, text, errors}` append 到 `turns`，并裁剪到最近 10 轮
- `route` 是纯代码节点，不调用 LLM
- `explain` 是唯一新增 LLM 节点
- 顶层图编译一次，共享 `MemorySaver`

## 8. 路由规则

按顺序：

1. 请求显式 `intent` 合法 → 使用它
2. 请求带 `turn_id` 或 `error_id` → `followup`
3. 当前线程没有 `turns` / `errors` → `correct`
4. `content` 很短且包含追问标记 → `followup`
   - 中文疑问/指代：`为什么`、`怎么`、`如何`、`解释`、`这个`、`这条`、`第.个`、`有没有`、`更自然`、`换个说法`、`?`、`？`
   - 同时要求文本以中文为主，避免把英文新句子误判为追问
5. 其他 → `correct`

本轮不调用 LLM 做意图分类。后续笔记/复习加入时，扩展显式 `intent` 和规则；只有歧义时才考虑轻量模型兜底。

## 9. Span 校验与重叠消解

### 9.1 模型输出

提示词增加：

```json
{
  "category": "时态错误",
  "fragment": "go",
  "span_start": 12,
  "span_end": 14,
  "correction": "went",
  "explanation": "..."
}
```

- `span_start` 0-based，`span_end` exclusive
- span 只作为提示，不是真相
- 不再要求 `occurrence`

### 9.2 校验算法

1. 基本校验：`fragment` 非空；`category` 合法；`correction` 合法；`explanation` 非空；span 是整数。
2. 如果 `0 <= span_start < span_end <= len(text)` 且 `text[span_start:span_end] == fragment` → 采用。
3. 否则枚举 `fragment` 的所有出现位置：
   - 唯一匹配 → 采用，记录 `span_corrected`
   - 多个匹配 → 选离模型 `span_start` 最近的；距离阈值 `max(2, len(fragment))`；唯一最近才采用
   - 无匹配 / 多个等距 → 丢弃，记录 `span_ambiguous`
4. 采用后强制重算：

   ```text
   span_start = 匹配起点
   span_end = span_start + len(fragment)
   ```

5. 按 `(span_start, span_end, correction, category)` 去重。
6. 按 `span_start` 升序、`span_end` 降序排序，分配 `error_id = e1/e2/...`。
7. 重叠消解：
   - 后一个 span 与前一个重叠时，保留覆盖更大的；
   - 被覆盖且修正冲突的小 span 丢弃；
   - 同一 span 出现冲突修正时，保留排序更靠前的一条并记录；
   - 所有丢弃都写日志：`request_id / error_id / fragment / reason`。

### 9.3 索引单位

- 后端使用 Python code point 索引
- 前端本轮只用 `error_id` 追问；高亮功能延后
- 后续高亮时，后端返回 UTF-16 偏移或预切 segments

## 10. 追问目标解析与解释

### 10.1 `resolve_target`（纯代码）

输入：

- `turns`：最近 10 轮，每轮 `{turn_id, text, errors, minimal_*, fluency_*}`
- `turn_id` / `error_id` / `rewrite_variant`（均可空）
- 用户问题

输出：

```python
{
    "resolution_status": "direct" | "turn" | "rewrite" | "fuzzy" | "none",
    "resolved_turn_id": str | None,
    "resolved_error_id": str | None,
    "resolved_variant": "minimal" | "fluency" | "both" | None,
    "candidate_refs": [],          # 预留字段，当前恒为空
    "target_error": str | None,
}
```

顺序：

1. 显式 `turn_id`：
   - 该轮不存在 → `none` + `target_error`（`找不到指定的轮次` / `历史已超出范围`）
   - 同时给了 `error_id`：存在 → `direct`；不存在 → `none` + `target_error`
   - 否则 → `rewrite`（带 `rewrite_variant`）或 `turn`
2. 只有显式 `error_id`：在最近 10 轮中查找该错误 → `direct`；找不到 → `none` + `target_error`
3. 只有 `rewrite_variant`：目标为最新一轮 → `rewrite`
4. 都没有 → `fuzzy`：不解析、不猜测，把整段 `turns` 交给 explain 由模型定位

`resolve_target` 不调用 LLM，也不做正则匹配。代码只处理确定性引用
（UI 点选、显式 ID），自由文本的语言理解归模型。

### 10.2 `explain`

输入：

- `turns`（完整结构，含 errors 与两版改写；未来新增字段自动带入）
- `resolution_status`
- `resolved_turn_id` / `resolved_error_id` / `resolved_variant`
- 用户问题

输出：

```json
{
  "text": "为什么这么改的解释...",
  "turn_id": "t2",
  "error_id": "e2",
  "focus": {"kind": "error|rewrite|turn", "variant": "minimal|fluency|both|null"}
}
```

行为：

- `direct`：显式选中的错误是权威目标，模型返回的 `turn_id/error_id` 不一致 → 报错
- `turn` / `rewrite`：以用户给定的轮次和改写版本为准，模型返回的错误只做存在性校验
- `fuzzy`：模型自行在最近 10 轮里定位轮次、错误或改写；不合法时回退到最近一轮并写日志，**不因解析不一致而丢弃答案**
- 追问对象不限于错误：模型可对比原文、Minimal、Fluency，回答“为什么省略/简写/更自然/两版区别”
- 模型无法区分多个同等合理的解释时，才反问“你指的是哪一处？”

约束：

- 不重新纠错；不新增错误
- 不改变原文，不输出新的改写版本
- 可以评估替代写法（“改成 xxx 可以吗”），返回“可以/不可以 + 原因”；本轮不自动应用
- 使用 `thinking` 开启（GLM-5.3 无法关闭）+ `reasoning_effort=low` + `temperature=0.2`
- 失败时发 `explanation_error` / `error`，不阻塞线程状态
- `turns` 只保留最近 10 轮；更早的显式引用返回“历史已超出范围”

## 11. Checkpointer

- `MemorySaver` 在应用启动时创建，与图一起编译一次
- `thread_id` 通过 `config={"configurable": {"thread_id": ...}}` 传入
- 同一线程的 `route` 能看到上一轮的 `turns` / 最新 `errors`
- `MemorySaver` 只存在进程内：
  - 重启丢失
  - 多 worker 不共享
  - 本地 MVP 可接受
- 后续替换 `PostgresSaver`，state 结构不变

## 12. 前端

`/stream` 页增加最小追问能力：

- 收到 `thread` 事件后保存 `threadId`
- 前端保留最近 10 轮报告（turn_id + 原文 + errors）
- 每轮错误卡片增加“追问”按钮，点击时记录 `turn_id + error_id`
- 页面底部增加追问输入框；提交时走同一个 `/chat/stream`
- 不点击也可以自由输入“为什么 go 改成 went”；后端按历史解析
- 收到 `intent=followup` 后渲染解释卡片，显示解析到的轮次/错误
- `explanation` 事件追加到对话区
- 新一轮纠错追加报告，不清空历史；只清空旧解释和当前选中项
- 刷新即丢失（MemorySaver + 无前端持久化）

## 13. 测试

### 后端单元

- span 正确、差一位、越界、start>=end
- 重复 fragment 的 span 校正
- 多个等距候选 → 丢弃
- 幻觉 fragment → 丢弃
- 重叠消解：大 span 覆盖小 span、同 span 冲突
- `error_id` 排序稳定
- emoji / 非 BMP 文本不崩

### 图与 checkpointer

- 首次纠错建立线程，errors 写入 checkpoint/turns
- 追问不调用 `error_locate`
- 同一线程第二轮纠错追加新 turn，保留旧 turn
- 最近 10 轮裁剪：第 11 轮后最旧一轮被移除
- 按 `fragment` / `correction` 跨轮解析到正确 turn/error
- 多个候选时优先最近一轮，仍冲突则反问
- 不同 `thread_id` 状态隔离
- 无 checkpoint 的追问返回错误，不重新定位

### SSE

- 纠错：`thread → intent → errors → minimal/fluency → done`
- 追问：`thread → intent(followup) → explanation → done`
- 追问带 `error_id` 与不带 `error_id` 两条路径
- 断连取消、心跳、错误降级不回归

### 前端 E2E

- 纠错后点击错误卡片追问，看到解释
- 自由输入“为什么 go 改成 went”跨轮追问
- 同一片段在多轮出现时，候选解释或反问不猜错
- 新纠错追加报告，历史仍可追问
- 刷新丢失是预期行为

## 14. 风险

| 风险 | 处理 |
|---|---|
| MemorySaver 重启丢失 | 文档标注仅 MVP；后续 PostgresSaver |
| 规则误判意图 | 显式 `error_id`/`intent` 优先；误判日志 |
| span 校正选错重复片段 | 距离阈值 + 等距丢弃 + 日志 |
| 同 span 多修正 | 保留一条并记录，避免追问歧义 |
| 追问解释与错误条目不一致 | explain 输入完整 turns + turn_id/error_id；测试覆盖 |
| 跨轮引用歧义 | 显式 ID 优先；候选按最近轮次排序；仍冲突则反问 |
| 历史无限增长 | `turns` 只保留最近 10 轮；超范围引用返回明确错误 |
| 单入口事件膨胀 | 事件版本化；前端按 `intent` 分发 |

## 15. 本轮范围

**做**

- span/error_id/重叠消解
- 最近 10 轮 `turns` 历史
- 顶层 route + correct/followup 分支
- MemorySaver + thread_id
- explain 节点 + 跨轮目标解析 + explanation 事件
- 最小前端追问 UI（含历史轮次）
- 单测/图测试/SSE/E2E

**不做**

- 笔记、复习
- DB 持久化、认证、限流
- 局部 Fluency 重写
- 逐条错误流式
- 通用意图分类器

## 16. 待确认

- 是否接受“扁平顶层图 + 逻辑分支”，而不是本轮就上编译子图？
- 追问 MVP 只解释/评估替代写法，不自动应用替代修正，是否可接受？
- 跨轮引用找不到唯一目标时，是否允许 explain 反问“你指的是哪一处”？

## 17. 未来扩展：note（不在本轮范围）

note 只做规划预留，不实现。未来结构：

```text
route
  ├─ correct  → 纠错子图
  ├─ followup → resolve_target → explain
  └─ note     → resolve_note_scope
                    │
                    ▼
              generate_note
                    │
                    ▼
                interrupt
                    │
                    ▼
               commit_note
```

已确认：

- 裸“保存”默认只保存**当前轮**，不默认整会话
- 明确说“全部保存 / 保存整个会话”时才覆盖最近 10 轮
- `resolve_note_scope` 独立实现，本轮不复用 `resolve_target`
- 未来是否复用，等 note 真正实现时再评估
- `NoteSelection`：`scope: error|turn|session|explicit` + `turn_ids` + `error_refs`
- `generate_note` 生成 `proposal_id`；`commit_note` 用 `thread_id + proposal_id` 幂等
- note 正文写 Store/DB，不依赖 checkpoint 长期保存
- “保存”在 MVP 只覆盖最近 10 轮；正式版查 DB/Store
