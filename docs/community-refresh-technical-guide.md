# 知识图谱社区刷新功能技术开发指南

## 1. 概述

本文档详细说明了知识图谱中社区检测、清理和重建的完整技术实现，包括数据结构变化、算法原理、性能考虑等关键技术细节，用于指导其他项目的开发实现。

### 1.1 功能定位

社区刷新功能是GraphRAG（Graph Retrieval-Augmented Generation）架构的核心组件，主要作用：

- **层次化组织**：将分散的实体按语义相关性组织成多层级社区
- **信息聚合**：为每个社区生成摘要，支持全局和局部搜索
- **性能优化**：通过社区结构加速图查询和推理
- **一致性保证**：确保社区结构与底层实体关系的同步

### 1.2 技术架构

```
用户操作 → API调用 → 数据清理 → 图投影 → 社区检测 → 层级构建 → 摘要生成 → 向量化 → 索引更新
```

## 2. 前置数据结构

### 2.1 实体-关系图状态

**执行前的数据结构**：

```cypher
// 文档节点
(:Document {fileName: "doc1.pdf", fileSize: 1024000, status: "Completed"})

// 文本块节点
(:Chunk {
  id: "chunk_1_doc1.pdf", 
  text: "某段文本内容",
  embedding: [0.1, 0.2, 0.3, ...],  // 384维向量
  position: 1,
  fileName: "doc1.pdf"
})

// 实体节点
(:Person:__Entity__ {
  id: "张三",
  description: "公司CEO",
  embedding: [0.5, 0.6, 0.7, ...]
})

(:Organization:__Entity__ {
  id: "ABC公司", 
  description: "科技公司",
  embedding: [0.2, 0.8, 0.1, ...]
})

// 基础关系
(chunk)-[:PART_OF]->(document)
(chunk)-[:HAS_ENTITY]->(entity)
(entity1)-[:WORKS_FOR]->(entity2)
```

**关键数据统计**（执行前）：
- 实体节点数：~1000个
- 实体间关系数：~2000个  
- 社区节点数：0个
- 社区相关关系数：0个

### 2.2 图的连通性特征

执行前的图呈现以下特征：
- **稀疏连接**：实体间关系密度约0.2%
- **多个连通分量**：通常存在3-5个独立的子图
- **不均匀分布**：80%的实体集中在20%的连通分量中

## 3. 执行流程详解

### 3.1 阶段1：数据清理（clear_communities）

#### 3.1.1 执行逻辑

```python
def clear_communities(gds):
    # 删除所有现有社区节点和关系
    gds.run_cypher("MATCH (c:`__Community__`) DETACH DELETE c")
    
    # 清除实体上的社区属性
    gds.run_cypher("MATCH (e:`__Entity__`) REMOVE e.communities")
```

#### 3.1.2 数据变化

**删除前**：
```cypher
// 可能存在的旧社区数据
(:__Community__ {id: "0-123", level: 0, summary: "旧摘要"})
(:Person {id: "张三", communities: [123, 456, 789]})
```

**删除后**：
```cypher
// 社区节点完全清空
// 实体节点保留，但移除communities属性
(:Person {id: "张三", description: "公司CEO"})  // communities属性被移除
```

#### 3.1.3 设计原因

**为什么要完全清理而非增量更新？**

1. **一致性保证**：避免新旧社区数据混合导致的不一致
2. **算法要求**：Leiden算法需要全图重新计算获得最优结果
3. **简化逻辑**：增量更新的复杂度远高于重建
4. **性能考虑**：全量重建在中等规模图（<10万节点）上性能更好

### 3.2 阶段2：图投影（create_community_graph_projection）

#### 3.2.1 投影创建

```cypher
MATCH (source:!Chunk&!Document&!__Community__)-[]->(target:!Chunk&!Document&!__Community__)
WITH source, target, count(*) as weight
WITH gds.graph.project(
    'communities',
    source,
    target,
    {
        relationshipProperties: { weight: weight },
        undirectedRelationshipTypes: ['*']
    }
) AS g
RETURN g.graphName, g.nodeCount, g.relationshipCount
```

#### 3.2.2 投影特征

**投影前的原始图**：
- 节点类型：Document, Chunk, Person, Organization等
- 有向关系：WORKS_FOR, PART_OF, HAS_ENTITY等

**投影后的处理图**：
- 节点：仅包含实体节点（Person, Organization等）
- 关系：转换为无向加权边
- 权重：相同节点对之间的关系数量

