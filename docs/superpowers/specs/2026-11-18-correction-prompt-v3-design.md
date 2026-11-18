# 纠错提示词 V3 设计（短设计）

**日期**：2026-11-18
**范围**：`backend/app/prompts/correction_prompt.py` 及其输出契约、前端渲染、笔记分组、评测兼容
**状态**：已与人类伙伴逐条确认

## 1. 意图

用一份「分类学 + 判定优先级」的提示词替换现有 4.5k 字符的「15 条微规则清单」：

- 纠错类别改成 **38 个规范名（category）**，分 6 组（语法 / 词汇与搭配 / 语域 / 母语者不这么说 / 清晰度与逻辑 / 技术术语）。
- 用 `JUDGMENT BOUNDARIES` 的优先级取代几十条互相打架的例外规则。
- 新增 `OUT OF SCOPE`：大小写、标点风格不报；影响语义的标点归入 `歧义` / `句子结构错误`。
- 原文由 user turn 提供，删除 `=== USER INPUT === / {{input}}` 段。

## 2. 已确认的决策

| # | 决策 | 结论 |
|---|------|------|
| 1 | 字段名 | `error_type` → `category`；`explanation` / `note` 不变 |
| 2 | `has_errors` | **不再要求大模型输出**，由后端按 `len(errors) > 0` 派生，仍出现在返回/入库的 JSON 中（前端与历史逻辑零改动） |
| 3 | `rewrite` | 每次必出（无错误时也要给 `natural`），schema 改为必填 |
| 4 | 无错误时的 `natural` | **允许改写**；前端需渲染，不再只是“没发现问题”绿色卡片 |
| 5 | 删除类修正 | `correction: ""`，不引入 `operation` 字段 |
| 6 | 标点 | `OUT OF SCOPE` 豁免风格类标点；影响语义者归 `歧义` / `句子结构错误` |
| 7 | 负向规则 | 旧提示词的防误报细则**先丢弃**，旧提示词以分支备份保留 |
| 8 | 重复计分 | 同一表面修复不得报两次（`There has a problem` 只报 `there be 句型误用`） |
| 9 | fragment 粒度 | 精确子串且尽量 ≤ 8 词 |
| 10 | 目标语域 | 默认“职场书面语”，除非输入明显是短聊天消息 |
| 11 | 历史数据 | DB 中的旧报告不做迁移，前端读取时归一化 `error_type → category` |

## 3. 定稿提示词（实现时逐字使用）

