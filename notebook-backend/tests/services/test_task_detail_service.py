import pytest
from datetime import datetime
from app.services.task_detail_service import TaskDetailService
from app.services.task_service import TaskService
from app.models.task import TaskStatus, TaskDetail


def test_create_task_detail(db_session):
    """测试创建任务详情"""
    # 创建一个任务
    task_service = TaskService(db_session)
    task = task_service.create_task(
        name="测试任务",
        task_type="TEST",
        created_by=1
    )
    
    # 创建任务详情服务实例
    task_detail_service = TaskDetailService(db_session)
    
    # 创建任务详情
    task_detail = task_detail_service.create_task_detail(
        task_id=task.id,
        step_name="测试步骤",
        step_order=1
    )
    
    # 断言
    assert task_detail.id is not None
    assert task_detail.task_id == task.id
    assert task_detail.step_name == "测试步骤"
    assert task_detail.step_order == 1
    assert task_detail.status == TaskStatus.PENDING
    assert task_detail.progress == 0


def test_update_task_detail(db_session):
    """测试更新任务详情"""
    # 创建一个任务
    task_service = TaskService(db_session)
    task = task_service.create_task(
        name="测试任务",
        task_type="TEST",
        created_by=1
    )
    
    # 创建任务详情服务实例
    task_detail_service = TaskDetailService(db_session)
    
    # 创建任务详情
    task_detail = task_detail_service.create_task_detail(
        task_id=task.id,
        step_name="测试步骤",
        step_order=1
    )
    
    # 更新任务详情
    updated_detail = task_detail_service.update_task_detail(
        task_detail_id=task_detail.id,
        status=TaskStatus.RUNNING,
        progress=50,
        details={"test_key": "test_value"}
    )
    
    # 断言
    assert updated_detail.status == TaskStatus.RUNNING
    assert updated_detail.progress == 50
    assert updated_detail.details == {"test_key": "test_value"}
    assert updated_detail.started_at is not None


def test_update_task_status_based_on_details(db_session):
    """测试根据任务详情更新任务状态"""
    # 创建一个任务
    task_service = TaskService(db_session)
    task = task_service.create_task(
        name="测试任务",
        task_type="TEST",
        created_by=1
    )
    
    # 创建任务详情服务实例
    task_detail_service = TaskDetailService(db_session)
    
    # 创建三个任务详情步骤
    task_detail1 = task_detail_service.create_task_detail(
        task_id=task.id,
        step_name="步骤1",
        step_order=1
    )
    
    task_detail2 = task_detail_service.create_task_detail(
        task_id=task.id,
        step_name="步骤2",
        step_order=2
    )
    
    task_detail3 = task_detail_service.create_task_detail(
        task_id=task.id,
        step_name="步骤3",
        step_order=3
    )
    
    # 更新步骤1为完成状态
    task_detail_service.update_task_detail(
        task_detail_id=task_detail1.id,
        status=TaskStatus.COMPLETED,
        progress=100
    )
    
    # 更新步骤2为运行中状态
    task_detail_service.update_task_detail(
        task_detail_id=task_detail2.id,
        status=TaskStatus.RUNNING,
        progress=50
    )
    
    # 更新任务状态
    updated_task = task_service.update_task_status_based_on_details(task.id)
    
    # 断言
    assert updated_task.status == TaskStatus.RUNNING
    assert updated_task.progress == 50  # (100 + 50 + 0) / 3
    assert updated_task.started_at is not None
    
    # 更新所有步骤为完成状态
    task_detail_service.update_task_detail(
        task_detail_id=task_detail2.id,
        status=TaskStatus.COMPLETED,
        progress=100
    )
    
    task_detail_service.update_task_detail(
        task_detail_id=task_detail3.id,
        status=TaskStatus.COMPLETED,
        progress=100
    )
    
    # 再次更新任务状态
    updated_task = task_service.update_task_status_based_on_details(task.id)
    
    # 断言
    assert updated_task.status == TaskStatus.COMPLETED
    assert updated_task.progress == 100
    assert updated_task.completed_at is not None 