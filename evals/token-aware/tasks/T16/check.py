"""Check for T16: flattened device records.

Usage: python check.py <workdir>
Reads out/devices_flat.csv from the workdir and compares its header and rows
with a table computed here from hidden/devices.json.
Prints one line, PASS or FAIL: <reason>. Exit 0 on pass, 1 on fail.
"""

import csv
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = Path("out/devices_flat.csv")


def fail(reason: str) -> None:
    print(f"FAIL: {reason}")
    sys.exit(1)


def leaves(node, path, bag):
    if isinstance(node, dict):
        for name in node:
            leaves(node[name], path + [name], bag)
    elif path:
        bag[".".join(path)] = node


def text_of(node) -> str:
    if node is None:
        return ""
    if node is True:
        return "true"
    if node is False:
        return "false"
    if isinstance(node, list):
        return ";".join(text_of(x) for x in node)
    return str(node)


def expected() -> list[list[str]]:
    data = json.loads((HERE / "hidden" / "devices.json").read_text(encoding="utf-8"))
    bags = []
    names = set()
    for item in data:
        bag: dict = {}
        leaves(item, [], bag)
        bags.append(bag)
        names.update(bag)
    header = sorted(names)
    table = [header]
    for bag in bags:
        table.append([text_of(bag[n]) if n in bag else "" for n in header])
    return table


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: python check.py <workdir>")
    target = Path(sys.argv[1]).resolve() / OUTPUT
    if not target.is_file():
        fail(f"missing {OUTPUT.as_posix()}")
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail("output is not UTF-8 text")
    got = list(csv.reader(io.StringIO(text, newline="")))
    want = expected()
    if not got:
        fail("output is empty")
    if got[0] != want[0]:
        missing = sorted(set(want[0]) - set(got[0]))
        extra = sorted(set(got[0]) - set(want[0]))
        if not missing and not extra:
            fail("column order is not the sorted order of the flattened keys")
        fail(f"columns differ: missing {missing}, extra {extra}")
    if len(got) != len(want):
        fail(f"expected {len(want) - 1} data rows, found {len(got) - 1}")
    for number, (have, need) in enumerate(zip(got[1:], want[1:]), start=2):
        if have != need:
            for name, h, n in zip(want[0], have, need):
                if h != n:
                    fail(f"line {number} column {name}: expected '{n}', found '{h}'")
            fail(f"line {number} has {len(have)} cells, expected {len(need)}")
    print("PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # any unexpected error is a fail, with a reason
        print(f"FAIL: checker error {exc.__class__.__name__}")
        sys.exit(1)
