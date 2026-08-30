# 记笔记功能设计文档（notes-feature）

**所属**：地道英语纠错 · 智能笔记本 | **版本**：V0.2 | **状态**：草稿 | **日期**：2026-08-29
**对应功能**：F-02 记笔记（PRD `Overview.md` §1.2 后期版本功能）
**依赖**：`backend/app/models/`、`backend/app/services/correction_service.py`、`backend/app/services/llm_client.py`、`backend/app/routers/messages.py`、`web/src/pages/CorrectionPage.tsx`、`web/src/components/correction/`

> 本文档定义「记笔记」功能的设计：将纠错结果中的错误归纳为**规则笔记**，以规则为主体、累积多个错误案例，为后续复习功能（F-03，不在本次范围）提供数据基础。

## 〇、背景与目标

- **产品愿景**：Echo 定位「会帮你记住每一个错误的 AI 英语教练」。纠错（F-01）已交付，但「记住」环节缺失——错误改完即忘，无沉淀。
- **本次目标**：实现 F-02 记笔记，让用户从纠错结果中保存「学到的规则」，按规则累积错误案例，可在笔记列表页查看与管理。
- **范围边界**：本次只做「保存 + 查看 + 删除」；**复习功能（F-03）不在本次范围**。

## 一、已确认决策

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 保存触发 | 手动逐条（每个 error 块）+ 批量（整条纠错全部 error）两个入口 |
| 2 | 笔记模型 | **以规则为主体**，同一规则累积多个错误案例；非「每次纠错一条笔记」 |
| 3 | 规则粒度 | `rule_title` 是**可单独测试的规则点**（如「介词后加 -ing 形式」），非语法范畴（如「过去时」）；同类错误合并为一条规则 |
| 4 | 规则生成来源 | **保存时 LLM 生成**（不依赖纠错时的 learnings 字段）。输入 `source_text + errors`，输出 `rule_title + description + example`。纠错提示词本期不改，learnings 仍展示 |
| 5 | 规则作用域 | **系统级全局共享规则库**，跨用户统一；LLM 比对时拿系统全量规则（非用户私有） |
| 6 | 去重方式 | LLM 从 `existing_rules` 中语义匹配，**原样返回已有 rule_title**；后端按 `rule_title` 精确匹配决定新建/追加。LLM 不操作 UUID |
| 7 | 字段结构 | `rule_title`（短标题）+ `description`（详细讲解），**无中间 `rule` 字段** |
| 8 | 规则库规模 | 现阶段全量发送规则给 LLM（单用户，增长缓慢）；超 200 条再优化 |
| 9 | 删除语义 | 删除 = 删当前用户的 `note_cases`，全局 `notes` 规则保留 |
| 10 | LLM 调用 | 单次调用同时完成去重匹配 + 规则生成；批量保存时一次调用返回多条 |
| 11 | 布局 | 左侧 sidebar 导航（纠错/笔记）+ 右上角退出；移动端汉堡菜单 |

## 二、数据模型

### 2.1 新增表

```python
# notes — 全局规则库（系统级，跨用户共享）
class Note(Base):
    __tablename__ = "notes"
    id: UUID (PK, default uuid4)
    rule_title: str          # 短标题，如「介词后加 -ing 形式」
    description: str         # 详细讲解（构成方式、常见介词、边界情况等）
    created_at: datetime     # server_default now()
    updated_at: datetime     # 追加案例时更新

# note_cases — 用户案例（归属用户，引用全局规则）
class NoteCase(Base):
    __tablename__ = "note_cases"
    id: UUID (PK, default uuid4)
    note_id: UUID (FK notes.id, ondelete=CASCADE)        # 引用全局规则
    user_id: UUID (FK users.id, ondelete=CASCADE)        # 案例归属用户
    example: str            # 「错误写法 → 正确写法」对照
    source_text: str         # 来源原文（用户提交的英文，≤2000）
    source_message_id: UUID | None (FK messages.id, ondelete=SET NULL)  # 溯源
    created_at: datetime     # server_default now()
```

### 2.2 关键设计决策

1. **规则全局共享，案例用户隔离**：`notes` 无 `user_id`，任何用户保存笔记时 LLM 判断无匹配即新建全局规则；`note_cases` 带 `user_id`，案例按用户隔离。用户「笔记列表」= 自己有案例的规则。

