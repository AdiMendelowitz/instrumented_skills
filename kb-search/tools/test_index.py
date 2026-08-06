"""Tests for index.py.

Covers the required cases: empty domain, single-document domain, never-indexed
domain, stale index needing rebuild, JSONL chunking, and unicode. Plus one CRLF
case, because a Windows line-ending bug is a defect class that bites this kind of
tooling easily.
"""

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import index as I  # noqa: E402


def write(path: Path, text: str, *, newline: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline=newline) as f:
        f.write(text)
    return path


# --- tokenize ---------------------------------------------------------------


def test_tokenize_lowercases_and_splits():
    assert I.tokenize("Hello, World! foo_bar") == ["hello", "world", "foo", "bar"]


def test_tokenize_drops_empties():
    assert I.tokenize("   ...   ") == []


def test_tokenize_handles_unicode():
    # Non-ASCII must produce tokens, not collapse to empty: retro journals and
    # handoff snapshots can contain non-ASCII text.
    tokens = I.tokenize("naïve café Ünicode")
    assert "naïve" in tokens
    assert "café" in tokens
    assert "ünicode" in tokens


def test_tokenize_empty_string():
    assert I.tokenize("") == []


# --- markdown chunking ------------------------------------------------------


def test_chunk_markdown_splits_on_headings(tmp_path):
    p = write(tmp_path / "doc.md", "# One\nalpha\n\n## Two\nbeta\n")
    chunks = I.chunk_markdown(p, "doc.md")
    assert [c.heading for c in chunks] == ["One", "Two"]
    assert "alpha" in chunks[0].text


def test_chunk_markdown_captures_preamble(tmp_path):
    p = write(tmp_path / "doc.md", "intro text\n\n# One\nalpha\n")
    chunks = I.chunk_markdown(p, "doc.md")
    assert chunks[0].heading == "(preamble)"
    assert "intro text" in chunks[0].text


def test_chunk_markdown_no_headings_still_yields_one_chunk(tmp_path):
    p = write(tmp_path / "flat.md", "just some prose with no heading at all\n")
    chunks = I.chunk_markdown(p, "flat.md")
    assert len(chunks) == 1
    assert chunks[0].heading == "(preamble)"


def test_chunk_markdown_skips_empty_sections(tmp_path):
    p = write(tmp_path / "doc.md", "# Empty\n\n# Full\ncontent\n")
    chunks = I.chunk_markdown(p, "doc.md")
    assert [c.heading for c in chunks] == ["Full"]


def test_chunk_markdown_handles_crlf(tmp_path):
    """CRLF must chunk identically to LF.

    A Windows line-ending assumption is an easy defect to introduce; this asserts
    that class of bug cannot land here.
    """
    lf = write(tmp_path / "lf.md", "# One\nalpha\n\n## Two\nbeta\n", newline="\n")
    crlf = write(tmp_path / "crlf.md", "# One\nalpha\n\n## Two\nbeta\n", newline="\r\n")
    a = I.chunk_markdown(lf, "lf.md")
    b = I.chunk_markdown(crlf, "crlf.md")
    assert [c.heading for c in a] == [c.heading for c in b]
    assert [c.text for c in a] == [c.text for c in b]


def test_chunk_markdown_unicode_content(tmp_path):
    p = write(tmp_path / "u.md", "# Café\nnaïve findings über alles\n")
    chunks = I.chunk_markdown(p, "u.md")
    assert chunks[0].heading == "Café"
    assert "über" in chunks[0].text


# --- jsonl chunking ---------------------------------------------------------


def test_chunk_jsonl_one_chunk_per_line(tmp_path):
    p = write(
        tmp_path / "log.jsonl",
        '{"a": 1}\n{"b": 2}\n',
    )
    chunks = I.chunk_jsonl(p, "log.jsonl")
    assert len(chunks) == 2
    assert chunks[0].heading == "line 1"
    assert chunks[1].heading == "line 2"