**数据变化示例**：
```
原始：(张三)-[:WORKS_FOR]->(ABC公司), (张三)-[:LOCATED_IN]->(ABC公司)
投影：(张三)-[:REL {weight: 2}]-(ABC公司)
```

#### 3.2.3 设计原因

**为什么需要图投影？**

1. **算法适配**：Leiden算法需要无向图输入
2. **性能优化**：GDS内存投影比原生Cypher查询快100-1000倍
3. **权重计算**：多重关系自动聚合为权重，体现连接强度
4. **类型过滤**：排除文档和块节点，专注于实体关系

### 3.3 阶段3：社区检测（write_communities）

#### 3.3.1 Leiden算法执行

```python
gds.leiden.write(
    graph_project,
    writeProperty="communities",           # 结果属性名
    includeIntermediateCommunities=True,   # 生成多层级
    relationshipWeightProperty="weight",   # 使用边权重
    maxLevels=3,                          # 最大3层
    minCommunitySize=1,                   # 最小社区1个节点
)
```

#### 3.3.2 算法输出格式

**实体节点的communities属性**：
```
张三.communities = [15, 7, 2]
李四.communities = [15, 7, 2] 
王五.communities = [23, 8, 2]
```

**数组含义**：
- `[0]`：0级社区ID（最细粒度）
- `[1]`：1级社区ID（中等粒度）
- `[2]`：2级社区ID（最粗粒度）

#### 3.3.3 社区质量指标

执行后典型的社区分布：
- **0级社区**：~50个，平均20个节点
- **1级社区**：~15个，平均65个节点  
- **2级社区**：~5个，平均200个节点

**模块度（Modularity）**：通常在0.3-0.8之间，越高表示社区结构越明显。

#### 3.3.4 设计原因

**为什么选择Leiden算法？**

1. **质量优势**：相比Louvain算法，避免了poorly connected communities问题
2. **多层级**：自然生成层次化结构，适合GraphRAG的多粒度检索
3. **可重现性**：相同输入产生稳定输出
4. **性能**：O(m log n)复杂度，适合中大规模图

### 3.4 阶段4：社区节点创建（CREATE_COMMUNITY_LEVELS）

#### 3.4.1 节点创建逻辑

```cypher
MATCH (e:`__Entity__`)
WHERE e.communities is NOT NULL
UNWIND range(0, size(e.communities) - 1, 1) AS index
CALL {
  WITH e, index
  WHERE index = 0
  MERGE (c:`__Community__` {id: toString(index) + '-' + toString(e.communities[index])})
  ON CREATE SET c.level = index
  MERGE (e)-[:IN_COMMUNITY]->(c)
  RETURN count(*) AS count_0
}
CALL {
  WITH e, index
  WHERE index > 0
  MERGE (current:`__Community__` {id: toString(index) + '-' + toString(e.communities[index])})
  ON CREATE SET current.level = index
  MERGE (previous:`__Community__` {id: toString(index - 1) + '-' + toString(e.communities[index - 1])})
  MERGE (previous)-[:PARENT_COMMUNITY]->(current)
  RETURN count(*) AS count_1
}
```

#### 3.4.2 生成的数据结构

**新增社区节点**：
```cypher
(:__Community__ {id: "0-15", level: 0})  // 0级社区
(:__Community__ {id: "1-7", level: 1})   // 1级社区  
(:__Community__ {id: "2-2", level: 2})   // 2级社区
```

**新增关系**：
```cypher
(张三)-[:IN_COMMUNITY]->(:__Community__ {id: "0-15"})
(李四)-[:IN_COMMUNITY]->(:__Community__ {id: "0-15"})
(:__Community__ {id: "0-15"})-[:PARENT_COMMUNITY]->(:__Community__ {id: "1-7"})
(:__Community__ {id: "1-7"})-[:PARENT_COMMUNITY]->(:__Community__ {id: "2-2"})
```

#### 3.4.3 ID编码规则

**社区ID格式**：`{level}-{community_number}`

- level：社区层级（0最细，数字越大越粗）
- community_number：Leiden算法分配的社区编号

**示例**：
- `"0-15"`：0级的第15号社区
- `"1-7"`：1级的第7号社区

### 3.5 阶段5：属性计算

#### 3.5.1 社区权重计算

```cypher
-- 计算每个社区包含的chunk数量
MATCH (n:`__Community__`)<-[:IN_COMMUNITY]-()<-[:HAS_ENTITY]-(c)
WITH n, count(distinct c) AS chunkCount
SET n.weight = chunkCount
```

