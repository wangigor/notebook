from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional
from app.database import Base


# SQLAlchemy 模型
class ChatSession(Base):
    """会话数据库模型"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # 关系
    messages = relationship("ChatMessage", backref="chat_session", cascade="all, delete-orphan")
    # 暂时移除user关系，避免循环依赖
    # user = relationship("User", back_populates="sessions")


class ChatMessage(Base):
    """消息数据库模型"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(50), nullable=False)  # user 或 assistant
    content = Column(Text, nullable=False)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    # session关系通过backref定义


# Pydantic 模型
class MessageBase(BaseModel):
    """消息基础模型"""
    role: str
    content: str


class MessageCreate(MessageBase):
    """消息创建模型"""
    pass


class Message(MessageBase):
    """消息响应模型"""
    id: int
    session_id: int
    created_at: datetime
    
    model_config = ConfigDict(
from_attributes=True)


class ChatSessionBase(BaseModel):
    """会话基础模型"""
    title: Optional[str] = None


class ChatSessionCreate(ChatSessionBase):
    """会话创建模型"""
    session_id: str
    user_id: Optional[int] = None


class ChatSessionUpdate(ChatSessionBase):
    """会话更新模型"""
    pass


class ChatSessionResponse(ChatSessionBase):
    """会话响应模型"""
    id: int
    session_id: str
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool
    messages: List[Message] = []
    
    model_config = ConfigDict(
from_attributes=True)


class ChatSessionList(BaseModel):
    """会话列表响应模型"""
    sessions: List[ChatSessionResponse] 