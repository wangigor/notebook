#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全版本的Celery任务处理器
避开SIGSEGV段错误问题，使用简化的依赖链
"""
import logging
import os
import time
from typing import Dict, Any, Optional

# 设置环境标志
os.environ['CELERY_WORKER'] = '1'

from app.core.config import settings
from app.celery_app import celery_app as app
from app.models.document import Document
from app.db.dependencies import get_db
from app.services.neo4j_service import Neo4jService
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)

@app.task(bind=True, name="process_document_safe")
def process_document_safe(self, task_id: str, doc_id: int, processing_mode: str = "graph") -> Dict[str, Any]:
    """
    安全版本的文档处理任务
    避开复杂的智能实体统一，使用基础处理流程
    """
    logger.info(f"🛡️ 开始安全文档处理: doc_id={doc_id}, task_id={task_id}, 处理模式={processing_mode}")
    
    task_service = None
    
    try:
        # 初始化任务服务
        task_service = TaskService()
        
        # 更新任务状态为运行中
        logger.info(f"更新任务状态: {task_id}, 状态: RUNNING")
        task_service.update_task_status(task_id, "RUNNING", progress=10)
        
        # 检查是否使用安全模式
        use_safe_mode = getattr(settings, 'FORCE_SAFE_MODE', True)
        
        if use_safe_mode:
            logger.info("🛡️ 使用安全模式处理文档")
            result = _process_document_safe_mode(doc_id, task_id, processing_mode, task_service)
        else:
            logger.info("⚡ 使用完整模式处理文档")
            result = _process_document_full_mode(doc_id, task_id, processing_mode, task_service)
        
        # 更新任务为完成状态
        task_service.update_task_status(task_id, "COMPLETED", progress=100, result=result)
        
        logger.info(f"✅ 文档处理完成: doc_id={doc_id}, task_id={task_id}")
        return result
        
    except Exception as e:
        error_msg = f"文档处理失败: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        # 更新任务为失败状态
        if task_service:
            try:
                task_service.update_task_status(task_id, "FAILED", error=error_msg)
            except Exception as update_error:
                logger.error(f"❌ 更新任务状态失败: {update_error}")
        
        # 重新抛出异常
        raise


def _process_document_safe_mode(doc_id: int, task_id: str, processing_mode: str, 
                              task_service: TaskService) -> Dict[str, Any]:
    """
    安全模式文档处理
    避开智能实体统一，使用基础文档解析和存储
    """
    logger.info(f"🛡️ 开始安全模式处理: doc_id={doc_id}")
    
    start_time = time.time()
    
    try:
        # 1. 获取文档信息
        task_service.update_task_status(task_id, "RUNNING", progress=20)
        
        db = next(get_db())
        document = db.query(Document).filter(Document.id == doc_id).first()
        
        if not document:
            raise ValueError(f"文档未找到: doc_id={doc_id}")
        
        logger.info(f"获取文档: {document.title}, 文件路径: {document.file_path}")
        
        # 2. 基础文档解析
        task_service.update_task_status(task_id, "RUNNING", progress=40)
        
        from app.services.document_parser import DocumentParser
        parser = DocumentParser()
        
        # 解析文档内容
        parsed_content = parser.parse_file(document.file_path)
        logger.info(f"文档解析完成，内容长度: {len(parsed_content)}")
        
        # 3. 简单分块
        task_service.update_task_status(task_id, "RUNNING", progress=60)
        
        chunks = _create_simple_chunks(parsed_content, doc_id)
        logger.info(f"文档分块完成，分块数量: {len(chunks)}")
        
        # 4. 基础存储（跳过向量化和智能处理）
        task_service.update_task_status(task_id, "RUNNING", progress=80)
        
        if processing_mode == "graph":
            storage_result = _store_chunks_to_neo4j(chunks, document)
        else:
            storage_result = {"status": "success", "chunks_stored": len(chunks)}
        
        # 5. 更新文档状态
        document.processing_status = "completed"
        document.chunk_count = len(chunks)
        db.commit()
        
        processing_time = time.time() - start_time
        
        result = {
            "status": "success",
            "processing_mode": "safe",
            "document_id": doc_id,
            "chunks_created": len(chunks),
            "processing_time": processing_time,
            "storage_result": storage_result,
            "message": "安全模式处理完成"
        }
        
        logger.info(f"🎉 安全模式处理完成: {processing_time:.2f}秒")
        return result
        
    except Exception as e:
        logger.error(f"❌ 安全模式处理失败: {str(e)}")
        raise


def _process_document_full_mode(doc_id: int, task_id: str, processing_mode: str,
                              task_service: TaskService) -> Dict[str, Any]:
    """
    完整模式文档处理
    使用智能实体统一等高级功能
    """
    logger.info(f"⚡ 开始完整模式处理: doc_id={doc_id}")
    
    # 这里可以调用原始的复杂处理逻辑
    # 但在当前阶段，为了避免SIGSEGV，暂时回退到安全模式
    logger.warning("完整模式暂时不可用，回退到安全模式")
    return _process_document_safe_mode(doc_id, task_id, processing_mode, task_service)


def _create_simple_chunks(content: str, doc_id: int, chunk_size: int = 1000) -> list:
    """
    创建简单的文本分块
    """
    chunks = []
    
    # 按段落分割
    paragraphs = content.split('\n\n')
    
    current_chunk = ""
    chunk_index = 0
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        
        # 如果当前块加上新段落超过大小限制，则创建新块
        if len(current_chunk) + len(paragraph) > chunk_size and current_chunk:
            chunks.append({
                'id': f"doc_{doc_id}_chunk_{chunk_index}",
                'content': current_chunk,
                'chunk_index': chunk_index,
                'document_id': doc_id,
                'start_pos': 0,  # 简化位置信息
                'end_pos': len(current_chunk)
            })
            current_chunk = paragraph
            chunk_index += 1
        else:
            current_chunk += "\n\n" + paragraph if current_chunk else paragraph
    
    # 添加最后一个块
    if current_chunk:
        chunks.append({
            'id': f"doc_{doc_id}_chunk_{chunk_index}",
            'content': current_chunk,
            'chunk_index': chunk_index,
            'document_id': doc_id,
            'start_pos': 0,
            'end_pos': len(current_chunk)
        })
    
    return chunks


def _store_chunks_to_neo4j(chunks: list, document) -> Dict[str, Any]:
    """
    将分块存储到Neo4j（基础版本，无向量化）
    """
    try:
        neo4j_service = Neo4jService()
        
        # 创建文档节点
        doc_query = """
        MERGE (d:Document {id: $doc_id})
        SET d.title = $title,
            d.file_path = $file_path,
            d.chunk_count = $chunk_count,
            d.created_at = datetime(),
            d.processing_mode = 'safe'
        RETURN d
        """
        
        neo4j_service.execute_query(doc_query, {
            'doc_id': document.id,
            'title': document.title,
            'file_path': document.file_path,
            'chunk_count': len(chunks)
        })
        
        # 创建分块节点
        chunks_stored = 0
        for chunk in chunks:
            chunk_query = """
            CREATE (c:Chunk {
                id: $chunk_id,
                content: $content,
                chunk_index: $chunk_index,
                document_id: $document_id,
                start_pos: $start_pos,
                end_pos: $end_pos,
                created_at: datetime()
            })
            WITH c
            MATCH (d:Document {id: $document_id})
            CREATE (d)-[:HAS_CHUNK]->(c)
            RETURN c
            """
            
            neo4j_service.execute_query(chunk_query, {
                'chunk_id': chunk['id'],
                'content': chunk['content'],
                'chunk_index': chunk['chunk_index'],
                'document_id': chunk['document_id'],
                'start_pos': chunk['start_pos'],
                'end_pos': chunk['end_pos']
            })
            chunks_stored += 1
        
        logger.info(f"✅ Neo4j存储完成: {chunks_stored} 个分块")
        
        return {
            "status": "success",
            "chunks_stored": chunks_stored,
            "storage_type": "neo4j_basic"
        }
        
    except Exception as e:
        logger.error(f"❌ Neo4j存储失败: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "chunks_stored": 0
        }


@app.task(bind=True, name="test_safe_task")
def test_safe_task(self) -> Dict[str, Any]:
    """
    测试安全任务处理
    """
    logger.info("🧪 开始安全任务测试")
    
    try:
        import time
        time.sleep(2)  # 模拟处理
        
        result = {
            "status": "success",
            "message": "安全任务测试完成",
            "timestamp": time.time(),
            "worker_pid": os.getpid()
        }
        
        logger.info("✅ 安全任务测试成功")
        return result
        
    except Exception as e:
        logger.error(f"❌ 安全任务测试失败: {str(e)}")
        raise 