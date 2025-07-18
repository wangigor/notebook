# CHAT_VECTOR_GRAPH_FULLTEXT_MODE 技术实现指南

## 概述

CHAT_VECTOR_GRAPH_FULLTEXT_MODE是LLM图构建器中最复杂和最强大的搜索模式，它将向量语义搜索、图结构遍历和全文关键字搜索三种技术有机结合，实现了多维度的智能检索系统。

### 核心特性

- **混合搜索架构**: 同时利用向量相似度、图关系和全文匹配
- **动态图扩展**: 基于相似度分数智能决定图遍历深度
- **实体关系增强**: 通过知识图谱提供上下文丰富的答案
- **全文精确匹配**: 确保关键词的精确覆盖

## 1. 技术架构设计

### 1.1 整体数据流

```
用户查询 → 查询预处理 → 混合检索 → 实体扩展 → 后处理 → 结果聚合 → LLM生成 → 响应返回
     ↓           ↓           ↓           ↓           ↓           ↓           ↓
  问题分析   查询向量化   向量+全文搜索  图遍历扩展  数据整合   上下文构建  答案生成
```

### 1.2 核心组件架构

```python
# 主要模块组织
src/
├── QA_integration.py          # 核心编排器
├── shared/
│   └── constants.py          # 查询定义和配置
├── chunkid_entities.py       # 后处理模块
└── make_relationships.py     # 关系构建器

# 配置映射
CHAT_MODE_CONFIG_MAP = {
    CHAT_VECTOR_GRAPH_FULLTEXT_MODE: {
        "retrieval_query": VECTOR_GRAPH_SEARCH_QUERY,    # 主查询
        "top_k": VECTOR_SEARCH_TOP_K,                    # 返回数量: 5
        "index_name": "vector",                          # 向量索引
        "keyword_index": "keyword",                      # 全文索引  
        "document_filter": False,                        # 文档过滤: 禁用
        "node_label": "Chunk",                          # 目标节点
        "embedding_node_property": "embedding",         # 向量属性
        "text_node_properties": ["text"],               # 文本属性
        "mode": "graph_vector_fulltext"
    }
}
```

## 2. 前置数据结构

### 2.1 图数据库模式

执行前的Neo4j图数据库包含以下核心结构：

```cypher
// 文档节点 - 数据源
(:Document {
    fileName: "example.pdf",
    fileSize: 1024000,
    fileType: "pdf",
    status: "Completed",
    createdAt: datetime(),
    nodeCount: 45,
    relationshipCount: 87
})

// 文本块节点 - 基础检索单元
(:Chunk {
    id: "chunk_1_example.pdf",
    text: "实际的文档内容文本...",
    embedding: [0.1, 0.2, 0.3, ...],  // 384维向量
    position: 1,
    length: 512,
    fileName: "example.pdf",
    page_number: 1
})

// 实体节点 - 知识元素
(:Person:__Entity__ {
    id: "张三",
    description: "公司CEO，负责整体战略",
    embedding: [0.5, 0.6, 0.7, ...]   // 384维向量
})

(:Organization:__Entity__ {
    id: "ABC科技公司",
    description: "专注人工智能的科技公司",
    embedding: [0.2, 0.8, 0.1, ...]
})

// 基础关系结构
(chunk)-[:PART_OF]->(document)
(chunk)-[:HAS_ENTITY]->(entity)
(chunk)-[:NEXT_CHUNK]->(nextChunk)
(chunk)-[:SIMILAR]->(similarChunk)
(entity1)-[:WORKS_FOR]->(entity2)
```

### 2.2 必需的索引结构

```cypher
-- 向量索引 (相似度搜索)
CREATE VECTOR INDEX vector IF NOT EXISTS
FOR (c:Chunk) ON c.embedding
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }
}

-- 全文索引 (关键词搜索)  
CREATE FULLTEXT INDEX keyword IF NOT EXISTS
FOR (n:Chunk) ON EACH [n.text]

-- 实体向量索引
CREATE VECTOR INDEX entity_vector IF NOT EXISTS
FOR (e:__Entity__) ON e.embedding
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }
}

-- 实体全文索引
CREATE FULLTEXT INDEX entities IF NOT EXISTS
FOR (n:__Entity__) ON EACH [n.id, n.description]
```

