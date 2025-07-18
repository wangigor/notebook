# -*- coding: utf-8 -*-
"""
实体相似度计算服务
实现基于多维度的实体相似度计算，支持语义、词汇和上下文相似度
"""
import logging
import asyncio
import difflib
import re
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app.core.config import settings
from app.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


@dataclass
class SimilarityResult:
    """相似度计算结果"""
    total_similarity: float
    semantic_similarity: float
    lexical_similarity: float
    contextual_similarity: float
    confidence: float
    details: Dict[str, Any]


class EntitySimilarityCalculator:
    """
    实体相似度计算器
    
    支持多维度相似度计算：
    - 语义相似度：基于embedding向量的cosine相似度（权重40%）
    - 词汇相似度：编辑距离+别名匹配（权重30%）
    - 上下文相似度：类型+描述+共现分析（权重30%）
    """
    
    def __init__(self):
        """初始化相似度计算器"""
        self.embedding_service = get_embedding_service()
        
        # 从配置加载权重
        self.semantic_weight = settings.ENTITY_SIMILARITY_SEMANTIC_WEIGHT
        self.lexical_weight = settings.ENTITY_SIMILARITY_LEXICAL_WEIGHT
        self.contextual_weight = settings.ENTITY_SIMILARITY_CONTEXTUAL_WEIGHT
        
        # 相似度计算缓存
        self._similarity_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        logger.info(f"实体相似度计算器已初始化，权重配置: 语义{self.semantic_weight:.1f}, "
                   f"词汇{self.lexical_weight:.1f}, 上下文{self.contextual_weight:.1f}")
    
    async def calculate_similarity(self, entity1, entity2) -> SimilarityResult:
        """
        计算两个实体的综合相似度
        
        Args:
            entity1: 第一个实体
            entity2: 第二个实体
            
        Returns:
            SimilarityResult: 相似度计算结果
        """
        try:
            # 检查缓存
            cache_key = self._generate_similarity_cache_key(entity1, entity2)
            if cache_key in self._similarity_cache:
                self._cache_hits += 1
                logger.debug(f"相似度计算缓存命中: {entity1.name} <-> {entity2.name}")
                return self._similarity_cache[cache_key]
            
            self._cache_misses += 1
            
            # 1. 计算语义相似度（基于embedding向量）
            semantic_sim = await self._calculate_semantic_similarity(entity1, entity2)
            
            # 2. 计算词汇相似度（编辑距离+别名匹配）
            lexical_sim = self._calculate_lexical_similarity(entity1, entity2)
            
            # 3. 计算上下文相似度（类型+描述+共现）
            contextual_sim = self._calculate_contextual_similarity(entity1, entity2)
            
            # 4. 计算加权总相似度
            total_sim = (
                self.semantic_weight * semantic_sim +
                self.lexical_weight * lexical_sim +
                self.contextual_weight * contextual_sim
            )
            
            # 5. 计算置信度（基于各维度的一致性）
            confidence = self._calculate_confidence(semantic_sim, lexical_sim, contextual_sim)
            
            # 创建结果对象
            result = SimilarityResult(
                total_similarity=total_sim,
                semantic_similarity=semantic_sim,
                lexical_similarity=lexical_sim,
                contextual_similarity=contextual_sim,
                confidence=confidence,
                details={
                    "entity1_name": entity1.name,
                    "entity2_name": entity2.name,
                    "entity1_type": entity1.type,
                    "entity2_type": entity2.type,
                    "weights_used": {
                        "semantic": self.semantic_weight,
                        "lexical": self.lexical_weight,
                        "contextual": self.contextual_weight
                    }
                }
            )
            
            # 缓存结果
            self._similarity_cache[cache_key] = result
            
            # 缓存大小控制
            if len(self._similarity_cache) > settings.ENTITY_SIMILARITY_CACHE_SIZE:
                self._clean_similarity_cache()
            
            logger.debug(f"相似度计算完成: {entity1.name} <-> {entity2.name} = {total_sim:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"相似度计算失败: {entity1.name} <-> {entity2.name}, 错误: {str(e)}")
            # 返回默认的低相似度结果
            return SimilarityResult(
                total_similarity=0.0,
                semantic_similarity=0.0,
                lexical_similarity=0.0,
                contextual_similarity=0.0,
                confidence=0.0,
                details={"error": str(e)}
            )
    
    async def _calculate_semantic_similarity(self, entity1, entity2) -> float:
        """
        计算语义相似度（基于embedding向量的cosine相似度）
        
        Args:
            entity1: 第一个实体
            entity2: 第二个实体
            
        Returns:
            语义相似度分数 [0.0, 1.0]
        """
        try:
            # 确保两个实体都有embedding向量
            embedding1 = getattr(entity1, 'embedding', None)
            embedding2 = getattr(entity2, 'embedding', None)
            
            # 如果缺少embedding，尝试生成
            if embedding1 is None or embedding2 is None:
                entities_to_embed = []
                texts_to_embed = []
                
                if embedding1 is None:
                    entities_to_embed.append(entity1)
                    texts_to_embed.append(self._get_entity_text_representation(entity1))
                    
                if embedding2 is None:
                    entities_to_embed.append(entity2)
                    texts_to_embed.append(self._get_entity_text_representation(entity2))
                
                # 批量生成embedding
                if texts_to_embed:
                    new_embeddings = await self.embedding_service.embed_documents_batch(texts_to_embed)
                    
                    # 更新实体的embedding
                    for i, entity in enumerate(entities_to_embed):
                        if i < len(new_embeddings):
                            entity.embedding = new_embeddings[i]
                
                # 重新获取embedding
                embedding1 = getattr(entity1, 'embedding', None)
                embedding2 = getattr(entity2, 'embedding', None)
            
            # 如果仍然缺少embedding，返回0
            if embedding1 is None or embedding2 is None:
                logger.warning(f"无法获取embedding向量: {entity1.name} or {entity2.name}")
                return 0.0
            
            # 转换为numpy数组
            vec1 = np.array(embedding1, dtype=np.float32)
            vec2 = np.array(embedding2, dtype=np.float32)
            
            # 检查向量维度
            if len(vec1) != len(vec2):
                logger.warning(f"Embedding维度不匹配: {len(vec1)} vs {len(vec2)}")
                return 0.0
            
            # 计算cosine相似度
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                logger.warning("发现零向量，无法计算cosine相似度")
                return 0.0
            
            cosine_sim = np.dot(vec1, vec2) / (norm1 * norm2)
            
            # 将cosine相似度从[-1, 1]映射到[0, 1]
            normalized_sim = (cosine_sim + 1.0) / 2.0
            
            # 确保结果在[0, 1]范围内
            return max(0.0, min(1.0, float(normalized_sim)))
            
        except Exception as e:
            logger.warning(f"语义相似度计算失败: {str(e)}")
            return 0.0
    
    def _calculate_lexical_similarity(self, entity1, entity2) -> float:
        """
        计算词汇相似度（编辑距离+别名匹配）
        
        Args:
            entity1: 第一个实体
            entity2: 第二个实体
            
        Returns:
            词汇相似度分数 [0.0, 1.0]
        """
        try:
            # 1. 主名称相似度（编辑距离）
            name_sim = self._calculate_string_similarity(entity1.name, entity2.name)
            
            # 2. 别名匹配相似度
            alias_sim = self._calculate_alias_similarity(entity1, entity2)
            
            # 3. 合并词汇相似度（取最大值）
            lexical_sim = max(name_sim, alias_sim)
            
            logger.debug(f"词汇相似度: {entity1.name} <-> {entity2.name} = {lexical_sim:.3f} "
                        f"(名称: {name_sim:.3f}, 别名: {alias_sim:.3f})")
            
            return lexical_sim
            
        except Exception as e:
            logger.warning(f"词汇相似度计算失败: {str(e)}")
            return 0.0
    
    def _calculate_contextual_similarity(self, entity1, entity2) -> float:
        """
        计算上下文相似度（类型+描述+共现）
        
        Args:
            entity1: 第一个实体
            entity2: 第二个实体
            
        Returns:
            上下文相似度分数 [0.0, 1.0]
        """
        try:
            # 1. 实体类型匹配（权重50%）
            type_sim = 1.0 if entity1.type == entity2.type else 0.0
            
            # 2. 描述相似度（权重30%）
            desc_sim = self._calculate_description_similarity(entity1, entity2)
            
            # 3. 源文本上下文重叠度（权重20%）
            context_sim = self._calculate_context_overlap(entity1, entity2)
            
            # 4. 合并上下文相似度
            contextual_sim = 0.5 * type_sim + 0.3 * desc_sim + 0.2 * context_sim
            
            logger.debug(f"上下文相似度: {entity1.name} <-> {entity2.name} = {contextual_sim:.3f} "
                        f"(类型: {type_sim:.3f}, 描述: {desc_sim:.3f}, 上下文: {context_sim:.3f})")
            
            return contextual_sim
            
        except Exception as e:
            logger.warning(f"上下文相似度计算失败: {str(e)}")
            return 0.0
    
    def _get_entity_text_representation(self, entity) -> str:
        """获取实体的文本表示，用于生成embedding"""
        parts = [entity.name]
        
        if entity.type:
            parts.append(f"类型:{entity.type}")
        
        if entity.description:
            parts.append(f"描述:{entity.description}")
        
        return " ".join(parts)
    
    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """计算两个字符串的相似度（基于编辑距离）"""
        if not str1 or not str2:
            return 0.0
        
        # 标准化字符串
        norm_str1 = self._normalize_string(str1)
        norm_str2 = self._normalize_string(str2)
        
        if norm_str1 == norm_str2:
            return 1.0
        
        # 使用difflib计算相似度
        similarity = difflib.SequenceMatcher(None, norm_str1, norm_str2).ratio()
        return float(similarity)
    
    def _calculate_alias_similarity(self, entity1, entity2) -> float:
        """计算别名匹配相似度"""
        aliases1 = getattr(entity1, 'aliases', []) or []
        aliases2 = getattr(entity2, 'aliases', []) or []
        
        # 构建所有可能的名称集合
        names1 = [entity1.name] + aliases1
        names2 = [entity2.name] + aliases2
        
        max_similarity = 0.0
        
        # 计算所有名称组合的最大相似度
        for name1 in names1:
            for name2 in names2:
                sim = self._calculate_string_similarity(name1, name2)
                max_similarity = max(max_similarity, sim)
        
        return max_similarity
    
    def _calculate_description_similarity(self, entity1, entity2) -> float:
        """计算描述相似度"""
        desc1 = getattr(entity1, 'description', '') or ''
        desc2 = getattr(entity2, 'description', '') or ''
        
        if not desc1 or not desc2:
            return 0.0
        
        return self._calculate_string_similarity(desc1, desc2)
    
    def _calculate_context_overlap(self, entity1, entity2) -> float:
        """计算源文本上下文重叠度"""
        context1 = getattr(entity1, 'source_text', '') or ''
        context2 = getattr(entity2, 'source_text', '') or ''
        
        if not context1 or not context2:
            return 0.0
        
        # 提取关键词
        words1 = set(self._extract_keywords(context1))
        words2 = set(self._extract_keywords(context2))
        
        if not words1 or not words2:
            return 0.0
        
        # 计算Jaccard相似度
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _normalize_string(self, text: str) -> str:
        """标准化字符串"""
        # 转小写
        text = text.lower()
        # 移除特殊字符
        text = re.sub(r'[^\w\s]', '', text)
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        # 简单的关键词提取：移除停词，保留长度>2的词
        stop_words = {'的', '是', '在', '了', '和', '与', '或', '但', '然而', '因此', '所以'}
        
        words = re.findall(r'\w+', text.lower())
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        
        return keywords
    
    def _calculate_confidence(self, semantic_sim: float, lexical_sim: float, contextual_sim: float) -> float:
        """
        计算相似度结果的置信度
        
        基于各维度相似度的一致性和分布来评估置信度
        """
        similarities = [semantic_sim, lexical_sim, contextual_sim]
        
        # 计算标准差（一致性指标）
        mean_sim = np.mean(similarities)
        std_sim = np.std(similarities)
        
        # 置信度与一致性成正比，与标准差成反比
        consistency_score = 1.0 - min(std_sim / 0.5, 1.0)  # 标准差越小，一致性越高
        magnitude_score = mean_sim  # 平均相似度越高，置信度越高
        
        confidence = 0.7 * consistency_score + 0.3 * magnitude_score
        
        return max(0.0, min(1.0, confidence))
    
    def _generate_similarity_cache_key(self, entity1, entity2) -> str:
        """生成相似度缓存键"""
        # 确保缓存键的一致性（不考虑实体顺序）
        key1 = f"{entity1.name}_{entity1.type}"
        key2 = f"{entity2.name}_{entity2.type}"
        
        # 按字典序排序，确保相同实体对的缓存键一致
        if key1 <= key2:
            return f"{key1}___{key2}"
        else:
            return f"{key2}___{key1}"
    
    def _clean_similarity_cache(self):
        """清理相似度缓存"""
        # 简单的LRU策略：保留一半缓存
        cache_items = list(self._similarity_cache.items())
        keep_count = len(cache_items) // 2
        
        # 保留后一半（假设更新）
        new_cache = dict(cache_items[-keep_count:])
        self._similarity_cache = new_cache
        
        logger.debug(f"相似度缓存清理完成，保留 {len(self._similarity_cache)} 项")
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0
        
        return {
            "cache_size": len(self._similarity_cache),
            "total_requests": total_requests,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._similarity_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("相似度计算缓存已清空")


# 🆕 集成接口和工厂方法
_similarity_calculator_instance = None

def get_entity_similarity_calculator() -> EntitySimilarityCalculator:
    """
    获取实体相似度计算器实例（单例模式）
    
    Returns:
        EntitySimilarityCalculator: 相似度计算器实例
    """
    global _similarity_calculator_instance
    if _similarity_calculator_instance is None:
        _similarity_calculator_instance = EntitySimilarityCalculator()
    return _similarity_calculator_instance


class EntitySimilarityMatrix:
    """
    实体相似度矩阵构建器
    
    用于批量计算实体间的相似度矩阵，支持大规模实体处理
    """
    
    def __init__(self, calculator: Optional[EntitySimilarityCalculator] = None):
        """初始化相似度矩阵构建器"""
        self.calculator = calculator or get_entity_similarity_calculator()
        logger.info("实体相似度矩阵构建器已初始化")
    
    async def build_similarity_matrix(self, entities: List[Any], 
                                    threshold: float = 0.0,
                                    max_matrix_size: Optional[int] = None) -> Dict[str, Any]:
        """
        构建实体相似度矩阵
        
        Args:
            entities: 实体列表
            threshold: 相似度阈值，低于此值的不计算
            max_matrix_size: 最大矩阵大小限制
            
        Returns:
            包含相似度矩阵和元数据的字典
        """
        import time
        from app.core.config import settings
        
        start_time = time.time()
        n_entities = len(entities)
        max_size = max_matrix_size or settings.ENTITY_UNIFICATION_MAX_MATRIX_SIZE
        
        logger.info(f"开始构建 {n_entities}×{n_entities} 实体相似度矩阵")
        
        # 检查矩阵大小限制
        if n_entities * n_entities > max_size:
            logger.warning(f"矩阵大小 {n_entities}×{n_entities} 超过限制 {max_size}，将进行分块处理")
            return await self._build_large_matrix(entities, threshold, max_size)
        
        # 构建相似度矩阵
        similarity_matrix = {}
        comparison_count = 0
        valid_pairs = 0
        
        try:
            # 批量处理，减少内存使用
            batch_size = min(100, n_entities)
            
            for i in range(0, n_entities, batch_size):
                batch_i_end = min(i + batch_size, n_entities)
                
                for j in range(i, n_entities, batch_size):
                    batch_j_end = min(j + batch_size, n_entities)
                    
                    # 处理当前批次
                    await self._process_matrix_batch(
                        entities, similarity_matrix,
                        i, batch_i_end, j, batch_j_end,
                        threshold
                    )
                    
                    comparison_count += (batch_i_end - i) * (batch_j_end - j)
                    
                    # 内存压力控制
                    if comparison_count % 10000 == 0:
                        logger.debug(f"已处理 {comparison_count} 对实体比较")
            
            # 统计有效相似度对
            valid_pairs = sum(len(similarities) for similarities in similarity_matrix.values())
            
            build_duration = time.time() - start_time
            
            logger.info(f"相似度矩阵构建完成: {comparison_count} 次比较, "
                       f"{valid_pairs} 对有效相似度, 耗时: {build_duration:.3f}秒")
            
            return {
                "matrix": similarity_matrix,
                "metadata": {
                    "entity_count": n_entities,
                    "comparison_count": comparison_count,
                    "valid_pairs": valid_pairs,
                    "threshold": threshold,
                    "build_duration": build_duration,
                    "matrix_density": valid_pairs / (comparison_count / 2) if comparison_count > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"构建相似度矩阵失败: {str(e)}")
            raise
    
    async def _process_matrix_batch(self, entities: List[Any], similarity_matrix: Dict[str, Dict[str, float]],
                                  i_start: int, i_end: int, j_start: int, j_end: int,
                                  threshold: float):
        """处理矩阵批次"""
        tasks = []
        
        for i in range(i_start, i_end):
            entity_i = entities[i]
            entity_i_id = entity_i.id
            
            if entity_i_id not in similarity_matrix:
                similarity_matrix[entity_i_id] = {}
            
            for j in range(max(j_start, i), j_end):  # 只计算上三角矩阵
                if i == j:
                    similarity_matrix[entity_i_id][entities[j].id] = 1.0
                    continue
                
                entity_j = entities[j]
                
                # 创建异步任务
                task = self.calculator.calculate_similarity(entity_i, entity_j)
                tasks.append((i, j, task))
        
        # 批量执行相似度计算
        if tasks:
            results = await asyncio.gather(*[task for _, _, task in tasks], return_exceptions=True)
            
            # 处理结果
            for k, (i, j, _) in enumerate(tasks):
                try:
                    if isinstance(results[k], Exception):
                        logger.warning(f"相似度计算失败: {entities[i].name} <-> {entities[j].name}")
                        continue
                    
                    similarity_result = results[k]
                    total_sim = similarity_result.total_similarity
                    
                    if total_sim >= threshold:
                        entity_i_id = entities[i].id
                        entity_j_id = entities[j].id
                        
                        # 双向存储
                        similarity_matrix[entity_i_id][entity_j_id] = total_sim
                        
                        if entity_j_id not in similarity_matrix:
                            similarity_matrix[entity_j_id] = {}
                        similarity_matrix[entity_j_id][entity_i_id] = total_sim
                        
                except Exception as e:
                    logger.warning(f"处理相似度结果失败: {str(e)}")
                    continue
    
    async def _build_large_matrix(self, entities: List[Any], threshold: float, max_size: int) -> Dict[str, Any]:
        """构建大型相似度矩阵（分块处理）"""
        import math
        
        n_entities = len(entities)
        chunk_size = int(math.sqrt(max_size / 4))  # 保守估算
        
        logger.info(f"使用分块策略构建大型矩阵，分块大小: {chunk_size}")
        
        similarity_matrix = {}
        total_comparisons = 0
        valid_pairs = 0
        
        # 分块处理
        for i in range(0, n_entities, chunk_size):
            i_end = min(i + chunk_size, n_entities)
            chunk_entities = entities[i:i_end]
            
            # 构建当前块的相似度矩阵
            chunk_result = await self.build_similarity_matrix(
                chunk_entities, threshold, max_size
            )
            
            # 合并结果
            chunk_matrix = chunk_result["matrix"]
            for entity_id, similarities in chunk_matrix.items():
                if entity_id not in similarity_matrix:
                    similarity_matrix[entity_id] = {}
                similarity_matrix[entity_id].update(similarities)
            
            total_comparisons += chunk_result["metadata"]["comparison_count"]
            valid_pairs += chunk_result["metadata"]["valid_pairs"]
            
            logger.debug(f"完成分块 {i//chunk_size + 1}/{(n_entities + chunk_size - 1)//chunk_size}")
        
        return {
            "matrix": similarity_matrix,
            "metadata": {
                "entity_count": n_entities,
                "comparison_count": total_comparisons,
                "valid_pairs": valid_pairs,
                "threshold": threshold,
                "chunked_processing": True,
                "chunk_size": chunk_size
            }
        }
    
    def get_top_similar_entities(self, similarity_matrix: Dict[str, Dict[str, float]], 
                               entity_id: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        获取与指定实体最相似的top-k实体
        
        Args:
            similarity_matrix: 相似度矩阵
            entity_id: 目标实体ID
            top_k: 返回的最相似实体数量
            
        Returns:
            [(entity_id, similarity_score), ...] 按相似度降序排列
        """
        if entity_id not in similarity_matrix:
            return []
        
        similarities = similarity_matrix[entity_id]
        
        # 排序并返回top-k
        sorted_similarities = sorted(
            similarities.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        return sorted_similarities[:top_k]


# 🆕 测试和验证函数
async def test_entity_similarity_calculator() -> Dict[str, Any]:
    """
    测试实体相似度计算器的功能
    
    Returns:
        测试结果
    """
    from app.services.knowledge_extraction_service import Entity
    
    test_results = {
        "basic_similarity": False,
        "semantic_similarity": False,
        "lexical_similarity": False,
        "contextual_similarity": False,
        "matrix_construction": False,
        "error_messages": []
    }
    
    try:
        # 创建测试实体
        entity1 = Entity(
            id="test_1",
            name="苹果公司",
            type="组织",
            description="一家美国跨国技术公司",
            properties={},
            confidence=0.9,
            source_text="苹果公司是一家位于加利福尼亚州库比蒂诺的美国跨国技术公司",
            start_pos=0,
            end_pos=10,
            aliases=["Apple Inc.", "Apple", "苹果"]
        )
        
        entity2 = Entity(
            id="test_2", 
            name="Apple Inc.",
            type="组织",
            description="American multinational technology company",
            properties={},
            confidence=0.85,
            source_text="Apple Inc. is an American multinational technology company headquartered in Cupertino, California",
            start_pos=0,
            end_pos=10,
            aliases=["Apple", "苹果公司"]
        )
        
        entity3 = Entity(
            id="test_3",
            name="香港",
            type="地点", 
            description="中国特别行政区",
            properties={},
            confidence=0.8,
            source_text="香港是中华人民共和国的一个特别行政区",
            start_pos=0,
            end_pos=2,
            aliases=["Hong Kong", "HK"]
        )
        
        # 初始化计算器
        calculator = get_entity_similarity_calculator()
        
        # 1. 测试基本相似度计算
        result1 = await calculator.calculate_similarity(entity1, entity2)
        test_results["basic_similarity"] = result1.total_similarity > 0.7  # 相同公司应该高相似度
        
        # 2. 测试语义相似度
        test_results["semantic_similarity"] = result1.semantic_similarity >= 0.0
        
        # 3. 测试词汇相似度  
        test_results["lexical_similarity"] = result1.lexical_similarity > 0.5  # 别名匹配
        
        # 4. 测试上下文相似度
        test_results["contextual_similarity"] = result1.contextual_similarity > 0.5  # 相同类型
        
        # 5. 测试矩阵构建
        matrix_builder = EntitySimilarityMatrix(calculator)
        matrix_result = await matrix_builder.build_similarity_matrix([entity1, entity2, entity3])
        test_results["matrix_construction"] = len(matrix_result["matrix"]) == 3
        
        logger.info("✅ 实体相似度计算器测试通过")
        
    except Exception as e:
        test_results["error_messages"].append(str(e))
        logger.error(f"❌ 实体相似度计算器测试失败: {str(e)}")
    
    return test_results 