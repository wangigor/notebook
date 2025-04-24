# 知识库Agent系统 API文档

## 目录

- [认证接口](#认证接口)
- [Agent接口](#agent接口)
- [聊天会话接口](#聊天会话接口)
- [文档管理接口](#文档管理接口)

## 认证接口

### 获取访问令牌

- **URL**: `/api/auth/token`
- **方法**: `POST`
- **说明**: 用户登录并获取访问令牌
- **请求参数**: 
  - `username`: 用户名
  - `password`: 密码
- **响应**: 
  ```json
  {
    "access_token": "string",
    "token_type": "bearer"
  }
  ```

### 注册新用户

- **URL**: `/api/auth/register`
- **方法**: `POST`
- **说明**: 注册新用户账号
- **请求体**: 
  ```json
  {
    "username": "string",
    "email": "string",
    "password": "string",
    "full_name": "string"
  }
  ```
- **响应**: 
  ```json
  {
    "id": "string",
    "username": "string",
    "email": "string",
    "full_name": "string",
    "is_active": true,
    "created_at": "string",
    "updated_at": "string"
  }
  ```

### 获取当前用户信息

- **URL**: `/api/auth/me`
- **方法**: `GET`
- **说明**: 获取当前登录用户的信息
- **请求头**: 需要包含有效的认证Token
- **响应**: 
  ```json
  {
    "id": "string",
    "username": "string",
    "email": "string",
    "full_name": "string",
    "is_active": true,
    "created_at": "string",
    "updated_at": "string"
  }
  ```

## Agent接口

### 查询知识库

- **URL**: `/api/agents/query`
- **方法**: `POST`
- **说明**: 向知识库Agent发送查询
- **请求头**: 需要包含有效的认证Token
- **请求体**: 
  ```json
  {
    "query": "string",
    "session_id": "string",
    "use_retrieval": true,
    "stream": false
  }
  ```
- **响应**: 
  ```json
  {
    "answer": "string",
    "sources": [
      {
        "content": "string",
        "metadata": {
          "key": "value"
        }
      }
    ]
  }
  ```

### 流式查询知识库

- **URL**: `/api/agents/query/stream`
- **方法**: `GET`
- **说明**: 向知识库Agent发送查询，使用流式响应
- **请求头**: 需要包含有效的认证Token
- **请求参数**: 
  - `query`: 查询内容
  - `session_id`: 会话ID（可选）
- **响应**: 
  - 媒体类型: `text/event-stream`
  - 格式: 
    ```
    data: {"type": "chunk", "content": "string"}\n\n
    ```

### 上传文档

- **URL**: `/api/agents/upload-file`
- **方法**: `POST`
- **说明**: 上传文档到知识库
- **请求头**: 需要包含有效的认证Token
- **请求体**: 
  - Content-Type: `multipart/form-data`
  - `file`: 文件数据
  - `metadata`: 文档元数据（JSON字符串，可选）
- **响应**: 
  ```json
  {
    "document_id": "string",
    "name": "string",
    "file_type": "string",
    "success": true,
    "message": "string"
  }
  ```

### 获取Agent配置

- **URL**: `/api/agents/config`
- **方法**: `GET`
- **说明**: 获取知识库Agent的当前配置
- **请求头**: 需要包含有效的认证Token
- **响应**: 
  ```json
  {
    "max_token_limit": 4096,
    "return_messages": true,
    "return_source_documents": true,
    "k": 5,
    "vector_store_url": "string",
    "embedding_model": "string",
    "success": true,
    "message": "string"
  }
  ```

### 更新Agent配置

- **URL**: `/api/agents/config`
- **方法**: `POST`
- **说明**: 更新知识库Agent的配置
- **请求头**: 需要包含有效的认证Token
- **请求体**: 
  ```json
  {
    "max_token_limit": 4096,
    "return_messages": true,
    "return_source_documents": true,
    "k": 5
  }
  ```
- **响应**: 
  ```json
  {
    "max_token_limit": 4096,
    "return_messages": true,
    "return_source_documents": true,
    "k": 5,
    "vector_store_url": "string",
    "embedding_model": "string",
    "success": true,
    "message": "string"
  }
  ```

## 聊天会话接口

### 获取会话列表

- **URL**: `/api/chat/sessions`
- **方法**: `GET`
- **说明**: 获取用户的所有聊天会话
- **请求头**: 需要包含有效的认证Token
- **响应**: 
  ```json
  [
    {
      "id": "string",
      "session_id": "string",
      "title": "string",
      "createdAt": "string",
      "updatedAt": "string"
    }
  ]
  ```

### 创建新会话

- **URL**: `/api/chat/sessions`
- **方法**: `POST`
- **说明**: 创建新的聊天会话
- **请求头**: 需要包含有效的认证Token
- **请求体**: 
  ```json
  {
    "title": "string"
  }
  ```
- **响应**: 
  ```json
  {
    "id": "string",
    "session_id": "string",
    "title": "string",
    "createdAt": "string",
    "updatedAt": "string"
  }
  ```

### 获取会话详情

- **URL**: `/api/chat/sessions/{session_id}`
- **方法**: `GET`
- **说明**: 获取特定会话的详细信息
- **请求头**: 需要包含有效的认证Token
- **路径参数**: 
  - `session_id`: 会话ID
- **响应**: 
  ```json
  {
    "id": "string",
    "session_id": "string",
    "title": "string",
    "createdAt": "string",
    "updatedAt": "string"
  }
  ```

### 更新会话信息

- **URL**: `/api/chat/sessions/{session_id}`
- **方法**: `PUT`
- **说明**: 更新会话信息（如标题）
- **请求头**: 需要包含有效的认证Token
- **路径参数**: 
  - `session_id`: 会话ID
- **请求体**: 
  ```json
  {
    "title": "string"
  }
  ```
- **响应**: 
  ```json
  {
    "id": "string",
    "session_id": "string",
    "title": "string",
    "createdAt": "string",
    "updatedAt": "string"
  }
  ```

### 删除会话

- **URL**: `/api/chat/sessions/{session_id}`
- **方法**: `DELETE`
- **说明**: 删除特定的会话及其所有消息
- **请求头**: 需要包含有效的认证Token
- **路径参数**: 
  - `session_id`: 会话ID
- **响应**: 
  ```json
  {
    "success": true,
    "message": "会话已删除"
  }
  ```

### 获取会话消息

- **URL**: `/api/chat/sessions/{session_id}/messages`
- **方法**: `GET`
- **说明**: 获取特定会话的所有消息
- **请求头**: 需要包含有效的认证Token
- **路径参数**: 
  - `session_id`: 会话ID
- **响应**: 
  ```json
  [
    {
      "id": "string",
      "role": "user",
      "content": "string",
      "timestamp": "string"
    },
    {
      "id": "string",
      "role": "assistant",
      "content": "string",
      "timestamp": "string"
    }
  ]
  ```

### 添加消息到会话

- **URL**: `/api/chat/sessions/{session_id}/messages`
- **方法**: `POST`
- **说明**: 向特定会话添加新消息
- **请求头**: 需要包含有效的认证Token
- **路径参数**: 
  - `session_id`: 会话ID
- **请求体**: 
  ```json
  {
    "role": "user",
    "content": "string"
  }
  ```
- **响应**: 
  ```json
  {
    "id": "string",
    "role": "user",
    "content": "string",
    "timestamp": "string"
  }
  ```

## 文档管理接口

### 获取文档列表

- **URL**: `/api/documents`
- **方法**: `GET`
- **说明**: 获取用户上传的所有文档
- **请求头**: a需要包含有效的认证Token
- **请求参数**: 
  - `skip`: 跳过的文档数量（分页，可选）
  - `limit`: 返回的最大文档数（分页，可选）
  - `search`: 搜索关键词（可选）
  - `file_type`: 文件类型过滤（可选）
- **响应**: 
  ```json
  {
    "documents": [
      {
        "id": 1,
        "document_id": "string",
        "name": "string",
        "file_type": "string",
        "created_at": "string",
        "updated_at": "string",
        "metadata": {
          "key": "value"
        }
      }
    ],
    "total": 10
  }
  ```

### 获取文档详情

- **URL**: `/api/documents/{id}`
- **方法**: `GET`
- **说明**: 获取特定文档的详细信息
- **请求头**: 需要包含有效的认证Token
- **路径参数**: 
  - `id`: 文档ID
- **响应**: 
  ```json
  {
    "id": 1,
    "document_id": "string",
    "name": "string",
    "file_type": "string",
    "created_at": "string",
    "updated_at": "string",
    "content": "string",
    "extracted_text": "string",
    "metadata": {
      "key": "value"
    }
  }
  ```

### 更新文档信息

- **URL**: `/api/documents/{id}`
- **方法**: `PUT`
- **说明**: 更新文档信息（如名称、元数据）
- **请求头**: 需要包含有效的认证Token
- **路径参数**: 
  - `id`: 文档ID
- **请求体**: 
  ```json
  {
    "name": "string",
    "metadata": {
      "key": "value"
    }
  }
  ```
- **响应**: 
  ```json
  {
    "id": 1,
    "document_id": "string",
    "name": "string",
    "file_type": "string",
    "created_at": "string",
    "updated_at": "string",
    "metadata": {
      "key": "value"
    }
  }
  ```

### 删除文档

- **URL**: `/api/documents/{id}`
- **方法**: `DELETE`
- **说明**: 删除特定文档及其在知识库中的向量
- **请求头**: 需要包含有效的认证Token
- **路径参数**: 
  - `id`: 文档ID
- **响应**: 
  ```json
  {
    "success": true,
    "message": "文档已删除"
  }
  ```

### 上传文档

- **URL**: `/api/documents/upload`
- **方法**: `POST`
- **说明**: 上传新文档到知识库（重定向到/api/agents/upload-file）
- **请求头**: 需要包含有效的认证Token
- **请求体**: 
  - Content-Type: `multipart/form-data`
  - `file`: 文件数据
  - `metadata`: 文档元数据（JSON字符串，可选）
- **响应**: 
  ```json
  {
    "document_id": "string",
    "name": "string",
    "file_type": "string",
    "success": true,
    "message": "string"
  }
  ```

## 错误码说明

| 状态码 | 说明                   |
|--------|------------------------|
| 200    | 请求成功               |
| 400    | 请求参数错误           |
| 401    | 未认证或认证失败       |
| 403    | 权限不足               |
| 404    | 资源不存在             |
| 422    | 请求体验证失败         |
| 500    | 服务器内部错误         |

## 认证说明

所有需要认证的API都需要在请求头中包含Bearer令牌：

```
Authorization: Bearer {access_token}
```

令牌可以通过`/api/auth/token`接口获取。

## 分页说明

支持分页的API通常接受以下查询参数：

- `skip`: 跳过的记录数量
- `limit`: 返回的最大记录数量

响应中通常包含：

- 数据列表
- `total`: 总记录数 