### 2.3 数据统计特征

**典型的图规模指标：**
- 文档节点：~100个
- 块节点：~10,000个  
- 实体节点：~2,000个
- HAS_ENTITY关系：~15,000个
- 实体间关系：~5,000个
- 向量维度：384

## 3. 核心查询实现

### 3.1 主检索查询 (VECTOR_GRAPH_SEARCH_QUERY)

这是整个模式的核心查询，由三个部分组成：

```cypher
-- PREFIX: 初始检索和聚合
VECTOR_GRAPH_SEARCH_QUERY_PREFIX = """
WITH node as chunk, score
// 找到块所属的文档
MATCH (chunk)-[:PART_OF]->(d:Document)
// 聚合块详情
WITH d, collect(DISTINCT {chunk: chunk, score: score}) AS chunks, avg(score) as avg_score
// 获取实体
CALL { WITH chunks
UNWIND chunks as chunkScore
WITH chunkScore.chunk as chunk
"""

-- ENTITY_QUERY: 智能实体扩展
VECTOR_GRAPH_SEARCH_ENTITY_QUERY = """
    OPTIONAL MATCH (chunk)-[:HAS_ENTITY]->(e)
    WITH e, count(*) AS numChunks 
    ORDER BY numChunks DESC 
    LIMIT {no_of_entites}           // 默认40个实体

    WITH 
    CASE 
        // 低相似度范围 - 需要更多上下文
        WHEN e.embedding IS NULL OR 
             ({embedding_match_min} <= vector.similarity.cosine($query_vector, e.embedding) 
              AND vector.similarity.cosine($query_vector, e.embedding) <= {embedding_match_max}) 
        THEN 
            collect {{
                OPTIONAL MATCH path=(e)(()-[rels:!HAS_ENTITY&!PART_OF]-()){{0,1}}(:!Chunk&!Document&!__Community__) 
                RETURN path LIMIT {entity_limit_minmax_case}   // 20个路径
            }}
        // 高相似度 - 扩展更多关系
        WHEN e.embedding IS NOT NULL AND 
             vector.similarity.cosine($query_vector, e.embedding) > {embedding_match_max} 
        THEN
            collect {{
                OPTIONAL MATCH path=(e)(()-[rels:!HAS_ENTITY&!PART_OF]-()){{0,2}}(:!Chunk&!Document&!__Community__) 
                RETURN path LIMIT {entity_limit_max_case}      // 40个路径
            }} 
        ELSE 
            collect {{ 
                MATCH path=(e) 
                RETURN path 
            }}
    END AS paths, e
"""

-- SUFFIX: 结果格式化和聚合
VECTOR_GRAPH_SEARCH_QUERY_SUFFIX = """
   WITH apoc.coll.toSet(apoc.coll.flatten(collect(DISTINCT paths))) AS paths,
        collect(DISTINCT e) AS entities
   
   // 去重节点和关系
   RETURN
       collect {
           UNWIND paths AS p
           UNWIND relationships(p) AS r
           RETURN DISTINCT r
       } AS rels,
       collect {
           UNWIND paths AS p
           UNWIND nodes(p) AS n
           RETURN DISTINCT n
       } AS nodes,
       entities
}

// 生成响应文本
WITH d, avg_score,
    [c IN chunks | c.chunk.text] AS texts,
    [c IN chunks | {id: c.chunk.id, score: c.score}] AS chunkdetails,
    [n IN nodes | elementId(n)] AS entityIds,
    [r IN rels | elementId(r)] AS relIds,
    // 实体文本格式化
    apoc.coll.sort([
        n IN nodes |
        coalesce(apoc.coll.removeAll(labels(n), ['__Entity__'])[0], "") + ":" +
        coalesce(n.id, "") +
        (CASE WHEN n.description IS NOT NULL THEN " (" + n.description + ")" ELSE "" END)
    ]) AS nodeTexts,
    // 关系文本格式化
    apoc.coll.sort([
        r IN rels |
        coalesce(apoc.coll.removeAll(labels(startNode(r)), ['__Entity__'])[0], "") + ":" +
        coalesce(startNode(r).id, "") + " " + type(r) + " " +
        coalesce(apoc.coll.removeAll(labels(endNode(r)), ['__Entity__'])[0], "") + ":" + 
        coalesce(endNode(r).id, "")
    ]) AS relTexts,
    entities

// 组合最终文本
WITH d, avg_score, chunkdetails, entityIds, relIds,
    "Text Content:\n" + apoc.text.join(texts, "\n----\n") +
    "\n----\nEntities:\n" + apoc.text.join(nodeTexts, "\n") +
    "\n----\nRelationships:\n" + apoc.text.join(relTexts, "\n") AS text,
    entities

RETURN
   text,
   avg_score AS score,
   {
       length: size(text),
       source: COALESCE(CASE WHEN d.url CONTAINS "None" THEN d.fileName ELSE d.url END, d.fileName),
       chunkdetails: chunkdetails,
       entities : {
           entityids: entityIds,
           relationshipids: relIds
       }
   } AS metadata
"""
```

