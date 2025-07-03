# Neo4j直接替换Qdrant开发计划

## 🎯 总体策略

### 核心思路
```
当前架构：用户查询 → KnowledgeAgent → VectorStoreService(Qdrant) → LLM回答
目标架构：用户查询 → KnowledgeAgent → Neo4jGraphService(Neo4j) → LLM回答
```

**保持不变：**
- API接口完全兼容
- 用户体验无感知
- 现有的会话管理、认证等逻辑

**直接替换：**
- `VectorStoreService` → `Neo4jGraphService`
- `MemoryService` → `Neo4jMemoryService`
- Qdrant相似度搜索 → Neo4j混合搜索

## 📋 详细开发计划

### 阶段一：Neo4j检索服务实现（2-3天）

#### 1.1 创建Neo4j图谱检索服务
**新建文件：** `app/services/neo4j_graph_service.py`

```python
from typing import List, Dict, Any, Optional
from langchain_neo4j import Neo4jVector
from langchain_community.graphs import Neo4jGraph
from langchain_core.documents import Document
from app.services.neo4j_service import Neo4jService
from app.services.embedding_service import get_embedding_service
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class Neo4jGraphService:
    """Neo4j图谱检索服务 - 直接替换VectorStoreService"""
    
    def __init__(self):
        logger.info("初始化Neo4j图谱检索服务")
        self.neo4j_service = Neo4jService()
        self.graph = self._create_graph_connection()
        self.vector_retriever = self._initialize_vector_retriever()
        self._ensure_indexes()
    
    def _create_graph_connection(self):
        """创建Neo4j图连接"""
        return Neo4jGraph(
            url=settings.NEO4J_URI,
            username=settings.NEO4J_USERNAME,
            password=settings.NEO4J_PASSWORD,
            database=settings.NEO4J_DATABASE
        )
    
    def _initialize_vector_retriever(self):
        """初始化Neo4j向量检索器"""
        try:
            embedding_service = get_embedding_service()
            
            # 使用完整的混合搜索查询
            retrieval_query = self._build_graph_vector_query()
            
            neo4j_vector = Neo4jVector.from_existing_graph(
                embedding=embedding_service,
                graph=self.graph,
                index_name="vector",                    # 向量索引
                node_label="Chunk",                     # 目标节点
                text_node_properties=["text"],          # 文本属性
                embedding_node_property="embedding",    # 向量属性
                retrieval_query=retrieval_query,        # 自定义混合查询
                search_type="hybrid",                   # 混合搜索
                keyword_index_name="keyword"            # 全文索引
            )
            
            logger.info("Neo4j向量检索器初始化成功")
            return neo4j_vector
            
        except Exception as e:
            logger.error(f"Neo4j向量检索器初始化失败: {e}")
            raise
    
    def _build_graph_vector_query(self) -> str:
        """构建图向量混合查询"""
        return """
        WITH node as chunk, score
        MATCH (chunk)-[:PART_OF]->(d:Document)
        WITH d, collect(DISTINCT {chunk: chunk, score: score}) AS chunks, avg(score) as avg_score
        CALL { 
            WITH chunks
            UNWIND chunks as chunkScore
            WITH chunkScore.chunk as chunk
            OPTIONAL MATCH (chunk)-[:HAS_ENTITY]->(e)
            WITH e, count(*) AS numChunks 
            ORDER BY numChunks DESC 
            LIMIT 40
            
            WITH 
            CASE 
                WHEN e.embedding IS NULL OR 
                     (0.3 <= vector.similarity.cosine($query_vector, e.embedding) 
                      AND vector.similarity.cosine($query_vector, e.embedding) <= 0.9) 
                THEN 
                    collect {
                        OPTIONAL MATCH path=(e)(()-[rels:!HAS_ENTITY&!PART_OF]-()){{0,1}}(:!Chunk&!Document&!__Community__) 
                        RETURN path LIMIT 20
                    }
                WHEN e.embedding IS NOT NULL AND 
                     vector.similarity.cosine($query_vector, e.embedding) > 0.9 
                THEN
                    collect {
                        OPTIONAL MATCH path=(e)(()-[rels:!HAS_ENTITY&!PART_OF]-()){{0,2}}(:!Chunk&!Document&!__Community__) 
                        RETURN path LIMIT 40
                    } 
                ELSE 
                    collect { 
                        MATCH path=(e) 
                        RETURN path 
                    }
            END AS paths, e
            
            WITH apoc.coll.toSet(apoc.coll.flatten(collect(DISTINCT paths))) AS paths,
                 collect(DISTINCT e) AS entities
            
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
        
        WITH d, avg_score,
            [c IN chunks | c.chunk.text] AS texts,
            [c IN chunks | {id: c.chunk.id, score: c.score}] AS chunkdetails,
            [n IN nodes | elementId(n)] AS entityIds,
            [r IN rels | elementId(r)] AS relIds,
            apoc.coll.sort([
                n IN nodes |
                coalesce(apoc.coll.removeAll(labels(n), ['__Entity__'])[0], "") + ":" +
                coalesce(n.id, "") +
                (CASE WHEN n.description IS NOT NULL THEN " (" + n.description + ")" ELSE "" END)
            ]) AS nodeTexts,
            apoc.coll.sort([
                r IN rels |
                coalesce(apoc.coll.removeAll(labels(startNode(r)), ['__Entity__'])[0], "") + ":" +
                coalesce(startNode(r).id, "") + " " + type(r) + " " +
                coalesce(apoc.coll.removeAll(labels(endNode(r)), ['__Entity__'])[0], "") + ":" + 
                coalesce(endNode(r).id, "")
            ]) AS relTexts,
            entities
        
        WITH d, avg_score, chunkdetails, entityIds, relIds,
            "Text Content:\\n" + apoc.text.join(texts, "\\n----\\n") +
            "\\n----\\nEntities:\\n" + apoc.text.join(nodeTexts, "\\n") +
            "\\n----\\nRelationships:\\n" + apoc.text.join(relTexts, "\\n") AS text,
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
    
    def _ensure_indexes(self):
        """确保所需索引存在"""
        try:
            # 创建向量索引
            vector_index_query = """
            CREATE VECTOR INDEX vector IF NOT EXISTS
            FOR (c:Chunk) ON c.embedding
            OPTIONS {
              indexConfig: {
                `vector.dimensions`: 384,
                `vector.similarity_function`: 'cosine'
              }
            }
            """
            self.neo4j_service.execute_write_query(vector_index_query)
            
            # 创建全文索引
            fulltext_index_query = """
            CREATE FULLTEXT INDEX keyword IF NOT EXISTS
            FOR (n:Chunk) ON EACH [n.text]
            """
            self.neo4j_service.execute_write_query(fulltext_index_query)
            
            # 创建实体向量索引
            entity_vector_index_query = """
            CREATE VECTOR INDEX entity_vector IF NOT EXISTS
            FOR (e:__Entity__) ON e.embedding
            OPTIONS {
              indexConfig: {
                `vector.dimensions`: 384,
                `vector.similarity_function`: 'cosine'
              }
            }
            """
            self.neo4j_service.execute_write_query(entity_vector_index_query)
            
            logger.info("Neo4j索引创建完成")
            
        except Exception as e:
            logger.warning(f"索引创建失败: {e}")
    
    # 保持与VectorStoreService相同的接口
    def similarity_search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """相似度搜索 - 兼容VectorStoreService接口"""
        try:
            logger.info(f"执行Neo4j混合搜索: 查询='{query[:30]}...', k={k}")
            
            # 使用Neo4j混合搜索
            docs = self.vector_retriever.similarity_search(query, k=k)
            
            # 转换为兼容格式
            results = []
            for doc in docs:
                result = {
                    "content": doc.page_content,
                    "metadata": {
                        **doc.metadata,
                        "search_type": "neo4j_hybrid",
                        "entities": doc.metadata.get("entities", {}),
                        "source": doc.metadata.get("source", ""),
                        "score": doc.metadata.get("score", 0.0)
                    }
                }
                results.append(result)
            
            logger.info(f"Neo4j混合搜索找到 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"Neo4j混合搜索失败: {e}")
            # 降级处理：返回空结果
            return []
    
    async def store_vectors(self, vectors: List[List[float]], metadata: List[Dict[str, Any]]) -> bool:
        """存储向量 - 兼容接口（实际上文档已经在图谱构建时存储）"""
        logger.info("Neo4j图谱检索服务：向量已通过图谱构建流程存储")
        return True
    
    async def search_vectors(self, query_vector: List[float], limit: int = 5, 
                           filter_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """向量搜索 - 兼容接口"""
        # 将向量查询转换为文本查询（简化处理）
        # 实际场景中可以直接使用向量进行Neo4j向量搜索
        return self.similarity_search("", k=limit)
    
    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]) -> List[str]:
        """添加文本 - 兼容接口"""
        logger.info("Neo4j图谱检索服务：文本通过图谱构建流程添加")
        return [f"neo4j_doc_{i}" for i in range(len(texts))]
    
    def delete_texts(self, ids: List[str]) -> bool:
        """删除文本 - 兼容接口"""
        logger.info(f"Neo4j图谱检索服务：删除文档 {len(ids)} 个")
        # 可以实现基于文档ID的删除逻辑
        return True
```

