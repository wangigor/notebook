# -*- coding: utf-8 -*-
"""
工具执行服务
统一处理LangGraph Agent中的工具调用执行、错误恢复和结果验证
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from langchain_core.tools import BaseTool
from langchain_core.messages import ToolCall, ToolMessage

logger = logging.getLogger(__name__)

class ToolExecutionService:
    """工具执行服务"""
    
    def __init__(self, tools: List[BaseTool], max_retries: int = 2, timeout: float = 30.0):
        """初始化工具执行服务
        
        Args:
            tools: 可用工具列表
            max_retries: 最大重试次数
            timeout: 单个工具调用超时时间（秒）
        """
        self.tools = {tool.name: tool for tool in tools}
        self.max_retries = max_retries
        self.timeout = timeout
        
        logger.info(f"工具执行服务初始化完成: {len(self.tools)} 个工具")
    
    async def execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolMessage]:
        """执行工具调用列表
        
        Args:
            tool_calls: LLM生成的工具调用列表
            
        Returns:
            工具执行结果消息列表
        """
        if not tool_calls:
            return []
        
        logger.info(f"开始执行 {len(tool_calls)} 个工具调用")
        
        # 并发执行所有工具调用
        tasks = [
            self._execute_single_tool_call(tool_call)
            for tool_call in tool_calls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常
        tool_messages = []
        for i, (tool_call, result) in enumerate(zip(tool_calls, results)):
            if isinstance(result, Exception):
                logger.error(f"工具调用 {i+1} 失败: {str(result)}")
                tool_message = ToolMessage(
                    content=f"工具执行失败: {str(result)}",
                    tool_call_id=tool_call['id'],
                    name=tool_call['name']
                )
            else:
                tool_message = result
            
            tool_messages.append(tool_message)
        
        logger.info(f"工具调用执行完成: {len(tool_messages)} 个结果")
        return tool_messages
    
    async def _execute_single_tool_call(self, tool_call: ToolCall) -> ToolMessage:
        """执行单个工具调用
        
        Args:
            tool_call: 单个工具调用
            
        Returns:
            工具执行结果消息
        """
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        tool_call_id = tool_call['id']
        
        if tool_name not in self.tools:
            error_msg = f"未知工具: {tool_name}. 可用工具: {list(self.tools.keys())}"
            logger.error(error_msg)
            return ToolMessage(
                content=error_msg,
                tool_call_id=tool_call_id,
                name=tool_name
            )
        
        tool = self.tools[tool_name]
        
        # 尝试执行工具，带重试机制
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"执行工具 '{tool_name}' (尝试 {attempt + 1}/{self.max_retries + 1})")
                
                # 带超时的工具执行
                result = await asyncio.wait_for(
                    self._safe_tool_invoke(tool, tool_args),
                    timeout=self.timeout
                )
                
                # 格式化结果
                formatted_result = self._format_tool_result(result, tool_name)
                
                logger.info(f"工具 '{tool_name}' 执行成功")
                return ToolMessage(
                    content=formatted_result,
                    tool_call_id=tool_call_id,
                    name=tool_name
                )
                
            except asyncio.TimeoutError:
                error_msg = f"工具 '{tool_name}' 执行超时 ({self.timeout}秒)"
                logger.warning(error_msg)
                if attempt == self.max_retries:
                    return ToolMessage(
                        content=f"执行超时: {error_msg}",
                        tool_call_id=tool_call_id,
                        name=tool_name
                    )
                
            except Exception as e:
                error_msg = f"工具 '{tool_name}' 执行失败: {str(e)}"
                logger.warning(f"{error_msg} (尝试 {attempt + 1}/{self.max_retries + 1})")
                
                if attempt == self.max_retries:
                    return ToolMessage(
                        content=f"执行失败: {error_msg}",
                        tool_call_id=tool_call_id,
                        name=tool_name
                    )
                
                # 短暂延迟后重试
                await asyncio.sleep(1.0 * (attempt + 1))
        
        # 不应该到达这里，但作为保险
        return ToolMessage(
            content=f"工具 '{tool_name}' 执行失败: 达到最大重试次数",
            tool_call_id=tool_call_id,
            name=tool_name
        )
    
    async def _safe_tool_invoke(self, tool: BaseTool, tool_args: Dict[str, Any]) -> Any:
        """安全地调用工具"""
        try:
            # 检查工具是否支持异步调用
            if hasattr(tool, 'ainvoke'):
                return await tool.ainvoke(tool_args)
            elif hasattr(tool, 'arun'):
                return await tool.arun(**tool_args)
            else:
                # 同步工具调用，在线程池中执行
                import asyncio
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, tool.invoke, tool_args)
                
        except Exception as e:
            logger.error(f"工具调用异常: {str(e)}")
            raise
    
    def _format_tool_result(self, result: Any, tool_name: str) -> str:
        """格式化工具执行结果"""
        try:
            if isinstance(result, dict):
                # 对于字典结果，格式化为可读字符串
                if tool_name == "search_wikipedia_entity":
                    return self._format_wikipedia_result(result)
                else:
                    # 通用字典格式化
                    return str(result)
            
            elif isinstance(result, str):
                return result
            
            else:
                return str(result)
                
        except Exception as e:
            logger.warning(f"格式化工具结果失败: {str(e)}")
            return str(result)
    
    def _format_wikipedia_result(self, result: Dict[str, Any]) -> str:
        """格式化Wikipedia搜索结果"""
        if not result.get("found", False):
            return f"Wikipedia搜索未找到相关条目: {result.get('entity_name', 'Unknown')}"
        
        title = result.get("title", "")
        summary = result.get("summary", "")
        url = result.get("url", "")
        
        formatted = f"Wikipedia条目: {title}\n"
        if summary:
            # 限制摘要长度
            summary_truncated = summary[:300] + "..." if len(summary) > 300 else summary
            formatted += f"摘要: {summary_truncated}\n"
        if url:
            formatted += f"链接: {url}"
        
        return formatted
    
    def get_tool_statistics(self) -> Dict[str, Any]:
        """获取工具使用统计"""
        return {
            "available_tools": list(self.tools.keys()),
            "total_tools": len(self.tools),
            "max_retries": self.max_retries,
            "timeout": self.timeout
        }

# 全局实例和工厂函数
_tool_execution_service = None

def get_tool_execution_service(tools: Optional[List[BaseTool]] = None) -> ToolExecutionService:
    """获取工具执行服务实例（单例模式）"""
    global _tool_execution_service
    
    if _tool_execution_service is None and tools is not None:
        _tool_execution_service = ToolExecutionService(tools)
    elif _tool_execution_service is None:
        # 使用默认工具
        from app.tools import get_entity_analysis_tools
        default_tools = get_entity_analysis_tools()
        _tool_execution_service = ToolExecutionService(default_tools)
    
    return _tool_execution_service