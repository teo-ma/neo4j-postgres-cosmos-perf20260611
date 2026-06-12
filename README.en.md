# Neo4j / PostgreSQL / Cosmos DB Graph Performance Benchmark

## Executive Summary

This project compares three graph-capable data stores on the same synthetic social graph, using a **deep-hop analytical workload** (3/4/5-hop traversals and shortest path up to 7 hops) that represents R&D analysis and knowledge reasoning rather than shallow lookups:

- Neo4j Community Edition on an Azure VM
- Azure Database for PostgreSQL Flexible Server
- Azure Cosmos DB Gremlin API

The benchmark shows a stark split in suitability:

- Neo4j leads across deep traversals and shortest path, and its latency grows most gently with depth (shortest path P50 ~2 ms).
- PostgreSQL is strong for point lookups and low/mid-hop counts, but recursive shortest path (BFS) collapses to ~14 s P50.
- Cosmos DB Gremlin is already seconds-slow at 4/5 hops (5-hop P50 ~7.8 s) and every shortest-path query hits a server-side 60 s timeout and fails to return.

Conclusion: for a graph database serving R&D analysis and knowledge reasoning (multi-hop paths, evidence chains, pathway tracing), **Neo4j is the only engine that completes deep traversals stably within acceptable latency**; PostgreSQL fits shallow structured retrieval; Cosmos DB Gremlin is not suitable for this deep-hop workload.

## Scope and Methodology

- Data set: 100,000 nodes and 1,000,000 edges
- Graph shape: synthetic social graph with skewed hubs (mimics a few highly connected entities in an R&D knowledge graph)
- Execution environment: all benchmarks ran from the same Azure VM in `centralus`
- Operations tested (deep-hop workload): point lookup, 3-hop count, 4-hop count, 5-hop count, shortest path up to 7 hops
- Measurement model:
  - Point lookup and 3-hop: 200 measured runs per operation, after warmup
  - 4-hop / 5-hop / shortest path: 20 measured runs per operation (deep hops are extremely expensive; iterations reduced to bound total runtime)
- Cosmos DB handling: deep traversals combinatorially explode on a hub-skewed graph, so deep operations use a **per-query timeout** (20 s for 4/5-hop and shortest path). **Timed-out queries are scored at the timeout penalty value** and counted separately as `timeouts`, so the benchmark always produces results that faithfully reflect Cosmos's deep-hop disadvantage. During this run Cosmos was provisioned at 100,000 RU/s (well past any throttling bottleneck); shortest path still timed out on all 20/20 runs with a server-side `GraphTimeoutException` (60 s).

Generated outputs and the full result report are stored in `results/`:

- `results/result_neo4j.json`
- `results/result_postgresql.json`
- `results/result_cosmos_gremlin.json`
- `results/REPORT.md`
- `results/benchmark_p50_comparison.png`

## Results Summary

### P50 latency in milliseconds

| Operation | Neo4j Community | PostgreSQL Flexible | Cosmos DB Gremlin |
|---|---:|---:|---:|
| Point lookup (by id) | 6.72 | 0.16 | 6.48 |
| 3-hop count | 3.31 | 1.19 | 141.20 |
| 4-hop count | 8.87 | 7.85 | 1025.99 |
| 5-hop count | 58.40 | 78.67 | 7840.78 |
| Shortest path (<=7) | 1.98 | 13929.52 | 20000.00* |

> \* Cosmos DB shortest path timed out on all 20/20 runs (server-side 60 s `GraphTimeoutException`); the table records the 20000 ms penalty value, meaning "did not return".

### P95 latency in milliseconds

| Operation | Neo4j Community | PostgreSQL Flexible | Cosmos DB Gremlin |
|---|---:|---:|---:|
| Point lookup (by id) | 17.66 | 0.21 | 32.27 |
| 3-hop count | 5.48 | 1.70 | 219.32 |
| 4-hop count | 13.30 | 12.44 | 1690.17 |
| 5-hop count | 86.68 | 122.32 | 11441.93 |
| Shortest path (<=7) | 3.62 | 21406.21 | 20000.00* |

### Interpretation

- **Neo4j is the best choice for deep traversal and path reasoning**: 3/4/5-hop latency grows gently with depth (3→58 ms), and shortest path leverages native graph traversal plus early pruning for a P50 of just ~2 ms, far ahead of the others.
- **PostgreSQL fits shallow structured retrieval**: point lookup and low/mid-hop JOIN counts are very fast, but shortest path relies on a recursive CTE (BFS) that branches explosively on a hub-skewed graph, reaching ~14 s P50 — unsuitable for interactive path queries.
- **Cosmos DB Gremlin is not suitable for deep-hop analysis**: 4 hops is already ~1 s P50, 5 hops ~7.8 s, and shortest path times out 20/20 even at 100,000 RU/s — a single query consumes ~300k RU yet still cannot finish within 60 s.

Note: shortest path does not enumerate all paths within 7 hops; it finds one shortest viable path between two vertices. Once Neo4j finds a shorter path it prunes and stops expanding, so its shortest path is even faster than the fixed-expansion 3/4/5-hop counts; PostgreSQL's recursive BFS and Cosmos's `repeat().until()` both lack equally efficient pruning, making them extremely expensive on a hub-skewed graph.

### Visualization

![P50 graph database comparison](results/benchmark_p50_comparison.png)

## Implications for Drug Discovery

In drug discovery, the highest-value queries are usually multi-hop and explainable: target discovery, pathway tracing, drug repurposing, and evidence-chain analysis across genes, proteins, compounds, diseases, and literature. For these workloads, the most important indicators are multi-hop latency, shortest-path latency, and tail latency at P95/P99.

This deep-hop benchmark maps directly onto those scenarios: 4/5-hop counts model "impact-radius analysis across many relationship layers", and shortest path models "the shortest evidence chain between two entities (e.g. compound ↔ disease)". The results are unambiguous:

- **Neo4j**: the only engine that completes deep traversal stably at ms-to-tens-of-ms and keeps shortest path near real time — the best fit for R&D analysis and knowledge reasoning.
- **PostgreSQL**: shallow joins (within 3 hops) are fast and most economical, but shortest path reaches tens of seconds, unsuitable for interactive path reasoning.
- **Cosmos DB Gremlin**: deep traversal starts at seconds and shortest path simply times out; raising RU/s sharply does not help, so it is **not recommended** for R&D graphs centered on deep path reasoning.

## Reproducibility

Main scripts:

- `benchmark/generate_data.py` generates the data set
- `benchmark/bench_neo4j.py` loads and benchmarks Neo4j
- `benchmark/bench_postgres.py` loads and benchmarks PostgreSQL
- `benchmark/bench_cosmos.py` loads and benchmarks Cosmos Gremlin
- `benchmark/make_report.py` builds `results/REPORT.md`
- `benchmark/make_plot.py` builds `results/benchmark_p50_comparison.png` (log-scale P50 comparison)

Infrastructure helpers:

- `infra/provision_neo4j_vm.sh`
- `infra/provision_postgres.sh`
- `infra/provision_cosmos.sh`
- `infra/ssh_vm.sh`
- `infra/teardown.sh`

## Cleanup

When the comparison is no longer needed, delete the Azure resources to stop billing:

```bash
bash infra/teardown.sh
```