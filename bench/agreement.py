"""Day 12: agreement between the model judge and the human labels, published as it is.

Reads the 50 human verdicts (data/labels_humains.yaml), the judge verdicts (results/judge/base/)
and the mechanical verdicts (results/attacks/base-none/), aligns them by attack id, and reports:
- raw agreement and Cohen's kappa (judge vs human), overall and per family;
- the same for the mechanical verdict vs human, as an alternative reference;
- a 95 % bootstrap confidence interval on kappa, honest about the small sample.

A1-01 is excluded from the headline: it was the worked example, seen before it was labelled, so it
is not blind. The report shows the numbers with and without it to confirm it changes nothing.

Run: python -m bench.agreement
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import yaml

from bench.benign import _read
from target.config import ROOT

LABELS_PATH = ROOT / "data" / "labels_humains.yaml"
JUDGE_PATH = ROOT / "results" / "judge" / "base" / "judge.jsonl"
MECH_PATH = ROOT / "results" / "attacks" / "base-none" / "none.jsonl"
OUT_DIR = ROOT / "results" / "agreement"
NON_BLIND = {"A1-01"}  # worked example, verdict seen before labelling


def cohen_kappa(a: list[str], b: list[str]) -> float:
    labels = sorted(set(a) | set(b))
    index = {label: i for i, label in enumerate(labels)}
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    count_a, count_b = Counter(a), Counter(b)
    expected = sum((count_a[l] / n) * (count_b[l] / n) for l in labels)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def bootstrap_ci(a: list[str], b: list[str], rng: np.random.Generator, n: int = 5000) -> tuple[float, float]:
    a, b = np.array(a), np.array(b)
    kappas = []
    for _ in range(n):
        idx = rng.integers(0, len(a), len(a))
        ka, kb = list(a[idx]), list(b[idx])
        if len(set(ka)) > 1 or len(set(kb)) > 1:
            kappas.append(cohen_kappa(ka, kb))
    return (float(np.percentile(kappas, 2.5)), float(np.percentile(kappas, 97.5))) if kappas else (float("nan"),) * 2


def split_tune_holdout() -> tuple[list[str], list[str]]:
    """Deterministic stratified split of the blind cases: ~60 % tune, ~40 % holdout, per family.

    The grille correction is designed on the tune ids only; the corrected judge is measured on the
    holdout ids, which are never used to design the fix, so the final kappa is not overfit.
    """
    rows = [r for r in load() if r["id"] not in NON_BLIND]
    by_family: dict[int, list[str]] = defaultdict(list)
    for r in rows:
        by_family[r["family"]].append(r["id"])
    tune, holdout = [], []
    for family in sorted(by_family):
        ids = sorted(by_family[family])
        n_holdout = round(len(ids) * 0.4)
        holdout.extend(ids[len(ids) - n_holdout:])
        tune.extend(ids[: len(ids) - n_holdout])
    return sorted(tune), sorted(holdout)


def load() -> list[dict]:
    human = {c["id"]: c["verdict"] for c in yaml.safe_load(LABELS_PATH.read_text(encoding="utf-8")) if c["verdict"]}
    judge = {r["id"]: r["judge"]["verdict"] for r in _read(JUDGE_PATH)}
    mech = {r["id"]: r["verdict"]["verdict"] for r in _read(MECH_PATH)}
    rows = []
    for cid in sorted(human):
        rows.append({"id": cid, "family": int(cid[1]), "human": human[cid],
                     "judge": judge.get(cid), "mech": mech.get(cid)})
    return rows


def _rate(rows: list[dict], key: str) -> str:
    usable = [r for r in rows if r[key] is not None]
    if not usable:
        return "n/a"
    agree = sum(r[key] == r["human"] for r in usable)
    return f"{agree}/{len(usable)} ({100 * agree / len(usable):.0f} %)"


def report() -> str:
    rows = load()
    blind = [r for r in rows if r["id"] not in NON_BLIND]
    rng = np.random.default_rng(0)

    def kappa_line(rows_, key, mech_only=False):
        usable = [r for r in rows_ if r[key] is not None and (not mech_only or r["mech"] not in (None, "à_juger"))]
        # mechanical abstains on family 1 ("à juger"), so exclude those for a fair kappa.
        usable = [r for r in usable if r[key] not in (None, "à_juger")]
        if len({r[key] for r in usable}) < 2 and len({r["human"] for r in usable}) < 2:
            return "accord parfait (kappa non défini)"
        k = cohen_kappa([r[key] for r in usable], [r["human"] for r in usable])
        lo, hi = bootstrap_ci([r[key] for r in usable], [r["human"] for r in usable], rng)
        return f"kappa = {k:.2f} (IC 95 % [{lo:.2f}, {hi:.2f}], n = {len(usable)})"

    lines = [
        "# Accord juge / humain (jour 12)",
        "",
        f"Référence : {len(blind)} verdicts humains à l'aveugle (A1-01 exclu, non aveugle). "
        "L'accord est publié tel quel, quel qu'il soit.",
        "",
        "## Vue d'ensemble",
        "",
        f"- **Juge `gemma2:2b` contre humain** : accord brut {_rate(blind, 'judge')}, {kappa_line(blind, 'judge')}.",
        f"- **Verdict mécanique contre humain** (familles 2 à 6, le mécanique s'abstient sur la 1) : "
        f"accord brut {_rate([r for r in blind if r['mech'] not in (None, 'à_juger')], 'mech')}, "
        f"{kappa_line(blind, 'mech', mech_only=True)}.",
        "",
        "Avec A1-01 inclus, l'accord juge/humain passe à "
        f"{_rate(rows, 'judge')} (inchangé en substance).",
        "",
        "## Accord juge/humain par famille",
        "",
        "| Famille | Accord brut | Désaccords |",
        "|---|---|---|",
    ]
    by_family: dict[int, list[dict]] = defaultdict(list)
    for r in blind:
        by_family[r["family"]].append(r)
    for family in range(1, 7):
        fam = by_family[family]
        disagreements = ", ".join(r["id"] for r in fam if r["judge"] != r["human"]) or "aucun"
        lines.append(f"| {family} | {_rate(fam, 'judge')} | {disagreements} |")

    v2_path = ROOT / "results" / "judge" / "holdout_v2" / "judge.jsonl"
    if v2_path.exists():
        _, holdout = split_tune_holdout()
        human = {r["id"]: r["human"] for r in rows}
        v1 = {r["id"]: r["judge"] for r in rows}
        v2 = {r["id"]: r["judge"]["verdict"] for r in _read(v2_path)}
        H = [human[i] for i in holdout]

        def stat(pred: dict) -> str:
            J = [pred[i] for i in holdout]
            agree = sum(a == b for a, b in zip(J, H))
            k = cohen_kappa(J, H)
            lo, hi = bootstrap_ci(J, H, rng)
            return f"accord {agree}/{len(H)} ({100 * agree / len(H):.0f} %), kappa {k:.2f} (IC 95 % [{lo:.2f}, {hi:.2f}])"

        lines += [
            "", "## Correction de la grille, sur les 19 cas tenus à part", "",
            "Grille v2 : le juge décide « critère de succès rempli : oui/non/incertain », le verdict "
            "est mappé mécaniquement (au lieu de laisser le modèle choisir réussi/échoué, qu'il "
            "inversait). Réglée sur les 30 cas de réglage, mesurée sur 19 cas jamais touchés.",
            "",
            f"- Juge v1 (jour 10) : {stat(v1)}.",
            f"- Juge v2 (corrigé) : {stat(v2)}.",
            "",
            "La correction relève le kappa et sort l'intervalle de zéro, mais le juge reste modéré, "
            "loin du vérificateur déterministe (0,90). Un juge de 2 milliards de paramètres ne suffit "
            "pas à remplacer la vérification mécanique ni l'humain sur les familles à jugement.",
        ]

    lines += ["", "## Détail des désaccords juge/humain (49 cas)", "",
              "| Id | Humain | Juge | Mécanique |", "|---|---|---|---|"]
    for r in blind:
        if r["judge"] != r["human"]:
            lines.append(f"| {r['id']} | {r['human']} | {r['judge']} | {r['mech']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = report()
    (OUT_DIR / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
