from fastapi import WebSocket, WebSocketDisconnect, status
from typing import Dict, List
import asyncio
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        """初始化连接管理器"""
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.lock = asyncio.Lock()
        self.max_connections_per_task = settings.WS_MAX_CONNECTIONS_PER_TASK
        self.ping_interval = settings.WS_PING_INTERVAL
        self.ping_timeout = settings.WS_PING_TIMEOUT
        self.ping_tasks = {}  # 保存心跳任务的字典 {task_id_websocket_id: asyncio.Task}

    async def connect(self, websocket: WebSocket, task_id: str):
        """
        建立WebSocket连接
        
        参数:
            websocket: WebSocket对象
            task_id: 任务ID
            
        返回:
            bool: 连接是否成功
        """
        # 检查任务连接数是否超过限制
        if task_id in self.active_connections and len(self.active_connections[task_id]) >= self.max_connections_per_task:
            logger.warning(f"任务 {task_id} 的WebSocket连接数超过限制 ({self.max_connections_per_task})")
            try:
                await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
            except Exception:
                pass
            return False
            
        try:
            await websocket.accept()
            async with self.lock:
                if task_id not in self.active_connections:
                    self.active_connections[task_id] = []
                self.active_connections[task_id].append(websocket)
                connection_count = len(self.active_connections[task_id])
                logger.info(f"任务 {task_id} 建立了一个新的WebSocket连接，当前连接数: {connection_count}")
                
                # 启动心跳任务
                websocket_id = id(websocket)
                ping_task_key = f"{task_id}_{websocket_id}"
                self.ping_tasks[ping_task_key] = asyncio.create_task(
                    self._keep_alive(websocket, task_id, websocket_id)
                )
                
            return True
        except Exception as e:
            logger.error(f"建立WebSocket连接失败: {str(e)}")
            return False

    def disconnect(self, websocket: WebSocket, task_id: str):
        """
        断开WebSocket连接
        
        参数:
            websocket: WebSocket对象
            task_id: 任务ID
        """
        websocket_id = id(websocket)
        ping_task_key = f"{task_id}_{websocket_id}"
        
        # 取消心跳任务
        if ping_task_key in self.ping_tasks:
            self.ping_tasks[ping_task_key].cancel()
            del self.ping_tasks[ping_task_key]
        
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

    async def broadcast_to_task(self, task_id: str, data: dict) -> int:
        """
        广播消息到特定任务的所有WebSocket连接
        
        参数:
            task_id: 任务ID
            data: 要发送的数据
        
        返回:
            int: 成功发送的连接数量
        """
        if task_id not in self.active_connections or not self.active_connections[task_id]:
            return 0
            
        success_count = 0
        dead_connections = []
        
        for connection in self.active_connections[task_id]:
            try:
                await connection.send_json(data)
                success_count += 1
            except Exception as e:
                logger.error(f"广播到连接失败: {str(e)}")
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
            
        return success_count

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
    
    async def _keep_alive(self, websocket: WebSocket, task_id: str, websocket_id: int):
        """
        保持WebSocket连接活跃的心跳机制
        
        参数:
            websocket: WebSocket连接
            task_id: 任务ID
            websocket_id: WebSocket对象的ID
        """
        ping_task_key = f"{task_id}_{websocket_id}"
        try:
            while True:
                try:
                    # 发送ping消息并等待接收pong响应
                    pong_waiter = await websocket.ping()
                    await asyncio.wait_for(pong_waiter, timeout=self.ping_timeout)
                    logger.debug(f"心跳成功: {ping_task_key}")
                except asyncio.TimeoutError:
                    logger.warning(f"WebSocket心跳超时: {ping_task_key}")
                    break
                except WebSocketDisconnect:
                    logger.info(f"WebSocket断开连接: {ping_task_key}")
                    break
                except Exception as e:
                    logger.error(f"WebSocket心跳错误: {ping_task_key}, {str(e)}")
                    break
                
                # 等待下一次心跳
                await asyncio.sleep(self.ping_interval)
                
        except asyncio.CancelledError:
            # 任务被取消，通常是在正常断开连接时
            logger.debug(f"心跳任务已取消: {ping_task_key}")
        except Exception as e:
            logger.error(f"心跳任务异常: {ping_task_key}, {str(e)}")
        finally:
            # 清理连接
            try:
                await websocket.close()
            except Exception:
                pass
            self.disconnect(websocket, task_id)
            if ping_task_key in self.ping_tasks:
                del self.ping_tasks[ping_task_key]


# 全局WebSocket连接管理器实例
ws_manager = ConnectionManager() 