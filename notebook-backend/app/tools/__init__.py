# -*- coding: utf-8 -*-
"""
工具注册中心
统一管理所有可用的LangChain工具
"""

from typing import List
from langchain_core.tools import BaseTool

from .wikipedia_tool import search_wikipedia_entity

AVAILABLE_TOOLS = {
    "search_wikipedia_entity": search_wikipedia_entity,
}

def get_all_tools():
    """获取所有可用工具"""
    return list(AVAILABLE_TOOLS.values())

def get_tool_by_name(tool_name):
    """根据名称获取工具"""
    if tool_name not in AVAILABLE_TOOLS:
        raise ValueError("工具 '{}' 不存在。可用工具: {}".format(tool_name, list(AVAILABLE_TOOLS.keys())))
    return AVAILABLE_TOOLS[tool_name]

def get_entity_analysis_tools():
    """获取实体分析相关的工具"""
    return [
        search_wikipedia_entity,
    ]