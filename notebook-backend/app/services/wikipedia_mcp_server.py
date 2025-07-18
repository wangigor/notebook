# -*- coding: utf-8 -*-
"""
Wikipedia MCP服务器
提供Wikipedia搜索和实体信息获取功能
使用 LangChain Wikipedia 工具通过API代理访问
"""
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.documents import Document
import logging
import traceback
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime
import re
import time
import ssl
import urllib3
import certifi
import os

logger = logging.getLogger(__name__)

class WikipediaMCPServer:
    """Wikipedia MCP服务器"""
    
    def __init__(self):
        """初始化Wikipedia MCP服务器"""
        self.name = "wikipedia-search"
        
        # 强制使用最新的certifi证书
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['CURL_CA_BUNDLE'] = certifi.where()
        
        # 配置Clash代理（用于Celery worker环境）
        clash_proxy = "http://127.0.0.1:7890"
        os.environ['HTTP_PROXY'] = clash_proxy
        os.environ['HTTPS_PROXY'] = clash_proxy
        os.environ['http_proxy'] = clash_proxy
        os.environ['https_proxy'] = clash_proxy
        
        # 禁用SSL警告（如果使用代理导致证书问题）
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        logger.info(f"Wikipedia MCP 服务器已配置代理: {clash_proxy}")
        
        # 使用API代理服务提高访问稳定性
        api_wrapper = WikipediaAPIWrapper()
        
        # 配置LangChain Wikipedia工具
        self.wikipedia_tool = WikipediaQueryRun(api_wrapper=api_wrapper)
        
        self.search_cache = {}
        self.cache_expiry_hours = 24
        self.max_retries = 3
        self.retry_delay = 2
    
    def _convert_langchain_docs_to_result(self, docs: List[Document], entity_name: str, entity_type: str = None) -> Dict[str, Any]:
        """
        将LangChain Document对象转换为原有的返回格式
        
        Args:
            docs: LangChain Document对象列表
            entity_name: 实体名称
            entity_type: 实体类型
            
        Returns:
            与原有格式兼容的结果字典
        """
        if not docs:
            return {
                "found": False,
                "reason": "No Wikipedia entry found",
                "entity_name": entity_name,
                "search_query": entity_name if not entity_type else f"{entity_name} {entity_type}"
            }
        
        # 使用第一个文档作为主要结果
        main_doc = docs[0]
        
        # 提取页面信息
        title = main_doc.metadata.get("title", entity_name)
        summary = main_doc.page_content[:800] if main_doc.page_content else ""
        
        # 构建结果
        result = {
            "found": True,
            "title": title,
            "summary": summary,
            "url": main_doc.metadata.get("source", ""),
            "entity_name": entity_name,
            "search_query": entity_name if not entity_type else f"{entity_name} {entity_type}",
            "alternative_titles": [doc.metadata.get("title", "") for doc in docs[1:]] if len(docs) > 1 else []
        }
        
        # 添加实体特定信息
        if entity_type:
            result["entity_type"] = entity_type
            result["type_relevance"] = self._calculate_type_relevance(main_doc, entity_type)
        
        return result
    
    def search_entity(self, entity_name: str, entity_type: str = None) -> Dict[str, Any]:
        """
        搜索实体基本信息
        
        Args:
            entity_name: 实体名称
            entity_type: 实体类型（可选）
            
        Returns:
            搜索结果字典
        """
        try:
            # 检查缓存
            cache_key = f"{entity_name}_{entity_type}"
            if cache_key in self.search_cache:
                cached_result = self.search_cache[cache_key]
                if self._is_cache_valid(cached_result["timestamp"]):
                    logger.debug(f"使用缓存结果: {entity_name}")
                    return cached_result["data"]
            
            # 执行搜索
            search_results = self._search_wikipedia(entity_name, entity_type)
            
            # 缓存结果
            self.search_cache[cache_key] = {
                "data": search_results,
                "timestamp": datetime.now()
            }
            
            return search_results
            
        except Exception as e:
            logger.error(f"Wikipedia搜索失败: {entity_name}, 错误: {str(e)}")
            logger.error(f"异常调用栈:\n{traceback.format_exc()}")
            # 优雅降级：返回未找到结果而不是抛出异常
            return {
                "found": False,
                "error": str(e),
                "entity_name": entity_name,
                "graceful_degradation": True
            }
    
    def get_entity_summary(self, entity_name: str, max_sentences: int = 3) -> Dict[str, Any]:
        """
        获取实体详细摘要
        
        Args:
            entity_name: 实体名称
            max_sentences: 最大句子数（用于控制返回内容长度）
            
        Returns:
            摘要结果字典
        """
        try:
            # 使用LangChain WikipediaQueryRun工具搜索
            search_result = self.wikipedia_tool.run(entity_name)
            
            if not search_result or search_result.strip() == "No good Wikipedia Search Result was found":
                return {
                    "found": False,
                    "reason": "No Wikipedia entry found",
                    "entity_name": entity_name
                }
            
            # 根据max_sentences控制摘要长度
            content = search_result
            if max_sentences and max_sentences > 0:
                # 简单的句子分割，按句号分割并取前N句
                sentences = content.split('。')
                if len(sentences) > max_sentences:
                    content = '。'.join(sentences[:max_sentences]) + '。'
            
            return {
                "found": True,
                "title": entity_name,
                "summary": content,
                "url": f"https://zh.wikipedia.org/wiki/{entity_name.replace(' ', '_')}",
                "entity_name": entity_name
            }
            
        except Exception as e:
            logger.error(f"获取Wikipedia摘要失败: {entity_name}, 错误: {str(e)}")
            logger.error(f"异常调用栈:\n{traceback.format_exc()}")
            # 优雅降级：返回未找到结果而不是抛出异常
            return {
                "found": False,
                "error": str(e),
                "entity_name": entity_name,
                "graceful_degradation": True
            }
    
    def _search_wikipedia(self, entity_name: str, entity_type: str = None) -> Dict[str, Any]:
        """
        执行Wikipedia搜索（带重试机制）
        
        Args:
            entity_name: 实体名称
            entity_type: 实体类型
            
        Returns:
            搜索结果
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return self._do_wikipedia_search(entity_name, entity_type)
            except Exception as e:
                last_error = e
                logger.warning(f"Wikipedia搜索尝试 {attempt + 1}/{self.max_retries} 失败: {entity_name}, 错误: {str(e)}")
                logger.debug(f"错误详情: {type(e).__name__}: {str(e)}")
                
                # 添加调试信息
                logger.debug(f"完整错误堆栈: {traceback.format_exc()}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    
        # 所有重试都失败了
        logger.error(f"Wikipedia搜索完全失败: {entity_name}, 最后错误: {str(last_error)}")
        return {
            "found": False,
            "error": f"网络连接失败，已重试{self.max_retries}次: {str(last_error)}",
            "entity_name": entity_name,
            "retry_attempts": self.max_retries
        }
    
    def _do_wikipedia_search(self, entity_name: str, entity_type: str = None) -> Dict[str, Any]:
        """
        使用LangChain工具执行Wikipedia搜索
        
        Args:
            entity_name: 实体名称
            entity_type: 实体类型
            
        Returns:
            搜索结果
        """
        # 构建搜索查询
        search_query = entity_name
        if entity_type:
            search_query = f"{entity_name}"
        
        try:
            # 使用LangChain WikipediaQueryRun工具搜索
            search_result = self.wikipedia_tool.run(search_query)
            
            if not search_result or search_result.strip() == "No good Wikipedia Search Result was found":
                return {
                    "found": False,
                    "reason": "No Wikipedia entry found",
                    "entity_name": entity_name,
                    "search_query": search_query
                }
            
            # 将搜索结果转换为Document格式以便复用现有的转换逻辑
            doc = Document(
                page_content=search_result[:2000],  # 限制长度
                metadata={
                    "title": entity_name,  # 使用实体名称作为标题
                    "source": f"https://zh.wikipedia.org/wiki/{entity_name.replace(' ', '_')}"
                }
            )
            
            # 转换为原有格式
            result = self._convert_langchain_docs_to_result([doc], entity_name, entity_type)
            
            logger.debug(f"Wikipedia搜索成功: {entity_name}")
            return result
            
        except Exception as e:
            logger.error(f"LangChain Wikipedia工具搜索失败: {entity_name}, 错误: {str(e)}")
            logger.error(f"异常调用栈:\n{traceback.format_exc()}")
            # 返回搜索失败的结果
            return {
                "found": False,
                "reason": f"LangChain Wikipedia工具搜索失败: {str(e)}",
                "entity_name": entity_name,
                "search_query": search_query,
                "error": str(e)
            }
    
    def _calculate_type_relevance(self, doc: Document, entity_type: str) -> float:
        """
        计算Document与实体类型的相关性
        
        Args:
            doc: LangChain Document对象
            entity_type: 实体类型
            
        Returns:
            相关性分数 (0-1)
        """
        try:
            # 获取文档内容和元数据
            content = doc.page_content.lower() if doc.page_content else ""
            title = doc.metadata.get("title", "").lower()
            
            # 类型关键词映射
            type_keywords = {
                "人物": ["人物", "人", "演员", "歌手", "作家", "科学家", "政治家", "企业家"],
                "组织": ["公司", "企业", "组织", "机构", "团体", "协会", "学校", "大学"],
                "地点": ["地方", "城市", "国家", "地区", "位置", "建筑", "景点"],
                "产品": ["产品", "设备", "软件", "硬件", "工具", "系统"],
                "技术": ["技术", "算法", "方法", "协议", "标准", "框架"],
                "事件": ["事件", "活动", "会议", "战争", "运动", "节日"]
            }
            
            keywords = type_keywords.get(entity_type, [])
            
            # 计算匹配度
            matches = 0
            total_keywords = len(keywords)
            
            for keyword in keywords:
                if keyword in content or keyword in title:
                    matches += 1
            
            relevance = matches / total_keywords if total_keywords > 0 else 0.0
            
            return min(relevance, 1.0)
            
        except Exception as e:
            logger.warning(f"计算类型相关性失败: {str(e)}")
            return 0.0
    
    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """
        检查缓存是否有效
        
        Args:
            timestamp: 缓存时间戳
            
        Returns:
            是否有效
        """
        from datetime import timedelta
        return datetime.now() - timestamp < timedelta(hours=int(self.cache_expiry_hours))
    
    def clear_cache(self):
        """清空搜索缓存"""
        self.search_cache.clear()
        logger.info("Wikipedia搜索缓存已清空")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "cache_size": len(self.search_cache),
            "cache_expiry_hours": self.cache_expiry_hours
        }


# 全局实例
_wikipedia_server_instance = None

def get_wikipedia_mcp_server() -> WikipediaMCPServer:
    """获取Wikipedia MCP服务器实例（单例模式）"""
    global _wikipedia_server_instance
    if _wikipedia_server_instance is None:
        _wikipedia_server_instance = WikipediaMCPServer()
    return _wikipedia_server_instance
