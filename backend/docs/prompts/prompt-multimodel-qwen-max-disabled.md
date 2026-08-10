# 提示词输出采集报告（Prompt Output Report）

- **模型**：`qwen3.8-max`
- **思考模式**：disabled（关闭）
- **场景**：casual（日常/职场口语）
- **用例数**：9
- **总耗时**：57.4 秒

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

### C-01（耗时 5.7s）

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
        "explanation": "job 是可数名词单数，此处泛指创建任务这一动作，需加不定冠词 a。",
        "correction": "creating a job"
      },
      {
        "category": "style",
        "error_type": "语域错配",
        "fragment": "set up logic",
        "explanation": "set up 作形容词修饰名词时通常写作 setup（连写）；在技术文档或工单标题中，setup logic 比 set up logic 更规范。",
        "correction": "setup logic"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Correct the trigger_by field setup logic when creating a job.",
        "explanation": "仅修正冠词和复合词拼写，保留原句结构和语气"
      },
      "natural": {
        "text": "Fix the trigger_by field setup logic when creating a job.",
        "explanation": "用 Fix 替代 Correct 更符合技术工单/Slack 沟通习惯，简洁直接"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数需冠词",
        "rule": "可数名词单数在句中作宾语且表示泛指时，必须使用不定冠词 a/an 或定冠词 the，不可裸用。",
        "instances": [
          {
            "wrong": "creating job",
            "right": "creating a job"
          }
        ],
        "examples": [
          {
            "wrong": "when deploying service",
            "right": "when deploying a service"
          },
          {
            "wrong": "update config",
            "right": "update a config"
          }
        ]
      },
      {
        "title": "复合名词拼写",
        "rule": "set up 是动词短语，作名词或形容词修饰其他名词时应连写为 setup。",
        "instances": [
          {
            "wrong": "set up logic",
            "right": "setup logic"
          }
        ],
        "examples": [
          {
            "wrong": "the set up process",
            "right": "the setup process"
          },
          {
            "wrong": "initial set up",
            "right": "initial setup"
          }
        ]
      }
    ]
  }
}
```

### C-02（耗时 2.2s）

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

### C-03（耗时 4.8s）

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
        "explanation": "GDSP cluster 是可数名词单数，且此处特指某个集群，需加定冠词 the。",
        "correction": "of the GDSP cluster"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "In that case, the egress IP (出网IP) of the GDSP cluster should be enough, right?",
        "explanation": "仅补充缺失的定冠词，保留原句结构和语气。"
      },
      "natural": {
        "text": "In that case, the GDSP cluster's egress IP (出网IP) should be enough, right?",
        "explanation": "用所有格替代 of 结构更简洁自然，适合 Slack/IM 沟通。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数需限定词",
        "rule": "可数名词单数在句中作宾语或介词宾语时，必须带冠词（a/an/the）或其他限定词（this/that/my 等），不可裸用。",
        "instances": [
          {
            "wrong": "of GDSP cluster",
            "right": "of the GDSP cluster"
          }
        ],
        "examples": [
          {
            "wrong": "I joined project team.",
            "right": "I joined the project team."
          },
          {
            "wrong": "Check server status.",
            "right": "Check the server status."
          }
        ]
      }
    ]
  }
}
```

