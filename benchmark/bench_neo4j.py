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
    print("Creating constraint + indexes...")
    with driver.session() as s:
        s.run("CREATE CONSTRAINT person_id IF NOT EXISTS "
              "FOR (p:Person) REQUIRE p.id IS UNIQUE")
    # Load persons in batches
    import csv
    t0 = time.time()
    with open(os.path.join(DATA_DIR, "persons.csv")) as f:
        rows = list(csv.DictReader(f))
    print(f"Loading {len(rows)} persons...")
    with driver.session() as s:
        batch = []
        for r in rows:
            batch.append({"id": int(r["id"]), "name": r["name"],
                          "age": int(r["age"]), "city": r["city"]})
            if len(batch) >= 5000:
                s.run("UNWIND $rows AS r CREATE (p:Person) SET p = r", rows=batch)
                batch = []
        if batch:
            s.run("UNWIND $rows AS r CREATE (p:Person) SET p = r", rows=batch)
    print(f"Persons loaded in {time.time()-t0:.1f}s")

    t0 = time.time()
    with open(os.path.join(DATA_DIR, "knows.csv")) as f:
        edges = list(csv.DictReader(f))
    print(f"Loading {len(edges)} KNOWS edges...")
    with driver.session() as s:
        batch = []
        for e in edges:
            batch.append({"src": int(e["src"]), "dst": int(e["dst"]),
                          "since": int(e["since"])})
            if len(batch) >= 10000:
                s.run("UNWIND $rows AS r MATCH (a:Person {id:r.src}), "
                      "(b:Person {id:r.dst}) CREATE (a)-[:KNOWS {since:r.since}]->(b)",
                      rows=batch)
                batch = []
        if batch:
            s.run("UNWIND $rows AS r MATCH (a:Person {id:r.src}), "
                  "(b:Person {id:r.dst}) CREATE (a)-[:KNOWS {since:r.since}]->(b)",
                  rows=batch)
    print(f"Edges loaded in {time.time()-t0:.1f}s")


def bench(driver):
    ids = bc.sample_ids(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    pairs = bc.sample_pairs(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    results = {}

    with driver.session() as s:
        def point_lookup(i):
            s.run("MATCH (p:Person {id:$id}) RETURN p.name",
                  id=ids[i]).consume()

        def one_hop(i):
            s.run("MATCH (p:Person {id:$id})-[:KNOWS]->(f) RETURN f.id",
                  id=ids[i]).consume()

        def two_hop(i):
            s.run("MATCH (p:Person {id:$id})-[:KNOWS*2]->(f) "
                  "RETURN count(DISTINCT f)", id=ids[i]).consume()

        def three_hop(i):
            s.run("MATCH (p:Person {id:$id})-[:KNOWS*3]->(f) "
                  "RETURN count(DISTINCT f)", id=ids[i]).consume()

        def shortest_path(i):
            src, dst = pairs[i]
            s.run("MATCH (a:Person {id:$s}),(b:Person {id:$d}), "
                  "p = shortestPath((a)-[:KNOWS*..5]->(b)) RETURN length(p)",
                  s=src, d=dst).consume()

        fns = {"point_lookup": point_lookup, "one_hop": one_hop,
               "two_hop": two_hop, "three_hop": three_hop,
               "shortest_path": shortest_path}
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
