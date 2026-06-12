# Graph DB Performance Comparison — Drug-Discovery Knowledge Graph

Workload: synthetic drug-discovery knowledge graph (Hetionet-style, ~20,000 nodes / 200,000 edges). All engines run the same logical operations on identical data.

Compute: ~4 vCPU / 16 GB class for each engine.


## P50 (MS)

| Operation | Neo4j Community (VM) | PostgreSQL Flexible | Cosmos DB (Gremlin) |
|---|---|---|---|
| Compound point lookup | 2.40 | 0.17 | 6.28 |
| Compound->target->PPI (2-hop) | 1.83 | 0.40 | 37.45 |
| Compound->target->pathway->disease (3-hop) | 1.78 | 0.92 | 125.08 |
| Compound->target->PPI->pathway->disease (4-hop) | 3.56 | 4.83 | 598.69 |
| Shortest evidence chain Compound->Disease (<=7) | 1.38 | 15.44 | 20000.00 |

## P95 (MS)

| Operation | Neo4j Community (VM) | PostgreSQL Flexible | Cosmos DB (Gremlin) |
|---|---|---|---|
| Compound point lookup | 3.60 | 0.20 | 9.78 |
| Compound->target->PPI (2-hop) | 3.85 | 0.69 | 51.32 |
| Compound->target->pathway->disease (3-hop) | 2.82 | 1.59 | 177.48 |
| Compound->target->PPI->pathway->disease (4-hop) | 4.94 | 7.10 | 779.68 |
| Shortest evidence chain Compound->Disease (<=7) | 1.83 | 59.64 | 20000.00 |

## MEAN (MS)

| Operation | Neo4j Community (VM) | PostgreSQL Flexible | Cosmos DB (Gremlin) |
|---|---|---|---|
| Compound point lookup | 2.51 | 0.17 | 11.12 |
| Compound->target->PPI (2-hop) | 2.25 | 0.54 | 38.21 |
| Compound->target->pathway->disease (3-hop) | 1.89 | 1.01 | 125.73 |
| Compound->target->PPI->pathway->disease (4-hop) | 3.68 | 4.87 | 597.50 |
| Shortest evidence chain Compound->Disease (<=7) | 1.45 | 20.14 | 20000.00 |

## Fastest engine per operation (by P50)

| Operation | Winner | P50 (ms) |
|---|---|---|
| Compound point lookup | PostgreSQL Flexible | 0.17 |
| Compound->target->PPI (2-hop) | PostgreSQL Flexible | 0.40 |
| Compound->target->pathway->disease (3-hop) | PostgreSQL Flexible | 0.92 |
| Compound->target->PPI->pathway->disease (4-hop) | Neo4j Community (VM) | 3.56 |
| Shortest evidence chain Compound->Disease (<=7) | Neo4j Community (VM) | 1.38 |
