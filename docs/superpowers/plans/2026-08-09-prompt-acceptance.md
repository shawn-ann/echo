# 提示词验收实现计划（prompt-acceptance）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出符合要求的真实 LLM 提示词（`SYSTEM_PROMPT` 常量），并用 9 个 golden 用例的验收脚本（结构+语义断言，9/9 全过）验证其效果。

**Architecture:** 提示词存 `backend/app/prompts/correction_prompt.py`（SYSTEM_PROMPT 常量）；golden 用例存 `backend/app/prompts/golden_cases.json`（9 条：原文+期望断言）；验收逻辑拆为纯函数模块 `backend/app/scripts/acceptance_checks.py`（可单测）与 CLI 主脚本 `backend/app/scripts/prompt_acceptance.py`（加载配置→调 LLM→跑断言→汇总退出码）。LLM 连接读 `get_settings()`（pydantic-settings + .env，config.py 已有 LLM_BASE_URL/API_KEY/MODEL）。

> **路径约定**：测试以 `from app.prompts...` / `from app.scripts...` 导入（pytest.ini `pythonpath = .` 指向 backend 根），因此模块放 `backend/app/prompts/` 与 `backend/app/scripts/`（非 `backend/` 顶层），与现有 `app/services`/`app/core` 结构一致。

**Tech Stack:** Python + httpx + pydantic-settings（无新增依赖）；pytest 单测（验收脚本逻辑用注入的假 LLM 可测）

**依赖文档:** `docs/superpowers/specs/2026-08-09-prompt-acceptance-design.md`

---

### Task 1: SYSTEM_PROMPT 常量（correction_prompt.py）

**Files:**
- Create: `backend/app/prompts/__init__.py`
- Create: `backend/app/prompts/correction_prompt.py`
- Test: `backend/tests/test_correction_prompt.py`

- [ ] **Step 1: 编写失败的测试**

创建 `backend/app/prompts/__init__.py`（空文件）。

创建 `backend/tests/test_correction_prompt.py`：

```python
from app.prompts.correction_prompt import SYSTEM_PROMPT


def test_system_prompt_contains_contract_fields():
    assert "intent" in SYSTEM_PROMPT
    assert "correction" in SYSTEM_PROMPT
    assert "reply" in SYSTEM_PROMPT
    assert "category" in SYSTEM_PROMPT
    assert "error_type" in SYSTEM_PROMPT
    assert "learnings" in SYSTEM_PROMPT
    assert "minimal" in SYSTEM_PROMPT
    assert "natural" in SYSTEM_PROMPT


def test_system_prompt_contains_enum_values():
    for v in ("grammar", "collocation", "chinglish", "style"):
        assert v in SYSTEM_PROMPT
    for v in ("Major", "Minor"):
        assert v not in SYSTEM_PROMPT  # 契约不加 severity


def test_system_prompt_no_markdown_fence():
    assert "```" not in SYSTEM_PROMPT
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_correction_prompt.py -v`
Expected: FAIL（ModuleNotFoundError: app.prompts）

- [ ] **Step 3: 实现 SYSTEM_PROMPT**

创建 `backend/app/prompts/correction_prompt.py`：

```python
"""真实 LLM 提示词：会话式纠错 + 追问。

输出契约遵循 docs/superpowers/specs/2026-08-09-prompt-acceptance-design.md §二。
"""

