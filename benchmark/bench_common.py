#!/usr/bin/env python3
"""Shared benchmark utilities: timing, warmup, percentile reporting.

Each database-specific benchmark module implements the same set of
logical operations and feeds latencies here so results are comparable.
"""
import json
import os
import random
import statistics
import time

NUM_NODES = int(os.environ.get("NUM_NODES", "20000"))
SEED = int(os.environ.get("SEED", "42"))
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

# Logical workload definitions shared by all engines.
# Each is run ITERATIONS times against pre-sampled node ids.
ITERATIONS = 200
WARMUP = 20

# Drug-discovery workload. All operations start from a Compound and follow the
# typed meta-graph used in generate_data.py:
#   Compound -TARGETS-> Protein -INTERACTS-> Protein
#                       Protein -PARTICIPATES_IN-> Pathway -IMPLICATED_IN-> Disease
# Operations every engine must implement (key -> human description)
OPERATIONS = [
    ("point_lookup", "Compound point lookup by id"),
    ("targets_2hop", "Compound -> target -> interacting protein (2-hop count)"),
    ("pathway_3hop", "Compound -> target -> pathway -> disease (3-hop count)"),
    ("reach_4hop", "Compound -> target -> PPI -> pathway -> disease (4-hop count)"),
    ("evidence_path", "Shortest evidence chain Compound -> Disease (<=7)"),
]

# Node type proportions (keep in sync with generate_data.py).
TYPE_FRACTIONS = [
    ("Compound", 0.20),
    ("Protein", 0.35),
    ("Gene", 0.25),
    ("Disease", 0.15),
    ("Pathway", 0.05),
]


def compute_ranges(n):
    """Return {type: (start, end_exclusive)} contiguous id ranges."""
    ranges = {}
    start = 0
    items = list(TYPE_FRACTIONS)
    for idx, (t, frac) in enumerate(items):
        if idx == len(items) - 1:
            end = n
        else:
            end = start + max(1, int(round(n * frac)))
        ranges[t] = (start, end)
        start = end
    return ranges


def sample_compounds(n, count):
    """Sample Compound ids (traversal start points)."""
    rng = random.Random(SEED)
    s, e = compute_ranges(n)["Compound"]
    return [rng.randint(s, e - 1) for _ in range(count)]


def sample_evidence_pairs(n, count):
    """Sample (compound_id, disease_id) pairs for shortest-path queries."""
    rng = random.Random(SEED + 1)
    ranges = compute_ranges(n)
    cs, ce = ranges["Compound"]
    ds, de = ranges["Disease"]
    return [(rng.randint(cs, ce - 1), rng.randint(ds, de - 1))
            for _ in range(count)]


def percentiles(latencies_ms):
    if not latencies_ms:
        return {}
    s = sorted(latencies_ms)
    n = len(s)
    def pct(p):
        idx = min(n - 1, int(round(p / 100.0 * (n - 1))))
        return round(s[idx], 3)
    return {
        "count": n,
        "mean_ms": round(statistics.mean(s), 3),
        "p50_ms": pct(50),
        "p95_ms": pct(95),
        "p99_ms": pct(99),
        "min_ms": round(s[0], 3),
        "max_ms": round(s[-1], 3),
    }


def time_op(fn, iterations=ITERATIONS, warmup=WARMUP):
    """Run fn(i) iterations times; return latency stats in ms."""
    for i in range(warmup):
        try:
            fn(i)
        except Exception:
            pass
    lat = []
    for i in range(iterations):
        t0 = time.perf_counter()
        fn(i)
        lat.append((time.perf_counter() - t0) * 1000.0)
    return percentiles(lat)


def save_result(engine, results, extra=None):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    payload = {"engine": engine, "operations": results}
    if extra:
        payload.update(extra)
    path = os.path.join(RESULTS_DIR, f"result_{engine}.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Saved {path}")
    return path