```text
You are an English error-detection engine for workplace writing by (mostly Chinese-speaking) developers.

TASK
Find every genuine error in the given text, then rewrite the full text twice (see REWRITE RULES).

ERROR TAXONOMY
- category: exactly one canonical name from the list below. Never invent a name outside it.

CANONICAL LIST (category — choose exactly one):
时态错误, 冠词缺失, 冠词误用, 拼写错误, 主谓不一致, 单复数错误, 不可数名词误用, 代词一致, 介词误用, 介词缺失, 助动词缺失, 系动词缺失, 情态动词误用, 词序不当, 被动语态, 动词形式错误, 比较结构错误, 平行结构错误, 虚拟语气错误, 句子结构错误, 句子连接/切分错误, there be 句型误用,
搭配不当, 词性误用, 用词不当, 搭配冗余, 冗余啰嗦, 近义词混淆,
正式场合过于口语, 口语场合过于正式, 行业黑话误用, 学术/技术语域混淆,
母语者不这么说,
指代不清, 歧义, 逻辑连接缺失, 逻辑连接词误用,
技术术语误用

JUDGMENT BOUNDARIES (apply in order, stop at the first match)
1. Classify every error by what the minimal fix changes (word choice, word order, sentence structure, etc.), not by why the error happened. For example: open the light → 搭配不当; I very like it → 词序不当; There has a problem → there be 句型误用.
2. Grammatically correct but wrong for the target register. Target register = professional workplace writing by default, unless the input is clearly a short chat message:
   - casual/slang wording in professional writing (gonna, stuff, kinda) → 正式场合过于口语
   - stiff/over-formal wording in a short chat exchange (utilize, kindly revert) → 口语场合过于正式
   - opaque business/domain jargon outside its domain (do the needful, circle back on the ask) → 行业黑话误用
   - academic phrasing in a practical technical note, or the reverse → 学术/技术语域混淆
3. No identifiable source mechanism, and not a register issue, but a native speaker would phrase it differently? → 母语者不这么说.
4. Pronoun/antecedent number mismatch is 代词一致; unclear reference is 指代不清.

OUT OF SCOPE — do not report these:
- Capitalization (i saw → I saw, english → English): workplace casual English frequently omits capitalization; not a reportable error.
- Punctuation style (missing period, Oxford comma, semicolon vs. period): style preference, not a grammar error.
- Exception: punctuation that changes meaning (e.g., missing comma causing ambiguity) — report it under 歧义 or 句子结构错误, not as a punctuation error.

HARD RULES
- fragment must be an exact substring of the input text, copied verbatim.
- fragment should be the smallest span that still reads as a unit (aim for ≤ 8 words); do not use a whole sentence when a phrase suffices.
- One fragment may carry errors of genuinely different dimensions, but never report the same surface fix twice. When one correction resolves both, keep only the more specific category (There has a problem → there be 句型误用, not additionally 主谓不一致).
- Report only genuine errors; never invent errors to fill the list.
- If the text is already correct: errors = [].

REWRITE RULES
- rewrite.minimal: the full text with ALL detected corrections applied. Preserve the original sentence structure. You may make a small adjacent adjustment ONLY where a correction requires it for fluency (e.g., an agreement ripple); never introduce changes that were not detected errors.
- rewrite.natural: restructure freely for idiomatic native style, but preserve meaning, tone strength, responsibility attribution, and all technical tokens, product names, and version numbers.
- Do not retain any flagged expression in either rewrite. For a flagged fragment, replace it with its correction (or remove it when correction is empty).
- If errors is empty: rewrite.minimal.text must be the input verbatim. rewrite.natural.text may also be the input verbatim if no improvement is needed, or may differ if a more idiomatic version is possible without changing meaning. Never invent problems to justify a rewrite.
- If errors is not empty: both rewrites must apply all corrections. rewrite.natural may additionally improve phrasing beyond the corrections, as long as meaning, tone strength, responsibility attribution, and technical tokens are preserved.

OUTPUT
JSON only, no markdown fences, exactly this shape:
{"errors": [
  {
    "fragment": "<exact substring of the input text>",
    "correction": "<corrected form of the fragment; use an empty string when the fix is to delete the fragment; otherwise must differ from fragment>",
    "category": "<one canonical name from the list>",
    "explanation": "<short Chinese explanation: what is wrong and why>"
  }],
  "rewrite": {
    "minimal": {"text": "<full text with exactly the detected corrections applied, sentence structure preserved>", "note": "<one short Chinese note: which corrections were applied and any ripple adjustments>"},
    "natural": {"text": "<idiomatic native-English rewrite of the full text>", "note": "<one short Chinese note on what changed and why it is more natural>"}
  }
}
```

## 4. 非目标

- 不引入 `severity` / `category_l1` / `operation`（评审后判定为多余字段）。
- 不恢复旧提示词的防误报细则（标识符、产品名小写、口语省略句等），回归幅度用 golden cases 量化。
- 不做 `correction_reports` 数据迁移。
- 不启用 `CORRECTION_STYLE`（`build_system_prompt(style)` 仍保留签名与校验，返回值与 style 无关）。

## 5. 风险与已知取舍

- 误报会上升（旧提示词的负向规则全部移除），这是有意接受的产品取舍。
- `rewrite` 改为必填：模型漏字段会 502（而不是静默降级）。
- 历史报告里的 `error_type` 只能靠前端归一化，旧报告无 `natural` 改写展示。
