# 提示词输出采集报告（Prompt Output Report）

- **模型**：`qwen3.8-max`
- **思考模式**：enabled（开启）
- **场景**：casual（日常/职场口语）
- **用例数**：9
- **总耗时**：1428.4 秒

## 一、测试提示词（SYSTEM_PROMPT）

```text
你是英文纠错教练，面向日常/职场口语场景（如 Slack/IM 工单对话、技术沟通）。
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
    "rule": "规则完整说明（中文）",
    "instances": [{"wrong": "错误写法（英文）", "right": "正确写法（英文）"}],
    "examples": [{"wrong": "错误写法（英文）", "right": "正确写法（英文）"}]}]}

## 错误类型标签（为 error_type 字段提供精确分类）

| 情形 | 标签 | 示例 |
|---|---|---|
| 表达在英语中不存在或不自然 | 中式直译 | `open the light`, `play computer` |
| 表达是合法英语但语域与当前语境不符 | 语域错配 | Slack 消息中使用 `for your reference`（正式邮件中可使用） |
| 词汇选择或词性使用不当 | 用词不当 | `do some customize`（应为 customization） |
| 标准语法错误（时态、冠词、一致性等） | 使用标准语法术语 | 时态错误, 冠词缺失, 主谓不一致 |

对"语域错配"，根据输入文本推断当前语境的正式程度（如含 @mention、缩写多为 Slack/IM；含 Dear、Regards 多为邮件）。对应 learning 的 rule 中必须注明该表达在何种场景下是合适的（如"正式邮件中可使用"）。不得将语域错配标记为"中式直译"。

## 术语规范
- 命名错误类型或陈述规则时，必须使用完整中文语法术语：名词 / 动词 / 形容词 / 副词 / 介词 / 主语 / 谓语 / 宾语 / 时态 / 单数 / 复数 / 不可数 / 主动 / 被动 / 不定式 / 动名词 / 关系从句 / 冠词 等。
- **禁止**在模式、公式或规则陈述中使用字母缩写如 N、V、Adj、Adv、NP、VP、S、O。
  - 错误示例：❌ there are + N + V
  - 正确示例：✅ there are + 名词 + 动词

## 保留领域术语、缩写与行业惯用写法
以下情况一律视为有意为之的术语或格式，**不得**列为修正项：
- 全大写短语（如 TO BE、AS IS、TODO、FIXME）
- 冒号引导的标签式表达（如 "As it:" "TO BE:" "Status:" "Note:" 后接描述）
- 不定式作后置定语（如 "validation to refuse" "rule to apply"）等价于 that 从句时
- 技术产品名、版本号、工单链接（如 `trigger_by`、`airflow`、`DSD-45874`、`pvc`、Jira 链接）必须原样保留，展示时用反引号包裹

遇到无法确定作者意图的表达，不列为修正项，不得臆测改写。若两种写法母语者在某些语境下都会使用（如 "cannot" 与 "can not"），视为等价表达，不列为修正项。

## 关键约束
- `natural` 改写应提供比 `minimal` 更自然/地道的整句表达；natural 改写偏口语化（Slack/IM 风格，可用缩写、简短句）。若 `minimal` 已经足够自然（如修正后已是唯一地道说法），则允许 `natural` 与 `minimal` 相同，无需强行制造差异。
- - 口语/即时消息场景中常见的省略表达（如省略主语/助动词的疑问句 `getting an error?`、`Hitting the same issue?`、`Seeing any logs?`）属于该场景的正常表达，**不列为修正项**，不判为语法错误。
- 任何改写版本均不得保留被标记为错误的表达 — 若某项被标记为错误，所有改写版本（含 minimal）都必须替换。
- 不改变时态意图、语气强度或归责对象。
- 区分"中式直译"与"语域错配"：若表达是合法英语但不符合当前语境的正式程度，error_type 标记为"语域错配"而非"中式直译"；对应 learning 的 rule 必须注明适用场景。
- category 与 error_type 一致：冠词缺失/时态错误/主谓不一致/不可数名词误用 → grammar；中式直译 → chinglish；语域错配 → style；其余用词/搭配问题 → collocation 或 style。
- 无法确定作者意图的表达不列为修正项，不臆测改写。
- 无错误 → has_errors=false，errors 与 learnings 为空，minimal 与 natural 两版 text 均为空字符串、explanation 为空字符串。
- 每个不同规则归纳一条 learning；同类错误的多个实例合并到同一条 learning 的 instances 数组。
- learnings 的 examples 为对象数组，每项含 wrong 与 right 两版：{"wrong": "错误写法（英文）", "right": "正确写法（英文）"}。
- error_type、explanation、title、rule 用中文；fragment、correction、instances 的 wrong/right、examples 的 wrong/right、rewrite 的 text 保持英文。

## 示例

### 示例 1：多种错误类型 + 合并学习项

**输入**：`there are some rules need to follow before you start the deploy, as below`

**输出**：
{"intent":"correction","correction":{"has_errors":true,"errors":[{"category":"grammar","error_type":"关系从句缺失","fragment":"rules need to follow","explanation":"名词 rules 后直接跟动词 need 不合法，需用关系从句或不定式连接。","correction":"rules that need to be followed"},{"category":"grammar","error_type":"动词误作名词","fragment":"the deploy","explanation":"deploy 是动词，作名词应使用 deployment。","correction":"the deployment"},{"category":"style","error_type":"语域错配","fragment":"as below","explanation":"as below 在正式列举中不标准，正式文档应使用 as follows；口语中可用 as shown below。","correction":"as follows"}],"rewrite":{"minimal":{"text":"There are some rules that need to be followed before you start the deployment, as follows.","explanation":"仅修正语法和用词，保留原句结构和语气"},"natural":{"text":"Before you deploy, there are a few rules to go through, like below.","explanation":"用 go through 更口语化，like below 适合 Slack 日常沟通。"}},"learnings":[{"title":"名词后修饰动作需连接词","rule":"名词后修饰动作必须通过关系从句或不定式连接，不能直接并列。","instances":[{"wrong":"there are + 名词 + 动词","right":"there are + 名词 + that/which + 动词 或 to + 动词"}],"examples":[{"wrong":"There are some files need to update.","right":"There are some files that need to be updated."}]},{"title":"动词的名词形式","rule":"deploy 是动词，表示“部署”的名词形式是 deployment，不可直接用原形。","instances":[{"wrong":"the deploy","right":"the deployment"}],"examples":[{"wrong":"the deploy","right":"the deployment"}]},{"title":"列举引导词","rule":"列举多项内容时正式场合用 as follows，口语中可用 as shown below / like below；避免使用 as below。","instances":[{"wrong":"as below","right":"as follows"}],"examples":[{"wrong":"The steps are as below.","right":"The steps are as follows."}]}]}}

### 示例 2：同类错误合并为一条 learning

**输入**：`the resouce quota is created automaticaly, and the configration is not applyed yet`

**输出**：
{"intent":"correction","correction":{"has_errors":true,"errors":[{"category":"grammar","error_type":"拼写错误","fragment":"resouce","explanation":"resource 拼写错误，漏写 r。","correction":"resource"},{"category":"grammar","error_type":"拼写错误","fragment":"automaticaly","explanation":"automatically 拼写错误，漏写 l。","correction":"automatically"},{"category":"grammar","error_type":"拼写错误","fragment":"configration","explanation":"configuration 拼写错误，漏写 u。","correction":"configuration"},{"category":"grammar","error_type":"时态错误","fragment":"is not applyed","explanation":"表示“尚未应用”应用现在完成时被动语态，且 apply 过去分词为 applied。","correction":"has not been applied"}],"rewrite":{"minimal":{"text":"The resource quota is created automatically, and the configuration has not been applied yet.","explanation":"仅修正语法和用词，保留原句结构和语气"},"natural":{"text":"The resource quota gets created automatically, and the config hasn't been applied yet.","explanation":"用 gets created 和 config 缩写，更贴近日常技术聊天。"}},"learnings":[{"title":"常见拼写错误","rule":"技术文档中常见拼写错误，注意元音和双写字母。","instances":[{"wrong":"resouce","right":"resource"},{"wrong":"automaticaly","right":"automatically"},{"wrong":"configration","right":"configuration"}],"examples":[{"wrong":"resouce","right":"resource"},{"wrong":"automaticaly","right":"automatically"}]},{"title":"现在完成时表尚未","rule":"表示“尚未完成”应用现在完成时的被动语态 has/have not been + 过去分词。","instances":[{"wrong":"is not applyed","right":"has not been applied"}],"examples":[{"wrong":"The change is not applyed.","right":"The change has not been applied."}]}]}}

## 返回格式（严格遵守字段名）
{"intent": "correction", "correction": {"has_errors": ..., "errors": [...], "rewrite": {"minimal": {...}, "natural": {...}}, "learnings": [...]}, "reply": null}

```

