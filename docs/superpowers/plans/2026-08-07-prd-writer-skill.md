# PRD Writer Skill 中文化安装实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 aakashg 的 prd-writer skill 中文化后安装到 opencode 全局 skills 目录，使"每功能一份 PRD"的标准需求文档生成能力可用。

**Architecture:** 直接采用成熟的 aakashg/pm-claude-code-setup prd-writer SKILL.md 为基础，补充 YAML frontmatter（opencode 自动发现/触发必需），将全文翻译为中文本，安装至 `~/.config/opencode/skills/prd-writer/`，最后通过结构化验证命令确认安装正确。原文档保留为临时参考，不修改。

**Tech Stack:** Markdown、opencode skills 格式（YAML frontmatter）、bash 验证命令

**设计文档:** `docs/superpowers/specs/2026-08-07-prd-writer-skill-design.md`

---

### Task 1: 拉取原始源文件到临时参考位置

**Files:**
- 参考: `/var/folders/1d/289t41_508q5jx7jgb5s2vmh0000gn/T/opencode/prd-writer-source.md`（原始英文 SKILL.md）

- [ ] **Step 1: 创建目标目录**

Run:
```bash
mkdir -p ~/.config/opencode/skills/prd-writer
```

- [ ] **Step 2: 拉取原始英文 SKILL.md 到临时参考位置**

Run:
```bash
curl -sL "https://raw.githubusercontent.com/aakashg/pm-claude-code-setup/main/.claude/skills/prd-writer/SKILL.md" -o /var/folders/1d/289t41_508q5jx7jgb5s2vmh0000gn/T/opencode/prd-writer-source.md
wc -l /var/folders/1d/289t41_508q5jx7jgb5s2vmh0000gn/T/opencode/prd-writer-source.md
```

Expected: `260 /var/folders/1d/289t41_508q5jx7jgb5s2vmh0000gn/T/opencode/prd-writer-source.md`

- [ ] **Step 3: 确认目标目录为空**

Run:
```bash
ls -la ~/.config/opencode/skills/prd-writer/
```

Expected: 目录存在且为空（或仅 `.` 与 `..`）。

---

### Task 2: 写入完整中文化 SKILL.md

**Files:**
- Create: `~/.config/opencode/skills/prd-writer/SKILL.md`

- [ ] **Step 1: 写入中文版 SKILL.md**

使用 Write 工具创建 `~/.config/opencode/skills/prd-writer/SKILL.md`，内容为：

````markdown
---
name: prd-writer
description: >
  编写结构化的产品需求文档（PRD）。当用户要求编写 PRD、产品需求文档、产品规格、
  功能需求或产品需求说明时使用。生成前先澄清需求，按阶段演进，每个功能生成一份
  独立的 PRD 文档。这是"一功能一文档"的标准通用需求文档格式。
---

# PRD 编写器

## 触发条件

在以下请求时激活："编写 PRD"、"创建 PRD"、"起草 PRD"、"为 [功能] 编写 PRD"、"规划 [功能]"、"[功能] 一页纸"。

## 背景

PRD 没有死。糟糕的 PRD 死了。AI 终结了 10 页长的 PRD——没人会读那些。现代 PRD 更轻、更锐利、示例丰富。

核心理念：
- **思考要精准，不要追求完整。** 团队成员讨厌 AI 生成的冗余，渴望人类写的清晰。最多 2-3 页。
- **PRD 用于对齐，而非命令。** 它驱动讨论和决策。它是你讨论、辩论、参考和同步的依据。
- **工程师真正愿意读的 PRD 抓住"为什么"和"是什么"，而不是"怎么做"。**
- **PRD 不是一次写成的。** 它是随时间演进的活文档，反映团队在每个阶段的最新思考。

## 行为

### 第 1 步：动笔前先澄清

生成任何内容之前，先问 3-5 个澄清问题。根据缺失信息定制。常见缺口：

- 谁有这个问题？（不是"用户"——具体是哪些用户？职位、公司规模、情境）
- 我们有什么数据证明这值得做？（使用数据、工单、收入影响、客户引述）
- 范围是什么？（MVP 还是完整愿景——这份 PRD 处于什么阶段？）
- 工程团队是否已标记出技术约束？
- 时间线是什么？为什么？

