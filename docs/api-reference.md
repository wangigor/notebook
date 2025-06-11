# LLM图构建器API接口文档

## 概述

本文档详细描述了LLM图构建器的所有API接口，包括请求参数、响应格式、错误处理等信息。

## 基础信息

- **基础URL**: `http://localhost:8000/api/v1`
- **认证方式**: Bearer Token (JWT)
- **内容类型**: `application/json` 或 `multipart/form-data`
- **API版本**: v1

## 主要API端点

### 1. 数据库连接
**POST** `/connect`

连接并验证Neo4j数据库凭证。

**请求参数**:
```json
{
  "uri": "bolt://localhost:7687",
  "userName": "neo4j", 
  "password": "password",
  "database": "neo4j",
  "email": "user@example.com"
}
```

**响应**:
```json
{
  "status": "Success",
  "data": {
    "db_vector_dimension": 384,
    "message": "Connection Successful",
    "gds_status": true,
    "write_access": true
  }
}
```

### 2. 文件上传
**POST** `/upload`

分块上传文件到系统。支持PDF、Word、图片、文本等格式。

**请求** (multipart/form-data):
- `file`: 文件分块
- `chunkNumber`: 当前分块号
- `totalChunks`: 总分块数
- `originalname`: 原始文件名
- `model`: LLM模型名称
- 数据库凭证字段

**响应**:
```json
{
  "status": "Success", 
  "data": {
    "file_size": 1966610,
    "file_name": "document.pdf",
    "message": "File uploaded successfully"
  }
}
```

### 3. 实体抽取
**POST** `/extract`

从文档中抽取实体和关系，构建知识图谱。

**请求参数**:
```json
{
  "file_name": "document.pdf",
  "model": "openai",
  "allowedNodes": "Person,Organization,Location",
  "allowedRelationship": "Person,WORKS_FOR,Organization",
  "token_chunk_size": 512,
  "chunk_overlap": 50,
  "chunks_to_combine": 1,
  "additional_instructions": "Focus on business relationships"
}
```

**响应**:
```json
{
  "status": "Success",
  "data": {
    "fileName": "document.pdf",
    "nodeCount": 45,
    "relationshipCount": 32,
    "processingTime": "2.45 minutes"
  }
}
```

### 4. 图查询
**POST** `/graph_query`

查询指定文档的图数据用于可视化。

**请求参数**:
```json
{
  "document_names": "[\"document1.pdf\", \"document2.docx\"]"
}
```

**响应**:
```json
{
  "status": "Success",
  "data": {
    "nodes": [{
      "element_id": "4:...:1001",
      "labels": ["Person"],
      "properties": {
        "id": "John Doe",
        "description": "Software Engineer"
      }
    }],
    "relationships": [{
      "start_node_element_id": "4:...:1001",
      "end_node_element_id": "4:...:1002", 
      "type": "WORKS_FOR"
    }]
  }
}
```

### 5. 聊天查询
**POST** `/chatbot`

基于知识图谱回答用户问题。

**请求参数**:
```json
{
  "question": "Who works for Tech Corp?",
  "session_id": "session_123",
  "mode": "vector",
  "document_names": "[\"document.pdf\"]",
  "model": "openai"
}
```

**响应**:
```json
{
  "status": "Success",
  "data": {
    "message": "John Doe and Jane Smith work for Tech Corp.",
    "sources": [{
      "document": "document.pdf",
      "chunk_id": "chunk_001",
      "score": 0.92
    }],
    "response_time": "1.23"
  }
}
```

### 6. 获取文档列表
**POST** `/sources_list`

获取已上传文档的列表和状态。

**响应**:
```json
{
  "status": "Success",
  "data": [{
    "fileName": "document.pdf",
    "fileSize": 1024000,
    "status": "Completed",
    "nodeCount": 45,
    "relationshipCount": 32,
    "model": "openai",
    "createdAt": "2024-01-15T10:30:00Z"
  }]
}
```

### 7. 删除文档
**POST** `/delete_document_and_entities`

删除文档及其相关数据。

**请求参数**:
```json
{
  "filenames": "[\"document.pdf\"]",
  "source_types": "[\"local file\"]",
  "deleteEntities": "true"
}
```

## 错误处理

**错误响应格式**:
```json
{
  "status": "Failed",
  "message": "Error description",
  "error_code": "ERROR_CODE"
}
```

**常见错误码**:
- `AUTH_FAILED`: 认证失败
- `INVALID_PARAMS`: 参数错误
- `FILE_NOT_FOUND`: 文件不存在
- `PROCESSING_TIMEOUT`: 处理超时
- `LLM_API_ERROR`: LLM API错误

