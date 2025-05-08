#!/bin/bash

# 脚本用于安装WebSocket所需的依赖

echo "安装WebSocket服务所需的依赖..."

# 确保pip最新
pip install --upgrade pip

# 安装核心依赖
pip install websockets>=10.0 fastapi>=0.95.0 uvicorn[standard]>=0.21.0 python-jose[cryptography]>=3.3.0

# 检查依赖是否安装成功
echo "检查关键依赖安装情况:"
pip show websockets
pip show fastapi
pip show uvicorn

echo "WebSocket依赖安装完成。如果需要完整安装所有依赖，请运行:"
echo "cd notebook-backend && pip install -r requirements.txt"

echo "启动服务器:"
echo "uvicorn app.main:app --reload" 