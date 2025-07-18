#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DashScope LLM服务适配器
解决OpenAI网络连接问题，使用DashScope的千问模型进行知识抽取
"""
import logging
import os
from typing import Dict, Any, Optional, List
import dashscope
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from app.core.config import settings

logger = logging.getLogger(__name__)

class DashScopeLLM(BaseLanguageModel):
    """
    DashScope千问模型适配器
    实现LangChain接口，用于替代OpenAI LLM
    """
    
    def __init__(self, 
                 model: str = "qwen-turbo",
                 temperature: float = 0.0,
                 max_tokens: int = 2000,
                 **kwargs):
        super().__init__(**kwargs)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # 设置API Key
        dashscope.api_key = settings.DASHSCOPE_API_KEY
        
        logger.info(f"DashScope LLM初始化：模型={model}, 温度={temperature}")
    
    def _generate(self, 
                  messages: List[BaseMessage],
                  stop: Optional[List[str]] = None,
                  run_manager: Optional[CallbackManagerForLLMRun] = None,
                  **kwargs) -> Any:
        """生成响应"""
        try:
            # 转换消息格式
            dashscope_messages = self._convert_messages(messages)
            
            # 调用DashScope API
            response = dashscope.Generation.call(
                model=self.model,
                messages=dashscope_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                result_format='message',
                **kwargs
            )
            
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                
                # 返回LangChain格式的结果
                from langchain_core.outputs import LLMResult, Generation
                return LLMResult(
                    generations=[[Generation(text=content)]],
                    llm_output={"model": self.model}
                )
            else:
                raise Exception(f"DashScope API调用失败: {response.status_code}, {response.message}")
                
        except Exception as e:
            logger.error(f"DashScope LLM生成失败: {str(e)}")
            raise
    
    async def _agenerate(self, 
                        messages: List[BaseMessage],
                        stop: Optional[List[str]] = None,
                        run_manager: Optional[CallbackManagerForLLMRun] = None,
                        **kwargs) -> Any:
        """异步生成响应"""
        # DashScope暂不支持异步，回退到同步调用
        return self._generate(messages, stop, run_manager, **kwargs)
    
    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """转换消息格式为DashScope格式"""
        dashscope_messages = []
        
        for message in messages:
            if isinstance(message, HumanMessage):
                dashscope_messages.append({
                    "role": "user",
                    "content": message.content
                })
            elif isinstance(message, AIMessage):
                dashscope_messages.append({
                    "role": "assistant", 
                    "content": message.content
                })
            else:
                # 其他类型消息当作用户消息处理
                dashscope_messages.append({
                    "role": "user",
                    "content": str(message.content)
                })
        
        return dashscope_messages
    
    def invoke(self, input: Any, config: Optional[Dict] = None, **kwargs) -> AIMessage:
        """同步调用接口"""
        if isinstance(input, str):
            messages = [HumanMessage(content=input)]
        elif isinstance(input, list):
            messages = input
        else:
            messages = [HumanMessage(content=str(input))]
        
        result = self._generate(messages, **kwargs)
        content = result.generations[0][0].text
        
        return AIMessage(content=content)
    
    async def ainvoke(self, input: Any, config: Optional[Dict] = None, **kwargs) -> AIMessage:
        """异步调用接口"""
        return self.invoke(input, config, **kwargs)
    
    # 实现抽象方法
    def predict(self, text: str, **kwargs) -> str:
        """预测文本响应"""
        result = self.invoke(text, **kwargs)
        return result.content
    
    def predict_messages(self, messages: List[BaseMessage], **kwargs) -> BaseMessage:
        """预测消息响应"""
        result = self._generate(messages, **kwargs)
        content = result.generations[0][0].text
        return AIMessage(content=content)
    
    async def apredict(self, text: str, **kwargs) -> str:
        """异步预测文本响应"""
        return self.predict(text, **kwargs)
    
    async def apredict_messages(self, messages: List[BaseMessage], **kwargs) -> BaseMessage:
        """异步预测消息响应"""
        return self.predict_messages(messages, **kwargs)
    
    def generate_prompt(self, prompts: List[str], **kwargs) -> Any:
        """生成提示响应"""
        from langchain_core.outputs import LLMResult, Generation
        generations = []
        for prompt in prompts:
            result = self.invoke(prompt, **kwargs)
            generations.append([Generation(text=result.content)])
        return LLMResult(generations=generations, llm_output={"model": self.model})
    
    async def agenerate_prompt(self, prompts: List[str], **kwargs) -> Any:
        """异步生成提示响应"""
        return self.generate_prompt(prompts, **kwargs)
    
    @property
    def _llm_type(self) -> str:
        """返回LLM类型"""
        return "dashscope"
    
    @property 
    def _identifying_params(self) -> Dict[str, Any]:
        """返回识别参数"""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

class DashScopeLLMService:
    """DashScope LLM服务管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._llm_instances = {}
        self._initialized = True
        logger.info("DashScope LLM服务管理器初始化完成")
    
    def get_llm(self, 
                model: str = "qwen-turbo",
                temperature: float = 0.0,
                max_tokens: int = 2000,
                **kwargs) -> DashScopeLLM:
        """获取DashScope LLM实例"""
        
        cache_key = f"{model}_{temperature}_{max_tokens}"
        
        if cache_key not in self._llm_instances:
            self._llm_instances[cache_key] = DashScopeLLM(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            logger.info(f"创建新的DashScope LLM实例: {cache_key}")
        
        return self._llm_instances[cache_key]
    
    def get_processing_llm(self, **kwargs) -> DashScopeLLM:
        """获取文档处理专用LLM"""
        return self.get_llm(
            model="qwen-turbo",
            temperature=0.0,
            max_tokens=2000,
            **kwargs
        )
    
    def get_chat_llm(self, **kwargs) -> DashScopeLLM:
        """获取对话专用LLM"""
        return self.get_llm(
            model="qwen-plus",
            temperature=0.1,
            max_tokens=1500,
            **kwargs
        )

# 全局实例
_dashscope_llm_service = DashScopeLLMService()

def get_dashscope_llm_service() -> DashScopeLLMService:
    """获取DashScope LLM服务实例"""
    return _dashscope_llm_service

def get_dashscope_processing_llm() -> DashScopeLLM:
    """快速获取处理用LLM"""
    return _dashscope_llm_service.get_processing_llm() 