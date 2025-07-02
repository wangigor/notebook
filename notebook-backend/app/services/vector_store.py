from typing import List, Dict, Any, Optional
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import DashScopeEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.http.exceptions import UnexpectedResponse
from app.models.memory import VectorStoreConfig, EmbeddingConfig
from app.core.config import settings
from app.services.embedding_service import get_embedding_service
import logging
import time
import json
import hashlib
import httpx
import numpy as np
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

# 添加 VectorStore 类 (为了兼容 document_processor.py 的导入)
class VectorStore:
    """
    向量存储服务
    
    用于存储和检索向量化数据
    """
    
    def __init__(self):
        """初始化向量存储服务"""
        logger.info("初始化向量存储服务")
        self._setup_qdrant_connection()
    
    def _setup_qdrant_connection(self):
        """设置Qdrant连接"""
        self.qdrant_url = settings.QDRANT_URL
        self.qdrant_api_key = settings.QDRANT_API_KEY
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = settings.VECTOR_SIZE
        
        logger.info(f"Qdrant URL: {self.qdrant_url}")
        logger.info(f"Collection name: {self.collection_name}")
        logger.info(f"Vector size: {self.vector_size}")
    
    async def store_document_vectors(self, doc_id: int, content: str) -> Optional[List[str]]:
        """
        存储文档向量
        
        Args:
            doc_id: 文档ID
            content: 文档内容
            
        Returns:
            Optional[List[str]]: 向量ID列表，如果失败则返回None
        """
        logger.info(f"存储文档向量: doc_id={doc_id}")
        
        try:
            # 生成向量
            vectors = await self._generate_embeddings(content)
            if not vectors:
                logger.error("生成向量失败")
                return None
                
            # 存储向量
            vector_ids = await self._store_vectors(doc_id, vectors)
            if not vector_ids:
                logger.error("存储向量失败")
                return None
                
            logger.info(f"成功存储文档向量: vector_count={len(vector_ids)}")
            return vector_ids
            
        except Exception as e:
            logger.exception(f"存储文档向量失败: {str(e)}")
            return None
    
    async def _generate_embeddings(self, content: str) -> Optional[List[List[float]]]:
        """
        生成文本向量嵌入
        
        Args:
            content: 文本内容
            
        Returns:
            Optional[List[List[float]]]: 向量列表，如果失败则返回None
        """
        # 在此处实现向量嵌入生成逻辑
        # 简单示例：生成随机向量（实际应用中请替换为真实的嵌入模型）
        try:
            # 生成简单的随机向量（仅用于测试）
            vector_count = max(1, len(content) // 1000)  # 每1000字符生成一个向量
            vectors = []
            
            for _ in range(vector_count):
                # 生成指定维度的随机向量
                vector = np.random.randn(self.vector_size).tolist()
                vectors.append(vector)
                
            return vectors
            
        except Exception as e:
            logger.exception(f"生成向量嵌入失败: {str(e)}")
            return None
    
    async def _store_vectors(self, doc_id: int, vectors: List[List[float]]) -> Optional[List[str]]:
        """
        存储向量到Qdrant
        
        Args:
            doc_id: 文档ID
            vectors: 向量列表
            
        Returns:
            Optional[List[str]]: 向量ID列表，如果失败则返回None
        """
        # 在此处实现向量存储逻辑
        try:
            # 生成向量ID
            vector_ids = []
            timestamp = datetime.utcnow().isoformat()
            
            for i, vector in enumerate(vectors):
                vector_id = f"doc_{doc_id}_part_{i}_{timestamp}"
                vector_id_hash = hashlib.md5(vector_id.encode()).hexdigest()
                vector_ids.append(vector_id_hash)
            
            # TODO: 实际调用Qdrant API存储向量
            # 这里仅返回生成的ID，实际应用中应调用Qdrant API
            
            return vector_ids
            
        except Exception as e:
            logger.exception(f"存储向量失败: {str(e)}")
            return None
            
# 保留原有的VectorStoreService类
class VectorStoreService:
    """
    向量存储服务
    
    用于存储和检索向量化数据
    """
    
    def __init__(self, force_mock=False):
        """初始化向量存储服务
        
        Args:
            force_mock: 强制使用模拟模式，即使环境变量未设置
        """
        logger.info("初始化向量存储服务")
        # 检查是否应该使用模拟模式
        self.is_mock_mode = force_mock or getattr(settings, 'MOCK_VECTOR_STORE', False)
        logger.info(f"向量存储模式: {'模拟' if self.is_mock_mode else '真实'}")
        
        self.client = None
        self.vector_store = None
        
        if not self.is_mock_mode:
            try:
                self._setup_qdrant_connection()
                self._init_vector_store()
                if self.vector_store is None:
                    logger.warning("初始化真实向量存储失败，切换到模拟模式")
                    self.is_mock_mode = True
            except Exception as e:
                import traceback
                logger.error(f"初始化向量存储服务出错: {str(e)}")
                logger.error(f"错误堆栈: {traceback.format_exc()}")
                logger.warning("由于错误，切换到模拟模式")
                self.is_mock_mode = True
        
    def _setup_qdrant_connection(self):
        """设置Qdrant连接"""
        self.qdrant_url = settings.QDRANT_URL
        self.qdrant_api_key = settings.QDRANT_API_KEY
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        
        logger.info(f"尝试连接到Qdrant: URL={self.qdrant_url}")
        
        # 记录API Key状态
        if not self.qdrant_api_key:
            logger.warning("未配置Qdrant API Key")
        
        # 检查Qdrant服务是否可用
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(self.qdrant_url)
                response.raise_for_status()
                
                # 检查集合列表
                collections_response = client.get(f"{self.qdrant_url}/collections")
                collections_response.raise_for_status()
                
                logger.info("成功连接到Qdrant服务器")
                
                # 检查或创建集合
                self._check_or_create_collection()
                
                # 初始化Qdrant客户端
                self.client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
                logger.info("成功初始化Qdrant客户端")
                
        except Exception as e:
            logger.error(f"连接到Qdrant失败: {str(e)}")
            
    def _init_vector_store(self):
        """初始化向量存储"""
        try:
            if not self.client:
                logger.warning("Qdrant客户端未初始化，尝试重新初始化")
                self.client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
                logger.info(f"重新初始化客户端成功: {self.client}")
            
            # 获取嵌入模型
            logger.info("开始获取嵌入模型...")
            embeddings = self._get_embeddings()
            logger.info(f"成功获取嵌入模型: {embeddings}")
            
            # 初始化向量存储
            logger.info(f"开始初始化QdrantVectorStore，参数: client={self.client}, collection_name={self.collection_name}")
            self.vector_store = QdrantVectorStore(
                client=self.client,
                collection_name=self.collection_name,
                embedding=embeddings
            )
            logger.info(f"成功初始化向量存储: {self.collection_name}")
        except Exception as e:
            import traceback
            logger.error(f"初始化向量存储失败: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            self.vector_store = None
    
    def _check_or_create_collection(self):
        """检查集合是否存在，如果不存在则创建"""
        logger.info(f"检查或创建集合: {self.collection_name}")
        
        try:
            with httpx.Client(timeout=10.0) as client:
                # 获取集合列表
                collections_response = client.get(f"{self.qdrant_url}/collections")
                collections_data = collections_response.json()
                
                # 正确获取collections列表，注意collections位于result字段内
                collection_exists = False
                collections_list = collections_data.get("result", {}).get("collections", [])
                
                for collection in collections_list:
                    if collection.get("name") == self.collection_name:
                        collection_exists = True
                        break
                
                if collection_exists:
                    logger.info(f"集合 {self.collection_name} 已存在")
                    
                    # 获取集合详情
                    collection_response = client.get(f"{self.qdrant_url}/collections/{self.collection_name}")
                    collection_response.raise_for_status()
                    
                    return
                
                # 创建集合
                logger.info(f"创建集合: {self.collection_name}")
                
                create_collection_data = {
                    "name": self.collection_name,
                    "vectors": {
                        "size": settings.VECTOR_SIZE,
                        "distance": "Cosine"
                    }
                }
                
                headers = {}
                if self.qdrant_api_key:
                    headers["api-key"] = self.qdrant_api_key
                
                try:
                    create_response = client.put(
                        f"{self.qdrant_url}/collections/{self.collection_name}",
                        json=create_collection_data,
                        headers=headers
                    )
                    
                    create_response.raise_for_status()
                    logger.info(f"成功创建集合: {self.collection_name}")
                except httpx.HTTPStatusError as e:
                    # 检查是否是409冲突错误（集合已存在）
                    if e.response.status_code == 409:
                        logger.info(f"集合 {self.collection_name} 已经被其他进程创建，继续使用")
                    else:
                        # 其他HTTP错误，重新抛出
                        raise
                
        except Exception as e:
            logger.error(f"检查或创建集合失败: {str(e)}")
    
    async def store_vectors(self, vectors: List[List[float]], metadata: List[Dict[str, Any]]) -> bool:
        """
        存储向量到向量存储
        
        Args:
            vectors: 向量列表
            metadata: 元数据列表
            
        Returns:
            bool: 是否成功
        """
        if len(vectors) != len(metadata):
            logger.error("向量数量与元数据数量不匹配")
            return False
            
        try:
            points = []
            
            for i, (vector, meta) in enumerate(zip(vectors, metadata)):
                point_id = meta.get("id", f"vector_{i}_{datetime.utcnow().timestamp()}")
                
                points.append({
                    "id": point_id,
                    "vector": vector,
                    "payload": meta
                })
            
            # 批量插入向量
            headers = {}
            if self.qdrant_api_key:
                headers["api-key"] = self.qdrant_api_key
                
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    f"{self.qdrant_url}/collections/{self.collection_name}/points",
                    json={"points": points},
                    headers=headers
                )
                
                response.raise_for_status()
                logger.info(f"成功存储 {len(vectors)} 个向量")
                return True
                
        except Exception as e:
            logger.exception(f"存储向量失败: {str(e)}")
            return False
            
    async def search_vectors(self, query_vector: List[float], limit: int = 5, filter_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        搜索相似向量
        
        Args:
            query_vector: 查询向量
            limit: 返回结果数量上限
            filter_params: 过滤参数
            
        Returns:
            List[Dict[str, Any]]: 搜索结果
        """
        try:
            search_request = {
                "vector": query_vector,
                "limit": limit
            }
            
            if filter_params:
                search_request["filter"] = filter_params
                
            headers = {}
            if self.qdrant_api_key:
                headers["api-key"] = self.qdrant_api_key
                
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.qdrant_url}/collections/{self.collection_name}/points/search",
                    json=search_request,
                    headers=headers
                )
                
                response.raise_for_status()
                results = response.json()
                
                return results.get("result", [])
                
        except Exception as e:
            logger.exception(f"搜索向量失败: {str(e)}")
            return []
            
    async def delete_vectors(self, ids: List[str]) -> bool:
        """
        删除向量
        
        Args:
            ids: 向量ID列表
            
        Returns:
            bool: 是否成功
        """
        try:
            delete_request = {
                "points": ids
            }
            
            headers = {}
            if self.qdrant_api_key:
                headers["api-key"] = self.qdrant_api_key
                
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.qdrant_url}/collections/{self.collection_name}/points/delete",
                    json=delete_request,
                    headers=headers
                )
                
                response.raise_for_status()
                logger.info(f"成功删除 {len(ids)} 个向量")
                return True
                
        except Exception as e:
            logger.exception(f"删除向量失败: {str(e)}")
            return False

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
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        为文本生成嵌入向量
        
        Args:
            texts: 要生成嵌入的文本列表
            
        Returns:
            List[List[float]]: 生成的嵌入向量列表
        """
        logger.info(f"生成嵌入向量: {len(texts)} 条文本")
        # 使用统一的嵌入服务
        embedding_service = get_embedding_service()
        return embedding_service.embed_documents(texts)
            
    def _get_embeddings(self):
        """
        获取嵌入模型
        
        Returns:
            embeddings: 嵌入模型实例
        """
        # 使用统一的嵌入服务
        embedding_service = get_embedding_service()
        return embedding_service.embedding_model 