**结果示例**：
```cypher
(:__Community__ {id: "0-15", level: 0, weight: 45})  // 包含45个chunks
```

#### 3.5.2 社区排名计算

```cypher
-- 基于包含的文档数量计算排名
MATCH (c:__Community__)<-[:IN_COMMUNITY*]-(:!Chunk&!Document&!__Community__)<-[HAS_ENTITY]-(:Chunk)<-[]-(d:Document)
WITH c, count(distinct d) AS rank
SET c.community_rank = rank
```

#### 3.5.3 设计原因

**为什么需要这些属性？**

1. **weight**：用于GraphRAG检索时的相关性排序
2. **community_rank**：基于文档覆盖度的重要性评估
3. **level**：支持多粒度检索策略

### 3.6 阶段6：摘要生成（create_community_summaries）

#### 3.6.1 社区信息提取

```cypher
MATCH (c:`__Community__`)<-[:IN_COMMUNITY]-(e)
WHERE c.level = 0 AND size(nodes) > 1
CALL apoc.path.subgraphAll(nodes[0], {whitelistNodes:nodes})
YIELD relationships
RETURN c.id AS communityId,
       [n in nodes | {id: n.id, description: n.description, type: labels(n)[0]}] AS nodes,
       [r in relationships | {start: startNode(r).id, type: type(r), end: endNode(r).id}] AS rels
```

**提取结果示例**：
```json
{
  "communityId": "0-15",
  "nodes": [
    {"id": "张三", "description": "公司CEO", "type": "Person"},
    {"id": "ABC公司", "description": "科技公司", "type": "Organization"}
  ],
  "rels": [
    {"start": "张三", "type": "WORKS_FOR", "end": "ABC公司"}
  ]
}
```

#### 3.6.2 LLM摘要生成

**Prompt模板**：
```
Based on the provided nodes and relationships that belong to the same graph community,
generate following output in exact format
title: A concise title, no more than 4 words,
summary: A natural language summary of the information

Nodes are:
id: 张三, type: Person, description: 公司CEO
id: ABC公司, type: Organization, description: 科技公司

Relationships are:
(张三)-[:WORKS_FOR]->(ABC公司)
```

**LLM输出示例**：
```
title: ABC公司管理层
summary: 张三担任ABC科技公司的CEO，负责公司的整体运营和战略决策。该公司是一家专注于技术创新的现代化企业。
```

#### 3.6.3 并发处理

```python
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(process_community_info, community, community_chain) 
               for community in community_info_list]
    
    for future in as_completed(futures):
        result = future.result()
        summaries.append(result)
```

**性能数据**：
- 串行处理：~50个社区需要5-10分钟
- 并发处理：~50个社区需要1-2分钟

### 3.7 阶段7：向量化（create_community_embeddings）

#### 3.7.1 嵌入生成

```python
# 批量处理社区摘要
batch_size = 100
for i in range(0, len(community_summaries), batch_size):
    batch = community_summaries[i:i+batch_size]
    for community in batch:
        embedding = embeddings.embed_query(community['summary'])
        community['embedding'] = embedding
```

#### 3.7.2 数据存储

```cypher
UNWIND $rows AS row
MATCH (c) WHERE c.id = row.communityId
CALL db.create.setNodeVectorProperty(c, "embedding", row.embedding)
```

**结果数据**：
```cypher
(:__Community__ {
  id: "0-15", 
  level: 0, 
  weight: 45,
  title: "ABC公司管理层",
  summary: "张三担任ABC科技公司的CEO...",
  embedding: [0.234, 0.567, 0.891, ...]  // 384维向量
})
```

### 3.8 阶段8：索引创建

#### 3.8.1 向量索引

```cypher
CREATE VECTOR INDEX community_vector IF NOT EXISTS 
FOR (c:__Community__) ON c.embedding
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }
}
```

#### 3.8.2 全文索引

```cypher
CREATE FULLTEXT INDEX community_keyword IF NOT EXISTS
FOR (n:`__Community__`) ON EACH [n.summary]
```

## 4. 执行后数据结构

### 4.1 完整的图结构

