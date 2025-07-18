#!/bin/zsh

# macOS 专用 Celery Worker 启动脚本 - 解决 fork 安全问题
echo "🍎 macOS 专用 Celery Worker 启动脚本"

# 设置 macOS fork 安全环境变量
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 设置多进程启动方法为 spawn（避免 fork 问题）
export MULTIPROCESSING_START_METHOD=spawn

# 禁用一些可能导致 fork 问题的功能
export PYTORCH_ENABLE_MPS_FALLBACK=1
export OMP_NUM_THREADS=1

# 设置 Celery 专用环境变量
export CELERY_WORKER=1
export FORKED_BY_MULTIPROCESSING=1

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

# 显式设置SSL相关环境变量（确保被加载）
echo "设置SSL配置..."
export PYTHONHTTPSVERIFY=0
export REQUESTS_CA_BUNDLE=""
export CURL_CA_BUNDLE=""
export SSL_VERIFY=False
echo "SSL验证已禁用"

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

# 安装celery（如果不存在）
echo "确保celery已安装..."
pip install celery

# 设置全局语义统一模式
echo "设置全局语义统一模式..."
export POST_GRAPH_UNIFICATION_MODE="global_semantic"
echo "POST_GRAPH_UNIFICATION_MODE: $POST_GRAPH_UNIFICATION_MODE"

# 启动Celery Worker (macOS 优化模式)
echo "🚀 启动Celery Worker (macOS 优化模式)..."
echo "使用 solo 池模式避免 fork 问题"

# macOS 专用启动参数
celery -A app.core.celery_app worker \
    --loglevel=info \
    --pool=solo \
    --concurrency=1 \
    --prefetch-multiplier=1 \
    --without-gossip \
    --without-mingle \
    --without-heartbeat