SYSTEM_PROMPT = """你是英文纠错教练，面向通用日常英语场景（含技术/职场表达）。
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
- category 与 error_type 一致：冠词缺失/时态错误/主谓不一致/不可数名词误用 → grammar；中式直译 → chinglish；语域错配 → style；其余用词/搭配问题 → collocation 或 style
- 无法确定作者意图的表达不列为修正项，不臆测改写
- 无错误 → has_errors=false，errors 与 learnings 为空，minimal 与 natural 两版 text 均为原句、explanation 为空字符串
- 每个不同规则归纳一条 learning；同类错误的多个实例合并到同一条 learning 的 instances 数组
- error_type、explanation、title、rule、examples 用中文；fragment、correction、instances 的 wrong/right、rewrite 的 text 保持英文

## 返回格式（严格遵守字段名）
{"intent": "correction", "correction": {"has_errors": ..., "errors": [...], "rewrite": {"minimal": {...}, "natural": {...}}, "learnings": [...]}, "reply": null}
"""
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_correction_prompt.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/prompts/ backend/tests/test_correction_prompt.py
git commit -m "feat(prompts): SYSTEM_PROMPT 常量（合并契约 intent/correction/reply + learnings + category/error_type）"
```

---

### Task 2: golden_cases.json + 加载器

**Files:**
- Create: `backend/app/prompts/golden_cases.json`
- Create: `backend/app/prompts/golden_cases.py`
- Test: `backend/tests/test_golden_cases.py`

- [ ] **Step 1: 编写失败的测试**

创建 `backend/app/prompts/golden_cases.py`（先空壳，仅函数签名）：

```python
from pathlib import Path

_GOLDEN_PATH = Path(__file__).parent / "golden_cases.json"


def load_golden_cases() -> list[dict]:
    """读取 golden_cases.json，返回用例列表。"""
    raise NotImplementedError
```

创建 `backend/tests/test_golden_cases.py`：

```python
from app.prompts.golden_cases import load_golden_cases


def test_load_returns_9_cases():
    cases = load_golden_cases()
    assert len(cases) == 9


def test_each_case_has_required_keys():
    for case in load_golden_cases():
        assert set(("id", "input", "expect")).issubset(case.keys())
        assert isinstance(case["id"], str)
        assert isinstance(case["input"], str)
        assert isinstance(case["expect"], dict)


