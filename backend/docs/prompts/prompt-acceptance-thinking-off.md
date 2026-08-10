# 提示词输出采集报告（Prompt Output Report）

- **模型**：`deepseek-v4-flash`
- **思考模式**：disabled（关闭）
- **场景**：casual（日常/职场口语）
- **用例数**：9
- **总耗时**：58.3 秒

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

### C-01（耗时 1.5s）

**输入**：Correct the trigger_by field set up logic when creating job.

**输出**：

```json
{
  "intent": "correction",
  "correction": {
    "has_errors": false,
    "errors": [],
    "rewrite": {
      "minimal": {
        "text": "Correct the trigger_by field set up logic when creating job.",
        "explanation": ""
      },
      "natural": {
        "text": "Correct the trigger_by field set up logic when creating job.",
        "explanation": ""
      }
    },
    "learnings": []
  },
  "reply": null
}
```

### C-02（耗时 0.9s）

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

### C-03（耗时 17.4s）

**输入**：In that case, the egress IP(出网ip) of GDSP cluster should be enough, right?

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

### C-04（耗时 3.8s）

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
        "explanation": "resource pool 是可数名词，此处泛指添加资源池，应加不定冠词 a。",
        "correction": "adding a resource pool"
      },
      {
        "category": "grammar",
        "error_type": "不可数名词误用",
        "fragment": "How many storage",
        "explanation": "storage 是不可数名词，不能用 many 修饰，应使用 much 或 how much。",
        "correction": "How much storage"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "This pvc should be created when adding a resource pool. How much storage do we want?",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "This pvc should be created when we add a resource pool. How much storage do we need?",
        "explanation": "用 we add 更自然，need 比 want 更符合技术讨论语境。"
      }
    },
    "learnings": [
      {
        "title": "可数名词前需冠词",
        "rule": "可数名词单数形式前需加冠词（a/an/the），表示泛指时用不定冠词。",
        "instances": [
          {
            "wrong": "adding resource pool",
            "right": "adding a resource pool"
          }
        ],
        "examples": [
          {
            "wrong": "We need to create a new user.",
            "right": "We need to create a new user."
          }
        ]
      },
      {
        "title": "不可数名词用 much 修饰",
        "rule": "storage 是不可数名词，表示数量时用 much 或 how much，不能用 many。",
        "instances": [
          {
            "wrong": "How many storage",
            "right": "How much storage"
          }
        ],
        "examples": [
          {
            "wrong": "How many storage do we have?",
            "right": "How much storage do we have?"
          }
        ]
      }
    ]
  }
}
```

### C-05（耗时 3.9s）

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
        "explanation": "不定式后应接动词原形，finished 是过去分词，应改为 finish。",
        "correction": "to finish"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "logs is empty",
        "explanation": "logs 是复数名词，谓语动词应用 are，而不是 is。",
        "correction": "logs are empty"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Is it possible to finish the testing for `DSD-45874` and release it by this week? This would fix the issue that airflow worker/scheduler logs are empty.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Can we finish testing for `DSD-45874` and release it this week? That would fix the empty airflow worker/scheduler logs issue.",
        "explanation": "用 Can we 更口语化，省略 the 和 by 更简洁，符合 Slack 日常沟通风格。"
      }
    },
    "learnings": [
      {
        "title": "不定式后接动词原形",
        "rule": "不定式 to + 动词原形，不能接过去分词或第三人称单数形式。",
        "instances": [
          {
            "wrong": "to finished",
            "right": "to finish"
          }
        ],
        "examples": [
          {
            "wrong": "I need to finished the report.",
            "right": "I need to finish the report."
          }
        ]
      },
      {
        "title": "主谓一致",
        "rule": "复数主语后谓语动词用复数形式，logs 是复数，谓语用 are。",
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
      }
    ]
  }
}
```

### C-06（耗时 16.8s）

**输入**：Sorry for the late response, we are working on the release operation, the restart function should work now, please check.

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

