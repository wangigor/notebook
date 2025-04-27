## 二、后端API设计

### 1. 文档上传API
```python
@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """上传文档并启动异步处理任务"""
    try:
        # 保存文件到临时存储
        temp_file_path = await save_upload_file_temp(file)
        
        # 创建文档记录
        document = await document_service.create_document_record(
            user_id=current_user.id,
            name=file.filename or "未命名文档",
            file_type=get_file_extension(file.filename),
            metadata=parse_metadata(metadata),
            content_type=file.content_type
        )
        
        # 创建任务记录
        task_id = str(uuid.uuid4())
        task = await document_service.create_upload_task(
            task_id=task_id,
            document_id=document.id,
            user_id=current_user.id,
            file_path=temp_file_path,
            file_name=file.filename,
            content_type=file.content_type
        )
        
        # 启动异步处理任务
        process_document.delay(document.id, task.id, temp_file_path)
        
        return {
            "success": True,
            "document_id": document.id,
            "task_id": task.id,
            "message": "文档上传成功，正在处理中"
        }
    except Exception as e:
        logger.error(f"上传文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传文档失败: {str(e)}")
```

### 2. 文档下载API
```python
@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    storage_service: StorageService = Depends(get_storage_service),
    current_user: User = Depends(get_current_user)
):
    """获取文档下载链接"""
    # 获取文档信息
    document = await document_service.get_document_by_id(document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 检查权限
    if document.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问此文档")
    
    # 检查文档是否已存储到MinIO
    if not document.object_key or not document.bucket_name:
        raise HTTPException(status_code=400, detail="文档尚未完成处理或不可下载")
    
    # 生成预签名下载URL
    try:
        presigned_url = await storage_service.generate_presigned_url(
            bucket_name=document.bucket_name,
            object_key=document.object_key,
            expires=3600  # 链接有效期1小时
        )
        
        return {
            "success": True,
            "document_name": document.name,
            "download_url": presigned_url,
            "expires_in": 3600
        }
    except Exception as e:
        logger.error(f"生成下载链接失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成下载链接失败: {str(e)}")
```

### 3. 任务状态查询API
```python
@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    task_service: TaskService = Depends(get_task_service),
    current_user: User = Depends(get_current_user)
):
    """获取任务状态"""
    task = await task_service.get_task_with_details(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 检查权限
    if task.document.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问此任务")
    
    return task
```

### 4. WebSocket连接端点
```python
@app.websocket("/ws/tasks/{task_id}")
async def websocket_task_endpoint(
    websocket: WebSocket, 
    task_id: str,
    token: str = Query(...),
    task_service: TaskService = Depends(get_task_service)
):
    # 验证用户权限
    try:
        user = get_user_from_token(token)
        task = await task_service.get_task_by_id(task_id)
        
        if not task or (task.document.user_id != user.id and not user.is_admin):
            await websocket.close(code=4003)
            return
    except:
        await websocket.close(code=4001)
        return
    
    # 建立连接
    await manager.connect(websocket, task_id)
    
    # 发送当前状态
    current_status = await task_service.get_task_with_details(task_id)
    await websocket.send_json({
        "event": "task_update",
        "data": current_status
    })
    
    try:
        # 保持连接
        while True:
            data = await websocket.receive_text()
            # 可选：处理客户端命令，如取消任务
    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id)
```

### 5. 搜索API（新增）
```python
@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db),
    vector_store_service: VectorStoreService = Depends(get_vector_store_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """基于语义搜索用户的文档"""
    # 获取用户专属collection名称
    collection_name = vector_store_service.get_user_collection_name(current_user.id)
    
    # 检查collection是否存在
    if not vector_store_service.client.collection_exists(collection_name):
        return {
            "results": [],
            "total": 0,
            "message": "未找到任何文档"
        }
    
    # 向量化查询文本
    query_vector = embedding_service.embed_text(request.query)
    
    # 在用户collection中搜索
    search_results = vector_store_service.client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=request.limit or 10,
        score_threshold=request.threshold or 0.7
    )
    
    # 处理结果
    results = []
    for result in search_results:
        document_id = result.payload.get("document_id")
        document = await document_service.get_document_by_id(document_id)
        
        if document:
            results.append({
                "score": result.score,
                "document_id": document_id,
                "document_name": document.name,
                "text": result.payload.get("text", ""),
                "metadata": document.metadata
            })
    
    return {
        "results": results,
        "total": len(results)
    }
```

