# Notebook AI - 知识库Agent系统

基于LangGraph和FastAPI构建的智能知识库Agent系统，采用前后端分离架构，支持文档处理、实体提取、图谱构建和智能问答。

## 项目结构

- `notebook-backend/` - Python后端项目，基于FastAPI和LangGraph
- `notebook-frontend/` - TypeScript前端项目，基于Vite + React
- `config/` - 配置文件目录

## 快速开始

### 🚀 一键启动（推荐）

```bash
# 克隆项目后，在项目根目录执行
./start-all.sh
```

这将自动启动：
- 后端API服务 (端口8000)
- Celery任务处理器
- 前端Web应用 (端口3000)

### 🛠️ 开发模式启动

```bash
# 在多个终端窗口中启动服务，便于调试
./dev-start.sh
```

### ⚙️ 手动启动各服务

#### 后端API
```bash
cd notebook-backend
./start.sh          # 通用版本
# 或
./start_macos.sh     # macOS优化版本
```

#### Celery Worker
```bash
cd notebook-backend
./start_celery.sh
```

#### 前端
```bash
cd notebook-frontend
./start.sh
```

### 📊 检查服务状态

```bash
./status.sh          # 检查所有服务状态
```

### 🛑 停止所有服务

```bash
./stop-all.sh
```

### 🔧 环境配置

1. 复制环境变量模板
   ```bash
   cp .env.example .env
   ```

2. 编辑 `.env` 文件，填入必要的API密钥和配置

## 功能介绍

- 基于LangGraph构建的智能Agent系统
- 支持自然语言问答
- 可扩展的知识库接入
- 美观的用户界面

## 技术栈

### 后端
- **框架**: FastAPI, LangGraph, LangChain
- **语言**: Python 3.10+
- **数据库**: SQLite, Neo4j (图数据库)
- **向量数据库**: Qdrant
- **任务队列**: Celery + Redis
- **AI服务**: OpenAI, DashScope (阿里云)

### 前端
- **框架**: Vite + React 18
- **语言**: TypeScript
- **UI库**: Semi Design
- **状态管理**: TanStack Query
- **路由**: React Router

### 基础设施
- **容器化**: Docker (可选)
- **进程管理**: 自定义启动脚本
- **日志**: 结构化日志系统

## 访问地址

启动成功后，可通过以下地址访问：

- **前端应用**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **交互式API**: http://localhost:8000/redoc