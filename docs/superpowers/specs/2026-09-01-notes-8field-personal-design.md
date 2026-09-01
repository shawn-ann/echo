# 笔记功能重构：8 字段 AI 初稿 + 个人化 + 自动保存

**日期**：2026-09-01
**状态**：定稿
**分支**：v0.4
**对应 PRD 方向**：AI 职场英文纠错 & 自动笔记学习工具（笔记部分）

## 一、背景与目标

现有笔记功能（F-02）将纠错结果按全局规则库（`notes` 无 `user_id`）去重归纳，用户主动点击「记笔记」异步保存。本轮重构目标：

1. **个人化**：去掉全局规则库，`notes` 变个人专属
2. **8 字段笔记**：LLM 从错误归纳生成标准化 8 字段笔记初稿
3. **自动保存**：纠错成功后自动触发笔记保存，移除用户手动「记笔记」入口
4. **同句同类合并**：一次纠错内，同 `error_type` 错误合并为一条笔记；不同 `error_type` 各自独立

## 二、范围

### 本轮做
- 笔记数据模型重构（个人化 + 8 字段）
- 笔记 LLM prompt 重写
- 自动保存触发链路
- 笔记接口响应更新
- 前端笔记页展示更新
- 数据迁移（清库重建）

### 不做（TODO，后期排期）
- 跨次去重匹配（同规则点追加案例）
- 易错星级、人工编辑（PRD §4.3）
- 闪卡复习（F-05）、数据分析（F-06）
- 纠错 F-01 全链路（prompt/schema/报告结构/前端）**完全不动**

## 三、数据模型

### `notes` 表（规则级，个人化）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `user_id` | FK → users.id, CASCADE | 新增，个人专属 |
| `rule_title` | String(200) | 规则标题（LLM 生成） |
| `knowledge_point` | Text | ⑤ 核心知识点提炼 |
| `warning` | Text | ⑥ 个人易错警示 |
| `alternatives` | JSONB | ⑦ 职场同义备选（字符串数组，2-3 条） |
| `feynman_question` | Text | ⑧ 费曼自测问题 |
| `created_at` / `updated_at` | DateTime | `updated_at` 用于列表排序 |
| **唯一键** | `(user_id, rule_title)` | 防同次生成重复 |

移除：`description`、`examples`。

### `note_cases` 表（案例级）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `note_id` | FK → notes.id, CASCADE | |
| `user_id` | FK → users.id, CASCADE | |
| `original_sentence` | Text | ① 用户原句（= 提交的 source_text） |
| `polished_sentence` | Text | ② 优化终句（= `rewrite.minimal.text`，完整终版） |
| `change_details` | Text | ③ 修改明细，`fragment → correction` 分号串联 |
| `error_root` | String | ④ 错误根源（= 细粒度 `error_type`） |
| `source_message_id` | FK → messages.id, SET NULL | 溯源 |
| `created_at` | DateTime | |
| **唯一键** | `(note_id, user_id, original_sentence)` | 防同句重复入库 |

移除：`fragment`、`correction`、`source_text`。

### 合并规则

- **同一次纠错内**：按 `error_type` 分组，同 `error_type` 的多个错误 → 1 条笔记 + 1 个案例（`change_details` 分号串联）
- **不同 `error_type`** → 各自独立笔记
- **跨次纠错**：不做去重匹配，每次生成新笔记（TODO）

## 四、LLM 笔记生成契约

### 调用时机

复用现有异步模式：纠错成功 → `BackgroundTasks` 后台触发笔记 LLM 调用 → 入库。

### LLM 输入

- `source_text`：用户原句
- `errors[]`：来自纠错报告（`error_type/fragment/explanation/correction`）

### LLM 输出（8 字段结构）

