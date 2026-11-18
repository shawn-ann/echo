"""纠错报告错误类型的字段归一化（跨新旧产物）。

新产物（V3）用中文 `category`；旧产物用 `error_type`，且部分更早产物还带
英文枚举 `category`（grammar/collocation/chinglish/style），不能直接采用。
"""

_LEGACY_ENUMS = {"grammar", "collocation", "chinglish", "style"}


def model_category(err: dict) -> str:
    """取错误的规范类型名，兼容新旧两种产物。"""
    cat = err.get("category")
    if isinstance(cat, str) and cat and cat not in _LEGACY_ENUMS:
        return cat
    return err.get("error_type") or cat or ""
