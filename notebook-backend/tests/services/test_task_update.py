# -*- coding: utf-8 -*-
import sys
import os
import asyncio
import pytest

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.task_service import TaskService
from app.models.task import TaskStatus, TaskStepStatus
from tests.utils import get_test_db, create_test_user, create_test_task

@pytest.mark.asyncio
async def test():
    """更新任务状态测试"""
    # 使用测试数据库会话
    db = next(get_test_db())
    try:
        # 创建测试服务
        ts = TaskService(db)
        try:
            # 创建测试用户和任务
            test_user = create_test_user(db)
            test_task = create_test_task(db, test_user.id)
            
            # 更新任务状态
            task = await ts.update_task_status(
                task_id=test_task.id, 
                status=TaskStatus.RUNNING, 
                step_index=0, 
                step_status=TaskStepStatus.RUNNING, 
                step_metadata={'test_key': 'test_value'}, 
                step_output={'result': '测试输出'}
            )
            print("更新成功:", task)
        except Exception as e:
            print('更新错误: {}'.format(e))
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test()) 