在用户回答之前不要继续。没有明确答案的 PRD 模糊且无用。

如果用户处于早期阶段或仍在探索，生成一份"小规格"（第 1 阶段）——刚好够团队进一步探索。永远不要强迫一个需要先做探索的想法生成完整 PRD。

### 第 2 步：判定 PRD 阶段

PRD 分阶段演进。询问或推断用户所处的阶段：

| 阶段 | 是什么 | PRD 长什么样 |
|------|--------|-------------|
| **1. 团队启动** | 与设计+工程一起探索问题 | 一份"小规格"——标题、问题假设、2-3 个开放问题。可能只是一段话。 |
| **2. 规划评审** | 向领导层展示以排优先级 | 一页纸：问题、战略契合、初步数据、潜在方案。受众：VP、CEO。 |
| **3. 跨职能启动** | 引入销售、支持、市场、法务、QA | 扩展文档，需要跨职能输入。有说服力的问题 + 初步方案方向。 |
| **4. 方案评审** | 就方案表明立场 | 完整 PRD，含方案细节、流程、边界情况。可向高级领导层展示。 |
| **5. 上线就绪** | 工程交接 | 具体规格：边界情况、指标、用户流程。工程师会大量评论此版本。 |
| **6. 影响评审** | 上线后复盘 | 顶部添加结果链接。哪些有效、哪些无效、回滚说明。闭合"构建-测试-学习"闭环。 |

除非用户另有指定，默认第 4 阶段（方案评审）。这是最常见的 PRD 请求。

### 第 3 步：生成 PRD

每个章节都要凭本事立足。如果一个章节不驱动决策或防止错误，就删掉它。

**标题：**[功能名]
**作者：**[如已知则填用户名]
**日期：**[今天日期]
**状态：**草稿——[阶段名]

---

**1. 假设**
一句话。可测试。防止浪费开发周期。
格式："我们相信[动作]将为[用户]带来[结果]，以[指标]衡量。"

示例："我们相信为回访用户提供一键结账，将通过减少购买流程中的摩擦，将转化率提升 15%。"

**2. 问题**
- 谁有这个问题（特定用户细分，而非"所有人"）
- 有多严重（频率、严重程度、带数据）
- 今天他们如何解决（变通方案 = 强信号）
- 如果我们不解决会发生什么
- 客户证据：引述、工单、研究结果。没有客户证据的 PRD 是建立在假设上的 PRD。

**3. 战略契合**
- 为什么是这个问题，为什么是现在
- 与当前 OKR 的关联
- 为什么是这个方案而非我们考虑过的替代方案（明确解释有争议的决策——对齐就发生在这里）
- 相关时给出竞争背景（点名竞争对手，不要只说"市场"）

**4. 方案**
- 具体描述我们构建什么（不要模糊）
- 用户流程（逐步）
- 关键交互与状态
- 在有用处包含线框图描述或 ASCII 示意图
- 对于 AI 功能：15-25 个输入/输出对，展示预期行为、边界情况输入、拒绝标准，以及系统如何处理意外或畸形输入

**5. 非目标**
尽早说明。这是防范围蔓延的最好防线。
- 我们明确不做的事（要具体："V1 我们不做 Outlook 同步"）
- 考虑过但砍掉的功能，每个附一行理由
- 团队应理解的刻意取舍

**6. 成功指标**
- 主指标，带目标数字和时间框架
- 次要指标（2-3 个）
- 护栏指标（哪些不应恶化——带当前基线和可接受范围）
- 实验时：A/B 测试毕业的通过标准

**7. 上线计划**
- A/B 测试还是全量上线？渐进还是爆炸式？
- 若渐进：分阶段百分比（1% → 10% → 50% → 100%），各阶段附 go/no-go 标准
- 回滚计划：出错时如何撤销

**8. 开放问题**
- 用 `[NEED: data from X]` 占位符标记未决事项
- 每个问题附负责人和截止时间
- 不要隐藏未知——把它们摆到台面上

