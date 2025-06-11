# 核心模块开发指南

## 概述

本文档详细说明了LLM图构建器的核心模块实现，为开发者提供代码级别的技术指导。

## 模块架构图

```
Backend Core Modules
├── File Processing
│   ├── local_file.py          # 文件加载和解析
│   ├── create_chunks.py       # 文档分块处理
│   └── document_sources/      # 外部数据源
├── LLM Integration
│   ├── llm.py                 # LLM模型集成
│   └── prompts/               # 提示模板
├── Graph Processing
│   ├── make_relationships.py  # 关系构建
│   ├── graphDB_dataAccess.py  # 数据库访问
│   └── vector_index.py        # 向量索引
└── API Layer
    ├── main.py                # 主API路由
    └── entities/              # 数据模型
```

## 1. 文件处理模块

### 1.1 文件加载器 (local_file.py)

**核心功能**: 统一的文档加载接口，支持多种文件格式。

```python
def load_file(file_path: str, file_type: str) -> List[Document]:
    """
    加载文档的核心函数
    
    Args:
        file_path: 文件路径
        file_type: 文件类型 (pdf, docx, txt等)
    
    Returns:
        Document对象列表
    """
    loader, encoding_flag = load_document_content(file_path)
    
    try:
        if encoding_flag:
            documents = loader.load()
        else:
            documents = loader.load()
            
        # 添加元数据
        for doc in documents:
            doc.metadata.update({
                'file_path': file_path,
                'file_type': file_type,
                'loaded_at': datetime.now().isoformat()
            })
            
        return documents
        
    except Exception as e:
        logging.error(f"Failed to load file {file_path}: {e}")
        raise FileLoadError(f"Cannot load file: {e}")

def load_document_content(file_path: str):
    """
    根据文件扩展名选择合适的加载器
    
    支持的格式:
    - PDF: PyMuPDFLoader
    - Word: UnstructuredFileLoader  
    - Text: TextFileLoader with encoding detection
    - Images: OCR processing
    """
    file_extension = Path(file_path).suffix.lower()
    encoding_flag = False
    
    if file_extension == '.pdf':
        loader = PyMuPDFLoader(file_path)
        return loader, encoding_flag
        
    elif file_extension == '.txt':
        encoding = detect_encoding(file_path)
        if encoding.lower() == 'utf-8':
            loader = UnstructuredFileLoader(
                file_path, 
                mode="elements", 
                autodetect_encoding=True
            )
        else:
            # 处理特殊编码
            with open(file_path, encoding=encoding, errors="replace") as f:
                content = f.read()
            loader = ListLoader([
                Document(page_content=content, metadata={"source": file_path})
            ])
            encoding_flag = True
            
        return loader, encoding_flag
        
    elif file_extension in ['.docx', '.pptx', '.xlsx']:
        loader = UnstructuredFileLoader(
            file_path, 
            mode="elements",
            autodetect_encoding=True
        )
        return loader, encoding_flag
        
    elif file_extension in ['.jpg', '.jpeg', '.png', '.svg']:
        # 图片OCR处理
        loader = ImageOCRLoader(file_path)
        return loader, encoding_flag
        
    else:
        # 默认处理器
        loader = UnstructuredFileLoader(
            file_path,
            mode="elements", 
            autodetect_encoding=True
        )
        return loader, encoding_flag

def detect_encoding(file_path: str) -> str:
    """检测文件编码"""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        
    result = chardet.detect(raw_data)
    encoding = result.get('encoding', 'utf-8')
    
    if encoding.lower().startswith('gb'):
        encoding = 'gb18030'
        
    return encoding
```

**关键设计要点**:
- 使用工厂模式根据文件类型选择加载器
- 统一的错误处理和日志记录
- 编码检测确保文本正确解析
- 元数据丰富，便于后续处理

### 1.2 文档分块器 (create_chunks.py)

**核心功能**: 将长文档分割成适合LLM处理的文本块。

