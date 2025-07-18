# -*- coding: utf-8 -*-
"""
增量实体统一REST API路由
提供手动触发、状态查询、配置管理等功能
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.database import get_db
from app.services.task_service import TaskService
from app.services.sampling_detector import get_sampling_detector, SamplingStrategy
from app.services.incremental_entity_resolver import get_incremental_entity_resolver
from app.worker.entity_unification_tasks import trigger_document_entity_unification
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/entity-unification", tags=["Entity Unification"])


# 请求模型
class ManualUnificationRequest(BaseModel):
    """手动触发实体统一请求"""
    document_id: int = Field(..., description="文档ID")
    entities: List[Dict[str, Any]] = Field(..., description="实体数据列表")
    mode: str = Field(default="incremental", description="统一模式: incremental 或 sampling")
    priority: int = Field(default=1, description="任务优先级")


class SamplingRequest(BaseModel):
    """手动触发抽样请求"""
    entity_type: str = Field(..., description="实体类型")
    sample_size: Optional[int] = Field(None, description="抽样大小")
    strategies: Optional[List[str]] = Field(None, description="抽样策略列表")


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    enable_post_extraction: Optional[bool] = Field(None, description="启用文档解析后统一")
    enable_post_graph: Optional[bool] = Field(None, description="启用图谱构建后统一")
    default_mode: Optional[str] = Field(None, description="默认统一模式")
    post_graph_mode: Optional[str] = Field(None, description="图谱后统一模式")


# 响应模型
class UnificationStatusResponse(BaseModel):
    """统一状态响应"""
    task_id: str
    status: str
    progress: float
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class SamplingStatusResponse(BaseModel):
    """抽样状态响应"""
    task_id: str
    entity_type: str
    status: str
    sample_size: int
    strategies: List[str]
    created_at: datetime
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class SystemStatusResponse(BaseModel):
    """系统状态响应"""
    unification_enabled: bool
    sampling_enabled: bool
    active_tasks: int
    pending_tasks: int
    completed_tasks: int
    failed_tasks: int
    performance_stats: Dict[str, Any]
    configuration: Dict[str, Any]


# API端点
@router.post("/trigger", response_model=Dict[str, Any])
async def trigger_manual_unification(
    request: ManualUnificationRequest,
    db=Depends(get_db)
):
    """手动触发实体统一"""
    try:
        logger.info(f"Manual unification triggered for document {request.document_id}, mode: {request.mode}")
        
        # 验证模式
        if request.mode not in ["incremental", "sampling"]:
            raise HTTPException(status_code=400, detail="Mode must be 'incremental' or 'sampling'")
        
        # 触发统一任务
        result = trigger_document_entity_unification(
            document_id=request.document_id,
            extracted_entities=request.entities,
            unification_mode=request.mode
        )
        
        return {
            "success": True,
            "message": "Entity unification triggered successfully",
            "task_id": result["task_id"],
            "document_id": result["document_id"],
            "entity_count": result["entity_count"],
            "mode": result["mode"],
            "status": result["status"]
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger manual unification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sampling/trigger", response_model=Dict[str, Any])
async def trigger_manual_sampling(request: SamplingRequest):
    """手动触发抽样检测"""
    try:
        detector = get_sampling_detector()
        
        # 转换策略
        strategies = None
        if request.strategies:
            strategies = [SamplingStrategy(s) for s in request.strategies]
        
        # 触发抽样
        task_id = detector.trigger_manual_sampling(
            entity_type=request.entity_type,
            strategies=strategies,
            sample_size=request.sample_size
        )
        
        return {
            "success": True,
            "message": "Sampling triggered successfully",
            "task_id": task_id,
            "entity_type": request.entity_type,
            "sample_size": request.sample_size or detector.default_sample_size,
            "strategies": request.strategies or [s.value for s in detector.default_strategy_weights.keys()]
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger manual sampling: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=UnificationStatusResponse)
async def get_task_status(
    task_id: str = Path(..., description="任务ID"),
    db=Depends(get_db)
):
    """获取统一任务状态"""
    try:
        task_service = TaskService(db)
        
        # 获取任务详情
        task_data = await task_service.get_task_with_details(task_id)
        
        if not task_data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return UnificationStatusResponse(
            task_id=task_data["id"],
            status=task_data["status"],
            progress=task_data.get("progress", 0.0),
            created_at=task_data["created_at"],
            completed_at=task_data.get("completed_at"),
            result=task_data.get("result"),
            error_message=task_data.get("error_message")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sampling/status/{task_id}", response_model=SamplingStatusResponse)
async def get_sampling_status(task_id: str = Path(..., description="抽样任务ID")):
    """获取抽样任务状态"""
    try:
        detector = get_sampling_detector()
        
        # 获取任务状态
        task_data = detector.get_task_status(task_id)
        
        if not task_data:
            raise HTTPException(status_code=404, detail="Sampling task not found")
        
        return SamplingStatusResponse(
            task_id=task_data["task_id"],
            entity_type=task_data["entity_type"],
            status=task_data["status"],
            sample_size=task_data["sample_size"],
            strategies=task_data["strategies"],
            created_at=datetime.fromisoformat(task_data["created_at"]),
            result=task_data.get("result"),
            error_message=task_data.get("error_message")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sampling status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status():
    """获取系统状态"""
    try:
        detector = get_sampling_detector()
        
        # 获取抽样统计信息
        sampling_stats = detector.get_sampling_statistics()
        
        # 获取配置信息
        config = {
            "post_extraction_unification": settings.ENABLE_POST_EXTRACTION_UNIFICATION,
            "post_graph_unification": settings.ENABLE_POST_GRAPH_UNIFICATION,
            "default_unification_mode": settings.DEFAULT_UNIFICATION_MODE,
            "post_graph_unification_mode": settings.POST_GRAPH_UNIFICATION_MODE,
            "sampling_interval_hours": settings.SAMPLING_INTERVAL_HOURS,
            "sampling_size_per_type": settings.SAMPLING_SIZE_PER_TYPE
        }
        
        return SystemStatusResponse(
            unification_enabled=settings.ENABLE_POST_EXTRACTION_UNIFICATION,
            sampling_enabled=sampling_stats["is_running"],
            active_tasks=sampling_stats["active_tasks"],
            pending_tasks=sampling_stats["pending_tasks"],
            completed_tasks=sampling_stats["completed_tasks"],
            failed_tasks=sampling_stats["failed_tasks"],
            performance_stats=sampling_stats["performance_stats"],
            configuration=config
        )
        
    except Exception as e:
        logger.error(f"Failed to get system status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks", response_model=List[UnificationStatusResponse])
async def list_tasks(
    status: Optional[str] = Query(None, description="按状态过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db=Depends(get_db)
):
    """获取任务列表"""
    try:
        task_service = TaskService(db)
        
        # 获取任务列表
        tasks = await task_service.list_tasks(
            status=status,
            limit=limit,
            offset=offset
        )
        
        return [
            UnificationStatusResponse(
                task_id=task["id"],
                status=task["status"],
                progress=task.get("progress", 0.0),
                created_at=task["created_at"],
                completed_at=task.get("completed_at"),
                result=task.get("result"),
                error_message=task.get("error_message")
            )
            for task in tasks
        ]
        
    except Exception as e:
        logger.error(f"Failed to list tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sampling/tasks", response_model=List[SamplingStatusResponse])
async def list_sampling_tasks(
    entity_type: Optional[str] = Query(None, description="按实体类型过滤"),
    status: Optional[str] = Query(None, description="按状态过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制")
):
    """获取抽样任务列表"""
    try:
        detector = get_sampling_detector()
        
        # 获取所有任务
        all_tasks = []
        for task_id, task in detector.sampling_tasks.items():
            if entity_type and task.entity_type != entity_type:
                continue
            if status and task.status.value != status:
                continue
                
            task_data = detector.get_task_status(task_id)
            if task_data:
                all_tasks.append(SamplingStatusResponse(
                    task_id=task_data["task_id"],
                    entity_type=task_data["entity_type"],
                    status=task_data["status"],
                    sample_size=task_data["sample_size"],
                    strategies=task_data["strategies"],
                    created_at=datetime.fromisoformat(task_data["created_at"]),
                    result=task_data.get("result"),
                    error_message=task_data.get("error_message")
                ))
        
        # 按创建时间排序并限制数量
        all_tasks.sort(key=lambda x: x.created_at, reverse=True)
        return all_tasks[:limit]
        
    except Exception as e:
        logger.error(f"Failed to list sampling tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/update", response_model=Dict[str, Any])
async def update_configuration(request: ConfigUpdateRequest):
    """更新配置"""
    try:
        updates = {}
        
        # 更新配置（注意：这里只是示例，实际应用中可能需要持久化配置）
        if request.enable_post_extraction is not None:
            settings.ENABLE_POST_EXTRACTION_UNIFICATION = request.enable_post_extraction
            updates["enable_post_extraction"] = request.enable_post_extraction
            
        if request.enable_post_graph is not None:
            settings.ENABLE_POST_GRAPH_UNIFICATION = request.enable_post_graph
            updates["enable_post_graph"] = request.enable_post_graph
            
        if request.default_mode is not None:
            if request.default_mode not in ["incremental", "sampling"]:
                raise HTTPException(status_code=400, detail="Invalid default mode")
            settings.DEFAULT_UNIFICATION_MODE = request.default_mode
            updates["default_mode"] = request.default_mode
            
        if request.post_graph_mode is not None:
            if request.post_graph_mode not in ["incremental", "sampling"]:
                raise HTTPException(status_code=400, detail="Invalid post graph mode")
            settings.POST_GRAPH_UNIFICATION_MODE = request.post_graph_mode
            updates["post_graph_mode"] = request.post_graph_mode
        
        return {
            "success": True,
            "message": "Configuration updated successfully",
            "updates": updates,
            "current_config": {
                "enable_post_extraction": settings.ENABLE_POST_EXTRACTION_UNIFICATION,
                "enable_post_graph": settings.ENABLE_POST_GRAPH_UNIFICATION,
                "default_mode": settings.DEFAULT_UNIFICATION_MODE,
                "post_graph_mode": settings.POST_GRAPH_UNIFICATION_MODE
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/{task_id}", response_model=Dict[str, Any])
async def cancel_task(
    task_id: str = Path(..., description="任务ID"),
    db=Depends(get_db)
):
    """取消任务"""
    try:
        task_service = TaskService(db)
        
        # 取消任务
        success = await task_service.cancel_task(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
        
        return {
            "success": True,
            "message": "Task cancelled successfully",
            "task_id": task_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sampling/tasks/{task_id}", response_model=Dict[str, Any])
async def cancel_sampling_task(task_id: str = Path(..., description="抽样任务ID")):
    """取消抽样任务"""
    try:
        detector = get_sampling_detector()
        
        # 取消任务
        success = detector.cancel_task(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Sampling task not found or cannot be cancelled")
        
        return {
            "success": True,
            "message": "Sampling task cancelled successfully",
            "task_id": task_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel sampling task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=Dict[str, Any])
async def get_metrics():
    """获取性能指标"""
    try:
        detector = get_sampling_detector()
        
        # 获取统计信息
        stats = detector.get_sampling_statistics()
        
        # 计算额外指标
        performance_stats = stats["performance_stats"]
        
        metrics = {
            "sampling_metrics": {
                "total_samples": performance_stats["total_samples"],
                "total_unified": performance_stats["total_unified"],
                "total_conflicts": performance_stats["total_conflicts"],
                "average_processing_time": performance_stats["average_processing_time"],
                "reduction_rate": (performance_stats["total_samples"] - performance_stats["total_unified"]) / max(1, performance_stats["total_samples"]),
                "conflict_rate": performance_stats["total_conflicts"] / max(1, performance_stats["total_samples"])
            },
            "task_metrics": {
                "active_tasks": stats["active_tasks"],
                "pending_tasks": stats["pending_tasks"],
                "completed_tasks": stats["completed_tasks"],
                "failed_tasks": stats["failed_tasks"],
                "total_tasks": stats["active_tasks"] + stats["pending_tasks"] + stats["completed_tasks"] + stats["failed_tasks"]
            },
            "system_metrics": {
                "is_running": stats["is_running"],
                "sampling_frequency_hours": stats["sampling_frequency"],
                "history_records": stats["total_history_records"]
            },
            "strategy_effectiveness": performance_stats["strategy_effectiveness"]
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))