# -*- coding: utf-8 -*-
"""
自主Agent配置管理
集中管理自主实体去重Agent的配置选项
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class AutonomousAgentConfig:
    """自主Agent配置类"""
    
    # === 基础配置 ===
    max_conversation_turns: int = 8
    confidence_threshold: float = 0.85
    conservative_mode: bool = True
    enable_reflection: bool = True
    batch_size: int = 20
    
    # === 工具配置 ===
    enable_wikipedia_search: bool = True
    enable_semantic_comparison: bool = True
    wikipedia_search_timeout: int = 10
    max_tool_calls_per_turn: int = 5
    
    # === 决策引擎配置 ===
    merge_threshold: float = 0.85
    risk_threshold: float = 0.7
    verification_threshold: float = 0.6
    
    # === 性能配置 ===
    enable_parallel_processing: bool = True
    max_parallel_entities: int = 50
    processing_timeout: int = 300  # 5分钟
    
    # === 集成配置 ===
    enable_fallback: bool = True
    fallback_to_traditional: bool = True
    log_level: str = "INFO"
    
    # === 高级配置 ===
    custom_decision_rules: Dict[str, Any] = field(default_factory=dict)
    entity_type_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "组织": 0.80,
        "人物": 0.85,
        "产品": 0.75,
        "地点": 0.90,
        "技术": 0.70
    })
    
    @classmethod
    def from_env(cls) -> 'AutonomousAgentConfig':
        """从环境变量加载配置"""
        config = cls()
        
        # 基础配置
        config.max_conversation_turns = int(os.getenv('AGENT_MAX_TURNS', config.max_conversation_turns))
        config.confidence_threshold = float(os.getenv('AGENT_CONFIDENCE_THRESHOLD', config.confidence_threshold))
        config.conservative_mode = os.getenv('AGENT_CONSERVATIVE_MODE', 'true').lower() == 'true'
        config.enable_reflection = os.getenv('AGENT_ENABLE_REFLECTION', 'true').lower() == 'true'
        config.batch_size = int(os.getenv('AGENT_BATCH_SIZE', config.batch_size))
        
        # 工具配置
        config.enable_wikipedia_search = os.getenv('AGENT_ENABLE_WIKIPEDIA', 'true').lower() == 'true'
        config.enable_semantic_comparison = os.getenv('AGENT_ENABLE_SEMANTIC', 'true').lower() == 'true'
        config.wikipedia_search_timeout = int(os.getenv('AGENT_WIKIPEDIA_TIMEOUT', config.wikipedia_search_timeout))
        
        # 决策引擎配置
        config.merge_threshold = float(os.getenv('AGENT_MERGE_THRESHOLD', config.merge_threshold))
        config.risk_threshold = float(os.getenv('AGENT_RISK_THRESHOLD', config.risk_threshold))
        
        # 性能配置
        config.enable_parallel_processing = os.getenv('AGENT_ENABLE_PARALLEL', 'true').lower() == 'true'
        config.max_parallel_entities = int(os.getenv('AGENT_MAX_PARALLEL', config.max_parallel_entities))
        config.processing_timeout = int(os.getenv('AGENT_PROCESSING_TIMEOUT', config.processing_timeout))
        
        # 集成配置
        config.enable_fallback = os.getenv('AGENT_ENABLE_FALLBACK', 'true').lower() == 'true'
        config.fallback_to_traditional = os.getenv('AGENT_FALLBACK_TRADITIONAL', 'true').lower() == 'true'
        config.log_level = os.getenv('AGENT_LOG_LEVEL', config.log_level)
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'max_conversation_turns': self.max_conversation_turns,
            'confidence_threshold': self.confidence_threshold,
            'conservative_mode': self.conservative_mode,
            'enable_reflection': self.enable_reflection,
            'batch_size': self.batch_size,
            'enable_wikipedia_search': self.enable_wikipedia_search,
            'enable_semantic_comparison': self.enable_semantic_comparison,
            'wikipedia_search_timeout': self.wikipedia_search_timeout,
            'max_tool_calls_per_turn': self.max_tool_calls_per_turn,
            'merge_threshold': self.merge_threshold,
            'risk_threshold': self.risk_threshold,
            'verification_threshold': self.verification_threshold,
            'enable_parallel_processing': self.enable_parallel_processing,
            'max_parallel_entities': self.max_parallel_entities,
            'processing_timeout': self.processing_timeout,
            'enable_fallback': self.enable_fallback,
            'fallback_to_traditional': self.fallback_to_traditional,
            'log_level': self.log_level,
            'custom_decision_rules': self.custom_decision_rules,
            'entity_type_thresholds': self.entity_type_thresholds
        }
    
    def update_from_dict(self, config_dict: Dict[str, Any]):
        """从字典更新配置"""
        for key, value in config_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def get_entity_threshold(self, entity_type: str) -> float:
        """获取特定实体类型的阈值"""
        return self.entity_type_thresholds.get(entity_type, self.confidence_threshold)
    
    def is_valid(self) -> bool:
        """验证配置有效性"""
        # 基础验证
        if not 1 <= self.max_conversation_turns <= 20:
            return False
        
        if not 0.0 <= self.confidence_threshold <= 1.0:
            return False
        
        if not 0.0 <= self.merge_threshold <= 1.0:
            return False
        
        if not 0.0 <= self.risk_threshold <= 1.0:
            return False
        
        if not 1 <= self.batch_size <= 100:
            return False
        
        if not 10 <= self.processing_timeout <= 3600:
            return False
        
        return True


# 全局配置实例
_global_config = None

def get_autonomous_agent_config() -> AutonomousAgentConfig:
    """获取全局自主Agent配置"""
    global _global_config
    if _global_config is None:
        _global_config = AutonomousAgentConfig.from_env()
    return _global_config

def update_autonomous_agent_config(config_dict: Dict[str, Any]):
    """更新全局配置"""
    global _global_config
    if _global_config is None:
        _global_config = AutonomousAgentConfig.from_env()
    _global_config.update_from_dict(config_dict)

def reset_autonomous_agent_config():
    """重置全局配置"""
    global _global_config
    _global_config = None