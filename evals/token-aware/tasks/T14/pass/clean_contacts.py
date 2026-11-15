"""Clean the contact export.

Reads data/contacts_export.csv (semicolon-separated, UTF-8 with an optional
byte order mark) and writes out/contacts_clean.csv.
"""

import csv
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

SOURCE = Path("data/contacts_export.csv")
TARGET = Path("out/contacts_clean.csv")
HEADER = ["email", "name", "signup_date", "monthly_fee_eur"]
WHITESPACE = re.compile(r"\s+")
CENT = Decimal("0.01")


def clean_name(text: str) -> str:
    return WHITESPACE.sub(" ", text).strip()


def clean_fee(text: str) -> str:
    text = text.strip()
    if not text:
        return format(Decimal("0.00"), "f")
    plain = text.replace(".", "").replace(",", ".")
    return format(Decimal(plain).quantize(CENT), "f")


def clean_date(text: str) -> str:
    return datetime.strptime(text.strip(), "%d.%m.%Y").date().isoformat()


def main() -> None:
    latest: dict[str, dict[str, str]] = {}
    with SOURCE.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            record = {
                "email": row["E-mail"].strip().lower(),
                "name": clean_name(row["Name"]),
                "signup_date": clean_date(row["Signup date"]),
                "monthly_fee_eur": clean_fee(row["Fee"]),
            }
            kept = latest.get(record["email"])
            if kept is None or record["signup_date"] > kept["signup_date"]:
                latest[record["email"]] = record

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(HEADER)
        for email in sorted(latest):
            record = latest[email]
            writer.writerow([record[column] for column in HEADER])


if __name__ == "__main__":
    main()
