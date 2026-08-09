"""提示词验收脚本。

用法：
    cd backend
    .venv/bin/python -m app.scripts.prompt_acceptance

依赖 .env 中 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL（config.py 提供默认值）。
逐条跑 9 个 golden 用例：
- 结构断言：JSON 合法、字段齐全、category 枚举
- 语义断言：关键错误被识别（无遗漏）、每个错误有实质修正、术语保留、两版互异
- 语法复核：用一次轻量 LLM 调用判断 minimal 修正后的句子是否语法正确
生成 Markdown 测试报告（docs/prompts/prompt-acceptance-report.md）。
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.prompts.correction_prompt import SYSTEM_PROMPT
from app.prompts.golden_cases import load_golden_cases
from app.scripts.acceptance_checks import semantic_check, structure_check

_REPORT_PATH = Path(__file__).resolve().parents[2] / "docs" / "prompts" / "prompt-acceptance-report.md"

_GRAMMAR_CHECK_SYSTEM = """你是英文语法检查器。判断给定英文句子是否有语法错误或不地道表达。
只输出一个词：YES（有语法错误）或 NO（没有语法错误）。不要输出其他内容。"""


def build_messages(input_text: str) -> list[dict]:
    """构建发给 LLM 的 messages：system prompt + 用户原文。"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": input_text},
    ]


def build_grammar_messages(sentence: str) -> list[dict]:
    """构建语法复核的 messages。"""
    return [
        {"role": "system", "content": _GRAMMAR_CHECK_SYSTEM},
        {"role": "user", "content": sentence},
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
            json={"model": settings.LLM_MODEL, "messages": messages, "temperature": 0},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _extract_correction(payload: dict) -> dict:
    """从 LLM 响应中取出 correction 对象（兼容 intent 包装）。"""
    if "correction" in payload and isinstance(payload["correction"], dict):
        return payload["correction"]
    return payload


async def _grammar_check(llm_call, sentence: str) -> bool | None:
    """用轻量 LLM 判断句子是否语法正确。返回 True=无错 / False=有错 / None=判断失败。"""
    for attempt in range(2):
        try:
            raw = await llm_call(build_grammar_messages(sentence))
            answer = raw.strip().upper()
            if answer.startswith("YES"):
                return False
            if answer.startswith("NO"):
                return True
            return None
        except Exception:  # noqa: BLE001 - 网络/超时兜底
            continue
    return None


async def run_case(llm_call, case: dict) -> dict:
    """跑单个用例，返回含 {id, passed, failures, raw, elapsed, errors, minimal, expected, input} 的 dict。"""
    case_id = case["id"]
    case_input = case.get("input", "")
    started = time.monotonic()
    raw = ""
    last_exc = None
    for attempt in range(2):
        try:
            raw = await llm_call(build_messages(case["input"]))
            break
        except Exception as exc:  # noqa: BLE001 - 验收脚本需兜底所有网络/HTTP 异常
            last_exc = exc
    else:
        return {
            "id": case_id,
            "passed": False,
            "failures": [f"LLM 调用失败: {last_exc}"],
            "raw": "",
            "elapsed": round(time.monotonic() - started, 1),
            "errors": [],
            "minimal": "",
            "input": case_input,
            "expected": case.get("expect", {}),
        }

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "id": case_id, "passed": False, "failures": ["LLM 返回不是合法 JSON"], "raw": raw,
            "elapsed": round(time.monotonic() - started, 1), "errors": [], "minimal": "",
            "input": case_input,
            "expected": case.get("expect", {}),
        }

    if not isinstance(payload, dict):
        return {
            "id": case_id, "passed": False, "failures": ["LLM 返回 JSON 不是对象"], "raw": raw,
            "elapsed": round(time.monotonic() - started, 1), "errors": [], "minimal": "",
            "input": case_input,
            "expected": case.get("expect", {}),
        }

    report = _extract_correction(payload)
    failures = structure_check(report)
    failures.extend(semantic_check(report, case.get("expect", {})))

    minimal_text = ((report.get("rewrite") or {}).get("minimal") or {}).get("text", "")
    grammar_ok = None
    if not failures and minimal_text:
        grammar_ok = await _grammar_check(llm_call, minimal_text)
        if grammar_ok is False:
            failures.append("minimal 修正后的句子仍有语法错误")

    return {
        "id": case_id,
        "passed": not failures,
        "failures": failures,
        "raw": raw,
        "elapsed": round(time.monotonic() - started, 1),
        "errors": report.get("errors", []),
        "minimal": minimal_text,
        "grammar_ok": grammar_ok,
        "input": case_input,
        "expected": case.get("expect", {}),
    }


