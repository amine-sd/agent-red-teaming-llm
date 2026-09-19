# Sous Windows sans make : remplacer `make <cible>` par la commande de la recette.
# En local, PYTHON pointe sur le venv ; en CI (Linux), sur python.
PYTHON ?= python

.PHONY: eval corpus test bench-none bench-all bench-stability

## eval : (re)génère rapport.md à partir des résultats existants
eval:
	$(PYTHON) -m bench.report

## corpus : télécharge et découpe le corpus Service-Public
corpus:
	$(PYTHON) -m target.corpus

## test : suite pytest
test:
	$(PYTHON) -m pytest -q

## bench-none : 60 attaques sans garde-fou (référence)
bench-none:
	$(PYTHON) -m bench.attack_runner --config none --run-dir results/attacks/base-none

## bench-all : 60 attaques avec les quatre garde-fous
bench-all:
	$(PYTHON) -m bench.attack_runner --config all --run-dir results/attacks/base-all
