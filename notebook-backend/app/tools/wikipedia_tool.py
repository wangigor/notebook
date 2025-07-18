# -*- coding: utf-8 -*-
"""
Wikipedia搜索工具
基于LangChain工具框架的标准化Wikipedia搜索实现
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.tools import tool

from app.services.wikipedia_mcp_server import get_wikipedia_mcp_server

logger = logging.getLogger(__name__)

@tool
def search_wikipedia_entity(entity_name: str, entity_type: str = None) -> dict:
    """【可选工具】智能Wikipedia搜索 - 仅在内在知识不足时使用
    
    这是一个可选的验证工具，用于在实体去重过程中获取权威信息。
    请优先使用你的内在知识判断实体关系，仅在以下情况时考虑使用此工具：
    
    🔍 推荐使用场景：
    - 遇到不熟悉的专业术语或新兴概念
    - 实体名称存在歧义（如"苹果"可能是水果或公司）
    - 基于内在知识的置信度低于80%
    - 需要验证模糊或不确定的实体关系
    
    ✋ 无需使用场景：
    - 知名公司、著名人物、常见产品
    - 明显不同的竞争对手实体
    - 基于常识即可判断的情况
    
    Args:
        entity_name: 要搜索的实体名称
        entity_type: 实体类型（可选），如"人物"、"组织"、"地点"等，有助于提高搜索准确性
    
    Returns:
        包含Wikipedia搜索结果的字典，包含以下字段：
        - found: 是否找到相关条目 (bool)
        - title: Wikipedia条目标题 (str)
        - summary: 条目摘要 (str)
        - url: Wikipedia页面URL (str)
        - entity_name: 搜索的实体名称 (str)
        - entity_type: 实体类型 (str, optional)
        - error: 搜索错误信息 (str, 仅在出错时)
        
    Examples:
        >>> # 推荐使用：不熟悉的专业术语
        >>> search_wikipedia_entity("某个新兴技术概念", "技术")
        
        >>> # 不推荐：知名实体，直接判断即可
        >>> # search_wikipedia_entity("苹果公司", "组织")  # 无需搜索
    """
    try:
        logger.info(f"使用工具搜索Wikipedia: 实体='{entity_name}', 类型='{entity_type}'")
        
        # 获取Wikipedia服务器实例
        wikipedia_server = get_wikipedia_mcp_server()
        
        # 执行搜索
        search_result = wikipedia_server.search_entity(
            entity_name=entity_name,
            entity_type=entity_type
        )
        
        # 添加工具调用标记
        search_result["tool_called"] = True
        search_result["tool_name"] = "search_wikipedia_entity"
        
        logger.info(f"Wikipedia搜索完成: {entity_name} -> 找到={search_result.get('found', False)}")
        
        return search_result
        
    except Exception as e:
        error_msg = f"Wikipedia工具调用失败: {str(e)}"
        logger.error(error_msg)
        
        # 返回错误结果，保持一致的格式
        return {
            "found": False,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "error": str(e),
            "tool_called": True,
            "tool_name": "search_wikipedia_entity",
            "graceful_degradation": True
        }

# 为了向后兼容，也提供一个获取工具实例的函数
def get_wikipedia_search_tool():
    """获取Wikipedia搜索工具实例"""
    return search_wikipedia_entity