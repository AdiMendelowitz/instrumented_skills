import argparse
import gzip
import hashlib
import io
import os
import posixpath
import re
import sys
import tempfile

DATA_CARD = (
    "# Data card: token-aware evaluation package\n\n"
    "What this is: the pre-registration, tasks, fixtures, probes, harness and analysis source, and the 1,788 run records "
    "of the token-aware M2 final batch (13 batches run on 2026-11-10 with Claude Code 2.1.303 and claude-sonnet-5-5), "
    "with the analysis output and the results file final.md.\n\n"
    "Files: {files} published files; {changed} changed by redaction; {replacements} replacements in total.\n\n"
    "Records: `s4/s4final-records-2026-11-10.jsonl.gz`, one JSON record per line, 600 track B runs (12 held-out tasks, "
    "arms N, K0, K1, K0f, K1f, 10 runs each) and 18 track A runs (fixture F2, arms AN, AS, ASn, 6 each). "
    "Rerun the analysis with `python analysis.py <folder of *.record.json files> prereg.json --stage final --json out.json`; "
    "split the records into one file per `run_id` first.\n\n"
    "Redaction: the account user name in Windows paths was replaced with `REDACTED_USER` by `publish_eval.py`, in code and "
    "records alike. The pre-registered md5s (harness.py, runlib.py, prereg.json, the record sums) therefore do not verify "
    "against these copies; `REDACTION-PAIRS.tsv` gives, for every changed file, its original md5 and its published md5. "
    "Unchanged files keep their original bytes, listed in `SHA256SUMS`.\n\n"
    "Excluded: raw stream logs, earlier batches, pilot data, build briefs and editor backups.\n\n"
    "Not measured: Cowork behaviour (untested); the live configuration of any user; fixture F1.\n\n"
    "Licence: data under CC BY 4.0 (`LICENSE-DATA.md`); code under the repository's MIT licence.\n"
)
LICENSE_DATA = (
    "# Licence for the evaluation data\n\n"
    "The evaluation data in this folder (run records, analysis output, tasks, fixtures, probes and results text) "
    "is licensed under the Creative Commons Attribution 4.0 International licence (CC BY 4.0): "
    "https://creativecommons.org/licenses/by/4.0/\n\n"
    "Attribution: Adi Mendelowitz, token-aware evaluation package, instrumented_skills.\n\n"
    "Source code in this folder (`*.py` and test configuration) is licensed under the MIT licence in the repository root.\n"
)

PROVENANCE = (
    "# Provenance: evaluated token-aware K1 tree\n\n"
    "This folder is the token-aware skill tree measured as arm K1 in the M2 final batch (tree md5 "
    "93263e8f72992caf8379cada56f01e04, recorded in ../token-aware/final.md line 10), published as measured.\n\n"
    "Files: {files} published files; {changed} changed by redaction; {replacements} replacements in total. "
    "`REDACTION-PAIRS.tsv` gives the original and published md5 of every changed file; `SHA256SUMS` lists every "
    "published file.\n\n"
    "Measured result (../token-aware/final.md, Final batch results): against having no token skill (arm N), this tree "
    "showed no measurable saving in cost per success (ratio 1.008, 95 per cent interval 0.939 to 1.082, 12 held-out "
    "tasks). The forced-load cost was measured on the earlier K0 version, where loading the skill raised cost per "
    "success by about 32 per cent (ratio 1.318). With both versions forced to load, this tree's guidance made no "
    "measurable difference against K0's (K1f against K0f, ratio 1.049, interval 0.970 to 1.134). The evaluation made no comparison of this tree forced "
    "against this tree unforced.\n\n"
    "Licence: code under the repository's MIT licence.\n"
)

GENERATED = ("DATA-CARD.md", "LICENSE-DATA.md", "REDACTION-PAIRS.tsv", "SHA256SUMS")
GENERATED_TREE = ("PROVENANCE.md", "REDACTION-PAIRS.tsv", "SHA256SUMS")

