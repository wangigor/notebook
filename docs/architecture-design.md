# LLM图构建器系统架构设计

## 1. 总体架构

### 1.1 系统概览

LLM图构建器是一个端到端的知识图谱构建系统，采用微服务架构，支持多种文档格式的处理和多种LLM模型的集成。

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端层 (UI)    │    │   后端层 (API)   │    │   数据层 (DB)    │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • React应用     │    │ • FastAPI服务   │    │ • Neo4j图数据库 │
│ • 文件上传组件   │◄───┤ • 文档处理服务   │◄───┤ • 向量索引      │
│ • 图可视化组件   │    │ • LLM集成服务   │    │ • 全文索引      │
│ • 用户交互界面   │    │ • 图构建服务     │    │ • 文件存储      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       ▲                       ▲
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   外部集成      │    │   中间件层      │    │   基础设施      │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • LLM API       │    │ • 缓存层        │    │ • Docker容器    │
│ • 嵌入模型API   │    │ • 消息队列      │    │ • Kubernetes    │
│ • 云存储服务    │    │ • 负载均衡      │    │ • 监控告警      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 1.2 核心模块

1. **文档处理模块**: 负责文件上传、解析、分块
2. **知识抽取模块**: 使用LLM进行实体和关系抽取
3. **图构建模块**: 创建和管理知识图谱
4. **向量化模块**: 生成和管理嵌入向量
5. **检索模块**: 提供多模态检索能力
6. **可视化模块**: 图的展示和交互

## 2. 前端架构

### 2.1 组件层级结构

```
App
├── Layout
│   ├── Header
│   ├── Sidebar
│   └── Footer
├── DataSources
│   ├── Local
│   │   ├── DropZone
│   │   └── DropZoneForSmallLayouts
│   ├── AWS
│   │   └── S3Modal
│   ├── GCS
│   └── Web
├── Graph
│   ├── GraphVisualization
│   ├── NodeDetail
│   └── RelationshipDetail
├── ChatBot
│   ├── ChatInterface
│   ├── MessageList
│   └── InputArea
└── Settings
    ├── ModelConfiguration
    ├── SchemaSettings
    └── DatabaseSettings
```

### 2.2 状态管理

```typescript
// 全局状态结构
interface GlobalState {
  user: {
    credentials: UserCredentials;
    isAuthenticated: boolean;
  };
  files: {
    filesData: CustomFile[];
    uploadProgress: UploadProgress[];
    processingStatus: ProcessingStatus[];
  };
  graph: {
    nodes: GraphNode[];
    relationships: GraphRelationship[];
    selectedNode: GraphNode | null;
  };
  chat: {
    messages: ChatMessage[];
    isLoading: boolean;
  };
  settings: {
    model: string;
    allowedNodes: string[];
    allowedRelationships: string[];
  };
}

// Context Providers
const UserCredentialsProvider = ({ children }) => {
  const [userCredentials, setUserCredentials] = useState<UserCredentials>();
  const [connectionStatus, setConnectionStatus] = useState<boolean>(false);
  
  return (
    <UserCredentialsContext.Provider value={{
      userCredentials,
      setUserCredentials,
      connectionStatus,
      setConnectionStatus
    }}>
      {children}
    </UserCredentialsContext.Provider>
  );
};

const FileContextProvider = ({ children }) => {
  const [filesData, setFilesData] = useState<CustomFile[]>([]);
  const [model, setModel] = useState<string>('openai');
  
  return (
    <FileContext.Provider value={{
      filesData,
      setFilesData,
      model,
      setModel
    }}>
      {children}
    </FileContext.Provider>
  );
};
```

### 2.3 API集成层

```typescript
// API调用抽象
class APIClient {
  private baseURL: string;
  
  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }
  
  async upload(formData: FormData): Promise<UploadResponse> {
    return this.post('/upload', formData);
  }
  
  async extract(params: ExtractParams): Promise<ExtractResponse> {
    return this.post('/extract', params);
  }
  
  async query(params: QueryParams): Promise<QueryResponse> {
    return this.post('/graph_query', params);
  }
  
  async chat(message: string): Promise<ChatResponse> {
    return this.post('/chatbot', { message });
  }
  
  private async post(endpoint: string, data: any): Promise<any> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    
    if (!response.ok) {
      throw new Error(`API call failed: ${response.statusText}`);
    }
    
    return response.json();
  }
}
```

