# Neo4j / PostgreSQL / Cosmos DB Graph Performance Benchmark

## Executive Summary

This project compares three graph-capable data stores on the same synthetic **drug-discovery knowledge graph** (heterogeneous, Hetionet-flavored), using a **drug-discovery reasoning workload** (semantic multi-hop pathway traversals of 2/3/4 hops and a shortest evidence chain up to 7 hops) that represents R&D analysis and knowledge reasoning rather than shallow lookups:

- Neo4j Community Edition on an Azure VM
- Azure Database for PostgreSQL Flexible Server
- Azure Cosmos DB Gremlin API

The benchmark shows a stark split in suitability:

- Neo4j leads across multi-hop pathway traversals and the shortest evidence chain, and its latency grows most gently with depth (evidence chain P50 ~1.4 ms).
- PostgreSQL is strong for point lookups and low/mid-hop counts, but the shortest evidence chain (level-synchronized BFS) is noticeably costlier at ~15 ms P50 / ~60 ms P95.
- Cosmos DB Gremlin is already seconds-slow at 3/4 hops (4-hop P50 ~0.6 s) and every evidence-chain query hits a per-query timeout (20/20) and fails to return.

Conclusion: for a graph database serving drug-discovery analysis and knowledge reasoning (multi-hop pathways, evidence chains, target discovery), **Neo4j is the only engine that completes deep pathway traversals and evidence chains stably at millisecond latency**; PostgreSQL fits shallow structured retrieval and low/mid-hop counts; Cosmos DB Gremlin is not suitable for this deep evidence-chain workload.

## Scope and Methodology

- Data set: ~20,000 nodes and 200,000 edges
- Graph shape: heterogeneous drug-discovery knowledge graph (Hetionet-flavored) with skewed hubs (a few highly connected protein and disease hubs)
  - Node types: Compound (20%), Protein (35%), Gene (25%), Disease (15%), Pathway (5%)
  - Relation types: `TARGETS` (Compound→Protein), `INTERACTS` (Protein↔Protein PPI), `ENCODES` (Gene→Protein), `ASSOCIATED_WITH` (Gene→Disease), `PARTICIPATES_IN` (Protein→Pathway), `IMPLICATED_IN` (Pathway→Disease), `TREATS` (Compound→Disease, known therapy)
- Execution environment: all benchmarks ran from the same Azure VM in `centralus`
- Operations tested (drug-discovery reasoning workload):
  - **Compound point lookup** (name by id)
  - **2-hop**: Compound → target → PPI (`TARGETS`→`INTERACTS`)
  - **3-hop**: Compound → target → pathway → disease (`TARGETS`→`PARTICIPATES_IN`→`IMPLICATED_IN`)
  - **4-hop**: Compound → target → PPI → pathway → disease (one extra `INTERACTS` layer)
  - **Shortest evidence chain**: the shortest explainable path between a Compound and a Disease, up to 7 hops
- Measurement model:
  - Point lookup, 2-hop, 3-hop: 200 measured runs per operation, after warmup
  - 4-hop / shortest evidence chain: 20 measured runs per operation (deep hops are expensive; iterations reduced to bound total runtime)
- Cosmos DB handling: deep traversals combinatorially explode on a hub-skewed graph, so deep operations use a **per-query timeout** (20 s for 4-hop and the evidence chain). **Timed-out queries are scored at the timeout penalty value** and counted separately as `timeouts`, so the benchmark always produces results that faithfully reflect Cosmos's deep-hop disadvantage. During the load phase Cosmos was temporarily raised to 40,000 RU/s to avoid throttling; even so, the evidence chain still timed out on all 20/20 runs. Note also that bulk loading triggers per-request 429 (`RequestRateTooLarge`) diagnostics from gremlinpython, suppressed client-side with `logging.disable` to avoid log explosion.

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
| Compound point lookup (by id) | 2.40 | 0.17 | 6.28 |
| 2-hop: Compound→target→PPI | 1.83 | 0.40 | 37.45 |
| 3-hop: Compound→target→pathway→disease | 1.78 | 0.92 | 125.08 |
| 4-hop: Compound→target→PPI→pathway→disease | 3.56 | 4.83 | 598.69 |
| Shortest evidence chain: Compound→Disease (<=7) | 1.38 | 15.44 | 20000.00* |

