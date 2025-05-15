import uuid
from datetime import datetime
import pytest
from app.database import SessionLocal
from app.services.task_detail_service import TaskDetailService
from app.services.task_service import TaskService
from app.models.task import TaskStatus, TaskDetail

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
def task_detail_service(db_session):
    """创建任务详情服务实例"""
    return TaskDetailService(db_session)

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

def test_create_task_detail(db_session, task_detail_service, test_task):
    """测试创建任务详情"""
    task_detail = task_detail_service.create_task_detail(
        task_id=test_task.id,
        step_name="测试步骤",
        step_order=0
    )
    
    assert task_detail is not None
    assert task_detail.id is not None
    assert task_detail.task_id == test_task.id
    assert task_detail.step_name == "测试步骤"
    assert task_detail.step_order == 0
    assert task_detail.status == TaskStatus.PENDING
    assert task_detail.progress == 0
    
    # 清理测试数据
    db_session.delete(task_detail)
    db_session.commit()

def test_update_task_detail(db_session, task_detail_service, test_task):
    """测试更新任务详情"""
    # 创建任务详情
    task_detail = task_detail_service.create_task_detail(
        task_id=test_task.id,
        step_name="测试步骤",
        step_order=0
    )
    
    # 更新任务详情
    test_details = {"test_key": "test_value"}
    updated_detail = task_detail_service.update_task_detail(
        task_detail_id=task_detail.id,
        status=TaskStatus.RUNNING,
        progress=50,
        details=test_details,
        error_message="测试错误"
    )
    
    assert updated_detail is not None
    assert updated_detail.status == TaskStatus.RUNNING
    assert updated_detail.progress == 50
    assert updated_detail.details == test_details
    assert updated_detail.error_message == "测试错误"
    assert updated_detail.started_at is not None
    
    # 更新为完成状态
    completed_detail = task_detail_service.update_task_detail(
        task_detail_id=task_detail.id,
        status=TaskStatus.COMPLETED,
        progress=100
    )
    
    assert completed_detail.status == TaskStatus.COMPLETED
    assert completed_detail.progress == 100
    assert completed_detail.completed_at is not None
    
    # 清理测试数据
    db_session.delete(task_detail)
    db_session.commit()

def test_get_task_details_by_task_id(db_session, task_detail_service, test_task):
    """测试获取任务的所有详情记录"""
    # 创建多个任务详情
    details = []
    for i in range(3):
        detail = task_detail_service.create_task_detail(
            task_id=test_task.id,
            step_name=f"测试步骤{i}",
            step_order=i
        )
        details.append(detail)
    
    # 获取任务详情
    task_details = task_detail_service.get_task_details_by_task_id(test_task.id)
    
    assert task_details is not None
    assert len(task_details) == 3
    assert task_details[0].step_order == 0
    assert task_details[1].step_order == 1
    assert task_details[2].step_order == 2
    
    # 清理测试数据
    for detail in details:
        db_session.delete(detail)
    db_session.commit()

def test_check_all_task_details_completed(db_session, task_detail_service, test_task):
    """测试检查任务的所有详情是否已完成"""
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
    is_completed = task_detail_service.check_all_task_details_completed(test_task.id)
    assert is_completed is False
    
    # 更新部分步骤为完成状态
    task_detail_service.update_task_detail(
        task_detail_id=details[0].id,
        status=TaskStatus.COMPLETED,
        progress=100
    )
    task_detail_service.update_task_detail(
        task_detail_id=details[1].id,
        status=TaskStatus.COMPLETED,
        progress=100
    )
    
    # 仍有未完成的步骤
    is_completed = task_detail_service.check_all_task_details_completed(test_task.id)
    assert is_completed is False
    
    # 更新所有步骤为完成状态
    task_detail_service.update_task_detail(
        task_detail_id=details[2].id,
        status=TaskStatus.COMPLETED,
        progress=100
    )
    
    # 所有步骤都完成
    is_completed = task_detail_service.check_all_task_details_completed(test_task.id)
    assert is_completed is True
    
    # 清理测试数据
    for detail in details:
        db_session.delete(detail)
    db_session.commit()

def test_update_task_status_based_on_details(db_session):
    """测试根据任务详情更新任务状态"""
    # 这个测试在test_task_service.py中实现
    pass 