### 6. 混合搜索API（增强）
```python
@router.post("/search/hybrid", response_model=SearchResponse)
async def hybrid_search_documents(
    request: HybridSearchRequest,
    db: Session = Depends(get_db),
    vector_store_service: VectorStoreService = Depends(get_vector_store_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """结合向量搜索和关键词搜索的混合搜索"""
    # 获取用户collection
    collection_name = vector_store_service.get_user_collection_name(current_user.id)
    if not vector_store_service.client.collection_exists(collection_name):
        return {"results": [], "total": 0, "message": "未找到任何文档"}
    
    # 向量化查询文本
    query_vector = embedding_service.embed_text(request.query)
    
    # 构建搜索过滤条件
    filter_conditions = []
    
    # 1. 关键词过滤（全文匹配）
    if request.keywords:
        filter_conditions.append(
            models.FieldCondition(
                key="text",
                match=models.MatchText(text=request.keywords)
            )
        )
    
    # 2. 文档类型过滤
    if request.file_types:
        # 先通过SQL查询获取符合类型的文档ID列表
        document_ids = await document_service.get_document_ids_by_file_types(
            current_user.id, request.file_types
        )
        if document_ids:
            filter_conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchAny(any=document_ids)
                )
            )
        else:
            # 没有符合类型的文档，直接返回空结果
            return {"results": [], "total": 0, "message": "没有匹配的文档类型"}
    
    # 3. 粒度过滤
    if request.granularity:
        filter_conditions.append(
            models.FieldCondition(
                key="granularity",
                match=models.MatchValue(value=request.granularity)
            )
        )
    
    # 执行混合搜索
    search_results = vector_store_service.client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=request.limit or 10,
        score_threshold=request.threshold or 0.7,
        filter=models.Filter(
            must=filter_conditions
        ) if filter_conditions else None
    )
    
    # 处理结果，添加上下文信息
    results = []
    for result in search_results:
        document_id = result.payload.get("document_id")
        document = await document_service.get_document_by_id(document_id)
        
        if document:
            # 获取上下文（针对句子和段落）
            context = ""
            granularity = result.payload.get("granularity")
            if granularity in ["sentence", "paragraph"] and request.include_context:
                context = await document_service.get_context_for_text(
                    document_id, 
                    result.payload.get("text"),
                    context_size=request.context_size or 2
                )
            
            results.append({
                "score": result.score,
                "document_id": document_id,
                "document_name": document.name,
                "text": result.payload.get("text", ""),
                "context": context,
                "granularity": granularity,
                "metadata": document.metadata
            })
    
    return {
        "results": results,
        "total": len(results),
        "filters_applied": {
            "keywords": bool(request.keywords),
            "file_types": request.file_types,
            "granularity": request.granularity
        }
    }
```

### 7. 搜索请求模型
```python
class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10
    threshold: Optional[float] = 0.7

class HybridSearchRequest(BaseModel):
    query: str
    keywords: Optional[str] = None
    file_types: Optional[List[str]] = None
    granularity: Optional[str] = None  # "document", "paragraph", "sentence"
    limit: Optional[int] = 10
    threshold: Optional[float] = 0.7
    include_context: Optional[bool] = True
    context_size: Optional[int] = 2  # 上下文大小（段落数或句子数）

class SearchResponse(BaseModel):
    results: List[Dict]
    total: int
    message: Optional[str] = None
    filters_applied: Optional[Dict] = None
``` 