## 3. 后端架构

### 3.1 服务层架构

```python
# main.py - 主应用入口
from fastapi import FastAPI, HTTPException
from src.routers import upload, extract, query, chat
from src.middleware import AuthMiddleware, LoggingMiddleware

app = FastAPI(title="LLM Graph Builder API")

# 中间件
app.add_middleware(AuthMiddleware)
app.add_middleware(LoggingMiddleware)

# 路由注册
app.include_router(upload.router, prefix="/api/v1")
app.include_router(extract.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")

# 文档处理服务架构
class DocumentProcessingService:
    def __init__(self):
        self.file_loader = FileLoaderFactory()
        self.chunker = DocumentChunker()
        self.vectorizer = VectorizationService()
        self.extractor = EntityExtractionService()
        self.graph_builder = GraphBuildingService()
    
    async def process_document(self, file_path: str, config: ProcessingConfig):
        # 1. 加载文档
        documents = await self.file_loader.load(file_path)
        
        # 2. 分块处理
        chunks = self.chunker.split(documents, config.chunk_size, config.chunk_overlap)
        
        # 3. 向量化
        embeddings = await self.vectorizer.embed(chunks)
        
        # 4. 实体抽取
        entities = await self.extractor.extract(chunks, config.llm_model)
        
        # 5. 构建图
        graph = await self.graph_builder.build(chunks, entities, embeddings)
        
        return graph

# LLM集成服务
class LLMIntegrationService:
    def __init__(self):
        self.model_registry = ModelRegistry()
        self.prompt_manager = PromptManager()
    
    async def extract_entities(self, text: str, model: str, schema: Schema):
        llm = self.model_registry.get_model(model)
        prompt = self.prompt_manager.get_extraction_prompt(schema)
        
        response = await llm.ainvoke(prompt.format(text=text))
        return self.parse_extraction_response(response)
    
    def parse_extraction_response(self, response: str):
        # 解析LLM响应，提取实体和关系
        parser = GraphDocumentParser()
        return parser.parse(response)

# 图数据库服务
class GraphDatabaseService:
    def __init__(self, uri: str, username: str, password: str):
        self.graph = Neo4jGraph(uri=uri, username=username, password=password)
        self.data_access = GraphDBDataAccess(self.graph)
    
    async def create_document_node(self, document: Document):
        return self.data_access.create_source_node(document)
    
    async def create_chunks(self, chunks: List[Chunk]):
        return self.data_access.create_chunks(chunks)
    
    async def create_entities(self, entities: List[Entity]):
        return self.data_access.create_entities(entities)
    
    async def create_relationships(self, relationships: List[Relationship]):
        return self.data_access.create_relationships(relationships)
```

### 3.2 数据访问层

```python
# 数据访问抽象
from abc import ABC, abstractmethod

class DatabaseInterface(ABC):
    @abstractmethod
    async def create_node(self, node: Node) -> str:
        pass
    
    @abstractmethod
    async def create_relationship(self, rel: Relationship) -> str:
        pass
    
    @abstractmethod
    async def query(self, cypher: str, params: dict) -> List[dict]:
        pass

class Neo4jDataAccess(DatabaseInterface):
    def __init__(self, graph: Neo4jGraph):
        self.graph = graph
    
    async def create_node(self, node: Node) -> str:
        query = """
        MERGE (n:{labels} {{id: $id}})
        SET n += $properties
        RETURN elementId(n) as id
        """.format(labels=":".join(node.labels))
        
        result = await self.execute_query(query, {
            "id": node.id,
            "properties": node.properties
        })
        return result[0]["id"]
    
    async def create_relationship(self, rel: Relationship) -> str:
        query = """
        MATCH (source) WHERE elementId(source) = $source_id
        MATCH (target) WHERE elementId(target) = $target_id
        MERGE (source)-[r:{type}]->(target)
        SET r += $properties
        RETURN elementId(r) as id
        """.format(type=rel.type)
        
        result = await self.execute_query(query, {
            "source_id": rel.source_id,
            "target_id": rel.target_id,
            "properties": rel.properties
        })
        return result[0]["id"]
    
    async def execute_query(self, query: str, params: dict) -> List[dict]:
        return execute_graph_query(self.graph, query, params)

# 仓储模式实现
class DocumentRepository:
    def __init__(self, db: DatabaseInterface):
        self.db = db
    
    async def save(self, document: Document) -> str:
        node = Node(
            id=document.id,
            labels=["Document"],
            properties={
                "fileName": document.fileName,
                "fileSize": document.fileSize,
                "fileType": document.fileType,
                "status": document.status,
                "createdAt": document.createdAt
            }
        )
        return await self.db.create_node(node)
    
    async def find_by_name(self, file_name: str) -> Optional[Document]:
        query = """
        MATCH (d:Document {fileName: $fileName})
        RETURN d
        """
        results = await self.db.query(query, {"fileName": file_name})
        if results:
            return Document.from_dict(results[0]["d"])
        return None

class ChunkRepository:
    def __init__(self, db: DatabaseInterface):
        self.db = db
    
    async def save_batch(self, chunks: List[Chunk]) -> List[str]:
        batch_query = """
        UNWIND $chunks as chunk
        MERGE (c:Chunk {id: chunk.id})
        SET c += chunk.properties
        RETURN elementId(c) as id
        """
        
        chunk_data = [{
            "id": chunk.id,
            "properties": chunk.properties
        } for chunk in chunks]
        
        results = await self.db.query(batch_query, {"chunks": chunk_data})
        return [result["id"] for result in results]
```

