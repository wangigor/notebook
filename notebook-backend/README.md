# 知识库Agent后端

基于FastAPI和LangGraph构建的知识库Agent系统后端。

## 功能特点

- 基于LangGraph构建的Agent系统
- RESTful API接口
- 可扩展的知识库查询功能

## 安装与运行

### 环境要求

- Python 3.9+
- 安装有pip

### 安装步骤

1. 克隆仓库
2. 创建虚拟环境（可选但推荐）
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate  # Windows
   ```
3. 复制环境变量示例文件并配置
   ```bash
   cp .env.example .env
   # 编辑.env文件，填入你的OpenAI API密钥
   ```
4. 运行启动脚本
   ```bash
   ./start.sh
   ```

### 手动运行

1. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```
2. 启动服务
   ```bash
   uvicorn app.main:app --reload
   ```

## API文档

启动服务后，访问 http://localhost:8000/docs 查看自动生成的API文档。

## 项目结构

```
notebook-backend/
├── app/
│   ├── agents/           # Agent实现
│   ├── models/           # 数据模型
│   ├── routers/          # API路由
│   └── main.py           # 主应用入口
├── requirements.txt      # 依赖列表
├── .env.example          # 环境变量示例
└── start.sh              # 启动脚本
``` 