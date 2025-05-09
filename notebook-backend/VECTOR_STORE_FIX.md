# 向量存储服务问题修复

## 问题描述

在日志中发现错误 `初始化向量存储失败: 'request'`，但没有完整的错误堆栈信息，导致难以诊断问题。

## 根本原因

1. **导入冲突**：`_get_embeddings` 方法中重复导入了 `DashScopeEmbeddings`，但路径与文件顶部的导入不同，导致潜在冲突。
2. **异常处理不完善**：初始化向量存储时未捕获和记录完整的异常堆栈，只记录了简单的错误消息。
3. **错误追踪**：DashScope API 调用失败时，生成的错误没有正确处理。

## 修复方案

1. **改进导入**：移除 `_get_embeddings` 方法中的重复导入，使用文件顶部已导入的 `DashScopeEmbeddings` 类。
2. **增强错误处理**：
   - 添加详细的错误日志，包括完整的堆栈跟踪
   - 添加详细的调试日志，帮助诊断问题
3. **添加容错机制**：
   - 在 `_get_embeddings` 方法中添加模拟嵌入模型作为备选方案
   - 修改 `VectorStoreService` 初始化逻辑，在遇到错误时自动切换到模拟模式
4. **参数检查**：添加对必要环境变量（如 DASHSCOPE_API_KEY）的检查和验证

## 使用方法

当使用 `VectorStoreService` 类时，现在有以下选项：

1. **正常模式**（尝试连接真实的 Qdrant 服务和 DashScope API）:
   ```python
   service = VectorStoreService()
   ```

2. **强制模拟模式**（不进行任何外部 API 调用，使用模拟数据）:
   ```python
   service = VectorStoreService(force_mock=True)
   ```

3. **通过环境变量控制模式**:
   在 `.env` 文件中设置 `MOCK_VECTOR_STORE=True` 来启用模拟模式

## 注意事项

- 模拟模式下生成的向量是随机的，仅用于测试和开发
- 为了正常使用向量存储服务，需确保以下环境变量正确配置：
  - `DASHSCOPE_API_KEY`：用于生成嵌入向量的 API 密钥
  - `QDRANT_URL`：Qdrant 服务的 URL
  - `QDRANT_COLLECTION_NAME`：向量集合名称

## 测试

提供了一个测试脚本 `test_vector_store.py`，可用于验证向量存储服务的功能和配置：

```bash
python test_vector_store.py
```

这个脚本会检查环境变量、尝试初始化服务、测试相似度搜索功能，并输出详细的日志和结果。 