2. **source_text 冗余存储**：笔记独立于纠错存活。`source_message_id` 仅作溯源链接，用 `SET NULL` 避免删消息级联删案例。

3. **`updated_at`**：追加新案例时更新，笔记列表可按「最近更新」排序（复习优先级信号）。

4. **无 `correction_report_id` 外键**：笔记不绑定报告，只存「当时那句话 + LLM 生成的规则」。

5. **`rule_title` 粒度约束**：由保存时 LLM prompt 控制，不改数据模型（prompt 含正反例约束粒度）。

### 2.3 与现有模型的关系

```
users (1) ──< note_cases (N) >── (1) notes
                    │ source_message_id (SET NULL)
                    ▼
              messages (现有表)

session_conversations ──< messages ──> correction_reports (现有链路，笔记不依赖)
```

### 2.4 迁移

`alembic revision --autogenerate -m "add notes and note_cases tables"`，纯新增表，不影响现有数据。

## 三、保存时 LLM I/O 契约

**单次调用同时完成：去重匹配 + 规则生成 + 案例提取。**

### 3.1 输入

```
- existing_rules: [{rule_title}]          // 系统全量规则的 rule_title 列表（现阶段）
- source_text: str                         // 用户提交的原文
- errors: [{error_type, fragment, explanation, correction}]  // 1 个或多个
```

### 3.2 输出

```json
{
  "results": [
    {
      "rule_title": "介词后加 -ing 形式",
      "description": "英语中介词后接动词时需用动名词形式(-ing)而非不定式...",
      "example": "interested in read → interested in reading"
    }
  ]
}
```

每个 result 对应一条规则（同类错误由 LLM 合并为一条）。字段说明：

| 字段 | 说明 |
|------|------|
| `rule_title` | 若与 `existing_rules` 中某条语义相同，**必须原样返回那条的 rule_title**（不得改写）；确属新规则时生成新的 rule_title |
| `description` | 详细讲解（构成方式、常见介词、边界情况）。已存在规则时后端会忽略此字段 |
| `example` | 「错误写法 → 正确写法」对照，从本次 errors 中提炼 |

### 3.3 后端处理逻辑

```python
for result in llm_results:
    note = SELECT note WHERE rule_title = result.rule_title  # 精确匹配
    if note:
        # 已有规则 → 只追加案例（description 已存在，忽略 LLM 的 description）
        追加 NoteCase(note.id, result.example, source_text, user_id, source_message_id)
    else:
        # 新规则 → 建 note + 首条案例
        note = CREATE Note(result.rule_title, result.description)
        追加 NoteCase(note.id, result.example, source_text, user_id, source_message_id)
```

### 3.4 两种触发对应同一契约

| 触发 | errors 传入 | results 长度 |
|------|-----------|------------|
| 单个 error 记笔记 | 1 个 error | 1 |
| 批量记笔记 | 全部 errors | N（同类错误由 LLM 合并） |

### 3.5 prompt 约束要点

写在保存时 LLM 的 system prompt 中：

1. **rule_title 粒度**：描述一个可单独测试的规则点，非语法范畴
   - ✅ 好：「介词后加 -ing 形式」「to 不定式接动词原形」「可数名词单数需加冠词」
   - ❌ 坏：「过去时」「冠词」「时态」「介词」（太宽泛，含多个不相关练习点）
   - ❌ 坏：「in 后加 ing」（太碎片，应泛化到所有介词）

2. **合并指令**：同类错误合并为一条 result（如 2 个时态错误 → 1 条规则）

3. **去重指令**：若新错误的规则与 `existing_rules` 中某条语义相同，**必须原样返回那条的 rule_title**（不得修改、不得编造）。只有确属新规则时，才生成新的 rule_title。description 字段始终生成（匹配已有规则时后端会忽略，仅用于新建规则）

4. **example 格式**：`错误写法 → 正确写法`

5. **description 要求**：包含规则说明、构成方式、常见情况、边界/例外情况

### 3.6 LLM 调用复用

保存时 LLM 调用复用现有 `LLMClient`（`RealLLMClient` / `MockLLMClient`），同 `LLM_MODE` 切换。新建 `backend/app/prompts/note_prompt.py` 存放保存时 system prompt，`backend/app/services/note_service.py` 封装保存逻辑。