---

### 第 4 步：按阶段的清单

生成后，按该阶段的清单核对 PRD。向用户标注缺口。

**规划阶段清单：**
- [ ] 问题是否明确定义并带用户细分？
- [ ] 是否记录了当前状态（问题今天如何被忽视）？
- [ ] 是否识别出将变动的业务指标？
- [ ] 是否包含定性证据（不只是假设）？
- [ ] 是否识别出知识缺口并附负责人和时间线？
- [ ] 是否调研了竞争格局？

**方案评审清单：**
- [ ] 是否识别了边界情况？
- [ ] 是否确定了上线计划（实验 vs. 渐进）？
- [ ] 是否指定了跨职能需求（法务、市场、支持）？
- [ ] 是否定义了埋点与分析事件？
- [ ] 是否记录了风险与应对？

**上线就绪清单：**
- [ ] 是否解决了工程关切？
- [ ] 设计是否完成？
- [ ] 任务是否已估算并创建？
- [ ] GTM 赋能是否完成（销售、支持、文档）？
- [ ] 是否记录了假设与影响规模？
- [ ] 是否解决了所有边界情况？
- [ ] 是否准备了 QA 测试计划？

### 第 5 步：评审

生成后，主动提供：
- "要我用工程师、设计师或怀疑者的视角评审这份文档吗？"
- "要我把这份压缩成一页纸给高管评审吗？"
- "要我为 AI 行为添加含输入/输出示例的规格吗？"

---

## PRD 章节正反例

### 反面假设（模糊、不可测）
```
我们相信改进引导体验将带来更好的用户参与度。
```
没有具体动作、目标用户、指标或数字。"更好"和"改进"毫无意义。

### 正面假设（具体、可测）
```
我们相信将 7 步引导向导替换为面向中型市场团队（50-200 名员工）的单屏
设置，将把 7 日激活率从 23% 提升到 35%，因为根据我们 6 月队列分析，
67% 的用户目前在第 4 步（集成页）放弃。
```

### 反面问题章节（无证据）
```
用户觉得当前体验令人困惑，并会受益于改进。许多用户表示对更好方案有兴趣。
```
没有具体细节、数据、客户引述或变通方案的证据。这可以描述任何公司的任何功能。

### 正面问题章节（证据丰富）
```
对象：中型市场项目团队（50-200 人），使用我们的工具做任务管理。

有多严重：在我们最新的用户调研（n=340）中，67% 的受访者表示他们使用
独立的日历工具追踪项目截止时间。与"错过截止时间"相关的工单环比增加 23%。
离职访谈将"没有日历视图"列为流失的第 3 大原因。

当前的变通方案：用户导出任务为 CSV，手动把截止时间加到 Google 日历，
或使用经常崩溃的 Zapier 集成。他们会构建变通方案这一事实证明了痛点是真实的。

如果我们不解决：销售报告第四季度 3 笔 >5 万美元 ARR 的交易流失，
理由是"没有日历"。竞品 Asana 和 Monday.com 都在过去 12 个月推出了日历视图。
```

### 反面指标章节（模糊到可笑）
```
成功指标：
- 参与度：改进
- 用户满意度：提升
- 性能：维持
```

### 正面指标章节（具体、可操作）
```
成功指标：
| 指标 | 类型 | 基线 | 目标 | 时间框架 |
|------|------|------|------|---------|
| 日历视图采用率 | 主 | 0% | 周活跃用户的 40% | 90 天 |
| 周活跃用户 | 主 | 12,400 | 14,260（+15%） | 90 天 |
| "错过截止时间"工单 | 次 | 89/月 | 65/月（-27%） | 90 天 |

护栏：
- 日历视图页面加载时间：<2s（p95）
- 拖拽任务更新时间延迟：<500ms
- 整体应用崩溃率不得上升

通过标准（10% 灰度毕业）：日历视图采用率 > 暴露用户的 25%，
且两周后无护栏违规。
```

### 反面非目标（缺失或泛泛而谈）
```
非目标：
- 超出范围的项目将在未来版本中考虑
```