async def run_acceptance(llm_call, cases: list[dict]) -> dict:
    """跑全部用例，返回 {total, passed, all_passed, results, elapsed, prompt}。"""
    started = time.monotonic()
    results = []
    for case in cases:
        results.append(await run_case(llm_call, case))
    passed_count = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed_count,
        "all_passed": passed_count == len(results),
        "results": results,
        "elapsed": round(time.monotonic() - started, 1),
        "prompt": SYSTEM_PROMPT,
        "model": get_settings().LLM_MODEL,
    }


def _render_report(summary: dict) -> str:
    lines: list[str] = []
    lines.append("# 提示词验收测试报告（Prompt Acceptance Report）")
    lines.append("")
    lines.append(f"- **模型**：`{summary['model']}`")
    lines.append(f"- **总耗时**：{summary['elapsed']} 秒")
    lines.append(f"- **通过**：{summary['passed']}/{summary['total']}")
    lines.append("")
    lines.append("## 一、测试提示词（SYSTEM_PROMPT）")
    lines.append("")
    lines.append("```text")
    lines.append(summary["prompt"])
    lines.append("```")
    lines.append("")
    lines.append("## 二、测试用例与结果")
    lines.append("")
    for r in summary["results"]:
        mark = "✅ 通过" if r["passed"] else "❌ 失败"
        lines.append(f"### {r['id']} {mark}（耗时 {r['elapsed']}s）")
        lines.append("")
        lines.append(f"**输入句子**：{r.get('input', '')}")
        lines.append("")
        lines.append("**期待结果**：")
        lines.append("")
        lines.append("| 需识别的错误片段 | 说明 |")
        lines.append("|---|---|")
        for m in r["expected"].get("must_have", []):
            lines.append(f"| `{m['fragment_contains']}` | 应被识别并修正 |")
        if not r["expected"].get("must_have"):
            lines.append("| （无） | 无错误场景 |")
        lines.append("")
        lines.append("**纠错结果**：")
        lines.append("")
        if r["errors"]:
            lines.append("| 严重片段 fragment | 错误类型 error_type | 修正 correction |")
            lines.append("|---|---|---|")
            for e in r["errors"]:
                lines.append(
                    f"| `{e.get('fragment','')}` | {e.get('error_type','')} | `{e.get('correction','')}` |"
                )
        else:
            lines.append("（LLM 未识别出错误）")
        lines.append("")
        lines.append(f"**最小修正 minimal**：{r['minimal'] or '（无）'}")
        if r.get("grammar_ok") is not None:
            lines.append(f"")
            lines.append(f"**语法复核**：{'无语法错误 ✅' if r['grammar_ok'] else '仍有语法错误 ❌'}")
        lines.append("")
        if r["failures"]:
            lines.append("**失败详情**：")
            lines.append("")
            for f in r["failures"]:
                lines.append(f"- {f}")
            lines.append("")
    return "\n".join(lines)


def write_report(summary: dict) -> str:
    """生成并保存 Markdown 测试报告。返回报告路径。"""
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text(_render_report(summary), encoding="utf-8")
    return str(_REPORT_PATH)


async def main() -> int:
    cases = load_golden_cases()
    summary = await run_acceptance(_call_llm, cases)
    report_path = write_report(summary)
    print(f"\n=== 验收结果：{summary['passed']}/{summary['total']} ===")
    for r in summary["results"]:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"[{mark}] {r['id']} ({r['elapsed']}s)")
        for f in r["failures"]:
            print(f"      - {f}")
    print(f"\n测试报告已生成：{report_path}")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
