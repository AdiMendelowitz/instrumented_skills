#!/usr/bin/env python3
"""context_payload.py: static estimator of the startup context a Claude Code configuration loads.

Specification: notes/token-aware/plans/context-audit-spec-2026-10-26.md (v1.1), section 4.
Tests: tools/test_context_payload.py (21 tests, written from the specification only, ADR-25).

Commands
  measure ROOT [--json] [--self SKILL_MD]
  diff BEFORE AFTER [--json] [--triggers FILE] [--pinned FILE]

Every figure is an estimate: est_tokens = ceil((bytes - comment_bytes) / 4). The measured value of the
evaluation is the harness triple, never this tool. The tool reads only inside ROOT (plus the --self,
--triggers and --pinned files as given) and never writes anywhere.

Exit codes: 0 success, no guard fired; 1 diff ran and trigger_loss (with --triggers) or pinned_rule_moved
(with --pinned) fired; 2 usage error; 3 a missing import or an import cycle (named in warnings);
4 an import or reference resolving outside ROOT (nothing outside ROOT is read). Highest code wins.
JSON is printed on exits 0, 1 and 3; exits 2 and 4 print one line to stderr and nothing on stdout.

An unterminated `<!--` is not a comment: its bytes count and any import after it is followed.
`total_est_tokens_delta` is AFTER's always-loaded estimate minus BEFORE's, each side by its own kinds.

Stdlib only, Python 3.12+.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

IMPORT_RE = re.compile(r"(?<!\S)@([\w./-]+\.md)\b")
COMMENT_RE = re.compile(rb"<!--.*?-->", re.DOTALL)
ALWAYS_LOADED_KINDS = ("claude_md", "import", "memory", "skill_description", "self")
LABEL = "estimate"


class Escape(Exception):
    """An import or reference resolves outside ROOT; carries one line for stderr."""


# ----------------------------------------------------------------------------- helpers

def est_tokens(n_bytes: int, comment_bytes: int) -> int:
    return math.ceil(max(n_bytes - comment_bytes, 0) / 4)


def comment_bytes_of(data: bytes) -> int:
    return sum(len(m.group(0)) for m in COMMENT_RE.finditer(data))


def strip_comments(data: bytes) -> bytes:
    return COMMENT_RE.sub(b"", data)


def text_of(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def inside_root(candidate: Path, root_real: Path) -> bool:
    """True when the candidate, after resolving symlinks, lies strictly inside ROOT.

    The lexical path is checked too, so a symlink that points back inside ROOT through a path
    containing '..' is still accepted only if both forms stay inside ROOT.
    """
    lexical = Path(os.path.normpath(str(candidate)))
    try:
        real = Path(os.path.realpath(str(candidate)))
    except OSError:
        return False
    for p in (lexical, real):
        try:
            p.relative_to(root_real)
        except ValueError:
            return False
        if p == root_real:
            return False
    return True


def description_of(data: bytes) -> str | None:
    """Same-line `description:` value between the first `---` pair, quotes stripped; None if absent."""
    lines = text_of(data).splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        if line.startswith("description:"):
            value = line[len("description:"):].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value
    return None


def item(path: str, kind: str, n_bytes: int, comment: int) -> dict:
    return {"path": path, "kind": kind, "bytes": n_bytes, "comment_bytes": comment,
            "est_tokens": est_tokens(n_bytes, comment), "label": LABEL}


# ----------------------------------------------------------------------------- measure

class Measurement:
    def __init__(self, root: Path):
        self.root_given = root
        self.root = Path(os.path.realpath(str(root)))
        self.items: list[dict] = []
        self.warnings: list[str] = []
        self.exit_code = 0
        self.always_texts: dict[str, bytes] = {}      # rel path -> comment-stripped bytes
        self.always_lines: dict[str, list[str]] = {}  # rel path -> raw lines
        self.descriptions: dict[str, str] = {}        # skill dir name -> description
        self.skill_paths: dict[str, str] = {}         # skill dir name -> rel path
        self.on_demand: dict[str, list[str]] = {}     # rel path -> naming lines

    # imports -------------------------------------------------------------------------
    def _read_inside(self, path: Path, importer: str) -> bytes:
        if not inside_root(path, self.root):
            raise Escape("exit 4: reference from %s resolves outside ROOT" % importer)
        return path.read_bytes()

    def _walk_imports(self) -> None:
        claude = self.root / "CLAUDE.md"
        data = claude.read_bytes()
        self.items.append(item("CLAUDE.md", "claude_md", len(data), comment_bytes_of(data)))
        self.always_texts["CLAUDE.md"] = strip_comments(data)
        self.always_lines["CLAUDE.md"] = text_of(data).splitlines()
        seen: dict[str, bool] = {"CLAUDE.md": True}
        cycles_reported: set[tuple] = set()

        def visit(file_rel: str, data_: bytes, stack: list[str]) -> None:
            base = (self.root / file_rel).parent
            for m in IMPORT_RE.finditer(text_of(strip_comments(data_))):
                target = base / m.group(1)
                if not inside_root(target, self.root):
                    raise Escape("exit 4: import %s in %s resolves outside ROOT" % (m.group(1), file_rel))
                target_rel = rel_posix(Path(os.path.normpath(str(target))), self.root)
                if target_rel in stack:
                    cycle = stack[stack.index(target_rel):] + [target_rel]
                    key = tuple(cycle)
                    if key not in cycles_reported:
                        cycles_reported.add(key)
                        self.warnings.append("import cycle: " + " -> ".join(cycle))
                        self.exit_code = max(self.exit_code, 3)
                    continue
                if target_rel in seen:
                    continue
                if not target.is_file():
                    self.warnings.append("missing import: %s imported by %s" % (target_rel, file_rel))
                    self.exit_code = max(self.exit_code, 3)
                    seen[target_rel] = False
                    continue
                tdata = self._read_inside(target, file_rel)
                seen[target_rel] = True
                kind = "memory" if target_rel.startswith("memory/") else "import"
                self.items.append(item(target_rel, kind, len(tdata), comment_bytes_of(tdata)))
                self.always_texts[target_rel] = strip_comments(tdata)
                self.always_lines[target_rel] = text_of(tdata).splitlines()
                visit(target_rel, tdata, stack + [target_rel])

        visit("CLAUDE.md", data, ["CLAUDE.md"])

    # skills --------------------------------------------------------------------------
    def _skills(self) -> None:
        skills_dir = self.root / "skills"
        if not skills_dir.is_dir():
            return
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            if not inside_root(skill_md, self.root):
                raise Escape("exit 4: %s resolves outside ROOT" % rel_posix(skill_md, self.root))
            data = skill_md.read_bytes()
            desc = description_of(data)
            rel = rel_posix(skill_md, self.root)
            name = skill_md.parent.name
            if desc is None:
                self.warnings.append("no description in %s" % rel)
                desc = ""
            self.descriptions[name] = desc
            self.skill_paths[name] = rel
            self.items.append(item(rel, "skill_description", len(desc.encode("utf-8")), 0))
            self.always_texts[rel] = desc.encode("utf-8")

    # on demand -----------------------------------------------------------------------
    def _on_demand(self) -> None:
        listed = {it["path"] for it in self.items}
        # Import tokens are not references: strip them before searching for named paths.
        texts = {rel: IMPORT_RE.sub(" ", text_of(data)) for rel, data in self.always_texts.items()}
        files = []
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            dirnames.sort()
            for fn in filenames:
                files.append(Path(dirpath) / fn)
        for path in sorted(files):
            if not path.is_file():
                continue
            rel = rel_posix(path, self.root)
            if rel in listed:
                continue
            name_rx = re.compile(r"(?<![\w./-])" + re.escape(rel) + r"(?![\w-]|\.\w)")
            named_by = []
            for rel_src, text in texts.items():
                if name_rx.search(text):
                    for line in self.always_lines.get(rel_src, []):
                        visible = IMPORT_RE.sub(" ", re.sub(r"<!--.*?-->", "", line))
                        if name_rx.search(visible):
                            named_by.append(line)
            if not named_by:
                continue
            if not inside_root(path, self.root):
                raise Escape("exit 4: reference %s resolves outside ROOT" % rel)
            data = path.read_bytes()
            self.items.append(item(rel, "on_demand", len(data), comment_bytes_of(data)))
            self.on_demand[rel] = named_by

    # self ----------------------------------------------------------------------------
    def _self_row(self, self_md: str) -> None:
        p = Path(self_md)
        if not p.is_file():
            raise Usage("--self file not found: %s" % self_md)
        desc = description_of(p.read_bytes())
        if desc is None:
            self.warnings.append("no description in --self file %s" % self_md)
            desc = ""
        self.items.append(item(self_md, "self", len(desc.encode("utf-8")), 0))

    # driver --------------------------------------------------------------------------
    def run(self, self_md: str | None = None) -> "Measurement":
        if not (self.root / "CLAUDE.md").is_file():
            raise Usage("ROOT has no CLAUDE.md: %s" % self.root_given)
        self._walk_imports()
        self._skills()
        self._on_demand()
        if self_md is not None:
            self._self_row(self_md)
        return self

    def totals(self) -> tuple[int, int]:
        incl = sum(it["est_tokens"] for it in self.items if it["kind"] in ALWAYS_LOADED_KINDS)
        excl = sum(it["est_tokens"] for it in self.items if it["kind"] in ALWAYS_LOADED_KINDS and it["kind"] != "self")
        return incl, excl

    def to_json(self) -> dict:
        incl, excl = self.totals()
        return {"root": Path(self.root_given).as_posix(), "items": self.items, "always_loaded_est_tokens": incl,
                "always_loaded_excl_self_est_tokens": excl, "warnings": self.warnings}


class Usage(Exception):
    pass


# ----------------------------------------------------------------------------- diff

def read_lines_file(path: str, what: str) -> list[str]:
    p = Path(path)
    if not p.is_file():
        raise Usage("%s file not found: %s" % (what, path))
    return [ln for ln in p.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]


def diff_trees(before: Measurement, after: Measurement, triggers: str | None, pinned: str | None) -> tuple[dict, int]:
    warnings = list(before.warnings) + list(after.warnings)
    exit_code = max(before.exit_code, after.exit_code)
    b_items = {it["path"]: it for it in before.items}
    a_items = {it["path"]: it for it in after.items}
    deltas = []
    for path in sorted(set(b_items) | set(a_items)):
        b, a = b_items.get(path), a_items.get(path)
        kind = (a or b)["kind"]
        bd = (a["bytes"] if a else 0) - (b["bytes"] if b else 0)
        ed = (a["est_tokens"] if a else 0) - (b["est_tokens"] if b else 0)
        deltas.append({"path": path, "kind": kind, "bytes_delta": bd, "est_tokens_delta": ed})
    # Scope: the always-loaded total of AFTER minus that of BEFORE, each side by its own kinds, so a file
    # that leaves the always-loaded set (import to on_demand) counts as a saving and one that joins it as a cost.
    total = after.totals()[1] - before.totals()[1]

    # trigger_loss and dropped-word warnings
    trigger_loss = []
    for name, b_desc in before.descriptions.items():
        a_desc = after.descriptions.get(name)
        if a_desc is None:
            warnings.append("skill %s absent in AFTER" % name)
            continue
        dropped = sorted(set(b_desc.split()) - set(a_desc.split()))
        if dropped:
            warnings.append("description of %s dropped words: %s" % (before.skill_paths[name], ", ".join(dropped)))
    if triggers is not None:
        for ln in read_lines_file(triggers, "--triggers"):
            if "\t" not in ln:
                warnings.append("triggers line without a tab ignored: %s" % ln)
                continue
            skill, phrase = ln.split("\t", 1)
            skill, phrase = skill.strip(), phrase.strip()
            b_desc = before.descriptions.get(skill)
            a_desc = after.descriptions.get(skill, "")
            if b_desc is None:
                continue
            if phrase.lower() in b_desc.lower() and phrase.lower() not in a_desc.lower():
                trigger_loss.append({"skill": skill, "phrase": phrase})

    # removed always-loaded lines (claude_md, import, memory), by file
    removed: list[tuple[str, str]] = []
    for rel, b_lines in before.always_lines.items():
        a_lines = after.always_lines.get(rel, [])
        a_set = {ln.strip() for ln in a_lines if ln.strip()}
        for ln in b_lines:
            if ln.strip() and ln.strip() not in a_set:
                removed.append((rel, ln))

    # displaced: removed lines reappearing in an on-demand file of AFTER
    displaced = []
    on_demand_lines = {}
    for rel in after.on_demand:
        data = (after.root / rel).read_bytes()
        on_demand_lines[rel] = {ln.strip() for ln in text_of(data).splitlines() if ln.strip()}
    for rel_from, ln in removed:
        for rel_to, lines in on_demand_lines.items():
            if ln.strip() in lines:
                naming = after.on_demand[rel_to]
                entry = {"line": ln, "from": rel_from, "to": rel_to, "named_by": naming[0] if naming else ""}
                if entry not in displaced:
                    displaced.append(entry)

    # pinned_rule_moved
    pinned_moved = []
    if pinned is not None:
        patterns = []
        for pat in read_lines_file(pinned, "--pinned"):
            try:
                patterns.append((pat, re.compile(pat)))
            except re.error as e:
                warnings.append("pinned pattern ignored (%s): %s" % (e, pat))
        for rel_from, ln in removed:
            for pat, rx in patterns:
                if rx.search(ln):
                    pinned_moved.append({"line": ln, "from": rel_from, "pattern": pat})

    if trigger_loss or pinned_moved:
        exit_code = max(exit_code, 1)
    out = {"before": Path(before.root_given).as_posix(), "after": Path(after.root_given).as_posix(), "deltas": deltas,
           "total_est_tokens_delta": total,
           "guards": {"trigger_loss": trigger_loss, "displaced": displaced, "pinned_rule_moved": pinned_moved},
           "warnings": warnings}
    return out, exit_code


# ----------------------------------------------------------------------------- CLI

def emit(obj: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False))
        return
    if "items" in obj:
        for it in obj["items"]:
            print("%-18s %8d B %6d est  %s" % (it["kind"], it["bytes"], it["est_tokens"], it["path"]))
        print("always_loaded_est_tokens %d (excl self %d), label %s" % (
            obj["always_loaded_est_tokens"], obj["always_loaded_excl_self_est_tokens"], LABEL))
    else:
        for d in obj["deltas"]:
            print("%-18s %+8d B %+6d est  %s" % (d["kind"], d["bytes_delta"], d["est_tokens_delta"], d["path"]))
        print("total_est_tokens_delta %+d" % obj["total_est_tokens_delta"])
        for g, rows in obj["guards"].items():
            print("%s: %d" % (g, len(rows)))
    for w in obj["warnings"]:
        print("warning: " + w)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="context_payload.py", add_help=True)
    sub = ap.add_subparsers(dest="cmd")
    m = sub.add_parser("measure")
    m.add_argument("root")
    m.add_argument("--json", action="store_true")
    m.add_argument("--self", dest="self_md", default=None)
    d = sub.add_parser("diff")
    d.add_argument("before")
    d.add_argument("after")
    d.add_argument("--json", action="store_true")
    d.add_argument("--triggers", default=None)
    d.add_argument("--pinned", default=None)
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:  # argparse already printed; keep exit 2 for usage errors
        return 2 if e.code else 0
    try:
        if args.cmd == "measure":
            if not (Path(args.root) / "CLAUDE.md").is_file():
                raise Usage("ROOT has no CLAUDE.md: %s" % args.root)
            if args.self_md is not None and not Path(args.self_md).is_file():
                raise Usage("--self file not found: %s" % args.self_md)
            meas = Measurement(Path(args.root)).run(args.self_md)
            emit(meas.to_json(), args.json)
            return meas.exit_code
        if args.cmd == "diff":
            for r in (args.before, args.after):
                if not (Path(r) / "CLAUDE.md").is_file():
                    raise Usage("ROOT has no CLAUDE.md: %s" % r)
            for opt, val in (("--triggers", args.triggers), ("--pinned", args.pinned)):
                if val is not None and not Path(val).is_file():
                    raise Usage("%s file not found: %s" % (opt, val))
            before = Measurement(Path(args.before)).run()
            after = Measurement(Path(args.after)).run()
            out, code = diff_trees(before, after, args.triggers, args.pinned)
            emit(out, args.json)
            return code
        raise Usage("command required: measure or diff")
    except Usage as e:
        print("exit 2: %s" % e, file=sys.stderr)
        return 2
    except Escape as e:
        print(str(e), file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
