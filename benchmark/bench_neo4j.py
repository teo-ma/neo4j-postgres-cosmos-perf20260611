#!/usr/bin/env python3
"""Neo4j Community benchmark: load data + run shared workload.

Runs ON the Neo4j VM. Connects to bolt://localhost:7687.
Env: NEO4J_PASSWORD, NUM_NODES, plus standard benchmark vars.
Usage:
  python3 bench_neo4j.py load    # bulk load persons + knows
  python3 bench_neo4j.py bench   # run benchmark
"""
import os
import sys
import time

from neo4j import GraphDatabase

import bench_common as bc

URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
USER = os.environ.get("NEO4J_USER", "neo4j")
PWD = os.environ.get("NEO4J_PASSWORD", "neo4jpass123")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def get_driver():
    return GraphDatabase.driver(URI, auth=(USER, PWD))


def load(driver):
    import csv
    from collections import defaultdict
    print("Creating constraint...")
    with driver.session() as s:
        s.run("CREATE CONSTRAINT entity_id IF NOT EXISTS "
              "FOR (n:Entity) REQUIRE n.id IS UNIQUE")
    # Load nodes in batches
    t0 = time.time()
    with open(os.path.join(DATA_DIR, "nodes.csv")) as f:
        rows = list(csv.DictReader(f))
    print(f"Loading {len(rows)} nodes...")
    with driver.session() as s:
        batch = []
        for r in rows:
            batch.append({"id": int(r["id"]), "type": r["type"],
                          "name": r["name"]})
            if len(batch) >= 5000:
                s.run("UNWIND $rows AS r CREATE (n:Entity) SET n = r", rows=batch)
                batch = []
        if batch:
            s.run("UNWIND $rows AS r CREATE (n:Entity) SET n = r", rows=batch)
    print(f"Nodes loaded in {time.time()-t0:.1f}s")

    # Group edges by relation type; relation types come from a fixed allowlist
    # so the type can be safely interpolated into the Cypher statement.
    t0 = time.time()
    groups = defaultdict(list)
    with open(os.path.join(DATA_DIR, "edges.csv")) as f:
        for e in csv.DictReader(f):
            groups[e["rel"]].append({"src": int(e["src"]), "dst": int(e["dst"])})
    allowed = {"TARGETS", "INTERACTS", "ENCODES", "ASSOCIATED_WITH",
               "PARTICIPATES_IN", "IMPLICATED_IN", "TREATS"}
    total = 0
    with driver.session() as s:
        for rel, items in groups.items():
            if rel not in allowed:
                continue
            print(f"  {rel}: {len(items)} edges")
            for i in range(0, len(items), 10000):
                batch = items[i:i + 10000]
                s.run(f"UNWIND $rows AS r MATCH (a:Entity {{id:r.src}}),"
                      f"(b:Entity {{id:r.dst}}) CREATE (a)-[:{rel}]->(b)",
                      rows=batch)
                total += len(batch)
    print(f"{total} edges loaded in {time.time()-t0:.1f}s")


def bench(driver):
    cids = bc.sample_compounds(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    pairs = bc.sample_evidence_pairs(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    results = {}

    with driver.session() as s:
        def point_lookup(i):
            s.run("MATCH (c:Entity {id:$id}) RETURN c.name",
                  id=cids[i]).consume()

        def targets_2hop(i):
            s.run("MATCH (c:Entity {id:$id})-[:TARGETS]->()-[:INTERACTS]->(p) "
                  "RETURN count(DISTINCT p)", id=cids[i]).consume()

        def pathway_3hop(i):
            s.run("MATCH (c:Entity {id:$id})-[:TARGETS]->()"
                  "-[:PARTICIPATES_IN]->()-[:IMPLICATED_IN]->(d) "
                  "RETURN count(DISTINCT d)", id=cids[i]).consume()

        def reach_4hop(i):
            s.run("MATCH (c:Entity {id:$id})-[:TARGETS]->()-[:INTERACTS]->()"
                  "-[:PARTICIPATES_IN]->()-[:IMPLICATED_IN]->(d) "
                  "RETURN count(DISTINCT d)", id=cids[i]).consume()

        def evidence_path(i):
            src, dst = pairs[i]
            s.run("MATCH (a:Entity {id:$s}),(b:Entity {id:$d}), "
                  "p = shortestPath((a)-[*..7]->(b)) RETURN length(p)",
                  s=src, d=dst).consume()

        fns = {"point_lookup": point_lookup,
               "targets_2hop": targets_2hop, "pathway_3hop": pathway_3hop,
               "reach_4hop": reach_4hop,
               "evidence_path": evidence_path}
        for key, _desc in bc.OPERATIONS:
            print(f"Running {key}...")
            results[key] = bc.time_op(fns[key])
            print(f"  {results[key]}")

    bc.save_result("neo4j", results)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "bench"
    driver = get_driver()
    try:
        if mode == "load":
            load(driver)
        else:
            bench(driver)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
