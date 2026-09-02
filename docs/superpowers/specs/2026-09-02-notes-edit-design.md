# 移除个人易错警示 + 笔记编辑功能

**日期**：2026-09-02
**状态**：定稿
**分支**：v0.4
**依赖前置**：`2026-09-01-notes-8field-personal-design.md`（笔记 8 字段个人化 + 自动保存，已实现）

## 一、背景与目标

笔记功能已实现 8 字段 AI 初稿 + 自动保存。本轮两个目标：

1. **移除「个人易错警示」字段**：从记笔记角度审视，该字段与「核心知识点」「个人案例」信息重叠，且"个人化"是伪命题（AI 生成时无用户画像数据支撑，"你常错"是编造叙事）。案例列表本身即最好的"易错提醒"。
2. **笔记编辑功能**：实现 PRD §4.3「人工编辑内化」——用户可编辑 AI 生成的规则内容，完成"AI 整理 + 人脑内化"。

## 二、范围

### 本轮做
- 移除 `notes.warning`（个人易错警示）字段，数据模型 3 规则级字段 + 4 案例级字段
- 新增 `PUT /api/v1/notes/{note_id}` 编辑规则级字段
- 前端内联编辑：rule_title + 核心知识点 + 同义备选 + 费曼自测
- 字段 UI 标签改名：「职场同义备选」→「同义备选」（`alternatives` 字段名不变）

### 不做（TODO / 明确排除）
- 编辑案例级字段（只读）
- 新增自定义字段 / 易错星级
- 编辑历史 / 审计
- 跨次去重、数据分析
- 数据迁移文件（本地重建 DB）

## 三、数据模型变更

### `notes` 表
- **删除 `warning` 列**（Text, nullable=False）

变更后 `notes` 字段：
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `user_id` | FK → users.id, CASCADE | |
| `rule_title` | String(200) | 规则标题 |
| `knowledge_point` | Text | 核心知识点 |
| `alternatives` | JSONB | 同义备选（字符串数组） |
| `feynman_question` | Text | 费曼自测 |
| `created_at` / `updated_at` | DateTime | |

### `note_cases` 表
不变：`original_sentence` / `polished_sentence` / `change_details` / `error_root` / `source_message_id` / `created_at`，唯一约束 `(note_id, user_id, original_sentence)`。

### 迁移策略
不写 alembic 迁移文件。开发环境直接重建 DB（用户已确认）。

### 连带更新
- 既有 E2E `notes.spec.ts` N-03 断言「⚠️ 个人易错警示」→ 需移除该断言
- 既有后端测试中对 `warning` 字段的引用 → 移除

## 四、接口契约

### 新增 `PUT /api/v1/notes/{note_id}`

**请求体**（`UpdateNoteRequest`）：
```json
{
  "rule_title": "现在完成时与介词 to 后的动词形式",
  "knowledge_point": "在现在完成时中，助动词 have/has 后必须接动词的过去分词...",
  "alternatives": ["I have sent you the report...", "I've shared the report..."],
  "feynman_question": "助动词 have 后面的动词该用什么形式？为什么？"
}
```

**校验规则**：
- `rule_title`、`knowledge_point`、`feynman_question` 非空（`min_length=1`，trim 后）
- `alternatives` 可为空数组
- 按用户隔离：非本人笔记 → 404 `NOTE_NOT_FOUND`

**响应**：200 + 更新后的 `NoteDetailResponse`

### 变更后 notes API 总览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/notes` | 列表（`rule_title`/`knowledge_point`/`case_count`/`updated_at`） |
| GET | `/api/v1/notes/{id}` | 详情 7 字段 + cases |
| PUT | `/api/v1/notes/{id}` | **新增**：编辑规则级 4 字段 |
| DELETE | `/api/v1/notes/{id}` | 删除笔记 |
| DELETE | `/api/v1/notes/{id}/cases/{case_id}` | 删除单个案例 |

## 五、前端设计

### 组件改动

**`NoteCard.tsx`**：
- 普通态：卡片展示规则级字段（📌 核心知识点 / 💼 同义备选 / ❓ 费曼自测）+ 案例区；底部右侧「✏️ 编辑此笔记」按钮
- 编辑态：点「编辑此笔记」→ 卡片临时增宽，4 项变输入控件（🏷 规则标题 input + 📌 核心知识点 textarea + 💼 同义备选 行内 input+✕+「＋ 添加一条」 + ❓ 费曼自测 textarea），底部「取消 / 保存」
- 保存成功 → toast「✓ 笔记已保存」+ 更新本地 detail + 退出编辑态
- 取消 → 丢弃改动，恢复普通态

**编辑态字段标签**：🏷 规则标题 / 📌 核心知识点 / 💼 同义备选 / ❓ 费曼自测

**`NoteCaseItem.tsx`**：不变（案例只读）

**`notes.ts`**：新增 `updateNote(noteId: string, payload: UpdateNoteRequest): Promise<NoteDetailResponse>`

### 交互状态

| 状态 | 行为 |
|------|------|
| 编辑中 | 底部「取消 / 保存」；保存时按钮 loading「保存中…」 |
| 校验失败 | 空文本字段红框 + 字段下方红字「不能为空」，阻止保存 |
| 保存成功 | toast「✓ 笔记已保存」+ 退出编辑态 + 更新显示 |
| 保存失败 | toast「保存失败，请重试」+ 保持编辑态 |
| 取消 | 丢弃改动，恢复普通态 |

### 视觉参考
编辑态视觉稿见 `.superpowers/brainstorm/`（方案 A：内联编辑、卡片增宽、输入横向舒展、统一保存/取消条）。

## 六、测试计划

### 后端
| 测试 | 覆盖点 |
|------|--------|
| 模型 | `notes` 无 `warning` 字段；3 规则级 + 4 案例级 |
| Schema | `UpdateNoteRequest` 校验（空 rule_title/knowledge_point/feynman_question 拒绝；alternatives 空数组允许） |
| Service `update_note` | 更新 3 内容字段 + rule_title；按用户隔离 404；commit 生效 |
| API `PUT /notes/{id}` | 200 返回更新后 detail；404 非本人 / 不存在；400 空文本 |
| 既有回归 | 移除所有 `warning` 断言后全量通过 |

### 前端
- `NoteCard` 编辑态交互逻辑（tsc 构建验证）
- `notes.ts` `updateNote` 类型
- E2E：新增「编辑笔记保存」用例（进入编辑 → 修改标题/内容 → 保存 → 断言列表与展开显示新值）

### 迁移
本地重建 DB（不写迁移文件）

## 七、验收标准

- AC-N-01：`notes` 表无 `warning` 列，笔记卡片/详情不展示「个人易错警示」
- AC-N-02：编辑入口「✏️ 编辑此笔记」在普通态卡片底部右侧
- AC-N-03：点编辑后 4 项（标题/知识点/同义备选/费曼）变输入控件，可修改
- AC-N-04：同义备选支持逐条删除（✕）与新增（＋ 添加一条），可清空
- AC-N-05：文本字段留空点保存 → 红框 + 「不能为空」提示，不提交
- AC-N-06：保存成功 → toast「✓ 笔记已保存」+ 显示更新后的值；取消 → 丢弃改动
- AC-N-07：保存后列表页标题（若改 title）同步更新
- AC-N-08：改 `rule_title` 后详情/列表使用新标题