```python
class CreateChunksofDocument:
    """文档分块处理类"""
    
    def __init__(self, pages: List[Document], graph: Neo4jGraph):
        self.pages = pages
        self.graph = graph
        
    def split_file_into_chunks(self, token_chunk_size: int, chunk_overlap: int):
        """
        核心分块逻辑
        
        Args:
            token_chunk_size: 每个块的最大token数
            chunk_overlap: 块之间的重叠token数
            
        Returns:
            分块后的Document列表
        """
        # 配置分块器
        text_splitter = TokenTextSplitter(
            chunk_size=token_chunk_size,
            chunk_overlap=chunk_overlap,
            encoding_name="cl100k_base"  # OpenAI tokenizer
        )
        
        # 获取最大处理块数限制
        MAX_TOKEN_CHUNK_SIZE = int(os.getenv('MAX_TOKEN_CHUNK_SIZE', 10000))
        chunk_to_be_created = int(MAX_TOKEN_CHUNK_SIZE / token_chunk_size)
        
        chunks = []
        
        # 根据文档类型采用不同分块策略
        if self._is_pdf_document():
            chunks = self._split_pdf_by_pages(text_splitter, chunk_to_be_created)
        elif self._is_youtube_document():
            chunks = self._split_youtube_with_timestamps(text_splitter, chunk_to_be_created)
        else:
            chunks = self._split_generic_document(text_splitter, chunk_to_be_created)
            
        return chunks[:chunk_to_be_created]
    
    def _is_pdf_document(self) -> bool:
        """检查是否为PDF文档"""
        return (self.pages and 
                'page' in self.pages[0].metadata and 
                'source' in self.pages[0].metadata)
    
    def _split_pdf_by_pages(self, text_splitter, max_chunks: int):
        """PDF按页分块"""
        chunks = []
        
        for i, document in enumerate(self.pages):
            if len(chunks) >= max_chunks:
                break
                
            page_number = i + 1
            page_chunks = text_splitter.split_documents([document])
            
            for chunk in page_chunks:
                if len(chunks) >= max_chunks:
                    break
                    
                # 添加页码信息
                chunk.metadata.update({
                    'page_number': page_number,
                    'chunk_index': len(chunks)
                })
                chunks.append(chunk)
                
        return chunks
    
    def _split_youtube_with_timestamps(self, text_splitter, max_chunks: int):
        """YouTube视频带时间戳分块"""
        base_chunks = text_splitter.split_documents([self.pages[0]])
        limited_chunks = base_chunks[:max_chunks]
        
        # 计算时间戳
        youtube_id = extract_youtube_id(self.pages[0].metadata.get('source', ''))
        return get_calculated_timestamps(limited_chunks, youtube_id)
    
    def _split_generic_document(self, text_splitter, max_chunks: int):
        """通用文档分块"""
        all_chunks = text_splitter.split_documents(self.pages)
        
        # 添加chunk索引
        for i, chunk in enumerate(all_chunks[:max_chunks]):
            chunk.metadata['chunk_index'] = i
            
        return all_chunks[:max_chunks]

def get_calculated_timestamps(chunks: List[Document], youtube_id: str) -> List[Document]:
    """为YouTube分块计算时间戳"""
    try:
        # 获取视频总时长
        total_duration = get_youtube_duration(youtube_id)
        chunk_count = len(chunks)
        
        if chunk_count == 0:
            return chunks
            
        # 平均分配时间
        time_per_chunk = total_duration / chunk_count
        
        for i, chunk in enumerate(chunks):
            start_time = int(i * time_per_chunk)
            end_time = int((i + 1) * time_per_chunk)
            
            chunk.metadata.update({
                'start_time': start_time,
                'end_time': min(end_time, total_duration),
                'youtube_url': f"https://www.youtube.com/watch?v={youtube_id}&t={start_time}s"
            })
            
        return chunks
        
    except Exception as e:
        logging.warning(f"Failed to calculate timestamps: {e}")
        return chunks
```

**设计特点**:
- 支持多种文档类型的差异化分块策略
- Token级别的精确分块控制
- 保留重要的元数据信息
- 可配置的分块参数

## 2. LLM集成模块

### 2.1 LLM模型管理 (llm.py)

**核心功能**: 统一的LLM接口，支持多种模型提供商。

