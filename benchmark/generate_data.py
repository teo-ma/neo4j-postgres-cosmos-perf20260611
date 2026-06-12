#!/usr/bin/env python3
"""Generate a synthetic drug-discovery knowledge graph shared by all engines.

Heterogeneous, Hetionet-flavored graph with typed nodes and typed edges.
Outputs into ./data/:
  - nodes.csv : id,type,name
  - edges.csv : src,dst,rel

Node types (contiguous id ranges, scaled from NUM_NODES):
  Compound, Protein, Gene, Disease, Pathway
Edge (relation) types form a meta-graph that supports drug-discovery
reasoning paths, e.g.:
  Compound -TARGETS-> Protein -PARTICIPATES_IN-> Pathway -IMPLICATED_IN-> Disease
  Compound -TARGETS-> Protein -INTERACTS-> Protein -PARTICIPATES_IN-> Pathway -IMPLICATED_IN-> Disease
The same files are loaded into Neo4j, PostgreSQL and Cosmos DB so the
benchmark compares identical data.
"""
import csv
import os
import random
import sys

NUM_NODES = int(os.environ.get("NUM_NODES", "20000"))
NUM_EDGES = int(os.environ.get("NUM_EDGES", "200000"))
SEED = int(os.environ.get("SEED", "42"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Node type proportions (must sum to ~1.0).
TYPE_FRACTIONS = [
    ("Compound", 0.20),
    ("Protein", 0.35),
    ("Gene", 0.25),
    ("Disease", 0.15),
    ("Pathway", 0.05),
]

# Relation type proportions of NUM_EDGES (must sum to ~1.0).
REL_FRACTIONS = [
    ("TARGETS", 0.25),          # Compound -> Protein
    ("INTERACTS", 0.32),        # Protein  -> Protein (PPI)
    ("ENCODES", 0.04),          # Gene     -> Protein
    ("ASSOCIATED_WITH", 0.10),  # Gene     -> Disease
    ("PARTICIPATES_IN", 0.15),  # Protein  -> Pathway
    ("IMPLICATED_IN", 0.08),    # Pathway  -> Disease
    ("TREATS", 0.06),           # Compound -> Disease (known therapy)
]

TYPE_PREFIX = {"Compound": "CMPD", "Protein": "PROT", "Gene": "GENE",
               "Disease": "DIS", "Pathway": "PWY"}


def compute_ranges(n):
    """Return {type: (start, end_exclusive)} contiguous id ranges."""
    ranges = {}
    start = 0
    items = list(TYPE_FRACTIONS)
    for idx, (t, frac) in enumerate(items):
        if idx == len(items) - 1:
            end = n  # last type absorbs rounding remainder
        else:
            end = start + max(1, int(round(n * frac)))
        ranges[t] = (start, end)
        start = end
    return ranges


def _rand_in(rng, span):
    return rng.randint(span[0], span[1] - 1)


def main():
    rng = random.Random(SEED)
    os.makedirs(DATA_DIR, exist_ok=True)
    ranges = compute_ranges(NUM_NODES)
    print("Node id ranges:", ranges)

    print(f"Generating {NUM_NODES} nodes -> nodes.csv")
    with open(os.path.join(DATA_DIR, "nodes.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "type", "name"])
        for t, (s, e) in ranges.items():
            pfx = TYPE_PREFIX[t]
            for i in range(s, e):
                w.writerow([i, t, f"{pfx}_{i}"])

    # Hub sets to keep deep traversals expensive (skewed degree).
    prot_s, prot_e = ranges["Protein"]
    dis_s, dis_e = ranges["Disease"]
    hub_prot_end = prot_s + max(1, int((prot_e - prot_s) * 0.05))  # top 5% PPI hubs
    hub_dis_end = dis_s + max(1, int((dis_e - dis_s) * 0.10))      # top 10% disease hubs

    def gen_edges(rel, count, src_t, dst_t, seen, w):
        sr = ranges[src_t]
        dr = ranges[dst_t]
        written = 0
        attempts = 0
        max_attempts = count * 20
        while written < count and attempts < max_attempts:
            attempts += 1
            src = _rand_in(rng, sr)
            if rel == "INTERACTS" and rng.random() < 0.20:
                dst = rng.randint(prot_s, hub_prot_end - 1)  # bias to PPI hubs
            elif rel == "IMPLICATED_IN" and rng.random() < 0.20:
                dst = rng.randint(dis_s, hub_dis_end - 1)    # bias to disease hubs
            else:
                dst = _rand_in(rng, dr)
            if src == dst:
                continue
            key = (src, dst, rel)
            if key in seen:
                continue
            seen.add(key)
            w.writerow([src, dst, rel])
            written += 1
        return written

    rel_targets = {
        "TARGETS": ("Compound", "Protein"),
        "INTERACTS": ("Protein", "Protein"),
        "ENCODES": ("Gene", "Protein"),
        "ASSOCIATED_WITH": ("Gene", "Disease"),
        "PARTICIPATES_IN": ("Protein", "Pathway"),
        "IMPLICATED_IN": ("Pathway", "Disease"),
        "TREATS": ("Compound", "Disease"),
    }

    print(f"Generating ~{NUM_EDGES} edges -> edges.csv")
    seen = set()
    total = 0
    with open(os.path.join(DATA_DIR, "edges.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src", "dst", "rel"])
        for rel, frac in REL_FRACTIONS:
            count = int(round(NUM_EDGES * frac))
            src_t, dst_t = rel_targets[rel]
            n = gen_edges(rel, count, src_t, dst_t, seen, w)
            total += n
            print(f"  {rel}: {n} edges ({src_t} -> {dst_t})")
    print(f"Done. {NUM_NODES} nodes, {total} edges in", DATA_DIR)


if __name__ == "__main__":
    sys.exit(main())
