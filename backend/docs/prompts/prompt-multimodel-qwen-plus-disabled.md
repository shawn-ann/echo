# 提示词输出采集报告（Prompt Output Report）

- **模型**：`qwen3.7-plus`
- **思考模式**：disabled（关闭）
- **场景**：casual（日常/职场口语）
- **用例数**：9
- **总耗时**：115.8 秒

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

### C-01（耗时 12.8s）

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
        "error_type": "冠词缺失",
        "fragment": "creating job",
        "explanation": "job 是可数名词，单数形式前需加冠词 a 或 the，此处泛指创建任务的过程，建议用 a job。",
        "correction": "creating a job"
      },
      {
        "category": "style",
        "error_type": "语域错配",
        "fragment": "Correct the trigger_by field set up logic",
        "explanation": "在 Slack/IM 等即时通讯场景中，'Correct' 作为祈使句开头显得过于正式和生硬，类似工单标题而非对话。日常沟通中常用 'Fix'、'Update' 或直接说明问题。此外 'set up' 作定语修饰 logic 时通常连写为 'setup' 或用 'configuration'。",
        "correction": "Fix the trigger_by field setup logic"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Correct the trigger_by field setup logic when creating a job.",
        "explanation": "仅修正冠词缺失和合成词拼写，保留原句结构。"
      },
      "natural": {
        "text": "Fix the trigger_by setup logic for job creation.",
        "explanation": "用 Fix 替代 Correct 更符合技术沟通习惯，for job creation 比 when creating a job 更简洁地道。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数需加冠词",
        "rule": "可数名词单数形式不能单独使用，需根据语境添加不定冠词 a/an 或定冠词 the。",
        "instances": [
          {
            "wrong": "creating job",
            "right": "creating a job"
          }
        ],
        "examples": [
          {
            "wrong": "I am writing code.",
            "right": "I am writing a piece of code."
          },
          {
            "wrong": "Create user account.",
            "right": "Create a user account."
          }
        ]
      },
      {
        "title": "技术沟通中的动词选择",
        "rule": "在即时通讯或非正式技术讨论中，Fix/Update 比 Correct 更自然；Correct 多用于正式文档或纠错场景。",
        "instances": [
          {
            "wrong": "Correct the bug",
            "right": "Fix the bug"
          }
        ],
        "examples": [
          {
            "wrong": "Please correct this error.",
            "right": "Please fix this error."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-02（耗时 2.6s）

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

### C-03（耗时 11.4s）

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
        "explanation": "cluster 是可数名词，特指某个集群时需加定冠词 the。",
        "correction": "of the GDSP cluster"
      },
      {
        "category": "style",
        "error_type": "语域错配",
        "fragment": "(出网ip)",
        "explanation": "在英文技术沟通中夹杂中文注释显得不专业且破坏阅读流畅性，建议直接使用英文术语或移除。",
        "correction": ""
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "In that case, the egress IP of the GDSP cluster should be enough, right?",
        "explanation": "补全冠词并移除中文注释，保留原句结构。"
      },
      "natural": {
        "text": "So the GDSP cluster's egress IP should be sufficient, right?",
        "explanation": "用 So 开头更自然连接上下文，sufficient 比 enough 在技术语境下稍显正式但依然得体，所有格形式更简洁。"
      }
    },
    "learnings": [
      {
        "title": "特指单数可数名词需加冠词",
        "rule": "当名词为单数可数名词且特指某事物时，必须使用定冠词 the。",
        "instances": [
          {
            "wrong": "of GDSP cluster",
            "right": "of the GDSP cluster"
          }
        ],
        "examples": [
          {
            "wrong": "Check status of server.",
            "right": "Check the status of the server."
          }
        ]
      },
      {
        "title": "避免中英混杂",
        "rule": "在英文工作沟通中，应避免在句子中插入中文解释，除非对方明确不懂该英文术语。通常直接使用标准英文术语即可。",
        "instances": [
          {
            "wrong": "egress IP(出网ip)",
            "right": "egress IP"
          }
        ],
        "examples": [
          {
            "wrong": "Please check the log(日志).",
            "right": "Please check the log."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-04（耗时 12.1s）

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
        "explanation": "resource pool 是可数名词单数，在此处泛指或特指某操作时，需加冠词 a 或 the。结合语境通常指“添加资源池”这一动作涉及的对象，建议用 the 表示特指当前讨论的资源池，或 a 表示泛指。",
        "correction": "adding the resource pool"
      },
      {
        "category": "grammar",
        "error_type": "不可数名词误用",
        "fragment": "How many storage",
        "explanation": "storage（存储容量）是不可数名词，不能用 How many 修饰，应用 How much。",
        "correction": "How much storage"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "This PVC should be created when adding the resource pool. How much storage do we want?",
        "explanation": "仅修正冠词和疑问词搭配错误，保留原句结构。"
      },
      "natural": {
        "text": "This PVC gets created when we add the resource pool. How much storage do we need?",
        "explanation": "用 gets created 更口语化；将 want 改为 need 更符合技术需求讨论的语境；补充主语 we 使句子更完整自然。"
      }
    },
    "learnings": [
      {
        "title": "不可数名词的提问方式",
        "rule": "storage、information、advice 等不可数名词，提问数量时用 How much，不能用 How many。",
        "instances": [
          {
            "wrong": "How many storage",
            "right": "How much storage"
          }
        ],
        "examples": [
          {
            "wrong": "How many information do you have?",
            "right": "How much information do you have?"
          }
        ]
      },
      {
        "title": "可数名词单数需加冠词",
        "rule": "在介词后接可数名词单数时，必须加冠词 a/an 或 the，不能裸奔。",
        "instances": [
          {
            "wrong": "adding resource pool",
            "right": "adding the resource pool"
          }
        ],
        "examples": [
          {
            "wrong": "after creating ticket",
            "right": "after creating the ticket"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-05（耗时 20.7s）

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
        "error_type": "不定式误用",
        "fragment": "to finished",
        "explanation": "to 后接动词原形构成不定式，finished 是过去式或过去分词，应改为 finish。",
        "correction": "to finish"
      },
      {
        "category": "grammar",
        "error_type": "介词冗余",
        "fragment": "by this week",
        "explanation": "this week 前通常不加介词 by，直接说 this week 即可表示“在本周内”。若强调截止期限可用 by the end of this week。",
        "correction": "this week"
      },
      {
        "category": "grammar",
        "error_type": "拼写错误",
        "fragment": "ariflow",
        "explanation": "Airflow 是专有名词，拼写错误且首字母通常大写。",
        "correction": "Airflow"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "logs is empty",
        "explanation": "主语 logs 是复数，谓语动词应用 are 而非 is。",
        "correction": "logs are empty"
      },
      {
        "category": "style",
        "error_type": "搭配冗余",
        "fragment": "the issue that ... issue",
        "explanation": "句尾重复使用 issue，造成语义冗余和结构累赘。",
        "correction": "the issue where ..."
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Is it possible to finish the testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it this week? This would fix the issue that Airflow worker/scheduler logs are empty.",
        "explanation": "仅修正语法、拼写和冗余表达，保留原句结构。"
      },
      "natural": {
        "text": "Can we finish testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it this week? That should fix the empty Airflow worker/scheduler logs issue.",
        "explanation": "用 Can we 更直接自然；将从句简化为名词短语 empty ... logs issue，更符合技术沟通习惯。"
      }
    },
    "learnings": [
      {
        "title": "不定式后接动词原形",
        "rule": "to 作为不定式符号时，后面必须跟动词原形，不能跟过去式或过去分词。",
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
        "title": "时间状语 this week 前不加介词",
        "rule": "当 this/next/last 与 week/month/year 等连用时，前面通常不加介词 in/on/by。若需表达截止含义，建议使用 by the end of this week。",
        "instances": [
          {
            "wrong": "by this week",
            "right": "this week"
          }
        ],
        "examples": [
          {
            "wrong": "I will finish it by next Monday.",
            "right": "I will finish it next Monday. (或 by next Monday)"
          }
        ]
      },
      {
        "title": "复数主语配复数谓语",
        "rule": "主语为复数名词时，be 动词应用 are，而非 is。",
        "instances": [
          {
            "wrong": "logs is empty",
            "right": "logs are empty"
          }
        ],
        "examples": [
          {
            "wrong": "The files is missing.",
            "right": "The files are missing."
          }
        ]
      },
      {
        "title": "避免同义词重复冗余",
        "rule": "在定语从句或同位语中，避免头尾重复使用相同的名词（如 issue ... issue），可改用 where 引导的从句或将其转化为前置定语。",
        "instances": [
          {
            "wrong": "the issue that ... issue",
            "right": "the issue where ... / the ... issue"
          }
        ],
        "examples": [
          {
            "wrong": "It solves the problem that the server crash problem.",
            "right": "It solves the server crash problem."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-06（耗时 12.9s）

**输入**：Sorry for the late response, we are working on the release operation, the restart function should work now, please check.

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "style",
        "error_type": "语域错配",
        "fragment": "release operation",
        "explanation": "operation 在此处显得过于正式和宏大，通常指大型军事或医疗行动。在软件发布语境下，直接说 release 或 deployment 更自然。",
        "correction": "the release"
      },
      {
        "category": "grammar",
        "error_type": "逗号拼接",
        "fragment": "...operation, the restart function should work now, please check.",
        "explanation": "多个独立子句仅用逗号连接，造成句子结构松散（Run-on sentence）。建议拆分为独立句子或使用连词。",
        "correction": "...release. The restart function should work now; please check."
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Sorry for the late response. We are working on the release. The restart function should work now; please check.",
        "explanation": "修正了逗号拼接错误，并将 release operation 简化为 release，保留原意。"
      },
      "natural": {
        "text": "Sorry for the delay! We've been working on the release. The restart function should be working now—please give it a try.",
        "explanation": "使用 'Sorry for the delay' 更地道；'give it a try' 比 'please check' 在即时通讯中更亲切自然；用破折号连接最后部分，语气更流畅。"
      }
    },
    "learnings": [
      {
        "title": "软件发布用语简化",
        "rule": "在技术沟通中，'release' 本身即可指代发布过程或版本，无需添加 'operation'。'Deployment' 也是常用词，但 'release operation' 属于冗余且过于正式的搭配。",
        "instances": [
          {
            "wrong": "working on the release operation",
            "right": "working on the release"
          }
        ],
        "examples": [
          {
            "wrong": "The release operation is complete.",
            "right": "The release is complete."
          }
        ]
      },
      {
        "title": "避免逗号拼接长句",
        "rule": "英语中两个完整的独立句子不能仅用逗号连接。在 Slack/IM 等非正式场合，可以使用句号、分号或破折号来分隔不同的意思单元，使表达更清晰。",
        "instances": [
          {
            "wrong": "We fixed the bug, please test it.",
            "right": "We fixed the bug. Please test it."
          }
        ],
        "examples": [
          {
            "wrong": "I updated the code, it should work now.",
            "right": "I updated the code; it should work now."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-07（耗时 15.7s）

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
        "fragment": "The issue airflow instance log have been fixed",
        "explanation": "主语核心词是单数名词 issue（或 log），谓语动词应用单数 has，而非复数 have。此外，issue 与 log 之间缺乏介词连接，导致名词堆砌。",
        "correction": "The issue with the airflow instance log has been fixed"
      },
      {
        "category": "collocation",
        "error_type": "用词不当",
        "fragment": "real quick",
        "explanation": "quick 是形容词，修饰动词 should be (implied action) 或作为表语时，口语中常用 fast 或 quickly。虽然 real quick 在极随意口语中常见，但在技术沟通中建议用 faster 或 much faster 来表达“快很多/很快”。此处语境暗示新实例会比旧的好，用 faster 更准确；若仅指速度快，用 fast 即可。考虑到上下文是对比修复后的效果，通常隐含“会比之前快”，故推荐 faster。若仅陈述事实，fast 亦可。这里修正为更标准的 fast 或 faster。",
        "correction": "fast"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The issue with the airflow instance log has been fixed. Could you please create a new airflow instance instead? The log viewer and download should be fast.",
        "explanation": "修正主谓一致和名词修饰关系，将 real quick 改为 fast。"
      },
      "natural": {
        "text": "The airflow instance log issue is fixed. Can you spin up a new instance? The log viewer and downloads should be much faster now.",
        "explanation": "使用 spin up 替代 create 更符合技术语境；用 much faster 强调修复后的改进效果，比单纯说 fast 更自然且符合语境逻辑。"
      }
    },
    "learnings": [
      {
        "title": "主谓一致与名词修饰",
        "rule": "当主语包含多个名词时，需确定核心主语的单复数以决定谓语动词形式。名词修饰名词时，若关系不紧密，建议加介词（如 with）澄清关系。",
        "instances": [
          {
            "wrong": "The issue ... log have been fixed",
            "right": "The issue with the ... log has been fixed"
          }
        ],
        "examples": [
          {
            "wrong": "The server error logs have been cleared.",
            "right": "The server error logs have been cleared."
          },
          {
            "wrong": "The issue database connection have been resolved.",
            "right": "The issue with the database connection has been resolved."
          }
        ]
      },
      {
        "title": "描述速度的副词/形容词选择",
        "rule": "在技术沟通中，描述系统响应速度时，常用 fast (形容词) 或 quickly (副词)。Real quick 过于口语化且语法上不严谨（应用 really quickly）。若强调对比改进，用 faster。",
        "instances": [
          {
            "wrong": "It should be real quick.",
            "right": "It should be fast."
          }
        ],
        "examples": [
          {
            "wrong": "The query runs real quick.",
            "right": "The query runs very quickly."
          },
          {
            "wrong": "Response time is real quick.",
            "right": "Response time is fast."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-08（耗时 16.4s）

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
        "explanation": "两个完整的独立子句之间不能仅用逗号连接，需使用句号、分号或连词。",
        "correction": "resolved now. I suspect"
      },
      {
        "category": "collocation",
        "error_type": "搭配不当",
        "fragment": "DB missing column",
        "explanation": "“DB missing column”表达略显生硬，通常说“a missing column in the DB”或“the DB is missing a column”。此处作为原因状语，建议改为名词短语结构。",
        "correction": "a missing column in the DB"
      },
      {
        "category": "grammar",
        "error_type": "逗号拼接",
        "fragment": "urgent now, we can",
        "explanation": "同样是两个独立子句直接用逗号连接，属于逗号拼接错误。",
        "correction": "urgent now, so we can"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The empty log issue in PROD has been resolved now. I suspect this was also caused by a missing column in the DB. Then DSD-45874 is not urgent now, so we can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "修正了标点符号错误和名词短语搭配，保留了原句的逻辑连接词和语气。"
      },
      "natural": {
        "text": "The empty log issue in PROD is fixed. I suspect it was due to a missing column in the DB. Since DSD-45874 isn't urgent anymore, let's release both DSD-45874 & DSD-45252 next week.",
        "explanation": "使用更简洁的 'is fixed' 和 'due to'，将 'Then... so...' 结构优化为 'Since..., let's...'，更符合 Slack/IM 的自然沟通风格。"
      }
    },
    "learnings": [
      {
        "title": "避免逗号拼接",
        "rule": "英语中两个完整的独立句子（主谓结构完整）不能仅用逗号连接。应使用句号分开，或使用连词（如 and, but, so）连接。",
        "instances": [
          {
            "wrong": "Issue resolved, I think it's fixed.",
            "right": "Issue resolved. I think it's fixed."
          },
          {
            "wrong": "It's not urgent, we can wait.",
            "right": "It's not urgent, so we can wait."
          }
        ],
        "examples": [
          {
            "wrong": "The bug is fixed, we can deploy.",
            "right": "The bug is fixed. We can deploy."
          }
        ]
      },
      {
        "title": "描述缺失组件的表达",
        "rule": "描述数据库或系统中缺少某列/字段时，常用 'a missing column in the DB' 或 'the DB is missing a column'，避免直接使用 'DB missing column' 这种名词堆砌。",
        "instances": [
          {
            "wrong": "caused by DB missing column",
            "right": "caused by a missing column in the DB"
          }
        ],
        "examples": [
          {
            "wrong": "Error due to table missing index.",
            "right": "Error due to a missing index in the table."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-09（耗时 11.3s）

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
        "error_type": "主谓不一致",
        "fragment": "there are some error log",
        "explanation": "some 修饰可数名词复数，log 应为 logs；或者将 are 改为 is 并去掉 some。通常日志不止一条，建议用复数。",
        "correction": "there are some error logs"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "triggering dag",
        "explanation": "dag 是可数名词单数，泛指时需加冠词 a 或 the，或改为复数 dags。此处特指触发某个 DAG 的动作，建议加 the 或 a。",
        "correction": "triggering a DAG"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error logs when triggering a DAG.",
        "explanation": "仅修正语法错误（复数和冠词），保留原句结构。"
      },
      "natural": {
        "text": "BTW, it's easier to check the running worker and scheduler pods. This helps if you see any error logs when triggering a DAG.",
        "explanation": "Slack/IM 场景中，用 BTW 替代 By the way，用 it's easier to... 替代 you could... more easily 更直接自然；see any error logs 比 there are some error logs 更符合口语习惯。"
      }
    },
    "learnings": [
      {
        "title": "some 后接可数名词复数",
        "rule": "some 修饰可数名词时，名词必须用复数形式。",
        "instances": [
          {
            "wrong": "some error log",
            "right": "some error logs"
          }
        ],
        "examples": [
          {
            "wrong": "I have some question.",
            "right": "I have some questions."
          }
        ]
      },
      {
        "title": "可数名词单数需加冠词",
        "rule": "单数可数名词在句中不能裸奔，需根据语境加不定冠词 a/an 或定冠词 the。",
        "instances": [
          {
            "wrong": "triggering dag",
            "right": "triggering a DAG"
          }
        ],
        "examples": [
          {
            "wrong": "run job",
            "right": "run a job"
          }
        ]
      }
    ]
  },
  "reply": null
}
```