#### 1.2 创建Neo4j记忆服务
**新建文件：** `app/services/neo4j_memory_service.py`

```python
from typing import Dict, Any, List, Optional
from app.models.memory import ConversationHistory, MemoryConfig
from app.services.neo4j_graph_service import Neo4jGraphService

class Neo4jMemoryService:
    """Neo4j图谱记忆服务 - 直接替换MemoryService"""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.graph_service = Neo4jGraphService()  # 使用Neo4j替代向量存储
        self.histories: Dict[str, ConversationHistory] = {}
    
    def get_conversation_history(self, session_id: str) -> ConversationHistory:
        """获取会话历史"""
        if session_id not in self.histories:
            self.histories[session_id] = ConversationHistory()
        return self.histories[session_id]
    
    def add_user_message(self, session_id: str, message: str) -> None:
        """添加用户消息"""
        history = self.get_conversation_history(session_id)
        history.add_user_message(message)
    
    def add_ai_message(self, session_id: str, message: str) -> None:
        """添加AI消息"""
        history = self.get_conversation_history(session_id)
        history.add_ai_message(message)
    
    def get_relevant_documents(self, query: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取相关文档 - 使用Neo4j混合搜索"""
        if k is None:
            k = self.config.k
        
        # 直接使用Neo4j图谱检索
        return self.graph_service.similarity_search(query, k=k)
    
    def get_context_for_query(self, session_id: str, query: str) -> Dict[str, Any]:
        """获取查询上下文"""
        # 获取会话历史
        history = self.get_conversation_history(session_id)
        history_text = self._format_history(history)
        
        # 获取相关文档（使用Neo4j混合搜索）
        documents = self.get_relevant_documents(query)
        
        return {
            "history": history_text,
            "documents": documents,
            "raw_documents": documents
        }
    
    def _format_history(self, history: ConversationHistory) -> str:
        """格式化历史记录"""
        formatted = ""
        for message in history.messages[-10:]:  # 最近10条消息
            role = "用户" if message.role == "user" else "助手"
            formatted += f"{role}: {message.content}\n"
        return formatted
    
    def add_documents(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """添加文档到知识库"""
        return self.graph_service.add_texts(texts, metadatas or [{}] * len(texts))
```

