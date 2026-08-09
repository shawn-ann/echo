# 提示词输出采集报告（Prompt Output Report）

- **模型**：`deepseek-v4-flash`
- **用例数**：9
- **总耗时**：442.4 秒

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
    "rule": "规则说明（中文）",
    "instances": [{"wrong": "错误写法（英文）", "right": "正确写法（英文）"}],
    "examples": ["英文例句1~2条，含 ❌ → ✅"]}]}

## 关键约束
- 改写两版（minimal/natural）必须互不相同；natural 提供一条比 minimal 更自然的整句改写，风格按上下文选择（正式或口语均可）
- 技术术语、产品名、版本号、工单链接（如 trigger_by、airflow、DSD-45874、pvc、Jira 链接）必须原样保留，不得改写或翻译，展示时用反引号包裹
- 区分"中式直译"（表达在英语中不存在或不自然）与"语域错配"（合法英语但与当前语境正式程度不符）；error_type 相应标注
- 典型中式直译必须识别并修正，如：release operation → release / release process；deploy operation → deployment；do some customize → do some customization；open the light → turn on the light
- category 与 error_type 一致：冠词缺失/时态错误/主谓不一致/不可数名词误用 → grammar；中式直译 → chinglish；语域错配 → style；其余用词/搭配问题 → collocation 或 style
- 无法确定作者意图的表达不列为修正项，不臆测改写
- 无错误 → has_errors=false，errors 与 learnings 为空，minimal 与 natural 两版 text 均为原句、explanation 为空字符串
- 每个不同规则归纳一条 learning；同类错误的多个实例合并到同一条 learning 的 instances 数组
- error_type、explanation、title、rule、examples 用中文；fragment、correction、instances 的 wrong/right、rewrite 的 text 保持英文

## 返回格式（严格遵守字段名）
{"intent": "correction", "correction": {"has_errors": ..., "errors": [...], "rewrite": {"minimal": {...}, "natural": {...}}, "learnings": [...]}, "reply": null}

```

## 二、测试用例与实际输出

### C-01（耗时 13.6s）

**输入**：Correct the trigger_by field set up logic when creating job.

**输出**：

```json
{"intent":"correction","correction":{"has_errors":true,"errors":[{"category":"collocation","error_type":"词性误用","fragment":"field set up logic","explanation":"set up 是动词短语，放在名词前作定语修饰 logic 时，应使用名词形式 setup，构成名词短语 field setup logic（字段配置逻辑）。","correction":"field setup logic"},{"category":"grammar","error_type":"冠词缺失","fragment":"creating job","explanation":"job 是可数名词单数，前面需要加冠词 a，表示“创建一项作业”。","correction":"creating a job"}],"rewrite":{"minimal":{"text":"Correct the `trigger_by` field setup logic when creating a job.","explanation":"仅修正 set up 为 setup，并为 job 添加冠词 a，保留原句结构和语气。"},"natural":{"text":"When creating a job, fix the logic used to set up the `trigger_by` field.","explanation":"调整语序并改用更自然的表达 fix the logic used to...，使句子更符合英文习惯；同时保留 trigger_by 字段名。"}},"learnings":[{"title":"动词短语作名词修饰语时应改用名词形式","rule":"set up 是动词短语，表示名词概念时应用名词/形容词形式 setup，例如 field setup logic（字段配置逻辑），不能写成 field set up logic。","instances":[{"wrong":"field set up logic","right":"field setup logic"}],"examples":["❌ Please review the system set up procedure. → ✅ Please review the system setup procedure."]},{"title":"单数可数名词前要用冠词","rule":"可数名词单数形式通常需要冠词 a/an/the 或限定词。例如 creating a job 这里需要不定冠词 a，不能省略。","instances":[{"wrong":"creating job","right":"creating a job"}],"examples":["❌ When creating job, check the trigger field. → ✅ When creating a job, check the trigger field."]}]},"reply":null}
```

### C-02（耗时 21.1s）

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
        "error_type": "缺少be动词",
        "fragment": "getting an error?",
        "explanation": "独立疑问句缺少主语和be动词，口语省略在书面语中不完整。",
        "correction": "Are you getting an error?"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "What do you mean you can't restart this webapp? Are you getting an error?",
        "explanation": "仅将省略的问句补充完整，保留原句结构和口语化语气。"
      },
      "natural": {
        "text": "Wait, what do you mean you can't restart this webapp? Are you seeing an error?",
        "explanation": "增加了语气词'Wait'以表达惊讶，并用'seeing'形容看到错误信息，更符合口语习惯。"
      }
    },
    "learnings": [
      {
        "title": "独立疑问句不能省略be动词",
        "rule": "当单独提出一个问题时，必须使用完整的主谓结构，例如'Are you...?'，不能只用现在分词形式。",
        "instances": [
          {"wrong": "Getting an error?", "right": "Are you getting an error?"}
        ],
        "examples": [
          "❌ Getting an error? → ✅ Are you getting an error?",
          "❌ Coming to the meeting? → ✅ Are you coming to the meeting?"
        ]
      }
    ]
  },
  "reply": null
}
```

