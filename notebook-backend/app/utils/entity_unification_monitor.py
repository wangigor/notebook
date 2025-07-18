# -*- coding: utf-8 -*-
"""
实体统一监控工具
提供详细的性能监控、日志增强和度量收集功能
"""
import logging
import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


@dataclass
class UnificationMetrics:
    """统一指标"""
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    
    # 输入统计
    input_entity_count: int = 0
    input_avg_quality: float = 0.0
    
    # 处理阶段耗时
    preprocessing_time: float = 0.0
    embedding_time: float = 0.0
    similarity_matrix_time: float = 0.0
    clustering_time: float = 0.0
    merging_time: float = 0.0
    
    # 输出统计
    output_entity_count: int = 0
    merge_operation_count: int = 0
    reduction_rate: float = 0.0
    
    # 质量指标
    avg_merge_confidence: float = 0.0
    conflict_count: int = 0
    error_count: int = 0
    
    # 性能指标
    total_processing_time: float = 0.0
    entities_per_second: float = 0.0
    cache_hit_rate: float = 0.0
    memory_usage_mb: float = 0.0


class EntityUnificationMonitor:
    """实体统一监控器"""
    
    def __init__(self):
        """初始化监控器"""
        self._metrics_history = []
        self._current_session = None
        self._lock = threading.Lock()
        
        # 配置详细的日志格式
        self._setup_detailed_logging()
        
        logger.info("🔍 实体统一监控器已启动")
    
    def _setup_detailed_logging(self):
        """配置详细的日志格式"""
        # 创建专门的统一日志记录器
        self.unification_logger = logging.getLogger("entity_unification")
        self.unification_logger.setLevel(logging.DEBUG)
        
        # 避免重复添加handler
        if not self.unification_logger.handlers:
            # 创建格式化器
            formatter = logging.Formatter(
                '[%(asctime)s] 🔗 UNIFICATION | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # 创建控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.INFO)
            
            self.unification_logger.addHandler(console_handler)
            self.unification_logger.propagate = False
    
    def start_session(self, session_id: Optional[str] = None) -> str:
        """开始新的统一会话"""
        if session_id is None:
            session_id = f"unification_{int(time.time() * 1000)}"
        
        with self._lock:
            self._current_session = UnificationMetrics(
                session_id=session_id,
                start_time=time.time()
            )
        
        self.unification_logger.info(f"📊 开始统一会话: {session_id}")
        return session_id
    
    def log_preprocessing_start(self, entity_count: int):
        """记录预处理开始"""
        if self._current_session:
            self._current_session.input_entity_count = entity_count
            
        self.unification_logger.info(f"🔄 预处理阶段开始 | 输入实体数量: {entity_count}")
    
    def log_preprocessing_complete(self, valid_entity_count: int, duration: float):
        """记录预处理完成"""
        if self._current_session:
            self._current_session.preprocessing_time = duration
            
        reduction = self._current_session.input_entity_count - valid_entity_count if self._current_session else 0
        
        self.unification_logger.info(
            f"✅ 预处理完成 | 有效实体: {valid_entity_count} | "
            f"过滤: {reduction} | 耗时: {duration:.3f}s"
        )
    
    def log_embedding_start(self, entities_need_embedding: int):
        """记录embedding开始"""
        self.unification_logger.info(f"🧠 Embedding生成开始 | 需处理实体: {entities_need_embedding}")
    
    def log_embedding_complete(self, successful_count: int, duration: float, cache_hit_rate: float):
        """记录embedding完成"""
        if self._current_session:
            self._current_session.embedding_time = duration
            self._current_session.cache_hit_rate = cache_hit_rate
        
        self.unification_logger.info(
            f"✅ Embedding生成完成 | 成功: {successful_count} | "
            f"耗时: {duration:.3f}s | 缓存命中率: {cache_hit_rate:.1%}"
        )
    
    def log_similarity_matrix_start(self, entity_count: int):
        """记录相似度矩阵构建开始"""
        matrix_size = entity_count * entity_count
        self.unification_logger.info(f"📐 相似度矩阵构建开始 | 实体数: {entity_count} | 矩阵大小: {matrix_size}")
    
    def log_similarity_matrix_complete(self, comparison_count: int, valid_pairs: int, duration: float):
        """记录相似度矩阵构建完成"""
        if self._current_session:
            self._current_session.similarity_matrix_time = duration
        
        density = valid_pairs / comparison_count if comparison_count > 0 else 0
        
        self.unification_logger.info(
            f"✅ 相似度矩阵完成 | 比较次数: {comparison_count} | "
            f"有效相似度对: {valid_pairs} | 密度: {density:.1%} | 耗时: {duration:.3f}s"
        )
    
    def log_clustering_start(self, threshold: float):
        """记录聚类开始"""
        self.unification_logger.info(f"🔗 聚类分析开始 | 阈值: {threshold:.3f}")
    
    def log_clustering_complete(self, cluster_count: int, duration: float):
        """记录聚类完成"""
        if self._current_session:
            self._current_session.clustering_time = duration
        
        self.unification_logger.info(f"✅ 聚类分析完成 | 发现聚类: {cluster_count} | 耗时: {duration:.3f}s")
    
    def log_merge_operation(self, primary_entity_name: str, secondary_entity_name: str, 
                          decision: str, similarity_score: float, conflicts: int):
        """记录单次合并操作"""
        conflict_indicator = "⚠️" if conflicts > 0 else "✅"
        
        self.unification_logger.debug(
            f"{conflict_indicator} 合并操作 | {primary_entity_name} + {secondary_entity_name} | "
            f"决策: {decision} | 相似度: {similarity_score:.3f} | 冲突: {conflicts}"
        )
    
    def log_merging_complete(self, merge_count: int, conflict_count: int, duration: float):
        """记录合并阶段完成"""
        if self._current_session:
            self._current_session.merging_time = duration
            self._current_session.merge_operation_count = merge_count
            self._current_session.conflict_count = conflict_count
        
        self.unification_logger.info(
            f"✅ 实体合并完成 | 合并操作: {merge_count} | "
            f"冲突处理: {conflict_count} | 耗时: {duration:.3f}s"
        )
    
    def log_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """记录错误"""
        if self._current_session:
            self._current_session.error_count += 1
        
        context_str = f" | 上下文: {json.dumps(context, ensure_ascii=False)}" if context else ""
        
        self.unification_logger.error(f"❌ {error_type} | {error_message}{context_str}")
    
    def complete_session(self, output_entity_count: int, avg_merge_confidence: float) -> UnificationMetrics:
        """完成统一会话"""
        if not self._current_session:
            logger.warning("没有活跃的统一会话")
            return None
        
        with self._lock:
            # 完成会话
            self._current_session.end_time = time.time()
            self._current_session.output_entity_count = output_entity_count
            self._current_session.avg_merge_confidence = avg_merge_confidence
            
            # 计算总体指标
            self._current_session.total_processing_time = (
                self._current_session.end_time - self._current_session.start_time
            )
            
            if self._current_session.input_entity_count > 0:
                self._current_session.reduction_rate = (
                    (self._current_session.input_entity_count - output_entity_count) / 
                    self._current_session.input_entity_count
                )
                
                self._current_session.entities_per_second = (
                    self._current_session.input_entity_count / 
                    max(self._current_session.total_processing_time, 0.001)
                )
            
            # 记录会话完成
            metrics = self._current_session
            self._metrics_history.append(metrics)
            
            # 记录详细的会话总结
            self._log_session_summary(metrics)
            
            # 清空当前会话
            self._current_session = None
            
            return metrics
    
    def _log_session_summary(self, metrics: UnificationMetrics):
        """记录会话总结"""
        self.unification_logger.info("="*80)
        self.unification_logger.info(f"📋 统一会话总结 | {metrics.session_id}")
        self.unification_logger.info("="*80)
        
        # 基础统计
        self.unification_logger.info(f"📊 基础统计:")
        self.unification_logger.info(f"  └─ 输入实体: {metrics.input_entity_count}")
        self.unification_logger.info(f"  └─ 输出实体: {metrics.output_entity_count}")
        self.unification_logger.info(f"  └─ 减少率: {metrics.reduction_rate:.1%}")
        self.unification_logger.info(f"  └─ 合并操作: {metrics.merge_operation_count}")
        
        # 处理时间分析
        self.unification_logger.info(f"⏱️ 处理时间分析:")
        self.unification_logger.info(f"  └─ 总时间: {metrics.total_processing_time:.3f}s")
        self.unification_logger.info(f"  └─ 预处理: {metrics.preprocessing_time:.3f}s ({metrics.preprocessing_time/metrics.total_processing_time*100:.1f}%)")
        self.unification_logger.info(f"  └─ Embedding: {metrics.embedding_time:.3f}s ({metrics.embedding_time/metrics.total_processing_time*100:.1f}%)")
        self.unification_logger.info(f"  └─ 相似度矩阵: {metrics.similarity_matrix_time:.3f}s ({metrics.similarity_matrix_time/metrics.total_processing_time*100:.1f}%)")
        self.unification_logger.info(f"  └─ 聚类分析: {metrics.clustering_time:.3f}s ({metrics.clustering_time/metrics.total_processing_time*100:.1f}%)")
        self.unification_logger.info(f"  └─ 实体合并: {metrics.merging_time:.3f}s ({metrics.merging_time/metrics.total_processing_time*100:.1f}%)")
        
        # 质量指标
        self.unification_logger.info(f"🎯 质量指标:")
        self.unification_logger.info(f"  └─ 平均合并置信度: {metrics.avg_merge_confidence:.3f}")
        self.unification_logger.info(f"  └─ 处理速度: {metrics.entities_per_second:.1f} 实体/秒")
        self.unification_logger.info(f"  └─ 缓存命中率: {metrics.cache_hit_rate:.1%}")
        self.unification_logger.info(f"  └─ 冲突数量: {metrics.conflict_count}")
        self.unification_logger.info(f"  └─ 错误数量: {metrics.error_count}")
        
        self.unification_logger.info("="*80)
    
    def get_performance_report(self, last_n_sessions: int = 10) -> Dict[str, Any]:
        """获取性能报告"""
        if not self._metrics_history:
            return {"error": "没有历史数据"}
        
        recent_sessions = self._metrics_history[-last_n_sessions:]
        
        # 计算平均指标
        avg_reduction_rate = sum(m.reduction_rate for m in recent_sessions) / len(recent_sessions)
        avg_processing_time = sum(m.total_processing_time for m in recent_sessions) / len(recent_sessions)
        avg_entities_per_second = sum(m.entities_per_second for m in recent_sessions) / len(recent_sessions)
        avg_merge_confidence = sum(m.avg_merge_confidence for m in recent_sessions) / len(recent_sessions)
        avg_cache_hit_rate = sum(m.cache_hit_rate for m in recent_sessions) / len(recent_sessions)
        
        total_entities_processed = sum(m.input_entity_count for m in recent_sessions)
        total_merges = sum(m.merge_operation_count for m in recent_sessions)
        total_conflicts = sum(m.conflict_count for m in recent_sessions)
        total_errors = sum(m.error_count for m in recent_sessions)
        
        return {
            "sessions_analyzed": len(recent_sessions),
            "total_entities_processed": total_entities_processed,
            "averages": {
                "reduction_rate": avg_reduction_rate,
                "processing_time": avg_processing_time,
                "entities_per_second": avg_entities_per_second,
                "merge_confidence": avg_merge_confidence,
                "cache_hit_rate": avg_cache_hit_rate
            },
            "totals": {
                "merge_operations": total_merges,
                "conflicts_resolved": total_conflicts,
                "errors_encountered": total_errors
            },
            "latest_session": asdict(recent_sessions[-1]) if recent_sessions else None
        }
    
    def export_metrics_history(self, filepath: str):
        """导出指标历史"""
        import json
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([asdict(m) for m in self._metrics_history], f, 
                     ensure_ascii=False, indent=2)
        
        logger.info(f"指标历史已导出到: {filepath}")


# 🆕 全局监控器实例
_unification_monitor_instance = None

def get_unification_monitor() -> EntityUnificationMonitor:
    """获取统一监控器实例（单例模式）"""
    global _unification_monitor_instance
    if _unification_monitor_instance is None:
        _unification_monitor_instance = EntityUnificationMonitor()
    return _unification_monitor_instance 