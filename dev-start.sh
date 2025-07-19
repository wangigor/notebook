#!/bin/bash

# Notebook AI 开发模式启动脚本
# 在不同终端窗口启动各个服务，便于开发调试

set -e

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Notebook AI 开发模式启动 ===${NC}"

# 检查必要目录
if [ ! -d "notebook-backend" ] || [ ! -d "notebook-frontend" ]; then
    echo -e "${RED}错误: 请在项目根目录运行此脚本${NC}"
    exit 1
fi

# 检测终端类型和操作系统
detect_terminal() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v osascript >/dev/null 2>&1; then
            echo "macos_terminal"
        else
            echo "unknown"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v gnome-terminal >/dev/null 2>&1; then
            echo "gnome_terminal"
        elif command -v konsole >/dev/null 2>&1; then
            echo "konsole"
        elif command -v xterm >/dev/null 2>&1; then
            echo "xterm"
        else
            echo "unknown"
        fi
    else
        echo "unknown"
    fi
}

# 在新终端窗口中启动命令
start_in_new_terminal() {
    local title=$1
    local command=$2
    local terminal_type=$(detect_terminal)
    
    case $terminal_type in
        "macos_terminal")
            osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && echo '=== $title ===' && $command\""
            ;;
        "gnome_terminal")
            gnome-terminal --title="$title" -- bash -c "cd $(pwd) && echo '=== $title ===' && $command; exec bash"
            ;;
        "konsole")
            konsole --title "$title" -e bash -c "cd $(pwd) && echo '=== $title ===' && $command; exec bash"
            ;;
        "xterm")
            xterm -title "$title" -e bash -c "cd $(pwd) && echo '=== $title ===' && $command; exec bash" &
            ;;
        *)
            echo -e "${YELLOW}无法检测终端类型，使用后台模式启动${NC}"
            echo -e "${BLUE}启动 $title...${NC}"
            nohup bash -c "$command" > "logs/${title,,}.log" 2>&1 &
            ;;
    esac
}

# 创建日志目录
mkdir -p logs

echo -e "${BLUE}开发模式将在新的终端窗口中启动各个服务${NC}"
echo -e "${YELLOW}这样可以方便查看各服务的实时日志和进行调试${NC}"

# 启动后端API
echo -e "\n${GREEN}启动后端API服务...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    start_in_new_terminal "后端API" "cd notebook-backend && ./start_macos.sh"
else
    start_in_new_terminal "后端API" "cd notebook-backend && ./start.sh"
fi

# 等待一下
sleep 2

# 启动Celery Worker
echo -e "${GREEN}启动Celery Worker...${NC}"
start_in_new_terminal "Celery Worker" "cd notebook-backend && ./start_celery.sh"

# 等待一下
sleep 2

# 启动前端
echo -e "${GREEN}启动前端服务...${NC}"
start_in_new_terminal "前端服务" "cd notebook-frontend && ./start.sh"

echo -e "\n${GREEN}=== 开发模式启动完成 ===${NC}"
echo -e "${BLUE}各服务已在独立的终端窗口中启动${NC}"

echo -e "\n${BLUE}服务访问地址:${NC}"
echo -e "  • 前端应用: ${GREEN}http://localhost:3000${NC}"
echo -e "  • 后端API: ${GREEN}http://localhost:8000${NC}"
echo -e "  • API文档: ${GREEN}http://localhost:8000/docs${NC}"

echo -e "\n${YELLOW}提示:${NC}"
echo -e "  • 各服务运行在独立的终端窗口中"
echo -e "  • 可以直接在对应终端中查看日志和调试信息"
echo -e "  • 使用 Ctrl+C 在对应终端中停止服务"
echo -e "  • 或使用 './stop-all.sh' 停止所有服务"

# 如果支持，自动打开浏览器
if command -v open >/dev/null 2>&1; then
    echo -e "\n${BLUE}正在打开浏览器...${NC}"
    sleep 5  # 等待前端启动
    open http://localhost:3000
elif command -v xdg-open >/dev/null 2>&1; then
    echo -e "\n${BLUE}正在打开浏览器...${NC}"
    sleep 5  # 等待前端启动
    xdg-open http://localhost:3000
fi
