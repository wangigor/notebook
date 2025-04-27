## 三、存储服务实现

### 1. MinIO存储服务
```python
from minio import Minio
from minio.error import S3Error
from app.core.config import settings
import os
import uuid
import tempfile

class StorageService:
    """MinIO对象存储服务"""
    
    def __init__(self):
        """初始化MinIO客户端"""
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,  # 是否使用HTTPS
        )
        self._ensure_buckets_exist()
    
    def _ensure_buckets_exist(self):
        """确保必要的存储桶存在"""
        document_bucket = settings.MINIO_DOCUMENT_BUCKET
        if not self.client.bucket_exists(document_bucket):
            self.client.make_bucket(document_bucket)
            logger.info(f"创建MinIO存储桶: {document_bucket}")
    
    async def upload_file_and_update_document(self, document_id, **kwargs):
        """
        上传文件到MinIO并更新文档记录
        
        参数:
            document_id: 文档ID
            kwargs: 其他参数，包括文件路径
            
        返回:
            上传结果信息
        """
        document_service = get_document_service()
        document = await document_service.get_document_by_id(document_id)
        
        if not document:
            raise ValueError(f"文档不存在: {document_id}")
        
        file_path = kwargs.get("file_path")
        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"文件路径无效: {file_path}")
        
        content_type = kwargs.get("content_type") or document.content_type or "application/octet-stream"
        
        try:
            # 生成唯一对象键
            file_name = os.path.basename(file_path)
            object_key = f"{document.user_id}/{uuid.uuid4()}/{file_name}"
            
            # 上传文件到MinIO
            result = self.client.fput_object(
                bucket_name=settings.MINIO_DOCUMENT_BUCKET,
                object_name=object_key,
                file_path=file_path,
                content_type=content_type
            )
            
            # 获取文件大小
            file_size = os.path.getsize(file_path)
            
            # 更新文档记录
            await document_service.update_document_storage_info(
                document_id=document_id,
                bucket_name=settings.MINIO_DOCUMENT_BUCKET,
                object_key=object_key,
                content_type=content_type,
                file_size=file_size,
                etag=result.etag
            )
            
            return {
                "bucket_name": settings.MINIO_DOCUMENT_BUCKET,
                "object_key": object_key,
                "content_type": content_type,
                "file_size": file_size,
                "etag": result.etag
            }
            
        except S3Error as e:
            logger.error(f"MinIO上传错误: {str(e)}")
            raise Exception(f"文件上传到存储服务失败: {str(e)}")
    
    async def download_to_temp(self, bucket_name, object_key):
        """
        从MinIO下载文件到临时目录
        
        参数:
            bucket_name: 桶名称
            object_key: 对象键
            
        返回:
            临时文件路径
        """
        try:
            # 创建临时文件
            temp_dir = tempfile.mkdtemp()
            file_name = os.path.basename(object_key)
            temp_file_path = os.path.join(temp_dir, file_name)
            
            # 下载文件
            self.client.fget_object(
                bucket_name=bucket_name,
                object_name=object_key,
                file_path=temp_file_path
            )
            
            return temp_file_path
            
        except S3Error as e:
            logger.error(f"MinIO下载错误: {str(e)}")
            raise Exception(f"从存储服务下载文件失败: {str(e)}")
    
    async def generate_presigned_url(self, bucket_name, object_key, expires=3600):
        """
        生成预签名URL用于临时访问
        
        参数:
            bucket_name: 桶名称
            object_key: 对象键
            expires: 过期时间(秒)，默认1小时
            
        返回:
            预签名URL字符串
        """
        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket_name,
                object_name=object_key,
                expires=expires
            )
            return url
        except S3Error as e:
            logger.error(f"生成预签名URL错误: {str(e)}")
            raise Exception(f"生成访问链接失败: {str(e)}")
    
    async def delete_file(self, bucket_name, object_key):
        """
        删除MinIO中的文件
        
        参数:
            bucket_name: 桶名称
            object_key: 对象键
            
        返回:
            删除是否成功
        """
        try:
            self.client.remove_object(
                bucket_name=bucket_name,
                object_name=object_key
            )
            return True
        except S3Error as e:
            logger.error(f"MinIO删除错误: {str(e)}")
            raise Exception(f"删除存储文件失败: {str(e)}")
```