RE_SEP = re.compile(r"(users)(\\\\|\\|/)adime\b", re.IGNORECASE)
RE_STRIPPED = re.compile(r"(users)adime\b", re.IGNORECASE)


class Fail(Exception):
    def __init__(self, code, msg):
        Exception.__init__(self, msg)
        self.code = code
        self.msg = msg


def md5(b):
    return hashlib.md5(b).hexdigest()


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def redact(text, token):
    text, n1 = RE_SEP.subn(lambda m: m.group(1) + m.group(2) + token, text)
    text, n2 = RE_STRIPPED.subn(lambda m: m.group(1) + token, text)
    return text, n1 + n2


def gz_bytes(data):
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, compresslevel=9, mtime=0) as g:
        g.write(data)
    return buf.getvalue()


def read_allowlist(path):
    with open(path, "rb") as f:
        raw = f.read()
    try:
        lines = raw.decode("utf-8-sig").split("\n")
    except UnicodeDecodeError:
        raise Fail(2, "allowlist is not valid UTF-8: " + path)
    seen = set()
    out = []
    for ln in lines:
        ln = ln.strip()
        if ln:
            if ln.startswith("/") or ln.split("/")[0].endswith(":"):
                raise Fail(2, "absolute allowlist path: " + ln)
            ln = posixpath.normpath(ln)
            if ln == ".." or ln.startswith("../"):
                raise Fail(2, "allowlist path leaves SRC: " + ln)
        if not ln or ln in seen:
            continue
        seen.add(ln)
        out.append(ln)
    return out


def write_file(path, data):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def list_files(root):
    res = []
    for dp, dn, fn in os.walk(root):
        for n in fn:
            full = os.path.join(dp, n)
            res.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return res


def run(src, allow, out, token, profile="eval"):
    generated = GENERATED_TREE if profile == "tree" else GENERATED
    paths = read_allowlist(allow)
    missing = []
    for p in paths:
        parts = p.split("/")
        if p.startswith("/") or ".." in parts or not os.path.isfile(os.path.join(src, *parts)):
            missing.append(p)
    if missing:
        raise Fail(2, "missing allowlist paths:\n" + "\n".join(missing))

    def outrel(p):
        if profile == "tree":
            return p
        return p + ".gz" if p.endswith(".jsonl") else p

    expected = set(outrel(p) for p in paths) | set(generated)
    for g in generated:
        if os.path.isdir(os.path.join(out, g)):
            raise Fail(2, "OUT holds a directory named like a generated file: " + g)
    if os.path.isdir(out):
        unexpected = sorted(r for r in list_files(out) if r not in expected)
        if unexpected:
            raise Fail(3, "unexpected files in OUT:\n" + "\n".join(unexpected))
    os.makedirs(out, exist_ok=True)

    rows = []
    total_repl = 0
    changed = 0
    for p in paths:
        with open(os.path.join(src, *p.split("/")), "rb") as f:
            raw = f.read()
        data = raw
        n = 0
        is_text = False
        if b"\x00" not in raw:
            try:
                text = raw.decode("utf-8")
                is_text = True
            except UnicodeDecodeError:
                is_text = False
        if not is_text and re.search(rb"(?i)users(\\\\|\\|/)?adime", raw):
            raise Fail(4, "binary file holds the user name, cannot redact safely: " + p)
        if is_text:
            text2, n = redact(text, token)
            if n:
                data = text2.encode("utf-8")
        rel = outrel(p)
        written = gz_bytes(data) if (p.endswith(".jsonl") and profile != "tree") else data
        write_file(os.path.join(out, *rel.split("/")), written)
        if data != raw:
            changed += 1
            total_repl += n
            rows.append("\t".join([p, md5(raw), md5(data), rel, md5(written), str(n)]))

    header = "path\toriginal_md5\tpublished_md5\tpublished_file\tpublished_file_md5\treplacements"
    write_file(os.path.join(out, "REDACTION-PAIRS.tsv"), ("\n".join([header] + rows) + "\n").encode("utf-8"))
    if profile == "tree":
        prov = PROVENANCE.format(files=len(paths), changed=changed, replacements=total_repl)
        write_file(os.path.join(out, "PROVENANCE.md"), prov.encode("utf-8"))
    else:
        card = DATA_CARD.format(files=len(paths), changed=changed, replacements=total_repl)
        write_file(os.path.join(out, "DATA-CARD.md"), card.encode("utf-8"))
        write_file(os.path.join(out, "LICENSE-DATA.md"), LICENSE_DATA.encode("utf-8"))

    rels = sorted((r for r in list_files(out) if r != "SHA256SUMS"), key=lambda r: r.encode("utf-8"))
    lines = []
    for r in rels:
        with open(os.path.join(out, *r.split("/")), "rb") as f:
            lines.append("%s  %s\n" % (sha256(f.read()), r))
    sums = "".join(lines).encode("utf-8")
    write_file(os.path.join(out, "SHA256SUMS"), sums)
    return {"files": len(paths), "changed": changed, "replacements": total_repl, "sums": sha256(sums)}


