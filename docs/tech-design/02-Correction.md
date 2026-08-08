# 纠错功能详细设计文档（02-Correction）

**所属**：地道英语纠错 · 智能笔记本 | **版本**：V0.2 | **状态**：草稿 | **日期**：2026年8月
**对应 PRD**：`PRD/pages/02-Correction.md`（V2.5，含 PRD 同步更新）、`PRD/Overview.md` §1.1
**依赖**：`00-Architecture.md`（顶层契约：接口风格、错误格式、鉴权、数据契约、LLM 接入契约）

> 本文档为纠错功能的**详细技术设计**（LLM 层、数据模型、API 契约、前端组件、上下文策略、场景矩阵、验证方式）。顶层约定不重复定义，统一引用 `00-Architecture.md`。

## 〇、功能概述

- **目标**：在单一大会话中提交英文文本获取结构化纠错报告，并可无限追问；全部历史持久化、按账号隔离
- **入口**：登录后默认落地页（替换现有占位页 `CorrectionPlaceholder.tsx`）
- **关键约束**（PRD §4.3/§4.5/§4.6）：AI 意图判定（单次调用）；纠错报告非流式一次性呈现；追问关联最近一次纠错报告；输入 ≤2000 字符

### 0.1 本功能关键设计决策

| # | 决策点 | 选择 | 理由 |
|---|--------|------|------|
| 1 | LLM 集成 | 客户端抽象接口；生产 OpenAI 兼容实现，测试注入确定性 Mock | TDD/E2E 可离线运行，真实调用仅冒烟验证 |
| 2 | 错误语块定位 | 只返回**文本片段**，原文不高亮（已同步更新 PRD） | 简化 LLM 输出契约，报告卡片内展示语段 |
| 3 | 意图判定 | **单次 LLM 调用**返回 `intent` 标记 + 对应内容 | 省一次调用，低延迟 |
| 4 | LLM 未配置 | 返回 `503 LLM_SERVICE_UNAVAILABLE` | 语义清晰，生产必须配 key 才能用 |
| 5 | 改写下划线 | **一并移除**，仅展示改写文本 + 解释（已同步更新 PRD） | 与「只返回文本片段」决策一致 |
| 6 | 上下文截断 | 按消息条数，`CONTEXT_LIMIT` 默认 40 条 | 实现简单，MVP 自用场景够用 |

## 一、LLM 层

### 1.1 客户端抽象

- 定义 `LLMClient` 接口（`app/services/llm_client.py`），统一 `chat(messages) -> str` 调用入口
- **生产实现**：OpenAI 兼容 Chat Completions API（`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` 环境变量注入，见架构 §6.1/§7.2）；非流式
- **测试实现**：确定性 Mock/Stub，按输入返回预设 JSON；经依赖注入供 services 使用（对齐登录功能 `auth_service` 的 TDD 先例）
- **未配置行为**：`LLM_BASE_URL`/`LLM_API_KEY` 缺失时，纠错请求返回 `503`（见 §4.3）

### 1.2 单次调用契约（意图判定 + 内容生成）

> **提示词工程说明**：本轮开发**不实现真实 LLM 调用**，仅实现 Mock 路径；真实 LLM 的提示词内容后续**单独编写文档**（另立文档），此处仅写明意图与契约约束。真实提示词须满足的意图判定与输出约束如下。

