from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.chat import ChatSession as DB_ChatSession, ChatMessage, ChatSessionCreate, ChatSessionUpdate, MessageCreate, ChatSessionResponse
from app.models.user import User
from app.database import get_db
from fastapi import Depends, HTTPException, status


class ChatService:
    """会话服务"""
    
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db
    
    def get_user_sessions(self, user_id: int, skip: int = 0, limit: int = 100) -> List[DB_ChatSession]:
        """获取用户的所有会话"""
        return self.db.query(DB_ChatSession).filter(
            DB_ChatSession.user_id == user_id,
            DB_ChatSession.is_active == True
        ).order_by(DB_ChatSession.updated_at.desc()).offset(skip).limit(limit).all()
    
    def get_session_by_id(self, session_id: str, user_id: int) -> Optional[DB_ChatSession]:
        """根据会话ID获取会话"""
        return self.db.query(DB_ChatSession).filter(
            DB_ChatSession.session_id == session_id,
            DB_ChatSession.user_id == user_id,
            DB_ChatSession.is_active == True
        ).first()
    
    def create_session(self, session: ChatSessionCreate) -> DB_ChatSession:
        """创建新会话"""
        print(f"创建会话: session_id={session.session_id}, title={session.title}, user_id={session.user_id}")
        
        # 确保user_id非空
        if not session.user_id:
            raise ValueError("user_id不能为空")
            
        db_session = DB_ChatSession(
            session_id=session.session_id,
            title=session.title or "新对话",
            user_id=session.user_id
        )
        self.db.add(db_session)
        self.db.commit()
        self.db.refresh(db_session)
        print(f"会话创建成功: id={db_session.id}, session_id={db_session.session_id}")
        return db_session
    
    def update_session(self, session_id: str, user_id: int, session_update: ChatSessionUpdate) -> Optional[DB_ChatSession]:
        """更新会话"""
        db_session = self.get_session_by_id(session_id, user_id)
        if not db_session:
            return None
        
        if session_update.title is not None:
            db_session.title = session_update.title
        
        db_session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_session)
        return db_session
    
    def delete_session(self, session_id: str, user_id: int) -> bool:
        """删除会话（软删除）"""
        db_session = self.get_session_by_id(session_id, user_id)
        if not db_session:
            return False
        
        db_session.is_active = False
        db_session.updated_at = datetime.utcnow()
        self.db.commit()
        return True
    
    def get_messages(self, session_id: str, user_id: int, skip: int = 0, limit: int = 100) -> List[ChatMessage]:
        """获取会话中的消息"""
        db_session = self.get_session_by_id(session_id, user_id)
        if not db_session:
            return []
        
        return self.db.query(ChatMessage).filter(
            ChatMessage.session_id == db_session.id
        ).order_by(ChatMessage.created_at.asc()).offset(skip).limit(limit).all()
    
    def add_message(self, session_id: str, user_id: int, message: MessageCreate) -> Optional[ChatMessage]:
        """添加消息到会话"""
        db_session = self.get_session_by_id(session_id, user_id)
        if not db_session:
            return None
        
        db_message = ChatMessage(
            role=message.role,
            content=message.content,
            session_id=db_session.id
        )
        
        # 更新会话最后活动时间
        db_session.updated_at = datetime.utcnow()
        
        # 如果是第一条消息，使用消息内容作为会话标题
        if not db_session.title or db_session.title == "新对话":
            if message.role == "user" and message.content:
                # 截取前20个字符作为标题
                db_session.title = message.content[:20] + ("..." if len(message.content) > 20 else "")
        
        self.db.add(db_message)
        self.db.commit()
        self.db.refresh(db_message)
        return db_message 