#!/usr/bin/env python
"""
WebSocket连接测试脚本
用于测试后端WebSocket接口是否正常工作
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
SERVER_URL = "ws://localhost:8000/ws"
TEST_TASK_ID = "test-task-" + datetime.now().strftime("%Y%m%d%H%M%S")
TEST_TOKEN = "test-token"  # 实际环境中应该使用有效的JWT token

async def test_websocket_connection():
    """测试WebSocket连接"""
    try:
        logger.info(f"尝试连接到WebSocket服务器: {SERVER_URL}")
        
        # 连接到WebSocket服务器
        async with websockets.connect(SERVER_URL) as websocket:
            logger.info("WebSocket连接已建立")
            
            # 发送第一条消息，包含任务ID和token
            first_message = {
                "task_id": TEST_TASK_ID,
                "token": TEST_TOKEN
            }
            await websocket.send(json.dumps(first_message))
            logger.info(f"已发送初始消息: {first_message}")
            
            # 接收服务器响应
            response = await websocket.recv()
            response_data = json.loads(response)
            logger.info(f"收到服务器响应: {response_data}")
            
            # 检查连接是否成功
            if response_data.get("status") == "connected":
                logger.info("连接成功确认")
                
                # 发送测试消息
                test_message = {
                    "type": "test_message",
                    "content": "这是一条测试消息",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(test_message))
                logger.info(f"已发送测试消息: {test_message}")
                
                # 接收服务器响应
                response = await websocket.recv()
                response_data = json.loads(response)
                logger.info(f"收到服务器响应: {response_data}")
                
                # 等待5秒后关闭连接
                logger.info("等待5秒...")
                await asyncio.sleep(5)
                
                logger.info("测试完成，关闭连接")
            else:
                logger.error(f"连接未成功确认, 服务器响应: {response_data}")
    
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"WebSocket连接已关闭: {e}")
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")

if __name__ == "__main__":
    logger.info("开始WebSocket连接测试")
    asyncio.run(test_websocket_connection())
    logger.info("WebSocket测试脚本执行完毕") 