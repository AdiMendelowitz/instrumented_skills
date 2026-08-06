"""Tests for search.py.

The degradation states matter most here: "never indexed", "indexed but zero
matches", and "corrupt" must stay distinguishable, because a consuming skill
behaves differently in each case.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import index as I  # noqa: E402
import search as S  # noqa: E402


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def corpus(tmp_path: Path) -> Path:
    d = tmp_path / "domain"
    write(d / "alpha.md", "# Caching\nprompt caching breaks even after three re-reads\n")
    write(d / "beta.md", "# Handoff\nsnapshot carries unverified claims forward\n")
    write(d / "gamma.md", "# Retro\nfriction recurred across three sessions\n")
    return d


# --- ranking ----------------------------------------------------------------


def test_search_finds_matching_chunk(tmp_path):
    idx = I.build_index(corpus(tmp_path))
    results = S.search_domain(idx, "caching break even")
    assert results
    assert results[0]["source_file"] == "alpha.md"


def test_search_ranks_best_match_first(tmp_path):
    idx = I.build_index(corpus(tmp_path))
    results = S.search_domain(idx, "unverified snapshot")
    assert results[0]["source_file"] == "beta.md"


def test_search_returns_empty_for_unrelated_query(tmp_path):
    """Zero-score hits must be dropped.

    BM25 scores every chunk, so without filtering an unrelated query returns
    top_k results that look like hits. "No results" has to be honest for the
    consuming skill's degradation handling to mean anything.
    """
    idx = I.build_index(corpus(tmp_path))
    assert S.search_domain(idx, "photosynthesis chlorophyll stomata") == []


def test_search_returns_empty_for_empty_query(tmp_path):
    idx = I.build_index(corpus(tmp_path))
    assert S.search_domain(idx, "   ") == []


def test_search_respects_top_k(tmp_path):
    idx = I.build_index(corpus(tmp_path))
    results = S.search_domain(idx, "three", top_k=1)
    assert len(results) == 1


def test_search_top_k_zero_returns_nothing(tmp_path):
    idx = I.build_index(corpus(tmp_path))
    assert S.search_domain(idx, "three", top_k=0) == []


def test_ranks_are_sequential_from_one(tmp_path):
    idx = I.build_index(corpus(tmp_path))
    results = S.search_domain(idx, "three")
    assert [r["rank"] for r in results] == list(range(1, len(results) + 1))


def test_results_carry_required_fields(tmp_path):
    idx = I.build_index(corpus(tmp_path))
    r = S.search_domain(idx, "caching")[0]
    assert set(r) >= {"rank", "score", "source_file", "heading", "text", "truncated"}


def test_search_matches_unicode_query(tmp_path):
    d = tmp_path / "domain"
    write(d / "u.md", "# Café\nnaïve findings über alles\n")
    idx = I.build_index(d)
    results = S.search_domain(idx, "naïve")
    assert results
    assert "über" in results[0]["text"]


# --- excerpting -------------------------------------------------------------


def test_long_text_is_truncated_and_flagged(tmp_path):
    d = tmp_path / "domain"
    write(d / "long.md", "# Long\n" + ("caching " * 500))
    idx = I.build_index(d)
    r = S.search_domain(idx, "caching", excerpt_chars=100)[0]
    assert r["truncated"] is True
    assert len(r["text"]) <= 103


def test_short_text_is_not_flagged(tmp_path):
    idx = I.build_index(corpus(tmp_path))
    r = S.search_domain(idx, "caching")[0]
    assert r["truncated"] is False


# --- CLI degradation states -------------------------------------------------


def run_cli(argv, capsys) -> dict:
    rc = S.main(argv)
    assert rc == 0
    return json.loads(capsys.readouterr().out)


def test_cli_ok_status(tmp_path, capsys):
    corpus(tmp_path)
    out = run_cli(
        ["--root", str(tmp_path), "--domain", "domain", "--query", "caching"], capsys
    )
    assert out["status"] == "ok"
    assert out["results"]


def test_cli_no_results_distinct_from_no_index(tmp_path, capsys):
    corpus(tmp_path)
    out = run_cli(
        ["--root", str(tmp_path), "--domain", "domain", "--query", "photosynthesis"],
        capsys,
    )
    assert out["status"] == "no_results"
    assert out["results"] == []


def test_cli_no_index_status(tmp_path, capsys):
    out = run_cli(
        ["--root", str(tmp_path), "--domain", "absent", "--query", "anything"], capsys
    )
    assert out["status"] == "no_index"
    assert out["results"] == []


def test_cli_empty_corpus_status(tmp_path, capsys):
    (tmp_path / "hollow").mkdir()
    out = run_cli(
        ["--root", str(tmp_path), "--domain", "hollow", "--query", "anything"], capsys
    )
    assert out["status"] == "empty_corpus"


def test_cli_reports_index_state(tmp_path, capsys):
    corpus(tmp_path)
    first = run_cli(
        ["--root", str(tmp_path), "--domain", "domain", "--query", "caching"], capsys
    )
    second = run_cli(
        ["--root", str(tmp_path), "--domain", "domain", "--query", "caching"], capsys
    )
    assert first["index_state"] == "built"
    assert second["index_state"] == "cached"


def test_cli_clamps_top_k_to_max(tmp_path, capsys):
    corpus(tmp_path)
    out = run_cli(
        [
            "--root", str(tmp_path), "--domain", "domain",
            "--query", "three", "--top-k", "999",
        ],
        capsys,
    )
    assert len(out["results"]) <= S.MAX_TOP_K


def test_cli_output_is_valid_json_not_prose(tmp_path, capsys):
    """The contract is data for a caller, not a formatted string for a model."""
    corpus(tmp_path)
    S.main(["--root", str(tmp_path), "--domain", "domain", "--query", "caching"])
    json.loads(capsys.readouterr().out)  # raises if prose leaked in


# --- jsonl corpus end to end ------------------------------------------------


def test_search_over_jsonl_corpus(tmp_path):
    d = tmp_path / "domain"
    write(
        d / "log.jsonl",
        '{"f": "F1", "lens": "evidence-integrity", "anchor": "unsourced rate claim"}\n'
        '{"f": "F2", "lens": "pre-mortem", "anchor": "index never rebuilt"}\n',
    )
    idx = I.build_index(d)
    results = S.search_domain(idx, "evidence integrity unsourced")
    assert results
    assert results[0]["heading"] == "line 1"


def test_no_search_all_symbol_exists():
    """search_all was cut: it contradicted the deliberate merged-index non-goal."""
    assert not hasattr(S, "search_all")
