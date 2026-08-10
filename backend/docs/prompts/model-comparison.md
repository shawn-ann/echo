# 多模型纠错对比报告（Model Comparison）

- **用例数**：9
- **命中规则**：golden 错误片段与 LLM fragment 双向子串，或 golden 内容词（去停用词）任一在 LLM fragment 中，即算该 must_have 命中

## 一、总览

| 模型 | 思考 | 总耗时(s) | 平均/用例(s) | 命中率 | learnings 总数 |
|------|------|----------|-------------|--------|---------------|
| `qwen3.7-flash` | disabled | 35.9 | 4.0 | 16/16 | 13 |
| `qwen3.8-max` | disabled | 57.4 | 6.4 | 16/16 | 17 |
| `glm-5.2` | disabled | 65.9 | 7.3 | 16/16 | 20 |
| `qwen3.7-plus` | disabled | 115.8 | 12.9 | 16/16 | 18 |
| `qwen3.7-flash` | enabled | 227.0 | 25.2 | 16/16 | 17 |
| `glm-5.2` | enabled | 256.3 | 28.5 | 16/16 | 19 |
| `qwen3.7-plus` | enabled | 506.0 | 56.2 | 16/16 | 19 |
| `deepseek-v4-pro` | enabled | 215.7 | 24.0 | 15/16 | 13 |
| `deepseek-v4-pro` | disabled | 62.8 | 7.0 | 14/16 | 13 |
| `deepseek-v4-flash-0731` | enabled | 180.4 | 20.0 | 13/16 | 15 |
| `qwen3.8-max` | enabled | 1428.4 | 158.7 | 8/16 | 11 |
| `deepseek-v4-flash-0731` | disabled | 31.0 | 3.4 | 6/16 | 5 |

## 二、逐用例对比

### C-01

| 模型 | 思考 | 耗时(s) | 命中 | 识别错误数 | learnings | 错误列表 |
|------|------|--------|------|-----------|-----------|---------|
| `qwen3.7-flash` | disabled | 5.5 | 2/2 | 1 | 2 | [grammar]冠词缺失→creating the job |
| `qwen3.7-flash` | enabled | 27.4 | 2/2 | 2 | 2 | [grammar]冠词缺失→creating a job；[collocation]用词不当→setup |
| `qwen3.7-plus` | disabled | 12.8 | 2/2 | 2 | 2 | [grammar]冠词缺失→creating a job；[style]语域错配→Fix the trigger_by field setup logic |
| `qwen3.7-plus` | enabled | 51.1 | 2/2 | 2 | 2 | [grammar]词性误用→setup；[grammar]冠词缺失→creating a job |
| `qwen3.8-max` | disabled | 5.7 | 2/2 | 2 | 2 | [grammar]冠词缺失→creating a job；[style]语域错配→setup logic |
| `qwen3.8-max` | enabled | 79.7 | 2/2 | 2 | 2 | [collocation]用词不当→`trigger_by` field setup logic；[grammar]冠词缺失→when creating a j |
| `deepseek-v4-flash-0731` | disabled | 1.5 | 0/2 | 0 | 0 | （无） |
| `deepseek-v4-flash-0731` | enabled | 20.2 | 2/2 | 2 | 2 | [collocation]用词不当→setup logic；[grammar]冠词缺失→when creating a job |
| `deepseek-v4-pro` | disabled | 9.7 | 2/2 | 2 | 2 | [collocation]用词不当→setup；[grammar]冠词缺失→Correct the trigger_by field setup logic |
| `deepseek-v4-pro` | enabled | 22.2 | 2/2 | 2 | 2 | [grammar]用词不当→setup；[grammar]冠词缺失→creating a job |
| `glm-5.2` | disabled | 5.5 | 2/2 | 2 | 2 | [grammar]冠词缺失→creating a job；[collocation]用词不当→setup logic |
| `glm-5.2` | enabled | 24.9 | 2/2 | 2 | 2 | [grammar]词性错误→setup；[grammar]冠词缺失→creating a job |

### C-02

