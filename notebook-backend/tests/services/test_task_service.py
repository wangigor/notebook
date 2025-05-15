# -*- coding: utf-8 -*-
import sys
import os
import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock
import uuid
from datetime import datetime
from app.database import SessionLocal
from app.services.task_service import TaskService
from app.services.task_detail_service import TaskDetailService
from app.models.task import TaskStatus, TaskStepStatus, Task, TaskDetail

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.utils import get_test_db, create_test_user, create_test_task

@pytest.fixture
def db():
    """数据库会话固定装置"""
    for db in get_test_db():
        yield db

@pytest.fixture
def db_session():
    """创建数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def task_service(db_session):
    """创建任务服务实例"""
    return TaskService(db_session)

@pytest.fixture
def test_user(db):
    """测试用户固定装置"""
    return create_test_user(db)

@pytest.fixture
def test_task(db_session, task_service):
    """创建测试任务"""
    task = task_service.create_task(
        name="测试任务",
        task_type="TEST",
        created_by=1
    )
    yield task
    # 清理测试数据
    db_session.query(TaskDetail).filter(TaskDetail.task_id == task.id).delete()
    db_session.delete(task)
    db_session.commit()

@pytest.fixture
def task_detail_service(db_session):
    """创建任务详情服务实例"""
    return TaskDetailService(db_session)

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

def test_update_task_status_based_on_details(db_session, task_service, task_detail_service, test_task):
    """测试根据任务详情更新任务状态"""
    # 创建多个任务详情
    details = []
    for i in range(3):
        detail = task_detail_service.create_task_detail(
            task_id=test_task.id,
            step_name=f"测试步骤{i}",
            step_order=i
        )
        details.append(detail)
    
    # 初始状态，所有步骤都是PENDING
    updated_task = task_service.update_task_status_based_on_details(test_task.id)
    assert updated_task.status == TaskStatus.PENDING
    assert updated_task.progress == 0.0
    
    # 更新第一个步骤为运行中
    task_detail_service.update_task_detail(
        task_detail_id=details[0].id,
        status=TaskStatus.RUNNING,
        progress=50
    )
    
    # 任务状态应该变为运行中
    updated_task = task_service.update_task_status_based_on_details(test_task.id)
    assert updated_task.status == TaskStatus.RUNNING
    assert updated_task.progress > 0.0
    assert updated_task.started_at is not None
    
    # 更新所有步骤为完成状态
    for detail in details:
        task_detail_service.update_task_detail(
            task_detail_id=detail.id,
            status=TaskStatus.COMPLETED,
            progress=100
        )
    
    # 任务状态应该变为已完成
    updated_task = task_service.update_task_status_based_on_details(test_task.id)
    assert updated_task.status == TaskStatus.COMPLETED
    assert updated_task.progress == 100.0
    assert updated_task.completed_at is not None
    
    # 清理测试数据
    for detail in details:
        db_session.delete(detail)
    db_session.commit()

def test_update_task_status_based_on_details_with_failure(db_session, task_service, task_detail_service, test_task):
    """测试当有步骤失败时更新任务状态"""
    # 创建多个任务详情
    details = []
    for i in range(3):
        detail = task_detail_service.create_task_detail(
            task_id=test_task.id,
            step_name=f"测试步骤{i}",
            step_order=i
        )
        details.append(detail)
    
    # 更新第一个步骤为完成
    task_detail_service.update_task_detail(
        task_detail_id=details[0].id,
        status=TaskStatus.COMPLETED,
        progress=100
    )
    
    # 更新第二个步骤为失败
    task_detail_service.update_task_detail(
        task_detail_id=details[1].id,
        status=TaskStatus.FAILED,
        progress=50,
        error_message="测试错误"
    )
    
    # 任务状态应该变为失败
    updated_task = task_service.update_task_status_based_on_details(test_task.id)
    assert updated_task.status == TaskStatus.FAILED
    assert updated_task.error_message is not None
    assert updated_task.completed_at is not None
    
    # 清理测试数据
    for detail in details:
        db_session.delete(detail)
    db_session.commit()

def test_update_task_status_based_on_details_with_mixed_status(db_session, task_service, task_detail_service, test_task):
    """测试当步骤状态混合时更新任务状态"""
    # 创建多个任务详情
    details = []
    for i in range(3):
        detail = task_detail_service.create_task_detail(
            task_id=test_task.id,
            step_name=f"测试步骤{i}",
            step_order=i
        )
        details.append(detail)
    
    # 更新步骤状态为混合状态
    task_detail_service.update_task_detail(
        task_detail_id=details[0].id,
        status=TaskStatus.COMPLETED,
        progress=100
    )
    task_detail_service.update_task_detail(
        task_detail_id=details[1].id,
        status=TaskStatus.RUNNING,
        progress=50
    )
    
    # 任务状态应该为运行中
    updated_task = task_service.update_task_status_based_on_details(test_task.id)
    assert updated_task.status == TaskStatus.RUNNING
    assert updated_task.progress > 0.0
    assert updated_task.started_at is not None
    
    # 清理测试数据
    for detail in details:
        db_session.delete(detail)
    db_session.commit() 