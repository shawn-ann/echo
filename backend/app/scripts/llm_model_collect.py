"""多模型纠错采集脚本：串行跑「模型 × 思考模式」组合的 9 个 golden 用例。

用法：
    cd backend
    .venv/bin/python -m app.scripts.llm_model_collect \
        --base-url <百炼 endpoint> --api-key <key>

可用模型（探测确认）与思考模式组合在此配置。每个组合产出：
docs/prompts/prompt-multimodel-<name>-<thinking>.json
"""

import argparse
import asyncio
import sys

from app.core.config import get_settings
from app.prompts.golden_cases import load_golden_cases
from app.scripts.prompt_acceptance import _call_llm, run_acceptance, write_report

# 模型 ID -> (显示名, 思考模式列表)
MODEL_COMBOS = {
    "qwen3.7-flash": ("qwen-flash", ["disabled", "enabled"]),
    "qwen3.7-plus": ("qwen-plus", ["disabled", "enabled"]),
    "qwen3.8-max": ("qwen-max", ["disabled", "enabled"]),
    "deepseek-v4-flash-0731": ("deepseek-flash", ["disabled", "enabled"]),
    "deepseek-v4-pro": ("deepseek-pro", ["disabled", "enabled"]),
    "glm-5.2": ("glm-5.2", ["disabled", "enabled"]),
}


async def main() -> int:
    parser = argparse.ArgumentParser(description="多模型纠错采集")
    parser.add_argument("--base-url", required=True, help="百炼 openai 兼容 endpoint")
    parser.add_argument("--api-key", required=True, help="百炼 API key")
    args = parser.parse_args()

    cases = load_golden_cases()
    style = get_settings().CORRECTION_STYLE

    total_start = None
    for model_id, (name, thinkings) in MODEL_COMBOS.items():
        for thinking in thinkings:
            print(f"\n=== 采集 {model_id} ({thinking}) ... ===", flush=True)
            summary = await run_acceptance(
                _call_llm, cases, style=style, thinking=thinking,
                base_url=args.base_url, api_key=args.api_key, model=model_id,
            )
            report_path = f"docs/prompts/prompt-multimodel-{name}-{thinking}.md"
            write_report(summary, report_path)
            json_path = report_path.rsplit(".", 1)[0] + ".json"
            print(f"  -> {summary['elapsed']}s，报告 {report_path}，数据 {json_path}", flush=True)

    print("\n=== 全部采集完成 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