## 四、API 接口

### 4.1 新增接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/notes/save` | 保存笔记（单个/批量），触发 LLM 生成规则 |
| GET | `/api/v1/notes` | 笔记列表（当前用户有案例的规则） |
| GET | `/api/v1/notes/{note_id}` | 笔记详情（含全部案例） |
| DELETE | `/api/v1/notes/{note_id}` | 删除笔记（仅删当前用户的案例，全局规则保留） |
| DELETE | `/api/v1/notes/{note_id}/cases/{case_id}` | 删除单个案例 |

### 4.2 请求/响应

**POST /notes/save**

```json
// 请求
{
  "message_id": "uuid",
  "source_text": "I interested in read...",
  "errors": [
    {"error_type": "动词形式", "fragment": "interested in read", "explanation": "...", "correction": "interested in reading"}
  ]
}

// 响应（异步化后改为）
HTTP 202
{
  "accepted": true
}
```

> **执行方式变更**：保存请求**同步返回成功码 `202`**（毫秒级，不等 LLM 生成），规则生成与入库由后端**后台异步执行**（`FastAPI.BackgroundTasks` + 独立 session）。前端点击后立即乐观反馈，刷新笔记列表页（`GET /notes`）后才见最终结果。原「返回精简结构（note_id + case_id + is_new）」随异步化不再需要——最终数据靠列表页拉取。详见 `notes-async-save-design.md`（08-30）。

**GET /notes**

```json
{
  "notes": [
    {
      "id": "uuid",
      "rule_title": "介词后加 -ing 形式",
      "description": "...",
      "case_count": 3,
      "updated_at": "2026-08-29T..."
    }
  ]
}
```

**GET /notes/{note_id}**

```json
{
  "id": "uuid",
  "rule_title": "介词后加 -ing 形式",
  "description": "...",
  "cases": [
    {
      "id": "uuid",
      "example": "interested in read → interested in reading",
      "source_text": "I interested in read...",
      "created_at": "..."
    }
  ]
}
```

### 4.3 鉴权与隔离

- 所有接口需 Bearer token（同现有 `/messages`）
- 笔记列表/详情/删除按 `user_id` 过滤 `note_cases`——全局规则可见，但案例按用户隔离
- **404 语义**：note_id 存在但当前用户无案例 → 404（对用户而言「不存在」）

### 4.4 关键设计点

1. **保存接口返回精简结构**（~已随异步化调整：`POST /notes/save` 改为返回 `202 {accepted:true}` 成功码，不再返回规则/案例明细；最终数据靠笔记列表页 `GET /notes` 拉取，见 §4.2 注）
2. **DELETE /notes/{id}** 删的是「当前用户在该规则下的所有案例」，全局 `notes` 行保留（其他用户可能引用）
3. **新增 router** `backend/app/routers/notes.py`，注册到 `app.main`

## 五、前端交互与页面结构

### 5.1 整体布局：左侧 sidebar 导航

新增 `AppLayout` 组件，包裹 `/correction` 和 `/notes` 路由：

```
桌面端（≥768px）：
┌────────┬──────────────────────────────┐
│        │ shawn          [退出]        │ ← 顶部条（精简）
│  Echo  ├──────────────────────────────┤
│        │                              │
│ ✏️ 纠错 │     页面主体内容              │
│ 📖 笔记 │                              │
│        │                              │
└────────┴──────────────────────────────┘
 sidebar(200px)    顶部条 + 主内容(弹性)

移动端（<768px）：
┌──────────────────────────────────┐
│ [☰]  Echo           (顶部精简)    │
├──────────────────────────────────┤
│         页面主体内容              │
└──────────────────────────────────┘
点击 ☰ 展开抽屉式 sidebar
```

- sidebar 固定宽度 200px，垂直布局：Logo 顶部，导航项居中，留白
- 顶部条：右侧用户名 + 退出按钮（复用现有逻辑）
- 当前页对应导航项高亮
- 移动端：顶部精简 header（汉堡菜单 + Logo），sidebar 改为抽屉式

### 5.2 路由调整

```tsx
// App.tsx
<Route element={<AuthGuard />}>
  <Route element={<AppLayout />}>
    <Route path="/correction" element={<CorrectionPage />} />
    <Route path="/notes" element={<NotesPage />} />
  </Route>
</Route>
```

