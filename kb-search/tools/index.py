"""Corpus indexing for kb-search.

Builds a BM25 index over a directory of markdown/text files, or over a .jsonl
file where each line is one record. Persists as JSON, never pickle: an index
cache lives in project directories that get synced, shared, or committed, and
unpickling executes arbitrary code. BM25Okapi is reconstructed in memory on
load; IDF computation is cheap enough that this costs nothing meaningful.

Nothing here reaches the network and nothing calls an LLM. Standard library
only: BM25 is implemented directly below rather than taken from rank_bm25.

This reverses an earlier intent to depend on rank_bm25, on evidence found while
implementing it. rank_bm25's BM25Okapi uses the IDF variant
log((N - n + 0.5) / (n + 0.5)), which is zero or negative once a term appears
in half or more of the documents -- on a two-file corpus a term in one file
scores exactly 0.0, and on a single-file corpus every score is negative. Those
are the corpus sizes every consuming skill starts at. Its BM25Plus avoids that
but adds a delta floor, scoring documents that do not contain the term above
zero, which breaks the "no results" honesty rule the degradation states rest on.
The Lucene-style IDF used here, ln(1 + (N - n + 0.5) / (n + 0.5)), is always
positive and gives a non-matching document exactly zero.

Python 3.10+, so it runs on 3.12 and 3.13 alike.
"""

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

INDEX_VERSION = 1

# Standard BM25 parameters. k1 controls term-frequency saturation, b controls
# length normalization; these are the conventional defaults.
BM25_K1 = 1.5
BM25_B = 0.75
TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
JSONL_SUFFIXES = {".jsonl"}

# Directories whose contents are never knowledge, only machinery. Any path with
# one of these as a component is skipped, along with any dot-directory.
#
# This is not hypothetical tidiness: a first real run indexed
# tools/.pytest_cache/README.md and ranked it second, above two genuine hits.
# Build artifacts, VCS internals, and dependency trees outrank real content
# easily because they are short and keyword-dense.
NOISE_DIRS = {
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "site-packages",
    "egg-info",
}


def is_noise_path(rel_parts: tuple[str, ...]) -> bool:
    """True when any path component is a dot-directory or known machinery.

    Checks components rather than the full path so a nested
    `a/.git/b/c.md` is caught, not merely a top-level `.git/`.
    """
    for part in rel_parts[:-1]:  # directory components only; the file is last
        if part.startswith("."):
            return True
        if part in NOISE_DIRS:
            return True
        if part.endswith(".egg-info"):
            return True
    return False

# Split on any non-alphanumeric run, underscore included, so snake_case
# identifiers like retro_capture match a query for "retro capture". Unicode-aware
# by default in Python 3, so non-ASCII content in retro journals and handoff
# snapshots tokenizes rather than collapsing to empty.
_TOKEN_SPLIT = re.compile(r"[\W_]+", re.UNICODE)

# A markdown ATX heading: one to six hashes, a space, then the heading text.
_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


class CorpusNotFound(FileNotFoundError):
    """Raised when the corpus root or domain directory does not exist."""


class EmptyCorpus(ValueError):
    """Raised when a corpus exists but yields no indexable chunks."""


@dataclass(frozen=True)
class Chunk:
    """One indexable unit: a heading section, or one JSONL record."""

    text: str
    source_file: str
    heading: str


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens. Empty strings dropped."""
    return [t for t in _TOKEN_SPLIT.split(text.lower()) if t]


def chunk_markdown(path: Path, rel_name: str) -> list[Chunk]:
    """Split a markdown/text file into one chunk per heading section.

    Text before the first heading becomes its own chunk under the heading
    "(preamble)", so a file with no headings at all still indexes as one chunk
    rather than silently contributing nothing.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Not fatal: a corpus can contain a stray non-UTF-8 file, and skipping
        # one file is better than failing the whole build.
        return []

    sections: list[tuple[str, list[str]]] = [("(preamble)", [])]
    for line in raw.splitlines():
        m = _HEADING.match(line)
        if m:
            sections.append((m.group(2), []))
        else:
            sections[-1][1].append(line)

    chunks = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        text = body if heading == "(preamble)" else f"{heading}\n\n{body}"
        chunks.append(Chunk(text=text, source_file=rel_name, heading=heading))
    return chunks