```cypher
// 原有结构保持不变
(:Document)-[:FIRST_CHUNK]->(:Chunk)-[:HAS_ENTITY]->(:Person)

// 新增社区结构
(:Person)-[:IN_COMMUNITY]->(:__Community__ {level: 0})
(:__Community__ {level: 0})-[:PARENT_COMMUNITY]->(:__Community__ {level: 1})
(:__Community__ {level: 1})-[:PARENT_COMMUNITY]->(:__Community__ {level: 2})

// 社区节点完整属性
(:__Community__ {
  id: "0-15",
  level: 0,
  weight: 45,
  community_rank: 3,
  title: "ABC公司管理层", 
  summary: "详细摘要文本...",
  embedding: [0.234, 0.567, ...]
})
```

### 4.2 数据统计变化

| 指标 | 执行前 | 执行后 | 变化 |
|------|--------|--------|------|
| 节点总数 | 3,500 | 4,170 | +670个社区节点 |
| 关系总数 | 8,200 | 9,540 | +1,340个社区关系 |
| 向量索引数 | 2个 | 4个 | +社区向量索引+实体向量索引 |
| 全文索引数 | 2个 | 3个 | +社区全文索引 |

### 4.3 存储空间影响

**内存使用**：
- 社区节点：~50MB（1000个节点 × 50KB/节点）
- 向量存储：~150MB（1000个向量 × 384维 × 4字节）
- 索引开销：~80MB

**磁盘存储**：
- 图数据：增加约20%
- 向量索引：增加约300MB
- 全文索引：增加约50MB

## 5. 性能与优化

### 5.1 执行时间分析

| 阶段 | 小图(<1K节点) | 中图(1K-10K节点) | 大图(>10K节点) |
|------|---------------|------------------|----------------|
| 数据清理 | <1秒 | 1-5秒 | 5-30秒 |
| 图投影 | 1-2秒 | 5-15秒 | 30-120秒 |
| 社区检测 | 2-5秒 | 15-60秒 | 2-10分钟 |
| 摘要生成 | 30-60秒 | 2-5分钟 | 5-15分钟 |
| 向量化 | 10-20秒 | 1-2分钟 | 3-8分钟 |
| 索引创建 | 5-10秒 | 30-60秒 | 2-5分钟 |
| **总计** | **1-2分钟** | **5-10分钟** | **15-30分钟** |

### 5.2 性能瓶颈

1. **LLM API调用**：占总时间的60-70%
2. **向量嵌入计算**：占总时间的20-25%
3. **图算法计算**：占总时间的10-15%

### 5.3 优化策略

#### 5.3.1 并发优化

```python
# LLM调用并发限制
MAX_CONCURRENT_LLM_CALLS = 10

# 向量化批处理
EMBEDDING_BATCH_SIZE = 100

# 数据库批量写入
DB_BATCH_SIZE = 1000
```

#### 5.3.2 缓存策略

```python
# 社区摘要缓存
COMMUNITY_SUMMARY_CACHE_TTL = 3600  # 1小时

# 嵌入向量缓存
EMBEDDING_CACHE_SIZE = 10000

# 图投影缓存
GRAPH_PROJECTION_CACHE = True
```

## 6. 错误处理与恢复

### 6.1 常见错误场景

#### 6.1.1 LLM API失败

**错误表现**：
```
HTTPException: Rate limit exceeded
ConnectionError: API endpoint unreachable
```

**处理策略**：
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def process_community_info(community, chain):
    try:
        return chain.invoke({'community_info': combined_text})
    except Exception as e:
        logging.warning(f"LLM processing failed for community {community['communityId']}: {e}")
        return {"community": community['communityId'], "title": "处理失败", "summary": "摘要生成失败"}
```

#### 6.1.2 图投影失败

**错误表现**：
```
Neo4jError: Insufficient memory for graph projection
```

**处理策略**：
```python
def create_community_graph_projection(gds):
    try:
        # 检查可用内存
        memory_info = gds.debug.sysInfo()
        if memory_info['availableMemory'] < required_memory:
            raise MemoryError("Insufficient memory for graph projection")
        
        return gds.graph.project(...)
    except MemoryError:
        # 分批处理或降级策略
        return create_reduced_projection(gds)
```

### 6.2 数据一致性保证

#### 6.2.1 事务边界

```python
def create_communities_with_transaction(uri, username, password, database):
    with driver.session(database=database) as session:
        with session.begin_transaction() as tx:
            try:
                clear_communities(tx)
                create_community_structure(tx)
                tx.commit()
            except Exception as e:
                tx.rollback()
                raise