### 3.3 业务逻辑层

```python
# 领域模型
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class Document:
    id: str
    fileName: str
    fileSize: int
    fileType: str
    status: str
    createdAt: datetime
    chunks: List['Chunk'] = None

@dataclass
class Chunk:
    id: str
    text: str
    position: int
    length: int
    embedding: List[float] = None
    entities: List['Entity'] = None

@dataclass
class Entity:
    id: str
    type: str
    properties: dict
    embedding: List[float] = None

@dataclass
class Relationship:
    id: str
    type: str
    source_id: str
    target_id: str
    properties: dict = None

# 业务服务
class DocumentProcessingWorkflow:
    def __init__(self, 
                 document_repo: DocumentRepository,
                 chunk_repo: ChunkRepository,
                 entity_repo: EntityRepository,
                 llm_service: LLMIntegrationService,
                 vector_service: VectorizationService):
        self.document_repo = document_repo
        self.chunk_repo = chunk_repo
        self.entity_repo = entity_repo
        self.llm_service = llm_service
        self.vector_service = vector_service
    
    async def process(self, file_path: str, config: ProcessingConfig) -> ProcessingResult:
        try:
            # 1. 创建文档记录
            document = await self.create_document(file_path)
            
            # 2. 加载和分块
            chunks = await self.load_and_chunk_document(file_path, config)
            
            # 3. 保存chunks
            chunk_ids = await self.chunk_repo.save_batch(chunks)
            
            # 4. 向量化
            embeddings = await self.vector_service.embed_chunks(chunks)
            await self.update_chunk_embeddings(chunk_ids, embeddings)
            
            # 5. 知识抽取（实体和关系）
            entities, relationships = await self.extract_knowledge(chunks, config.llm_model)
            
            # 6. 保存实体和关系
            await self.save_entities_and_relationships(entities, relationships, chunk_ids)
            
            # 7. 更新文档状态
            await self.update_document_status(document.id, "Completed")
            
            return ProcessingResult(
                document_id=document.id,
                chunk_count=len(chunks),
                entity_count=len(entities),
                relationship_count=len(relationships),
                status="Success"
            )
            
        except Exception as e:
            await self.update_document_status(document.id, "Failed")
            raise ProcessingError(f"Failed to process document: {str(e)}")
    
    async def extract_knowledge(self, chunks: List[Chunk], llm_model: str) -> Tuple[List[Entity], List[Relationship]]:
        """
        知识抽取：同时抽取实体和关系
        
        优化策略：
        1. 合并实体和关系抽取，减少50%的LLM调用
        2. 统一提示词模板，提高一致性
        3. 并行处理多个chunk，提升性能
        4. 智能去重和过滤，提高质量
        
        Args:
            chunks: 文档分块列表
            llm_model: 使用的LLM模型
            
        Returns:
            元组：(实体列表, 关系列表)
        """
        from app.services.knowledge_extraction_service import KnowledgeExtractionService
        
        knowledge_service = KnowledgeExtractionService()
        entities, relationships = await knowledge_service.extract_knowledge_from_chunks(chunks)
        
        logger.info(f"知识抽取完成：{len(entities)} 个实体，{len(relationships)} 个关系")
        return entities, relationships
    
    async def create_document(self, file_path: str) -> Document:
        file_info = get_file_info(file_path)
        document = Document(
            id=generate_uuid(),
            fileName=file_info.name,
            fileSize=file_info.size,
            fileType=file_info.type,
            status="Processing",
            createdAt=datetime.now()
        )
        await self.document_repo.save(document)
        return document
```