def test_chunk_jsonl_skips_blank_lines(tmp_path):
    p = write(tmp_path / "log.jsonl", '{"a": 1}\n\n\n{"b": 2}\n')
    assert len(I.chunk_jsonl(p, "log.jsonl")) == 2


def test_chunk_jsonl_keeps_malformed_line_as_text(tmp_path):
    """A malformed record is indexed raw rather than dropped.

    Losing a record silently is worse than ranking it imperfectly.
    """
    p = write(tmp_path / "log.jsonl", 'not json at all\n{"a": 1}\n')
    chunks = I.chunk_jsonl(p, "log.jsonl")
    assert len(chunks) == 2
    assert "not json at all" in chunks[0].text


def test_chunk_jsonl_preserves_unicode(tmp_path):
    p = write(tmp_path / "log.jsonl", '{"note": "café"}\n')
    chunks = I.chunk_jsonl(p, "log.jsonl")
    assert "café" in chunks[0].text


# --- collect / build --------------------------------------------------------


def test_collect_chunks_walks_recursively(tmp_path):
    d = tmp_path / "domain"
    write(d / "a.md", "# A\nalpha\n")
    write(d / "sub" / "b.md", "# B\nbeta\n")
    chunks = I.collect_chunks(d)
    assert {c.source_file for c in chunks} == {"a.md", "sub/b.md"}


def test_collect_chunks_ignores_unknown_suffixes(tmp_path):
    d = tmp_path / "domain"
    write(d / "a.md", "# A\nalpha\n")
    write(d / "binary.bin", "\x00\x01\x02")
    chunks = I.collect_chunks(d)
    assert {c.source_file for c in chunks} == {"a.md"}


def test_build_index_on_single_document(tmp_path):
    d = tmp_path / "domain"
    write(d / "only.md", "# Only\nsole document\n")
    idx = I.build_index(d)
    assert len(idx.chunks) == 1


def test_build_index_raises_on_missing_directory(tmp_path):
    with pytest.raises(I.CorpusNotFound):
        I.build_index(tmp_path / "nope")