def test_all_cases_have_unique_ids():
    ids = [c["id"] for c in load_golden_cases()]
    assert len(ids) == len(set(ids))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_golden_cases.py -v`
Expected: FAIL（NotImplementedError）

- [ ] **Step 3: 创建 golden_cases.json（9 条完整用例）**

创建 `backend/app/prompts/golden_cases.json`：

```json
{
  "cases": [
    {
      "id": "C-01",
      "input": "Correct the trigger_by field set up logic when creating job.",
      "expect": {
        "has_errors": true,
        "error_count_min": 2,
        "must_have": [
          { "fragment_contains": "creating job", "correction_contains": "a job", "category_expected": "grammar", "error_type_contains": "冠词" },
          { "fragment_contains": "set up", "correction_contains": "setup" }
        ],
        "minimal_contains": "setup",
        "preserve_terms": ["trigger_by"],
        "learnings_min": 2
      }
    },
    {
      "id": "C-02",
      "input": "What do you mean you can't restart this webapp? getting an error?",
      "expect": {
        "has_errors": true,
        "error_count_min": 1,
        "must_have": [
          { "fragment_contains": "getting an error", "correction_contains": "are you getting", "category_expected": "grammar", "error_type_contains": "主语" }
        ],
        "minimal_contains": "Are you getting",
        "preserve_terms": ["webapp"],
        "learnings_min": 1
      }
    },
    {
      "id": "C-03",
      "input": "In that case, the egress IP(出网ip) of GDSP cluster should be enough, right?",
      "expect": {
        "has_errors": true,
        "error_count_min": 1,
        "must_have": [
          { "fragment_contains": "GDSP cluster", "correction_contains": "the GDSP cluster", "category_expected": "grammar", "error_type_contains": "冠词" }
        ],
        "minimal_contains": "the GDSP cluster",
        "preserve_terms": ["GDSP"],
        "learnings_min": 1
      }
    },
    {
      "id": "C-04",
      "input": "This pvc should be created when adding resource pool. How many storage do we want?",
      "expect": {
        "has_errors": true,
        "error_count_min": 2,
        "must_have": [
          { "fragment_contains": "adding resource pool", "correction_contains": "a resource pool", "category_expected": "grammar", "error_type_contains": "冠词" },
          { "fragment_contains": "How many storage", "correction_contains": "How much storage", "category_expected": "grammar", "error_type_contains": "不可数" }
        ],
        "minimal_contains": "How much storage",
        "preserve_terms": ["pvc"],
        "learnings_min": 2
      }
    },
    {
      "id": "C-05",
      "input": "Is it possible to finished the testing for https://jira.rakuten-it.com/jira/browse/DSD-45874 and release it by this week? This would fix the issue that ariflow worker/scheduler logs is empty issue.",
      "expect": {
        "has_errors": true,
        "error_count_min": 3,
        "must_have": [
          { "fragment_contains": "to finished", "correction_contains": "to finish", "category_expected": "grammar", "error_type_contains": "不定式" },
          { "fragment_contains": "logs is", "correction_contains": "logs are", "category_expected": "grammar", "error_type_contains": "主谓" },
          { "fragment_contains": "empty issue", "correction_contains": "logs are empty", "category_expected": "grammar" }
        ],
        "minimal_contains": "by the end of this week",
        "preserve_terms": ["DSD-45874", "ariflow"],
        "learnings_min": 3
      }
    },
    {
      "id": "C-06",
      "input": "Sorry for the late response, we are working on the release operation, the restart function should work now, please check.",
      "expect": {
        "has_errors": true,
        "error_count_min": 1,
        "must_have": [
          { "fragment_contains": "release operation", "correction_contains": "release", "category_expected": "chinglish", "error_type_contains": "中式直译" }
        ],
        "minimal_contains": "the release",
        "preserve_terms": ["release"],
        "learnings_min": 1
      }
    },
    {
      "id": "C-07",
      "input": "The issue airflow instance log have been fixed, could you please create a new airflow instance instead? The log viewer and download should be real quick.",
      "expect": {
        "has_errors": true,
        "error_count_min": 2,
        "must_have": [
          { "fragment_contains": "log have been", "correction_contains": "log issue has been", "category_expected": "grammar", "error_type_contains": "主谓" },
          { "fragment_contains": "real quick", "correction_contains": "really quick", "category_expected": "grammar", "error_type_contains": "用词" }
        ],
        "minimal_contains": "really quick",
        "preserve_terms": ["airflow"],
        "learnings_min": 2
      }
    },
    {
      "id": "C-08",
      "input": "The empty log issue in PROD has been resolved now, I suspect this is also caused by the DB missing column. Then DSD-45874 is not urgent now, we can release both DSD-45874 & DSD-45252 next week.",
      "expect": {
        "has_errors": true,
        "error_count_min": 2,
        "must_have": [
          { "fragment_contains": "DB missing column", "correction_contains": "missing DB column", "category_expected": "collocation", "error_type_contains": "词序" },
          { "fragment_contains": "is not urgent", "correction_contains": "is no longer urgent", "category_expected": "style", "error_type_contains": "搭配" }
        ],
        "minimal_contains": "no longer urgent",
        "preserve_terms": ["DSD-45874", "DSD-45252", "PROD"],
        "learnings_min": 2
      }
    },
    {
      "id": "C-09",
      "input": "By the way, you could also check the running worker pod and scheduler pod more easily. This would be helpful if there are some error log when triggering dag.",
      "expect": {
        "has_errors": true,
        "error_count_min": 2,
        "must_have": [
          { "fragment_contains": "some error log", "correction_contains": "error logs", "category_expected": "grammar", "error_type_contains": "主谓" },
          { "fragment_contains": "triggering dag", "correction_contains": "a dag", "category_expected": "grammar", "error_type_contains": "冠词" }
        ],
        "minimal_contains": "a DAG",
        "preserve_terms": ["worker", "scheduler"],
        "learnings_min": 2
      }
    }
  ]
}
```

> 说明：C-09 的 `minimal_contains` 写 `"a DAG"` 但原文是 `dag` 小写；LLM 可能输出 `a DAG` 或 `a dag`。为稳健，该断言在语义检查中做**大小写不敏感**匹配（见 Task 3）。

- [ ] **Step 4: 实现加载器**

修改 `backend/app/prompts/golden_cases.py`：

```python
import json
from pathlib import Path

