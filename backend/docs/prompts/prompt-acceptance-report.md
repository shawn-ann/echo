# 提示词输出采集报告（Prompt Output Report）

- **模型**：`deepseek-v4-flash`
- **场景**：casual（日常/职场口语）
- **用例数**：9
- **总耗时**：419.4 秒

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

### C-01（耗时 19.8s）

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
        "error_type": "词性误用",
        "fragment": "set up logic",
        "explanation": "set up 是动词短语，此处修饰 logic 应使用名词形式 setup（一个词），表示“配置/设置逻辑”。",
        "correction": "setup logic"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "creating job",
        "explanation": "job 是可数名词单数，被泛指时不能裸用，需加不定冠词 a。",
        "correction": "creating a job"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Correct the `trigger_by` field setup logic when creating a job.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "When creating a job, fix the logic that sets up the `trigger_by` field.",
        "explanation": "调整语序并直接用 sets up 表达配置动作，读起来更符合日常技术沟通习惯。"
      }
    },
    "learnings": [
      {
        "title": "动词短语作定语需用名词形式",
        "rule": "set up 是动词短语，作名词修饰语时应用名词形式 setup（一个词），表示“设置、配置”。",
        "instances": [
          {
            "wrong": "set up logic",
            "right": "setup logic"
          }
        ],
        "examples": [
          {
            "wrong": "field set up logic",
            "right": "field setup logic"
          }
        ]
      },
      {
        "title": "可数名词单数需加冠词",
        "rule": "单数可数名词如 job 在泛指时需加不定冠词 a/an，不能直接使用原形。",
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
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-02（耗时 5.0s）

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

### C-03（耗时 63.0s）

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
        "fragment": "of `GDSP` cluster",
        "explanation": "GDSP 作为专有名称修饰 cluster 时，前面仍需冠词，应为 of the GDSP cluster。",
        "correction": "of the `GDSP` cluster"
      },
      {
        "category": "style",
        "error_type": "中英混用",
        "fragment": "egress IP(出网ip)",
        "explanation": "英文消息中插入中文注释会造成中英混用，影响英文读者理解；egress IP 本身是标准技术术语，应删除中文注释。",
        "correction": "egress IP"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "In that case, the egress IP of the `GDSP` cluster should be enough, right?",
        "explanation": "仅修正冠词并删除中文注释，保留原句结构和语气"
      },
      "natural": {
        "text": "In that case, the `GDSP` cluster's egress IP should be enough, right?",
        "explanation": "用所属关系 the cluster's egress IP 表达更简洁自然，符合日常技术聊天语气。"
      }
    },
    "learnings": [
      {
        "title": "专有名词修饰普通名词仍需冠词",
        "rule": "当专有名词（如 `GDSP`）修饰普通名词（如 cluster）时，普通名词前仍需按语法加相应冠词，即 the `GDSP` cluster，不能省略为 `GDSP` cluster。",
        "instances": [
          {
            "wrong": "of GDSP cluster",
            "right": "of the GDSP cluster"
          }
        ],
        "examples": [
          {
            "wrong": "I will check with DevOps team first.",
            "right": "I will check with the DevOps team first."
          },
          {
            "wrong": "The issue happens in production env.",
            "right": "The issue happens in the production environment."
          }
        ]
      },
      {
        "title": "英文交流中避免中英混用",
        "rule": "英文技术消息中不要插入中文注释；如需解释术语，可单独用中文补充，或在英文中使用英文同义说明。",
        "instances": [
          {
            "wrong": "egress IP(出网ip)",
            "right": "egress IP"
          }
        ],
        "examples": [
          {
            "wrong": "The job is stuck in pending(排队中).",
            "right": "The job is stuck in pending."
          },
          {
            "wrong": "Please approve the PR(合并请求) today.",
            "right": "Please approve the PR today."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-04（耗时 9.2s）

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
        "explanation": "resource pool 是可数名词单数，泛指时前面应有冠词 a，不能用裸名词。",
        "correction": "adding a resource pool"
      },
      {
        "category": "grammar",
        "error_type": "不可数名词误用",
        "fragment": "How many storage",
        "explanation": "storage 是不可数名词，询问数量时应用 how much，不能用 how many。",
        "correction": "How much storage"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "This pvc should be created when adding a resource pool. How much storage do we want?",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "This PVC should be created when we add a resource pool. How much storage do we want?",
        "explanation": "用完整从句 when we add 替代分词结构，读起来更自然；PVC 大写更符合技术缩写惯例。"
      }
    },
    "learnings": [
      {
        "title": "可数名词单数需加冠词",
        "rule": "可数名词单数在泛指或首次提及时，前面须加冠词 a/an 或 the。",
        "instances": [
          {
            "wrong": "adding resource pool",
            "right": "adding a resource pool"
          }
        ],
        "examples": [
          {
            "wrong": "When adding resource pool, ...",
            "right": "When adding a resource pool, ..."
          }
        ]
      },
      {
        "title": "不可数名词用 how much",
        "rule": "不可数名词（如 storage、information、water）不能与 how many 连用，表示数量时应使用 how much。",
        "instances": [
          {
            "wrong": "How many storage do we want?",
            "right": "How much storage do we want?"
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

### C-05（耗时 90.6s）

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
        "explanation": "不定式 to 后应接动词原形，finished 是过去分词，应改为 finish。",
        "correction": "to finish"
      },
      {
        "category": "collocation",
        "error_type": "介词搭配不当",
        "fragment": "by this week",
        "explanation": "表示“截止本周”更自然的说法是 by the end of this week；by this week 不符合英语习惯。口语中也可直接用 this week。",
        "correction": "by the end of this week"
      },
      {
        "category": "grammar",
        "error_type": "拼写错误",
        "fragment": "ariflow",
        "explanation": "airflow 拼写错误，注意字母顺序。",
        "correction": "airflow"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "logs is",
        "explanation": "logs 是复数名词，谓语动词应用 are 而不是 is。",
        "correction": "logs are"
      },
      {
        "category": "collocation",
        "error_type": "搭配冗余",
        "fragment": "empty issue",
        "explanation": "句首已有 the issue that，句末再出现 issue 造成重复冗余，应删除。",
        "correction": "empty"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Is it possible to finish the testing for `https://jira.rakuten-it.com/jira/browse/DSD-45874` and release it by the end of this week? This would fix the issue that airflow worker/scheduler logs are empty.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Can we finish the testing for `https://jira.rakuten-it.com/jira/browse/DSD-45874` and release it this week? That would fix the issue with the airflow worker/scheduler logs being empty.",
        "explanation": "用 Can we 更口语化，that 指代前句，with ... being empty 比 the issue that ... are empty 更简洁自然。"
      }
    },
    "learnings": [
      {
        "title": "不定式后接动词原形",
        "rule": "to 是不定式标志，后面必须接动词原形，不能接过去分词或进行时。",
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
        "title": "时间状语搭配",
        "rule": "表示“截止本周”用 by the end of this week；表示“本周内”用 this week。不要直接写 by this week。",
        "instances": [
          {
            "wrong": "by this week",
            "right": "by the end of this week"
          }
        ],
        "examples": [
          {
            "wrong": "Please submit it by this week.",
            "right": "Please submit it by the end of this week."
          }
        ]
      },
      {
        "title": "Airflow 拼写",
        "rule": "airflow 是 Apache 工作流平台专有名词，拼写为 airflow，注意字母顺序，不要写成 ariflow。",
        "instances": [
          {
            "wrong": "ariflow",
            "right": "airflow"
          }
        ],
        "examples": [
          {
            "wrong": "ariflow DAG",
            "right": "airflow DAG"
          }
        ]
      },
      {
        "title": "复数主语搭配复数谓语",
        "rule": "可数名词复数作主语时，谓语动词用复数形式。logs 是复数，be 动词应用 are。",
        "instances": [
          {
            "wrong": "logs is empty",
            "right": "logs are empty"
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
        "title": "避免语义重复",
        "rule": "当句首已用 the issue that 引导从句时，句末不要再重复 issue，以免冗余。",
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
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-06（耗时 67.3s）

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
        "fragment": "late response, we are",
        "explanation": "逗号不能连接两个独立分句；'Sorry for the late response' 和 'we are working...' 是两个完整句子，应用句号或分号分隔。",
        "correction": "late response. We are"
      },
      {
        "category": "grammar",
        "error_type": "逗号拼接",
        "fragment": "release operation, the restart",
        "explanation": "逗号不能连接两个独立分句；'we are working on the release operation' 和 'the restart function should work now' 是两个独立分句。",
        "correction": "release operation. The restart"
      },
      {
        "category": "grammar",
        "error_type": "逗号拼接",
        "fragment": "work now, please check",
        "explanation": "逗号不能连接两个独立分句；'the restart function should work now' 和 'please check' 是两个独立分句。",
        "correction": "work now. Please check"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Sorry for the late response. We are working on the release operation. The restart function should work now. Please check.",
        "explanation": "仅修正逗号拼接，将逗号改为句号并大写后续句首，保留原句结构和语气。"
      },
      "natural": {
        "text": "Sorry for the late reply. We're working on the release. The restart should work now — please check.",
        "explanation": "使用更口语化的 late reply 和缩写 we're，并用破折号连接最后一句，更贴近 Slack/IM 日常沟通。"
      }
    },
    "learnings": [
      {
        "title": "逗号不能连接独立分句",
        "rule": "两个独立分句之间不能只用逗号连接，应使用句号、分号或并列/从属连词。在口语聊天中即使常见，也应视为标点错误。",
        "instances": [
          {
            "wrong": "Sorry for the late response, we are working on the release operation.",
            "right": "Sorry for the late response. We are working on the release operation."
          },
          {
            "wrong": "We are working on the release operation, the restart function should work now.",
            "right": "We are working on the release operation. The restart function should work now."
          },
          {
            "wrong": "The restart function should work now, please check.",
            "right": "The restart function should work now. Please check."
          }
        ],
        "examples": [
          {
            "wrong": "I finished the task, I will send the report.",
            "right": "I finished the task. I will send the report."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-07（耗时 20.8s）

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
        "explanation": "issue 表示“关于……的问题”时，后接名词短语必须用介词 with 连接，不能直接并列。",
        "correction": "The issue with the airflow instance log"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "have been fixed",
        "explanation": "主语 The issue 是单数，完成时助动词应为 has，have 用于复数主语、I 或 you。",
        "correction": "has been fixed"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The issue with the airflow instance log has been fixed. Could you please create a new airflow instance instead? The log viewer and download should be real quick.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "The airflow instance log issue is fixed — could you spin up a new airflow instance instead? Viewing and downloading logs should be pretty quick.",
        "explanation": "用 is fixed 更简洁，spin up 是创建实例时常用的口语化说法，Viewing and downloading logs 比名词短语更自然。"
      }
    },
    "learnings": [
      {
        "title": "issue 后接名词需加介词 with",
        "rule": "当 issue 表示“关于……的问题”时，后接名词短语需要加介词 with 连接，不能直接并列。",
        "instances": [
          {
            "wrong": "The issue airflow instance log",
            "right": "The issue with the airflow instance log"
          }
        ],
        "examples": [
          {
            "wrong": "The issue disk space has been solved.",
            "right": "The issue with disk space has been solved."
          }
        ]
      },
      {
        "title": "单数主语用 has 而非 have",
        "rule": "主语为第三人称单数（如 the issue）时，完成时助动词用 has，不能用 have；have 用于复数主语、I 或 you。",
        "instances": [
          {
            "wrong": "The issue have been fixed",
            "right": "The issue has been fixed"
          }
        ],
        "examples": [
          {
            "wrong": "The problem have been solved.",
            "right": "The problem has been solved."
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-08（耗时 67.3s）

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
        "fragment": "The empty log issue in PROD has been resolved now, I suspect",
        "explanation": "两个独立分句（The empty log issue ... has been resolved now 与 I suspect ...）用逗号直接连接，构成逗号拼接，应改用句号或加连接词。",
        "correction": "The empty log issue in PROD has been resolved now. I suspect"
      },
      {
        "category": "grammar",
        "error_type": "词序不当",
        "fragment": "the DB missing column",
        "explanation": "修饰语 missing 应紧挨名词 column，并用介词短语表示所属关系，the DB missing column 应为 the missing column in the DB。",
        "correction": "the missing column in the DB"
      },
      {
        "category": "grammar",
        "error_type": "逗号拼接",
        "fragment": "DSD-45874 is not urgent now, we can release",
        "explanation": "两个独立分句（DSD-45874 is not urgent now 与 we can release ...）用逗号连接，构成逗号拼接，应改用句号或加 so。",
        "correction": "DSD-45874 is not urgent now. We can release"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The empty log issue in PROD has been resolved now. I suspect this is also caused by the missing column in the DB. Then DSD-45874 is not urgent now. We can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "仅修正逗号拼接和词序问题，保留原句结构和语气。"
      },
      "natural": {
        "text": "The empty log issue in PROD is now resolved. I suspect it's also caused by the missing column in the DB. So DSD-45874 isn't urgent anymore, and we can release both DSD-45874 & DSD-45252 next week.",
        "explanation": "用 is now resolved 更简洁，it's 缩写和 so 更口语化，isn't urgent anymore 比 is not urgent now 更自然，整体更符合 Slack 聊天场景。"
      }
    },
    "learnings": [
      {
        "title": "独立分句不能用逗号直接连接",
        "rule": "两个独立的完整分句在英语中不能只用逗号连接（逗号拼接），应使用句号、分号或并列连接词（如 so、and）。",
        "instances": [
          {
            "wrong": "The empty log issue in PROD has been resolved now, I suspect",
            "right": "The empty log issue in PROD has been resolved now. I suspect"
          },
          {
            "wrong": "DSD-45874 is not urgent now, we can release",
            "right": "DSD-45874 is not urgent now. We can release"
          }
        ],
        "examples": [
          {
            "wrong": "The deployment is done, we can proceed.",
            "right": "The deployment is done, so we can proceed."
          }
        ]
      },
      {
        "title": "名词修饰语顺序",
        "rule": "当一个名词带有形容词修饰语和所属名词时，形容词应紧挨名词，所属关系用介词短语表达。如 the DB missing column 应说 the missing column in the DB。",
        "instances": [
          {
            "wrong": "the DB missing column",
            "right": "the missing column in the DB"
          }
        ],
        "examples": [
          {
            "wrong": "the database missing row",
            "right": "the missing row in the database"
          }
        ]
      }
    ]
  },
  "reply": null
}
```

### C-09（耗时 76.4s）

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
        "fragment": "some error log",
        "explanation": "there are 是复数形式，后接的可数名词也应为复数；error log 应写作 error logs，否则与 are 不一致。",
        "correction": "some error logs"
      },
      {
        "category": "grammar",
        "error_type": "冠词缺失",
        "fragment": "when triggering dag",
        "explanation": "triggering 是及物动词，后接名词 dag 作宾语时需加冠词；`dag` 为 Airflow 领域术语，保留原书写形式，但冠词仍不可省略。",
        "correction": "when triggering the dag"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error logs when triggering the dag.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "By the way, you could also check the running worker and scheduler pod logs — that's helpful if there are any error logs when you trigger the dag.",
        "explanation": "把“更容易地检查 pod”改为更明确的“查看 pod 日志”；用 that's helpful 更口语直接；when you trigger 比 when triggering 更贴近日常技术聊天。"
      }
    },
    "learnings": [
      {
        "title": "there be 句型的主谓一致",
        "rule": "there are 后接可数名词时，名词必须用复数形式，与 be 动词保持单复数一致；条件句（if）中表示“任何”时用 any 比 some 更自然。",
        "instances": [
          {
            "wrong": "there are some error log",
            "right": "there are some error logs"
          }
        ],
        "examples": [
          {
            "wrong": "There are some error log in the log file.",
            "right": "There are some error logs in the log file."
          }
        ]
      },
      {
        "title": "动词宾语前需要冠词",
        "rule": "及物动词（如 trigger）后接名词作宾语时，名词前需要加冠词 the 或 a/an，不能省略；即使是领域术语（如 `dag`）也要遵守冠词规则。",
        "instances": [
          {
            "wrong": "when triggering dag",
            "right": "when triggering the dag"
          }
        ],
        "examples": [
          {
            "wrong": "The task fails when triggering dag.",
            "right": "The task fails when triggering the dag."
          }
        ]
      }
    ]
  },
  "reply": null
}
```
