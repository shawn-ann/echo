"""
基于 ground_truth 基准评估各模型输出质量。
匹配规则：模糊匹配（内容词重叠/子串），不要求字符级完全一致。
"""
import json
import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "prompts"
GOLDEN_PATH = Path(__file__).resolve().parent.parent / "prompts" / "golden_cases.json"
REPORT_PATH = PROMPTS_DIR / "ground-truth-eval-report.md"

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "for",
    "and", "or", "but", "when", "by", "this", "that", "it", "we", "you",
    "should", "be", "have", "has", "been", "not", "now", "some", "if",
}

ERROR_TYPE_GROUPS = [
    {"冠词缺失"},
    {"词性误用", "用词不当", "词性错误"},
    {"主谓不一致"},
    {"不可数名词误用"},
    {"不定式错误", "不定式误用", "动词形式错误", "不定式后动词形式错误"},
    {"拼写错误"},
    {"搭配冗余"},
    {"逗号拼接", "逗号连接独立子句", "逗号粘连", "逗号连接"},
    {"单复数错误", "单复数不一致", "数不一致", "名词单复数错误"},
    {"语域错配"},
    {"介词缺失"},
    {"词序不当", "语序不当"},
    {"搭配不当"},
    {"中式直译"},
]


def _content_words(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z_]+", text.lower())
    return {t for t in tokens if t not in STOP_WORDS and len(t) > 1}


def _fragment_match(gt_fragment: str, model_fragment: str) -> bool:
    """模糊匹配：子串/去空格子串/全部内容词包含。"""
    gt_low = gt_fragment.lower().strip()
    mf_low = model_fragment.lower().strip()
    if not gt_low or not mf_low:
        return False
    # 1. 子串匹配
    if gt_low in mf_low or mf_low in gt_low:
        return True
    # 2. 去空格子串（处理 set up vs setup）
    gt_nospace = gt_low.replace(" ", "")
    mf_nospace = mf_low.replace(" ", "")
    if len(gt_nospace) > 2 and len(mf_nospace) > 2:
        if gt_nospace in mf_nospace or mf_nospace in gt_nospace:
            return True
    # 3. 全部内容词包含（不是任一重叠）
    gt_words = _content_words(gt_fragment)
    mf_words = _content_words(model_fragment)
    if gt_words and gt_words.issubset(mf_words):
        return True
    return False


def _error_type_match(gt_type: str, model_type: str) -> bool:
    if gt_type == model_type:
        return True
    for group in ERROR_TYPE_GROUPS:
        if gt_type in group and model_type in group:
            return True
    return False


def _correction_direction_match(gt_corr: str, model_corr: str) -> bool:
    """检查修正方向是否一致（关键词重叠）。"""
    gt_words = _content_words(gt_corr)
    mf_words = _content_words(model_corr)
    if not gt_words:
        return True
    overlap = gt_words & mf_words
    return len(overlap) >= 1


def _load_model_results(filepath: Path) -> tuple[list[dict], str, str, str]:
    data = json.loads(filepath.read_text(encoding="utf-8"))
    # 从文件名提取版本标记（如 v2, v3）
    stem = filepath.stem  # e.g. prompt-multimodel-glm-5.2-disabled-v3
    ver = ""
    m = re.search(r"-(v\d+)$", stem)
    if m:
        ver = m.group(1)
    model_label = data.get("model", "?")
    if ver:
        model_label = f"{model_label}({ver})"
    results = []
    for r in data["results"]:
        try:
            parsed = json.loads(r["output"])
        except (json.JSONDecodeError, TypeError):
            parsed = {"intent": "error", "correction": None}
        results.append({
            "id": r["id"],
            "parsed": parsed,
            "elapsed": r.get("elapsed"),
        })
    prompt = data.get("prompt", "")
    return results, model_label, data.get("thinking", "?"), prompt


def _extract_errors(parsed: dict) -> list[dict]:
    corr = parsed.get("correction")
    if not corr or not isinstance(corr, dict):
        return []
    return corr.get("errors", []) or []


