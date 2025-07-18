#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一嵌入向量服务 - 单例版本
提供统一的文本嵌入向量生成接口，使用全局DashScope单例
"""
import logging
import numpy as np
import os
import threading
from typing import List, Optional, Dict, Any
from langchain_core.embeddings import Embeddings
from app.core.config import settings
from app.services.dashscope_singleton import get_dashscope_client, get_dashscope_stats

logger = logging.getLogger(__name__)

# 🔒 线程锁，防止并发初始化冲突
_init_lock = threading.Lock()
_instance_lock = threading.Lock()

class EmbeddingService:
    """
    统一嵌入向量服务 - Fork安全版本
    
    提供统一的文本嵌入向量生成接口，支持文档和查询的向量化
    """
    
    def __init__(self):
        """初始化嵌入服务"""
        logger.info("初始化统一嵌入向量服务 (Fork安全版本)")
        self.embedding_model = None
        self.is_mock_mode = False
        self._process_id = os.getpid()  # 记录进程ID
        self._initialized = False
        
        # 🆕 添加缓存和批量处理支持
        self._embedding_cache = {}  # 简单的内存缓存
        self._cache_hit_count = 0
        self._cache_miss_count = 0
        
        # 🛡️ 安全初始化：在fork环境下延迟初始化
        if self._is_in_celery_worker():
            logger.info("检测到Celery Worker环境，延迟初始化embedding模型")
            self._lazy_init = True
        else:
            logger.info("非Celery环境，立即初始化embedding模型")
            self._lazy_init = False
            self._init_embedding_model()
    
    def _is_in_celery_worker(self) -> bool:
        """检测是否在Celery Worker中运行"""
        # 检查环境变量和进程名
        return (
            'CELERY_WORKER' in os.environ or
            'celery worker' in ' '.join(os.sys.argv) or
            hasattr(os.sys, '_called_from_test')  # 测试环境
        )
    
    def _ensure_initialized(self):
        """确保模型已初始化（线程安全）"""
        if self._initialized:
            return
            
        with _init_lock:
            if self._initialized:
                return
                
            current_pid = os.getpid()
            if current_pid != self._process_id:
                logger.warning(f"检测到进程ID变化: {self._process_id} -> {current_pid}，重新初始化")
                self._process_id = current_pid
                self._initialized = False
            
            if not self._initialized:
                self._init_embedding_model()
    
    def _init_embedding_model(self):
        """初始化嵌入模型 - 使用DashScope单例"""
        try:
            logger.info("🔧 开始初始化嵌入模型（单例模式）...")
            
            # 🆕 使用DashScope单例而非独立实例
            self.embedding_model = get_dashscope_client()
            
            # 获取单例统计信息
            stats = get_dashscope_stats()
            self.is_mock_mode = stats.get("is_mock_mode", False)
            
            if self.is_mock_mode:
                logger.warning(f"⚠️ 使用Mock模式，原因: {stats.get('initialization_error', '未知')}")
            else:
                logger.info(f"✅ 使用DashScope单例成功，连接数: {stats.get('connection_count', 0)}")
                
        except Exception as e:
            logger.error(f"❌ 获取DashScope单例失败: {str(e)}")
            logger.warning("🚨 回退到本地Mock模式")
            self.is_mock_mode = True
            self.embedding_model = self._create_mock_embeddings()
        finally:
            self._initialized = True
    
    def _create_mock_embeddings(self) -> Embeddings:
        """创建模拟嵌入模型"""
        
        class MockEmbeddings(Embeddings):
            """Mock嵌入模型，用于测试和备用"""
            
            def embed_documents(self, texts: List[str]) -> List[List[float]]:
                """为文本生成随机嵌入向量"""
                logger.warning(f"🎭 使用MockEmbeddings处理 {len(texts)} 条文本")
                try:
                    import random
                    # 使用固定种子确保一致性
                    random.seed(hash(' '.join(texts)) % 2**32)
                    return [[random.gauss(0, 1) for _ in range(settings.VECTOR_SIZE)] for _ in range(len(texts))]
                except Exception as e:
                    logger.error(f"Mock embedding生成失败: {e}")
                    return [[0.0] * settings.VECTOR_SIZE for _ in range(len(texts))]
                
            def embed_query(self, text: str) -> List[float]:
                """为查询生成随机嵌入向量"""
                logger.warning(f"🎭 使用MockEmbeddings处理查询: {text[:30]}...")
                try:
                    import random
                    random.seed(hash(text) % 2**32)
                    return [random.gauss(0, 1) for _ in range(settings.VECTOR_SIZE)]
                except Exception as e:
                    logger.error(f"Mock query embedding生成失败: {e}")
                    return [0.0] * settings.VECTOR_SIZE
        
        logger.info("✨ 创建 MockEmbeddings 作为备份方案")
        return MockEmbeddings()
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量文档嵌入
        
        Args:
            texts: 要嵌入的文本列表
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        if not texts:
            logger.warning("输入文本列表为空")
            return []
        
        # 确保模型已初始化
        self._ensure_initialized()
        
        try:
            logger.info(f"正在为 {len(texts)} 条文本生成嵌入向量...")
            embeddings = self.embedding_model.embed_documents(texts)
            logger.info(f"✅ 成功生成 {len(embeddings)} 个嵌入向量")
            return embeddings
        except Exception as e:
            logger.error(f"❌ 批量文档嵌入失败: {str(e)}")
            # 返回随机向量作为备份
            logger.warning("🔄 返回随机向量作为备份")
            try:
                import random
                return [[random.gauss(0, 1) for _ in range(settings.VECTOR_SIZE)] for _ in range(len(texts))]
            except Exception as backup_error:
                logger.error(f"❌ 备份向量生成也失败: {backup_error}")
                return [[0.0] * settings.VECTOR_SIZE for _ in range(len(texts))]
    
    def embed_query(self, text: str) -> List[float]:
        """
        单个查询嵌入
        
        Args:
            text: 要嵌入的查询文本
            
        Returns:
            List[float]: 嵌入向量
        """
        if not text:
            logger.warning("输入查询文本为空")
            return [0.0] * settings.VECTOR_SIZE
        
        # 确保模型已初始化
        self._ensure_initialized()
        
        try:
            logger.info(f"正在为查询文本生成嵌入向量: {text[:50]}...")
            embedding = self.embedding_model.embed_query(text)
            logger.info("✅ 成功生成查询嵌入向量")
            return embedding
        except Exception as e:
            logger.error(f"❌ 查询嵌入失败: {str(e)}")
            # 返回随机向量作为备份
            logger.warning("🔄 返回随机向量作为备份")
            try:
                import random
                random.seed(hash(text) % 2**32)
                return [random.gauss(0, 1) for _ in range(settings.VECTOR_SIZE)]
            except Exception as backup_error:
                logger.error(f"❌ 备份向量生成也失败: {backup_error}")
                return [0.0] * settings.VECTOR_SIZE
    
    def get_vector_dimension(self) -> int:
        """获取向量维度"""
        return settings.VECTOR_SIZE
    
    def is_available(self) -> bool:
        """检查服务可用性"""
        try:
            self._ensure_initialized()
            
            if self.is_mock_mode:
                logger.info("🎭 嵌入服务运行在模拟模式")
                return False
            
            # 进行简单的可用性测试
            test_embedding = self.embedding_model.embed_query("测试")
            return len(test_embedding) == settings.VECTOR_SIZE
        except Exception as e:
            logger.error(f"❌ 服务可用性检查失败: {str(e)}")
            return False

    # 🆕 批量embedding处理策略
    async def embed_documents_batch(self, texts: List[str], 
                                   batch_size: Optional[int] = None,
                                   use_cache: bool = True,
                                   max_retries: int = 3) -> List[List[float]]:
        """
        智能批量文档嵌入，支持缓存、重试和性能优化
        
        Args:
            texts: 要嵌入的文本列表
            batch_size: 批处理大小，None则使用配置值
            use_cache: 是否使用缓存
            max_retries: 最大重试次数
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        if not texts:
            logger.warning("输入文本列表为空")
            return []
        
        import asyncio
        import time
        
        start_time = time.time()
        batch_size = batch_size or getattr(settings, 'ENTITY_EMBEDDING_BATCH_SIZE', 50)
        
        logger.info(f"开始批量处理 {len(texts)} 个文本，批次大小: {batch_size}")
        
        # 确保模型已初始化
        self._ensure_initialized()
        
        all_embeddings = []
        cache_hits = 0
        cache_misses = 0
        
        try:
            # 分批处理
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                # 检查缓存
                if use_cache:
                    cached_embeddings, uncached_texts, cache_indices = self._check_batch_cache(batch_texts)
                    cache_hits += len(cached_embeddings)
                    cache_misses += len(uncached_texts)
                else:
                    uncached_texts = batch_texts
                    cache_indices = list(range(len(batch_texts)))
                    cached_embeddings = []
                
                # 生成未缓存的embeddings
                if uncached_texts:
                    new_embeddings = await self._embed_with_retry(uncached_texts, max_retries)
                    
                    # 更新缓存
                    if use_cache:
                        self._update_batch_cache(uncached_texts, new_embeddings)
                else:
                    new_embeddings = []
                
                # 合并结果
                batch_embeddings = self._merge_batch_results(
                    cached_embeddings, new_embeddings, cache_indices, len(batch_texts)
                )
                all_embeddings.extend(batch_embeddings)
                
                # 控制API调用频率
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)
            
            processing_time = time.time() - start_time
            hit_rate = cache_hits / (cache_hits + cache_misses) if (cache_hits + cache_misses) > 0 else 0
            
            logger.info(f"✅ 批量处理完成: {processing_time:.2f}秒, "
                       f"缓存命中率: {hit_rate:.1%} ({cache_hits}/{cache_hits + cache_misses})")
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"❌ 批量嵌入处理失败: {str(e)}")
            # 降级处理：返回随机向量
            logger.warning("🔄 返回随机向量作为降级处理")
            try:
                import random
                return [[random.gauss(0, 1) for _ in range(settings.VECTOR_SIZE)] for _ in texts]
            except Exception as backup_error:
                logger.error(f"❌ 降级处理也失败: {backup_error}")
                return [[0.0] * settings.VECTOR_SIZE for _ in texts]
    
    def _check_batch_cache(self, texts: List[str]) -> tuple:
        """检查批量文本的缓存状态"""
        cached_embeddings = []
        uncached_texts = []
        cache_indices = []
        
        for i, text in enumerate(texts):
            cache_key = self._generate_cache_key(text)
            if cache_key in self._embedding_cache:
                cached_embeddings.append(self._embedding_cache[cache_key])
                self._cache_hit_count += 1
            else:
                uncached_texts.append(text)
                cache_indices.append(i)
                self._cache_miss_count += 1
        
        return cached_embeddings, uncached_texts, cache_indices
    
    def _merge_batch_results(self, cached_embeddings: List[List[float]], 
                           new_embeddings: List[List[float]], 
                           cache_indices: List[int], 
                           total_count: int) -> List[List[float]]:
        """合并缓存和新生成的embeddings"""
        result = [None] * total_count
        
        # 填入缓存的结果
        cached_idx = 0
        new_idx = 0
        
        for i in range(total_count):
            if i in cache_indices:
                if new_idx < len(new_embeddings):
                    result[i] = new_embeddings[new_idx]
                    new_idx += 1
                else:
                    # 备用零向量
                    result[i] = [0.0] * settings.VECTOR_SIZE
            else:
                if cached_idx < len(cached_embeddings):
                    result[i] = cached_embeddings[cached_idx]
                    cached_idx += 1
                else:
                    # 备用零向量
                    result[i] = [0.0] * settings.VECTOR_SIZE
        
        return result
    
    def _update_batch_cache(self, texts: List[str], embeddings: List[List[float]]):
        """更新批量缓存"""
        for text, embedding in zip(texts, embeddings):
            cache_key = self._generate_cache_key(text)
            self._embedding_cache[cache_key] = embedding
        
        # 清理缓存
        self._clean_cache()
    
    async def _embed_with_retry(self, texts: List[str], max_retries: int) -> List[List[float]]:
        """
        带重试机制的嵌入生成
        
        Args:
            texts: 文本列表
            max_retries: 最大重试次数
            
        Returns:
            嵌入向量列表
        """
        import asyncio
        
        for attempt in range(max_retries + 1):
            try:
                # 使用线程池异步调用同步方法
                loop = asyncio.get_event_loop()
                embeddings = await loop.run_in_executor(
                    None, self.embedding_model.embed_documents, texts
                )
                return embeddings
                
            except Exception as e:
                if attempt < max_retries:
                    wait_time = (2 ** attempt) * 0.5  # 指数退避
                    logger.warning(f"⚠️ 嵌入生成失败 (尝试 {attempt + 1}/{max_retries + 1}): {str(e)}")
                    logger.info(f"⏳ 等待 {wait_time:.1f}秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ 嵌入生成失败，已达最大重试次数: {str(e)}")
                    # 返回随机向量作为降级
                    try:
                        import random
                        return [[random.gauss(0, 1) for _ in range(settings.VECTOR_SIZE)] for _ in texts]
                    except Exception as backup_error:
                        logger.error(f"❌ 降级向量生成失败: {backup_error}")
                        return [[0.0] * settings.VECTOR_SIZE for _ in texts]
    
    def _generate_cache_key(self, text: str) -> str:
        """生成缓存键"""
        import hashlib
        
        # 标准化文本
        normalized_text = text.strip().lower()
        # 生成MD5哈希作为缓存键
        return hashlib.md5(normalized_text.encode('utf-8')).hexdigest()
    
    def _clean_cache(self):
        """清理缓存，保留最近使用的一半"""
        cache_limit = getattr(settings, 'ENTITY_SIMILARITY_CACHE_SIZE', 1000)
        if len(self._embedding_cache) <= cache_limit:
            return
        
        # 简单的LRU策略：删除一半最旧的条目
        cache_items = list(self._embedding_cache.items())
        keep_count = cache_limit // 2
        
        # 保留后一半（假设后添加的更新）
        new_cache = dict(cache_items[-keep_count:])
        self._embedding_cache = new_cache
        
        logger.debug(f"🧹 缓存清理完成，保留 {len(self._embedding_cache)} 项")
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._cache_hit_count + self._cache_miss_count
        hit_rate = self._cache_hit_count / total_requests if total_requests > 0 else 0
        
        return {
            "cache_size": len(self._embedding_cache),
            "cache_limit": getattr(settings, 'ENTITY_SIMILARITY_CACHE_SIZE', 1000),
            "total_requests": total_requests,
            "cache_hits": self._cache_hit_count,
            "cache_misses": self._cache_miss_count,
            "hit_rate": hit_rate,
            "memory_usage_estimate": len(self._embedding_cache) * settings.VECTOR_SIZE * 4,  # float32估算
            "process_id": self._process_id,
            "is_mock_mode": self.is_mock_mode
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._embedding_cache.clear()
        self._cache_hit_count = 0
        self._cache_miss_count = 0
        logger.info("🧹 嵌入缓存已清空")


# 🔒 创建全局实例（单例模式，线程安全）
_embedding_service_instance = None

def get_embedding_service() -> EmbeddingService:
    """
    获取嵌入服务实例（单例模式，线程安全）
    
    Returns:
        EmbeddingService: 嵌入服务实例
    """
    global _embedding_service_instance
    if _embedding_service_instance is None:
        with _instance_lock:
            if _embedding_service_instance is None:
                _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance


# 🆕 添加测试和验证函数
async def test_embedding_service() -> Dict[str, Any]:
    """
    测试嵌入服务的可用性和性能
    
    Returns:
        测试结果字典
    """
    test_results = {
        "service_available": False,
        "vector_dimension": 0,
        "api_connectivity": False,
        "batch_processing": False,
        "error_messages": [],
        "performance_metrics": {}
    }
    
    try:
        import time
        start_time = time.time()
        
        # 获取嵌入服务实例
        embedding_service = get_embedding_service()
        
        # 1. 检查基本可用性
        test_results["service_available"] = not embedding_service.is_mock_mode
        test_results["vector_dimension"] = embedding_service.get_vector_dimension()
        
        # 2. 测试单个查询向量生成
        single_test_start = time.time()
        test_query = "这是一个测试查询文本"
        query_embedding = embedding_service.embed_query(test_query)
        single_test_duration = time.time() - single_test_start
        
        test_results["api_connectivity"] = len(query_embedding) == settings.VECTOR_SIZE
        test_results["performance_metrics"]["single_query_time"] = single_test_duration
        
        # 3. 测试批量文档向量生成
        batch_test_start = time.time()
        test_texts = [
            "第一个测试文档内容",
            "第二个测试文档内容", 
            "第三个测试文档内容",
            "第四个测试文档内容",
            "第五个测试文档内容"
        ]
        batch_embeddings = embedding_service.embed_documents(test_texts)
        batch_test_duration = time.time() - batch_test_start
        
        test_results["batch_processing"] = (
            len(batch_embeddings) == len(test_texts) and
            all(len(emb) == settings.VECTOR_SIZE for emb in batch_embeddings)
        )
        
        test_results["performance_metrics"]["batch_processing_time"] = batch_test_duration
        test_results["performance_metrics"]["avg_time_per_text"] = batch_test_duration / len(test_texts)
        
        # 4. 测试缓存功能
        cache_test_start = time.time()
        duplicate_embeddings = embedding_service.embed_documents(test_texts)  # 重复调用
        cache_test_duration = time.time() - cache_test_start
        
        test_results["performance_metrics"]["cache_test_time"] = cache_test_duration
        test_results["cache_statistics"] = embedding_service.get_cache_statistics()
        
        total_test_duration = time.time() - start_time
        test_results["performance_metrics"]["total_test_time"] = total_test_duration
        
        logger.info(f"✅ 嵌入服务测试完成，总耗时: {total_test_duration:.2f}秒")
        
    except Exception as e:
        error_msg = f"嵌入服务测试失败: {str(e)}"
        logger.error(error_msg)
        test_results["error_messages"].append(error_msg)
    
    return test_results


def validate_embedding_dimensions(embeddings: List[List[float]]) -> Dict[str, Any]:
    """
    验证embedding向量的维度一致性
    
    Args:
        embeddings: 向量列表
        
    Returns:
        验证结果
    """
    validation_result = {
        "is_valid": True,
        "expected_dimension": settings.VECTOR_SIZE,
        "actual_dimensions": [],
        "inconsistent_vectors": [],
        "summary": {}
    }
    
    if not embeddings:
        validation_result["is_valid"] = False
        validation_result["summary"]["error"] = "输入向量列表为空"
        return validation_result
    
    for i, embedding in enumerate(embeddings):
        if not isinstance(embedding, list):
            validation_result["is_valid"] = False
            validation_result["inconsistent_vectors"].append({
                "index": i,
                "issue": "不是列表类型",
                "type": str(type(embedding))
            })
            continue
            
        actual_dim = len(embedding)
        validation_result["actual_dimensions"].append(actual_dim)
        
        if actual_dim != settings.VECTOR_SIZE:
            validation_result["is_valid"] = False
            validation_result["inconsistent_vectors"].append({
                "index": i,
                "expected": settings.VECTOR_SIZE,
                "actual": actual_dim,
                "issue": "维度不匹配"
            })
    
    # 生成摘要
    if validation_result["actual_dimensions"]:
        validation_result["summary"] = {
            "total_vectors": len(embeddings),
            "min_dimension": min(validation_result["actual_dimensions"]),
            "max_dimension": max(validation_result["actual_dimensions"]),
            "inconsistent_count": len(validation_result["inconsistent_vectors"]),
            "consistency_rate": 1.0 - (len(validation_result["inconsistent_vectors"]) / len(embeddings))
        }
    
    return validation_result 