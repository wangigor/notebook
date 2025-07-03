import os
import asyncio
import logging
from app.core.celery_app import celery_app
from app.database import get_db, SessionLocal
from app.services.task_service import TaskService
from app.services.document_service import DocumentService
from app.services.storage_service import StorageService
from app.services.task_detail_service import TaskDetailService
from app.ws.connection_manager import ws_manager
from app.models.task import TaskStatus, TaskStepStatus
from datetime import datetime
from app.core.config import settings
import traceback
from app.models.document import DocumentStatus
from app.worker.websocket_manager import WebSocketManager


logger = logging.getLogger(__name__)
ws_manager = WebSocketManager()

@celery_app.task(bind=True, name="process_document")
def process_document(self, doc_id: int, task_id: str, file_path: str, processing_mode: str = "rag"):
    """处理文档的任务 - 调度器"""
    logger.info(f"开始处理文档任务: doc_id={doc_id}, task_id={task_id}, 处理模式={processing_mode}")
    
    # 根据处理模式选择对应的处理器
    if processing_mode == "rag":
        from app.worker.processing.rag_processor import run as rag_processor_run
        asyncio.run(rag_processor_run(doc_id, task_id, file_path))
    elif processing_mode == "graph":
        from app.worker.processing.graph_processor import run as graph_processor_run
        asyncio.run(graph_processor_run(doc_id, task_id, file_path))
    else:
        raise ValueError(f"不支持的处理模式: {processing_mode}")
    
    return {"status": "completed", "doc_id": doc_id, "task_id": task_id, "processing_mode": processing_mode}



async def push_task_update(task_id: str, task_service, task_detail_service=None):
    """推送任务状态更新"""
    try:
        # 获取完整任务状态
        task_data = await task_service.get_task_with_details(task_id)
        
        # 如果提供了task_detail_service，获取任务详情
        if task_detail_service:
            task_details = task_detail_service.get_task_details_by_task_id(task_id)
            task_details_data = [
                {
                    "id": td.id,
                    "step_name": td.step_name,
                    "step_order": td.step_order,
                    "status": td.status,
                    "progress": td.progress,
                    "details": td.details,
                    "error_message": td.error_message,
                    "started_at": td.started_at.isoformat() if td.started_at else None,
                    "completed_at": td.completed_at.isoformat() if td.completed_at else None,
                    "created_at": td.created_at.isoformat()
                }
                for td in task_details
            ]
            
            # 添加任务详情到推送数据
            task_data["task_details"] = task_details_data
        
        # 异步推送到WebSocket
        from app.worker.websocket_manager import WebSocketManager
        ws_manager = WebSocketManager()
        await ws_manager.send_update(task_id, {
            "event": "task_update",
            "data": task_data
        })
    except Exception as e:
        logger.error(f"推送任务更新失败: {str(e)}")

# 取消任务的Celery任务
@celery_app.task(name="cancel_document_task")
def cancel_document_task(task_id: str):
    """取消文档处理任务"""
    # 这里可以添加取消逻辑，例如向处理进程发送终止信号
    # 由于Celery任务一旦开始执行就不容易被打断，这里我们主要是标记任务状态为取消
    asyncio.run(cancel_document_task_async(task_id))
    return {"status": "cancelled", "task_id": task_id}

async def cancel_document_task_async(task_id: str):
    """异步取消文档处理任务"""
    session = SessionLocal()
    try:
        task_service = TaskService(session)
        task_detail_service = TaskDetailService(session)
        
        # 更新任务状态为已取消
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.CANCELLED
        )
        
        # 推送状态更新
        await push_task_update(task_id, task_service, task_detail_service)
    finally:
        session.close() 