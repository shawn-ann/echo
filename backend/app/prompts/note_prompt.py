"""保存笔记时 LLM 提示词：从错误生成/匹配规则笔记。"""


def build_note_system_prompt(existing_rules: list[str]) -> str:
    rules_list = "\n".join(f"- {r}" for r in existing_rules) if existing_rules else "（暂无已有规则）"
    return f"""你是英语语法规则归纳助手。根据用户提交的英文原文和错误列表，归纳出对应的语法规则笔记。

## 已有规则库
以下是系统中已存在的规则，新错误若属于其中某条，必须原样返回那条的 rule_title：
{rules_list}

## 输出格式
输出 JSON 对象，含 results 数组，每个元素对应一条规则（同类错误合并为一条）：
```json
{{
  "results": [
    {{
      "rule_title": "介词后加 -ing 形式",
      "description": "英语中介词后接动词时需用动名词形式(-ing)而非不定式...",
      "example": "interested in read → interested in reading"
    }}
  ]
}}
```

## rule_title 粒度要求
- 标题描述一个【可单独测试的规则点】，不是语法范畴
- ✅ 好："介词后加 -ing 形式"、"to 不定式接动词原形"、"可数名词单数需加冠词"
- ❌ 坏："过去时"、"冠词"、"时态"、"介词"（太宽泛，含多个不相关练习点）
- ❌ 坏："in 后加 ing"（太碎片，应泛化到所有介词）

## 合并指令
同类错误合并为一条 result（如 2 个时态错误 → 1 条规则）

## 去重指令
若新错误的规则与已有规则库中某条语义相同，必须原样返回那条的 rule_title（不得修改、不得编造）。description 字段始终生成（匹配已有规则时后端会忽略，仅用于新建规则）。

## example 格式
「错误写法 → 正确写法」，从本次 errors 中提炼

## description 要求
包含规则说明、构成方式、常见情况、边界/例外情况，一段完整讲解
"""


def build_note_user_content(source_text: str, errors: list[dict]) -> str:
    import json

    return f"""## 原文
{source_text}

## 错误列表
{json.dumps(errors, ensure_ascii=False, indent=2)}
"""
