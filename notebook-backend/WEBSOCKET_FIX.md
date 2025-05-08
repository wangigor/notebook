# WebSocket 404错误修复方案

## 问题描述

WebSocket连接请求返回404错误（`GET /ws HTTP/1.1 404 Not Found`），表明服务器无法找到WebSocket路由。

## 问题根源分析

经过分析，发现以下几个问题：

1. **循环导入问题**：WebSocket路由文件直接从main.py导入app对象，而main.py又尝试导入WebSocket模块，造成循环导入。

2. **错误的路由注册方式**：未使用FastAPI的APIRouter正确注册路由。

3. **依赖问题**：确保websockets库已正确安装。

## 修复步骤

1. **修改路由结构**：
   - 将`app/api/ws.py`中直接使用app的方式改为使用APIRouter
   - 修正API路径和WebSocket路径

2. **修改依赖**：
   - 确保`websockets`库列在requirements.txt的前面并被正确安装
   - 禁用可能导致安装问题的包（如psycopg2-binary）

3. **修改main.py**：
   - 使用包含_router方式导入WebSocket路由
   - 使用app.include_router()注册路由

## 使用方法

### 1. 安装依赖

在notebook-backend目录下运行：

```bash
# 给安装脚本添加执行权限
chmod +x install_ws_deps.sh

# 运行安装脚本
./install_ws_deps.sh
```

### 2. 重启服务器

完全停止并重启服务器以确保更改生效：

```bash
# 停止所有uvicorn进程
pkill -f uvicorn

# 启动服务器
cd notebook-backend
uvicorn app.main:app --reload
```

### 3. 测试WebSocket连接

使用提供的测试脚本验证WebSocket连接：

```bash
# 给测试脚本添加执行权限
chmod +x test_websocket.py

# 运行测试脚本
./test_websocket.py
```

## 验证方法

成功修复后，访问以下URL应该能看到所有API路由列表，包括WebSocket路由：

```
http://localhost:8000/routes
```

WebSocket路由应该正确显示为`/ws`路径。

## 常见问题

1. **依赖安装失败**：
   - 如安装psycopg2-binary失败，可注释掉该依赖后重新安装其他依赖
   - 使用`pip show websockets`检查websockets是否正确安装

2. **仍然出现404错误**：
   - 检查日志以了解路由注册情况
   - 确认main.py中正确导入并注册了ws_router
   - 确认WebSocket路由正确使用`prefix=""`参数覆盖前缀

3. **认证问题**：
   - 在测试脚本中使用有效的token值
   - 如为测试目的，可临时注释掉ws.py中的token验证逻辑 