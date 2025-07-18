# -*- coding: utf-8 -*-
"""
全局实体统一服务 - 重构版本
整合Neo4j采样、LLM语义分析和数据库更新的完整流程
"""
import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.services.neo4j_entity_sampler import get_neo4j_entity_sampler
from app.services.langgraph_entity_agent import get_langgraph_entity_deduplication_agent
from app.services.neo4j_entity_updater import get_neo4j_entity_updater
from app.models.entity import Entity

logger = logging.getLogger(__name__)


@dataclass
class GlobalUnificationConfig:
    """全局实体统一配置"""
    max_sample_entities_per_type: int = 50  # 每种类型最大采样数量
    min_entities_for_unification: int = 2   # 启动统一的最小实体数
    enable_cross_document_sampling: bool = True  # 启用跨文档采样
    llm_confidence_threshold: float = 0.7  # LLM置信度阈值
    max_batch_size: int = 20  # 最大批处理大小
    enable_quality_boost: bool = True  # 启用质量分数提升


@dataclass
class GlobalUnificationResult:
    """全局实体统一结果"""
    success: bool
    total_entities_processed: int
    entities_merged: int
    entities_deleted: int
    relationships_updated: int
    processing_time: float
    type_statistics: Dict[str, Any]
    errors: List[str]