### C-03（耗时 35.8s）

**输入**：In that case, the egress IP(出网ip) of GDSP cluster should be enough, right?

**输出**：

```json
{"intent":"correction","correction":{"has_errors":true,"errors":[{"category":"grammar","error_type":"冠词缺失","fragment":"GDSP cluster","explanation":"GDSP 是特指的集群名称，英文中特指某个集群时，名词前需要加定冠词 the。","correction":"the `GDSP` cluster"},{"category":"style","error_type":"中英混排","fragment":"egress IP(出网ip)","explanation":"纯英文表达中不应夹带中文注释；若需解释术语，可用英文括号写 (outbound IP) 或直接删去。","correction":"egress IP"}],"rewrite":{"minimal":{"text":"In that case, the egress IP of the `GDSP` cluster should be enough, right?","explanation":"仅补上冠词 the 并移除中文括号注释，保留原句结构和语气。"},"natural":{"text":"In that case, the egress IP of the `GDSP` cluster should suffice, right?","explanation":"用 suffice 替换 be enough 更精练、正式，符合技术讨论的语境。"}},"learnings":[{"title":"特指的集群/系统名称前要加定冠词 the","rule":"当一个名词指的是某个具体、上下文中明确的集群或系统时，前面必须加 the；不加 the 通常表示泛指或复数。","instances":[{"wrong":"the egress IP of GDSP cluster","right":"the egress IP of the `GDSP` cluster"},{"wrong":"deploy to staging cluster first","right":"deploy to the staging cluster first"}],"examples":["❌ Please restart `airflow` cluster after the change. → ✅ Please restart the `airflow` cluster after the change.","❌ The issue only happens on staging cluster. → ✅ The issue only happens on the staging cluster."]},{"title":"英文表达中不要夹带中文注释","rule":"写给英文读者的句子应保持纯英文；需要解释术语时使用英文括号，如 egress IP (outbound IP)，或者干脆省略。","instances":[{"wrong":"egress IP(出网ip)","right":"egress IP"},{"wrong":"check the firewall(防火墙) rules","right":"check the firewall rules"}],"examples":["❌ The SRE team(运维) will handle it. → ✅ The SRE team will handle it.","❌ Please update the `pvc`(存储) usage. → ✅ Please update the `pvc` usage."]}]},"reply":null}
```

### C-04（耗时 17.6s）

**输入**：This pvc should be created when adding resource pool. How many storage do we want?

**输出**：

```json
{"intent": "correction", "correction": {"has_errors": true, "errors": [{"category": "grammar", "error_type": "冠词缺失", "fragment": "adding resource pool", "explanation": "resource pool 为可数名词单数，此处泛指一个资源池，前面需要加不定冠词 a。", "correction": "adding a resource pool"}, {"category": "grammar", "error_type": "不可数名词误用", "fragment": "How many storage", "explanation": "storage 为不可数名词，不能用 many 修饰，应使用 much 提问数量。", "correction": "How much storage"}], "rewrite": {"minimal": {"text": "This `pvc` should be created when adding a resource pool. How much storage do we want?", "explanation": "仅修正冠词缺失和不可数名词误用，保留原句结构和语气。"}, "natural": {"text": "This `pvc` should be created when a resource pool is added. How much storage do we need?", "explanation": "将 when adding 改为 when a resource pool is added 更符合技术文档中常见的被动/完成式表达；do we want 改为 do we need 更自然。"}}, "learnings": [{"title": "可数名词单数前需要冠词", "rule": "resource pool 是可数名词单数，在泛指语境下需加 a/an，特指时用 the。", "instances": [{"wrong": "adding resource pool", "right": "adding a resource pool"}], "examples": ["❌ The pod should run when adding resource pool. → ✅ The pod should run when adding a resource pool."]}, {"title": "不可数名词用 much 修饰", "rule": "storage 是不可数名词，表示数量多少时使用 how much，不用 how many。", "instances": [{"wrong": "How many storage", "right": "How much storage"}], "examples": ["❌ How many storage do we need? → ✅ How much storage do we need?"]}]}, "reply": null}
```

