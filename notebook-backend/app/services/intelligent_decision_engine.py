# -*- coding: utf-8 -*-
"""
智能决策引擎
为自主实体去重Agent提供强化的决策能力
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """置信度级别"""
    VERY_HIGH = "very_high"  # 0.95+
    HIGH = "high"           # 0.85-0.95
    MEDIUM = "medium"       # 0.70-0.85
    LOW = "low"            # 0.50-0.70
    VERY_LOW = "very_low"  # <0.50


class DecisionType(Enum):
    """决策类型"""
    MERGE = "merge"
    KEEP_SEPARATE = "keep_separate"
    NEED_MORE_INFO = "need_more_info"
    UNCERTAIN = "uncertain"


@dataclass
class EntityPair:
    """实体对"""
    entity1_index: int
    entity2_index: int
    entity1_name: str
    entity2_name: str
    entity1_type: str
    entity2_type: str
    vector_similarity: float = 0.0
    description1: str = ""
    description2: str = ""


@dataclass
class DecisionResult:
    """决策结果"""
    decision: DecisionType
    confidence: float
    reasoning: str
    evidence: List[str]
    need_verification: bool = False
    suggested_tools: List[str] = None


class IntelligentDecisionEngine:
    """
    智能决策引擎
    
    提供基于多维度分析的智能决策能力：
    1. 语义分析
    2. 常识推理
    3. 证据评估
    4. 风险评估
    """
    
    def __init__(self):
        """初始化决策引擎"""
        self.decision_rules = self._load_decision_rules()
        self.entity_patterns = self._load_entity_patterns()
        self.risk_factors = self._load_risk_factors()
    
    def analyze_entity_pair(self, pair: EntityPair) -> DecisionResult:
        """
        分析实体对并做出智能决策
        
        Args:
            pair: 实体对
            
        Returns:
            决策结果
        """
        logger.debug(f"分析实体对: {pair.entity1_name} vs {pair.entity2_name}")
        
        # 多维度分析
        semantic_score = self._analyze_semantic_similarity(pair)
        pattern_score = self._analyze_pattern_matching(pair)
        risk_score = self._analyze_risk_factors(pair)
        context_score = self._analyze_context_similarity(pair)
        
        # 综合决策
        overall_confidence = self._calculate_overall_confidence(
            semantic_score, pattern_score, risk_score, context_score
        )
        
        decision = self._make_decision(overall_confidence, risk_score, pair)
        
        return DecisionResult(
            decision=decision.decision,
            confidence=overall_confidence,
            reasoning=decision.reasoning,
            evidence=decision.evidence,
            need_verification=decision.need_verification,
            suggested_tools=decision.suggested_tools
        )
    
    def _analyze_semantic_similarity(self, pair: EntityPair) -> float:
        """分析语义相似度"""
        name1, name2 = pair.entity1_name.lower(), pair.entity2_name.lower()
        
        # 完全匹配
        if name1 == name2:
            return 1.0
        
        # 简单的语义相似度分析
        similarity = 0.0
        
        # 检查包含关系
        if name1 in name2 or name2 in name1:
            similarity += 0.6
        
        # 检查关键词重叠
        words1 = set(name1.split())
        words2 = set(name2.split())
        if words1 and words2:
            overlap = len(words1 & words2) / len(words1 | words2)
            similarity += overlap * 0.4
        
        # 向量相似度权重
        if pair.vector_similarity > 0:
            similarity = (similarity + pair.vector_similarity) / 2
        
        return min(similarity, 1.0)
    
    def _analyze_pattern_matching(self, pair: EntityPair) -> float:
        """分析模式匹配"""
        score = 0.0
        
        # 检查常见的实体模式
        patterns = self.entity_patterns.get(pair.entity1_type, [])
        
        for pattern in patterns:
            if pattern["type"] == "abbreviation":
                if self._is_abbreviation_match(pair.entity1_name, pair.entity2_name):
                    score += 0.8
            elif pattern["type"] == "translation":
                if self._is_translation_match(pair.entity1_name, pair.entity2_name):
                    score += 0.9
            elif pattern["type"] == "variation":
                if self._is_name_variation(pair.entity1_name, pair.entity2_name):
                    score += 0.6
        
        return min(score, 1.0)
    
    def _analyze_risk_factors(self, pair: EntityPair) -> float:
        """分析风险因素（风险越高，合并越危险）"""
        risk = 0.0
        
        # 检查竞争对手风险
        if self._are_competitors(pair.entity1_name, pair.entity2_name, pair.entity1_type):
            risk += 0.9
        
        # 检查不同类别风险
        if pair.entity1_type != pair.entity2_type:
            risk += 0.5
        
        # 检查常见混淆风险
        if self._are_commonly_confused(pair.entity1_name, pair.entity2_name):
            risk += 0.7
        
        # 检查描述冲突
        if pair.description1 and pair.description2:
            if self._descriptions_conflict(pair.description1, pair.description2):
                risk += 0.6
        
        return min(risk, 1.0)
    
    def _analyze_context_similarity(self, pair: EntityPair) -> float:
        """分析上下文相似度"""
        if not pair.description1 or not pair.description2:
            return 0.0
        
        # 简单的上下文相似度分析
        desc1_words = set(pair.description1.lower().split())
        desc2_words = set(pair.description2.lower().split())
        
        if desc1_words and desc2_words:
            overlap = len(desc1_words & desc2_words) / len(desc1_words | desc2_words)
            return overlap
        
        return 0.0
    
    def _calculate_overall_confidence(self, semantic: float, pattern: float, 
                                    risk: float, context: float) -> float:
        """计算综合置信度"""
        # 加权计算
        weights = {
            "semantic": 0.4,
            "pattern": 0.3,
            "context": 0.2,
            "risk_penalty": 0.1
        }
        
        confidence = (
            semantic * weights["semantic"] +
            pattern * weights["pattern"] +
            context * weights["context"]
        )
        
        # 风险惩罚
        risk_penalty = risk * weights["risk_penalty"]
        confidence = max(0.0, confidence - risk_penalty)
        
        return confidence
    
    def _make_decision(self, confidence: float, risk: float, pair: EntityPair) -> DecisionResult:
        """做出最终决策"""
        evidence = []
        reasoning_parts = []
        need_verification = False
        suggested_tools = []
        
        # 基于置信度和风险做决策
        if confidence >= 0.95 and risk < 0.3:
            decision = DecisionType.MERGE
            reasoning_parts.append(f"高置信度({confidence:.2f})且低风险({risk:.2f})")
            evidence.append("语义高度相似")
        
        elif confidence >= 0.80 and risk < 0.5:
            # 需要验证的候选
            decision = DecisionType.NEED_MORE_INFO
            reasoning_parts.append(f"中高置信度({confidence:.2f})但需要验证")
            need_verification = True
            suggested_tools = ["search_wikipedia_entity"]
            evidence.append("可能相同，建议验证")
        
        elif risk >= 0.7:
            decision = DecisionType.KEEP_SEPARATE
            reasoning_parts.append(f"高风险({risk:.2f})，保守保持独立")
            evidence.append("存在高风险因素")
        
        elif confidence < 0.5:
            decision = DecisionType.KEEP_SEPARATE
            reasoning_parts.append(f"低置信度({confidence:.2f})")
            evidence.append("相似度不足")
        
        else:
            decision = DecisionType.UNCERTAIN
            reasoning_parts.append(f"中等置信度({confidence:.2f})和风险({risk:.2f})")
            evidence.append("需要人工判断")
        
        reasoning = " | ".join(reasoning_parts)
        
        return DecisionResult(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            evidence=evidence,
            need_verification=need_verification,
            suggested_tools=suggested_tools
        )
    
    def _is_abbreviation_match(self, name1: str, name2: str) -> bool:
        """检查是否为缩写匹配"""
        # 简单的缩写检查
        short_name = name1 if len(name1) < len(name2) else name2
        long_name = name2 if len(name1) < len(name2) else name1
        
        if len(short_name) <= 5 and len(long_name) > len(short_name):
            # 检查是否为首字母缩写
            initials = ''.join([word[0].upper() for word in long_name.split() if word])
            return short_name.upper() == initials
        
        return False
    
    def _is_translation_match(self, name1: str, name2: str) -> bool:
        """检查是否为翻译匹配"""
        # 这里可以加入更复杂的翻译检查逻辑
        translation_pairs = {
            "苹果公司": ["apple", "apple inc", "apple corporation"],
            "微软": ["microsoft", "microsoft corporation"],
            "谷歌": ["google", "alphabet", "alphabet inc"],
            # 可以扩展更多翻译对
        }
        
        for cn_name, en_names in translation_pairs.items():
            if (cn_name in name1.lower() and any(en in name2.lower() for en in en_names)) or \
               (cn_name in name2.lower() and any(en in name1.lower() for en in en_names)):
                return True
        
        return False
    
    def _is_name_variation(self, name1: str, name2: str) -> bool:
        """检查是否为名称变体"""
        # 移除常见的公司后缀
        suffixes = ["inc", "corp", "corporation", "ltd", "limited", "co", "company", "公司", "集团"]
        
        clean_name1 = name1.lower()
        clean_name2 = name2.lower()
        
        for suffix in suffixes:
            clean_name1 = clean_name1.replace(suffix, "").strip()
            clean_name2 = clean_name2.replace(suffix, "").strip()
        
        return clean_name1 == clean_name2
    
    def _are_competitors(self, name1: str, name2: str, entity_type: str) -> bool:
        """检查是否为竞争对手"""
        # 已知的竞争对手组
        competitor_groups = {
            "technology": [
                ["apple", "microsoft", "google", "amazon", "meta"],
                ["intel", "amd", "nvidia"],
                ["samsung", "lg", "sony"]
            ],
            "automotive": [
                ["tesla", "ford", "gm", "toyota", "volkswagen"]
            ],
            "ecommerce": [
                ["amazon", "alibaba", "ebay", "walmart"]
            ]
        }
        
        groups = competitor_groups.get(entity_type.lower(), [])
        
        for group in groups:
            name1_in_group = any(comp in name1.lower() for comp in group)
            name2_in_group = any(comp in name2.lower() for comp in group)
            if name1_in_group and name2_in_group:
                return True
        
        return False
    
    def _are_commonly_confused(self, name1: str, name2: str) -> bool:
        """检查是否为常见混淆实体"""
        # 常见混淆对
        confusion_pairs = [
            ("apple", "apple music"),  # 公司 vs 产品
            ("google", "google search"),  # 公司 vs 产品
            ("microsoft", "microsoft office"),  # 公司 vs 产品
        ]
        
        for pair in confusion_pairs:
            if (pair[0] in name1.lower() and pair[1] in name2.lower()) or \
               (pair[1] in name1.lower() and pair[0] in name2.lower()):
                return True
        
        return False
    
    def _descriptions_conflict(self, desc1: str, desc2: str) -> bool:
        """检查描述是否冲突"""
        # 简单的冲突检查
        conflict_keywords = [
            ("competitor", "rival"),
            ("different", "separate"),
            ("founded in", "established in")  # 不同创立时间可能表示不同实体
        ]
        
        for keyword_pair in conflict_keywords:
            if keyword_pair[0] in desc1.lower() and keyword_pair[1] in desc2.lower():
                return True
        
        return False
    
    def _load_decision_rules(self) -> Dict[str, Any]:
        """加载决策规则"""
        return {
            "merge_threshold": 0.85,
            "risk_threshold": 0.7,
            "verification_threshold": 0.6
        }
    
    def _load_entity_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """加载实体模式"""
        return {
            "组织": [
                {"type": "abbreviation", "weight": 0.8},
                {"type": "translation", "weight": 0.9},
                {"type": "variation", "weight": 0.6}
            ],
            "人物": [
                {"type": "variation", "weight": 0.7},
                {"type": "translation", "weight": 0.8}
            ],
            "产品": [
                {"type": "variation", "weight": 0.6},
                {"type": "version", "weight": 0.5}
            ]
        }
    
    def _load_risk_factors(self) -> Dict[str, float]:
        """加载风险因子"""
        return {
            "competitor_risk": 0.9,
            "type_mismatch_risk": 0.5,
            "confusion_risk": 0.7,
            "description_conflict_risk": 0.6
        }


# 全局实例
_decision_engine_instance = None

def get_intelligent_decision_engine() -> IntelligentDecisionEngine:
    """获取智能决策引擎实例（单例模式）"""
    global _decision_engine_instance
    if _decision_engine_instance is None:
        _decision_engine_instance = IntelligentDecisionEngine()
    return _decision_engine_instance