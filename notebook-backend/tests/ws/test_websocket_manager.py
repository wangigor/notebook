import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.ws.connection_manager import ConnectionManager

@pytest.fixture
def connection_manager():
    """创建连接管理器实例"""
    return ConnectionManager()

@pytest.mark.asyncio
async def test_connect(connection_manager):
    """测试WebSocket连接"""
    # 创建模拟的WebSocket对象
    mock_websocket = MagicMock()
    mock_websocket.accept = MagicMock(return_value=asyncio.Future())
    mock_websocket.accept.return_value.set_result(None)
    
    # 连接到WebSocket
    task_id = "test-task-id"
    result = await connection_manager.connect(mock_websocket, task_id)
    
    # 验证连接是否成功
    assert result is True
    mock_websocket.accept.assert_called_once()
    assert task_id in connection_manager.active_connections
    assert mock_websocket in connection_manager.active_connections[task_id]
    
    # 清理
    connection_manager.disconnect(mock_websocket, task_id)

@pytest.mark.asyncio
async def test_disconnect(connection_manager):
    """测试WebSocket断开连接"""
    # 创建模拟的WebSocket对象并连接
    mock_websocket = MagicMock()
    mock_websocket.accept = MagicMock(return_value=asyncio.Future())
    mock_websocket.accept.return_value.set_result(None)
    
    task_id = "test-task-id"
    await connection_manager.connect(mock_websocket, task_id)
    
    # 断开连接
    connection_manager.disconnect(mock_websocket, task_id)
    
    # 验证连接是否已断开
    assert task_id not in connection_manager.active_connections

@pytest.mark.asyncio
async def test_send_task_update(connection_manager):
    """测试发送任务更新消息"""
    # 创建模拟的WebSocket对象并连接
    mock_websocket = MagicMock()
    mock_websocket.accept = MagicMock(return_value=asyncio.Future())
    mock_websocket.accept.return_value.set_result(None)
    mock_websocket.send_json = MagicMock(return_value=asyncio.Future())
    mock_websocket.send_json.return_value.set_result(None)
    
    task_id = "test-task-id"
    await connection_manager.connect(mock_websocket, task_id)
    
    # 发送任务更新
    test_data = {"status": "RUNNING", "progress": 50}
    await connection_manager.send_task_update(task_id, test_data)
    
    # 验证消息是否已发送
    mock_websocket.send_json.assert_called_once()
    args, _ = mock_websocket.send_json.call_args
    assert args[0]["event"] == "task_update"
    assert args[0]["data"] == test_data
    
    # 清理
    connection_manager.disconnect(mock_websocket, task_id)

@pytest.mark.asyncio
async def test_send_update(connection_manager):
    """测试发送更新消息"""
    # 创建模拟的WebSocket对象并连接
    mock_websocket = MagicMock()
    mock_websocket.accept = MagicMock(return_value=asyncio.Future())
    mock_websocket.accept.return_value.set_result(None)
    mock_websocket.send_json = MagicMock(return_value=asyncio.Future())
    mock_websocket.send_json.return_value.set_result(None)
    
    task_id = "test-task-id"
    await connection_manager.connect(mock_websocket, task_id)
    
    # 发送更新消息
    test_message = {"event": "custom_event", "data": {"key": "value"}}
    await connection_manager.send_update(task_id, test_message)
    
    # 验证消息是否已发送
    mock_websocket.send_json.assert_called_once_with(test_message)
    
    # 清理
    connection_manager.disconnect(mock_websocket, task_id)

@pytest.mark.asyncio
async def test_broadcast_to_task(connection_manager):
    """测试广播消息到任务的所有连接"""
    # 创建多个模拟的WebSocket对象并连接
    mock_websockets = []
    task_id = "test-task-id"
    
    for i in range(3):
        mock_ws = MagicMock()
        mock_ws.accept = MagicMock(return_value=asyncio.Future())
        mock_ws.accept.return_value.set_result(None)
        mock_ws.send_json = MagicMock(return_value=asyncio.Future())
        mock_ws.send_json.return_value.set_result(None)
        
        await connection_manager.connect(mock_ws, task_id)
        mock_websockets.append(mock_ws)
    
    # 广播消息
    test_data = {"event": "broadcast_test", "data": {"key": "value"}}
    success_count = await connection_manager.broadcast_to_task(task_id, test_data)
    
    # 验证消息是否已广播到所有连接
    assert success_count == 3
    for ws in mock_websockets:
        ws.send_json.assert_called_once_with(test_data)
    
    # 清理
    for ws in mock_websockets:
        connection_manager.disconnect(ws, task_id)

@pytest.mark.asyncio
async def test_send_update_with_task_details(connection_manager):
    """测试发送包含任务详情的更新消息"""
    # 创建模拟的WebSocket对象并连接
    mock_websocket = MagicMock()
    mock_websocket.accept = MagicMock(return_value=asyncio.Future())
    mock_websocket.accept.return_value.set_result(None)
    mock_websocket.send_json = MagicMock(return_value=asyncio.Future())
    mock_websocket.send_json.return_value.set_result(None)
    
    task_id = "test-task-id"
    await connection_manager.connect(mock_websocket, task_id)
    
    # 创建包含任务详情的测试数据
    task_details = [
        {
            "id": 1,
            "step_name": "步骤1",
            "step_order": 0,
            "status": "COMPLETED",
            "progress": 100,
            "details": {"duration_seconds": 1.5},
            "error_message": None,
            "started_at": "2023-01-01T00:00:00",
            "completed_at": "2023-01-01T00:00:01",
            "created_at": "2023-01-01T00:00:00"
        },
        {
            "id": 2,
            "step_name": "步骤2",
            "step_order": 1,
            "status": "RUNNING",
            "progress": 50,
            "details": {},
            "error_message": None,
            "started_at": "2023-01-01T00:00:01",
            "completed_at": None,
            "created_at": "2023-01-01T00:00:00"
        }
    ]
    
    test_data = {
        "id": task_id,
        "status": "RUNNING",
        "progress": 50,
        "task_details": task_details
    }
    
    test_message = {"event": "task_update", "data": test_data}
    await connection_manager.send_update(task_id, test_message)
    
    # 验证消息是否已发送，并且包含任务详情
    mock_websocket.send_json.assert_called_once()
    args, _ = mock_websocket.send_json.call_args
    assert args[0]["event"] == "task_update"
    assert args[0]["data"]["task_details"] == task_details
    
    # 清理
    connection_manager.disconnect(mock_websocket, task_id) 