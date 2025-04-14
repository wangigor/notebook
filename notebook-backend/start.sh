#!/bin/zsh

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

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 启动应用
echo "启动应用..."
# 使用端口8000，与前端默认配置匹配
PORT=${1:-8000}
echo "使用端口: $PORT"
# 增加日志级别以获取更详细的信息
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --reload --log-level debug 
