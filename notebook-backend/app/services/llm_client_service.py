"""
LLM 客户端服务模块
"""
import logging
from typing import Dict, Any, Optional
from threading import Lock
from langchain_openai import ChatOpenAI

from app.core.llm_config import LLMConfig

logger = logging.getLogger(__name__)


class LLMClientService:
    """LLM 客户端服务类 - 单例模式"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(LLMClientService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化服务"""
        if self._initialized:
            return
            
        self._llm_instances: Dict[str, ChatOpenAI] = {}
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._initialized = True
        logger.info("LLM客户端服务初始化完成")
    
    def _generate_cache_key(self, **kwargs) -> str:
        """生成缓存键
        
        Args:
            **kwargs: 配置参数
            
        Returns:
            缓存键字符串
        """
        # 将配置参数转换为排序后的字符串作为缓存键
        sorted_items = sorted(kwargs.items())
        return str(hash(tuple(sorted_items)))
    
    def _create_llm_instance(self, **kwargs) -> ChatOpenAI:
        """创建 LLM 实例
        
        Args:
            **kwargs: 配置参数
            
        Returns:
            ChatOpenAI 实例
        """
        try:
            # 过滤掉不属于 ChatOpenAI 的参数
            valid_params = {}
            for key, value in kwargs.items():
                if key in ['model', 'temperature', 'streaming', 'timeout', 'max_retries', 'api_key', 'base_url', 'max_tokens']:
                    valid_params[key] = value
            
            logger.debug(f"创建LLM实例，参数: {valid_params}")
            return ChatOpenAI(**valid_params)
        except Exception as e:
            logger.error(f"创建LLM实例失败: {str(e)}")
            raise
    
    def get_llm(self, streaming: bool = False, **kwargs) -> ChatOpenAI:
        """获取 LLM 实例
        
        Args:
            streaming: 是否启用流式响应
            **kwargs: 其他配置参数
            
        Returns:
            ChatOpenAI 实例
        """
        # 获取默认配置
        config = LLMConfig.get_default_config(streaming=streaming)
        
        # 合并用户提供的配置
        config.update(kwargs)
        
        # 生成缓存键
        cache_key = self._generate_cache_key(**config)
        
        # 检查缓存
        if cache_key in self._llm_instances:
            logger.debug(f"从缓存获取LLM实例: {cache_key}")
            return self._llm_instances[cache_key]
        
        # 创建新实例
        logger.info(f"创建新的LLM实例: streaming={streaming}")
        llm_instance = self._create_llm_instance(**config)
        
        # 缓存实例
        self._llm_instances[cache_key] = llm_instance
        self._config_cache[cache_key] = config.copy()
        
        return llm_instance
    
    def get_chat_llm(self, streaming: bool = True, **kwargs) -> ChatOpenAI:
        """获取对话专用的 LLM 实例
        
        Args:
            streaming: 是否启用流式响应，对话场景默认为True
            **kwargs: 其他配置参数
            
        Returns:
            ChatOpenAI 实例
        """
        # 获取对话专用配置
        config = LLMConfig.get_chat_config(streaming=streaming)
        
        # 合并用户提供的配置
        config.update(kwargs)
        
        # 生成缓存键
        cache_key = self._generate_cache_key(**config)
        
        # 检查缓存
        if cache_key in self._llm_instances:
            logger.debug(f"从缓存获取对话LLM实例: {cache_key}")
            return self._llm_instances[cache_key]
        
        # 创建新实例
        logger.info(f"创建新的对话LLM实例: streaming={streaming}")
        llm_instance = self._create_llm_instance(**config)
        
        # 缓存实例
        self._llm_instances[cache_key] = llm_instance
        self._config_cache[cache_key] = config.copy()
        
        return llm_instance
    
    def get_processing_llm(self, streaming: bool = False, **kwargs) -> ChatOpenAI:
        """获取文档处理专用的 LLM 实例
        
        Args:
            streaming: 是否启用流式响应，处理场景默认为False
            **kwargs: 其他配置参数
            
        Returns:
            ChatOpenAI 实例
        """
        # 获取处理专用配置
        config = LLMConfig.get_processing_config(streaming=streaming)
        
        # 合并用户提供的配置
        config.update(kwargs)
        
        # 生成缓存键
        cache_key = self._generate_cache_key(**config)
        
        # 检查缓存
        if cache_key in self._llm_instances:
            logger.debug(f"从缓存获取处理LLM实例: {cache_key}")
            return self._llm_instances[cache_key]
        
        # 创建新实例
        logger.info(f"创建新的处理LLM实例: streaming={streaming}")
        llm_instance = self._create_llm_instance(**config)
        
        # 缓存实例
        self._llm_instances[cache_key] = llm_instance
        self._config_cache[cache_key] = config.copy()
        
        return llm_instance
    
    def clear_cache(self):
        """清空缓存"""
        logger.info("清空LLM实例缓存")
        self._llm_instances.clear()
        self._config_cache.clear()
    
    def reinitialize(self):
        """重新初始化所有LLM实例"""
        logger.info("重新初始化所有LLM实例")
        # 清空缓存
        self.clear_cache()
        # 重新创建常用实例
        self.get_chat_llm(streaming=True)
        self.get_processing_llm(streaming=False)
        logger.info("LLM实例重新初始化完成")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息
        
        Returns:
            缓存信息字典
        """
        return {
            "cached_instances": len(self._llm_instances),
            "cache_keys": list(self._config_cache.keys())
        } 