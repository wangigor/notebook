# -*- coding: utf-8 -*-
import sys
import os
import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.task_service import TaskService
from app.models.task import TaskStatus, TaskStepStatus, Task
from tests.utils import get_test_db, create_test_user, create_test_task

@pytest.fixture
def db():
    """数据库会话固定装置"""
    for db in get_test_db():
        yield db

@pytest.fixture
def task_service(db):
    """任务服务固定装置"""
    return TaskService(db)

@pytest.fixture
def test_user(db):
    """测试用户固定装置"""
    return create_test_user(db)

@pytest.fixture
def test_task(db, test_user):
    """测试任务固定装置"""
    return create_test_task(db, test_user.id)

@pytest.mark.asyncio
async def test_update_task_status(task_service, test_task, monkeypatch):
    """测试更新任务状态功能"""
    # 模拟WebSocket发送
    async def mock_send_task_update(*args, **kwargs):
        return None
    
    # 打补丁替换WebSocket发送方法
    monkeypatch.setattr("app.ws.connection_manager.ws_manager.send_task_update", mock_send_task_update)
    
    # 执行更新任务状态
    updated_task = await task_service.update_task_status(
        task_id=test_task.id, 
        status=TaskStatus.RUNNING, 
        progress=50.0,
        step_index=0, 
        step_status=TaskStepStatus.RUNNING, 
        step_metadata={'test_key': 'test_value'}, 
        step_output={'result': '测试输出'}
    )
    
    # 解析steps字段（如果是字符串）
    steps = updated_task.steps
    if isinstance(steps, str):
        steps = json.loads(steps)
    
    # 断言
    assert updated_task is not None
    assert updated_task.status == TaskStatus.RUNNING
    assert updated_task.progress == 50.0
    assert steps[0]['status'] == TaskStepStatus.RUNNING
    assert 'metadata' in steps[0]
    assert steps[0]['metadata']['test_key'] == 'test_value'
    assert 'output' in steps[0]
    assert steps[0]['output']['result'] == '测试输出'

@pytest.mark.asyncio
async def test_get_task_with_details(task_service, test_task):
    """测试获取任务详情功能"""
    # 执行获取任务详情
    task_details = task_service.get_task_with_details(test_task.id)
    
    # 断言
    assert task_details is not None
    assert 'id' in task_details
    assert task_details['id'] == test_task.id
    assert 'status' in task_details
    assert 'steps' in task_details
    assert 'created_by' in task_details 