### 正面非目标（具体、防范围蔓延）
```
非目标：
- 我们不构建 Outlook/Exchange 同步。V1 仅支持 Google 日历。
  Outlook 依据企业需求放到 V2。
- 我们不构建资源容量规划。那是独立项目，由平台团队负责。
- 我们不替换 Google 日历。同步是增量的。
- 没有截止时间的任务不会出现在日历视图中。这是刻意的——
  让视图聚焦在截止时间上。
```

---

## 反模式（分析 500+ PRD 总结）

**花哨的结构、空洞的内容。** 每个章节都填了，但什么也没说。用"确保与法律标准对齐"之类的同义反复填充，而不是点名具体法律风险和应对方案。

**把思考外包出去。** 写"设计将探索最优布局"，而不是描述用户流程并推演边界情况。设计师应该挑战并改进你的思考——而不是收到一张空白画布。

**没有客户证据。** 最大的红旗。零用户引述、零工单、零数据点，意味着 PRD 建立在感觉上。哪怕 3 条客户引述，也能把规格从观点变成证据。

**隐瞒有争议的决策。** 方案 A 和 B 难分伯仲？说出来。解释你为什么选。对齐正是在这里发生。埋藏争议必然以阻碍者身份卷土重来。

**没有基线的指标。** "提升转化率"如果没有当前数值、目标和截止时间就毫无意义。没有基线的指标是愿望，不是度量。

**在上线就结束。** PRD 生命周期延伸到工程交接之后。上线后添加第 6 阶段结果链接。顶尖科技公司 50-92% 的功能未达预期——学习比规格更有价值。

**过度规定"怎么做"。** 工程师和设计师是有创造力的解题者。执着于"为什么"和"是什么"——而不是像素级细节或架构选择。规定用户结果，而非实现。

**试图同时写给所有受众。** 创始人觉得 PRD 过度雕琢，设计师觉得规定过死，工程师想要更多细节。解决之道：与阶段匹配。早期精简，后期详细，始终聚焦决策。

---

## 规则
- **思考要精准，不要完整。** PRD 保持在 2 页以内，除非用户要求更多。若超过 2 页，询问是否需要该深度。
- **用 `[NEED: 来自 X 的数据]` 标记缺失信息**，而不是编造。绝不虚构数据、客户引述或指标。
- **使用具体数字。** 不是"提升参与度"——而是"把 7 日激活率从 23% 提升到 35%"。
- **不要废话。** 每句话都应增加信息或驱动决策。砍掉通不过"所以呢？"测试的内容。
- **非目标要提前。** 防范围蔓延的最好防线。在方案章节之前写。
- **AI 功能**加一个专门章节：15-25 个行为示例（输入/输出对）、边界情况、拒绝标准、评估标准。
- **一份强 PRD 让团队无需开会即对齐。** 如果有人读完还需要 30 分钟讲解，它就没完成。
- **文档是你不在场时的声音。** 认真对待。
````

- [ ] **Step 2: 确认文件已创建且行数合理**

Run:
```bash
wc -l ~/.config/opencode/skills/prd-writer/SKILL.md
head -5 ~/.config/opencode/skills/prd-writer/SKILL.md
```

Expected: 约 250-270 行；`head` 显示 `---`、`name: prd-writer`、`description: >` 及描述文本。

---

### Task 3: 验证 frontmatter 语法

**Files:**
- Verify: `~/.config/opencode/skills/prd-writer/SKILL.md`

- [ ] **Step 1: 检查 frontmatter 完整性**

Run:
```bash
sed -n '1,8p' ~/.config/opencode/skills/prd-writer/SKILL.md
```

Expected: 第 1 行 `---`，第 2 行 `name: prd-writer`，第 3 行 `description: >`，之后是缩进的中文描述，末尾再次出现 `---` 闭合。前后无空行错误。

- [ ] **Step 2: 检查 `name` 唯一性与格式**

Run:
```bash
grep -c "^name:" ~/.config/opencode/skills/prd-writer/SKILL.md
```

Expected: `1`

---

### Task 4: 验证章节结构完整性

**Files:**
- Verify: `~/.config/opencode/skills/prd-writer/SKILL.md`