### C-04（耗时 5.9s）

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
        "explanation": "resource pool 是可数名词单数，此处泛指“一个资源池”，需加不定冠词 a。",
        "correction": "when adding a resource pool"
      },
      {
        "category": "grammar",
        "error_type": "不可数名词误用",
        "fragment": "How many storage",
        "explanation": "storage 是不可数名词，询问数量应用 how much 而非 how many。",
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
        "explanation": "将 do we want 改为 do we need 更符合技术需求确认场景；pvc 作为领域术语保留原样。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数需冠词",
        "rule": "可数名词单数在句中作宾语且表示泛指时，必须使用不定冠词 a/an 或定冠词 the，不可裸用。",
        "instances": [
          {
            "wrong": "adding resource pool",
            "right": "adding a resource pool"
          }
        ],
        "examples": [
          {
            "wrong": "when creating cluster",
            "right": "when creating a cluster"
          },
          {
            "wrong": "add user",
            "right": "add a user"
          }
        ]
      },
      {
        "title": "不可数名词的数量疑问词",
        "rule": "storage、memory、disk space 等不可数名词询问数量时，必须使用 how much，不可使用 how many。",
        "instances": [
          {
            "wrong": "how many storage",
            "right": "how much storage"
          }
        ],
        "examples": [
          {
            "wrong": "how many memory",
            "right": "how much memory"
          },
          {
            "wrong": "how many disk space",
            "right": "how much disk space"
          }
        ]
      }
    ]
  }
}
```

### C-05（耗时 8.5s）

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
        "explanation": "不定式 to 后必须接动词原形，不能用过去式或过去分词。",
        "correction": "to finish"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "logs is empty",
        "explanation": "主语 logs 是复数名词，谓语动词应用 are。",
        "correction": "logs are empty"
      },
      {
        "category": "style",
        "error_type": "搭配冗余",
        "fragment": "the issue that ... issue",
        "explanation": "句首已有 the issue that，句尾再重复 issue 造成语义冗余。",
        "correction": "the issue where airflow worker/scheduler logs are empty"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Is it possible to finish the testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it by this week? This would fix the issue where airflow worker/scheduler logs are empty.",
        "explanation": "仅修正语法和冗余表达，保留原句结构和语气"
      },
      "natural": {
        "text": "Can we finish testing https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it this week? That should fix the empty airflow worker/scheduler logs.",
        "explanation": "用 Can we 更口语化；empty logs 作前置定语更简洁自然，适合 Slack/IM 沟通"
      }
    },
    "learnings": [
      {
        "title": "不定式后接动词原形",
        "rule": "不定式标记 to 后必须接动词原形，不可使用过去式或过去分词形式。",
        "instances": [
          {
            "wrong": "to finished",
            "right": "to finish"
          }
        ],
        "examples": [
          {
            "wrong": "I want to finished the task.",
            "right": "I want to finish the task."
          }
        ]
      },
      {
        "title": "复数主语与谓语一致",
        "rule": "当主语为复数名词（如 logs）时，系动词或助动词必须使用复数形式（are/have），不可用单数（is/has）。",
        "instances": [
          {
            "wrong": "logs is empty",
            "right": "logs are empty"
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
        "title": "避免同义重复",
        "rule": "在 the issue that/where 引导的从句中，若已明确指代问题内容，句尾不应再重复 issue 一词。",
        "instances": [
          {
            "wrong": "the issue that X is Y issue",
            "right": "the issue where X is Y"
          }
        ],
        "examples": [
          {
            "wrong": "This fixes the issue that the API returns error issue.",
            "right": "This fixes the issue where the API returns an error."
          }
        ]
      }
    ]
  }
}
```