```json
{
  "results": [
    {
      "rule_title": "第三人称单数主谓一致",
      "knowledge_point": "一般现在时中，主语为第三人称单数时，实义动词加 -s/-es...",
      "warning": "你常忘给 she/he/it 加 -s，写邮件时先检查主语",
      "alternatives": ["She runs the report daily.", "He handles the tickets.", "The system updates automatically."],
      "feynman_question": "主语是 she/he/it 时，动词该怎么变？",
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

### 关键约束

1. **按 `error_type` 分组**：LLM 将同 `error_type` 错误归到同一 `result`，`error_root` 直接取该 `error_type` 值
2. **`cases` 单案例**：同 `error_type` 下多个错误合并为 1 个 case（`change_details` 分号串联）
3. **`polished_sentence` 后端填充**：LLM 不生成，后端从 `rewrite.minimal.text` 直接取值
4. **`alternatives` 2-3 条**：完整英文句子，覆盖不同正式程度
5. **`rule_title` 粒度**：沿用现有 prompt 约束——「可单独测试的规则点」，非语法范畴

### 后端组装

LLM 只输出规则级字段 + `change_details`。后端对每个 case 填充：
- `original_sentence` ← `source_text`
- `polished_sentence` ← `report.structure.rewrite.minimal.text`

## 五、自动触发链路

```
POST /api/v1/messages（纠错）
  → 现有纠错逻辑（LLM 报告 + 入库）不变
  → 返回 200 + 报告给前端
  → 若 has_errors=true：BackgroundTasks 后台触发笔记保存
      → 独立 session 内调笔记 LLM（归纳 8 字段）
      → 按 error_type 分组
      → original_sentence ← 用户消息 content
      → polished_sentence ← report.structure.rewrite.minimal.text
      → 入库 notes + note_cases
  → has_errors=false：不触发
```

## 六、接口契约

### `POST /api/v1/notes/save`
**完全删除**（不再由前端调用）。

### `GET /api/v1/notes`（列表）

```json
{
  "notes": [
    {
      "id": "uuid",
      "rule_title": "第三人称单数主谓一致",
      "knowledge_point": "一般现在时中...",
      "case_count": 1,
      "updated_at": "2026-09-01T..."
    }
  ]
}
```

按用户过滤，按 `updated_at` 倒序。

### `GET /api/v1/notes/{note_id}`（详情）

```json
{
  "id": "uuid",
  "rule_title": "...",
  "knowledge_point": "...",
  "warning": "...",
  "alternatives": ["...", "...", "..."],
  "feynman_question": "...",
  "cases": [
    {
      "id": "uuid",
      "original_sentence": "She go to school. He go home.",
      "polished_sentence": "She goes to school. He goes home.",
      "change_details": "She go → She goes; He go → He goes",
      "error_root": "主谓不一致",
      "created_at": "2026-09-01T..."
    }
  ]
}
```

### `DELETE /api/v1/notes/{note_id}`、`DELETE /api/v1/notes/{note_id}/cases/{case_id}`
保留不变，按用户隔离删除。

## 七、前端变更

### 移除
- 纠错页报告卡片的「记笔记」/「全部记笔记」按钮及交互

### 笔记列表页
- 卡片展示 `rule_title` + `knowledge_point` 摘要 + `case_count` + `updated_at`
- 展开查看详情：规则级 4 字段（⑤⑥⑦⑧）+ 案例列表（①②③④）
- 空态文案改为：「去纠错页写一段英文，AI 会自动为你沉淀笔记」
- 加载/错误态沿用现有逻辑

## 八、错误处理与边界

- 笔记 LLM 超时/不可用/返回无效 → 记日志、静默丢弃，不影响纠错结果
- `has_errors=false`：不触发保存
- `rewrite.minimal` 为 null（极端）：跳过保存并记日志
- 多用户隔离按 `user_id` 过滤
- 列表按 `updated_at` 倒序

## 九、测试计划

### 后端
| 测试 | 覆盖点 |
|------|--------|
| 笔记模型迁移 | 新字段 + 唯一键 + FK |
| 笔记 LLM prompt | 8 字段 JSON schema，按 `error_type` 分组 |
| 自动触发 | `POST /messages` 成功后台触发（mock LLM） |
| 无错误不触发 | `has_errors=false` 不生成笔记 |
| 同句同类合并 | 同 `error_type` 多错误 → 1 笔记 1 案例 |
| 多类型拆分 | 不同 `error_type` → 独立笔记 |
| `polished_sentence` | 取 `rewrite.minimal.text` |
| `original_sentence` | 取 `source_text` |
| 列表/详情 | 新字段响应，按 `updated_at` 倒序，按用户隔离 |
| 删除 | 按用户隔离 |
| 后台 LLM 失败 | 静默丢弃不抛错 |

### 前端
- 笔记列表新字段展示
- 详情展开 8 字段
- 移除「记笔记」按钮后纠错页无回归

## 十、数据迁移

- 清库重建：新建 alembic migration 重建 `notes`/`note_cases` 表
- 旧数据清除（单账号自用可接受）