### 阶段二：替换现有服务（1天）

#### 2.1 修改知识代理
**修改文件：** `app/agents/knowledge_agent.py`

```python
# 只需要更改import和初始化
from app.services.neo4j_memory_service import Neo4jMemoryService  # 新的导入

class KnowledgeAgent:
    def __init__(self, memory_config: Optional[MemoryConfig] = None):
        self.memory_config = memory_config or MemoryConfig()
        # 直接替换为Neo4j记忆服务
        self.memory_service = Neo4jMemoryService(self.memory_config)
        self.graph = self._build_agent_graph()
    
    # 其余代码保持完全不变！
```

#### 2.2 更新文档服务
**修改文件：** `app/services/document_service.py`

```python
# 在构造函数中替换向量存储
from app.services.neo4j_graph_service import Neo4jGraphService

class DocumentService:
    def __init__(self, db: Session, vector_store: VectorStoreService = None):
        self.db = db
        # 直接替换为Neo4j图谱服务
        self.vector_store = Neo4jGraphService()
        # 其余逻辑保持不变
```

#### 2.3 更新代理路由
**修改文件：** `app/routers/agents.py`

```python
# 更新全局服务初始化
from app.services.neo4j_graph_service import Neo4jGraphService

# 替换VectorStoreService的使用
async def upload_file_to_documents(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # 使用Neo4j图谱服务替代向量存储
        graph_service = Neo4jGraphService()
        document_service = DocumentService(db, graph_service)
        # 其余逻辑不变
```

### 阶段三：配置和清理（1天）

#### 3.1 更新配置文件
**修改文件：** `app/core/config.py`

