# -*- coding: utf-8 -*-
"""
全局实体统一API路由
提供全局语义实体统一的REST API接口
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.global_entity_unification_service_v2 import (
    get_global_entity_unification_service, GlobalUnificationConfig
)
from app.services.neo4j_entity_sampler import get_neo4j_entity_sampler
from app.worker.celery_tasks import trigger_document_entity_unification
from app.models.entity import Entity

logger = logging.getLogger(__name__)

router = APIRouter()


class GlobalUnificationRequest(BaseModel):
    """全局统一请求模型"""
    entity_type: Optional[str] = Field(None, description="指定实体类型，为空则统一所有类型")
    limit: Optional[int] = Field(50, description="处理数量限制")
    force_unification: bool = Field(False, description="强制统一，忽略最小实体数限制")


class GlobalUnificationConfigRequest(BaseModel):
    """全局统一配置请求模型"""
    max_sample_entities_per_type: int = Field(50, description="每种类型最大采样数量")
    min_entities_for_unification: int = Field(2, description="启动统一的最小实体数")
    enable_cross_document_sampling: bool = Field(True, description="启用跨文档采样")
    llm_confidence_threshold: float = Field(0.7, description="LLM置信度阈值")
    max_batch_size: int = Field(20, description="最大批处理大小")
    enable_quality_boost: bool = Field(True, description="启用质量分数提升")


class DocumentUnificationRequest(BaseModel):
    """文档实体统一请求模型"""
    document_id: int = Field(..., description="文档ID")
    entities: List[Dict[str, Any]] = Field(..., description="实体数据列表")
    unification_mode: str = Field("global_semantic", description="统一模式")


@router.get("/statistics")
async def get_unification_statistics():
    """获取全局统一统计信息"""
    try:
        # 获取服务实例
        global_service = get_global_entity_unification_service()
        
        # 获取统计信息
        stats = await global_service.get_unification_statistics()
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"获取统一统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/entity-types")
async def get_entity_types():
    """获取所有实体类型及其数量"""
    try:
        # 获取Neo4j采样器
        sampler = get_neo4j_entity_sampler()
        
        # 获取实体类型统计
        type_stats = await sampler.get_entity_types_with_counts()
        
        return {
            "success": True,
            "data": {
                "type_counts": type_stats,
                "total_types": len(type_stats),
                "total_entities": sum(type_stats.values())
            }
        }
        
    except Exception as e:
        logger.error(f"获取实体类型失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取实体类型失败: {str(e)}")


@router.post("/manual-unify")
async def manual_unify_entities(
    request: GlobalUnificationRequest,
    background_tasks: BackgroundTasks
):
    """手动触发实体统一"""
    try:
        # 获取服务实例
        global_service = get_global_entity_unification_service()
        
        if request.entity_type:
            # 统一指定类型
            result = await global_service.manual_unify_entity_type(
                entity_type=request.entity_type,
                limit=request.limit
            )
            
            return {
                "success": True,
                "message": f"已完成 {request.entity_type} 类型实体统一",
                "data": {
                    "entity_type": request.entity_type,
                    "total_processed": result.total_entities_processed,
                    "entities_merged": result.entities_merged,
                    "entities_deleted": result.entities_deleted,
                    "relationships_updated": result.relationships_updated,
                    "processing_time": result.processing_time,
                    "errors": result.errors
                }
            }
        else:
            # 获取所有实体类型
            sampler = get_neo4j_entity_sampler()
            type_stats = await sampler.get_entity_types_with_counts()
            
            if not type_stats:
                return {
                    "success": False,
                    "message": "没有发现任何实体类型"
                }
            
            # 异步处理所有类型
            total_results = {}
            for entity_type in type_stats.keys():
                try:
                    result = await global_service.manual_unify_entity_type(
                        entity_type=entity_type,
                        limit=request.limit
                    )
                    total_results[entity_type] = {
                        "success": result.success,
                        "total_processed": result.total_entities_processed,
                        "entities_merged": result.entities_merged,
                        "entities_deleted": result.entities_deleted,
                        "relationships_updated": result.relationships_updated,
                        "processing_time": result.processing_time,
                        "errors": result.errors
                    }
                except Exception as e:
                    logger.error(f"统一 {entity_type} 类型失败: {str(e)}")
                    total_results[entity_type] = {
                        "success": False,
                        "error": str(e)
                    }
            
            # 汇总结果
            total_processed = sum(r.get("total_processed", 0) for r in total_results.values())
            total_merged = sum(r.get("entities_merged", 0) for r in total_results.values())
            total_deleted = sum(r.get("entities_deleted", 0) for r in total_results.values())
            total_relationships = sum(r.get("relationships_updated", 0) for r in total_results.values())
            
            return {
                "success": True,
                "message": f"已完成所有实体类型统一",
                "data": {
                    "total_types_processed": len(total_results),
                    "total_entities_processed": total_processed,
                    "total_entities_merged": total_merged,
                    "total_entities_deleted": total_deleted,
                    "total_relationships_updated": total_relationships,
                    "results_by_type": total_results
                }
            }
        
    except Exception as e:
        logger.error(f"手动实体统一失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"实体统一失败: {str(e)}")


@router.post("/trigger-document-unification")
async def trigger_document_unification(request: DocumentUnificationRequest):
    """触发文档实体统一任务"""
    try:
        # 验证统一模式
        valid_modes = ["incremental", "sampling", "global_semantic"]
        if request.unification_mode not in valid_modes:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的统一模式: {request.unification_mode}。有效模式: {valid_modes}"
            )
        
        # 触发统一任务
        task_result = trigger_document_entity_unification(
            document_id=request.document_id,
            extracted_entities=request.entities,
            unification_mode=request.unification_mode
        )
        
        return {
            "success": True,
            "message": f"已触发文档 {request.document_id} 的实体统一任务",
            "data": task_result
        }
        
    except Exception as e:
        logger.error(f"触发文档实体统一失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"触发任务失败: {str(e)}")


@router.post("/configure")
async def configure_global_unification(request: GlobalUnificationConfigRequest):
    """配置全局统一参数"""
    try:
        # 创建新配置
        config = GlobalUnificationConfig(
            max_sample_entities_per_type=request.max_sample_entities_per_type,
            min_entities_for_unification=request.min_entities_for_unification,
            enable_cross_document_sampling=request.enable_cross_document_sampling,
            llm_confidence_threshold=request.llm_confidence_threshold,
            max_batch_size=request.max_batch_size,
            enable_quality_boost=request.enable_quality_boost
        )
        
        # 更新服务配置
        global_service = get_global_entity_unification_service(config)
        
        return {
            "success": True,
            "message": "全局统一配置已更新",
            "data": {
                "max_sample_entities_per_type": config.max_sample_entities_per_type,
                "min_entities_for_unification": config.min_entities_for_unification,
                "enable_cross_document_sampling": config.enable_cross_document_sampling,
                "llm_confidence_threshold": config.llm_confidence_threshold,
                "max_batch_size": config.max_batch_size,
                "enable_quality_boost": config.enable_quality_boost
            }
        }
        
    except Exception as e:
        logger.error(f"配置全局统一失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"配置更新失败: {str(e)}")


@router.get("/sample-entities/{entity_type}")
async def sample_entities_by_type(
    entity_type: str,
    limit: int = 10,
    exclude_document_id: Optional[int] = None
):
    """按类型采样实体"""
    try:
        # 获取Neo4j采样器
        sampler = get_neo4j_entity_sampler()
        
        # 执行采样
        exclude_docs = [exclude_document_id] if exclude_document_id else None
        sampled_entities = await sampler.sample_entities_by_type(
            entity_type=entity_type,
            limit=limit,
            exclude_document_ids=exclude_docs
        )
        
        return {
            "success": True,
            "data": {
                "entity_type": entity_type,
                "limit": limit,
                "exclude_document_id": exclude_document_id,
                "sampled_count": len(sampled_entities),
                "entities": sampled_entities
            }
        }
        
    except Exception as e:
        logger.error(f"采样 {entity_type} 类型实体失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"实体采样失败: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 测试各个服务组件
        checks = {}
        
        # 测试Neo4j采样器
        try:
            sampler = get_neo4j_entity_sampler()
            type_stats = await sampler.get_entity_types_with_counts()
            checks["neo4j_sampler"] = {
                "status": "healthy",
                "entity_types_found": len(type_stats)
            }
        except Exception as e:
            checks["neo4j_sampler"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # 测试全局统一服务
        try:
            global_service = get_global_entity_unification_service()
            stats = await global_service.get_unification_statistics()
            checks["global_unification_service"] = {
                "status": "healthy",
                "entity_statistics": stats.get("entity_statistics", {})
            }
        except Exception as e:
            checks["global_unification_service"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # 判断整体健康状态
        all_healthy = all(check["status"] == "healthy" for check in checks.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "checks": checks
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }