# kb-search

**grep answers when one term anchors the query. This answers when none does.**

Ranked lexical search (BM25) over a corpus of markdown, text, or JSONL files. It is the
read-path for the durable artifacts the other skills write: critique logs, retro journals,
handoff snapshots, reference documents. It has no agent loop, makes no LLM call, and
depends on nothing outside the standard library.

| | |
|---|---|
| **Method** | BM25 ranking, JSON index cache (never pickle) |
| **Tests** | 69 pass (49 core/index, 20 ranking/search) |
| **Depends on** | `token-aware/references/search_policy.md` (hard dependency, see below) |
| **Ships** | complete |

The point is reconciliation across a whole archive rather than one file. `critique`
already reconciles a target against its own last log entry; kb-search lets a run ask
whether the same root cause has fired on any other target. A retro can check whether a
long-horizon action from six weeks ago was ever carried out. A handoff can search prior
snapshots for what a past session already settled. See the top-level
[README](../README.md#how-the-skills-connect) for the full data-flow diagram across all
five skills.

## ⚠️ Hard dependency

kb-search defers one decision to `token-aware/references/search_policy.md`: when to reach
for it at all. That file is the gating rule (grep first; escalate to kb-search only when
grep is insufficient). Without it the skill gets reached for reflexively, which is the
failure it is most exposed to. Install `token-aware` alongside kb-search; the repo-root
installer warns if you do not.

## What it does

- `tools/index.py`: the core (chunking, tokenisation, the Lucene-style BM25, and a JSON,
  never pickle, index cache that lives beside the corpus rather than inside it) plus the
  explicit build CLI. Rarely run by hand; search builds lazily.
- `tools/search.py`: query a corpus, get ranked chunks as JSON. Always exits 0 and reports
  state in `status`, since a missing corpus is a normal condition a caller handles, not an
  error.

```
python tools/search.py --root <corpus-root> --domain <name> --query "<text>" [--top-k N]
```

The corpus indexed is `<root>/<domain>`: `--root` holds your corpora, `--domain` names
the subdirectory to search. Both are explicit, since the skill never guesses which project
is active and corpora live in different places (a retro journal under a project's own
`.claude/`, a handoff archive global under `~/.claude/`).

## Install

Copy the folder to wherever your surface reads skills from, or use the repo-root install
script (which installs `token-aware` too by default, so the policy dependency is present):

```bash
cp -r kb-search ~/.claude/skills/          # or: ./install.sh kb-search token-aware
```

The toolkit is standard-library only, so there is nothing to `pip install` to run it. For
the tests:

```bash
cd kb-search/tools
python -m pytest -q     # run it for the count; a number in prose drifts as tests are added
```

## Adapting this skill

**Point it at a real corpus.** Any append-only directory of markdown, text, or JSONL
files works. The four properties in `SKILL.md` § Corpus contract (plain text on disk, one
file per event dated in the filename, a stable location named in the owning skill, and
append-only in practice) are what make a corpus rank well and age well.

**`--domain` names the subdirectory under `--root` to index.** Give each corpus its own
subdirectory so their indexes stay separate; there is deliberately no cross-corpus search,
because ranking a critique finding against a retro line on one scale produces a
meaningless number.

**Tuning is minimal on purpose.** BM25 `BM25_K1` and `BM25_B` and the `NOISE_DIRS`
exclusion set live near the top of `tools/index.py`; the top-k cap and default excerpt
length are constants in `tools/search.py`. Change the excluded-directory set if your corpus
keeps machinery files somewhere unusual, but keep the exclusion: short, keyword-dense
machinery files outrank genuine content otherwise.

## Files

```
SKILL.md              the protocol, output contract, and design notes
tools/index.py        core (chunking, tokenisation, BM25, JSON cache) + build CLI
tools/search.py       query entry point (always exits 0, status in JSON)
tools/test_index.py   tests for the core and the build CLI
tools/test_search.py  tests for ranking and the four degradation states
```
