from typing import List, Dict, Any, Optional
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import DashScopeEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.http.exceptions import UnexpectedResponse
from app.models.memory import VectorStoreConfig, EmbeddingConfig
from app.core.config import settings
import logging
import time

# 配置日志
logger = logging.getLogger(__name__)

class VectorStoreService:
    """向量存储服务"""
    
    def __init__(self):
        self.is_mock_mode = False
        
        # 初始化Dashscope Embedding
        try:
            self.embedding = DashScopeEmbeddings(
                model=settings.DASHSCOPE_EMBEDDING_MODEL,
                dashscope_api_key=settings.DASHSCOPE_API_KEY
            )
            if not settings.DASHSCOPE_API_KEY:
                logger.warning("未配置DashScope API Key，Embedding功能可能受限")
        except Exception as e:
            logger.error(f"初始化DashScopeEmbeddings失败: {str(e)}")
            raise
        
        # 初始化Qdrant客户端
        try:
            logger.info(f"尝试连接到Qdrant: URL={settings.QDRANT_URL}")
            self.client = QdrantClient(
                url=settings.QDRANT_URL, 
                api_key=settings.QDRANT_API_KEY,
                timeout=settings.QDRANT_TIMEOUT
            )
            if not settings.QDRANT_API_KEY:
                logger.warning("未配置Qdrant API Key")
                
            # 测试连接
            if not self._test_connection():
                raise ConnectionError("无法连接到Qdrant服务器")
                
        except Exception as e:
            logger.warning(f"连接到Qdrant服务器失败: {str(e)}. 切换到本地模拟模式.")
            self.is_mock_mode = True
        
        # 初始化向量存储
        if not self.is_mock_mode:
            try:
                self.vector_store = self._create_vector_store()
            except Exception as e:
                logger.error(f"创建向量存储失败: {str(e)}. 切换到本地模拟模式.")
                self.is_mock_mode = True
    
    def _test_connection(self):
        """测试Qdrant连接"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # 尝试简单的API调用
                self.client.get_collections()
                logger.info("成功连接到Qdrant服务器")
                return True
            except UnexpectedResponse as e:
                 if e.status_code == 401: # 处理认证错误
                    logger.error("Qdrant认证失败: 请检查API Key")
                    return False
                 logger.warning(f"Qdrant连接尝试 {attempt+1}/{max_retries} 失败 (HTTP {e.status_code}): {e.content.decode() if e.content else '无内容'}")
            except Exception as e:
                logger.warning(f"Qdrant连接尝试 {attempt+1}/{max_retries} 失败: {str(e)}")
                
            if attempt < max_retries - 1:
                logger.info(f"在 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
        
        logger.error(f"在 {max_retries} 次尝试后无法连接到Qdrant服务器")
        return False
        
    def _create_vector_store(self) -> Optional[QdrantVectorStore]:
        """创建向量存储"""
        if self.is_mock_mode:
            logger.info("在模拟模式下运行，不创建真实向量存储")
            return None
            
        try:
            logger.info(f"检查或创建集合: {settings.QDRANT_COLLECTION_NAME}")
            collections = self.client.get_collections().collections
            collection_names = [collection.name for collection in collections]
            
            if settings.QDRANT_COLLECTION_NAME not in collection_names:
                # 获取嵌入维度
                logger.info("获取嵌入维度...")
                embedding_dimension = len(self.embedding.embed_query("test"))
                logger.info(f"嵌入维度: {embedding_dimension}")
                
                logger.info(f"创建集合: {settings.QDRANT_COLLECTION_NAME}")
                self.client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=embedding_dimension,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"集合 {settings.QDRANT_COLLECTION_NAME} 创建成功")
            else:
                logger.info(f"集合 {settings.QDRANT_COLLECTION_NAME} 已存在")
            
            return QdrantVectorStore(
                client=self.client,
                collection_name=settings.QDRANT_COLLECTION_NAME,
                embedding=self.embedding
            )
        except Exception as e:
            logger.error(f"创建向量存储出错: {str(e)}", exc_info=True)
            self.is_mock_mode = True
            return None
    
    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """添加文本到向量存储
        
        Args:
            texts: 要添加的文本列表
            metadatas: 元数据列表，与texts一一对应
            
        Returns:
            文档ID列表
        """
        if self.is_mock_mode:
            logger.info(f"模拟模式: 添加 {len(texts)} 条文本")
            return [f"mock-id-{i}" for i in range(len(texts))]
            
        if not self.vector_store:
            logger.error("向量存储未初始化，无法添加文本")
            return []
            
        try:
            logger.info(f"向向量存储添加 {len(texts)} 条文本...")
            result = self.vector_store.add_texts(texts=texts, metadatas=metadatas)
            logger.info(f"成功添加 {len(result)} 条文本")
            return result
        except Exception as e:
            logger.error(f"添加文本到向量存储出错: {str(e)}", exc_info=True)
            return [f"error-id-{i}" for i in range(len(texts))]
    
    def delete_texts(self, ids: List[str]) -> bool:
        """从向量存储中删除文本
        
        Args:
            ids: 要删除的文档ID列表
            
        Returns:
            是否成功删除
        """
        if self.is_mock_mode:
            logger.info(f"模拟模式: 删除 {len(ids)} 条文本")
            return True
            
        if not self.client:
            logger.error("Qdrant客户端未初始化，无法删除文本")
            return False
            
        try:
            # 将ID转换为字符串列表，以防是Point ID
            string_ids = [str(doc_id) for doc_id in ids]
            logger.info(f"从集合 {settings.QDRANT_COLLECTION_NAME} 删除 {len(string_ids)} 个文档...")
            
            # 使用Qdrant客户端删除点
            response = self.client.delete(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points_selector={"ids": string_ids}
            )
            logger.info(f"删除操作响应: {response.status}")
            return response.status == "completed"
        except Exception as e:
            logger.error(f"删除向量存储文档出错: {str(e)}", exc_info=True)
            return False
    
    def similarity_search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """相似度搜索
        
        Args:
            query: 查询文本
            k: 返回的文档数量
            
        Returns:
            相似文档列表
        """
        if self.is_mock_mode:
            logger.info(f"模拟模式: 执行相似度搜索, 查询: '{query}'")
            # 返回模拟结果
            return [
                {
                    "content": f"模拟文档内容 {i}，相关查询: {query}",
                    "metadata": {"source": f"模拟来源{i}", "doc_id": f"mock-doc-{i}"}
                }
                for i in range(min(k, settings.AGENT_K)) # 使用配置的K值
            ]
            
        if not self.vector_store:
            logger.error("向量存储未初始化，无法执行相似度搜索")
            return []
            
        try:
            logger.info(f"执行相似度搜索: 查询='{query[:30]}...', k={k}")
            docs = self.vector_store.similarity_search(query, k=k)
            results = []
            
            for doc in docs:
                results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata
                })
            logger.info(f"相似度搜索找到 {len(results)} 个结果")
            return results
        except Exception as e:
            logger.error(f"相似度搜索出错: {str(e)}", exc_info=True)
            # 如果出错，返回一个空的结果
            return [] 