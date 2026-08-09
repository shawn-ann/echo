# 提示词输出采集报告（Prompt Output Report）

- **模型**：`deepseek-v4-flash`
- **用例数**：9
- **总耗时**：493.2 秒

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
- `natural` 改写应提供比 `minimal` 更自然/地道的整句表达，风格按上下文选择（正式或口语均可）；若 `minimal` 已经足够自然（如修正后已是唯一地道说法），则允许 `natural` 与 `minimal` 相同，无需强行制造差异。
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

### C-01（耗时 23.3s）

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
        "error_type": "动词误作名词",
        "fragment": "set up logic",
        "explanation": "set up 是动词短语，此处修饰名词 logic 应使用名词形式 setup，表示“设置逻辑”。",
        "correction": "setup logic"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "creating job",
        "explanation": "job 是可数名词，单数形式前需加冠词 a，泛指“创建作业”时应写 creating a job。",
        "correction": "creating a job"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Correct the `trigger_by` field setup logic when creating a job.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Fix the logic behind setting up the `trigger_by` field when creating a job.",
        "explanation": "用 fix the logic behind... 更贴近技术沟通习惯，动名词 setting up 也更自然地引出设置动作。"
      }
    },
    "learnings": [
      {
        "title": "动词短语与名词形式",
        "rule": "set up 是动词短语，表示“设置”；名词形式为 setup，表示“设置、配置”。修饰名词时用 setup，不能用动词短语 set up。",
        "instances": [
          {
            "wrong": "set up logic",
            "right": "setup logic"
          },
          {
            "wrong": "field set up logic",
            "right": "field setup logic"
          }
        ],
        "examples": [
          {
            "wrong": "The set up process is complex.",
            "right": "The setup process is complex."
          },
          {
            "wrong": "Please review the field set up.",
            "right": "Please review the field setup."
          }
        ]
      },
      {
        "title": "可数名词前需冠词",
        "rule": "单数可数名词前必须加冠词（a/an/the）或其他限定词，不能单独出现。",
        "instances": [
          {
            "wrong": "creating job",
            "right": "creating a job"
          }
        ],
        "examples": [
          {
            "wrong": "When creating job, check the config.",
            "right": "When creating a job, check the config."
          },
          {
            "wrong": "I need to create job.",
            "right": "I need to create a job."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-02（耗时 63.9s）

**输入**：What do you mean you can't restart this webapp? getting an error?

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "grammar",
        "error_type": "主语与助动词缺失",
        "fragment": "getting an error?",
        "explanation": "getting an error? 是省略了主语和助动词的疑问句，口语或即时消息中较常见，但在正式书面语中应补全为 Are you getting an error?。",
        "correction": "Are you getting an error?"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "What do you mean you can't restart this webapp? Are you getting an error?",
        "explanation": "仅补全第二个问句，保留原句结构和口语语气"
      },
      "natural": {
        "text": "What do you mean you can't restart this webapp? Are you seeing an error?",
        "explanation": "改用 seeing an error，更贴近技术聊天中询问报错信息的常见说法，同时保持口语化。"
      }
    },
    "learnings": [
      {
        "title": "口语省略疑问句在正式书面语中需补全",
        "rule": "在英语口语或即时消息中，可以省略句首的 Are you 直接把现在分词短语用作疑问句（如 Getting an error?），但在正式书面语中应补全主语和助动词，写成 Are you getting an error? 等完整句。",
        "instances": [
          {
            "wrong": "getting an error?",
            "right": "Are you getting an error?"
          }
        ],
        "examples": [
          {
            "wrong": "Working on it?",
            "right": "Are you working on it?"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-03（耗时 20.7s）

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
        "explanation": "GDSP cluster 在此处指代具体且语境明确的集群，应加定冠词 the。",
        "correction": "the GDSP cluster"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "In that case, the egress IP of the GDSP cluster should be enough, right?",
        "explanation": "仅修正冠词缺失，保留原句结构和语气"
      },
      "natural": {
        "text": "In that case, the GDSP cluster's egress IP should suffice, right?",
        "explanation": "用所有格 the GDSP cluster's 更自然紧凑，suffice 比 be enough 更书面简洁。"
      }
    },
    "learnings": [
      {
        "title": "指代明确的普通名词前需加定冠词",
        "rule": "当名词（如 cluster）在语境中特指某一具体对象时，必须使用定冠词 the，不能省略。",
        "instances": [
          {
            "wrong": "GDSP cluster",
            "right": "the GDSP cluster"
          }
        ],
        "examples": [
          {
            "wrong": "The request is handled by GDSP cluster.",
            "right": "The request is handled by the GDSP cluster."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-04（耗时 23.8s）

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
        "explanation": "resource pool 是可数名词单数，前面缺少冠词，应加 a 或 the。",
        "correction": "adding a resource pool"
      },
      {
        "category": "grammar",
        "error_type": "不可数名词误用",
        "fragment": "How many storage",
        "explanation": "storage 是不可数名词，不能用 many 修饰，应用 much。",
        "correction": "How much storage"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "This `pvc` should be created when adding a resource pool. How much storage do we want?",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "This `pvc` should be created when a resource pool is added. How much storage do we want?",
        "explanation": "用完整被动从句 when a resource pool is added 替代 when adding，句子结构更正式清晰；同时修正不可数名词用法。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数需要冠词",
        "rule": "可数名词单数前必须加冠词（a/an/the）或限定词，不能裸用。resource pool 是可数名词单数，所以应说 a resource pool 或 the resource pool。",
        "instances": [
          {
            "wrong": "adding resource pool",
            "right": "adding a resource pool"
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
        "title": "不可数名词用 much 修饰",
        "rule": "storage 是不可数名词，询问数量时用 How much，不能用 How many。How many 只能修饰可数名词复数。",
        "instances": [
          {
            "wrong": "How many storage",
            "right": "How much storage"
          }
        ],
        "examples": [
          {
            "wrong": "How many storage do we need?",
            "right": "How much storage do we need?"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-05（耗时 94.9s）

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
        "explanation": "不定式 to 后必须接动词原形，finished 是过去式，应改为 finish。",
        "correction": "to finish"
      },
      {
        "category": "chinglish",
        "error_type": "中式直译",
        "fragment": "by this week",
        "explanation": "by 表示截止时间时后接具体时间点，英语中不说 by this week；表示“本周内”应使用 this week，或明确截止时间用 by the end of this week。",
        "correction": "by the end of this week"
      },
      {
        "category": "grammar",
        "error_type": "拼写错误",
        "fragment": "ariflow",
        "explanation": "Airflow 的正确拼写为 airflow，这里把 r 放到了错误位置。",
        "correction": "airflow"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "logs is",
        "explanation": "logs（日志）是复数，谓语应使用 are。",
        "correction": "logs are"
      },
      {
        "category": "collocation",
        "error_type": "搭配冗余",
        "fragment": "empty issue",
        "explanation": "the issue that 已包含“问题”的含义，从句末尾再写 issue 造成语义重复，应删去。",
        "correction": "empty"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Is it possible to finish the testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it by the end of this week? This would fix the issue that airflow worker/scheduler logs are empty.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Can we finish testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it this week? That would fix the issue where airflow worker/scheduler logs are empty.",
        "explanation": "改用 Can we... 更口语化；用 this week 表达“本周内”，用 where 引导问题从句，表达更自然。"
      }
    },
    "learnings": [
      {
        "title": "不定式后接动词原形",
        "rule": "不定式符号 to 后面必须使用动词原形，不能使用过去式或其他形式。",
        "instances": [
          {
            "wrong": "to finished",
            "right": "to finish"
          }
        ],
        "examples": [
          {
            "wrong": "I want to finished the report.",
            "right": "I want to finish the report."
          }
        ]
      },
      {
        "title": "截止时间用 by the end of this week",
        "rule": "英语中表示“本周内”应使用 this week，表示“截至本周结束”用 by the end of this week；by 后接具体时间点，如 by Friday，不能说 by this week。",
        "instances": [
          {
            "wrong": "by this week",
            "right": "by the end of this week"
          }
        ],
        "examples": [
          {
            "wrong": "Can we finish by this week?",
            "right": "Can we finish by the end of this week?"
          }
        ]
      },
      {
        "title": "技术产品名拼写",
        "rule": "技术产品名应使用官方拼写，Airflow 应写作 airflow，不要写成 ariflow。",
        "instances": [
          {
            "wrong": "ariflow",
            "right": "airflow"
          }
        ],
        "examples": [
          {
            "wrong": "Check the ariflow logs.",
            "right": "Check the airflow logs."
          }
        ]
      },
      {
        "title": "复数主语用复数谓语",
        "rule": "logs 是复数名词，谓语要用 are，主语与谓语在数上保持一致。",
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
          }
        ]
      },
      {
        "title": "避免 issue 语义重复",
        "rule": "the issue that 已表达“问题”，从句结尾不要再重复 issue，避免语义冗余。",
        "instances": [
          {
            "wrong": "the issue that logs are empty issue",
            "right": "the issue that logs are empty"
          }
        ],
        "examples": [
          {
            "wrong": "The issue that the file is missing issue should be fixed.",
            "right": "The issue that the file is missing should be fixed."
          }
        ]
      }
    ]
  }
}
```

### C-06（耗时 35.1s）

**输入**：Sorry for the late response, we are working on the release operation, the restart function should work now, please check.

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": true,
    "errors": [
      {
        "category": "collocation",
        "error_type": "搭配冗余",
        "fragment": "the release operation",
        "explanation": "release 本身已可指代“发布”这一动作或事项，再加 operation 显得冗余；更自然的说法是 the release 或 the release process。",
        "correction": "the release"
      },
      {
        "category": "grammar",
        "error_type": "逗号误用（comma splice）",
        "fragment": "should work now, please check",
        "explanation": "should work now 与 please check 是两个完整的独立分句，不能用逗号直接连接；应改用句号断开，或用 so 等连接词连接。",
        "correction": "should work now. Please check"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Sorry for the late response. We are working on the release, so the restart function should work now. Please check.",
        "explanation": "仅修正搭配冗余和逗号连接问题，保留原句结构和语气"
      },
      "natural": {
        "text": "Sorry for the late reply! We're working on the release, so the restart should work now — please give it a try.",
        "explanation": "用 reply 更贴近聊天语境，we're 更口语化，restart 直接作名词使用，结尾用 give it a try 显得更自然友好。"
      }
    },
    "learnings": [
      {
        "title": "动作名词不必叠加 operation",
        "rule": "表示“正在做某个动作或流程”时，release、deployment 等词本身已可指代该动作，无需再加 operation；如需强调流程可说 the release process。",
        "instances": [
          {
            "wrong": "the release operation",
            "right": "the release"
          },
          {
            "wrong": "working on the deployment operation",
            "right": "working on the deployment"
          }
        ],
        "examples": [
          {
            "wrong": "We are working on the deployment operation.",
            "right": "We are working on the deployment."
          },
          {
            "wrong": "The release operation is delayed.",
            "right": "The release is delayed."
          }
        ]
      },
      {
        "title": "逗号不能连接两个完整句子",
        "rule": "两个完整的独立分句不能仅用逗号连接（comma splice），应改用句号、分号或连接词（so、and、but 等）。",
        "instances": [
          {
            "wrong": "The restart function should work now, please check.",
            "right": "The restart function should work now. Please check."
          }
        ],
        "examples": [
          {
            "wrong": "The file is uploaded, you can download it.",
            "right": "The file is uploaded. You can download it."
          },
          {
            "wrong": "It's fixed now, please verify.",
            "right": "It's fixed now. Please verify."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-07（耗时 118.4s）

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
        "error_type": "词序不当",
        "fragment": "issue airflow instance log",
        "explanation": "名词短语中修饰语应放在被修饰名词之前，“airflow 实例日志的问题”应表达为 airflow instance log issue，而不是 issue airflow instance log。",
        "correction": "airflow instance log issue"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "have been fixed",
        "explanation": "主语 The issue（或 The airflow instance log issue）是单数，现在完成时的助动词应用 has，而不是 have。",
        "correction": "has been fixed"
      },
      {
        "category": "grammar",
        "error_type": "逗号拼接",
        "fragment": "fixed, could you",
        "explanation": "两个独立分句不能仅用逗号连接，应用句号、分号或连接词分隔。",
        "correction": "fixed. Could you"
      },
      {
        "category": "style",
        "error_type": "语域错配",
        "fragment": "real quick",
        "explanation": "real quick 是口语化表达，在正式或书面沟通中显得过于随意；在 Slack 等即时消息中可使用，但正式场合建议用 really quick 或 very quick。",
        "correction": "really quick"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The airflow instance log issue has been fixed. Could you please create a new airflow instance instead? The log viewer and download should be really quick.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Since the airflow instance log issue has been fixed, could you please create a new airflow instance instead? The log viewer and download should be quick.",
        "explanation": "用 Since 连接原因与请求，句子更连贯；去掉口语化的 really，整体更简洁自然。"
      }
    },
    "learnings": [
      {
        "title": "名词修饰语放在被修饰名词之前",
        "rule": "当一个名词修饰另一个名词时，修饰语要放在被修饰名词之前，不能颠倒顺序。",
        "instances": [
          {
            "wrong": "issue airflow instance log",
            "right": "airflow instance log issue"
          }
        ],
        "examples": [
          {
            "wrong": "problem the server",
            "right": "server problem"
          }
        ]
      },
      {
        "title": "单数主语用 has，复数主语用 have",
        "rule": "现在完成时的助动词要与主语保持一致：单数主语用 has，复数主语用 have。",
        "instances": [
          {
            "wrong": "have been fixed",
            "right": "has been fixed"
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
        "title": "两个独立分句不能仅用逗号连接",
        "rule": "两个独立分句之间需要句号、分号或连接词，不能用逗号直接连接。",
        "instances": [
          {
            "wrong": "fixed, could you",
            "right": "fixed. Could you"
          }
        ],
        "examples": [
          {
            "wrong": "The weather was nice, we went out.",
            "right": "The weather was nice. We went out."
          }
        ]
      },
      {
        "title": "口语化表达注意语域",
        "rule": "real quick 是口语化的非正式表达，在即时消息中可以使用；在正式邮件或书面文档中应改用 really quick 或 very quick。",
        "instances": [
          {
            "wrong": "real quick",
            "right": "really quick"
          }
        ],
        "examples": [
          {
            "wrong": "I'll respond real quick.",
            "right": "I'll respond very quickly."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-08（耗时 82.0s）

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
        "explanation": "两个独立分句用逗号连接不符合英语标点规则，应使用句号、分号或连接词。",
        "correction": "resolved now; I suspect"
      },
      {
        "category": "grammar",
        "error_type": "逗号拼接",
        "fragment": "urgent now, we can",
        "explanation": "两个独立分句用逗号连接不符合英语标点规则，应使用句号、分号或连接词。",
        "correction": "urgent now; we can"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "the DB missing column",
        "explanation": "column 是可数名词单数，在动名词复合结构 the DB missing ... 中作宾语，需在前面加不定冠词 a。",
        "correction": "the DB missing a column"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The empty log issue in PROD has been resolved now; I suspect this is also caused by the DB missing a column. Then DSD-45874 is not urgent now; we can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "The empty log issue in PROD has been resolved now. I suspect this is also caused by a missing column in the DB. Since DSD-45874 is no longer urgent, we can release both DSD-45874 and DSD-45252 next week.",
        "explanation": "用 a missing column in the DB 更自然，Since 和 no longer urgent 让逻辑更清晰，整句更流畅。"
      }
    },
    "learnings": [
      {
        "title": "两个独立分句不能用逗号连接",
        "rule": "在英语中，两个完整的独立分句不能仅用逗号连接（逗号拼接），应使用句号、分号或连词（and, so, but 等）。",
        "instances": [
          {
            "wrong": "resolved now, I suspect",
            "right": "resolved now; I suspect"
          },
          {
            "wrong": "urgent now, we can",
            "right": "urgent now; we can"
          }
        ],
        "examples": [
          {
            "wrong": "It is late, we should go.",
            "right": "It is late; we should go."
          }
        ]
      },
      {
        "title": "可数名词单数前需要冠词",
        "rule": "可数名词的单数形式在句子中作宾语时，前面需要加不定冠词 a/an 或定冠词 the 等限定词；动名词复合结构中的宾语名词同样适用。",
        "instances": [
          {
            "wrong": "the DB missing column",
            "right": "the DB missing a column"
          }
        ],
        "examples": [
          {
            "wrong": "The issue is caused by missing column.",
            "right": "The issue is caused by a missing column."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-09（耗时 31.0s）

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
        "explanation": "there are 后接可数名词 error log 时应使用复数形式 error logs，也可用 any 更贴合条件句。",
        "correction": "some error logs"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "when triggering dag",
        "explanation": "DAG 指某个具体工作流，是可数名词，前面应加冠词，通常写作 the DAG 或 a DAG。",
        "correction": "when triggering the DAG"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error logs when triggering the DAG.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "By the way, you could also check the running worker and scheduler pods more easily. That would help if any error logs come up when the DAG is triggered.",
        "explanation": "将 worker pod and scheduler pod 合并为 worker and scheduler pods 更简洁；用 any 和 come up 更贴合条件句和口语沟通场景。"
      }
    },
    "learnings": [
      {
        "title": "some 后接可数名词需用复数",
        "rule": "some 修饰可数名词时必须使用复数形式，且与 there are 保持一致：there are some + 名词复数。",
        "instances": [
          {
            "wrong": "some error log",
            "right": "some error logs"
          }
        ],
        "examples": [
          {
            "wrong": "There are some error log in the output.",
            "right": "There are some error logs in the output."
          }
        ]
      },
      {
        "title": "单数可数名词前需加冠词",
        "rule": "单数可数名词前通常需要冠词（a/an/the）。DAG 在指某个具体工作流时用 the DAG。",
        "instances": [
          {
            "wrong": "when triggering dag",
            "right": "when triggering the DAG"
          }
        ],
        "examples": [
          {
            "wrong": "The task fails when triggering dag.",
            "right": "The task fails when triggering the DAG."
          }
        ]
      }
    ]
  },
  "reply": null
}
```