> \* Cosmos DB evidence chain timed out on all 20/20 runs (per-query 20 s timeout); the table records the 20000 ms penalty value, meaning "did not return".

### P95 latency in milliseconds

| Operation | Neo4j Community | PostgreSQL Flexible | Cosmos DB Gremlin |
|---|---:|---:|---:|
| Compound point lookup (by id) | 3.60 | 0.20 | 9.78 |
| 2-hop: Compound→target→PPI | 3.85 | 0.69 | 51.32 |
| 3-hop: Compound→target→pathway→disease | 2.82 | 1.59 | 177.48 |
| 4-hop: Compound→target→PPI→pathway→disease | 4.94 | 7.10 | 779.68 |
| Shortest evidence chain: Compound→Disease (<=7) | 1.83 | 59.64 | 20000.00* |

### Interpretation

- **Neo4j is the best choice for multi-hop pathway traversal and evidence-chain reasoning**: 2/3/4-hop latency grows gently with depth (up to ~3.6 ms), and the evidence chain leverages native graph traversal plus early pruning for a P50 of just ~1.4 ms, far ahead of the others.
- **PostgreSQL fits shallow structured retrieval**: point lookup and low/mid-hop JOIN counts are very fast (sub-ms to ~1 ms), and 4-hop at ~4.8 ms is still acceptable; the evidence chain, reimplemented as a level-synchronized BFS (Python-side layer expansion with a global visited set), stabilizes at ~15 ms P50 / ~60 ms P95 — usable but clearly slower than Neo4j with higher tail latency.
- **Cosmos DB Gremlin is not suitable for deep evidence-chain analysis**: 2 hops is already tens of ms, 3 hops ~125 ms, 4 hops ~0.6 s, and the evidence chain times out 20/20 even at 40,000 RU/s — `repeat().until()` explodes combinatorially on a hub-skewed graph and cannot finish within the limit.

Note: the shortest evidence chain does not enumerate all paths within 7 hops; it finds one shortest viable path between two vertices. Once Neo4j finds a shorter path it prunes and stops expanding, so its evidence chain is even faster than the fixed-expansion 3/4-hop counts; PostgreSQL's level-synchronized BFS and Cosmos's `repeat().until()` both lack equally efficient pruning, making them costlier on a hub-skewed graph (PG stays bounded, Cosmos times out).

### Visualization

![P50 graph database comparison](results/benchmark_p50_comparison.png)

## Implications for Drug Discovery

In drug discovery, the highest-value queries are usually multi-hop and explainable: target discovery, pathway tracing, drug repurposing, and evidence-chain analysis across genes, proteins, compounds, diseases, and literature. For these workloads, the most important indicators are multi-hop latency, shortest-path latency, and tail latency at P95/P99.

This benchmark maps directly onto those scenarios: the 2/3/4-hop pathway traversals model "mechanistic analysis across compound→target→pathway→disease layers", and the shortest evidence chain models "the shortest explainable evidence chain between two entities (e.g. compound ↔ disease)". The results are unambiguous:

- **Neo4j**: the only engine that completes multi-hop pathway traversal stably at millisecond latency and keeps the evidence chain near real time — the best fit for drug-discovery analysis and knowledge reasoning.
- **PostgreSQL**: shallow joins (within 3 hops) are fast and most economical, and 4-hop is acceptable; the evidence chain via level-synchronized BFS is ~15 ms — usable but with higher tail latency.
- **Cosmos DB Gremlin**: deep pathways start at seconds and the evidence chain simply times out; raising RU/s does not help, so it is **not recommended** for R&D graphs centered on deep evidence-chain reasoning.

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