## 4. 数据库设计

### 4.1 图数据模型

```cypher
-- 节点类型定义
(:Document {
    fileName: string,
    fileSize: integer,
    fileType: string,
    status: string,
    createdAt: datetime,
    updatedAt: datetime,
    nodeCount: integer,
    relationshipCount: integer
})

(:Chunk {
    id: string,
    text: string,
    position: integer,
    length: integer,
    fileName: string,
    embedding: vector,
    content_offset: integer
})

(:Entity {
    id: string,
    type: string,
    description: string,
    embedding: vector
})

(:__Community__ {
    id: string,
    level: integer,
    rank: float,
    weight: float,
    summary: string,
    embedding: vector
})

-- 关系类型定义
(:Document)-[:FIRST_CHUNK]->(:Chunk)
(:Chunk)-[:NEXT_CHUNK]->(:Chunk)
(:Chunk)-[:PART_OF]->(:Document)
(:Chunk)-[:HAS_ENTITY]->(:Entity)
(:Entity)-[:RELATED]->(:Entity)
(:Entity)-[:IN_COMMUNITY]->(:__Community__)
(:Chunk)-[:SIMILAR]->(:Chunk)
```

### 4.2 索引设计

```cypher
-- 向量索引
CREATE VECTOR INDEX vector IF NOT EXISTS
FOR (c:Chunk) ON c.embedding
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }
}

CREATE VECTOR INDEX entity_vector IF NOT EXISTS
FOR (e:Entity) ON e.embedding
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }
}

-- 全文索引
CREATE FULLTEXT INDEX entities IF NOT EXISTS
FOR (n:Entity) ON EACH [n.id, n.description]

CREATE FULLTEXT INDEX keyword IF NOT EXISTS
FOR (n:Chunk) ON EACH [n.text]

CREATE FULLTEXT INDEX community_keyword IF NOT EXISTS
FOR (n:`__Community__`) ON EACH [n.summary]

-- 属性索引
CREATE INDEX document_filename IF NOT EXISTS
FOR (d:Document) ON (d.fileName)

CREATE INDEX chunk_filename IF NOT EXISTS
FOR (c:Chunk) ON (c.fileName)

CREATE INDEX entity_id IF NOT EXISTS
FOR (e:Entity) ON (e.id)
```

### 4.3 数据访问模式

```python
# 查询模式定义
class QueryPatterns:
    # 文档相关查询
    GET_DOCUMENT_BY_NAME = """
    MATCH (d:Document {fileName: $fileName})
    RETURN d
    """
    
    GET_DOCUMENT_CHUNKS = """
    MATCH (d:Document {fileName: $fileName})<-[:PART_OF]-(c:Chunk)
    RETURN c ORDER BY c.position
    """
    
    GET_DOCUMENT_STATS = """
    MATCH (d:Document {fileName: $fileName})
    OPTIONAL MATCH (d)<-[:PART_OF]-(c:Chunk)
    OPTIONAL MATCH (c)-[:HAS_ENTITY]->(e:Entity)
    RETURN d.fileName as fileName,
           count(DISTINCT c) as chunkCount,
           count(DISTINCT e) as entityCount
    """
    
    # 向量搜索查询
    VECTOR_SEARCH = """
    CALL db.index.vector.queryNodes($indexName, $topK, $queryVector)
    YIELD node, score
    WHERE score >= $minScore
    RETURN node, score
    ORDER BY score DESC
    """
    
    # 图遍历查询
    ENTITY_NEIGHBORS = """
    MATCH (e:Entity {id: $entityId})
    OPTIONAL MATCH (e)-[r]-(neighbor:Entity)
    RETURN e, collect({relationship: r, neighbor: neighbor}) as neighbors
    """
    
    # 社区检测查询
    COMMUNITY_ENTITIES = """
    MATCH (c:__Community__ {id: $communityId})<-[:IN_COMMUNITY]-(e:Entity)
    RETURN c, collect(e) as entities
    """
```

## 5. 性能优化

### 5.1 数据库优化

