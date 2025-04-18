"""
内容块管理器 - 处理AI响应中的内容块
提供标准化的格式和管理功能
"""
import re
import logging
import json
import hashlib
import time
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

# 内容块类型常量
BLOCK_TYPE_ANALYSIS = "analysis"  # 分析块
BLOCK_TYPE_THINKING = "thinking"  # 思考块
BLOCK_TYPE_ANSWER = "answer"     # 回答块
BLOCK_TYPE_CODE = "code"         # 代码块
BLOCK_TYPE_ERROR = "error"       # 错误块

# 块类型前缀标记
BLOCK_MARKERS = {
    BLOCK_TYPE_ANALYSIS: "【AI分析中】",
    BLOCK_TYPE_THINKING: "【思考过程】",
    BLOCK_TYPE_ANSWER: "【回答】",
    BLOCK_TYPE_CODE: "【代码】",
    BLOCK_TYPE_ERROR: "【错误】"
}

class ContentBlock:
    """
    内容块 - 管理单个响应块的生命周期
    包括添加内容、标记完成和格式化
    """
    def __init__(self, block_type: str = BLOCK_TYPE_ANALYSIS):
        """
        初始化内容块
        
        Args:
            block_type: 块类型，默认为分析
        """
        self.block_type = block_type
        self.content = ""
        self.completed = False
        self.created_at = time.time()
        self.completed_at = None
        self.hash = None
        logger.debug(f"创建新内容块: 类型={block_type}")
        
    def add_content(self, content: str) -> None:
        """
        添加内容到块
        
        Args:
            content: 要添加的内容
        """
        if self.completed:
            logger.warning(f"尝试向已完成的块添加内容: {self.block_type}")
            return
            
        # 检查是否为首次添加内容
        if not self.content:
            self.content = content
        else:
            # 判断是否需要添加空格或换行
            if self.content.endswith(("\n", " ", ".", "!", "?")):
                self.content += content

        # 生成新的哈希值
        self._generate_hash()
        
    def complete(self) -> None:
        """标记块为已完成"""
        if self.completed:
            return
            
        self.completed = True
        self.completed_at = time.time()
        logger.debug(f"完成内容块: 类型={self.block_type}, 长度={len(self.content)}")
        
    def format(self) -> str:
        """
        获取格式化的块内容，包括适当的标记
        
        Returns:
            格式化后的内容，带有标记
        """
        marker = BLOCK_MARKERS.get(self.block_type, "")
        
        if not self.content:
            logger.warning(f"块内容为空: {self.block_type}")
            return ""
            
        # 格式化为标准格式: 标记+内容+双换行
        formatted = f"{marker}\n{self.content}\n\n"
        return formatted
        
    def _generate_hash(self) -> None:
        """生成内容的哈希值，用于重复检测"""
        content_to_hash = f"{self.block_type}:{self.content}"
        self.hash = hashlib.md5(content_to_hash.encode()).hexdigest()
        
    def to_dict(self) -> Dict[str, Any]:
        """将块转换为字典表示"""
        return {
            "type": self.block_type,
            "content": self.content,
            "completed": self.completed,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "hash": self.hash
        }
        
    def __str__(self) -> str:
        return f"ContentBlock({self.block_type}, completed={self.completed}, len={len(self.content)})"

