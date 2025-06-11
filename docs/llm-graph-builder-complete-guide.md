# LLM图构建器完整开发指南

## 概述

本文档详细说明了从本地文档上传到生成知识图谱的完整技术实现，提供了一套可复用的知识图谱构建解决方案。

## 系统架构

### 整体架构图

```
前端 (React/TypeScript)
├── 文件上传组件 (DropZone)
├── 文件管理界面
└── 图可视化组件

后端 (Python/FastAPI)
├── 文件处理模块
├── 文档解析模块
├── 分块处理模块
├── LLM集成模块
├── 向量化模块
└── 图数据库模块

数据存储
├── Neo4j 图数据库
├── 向量索引 (Vector Index)
└── 全文索引 (Fulltext Index)
```

### 核心技术栈

- **前端**: React, TypeScript, Neo4j NDL
- **后端**: Python, FastAPI, LangChain
- **数据库**: Neo4j Graph Database
- **机器学习**: OpenAI/Gemini/Anthropic等LLM, SentenceTransformers
- **文档处理**: PyMuPDF, UnstructuredFileLoader
- **向量化**: Various embedding models

## 完整处理流程

### 1. 文件上传阶段

#### 1.1 前端分块上传
```typescript
// 文件分块上传实现
const uploadFileInChunks = (file: File) => {
  const totalChunks = Math.ceil(file.size / chunkSize);
  const chunkProgressIncrement = 100 / totalChunks;
  let chunkNumber = 1;
  let start = 0;
  let end = chunkSize;
  
  const uploadNextChunk = async () => {
    if (chunkNumber <= totalChunks) {
      const chunk = file.slice(start, end);
      const formData = new FormData();
      formData.append('file', chunk);
      formData.append('chunkNumber', chunkNumber.toString());
      formData.append('totalChunks', totalChunks.toString());
      formData.append('originalname', file.name);
      formData.append('model', model);
      
      // 添加用户凭证
      for (const key in userCredentials) {
        formData.append(key, userCredentials[key]);
      }
      
      const apiResponse = await uploadAPI(chunk, model, chunkNumber, totalChunks, file.name);
      // 处理响应和进度更新
    }
  };
};
```

#### 1.2 后端文件合并
```python
def upload_file(graph, model, chunk, chunk_number: int, total_chunks: int, originalname, uri, chunk_dir, merged_dir):
    gcs_file_cache = os.environ.get('GCS_FILE_CACHE')
    
    if gcs_file_cache == 'True':
        # 上传到GCS
        folder_name = create_gcs_bucket_folder_name_hashed(uri, originalname)
        upload_file_to_gcs(chunk, chunk_number, originalname, BUCKET_UPLOAD, folder_name)
    else:
        # 本地存储
        if not os.path.exists(chunk_dir):
            os.mkdir(chunk_dir)
        
        chunk_file_path = os.path.join(chunk_dir, f"{originalname}_part_{chunk_number}")
        with open(chunk_file_path, "wb") as chunk_file:
            chunk_file.write(chunk.file.read())
    
    # 最后一个分块时合并文件
    if int(chunk_number) == int(total_chunks):
        if gcs_file_cache == 'True':
            file_size = merge_file_gcs(BUCKET_UPLOAD, originalname, folder_name, int(total_chunks))
        else:
            file_size = merge_chunks_local(originalname, int(total_chunks), chunk_dir, merged_dir)
        
        # 创建文档源节点
        create_source_node_in_graph(graph, originalname, file_size, model)
```

### 2. 文档解析阶段

#### 2.1 文档加载器
```python
def load_document_content(file_path):
    file_extension = Path(file_path).suffix.lower()
    encoding_flag = False
    
    if file_extension == '.pdf':
        loader = PyMuPDFLoader(file_path)
        return loader, encoding_flag
    elif file_extension == ".txt":
        encoding = detect_encoding(file_path)
        if encoding.lower() == "utf-8":
            loader = UnstructuredFileLoader(file_path, mode="elements", autodetect_encoding=True)
            return loader, encoding_flag
        else:
            # 处理特殊编码
            with open(file_path, encoding=encoding, errors="replace") as f:
                content = f.read()
            loader = ListLoader([Document(page_content=content, metadata={"source": file_path})])
            encoding_flag = True
            return loader, encoding_flag
    else:
        loader = UnstructuredFileLoader(file_path, mode="elements", autodetect_encoding=True)
        return loader, encoding_flag
```

