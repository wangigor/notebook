# -*- coding: utf-8 -*-
import sys
import os
import uuid
import random
import json
from datetime import datetime
from typing import Generator, Any, Dict

# 确保可以导入app模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.task import Task

def get_test_db() -> Generator:
    """获取测试数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def setup_test_db():
    """设置测试数据库（可以创建测试表或初始化测试数据）"""
    # 这里可以创建测试用的表，或者使用内存数据库
    # Base.metadata.create_all(bind=engine)
    pass

def teardown_test_db():
    """清理测试数据库"""
    # 这里可以删除测试数据或者删除测试表
    # Base.metadata.drop_all(bind=engine)
    pass

def create_test_user(db) -> User:
    """创建测试用户，使用随机电子邮件避免冲突"""
    random_suffix = uuid.uuid4().hex[:8]
    random_username = f"testuser_{random_suffix}"
    random_email = f"test_{random_suffix}@example.com"
    
    user = User(
        username=random_username,
        email=random_email,
        hashed_password="hashed_pwd",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_test_task(db, user_id: int, document_id: int = None) -> Task:
    """创建测试任务，使用随机ID避免冲突"""
    task_id = f"test-task-{uuid.uuid4().hex[:8]}"
    
    # 创建任务步骤JSON
    steps = [{
        "name": "步骤1",
        "description": "测试步骤",
        "status": "PENDING"
    }]
    
    task = Task(
        id=task_id,
        name="Test Task",
        task_type="TEST",
        status="PENDING",
        progress=0.0,
        created_by=user_id,
        document_id=document_id,
        steps=json.dumps(steps),
        created_at=datetime.utcnow(),
        task_metadata={"test": True}
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task 