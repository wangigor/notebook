#!/bin/bash

# 接受命令行参数
API_URL="${1:-ws://localhost:8000}"
TOKEN="${2}"
TASK_ID="${3}"

if [ -z "$TOKEN" ]; then
  echo "错误: 请提供用户TOKEN"
  echo "用法: $0 [API_URL] TOKEN TASK_ID"
  echo "示例: $0 ws://localhost:8000 eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXV... 123e4567-e89b-12d3-a456-426614174000"
  exit 1
fi

if [ -z "$TASK_ID" ]; then
  echo "错误: 请提供任务ID"
  echo "用法: $0 [API_URL] TOKEN TASK_ID"
  echo "示例: $0 ws://localhost:8000 eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXV... 123e4567-e89b-12d3-a456-426614174000"
  exit 1
fi

# 安装依赖
pip install websockets==11.0.3 > /dev/null

# 设置环境变量
export API_URL="$API_URL"
export TOKEN="$TOKEN"
export TASK_ID="$TASK_ID"

echo "开始测试WebSocket连接..."
echo "API_URL: $API_URL"
echo "TASK_ID: $TASK_ID"

# 运行测试脚本
python tests/test_websocket.py 