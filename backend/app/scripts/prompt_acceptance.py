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
            json={"model": settings.LLM_MODEL, "messages": messages, "temperature": 0},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _extract_correction(payload: dict) -> dict:
    """从 LLM 响应中取出 correction 对象（兼容 intent 包装）。"""
    if "correction" in payload and isinstance(payload["correction"], dict):
        return payload["correction"]
    return payload


async def run_case(llm_call, case: dict) -> dict:
    """跑单个用例，返回 {id, passed, failures, raw}。网络异常重试一次。"""
    case_id = case["id"]
    raw = ""
    last_exc = None
    for attempt in range(2):
        try:
            raw = await llm_call(build_messages(case["input"]))
            break
        except Exception as exc:  # noqa: BLE001 - 验收脚本需兜底所有网络/HTTP 异常
            last_exc = exc
    else:
        return {"id": case_id, "passed": False, "failures": [f"LLM 调用失败: {last_exc}"], "raw": ""}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"id": case_id, "passed": False, "failures": ["LLM 返回不是合法 JSON"], "raw": raw}

    if not isinstance(payload, dict):
        return {"id": case_id, "passed": False, "failures": ["LLM 返回 JSON 不是对象"], "raw": raw}

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
