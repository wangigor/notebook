#!/usr/bin/env python3
"""
LLM服务验证脚本

用于验证LLMClientService的实际功能
"""
import sys
import os
import asyncio
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.llm_client_service import LLMClientService
from app.core.llm_config import LLMConfig

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_llm_service():
    """测试LLM服务功能"""
    
    print("=" * 50)
    print("LLM服务验证测试")
    print("=" * 50)
    
    try:
        # 1. 测试单例模式
        print("\n1. 测试单例模式...")
        service1 = LLMClientService()
        service2 = LLMClientService()
        assert service1 is service2, "单例模式失败"
        print("✓ 单例模式正常")
        
        # 2. 测试配置获取
        print("\n2. 测试配置获取...")
        config = LLMConfig.get_default_config(streaming=False)
        print(f"✓ 默认配置: {config}")
        
        # 3. 测试LLM实例获取
        print("\n3. 测试LLM实例获取...")
        
        # 非流式LLM
        llm_non_streaming = service1.get_llm(streaming=False)
        print(f"✓ 非流式LLM实例: {type(llm_non_streaming).__name__}")
        
        # 流式LLM
        llm_streaming = service1.get_llm(streaming=True)
        print(f"✓ 流式LLM实例: {type(llm_streaming).__name__}")
        
        # 4. 测试专用方法
        print("\n4. 测试专用方法...")
        
        chat_llm = service1.get_chat_llm()
        print(f"✓ 对话LLM实例: {type(chat_llm).__name__}")
        
        processing_llm = service1.get_processing_llm()
        print(f"✓ 处理LLM实例: {type(processing_llm).__name__}")
        
        # 5. 测试缓存机制
        print("\n5. 测试缓存机制...")
        
        # 再次获取相同配置的实例，应该从缓存返回
        llm_cached = service1.get_llm(streaming=False)
        assert llm_cached is llm_non_streaming, "缓存机制失败"
        print("✓ 缓存机制正常")
        
        # 6. 测试缓存信息
        print("\n6. 测试缓存信息...")
        cache_info = service1.get_cache_info()
        print(f"✓ 缓存信息: {cache_info}")
        
        # 7. 测试清理缓存
        print("\n7. 测试清理缓存...")
        service1.clear_cache()
        cache_info_after = service1.get_cache_info()
        print(f"✓ 清理后缓存信息: {cache_info_after}")
        
        print("\n" + "=" * 50)
        print("✅ 所有测试通过！LLM服务工作正常")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        logger.exception("测试过程中发生错误")
        return False
    
    return True

def test_configuration():
    """测试配置功能"""
    
    print("\n" + "=" * 30)
    print("配置测试")
    print("=" * 30)
    
    # 测试不同配置
    configs = [
        {"streaming": False},
        {"streaming": True},
        {"streaming": False, "temperature": 0.5},
        {"streaming": True, "model": "gpt-4"},
    ]
    
    for i, config in enumerate(configs, 1):
        print(f"\n{i}. 测试配置: {config}")
        full_config = LLMConfig.get_default_config(**config)
        print(f"   完整配置: {full_config}")

if __name__ == "__main__":
    print("开始LLM服务验证...")
    
    # 检查环境变量
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  警告: 未设置OPENAI_API_KEY环境变量")
        print("   某些功能可能无法正常工作")
    
    # 运行配置测试
    test_configuration()
    
    # 运行异步测试
    success = asyncio.run(test_llm_service())
    
    if success:
        print("\n🎉 LLM服务验证完成！")
        sys.exit(0)
    else:
        print("\n💥 LLM服务验证失败！")
        sys.exit(1) 