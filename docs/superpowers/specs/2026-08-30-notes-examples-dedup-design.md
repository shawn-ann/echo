# 笔记示例与错误案例去重设计文档（notes-examples-dedup）

**所属**：地道英语纠错 · 智能笔记本 | **版本**：V0.2 | **状态**：草稿 | **日期**：2026-08-30
**依赖**：`backend/app/models/note.py`、`backend/app/prompts/note_prompt.py`、`backend/app/services/note_service.py`、`backend/app/schemas/note.py`、`web/src/components/notes/NoteCard.tsx`、`web/src/components/notes/NoteCaseItem.tsx`

> 本文档定义记笔记功能的增强设计：新增 AI 生成的通用示例（examples），并将错误案例数据源从 LLM 自由生成的 example 字符串改为结构化错误引用（fragment + correction），从根上解决案例重复引用问题。

> **执行方式变更**：本文档的**生成契约（examples/references/去重/数据模型）全部保留不变**，仅将保存执行从「同步同步调用」改为「后台异步执行」（`POST /notes/save` 返回 `202`，规则后台生成后刷新列表页可见）。详见 `notes-async-save-design.md`（08-30）。

## 〇、背景与目标

- **现状问题**：记笔记功能已上线（F-02），但错误案例存在重复引用问题。同一条规则（如「第三人称单数主谓一致」）下出现多条几乎相同的案例，均来自同一次纠错。
- **根因分析**：当前 `NoteCase.example` 是 LLM 保存笔记时自由生成的字符串（如 `She have → She has; she go → she goes`），跨调用不稳定（LLM 每次措辞不同）→ 去重失效、重复引用。
- **本次目标**：
  1. 新增 AI 生成的**通用示例**（examples），展示规则本身，与用户错误解耦
  2. 错误案例数据源改为**结构化错误引用**（fragment + correction，透传自纠错报告），LLM 只归组不改写
  3. 通过 DB 唯一约束从根上消除重复引用

## 一、已确认决策

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | AI 示例生成时机 | **新建规则时生成固定示例**（与 description 一并返回，固定存储） |
| 2 | AI 示例内容形式 | **正确用法示例 + 简短说明**（不依赖用户具体错误） |
| 3 | AI 示例数量 | **每条规则 3 个** |
| 4 | 示例存储 | **方案 A：`notes.examples` JSONB 列**（内嵌，无单独表） |
| 5 | 案例数据源 | **结构化错误引用**：`fragment` + `correction`，替代 `example` 字符串 |
| 6 | references 生成 | LLM **透传**输入 errors 的 fragment，**只归组不改写** |
| 7 | correction 来源 | LLM **不输出** correction，后端从输入 errors 按 fragment 匹配（取第一个） |
| 8 | 去重键 | `(note_id, user_id, source_text, fragment)` DB 唯一约束 |
| 9 | 同规则多错误 | 一条规则可对应多个 case（每个 fragment 一行，如 She have / she go 各一行） |
| 10 | 存量数据 | `note_cases.example` **清空重建**，不迁移 |

## 二、数据模型变更

### 2.1 `notes` 表：新增 `examples` JSONB 列

```python
class Note(Base):
    __tablename__ = "notes"
    # ... 现有字段
    examples: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # 结构：[{"text": "She plays tennis every day.", "note": "play → plays"},
    #        {"text": "He goes to work by bus.", "note": "go → goes"},
    #        {"text": "It rains a lot in spring.", "note": "rain → rains"}]
```

### 2.2 `note_cases` 表：重构 + 唯一约束

```python
class NoteCase(Base):
    __tablename__ = "note_cases"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(FK notes CASCADE)
    user_id: Mapped[uuid.UUID] = mapped_column(FK users CASCADE)
    fragment: Mapped[str] = mapped_column(Text, nullable=False)    # 原 example 列改造
    correction: Mapped[str] = mapped_column(Text, nullable=False)   # 新增
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(FK messages SET NULL)
    created_at: Mapped[datetime]

    __table_args__ = (
        UniqueConstraint("note_id", "user_id", "source_text", "fragment",
                         name="uq_note_cases_dedup"),
    )
```

### 2.3 关键设计点

1. **去重键 `(note_id, user_id, source_text, fragment)`**——同一用户同一规则下，同原文 + 同错误段只保留一条。`fragment` 来自纠错报告（确定性），跨 LLM 调用稳定。
2. **同规则多错误**：一条规则可对应多个 case（`She have` / `she go` 是不同 fragment，各自一行）。
3. **DB 层兜底**：即使前端重复点击或 LLM 重复归组，唯一约束保证不重复插入。

## 三、保存时 LLM I/O 契约

### 3.1 输入（不变）

```
- existing_rules: [{rule_title}]
- source_text: str
- errors: [{error_type, fragment, explanation, correction}]   # 结构化错误块
```

### 3.2 输出（调整）