### 3.2 智能扩展策略说明

**为什么使用动态路径扩展？**

1. **相似度阈值决策**：
   - `embedding_match_min` (0.3) ～ `embedding_match_max` (0.9)：中等相关性，1跳扩展
   - 大于 `embedding_match_max` (0.9)：高相关性，2跳扩展
   - 其他情况：仅返回实体本身

2. **扩展数量控制**：
   - 中等相关性：限制20个路径（`entity_limit_minmax_case`）
   - 高相关性：限制40个路径（`entity_limit_max_case`）

3. **关系过滤策略**：
   ```cypher
   [rels:!HAS_ENTITY&!PART_OF]
   ```
   排除文档结构关系，只关注语义关系

## 4. 执行流程详解

### 4.1 请求处理管道

```python
# QA_integration.py - 主执行流程
async def QA_RAG(graph, model, question, document_names, session_id, mode):
    """
    Args:
        graph: Neo4j图实例
        model: LLM模型名称
        question: 用户问题
        document_names: 文档名列表(JSON字符串)
        session_id: 会话ID
        mode: 聊天模式 = "graph_vector_fulltext"
    """
    
    # 1. 获取聊天配置
    chat_mode_settings = CHAT_MODE_CONFIG_MAP[mode]
    logging.info(f"Chat Mode: {mode}")
    
    # 2. 创建会话历史
    history = create_neo4j_chat_message_history(graph, session_id)
    messages = history.messages
    user_question = HumanMessage(content=question)
    messages.append(user_question)
    
    # 3. 处理聊天响应
    return process_chat_response(messages, history, question, model, graph, 
                               document_names, chat_mode_settings)

def process_chat_response(messages, history, question, model, graph, 
                         document_names, chat_mode_settings):
    """核心处理逻辑"""
    
    # 1. 设置聊天环境
    llm, doc_retriever, model_version = setup_chat(
        model, graph, document_names, chat_mode_settings
    )
    
    # 2. 检索文档
    docs, transformed_question = retrieve_documents(doc_retriever, messages)
    
    if docs:
        # 3. 处理检索结果
        content, result, total_tokens, formatted_docs = process_documents(
            docs, question, messages, llm, model, chat_mode_settings
        )
    else:
        content = "I couldn't find any relevant documents to answer your question."
        result = {"sources": [], "nodedetails": {}, "entities": {}}
        total_tokens = 0
        formatted_docs = ""
    
    # 4. 构建响应
    ai_response = AIMessage(content=content)
    messages.append(ai_response)
    
    # 5. 异步摘要处理
    summarization_thread = threading.Thread(
        target=summarize_and_log, 
        args=(history, messages, llm)
    )
    summarization_thread.start()
    
    return {
        "session_id": session_id,
        "message": content,
        "info": {
            "sources": result["sources"],
            "model": model_version,
            "nodedetails": result["nodedetails"],
            "total_tokens": total_tokens,
            "mode": chat_mode_settings["mode"],
            "entities": result["entities"]
        },
        "user": "chatbot"
    }
```

