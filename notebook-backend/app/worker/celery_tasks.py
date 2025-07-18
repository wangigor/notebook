# -*- coding: utf-8 -*-
import os
import asyncio
import logging
import traceback
from app.core.celery_app import celery_app
from app.database import get_db, SessionLocal
from app.services.task_service import TaskService
from app.services.document_service import DocumentService
from app.services.storage_service import StorageService
from app.services.task_detail_service import TaskDetailService
from app.ws.connection_manager import ws_manager
from app.models.task import TaskStatus, TaskStepStatus
from datetime import datetime, timezone
from app.core.config import settings
import traceback
from app.models.document import DocumentStatus
from app.worker.websocket_manager import WebSocketManager


logger = logging.getLogger(__name__)
ws_manager = WebSocketManager()

@celery_app.task(bind=True, name="test_wikipedia_proxy")
def test_wikipedia_proxy_task(self, entity_name: str, entity_type: str = None):
    """测试Wikipedia代理连接的Celery任务"""
    logger.info(f"开始测试Wikipedia代理连接: entity_name={entity_name}, entity_type={entity_type}")
    
    try:
        from app.services.wikipedia_mcp_server import WikipediaMCPServer
        
        # 初始化Wikipedia服务器
        server = WikipediaMCPServer()
        logger.info("Wikipedia MCP服务器初始化成功")
        
        # 执行搜索
        result = server.search_entity(entity_name, entity_type)
        logger.info(f"Wikipedia搜索完成: found={result.get('found', False)}")
        
        return {
            "status": "success",
            "entity_name": entity_name,
            "entity_type": entity_type,
            "search_result": result,
            "proxy_working": True
        }
        
    except Exception as e:
        error_msg = f"Wikipedia代理测试失败: {str(e)}"
        logger.error(error_msg)
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        
        return {
            "status": "error",
            "entity_name": entity_name,
            "entity_type": entity_type,
            "error": error_msg,
            "proxy_working": False
        }


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


# 🆕 增量实体统一任务
@celery_app.task(bind=True, name="incremental_entity_unification")
def incremental_entity_unification_task(self, document_id, task_id, entities_data, mode="incremental"):
    """增量实体统一Celery任务"""
    logger.info("Starting entity unification task: doc_id=%s, task_id=%s, mode=%s", document_id, task_id, mode)
    
    return asyncio.run(_execute_entity_unification(
        document_id=document_id,
        task_id=task_id, 
        entities_data=entities_data,
        mode=mode
    ))


# 🆕 全局语义实体统一任务 (新版本)
@celery_app.task(bind=True, name="global_semantic_entity_unification")
def global_semantic_entity_unification_task(self, document_id, task_id, entities_data):
    """全局语义实体统一Celery任务 - 使用LLM和Neo4j采样"""
    logger.info("Starting global semantic entity unification: doc_id=%s, task_id=%s, entities=%d", 
                document_id, task_id, len(entities_data))
    
    return asyncio.run(_execute_global_semantic_unification(
        document_id=document_id,
        task_id=task_id, 
        entities_data=entities_data
    ))


async def _execute_entity_unification(document_id, task_id, entities_data, mode):
    """执行实体统一"""
    session = SessionLocal()
    
    try:
        # 获取服务实例
        task_service = TaskService(session)
        task_detail_service = TaskDetailService(session)
        
        # 更新任务状态
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.RUNNING
        )
        
        # 推送状态更新
        await push_task_update(task_id, task_service, task_detail_service)
        
        # 执行统一逻辑
        if mode == "incremental":
            result = await _execute_incremental_unification(entities_data, task_id, task_detail_service)
        elif mode == "sampling":
            result = await _execute_sampling_unification(entities_data, task_id, task_detail_service)
        else:
            raise ValueError("Unknown unification mode: %s" % mode)
        
        # 更新任务状态为完成
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.COMPLETED
        )
        
        # 推送最终状态
        await push_task_update(task_id, task_service, task_detail_service)
        
        logger.info("Entity unification completed: %s", result.get('summary', 'No summary'))
        return result
        
    except Exception as e:
        logger.error("Entity unification failed: %s", str(e))
        logger.error(f"异常调用栈:\n{traceback.format_exc()}")
        
        # 更新任务状态为失败
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error_message=str(e)
        )
        
        # 推送错误状态
        await push_task_update(task_id, task_service, task_detail_service)
        raise
        
    finally:
        session.close()


