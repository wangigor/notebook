"""
文档加载器模块
负责使用LangChain加载各种格式的文档
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class BaseDocumentLoader(ABC):
    """文档加载器基类"""
    
    @abstractmethod
    def load(self, file_path: str) -> Dict[str, Any]:
        """加载文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            解析结果字典
        """
        pass

class LangChainDocumentLoader(BaseDocumentLoader):
    """LangChain文档加载器"""
    
    def __init__(self):
        """初始化LangChain文档加载器"""
        try:
            from langchain_community.document_loaders import PyMuPDFLoader, UnstructuredFileLoader
            self.pdf_loader = PyMuPDFLoader
            self.unstructured_loader = UnstructuredFileLoader
            logger.info("LangChain文档加载器初始化成功")
        except ImportError as e:
            logger.error(f"LangChain文档加载器初始化失败: {str(e)}")
            raise
    
    def load(self, file_path: str) -> Dict[str, Any]:
        """加载文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            解析结果字典
        """
        try:
            file_path = str(Path(file_path).resolve())
            file_ext = Path(file_path).suffix.lower()
            
            logger.info(f"开始加载文档: {file_path}, 类型: {file_ext}")
            
            if file_ext == '.pdf':
                loader = self.pdf_loader(file_path)
            else:
                loader = self.unstructured_loader(file_path)
                
            documents = loader.load()
            result = self._process_documents(documents)
            
            logger.info(f"文档加载完成: {file_path}")
            return result
            
        except Exception as e:
            logger.error(f"文档加载失败: {file_path}, 错误: {str(e)}")
            raise
    
    def _process_documents(self, documents: List[Any]) -> Dict[str, Any]:
        """处理文档内容
        
        Args:
            documents: LangChain文档列表
            
        Returns:
            处理后的文档内容
        """
        try:
            # 合并所有文档内容
            content = "\n\n".join([doc.page_content for doc in documents])
            
            # 提取元数据
            metadata = {}
            if documents and hasattr(documents[0], 'metadata'):
                metadata = documents[0].metadata
            
            return {
                'content': content,
                'metadata': metadata,
                'page_count': len(documents)
            }
            
        except Exception as e:
            logger.error(f"文档处理失败: {str(e)}")
            raise 