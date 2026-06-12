#!/usr/bin/env python3
"""Cosmos DB (Gremlin API) benchmark: load graph + run shared workload.

Env: COSMOS_HOST (e.g. <acct>.gremlin.cosmos.azure.com), COSMOS_KEY,
COSMOS_DB, COSMOS_GRAPH, plus standard benchmark vars.
Usage:
  python3 bench_cosmos.py load
  python3 bench_cosmos.py bench
"""
import asyncio
import csv
import os
import queue
import sys
import threading
import time

from gremlin_python.driver import client, serializer

import bench_common as bc

HOST = os.environ["COSMOS_HOST"]
KEY = os.environ["COSMOS_KEY"]
DB = os.environ.get("COSMOS_DB", "graphdb")
GRAPH = os.environ.get("COSMOS_GRAPH", "social")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOAD_THREADS = int(os.environ.get("COSMOS_LOAD_THREADS", "32"))


def _ensure_event_loop():
    """gremlinpython's aiohttp transport needs an event loop bound to the current thread."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def make_client():
    _ensure_event_loop()
    return client.Client(
        f"wss://{HOST}:443/", "g",
        username=f"/dbs/{DB}/colls/{GRAPH}",
        password=KEY,
        message_serializer=serializer.GraphSONSerializersV2d0(),
    )


def _submit(c, query, bindings=None):
    return c.submit(query, bindings or {}).all().result()


def load():
    # Partition key strategy: pk = id % 100 to spread across partitions.
    persons = []
    with open(os.path.join(DATA_DIR, "persons.csv")) as f:
        for r in csv.DictReader(f):
            persons.append(r)
    edges = []
    with open(os.path.join(DATA_DIR, "knows.csv")) as f:
        for e in csv.DictReader(f):
            edges.append(e)

    print(f"Loading {len(persons)} vertices with {LOAD_THREADS} threads...")
    t0 = time.time()

    def vertex_query(c, r):
        pk = int(r["id"]) % 100
        q = ("g.addV('person').property('id', vid).property('pk', pk)"
             ".property('name', name).property('age', age)"
             ".property('city', city)")
        _submit(c, q, {"vid": str(r["id"]), "pk": str(pk),
                       "name": r["name"], "age": int(r["age"]),
                       "city": r["city"]})

    _run_pool(vertex_query, persons, "vertices")
    print(f"Vertices loaded in {time.time()-t0:.1f}s")

    print(f"Loading {len(edges)} edges...")
    t0 = time.time()

    def edge_query(c, e):
        q = ("g.V().has('person','id',src)"
             ".addE('knows').to(g.V().has('person','id',dst))"
             ".property('since', since)")
        _submit(c, q, {"src": str(e["src"]), "dst": str(e["dst"]),
                       "since": int(e["since"])})

    _run_pool(edge_query, edges, "edges")
    print(f"Edges loaded in {time.time()-t0:.1f}s")


def _run_pool(op, items, label):
    """Run op(client, item) across LOAD_THREADS persistent clients."""
    q = queue.Queue()
    for it in items:
        q.put(it)
    total = len(items)
    counters = {"done": 0, "errors": 0}
    lock = threading.Lock()

    def worker():
        c = make_client()
        try:
            while True:
                try:
                    it = q.get_nowait()
                except queue.Empty:
                    return
                ok = _retry(op, c, it)
                with lock:
                    counters["done"] += 1
                    if not ok:
                        counters["errors"] += 1
                    d = counters["done"]
                if d % 20000 == 0:
                    print(f"  {d}/{total} {label} (errors={counters['errors']})")
                q.task_done()
        finally:
            c.close()

    threads = [threading.Thread(target=worker) for _ in range(LOAD_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"  total {label}: {counters['done']}, errors: {counters['errors']}")


def _retry(op, c, item, attempts=6):
    for a in range(attempts):
        try:
            op(c, item)
            return True
        except Exception:
            time.sleep(0.05 * (2 ** a))
    return False


def bench():
    ids = bc.sample_ids(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    pairs = bc.sample_pairs(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    c = make_client()
    results = {}
    try:
        def point_lookup(i):
            _submit(c, "g.V().has('person','id',vid).values('name')",
                    {"vid": str(ids[i])})

        def three_hop(i):
            _submit(c, "g.V().has('person','id',vid).out('knows')"
                       ".out('knows').out('knows').dedup().count()",
                    {"vid": str(ids[i])})

        def four_hop(i):
            _submit(c, "g.V().has('person','id',vid).out('knows')"
                       ".out('knows').out('knows').out('knows').dedup().count()",
                    {"vid": str(ids[i])})

        def five_hop(i):
            _submit(c, "g.V().has('person','id',vid).out('knows')"
                       ".out('knows').out('knows').out('knows').out('knows')"
                       ".dedup().count()",
                    {"vid": str(ids[i])})

        def shortest_path(i):
            src, dst = pairs[i]
            _submit(c, "g.V().has('person','id',s).repeat(out('knows').simplePath())"
                       ".until(has('id',d).or().loops().is(7)).has('id',d)"
                       ".path().limit(1).count(local)",
                    {"s": str(src), "d": str(dst)})

        fns = {
            "point_lookup": point_lookup,
            "three_hop": three_hop,
            "four_hop": four_hop,
            "five_hop": five_hop,
            "shortest_path": shortest_path,
        }
        for key, _desc in bc.OPERATIONS:
            print(f"Running {key}...")
            results[key] = bc.time_op(fns[key])
            print(f"  {results[key]}")
    finally:
        c.close()
    bc.save_result("cosmos_gremlin", results)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "bench"
    if mode == "load":
        load()
    else:
        bench()


if __name__ == "__main__":
    main()