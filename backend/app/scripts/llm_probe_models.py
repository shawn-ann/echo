"""百炼多模型可用性 + 思考参数能力探测脚本。

对候选模型逐个发最小纠错请求，确认：
- 模型是否可用（HTTP 200 / 404 模型不存在 / 401 鉴权失败 / 400 参数不兼容）
- 思考参数支持情况（thinking: disabled / thinking: enabled / 忽略 / 报错）
- Qwen 额外探测 enable_thinking 参数

用法：
    cd backend
    .venv/bin/python -m app.scripts.llm_probe_models \
        --base-url <百炼 openai 兼容 endpoint> \
        --api-key <key> \
        --out docs/prompts/model-probe-report.md

输出：控制台表格 + Markdown 探测报告。
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx

from app.prompts.correction_prompt import build_system_prompt
from app.prompts.golden_cases import load_golden_cases

# 候选模型清单：id + 显示名 + 特殊探测参数
MODELS = [
    {"id": "qwen3.7-flash", "name": "Qwen3.7 Flash", "extra_params": ["enable_thinking"]},
    {"id": "qwen3.7-plus", "name": "Qwen3.7 Plus", "extra_params": ["enable_thinking"]},
    {"id": "qwen3.8-max", "name": "Qwen3.8 Max", "extra_params": ["enable_thinking"]},
    {"id": "deepseek-v4-flash-0731", "name": "DeepSeek V4 Flash", "extra_params": []},
    {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "extra_params": []},
    {"id": "glm-5.2", "name": "GLM 5.2", "extra_params": []},
    {"id": "kimi/kimi-k3", "name": "Kimi K3", "extra_params": []},
    {"id": "MiniMax/MiniMax-M3", "name": "MiniMax M3", "extra_params": []},
]

PROBE_TEXT = "Correct the trigger_by field set up logic when creating job."


async def _probe(base_url: str, api_key: str, model_id: str, extra: dict) -> tuple[int, float, str]:
    """发一条探测请求。返回 (status, elapsed, snippet)。"""
    url = base_url.rstrip("/") + "/chat/completions"
    messages = [
        {"role": "system", "content": build_system_prompt("casual")},
        {"role": "user", "content": PROBE_TEXT},
    ]
    body = {"model": model_id, "messages": messages, "temperature": 0, **extra}
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json=body,
            )
            elapsed = round(time.monotonic() - started, 1)
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                return r.status_code, elapsed, content[:120]
            return r.status_code, elapsed, r.text[:120]
    except Exception as exc:  # noqa: BLE001 - 探测需兜底网络/超时
        elapsed = round(time.monotonic() - started, 1)
        return 0, elapsed, f"{type(exc).__name__}: {exc}"


async def probe_model(base_url: str, api_key: str, m: dict) -> dict:
    """探测单模型：可用性 + 思考参数能力。"""
    model_id = m["id"]
    result = {"id": model_id, "name": m["name"], "available": False, "thinking": "unknown", "detail": {}}

    # 1. 基线：不带思考参数（默认行为）
    status, elapsed, snippet = await _probe(base_url, api_key, model_id, {})
    result["detail"]["default"] = {"status": status, "elapsed": elapsed, "snippet": snippet}
    if status != 200:
        result["detail"]["default_error"] = snippet
        return result  # 模型不可用

    result["available"] = True

    # 2. thinking disabled
    status, elapsed, snippet = await _probe(base_url, api_key, model_id, {"thinking": {"type": "disabled"}})
    result["detail"]["thinking_disabled"] = {"status": status, "elapsed": elapsed, "snippet": snippet}

    # 3. thinking enabled
    status, elapsed, snippet = await _probe(base_url, api_key, model_id, {"thinking": {"type": "enabled"}})
    result["detail"]["thinking_enabled"] = {"status": status, "elapsed": elapsed, "snippet": snippet}

    # 4. 判定思考能力
    off_ok = result["detail"]["thinking_disabled"]["status"] == 200
    on_ok = result["detail"]["thinking_enabled"]["status"] == 200
    if on_ok and off_ok:
        result["thinking"] = "both"  # 开启+关闭都支持
    elif off_ok and not on_ok:
        result["thinking"] = "disabled_only"
    elif on_ok and not off_ok:
        result["thinking"] = "enabled_only"
    else:
        result["thinking"] = "unsupported"  # 都不支持显式设置（忽略/报错）

    # 5. Qwen 额外探测 enable_thinking
    if m.get("extra_params"):
        for param in m["extra_params"]:
            for val in (False, True):
                status, elapsed, snippet = await _probe(base_url, api_key, model_id, {param: val})
                result["detail"][f"{param}_{val}"] = {"status": status, "elapsed": elapsed, "snippet": snippet}

    return result


def _render_report(results: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# 百炼多模型探测报告（Model Probe Report）")
    lines.append("")
    lines.append("| 模型 | 可用 | 思考支持 | 默认耗时(s) | 备注 |")
    lines.append("|------|------|---------|-----------|------|")
    for r in results:
        avail = "✅" if r["available"] else "❌"
        detail = r.get("detail", {})
        default = detail.get("default", {})
        note = detail.get("default_error", "—")
        lines.append(f"| `{r['id']}` | {avail} | {r['thinking']} | {default.get('elapsed', '—')} | {note[:40]} |")
    lines.append("")
    lines.append("## 探测详情")
    lines.append("")
    for r in results:
        lines.append(f"### `{r['id']}`（{r['name']}）")
        lines.append("")
        for k, v in r.get("detail", {}).items():
            if isinstance(v, str):
                lines.append(f"- `{k}`：{v[:80]}")
                continue
            status = v.get("status")
            mark = "✅" if status == 200 else "❌"
            snippet = (v.get("snippet") or "")[:60].replace("\n", " ")
            lines.append(f"- `{k}`：{mark} status={status} 耗时{v.get('elapsed')}s `{snippet}`")
        lines.append("")
    return "\n".join(lines)


def write_report(results: list[dict], out: str) -> str:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_report(results), encoding="utf-8")
    return str(path)


async def main() -> int:
    parser = argparse.ArgumentParser(description="百炼多模型探测")
    parser.add_argument("--base-url", required=True, help="百炼 openai 兼容 endpoint")
    parser.add_argument("--api-key", required=True, help="百炼 API key")
    parser.add_argument("--out", default="docs/prompts/model-probe-report.md", help="探测报告输出路径")
    args = parser.parse_args()

    results = []
    for m in MODELS:
        print(f"探测 {m['id']} ...")
        r = await probe_model(args.base_url, args.api_key, m)
        results.append(r)
        print(f"  -> 可用={r['available']} 思考={r['thinking']}")

    out = write_report(results, args.out)
    print(f"\n探测报告已生成：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
