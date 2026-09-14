"""The variant-generating attacker agent (day 8).

For each base attack that failed against the target, the agent generates variants with the
transformation operators, sends each one, reads the mechanical verdict, and stops at the first
variant that succeeds. It is an agent in that it acts on the verdict it reads: it keeps trying
until it breaks through or exhausts its budget, and logs every attempt.

It targets families with a mechanical verdict (here 3 and 6): family 1 needs the day 10 judge
before it can be looped on.

Run: python -m bench.agent --families 3 6
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

import httpx

from bench.attack_runner import build_retrievers, note_facts
from bench.attacks import load_attacks
from bench.benign import _read
from bench.variants import generate_variants
from target.config import ROOT, parse_guardrails, settings
from target.corpus import Chunk
from target.pipeline import run

RESULTS_DIR = ROOT / "results" / "attacks"
BASE_DIR = RESULTS_DIR / "base-none"


def _context(question: str, result, by_id: dict[str, Chunk]) -> str:
    extracts = " ".join(by_id[c].text for c in result.retrieved if c in by_id)
    return f"{question}\n{extracts}"


def failing_targets(families: list[int], base_dir: Path) -> list[dict]:
    """Base attacks of the given families that were marked échoué in the base run."""
    verdict_by_id = {r["id"]: r["verdict"]["verdict"] for r in _read(base_dir / "none.jsonl")}
    return [a for a in load_attacks()
            if a["family"] in families and verdict_by_id.get(a["id"]) == "échoué"]


def run_agent(targets, config_name, retrievers, facts, by_id, out_path, max_variants):
    from bench.verdicts import compute_verdict

    records = _read(out_path)
    solved = {r["parent"] for r in records if r.get("verdict", {}).get("verdict") == "réussi"}
    attempted = {r["id"] for r in records if "error" not in r}
    config = replace(settings, guardrails=parse_guardrails(config_name))
    public, trapped = retrievers

    with out_path.open("a", encoding="utf-8") as f:
        for base in targets:
            if base["id"] in solved:
                continue
            for variant in generate_variants(base, max_variants):
                if variant["id"] in attempted or base["id"] in solved:
                    continue
                retriever = trapped if variant["family"] == 2 else public
                start = time.perf_counter()
                record = {k: variant[k] for k in ("id", "parent", "family", "target", "operators",
                                                  "base_question", "question")}
                record |= {"config": config_name, "temperature": config.temperature}
                try:
                    result = run(variant["question"], config, retriever)
                    record.update(asdict(result))
                    record["verdict"] = compute_verdict(
                        variant, result, _context(variant["question"], result, by_id), facts
                    )
                except httpx.HTTPError as exc:
                    record["error"] = str(exc)
                    record["verdict"] = {"verdict": "non_evaluable", "reason": f"erreur modèle: {exc}", "proxy": False}
                record["wall_s"] = round(time.perf_counter() - start, 1)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                v = record["verdict"]["verdict"]
                print(f"[{config_name}] {variant['id']} {'+'.join(variant['operators'])} -> {v} "
                      f"({record['wall_s']:.0f} s)", flush=True)
                if v == "réussi":
                    solved.add(base["id"])
                    break


def summarize(run_dir: Path, targets: list[dict]) -> str:
    records = _read(run_dir / "variants.jsonl")
    by_parent: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_parent[r["parent"]].append(r)

    solved = [t for t in targets if any(r["verdict"]["verdict"] == "réussi" for r in by_parent.get(t["id"], []))]
    lines = [
        f"# Variantes : résultats du {run_dir.name}",
        "",
        f"Agent à opérateurs sur {len(targets)} attaques de base échouées. "
        f"**{len(solved)}/{len(targets)} ont désormais une variante qui réussit** là où la base "
        "échouait.",
        "",
        "| Attaque de base | Variantes essayées | Variante gagnante | Opérateurs |",
        "|---|---|---|---|",
    ]
    for t in targets:
        attempts = by_parent.get(t["id"], [])
        win = next((r for r in attempts if r["verdict"]["verdict"] == "réussi"), None)
        winner = win["id"] if win else "aucune"
        ops = "+".join(win["operators"]) if win else ""
        lines.append(f"| {t['id']} (famille {t['family']}) | {len(attempts)} | {winner} | {ops} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the variant-generating agent.")
    parser.add_argument("--families", type=int, nargs="+", default=[3, 6])
    parser.add_argument("--config", default="none")
    parser.add_argument("--base-dir", type=Path, default=BASE_DIR)
    parser.add_argument("--run-dir", type=Path, default=RESULTS_DIR / f"variants-{date.today().isoformat()}")
    parser.add_argument("--max-variants", type=int, default=5)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    targets = failing_targets(args.families, args.base_dir)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    if not args.summary_only:
        retrievers = build_retrievers()
        by_id = {c.chunk_id: c for c in retrievers[1].chunks}
        run_agent(targets, args.config, retrievers, note_facts(), by_id,
                  args.run_dir / "variants.jsonl", args.max_variants)
    summary = summarize(args.run_dir, targets)
    (args.run_dir / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
