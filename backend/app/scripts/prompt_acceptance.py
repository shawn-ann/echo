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
from app.prompts.correction_prompt import build_system_prompt
from app.prompts.golden_cases import load_golden_cases

_REPORT_PATH = Path(__file__).resolve().parents[2] / "docs" / "prompts" / "prompt-acceptance-report.md"


def build_messages(input_text: str, style: str = "casual") -> list[dict]:
    """构建发给 LLM 的 messages：system prompt（按场景）+ 用户原文。"""
    return [
        {"role": "system", "content": build_system_prompt(style)},
        {"role": "user", "content": input_text},
    ]


async def _call_llm(messages: list[dict], thinking: str = "disabled") -> str:
    """调用 OpenAI 兼容 Chat Completions API，返回 content 字符串。

    thinking: "enabled"（思考开启，deepseek 默认）/ "disabled"（思考关闭）。
    注意：deepseek 思考开启时不支持 temperature（无效但报错不触发）。
    """
    settings = get_settings()
    if not settings.LLM_BASE_URL or not settings.LLM_API_KEY:
        print("请先在 .env 配置 LLM_BASE_URL 与 LLM_API_KEY")
        sys.exit(1)
    url = settings.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            json={
                "model": settings.LLM_MODEL,
                "messages": messages,
                "temperature": 0,
                "thinking": {"type": thinking},
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def run_case(llm_call, case: dict, style: str = "casual", thinking: str = "disabled") -> dict:
    """采集单个用例的 LLM 输出。返回 {id, input, output, elapsed, error, note}。"""
    case_id = case["id"]
    case_input = case.get("input", "")
    note = case.get("note")
    started = time.monotonic()
    raw = ""
    last_exc = None
    for attempt in range(3):
        try:
            raw = await llm_call(build_messages(case_input, style), thinking)
            break
        except Exception as exc:  # noqa: BLE001 - 采集脚本需兜底所有网络/HTTP 异常
            last_exc = exc
    elapsed = round(time.monotonic() - started, 1)
    if not raw:
        detail = f"{type(last_exc).__name__}: {last_exc}" if last_exc else "未知错误"
        return {"id": case_id, "input": case_input, "output": "", "elapsed": elapsed, "error": f"LLM 调用失败: {detail}", "note": note}
    return {"id": case_id, "input": case_input, "output": raw, "elapsed": elapsed, "error": None, "note": note}


async def run_acceptance(llm_call, cases: list[dict], style: str = "casual", thinking: str = "disabled") -> dict:
    """跑全部用例，返回 {total, results, elapsed, prompt, model, style, thinking}。"""
    started = time.monotonic()
    results = [await run_case(llm_call, case, style, thinking) for case in cases]
    return {
        "total": len(results),
        "results": results,
        "elapsed": round(time.monotonic() - started, 1),
        "prompt": build_system_prompt(style),
        "model": get_settings().LLM_MODEL,
        "style": style,
        "thinking": thinking,
    }


def _format_output(raw: str) -> str:
    """若 raw 是合法 JSON，格式化为缩进形式；否则原样返回。"""
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return raw


def _render_report(summary: dict) -> str:
    lines: list[str] = []
    lines.append("# 提示词输出采集报告（Prompt Output Report）")
    lines.append("")
    lines.append(f"- **模型**：`{summary['model']}`")
    lines.append(f"- **思考模式**：{summary['thinking']}（{'开启' if summary['thinking'] == 'enabled' else '关闭'}）")
    lines.append(f"- **场景**：{summary['style']}（{'日常/职场口语' if summary['style'] == 'casual' else '正式书面'}）")
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
        if r.get("note"):
            lines.append("")
            lines.append(f"**说明**：{r['note']}")
        lines.append("")
        if r.get("error"):
            lines.append(f"**输出**：（采集失败）{r['error']}")
            lines.append("")
            continue
        lines.append("**输出**：")
        lines.append("")
        lines.append("```json")
        lines.append(_format_output(r["output"]))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _json_path(report_path: str) -> str:
    """由 Markdown 报告路径推导 JSON 数据文件路径。"""
    return report_path.rsplit(".", 1)[0] + ".json"


def write_report(summary: dict, report_path: str | None = None) -> str:
    """生成并保存 Markdown 报告（及同目录 JSON 数据文件）。返回报告路径。"""
    path = Path(report_path) if report_path else _REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_report(summary), encoding="utf-8")
    # 同时输出机器可读 JSON（供对比脚本使用）
    _json_path(str(path)).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return str(path)


async def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="提示词输出采集")
    parser.add_argument("--thinking", choices=["enabled", "disabled"], default="disabled",
                        help="思考模式（deepseek 默认 enabled；本需求对比关闭）")
    parser.add_argument("--report", default=str(_REPORT_PATH), help="报告输出路径")
    args = parser.parse_args()

    cases = load_golden_cases()
    style = get_settings().CORRECTION_STYLE
    summary = await run_acceptance(_call_llm, cases, style=style, thinking=args.thinking)
    report_path = write_report(summary, args.report)
    print(f"\n=== 采集完成：{summary['total']} 条用例（场景 {style}，思考 {args.thinking}），总耗时 {summary['elapsed']}s ===")
    for r in summary["results"]:
        status = "OK " if r.get("error") is None else "ERR"
        print(f"[{status}] {r['id']} ({r['elapsed']}s)")
    print(f"\n报告已生成：{report_path}")
    print(f"数据文件：{_json_path(report_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
