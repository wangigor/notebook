#!/bin/bash
# 文件: test_task_api.sh

# 设置变量
API_BASE="http://localhost:8000/api"
TOKEN="替换为有效token"
DOCUMENT_ID="替换为有效文档ID"
TASK_ID="替换为有效任务ID"

# 测试获取文档任务列表
echo "测试获取文档任务列表"
curl -s "${API_BASE}/documents/${DOCUMENT_ID}/tasks" \
  -H "Authorization: Bearer ${TOKEN}" | jq

# 测试获取任务详情
echo "测试获取任务详情"
curl -s "${API_BASE}/tasks/${TASK_ID}" \
  -H "Authorization: Bearer ${TOKEN}" | jq

# 测试更新任务状态
echo "测试更新任务状态"
curl -s -X POST "${API_BASE}/tasks/${TASK_ID}/status" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"progress": 50}' | jq

echo "测试完成" 