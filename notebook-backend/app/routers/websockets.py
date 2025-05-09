from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status, Request, HTTPException, Body
from app.ws.connection_manager import ws_manager
from app.auth.dependencies import get_user_from_token
from app.services.task_service import TaskService
from app.database import get_db
import logging
import json
from typing import Optional, Dict, Any
from app.core.config import settings
from sqlalchemy.orm import Session

router = APIRouter()
logger = logging.getLogger(__name__)

# 依赖项：获取任务服务
def get_task_service_dep(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db)

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
        
        # 验证用户Token
        user = await get_user_from_token(auth_token, db)
        if not user:
            logger.warning(f"WebSocket连接无效token")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # 接受连接，需要指定使用的子协议
        await websocket.accept(subprotocol=f"Bearer.{auth_token}" if auth_token else None)
            
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
                task = await task_service.get_task_by_id(task_id)
                
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
            connection_success = await ws_manager.connect(websocket, task_id)
            if not connection_success:
                await websocket.send_json({
                    "event": "error", 
                    "message": f"连接数已达上限({settings.WS_MAX_CONNECTIONS_PER_TASK})，请稍后重试"
                })
                return
                
            logger.info(f"用户 {user.id} 成功建立WebSocket连接，任务ID: {task_id}")
            
            # 发送初始任务状态
            try:
                initial_data = await task_service.get_task_with_details(task_id)
                await websocket.send_json({
                    "event": "task_update",
                    "data": initial_data
                })
            except Exception as e:
                logger.error(f"发送初始任务状态失败: {str(e)}")
                await websocket.send_json({
                    "event": "error", 
                    "message": "获取初始任务状态失败，但连接已建立"
                })
            
            # 发送连接确认消息
            await websocket.send_json({
                "event": "connection_established",
                "message": "WebSocket连接已建立",
                "task_id": task_id
            })
            
            # 等待连接关闭
            try:
                while True:
                    message = await websocket.receive_text()
                    try:
                        data = json.loads(message)
                        # 处理客户端消息
                        if data.get("type") == "ping":
                            # 处理客户端主动发送的ping
                            await websocket.send_json({"type": "pong", "timestamp": data.get("timestamp", 0)})
                    except json.JSONDecodeError:
                        logger.warning(f"收到非JSON格式消息: {message[:100]}...")
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
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass

@router.post("/internal/ws/send/{task_id}", status_code=200)
async def send_task_update_to_ws(
    task_id: str,
    data: Dict[str, Any] = Body(...),
    request: Request = None
):
    """
    内部API端点，用于从Celery接收任务更新并转发到WebSocket
    
    安全说明: 该端点仅供内部服务使用，通过API密钥保护
    """
    # 验证内部API密钥
    api_key = request.headers.get("X-API-Key")
    expected_key = settings.INTERNAL_API_KEY
    
    if not api_key:
        logger.warning(f"未授权的内部API访问尝试 (缺少API密钥)，任务ID: {task_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="未授权访问"
        )
    
    # 为调试添加更详细的日志，但不记录完整密钥
    # 只记录前几个字符，用于匹配问题排查
    if api_key != expected_key:
        received_prefix = api_key[:4] + "***" if api_key else "空"
        expected_prefix = expected_key[:4] + "***" if expected_key else "空"
        logger.warning(f"API密钥不匹配，接收到: {received_prefix}，预期: {expected_prefix}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="未授权访问"
        )
        
    # 发送更新到所有相关的WebSocket连接
    result = await ws_manager.broadcast_to_task(task_id, data)
    if result:
        logger.info(f"任务 {task_id} 的更新已发送给 {result} 个WebSocket连接")
        return {"success": True, "connections_notified": result}
    else:
        logger.warning(f"任务 {task_id} 没有活跃的WebSocket连接，更新未发送")
        return {"success": True, "connections_notified": 0}

@router.post("/internal/task_update/{task_id}", status_code=200)
async def push_task_update_to_websocket(
    task_id: str,
    task_service: TaskService = Depends(get_task_service_dep),
    request: Request = None
):
    """
    内部API：将任务更新推送到WebSocket
    该接口供Celery任务调用，推送任务状态更新
    """
    # 验证内部API密钥
    api_key = request.headers.get("X-API-Key")
    expected_key = settings.INTERNAL_API_KEY
    
    if not api_key:
        logger.warning(f"未授权的内部API访问尝试 (缺少API密钥)，任务ID: {task_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="未授权访问"
        )
    
    # 为调试添加更详细的日志，但不记录完整密钥
    # 只记录前几个字符，用于匹配问题排查
    if api_key != expected_key:
        received_prefix = api_key[:4] + "***" if api_key else "空"
        expected_prefix = expected_key[:4] + "***" if expected_key else "空"
        logger.warning(f"API密钥不匹配，接收到: {received_prefix}，预期: {expected_prefix}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="未授权访问"
        )
    
    # 获取任务详情
    task_data = await task_service.get_task_with_details(task_id)
    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 广播任务更新
    sent_count = await ws_manager.broadcast_to_task(task_id, {
        "event": "task_update",
        "data": task_data
    })
    
    return {
        "success": True,
        "task_id": task_id,
        "connections_notified": sent_count
    } 