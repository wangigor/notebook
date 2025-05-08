# -*- coding: utf-8 -*-
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from app.core.config import settings # 导入settings


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
    """嵌入模型配置 (从settings获取)"""
    model: str = Field(default=settings.DASHSCOPE_EMBEDDING_MODEL)
    api_key: Optional[str] = Field(default=settings.DASHSCOPE_API_KEY, description="DashScope API Key")
    
    # 移除 model_config，因为不再直接定义 model_name
    # model_config = {
    #     "protected_namespaces": () 
    # }


class VectorStoreConfig(BaseModel):
    """向量存储配置 (从settings获取)"""
    url: str = Field(default=settings.QDRANT_URL)
    api_key: Optional[str] = Field(default=settings.QDRANT_API_KEY)
    collection_name: str = Field(default=settings.QDRANT_COLLECTION_NAME)
    embedding_config: EmbeddingConfig = Field(default_factory=EmbeddingConfig)


class MemoryConfig(BaseModel):
    """记忆配置 (从settings获取)"""
    max_token_limit: int = Field(default=settings.AGENT_MAX_TOKEN_LIMIT)
    vector_store_config: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    return_messages: bool = Field(default=settings.AGENT_RETURN_MESSAGES)
    return_source_documents: bool = Field(default=settings.AGENT_RETURN_SOURCE_DOCUMENTS)
    k: int = Field(default=settings.AGENT_K) # 返回的相似文档数量 