# Neo4j / PostgreSQL / Cosmos DB 图数据库性能对比

## 项目结论

本项目在 Azure 上使用同一份合成社交图数据，对三种图相关存储方案进行了性能对比：

- Neo4j Community Edition，部署在 Azure VM 上
- Azure Database for PostgreSQL Flexible Server
- Azure Cosmos DB Gremlin API

本轮测试专门面向**研发分析与知识推理**场景，工作负载以**高跳数深度遍历**（3/4/5 跳）和**最短路径（最多 7 跳）**为主，而非浅层关联查询。结果显示三类数据库的适用场景差异巨大：

- Neo4j 在深度遍历和最短路径上全面领先，且延迟随跳数增长最平缓——最短路径 P50 仅约 2 ms
- PostgreSQL 在点查和中低跳计数上很强，但递归最短路径（BFS）成本急剧上升，P50 接近 14 秒
- Cosmos DB Gremlin 在 4/5 跳已显著变慢（5 跳 P50 约 7.8 秒），最短路径全部触发服务端 60 秒超时而无法返回

结论：若图数据库主要服务于研发分析和知识推理（多跳路径、证据链、通路追踪），**Neo4j 是唯一能在可接受延迟内稳定完成深度遍历的引擎**；PostgreSQL 适合浅层结构化检索；Cosmos DB Gremlin 在这类深跳负载下并不适用。

## 配置与测试范围

### Azure 资源配置

| 组件 | 规格 | CPU / 内存 | 其他关键配置 |
|---|---|---:|---|
| Neo4j VM | `Standard_D4s_v5` | 4 vCPU / 16 GiB | Ubuntu 22.04，Premium SSD 数据盘，单机部署 |
| PostgreSQL Flexible Server | `Standard_D4ds_v5` | 4 vCore / 16 GiB | PostgreSQL 16，128 GB 存储，General Purpose，未开启 HA |
| Cosmos DB Gremlin | Gremlin API | 按 RU/s 计费 | 图数据库 `graphdb.social`，分区键 `/pk` |

### 数据规模与测试方式

- 数据规模：100,000 个节点，1,000,000 条边
- 图形状：带有 hub 偏斜的合成社交图（模拟研发知识图谱中少数高连接度的枢纽实体）
- 执行位置：全部从同一台 Azure VM（`centralus`）发起请求，尽量保证网络口径一致
- 测试操作（深跳分析负载）：点查、3 跳计数、4 跳计数、5 跳计数、最短路径（最多 7 跳）
- 计量方式：
  - 点查与 3 跳：每个操作 200 次正式测量 + warmup
  - 4 跳 / 5 跳 / 最短路径：每个操作 20 次正式测量（深跳代价极高，缩短迭代以控制总时长）
- Cosmos DB 专项处理：深跳遍历在 hub 偏斜图上会组合爆炸，因此为 Cosmos 的深跳操作设置**单查询超时**（4/5 跳 20 秒、最短路径 20 秒）。**超时的查询按超时值计为惩罚延迟**，并单独统计 `timeouts` 次数，以保证测试始终可产出结果并如实反映其深跳劣势。测试期间 Cosmos 图吞吐设为 100,000 RU/s（已远超限流瓶颈），最短路径仍 20/20 全部超时，服务端返回 `GraphTimeoutException`（60 秒）。

### 结果文件

- `results/result_neo4j.json`
- `results/result_postgresql.json`
- `results/result_cosmos_gremlin.json`
- `results/REPORT.md`
- `results/benchmark_p50_comparison.png`

## 性能结果

### P50 延迟（毫秒）

| 操作 | Neo4j Community | PostgreSQL Flexible | Cosmos DB Gremlin |
|---|---:|---:|---:|
| 点查（按 id） | 6.72 | 0.16 | 6.48 |
| 3 跳计数 | 3.31 | 1.19 | 141.20 |
| 4 跳计数 | 8.87 | 7.85 | 1025.99 |
| 5 跳计数 | 58.40 | 78.67 | 7840.78 |
| 最短路径（<=7） | 1.98 | 13929.52 | 20000.00* |

> \* Cosmos DB 最短路径 20/20 全部超时（服务端 60 秒 `GraphTimeoutException`），表中按 20000 ms 惩罚值计入，实际为「无法返回」。

### P95 延迟（毫秒）

| 操作 | Neo4j Community | PostgreSQL Flexible | Cosmos DB Gremlin |
|---|---:|---:|---:|
| 点查（按 id） | 17.66 | 0.21 | 32.27 |
| 3 跳计数 | 5.48 | 1.70 | 219.32 |
| 4 跳计数 | 13.30 | 12.44 | 1690.17 |
| 5 跳计数 | 86.68 | 122.32 | 11441.93 |
| 最短路径（<=7） | 3.62 | 21406.21 | 20000.00* |

### 结果解读