def _eval_case(gt: dict, model_errors: list[dict]) -> dict:
    required = gt.get("required_errors", [])
    optional = gt.get("optional_errors", [])

    matched_required = []
    missed_required = []
    used_model_indices: set[int] = set()

    for gt_err in required:
        gt_frag = gt_err["fragment"]
        gt_len = len(gt_frag)
        # Pass 1: fragment match + type match
        best_idx = None
        for i, me in enumerate(model_errors):
            if i in used_model_indices:
                continue
            if _fragment_match(gt_frag, me.get("fragment", "")):
                if _error_type_match(gt_err["error_type"], me.get("error_type", "")):
                    best_idx = i
                    break
        # Pass 2: fragment match only, prefer shorter fragments (more precise)
        if best_idx is None:
            candidates = []
            for i, me in enumerate(model_errors):
                if i in used_model_indices:
                    continue
                mf = me.get("fragment", "")
                if _fragment_match(gt_frag, mf):
                    # Skip very long fragments with mismatched type (likely different error)
                    if len(mf) > gt_len * 3 and not _error_type_match(gt_err["error_type"], me.get("error_type", "")):
                        continue
                    candidates.append((i, len(mf)))
            if candidates:
                # Prefer shortest fragment (most precise match)
                candidates.sort(key=lambda x: x[1])
                best_idx = candidates[0][0]
        if best_idx is not None:
            used_model_indices.add(best_idx)
            me = model_errors[best_idx]
            type_ok = _error_type_match(gt_err["error_type"], me.get("error_type", ""))
            corr_ok = _correction_direction_match(gt_err["correction"], me.get("correction", ""))
            matched_required.append({
                "gt_fragment": gt_frag,
                "gt_type": gt_err["error_type"],
                "model_fragment": me.get("fragment", ""),
                "model_type": me.get("error_type", ""),
                "type_match": type_ok,
                "corr_match": corr_ok,
            })
        else:
            missed_required.append(gt_err)

    matched_optional = []
    for gt_err in optional:
        found_idx = None
        for i, me in enumerate(model_errors):
            if i in used_model_indices:
                continue
            if _fragment_match(gt_err["fragment"], me.get("fragment", "")):
                found_idx = i
                break
        if found_idx is not None:
            used_model_indices.add(found_idx)
            me = model_errors[found_idx]
            matched_optional.append({
                "gt_fragment": gt_err["fragment"],
                "model_fragment": me.get("fragment", ""),
            })

    fabricated = []
    for i, me in enumerate(model_errors):
        if i in used_model_indices:
            continue
        fabricated.append({
            "fragment": me.get("fragment", ""),
            "error_type": me.get("error_type", ""),
            "correction": me.get("correction", ""),
        })

    rewrite_text = ""

    return {
        "required_total": len(required),
        "required_matched": len(matched_required),
        "required_missed": len(missed_required),
        "optional_total": len(optional),
        "optional_matched": len(matched_optional),
        "fabricated_count": len(fabricated),
        "matched_required": matched_required,
        "missed_required": missed_required,
        "matched_optional": matched_optional,
        "fabricated": fabricated,
    }


