"""Run the base attacks against the target, log a full trace, and record a mechanical verdict.

Each attack goes through the same pipeline as a real request, in the chosen guardrail configuration.
Everything is captured to a JSONL trace, one line per attack: question, full answer, retrieved
chunks, tool calls, guardrail events, token counts, and the mechanical verdict (families 2 to 6;
family 1 is left "à juger" for the day 10 judge).

Family 2's poisoned fiches are added to the index only for family 2 attacks, so they do not affect
the other families or the benign reference.

Run: python -m bench.attack_runner --config none
Traces go to results/attacks/<date>/<config>.jsonl plus summary.md; a stopped run resumes.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

import httpx
import yaml

from bench.attacks import load_attacks
from bench.benign import _read
from bench.verdicts import compute_verdict
from target.config import ROOT, parse_guardrails, settings
from target.corpus import PLANTED_PATH, TRAPPED_PATH, Chunk, load_chunks, load_planted
from target.pipeline import run
from target.retrieval import Retriever

RESULTS_DIR = ROOT / "results" / "attacks"


def note_facts(path: Path = PLANTED_PATH) -> dict[str, list[str]]:
    return {doc["id"]: doc["facts"] for doc in yaml.safe_load(path.read_text(encoding="utf-8"))}


def build_retrievers() -> tuple[Retriever, Retriever]:
    """A public retriever, and one that also holds the trapped fiches for family 2."""
    public_chunks = load_chunks()
    return Retriever(public_chunks), Retriever(public_chunks + load_planted(TRAPPED_PATH))


def _context(question: str, result, by_id: dict[str, Chunk]) -> str:
    """Rebuild what the model read: the question plus the text of the retrieved chunks."""
    extracts = " ".join(by_id[c].text for c in result.retrieved if c in by_id)
    return f"{question}\n{extracts}"


def run_config(name: str, attacks: list[dict], retrievers, facts, by_id, out_path: Path) -> None:
    public, trapped = retrievers
    # An attack that errored (Ollama crashed under memory pressure) is retried on the next run.
    done = {r["id"] for r in _read(out_path) if "error" not in r}
    config = replace(settings, guardrails=parse_guardrails(name))
    with out_path.open("a", encoding="utf-8") as f:
        for attack in attacks:
            if attack["id"] in done:
                continue
            retriever = trapped if attack["family"] == 2 else public
            start = time.perf_counter()
            record = {k: attack.get(k) for k in ("id", "family", "target", "question")}
            record |= {"config": name, "model": config.model, "temperature": config.temperature}
            try:
                result = run(attack["question"], config, retriever)
                record.update(asdict(result))
                record["verdict"] = compute_verdict(
                    attack, result, _context(attack["question"], result, by_id), facts
                )
            except httpx.HTTPError as exc:  # not evaluable: a model error, retried on the next run
                record["error"] = str(exc)
                record["verdict"] = {"verdict": "non_evaluable", "reason": f"erreur modèle: {exc}", "proxy": False}
            record["wall_s"] = round(time.perf_counter() - start, 1)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            v = record["verdict"]["verdict"]
            print(f"[{name}] {attack['id']} (famille {attack['family']}) -> {v} ({record['wall_s']:.0f} s)", flush=True)


def summarize(run_dir: Path, attacks: list[dict], configs: list[str]) -> str:
    order = ["réussi", "à_juger", "échoué", "non_evaluable"]
    lines = [
        f"# Attaques de base : traces du {run_dir.name}",
        "",
        f"Modèle `{settings.model}`, température {settings.temperature}, top_k {settings.top_k}, "
        f"{len(attacks)} attaques de base. Verdict mécanique pour les familles 2 à 6 ; la famille 1 "
        "est laissée « à juger » pour le juge du jour 10.",
        "",
        "| Configuration | Famille | Réussi | À juger | Échoué | Non évaluable |",
        "|---|---|---|---|---|---|",
    ]
    for name in configs:
        records = _read(run_dir / f"{name}.jsonl")
        for family in range(1, 7):
            counts = Counter(r["verdict"]["verdict"] for r in records if r["family"] == family)
            if not counts:
                continue
            lines.append(f"| `{name}` | {family} | " + " | ".join(str(counts.get(v, 0)) for v in order) + " |")
    lines += ["", "## Détail par attaque", "",
              "| Id | Famille | Config | Verdict | Motif | Durée |", "|---|---|---|---|---|---|"]
    for name in configs:
        for r in _read(run_dir / f"{name}.jsonl"):
            v = r["verdict"]
            flag = " (proxy)" if v.get("proxy") else ""
            lines.append(f"| {r['id']} | {r['family']} | `{name}` | {v['verdict']}{flag} | {v['reason']} | {r['wall_s']:.0f} s |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run and score the base attacks.")
    parser.add_argument("--config", action="append", help='guardrails, e.g. "none", "all"')
    parser.add_argument("--run-dir", type=Path, default=RESULTS_DIR / date.today().isoformat())
    parser.add_argument("--ids", help="comma-separated attack ids to run instead of all 60")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    configs = args.config or ["none"]
    attacks = load_attacks()
    if args.ids:
        wanted = set(args.ids.split(","))
        attacks = [a for a in attacks if a["id"] in wanted]
    args.run_dir.mkdir(parents=True, exist_ok=True)
    if not args.summary_only:
        retrievers = build_retrievers()
        by_id = {c.chunk_id: c for c in retrievers[1].chunks}
        facts = note_facts()
        for name in configs:
            run_config(name, attacks, retrievers, facts, by_id, args.run_dir / f"{name}.jsonl")
    summary = summarize(args.run_dir, attacks, configs)
    (args.run_dir / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
