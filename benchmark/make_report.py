#!/usr/bin/env python3
"""Combine result_*.json files into a single comparison report (Markdown)."""
import glob
import json
import os

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
OPS = [
    ("point_lookup", "Point lookup (by id)"),
    ("one_hop", "1-hop neighbors"),
    ("two_hop", "2-hop count (FoF)"),
    ("three_hop", "3-hop count"),
    ("shortest_path", "Shortest path (<=5)"),
]
ENGINE_LABELS = {
    "neo4j": "Neo4j Community (VM)",
    "postgresql": "PostgreSQL Flexible",
    "cosmos_gremlin": "Cosmos DB (Gremlin)",
}


def load_results():
    out = {}
    for path in glob.glob(os.path.join(RESULTS_DIR, "result_*.json")):
        with open(path) as f:
            data = json.load(f)
        out[data["engine"]] = data
    return out


def fmt(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) else "-"


def main():
    res = load_results()
    if not res:
        print("No results found in", RESULTS_DIR)
        return
    engines = [e for e in ["neo4j", "postgresql", "cosmos_gremlin"] if e in res]

    lines = ["# Graph DB Performance Comparison\n"]
    lines.append("Workload: synthetic social graph. All engines run the "
                 "same logical operations on identical data.\n")
    lines.append("Compute: ~4 vCPU / 16 GB class for each engine.\n")

    for metric in ["p50_ms", "p95_ms", "mean_ms"]:
        lines.append(f"\n## {metric.replace('_ms',' (ms)').upper()}\n")
        header = "| Operation | " + " | ".join(ENGINE_LABELS[e] for e in engines) + " |"
        sep = "|" + "---|" * (len(engines) + 1)
        lines.append(header)
        lines.append(sep)
        for key, desc in OPS:
            row = [desc]
            for e in engines:
                v = res[e]["operations"].get(key, {}).get(metric)
                row.append(fmt(v))
            lines.append("| " + " | ".join(row) + " |")

    # winner per op by p50
    lines.append("\n## Fastest engine per operation (by P50)\n")
    lines.append("| Operation | Winner | P50 (ms) |")
    lines.append("|---|---|---|")
    for key, desc in OPS:
        best_e, best_v = None, None
        for e in engines:
            v = res[e]["operations"].get(key, {}).get("p50_ms")
            if v is not None and (best_v is None or v < best_v):
                best_e, best_v = e, v
        if best_e:
            lines.append(f"| {desc} | {ENGINE_LABELS[best_e]} | {fmt(best_v)} |")

    report = "\n".join(lines) + "\n"
    out_path = os.path.join(RESULTS_DIR, "REPORT.md")
    with open(out_path, "w") as f:
        f.write(report)
    print("Wrote", out_path)
    print(report)


if __name__ == "__main__":
    main()
