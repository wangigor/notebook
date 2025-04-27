from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Path, Query
from typing import List, Optional
from sqlalchemy.orm import Session
import logging

from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.task import TaskStatusResponse, TaskStatus
from app.database import get_db
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖项：获取任务服务
def get_task_service_dep(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db)

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

@router.post("/{task_id}/cancel", response_model=dict)
async def cancel_task(
    task_id: str = Path(..., title="任务ID"),
    task_service: TaskService = Depends(get_task_service_dep),
    current_user: User = Depends(get_current_user)
):
    """
    取消任务
    """
    # 取消任务
    result = await task_service.cancel_task(task_id, current_user.id)
    if result:
        return {"status": "success", "message": "任务已取消"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法取消任务，可能任务已完成或已取消"
        )

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
    
    return tasks 