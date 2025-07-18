# -*- coding: utf-8 -*-
"""
Agent状态模型
定义实体分析Agent的状态结构
"""
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class EntityPair(BaseModel):
    """实体对模型"""
    entity1_index: int
    entity2_index: int
    entity1_name: str
    entity2_name: str
    confidence: Literal["high", "medium", "low"]
    similarity_score: float = 0.0
    reason: str = ""
    needs_verification: bool = False

class SearchResult(BaseModel):
    """搜索结果模型"""
    entity_name: str
    found: bool
    title: Optional[str] = None
    summary: Optional[str] = None
    url: Optional[str] = None
    categories: List[str] = []
    entity_type: Optional[str] = None
    type_relevance: float = 0.0
    disambiguation: bool = False
    options: List[str] = []
    error: Optional[str] = None

class MergeDecision(BaseModel):
    """合并决策模型"""
    primary_entity_index: int
    duplicate_indices: List[int]
    merged_name: str
    merged_description: str
    confidence: float
    reason: str
    wikipedia_evidence: Optional[str] = None

class EntityAnalysisState(BaseModel):
    """Agent分析状态"""
    # 输入数据
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    entity_type: str = ""
    
    # 处理状态
    processing_step: Literal["initial", "search", "decision", "complete"] = "initial"
    started_at: datetime = Field(default_factory=datetime.now)
    
    # 分析结果
    initial_analysis: Optional[Dict[str, Any]] = None
    entity_pairs: List[EntityPair] = Field(default_factory=list)
    search_results: Dict[str, SearchResult] = Field(default_factory=dict)
    final_decision: Optional[Dict[str, Any]] = None
    
    # 合并决策
    merge_groups: List[MergeDecision] = Field(default_factory=list)
    independent_entities: List[int] = Field(default_factory=list)
    uncertain_cases: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 统计信息
    total_entities: int = 0
    pairs_analyzed: int = 0
    searches_performed: int = 0
    processing_time: float = 0.0
    
    # 错误和日志
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    debug_info: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
    
    def add_error(self, error: str):
        """添加错误信息"""
        self.errors.append(f"[{datetime.now().strftime('%H:%M:%S')}] {error}")
    
    def add_warning(self, warning: str):
        """添加警告信息"""
        self.warnings.append(f"[{datetime.now().strftime('%H:%M:%S')}] {warning}")
    
    def add_debug_info(self, key: str, value: Any):
        """添加调试信息"""
        self.debug_info[key] = value
    
    def get_entity_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """根据索引获取实体"""
        if 0 <= index < len(self.entities):
            return self.entities[index]
        return None
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """获取处理摘要"""
        return {
            "processing_step": self.processing_step,
            "total_entities": self.total_entities,
            "pairs_analyzed": self.pairs_analyzed,
            "searches_performed": self.searches_performed,
            "processing_time": self.processing_time,
            "merge_groups": len(self.merge_groups),
            "independent_entities": len(self.independent_entities),
            "uncertain_cases": len(self.uncertain_cases),
            "errors": len(self.errors),
            "warnings": len(self.warnings)
        }
    
    def is_complete(self) -> bool:
        """检查是否处理完成"""
        return self.processing_step == "complete"
    
    def has_errors(self) -> bool:
        """检查是否有错误"""
        return len(self.errors) > 0

class AgentConfig(BaseModel):
    """Agent配置模型"""
    # Wikipedia搜索配置
    max_wikipedia_search_results: int = 3
    wikipedia_summary_sentences: int = 3
    search_timeout_seconds: int = 10
    max_concurrent_searches: int = 5
    enable_search_cache: bool = True
    cache_expiry_hours: int = 24
    
    # 分析配置
    similarity_threshold: float = 0.7
    confidence_threshold: float = 0.9
    max_entity_pairs: int = 50
    
    # 错误处理配置
    wikipedia_search_retries: int = 3
    fallback_to_legacy_mode: bool = True
    log_search_failures: bool = True
    continue_on_search_error: bool = True
    
    # 性能配置
    max_processing_time_seconds: int = 300
    enable_parallel_processing: bool = True
    
    def validate_config(self) -> bool:
        """验证配置有效性"""
        if self.similarity_threshold < 0 or self.similarity_threshold > 1:
            return False
        if self.confidence_threshold < 0 or self.confidence_threshold > 1:
            return False
        if self.max_entity_pairs <= 0:
            return False
        return True