# kb-search

**Ranked search over your logs and notes for the questions no single grep term can answer.**

`kb-search` ranks chunks of a markdown, text or JSONL corpus with BM25. It is the read path
for the records the other skills write (critique logs, retro journals, handoff snapshots
and reference documents), so a run can ask whether a root cause found today has fired on any
other file, whether a long-horizon action from six weeks ago was carried out, or what a past
session already settled. It has no agent loop, makes no model call and uses the Python
standard library only.

| | |
|---|---|
| Protocol | v1.1 |
| Run it with | `/kb-search`, or `python tools/search.py` from another skill |
| Method | BM25 ranking with a JSON index cache, which loads without running any code |
| Tests | 69, run with `python -m pytest -q` in `tools/` |
| Depends on | nothing outside its own folder |

## Quick start

```bash
cp -r kb-search ~/.claude/skills/          # or ./install.sh kb-search from the repo root
python ~/.claude/skills/kb-search/tools/search.py --root .claude --domain retro-log --query "lock timeout nightly job"
```

`--root` holds your corpora and `--domain` names the subdirectory to search, so the corpus
indexed is `<root>/<domain>`. Both are explicit because the skill never guesses which
project is active, and corpora live in different places (a retro journal under a project's
own `.claude/`, a handoff archive under `~/.claude/`). The second command, run from a
project root, searches that project's retro journals and returns ranked chunks as JSON. The
index builds on the first search and is cached beside the corpus.

## Search policy

> [!WARNING]
> kb-search defers one decision to `references/search_policy.md`, which is when to reach
> for it at all. That file is the gating rule (grep first, and escalate to kb-search only
> when grep is insufficient). Without it the skill gets reached for reflexively, which is
> the failure it is most exposed to, so keep the file in the folder when you copy or adapt
> the skill.

## What the tools do

`tools/index.py` holds the core (chunking, tokenisation, a Lucene-style BM25 and the JSON
index cache) and a build command you rarely need, since search builds the index lazily.
`tools/search.py` queries a corpus and returns ranked chunks as JSON. It always exits 0 and
reports its state in a `status` field, because a missing corpus is a normal condition for
the caller to handle.

## Adapting this skill

### Point it at a real corpus

Any append-only directory of markdown, text or JSONL files works. The four properties in
`SKILL.md` § Corpus contract (plain text on disk, one file per event with the date in the
filename, a stable location named by the owning skill, and append-only in practice) are what
make a corpus rank well and age well.

### One domain per corpus

Give each corpus its own subdirectory so the indexes stay separate. There is deliberately
no search across corpora, because a critique finding and a retro line ranked on one scale
produce a meaningless number.

### Tuning

`BM25_K1`, `BM25_B` and the `NOISE_DIRS` exclusion set sit near the top of
`tools/index.py`, and the top-k cap and default excerpt length are constants in
`tools/search.py`. Change the excluded directories if your corpus keeps machinery files
somewhere unusual, and keep the exclusion itself, since short, keyword-dense machinery files
otherwise outrank real content.

## Files

```
SKILL.md                      the protocol, output contract and design notes
references/search_policy.md   when to grep and when to escalate to kb-search
tools/index.py                core (chunking, tokenisation, BM25, JSON cache) and build command
tools/search.py               query entry point (always exits 0, status in JSON)
tools/test_index.py           tests for the core and the build command
tools/test_search.py          tests for ranking and the four degradation states
```