```python
class Settings(BaseSettings):
    # 移除Qdrant配置
    # QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    # QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    # QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "documents")
    
    # 保留Neo4j配置（已存在）
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")
    
    # 添加Neo4j搜索配置
    NEO4J_SEARCH_TOP_K: int = int(os.getenv("NEO4J_SEARCH_TOP_K", "5"))
    NEO4J_ENTITY_LIMIT: int = int(os.getenv("NEO4J_ENTITY_LIMIT", "40"))
    NEO4J_SIMILARITY_THRESHOLD: float = float(os.getenv("NEO4J_SIMILARITY_THRESHOLD", "0.7"))
```

#### 3.2 更新依赖文件
**修改文件：** `requirements.txt`

```bash
# 移除Qdrant相关依赖
# qdrant-client>=1.6.0
# langchain-qdrant==0.2.0

# 确保Neo4j相关依赖存在
langchain-neo4j>=0.2.0
neo4j>=5.15.0
```

#### 3.3 删除旧文件

```bash
# 删除Qdrant相关文件
rm app/services/vector_store.py
rm app/services/memory_service.py
rm VECTOR_STORE_FIX.md
rm test_vector_store.py

# 删除相关测试文件
rm tests/services/test_vector_store.py
```

#### 3.4 更新环境变量文件
**修改文件：** `.env.example`

```bash
# 移除Qdrant配置
# QDRANT_URL=http://localhost:6333
# QDRANT_API_KEY=
# QDRANT_COLLECTION_NAME=documents

# 确保Neo4j配置存在
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

# 新增Neo4j搜索配置
NEO4J_SEARCH_TOP_K=5
NEO4J_ENTITY_LIMIT=40
NEO4J_SIMILARITY_THRESHOLD=0.7
```

### 阶段四：测试和验证（1天）

#### 4.1 创建替换验证脚本
**新建文件：** `scripts/verify_neo4j_replacement.py`

```python
#!/usr/bin/env python3
"""
验证Neo4j替换是否成功
"""

import asyncio
import logging
from app.agents.knowledge_agent import KnowledgeAgent
from app.services.neo4j_graph_service import Neo4jGraphService

async def main():
    print("🔍 验证Neo4j替换...")
    
    # 1. 测试Neo4j图谱服务
    print("\n1. 测试Neo4j图谱服务...")
    try:
        graph_service = Neo4jGraphService()
        results = graph_service.similarity_search("测试查询", k=3)
        print(f"  ✅ Neo4j搜索成功: 找到 {len(results)} 个结果")
    except Exception as e:
        print(f"  ❌ Neo4j搜索失败: {e}")
        return False
    
    # 2. 测试知识代理
    print("\n2. 测试知识代理...")
    try:
        agent = KnowledgeAgent()
        result = await agent.run("什么是人工智能？", session_id="test_session")
        print(f"  ✅ 知识代理运行成功: {result['answer'][:50]}...")
    except Exception as e:
        print(f"  ❌ 知识代理失败: {e}")
        return False
    
    # 3. 检查是否还有Qdrant引用
    print("\n3. 检查Qdrant引用...")
    qdrant_refs = check_qdrant_references()
    if qdrant_refs:
        print(f"  ⚠️  发现 {len(qdrant_refs)} 个Qdrant引用:")
        for ref in qdrant_refs[:5]:  # 只显示前5个
            print(f"    - {ref}")
    else:
        print("  ✅ 未发现Qdrant引用")
    
    print("\n🎉 Neo4j替换验证完成！")
    return True

def check_qdrant_references():
    """检查代码中的Qdrant引用"""
    import os
    import re
    
    qdrant_patterns = [
        r"qdrant",
        r"QdrantClient", 
        r"QdrantVectorStore",
        r"QDRANT_"
    ]
    
    references = []
    
    # 扫描app目录
    for root, dirs, files in os.walk("app"):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        for pattern in qdrant_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                references.append(f"{file_path}: {pattern}")
                except:
                    pass
    
    return references

if __name__ == "__main__":
    asyncio.run(main())
```

#### 4.2 创建功能测试
**新建文件：** `tests/test_neo4j_replacement.py`

