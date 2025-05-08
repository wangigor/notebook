"""
文本提取服务模块

负责从不同类型的文件中提取文本内容
"""

import os
import logging
from io import BytesIO
from typing import Optional, Union, BinaryIO

logger = logging.getLogger(__name__)

class TextExtractor:
    """
    文本提取器
    
    用于从不同类型的文件中提取文本内容
    """
    
    def __init__(self):
        """初始化文本提取器"""
        logger.info("初始化文本提取器")
    
    async def extract_text(self, file_path: str) -> Optional[str]:
        """
        从文件中提取文本
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[str]: 提取的文本内容，如果提取失败则返回None
        """
        logger.info(f"开始从文件提取文本: {file_path}")
        
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return None
                
            # 获取文件扩展名
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # 读取文件内容
            with open(file_path, 'rb') as f:
                content = f.read()
                
            # 根据文件类型调用不同的提取方法
            if file_ext in ['.txt', '.md', '.json', '.csv']:
                # 文本文件
                return self._extract_from_text_file(content)
                
            elif file_ext in ['.pdf']:
                # PDF文件
                return self._extract_from_pdf(content)
                
            elif file_ext in ['.doc', '.docx']:
                # Word文档
                return self._extract_from_word(content)
                
            elif file_ext in ['.xls', '.xlsx']:
                # Excel文件
                return self._extract_from_excel(content)
                
            elif file_ext in ['.html', '.htm']:
                # HTML文件
                return self._extract_from_html(content)
                
            else:
                # 未知类型，尝试作为文本处理
                logger.warning(f"未知文件类型: {file_ext}，尝试作为文本处理")
                return content.decode('utf-8', errors='ignore')
                
        except Exception as e:
            logger.exception(f"提取文本时出错: {str(e)}")
            return None
    
    def _extract_from_text_file(self, content: bytes) -> str:
        """
        从文本文件中提取文本
        
        Args:
            content: 文件内容
            
        Returns:
            str: 提取的文本
        """
        return content.decode('utf-8', errors='ignore')
    
    def _extract_from_pdf(self, content: bytes) -> str:
        """
        从PDF文件中提取文本
        
        Args:
            content: 文件内容
            
        Returns:
            str: 提取的文本
        """
        try:
            import PyPDF2
            
            pdf_reader = PyPDF2.PdfReader(BytesIO(content))
            text = ""
            
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
                
            return text
        except ImportError:
            logger.warning("PyPDF2模块未安装，无法提取PDF文本")
            return "PDF文本提取失败（PyPDF2模块未安装）"
        except Exception as e:
            logger.error(f"PDF提取文本错误: {str(e)}")
            return f"PDF文本提取失败: {str(e)}"
    
    def _extract_from_word(self, content: bytes) -> str:
        """
        从Word文档中提取文本
        
        Args:
            content: 文件内容
            
        Returns:
            str: 提取的文本
        """
        try:
            import docx
            
            doc = docx.Document(BytesIO(content))
            text = ""
            
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
                
            return text
        except ImportError:
            logger.warning("python-docx模块未安装，无法提取Word文本")
            return "Word文本提取失败（python-docx模块未安装）"
        except Exception as e:
            logger.error(f"Word提取文本错误: {str(e)}")
            return f"Word文本提取失败: {str(e)}"
    
    def _extract_from_excel(self, content: bytes) -> str:
        """
        从Excel文件中提取文本
        
        Args:
            content: 文件内容
            
        Returns:
            str: 提取的文本
        """
        try:
            import openpyxl
            
            workbook = openpyxl.load_workbook(BytesIO(content))
            text = ""
            
            for sheet in workbook:
                text += f"Sheet: {sheet.title}\n"
                
                for row in sheet.iter_rows(values_only=True):
                    text += "\t".join([str(cell) if cell is not None else "" for cell in row]) + "\n"
            
            return text
        except ImportError:
            logger.warning("openpyxl模块未安装，无法提取Excel文本")
            return "Excel文本提取失败（openpyxl模块未安装）"
        except Exception as e:
            logger.error(f"Excel提取文本错误: {str(e)}")
            return f"Excel文本提取失败: {str(e)}"
    
    def _extract_from_html(self, content: bytes) -> str:
        """
        从HTML文件中提取文本
        
        Args:
            content: 文件内容
            
        Returns:
            str: 提取的文本
        """
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # 移除script和style元素
            for script in soup(["script", "style"]):
                script.extract()
                
            # 获取文本
            text = soup.get_text()
            
            # 分割成行并清理
            lines = (line.strip() for line in text.splitlines())
            # 分割多行
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # 去除空行
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
        except ImportError:
            logger.warning("BeautifulSoup模块未安装，无法提取HTML文本")
            return "HTML文本提取失败（BeautifulSoup模块未安装）"
        except Exception as e:
            logger.error(f"HTML提取文本错误: {str(e)}")
            return f"HTML文本提取失败: {str(e)}" 