class ResponseGenerator:
    """
    响应生成器 - 管理多个内容块，确保它们的正确创建、完成和格式化
    """
    def __init__(self):
        """初始化响应生成器"""
        self.blocks: List[ContentBlock] = []
        self.current_block = None
        self.last_block_type = None
        logger.debug("初始化新的响应生成器")
        
    def start_block(self, block_type: str) -> ContentBlock:
        """
        开始一个新的内容块
        
        Args:
            block_type: 新块的类型
            
        Returns:
            创建的ContentBlock对象
        """
        # 如果有当前块，先完成它
        if self.current_block:
            self.complete_current_block()
            
        # 创建新块
        self.current_block = ContentBlock(block_type)
        self.blocks.append(self.current_block)
        self.last_block_type = block_type
        return self.current_block
        
    def add_content(self, content: str, block_type: Optional[str] = None) -> None:
        """
        添加内容到当前块，如果未指定类型则使用上一次的类型
        
        Args:
            content: 要添加的内容
            block_type: 可选的块类型，用于创建新块
        """
        # 如果指定了新类型且与当前类型不同，则创建新块
        if block_type and self.current_block and block_type != self.current_block.block_type:
            logger.debug(f"块类型改变: {self.current_block.block_type} -> {block_type}")
            self.complete_current_block()
            self.start_block(block_type)
            
        # 如果没有当前块，创建一个新块
        if not self.current_block:
            # 使用提供的类型或默认为上一次的类型或分析
            block_type = block_type or self.last_block_type or BLOCK_TYPE_ANALYSIS
            self.start_block(block_type)
            
        # 添加内容到当前块
        self.current_block.add_content(content)
        
    def complete_current_block(self) -> None:
        """完成当前块"""
        if self.current_block:
            self.current_block.complete()
            self.current_block = None
        
    def get_formatted_response(self, add_default_answer: bool = True) -> str:
        """
        获取格式化的完整响应，包括所有块
        
        Args:
            add_default_answer: 是否在没有回答块时添加默认回答块，默认为True
            
        Returns:
            格式化的响应文本
        """
        # 确保所有块都已完成
        if self.current_block:
            self.complete_current_block()
            
        # 合并所有块
        formatted_blocks = [block.format() for block in self.blocks if block.content]
        
        # 特殊处理 - 确保至少有一个回答块（如果add_default_answer为True）
        has_answer_block = any(block.block_type == BLOCK_TYPE_ANSWER for block in self.blocks)
        
        if add_default_answer and not has_answer_block and self.blocks:
            # 如果没有回答块但有其他块
            logger.warning("生成的响应中没有回答块，添加默认回答块")
            answer_block = ContentBlock(BLOCK_TYPE_ANSWER)
            answer_block.add_content("请参考上述分析和思考。")
            answer_block.complete()
            self.blocks.append(answer_block)
            formatted_blocks.append(answer_block.format())
        
        # 合并所有格式化块
        full_response = "".join(formatted_blocks)
        
        return full_response
        
    def get_blocks_as_json(self) -> str:
        """获取所有块的JSON表示"""
        blocks_dicts = [block.to_dict() for block in self.blocks]
        return json.dumps(blocks_dicts, ensure_ascii=False)
        
    def __str__(self) -> str:
        return f"ResponseGenerator(blocks={len(self.blocks)})"


def detect_block_type(content: str) -> str:
    """
    检测内容块类型
    
    Args:
        content: 要检测的内容
        
    Returns:
        检测到的块类型
    """
    # 优先检查显式标记
    if any(x in content for x in ["思考过程", "AI思考"]):
        return BLOCK_TYPE_THINKING
    if any(x in content for x in ["分析", "AI分析中"]):
        return BLOCK_TYPE_ANALYSIS
    if any(x in content for x in ["回答", "答案"]):
        return BLOCK_TYPE_ANSWER
    if any(x in content for x in ["代码", "函数", "```"]):
        return BLOCK_TYPE_CODE
    if any(x in content for x in ["错误", "警告", "失败"]):
        return BLOCK_TYPE_ERROR
        
    # 通过内容特征识别块类型
    if any(x in content for x in ["检索", "搜索", "查找", "文档中"]):
        return BLOCK_TYPE_ANALYSIS
    if any(x in content for x in ["未找到", "没有发现", "无结果"]):
        return BLOCK_TYPE_THINKING
    if content.startswith(("正在思考", "我认为", "思考", "假设", "考虑")):
        return BLOCK_TYPE_THINKING
    if any(x in content for x in ["结论", "总结"]) or content.startswith(("因此", "所以", "综上")):
        return BLOCK_TYPE_ANSWER
    if any(x in content for x in ["例如", "示例"]) or content.startswith(("###", "#", "##")):
        return BLOCK_TYPE_ANSWER

    # 默认为分析块
    return BLOCK_TYPE_ANALYSIS
    
    
def clean_block_content(content: str, block_type: str) -> str:
    """
    清理块内容，移除标记
    
    Args:
        content: 要清理的内容
        block_type: 块类型
        
    Returns:
        清理后的内容
    """
    cleaned = content
    
    # 移除所有可能的块标记
    for marker in BLOCK_MARKERS.values():
        cleaned = cleaned.replace(marker, "")
        
    # 移除方括号格式的标记
    bracket_markers = [
        "[思考过程]", "[AI思考]", "[AI分析中]", "[分析]", 
        "[回答]", "[答案]", "[代码]", "[错误]"
    ]
    for marker in bracket_markers:
        cleaned = cleaned.replace(marker, "")
        
    # 确保代码块的正确格式
    if block_type == BLOCK_TYPE_CODE and "```" in cleaned:
        # 确保代码块有正确的围栏格式
        if not cleaned.startswith("```"):
            cleaned = "```\n" + cleaned
        if not cleaned.endswith("```"):
            cleaned = cleaned + "\n```"
            

    return '\n'.join(cleaned_lines) 