输入为「系统提示（约束 JSON schema + 错误分类 + 最小修正原则）+ 最近 N 条消息 + 用户新提交」。LLM 返回单份 JSON，经 Pydantic 校验：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "grammar",
        "fragment": "I go to",
        "explanation": "yesterday 表示过去，故用过去式 went",
        "correction": "I went to"
      }
    ],
    "rewrite": {
      "minimal":  { "text": "Yesterday I went to the park.", "explanation": "修正时态，保留原句结构" },
      "natural":  { "text": "Yesterday I enjoyed the park.", "explanation": "用 enjoyed 更自然" }
    }
  },
  "reply": null
}
```

- `intent=correction` 时：返回 `correction` 对象；`has_errors=false` 时 `errors`/`rewrite` 可为空，前端展示鼓励文案（PRD §7.2）
- `intent=follow_up` 时：返回 `reply`（纯文本），`correction` 为 null
- **错误分类**（PRD §4.10）：`grammar`（语法）/ `collocation`（搭配）/ `chinglish`（中式英语，橙色展示）/ `style`（风格与语气）
- **真实提示词（另立文档）须满足的意图判定约束**（PRD §4.3）：纯中文 → follow_up；英文夹杂中文生词 → correction；疑问句式 → 结合上下文判断，不强制归为追问；纠错报告遵循「最小修正」原则、报告内不重复原文、无错误返回鼓励文案

### 1.3 解析与容错

- LLM 返回经 Pydantic schema 校验；校验失败 → **单次重试**（附解析错误提示）→ 仍失败 → `502 LLM_RESPONSE_INVALID`
- LLM 调用超时 120s → `504 LLM_TIMEOUT`（对齐 PRD §4.8 超时阈值）
- LLM 服务异常（连接错误/5xx）→ `503`/`500`，前端提示重试

## 二、数据模型（本功能）

> 遵循架构 §4.2 顶层契约：`session_conversations → messages → correction_reports`；纠错报告为独立对象（自带 ID），便于追问指代与后续错题提取（F-03）。

### 2.1 session_conversations（对话）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `user_id` | UUID FK → users.id | 账号隔离 |
| `created_at` | timestamptz | `YYYY-MM-DD HH:MM:SS` |

- **MVP 单对话**：首次进入时 get-or-create 该用户的对话行，全部消息挂其下；预留多对话维度（后期多会话管理为增量 UI 工作）

### 2.2 messages（消息）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `conversation_id` | UUID FK → session_conversations.id | |
| `role` | enum | `user` / `assistant` |
| `type` | enum | `correction`（用户提交）/ `report`（AI 纠错报告）/ `follow_up`（用户追问）/ `reply`（AI 纯文本回复） |
| `content` | text | 用户原文/追问/纯文本回复；`report` 类型为 NULL |
| `report_id` | UUID FK → correction_reports.id | `report` 类型非空，其余 NULL |
| `created_at` | timestamptz | |

- **追问指代**：追问时查该对话最近一条 `type=report` 消息，取其 `report_id` 对应的报告作为上下文；MVP 已知取舍（PRD §4.6）
- 每条消息独立成行；用户提交与其对应 AI 回复为相邻两行，前端成对渲染

### 2.3 correction_reports（纠错报告）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `message_id` | UUID FK → messages.id | 唯一，关联所属 AI 消息 |
| `version` | int | 报告契约版本号，当前 `1`（版本化契约见架构 §5.3） |
| `structure` | JSONB | 报告本体（§1.2 的 `correction` 结构），按 `version` 校验 |
| `created_at` | timestamptz | |

### 2.4 数据示例

**场景**：用户提交 `"Yesterday I go to the park and eat very delicious food."`，AI 返回纠错报告；随后追问 `"为什么不能用 very？"`，AI 纯文本回复。

**① session_conversations**

| id | user_id | created_at |
|---|---|---|
| `conv_001` | `u_1` | `2026-08-08 10:00:00` |

**② messages**

| id | conversation_id | role | type | content | report_id | created_at |
|---|---|---|---|---|---|---|
| `msg_1` | conv_001 | user | correction | "Yesterday I go to the park and eat very delicious food." | NULL | `2026-08-08 10:00:01` |
| `msg_2` | conv_001 | assistant | report | NULL | `rep_001` | `2026-08-08 10:00:05` |
| `msg_3` | conv_001 | user | follow_up | "为什么不能用 very？" | NULL | `2026-08-08 10:01:00` |
| `msg_4` | conv_001 | assistant | reply | "delicious 是极限形容词，本身已含程度……" | NULL | `2026-08-08 10:01:02` |

**③ correction_reports**（`rep_001`，message_id=`msg_2`，version=1）

```json
{
  "has_errors": true,
  "errors": [
    {
      "category": "grammar",
      "fragment": "I go to",
      "explanation": "yesterday 表示过去，故用过去式 went",
      "correction": "I went to"
    },
    {
      "category": "chinglish",
      "fragment": "eat very delicious food",
      "explanation": "delicious 是极限形容词，通常不加 very；eat 与 food 搭配不地道",
      "correction": "ate really delicious food"
    }
  ],
  "rewrite": {
    "minimal": {
      "text": "Yesterday I went to the park and ate really delicious food.",
      "explanation": "修正时态与极限形容词用法，保留原句结构"
    },
    "natural": {
      "text": "Yesterday I went to the park and enjoyed some delicious food.",
      "explanation": "用 enjoyed + some delicious food 更自然"
    }
  }
}
```

## 三、交互流程

### 3.1 提交纠错时序

```
User        Frontend          Backend              DB        LLM
 │ 输入文本   │                │                   │          │
 │──提交──▶│ 前端非空/字数校验      │                   │          │
 │        │ 失败→提示，不发请求     │                   │          │
 │        │ 用户消息先上屏+加载态   │                   │          │
 │        │──POST /api/v1/messages──▶│               │          │
 │        │                │ 鉴权→get-or-create 对话 │          │
 │        │                │ 组装上下文(最近N条)    │          │
 │        │                │──LLM 调用────────────▶│          │
 │        │                │◀──intent+内容─────────│          │
 │        │                │ 校验→入库(消息+报告)    │          │
 │        │                │──写 session_conversations/messages──▶│
 │        │◀──200 {user_message, assistant_message}──│          │
 │        │ 替换加载态，渲染报告/回复                 │          │
