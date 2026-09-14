"""Tests of the benign query set and of its scoring."""

import pytest

from bench.benign import contains, load_queries, score
from target.config import CHUNKS_PATH
from target.corpus import load_chunks

QUERIES = load_queries()


def test_contains_matches_whole_words_ignoring_case_and_accents():
    assert contains("Elle est valable 10 ans.", ["10 ans"])
    assert not contains("Elle est valable 110 ans.", ["10 ans"])
    assert contains("Saisissez le defenseur des droits.", ["Défenseur des droits"])
    assert contains("Le timbre coûte 86 €.", ["86 €"])


def test_score_requires_every_fact_and_no_refusal():
    query = {"expected_facts": [["municipales"], ["européennes"]], "fiches": ["F1937"]}
    both = {"answer": "Municipales et européennes [F1937].", "events": [], "cited": [{"fiche_id": "F1937"}]}
    assert score(query, both) == {"blocked": False, "success": True, "cited_expected": True}
    assert score(query, {**both, "answer": "Seulement les municipales."})["success"] is False
    refused = {**both, "events": [{"guardrail": "input", "action": "blocked_question"}]}
    assert score(query, refused)["success"] is False


def test_query_set_is_well_formed():
    ids = [q["id"] for q in QUERIES]
    assert len(ids) == 30 and len(set(ids)) == 30
    assert sum(q["kind"] == "ordinaire" for q in QUERIES) == 25
    assert sum(q["kind"] == "piege" for q in QUERIES) == 5


@pytest.mark.skipif(not CHUNKS_PATH.exists(), reason="corpus not built: python -m target.corpus")
def test_every_expected_fact_is_in_its_fiche():
    texts: dict[str, str] = {}
    for c in load_chunks():
        texts[c.fiche_id] = texts.get(c.fiche_id, "") + f" {c.title} {c.text}"
    for q in QUERIES:
        fiche_text = " ".join(texts[f] for f in q["fiches"])
        for group in q["expected_facts"]:
            assert contains(fiche_text, group), (q["id"], group)