#### 2.2 支持的文件格式
- **PDF文档**: `.pdf` - 使用PyMuPDFLoader
- **Microsoft Office**: `.docx`, `.pptx`, `.xlsx` - 使用UnstructuredFileLoader
- **图片**: `.jpeg`, `.jpg`, `.png`, `.svg` - OCR处理
- **文本**: `.txt`, `.md`, `.html` - 编码检测和处理

### 3. 文档分块阶段

#### 3.1 分块策略
```python
class CreateChunksofDocument:
    def __init__(self, pages: list[Document], graph: Neo4jGraph):
        self.pages = pages
        self.graph = graph

    def split_file_into_chunks(self, token_chunk_size, chunk_overlap):
        text_splitter = TokenTextSplitter(
            chunk_size=token_chunk_size, 
            chunk_overlap=chunk_overlap
        )
        MAX_TOKEN_CHUNK_SIZE = int(os.getenv('MAX_TOKEN_CHUNK_SIZE', 10000))
        chunk_to_be_created = int(MAX_TOKEN_CHUNK_SIZE / token_chunk_size)
        
        # 根据不同的文档类型处理分块
        if 'page' in self.pages[0].metadata:
            # PDF文档按页分块
            chunks = []
            for i, document in enumerate(self.pages):
                page_number = i + 1
                if len(chunks) >= chunk_to_be_created:
                    break
                for chunk in text_splitter.split_documents([document]):
                    chunks.append(Document(
                        page_content=chunk.page_content, 
                        metadata={'page_number': page_number}
                    ))
        elif 'length' in self.pages[0].metadata:
            # YouTube视频处理时间戳
            chunks_without_time_range = text_splitter.split_documents([self.pages[0]])
            chunks = get_calculated_timestamps(chunks_without_time_range[:chunk_to_be_created], youtube_id)
        else:
            # 常规文档分块
            chunks = text_splitter.split_documents(self.pages)
            
        return chunks[:chunk_to_be_created]
```

#### 3.2 分块参数配置
- `token_chunk_size`: 每个块的最大token数 (默认: 512)
- `chunk_overlap`: 块之间的重叠token数 (默认: 50)
- `MAX_TOKEN_CHUNK_SIZE`: 总体token限制 (默认: 10000)

### 4. 向量化处理阶段

#### 4.1 向量嵌入生成
```python
def create_chunk_embeddings(graph, chunkId_chunkDoc_list, file_name):
    isEmbedding = os.getenv('IS_EMBEDDING')
    embeddings, dimension = EMBEDDING_FUNCTION, EMBEDDING_DIMENSION
    data_for_query = []
    
    for row in chunkId_chunkDoc_list:
        if isEmbedding.upper() == "TRUE":
            embeddings_arr = embeddings.embed_query(row['chunk_doc'].page_content)
            data_for_query.append({
                "chunkId": row['chunk_id'],
                "embeddings": embeddings_arr
            })
    
    # 批量更新向量嵌入
    query_to_create_embedding = """
        UNWIND $data AS row
        MATCH (d:Document {fileName: $fileName})
        MERGE (c:Chunk {id: row.chunkId})
        SET c.embedding = row.embeddings
        MERGE (c)-[:PART_OF]->(d)
    """
    execute_graph_query(graph, query_to_create_embedding, 
                       params={"fileName": file_name, "data": data_for_query})
```

#### 4.2 向量索引创建
```python
def create_chunk_vector_index(graph):
    try:
        vector_index_query = """
        SHOW INDEXES YIELD name, type, labelsOrTypes, properties 
        WHERE name = 'vector' AND type = 'VECTOR' 
        AND 'Chunk' IN labelsOrTypes AND 'embedding' IN properties 
        RETURN name
        """
        vector_index = execute_graph_query(graph, vector_index_query)
        
        if not vector_index:
            vector_store = Neo4jVector(
                embedding=EMBEDDING_FUNCTION,
                graph=graph,
                node_label="Chunk", 
                embedding_node_property="embedding",
                index_name="vector",
                embedding_dimension=EMBEDDING_DIMENSION
            )
            vector_store.create_new_index()
            logging.info("Vector index created successfully")
        else:
            logging.info("Vector index already exists")
    except Exception as e:
        if "EquivalentSchemaRuleAlreadyExists" in str(e):
            logging.info("Vector index already exists, skipping creation.")
        else:
            raise
```

### 5. 实体抽取阶段

