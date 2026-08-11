# 提示词输出采集报告（Prompt Output Report）

- **模型**：`glm-5.2`
- **思考模式**：disabled（关闭）
- **场景**：casual（日常/职场口语）
- **用例数**：9
- **总耗时**：64.4 秒

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
- **括号内的中文/翻译注释不属于待纠错内容**：fragment 不得包含注释，注释前的英文术语按其本来的语法地位处理，不得因注释存在而臆测改动
- **术语与专有缩写的冠词**：当术语/缩写已带限定词（定冠词、指代词、所有格等）或作为固定技术表达使用时，不得因"缩写元音音素"或"可数名词单数"而新增/改动冠词；仅当术语**裸用且确需限定**时才补冠词。是否加冠词以母语者的实际用法为准，不确定时不臆测

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
- 每个不同规则归纳一条 learning；同类错误的多个实例合并到同一条 learning 的 instances 数组；learning 负责详细讲解该类错误（含适用场景、例句）。
- **errors 与 learnings 的关系**：errors 必须列出**每一个**具体错误（含片段与最小修正）；learnings 是对 errors 的归纳总结，同类错误合并为一条 learning 用于详细讲解。learnings **不得涉及 errors 中未列出的错误**——每条 learning 所讲的规则，其错误实例必须已出现在 errors 中。
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

