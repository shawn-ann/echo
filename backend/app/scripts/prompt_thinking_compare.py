"""纠错 LLM 思考模式对比脚本：读思考开启/关闭两份采集 JSON，生成对比报告。

用法：
    cd backend
    .venv/bin/python -m app.scripts.prompt_thinking_compare \
        --on docs/prompts/prompt-acceptance-thinking-on.json \
        --off docs/prompts/prompt-acceptance-thinking-off.json \
        --out docs/prompts/prompt-thinking-comparison.md

依赖两份由 prompt_acceptance.py 生成的 JSON 数据文件（含 thinking/elapsed/results）。
退出码 0。
"""

import argparse
import json
import sys
from pathlib import Path

from app.core.config import get_settings


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"找不到数据文件：{p}")
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def _summarize_result(raw: str) -> dict:
    """从 LLM 原始输出提取纠错摘要：errors 集合与 learnings 条数。"""
    try:
        payload = json.loads(raw)
        correction = payload.get("correction") or payload
    except json.JSONDecodeError:
        return {"error": "非合法 JSON", "learnings": 0, "errors": []}
    errors = correction.get("errors") or []
    learnings = correction.get("learnings") or []
    return {
        "errors": [
            {"category": e.get("category") or e.get("error_type"), "correction": e.get("correction")}
            for e in errors
        ],
        "learnings": len(learnings),
    }


def _render_compare(on: dict, off: dict) -> str:
    lines: list[str] = []
    lines.append("# 纠错 LLM 思考模式对比报告（Thinking Mode Comparison）")
    lines.append("")
    lines.append(f"- **模型**：`{on.get('model', get_settings().LLM_MODEL)}` · 场景：{on.get('style', 'casual')}")
    lines.append(f"- **思考开启**：总耗时 {on.get('elapsed', 0)}s（{on.get('total', 0)} 条）")
    lines.append(f"- **思考关闭**：总耗时 {off.get('elapsed', 0)}s（{off.get('total', 0)} 条）")
    on_elapsed = on.get("elapsed", 0) or 1
    speedup = round((on_elapsed - off.get("elapsed", 0)) / on_elapsed * 100, 1)
    lines.append(f"- **整体提速**：{speedup}%")
    lines.append("")
    lines.append("## 一、逐用例耗时对比")
    lines.append("")
    lines.append("| 用例 | 思考开启(s) | 思考关闭(s) | 差异(s) | 提速% |")
    lines.append("|---|---|---|---|---|")
    on_by_id = {r["id"]: r for r in on.get("results", [])}
    off_by_id = {r["id"]: r for r in off.get("results", [])}
    for r in on.get("results", []):
        rid = r["id"]
        off_r = off_by_id.get(rid)
        on_el = r.get("elapsed", 0)
        off_el = off_r.get("elapsed", 0) if off_r else 0
        diff = round(off_el - on_el, 1)
        sp = round((on_el - off_el) / on_el * 100, 1) if on_el else 0
        lines.append(f"| {rid} | {on_el} | {off_el} | {diff} | {sp}% |")
    lines.append("")
    lines.append("## 二、逐用例纠错结果对比")
    lines.append("")
    for r in on.get("results", []):
        rid = r["id"]
        off_r = off_by_id.get(rid)
        if r.get("error") or (off_r and off_r.get("error")):
            lines.append(f"### {rid}")
            lines.append("")
            lines.append(f"- 思考开启：{'采集失败' if r.get('error') else '正常'}")
            lines.append(f"- 思考关闭：{'采集失败' if (off_r and off_r.get('error')) else '正常'}")
            lines.append("")
            continue
        on_s = _summarize_result(r.get("output", ""))
        off_s = _summarize_result(off_r.get("output", "")) if off_r else {"errors": [], "learnings": 0}
        same_errors = on_s["errors"] == off_s["errors"]
        lines.append(f"### {rid}")
        lines.append("")
        lines.append(f"- **思考开启**：errors {len(on_s['errors'])} 条、learnings {on_s['learnings']} 条")
        for e in on_s["errors"]:
            lines.append(f"  - {e.get('category') or e.get('error_type')}: → {e.get('correction')}")
        lines.append(f"- **思考关闭**：errors {len(off_s['errors'])} 条、learnings {off_s['learnings']} 条")
        for e in off_s["errors"]:
            lines.append(f"  - {e.get('category') or e.get('error_type')}: → {e.get('correction')}")
        lines.append(f"- **差异**：{'错误识别一致 ✅' if same_errors else '错误识别不一致 ⚠️'}")
        lines.append("")
    lines.append("## 三、总结")
    lines.append("")
    lines.append(f"- **提速**：关闭思考整体耗时减少 {speedup}%（{on.get('elapsed',0)}s → {off.get('elapsed',0)}s）")
    lines.append("- **质量**：见 §二 逐用例差异；关闭思考后错误识别是否一致、learnings 完整度需结合用例评估。")
    lines.append("- **建议**：若关闭思考在可接受耗时内识别质量不降，可默认关闭思考以提速；否则权衡。")
    lines.append("")
    return "\n".join(lines)


def write_compare(on: dict, off: dict, out: str) -> str:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_compare(on, off), encoding="utf-8")
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="思考模式对比")
    parser.add_argument("--on", required=True, help="思考开启的采集 JSON")
    parser.add_argument("--off", required=True, help="思考关闭的采集 JSON")
    parser.add_argument("--out", default="docs/prompts/prompt-thinking-comparison.md", help="对比报告输出路径")
    args = parser.parse_args()

    on = _load_json(args.on)
    off = _load_json(args.off)
    out = write_compare(on, off, args.out)
    print(f"对比报告已生成：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
