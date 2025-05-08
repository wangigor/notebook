# WebSocket连接问题修复指南

## 问题描述

之前WebSocket连接出现404错误(`GET /ws HTTP/1.1 404 Not Found`)的原因是由于循环导入和路由注册问题。

## 修复步骤

1. 修改了WebSocket路由结构：
   - 将直接导入`app`实例改为使用`APIRouter`
   - 修正了API路径和WebSocket路径

2. 修复前端连接代码：
   - 更新了WebSocket URL构建方式
   - 改进了认证机制
   - 添加了详细的错误处理

3. 确保依赖安装：
   ```bash
   # 安装基本依赖
   pip install -r requirements.txt
   
   # 如果不需要PostgreSQL，可以使用以下命令避免psycopg2安装问题
   pip install -r requirements.txt --no-deps
   
   # 然后手动安装其他核心依赖
   pip install fastapi uvicorn python-jose pyjwt
   ```

## 重启服务

请完全重启FastAPI服务器：

```bash
# 停止现有服务
pkill -f uvicorn

# 重新启动服务
cd /项目根目录
uvicorn app.main:app --reload
```

## 测试WebSocket连接

可使用以下方法测试WebSocket连接：

1. 浏览器开发者工具测试：
   ```javascript
   // 打开浏览器控制台，执行
   const ws = new WebSocket('ws://localhost:8000/ws');
   ws.onopen = () => {
     console.log('已连接');
     ws.send(JSON.stringify({task_id: 'test123', token: 'test-token'}));
   };
   ws.onmessage = (e) => console.log('收到消息:', JSON.parse(e.data));
   ws.onerror = (e) => console.error('错误:', e);
   ```

2. 使用前端代码测试：
   ```javascript
   import { createWebSocketConnectionWithHeaders } from './services/websocket';
   
   // 使用预检API方式连接
   async function testConnection() {
     try {
       const socket = await createWebSocketConnectionWithHeaders(
         'test-task-123',
         'Bearer your-token-here',
         {
           onOpen: () => console.log('连接成功'),
           onMessage: (data) => console.log('收到消息:', data),
           onError: (err) => console.error('错误:', err)
         }
       );
       
       // 发送测试消息
       socket.sendMessage({type: 'test', content: 'Hello Server'});
       
       // 10秒后关闭连接
       setTimeout(() => socket.close(), 10000);
     } catch (error) {
       console.error('连接失败:', error);
     }
   }
   
   testConnection();
   ```

## 故障排除

如果问题仍然存在：

1. 检查FastAPI日志，查看路由是否正确注册
2. 检查网络请求，确认WebSocket连接请求是否正确发送
3. 验证认证Token是否有效
4. 确保CORS配置正确 