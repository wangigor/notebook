# LLM图构建器技术文档

## 文档概述

本文档集合提供了LLM图构建器项目的完整技术指导，涵盖从系统架构到部署运维的各个方面。

## 文档结构

### 📋 [完整开发指南](./llm-graph-builder-complete-guide.md)
- **目标用户**: 项目经理、架构师、高级开发者
- **内容**: 系统整体概览、技术选型、完整处理流程
- **适用场景**: 快速了解项目全貌、技术决策参考

### 🏗️ [架构设计文档](./architecture-design.md) 
- **目标用户**: 架构师、技术负责人、高级开发者
- **内容**: 系统架构、模块设计、数据流、扩展性设计
- **适用场景**: 架构评审、系统设计、技术改进

### 🔌 [API接口文档](./api-reference.md)
- **目标用户**: 前端开发者、集成开发者、测试工程师
- **内容**: 详细API规范、请求响应格式、错误处理、使用示例
- **适用场景**: 前后端协作、第三方集成、API测试

### ⚙️ [核心模块指南](./core-modules-guide.md)
- **目标用户**: 后端开发者、算法工程师
- **内容**: 核心代码实现、模块设计、扩展开发
- **适用场景**: 功能开发、代码维护、模块扩展

### 🚀 [部署配置指南](./deployment-guide.md)
- **目标用户**: DevOps工程师、运维人员、部署负责人
- **内容**: 环境配置、容器化部署、Kubernetes集群部署
- **适用场景**: 生产部署、环境配置、运维管理

## 快速导航

### 🎯 按角色导航

**项目负责人/产品经理**
1. [完整开发指南](./llm-graph-builder-complete-guide.md) - 了解项目全貌
2. [架构设计文档](./architecture-design.md) - 理解技术架构

**后端开发者**
1. [核心模块指南](./core-modules-guide.md) - 核心代码实现
2. [API接口文档](./api-reference.md) - API设计规范
3. [架构设计文档](./architecture-design.md) - 系统架构理解

**前端开发者**
1. [API接口文档](./api-reference.md) - API调用指南
2. [完整开发指南](./llm-graph-builder-complete-guide.md) - 业务流程理解

**DevOps工程师**
1. [部署配置指南](./deployment-guide.md) - 部署运维指南
2. [架构设计文档](./architecture-design.md) - 系统架构理解

**算法工程师**
1. [核心模块指南](./core-modules-guide.md) - LLM集成实现
2. [完整开发指南](./llm-graph-builder-complete-guide.md) - 处理流程理解

### 🎯 按场景导航

**新项目开发**
1. [完整开发指南](./llm-graph-builder-complete-guide.md) - 整体方案
2. [架构设计文档](./architecture-design.md) - 架构参考
3. [核心模块指南](./core-modules-guide.md) - 实现参考

**系统集成**
1. [API接口文档](./api-reference.md) - 集成接口
2. [架构设计文档](./architecture-design.md) - 系统理解
3. [部署配置指南](./deployment-guide.md) - 环境配置

**功能扩展**
1. [核心模块指南](./core-modules-guide.md) - 模块扩展
2. [架构设计文档](./architecture-design.md) - 架构约束
3. [API接口文档](./api-reference.md) - 接口规范

**生产部署**
1. [部署配置指南](./deployment-guide.md) - 部署方案
2. [架构设计文档](./architecture-design.md) - 性能优化
3. [完整开发指南](./llm-graph-builder-complete-guide.md) - 配置参考

## 技术特性

### 核心功能
- 📄 **多格式文档处理**: PDF、Word、Excel、图片、文本等
- 🤖 **多模型LLM集成**: OpenAI、Google、Anthropic、Ollama等
- 🔗 **知识图谱构建**: 实体识别、关系抽取、图结构优化
- 🔍 **多模态检索**: 向量检索、图检索、混合检索
- 💬 **智能问答**: 基于知识图谱的上下文感知对话

