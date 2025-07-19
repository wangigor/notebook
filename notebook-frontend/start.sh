#!/bin/bash

# 切换到脚本所在目录
cd "$(dirname "$0")" || exit 1

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Notebook AI 前端启动脚本 ===${NC}"
echo -e "${BLUE}当前工作目录:${NC} $(pwd)"

# 检查是否安装了nodejs
if ! command -v node &> /dev/null; then
    echo -e "${RED}未找到Node.js! 请先安装Node.js (推荐v18或更高版本)${NC}"
    exit 1
fi

# 显示Node.js和npm版本
echo -e "${GREEN}使用的Node.js版本:${NC}"
node -v
echo -e "${GREEN}使用的npm版本:${NC}"
npm -v

# 检查React版本兼容性
NODE_VERSION=$(node -v | cut -d 'v' -f 2 | cut -d '.' -f 1)
if [ "$NODE_VERSION" -lt "18" ]; then
    echo -e "${YELLOW}警告: 当前Node.js版本较旧，可能不完全支持React 19。建议升级到Node.js v18+${NC}"
fi

# 检查package.json是否存在
if [ ! -f "package.json" ]; then
    echo -e "${RED}错误: 在当前目录中未找到package.json文件!${NC}"
    exit 1
fi

# 安装依赖(如果node_modules不存在)
if [ ! -d "node_modules" ]; then
    echo -e "${GREEN}正在安装项目依赖...${NC}"
    npm install
else
    echo -e "${GREEN}依赖已安装${NC}"
fi

# 显示项目信息
echo -e "\n${GREEN}=== 项目信息 ===${NC}"
echo -e "${BLUE}• 前端使用:${NC} Vite + React + TypeScript + Semi Design"
echo -e "${BLUE}• 后端API地址:${NC} http://localhost:8000/api"
echo -e "${BLUE}• 模拟数据模式:${NC} 已开启 (src/api/api.ts中可配置)"
echo -e "${BLUE}• 默认前端端口:${NC} 3000"

# 显示提示信息
echo -e "\n${GREEN}=== 常见问题 ===${NC}"
echo -e "${YELLOW}• 如果遇到 'ref is now a regular prop' 警告，这是React 19正常的API变更警告，不影响功能${NC}"
echo -e "${YELLOW}• 如果API请求失败，将使用模拟数据${NC}"
echo -e "${YELLOW}• 按Ctrl+C可以退出开发服务器${NC}"

# 启动开发服务器
echo -e "\n${GREEN}启动Vite开发服务器...${NC}"
echo -e "${GREEN}应用将运行在:${NC} http://localhost:3000"
npm run dev -- --open 