## 二、测试用例与实际输出

### C-01（耗时 79.7s）

**输入**：Correct the trigger_by field set up logic when creating job.

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "collocation",
        "error_type": "用词不当",
        "fragment": "`trigger_by` field set up logic",
        "explanation": "set up 是动词短语，不能直接放在名词 logic 前作名词性修饰语；这里应使用名词 setup，或改为 for setting up 结构。",
        "correction": "`trigger_by` field setup logic"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "when creating job",
        "explanation": "job 是可数名词单数，不能单独出现；泛指创建一个任务时需要加不定冠词 a。",
        "correction": "when creating a job"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Correct the `trigger_by` field setup logic when creating a job.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Fix the logic for setting up the `trigger_by` field when creating a job.",
        "explanation": "用 Fix 和 for setting up 结构更符合工单/IM 中的口语化技术表达。"
      }
    },
    "learnings": [
      {
        "title": "动词短语与名词形式区分",
        "rule": "set up 是动词短语；表示“设置/配置”这一概念作名词或修饰名词时用 setup，也可改用介词 for 加动名词 setting up 的结构。",
        "instances": [
          {
            "wrong": "field set up logic",
            "right": "field setup logic"
          }
        ],
        "examples": [
          {
            "wrong": "Update the field set up logic.",
            "right": "Update the field setup logic."
          }
        ]
      },
      {
        "title": "可数名词单数需要限定词",
        "rule": "可数名词单数不能单独出现，需要冠词、指示代词或物主代词等限定词；泛指某一个事物时用不定冠词 a 或 an。",
        "instances": [
          {
            "wrong": "when creating job",
            "right": "when creating a job"
          }
        ],
        "examples": [
          {
            "wrong": "Error happens when creating job.",
            "right": "Error happens when creating a job."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-02（耗时 11.6s）

**输入**：What do you mean you can't restart this webapp? getting an error?

**说明**：口语省略疑问句 getting an error? 在 casual（日常/职场口语）场景下属正常表达，不判错；formal（正式书面）场景下应补全为 Are you getting an error?。

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": false,
    "errors": [],
    "rewrite": {
      "minimal": {
        "text": "",
        "explanation": ""
      },
      "natural": {
        "text": "",
        "explanation": ""
      }
    },
    "learnings": []
  },
  "reply": null
}
```

### C-03（耗时 43.6s）

**输入**：In that case, the egress IP(出网ip) of GDSP cluster should be enough, right?

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "of GDSP cluster",
        "explanation": "cluster 是可数名词单数，此处特指某个 GDSP 集群，需要加定冠词 the。",
        "correction": "of the GDSP cluster"
      },
      {
        "category": "style",
        "error_type": "中英混排",
        "fragment": "egress IP(出网ip)",
        "explanation": "英文技术沟通中不宜夹带中文注释；egress IP 本身已可表达该含义。",
        "correction": "egress IP"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "In that case, the egress IP of the GDSP cluster should be enough, right?",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "In that case, the GDSP cluster's egress IP should be enough, right?",
        "explanation": "用所有格形式更口语、更自然，适合 Slack/IM 技术沟通。"
      }
    },
    "learnings": [
      {
        "title": "单数可数名词需要限定词",
        "rule": "单数可数名词通常不能单独出现，需要冠词、物主代词、指示代词等限定词；特指已知事物时用定冠词 the。",
        "instances": [
          {
            "wrong": "of GDSP cluster",
            "right": "of the GDSP cluster"
          }
        ],
        "examples": [
          {
            "wrong": "GDSP cluster is ready.",
            "right": "The GDSP cluster is ready."
          }
        ]
      },
      {
        "title": "英文表达中避免中英混排",
        "rule": "面向英文读者或在英文技术沟通中，应避免在英文术语后夹带中文注释；如需解释，应使用英文表达。",
        "instances": [
          {
            "wrong": "egress IP(出网ip)",
            "right": "egress IP"
          }
        ],
        "examples": [
          {
            "wrong": "egress IP(出网ip)",
            "right": "egress IP"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-04（耗时 46.1s）

**输入**：This pvc should be created when adding resource pool. How many storage do we want?

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "adding resource pool",
        "explanation": "resource pool 是可数名词单数，前面需要冠词或限定词；这里表示添加一个资源池，用 a resource pool。",
        "correction": "adding a resource pool"
      },
      {
        "category": "grammar",
        "error_type": "不可数名词误用",
        "fragment": "How many storage",
        "explanation": "storage 是不可数名词，询问数量应使用 how much，不能使用 how many。",
        "correction": "How much storage"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "This `pvc` should be created when adding a resource pool. How much storage do we want?",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "This `pvc` should be created when we add a resource pool. How much storage do we want?",
        "explanation": "补充主语 we，使 when 引导的时间状语更口语、更清晰；整体适合 Slack/IM 技术沟通。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数前需要冠词或限定词",
        "rule": "可数名词单数不能单独出现，前面通常需要冠词 a/an/the 或 this/that/my 等限定词；表示泛指某一类中的一个用 a/an。",
        "instances": [
          {
            "wrong": "adding resource pool",
            "right": "adding a resource pool"
          }
        ],
        "examples": [
          {
            "wrong": "We need to create user.",
            "right": "We need to create a user."
          }
        ]
      },
      {
        "title": "不可数名词用 how much 提问数量",
        "rule": "storage 这类不可数名词不能用 how many 提问数量，应使用 how much；how many 后接可数名词复数。",
        "instances": [
          {
            "wrong": "How many storage",
            "right": "How much storage"
          }
        ],
        "examples": [
          {
            "wrong": "How many memory is needed?",
            "right": "How much memory is needed?"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-05（耗时 360.4s）

**输入**：Is it possible to finished the testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it by this week? This would fix the issue that ariflow worker/scheduler logs is empty issue.

**输出**：（采集失败）LLM 调用失败: ReadTimeout: 

### C-06（耗时 68.0s）

**输入**：Sorry for the late response, we are working on the release operation, the restart function should work now, please check.

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "grammar",
        "error_type": "逗号拼接",
        "fragment": "Sorry for the late response, we are working on the release operation, the restart function should work now, please check.",
        "explanation": "多个独立分句不能只用逗号连接，应拆成句子，或使用连词、分号。",
        "correction": "Sorry for the late response. We are working on the release, and the restart function should work now. Please check."
      },
      {
        "category": "chinglish",
        "error_type": "中式直译",
        "fragment": "release operation",
        "explanation": "“发布操作”直译成 release operation 不自然，技术沟通中通常直接说 release，或根据语境说 release process / deployment。",
        "correction": "release"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Sorry for the late response. We are working on the release, and the restart function should work now. Please check.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Sorry for the delay. We're working on the release, and the restart function should be working now. Could you check?",
        "explanation": "用 Sorry for the delay、We're 和 Could you check 更贴近 Slack/IM 口语，语气更自然礼貌。"
      }
    },
    "learnings": [
      {
        "title": "避免逗号拼接",
        "rule": "英语中多个独立分句不能只用逗号连接，应使用句号、分号或连词。",
        "instances": [
          {
            "wrong": "Sorry for the late response, we are working on the release operation, the restart function should work now, please check.",
            "right": "Sorry for the late response. We are working on the release, and the restart function should work now. Please check."
          }
        ],
        "examples": [
          {
            "wrong": "The config is updated, please check.",
            "right": "The config is updated. Please check."
          }
        ]
      },
      {
        "title": "避免中式直译",
        "rule": "中文“发布操作”在英语技术沟通中通常不直译为 release operation，可直接使用 release，或根据语境使用 release process、deployment。",
        "instances": [
          {
            "wrong": "release operation",
            "right": "release"
          }
        ],
        "examples": [
          {
            "wrong": "We are working on the release operation.",
            "right": "We are working on the release."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-07（耗时 360.4s）

**输入**：The issue airflow instance log have been fixed, could you please create a new airflow instance instead? The log viewer and download should be real quick.

**输出**：（采集失败）LLM 调用失败: ReadTimeout: 

### C-08（耗时 360.4s）

**输入**：The empty log issue in PROD has been resolved now, I suspect this is also caused by the DB missing column. Then DSD-45874 is not urgent now, we can release both DSD-45874 & DSD-45252 next week.

**输出**：（采集失败）LLM 调用失败: ReadTimeout: 

### C-09（耗时 98.3s）

**输入**：By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error log when triggering dag.

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "style",
        "error_type": "搭配冗余",
        "fragment": "the running worker pod and scheduler pod",
        "explanation": "worker pod 和 scheduler pod 重复了同一个中心名词 pod，可合并为并列结构，用复数 pods 更简洁自然。",
        "correction": "the running worker and scheduler pods"
      },
      {
        "category": "grammar",
        "error_type": "单复数错误",
        "fragment": "some error log",
        "explanation": "there are 后应接复数名词；此处表示不确定是否存在错误日志，条件句中用 any 比 some 更自然。",
        "correction": "any error logs"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "when triggering dag",
        "explanation": "可数名词单数 dag 前缺少冠词或限定词；技术缩写通常写作 `DAG`。",
        "correction": "when triggering a `DAG`"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "By the way, you could also check the running worker and scheduler pods more easily. This would be helpful if there are any error logs when triggering a `DAG`.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "By the way, it’s also easier to check the running worker and scheduler pods. That would help if there are any error logs when triggering a `DAG`.",
        "explanation": "用 it’s easier to check 替代 could also check ... more easily，更口语直接；That would help 比 This would be helpful 更贴近 Slack/IM 风格。"
      }
    },
    "learnings": [
      {
        "title": "并列同类名词可共享复数中心词",
        "rule": "当多个并列成分共享同一个中心名词时，可将中心名词放在最后并使用复数，避免重复。适用于 Slack/IM 技术沟通。",
        "instances": [
          {
            "wrong": "worker pod and scheduler pod",
            "right": "worker and scheduler pods"
          }
        ],
        "examples": [
          {
            "wrong": "Check the worker pod and scheduler pod.",
            "right": "Check the worker and scheduler pods."
          }
        ]
      },
      {
        "title": "there are 后接复数名词",
        "rule": "表示存在多个事物时用 there are + 复数名词；some 修饰可数名词复数，条件句中通常用 any 表示不确定是否存在。",
        "instances": [
          {
            "wrong": "some error log",
            "right": "any error logs"
          }
        ],
        "examples": [
          {
            "wrong": "if there are some error log",
            "right": "if there are any error logs"
          }
        ]
      },
      {
        "title": "可数名词单数需要冠词",
        "rule": "可数名词单数不能单独出现，需要冠词、限定词或变为复数；技术缩写 `DAG` 通常大写。",
        "instances": [
          {
            "wrong": "triggering dag",
            "right": "triggering a `DAG`"
          }
        ],
        "examples": [
          {
            "wrong": "when triggering dag",
            "right": "when triggering a `DAG`"
          }
        ]
      }
    ]
  },
  "reply": null
}
```
