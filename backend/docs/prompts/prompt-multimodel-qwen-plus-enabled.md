# 提示词输出采集报告（Prompt Output Report）

- **模型**：`qwen3.7-plus`
- **思考模式**：enabled（开启）
- **场景**：casual（日常/职场口语）
- **用例数**：9
- **总耗时**：506.0 秒

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

### C-01（耗时 51.1s）

**输入**：Correct the trigger_by field set up logic when creating job.

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "grammar",
        "error_type": "词性误用",
        "fragment": "set up",
        "explanation": "set up 是动词短语，此处作定语修饰 logic，应使用名词形式 setup。",
        "correction": "setup"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "creating job",
        "explanation": "job 是可数名词，单数形式前需加不定冠词 a，或改为复数 jobs。",
        "correction": "creating a job"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Correct the `trigger_by` field setup logic when creating a job.",
        "explanation": "仅修正词性和冠词错误，保留原句结构和语气。"
      },
      "natural": {
        "text": "Fix the setup logic for the `trigger_by` field when creating a job.",
        "explanation": "在工单或技术沟通中，用 Fix 替代 Correct 更口语化且自然，调整语序使表达更流畅。"
      }
    },
    "learnings": [
      {
        "title": "动词短语与名词形式的区别",
        "rule": "set up 是动词短语，表示“设置”的动作；setup 是名词，表示“设置、配置”。在修饰名词（如 logic, process）时，必须使用名词形式 setup。",
        "instances": [
          {
            "wrong": "set up logic",
            "right": "setup logic"
          }
        ],
        "examples": [
          {
            "wrong": "The set up process is slow.",
            "right": "The setup process is slow."
          }
        ]
      },
      {
        "title": "可数名词单数需加冠词",
        "rule": "job 是可数名词，在句中作单数使用时，前面必须加不定冠词 a，或者改为复数形式 jobs。",
        "instances": [
          {
            "wrong": "creating job",
            "right": "creating a job"
          }
        ],
        "examples": [
          {
            "wrong": "when creating task",
            "right": "when creating a task"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-02（耗时 16.9s）

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

### C-03（耗时 52.9s）

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
        "explanation": "GDSP cluster 是特指某个具体的集群，作为可数名词单数，前面需要加定冠词 the。",
        "correction": "of the GDSP cluster"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "In that case, the egress IP (出网ip) of the GDSP cluster should be enough, right?",
        "explanation": "仅补充缺失的定冠词，保留原句结构和中文注释。"
      },
      "natural": {
        "text": "In that case, the egress IP for the GDSP cluster should be enough, right?",
        "explanation": "去掉了中文注释以保持英文句子的纯粹，使用 for 替代 of 搭配 cluster 在技术语境中更自然。"
      }
    },
    "learnings": [
      {
        "title": "特指的可数名词单数需加定冠词",
        "rule": "当可数名词单数表示特指（如被专有名词修饰或上下文中明确指代）时，前面必须使用定冠词 the。",
        "instances": [
          {
            "wrong": "of GDSP cluster",
            "right": "of the GDSP cluster"
          }
        ],
        "examples": [
          {
            "wrong": "config of Redis cluster",
            "right": "config of the Redis cluster"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-04（耗时 35.6s）

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
        "fragment": "resource pool",
        "explanation": "resource pool 是可数名词单数，前面需要加不定冠词 a 或定冠词 the。",
        "correction": "a resource pool"
      },
      {
        "category": "grammar",
        "error_type": "不可数名词误用",
        "fragment": "How many storage",
        "explanation": "storage 是不可数名词，不能用 how many 修饰，应改为 how much。",
        "correction": "How much storage"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "This pvc should be created when adding a resource pool. How much storage do we want?",
        "explanation": "仅修正冠词和不可数名词修饰语，保留原句结构和语气。"
      },
      "natural": {
        "text": "This PVC should be created when adding a resource pool. How much storage do we need?",
        "explanation": "将 pvc 大写更规范，用 need 替换 want 在技术沟通中更自然，表示“需要多少存储空间”。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数需加冠词",
        "rule": "可数名词单数在句中不能单独使用，前面必须加冠词（如 a, an, the）或限定词，或者变为复数形式。",
        "instances": [
          {
            "wrong": "adding resource pool",
            "right": "adding a resource pool"
          }
        ],
        "examples": [
          {
            "wrong": "creating resource pool",
            "right": "creating a resource pool"
          }
        ]
      },
      {
        "title": "不可数名词的数量提问",
        "rule": "询问不可数名词的数量时，必须使用 how much 而不是 how many。",
        "instances": [
          {
            "wrong": "How many storage",
            "right": "How much storage"
          }
        ],
        "examples": [
          {
            "wrong": "How many memory",
            "right": "How much memory"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-05（耗时 85.8s）

**输入**：Is it possible to finished the testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it by this week? This would fix the issue that ariflow worker/scheduler logs is empty issue.

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "grammar",
        "error_type": "不定式后动词形式错误",
        "fragment": "to finished",
        "explanation": "to 作为不定式符号，其后必须接动词原形，不能使用过去式或过去分词。",
        "correction": "to finish"
      },
      {
        "category": "collocation",
        "error_type": "搭配不当",
        "fragment": "by this week",
        "explanation": "表示“在本周内”通常直接使用 this week，或使用 by the end of this week。by this week 搭配不自然。",
        "correction": "this week"
      },
      {
        "category": "grammar",
        "error_type": "拼写错误",
        "fragment": "ariflow",
        "explanation": "技术产品名拼写错误，且作为专有名词首字母应大写。",
        "correction": "Airflow"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "logs is",
        "explanation": "logs 是复数名词，其后的谓语动词应使用复数形式 are。",
        "correction": "logs are"
      },
      {
        "category": "collocation",
        "error_type": "搭配冗余",
        "fragment": "the issue that ... empty issue",
        "explanation": "the issue that 引导同位语从句解释 issue 的具体内容时，句末不需要再重复 issue，否则造成句式杂糅和语义重复。",
        "correction": "the issue that ... empty"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Is it possible to finish the testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it this week? This would fix the issue that Airflow worker/scheduler logs are empty.",
        "explanation": "仅修正语法、拼写和冗余，保留原句结构和语气。"
      },
      "natural": {
        "text": "Could we finish testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it this week? This should fix the issue with empty Airflow worker/scheduler logs.",
        "explanation": "使用 Could we 更委婉自然，用 the issue with empty ... 替代从句，更符合 Slack/IM 等日常技术沟通的简洁风格。"
      }
    },
    "learnings": [
      {
        "title": "不定式后接动词原形",
        "rule": "to 作为不定式符号时，其后必须接动词原形，不可使用过去式或过去分词形式。",
        "instances": [
          {
            "wrong": "to finished",
            "right": "to finish"
          }
        ],
        "examples": [
          {
            "wrong": "I want to went home.",
            "right": "I want to go home."
          }
        ]
      },
      {
        "title": "时间状语 this week 的搭配",
        "rule": "表示“在本周内”直接使用 this week 即可；若强调截止时间，应使用 by the end of this week，避免使用 by this week。",
        "instances": [
          {
            "wrong": "by this week",
            "right": "this week"
          }
        ],
        "examples": [
          {
            "wrong": "Can you finish it by this week?",
            "right": "Can you finish it this week?"
          }
        ]
      },
      {
        "title": "主谓一致与专有名词拼写",
        "rule": "复数名词作主语时，谓语动词需使用复数形式；技术产品名等专有名词需注意正确拼写及首字母大写。",
        "instances": [
          {
            "wrong": "ariflow worker/scheduler logs is",
            "right": "Airflow worker/scheduler logs are"
          }
        ],
        "examples": [
          {
            "wrong": "The kubernetes pods is running.",
            "right": "The Kubernetes pods are running."
          }
        ]
      },
      {
        "title": "同位语从句避免重复中心词",
        "rule": "当使用 the issue that / the fact that 等结构引导同位语从句时，从句结束后不可再重复中心名词，以免造成句式杂糅。",
        "instances": [
          {
            "wrong": "the issue that ... empty issue",
            "right": "the issue that ... empty"
          }
        ],
        "examples": [
          {
            "wrong": "This fixes the problem that the server is down problem.",
            "right": "This fixes the problem that the server is down."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-06（耗时 75.6s）

**输入**：Sorry for the late response, we are working on the release operation, the restart function should work now, please check.

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "chinglish",
        "error_type": "中式直译",
        "fragment": "release operation",
        "explanation": "“发布操作”直译为 release operation 不自然，英语中通常直接说 the release 或 the release process。",
        "correction": "the release"
      },
      {
        "category": "chinglish",
        "error_type": "中式直译",
        "fragment": "please check",
        "explanation": "“请检查”直译为 please check 缺少宾语且语气生硬。日常沟通中更习惯用 please give it a try 或 could you please check。",
        "correction": "please give it a try"
      },
      {
        "category": "grammar",
        "error_type": "逗号粘连",
        "fragment": "response, we are working on the release operation, the restart function should work now, please check.",
        "explanation": "多个独立完整的句子仅用逗号连接，构成逗号粘连。建议使用句号断句或添加连词。",
        "correction": "response. We are working on the release, and the restart function should work now. Please give it a try."
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Sorry for the late response. We are working on the release, and the restart function should work now. Please give it a try.",
        "explanation": "修正了逗号粘连和中式直译，保留原句结构和语气。"
      },
      "natural": {
        "text": "Sorry for the delay! We're working on the release now, so the restart function should be working. Please give it a try and let me know.",
        "explanation": "使用 delay 替代 late response 更简洁，增加 so 和 let me know 使语气更连贯、友好，符合 Slack 沟通风格。"
      }
    },
    "learnings": [
      {
        "title": "避免直译“操作”",
        "rule": "在技术语境中，中文的“发布操作”、“部署操作”通常不需要直译为 operation，直接使用 the release、the deployment 或 the release process 即可。",
        "instances": [
          {
            "wrong": "release operation",
            "right": "the release"
          }
        ],
        "examples": [
          {
            "wrong": "We are doing the deploy operation.",
            "right": "We are doing the deployment."
          }
        ]
      },
      {
        "title": "“请检查”的地道表达",
        "rule": "中文的“请检查”直译为 please check 在英语中显得生硬且缺少宾语。日常沟通中，建议加上宾语（如 check it）或使用更委婉自然的表达，如 please give it a try、could you please check 或 let me know if it works。",
        "instances": [
          {
            "wrong": "please check",
            "right": "please give it a try"
          }
        ],
        "examples": [
          {
            "wrong": "I fixed the bug, please check.",
            "right": "I fixed the bug, please give it a try."
          }
        ]
      },
      {
        "title": "避免逗号粘连",
        "rule": "英语中不能用逗号直接连接两个或多个独立的完整句子（即逗号粘连）。需要使用句号断句，或者使用连词（如 and, so, but）连接。",
        "instances": [
          {
            "wrong": "response, we are working",
            "right": "response. We are working"
          }
        ],
        "examples": [
          {
            "wrong": "The server is down, please restart it.",
            "right": "The server is down. Please restart it."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-07（耗时 66.0s）

**输入**：The issue airflow instance log have been fixed, could you please create a new airflow instance instead? The log viewer and download should be real quick.

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "log have been",
        "explanation": "主语 log 为单数名词，谓语动词应使用单数形式 has，而非复数形式 have。",
        "correction": "log has been"
      },
      {
        "category": "collocation",
        "error_type": "名词堆砌",
        "fragment": "The issue airflow instance log",
        "explanation": "多个名词直接堆砌导致修饰关系不清，issue 不能直接作定语修饰 log，需使用介词 with 连接或调整语序。",
        "correction": "The issue with the Airflow instance log"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The issue with the Airflow instance log has been fixed, could you please create a new Airflow instance instead? The log viewer and download should be real quick.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "The Airflow instance log issue is fixed. Could you spin up a new instance instead? The log viewer and download should be really quick.",
        "explanation": "将名词堆砌简化为 log issue，使用 spin up 替代 create 更符合技术语境，拆分句子使表达更清晰自然"
      }
    },
    "learnings": [
      {
        "title": "单数主语与谓语动词的一致性",
        "rule": "当主语是单数名词时，谓语动词必须使用单数形式（如 has 而非 have）。",
        "instances": [
          {
            "wrong": "log have been",
            "right": "log has been"
          }
        ],
        "examples": [
          {
            "wrong": "The issue have been fixed.",
            "right": "The issue has been fixed."
          }
        ]
      },
      {
        "title": "避免名词直接堆砌导致修饰不清",
        "rule": "多个名词直接连用会导致修饰关系不清。表达‘某物的问题’时，应使用介词 with 连接（the issue with the...），或将核心名词 issue 后置（the ... issue）。",
        "instances": [
          {
            "wrong": "The issue airflow instance log",
            "right": "The issue with the Airflow instance log"
          }
        ],
        "examples": [
          {
            "wrong": "The issue network timeout",
            "right": "The issue with the network timeout"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-08（耗时 65.7s）

**输入**：The empty log issue in PROD has been resolved now, I suspect this is also caused by the DB missing column. Then DSD-45874 is not urgent now, we can release both DSD-45874 & DSD-45252 next week.

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
        "fragment": "resolved now, I suspect",
        "explanation": "两个完整的独立句子不能仅用逗号连接，需使用句号、分号或添加连词。",
        "correction": "resolved now. I suspect"
      },
      {
        "category": "collocation",
        "error_type": "语序不当",
        "fragment": "the DB missing column",
        "explanation": "名词修饰语序不自然，英语中通常将分词（如 missing）放在名词前，或使用介词短语后置。",
        "correction": "the missing DB column"
      },
      {
        "category": "style",
        "error_type": "用词不当",
        "fragment": "Then",
        "explanation": "Then 通常表示时间顺序（然后），表示直接的因果关系（所以）在口语中更常用 So。",
        "correction": "So"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The empty log issue in PROD has been resolved now. I suspect this is also caused by the missing DB column. So DSD-45874 is not urgent now, and we can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "修正了逗号拼接、语序和连词，并补充了 and 以修复后半句的逗号拼接，保留了原句结构和语气。"
      },
      "natural": {
        "text": "The empty log issue in PROD is now resolved. I suspect it was also caused by a missing column in the DB. Since DSD-45874 is no longer urgent, we can release both DSD-45874 and DSD-45252 next week.",
        "explanation": "使用 is now resolved 更简洁，Since 引导原因状语从句使逻辑更连贯，no longer urgent 比 not urgent now 更地道。"
      }
    },
    "learnings": [
      {
        "title": "避免逗号拼接",
        "rule": "两个完整的独立句子不能仅用逗号连接，必须使用句号、分号，或添加并列连词（如 and, but, so）。",
        "instances": [
          {
            "wrong": "独立句子1, 独立句子2",
            "right": "独立句子1. 独立句子2 或 独立句子1, and 独立句子2"
          }
        ],
        "examples": [
          {
            "wrong": "The issue is resolved, I will close the ticket.",
            "right": "The issue is resolved. I will close the ticket."
          }
        ]
      },
      {
        "title": "名词修饰语序",
        "rule": "当使用分词或形容词修饰名词时，通常放在名词前面；如果是名词修饰名词，需注意逻辑关系，避免生硬堆砌。",
        "instances": [
          {
            "wrong": "the + 名词1 + 分词 + 名词2",
            "right": "the + 分词 + 名词1 + 名词2 或 the + 分词 + 名词2 + in + 名词1"
          }
        ],
        "examples": [
          {
            "wrong": "the DB missing column",
            "right": "the missing DB column"
          }
        ]
      },
      {
        "title": "因果连词的选择",
        "rule": "表示直接的因果关系（所以）时，口语中常用 So；Then 更多用于表示时间顺序（然后）或承接上文（那么）。",
        "instances": [
          {
            "wrong": "Then + 因果结果",
            "right": "So + 因果结果"
          }
        ],
        "examples": [
          {
            "wrong": "The server is down, then we need to restart it.",
            "right": "The server is down, so we need to restart it."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-09（耗时 56.2s）

**输入**：By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error log when triggering dag.

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "grammar",
        "error_type": "单复数错误",
        "fragment": "some error log",
        "explanation": "log 是可数名词，被 some 修饰时应使用复数形式 logs。在条件句中，使用 any 搭配复数名词更为自然。",
        "correction": "some error logs"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "triggering dag",
        "explanation": "dag (DAG) 是可数名词单数，前面需要加不定冠词 a 或定冠词 the，且技术缩写通常大写。",
        "correction": "triggering a DAG"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error logs when triggering a DAG.",
        "explanation": "仅修正名词复数和冠词缺失，保留原句结构和语气。"
      },
      "natural": {
        "text": "Btw, you can also easily check the running worker and scheduler pods. This is super helpful if you see any error logs when triggering a DAG.",
        "explanation": "使用 Btw、super helpful 和 see any error logs，更贴近 Slack 等即时通讯工具的日常技术沟通风格。"
      }
    },
    "learnings": [
      {
        "title": "some 修饰可数名词需用复数",
        "rule": "some 修饰可数名词时，名词必须使用复数形式；在条件句中，使用 any 搭配复数名词更为自然。",
        "instances": [
          {
            "wrong": "some error log",
            "right": "some error logs"
          }
        ],
        "examples": [
          {
            "wrong": "some error log",
            "right": "some error logs"
          }
        ]
      },
      {
        "title": "可数名词单数前需加冠词",
        "rule": "可数名词单数在句中泛指时，前面需要加不定冠词 a 或 an；特指时加 the。技术缩写如 DAG 也遵循此规则，且通常大写。",
        "instances": [
          {
            "wrong": "triggering dag",
            "right": "triggering a DAG"
          }
        ],
        "examples": [
          {
            "wrong": "triggering dag",
            "right": "triggering a DAG"
          }
        ]
      }
    ]
  },
  "reply": null
}
```
