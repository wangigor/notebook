#!/bin/bash

# Notebook AI 服务状态检查脚本

set -e

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Notebook AI 服务状态检查 ===${NC}"

# 加载端口配置
if [ -f "config/ports.conf" ]; then
    source config/ports.conf
else
    # 默认端口配置
    BACKEND_PORT=8000
    FRONTEND_PORT=3000
fi

# 函数：检查端口状态
check_port_status() {
    local port=$1
    local service_name=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        local pid=$(lsof -ti:$port)
        echo -e "${GREEN}✓ $service_name${NC} - 运行中 (端口: $port, PID: $pid)"
        return 0
    else
        echo -e "${RED}✗ $service_name${NC} - 未运行 (端口: $port)"
        return 1
    fi
}

# 函数：检查HTTP服务响应
check_http_service() {
    local port=$1
    local service_name=$2
    local endpoint=${3:-""}
    
    local url="http://localhost:$port$endpoint"
    
    if curl -s --max-time 5 "$url" >/dev/null 2>&1; then
        echo -e "  ${GREEN}→ HTTP响应正常${NC} ($url)"
        return 0
    else
        echo -e "  ${YELLOW}→ HTTP响应异常${NC} ($url)"
        return 1
    fi
}

# 函数：检查Celery状态
check_celery_status() {
    local celery_pids=$(pgrep -f "celery.*worker" 2>/dev/null || true)
    
    if [ -n "$celery_pids" ]; then
        echo -e "${GREEN}✓ Celery Worker${NC} - 运行中 (PID: $celery_pids)"
        
        # 尝试检查Celery状态（如果可能）
        cd notebook-backend 2>/dev/null || true
        if [ -f "venv/bin/activate" ]; then
            source venv/bin/activate 2>/dev/null || true
            if command -v celery >/dev/null 2>&1; then
                local celery_status=$(celery -A app.core.celery_app status 2>/dev/null || echo "无法获取详细状态")
                echo -e "  ${BLUE}→ Celery状态: $celery_status${NC}"
            fi
        fi
        cd - >/dev/null 2>&1 || true
        return 0
    else
        echo -e "${RED}✗ Celery Worker${NC} - 未运行"
        return 1
    fi
}

# 函数：检查依赖服务
check_dependencies() {
    echo -e "\n${BLUE}=== 依赖服务检查 ===${NC}"
    
    # 检查Redis
    if command -v redis-cli >/dev/null 2>&1; then
        if redis-cli ping >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Redis${NC} - 运行中"
        else
            echo -e "${YELLOW}⚠ Redis${NC} - 无法连接"
        fi
    else
        echo -e "${YELLOW}⚠ Redis${NC} - redis-cli未安装，无法检查"
    fi
    
    # 检查Qdrant
    if [ -n "${QDRANT_HOST:-}" ] && [ -n "${QDRANT_PORT:-}" ]; then
        if curl -s --max-time 5 "http://${QDRANT_HOST}:${QDRANT_PORT}" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Qdrant${NC} - 运行中 (${QDRANT_HOST}:${QDRANT_PORT})"
        else
            echo -e "${YELLOW}⚠ Qdrant${NC} - 无法连接 (${QDRANT_HOST}:${QDRANT_PORT})"
        fi
    else
        echo -e "${YELLOW}⚠ Qdrant${NC} - 配置未找到"
    fi
}

# 函数：显示系统资源使用情况
show_resource_usage() {
    echo -e "\n${BLUE}=== 系统资源使用情况 ===${NC}"
    
    # CPU和内存使用情况
    if command -v top >/dev/null 2>&1; then
        echo -e "${BLUE}CPU和内存使用情况:${NC}"
        top -l 1 -n 0 | grep -E "(CPU usage|PhysMem)" 2>/dev/null || \
        top -bn1 | grep -E "(Cpu|Mem)" | head -2 2>/dev/null || \
        echo "无法获取系统资源信息"
    fi
    
    # 磁盘使用情况
    echo -e "\n${BLUE}磁盘使用情况:${NC}"
    df -h . 2>/dev/null || echo "无法获取磁盘使用信息"
}

# 函数：显示日志文件状态
show_log_status() {
    echo -e "\n${BLUE}=== 日志文件状态 ===${NC}"
    
    if [ -d "logs" ]; then
        for log_file in logs/*.log; do
            if [ -f "$log_file" ]; then
                local size=$(du -h "$log_file" 2>/dev/null | cut -f1)
                local modified=$(stat -c %y "$log_file" 2>/dev/null || stat -f %Sm "$log_file" 2>/dev/null || echo "未知")
                echo -e "${BLUE}$log_file${NC} - 大小: $size, 修改时间: $modified"
            fi
        done
    else
        echo -e "${YELLOW}logs目录不存在${NC}"
    fi
}

# 主要状态检查
echo -e "\n${BLUE}=== 核心服务状态 ===${NC}"

backend_status=0
frontend_status=0
celery_status=0

# 检查后端API
if check_port_status $BACKEND_PORT "后端API"; then
    check_http_service $BACKEND_PORT "后端API" "/docs"
    backend_status=1
fi

# 检查前端服务
if check_port_status $FRONTEND_PORT "前端服务"; then
    check_http_service $FRONTEND_PORT "前端服务"
    frontend_status=1
fi

# 检查Celery Worker
if check_celery_status; then
    celery_status=1
fi

# 检查依赖服务
check_dependencies

# 显示资源使用情况
show_resource_usage

# 显示日志状态
show_log_status

# 总结
echo -e "\n${BLUE}=== 状态总结 ===${NC}"
total_services=3
running_services=$((backend_status + frontend_status + celery_status))

if [ $running_services -eq $total_services ]; then
    echo -e "${GREEN}✓ 所有服务运行正常 ($running_services/$total_services)${NC}"
    echo -e "${BLUE}访问地址:${NC}"
    echo -e "  • 前端应用: ${GREEN}http://localhost:$FRONTEND_PORT${NC}"
    echo -e "  • 后端API: ${GREEN}http://localhost:$BACKEND_PORT${NC}"
    echo -e "  • API文档: ${GREEN}http://localhost:$BACKEND_PORT/docs${NC}"
elif [ $running_services -gt 0 ]; then
    echo -e "${YELLOW}⚠ 部分服务运行中 ($running_services/$total_services)${NC}"
    echo -e "${YELLOW}使用 './start-all.sh' 启动所有服务${NC}"
else
    echo -e "${RED}✗ 所有服务都未运行 ($running_services/$total_services)${NC}"
    echo -e "${YELLOW}使用 './start-all.sh' 启动所有服务${NC}"
fi
