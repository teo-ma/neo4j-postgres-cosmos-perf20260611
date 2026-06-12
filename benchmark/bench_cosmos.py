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
import logging
import os
import queue
import sys
import threading
import time

from gremlin_python.driver import client, serializer

import bench_common as bc

# Bulk loads provoke a flood of 429 (RequestRateTooLarge) responses that the
# gremlinpython client logs verbatim with full diagnostics, producing gigabytes
# of noise. _retry() already handles throttling, so silence client logging.
logging.disable(logging.CRITICAL)

HOST = os.environ["COSMOS_HOST"]
KEY = os.environ["COSMOS_KEY"]
DB = os.environ.get("COSMOS_DB", "graphdb")
GRAPH = os.environ.get("COSMOS_GRAPH", "social")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOAD_THREADS = int(os.environ.get("COSMOS_LOAD_THREADS", "32"))

# Deep-hop traversals on a hub-skewed graph can fan out combinatorially and
# never return on Cosmos Gremlin. Bound them with a per-query timeout and a
# smaller iteration count so the benchmark always produces results; a timed-out
# query is recorded at the timeout value as a penalty latency.
SHALLOW_TIMEOUT = float(os.environ.get("COSMOS_SHALLOW_TIMEOUT", "30"))
DEEP_TIMEOUT = float(os.environ.get("COSMOS_DEEP_TIMEOUT", "20"))
DEEP_ITERS = int(os.environ.get("COSMOS_DEEP_ITERS", "20"))
DEEP_WARMUP = int(os.environ.get("COSMOS_DEEP_WARMUP", "2"))


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


def _submit_timed(c, query, bindings, timeout):
    """Submit a query and wait at most `timeout` seconds for full results."""
    fut = c.submitAsync(query, bindings or {})
    rs = fut.result(timeout=timeout)
    return rs.all().result(timeout=timeout)


def _timed_op(fn, iterations, warmup, timeout):
    """Run fn(i); record latency in ms. A timeout/error counts as a penalty
    latency equal to `timeout` and is tallied separately."""
    for i in range(warmup):
        try:
            fn(i)
        except Exception:
            pass
    lat = []
    timeouts = 0
    for i in range(iterations):
        t0 = time.perf_counter()
        try:
            fn(i)
            lat.append((time.perf_counter() - t0) * 1000.0)
        except Exception:
            timeouts += 1
            lat.append(timeout * 1000.0)
    stats = bc.percentiles(lat)
    stats["timeouts"] = timeouts
    return stats


def load():
    # Partition key strategy: pk = id % 100 to spread across partitions.
    nodes = []
    with open(os.path.join(DATA_DIR, "nodes.csv")) as f:
        for r in csv.DictReader(f):
            nodes.append(r)
    edges = []
    with open(os.path.join(DATA_DIR, "edges.csv")) as f:
        for e in csv.DictReader(f):
            edges.append(e)

    print(f"Loading {len(nodes)} vertices with {LOAD_THREADS} threads...")
    t0 = time.time()

    def vertex_query(c, r):
        pk = int(r["id"]) % 100
        q = ("g.addV(vlabel).property('id', vid).property('pk', pk)"
             ".property('name', name)")
        _submit(c, q, {"vlabel": r["type"], "vid": str(r["id"]),
                       "pk": str(pk), "name": r["name"]})

    _run_pool(vertex_query, nodes, "vertices")
    print(f"Vertices loaded in {time.time()-t0:.1f}s")

    print(f"Loading {len(edges)} edges...")
    t0 = time.time()

    def edge_query(c, e):
        q = ("g.V().has('id',src)"
             ".addE(rel).to(g.V().has('id',dst))")
        _submit(c, q, {"src": str(e["src"]), "dst": str(e["dst"]),
                       "rel": e["rel"]})

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
    cids = bc.sample_compounds(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    pairs = bc.sample_evidence_pairs(bc.NUM_NODES, bc.ITERATIONS + bc.WARMUP)
    c = make_client()
    results = {}
    try:
        def point_lookup(i):
            _submit_timed(c, "g.V().has('id',vid).values('name')",
                          {"vid": str(cids[i])}, SHALLOW_TIMEOUT)

        def targets_2hop(i):
            _submit_timed(c, "g.V().has('id',vid).out('TARGETS')"
                             ".out('INTERACTS').dedup().count()",
                          {"vid": str(cids[i])}, SHALLOW_TIMEOUT)

        def pathway_3hop(i):
            _submit_timed(c, "g.V().has('id',vid).out('TARGETS')"
                             ".out('PARTICIPATES_IN').out('IMPLICATED_IN')"
                             ".dedup().count()",
                          {"vid": str(cids[i])}, SHALLOW_TIMEOUT)

        def reach_4hop(i):
            _submit_timed(c, "g.V().has('id',vid).out('TARGETS').out('INTERACTS')"
                             ".out('PARTICIPATES_IN').out('IMPLICATED_IN')"
                             ".dedup().count()",
                          {"vid": str(cids[i])}, DEEP_TIMEOUT)

        def evidence_path(i):
            src, dst = pairs[i]
            _submit_timed(c, "g.V().has('id',s).repeat(out().simplePath())"
                             ".until(has('id',d).or().loops().is(7)).has('id',d)"
                             ".path().limit(1).count(local)",
                          {"s": str(src), "d": str(dst)}, DEEP_TIMEOUT)

        # (function, iterations, warmup, timeout) per operation. Deep traversals
        # use fewer iterations + a tighter timeout so the run stays bounded.
        cfg = {
            "point_lookup": (point_lookup, bc.ITERATIONS, bc.WARMUP, SHALLOW_TIMEOUT),
            "targets_2hop": (targets_2hop, bc.ITERATIONS, bc.WARMUP, SHALLOW_TIMEOUT),
            "pathway_3hop": (pathway_3hop, bc.ITERATIONS, bc.WARMUP, SHALLOW_TIMEOUT),
            "reach_4hop": (reach_4hop, DEEP_ITERS, DEEP_WARMUP, DEEP_TIMEOUT),
            "evidence_path": (evidence_path, DEEP_ITERS, DEEP_WARMUP, DEEP_TIMEOUT),
        }
        for key, _desc in bc.OPERATIONS:
            fn, iters, warm, timeout = cfg[key]
            print(f"Running {key} (iters={iters}, timeout={timeout}s)...", flush=True)
            results[key] = _timed_op(fn, iters, warm, timeout)
            print(f"  {results[key]}", flush=True)
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