```python
# 批量操作优化
class BatchOperationManager:
    def __init__(self, graph: Neo4jGraph, batch_size: int = 1000):
        self.graph = graph
        self.batch_size = batch_size
    
    async def batch_create_nodes(self, nodes: List[Node]):
        for i in range(0, len(nodes), self.batch_size):
            batch = nodes[i:i + self.batch_size]
            await self.create_nodes_batch(batch)
    
    async def create_nodes_batch(self, nodes: List[Node]):
        query = """
        UNWIND $nodes as node
        CALL apoc.merge.node(node.labels, {id: node.id}, node.properties)
        YIELD node as n
        RETURN count(n)
        """
        
        node_data = [{
            "labels": node.labels,
            "id": node.id,
            "properties": node.properties
        } for node in nodes]
        
        await execute_graph_query(self.graph, query, {"nodes": node_data})

# 连接池管理
class ConnectionPoolManager:
    def __init__(self, uri: str, auth: tuple, max_connections: int = 50):
        self.driver = GraphDatabase.driver(
            uri, 
            auth=auth,
            max_connection_pool_size=max_connections,
            connection_timeout=30,
            max_retry_time=15
        )
    
    async def execute_query(self, query: str, params: dict = None):
        async with self.driver.session() as session:
            result = await session.run(query, params)
            return await result.data()
```

### 5.2 缓存策略

```python
# 多层缓存架构
import redis
from functools import wraps

class CacheManager:
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
        self.local_cache = {}
        self.cache_ttl = 3600  # 1小时
    
    def cached(self, key_prefix: str, ttl: int = None):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                cache_key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"
                
                # 1. 检查本地缓存
                if cache_key in self.local_cache:
                    return self.local_cache[cache_key]
                
                # 2. 检查Redis缓存
                cached_result = self.redis_client.get(cache_key)
                if cached_result:
                    result = json.loads(cached_result)
                    self.local_cache[cache_key] = result
                    return result
                
                # 3. 执行原函数
                result = await func(*args, **kwargs)
                
                # 4. 存储到缓存
                ttl_value = ttl or self.cache_ttl
                self.redis_client.setex(cache_key, ttl_value, json.dumps(result))
                self.local_cache[cache_key] = result
                
                return result
            return wrapper
        return decorator

# 使用缓存的服务
class CachedGraphService:
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
    
    @cache_manager.cached("entity_neighbors", ttl=1800)
    async def get_entity_neighbors(self, entity_id: str):
        # 实际的图查询逻辑
        return await self.query_entity_neighbors(entity_id)
    
    @cache_manager.cached("document_stats", ttl=3600)
    async def get_document_statistics(self, file_name: str):
        # 实际的统计查询逻辑
        return await self.query_document_stats(file_name)
```

### 5.3 异步处理

```python
# 异步任务处理
import asyncio
from celery import Celery

# Celery配置
celery_app = Celery(
    'llm_graph_builder',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

@celery_app.task
def process_document_async(file_path: str, config: dict):
    """异步文档处理任务"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        processor = DocumentProcessingService()
        result = loop.run_until_complete(
            processor.process_document(file_path, ProcessingConfig(**config))
        )
        return result
    finally:
        loop.close()

# 批量处理管理器
class BatchProcessingManager:
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_documents_batch(self, documents: List[str], config: ProcessingConfig):
        tasks = []
        for doc in documents:
            task = self.process_document_with_semaphore(doc, config)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self.process_batch_results(results)
    
    async def process_document_with_semaphore(self, document: str, config: ProcessingConfig):
        async with self.semaphore:
            return await self.process_single_document(document, config)
```

## 6. 监控和日志

### 6.1 指标监控

```python
# 性能指标收集
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# 定义指标
document_processing_total = Counter(
    'document_processing_total', 
    'Total number of documents processed',
    ['status']
)

document_processing_duration = Histogram(
    'document_processing_duration_seconds',
    'Time spent processing documents',
    ['document_type']
)

active_connections = Gauge(
    'neo4j_active_connections',
    'Number of active Neo4j connections'
)

# 指标收集装饰器
def monitor_performance(metric_name: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                document_processing_total.labels(status='success').inc()
                return result
            except Exception as e:
                document_processing_total.labels(status='error').inc()
                raise
            finally:
                duration = time.time() - start_time
                document_processing_duration.labels(
                    document_type=kwargs.get('file_type', 'unknown')
                ).observe(duration)
        return wrapper
    return decorator

# 启动监控服务器
start_http_server(8000)
```

