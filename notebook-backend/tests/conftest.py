# -*- coding: utf-8 -*-
import sys
import os
import pytest

# 确保可以导入app模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from tests.utils import create_test_user, create_test_task

@pytest.fixture(scope="session")
def db_session():
    """会话级别数据库会话固定装置"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def db():
    """函数级别数据库会话固定装置"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def test_user(db):
    """创建测试用户"""
    return create_test_user(db)

@pytest.fixture
def test_task(db, test_user):
    """创建测试任务"""
    return create_test_task(db, test_user.id) 