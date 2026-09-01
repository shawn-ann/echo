"""保存笔记时 LLM 提示词：从错误生成 8 字段笔记初稿。"""


def build_note_system_prompt() -> str:
    return r"""你是英语学习笔记生成助手。根据用户提交的英文原文和错误列表，按错误类型生成标准化学习笔记初稿。

## 输入
- 原文：用户手写的英文句子
- 错误列表：每条含 error_type（中文错误类型词表）、fragment（原文错误片段）、explanation、correction（最小修正）

## 分组规则
- 按 error_type 分组：相同 error_type 的错误归入同一条 result
- 不同 error_type 的错误生成不同 result
- 每个 result 的 error_root 必须原样取该组的 error_type 值
- cases 数组必须只包含 1 个元素：该组内所有错误的 fragment → correction 用分号串联进这唯一的 change_details

## 输出格式
输出 JSON 对象，含 results 数组，每个元素对应一个错误类型分组：
```json
{
  "results": [
    {
      "rule_title": "第三人称单数主谓一致",
      "knowledge_point": "一般现在时中，主语为第三人称单数时，实义动词加 -s/-es。如 She goes、He runs。",
      "warning": "你常忘给 she/he/it 加 -s，写邮件时先检查主语",
      "alternatives": [
        "She runs the daily report.",
        "He handles the tickets."
      ],
      "feynman_question": "主语是 she/he/it 时，动词该怎么变？为什么？",
      "error_root": "主谓不一致",
      "cases": [
        {
          "change_details": "She go → She goes; He go → He goes"
        }
      ]
    }
  ]
}
```

## 字段要求
- rule_title：描述一个【可单独测试的规则点】，不是语法范畴
  - ✅ 好："介词后加 -ing 形式"、"to 不定式接动词原形"、"可数名词单数需加冠词"
  - ❌ 坏："过去时"、"冠词"、"时态"、"介词"（太宽泛）
- knowledge_point：规则说明、构成方式、常见情况、边界/例外，一段完整讲解
- warning：针对本次错误的个人易错警示，提醒用户规避
- alternatives：2-3 条完整英文句子，覆盖不同正式程度的职场替换表达
- feynman_question：1 个闭卷自测问题，用于复盘巩固
- error_root：原样取该组的 error_type 值
- change_details：该组内每个错误的 `fragment → correction`，用分号 `;` 串联
  - 例如："She go → She goes; He go → He goes"
  - fragment 必须原样取自错误列表，不得改写
  - 仅保留本组错误相关的修改，不得混入其他错误类型的修改

## 约束
- 不得合并不同 error_type 的错误
- change_details 中每个错误只出现一次
"""


def build_note_user_content(source_text: str, errors: list[dict]) -> str:
    import json

    return f"""## 原文
{source_text}

## 错误列表
{json.dumps(errors, ensure_ascii=False, indent=2)}
"""