### 4.2 Neo4j向量检索器设置

```python
def initialize_neo4j_vector(graph, chat_mode_settings):
    """初始化混合检索器"""
    
    retrieval_query = chat_mode_settings.get("retrieval_query")
    index_name = chat_mode_settings.get("index_name")        # "vector"
    keyword_index = chat_mode_settings.get("keyword_index")   # "keyword"
    node_label = chat_mode_settings.get("node_label")        # "Chunk"
    embedding_node_property = chat_mode_settings.get("embedding_node_property")  # "embedding"
    text_node_properties = chat_mode_settings.get("text_node_properties")        # ["text"]

    # 创建混合检索器
    neo_db = Neo4jVector.from_existing_graph(
        embedding=EMBEDDING_FUNCTION,                    # sentence-transformer
        index_name=index_name,                          # 向量索引
        retrieval_query=retrieval_query,                # 自定义查询
        graph=graph,                                    # Neo4j连接
        search_type="hybrid",                           # 混合搜索！
        node_label=node_label,                          # 目标节点类型
        embedding_node_property=embedding_node_property, # 向量属性
        text_node_properties=text_node_properties,      # 文本属性
        keyword_index_name=keyword_index                # 全文索引
    )
    
    return neo_db
```

### 4.3 文档检索链构建

```python
def create_document_retriever_chain(llm, retriever):
    """创建带查询转换的检索链"""
    
    # 查询转换提示
    query_transform_prompt = ChatPromptTemplate.from_messages([
        ("system", QUESTION_TRANSFORM_TEMPLATE),  # 根据对话历史生成搜索查询
        MessagesPlaceholder(variable_name="messages")
    ])

    # 文档压缩管道
    splitter = TokenTextSplitter(
        chunk_size=CHAT_DOC_SPLIT_SIZE,           # 1000
        chunk_overlap=0
    )
    
    embeddings_filter = EmbeddingsFilter(
        embeddings=EMBEDDING_FUNCTION,
        similarity_threshold=CHAT_EMBEDDING_FILTER_SCORE_THRESHOLD  # 0.8
    )

    pipeline_compressor = DocumentCompressorPipeline(
        transformers=[splitter, embeddings_filter]
    )

    compression_retriever = ContextualCompressionRetriever(
        base_compressor=pipeline_compressor, 
        base_retriever=retriever
    )

    # 查询转换检索链
    query_transforming_retriever_chain = RunnableBranch(
        (
            # 首次查询直接使用
            lambda x: len(x.get("messages", [])) == 1,
            (lambda x: x["messages"][-1].content) | compression_retriever,
        ),
        # 后续查询需要转换
        query_transform_prompt | llm | StrOutputParser() | compression_retriever,
    ).with_config(run_name="chat_retriever_chain")

    return query_transforming_retriever_chain
```

## 5. 执行后数据变化

### 5.1 检索结果数据结构

执行查询后，系统返回结构化的文档列表：

```python
# 单个文档对象结构
Document = {
    "page_content": """
Text Content:
原始文档文本内容第一部分
----
原始文档文本内容第二部分
----
Entities:
Person:张三 (公司CEO，负责整体战略)
Organization:ABC科技公司 (专注人工智能的科技公司)
----
Relationships:
Person:张三 WORKS_FOR Organization:ABC科技公司
Person:李四 REPORTS_TO Person:张三
""",
    "metadata": {
        "length": 1542,
        "source": "example.pdf",
        "chunkdetails": [
            {"id": "chunk_1_example.pdf", "score": 0.92},
            {"id": "chunk_2_example.pdf", "score": 0.88}
        ],
        "entities": {
            "entityids": ["4:abc:1001", "4:abc:1002", "4:abc:1003"],
            "relationshipids": ["5:def:2001", "5:def:2002"]
        }
    },
    "state": {
        "query_similarity_score": 0.90
    }
}
```

### 5.2 后处理数据扩展

