from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.task import TaskDetail, TaskStatus

"""
任务详情服务

注意：在使用此服务前，请确保已执行数据库迁移以创建task_details表。
可以使用以下命令执行迁移：
    alembic upgrade head

如果您使用的是手动迁移脚本，请确保已执行migrations/versions/add_task_detail_table.py
"""

class TaskDetailService:
    def __init__(self, db: Session):
        self.db = db

    def create_task_detail(self, task_id: str, step_name: str, step_order: int) -> TaskDetail:
        """创建任务详情记录"""
        task_detail = TaskDetail(
            task_id=task_id,
            step_name=step_name,
            step_order=step_order,
            status=TaskStatus.PENDING,
            progress=0
        )
        self.db.add(task_detail)
        self.db.commit()
        self.db.refresh(task_detail)
        return task_detail

    def update_task_detail(
        self, 
        task_detail_id: int, 
        status: Optional[str] = None,
        progress: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> TaskDetail:
        """更新任务详情状态和进度"""
        task_detail = self.db.query(TaskDetail).filter(TaskDetail.id == task_detail_id).first()
        if not task_detail:
            raise ValueError(f"TaskDetail with id {task_detail_id} not found")

        update_data = {}
        if status:
            update_data["status"] = status
            if status == TaskStatus.RUNNING and not task_detail.started_at:
                update_data["started_at"] = datetime.utcnow()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                update_data["completed_at"] = datetime.utcnow()
        
        if progress is not None:
            update_data["progress"] = progress
        
        if details:
            # 合并现有details和新details
            current_details = task_detail.details or {}
            current_details.update(details)
            update_data["details"] = current_details
        
        if error_message:
            update_data["error_message"] = error_message

        # 更新任务详情
        for key, value in update_data.items():
            setattr(task_detail, key, value)
        
        self.db.commit()
        self.db.refresh(task_detail)
        return task_detail

    def get_task_details_by_task_id(self, task_id: str) -> List[TaskDetail]:
        """获取任务的所有详情记录"""
        return self.db.query(TaskDetail).filter(TaskDetail.task_id == task_id).order_by(TaskDetail.step_order).all()

    def check_all_task_details_completed(self, task_id: str) -> bool:
        """检查任务的所有详情是否已完成"""
        task_details = self.get_task_details_by_task_id(task_id)
        if not task_details:
            return False
        
        return all(td.status == TaskStatus.COMPLETED for td in task_details) 