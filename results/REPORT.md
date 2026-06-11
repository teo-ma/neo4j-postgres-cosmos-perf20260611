# Graph DB Performance Comparison

Workload: synthetic social graph. All engines run the same logical operations on identical data.

Compute: ~4 vCPU / 16 GB class for each engine.


## P50 (MS)

| Operation | Neo4j Community (VM) | PostgreSQL Flexible | Cosmos DB (Gremlin) |
|---|---|---|---|
| Point lookup (by id) | 2.37 | 0.18 | 5.53 |
| 1-hop neighbors | 2.57 | 0.21 | 14.41 |
| 2-hop count (FoF) | 2.10 | 0.43 | 33.50 |
| 3-hop count | 2.51 | 1.28 | 134.93 |
| Shortest path (<=5) | 1.97 | 138.63 | 10631.36 |

## P95 (MS)

| Operation | Neo4j Community (VM) | PostgreSQL Flexible | Cosmos DB (Gremlin) |
|---|---|---|---|
| Point lookup (by id) | 4.26 | 0.21 | 25.78 |
| 1-hop neighbors | 3.59 | 0.29 | 22.01 |
| 2-hop count (FoF) | 3.08 | 0.52 | 46.79 |
| 3-hop count | 3.76 | 2.04 | 211.41 |
| Shortest path (<=5) | 2.81 | 211.43 | 15669.98 |

## MEAN (MS)

| Operation | Neo4j Community (VM) | PostgreSQL Flexible | Cosmos DB (Gremlin) |
|---|---|---|---|
| Point lookup (by id) | 2.57 | 0.18 | 10.13 |
| 1-hop neighbors | 2.55 | 0.23 | 15.42 |
| 2-hop count (FoF) | 2.13 | 0.44 | 33.72 |
| 3-hop count | 2.62 | 1.36 | 137.69 |
| Shortest path (<=5) | 2.05 | 136.76 | 10582.41 |

## Fastest engine per operation (by P50)

| Operation | Winner | P50 (ms) |
|---|---|---|
| Point lookup (by id) | PostgreSQL Flexible | 0.18 |
| 1-hop neighbors | PostgreSQL Flexible | 0.21 |
| 2-hop count (FoF) | PostgreSQL Flexible | 0.43 |
| 3-hop count | PostgreSQL Flexible | 1.28 |
| Shortest path (<=5) | Neo4j Community (VM) | 1.97 |
