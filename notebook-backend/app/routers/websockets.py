from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from app.ws.connection_manager import ws_manager
from app.auth.dependencies import get_user_from_token
from app.services.task_service import TaskService
from app.database import get_db
import logging
import json
from typing import Optional, Dict, Any

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws")
async def websocket_task_endpoint(
    websocket: WebSocket, 
    db = Depends(get_db)
):
    """任务WebSocket连接端点"""
    # 验证用户token
    try:
        # 从WebSocket子协议中提取token
        # 子协议格式：["Bearer.token值"]
        auth_token = None
        if websocket.headers.get("sec-websocket-protocol"):
            protocols = websocket.headers.get("sec-websocket-protocol").split(", ")
            for protocol in protocols:
                if protocol.startswith("Bearer."):
                    auth_token = protocol.replace("Bearer.", "")
                    break
            
        if not auth_token:
            logger.warning(f"WebSocket连接缺少token")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # 接受连接，需要指定使用的子协议
        await websocket.accept(subprotocol=f"Bearer.{auth_token}" if auth_token else None)
            
        user = await get_user_from_token(auth_token, db)
        if not user:
            logger.warning(f"WebSocket连接无效token")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # 等待客户端发送任务ID
        task_id = None
        try:
            # 等待客户端发送任务ID
            init_message = await websocket.receive_text()
            init_data = json.loads(init_message)
            
            if 'task_id' not in init_data:
                logger.warning(f"WebSocket连接未提供任务ID")
                await websocket.send_json({"event": "error", "message": "未提供任务ID"})
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return
                
            task_id = init_data['task_id']
            
            # 验证任务访问权限
            task_service = TaskService(db)
            
            try:
                task = task_service.get_task_by_id(task_id)
                
                if not task or task.created_by != user.id:
                    logger.warning(f"用户 {user.id} 尝试访问无权限的任务 {task_id}")
                    await websocket.send_json({"event": "error", "message": "无权访问该任务"})
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return
            except Exception as e:
                logger.error(f"获取任务信息失败: {str(e)}")
                await websocket.send_json({"event": "error", "message": "获取任务信息失败"})
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                return
            
            # 注册WebSocket连接
            await ws_manager.connect(websocket, task_id)
            logger.info(f"用户 {user.id} 成功建立WebSocket连接，任务ID: {task_id}")
            
            # 发送初始任务状态
            initial_data = task_service.get_task_with_details(task_id)
            await websocket.send_json({
                "event": "task_update",
                "data": initial_data
            })
            
            # 等待连接关闭
            try:
                while True:
                    await websocket.receive_text()  # 持续接收，保持连接
            except WebSocketDisconnect:
                logger.info(f"用户 {user.id} WebSocket连接断开，任务ID: {task_id}")
                ws_manager.disconnect(websocket, task_id)
                
        except WebSocketDisconnect:
            logger.warning(f"WebSocket连接在初始化过程中断开")
            if task_id:
                ws_manager.disconnect(websocket, task_id)
        except json.JSONDecodeError:
            logger.warning(f"WebSocket收到无效JSON数据")
            await websocket.send_json({"event": "error", "message": "无效的JSON数据"})
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            
    except Exception as e:
        logger.error(f"WebSocket连接处理错误: {str(e)}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR) 