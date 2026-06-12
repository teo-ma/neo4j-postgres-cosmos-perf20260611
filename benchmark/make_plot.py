#!/usr/bin/env python3
"""Render results/benchmark_p50_comparison.png from result_*.json.

Deep-hop latencies span several orders of magnitude (sub-ms point lookups vs
multi-second deep traversals), so the y-axis uses a log scale.
"""
import glob
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
OPS = [
    ("point_lookup", "Point lookup"),
    ("three_hop", "3-hop"),
    ("four_hop", "4-hop"),
    ("five_hop", "5-hop"),
    ("shortest_path", "Shortest path (<=7)"),
]
ENGINES = [
    ("neo4j", "Neo4j Community (VM)", "#4C72B0"),
    ("postgresql", "PostgreSQL Flexible", "#55A868"),
    ("cosmos_gremlin", "Cosmos DB (Gremlin)", "#C44E52"),
]


def load_results():
    out = {}
    for path in glob.glob(os.path.join(RESULTS_DIR, "result_*.json")):
        with open(path) as f:
            data = json.load(f)
        out[data["engine"]] = data
    return out


def main():
    res = load_results()
    op_keys = [k for k, _ in OPS]
    op_labels = [lbl for _, lbl in OPS]
    x = np.arange(len(op_keys))
    width = 0.26

    fig, ax = plt.subplots(figsize=(11, 6))
    for i, (eng, label, color) in enumerate(ENGINES):
        if eng not in res:
            continue
        vals = []
        for k in op_keys:
            v = res[eng]["operations"].get(k, {}).get("p50_ms")
            vals.append(v if v is not None else 0)
        offset = (i - 1) * width
        bars = ax.bar(x + offset, vals, width, label=label, color=color)
        for rect, v in zip(bars, vals):
            if v > 0:
                ax.annotate(f"{v:.1f}", xy=(rect.get_x() + rect.get_width() / 2, v),
                            xytext=(0, 3), textcoords="offset points",
                            ha="center", va="bottom", fontsize=7)

    ax.set_yscale("log")
    ax.set_ylabel("P50 latency (ms, log scale)")
    ax.set_title("Graph DB Deep-Hop Performance (P50, lower is better)")
    ax.set_xticks(x)
    ax.set_xticklabels(op_labels)
    ax.legend()
    ax.grid(axis="y", which="both", linestyle=":", alpha=0.4)
    fig.tight_layout()

    out_path = os.path.join(RESULTS_DIR, "benchmark_p50_comparison.png")
    fig.savefig(out_path, dpi=130)
    print("Wrote", out_path)


if __name__ == "__main__":
    main()