```

#### 6.2.2 中断恢复

```python
def resume_community_creation(gds):
    # 检查中断点
    if community_nodes_exist() and not community_summaries_exist():
        # 从摘要生成阶段恢复
        create_community_summaries(gds, model)
    elif community_summaries_exist() and not community_embeddings_exist():
        # 从向量化阶段恢复
        create_community_embeddings(gds)
```

## 7. 部署与运维

### 7.1 环境要求

#### 7.1.1 硬件配置

**最小配置**：
- CPU：4核心
- 内存：8GB RAM
- 存储：50GB SSD

**推荐配置**：
- CPU：8核心以上
- 内存：16GB+ RAM  
- 存储：100GB+ SSD
- GPU：可选，用于本地嵌入模型

#### 7.1.2 软件依赖

```
Neo4j: 5.0+
Neo4j GDS: 2.0+  
Python: 3.9+
graphdatascience: 1.8+
langchain: 0.1+
sentence-transformers: 2.2+
```

### 7.2 配置参数

#### 7.2.1 社区检测参数

```python
# communities.py
MAX_COMMUNITY_LEVELS = 3        # 最大层级数
MIN_COMMUNITY_SIZE = 1          # 最小社区大小
MAX_WORKERS = 10               # 并发线程数
COMMUNITY_CREATION_DEFAULT_MODEL = "openai_gpt_4o"  # 默认LLM模型
```

#### 7.2.2 性能调优参数

```bash
# Neo4j配置 (neo4j.conf)
server.memory.heap.initial_size=4G
server.memory.heap.max_size=8G
server.memory.pagecache.size=2G

# GDS配置
gds.enterprise.license_file=/path/to/license
```

### 7.3 监控指标

#### 7.3.1 关键指标

```python
# 性能指标
community_detection_duration = timer()
summary_generation_duration = timer()
embedding_creation_duration = timer()

# 质量指标
community_count_by_level = count_communities_by_level()
average_community_size = calculate_average_community_size()
modularity_score = calculate_modularity()

# 资源指标
memory_usage = get_memory_usage()
cpu_utilization = get_cpu_utilization()
```

#### 7.3.2 告警规则

```yaml
alerts:
  - name: community_detection_timeout
    condition: community_detection_duration > 1800  # 30分钟
    severity: warning
    
  - name: low_modularity_score  
    condition: modularity_score < 0.3
    severity: warning
    
  - name: memory_exhaustion
    condition: memory_usage > 0.9
    severity: critical
```

## 8. 测试与验证

### 8.1 功能测试

#### 8.1.1 数据完整性测试

```python
def test_community_data_integrity():
    # 验证所有实体都分配到社区
    entities_without_communities = count_entities_without_communities()
    assert entities_without_communities == 0
    
    # 验证社区层级结构完整
    orphan_communities = count_orphan_communities()
    assert orphan_communities == 0
    
    # 验证社区摘要生成完成
    communities_without_summary = count_communities_without_summary()
    assert communities_without_summary == 0
```

#### 8.1.2 性能测试

```python
def test_community_detection_performance():
    start_time = time.time()
    create_communities(uri, username, password, database)
    duration = time.time() - start_time
    
    # 验证执行时间在合理范围内
    assert duration < 1800  # 30分钟内完成
    
    # 验证内存使用合理
    memory_usage = get_memory_usage()
    assert memory_usage < 0.8  # 不超过80%
```

### 8.2 质量验证

#### 8.2.1 社区质量评估

```python
def evaluate_community_quality():
    modularity = calculate_modularity()
    silhouette_score = calculate_silhouette_score()
    coverage = calculate_coverage()
    
    logging.info(f"Community Quality Metrics:")
    logging.info(f"  Modularity: {modularity:.3f}")
    logging.info(f"  Silhouette Score: {silhouette_score:.3f}")  
    logging.info(f"  Coverage: {coverage:.3f}")
    
    return {
        "modularity": modularity,
        "silhouette_score": silhouette_score,
        "coverage": coverage
    }
```

#### 8.2.2 摘要质量检查

```python
def validate_community_summaries():
    summaries = get_all_community_summaries()
    
    quality_issues = []
    for summary in summaries:
        # 检查摘要长度
        if len(summary['text']) < 50:
            quality_issues.append(f"Community {summary['id']}: Summary too short")
            
        # 检查关键词覆盖
        if not contains_relevant_keywords(summary['text'], summary['entities']):
            quality_issues.append(f"Community {summary['id']}: Low keyword coverage")
    
    return quality_issues
