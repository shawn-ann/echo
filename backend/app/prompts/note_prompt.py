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
      "rule_title": "第三人称单数主谓一致",
      "description": "一般现在时中，主语为第三人称单数时，实义动词加 -s/-es，助动词用 has...",
      "examples": [
        {{"text": "She plays tennis every day.", "note": "play → plays"}},
        {{"text": "He goes to work by bus.", "note": "go → goes"}}
      ],
      "references": ["She have", "she go"]
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
若新错误的规则与已有规则库中某条语义相同，必须原样返回那条的 rule_title（不得修改、不得编造）。

## references 生成
- references 是字符串数组，每个元素是**原样选取自输入「错误列表」中 fragment 字段**的文本
- 一条规则可对应多个 references（如 She have / she go 同属主谓一致）
- **不得改写** fragment 文本，**不得补充**不在错误列表中的文本

## examples 要求
- 给出 3 个**正确用法**的完整英文句子，不参考用户错误
- 每条含 text（英文句子）和 note（简短中文说明，如 play → plays）
- 覆盖该规则的典型场景

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
