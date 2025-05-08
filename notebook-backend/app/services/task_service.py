import json
"""
任务服务类，负责任务的创建、查询、更新和取消等操作
"""
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.task import Task, TaskStatus, TaskStep, TaskStepStatus
from app.models.document import Document
from app.ws.connection_manager import ws_manager

logger = logging.getLogger(__name__)

class TaskService:
    """任务服务类"""
    
    def __init__(self, db: Session):
        """
        初始化任务服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    def create_task(
        self, 
        name: str, 
        task_type: str, 
        created_by: int,
        document_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        创建一个新任务
        
        Args:
            name: 任务名称
            task_type: 任务类型
            created_by: 创建者ID
            document_id: 文档ID (可选)
            description: 任务描述 (可选)
            metadata: 任务元数据 (可选)
            
        Returns:
            Task: 创建的任务对象
        """
        logger.info(f"创建任务: {name}, 类型: {task_type}, 创建者: {created_by}")
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 验证文档ID (如果提供)
        if document_id:
            document = self.db.query(Document).filter(Document.id == document_id).first()
            if not document:
                logger.error(f"文档不存在: {document_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="文档不存在"
                )
                
        # 创建任务对象
        task = Task(
            id=task_id,
            name=name,
            task_type=task_type,
            created_by=created_by,
            document_id=document_id,
            description=description,
            task_metadata=metadata,  # 注意这里使用task_metadata而不是metadata
            status=TaskStatus.PENDING,
            progress=0.0,
            created_at=datetime.utcnow()
        )
        
        try:
            # 保存到数据库
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            logger.info(f"任务创建成功: {task_id}")
            return task
        except Exception as e:
            self.db.rollback()
            logger.error(f"任务创建失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"任务创建失败: {str(e)}"
            )
    
    def create_upload_task(
        self,
        task_id: str,
        document_id: str,
        user_id: int,
        file_path: str,
        file_name: str,
        content_type: str
    ) -> Task:
        """
        创建文件上传任务
        
        Args:
            task_id: 任务ID
            document_id: 文档ID
            user_id: 用户ID
            file_path: 文件路径
            file_name: 文件名
            content_type: 文件类型
            
        Returns:
            Task: 创建的任务对象
        """
        logger.info(f"创建上传任务: {file_name}, 用户: {user_id}")
        
        # 构建上传任务元数据
        metadata = {
            "file_path": file_path,
            "file_name": file_name,
            "content_type": content_type
        }
        
        # 创建任务步骤
        steps = [
            TaskStep(
                name="文件上传",
                description="上传文件到服务器",
                status=TaskStepStatus.PENDING
            ).dict(),
            TaskStep(
                name="文件处理",
                description="处理文件内容",
                status=TaskStepStatus.PENDING
            ).dict(),
            TaskStep(
                name="文档索引",
                description="构建文档索引",
                status=TaskStepStatus.PENDING
            ).dict()
        ]
        
        # 创建任务对象
        task = Task(
            id=task_id,
            name=f"上传文件: {file_name}",
            task_type="DOCUMENT_UPLOAD",
            created_by=user_id,
            document_id=document_id,
            description=f"上传并处理文件: {file_name}",
            task_metadata=metadata,  # 注意这里使用task_metadata而不是metadata
            steps=steps,
            status=TaskStatus.PENDING,
            progress=0.0,
            created_at=datetime.utcnow()
        )
        
        try:
            # 保存到数据库
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            logger.info(f"上传任务创建成功: {task_id}")
            return task
        except Exception as e:
            self.db.rollback()
            logger.error(f"上传任务创建失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"上传任务创建失败: {str(e)}"
            )
    
    def get_task_by_id(self, task_id: str) -> Any:
        """
        根据ID获取任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            TaskStatusResponse: 任务响应对象
            
        Raises:
            HTTPException: 如果任务不存在
        """
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.error(f"任务不存在: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 转换为TaskStatusResponse对象
        from app.models.task import TaskStatusResponse
        task_dict = {
            "id": task.id,
            "name": task.name,
            "description": task.description,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "steps": task.steps or [],
            "document_id": str(task.document_id) if task.document_id is not None else None,
            "created_by": task.created_by,
            "metadata": task.task_metadata or {}
        }
        return TaskStatusResponse.model_validate(task_dict)
    
    def get_task_with_details(self, task_id: str) -> Dict[str, Any]:
        """获取任务详细信息，包括所有步骤详情"""
        task = self.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"找不到任务: {task_id}")
        
        # 构建任务详情响应
        task_dict = {
            "id": task.id,
            "name": task.name,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            # "updated_at": task.updated_at.isoformat() if task.updated_at else None if task.updated_at else None,
            "steps": task.steps,
            "created_by": task.created_by,
            "document_id": str(task.document_id) if task.document_id is not None else None
        }
        
        # 添加文档信息（如果有）
        if task.document_id:
            document = self.db.query(Document).filter(Document.id == task.document_id).first()
            if document:
                task_dict["document"] = {
                    "id": str(document.id),  # 转换为字符串
                    "name": document.name,
                    "file_type": document.file_type,
                    "processing_status": document.processing_status
                }
        
        return task_dict
    
    async def get_user_tasks(
        self, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 10,
        include_completed: bool = True
    ) -> Tuple[List[Any], int]:
        """
        获取用户的任务列表
        
        Args:
            user_id: 用户ID
            skip: 分页起始位置
            limit: 分页大小
            include_completed: 是否包含已完成的任务
            
        Returns:
            Tuple[List[Any], int]: 包含任务响应对象和总数的元组
        """
        # 构建查询
        query = self.db.query(Task).filter(Task.created_by == user_id)
        
        # 如果不包含已完成任务，则过滤掉
        if not include_completed:
            query = query.filter(Task.status != TaskStatus.COMPLETED)
        
        # 获取总数
        total = query.count()
        
        # 分页并按创建时间倒序排序
        tasks = query.order_by(desc(Task.created_at)).offset(skip).limit(limit).all()
        
        # 转换为TaskStatusResponse对象
        from app.models.task import TaskStatusResponse
        task_responses = []
        for task in tasks:
            # 创建基本任务字典
            task_dict = {
                "id": task.id,
                "name": task.name,
                "description": task.description,
                "task_type": task.task_type,
                "status": task.status,
                "progress": task.progress,
                "error_message": task.error_message,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "steps": task.steps or [],
                "document_id": str(task.document_id) if task.document_id is not None else None,
                "created_by": task.created_by,
                "metadata": task.task_metadata or {}
            }
            # 添加到响应列表
            task_responses.append(TaskStatusResponse.model_validate(task_dict))
        
        return task_responses, total
    
    async def update_task_status(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[float] = None,
        error_message: Optional[str] = None,
        step_index: Optional[int] = None,
        step_status: Optional[TaskStepStatus] = None,
        step_progress: Optional[float] = None,
        step_error: Optional[str] = None,
        step_metadata: Optional[Dict[str, Any]] = None,
        step_output: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新的任务状态
            progress: 任务进度 (可选)
            error_message: 错误信息 (可选，当状态为FAILED时使用)
            step_index: 要更新的步骤索引 (可选)
            step_status: 步骤状态 (可选)
            step_progress: 步骤进度 (可选)
            step_error: 步骤错误信息 (可选)
            step_metadata: 步骤元数据 (可选)
            step_output: 步骤输出 (可选)
            
        Returns:
            TaskStatusResponse: 更新后的任务响应对象
        """
        logger = logging.getLogger(__name__)
        logger.info(f"更新任务状态: {task_id}, 状态: {status}, 进度: {progress}")
        
        # 获取任务
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"找不到任务: {task_id}")
        
        # 更新任务状态
        if status is not None:
            task.status = status
            
            # 如果是正在运行，记录开始时间
            if status == TaskStatus.RUNNING and not task.started_at:
                task.started_at = datetime.utcnow()
                
            # 如果是已完成或失败，记录结束时间
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED] and not task.completed_at:
                task.completed_at = datetime.utcnow()
        
        # 更新进度
        if progress is not None:
            task.progress = progress
        
        # 更新错误信息
        if error_message is not None:
            task.error_message = error_message
        
        # 更新步骤状态
        if step_index is not None and task.steps:
            # 处理steps字段可能是字符串的情况
            if isinstance(task.steps, str):
                try:
                    steps = json.loads(task.steps)
                except Exception as e:
                    logger.error(f"解析steps字符串失败: {e}")
                    steps = []
            else:
                steps = task.steps
            if 0 <= step_index < len(steps):
                # 更新步骤状态
                if step_status is not None:
                    steps[step_index]["status"] = step_status
                    
                    # 记录步骤开始时间
                    if step_status == TaskStepStatus.RUNNING and not steps[step_index].get("started_at"):
                        steps[step_index]["started_at"] = datetime.utcnow().isoformat()
                    
                    # 记录步骤完成时间
                    if step_status in [TaskStepStatus.COMPLETED, TaskStepStatus.FAILED] and not steps[step_index].get("completed_at"):
                        steps[step_index]["completed_at"] = datetime.utcnow().isoformat()
                
                # 更新步骤进度
                if step_progress is not None:
                    steps[step_index]["progress"] = step_progress
                
                # 更新步骤错误信息
                if step_error is not None:
                    steps[step_index]["error_message"] = step_error
                    
                # 添加步骤元数据
                if step_metadata is not None:
                    steps[step_index]["metadata"] = step_metadata
                    
                # 添加步骤输出
                if step_output is not None:
                    steps[step_index]["output"] = step_output
                
                # 保存更新后的步骤回任务对象
                task.steps = json.dumps(steps)
        
        # 更新任务
        # task.updated_at = datetime.utcnow()
        self.db.commit()
        
        # 发送WebSocket通知
        try:
            await ws_manager.send_task_update(task_id, {
                "id": task.id,
                "status": task.status,
                "progress": task.progress,
                "error_message": task.error_message,
                "steps": task.steps,
                # "updated_at": task.updated_at.isoformat() if task.updated_at else None
            })
        except Exception as e:
            logger.error(f"发送WebSocket通知失败: {str(e)}")
        
        # 返回转换后的响应对象
        from app.models.task import TaskStatusResponse
        task_dict = {
            "id": task.id,
            "name": task.name,
            "description": task.description,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "steps": task.steps or [],
            "document_id": str(task.document_id) if task.document_id is not None else None,
            "created_by": task.created_by,
            "metadata": task.task_metadata or {}
        }
        return TaskStatusResponse.model_validate(task_dict)
    
    async def cancel_task(self, task_id: str, user_id: int) -> Any:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            user_id: 用户ID (用于验证权限)
            
        Returns:
            TaskStatusResponse: 更新后的任务响应对象
            
        Raises:
            HTTPException: 如果任务已经完成或失败，或者用户无权取消
        """
        # 获取任务
        task = self.get_task_by_id(task_id)
        
        # 验证任务所有者
        if task.created_by != user_id:
            logger.warning(f"用户 {user_id} 尝试取消不属于他的任务 {task_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有任务创建者可以取消任务"
            )
        
        # 验证任务是否可以取消
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            logger.warning(f"尝试取消已结束的任务: {task_id}, 当前状态: {task.status}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无法取消已{task.status}的任务"
            )
        
        # 更新任务状态为已取消
        return await self.update_task_status(
            task_id=task_id,
            status=TaskStatus.CANCELLED,
            progress=task.progress,
            error_message="任务被用户取消"
        ) 