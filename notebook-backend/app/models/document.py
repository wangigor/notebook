# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any, Union
from enum import Enum, auto
from app.database import Base

class DocumentStatus(str, Enum):
    """文档状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"  # 添加删除状态

# SQLAlchemy ORM 模型定义
class Document(Base):
    """文档数据表模型"""
    __tablename__ = "documents"
    
    # 主键和基本信息
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 处理状态
    processing_status = Column(String(20), nullable=True, default=DocumentStatus.PENDING)
    
    # 存储相关字段
    bucket_name = Column(String(100), nullable=True)
    object_key = Column(String(255), nullable=True)
    content_type = Column(String(100), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    etag = Column(String(100), nullable=True)
    
    # 向量存储相关字段
    vector_store_id = Column(String(255), nullable=True)
    vector_collection_name = Column(String(255), nullable=True)
    vector_count = Column(Integer, nullable=True)
    
    # 关联任务
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    
    # 元数据（改名为doc_metadata避免与SQLAlchemy保留字冲突）
    doc_metadata = Column('metadata', JSON, nullable=True)
    
    # 内容 (不在数据库中存储，但代码中临时使用)
    content = None
    
    # 为了兼容性，创建meta_info属性作为doc_metadata的别名
    @property
    def meta_info(self):
        return self.doc_metadata
    
    @meta_info.setter
    def meta_info(self, value):
        self.doc_metadata = value
    
    # 标记删除状态
    @property
    def deleted(self):
        return self.processing_status == DocumentStatus.DELETED
    
    @deleted.setter
    def deleted(self, value):
        if value:
            self.processing_status = DocumentStatus.DELETED
    
    # 时间戳
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系映射（如有必要）
    # tasks = relationship("Task", back_populates="document")
    # user = relationship("User", back_populates="documents")

# Pydantic 模型（保持不变）
class DocumentPydantic(BaseModel):
    """文档模型"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    content: str
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    status: DocumentStatus = DocumentStatus.PENDING

class DocumentCreate(BaseModel):
    """创建文档的请求模型"""
    name: str
    content: str
    user_id: int
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

class DocumentUpdate(BaseModel):
    """更新文档的请求模型"""
    name: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    status: Optional[DocumentStatus] = None
    is_deleted: Optional[bool] = None

class DocumentPreviewContent(BaseModel):
    """文档预览数据模型"""
    content: Optional[str] = None
    content_type: str

    class Config:
        orm_mode = True

# 保持原有的文档预览类型，用于文档列表
class DocumentPreview(BaseModel):
    """文档预览类型（用于列表）"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    file_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    status: Optional[DocumentStatus] = None
    preview_content: Optional[str] = None  
    tags: Optional[List[str]] = None
    user_id: int
    metadata: Optional[Dict[str, Any]] = None

class DocumentResponse(BaseModel):
    """文档响应模型"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    content: str
    user_id: int
    created_at: datetime
    updated_at: datetime
    status: DocumentStatus
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_deleted: bool = False

class DocumentList(BaseModel):
    """文档列表响应模型"""
    total: int
    items: List[DocumentPreview]
    page: int
    page_size: int