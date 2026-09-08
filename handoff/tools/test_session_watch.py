"""Tests for session_watch.py.

The hook's hard requirement is that it never interferes with prompt submission, so a
number of these assert silence-and-exit-zero on bad input rather than any output. The
state directory is redirected to a tmp_path in every test via the autouse fixture, so
no test can touch a real ~/.claude directory.
"""

import io
import json
import time
from pathlib import Path

import pytest

import session_watch as W


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Never let a test read or write the real marker directory."""
    d = tmp_path / "state"
    monkeypatch.setenv("HANDOFF_WATCH_STATE", str(d))
    monkeypatch.delenv("HANDOFF_WATCH", raising=False)
    monkeypatch.delenv("HANDOFF_WARN_TURNS", raising=False)
    monkeypatch.delenv("HANDOFF_URGE_TURNS", raising=False)
    return d


def write_transcript(path: Path, n_user_turns: int, extra_events: list | None = None) -> Path:
    events = []
    for i in range(n_user_turns):
        events.append({"type": "user", "message": {"content": f"message {i}"}})
        events.append({"type": "assistant", "message": {"content": "reply"}})
    events.extend(extra_events or [])
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return path


def run_main(monkeypatch, capsys, payload: dict | str) -> tuple[int, str]:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    code = W.main()
    return code, capsys.readouterr().out


# --- turn counting -----------------------------------------------------------

def test_counts_plain_user_turns(tmp_path):
    assert W.count_user_turns(write_transcript(tmp_path / "t.jsonl", 7)) == 7


def test_missing_transcript_counts_zero(tmp_path):
    assert W.count_user_turns(tmp_path / "absent.jsonl") == 0


def test_malformed_lines_are_skipped_not_fatal(tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text(
        json.dumps({"type": "user", "message": {"content": "real"}}) + "\n"
        + '{"type":"user" this is broken\n'
        + json.dumps({"type": "user", "message": {"content": "also real"}}) + "\n",
        encoding="utf-8",
    )
    assert W.count_user_turns(t) == 2


def test_tool_results_do_not_inflate_the_count(tmp_path):
    """tool_result events carry type 'user' but are not user turns.

    Counting them would fire the nudge several times early on a tool-heavy session.
    """
    t = write_transcript(tmp_path / "t.jsonl", 3, extra_events=[
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "x", "content": "output"}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "y", "content": "more"}]}},
    ])
    assert W.count_user_turns(t) == 3


def test_text_blocks_in_list_content_do_count(tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({
        "type": "user",
        "message": {"content": [{"type": "text", "text": "a real typed message"}]},
    }) + "\n", encoding="utf-8")
    assert W.count_user_turns(t) == 1


def test_meta_and_sidechain_events_are_excluded(tmp_path):
    t = write_transcript(tmp_path / "t.jsonl", 2, extra_events=[
        {"type": "user", "isMeta": True, "message": {"content": "injected"}},
        {"type": "user", "isSidechain": True, "message": {"content": "subagent"}},
    ])
    assert W.count_user_turns(t) == 2


def test_empty_user_messages_do_not_count(tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text(
        json.dumps({"type": "user", "message": {"content": "   "}}) + "\n"
        + json.dumps({"type": "user", "message": {"content": "real"}}) + "\n",
        encoding="utf-8",
    )
    assert W.count_user_turns(t) == 1


def test_prefilter_accepts_both_json_spacings(tmp_path):
    """Claude Code versions differ on separator spacing; both must count."""
    t = tmp_path / "t.jsonl"
    t.write_text(
        '{"type":"user","message":{"content":"compact"}}\n'
        '{"type": "user", "message": {"content": "spaced"}}\n',
        encoding="utf-8",
    )
    assert W.count_user_turns(t) == 2


def test_missing_message_key_does_not_raise(tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text('{"type":"user"}\n', encoding="utf-8")
    assert W.count_user_turns(t) == 0


# --- thresholds --------------------------------------------------------------

def test_defaults(monkeypatch):
    assert W.thresholds() == (W.DEFAULT_WARN_TURNS, W.DEFAULT_URGE_TURNS)


def test_env_override_parses(monkeypatch):
    monkeypatch.setenv("HANDOFF_WARN_TURNS", "5")
    monkeypatch.setenv("HANDOFF_URGE_TURNS", "9")
    assert W.thresholds() == (5, 9)


def test_malformed_env_override_falls_back(monkeypatch):
    monkeypatch.setenv("HANDOFF_WARN_TURNS", "not-a-number")
    assert W.thresholds()[0] == W.DEFAULT_WARN_TURNS


def test_nonpositive_override_falls_back(monkeypatch):
    monkeypatch.setenv("HANDOFF_WARN_TURNS", "0")
    assert W.thresholds()[0] == W.DEFAULT_WARN_TURNS


def test_urge_below_warn_is_corrected(monkeypatch):
    """urge <= warn would make the second signal unreachable."""
    monkeypatch.setenv("HANDOFF_WARN_TURNS", "20")
    monkeypatch.setenv("HANDOFF_URGE_TURNS", "10")
    warn, urge = W.thresholds()
    assert warn == 20 and urge > warn


# --- markers -----------------------------------------------------------------

def test_marker_prevents_refiring(tmp_path):
    base = tmp_path / "m"
    assert not W.already_fired(base, "s1", "warn")
    W.mark_fired(base, "s1", "warn")
    assert W.already_fired(base, "s1", "warn")
    assert not W.already_fired(base, "s1", "urge")   # other level still available
    assert not W.already_fired(base, "s2", "warn")   # other session unaffected


def test_mark_fired_survives_unwritable_path(tmp_path):
    blocked = tmp_path / "afile"
    blocked.write_text("not a directory", encoding="utf-8")
    W.mark_fired(blocked / "sub", "s", "warn")  # must not raise


def test_prune_removes_only_expired_markers(tmp_path):
    base = tmp_path / "m"
    base.mkdir()
    old, fresh = base / "old.warn", base / "fresh.warn"
    old.touch()
    fresh.touch()
    stale = time.time() - (W.MARKER_TTL_SECONDS + 100)
    import os as _os
    _os.utime(old, (stale, stale))
    assert W.prune_markers(base) == 1
    assert not old.exists() and fresh.exists()


def test_prune_on_missing_dir_is_safe(tmp_path):
    assert W.prune_markers(tmp_path / "never-made") == 0


# --- message content: factual, not imperative -------------------------------

def test_messages_state_facts_rather_than_issuing_commands():
    """The hooks reference warns imperative phrasing can trip injection defenses."""
    for msg in (W.build_message(25, W.Level.WARN), W.build_message(40, W.Level.URGE)):
        assert msg.startswith("Session state:")
        lowered = msg.lower()
        for imperative in ("tell the user", "you must", "do not repeat", "recommend that"):
            assert imperative not in lowered


def test_messages_hedge_the_count_because_the_transcript_lags():
    assert "at least" in W.build_message(25, W.Level.WARN)
    assert "at least" in W.build_message(40, W.Level.URGE)


def test_messages_name_the_skill_and_the_count():
    assert "/handoff" in W.build_message(25, W.Level.WARN)
    assert "25" in W.build_message(25, W.Level.WARN)
    assert "40" in W.build_message(40, W.Level.URGE)


def test_singular_turn_reads_correctly():
    """Only reachable at a lowered threshold, which is exactly what the documented
    verification command uses, so it is the first output a new user ever sees."""
    assert "1 user turn." in W.build_message(1, W.Level.URGE)
    assert "1 user turn," in W.build_message(1, W.Level.WARN)
    assert "2 user turns," in W.build_message(2, W.Level.WARN)


# --- main(): output contract and fail-open ----------------------------------

def test_output_is_plain_text_not_json(monkeypatch, capsys, tmp_path):
    """JSON on this event triggers a known first-prompt error; plain text does not."""
    monkeypatch.setenv("HANDOFF_WARN_TURNS", "3")
    monkeypatch.setenv("HANDOFF_URGE_TURNS", "50")
    t = write_transcript(tmp_path / "t.jsonl", 4)
    code, out = run_main(monkeypatch, capsys, {"transcript_path": str(t), "session_id": "s"})
    assert code == 0
    assert out.strip().startswith("Session state:")
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


def test_silent_on_malformed_stdin(monkeypatch, capsys):
    code, out = run_main(monkeypatch, capsys, "this is not json")
    assert code == 0 and out.strip() == ""


def test_silent_on_non_dict_stdin(monkeypatch, capsys):
    code, out = run_main(monkeypatch, capsys, "[1, 2, 3]")
    assert code == 0 and out.strip() == ""


def test_silent_when_disabled(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HANDOFF_WATCH", "0")
    t = write_transcript(tmp_path / "t.jsonl", 99)
    code, out = run_main(monkeypatch, capsys, {"transcript_path": str(t), "session_id": "s"})
    assert code == 0 and out.strip() == ""


def test_silent_below_threshold(monkeypatch, capsys, tmp_path):
    t = write_transcript(tmp_path / "t.jsonl", 3)
    code, out = run_main(monkeypatch, capsys, {"transcript_path": str(t), "session_id": "s"})
    assert code == 0 and out.strip() == ""


def test_silent_without_transcript_path(monkeypatch, capsys):
    code, out = run_main(monkeypatch, capsys, {"session_id": "s"})
    assert code == 0 and out.strip() == ""


def test_does_not_repeat_the_same_level(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HANDOFF_WARN_TURNS", "3")
    monkeypatch.setenv("HANDOFF_URGE_TURNS", "50")
    t = write_transcript(tmp_path / "t.jsonl", 4)
    payload = {"transcript_path": str(t), "session_id": "s2"}
    _, first = run_main(monkeypatch, capsys, payload)
    _, second = run_main(monkeypatch, capsys, payload)
    assert first.strip() != "" and second.strip() == ""


def test_escalates_from_warn_to_urge(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HANDOFF_WARN_TURNS", "3")
    monkeypatch.setenv("HANDOFF_URGE_TURNS", "6")
    small = write_transcript(tmp_path / "a.jsonl", 4)
    _, warn_out = run_main(monkeypatch, capsys, {"transcript_path": str(small), "session_id": "s3"})
    assert "approaching" in warn_out
    big = write_transcript(tmp_path / "b.jsonl", 7)
    _, urge_out = run_main(monkeypatch, capsys, {"transcript_path": str(big), "session_id": "s3"})
    assert "materially" in urge_out


def test_exits_before_reading_transcript_once_urge_fired(monkeypatch, capsys, isolated_state):
    """The whole back half of a long session must not re-scan the transcript.

    Points at a nonexistent transcript: if the hook returns silently anyway, it proved
    it never tried to read it.
    """
    W.mark_fired(isolated_state, "s4", W.Level.URGE)
    code, out = run_main(monkeypatch, capsys, {
        "transcript_path": "/nonexistent/path/that/would/fail.jsonl", "session_id": "s4"})
    assert code == 0 and out.strip() == ""


def test_session_id_with_separators_cannot_escape_the_state_dir(monkeypatch, capsys, tmp_path, isolated_state):
    monkeypatch.setenv("HANDOFF_WARN_TURNS", "2")
    monkeypatch.setenv("HANDOFF_URGE_TURNS", "50")
    t = write_transcript(tmp_path / "t.jsonl", 3)
    run_main(monkeypatch, capsys, {"transcript_path": str(t), "session_id": "../../evil"})
    assert not (tmp_path / "evil.warn").exists()
    assert any(p.name.endswith(".warn") for p in isolated_state.iterdir())
