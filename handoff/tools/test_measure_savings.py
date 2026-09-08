"""Tests for measure_savings.py."""

from pathlib import Path

import pytest

import measure_savings as M

VALID_HANDOFF = """\
HANDOFF v3.0 | 2026-03-14 | supersedes: none | session-length: short
OBJ: ship the export feature

STATE
  src/export.py | v1 | 4L 40B | CSV export helper
DECIDED
  exports over 10k rows return 413

PROPOSED
  Redis-backed queue for large exports

REJECTED
  client-side generation | memory footprint too large

OPEN
  which queue backend is approved | blocks: sizing async work

UNVERIFIED
  all consumers tolerate a 413 | never confirmed with API consumers

PATTERN
  CSV escaping edge cases found late | occurrences: 2

FIRST
  ask ops which queue backend is approved
"""


def test_parse_extracts_header_and_obj():
    p = M.parse_handoff(VALID_HANDOFF)
    assert p.header_fields["version"] == "3.0"
    assert p.header_fields["supersedes"].strip() == "none"
    assert p.header_fields["length"] == "short"
    assert p.obj == "ship the export feature"


def test_parse_splits_sections_correctly():
    p = M.parse_handoff(VALID_HANDOFF)
    assert len(p.sections["STATE"]) == 1
    assert len(p.sections["DECIDED"]) == 1
    assert len(p.sections["FIRST"]) == 1
    assert p.sections["FIRST"][0].startswith("ask ops")


def test_lint_clean_document_has_no_violations():
    assert M.lint(M.parse_handoff(VALID_HANDOFF)) == []


def test_content_line_starting_with_a_section_word_stays_content():
    """Indentation, not the first word, decides what is a label.

    Before this was fixed, an OPEN item beginning with 'PATTERN' started a new section
    there, truncating OPEN and mis-attributing every following line.
    """
    doc = VALID_HANDOFF.replace(
        "OPEN\n  which queue backend is approved | blocks: sizing async work\n",
        "OPEN\n  which queue backend is approved | blocks: sizing async work\n"
        "  PATTERN detection needs more runs | blocks: nothing yet\n"
        "  STATE of the worker is unclear | blocks: deploy\n",
    )
    p = M.parse_handoff(doc)
    assert len(p.sections["OPEN"]) == 3
    assert len(p.sections["PATTERN"]) == 1  # unchanged, not hijacked
    assert p.sections["PATTERN"][0].startswith("CSV escaping")


def test_indented_obj_like_line_is_not_read_as_the_objective():
    doc = VALID_HANDOFF.replace(
        "DECIDED\n  exports over 10k rows return 413\n",
        "DECIDED\n  exports over 10k rows return 413\n  OBJ: this is a decision, not the header\n",
    )
    p = M.parse_handoff(doc)
    assert p.obj == "ship the export feature"
    assert len(p.sections["DECIDED"]) == 2


def test_section_label_with_spec_comment_is_recognized():
    """The SKILL.md template writes labels as 'STATE   <=8 lines, paths first'."""
    doc = (
        "HANDOFF v3.0 | 2026-01-01 | supersedes: none | session-length: short\n"
        "OBJ: x\n"
        "STATE            <=8 lines, paths first\n"
        "  a.py | v1 | 1L 1B | thing\n"
        "FIRST            1 line\n"
        "  do the thing\n"
    )
    p = M.parse_handoff(doc)
    assert len(p.sections["STATE"]) == 1
    assert len(p.sections["FIRST"]) == 1


def test_lint_flags_cap_violation():
    over = VALID_HANDOFF.replace(
        "PATTERN\n  CSV escaping edge cases found late | occurrences: 2\n",
        "PATTERN\n" + "\n".join(f"  issue {i} | occurrences: 2" for i in range(5)) + "\n",
    )
    violations = M.lint(M.parse_handoff(over))
    assert any("PATTERN" in v for v in violations)