| 模型 | 思考 | 耗时(s) | 命中 | 识别错误数 | learnings | 错误列表 |
|------|------|--------|------|-----------|-----------|---------|
| `qwen3.7-flash` | disabled | 1.0 | 0/0 | 0 | 0 | （无） |
| `qwen3.7-flash` | enabled | 6.3 | 0/0 | 0 | 0 | （无） |
| `qwen3.7-plus` | disabled | 2.6 | 0/0 | 0 | 0 | （无） |
| `qwen3.7-plus` | enabled | 16.9 | 0/0 | 0 | 0 | （无） |
| `qwen3.8-max` | disabled | 2.2 | 0/0 | 0 | 0 | （无） |
| `qwen3.8-max` | enabled | 11.6 | 0/0 | 0 | 0 | （无） |
| `deepseek-v4-flash-0731` | disabled | 1.4 | 0/0 | 0 | 0 | （无） |
| `deepseek-v4-flash-0731` | enabled | 3.0 | 0/0 | 0 | 0 | （无） |
| `deepseek-v4-pro` | disabled | 2.3 | 0/0 | 0 | 0 | （无） |
| `deepseek-v4-pro` | enabled | 5.5 | 0/0 | 0 | 0 | （无） |
| `glm-5.2` | disabled | 1.3 | 0/0 | 0 | 0 | （无） |
| `glm-5.2` | enabled | 3.4 | 0/0 | 0 | 0 | （无） |

### C-03

| 模型 | 思考 | 耗时(s) | 命中 | 识别错误数 | learnings | 错误列表 |
|------|------|--------|------|-----------|-----------|---------|
| `qwen3.7-flash` | disabled | 3.3 | 1/1 | 1 | 1 | [style]语域错配→ |
| `qwen3.7-flash` | enabled | 18.6 | 1/1 | 1 | 1 | [grammar]冠词缺失→of the GDSP cluster |
| `qwen3.7-plus` | disabled | 11.4 | 1/1 | 2 | 2 | [grammar]冠词缺失→of the GDSP cluster；[style]语域错配→ |
| `qwen3.7-plus` | enabled | 52.9 | 1/1 | 1 | 1 | [grammar]冠词缺失→of the GDSP cluster |
| `qwen3.8-max` | disabled | 4.8 | 1/1 | 1 | 1 | [grammar]冠词缺失→of the GDSP cluster |
| `qwen3.8-max` | enabled | 43.6 | 1/1 | 2 | 2 | [grammar]冠词缺失→of the GDSP cluster；[style]中英混排→egress IP |
| `deepseek-v4-flash-0731` | disabled | 1.1 | 0/1 | 0 | 0 | （无） |
| `deepseek-v4-flash-0731` | enabled | 19.4 | 1/1 | 1 | 1 | [grammar]冠词缺失→the egress IP of the GDSP cluster |
| `deepseek-v4-pro` | disabled | 2.3 | 0/1 | 0 | 0 | （无） |
| `deepseek-v4-pro` | enabled | 13.4 | 1/1 | 1 | 1 | [grammar]冠词缺失→the GDSP cluster |
| `glm-5.2` | disabled | 6.3 | 1/1 | 2 | 2 | [grammar]冠词缺失→an IP；[grammar]冠词缺失→the GDSP cluster |
| `glm-5.2` | enabled | 27.0 | 1/1 | 2 | 2 | [grammar]冠词缺失→of the GDSP cluster；[chinglish]中式直译→IP |

### C-04

| 模型 | 思考 | 耗时(s) | 命中 | 识别错误数 | learnings | 错误列表 |
|------|------|--------|------|-----------|-----------|---------|
| `qwen3.7-flash` | disabled | 2.6 | 2/2 | 1 | 1 | [grammar]不可数名词误用→How much storage |
| `qwen3.7-flash` | enabled | 23.1 | 2/2 | 2 | 2 | [grammar]冠词缺失→adding a resource pool；[grammar]不可数名词误用→How much storage |
| `qwen3.7-plus` | disabled | 12.1 | 2/2 | 2 | 2 | [grammar]冠词缺失→adding the resource pool；[grammar]不可数名词误用→How much storage |
| `qwen3.7-plus` | enabled | 35.6 | 2/2 | 2 | 2 | [grammar]冠词缺失→a resource pool；[grammar]不可数名词误用→How much storage |
| `qwen3.8-max` | disabled | 5.9 | 2/2 | 2 | 2 | [grammar]冠词缺失→when adding a resource pool；[grammar]不可数名词误用→How much storage |
| `qwen3.8-max` | enabled | 46.1 | 2/2 | 2 | 2 | [grammar]冠词缺失→adding a resource pool；[grammar]不可数名词误用→How much storage |
| `deepseek-v4-flash-0731` | disabled | 2.8 | 0/2 | 0 | 0 | （无） |
| `deepseek-v4-flash-0731` | enabled | 20.2 | 2/2 | 2 | 2 | [grammar]冠词缺失→adding a resource pool；[grammar]不可数名词误用→How much storage |
| `deepseek-v4-pro` | disabled | 5.5 | 2/2 | 1 | 1 | [grammar]不可数名词误用→How much storage |
| `deepseek-v4-pro` | enabled | 31.4 | 2/2 | 2 | 2 | [grammar]冠词缺失→a resource pool；[grammar]不可数名词误用→How much storage |
| `glm-5.2` | disabled | 6.7 | 2/2 | 2 | 2 | [grammar]冠词缺失→adding a resource pool；[grammar]不可数名词误用→How much storage |
| `glm-5.2` | enabled | 23.3 | 2/2 | 2 | 2 | [grammar]冠词缺失→adding a resource pool；[grammar]不可数名词误用→How much storage |

