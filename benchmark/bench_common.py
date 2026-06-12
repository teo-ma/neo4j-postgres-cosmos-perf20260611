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

NUM_NODES = int(os.environ.get("NUM_NODES", "100000"))
SEED = int(os.environ.get("SEED", "42"))
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

# Logical workload definitions shared by all engines.
# Each is run ITERATIONS times against pre-sampled node ids.
ITERATIONS = 200
WARMUP = 20

# Operations every engine must implement (key -> human description)
OPERATIONS = [
    ("point_lookup", "Point lookup by person id"),
    ("three_hop", "3-hop reachable distinct count"),
    ("four_hop", "4-hop reachable distinct count"),
    ("five_hop", "5-hop reachable distinct count"),
    ("shortest_path", "Shortest path between two persons (<=7 hops)"),
]


def sample_ids(n, count):
    rnd = random.Random(SEED)
    return [rnd.randint(0, n - 1) for _ in range(count)]


def sample_pairs(n, count):
    rnd = random.Random(SEED + 1)
    # bias destinations toward hub nodes (id < 1000) so paths usually exist
    return [(rnd.randint(0, n - 1), rnd.randint(0, min(999, n - 1)))
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