### 5.3 对现有代码的影响

- `CorrectionPage.tsx`：移除 header 部分，只保留 `MessageList + Composer`
- 新增 `AppLayout.tsx`：sidebar + 顶部条 + `<Outlet />`
- 新增 `NotesPage.tsx`：笔记列表页
- `App.tsx`：路由嵌套调整

### 5.4 两个触发入口

**① 单个 ErrorCard 内的「记笔记」按钮**

- 位置：`ErrorCard` 底部，`修正后` 行右侧
- 文案：「记笔记」+ 笔记图标
- 点击后：按钮变「已记录」禁用态 + **乐观反馈**（立即，不等 LLM）→ 调 `POST /notes/save`（errors 传 1 个）→ 请求返回 `202`；规则后台入账，**刷新笔记列表页后可见最终结果**

**② 纠错报告底部的「全部记笔记」按钮**

- 位置：`CorrectionReportCard` 底部（改写下文，原文保留在用户消息中）
- 文案：「全部记笔记」+ 图标
- 点击后：按钮变「已记录」禁用态 + **乐观反馈** → 调 `POST /notes/save`（errors 传全部）→ 返回 `202`；规则后台入账，刷新列表页后可见

> **执行方式变更**：计数器不再用「按钮 loading → 等同步返回 → toast 结果」的同步链路；改为「点击即乐观反馈（按钮已记录）→ 后台入账 → 刷新列表页可见」，详见 `notes-async-save-design.md`。

### 5.5 「已记录」状态判定

- **不做实时同步**——不查 API 判断某条 error 是否已记过（成本高、价值低）
- **当前会话内标记**——用户点了「记笔记」后标记为已记录，刷新页面后重置
- 重复保存时 LLM 会匹配已有规则并追加案例，不会产生重复笔记

### 5.6 /notes 笔记列表页

**列表项（折叠态）：**
- `rule_title` + `case_count` + `updated_at`
- `description` 首行预览

**展开后：**
- 完整 `description`
- 全部案例（每个案例：example 对照 + source_text + 删除按钮 ×）
- 底部「删除该笔记」按钮

**交互：**
- 点击列表项展开/折叠
- 删除单个案例：× 按钮 → 二次确认 → `DELETE /notes/{note_id}/cases/{case_id}` → 移除该案例，case_count -1
- 删除笔记：底部按钮 → 二次确认 → `DELETE /notes/{note_id}` → 列表移除该条
- 空态：「还没有笔记，去纠错页记下你的第一条规则吧」+ 跳转按钮

**响应式：** 移动端单列堆叠，卡片全宽，同纠错页约定。

## 六、错误处理

> **执行方式变更**：保存请求已异步化（返回 `202` 即成功）。LLM 生成与入库在**后台任务**中执行，其失败**不再能被前端 toast 捕获**，改为**后台记日志、本次保存静默丢弃**，不向上抛出导致任务崩溃。前端不感知失败（乐观反馈已给）；用户可通过刷新列表页发现「没记上」，再次点击重存即可。

| 场景 | 后台处理 |
|------|---------|
| 保存时 LLM 超时（504） | 记录日志，静默丢弃本次保存 |
| 保存时 LLM 不可用（503） | 记录日志，静默丢弃 |
| LLM 返回格式无效（502，重试 1 次仍失败） | 记录日志，静默丢弃 |

| 场景 | 同步处理（无可异步化部分） |
|------|---------|
| 删除不存在的笔记/案例 | 404 |
| 删除他人案例 | 404（按 user_id 过滤，对用户而言「不存在」） |
| 笔记列表为空 | 200 + `notes: []`，前端显示空态 |

后台任务内复用 `save_notes` 已有的 `AppError` 抛错逻辑，在任务外层 `try/except AppError` 捕获并记日志（见 `notes-async-save-design.md` §3.4）。

## 七、测试策略

### 7.1 后端测试（pytest）

- **Mock LLM**：`note_service` 测试注入 `MockLLMClient`，返回确定性规则 JSON
- **数据模型**：`test_models_note.py` 验证 Note/NoteCase CRUD、级联删除
- **API 契约**：`test_notes_api.py` 验证：
  - 保存（单个/批量，新建规则/追加案例）
  - 列表（按 user_id 隔离，case_count 正确）
  - 详情（404 语义）
  - 删除笔记（全局 notes 保留，user cases 删除）
  - 删除单个案例
