# 提示词输出采集报告（Prompt Output Report）

- **模型**：`qwen3.7-flash`
- **思考模式**：disabled（关闭）
- **场景**：casual（日常/职场口语）
- **用例数**：9
- **总耗时**：27.3 秒

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
- **括号内中文注释**（如 `egress IP(出网ip)` 中的 `(出网ip)`）是作者的翻译注释，不是待纠错内容：fragment 不得包含注释，注释前的英文术语（如 `IP`）按专有缩写处理，不得因其元音音素而强加不定冠词（`an IP`）

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

### C-01（耗时 2.7s）

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
        "explanation": "job 是可数名词单数，此处特指创建任务这一行为或泛指此类操作，需加不定冠词 a。",
        "correction": "creating a job"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Correct the trigger_by field set up logic when creating a job.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Fix the trigger_by field setup logic for new jobs.",
        "explanation": "用 Fix 更直接，setup 比 set up 作定语更常见，for new jobs 更符合技术语境。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数需限定词",
        "rule": "可数名词单数（如 job, task, file）在句中不能裸奔，必须加冠词（a/an/the）或所有格等限定词。",
        "instances": [
          {
            "wrong": "creating job",
            "right": "creating a job"
          }
        ],
        "examples": [
          {
            "wrong": "Please check the status of server.",
            "right": "Please check the status of the server."
          },
          {
            "wrong": "I need to update config file.",
            "right": "I need to update the config file."
          }
        ]
      }
    ]
  }
}
```

### C-02（耗时 0.6s）

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

### C-03（耗时 0.6s）

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
  }
}
```

### C-04（耗时 4.3s）

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
        "fragment": "This pvc",
        "explanation": "pvc 是可数名词单数，且此处指代特定的一个 PVC，需加不定冠词 a。",
        "correction": "A pvc"
      },
      {
        "category": "grammar",
        "error_type": "介词缺失",
        "fragment": "when adding resource pool",
        "explanation": "adding 是及物动词，后接宾语 resource pool 时，前面缺少定冠词 the（特指该资源池）或不定冠词 a。",
        "correction": "when adding the resource pool"
      },
      {
        "category": "collocation",
        "error_type": "不可数名词误用",
        "fragment": "How many storage",
        "explanation": "storage 表示“存储空间”时为不可数名词，不能用 how many 修饰，应使用 how much。",
        "correction": "How much storage"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "A pvc should be created when adding the resource pool. How much storage do we want?",
        "explanation": "仅修正语法错误，保留原句结构和语气。"
      },
      "natural": {
        "text": "We need to create a PVC when adding the resource pool. How much storage should we allocate?",
        "explanation": "将被动语态改为主动语态更直接；allocate 比 want 在技术语境下更专业、具体。"
      }
    },
    "learnings": [
      {
        "title": "不可数名词与 How much/many",
        "rule": "Storage（存储空间）是不可数名词，询问数量时应使用 How much，而非 How many。How many 仅用于可数名词复数。",
        "instances": [
          {
            "wrong": "How many storage",
            "right": "How much storage"
          }
        ],
        "examples": [
          {
            "wrong": "How many memory do you have?",
            "right": "How much memory do you have?"
          },
          {
            "wrong": "How many disk space is left?",
            "right": "How much disk space is left?"
          }
        ]
      }
    ]
  }
}
```

### C-05（耗时 4.1s）

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
        "error_type": "动词形式错误",
        "fragment": "to finished",
        "explanation": "不定式 to 后应接动词原形，finished 是过去式/过去分词。",
        "correction": "to finish"
      },
      {
        "category": "collocation",
        "error_type": "搭配冗余",
        "fragment": "the issue that ariflow worker/scheduler logs is empty issue",
        "explanation": "句首已使用 the issue，结尾再次重复 issue 造成语义冗余；此外 logs 为复数名词，系动词应用 are 而非 is。",
        "correction": "that the airflow worker/scheduler logs are empty"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Is it possible to finish the testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it by this week? This would fix the issue that airflow worker/scheduler logs are empty.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Can we wrap up testing for DSD-45874 and release it this week? It should fix the empty log issue for the airflow workers/schedulers.",
        "explanation": "用 wrap up 替代 finish 更地道，简化了 Jira 链接引用方式，将冗长的从句改为简洁的名词短语，更符合 Slack 沟通习惯。"
      }
    },
    "learnings": [
      {
        "title": "不定式后接动词原形",
        "rule": "在不定式符号 to 之后，必须使用动词原形，不能使用过去式或过去分词。",
        "instances": [
          {
            "wrong": "to finished",
            "right": "to finish"
          }
        ],
        "examples": [
          {
            "wrong": "I want to went there.",
            "right": "I want to go there."
          }
        ]
      },
      {
        "title": "避免同义反复与主谓一致",
        "rule": "在描述问题时，避免在同一句中重复使用相同的中心名词（如 issue）；同时注意主语（logs）与系动词（are/is）的数的一致。",
        "instances": [
          {
            "wrong": "the issue that ... is empty issue",
            "right": "the issue that ... are empty"
          }
        ],
        "examples": [
          {
            "wrong": "The problem of the error is an error.",
            "right": "The problem is an error."
          }
        ]
      }
    ]
  }
}
```

