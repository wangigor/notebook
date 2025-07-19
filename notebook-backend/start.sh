#!/bin/bash

# Notebook AI 后端启动脚本 (通用版本)
echo "=== Notebook AI 后端启动脚本 ==="

# macOS 系统需要设置此环境变量避免fork安全问题
if [[ "$OSTYPE" == "darwin"* ]]; then
    export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
fi

# 切换到脚本所在目录
cd "$(dirname "$0")" || exit 1
echo "当前工作目录: $(pwd)"

# 使用当前目录（notebook-backend）的虚拟环境
VENV_PATH="./venv"
PYTHON_VERSION="3.10.13"
PYENV_PYTHON="/Users/wangke/.pyenv/versions/${PYTHON_VERSION}/bin/python"

if [ ! -d "$VENV_PATH" ]; then
    echo "正在创建Python ${PYTHON_VERSION}虚拟环境..."
    
    # 检查pyenv中的Python版本是否存在
    if [ -f "$PYENV_PYTHON" ]; then
        echo "使用pyenv中的Python ${PYTHON_VERSION}创建虚拟环境..."
        "$PYENV_PYTHON" -m venv "$VENV_PATH"
    else
        echo "在pyenv中未找到Python ${PYTHON_VERSION}，尝试使用系统Python..."
        # 尝试使用系统中的Python 3.10
        if command -v python3.10 &> /dev/null; then
            python3.10 -m venv "$VENV_PATH"
        else
            echo "错误: 未找到Python 3.10！请确保安装了Python 3.10"
            exit 1
        fi
    fi
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source "$VENV_PATH/bin/activate"

# 检查Python版本
PYTHON_VERSION_ACTUAL=$(python --version 2>&1)
echo "使用Python版本: $PYTHON_VERSION_ACTUAL"

# 检查requirements.txt文件
if [ ! -f "requirements.txt" ]; then
    echo "错误: 在当前目录中未找到requirements.txt文件!"
    exit 1
fi

# 加载环境变量
if [ -f .env ]; then
  export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

echo "检查环境..."
# 检查网络连接
echo "检查Qdrant服务器连接..."
if curl -s --head --max-time 5 "http://wangigor.ddns.net:30063" > /dev/null 2>&1; then
    echo "Qdrant服务器可访问，使用远程服务器..."
    export QDRANT_URL="http://wangigor.ddns.net:30063"
else
    echo "Qdrant服务器不可访问，使用本地模拟模式..."
    # 没有设置QDRANT_URL，让应用程序进入模拟模式
fi

# 升级pip
echo "升级pip..."
python3.10 -m pip install --upgrade pip

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 安装uvicorn（如果不存在）
echo "确保uvicorn已安装..."
pip install uvicorn

# 启动应用
echo "启动应用..."
# 使用端口8000，与前端默认配置匹配
PORT=${1:-8000}
echo "使用端口: $PORT"
# 增加日志级别以获取更详细的信息
python3.10 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --reload --log-level debug 