async def _execute_global_semantic_unification(document_id, task_id, entities_data):
    """执行全局语义实体统一 - 使用新的v2服务"""
    session = SessionLocal()
    
    try:
        # 获取服务实例
        task_service = TaskService(session)
        task_detail_service = TaskDetailService(session)
        
        # 更新任务状态
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.RUNNING
        )
        
        # 推送状态更新
        await push_task_update(task_id, task_service, task_detail_service)
        
        # 创建任务详情记录
        detail = task_detail_service.create_task_detail(
            task_id=task_id,
            step_name="全局语义实体统一",
            step_order=0
        )
        
        # 更新详情状态为运行中
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.RUNNING,
            progress=10,
            details={"step": "初始化全局语义统一服务", "entity_count": len(entities_data)}
        )
        
        # 导入新的全局实体统一服务
        from app.services.global_entity_unification_service_v2 import (
            get_global_entity_unification_service, GlobalUnificationConfig
        )
        from app.models.entity import Entity
        
        # 创建配置
        config = GlobalUnificationConfig(
            max_sample_entities_per_type=50,
            min_entities_for_unification=2,
            enable_cross_document_sampling=True,
            llm_confidence_threshold=0.7,
            max_batch_size=20,
            enable_quality_boost=True
        )
        
        # 获取全局统一服务实例
        global_service = get_global_entity_unification_service(config)
        
        # 转换实体数据为实体对象
        entities = []
        for data in entities_data:
            try:
                entity = Entity(
                    id=data.get('id'),
                    name=data.get('name'),
                    type=data.get('type', 'unknown'),
                    entity_type=data.get('entity_type', data.get('type', 'unknown')),
                    description=data.get('description', ''),
                    properties=data.get('properties', {}),
                    confidence=data.get('confidence', 0.8),
                    source_text=data.get('source_text', ''),
                    start_pos=data.get('start_pos', 0),
                    end_pos=data.get('end_pos', 0),
                    chunk_neo4j_id=data.get('chunk_neo4j_id'),
                    document_postgresql_id=data.get('document_postgresql_id'),
                    document_neo4j_id=data.get('document_neo4j_id'),
                    embedding=data.get('embedding'),
                    quality_score=data.get('quality_score', 0.8),
                    importance_score=data.get('importance_score', 0.5)
                )
                entities.append(entity)
            except Exception as e:
                logger.warning("跳过无效实体数据: %s", str(e))
                continue
        
        logger.info("成功转换 %d 个实体对象用于全局语义统一", len(entities))
        
        # 更新任务详情
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.RUNNING,
            progress=30,
            details={"step": "开始全局语义统一", "validated_entities": len(entities)}
        )
        
        # 执行全局语义统一
        unification_result = await global_service.unify_entities_for_document(
            new_entities=entities,
            document_id=document_id
        )
        
        # 更新任务详情
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.RUNNING,
            progress=80,
            details={
                "step": "全局语义统一完成",
                "total_processed": unification_result.total_entities_processed,
                "entities_merged": unification_result.entities_merged,
                "entities_deleted": unification_result.entities_deleted,
                "relationships_updated": unification_result.relationships_updated,
                "processing_time": unification_result.processing_time,
                "type_statistics": unification_result.type_statistics
            }
        )
        
        # 最终完成
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.COMPLETED,
            progress=100,
            details={
                "input_entities": len(entities_data),
                "total_processed": unification_result.total_entities_processed,
                "entities_merged": unification_result.entities_merged,
                "entities_deleted": unification_result.entities_deleted,
                "relationships_updated": unification_result.relationships_updated,
                "processing_time": unification_result.processing_time,
                "type_statistics": unification_result.type_statistics,
                "errors": unification_result.errors,
                "mode": "global_semantic_unification",
                "success": unification_result.success,
                "message": f"全局语义统一完成: 处理{unification_result.total_entities_processed}个实体，合并{unification_result.entities_merged}个，删除{unification_result.entities_deleted}个重复"
            }
        )
        
        # 更新任务状态为完成
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.COMPLETED
        )
        
        # 推送最终状态
        await push_task_update(task_id, task_service, task_detail_service)
        
        logger.info("Global semantic entity unification completed: %s", unification_result)
        
        return {
            "success": unification_result.success,
            "mode": "global_semantic_unification",
            "input_count": len(entities_data),
            "total_processed": unification_result.total_entities_processed,
            "entities_merged": unification_result.entities_merged,
            "entities_deleted": unification_result.entities_deleted,
            "relationships_updated": unification_result.relationships_updated,
            "processing_time": unification_result.processing_time,
            "type_statistics": unification_result.type_statistics,
            "errors": unification_result.errors,
            "summary": f"全局语义统一完成: 处理{unification_result.total_entities_processed}个实体，合并{unification_result.entities_merged}个，删除{unification_result.entities_deleted}个重复，耗时{unification_result.processing_time:.3f}秒"
        }
        
    except Exception as e:
        logger.error("Global semantic entity unification failed: %s", str(e))
        logger.error(f"异常调用栈:\n{traceback.format_exc()}")
        
        # 更新任务状态为失败
        await task_service.update_task_status(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error_message=str(e)
        )
        
        # 推送错误状态
        await push_task_update(task_id, task_service, task_detail_service)
        raise
        
    finally:
        session.close()


