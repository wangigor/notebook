## 四、任务处理系统实现

### 1. Celery任务定义
```python
@celery_app.task(bind=True, name="process_document")
def process_document(self, document_id: int, task_id: str, file_path: str):
    """处理文档的主任务"""
    try:
        # 获取任务和相关服务
        task_service = get_task_service()
        document_service = get_document_service()
        storage_service = get_storage_service()
        
        # 更新任务状态为运行中
        task_service.update_task_status(task_id, "RUNNING")
        task_service.update_task_start_time(task_id)
        push_task_update(task_id)  # 推送状态更新
        
        # 定义处理步骤
        steps = [
            {
                "name": "VALIDATE",
                "func": document_service.validate_document,
                "weight": 5,  # 进度权重百分比
            },
            {
                "name": "UPLOAD_TO_STORAGE",  # 步骤：上传到MinIO
                "func": storage_service.upload_file_and_update_document,
                "weight": 10,
            },
            {
                "name": "EXTRACT_TEXT",
                "func": document_service.extract_text_from_file,
                "weight": 30,
            },
            {
                "name": "PREPROCESS",
                "func": document_service.preprocess_text,
                "weight": 15,
            },
            {
                "name": "VECTORIZE",
                "func": document_service.vectorize_document,
                "weight": 30,
            },
            {
                "name": "STORE",
                "func": document_service.store_document_vectors,
                "weight": 10,
            }
        ]
        
        # 执行每个步骤
        document_data = {"file_path": file_path}
        overall_progress = 0
        
        for step in steps:
            # 更新步骤状态
            task_service.update_step_status(task_id, step["name"], "RUNNING")
            task_service.update_step_start_time(task_id, step["name"])
            push_task_update(task_id)  # 推送状态更新
            
            # 执行步骤
            try:
                step_result = step["func"](document_id, **document_data)
                document_data.update(step_result)  # 更新数据用于下一步骤
                
                # 更新步骤完成状态
                task_service.update_step_status(
                    task_id, 
                    step["name"], 
                    "COMPLETED", 
                    progress=100,
                    details={"output": str(step_result)}
                )
                task_service.update_step_complete_time(task_id, step["name"])
                
                # 更新总体进度
                overall_progress += step["weight"]
                task_service.update_task_progress(task_id, overall_progress)
                push_task_update(task_id)  # 推送状态更新
                
            except Exception as e:
                # 步骤失败处理
                logger.error(f"任务步骤 {step['name']} 失败: {str(e)}")
                task_service.update_step_status(
                    task_id, 
                    step["name"], 
                    "FAILED", 
                    error_message=str(e)
                )
                
                # 更新任务状态为失败
                task_service.update_task_status(task_id, "FAILED", error_message=str(e))
                push_task_update(task_id)  # 推送状态更新
                
                # 清理临时文件
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
                return False
        
        # 更新文档状态为已处理
        document_service.update_document_processing_status(document_id, "COMPLETED")
        
        # 更新任务状态为已完成
        task_service.update_task_status(task_id, "COMPLETED", progress=100)
        task_service.update_task_complete_time(task_id)
        push_task_update(task_id)  # 推送状态更新
        
        # 清理临时文件
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return True
        
    except Exception as e:
        # 任务整体异常处理
        logger.error(f"处理文档任务失败: {str(e)}")
        task_service.update_task_status(task_id, "FAILED", error_message=str(e))
        push_task_update(task_id)  # 推送状态更新
        
        # 清理临时文件
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return False
```

