import functools
import logging
from datetime import datetime
from app.database import get_db
from app.services.task_service import TaskService
from app.services.task_detail_service import TaskDetailService
from app.models.task import TaskStatus
from app.websockets.task_manager import sync_push_task_update

logger = logging.getLogger(__name__)

def update_task_status(func):
    """任务状态更新装饰器，统一任务状态更新和WebSocket推送"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 提取参数
        # 假设最常见的参数模式是：(self, result_from_previous, document_id, task_id, task_detail_id)
        # 或者第一个任务：(self, document_id, task_id, task_detail_id, file_path)
        task_id = None
        task_detail_id = None
        
        # 尝试从args中提取
        if len(args) >= 4:
            if len(args) == 4:  # validate_file任务
                task_id = args[2]
                task_detail_id = args[3]
            else:  # 其他子任务
                task_id = args[3]
                task_detail_id = args[4]
        
        # 或者从kwargs中提取
        task_id = kwargs.get('task_id', task_id)
        task_detail_id = kwargs.get('task_detail_id', task_detail_id)
        
        if not task_id or not task_detail_id:
            # 无法确定任务ID，直接执行原函数
            return func(*args, **kwargs)
        
        db = next(get_db())
        task_service = TaskService(db)
        task_detail_service = TaskDetailService(db)
        
        try:
            # 1. 更新任务详情状态为运行中
            task_detail_service.update_task_detail(
                task_detail_id,
                status=TaskStatus.RUNNING,
                progress=10
            )
            
            # 2. 推送任务状态更新
            sync_push_task_update(task_id, task_service, task_detail_service)
            
            # 3. 执行原始任务函数
            result = func(*args, **kwargs)
            
            # 4. 任务成功完成后，更新状态和推送
            # 注意：这部分可能在子任务中已经处理，避免重复更新
            if not task_detail_service.get_task_details_by_task_id(task_id)[-1].id == task_detail_id:
                # 如果不是最后一个任务，才更新主任务状态
                task_service.update_task_status_based_on_details(task_id)
                sync_push_task_update(task_id, task_service, task_detail_service)
            
            return result
            
        except Exception as e:
            # 5. 任务失败，更新状态和推送
            logger.error(f"任务执行失败: {str(e)}")
            task_detail_service.update_task_detail(
                task_detail_id,
                status=TaskStatus.FAILED,
                error_message=str(e)
            )
            task_service.update_task_status_based_on_details(task_id)
            sync_push_task_update(task_id, task_service, task_detail_service)
            raise
            
    return wrapper 