#### 5.1 LLM模型配置
```python
def get_llm(model: str):
    model = model.lower().strip()
    env_key = f"LLM_MODEL_CONFIG_{model}"
    env_value = os.environ.get(env_key)
    
    if "gemini" in model:
        model_name = env_value
        credentials, project_id = google.auth.default()
        llm = ChatVertexAI(
            model_name=model_name,
            credentials=credentials,
            project=project_id,
            temperature=0,
            safety_settings={
                HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
                # 其他安全设置...
            }
        )
    elif "openai" in model:
        model_name, api_key = env_value.split(",")
        llm = ChatOpenAI(
            api_key=api_key,
            model=model_name,
            temperature=0
        )
    # 其他模型配置...
    
    return llm, model_name
```

#### 5.2 实体和关系抽取
```python
async def get_graph_from_llm(model, chunkId_chunkDoc_list, allowedNodes, allowedRelationship, chunks_to_combine, additional_instructions=None):
    try:
        llm, model_name = get_llm(model)
        
        # 合并chunks
        combined_chunk_document_list = get_combined_chunks(chunkId_chunkDoc_list, chunks_to_combine)
        
        # 处理允许的节点和关系
        allowed_nodes = [node.strip() for node in allowedNodes.split(',') if node.strip()]
        allowed_relationships = []
        
        if allowedRelationship:
            items = [item.strip() for item in allowedRelationship.split(',') if item.strip()]
            if len(items) % 3 != 0:
                raise LLMGraphBuilderException("allowedRelationship must be a multiple of 3")
            
            for i in range(0, len(items), 3):
                source, relation, target = items[i:i + 3]
                allowed_relationships.append((source, relation, target))
        
        # 使用LLM转换器抽取图文档
        graph_document_list = await get_graph_document_list(
            llm, combined_chunk_document_list, allowed_nodes, 
            allowed_relationships, additional_instructions
        )
        
        return graph_document_list
    except Exception as e:
        logging.error(f"Error in get_graph_from_llm: {e}")
        raise LLMGraphBuilderException(f"Error in getting graph from llm: {e}")
```

#### 5.3 LLM图转换器配置
```python
async def get_graph_document_list(llm, combined_chunk_document_list, allowedNodes, allowedRelationship, additional_instructions=None):
    if additional_instructions:
        additional_instructions = sanitize_additional_instruction(additional_instructions)
    
    if "diffbot_api_key" in dir(llm):
        llm_transformer = llm
    else:
        node_properties = ["description"]
        relationship_properties = ["description"]
        
        llm_transformer = LLMGraphTransformer(
            llm=llm,
            node_properties=node_properties,
            relationship_properties=relationship_properties,
            allowed_nodes=allowedNodes,
            allowed_relationships=allowedRelationship,
            additional_instructions=ADDITIONAL_INSTRUCTIONS + (additional_instructions if additional_instructions else "")
        )
    
    if isinstance(llm, DiffbotGraphTransformer):
        graph_document_list = llm_transformer.convert_to_graph_documents(combined_chunk_document_list)
    else:
        graph_document_list = await llm_transformer.aconvert_to_graph_documents(combined_chunk_document_list)
    
    return graph_document_list
```

### 6. 图构建阶段

#### 6.1 图文档保存
```python
def save_graphDocuments_in_neo4j(graph: Neo4jGraph, graph_document_list: List[GraphDocument], max_retries=3, delay=1):
    retries = 0
    while retries < max_retries:
        try:
            graph.add_graph_documents(graph_document_list, baseEntityLabel=True)
            return
        except TransientError as e:
            if "DeadlockDetected" in str(e):
                retries += 1
                logging.info(f"Deadlock detected. Retrying {retries}/{max_retries} in {delay} seconds...")
                time.sleep(delay)
            else:
                raise
    
    logging.error("Failed to execute query after maximum retries due to persistent deadlocks.")
    raise RuntimeError("Query execution failed after multiple retries due to deadlock.")
```

#### 6.2 关系构建
```python
def merge_relationship_between_chunk_and_entites(graph: Neo4jGraph, graph_documents_chunk_chunk_Id: list):
    batch_data = []
    logging.info("Create HAS_ENTITY relationship between chunks and entities")
    
    for graph_doc_chunk_id in graph_documents_chunk_chunk_Id:
        for node in graph_doc_chunk_id['graph_doc'].nodes:
            query_data = {
                'chunk_id': graph_doc_chunk_id['chunk_id'],
                'node_type': node.type,
                'node_id': node.id
            }
            batch_data.append(query_data)
    
    if batch_data:
        unwind_query = """
            UNWIND $batch_data AS data
            MATCH (c:Chunk {id: data.chunk_id})
            CALL apoc.merge.node([data.node_type], {id: data.node_id}) YIELD node AS n
            MERGE (c)-[:HAS_ENTITY]->(n)
        """
        execute_graph_query(graph, unwind_query, params={"batch_data": batch_data})
```