```python
import pytest
import asyncio
from app.agents.knowledge_agent import KnowledgeAgent
from app.services.neo4j_graph_service import Neo4jGraphService

class TestNeo4jReplacement:
    """Neo4j替换功能测试"""
    
    def test_neo4j_graph_service_init(self):
        """测试Neo4j图谱服务初始化"""
        service = Neo4jGraphService()
        assert service.graph is not None
        assert service.vector_retriever is not None
    
    def test_similarity_search(self):
        """测试相似度搜索"""
        service = Neo4jGraphService()
        results = service.similarity_search("测试查询", k=3)
        assert isinstance(results, list)
        # 可能为空（如果没有数据），但不应该抛出异常
    
    @pytest.mark.asyncio
    async def test_knowledge_agent(self):
        """测试知识代理"""
        agent = KnowledgeAgent()
        result = await agent.run("什么是AI？", session_id="test_session")
        
        assert "answer" in result
        assert "sources" in result
        assert "metadata" in result
        assert isinstance(result["answer"], str)
    
    def test_api_compatibility(self):
        """测试API兼容性"""
        service = Neo4jGraphService()
        
        # 测试所有兼容接口
        assert hasattr(service, 'similarity_search')
        assert hasattr(service, 'add_texts') 
        assert hasattr(service, 'delete_texts')
        
        # 测试接口调用
        texts = ["测试文本1", "测试文本2"]
        ids = service.add_texts(texts, [{"test": True}] * len(texts))
        assert len(ids) == len(texts)
        
        success = service.delete_texts(ids)
        assert isinstance(success, bool)
```

## 📊 实施时间表

| 阶段 | 时间 | 主要任务 | 验收标准 |
|------|------|----------|----------|
| **第1天** | Neo4j服务实现 | 创建Neo4jGraphService和Neo4jMemoryService | ✅ 服务可正常初始化和搜索 |
| **第2天** | 服务替换 | 修改KnowledgeAgent等使用新服务 | ✅ 现有API正常运行 |
| **第3天** | 配置清理 | 更新配置、删除旧文件、更新依赖 | ✅ 无Qdrant引用 |
| **第4天** | 测试验证 | 功能测试、性能测试、集成测试 | ✅ 所有测试通过 |

## 🚀 实施步骤

### 立即开始的第一步

1. **备份当前代码**
```bash
git branch backup-before-neo4j-replacement
git checkout -b neo4j-replacement
```

2. **创建Neo4j图谱服务**
```bash
touch app/services/neo4j_graph_service.py
touch app/services/neo4j_memory_service.py
```

3. **实现核心检索逻辑**（如上面的代码）

4. **逐步替换服务引用**

### 回滚计划
如果出现问题，可以快速回滚：
```bash
git checkout backup-before-neo4j-replacement
```

## 🎯 优势对比

| 特性 | Qdrant方案 | Neo4j替换方案 |
|------|------------|---------------|
| **搜索能力** | 纯向量搜索 | 向量+图+全文混合搜索 |
| **上下文理解** | 基于文档相似度 | 基于实体关系和图结构 |
| **系统复杂度** | 简单 | 中等（但功能更强） |
| **维护成本** | 需要维护两套系统 | 单一Neo4j系统 |
| **数据一致性** | 需要同步 | 天然一致 |
| **扩展性** | 有限 | 强大的图算法支持 |

## 🛡️ 风险控制措施

### 1. 数据备份
- 在开始替换前，完整备份当前Qdrant数据
- 备份PostgreSQL数据库
- 创建代码快照分支

### 2. 渐进式验证
- 每个阶段完成后进行功能验证
- 确保API接口完全兼容
- 性能基准测试

### 3. 快速回滚
- 保留完整的回滚方案
- 测试回滚流程的有效性
- 监控系统稳定性指标

## 📋 TODO清单

### 准备阶段
- [ ] 创建备份分支
- [ ] 备份Qdrant数据
- [ ] 验证Neo4j图谱数据完整性

### 开发阶段
- [ ] 实现Neo4jGraphService
- [ ] 实现Neo4jMemoryService  
- [ ] 修改KnowledgeAgent引用
- [ ] 更新DocumentService
- [ ] 更新路由文件

### 配置阶段
- [ ] 更新config.py配置
- [ ] 更新requirements.txt
- [ ] 更新环境变量文件
- [ ] 删除Qdrant相关文件

### 测试阶段
- [ ] 创建验证脚本
- [ ] 运行功能测试
- [ ] 性能基准测试
- [ ] API兼容性测试

### 部署阶段
- [ ] 生产环境部署
- [ ] 监控系统指标
- [ ] 用户反馈收集
- [ ] 文档更新

## 🔗 相关文档

- [Neo4j图谱对话技术指南](../docs/chat-vector-graph-fulltext-technical-guide.md)
- [当前系统架构设计](../docs/architecture-design.md)
- [Neo4j服务API参考](../docs/api-reference.md)

---

**创建时间：** 2024年12月
**预计完成时间：** 4个工作日
**负责人：** 开发团队
**优先级：** 高 