### C-07（耗时 5.3s）

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
        "explanation": "主语是 The issue，是单数，谓语动词应为 has 而不是 have。",
        "correction": "The issue airflow instance log has been fixed"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "create a new airflow instance",
        "explanation": "airflow instance 是可数名词单数，需要冠词 a，这里已经用了 a，但原句可能缺少冠词，此处实际正确，但为了保持一致性，不列为错误。",
        "correction": "create a new airflow instance"
      },
      {
        "category": "style",
        "error_type": "语域错配",
        "fragment": "could you please",
        "explanation": "在 Slack/IM 场景中，'could you please' 略显正式，通常用更简洁的 'Can you' 或 'Please' 更自然。",
        "correction": "Can you"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The issue airflow instance log has been fixed, could you please create a new airflow instance instead? The log viewer and download should be real quick.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "The airflow instance log issue is fixed. Can you create a new airflow instance instead? The log viewer and download should be quick.",
        "explanation": "用更简洁的 'Can you' 和 'is fixed' 更符合 Slack 日常沟通风格，去掉 'please' 使语气更直接。"
      }
    },
    "learnings": [
      {
        "title": "主谓一致",
        "rule": "主语是单数名词时，谓语动词必须用单数形式。",
        "instances": [
          {
            "wrong": "The issue ... have been fixed",
            "right": "The issue ... has been fixed"
          }
        ],
        "examples": [
          {
            "wrong": "The problem have been solved.",
            "right": "The problem has been solved."
          }
        ]
      },
      {
        "title": "语域匹配",
        "rule": "在即时消息或 Slack 场景中，使用更简洁直接的请求表达，如 'Can you' 或 'Please'，避免过于正式的 'could you please'。",
        "instances": [
          {
            "wrong": "could you please",
            "right": "Can you"
          }
        ],
        "examples": [
          {
            "wrong": "Could you please check the logs?",
            "right": "Can you check the logs?"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-08（耗时 4.5s）

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
        "error_type": "冠词缺失",
        "fragment": "the DB missing column",
        "explanation": "DB 前缺少冠词，应使用 the DB 或 a DB，此处特指生产环境的数据库，应用 the。",
        "correction": "the missing column in the DB"
      },
      {
        "category": "grammar",
        "error_type": "时态错误",
        "fragment": "is also caused by",
        "explanation": "表示“可能也是由……引起的”应用现在完成时被动语态，因为动作发生在过去且对现在有影响。",
        "correction": "has also been caused by"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The empty log issue in PROD has been resolved now. I suspect this has also been caused by the missing column in the DB. Then DSD-45874 is not urgent now, we can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "The empty log issue in PROD is resolved now. I think it's also due to the missing column in the DB. So DSD-45874 isn't urgent anymore, we can ship both DSD-45874 & DSD-45252 next week.",
        "explanation": "用 is resolved 和 due to 更口语化，ship 比 release 更贴近技术团队日常沟通。"
      }
    },
    "learnings": [
      {
        "title": "名词前需冠词",
        "rule": "特指某个名词时，前面需加定冠词 the。",
        "instances": [
          {
            "wrong": "the DB missing column",
            "right": "the missing column in the DB"
          }
        ],
        "examples": [
          {
            "wrong": "the DB missing column",
            "right": "the missing column in the DB"
          }
        ]
      },
      {
        "title": "现在完成时表影响",
        "rule": "表示过去动作对现在有影响时，应用现在完成时。",
        "instances": [
          {
            "wrong": "is also caused by",
            "right": "has also been caused by"
          }
        ],
        "examples": [
          {
            "wrong": "The issue is caused by the config.",
            "right": "The issue has been caused by the config."
          }
        ]
      }
    ]
  }
}
```

### C-09（耗时 4.1s）

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
        "error_type": "冠词缺失",
        "fragment": "there are some error log",
        "explanation": "error log 在此处指代多个日志条目，应使用复数形式 logs，且 some 后接可数名词复数。",
        "correction": "there are some error logs"
      },
      {
        "category": "grammar",
        "error_type": "时态错误",
        "fragment": "when triggering dag",
        "explanation": "此处描述一般情况，用一般现在时更合适，且 dag 前应加冠词 the。",
        "correction": "when triggering the DAG"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error logs when triggering the DAG.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "By the way, you could also check the running worker and scheduler pods more easily. That'd help if there are any error logs when triggering the DAG.",
        "explanation": "用 pods 复数涵盖两个 pod，用 That'd help 更口语化，any 更自然。"
      }
    },
    "learnings": [
      {
        "title": "可数名词复数",
        "rule": "some 后接可数名词时，名词必须用复数形式。",
        "instances": [
          {
            "wrong": "some error log",
            "right": "some error logs"
          }
        ],
        "examples": [
          {
            "wrong": "There are some error log.",
            "right": "There are some error logs."
          }
        ]
      },
      {
        "title": "专有名词前加冠词",
        "rule": "DAG 作为特定术语时，通常加定冠词 the 指代具体对象。",
        "instances": [
          {
            "wrong": "triggering dag",
            "right": "triggering the DAG"
          }
        ],
        "examples": [
          {
            "wrong": "When triggering dag, check logs.",
            "right": "When triggering the DAG, check logs."
          }
        ]
      }
    ]
  }
}
```