_GOLDEN_PATH = Path(__file__).parent / "golden_cases.json"


def load_golden_cases() -> list[dict]:
    """读取 golden_cases.json，返回用例列表。"""
    with _GOLDEN_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_golden_cases.py -v`
Expected: PASS（3 passed）

- [ ] **Step 6: Commit**

```bash
git add backend/app/prompts/golden_cases.json backend/app/prompts/golden_cases.py backend/tests/test_golden_cases.py
git commit -m "feat(prompts): 9 条 golden 用例与加载器"
```

---

### Task 3: 验收断言纯函数（acceptance_checks.py）

**Files:**
- Create: `backend/app/scripts/__init__.py`（空文件）
- Create: `backend/app/scripts/acceptance_checks.py`
- Test: `backend/tests/test_acceptance_checks.py`

- [ ] **Step 1: 编写失败的测试**

创建 `backend/app/scripts/__init__.py`（空文件）。

创建 `backend/tests/test_acceptance_checks.py`：

```python
from app.scripts.acceptance_checks import (
    CATEGORY_ENUM,
    structure_check,
    semantic_check,
)


def _valid_report():
    return {
        "has_errors": True,
        "errors": [
            {
                "category": "grammar",
                "error_type": "冠词缺失",
                "fragment": "creating job",
                "explanation": "job 是可数名词单数",
                "correction": "creating a job",
            }
        ],
        "rewrite": {
            "minimal": {"text": "Correct the trigger_by field setup logic when creating a job.", "explanation": "仅修正语法和用词"},
            "natural": {"text": "Fix the trigger_by field setup logic when creating a job.", "explanation": "更自然"},
        },
        "learnings": [
            {
                "title": "可数名词单数不能裸用",
                "rule": "可数名词单数必须加冠词",
                "instances": [{"wrong": "creating job", "right": "creating a job"}],
                "examples": ["I'm deploying service ❌ → I'm deploying a service ✅"],
            }
        ],
    }


def test_structure_check_valid():
    errors = structure_check(_valid_report())
    assert errors == []


def test_structure_check_missing_category():
    report = _valid_report()
    report["errors"][0]["category"] = "typo"
    errors = structure_check(report)
    assert any("category" in e for e in errors)


def test_structure_check_missing_field():
    report = _valid_report()
    del report["errors"][0]["correction"]
    errors = structure_check(report)
    assert any("correction" in e for e in errors)


def test_structure_check_rewrite_needs_both():
    report = _valid_report()
    del report["rewrite"]["natural"]
    errors = structure_check(report)
    assert any("natural" in e for e in errors)


def test_structure_check_learnings_required_fields():
    report = _valid_report()
    del report["learnings"][0]["examples"]
    errors = structure_check(report)
    assert any("examples" in e for e in errors)


def test_semantic_check_hit_and_miss():
    expect = {
        "has_errors": True,
        "error_count_min": 1,
        "must_have": [
            {"fragment_contains": "creating job", "correction_contains": "a job", "category_expected": "grammar", "error_type_contains": "冠词"}
        ],
        "minimal_contains": "setup",
        "preserve_terms": ["trigger_by"],
        "learnings_min": 1,
    }
    # 满足期望的响应 → 无失败
    failures = semantic_check(_valid_report(), expect)
    assert failures == []
    # 破坏 correction_contains → 失败
    bad = _valid_report()
    bad["errors"][0]["correction"] = "creating the job"
    failures = semantic_check(bad, expect)
    assert any("a job" in f for f in failures)


def test_semantic_check_perfect_case():
    report = {
        "has_errors": False,
        "errors": [],
        "rewrite": {
            "minimal": {"text": "I'll check the logs.", "explanation": ""},
            "natural": {"text": "I'll check the logs.", "explanation": ""},
        },
        "learnings": [],
    }
    expect = {"has_errors": False, "error_count_min": 0, "must_have": [], "minimal_contains": "logs", "preserve_terms": [], "learnings_min": 0}
    assert semantic_check(report, expect) == []