class GlobalEntityUnificationService:
    """全局实体统一服务"""
    
    def __init__(self, config: Optional[GlobalUnificationConfig] = None):
        """
        初始化全局实体统一服务
        
        Args:
            config: 统一配置
        """
        self.config = config or GlobalUnificationConfig()
        self.entity_sampler = get_neo4j_entity_sampler()
        self.langgraph_agent = get_langgraph_entity_deduplication_agent()
        self.entity_updater = get_neo4j_entity_updater()
        
        logger.info("全局实体统一服务初始化完成（使用LangGraph Agent）")
    
    async def unify_entities_for_document(
        self,
        new_entities: List[Entity],
        document_id: int
    ) -> GlobalUnificationResult:
        """
        为新文档的实体执行全局统一
        
        Args:
            new_entities: 新提取的实体列表
            document_id: 文档ID
            
        Returns:
            统一结果
        """
        start_time = time.time()
        
        logger.info(f"开始为文档 {document_id} 执行全局实体统一，新实体数: {len(new_entities)}")
        
        try:
            # 1. 按类型分组新实体
            new_entities_by_type = self._group_entities_by_type(new_entities)
            
            logger.info(f"新实体按类型分组: {[(t, len(entities)) for t, entities in new_entities_by_type.items()]}")
            
            # 2. 为每种类型执行统一
            total_processed = 0
            total_merged = 0
            total_deleted = 0
            total_relationships_updated = 0
            type_statistics = {}
            all_errors = []
            
            for entity_type, type_new_entities in new_entities_by_type.items():
                try:
                    type_result = await self._unify_entities_by_type(
                        type_new_entities, entity_type, document_id
                    )
                    
                    total_processed += type_result['entities_processed']
                    total_merged += type_result['entities_merged']
                    total_deleted += type_result['entities_deleted']
                    total_relationships_updated += type_result['relationships_updated']
                    type_statistics[entity_type] = type_result
                    
                    if type_result['errors']:
                        all_errors.extend(type_result['errors'])
                    
                    logger.info(f"{entity_type} 类型统一完成: {type_result}")
                    
                except Exception as e:
                    error_msg = f"{entity_type} 类型统一失败: {str(e)}"
                    logger.error(error_msg)
                    all_errors.append(error_msg)
            
            processing_time = time.time() - start_time
            
            result = GlobalUnificationResult(
                success=len(all_errors) == 0,
                total_entities_processed=total_processed,
                entities_merged=total_merged,
                entities_deleted=total_deleted,
                relationships_updated=total_relationships_updated,
                processing_time=processing_time,
                type_statistics=type_statistics,
                errors=all_errors
            )
            
            logger.info(f"文档 {document_id} 全局实体统一完成: {result}")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"全局实体统一执行失败: {str(e)}"
            logger.error(error_msg)
            
            return GlobalUnificationResult(
                success=False,
                total_entities_processed=0,
                entities_merged=0,
                entities_deleted=0,
                relationships_updated=0,
                processing_time=processing_time,
                type_statistics={},
                errors=[error_msg]
            )
    
    async def _unify_entities_by_type(
        self,
        new_entities: List[Entity],
        entity_type: str,
        document_id: int
    ) -> Dict[str, Any]:
        """
        为特定类型的实体执行统一
        
        Args:
            new_entities: 新实体列表
            entity_type: 实体类型
            document_id: 文档ID
            
        Returns:
            类型统一结果
        """
        logger.info(f"开始处理 {entity_type} 类型的 {len(new_entities)} 个新实体")
        
        result = {
            'entities_processed': len(new_entities),
            'entities_merged': 0,
            'entities_deleted': 0,
            'relationships_updated': 0,
            'errors': []
        }
        
        if len(new_entities) < self.config.min_entities_for_unification:
            logger.info(f"{entity_type} 类型新实体数量不足，跳过统一")
            return result
        
        try:
            # 1. 从Neo4j采样现有实体
            sampled_entities = self._sample_existing_entities(
                entity_type, document_id
            )
            
            logger.info(f"从Neo4j采样了 {len(sampled_entities)} 个 {entity_type} 类型的现有实体")
            
            # 2. 合并新实体和采样实体
            all_entities = self._combine_entities(new_entities, sampled_entities)
            
            # 🔍 详细日志：合并后的待合并实体集合
            logger.info("=" * 80)
            logger.info(f"🔍 合并后的待合并实体集合 - {entity_type} 类型")
            logger.info("=" * 80)
            logger.info(f"新实体数量: {len(new_entities)}")
            logger.info(f"采样现有实体数量: {len(sampled_entities)}")
            logger.info(f"合并后总实体数量: {len(all_entities)}")
            
            # 详细显示合并后的实体信息（前15个）
            logger.info(f"📝 合并后实体详情（前15个）:")
            for i, entity in enumerate(all_entities[:15]):
                source = entity.get('source', 'unknown')
                logger.info(f"  实体 {i+1} ({source}):")
                logger.info(f"    - 名称: {entity.get('name', 'N/A')}")
                logger.info(f"    - 类型: {entity.get('type', 'N/A')}")
                logger.info(f"    - 描述: {entity.get('description', 'N/A')[:100]}..." if entity.get('description') else "    - 描述: 无")
                logger.info(f"    - ID: {entity.get('id', 'N/A')}")
                logger.info(f"    - 来源: {source}")
                logger.info(f"    - 质量分数: {entity.get('quality_score', 'N/A')}")
                logger.info(f"    - 置信度: {entity.get('confidence', 'N/A')}")
                logger.info(f"    - 别名: {entity.get('aliases', [])}")
                
            if len(all_entities) > 15:
                logger.info(f"  ... 还有 {len(all_entities) - 15} 个实体")
            
            # 按来源统计
            source_stats = {}
            for entity in all_entities:
                source = entity.get('source', 'unknown')
                source_stats[source] = source_stats.get(source, 0) + 1
            
            logger.info(f"📊 实体来源统计:")
            for source, count in source_stats.items():
                logger.info(f"  - {source}: {count} 个")
            
            logger.info("=" * 80)
            
            if len(all_entities) < self.config.min_entities_for_unification:
                logger.info(f"{entity_type} 类型总实体数量不足，跳过统一")
                return result
            
            # 3. LangGraph Agent语义去重分析
            logger.info(f"开始LLM语义去重分析，实体类型: {entity_type}，数量: {len(all_entities)}")
            
            # 转换为LangGraph Agent所需的格式
            entity_dicts = []
            for entity in all_entities:
                try:
                    # 安全地获取实体数据，支持字典和Entity对象
                    entity_dict = {
                        'name': entity.get('name', '') if isinstance(entity, dict) else getattr(entity, 'name', ''),
                        'type': entity.get('type', '') if isinstance(entity, dict) else getattr(entity, 'type', ''),
                        'description': entity.get('description', '') if isinstance(entity, dict) else getattr(entity, 'description', ''),
                        'properties': entity.get('properties', {}) if isinstance(entity, dict) else getattr(entity, 'properties', {})
                    }
                    
                    # 处理ID字段
                    if isinstance(entity, dict):
                        if entity.get('id'):
                            entity_dict['id'] = entity.get('id')
                    else:
                        if hasattr(entity, 'id'):
                            entity_dict['id'] = entity.id
                    
                    entity_dicts.append(entity_dict)
                except Exception as e:
                    logger.warning(f"跳过无效实体转换: {str(e)}")
                    continue
            
            # 使用Agent模式进行去重分析（新的实体列表模式）
            logger.info(f"使用Agent模式进行去重分析：{entity_type} 类型，{len(entity_dicts)} 个实体")
            
            # 🔍 详细日志：发送给Agent的实体数据格式检查
            logger.info("=== 发送给Agent的实体数据格式检查 ===")
            logger.info(f"实体字典数量: {len(entity_dicts)}")
            
            if entity_dicts:
                logger.info("前3个实体的数据格式:")
                for i, entity_dict in enumerate(entity_dicts[:3]):
                    logger.info(f"  实体 {i+1}:")
                    logger.info(f"    - name: {entity_dict.get('name', 'N/A')}")
                    logger.info(f"    - type: {entity_dict.get('type', 'N/A')}")
                    logger.info(f"    - id: {entity_dict.get('id', 'N/A')}")
                    logger.info(f"    - description: {entity_dict.get('description', 'N/A')[:50]}...{' (truncated)' if len(entity_dict.get('description', '')) > 50 else ''}")
            
            analysis_result = await self.langgraph_agent.deduplicate_entities_list(entity_dicts, entity_type)
            
            # 🔍 详细日志：Agent返回结果检查
            logger.info("=== Agent返回结果检查 ===")
            logger.info(f"分析结果类型: {type(analysis_result)}")
            logger.info(f"分析结果键: {list(analysis_result.keys()) if isinstance(analysis_result, dict) else 'N/A'}")
            logger.info(f"分析摘要: {analysis_result.get('analysis_summary', 'N/A')}")
            
            merge_groups = analysis_result.get("merge_groups", [])
            logger.info(f"Agent识别的合并组数量: {len(merge_groups)}")
            
            if merge_groups:
                logger.info("前2个合并组的详情:")
                for i, group in enumerate(merge_groups[:2]):
                    logger.info(f"  合并组 {i+1}:")
                    logger.info(f"    - primary_entity: {group.get('primary_entity', 'N/A')}")
                    logger.info(f"    - duplicates: {group.get('duplicates', [])}")
                    logger.info(f"    - primary_entity_id: {group.get('primary_entity_id', 'N/A')}")
                    logger.info(f"    - duplicate_entity_ids: {group.get('duplicate_entity_ids', [])}")
                    logger.info(f"    - confidence: {group.get('confidence', 'N/A')}")
            
            # 4. 提取合并操作
            logger.info(f"开始提取合并操作，原实体数量: {len(all_entities)}")
            merge_operations = self._extract_merge_operations_from_agent_result(analysis_result, all_entities)
            
            if not merge_operations:
                logger.info(f"{entity_type} 类型没有需要合并的实体")
                return result
            
            # 5. 应用合并操作到Neo4j
            update_result = self.entity_updater.apply_merge_operations(
                all_entities, merge_operations
            )
            
            result['entities_merged'] = update_result['merged_entities']
            result['entities_deleted'] = update_result['deleted_entities']
            result['relationships_updated'] = update_result['updated_relationships']
            result['errors'] = update_result['errors']
            
            logger.info(f"{entity_type} 类型统一完成: 合并 {result['entities_merged']} 个，删除 {result['entities_deleted']} 个")
            
            return result
            
        except Exception as e:
            error_msg = f"{entity_type} 类型统一处理失败: {str(e)}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
            return result
    
    def _sample_existing_entities(
        self,
        entity_type: str,
        exclude_document_id: int
    ) -> List[Dict[str, Any]]:
        """
        从Neo4j采样现有实体
        
        Args:
            entity_type: 实体类型
            exclude_document_id: 排除的文档ID
            
        Returns:
            采样的实体列表
        """
        try:
            # 获取该类型的实体总数
            total_count = self.entity_sampler.get_entity_count_by_type(entity_type)
            
            if total_count == 0:
                logger.info(f"Neo4j中没有 {entity_type} 类型的现有实体")
                return []
            
            # 确定采样数量
            sample_size = min(total_count, self.config.max_sample_entities_per_type)
            
            # 执行采样 - 统一使用同步方法
            sampled_entities = self.entity_sampler.sample_entities_by_type(
                entity_type=entity_type,
                limit=sample_size,
                exclude_document_ids=[exclude_document_id] if not self.config.enable_cross_document_sampling else None
            )
            
            logger.debug(f"成功采样 {len(sampled_entities)} 个 {entity_type} 类型实体")
            return sampled_entities
            
        except Exception as e:
            logger.error(f"采样 {entity_type} 类型实体失败: {str(e)}")
            return []
    
    def _combine_entities(
        self,
        new_entities: List[Entity],
        sampled_entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        合并新实体和采样实体为统一格式
        
        Args:
            new_entities: 新实体列表
            sampled_entities: 采样的现有实体列表
            
        Returns:
            统一格式的实体列表
        """
        combined_entities = []
        
        # 添加新实体（转换为字典格式）
        for entity in new_entities:
            try:
                # 安全地转换Entity对象为字典
                entity_dict = {
                    'id': getattr(entity, 'id', ''),
                    'name': getattr(entity, 'name', ''),
                    'type': getattr(entity, 'type', ''),
                    'entity_type': getattr(entity, 'entity_type', None) or getattr(entity, 'type', ''),
                    'description': getattr(entity, 'description', ''),
                    'properties': getattr(entity, 'properties', {}),
                    'confidence': getattr(entity, 'confidence', 0.8),
                    'source_text': getattr(entity, 'source_text', ''),
                    'quality_score': getattr(entity, 'quality_score', 0.8),
                    'importance_score': getattr(entity, 'importance_score', 0.5),
                    'aliases': getattr(entity, 'aliases', []) or [],
                    'source': 'new_document',
                    'temp_id': getattr(entity, 'id', '')
                }
                combined_entities.append(entity_dict)
            except Exception as e:
                logger.warning(f"跳过有问题的新实体: {str(e)}")
                continue
        
        # 添加采样实体（已经是字典格式）
        for entity in sampled_entities:
            try:
                # 创建实体副本，避免修改原始数据
                entity_copy = dict(entity)
                entity_copy['source'] = 'neo4j_existing'
                combined_entities.append(entity_copy)
            except Exception as e:
                logger.warning(f"跳过有问题的采样实体: {str(e)}")
                continue
        
        logger.debug(f"合并实体完成: 新实体 {len(new_entities)} 个，采样实体 {len(sampled_entities)} 个，总计 {len(combined_entities)} 个")
        
        return combined_entities
    
    def _group_entities_by_type(self, entities: List[Entity]) -> Dict[str, List[Entity]]:
        """
        按类型分组实体
        
        Args:
            entities: 实体列表
            
        Returns:
            按类型分组的实体字典
        """
        grouped = {}
        
        for entity in entities:
            # 安全地获取实体类型，支持Entity对象和字典格式
            if hasattr(entity, 'entity_type'):
                # Entity对象
                entity_type = entity.entity_type or entity.type
            else:
                # 字典格式
                entity_type = entity.get('entity_type') or entity.get('type', 'unknown')
            
            if entity_type not in grouped:
                grouped[entity_type] = []
            grouped[entity_type].append(entity)
        
        return grouped
    
    async def get_unification_statistics(self) -> Dict[str, Any]:
        """
        获取统一统计信息
        
        Returns:
            统计信息
        """
        try:
            # 获取实体统计
            entity_stats = self.entity_updater.get_entity_statistics()
            
            # 获取类型分布统计
            type_stats = self.entity_sampler.get_entity_types_with_counts()
            
            return {
                'entity_statistics': entity_stats,
                'type_distribution': type_stats,
                'config': {
                    'max_sample_entities_per_type': self.config.max_sample_entities_per_type,
                    'min_entities_for_unification': self.config.min_entities_for_unification,
                    'llm_confidence_threshold': self.config.llm_confidence_threshold,
                    'max_batch_size': self.config.max_batch_size
                }
            }
            
        except Exception as e:
            logger.error(f"获取统一统计信息失败: {str(e)}")
            return {
                'error': str(e),
                'entity_statistics': {},
                'type_distribution': {},
                'config': {}
            }
    
    async def manual_unify_entity_type(
        self,
        entity_type: str,
        limit: Optional[int] = None
    ) -> GlobalUnificationResult:
        """
        手动触发特定类型的实体统一
        
        Args:
            entity_type: 实体类型
            limit: 处理数量限制
            
        Returns:
            统一结果
        """
        start_time = time.time()
        
        logger.info(f"开始手动统一 {entity_type} 类型实体，限制: {limit}")
        
        try:
            # 采样该类型的所有实体
            sample_limit = limit or self.config.max_sample_entities_per_type * 2
            
            # 统一使用同步方法采样
            sampled_entities = self.entity_sampler.sample_entities_by_type(
                entity_type=entity_type,
                limit=sample_limit
            )
            
            if len(sampled_entities) < self.config.min_entities_for_unification:
                logger.info(f"{entity_type} 类型实体数量不足，跳过统一")
                return GlobalUnificationResult(
                    success=True,
                    total_entities_processed=len(sampled_entities),
                    entities_merged=0,
                    entities_deleted=0,
                    relationships_updated=0,
                    processing_time=time.time() - start_time,
                    type_statistics={},
                    errors=[]
                )
            
            # LangGraph Agent分析
            logger.info(f"开始Agent去重分析：{entity_type} 类型，{len(sampled_entities)} 个实体")
            
            # 转换为LangGraph Agent所需的格式
            entity_dicts = []
            for entity in sampled_entities:
                try:
                    # 安全地转换实体为Agent所需格式
                    entity_dict = {
                        'name': entity.get('name', ''),
                        'type': entity.get('type', ''),
                        'description': entity.get('description', ''),
                        'properties': entity.get('properties', {})
                    }
                    if entity.get('id'):
                        entity_dict['id'] = entity.get('id')
                    entity_dicts.append(entity_dict)
                except Exception as e:
                    logger.warning(f"跳过无效实体转换: {str(e)}")
                    continue
            
            analysis_result = await self.langgraph_agent.deduplicate_entities_list(entity_dicts, entity_type)
            
            # 应用合并操作
            merge_operations = self._extract_merge_operations_from_agent_result(analysis_result, sampled_entities)
            update_result = self.entity_updater.apply_merge_operations(
                sampled_entities, merge_operations
            )
            
            processing_time = time.time() - start_time
            
            return GlobalUnificationResult(
                success=len(update_result['errors']) == 0,
                total_entities_processed=len(sampled_entities),
                entities_merged=update_result['merged_entities'],
                entities_deleted=update_result['deleted_entities'],
                relationships_updated=update_result['updated_relationships'],
                processing_time=processing_time,
                type_statistics={entity_type: update_result},
                errors=update_result['errors']
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"手动统一 {entity_type} 类型失败: {str(e)}"
            logger.error(error_msg)
            
            return GlobalUnificationResult(
                success=False,
                total_entities_processed=0,
                entities_merged=0,
                entities_deleted=0,
                relationships_updated=0,
                processing_time=processing_time,
                type_statistics={},
                errors=[error_msg]
            )
    
    def _get_entity_real_id(self, entity: Dict[str, Any]) -> Optional[str]:
        """
        获取实体的真实Neo4j ID
        
        Args:
            entity: 实体数据
            
        Returns:
            真实的Neo4j ID或None
        """
        # 优先级：elementId > identity > node_id > id
        for id_field in ['elementId', 'identity', 'node_id', 'id']:
            if entity.get(id_field):
                return str(entity[id_field])
        
        # 如果都没有，记录警告
        logger.warning(f"实体 {entity.get('name', 'Unknown')} 没有有效的ID字段")
        return None
    
    def _extract_merge_operations_from_agent_result(self, analysis_result: Dict[str, Any], entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从LangGraph Agent结果中提取合并操作（增强版）
        
        Args:
            analysis_result: Agent分析结果
            entities: 原始实体列表（统一为字典格式）
            
        Returns:
            合并操作列表
        """
        logger.info("开始从Agent结果中提取合并操作（增强版）")
        
        merge_operations = []
        
        # 从Agent结果中提取合并组
        merge_groups = analysis_result.get("merge_groups", [])
        
        logger.info(f"Agent返回了 {len(merge_groups)} 个合并组")
        
        # 🔍 详细日志：Agent结果分析
        logger.info("=== Agent分析结果详情 ===")
        logger.info(f"分析摘要: {analysis_result.get('analysis_summary', 'N/A')}")
        logger.info(f"合并组数量: {len(merge_groups)}")
        logger.info(f"独立实体数量: {len(analysis_result.get('independent_entities', []))}")
        logger.info(f"不确定案例数量: {len(analysis_result.get('uncertain_cases', []))}")
        
        for i, group in enumerate(merge_groups):
            logger.info(f"=== 处理合并组 {i+1} ===")
            
            try:
                # 🔧 增强的字段提取逻辑
                # 优先使用增强后的ID字段，降级到索引字段
                primary_entity_id = group.get("primary_entity_id")
                primary_entity_index = group.get("primary_entity_index") 
                primary_entity_str = group.get("primary_entity", "1")
                
                duplicate_entity_ids = group.get("duplicate_entity_ids", [])
                duplicate_indices = group.get("duplicate_indices", [])
                duplicate_strs = group.get("duplicates", [])
                
                logger.info(f"原始字段:")
                logger.info(f"  - primary_entity: {primary_entity_str}")
                logger.info(f"  - primary_entity_id: {primary_entity_id}")
                logger.info(f"  - primary_entity_index: {primary_entity_index}")
                logger.info(f"  - duplicates: {duplicate_strs}")
                logger.info(f"  - duplicate_entity_ids: {duplicate_entity_ids}")
                logger.info(f"  - duplicate_indices: {duplicate_indices}")
                
                # 🔧 智能索引解析
                if primary_entity_id and primary_entity_index is not None:
                    # 使用增强后的ID和索引
                    primary_index = primary_entity_index
                elif primary_entity_str.isdigit():
                    # 从字符串转换索引（Agent返回的是1-based）
                    primary_index = int(primary_entity_str) - 1
                else:
                    logger.warning(f"无法确定主实体索引: {primary_entity_str}")
                    continue
                
                # 处理重复实体索引
                valid_duplicate_indices = []
                if duplicate_indices:
                    # 使用增强后的索引
                    valid_duplicate_indices = duplicate_indices
                else:
                    # 从字符串转换索引
                    for dup_str in duplicate_strs:
                        if isinstance(dup_str, str) and dup_str.isdigit():
                            valid_duplicate_indices.append(int(dup_str) - 1)
                        elif isinstance(dup_str, int):
                            valid_duplicate_indices.append(dup_str - 1)
                
                logger.info(f"解析后索引:")
                logger.info(f"  - 主实体索引: {primary_index}")
                logger.info(f"  - 重复实体索引: {valid_duplicate_indices}")
                
                # 🔧 索引有效性验证
                if primary_index < 0 or primary_index >= len(entities):
                    logger.warning(f"主实体索引 {primary_index} 超出范围 [0, {len(entities)-1}]，跳过")
                    continue
                
                # 过滤有效的重复实体索引
                filtered_duplicate_indices = []
                for dup_idx in valid_duplicate_indices:
                    if 0 <= dup_idx < len(entities) and dup_idx != primary_index:
                        filtered_duplicate_indices.append(dup_idx)
                    else:
                        logger.warning(f"重复实体索引 {dup_idx} 无效或与主实体相同，跳过")
                
                if not filtered_duplicate_indices:
                    logger.warning(f"合并组 {i+1} 无有效重复实体索引，跳过")
                    continue
                
                # 🔧 智能主实体选择：优先选择Neo4j中的现有实体作为主实体
                all_indices = [primary_index] + filtered_duplicate_indices
                all_entities_in_group = [entities[idx] for idx in all_indices]
                
                # 查找Neo4j现有实体（source为'neo4j_existing'）
                neo4j_entities = []
                new_entities = []
                
                for idx, entity in zip(all_indices, all_entities_in_group):
                    if entity.get('source') == 'neo4j_existing':
                        neo4j_entities.append((idx, entity))
                    else:
                        new_entities.append((idx, entity))
                
                logger.info(f"实体来源分析:")
                logger.info(f"  - Neo4j现有实体: {len(neo4j_entities)} 个")
                logger.info(f"  - 新文档实体: {len(new_entities)} 个")
                
                # 🔧 智能选择主实体：优先选择Neo4j现有实体
                if neo4j_entities:
                    # 选择第一个Neo4j现有实体作为主实体
                    actual_primary_index, actual_primary_entity = neo4j_entities[0]
                    
                    # 其他所有实体都作为重复实体
                    actual_duplicate_indices = []
                    actual_duplicate_entities = []
                    
                    # 正确遍历：使用zip来获取索引和实体的对应关系
                    for idx, entity in zip(all_indices, all_entities_in_group):
                        if idx != actual_primary_index:
                            actual_duplicate_indices.append(idx)
                            actual_duplicate_entities.append(entity)
                    
                    logger.info(f"🔄 智能主实体选择：选择Neo4j现有实体作为主实体")
                    logger.info(f"  - 新主实体: [{actual_primary_index}] {actual_primary_entity.get('name')} (Neo4j现有)")
                    logger.info(f"  - 待合并实体: {[(idx, entities[idx].get('name')) for idx in actual_duplicate_indices]}")
                    
                else:
                    # 如果没有Neo4j现有实体，使用原始选择
                    actual_primary_index = primary_index
                    actual_primary_entity = entities[primary_index]
                    actual_duplicate_indices = filtered_duplicate_indices
                    actual_duplicate_entities = [entities[idx] for idx in filtered_duplicate_indices]
                    
                    logger.info(f"使用原始主实体选择（无Neo4j现有实体）")
                
                # 🔧 特殊情况检查：如果只有完全相同的实体，跳过合并
                if len(actual_duplicate_indices) == 0:
                    logger.info(f"合并组 {i+1} 经过智能选择后无需合并，跳过")
                    continue
                
                # 🔧 新增：检查是否为新文档实体与现有实体的匹配情况
                primary_source = entities[actual_primary_index].get('source')
                duplicate_sources = [entities[idx].get('source') for idx in actual_duplicate_indices]
                all_sources = [primary_source] + duplicate_sources
                all_names = [entities[idx].get('name') for idx in [actual_primary_index] + actual_duplicate_indices]
                
                # 如果所有实体名称相同，且包含新文档实体和Neo4j现有实体的组合
                if len(set(all_names)) == 1:
                    has_new_document = 'new_document' in all_sources
                    has_neo4j_existing = 'neo4j_existing' in all_sources
                    
                    if has_new_document and has_neo4j_existing:
                        logger.info(f"合并组 {i+1} 是新文档实体与现有实体的匹配，这是正常的实体统一情况")
                        # 继续处理，这是正常的统一操作
                    elif len(set(all_sources)) == 1:
                        logger.info(f"合并组 {i+1} 中所有实体来源相同且名称相同，跳过不必要的合并")
                        continue
                
                # 安全地访问实体名称
                primary_name = actual_primary_entity.get('name', 'Unknown')
                duplicate_names = [dup.get('name', 'Unknown') for dup in actual_duplicate_entities]
                
                logger.info(f"最终实体映射:")
                logger.info(f"  - 主实体: [{actual_primary_index}] {primary_name} ({actual_primary_entity.get('source', 'unknown')})")
                logger.info(f"  - 重复实体: {[(idx, entities[idx].get('name', 'Unknown'), entities[idx].get('source', 'unknown')) for idx in actual_duplicate_indices]}")
                
                # 🔧 创建增强的合并操作
                merge_operation = {
                    "primary_entity": actual_primary_entity,
                    "duplicate_entities": actual_duplicate_entities,
                    "primary_entity_index": actual_primary_index,
                    "duplicate_indices": actual_duplicate_indices,
                    "merged_name": group.get("merged_name", primary_name),
                    "merged_description": group.get("merged_description", actual_primary_entity.get('description', '')),
                    "confidence": group.get("confidence", 0.0),
                    "reason": group.get("reason", "LangGraph Agent分析结果"),
                    "wikipedia_evidence": group.get("wikipedia_evidence", ""),
                    # 新增：原始字段保留
                    "original_group": group
                }
                
                merge_operations.append(merge_operation)
                
                logger.info(f"✅ 合并操作创建成功: {primary_name} <- {duplicate_names}")
                
            except Exception as e:
                logger.error(f"❌ 处理合并组 {i+1} 失败: {str(e)}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")
                continue
        
        logger.info(f"=== 合并操作提取完成 ===")
        logger.info(f"成功提取 {len(merge_operations)} 个合并操作")
        
        # 🔍 详细日志：最终合并操作摘要
        if merge_operations:
            logger.info("📋 合并操作摘要:")
            for i, op in enumerate(merge_operations):
                primary_name = op["primary_entity"].get("name", "Unknown")
                duplicate_names = [dup.get("name", "Unknown") for dup in op["duplicate_entities"]]
                logger.info(f"  {i+1}. {primary_name} <- {duplicate_names} (置信度: {op['confidence']})")
        else:
            logger.warning("⚠️ 没有提取到任何合并操作")
        
        return merge_operations


# 全局实例
_global_unification_service = None

def get_global_entity_unification_service(
    config: Optional[GlobalUnificationConfig] = None
) -> GlobalEntityUnificationService:
    """获取全局实体统一服务实例"""
    global _global_unification_service
    if _global_unification_service is None or config is not None:
        _global_unification_service = GlobalEntityUnificationService(config)
    return _global_unification_service