- **去重逻辑**：LLM 返回已有 rule_title → 追加案例；返回新 rule_title → 新建
- **隔离**：用户 A 的笔记对用户 B 不可见

### 7.2 前端测试（Playwright E2E）

- 笔记列表页加载、空态
- 单个 error 记笔记 → toast + 按钮状态变化
- 批量记笔记 → toast + 按钮状态变化
- 笔记展开/折叠
- 删除单个案例
- 删除笔记
- 导航：纠错页 ↔ 笔记页切换

E2E 自动起后端 `LLM_MODE=mock`（见 `playwright.config.ts`），需扩展 mock responder 支持笔记保存响应。

### 7.3 测试 gotcha

- 后端测试依赖 `echo_test` DB，conftest 会 `create_all`（不用 alembic）。新增 Note/NoteCase 模型需在 `app/models/__init__.py` 注册（确保 `Base.metadata` 包含）
- conftest `clean_sessions` fixture 需扩展：truncate `note_cases` + `notes`（或纳入现有清理逻辑）

## 八、文件改动清单

### 后端新增
- `backend/app/models/note.py` — Note + NoteCase 模型
- `backend/app/schemas/note.py` — Pydantic schemas
- `backend/app/services/note_service.py` — 保存/列表/详情/删除逻辑
- `backend/app/prompts/note_prompt.py` — 保存时 system prompt
- `backend/app/routers/notes.py` — API 路由
- `backend/tests/test_models_note.py`
- `backend/tests/test_notes_api.py`
- `backend/alembic/versions/xxxx_add_notes_and_note_cases.py`

### 后端修改
- `backend/app/models/__init__.py` — 注册 Note/NoteCase
- `backend/app/main.py` — 注册 notes router
- `backend/tests/conftest.py` — `clean_sessions` 扩展清理 notes/note_cases
- `backend/app/services/llm_client.py` — MockLLMClient 扩展笔记保存 mock responder（或 note_service 测试中注入）

### 前端新增
- `web/src/components/AppLayout.tsx` — sidebar + 顶部条 + Outlet
- `web/src/components/Sidebar.tsx` — 导航项
- `web/src/pages/NotesPage.tsx` — 笔记列表页
- `web/src/components/notes/NoteCard.tsx` — 笔记列表项（折叠/展开）
- `web/src/components/notes/NoteCaseItem.tsx` — 案例行（example + 删除）
- `web/src/api/notes.ts` — 笔记 API 客户端

### 前端修改
- `web/src/App.tsx` — 路由嵌套调整（AppLayout 包裹）
- `web/src/pages/CorrectionPage.tsx` — 移除 header，只保留主体
- `web/src/components/correction/ErrorCard.tsx` — 新增「记笔记」按钮
- `web/src/components/correction/CorrectionReportCard.tsx` — 新增「全部记笔记」按钮
- `web/src/api/messages.ts` — 补充 ErrorBlock 类型导出（供 notes API 复用）

## 九、未来演进

1. **移除纠错 learnings**：后期修改纠错提示词，不再生成 learnings 段。保存时 LLM 逻辑不变（本就独立于 learnings），触发点已是 error 块。纠错报告移除 learnings 分区即可。
2. **规则库规模优化**：规则超 200 条时，按 error_type 预筛选相关规则子集发送给 LLM（需给 notes 加分类标签）。
3. **全局规则管理**：管理员后台编辑/合并/删除全局规则（本期不做）。
4. **复习功能（F-03）**：基于 notes + note_cases 数据，实现间隔重复（SRS）复习模式。

---

**变更记录**

- V0.2 · 2026-08-30 · **同步异步化设计**：§4.2 `POST /notes/save` 返回结构改为 `202 {accepted:true}`（后台入账）；§5.4 前端触发改为乐观反馈 + 后台入账 + 刷新可见（去同步 toasting）；§六 错误处理改为后台记日志、不 toast；§4.4 设计点同步（详见 `notes-async-save-design.md`）

- V0.1 · 2026-08-29 · 初稿：记笔记功能设计（规则中心 + 全局共享 + 保存时 LLM 生成 + 左侧 sidebar 布局）
