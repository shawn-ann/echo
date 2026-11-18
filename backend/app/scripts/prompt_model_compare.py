"""多模型纠错对比脚本：读各模型采集 JSON，按 golden 命中率打分，生成对比报告。

用法：
    cd backend
    .venv/bin/python -m app.scripts.prompt_model_compare \
        --jsons docs/prompts/prompt-multimodel-qwen3_7-flash-disabled.json ... \
        --out docs/prompts/model-comparison.md

每个 JSON 由 prompt_acceptance.py 生成（含 model/thinking/elapsed/results）。
打分：对每用例的 golden must_have（fragment_contains），LLM errors 中是否命中（CI 子串）。
退出码 0。
"""

import argparse
import json
import sys
from pathlib import Path

from app.prompts.golden_cases import load_golden_cases


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"找不到数据文件：{p}")
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def _ci(text: str) -> str:
    return text.lower().replace("`", "")


_STOPWORDS = {
    "a", "an", "the", "to", "when", "of", "in", "on", "for", "and", "or", "is",
    "are", "was", "were", "have", "has", "had", "do", "does", "did", "be", "been",
    "that", "this", "these", "those", "with", "by", "at", "from", "it", "its",
}


def _content_words(text: str) -> list[str]:
    """提取文本的内容词（非停用词、长度>1）。"""
    return [w for w in text.split() if w not in _STOPWORDS and len(w) > 1]


def _summarize_output(raw: str) -> dict:
    try:
        payload = json.loads(raw)
        correction = payload.get("correction") or payload
    except json.JSONDecodeError:
        return {"error": "非合法 JSON", "learnings": 0, "errors": [], "ok": False}
    errors = correction.get("errors") or []
    learnings = correction.get("learnings") or []
    return {
        "errors": [
            {"category": e.get("category") or e.get("error_type"), "correction": e.get("correction")}
            for e in errors
        ],
        "learnings": len(learnings),
        "ok": True,
    }


def _case_hit_rate(case_id: str, summary: dict, case_map: dict) -> tuple[int, int]:
    """返回 (命中数, 总数)。

    匹配规则（任一命中即算）：
    1. golden 片段是 LLM fragment 的子串
    2. LLM fragment 是 golden 片段的子串
    3. golden 内容词（去停用词）任一在 LLM fragment 中
    """
    expect = case_map.get(case_id, {}).get("expect", {})
    must_have = expect.get("must_have", [])
    total = len(must_have)
    if total == 0:
        return 0, 0
    errors = summary.get("errors", [])
    fragments = [_ci(e.get("fragment", "")) for e in errors]
    hit = 0
    for must in must_have:
        needle = _ci(must.get("fragment_contains", ""))
        if not needle:
            continue
        words = _content_words(needle)
        matched = any(
            needle in f or f in needle or any(w in f for w in words)
            for f in fragments
        )
        if matched:
            hit += 1
    return hit, total


def _render_compare(items: list[dict], cases: list[dict]) -> str:
    case_map = {c["id"]: c for c in cases}
    lines: list[str] = []
    lines.append("# 多模型纠错对比报告（Model Comparison）")
    lines.append("")
    lines.append(f"- **用例数**：{len(cases)}")
    lines.append("- **命中规则**：golden 错误片段与 LLM fragment 双向子串，或 golden 内容词（去停用词）任一在 LLM fragment 中，即算该 must_have 命中")
    lines.append("")
    lines.append("## 一、总览")
    lines.append("")
    lines.append("| 模型 | 思考 | 总耗时(s) | 平均/用例(s) | 命中率 | learnings 总数 |")
    lines.append("|------|------|----------|-------------|--------|---------------|")
    for it in sorted(items, key=lambda x: (-x["hit"], x["elapsed"])):
        lines.append(
            f"| `{it['model']}` | {it['thinking']} | {it['elapsed']} | "
            f"{it['avg']} | {it['hit']}/{it['total']} | {it['learnings']} |"
        )
    lines.append("")
    lines.append("## 二、逐用例对比")
    lines.append("")
    for case in cases:
        cid = case["id"]
        lines.append(f"### {cid}")
        lines.append("")
        lines.append("| 模型 | 思考 | 耗时(s) | 命中 | 识别错误数 | learnings | 错误列表 |")
        lines.append("|------|------|--------|------|-----------|-----------|---------|")
        for it in items:
            c = it["cases"].get(cid)
            if not c:
                continue
            errs = "；".join(
                f"{e.get('category') or e.get('error_type')}→{e.get('correction')}"
                for e in c["errors"]
            ) or "（无）"
            lines.append(
                f"| `{it['model']}` | {it['thinking']} | {c['elapsed']} | "
                f"{c['hit']}/{c['total']} | {len(c['errors'])} | {c['learnings']} | {errs[:80]} |"
            )
        lines.append("")
    lines.append("## 三、总结")
    lines.append("")
    lines.append("- **最准**（命中率最高）：见 §一 排序，命中率越高识别 golden 错误越全。")
    lines.append("- **最快**（平均耗时最低）：见 §一 平均/用例列。")
    lines.append("- **综合建议**：结合命中率与耗时，选取纠错场景最均衡的模型/思考模式。")
    lines.append("")
    return "\n".join(lines)


def write_report(items: list[dict], out: str, cases: list[dict]) -> str:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_compare(items, cases), encoding="utf-8")
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="多模型对比")
    parser.add_argument("--jsons", nargs="+", required=True, help="各模型的采集 JSON 路径")
    parser.add_argument("--out", default="docs/prompts/model-comparison.md", help="对比报告输出路径")
    args = parser.parse_args()

    cases = load_golden_cases()
    case_map = {c["id"]: c for c in cases}

    items = []
    for path in args.jsons:
        data = _load_json(path)
        model = data.get("model", "?")
        thinking = data.get("thinking", "?")
        total = data.get("total", 0)
        elapsed = data.get("elapsed", 0)
        hit_total = 0
        hit_count = 0
        learnings_total = 0
        per_case = {}
        for r in data.get("results", []):
            cid = r.get("id", "?")
            raw = r.get("output", "")
            summary = _summarize_output(raw)
            h, t = _case_hit_rate(cid, summary, case_map)
            hit_total += t
            hit_count += h
            learnings_total += summary.get("learnings", 0)
            per_case[cid] = {
                "elapsed": r.get("elapsed", 0),
                "errors": summary.get("errors", []),
                "learnings": summary.get("learnings", 0),
                "hit": h,
                "total": t,
            }
        items.append({
            "model": model,
            "thinking": thinking,
            "elapsed": elapsed,
            "avg": round(elapsed / total, 1) if total else 0,
            "hit": hit_count,
            "total": hit_total,
            "learnings": learnings_total,
            "cases": per_case,
        })

    out = write_report(items, args.out, cases)
    print(f"对比报告已生成：{out}")
    for it in sorted(items, key=lambda x: (-x["hit"], x["elapsed"])):
        print(f"  {it['model']} ({it['thinking']}): 命中 {it['hit']}/{it['total']}, 耗时 {it['elapsed']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
