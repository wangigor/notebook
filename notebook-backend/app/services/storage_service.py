"""
存储服务 - 提供MinIO对象存储服务接口
"""
import logging
from typing import Optional
import os
from minio import Minio
from minio.error import S3Error
from fastapi import HTTPException
from app.core.config import settings

logger = logging.getLogger(__name__)

class StorageService:
    """存储服务接口"""
    
    def __init__(self):
        """初始化MinIO客户端"""
        try:
            self.client = Minio(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            logger.info(f"初始化MinIO客户端成功: {settings.MINIO_ENDPOINT}")
            
            # 初始化存储桶
            self._init_buckets()
        except Exception as e:
            logger.error(f"初始化MinIO客户端失败: {str(e)}")
            self.client = None
    
    def _init_buckets(self):
        """初始化存储桶"""
        try:
            # 创建文档桶
            if not self.client.bucket_exists(settings.DOCUMENT_BUCKET):
                self.client.make_bucket(settings.DOCUMENT_BUCKET)
                logger.info(f"创建文档存储桶: {settings.DOCUMENT_BUCKET}")
        except Exception as e:
            logger.error(f"初始化存储桶失败: {str(e)}")
    
    async def upload_file(self, file_path: str, bucket_name: str, object_name: str, content_type: Optional[str] = None) -> bool:
        """
        上传文件到MinIO
        
        参数:
            file_path: 本地文件路径
            bucket_name: 存储桶名称
            object_name: 对象名称
            content_type: 内容类型
            
        返回:
            是否上传成功
        """
        if not self.client:
            logger.error("MinIO客户端未初始化")
            return False
        
        try:
            # 获取文件大小
            file_size = os.path.getsize(file_path)
            
            # 如果未指定内容类型，尝试根据文件扩展名推断
            if not content_type:
                file_ext = os.path.splitext(file_path)[1].lower()
                content_type = self._get_content_type(file_ext)
            
            logger.info(f"上传文件到MinIO: {bucket_name}/{object_name}, 大小: {file_size}, 类型: {content_type}")
            
            # 上传文件
            self.client.fput_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=file_path,
                content_type=content_type
            )
            
            logger.info(f"文件上传成功: {bucket_name}/{object_name}")
            return True
        except Exception as e:
            logger.error(f"上传文件到MinIO失败: {str(e)}")
            return False
    
    async def download_file(self, bucket_name: str, object_name: str, file_path: str) -> bool:
        """
        从MinIO下载文件
        
        参数:
            bucket_name: 存储桶名称
            object_name: 对象名称
            file_path: 本地文件路径
            
        返回:
            是否下载成功
        """
        if not self.client:
            logger.error("MinIO客户端未初始化")
            return False
        
        try:
            logger.info(f"从MinIO下载文件: {bucket_name}/{object_name} 到 {file_path}")
            
            # 下载文件
            self.client.fget_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=file_path
            )
            
            logger.info(f"文件下载成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"从MinIO下载文件失败: {str(e)}")
            return False
    
    async def generate_presigned_url(self, bucket_name: str, object_name: str, expires: int = 3600) -> str:
        """
        生成预签名URL，用于临时访问文件
        
        参数:
            bucket_name: 存储桶名称
            object_name: 对象名称
            expires: 过期时间（秒），默认1小时
            
        返回:
            预签名URL
        """
        if not self.client:
            logger.error("MinIO客户端未初始化")
            raise HTTPException(status_code=500, detail="存储服务未初始化")
        
        try:
            logger.info(f"生成预签名URL: {bucket_name}/{object_name}, 过期时间: {expires}秒")
            
            # 生成预签名URL
            url = self.client.presigned_get_object(
                bucket_name=bucket_name,
                object_name=object_name,
                expires=expires
            )
            
            logger.info(f"预签名URL生成成功")
            return url
        except Exception as e:
            logger.error(f"生成预签名URL失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"生成预签名URL失败: {str(e)}")
    
    async def delete_object(self, bucket_name: str, object_name: str) -> bool:
        """
        删除MinIO中的对象
        
        参数:
            bucket_name: 存储桶名称
            object_name: 对象名称
            
        返回:
            是否删除成功
        """
        if not self.client:
            logger.error("MinIO客户端未初始化")
            return False
        
        try:
            logger.info(f"删除MinIO对象: {bucket_name}/{object_name}")
            
            # 删除对象
            self.client.remove_object(
                bucket_name=bucket_name,
                object_name=object_name
            )
            
            logger.info(f"对象删除成功: {bucket_name}/{object_name}")
            return True
        except Exception as e:
            logger.error(f"删除MinIO对象失败: {str(e)}")
            return False
    
    def _get_content_type(self, file_ext: str) -> str:
        """
        根据文件扩展名获取内容类型
        
        参数:
            file_ext: 文件扩展名
            
        返回:
            内容类型
        """
        content_types = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".json": "application/json",
            ".md": "text/markdown",
            ".html": "text/html",
            ".htm": "text/html",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".zip": "application/zip",
            ".rar": "application/x-rar-compressed",
            ".tar": "application/x-tar"
        }
        
        return content_types.get(file_ext, "application/octet-stream") 