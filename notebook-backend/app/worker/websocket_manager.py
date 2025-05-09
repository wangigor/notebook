import logging
import json
import httpx
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    WebSocket管理器
    负责处理WebSocket连接和消息发送
    """
    
    def __init__(self):
        """初始化WebSocket管理器"""
        self.active_connections = {}
        self.api_base_url = settings.API_BASE_URL
        self.internal_api_key = settings.INTERNAL_API_KEY
        logger.info(f"WebSocketManager初始化，API基础URL: {self.api_base_url}")
        # 不记录完整API密钥，但记录前几个字符以帮助调试
        masked_key = self.internal_api_key[:4] + "***" if self.internal_api_key else "未设置"
        logger.info(f"内部API密钥前缀: {masked_key}")
    
    async def connect(self, client_id: str, websocket):
        """
        注册新的WebSocket连接
        
        Args:
            client_id: 客户端ID
            websocket: WebSocket连接对象
        """
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket连接已注册: {client_id}")
    
    def disconnect(self, client_id: str):
        """
        移除WebSocket连接
        
        Args:
            client_id: 客户端ID
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket连接已移除: {client_id}")
    
    async def send_message(self, client_id: str, message: str):
        """
        向特定客户端发送消息
        
        Args:
            client_id: 客户端ID
            message: 要发送的消息
        """
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_text(message)
            logger.info(f"消息已发送到客户端: {client_id}")
        else:
            logger.warning(f"客户端 {client_id} 不存在，无法发送消息")
    
    async def broadcast(self, message: str):
        """
        向所有已连接的客户端广播消息
        
        Args:
            message: 要广播的消息
        """
        for client_id, websocket in self.active_connections.items():
            await websocket.send_text(message)
        logger.info(f"消息已广播给所有客户端，共{len(self.active_connections)}个")
    
    async def send_update(self, task_id: str, data: Dict[str, Any]):
        """
        发送任务更新到WebSocket服务
        
        Args:
            task_id: 任务ID
            data: 要发送的数据
        
        Returns:
            bool: 发送是否成功
        """
        try:
            # 使用内部API将消息发送到WebSocket服务
            ws_update_url = f"{self.api_base_url}/internal/ws/send/{task_id}"
            logger.info(f"准备发送任务更新到: {ws_update_url}")
            
            # 检查API密钥是否已设置
            if not self.internal_api_key:
                logger.error("内部API密钥未设置，无法发送任务更新")
                return False
                
            masked_key = self.internal_api_key[:4] + "***" if self.internal_api_key else "未设置"
            logger.info(f"使用API密钥前缀: {masked_key} 发送请求")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    ws_update_url,
                    json=data,
                    headers={
                        "X-API-Key": self.internal_api_key,
                        "Content-Type": "application/json"
                    },
                    timeout=5.0  # 5秒超时
                )
                
                if response.status_code == 200:
                    logger.info(f"任务更新成功发送到WebSocket服务: task_id={task_id}")
                    return True
                else:
                    logger.error(f"任务更新发送失败: status_code={response.status_code}, response={response.text}")
                    if response.status_code == 403:
                        logger.error("可能是API密钥不匹配，请检查环境变量和配置")
                    return False
                    
        except Exception as e:
            logger.error(f"发送任务更新到WebSocket服务失败: {str(e)}")
            # 如果发送失败，我们记录错误但不影响任务处理流程
            return False

# 创建全局实例
websocket_manager = WebSocketManager() 