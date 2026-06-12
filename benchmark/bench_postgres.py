#!/usr/bin/env python3
"""PostgreSQL benchmark: model the graph as relational tables and run
the same logical workload using recursive CTEs.

Env: PG_HOST, PG_USER, PG_PASSWORD, PG_DB (default 'graphdb'), plus
standard benchmark vars.
Usage:
  python3 bench_postgres.py load
  python3 bench_postgres.py bench
"""
import csv
import io
import os
import sys
import time

import psycopg2

import bench_common as bc

HOST = os.environ["PG_HOST"]
USER = os.environ["PG_USER"]
PWD = os.environ["PG_PASSWORD"]
DB = os.environ.get("PG_DB", "graphdb")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def connect(db=DB):
    return psycopg2.connect(host=HOST, user=USER, password=PWD, dbname=db,
                            sslmode="require")


def ensure_db():
    conn = connect(db="postgres")
    conn.autocommit = True
    with conn.cursor() as c:
        c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB,))
        if not c.fetchone():
            c.execute(f"CREATE DATABASE {DB}")
    conn.close()


def load():
    ensure_db()
    conn = connect()
    conn.autocommit = False
    with conn.cursor() as c:
        c.execute("DROP TABLE IF EXISTS knows; DROP TABLE IF EXISTS person;")
        c.execute("CREATE TABLE person (id int PRIMARY KEY, name text, "
                  "age int, city text)")
        c.execute("CREATE TABLE knows (src int, dst int, since int)")
        conn.commit()

        t0 = time.time()
        print("COPY persons...")
        with open(os.path.join(DATA_DIR, "persons.csv")) as f:
            c.copy_expert("COPY person(id,name,age,city) FROM STDIN WITH CSV HEADER", f)
        conn.commit()
        print(f"  persons in {time.time()-t0:.1f}s")

        t0 = time.time()
        print("COPY knows...")
        with open(os.path.join(DATA_DIR, "knows.csv")) as f:
            c.copy_expert("COPY knows(src,dst,since) FROM STDIN WITH CSV HEADER", f)
        conn.commit()
        print(f"  edges in {time.time()-t0:.1f}s")

        t0 = time.time()
        print("Creating indexes...")
        c.execute("CREATE INDEX idx_knows_src ON knows(src)")
        c.execute("CREATE INDEX idx_knows_dst ON knows(dst)")
        c.execute("ANALYZE person; ANALYZE knows;")
        conn.commit()
        print(f"  indexes in {time.time()-t0:.1f}s")
    conn.close()


def bench():
    ids = bc.sample_ids(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    pairs = bc.sample_pairs(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    conn = connect()
    conn.autocommit = True
    results = {}
    with conn.cursor() as c:
        def point_lookup(i):
            c.execute("SELECT name FROM person WHERE id=%s", (ids[i],))
            c.fetchall()

        def three_hop(i):
            c.execute(
                "SELECT count(DISTINCT k3.dst) FROM knows k1 "
                "JOIN knows k2 ON k1.dst=k2.src "
                "JOIN knows k3 ON k2.dst=k3.src WHERE k1.src=%s", (ids[i],))
            c.fetchall()

        def four_hop(i):
            c.execute(
                "SELECT count(DISTINCT k4.dst) FROM knows k1 "
                "JOIN knows k2 ON k1.dst=k2.src "
                "JOIN knows k3 ON k2.dst=k3.src "
                "JOIN knows k4 ON k3.dst=k4.src WHERE k1.src=%s", (ids[i],))
            c.fetchall()

        def five_hop(i):
            c.execute(
                "SELECT count(DISTINCT k5.dst) FROM knows k1 "
                "JOIN knows k2 ON k1.dst=k2.src "
                "JOIN knows k3 ON k2.dst=k3.src "
                "JOIN knows k4 ON k3.dst=k4.src "
                "JOIN knows k5 ON k4.dst=k5.src WHERE k1.src=%s", (ids[i],))
            c.fetchall()

        def shortest_path(i):
            src, dst = pairs[i]
            c.execute(
                "WITH RECURSIVE bfs(node, depth) AS ("
                "  SELECT %s::int, 0"
                "  UNION ALL"
                "  SELECT k.dst, b.depth+1 FROM bfs b "
                "    JOIN knows k ON k.src=b.node WHERE b.depth < 7"
                ") SELECT min(depth) FROM bfs WHERE node=%s",
                (src, dst))
            c.fetchall()

        fns = {"point_lookup": point_lookup,
               "three_hop": three_hop, "four_hop": four_hop,
               "five_hop": five_hop,
               "shortest_path": shortest_path}
        for key, _desc in bc.OPERATIONS:
            print(f"Running {key}...")
            results[key] = bc.time_op(fns[key])
            print(f"  {results[key]}")
    conn.close()
    bc.save_result("postgresql", results)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "bench"
    if mode == "load":
        load()
    else:
        bench()


if __name__ == "__main__":
    main()