def test_build_index_raises_on_empty_domain(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    with pytest.raises(I.EmptyCorpus):
        I.build_index(d)


def test_build_index_raises_when_only_unindexable_files(tmp_path):
    d = tmp_path / "domain"
    write(d / "thing.bin", "\x00\x01")
    with pytest.raises(I.EmptyCorpus):
        I.build_index(d)


# --- persistence ------------------------------------------------------------


def test_save_and_load_roundtrip(tmp_path):
    d = tmp_path / "domain"
    write(d / "a.md", "# A\nalpha beta\n")
    idx = I.build_index(d)
    cache = tmp_path / "cache.json"
    I.save_index(idx, cache)
    loaded = I.load_index(cache)
    assert [c.text for c in loaded.chunks] == [c.text for c in idx.chunks]
    assert loaded.corpus_hash == idx.corpus_hash


def test_cache_is_plain_json_not_pickle(tmp_path):
    """The cache must be inspectable text.

    Unpickling executes arbitrary code and these caches sit in directories that
    get synced and committed; this asserts the format never regresses.
    """
    d = tmp_path / "domain"
    write(d / "a.md", "# A\nalpha\n")
    idx = I.build_index(d)
    cache = tmp_path / "cache.json"
    I.save_index(idx, cache)
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert data["index_version"] == I.INDEX_VERSION
    assert isinstance(data["chunks"], list)


def test_load_index_rejects_version_mismatch(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps({"index_version": 999, "corpus_hash": "x", "chunks": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        I.load_index(cache)


def test_index_file_lands_outside_the_corpus(tmp_path):
    """An index inside the corpus would change the hash and force a rebuild every run."""
    d = tmp_path / "domain"
    d.mkdir()
    p = I.index_path_for(d)
    assert d not in p.parents
    assert p.parent == d.parent


# --- get_or_build state machine ---------------------------------------------


def test_get_or_build_reports_built_then_cached(tmp_path):
    d = tmp_path / "domain"
    write(d / "a.md", "# A\nalpha\n")
    _, state1 = I.get_or_build_index(d)
    _, state2 = I.get_or_build_index(d)
    assert state1 == "built"
    assert state2 == "cached"


def test_get_or_build_rebuilds_when_source_changes(tmp_path):
    d = tmp_path / "domain"
    write(d / "a.md", "# A\nalpha\n")
    I.get_or_build_index(d)
    time.sleep(1.1)  # mtime resolution is one second in the hash
    write(d / "b.md", "# B\nbeta\n")
    idx, state = I.get_or_build_index(d)
    assert state == "rebuilt-stale"
    assert len(idx.chunks) == 2


def test_get_or_build_recovers_from_corrupt_cache(tmp_path):
    d = tmp_path / "domain"
    write(d / "a.md", "# A\nalpha\n")
    I.get_or_build_index(d)
    I.index_path_for(d).write_text("{ this is not json", encoding="utf-8")
    idx, state = I.get_or_build_index(d)
    assert state == "rebuilt-corrupt"
    assert len(idx.chunks) == 1


def test_get_or_build_force_rebuilds(tmp_path):
    d = tmp_path / "domain"
    write(d / "a.md", "# A\nalpha\n")
    I.get_or_build_index(d)
    _, state = I.get_or_build_index(d, force=True)
    assert state == "built"


def test_get_or_build_raises_on_never_indexed_domain(tmp_path):
    with pytest.raises(I.CorpusNotFound):
        I.get_or_build_index(tmp_path / "absent")


# --- source hash ------------------------------------------------------------


def test_source_hash_stable_across_calls(tmp_path):
    d = tmp_path / "domain"
    write(d / "a.md", "# A\nalpha\n")
    assert I.source_hash(d) == I.source_hash(d)


def test_source_hash_ignores_unindexable_files(tmp_path):
    d = tmp_path / "domain"
    write(d / "a.md", "# A\nalpha\n")
    before = I.source_hash(d)
    write(d / "junk.bin", "\x00")
    assert I.source_hash(d) == before


# --- CLI --------------------------------------------------------------------


def test_cli_returns_2_on_missing_corpus(tmp_path, capsys):
    rc = I.main(["--root", str(tmp_path), "--domain", "nope"])
    assert rc == 2


def test_cli_returns_3_on_empty_corpus(tmp_path, capsys):
    (tmp_path / "empty").mkdir()
    rc = I.main(["--root", str(tmp_path), "--domain", "empty"])
    assert rc == 3


def test_cli_emits_json_on_success(tmp_path, capsys):
    write(tmp_path / "domain" / "a.md", "# A\nalpha\n")
    rc = I.main(["--root", str(tmp_path), "--domain", "domain"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["chunks"] == 1
    assert payload["state"] == "built"


# --- BM25 small-corpus behavior ---------------------------------------------
# These guard the defect that forced the stdlib rewrite: rank_bm25's BM25Okapi
# scored a matching term at exactly 0.0 on a two-document corpus and negative on
# a one-document corpus, which is the size every consuming skill starts at.


def test_bm25_positive_score_on_single_document_corpus():
    bm = I.BM25([I.tokenize("alpha beta gamma")])
    assert bm.get_scores(I.tokenize("alpha"))[0] > 0


def test_bm25_positive_score_on_two_document_corpus():
    bm = I.BM25([I.tokenize("alpha beta"), I.tokenize("gamma delta")])
    scores = bm.get_scores(I.tokenize("alpha"))
    assert scores[0] > 0


def test_bm25_non_matching_document_scores_exactly_zero():
    """The delta floor in BM25Plus broke this; "no results" must stay truthful."""
    bm = I.BM25([I.tokenize("alpha beta"), I.tokenize("gamma delta")])
    assert bm.get_scores(I.tokenize("alpha"))[1] == 0.0


def test_bm25_unknown_term_scores_zero_everywhere():
    bm = I.BM25([I.tokenize("alpha beta"), I.tokenize("gamma delta")])
    assert bm.get_scores(I.tokenize("epsilon")) == [0.0, 0.0]


def test_bm25_idf_never_negative():
    """A term in every document must still score above zero, not below it."""
    bm = I.BM25([I.tokenize("shared term"), I.tokenize("shared other")])
    assert all(v > 0 for v in bm.idf.values())


def test_bm25_ranks_denser_match_higher():
    bm = I.BM25([I.tokenize("alpha alpha alpha filler"), I.tokenize("alpha filler filler filler")])
    scores = bm.get_scores(I.tokenize("alpha"))
    assert scores[0] > scores[1]


def test_bm25_empty_corpus_returns_no_scores():
    assert I.BM25([]).get_scores(["alpha"]) == []


def test_tokenize_splits_snake_case():
    assert I.tokenize("retro_capture") == ["retro", "capture"]


# --- noise exclusion --------------------------------------------------------
# A first real run indexed tools/.pytest_cache/README.md and ranked it second,
# above two genuine hits. Build artifacts and VCS internals are short and
# keyword-dense, so they outrank real content easily.


def test_pytest_cache_is_not_indexed(tmp_path):
    d = tmp_path / "domain"
    write(d / "real.md", "# Real\ncaching mechanics content\n")
    write(d / ".pytest_cache" / "README.md", "# pytest cache directory\ncache plugin data\n")
    chunks = I.collect_chunks(d)
    assert {c.source_file for c in chunks} == {"real.md"}


def test_git_directory_is_not_indexed(tmp_path):
    d = tmp_path / "domain"
    write(d / "real.md", "# Real\ncontent\n")
    write(d / ".git" / "COMMIT_EDITMSG", "some commit message\n")
    assert {c.source_file for c in I.collect_chunks(d)} == {"real.md"}


def test_nested_dot_directory_is_not_indexed(tmp_path):
    """Component-wise checking, so a dot-dir below the root is caught too."""
    d = tmp_path / "domain"
    write(d / "real.md", "# Real\ncontent\n")
    write(d / "sub" / ".venv" / "notes.md", "# Venv\nnoise\n")
    assert {c.source_file for c in I.collect_chunks(d)} == {"real.md"}


def test_node_modules_is_not_indexed(tmp_path):
    d = tmp_path / "domain"
    write(d / "real.md", "# Real\ncontent\n")
    write(d / "node_modules" / "pkg" / "README.md", "# Pkg\nnoise\n")
    assert {c.source_file for c in I.collect_chunks(d)} == {"real.md"}


def test_pycache_is_not_indexed(tmp_path):
    d = tmp_path / "domain"
    write(d / "real.md", "# Real\ncontent\n")
    write(d / "__pycache__" / "stale.txt", "cached bytecode notes\n")
    assert {c.source_file for c in I.collect_chunks(d)} == {"real.md"}


def test_dotfile_at_top_level_is_still_indexed(tmp_path):
    """Only dot-DIRECTORIES are excluded; a dotfile is content the user chose."""
    d = tmp_path / "domain"
    write(d / ".hidden-notes.md", "# Hidden\nreal content the user wrote\n")
    assert {c.source_file for c in I.collect_chunks(d)} == {".hidden-notes.md"}


def test_source_hash_ignores_noise_directories(tmp_path):
    """Both walks must agree on corpus membership.

    If the hash counted a file the chunker skipped, editing noise would force a
    pointless rebuild; if it skipped one the chunker counted, a real edit would
    go undetected.
    """
    d = tmp_path / "domain"
    write(d / "real.md", "# Real\ncontent\n")
    before = I.source_hash(d)
    write(d / ".pytest_cache" / "README.md", "# noise\nnoise\n")
    assert I.source_hash(d) == before