def main():
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    gt_map = {c["id"]: c.get("ground_truth", {}) for c in golden["cases"]}
    input_map = {c["id"]: c.get("input", "") for c in golden["cases"]}

    model_files = sorted(PROMPTS_DIR.glob("prompt-multimodel-*.json"))

    all_results = []
    prompt_groups: dict[str, list[str]] = {}
    for mf in model_files:
        model_results, model_name, thinking, prompt = _load_model_results(mf)
        case_evals = {}
        for r in model_results:
            cid = r["id"]
            gt = gt_map.get(cid, {})
            model_errors = _extract_errors(r["parsed"])
            case_evals[cid] = _eval_case(gt, model_errors)
        all_results.append({
            "file": mf.name,
            "model": model_name,
            "thinking": thinking,
            "cases": case_evals,
        })
        key = prompt if prompt else "(unknown)"
        prompt_groups.setdefault(key, []).append(f"`{model_name}` {thinking}")

    lines = []
    lines.append("# Ground Truth 评估报告")
    lines.append("")

    # ── 提示词 ──
    lines.append("## 一、测试提示词（System Prompt）")
    lines.append("")
    if len(prompt_groups) == 1:
        prompt_text = list(prompt_groups.keys())[0]
        lines.append("所有模型使用同一提示词：")
        lines.append("")
        lines.append("```text")
        lines.append(prompt_text)
        lines.append("```")
    else:
        lines.append(f"共 {len(prompt_groups)} 个版本的提示词：")
        lines.append("")
        for idx, (prompt_text, models) in enumerate(prompt_groups.items(), 1):
            lines.append(f"### 提示词版本 {idx}（{len(prompt_text)} 字符）")
            lines.append("")
            lines.append("**适用模型**：" + ", ".join(models))
            lines.append("")
            lines.append("```text")
            lines.append(prompt_text)
            lines.append("```")
            lines.append("")

    # ── 评估说明 ──
    lines.append("## 二、评估说明")
    lines.append("")
    lines.append("- **评估基准**：`golden_cases.json` 中 `ground_truth` 字段（required_errors + optional_errors）")
    lines.append("- **匹配规则**：子串/去空格子串/全部内容词包含，长片段+类型不匹配跳过，优先短片段精确匹配")
    lines.append("- **评估维度**：召回率（required 命中）、误报率（fabricated 数量）、错误类型匹配度")
    lines.append("")

    # ── 总览 ──
    lines.append("## 三、总览")
    lines.append("")
    header = "| 模型 | 思考 | required命中 | required遗漏 | optional命中 | 误报总数 | 评估 |"
    sep = "|------|------|:---:|:---:|:---:|:---:|------|"
    lines.append(header)
    lines.append(sep)

    for ar in all_results:
        total_required = sum(c["required_total"] for c in ar["cases"].values())
        total_matched = sum(c["required_matched"] for c in ar["cases"].values())
        total_missed = sum(c["required_missed"] for c in ar["cases"].values())
        total_opt = sum(c["optional_total"] for c in ar["cases"].values())
        total_opt_matched = sum(c["optional_matched"] for c in ar["cases"].values())
        total_fab = sum(c["fabricated_count"] for c in ar["cases"].values())
        recall = f"{total_matched}/{total_required}" if total_required else "N/A"
        verdict = _verdict(total_matched, total_required, total_fab)
        lines.append(
            f"| `{ar['model']}` | {ar['thinking']} | {recall} | {total_missed} | "
            f"{total_opt_matched}/{total_opt} | {total_fab} | {verdict} |"
        )

    # ── 逐用例 ──
    lines.append("")
    lines.append("## 四、逐用例详细评估")
    lines.append("")

    case_ids = [f"C-0{i}" for i in range(1, 10)]
    for cid in case_ids:
        gt = gt_map.get(cid, {})
        req = gt.get("required_errors", [])
        opt = gt.get("optional_errors", [])
        input_text = input_map.get(cid, "")
        lines.append(f"### {cid}")
        lines.append("")
        lines.append(f"**原文**：{input_text}")
        lines.append("")
        lines.append(f"**基准**：required={len(req)}, optional={len(opt)}")
        if req:
            lines.append("")
            lines.append("**必需错误**：")
            for e in req:
                lines.append(f"- `{e['fragment']}` → `{e['correction']}` ({e['error_type']})")
        if opt:
            lines.append("")
            lines.append("**可选错误**：")
            for e in opt:
                lines.append(f"- `{e['fragment']}` → `{e['correction']}` ({e['error_type']})")
        lines.append("")
        lines.append("| 模型 | 思考 | 命中required | 遗漏required | 命中optional | 误报 | 误报详情 |")
        lines.append("|------|------|---|---|---|---|---|")

        for ar in all_results:
            ce = ar["cases"].get(cid, {})
            miss_details = ""
            if ce.get("missed_required"):
                miss_details = ", ".join(f"`{m['fragment']}`" for m in ce["missed_required"])
            fab_details = ""
            if ce.get("fabricated"):
                fab_details = "; ".join(
                    f"`{f['fragment']}`({f['error_type']})" for f in ce["fabricated"]
                )
            hit_req = ce.get("required_matched", 0)
            miss_req = ce.get("required_missed", 0)
            hit_opt = ce.get("optional_matched", 0)
            fab_count = ce.get("fabricated_count", 0)

            type_issues = ""
            for mr in ce.get("matched_required", []):
                if not mr["type_match"]:
                    type_issues += f"⚠️ `{mr['gt_fragment']}` 类型不符(gt:{mr['gt_type']} vs model:{mr['model_type']}); "
            if type_issues:
                fab_details = type_issues + fab_details

            lines.append(
                f"| `{ar['model']}` | {ar['thinking']} | {hit_req}/{ce.get('required_total',0)} | "
                f"{miss_details or '—'} | {hit_opt} | "
                f"{fab_count}{'⚠️' if fab_count else ''} | {fab_details or '—'} |"
            )
        lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已生成：{REPORT_PATH}")


def _verdict(matched: int, total: int, fabricated: int) -> str:
    if total == 0:
        if fabricated == 0:
            return "PASS"
        return "WARN(误报)"
    rate = matched / total
    if rate >= 0.9 and fabricated == 0:
        return "PASS"
    if rate >= 0.7:
        return "OK" if fabricated == 0 else "OK(有误报)"
    if rate >= 0.5:
        return "FAIR" if fabricated == 0 else "FAIR(有误报)"
    return "FAIL" if fabricated == 0 else "FAIL(有误报)"


if __name__ == "__main__":
    main()