def test_semantic_check_case_insensitive_contains():
    expect = {"has_errors": True, "error_count_min": 1,
              "must_have": [{"fragment_contains": "triggering dag", "correction_contains": "a DAG"}],
              "minimal_contains": "a DAG", "preserve_terms": [], "learnings_min": 1}
    report = _valid_report()
    report["errors"][0] = {
        "category": "grammar", "error_type": "冠词缺失", "fragment": "triggering dag",
        "explanation": "x", "correction": "triggering a dag",
    }
    report["rewrite"]["minimal"] = {"text": "... a dag ...", "explanation": ""}
    assert semantic_check(report, expect) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_acceptance_checks.py -v`
Expected: FAIL（ModuleNotFoundError: app.scripts）

- [ ] **Step 3: 实现断言模块**

创建 `backend/app/scripts/acceptance_checks.py`：

```python
"""验收断言纯函数：结构检查 + 语义检查。"""

from typing import Any

CATEGORY_ENUM = {"grammar", "collocation", "chinglish", "style"}


def _ci(text: str) -> str:
    return text.lower()


def structure_check(report: dict[str, Any]) -> list[str]:
    """结构断言。返回失败消息列表；空列表 = 通过。"""
    failures: list[str] = []
    if not isinstance(report.get("has_errors"), bool):
        failures.append("has_errors 必须是布尔值")
    errors = report.get("errors")
    if not isinstance(errors, list):
        failures.append("errors 必须是数组")
        errors = []
    for i, e in enumerate(errors):
        for field in ("category", "error_type", "fragment", "explanation", "correction"):
            if not isinstance(e.get(field), str) or not e[field].strip():
                failures.append(f"errors[{i}].{field} 缺失或为空")
        if e.get("category") not in CATEGORY_ENUM:
            failures.append(f"errors[{i}].category 不在枚举内: {e.get('category')!r}")
    rewrite = report.get("rewrite")
    if not isinstance(rewrite, dict):
        failures.append("rewrite 必须是对象")
        rewrite = {}
    for key in ("minimal", "natural"):
        opt = rewrite.get(key)
        if not isinstance(opt, dict):
            failures.append(f"rewrite.{key} 缺失")
        else:
            for field in ("text", "explanation"):
                if not isinstance(opt.get(field), str):
                    failures.append(f"rewrite.{key}.{field} 缺失")
    learnings = report.get("learnings")
    if not isinstance(learnings, list):
        failures.append("learnings 必须是数组")
        learnings = []
    for i, l in enumerate(learnings):
        for field in ("title", "rule", "instances", "examples"):
            if field not in l:
                failures.append(f"learnings[{i}].{field} 缺失")
        if isinstance(l.get("instances"), list):
            for j, inst in enumerate(l["instances"]):
                if not isinstance(inst.get("wrong"), str) or not isinstance(inst.get("right"), str):
                    failures.append(f"learnings[{i}].instances[{j}] 需含 wrong/right")
    return failures


def _must_have_failure(must: dict[str, Any], errors: list[dict[str, Any]]) -> list[str]:
    """对一条 must_have 断言找失败。任一命中即可算该断言通过。"""
    for e in errors:
        ok = True
        if "fragment_contains" in must and _ci(must["fragment_contains"]) not in _ci(e.get("fragment", "")):
            ok = False
        if ok and "correction_contains" in must and _ci(must["correction_contains"]) not in _ci(e.get("correction", "")):
            ok = False
        if ok and "category_expected" in must and must["category_expected"] != e.get("category"):
            ok = False
        if ok and "error_type_contains" in must and must["error_type_contains"] not in e.get("error_type", ""):
            ok = False
        if ok:
            return []
    return [f"must_have 未命中: {must}"]


