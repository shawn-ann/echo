# 提示词验收设计文档（prompt-acceptance-design）

**所属**：地道英语纠错 · 智能笔记本 | **版本**：V0.1 | **状态**：草稿 | **日期**：2026年8月
**对应功能**：F-01 会话式文本纠错 · 提示词工程与验收
**依赖**：`backend/app/core/config.py`（`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`，pydantic-settings + `.env` 驱动）

> 本文档定义**真实 LLM 提示词**与**验收脚本**的设计。本轮交付**仅提示词 + 验收脚本**，不接入真实 LLM 到产品链路、不改 Pydantic schema / 前端 / Mock。验收通过后再同步 PRD 与契约（见 §7）。

## 〇、背景与目标

- 产品目前 LLM 层用确定性 Mock（`LLM_MODE=mock`），真实提示词尚未编写（技术设计 `02-Correction.md` §1.2 注明"真实提示词另行编写文档"）。
- 目标：产出一条**符合要求的提示词**（`SYSTEM_PROMPT` 常量），并用 **9 个 golden 用例**做验收，脚本判定其结构合法性与语义正确性。
- 范围边界：不接真实 LLM 到产品链路、不改 schema/前端/Mock；运行配置复用 `.env`（非环境变量注入）。

## 一、已确认决策

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 交付范围 | 提示词 + 验收 Python 脚本；9 示例做 golden 测试集 |
| 2 | 运行配置 | 复用 pydantic-settings，`.env` 文件驱动（`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` 已存在 config.py） |
| 3 | 提示词位置 | `backend/app/prompts/correction_prompt.py`（`build_system_prompt(style)` 场景参数化 + 默认 `SYSTEM_PROMPT` 导出） |
| 4 | Golden 用例 | `backend/app/prompts/golden_cases.json` 独立数据文件 |
| 5 | 验收脚本 | `backend/app/scripts/prompt_acceptance.py`（纯输出采集，生成报告） |
| 6 | 验收粒度 | 纯输出采集：只记录输入/实际输出（完整 JSON）/耗时，不做断言判定 |
| 7 | PRD 同步 | 先不改，验收通过后同步 |
| 8 | 领域定位 | 通用日常英语；技术术语/专有名词（GDSP、airflow、DSD-45874、pvc 等）原样保留 |
| 9 | 顶层结构 | **保持原 `intent/correction/reply`** |
| 10 | 错误对象 | **`category`（4 枚举）+ `error_type`（中文语法术语）同时由 LLM 输出（方案 A）** |
| 11 | learnings | **放 `correction` 内部**，含 `title/rule/instances[{wrong,right}]/examples[{wrong,right}]` |
| 12 | rewrite | **保持原 `minimal`/`natural` 两版（允许相同）** |
| 13 | severity | **不加** |
| 14 | 场景参数化 | `build_system_prompt(style)`，style ∈ {casual（默认，日常/职场口语）, formal（正式书面）}；`CORRECTION_STYLE` 配置切换 |

### 一.1 场景参数化设计

提示词从静态常量改为 `build_system_prompt(style)` 函数，按场景生成提示词。切换通过 `CORRECTION_STYLE` 配置字段（`.env`）控制，用户可随时切换。

| 维度 | casual（默认，日常/职场口语） | formal（正式书面） |
|------|------------------------------|---------------------|
| 场景描述 | 面向日常/职场口语场景（Slack/IM 工单对话、技术沟通） | 面向正式书面场景（邮件、技术文档、工单报告） |
| 口语省略（如 `getting an error?`） | **不判错**（口语场景正常表达，不列为修正项） | 判错，补全为书面完整形式（`Are you getting an error?`） |
| `natural` 改写风格 | 偏口语化（缩写、简短句） | 偏书面正式（完整句式、规范用词） |
| 其他（结构/错误类型表/术语/保留术语/learnings 格式） | 两场景共用 | 两场景共用 |

- 保留 `SYSTEM_PROMPT = build_system_prompt("casual")` 作为向后兼容导出
- `correction_service.py` 统一使用 `build_system_prompt(get_settings().CORRECTION_STYLE)`，废弃旧的占位 SYSTEM_PROMPT

## 二、报告 JSON 契约（version 1，合并结构）

