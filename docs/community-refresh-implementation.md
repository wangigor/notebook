# 社区刷新功能实现文档

## 概述

本文档描述了知识图谱社区刷新功能的完整实现，包括后端服务、前端界面和API接口。

## 功能特性

### 核心功能
- **社区检测**：使用GDS Leiden算法检测知识图谱中的社区结构
- **多层级社区**：支持0-2级社区层级结构
- **LLM摘要生成**：为每个社区生成自然语言摘要
- **向量化**：为社区生成嵌入向量用于相似性搜索
- **实时进度**：通过WebSocket提供实时任务进度更新

### 技术栈
- **后端**：FastAPI + SQLAlchemy + Neo4j + Celery
- **前端**：React + TypeScript + Semi Design
- **图算法**：Neo4j GDS Leiden算法
- **向量化**：SentenceTransformers
- **异步任务**：Celery + Redis

## 架构设计

### 后端架构

#### 1. 社区服务 (CommunityService)
**文件路径**: `notebook-backend/app/services/community_service.py`

**核心方法**:
- `clear_communities()` - 清理现有社区数据
- `create_community_graph_projection()` - 创建图投影
- `detect_communities()` - 执行Leiden算法
- `create_community_nodes()` - 创建社区节点
- `calculate_community_properties()` - 计算社区属性
- `generate_community_summaries()` - 生成社区摘要
- `create_community_embeddings()` - 创建嵌入向量
- `create_community_indexes()` - 创建索引

#### 2. Celery任务 (CommunityTasks)
**文件路径**: `notebook-backend/app/tasks/community_tasks.py`

**任务类型**:
- `community_detection_task` - 社区检测异步任务
- `cancel_community_detection_task` - 取消任务

#### 3. API路由
**文件路径**: `notebook-backend/app/routers/agents.py`

**端点**:
- `POST /api/agents/community/refresh` - 触发社区刷新

### 前端架构

#### 1. 文档管理器扩展
**文件路径**: `notebook-frontend/src/components/DocumentManager.tsx`

**新增功能**:
- 社区刷新按钮
- 任务监控对话框
- 实时进度显示

#### 2. API接口
**文件路径**: `notebook-frontend/src/api/api.ts`

**新增方法**:
- `agent.refreshCommunities()` - 调用社区刷新API

## 数据流程

### 1. 用户触发流程
```
用户点击"社区刷新"按钮
    ↓
前端调用 /api/agents/community/refresh
    ↓
后端创建任务记录
    ↓
启动Celery异步任务
    ↓
返回任务ID给前端
    ↓
前端显示任务监控对话框
```

### 2. 任务执行流程
```
Celery任务开始执行
    ↓
阶段1: 数据清理 (clear_communities)
    ↓
阶段2: 图投影 (create_community_graph_projection)
    ↓
阶段3: 社区检测 (detect_communities)
    ↓
阶段4: 节点创建 (create_community_nodes)
    ↓
阶段5: 属性计算 (calculate_community_properties)
    ↓
阶段6: 摘要生成 (generate_community_summaries)
    ↓
阶段7: 向量化 (create_community_embeddings)
    ↓
阶段8: 索引创建 (create_community_indexes)
    ↓
任务完成，更新状态
```

### 3. 实时更新流程
```
任务执行过程中
    ↓
每个步骤完成后更新任务详情
    ↓
通过WebSocket推送更新
    ↓
前端实时显示进度
```

## 配置参数

### 环境变量
```bash
# 社区检测配置
COMMUNITY_MAX_LEVELS=3          # 最大社区层级
COMMUNITY_MIN_SIZE=1            # 最小社区大小
COMMUNITY_MAX_WORKERS=10        # 最大并发工作线程
COMMUNITY_LLM_MODEL=gpt-4o      # LLM模型名称
COMMUNITY_EMBEDDING_MODEL=all-MiniLM-L6-v2  # 嵌入模型
COMMUNITY_BATCH_SIZE=100        # 批处理大小
COMMUNITY_TIMEOUT_MINUTES=30    # 超时时间
```

### Neo4j配置
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j
```

## 安装和部署

### 1. 依赖安装
```bash
# 后端依赖
pip install graphdatascience>=1.8.0 sentence-transformers>=2.2.0

# 前端依赖
npm install
```

### 2. Neo4j GDS插件
确保Neo4j已安装GDS插件：
```cypher
CALL gds.list()
```

### 3. 启动服务
```bash
# 启动后端
cd notebook-backend
python -m uvicorn app.main:app --reload

# 启动Celery
celery -A app.celery_app worker --loglevel=info

# 启动前端
cd notebook-frontend
npm run dev
```

## 使用指南

### 1. 触发社区刷新
1. 打开文档管理页面
2. 点击"社区刷新"按钮
3. 系统会显示任务监控对话框
4. 实时查看任务执行进度

### 2. 监控任务状态
- **PENDING**: 任务等待执行
- **RUNNING**: 任务正在执行
- **COMPLETED**: 任务完成
- **FAILED**: 任务失败
- **CANCELLED**: 任务已取消

### 3. 查看任务详情
每个任务包含8个步骤：
1. 数据清理
2. 图投影
3. 社区检测
4. 节点创建
5. 属性计算
6. 摘要生成
7. 向量化
8. 索引创建

## 性能指标

### 预期性能
- **小图** (<1K节点): 1-2分钟
- **中图** (1K-10K节点): 5-10分钟
- **大图** (>10K节点): 15-30分钟

### 质量指标
- **模块度**: 0.3-0.8
- **社区分布**: 0级~50个、1级~15个、2级~5个社区

## 故障排除

### 常见问题

#### 1. GDS连接失败
**错误**: `Failed to connect to Neo4j GDS`
**解决方案**:
- 检查Neo4j服务是否运行
- 确认GDS插件已安装
- 验证连接参数

#### 2. 内存不足
**错误**: `Insufficient memory for graph projection`
**解决方案**:
- 增加Neo4j内存配置
- 减少批处理大小
- 使用更小的图投影

#### 3. LLM调用失败
**错误**: `LLM API call failed`
**解决方案**:
- 检查OpenAI API密钥
- 确认网络连接
- 验证API配额

### 日志查看
```bash
# 查看后端日志
tail -f notebook-backend/logs/app.log

# 查看Celery日志
tail -f notebook-backend/logs/celery.log
```

## 扩展功能

### 1. 自定义算法参数
可以通过修改`CommunityService`类中的配置参数来自定义算法行为。

### 2. 支持更多LLM模型
可以扩展支持其他LLM提供商，如Claude、Gemini等。

### 3. 社区可视化
可以添加社区结构的可视化功能，帮助用户理解社区分布。

### 4. 增量更新
可以实现增量社区检测，只处理新增的文档和实体。

## 总结

社区刷新功能已成功集成到现有的知识图谱系统中，提供了完整的社区检测和生成能力。通过异步任务处理和实时进度更新，为用户提供了良好的使用体验。

该功能为知识图谱分析提供了强大的社区发现能力，有助于理解文档之间的关联关系和主题分布。 