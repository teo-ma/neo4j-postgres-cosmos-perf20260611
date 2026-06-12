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
        c.execute("DROP TABLE IF EXISTS edges; DROP TABLE IF EXISTS nodes;")
        c.execute("CREATE TABLE nodes (id int PRIMARY KEY, type text, name text)")
        c.execute("CREATE TABLE edges (src int, dst int, rel text)")
        conn.commit()

        t0 = time.time()
        print("COPY nodes...")
        with open(os.path.join(DATA_DIR, "nodes.csv")) as f:
            c.copy_expert("COPY nodes(id,type,name) FROM STDIN WITH CSV HEADER", f)
        conn.commit()
        print(f"  nodes in {time.time()-t0:.1f}s")

        t0 = time.time()
        print("COPY edges...")
        with open(os.path.join(DATA_DIR, "edges.csv")) as f:
            c.copy_expert("COPY edges(src,dst,rel) FROM STDIN WITH CSV HEADER", f)
        conn.commit()
        print(f"  edges in {time.time()-t0:.1f}s")

        t0 = time.time()
        print("Creating indexes...")
        c.execute("CREATE INDEX idx_edges_src_rel ON edges(src, rel)")
        c.execute("CREATE INDEX idx_edges_src ON edges(src)")
        c.execute("CREATE INDEX idx_edges_dst ON edges(dst)")
        c.execute("CREATE INDEX idx_nodes_type ON nodes(type)")
        c.execute("ANALYZE nodes; ANALYZE edges;")
        conn.commit()
        print(f"  indexes in {time.time()-t0:.1f}s")
    conn.close()


def bench():
    cids = bc.sample_compounds(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    pairs = bc.sample_evidence_pairs(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    conn = connect()
    conn.autocommit = True
    results = {}
    with conn.cursor() as c:
        def point_lookup(i):
            c.execute("SELECT name FROM nodes WHERE id=%s", (cids[i],))
            c.fetchall()

        def targets_2hop(i):
            c.execute(
                "SELECT count(DISTINCT e2.dst) FROM edges e1 "
                "JOIN edges e2 ON e1.dst=e2.src "
                "WHERE e1.src=%s AND e1.rel='TARGETS' AND e2.rel='INTERACTS'",
                (cids[i],))
            c.fetchall()

        def pathway_3hop(i):
            c.execute(
                "SELECT count(DISTINCT e3.dst) FROM edges e1 "
                "JOIN edges e2 ON e1.dst=e2.src "
                "JOIN edges e3 ON e2.dst=e3.src "
                "WHERE e1.src=%s AND e1.rel='TARGETS' "
                "AND e2.rel='PARTICIPATES_IN' AND e3.rel='IMPLICATED_IN'",
                (cids[i],))
            c.fetchall()

        def reach_4hop(i):
            c.execute(
                "SELECT count(DISTINCT e4.dst) FROM edges e1 "
                "JOIN edges e2 ON e1.dst=e2.src "
                "JOIN edges e3 ON e2.dst=e3.src "
                "JOIN edges e4 ON e3.dst=e4.src "
                "WHERE e1.src=%s AND e1.rel='TARGETS' AND e2.rel='INTERACTS' "
                "AND e3.rel='PARTICIPATES_IN' AND e4.rel='IMPLICATED_IN'",
                (cids[i],))
            c.fetchall()

        def evidence_path(i):
            src, dst = pairs[i]
            # Level-synchronized BFS with a global visited set: expand the
            # frontier one hop at a time (one SQL round-trip per level) and
            # dedup against everything already seen. This visits each node at
            # most once, avoiding the exponential simple-path enumeration a
            # single recursive CTE would incur on a hub-skewed graph, while
            # still returning the true shortest hop count (<=7) like the
            # shortestPath/simplePath traversals on Neo4j and Cosmos.
            if src == dst:
                return
            visited = {src}
            frontier = [src]
            for _depth in range(1, 8):
                c.execute(
                    "SELECT DISTINCT dst FROM edges WHERE src = ANY(%s)",
                    (frontier,))
                nxt = [r[0] for r in c.fetchall() if r[0] not in visited]
                if not nxt:
                    break
                if dst in nxt:
                    break
                visited.update(nxt)
                frontier = nxt


        fns = {"point_lookup": point_lookup,
               "targets_2hop": targets_2hop, "pathway_3hop": pathway_3hop,
               "reach_4hop": reach_4hop,
               "evidence_path": evidence_path}
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