### C-01（耗时 6.7s）

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
        "explanation": "job 是可数名词单数，泛指时需加不定冠词 a。",
        "correction": "creating a job"
      },
      {
        "category": "grammar",
        "error_type": "介词缺失",
        "fragment": "Correct the trigger_by field",
        "explanation": "表示“修正某字段中的逻辑”时，field 后需加介词 in 或 for 来连接逻辑。",
        "correction": "Correct the trigger_by field in"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Correct the trigger_by field setup logic when creating a job.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Fix the trigger_by field setup logic when creating a job.",
        "explanation": "用 Fix 替代 Correct 更简洁，符合 Slack/IM 场景的口语化风格。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数需冠词",
        "rule": "可数名词单数泛指时必须加冠词（a/an/the），不能裸用。",
        "instances": [
          {
            "wrong": "creating job",
            "right": "creating a job"
          }
        ],
        "examples": [
          {
            "wrong": "when starting task",
            "right": "when starting a task"
          }
        ]
      },
      {
        "title": "名词间需介词连接",
        "rule": "表示“某字段的逻辑”时，名词 field 与名词 logic 之间需用介词 in 或 for 连接，不能直接并列。",
        "instances": [
          {
            "wrong": "field setup logic",
            "right": "field setup logic in"
          }
        ],
        "examples": [
          {
            "wrong": "the config value",
            "right": "the value in the config"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-02（耗时 1.8s）

**输入**：What do you mean you can't restart this webapp? getting an error?

**说明**：口语省略疑问句 getting an error? 在 casual（日常/职场口语）场景下属正常表达，不判错；formal（正式书面）场景下应补全为 Are you getting an error?。

**输出**：

```json
{
  "intent": "follow_up",
  "correction": null,
  "reply": "这句话在 Slack/IM 场景下非常地道、自然，没有语法或用词问题。你省略主语/助动词的问句（getting an error?）也是口语中完全正常的表达，不需要修改。"
}
```

### C-03（耗时 5.3s）

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
        "fragment": "GDSP cluster",
        "explanation": "GDSP cluster 是可数名词单数，此处特指前文提到的集群，需补充定冠词 the。",
        "correction": "the GDSP cluster"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "In that case, the egress IP of the GDSP cluster should be enough, right?",
        "explanation": "仅补充缺失的定冠词，保留原句结构和语气"
      },
      "natural": {
        "text": "In that case, the GDSP cluster's egress IP should be enough, right?",
        "explanation": "使用名词所有格 's 替代 of 结构，使句子更紧凑，更符合 Slack/IM 中的口语沟通习惯"
      }
    },
    "learnings": [
      {
        "title": "特指可数名词需加定冠词",
        "rule": "可数名词单数不能裸用。当指代特定对象（如前文提及的集群、服务）时，需补充定冠词 the。",
        "instances": [
          {
            "wrong": "GDSP cluster",
            "right": "the GDSP cluster"
          }
        ],
        "examples": [
          {
            "wrong": "Egress IP of kubernetes cluster",
            "right": "The egress IP of the kubernetes cluster"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-04（耗时 6.1s）

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
        "fragment": "when adding resource pool",
        "explanation": "可数名词 resource pool 单数前需加不定冠词 a。",
        "correction": "when adding a resource pool"
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
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "This pvc should be created when adding a resource pool. How much storage do we need?",
        "explanation": "用 need 替代 want，在技术讨论中更自然。"
      }
    },
    "learnings": [
      {
        "title": "可数名词需加冠词",
        "rule": "可数名词单数形式前必须有冠词或限定词。",
        "instances": [
          {
            "wrong": "when adding resource pool",
            "right": "when adding a resource pool"
          }
        ],
        "examples": [
          {
            "wrong": "when adding resource pool",
            "right": "when adding a resource pool"
          }
        ]
      },
      {
        "title": "不可数名词用 how much",
        "rule": "不可数名词前用 how much 提问，how many 仅用于可数名词复数。",
        "instances": [
          {
            "wrong": "How many storage",
            "right": "How much storage"
          }
        ],
        "examples": [
          {
            "wrong": "How many storage",
            "right": "How much storage"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-05（耗时 9.4s）

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
        "error_type": "不定式错误",
        "fragment": "to finished",
        "explanation": "不定式符号 to 后应接动词原形，不能用过去式。",
        "correction": "to finish"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "logs is",
        "explanation": "名词 logs 为复数，谓语动词应使用复数形式 are。",
        "correction": "logs are"
      },
      {
        "category": "collocation",
        "error_type": "搭配冗余",
        "fragment": "fix the issue that ... logs is empty issue",
        "explanation": "前面已有 the issue that 引导，句末再接 issue 属于语义重复。",
        "correction": "fix the issue that ... logs are empty"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Is it possible to finish the testing for `https://jira.rakuten-it.com/jira/browse/DSD-45874` and release it by this week? This would fix the issue that `airflow` worker/scheduler logs are empty.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Can we finish testing for `https://jira.rakuten-it.com/jira/browse/DSD-45874` and release it this week? This would fix the empty `airflow` worker/scheduler logs issue.",
        "explanation": "用 Can we 更口语化，this week 更简洁，empty logs issue 更紧凑。"
      }
    },
    "learnings": [
      {
        "title": "不定式符号 to 后接动词原形",
        "rule": "不定式结构 to + 动词原形，不能使用过去式或过去分词。",
        "instances": [
          {
            "wrong": "to finished",
            "right": "to finish"
          }
        ],
        "examples": [
          {
            "wrong": "I want to started the process.",
            "right": "I want to start the process."
          }
        ]
      },
      {
        "title": "主谓一致：复数名词配复数谓语",
        "rule": "复数名词作主语时，谓语动词须用复数形式。",
        "instances": [
          {
            "wrong": "logs is",
            "right": "logs are"
          }
        ],
        "examples": [
          {
            "wrong": "The logs is missing.",
            "right": "The logs are missing."
          }
        ]
      },
      {
        "title": "避免 the issue that...issue 的语义重复",
        "rule": "使用 the issue that... 描述具体问题时，句末不应再重复 issue，否则造成语义冗余。",
        "instances": [
          {
            "wrong": "fix the issue that ... is empty issue",
            "right": "fix the issue that ... is empty"
          }
        ],
        "examples": [
          {
            "wrong": "This solves the issue that the config is missing issue.",
            "right": "This solves the issue that the config is missing."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-06（耗时 8.6s）

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
        "error_type": "逗号连接独立子句",
        "fragment": "response, we",
        "explanation": "两个独立子句之间不能仅用逗号连接，应使用句号、分号或连词。",
        "correction": "response. We"
      },
      {
        "category": "grammar",
        "error_type": "逗号连接独立子句",
        "fragment": "operation, the",
        "explanation": "两个独立子句之间不能仅用逗号连接，应使用句号、分号或连词。",
        "correction": "operation. The"
      },
      {
        "category": "collocation",
        "error_type": "搭配冗余",
        "fragment": "release operation",
        "explanation": "release 本身已包含发布操作的含义，加 operation 属语义冗余，直接用 release 即可。",
        "correction": "release"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Sorry for the late response. We are working on the release. The restart function should work now, please check.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Sorry for the delay! We're working on the release, and the restart function should work now. Could you check?",
        "explanation": "用 Sorry for the delay 更口语化，添加连词使句子更连贯，Could you check 更符合即时消息沟通的礼貌语气。"
      }
    },
    "learnings": [
      {
        "title": "逗号不能连接独立子句",
        "rule": "两个独立子句（即各含主语和谓语的完整句）之间不能仅用逗号连接，应使用句号、分号或并列连词（如 and、but、so）。",
        "instances": [
          {
            "wrong": "response, we",
            "right": "response. We"
          },
          {
            "wrong": "operation, the",
            "right": "operation. The"
          }
        ],
        "examples": [
          {
            "wrong": "I finished the task, it was hard.",
            "right": "I finished the task. It was hard."
          }
        ]
      },
      {
        "title": "避免名词搭配冗余",
        "rule": "release 本身已表示“发布”这一动作或事件，搭配 operation 属语义冗余，直接使用 release 即可。",
        "instances": [
          {
            "wrong": "release operation",
            "right": "release"
          }
        ],
        "examples": [
          {
            "wrong": "start the deploy operation",
            "right": "start the deployment"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-07（耗时 8.3s）

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
        "error_type": "冠词缺失",
        "fragment": "airflow instance log",
        "explanation": "此处指代特定的 Airflow 实例日志，名词前需补充定冠词 the。",
        "correction": "the Airflow instance log"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "log have been fixed",
        "explanation": "主语 log 为单数名词，助动词应使用单数形式 has。",
        "correction": "log has been fixed"
      },
      {
        "category": "collocation",
        "error_type": "用词不当",
        "fragment": "real quick",
        "explanation": "real quick 偏非正式口语，职场沟通中建议使用 really fast 或 much faster 更显专业。",
        "correction": "really fast"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The issue with the Airflow instance log has been fixed. Could you please create a new Airflow instance instead? The log viewer and download should be really fast.",
        "explanation": "仅修正冠词、主谓一致和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "The Airflow instance log issue has been fixed—could you create a new Airflow instance instead? Log viewing and downloading should be much faster now.",
        "explanation": "用 log issue 简化表达，破折号连接更符合 Slack 风格，much faster 更自然。"
      }
    },
    "learnings": [
      {
        "title": "单数名词需搭配单数助动词",
        "rule": "主语为单数名词时，助动词 have 需改为单数形式 has。",
        "instances": [
          {
            "wrong": "log have been fixed",
            "right": "log has been fixed"
          }
        ],
        "examples": [
          {
            "wrong": "The bug have been resolved.",
            "right": "The bug has been resolved."
          }
        ]
      },
      {
        "title": "特指名词需加定冠词",
        "rule": "指代特定事物时，名词前需补充定冠词 the。",
        "instances": [
          {
            "wrong": "airflow instance log",
            "right": "the Airflow instance log"
          }
        ],
        "examples": [
          {
            "wrong": "server is down",
            "right": "the server is down"
          }
        ]
      },
      {
        "title": "避免偏非正式的修饰搭配",
        "rule": "real quick 偏非正式口语，职场沟通中建议使用 really fast 或 much faster。",
        "instances": [
          {
            "wrong": "real quick",
            "right": "really fast"
          }
        ],
        "examples": [
          {
            "wrong": "It should be real quick.",
            "right": "It should be really fast."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-08（耗时 10.8s）

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
        "error_type": "逗号拼接错误",
        "fragment": "has been resolved now, I suspect",
        "explanation": "两个独立完整句之间仅用逗号连接构成了逗号拼接错误，应使用句号、分号或并列连词连接。",
        "correction": "has been resolved now. I suspect"
      },
      {
        "category": "collocation",
        "error_type": "搭配冗余",
        "fragment": "the DB missing column",
        "explanation": "DB 与 missing column 之间直接堆叠名词修饰语不够自然，且 missing 作定语时通常前置，应改为 the missing DB column。",
        "correction": "the missing DB column"
      },
      {
        "category": "grammar",
        "error_type": "时态错误",
        "fragment": "Then DSD-45874 is not urgent now",
        "explanation": "描述状态因前述事件而发生的改变，应使用现在时态的对应表达或现在完成时，原句直接用 is not urgent now 略显生硬，可改为 is no longer urgent。",
        "correction": "Then DSD-45874 is no longer urgent"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The empty log issue in PROD has been resolved now. I suspect this is also caused by the missing DB column. Then DSD-45874 is no longer urgent, and we can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "The empty log issue in PROD is resolved now. I suspect it's also caused by the missing DB column, so DSD-45874 isn't urgent anymore—we can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "用 it's 和 isn't 缩写更符合 Slack/IM 风格，用 so 和破折号连接因果与后续动作，更口语化。"
      }
    },
    "learnings": [
      {
        "title": "逗号不能连接两个独立完整句",
        "rule": "两个独立完整句之间不能仅用逗号连接，应使用句号、分号或并列连词（如 and/so/but）。",
        "instances": [
          {
            "wrong": "has been resolved now, I suspect",
            "right": "has been resolved now. I suspect"
          }
        ],
        "examples": [
          {
            "wrong": "The deploy is done, we can go home.",
            "right": "The deploy is done. We can go home."
          }
        ]
      },
      {
        "title": "名词修饰语的词序",
        "rule": "当多个名词或形容词修饰一个中心名词时，形容词通常前置，名词修饰语紧跟其后，避免直接堆叠造成歧义。",
        "instances": [
          {
            "wrong": "the DB missing column",
            "right": "the missing DB column"
          }
        ],
        "examples": [
          {
            "wrong": "the server new config",
            "right": "the new server config"
          }
        ]
      },
      {
        "title": "状态改变的表达",
        "rule": "描述某事物因前述事件而不再处于某种状态时，用 no longer 或 not ... anymore 比直接加 now 更自然。",
        "instances": [
          {
            "wrong": "is not urgent now",
            "right": "is no longer urgent"
          }
        ],
        "examples": [
          {
            "wrong": "This ticket is not urgent now.",
            "right": "This ticket is no longer urgent."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-09（耗时 7.4s）

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
        "error_type": "数不一致",
        "fragment": "there are some error log",
        "explanation": "名词 log 在此处为可数名词，some error log 中名词应用复数形式，与助动词 are 保持一致。",
        "correction": "there are some error logs"
      },
      {
        "category": "collocation",
        "error_type": "冠词缺失",
        "fragment": "triggering dag",
        "explanation": "dag 作为可数名词单数，在此处表示特定任务，前面需要加不定冠词 a。",
        "correction": "triggering a dag"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error logs when triggering a dag.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "By the way, it might be easier to check the running worker and scheduler pods. This would help if you see any error logs when triggering a dag.",
        "explanation": "用 it might be easier to 更符合口语建议语气，pods 用复数更自然，if you see 更口语化。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单复数一致",
        "rule": "there are 后接可数名词时，名词必须用复数形式。",
        "instances": [
          {
            "wrong": "there are some error log",
            "right": "there are some error logs"
          }
        ],
        "examples": [
          {
            "wrong": "there are some error log",
            "right": "there are some error logs"
          }
        ]
      },
      {
        "title": "可数名词单数需加冠词",
        "rule": "可数名词单数不能裸用，前面需要加冠词（如 a/an）或限定词。",
        "instances": [
          {
            "wrong": "triggering dag",
            "right": "triggering a dag"
          }
        ],
        "examples": [
          {
            "wrong": "triggering dag",
            "right": "triggering a dag"
          }
        ]
      }
    ]
  },
  "reply": null
}
```
