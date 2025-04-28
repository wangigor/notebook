"""
文档处理器模块
负责文档文本提取和向量化处理
"""

import logging
from typing import Dict, Any, Optional

from app.models.document import DocumentStatus
from app.services.document_service import DocumentService
from app.services.text_extraction import TextExtractor
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """
    文档处理器
    
    负责文档的文本提取和向量化流程
    """
    
    def __init__(
        self,
        document_service: DocumentService,
        text_extractor: TextExtractor,
        vector_store: VectorStore
    ):
        """
        初始化文档处理器
        
        Args:
            document_service: 文档服务
            text_extractor: 文本提取器
            vector_store: 向量存储
        """
        self.document_service = document_service
        self.text_extractor = text_extractor
        self.vector_store = vector_store
    
    async def process_document(self, doc_id: int) -> None:
        """
        处理单个文档
        
        Args:
            doc_id: 文档ID（整数）
        """
        logger.info(f"开始处理文档: {doc_id}")
        
        try:
            # 1. 获取文档信息
            document = await self.document_service.get_document(doc_id)
            if not document:
                logger.error(f"文档不存在: {doc_id}")
                return
                
            # 2. 更新文档状态为处理中
            await self.document_service.update_document_status(
                doc_id, 
                DocumentStatus.PROCESSING,
                "文档处理中"
            )
            
            # 3. 提取文档文本
            logger.info(f"提取文档文本: {doc_id}")
            text_content = await self.text_extractor.extract_text(document.file_path)
            
            if not text_content:
                logger.error(f"文档文本提取失败: {doc_id}")
                await self.document_service.update_document_status(
                    doc_id,
                    DocumentStatus.FAILED,
                    "文档文本提取失败"
                )
                return
            
            # 4. 存储文档文本
            logger.info(f"保存文档文本内容: {doc_id}")
            await self.document_service.update_document_content(doc_id, text_content)
            
            # 5. 文档向量化处理
            logger.info(f"文档向量化处理: {doc_id}")
            vector_ids = await self.vector_store.store_document_vectors(doc_id, text_content)
            
            if not vector_ids:
                logger.error(f"文档向量化失败: {doc_id}")
                await self.document_service.update_document_status(
                    doc_id,
                    DocumentStatus.FAILED,
                    "文档向量化失败"
                )
                return
            
            # 6. 更新文档状态为可用
            logger.info(f"文档处理完成: {doc_id}")
            await self.document_service.update_document_status(
                doc_id,
                DocumentStatus.AVAILABLE,
                "文档处理完成"
            )
            
        except Exception as e:
            logger.exception(f"处理文档时发生错误: {str(e)}")
            # 更新文档状态为失败
            try:
                await self.document_service.update_document_status(
                    doc_id,
                    DocumentStatus.FAILED,
                    f"处理失败: {str(e)}"
                )
            except Exception as update_error:
                logger.exception(f"更新文档状态失败: {str(update_error)}") 