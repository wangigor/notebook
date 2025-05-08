"""
数据库依赖项

提供数据库会话的依赖函数
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from sqlalchemy.orm import Session

from app.database import SessionLocal

logger = logging.getLogger(__name__)

# 使用上下文管理器的同步会话获取函数
def get_db():
    """
    获取数据库会话（同步版本）
    
    Returns:
        Session: 同步数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 异步上下文管理器，用于在异步环境中使用同步数据库会话
@asynccontextmanager
async def get_db_session() -> AsyncGenerator[Session, Any]:
    """
    获取数据库会话（异步版本）
    
    在异步环境中使用同步数据库会话
    
    Yields:
        Session: 同步数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 