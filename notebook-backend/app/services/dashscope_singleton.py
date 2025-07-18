#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DashScope单例管理器
解决多DashScope客户端冲突，提供线程安全的全局实例
"""
import logging
import threading
import os
from typing import Optional, Dict, Any
from langchain_community.embeddings import DashScopeEmbeddings
from app.core.config import settings

logger = logging.getLogger(__name__)

class DashScopeSingleton:
    """
    DashScope单例管理器
    
    确保整个应用只有一个DashScope客户端实例，避免连接池冲突
    """
    
    _instance: Optional['DashScopeSingleton'] = None
    _lock = threading.Lock()
    _client_lock = threading.Lock()
    
    def __new__(cls):
        """线程安全的单例实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DashScopeSingleton, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化单例"""
        if getattr(self, '_initialized', False):
            return
        
        self._dashscope_client: Optional[DashScopeEmbeddings] = None
        self._process_id = os.getpid()
        self._connection_count = 0
        self._is_mock_mode = False
        self._initialization_error = None
        self._initialized = True
        
        logger.info("🔧 DashScope单例管理器初始化完成")
    
    def get_client(self, force_reinit: bool = False) -> DashScopeEmbeddings:
        """
        获取DashScope客户端实例
        
        Args:
            force_reinit: 是否强制重新初始化
            
        Returns:
            DashScopeEmbeddings实例
        """
        current_pid = os.getpid()
        
        # 检测进程变化（fork后）
        if current_pid != self._process_id:
            logger.warning(f"🔄 检测到进程变化: {self._process_id} -> {current_pid}，重新初始化DashScope客户端")
            force_reinit = True
            self._process_id = current_pid
        
        if self._dashscope_client is None or force_reinit:
            with self._client_lock:
                if self._dashscope_client is None or force_reinit:
                    self._initialize_client()
        
        self._connection_count += 1
        return self._dashscope_client
    
    def _initialize_client(self):
        """初始化DashScope客户端"""
        try:
            logger.info("🚀 正在初始化DashScope客户端...")
            
            if not settings.DASHSCOPE_API_KEY:
                logger.warning("⚠️ 未配置DASHSCOPE_API_KEY，使用Mock模式")
                self._is_mock_mode = True
                self._dashscope_client = self._create_mock_client()
                return
            
            # 创建DashScope客户端
            self._dashscope_client = DashScopeEmbeddings(
                dashscope_api_key=settings.DASHSCOPE_API_KEY,
                model=settings.DASHSCOPE_EMBEDDING_MODEL
            )
            
            # 健康检查
            self._health_check()
            
            logger.info("✅ DashScope客户端初始化成功")
            self._is_mock_mode = False
            self._initialization_error = None
            
        except Exception as e:
            logger.error(f"❌ DashScope客户端初始化失败: {str(e)}")
            self._initialization_error = str(e)
            self._is_mock_mode = True
            self._dashscope_client = self._create_mock_client()
    
    def _health_check(self):
        """健康检查"""
        try:
            # 执行简单的嵌入测试
            test_result = self._dashscope_client.embed_query("健康检查")
            if not test_result or len(test_result) == 0:
                raise ValueError("健康检查失败：返回空向量")
            logger.info(f"✅ DashScope健康检查通过，向量维度: {len(test_result)}")
        except Exception as e:
            logger.error(f"❌ DashScope健康检查失败: {str(e)}")
            raise
    
    def _create_mock_client(self) -> DashScopeEmbeddings:
        """创建Mock客户端"""
        from langchain_core.embeddings import Embeddings
        import random
        
        class MockDashScopeEmbeddings(Embeddings):
            """Mock DashScope嵌入客户端"""
            
            def embed_documents(self, texts):
                logger.warning(f"🎭 Mock模式：处理{len(texts)}个文档")
                return [[random.gauss(0, 1) for _ in range(settings.VECTOR_SIZE)] for _ in range(len(texts))]
            
            def embed_query(self, text):
                logger.warning(f"🎭 Mock模式：处理查询 {text[:30]}...")
                return [random.gauss(0, 1) for _ in range(settings.VECTOR_SIZE)]
        
        logger.info("🎭 创建Mock DashScope客户端")
        return MockDashScopeEmbeddings()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "process_id": self._process_id,
            "connection_count": self._connection_count,
            "is_mock_mode": self._is_mock_mode,
            "initialization_error": self._initialization_error,
            "client_initialized": self._dashscope_client is not None
        }
    
    def reset(self):
        """重置客户端（用于测试）"""
        with self._client_lock:
            self._dashscope_client = None
            self._connection_count = 0
            self._initialization_error = None
            logger.info("🔄 DashScope客户端已重置")

# 全局单例实例
_dashscope_singleton = DashScopeSingleton()

def get_dashscope_client(force_reinit: bool = False) -> DashScopeEmbeddings:
    """
    获取全局DashScope客户端实例
    
    Args:
        force_reinit: 是否强制重新初始化
        
    Returns:
        DashScopeEmbeddings实例
    """
    return _dashscope_singleton.get_client(force_reinit=force_reinit)

def get_dashscope_stats() -> Dict[str, Any]:
    """获取DashScope客户端统计信息"""
    return _dashscope_singleton.get_stats()

def reset_dashscope_client():
    """重置DashScope客户端"""
    _dashscope_singleton.reset() 