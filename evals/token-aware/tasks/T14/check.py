"""Check for T14: cleaned contact export.

Usage: python check.py <workdir>
Reads out/contacts_clean.csv from the workdir and compares it with the rows
computed here from hidden/contacts_export.csv.
Prints one line, PASS or FAIL: <reason>. Exit 0 on pass, 1 on fail.
"""

import csv
import io
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = Path("out/contacts_clean.csv")
HEADER = ["email", "name", "signup_date", "monthly_fee_eur"]


def fail(reason: str) -> None:
    print(f"FAIL: {reason}")
    sys.exit(1)


def fee_text(raw: str) -> str:
    raw = raw.strip()
    if raw == "":
        return "0.00"
    value = Decimal(raw.replace(".", "").replace(",", "."))
    return f"{value:.2f}"


def expected_rows() -> list[list[str]]:
    raw = (HERE / "hidden" / "contacts_export.csv").read_bytes()
    text = raw.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=";"))
    header, body = rows[0], rows[1:]
    index = {name: header.index(name) for name in ("E-mail", "Name", "Signup date", "Fee")}
    best: dict[str, tuple[date, list[str]]] = {}
    for cells in body:
        if not cells:
            continue
        email = cells[index["E-mail"]].strip().lower()
        day, month, year = (int(p) for p in cells[index["Signup date"]].strip().split("."))
        signed = date(year, month, day)
        name = " ".join(cells[index["Name"]].split())
        out = [email, name, signed.isoformat(), fee_text(cells[index["Fee"]])]
        if email not in best or signed > best[email][0]:
            best[email] = (signed, out)
    return [best[key][1] for key in sorted(best)]


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: python check.py <workdir>")
    target = Path(sys.argv[1]).resolve() / OUTPUT
    if not target.is_file():
        fail(f"missing {OUTPUT.as_posix()}")
    raw = target.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        fail("output starts with a byte order mark")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        fail("output is not UTF-8")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows or rows[0] != HEADER:
        fail("header must be email,name,signup_date,monthly_fee_eur")
    got = rows[1:]
    want = expected_rows()
    if len(got) != len(want):
        fail(f"expected {len(want)} rows, found {len(got)}")
    for number, (have, need) in enumerate(zip(got, want), start=2):
        if have != need:
            fail(f"line {number}: expected {','.join(need)}, found {','.join(have)}")
    print("PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # any unexpected error is a fail, with a reason
        print(f"FAIL: checker error {exc.__class__.__name__}")
        sys.exit(1)