### 技术亮点
- 🏗️ **微服务架构**: 模块化设计，易于扩展和维护
- ⚡ **异步处理**: 大文件分块上传，异步任务处理
- 🎯 **高性能**: 向量索引、缓存策略、连接池优化
- 🔒 **安全可靠**: JWT认证、输入验证、错误恢复
- 📊 **可观测性**: 结构化日志、性能监控、健康检查

### 扩展能力
- 🔌 **插件架构**: 支持自定义文档加载器、LLM模型
- 📈 **水平扩展**: Kubernetes集群部署，自动伸缩
- 🌐 **多数据源**: 本地文件、云存储、网页、社交媒体
- 🎨 **可视化**: 图谱可视化、关系探索、数据洞察

## 快速开始

### 前置条件
- Python 3.9+
- Node.js 18+
- Neo4j 5.0+
- Docker (可选)
- Kubernetes (可选)

### 本地开发环境
```bash
# 1. 克隆项目
git clone <repository-url>
cd llm-graph-builder

# 2. 启动Neo4j
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -e NEO4J_PLUGINS='["apoc","graph-data-science"]' \
  neo4j:5.15

# 3. 配置后端
cd backend
python -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑.env配置文件

# 4. 启动后端服务
uvicorn main:app --reload

# 5. 配置前端 (新终端)
cd frontend
npm install
cp .env.example .env.local
# 编辑前端环境变量

# 6. 启动前端服务
npm start
```

### Docker快速部署
```bash
# 克隆项目
git clone <repository-url>
cd llm-graph-builder

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 访问应用
# 前端: http://localhost:3000
# 后端API: http://localhost:8000
# Neo4j浏览器: http://localhost:7474
```

## 版本信息

### 当前版本: v1.0.0

**主要特性**:
- 完整的文档到知识图谱处理流程
- 多种LLM模型支持
- 容器化部署支持
- RESTful API接口
- React前端界面

**技术栈**:
- **后端**: Python 3.9, FastAPI, LangChain, Neo4j
- **前端**: React 18, TypeScript, Material-UI
- **数据库**: Neo4j 5.15, Redis 7
- **部署**: Docker, Kubernetes

## 贡献指南

### 开发规范
1. 遵循[代码风格指南](./llm-graph-builder-complete-guide.md#代码风格与组织)
2. 提交前运行测试套件
3. 更新相关文档
4. 提交详细的Pull Request描述

### 文档更新
1. 修改代码时同步更新文档
2. 添加新功能时更新API文档
3. 架构变更时更新架构文档
4. 部署方式变更时更新部署指南

### 问题反馈
1. 使用GitHub Issues报告问题
2. 提供详细的错误信息和重现步骤
3. 标明环境信息和版本号

## 常见问题

### Q: 支持哪些文档格式？
A: 支持PDF、Word、Excel、PowerPoint、图片(JPG/PNG)、文本文件等多种格式。

### Q: 支持哪些LLM模型？
A: 支持OpenAI GPT系列、Google Gemini、Anthropic Claude、Ollama本地模型等。

### Q: 如何处理大文件？
A: 系统支持分块上传和处理，可配置最大文件大小和分块策略。

### Q: 如何扩展自定义功能？
A: 系统采用插件架构，可以扩展自定义文档加载器、LLM模型、处理器等。

### Q: 生产环境部署建议？
A: 推荐使用Kubernetes集群部署，配置自动伸缩、监控告警、数据备份等。

## 技术支持

### 文档维护
- 📝 **文档版本**: 与代码版本同步更新
- 🔄 **更新频率**: 每次功能发布都会更新相关文档
- 📞 **技术支持**: 通过GitHub Issues或邮件联系

### 培训资源
- 🎓 **新手教程**: [完整开发指南](./llm-graph-builder-complete-guide.md)
- 🔧 **开发实战**: [核心模块指南](./core-modules-guide.md)
- 🚀 **部署实践**: [部署配置指南](./deployment-guide.md)

---

**注意**: 本文档基于LLM图构建器v1.0.0版本编写，如有疑问请参考对应版本的代码实现。 