### 6.2 结构化日志

```python
# 结构化日志配置
import structlog
import logging

# 配置structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.add_logger_name,
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# 在服务中使用结构化日志
class DocumentProcessingService:
    def __init__(self):
        self.logger = logger.bind(service="document_processing")
    
    async def process_document(self, file_path: str, config: ProcessingConfig):
        process_logger = self.logger.bind(
            file_path=file_path,
            file_type=config.file_type,
            model=config.llm_model
        )
        
        process_logger.info("Starting document processing")
        
        try:
            # 处理逻辑
            result = await self.do_processing(file_path, config)
            
            process_logger.info(
                "Document processing completed",
                chunk_count=result.chunk_count,
                entity_count=result.entity_count,
                processing_time=result.processing_time
            )
            
            return result
            
        except Exception as e:
            process_logger.error(
                "Document processing failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
```

## 7. 安全设计

### 7.1 认证和授权

```python
# JWT认证
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import JWTAuthentication

# 用户模型
class User(BaseUser):
    email: str
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False

# JWT认证配置
jwt_authentication = JWTAuthentication(
    secret=settings.JWT_SECRET,
    lifetime_seconds=3600,
    tokenUrl="auth/jwt/login",
)

# 权限控制
from enum import Enum

class Permission(Enum):
    READ_DOCUMENTS = "read:documents"
    WRITE_DOCUMENTS = "write:documents"
    DELETE_DOCUMENTS = "delete:documents"
    ADMIN_ACCESS = "admin:access"

def require_permission(permission: Permission):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = get_current_user()
            if not has_permission(current_user, permission):
                raise HTTPException(
                    status_code=403,
                    detail="Insufficient permissions"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 使用权限控制
@app.post("/documents")
@require_permission(Permission.WRITE_DOCUMENTS)
async def create_document(document_data: DocumentCreate):
    return await document_service.create(document_data)
```

### 7.2 数据保护

```python
# 数据加密
from cryptography.fernet import Fernet

class DataEncryption:
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """加密敏感数据"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """解密敏感数据"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()

# API输入验证
from pydantic import BaseModel, validator

class DocumentUploadRequest(BaseModel):
    file_name: str
    file_size: int
    model: str
    
    @validator('file_name')
    def validate_file_name(cls, v):
        if not v or len(v) > 255:
            raise ValueError('Invalid file name')
        if any(char in v for char in ['..', '/', '\\']):
            raise ValueError('File name contains invalid characters')
        return v
    
    @validator('file_size')
    def validate_file_size(cls, v):
        if v <= 0 or v > 100 * 1024 * 1024:  # 100MB限制
            raise ValueError('Invalid file size')
        return v

# SQL注入防护
def sanitize_cypher_input(input_string: str) -> str:
    """清理Cypher查询输入"""
    # 移除潜在的恶意字符
    dangerous_chars = [';', '--', '/*', '*/', 'xp_', 'sp_']
    for char in dangerous_chars:
        input_string = input_string.replace(char, '')
    return input_string

# 参数化查询
def safe_execute_query(graph: Neo4jGraph, query: str, params: dict):
    """安全的查询执行"""
    # 验证参数
    validated_params = {}
    for key, value in params.items():
        if isinstance(value, str):
            validated_params[key] = sanitize_cypher_input(value)
        else:
            validated_params[key] = value
    
    return execute_graph_query(graph, query, validated_params)
```

## 8. 部署架构

### 8.1 容器化部署

```yaml
# docker-compose.yml
version: '3.8'

services:
  # 前端服务
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://backend:8000
    depends_on:
      - backend
    networks:
      - app-network

  # 后端服务
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USERNAME=neo4j
      - NEO4J_PASSWORD=password
      - REDIS_URL=redis://redis:6379
    depends_on:
      - neo4j
      - redis
    networks:
      - app-network
    volumes:
      - ./uploads:/app/uploads

  # Neo4j数据库
  neo4j:
    image: neo4j:5.15
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]
    volumes:
      - neo4j_data:/data
    networks:
      - app-network

  # Redis缓存
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - app-network

  # Nginx负载均衡
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend
    networks:
      - app-network

networks:
  app-network:
    driver: bridge

volumes:
  neo4j_data:
```

