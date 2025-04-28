from fastapi import WebSocket
from typing import Dict, List
import asyncio
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        """初始化连接管理器"""
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, task_id: str):
        """
        建立WebSocket连接
        
        参数:
            websocket: WebSocket对象
            task_id: 任务ID
        """
        await websocket.accept()
        async with self.lock:
            if task_id not in self.active_connections:
                self.active_connections[task_id] = []
            self.active_connections[task_id].append(websocket)
            logger.info(f"任务 {task_id} 建立了一个新的WebSocket连接，当前连接数: {len(self.active_connections[task_id])}")

    def disconnect(self, websocket: WebSocket, task_id: str):
        """
        断开WebSocket连接
        
        参数:
            websocket: WebSocket对象
            task_id: 任务ID
        """
        if task_id in self.active_connections:
            if websocket in self.active_connections[task_id]:
                self.active_connections[task_id].remove(websocket)
                logger.info(f"任务 {task_id} 断开了一个WebSocket连接，剩余连接数: {len(self.active_connections[task_id])}")
            
            if len(self.active_connections[task_id]) == 0:
                del self.active_connections[task_id]
                logger.info(f"任务 {task_id} 没有活跃连接，已从管理器中移除")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        向单个连接发送消息
        
        参数:
            message: 消息内容(字典)
            websocket: WebSocket对象
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送WebSocket消息失败: {str(e)}")

    async def send_task_update(self, task_id: str, data: dict):
        """
        发送任务更新消息
        
        参数:
            task_id: 任务ID
            data: 更新数据
        """
        message = {
            "event": "task_update",
            "data": data
        }
        await self.send_update(task_id, message)

    async def send_update(self, task_id: str, message: dict):
        """
        向特定任务的所有连接发送更新消息
        
        参数:
            task_id: 任务ID
            message: 消息内容(字典)
        """
        if task_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"发送任务更新失败: {str(e)}")
                    dead_connections.append(connection)
                    
            # 移除死连接
            for dead in dead_connections:
                if dead in self.active_connections[task_id]:
                    self.active_connections[task_id].remove(dead)
                    logger.warning(f"移除了任务 {task_id} 的一个死连接")
                
            # 如果没有连接了，清理字典
            if task_id in self.active_connections and not self.active_connections[task_id]:
                del self.active_connections[task_id]
                logger.info(f"任务 {task_id} 没有有效连接，已从管理器中移除")
        else:
            logger.debug(f"任务 {task_id} 没有活跃的WebSocket连接，消息无法发送")

    def get_connections_count(self, task_id: str = None):
        """
        获取连接数量
        
        参数:
            task_id: 任务ID，如果不提供则返回所有连接数
            
        返回:
            连接数量
        """
        if task_id:
            return len(self.active_connections.get(task_id, []))
        else:
            count = 0
            for connections in self.active_connections.values():
                count += len(connections)
            return count


# 全局WebSocket连接管理器实例
ws_manager = ConnectionManager() 