### C-06（耗时 3.6s）

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
        "explanation": "原句由多个独立子句组成，仅用逗号连接属于逗号拼接错误。应使用句号、分号或连词断开。",
        "correction": "Sorry for the late response. We are working on the release operation; the restart function should work now. Please check."
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Sorry for the late response. We are working on the release operation, and the restart function should work now. Please check.",
        "explanation": "将长句拆分为独立的句子，修正标点符号错误，保留原意和语气。"
      },
      "natural": {
        "text": "Sorry for the delay! We're still finalizing the release, but the restart function should be good to go now. Could you give it a try?"
      }
    },
    "learnings": [
      {
        "title": "避免逗号拼接",
        "rule": "英语中不能仅用逗号连接两个或多个完整的独立子句（即包含主语和谓语且能单独成句的部分）。应使用句号、分号，或在中间加上并列连词（如 and, but, so）。",
        "instances": [
          {
            "wrong": "I like apples, he likes oranges.",
            "right": "I like apples, and he likes oranges."
          },
          {
            "wrong": "It is raining, I will stay home.",
            "right": "It is raining, so I will stay home."
          }
        ],
        "examples": [
          {
            "wrong": "The server is down, we need to fix it.",
            "right": "The server is down. We need to fix it."
          }
        ]
      }
    ]
  }
}
```

### C-07（耗时 2.3s）

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
        "explanation": "主语 The issue airflow instance log 是单数，谓语动词应用 has been。",
        "correction": "The issue airflow instance log has been fixed"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The issue airflow instance log has been fixed, could you please create a new airflow instance instead? The log viewer and download should be real quick.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Fixed the issue with the Airflow instance logs. Could you spin up a new one? Viewing and downloading logs should be much faster now.",
        "explanation": "拆分长句，使用更地道的口语表达（spin up），并优化了后半句的表述使其更自然。"
      }
    },
    "learnings": [
      {
        "title": "主谓一致原则",
        "rule": "当主语为单数名词短语时，谓语动词需使用单数形式（如 has）。",
        "instances": [
          {
            "wrong": "The issue airflow instance log have been fixed",
            "right": "The issue airflow instance log has been fixed"
          }
        ],
        "examples": [
          {
            "wrong": "The list of items are ready.",
            "right": "The list of items is ready."
          }
        ]
      }
    ]
  }
}
```

### C-08（耗时 4.8s）

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
        "explanation": "两个独立完整句子之间不能仅用逗号连接，需使用句号、分号或连词。",
        "correction": "resolved now. I suspect"
      },
      {
        "category": "collocation",
        "error_type": "搭配冗余",
        "fragment": "now ... now",
        "explanation": "句中重复使用 'now' 显得累赘，第二处可省略或替换为 'at the moment'。",
        "correction": "resolved now, I suspect this is also caused by the DB missing column. Then DSD-45874 is not urgent, we can release both DSD-45874 & DSD-45252 next week."
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The empty log issue in PROD has been resolved now. I suspect this is also caused by the DB missing column. Then DSD-45874 is not urgent at the moment; we can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "修正了标点符号错误，并去除了重复的 'now'。"
      },
      "natural": {
        "text": "The empty log issue in PROD is fixed. I think it was caused by a missing DB column too. Since DSD-45874 isn't urgent anymore, let's hold off and release both DSD-45874 & DSD-45252 next week.",
        "explanation": "使用了更地道的口语表达（is fixed, hold off），逻辑连接更顺畅。"
      }
    },
    "learnings": [
      {
        "title": "避免逗号拼接 (Comma Splice)",
        "rule": "在英语中，两个独立的完整句子（Independent Clauses）不能仅通过逗号连接。必须使用句号（.）、分号（;）或者并列连词（如 and, but, so）。",
        "instances": [
          {
            "wrong": "Issue resolved, I suspect...",
            "right": "Issue resolved. I suspect..."
          }
        ],
        "examples": [
          {
            "wrong": "I like coffee, she likes tea.",
            "right": "I like coffee, and she likes tea."
          }
        ]
      },
      {
        "title": "避免同义反复",
        "rule": "在同一句话或紧密相连的句子中，尽量避免重复使用相同的副词（如 now, very），以保持语言简洁。",
        "instances": [
          {
            "wrong": "...resolved now... not urgent now",
            "right": "...resolved now... not urgent"
          }
        ],
        "examples": [
          {
            "wrong": "I am very happy very much.",
            "right": "I am very happy."
          }
        ]
      }
    ]
  }
}
```

### C-09（耗时 4.2s）

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
        "explanation": "主语 log 为单数，谓语动词应使用 is 而非 are。",
        "correction": "there is an error log"
      },
      {
        "category": "collocation",
        "error_type": "用词不当",
        "fragment": "triggering dag",
        "explanation": "dag 通常作为可数名词使用，此处缺少冠词；且触发 DAG 常用 run 或 execute。",
        "correction": "running a DAG"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there is an error log when running a DAG.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Also, it's easier to just check the worker and scheduler pods for errors when a DAG runs.",
        "explanation": "更口语化，将长句简化，符合 Slack/IM 沟通习惯。"
      }
    },
    "learnings": [
      {
        "title": "There be 句型的主谓一致",
        "rule": "在 there be 句型中，be 动词的单复数由紧随其后的主语决定。若主语为单数或不可数名词，使用 is；若为复数，使用 are。",
        "instances": [
          {
            "wrong": "there are some error log",
            "right": "there is an error log"
          }
        ],
        "examples": [
          {
            "wrong": "There are a problem.",
            "right": "There is a problem."
          }
        ]
      },
      {
        "title": "DAG 的动词搭配与冠词",
        "rule": "DAG（有向无环图）是可数名词，泛指时需用不定冠词 a/an。在 Airflow 等语境中，触发或执行 DAG 常用 run 或 execute。",
        "instances": [
          {
            "wrong": "triggering dag",
            "right": "running a DAG"
          }
        ],
        "examples": [
          {
            "wrong": "I am fixing triggering dag.",
            "right": "I am fixing running a DAG."
          }
        ]
      }
    ]
  }
}
```
