"""
异步任务处理模块

负责异步任务队列管理和处理
"""

import asyncio
import logging
from asyncio import Queue, Task
from typing import Dict, Any, List, Optional

from app.core.config import settings
from app.worker.document_processor import DocumentProcessor
from app.services.document_service import DocumentService
from app.services.text_extraction import TextExtractor
from app.services.vector_store import VectorStore
from app.db.dependencies import get_db_session

logger = logging.getLogger(__name__)

# 全局任务队列
task_queue: Queue = asyncio.Queue()
# 任务处理器缓存
_document_processor: Optional[DocumentProcessor] = None

# 服务实例初始化函数
async def get_document_processor() -> DocumentProcessor:
    """
    获取文档处理器实例
    
    如果没有初始化，则创建一个新实例
    
    Returns:
        DocumentProcessor: 文档处理器实例
    """
    global _document_processor
    
    if _document_processor is None:
        # 初始化依赖服务
        async with get_db_session() as session:
            document_service = DocumentService(session)
            text_extractor = TextExtractor()
            vector_store = VectorStore()
            
            # 创建文档处理器
            _document_processor = DocumentProcessor(
                document_service=document_service,
                text_extractor=text_extractor,
                vector_store=vector_store
            )
    
    return _document_processor

async def process_document_task(document_id: str) -> None:
    """
    处理单个文档任务
    
    Args:
        document_id: 文档ID
    """
    try:
        logger.info(f"开始执行文档处理任务: {document_id}")
        
        # 获取处理器
        processor = await get_document_processor()
        
        # 执行文档处理
        await processor.process_document(document_id)
        
        logger.info(f"文档处理任务完成: {document_id}")
    except Exception as e:
        logger.exception(f"文档处理任务失败: {document_id}, 错误: {str(e)}")

async def add_document_task(document_id: str) -> None:
    """
    添加文档处理任务到队列
    
    Args:
        document_id: 文档ID
    """
    logger.info(f"添加文档处理任务到队列: {document_id}")
    await task_queue.put(document_id)
    logger.info(f"当前队列任务数: {task_queue.qsize()}")

async def start_worker() -> None:
    """
    启动任务处理器工作循环
    
    持续监听任务队列并处理任务，出错时会继续尝试
    """
    logger.info("启动文档处理工作器")
    
    while True:
        try:
            # 从队列中获取任务
            document_id = await task_queue.get()
            logger.info(f"从队列获取文档处理任务: {document_id}")
            
            # 处理文档
            await process_document_task(document_id)
            
            # 标记任务完成
            task_queue.task_done()
            
        except Exception as e:
            logger.exception(f"任务处理器发生错误: {str(e)}")
            # 在发生错误时等待一段时间，避免CPU持续占用
            await asyncio.sleep(5) 