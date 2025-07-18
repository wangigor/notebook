import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class EntityLifecycleState(Enum):
    """实体生命周期状态枚举"""
    NEW = "new"           # 新创建的实体
    STABLE = "stable"     # 稳定的实体
    SUSPICIOUS = "suspicious"  # 可疑的实体（可能需要统一）
    DEPRECATED = "deprecated"  # 废弃的实体

@dataclass
class Entity:
    """实体数据类 - 统一版本支持智能实体统一
    
    这是系统中唯一的Entity定义，包含所有必要的字段和验证逻辑
    """
    id: str
    name: str
    type: str
    description: str
    properties: Dict[str, Any]
    confidence: float
    source_text: str
    start_pos: int
    end_pos: int
    
    # 扩展字段（用于图谱存储）
    chunk_neo4j_id: Optional[str] = None
    document_postgresql_id: Optional[int] = None
    document_neo4j_id: Optional[str] = None
    chunk_index: int = 0
    entity_index: int = 0
    
    # 🆕 实体统一增强字段
    aliases: List[str] = None  # 别名列表
    embedding: Optional[List[float]] = None  # 向量表示
    quality_score: float = 1.0  # 质量分数
    
    # 🆕 合并追踪字段（用于智能统一）
    merged_from: Optional[List[str]] = None  # 合并源实体ID列表
    merge_timestamp: Optional[str] = None  # 合并时间戳
    
    # 🆕 增量统一专用字段
    entity_type: Optional[str] = None  # 具体类型：公司、人物、产品等
    lifecycle_state: EntityLifecycleState = EntityLifecycleState.NEW  # 生命周期状态
    importance_score: float = 0.0  # 重要性分数
    last_unified_at: Optional[datetime] = None  # 最后统一时间
    fingerprint: Optional[str] = None  # 实体指纹
    created_at: Optional[datetime] = None  # 创建时间
    updated_at: Optional[datetime] = None  # 更新时间
    last_referenced_at: Optional[datetime] = None  # 最后引用时间
    reference_count: int = 0  # 引用计数
    relationship_count: int = 0  # 关系计数
    
    def __post_init__(self):
        """初始化后处理，确保向后兼容性和数据验证"""
        if self.aliases is None:
            self.aliases = []
        
        if self.merged_from is None:
            self.merged_from = []
        
        # 验证和清理aliases列表
        self.aliases = self._validate_and_clean_aliases(self.aliases)
        
        # 确保质量分数在合理范围内
        if self.quality_score < 0.0 or self.quality_score > 1.0:
            self.quality_score = min(1.0, max(0.0, self.quality_score))
        
        # 确保重要性分数在合理范围内
        if self.importance_score < 0.0 or self.importance_score > 1.0:
            self.importance_score = min(1.0, max(0.0, self.importance_score))
        
        # 验证embedding向量
        if self.embedding is not None:
            self.embedding = self._validate_embedding(self.embedding)
        
        # 设置默认时间戳
        current_time = datetime.now()
        if self.created_at is None:
            self.created_at = current_time
        if self.updated_at is None:
            self.updated_at = current_time
        if self.last_referenced_at is None:
            self.last_referenced_at = current_time
        
        # 如果没有指定entity_type，使用type字段
        if self.entity_type is None:
            self.entity_type = self.type
        
        # 生成指纹
        if self.fingerprint is None:
            self.fingerprint = self._generate_fingerprint()
    
    def _validate_and_clean_aliases(self, aliases: List[str]) -> List[str]:
        """验证和清理别名列表"""
        if not aliases:
            return []
        
        cleaned_aliases = []
        for alias in aliases:
            if isinstance(alias, str) and alias.strip():
                # 标准化别名
                cleaned_alias = alias.strip()
                # 避免自己成为自己的别名
                if cleaned_alias != self.name and cleaned_alias not in cleaned_aliases:
                    cleaned_aliases.append(cleaned_alias)
        
        return cleaned_aliases
    
    def _validate_embedding(self, embedding: List[float]) -> Optional[List[float]]:
        """验证embedding向量"""
        if not embedding:
            return None
        
        try:
            # 确保所有元素都是数字
            validated_embedding = [float(x) for x in embedding]
            
            # 检查向量维度（预期维度可以从配置中获取）
            from app.core.config import settings
            expected_dim = getattr(settings, 'VECTOR_SIZE', 1536)  # 默认1536维
            
            if len(validated_embedding) != expected_dim:
                logger.warning(f"Embedding维度不匹配: 期望{expected_dim}, 实际{len(validated_embedding)}")
                # 如果维度不匹配，返回None而不是抛出异常
                return None
            
            return validated_embedding
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Embedding验证失败: {str(e)}")
            return None
    
    def add_alias(self, alias: str) -> bool:
        """添加别名"""
        if alias and alias.strip() and alias != self.name:
            clean_alias = alias.strip()
            if clean_alias not in self.aliases:
                self.aliases.append(clean_alias)
                return True
        return False
    
    def get_all_names(self) -> List[str]:
        """获取所有名称（包括主名称和别名）"""
        return [self.name] + self.aliases
    
    def is_merged_entity(self) -> bool:
        """判断是否为合并后的实体"""
        return bool(self.merged_from and len(self.merged_from) > 0)
    
    def _generate_fingerprint(self) -> str:
        """生成实体指纹，用于快速变更检测"""
        import hashlib
        
        # 使用关键字段生成指纹
        fingerprint_data = f"{self.name}|{self.type}|{self.description}|{self.quality_score}|{len(self.aliases)}"
        return hashlib.md5(fingerprint_data.encode('utf-8')).hexdigest()
    
    def update_fingerprint(self) -> str:
        """更新实体指纹"""
        self.fingerprint = self._generate_fingerprint()
        self.updated_at = datetime.now()
        return self.fingerprint
    
    def has_changed(self, other_fingerprint: str) -> bool:
        """检查实体是否发生变更"""
        return self.fingerprint != other_fingerprint
    
    def calculate_completeness(self) -> float:
        """计算信息完整度"""
        total_fields = 5  # name, type, description, properties, aliases
        filled_fields = 0
        
        if self.name and self.name.strip():
            filled_fields += 1
        if self.type and self.type.strip():
            filled_fields += 1
        if self.description and self.description.strip():
            filled_fields += 1
        if self.properties and len(self.properties) > 0:
            filled_fields += 1
        if self.aliases and len(self.aliases) > 0:
            filled_fields += 1
        
        return filled_fields / total_fields
    
    def calculate_recency(self) -> float:
        """计算时效性分数"""
        from datetime import timedelta
        
        if self.last_referenced_at is None:
            return 0.0
        
        now = datetime.now()
        time_diff = now - self.last_referenced_at
        
        # 30天内的实体得分较高
        if time_diff <= timedelta(days=30):
            return 1.0 - (time_diff.days / 30.0)
        else:
            return 0.0
    
    def update_importance_score(self) -> float:
        """更新重要性分数"""
        score = 0.0
        
        # 引用频率权重 (40%)
        score += min(self.reference_count * 0.1, 0.4)
        
        # 关系丰富度权重 (30%)
        score += min(self.relationship_count * 0.05, 0.3)
        
        # 信息完整度权重 (20%)
        score += self.calculate_completeness() * 0.2
        
        # 时效性权重 (10%)
        score += self.calculate_recency() * 0.1
        
        self.importance_score = min(score, 1.0)
        return self.importance_score
    
    def update_lifecycle_state(self) -> EntityLifecycleState:
        """更新生命周期状态"""
        from datetime import timedelta
        
        now = datetime.now()
        
        # 新实体：创建时间<24h
        if self.created_at and now - self.created_at < timedelta(hours=24):
            self.lifecycle_state = EntityLifecycleState.NEW
        # 废弃实体：90天未被引用
        elif self.last_referenced_at and now - self.last_referenced_at > timedelta(days=90):
            self.lifecycle_state = EntityLifecycleState.DEPRECATED
        # 可疑实体：质量分数低或最近被修改
        elif self.quality_score < 0.6 or (self.updated_at and now - self.updated_at < timedelta(hours=1)):
            self.lifecycle_state = EntityLifecycleState.SUSPICIOUS
        else:
            self.lifecycle_state = EntityLifecycleState.STABLE
        
        return self.lifecycle_state
    
    def mark_referenced(self):
        """标记实体被引用"""
        self.reference_count += 1
        self.last_referenced_at = datetime.now()
        self.update_lifecycle_state()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'entity_type': self.entity_type,
            'description': self.description,
            'properties': self.properties,
            'confidence': self.confidence,
            'quality_score': self.quality_score,
            'importance_score': self.importance_score,
            'aliases': self.aliases,
            'merged_from': self.merged_from,
            'merge_timestamp': self.merge_timestamp,
            'lifecycle_state': self.lifecycle_state.value,
            'fingerprint': self.fingerprint,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_referenced_at': self.last_referenced_at.isoformat() if self.last_referenced_at else None,
            'last_unified_at': self.last_unified_at.isoformat() if self.last_unified_at else None,
            'reference_count': self.reference_count,
            'relationship_count': self.relationship_count
        }


@dataclass  
class Relationship:
    """关系数据类 - 统一版本"""
    id: str
    source_entity_id: str
    target_entity_id: str
    source_entity_name: str
    target_entity_name: str
    relationship_type: str
    description: str
    properties: Dict[str, Any]
    confidence: float
    source_text: str
    context: str
    
    # 扩展字段（用于图谱存储）
    chunk_neo4j_id: Optional[str] = None
    document_postgresql_id: Optional[int] = None
    document_neo4j_id: Optional[str] = None


@dataclass
class KnowledgeExtractionResult:
    """知识抽取结果"""
    entities: List[Entity]
    relationships: List[Relationship]
    chunk_id: str
    chunk_index: int
    success: bool
    error_message: Optional[str] = None 