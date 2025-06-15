#!/bin/zsh

# macOS 系统需要设置此环境变量避免fork安全问题
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# 切换到脚本所在目录
cd "$(dirname "$0")" || exit 1
echo "当前工作目录: $(pwd)"

# 使用当前目录（notebook-backend）的虚拟环境
VENV_PATH="./venv"  # 修改为当前目录下的venv
PYTHON_VERSION="3.10.13"  # 指定Python版本
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

# 安装开发依赖（包括watchdog用于热部署）
echo "安装开发依赖..."
pip install celery watchdog

# 设置Python路径
echo "设置PYTHONPATH..."
export PYTHONPATH=$PYTHONPATH:$(pwd)
echo "PYTHONPATH: $PYTHONPATH"

# 创建热部署监控脚本
cat > celery_hotreload.py << 'EOF'
#!/usr/bin/env python3
"""
Celery热部署监控脚本
监控代码变化并自动重启Celery worker
"""
import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CeleryReloadHandler(FileSystemEventHandler):
    def __init__(self, celery_process):
        self.celery_process = celery_process
        self.last_reload = 0
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        # 只监控Python文件
        if not event.src_path.endswith('.py'):
            return
            
        # 避免频繁重启（1秒内的变化只重启一次）
        current_time = time.time()
        if current_time - self.last_reload < 1:
            return
            
        print(f"检测到文件变化: {event.src_path}")
        print("重启Celery worker...")
        
        # 重启Celery进程
        self.restart_celery()
        self.last_reload = current_time
        
    def restart_celery(self):
        # 终止当前进程
        if self.celery_process and self.celery_process.poll() is None:
            self.celery_process.terminate()
            try:
                self.celery_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.celery_process.kill()
                
        # 启动新进程
        self.celery_process = subprocess.Popen([
            'celery', '-A', 'app.core.celery_app', 'worker', '--loglevel=info'
        ])
        print(f"Celery worker已重启，PID: {self.celery_process.pid}")

def main():
    print("启动Celery热部署监控...")
    
    # 启动初始Celery进程
    celery_process = subprocess.Popen([
        'celery', '-A', 'app.core.celery_app', 'worker', '--loglevel=info'
    ])
    print(f"Celery worker已启动，PID: {celery_process.pid}")
    
    # 设置文件监控
    event_handler = CeleryReloadHandler(celery_process)
    observer = Observer()
    
    # 监控app目录
    watch_path = Path('./app')
    if watch_path.exists():
        observer.schedule(event_handler, str(watch_path), recursive=True)
        print(f"监控目录: {watch_path.absolute()}")
    
    observer.start()
    
    try:
        while True:
            time.sleep(1)
            # 检查Celery进程是否还在运行
            if celery_process.poll() is not None:
                print("Celery进程意外退出，重新启动...")
                celery_process = subprocess.Popen([
                    'celery', '-A', 'app.core.celery_app', 'worker', '--loglevel=info'
                ])
                event_handler.celery_process = celery_process
                
    except KeyboardInterrupt:
        print("\n正在停止Celery热部署监控...")
        observer.stop()
        if celery_process and celery_process.poll() is None:
            celery_process.terminate()
            try:
                celery_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                celery_process.kill()
                
    observer.join()
    print("Celery热部署监控已停止")

if __name__ == '__main__':
    main()
EOF

# 启动热部署监控
echo "启动Celery热部署模式..."
python celery_hotreload.py 