# Neo4j / PostgreSQL / Cosmos DB Graph Performance Benchmark

This repository benchmarks three graph-friendly data stores on the same synthetic social graph workload:

- Neo4j Community Edition on an Azure VM
- Azure Database for PostgreSQL Flexible Server
- Azure Cosmos DB Gremlin API

The goal is to compare how each engine behaves for graph workloads that matter in practice: point lookups, 1-hop/2-hop/3-hop traversals, and shortest-path queries.

## What Was Tested

- Data set: 100,000 nodes and 1,000,000 edges
- Workload: synthetic social graph with skewed hubs
- Client side: all benchmarks were executed from the same Azure VM in `centralus` to keep network conditions consistent
- Iterations: 200 measured runs per operation, after warmup

The raw benchmark outputs and generated summary are in `results/`:

- `results/result_neo4j.json`
- `results/result_postgresql.json`
- `results/result_cosmos_gremlin.json`
- `results/REPORT.md`

## Test Flow

1. Provision Azure resources:
   - Neo4j VM
   - PostgreSQL Flexible Server
   - Cosmos DB Gremlin account and graph container
2. Generate the synthetic graph data locally.
3. Load the same logical graph into each engine.
4. Run the benchmark suite for the five operations below:
   - point lookup
   - 1-hop neighbors
   - 2-hop count
   - 3-hop count
   - shortest path (up to 5 hops)
5. Aggregate the results into a comparison report.

## Key Results

### P50 latency in milliseconds

| Operation | Neo4j Community | PostgreSQL Flexible | Cosmos DB Gremlin |
|---|---:|---:|---:|
| Point lookup (by id) | 2.37 | 0.18 | 5.53 |
| 1-hop neighbors | 2.57 | 0.21 | 14.41 |
| 2-hop count (FoF) | 2.10 | 0.43 | 33.50 |
| 3-hop count | 2.51 | 1.28 | 134.93 |
| Shortest path (<=5) | 1.97 | 138.63 | 10631.36 |

### Main takeaway

- PostgreSQL was fastest for point lookups and shallow traversals.
- Neo4j was dramatically faster for shortest-path queries and stayed stable as traversal depth increased.
- Cosmos DB Gremlin worked correctly, but it was much slower for traversal-heavy workloads, especially shortest path.

## Reproduce

The main scripts are under `benchmark/` and `infra/`.

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

When you are done, delete all billable Azure resources:

```bash
bash infra/teardown.sh
```