### C-06（耗时 6.9s）

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
        "explanation": "多个独立分句仅用逗号连接构成逗号拼接错误，应拆分为独立句子或使用连词/分号。",
        "correction": "Sorry for the late response. We are working on the release operation. The restart function should work now; please check."
      },
      {
        "category": "collocation",
        "error_type": "搭配不当",
        "fragment": "release operation",
        "explanation": "release operation 不是技术场景中的惯用搭配，通常直接说 the release 或 the deployment。",
        "correction": "the release"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Sorry for the late response. We are working on the release. The restart function should work now; please check.",
        "explanation": "仅修正语法和搭配，保留原句结构和语气"
      },
      "natural": {
        "text": "Sorry for the delay! We're working on the release. The restart function should be working now—please give it a try.",
        "explanation": "用 Sorry for the delay 更自然口语化，give it a try 比 please check 更符合 Slack/IM 沟通风格"
      }
    },
    "learnings": [
      {
        "title": "避免逗号拼接",
        "rule": "英语中两个或以上独立分句不能仅用逗号连接，需使用句号、分号或并列连词（and/but/so）分隔。",
        "instances": [
          {
            "wrong": "A, B, C.",
            "right": "A. B. C. 或 A; B; C. 或 A, and B."
          }
        ],
        "examples": [
          {
            "wrong": "I'm busy, I'll reply later.",
            "right": "I'm busy. I'll reply later."
          }
        ]
      },
      {
        "title": "发布操作的惯用表达",
        "rule": "在技术语境中表示“发布”通常直接用 the release 或 the deployment，避免冗余的 release operation。",
        "instances": [
          {
            "wrong": "release operation",
            "right": "the release / the deployment"
          }
        ],
        "examples": [
          {
            "wrong": "We are doing the release operation.",
            "right": "We are working on the release."
          }
        ]
      }
    ]
  }
}
```

### C-07（耗时 7.9s）

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
        "fragment": "log have been fixed",
        "explanation": "主语 log 为单数，谓语动词应用 has been fixed。",
        "correction": "log has been fixed"
      },
      {
        "category": "collocation",
        "error_type": "搭配冗余",
        "fragment": "create a new airflow instance instead",
        "explanation": "前文已说明旧实例日志问题已修复，此处请求创建新实例时 instead 显得多余且逻辑稍显矛盾，建议删除或改为 to replace the old one 以明确意图。",
        "correction": "create a new `airflow` instance"
      },
      {
        "category": "style",
        "error_type": "语域错配",
        "fragment": "real quick",
        "explanation": "real quick 过于口语化（类似中文“贼快”），在职场技术沟通中建议使用 much faster 或 significantly quicker。",
        "correction": "much faster"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The issue with the `airflow` instance log has been fixed. Could you please create a new `airflow` instance? The log viewer and download should be much faster.",
        "explanation": "修正主谓一致、移除冗余副词并调整语域，保留原句结构。"
      },
      "natural": {
        "text": "The `airflow` instance log issue is fixed. Could you spin up a new instance? Log viewing and downloading should be way faster now.",
        "explanation": "使用 spin up 替代 create，way faster 在 Slack/IM 中比 real quick 更自然且不失礼貌，整体更符合技术团队日常沟通习惯。"
      }
    },
    "learnings": [
      {
        "title": "主谓一致原则",
        "rule": "单数名词作主语时，谓语动词必须使用单数形式；复数名词作主语时使用复数形式。",
        "instances": [
          {
            "wrong": "log have been fixed",
            "right": "log has been fixed"
          }
        ],
        "examples": [
          {
            "wrong": "The data is corrupted.",
            "right": "The data are corrupted."
          },
          {
            "wrong": "The logs has been cleared.",
            "right": "The logs have been cleared."
          }
        ]
      },
      {
        "title": "避免过度口语化的程度副词",
        "rule": "在职场或技术沟通中，避免使用 real 作为程度副词修饰形容词（如 real quick, real good），应使用 much, significantly, considerably 等标准副词；Slack/IM 中可用 way 或 pretty。",
        "instances": [
          {
            "wrong": "real quick",
            "right": "much faster"
          }
        ],
        "examples": [
          {
            "wrong": "It's real important.",
            "right": "It's very important."
          },
          {
            "wrong": "This is real slow.",
            "right": "This is quite slow."
          }
        ]
      }
    ]
  }
}
```