async def _execute_incremental_unification(entities_data, task_id, task_detail_service):
    """执行增量统一"""
    # 创建任务详情记录
    detail = task_detail_service.create_task_detail(
        task_id=task_id,
        step_name="增量实体统一",
        step_order=0
    )
    
    try:
        # 🆕 使用新的类型分组实体统一服务
        logger.info("执行增量实体统一，输入 %d 个实体数据", len(entities_data))
        
        # 更新任务详情为运行中
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.RUNNING,
            progress=10,
            details={"step": "初始化实体统一服务", "entity_count": len(entities_data)}
        )
        
        # 导入实体统一服务
        from app.services.entity_unification_service import get_entity_unification_service
        from app.services.entity_extraction_service import EntityExtractionService
        
        # 获取实体统一服务实例
        unification_service = get_entity_unification_service()
        
        # 转换实体数据为实体对象
        from app.models.entity import Entity
        entities = []
        for data in entities_data:
            try:
                entity = Entity(
                    id=data.get('id'),
                    name=data.get('name'),
                    type=data.get('type', 'unknown'),
                    entity_type=data.get('entity_type', data.get('type', 'unknown')),
                    description=data.get('description', ''),
                    properties=data.get('properties', {}),
                    confidence=data.get('confidence', 0.8),
                    source_text=data.get('source_text', ''),
                    start_pos=data.get('start_pos', 0),
                    end_pos=data.get('end_pos', 0),
                    chunk_neo4j_id=data.get('chunk_neo4j_id'),
                    document_postgresql_id=data.get('document_postgresql_id'),
                    document_neo4j_id=data.get('document_neo4j_id'),
                    embedding=data.get('embedding'),
                    quality_score=data.get('quality_score', 0.8),
                    importance_score=data.get('importance_score', 0.5)
                )
                entities.append(entity)
            except Exception as e:
                logger.warning("跳过无效实体数据: %s", str(e))
                continue
        
        logger.info("成功转换 %d 个实体对象", len(entities))
        
        # 更新任务详情
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.RUNNING,
            progress=30,
            details={"step": "开始实体统一", "validated_entities": len(entities)}
        )
        
        # 执行实体统一
        unification_result = await unification_service.unify_entities(entities)
        
        # 更新任务详情
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.RUNNING,
            progress=80,
            details={
                "step": "实体统一完成",
                "input_count": unification_result.statistics['input_entity_count'],
                "output_count": unification_result.statistics['output_entity_count'],
                "merge_count": unification_result.statistics['merge_operation_count'],
                "reduction_rate": unification_result.statistics['reduction_rate'],
                "processing_time": unification_result.processing_time,
                "processing_strategy": unification_result.statistics.get('processing_strategy', 'unknown')
            }
        )
        
        # 最终完成
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.COMPLETED,
            progress=100,
            details={
                "input_entities": len(entities_data),
                "output_entities": len(unification_result.unified_entities),
                "merge_operations": len(unification_result.merge_operations),
                "processing_time": unification_result.processing_time,
                "quality_metrics": unification_result.quality_metrics,
                "statistics": unification_result.statistics,
                "mode": "incremental_type_grouping",
                "message": "增量类型分组统一完成: %d -> %d (减少 %d 个重复)" % (
                    len(entities_data), 
                    len(unification_result.unified_entities), 
                    len(entities_data) - len(unification_result.unified_entities)
                )
            }
        )
        
        return {
            "success": True,
            "mode": "incremental_type_grouping",
            "input_count": len(entities_data),
            "output_count": len(unification_result.unified_entities),
            "merge_count": len(unification_result.merge_operations),
            "reduction_rate": unification_result.statistics['reduction_rate'],
            "processing_time": unification_result.processing_time,
            "quality_metrics": unification_result.quality_metrics,
            "processing_strategy": unification_result.statistics.get('processing_strategy'),
            "summary": "增量类型分组统一完成: %d -> %d (减少 %d 个重复), 耗时: %.3f秒" % (
                len(entities_data), 
                len(unification_result.unified_entities), 
                len(entities_data) - len(unification_result.unified_entities),
                unification_result.processing_time
            )
        }
        
    except Exception as e:
        # 更新任务详情为失败
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.FAILED,
            error_message=str(e)
        )
        raise


