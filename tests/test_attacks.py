"""Tests of the base attack catalogue and of the trapped fiches it relies on."""

import yaml

from bench.attacks import load_attacks
from target.corpus import TRAPPED_PATH, load_planted

ATTACKS = load_attacks()
TRAPPED = {doc["id"]: doc for doc in yaml.safe_load(TRAPPED_PATH.read_text(encoding="utf-8"))}


def test_sixty_attacks_ten_per_family():
    assert len(ATTACKS) == 60
    for family in range(1, 7):
        assert sum(a["family"] == family for a in ATTACKS) == 10, family


def test_family2_attacks_point_at_a_trapped_doc_carrying_their_resource():
    for attack in ATTACKS:
        if attack["family"] != 2:
            continue
        doc = TRAPPED[attack["trapped_doc"]]
        text = " ".join(s["text"] for s in doc["sections"])
        assert attack["resource"] in text, attack["id"]
        assert attack["resource"].endswith(".invalid") or ".invalid/" in attack["resource"]


def test_family6_attacks_use_fictional_domains_only():
    for attack in ATTACKS:
        if attack["family"] == 6 and "http" in attack["question"]:
            assert ".invalid" in attack["question"], attack["id"]


def test_trapped_fiches_are_public_fictional_and_loadable():
    for doc in TRAPPED.values():
        assert doc["scope"] == "public" and doc["fictional"] is True
    chunks = load_planted(TRAPPED_PATH)
    assert chunks and all(c.scope == "public" for c in chunks)
