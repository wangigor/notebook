from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Path, Query, Body
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import logging
import os
import uuid
from datetime import datetime
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.task import TaskStatusResponse, TaskStatus, TaskStepStatus, TaskCreate
from app.database import get_db
from app.services.task_service import TaskService
from app.worker.celery_tasks import push_task_update
from app.celery_tasks.document_processing import process_document

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖项：获取任务服务
def get_task_service_dep(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db)

@router.post("/", response_model=TaskStatusResponse)
async def create_task(
    task_data: TaskCreate,
    task_service: TaskService = Depends(get_task_service_dep),
    current_user: User = Depends(get_current_user)
):
    """
    创建新任务
    """
    logger.info(f"创建新任务: {task_data.name}, 类型: {task_data.task_type}, 文档ID: {task_data.document_id}")
    
    task = task_service.create_task(
        name=task_data.name,
        task_type=task_data.task_type,
        created_by=current_user.id,
        document_id=task_data.document_id,
        description=task_data.description,
        metadata=task_data.metadata
    )
    
    return TaskStatusResponse.model_validate(task)

@router.get("/", response_model=List[TaskStatusResponse])
async def get_tasks(
    task_service: TaskService = Depends(get_task_service_dep),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的所有任务
    """
    tasks, _ = await task_service.get_user_tasks(current_user.id)
    return tasks

@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task(
    task_id: str = Path(..., title="任务ID"),
    task_service: TaskService = Depends(get_task_service_dep),
    current_user: User = Depends(get_current_user)
):
    """
    获取任务详情
    """
    task = await task_service.get_task_by_id(task_id)
    if not task or task.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="任务不存在或无权访问"
        )
    return task

@router.post("/{task_id}/cancel", response_model=TaskStatusResponse)
async def cancel_task(
    task_id: str = Path(..., title="任务ID"),
    task_service: TaskService = Depends(get_task_service_dep),
    current_user: User = Depends(get_current_user)
):
    """
    取消任务
    """
    return await task_service.cancel_task(task_id, current_user.id)

@router.get("/user/list", response_model=List[TaskStatusResponse])
async def get_user_tasks(
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
    include_completed: bool = Query(True),
    task_service: TaskService = Depends(get_task_service_dep),
    current_user: User = Depends(get_current_user)
):
    """获取用户的任务列表"""
    tasks, _ = await task_service.get_user_tasks(
        user_id=current_user.id, 
        limit=limit, 
        skip=skip,
        include_completed=include_completed
    )
    
    # 直接返回任务响应对象，因为在service层已经转换
    return tasks

@router.post("/{task_id}/test-update", response_model=TaskStatusResponse)
async def test_update_task(
    task_id: str,
    status: Optional[str] = Body(None),
    progress: Optional[float] = Body(None),
    step_index: Optional[int] = Body(None),
    step_status: Optional[str] = Body(None),
    step_progress: Optional[float] = Body(None),
    db: Session = Depends(get_db),
    task_service: TaskService = Depends(get_task_service_dep),
    current_user: User = Depends(get_current_user)
):
    """测试用：更新任务状态（仅在开发环境可用）"""
    if os.getenv("ENVIRONMENT", "development") != "development":
        raise HTTPException(status_code=403, detail="此接口仅在开发环境可用")
    
    # 验证任务权限
    task = await task_service.get_task_by_id(task_id)
    if not task or task.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="任务不存在或无访问权限")
    
    # 更新任务状态
    task_status = TaskStatus(status) if status else None
    step_status_enum = TaskStepStatus(step_status) if step_status else None
    
    updated_task = await task_service.update_task_status(
        task_id=task_id,
        status=task_status,
        progress=progress,
        step_index=step_index,
        step_status=step_status_enum,
        step_progress=step_progress
    )
    
    # 推送更新
    await push_task_update(task_id, task_service)
    
    return TaskStatusResponse.model_validate(updated_task)

class ProcessDocumentRequest(BaseModel):
    """处理文档的请求体"""
    document_id: str
    file_path: str
    task_name: Optional[str] = None
    task_type: str = "DOCUMENT_PROCESSING"
    priority: Optional[int] = None
    
@router.post("/document_processing", status_code=status.HTTP_202_ACCEPTED)
async def start_document_processing(
    request: ProcessDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    启动文档处理任务
    
    Args:
        request: 处理文档的请求体
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        任务信息
    """
    try:
        task_service = TaskService(db)
        
        # 创建任务记录
        task_id = str(uuid.uuid4())
        task_name = request.task_name or f"文档处理任务-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        task = task_service.create_task(
            task_id=task_id,
            name=task_name,
            task_type=request.task_type,
            document_id=request.document_id,
            created_by=current_user.id,
            priority=request.priority
        )
        
        # 异步启动Celery任务
        process_document.delay(
            document_id=request.document_id,
            task_id=task_id,
            file_path=request.file_path
        )
        
        logger.info(f"启动文档处理任务: {task_id}, 文档ID: {request.document_id}")
        
        return {
            "message": "文档处理任务已启动",
            "task_id": task_id,
            "document_id": request.document_id
        }
        
    except Exception as e:
        logger.error(f"启动文档处理任务失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动文档处理任务失败: {str(e)}"
        )

@router.get("/{task_id}/details", response_model=Dict[str, Any])
async def get_task_details(
    task_id: str = Path(..., title="任务ID"),
    task_service: TaskService = Depends(get_task_service_dep),
    current_user: User = Depends(get_current_user)
):
    """
    获取任务步骤详情
    """
    task = await task_service.get_task_by_id(task_id)
    if not task or task.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="任务不存在或无权访问"
        )
    
    from app.services.task_detail_service import TaskDetailService
    task_detail_service = TaskDetailService(task_service.db)
    task_details = task_detail_service.get_task_details_by_task_id(task_id)
    
    # 转换任务详情数据为响应格式
    task_details_data = []
    for td in task_details:
        task_details_data.append({
            "id": td.id,
            "task_id": td.task_id,
            "step_name": td.step_name,
            "step_order": td.step_order,
            "status": td.status,
            "progress": td.progress,
            "details": td.details,
            "error_message": td.error_message,
            "started_at": td.started_at.isoformat() if td.started_at else None,
            "completed_at": td.completed_at.isoformat() if td.completed_at else None,
            "created_at": td.created_at.isoformat()
        })
    
    return {
        "task_id": task_id,
        "task_details": task_details_data
    } 