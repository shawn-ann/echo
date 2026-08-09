import json
from pathlib import Path

_GOLDEN_PATH = Path(__file__).parent / "golden_cases.json"


def load_golden_cases() -> list[dict]:
    """读取 golden_cases.json，返回用例列表。"""
    with _GOLDEN_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]
