-- 修改tasks表结构以匹配模型定义

-- 添加name字段
ALTER TABLE tasks ADD COLUMN name VARCHAR(255);

-- 添加description字段
ALTER TABLE tasks ADD COLUMN description TEXT;

-- 将type字段重命名为task_type
ALTER TABLE tasks RENAME COLUMN type TO task_type;

-- 将overall_progress字段重命名为progress并修改类型为float
ALTER TABLE tasks RENAME COLUMN overall_progress TO progress;
ALTER TABLE tasks ALTER COLUMN progress TYPE FLOAT;

-- 添加steps字段
ALTER TABLE tasks ADD COLUMN steps JSONB;

-- 添加task_metadata字段
ALTER TABLE tasks ADD COLUMN task_metadata JSONB;

-- 将非空约束确保与模型一致
UPDATE tasks SET name = '未命名任务' WHERE name IS NULL;
ALTER TABLE tasks ALTER COLUMN name SET NOT NULL;

-- 添加索引提高性能
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_document_id ON tasks(document_id);
CREATE INDEX idx_tasks_created_by ON tasks(created_by); 