- **Neo4j 是深跳遍历与路径推理的最佳选择**：3/4/5 跳延迟随跳数增长平缓（3→58 ms），最短路径凭借原生图遍历 + 提前剪枝，P50 仅约 2 ms，远超另外两者。
- **PostgreSQL 适合浅层结构化检索**：点查与中低跳的 JOIN 计数非常快，但最短路径依赖递归 CTE（BFS），在 hub 偏斜图上分支爆炸，P50 接近 14 秒，不适合交互式路径查询。
- **Cosmos DB Gremlin 不适合深跳分析**：4 跳已达秒级（P50 约 1 秒），5 跳约 7.8 秒，最短路径在 100,000 RU/s 下仍 20/20 全部服务端超时——单次查询消耗约 30 万 RU 仍无法在 60 秒内完成。

补充说明：最短路径不是枚举 7 跳内所有路径，而是寻找两点间最短的一条可行路径。Neo4j 一旦找到更短路径即可提前剪枝停止扩展，因此其最短路径甚至快于固定展开的 3/4/5 跳计数；而 PostgreSQL 的递归 BFS 与 Cosmos 的 `repeat().until()` 都缺乏同等高效的剪枝，导致在 hub 偏斜图上代价极高。

### 可视化

![P50 图数据库性能对比](results/benchmark_p50_comparison.png)

## 药物研发场景如何理解

如果把这组测试映射到药物研发，最有价值的查询通常是多跳、可解释的：

- 靶点发现
- 通路追踪
- 药物再定位
- 基因、蛋白、化合物、疾病、文献之间的证据链分析

这类任务真正重要的是：

- 多跳延迟
- 最短路径延迟
- P95 / P99 尾延迟

本轮深跳测试恰好对应这些场景：4/5 跳计数模拟「跨多层关系的影响范围分析」，最短路径模拟「两个实体（如化合物↔疾病）之间的最短证据链」。结果非常明确：

- **Neo4j**：唯一能在毫秒到几十毫秒级稳定完成深度遍历、且最短路径接近实时的引擎，最适合研发分析与知识推理。
- **PostgreSQL**：浅层关联（3 跳内）足够快且最经济，但最短路径达到十几秒，不适合交互式路径推理。
- **Cosmos DB Gremlin**：深跳遍历秒级起步、最短路径直接超时，即使大幅提高 RU/s 也无法解决，因此**不建议**用于以深度路径推理为核心的研发图谱。

## 成本对比

### 成本口径

- 价格口径：Azure 公共零售价，`centralus`
- 仅计算持续运行的基础资源费用，不含税费、流量、备份和折扣
- 月成本按约 `730 小时/月` 估算

### 计算单价

| 组件 | 按量单价 | 说明 |
|---|---:|---|
| Neo4j VM `Standard_D4s_v5` | `$0.217 / 小时` | Linux VM 计算费 |
| PostgreSQL `Standard_D4ds_v5` | `$0.402 / 小时` | Flexible Server 计算费 |
| Cosmos DB Gremlin | `$0.008 / 小时 / 100 RU/s` | 按 RU/s 线性计费 |

### 月成本估算

| 组件 | 当前配置 | 估算月成本 |
|---|---|---:|
| Neo4j VM | 4 vCPU / 16 GiB | 约 `$158/月` |
| PostgreSQL Flexible Server | 4 vCore / 16 GiB / 128 GB 存储 | 约 `$294/月`（存储另计，量级较小） |
| Cosmos DB Gremlin（本轮深跳测试 100,000 RU/s） | 100,000 RU/s | 约 `$5,840/月` |
| Cosmos DB Gremlin（低吞吐 10,000 RU/s） | 10,000 RU/s | 约 `$584/月` |

> 本轮深跳测试为了排除限流瓶颈，临时将 Cosmos 提高到 100,000 RU/s；即便如此，深跳仍未能改善，说明瓶颈在服务端遍历超时而非 RU 供给。测试完成后应及时调低 RU/s 以避免高额计费。

### 成本结论

- Neo4j 与 PostgreSQL 都属于同一档位的单机/托管数据库成本，差距主要体现在托管开销
- Cosmos DB Gremlin 的费用由 RU/s 决定，吞吐越高，成本增长越快
- 如果长期维持高 RU/s，Cosmos 的成本会显著高于前两者

## 复现方式

主要脚本位于 `benchmark/` 和 `infra/`：

- `benchmark/generate_data.py`：生成测试数据
- `benchmark/bench_neo4j.py`：加载并测试 Neo4j
- `benchmark/bench_postgres.py`：加载并测试 PostgreSQL
- `benchmark/bench_cosmos.py`：加载并测试 Cosmos Gremlin
- `benchmark/make_report.py`：生成 `results/REPORT.md`
- `benchmark/make_plot.py`：生成 `results/benchmark_p50_comparison.png`（对数刻度 P50 对比图）

基础设施脚本：

- `infra/provision_neo4j_vm.sh`
- `infra/provision_postgres.sh`
- `infra/provision_cosmos.sh`
- `infra/ssh_vm.sh`
- `infra/teardown.sh`

## 清理资源

测试结束后建议删除 Azure 资源，避免持续计费：

```bash
bash infra/teardown.sh
```