```

## 9. 迁移指导

### 9.1 系统适配

#### 9.1.1 数据库适配

**Neo4j → 其他图数据库**：

```python
# 抽象图数据库接口
class GraphDatabaseAdapter:
    def execute_query(self, query: str, params: dict) -> List[dict]:
        raise NotImplementedError
        
    def create_vector_index(self, index_name: str, node_label: str, property_name: str):
        raise NotImplementedError

class Neo4jAdapter(GraphDatabaseAdapter):
    # Neo4j实现
    pass

class TigerGraphAdapter(GraphDatabaseAdapter): 
    # TigerGraph实现
    pass
```

#### 9.1.2 LLM接口适配

```python
# 统一LLM接口
class LLMProvider:
    def generate_summary(self, community_info: str) -> str:
        raise NotImplementedError

class OpenAIProvider(LLMProvider):
    def generate_summary(self, community_info: str) -> str:
        # OpenAI实现
        pass

class HuggingFaceProvider(LLMProvider):
    def generate_summary(self, community_info: str) -> str:
        # HuggingFace实现  
        pass
```

### 9.2 功能扩展

#### 9.2.1 增量更新支持

```python
def incremental_community_update(new_entities: List[Entity], updated_relationships: List[Relationship]):
    """增量更新社区结构而非完全重建"""
    
    # 1. 识别受影响的社区
    affected_communities = identify_affected_communities(new_entities, updated_relationships)
    
    # 2. 局部重新计算
    for community in affected_communities:
        recompute_community_structure(community)
        
    # 3. 更新摘要和嵌入
    regenerate_summaries(affected_communities)
    update_embeddings(affected_communities)
```

#### 9.2.2 自定义社区算法

```python
class CommunityDetectionStrategy:
    def detect_communities(self, graph_projection) -> List[Community]:
        raise NotImplementedError

class LeidenStrategy(CommunityDetectionStrategy):
    def detect_communities(self, graph_projection) -> List[Community]:
        # Leiden算法实现
        pass

class LouvainStrategy(CommunityDetectionStrategy):
    def detect_communities(self, graph_projection) -> List[Community]:
        # Louvain算法实现
        pass
```

### 9.3 最佳实践

#### 9.3.1 代码组织

```
project/
├── core/
│   ├── graph/          # 图数据库抽象层
│   ├── llm/           # LLM接口层  
│   ├── embedding/     # 嵌入模型层
│   └── algorithms/    # 社区检测算法
├── services/
│   ├── community_service.py    # 主业务逻辑
│   ├── summary_service.py      # 摘要生成服务
│   └── embedding_service.py    # 向量化服务
├── config/
│   ├── settings.py             # 配置管理
│   └── constants.py            # 常量定义
└── tests/
    ├── integration/            # 集成测试
    ├── unit/                  # 单元测试
    └── performance/           # 性能测试
```

#### 9.3.2 配置管理

```python
# settings.py
from pydantic import BaseSettings

class CommunitySettings(BaseSettings):
    # 算法参数
    max_community_levels: int = 3
    min_community_size: int = 1
    detection_algorithm: str = "leiden"
    
    # 性能参数
    max_concurrent_workers: int = 10
    llm_batch_size: int = 10
    embedding_batch_size: int = 100
    
    # LLM配置
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.0
    
    # 数据库配置
    graph_db_uri: str
    graph_db_username: str
    graph_db_password: str
    
    class Config:
        env_file = ".env"
```

## 10. 总结

社区刷新功能是知识图谱系统的关键组件，通过系统化的数据清理、图算法处理、AI摘要生成和向量化存储，实现了从平面实体关系到层次化社区结构的转换。

**核心价值**：
1. **结构化组织**：将复杂的实体关系组织成可理解的社区层次
2. **语义聚合**：通过AI生成的摘要提供高级语义信息
3. **检索优化**：支持GraphRAG的全局和局部搜索策略
4. **可扩展性**：模块化设计支持不同规模和需求的部署

**技术特点**：
1. **算法驱动**：基于Leiden算法的社区检测保证了结果质量
2. **AI增强**：LLM生成的摘要提供了人类可理解的社区描述
3. **向量化支持**：嵌入向量支持语义相似性搜索
4. **性能优化**：并发处理和批量操作确保了执行效率

本文档提供的技术细节和代码示例可以直接用于指导其他项目的开发实现，通过合理的适配和扩展，能够满足不同场景下的社区检测需求。 