```python
def get_llm(model: str):
    """
    LLM工厂函数，根据模型名称返回对应的LLM实例
    
    支持的模型:
    - OpenAI: gpt-4, gpt-3.5-turbo
    - Google: gemini-pro, gemini-1.5-pro
    - Anthropic: claude-3-sonnet, claude-3-haiku
    - Ollama: 本地模型
    - Diffbot: 专业知识图谱抽取
    """
    model = model.lower().strip()
    env_key = f"LLM_MODEL_CONFIG_{model}"
    env_value = os.environ.get(env_key)
    
    if not env_value:
        raise ValueError(f"Model configuration not found for {model}")
    
    try:
        if "gemini" in model:
            return _create_gemini_llm(model, env_value)
        elif "openai" in model:
            return _create_openai_llm(model, env_value)  
        elif "anthropic" in model:
            return _create_anthropic_llm(model, env_value)
        elif "ollama" in model:
            return _create_ollama_llm(model, env_value)
        elif "diffbot" in model:
            return _create_diffbot_llm(model, env_value)
        else:
            raise ValueError(f"Unsupported model: {model}")
            
    except Exception as e:
        logging.error(f"Failed to create LLM for model {model}: {e}")
        raise LLMCreationError(f"Cannot create LLM: {e}")

def _create_openai_llm(model: str, config: str):
    """创建OpenAI LLM实例"""
    try:
        model_name, api_key = config.split(",", 1)
        
        return ChatOpenAI(
            api_key=api_key.strip(),
            model=model_name.strip(),
            temperature=0,
            max_tokens=4000,
            timeout=120,
            max_retries=3
        ), model_name.strip()
        
    except ValueError:
        raise ValueError("OpenAI config format: model_name,api_key")

def _create_gemini_llm(model: str, config: str):
    """创建Google Gemini LLM实例"""
    model_name = config.strip()
    
    # 设置安全过滤器
    safety_settings = {
        HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DEROGATORY: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_TOXICITY: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_VIOLENCE: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUAL: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_MEDICAL: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    credentials, project_id = google.auth.default()
    
    return ChatVertexAI(
        model_name=model_name,
        credentials=credentials,
        project=project_id,
        temperature=0,
        max_output_tokens=8000,
        safety_settings=safety_settings
    ), model_name

async def get_graph_from_llm(model: str, 
                           chunkId_chunkDoc_list: List[dict],
                           allowedNodes: str,
                           allowedRelationship: str,
                           chunks_to_combine: int,
                           additional_instructions: str = None):
    """
    使用LLM从文档chunks中抽取图结构
    
    Args:
        model: LLM模型名称
        chunkId_chunkDoc_list: chunk ID和Document的映射列表
        allowedNodes: 允许的节点类型
        allowedRelationship: 允许的关系类型
        chunks_to_combine: 合并处理的chunk数量
        additional_instructions: 额外的抽取指令
        
    Returns:
        GraphDocument列表
    """
    try:
        # 获取LLM实例
        llm, model_name = get_llm(model)
        
        # 合并chunks
        combined_chunk_document_list = get_combined_chunks(
            chunkId_chunkDoc_list, 
            chunks_to_combine
        )
        
        # 解析允许的节点和关系
        allowed_nodes = parse_allowed_nodes(allowedNodes)
        allowed_relationships = parse_allowed_relationships(allowedRelationship)
        
        # 获取图文档
        graph_document_list = await get_graph_document_list(
            llm=llm,
            combined_chunk_document_list=combined_chunk_document_list,
            allowed_nodes=allowed_nodes,
            allowed_relationships=allowed_relationships,
            additional_instructions=additional_instructions
        )
        
        logging.info(f"Extracted {len(graph_document_list)} graph documents")
        return graph_document_list
        
    except Exception as e:
        logging.error(f"Graph extraction failed: {e}")
        raise LLMGraphBuilderException(f"Error in getting graph from llm: {e}")

def parse_allowed_nodes(allowedNodes: str) -> List[str]:
    """解析允许的节点类型"""
    if not allowedNodes:
        return []
    return [node.strip() for node in allowedNodes.split(',') if node.strip()]

def parse_allowed_relationships(allowedRelationship: str) -> List[tuple]:
    """解析允许的关系类型"""
    if not allowedRelationship:
        return []
        
    items = [item.strip() for item in allowedRelationship.split(',') if item.strip()]
    
    if len(items) % 3 != 0:
        raise ValueError("Relationship format: source,relation,target")
    
    relationships = []
    for i in range(0, len(items), 3):
        source, relation, target = items[i:i + 3]
        relationships.append((source, relation, target))
        
    return relationships

async def get_graph_document_list(llm, 
                                combined_chunk_document_list: List[Document],
                                allowed_nodes: List[str],
                                allowed_relationships: List[tuple],
                                additional_instructions: str = None):
    """配置并运行LLM图转换器"""
    
    # 处理额外指令
    if additional_instructions:
        additional_instructions = sanitize_additional_instruction(additional_instructions)
    
    # 检查是否为Diffbot
    if hasattr(llm, 'diffbot_api_key'):
        return llm.convert_to_graph_documents(combined_chunk_document_list)
    
    # 配置LLM图转换器
    node_properties = ["description"]
    relationship_properties = ["description"]
    
    llm_transformer = LLMGraphTransformer(
        llm=llm,
        node_properties=node_properties,
        relationship_properties=relationship_properties,
        allowed_nodes=allowed_nodes,
        allowed_relationships=allowed_relationships,
        additional_instructions=ADDITIONAL_INSTRUCTIONS + (additional_instructions or "")
    )
    
    # 异步转换
    return await llm_transformer.aconvert_to_graph_documents(combined_chunk_document_list)
```

