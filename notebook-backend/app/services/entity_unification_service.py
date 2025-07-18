# -*- coding: utf-8 -*-
"""
实体统一核心服务
实现基于多维度相似度的智能实体统一算法，是整个实体统一系统的核心
"""
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.services.entity_similarity_service import (
    get_entity_similarity_calculator, 
    EntitySimilarityMatrix
)
from app.services.entity_merge_service import (
    get_merge_decision_engine,
    get_entity_merger,
    MergeDecision,
    MergedEntity
)
from app.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


@dataclass
class UnificationResult:
    """统一结果"""
    unified_entities: List[Any]
    merge_operations: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    processing_time: float
    quality_metrics: Dict[str, Any]


@dataclass
class UnificationConfig:
    """统一配置"""
    similarity_threshold: float = 0.65
    batch_size: int = 100
    max_matrix_size: int = 10000
    enable_caching: bool = True
    parallel_workers: int = 4
    memory_limit_mb: int = 2048
    # 🆕 类型分组配置
    enable_type_grouping: bool = True
    type_similarity_thresholds: Dict[str, float] = None
    max_entities_per_type_batch: int = 50
    # 🚀 LangGraph Agent配置
    enable_langgraph_agent: bool = True
    agent_prescreening_threshold: float = 0.4
    force_wikipedia_verification: bool = True
    agent_conservative_mode: bool = True
    max_agent_pairs_per_batch: int = 50
    
    def __post_init__(self):
        """初始化后处理"""
        if self.type_similarity_thresholds is None:
            self.type_similarity_thresholds = {
                '人物': 0.75,      # 人名相似度要求高
                '组织': 0.70,      # 组织名可能有缩写
                '地点': 0.80,      # 地名要求精确
                '产品': 0.65,      # 产品名变体较多
                '技术': 0.60,      # 技术名词变体最多
                '事件': 0.75,      # 事件名要求较高
                '时间': 0.85,      # 时间表达要求精确
                '数量': 0.90,      # 数量表达要求很精确
                'default': 0.65    # 默认阈值
            }


