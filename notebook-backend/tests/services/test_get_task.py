# -*- coding: utf-8 -*-
import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.task_service import TaskService
from tests.utils import get_test_db, create_test_task, create_test_user

def test():
    """获取任务详情测试"""
    # 使用测试数据库会话
    db = next(get_test_db())
    try:
        # 创建测试服务
        ts = TaskService(db)
        try:
            # 创建测试用户和任务
            test_user = create_test_user(db)
            test_task = create_test_task(db, test_user.id)
            
            # 获取任务详情
            task_details = ts.get_task_with_details(test_task.id)
            print("Task details:", json.dumps(task_details, indent=2, ensure_ascii=False))
        except Exception as e:
            print("Error getting task details: {}".format(e))
    finally:
        db.close()

if __name__ == "__main__":
    test() 