def chunk_jsonl(path: Path, rel_name: str) -> list[Chunk]:
    """One chunk per line of a .jsonl file.

    This is a format property, not a consumer-specific one: kb-search does not
    know or care what fields a record holds. Each record is flattened to its
    own JSON text so every value is searchable, and the heading is the line
    number, which is the only stable identifier a bare JSONL line has.
    """
    chunks = []
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    for lineno, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            # A malformed line is indexed as raw text rather than dropped:
            # losing a record silently is worse than ranking it imperfectly.
            text = line
        else:
            text = json.dumps(record, ensure_ascii=False)
        chunks.append(
            Chunk(text=text, source_file=rel_name, heading=f"line {lineno}")
        )
    return chunks


def collect_chunks(domain_dir: Path) -> list[Chunk]:
    """Walk a domain directory and chunk every file it recognizes.

    Recognition is by suffix. Unknown suffixes are skipped rather than read as
    text, so a stray binary in a corpus directory cannot poison the index.
    """
    chunks: list[Chunk] = []
    for path in sorted(domain_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(domain_dir)
        if is_noise_path(rel_path.parts):
            continue
        rel = rel_path.as_posix()
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            chunks.extend(chunk_markdown(path, rel))
        elif suffix in JSONL_SUFFIXES:
            chunks.extend(chunk_jsonl(path, rel))
    return chunks


def source_hash(domain_dir: Path) -> str:
    """Fingerprint the corpus so a stale index rebuilds itself.

    Covers path, size, and mtime of every recognized file. Content is not read
    here: a hash over metadata is enough to detect the edits that matter, and
    reading every file twice would double the cost of the common no-change case.
    """
    h = hashlib.sha256()
    h.update(f"v{INDEX_VERSION}\n".encode())
    for path in sorted(domain_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in (TEXT_SUFFIXES | JSONL_SUFFIXES):
            continue
        rel_path = path.relative_to(domain_dir)
        if is_noise_path(rel_path.parts):
            continue
        stat = path.stat()
        rel = rel_path.as_posix()
        h.update(f"{rel}|{stat.st_size}|{int(stat.st_mtime)}\n".encode())
    return h.hexdigest()


class BM25:
    """Okapi BM25 with the Lucene-style IDF, which stays positive on small corpora.

    idf(t) = ln(1 + (N - n + 0.5) / (n + 0.5))

    The classic variant drops the leading 1 and goes zero or negative once a
    term appears in half or more of the documents. On the corpus sizes these
    skills start at -- a handful of retro entries or handoff snapshots -- that
    silently returns nothing for terms that plainly match. A document that does
    not contain a query term contributes exactly zero for it, so a query
    sharing no vocabulary with the corpus scores zero everywhere and "no
    results" stays a truthful answer.
    """

    def __init__(self, corpus_tokens: list[list[str]], k1: float = BM25_K1, b: float = BM25_B):
        self.k1 = k1
        self.b = b
        self.doc_count = len(corpus_tokens)
        self.doc_lengths = [len(t) for t in corpus_tokens]
        total = sum(self.doc_lengths)
        self.avg_doc_length = (total / self.doc_count) if self.doc_count else 0.0
        self.term_freqs: list[dict[str, int]] = [Counter(t) for t in corpus_tokens]

        doc_freq: Counter[str] = Counter()
        for tf in self.term_freqs:
            doc_freq.update(tf.keys())
        self.idf = {
            term: math.log(
                1.0 + (self.doc_count - n + 0.5) / (n + 0.5)
            )
            for term, n in doc_freq.items()
        }

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        scores = [0.0] * self.doc_count
        if not self.doc_count or self.avg_doc_length == 0:
            return scores
        for term in query_tokens:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, tf in enumerate(self.term_freqs):
                f = tf.get(term, 0)
                if not f:
                    continue
                norm = 1.0 - self.b + self.b * (self.doc_lengths[i] / self.avg_doc_length)
                scores[i] += idf * (f * (self.k1 + 1.0)) / (f + self.k1 * norm)
        return scores


class Index:
    """An in-memory BM25 index plus the chunks it ranks."""

    def __init__(self, chunks: list[Chunk], corpus_hash: str):
        if not chunks:
            raise EmptyCorpus("corpus produced no indexable chunks")
        self.chunks = chunks
        self.corpus_hash = corpus_hash
        self._tokens = [tokenize(c.text) for c in chunks]
        self.bm25 = BM25(self._tokens)

    def to_json(self) -> dict:
        return {
            "index_version": INDEX_VERSION,
            "corpus_hash": self.corpus_hash,
            "chunks": [asdict(c) for c in self.chunks],
        }

    @classmethod
    # Quoted forward reference: on 3.13 annotations are still evaluated
    # eagerly, so a bare Index here would raise NameError inside its own
    # class body. PEP 649 changes this in 3.14; quoting works on both.
    def from_json(cls, data: dict) -> "Index":
        chunks = [Chunk(**c) for c in data["chunks"]]
        return cls(chunks, data["corpus_hash"])


def index_path_for(domain_dir: Path) -> Path:
    """Cache location: a sibling dotfile, so it never lands inside the corpus.

    An index written inside the corpus directory would be picked up by the next
    walk and change the source hash, guaranteeing a rebuild on every run.
    """
    return domain_dir.parent / f".{domain_dir.name}.kbindex.json"


def build_index(domain_dir: Path) -> Index:
    if not domain_dir.is_dir():
        raise CorpusNotFound(f"no such domain directory: {domain_dir}")
    chunks = collect_chunks(domain_dir)
    return Index(chunks, source_hash(domain_dir))


def save_index(index: Index, path: Path) -> None:
    path.write_text(
        json.dumps(index.to_json(), ensure_ascii=False), encoding="utf-8"
    )


def load_index(path: Path) -> Index:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("index_version") != INDEX_VERSION:
        raise ValueError("index version mismatch")
    return Index.from_json(data)


def get_or_build_index(domain_dir: Path, *, force: bool = False) -> tuple[Index, str]:
    """Load a fresh cached index, or rebuild. Returns (index, state).

    state is one of: "cached", "built", "rebuilt-stale", "rebuilt-corrupt".
    The caller reports it; a corrupt cache is rebuilt once rather than raised,
    so a corrupt cache is a recoverable condition rather than a crash.
    """
    if not domain_dir.is_dir():
        raise CorpusNotFound(f"no such domain directory: {domain_dir}")

    cache = index_path_for(domain_dir)
    current = source_hash(domain_dir)

    if not force and cache.exists():
        try:
            index = load_index(cache)
        except (json.JSONDecodeError, ValueError, KeyError, TypeError, OSError):
            index = build_index(domain_dir)
            save_index(index, cache)
            return index, "rebuilt-corrupt"
        if index.corpus_hash == current:
            return index, "cached"
        index = build_index(domain_dir)
        save_index(index, cache)
        return index, "rebuilt-stale"

    index = build_index(domain_dir)
    save_index(index, cache)
    return index, "built"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build or refresh a kb-search index for one domain."
    )
    ap.add_argument("--root", required=True, help="corpus root directory")
    ap.add_argument("--domain", required=True, help="domain name (subdirectory of root)")
    ap.add_argument("--force", action="store_true", help="rebuild even if the cache is fresh")
    a = ap.parse_args(argv)

    domain_dir = Path(a.root).expanduser().resolve() / a.domain
    try:
        index, state = get_or_build_index(domain_dir, force=a.force)
    except CorpusNotFound as e:
        print(f"corpus not found: {e}", file=sys.stderr)
        return 2
    except EmptyCorpus as e:
        print(f"empty corpus: {e}", file=sys.stderr)
        return 3

    print(
        json.dumps(
            {
                "domain": a.domain,
                "state": state,
                "chunks": len(index.chunks),
                "index_file": str(index_path_for(domain_dir)),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
