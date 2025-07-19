# Notebook AI 快速启动指南

本指南将帮助您快速启动和运行 Notebook AI 系统。

## 系统要求

- **Python**: 3.10+
- **Node.js**: 18+
- **操作系统**: macOS, Linux, Windows
- **内存**: 建议 8GB+
- **磁盘空间**: 至少 2GB

## 依赖服务

### 必需服务
- **Redis**: 用于Celery任务队列 (可选，系统会自动检测)

### 外部服务
- **Qdrant**: 向量数据库 (远程服务器: wangigor.ddns.net:30063)
- **OpenAI API**: AI服务 (需要API密钥)
- **DashScope**: 阿里云AI服务 (可选，需要API密钥)

## 快速启动步骤

### 1. 克隆项目

```bash
git clone <repository-url>
cd notebook-ai
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量文件
nano .env  # 或使用其他编辑器
```

**必需配置项**:
```env
# AI服务API密钥
OPENAI_API_KEY=your_openai_api_key_here
DASHSCOPE_API_KEY=your_dashscope_api_key_here

# 数据库配置 (可选，有默认值)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

### 3. 一键启动

```bash
# 给启动脚本执行权限
chmod +x *.sh
chmod +x notebook-backend/*.sh
chmod +x notebook-frontend/*.sh

# 启动所有服务
./start-all.sh
```

### 4. 验证启动

启动完成后，系统会显示访问地址：

- **前端应用**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

您也可以使用状态检查脚本：

```bash
./status.sh
```

## 启动模式

### 生产模式 (后台运行)
```bash
./start-all.sh
```
- 所有服务在后台运行
- 日志输出到 `logs/` 目录
- 使用 `./stop-all.sh` 停止

### 开发模式 (多终端)
```bash
./dev-start.sh
```
- 每个服务在独立终端窗口运行
- 实时查看日志和调试信息
- 支持热重载

### 手动启动
```bash
# 后端API
cd notebook-backend && ./start.sh

# Celery Worker
cd notebook-backend && ./start_celery.sh

# 前端
cd notebook-frontend && ./start.sh
```

## 常见问题

### 1. 端口被占用
```bash
# 检查端口占用
lsof -i :8000  # 后端
lsof -i :3000  # 前端

# 停止占用进程
./stop-all.sh
```

### 2. Python虚拟环境问题
```bash
# 手动创建虚拟环境
cd notebook-backend
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Node.js依赖问题
```bash
# 清理并重新安装
cd notebook-frontend
rm -rf node_modules package-lock.json
npm install
```

### 4. 服务无法连接外部API
检查网络连接和API密钥配置：
```bash
# 检查Qdrant连接
curl -I http://wangigor.ddns.net:30063

# 检查环境变量
cat .env | grep API_KEY
```

## 日志和调试

### 日志文件位置
- `logs/backend.log` - 后端API日志
- `logs/celery.log` - Celery任务日志
- `logs/frontend.log` - 前端构建日志

### 实时查看日志
```bash
# 查看后端日志
tail -f logs/backend.log

# 查看所有日志
tail -f logs/*.log
```

### 调试模式
在 `.env` 文件中设置：
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

## 停止服务

```bash
# 停止所有服务
./stop-all.sh

# 检查是否完全停止
./status.sh
```

## 下一步

启动成功后，您可以：

1. **访问前端应用** - http://localhost:3000
2. **查看API文档** - http://localhost:8000/docs
3. **上传文档** - 通过前端界面上传文档进行处理
4. **查看系统状态** - 使用 `./status.sh` 监控服务

## 获取帮助

如果遇到问题：

1. 检查 `logs/` 目录中的日志文件
2. 运行 `./status.sh` 查看服务状态
3. 确认环境变量配置正确
4. 检查系统要求是否满足

更多详细信息请参考项目根目录的 `README.md` 文件。
