"""Flatten nested device records into a CSV table.

Reads data/devices.json (a JSON array of objects) and writes
out/devices_flat.csv with one row per device.
"""

import csv
import json
from pathlib import Path

SOURCE = Path("data/devices.json")
TARGET = Path("out/devices_flat.csv")


def flatten(value, prefix: str, out: dict) -> None:
    """Store every leaf value under its dotted key path. Empty objects add nothing."""
    if isinstance(value, dict):
        for key, inner in value.items():
            flatten(inner, f"{prefix}.{key}" if prefix else key, out)
        return
    out[prefix] = value


def render(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ";".join(render(item) for item in value)
    return str(value)


def main() -> None:
    with SOURCE.open(encoding="utf-8") as handle:
        records = json.load(handle)

    flat_records = []
    columns: set[str] = set()
    for record in records:
        out: dict = {}
        flatten(record, "", out)
        flat_records.append(out)
        columns.update(out)

    ordered = sorted(columns)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(ordered)
        for out in flat_records:
            writer.writerow([render(out[c]) if c in out else "" for c in ordered])


if __name__ == "__main__":
    main()