### 8.2 Kubernetes部署

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-graph-builder-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: llm-graph-builder-backend
  template:
    metadata:
      labels:
        app: llm-graph-builder-backend
    spec:
      containers:
      - name: backend
        image: llm-graph-builder-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: NEO4J_URI
          valueFrom:
            secretKeyRef:
              name: neo4j-credentials
              key: uri
        - name: NEO4J_USERNAME
          valueFrom:
            secretKeyRef:
              name: neo4j-credentials
              key: username
        - name: NEO4J_PASSWORD
          valueFrom:
            secretKeyRef:
              name: neo4j-credentials
              key: password
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30

---
apiVersion: v1
kind: Service
metadata:
  name: llm-graph-builder-backend-service
spec:
  selector:
    app: llm-graph-builder-backend
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: llm-graph-builder-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.llm-graph-builder.com
    secretName: llm-graph-builder-tls
  rules:
  - host: api.llm-graph-builder.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: llm-graph-builder-backend-service
            port:
              number: 80
```

## 9. 扩展性设计

### 9.1 微服务拆分

```python
# 文档处理微服务
@app.route("/document-processor")
class DocumentProcessorService:
    def __init__(self):
        self.loader_service = DocumentLoaderService()
        self.chunker_service = ChunkerService()
    
    async def process(self, file_path: str) -> ProcessingResult:
        # 文档处理逻辑
        pass

# 实体抽取微服务
@app.route("/entity-extractor")
class EntityExtractionService:
    def __init__(self):
        self.llm_service = LLMService()
        self.prompt_service = PromptService()
    
    async def extract(self, chunks: List[Chunk]) -> List[Entity]:
        # 实体抽取逻辑
        pass

# 图构建微服务
@app.route("/graph-builder")
class GraphBuildingService:
    def __init__(self):
        self.graph_db = GraphDatabase()
        self.vector_service = VectorService()
    
    async def build_graph(self, entities: List[Entity]) -> Graph:
        # 图构建逻辑
        pass

# 服务发现和负载均衡
class ServiceRegistry:
    def __init__(self):
        self.services = {}
        self.load_balancer = RoundRobinLoadBalancer()
    
    def register_service(self, service_name: str, instance: ServiceInstance):
        if service_name not in self.services:
            self.services[service_name] = []
        self.services[service_name].append(instance)
    
    def get_service(self, service_name: str) -> ServiceInstance:
        instances = self.services.get(service_name, [])
        if not instances:
            raise ServiceNotAvailableError(f"Service {service_name} not available")
        return self.load_balancer.select(instances)
```

### 9.2 插件架构

```python
# 插件接口定义
from abc import ABC, abstractmethod

class DocumentLoaderPlugin(ABC):
    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        pass
    
    @abstractmethod
    async def load(self, file_path: str) -> List[Document]:
        pass

class LLMPlugin(ABC):
    @abstractmethod
    def get_model_name(self) -> str:
        pass
    
    @abstractmethod
    async def extract_entities(self, text: str, schema: Schema) -> List[Entity]:
        pass

# 插件管理器
class PluginManager:
    def __init__(self):
        self.document_loaders = []
        self.llm_plugins = []
    
    def register_document_loader(self, plugin: DocumentLoaderPlugin):
        self.document_loaders.append(plugin)
    
    def register_llm_plugin(self, plugin: LLMPlugin):
        self.llm_plugins.append(plugin)
    
    def get_document_loader(self, file_path: str) -> DocumentLoaderPlugin:
        for loader in self.document_loaders:
            if loader.can_handle(file_path):
                return loader
        raise NoSuitableLoaderError(f"No loader found for {file_path}")
    
    def get_llm_plugin(self, model_name: str) -> LLMPlugin:
        for plugin in self.llm_plugins:
            if plugin.get_model_name() == model_name:
                return plugin
        raise ModelNotFoundError(f"Model {model_name} not found")

# 示例插件实现
class PDFLoaderPlugin(DocumentLoaderPlugin):
    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith('.pdf')
    
    async def load(self, file_path: str) -> List[Document]:
        loader = PyMuPDFLoader(file_path)
        return loader.load()

class OpenAIPlugin(LLMPlugin):
    def get_model_name(self) -> str:
        return "openai"
    
    async def extract_entities(self, text: str, schema: Schema) -> List[Entity]:
        # OpenAI实体抽取实现
        pass
```

通过这种架构设计，系统具备了良好的可扩展性、可维护性和可测试性，能够适应不同规模和复杂度的知识图谱构建需求。 