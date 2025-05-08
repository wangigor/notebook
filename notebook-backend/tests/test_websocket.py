"""
WebSocket连接测试脚本
"""
import asyncio
import websockets
import json
import logging
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 测试配置
API_URL = os.getenv("API_URL", "ws://localhost:8000")
TOKEN = os.getenv("TOKEN", "your_token_here")  # 替换为有效的用户认证token
TASK_ID = os.getenv("TASK_ID", "your_task_id_here")  # 替换为有效的任务ID

async def test_websocket_connection():
    """测试WebSocket连接"""
    websocket_url = f"{API_URL}/ws/tasks/{TASK_ID}?token={TOKEN}"
    logger.info(f"尝试连接WebSocket: {websocket_url}")
    
    try:
        async with websockets.connect(websocket_url) as websocket:
            logger.info("WebSocket连接成功")
            
            # 接收初始消息
            response = await websocket.recv()
            data = json.loads(response)
            logger.info(f"接收到初始消息: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            # 保持连接一段时间以等待可能的任务更新
            try:
                for _ in range(10):  # 等待最多10条消息或60秒
                    logger.info("等待消息...")
                    response = await asyncio.wait_for(websocket.recv(), timeout=6.0)
                    data = json.loads(response)
                    logger.info(f"接收到消息: {json.dumps(data, ensure_ascii=False, indent=2)}")
            except asyncio.TimeoutError:
                logger.info("等待超时，未收到新消息")
            
            logger.info("测试完成")
    except Exception as e:
        logger.error(f"WebSocket连接测试失败: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        # 检查是否提供了必要的环境变量
        if TOKEN == "your_token_here":
            logger.error("请提供有效的用户TOKEN作为环境变量")
            sys.exit(1)
            
        if TASK_ID == "your_task_id_here":
            logger.error("请提供有效的任务ID作为环境变量")
            sys.exit(1)
            
        logger.info("开始WebSocket连接测试")
        asyncio.run(test_websocket_connection())
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")
        sys.exit(1) 