class EntityUnificationService:
    """
    实体统一核心服务
    
    提供完整的实体统一流程：
    1. 批量embedding生成
    2. 相似度矩阵构建  
    3. 聚类合并算法
    4. 质量评估和优化
    """
    
    def __init__(self, config: Optional[UnificationConfig] = None):
        """初始化实体统一服务"""
        self.config = config or self._load_default_config()
        
        # 初始化传统组件
        self.embedding_service = get_embedding_service()
        self.similarity_calculator = get_entity_similarity_calculator()
        self.similarity_matrix_builder = EntitySimilarityMatrix()
        self.merge_decision_engine = get_merge_decision_engine()
        self.entity_merger = get_entity_merger()
        
    # 🚀 初始化LangGraph Agent（如果启用）
        self.langgraph_agent = None
        self.autonomous_agent_integration = None
        
        # 优先使用自主Agent
        if self.config.enable_langgraph_agent:
            try:
                # 先尝试自主Agent
                from app.services.autonomous_agent_integration import get_autonomous_agent_integration
                self.autonomous_agent_integration = get_autonomous_agent_integration(self.config)
                logger.info("自主实体去重Agent已启用")
                
            except Exception as e:
                logger.warning(f"自主Agent初始化失败，尝试传统LangGraph: {str(e)}")
                try:
                    from app.services.langgraph_entity_agent import get_langgraph_entity_deduplication_agent
                    agent_config = {
                        "prescreening_threshold": self.config.agent_prescreening_threshold,
                        "force_wikipedia_verification": self.config.force_wikipedia_verification,
                        "conservative_mode": self.config.agent_conservative_mode,
                        "max_pairs_per_batch": self.config.max_agent_pairs_per_batch,
                        "enable_vector_prescreening": True,  # 启用向量预筛选
                        "max_retries": 2  # 最大重试次数
                    }
                    self.langgraph_agent = get_langgraph_entity_deduplication_agent(agent_config)
                    logger.info("传统LangGraph Agent已启用")
                except Exception as e2:
                    logger.warning(f"传统LangGraph Agent初始化失败，回退到传统方法: {str(e2)}")
                    self.config.enable_langgraph_agent = False
        
        # 性能监控
        self.performance_stats = {
            "total_entities_processed": 0,
            "total_merge_operations": 0,
            "total_processing_time": 0.0,
            "cache_hit_rate": 0.0
        }
        
        strategy = "自主Agent" if self.autonomous_agent_integration else \
                  ("传统LangGraph Agent" if self.langgraph_agent else "传统向量相似度")
        logger.info(f"实体统一服务已初始化，使用策略: {strategy}")
    
    async def unify_entities(self, entities: List[Any]) -> UnificationResult:
        """
        执行完整的实体统一流程
        
        Args:
            entities: 待统一的实体列表
            
        Returns:
            UnificationResult: 统一结果
        """
        start_time = time.time()
        
        logger.info(f"开始实体统一流程，输入实体数量: {len(entities)}")
        
        try:
            # 阶段1: 数据预处理和验证
            validated_entities = await self._preprocess_entities(entities)
            logger.info(f"预处理完成，有效实体: {len(validated_entities)}")
            
            # 🆕 选择统一策略：类型分组 vs 传统全量
            if self.config.enable_type_grouping:
                result = await self._unify_entities_by_type_grouping(validated_entities, start_time)
            else:
                result = await self._unify_entities_traditional(validated_entities, start_time)
            
            logger.info(f"实体统一完成: {len(entities)} -> {len(result.unified_entities)} "
                       f"(减少 {len(entities) - len(result.unified_entities)} 个重复), "
                       f"耗时: {result.processing_time:.3f}秒")
            
            return result
            
        except Exception as e:
            logger.error(f"实体统一失败: {str(e)}")
            raise
    
    async def _unify_entities_by_type_grouping(self, entities: List[Any], start_time: float) -> UnificationResult:
        """
        🆕 基于类型分组的实体统一（性能优化版本）
        
        Args:
            entities: 预处理后的实体列表
            start_time: 开始时间
            
        Returns:
            UnificationResult: 统一结果
        """
        logger.info(f"使用类型分组策略进行实体统一，共 {len(entities)} 个实体")
        
        # 步骤1: 按类型分组
        entities_by_type = self._group_entities_by_type(entities)
        logger.info(f"实体类型分组完成: {[(type_name, len(entities_list)) for type_name, entities_list in entities_by_type.items()]}")
        
        # 步骤2: 为所有实体批量生成embedding（跨类型优化）
        all_embedded_entities = await self._generate_embeddings_for_entities(entities)
        logger.info(f"跨类型批量embedding生成完成: {len(all_embedded_entities)} 个实体")
        
        # 重新按类型分组embedded entities
        embedded_entities_by_type = self._group_entities_by_type(all_embedded_entities)
        
        # 步骤3: 并行处理每个类型的实体统一
        unified_entities = []
        all_merge_operations = []
        type_processing_stats = {}
        
        for entity_type, type_entities in embedded_entities_by_type.items():
            if len(type_entities) < 2:
                # 单个实体，无需合并
                unified_entities.extend(type_entities)
                type_processing_stats[entity_type] = {
                    "input_count": len(type_entities),
                    "output_count": len(type_entities),
                    "merge_count": 0,
                    "processing_time": 0.0
                }
                continue
            
            logger.info(f"处理类型 '{entity_type}' 的 {len(type_entities)} 个实体")
            type_start_time = time.time()
            
            try:
                # 获取类型特定的相似度阈值
                type_threshold = self.config.type_similarity_thresholds.get(
                    entity_type, 
                    self.config.type_similarity_thresholds.get('default', 0.65)
                )
                
                # 分批处理（如果实体过多）
                type_unified_entities, type_merge_operations = await self._process_type_entities_in_batches(
                    type_entities, entity_type, type_threshold
                )
                
                unified_entities.extend(type_unified_entities)
                all_merge_operations.extend(type_merge_operations)
                
                type_processing_time = time.time() - type_start_time
                type_processing_stats[entity_type] = {
                    "input_count": len(type_entities),
                    "output_count": len(type_unified_entities),
                    "merge_count": len(type_merge_operations),
                    "processing_time": type_processing_time,
                    "similarity_threshold": type_threshold,
                    "reduction_rate": (len(type_entities) - len(type_unified_entities)) / len(type_entities) if type_entities else 0
                }
                
                logger.info(f"类型 '{entity_type}' 处理完成: {len(type_entities)} -> {len(type_unified_entities)} "
                           f"(减少 {len(type_entities) - len(type_unified_entities)} 个), "
                           f"用时: {type_processing_time:.3f}秒")
                
            except Exception as e:
                logger.error(f"处理类型 '{entity_type}' 失败: {str(e)}")
                # 错误处理：跳过统一，保留原始实体
                unified_entities.extend(type_entities)
                type_processing_stats[entity_type] = {
                    "input_count": len(type_entities),
                    "output_count": len(type_entities),
                    "merge_count": 0,
                    "processing_time": 0.0,
                    "error": str(e)
                }
        
        # 步骤4: 质量评估
        quality_metrics = self._evaluate_unification_quality(
            entities, unified_entities, all_merge_operations
        )
        quality_metrics["type_processing_stats"] = type_processing_stats
        
        processing_time = time.time() - start_time
        
        # 更新统计信息
        self._update_performance_stats(len(entities), len(all_merge_operations), processing_time)
        
        return UnificationResult(
            unified_entities=unified_entities,
            merge_operations=all_merge_operations,
            statistics={
                "input_entity_count": len(entities),
                "output_entity_count": len(unified_entities),
                "merge_operation_count": len(all_merge_operations),
                "reduction_rate": (len(entities) - len(unified_entities)) / len(entities) if entities else 0,
                "processing_strategy": "type_grouping",
                "entity_types_processed": len(entities_by_type),
                "type_processing_stats": type_processing_stats,
                "processing_stages": {
                    "preprocessing": "completed",
                    "type_grouping": "completed",
                    "batch_embedding_generation": "completed",
                    "type_parallel_processing": "completed",
                    "quality_evaluation": "completed"
                }
            },
            processing_time=processing_time,
            quality_metrics=quality_metrics
        )
    
    async def _unify_entities_traditional(self, entities: List[Any], start_time: float) -> UnificationResult:
        """
        传统的实体统一流程（保持向后兼容）
        
        Args:
            entities: 预处理后的实体列表
            start_time: 开始时间
            
        Returns:
            UnificationResult: 统一结果
        """
        logger.info(f"使用传统策略进行实体统一，共 {len(entities)} 个实体")
        
        # 阶段2: 批量embedding生成
        embedded_entities = await self._generate_embeddings_for_entities(entities)
        logger.info(f"embedding生成完成，成功处理: {len(embedded_entities)}")
        
        # 阶段3: 构建相似度矩阵
        similarity_matrix_result = await self._build_similarity_matrix(embedded_entities)
        logger.info(f"相似度矩阵构建完成，有效相似度对: {similarity_matrix_result['metadata']['valid_pairs']}")
        
        # 阶段4: 聚类和合并
        unified_entities, merge_operations = await self._cluster_and_merge_entities(
            embedded_entities, similarity_matrix_result
        )
        logger.info(f"聚类合并完成，统一后实体数量: {len(unified_entities)}, 合并操作: {len(merge_operations)}")
        
        # 阶段5: 质量评估和优化
        quality_metrics = self._evaluate_unification_quality(
            entities, unified_entities, merge_operations
        )
        
        processing_time = time.time() - start_time
        
        # 更新统计信息
        self._update_performance_stats(len(entities), len(merge_operations), processing_time)
        
        return UnificationResult(
            unified_entities=unified_entities,
            merge_operations=merge_operations,
            statistics={
                "input_entity_count": len(entities),
                "output_entity_count": len(unified_entities),
                "merge_operation_count": len(merge_operations),
                "reduction_rate": (len(entities) - len(unified_entities)) / len(entities) if entities else 0,
                "processing_strategy": "traditional",
                "processing_stages": {
                    "preprocessing": "completed",
                    "embedding_generation": "completed", 
                    "similarity_matrix": "completed",
                    "clustering_merging": "completed",
                    "quality_evaluation": "completed"
                }
            },
            processing_time=processing_time,
            quality_metrics=quality_metrics
        )
    
    async def _preprocess_entities(self, entities: List[Any]) -> List[Any]:
        """
        预处理实体数据
        
        Args:
            entities: 原始实体列表
            
        Returns:
            验证和清理后的实体列表
        """
        valid_entities = []
        
        for entity in entities:
            try:
                # 基本验证
                if not hasattr(entity, 'name') or not entity.name:
                    logger.warning(f"跳过无效实体：缺少名称")
                    continue
                
                if not hasattr(entity, 'type') or not entity.type:
                    logger.warning(f"跳过无效实体：{entity.name} 缺少类型")
                    continue
                
                # 质量过滤
                quality_score = getattr(entity, 'quality_score', 1.0)
                if quality_score < settings.ENTITY_QUALITY_MIN_SCORE:
                    logger.debug(f"跳过低质量实体：{entity.name} (质量分数: {quality_score})")
                    continue
                
                # 名称长度检查
                if len(entity.name.strip()) < 2:
                    logger.debug(f"跳过名称过短的实体：{entity.name}")
                    continue
                
                valid_entities.append(entity)
                
            except Exception as e:
                logger.warning(f"预处理实体时出错: {str(e)}")
                continue
        
        logger.debug(f"预处理完成: {len(entities)} -> {len(valid_entities)}")
        return valid_entities
    
    async def _generate_embeddings_for_entities(self, entities: List[Any]) -> List[Any]:
        """
        为实体批量生成embedding向量
        
        Args:
            entities: 实体列表
            
        Returns:
            包含embedding的实体列表
        """
        # 分离已有embedding和需要生成embedding的实体
        entities_with_embedding = []
        entities_need_embedding = []
        texts_to_embed = []
        
        for entity in entities:
            if hasattr(entity, 'embedding') and entity.embedding is not None:
                entities_with_embedding.append(entity)
            else:
                entities_need_embedding.append(entity)
                # 生成实体的文本表示
                text_repr = self._get_entity_text_representation(entity)
                texts_to_embed.append(text_repr)
        
        logger.debug(f"Embedding状态: 已有 {len(entities_with_embedding)}, 需生成 {len(entities_need_embedding)}")
        
        # 批量生成embedding
        if texts_to_embed:
            try:
                embeddings = await self.embedding_service.embed_documents_batch(
                    texts_to_embed,
                    batch_size=self.config.batch_size,
                    use_cache=self.config.enable_caching
                )
                
                # 将生成的embedding分配给对应的实体
                for i, entity in enumerate(entities_need_embedding):
                    if i < len(embeddings):
                        entity.embedding = embeddings[i]
                        entities_with_embedding.append(entity)
                    else:
                        logger.warning(f"实体 {entity.name} 未能获得embedding")
                        
            except Exception as e:
                logger.error(f"批量生成embedding失败: {str(e)}")
                # 降级处理：返回原始实体列表
                return entities
        
        return entities_with_embedding
    
    async def _build_similarity_matrix(self, entities: List[Any]) -> Dict[str, Any]:
        """
        构建实体相似度矩阵
        
        Args:
            entities: 实体列表
            
        Returns:
            相似度矩阵结果
        """
        # 检查实体数量限制
        if len(entities) * len(entities) > self.config.max_matrix_size:
            logger.warning(f"实体数量过大 ({len(entities)}^2 > {self.config.max_matrix_size})，使用分块策略")
        
        matrix_result = await self.similarity_matrix_builder.build_similarity_matrix(
            entities,
            threshold=self.config.similarity_threshold,
            max_matrix_size=self.config.max_matrix_size
        )
        
        return matrix_result
    
    async def _cluster_and_merge_entities(self, entities: List[Any], 
                                        similarity_matrix_result: Dict[str, Any]) -> Tuple[List[Any], List[Dict[str, Any]]]:
        """
        基于相似度矩阵进行聚类和合并
        
        Args:
            entities: 实体列表
            similarity_matrix_result: 相似度矩阵结果
            
        Returns:
            (统一后的实体列表, 合并操作记录)
        """
        similarity_matrix = similarity_matrix_result["matrix"]
        
        # 1. 构建实体ID到实体对象的映射
        entity_map = {entity.id: entity for entity in entities}
        
        # 2. 使用连通图算法找到需要合并的实体组
        entity_clusters = self._find_entity_clusters(similarity_matrix, self.config.similarity_threshold)
        
        logger.debug(f"发现 {len(entity_clusters)} 个实体聚类")
        
        # 3. 执行合并操作
        unified_entities = []
        merge_operations = []
        processed_entity_ids = set()
        
        for cluster in entity_clusters:
            if len(cluster) == 1:
                # 单个实体，无需合并
                entity_id = cluster[0]
                if entity_id in entity_map and entity_id not in processed_entity_ids:
                    unified_entities.append(entity_map[entity_id])
                    processed_entity_ids.add(entity_id)
            else:
                # 多个实体需要合并
                cluster_entities = [entity_map[eid] for eid in cluster if eid in entity_map]
                
                if len(cluster_entities) >= 2:
                    merged_entity, merge_ops = await self._merge_entity_cluster(cluster_entities)
                    unified_entities.append(merged_entity)
                    merge_operations.extend(merge_ops)
                    processed_entity_ids.update(cluster)
                elif len(cluster_entities) == 1:
                    # 聚类中只有一个有效实体
                    unified_entities.append(cluster_entities[0])
                    processed_entity_ids.update(cluster)
        
        # 4. 添加未处理的单独实体
        for entity in entities:
            if entity.id not in processed_entity_ids:
                unified_entities.append(entity)
        
        return unified_entities, merge_operations
    
    def _find_entity_clusters(self, similarity_matrix: Dict[str, Dict[str, float]], 
                            threshold: float) -> List[List[str]]:
        """
        使用连通图算法找到实体聚类
        
        Args:
            similarity_matrix: 相似度矩阵
            threshold: 相似度阈值
            
        Returns:
            实体聚类列表，每个聚类是实体ID的列表
        """
        # 构建图的边
        edges = []
        for entity1_id, similarities in similarity_matrix.items():
            for entity2_id, similarity in similarities.items():
                if similarity >= threshold and entity1_id != entity2_id:
                    edges.append((entity1_id, entity2_id, similarity))
        
        # 使用并查集算法找连通分量
        clusters = self._union_find_clustering(edges)
        
        # 过滤掉空聚类
        clusters = [cluster for cluster in clusters if cluster]
        
        return clusters
    
    def _union_find_clustering(self, edges: List[Tuple[str, str, float]]) -> List[List[str]]:
        """
        使用并查集算法进行聚类
        
        Args:
            edges: 边列表 [(entity1_id, entity2_id, similarity), ...]
            
        Returns:
            聚类列表
        """
        # 初始化并查集
        parent = {}
        rank = {}
        
        def find(x):
            if x not in parent:
                parent[x] = x
                rank[x] = 0
                return x
            if parent[x] != x:
                parent[x] = find(parent[x])  # 路径压缩
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px == py:
                return
            # 按秩合并
            if rank[px] < rank[py]:
                px, py = py, px
            parent[py] = px
            if rank[px] == rank[py]:
                rank[px] += 1
        
        # 处理所有边
        for entity1_id, entity2_id, similarity in edges:
            union(entity1_id, entity2_id)
        
        # 收集聚类
        clusters_map = {}
        for entity_id in parent:
            root = find(entity_id)
            if root not in clusters_map:
                clusters_map[root] = []
            clusters_map[root].append(entity_id)
        
        return list(clusters_map.values())
    
    async def _merge_entity_cluster(self, cluster_entities: List[Any]) -> Tuple[Any, List[Dict[str, Any]]]:
        """
        合并一个实体聚类
        
        Args:
            cluster_entities: 聚类中的实体列表
            
        Returns:
            (合并后的实体, 合并操作记录列表)
        """
        if len(cluster_entities) == 1:
            return cluster_entities[0], []
        
        merge_operations = []
        
        # 选择最佳的主实体（置信度最高的）
        primary_entity = max(cluster_entities, key=lambda e: e.confidence)
        remaining_entities = [e for e in cluster_entities if e.id != primary_entity.id]
        
        # 逐个合并其他实体到主实体
        merged_entity = primary_entity
        
        for secondary_entity in remaining_entities:
            try:
                # 获取合并决策
                merge_decision = await self.merge_decision_engine.should_merge(
                    merged_entity, secondary_entity
                )
                
                if merge_decision.decision in [MergeDecision.AUTO_MERGE, MergeDecision.CONDITIONAL_MERGE]:
                    # 执行合并
                    new_merged_entity = self.entity_merger.merge_entities(
                        merged_entity, secondary_entity, merge_decision
                    )
                    
                    # 记录合并操作
                    merge_operations.append({
                        "operation_type": "merge",
                        "primary_entity_id": merged_entity.id,
                        "secondary_entity_id": secondary_entity.id,
                        "merged_entity_id": new_merged_entity.id,
                        "decision": merge_decision.decision.value,
                        "similarity_score": merge_decision.similarity_result.total_similarity,
                        "confidence": merge_decision.confidence,
                        "conflicts": [
                            {
                                "type": conflict.conflict_type,
                                "severity": conflict.severity,
                                "description": conflict.description
                            }
                            for conflict in merge_decision.conflicts
                        ]
                    })
                    
                    merged_entity = new_merged_entity
                else:
                    # 拒绝合并，记录原因
                    merge_operations.append({
                        "operation_type": "reject_merge",
                        "entity1_id": merged_entity.id,
                        "entity2_id": secondary_entity.id,
                        "reason": merge_decision.reasoning,
                        "decision": merge_decision.decision.value
                    })
                    
            except Exception as e:
                logger.error(f"合并实体失败: {merged_entity.name} + {secondary_entity.name}, 错误: {str(e)}")
                merge_operations.append({
                    "operation_type": "merge_error",
                    "entity1_id": merged_entity.id,
                    "entity2_id": secondary_entity.id,
                    "error": str(e)
                })
                continue
        
        return merged_entity, merge_operations
    
    def _evaluate_unification_quality(self, original_entities: List[Any], 
                                    unified_entities: List[Any], 
                                    merge_operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        评估统一质量
        
        Args:
            original_entities: 原始实体列表
            unified_entities: 统一后实体列表
            merge_operations: 合并操作记录
            
        Returns:
            质量指标字典
        """
        # 基础统计
        original_count = len(original_entities)
        unified_count = len(unified_entities)
        merge_count = len([op for op in merge_operations if op.get("operation_type") == "merge"])
        
        # 计算减少率
        reduction_rate = (original_count - unified_count) / original_count if original_count > 0 else 0
        
        # 计算平均质量分数
        avg_original_quality = sum(getattr(e, 'quality_score', 1.0) for e in original_entities) / original_count if original_count > 0 else 0
        avg_unified_quality = sum(getattr(e, 'quality_score', 1.0) for e in unified_entities) / unified_count if unified_count > 0 else 0
        
        # 计算合并操作的平均置信度
        merge_confidences = [op.get("confidence", 0) for op in merge_operations if op.get("operation_type") == "merge"]
        avg_merge_confidence = sum(merge_confidences) / len(merge_confidences) if merge_confidences else 0
        
        # 计算冲突统计
        total_conflicts = sum(len(op.get("conflicts", [])) for op in merge_operations if op.get("operation_type") == "merge")
        avg_conflicts_per_merge = total_conflicts / merge_count if merge_count > 0 else 0
        
        return {
            "reduction_rate": reduction_rate,
            "merge_efficiency": merge_count / original_count if original_count > 0 else 0,
            "quality_improvement": avg_unified_quality - avg_original_quality,
            "avg_merge_confidence": avg_merge_confidence,
            "avg_conflicts_per_merge": avg_conflicts_per_merge,
            "total_conflicts": total_conflicts,
            "rejected_merges": len([op for op in merge_operations if op.get("operation_type") == "reject_merge"]),
            "merge_errors": len([op for op in merge_operations if op.get("operation_type") == "merge_error"])
        }
    
    def _get_entity_text_representation(self, entity) -> str:
        """获取实体的文本表示，用于生成embedding"""
        parts = [entity.name]
        
        if hasattr(entity, 'type') and entity.type:
            parts.append(f"类型:{entity.type}")
        
        if hasattr(entity, 'description') and entity.description:
            parts.append(f"描述:{entity.description}")
        
        return " ".join(parts)
    
    def _load_default_config(self) -> UnificationConfig:
        """加载默认配置"""
        return UnificationConfig(
            similarity_threshold=settings.ENTITY_UNIFICATION_MEDIUM_THRESHOLD,
            batch_size=settings.ENTITY_UNIFICATION_BATCH_SIZE,
            max_matrix_size=settings.ENTITY_UNIFICATION_MAX_MATRIX_SIZE,
            enable_caching=True,
            parallel_workers=settings.ENTITY_UNIFICATION_PARALLEL_WORKERS,
            memory_limit_mb=settings.ENTITY_UNIFICATION_MEMORY_LIMIT_MB,
            # 🆕 类型分组配置
            enable_type_grouping=getattr(settings, 'ENTITY_UNIFICATION_ENABLE_TYPE_GROUPING', True),
            max_entities_per_type_batch=getattr(settings, 'ENTITY_UNIFICATION_MAX_ENTITIES_PER_TYPE_BATCH', 50)
        )
    
    def _group_entities_by_type(self, entities: List[Any]) -> Dict[str, List[Any]]:
        """
        🆕 按类型分组实体
        
        Args:
            entities: 实体列表
            
        Returns:
            按类型分组的实体字典
        """
        entities_by_type = {}
        
        for entity in entities:
            entity_type = getattr(entity, 'type', 'unknown')
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity)
        
        return entities_by_type
    
    async def _process_type_entities_in_batches(self, type_entities: List[Any], entity_type: str, threshold: float) -> Tuple[List[Any], List[Dict[str, Any]]]:
        """
        🆕 分批处理同类型实体
        
        Args:
            type_entities: 同类型实体列表
            entity_type: 实体类型
            threshold: 相似度阈值
            
        Returns:
            (统一后的实体列表, 合并操作记录)
        """
        max_batch_size = self.config.max_entities_per_type_batch
        
        if len(type_entities) <= max_batch_size:
            # 单批处理
            return await self._process_single_type_batch(type_entities, entity_type, threshold)
        else:
            # 多批处理
            logger.info(f"类型 '{entity_type}' 实体过多 ({len(type_entities)}), 分批处理 (批大小: {max_batch_size})")
            
            unified_entities = []
            all_merge_operations = []
            
            for i in range(0, len(type_entities), max_batch_size):
                batch_entities = type_entities[i:i + max_batch_size]
                batch_unified, batch_operations = await self._process_single_type_batch(
                    batch_entities, entity_type, threshold
                )
                unified_entities.extend(batch_unified)
                all_merge_operations.extend(batch_operations)
                
                logger.debug(f"批次 {i//max_batch_size + 1} 完成: {len(batch_entities)} -> {len(batch_unified)}")
            
            return unified_entities, all_merge_operations
    
    async def _process_single_type_batch(self, entities: List[Any], entity_type: str, threshold: float) -> Tuple[List[Any], List[Dict[str, Any]]]:
        """
        🆕 处理单个类型批次的实体统一
        
        Args:
            entities: 同类型实体列表
            entity_type: 实体类型
            threshold: 相似度阈值
            
        Returns:
            (统一后的实体列表, 合并操作记录)
        """
        if len(entities) < 2:
            return entities, []
        
        # 🚀 优先使用自主Agent（如果启用）
        if self.autonomous_agent_integration:
            try:
                logger.info(f"使用自主Agent处理 {entity_type} 类型的 {len(entities)} 个实体")
                
                # 直接调用自主Agent集成器，返回UnificationResult
                unification_result = await self.autonomous_agent_integration.unify_entities_with_autonomous_agent(entities)
                
                # 转换为元组格式以兼容现有接口
                return unification_result.unified_entities, unification_result.merge_operations
                
            except Exception as e:
                logger.error(f"自主Agent处理失败，回退到传统方法: {str(e)}")
                # 继续使用传统方法作为备选
        
        # 🚀 使用传统LangGraph Agent（如果启用）
        if self.langgraph_agent:
            try:
                logger.info(f"使用传统LangGraph Agent处理 {entity_type} 类型的 {len(entities)} 个实体")
                
                # 转换实体格式为Agent兼容格式
                agent_entities = self._convert_entities_for_agent(entities)
                
                # 调用传统LangGraph Agent
                agent_result = await self.langgraph_agent.deduplicate_entities(agent_entities, entity_type)
                
                # 转换Agent结果为统一格式
                unified_entities, merge_operations = self._convert_agent_result_to_unification_format(
                    agent_result, entities
                )
                
                logger.info(f"传统LangGraph Agent处理完成: {len(entities)} -> {len(unified_entities)} 个实体")
                return unified_entities, merge_operations
                
            except Exception as e:
                logger.error(f"传统LangGraph Agent处理失败，回退到传统方法: {str(e)}")
                # 继续使用传统方法作为备选
        
        # 传统方法（向量相似度矩阵）
        logger.info(f"使用传统向量相似度方法处理 {entity_type} 类型的 {len(entities)} 个实体")
        
        # 使用类型特定的配置构建相似度矩阵
        similarity_matrix_result = await self._build_similarity_matrix_with_threshold(entities, threshold)
        
        # 聚类和合并
        unified_entities, merge_operations = await self._cluster_and_merge_entities(
            entities, similarity_matrix_result
        )
        
        return unified_entities, merge_operations
    
    def _convert_entities_for_agent(self, entities: List[Any]) -> List[Dict[str, Any]]:
        """
        🚀 转换实体格式为Agent兼容格式
        
        Args:
            entities: 实体对象列表
            
        Returns:
            Agent兼容的字典格式实体列表
        """
        agent_entities = []
        
        for entity in entities:
            agent_entity = {
                "name": getattr(entity, 'name', str(entity)),
                "type": getattr(entity, 'type', 'unknown'),
                "description": getattr(entity, 'description', ''),
                "properties": getattr(entity, 'properties', {}),
                "confidence": getattr(entity, 'confidence', 1.0),
                "quality_score": getattr(entity, 'quality_score', 1.0),
                "source_text": getattr(entity, 'source_text', ''),
                "id": getattr(entity, 'id', f"entity_{len(agent_entities)}")
            }
            
            # 保留embedding如果存在
            if hasattr(entity, 'embedding'):
                agent_entity['embedding'] = entity.embedding
            
            agent_entities.append(agent_entity)
        
        return agent_entities
    
    def _convert_agent_result_to_unification_format(self, agent_result: Dict[str, Any], 
                                                   original_entities: List[Any]) -> Tuple[List[Any], List[Dict[str, Any]]]:
        """
        🚀 转换Agent结果为统一格式
        
        Args:
            agent_result: Agent返回的结果
            original_entities: 原始实体列表
            
        Returns:
            (统一后的实体列表, 合并操作记录)
        """
        unified_entities = []
        merge_operations = []
        
        # 处理合并组
        merge_groups = agent_result.get("merge_groups", [])
        processed_entity_indices = set()
        
        for group in merge_groups:
            # 获取主实体索引（Agent返回的是1开始的索引，需要转换为0开始）
            primary_index = int(group.get("primary_entity", "1")) - 1
            duplicate_indices = [int(idx) - 1 for idx in group.get("duplicates", [])]
            
            # 验证索引有效性
            if 0 <= primary_index < len(original_entities):
                primary_entity = original_entities[primary_index]
                
                # 更新主实体信息
                if group.get("merged_name"):
                    primary_entity.name = group["merged_name"]
                if group.get("merged_description"):
                    primary_entity.description = group["merged_description"]
                
                # 合并属性信息
                for dup_idx in duplicate_indices:
                    if 0 <= dup_idx < len(original_entities):
                        dup_entity = original_entities[dup_idx]
                        
                        # 合并属性
                        if hasattr(primary_entity, 'properties') and hasattr(dup_entity, 'properties'):
                            primary_entity.properties.update(dup_entity.properties)
                        
                        # 增加出现次数
                        chunk_ids = primary_entity.properties.get('chunk_ids', [])
                        dup_chunk_ids = dup_entity.properties.get('chunk_ids', [])
                        primary_entity.properties['chunk_ids'] = list(set(chunk_ids + dup_chunk_ids))
                        
                        processed_entity_indices.add(dup_idx)
                
                unified_entities.append(primary_entity)
                processed_entity_indices.add(primary_index)
                
                # 记录合并操作
                merge_operations.append({
                    "operation_type": "agent_merge",
                    "primary_entity_id": getattr(primary_entity, 'id', f"entity_{primary_index}"),
                    "secondary_entity_ids": [
                        getattr(original_entities[idx], 'id', f"entity_{idx}") 
                        for idx in duplicate_indices 
                        if 0 <= idx < len(original_entities)
                    ],
                    "merged_entity_name": group.get("merged_name", primary_entity.name),
                    "confidence": group.get("confidence", 0.0),
                    "reason": group.get("reason", ""),
                    "wikipedia_evidence": group.get("wikipedia_evidence", ""),
                    "agent_decision": True
                })
        
        # 添加独立实体
        independent_indices = agent_result.get("independent_entities", [])
        for idx_str in independent_indices:
            idx = int(idx_str) - 1  # 转换为0开始的索引
            if 0 <= idx < len(original_entities) and idx not in processed_entity_indices:
                unified_entities.append(original_entities[idx])
                processed_entity_indices.add(idx)
        
        # 添加任何未处理的实体（安全措施）
        for i, entity in enumerate(original_entities):
            if i not in processed_entity_indices:
                unified_entities.append(entity)
                logger.warning(f"实体 {i} 未被Agent处理，自动添加为独立实体")
        
        return unified_entities, merge_operations
    
    async def _build_similarity_matrix_with_threshold(self, entities: List[Any], threshold: float) -> Dict[str, Any]:
        """
        🆕 使用指定阈值构建相似度矩阵
        
        Args:
            entities: 实体列表
            threshold: 相似度阈值
            
        Returns:
            相似度矩阵结果
        """
        # 检查实体数量限制
        if len(entities) * len(entities) > self.config.max_matrix_size:
            logger.warning(f"实体数量过大 ({len(entities)}^2 > {self.config.max_matrix_size})，使用分块策略")
        
        matrix_result = await self.similarity_matrix_builder.build_similarity_matrix(
            entities,
            threshold=threshold,
            max_matrix_size=self.config.max_matrix_size
        )
        
        return matrix_result
    
    def _update_performance_stats(self, entity_count: int, merge_count: int, processing_time: float):
        """更新性能统计"""
        self.performance_stats["total_entities_processed"] += entity_count
        self.performance_stats["total_merge_operations"] += merge_count
        self.performance_stats["total_processing_time"] += processing_time
        
        # 更新缓存命中率
        embedding_stats = self.embedding_service.get_cache_statistics()
        self.performance_stats["cache_hit_rate"] = embedding_stats.get("hit_rate", 0.0)
    
    def get_performance_statistics(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return self.performance_stats.copy()


# 🆕 全局实例和工厂函数
_entity_unification_service_instance = None

def get_entity_unification_service(config: Optional[UnificationConfig] = None) -> EntityUnificationService:
    """
    获取实体统一服务实例（单例模式）
    
    Args:
        config: 可选配置，仅在首次创建时使用
        
    Returns:
        EntityUnificationService: 统一服务实例
    """
    global _entity_unification_service_instance
    if _entity_unification_service_instance is None:
        _entity_unification_service_instance = EntityUnificationService(config)
    return _entity_unification_service_instance 