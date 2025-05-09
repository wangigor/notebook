# 文档处理任务流程 - 第一阶段实施说明

本文档说明了文档处理任务流程第一阶段的实施内容和使用方法。

## 实施内容

第一阶段主要实现了以下功能：

1. TaskDetail数据模型及关联关系
2. 任务详情服务（TaskDetailService）
3. 任务状态基于详情更新的功能（TaskService.update_task_status_based_on_details）
4. 相关测试代码

## 数据库迁移

在使用这些功能前，需要执行数据库迁移以创建task_details表：

```bash
# 使用alembic执行迁移
cd notebook-backend
alembic upgrade head
```

如果无法使用alembic，可以手动执行以下SQL语句创建表：

```sql
CREATE TABLE task_details (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(36) REFERENCES tasks(id),
    step_name VARCHAR(50) NOT NULL,
    step_order INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    progress INTEGER NOT NULL,
    details JSONB,
    error_message TEXT,
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE INDEX idx_task_details_task_id ON task_details(task_id);
CREATE INDEX idx_task_details_status ON task_details(status);
```

## 使用示例

### 创建任务和任务详情

```python
from app.services.task_service import TaskService
from app.services.task_detail_service import TaskDetailService
from app.database import get_db

# 获取数据库会话
db = next(get_db())

# 创建任务
task_service = TaskService(db)
task = task_service.create_task(
    name="处理文档",
    task_type="DOCUMENT_PROCESSING",
    created_by=1,
    document_id="doc-123",
    description="处理文档并生成向量"
)

# 创建任务详情服务
task_detail_service = TaskDetailService(db)

# 创建任务详情步骤
step1 = task_detail_service.create_task_detail(
    task_id=task.id,
    step_name="文件验证",
    step_order=1
)

step2 = task_detail_service.create_task_detail(
    task_id=task.id,
    step_name="文本提取",
    step_order=2
)

step3 = task_detail_service.create_task_detail(
    task_id=task.id,
    step_name="文本分块",
    step_order=3
)
```

### 更新任务详情和任务状态

```python
# 更新第一个步骤为运行中
step1 = task_detail_service.update_task_detail(
    task_detail_id=step1.id,
    status="RUNNING",
    progress=30
)

# 更新任务状态
task = task_service.update_task_status_based_on_details(task.id)
print(f"任务状态: {task.status}, 进度: {task.progress}")

# 更新第一个步骤为完成
step1 = task_detail_service.update_task_detail(
    task_detail_id=step1.id,
    status="COMPLETED",
    progress=100,
    details={"processed_items": 120}
)

# 再次更新任务状态
task = task_service.update_task_status_based_on_details(task.id)
print(f"任务状态: {task.status}, 进度: {task.progress}")
```

## 测试

运行单元测试验证功能：

```bash
cd notebook-backend
pytest tests/services/test_task_detail_service.py -v
```

## 下一步工作

第一阶段完成后，可以进入第二阶段的实施：

1. 实现Celery任务处理链
2. 实现WebSocket通知系统
3. 集成到应用框架中 