> 顶层保持现有 `intent/correction/reply`；在 `correction` 内新增 `learnings`，并在 `errors[]` 内同时输出 `category` 与 `error_type`。

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "creating job",
        "explanation": "job 是可数名词单数，不能裸用，需加冠词",
        "correction": "creating a job"
      }
    ],
    "rewrite": {
      "minimal": { "text": "...", "explanation": "仅修正语法和用词，保留原句结构和语气" },
      "natural": { "text": "...", "explanation": "..." }
    },
    "learnings": [
      {
        "title": "可数名词单数不能裸用",
        "rule": "可数名词单数必须加冠词（a/an/the）或改为复数",
        "instances": [ { "wrong": "creating job", "right": "creating a job" } ],
        "examples": [ { "wrong": "I'm deploying service.", "right": "I'm deploying a service." } ]
      }
    ]
  },
  "reply": null
}
```

### 2.1 字段规则

| 字段 | 规则 |
|------|------|
| `intent` | `correction` / `follow_up`（保持原样；follow_up 时 `reply` 非空、`correction` 为 null） |
| `correction.has_errors` | bool；无错误为 false |
| `correction.errors[].category` | 4 枚举：`grammar`/`collocation`/`chinglish`/`style`（**LLM 输出**，方案 A） |
| `correction.errors[].error_type` | 中文语法术语：冠词缺失 / 时态错误 / 主谓不一致 / 不可数名词误用 / 语域错配 / 中式直译 / 用词不当 / 词序不当 / 搭配冗余 等（**LLM 输出**） |
| `correction.errors[].fragment` | 出错的原文片段（英文） |
| `correction.errors[].explanation` | 为什么错（中文） |
| `correction.errors[].correction` | 最小修正（英文） |
| `correction.rewrite` | `minimal` + `natural` 两版，各含 `text`/`explanation`；两版互异 |
| `correction.learnings[]` | 新增；每项 `title`/`rule`/`instances[{wrong,right}]`/`examples[{wrong,right}]`（examples 为对象数组） |
| `reply` | follow_up 时非空（保持原样） |

### 2.2 无错误表达

- `has_errors: false` 时：`errors`/`learnings` 为空，`rewrite.minimal` 与 `natural` 两版 `text` 均为**空字符串**、`explanation` 为空字符串。

### 2.3 术语与专名保留

- 技术术语、产品名、版本号、工单链接（`trigger_by`、`airflow`、`DSD-45874`、`pvc`、Jira 链接等）原样保留，不得改写或翻译；提示词中要求用反引号包裹展示。

## 三、示例 ↔ 契约映射

9 个 golden 示例的「错误分析」直接对应 `correction.errors[]`；「学到的规则」对应 `correction.learnings[]`；改写版本映射如下：

| 9 示例的改写版本 | 契约字段 | 验收处理 |
|----------------|---------|---------|
| 最小修正版 | `rewrite.minimal` | **精确比对**：文本与示例最小修正版一致 |
| 正式版 + 口语版 | `rewrite.natural` | **只校验存在且 ≠ minimal**；不要求等于正式版/口语版任一（`natural` 是"更自然/更地道"的单一版本，示例的正式/口语作为语义参考，不逐字断言） |

## 四、提示词草案（correction_prompt.py 的 SYSTEM_PROMPT）

> 基于用户提供的参考提示词改造，适配上述合并契约。完整内容在实现时落盘；此处列出**关键段落与约束**：

```text
你是英文纠错教练，面向通用日常英语场景（含技术/职场表达）。
结合对话上下文判断用户意图，只输出合法 JSON，不要用 markdown 代码块包裹。

## 意图判定
- 提交英文文本 → intent=correction，输出结构化纠错报告
- 纯中文或提问 → intent=follow_up，输出 reply（纯文本）

## correction 报告结构（严格按此 JSON）
{ "has_errors": bool,
  "errors": [
    { "category": "grammar|collocation|chinglish|style",
      "error_type": "中文语法术语（如：冠词缺失、时态错误、主谓不一致、不可数名词误用、语域错配、中式直译、用词不当、词序不当、搭配冗余）",
      "fragment": "出错的原文片段（英文）",
      "explanation": "为什么错（中文）",
      "correction": "最小修正（英文）" } ],
  "rewrite": {
    "minimal": { "text": "仅替换被标记错误，保留原句结构和语气（英文）", "explanation": "仅修正语法和用词，保留原句结构和语气" },
    "natural": { "text": "更自然/地道的整句改写（英文）", "explanation": "为什么更自然（中文）" } },
  "learnings": [
    { "title": "规则一句话（中文）",
      "rule": "规则说明（中文）",
      "instances": [ { "wrong": "错误写法（英文）", "right": "正确写法（英文）" } ],
      "examples": [ { "wrong": "错误写法（英文）", "right": "正确写法（英文）" } ] } ] }

