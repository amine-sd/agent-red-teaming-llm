"""Load the base attack catalogue: attacks/*.yaml, one file per family, ten attacks each.

Each attack is a dict with at least id, family, target, question, success_hint. Family 2 also
carries trapped_doc and resource. The loader validates the shape so that a malformed catalogue
fails loudly here rather than halfway through a bench run.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from target.config import ROOT

ATTACKS_DIR = ROOT / "attacks"
REQUIRED = ("id", "family", "target", "question", "success_hint")


def load_attacks(directory: Path = ATTACKS_DIR) -> list[dict]:
    attacks: list[dict] = []
    for path in sorted(directory.glob("famille*.yaml")):
        attacks.extend(yaml.safe_load(path.read_text(encoding="utf-8")) or [])

    seen: set[str] = set()
    for attack in attacks:
        missing = [field for field in REQUIRED if field not in attack]
        if missing:
            raise ValueError(f"attack {attack.get('id', '?')} misses {missing}")
        if attack["id"] in seen:
            raise ValueError(f"duplicate attack id {attack['id']}")
        seen.add(attack["id"])
        if attack["family"] == 2 and not {"trapped_doc", "resource"} <= attack.keys():
            raise ValueError(f"family 2 attack {attack['id']} needs trapped_doc and resource")
    return attacks
