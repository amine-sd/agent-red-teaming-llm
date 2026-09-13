"""Tests of the target that run without a model: parsing, retrieval, prompt, citations."""

from fastapi.testclient import TestClient

import target.app as app_module
import target.pipeline as pipeline
from target.corpus import Chunk, parse_fiche
from target.llm import Reply
from target.prompts import build_user_message
from target.retrieval import Retriever, tokenize

FICHE = """<?xml version="1.0" encoding="UTF-8"?>
<Publication xmlns:dc="http://purl.org/dc/elements/1.1/" ID="F1" type="Fiche d'information conditionnée"
  spUrl="https://www.service-public.gouv.fr/particuliers/vosdroits/F1">
<dc:title>Passeport d'un majeur</dc:title>
<dc:description>Comment obtenir un passeport.</dc:description>
<Theme ID="THEME"><Titre>Papiers - Citoyenneté - Élections</Titre></Theme>
<Introduction><Texte><Paragraphe>Le passeport est un titre de voyage.</Paragraphe></Texte></Introduction>
<Texte>
  <Chapitre>
    <Titre><Paragraphe>Où faire la demande ?</Paragraphe></Titre>
    <Paragraphe>En <MiseEnEvidence>mairie</MiseEnEvidence>, sur rendez-vous.</Paragraphe>
    <Liste><Item><Paragraphe>Photo d'identité</Paragraphe></Item></Liste>
  </Chapitre>
</Texte>
</Publication>"""


def fiche(theme: str = "N19810") -> bytes:
    return FICHE.replace("THEME", theme).encode("utf-8")


def chunk(fiche_id: str, text: str) -> Chunk:
    return Chunk(f"{fiche_id}-000", fiche_id, f"Fiche {fiche_id}", f"https://x/{fiche_id}", "", text)


def test_parse_fiche_cuts_summary_introduction_and_chapters():
    chunks = parse_fiche(fiche())
    assert [c.section for c in chunks] == ["Résumé", "Introduction", "Où faire la demande ?"]
    assert chunks[2].text == "En mairie, sur rendez-vous.\nPhoto d'identité"
    assert chunks[0].chunk_id == "F1-000"
    assert chunks[0].url.endswith("/vosdroits/F1")


def test_parse_fiche_skips_other_themes():
    assert parse_fiche(fiche(theme="N19806")) == []


def test_tokenize_drops_accents_stopwords_and_plurals():
    assert tokenize("Où renouveler le passeport d'un mineur ?") == ["renouveler", "passeport", "mineur"]
    assert tokenize("listes électorales") == tokenize("liste électorale")


def test_search_ranks_the_matching_chunk_first():
    retriever = Retriever([
        chunk("F1", "Renouvellement du passeport en mairie."),
        chunk("F2", "Inscription sur les listes électorales."),
        chunk("F3", "Carte nationale d'identité perdue ou volée."),
    ])
    assert retriever.search("inscription liste électorale", k=3)[0].fiche_id == "F2"


def test_search_returns_nothing_without_a_common_word():
    retriever = Retriever([chunk("F1", "Passeport."), chunk("F2", "Carte d'identité.")])
    assert retriever.search("recette de cuisine", k=3) == []


def test_user_message_tags_each_excerpt_with_its_fiche_id():
    message = build_user_message("Question ?", [chunk("F7", "Texte.")])
    assert "[F7] Fiche F7\nTexte." in message
    assert message.endswith("Question : Question ?")


def test_ask_keeps_only_citations_given_to_the_model(monkeypatch):
    monkeypatch.setattr(app_module, "_retriever", Retriever([chunk("F1", "Passeport en mairie.")]))
    monkeypatch.setattr(pipeline, "chat", lambda *args, **kwargs: Reply("Allez en mairie [F1] ou [F9].", 10, 5, 0.1))
    response = TestClient(app_module.app).post("/ask", json={"question": "Où demander un passeport ?"})
    assert response.status_code == 200
    body = response.json()
    assert [s["fiche_id"] for s in body["cited"]] == ["F1"]
    assert body["retrieved"] == ["F1-000"]