def test_lint_flags_missing_first():
    no_first = VALID_HANDOFF.replace(
        "FIRST\n  ask ops which queue backend is approved\n", "FIRST\n"
    )
    violations = M.lint(M.parse_handoff(no_first))
    assert any("FIRST is empty" in v for v in violations)


def test_lint_flags_multiple_first_lines():
    two_first = VALID_HANDOFF.replace(
        "FIRST\n  ask ops which queue backend is approved\n",
        "FIRST\n  do thing one\n  do thing two\n",
    )
    violations = M.lint(M.parse_handoff(two_first))
    assert any("more than one line" in v for v in violations)


def test_lint_flags_missing_header():
    no_header = VALID_HANDOFF.split("\n", 1)[1]
    violations = M.lint(M.parse_handoff(no_header))
    assert any("no HANDOFF header" in v for v in violations)


def test_lint_requires_context_degradation_note_on_long_sessions():
    long_session = VALID_HANDOFF.replace("session-length: short", "session-length: long")
    violations = M.lint(M.parse_handoff(long_session))
    assert any("context degradation" in v for v in violations)

    long_with_note = long_session.replace(
        "UNVERIFIED\n  all consumers tolerate a 413 | never confirmed with API consumers\n",
        "UNVERIFIED\n  all consumers tolerate a 413 | never confirmed with API consumers\n"
        "  snapshot authored under context degradation | session ran past 30 turns\n",
    )
    violations2 = M.lint(M.parse_handoff(long_with_note))
    assert not any("context degradation" in v for v in violations2)


def test_state_check_passes_on_matching_file(tmp_path: Path):
    f = tmp_path / "export.py"
    content = "line1\nline2\nline3\nline4\n"
    # newline="" suppresses platform newline translation (LF -> CRLF on Windows),
    # so the byte count computed below from the in-memory string matches what is
    # actually written to disk on every platform. Without this, Path.write_text's
    # default text-mode write inflates the on-disk size by one byte per line on
    # Windows, and state_check() -- correctly reading real bytes off disk -- reports
    # a mismatch this fixture itself introduced.
    f.write_text(content, encoding="utf-8", newline="")
    n_lines = content.count("\n")
    n_bytes = len(content.encode("utf-8"))
    doc = f"STATE\n  export.py | v1 | {n_lines}L {n_bytes}B | test file\nFIRST\n  do it\n"
    parsed = M.parse_handoff("HANDOFF v3.0 | d | supersedes: none | session-length: short\n"
                              "OBJ: x\n" + doc)
    assert M.state_check(parsed, tmp_path) == []


def test_state_check_flags_drift(tmp_path: Path):
    f = tmp_path / "export.py"
    f.write_text("line1\nline2\n", encoding="utf-8", newline="")  # 2 lines, but snapshot claims 99
    doc = "STATE\n  export.py | v1 | 99L 999B | test file\nFIRST\n  do it\n"
    parsed = M.parse_handoff("HANDOFF v3.0 | d | supersedes: none | session-length: short\n"
                              "OBJ: x\n" + doc)
    findings = M.state_check(parsed, tmp_path)
    assert len(findings) == 1
    assert "export.py" in findings[0]


def test_state_check_flags_missing_file(tmp_path: Path):
    doc = "STATE\n  nowhere.py | v1 | 5L 50B | ghost file\nFIRST\n  do it\n"
    parsed = M.parse_handoff("HANDOFF v3.0 | d | supersedes: none | session-length: short\n"
                              "OBJ: x\n" + doc)
    findings = M.state_check(parsed, tmp_path)
    assert len(findings) == 1
    assert "no file at" in findings[0]