## 关键约束
- 改写两版（minimal/natural）允许相同（若 minimal 已足够自然）
- natural 提供比 minimal 更自然/地道的整句改写，风格按上下文选择（正式或口语均可）
- 技术术语/专有名词原样保留，不得改写或翻译
- 区分"中式直译"（表达不存在/不自然）与"语域错配"（合法英语但语域不符）；error_type 相应标注
- category 与 error_type 一致：冠词缺失/时态/主谓一致等 → grammar；用词不当 → collocation 或 style；中式直译 → chinglish；语域错配 → style
- 无错误 → has_errors=false，errors/learnings 为空，两版 rewrite 的 text 为空字符串
- 每个不同规则归纳一条 learning；同类错误合并到同一条的 instances
- learnings 的 examples 为对象数组，每项含 wrong/right

## 返回格式（严格）
{"intent": "correction", "correction": { ... }, "reply": null}
```

## 五、验收脚本设计（prompt_acceptance.py）

### 5.1 流程

```
prompt_acceptance.py
├── 1. 加载配置（get_settings() 读 .env：LLM_BASE_URL/API_KEY/MODEL）
│       → 缺 key 打印「请先在 .env 配置 LLM_*」并退出码 1
├── 2. 加载 golden_cases.json + correction_prompt.SYSTEM_PROMPT
├── 3. 逐条：构建 messages([system, user=原文]) → 调 LLM → 解析 JSON
├── 4. 结构断言 structure_check(response, case)
├── 5. 语义断言 semantic_check(response, case)
├── 6. 输出逐条 PASS/FAIL + 失败详情
└── 7. 汇总：9/9 → 退出码 0；否则退出码 1
```

### 5.2 断言细则

**结构断言（每条用例必过）：**
- JSON 可解析；`intent` ∈ {correction, follow_up}；correction 路径下 `has_errors` 为 bool
- errors 每项 5 字段齐全：category / error_type / fragment / explanation / correction
- category ∈ 4 枚举；error_type 非空中文
- rewrite 有 `minimal`、`natural` 两键，各含 text/explanation
- learnings 每项 4 字段：title / rule / instances / examples；instances 与 examples 每项有 wrong/right

**语义断言（对照 golden_cases.json 的 expect）：**
- `fragment_contains` 命中：LLM 的 error.fragment 含期望片段
- `correction_contains` 命中：LLM 的 error.correction 含期望修正词
- `category_expected`：LLM 的 category 与期望一致（用于校验方案 A 自洽性示例）
- category↔error_type 一致性：冠词缺失/时态/主谓一致→grammar；中式直译→chinglish；语域错配→style
- `minimal` 文本 ≈ 示例「最小修正版」；`natural` 存在且 ≠ minimal
- `preserve_terms`：示例指定的技术术语/专名在输出全文保留
- `learnings_min`：learnings 条数达标
- 无错误用例：has_errors=false 且两版 rewrite = 原句

### 5.3 golden_cases.json 结构

```json
{
  "cases": [
    {
      "id": "C-01",
      "input": "Correct the trigger_by field set up logic when creating job.",
      "expect": {
        "has_errors": true,
        "error_count_min": 2,
        "must_have": [
          { "fragment_contains": "creating job", "correction_contains": "a job", "category_expected": "grammar", "error_type_contains": "冠词" },
          { "fragment_contains": "set up", "correction_contains": "setup" }
        ],
        "minimal_contains": "setup",
        "preserve_terms": ["trigger_by"],
        "learnings_min": 2
      }
    }
  ]
}
```

## 六、文件结构

```
backend/
├── app/core/config.py           （已有，LLM_* 字段，pydantic-settings + .env）
├── prompts/
│   ├── correction_prompt.py     （SYSTEM_PROMPT 常量）
│   └── golden_cases.json        （9 用例）
└── scripts/
    └── prompt_acceptance.py     （验收脚本）
```

## 七、验收通过后的后续（本轮不做）

1. 同步 PRD `02-Correction.md`（§4.5/§4.10）与架构契约：learnings 新增、category+error_type 双字段、无 severity
2. 升级 Pydantic schema `correction.py`、Mock `_default_responder`、前端 `CorrectionReportCard.tsx` 展示 learnings
3. 将 `SYSTEM_PROMPT` 接入 `correction_service.py` 的真实调用路径

---

**变更记录**

- V0.1 · 2026-08 · 初稿：基于 9 个 golden 示例与用户参考提示词，定稿合并契约（保持 intent/correction/reply 顶层 + correction 内新增 learnings + errors 双字段 category/error_type）；确认决策 13 项；定义验收脚本结构与断言；示例改写版本映射（最小修正→minimal、正式/口语→natural 语义参考）
