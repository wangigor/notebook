# notebook-ai代码整合计划

本文档提供了将独立app目录代码整合到notebook-backend应用的详细计划。整合原则为：以notebook-backend中已存在的文件为准，仅迁移notebook-backend中不存在的功能和文件。

## 1. 需要迁移的关键组件

### worker目录
notebook-backend中缺失，需整体迁移：
- 将`app/worker`整体迁移到`notebook-backend/app/`下
- 调整导入路径，确保与notebook-backend现有代码兼容
- 确保Celery配置与现有应用一致

### websocket管理
notebook-backend中实现较简单：
- 将`app/core/websocket_manager.py`迁移到`notebook-backend/app/ws/`目录下
- 调整现有代码以使用新的websocket管理器
- 确保ws连接管理逻辑保持一致

### 任务相关API
notebook-backend中实现不完整：
- `app/api/endpoints/tasks.py`中的功能需迁移到`notebook-backend/app/routers/tasks.py`
- 确保保留现有的函数签名和参数结构
- 统一API响应格式

## 2. 需要合并/更新的核心功能

### 文档处理流程
需要合并两者的功能：
- notebook-backend已有文档处理功能，但缺少异步任务处理
- 需将app中的异步文档处理任务机制整合到notebook-backend的文档服务中
- 确保上传、处理、存储的完整流程保持一致

### 数据模型差异
需要统一数据模型：
- notebook-backend使用`document_id`作为文档标识，而app使用`id`
- 需统一为一种模式，同时确保数据库迁移脚本正确
- 确保所有关联关系正确映射

### API路由结构
需要整合为一致的结构：
- notebook-backend使用`routers`目录，app使用`api/endpoints`
- 需确保所有API路由保持一致的结构和命名
- 统一API参数和响应格式

## 3. 代码整合流程

1. **创建备份**：在开始整合前备份两个代码库
   ```bash
   cp -r app app_backup
   cp -r notebook-backend notebook-backend_backup
   ```

2. **结构调整**：创建必要的目录，确保统一的项目结构
   ```bash
   mkdir -p notebook-backend/app/worker
   mkdir -p notebook-backend/app/ws
   ```

3. **文件迁移**：从app迁移notebook-backend中不存在的文件
   ```bash
   # 迁移worker目录内容
   cp -r app/worker/* notebook-backend/app/worker/
   
   # 迁移websocket管理器
   cp app/core/websocket_manager.py notebook-backend/app/ws/connection_manager.py
   
   # 补充任务API
   cp app/api/endpoints/tasks.py notebook-backend/app/routers/tasks.py
   ```

4. **代码合并**：对于需要合并的文件，手动整合功能
   - 比较两个版本的实现差异
   - 保留notebook-backend的基本结构
   - 添加app中的额外功能
   - 确保命名和语法一致性

5. **导入路径修复**：更新所有导入语句，确保路径正确
   - 修改所有`app.`开头的导入路径
   - 确保所有服务和依赖项正确导入
   - 解决可能的循环导入问题

6. **数据库迁移**：如果模型有变化，创建相应的数据库迁移脚本
   - 使用Alembic生成迁移脚本
   - 仔细检查自动生成的迁移，确保没有数据丢失风险

7. **测试验证**：执行全面测试，确保功能正常
   - 上传文档测试
   - 任务处理流程测试
   - API端点测试
   - WebSocket连接测试

## 4. 必要的代码调整

### worker/celery_tasks.py 调整
- 更新导入路径
- 调整任务处理流程，确保与notebook-backend的document_service兼容
- 确保任务状态更新与WebSocket推送正常工作

### ws/connection_manager.py 调整
- 更新类名和方法名以适应notebook-backend的命名约定
- 确保接口与现有代码兼容
- 调整WebSocket消息格式

### routers/tasks.py 调整
- 统一API格式和响应结构
- 确保权限验证逻辑一致
- 调整依赖项注入方式

## 5. 潜在的问题和风险

1. **数据兼容性**：不同模型结构可能导致现有数据访问问题
2. **路径冲突**：迁移后的代码可能与现有路径冲突
3. **性能问题**：合并后的代码可能存在性能瓶颈
4. **错误处理不一致**：不同的错误处理策略可能导致不一致的用户体验

## 6. 后续建议

1. **代码审查**：整合后进行全面代码审查，确保代码质量和一致性
2. **文档更新**：更新API文档，反映合并后的变化
3. **监控系统**：建立监控系统，及时发现潜在问题
4. **持续优化**：根据实际运行情况，持续优化代码

## 7. 执行时间安排

整个代码整合过程预计需要1-2天的时间：
- 代码分析与规划：2小时
- 目录结构调整：1小时
- 文件迁移：1小时
- 代码合并和调整：8小时
- 测试与修复：4小时
- 部署与验证：2小时

按此计划执行，可确保代码整合的平稳过渡，减少潜在的问题和风险。 