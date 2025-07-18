# -*- coding: utf-8 -*-
"""
实体合并服务
实现智能实体合并决策和执行，包括冲突检测和解决策略
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings
from app.services.entity_similarity_service import get_entity_similarity_calculator, SimilarityResult

logger = logging.getLogger(__name__)


class MergeDecision(Enum):
    """合并决策类型"""
    AUTO_MERGE = "auto_merge"                    # 高置信度自动合并
    CONDITIONAL_MERGE = "conditional_merge"      # 中等置信度条件合并
    REJECT_MERGE = "reject_merge"               # 低置信度拒绝合并
    CONFLICT_DETECTED = "conflict_detected"      # 检测到冲突


@dataclass
class ConflictInfo:
    """冲突信息"""
    conflict_type: str
    entity1_value: Any
    entity2_value: Any
    severity: float  # 冲突严重程度 [0.0, 1.0]
    description: str


@dataclass
class MergeDecisionResult:
    """合并决策结果"""
    decision: MergeDecision
    confidence: float
    similarity_result: SimilarityResult
    conflicts: List[ConflictInfo]
    reasoning: str
    metadata: Dict[str, Any]


@dataclass
class MergedEntity:
    """合并后的实体"""
    id: str
    name: str
    type: str
    entity_type: str  # 🔧 添加缺失的entity_type属性
    description: str
    properties: Dict[str, Any]
    confidence: float
    source_text: str
    start_pos: int
    end_pos: int
    
    # 🔧 添加缺失的Neo4j相关属性
    chunk_neo4j_id: Optional[str] = None
    document_postgresql_id: Optional[int] = None
    document_neo4j_id: Optional[str] = None
    
    # 增强字段
    aliases: List[str] = None
    embedding: Optional[List[float]] = None
    quality_score: float = 0.0
    importance_score: float = 0.0  # 🔧 添加缺失的importance_score属性
    
    # 合并元信息
    merged_from: List[str] = None  # 原始实体ID列表
    merge_timestamp: str = ""
    merge_method: str = ""
    
    def __post_init__(self):
        """初始化默认值"""
        if self.aliases is None:
            self.aliases = []
        if self.merged_from is None:
            self.merged_from = []


class EntityMergeDecisionEngine:
    """
    实体合并决策引擎
    
    基于多维度相似度和冲突检测来决定是否合并实体
    """
    
    def __init__(self):
        """初始化合并决策引擎"""
        self.similarity_calculator = get_entity_similarity_calculator()
        
        # 从配置加载阈值
        self.high_threshold = settings.ENTITY_UNIFICATION_HIGH_THRESHOLD
        self.medium_threshold = settings.ENTITY_UNIFICATION_MEDIUM_THRESHOLD
        self.low_threshold = settings.ENTITY_UNIFICATION_LOW_THRESHOLD
        
        logger.info(f"实体合并决策引擎已初始化，阈值: "
                   f"高({self.high_threshold:.2f}), 中({self.medium_threshold:.2f}), 低({self.low_threshold:.2f})")
    
    async def should_merge(self, entity1, entity2) -> MergeDecisionResult:
        """
        判断两个实体是否应该合并
        
        Args:
            entity1: 第一个实体
            entity2: 第二个实体
            
        Returns:
            MergeDecisionResult: 合并决策结果
        """
        try:
            # 1. 计算相似度
            similarity_result = await self.similarity_calculator.calculate_similarity(entity1, entity2)
            total_similarity = similarity_result.total_similarity
            
            # 2. 基于相似度阈值进行初步决策
            if total_similarity >= self.high_threshold:
                initial_decision = MergeDecision.AUTO_MERGE
            elif total_similarity >= self.medium_threshold:
                initial_decision = MergeDecision.CONDITIONAL_MERGE
            elif total_similarity >= self.low_threshold:
                initial_decision = MergeDecision.REJECT_MERGE
            else:
                initial_decision = MergeDecision.REJECT_MERGE
            
            # 3. 冲突检测
            conflicts = self._detect_conflicts(entity1, entity2)
            
            # 4. 基于冲突调整决策
            final_decision, reasoning = self._adjust_decision_by_conflicts(
                initial_decision, conflicts, total_similarity
            )
            
            # 5. 计算最终置信度
            final_confidence = self._calculate_merge_confidence(
                similarity_result, conflicts, final_decision
            )
            
            result = MergeDecisionResult(
                decision=final_decision,
                confidence=final_confidence,
                similarity_result=similarity_result,
                conflicts=conflicts,
                reasoning=reasoning,
                metadata={
                    "entity1_id": entity1.id,
                    "entity2_id": entity2.id,
                    "initial_decision": initial_decision.value,
                    "conflict_count": len(conflicts),
                    "thresholds_used": {
                        "high": self.high_threshold,
                        "medium": self.medium_threshold,
                        "low": self.low_threshold
                    }
                }
            )
            
            logger.debug(f"合并决策: {entity1.name} <-> {entity2.name} = {final_decision.value} "
                        f"(相似度: {total_similarity:.3f}, 冲突: {len(conflicts)})")
            
            return result
            
        except Exception as e:
            logger.error(f"合并决策失败: {entity1.name} <-> {entity2.name}, 错误: {str(e)}")
            return MergeDecisionResult(
                decision=MergeDecision.REJECT_MERGE,
                confidence=0.0,
                similarity_result=similarity_result if 'similarity_result' in locals() else None,
                conflicts=[],
                reasoning=f"决策过程出错: {str(e)}",
                metadata={"error": str(e)}
            )
    
    def _detect_conflicts(self, entity1, entity2) -> List[ConflictInfo]:
        """
        检测实体间的冲突
        
        Args:
            entity1: 第一个实体
            entity2: 第二个实体
            
        Returns:
            冲突信息列表
        """
        conflicts = []
        
        # 1. 实体类型冲突检测
        if entity1.type != entity2.type:
            conflicts.append(ConflictInfo(
                conflict_type="type_mismatch",
                entity1_value=entity1.type,
                entity2_value=entity2.type,
                severity=0.8,  # 类型冲突是高严重性的
                description=f"实体类型不匹配: {entity1.type} vs {entity2.type}"
            ))
        
        # 2. 描述语义矛盾检测
        desc_conflict = self._detect_description_conflict(entity1, entity2)
        if desc_conflict:
            conflicts.append(desc_conflict)
        
        # 3. 属性冲突检测
        property_conflicts = self._detect_property_conflicts(entity1, entity2)
        conflicts.extend(property_conflicts)
        
        # 4. 置信度差异过大检测
        confidence_diff = abs(entity1.confidence - entity2.confidence)
        if confidence_diff > 0.4:  # 置信度差异超过40%
            conflicts.append(ConflictInfo(
                conflict_type="confidence_mismatch",
                entity1_value=entity1.confidence,
                entity2_value=entity2.confidence,
                severity=confidence_diff * 0.5,  # 根据差异程度设置严重性
                description=f"置信度差异过大: {entity1.confidence:.2f} vs {entity2.confidence:.2f}"
            ))
        
        return conflicts
    
    def _detect_description_conflict(self, entity1, entity2) -> Optional[ConflictInfo]:
        """检测描述语义矛盾"""
        desc1 = getattr(entity1, 'description', '') or ''
        desc2 = getattr(entity2, 'description', '') or ''
        
        if not desc1 or not desc2:
            return None
        
        # 简单的矛盾词检测
        contradiction_pairs = [
            ("男", "女"), ("male", "female"),
            ("老", "年轻"), ("old", "young"),
            ("大", "小"), ("big", "small"),
            ("是", "不是"), ("正确", "错误"),
            ("存在", "不存在"), ("真", "假")
        ]
        
        desc1_lower = desc1.lower()
        desc2_lower = desc2.lower()
        
        for word1, word2 in contradiction_pairs:
            if (word1 in desc1_lower and word2 in desc2_lower) or \
               (word2 in desc1_lower and word1 in desc2_lower):
                return ConflictInfo(
                    conflict_type="description_contradiction",
                    entity1_value=desc1,
                    entity2_value=desc2,
                    severity=0.6,
                    description=f"描述中发现矛盾词汇: {word1} vs {word2}"
                )
        
        return None
    
    def _detect_property_conflicts(self, entity1, entity2) -> List[ConflictInfo]:
        """检测属性冲突"""
        conflicts = []
        
        props1 = getattr(entity1, 'properties', {}) or {}
        props2 = getattr(entity2, 'properties', {}) or {}
        
        # 检查共同属性的值冲突
        common_keys = set(props1.keys()).intersection(set(props2.keys()))
        
        for key in common_keys:
            value1 = props1[key]
            value2 = props2[key]
            
            # 跳过相同值
            if value1 == value2:
                continue
            
            # 检测数值类型的显著差异
            if isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
                if value1 != 0 and value2 != 0:
                    diff_ratio = abs(value1 - value2) / max(abs(value1), abs(value2))
                    if diff_ratio > 0.5:  # 差异超过50%
                        conflicts.append(ConflictInfo(
                            conflict_type="property_value_mismatch",
                            entity1_value=value1,
                            entity2_value=value2,
                            severity=min(diff_ratio, 1.0),
                            description=f"属性 {key} 数值差异过大: {value1} vs {value2}"
                        ))
            
            # 检测字符串类型的冲突
            elif isinstance(value1, str) and isinstance(value2, str):
                if len(value1) > 0 and len(value2) > 0 and value1.lower() != value2.lower():
                    conflicts.append(ConflictInfo(
                        conflict_type="property_value_mismatch",
                        entity1_value=value1,
                        entity2_value=value2,
                        severity=0.4,
                        description=f"属性 {key} 字符串值不匹配: {value1} vs {value2}"
                    ))
        
        return conflicts
    
    def _adjust_decision_by_conflicts(self, initial_decision: MergeDecision, 
                                    conflicts: List[ConflictInfo], 
                                    similarity: float) -> Tuple[MergeDecision, str]:
        """
        基于冲突调整合并决策
        
        Args:
            initial_decision: 初始决策
            conflicts: 冲突列表
            similarity: 相似度分数
            
        Returns:
            (最终决策, 推理说明)
        """
        if not conflicts:
            return initial_decision, f"无冲突，基于相似度({similarity:.3f})的初始决策"
        
        # 计算总冲突严重程度
        total_conflict_severity = sum(conflict.severity for conflict in conflicts)
        avg_conflict_severity = total_conflict_severity / len(conflicts)
        
        # 检查是否有严重冲突（类型不匹配等）
        has_critical_conflict = any(
            conflict.conflict_type == "type_mismatch" and conflict.severity > 0.7
            for conflict in conflicts
        )
        
        if has_critical_conflict:
            return MergeDecision.CONFLICT_DETECTED, f"检测到严重类型冲突，拒绝合并"
        
        # 基于平均冲突严重程度调整决策
        if avg_conflict_severity > 0.6:
            if initial_decision == MergeDecision.AUTO_MERGE:
                return MergeDecision.CONDITIONAL_MERGE, f"高冲突严重度({avg_conflict_severity:.2f})，降级为条件合并"
            elif initial_decision == MergeDecision.CONDITIONAL_MERGE:
                return MergeDecision.REJECT_MERGE, f"高冲突严重度({avg_conflict_severity:.2f})，拒绝合并"
        elif avg_conflict_severity > 0.3:
            if initial_decision == MergeDecision.AUTO_MERGE:
                return MergeDecision.CONDITIONAL_MERGE, f"中等冲突严重度({avg_conflict_severity:.2f})，降级为条件合并"
        
        return initial_decision, f"冲突严重度较低({avg_conflict_severity:.2f})，保持初始决策"
    
    def _calculate_merge_confidence(self, similarity_result: SimilarityResult, 
                                  conflicts: List[ConflictInfo], 
                                  decision: MergeDecision) -> float:
        """计算合并决策的置信度"""
        base_confidence = similarity_result.confidence
        
        # 基于冲突调整置信度
        if conflicts:
            conflict_penalty = sum(conflict.severity for conflict in conflicts) / len(conflicts)
            adjusted_confidence = base_confidence * (1.0 - conflict_penalty * 0.5)
        else:
            adjusted_confidence = base_confidence
        
        # 基于决策类型调整置信度
        decision_multiplier = {
            MergeDecision.AUTO_MERGE: 1.0,
            MergeDecision.CONDITIONAL_MERGE: 0.8,
            MergeDecision.REJECT_MERGE: 0.3,
            MergeDecision.CONFLICT_DETECTED: 0.1
        }
        
        final_confidence = adjusted_confidence * decision_multiplier.get(decision, 0.5)
        
        return max(0.0, min(1.0, final_confidence))


class EntityMerger:
    """
    实体合并执行器
    
    执行实际的实体合并操作，包括属性合并和质量评估
    """
    
    def __init__(self):
        """初始化实体合并器"""
        logger.info("实体合并执行器已初始化")
    
    def merge_entities(self, primary_entity, secondary_entity, 
                      merge_decision: MergeDecisionResult) -> MergedEntity:
        """
        执行实体合并
        
        Args:
            primary_entity: 主实体（保留其ID和主要属性）
            secondary_entity: 次要实体（将其信息合并到主实体）
            merge_decision: 合并决策结果
            
        Returns:
            MergedEntity: 合并后的实体
        """
        try:
            import datetime
            
            # 1. 选择主实体（置信度更高的作为主实体）
            if secondary_entity.confidence > primary_entity.confidence:
                primary_entity, secondary_entity = secondary_entity, primary_entity
            
            # 2. 合并基本属性
            merged_name = self._merge_names(primary_entity, secondary_entity)
            merged_type = self._merge_types(primary_entity, secondary_entity)
            merged_description = self._merge_descriptions(primary_entity, secondary_entity)
            merged_properties = self._merge_properties(primary_entity, secondary_entity)
            
            # 3. 合并增强字段
            merged_aliases = self._merge_aliases(primary_entity, secondary_entity)
            merged_embedding = self._select_best_embedding(primary_entity, secondary_entity)
            
            # 4. 计算合并后的质量分数
            merged_quality = self._calculate_merged_quality(
                primary_entity, secondary_entity, merge_decision
            )
            
            # 5. 选择最佳的位置信息
            merged_start_pos, merged_end_pos = self._merge_positions(primary_entity, secondary_entity)
            
            # 6. 合并源文本
            merged_source_text = self._merge_source_texts(primary_entity, secondary_entity)
            
            # 7. 创建合并后的实体
            merged_entity = MergedEntity(
                id=primary_entity.id,  # 保持主实体的ID
                name=merged_name,
                type=merged_type,
                entity_type=getattr(primary_entity, 'entity_type', merged_type),  # 🔧 添加entity_type
                description=merged_description,
                properties=merged_properties,
                confidence=max(primary_entity.confidence, secondary_entity.confidence),
                source_text=merged_source_text,
                start_pos=merged_start_pos,
                end_pos=merged_end_pos,
                chunk_neo4j_id=getattr(primary_entity, 'chunk_neo4j_id', None),  # 🔧 添加Neo4j相关属性
                document_postgresql_id=getattr(primary_entity, 'document_postgresql_id', None),
                document_neo4j_id=getattr(primary_entity, 'document_neo4j_id', None),
                aliases=merged_aliases,
                embedding=merged_embedding,
                quality_score=merged_quality,
                importance_score=max(getattr(primary_entity, 'importance_score', 0.0), getattr(secondary_entity, 'importance_score', 0.0)),  # 🔧 添加importance_score
                merged_from=[primary_entity.id, secondary_entity.id],
                merge_timestamp=datetime.datetime.now().isoformat(),
                merge_method="intelligent_similarity_based"
            )
            
            logger.debug(f"实体合并完成: {primary_entity.name} + {secondary_entity.name} -> {merged_name}")
            
            return merged_entity
            
        except Exception as e:
            logger.error(f"实体合并失败: {str(e)}")
            raise
    
    def _merge_names(self, entity1, entity2) -> str:
        """合并实体名称（选择更短且更常见的）"""
        name1, name2 = entity1.name, entity2.name
        
        # 优先选择更短的名称（通常是更简洁的表达）
        if len(name1) <= len(name2):
            return name1
        else:
            return name2
    
    def _merge_types(self, entity1, entity2) -> str:
        """合并实体类型（选择置信度更高的实体的类型）"""
        if entity1.confidence >= entity2.confidence:
            return entity1.type
        else:
            return entity2.type
    
    def _merge_descriptions(self, entity1, entity2) -> str:
        """合并描述信息"""
        desc1 = getattr(entity1, 'description', '') or ''
        desc2 = getattr(entity2, 'description', '') or ''
        
        if not desc1:
            return desc2
        if not desc2:
            return desc1
        
        # 选择更详细的描述
        if len(desc1) >= len(desc2):
            return desc1
        else:
            return desc2
    
    def _merge_properties(self, entity1, entity2) -> Dict[str, Any]:
        """合并属性信息"""
        props1 = getattr(entity1, 'properties', {}) or {}
        props2 = getattr(entity2, 'properties', {}) or {}
        
        merged_props = props1.copy()
        
        # 合并属性，优先保留entity1的值，添加entity2的新属性
        for key, value in props2.items():
            if key not in merged_props:
                merged_props[key] = value
            elif isinstance(value, list) and isinstance(merged_props[key], list):
                # 合并列表类型属性
                merged_list = list(set(merged_props[key] + value))
                merged_props[key] = merged_list
        
        # 添加合并元信息
        merged_props['merged_from_entities'] = [entity1.id, entity2.id]
        merged_props['merge_source_confidences'] = [entity1.confidence, entity2.confidence]
        
        return merged_props
    
    def _merge_aliases(self, entity1, entity2) -> List[str]:
        """合并别名列表"""
        aliases1 = getattr(entity1, 'aliases', []) or []
        aliases2 = getattr(entity2, 'aliases', []) or []
        
        # 收集所有可能的名称
        all_names = set()
        all_names.add(entity1.name)
        all_names.add(entity2.name)
        all_names.update(aliases1)
        all_names.update(aliases2)
        
        # 确定主名称（合并后实体的名称）
        primary_name = self._merge_names(entity1, entity2)
        
        # 移除主名称，剩下的作为别名
        all_names.discard(primary_name)
        
        # 转换为列表并限制数量
        merged_aliases = list(all_names)
        
        # 限制别名数量，避免过多
        max_aliases = settings.ENTITY_ALIAS_MAX_COUNT
        if len(merged_aliases) > max_aliases:
            # 按长度排序，保留较短的别名（通常更常用）
            merged_aliases = sorted(merged_aliases, key=len)[:max_aliases]
        
        return merged_aliases
    
    def _select_best_embedding(self, entity1, entity2) -> Optional[List[float]]:
        """选择最佳的embedding向量"""
        embedding1 = getattr(entity1, 'embedding', None)
        embedding2 = getattr(entity2, 'embedding', None)
        
        if embedding1 is None:
            return embedding2
        if embedding2 is None:
            return embedding1
        
        # 选择置信度更高的实体的embedding
        if entity1.confidence >= entity2.confidence:
            return embedding1
        else:
            return embedding2
    
    def _calculate_merged_quality(self, entity1, entity2, 
                                merge_decision: MergeDecisionResult) -> float:
        """计算合并后的质量分数"""
        quality1 = getattr(entity1, 'quality_score', 0.8)
        quality2 = getattr(entity2, 'quality_score', 0.8)
        
        # 基础质量分数（加权平均）
        conf1, conf2 = entity1.confidence, entity2.confidence
        total_conf = conf1 + conf2
        
        if total_conf > 0:
            base_quality = (quality1 * conf1 + quality2 * conf2) / total_conf
        else:
            base_quality = (quality1 + quality2) / 2
        
        # 基于合并决策调整质量分数
        decision_bonus = {
            MergeDecision.AUTO_MERGE: 0.1,      # 高置信度合并，质量加分
            MergeDecision.CONDITIONAL_MERGE: 0.05,  # 条件合并，小幅加分
            MergeDecision.REJECT_MERGE: -0.1,   # 不应该合并但被强制合并，减分
            MergeDecision.CONFLICT_DETECTED: -0.2   # 有冲突的合并，大幅减分
        }
        
        bonus = decision_bonus.get(merge_decision.decision, 0.0)
        final_quality = base_quality + bonus
        
        return max(0.0, min(1.0, final_quality))
    
    def _merge_positions(self, entity1, entity2) -> Tuple[int, int]:
        """合并位置信息（选择更准确的位置）"""
        # 简单策略：选择置信度更高的实体的位置
        if entity1.confidence >= entity2.confidence:
            return entity1.start_pos, entity1.end_pos
        else:
            return entity2.start_pos, entity2.end_pos
    
    def _merge_source_texts(self, entity1, entity2) -> str:
        """合并源文本（选择更长的或者置信度更高的）"""
        text1 = getattr(entity1, 'source_text', '') or ''
        text2 = getattr(entity2, 'source_text', '') or ''
        
        if not text1:
            return text2
        if not text2:
            return text1
        
        # 选择更详细的源文本
        if len(text1) >= len(text2):
            return text1
        else:
            return text2


# 🆕 集成接口
_merge_decision_engine_instance = None
_entity_merger_instance = None

def get_merge_decision_engine() -> EntityMergeDecisionEngine:
    """获取合并决策引擎实例（单例模式）"""
    global _merge_decision_engine_instance
    if _merge_decision_engine_instance is None:
        _merge_decision_engine_instance = EntityMergeDecisionEngine()
    return _merge_decision_engine_instance

def get_entity_merger() -> EntityMerger:
    """获取实体合并器实例（单例模式）"""
    global _entity_merger_instance
    if _entity_merger_instance is None:
        _entity_merger_instance = EntityMerger()
    return _entity_merger_instance 