def test_state_check_resolves_home_relative_paths(tmp_path, monkeypatch):
    """'~/...' is the form the protocol's examples and prior handoffs use.

    Joining it onto base_dir produced '<base>/~/...' and false-alarmed every row.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows
    target = tmp_path / ".claude" / "skills" / "x.md"
    target.parent.mkdir(parents=True)
    content = "a\nb\nc\n"
    # See the comment in test_state_check_passes_on_matching_file: newline=""
    # keeps the on-disk bytes matching what's computed from the in-memory string.
    target.write_text(content, encoding="utf-8", newline="")
    n_lines, n_bytes = content.count("\n"), len(content.encode())
    doc = (f"STATE\n  ~/.claude/skills/x.md | v1 | {n_lines}L {n_bytes}B | thing\n"
           "FIRST\n  do it\n")
    parsed = M.parse_handoff("HANDOFF v3.0 | d | supersedes: none | session-length: short\n"
                              "OBJ: x\n" + doc)
    assert M.state_check(parsed, Path("/unrelated/base")) == []


def test_state_check_resolves_absolute_paths(tmp_path):
    target = tmp_path / "abs.py"
    content = "x\ny\n"
    # See the comment in test_state_check_passes_on_matching_file.
    target.write_text(content, encoding="utf-8", newline="")
    doc = (f"STATE\n  {target} | v1 | 2L {len(content.encode())}B | thing\n"
           "FIRST\n  do it\n")
    parsed = M.parse_handoff("HANDOFF v3.0 | d | supersedes: none | session-length: short\n"
                              "OBJ: x\n" + doc)
    assert M.state_check(parsed, Path("/unrelated/base")) == []


def test_state_check_skips_non_path_rows(tmp_path: Path):
    # install and process rows have three pipe-fields, not four, and no <n>L <n>B shape
    doc = ("STATE\n"
           "  requests | 2.31.0 | installed globally\n"
           "  worker | running | background export job\n"
           "FIRST\n  do it\n")
    parsed = M.parse_handoff("HANDOFF v3.0 | d | supersedes: none | session-length: short\n"
                              "OBJ: x\n" + doc)
    assert M.state_check(parsed, tmp_path) == []


def test_compare_savings_computes_a_real_percentage():
    handoff = "STATE\n  a | v1 | 1L 1B | x\nFIRST\n  y\n"  # short
    prose = "This is a much longer prose description of the exact same state. " * 5
    result = M.compare_savings(handoff, prose)
    assert result["saved_pct"] > 0
    assert result["handoff_tokens_estimated"] < result["prose_tokens_estimated"]


def test_compare_savings_rejects_empty_prose():
    with pytest.raises(ValueError):
        M.compare_savings("STATE\n  a | v1 | 1L 1B | x\n", "")


def test_cli_lint_exits_nonzero_on_violations(tmp_path: Path, capsys):
    bad = tmp_path / "bad.md"
    bad.write_text("FIRST\n  a\n  b\n", encoding="utf-8")  # two FIRST lines, no header
    assert M.main([str(bad), "--lint"]) == 1
    out = capsys.readouterr().out
    assert "violation" in out


def test_cli_lint_exits_zero_on_clean_doc(tmp_path: Path, capsys):
    good = tmp_path / "good.md"
    good.write_text(VALID_HANDOFF, encoding="utf-8")
    assert M.main([str(good), "--lint"]) == 0
    assert "clean" in capsys.readouterr().out


def test_cli_defaults_to_lint_with_no_flags(tmp_path: Path, capsys):
    good = tmp_path / "good.md"
    good.write_text(VALID_HANDOFF, encoding="utf-8")
    assert M.main([str(good)]) == 0
    assert "clean" in capsys.readouterr().out


def test_cli_state_check(tmp_path: Path, capsys):
    target = tmp_path / "export.py"
    content = "a\nb\n"
    # See the comment in test_state_check_passes_on_matching_file.
    target.write_text(content, encoding="utf-8", newline="")
    n_lines, n_bytes = content.count("\n"), len(content.encode("utf-8"))
    doc = tmp_path / "h.md"
    doc.write_text(
        "HANDOFF v3.0 | d | supersedes: none | session-length: short\nOBJ: x\n"
        f"STATE\n  export.py | v1 | {n_lines}L {n_bytes}B | test\nFIRST\n  z\n",
        encoding="utf-8",
    )
    assert M.main([str(doc), "--state-check", "--base-dir", str(tmp_path)]) == 0
    assert "all path-shaped" in capsys.readouterr().out