### 2. Qdrant向量存储服务（增强版）
```python
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, ShardingConfig, PlacementStrategy
import uuid

class VectorStoreService:
    """Qdrant向量存储服务"""
    
    def __init__(self, client_config=None):
        """初始化Qdrant客户端"""
        self.client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
    
    def get_user_collection_name(self, user_id):
        """获取用户专属的collection名称"""
        return f"user_{user_id}_docs"
    
    def ensure_user_collection_exists(self, user_id, vector_size=1536):
        """确保用户的collection已创建，并根据文档量判断是否需要分区"""
        collection_name = self.get_user_collection_name(user_id)
        
        # 检查collection是否存在，不存在则创建
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                # 新增：添加分片数量配置，实现向量分区
                sharding_config=ShardingConfig(
                    shard_number=3,  # 初始为3个分片
                    replication_factor=1,
                    placement_strategy=PlacementStrategy.AUTO
                )
            )
            logger.info(f"为用户{user_id}创建了新的向量collection: {collection_name}")
        else:
            # 检查文档数量，超过阈值自动扩展分片
            stats = self.client.get_collection(collection_name)
            points_count = stats.vectors_count
            
            if points_count > 100000 and stats.sharding_config.shard_number < 5:
                # 当向量数超过10万且分片数小于5时，增加分片数量
                self.client.update_collection(
                    collection_name=collection_name,
                    sharding_config=ShardingConfig(
                        shard_number=stats.sharding_config.shard_number + 2,
                        replication_factor=1,
                        placement_strategy=PlacementStrategy.AUTO
                    )
                )
                logger.info(f"用户{user_id}的collection向量量较大，已增加分片数")
        
        return collection_name
    
    async def store_document_vectors(self, document_id, **kwargs):
        """存储文档向量到用户的collection"""
        document_service = get_document_service()
        document = await document_service.get_document_by_id(document_id)
        
        if not document:
            raise ValueError(f"文档不存在: {document_id}")
        
        user_id = document.user_id
        vectors = kwargs.get("vectors")
        
        if not vectors:
            raise ValueError("未找到向量数据")
        
        # 确保用户collection存在
        collection_name = self.ensure_user_collection_exists(user_id)
        
        # 批量添加向量
        self.client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "document_id": document_id,
                        "text": metadata.get("text", ""),
                        "chunk_index": metadata.get("chunk_index", 0),
                        # 新增：存储粒度信息
                        "granularity": metadata.get("granularity", "paragraph"),
                        "metadata": metadata
                    }
                )
                for vector, metadata in vectors
            ]
        )
        
        # 新增：为payload字段创建索引，提升过滤查询性能
        self._ensure_payload_indexes(collection_name)
        
        # 更新文档记录，添加collection信息
        await document_service.update_document_vector_info(
            document_id=document_id,
            vector_collection_name=collection_name,
            vector_count=len(vectors)
        )
        
        return {
            "collection_name": collection_name,
            "vector_count": len(vectors)
        }
    
    def _ensure_payload_indexes(self, collection_name):
        """确保collection有必要的payload索引"""
        try:
            # 创建document_id索引
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="document_id",
                field_schema="integer"
            )
            
            # 创建granularity索引
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="granularity",
                field_schema="keyword"
            )
            
            logger.info(f"为collection {collection_name}创建了payload索引")
        except Exception as e:
            # 索引可能已存在
            logger.debug(f"创建索引时出现异常（可能已存在）: {str(e)}")
``` 