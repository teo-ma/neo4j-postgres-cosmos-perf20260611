# Graph DB Performance Comparison

Workload: synthetic social graph. All engines run the same logical operations on identical data.

Compute: ~4 vCPU / 16 GB class for each engine.


## P50 (MS)

| Operation | Neo4j Community (VM) | PostgreSQL Flexible | Cosmos DB (Gremlin) |
|---|---|---|---|
| Point lookup (by id) | 6.72 | 0.16 | 6.48 |
| 3-hop count | 3.31 | 1.19 | 141.20 |
| 4-hop count | 8.87 | 7.85 | 1025.99 |
| 5-hop count | 58.40 | 78.67 | 7840.78 |
| Shortest path (<=7) | 1.98 | 13929.52 | 20000.00 |

## P95 (MS)

| Operation | Neo4j Community (VM) | PostgreSQL Flexible | Cosmos DB (Gremlin) |
|---|---|---|---|
| Point lookup (by id) | 17.66 | 0.21 | 32.27 |
| 3-hop count | 5.48 | 1.70 | 219.32 |
| 4-hop count | 13.30 | 12.44 | 1690.17 |
| 5-hop count | 86.68 | 122.32 | 11441.93 |
| Shortest path (<=7) | 3.62 | 21406.21 | 20000.00 |

## MEAN (MS)

| Operation | Neo4j Community (VM) | PostgreSQL Flexible | Cosmos DB (Gremlin) |
|---|---|---|---|
| Point lookup (by id) | 7.88 | 0.19 | 12.26 |
| 3-hop count | 3.52 | 1.23 | 144.03 |
| 4-hop count | 9.07 | 8.02 | 1097.47 |
| 5-hop count | 59.01 | 79.88 | 8209.57 |
| Shortest path (<=7) | 2.57 | 13742.15 | 20000.00 |

## Fastest engine per operation (by P50)

| Operation | Winner | P50 (ms) |
|---|---|---|
| Point lookup (by id) | PostgreSQL Flexible | 0.16 |
| 3-hop count | PostgreSQL Flexible | 1.19 |
| 4-hop count | PostgreSQL Flexible | 7.85 |
| 5-hop count | Neo4j Community (VM) | 58.40 |
| Shortest path (<=7) | Neo4j Community (VM) | 1.98 |