#### 6.3 块间关系创建
```python
def create_relation_between_chunks(graph, file_name, chunks: List[Document]) -> list:
    batch_data = []
    relationships = []
    previous_chunk_id = None
    firstChunk = True
    
    for index, chunk in enumerate(chunks):
        current_chunk_id = generate_chunk_id(chunk, file_name, index)
        
        batch_data.append({
            "id": current_chunk_id,
            "pg_content": chunk.page_content,
            "position": index,
            "length": len(chunk.page_content),
            "f_name": file_name,
            "content_offset": chunk.metadata.get('content_offset', 0)
        })
        
        # 创建块间关系
        if firstChunk:
            relationships.append({"type": "FIRST_CHUNK", "chunk_id": current_chunk_id})
            firstChunk = False
        else:
            relationships.append({
                "type": "NEXT_CHUNK",
                "previous_chunk_id": previous_chunk_id,
                "current_chunk_id": current_chunk_id
            })
        
        previous_chunk_id = current_chunk_id
    
    # 批量创建Chunk节点和PART_OF关系
    query_to_create_chunk_and_PART_OF_relation = """
        UNWIND $batch_data AS data
        MERGE (c:Chunk {id: data.id})
        SET c.text = data.pg_content, 
            c.position = data.position, 
            c.length = data.length, 
            c.fileName = data.f_name, 
            c.content_offset = data.content_offset
        WITH data, c
        MATCH (d:Document {fileName: data.f_name})
        MERGE (c)-[:PART_OF]->(d)
    """
    execute_graph_query(graph, query_to_create_chunk_and_PART_OF_relation, 
                       params={"batch_data": batch_data})
    
    # 创建FIRST_CHUNK关系
    query_to_create_FIRST_relation = """ 
        UNWIND $relationships AS relationship
        MATCH (d:Document {fileName: $f_name})
        MATCH (c:Chunk {id: relationship.chunk_id})
        FOREACH(r IN CASE WHEN relationship.type = 'FIRST_CHUNK' THEN [1] ELSE [] END |
                MERGE (d)-[:FIRST_CHUNK]->(c))
    """
    execute_graph_query(graph, query_to_create_FIRST_relation, 
                       params={"f_name": file_name, "relationships": relationships})
    
    return relationships
```

### 7. 索引和优化阶段

#### 7.1 全文索引创建
```python
def create_vector_fulltext_indexes(uri, username, password, database):
    types = ["entities", "hybrid"]
    embedding_model = os.getenv('EMBEDDING_MODEL')
    embeddings, dimension = load_embedding_model(embedding_model)
    
    try:
        driver = get_graphDB_driver(uri, username, password, database)
        driver.verify_connectivity()
        
        for index_type in types:
            try:
                create_fulltext(driver, index_type)
                logging.info(f"Full-text index for type '{index_type}' created successfully.")
            except Exception as e:
                logging.error(f"Failed to create full-text index for type '{index_type}': {e}")
        
        # 创建向量索引
        create_vector_index(driver, CHUNK_VECTOR_INDEX_NAME, dimension)
        
    finally:
        driver.close()
```

#### 7.2 KNN图更新
```python
def update_KNN_graph(self):
    """更新具有SIMILAR关系的图节点，基于嵌入向量相似度匹配"""
    index = self.graph.query("""
        show indexes yield * where type = 'VECTOR' and name = 'vector'
    """, session_params={"database": self.graph._database})
    
    knn_min_score = os.environ.get('KNN_MIN_SCORE')
    if len(index) > 0:
        logging.info('update KNN graph')
        self.graph.query("""
            MATCH (c:Chunk)
            WHERE c.embedding IS NOT NULL AND count { (c)-[:SIMILAR]-() } < 5
            CALL db.index.vector.queryNodes('vector', 6, c.embedding) yield node, score
            WHERE node <> c and score >= $score 
            MERGE (c)-[rel:SIMILAR]-(node) 
            SET rel.score = score
        """, {"score": float(knn_min_score)}, 
        session_params={"database": self.graph._database})
```

## 核心配置

### 环境变量配置

