# -*- coding: utf-8 -*-
"""
任务模型定义
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, String, Float, Integer, Text, JSON, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database import Base

class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "PENDING"  # 等待中
    RUNNING = "RUNNING"  # 运行中
    COMPLETED = "COMPLETED"  # 已完成
    FAILED = "FAILED"  # 失败
    CANCELLED = "CANCELLED"  # 已取消


class TaskStepStatus(str, Enum):
    """任务步骤状态枚举"""
    PENDING = "PENDING"  # 等待中
    RUNNING = "RUNNING"  # 运行中
    COMPLETED = "COMPLETED"  # 已完成
    FAILED = "FAILED"  # 失败
    SKIPPED = "SKIPPED"  # 已跳过


class TaskStepType(str, Enum):
    """任务步骤类型枚举"""
    FILE_UPLOAD = "FILE_UPLOAD"  # 文件上传到对象存储
    TEXT_EXTRACTION = "TEXT_EXTRACTION"  # 文本提取
    TEXT_SPLITTING = "TEXT_SPLITTING"  # 文本分块
    TEXT_PROCESSING = "TEXT_PROCESSING"  # 文本处理（清洗/格式化）
    EMBEDDING_GENERATION = "EMBEDDING_GENERATION"  # 生成嵌入向量
    VECTOR_STORAGE = "VECTOR_STORAGE"  # 存储向量到向量数据库
    METADATA_EXTRACTION = "METADATA_EXTRACTION"  # 元数据提取
    DOCUMENT_INDEXING = "DOCUMENT_INDEXING"  # 文档索引构建


class Task(Base):
    """任务数据模型"""
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, index=True)  # 任务ID
    name = Column(String(255), nullable=False)  # 任务名称
    description = Column(Text, nullable=True)  # 任务描述
    task_type = Column(String(50), nullable=False)  # 任务类型
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # 创建者ID
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)  # 文档ID
    status = Column(String(20), nullable=False, default=TaskStatus.PENDING)  # 任务状态
    progress = Column(Float, nullable=False, default=0.0)  # 任务进度（0-100）
    error_message = Column(Text, nullable=True)  # 错误信息（当状态为FAILED时）
    task_metadata = Column(JSON, nullable=True)  # 任务元数据
    steps = Column(JSON, nullable=True)  # 任务步骤
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)  # 创建时间
    started_at = Column(DateTime, nullable=True)  # 开始时间
    completed_at = Column(DateTime, nullable=True)  # 完成时间
    
    # 移除关系映射，改为纯SQL方式查询
    # created_by_user = relationship("User", back_populates="tasks")
    # document = relationship("Document", back_populates="tasks")
    
    # 添加关系
    task_details = relationship("TaskDetail", back_populates="task", cascade="all, delete-orphan")


class TaskDetail(Base):
    """任务详情数据模型"""
    __tablename__ = "task_details"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    step_name = Column(String(50), nullable=False)  # 步骤名称
    step_order = Column(Integer, nullable=False)  # 步骤顺序
    status = Column(String(20), nullable=False, default=TaskStatus.PENDING)  # 步骤状态
    progress = Column(Integer, nullable=False, default=0)  # 步骤进度（0-100）
    details = Column(JSON, nullable=True)  # 步骤详细信息
    error_message = Column(Text, nullable=True)  # 错误信息
    started_at = Column(DateTime, nullable=True)  # 开始时间
    completed_at = Column(DateTime, nullable=True)  # 完成时间
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)  # 创建时间
    
    # 与Task的关系
    task = relationship("Task", back_populates="task_details")

    # 添加索引
    __table_args__ = (
        Index('idx_task_details_task_id', 'task_id'),
        Index('idx_task_details_status', 'status'),
    )


class TaskStep(BaseModel):
    """任务步骤模型（Pydantic）"""
    name: str  # 步骤名称
    description: Optional[str] = None  # 步骤描述
    status: TaskStepStatus = TaskStepStatus.PENDING  # 步骤状态
    progress: float = 0.0  # 步骤进度（0-100）
    started_at: Optional[datetime] = None  # 开始时间
    completed_at: Optional[datetime] = None  # 完成时间
    error_message: Optional[str] = None  # 错误信息（当状态为FAILED时）
    # 新增字段
    step_type: Optional[str] = None  # 步骤类型
    output: Optional[Dict[str, Any]] = None  # 步骤输出数据
    metadata: Optional[Dict[str, Any]] = None  # 步骤元数据

    model_config = ConfigDict(
from_attributes=True)


# 添加TaskDetail相关的Pydantic模型
class TaskDetailBase(BaseModel):
    """任务详情基础模型"""
    step_name: str
    step_order: int
    status: str = TaskStatus.PENDING
    progress: int = 0
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class TaskDetailCreate(TaskDetailBase):
    """任务详情创建模型"""
    task_id: str

class TaskDetailUpdate(BaseModel):
    """任务详情更新模型"""
    status: Optional[str] = None
    progress: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TaskDetailResponse(TaskDetailBase):
    """任务详情响应模型"""
    id: int
    task_id: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskStatusResponse(BaseModel):
    """任务状态响应模型"""
    id: str  # 任务ID
    name: str  # 任务名称
    description: Optional[str] = None  # 任务描述
    task_type: str  # 任务类型
    status: TaskStatus  # 任务状态
    progress: float  # 任务进度（0-100）
    error_message: Optional[str] = None  # 错误信息
    created_at: datetime  # 创建时间
    started_at: Optional[datetime] = None  # 开始时间
    completed_at: Optional[datetime] = None  # 完成时间
    steps: List[TaskStep] = []  # 任务步骤
    task_details: List[TaskDetailResponse] = []  # 任务详情记录
    document_id: Optional[str] = None  # 文档ID
    created_by: Optional[int] = None  # 创建者ID
    metadata: Dict[str, Any] = Field(default_factory=dict)  # 任务元数据

    model_config = ConfigDict(
from_attributes=True)


class TaskCreate(BaseModel):
    """任务创建请求模型"""
    name: str  # 任务名称
    task_type: str  # 任务类型
    description: Optional[str] = None  # 任务描述
    document_id: Optional[str] = None  # 文档ID
    metadata: Optional[Dict[str, Any]] = None  # 任务元数据

    model_config = ConfigDict(
from_attributes=True)


class TaskList(BaseModel):
    """任务列表响应模型"""
    tasks: List[TaskStatusResponse]
    total: int
    
    model_config = ConfigDict(
from_attributes=True) 