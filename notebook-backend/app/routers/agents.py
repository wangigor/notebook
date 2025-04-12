from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from uuid import uuid4
import asyncio
import json
from app.agents.knowledge_agent import KnowledgeAgent
from app.models.memory import MemoryConfig, VectorStoreConfig, EmbeddingConfig
from app.auth.dependencies import get_current_user
from app.services.chat_service import ChatService
from app.models.user import User
from app.models.chat import MessageCreate, ChatSessionCreate

router = APIRouter()


# 全局Agent实例，按配置创建
agent = KnowledgeAgent()

class QueryRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    stream: Optional[bool] = False
    use_retrieval: Optional[bool] = True

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    session_id: str

class DocumentUploadRequest(BaseModel):
    texts: List[str]
    metadatas: Optional[List[Dict[str, Any]]] = None

class DocumentUploadResponse(BaseModel):
    document_ids: List[str]
    count: int

class ConfigUpdateRequest(BaseModel):
    memory_config: Optional[MemoryConfig] = None
    vector_store_config: Optional[VectorStoreConfig] = None
    embedding_config: Optional[EmbeddingConfig] = None

class ConfigResponse(BaseModel):
    memory_config: MemoryConfig
    success: bool
    message: str

@router.post("/query", response_model=QueryResponse)
async def query_agent(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends()
):
    """
    查询知识库Agent
    """
    # 如果请求流式响应，重定向到流式接口
    if request.stream:
        return await stream_query_agent(request, current_user, chat_service)
        
    try:
        # 获取或创建会话
        session_id = request.session_id or f"session_{uuid4()}"
        
        # 确保会话存在于数据库中
        db_session = chat_service.get_session_by_id(session_id, current_user.id)
        if not db_session:
            # 创建一个新会话
            db_session = chat_service.create_session(
                ChatSessionCreate(
                    session_id=session_id,
                    user_id=current_user.id,
                    title=request.query[:20] + ("..." if len(request.query) > 20 else "")
                )
            )
        
        # 保存用户消息到数据库
        user_message = MessageCreate(role="user", content=request.query)
        chat_service.add_message(session_id, current_user.id, user_message)
        
        # 处理查询
        result = await agent.run(
            query=request.query, 
            context=request.context or {}, 
            session_id=session_id
        )
        
        # 保存AI回复到数据库
        ai_message = MessageCreate(role="assistant", content=result["answer"])
        chat_service.add_message(session_id, current_user.id, ai_message)
        
        return QueryResponse(
            answer=result["answer"],
            sources=result.get("sources", []),
            metadata=result.get("metadata", {}),
            session_id=session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent执行错误: {str(e)}")

# 流式响应生成器
async def generate_stream_response(
    query: str, 
    session_id: str, 
    context: Optional[Dict[str, Any]], 
    user_id: int,
    chat_service: ChatService
):
    """生成流式响应"""
    try:
        # 确保会话存在于数据库中
        db_session = chat_service.get_session_by_id(session_id, user_id)
        if not db_session:
            # 创建一个新会话
            db_session = chat_service.create_session(
                ChatSessionCreate(
                    session_id=session_id,
                    user_id=user_id,
                    title=query[:20] + ("..." if len(query) > 20 else "")
                )
            )
        
        # 保存用户消息到数据库
        user_message = MessageCreate(role="user", content=query)
        chat_service.add_message(session_id, user_id, user_message)
            
        # 构建SSE格式的响应
        def format_sse(data: dict) -> str:
            # 直接以原始形式发送内容，不进行Unicode转义
            if 'content' in data and isinstance(data['content'], str):
                data_copy = data.copy()
                content = data_copy['content']
                # 移除content，稍后单独添加到JSON
                del data_copy['content']
                # 先序列化剩余部分
                json_without_content = json.dumps(data_copy, ensure_ascii=False)
                # 在JSON末尾前插入content
                json_str = json_without_content[:-1] + ',"content":"' + content.replace('"', '\\"') + '"}'
                return f"data: {json_str}\n\n"
            else:
                return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            
        # 发送思考过程
        yield format_sse({"type": "chunk", "content": "【AI分析中】\n正在分析您的问题...\n"})
        await asyncio.sleep(0.1)
            
        # 准备接收流式响应
        full_answer = ""
        
        # 使用agent的流式方法
        async for chunk in agent.run_stream(query=query, context=context or {}, session_id=session_id):
            if isinstance(chunk, str):
                event_data = {"type": "chunk", "content": chunk}
                full_answer += chunk
                yield format_sse(event_data)
                # 每个字符都需要立即输出，不需要延迟
                # await asyncio.sleep(0.01)  # 移除延迟
            else:
                # 如果不是字符串，可能是dict格式的事件
                event_data = {"type": "chunk", "content": str(chunk)}
                full_answer += str(chunk)
                yield format_sse(event_data)
                # 每个字符都需要立即输出，不需要延迟
                # await asyncio.sleep(0.01)  # 移除延迟
                
        # 保存完整的AI回复到数据库
        if full_answer:
            ai_message = MessageCreate(role="assistant", content=full_answer)
            chat_service.add_message(session_id, user_id, ai_message)
            
        # 发送完成事件
        yield format_sse({"type": "complete"})
            
    except Exception as e:
        error_msg = f"处理流式响应时出错: {str(e)}"
        print(f"流式响应错误: {error_msg}")
        # 发送错误事件
        yield format_sse({"type": "error", "message": error_msg})

async def stream_query_agent(
    request: QueryRequest,
    current_user: User,
    chat_service: ChatService
):
    """
    流式查询知识库Agent
    """
    # 获取或创建会话ID
    session_id = request.session_id or f"session_{uuid4()}"
    
    return StreamingResponse(
        generate_stream_response(
            request.query, 
            session_id, 
            request.context, 
            current_user.id, 
            chat_service
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    request: DocumentUploadRequest, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    上传文档到知识库
    """
    try:
        document_ids = agent.add_documents(
            texts=request.texts,
            metadatas=request.metadatas
        )
        
        return DocumentUploadResponse(
            document_ids=document_ids,
            count=len(document_ids)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档上传错误: {str(e)}")

@router.post("/config", response_model=ConfigResponse)
async def update_config(
    request: ConfigUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    更新Agent配置
    """
    try:
        global agent
        
        # 创建新的配置
        memory_config = MemoryConfig()
        
        # 更新向量存储配置
        if request.vector_store_config:
            memory_config.vector_store_config = request.vector_store_config
        
        # 更新嵌入配置
        if request.embedding_config:
            memory_config.vector_store_config.embedding_config = request.embedding_config
        
        # 更新记忆配置
        if request.memory_config:
            # 保留向量存储配置
            vector_store_config = memory_config.vector_store_config
            memory_config = request.memory_config
            memory_config.vector_store_config = vector_store_config
        
        # 创建新的Agent实例
        agent = KnowledgeAgent(memory_config=memory_config)
        
        return ConfigResponse(
            memory_config=memory_config,
            success=True,
            message="配置更新成功"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置更新错误: {str(e)}")

@router.get("/config", response_model=ConfigResponse)
async def get_config(
    current_user: User = Depends(get_current_user)
):
    """
    获取当前Agent配置
    """
    try:
        return ConfigResponse(
            memory_config=agent.memory_config,
            success=True,
            message="获取配置成功"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置错误: {str(e)}") 