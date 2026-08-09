# 提示词验收测试报告（Prompt Acceptance Report）

- **模型**：`deepseek-v4-flash`
- **总耗时**：470.5 秒
- **通过**：7/9

## 一、测试提示词（SYSTEM_PROMPT）

```text
你是英文纠错教练，面向通用日常英语场景（含技术/职场表达）。
结合对话上下文判断用户意图，只输出合法 JSON，不要用 markdown 代码块包裹，不要添加任何额外说明文字。

## 意图判定
- 提交英文文本 → intent=correction，输出结构化纠错报告
- 纯中文或提问 → intent=follow_up，输出 reply（纯文本）

## correction 报告结构（严格按此 JSON）
{"has_errors": bool,
 "errors": [
   {"category": "grammar|collocation|chinglish|style",
    "error_type": "中文语法术语（如：冠词缺失、时态错误、主谓不一致、不可数名词误用、语域错配、中式直译、用词不当、词序不当、搭配冗余）",
    "fragment": "出错的原文片段（英文）",
    "explanation": "为什么错（中文）",
    "correction": "最小修正（英文）"}],
 "rewrite": {
   "minimal": {"text": "仅替换被标记错误，保留原句结构和语气（英文）", "explanation": "仅修正语法和用词，保留原句结构和语气"},
   "natural": {"text": "更自然/地道的整句改写（英文）", "explanation": "为什么更自然（中文）"}},
 "learnings": [
   {"title": "规则一句话（中文）",
    "rule": "规则说明（中文）",
    "instances": [{"wrong": "错误写法（英文）", "right": "正确写法（英文）"}],
    "examples": ["英文例句1~2条，含 ❌ → ✅"]}]}

## 关键约束
- 改写两版（minimal/natural）必须互不相同；natural 提供一条比 minimal 更自然的整句改写，风格按上下文选择（正式或口语均可）
- 技术术语、产品名、版本号、工单链接（如 trigger_by、airflow、DSD-45874、pvc、Jira 链接）必须原样保留，不得改写或翻译，展示时用反引号包裹
- 区分"中式直译"（表达在英语中不存在或不自然）与"语域错配"（合法英语但与当前语境正式程度不符）；error_type 相应标注
- 典型中式直译必须识别并修正，如：release operation → release / release process；deploy operation → deployment；do some customize → do some customization；open the light → turn on the light
- category 与 error_type 一致：冠词缺失/时态错误/主谓不一致/不可数名词误用 → grammar；中式直译 → chinglish；语域错配 → style；其余用词/搭配问题 → collocation 或 style
- 无法确定作者意图的表达不列为修正项，不臆测改写
- 无错误 → has_errors=false，errors 与 learnings 为空，minimal 与 natural 两版 text 均为原句、explanation 为空字符串
- 每个不同规则归纳一条 learning；同类错误的多个实例合并到同一条 learning 的 instances 数组
- error_type、explanation、title、rule、examples 用中文；fragment、correction、instances 的 wrong/right、rewrite 的 text 保持英文

## 返回格式（严格遵守字段名）
{"intent": "correction", "correction": {"has_errors": ..., "errors": [...], "rewrite": {"minimal": {...}, "natural": {...}}, "learnings": [...]}, "reply": null}

```

## 二、测试用例与结果

### C-01 ✅ 通过（耗时 28.0s）

**输入句子**：Correct the trigger_by field set up logic when creating job.

**期待结果**：

| 需识别的错误片段 | 说明 |
|---|---|
| `creating job` | 应被识别并修正 |
| `set up` | 应被识别并修正 |

**纠错结果**：

| 严重片段 fragment | 错误类型 error_type | 修正 correction |
|---|---|---|
| `field set up` | 名词形式误用 | `field setup` |
| `creating job` | 冠词缺失 | `creating a job` |

**最小修正 minimal**：Correct the `trigger_by` field setup logic when creating a job.

**语法复核**：无语法错误 ✅

### C-02 ✅ 通过（耗时 39.2s）

**输入句子**：What do you mean you can't restart this webapp? getting an error?

**期待结果**：

| 需识别的错误片段 | 说明 |
|---|---|
| `getting an error` | 应被识别并修正 |

**纠错结果**：

| 严重片段 fragment | 错误类型 error_type | 修正 correction |
|---|---|---|
| `getting an error?` | 句子成分缺失 | `Are you getting an error?` |

**最小修正 minimal**：What do you mean you can't restart this `webapp`? Are you getting an error?

**语法复核**：无语法错误 ✅

### C-03 ✅ 通过（耗时 17.3s）

**输入句子**：In that case, the egress IP(出网ip) of GDSP cluster should be enough, right?

**期待结果**：

| 需识别的错误片段 | 说明 |
|---|---|
| `GDSP cluster` | 应被识别并修正 |

**纠错结果**：

| 严重片段 fragment | 错误类型 error_type | 修正 correction |
|---|---|---|
| `GDSP cluster` | 冠词缺失 | `the GDSP cluster` |
| `IP(出网ip)` | 中英混用 | `IP` |

**最小修正 minimal**：In that case, the egress IP of the GDSP cluster should be enough, right?

**语法复核**：无语法错误 ✅

### C-04 ✅ 通过（耗时 34.5s）

**输入句子**：This pvc should be created when adding resource pool. How many storage do we want?

**期待结果**：

| 需识别的错误片段 | 说明 |
|---|---|
| `resource pool` | 应被识别并修正 |
| `How many storage` | 应被识别并修正 |

**纠错结果**：

| 严重片段 fragment | 错误类型 error_type | 修正 correction |
|---|---|---|
| `when adding resource pool` | 冠词缺失 | `when adding a resource pool` |
| `How many storage` | 不可数名词误用 | `How much storage` |