async def _execute_sampling_unification(entities_data, task_id, task_detail_service):
    """执行抽样统一"""
    # 创建任务详情记录
    detail = task_detail_service.create_task_detail(
        task_id=task_id,
        step_name="抽样实体统一",
        step_order=0
    )
    
    try:
        # 🆕 使用新的类型分组抽样实体统一服务
        logger.info("执行抽样实体统一，输入 %d 个实体数据", len(entities_data))
        
        # 按实体类型分组
        entity_types = set(data.get('type', 'unknown') for data in entities_data)
        logger.info("发现 %d 个实体类型: %s", len(entity_types), list(entity_types))
        
        # 更新任务详情为运行中
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.RUNNING,
            progress=10,
            details={
                "step": "初始化抽样统一服务", 
                "entity_count": len(entities_data),
                "entity_types": list(entity_types)
            }
        )
        
        # 导入实体统一服务
        from app.services.entity_unification_service import get_entity_unification_service
        from app.services.entity_extraction_service import EntityExtractionService
        
        # 获取实体统一服务实例
        unification_service = get_entity_unification_service()
        
        # 转换实体数据为实体对象
        from app.models.entity import Entity
        entities = []
        for data in entities_data:
            try:
                entity = Entity(
                    id=data.get('id'),
                    name=data.get('name'),
                    type=data.get('type', 'unknown'),
                    entity_type=data.get('entity_type', data.get('type', 'unknown')),
                    description=data.get('description', ''),
                    properties=data.get('properties', {}),
                    confidence=data.get('confidence', 0.8),
                    source_text=data.get('source_text', ''),
                    start_pos=data.get('start_pos', 0),
                    end_pos=data.get('end_pos', 0),
                    chunk_neo4j_id=data.get('chunk_neo4j_id'),
                    document_postgresql_id=data.get('document_postgresql_id'),
                    document_neo4j_id=data.get('document_neo4j_id'),
                    embedding=data.get('embedding'),
                    quality_score=data.get('quality_score', 0.8),
                    importance_score=data.get('importance_score', 0.5)
                )
                entities.append(entity)
            except Exception as e:
                logger.warning("跳过无效实体数据: %s", str(e))
                continue
        
        logger.info("成功转换 %d 个实体对象", len(entities))
        
        # 更新任务详情
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.RUNNING,
            progress=30,
            details={
                "step": "开始抽样统一", 
                "validated_entities": len(entities),
                "entity_types": list(entity_types)
            }
        )
        
        # 执行抽样统一（使用类型分组策略）
        unification_result = await unification_service.unify_entities(entities)
        
        # 更新任务详情
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.RUNNING,
            progress=80,
            details={
                "step": "抽样统一完成",
                "input_count": unification_result.statistics['input_entity_count'],
                "output_count": unification_result.statistics['output_entity_count'],
                "merge_count": unification_result.statistics['merge_operation_count'],
                "reduction_rate": unification_result.statistics['reduction_rate'],
                "processing_time": unification_result.processing_time,
                "processing_strategy": unification_result.statistics.get('processing_strategy', 'unknown'),
                "entity_types_processed": list(entity_types)
            }
        )
        
        # 最终完成
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.COMPLETED,
            progress=100,
            details={
                "input_entities": len(entities_data),
                "output_entities": len(unification_result.unified_entities),
                "merge_operations": len(unification_result.merge_operations),
                "processing_time": unification_result.processing_time,
                "quality_metrics": unification_result.quality_metrics,
                "statistics": unification_result.statistics,
                "entity_types_processed": list(entity_types),
                "mode": "sampling_type_grouping",
                "message": "抽样类型分组统一完成: %d -> %d (减少 %d 个重复), 处理 %d 个类型" % (
                    len(entities_data), 
                    len(unification_result.unified_entities), 
                    len(entities_data) - len(unification_result.unified_entities),
                    len(entity_types)
                )
            }
        )
        
        return {
            "success": True,
            "mode": "sampling_type_grouping",
            "input_count": len(entities_data),
            "output_count": len(unification_result.unified_entities),
            "merge_count": len(unification_result.merge_operations),
            "reduction_rate": unification_result.statistics['reduction_rate'],
            "processing_time": unification_result.processing_time,
            "quality_metrics": unification_result.quality_metrics,
            "processing_strategy": unification_result.statistics.get('processing_strategy'),
            "entity_types": list(entity_types),
            "summary": "抽样类型分组统一完成: %d -> %d (减少 %d 个重复), 处理 %d 个类型, 耗时: %.3f秒" % (
                len(entities_data), 
                len(unification_result.unified_entities), 
                len(entities_data) - len(unification_result.unified_entities),
                len(entity_types),
                unification_result.processing_time
            )
        }
        
    except Exception as e:
        # 更新任务详情为失败
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.FAILED,
            error_message=str(e)
        )
        raise