**关键特性**:
- 多模型支持的统一接口
- 配置驱动的模型创建
- 异步处理提升性能
- 完善的错误处理和重试机制

## 3. 图处理模块

### 3.1 关系构建器 (make_relationships.py)

**核心功能**: 在chunks、实体之间创建各种类型的关系。

```python
def create_relation_between_chunks(graph: Neo4jGraph, 
                                 file_name: str, 
                                 chunks: List[Document]) -> List[dict]:
    """
    在文档chunks之间创建顺序关系
    
    关系类型:
    - FIRST_CHUNK: 文档到第一个chunk
    - NEXT_CHUNK: chunk之间的顺序关系
    - PART_OF: chunk到文档的从属关系
    """
    batch_data = []
    relationships = []
    previous_chunk_id = None
    first_chunk = True
    
    for index, chunk in enumerate(chunks):
        # 生成唯一的chunk ID
        current_chunk_id = generate_chunk_id(chunk, file_name, index)
        
        # 准备chunk节点数据
        batch_data.append({
            "id": current_chunk_id,
            "pg_content": chunk.page_content,
            "position": index,
            "length": len(chunk.page_content),
            "f_name": file_name,
            "content_offset": chunk.metadata.get('content_offset', 0),
            "page_number": chunk.metadata.get('page_number'),
            "start_time": chunk.metadata.get('start_time'),
            "end_time": chunk.metadata.get('end_time')
        })
        
        # 记录关系信息
        if first_chunk:
            relationships.append({
                "type": "FIRST_CHUNK",
                "chunk_id": current_chunk_id
            })
            first_chunk = False
        else:
            relationships.append({
                "type": "NEXT_CHUNK", 
                "previous_chunk_id": previous_chunk_id,
                "current_chunk_id": current_chunk_id
            })
        
        previous_chunk_id = current_chunk_id
    
    # 批量创建chunk节点
    create_chunks_query = """
        UNWIND $batch_data AS data
        MERGE (c:Chunk {id: data.id})
        SET c.text = data.pg_content,
            c.position = data.position,
            c.length = data.length,
            c.fileName = data.f_name,
            c.content_offset = data.content_offset,
            c.page_number = data.page_number,
            c.start_time = data.start_time,
            c.end_time = data.end_time
        WITH data, c
        MATCH (d:Document {fileName: data.f_name})
        MERGE (c)-[:PART_OF]->(d)
    """
    execute_graph_query(graph, create_chunks_query, {"batch_data": batch_data})
    
    # 创建FIRST_CHUNK关系
    first_chunk_query = """
        UNWIND $relationships AS rel
        MATCH (d:Document {fileName: $f_name})
        MATCH (c:Chunk {id: rel.chunk_id})
        FOREACH(r IN CASE WHEN rel.type = 'FIRST_CHUNK' THEN [1] ELSE [] END |
            MERGE (d)-[:FIRST_CHUNK]->(c))
    """
    execute_graph_query(graph, first_chunk_query, {
        "f_name": file_name, 
        "relationships": relationships
    })
    
    # 创建NEXT_CHUNK关系
    next_chunk_query = """
        UNWIND $relationships AS rel
        MATCH (prev:Chunk {id: rel.previous_chunk_id})
        MATCH (curr:Chunk {id: rel.current_chunk_id})
        FOREACH(r IN CASE WHEN rel.type = 'NEXT_CHUNK' THEN [1] ELSE [] END |
            MERGE (prev)-[:NEXT_CHUNK]->(curr))
    """
    execute_graph_query(graph, next_chunk_query, {"relationships": relationships})
    
    return relationships

def merge_relationship_between_chunk_and_entites(graph: Neo4jGraph, 
                                               graph_documents_chunk_chunk_Id: List[dict]):
    """
    在chunks和entities之间创建HAS_ENTITY关系
    """
    batch_data = []
    
    for graph_doc_chunk_id in graph_documents_chunk_chunk_Id:
        graph_doc = graph_doc_chunk_id['graph_doc']
        chunk_id = graph_doc_chunk_id['chunk_id']
        
        # 为每个实体创建关系数据
        for node in graph_doc.nodes:
            batch_data.append({
                'chunk_id': chunk_id,
                'node_type': node.type,
                'node_id': node.id
            })
    
    if batch_data:
        # 批量创建HAS_ENTITY关系
        query = """
            UNWIND $batch_data AS data
            MATCH (c:Chunk {id: data.chunk_id})
            CALL apoc.merge.node([data.node_type], {id: data.node_id}) YIELD node AS n
            MERGE (c)-[:HAS_ENTITY]->(n)
        """
        execute_graph_query(graph, query, {"batch_data": batch_data})

def create_chunk_embeddings(graph: Neo4jGraph, 
                          chunkId_chunkDoc_list: List[dict], 
                          file_name: str):
    """
    为chunks创建向量嵌入
    """
    is_embedding = os.getenv('IS_EMBEDDING', 'True').upper() == 'TRUE'
    
    if not is_embedding:
        logging.info("Embedding generation disabled")
        return
    
    embeddings, dimension = EMBEDDING_FUNCTION, EMBEDDING_DIMENSION
    data_for_query = []
    
    # 生成嵌入向量
    for row in chunkId_chunkDoc_list:
        try:
            embeddings_arr = embeddings.embed_query(row['chunk_doc'].page_content)
            data_for_query.append({
                "chunkId": row['chunk_id'],
                "embeddings": embeddings_arr
            })
        except Exception as e:
            logging.warning(f"Failed to generate embedding for chunk {row['chunk_id']}: {e}")
    
    if data_for_query:
        # 批量更新嵌入向量
        query = """
            UNWIND $data AS row
            MATCH (c:Chunk {id: row.chunkId})
            SET c.embedding = row.embeddings
        """
        execute_graph_query(graph, query, {"data": data_for_query})
        
        logging.info(f"Created embeddings for {len(data_for_query)} chunks")

class KNNGraphUpdater:
    """基于向量相似度的K近邻图更新器"""
    
    def __init__(self, graph: Neo4jGraph):
        self.graph = graph
        self.knn_min_score = float(os.environ.get('KNN_MIN_SCORE', '0.94'))
    
    def update_KNN_graph(self):
        """更新chunks之间的SIMILAR关系"""
        # 检查向量索引是否存在
        index_check = self.graph.query("""
            SHOW INDEXES YIELD * 
            WHERE type = 'VECTOR' AND name = 'vector'
        """)
        
        if not index_check:
            logging.warning("Vector index not found, skipping KNN update")
            return
        
        logging.info("Updating KNN graph with SIMILAR relationships")
        
        # 为embedding不足5个SIMILAR关系的chunk找到相似节点
        query = """
            MATCH (c:Chunk)
            WHERE c.embedding IS NOT NULL 
            AND count { (c)-[:SIMILAR]-() } < 5
            CALL db.index.vector.queryNodes('vector', 6, c.embedding) 
            YIELD node, score
            WHERE node <> c AND score >= $score
            MERGE (c)-[rel:SIMILAR]-(node)
            SET rel.score = score
        """
        
        self.graph.query(query, {"score": self.knn_min_score})
        logging.info("KNN graph update completed")
```

