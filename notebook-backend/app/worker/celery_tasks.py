import os
import asyncio
import logging
from app.core.config import celery_app
from app.database import get_async_session
from app.services.task_service import TaskService
from app.services.document_service import DocumentService
from app.services.storage_service import StorageService
from app.ws.connection_manager import ws_manager
from app.models.task import TaskStatus, TaskStepStatus
from datetime import datetime

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="process_document")
def process_document(self, doc_id: int, task_id: str, file_path: str):
    """处理文档的任务"""
    logger.info(f"开始处理文档任务: doc_id={doc_id}, task_id={task_id}")
    
    # 使用asyncio运行异步处理函数
    asyncio.run(process_document_async(doc_id, task_id, file_path))
    
    return {"status": "completed", "doc_id": doc_id, "task_id": task_id}

async def process_document_async(doc_id: int, task_id: str, file_path: str):
    """处理文档的异步实现"""
    # 获取数据库会话
    async with get_async_session() as session:
        # 获取服务实例
        task_service = TaskService(session)
        document_service = DocumentService(session)
        storage_service = StorageService()
        
        try:
            # 更新任务状态为运行中
            await task_service.update_task_status(
                task_id=task_id, 
                status=TaskStatus.RUNNING,
                step_index=0, 
                step_status=TaskStepStatus.RUNNING
            )
            await push_task_update(task_id, task_service)
            
            # 定义处理步骤
            steps = [
                {
                    "name": "文件验证",
                    "func": document_service.validate_document,
                    "weight": 5,  # 进度权重百分比
                },
                {
                    "name": "文件上传",  # 步骤：上传到MinIO
                    "func": storage_service.upload_file_and_update_document,
                    "weight": 10,
                },
                {
                    "name": "文本提取",
                    "func": document_service.extract_text_from_file,
                    "weight": 30,
                },
                {
                    "name": "文本预处理",
                    "func": document_service.preprocess_text,
                    "weight": 15,
                },
                {
                    "name": "向量化处理",
                    "func": document_service.vectorize_document,
                    "weight": 30,
                },
                {
                    "name": "保存向量",
                    "func": document_service.store_document_vectors,
                    "weight": 10,
                }
            ]
            
            # 执行每个步骤
            document_data = {"file_path": file_path}
            overall_progress = 0
            
            for i, step in enumerate(steps):
                # 更新步骤状态
                await task_service.update_task_status(
                    task_id=task_id,
                    progress=overall_progress,
                    step_index=i,
                    step_status=TaskStepStatus.RUNNING
                )
                await push_task_update(task_id, task_service)
                
                # 执行步骤
                try:
                    step_result = await step["func"](doc_id, **document_data)
                    document_data.update(step_result)  # 更新数据用于下一步骤
                    
                    # 更新步骤完成状态
                    # 更新总体进度
                    overall_progress += step["weight"]
                    await task_service.update_task_status(
                        task_id=task_id,
                        progress=overall_progress,
                        step_index=i,
                        step_status=TaskStepStatus.COMPLETED,
                        step_progress=100
                    )
                    await push_task_update(task_id, task_service)
                    
                except Exception as e:
                    # 步骤失败处理
                    logger.error(f"任务步骤 {step['name']} 失败: {str(e)}")
                    await task_service.update_task_status(
                        task_id=task_id,
                        status=TaskStatus.FAILED,
                        error_message=str(e),
                        step_index=i,
                        step_status=TaskStepStatus.FAILED,
                        step_error=str(e)
                    )
                    await push_task_update(task_id, task_service)
                    
                    # 清理临时文件
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        
                    return False
            
            # 更新文档状态为已处理
            await document_service.update_document_status(doc_id, "completed")
            
            # 更新任务状态为已完成
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                progress=100
            )
            await push_task_update(task_id, task_service)
            
            # 清理临时文件
            if os.path.exists(file_path):
                os.remove(file_path)
                
            return True
            
        except Exception as e:
            # 任务整体异常处理
            logger.error(f"处理文档任务失败: {str(e)}")
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error_message=str(e)
            )
            await push_task_update(task_id, task_service)
            
            # 清理临时文件
            if os.path.exists(file_path):
                os.remove(file_path)
                
            return False

async def push_task_update(task_id: str, task_service):
    """推送任务状态更新"""
    try:
        # 获取完整任务状态
        task_data = await task_service.get_task_with_details(task_id)
        
        # 异步推送到WebSocket
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
    async with get_async_session() as session:
        task_service = TaskService(session)
        
        # 更新任务状态为已取消
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.CANCELLED
        )
        
        # 推送状态更新
        await push_task_update(task_id, task_service) 