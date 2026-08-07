# PRD Writer Skill 设计文档

**日期**：2026-08-07
**状态**：已批准

## 一、背景与目标

用户需要创建一个 skill 用于定义产品需求文档（PRD），核心要求：

- **标准通用的产品需求文档格式**（不绑定当前 echo 项目格式）
- **每个独立功能一份需求文档**，便于后期维护
- 若业内已有成熟 skill，优先直接使用，使用中再定制

## 二、行业调研结论

调研了 GitHub 上 5 个主流 PRD skill：

| Skill | Stars | 结构 | 是否符合"一功能一文档" |
|-------|-------|------|---------------------|
| pmYangKun/create-prd-skill | 283 | 一个产品一份 14 章大文档（B端专精） | ❌ |
| productskills/prd-writing | 54 | 每功能一份 ≤1200 词 7 段式 PRD | ✅ |
| aakashg/pm-claude-code-setup prd-writer | 149 | 每功能一份 PRD，先澄清需求再生成，6 阶段演进 | ✅ 最优 |
| FinStep-AI/prd-writer-skill | 76 | 一份 PRD + HTML 原型 | ⚠️ |
| luckybajaj22031996/pm-ba-claude-skills | 41 | 15 章节单文档 .docx | ⚠️ |

**选定方案**：直接采用 `aakashg/pm-claude-code-setup` 的 `prd-writer` skill。

## 三、设计

### 3.1 来源与安装位置

- 基础：aakashg prd-writer 的 `SKILL.md`（260 行，含触发条件/澄清步骤/阶段判定/7 段式模板/正反例/反模式清单/规则）
- 安装位置：`~/.config/opencode/skills/prd-writer/SKILL.md`（全局 skills 目录，跨项目可用）
- 必补项：增加 YAML frontmatter（`name: prd-writer` + 中文 `description` 触发描述），使 opencode 能自动发现并触发

### 3.2 保留的核心行为（不改）

- **Step 1 先澄清**：生成前问 3-5 个澄清问题（目标用户、数据证据、范围、技术约束、时间线）
- **Step 2 判阶段**：6 阶段演进（Kickoff→Planning→XFN→Solution Review→Launch→Impact），默认 Stage 4
- **Step 3 生成**：7 段式 PRD（Hypothesis/Problem/Strategic Fit/Solution/Non-Goals/Metrics/Rollout）
- 保留 Anti-Patterns、正反例、Rules（含 `[NEED: ...]` 不编造、非目标前置等）

### 3.3 定制点

- **输出中文化**：PRD 章节、提示语、示例、反模式全部翻译为中文，结构逻辑不变
- **触发描述中文化**：frontmatter 的 `description` 用中文编写，支持"需求文档/PRD/产品需求"等关键词触发
- 保留"每功能一份 PRD"用法：每次调用 = 生成一个功能的独立需求文档

### 3.4 不做清单

- ❌ 不引入 aakashg 整套 PM 体系（CLAUDE.md、其他 5 个 skill、模板库）
- ❌ 不引入 .docx 生成、HTML 原型生成等附加能力

## 四、交付物

1. `~/.config/opencode/skills/prd-writer/SKILL.md` — 中文版 prd-writer skill
2. 安装后验证：`~/.config/opencode/skills/` 下可见 `prd-writer`，frontmatter 正确、内容为中文本

## 五、验证方式

- 检查 frontmatter 语法正确（name + description）
- 检查核心三段式行为（澄清→判阶段→生成）完整保留
- 检查 7 段式章节结构完整
- 抽查翻译一致性（章节标题、示例、反模式均中文化）