def selftest():
    count = [0]

    def check(cond, msg):
        count[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src")
        os.makedirs(os.path.join(src, "h"))
        os.makedirs(os.path.join(src, "s4"))
        lines_in = [
            'C:\\\\Users\\\\adime\\\\venvs',
            'C:\\Users\\adime\\x',
            'C:/Users/adime/x',
            'c:\\\\users\\\\ADIME\\\\venvs',
            'Usersadime',
            'adimendelowitz@gmail.com',
            'Users/adimex',
        ]
        lines_exp = [
            'C:\\\\Users\\\\TKN\\\\venvs',
            'C:\\Users\\TKN\\x',
            'C:/Users/TKN/x',
            'c:\\\\users\\\\TKN\\\\venvs',
            'UsersTKN',
            'adimendelowitz@gmail.com',
            'Users/adimex',
        ]
        tok = "TKN"
        txt = "\n".join(lines_in) + "\n"
        with open(os.path.join(src, "h", "a.py"), "wb") as f:
            f.write(txt.encode("utf-8"))
        with open(os.path.join(src, "s4", "r.jsonl"), "wb") as f:
            f.write((lines_in[0] + "\n" + lines_in[5] + "\n").encode("utf-8"))
        binb = b"\x00\x01binary\x00"
        with open(os.path.join(src, "h", "b.bin"), "wb") as f:
            f.write(binb)
        with open(os.path.join(src, "h", "clean.txt"), "wb") as f:
            f.write(b"nothing here\n")
        allow = os.path.join(tmp, "allow.txt")
        with open(allow, "wb") as f:
            f.write(b"h/a.py\nh/b.bin\n\nh/clean.txt\ns4/r.jsonl\n")

        o1 = os.path.join(tmp, "o1")
        o2 = os.path.join(tmp, "o2")
        r1 = run(src, allow, o1, tok)
        r2 = run(src, allow, o2, tok)

        def rd(root, rel):
            with open(os.path.join(root, *rel.split("/")), "rb") as f:
                return f.read()

        got = rd(o1, "h/a.py").decode("utf-8").split("\n")
        for i, (g, e) in enumerate(zip(got, lines_exp)):
            check(g == e, "line %d redaction" % i)
        check(r1["replacements"] == 5 + 1, "replacement count")
        check(r1["files"] == 4 and r1["changed"] == 2, "files/changed counts")
        check(rd(o1, "h/b.bin") == binb, "binary unchanged")
        check(rd(o1, "h/clean.txt") == b"nothing here\n", "clean text unchanged")
        check(not os.path.exists(os.path.join(o1, "s4", "r.jsonl")), "jsonl not written plain")
        gz = rd(o1, "s4/r.jsonl.gz")
        check(gzip.decompress(gz).decode("utf-8") == lines_exp[0] + "\n" + lines_exp[5] + "\n", "gz decompresses to redacted text")
        check(rd(o1, "SHA256SUMS") == rd(o2, "SHA256SUMS"), "SHA256SUMS identical across OUT dirs")
        check(r1["sums"] == r2["sums"], "summary hash identical")
        before = dict((r, rd(o1, r)) for r in list_files(o1))
        run(src, allow, o1, tok)
        after = dict((r, rd(o1, r)) for r in list_files(o1))
        check(before == after, "second run same OUT byte-identical")
        check(sorted(before) == sorted(after) and "REDACTION-PAIRS.tsv" in before, "file sets equal")
        tsv = rd(o1, "REDACTION-PAIRS.tsv").decode("utf-8").split("\n")
        check(len(tsv) == 4 and tsv[3] == "", "tsv has header plus two rows")
        check(tsv[2].split("\t")[3] == "s4/r.jsonl.gz" and tsv[2].split("\t")[4] == md5(gz), "tsv gz row")
        check(b"6 replacements in total" in rd(o1, "DATA-CARD.md"), "data card line")
        sums_lines = rd(o1, "SHA256SUMS").decode("utf-8").splitlines()
        check("SHA256SUMS" not in "".join(x.split("  ", 1)[1] for x in sums_lines), "sums excludes itself")
        check([x.split("  ", 1)[1] for x in sums_lines] == sorted(x.split("  ", 1)[1] for x in sums_lines), "sums sorted")

        with open(os.path.join(o1, "stray.txt"), "wb") as f:
            f.write(b"x")
        try:
            run(src, allow, o1, tok)
            check(False, "guard should exit 3")
        except Fail as e:
            check(e.code == 3, "unexpected-file guard exits 3")
        os.remove(os.path.join(o1, "stray.txt"))

        allow2 = os.path.join(tmp, "allow2.txt")
        with open(allow2, "wb") as f:
            f.write(b"h/a.py\nh/nope.py\n")
        try:
            run(src, allow2, os.path.join(tmp, "o3"), tok)
            check(False, "missing should exit 2")
        except Fail as e:
            check(e.code == 2 and "h/nope.py" in e.msg, "missing allowlist path exits 2")
        regression_tests(run, check)
    print("SELFTEST OK %d assertions" % count[0])
    return 0


def _reg_setup(tmp):
    src = os.path.join(tmp, "src")
    os.makedirs(os.path.join(src, "h"))
    with open(os.path.join(src, "h", "a.py"), "wb") as f:
        f.write(b"C:\\Users\\adime\\x\n")
    with open(os.path.join(src, "h", "r.jsonl"), "wb") as f:
        f.write(b"{}\n")
    allow = os.path.join(tmp, "allow.txt")
    with open(allow, "wb") as f:
        f.write(b"h/a.py\nh/r.jsonl\n")
    return src, allow


def _snapshot(root):
    res = []
    for dp, dn, fn in os.walk(root):
        for n in dn + fn:
            full = os.path.join(dp, n)
            res.append((os.path.relpath(full, root), os.path.isdir(full)))
    return sorted(res)


def test_preflight_dir_collision(runfn, check):
    with tempfile.TemporaryDirectory() as tmp:
        src, allow = _reg_setup(tmp)
        for prof, names in (("eval", GENERATED), ("tree", GENERATED_TREE)):
            for g in names:
                out = os.path.join(tmp, "pre-" + prof + "-" + g)
                os.makedirs(os.path.join(out, g))
                before = _snapshot(out)
                try:
                    runfn(src, allow, out, "TKN", prof) if prof == "tree" else runfn(src, allow, out, "TKN")
                    check(False, "dir named %s should fail" % g)
                except Fail as e:
                    check(e.code == 2 and g in e.msg, "dir collision on %s exits 2 (%s)" % (g, prof))
                except Exception:
                    check(False, "dir collision on %s raised a raw error (%s)" % (g, prof))
                check(_snapshot(out) == before, "OUT unchanged after collision on %s (%s)" % (g, prof))
        out = os.path.join(tmp, "pre-nonempty")
        os.makedirs(os.path.join(out, "DATA-CARD.md"))
        with open(os.path.join(out, "DATA-CARD.md", "x.txt"), "wb") as f:
            f.write(b"x")
        before = _snapshot(out)
        try:
            runfn(src, allow, out, "TKN")
            check(False, "non-empty generated-name dir should fail")
        except Fail as e:
            check(e.code == 2 and "DATA-CARD.md" in e.msg, "non-empty generated-name dir exits 2")
        except Exception:
            check(False, "non-empty generated-name dir raised a raw error")
        check(_snapshot(out) == before, "OUT unchanged for non-empty generated-name dir")


def test_allowlist_not_utf8(script, check):
    import subprocess
    with tempfile.TemporaryDirectory() as tmp:
        src, allow = _reg_setup(tmp)
        bad = os.path.join(tmp, "bad-allow.txt")
        with open(bad, "wb") as f:
            f.write(b"h/a.py\n\xff\xfe\n")
        proc = subprocess.run([sys.executable, script, "--src", src, "--allowlist", bad,
                               "--out", os.path.join(tmp, "o-bad")], capture_output=True)
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        check(proc.returncode == 2, "non-UTF-8 allowlist exits 2 (got %d)" % proc.returncode)
        check("bad-allow.txt" in err and "\n" not in err, "non-UTF-8 message is one line naming the file")
        bom = os.path.join(tmp, "bom-allow.txt")
        with open(bom, "wb") as f:
            f.write(b"\xef\xbb\xbfh/a.py\nh/r.jsonl\n")
        try:
            check(read_allowlist(bom) == ["h/a.py", "h/r.jsonl"], "BOM allow-list read without BOM")
        except Fail:
            check(False, "BOM allow-list should not fail")


def test_tree_profile(runfn, check):
    with tempfile.TemporaryDirectory() as tmp:
        src, allow = _reg_setup(tmp)
        o = os.path.join(tmp, "o-tree")
        try:
            runfn(src, allow, o, "TKN", "tree")
        except Exception:
            check(False, "tree profile run raised")
        got = sorted(list_files(o))
        check(got == ["PROVENANCE.md", "REDACTION-PAIRS.tsv", "SHA256SUMS", "h/a.py", "h/r.jsonl"], "tree profile file set")
        with open(os.path.join(o, "h", "r.jsonl"), "rb") as f:
            check(f.read() == b"{}\n", "tree profile does not gzip")
        with open(os.path.join(o, "PROVENANCE.md"), "rb") as f:
            prov = f.read().decode("utf-8")
        check(prov == PROVENANCE.format(files=2, changed=1, replacements=1), "PROVENANCE text")
        check(prov.startswith("# Provenance: evaluated token-aware K1 tree\n\n") and "2 published files; 1 changed" in prov, "PROVENANCE filled")
        with open(os.path.join(o, "SHA256SUMS"), "rb") as f:
            names = [x.split("  ", 1)[1] for x in f.read().decode("utf-8").splitlines()]
        check(names == ["PROVENANCE.md", "REDACTION-PAIRS.tsv", "h/a.py", "h/r.jsonl"], "tree SHA256SUMS lists generated files")
        with open(os.path.join(o, "h", "a.py"), "rb") as f:
            check(b"TKN" in f.read(), "tree redacts text")


def regression_tests(runfn, check):
    test_preflight_dir_collision(runfn, check)
    test_allowlist_not_utf8(os.path.abspath(__file__), check)
    test_tree_profile(runfn, check)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--allowlist")
    ap.add_argument("--out")
    ap.add_argument("--token", default="REDACTED_USER")
    ap.add_argument("--profile", choices=("eval", "tree"), default="eval")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.src and a.allowlist and a.out):
        ap.error("--src, --allowlist and --out are required")
    try:
        r = run(a.src, a.allowlist, a.out, a.token, a.profile)
    except Fail as e:
        print(e.msg, file=sys.stderr)
        return e.code
    print("files=%d changed=%d replacements=%d sha256sums=%s" % (r["files"], r["changed"], r["replacements"], r["sums"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
