"""Unit tests for `scripts/ingest_suggestions.py`."""

from __future__ import annotations

from pathlib import Path

from scripts.ingest_suggestions import _extract_docs, ingest


def _suggestion(topic: str, docs: list[str]) -> dict:
    return {"topic": topic, "suggested_documents": docs}


def test_extract_docs_dedup_preserves_order():
    suggestions = [
        _suggestion("a", ["x.pdf", "y.pdf"]),
        _suggestion("b", ["y.pdf", "z.pdf"]),
    ]
    assert _extract_docs(suggestions) == ["x.pdf", "y.pdf", "z.pdf"]


def test_extract_docs_skips_invalid_entries():
    suggestions = [
        "not_a_dict",
        {"topic": "a"},  # no suggested_documents
        _suggestion("b", ["", None, 42, "valid.pdf"]),  # type: ignore[list-item]
    ]
    assert _extract_docs(suggestions) == ["valid.pdf"]


def test_ingest_copies_inbox_into_corpus(tmp_path: Path):
    inbox = tmp_path / "inbox"
    corpus = tmp_path / "corpus"
    inbox.mkdir()
    (inbox / "a.pdf").write_bytes(b"A")
    (inbox / "b.pdf").write_bytes(b"B")

    suggestions = [_suggestion("permits", ["a.pdf", "b.pdf"])]
    report = ingest(suggestions, inbox=inbox, corpus=corpus)

    assert report["ingested"] == ["a.pdf", "b.pdf"]
    assert report["skipped_existing"] == []
    assert report["missing_in_inbox"] == []
    assert (corpus / "a.pdf").read_bytes() == b"A"
    assert (corpus / "b.pdf").read_bytes() == b"B"


def test_ingest_is_idempotent(tmp_path: Path):
    inbox = tmp_path / "inbox"
    corpus = tmp_path / "corpus"
    inbox.mkdir()
    (inbox / "a.pdf").write_bytes(b"A")

    suggestions = [_suggestion("permits", ["a.pdf"])]
    ingest(suggestions, inbox=inbox, corpus=corpus)
    report = ingest(suggestions, inbox=inbox, corpus=corpus)

    assert report["ingested"] == []
    assert report["skipped_existing"] == ["a.pdf"]
    assert report["missing_in_inbox"] == []


def test_ingest_reports_missing_inbox_files(tmp_path: Path):
    inbox = tmp_path / "inbox"
    corpus = tmp_path / "corpus"
    inbox.mkdir()

    suggestions = [_suggestion("permits", ["nowhere.pdf"])]
    report = ingest(suggestions, inbox=inbox, corpus=corpus)

    assert report["ingested"] == []
    assert report["missing_in_inbox"] == ["nowhere.pdf"]
    assert not (corpus / "nowhere.pdf").exists()


def test_ingest_creates_corpus_dir_if_absent(tmp_path: Path):
    inbox = tmp_path / "inbox"
    corpus = tmp_path / "new_corpus"
    inbox.mkdir()
    (inbox / "a.pdf").write_bytes(b"A")

    suggestions = [_suggestion("permits", ["a.pdf"])]
    report = ingest(suggestions, inbox=inbox, corpus=corpus)

    assert corpus.is_dir()
    assert report["ingested"] == ["a.pdf"]


def test_ingest_handles_mixed_statuses(tmp_path: Path):
    inbox = tmp_path / "inbox"
    corpus = tmp_path / "corpus"
    inbox.mkdir()
    corpus.mkdir()
    (inbox / "new.pdf").write_bytes(b"N")
    (corpus / "existing.pdf").write_bytes(b"E")

    suggestions = [_suggestion("permits", ["new.pdf", "existing.pdf", "missing.pdf"])]
    report = ingest(suggestions, inbox=inbox, corpus=corpus)

    assert report["ingested"] == ["new.pdf"]
    assert report["skipped_existing"] == ["existing.pdf"]
    assert report["missing_in_inbox"] == ["missing.pdf"]
