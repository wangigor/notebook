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
from app.services.vector_store import VectorStoreService

logger = logging.getLogger(__name__)
ws_manager = WebSocketManager()

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
    session = SessionLocal()
    try:
        # 获取服务实例
        task_service = TaskService(session)
        task_detail_service = TaskDetailService(session)
        # 创建向量存储服务实例
        vector_store = VectorStoreService()
        # 修复：正确传递vector_store参数给DocumentService
        document_service = DocumentService(session, vector_store)
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
                    "description": "验证文件完整性和格式",
                    "func": document_service.validate_file,
                    "weight": 5.0,
                    "step_type": "FILE_VALIDATION",
                    "metadata": {
                        "supported_formats": ["pdf", "docx", "xlsx", "txt", "md"],
                        "estimated_time": "1-2秒"
                    }
                },
                {
                    "name": "文件上传",
                    "description": "上传文件到对象存储",
                    "func": storage_service.upload_file_and_update_document,
                    "weight": 10.0,
                    "step_type": "FILE_UPLOAD",
                    "metadata": {
                        "source_file": file_path,
                        "estimated_time": "1-3秒"
                    }
                },
                {
                    "name": "文本提取",
                    "description": "从文件中提取文本内容",
                    "func": document_service.extract_text_from_file_path,
                    "weight": 30.0,
                    "step_type": "TEXT_EXTRACTION",
                    "metadata": {
                        "supported_formats": ["pdf", "docx", "txt", "md"],
                        "estimated_time": "5-30秒"
                    }
                },
                {
                    "name": "文本预处理",
                    "description": "清洗和格式化提取的文本",
                    "func": document_service.preprocess_text,
                    "weight": 15.0,
                    "step_type": "TEXT_PROCESSING",
                    "metadata": {
                        "operations": ["去除冗余空格", "标准化换行符", "去除特殊字符"],
                        "estimated_time": "1-5秒"
                    }
                },
                {
                    "name": "向量化处理",
                    "description": "生成文本的嵌入向量表示",
                    "func": document_service.vectorize_document,
                    "weight": 30.0,
                    "step_type": "EMBEDDING_GENERATION",
                    "metadata": {
                        "embedding_model": settings.DASHSCOPE_EMBEDDING_MODEL,
                        "max_text_length": 2048,
                        "estimated_time": "5-20秒"
                    }
                },
                {
                    "name": "保存向量",
                    "description": "将向量存储到向量数据库",
                    "func": document_service.store_document_vectors,
                    "weight": 10.0,
                    "step_type": "VECTOR_STORAGE",
                    "metadata": {
                        "vector_db": "Qdrant",
                        "collection": settings.QDRANT_COLLECTION_NAME,
                        "estimated_time": "1-3秒"
                    }
                }
            ]
            
            # 为每个步骤创建TaskDetail记录
            task_details = []
            for i, step in enumerate(steps):
                task_detail = task_detail_service.create_task_detail(
                    task_id=task_id,
                    step_name=step["name"],
                    step_order=i
                )
                task_details.append(task_detail)
            
            # 获取文档信息，特别是需要得到user_id
            document = document_service.get_document_by_id(doc_id)
            if not document:
                raise Exception(f"找不到文档: {doc_id}")
                
            # 获取任务元数据，用于获取存储路径信息
            task = await task_service.get_task_by_id(task_id)
            if not task or not task.metadata:
                logger.warning(f"任务{task_id}不存在或没有元数据，将使用生成的新路径")
                
            # 执行每个步骤
            document_data = {
                "file_path": file_path, 
                "user_id": document.user_id
            }
            
            # 如果任务元数据中包含object_key和bucket_name，添加到document_data
            if task and task.metadata:
                if "object_key" in task.metadata:
                    document_data["object_key"] = task.metadata["object_key"]
                    logger.info(f"使用任务元数据中的object_key: {document_data['object_key']}")
                if "bucket_name" in task.metadata:
                    document_data["bucket_name"] = task.metadata["bucket_name"]
                    logger.info(f"使用任务元数据中的bucket_name: {document_data['bucket_name']}")
                    
            overall_progress = 0

            for i, step in enumerate(steps):
                step_start_time = datetime.utcnow()
                
                # 更新步骤状态为运行中
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[i].id,
                    status=TaskStatus.RUNNING,
                    progress=0,
                    details=step.get("metadata", {})
                )
                
                # 同步更新Task状态
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                
                # 执行步骤
                try:
                    # 如果是validate_file函数，不传递user_id参数
                    if step["func"] == document_service.validate_file:
                        step_data = {"file_path": document_data["file_path"]}
                        step_result = await step["func"](doc_id, **step_data)
                    else:
                        # 对于文件上传步骤，添加详细日志
                        if step["func"] == storage_service.upload_file_and_update_document:
                            object_key_before = document_data.get("object_key", "未提供")
                            bucket_name_before = document_data.get("bucket_name", settings.DOCUMENT_BUCKET)
                            logger.info(f"执行文件上传步骤前：object_key={object_key_before}, bucket_name={bucket_name_before}")
                            
                        # 执行步骤
                        step_result = await step["func"](doc_id, **document_data)
                        
                        # 对于文件上传步骤，验证路径是否一致
                        if step["func"] == storage_service.upload_file_and_update_document:
                            object_key_after = step_result.get("object_key", "未返回")
                            bucket_name_after = step_result.get("bucket_name", "未返回")
                            logger.info(f"执行文件上传步骤后：object_key={object_key_after}, bucket_name={bucket_name_after}")
                            
                            # 检查并记录是否一致
                            if "object_key" in document_data and object_key_after != document_data["object_key"]:
                                logger.warning(f"文件路径不一致！预期：{document_data['object_key']}，实际：{object_key_after}")
                            else:
                                logger.info("文件路径一致性确认：成功")
                    
                    document_data.update(step_result)  # 更新数据用于下一步骤
                    
                    # 计算执行时间
                    step_duration = (datetime.utcnow() - step_start_time).total_seconds()
                    
                    # 更新步骤状态为已完成
                    task_detail_service.update_task_detail(
                        task_detail_id=task_details[i].id,
                        status=TaskStatus.COMPLETED,
                        progress=100,
                        details={
                            "duration_seconds": step_duration,
                            "result_summary": f"步骤完成，用时{step_duration:.2f}秒",
                            **step_result  # 包含步骤返回的所有数据
                        }
                    )
                    
                    # 更新总体进度
                    overall_progress += step["weight"]
                    
                    # 同步更新Task状态
                    task_service.update_task_status_based_on_details(task_id)
                    await push_task_update(task_id, task_service, task_detail_service)
                    
                except Exception as e:
                    # 步骤失败处理
                    logger.error(f"任务步骤 {step['name']} 失败: {str(e)}")
                    
                    task_detail_service.update_task_detail(
                        task_detail_id=task_details[i].id,
                        status=TaskStatus.FAILED,
                        error_message=str(e),
                        details={
                            "error_details": {
                                "exception_type": type(e).__name__,
                                "stack_trace": traceback.format_exc()
                            }
                        }
                    )
                    
                    # 同步更新Task状态
                    task_service.update_task_status_based_on_details(task_id)
                    await push_task_update(task_id, task_service, task_detail_service)
                    
                    # 清理临时文件
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        
                    return False
            
            # 更新文档状态为已处理
            document_service.update_document_status(doc_id, DocumentStatus.COMPLETED)

            # 同步更新Task状态为已完成
            task_service.update_task_status_based_on_details(task_id)
            await push_task_update(task_id, task_service, task_detail_service)
            
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
            await push_task_update(task_id, task_service, task_detail_service)
            
            # 清理临时文件
            if os.path.exists(file_path):
                os.remove(file_path)
                
            return False
    finally:
        session.close()

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