### C-08（耗时 9.5s）

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
        "fragment": "has been resolved now, I suspect",
        "explanation": "两个独立句子不能仅用逗号连接，需使用句号、分号或连词。",
        "correction": "has been resolved. I suspect"
      },
      {
        "category": "collocation",
        "error_type": "搭配不当",
        "fragment": "DB missing column",
        "explanation": "missing column 作名词短语时，通常用 a missing DB column 或 the missing column in the DB；原表达缺少冠词且语序不自然。",
        "correction": "a missing DB column"
      },
      {
        "category": "style",
        "error_type": "语域错配",
        "fragment": "Then DSD-45874 is not urgent now",
        "explanation": "Then 用于句首表示因果推论在书面沟通中略显口语化，Slack/IM 中可用 So 或 Therefore 更自然。",
        "correction": "So DSD-45874 is no longer urgent"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The empty log issue in PROD has been resolved. I suspect this was also caused by a missing DB column. So DSD-45874 is no longer urgent, and we can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "修正逗号拼接、冠词缺失及连接词，保留原意和语气。"
      },
      "natural": {
        "text": "The empty log issue in PROD is fixed. Looks like it was also due to a missing DB column, so DSD-45874 isn't urgent anymore. We can ship both DSD-45874 & DSD-45252 next week.",
        "explanation": "用 is fixed / looks like / ship 等口语化表达，更符合 Slack 技术沟通习惯。"
      }
    },
    "learnings": [
      {
        "title": "避免逗号拼接",
        "rule": "两个完整句子之间不能用逗号直接连接，应使用句号、分号或并列连词（and/but/so）。",
        "instances": [
          {
            "wrong": "Issue resolved, I suspect...",
            "right": "Issue resolved. I suspect..."
          }
        ],
        "examples": [
          {
            "wrong": "The bug is fixed, I will test it.",
            "right": "The bug is fixed. I will test it."
          }
        ]
      },
      {
        "title": "名词短语的冠词与语序",
        "rule": "missing + 名词 作可数名词短语时需加冠词，且修饰语顺序应为 冠词 + 形容词 + 名词。",
        "instances": [
          {
            "wrong": "DB missing column",
            "right": "a missing DB column"
          }
        ],
        "examples": [
          {
            "wrong": "caused by DB missing column",
            "right": "caused by a missing DB column"
          }
        ]
      },
      {
        "title": "因果连接词的语域选择",
        "rule": "Then 用于句首表推论偏口语叙事，职场 IM 中推荐 So / Therefore / That means；正式邮件可用 Consequently。",
        "instances": [
          {
            "wrong": "Then DSD-45874 is not urgent",
            "right": "So DSD-45874 is not urgent"
          }
        ],
        "examples": [
          {
            "wrong": "Then we can delay the release.",
            "right": "So we can delay the release."
          }
        ]
      }
    ]
  }
}
```

### C-09（耗时 6.1s）

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
        "explanation": "some 修饰可数名词时需用复数形式，log 应为 logs。",
        "correction": "there are some error logs"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "triggering dag",
        "explanation": "dag 是可数名词单数，此处泛指触发 DAG 这一动作，需加不定冠词 a 或使用复数。",
        "correction": "triggering a DAG"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error logs when triggering a DAG.",
        "explanation": "仅修正语法错误，保留原句结构和语气。"
      },
      "natural": {
        "text": "BTW, it's easier to check the running worker and scheduler pods. That helps if you see any error logs when triggering a DAG.",
        "explanation": "用 BTW 和缩写更贴合 Slack/IM 风格；将两个 pod 合并为 pods 更简洁；see any error logs 比 there are some error logs 更自然。"
      }
    },
    "learnings": [
      {
        "title": "some 修饰可数名词需用复数",
        "rule": "some 后接可数名词时必须使用复数形式，不可用单数。",
        "instances": [
          {
            "wrong": "some error log",
            "right": "some error logs"
          }
        ],
        "examples": [
          {
            "wrong": "There are some issue.",
            "right": "There are some issues."
          }
        ]
      },
      {
        "title": "可数名词单数需限定词",
        "rule": "可数名词单数在句中不能裸用，需加冠词（a/an/the）或变为复数。DAG 作为可数技术术语同理。",
        "instances": [
          {
            "wrong": "triggering dag",
            "right": "triggering a DAG"
          }
        ],
        "examples": [
          {
            "wrong": "when deploying service",
            "right": "when deploying a service"
          }
        ]
      }
    ]
  }
}
```