通过`chunkid_entities.py`模块，系统进一步扩展检索结果：

```python
# 后处理输入
nodedetails = {
    "chunkdetails": [
        {"id": "chunk_1_example.pdf", "score": 0.92},
        {"id": "chunk_2_example.pdf", "score": 0.88}
    ]
}

entities = {
    "entityids": ["4:abc:1001", "4:abc:1002"],
    "relationshipids": ["5:def:2001", "5:def:2002"]
}

# 执行CHUNK_QUERY查询
def process_chunkids(driver, chunk_ids, entities):
    records = driver.execute_query(
        CHUNK_QUERY, 
        chunksIds=chunk_ids,
        entityIds=entities["entityids"], 
        relationshipIds=entities["relationshipids"]
    )
    
    return {
        "nodes": [...],           # 完整的实体节点信息
        "relationships": [...],   # 完整的关系信息  
        "chunk_data": [...],      # 扩展的文本块信息
        "community_data": []      # 社区信息(此模式下为空)
    }
```

### 5.3 最终响应数据结构

```json
{
    "session_id": "session_123",
    "message": "根据提供的文档，张三是ABC科技公司的CEO...",
    "info": {
        "sources": [
            {
                "chunkdetails": [
                    {
                        "id": "chunk_1_example.pdf",
                        "score": 0.92,
                        "fileName": "example.pdf",
                        "text": "张三担任ABC科技公司CEO一职...",
                        "page_number": 1,
                        "element_id": "4:abc:1234"
                    }
                ]
            }
        ],
        "model": "gpt-4",
        "nodedetails": {
            "chunkdetails": [...],
            "entitydetails": [],
            "communitydetails": []
        },
        "total_tokens": 1245,
        "response_time": 2.34,
        "mode": "graph_vector_fulltext",
        "entities": {
            "entityids": ["4:abc:1001", "4:abc:1002"],
            "relationshipids": ["5:def:2001"]
        }
    },
    "user": "chatbot"
}
```

## 6. 性能优化机制

### 6.1 查询优化策略

**1. 向量索引优化**
```python
# 向量搜索配置
retriever = neo_db.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={
        'top_k': 5,                           # 限制返回数量
        'effective_search_ratio': 2,          # 有效搜索比率
        'score_threshold': 0.7,               # 相似度阈值
        'filter': None                        # 不使用文档过滤
    }
)
```

**2. 实体扩展限制**
```python
# 实体数量控制参数
VECTOR_GRAPH_SEARCH_ENTITY_LIMIT = 40              # 最大实体数
VECTOR_GRAPH_SEARCH_ENTITY_LIMIT_MINMAX_CASE = 20  # 中等相关性路径数
VECTOR_GRAPH_SEARCH_ENTITY_LIMIT_MAX_CASE = 40     # 高相关性路径数
```

**3. 文档压缩优化**
```python
# 文档长度控制
def format_documents(documents, model, chat_mode_settings):
    prompt_token_cutoff = 4  # 默认4个文档
    
    # 根据模型调整
    for model_names, value in CHAT_TOKEN_CUT_OFF.items():
        if model in model_names:
            prompt_token_cutoff = value
            break
    
    # 按相似度排序并截取
    sorted_documents = sorted(
        documents, 
        key=lambda doc: doc.state.get("query_similarity_score", 0), 
        reverse=True
    )
    return sorted_documents[:prompt_token_cutoff]
```

### 6.2 缓存策略

```python
# 会话级缓存
@lru_cache(maxsize=100)
def get_cached_chat_history(session_id):
    return Neo4jChatMessageHistory(...)

# 查询结果缓存
class QueryCache:
    def __init__(self, max_size=1000, ttl=3600):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def get_cached_result(self, query_hash):
        if query_hash in self.cache:
            result, timestamp = self.cache[query_hash]
            if time.time() - timestamp < self.ttl:
                return result
        return None
```

## 7. 错误处理和监控

### 7.1 异常处理策略

