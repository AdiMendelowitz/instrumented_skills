#!/usr/bin/env python3
"""Prove a release tree differs from the evaluated tree only in four permitted ways.

Rule 4 (README.md): with --public-readme FILE the release README.md must be the bytes of FILE followed by one
'## Evaluation' section and no other level-1 or level-2 heading; a command-line run requires that argument.
Known limits of the heading check, accepted after two reviews (2026-11-15): it is a line scan, not a Markdown
parser. It guards against an accidental extra section, not a crafted one: a setext heading inside a quote, nested
list-and-quote markers, an indented code fence, an <h1> tag split across lines and bare-CR line endings pass.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

# Importing cost.py from the release tree must not write __pycache__ into it.
sys.dont_write_bytecode = True
import tempfile
from datetime import date
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
HEADER_RE = re.compile(r"^# .+ \| v(\d+\.\d+\.\d+) \| (\d{4}-\d{2}-\d{2})$")
TOKEN = "REDACTED_USER"


def load_redact():
    path = os.path.join(HERE, "publish_eval.py")
    spec = importlib.util.spec_from_file_location("_diff_scope_publish_eval", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.redact


def walk(root):
    """Return (files, empty_dirs, symlinks); symlinks are never followed."""
    files, empties, links = {}, set(), []
    for dp, dn, fn in os.walk(root, followlinks=False):
        dn.sort()
        rd = os.path.relpath(dp, root).replace(os.sep, "/")
        for d in list(dn):
            full = os.path.join(dp, d)
            if os.path.islink(full):
                links.append(posix_join(rd, d))
                dn.remove(d)
        for f in sorted(fn):
            full = os.path.join(dp, f)
            if os.path.islink(full):
                links.append(posix_join(rd, f))
            elif os.path.isfile(full):
                files[posix_join(rd, f)] = full
        if rd != "." and not dn and not fn:
            empties.add(rd)
    return dict(sorted(files.items())), empties, sorted(links)


def posix_join(rd, name):
    return name if rd == "." else rd + "/" + name


def read(p):
    with open(p, "rb") as f:
        return f.read()


def check_skill(ev, rel, version, redact):
    a, b = ev.split(b"\n"), rel.split(b"\n")
    if len(a) != len(b):
        return "line count differs (%d vs %d)" % (len(a), len(b))
    other = []
    for i in range(len(a)):
        if a[i] == b[i]:
            continue
        try:
            la, lb = a[i].decode("utf-8"), b[i].decode("utf-8")
        except UnicodeDecodeError:
            return "line %d differs and is not UTF-8" % (i + 1)
        if redact(la, TOKEN)[0] == lb:
            continue
        other.append((i, la, lb))
    if not other:
        return None
    if len(other) != 1:
        return "%d non-redaction lines differ, exactly one header line may differ" % len(other)
    i, la, lb = other[0]
    ma, mb = HEADER_RE.match(la), HEADER_RE.match(lb)
    if not ma:
        return "evaluated line %d is not a header line" % (i + 1)
    if not mb:
        return "release line %d is not a header line" % (i + 1)
    try:
        date.fromisoformat(mb.group(2))
    except ValueError:
        return "release header date %s is not a valid date" % mb.group(2)
    if mb.group(1) != version:
        return "release header version %s, expected %s" % (mb.group(1), version)
    return None


def check_redaction(ev, rel, redact):
    try:
        ta, tb = ev.decode("utf-8"), rel.decode("utf-8")
    except UnicodeDecodeError:
        return "binary file differs"
    a, b = ta.split("\n"), tb.split("\n")
    if len(a) != len(b):
        return "line count differs (%d vs %d)" % (len(a), len(b))
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y and redact(x, TOKEN)[0] != y:
            return "line %d differs and is not a user-path redaction" % (i + 1)
    return None


def check_rates(ev, rel, release_root):
    try:
        data = json.loads(rel.decode("utf-8"))
        old = json.loads(ev.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        return "rates.json does not parse: %s" % e
    if not isinstance(data, dict) or not isinstance(old, dict):
        return "rates.json is not an object"
    ph = data.get("placeholder")
    if not isinstance(ph, str) or not ph:
        return "missing or empty placeholder"
    if set(data) != set(old) | {"placeholder"}:
        return "top-level keys differ from evaluated plus placeholder"
    try:
        exp = date.fromisoformat(str(data.get("expires")))
    except ValueError:
        return "expires missing or not a date"
    if exp > date(2000, 12, 31):
        return "expires %s is later than 2000-12-31" % exp.isoformat()
    mo, mr = old.get("models"), data.get("models")
    if not isinstance(mr, dict) or not isinstance(mo, dict):
        return "models missing"
    if set(mo) != set(mr):
        return "model ids differ from evaluated"
    for k, v in mr.items():
        if not isinstance(v, dict) or not isinstance(mo[k], dict):
            return "model %s is not an object" % k
        if v.get("in") is not None or v.get("out") is not None:
            return "model %s has a non-null in/out" % k
        strip = lambda d: {x: y for x, y in d.items() if x not in ("in", "out")}
        if strip(v) != strip(mo[k]):
            return "model %s differs from evaluated beyond in/out" % k
    return check_cost_expired(release_root)


def check_cost_expired(release_root):
    cost = os.path.join(release_root, "tools", "cost.py")
    rates = Path(release_root, "tools", "rates.json")
    if not os.path.isfile(cost):
        return "tools/cost.py missing from release"
    saved_path = list(sys.path)
    saved_mods = set(sys.modules)
    name = "_diff_scope_release_cost"
    try:
        spec = importlib.util.spec_from_file_location(name, cost)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        try:
            mod.load_rates(rates)
        except Exception as e:
            if type(e).__name__ == "RatesExpired" and str(e).startswith("rates.json expired"):
                return None
            return "load_rates raised %s(%s), expected RatesExpired starting 'rates.json expired'" % (
                type(e).__name__, e)
        return "load_rates accepted the release rates.json (no expiry error)"
    except Exception as e:
        return "could not import or run release tools/cost.py: %s" % e
    finally:
        sys.path[:] = saved_path
        for m in set(sys.modules) - saved_mods:
            del sys.modules[m]
        sys.modules.pop(name, None)


ATX_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*#*[ \t]*$")
SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")


def headings(text):
    """List of (line_index, level, title): ATX (up to 3 leading spaces) and setext."""
    lines = text.split("\n")
    out = []
    for i, l in enumerate(lines):
        m = ATX_RE.match(l)
        if m:
            out.append((i, len(m.group(1)), (m.group(2) or "").strip()))
            continue
        if (l.strip() and i + 1 < len(lines) and not l.startswith("    ")):
            u = SETEXT_RE.match(lines[i + 1])
            if u and len(u.group(1)) >= 3:
                out.append((i, 1 if u.group(1)[0] == "=" else 2, l.strip()))
    return out


STRICT_ATX_RE = re.compile(r"^[\s>*+\-]*(?:\d+[.)]\s+)?#{1,2}(?:\s|$)")
STRICT_UNDERLINE_RE = re.compile(r"^\s*(?:=+|-+)\s*$")
STRICT_HTML_RE = re.compile(r"<h[12][\s>]", re.IGNORECASE)


def strict_heading(lines):
    """First line of an appended part (after its own first line) that could render as a level-1/2 heading.

    Stricter than headings(): also catches a heading inside a quote or list item, a setext underline of any
    length under any non-blank line (indented or not), and raw <h1>/<h2>. Fenced code is skipped.
    """
    fence = None
    for i, l in enumerate(lines):
        t = l.strip()
        if fence is None and (t.startswith("```") or t.startswith("~~~")):
            fence = t[:3]
            continue
        if fence is not None:
            if t.startswith(fence):
                fence = None
            continue
        if i == 0:
            continue
        if STRICT_ATX_RE.match(l) or STRICT_HTML_RE.search(l):
            return l
        if STRICT_UNDERLINE_RE.match(l) and lines[i - 1].strip():
            return lines[i - 1]
    return None


def check_readme(ev, rel):
    if ev is None:
        try:
            text = rel.decode("utf-8")
        except UnicodeDecodeError:
            return "README.md is not UTF-8"
        hs = headings(text)
        if (len(hs) != 2 or hs[0][1] != 1 or hs[1][1] != 2 or hs[1][2] != "Evaluation"):
            return "headings must be one level-1 then '## Evaluation', got %r" % [(h[1], h[2]) for h in hs]
        return None
    if not rel.startswith(ev):
        return "release README.md does not start with the evaluated bytes"
    tail = rel[len(ev):]
    if not (ev.endswith(b"\n") or tail.startswith(b"\n")):
        return "appended part does not start on a new line"
    body = tail.lstrip(b"\n")
    if not body.startswith(b"## Evaluation\n"):
        return "appended part does not start with '## Evaluation'"
    try:
        hs = headings(body.decode("utf-8"))
    except UnicodeDecodeError:
        return "appended part is not UTF-8"
    for i, lvl, title in hs[1:]:
        if lvl <= 2:
            return "appended part has another level-1/2 heading: %r" % title
    bad = strict_heading(body.decode("utf-8").replace("\r\n", "\n").split("\n"))
    if bad is not None:
        return "appended part has a line that can render as a level-1/2 heading: %r" % bad.strip()[:60]
    return None


def compare(evaluated, release, version="2.6.0", redact=None, public_readme=None):
    redact = redact or load_redact()
    fe, ee, le = walk(evaluated)
    fr, er, lr = walk(release)
    viol = []
    for p in le:
        viol.append((p, "symlink not allowed (evaluated tree)"))
    for p in lr:
        viol.append((p, "symlink not allowed (release tree)"))
    for p in sorted(ee ^ er):
        viol.append((p, "empty directory present in %s tree only" % ("evaluated" if p in ee else "release")))
    allp = sorted(set(fe) | set(fr))
    if public_readme is not None and "README.md" not in fr:
        viol.append(("README.md", "release tree has no README.md to check against the public README"))
    for p in allp:
        if p == "README.md" and public_readme is not None:
            if p in fe:
                viol.append((p, "evaluated tree holds a README.md; the public-prefix rule expects none"))
            elif p in fr:
                r = check_readme(public_readme, read(fr[p]))
                if r:
                    viol.append((p, r.replace("evaluated bytes", "public README bytes")))
            continue
        if p == "README.md" and p not in fe:
            r = check_readme(None, read(fr[p]))
            if r:
                viol.append((p, r))
            continue
        if p not in fe:
            viol.append((p, "added in release"))
            continue
        if p not in fr:
            viol.append((p, "removed from release"))
            continue
        a, b = read(fe[p]), read(fr[p])
        if a == b:
            continue
        if p == "SKILL.md":
            r = check_skill(a, b, version, redact)
        elif p == "tools/rates.json":
            r = check_rates(a, b, release)
        elif p == "README.md":
            r = check_readme(a, b)
        else:
            r = check_redaction(a, b, redact)
        if r:
            viol.append((p, r))
    for need in ("tools/rates.json",):
        if need not in fe or need not in fr:
            if not any(v[0] == need for v in viol):
                viol.append((need, "must exist in both trees"))
    return len(allp), viol


def report(n, viol):
    if not viol:
        print("DIFF-SCOPE PASS %d files compared" % n)
        return 0
    for p, r in viol:
        print("OUT-OF-SCOPE %s: %s" % (p, r))
    print("DIFF-SCOPE FAIL %d violations" % len(viol))
    return 1


def selftest():
    redact = load_redact()
    count = [0]

    def ok(cond, msg):
        count[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            sys.exit(1)

    skill = (b"---\nname: x\n---\n# Demo | v2.5.0 | 2026-11-01\nbody one\nbody two\n"
             b"home C:\\Users\\adime\\y\n")
    cost = (b"class RatesExpired(ValueError):\n    pass\n\n\n"
            b"def load_rates(path=None, today=None):\n"
            b"    import json, datetime\n"
            b"    d = json.loads(open(path, encoding='utf-8').read())\n"
            b"    if datetime.date.today() > datetime.date.fromisoformat(d['expires']):\n"
            b"        raise RatesExpired('rates.json expired ' + d['expires'])\n"
            b"    return d\n")
    ev_data = {"expires": "2026-12-09", "source": "s",
               "models": {"m1": {"in": 1.0, "out": 2.0, "cache_read_mult": 0.1},
                          "m2": {"in": 3.0, "out": 4.0, "cache_read_mult": 0.2}}}
    rel_data = {"placeholder": "prices withheld", "expires": "2000-01-01", "source": "s",
                "models": {"m1": {"in": None, "out": None, "cache_read_mult": 0.1},
                           "m2": {"in": None, "out": None, "cache_read_mult": 0.2}}}
    rates = json.dumps(ev_data, indent=1).encode()
    rel_rates = json.dumps(rel_data, indent=1).encode()
    base = {"SKILL.md": skill, "tools/cost.py": cost, "tools/rates.json": rates,
            "notes.txt": b"path C:\\Users\\adime\\x here\nsecond line\n"}

    def build(root, files):
        for rel, data in files.items():
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(data)

    def run(mod, expect_pass, label, version="2.6.0", ev_files=None, post=None, public=None):
        with tempfile.TemporaryDirectory() as t:
            e, r = os.path.join(t, "e"), os.path.join(t, "r")
            os.makedirs(e)
            os.makedirs(r)
            build(e, ev_files or base)
            rf = dict(ev_files or base)
            mod(rf)
            build(r, rf)
            if post:
                post(e, r)
            n, v = compare(e, r, version, redact, public_readme=public)
            ok(bool(not v) == expect_pass, "%s: expected %s, violations %r" % (
                label, "PASS" if expect_pass else "FAIL", v))

    def hdr(f):
        f["SKILL.md"] = f["SKILL.md"].replace(b"v2.5.0 | 2026-11-01", b"v2.6.0 | 2026-11-11")

    def red(f):
        f["notes.txt"] = b"path C:\\Users\\REDACTED_USER\\x here\nsecond line\n"

    def rat(f):
        f["tools/rates.json"] = rel_rates

    def rdm(f):
        f["README.md"] = b"# Title\n\ntext\n\n## Evaluation\n\nmore\n"

    def rates_with(fn):
        def mod(f):
            d = json.loads(rel_rates)
            fn(d)
            f["tools/rates.json"] = json.dumps(d).encode()
        return mod

    run(lambda f: None, True, "identical")
    run(hdr, True, "header only")
    run(red, True, "redaction only")
    run(rat, True, "rates only")
    run(rdm, True, "readme only")

    def allf(f):
        hdr(f); red(f); rat(f); rdm(f)
    run(allf, True, "all four")

    ev2 = dict(base)
    ev2["README.md"] = b"# T\n\nintro\n"
    run(lambda f: f.update({"README.md": b"# T\n\nintro\n\n## Evaluation\n\nx\n"}), True, "readme appended", ev_files=ev2)
    run(lambda f: f.update({"README.md": b"# T\n\nintro\n\n## Evaluation\n\n## Other\n"}), False, "readme appended extra h2", ev_files=ev2)

    run(lambda f: f.update({"extra.txt": b"x\n"}), False, "extra file")
    run(lambda f: f.pop("notes.txt"), False, "removed file")
    run(lambda f: f.update({"SKILL.md": skill.replace(b"body one", b"body ONE")}), False, "SKILL body change")
    run(lambda f: f.update({"SKILL.md": skill.replace(b"v2.5.0", b"v2.7.0")}), False, "wrong header version")
    run(lambda f: f.update({"notes.txt": b"path C:\\Users\\adime\\x here\nsecond LINE\n"}), False, "non-path line change")
    run(rates_with(lambda d: d["models"]["m1"].update({"in": 1.0})), False, "non-null price")
    run(rates_with(lambda d: d.pop("placeholder")), False, "no placeholder")
    run(rates_with(lambda d: d.update({"expires": "2099-01-01"})), False, "not expired")

    def other(f):
        f["README.md"] = b"# Title\n\n## Evaluation\n\n## Other\n"
    run(other, False, "README extra heading")
    run(lambda f: f.update({"__pycache__/x.pyc": b"\x00\x01"}), False, "pycache added")

    # Reviewer fixes, one assertion each.
    def link_file(e, r):
        os.symlink("notes.txt", os.path.join(r, "link.txt"))
    run(lambda f: None, False, "fix1 file symlink", post=link_file)

    def link_dir(e, r):
        os.symlink("real", os.path.join(r, "ln"))
    ev3 = dict(base)
    ev3["real/a"] = b"a"
    run(lambda f: None, False, "fix1 dir symlink", ev_files=ev3, post=link_dir)

    def empty_dir(e, r):
        os.makedirs(os.path.join(r, "emptydir"))
    run(lambda f: None, False, "fix2 empty dir in release only", post=empty_dir)

    run(lambda f: f.update({"README.md": b"# Title\n\nOther\n=====\n\n## Evaluation\n"}), False, "fix3 setext heading")
    run(lambda f: f.update({"README.md": b"# Title\n\n   ## Other\n\n## Evaluation\n"}), False, "fix3 indented heading")

    def wrong_class(f):
        f["tools/cost.py"] = cost.replace(b"class RatesExpired", b"class Boom").replace(b"raise RatesExpired", b"raise Boom")
        rat(f)
    run(wrong_class, False, "fix4 wrong exception class")

    def red_skill(f):
        hdr(f)
        f["SKILL.md"] = f["SKILL.md"].replace(b"C:\\Users\\adime\\y", b"C:\\Users\\REDACTED_USER\\y")
    run(red_skill, True, "fix5 SKILL header plus redaction")

    run(rates_with(lambda d: d["models"]["m1"].update({"batch_in": None})), False, "fix6 added model key")
    run(rates_with(lambda d: d["models"]["m2"].update({"cache_read_mult": 0.9})), False, "fix6 changed model field")
    run(rates_with(lambda d: d.update({"extra_top": 1})), False, "fix6 extra top-level key")

    run(lambda f: f.update({"SKILL.md": skill.replace(b"v2.5.0 | 2026-11-01", b"v2.6.0 | 2026-13-45")}), False, "fix7 invalid header date")

    # Public-prefix rule (S5d): release README = public README bytes + one '## Evaluation' section.
    pub = b"# T\n\nintro\n\n## Install\n\nsteps\n"
    good = pub + b"\n## Evaluation\n\nx\n"
    run(lambda f: f.update({"README.md": good}), True, "public prefix", public=pub)
    run(lambda f: f.update({"README.md": good + b"\n### Detail\n\ny\n"}), True, "public prefix with level-3 heading", public=pub)
    run(lambda f: f.update({"README.md": good.replace(b"intro", b"Intro")}), False, "public prefix altered", public=pub)
    run(lambda f: f.update({"README.md": pub}), False, "public prefix without Evaluation", public=pub)
    run(lambda f: f.update({"README.md": good + b"\n## Other\n"}), False, "public prefix extra h2", public=pub)
    run(lambda f: f.update({"README.md": b"# T\n\n## Evaluation\n\nx\n"}), False, "old two-heading README refused under public rule", public=pub)
    run(lambda f: None, False, "public rule with no release README", public=pub)
    for label, extra in (("one-char setext =", b"\nOther\n=\n"), ("two-char setext -", b"\nOther\n--\n"),
                         ("indented setext", b"\nFoo\n    Bar\n===\n"), ("quoted heading", b"\n> ## Other\n"),
                         ("list heading", b"\n- ## Other\n"), ("html h2", b"\n<h2>Other</h2>\n"),
                         ("html h1 upper", b"\n<H1 id='x'>Other</H1>\n"), ("crlf heading", b"\r\n## Other\r\n")):
        run(lambda f, extra=extra: f.update({"README.md": good + extra}), False, "public strict " + label, public=pub)
    run(lambda f: f.update({"README.md": good + b"\n```\ncode\n```\n\n---\n\ntext\n"}), True,
        "public strict allows a code fence and a rule after a blank line", public=pub)
    ev4 = dict(base)
    ev4["README.md"] = pub
    run(lambda f: f.update({"README.md": good}), False, "public rule with README in evaluated tree", ev_files=ev4, public=pub)

    print("SELFTEST OK %d assertions" % count[0])
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="diff_scope_test.py")
    ap.add_argument("--evaluated")
    ap.add_argument("--release")
    ap.add_argument("--version", default="2.6.0")
    ap.add_argument("--public-readme")
    ap.add_argument("--selftest", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if args.selftest:
        return selftest()
    if not args.evaluated or not args.release or not args.public_readme:
        print("usage: diff_scope_test.py --evaluated DIR --release DIR --public-readme FILE [--version X.Y.Z] | --selftest",
              file=sys.stderr)
        return 2
    if not os.path.isfile(args.public_readme):
        print("not a file: %s" % args.public_readme, file=sys.stderr)
        return 2
    for d in (args.evaluated, args.release):
        if not os.path.isdir(d):
            print("not a directory: %s" % d, file=sys.stderr)
            return 2
    n, viol = compare(args.evaluated, args.release, args.version, public_readme=read(args.public_readme))
    return report(n, viol)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