```json
{
  "results": [
    {
      "rule_title": "第三人称单数主谓一致",
      "description": "在一般现在时中，主语为第三人称单数时，实义动词加 -s/-es，助动词用 has...",
      "examples": [
        {"text": "She plays tennis every day.", "note": "play → plays"},
        {"text": "He goes to work by bus.", "note": "go → goes"},
        {"text": "It rains a lot in spring.", "note": "rain → rains"}
      ],
      "references": ["She have", "she go"]
    }
  ]
}
```

### 3.3 字段规则

| 字段 | 类型 | 说明 |
|------|------|------|
| `rule_title` | str | 已有规则必须原样返回（去重指令不变）；新规则生成 |
| `description` | str | 始终生成（新建时使用；匹配时后端忽略） |
| `examples` | list | 3 个正确用法示例 + 说明；仅新建规则时后端使用 |
| `references` | **list[str]** | 仅 fragment 字符串数组；从输入 errors 归组透传，**不改写** |

### 3.4 correction 由后端匹配

LLM **不输出** correction。后端从输入 errors 按 fragment 匹配：

```python
errors_by_fragment = {e.fragment: e.correction for e in errors}   # 取第一个匹配
```

- 匹配到 → 存 case
- 未匹配到 → 静默跳过该 fragment（防御 LLM 归组了不在 errors 中的文本）

### 3.5 prompt 约束要点

写在保存时 LLM 的 system prompt 中（在现有粒度/去重/合并指令基础上调整）：

1. **references 生成**：从输入「错误列表」中**原样选取**属于该规则的 `fragment` 文本，放入 `references` 数组。**不得改写、不得补充不在错误列表中的文本**。
2. **同类错误归组**：同一规则的多个错误段（如 `She have` / `she go`）归入同一条 result 的 references 数组。
3. **examples 要求**：给出 3 个**正确用法**的完整英文句子（不参考用户错误），各配一句简短中文说明，覆盖该规则的典型场景。
4. **去重指令**：新规则的 rule_title 与已有规则库语义相同，必须原样返回那条的 rule_title。

## 四、后端保存逻辑

**去重策略：保存前先查重（方案 1），DB 唯一约束作为最终兜底。** 不依赖异常处理——`session.rollback()` 会回滚整个事务，副作用大。

```python
async def save_notes(session, user_id, source_message_id, source_text, errors, llm_client):
    existing_rules = await _get_existing_rule_titles(session)
    parsed = await _call_llm_and_parse(llm_client, existing_rules, source_text, errors)

    errors_by_fragment = {e["fragment"]: e["correction"] for e in errors}

    saved = []
    for result in parsed.results:
        note = (await session.execute(
            select(Note).where(Note.rule_title == result.rule_title)
        )).scalars().first()

        if note is None:
            note = Note(rule_title=result.rule_title,
                        description=result.description,
                        examples=result.examples)
            session.add(note)
            await session.flush()
            is_new = True
        else:
            is_new = False  # 已有规则：忽略 examples（规则示例已存在，不覆盖）

        for fragment in result.references:
            correction = errors_by_fragment.get(fragment)
            if not correction:
                continue  # 防御：LLM 归组了不在 errors 中的文本

            # 先查重：同 (note, user, source_text, fragment) 已存在则跳过
            existing_case = (await session.execute(
                select(NoteCase.id).where(
                    NoteCase.note_id == note.id,
                    NoteCase.user_id == user_id,
                    NoteCase.source_text == source_text,
                    NoteCase.fragment == fragment,
                )
            )).scalars().first()
            if existing_case is not None:
                continue  # 重复案例，静默跳过

            case = NoteCase(note_id=note.id, user_id=user_id,
                            fragment=fragment, correction=correction,
                            source_text=source_text,
                            source_message_id=source_message_id)
            session.add(case)
            await session.flush()
            saved.append(SavedNoteItem(note_id=note.id,
                                       rule_title=note.rule_title,
                                       is_new=is_new, case_id=case.id))

    await session.commit()
    return saved
```

> 说明：DB 唯一约束 `uq_note_cases_dedup` 作为并发/竞态兜底；正常情况下先查重已拦截重复。若极端并发触发约束冲突，则由上层捕获 `IntegrityError` 返回 409 或重试（MVP 单用户场景概率极低，不专门处理）。

## 五、前端展示

### 5.1 笔记详情展开：示例与错误分离

