# -*- coding: utf-8 -*-
"""
实体指纹工具
实现实体指纹生成、比较和变更检测功能
"""
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from app.models.entity import Entity
from app.core.config import settings

logger = logging.getLogger(__name__)


class FingerprintType(Enum):
    """指纹类型枚举"""
    BASIC = "basic"           # 基础指纹（名称+类型）
    EXTENDED = "extended"     # 扩展指纹（包含描述+属性）
    SEMANTIC = "semantic"     # 语义指纹（包含embedding）
    FULL = "full"            # 完整指纹（所有字段）


class FingerprintAlgorithm(Enum):
    """指纹算法枚举"""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    XXHASH = "xxhash"


@dataclass
class FingerprintResult:
    """指纹结果"""
    fingerprint: str
    algorithm: FingerprintAlgorithm
    fingerprint_type: FingerprintType
    components: Dict[str, Any]
    created_at: datetime
    

@dataclass
class FingerprintComparison:
    """指纹比较结果"""
    is_identical: bool
    similarity_score: float
    changed_components: List[str]
    change_details: Dict[str, Any]
    

class EntityFingerprintUtil:
    """实体指纹工具类"""
    
    def __init__(self, 
                 algorithm: FingerprintAlgorithm = FingerprintAlgorithm.MD5,
                 default_type: FingerprintType = FingerprintType.EXTENDED):
        self.algorithm = algorithm
        self.default_type = default_type
        self.fingerprint_cache: Dict[str, FingerprintResult] = {}
        self.comparison_cache: Dict[str, FingerprintComparison] = {}
        
        logger.info(f"Initialized EntityFingerprintUtil with algorithm: {algorithm}, type: {default_type}")
        
    def generate_fingerprint(self, 
                           entity: Entity, 
                           fingerprint_type: Optional[FingerprintType] = None,
                           algorithm: Optional[FingerprintAlgorithm] = None) -> FingerprintResult:
        """生成实体指纹"""
        fp_type = fingerprint_type or self.default_type
        fp_algorithm = algorithm or self.algorithm
        
        # 检查缓存
        cache_key = f"{entity.id}_{fp_type.value}_{fp_algorithm.value}"
        if cache_key in self.fingerprint_cache:
            cached_result = self.fingerprint_cache[cache_key]
            # 检查实体是否已更新
            if entity.updated_at and entity.updated_at <= cached_result.created_at:
                return cached_result
                
        # 生成指纹组件
        components = self._extract_components(entity, fp_type)
        
        # 生成指纹字符串
        fingerprint_data = self._serialize_components(components)
        fingerprint = self._hash_data(fingerprint_data, fp_algorithm)
        
        # 创建结果
        result = FingerprintResult(
            fingerprint=fingerprint,
            algorithm=fp_algorithm,
            fingerprint_type=fp_type,
            components=components,
            created_at=datetime.now()
        )
        
        # 缓存结果
        self.fingerprint_cache[cache_key] = result
        
        return result
        
    def _extract_components(self, entity: Entity, fingerprint_type: FingerprintType) -> Dict[str, Any]:
        """提取指纹组件"""
        components = {}
        
        if fingerprint_type == FingerprintType.BASIC:
            components = {
                'name': self._normalize_text(entity.name),
                'type': entity.type,
                'entity_type': entity.entity_type
            }
            
        elif fingerprint_type == FingerprintType.EXTENDED:
            components = {
                'name': self._normalize_text(entity.name),
                'type': entity.type,
                'entity_type': entity.entity_type,
                'description': self._normalize_text(entity.description) if entity.description else '',
                'aliases': sorted([self._normalize_text(alias) for alias in entity.aliases]) if entity.aliases else [],
                'quality_score': round(entity.quality_score, 3),
                'confidence': round(entity.confidence, 3),
                'properties_hash': self._hash_properties(entity.properties) if entity.properties else ''
            }
            
        elif fingerprint_type == FingerprintType.SEMANTIC:
            components = {
                'name': self._normalize_text(entity.name),
                'type': entity.type,
                'entity_type': entity.entity_type,
                'description': self._normalize_text(entity.description) if entity.description else '',
                'aliases': sorted([self._normalize_text(alias) for alias in entity.aliases]) if entity.aliases else [],
                'embedding_hash': self._hash_embedding(entity.embedding) if entity.embedding else '',
                'quality_score': round(entity.quality_score, 3),
                'confidence': round(entity.confidence, 3)
            }
            
        elif fingerprint_type == FingerprintType.FULL:
            components = {
                'name': self._normalize_text(entity.name),
                'type': entity.type,
                'entity_type': entity.entity_type,
                'description': self._normalize_text(entity.description) if entity.description else '',
                'aliases': sorted([self._normalize_text(alias) for alias in entity.aliases]) if entity.aliases else [],
                'quality_score': round(entity.quality_score, 3),
                'importance_score': round(entity.importance_score, 3),
                'confidence': round(entity.confidence, 3),
                'properties_hash': self._hash_properties(entity.properties) if entity.properties else '',
                'embedding_hash': self._hash_embedding(entity.embedding) if entity.embedding else '',
                'lifecycle_state': entity.lifecycle_state.value if entity.lifecycle_state else '',
                'reference_count': entity.reference_count,
                'relationship_count': entity.relationship_count,
                'merged_from': sorted(entity.merged_from) if entity.merged_from else []
            }
            
        return components
        
    def _normalize_text(self, text: str) -> str:
        """标准化文本"""
        if not text:
            return ''
        
        # 转换为小写，去除首尾空格
        normalized = text.lower().strip()
        
        # 替换多个空格为单个空格
        normalized = ' '.join(normalized.split())
        
        # 移除标点符号（可选）
        import re
        normalized = re.sub(r'[^\w\s\u4e00-\u9fff]', '', normalized)
        
        return normalized
        
    def _hash_properties(self, properties: Dict[str, Any]) -> str:
        """哈希属性字典"""
        if not properties:
            return ''
        
        # 排序键值对以确保一致性
        sorted_props = sorted(properties.items())
        props_str = json.dumps(sorted_props, ensure_ascii=False, sort_keys=True)
        
        return hashlib.md5(props_str.encode('utf-8')).hexdigest()
        
    def _hash_embedding(self, embedding: List[float]) -> str:
        """哈希embedding向量"""
        if not embedding:
            return ''
        
        # 将浮点数转换为字符串（保留3位小数）
        embedding_str = ','.join([f"{x:.3f}" for x in embedding])
        
        return hashlib.md5(embedding_str.encode('utf-8')).hexdigest()
        
    def _serialize_components(self, components: Dict[str, Any]) -> str:
        """序列化组件"""
        return json.dumps(components, ensure_ascii=False, sort_keys=True)
        
    def _hash_data(self, data: str, algorithm: FingerprintAlgorithm) -> str:
        """哈希数据"""
        data_bytes = data.encode('utf-8')
        
        if algorithm == FingerprintAlgorithm.MD5:
            return hashlib.md5(data_bytes).hexdigest()
        elif algorithm == FingerprintAlgorithm.SHA1:
            return hashlib.sha1(data_bytes).hexdigest()
        elif algorithm == FingerprintAlgorithm.SHA256:
            return hashlib.sha256(data_bytes).hexdigest()
        elif algorithm == FingerprintAlgorithm.XXHASH:
            # 如果需要xxhash，需要安装xxhash库
            try:
                import xxhash
                return xxhash.xxh64(data_bytes).hexdigest()
            except ImportError:
                logger.warning("xxhash not available, falling back to MD5")
                return hashlib.md5(data_bytes).hexdigest()
        else:
            return hashlib.md5(data_bytes).hexdigest()
            
    def compare_fingerprints(self, 
                           entity1: Entity, 
                           entity2: Entity,
                           fingerprint_type: Optional[FingerprintType] = None) -> FingerprintComparison:
        """比较两个实体的指纹"""
        fp_type = fingerprint_type or self.default_type
        
        # 生成指纹
        fp1 = self.generate_fingerprint(entity1, fp_type)
        fp2 = self.generate_fingerprint(entity2, fp_type)
        
        # 检查缓存
        cache_key = f"{fp1.fingerprint}_{fp2.fingerprint}"
        if cache_key in self.comparison_cache:
            return self.comparison_cache[cache_key]
            
        # 比较指纹
        is_identical = fp1.fingerprint == fp2.fingerprint
        
        # 计算相似度和变更详情
        similarity_score, changed_components, change_details = self._analyze_changes(fp1.components, fp2.components)
        
        # 创建比较结果
        comparison = FingerprintComparison(
            is_identical=is_identical,
            similarity_score=similarity_score,
            changed_components=changed_components,
            change_details=change_details
        )
        
        # 缓存结果
        self.comparison_cache[cache_key] = comparison
        
        return comparison
        
    def _analyze_changes(self, 
                        components1: Dict[str, Any], 
                        components2: Dict[str, Any]) -> Tuple[float, List[str], Dict[str, Any]]:
        """分析变更详情"""
        changed_components = []
        change_details = {}
        
        # 获取所有键
        all_keys = set(components1.keys()) | set(components2.keys())
        
        identical_count = 0
        total_count = len(all_keys)
        
        for key in all_keys:
            value1 = components1.get(key)
            value2 = components2.get(key)
            
            if value1 == value2:
                identical_count += 1
            else:
                changed_components.append(key)
                change_details[key] = {
                    'old_value': value1,
                    'new_value': value2,
                    'change_type': self._classify_change(value1, value2)
                }
                
        # 计算相似度分数
        similarity_score = identical_count / total_count if total_count > 0 else 1.0
        
        return similarity_score, changed_components, change_details
        
    def _classify_change(self, old_value: Any, new_value: Any) -> str:
        """分类变更类型"""
        if old_value is None and new_value is not None:
            return 'added'
        elif old_value is not None and new_value is None:
            return 'removed'
        elif old_value != new_value:
            return 'modified'
        else:
            return 'unchanged'
            
    def detect_changes(self, 
                      entity: Entity, 
                      previous_fingerprint: str,
                      fingerprint_type: Optional[FingerprintType] = None) -> Dict[str, Any]:
        """检测实体变更"""
        current_fp = self.generate_fingerprint(entity, fingerprint_type)
        
        has_changed = current_fp.fingerprint != previous_fingerprint
        
        return {
            'has_changed': has_changed,
            'previous_fingerprint': previous_fingerprint,
            'current_fingerprint': current_fp.fingerprint,
            'change_timestamp': datetime.now().isoformat(),
            'fingerprint_type': current_fp.fingerprint_type.value,
            'components': current_fp.components if has_changed else None
        }
        
    def batch_generate_fingerprints(self, 
                                   entities: List[Entity],
                                   fingerprint_type: Optional[FingerprintType] = None) -> Dict[str, FingerprintResult]:
        """批量生成指纹"""
        results = {}
        
        for entity in entities:
            try:
                result = self.generate_fingerprint(entity, fingerprint_type)
                results[entity.id] = result
            except Exception as e:
                logger.error(f"Error generating fingerprint for entity {entity.id}: {str(e)}")
                
        return results
        
    def find_duplicate_fingerprints(self, 
                                   entities: List[Entity],
                                   fingerprint_type: Optional[FingerprintType] = None) -> Dict[str, List[str]]:
        """查找重复指纹"""
        fingerprints = self.batch_generate_fingerprints(entities, fingerprint_type)
        
        # 按指纹分组
        fp_groups = {}
        for entity_id, fp_result in fingerprints.items():
            fp = fp_result.fingerprint
            if fp not in fp_groups:
                fp_groups[fp] = []
            fp_groups[fp].append(entity_id)
            
        # 只返回有多个实体的指纹
        duplicates = {fp: entity_ids for fp, entity_ids in fp_groups.items() if len(entity_ids) > 1}
        
        return duplicates
        
    def get_fingerprint_statistics(self) -> Dict[str, Any]:
        """获取指纹统计信息"""
        total_cached = len(self.fingerprint_cache)
        total_comparisons = len(self.comparison_cache)
        
        # 按类型统计
        type_stats = {}
        for fp_result in self.fingerprint_cache.values():
            fp_type = fp_result.fingerprint_type.value
            type_stats[fp_type] = type_stats.get(fp_type, 0) + 1
            
        # 按算法统计
        algorithm_stats = {}
        for fp_result in self.fingerprint_cache.values():
            algorithm = fp_result.algorithm.value
            algorithm_stats[algorithm] = algorithm_stats.get(algorithm, 0) + 1
            
        return {
            'total_cached_fingerprints': total_cached,
            'total_cached_comparisons': total_comparisons,
            'fingerprint_type_distribution': type_stats,
            'algorithm_distribution': algorithm_stats,
            'cache_hit_rate': self._calculate_cache_hit_rate(),
            'supported_types': [t.value for t in FingerprintType],
            'supported_algorithms': [a.value for a in FingerprintAlgorithm]
        }
        
    def _calculate_cache_hit_rate(self) -> float:
        """计算缓存命中率"""
        # 这里需要实现更精确的缓存命中率统计
        # 暂时返回估算值
        return 0.0
        
    def clear_cache(self):
        """清空缓存"""
        self.fingerprint_cache.clear()
        self.comparison_cache.clear()
        logger.info("Cleared fingerprint cache")
        
    def validate_fingerprint(self, 
                           entity: Entity, 
                           expected_fingerprint: str,
                           fingerprint_type: Optional[FingerprintType] = None) -> bool:
        """验证指纹是否正确"""
        current_fp = self.generate_fingerprint(entity, fingerprint_type)
        return current_fp.fingerprint == expected_fingerprint
        
    def export_fingerprints(self, entities: List[Entity]) -> Dict[str, Any]:
        """导出指纹数据"""
        fingerprints = self.batch_generate_fingerprints(entities)
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'total_entities': len(entities),
            'fingerprints': {}
        }
        
        for entity_id, fp_result in fingerprints.items():
            export_data['fingerprints'][entity_id] = {
                'fingerprint': fp_result.fingerprint,
                'algorithm': fp_result.algorithm.value,
                'type': fp_result.fingerprint_type.value,
                'created_at': fp_result.created_at.isoformat()
            }
            
        return export_data
        
    def import_fingerprints(self, import_data: Dict[str, Any]) -> int:
        """导入指纹数据"""
        imported_count = 0
        
        for entity_id, fp_data in import_data.get('fingerprints', {}).items():
            try:
                # 重建指纹结果
                fp_result = FingerprintResult(
                    fingerprint=fp_data['fingerprint'],
                    algorithm=FingerprintAlgorithm(fp_data['algorithm']),
                    fingerprint_type=FingerprintType(fp_data['type']),
                    components={},  # 组件信息在导入时不可用
                    created_at=datetime.fromisoformat(fp_data['created_at'])
                )
                
                # 添加到缓存
                cache_key = f"{entity_id}_{fp_result.fingerprint_type.value}_{fp_result.algorithm.value}"
                self.fingerprint_cache[cache_key] = fp_result
                
                imported_count += 1
                
            except Exception as e:
                logger.error(f"Error importing fingerprint for entity {entity_id}: {str(e)}")
                
        logger.info(f"Imported {imported_count} fingerprints")
        return imported_count


# 全局实例
_entity_fingerprint_util = None


def get_entity_fingerprint_util() -> EntityFingerprintUtil:
    """获取实体指纹工具实例"""
    global _entity_fingerprint_util
    if _entity_fingerprint_util is None:
        _entity_fingerprint_util = EntityFingerprintUtil()
    return _entity_fingerprint_util


def generate_entity_fingerprint(entity: Entity, 
                               fingerprint_type: FingerprintType = FingerprintType.EXTENDED) -> str:
    """快速生成实体指纹的便捷函数"""
    util = get_entity_fingerprint_util()
    result = util.generate_fingerprint(entity, fingerprint_type)
    return result.fingerprint


def compare_entity_fingerprints(entity1: Entity, entity2: Entity) -> bool:
    """快速比较两个实体指纹的便捷函数"""
    util = get_entity_fingerprint_util()
    comparison = util.compare_fingerprints(entity1, entity2)
    return comparison.is_identical