"""
文档解析器模块
负责解析各种格式的文档并提取结构化信息
"""

import logging
import os
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.services.document_loader import LangChainDocumentLoader

logger = logging.getLogger(__name__)

class DocumentStructure:
    """文档结构类"""
    
    def __init__(self):
        self.title: Optional[str] = None
        self.headings: List[Dict[str, Any]] = []
        self.paragraphs: List[Dict[str, Any]] = []
        self.tables: List[Dict[str, Any]] = []
        self.lists: List[Dict[str, Any]] = []
        self.images: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}

class DocumentParser:
    """文档解析器"""
    
    def __init__(self):
        """初始化文档解析器"""
        self.loader = LangChainDocumentLoader()
        logger.info("文档解析器初始化完成")
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """解析文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            解析结果
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            logger.info(f"开始解析文档: {file_path}")
            
            # 加载文档
            result = self.loader.load(file_path)
            
            # 提取元数据
            result['file_info'] = self._extract_file_metadata(file_path)
            result['parse_timestamp'] = datetime.utcnow().isoformat()
            
            # 分析文档结构
            result['structure'] = self._analyze_structure(result['content'])
            
            logger.info(f"文档解析完成: {file_path}")
            return result
            
        except Exception as e:
            logger.error(f"文档解析失败: {file_path}, 错误: {str(e)}")
            logger.error(f"异常调用栈:\n{traceback.format_exc()}")
            raise
    
    def _extract_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """提取文件元数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件元数据
        """
        file_stat = os.stat(file_path)
        return {
            'file_name': os.path.basename(file_path),
            'file_path': file_path,
            'file_size': file_stat.st_size,
            'file_extension': Path(file_path).suffix.lower(),
            'created_time': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
            'modified_time': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
        }
    
    def _analyze_structure(self, content: str) -> DocumentStructure:
        """分析文档结构
        
        Args:
            content: 文档内容
            
        Returns:
            文档结构
        """
        structure = DocumentStructure()
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测标题
            if self._is_likely_heading(line):
                structure.headings.append({
                    'text': line,
                    'level': self._estimate_heading_level(line),
                    'type': 'detected_heading'
                })
            else:
                # 检测列表项
                if self._is_list_item(line):
                    structure.lists.append({
                        'text': line,
                        'type': 'list_item'
                    })
                else:
                    # 普通段落
                    structure.paragraphs.append({
                        'text': line,
                        'type': 'paragraph'
                    })
        
        return structure
    
    def _is_likely_heading(self, line: str) -> bool:
        """判断是否可能是标题
        
        Args:
            line: 文本行
            
        Returns:
            是否是标题
        """
        if len(line) < 5 or len(line) > 100:
            return False
        
        # 全大写可能是标题
        if line.isupper() and len(line.split()) <= 10:
            return True
        
        # 数字开头可能是章节标题
        if line.startswith(('第', 'Chapter', 'Section')) or line[0].isdigit():
            return True
        
        # 短句且没有标点符号可能是标题
        if len(line) <= 50 and not line.endswith(('.', '!', '?', '。', '！', '？')):
            return True
        
        return False
    
    def _estimate_heading_level(self, line: str) -> int:
        """估计标题级别
        
        Args:
            line: 标题文本
            
        Returns:
            标题级别
        """
        if len(line) <= 20:
            return 1
        elif len(line) <= 40:
            return 2
        else:
            return 3
    
    def _is_list_item(self, line: str) -> bool:
        """判断是否是列表项
        
        Args:
            line: 文本行
            
        Returns:
            是否是列表项
        """
        # 检查常见的列表标记
        list_markers = ['•', '·', '-', '*', '+', '→', '>']
        if any(line.startswith(marker) for marker in list_markers):
            return True
        
        # 检查数字列表
        if line[0].isdigit() and line[1:2] in ['.', '、', ')']:
            return True
        
        return False 