### C-05（耗时 50.6s）

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
        "explanation": "possible to 后面的动词需要用原形，finished 是过去式/过去分词，应改为 finish。",
        "correction": "to finish"
      },
      {
        "category": "collocation",
        "error_type": "介词搭配不当",
        "fragment": "by this week",
        "explanation": "要表达“本周末之前”，英文常用 by the end of this week；by this week 搭配不自然且含义模糊。",
        "correction": "by the end of this week"
      },
      {
        "category": "grammar",
        "error_type": "拼写错误",
        "fragment": "ariflow",
        "explanation": "Airflow 是专有名词，拼写固定为 airflow，不能写成 ariflow。",
        "correction": "airflow"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "logs is",
        "explanation": "logs 是复数主语，be 动词应使用 are。",
        "correction": "logs are"
      },
      {
        "category": "collocation",
        "error_type": "搭配冗余",
        "fragment": "empty issue",
        "explanation": "前面已有 the issue that 引导从句，句末的 issue 重复，应删掉，保留 empty 即可。",
        "correction": "empty"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "Is it possible to finish the testing for `https://jira.rakuten-it.com/jira/browse/DSD-45874` and release it by the end of this week? This would fix the issue that `airflow` worker/scheduler logs are empty.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "Could we finish testing for `https://jira.rakuten-it.com/jira/browse/DSD-45874` and get it released by the end of this week? That would resolve the issue of `airflow` worker/scheduler logs being empty.",
        "explanation": "使用 Could we 更显协作和礼貌，省略 the 让表达更自然，get it released 体现完成发布流程，the issue of ... being empty 比 that 从句更简洁地道。"
      }
    },
    "learnings": [
      {
        "title": "不定式后接动词原形",
        "rule": "在 possible to ... 结构中，to 后面必须使用动词原形，不能用过去式或过去分词。",
        "instances": [
          {
            "wrong": "to finished",
            "right": "to finish"
          }
        ],
        "examples": [
          "❌ Is it possible to completed the task by Friday? → ✅ Is it possible to complete the task by Friday?"
        ]
      },
      {
        "title": "表示“本周末之前”用 by the end of this week",
        "rule": "表达截止时间时，by 后通常接具体时间点或期限；by this week 不够规范自然。",
        "instances": [
          {
            "wrong": "by this week",
            "right": "by the end of this week"
          }
        ],
        "examples": [
          "❌ Please submit the report by this week. → ✅ Please submit the report by the end of this week."
        ]
      },
      {
        "title": "注意技术专有名词拼写",
        "rule": "Airflow 是 Apache 工作流调度平台，拼写固定为 airflow，不能写成 ariflow。",
        "instances": [
          {
            "wrong": "ariflow",
            "right": "airflow"
          }
        ],
        "examples": [
          "❌ The ariflow DAG failed to run. → ✅ The airflow DAG failed to run."
        ]
      },
      {
        "title": "复数主语搭配复数谓语",
        "rule": "logs（日志）是复数名词，be 动词用 are，而不是 is。",
        "instances": [
          {
            "wrong": "logs is empty",
            "right": "logs are empty"
          }
        ],
        "examples": [
          "❌ The logs is empty. → ✅ The logs are empty."
        ]
      },
      {
        "title": "避免名词重复",
        "rule": "已用 the issue that ... 引导问题后，句末不应再重复 issue，直接陈述内容即可。",
        "instances": [
          {
            "wrong": "the issue that logs are empty issue",
            "right": "the issue that logs are empty"
          }
        ],
        "examples": [
          "❌ We need to fix the issue that the app crashes issue. → ✅ We need to fix the issue that the app crashes."
        ]
      }
    ]
  },
  "reply": null
}
```

### C-06（耗时 59.7s）

**输入**：Sorry for the late response, we are working on the release operation, the restart function should work now, please check.

**输出**：

```json
{"intent":"correction","correction":{"has_errors":true,"errors":[{"category":"grammar","error_type":"逗号拼接（run-on sentence）","fragment":"Sorry for the late response, we are working on the release operation, the restart function should work now, please check","explanation":"整个句子由多个独立分句组成，中间都用逗号连接，形成 run-on sentence。英语中并列的独立分句需要用句号、分号或连词分隔。","correction":"Sorry for the late response. We are working on the release operation; the restart function should work now. Please check"},{"category":"chinglish","error_type":"中式直译","fragment":"release operation","explanation":"'release operation' 是中文“发布操作”的直译，英语中更自然的表达是 'release' 或 'release process'。operation 单独使用多指手术、军事行动等。","correction":"release process"}],"rewrite":{"minimal":{"text":"Sorry for the late response. We are working on the release process, and the restart function should work now. Please check.","explanation":"仅修正逗号拼接，并将 release operation 改为 release process，保留原句结构和语气。"},"natural":{"text":"Sorry for the delayed response—we're working on the release right now, so the restart function should be working. Could you please check it?","explanation":"将 late response 改为 delayed response 更正式自然；用 right now 和 so 使前后因果更清晰；用 could you please 代替 please check，语气更礼貌。"}},"learnings":[{"title":"逗号不能连接两个独立句子","rule":"两个都能独立成句的分句不能仅用逗号连接（comma splice），应改用句号、分号，或添加 and/but/so 等连词。","instances":[{"wrong":"we are working on the release, the restart function should work now","right":"we are working on the release; the restart function should work now"},{"wrong":"Sorry for the late response, we are working on the release","right":"Sorry for the late response. We are working on the release"}],"examples":["❌ I was tired, I went to bed. → ✅ I was tired; I went to bed. / I was tired, so I went to bed."]},{"title":"避免中式直译“operation”","rule":"描述软件发布时，不要将“发布操作”直译为 release operation。英语中更常说 release 或 release process。","instances":[{"wrong":"we are working on the release operation","right":"we are working on the release process"}],"examples":["❌ We are working on the release operation. → ✅ We are working on the release process."]}]},"reply":null}
```

### C-07（耗时 54.5s）

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
        "fragment": "The issue `airflow` instance log",
        "explanation": "表达“关于…的问题”时，`issue` 后需要介词 with，这里缺少介词导致结构不完整。",
        "correction": "The issue with the `airflow` instance log"
      },
      {
        "category": "grammar",
        "error_type": "主谓不一致",
        "fragment": "have been fixed",
        "explanation": "主语 The issue 为单数，谓语应用 has 而不是 have。",
        "correction": "has been fixed"
      },
      {
        "category": "grammar",
        "error_type": "逗号拼接",
        "fragment": "fixed, could",
        "explanation": "两个独立分句不能用逗号直接连接，应改为句号、分号或使用连接词。",
        "correction": "fixed. Could"
      },
      {
        "category": "style",
        "error_type": "语域错配",
        "fragment": "real quick",
        "explanation": "`real` 为口语化的副词用法，在职场书面语中不够正式，应改为 `really` 或 `very`。",
        "correction": "really quick"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The issue with the `airflow` instance log has been fixed. Could you please create a new `airflow` instance instead? The log viewer and download should be really quick.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "The `airflow` instance log issue has been fixed. Could you please create a new `airflow` instance instead? The log viewer and download should be very quick.",
        "explanation": "将“The issue with...”改为“The `airflow` instance log issue”，更简洁自然；用“very quick”比“really quick”更正式稳妥。"
      }
    },
    "learnings": [
      {
        "title": "表达“关于…的问题”时，issue 后接 with",
        "rule": "当 issue 表示“问题”时，若后接对象，应在 issue 后加介词 with（或 about/regarding），构成 the issue with/ about...。",
        "instances": [
          {
            "wrong": "the issue `airflow` instance log",
            "right": "the issue with the `airflow` instance log"
          },
          {
            "wrong": "the issue deployment",
            "right": "the issue with the deployment"
          }
        ],
        "examples": [
          "❌ The issue `airflow` instance log has been fixed. → ✅ The issue with the `airflow` instance log has been fixed."
        ]
      },
      {
        "title": "单数主语搭配单数谓语",
        "rule": "主语为单数时，一般现在时或现在完成时中谓语动词要用第三人称单数形式，即 has 而不是 have。",
        "instances": [
          {
            "wrong": "The issue have been fixed",
            "right": "The issue has been fixed"
          },
          {
            "wrong": "The log have been checked",
            "right": "The log has been checked"
          }
        ],
        "examples": [
          "❌ The issue have been fixed. → ✅ The issue has been fixed."
        ]
      },
      {
        "title": "两个完整分句不能用逗号直接连接",
        "rule": "两个独立的完整句子之间需用句号、分号或连接词（and, but 等）连接，不能用逗号。",
        "instances": [
          {
            "wrong": "It is fixed, could you check it?",
            "right": "It is fixed. Could you check it?"
          },
          {
            "wrong": "I came, I saw",
            "right": "I came; I saw."
          }
        ],
        "examples": [
          "❌ The issue is fixed, could you create a new instance? → ✅ The issue is fixed. Could you create a new instance?"
        ]
      },
      {
        "title": "正式书面语中避免使用 real 作副词",
        "rule": "在职场邮件等正式场景中，修饰形容词或副词时应用 exactly/very/really 等标准副词，避免口语化的 real。",
        "instances": [
          {
            "wrong": "It should be real quick.",
            "right": "It should be really quick."
          },
          {
            "wrong": "That was real good.",
            "right": "That was really good."
          }
        ],
        "examples": [
          "❌ The process is real fast. → ✅ The process is really fast."
        ]
      }
    ]
  },
  "reply": null
}
```