### C-05

| 模型 | 思考 | 耗时(s) | 命中 | 识别错误数 | learnings | 错误列表 |
|------|------|--------|------|-----------|-----------|---------|
| `qwen3.7-flash` | disabled | 3.5 | 4/4 | 2 | 2 | [grammar]动词形式错误→to finish；[collocation]搭配冗余→that the airflow worker/scheduler lo |
| `qwen3.7-flash` | enabled | 33.7 | 4/4 | 3 | 2 | [grammar]动词形式错误→finish；[grammar]拼写错误→Airflow；[grammar]主谓不一致→logs are empty |
| `qwen3.7-plus` | disabled | 20.7 | 4/4 | 5 | 4 | [grammar]不定式误用→to finish；[grammar]介词冗余→this week；[grammar]拼写错误→Airflow；[grammar] |
| `qwen3.7-plus` | enabled | 85.8 | 4/4 | 5 | 4 | [grammar]不定式后动词形式错误→to finish；[collocation]搭配不当→this week；[grammar]拼写错误→Airflow； |
| `qwen3.8-max` | disabled | 8.5 | 4/4 | 3 | 3 | [grammar]不定式误用→to finish；[grammar]主谓不一致→logs are empty；[style]搭配冗余→the issue whe |
| `qwen3.8-max` | enabled | 360.4 | 0/4 | 0 | 0 | （无） |
| `deepseek-v4-flash-0731` | disabled | 4.0 | 4/4 | 2 | 2 | [grammar]动词形式错误→to finish；[grammar]主谓不一致→logs are empty |
| `deepseek-v4-flash-0731` | enabled | 57.3 | 4/4 | 5 | 5 | [grammar]不定式误用→to finish；[collocation]搭配不当→this week；[grammar]拼写错误→airflow；[gram |
| `deepseek-v4-pro` | disabled | 10.4 | 4/4 | 3 | 3 | [grammar]动词形式错误→to finish；[grammar]主谓不一致→logs are；[style]搭配冗余→issue that the air |
| `deepseek-v4-pro` | enabled | 33.2 | 4/4 | 4 | 4 | [grammar]不定式误用→to finish；[grammar]拼写错误→airflow；[grammar]主谓不一致→logs are；[style]搭配 |
| `glm-5.2` | disabled | 8.5 | 4/4 | 3 | 3 | [grammar]不定式错误→to finish；[collocation]搭配冗余→fix the issue that the `airflow` work |
| `glm-5.2` | enabled | 43.1 | 4/4 | 4 | 4 | [grammar]不定式错误→to finish；[grammar]拼写错误→airflow；[grammar]主谓不一致→logs are empty；[st |

### C-06

| 模型 | 思考 | 耗时(s) | 命中 | 识别错误数 | learnings | 错误列表 |
|------|------|--------|------|-----------|-----------|---------|
| `qwen3.7-flash` | disabled | 3.1 | 1/1 | 1 | 1 | [grammar]逗号拼接→Sorry for the late response. We are working on the release operati |
| `qwen3.7-flash` | enabled | 28.5 | 1/1 | 2 | 2 | [collocation]搭配冗余→the release；[grammar]逗号拼接→response. We are working on the rele |
| `qwen3.7-plus` | disabled | 12.9 | 1/1 | 2 | 2 | [style]语域错配→the release；[grammar]逗号拼接→...release. The restart function should wo |
| `qwen3.7-plus` | enabled | 75.6 | 1/1 | 3 | 3 | [chinglish]中式直译→the release；[chinglish]中式直译→please give it a try；[grammar]逗号粘连→r |
| `qwen3.8-max` | disabled | 6.9 | 1/1 | 2 | 2 | [grammar]逗号拼接→Sorry for the late response. We are working on the release operati |
| `qwen3.8-max` | enabled | 68.0 | 1/1 | 2 | 2 | [grammar]逗号拼接→Sorry for the late response. We are working on the release, and th |
| `deepseek-v4-flash-0731` | disabled | 1.3 | 0/1 | 0 | 0 | （无） |
| `deepseek-v4-flash-0731` | enabled | 4.3 | 0/1 | 0 | 0 | （无） |
| `deepseek-v4-pro` | disabled | 1.7 | 0/1 | 0 | 0 | （无） |
| `deepseek-v4-pro` | enabled | 5.6 | 0/1 | 0 | 0 | （无） |
| `glm-5.2` | disabled | 9.4 | 1/1 | 3 | 2 | [grammar]逗号连接独立子句→response. We are working；[grammar]逗号连接独立子句→now. Please check；[ |
| `glm-5.2` | enabled | 38.9 | 1/1 | 2 | 2 | [grammar]逗号拼接→Sorry for the late response. We are working on the release process |

### C-07

| 模型 | 思考 | 耗时(s) | 命中 | 识别错误数 | learnings | 错误列表 |
|------|------|--------|------|-----------|-----------|---------|
| `qwen3.7-flash` | disabled | 3.2 | 2/2 | 2 | 2 | [grammar]主谓不一致→logs have been fixed；[collocation]用词不当→quickly |
| `qwen3.7-flash` | enabled | 28.1 | 2/2 | 3 | 3 | [grammar]成分缺失→issue with the Airflow instance logs；[grammar]主谓不一致→has been；[styl |
| `qwen3.7-plus` | disabled | 15.7 | 2/2 | 2 | 2 | [grammar]主谓不一致→The issue with the airflow instance log has been fixed；[collocati |
| `qwen3.7-plus` | enabled | 66.0 | 2/2 | 2 | 2 | [grammar]主谓不一致→log has been；[collocation]名词堆砌→The issue with the Airflow instanc |
| `qwen3.8-max` | disabled | 7.9 | 2/2 | 3 | 2 | [grammar]主谓不一致→log has been fixed；[collocation]搭配冗余→create a new `airflow` insta |
| `qwen3.8-max` | enabled | 360.4 | 0/2 | 0 | 0 | （无） |
| `deepseek-v4-flash-0731` | disabled | 5.7 | 0/2 | 0 | 0 | （无） |
| `deepseek-v4-flash-0731` | enabled | 20.8 | 2/2 | 2 | 2 | [grammar]介词缺失→issue with the airflow instance log；[grammar]主谓不一致→has |
| `deepseek-v4-pro` | disabled | 11.3 | 2/2 | 3 | 3 | [grammar]主谓不一致→The issue with the airflow instance log has been fixed；[grammar]名 |
| `deepseek-v4-pro` | enabled | 36.3 | 2/2 | 2 | 2 | [grammar]主谓不一致→has been fixed；[grammar]介词缺失→issue with the airflow instance log |
| `glm-5.2` | disabled | 9.5 | 2/2 | 4 | 3 | [grammar]冠词缺失→the `airflow` instance log；[grammar]主谓不一致→log has been fixed；[gram |
| `glm-5.2` | enabled | 29.8 | 2/2 | 2 | 2 | [grammar]介词缺失→issue with the airflow instance log；[grammar]主谓不一致→has been fixed |

### C-08

| 模型 | 思考 | 耗时(s) | 命中 | 识别错误数 | learnings | 错误列表 |
|------|------|--------|------|-----------|-----------|---------|
| `qwen3.7-flash` | disabled | 8.6 | 2/2 | 2 | 2 | [grammar]逗号粘连→resolved now. I suspect；[collocation]搭配冗余→not urgent |
| `qwen3.7-flash` | enabled | 39.3 | 2/2 | 4 | 3 | [grammar]连词缺失→resolved now. I suspect；[collocation]词序不当→a missing column in the  |
| `qwen3.7-plus` | disabled | 16.4 | 2/2 | 3 | 2 | [grammar]逗号拼接→resolved now. I suspect；[collocation]搭配不当→a missing column in the  |
| `qwen3.7-plus` | enabled | 65.7 | 2/2 | 3 | 3 | [grammar]逗号拼接→resolved now. I suspect；[collocation]语序不当→the missing DB column；[s |
| `qwen3.8-max` | disabled | 9.5 | 2/2 | 3 | 3 | [grammar]逗号拼接→has been resolved. I suspect；[collocation]搭配不当→a missing DB column |
| `qwen3.8-max` | enabled | 360.4 | 0/2 | 0 | 0 | （无） |
| `deepseek-v4-flash-0731` | disabled | 5.6 | 0/2 | 0 | 0 | （无） |
| `deepseek-v4-flash-0731` | enabled | 13.5 | 2/2 | 3 | 3 | [collocation]用词不当→related to the missing column in the DB；[grammar]逗号拼接→is not u |
| `deepseek-v4-pro` | disabled | 10.2 | 2/2 | 2 | 2 | [grammar]冠词缺失→a DB missing column；[style]语域错配→I think this is also caused by |
| `deepseek-v4-pro` | enabled | 43.2 | 2/2 | 1 | 1 | [chinglish]中式直译→the missing column in the DB |
| `glm-5.2` | disabled | 11.4 | 2/2 | 3 | 3 | [grammar]逗号连接独立子句→None；[collocation]用词不当→None；[grammar]时态不一致→None |
| `glm-5.2` | enabled | 40.0 | 2/2 | 3 | 3 | [grammar]逗号拼接→has been resolved now. I suspect；[chinglish]中式直译→a missing column  |

### C-09

| 模型 | 思考 | 耗时(s) | 命中 | 识别错误数 | learnings | 错误列表 |
|------|------|--------|------|-----------|-----------|---------|
| `qwen3.7-flash` | disabled | 5.2 | 2/2 | 2 | 2 | [grammar]主谓不一致→there is an error log；[collocation]用词不当→triggering a DAG |
| `qwen3.7-flash` | enabled | 21.8 | 2/2 | 2 | 2 | [grammar]单复数不一致→some error logs；[grammar]冠词缺失→triggering the DAG |
| `qwen3.7-plus` | disabled | 11.3 | 2/2 | 2 | 2 | [grammar]主谓不一致→there are some error logs；[grammar]冠词缺失→triggering a DAG |
| `qwen3.7-plus` | enabled | 56.2 | 2/2 | 2 | 2 | [grammar]单复数错误→some error logs；[grammar]冠词缺失→triggering a DAG |
| `qwen3.8-max` | disabled | 6.1 | 2/2 | 2 | 2 | [grammar]主谓不一致→there are some error logs；[grammar]冠词缺失→triggering a DAG |
| `qwen3.8-max` | enabled | 98.3 | 2/2 | 3 | 3 | [style]搭配冗余→the running worker and scheduler pods；[grammar]单复数错误→any error logs； |
| `deepseek-v4-flash-0731` | disabled | 7.6 | 2/2 | 3 | 3 | [grammar]冠词缺失→the running worker pod and the scheduler pod；[grammar]主谓不一致→there  |
| `deepseek-v4-flash-0731` | enabled | 21.9 | 0/2 | 0 | 0 | （无） |
| `deepseek-v4-pro` | disabled | 9.2 | 2/2 | 2 | 2 | [grammar]主谓不一致→there is some error log；[grammar]冠词缺失→when triggering the dag |
| `deepseek-v4-pro` | enabled | 24.8 | 2/2 | 1 | 1 | [grammar]名词单复数错误→some error logs |
| `glm-5.2` | disabled | 7.3 | 2/2 | 3 | 3 | [grammar]单复数错误→some error logs；[grammar]冠词缺失→triggering a dag；[style]语域错配→BTW |
| `glm-5.2` | enabled | 25.9 | 2/2 | 2 | 2 | [grammar]单复数错误→there are some error logs；[grammar]冠词缺失→when triggering a DAG |

## 三、总结

- **最准**（命中率最高）：见 §一 排序，命中率越高识别 golden 错误越全。
- **最快**（平均耗时最低）：见 §一 平均/用例列。
- **综合建议**：结合命中率与耗时，选取纠错场景最均衡的模型/思考模式。