```

### 3.2 历史加载

- 进入页面 `GET /messages` 全量正序加载，滚动到底部最新消息（PRD AC-C-11）
- 旧消息仅回看，不可重新提交或修改（AC-C-12）

### 3.3 追问关联

- 提交内容经 LLM 判定 `intent=follow_up` 时，后端在组装上下文时已含最近消息；`reply` 以纯文本消息入库并返回（AC-C-13）
- 纯中文输入 → LLM 应判为 follow_up（PRD §4.3 兜底规则作为判定参考）

## 四、接口契约

> 均需鉴权（`Authorization: Bearer <token>`），前缀 `/api/v1`。

### 4.1 POST /api/v1/messages

请求：
```json
{ "content": "Yesterday I go to the park" }
```
响应 200：
```json
{
  "user_message": {
    "id": "msg_1", "role": "user", "type": "correction",
    "content": "Yesterday I go to the park", "created_at": "2026-08-08 10:00:01"
  },
  "assistant_message": {
    "id": "msg_2", "role": "assistant", "type": "report",
    "content": null, "created_at": "2026-08-08 10:00:05",
    "report": { "has_errors": true, "errors": [...], "rewrite": {...} }
  }
}
```
- `type=reply` 时 `report` 为 null，内容在 `content`
- 错误：`400`（空/超 2000 字符，`VALIDATION_ERROR`）、`401`（未登录/失效）、`502`（LLM 返回无效）、`503`（LLM 未配置或不可用）、`504`（LLM 超时）、`500`（其他）

### 4.2 GET /api/v1/messages

响应 200：
```json
{
  "messages": [
    { "id":"msg_1","role":"user","type":"correction","content":"...","report":null,"created_at":"..." },
    { "id":"msg_2","role":"assistant","type":"report","content":null,"report":{...},"created_at":"..." }
  ]
}
```
- 正序（旧→新）；`report` 类型消息内嵌报告结构

### 4.3 统一错误响应

沿用架构 §5.2 格式 `{ "code", "message", "details" }`；新增错误码：

| HTTP | code | 说明 |
|------|------|------|
| 502 | `LLM_RESPONSE_INVALID` | LLM 返回无法解析/不符合 schema（含重试后） |
| 503 | `LLM_SERVICE_UNAVAILABLE` | LLM 未配置或服务不可用 |
| 504 | `LLM_TIMEOUT` | LLM 调用超时 120s |

> **依赖更新**：架构 `00-Architecture.md` §5.2 需补充 502/504 错误码。

## 五、上下文策略

- **数据库始终存全量历史**（架构 §4.3）
- LLM 上下文：取当前对话**最近 `CONTEXT_LIMIT` 条消息**（默认 `40`，`CONTEXT_LIMIT` 环境变量可配），按时间正序组装
- 展示仍加载全量，仅送入 LLM 的上下文做截断（不牺牲历史完整性）
- 配置项：`CONTEXT_LIMIT`（默认 40，架构 §7.2 同步更新）

## 六、前端设计

### 6.1 组件树

```
CorrectionPage（替代 CorrectionPlaceholder，沿用现有导航栏）
├── MessageList
│   ├── UserBubble          （correction/follow_up：靠右，品牌色高亮）
│   ├── CorrectionReportCard（type=report：整体大框，错误分析+改写 两分区）
│   │   ├── ErrorCard       （fragment + explanation + correction；grammar 红条/chinglish 橙条）
│   │   └── RewriteSection  （minimal 绿 ✏️ / natural 紫 ✨ 两虚线框 + CopyButton）
│   ├── ReplyBubble         （type=reply：靠左浅灰底纯文本）
│   └── LoadingBubble       （「AI 正在分析，请稍候…」）
└── Composer                （多行自动延伸输入框 + n/2000 字数 + 发送按钮三态）
```

### 6.2 前端行为要点

| 项 | 行为 |
|----|------|
| 加载态 | 提交后用户消息立即上屏 + LoadingBubble；按钮禁用；响应后替换 |
| 错误态 | `503/502/504/网络异常` → 「请求失败，请重试」；用户消息保留可重发 |
| 空态 | 无消息时引导文案「输入英文，AI 将为你纠错；也可以随时提问」 |
| 字数校验 | 超 2000 字符：字数标红 + 发送禁用，不截断输入（PRD §4.3） |
| 复制 | `navigator.clipboard.writeText` 复制改写整段；按钮变绿 ✓ + 「已复制」1-2s 消失；触控热区 ≥48px |
| 状态管理 | 新增 conversation 状态（消息列表 + 加载/错误），沿用 auth-context 模式 |
| 会话过期 | 401 → 沿用 01-Login §3.2 拦截：保留页面 + 提示重新登录，输入不丢失 |

## 七、三态与错误处理

| 状态 | 呈现 | 说明 |
|------|------|------|
| 加载态 | 发送按钮禁用 + LoadingBubble + 「AI 正在分析，请稍候…」；用户消息先上屏 | 防重复提交 |
| 空态 | 引导文案 | 首次使用无消息时 |
| 错误态 | 「请求失败，请重试」+ 重试；用户消息不丢失 | 502/503/504/网络/5xx |

| 场景 | 反馈 | 保留内容 |
|------|------|----------|
| 输入为空 | 发送按钮禁用（防御文案「请输入内容」） | — |
| 超 2000 字符 | 字数标红 + 发送禁用 | 输入全部保留 |
| 请求失败 | 「请求失败，请重试」 | 用户消息保留 |
| LLM 超时 120s | 「AI 响应超时，请重试」 | 用户消息保留 |
| 会话过期 | 「会话已过期，请重新登录」+ 重新登录入口 | 页面与输入保留 |

## 八、业务 Scenario 矩阵

| 场景 | 前置 | 触发 | 预期 | 关联 |
|------|------|------|------|------|
| 提交纠错成功 | 已登录 | 提交含错英文 | 报告一次性呈现，语块卡片 + 改写分区 | AC-C-01/02/03/05 |
| 无错误文本 | 已登录 | 提交正确英文 | 展示鼓励文案，不展示卡片 | AC-C-07 |
| 中文夹杂生词 | 已登录 | 提交"…餐厅…" | 按纠错处理生成报告 | PRD §4.3 |
| 纯中文提交 | 已登录 | 提交纯中文 | LLM 判 follow_up，返回纯文本回复 | AC-C-09 |
| 连续追问 | 已登录 | 多次追问 | 不限次数正常回复，基于最近纠错上下文 | AC-C-10/13 |
| 历史加载 | 已登录 | 进入页面/刷新 | 全量正序，刷新后仍在 | AC-C-11/12 |
| 超字数提交 | 已登录 | 输入 >2000 字符 | 字数标红 + 发送禁用，不截断 | AC-C-06 |
| 多行输入 | 已登录 | 输入换行文本 | 输入框自动延伸增高 | AC-C-14 |
| 复制改写 | 已登录 | 点击复制按钮 | 一键复制整段 + 「已复制」反馈 | AC-C-15 |
| 请求失败 | 已登录 | 服务异常/LLM 异常 | 「请求失败，请重试」，消息保留 | AC-C-08 |
| 会话过期提交 | 已过期 | 提交纠错 | 401 保留页面，提示重新登录，输入不丢失 | AC-L-08 / AC-C-08 |

## 九、验证方式（技术验收）

> 验收分两层：**先验证 API 契约，再验证 UI 功能**；均映射到 PRD AC。LLM 相关用例以 Mock 注入验证，真实 LLM 仅作冒烟。

### 9.1 API 契约验证（pytest，Mock LLM）

| # | 接口 | 用例 | 预期 | 关联 |
|---|------|------|------|------|
| T-C-01 | POST /messages | 提交含错英文（Mock 返回 correction） | 200，返回 user_message + assistant_message(report)；DB 落 messages 2 行 + correction_reports 1 行 | AC-C-01 |
| T-C-02 | POST /messages | 提交无错英文 | 200，report.has_errors=false | AC-C-07 |
| T-C-03 | POST /messages | 提交纯中文（Mock 返回 follow_up） | 200，type=reply，report=null | AC-C-09 |
| T-C-04 | POST /messages | 空内容 | 400 `VALIDATION_ERROR` | AC-C-02 输入约束 |
| T-C-05 | POST /messages | 超 2000 字符 | 400 `VALIDATION_ERROR` | AC-C-06 |
| T-C-06 | POST /messages | 未鉴权 | 401 | AC-L-05 |
| T-C-07 | POST /messages | LLM 未配置 | 503 `LLM_SERVICE_UNAVAILABLE` | §1.1 |
| T-C-08 | POST /messages | Mock 返回无效 JSON | 502 `LLM_RESPONSE_INVALID` | §1.3 |
| T-C-09 | GET /messages | 空对话 | 200 `{messages: []}` | AC-C-11 |
| T-C-10 | GET /messages | 有历史 | 200 全量正序，report 内嵌 | AC-C-11/12 |
| T-C-11 | 数据隔离 | 不同 user 提交 | 各自对话互不可见 | PRD §3.2 |
| T-C-12 | 追问上下文 | 提交 follow_up | 组装上下文含最近 report 消息 | AC-C-13 |

### 9.2 UI 功能验证（Playwright MCP / E2E）

| # | 操作步骤 | 预期 | 关联 |
|---|----------|------|------|
| U-C-01 | 进入纠错主页（首次） | 空态引导文案 | AC-C-11 |
| U-C-02 | 提交含错英文 | 用户消息上屏 → 加载态 → 报告整体呈现（错误分析+改写） | AC-C-01/02 |
| U-C-03 | 提交无错英文 | 鼓励文案 | AC-C-07 |
| U-C-04 | 提交纯中文 | 纯文本回复 | AC-C-09 |
| U-C-05 | 连续追问 3 次 | 依次堆叠，均正常回复 | AC-C-10 |
| U-C-06 | 输入 >2000 字符 | 字数标红 + 发送禁用，内容不截断 | AC-C-06 |
| U-C-07 | 多行输入 | 输入框自动延伸 | AC-C-14 |
| U-C-08 | 点击改写复制按钮 | 复制整段 + 「已复制」反馈 | AC-C-15 |
| U-C-09 | 刷新页面 | 历史全量加载，滚动到底部 | AC-C-11 |
| U-C-10 | 手机宽度 | 布局正常 | 响应式规范 |

### 9.3 验证顺序

1. **API 层**（T-C-01~12）：pytest + Mock LLM，确保契约与数据落库正确
2. **UI 层**（U-C-01~10）：Playwright MCP 走查，重点报告渲染与复制交互
3. **真实 LLM 冒烟（不阻塞本轮交付）**：本轮不实现真实 LLM 调用，提示词另行编写文档；待配置 key 并编写真实提示词后，手工提交典型场景（纠错/追问/纯中文/中英混排）验证意图判定覆盖（PRD §8 上线验证项）

---

**变更记录**

- V0.2 · 2026-08 · 明确本轮不实现真实 LLM 调用（仅 Mock 路径），真实提示词另行编写文档，此处写明意图与契约约束（§1.2）；真实 LLM 冒烟标注为不阻塞交付的可选环节（§9.3）
- V0.1 · 2026-08 · 初稿：LLM 层（客户端抽象 + 单次调用契约 + 解析容错）、数据模型（session_conversations/messages/correction_reports）、API 契约、上下文策略、前端组件、场景矩阵与验证方式；关键决策（Mock 测试、只返回文本片段、单次调用意图判定、未配置 503、移除改写下划线、CONTEXT_LIMIT=40）已同步更新 PRD
