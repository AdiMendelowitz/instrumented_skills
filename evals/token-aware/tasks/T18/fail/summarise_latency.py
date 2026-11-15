"""Latency summary per route, using nearest-rank percentiles."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def normalise(path):
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    segments = ["{id}" if seg.isdigit() else seg for seg in path.split("/")]
    return "/".join(segments)


def percentile(ordered, p):
    index = (p * len(ordered)) // 100
    return ordered[index]


def main():
    latencies = {}
    timeouts = {}
    with (ROOT / "data" / "requests.log").open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            _timestamp, method, path, _status, latency = line.split()
            key = f"{method} {normalise(path)}"
            timeouts.setdefault(key, 0)
            if latency == "n/a":
                timeouts[key] += 1
            else:
                latencies.setdefault(key, []).append(int(latency))
    summary = {}
    for key in sorted(timeouts):
        values = sorted(latencies.get(key, []))
        summary[key] = {
            "count": len(values),
            "p50_ms": percentile(values, 50),
            "p95_ms": percentile(values, 95),
            "timeouts": timeouts[key],
        }
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    text = json.dumps(summary, indent=2) + "\n"
    (out_dir / "latency_summary.json").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
