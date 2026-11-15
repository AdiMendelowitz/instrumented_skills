"""Tests for tools/context_payload.py, written from spec v1.1 section 5 only.

Run with CONTEXT_PAYLOAD set to the tool path. K1_SKILL_MD is needed by test 17.
Every input tree is built under pytest's tmp_path.
"""
import hashlib
import json
import math
import os
import subprocess
import sys

import pytest

TRIGGER_SENTENCE = (
    "Also use for context audits: shortening a CLAUDE.md, its imports, memory "
    "files or skill descriptions to cut startup context without changing behaviour."
)


@pytest.fixture
def tool():
    # Read inside the fixture so a missing variable fails the test, not the import.
    return os.environ["CONTEXT_PAYLOAD"]


def run(tool, *args):
    return subprocess.run(
        [sys.executable, tool, *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def skill(root, name, description, body="Body text that must never be counted.\n"):
    write(
        root,
        f"skills/{name}/SKILL.md",
        f"---\nname: {name}\ndescription: {description}\n---\n{body}",
    )


def est(n_bytes, comment_bytes=0):
    return math.ceil((n_bytes - comment_bytes) / 4)


def measure(tool, root, *extra):
    proc = run(tool, "measure", root, "--json", *extra)
    return proc, (json.loads(proc.stdout) if proc.stdout.strip() else None)


def diff(tool, before, after, *extra):
    proc = run(tool, "diff", before, after, "--json", *extra)
    return proc, (json.loads(proc.stdout) if proc.stdout.strip() else None)


def by_path(data):
    return {item["path"]: item for item in data["items"]}


def snapshot(root):
    snap = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            snap[str(p.relative_to(root))] = hashlib.md5(p.read_bytes()).hexdigest()
    return snap


# 1
def test_1_bare_claude_md(tool, tmp_path):
    text = "Be direct.\nUse British spelling.\n"
    write(tmp_path, "CLAUDE.md", text)
    proc, data = measure(tool, tmp_path)
    assert proc.returncode == 0
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["path"] == "CLAUDE.md"
    assert item["kind"] == "claude_md"
    assert item["bytes"] == len(text.encode("utf-8"))
    assert item["est_tokens"] == math.ceil(item["bytes"] / 4)
    assert item["label"] == "estimate"
    assert data["always_loaded_est_tokens"] == item["est_tokens"]


# 2
def test_2_one_level_import(tool, tmp_path):
    write(tmp_path, "CLAUDE.md", "Top rule.\n@rules.md\n")
    write(tmp_path, "rules.md", "Imported rule.\n")
    proc, data = measure(tool, tmp_path)
    assert proc.returncode == 0
    assert len(data["items"]) == 2
    items = by_path(data)
    assert items["CLAUDE.md"]["kind"] == "claude_md"
    assert items["rules.md"]["kind"] == "import"


# 3
def test_3_nested_import_two_levels(tool, tmp_path):
    write(tmp_path, "CLAUDE.md", "@docs/a.md\n")
    write(tmp_path, "docs/a.md", "Level one.\n@sub/b.md\n")
    write(tmp_path, "docs/sub/b.md", "Level two.\n")
    # A decoy at ROOT/sub/b.md shows resolution is relative to the importer.
    write(tmp_path, "sub/b.md", "Decoy.\n")
    proc, data = measure(tool, tmp_path)
    assert proc.returncode == 0
    assert len(data["items"]) == 3
    items = by_path(data)
    assert set(items) == {"CLAUDE.md", "docs/a.md", "docs/sub/b.md"}
    assert items["docs/a.md"]["kind"] == "import"
    assert items["docs/sub/b.md"]["kind"] == "import"


# 4
def test_4_import_cycle(tool, tmp_path):
    write(tmp_path, "CLAUDE.md", "@a.md\n")
    write(tmp_path, "a.md", "A.\n@b.md\n")
    write(tmp_path, "b.md", "B.\n@a.md\n")
    proc, data = measure(tool, tmp_path)
    assert proc.returncode == 3
    both = [w for w in data["warnings"] if "a.md" in w and "b.md" in w]
    assert both, "no single warning names both cycle files"
    assert any(w.index("a.md") < w.index("b.md") for w in both)


# 5
def test_5_missing_import(tool, tmp_path):
    write(tmp_path, "CLAUDE.md", "@missing.md\n")
    proc, data = measure(tool, tmp_path)
    assert proc.returncode == 3
    assert "missing.md" in "\n".join(data["warnings"])


# 6
def test_6_import_escaping_root(tool, tmp_path):
    secret = "SECRET_SENTINEL_9f3a"
    write(tmp_path, "outside/secret_outside.md", secret + "\n")

    def check_escape(root, escaping_line):
        write(root, "inside.md", "Inside rule.\n")
        write(root, "CLAUDE.md", f"@inside.md\n{escaping_line}\n")
        proc = run(tool, "measure", root, "--json")
        assert proc.returncode == 4
        assert secret not in proc.stdout
        assert secret not in proc.stderr
        assert len(proc.stderr.strip().splitlines()) == 1
        if proc.stdout.strip():
            data = json.loads(proc.stdout)
            assert secret not in json.dumps(data)
            assert not any("secret_outside" in i["path"] for i in data["items"])
        # Positive control: with the escaping import removed, the in-ROOT import resolves.
        write(root, "CLAUDE.md", "@inside.md\n")
        proc, data = measure(tool, root)
        assert proc.returncode == 0
        assert by_path(data)["inside.md"]["kind"] == "import"
        assert secret not in proc.stdout
        assert not any("secret_outside" in i["path"] for i in data["items"])

    # Escape through "..".
    check_escape(tmp_path / "root_a", "@../outside/secret_outside.md")

    # Escape through a symlink.
    root_b = tmp_path / "root_b"
    root_b.mkdir()
    try:
        os.symlink(tmp_path / "outside" / "secret_outside.md", root_b / "link.md")
    except (OSError, NotImplementedError):
        pytest.fail("could not create a symlink to test the symlink escape")
    check_escape(root_b, "@link.md")


# 7
def test_7_html_comment_417_bytes(tool, tmp_path):
    comment = "<!--" + "x" * (417 - len("<!---->")) + "-->"
    assert len(comment.encode("utf-8")) == 417
    with_comment = "Rule one.\n" + comment + "\nRule two.\n"

    root_c = tmp_path / "with_comment"
    root_p = tmp_path / "plain"
    write(root_c, "CLAUDE.md", with_comment)
    write(root_p, "CLAUDE.md", with_comment.replace(comment, ""))

    proc_c, data_c = measure(tool, root_c)
    proc_p, data_p = measure(tool, root_p)
    assert proc_c.returncode == 0
    assert proc_p.returncode == 0
    item_c = data_c["items"][0]
    item_p = data_p["items"][0]
    assert item_c["comment_bytes"] == 417
    assert item_p["comment_bytes"] == 0
    assert item_c["bytes"] == len(with_comment.encode("utf-8"))
    assert item_c["est_tokens"] == item_p["est_tokens"]
    assert item_c["est_tokens"] == est(item_c["bytes"], 417)


# 7a
def test_7a_at_signs_not_imports(tool, tmp_path):
    """Must-not-match: none of these @ forms is an import, so no import is found."""
    text = (
        "Contact user@example.com for access.\n"
        "Docstring tag @param name is not an import.\n"
        "Mail dev@notes.md is not an import either.\n"
    )
    write(tmp_path, "CLAUDE.md", text)
    proc, data = measure(tool, tmp_path)
    assert proc.returncode == 0
    assert len(data["items"]) == 1
    assert data["items"][0]["kind"] == "claude_md"
    assert not [i for i in data["items"] if i["kind"] == "import"]
    assert data["warnings"] == []

    # Positive control: a real import in the same kind of tree is found, so a
    # tool that never parses imports fails here.
    root2 = tmp_path / "control"
    write(root2, "CLAUDE.md", text + "@sub.md\n")
    write(root2, "sub.md", "Real import.\n")
    proc, data = measure(tool, root2)
    assert proc.returncode == 0
    assert len(data["items"]) == 2
    assert by_path(data)["sub.md"]["kind"] == "import"
    assert [i["path"] for i in data["items"] if i["kind"] == "import"] == ["sub.md"]


# 8
def test_8_skill_description_from_frontmatter_only(tool, tmp_path):
    desc = "Use when auditing context"
    write(tmp_path, "CLAUDE.md", "Rule.\n")
    # Quoted value: quotes are stripped from the counted bytes.
    write(
        tmp_path,
        "skills/alpha/SKILL.md",
        f'---\nname: alpha\ndescription: "{desc}"\n---\n' + ("Long body text. " * 200) + "\n",
    )
    proc, data = measure(tool, tmp_path)
    assert proc.returncode == 0
    items = by_path(data)
    row = items["skills/alpha/SKILL.md"]
    assert row["kind"] == "skill_description"
    assert row["bytes"] == len(desc.encode("utf-8"))
    assert row["est_tokens"] == est(row["bytes"])
    assert data["always_loaded_est_tokens"] == items["CLAUDE.md"]["est_tokens"] + row["est_tokens"]


# 9
def test_9_named_not_imported_is_on_demand(tool, tmp_path):
    write(tmp_path, "CLAUDE.md", "Details live in ondemand/guide.md when needed.\n")
    write(tmp_path, "ondemand/guide.md", "A long guide. " * 50)
    write(tmp_path, "ondemand/other.md", "Never named anywhere.\n")
    proc, data = measure(tool, tmp_path)
    assert proc.returncode == 0
    items = by_path(data)
    assert items["ondemand/guide.md"]["kind"] == "on_demand"
    assert "ondemand/other.md" not in items
    assert data["always_loaded_est_tokens"] == items["CLAUDE.md"]["est_tokens"]


# 10
def test_10_self_row(tool, tmp_path):
    root = tmp_path / "root"
    write(root, "CLAUDE.md", "Rule.\n")
    desc = "Token-aware skill description for the self row"
    self_md = tmp_path / "selfdir" / "SKILL.md"
    write(tmp_path / "selfdir", "SKILL.md", f"---\nname: token-aware\ndescription: {desc}\n---\nBody.\n")
    proc, data = measure(tool, root, "--self", self_md)
    assert proc.returncode == 0
    rows = [i for i in data["items"] if i["kind"] == "self"]
    assert len(rows) == 1
    row = rows[0]
    assert row["path"] == str(self_md)
    assert row["bytes"] == len(desc.encode("utf-8"))
    assert row["est_tokens"] == est(row["bytes"])
    assert (
        data["always_loaded_est_tokens"] - data["always_loaded_excl_self_est_tokens"]
        == row["est_tokens"]
    )
    assert data["always_loaded_excl_self_est_tokens"] == by_path(data)["CLAUDE.md"]["est_tokens"]


# 11
def test_11_diff_triggers_phrase_dropped(tool, tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    for root in (before, after):
        write(root, "CLAUDE.md", "Rule.\n")
    skill(before, "alpha", "Use for context audits and for shortening files")
    skill(after, "alpha", "Use for shortening files")
    trig = write(tmp_path, "triggers.txt", "alpha\tcontext audits\n")
    proc, data = diff(tool, before, after, "--triggers", trig)
    assert proc.returncode == 1
    assert data["guards"]["trigger_loss"] == [{"skill": "alpha", "phrase": "context audits"}]


# 11a
def test_11a_diff_no_triggers_shortened_description(tool, tmp_path):
    """Must-not-match: without --triggers the guard cannot fire, only warnings."""
    before, after = tmp_path / "before", tmp_path / "after"
    for root in (before, after):
        write(root, "CLAUDE.md", "Rule.\n")
    skill(before, "alpha", "Use for quokka audits and for shortening files")
    skill(after, "alpha", "Use for shortening files")
    proc, data = diff(tool, before, after)
    assert proc.returncode == 0
    assert data["guards"]["trigger_loss"] == []
    old = "Use for quokka audits and for shortening files"
    new = "Use for shortening files"
    dropped = set(old.split()) - set(new.split())
    assert dropped == {"quokka", "audits", "and"}
    joined = "\n".join(data["warnings"])
    for word in dropped:
        assert word in joined


# 12
def test_12_diff_displaced_line(tool, tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    moved = "Always cite the source file for every claim."
    naming = "Extra detail is in ondemand/rules.md for reference."
    write(before, "CLAUDE.md", f"{moved}\n{naming}\n")
    write(before, "ondemand/rules.md", "Other detail.\n")
    write(after, "CLAUDE.md", f"{naming}\n")
    write(after, "ondemand/rules.md", f"Other detail.\n  {moved}  \n")
    proc, data = diff(tool, before, after)
    assert proc.returncode == 0
    displaced = data["guards"]["displaced"]
    assert len(displaced) == 1
    entry = displaced[0]
    assert entry["line"].strip() == moved
    assert entry["from"] == "CLAUDE.md"
    assert entry["to"] == "ondemand/rules.md"
    assert entry["named_by"].strip() == naming


# 13
def test_13_diff_pinned_rule_removed(tool, tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    pinned_line = "Never share private data outside the session."
    write(before, "CLAUDE.md", f"{pinned_line}\nBe brief.\n")
    write(after, "CLAUDE.md", "Be brief.\n")
    pinned = write(tmp_path, "pinned.txt", "private data\n")
    proc, data = diff(tool, before, after, "--pinned", pinned)
    assert proc.returncode == 1
    moved = data["guards"]["pinned_rule_moved"]
    assert len(moved) == 1
    assert moved[0]["line"].strip() == pinned_line
    assert moved[0]["from"] == "CLAUDE.md"
    assert moved[0]["pattern"] == "private data"


# 14
def test_14_diff_shortening_only(tool, tmp_path):
    """Must-not-match: --triggers and --pinned are given but nothing in them is hit."""
    before, after = tmp_path / "before", tmp_path / "after"
    write(before, "CLAUDE.md", "Be brief and precise in all written output, please.\nUse British spelling.\n")
    write(after, "CLAUDE.md", "Be brief.\nUse British spelling.\n")
    skill(before, "alpha", "Use for context audits and for shortening files in detail")
    skill(after, "alpha", "Use for context audits")
    trig = write(tmp_path, "triggers.txt", "alpha\tcontext audits\n")
    pinned = write(tmp_path, "pinned.txt", "private data\nsafety rule\n")
    proc, data = diff(tool, before, after, "--triggers", trig, "--pinned", pinned)
    assert proc.returncode == 0
    assert data["total_est_tokens_delta"] < 0
    assert data["guards"]["trigger_loss"] == []
    assert data["guards"]["pinned_rule_moved"] == []


# 14a
def test_14a_memory_file_imported(tool, tmp_path):
    write(tmp_path, "CLAUDE.md", "@memory/prefs.md\n")
    write(tmp_path, "memory/prefs.md", "Prefer British spelling.\n")
    write(tmp_path, "memory/unused.md", "Never imported and never named.\n")
    proc, data = measure(tool, tmp_path)
    assert proc.returncode == 0
    items = by_path(data)
    assert items["memory/prefs.md"]["kind"] == "memory"
    assert "memory/unused.md" not in items
    assert not [i for i in data["items"] if i["kind"] == "on_demand"]
    assert data["always_loaded_est_tokens"] == (
        items["CLAUDE.md"]["est_tokens"] + items["memory/prefs.md"]["est_tokens"]
    )


# 14b
def test_14b_cycle_and_escape_together(tool, tmp_path):
    write(tmp_path, "outside/x.md", "Outside.\n")
    root = tmp_path / "root"
    write(root, "CLAUDE.md", "@a.md\n@../outside/x.md\n")
    write(root, "a.md", "A.\n@b.md\n")
    write(root, "b.md", "B.\n@a.md\n")
    proc = run(tool, "measure", root, "--json")
    assert proc.returncode == 4
    assert len(proc.stderr.strip().splitlines()) == 1


# 15
def test_15_json_keys(tool, tmp_path):
    root = tmp_path / "root"
    write(root, "CLAUDE.md", "@rules.md\nSee ondemand/guide.md for detail.\n")
    write(root, "rules.md", "Imported.\n")
    write(root, "ondemand/guide.md", "Guide.\n")
    skill(root, "alpha", "Use for alpha things")
    self_md = tmp_path / "SELF" / "SKILL.md"
    write(tmp_path / "SELF", "SKILL.md", "---\nname: s\ndescription: self desc\n---\nBody\n")

    proc, data = measure(tool, root, "--self", self_md)
    assert proc.returncode == 0
    assert set(data) == {"root", "items", "always_loaded_est_tokens",
                         "always_loaded_excl_self_est_tokens", "warnings"}
    assert isinstance(data["warnings"], list)
    kinds = set()
    for item in data["items"]:
        assert set(item) == {"path", "kind", "bytes", "comment_bytes", "est_tokens", "label"}
        assert item["label"] == "estimate"
        kinds.add(item["kind"])
    assert kinds <= {"claude_md", "import", "memory", "skill_description", "on_demand", "self"}

    # A diff in which every guard fires, so the guard entry keys can be checked too.
    before, after = tmp_path / "before", tmp_path / "after"
    write(before, "CLAUDE.md", "Never share private data.\nMoved rule here.\nSee ondemand/g.md.\n")
    write(before, "ondemand/g.md", "Other.\n")
    write(after, "CLAUDE.md", "See ondemand/g.md.\n")
    write(after, "ondemand/g.md", "Other.\nMoved rule here.\n")
    skill(before, "alpha", "Use for context audits please")
    skill(after, "alpha", "Use for tidying")
    trig = write(tmp_path, "t.txt", "alpha\tcontext audits\n")
    pinned = write(tmp_path, "p.txt", "private data\n")
    proc, data = diff(tool, before, after, "--triggers", trig, "--pinned", pinned)
    assert proc.returncode == 1
    assert set(data) == {"before", "after", "deltas", "total_est_tokens_delta",
                         "guards", "warnings"}
    for delta in data["deltas"]:
        assert set(delta) == {"path", "kind", "bytes_delta", "est_tokens_delta"}
    guards = data["guards"]
    assert set(guards) == {"trigger_loss", "displaced", "pinned_rule_moved"}
    for key in guards:
        assert len(guards[key]) >= 1
    assert set(guards["trigger_loss"][0]) == {"skill", "phrase"}
    assert set(guards["displaced"][0]) == {"line", "from", "to", "named_by"}
    assert set(guards["pinned_rule_moved"][0]) == {"line", "from", "pattern"}


# 16
def test_16_measured_tree_unchanged(tool, tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    for root, extra in ((before, "Old extra line.\n"), (after, "")):
        write(root, "CLAUDE.md", f"@memory/m.md\nSee ondemand/g.md.\n{extra}")
        write(root, "memory/m.md", "Memory.\n")
        write(root, "ondemand/g.md", "Guide.\n")
        skill(root, "alpha", "Use for context audits")
    trig = write(tmp_path, "t.txt", "alpha\tcontext audits\n")
    pinned = write(tmp_path, "p.txt", "nothing matches\n")
    self_md = tmp_path / "S" / "SKILL.md"
    write(tmp_path / "S", "SKILL.md", "---\nname: s\ndescription: d\n---\n")

    snap_before, snap_after = snapshot(before), snapshot(after)
    p1 = run(tool, "measure", before, "--json", "--self", self_md)
    p2 = run(tool, "measure", after, "--json")
    p3 = run(tool, "diff", before, after, "--json", "--triggers", trig, "--pinned", pinned)
    for proc in (p1, p2, p3):
        assert proc.returncode in (0, 1)
    for proc in (p1, p2):
        d = json.loads(proc.stdout)
        assert {"root", "items", "always_loaded_est_tokens",
                "always_loaded_excl_self_est_tokens", "warnings"} <= set(d)
    d = json.loads(p3.stdout)
    assert {"before", "after", "deltas", "total_est_tokens_delta", "guards", "warnings"} <= set(d)
    assert snapshot(before) == snap_before
    assert snapshot(after) == snap_after


# 17
def test_17_skill_md_contains_trigger_sentence():
    """Checks the K1 SKILL.md (path from K1_SKILL_MD) by design, not the tool."""
    skill_md = os.environ["K1_SKILL_MD"]
    with open(skill_md, encoding="utf-8") as fh:
        text = fh.read()
    assert TRIGGER_SENTENCE in text