def semantic_check(report: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    """语义断言。返回失败消息列表；空列表 = 通过。"""
    failures: list[str] = []
    errors = report.get("errors") or []
    if report.get("has_errors") is not expect.get("has_errors"):
        failures.append(f"has_errors 期望 {expect.get('has_errors')}，实际 {report.get('has_errors')}")
    if len(errors) < expect.get("error_count_min", 0):
        failures.append(f"errors 数量 {len(errors)} < 期望 {expect.get('error_count_min')}")
    for must in expect.get("must_have", []):
        failures.extend(_must_have_failure(must, errors))
    minimal_text = ((report.get("rewrite") or {}).get("minimal") or {}).get("text", "")
    if "minimal_contains" in expect:
        if _ci(expect["minimal_contains"]) not in _ci(minimal_text):
            failures.append(f"rewrite.minimal 不含 {expect['minimal_contains']!r}")
    full_text = _ci(
        str(report.get("rewrite", {}))
        + str(report.get("errors", []))
        + str(report.get("learnings", []))
    )
    for term in expect.get("preserve_terms", []):
        if _ci(term) not in full_text:
            failures.append(f"术语未保留: {term!r}")
    if len(report.get("learnings") or []) < expect.get("learnings_min", 0):
        failures.append(
            f"learnings 数量 {len(report.get('learnings') or [])} < 期望 {expect.get('learnings_min')}"
        )
    # 两版互异
    rewrite = report.get("rewrite") or {}
    if isinstance(rewrite.get("minimal"), dict) and isinstance(rewrite.get("natural"), dict):
        if rewrite["minimal"].get("text") == rewrite["natural"].get("text"):
            failures.append("minimal 与 natural 文本相同")
    return failures
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_acceptance_checks.py -v`
Expected: PASS（8 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/scripts/__init__.py backend/app/scripts/acceptance_checks.py backend/tests/test_acceptance_checks.py
git commit -m "feat(scripts): 验收断言纯函数（结构 + 语义，含大小写不敏感匹配）"
```

---

### Task 4: 验收 CLI 脚本（prompt_acceptance.py）

**Files:**
- Create: `backend/app/scripts/prompt_acceptance.py`
- Test: `backend/tests/test_prompt_acceptance.py`

- [ ] **Step 1: 编写失败的测试**

创建 `backend/tests/test_prompt_acceptance.py`：

```python
import json

from app.scripts.prompt_acceptance import build_messages, run_case, run_acceptance


def _mock_llm(responder):
    async def llm_call(messages):
        return responder(messages)
    return llm_call


def test_build_messages_uses_system_prompt():
    msgs = build_messages("Correct the trigger_by field set up logic when creating job.")
    assert msgs[0]["role"] == "system"
    assert "correction" in msgs[0]["content"]
    assert msgs[-1] == {"role": "user", "content": "Correct the trigger_by field set up logic when creating job."}


def test_run_case_success():
    report = {
        "intent": "correction",
        "correction": {
            "has_errors": True,
            "errors": [
                {"category": "grammar", "error_type": "冠词缺失", "fragment": "creating job",
                 "explanation": "x", "correction": "creating a job"}
            ],
            "rewrite": {
                "minimal": {"text": "Correct the trigger_by field setup logic when creating a job.", "explanation": "仅修正"},
                "natural": {"text": "Fix the trigger_by field setup logic when creating a job.", "explanation": "更自然"},
            },
            "learnings": [
                {"title": "t", "rule": "r", "instances": [{"wrong": "creating job", "right": "creating a job"}], "examples": ["e"]}
            ],
        },
        "reply": None,
    }
    llm_call = _mock_llm(lambda msgs: json.dumps(report, ensure_ascii=False))
    case = {
        "id": "C-01",
        "input": "Correct the trigger_by field set up logic when creating job.",
        "expect": {
            "has_errors": True, "error_count_min": 1,
            "must_have": [{"fragment_contains": "creating job", "correction_contains": "a job", "category_expected": "grammar"}],
            "minimal_contains": "setup", "preserve_terms": ["trigger_by"], "learnings_min": 1,
        },
    }
    result = run_case(llm_call, case)
    assert result["passed"] is True
    assert result["failures"] == []


def test_run_case_llm_bad_json():
    llm_call = _mock_llm(lambda msgs: "not-json")
    case = {"id": "X", "input": "hello", "expect": {}}
    result = run_case(llm_call, case)
    assert result["passed"] is False
    assert any("JSON" in f for f in result["failures"])


def test_run_acceptance_aggregates():
    calls = {"n": 0}

    def responder(messages):
        calls["n"] += 1
        report = {
            "intent": "correction",
            "correction": {
                "has_errors": False, "errors": [],
                "rewrite": {"minimal": {"text": "ok", "explanation": ""}, "natural": {"text": "ok", "explanation": ""}},
                "learnings": [],
            },
            "reply": None,
        }
        return json.dumps(report)

    cases = [
        {"id": "A", "input": "a", "expect": {"has_errors": False, "error_count_min": 0, "must_have": [], "minimal_contains": "ok", "preserve_terms": [], "learnings_min": 0}},
        {"id": "B", "input": "b", "expect": {"has_errors": False, "error_count_min": 0, "must_have": [], "minimal_contains": "ok", "preserve_terms": [], "learnings_min": 0}},
    ]
    summary = run_acceptance(_mock_llm(responder), cases)
    assert summary["total"] == 2
    assert summary["passed"] == 2
    assert summary["all_passed"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_prompt_acceptance.py -v`
Expected: FAIL（ModuleNotFoundError: app.scripts.prompt_acceptance）

- [ ] **Step 3: 实现 CLI 脚本**

创建 `backend/app/scripts/prompt_acceptance.py`：

```python
"""提示词验收脚本。

用法：
    cd backend
    .venv/bin/python -m app.scripts.prompt_acceptance

依赖 .env 中 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL（config.py 提供默认值）。
逐条跑 9 个 golden 用例，结构+语义断言；9/9 全过退出码 0，否则退出码 1。
"""

import asyncio
import json
import sys

import httpx

from app.core.config import get_settings
from app.prompts.correction_prompt import SYSTEM_PROMPT
from app.prompts.golden_cases import load_golden_cases
from app.scripts.acceptance_checks import semantic_check, structure_check


def build_messages(input_text: str) -> list[dict]:
    """构建发给 LLM 的 messages：system prompt + 用户原文。"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": input_text},
    ]


async def _call_llm(messages: list[dict]) -> str:
    """调用 OpenAI 兼容 Chat Completions API，返回 content 字符串。"""
    settings = get_settings()
    if not settings.LLM_BASE_URL or not settings.LLM_API_KEY:
        print("请先在 .env 配置 LLM_BASE_URL 与 LLM_API_KEY")
        sys.exit(1)
    url = settings.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            json={"model": settings.LLM_MODEL, "messages": messages},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _extract_correction(payload: dict) -> dict:
    """从 LLM 响应中取出 correction 对象（兼容 intent 包装）。"""
    if "correction" in payload and isinstance(payload["correction"], dict):
        return payload["correction"]
    return payload


async def run_case(llm_call, case: dict) -> dict:
    """跑单个用例，返回 {id, passed, failures, raw}。"""
    case_id = case["id"]
    try:
        raw = await llm_call(build_messages(case["input"]))
    except Exception as exc:  # noqa: BLE001 - 验收脚本需兜底所有网络/HTTP 异常
        return {"id": case_id, "passed": False, "failures": [f"LLM 调用失败: {exc}"], "raw": ""}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"id": case_id, "passed": False, "failures": ["LLM 返回不是合法 JSON"], "raw": raw}

    report = _extract_correction(payload)
    failures = structure_check(report)
    failures.extend(semantic_check(report, case.get("expect", {})))
    return {"id": case_id, "passed": not failures, "failures": failures, "raw": raw}


async def run_acceptance(llm_call, cases: list[dict]) -> dict:
    """跑全部用例，返回 {total, passed, all_passed, results}。"""
    results = []
    for case in cases:
        results.append(await run_case(llm_call, case))
    passed_count = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed_count,
        "all_passed": passed_count == len(results),
        "results": results,
    }


async def main() -> int:
    cases = load_golden_cases()
    summary = await run_acceptance(_call_llm, cases)
    print(f"\n=== 验收结果：{summary['passed']}/{summary['total']} ===")
    for r in summary["results"]:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"[{mark}] {r['id']}")
        for f in r["failures"]:
            print(f"      - {f}")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_prompt_acceptance.py -v`
Expected: PASS（4 passed）

> 注意：脚本作为 `python -m app.scripts.prompt_acceptance` 运行时，`app` 包在 path 上（backend 根）。若直接 `python scripts/prompt_acceptance.py` 会因 `app` 不可导入失败——因此文档/README 用 `-m` 方式。

- [ ] **Step 5: 全量回归**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 全绿（原 47 + prompt 3 + golden 3 + checks 8 + acceptance 4 = 65 passed）

- [ ] **Step 6: Commit**

```bash
git add backend/app/scripts/prompt_acceptance.py backend/tests/test_prompt_acceptance.py
git commit -m "feat(scripts): 提示词验收 CLI（跑 9 golden 用例，9/9 全过退出 0）"
```

---

### Task 5: 真实 LLM 验收运行（key 可用时）

**Files:**
- （无新增代码；运行已有脚本）

- [ ] **Step 1: 确认 .env 已配置 LLM**

Run: `cd backend && ls -la .env 2>/dev/null || echo "no .env"; .venv/bin/python -c "from app.core.config import get_settings; s=get_settings(); print(bool(s.LLM_API_KEY), s.LLM_MODEL)"`
Expected: 输出 `True deepseek-v4-flash`（或你配置的模型）

> 若 API_KEY 为空或需要改用你的 key，编辑 `backend/.env`（示例：`LLM_BASE_URL=https://api.deepseek.com`、`LLM_API_KEY=sk-xxx`、`LLM_MODEL=deepseek-v4-flash`），config.py 的默认值会被 .env 覆盖。

- [ ] **Step 2: 运行验收**

Run: `cd backend && .venv/bin/python -m app.scripts.prompt_acceptance`
Expected: 输出 `=== 验收结果：9/9 ===` 且每行 `[PASS] C-0X`

- [ ] **Step 3: 若某用例 FAIL，按失败明细调整提示词**

针对失败断言（如某 error_type 不匹配、术语未保留），修改 `backend/app/prompts/correction_prompt.py` 中对应约束（如补充术语保留示例、加强 category↔error_type 映射措辞），重跑直到 9/9。

- [ ] **Step 4: 提交提示词调优**

```bash
git add backend/app/prompts/correction_prompt.py
git commit -m "feat(prompts): 提示词调优至 9/9 验收通过"
```

---

## Self-Review 检查表

- **Spec 覆盖**：§二 契约 → Task 1（SYSTEM_PROMPT）+ Task 3（结构断言字段）；§五 验收脚本 → Task 3/4；§5.3 golden_cases → Task 2；§5.1 流程（配置/缺 key 退出/9 汇总）→ Task 4；§三 示例映射（minimal 精确、natural 仅校验存在且互异）→ Task 3 `semantic_check`；无 severity → Task 1 测试断言 `Major not in SYSTEM_PROMPT` + Task 3 结构断言不含 severity。
- **占位符扫描**：无 TBD/TODO；所有步骤含完整代码与命令。
- **类型一致性**：`structure_check(report) -> list[str]`、`semantic_check(report, expect) -> list[str]`、`run_case(llm_call, case) -> dict`、`run_acceptance(llm_call, cases) -> dict`；`build_messages(input_text) -> list[dict]`；golden 用例字段 `fragment_contains/correction_contains/category_expected/error_type_contains/minimal_contains/preserve_terms/learnings_min/has_errors/error_count_min` 在 Task 2（数据）与 Task 3（消费方）一致。