- [ ] **Step 1: 确认全部 8 个核心章节存在**

Run:
```bash
grep -n "^## \|^### " ~/.config/opencode/skills/prd-writer/SKILL.md
```

Expected 输出（顺序一致）：
```
## 触发条件
## 背景
## 行为
### 第 1 步：动笔前先澄清
### 第 2 步：判定 PRD 阶段
### 第 3 步：生成 PRD
### 第 4 步：按阶段的清单
### 第 5 步：评审
## PRD 章节正反例
## 反模式（分析 500+ PRD 总结）
## 规则
```

- [ ] **Step 2: 确认 7 段式 PRD 结构完整**

Run:
```bash
grep -n "^\*\*[1-8]\. " ~/.config/opencode/skills/prd-writer/SKILL.md
```

Expected: 包含 `1. 假设`、`2. 问题`、`3. 战略契合`、`4. 方案`、`5. 非目标`、`6. 成功指标`、`7. 上线计划`、`8. 开放问题`。

- [ ] **Step 3: 确认三个阶段的清单完整**

Run:
```bash
grep -c "清单：" ~/.config/opencode/skills/prd-writer/SKILL.md
```

Expected: `3`（规划阶段/方案评审/上线就绪）

---

### Task 5: 验证中文化（无残留英文章节标题）

**Files:**
- Verify: `~/.config/opencode/skills/prd-writer/SKILL.md`

- [ ] **Step 1: 检查原英文章节标题无残留**

Run:
```bash
grep -n "Anti-Patterns\|Good vs\|Step [0-9]\|^## Trigger\|^## Context\|^## Behavior\|^## Rules\|^# PRD Writer$" ~/.config/opencode/skills/prd-writer/SKILL.md
```

Expected: 无输出（grep 返回非零退出码）。

- [ ] **Step 2: 抽查正文无大面积英文残留**

Run:
```bash
grep -in "we believe\|onboarding\|non-goals\|success metrics\|out of scope" ~/.config/opencode/skills/prd-writer/SKILL.md
```

Expected: 无输出。说明正文示例已中文化（保留的 `PRD`、`MVP`、`OKR`、`QA`、`GTM`、`CSV`、`p95`、`ms`、`s` 等通用术语不算残留）。

---

### Task 6: 验证 skill 可被 opencode 发现

**Files:**
- Verify: `~/.config/opencode/skills/`（目录）

- [ ] **Step 1: 确认 prd-writer 出现在 skills 目录**

Run:
```bash
ls -la ~/.config/opencode/skills/
```

Expected: 列表中包含 `prd-writer` 目录（与 `superpowers` 软链并列）。

- [ ] **Step 2: 确认目录结构符合 opencode skill 规范**

Run:
```bash
find ~/.config/opencode/skills/prd-writer -type f
```

Expected: 仅 `SKILL.md` 一个文件。

---

### Task 7: 功能冒烟测试（可选但推荐）

**Files:**
- Use: `~/.config/opencode/skills/prd-writer/SKILL.md`

- [ ] **Step 1: 用中文触发词验证 skill 生效**

在 opencode 会话中发起：
```
帮我写一个任务的 PRD
```

Expected: 触发 prd-writer skill，先问 3-5 个澄清问题（目标用户、数据证据、范围、技术约束、时间线），再判定阶段并生成中文 PRD。

---

### Task 8: 提交实施计划文档

**Files:**
- Modify: `docs/superpowers/plans/2026-08-07-prd-writer-skill.md`（本文档，位于 echo 项目仓库内）

- [ ] **Step 1: 提交计划文档**

Run:
```bash
git add docs/superpowers/plans/2026-08-07-prd-writer-skill.md docs/superpowers/specs/2026-08-07-prd-writer-skill-design.md
git commit -m "docs: 新增 PRD Writer skill 中文化实施计划"
```

Note: 安装的 skill 文件位于 `~/.config/opencode/`（项目仓库之外），不入 git 版本管理。若需版本化该 skill，可后续将其复制到项目内 `.opencode/skills/`，本期不做（YAGNI）。
