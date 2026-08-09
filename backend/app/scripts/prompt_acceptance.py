"""提示词输出采集脚本。

用法：
    cd backend
    .venv/bin/python -m app.scripts.prompt_acceptance

依赖 .env 中 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL（config.py 提供默认值）。
对 9 个 golden 用例逐一调用真实 LLM（温度 0 + 网络重试），采集原始输出，
生成 Markdown 报告（docs/prompts/prompt-acceptance-report.md），
报告只展示：提示词、输入句子、实际输出（完整原始 JSON）、每条耗时。
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

_REPORT_PATH = Path(__file__).resolve().parents[2] / "docs" / "prompts" / "prompt-acceptance-report.md"


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


async def run_case(llm_call, case: dict) -> dict:
    """采集单个用例的 LLM 输出。返回 {id, input, output, elapsed, error}。"""
    case_id = case["id"]
    case_input = case.get("input", "")
    started = time.monotonic()
    raw = ""
    last_exc = None
    for attempt in range(2):
        try:
            raw = await llm_call(build_messages(case_input))
            break
        except Exception as exc:  # noqa: BLE001 - 采集脚本需兜底所有网络/HTTP 异常
            last_exc = exc
    elapsed = round(time.monotonic() - started, 1)
    if not raw:
        return {"id": case_id, "input": case_input, "output": "", "elapsed": elapsed, "error": f"LLM 调用失败: {last_exc}"}
    return {"id": case_id, "input": case_input, "output": raw, "elapsed": elapsed, "error": None}


async def run_acceptance(llm_call, cases: list[dict]) -> dict:
    """跑全部用例，返回 {total, results, elapsed, prompt, model}。"""
    started = time.monotonic()
    results = [await run_case(llm_call, case) for case in cases]
    return {
        "total": len(results),
        "results": results,
        "elapsed": round(time.monotonic() - started, 1),
        "prompt": SYSTEM_PROMPT,
        "model": get_settings().LLM_MODEL,
    }


def _render_report(summary: dict) -> str:
    lines: list[str] = []
    lines.append("# 提示词输出采集报告（Prompt Output Report）")
    lines.append("")
    lines.append(f"- **模型**：`{summary['model']}`")
    lines.append(f"- **用例数**：{summary['total']}")
    lines.append(f"- **总耗时**：{summary['elapsed']} 秒")
    lines.append("")
    lines.append("## 一、测试提示词（SYSTEM_PROMPT）")
    lines.append("")
    lines.append("```text")
    lines.append(summary["prompt"])
    lines.append("```")
    lines.append("")
    lines.append("## 二、测试用例与实际输出")
    lines.append("")
    for r in summary["results"]:
        lines.append(f"### {r['id']}（耗时 {r['elapsed']}s）")
        lines.append("")
        lines.append(f"**输入**：{r['input']}")
        lines.append("")
        if r.get("error"):
            lines.append(f"**输出**：（采集失败）{r['error']}")
            lines.append("")
            continue
        lines.append("**输出**：")
        lines.append("")
        lines.append("```json")
        lines.append(r["output"])
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def write_report(summary: dict) -> str:
    """生成并保存 Markdown 报告。返回报告路径。"""
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text(_render_report(summary), encoding="utf-8")
    return str(_REPORT_PATH)


async def main() -> int:
    cases = load_golden_cases()
    summary = await run_acceptance(_call_llm, cases)
    report_path = write_report(summary)
    print(f"\n=== 采集完成：{summary['total']} 条用例，总耗时 {summary['elapsed']}s ===")
    for r in summary["results"]:
        status = "OK " if r.get("error") is None else "ERR"
        print(f"[{status}] {r['id']} ({r['elapsed']}s)")
    print(f"\n报告已生成：{report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
