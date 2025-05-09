import logging
import os
import sys

# 设置日志格式
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

from app.services.vector_store import VectorStoreService

def main():
    print("\n===== 开始测试向量存储服务 =====\n")
    
    # 检查环境变量
    print("DASHSCOPE_API_KEY:", os.environ.get("DASHSCOPE_API_KEY", "未设置"))
    print("QDRANT_URL:", os.environ.get("QDRANT_URL", "未设置"))
    print("QDRANT_COLLECTION_NAME:", os.environ.get("QDRANT_COLLECTION_NAME", "未设置"))
    print("\n")
    
    # 1. 使用强制模拟模式
    print("1. 使用强制模拟模式初始化")
    mock_service = VectorStoreService(force_mock=True)
    print(f"初始化结果: is_mock_mode={mock_service.is_mock_mode}, vector_store={mock_service.vector_store}, client={mock_service.client}")
    
    # 2. 使用默认模式
    print("\n2. 使用默认模式初始化")
    service = VectorStoreService()
    print(f"初始化结果: is_mock_mode={service.is_mock_mode}, vector_store={service.vector_store is not None}, client={service.client is not None}")
    
    # 3. 测试搜索功能
    print("\n3. 测试相似度搜索")
    results = service.similarity_search("测试查询", k=2)
    print(f"搜索结果数量: {len(results)}")
    if results:
        print(f"第一个结果: {results[0]}")
    
    print("\n===== 测试完成 =====\n")

if __name__ == "__main__":
    main() 