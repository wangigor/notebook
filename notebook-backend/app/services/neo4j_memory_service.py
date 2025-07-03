from typing import Dict, Any, List, Optional
from app.models.memory import ConversationHistory, MemoryConfig
from app.services.neo4j_graph_service import Neo4jGraphService

class Neo4jMemoryService:
    """Neo4j图谱记忆服务 - 直接替换MemoryService"""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.graph_service = Neo4jGraphService()  # 使用Neo4j替代向量存储
        self.histories: Dict[str, ConversationHistory] = {}
    
    def get_conversation_history(self, session_id: str) -> ConversationHistory:
        """获取会话历史"""
        if session_id not in self.histories:
            self.histories[session_id] = ConversationHistory()
        return self.histories[session_id]
    
    def add_user_message(self, session_id: str, message: str) -> None:
        """添加用户消息"""
        history = self.get_conversation_history(session_id)
        history.add_user_message(message)
    
    def add_ai_message(self, session_id: str, message: str) -> None:
        """添加AI消息"""
        history = self.get_conversation_history(session_id)
        history.add_ai_message(message)
    
    def get_relevant_documents(self, query: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取相关文档 - 使用Neo4j混合搜索"""
        if k is None:
            k = self.config.k
        
        # 直接使用Neo4j图谱检索
        return self.graph_service.similarity_search(query, k=k)
    
    def get_context_for_query(self, session_id: str, query: str) -> Dict[str, Any]:
        """获取查询上下文"""
        # 获取会话历史
        history = self.get_conversation_history(session_id)
        history_text = self._format_history(history)
        
        # 获取相关文档（使用Neo4j混合搜索）
        documents = self.get_relevant_documents(query)
        
        return {
            "history": history_text,
            "documents": documents,
            "raw_documents": documents
        }
    
    def _format_history(self, history: ConversationHistory) -> str:
        """格式化历史记录"""
        formatted = ""
        for message in history.messages[-10:]:  # 最近10条消息
            role = "用户" if message.role == "user" else "助手"
            formatted += f"{role}: {message.content}\n"
        return formatted
    
    def add_documents(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """添加文档到知识库"""
        return self.graph_service.add_texts(texts, metadatas or [{}] * len(texts)) 