"""Load the base policy and versioned reinforcement rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_policy(use_reinforcements: bool = True) -> dict[str, Any]:
    base = load_json(DATA / "policy.json")
    if use_reinforcements:
        learned = load_json(DATA / "reinforcements.json")
        base["reinforcement_version"] = learned.get("version", 0)
        base["safety_rules"] = learned.get("rules", [])
    else:
        base["reinforcement_version"] = 0
        base["safety_rules"] = []
    return base

