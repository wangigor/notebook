from typing import List, Dict, Any, Optional
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import DashScopeEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from app.models.memory import VectorStoreConfig, EmbeddingConfig
import os


class VectorStoreService:
    """向量存储服务"""
    
    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self.client = self._create_client()
        self.embedding = self._create_embeddings()
        self.vector_store = self._create_vector_store()
        
    def _create_client(self) -> QdrantClient:
        """创建Qdrant客户端"""
        return QdrantClient(
            url=self.config.url,
            api_key=self.config.api_key
        )
    
    def _create_embeddings(self) -> DashScopeEmbeddings:
        """创建嵌入模型"""
        embedding_config = self.config.embedding_config
        api_key = os.getenv("DASHSCOPE_API_KEY") or embedding_config.api_key
        if not api_key:
            raise ValueError("DashScope API Key is required. Please set it in environment variable DASHSCOPE_API_KEY or in EmbeddingConfig.")
            
        return DashScopeEmbeddings(
            model=embedding_config.model_name,
            dashscope_api_key=api_key
        )
    
    def _create_vector_store(self) -> QdrantVectorStore:
        """创建向量存储"""
        # 检查集合是否存在，不存在则创建
        collections = self.client.get_collections().collections
        collection_names = [collection.name for collection in collections]
        
        if self.config.collection_name not in collection_names:
            # 获取嵌入维度
            embedding_dimension = len(self.embedding.embed_query("test"))
            
            self.client.create_collection(
                collection_name=self.config.collection_name,
                vectors_config=VectorParams(
                    size=embedding_dimension,
                    distance=Distance.COSINE
                )
            )
        
        return QdrantVectorStore(
            client=self.client,
            collection_name=self.config.collection_name,
            embedding=self.embedding
        )
    
    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """添加文本到向量存储
        
        Args:
            texts: 要添加的文本列表
            metadatas: 元数据列表，与texts一一对应
            
        Returns:
            文档ID列表
        """
        return self.vector_store.add_texts(texts=texts, metadatas=metadatas)
    
    def similarity_search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """相似度搜索
        
        Args:
            query: 查询文本
            k: 返回的文档数量
            
        Returns:
            相似文档列表
        """
        docs = self.vector_store.similarity_search(query, k=k)
        results = []
        
        for doc in docs:
            results.append({
                "content": doc.page_content,
                "metadata": doc.metadata
            })
            
        return results 