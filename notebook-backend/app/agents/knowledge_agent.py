from typing import Dict, Any, List, TypedDict, Optional, AsyncGenerator
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
import os
import asyncio
import json
from app.models.memory import MemoryConfig
from app.services.memory_service import MemoryService

class AgentState(TypedDict):
    """Agent状态"""
    session_id: str
    query: str
    context: Dict[str, Any]
    answer: str
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class KnowledgeAgent:
    """知识库Agent实现"""
    
    def __init__(self, memory_config: Optional[MemoryConfig] = None):
        self.memory_config = memory_config or MemoryConfig()
        self.memory_service = MemoryService(self.memory_config)
        self.graph = self._build_agent_graph()
    
    def _build_agent_graph(self) -> StateGraph:
        """构建Agent图"""
        # 创建节点
        prompt = ChatPromptTemplate.from_template("""
        你是一个知识库助手。
        请基于以下信息回答用户的问题：
        
        对话历史:
        {history}
        
        相关文档:
        {documents}
        
        用户问题: {query}
        
        如果知识库中有相关信息，请基于知识库回答。
        如果知识库中没有相关信息，你可以基于你的知识回答，但请明确说明这是你自己的知识而非来自知识库。
        请保持回答简洁、专业、有帮助。
        """)
        
        # 使用ChatOpenAI作为LLM
        llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
        
        # 定义节点函数
        def retrieve_context(state: AgentState) -> AgentState:
            """检索上下文"""
            session_id = state.get("session_id", "default")
            query = state.get("query", "")
            
            # 记录用户消息
            self.memory_service.add_user_message(session_id, query)
            
            # 获取上下文
            context = self.memory_service.get_context_for_query(session_id, query)
            state["context"] = {
                **state.get("context", {}),
                "history": context.get("history", ""),
                "documents": self._format_documents(context.get("documents", []))
            }
            
            return state
        
        def generate_answer(state: AgentState) -> AgentState:
            """生成回答"""
            query = state.get("query", "")
            context = state.get("context", {})
            
            # 构建输入
            input_data = {
                "query": query,
                "history": context.get("history", ""),
                "documents": context.get("documents", "")
            }
            
            # 生成回答
            chain = prompt | llm
            response = chain.invoke(input_data)
            
            if isinstance(response, AIMessage):
                answer = response.content
            else:
                answer = str(response)
                
            state["answer"] = answer
            
            # 记录AI消息
            session_id = state.get("session_id", "default")
            self.memory_service.add_ai_message(session_id, answer)
            
            # 提取来源
            documents = context.get("raw_documents", [])
            state["sources"] = documents
            
            return state
        
        # 构建图
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("retrieve_context", retrieve_context)
        workflow.add_node("generate_answer", generate_answer)
        
        # 设置边
        workflow.set_entry_point("retrieve_context")
        workflow.add_edge("retrieve_context", "generate_answer")
        workflow.set_finish_point("generate_answer")
        
        # 编译图
        return workflow.compile()
    
    def _format_documents(self, documents: List[Dict[str, Any]]) -> str:
        """格式化文档为字符串"""
        if not documents:
            return "没有找到相关文档。"
        
        formatted = ""
        for i, doc in enumerate(documents):
            formatted += f"文档 {i+1}:\n"
            formatted += f"内容: {doc.get('content', '')}\n"
            
            # 添加元数据
            metadata = doc.get('metadata', {})
            if metadata:
                formatted += "元数据:\n"
                for key, value in metadata.items():
                    formatted += f"  {key}: {value}\n"
            
            formatted += "\n"
        
        return formatted
    
    async def run(self, query: str, context: Dict[str, Any] = None, session_id: str = "default") -> Dict[str, Any]:
        """运行Agent
        
        Args:
            query: 用户查询
            context: 附加上下文
            session_id: 会话ID
            
        Returns:
            包含答案和来源的结果
        """
        # 设置初始状态
        initial_state: AgentState = {
            "session_id": session_id,
            "query": query,
            "context": context or {},
            "answer": "",
            "sources": [],
            "metadata": {}
        }
        
        # 执行Agent
        result = await self.graph.ainvoke(initial_state)
        
        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "metadata": result["metadata"]
        }
    
    def add_documents(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """添加文档到知识库
        
        Args:
            texts: 文本列表
            metadatas: 元数据列表
            
        Returns:
            文档ID列表
        """
        return self.memory_service.add_documents(texts, metadatas)
    
    async def run_stream(self, query: str, context: Dict[str, Any] = None, session_id: str = "default") -> AsyncGenerator[str, None]:
        """流式运行Agent
        
        Args:
            query: 用户查询
            context: 附加上下文
            session_id: 会话ID
            
        Yields:
            字符串内容，每次返回部分答案
        """
        try:
            # 设置初始状态
            initial_state: AgentState = {
                "session_id": session_id,
                "query": query,
                "context": context or {},
                "answer": "",
                "sources": [],
                "metadata": {}
            }
            
            # 记录用户消息
            self.memory_service.add_user_message(session_id, query)
            
            # 第一步：获取文档上下文
            yield "正在检索相关信息..."
            
            # 获取上下文
            retrieved_context = self.memory_service.get_context_for_query(session_id, query)
            documents = retrieved_context.get("documents", [])
            
            if documents:
                yield "已找到相关文档，正在分析..."
                # 输出文档的简要信息作为思考过程
                doc_summary = f"【思考过程】\n找到{len(documents)}个相关文档:\n\n"
                for i, doc in enumerate(documents[:3]):  # 只显示前3个文档
                    content = doc.get('content', '')
                    doc_summary += f"- **文档{i+1}**: {content[:100]}...\n\n" if len(content) > 100 else f"- **文档{i+1}**: {content}\n\n"
                yield doc_summary
            else:
                yield "【思考过程】\n未找到相关文档，将基于通用知识回答...\n\n"
            
            # 构建输入上下文
            agent_context = {
                **initial_state.get("context", {}),
                "history": retrieved_context.get("history", ""),
                "documents": self._format_documents(documents)
            }
            
            # 构建提示
            system_prompt = """你是一个知识库助手。请基于提供的信息回答用户问题。
            回答时，请清晰地展示出你的思考过程，使用【思考过程】标签来标记你的推理过程。
            然后给出最终答案，使用【回答】标签标记。
            
            你的回答应该遵循Markdown格式，支持以下格式：
            - 使用**粗体**表示重要内容
            - 使用*斜体*表示强调内容
            - 使用`代码块`表示代码或特殊内容
            - 使用列表（如1. 2. 或 - * 等）组织内容
            - 使用### 或 ## 等表示标题
            - 使用> 表示引用
            
            例如:
            【思考过程】
            1. 我需要分析用户问题："..."
            2. 查看相关文档是否包含答案信息
               - 文档1提到了...
               - 文档2包含...
            3. 根据以上信息，我可以得出...
            
            【回答】
            ## 用户问题的答案
            
            根据文档内容，答案是...
            
            如果知识库中有相关信息，请基于知识库回答。
            如果知识库中没有相关信息，你可以基于你的知识回答，但请明确说明这是你自己的知识而非来自知识库。
            """
            
            prompt = ChatPromptTemplate.from_template("""
            {system_prompt}
            
            对话历史:
            {history}
            
            相关文档:
            {documents}
            
            用户问题: {query}
            """)
            
            # 使用ChatOpenAI作为LLM，启用流式响应
            llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo", streaming=True)
            
            # 构建输入
            input_data = {
                "system_prompt": system_prompt,
                "query": query,
                "history": agent_context.get("history", ""),
                "documents": agent_context.get("documents", "")
            }
            
            # 使用流式生成回答
            full_answer = ""
            
            # 创建流式响应链
            chain = prompt | llm
            
            # 添加思考过程的提示
            yield "【AI分析中】\n正在思考如何回答您的问题...\n"
            
            # 使用astream方法获取流式响应
            buffer = ""
            async for chunk in chain.astream(input_data):
                if isinstance(chunk, AIMessage):
                    # 对于非流式响应（不太可能发生，因为我们设置了streaming=True）
                    content = chunk.content
                    full_answer += content
                    yield content
                else:
                    # 处理流式响应块
                    content = chunk.content
                    if content:  # 只有在有内容时才发送
                        full_answer += content
                        # 发送单个字符以确保实时显示
                        for char in content:
                            yield char
            
            # 记录AI消息
            self.memory_service.add_ai_message(session_id, full_answer)
            
        except Exception as e:
            error_message = f"流式处理出错: {str(e)}"
            print(error_message)
            yield f"【错误】流式处理出错: {str(e)}" 
            