```python
def process_chat_response(messages, history, question, model, graph, 
                         document_names, chat_mode_settings):
    try:
        # 主处理逻辑
        llm, doc_retriever, model_version = setup_chat(...)
        docs, transformed_question = retrieve_documents(...)
        
        if docs:
            content, result, total_tokens, formatted_docs = process_documents(...)
        else:
            # 降级处理
            content = "I couldn't find any relevant documents to answer your question."
            result = {"sources": [], "nodedetails": {}, "entities": {}}
            total_tokens = 0
            
    except Exception as e:
        logging.exception(f"Error processing chat response: {str(e)}")
        return {
            "session_id": "",
            "message": "Something went wrong",
            "info": {
                "sources": [],
                "model": model_version,
                "error": f"{type(e).__name__}: {str(e)}",
                "mode": chat_mode_settings["mode"]
            },
            "user": "chatbot"
        }
```

### 7.2 监控指标

```python
# 性能监控
import time
import logging

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
    
    def record_timing(self, operation, duration):
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(duration)
        
        # 记录关键性能指标
        logging.info(f"{operation} completed in {duration:.2f}s")
    
    def record_query_stats(self, query_type, result_count, avg_score):
        logging.info(f"Query: {query_type}, Results: {result_count}, Avg Score: {avg_score:.3f}")

# 使用示例
monitor = PerformanceMonitor()

def retrieve_documents(doc_retriever, messages):
    start_time = time.time()
    try:
        docs = doc_retriever.invoke({"messages": messages})
        retrieval_time = time.time() - start_time
        monitor.record_timing("document_retrieval", retrieval_time)
        return docs, None
    except Exception as e:
        monitor.record_timing("document_retrieval_failed", time.time() - start_time)
        raise
```

## 8. 与其他模式的对比

### 8.1 功能对比矩阵

| 功能特性 | Vector | Graph+Vector | **Graph+Vector+Fulltext** | Global+Vector+Fulltext |
|----------|--------|--------------|---------------------------|------------------------|
| 向量搜索 | ✅ | ✅ | ✅ | ✅ |
| 图遍历 | ❌ | ✅ | ✅ | ✅ |
| 全文搜索 | ❌ | ❌ | ✅ | ✅ |
| 实体扩展 | ❌ | ✅ | ✅ | ✅ |
| 文档过滤 | ✅ | ✅ | ❌ | ❌ |
| 社区搜索 | ❌ | ❌ | ❌ | ✅ |
| 复杂度 | 低 | 中 | **高** | 高 |
| 准确性 | 中 | 高 | **最高** | 高 |

### 8.2 适用场景

**CHAT_VECTOR_GRAPH_FULLTEXT_MODE 最适合：**

1. **复杂查询场景**: 需要同时考虑语义相似度和精确关键词匹配
2. **知识密集型应用**: 实体关系丰富，需要上下文扩展
3. **多文档检索**: 不限制特定文档，全库搜索
4. **高精度要求**: 对答案准确性要求极高的场景

**不适合的场景：**
- 简单事实查询（过度复杂）
- 实时性要求极高的场景（处理时间较长）
- 资源受限环境（内存和计算需求大）

## 9. 部署和运维指南

### 9.1 环境要求

```bash
# Python依赖
langchain==0.1.0
langchain-neo4j==0.2.0
langchain-openai==0.0.2
neo4j==5.15.0
sentence-transformers==2.2.2

# Neo4j配置
NEO4J_VERSION=5.15+
NEO4J_PLUGINS=["apoc", "graph-data-science"]
NEO4J_MEMORY_HEAP=4G
NEO4J_MEMORY_PAGECACHE=2G
```

### 9.2 配置参数调优

