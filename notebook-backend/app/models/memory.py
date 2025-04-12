from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, validator


class Message(BaseModel):
    """对话消息模型"""
    role: str
    content: str


class ConversationHistory(BaseModel):
    """对话历史记录"""
    messages: List[Message] = Field(default_factory=list)
    
    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append(Message(role="user", content=content))
    
    def add_ai_message(self, content: str) -> None:
        """添加AI消息"""
        self.messages.append(Message(role="assistant", content=content))
    
    def get_history_as_string(self, k: Optional[int] = None) -> str:
        """获取历史记录字符串
        
        Args:
            k: 最近k轮对话，None表示所有对话
        """
        history = self.messages
        if k is not None:
            history = history[-2*k:]
        
        result = ""
        for message in history:
            result += f"{message.role}: {message.content}\n"
        return result


class EmbeddingConfig(BaseModel):
    """嵌入模型配置"""
    model_name: str = "text-embedding-v1"
    api_key: Optional[str] = Field(None, description="DashScope API Key")


class VectorStoreConfig(BaseModel):
    """向量存储配置"""
    url: str = "http://wangigor.ddns.net:30063" 
    api_key: Optional[str] = None
    collection_name: str = "knowledge_base"
    embedding_config: EmbeddingConfig = Field(default_factory=EmbeddingConfig)


class MemoryConfig(BaseModel):
    """记忆配置"""
    max_token_limit: int = 2000
    vector_store_config: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    return_messages: bool = True
    return_source_documents: bool = True
    k: int = 5  # 返回的相似文档数量 