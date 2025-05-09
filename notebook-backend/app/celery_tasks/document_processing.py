from celery import Celery, chain, group
from datetime import datetime
import os
import time
import random
import logging
import asyncio
from app.services.task_service import TaskService
from app.services.task_detail_service import TaskDetailService
from app.services.document_service import DocumentService
from app.models.task import TaskStatus, TaskStepType
from app.database import get_db
from app.websockets.task_manager import sync_push_task_update
from app.celery_tasks.decorators import update_task_status

logger = logging.getLogger(__name__)
celery_app = Celery('document_tasks')

@celery_app.task(bind=True, name="process_document")
def process_document(self, document_id: str, task_id: str, file_path: str):
    """处理文档的主任务"""
    db = next(get_db())
    try:
        task_service = TaskService(db)
        task_detail_service = TaskDetailService(db)
        
        # 更新任务状态为运行中
        task_service.update_task(task_id, status=TaskStatus.RUNNING, started_at=datetime.utcnow())
        
        # 初始推送任务状态
        sync_push_task_update(task_id, task_service)
        
        # 定义处理步骤
        steps = [
            {"name": "文件验证", "type": TaskStepType.FILE_UPLOAD, "order": 1},
            {"name": "文本提取", "type": TaskStepType.TEXT_EXTRACTION, "order": 2},
            {"name": "文本分块", "type": TaskStepType.TEXT_SPLITTING, "order": 3},
            {"name": "生成向量", "type": TaskStepType.EMBEDDING_GENERATION, "order": 4},
            {"name": "向量存储", "type": TaskStepType.VECTOR_STORAGE, "order": 5}
        ]
        
        # 创建任务详情记录
        task_details = []
        for step in steps:
            task_detail = task_detail_service.create_task_detail(
                task_id=task_id,
                step_name=step["name"],
                step_order=step["order"]
            )
            task_details.append(task_detail)
        
        # 再次推送更新，显示所有处理步骤
        sync_push_task_update(task_id, task_service, task_detail_service)
        
        # 构建子任务链
        subtasks = chain(
            validate_file.s(document_id, task_id, task_details[0].id, file_path),
            extract_text.s(document_id, task_id, task_details[1].id),
            split_text.s(document_id, task_id, task_details[2].id),
            generate_embeddings.s(document_id, task_id, task_details[3].id),
            store_vectors.s(document_id, task_id, task_details[4].id)
        )
        
        # 执行子任务链
        result = subtasks.apply_async()
        return {"status": "started", "task_id": task_id}
        
    except Exception as e:
        # 发生异常时更新任务状态
        task_service.update_task(
            task_id, 
            status=TaskStatus.FAILED, 
            error_message=str(e),
            completed_at=datetime.utcnow()
        )
        # 推送失败状态
        sync_push_task_update(task_id, task_service)
        logger.error(f"处理文档任务失败: {str(e)}")
        raise

@celery_app.task(bind=True, name="validate_file")
@update_task_status
def validate_file(self, document_id: str, task_id: str, task_detail_id: int, file_path: str):
    """验证文件任务"""
    db = next(get_db())
    task_detail_service = TaskDetailService(db)
    task_service = TaskService(db)
    
    try:
        # 核心验证逻辑
        # TODO: 实现文件验证逻辑
        # 1. 检查文件是否存在
        # 2. 验证文件格式
        # 3. 检查文件大小
        
        # 模拟处理过程
        time.sleep(1)
        
        # 更新任务详情为完成
        task_detail_service.update_task_detail(
            task_detail_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            details={"file_size": os.path.getsize(file_path), "file_type": "pdf"}
        )
        
        # 更新主任务状态
        task_service.update_task_status_based_on_details(task_id)
        
        # 推送更新
        sync_push_task_update(task_id, task_service, task_detail_service)
        
        # 返回结果供下一个任务使用
        return {"document_id": document_id, "file_path": file_path, "validated": True}
    
    except Exception as e:
        # 异常将由装饰器处理
        raise

@celery_app.task(bind=True, name="extract_text")
@update_task_status
def extract_text(self, result_from_previous: dict, document_id: str, task_id: str, task_detail_id: int):
    """提取文本任务"""
    db = next(get_db())
    task_detail_service = TaskDetailService(db)
    task_service = TaskService(db)
    
    try:
        file_path = result_from_previous.get("file_path")
        if not file_path:
            raise ValueError("File path not provided from previous task")
        
        # TODO: 实现文本提取逻辑
        # 1. 根据文件类型选择合适的提取器
        # 2. 提取文本内容
        # 3. 清理和预处理文本
        
        # 模拟处理过程
        time.sleep(2)
        extracted_text = "这是从文件中提取的示例文本内容。"
        
        # 更新任务详情为完成
        task_detail_service.update_task_detail(
            task_detail_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            details={"text_length": len(extracted_text)}
        )
        
        # 更新主任务状态
        task_service.update_task_status_based_on_details(task_id)
        
        # 推送更新
        sync_push_task_update(task_id, task_service, task_detail_service)
        
        # 返回结果供下一个任务使用
        result_from_previous.update({"extracted_text": extracted_text})
        return result_from_previous
    
    except Exception as e:
        # 异常将由装饰器处理
        raise

