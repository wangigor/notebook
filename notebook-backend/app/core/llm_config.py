"""
LLM 配置管理模块
"""
from enum import Enum
from typing import Dict, Any, Optional
import os


class ModelType(Enum):
    """模型类型枚举"""
    GPT_4_1_MINI = "gpt-4.1-mini"
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"


class LLMConfig:
    """LLM 配置类"""
    
    # 默认配置
    DEFAULT_MODEL = ModelType.GPT_4O_MINI.value
    DEFAULT_TEMPERATURE = 0
    DEFAULT_MAX_TOKENS = None
    DEFAULT_TIMEOUT = 60
    DEFAULT_MAX_RETRIES = 3
    
    # 从环境变量获取配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
    
    @classmethod
    def get_default_config(cls, streaming: bool = False, **kwargs) -> Dict[str, Any]:
        """获取默认配置
        
        Args:
            streaming: 是否启用流式响应
            **kwargs: 额外的配置参数
            
        Returns:
            默认配置字典
        """
        config = {
            "model": cls.DEFAULT_MODEL,
            "temperature": cls.DEFAULT_TEMPERATURE,
            "streaming": streaming,
            "timeout": cls.DEFAULT_TIMEOUT,
            "max_retries": cls.DEFAULT_MAX_RETRIES,
        }
        
        if cls.DEFAULT_MAX_TOKENS:
            config["max_tokens"] = cls.DEFAULT_MAX_TOKENS
            
        if cls.OPENAI_API_KEY:
            config["api_key"] = cls.OPENAI_API_KEY
            
        if cls.OPENAI_API_BASE:
            config["base_url"] = cls.OPENAI_API_BASE
        
        # 合并额外参数
        config.update(kwargs)
            
        return config
    
    @classmethod
    def get_chat_config(cls, streaming: bool = True) -> Dict[str, Any]:
        """获取对话专用配置
        
        Args:
            streaming: 是否启用流式响应，对话场景默认为True
            
        Returns:
            对话配置字典
        """
        return cls.get_default_config(streaming=streaming)
    
    @classmethod
    def get_processing_config(cls, streaming: bool = False) -> Dict[str, Any]:
        """获取文档处理专用配置
        
        Args:
            streaming: 是否启用流式响应，处理场景默认为False
            
        Returns:
            处理配置字典
        """
        return cls.get_default_config(streaming=streaming) 