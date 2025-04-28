from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean, BigInteger
from sqlalchemy.orm import relationship
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.database import Base


# SQLAlchemy 模型
class Document(Base):
    """
    文档数据库模型
    
    注意：doc_metadata字段映射到数据库的metadata列。
    这是因为在SQLAlchemy的Declarative API中，'metadata'是一个保留名称，不能直接用作属性名。
    使用Column的name参数设置真实的数据库列名为"metadata"。
    """
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    file_type = Column(String(50))
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    doc_metadata = Column(JSON, name="metadata")
    task_id = Column(String(36))
    processing_status = Column(String(20), default='PENDING')
    bucket_name = Column(String(100))
    object_key = Column(String(255))
    content_type = Column(String(100))
    file_size = Column(BigInteger)
    etag = Column(String(100))
    vector_store_id = Column(String(255))
    vector_collection_name = Column(String(255))
    vector_count = Column(Integer)
    
    # 移除关系映射，改为纯SQL方式查询
    # user = relationship("User", backref="documents")
    # tasks = relationship("Task", back_populates="document", cascade="all, delete-orphan")


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
    user_id: int
    created_at: datetime
    updated_at: datetime
    content: Optional[str] = None
    extracted_text: Optional[str] = None
    bucket_name: Optional[str] = None
    object_key: Optional[str] = None
    processing_status: Optional[str] = None
    vector_store_id: Optional[str] = None
    
    @field_validator('metadata', mode='before')
    @classmethod
    def validate_metadata(cls, v):
        """确保metadata字段是字典类型"""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        try:
            # 尝试将非字典类型转换为字典
            return dict(v)
        except Exception:
            # 转换失败时返回空字典
            return {}
    
    class Config:
        from_attributes = True
        alias_generator = lambda x: "metadata" if x == "doc_metadata" else x
        populate_by_name = True


class DocumentUploadResponse(BaseModel):
    """文档上传响应模型"""
    success: bool
    id: int
    task_id: str
    message: str


class DocumentPreview(BaseModel):
    """文档预览模型"""
    id: int
    name: str
    file_type: str
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    processing_status: Optional[str] = None
    
    @field_validator('metadata', mode='before')
    @classmethod
    def validate_metadata(cls, v):
        """确保metadata字段是字典类型"""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        try:
            # 尝试将非字典类型转换为字典
            return dict(v)
        except Exception:
            # 转换失败时返回空字典
            return {}
    
    class Config:
        from_attributes = True
        alias_generator = lambda x: "metadata" if x == "doc_metadata" else x


class DocumentList(BaseModel):
    """文档列表模型"""
    documents: List[DocumentPreview]
    total: int
    
    class Config:
        from_attributes = True 