@celery_app.task(bind=True, name="split_text")
@update_task_status
def split_text(self, result_from_previous: dict, document_id: str, task_id: str, task_detail_id: int):
    """文本分块任务"""
    db = next(get_db())
    task_detail_service = TaskDetailService(db)
    task_service = TaskService(db)
    
    try:
        text = result_from_previous.get("extracted_text")
        if not text:
            raise ValueError("Extracted text not provided from previous task")
        
        # TODO: 实现文本分块逻辑
        # 1. 根据配置确定分块策略
        # 2. 将文本分割成合适大小的块
        # 3. 确保语义完整性
        
        # 模拟处理过程
        time.sleep(1.5)
        chunks = [text[i:i+100] for i in range(0, len(text), 100)]
        
        # 更新任务详情为完成
        task_detail_service.update_task_detail(
            task_detail_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            details={"chunk_count": len(chunks)}
        )
        
        # 更新主任务状态
        task_service.update_task_status_based_on_details(task_id)
        
        # 推送更新
        sync_push_task_update(task_id, task_service, task_detail_service)
        
        # 返回结果供下一个任务使用
        result_from_previous.update({"chunks": chunks})
        return result_from_previous
    
    except Exception as e:
        # 异常将由装饰器处理
        raise

@celery_app.task(bind=True, name="generate_embeddings")
@update_task_status
def generate_embeddings(self, result_from_previous: dict, document_id: str, task_id: str, task_detail_id: int):
    """生成向量嵌入任务"""
    db = next(get_db())
    task_detail_service = TaskDetailService(db)
    task_service = TaskService(db)
    
    try:
        chunks = result_from_previous.get("chunks")
        if not chunks:
            raise ValueError("Text chunks not provided from previous task")
        
        # TODO: 实现向量生成逻辑
        # 1. 批量处理文本块
        # 2. 调用嵌入模型API
        # 3. 处理和验证生成的向量
        
        # 模拟处理过程
        total_chunks = len(chunks)
        embeddings = []
        
        for i, chunk in enumerate(chunks):
            # 模拟向量生成
            time.sleep(0.5)
            # 生成随机向量作为示例
            embedding = [random.random() for _ in range(10)]
            embeddings.append(embedding)
            
            # 更新进度
            progress = int((i + 1) / total_chunks * 90) + 10
            task_detail_service.update_task_detail(
                task_detail_id,
                progress=progress,
                details={"processed_chunks": i + 1, "total_chunks": total_chunks}
            )
            
            # 定期推送更新进度
            if i % 5 == 0 or i == total_chunks - 1:
                sync_push_task_update(task_id, task_service, task_detail_service)
        
        # 更新任务详情为完成
        task_detail_service.update_task_detail(
            task_detail_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            details={"embedding_count": len(embeddings)}
        )
        
        # 更新主任务状态
        task_service.update_task_status_based_on_details(task_id)
        
        # 推送更新
        sync_push_task_update(task_id, task_service, task_detail_service)
        
        # 返回结果供下一个任务使用
        result_from_previous.update({"embeddings": embeddings})
        return result_from_previous
    
    except Exception as e:
        # 异常将由装饰器处理
        raise

@celery_app.task(bind=True, name="store_vectors")
@update_task_status
def store_vectors(self, result_from_previous: dict, document_id: str, task_id: str, task_detail_id: int):
    """存储向量到向量数据库任务"""
    db = next(get_db())
    task_detail_service = TaskDetailService(db)
    task_service = TaskService(db)
    document_service = DocumentService(db)
    
    try:
        chunks = result_from_previous.get("chunks")
        embeddings = result_from_previous.get("embeddings")
        
        if not chunks or not embeddings:
            raise ValueError("Chunks or embeddings not provided from previous tasks")
        
        # TODO: 实现向量存储逻辑
        # 1. 连接向量数据库
        # 2. 批量插入向量
        # 3. 验证存储结果
        
        # 模拟处理过程
        time.sleep(2)
        
        # 更新任务详情为完成
        task_detail_service.update_task_detail(
            task_detail_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            details={"stored_vectors": len(embeddings)}
        )
        
        # 更新文档状态
        document_service.update_document_status(document_id, "AVAILABLE")
        
        # 更新主任务状态
        task_service.update_task_status_based_on_details(task_id)
        
        # 推送最终完成状态
        sync_push_task_update(task_id, task_service, task_detail_service)
        
        # 返回处理结果
        return {
            "document_id": document_id,
            "task_id": task_id,
            "status": "completed",
            "chunks_processed": len(chunks),
            "vectors_stored": len(embeddings)
        }
    
    except Exception as e:
        # 异常将由装饰器处理
        raise 