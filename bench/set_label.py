"""Transcribe one human verdict into data/labels_humains.yaml, by case id, keeping the file's layout.

This only writes down a verdict Amine has decided (a keyboard help): it never chooses a verdict
itself. The judgment is his; this is the scribe.

Usage: python -m bench.set_label A1-02 échoué ["note facultative"]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from target.config import ROOT

LABELS_PATH = ROOT / "data" / "labels_humains.yaml"
VALID = {"réussi", "échoué", "incertain"}


def set_label(case_id: str, verdict: str, note: str | None = None) -> None:
    if verdict not in VALID:
        sys.exit(f"verdict invalide : {verdict!r} (attendu : réussi | échoué | incertain)")
    lines = LABELS_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    current = None
    set_verdict = False
    set_note = note is None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- id:"):
            current = stripped.split(":", 1)[1].strip()
        elif current == case_id and line.startswith("  verdict:") and not set_verdict:
            lines[i] = f"  verdict: {json.dumps(verdict, ensure_ascii=False)}\n"
            set_verdict = True
        elif current == case_id and not set_note and line.startswith("  note:"):
            lines[i] = f"  note: {json.dumps(note, ensure_ascii=False)}\n"
            set_note = True
    if not set_verdict:
        sys.exit(f"id introuvable : {case_id}")
    LABELS_PATH.write_text("".join(lines), encoding="utf-8")
    print(f"{case_id} -> {verdict}" + (f"  (note: {note})" if note else ""))


if __name__ == "__main__":
    set_label(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
