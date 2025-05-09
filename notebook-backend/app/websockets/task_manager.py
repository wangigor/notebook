import json
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from app.models.task import Task, TaskDetail

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        """添加新的WebSocket连接"""
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
        logger.info(f"新的WebSocket连接: {task_id}, 当前连接数: {len(self.active_connections[task_id])}")
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        """移除WebSocket连接"""
        if task_id in self.active_connections:
            if websocket in self.active_connections[task_id]:
                self.active_connections[task_id].remove(websocket)
            # 如果没有活跃连接，则移除任务ID
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
            logger.info(f"WebSocket连接断开: {task_id}, 剩余连接数: {len(self.active_connections.get(task_id, []))}")
    
    async def broadcast_task_update(self, task_id: str, data: Dict[str, Any]):
        """广播任务更新消息"""
        if task_id in self.active_connections:
            # 序列化数据为JSON字符串
            message = json.dumps(data)
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"发送WebSocket消息失败: {str(e)}")
    
    async def send_personal_message(self, websocket: WebSocket, message: str):
        """发送个人消息"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"发送个人WebSocket消息失败: {str(e)}")


# 创建全局连接管理器实例
connection_manager = ConnectionManager()

# 添加同步版本的WebSocket推送函数
def sync_push_task_update(task_id: str, task_service, task_detail_service=None, max_retries=3):
    """同步版本的任务更新推送函数，用于Celery任务中调用"""
    # 确保事务已提交
    db = task_service.db
    db.commit()  # 确保所有数据库更改已提交
    
    for attempt in range(max_retries):
        try:
            # 获取任务信息 - 从数据库中获取最新状态
            task = task_service.get_task_by_id(task_id)
            if not task:
                logger.error(f"推送任务更新失败: 任务 {task_id} 不存在")
                return False
            
            # 获取任务详情
            task_details = []
            if task_detail_service:
                task_details = task_detail_service.get_task_details_by_task_id(task_id)
            
            # 准备数据
            task_data = {
                "task_id": task.id,
                "status": task.status,
                "progress": task.progress,
                "error_message": task.error_message,
                "updated_at": task.updated_at.isoformat() if hasattr(task, 'updated_at') and task.updated_at else None,
                "task_details": [
                    {
                        "id": detail.id,
                        "step_name": detail.step_name,
                        "step_order": detail.step_order,
                        "status": detail.status,
                        "progress": detail.progress,
                        "error_message": detail.error_message,
                        "started_at": detail.started_at.isoformat() if detail.started_at else None,
                        "completed_at": detail.completed_at.isoformat() if detail.completed_at else None
                    }
                    for detail in task_details
                ] if task_details else []
            }
            
            # 使用异步循环运行WebSocket推送
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(connection_manager.broadcast_task_update(task_id, task_data))
                # 推送成功，跳出重试循环
                return True
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"推送任务更新失败 (尝试 {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                # 添加指数退避策略
                time.sleep(1 * (2 ** attempt))
    
    # 所有重试都失败，记录但不阻止主业务流程
    logger.warning(f"推送任务更新给WebSocket客户端失败，已达最大重试次数: {max_retries}")
    return False

async def task_websocket_endpoint(websocket: WebSocket, task_id: str):
    """任务WebSocket端点"""
    await connection_manager.connect(websocket, task_id)
    try:
        while True:
            # 等待前端消息（虽然在这个应用中前端可能不发送消息）
            data = await websocket.receive_text()
            # 对接收到的消息做处理，通常是控制命令
            await handle_websocket_message(websocket, task_id, data)
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, task_id)


async def handle_websocket_message(websocket: WebSocket, task_id: str, message: str):
    """处理从WebSocket接收到的消息"""
    try:
        data = json.loads(message)
        command = data.get("command")
        
        if command == "ping":
            # 心跳检测
            await connection_manager.send_personal_message(websocket, json.dumps({"command": "pong"}))
        elif command == "cancel":
            # 取消任务
            # TODO: 实现任务取消逻辑
            pass
        else:
            # 未知命令
            await connection_manager.send_personal_message(
                websocket, 
                json.dumps({"error": "Unknown command"})
            )
    except json.JSONDecodeError:
        await connection_manager.send_personal_message(
            websocket, 
            json.dumps({"error": "Invalid JSON format"})
        )
    except Exception as e:
        logger.error(f"处理WebSocket消息时出错: {str(e)}")
        await connection_manager.send_personal_message(
            websocket, 
            json.dumps({"error": f"Internal error: {str(e)}"})
        )


async def push_task_update(task_id: str, task_service, task_detail_service=None):
    """推送任务更新到WebSocket客户端"""
    try:
        # 获取任务信息
        task = task_service.get_task_by_id(task_id)
        if not task:
            logger.error(f"推送任务更新失败: 任务 {task_id} 不存在")
            return
        
        # 获取任务详情
        task_details = []
        if task_detail_service:
            task_details = task_detail_service.get_task_details_by_task_id(task_id)
        
        # 准备数据
        task_data = {
            "task_id": task.id,
            "status": task.status,
            "progress": task.progress,
            "error_message": task.error_message,
            "task_details": [
                {
                    "id": detail.id,
                    "step_name": detail.step_name,
                    "step_order": detail.step_order,
                    "status": detail.status,
                    "progress": detail.progress,
                    "error_message": detail.error_message,
                    "started_at": detail.started_at.isoformat() if detail.started_at else None,
                    "completed_at": detail.completed_at.isoformat() if detail.completed_at else None
                }
                for detail in task_details
            ] if task_details else []
        }
        
        # 广播更新
        await connection_manager.broadcast_task_update(task_id, task_data)
        
    except Exception as e:
        logger.error(f"推送任务更新失败: {str(e)}") 