### 3.2 数据库访问层 (graphDB_dataAccess.py)

**核心功能**: 封装所有Neo4j数据库操作，提供高级的数据访问接口。

```python
class GraphDBDataAccess:
    """图数据库数据访问类"""
    
    def __init__(self, graph: Neo4jGraph):
        self.graph = graph
        
    def create_source_node_in_graph(self, file_name: str, file_size: int, model: str):
        """创建文档源节点"""
        query = """
            MERGE (d:Document {fileName: $file_name})
            SET d.fileSize = $file_size,
                d.status = 'Processing',
                d.model = $model,
                d.createdAt = datetime(),
                d.updatedAt = datetime(),
                d.fileSource = 'local file',
                d.fileType = split($file_name, '.')[-1]
            RETURN d
        """
        
        result = execute_graph_query(self.graph, query, {
            "file_name": file_name,
            "file_size": file_size, 
            "model": model
        })
        
        logging.info(f"Created source node for {file_name}")
        return result

    def update_document_status(self, file_name: str, status: str, 
                             node_count: int = None, 
                             relationship_count: int = None,
                             processing_time: str = None):
        """更新文档处理状态"""
        set_clauses = ["d.status = $status", "d.updatedAt = datetime()"]
        params = {"file_name": file_name, "status": status}
        
        if node_count is not None:
            set_clauses.append("d.nodeCount = $node_count")
            params["node_count"] = node_count
            
        if relationship_count is not None:
            set_clauses.append("d.relationshipCount = $relationship_count") 
            params["relationship_count"] = relationship_count
            
        if processing_time is not None:
            set_clauses.append("d.processingTime = $processing_time")
            params["processing_time"] = processing_time
        
        query = f"""
            MATCH (d:Document {{fileName: $file_name}})
            SET {', '.join(set_clauses)}
            RETURN d
        """
        
        return execute_graph_query(self.graph, query, params)

    def get_document_list(self) -> List[dict]:
        """获取所有文档列表"""
        query = """
            MATCH (d:Document)
            OPTIONAL MATCH (d)<-[:PART_OF]-(c:Chunk)
            OPTIONAL MATCH (c)-[:HAS_ENTITY]->(e)
            WITH d, count(DISTINCT c) AS chunkCount, count(DISTINCT e) AS entityCount
            RETURN d.fileName AS fileName,
                   d.fileSize AS fileSize,
                   d.fileType AS fileType,
                   d.status AS status,
                   d.nodeCount AS nodeCount,
                   d.relationshipCount AS relationshipCount,
                   d.processingTime AS processingTime,
                   d.model AS model,
                   d.createdAt AS createdAt,
                   d.updatedAt AS updatedAt,
                   d.fileSource AS fileSource,
                   chunkCount,
                   entityCount
            ORDER BY d.createdAt DESC
        """
        
        return execute_graph_query(self.graph, query)

    def get_graph_results(self, document_names: List[str]) -> dict:
        """获取指定文档的图数据"""
        query = """
            MATCH (d:Document)
            WHERE d.fileName IN $document_names
            OPTIONAL MATCH (d)<-[:PART_OF]-(c:Chunk)-[:HAS_ENTITY]->(e)
            OPTIONAL MATCH (e)-[r]-(e2)
            WHERE e <> e2
            RETURN {
                nodes: collect(DISTINCT {
                    element_id: elementId(e),
                    labels: labels(e),
                    properties: properties(e)
                }),
                relationships: collect(DISTINCT {
                    element_id: elementId(r),
                    start_node_element_id: elementId(startNode(r)),
                    end_node_element_id: elementId(endNode(r)),
                    type: type(r),
                    properties: properties(r)
                })
            } AS result
        """
        
        results = execute_graph_query(self.graph, query, {
            "document_names": document_names
        })
        
        if results:
            return results[0]["result"]
        return {"nodes": [], "relationships": []}

    def delete_document_and_entities(self, file_names: List[str], 
                                   source_types: List[str],
                                   delete_entities: bool = True):
        """删除文档及相关数据"""
        try:
            for file_name, source_type in zip(file_names, source_types):
                # 删除文档和chunks
                delete_doc_query = """
                    MATCH (d:Document {fileName: $file_name, fileSource: $source_type})
                    OPTIONAL MATCH (d)<-[:PART_OF]-(c:Chunk)
                    DETACH DELETE d, c
                """
                execute_graph_query(self.graph, delete_doc_query, {
                    "file_name": file_name,
                    "source_type": source_type
                })
                
                if delete_entities:
                    # 删除孤立的实体
                    delete_entities_query = """
                        MATCH (e)
                        WHERE NOT (e:Document) AND NOT (e:Chunk) 
                        AND NOT (e:`__Community__`)
                        AND NOT EXISTS { (e)-[:HAS_ENTITY]-() }
                        DETACH DELETE e
                    """
                    execute_graph_query(self.graph, delete_entities_query)
            
            logging.info(f"Deleted {len(file_names)} documents and related entities")
            return {"status": "Success", "deleted_count": len(file_names)}
            
        except Exception as e:
            logging.error(f"Failed to delete documents: {e}")
            raise

    def update_node_relationship_count(self, file_name: str) -> dict:
        """更新并返回文档的节点和关系统计"""
        stats_query = """
            MATCH (d:Document {fileName: $file_name})
            OPTIONAL MATCH (d)<-[:PART_OF]-(c:Chunk)
            OPTIONAL MATCH (c)-[:HAS_ENTITY]->(e)
            OPTIONAL MATCH (e)-[r]-(e2)
            WHERE e <> e2
            WITH d, 
                 count(DISTINCT c) AS chunkNodeCount,
                 count(DISTINCT e) AS entityNodeCount,
                 count(DISTINCT r) AS relationshipCount
            SET d.chunkNodeCount = chunkNodeCount,
                d.entityNodeCount = entityNodeCount,
                d.relationshipCount = relationshipCount
            RETURN {
                chunkNodeCount: chunkNodeCount,
                entityNodeCount: entityNodeCount, 
                relationshipCount: relationshipCount
            } AS stats
        """
        
        result = execute_graph_query(self.graph, stats_query, {
            "file_name": file_name
        })
        
        if result:
            return {file_name: result[0]["stats"]}
        return {file_name: {"chunkNodeCount": 0, "entityNodeCount": 0, "relationshipCount": 0}}

def execute_graph_query(graph: Neo4jGraph, query: str, params: dict = None) -> List[dict]:
    """
    执行图数据库查询的统一接口
    
    Args:
        graph: Neo4j图实例
        query: Cypher查询语句
        params: 查询参数
        
    Returns:
        查询结果列表
    """
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            result = graph.query(query, params or {})
            return result
            
        except Exception as e:
            if "DeadlockDetected" in str(e) and attempt < max_retries - 1:
                logging.warning(f"Deadlock detected, retrying ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay * (2 ** attempt))  # 指数退避
                continue
            else:
                logging.error(f"Graph query failed: {e}")
                raise

def save_graphDocuments_in_neo4j(graph: Neo4jGraph, 
                                graph_document_list: List[GraphDocument],
                                max_retries: int = 3,
                                delay: int = 1):
    """
    将GraphDocument列表保存到Neo4j数据库
    
    Args:
        graph: Neo4j图实例
        graph_document_list: 要保存的图文档列表
        max_retries: 最大重试次数
        delay: 重试延迟时间
    """
    retries = 0
    
    while retries < max_retries:
        try:
            graph.add_graph_documents(
                graph_document_list, 
                baseEntityLabel=True,
                include_source=True
            )
            logging.info(f"Saved {len(graph_document_list)} graph documents")
            return
            
        except Exception as e:
            if "DeadlockDetected" in str(e) and retries < max_retries - 1:
                retries += 1
                logging.warning(f"Deadlock detected, retrying {retries}/{max_retries}")
                time.sleep(delay * retries)
            else:
                logging.error(f"Failed to save graph documents: {e}")
                raise
    
    raise RuntimeError("Failed to save graph documents after maximum retries")
```

