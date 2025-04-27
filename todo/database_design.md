## 一、数据库设计

### 1. Tasks表
```sql
CREATE TABLE tasks (
    id VARCHAR(36) PRIMARY KEY,
    document_id INTEGER, -- Removed: REFERENCES documents(id)
    type VARCHAR(50) NOT NULL, -- 'DOCUMENT_UPLOAD'
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
    overall_progress INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    estimated_completion_time TIMESTAMP,
    created_by INTEGER -- Removed: REFERENCES users(id)
);
```

### 2. Task_Details表
```sql
CREATE TABLE task_details (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(36), -- Removed: REFERENCES tasks(id)
    step_name VARCHAR(50) NOT NULL, -- 'UPLOAD', 'VALIDATE', 'EXTRACT_TEXT', 'PREPROCESS', 'VECTORIZE', 'STORE'
    step_order INTEGER NOT NULL, -- 排序用
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED'
    progress INTEGER DEFAULT 0,
    details JSONB,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 3. Documents表修改
```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    user_id INTEGER, -- Removed: REFERENCES users(id)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    task_id VARCHAR(36), -- Removed: REFERENCES tasks(id)
    processing_status VARCHAR(20) DEFAULT 'PENDING',
    -- MinIO存储相关字段
    bucket_name VARCHAR(100),
    object_key VARCHAR(255),
    content_type VARCHAR(100),
    file_size BIGINT,
    etag VARCHAR(100),
    -- 向量索引相关
    vector_store_id VARCHAR(255),
    vector_collection_name VARCHAR(255), -- 新增：存储用户特定的collection名称
    vector_count INTEGER                 -- 新增：存储向量数量
);

-- 新增：为user_id添加索引，优化按用户筛选的查询
CREATE INDEX idx_documents_user_id ON documents(user_id);
-- 新增：复合索引，优化获取用户已处理文档的查询
CREATE INDEX idx_documents_user_processing ON documents(user_id, processing_status);
```
