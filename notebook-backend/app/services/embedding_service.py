# -*- coding: utf-8 -*-
"""
统一嵌入向量服务
提供统一的文本嵌入向量生成接口
"""
import logging
import numpy as np
from typing import List, Optional
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.embeddings import Embeddings
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    统一嵌入向量服务
    
    提供统一的文本嵌入向量生成接口，支持文档和查询的向量化
    """
    
    def __init__(self):
        """初始化嵌入服务"""
        logger.info("初始化统一嵌入向量服务")
        self.embedding_model = None
        self.is_mock_mode = False
        self._init_embedding_model()
    
    def _init_embedding_model(self):
        """初始化嵌入模型"""
        try:
            # 检查 DASHSCOPE_API_KEY 是否已配置
            if not settings.DASHSCOPE_API_KEY:
                logger.error("未配置 DASHSCOPE_API_KEY，无法初始化嵌入模型")
                raise ValueError("未配置 DASHSCOPE_API_KEY，无法初始化嵌入模型")
            
            logger.info("正在初始化 DashScope 嵌入模型...")
            
            # 使用 DashScope 嵌入模型
            self.embedding_model = DashScopeEmbeddings(
                dashscope_api_key=settings.DASHSCOPE_API_KEY,
                model=settings.DASHSCOPE_EMBEDDING_MODEL
            )
            
            # 测试嵌入模型是否可用
            try:
                # 使用一个简单的文本进行测试
                test_embeddings = self.embedding_model.embed_documents(["测试文本"])
                logger.info(f"嵌入模型测试成功，向量维度: {len(test_embeddings[0])}")
                logger.info("成功初始化 DashScope 嵌入模型")
            except Exception as test_error:
                logger.error(f"嵌入模型测试失败: {str(test_error)}")
                raise ValueError(f"嵌入模型测试失败: {str(test_error)}")
                
        except Exception as e:
            logger.error(f"初始化嵌入模型失败: {str(e)}")
            logger.warning("切换到模拟模式")
            self.is_mock_mode = True
            self.embedding_model = self._create_mock_embeddings()
    
    def _create_mock_embeddings(self) -> Embeddings:
        """创建模拟嵌入模型"""
        
        class MockEmbeddings(Embeddings):
            """Mock嵌入模型，用于测试"""
            
            def embed_documents(self, texts: List[str]) -> List[List[float]]:
                """为文本生成随机嵌入向量"""
                logger.warning(f"使用MockEmbeddings处理 {len(texts)} 条文本")
                return [np.random.randn(settings.VECTOR_SIZE).tolist() for _ in range(len(texts))]
                
            def embed_query(self, text: str) -> List[float]:
                """为查询生成随机嵌入向量"""
                logger.warning(f"使用MockEmbeddings处理查询: {text[:30]}...")
                return np.random.randn(settings.VECTOR_SIZE).tolist()
        
        logger.info("创建 MockEmbeddings 作为备份方案")
        return MockEmbeddings()
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量文档嵌入
        
        Args:
            texts: 要嵌入的文本列表
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        if not texts:
            logger.warning("输入文本列表为空")
            return []
        
        try:
            logger.info(f"正在为 {len(texts)} 条文本生成嵌入向量...")
            embeddings = self.embedding_model.embed_documents(texts)
            logger.info(f"成功生成 {len(embeddings)} 个嵌入向量")
            return embeddings
        except Exception as e:
            logger.error(f"批量文档嵌入失败: {str(e)}")
            # 返回随机向量作为备份
            logger.warning("返回随机向量作为备份")
            return [np.random.randn(settings.VECTOR_SIZE).tolist() for _ in range(len(texts))]
    
    def embed_query(self, text: str) -> List[float]:
        """
        单个查询嵌入
        
        Args:
            text: 要嵌入的查询文本
            
        Returns:
            List[float]: 嵌入向量
        """
        if not text:
            logger.warning("输入查询文本为空")
            return np.random.randn(settings.VECTOR_SIZE).tolist()
        
        try:
            logger.info(f"正在为查询文本生成嵌入向量: {text[:50]}...")
            embedding = self.embedding_model.embed_query(text)
            logger.info("成功生成查询嵌入向量")
            return embedding
        except Exception as e:
            logger.error(f"查询嵌入失败: {str(e)}")
            # 返回随机向量作为备份
            logger.warning("返回随机向量作为备份")
            return np.random.randn(settings.VECTOR_SIZE).tolist()
    
    def get_vector_dimension(self) -> int:
        """
        获取向量维度
        
        Returns:
            int: 向量维度
        """
        return settings.VECTOR_SIZE
    
    def is_available(self) -> bool:
        """
        检查服务可用性
        
        Returns:
            bool: 服务是否可用
        """
        if self.is_mock_mode:
            logger.info("嵌入服务运行在模拟模式")
            return False
        
        try:
            # 进行简单的可用性测试
            test_embedding = self.embedding_model.embed_query("测试")
            return len(test_embedding) == settings.VECTOR_SIZE
        except Exception as e:
            logger.error(f"服务可用性检查失败: {str(e)}")
            return False


# 创建全局实例（单例模式）
_embedding_service_instance = None

def get_embedding_service() -> EmbeddingService:
    """
    获取嵌入服务实例（单例模式）
    
    Returns:
        EmbeddingService: 嵌入服务实例
    """
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance 