import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

logger = logging.getLogger(__name__)

@dataclass
class ChunkMetadata:
    """分块元数据"""
    chunk_id: str
    document_id: Optional[int] = None
    postgresql_document_id: Optional[int] = None
    neo4j_document_node_id: Optional[str] = None
    chunk_index: int = 0
    start_char: int = 0
    end_char: int = 0
    content_length: int = 0
    word_count: int = 0
    paragraph_count: int = 0
    heading_level: Optional[int] = None
    section_title: Optional[str] = None
    chunk_type: str = "content"  # content, heading, table, list
    overlap_start: int = 0
    overlap_end: int = 0
    created_at: str = ""
    embedding: Optional[List[float]] = None  # 嵌入向量
    vector_dimension: Optional[int] = None  # 向量维度
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'postgresql_document_id': self.postgresql_document_id,
            'neo4j_document_node_id': self.neo4j_document_node_id,
            'chunk_index': self.chunk_index,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'content_length': self.content_length,
            'word_count': self.word_count,
            'paragraph_count': self.paragraph_count,
            'heading_level': self.heading_level,
            'section_title': self.section_title,
            'chunk_type': self.chunk_type,
            'overlap_start': self.overlap_start,
            'overlap_end': self.overlap_end,
            'created_at': self.created_at,
            'embedding': self.embedding,
            'vector_dimension': self.vector_dimension
        }

@dataclass
class DocumentChunk:
    """文档分块"""
    content: str
    metadata: ChunkMetadata
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'content': self.content,
            'metadata': self.metadata.to_dict()
        }
    
    def set_embedding(self, embedding: List[float]) -> None:
        """设置嵌入向量
        
        Args:
            embedding: 嵌入向量
        """
        self.metadata.embedding = embedding
        self.metadata.vector_dimension = len(embedding) if embedding else None

class ChunkService:
    """文档分块服务"""
    
    def __init__(self):
        """初始化分块服务"""
        # 默认分块参数
        self.default_chunk_size = 1000  # 字符数
        self.default_chunk_overlap = 200  # 重叠字符数
        self.min_chunk_size = 100  # 最小分块大小
        self.max_chunk_size = 4000  # 最大分块大小
        
        # 句子分隔符（优先级从高到低）
        self.sentence_separators = [
            r'[.!?。！？]\s+',  # 句号、感叹号、问号后跟空格
            r'[.!?。！？]$',    # 行末的句号、感叹号、问号
            r'[;\n]\s*',        # 分号或换行符
            r'[,，]\s+',        # 逗号后跟空格
        ]
        
        # 段落分隔符
        self.paragraph_separators = [
            r'\n\s*\n',         # 双换行符
            r'\r\n\s*\r\n',     # Windows换行符
        ]
        
        logger.info("文档分块服务初始化完成")
    
    def chunk_document(
        self, 
        content: str, 
        document_id: Optional[int] = None,
        document_structure: Optional[Any] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        strategy: str = "adaptive"
    ) -> List[DocumentChunk]:
        """文档分块主方法
        
        Args:
            content: 文档内容
            document_id: 文档ID
            document_structure: 文档结构信息
            chunk_size: 分块大小
            chunk_overlap: 重叠大小
            strategy: 分块策略 ('fixed', 'sentence', 'paragraph', 'adaptive')
            
        Returns:
            分块列表
        """
        logger.info(f"开始文档分块，策略: {strategy}")
        
        # 使用默认参数
        chunk_size = chunk_size or self.default_chunk_size
        chunk_overlap = chunk_overlap or self.default_chunk_overlap
        
        # 验证参数
        chunk_size = max(self.min_chunk_size, min(chunk_size, self.max_chunk_size))
        chunk_overlap = min(chunk_overlap, chunk_size // 2)  # 重叠不超过分块大小的一半
        
        # 预处理文本
        content = self._preprocess_text(content)
        
        # 根据策略选择分块方法
        if strategy == "fixed":
            chunks = self._chunk_by_fixed_size(content, chunk_size, chunk_overlap)
        elif strategy == "sentence":
            chunks = self._chunk_by_sentence(content, chunk_size, chunk_overlap)
        elif strategy == "paragraph":
            chunks = self._chunk_by_paragraph(content, chunk_size, chunk_overlap)
        elif strategy == "adaptive":
            chunks = self._chunk_adaptive(content, document_structure, chunk_size, chunk_overlap)
        else:
            logger.warning(f"未知的分块策略: {strategy}，使用自适应策略")
            chunks = self._chunk_adaptive(content, document_structure, chunk_size, chunk_overlap)
        
        # 添加文档级元数据
        for i, chunk in enumerate(chunks):
            chunk.metadata.document_id = document_id
            chunk.metadata.chunk_index = i
            chunk.metadata.created_at = datetime.utcnow().isoformat()
            
            # 生成唯一ID
            chunk.metadata.chunk_id = self._generate_chunk_id(chunk.content, document_id, i)
        
        logger.info(f"文档分块完成，共生成 {len(chunks)} 个分块")
        return chunks
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本
        
        Args:
            text: 原始文本
            
        Returns:
            预处理后的文本
        """
        # 标准化换行符
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)
        
        # 清理多余的空白字符
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # 多个换行符合并为两个
        text = re.sub(r'[ \t]+', ' ', text)  # 多个空格或tab合并为一个空格
        
        # 去除首尾空白
        text = text.strip()
        
        return text
    
    def _chunk_by_fixed_size(self, content: str, chunk_size: int, overlap: int) -> List[DocumentChunk]:
        """固定大小分块
        
        Args:
            content: 文档内容
            chunk_size: 分块大小
            overlap: 重叠大小
            
        Returns:
            分块列表
        """
        chunks = []
        start = 0
        content_length = len(content)
        
        while start < content_length:
            end = min(start + chunk_size, content_length)
            chunk_content = content[start:end]
            
            # 创建元数据
            metadata = ChunkMetadata(
                chunk_id="",  # 稍后生成
                start_char=start,
                end_char=end,
                content_length=len(chunk_content),
                word_count=len(chunk_content.split()),
                paragraph_count=chunk_content.count('\n\n') + 1,
                chunk_type="content",
                overlap_start=overlap if start > 0 else 0,
                overlap_end=overlap if end < content_length else 0
            )
            
            chunks.append(DocumentChunk(content=chunk_content, metadata=metadata))
            
            # 计算下一个分块的起始位置
            start = end - overlap if end < content_length else end
        
        return chunks
    
    def _chunk_by_sentence(self, content: str, chunk_size: int, overlap: int) -> List[DocumentChunk]:
        """按句子分块
        
        Args:
            content: 文档内容
            chunk_size: 分块大小
            overlap: 重叠大小
            
        Returns:
            分块列表
        """
        # 分割句子
        sentences = self._split_into_sentences(content)
        if not sentences:
            return []
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # 如果添加当前句子会超过分块大小，先保存当前分块
            if current_length + sentence_length > chunk_size and current_chunk:
                chunk_content = ''.join(current_chunk)
                chunk_start = content.find(chunk_content)
                
                metadata = ChunkMetadata(
                    chunk_id="",
                    start_char=chunk_start,
                    end_char=chunk_start + len(chunk_content),
                    content_length=len(chunk_content),
                    word_count=len(chunk_content.split()),
                    paragraph_count=chunk_content.count('\n\n') + 1,
                    chunk_type="content"
                )
                
                chunks.append(DocumentChunk(content=chunk_content, metadata=metadata))
                
                # 处理重叠
                overlap_sentences = self._get_overlap_sentences(current_chunk, overlap)
                current_chunk = overlap_sentences
                current_length = sum(len(s) for s in overlap_sentences)
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        # 处理最后一个分块
        if current_chunk:
            chunk_content = ''.join(current_chunk)
            chunk_start = content.find(chunk_content)
            
            metadata = ChunkMetadata(
                chunk_id="",
                start_char=chunk_start,
                end_char=chunk_start + len(chunk_content),
                content_length=len(chunk_content),
                word_count=len(chunk_content.split()),
                paragraph_count=chunk_content.count('\n\n') + 1,
                chunk_type="content"
            )
            
            chunks.append(DocumentChunk(content=chunk_content, metadata=metadata))
        
        return chunks
    
    def _chunk_by_paragraph(self, content: str, chunk_size: int, overlap: int) -> List[DocumentChunk]:
        """按段落分块
        
        Args:
            content: 文档内容
            chunk_size: 分块大小
            overlap: 重叠大小
            
        Returns:
            分块列表
        """
        # 分割段落
        paragraphs = self._split_into_paragraphs(content)
        if not paragraphs:
            return []
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for paragraph in paragraphs:
            paragraph_length = len(paragraph)
            
            # 如果单个段落就超过分块大小，需要进一步分割
            if paragraph_length > chunk_size:
                # 如果当前分块不为空，先保存
                if current_chunk:
                    chunk_content = '\n\n'.join(current_chunk)
                    chunk_start = content.find(chunk_content)
                    
                    metadata = ChunkMetadata(
                        chunk_id="",
                        start_char=chunk_start,
                        end_char=chunk_start + len(chunk_content),
                        content_length=len(chunk_content),
                        word_count=len(chunk_content.split()),
                        paragraph_count=len(current_chunk),
                        chunk_type="content"
                    )
                    
                    chunks.append(DocumentChunk(content=chunk_content, metadata=metadata))
                    current_chunk = []
                    current_length = 0
                
                # 对长段落进行句子级分块
                para_chunks = self._chunk_by_sentence(paragraph, chunk_size, overlap)
                chunks.extend(para_chunks)
                
            else:
                # 如果添加当前段落会超过分块大小，先保存当前分块
                if current_length + paragraph_length > chunk_size and current_chunk:
                    chunk_content = '\n\n'.join(current_chunk)
                    chunk_start = content.find(chunk_content)
                    
                    metadata = ChunkMetadata(
                        chunk_id="",
                        start_char=chunk_start,
                        end_char=chunk_start + len(chunk_content),
                        content_length=len(chunk_content),
                        word_count=len(chunk_content.split()),
                        paragraph_count=len(current_chunk),
                        chunk_type="content"
                    )
                    
                    chunks.append(DocumentChunk(content=chunk_content, metadata=metadata))
                    
                    # 处理重叠
                    overlap_paras = self._get_overlap_paragraphs(current_chunk, overlap)
                    current_chunk = overlap_paras
                    current_length = sum(len(p) for p in overlap_paras)
                
                current_chunk.append(paragraph)
                current_length += paragraph_length + 2  # 加上段落分隔符的长度
        
        # 处理最后一个分块
        if current_chunk:
            chunk_content = '\n\n'.join(current_chunk)
            chunk_start = content.find(chunk_content)
            
            metadata = ChunkMetadata(
                chunk_id="",
                start_char=chunk_start,
                end_char=chunk_start + len(chunk_content),
                content_length=len(chunk_content),
                word_count=len(chunk_content.split()),
                paragraph_count=len(current_chunk),
                chunk_type="content"
            )
            
            chunks.append(DocumentChunk(content=chunk_content, metadata=metadata))
        
        return chunks
    
    def _chunk_adaptive(self, content: str, document_structure: Optional[Any], chunk_size: int, overlap: int) -> List[DocumentChunk]:
        """自适应分块（综合考虑文档结构）
        
        Args:
            content: 文档内容
            document_structure: 文档结构
            chunk_size: 分块大小
            overlap: 重叠大小
            
        Returns:
            分块列表
        """
        # 如果没有文档结构信息，降级到段落分块
        if not document_structure or not hasattr(document_structure, 'headings'):
            return self._chunk_by_paragraph(content, chunk_size, overlap)
        
        chunks = []
        
        # 尝试根据标题结构进行分块
        if document_structure.headings:
            sections = self._extract_sections_by_headings(content, document_structure.headings)
            
            for section in sections:
                section_content = section['content']
                section_title = section['title']
                heading_level = section['level']
                
                # 如果章节内容较短，直接作为一个分块
                if len(section_content) <= chunk_size:
                    metadata = ChunkMetadata(
                        chunk_id="",
                        start_char=section['start'],
                        end_char=section['end'],
                        content_length=len(section_content),
                        word_count=len(section_content.split()),
                        paragraph_count=section_content.count('\n\n') + 1,
                        heading_level=heading_level,
                        section_title=section_title,
                        chunk_type="section"
                    )
                    
                    chunks.append(DocumentChunk(content=section_content, metadata=metadata))
                
                else:
                    # 对长章节进行进一步分块
                    section_chunks = self._chunk_by_paragraph(section_content, chunk_size, overlap)
                    
                    # 为章节内的分块添加标题信息
                    for chunk in section_chunks:
                        chunk.metadata.section_title = section_title
                        chunk.metadata.heading_level = heading_level
                        chunk.metadata.chunk_type = "subsection"
                    
                    chunks.extend(section_chunks)
        
        else:
            # 没有标题结构，使用段落分块
            chunks = self._chunk_by_paragraph(content, chunk_size, overlap)
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """将文本分割为句子
        
        Args:
            text: 输入文本
            
        Returns:
            句子列表
        """
        sentences = []
        current_pos = 0
        
        # 使用正则表达式找到句子边界
        for separator in self.sentence_separators:
            pattern = re.compile(separator)
            matches = list(pattern.finditer(text))
            
            if matches:
                last_end = 0
                for match in matches:
                    sentence = text[last_end:match.end()].strip()
                    if sentence:
                        sentences.append(sentence)
                    last_end = match.end()
                
                # 添加最后一部分
                if last_end < len(text):
                    remaining = text[last_end:].strip()
                    if remaining:
                        sentences.append(remaining)
                
                return sentences
        
        # 如果没有找到分隔符，按最大长度分割
        max_sentence_length = 500
        for i in range(0, len(text), max_sentence_length):
            sentence = text[i:i + max_sentence_length]
            if sentence.strip():
                sentences.append(sentence)
        
        return sentences
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """将文本分割为段落
        
        Args:
            text: 输入文本
            
        Returns:
            段落列表
        """
        # 使用双换行符分割段落
        paragraphs = re.split(r'\n\s*\n', text)
        
        # 清理空段落
        paragraphs = [para.strip() for para in paragraphs if para.strip()]
        
        return paragraphs
    
    def _get_overlap_sentences(self, sentences: List[str], overlap_size: int) -> List[str]:
        """获取重叠的句子
        
        Args:
            sentences: 句子列表
            overlap_size: 重叠字符数
            
        Returns:
            重叠的句子列表
        """
        if not sentences:
            return []
        
        overlap_sentences = []
        current_length = 0
        
        # 从最后一句开始，向前选择句子直到达到重叠大小
        for sentence in reversed(sentences):
            overlap_sentences.insert(0, sentence)
            current_length += len(sentence)
            
            if current_length >= overlap_size:
                break
        
        return overlap_sentences
    
    def _get_overlap_paragraphs(self, paragraphs: List[str], overlap_size: int) -> List[str]:
        """获取重叠的段落
        
        Args:
            paragraphs: 段落列表
            overlap_size: 重叠字符数
            
        Returns:
            重叠的段落列表
        """
        if not paragraphs:
            return []
        
        overlap_paragraphs = []
        current_length = 0
        
        # 从最后一段开始，向前选择段落直到达到重叠大小
        for paragraph in reversed(paragraphs):
            overlap_paragraphs.insert(0, paragraph)
            current_length += len(paragraph) + 2  # 加上段落分隔符
            
            if current_length >= overlap_size:
                break
        
        return overlap_paragraphs
    
    def _extract_sections_by_headings(self, content: str, headings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """根据标题提取章节
        
        Args:
            content: 文档内容
            headings: 标题列表
            
        Returns:
            章节列表
        """
        sections = []
        
        for i, heading in enumerate(headings):
            heading_text = heading.get('text', '')
            heading_level = heading.get('level', 1)
            
            # 在内容中找到标题的位置
            heading_start = content.find(heading_text)
            if heading_start == -1:
                continue
            
            # 确定章节结束位置
            if i + 1 < len(headings):
                next_heading_text = headings[i + 1].get('text', '')
                next_heading_start = content.find(next_heading_text, heading_start + len(heading_text))
                section_end = next_heading_start if next_heading_start != -1 else len(content)
            else:
                section_end = len(content)
            
            # 提取章节内容
            section_content = content[heading_start:section_end].strip()
            
            sections.append({
                'title': heading_text,
                'level': heading_level,
                'start': heading_start,
                'end': section_end,
                'content': section_content
            })
        
        return sections
    
    def _generate_chunk_id(self, content: str, document_id: Optional[int], chunk_index: int) -> str:
        """生成分块唯一ID
        
        Args:
            content: 分块内容
            document_id: 文档ID
            chunk_index: 分块索引
            
        Returns:
            分块ID
        """
        # 使用内容哈希、文档ID和索引生成唯一ID
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
        doc_prefix = f"doc{document_id}_" if document_id else ""
        return f"{doc_prefix}chunk{chunk_index}_{content_hash}"
    
    def get_chunk_statistics(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """获取分块统计信息
        
        Args:
            chunks: 分块列表
            
        Returns:
            统计信息
        """
        if not chunks:
            return {}
        
        total_chunks = len(chunks)
        total_content_length = sum(chunk.metadata.content_length for chunk in chunks)
        total_word_count = sum(chunk.metadata.word_count for chunk in chunks)
        
        chunk_sizes = [chunk.metadata.content_length for chunk in chunks]
        
        return {
            'total_chunks': total_chunks,
            'total_content_length': total_content_length,
            'total_word_count': total_word_count,
            'average_chunk_size': total_content_length / total_chunks if total_chunks > 0 else 0,
            'min_chunk_size': min(chunk_sizes) if chunk_sizes else 0,
            'max_chunk_size': max(chunk_sizes) if chunk_sizes else 0,
            'chunk_types': self._count_chunk_types(chunks)
        }
    
    def _count_chunk_types(self, chunks: List[DocumentChunk]) -> Dict[str, int]:
        """统计分块类型
        
        Args:
            chunks: 分块列表
            
        Returns:
            类型统计
        """
        type_counts = {}
        for chunk in chunks:
            chunk_type = chunk.metadata.chunk_type
            type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
        
        return type_counts
    
    def validate_chunks(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """验证分块质量
        
        Args:
            chunks: 分块列表
            
        Returns:
            验证结果
        """
        issues = []
        warnings = []
        
        for i, chunk in enumerate(chunks):
            # 检查分块大小
            if chunk.metadata.content_length < self.min_chunk_size:
                issues.append(f"分块 {i} 太小: {chunk.metadata.content_length} 字符")
            
            if chunk.metadata.content_length > self.max_chunk_size:
                warnings.append(f"分块 {i} 较大: {chunk.metadata.content_length} 字符")
            
            # 检查空内容
            if not chunk.content.strip():
                issues.append(f"分块 {i} 内容为空")
            
            # 检查重复ID
            duplicate_ids = [j for j, other_chunk in enumerate(chunks) 
                           if j != i and other_chunk.metadata.chunk_id == chunk.metadata.chunk_id]
            if duplicate_ids:
                issues.append(f"分块 {i} 的ID与分块 {duplicate_ids} 重复")
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'statistics': self.get_chunk_statistics(chunks)
        } 