```
┌─ 第三人称单数主谓一致 ──────────────────┐
│ 📖 讲解                                  │
│ 在一般现在时中，主语为第三人称单数时...   │
│                                          │
│ ✨ 示例                                  │
│ • She plays tennis every day. (play→plays)│
│ • He goes to work by bus. (go→goes)      │
│ • It rains a lot in spring. (rain→rains) │
│                                          │
│ 📝 我的错误                              │
│ ┌───────────────────────────────────┐   │
│ │ ❌ She have  →  ✅ She has         │   │
│ │ 原文：She have many book...        │ [×]│
│ ├───────────────────────────────────┤   │
│ │ ❌ she go  →  ✅ she goes          │   │
│ │ 原文：She have many book...        │ [×]│
│ └───────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

- **示例区**：`detail.examples` 渲染（text + note），只读，无删除按钮
- **错误区**：`detail.cases` 渲染（fragment→correction 对照 + 原文），可删除
- `NoteCaseItem` 改造：从解析 `example.split('→')` 改为直接用 `fragment` / `correction` 字段

### 5.2 列表折叠态

不变：`rule_title` + `description` + `case_count` + `updated_at`。

## 六、迁移

`alembic revision --autogenerate -m "add note examples and refactor note_cases"`，手动调整生成的迁移脚本：

1. **`notes` 表**：新增 `examples` JSONB 列（`server_default` 为 `'[]'`，`nullable=False`）
2. **`note_cases` 表**：
   - 原 `example` 列**改名**为 `fragment`（存量值即「错误→正确」字符串，会被清空重建，无需转换）
   - 新增 `correction` 列（Text, nullable=False）
   - 新增唯一约束 `uq_note_cases_dedup`（`note_id, user_id, source_text, fragment`）
3. **存量数据清空**：迁移脚本内 `TRUNCATE note_cases`（清空所有案例）；`notes` 行保留，`examples` 初始为空数组

**存量数据策略**（用户已确认清空重建）：
- `note_cases`：清空，用户重新保存笔记时按新契约重建
- `notes`：保留现有规则标题/描述，但 `examples` 为空（存量规则暂无示例，可后续重新保存补全或接受）

> 迁移顺序注意：先加列/改名，再 TRUNCATE，最后加唯一约束（避免旧数据违反约束）。

## 七、测试策略

### 7.1 后端测试（pytest，MockLLM）

- **模型**：Note.examples 默认空数组；NoteCase 唯一约束生效
- **保存**：
  - 新规则：存 examples（3 个）+ 逐条 references（fragment+correction）
  - 已有规则：忽略 examples，只追加 references
  - 去重：同 (note, user, source_text, fragment) 重复保存只留一条
  - correction 匹配：后端从 errors 匹配（LLM 输出不含 correction）
  - 未匹配 fragment：静默跳过
  - 同规则多错误：`She have` / `she go` 各生成一个 case
- **API**：save/list/detail 契约与现有字段对齐（case 返回 fragment/correction）

### 7.2 前端测试（Playwright E2E）

- 笔记详情展开：示例区渲染（3 个示例）
- 错误区渲染（fragment→correction 对照）
- 重复保存不产生重复案例

### 7.3 测试 gotcha

- conftest `clean_sessions` 已含 note_cases/notes 清理（无需改）
- MockLLMClient `_default_responder` 需更新：笔记保存响应改为新契约（examples + references）

## 八、文件改动清单

### 后端
- `backend/app/models/note.py` — Note.examples + NoteCase 重构（fragment/correction + 唯一约束）
- `backend/app/prompts/note_prompt.py` — 输出契约调整（examples + references）
- `backend/app/schemas/note.py` — NoteRuleResult 增加 examples/references；NoteCaseItem 改 fragment/correction
- `backend/app/services/note_service.py` — save_notes 逻辑（examples 存储 + correction 匹配 + 先查重）
- `backend/tests/test_note_service.py` — 更新保存测试
- `backend/tests/test_notes_api.py` — 更新 API 契约断言
- `backend/tests/test_note_prompt.py` — 更新 prompt 测试
- `backend/alembic/versions/<hash>_add_note_examples_and_refactor_note_cases.py` — 新迁移

### 前端
- `web/src/api/notes.ts` — NoteCaseItem 类型改 fragment/correction；NoteDetailResponse 增加 examples
- `web/src/components/notes/NoteCaseItem.tsx` — 直接用 fragment/correction 字段
- `web/src/components/notes/NoteCard.tsx` — 渲染 examples 示例区
- `web/tests/e2e/notes.spec.ts` — 更新断言

## 九、未来演进

1. **复习功能（F-03）**：基于 examples（规则示例）+ cases（用户错误）做间隔重复练习——示例区可作为「看示例回忆规则」的练习材料。
2. **示例管理**：若未来需单独增删示例，可从 JSONB 拆为独立表。
3. **更精细去重**：若需「跨原文去重」（不同句子犯同一个错也合并），可改为 `(note_id, user_id, fragment)` 唯一——但会丢失场景区分，需产品权衡。

---

**变更记录**

- V0.2 · 2026-08-30 · 顶部注明执行方式改为异步（`POST /notes/save` 返回 202，后台入账，生成契约 examples/references/去重不变），详见 `notes-async-save-design.md`

- V0.1 · 2026-08-30 · 初稿：新增 AI 通用示例 + 错误案例结构化重构（fragment/correction 替代 example）+ 唯一约束去重
