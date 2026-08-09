"""真实 LLM 冒烟脚本：发一条英文纠错请求，验证真实调用链路与提示词效果。

用法：
    cd backend
    .venv/bin/python -m app.scripts.llm_smoke                # 用 .env 配置真实调用
    .venv/bin/python -m app.scripts.llm_smoke --text "She go to school yesterday."

依赖 .env 中 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL（config.py 提供默认值）。
注意：不要设 LLM_MODE=mock（否则走 MockLLMClient）。退出码 0=成功，1=失败。
"""

import argparse
import asyncio

from app.core.config import get_settings
from app.prompts.correction_prompt import build_system_prompt
from app.services.llm_client import get_llm_client


def build_smoke_messages(input_text: str, style: str = "casual") -> list[dict]:
    """构建冒烟 messages：system prompt（按场景）+ 用户原文。"""
    return [
        {"role": "system", "content": build_system_prompt(style)},
        {"role": "user", "content": input_text},
    ]


async def run_smoke(llm_call, input_text: str, style: str) -> dict:
    """用给定 llm_call 跑一次纠错。返回 {ok, raw, error}。"""
    try:
        raw = await llm_call(build_smoke_messages(input_text, style))
        return {"ok": True, "raw": raw, "error": None}
    except Exception as exc:  # noqa: BLE001 - 冒烟脚本需兜底所有异常
        return {"ok": False, "raw": "", "error": f"{type(exc).__name__}: {exc}"}


async def main() -> int:
    parser = argparse.ArgumentParser(description="真实 LLM 纠错冒烟")
    parser.add_argument("--text", default="She go to school yesterday.", help="要纠错的英文文本")
    args = parser.parse_args()

    settings = get_settings()
    client = get_llm_client()
    result = await run_smoke(client.complete, args.text, settings.CORRECTION_STYLE)

    if result["ok"]:
        print("=== 冒烟成功 ===")
        print(result["raw"])
        return 0
    print("=== 冒烟失败 ===")
    print(result["error"])
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
