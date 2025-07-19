#!/bin/bash

# Notebook AI 停止所有服务脚本

set -e

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Notebook AI 停止所有服务 ===${NC}"

# 函数：根据PID停止进程
stop_process_by_pid() {
    local pid_file=$1
    local service_name=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${BLUE}停止 $service_name (PID: $pid)...${NC}"
            kill $pid
            sleep 2
            
            # 如果进程仍在运行，强制杀死
            if ps -p $pid > /dev/null 2>&1; then
                echo -e "${YELLOW}强制停止 $service_name...${NC}"
                kill -9 $pid
            fi
            echo -e "${GREEN}✓ $service_name 已停止${NC}"
        else
            echo -e "${YELLOW}$service_name 进程不存在 (PID: $pid)${NC}"
        fi
        rm -f "$pid_file"
    else
        echo -e "${YELLOW}未找到 $service_name 的PID文件${NC}"
    fi
}

# 函数：根据端口停止进程
stop_process_by_port() {
    local port=$1
    local service_name=$2
    
    local pid=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        echo -e "${BLUE}停止占用端口 $port 的 $service_name (PID: $pid)...${NC}"
        kill $pid 2>/dev/null || true
        sleep 2
        
        # 检查是否还在运行
        local still_running=$(lsof -ti:$port 2>/dev/null)
        if [ -n "$still_running" ]; then
            echo -e "${YELLOW}强制停止端口 $port 上的进程...${NC}"
            kill -9 $still_running 2>/dev/null || true
        fi
        echo -e "${GREEN}✓ 端口 $port 上的 $service_name 已停止${NC}"
    else
        echo -e "${YELLOW}端口 $port 上没有运行的 $service_name${NC}"
    fi
}

# 函数：停止Celery相关进程
stop_celery_processes() {
    echo -e "${BLUE}停止所有Celery进程...${NC}"
    
    # 查找所有celery进程
    local celery_pids=$(pgrep -f "celery.*worker" 2>/dev/null || true)
    
    if [ -n "$celery_pids" ]; then
        echo -e "${BLUE}找到Celery进程: $celery_pids${NC}"
        for pid in $celery_pids; do
            echo -e "${BLUE}停止Celery进程 (PID: $pid)...${NC}"
            kill $pid 2>/dev/null || true
        done
        
        sleep 3
        
        # 检查是否还有celery进程
        local remaining_pids=$(pgrep -f "celery.*worker" 2>/dev/null || true)
        if [ -n "$remaining_pids" ]; then
            echo -e "${YELLOW}强制停止剩余的Celery进程...${NC}"
            for pid in $remaining_pids; do
                kill -9 $pid 2>/dev/null || true
            done
        fi
        echo -e "${GREEN}✓ 所有Celery进程已停止${NC}"
    else
        echo -e "${YELLOW}没有找到运行中的Celery进程${NC}"
    fi
}

# 加载端口配置
if [ -f "config/ports.conf" ]; then
    source config/ports.conf
else
    # 默认端口配置
    BACKEND_PORT=8000
    FRONTEND_PORT=3000
fi

# 停止服务（按相反顺序）

# 1. 停止前端服务
echo -e "\n${GREEN}=== 停止前端服务 ===${NC}"
stop_process_by_pid "logs/frontend.pid" "前端服务"
stop_process_by_port $FRONTEND_PORT "前端服务"

# 2. 停止Celery Worker
echo -e "\n${GREEN}=== 停止Celery Worker ===${NC}"
stop_process_by_pid "logs/celery.pid" "Celery Worker"
stop_celery_processes

# 3. 停止后端API
echo -e "\n${GREEN}=== 停止后端API ===${NC}"
stop_process_by_pid "logs/backend.pid" "后端API"
stop_process_by_port $BACKEND_PORT "后端API"

# 清理PID文件
echo -e "\n${BLUE}清理PID文件...${NC}"
rm -f logs/*.pid

# 检查是否还有相关进程
echo -e "\n${BLUE}检查剩余进程...${NC}"
remaining_processes=$(ps aux | grep -E "(uvicorn|celery|npm.*dev|node.*vite)" | grep -v grep || true)

if [ -n "$remaining_processes" ]; then
    echo -e "${YELLOW}发现可能相关的剩余进程:${NC}"
    echo "$remaining_processes"
    echo -e "${YELLOW}如需要，请手动停止这些进程${NC}"
else
    echo -e "${GREEN}✓ 没有发现相关的剩余进程${NC}"
fi

echo -e "\n${GREEN}=== 所有服务停止完成 ===${NC}"
echo -e "${BLUE}使用 './start-all.sh' 重新启动所有服务${NC}"
