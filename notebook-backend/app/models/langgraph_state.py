# -*- coding: utf-8 -*-
"""
LangGraph兼容的状态定义
用于实体去重Agent的状态管理（工具调用版本）
"""
from typing import Dict, List, Any, Optional, TypedDict, Literal
from typing_extensions import Annotated
from datetime import datetime

# LangGraph状态定义（使用TypedDict）
class EntityDeduplicationState(TypedDict):
    """实体去重Agent的状态（工具调用增强版）"""
    
    # === 输入数据 ===
    entities: List[Dict[str, Any]]  # 原始实体列表
    entity_type: str  # 实体类型
    
    # === 向量预筛选阶段 ===
    prescreened_pairs: List[Dict[str, Any]]  # 预筛选的实体对
    prescreening_threshold: float  # 预筛选阈值
    prescreening_stats: Dict[str, Any]  # 预筛选统计
    
    # === 智能分析阶段（包含工具调用） ===
    analysis_messages: List[Dict[str, Any]]  # LLM对话消息
    analysis_result: Optional[Dict[str, Any]]  # 最终分析结果
    entity_pairs: List[Dict[str, Any]]  # 分析后的实体对
    
    # === 工具调用相关 ===
    tool_calls_made: List[Dict[str, Any]]  # 执行的工具调用
    tool_results: List[Dict[str, Any]]  # 工具执行结果
    reasoning_steps: List[str]  # 推理步骤记录
    
    # === 最终决策阶段 ===
    final_decision_result: Optional[Dict[str, Any]]  # 最终决策结果
    merge_groups: List[Dict[str, Any]]  # 合并组
    independent_entities: List[int]  # 独立实体索引
    uncertain_cases: List[Dict[str, Any]]  # 不确定案例
    
    # === 流程控制 ===
    current_step: Literal[
        "start", "vector_prescreening", "intelligent_analysis", 
        "final_decision", "completed", "error"
    ]
    step_history: List[str]  # 步骤历史
    
    # === 性能和质量指标 ===
    started_at: Optional[datetime]
    processing_time: float
    total_entities: int
    pairs_analyzed: int
    
    # === 错误处理 ===
    errors: List[str]  # 错误列表
    warnings: List[str]  # 警告列表
    retry_count: int  # 重试次数
    
    # === 配置选项 ===
    config: Dict[str, Any]  # Agent配置


class EntityPairState(TypedDict):
    """单个实体对的状态"""
    entity1_index: int
    entity2_index: int
    entity1_name: str
    entity2_name: str
    vector_similarity: float  # 向量相似度
    llm_confidence: Literal["high", "medium", "low"]  # LLM置信度
    similarity_score: float  # 综合相似度分数
    reason: str  # 分析原因
    needs_verification: bool  # 是否需要验证
    wikipedia_verified: bool  # 是否已Wikipedia验证
    verification_result: Optional[Dict[str, Any]]  # 验证结果


class WikipediaSearchState(TypedDict):
    """Wikipedia搜索状态"""
    entity_name: str
    entity_index: int
    search_query: str
    found: bool
    title: Optional[str]
    summary: Optional[str]
    url: Optional[str]
    categories: List[str]
    entity_type: Optional[str]
    type_relevance: float
    disambiguation: bool
    options: List[str]
    error: Optional[str]
    search_timestamp: Optional[datetime]


class MergeDecisionState(TypedDict):
    """合并决策状态"""
    primary_entity_index: int
    duplicate_indices: List[int]
    merged_name: str
    merged_description: str
    confidence: float  # 0.0 - 1.0
    reason: str
    wikipedia_evidence: Optional[str]
    llm_reasoning: Optional[str]
    vector_support: float  # 向量相似度支持度
    final_verification: bool  # 是否通过最终验证


# === 状态更新函数 ===

def create_initial_state(entities: List[Dict[str, Any]], entity_type: str, config: Dict[str, Any]) -> EntityDeduplicationState:
    """创建初始状态"""
    return EntityDeduplicationState(
        # 输入数据
        entities=entities,
        entity_type=entity_type,
        
        # 向量预筛选阶段
        prescreened_pairs=[],
        prescreening_threshold=config.get("prescreening_threshold", 0.4),
        prescreening_stats={},
        
        # 智能分析阶段（包含工具调用）
        analysis_messages=[],
        analysis_result=None,
        entity_pairs=[],
        
        # 工具调用相关
        tool_calls_made=[],
        tool_results=[],
        reasoning_steps=[],
        
        # 最终决策阶段
        final_decision_result=None,
        merge_groups=[],
        independent_entities=[],
        uncertain_cases=[],
        
        # 流程控制
        current_step="start",
        step_history=[],
        
        # 性能和质量指标
        started_at=datetime.now(),
        processing_time=0.0,
        total_entities=len(entities),
        pairs_analyzed=0,
        
        # 错误处理
        errors=[],
        warnings=[],
        retry_count=0,
        
        # 配置选项
        config=config
    )


def update_step(state: EntityDeduplicationState, new_step: str) -> EntityDeduplicationState:
    """更新处理步骤"""
    state["step_history"].append(state["current_step"])
    state["current_step"] = new_step
    return state


def add_error(state: EntityDeduplicationState, error: str) -> EntityDeduplicationState:
    """添加错误"""
    state["errors"].append(error)
    if state["current_step"] != "error":
        state = update_step(state, "error")
    return state


def add_warning(state: EntityDeduplicationState, warning: str) -> EntityDeduplicationState:
    """添加警告"""
    state["warnings"].append(warning)
    return state


def calculate_processing_time(state: EntityDeduplicationState) -> EntityDeduplicationState:
    """计算处理时间"""
    if state["started_at"]:
        state["processing_time"] = (datetime.now() - state["started_at"]).total_seconds()
    return state


# === 状态验证函数 ===

def validate_state(state: EntityDeduplicationState) -> List[str]:
    """验证状态完整性"""
    errors = []
    
    # 检查必要字段
    if not state.get("entities"):
        errors.append("entities字段为空")
    
    if not state.get("entity_type"):
        errors.append("entity_type字段为空")
    
    # 检查步骤一致性
    current_step = state.get("current_step")
    if current_step == "llm_analysis" and not state.get("prescreened_pairs"):
        errors.append("LLM分析阶段但缺少预筛选结果")
    
    if current_step == "wikipedia_search" and not state.get("entity_pairs"):
        errors.append("Wikipedia搜索阶段但缺少实体对")
    
    if current_step == "final_decision" and not state.get("search_results"):
        errors.append("最终决策阶段但缺少搜索结果")
    
    return errors


# === 辅助函数 ===

def get_entity_by_index(state: EntityDeduplicationState, index: int) -> Optional[Dict[str, Any]]:
    """根据索引获取实体"""
    if 0 <= index < len(state["entities"]):
        return state["entities"][index]
    return None


def get_processing_summary(state: EntityDeduplicationState) -> Dict[str, Any]:
    """获取处理摘要"""
    return {
        "total_entities": state["total_entities"],
        "pairs_analyzed": state["pairs_analyzed"],
        "searches_performed": state["searches_performed"],
        "merge_groups_count": len(state["merge_groups"]),
        "independent_entities_count": len(state["independent_entities"]),
        "processing_time": state["processing_time"],
        "current_step": state["current_step"],
        "errors_count": len(state["errors"]),
        "warnings_count": len(state["warnings"]),
        "steps_completed": len(state["step_history"])
    }