```bash
# 数据库配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

# LLM模型配置
LLM_MODEL_CONFIG_openai=gpt-4,your_api_key
LLM_MODEL_CONFIG_gemini=gemini-pro
LLM_MODEL_CONFIG_anthropic=claude-3-sonnet-20240229,your_api_key

# 嵌入模型配置
EMBEDDING_MODEL=sentence_transformer
IS_EMBEDDING=TRUE

# 分块配置
MAX_TOKEN_CHUNK_SIZE=10000
UPDATE_GRAPH_CHUNKS_PROCESSED=20

# 文件存储配置
GCS_FILE_CACHE=False
BUCKET_UPLOAD=your-upload-bucket

# 相似度配置
KNN_MIN_SCORE=0.94
DUPLICATE_SCORE_VALUE=0.95
DUPLICATE_TEXT_DISTANCE=3
```

### 性能优化参数

```python
# 分块处理配置
CHUNK_SIZE = 512  # token数
CHUNK_OVERLAP = 50  # 重叠token数
CHUNKS_TO_COMBINE = 1  # 合并的chunk数量

# 向量搜索配置
VECTOR_SEARCH_TOP_K = 10
VECTOR_GRAPH_SEARCH_ENTITY_LIMIT = 30
VECTOR_GRAPH_SEARCH_EMBEDDING_MIN_MATCH = 0.7
VECTOR_GRAPH_SEARCH_EMBEDDING_MAX_MATCH = 0.9

# 批处理配置
BATCH_SIZE = 20  # 批处理大小
MAX_RETRIES = 3  # 最大重试次数
```

## 性能监控

### 关键指标监控

```python
# 处理时间监控
def monitor_processing_time():
    latency_metrics = {
        "update_embedding": "嵌入向量更新时间",
        "entity_extraction": "实体抽取时间", 
        "save_graphDocuments": "图文档保存时间",
        "relationship_between_chunk_entity": "关系创建时间"
    }
    
    for metric, description in latency_metrics.items():
        logging.info(f"{description}: {processing_time[metric]} seconds")

# 数据量监控
def monitor_data_metrics(file_name):
    count_response = graphDb_data_Access.update_node_relationship_count(file_name)
    metrics = count_response[file_name]
    
    logging.info(f"Chunk节点数: {metrics.get('chunkNodeCount')}")
    logging.info(f"实体节点数: {metrics.get('entityNodeCount')}")
    logging.info(f"关系数量: {metrics.get('relationshipCount')}")
```

## 错误处理

### 常见错误类型

1. **文件处理错误**
   - 文件格式不支持
   - 文件损坏或无法读取
   - 编码问题

2. **LLM处理错误**
   - API超时
   - 模型响应格式错误
   - 配额超限

3. **数据库错误**
   - 连接超时
   - 死锁检测
   - 索引创建失败

### 错误处理策略

```python
def handle_processing_errors(file_name, error):
    """统一的错误处理策略"""
    try:
        if isinstance(error, TransientError):
            # 数据库瞬态错误，重试
            return retry_with_backoff(operation, max_retries=3)
        elif isinstance(error, LLMGraphBuilderException):
            # LLM处理错误，记录并跳过
            logging.error(f"LLM processing failed for {file_name}: {error}")
            update_document_status(file_name, "Failed", str(error))
        else:
            # 其他错误，记录详细信息
            logging.error(f"Unexpected error for {file_name}: {error}")
            update_document_status(file_name, "Failed", str(error))
    except Exception as e:
        logging.critical(f"Error handling failed: {e}")
```

## 部署指南

### Docker部署

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-graph-builder
spec:
  replicas: 3
  selector:
    matchLabels:
      app: llm-graph-builder
  template:
    metadata:
      labels:
        app: llm-graph-builder
    spec:
      containers:
      - name: llm-graph-builder
        image: llm-graph-builder:latest
        ports:
        - containerPort: 8000
        env:
        - name: NEO4J_URI
          valueFrom:
            secretKeyRef:
              name: neo4j-credentials
              key: uri
```

## 总结

本技术指南提供了完整的LLM图构建器实现方案，涵盖了从文件上传到知识图谱生成的所有关键环节。通过遵循本指南，开发者可以：

1. 快速搭建知识图谱构建系统
2. 理解各个组件的作用和配置
3. 根据具体需求进行定制和优化
4. 处理常见的错误和性能问题

该方案具有良好的可扩展性和可维护性，支持多种文档格式和LLM模型，适用于各种知识图谱构建场景。 