### 2. 文档服务修改
```python
class DocumentService:
    # ... 保留其他方法 ...
    
    async def update_document_storage_info(self, document_id, bucket_name, object_key, content_type, file_size, etag):
        """更新文档的存储信息"""
        document = await self.get_document_by_id(document_id)
        if not document:
            raise ValueError(f"文档不存在: {document_id}")
            
        document.bucket_name = bucket_name
        document.object_key = object_key
        document.content_type = content_type
        document.file_size = file_size
        document.etag = etag
        document.updated_at = datetime.now()
        
        self.db.commit()
        return document
        
    # 新增：更新文档向量信息方法
    async def update_document_vector_info(self, document_id, vector_collection_name, vector_count):
        """更新文档的向量存储信息"""
        document = await self.get_document_by_id(document_id)
        if not document:
            raise ValueError(f"文档不存在: {document_id}")
            
        document.vector_collection_name = vector_collection_name
        document.vector_count = vector_count
        document.updated_at = datetime.now()
        
        self.db.commit()
        return document
        
    async def extract_text_from_file(self, document_id, **kwargs):
        """从文件中提取文本"""
        document = await self.get_document_by_id(document_id)
        if not document:
            raise ValueError(f"文档不存在: {document_id}")
            
        temp_file_path = None
        try:
            # 确定文件路径
            file_path = kwargs.get("file_path")
            
            # 如果没有本地文件路径但有MinIO存储信息，则从MinIO下载
            if not file_path and document.object_key:
                storage_service = get_storage_service()
                temp_file_path = await storage_service.download_to_temp(
                    document.bucket_name,
                    document.object_key
                )
                file_path = temp_file_path
                
            if not file_path:
                raise ValueError(f"无法获取文档文件: {document_id}")
                
            # 根据文件类型提取文本
            file_type = document.file_type.lower()
            text = ""
            
            if file_type in ['.pdf']:
                text = self._extract_text_from_pdf(file_path)
            elif file_type in ['.docx', '.doc']:
                text = self._extract_text_from_word(file_path)
            elif file_type in ['.txt']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                raise ValueError(f"不支持的文件类型: {file_type}")
                
            # 如果是临时下载的文件，清理它
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                temp_dir = os.path.dirname(temp_file_path)
                if os.path.exists(temp_dir) and len(os.listdir(temp_dir)) == 0:
                    os.rmdir(temp_dir)
                    
            return {"extracted_text": text}
            
        except Exception as e:
            # 确保清理临时文件
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                temp_dir = os.path.dirname(temp_file_path)
                if os.path.exists(temp_dir) and len(os.listdir(temp_dir)) == 0:
                    os.rmdir(temp_dir)
                    
            logger.error(f"文本提取失败: {str(e)}")
            raise ValueError(f"文本提取失败: {str(e)}")
    
    # 修改：增强向量化方法，支持多粒度
    async def vectorize_document(self, document_id, **kwargs):
        """将文档多粒度向量化：段落级、句子级和文档级"""
        document = await self.get_document_by_id(document_id)
        if not document:
            raise ValueError(f"文档不存在: {document_id}")
        
        # 获取预处理后的文本
        text = kwargs.get("preprocessed_text")
        if not text:
            raise ValueError("未找到预处理文本")
        
        # 获取嵌入服务
        embedding_service = get_embedding_service()
        
        # 1. 文档级向量化
        document_vector = embedding_service.embed_text(text[:8000])  # 取前8000字符作为文档摘要
        
        # 2. 段落级向量化
        paragraphs = self._split_text_into_paragraphs(text)
        paragraph_vectors = []
        
        for i, paragraph in enumerate(paragraphs):
            if len(paragraph.strip()) < 10:  # 忽略过短段落
                continue
            vector = embedding_service.embed_text(paragraph)
            paragraph_vectors.append((
                vector,
                {
                    "text": paragraph,
                    "chunk_index": i,
                    "document_id": document_id,
                    "granularity": "paragraph"
                }
            ))
        
        # 3. 句子级向量化（仅对关键段落进行句子拆分）
        sentence_vectors = []
        important_paragraphs = self._identify_important_paragraphs(paragraphs)
        
        for p_idx in important_paragraphs:
            sentences = self._split_paragraph_into_sentences(paragraphs[p_idx])
            for s_idx, sentence in enumerate(sentences):
                if len(sentence.strip()) < 5:  # 忽略过短句子
                    continue
                vector = embedding_service.embed_text(sentence)
                sentence_vectors.append((
                    vector,
                    {
                        "text": sentence,
                        "paragraph_index": p_idx,
                        "sentence_index": s_idx,
                        "document_id": document_id,
                        "granularity": "sentence"
                    }
                ))
        
        # 合并所有向量
        all_vectors = [
            (document_vector, {
                "text": text[:1000] + "...",  # 文档摘要
                "document_id": document_id,
                "granularity": "document"
            })
        ] + paragraph_vectors + sentence_vectors
        
        return {
            "vectors": all_vectors,
            "chunk_count": len(all_vectors),
            "granularity_counts": {
                "document": 1,
                "paragraph": len(paragraph_vectors),
                "sentence": len(sentence_vectors)
            }
        }
    
    def _identify_important_paragraphs(self, paragraphs):
        """识别文档中的重要段落（简化版：基于长度和关键词）"""
        important_indices = []
        keywords = ["重要", "关键", "总结", "结论", "核心", "关注", "总而言之", "综上所述"]
        
        for i, para in enumerate(paragraphs):
            # 长度适中的段落
            if 100 <= len(para) <= 1000:
                # 包含关键词的段落
                if any(kw in para for kw in keywords):
                    important_indices.append(i)
                # 或长度合适的段落（取样）
                elif len(para) > 200 and i % 3 == 0:  # 每隔3个段落采样一个
                    important_indices.append(i)
        
        # 确保选择的段落数量适中
        if len(important_indices) > 10:
            # 如果过多，均匀采样10个
            return [important_indices[i] for i in range(0, len(important_indices), len(important_indices)//10)]
        
        return important_indices
    
    def _split_text_into_paragraphs(self, text):
        """将文本分割成段落"""
        paragraphs = text.split('\n\n')
        result = []
        
        for p in paragraphs:
            p = p.strip()
            if p:
                # 处理过长段落，按照一定长度再次分割
                if len(p) > 1500:
                    # 以句号、问号、感叹号作为分割点，保证语义完整性
                    sentences = re.split(r'([。？！.?!])', p)
                    current_paragraph = ""
                    
                    for i in range(0, len(sentences), 2):
                        sentence = sentences[i]
                        # 添加标点（如果有）
                        if i + 1 < len(sentences):
                            sentence += sentences[i+1]
                            
                        if len(current_paragraph) + len(sentence) > 1000:
                            if current_paragraph:
                                result.append(current_paragraph)
                            current_paragraph = sentence
                        else:
                            current_paragraph += sentence
                    
                    if current_paragraph:
                        result.append(current_paragraph)
                else:
                    result.append(p)
        
        return result
    
    def _split_paragraph_into_sentences(self, paragraph):
        """将段落分割成句子"""
        # 以句号、问号、感叹号等作为分割点
        sentences = re.split(r'([。？！.?!])', paragraph)
        result = []
        current_sentence = ""
        
        for i in range(0, len(sentences), 2):
            part = sentences[i]
            # 添加标点（如果有）
            if i + 1 < len(sentences):
                part += sentences[i+1]
                
            if part.strip():
                result.append(part)
        
        return result
    
    # 修改：存储向量方法
    async def store_document_vectors(self, document_id, **kwargs):
        """存储文档向量"""
        vectors = kwargs.get("vectors")
        if not vectors:
            raise ValueError("未找到向量数据")
        
        # 使用向量存储服务
        vector_store_service = get_vector_store_service()
        result = await vector_store_service.store_document_vectors(document_id, vectors=vectors)
        
        return result
    
    async def get_context_for_text(self, document_id, text, context_size=2):
        """获取文本的上下文内容"""
        document = await self.get_document_by_id(document_id)
        if not document:
            return ""
        
        # 如果没有原始文本缓存，从MinIO下载并提取
        if not hasattr(self, '_document_text_cache'):
            self._document_text_cache = {}
            
        if document_id not in self._document_text_cache:
            # 下载并提取文本
            temp_file_path = None
            try:
                storage_service = get_storage_service()
                temp_file_path = await storage_service.download_to_temp(
                    document.bucket_name,
                    document.object_key
                )
                
                file_type = document.file_type.lower()
                full_text = ""
                
                if file_type in ['.pdf']:
                    full_text = self._extract_text_from_pdf(temp_file_path)
                elif file_type in ['.docx', '.doc']:
                    full_text = self._extract_text_from_word(temp_file_path)
                elif file_type in ['.txt']:
                    with open(temp_file_path, 'r', encoding='utf-8') as f:
                        full_text = f.read()
                
                # 缓存文本
                self._document_text_cache[document_id] = full_text
                
                # 清理临时文件
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    temp_dir = os.path.dirname(temp_file_path)
                    if os.path.exists(temp_dir) and len(os.listdir(temp_dir)) == 0:
                        os.rmdir(temp_dir)
            
            except Exception as e:
                logger.error(f"获取文档文本失败: {str(e)}")
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                return ""
        
        # 从缓存中获取文本
        full_text = self._document_text_cache.get(document_id, "")
        if not full_text:
            return ""
        
        # 查找文本在原文中的位置
        try:
            # 简化：使用文本匹配查找位置
            text_pos = full_text.find(text)
            if text_pos == -1:
                # 如果找不到完全匹配，尝试模糊匹配
                text_words = set(text.split())
                for i in range(len(full_text) - len(text)):
                    candidate = full_text[i:i+len(text)]
                    candidate_words = set(candidate.split())
                    # 如果有70%的词重叠，认为是相似文本
                    if len(text_words.intersection(candidate_words)) >= 0.7 * len(text_words):
                        text_pos = i
                        break
            
            if text_pos == -1:
                return "上下文提取失败"
            
            # 提取上下文
            context_start = max(0, text_pos - 200 * context_size)
            context_end = min(len(full_text), text_pos + len(text) + 200 * context_size)
            
            context = full_text[context_start:context_end]
            
            # 优化上下文展示
            if context_start > 0:
                context = "..." + context
            if context_end < len(full_text):
                context = context + "..."
                
            # 突出显示原文
            highlighted_context = context.replace(text, f"**{text}**")
            
            return highlighted_context
            
        except Exception as e:
            logger.error(f"提取上下文失败: {str(e)}")
            return ""
    
    async def get_document_ids_by_file_types(self, user_id, file_types):
        """获取指定用户特定文件类型的文档ID列表"""
        query = select(Document.id).where(
            Document.user_id == user_id,
            Document.file_type.in_(file_types),
            Document.processing_status == 'COMPLETED'
        )
        
        result = await self.db.execute(query)
        return [row[0] for row in result.all()]
```

### 3. 状态更新推送函数
```python
def push_task_update(task_id: str):
    """推送任务状态更新"""
    try:
        # 获取完整任务状态
        task_service = get_task_service()
        task_data = task_service.get_task_with_details(task_id)
        
        # 异步推送到WebSocket
        asyncio.run(manager.send_update(task_id, {
            "event": "task_update",
            "data": task_data
        }))
    except Exception as e:
        logger.error(f"推送任务更新失败: {str(e)}")
```

### 4. WebSocket连接管理器
```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        async with self.lock:
            if task_id not in self.active_connections:
                self.active_connections[task_id] = []
            self.active_connections[task_id].append(websocket)

    def disconnect(self, websocket: WebSocket, task_id: str):
        if task_id in self.active_connections:
            self.active_connections[task_id].remove(websocket)
            if len(self.active_connections[task_id]) == 0:
                del self.active_connections[task_id]

    async def send_update(self, task_id: str, message: dict):
        if task_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.append(connection)
                    
            # 移除死连接
            for dead in dead_connections:
                self.active_connections[task_id].remove(dead)
                
            # 如果没有连接了，清理字典
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

manager = ConnectionManager()
``` 