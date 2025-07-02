# -*- coding: utf-8 -*-
"""
社区检测Celery任务
"""
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
from celery import shared_task
from graphdatascience import GraphDataScience

# 确保使用正确的Celery应用实例
from app.core.celery_app import celery_app
from app.core.config import settings

from app.services.community_service import CommunityService
from app.services.task_service import TaskService
from app.services.task_detail_service import TaskDetailService
from app.websockets.task_manager import sync_push_task_update
from app.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def community_detection_task(self, task_id: str, user_id: int):
    """
    社区检测异步任务
    
    Args:
        task_id: 任务ID
        user_id: 用户ID
    """
    logger.info(f"开始执行社区检测任务: {task_id}")
    
    
    # 获取数据库会话
    db: Session = next(get_db())
    task_service = TaskService(db)
    task_detail_service = TaskDetailService(db)
    
    logger.info(f"数据库会话已创建，开始执行社区检测任务: {task_id}")
    
    try:
        # 更新任务状态为运行中
        task_service.update_task(
            task_id=task_id,
            status="RUNNING",
            progress=0.0,
            started_at=datetime.utcnow()
        )
        
        # 推送任务更新
        sync_push_task_update(task_id, task_service, task_detail_service)
        
        # 初始化GDS连接
        gds = GraphDataScience(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
            database=settings.NEO4J_DATABASE
        )
        
        # 创建社区服务
        community_service = CommunityService(gds)
        
        # 定义任务步骤
        steps = [
            {"name": "数据清理", "description": "清理现有社区数据", "method": "clear_communities"},
            {"name": "图投影", "description": "创建社区检测图投影", "method": "create_community_graph_projection"},
            {"name": "社区检测", "description": "使用Leiden算法检测社区", "method": "detect_communities"},
            {"name": "节点创建", "description": "创建社区节点和层级关系", "method": "create_community_nodes"},
            {"name": "属性计算", "description": "计算社区权重和排名", "method": "calculate_community_properties"},
            {"name": "摘要生成", "description": "使用LLM生成社区摘要", "method": "generate_community_summaries"},
            {"name": "向量化", "description": "生成社区嵌入向量", "method": "create_community_embeddings"},
            {"name": "索引创建", "description": "创建向量和全文索引", "method": "create_community_indexes"}
        ]
        
        total_steps = len(steps)
        completed_steps = 0
        
        # 执行每个步骤
        for i, step in enumerate(steps):
            step_name = step["name"]
            step_description = step["description"]
            method_name = step["method"]
            
            logger.info(f"执行步骤 {i+1}/{total_steps}: {step_name}")
            
            # 创建任务详情记录
            task_detail = task_detail_service.create_task_detail(
                task_id=task_id,
                step_name=step_name,
                step_order=i+1
            )
            
            # 立即更新状态为运行中
            task_detail_service.update_task_detail(
                task_detail_id=task_detail.id,
                status="RUNNING"
            )
            
            # 推送步骤开始更新
            sync_push_task_update(task_id, task_service, task_detail_service)
            
            try:
                # 执行步骤
                method = getattr(community_service, method_name)
                result = method()
                
                # 更新任务详情为完成
                task_detail_service.update_task_detail(
                    task_detail_id=task_detail.id,
                    status="COMPLETED",
                    progress=100,
                    details=result
                )
                
                completed_steps += 1
                progress = (completed_steps / total_steps) * 100
                
                # 更新主任务进度
                task_service.update_task(
                    task_id=task_id,
                    progress=progress
                )
                
                logger.info(f"步骤 {step_name} 完成: {result}")
                
            except Exception as e:
                logger.error(f"步骤 {step_name} 失败: {str(e)}")
                
                # 更新任务详情为失败
                task_detail_service.update_task_detail(
                    task_detail.id,
                    status="FAILED",
                    error_message=str(e)
                )
                
                # 更新主任务状态为失败
                task_service.update_task(
                    task_id=task_id,
                    status="FAILED",
                    error_message=f"步骤 {step_name} 失败: {str(e)}"
                )
                
                # 推送失败更新
                sync_push_task_update(task_id, task_service, task_detail_service)
                raise
            
            # 推送步骤完成更新
            sync_push_task_update(task_id, task_service, task_detail_service)
        
        # 任务完成
        task_service.update_task(
            task_id=task_id,
            status="COMPLETED",
            progress=100.0,
            completed_at=datetime.utcnow()
        )
        
        logger.info(f"社区检测任务完成: {task_id}")
        
        # 推送完成更新
        sync_push_task_update(task_id, task_service, task_detail_service)
        
        return {
            "status": "success",
            "task_id": task_id,
            "message": "社区检测完成"
        }
        
    except Exception as e:
        logger.error(f"社区检测任务失败: {str(e)}")
        
        # 更新任务状态为失败
        try:
            task_service.update_task(
                task_id=task_id,
                status="FAILED",
                error_message=str(e)
            )
            
            # 推送失败更新
            sync_push_task_update(task_id, task_service, task_detail_service)
        except Exception as update_error:
            logger.error(f"更新任务状态失败: {str(update_error)}")
        
        # 重试逻辑
        if self.request.retries < self.max_retries:
            logger.info(f"重试社区检测任务: {task_id}, 重试次数: {self.request.retries + 1}")
            raise self.retry(countdown=60 * (2 ** self.request.retries))  # 指数退避
        else:
            logger.error(f"社区检测任务达到最大重试次数: {task_id}")
            raise
        
    finally:
        # 关闭数据库连接
        try:
            db.close()
            logger.info(f"数据库会话已关闭: {task_id}")
        except Exception as close_error:
            logger.error(f"关闭数据库会话时出错: {str(close_error)}")

@celery_app.task
def cancel_community_detection_task(task_id: str):
    """
    取消社区检测任务
    
    Args:
        task_id: 任务ID
    """
    logger.info(f"取消社区检测任务: {task_id}")
    
    # 获取数据库会话
    db: Session = next(get_db())
    task_service = TaskService(db)
    task_detail_service = TaskDetailService(db)
    
    try:
        # 更新任务状态为已取消
        task_service.update_task(
            task_id=task_id,
            status="CANCELLED"
        )
        
        # 推送取消更新
        sync_push_task_update(task_id, task_service, task_detail_service)
        
        logger.info(f"社区检测任务已取消: {task_id}")
        
    except Exception as e:
        logger.error(f"取消社区检测任务失败: {str(e)}")
        raise
    finally:
        db.close() 