## 使用示例

### JavaScript客户端示例
```javascript
class LLMGraphClient {
  constructor(baseURL) {
    this.baseURL = baseURL;
    this.credentials = {};
  }

  async connect(credentials) {
    const response = await fetch(`${this.baseURL}/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials)
    });
    
    const result = await response.json();
    if (result.status === 'Success') {
      this.credentials = credentials;
    }
    return result;
  }

  async uploadFile(file, model) {
    const chunkSize = 1024 * 1024; // 1MB
    const totalChunks = Math.ceil(file.size / chunkSize);
    
    for (let i = 1; i <= totalChunks; i++) {
      const start = (i - 1) * chunkSize;
      const chunk = file.slice(start, start + chunkSize);
      
      const formData = new FormData();
      formData.append('file', chunk);
      formData.append('chunkNumber', i);
      formData.append('totalChunks', totalChunks);
      formData.append('originalname', file.name);
      formData.append('model', model);
      
      Object.entries(this.credentials).forEach(([key, value]) => {
        formData.append(key, value);
      });
      
      const response = await fetch(`${this.baseURL}/upload`, {
        method: 'POST',
        body: formData
      });
      
      if (i === totalChunks) {
        return await response.json();
      }
    }
  }

  async extractEntities(fileName, config) {
    const response = await fetch(`${this.baseURL}/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...this.credentials,
        file_name: fileName,
        ...config
      })
    });
    return await response.json();
  }
}

// 使用示例
const client = new LLMGraphClient('http://localhost:8000/api/v1');

await client.connect({
  uri: 'bolt://localhost:7687',
  userName: 'neo4j',
  password: 'password',
  database: 'neo4j',
  email: 'user@example.com'
});

const file = document.getElementById('fileInput').files[0];
await client.uploadFile(file, 'openai');

await client.extractEntities(file.name, {
  model: 'openai',
  allowedNodes: 'Person,Organization',
  token_chunk_size: 512
});
```

### Python客户端示例
```python
import requests
import json

class LLMGraphClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.credentials = {}
    
    def connect(self, credentials):
        response = requests.post(
            f"{self.base_url}/connect",
            json=credentials
        )
        result = response.json()
        if result["status"] == "Success":
            self.credentials = credentials
        return result
    
    def upload_file(self, file_path, model):
        import os
        
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        chunk_size = 1024 * 1024  # 1MB
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        
        with open(file_path, 'rb') as f:
            for i in range(1, total_chunks + 1):
                chunk = f.read(chunk_size)
                
                files = {'file': (file_name, chunk)}
                data = {
                    'chunkNumber': i,
                    'totalChunks': total_chunks,
                    'originalname': file_name,
                    'model': model,
                    **self.credentials
                }
                
                response = requests.post(
                    f"{self.base_url}/upload",
                    files=files,
                    data=data
                )
                
                if i == total_chunks:
                    return response.json()
    
    def extract_entities(self, file_name, **config):
        response = requests.post(
            f"{self.base_url}/extract",
            json={
                **self.credentials,
                'file_name': file_name,
                **config
            }
        )
        return response.json()

# 使用示例
client = LLMGraphClient('http://localhost:8000/api/v1')

client.connect({
    'uri': 'bolt://localhost:7687',
    'userName': 'neo4j',
    'password': 'password',
    'database': 'neo4j',
    'email': 'user@example.com'
})

client.upload_file('/path/to/document.pdf', 'openai')
result = client.extract_entities(
    'document.pdf',
    model='openai',
    allowedNodes='Person,Organization',
    token_chunk_size=512
)
```

## 最佳实践

1. **文件上传**: 使用分块上传处理大文件，实现断点续传
2. **实体抽取**: 合理设置chunk_size避免token超限
3. **错误处理**: 实现重试机制，特别是LLM API调用
4. **性能优化**: 缓存频繁查询结果，限制并发请求数
5. **安全**: 验证所有输入参数，使用HTTPS传输敏感数据

## 速率限制

| 端点类型 | 限制 | 说明 |
|----------|------|------|
| 文件上传 | 10 requests/minute | 防止服务器过载 |
| LLM处理 | 5 requests/minute | 避免API配额超限 |
| 图查询 | 100 requests/minute | 一般查询操作 |
| 聊天查询 | 20 requests/minute | 防止滥用 |

通过遵循这些API接口规范和最佳实践，开发者可以有效地集成和使用LLM图构建器服务。 