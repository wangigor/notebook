#!/bin/bash

# 停止所有正在运行的uvicorn进程
echo "正在停止现有的uvicorn进程..."
pkill -f uvicorn

# 等待进程完全停止
sleep 2

# 检查是否有依赖问题
echo "检查依赖..."
pip install -r requirements.txt

# 如果安装失败但不涉及PostgreSQL，可以跳过依赖
if [ $? -ne 0 ]; then
  echo "依赖安装失败，尝试跳过问题依赖..."
  pip install fastapi uvicorn python-jose pyjwt
fi

# 启动服务器
echo "正在启动FastAPI服务器..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 