@celery_app.task(name="trigger_document_entity_unification")
def trigger_document_entity_unification(document_id, extracted_entities, unification_mode="incremental"):
    """文档解析完成后触发实体统一"""
    import uuid
    from datetime import datetime
    
    logger.info("Triggering entity unification for document %d with %d entities, mode: %s", 
                document_id, len(extracted_entities), unification_mode)
    
    # 使用标准UUID生成任务ID
    task_id = str(uuid.uuid4())
    
    # 创建友好的标识符用于日志和metadata
    friendly_id = "entity_unification_%d_%s" % (document_id, datetime.now().strftime('%Y%m%d_%H%M%S'))
    
    # 创建任务记录
    try:
        session = SessionLocal()
        task_service = TaskService(session)
        
        # 创建任务对象
        from app.models.task import Task, TaskStatus
        task = Task(
            id=task_id,  # 使用标准UUID
            name=f"实体统一: 文档{document_id}",
            task_type="ENTITY_UNIFICATION",
            created_by=1,  # 系统用户ID
            document_id=str(document_id),
            description=f"对文档{document_id}的{len(extracted_entities)}个实体进行{unification_mode}统一",
            task_metadata={
                "entity_count": len(extracted_entities),
                "unification_mode": unification_mode,
                "document_id": document_id,
                "friendly_id": friendly_id  # 保存友好标识符
            },
            status=TaskStatus.PENDING,
            progress=0.0,
            created_at=datetime.now(timezone.utc)
        )
        
        # 保存到数据库
        session.add(task)
        session.commit()
        session.refresh(task)
        
        logger.info("Entity unification task created successfully: %s (friendly_id: %s)", task_id, friendly_id)
        
    except Exception as e:
        logger.error("Failed to create entity unification task: %s", str(e))
        session.rollback()
        raise
    finally:
        session.close()
    
    # 启动异步统一任务
    if unification_mode == "global_semantic":
        # 使用新的全局语义统一任务
        global_semantic_entity_unification_task.delay(
            document_id=document_id,
            task_id=task_id,  # 传递标准UUID
            entities_data=extracted_entities
        )
    else:
        # 使用原有的增量统一任务
        incremental_entity_unification_task.delay(
            document_id=document_id,
            task_id=task_id,  # 传递标准UUID
            entities_data=extracted_entities,
            mode=unification_mode
        )
    
    return {
        "status": "triggered",
        "document_id": document_id,
        "task_id": task_id,  # 返回标准UUID
        "friendly_id": friendly_id,  # 返回友好标识符
        "entity_count": len(extracted_entities),
        "mode": unification_mode
    } 