#!/bin/zsh

# macOS 系统需要设置此环境变量避免fork安全问题
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# 切换到脚本所在目录
cd "$(dirname "$0")" || exit 1
echo "当前工作目录: $(pwd)"

# 使用当前目录（notebook-backend）的虚拟环境
VENV_PATH="./venv"

# 激活虚拟环境
echo "激活虚拟环境..."
source "$VENV_PATH/bin/activate"

# 检查Python版本
PYTHON_VERSION_ACTUAL=$(python --version 2>&1)
echo "使用Python版本: $PYTHON_VERSION_ACTUAL"

# 加载环境变量
if [ -f .env ]; then
  export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

# 设置Python路径
echo "设置PYTHONPATH..."
export PYTHONPATH=$PYTHONPATH:$(pwd)
echo "PYTHONPATH: $PYTHONPATH"

# 启动Celery Worker
echo "启动Celery Worker..."
celery -A app.core.celery_app worker --loglevel=info
