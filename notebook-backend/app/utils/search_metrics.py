"""
搜索性能监控工具类
提供混合搜索过程中的性能指标收集和分析功能
"""
import time
import psutil
import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)

@dataclass
class SearchMetrics:
    """搜索性能指标数据类"""
    session_id: str
    query_text: str
    start_time: float
    end_time: Optional[float] = None
    
    # 性能指标
    total_duration: float = 0.0
    vector_search_duration: float = 0.0
    result_processing_duration: float = 0.0
    
    # 内存指标
    memory_baseline_mb: float = 0.0
    memory_peak_mb: float = 0.0
    memory_delta_mb: float = 0.0
    
    # 结果质量指标
    results_count: int = 0
    avg_score: float = 0.0
    score_distribution: List[float] = field(default_factory=list)
    
    # 数据统计
    entities_count: int = 0
    relationships_count: int = 0
    total_content_length: int = 0
    
    # 搜索模式
    search_mode: str = "hybrid"
    fallback_used: bool = False
    fallback_reason: str = ""

class SearchMetricsCollector:
    """搜索性能指标收集器"""
    
    def __init__(self):
        self.active_searches: Dict[str, SearchMetrics] = {}
        self.completed_searches: List[SearchMetrics] = []
        self.process = psutil.Process(os.getpid())
        
    def start_search(self, session_id: str, query_text: str) -> SearchMetrics:
        """开始搜索性能监控"""
        metrics = SearchMetrics(
            session_id=session_id,
            query_text=query_text,
            start_time=time.time(),
            memory_baseline_mb=self.process.memory_info().rss / 1024 / 1024
        )
        
        self.active_searches[session_id] = metrics
        
        logger.debug(f"[SEARCH_METRICS] search_started | session_id={session_id} | memory_baseline={metrics.memory_baseline_mb:.2f}MB")
        return metrics
    
    def record_vector_search_complete(self, session_id: str, duration: float, results_count: int):
        """记录向量搜索完成"""
        if session_id in self.active_searches:
            metrics = self.active_searches[session_id]
            metrics.vector_search_duration = duration
            metrics.results_count = results_count
            
            logger.debug(f"[SEARCH_METRICS] vector_search_complete | session_id={session_id} | duration={duration:.3f}s | results={results_count}")
    
    def record_fallback(self, session_id: str, reason: str):
        """记录搜索降级"""
        if session_id in self.active_searches:
            metrics = self.active_searches[session_id]
            metrics.fallback_used = True
            metrics.fallback_reason = reason
            metrics.search_mode = "fallback"
            
            logger.warning(f"[SEARCH_METRICS] search_fallback | session_id={session_id} | reason={reason}")
    
    def record_result_quality(self, session_id: str, results: List[Dict[str, Any]]):
        """记录结果质量指标"""
        if session_id not in self.active_searches:
            return
            
        metrics = self.active_searches[session_id]
        
        # 提取分数分布
        scores = []
        total_entities = 0
        total_relationships = 0
        total_content_length = 0
        
        for result in results:
            score = result.get("metadata", {}).get("score", 0.0)
            scores.append(score)
            
            # 统计实体和关系
            entities = result.get("metadata", {}).get("entities", {})
            total_entities += len(entities.get("entityids", []))
            total_relationships += len(entities.get("relationshipids", []))
            
            # 统计内容长度
            content = result.get("content", "")
            total_content_length += len(content)
        
        metrics.score_distribution = scores
        metrics.avg_score = statistics.mean(scores) if scores else 0.0
        metrics.entities_count = total_entities
        metrics.relationships_count = total_relationships
        metrics.total_content_length = total_content_length
        
        logger.debug(f"[SEARCH_METRICS] result_quality | session_id={session_id} | avg_score={metrics.avg_score:.3f} | entities={total_entities} | relationships={total_relationships}")
    
    def finish_search(self, session_id: str) -> Optional[SearchMetrics]:
        """完成搜索性能监控"""
        if session_id not in self.active_searches:
            return None
            
        metrics = self.active_searches[session_id]
        metrics.end_time = time.time()
        metrics.total_duration = metrics.end_time - metrics.start_time
        
        # 计算内存使用
        current_memory = self.process.memory_info().rss / 1024 / 1024
        metrics.memory_peak_mb = current_memory
        metrics.memory_delta_mb = current_memory - metrics.memory_baseline_mb
        
        # 移动到已完成列表
        self.completed_searches.append(metrics)
        del self.active_searches[session_id]
        
        logger.info(f"[SEARCH_METRICS] search_completed | session_id={session_id} | total_duration={metrics.total_duration:.3f}s | memory_delta={metrics.memory_delta_mb:.2f}MB")
        return metrics
    
    def get_performance_summary(self, last_n: int = 10) -> Dict[str, Any]:
        """获取性能摘要统计"""
        if not self.completed_searches:
            return {}
            
        recent_searches = self.completed_searches[-last_n:]
        
        # 计算统计指标
        durations = [s.total_duration for s in recent_searches]
        memory_deltas = [s.memory_delta_mb for s in recent_searches]
        avg_scores = [s.avg_score for s in recent_searches if s.avg_score > 0]
        
        fallback_count = sum(1 for s in recent_searches if s.fallback_used)
        
        summary = {
            "search_count": len(recent_searches),
            "avg_duration": statistics.mean(durations) if durations else 0.0,
            "max_duration": max(durations) if durations else 0.0,
            "min_duration": min(durations) if durations else 0.0,
            "avg_memory_delta": statistics.mean(memory_deltas) if memory_deltas else 0.0,
            "avg_result_score": statistics.mean(avg_scores) if avg_scores else 0.0,
            "fallback_rate": fallback_count / len(recent_searches) if recent_searches else 0.0,
            "total_entities": sum(s.entities_count for s in recent_searches),
            "total_relationships": sum(s.relationships_count for s in recent_searches),
        }
        
        logger.info(f"[SEARCH_METRICS] performance_summary | searches={summary['search_count']} | avg_duration={summary['avg_duration']:.3f}s | fallback_rate={summary['fallback_rate']:.2%}")
        
        return summary
    
    def analyze_quality_trends(self) -> Dict[str, Any]:
        """分析结果质量趋势"""
        if len(self.completed_searches) < 5:
            return {"message": "insufficient_data"}
            
        recent_10 = self.completed_searches[-10:]
        previous_10 = self.completed_searches[-20:-10] if len(self.completed_searches) >= 20 else []
        
        analysis = {
            "recent_avg_score": statistics.mean([s.avg_score for s in recent_10 if s.avg_score > 0]) if recent_10 else 0.0,
            "recent_avg_entities": statistics.mean([s.entities_count for s in recent_10]),
            "recent_fallback_rate": sum(1 for s in recent_10 if s.fallback_used) / len(recent_10),
        }
        
        if previous_10:
            analysis.update({
                "previous_avg_score": statistics.mean([s.avg_score for s in previous_10 if s.avg_score > 0]),
                "score_trend": "improving" if analysis["recent_avg_score"] > statistics.mean([s.avg_score for s in previous_10 if s.avg_score > 0]) else "declining",
                "fallback_trend": "improving" if analysis["recent_fallback_rate"] < sum(1 for s in previous_10 if s.fallback_used) / len(previous_10) else "declining"
            })
        
        logger.info(f"[SEARCH_METRICS] quality_analysis | avg_score={analysis['recent_avg_score']:.3f} | fallback_rate={analysis['recent_fallback_rate']:.2%}")
        
        return analysis

# 全局指标收集器实例
search_metrics_collector = SearchMetricsCollector()

def get_search_metrics_collector() -> SearchMetricsCollector:
    """获取全局搜索指标收集器"""
    return search_metrics_collector 