## 4. 使用示例

### 4.1 完整的文档处理流程

```python
async def process_document_end_to_end(file_path: str, config: dict):
    """端到端文档处理示例"""
    
    # 1. 初始化组件
    graph = Neo4jGraph(
        url=config['neo4j_uri'],
        username=config['neo4j_username'], 
        password=config['neo4j_password']
    )
    db_access = GraphDBDataAccess(graph)
    
    try:
        # 2. 创建文档源节点
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        db_access.create_source_node_in_graph(file_name, file_size, config['model'])
        
        # 3. 加载文档
        documents = load_file(file_path, get_file_extension(file_path))
        
        # 4. 分块处理
        chunker = CreateChunksofDocument(documents, graph)
        chunks = chunker.split_file_into_chunks(
            config['token_chunk_size'],
            config['chunk_overlap']
        )
        
        # 5. 创建chunk关系
        chunk_relationships = create_relation_between_chunks(graph, file_name, chunks)
        
        # 6. 生成嵌入向量
        chunk_doc_list = [{"chunk_id": rel["chunk_id"], "chunk_doc": chunks[i]} 
                         for i, rel in enumerate(chunk_relationships) 
                         if rel["type"] == "FIRST_CHUNK" or rel.get("current_chunk_id")]
        
        create_chunk_embeddings(graph, chunk_doc_list, file_name)
        
        # 7. LLM实体抽取
        graph_documents = await get_graph_from_llm(
            model=config['model'],
            chunkId_chunkDoc_list=chunk_doc_list,
            allowedNodes=config.get('allowedNodes', ''),
            allowedRelationship=config.get('allowedRelationship', ''),
            chunks_to_combine=config.get('chunks_to_combine', 1),
            additional_instructions=config.get('additional_instructions')
        )
        
        # 8. 保存图文档
        save_graphDocuments_in_neo4j(graph, graph_documents)
        
        # 9. 创建chunk-entity关系
        graph_doc_chunk_list = [
            {"graph_doc": graph_doc, "chunk_id": chunk_doc_list[i]["chunk_id"]}
            for i, graph_doc in enumerate(graph_documents)
        ]
        merge_relationship_between_chunk_and_entites(graph, graph_doc_chunk_list)
        
        # 10. 更新KNN图
        knn_updater = KNNGraphUpdater(graph)
        knn_updater.update_KNN_graph()
        
        # 11. 更新文档状态
        stats = db_access.update_node_relationship_count(file_name)
        db_access.update_document_status(
            file_name, 
            "Completed",
            stats[file_name]["entityNodeCount"],
            stats[file_name]["relationshipCount"]
        )
        
        logging.info(f"Document {file_name} processed successfully")
        return {"status": "Success", "file_name": file_name, "stats": stats}
        
    except Exception as e:
        # 更新失败状态
        db_access.update_document_status(file_name, "Failed")
        logging.error(f"Document processing failed: {e}")
        raise
```

