# Celery 启动脚本说明

本项目提供了多个 Celery 启动脚本，每个脚本都包含完整的依赖加载和环境设置功能。

## 启动脚本对比

### 1. `celery_worker.sh` - 标准生产模式
- **用途**: 生产环境或标准开发环境
- **特点**: 
  - 完整的依赖检查和安装
  - 环境变量加载
  - 网络连接检查
  - 标准 Celery worker 启动
- **启动命令**: `./celery_worker.sh`

### 2. `start_celery.sh` - 队列指定模式  
- **用途**: 指定特定队列和并发数的场景
- **特点**:
  - 完整的依赖检查和安装
  - 指定 `document_processing` 队列
  - 并发数设置为 2
  - 适合生产环境的队列管理
- **启动命令**: `./start_celery.sh`

### 3. `celery_dev.sh` - 开发热部署模式 ⭐ 推荐开发使用
- **用途**: 开发环境，支持代码热部署
- **特点**:
  - 完整的依赖检查和安装
  - 自动监控 `app/` 目录下的 Python 文件变化
  - 代码变更时自动重启 Celery worker
  - 使用 `watchdog` 库实现文件监控
  - 防止频繁重启（1秒内多次变化只重启一次）
- **启动命令**: `./celery_dev.sh`

## 新增功能

所有脚本现在都包含以下功能（仿照 backend 启动脚本）：

### 1. 虚拟环境管理
- 自动创建 Python 3.10.13 虚拟环境
- 支持 pyenv 和系统 Python
- 自动激活虚拟环境

### 2. 依赖管理
- 自动升级 pip
- 安装 `requirements.txt` 中的所有依赖
- 确保 Celery 已安装

### 3. 环境检查
- 加载 `.env` 文件中的环境变量
- 检查 Qdrant 服务器连接状态
- 设置 PYTHONPATH

### 4. 网络适配
- 自动检测 Qdrant 服务器可用性
- 可用时使用远程服务器
- 不可用时切换到本地模拟模式

## 使用建议

### 开发环境
```bash
# 推荐使用热部署模式
./celery_dev.sh
```

### 生产环境
```bash
# 使用标准模式
./celery_worker.sh

# 或者使用队列指定模式
./start_celery.sh
```

### 停止 Celery
```bash
# 使用 Ctrl+C 停止
# 热部署模式会自动清理子进程
```

## 热部署功能详解

`celery_dev.sh` 脚本创建了一个 `celery_hotreload.py` 监控脚本，具有以下特性：

1. **文件监控**: 监控 `app/` 目录下所有 `.py` 文件
2. **智能重启**: 检测到文件变化时自动重启 Celery worker
3. **防抖动**: 1秒内的多次变化只触发一次重启
4. **进程管理**: 优雅地终止旧进程并启动新进程
5. **异常恢复**: 如果 Celery 进程意外退出，自动重新启动

## 故障排除

### 1. 权限问题
```bash
chmod +x celery_worker.sh start_celery.sh celery_dev.sh
```

### 2. Python 版本问题
确保系统中安装了 Python 3.10：
```bash
python3.10 --version
```

### 3. 依赖安装失败
手动安装依赖：
```bash
source venv/bin/activate
pip install -r requirements.txt
pip install celery watchdog
```

### 4. 热部署不工作
检查 watchdog 是否安装：
```bash
pip install watchdog
```

## 架构改进

现在 Celery 启动脚本与 backend 启动脚本具有相同的功能：
- ✅ 依赖自动安装
- ✅ 环境自动配置  
- ✅ 网络连接检查
- ✅ 虚拟环境管理
- ✅ 热部署支持（开发模式）

这确保了开发和生产环境的一致性，减少了环境配置问题。 