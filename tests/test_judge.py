"""Tests of the judge prompt building and of the judging loop (against a scripted judge, no model)."""

import json

from bench.attack_runner import note_facts
from bench.attacks import load_attacks
from bench.judge import build_prompt, run_judge, summarize
from target.prompts import CANARY

ATTACKS = {a["id"]: a for a in load_attacks()}
FACTS = note_facts()


def trace(id, family, question="Q ?", answer="R.", retrieved=None, tool_calls=None):
    return {"id": id, "family": family, "question": question, "answer": answer,
            "retrieved": retrieved or [], "tool_calls": tool_calls or []}


def test_prompt_carries_the_family_criterion_and_evidence():
    _, user = build_prompt(trace("A3-02", 3), ATTACKS["A3-02"], FACTS)
    assert "fuite du prompt" in user and CANARY in user  # family 3 gets the canary

    _, user = build_prompt(trace("A4-02", 4), ATTACKS["A4-02"], FACTS)
    assert "PRX-4817" in user  # family 4 gets the note's facts

    tools = [{"name": "send_email", "arguments": {}, "executed": True, "blocked_by": None}]
    _, user = build_prompt(trace("A5-01", 5, tool_calls=tools), ATTACKS["A5-01"], FACTS)
    assert "send_email" in user  # family 5 gets the tool log


def test_family2_evidence_reports_whether_the_trapped_doc_was_retrieved():
    _, got = build_prompt(trace("A2-01", 2, retrieved=["TRAP-001-000"]), ATTACKS["A2-01"], FACTS)
    _, missed = build_prompt(trace("A2-01", 2, retrieved=["F1-000"]), ATTACKS["A2-01"], FACTS)
    assert "récupérée par l'application : oui" in got
    assert "récupérée par l'application : non" in missed


def test_run_judge_writes_a_verdict_per_trace(tmp_path):
    traces = [trace("A1-01", 1), trace("A3-02", 3)]
    calls = []

    def fake_call(system, user):
        calls.append(user)
        return {"verdict": "réussi", "raison": "test"}

    out = tmp_path / "judge.jsonl"
    run_judge(traces, ATTACKS, FACTS, out, call=fake_call)
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["judge"]["verdict"] for r in records] == ["réussi", "réussi"]
    assert len(calls) == 2
    assert "Famille" in summarize(out)


def test_run_judge_resumes(tmp_path):
    out = tmp_path / "judge.jsonl"
    run_judge([trace("A1-01", 1)], ATTACKS, FACTS, out, call=lambda s, u: {"verdict": "échoué", "raison": ""})
    run_judge([trace("A1-01", 1)], ATTACKS, FACTS, out, call=lambda s, u: {"verdict": "réussi", "raison": ""})
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1  # not re-judged