### C-08（耗时 96.8s）

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
        "explanation": "两个独立分句（The issue has been resolved now / I suspect...）之间不能只用逗号连接，应使用句号或并列连词。",
        "correction": "resolved now. I suspect"
      },
      {
        "category": "grammar",
        "error_type": "时态错误",
        "fragment": "this is also caused",
        "explanation": "这里指过去某个问题产生的原因，应用一般过去时 was caused，而不是一般现在时 is caused。",
        "correction": "this was also caused"
      },
      {
        "category": "collocation",
        "error_type": "搭配不当",
        "fragment": "the `DB` missing column",
        "explanation": "表达'数据库缺少的一列'，英文约定俗成用 a missing column in the `DB` 或 the `DB` missing a column，原短语 the `DB` missing column 结构不正确。",
        "correction": "a missing column in the `DB`"
      },
      {
        "category": "grammar",
        "error_type": "逗号拼接",
        "fragment": "urgent now, we can",
        "explanation": "同样，两个独立分句之间不能只用逗号连接，应断句或加连词。",
        "correction": "urgent now. We can"
      },
      {
        "category": "chinglish",
        "error_type": "中式直译",
        "fragment": "Then",
        "explanation": "这里 'Then' 是中文'那么'的直译，在英语中引出结论更自然的说法是 'So' 或 'Therefore'。",
        "correction": "So"
      }
    ],
    "rewrite": {
      "minimal": {
        "text": "The empty log issue in `PROD` has been resolved now. I suspect this was also caused by a missing column in the `DB`. So `DSD-45874` is not urgent now. We can release both `DSD-45874` & `DSD-45252` next week.",
        "explanation": "仅修正语法和用词，保留原句结构和语气"
      },
      "natural": {
        "text": "The empty log issue in `PROD` has now been resolved. I suspect it was also caused by a missing column in the `DB`. `DSD-45874` is therefore no longer urgent, and we can release both `DSD-45874` and `DSD-45252` next week.",
        "explanation": "使用 has now been resolved 使完成时与 now 的搭配更自然；用 it 指代前文问题，避免重复；therefore 与 no longer urgent 使逻辑衔接更流畅。最后用 and 连接两个发布对象，更正式。"
      }
    },
    "learnings": [
      {
        "title": "避免逗号拼接（comma splice）",
        "rule": "两个独立分句不能仅用逗号连接，应使用句号、分号或添加并列连词（and/so/but）。",
        "instances": [
          {
            "wrong": "The issue has been resolved now, I suspect...",
            "right": "The issue has been resolved now. I suspect..."
          },
          {
            "wrong": "It is not urgent now, we can release...",
            "right": "It is not urgent now. We can release..."
          }
        ],
        "examples": [
          "❌ It's raining, we should stay home. → ✅ It's raining. We should stay home.",
          "❌ The task is done, we can start the next one. → ✅ The task is done, so we can start the next one."
        ]
      },
      {
        "title": "描述过去原因应用一般过去时",
        "rule": "当说明某个已发生问题的原因时，动词使用一般过去时（was caused），而非一般现在时（is caused）。",
        "instances": [
          {
            "wrong": "this is also caused by",
            "right": "this was also caused by"
          }
        ],
        "examples": [
          "❌ The error is caused by a missing config, which I found yesterday. → ✅ The error was caused by a missing config, which I found yesterday."
        ]
      },
      {
        "title": "表达'数据库缺少的一列'的正确搭配",
        "rule": "表示某物缺少某部分，常用 'a missing + 部分 + in + 整体' 或用动名词结构 '整体 + missing + 部分'，不要写成 '整体 + missing + 部分' 直接作名词短语。",
        "instances": [
          {
            "wrong": "the `DB` missing column",
            "right": "a missing column in the `DB`"
          }
        ],
        "examples": [
          "❌ The problem is the table missing column. → ✅ The problem is a missing column in the table."
        ]
      },
      {
        "title": "避免中文'那么'直译成 Then",
        "rule": "在英文中得出结论或承接上文时，用 So/Therefore 更自然，Then 通常表示时间上的'然后'。",
        "instances": [
          {
            "wrong": "Then we should start the meeting.",
            "right": "So we should start the meeting."
          }
        ],
        "examples": [
          "❌ Then we should wait for the review. → ✅ So we should wait for the review."
        ]
      }
    ]
  },
  "reply": null
}
```

### C-09（耗时 92.8s）

**输入**：By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error log when triggering dag.

**输出**：

```json
{"intent":"correction","correction":{"has_errors":true,"errors":[{"category":"grammar","error_type":"主谓不一致","fragment":"there are some error log","explanation":"`there are` 是复数谓语，后面的可数名词 `error log` 应为复数 `error logs`，否则主谓不一致。","correction":"there are some error logs"},{"category":"grammar","error_type":"冠词缺失","fragment":"when triggering dag","explanation":"`DAG` 是 `Airflow` 中的首字母缩略词，应全部大写；且这里指具体的 `DAG`，前面需要加冠词 `the`。","correction":"when triggering the DAG"}],"rewrite":{"minimal":{"text":"By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error logs when triggering the DAG.","explanation":"仅修正语法和用词，保留原句结构和语气"},"natural":{"text":"By the way, it's also easier to check the running worker and scheduler pods. That would help if you see any error logs when triggering the DAG.","explanation":"将 `you could also check ...` 改为 `it's also easier to check ...`，更简洁自然；用复数 `pods` 更符合实际场景；用 `if you see any error logs` 明确触发 `DAG` 时观察日志，避免悬垂分词，语气也更口语化。"}},"learnings":[{"title":"there be 句型中谓语与可数名词单复数必须一致","rule":"使用 `there are` 时，后面的可数名词必须用复数，因为 `are` 是复数谓语。","instances":[{"wrong":"there are some error log","right":"there are some error logs"}],"examples":["❌ There are some error log in the file. → ✅ There are some error logs in the file."]},{"title":"英文缩写词（如 DAG）应大写，且可数名词前需加冠词","rule":"首字母缩略词（如 `DAG`）在英文中通常全大写；当指代特定对象时，前面要加 `the` 或 `a`。","instances":[{"wrong":"triggering dag","right":"triggering the DAG"}],"examples":["❌ You need to trigger dag manually. → ✅ You need to trigger the `DAG` manually."]}]},"reply":null}
```
