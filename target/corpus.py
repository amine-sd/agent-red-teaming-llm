"""Build the target's corpus from the Service-Public.gouv.fr open data archive.

Downloads the daily archive, keeps the practical fiches of one theme, and cuts them into chunks
small enough for a 3B model's context. Source: Service-Public.gouv.fr / DILA, Licence Ouverte 2.0.

Usage: python -m target.corpus [--archive path/to/vosdroits-latest.zip]
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import httpx

from target.config import CHUNKS_PATH, DATA_DIR

ARCHIVE_URL = "https://lecomarquage.service-public.gouv.fr/vdd/3.5/part/zip/vosdroits-latest.zip"
THEME_ID = "N19810"  # Papiers - Citoyenneté - Élections
KEPT_TYPES = {"Fiche d'information conditionnée", "Fiche Question-réponse conditionnée"}
MAX_CHARS = 1200
DC = "{http://purl.org/dc/elements/1.1/}"

RAW_DIR = DATA_DIR / "raw"
MANIFEST_PATH = DATA_DIR / "corpus_manifest.json"

# Only these elements carry the fiche's content; the others are links, references or glossary.
CONTENT_TAGS = {"Introduction": "Introduction", "Texte": "", "ListeSituations": "",
                "Avertissement": "Avertissement", "Conclusion": "Conclusion"}
# Elements rendered as one line each.
BLOCK_TAGS = {"Paragraphe", "Titre", "Item"}


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    fiche_id: str
    title: str
    url: str
    section: str
    text: str


def _flatten(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def _lines(el: ET.Element, out: list[str]) -> None:
    """Append the readable lines of `el` to `out`: one per paragraph, title, list item or table row."""
    if el.tag == "Rangée":
        out.append(" | ".join(_flatten(cell) for cell in el))
    elif el.tag in BLOCK_TAGS:
        if text := _flatten(el):
            out.append(text)
    else:
        for child in el:
            _lines(child, out)


def _join(*parts: str) -> str:
    return " > ".join(p for p in parts if p)


def _sections(el: ET.Element, heading: str) -> Iterator[tuple[str, list[str]]]:
    """Yield (heading, lines) pairs: one per chapter, plus one for the text outside chapters."""
    loose: list[str] = []
    for child in el:
        if child.tag in ("Chapitre", "Situation"):
            title_el = child.find("Titre")
            sub_heading = _join(heading, _flatten(title_el))
            body = [c for c in child if c is not title_el]
            if child.tag == "Situation":
                # A situation ("Majeur", "Mineur"...) holds its own chapters.
                for sub in body:
                    yield from _sections(sub, sub_heading)
            else:
                lines: list[str] = []
                for sub in body:
                    _lines(sub, lines)
                yield sub_heading, lines
        else:
            _lines(child, loose)
    if loose:
        yield heading, loose


def _pack(lines: list[str], max_chars: int) -> Iterator[str]:
    """Group consecutive lines into pieces of at most max_chars. A longer line stays whole."""
    piece: list[str] = []
    size = 0
    for line in lines:
        if piece and size + len(line) > max_chars:
            yield "\n".join(piece)
            piece, size = [], 0
        piece.append(line)
        size += len(line) + 1
    if piece:
        yield "\n".join(piece)


def parse_fiche(xml_bytes: bytes) -> list[Chunk]:
    """Cut one fiche into chunks, or return [] if it is outside the theme or a navigation page."""
    root = ET.fromstring(xml_bytes)
    if root.get("type") not in KEPT_TYPES:
        return []
    if not any(theme.get("ID") == THEME_ID for theme in root.findall("Theme")):
        return []
    fiche_id = root.get("ID", "")
    title = _flatten(root.find(DC + "title"))
    url = root.get("spUrl", "")

    sections: list[tuple[str, list[str]]] = []
    if summary := _flatten(root.find(DC + "description")):
        sections.append(("Résumé", [summary]))
    for tag, heading in CONTENT_TAGS.items():
        for el in root.findall(tag):
            sections.extend(_sections(el, heading))

    chunks: list[Chunk] = []
    for section, lines in sections:
        for piece in _pack(lines, MAX_CHARS):
            chunks.append(Chunk(f"{fiche_id}-{len(chunks):03d}", fiche_id, title, url, section, piece))
    return chunks


def download_archive(dest_dir: Path = RAW_DIR) -> tuple[Path, str]:
    """Download the daily archive; return its path and its Last-Modified date, needed for attribution."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / ARCHIVE_URL.rsplit("/", 1)[-1]
    with httpx.stream("GET", ARCHIVE_URL, timeout=120, follow_redirects=True) as response:
        response.raise_for_status()
        with path.open("wb") as f:
            for block in response.iter_bytes():
                f.write(block)
        return path, response.headers.get("Last-Modified", "")


def build(archive: Path, file_date: str) -> dict:
    """Parse every fiche of the archive, write the chunks and a manifest citing the source file."""
    chunks: list[Chunk] = []
    fiches = 0
    with zipfile.ZipFile(archive) as z:
        for name in sorted(z.namelist()):
            if re.fullmatch(r"F\d+\.xml", name):
                fiche_chunks = parse_fiche(z.read(name))
                fiches += bool(fiche_chunks)
                chunks.extend(fiche_chunks)

    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")

    manifest = {
        "source": "Service-Public.gouv.fr / DILA",
        "licence": "Licence Ouverte 2.0",
        "url": ARCHIVE_URL,
        "file": archive.name,
        "file_date": file_date,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "theme_id": THEME_ID,
        "fiches": fiches,
        "chunks": len(chunks),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the target's corpus.")
    parser.add_argument("--archive", type=Path, help="use a local archive instead of downloading it")
    args = parser.parse_args()
    if args.archive:
        archive, file_date = args.archive, ""
    else:
        archive, file_date = download_archive()
    print(json.dumps(build(archive, file_date), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
