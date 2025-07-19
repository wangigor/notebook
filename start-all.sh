#!/bin/bash

# Notebook AI 一键启动脚本
# 按顺序启动后端API、Celery Worker和前端服务

set -e

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 加载端口配置
if [ -f "config/ports.conf" ]; then
    source config/ports.conf
else
    # 默认端口配置
    BACKEND_PORT=8000
    FRONTEND_PORT=3000
fi

echo -e "${GREEN}=== Notebook AI 一键启动脚本 ===${NC}"
echo -e "${BLUE}启动顺序: 后端API -> Celery Worker -> 前端${NC}"

# 检查必要目录
if [ ! -d "notebook-backend" ] || [ ! -d "notebook-frontend" ]; then
    echo -e "${RED}错误: 请在项目根目录运行此脚本${NC}"
    exit 1
fi

# 函数：检查端口是否被占用
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}警告: 端口 $port 已被占用${NC}"
        return 1
    fi
    return 0
}

# 函数：等待服务启动
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=0
    
    echo -e "${BLUE}等待 $service_name 启动 (端口 $port)...${NC}"
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:$port >/dev/null 2>&1; then
            echo -e "${GREEN}✓ $service_name 启动成功${NC}"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
        echo -n "."
    done
    
    echo -e "\n${RED}✗ $service_name 启动超时${NC}"
    return 1
}

# 检查端口占用
echo -e "\n${BLUE}检查端口占用情况...${NC}"
check_port $BACKEND_PORT || echo -e "${YELLOW}后端端口 $BACKEND_PORT 被占用，可能需要手动停止${NC}"
check_port $FRONTEND_PORT || echo -e "${YELLOW}前端端口 $FRONTEND_PORT 被占用，可能需要手动停止${NC}"

# 启动后端API
echo -e "\n${GREEN}=== 启动后端API服务 ===${NC}"
cd notebook-backend

# 检测操作系统并选择合适的启动脚本
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${BLUE}检测到macOS系统，使用优化启动脚本${NC}"
    nohup ./start_macos.sh $BACKEND_PORT > ../logs/backend.log 2>&1 &
else
    nohup ./start.sh $BACKEND_PORT > ../logs/backend.log 2>&1 &
fi

BACKEND_PID=$!
echo "后端API PID: $BACKEND_PID"
cd ..

# 等待后端启动
if ! wait_for_service $BACKEND_PORT "后端API"; then
    echo -e "${RED}后端启动失败，停止启动流程${NC}"
    exit 1
fi

# 启动Celery Worker
echo -e "\n${GREEN}=== 启动Celery Worker ===${NC}"
cd notebook-backend
nohup ./start_celery.sh > ../logs/celery.log 2>&1 &
CELERY_PID=$!
echo "Celery Worker PID: $CELERY_PID"
cd ..

# 等待一下让Celery启动
sleep 3

# 启动前端
echo -e "\n${GREEN}=== 启动前端服务 ===${NC}"
cd notebook-frontend
nohup ./start.sh > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "前端服务 PID: $FRONTEND_PID"
cd ..

# 等待前端启动
if ! wait_for_service $FRONTEND_PORT "前端服务"; then
    echo -e "${YELLOW}前端启动可能需要更多时间，请稍后检查${NC}"
fi

# 保存PID到文件
mkdir -p logs
echo "$BACKEND_PID" > logs/backend.pid
echo "$CELERY_PID" > logs/celery.pid
echo "$FRONTEND_PID" > logs/frontend.pid

echo -e "\n${GREEN}=== 启动完成 ===${NC}"
echo -e "${BLUE}服务访问地址:${NC}"
echo -e "  • 前端应用: ${GREEN}http://localhost:$FRONTEND_PORT${NC}"
echo -e "  • 后端API: ${GREEN}http://localhost:$BACKEND_PORT${NC}"
echo -e "  • API文档: ${GREEN}http://localhost:$BACKEND_PORT/docs${NC}"

echo -e "\n${BLUE}日志文件位置:${NC}"
echo -e "  • 后端日志: logs/backend.log"
echo -e "  • Celery日志: logs/celery.log"
echo -e "  • 前端日志: logs/frontend.log"

echo -e "\n${YELLOW}使用 './stop-all.sh' 停止所有服务${NC}"
echo -e "${YELLOW}使用 './status.sh' 检查服务状态${NC}"