### 4.2 自定义LLM集成

```python
class CustomLLMProvider:
    """自定义LLM提供商实现示例"""
    
    def __init__(self, api_endpoint: str, api_key: str):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
    
    async def agenerate(self, messages: List[BaseMessage]) -> str:
        """异步生成响应"""
        # 实现自定义LLM调用逻辑
        pass
    
    async def aconvert_to_graph_documents(self, documents: List[Document]) -> List[GraphDocument]:
        """转换文档为图结构"""
        # 实现自定义图抽取逻辑
        pass

# 注册自定义LLM
def register_custom_llm(model_name: str, provider_class: type):
    """注册自定义LLM提供商"""
    LLM_REGISTRY[model_name] = provider_class

# 使用自定义LLM
register_custom_llm("custom_model", CustomLLMProvider)
```

## 5. 扩展指南

### 5.1 添加新的文件格式支持

```python
class ExcelDocumentLoader(BaseDocumentLoader):
    """Excel文档加载器示例"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
    
    def load(self) -> List[Document]:
        import pandas as pd
        
        # 读取Excel文件
        dfs = pd.read_excel(self.file_path, sheet_name=None)
        documents = []
        
        for sheet_name, df in dfs.items():
            # 将每个工作表转换为文档
            content = df.to_string(index=False)
            doc = Document(
                page_content=content,
                metadata={
                    "source": self.file_path,
                    "sheet_name": sheet_name,
                    "file_type": "excel"
                }
            )
            documents.append(doc)
            
        return documents

# 在load_document_content函数中添加支持
elif file_extension in ['.xlsx', '.xls']:
    loader = ExcelDocumentLoader(file_path)
    return loader, False
```

### 5.2 添加新的向量化模型

```python
class CustomEmbeddingModel:
    """自定义嵌入模型示例"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = self._load_model()
    
    def _load_model(self):
        # 加载自定义模型
        pass
    
    def embed_query(self, text: str) -> List[float]:
        """生成文本嵌入向量"""
        # 实现自定义嵌入逻辑
        pass
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量生成嵌入向量"""
        return [self.embed_query(text) for text in texts]

# 注册自定义嵌入模型
EMBEDDING_REGISTRY["custom_embedding"] = CustomEmbeddingModel
```

这个核心模块指南提供了LLM图构建器各个核心组件的详细实现说明，开发者可以基于这些模块快速构建自己的知识图谱系统，或者扩展现有功能以满足特定需求。 