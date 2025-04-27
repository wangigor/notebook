"""
任务模型定义
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Float, Integer, Text, JSON, DateTime, ForeignKey
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
    
    # 关系
    created_by_user = relationship("User", back_populates="tasks")
    document = relationship("Document", back_populates="tasks")


class TaskStep(BaseModel):
    """任务步骤模型（Pydantic）"""
    name: str  # 步骤名称
    description: Optional[str] = None  # 步骤描述
    status: TaskStepStatus = TaskStepStatus.PENDING  # 步骤状态
    progress: float = 0.0  # 步骤进度（0-100）
    started_at: Optional[datetime] = None  # 开始时间
    completed_at: Optional[datetime] = None  # 完成时间
    error_message: Optional[str] = None  # 错误信息（当状态为FAILED时）

    class Config:
        orm_mode = True


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
    document_id: Optional[str] = None  # 文档ID
    metadata: Dict[str, Any] = Field(default_factory=dict)  # 任务元数据

    class Config:
        orm_mode = True


class TaskCreate(BaseModel):
    """任务创建请求模型"""
    name: str  # 任务名称
    task_type: str  # 任务类型
    description: Optional[str] = None  # 任务描述
    document_id: Optional[str] = None  # 文档ID
    metadata: Optional[Dict[str, Any]] = None  # 任务元数据

    class Config:
        orm_mode = True


class TaskList(BaseModel):
    """任务列表响应模型"""
    tasks: List[TaskStatusResponse]
    total: int
    
    class Config:
        orm_mode = True 