```python
# constants.py - 关键参数配置
VECTOR_SEARCH_TOP_K = 5                              # 向量搜索返回数量
VECTOR_GRAPH_SEARCH_ENTITY_LIMIT = 40                # 实体扩展限制
VECTOR_GRAPH_SEARCH_EMBEDDING_MIN_MATCH = 0.3        # 最小相似度阈值
VECTOR_GRAPH_SEARCH_EMBEDDING_MAX_MATCH = 0.9        # 最大相似度阈值
CHAT_DOC_SPLIT_SIZE = 1000                           # 文档分割大小
CHAT_EMBEDDING_FILTER_SCORE_THRESHOLD = 0.8         # 嵌入过滤阈值

# 根据实际场景调优
PRODUCTION_CONFIG = {
    "VECTOR_SEARCH_TOP_K": 8,                        # 生产环境可提高到8
    "VECTOR_GRAPH_SEARCH_ENTITY_LIMIT": 60,          # 增加实体扩展
    "CHAT_EMBEDDING_FILTER_SCORE_THRESHOLD": 0.75    # 降低过滤阈值
}
```

### 9.3 监控和告警

```python
# 监控脚本示例
def health_check():
    """系统健康检查"""
    checks = {
        "neo4j_connection": check_neo4j_connection(),
        "vector_index": check_vector_index_status(),
        "fulltext_index": check_fulltext_index_status(),
        "llm_api": check_llm_api_availability(),
        "memory_usage": check_memory_usage()
    }
    
    failed_checks = [k for k, v in checks.items() if not v]
    
    if failed_checks:
        alert_admin(f"Health check failed: {failed_checks}")
        return False
    
    return True

def performance_alert():
    """性能告警"""
    avg_response_time = get_avg_response_time_last_hour()
    if avg_response_time > 10.0:  # 10秒阈值
        alert_admin(f"High response time: {avg_response_time:.2f}s")
    
    error_rate = get_error_rate_last_hour()
    if error_rate > 0.05:  # 5%错误率阈值
        alert_admin(f"High error rate: {error_rate:.2%}")
```

## 10. 故障排查指南

### 10.1 常见问题诊断

**问题1：检索结果为空**
```python
# 诊断步骤
def diagnose_empty_results(question, document_names):
    # 1. 检查向量索引
    vector_results = test_vector_search(question)
    print(f"Vector search results: {len(vector_results)}")
    
    # 2. 检查全文索引
    fulltext_results = test_fulltext_search(question)
    print(f"Fulltext search results: {len(fulltext_results)}")
    
    # 3. 检查文档存在性
    doc_exists = check_documents_exist(document_names)
    print(f"Documents exist: {doc_exists}")
    
    # 4. 检查相似度阈值
    similarity_scores = get_similarity_scores(question)
    print(f"Max similarity score: {max(similarity_scores) if similarity_scores else 0}")
```

**问题2：响应时间过长**
```python
# 性能分析
def analyze_performance_bottleneck(question):
    with performance_tracer():
        # 测试各个组件耗时
        vector_time = time_vector_search(question)
        graph_expansion_time = time_graph_expansion(question)
        llm_processing_time = time_llm_processing(question)
        
        bottleneck = max([
            ("vector_search", vector_time),
            ("graph_expansion", graph_expansion_time), 
            ("llm_processing", llm_processing_time)
        ], key=lambda x: x[1])
        
        print(f"Performance bottleneck: {bottleneck[0]} ({bottleneck[1]:.2f}s)")
```

## 11. 最佳实践总结

### 11.1 开发最佳实践

1. **查询优化**：
   - 合理设置实体扩展限制
   - 使用相似度阈值过滤低质量结果
   - 实现查询结果缓存

2. **错误处理**：
   - 实现多层次降级策略
   - 提供有意义的错误信息
   - 记录详细的执行日志

3. **性能监控**：
   - 监控关键性能指标
   - 设置合理的告警阈值
   - 定期进行性能优化

### 11.2 运维最佳实践

1. **容量规划**：
   - 根据数据规模配置合适的硬件
   - 预留足够的内存用于向量索引
   - 定期清理无用的会话数据

2. **安全考虑**：
   - 验证用户输入，防止注入攻击
   - 限制查询复杂度，防止资源滥用
   - 保护敏感的API密钥

3. **数据管理**：
   - 定期备份图数据库
   - 监控索引状态和性能
   - 实施数据一致性检查

通过遵循本指南，开发团队可以有效地实现和维护CHAT_VECTOR_GRAPH_FULLTEXT_MODE，为用户提供高质量的智能问答服务。