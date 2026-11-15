"""Draw the post figures from numbers.json only.

Usage: python figures.py --numbers numbers.json --out DIR
"""
import os
import sys

# The sibling numbers.py would shadow the standard library module of that name (imported by numpy).
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]

import argparse
import json
import math
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

matplotlib.rcParams.update({
    "svg.hashsalt": "token-aware-post-4",
    "svg.fonttype": "none",
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 100,
})

# Okabe-Ito colour-blind-safe palette
BLUE, ORANGE, GREEN, VERMILLION, SKY, PURPLE, YELLOW, BLACK = (
    "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#F0E442", "#000000")

COMPARISONS = ["K1_vs_K0", "K1_vs_N", "N_vs_K0", "K1f_vs_K0f", "K0f_vs_K0"]
B_ARMS = ["K0", "K0f", "K1", "K1f", "N"]


def label(cmp_key):
    return cmp_key.replace("_vs_", " against ")


class Numbers:
    def __init__(self, path):
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.raw = raw

    def __getitem__(self, key):
        return self.raw[key]["value"]

    def keys(self, prefix):
        return sorted(k for k in self.raw if k.startswith(prefix))


def save(fig, out, name, written):
    for ext, meta in (("png", {"Software": None}), ("svg", {"Date": None})):
        path = out / f"{name}.{ext}"
        kw = {"dpi": 200} if ext == "png" else {}
        fig.savefig(path, format=ext, metadata=meta, bbox_inches="tight", **kw)
        written.append(str(path))
    plt.close(fig)


def headline(n, out, written):
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, c in enumerate(COMPARISONS):
        base = f"confirmatory.comparison.{c}"
        ratio, lo, hi = n[f"{base}.ratio"], math.exp(n[f"{base}.lo"]), math.exp(n[f"{base}.hi"])
        y = len(COMPARISONS) - 1 - i
        ax.errorbar(ratio, y, xerr=[[ratio - lo], [hi - ratio]], fmt="o", color=BLUE, ecolor=BLUE,
                    capsize=4, markersize=6)
        ax.text(hi * 1.02, y + 0.18, f"{ratio:.3f} [{lo:.3f}, {hi:.3f}]", fontsize=8, va="bottom")
    bar = math.exp(n["confirmatory.constants.minimum_effect"])
    ax.axvline(1.0, color=BLACK, linewidth=1)
    ax.axvline(bar, color=VERMILLION, linewidth=1, linestyle="--")
    top = len(COMPARISONS) - 0.4
    ax.text(1.0, top, "ratio 1", ha="center", va="bottom", fontsize=8)
    ax.text(bar, top, f"minimum effect {bar:.2f}", ha="center", va="bottom", fontsize=8, color=VERMILLION)
    ax.set_xscale("log")
    ax.set_xticks([0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5])
    ax.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.1f"))
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_yticks(range(len(COMPARISONS)))
    ax.set_yticklabels([label(c) for c in reversed(COMPARISONS)])
    ax.set_ylim(-0.6, len(COMPARISONS) - 0.2)
    ax.set_xlabel("Cost-per-success ratio (log scale), mean with 95 per cent interval")
    ax.set_title("Headline: cost-per-success ratio by comparison")
    save(fig, out, "headline", written)


def forest(n, out, written):
    for c in COMPARISONS:
        keys = [k for k in n.keys(f"exploratory.forest.{c}.")]
        tasks = [k.rsplit(".", 1)[1] for k in keys]
        vals = [n[k] for k in keys]
        lo, hi = n[f"confirmatory.comparison.{c}.lo"], n[f"confirmatory.comparison.{c}.hi"]
        mean = n[f"confirmatory.comparison.{c}.mean"]
        fig, ax = plt.subplots(figsize=(6, 5))
        ys = list(range(len(tasks)))
        ax.axvspan(lo, hi, color=SKY, alpha=0.35, label="95 per cent interval")
        ax.axvline(mean, color=BLUE, linewidth=1.2, label="mean")
        ax.axvline(0.0, color=BLACK, linewidth=0.8)
        ax.scatter(vals, ys, color=VERMILLION, zorder=3, label="task")
        ax.set_yticks(ys)
        ax.set_yticklabels(tasks)
        ax.invert_yaxis()
        ax.set_xlabel("Per-task log cost-per-success difference")
        ax.set_title(f"Exploratory: per-task differences, {label(c)}")
        ax.legend(frameon=False, fontsize=8, loc="best")
        save(fig, out, f"forest_{c}", written)


def cost_decomposition(n, out, written):
    parts = [("input", BLUE), ("cache_read", GREEN), ("cache_write", ORANGE), ("output", VERMILLION)]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bottoms = [0.0] * len(B_ARMS)
    for part, colour in parts:
        vals = [n[f"exploratory.cost_decomposition.{a}.{part}"] for a in B_ARMS]
        ax.bar(B_ARMS, vals, bottom=bottoms, color=colour, label=part.replace("_", " "))
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_ylabel("Cost (USD)")
    ax.set_xlabel("Arm")
    ax.set_title("Exploratory: cost decomposition per track B arm")
    ax.legend(frameon=False, fontsize=8)
    save(fig, out, "cost_decomposition", written)


def power(n, out, written):
    pts = []
    for k in n.keys("exploratory.power_rule1.curve."):
        pts.append((float(k.rsplit(".curve.", 1)[1]), n[k]))
    pts.sort()
    bar = n["confirmatory.constants.minimum_effect"]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=BLUE, label="rule 1 pass probability")
    ax.plot([bar], [n["exploratory.power_rule1.at_bar"]], "o", color=VERMILLION, markersize=8,
            label=f"at the bar ({bar:.3f}): {n['exploratory.power_rule1.at_bar']:.3f}")
    dev = -0.070612
    ax.plot([dev], [n["exploratory.power_rule1.at_dev_estimate"]], "s", color=ORANGE, markersize=8,
            label=f"at the dev estimate ({dev:.3f}): {n['exploratory.power_rule1.at_dev_estimate']:.3f}")
    ax.set_xlabel("True effect (log cost-per-success difference)")
    ax.set_ylabel("Probability rule 1 passes")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Exploratory: rule 1 power curve, 12 tasks")
    ax.legend(frameon=False, fontsize=8, loc="center left")
    save(fig, out, "power_rule1", written)


def rule4(n, out, written):
    arms = ["AN", "AS", "ASn"]
    means = [n[f"confirmatory.rule4.{a}.mean"] for a in arms]
    sds = [n[f"confirmatory.rule4.{a}.sd"] for a in arms]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.bar(arms, means, yerr=sds, capsize=5, color=[BLUE, GREEN, ORANGE])
    target = n["confirmatory.constants.as_target"]
    line = target * means[0]
    ax.axhline(line, color=VERMILLION, linestyle="--", linewidth=1.2,
               label=f"{target:.2f} x AN mean = {line:.0f}")
    ax.set_ylabel("Scored size (tokens), mean with SD")
    ax.set_xlabel("Arm")
    ax.set_title("Rule 4: scored size by arm")
    ax.legend(frameon=False, fontsize=8)
    save(fig, out, "rule4", written)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--numbers", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    n = Numbers(a.numbers)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    headline(n, out, written)
    forest(n, out, written)
    cost_decomposition(n, out, written)
    power(n, out, written)
    rule4(n, out, written)
    for w in written:
        print(w)


if __name__ == "__main__":
    main()
