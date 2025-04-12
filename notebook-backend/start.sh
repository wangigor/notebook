#!/bin/bash

# 检查虚拟环境
if [ ! -d "venv312" ]; then
    echo "正在创建Python 3.12虚拟环境..."
    python3.12 -m venv venv312
fi

# 激活虚拟环境
echo "激活Python 3.12虚拟环境..."
source venv312/bin/activate

# 加载环境变量
if [ -f .env ]; then
  export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 启动应用
echo "启动应用..."
# 确保使用环境变量中的端口
echo "使用端口: ${PORT:-8000}"
python -m uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --reload 
