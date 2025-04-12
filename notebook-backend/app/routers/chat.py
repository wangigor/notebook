from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from app.services.chat_service import ChatService
from app.auth.dependencies import get_current_user
from app.models.user import User, UserResponse
from app.models.chat import (
    ChatSessionResponse,
    ChatSession,
    ChatSessionCreate,
    ChatSessionUpdate,
    Message,
    MessageCreate,
    ChatSessionList
)
from uuid import uuid4

router = APIRouter()


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends()
):
    """获取当前用户的所有对话会话"""
    sessions = chat_service.get_user_sessions(current_user.id, skip, limit)
    return sessions

@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    session_data: dict = None,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends()
):
    """创建新对话会话"""
    # 提取标题和会话ID（如果提供）
    title = None
    session_id = None
    
    if session_data:
        title = session_data.get("title")
        session_id = session_data.get("session_id")
    
    # 如果没有提供会话ID，生成一个新的
    if not session_id:
        session_id = f"session_{uuid4()}"
    
    # 创建会话对象，只使用从令牌中提取的user_id
    session = ChatSessionCreate(
        session_id=session_id,
        user_id=current_user.id,  # 只使用从JWT令牌中提取的用户ID
        title=title or "新对话"
    )
    
    return chat_service.create_session(session)

@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends()
):
    """获取特定对话会话"""
    session = chat_service.get_session_by_id(session_id, current_user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    return session

@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_session(
    session_id: str,
    session_update: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends()
):
    """更新对话会话"""
    updated_session = chat_service.update_session(session_id, current_user.id, session_update)
    if not updated_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    return updated_session

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends()
):
    """删除对话会话"""
    success = chat_service.delete_session(session_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    return None

@router.get("/sessions/{session_id}/messages", response_model=List[Message])
async def get_messages(
    session_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends()
):
    """获取会话中的所有消息"""
    messages = chat_service.get_messages(session_id, current_user.id, skip, limit)
    return messages

@router.post("/sessions/{session_id}/messages", response_model=Message)
async def add_message(
    session_id: str,
    message: MessageCreate,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends()
):
    """添加消息到会话"""
    db_message = chat_service.add_message(session_id, current_user.id, message)
    if not db_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    return db_message 