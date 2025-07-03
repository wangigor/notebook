from typing import Dict, Any, List, Optional
from app.models.memory import ConversationHistory, MemoryConfig
from app.services.neo4j_graph_service import Neo4jGraphService
import time
import logging


class MemoryService:
    """记忆服务"""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.vector_store = Neo4jGraphService()
        self.histories: Dict[str, ConversationHistory] = {}
    
    def get_conversation_history(self, session_id: str) -> ConversationHistory:
        """获取会话历史
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话历史
        """
        if session_id not in self.histories:
            self.histories[session_id] = ConversationHistory()
        
        return self.histories[session_id]
    
    def add_user_message(self, session_id: str, message: str) -> None:
        """添加用户消息
        
        Args:
            session_id: 会话ID
            message: 用户消息
        """
        history = self.get_conversation_history(session_id)
        history.add_user_message(message)
    
    def add_ai_message(self, session_id: str, message: str) -> None:
        """添加AI消息
        
        Args:
            session_id: 会话ID
            message: AI消息
        """
        history = self.get_conversation_history(session_id)
        history.add_ai_message(message)
    
    def get_relevant_documents(self, query: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取相关文档
        
        Args:
            query: 查询文本
            k: 返回的文档数量
            
        Returns:
            相关文档列表
        """
        logger = logging.getLogger(__name__)
        
        if k is None:
            k = self.config.k
        
        # [HYBRID_SEARCH_PERF] 记录检索请求参数
        retrieval_start_time = time.time()
        logger.info(f"[HYBRID_SEARCH_PERF] document_retrieval_start | duration=0.000s | query_length={len(query)} | k_value={k}")
        logger.debug(f"[HYBRID_SEARCH_DATA] retrieval_request | query_text={query[:100]}{'...' if len(query) > 100 else ''} | config_k={self.config.k}")
        
        # 调用图服务进行相似度搜索
        results = self.vector_store.similarity_search(query, k=k)
        
        # 记录检索结果
        retrieval_duration = time.time() - retrieval_start_time
        logger.info(f"[HYBRID_SEARCH_PERF] document_retrieval_complete | duration={retrieval_duration:.3f}s | results_count={len(results)}")
        
        # 通知搜索指标收集器向量搜索完成
        from app.utils.search_metrics import get_search_metrics_collector
        metrics_collector = get_search_metrics_collector()
        # 注意：这里使用query作为session_id的近似，实际应用中可能需要传递真实的session_id
        metrics_collector.record_vector_search_complete(query[:50], retrieval_duration, len(results))
            
        return results
    
    def get_context_for_query(self, session_id: str, query: str) -> Dict[str, Any]:
        """获取查询的上下文
        
        Args:
            session_id: 会话ID
            query: 查询文本
            
        Returns:
            包含历史记录和相关文档的上下文
        """
        # 获取会话历史
        history = self.get_conversation_history(session_id)
        history_text = history.get_history_as_string()
        
        # 获取相关文档
        documents = self.get_relevant_documents(query)
        
        return {
            "history": history_text,
            "documents": documents
        }
        
    def add_documents(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """添加文档到向量存储
        
        Args:
            texts: 文本列表
            metadatas: 元数据列表
            
        Returns:
            文档ID列表
        """
        return self.vector_store.add_texts(texts, metadatas) 