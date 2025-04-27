from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.database import Base


# SQLAlchemy 模型
class Document(Base):
    """文档数据库模型"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    vector_id = Column(String(255), nullable=True, index=True)
    doc_metadata = Column(JSON, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted = Column(Boolean, default=False)
    
    # MinIO存储信息，用于文件下载
    bucket_name = Column(String(255), nullable=True)
    object_key = Column(String(255), nullable=True)
    
    # 关系
    user = relationship("User", backref="documents")
    tasks = relationship("Task", back_populates="document", cascade="all, delete-orphan")


# Pydantic 模型
class DocumentBase(BaseModel):
    """文档基础模型"""
    name: str
    file_type: str
    metadata: Optional[Dict[str, Any]] = None


class DocumentCreate(DocumentBase):
    """创建文档模型"""
    content: Optional[str] = None
    extracted_text: Optional[str] = None
    
    
class DocumentUpdate(BaseModel):
    """更新文档模型"""
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    content: Optional[str] = None
    extracted_text: Optional[str] = None
    

class DocumentResponse(DocumentBase):
    """文档响应模型"""
    id: int
    document_id: str
    vector_id: Optional[str] = None
    user_id: int
    created_at: datetime
    updated_at: datetime
    content: Optional[str] = None
    extracted_text: Optional[str] = None
    bucket_name: Optional[str] = None
    object_key: Optional[str] = None
    
    class Config:
        from_attributes = True
        alias_generator = lambda x: "metadata" if x == "doc_metadata" else x


class DocumentUploadResponse(BaseModel):
    """文档上传响应模型"""
    success: bool
    document_id: str
    task_id: str
    message: str


class DocumentPreview(BaseModel):
    """文档预览模型"""
    id: int
    document_id: str
    name: str
    file_type: str
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True
        alias_generator = lambda x: "metadata" if x == "doc_metadata" else x


class DocumentList(BaseModel):
    """文档列表模型"""
    documents: List[DocumentPreview]
    total: int
    
    class Config:
        from_attributes = True 