**最小修正 minimal**：This `pvc` should be created when adding a resource pool. How much storage do we want?

**语法复核**：无语法错误 ✅

### C-05 ✅ 通过（耗时 65.7s）

**输入句子**：Is it possible to finished the testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it by this week? This would fix the issue that ariflow worker/scheduler logs is empty issue.

**期待结果**：

| 需识别的错误片段 | 说明 |
|---|---|
| `finished` | 应被识别并修正 |
| `logs is` | 应被识别并修正 |
| `empty issue` | 应被识别并修正 |
| `by this week` | 应被识别并修正 |

**纠错结果**：

| 严重片段 fragment | 错误类型 error_type | 修正 correction |
|---|---|---|
| `to finished` | 不定式误用 | `to finish` |
| `by this week` | 搭配不当 | `by the end of this week` |
| `ariflow` | 拼写错误 | ``airflow`` |
| `logs is empty issue` | 主谓不一致 | `logs are empty` |

**最小修正 minimal**：Is it possible to finish the testing for `https://jira.rakuten-it.com/jira/browse/DSD-45874` and release it by the end of this week? This would fix the issue that `airflow` worker/scheduler logs are empty.

**语法复核**：无语法错误 ✅

### C-06 ❌ 失败（耗时 41.7s）

**输入句子**：Sorry for the late response, we are working on the release operation, the restart function should work now, please check.

**期待结果**：

| 需识别的错误片段 | 说明 |
|---|---|
| `release operation` | 应被识别并修正 |

**纠错结果**：

| 严重片段 fragment | 错误类型 error_type | 修正 correction |
|---|---|---|
| `the release operation` | 中式直译 | `the release` |

**最小修正 minimal**：Sorry for the late response, we are working on the release, the restart function should work now, please check.

**语法复核**：仍有语法错误 ❌

**失败详情**：

- minimal 修正后的句子仍有语法错误

### C-07 ✅ 通过（耗时 83.4s）

**输入句子**：The issue airflow instance log have been fixed, could you please create a new airflow instance instead? The log viewer and download should be real quick.

**期待结果**：

| 需识别的错误片段 | 说明 |
|---|---|
| `have been fixed` | 应被识别并修正 |
| `real quick` | 应被识别并修正 |

**纠错结果**：

| 严重片段 fragment | 错误类型 error_type | 修正 correction |
|---|---|---|
| `have been fixed` | 主谓不一致 | `has been fixed` |
| `The issue `airflow` instance log` | 中式直译 | `The `airflow` instance log issue` |
| `fixed, could` | 逗号拼接 | `fixed. Could` |
| `real quick` | 语域错配 | `very quick` |

**最小修正 minimal**：The `airflow` instance log issue has been fixed. Could you please create a new `airflow` instance instead? The log viewer and download should be very quick.

**语法复核**：无语法错误 ✅

### C-08 ❌ 失败（耗时 87.0s）

**输入句子**：The empty log issue in PROD has been resolved now, I suspect this is also caused by the DB missing column. Then DSD-45874 is not urgent now, we can release both DSD-45874 & DSD-45252 next week.

**期待结果**：

| 需识别的错误片段 | 说明 |
|---|---|
| `DB missing column` | 应被识别并修正 |
| `is not urgent` | 应被识别并修正 |

**纠错结果**：

| 严重片段 fragment | 错误类型 error_type | 修正 correction |
|---|---|---|
| `resolved now, I suspect this` | 逗号拼接 | `resolved now; I suspect this` |
| `this is also caused by` | 时态错误 | `this was also caused by` |
| `the DB missing column` | 词序不当 | `a missing column in the DB` |
| `Then DSD-45874` | 语域错配 | `Therefore DSD-45874` |
| `not urgent now, we can release` | 逗号拼接 | `no longer urgent; we can release` |

**最小修正 minimal**：The empty log issue in PROD has been resolved now; I suspect this was also caused by a missing column in the DB. Therefore DSD-45874 is no longer urgent; we can release both DSD-45874 & DSD-45252 next week.

**失败详情**：

- 错误未识别: 'is not urgent'

### C-09 ✅ 通过（耗时 73.9s）

**输入句子**：By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error log when triggering dag.

**期待结果**：

| 需识别的错误片段 | 说明 |
|---|---|
| `some error log` | 应被识别并修正 |
| `triggering dag` | 应被识别并修正 |

**纠错结果**：

| 严重片段 fragment | 错误类型 error_type | 修正 correction |
|---|---|---|
| `some error log` | 名词单复数错误 | `any error logs` |
| `when triggering dag` | 冠词缺失 | `when triggering a `dag`` |
| `would be helpful if there are` | 虚拟语气误用 | `would be helpful if there were` |

**最小修正 minimal**：By the way, you could also check the running `worker pod` and `scheduler pod` more easily. This would be helpful if there were any error logs when triggering a `dag`.

**语法复核**：无语法错误 ✅

## 三、验收结论

- **总体结果**：7/9 通过（模型 `deepseek-v4-flash`，总耗时 470.5s）
- **验收原则**：只验证「纠错结果合理（关键错误无遗漏）+ 每个错误有实质修正 + minimal 修正后句子语法正确」；不限制错误数量（相邻错误合并可接受）、不限制 learnings 数量、不强制特定修正措辞。

**失败项**：

- **C-06**（41.7s）：minimal 修正后的句子仍有语法错误
- **C-08**（87.0s）：错误未识别: 'is not urgent'

> 说明：温度 0 下 LLM 对相同输入的识别集合仍存在偶发波动。失败项中若错误实际被识别（仅 fragment 措辞或漏检差异），属已知波动，可重跑确认；关键指标为「识别到的错误修正合理 + minimal 语法正确」。