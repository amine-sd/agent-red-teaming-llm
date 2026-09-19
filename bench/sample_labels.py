"""Prepare the human labelling sheet for day 11: 50 base attacks, stratified by family and verdict.

The sheet shows the labeller exactly what the judge saw (the family criterion, the evidence, the
question, the answer), so that day 12 compares like with like. It never shows the judge's verdict
nor the mechanical one: the labelling is blind, or the agreement measurement would be circular.

The stratification uses the mechanical verdict only to pick a mix of successes and failures in each
family (a family labelled all one way makes the agreement statistic meaningless). That verdict is
never written to the sheet.

Run: python -m bench.sample_labels   (refuses to overwrite an existing, filled-in sheet)
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml

from bench.attack_runner import note_facts
from bench.attacks import load_attacks
from bench.benign import _read
from bench.judge import BASE_DIR, FAMILY_NAMES, RUBRIC, _evidence
from target.config import ROOT

LABELS_PATH = ROOT / "data" / "labels_humains.yaml"
QUOTAS = {1: 9, 2: 9, 3: 8, 4: 8, 5: 8, 6: 8}  # sums to 50


def _literal_str(dumper, data):
    """Render multi-line strings as readable block scalars (|), not escaped one-liners."""
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


def select(traces: list[dict]) -> list[dict]:
    """Pick QUOTAS[family] cases per family, round-robin across mechanical verdicts for diversity."""
    by_family: dict[int, list[dict]] = defaultdict(list)
    for t in traces:
        by_family[t["family"]].append(t)

    chosen: list[dict] = []
    for family, quota in QUOTAS.items():
        by_verdict: dict[str, list[dict]] = defaultdict(list)
        for case in by_family[family]:
            by_verdict[case["verdict"]["verdict"]].append(case)
        groups = [sorted(by_verdict[v], key=lambda c: c["id"]) for v in sorted(by_verdict)]
        ordered: list[dict] = []
        i = 0
        while len(ordered) < len(by_family[family]):
            for group in groups:
                if i < len(group):
                    ordered.append(group[i])
            i += 1
        chosen.extend(ordered[:quota])
    return sorted(chosen, key=lambda c: c["id"])


def build_sheet(traces, attacks, facts) -> list[dict]:
    sheet = []
    for trace in select(traces):
        attack = attacks[trace["id"]]
        sheet.append({
            "id": trace["id"],
            "famille": f"{trace['family']} ({FAMILY_NAMES[trace['family']]})",
            "critere": RUBRIC[trace["family"]],
            "preuve": _evidence(trace, attack, facts),
            "question": trace["question"],
            "reponse": trace["answer"],
            "verdict": "",   # à remplir : réussi | échoué | incertain
            "note": "",
        })
    return sheet


HEADER = (
    "# Étiquetage humain des 50 cas (jour 11). À REMPLIR À LA MAIN, à l'aveugle.\n"
    "#\n"
    "# Pour chaque cas, lis le critère, la preuve, la question et la réponse, puis écris dans\n"
    "# verdict l'une des trois valeurs EXACTES : réussi | échoué | incertain.\n"
    "# 'note' est facultatif (une raison courte, utile au jour 12 pour comprendre les désaccords).\n"
    "#\n"
    "# Ne modifie que les champs verdict et note. Ne regarde pas l'avis du juge avant d'avoir fini :\n"
    "# c'est ce qui rend la mesure d'accord crédible.\n"
)


def main() -> None:
    if LABELS_PATH.exists():
        print(f"{LABELS_PATH} existe déjà : je ne l'écrase pas (tes verdicts seraient perdus).")
        return
    traces = _read(BASE_DIR / "none.jsonl")
    attacks = {a["id"]: a for a in load_attacks()}
    sheet = build_sheet(traces, attacks, note_facts())

    dumper = yaml.SafeDumper
    dumper.add_representer(str, _literal_str)
    body = yaml.dump(sheet, Dumper=dumper, allow_unicode=True, sort_keys=False, width=100)
    LABELS_PATH.write_text(HEADER + "\n" + body, encoding="utf-8")
    print(f"{LABELS_PATH} écrit : {len(sheet)} cas à étiqueter.")


if __name__ == "__main__":
    main()
