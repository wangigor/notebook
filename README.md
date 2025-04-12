# 知识库Agent系统

基于LangGraph和FastAPI构建的知识库Agent系统，采用前后端分离架构。

## 项目结构

- `notebook-backend/` - Python后端项目，基于FastAPI和LangGraph
- `notebook-frontend/` - TypeScript前端项目，基于Next.js

## 快速开始

### 后端

1. 进入后端目录
   ```bash
   cd notebook-backend
   ```

2. 创建和激活虚拟环境（推荐）
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate  # Windows
   ```

3. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

4. 配置环境变量
   ```bash
   cp .env.example .env
   # 编辑.env文件，填入OpenAI API密钥
   ```

5. 启动后端服务
   ```bash
   ./start.sh
   # 或
   uvicorn app.main:app --reload
   ```

### 前端

1. 进入前端目录
   ```bash
   cd notebook-frontend
   ```

2. 安装依赖
   ```bash
   npm install
   ```

3. 配置环境变量
   ```bash
   # 创建.env.local文件
   echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api" > .env.local
   ```

4. 启动开发服务器
   ```bash
   npm run dev
   ```

5. 浏览器访问前端应用
   ```
   http://localhost:3000
   ```

## 功能介绍

- 基于LangGraph构建的智能Agent系统
- 支持自然语言问答
- 可扩展的知识库接入
- 美观的用户界面

## 技术栈

- 后端: Python, FastAPI, LangGraph, LangChain
- 前端: TypeScript, Next.js, React, TailwindCSS 