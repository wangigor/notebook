from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, File, UploadFile, Form
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
from app.services.document_service import DocumentService
from app.services.vector_store import VectorStoreService
from app.database import get_db
from sqlalchemy.orm import Session
import datetime
import logging
import os
from app.core.config import settings

router = APIRouter()


# 全局Agent实例，按配置创建
agent = KnowledgeAgent()

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    use_retrieval: bool = True
    stream: bool = False

class QueryResponse(BaseModel):
    answer: str
    sources: Optional[List[Dict[str, Any]]] = None

class DocumentUploadRequest(BaseModel):
    texts: List[str]
    metadatas: Optional[List[Dict[str, Any]]] = None

class DocumentUploadResponse(BaseModel):
    document_ids: List[str]
    count: int

class ConfigUpdateRequest(BaseModel):
    # 允许更新特定的 Agent 配置项
    max_token_limit: Optional[int] = None
    return_messages: Optional[bool] = None
    return_source_documents: Optional[bool] = None
    k: Optional[int] = None

class ConfigResponse(BaseModel):
    max_token_limit: int
    return_messages: bool
    return_source_documents: bool
    k: int
    vector_store_url: str
    embedding_model: str
    success: bool
    message: str

@router.post("/query", response_model=QueryResponse)
async def query_agent(
    request: QueryRequest,
    chat_service: ChatService = Depends(ChatService),
    current_user: User = Depends(get_current_user)
):
    """
    使用Agent查询知识库
    """
    if request.stream:
        return StreamingResponse(
            generate_stream_response(
                query=request.query, 
                session_id=request.session_id or f"session_{uuid4()}", # 确保总是有session_id
                context={"use_retrieval": request.use_retrieval},
                user_id=current_user.id,
                chat_service=chat_service
            ),
            media_type="text/event-stream"
        )
    
    try:
        result = await agent.run(
            query=request.query,
            context={"use_retrieval": request.use_retrieval},
            session_id=request.session_id or f"session_{uuid4()}" # 确保总是有session_id
        )
        
        return QueryResponse(
            answer=result["answer"],
            sources=result["sources"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

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
        logger = logging.getLogger(__name__)
        logger.info(f"开始处理流式响应: 会话ID={session_id}, 查询={query[:30]}...")
        
        # 确保会话存在于数据库中
        db_session = chat_service.get_session_by_id(session_id, user_id)
        if not db_session:
            # 创建一个新会话
            logger.info(f"为用户 {user_id} 创建新会话: {session_id}")
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
        logger.info(f"已保存用户消息到会话 {session_id}")
            
        # 构建SSE格式的响应
        def format_sse(data: dict) -> str:
            """格式化为SSE格式"""
            try:
                # 使用标准的JSON序列化，不做特殊处理
                json_str = json.dumps(data, ensure_ascii=False)
                return f"data: {json_str}\n\n"
            except Exception as e:
                logger.error(f"SSE格式化错误: {str(e)}")
                # 失败时尝试简单序列化
                return f"data: {{'type': 'error', 'message': 'SSE格式化错误'}}\n\n"
            
        # 发送思考过程
        yield format_sse({"type": "chunk", "content": "【AI分析中】\n正在分析您的问题...\n"})
        await asyncio.sleep(0.1)
            
        # 准备接收流式响应
        full_answer = ""
        
        # 使用agent的流式方法
        try:
            logger.info(f"启动Agent流式响应 for session: {session_id}")
            async for chunk in agent.run_stream(query=query, context=context or {}, session_id=session_id):
                if isinstance(chunk, str) and chunk.strip():
                    event_data = {"type": "chunk", "content": chunk}
                    full_answer += chunk
                    yield format_sse(event_data)
                elif isinstance(chunk, dict):
                    # 如果是字典，直接发送
                    event_data = {"type": "chunk", "content": json.dumps(chunk)}
                    full_answer += json.dumps(chunk)
                    yield format_sse(event_data)
                else:
                    # 忽略空响应
                    pass
        except Exception as e:
            logger.error(f"Agent流式处理错误 for session {session_id}: {str(e)}", exc_info=True)
            error_msg = f"处理查询时出错: {str(e)}"
            yield format_sse({"type": "error", "message": error_msg})
            # 确保我们有一些内容来保存
            if not full_answer:
                full_answer = f"处理您的查询时发生错误: {str(e)}"
                
        # 保存完整的AI回复到数据库
        if full_answer:
            ai_message = MessageCreate(role="assistant", content=full_answer)
            chat_service.add_message(session_id, user_id, ai_message)
            logger.info(f"已保存AI响应到会话 {session_id}, 长度: {len(full_answer)}")
            
        # 发送完成事件
        yield format_sse({"type": "complete", "content": ""})
        logger.info(f"流式响应完成 for session: {session_id}")
            
    except Exception as e:
        error_msg = f"处理流式响应时出错 for session {session_id}: {str(e)}"
        logging.error(f"流式响应错误: {error_msg}", exc_info=True)
        # 发送错误事件
        yield format_sse({"type": "error", "message": error_msg})

# 废弃的旧上传端点 - 使用新的文档管理功能替代
@router.post("/upload", deprecated=True)
async def upload_documents_deprecated(
    request: DocumentUploadRequest, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    上传文档到知识库（已废弃，请使用 /api/documents/upload 替代）
    """
    raise HTTPException(status_code=410, detail="此端点已废弃，请使用 /api/documents/upload 替代")

# 新的上传端点 - 支持文件上传直接转发到文档管理API
@router.post("/upload-file")
async def upload_file_to_documents(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传文件到文档管理（转发到 /api/documents/upload）
    """
    try:
        # 创建文档服务
        # VectorStoreService 现在从settings获取配置, 不需要传参
        vector_store = VectorStoreService()
        document_service = DocumentService(db, vector_store)
        
        # 解析元数据
        parsed_metadata = {}
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except:
                parsed_metadata = {"notes": metadata}
        
        # 处理文件
        document = await document_service.process_file(
            file=file,
            user_id=current_user.id,
            metadata=parsed_metadata
        )
        
        return {
            "success": True,
            "message": "文档上传成功",
            "document_id": document.document_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传文档失败: {str(e)}")

@router.get("/config", response_model=ConfigResponse)
async def get_config(
    current_user: User = Depends(get_current_user)
):
    """
    获取当前Agent配置
    """
    try:
        # 从 settings 获取配置
        return ConfigResponse(
            max_token_limit=settings.AGENT_MAX_TOKEN_LIMIT,
            return_messages=settings.AGENT_RETURN_MESSAGES,
            return_source_documents=settings.AGENT_RETURN_SOURCE_DOCUMENTS,
            k=settings.AGENT_K,
            vector_store_url=settings.QDRANT_URL,
            embedding_model=settings.DASHSCOPE_EMBEDDING_MODEL,
            success=True,
            message="获取配置成功"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置错误: {str(e)}")

@router.post("/config", response_model=ConfigResponse)
async def update_config(
    request: ConfigUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    更新Agent配置 (仅部分配置)
    注意：此操作会重新初始化全局 Agent 实例
    """
    try:
        global agent
        logger = logging.getLogger(__name__)
        
        # 更新 settings 对象 (这不会持久化，仅影响当前运行实例)
        # 要持久化需要修改 .env 文件或环境变量
        updated_fields = request.dict(exclude_unset=True)
        if not updated_fields:
            raise HTTPException(status_code=400, detail="没有提供要更新的配置项")
        
        logger.warning(f"准备更新Agent配置: {updated_fields}")
        
        # 直接修改全局 settings 对象 (谨慎使用)
        # 注意：这可能不是最佳实践，更好的方式可能是创建新的Agent实例时传递配置
        current_config = settings.dict()
        updated_config = {**current_config, **updated_fields}
        
        # 更新特定的环境变量以反映更改 (如果需要)
        for key, value in updated_fields.items():
            env_key = f"AGENT_{key.upper()}" # 假设agent相关配置有AGENT_前缀
            if value is not None:
                os.environ[env_key] = str(value)
                setattr(settings, key, value)
        
        # 重新初始化全局 Agent 实例以应用新配置
        # 注意：这会影响所有后续请求
        logger.warning("重新初始化全局Agent实例以应用新配置...")
        agent = KnowledgeAgent() # 重新创建实例，它会从更新后的settings读取
        logger.info("全局Agent实例已重新初始化")
        
        return ConfigResponse(
            max_token_limit=settings.AGENT_MAX_TOKEN_LIMIT,
            return_messages=settings.AGENT_RETURN_MESSAGES,
            return_source_documents=settings.AGENT_RETURN_SOURCE_DOCUMENTS,
            k=settings.AGENT_K,
            vector_store_url=settings.QDRANT_URL,
            embedding_model=settings.DASHSCOPE_EMBEDDING_MODEL,
            success=True,
            message="配置更新成功，Agent已重新初始化"
        )
    except Exception as e:
        logger.error(f"配置更新错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"配置更新错误: {str(e)}")

@router.get("/query/stream")
async def stream_query_agent(
    query: str,
    session_id: Optional[str] = None,
    token: Optional[str] = None,  # 允许通过URL参数传递令牌
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(ChatService)
):
    """
    流式查询端点 - 直接对应EventSource请求
    支持通过URL参数传递认证令牌，因为EventSource不支持自定义头部
    """
    try:
        logger = logging.getLogger(__name__)
        logger.info(f"收到流式查询请求: 用户={current_user.username}, 会话ID={session_id}")
        
        # 验证会话所有权（如果提供了会话ID）
        if session_id:
            # 检查会话是否存在并属于当前用户
            db_session = chat_service.get_session_by_id(session_id, current_user.id)
            if not db_session:
                logger.warning(f"会话不存在或不属于当前用户: {session_id}")
                # 创建一个流式响应来传达错误
                async def error_stream():
                    yield f"data: {json.dumps({'type': 'error', 'message': '会话不存在或不属于当前用户'}, ensure_ascii=False)}\n\n"
                
                return StreamingResponse(
                    error_stream(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache, no-transform",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no"
                    }
                )
        
        # 如果没有会话ID，创建一个新的唯一会话ID
        effective_session_id = session_id or f"session_{uuid4()}"
        
        # 设置SSE响应头
        return StreamingResponse(
            generate_stream_response(
                query=query, 
                session_id=effective_session_id, 
                context={"use_retrieval": True},
                user_id=current_user.id,
                chat_service=chat_service
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        logger.error(f"流式查询处理错误: {str(e)}", exc_info=True)
        # 创建一个流式响应来传达错误
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': f'流式查询处理错误: {str(e)}'}, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

@router.get("/test")
async def test_api():
    """
    测试API是否正常运行的简单端点
    """
    return {
        "status": "ok",
        "message": "API正常运行",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "1.0.0"
    } 