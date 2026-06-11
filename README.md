# Neo4j / PostgreSQL / Cosmos DB Graph Performance Benchmark

## Executive Summary

This project compares three graph-capable data stores on the same synthetic social graph workload:

- Neo4j Community Edition on an Azure VM
- Azure Database for PostgreSQL Flexible Server
- Azure Cosmos DB Gremlin API

The benchmark shows a clear split in suitability:

- PostgreSQL is the fastest option for point lookups and shallow traversals.
- Neo4j is the strongest option for multi-hop traversal and shortest-path queries.
- Cosmos DB Gremlin is functional for graph storage, but it is much slower on traversal-heavy workloads.

For reporting purposes, the most relevant metric is not the single fastest query, but how the engine behaves as traversal depth increases and whether tail latency remains stable.

## Scope and Methodology

- Data set: 100,000 nodes and 1,000,000 edges
- Graph shape: synthetic social graph with skewed hubs
- Execution environment: all benchmarks ran from the same Azure VM in `centralus`
- Measurement model: 200 measured runs per operation, after warmup
- Operations tested: point lookup, 1-hop neighbors, 2-hop count, 3-hop count, shortest path up to 5 hops

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
| Point lookup (by id) | 2.37 | 0.18 | 5.53 |
| 1-hop neighbors | 2.57 | 0.21 | 14.41 |
| 2-hop count (FoF) | 2.10 | 0.43 | 33.50 |
| 3-hop count | 2.51 | 1.28 | 134.93 |
| Shortest path (<=5) | 1.97 | 138.63 | 10631.36 |

### Interpretation

- PostgreSQL performs best when the workload is dominated by indexed entity lookups and shallow joins.
- Neo4j maintains low and stable latency as traversal depth grows, which is the key requirement for interactive graph exploration.
- Cosmos DB Gremlin incurs significant overhead for traversal-heavy queries, especially shortest path, where network and distributed execution costs dominate.

### Visualization

![P50 graph database comparison](results/benchmark_p50_comparison.png)

## Implications for Drug Discovery

In drug discovery, the highest-value queries are usually multi-hop and explainable: target discovery, pathway tracing, drug repurposing, and evidence-chain analysis across genes, proteins, compounds, diseases, and literature. For these workloads, the most important indicators are multi-hop latency, shortest-path latency, and tail latency at P95/P99.

Practical reading of this benchmark:

- Neo4j is the best fit when graph traversal and path explanation are part of the core analysis workflow.
- PostgreSQL is appropriate for structured lookups, light relationship navigation, and broader relational support.
- Cosmos DB Gremlin is a better fit for managed, distributed access patterns than for latency-sensitive research exploration.

## Reproducibility

Main scripts:

- `benchmark/generate_data.py` generates the data set
- `benchmark/bench_neo4j.py` loads and benchmarks Neo4j
- `benchmark/bench_postgres.py` loads and benchmarks PostgreSQL
- `benchmark/bench_cosmos.py` loads and benchmarks Cosmos Gremlin
- `benchmark/make_report.py` builds `results/REPORT.md`

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
