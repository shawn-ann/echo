# 提示词输出采集报告（Prompt Output Report）

- **模型**：`deepseek-v4-flash`
- **场景**：casual（日常/职场口语）
- **用例数**：9
- **总耗时**：403.0 秒

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

### C-01（耗时 43.8s）

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
        "error_type": "动词短语误作名词修饰语",
        "fragment": "field set up logic",
        "explanation": "在名词短语中修饰 logic 时，应使用名词形式的 setup（一个词），而不是动词短语 set up；动词短语不能直接放在名词前作定语。",
        "correction": "field setup logic"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "creating job",
        "explanation": "job 是可数名词单数，前面需要冠词 a 或 the。这里泛指创建任务，应使用不定冠词 a。",
        "correction": "creating a job"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Correct the `trigger_by` field setup logic when creating a job.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Fix the way the `trigger_by` field is set up when creating a job.",
        "explanation": "用 fix the way ... is set up 更口语化，表达更自然，贴近日常技术沟通。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数前需要冠词",
        "rule": "当名词是可数名词单数时，前面必须加不定冠词 a/an 或定冠词 the，不能裸用。",
        "instances": [
          {
            "wrong": "creating job",
            "right": "creating a job"
          }
        ],
        "examples": [
          {
            "wrong": "when creating job",
            "right": "when creating a job"
          },
          {
            "wrong": "I need to check status.",
            "right": "I need to check the status."
          }
        ]
      },
      {
        "title": "setup 是名词/形容词，set up 是动词短语",
        "rule": "表示“设置、安装”的名词或形容词形式是一个词 setup；动词短语是 set up（两个词）。作名词修饰语（如 setup logic）时应用 setup。",
        "instances": [
          {
            "wrong": "field set up logic",
            "right": "field setup logic"
          }
        ],
        "examples": [
          {
            "wrong": "the set up instructions",
            "right": "the setup instructions"
          },
          {
            "wrong": "follow the set up process",
            "right": "follow the setup process"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-02（耗时 6.4s）

**输入**：What do you mean you can't restart this webapp? getting an error?

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

### C-03（耗时 39.5s）

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
        "explanation": "GDSP 集群在本对话中是明确特指的对象，其前应加定冠词 the。",
        "correction": "the GDSP cluster"
      },
      {
        "category": "style",
        "error_type": "中英文混杂",
        "fragment": "IP(出网ip)",
        "explanation": "英文消息中插入中文注释不符合英文沟通习惯，应直接删除，必要时可在消息外单独解释。",
        "correction": "IP"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "In that case, the egress IP of the GDSP cluster should be enough, right?",
        "explanation": "仅补上冠词并删除中文注释，保留原句结构和语气"
      },
      "natural": {
        "text": "In that case, the GDSP cluster's egress IP should be enough, right?",
        "explanation": "用名词所有格 the GDSP cluster's 替代 of 结构，表达更紧凑，也更贴近日常技术聊天的口吻。"
      }
    },
    "learnings": [
      {
        "title": "特指对象前需加定冠词",
        "rule": "当名词所指对象在上下文中已明确特指时，需在其前使用定冠词 the，例如 the GDSP cluster。",
        "instances": [
          {
            "wrong": "the egress IP of GDSP cluster",
            "right": "the egress IP of the GDSP cluster"
          }
        ],
        "examples": [
          {
            "wrong": "the egress IP of GDSP cluster",
            "right": "the egress IP of the GDSP cluster"
          }
        ]
      },
      {
        "title": "英文消息中避免夹带中文",
        "rule": "在英文沟通中不应混入中文注释；如需说明术语含义，应使用英文解释或单独沟通，避免破坏可读性。",
        "instances": [
          {
            "wrong": "egress IP(出网ip)",
            "right": "egress IP"
          }
        ],
        "examples": [
          {
            "wrong": "the egress IP(出网ip) of GDSP cluster",
            "right": "the egress IP of the GDSP cluster"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-04（耗时 52.7s）

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
        "explanation": "resource pool 是可数名词单数，在泛指时前面缺少冠词，应使用 a resource pool。",
        "correction": "adding a resource pool"
      },
      {
        "category": "grammar",
        "error_type": "不可数名词误用",
        "fragment": "How many storage",
        "explanation": "storage 是不可数名词，表示数量时应用 how much 而不是 how many。",
        "correction": "How much storage"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "This `pvc` should be created when adding a resource pool. How much storage do we want?",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "We should create this `pvc` when we add a resource pool. How much storage do we want?",
        "explanation": "把被动语态改为主动语态并补充 when 从句的主语，更符合日常技术聊天习惯，表达更直接自然。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数前需加冠词",
        "rule": "可数名词单数在泛指时通常需要冠词 a/an，特指时用 the，不能裸用（除少数固定搭配）。",
        "instances": [
          {
            "wrong": "adding resource pool",
            "right": "adding a resource pool"
          }
        ],
        "examples": [
          {
            "wrong": "Create the PVC when adding resource pool.",
            "right": "Create the PVC when adding a resource pool."
          }
        ]
      },
      {
        "title": "不可数名词用 much 修饰",
        "rule": "storage 是不可数名词，表示数量时用 how much / much，不能用 how many / many；many 只修饰可数名词复数。",
        "instances": [
          {
            "wrong": "How many storage",
            "right": "How much storage"
          }
        ],
        "examples": [
          {
            "wrong": "How many storage do we want?",
            "right": "How much storage do we want?"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-05（耗时 105.3s）

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
        "explanation": "possible to 后面的 to 是不定式标志，动词应使用原形，finished 应改为 finish。",
        "correction": "to finish"
      },
      {
        "category": "collocation",
        "error_type": "介词搭配不当",
        "fragment": "by this week",
        "explanation": "by 一般后接具体时间点（如 Friday、the end of this week），与 this week 搭配不自然；若表示“本周内”可用 within this week 或 by the end of this week。",
        "correction": "by the end of this week"
      },
      {
        "category": "grammar",
        "error_type": "拼写错误",
        "fragment": "ariflow",
        "explanation": "Airflow 拼写错误，r 与 i 位置颠倒。",
        "correction": "airflow"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "logs is",
        "explanation": "主语 logs 是复数，be 动词应为 are，不能用 is。",
        "correction": "logs are"
      },
      {
        "category": "style",
        "error_type": "搭配冗余",
        "fragment": "empty issue",
        "explanation": "前文 the issue that 已引出问题，句末再写 issue 造成重复，应删除。",
        "correction": "empty"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Is it possible to finish the testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it by the end of this week? This would fix the issue that airflow worker/scheduler logs are empty.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Can we wrap up the testing for DSD-45874 and release it by the end of this week? That would fix the empty Airflow worker/scheduler logs.",
        "explanation": "用 Can we 替代 Is it possible to，更口语化；并将 the issue that logs are empty 改为 the empty ... logs，避免冗长。"
      }
    },
    "learnings": [
      {
        "title": "to 后接动词原形",
        "rule": "在 possible to、need to、want to 等结构中，to 为不定式标志，后接动词原形，不随主语或时态改为过去式或过去分词。",
        "instances": [
          {
            "wrong": "to finished",
            "right": "to finish"
          }
        ],
        "examples": [
          {
            "wrong": "It's possible to finished the task.",
            "right": "It's possible to finish the task."
          },
          {
            "wrong": "We need to confirmed the release.",
            "right": "We need to confirm the release."
          }
        ]
      },
      {
        "title": "表示“截止本周末”用 by the end of",
        "rule": "介词 by 后需接一个具体时间点（如 Friday、noon、the end of the week），表示“本周内”应用 within this week 或 by the end of this week；by this week 不自然。",
        "instances": [
          {
            "wrong": "by this week",
            "right": "by the end of this week"
          }
        ],
        "examples": [
          {
            "wrong": "Please finish by this week.",
            "right": "Please finish by the end of this week."
          },
          {
            "wrong": "I can send it by this week.",
            "right": "I can send it within this week."
          }
        ]
      },
      {
        "title": "Airflow 的拼写",
        "rule": "Airflow 是 Apache 工作流平台的专有名词，字母顺序是 a-i-r-f-l-o-w，不要写成 ariflow。",
        "instances": [
          {
            "wrong": "ariflow",
            "right": "airflow"
          }
        ],
        "examples": [
          {
            "wrong": "ariflow",
            "right": "airflow"
          }
        ]
      },
      {
        "title": "复数主语搭配复数谓语",
        "rule": "主语是复数名词（如 logs）时，be 动词用 are，不能用 is；主谓需要一致。",
        "instances": [
          {
            "wrong": "logs is",
            "right": "logs are"
          }
        ],
        "examples": [
          {
            "wrong": "The logs is empty.",
            "right": "The logs are empty."
          },
          {
            "wrong": "The workers is busy.",
            "right": "The workers are busy."
          }
        ]
      },
      {
        "title": "避免 issue 重复",
        "rule": "用 the issue that ... 引出问题时，从句内部不要再重复 issue，否则句子冗余；直接描述问题内容即可。",
        "instances": [
          {
            "wrong": "the issue that logs are empty issue",
            "right": "the issue that logs are empty"
          }
        ],
        "examples": [
          {
            "wrong": "This fixes the issue that the logs are empty issue.",
            "right": "This fixes the issue that the logs are empty."
          },
          {
            "wrong": "We have the problem that the disk is full problem.",
            "right": "We have the problem that the disk is full."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-06（耗时 33.4s）

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
        "fragment": "the release operation",
        "explanation": "“发布操作”直译为 release operation 不自然。英语中表示“正在处理发版相关事宜”通常直接说 working on the release 或 the release process；operation 常用在军事、医疗、救援等“行动”语境，用在软件发布上显得生硬。",
        "correction": "the release"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Sorry for the late response, we are working on the release, the restart function should work now, please check.",
        "explanation": "仅将 release operation 改为地道的 the release，保留原句结构和语气"
      },
      "natural": {
        "text": "Sorry for the late reply — we're working on the release, so the restart should work now. Can you check again?",
        "explanation": "用 we're 缩写、破折号连接因果并拆成短句，can you check again 更口语，整体更贴近 Slack/IM 的沟通风格。"
      }
    },
    "learnings": [
      {
        "title": "发版相关事宜的地道表达",
        "rule": "表示“正在处理发布/发版相关的事”时，英语习惯直接说 working on the release 或 the release process，不宜直译为 release operation；operation 在英文中多指军事、医疗、救援等“行动”，用在软件发布语境中不自然。",
        "instances": [
          {
            "wrong": "the release operation",
            "right": "the release"
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

### C-07（耗时 34.7s）

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
        "error_type": "介词缺失",
        "fragment": "The issue airflow instance log",
        "explanation": "名词 issue 后需要介词 with 引出具体对象，不能直接与对象名词并列；也可以把对象前置组成 the airflow instance log issue。",
        "correction": "The issue with the airflow instance log"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "have been fixed",
        "explanation": "主语 The issue 是单数，现在完成时的助动词应用 has，不能用 have。",
        "correction": "has been fixed"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The issue with the `airflow` instance log has been fixed, could you please create a new `airflow` instance instead? The log viewer and download should be real quick.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "The issue with the `airflow` instance log is fixed now — could you create a new `airflow` instance instead? Viewing and downloading the logs should be pretty quick.",
        "explanation": "用 is fixed now 更口语化，viewing and downloading the logs 更直接表达功能，pretty quick 比 real quick 在技术聊天中更自然。"
      }
    },
    "learnings": [
      {
        "title": "issue 后需介词 with 或组成名词短语",
        "rule": "表达“某对象的问题”时，英语用 the issue with + 对象，或将对象前置组成 the + 对象 + issue，不能把 issue 和对象直接并列。",
        "instances": [
          {
            "wrong": "The issue airflow instance log",
            "right": "The issue with the airflow instance log"
          }
        ],
        "examples": [
          {
            "wrong": "The issue the deployment has been fixed.",
            "right": "The issue with the deployment has been fixed."
          }
        ]
      },
      {
        "title": "主语单数时谓语用 has",
        "rule": "主语是单数名词（如 the issue）时，现在完成时助动词用 has，不用 have；have 用于复数主语或 I/you/we/they。",
        "instances": [
          {
            "wrong": "The issue ... have been fixed",
            "right": "The issue ... has been fixed"
          }
        ],
        "examples": [
          {
            "wrong": "The issue have been fixed.",
            "right": "The issue has been fixed."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-08（耗时 73.9s）

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
        "error_type": "逗号误用",
        "fragment": "resolved now, I suspect",
        "explanation": "两个独立的完整子句不能用逗号直接连接，应改为句号、分号或使用连接词。",
        "correction": "resolved now. I suspect"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "the DB missing column",
        "explanation": "column 是可数名词单数，表示“缺少一列”时应在 column 前加不定冠词 a，或改用 a missing column in the DB。",
        "correction": "the DB missing a column"
      },
      {
        "category": "grammar",
        "error_type": "逗号误用",
        "fragment": "not urgent now, we can",
        "explanation": "两个独立的完整子句不能用逗号直接连接，此处应改为句号或用 so 等连接词。",
        "correction": "not urgent now. We can"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The empty log issue in PROD has been resolved now. I suspect this is also caused by the DB missing a column. Then DSD-45874 is not urgent now. We can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "仅修正标点和冠词，保留原句结构和语气。"
      },
      "natural": {
        "text": "The empty log issue in PROD has been resolved now. I suspect it's also caused by a missing column in the DB. Since DSD-45874 isn't urgent anymore, we can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "用 since 替代 then 让逻辑更清晰，it's、isn't 更口语化；a missing column in the DB 比 the DB missing a column 更自然。"
      }
    },
    "learnings": [
      {
        "title": "独立子句不能用逗号直接连接",
        "rule": "两个独立的完整子句之间不能用逗号连接（comma splice），应使用句号、分号或加 and/so 等连接词。口语消息中虽常见，但书面表达建议写规范。",
        "instances": [
          {
            "wrong": "resolved now, I suspect",
            "right": "resolved now. I suspect"
          },
          {
            "wrong": "not urgent now, we can",
            "right": "not urgent now. We can"
          }
        ],
        "examples": [
          {
            "wrong": "The issue is fixed, we can close it.",
            "right": "The issue is fixed. We can close it."
          },
          {
            "wrong": "The quota is created, the config is applied.",
            "right": "The quota is created and the config is applied."
          }
        ]
      },
      {
        "title": "可数名词单数前需冠词",
        "rule": "可数名词单数在句中作宾语时通常需要冠词（a/an/the）。表示“缺少一列”应说 missing a column 或 a missing column。",
        "instances": [
          {
            "wrong": "the DB missing column",
            "right": "the DB missing a column"
          }
        ],
        "examples": [
          {
            "wrong": "The report is missing page.",
            "right": "The report is missing a page."
          },
          {
            "wrong": "The server has missing disk.",
            "right": "The server has a missing disk."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-09（耗时 13.5s）

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
        "error_type": "名词单复数误用",
        "fragment": "some error log",
        "explanation": "some 后接可数名词时应用复数形式，error log 是可数名词，应改为 error logs。",
        "correction": "some error logs"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error logs when triggering dag.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "By the way, checking the running worker pod and scheduler pod would make it easier. That way you can spot any error logs when triggering the dag.",
        "explanation": "用 checking...would make it easier 更口语化，That way 链接上下文更自然，符合 Slack/IM 沟通风格。"
      }
    },
    "learnings": [
      {
        "title": "some 后接可数名词需用复数",
        "rule": "some 表示“一些”时，后接可数名词必须用复数形式；error log 是可数名词，应写作 error logs。",
        "instances": [
          {
            "wrong": "some error log",
            "right": "some error logs"
          }
        ],
        "examples": [
          {
            "wrong": "There are some error log in the file.",
            "right": "There are some error logs in the file."
          }
        ]
      }
    ]
  },
  "reply": null
}
```
