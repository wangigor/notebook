# -*- coding: utf-8 -*-
"""
LangGraph实体去重Agent（工具调用增强版）
真正使用LangGraph StateGraph实现的实体去重系统，支持LLM自主工具调用
"""
import json
import logging
import asyncio
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from itertools import combinations

from langgraph.graph import StateGraph, END

from app.models.langgraph_state import (
    EntityDeduplicationState, create_initial_state, update_step, add_error, add_warning, calculate_processing_time
)
from app.services.llm_client_service import LLMClientService
from app.services.tool_execution_service import get_tool_execution_service
from app.services.embedding_service import get_embedding_service
from app.tools import get_entity_analysis_tools
from app.prompts.entity_deduplication_prompts import (
    build_tool_aware_analysis_prompt, parse_tool_aware_analysis_result, process_entity_pairs_from_tool_analysis
)

logger = logging.getLogger(__name__)


class LangGraphEntityDeduplicationAgent:
    """LangGraph实体去重Agent"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化Agent"""
        self.config = config or self._get_default_config()
        
        # 初始化服务
        self.llm_service = LLMClientService()
        self.llm = self.llm_service.get_processing_llm(streaming=False)
        self.embedding_service = get_embedding_service()
        
        # 获取工具并创建工具执行服务
        self.tools = get_entity_analysis_tools()
        self.tool_executor = get_tool_execution_service(self.tools)
        self.llm_with_tools = self.llm_service.get_llm_with_tools(self.tools, streaming=False)
        
        # 创建状态图
        self.graph = self._create_state_graph()
        
        logger.info("LangGraph实体去重Agent初始化完成")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "prescreening_threshold": 0.4,  # 向量预筛选阈值
            "max_pairs_per_batch": 30,  # 每批处理的最大实体对数（降低以适应工具调用）
            "max_retries": 2,  # 最大重试次数
            "enable_vector_prescreening": True,  # 启用向量预筛选
            "conservative_mode": True,  # 保守模式
            "tool_calling_enabled": True,  # 启用工具调用
            "max_tool_calls_per_analysis": 10,  # 每次分析最大工具调用数
            "similarity_weights": {  # 相似度权重
                "vector": 0.3,
                "llm": 0.7  # 增加LLM权重，因为包含工具调用
            }
        }
    
    def _create_state_graph(self) -> StateGraph:
        """创建LangGraph状态图（简化版）"""
        # 创建状态图
        workflow = StateGraph(EntityDeduplicationState)
        
        # 添加节点
        workflow.add_node("vector_prescreening", self.vector_prescreening_node)
        workflow.add_node("intelligent_analysis", self.intelligent_analysis_node)
        workflow.add_node("final_decision", self.final_decision_node)
        workflow.add_node("error_handler", self.error_handler_node)
        
        # 设置入口点
        workflow.set_entry_point("vector_prescreening")
        
        # 添加边和条件路由
        workflow.add_conditional_edges(
            "vector_prescreening",
            self.should_proceed_to_analysis,
            {
                "intelligent_analysis": "intelligent_analysis",
                "skip_to_decision": "final_decision",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "intelligent_analysis", 
            self.should_proceed_to_decision,
            {
                "final_decision": "final_decision",
                "error": "error_handler"
            }
        )
        
        # 最终节点连接到END
        workflow.add_edge("final_decision", END)
        workflow.add_edge("error_handler", END)
        
        return workflow.compile()
    
    # === 节点实现 ===
    
    async def vector_prescreening_node(self, state: EntityDeduplicationState) -> EntityDeduplicationState:
        """向量预筛选节点 - 第一阶段"""
        logger.info("开始向量预筛选阶段")
        state = update_step(state, "vector_prescreening")
        
        try:
            if not self.config["enable_vector_prescreening"]:
                # 跳过向量预筛选，生成所有可能的实体对
                state["prescreened_pairs"] = self._generate_all_pairs(state["entities"])
                state["prescreening_stats"] = {
                    "total_possible_pairs": len(state["prescreened_pairs"]),
                    "filtered_pairs": len(state["prescreened_pairs"]),
                    "prescreening_enabled": False
                }
                return state
            
            # 为实体生成embedding
            entities_with_embeddings = await self._ensure_embeddings(state["entities"])
            
            # 计算向量相似度矩阵
            similarity_matrix = await self._compute_similarity_matrix(entities_with_embeddings)
            
            # 基于阈值筛选实体对
            prescreened_pairs = self._filter_pairs_by_similarity(
                entities_with_embeddings, 
                similarity_matrix, 
                state["prescreening_threshold"]
            )
            
            state["prescreened_pairs"] = prescreened_pairs
            state["prescreening_stats"] = {
                "total_possible_pairs": len(list(combinations(range(len(entities_with_embeddings)), 2))),
                "filtered_pairs": len(prescreened_pairs),
                "filtering_rate": 1 - (len(prescreened_pairs) / max(1, len(list(combinations(range(len(entities_with_embeddings)), 2))))),
                "threshold_used": state["prescreening_threshold"],
                "prescreening_enabled": True
            }
            
            logger.info(f"向量预筛选完成: {state['prescreening_stats']['total_possible_pairs']} -> {len(prescreened_pairs)} 对")
            return state
            
        except Exception as e:
            error_msg = f"向量预筛选失败: {str(e)}"
            logger.error(error_msg)
            return add_error(state, error_msg)
    
    async def intelligent_analysis_node(self, state: EntityDeduplicationState) -> EntityDeduplicationState:
        """智能分析节点 - 让LLM自主决定是否使用工具"""
        logger.info("开始智能分析阶段（含工具调用）")
        state = update_step(state, "intelligent_analysis")
        
        try:
            # 构建初始分析消息
            initial_message = build_tool_aware_analysis_prompt(
                state["prescreened_pairs"], 
                state["entity_type"]
            )
            
            # 🔍 详细日志：发往Agent的Prompt
            logger.info("=" * 80)
            logger.info(f"🔍 发往LangGraph Agent的Prompt - {state['entity_type']} 类型")
            logger.info("=" * 80)
            logger.info(f"实体对数量: {len(state['prescreened_pairs'])}")
            logger.info(f"实体类型: {state['entity_type']}")
            logger.info(f"Prompt长度: {len(initial_message)} 字符")
            logger.info("📝 完整Prompt内容:")
            logger.info("-" * 40)
            logger.info(initial_message)
            logger.info("-" * 40)
            logger.info("=" * 80)
            
            # 初始化对话消息
            messages = [{"role": "system", "content": initial_message}]
            state["analysis_messages"] = messages
            state["reasoning_steps"].append("开始智能实体去重分析")
            
            # 进行多轮对话分析，允许LLM自主调用工具
            max_iterations = 5  # 最大对话轮数
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"智能分析迭代 {iteration}/{max_iterations}")
                
                # 调用带工具的LLM
                response = await self.llm_with_tools.ainvoke(messages)
                
                # 处理响应
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    # LLM决定调用工具
                    logger.info(f"LLM请求调用 {len(response.tool_calls)} 个工具")
                    
                    # 记录智能搜索决策
                    for tool_call in response.tool_calls:
                        tool_name = tool_call.get('name', 'unknown')
                        tool_args = tool_call.get('args', {})
                        entity_name = tool_args.get('entity_name', 'unknown')
                        logger.info(f"🧠 智能搜索决策: LLM选择搜索 '{entity_name}' (工具: {tool_name})")
                    
                    # 记录工具调用
                    state["tool_calls_made"].extend([
                        {
                            "iteration": iteration,
                            "tool_call": tool_call,
                            "timestamp": datetime.now().isoformat(),
                            "decision_type": "llm_initiated"  # 标记为LLM自主决策
                        }
                        for tool_call in response.tool_calls
                    ])
                    
                    # 执行工具调用
                    tool_messages = await self.tool_executor.execute_tool_calls(response.tool_calls)
                    
                    # 记录工具结果
                    state["tool_results"].extend([
                        {
                            "iteration": iteration,
                            "tool_message": tool_message,
                            "timestamp": datetime.now().isoformat()
                        }
                        for tool_message in tool_messages
                    ])
                    
                    # 将响应和工具结果添加到对话历史
                    messages.append({"role": "assistant", "content": response.content, "tool_calls": response.tool_calls})
                    messages.extend([{"role": "tool", "content": tm.content, "tool_call_id": tm.tool_call_id} for tm in tool_messages])
                    
                    # 记录推理步骤
                    state["reasoning_steps"].append(f"迭代{iteration}: 调用了{len(response.tool_calls)}个工具，获得结果")
                    
                else:
                    # LLM完成分析，没有更多工具调用
                    logger.info("🧠 智能搜索决策: LLM基于内在知识完成分析，无需外部搜索")
                    
                    # 🔍 详细日志：Agent返回结果
                    logger.info("=" * 80)
                    logger.info(f"🔍 LangGraph Agent返回结果 - {state['entity_type']} 类型")
                    logger.info("=" * 80)
                    logger.info(f"迭代次数: {iteration}")
                    logger.info(f"响应长度: {len(response.content)} 字符")
                    logger.info("📝 完整Agent响应:")
                    logger.info("-" * 40)
                    logger.info(response.content)
                    logger.info("-" * 40)
                    
                    # 解析最终分析结果
                    analysis_result = parse_tool_aware_analysis_result(response.content)
                    
                    # 🔍 详细日志：解析后的分析结果
                    logger.info("📊 解析后的分析结果:")
                    logger.info(f"  - 合并组数量: {len(analysis_result.get('merge_groups', []))}")
                    logger.info(f"  - 独立实体数量: {len(analysis_result.get('independent_entities', []))}")
                    logger.info(f"  - 不确定案例数量: {len(analysis_result.get('uncertain_cases', []))}")
                    
                    # 显示合并组详情
                    if analysis_result.get('merge_groups'):
                        logger.info("🔗 合并组详情:")
                        for i, group in enumerate(analysis_result['merge_groups']):
                            logger.info(f"  合并组 {i+1}:")
                            logger.info(f"    - 主实体: {group.get('primary_entity', 'N/A')}")
                            logger.info(f"    - 重复实体: {group.get('duplicates', [])}")
                            logger.info(f"    - 合并名称: {group.get('merged_name', 'N/A')}")
                            logger.info(f"    - 合并描述: {group.get('merged_description', 'N/A')[:100]}...")
                            logger.info(f"    - 置信度: {group.get('confidence', 'N/A')}")
                            logger.info(f"    - 理由: {group.get('reason', 'N/A')[:100]}...")
                            logger.info(f"    - Wikipedia证据: {group.get('wikipedia_evidence', 'N/A')[:100]}...")
                    
                    # 显示独立实体
                    if analysis_result.get('independent_entities'):
                        logger.info(f"🔸 独立实体: {analysis_result['independent_entities']}")
                    
                    # 显示不确定案例
                    if analysis_result.get('uncertain_cases'):
                        logger.info(f"❓ 不确定案例: {analysis_result['uncertain_cases']}")
                    
                    logger.info("=" * 80)
                    
                    state["analysis_result"] = analysis_result
                    
                    # 处理实体对结果
                    entity_pairs = process_entity_pairs_from_tool_analysis(analysis_result)
                    state["entity_pairs"] = entity_pairs
                    state["pairs_analyzed"] = len(entity_pairs)
                    
                    # 记录最终推理步骤
                    state["reasoning_steps"].append(f"迭代{iteration}: 基于内在知识完成分析，识别{len(entity_pairs)}个实体对")
                    
                    break
            
            # 更新对话历史
            state["analysis_messages"] = messages
            
            logger.info(f"智能分析完成: {state['pairs_analyzed']} 个实体对，{len(state['tool_calls_made'])} 次工具调用")
            
            # 统计搜索决策
            tool_calls_count = len(state.get('tool_calls_made', []))
            total_entities = len(state.get('entities', []))
            search_rate = (tool_calls_count / max(1, total_entities)) * 100
            logger.info(f"📊 搜索决策统计: {tool_calls_count}/{total_entities} 实体需要外部搜索 ({search_rate:.1f}%)")
            
            return state
            
        except Exception as e:
            error_msg = f"智能分析失败: {str(e)}"
            logger.error(error_msg)
            return add_error(state, error_msg)
    
    async def final_decision_node(self, state: EntityDeduplicationState) -> EntityDeduplicationState:
        """最终决策节点 - 基于智能分析结果做最终决策"""
        logger.info("开始最终决策阶段")
        state = update_step(state, "final_decision")
        
        try:
            # 基于智能分析结果进行最终决策
            if state.get("analysis_result"):
                # 直接使用智能分析的结果
                analysis_result = state["analysis_result"]
                
                # 提取合并组和独立实体
                merge_groups = analysis_result.get("merge_groups", [])
                independent_entities = analysis_result.get("independent_entities", [])
                uncertain_cases = analysis_result.get("uncertain_cases", [])
                
                # 超保守验证：进一步验证合并决策
                validated_merge_groups = self._validate_merge_decisions_ultra_conservative(
                    merge_groups, state
                )
                
                state["merge_groups"] = validated_merge_groups
                state["independent_entities"] = independent_entities
                state["uncertain_cases"] = uncertain_cases
                
                # 设置最终决策结果
                state["final_decision_result"] = {
                    "decision_summary": f"智能分析完成: {len(validated_merge_groups)} 个合并组, {len(independent_entities)} 个独立实体",
                    "merge_groups": validated_merge_groups,
                    "independent_entities": independent_entities,
                    "uncertain_cases": uncertain_cases,
                    "tool_calls_used": len(state.get("tool_calls_made", [])),
                    "reasoning_steps": state.get("reasoning_steps", [])
                }
            else:
                # 没有分析结果，保守处理
                logger.warning("无智能分析结果，保守处理所有实体为独立")
                state["merge_groups"] = []
                state["independent_entities"] = list(range(len(state["entities"]))) 
                state["uncertain_cases"] = []
                state["final_decision_result"] = {
                    "decision_summary": "无有效分析结果，保守处理",
                    "merge_groups": [],
                    "independent_entities": state["independent_entities"],
                    "uncertain_cases": []
                }
            
            # 计算处理时间
            state = calculate_processing_time(state)
            state = update_step(state, "completed")
            
            logger.info(f"最终决策完成: {len(state['merge_groups'])} 个合并组, {len(state['independent_entities'])} 个独立实体")
            return state
            
        except Exception as e:
            error_msg = f"最终决策失败: {str(e)}"
            logger.error(error_msg)
            return add_error(state, error_msg)
    
    async def error_handler_node(self, state: EntityDeduplicationState) -> EntityDeduplicationState:
        """错误处理节点"""
        logger.error("进入错误处理阶段")
        state = update_step(state, "error")
        
        # 记录错误统计
        state["final_decision_result"] = {
            "decision_summary": "处理失败，进入错误恢复模式",
            "merge_groups": [],
            "independent_entities": list(range(len(state["entities"]))),
            "uncertain_cases": [],
            "error_recovery": True
        }
        
        state["merge_groups"] = []
        state["independent_entities"] = list(range(len(state["entities"])))
        state["uncertain_cases"] = []
        
        state = calculate_processing_time(state)
        
        logger.warning(f"错误恢复: 将所有 {len(state['entities'])} 个实体标记为独立")
        return state
    
    # === 条件路由函数 ===
    
    def should_proceed_to_analysis(self, state: EntityDeduplicationState) -> str:
        """判断是否应该进入智能分析"""
        if state["current_step"] == "error":
            return "error"
        
        if not state.get("prescreened_pairs"):
            logger.info("无预筛选实体对，跳过智能分析")
            return "skip_to_decision"
        
        if len(state["prescreened_pairs"]) > self.config["max_pairs_per_batch"]:
            logger.warning(f"实体对过多 ({len(state['prescreened_pairs'])}), 可能影响性能")
        
        return "intelligent_analysis"
    
    def should_proceed_to_decision(self, state: EntityDeduplicationState) -> str:
        """判断是否应该进入最终决策"""
        if state["current_step"] == "error":
            return "error"
        
        # 智能分析完成，直接进入最终决策
        return "final_decision"
    
    # === 辅助方法 ===
    
    def _generate_all_pairs(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成所有可能的实体对"""
        pairs = []
        for i, j in combinations(range(len(entities)), 2):
            pairs.append({
                "entity1_index": i,
                "entity2_index": j,
                "entity1_name": entities[i]["name"],
                "entity2_name": entities[j]["name"],
                "vector_similarity": 1.0,  # 默认高相似度，强制LLM分析
                "from_prescreening": False
            })
        return pairs
    
    async def _ensure_embeddings(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """确保实体有embedding向量"""
        entities_need_embedding = []
        texts_to_embed = []
        
        for entity in entities:
            if not hasattr(entity, 'embedding') or entity.get('embedding') is None:
                entities_need_embedding.append(entity)
                text_repr = self._get_entity_text_representation(entity)
                texts_to_embed.append(text_repr)
        
        if texts_to_embed:
            embeddings = await self.embedding_service.embed_documents_batch(texts_to_embed)
            for i, entity in enumerate(entities_need_embedding):
                if i < len(embeddings):
                    entity['embedding'] = embeddings[i]
        
        return entities
    
    async def _compute_similarity_matrix(self, entities: List[Dict[str, Any]]) -> np.ndarray:
        """计算向量相似度矩阵"""
        embeddings = []
        for entity in entities:
            embedding = entity.get('embedding', [])
            if embedding:
                embeddings.append(np.array(embedding))
            else:
                # 创建零向量作为默认
                embeddings.append(np.zeros(384))  # 假设384维embedding
        
        if not embeddings:
            return np.zeros((len(entities), len(entities)))
        
        embeddings_matrix = np.array(embeddings)
        
        # 计算余弦相似度
        norms = np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1  # 避免除零
        normalized_embeddings = embeddings_matrix / norms
        
        similarity_matrix = np.dot(normalized_embeddings, normalized_embeddings.T)
        return similarity_matrix
    
    def _filter_pairs_by_similarity(self, entities: List[Dict[str, Any]], 
                                   similarity_matrix: np.ndarray, 
                                   threshold: float) -> List[Dict[str, Any]]:
        """基于相似度阈值筛选实体对"""
        pairs = []
        n = len(entities)
        
        for i in range(n):
            for j in range(i + 1, n):
                similarity = similarity_matrix[i, j]
                if similarity >= threshold:
                    pairs.append({
                        "entity1_index": i,
                        "entity2_index": j,
                        "entity1_name": entities[i]["name"],
                        "entity2_name": entities[j]["name"], 
                        "vector_similarity": float(similarity),
                        "from_prescreening": True
                    })
        
        return pairs
    
    def _create_list_mode_initial_state(self, entities: List[Dict[str, Any]], entity_type: str) -> EntityDeduplicationState:
        """创建列表模式的初始状态"""
        from app.models.langgraph_state import create_initial_state
        
        # 使用原有的状态创建，但跳过向量预筛选
        initial_state = create_initial_state(entities, entity_type, self.config)
        
        # 直接设置为跳过向量预筛选
        initial_state["skip_vector_prescreening"] = True
        initial_state["entities_ready_for_analysis"] = entities
        
        return initial_state
    
    async def _execute_list_mode_graph(self, initial_state: EntityDeduplicationState) -> EntityDeduplicationState:
        """执行简化的状态图流程"""
        state = initial_state
        
        try:
            # 跳过向量预筛选，直接进行智能分析
            state = await self.list_mode_analysis_node(state)
            
            # 最终决策
            if state["current_step"] != "error":
                state = await self.final_decision_node(state)
            else:
                state = await self.error_handler_node(state)
            
            return state
            
        except Exception as e:
            error_msg = f"列表模式执行失败: {str(e)}"
            logger.error(error_msg)
            state["errors"].append(error_msg)
            state["current_step"] = "error"
            return await self.error_handler_node(state)
    
    async def list_mode_analysis_node(self, state: EntityDeduplicationState) -> EntityDeduplicationState:
        """列表模式的智能分析节点"""
        logger.info("开始列表模式智能分析")
        state = update_step(state, "list_mode_analysis")
        
        try:
            # 构建列表模式的分析消息
            analysis_message = self._build_list_mode_analysis_prompt(
                state["entities_ready_for_analysis"], 
                state["entity_type"]
            )
            
            # 🔍 详细日志：发往Agent的Prompt
            logger.info("=" * 80)
            logger.info(f"🔍 发往LangGraph Agent的Prompt [列表模式] - {state['entity_type']} 类型")
            logger.info("=" * 80)
            logger.info(f"实体数量: {len(state['entities_ready_for_analysis'])}")
            logger.info(f"实体类型: {state['entity_type']}")
            logger.info(f"Prompt长度: {len(analysis_message)} 字符")
            logger.info("📝 完整Prompt内容:")
            logger.info("-" * 40)
            logger.info(analysis_message)
            logger.info("-" * 40)
            logger.info("=" * 80)
            
            # 初始化对话消息
            messages = [{"role": "system", "content": analysis_message}]
            state["analysis_messages"] = messages
            state["reasoning_steps"].append("开始列表模式实体去重分析")
            
            # 进行多轮对话分析
            max_iterations = 3  # 列表模式减少迭代次数
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"列表模式分析迭代 {iteration}/{max_iterations}")
                
                # 调用带工具的LLM
                response = await self.llm_with_tools.ainvoke(messages)
                
                # 处理响应
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    # LLM决定调用工具
                    logger.info(f"LLM请求调用 {len(response.tool_calls)} 个工具")
                    
                    # 执行工具调用
                    tool_messages = await self.tool_executor.execute_tool_calls(response.tool_calls)
                    
                    # 更新对话历史
                    messages.append({"role": "assistant", "content": response.content, "tool_calls": response.tool_calls})
                    messages.extend([{"role": "tool", "content": tm.content, "tool_call_id": tm.tool_call_id} for tm in tool_messages])
                    
                    # 记录工具调用
                    state["tool_calls_made"].extend([{
                        "iteration": iteration,
                        "tool_call": tool_call,
                        "timestamp": datetime.now().isoformat()
                    } for tool_call in response.tool_calls])
                    
                    state["reasoning_steps"].append(f"迭代{iteration}: 调用了{len(response.tool_calls)}个工具")
                    
                else:
                    # LLM完成分析
                    logger.info("🧠 智能分析完成：基于实体列表的语义分析")
                    
                    # 🔍 详细日志：Agent返回结果
                    logger.info("=" * 80)
                    logger.info(f"🔍 LangGraph Agent返回结果 [列表模式] - {state['entity_type']} 类型")
                    logger.info("=" * 80)
                    logger.info(f"迭代次数: {iteration}")
                    logger.info(f"响应长度: {len(response.content)} 字符")
                    logger.info("📝 完整Agent响应:")
                    logger.info("-" * 40)
                    logger.info(response.content)
                    logger.info("-" * 40)
                    
                    # 解析分析结果
                    analysis_result = self._parse_list_mode_analysis_result(response.content, state["entities_ready_for_analysis"])
                    
                    # 详细日志：解析结果
                    logger.info("📊 解析后的分析结果:")
                    logger.info(f"  - 合并组数量: {len(analysis_result.get('merge_groups', []))}")
                    logger.info(f"  - 独立实体数量: {len(analysis_result.get('independent_entities', []))}")
                    
                    logger.info("=" * 80)
                    
                    state["analysis_result"] = analysis_result
                    break
            
            # 更新状态
            state["analysis_messages"] = messages
            logger.info(f"列表模式分析完成: {len(state.get('tool_calls_made', []))} 次工具调用")
            
            return state
            
        except Exception as e:
            error_msg = f"列表模式分析失败: {str(e)}"
            logger.error(error_msg)
            return add_error(state, error_msg)
    
    def _build_list_mode_analysis_prompt(self, entities: List[Dict[str, Any]], entity_type: str) -> str:
        """构建列表模式的分析prompt"""
        
        type_mapping = {
            "组织": "Organization", "人物": "Person", "地点": "Location", 
            "产品": "Product", "技术": "Technology", "时间": "Time", "事件": "Event"
        }
        english_type = type_mapping.get(entity_type, entity_type)
        
        # 构建实体列表字符串
        entities_text = ""
        for i, entity in enumerate(entities, 1):
            name = entity.get('name', 'Unknown')
            description = entity.get('description', '')
            aliases = entity.get('aliases', [])
            entity_id = entity.get('id', f'entity_{i}')
            
            entities_text += f"{i}. **{name}** (ID: {entity_id})\n"
            if description:
                entities_text += f"   - 描述: {description}\n"
            if aliases:
                entities_text += f"   - 别名: {', '.join(aliases)}\n"
            entities_text += "\n"
        
        prompt = f"""你是一个专业的知识库工程师，擅长实体消歧与知识融合。你的任务是对用户上传的异构数据进行智能合并，识别表述不同但指向相同实体的节点。\n\n**实体类型**: {english_type} ({entity_type})\n**处理实体数量**: {len(entities)}\n\n**实体列表**:\n{entities_text}\n\n**工作流程**:\n\n1. **实体提取**: 识别每个实体的核心特征\n2. **特征分析**: 对每个实体提取以下特征：\n   - 核心名称（标准化形式）\n   - 别名/缩写/变体\n   - 上下文特征（相关属性、关系）\n   - 领域分类\n\n3. **消歧处理**: 对存在歧义的实体，通过以下步骤处理：\n   a) 检查上下文语义特征\n   b) 使用Wikipedia工具查询候选解释\n   c) 构建消歧决策树：\n      - 如果Wikipedia存在明确区分页→采用标准名称\n      - 如果存在消歧页→选择与上下文最匹配的选项\n      - 无匹配→标记为待验证实体\n\n4. **合并规则**:\n   - **强制性合并**: 完全相同的规范化名称\n   - **高置信度合并**: \n     * 别名字典匹配（如\"MIT\"→\"麻省理工学院\"）\n     * Wikipedia重定向匹配\n     * 相同属性值\n   - **需人工审核的合并**: \n     * 部分属性冲突\n     * 跨语言实体（如\"Beijing\" vs \"北京\"）\n\n**特别注意**:\n- 对于人物实体，不同的人即使职位相似也绝不能合并\n- 对于组织实体，不同的公司/机构即使行业相同也绝不能合并\n- 只有在有明确证据证明是同一实体的不同表述时才能合并\n\n**输出格式**:\n请返回JSON格式的分析结果：\n\n```json\n{{\n  \"analysis_summary\": \"分析总结\",\n  \"merge_groups\": [\n    {{\n      \"primary_entity\": \"1\",\n      \"primary_entity_id\": \"entity_13a7bde4\",\n      \"duplicates\": [\"3\", \"5\"],\n      \"duplicate_entity_ids\": [\"entity_01d6297c\", \"entity_4f7e298d\"],\n      \"merged_name\": \"标准化名称\",\n      \"merged_description\": \"统一描述\",\n      \"confidence\": 0.95,\n      \"reason\": \"合并理由（必须包含具体证据）\",\n      \"wikipedia_evidence\": \"Wikipedia查询结果作为证据\"\n    }}\n  ],\n  \"independent_entities\": [\"2\", \"4\", \"6\", \"7\"],\n  \"uncertain_cases\": [\n    {{\n      \"entities\": [\"8\", \"9\"], \n      \"reason\": \"需要人工审核的原因\"\n    }}\n  ]\n}}\n```\n\n**开始分析**: 请对上述 {len(entities)} 个{entity_type}实体进行智能消歧与知识融合分析。"""
        
        return prompt
    
    def _parse_list_mode_analysis_result(self, response_content: str, entities: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """解析列表模式的分析结果"""
        try:
            # 尝试提取JSON内容
            import re
            import json
            
            # 查找JSON代码块
            json_match = re.search(r'```json\s*(.*?)\s*```', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 如果没有代码块，尝试查找JSON对象
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    logger.warning("无法在响应中找到JSON格式的结果")
                    return self._create_default_analysis_result(response_content)
            
            try:
                parsed_result = json.loads(json_str)
                
                # 验证必要字段
                if not isinstance(parsed_result, dict):
                    raise ValueError("解析结果不是字典格式")
                
                # 确保必要字段存在
                required_fields = ["merge_groups", "independent_entities"]
                for field in required_fields:
                    if field not in parsed_result:
                        parsed_result[field] = []
                
                # 确保optional字段存在
                if "uncertain_cases" not in parsed_result:
                    parsed_result["uncertain_cases"] = []
                if "analysis_summary" not in parsed_result:
                    parsed_result["analysis_summary"] = "实体消歧与知识融合分析完成"
                
                # 🔧 新增：ID提取逻辑
                if entities is not None:
                    parsed_result = self._enhance_result_with_entity_ids(parsed_result, entities)
                
                return parsed_result
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {str(e)}")
                return self._create_default_analysis_result(response_content)
                
        except Exception as e:
            logger.error(f"分析结果解析失败: {str(e)}")
            return self._create_default_analysis_result(response_content)
    
    def _enhance_result_with_entity_ids(self, parsed_result: Dict[str, Any], entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """增强解析结果，添加实体ID信息"""
        logger.info("开始增强解析结果，添加实体ID信息")
        
        # 安全地转换索引为实体ID
        def safe_index_to_id(index_str: str) -> Tuple[Optional[str], Optional[int]]:
            """安全地将索引字符串转换为实体ID和索引"""
            try:
                # 转换为0-based索引
                index = int(index_str) - 1 if index_str.isdigit() else int(index_str)
                if index < 0:
                    index = int(index_str) - 1 if int(index_str) > 0 else 0
                
                if 0 <= index < len(entities):
                    entity_id = entities[index].get('id', f'entity_{index}')
                    return entity_id, index
                else:
                    logger.warning(f"索引 {index_str} 超出实体范围 (0-{len(entities)-1})")
                    return None, None
            except (ValueError, TypeError) as e:
                logger.warning(f"无法转换索引 '{index_str}': {str(e)}")
                return None, None
        
        # 增强合并组
        enhanced_merge_groups = []
        for group in parsed_result.get("merge_groups", []):
            if not isinstance(group, dict):
                continue
            
            enhanced_group = dict(group)
            
            # 处理主实体ID
            primary_entity = group.get("primary_entity", "1")
            primary_entity_id, primary_index = safe_index_to_id(str(primary_entity))
            if primary_entity_id:
                enhanced_group["primary_entity_id"] = primary_entity_id
                enhanced_group["primary_entity_index"] = primary_index
            
            # 处理重复实体ID
            duplicates = group.get("duplicates", [])
            duplicate_entity_ids = []
            duplicate_indices = []
            
            for dup in duplicates:
                dup_id, dup_index = safe_index_to_id(str(dup))
                if dup_id and dup_index is not None:
                    duplicate_entity_ids.append(dup_id)
                    duplicate_indices.append(dup_index)
            
            enhanced_group["duplicate_entity_ids"] = duplicate_entity_ids
            enhanced_group["duplicate_indices"] = duplicate_indices
            
            enhanced_merge_groups.append(enhanced_group)
            
            logger.debug(f"增强合并组: 主实体 {primary_entity} -> ID {primary_entity_id}, "
                        f"重复实体 {duplicates} -> IDs {duplicate_entity_ids}")
        
        parsed_result["merge_groups"] = enhanced_merge_groups
        
        logger.info(f"完成实体ID增强，处理了 {len(enhanced_merge_groups)} 个合并组")
        return parsed_result
    
    def _create_default_analysis_result(self, response_content: str) -> Dict[str, Any]:
        """创建默认的分析结果"""
        return {
            "analysis_summary": f"解析失败，保守处理所有实体为独立: {response_content[:100]}...",
            "merge_groups": [],
            "independent_entities": [],
            "uncertain_cases": [],
            "parsing_error": True
        }
    
    def _get_entity_text_representation(self, entity: Dict[str, Any]) -> str:
        """获取实体的文本表示"""
        parts = [entity.get("name", "")]
        
        if entity.get("type"):
            parts.append(f"类型:{entity['type']}")
        
        if entity.get("description"):
            parts.append(f"描述:{entity['description']}")
        
        return " ".join(parts)
    
    # === 公共接口 ===
    
    async def deduplicate_entities_list(self, entities: List[Dict[str, Any]], entity_type: str) -> Dict[str, Any]:
        """
        执行实体去重（新的实体列表模式）
        
        Args:
            entities: 实体列表，每个实体包含name、description、type等信息
            entity_type: 实体类型
            
        Returns:
            分析结果字典
        """
        logger.info(f"开始LangGraph实体去重: {entity_type} 类型, {len(entities)} 个实体 [列表模式]")
        
        # 创建简化的初始状态（跳过向量预筛选）
        initial_state = self._create_list_mode_initial_state(entities, entity_type)
        
        # 执行简化的状态图（跳过向量预筛选）
        final_state = await self._execute_list_mode_graph(initial_state)
        
        # 格式化结果
        return self._format_result(final_state)
    
    async def deduplicate_entities(self, entities: List[Dict[str, Any]], entity_type: str) -> Dict[str, Any]:
        """执行实体去重（向后兼容接口）"""
        logger.info(f"开始LangGraph实体去重: {entity_type} 类型, {len(entities)} 个实体 [兼容模式]")
        
        # 兼容性处理：使用新的列表模式
        return await self.deduplicate_entities_list(entities, entity_type)
    
    def _format_result(self, state: EntityDeduplicationState) -> Dict[str, Any]:
        """格式化结果为标准格式"""
        
        def safe_int_conversion(value, default=0):
            """安全地将值转换为整数"""
            if isinstance(value, int):
                return value
            elif isinstance(value, (str, float)):
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default
            else:
                return default
        
        def safe_format_merge_groups(groups):
            """安全地格式化合并组"""
            formatted_groups = []
            for group in groups:
                if not isinstance(group, dict):
                    continue
                
                # 处理LLM返回的索引格式
                primary_entity = group.get("primary_entity", "1")
                duplicates = group.get("duplicates", [])
                
                # 确保duplicates是列表格式
                if not isinstance(duplicates, list):
                    duplicates = []
                
                formatted_groups.append({
                    "primary_entity": str(primary_entity),
                    "duplicates": [str(dup) for dup in duplicates],
                    "primary_entity_id": group.get("primary_entity_id", ""),
                    "duplicate_entity_ids": group.get("duplicate_entity_ids", []),
                    "merged_name": group.get("merged_name", ""),
                    "merged_description": group.get("merged_description", ""),
                    "confidence": group.get("confidence", 0.0),
                    "reason": group.get("reason", ""),
                    "wikipedia_evidence": group.get("wikipedia_evidence", "")
                })
            
            return formatted_groups
        
        def safe_format_independent_entities(entities):
            """安全地格式化独立实体"""
            if not isinstance(entities, list):
                return []
            
            formatted_entities = []
            for idx in entities:
                safe_idx = safe_int_conversion(idx)
                formatted_entities.append(str(safe_idx + 1))
            
            return formatted_entities
        
        try:
            return {
                "analysis_summary": state.get("final_decision_result", {}).get("decision_summary", "LangGraph分析完成"),
                "merge_groups": safe_format_merge_groups(state.get("merge_groups", [])),
                "independent_entities": safe_format_independent_entities(state.get("independent_entities", [])),
                "uncertain_cases": state.get("uncertain_cases", []),
                "statistics": {
                    "processing_strategy": "langgraph_agent",
                    "total_entities": state.get("total_entities", 0),
                    "pairs_analyzed": state.get("pairs_analyzed", 0), 
                    "tool_calls_performed": len(state.get("tool_calls_made", [])),
                    "processing_time": state.get("processing_time", 0.0),
                    "prescreening_stats": state.get("prescreening_stats", {}),
                    "current_step": state.get("current_step", "unknown"),
                    "steps_completed": len(state.get("step_history", [])),
                    "reasoning_steps": len(state.get("reasoning_steps", []))
                },
                "errors": state.get("errors", []),
                "warnings": state.get("warnings", [])
            }
        except Exception as e:
            logger.error(f"结果格式化失败: {str(e)}")
            # 返回安全的默认结果
            return {
                "analysis_summary": f"结果格式化失败: {str(e)}",
                "merge_groups": [],
                "independent_entities": [str(i + 1) for i in range(len(state.get("entities", [])))],
                "uncertain_cases": [],
                "statistics": {
                    "processing_strategy": "langgraph_agent_with_error",
                    "total_entities": len(state.get("entities", [])),
                    "pairs_analyzed": 0,
                    "tool_calls_performed": 0,
                    "processing_time": 0.0,
                    "prescreening_stats": {},
                    "current_step": "error",
                    "steps_completed": 0,
                    "reasoning_steps": 0
                },
                "errors": state.get("errors", []) + [f"结果格式化失败: {str(e)}"],
                "warnings": state.get("warnings", [])
            }


# === 保守分析方法 ===

    def _build_conservative_analysis_prompt(self, prescreened_pairs: List[Dict[str, Any]], entity_type: str) -> str:
        """构建超保守的分析prompt"""
        
        type_mapping = {
            "组织": "Organization", "人物": "Person", "地点": "Location", 
            "产品": "Product", "技术": "Technology", "时间": "Time", "事件": "Event"
        }
        english_type = type_mapping.get(entity_type, entity_type)
        
        prompt = f"""You are an ULTRA-CONSERVATIVE {english_type} entity deduplication expert for a LangGraph Agent system.\n\n🚨 CRITICAL MISSION: Prevent ANY incorrect merges. False negatives are acceptable, false positives are CATASTROPHIC.\n\n⛔ ABSOLUTE PROHIBITIONS - NEVER MERGE:\n- Different companies: Apple ≠ Google ≠ Microsoft ≠ Amazon ≠ Stanford University ≠ OpenAI\n- Different people: Steve Jobs ≠ Tim Cook ≠ Sundar Pichai ≠ Satya Nadella ≠ Elon Musk\n- Competitors in ANY industry\n- Different organization types: University ≠ Corporation ≠ Government ≠ NGO\n- Different time periods or contexts\n- ANY entities where you have even 1% doubt\n\n✅ ONLY SUGGEST MERGING IF:\n- IDENTICAL names in different languages (Apple Inc ↔ 苹果公司)\n- OBVIOUS abbreviations of EXACT SAME entity (IBM ↔ International Business Machines)\n- CONFIRMED aliases with 100% certainty\n\nCONFIDENCE LEVELS (Use EXTREMELY sparingly):\n- high: 99.9% certain identical entity (e.g., \"Apple Inc\" vs \"Apple Incorporated\")\n- medium: Possible same entity, MUST have Wikipedia verification  \n- low: Uncertain, requires extensive research\n\nTARGET: Maximum 5% of pairs should be anything above 'low'. Default to rejecting merges.\n\nEntity Pairs to Analyze:\n"""
        
        for i, pair in enumerate(prescreened_pairs[:50]):  # 限制数量避免prompt过长
            prompt += f"\nPair {i+1}:\n"
            prompt += f"  - Entity A: {pair['entity1_name']}\n"
            prompt += f"  - Entity B: {pair['entity2_name']}\n"
            prompt += f"  - Vector Similarity: {pair.get('vector_similarity', 0.0):.3f}\n"
        
        if len(prescreened_pairs) > 50:
            prompt += f"\n... and {len(prescreened_pairs) - 50} more pairs (truncated for analysis)\n"
        
        prompt += """\nReturn JSON format analysis:\n```json\n{\n  \"analysis_summary\": \"Ultra-conservative analysis with extreme prejudice against merging\",\n  \"entity_pairs\": [\n    {\n      \"entity1_index\": 0,\n      \"entity2_index\": 1,\n      \"entity1_name\": \"Entity 1 name\",\n      \"entity2_name\": \"Entity 2 name\", \n      \"confidence\": \"low\",\n      \"similarity_score\": 0.3,\n      \"reason\": \"Specific reason why they might be related\",\n      \"needs_verification\": true,\n      \"rejection_reason\": \"Why they should NOT be merged (always consider this)\"\n    }\n  ]\n}\n```\n\nREMEMBER: When in doubt, REJECT the merge. Better to have 1000 duplicates than 1 wrong merge."""
        
        return prompt
    
    def _process_entity_pairs_conservative(self, raw_pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理实体对，强制更保守的置信度"""
        processed_pairs = []
        
        for pair in raw_pairs:
            # 强制降级所有high confidence到medium
            original_confidence = pair.get("confidence", "low")
            if original_confidence == "high":
                # 只有极少数情况才保持high confidence
                entity1_name = pair.get("entity1_name", "")
                entity2_name = pair.get("entity2_name", "")
                
                # 更严格的high confidence标准
                is_truly_identical = (
                    entity1_name.lower().strip() == entity2_name.lower().strip() or
                    (len(entity1_name) <= 4 and entity1_name.upper() in entity2_name.upper()) or
                    (len(entity2_name) <= 4 and entity2_name.upper() in entity1_name.upper())
                )
                
                if not is_truly_identical:
                    pair["confidence"] = "medium"
                    pair["reason"] = f"降级: {pair.get('reason', '')} (自动保守化)"
                    logger.info(f"强制降级置信度: {entity1_name} vs {entity2_name}")
            
            # 强制所有实体对都需要验证
            pair["needs_verification"] = True
            
            processed_pairs.append(pair)
        
        return processed_pairs
    
    def _build_final_decision_prompt(self, state: EntityDeduplicationState) -> str:
        """构建最终决策prompt"""
        
        type_mapping = {
            "组织": "Organization", "人物": "Person", "地点": "Location", 
            "产品": "Product", "技术": "Technology", "时间": "Time", "事件": "Event"
        }
        english_type = type_mapping.get(state["entity_type"], state["entity_type"])
        
        prompt = f"""FINAL DECISION for {english_type} entity merging in LangGraph Agent.\n\n🚨 ULTRA-CONSERVATIVE FINAL VALIDATION 🚨\n\nPrevious Analysis Results:\n{json.dumps(state.get("analysis_result", {}), ensure_ascii=False, indent=2)}\n\nWikipedia Verification Results:\n"""
        
        # 从tool_results中获取Wikipedia搜索结果
        for tool_result in state.get("tool_results", []):
            if tool_result.get("tool_name") == "search_wikipedia_entity":
                tool_input = tool_result.get("input", {})
                entity_name = tool_input.get("entity_name", "Unknown")
                result_data = tool_result.get("result", {})
                
                prompt += f"\nEntity: {entity_name}\n"
                if result_data.get("found"):
                    prompt += f"  - Title: {result_data.get('title', 'N/A')}\n"
                    prompt += f"  - Summary: {result_data.get('summary', 'N/A')[:200]}...\n"
                    prompt += f"  - URL: {result_data.get('url', 'N/A')}\n"
                else:
                    prompt += f"  - No Wikipedia entry found\n"
                    if result_data.get("error"):
                        prompt += f"  - Error: {result_data['error']}\n"
        
        prompt += f"""\n🔒 FINAL MERGE CONDITIONS (ALL must be TRUE):\n1. Wikipedia EXPLICITLY confirms they are IDENTICAL entities\n2. One redirects to other OR explicitly states aliases\n3. ZERO contradictory evidence found\n4. Confidence ≥ 0.98 (98% certainty minimum)\n5. Common sense verification passes\n6. No competing interpretations exist\n\n❌ IMMEDIATE REJECTION IF:\n- Different Wikipedia pages exist for both\n- No clear Wikipedia confirmation\n- ANY conflicting information detected\n- Different entity categories/types\n- ANY doubt whatsoever exists\n\n🔍 FINAL CONTRADICTION CHECK:\nBefore ANY merge suggestion, verify:\n- Are they competitors or rivals?\n- Do they serve different functions?\n- Are they from different domains?\n- Could they coexist independently?\n\nReturn JSON format FINAL decision:\n```json\n{{\n  \"decision_summary\": \"Ultra-conservative final decision with exhaustive verification\",\n  \"merge_groups\": [\n    {{\n      \"primary_entity_index\": 0,\n      \"duplicate_indices\": [1],\n      \"merged_name\": \"Verified identical entity name\",\n      \"merged_description\": \"Verified description\", \n      \"confidence\": 0.98,\n      \"reason\": \"Wikipedia explicitly confirms identical entity with redirect\",\n      \"wikipedia_evidence\": \"Specific Wikipedia evidence\",\n      \"final_verification\": \"Passed ultra-conservative validation\"\n    }}\n  ],\n  \"independent_entities\": [2, 3, 4, 5, 6, 7, 8],\n  \"uncertain_cases\": [\n    {{\n      \"entities\": [9, 10], \n      \"reason\": \"Insufficient evidence for safe merging - keeping separate\"\n    }}\n  ]\n}}\n```\n\nDEFAULT DECISION: Keep entities separate unless overwhelming evidence proves they are identical."""
        
        return prompt
    
    def _parse_llm_analysis(self, response_content: str) -> Dict[str, Any]:
        """解析LLM分析响应"""
        try:
            json_match = self._extract_json_from_response(response_content)
            if json_match:
                return json.loads(json_match)
            else:
                raise ValueError("无法找到有效的JSON响应")
        except Exception as e:
            logger.error(f"解析LLM分析响应失败: {str(e)}")
            return {"analysis_summary": "解析失败", "entity_pairs": []}
    
    def _parse_final_decision(self, response_content: str) -> Dict[str, Any]:
        """解析最终决策响应"""
        try:
            json_match = self._extract_json_from_response(response_content)
            if json_match:
                return json.loads(json_match)
            else:
                raise ValueError("无法找到有效的JSON响应")
        except Exception as e:
            logger.error(f"解析最终决策响应失败: {str(e)}")
            return {
                "decision_summary": "解析失败",
                "merge_groups": [],
                "independent_entities": [],
                "uncertain_cases": []
            }
    
    def _extract_json_from_response(self, response_content: str) -> Optional[str]:
        """从响应中提取JSON内容"""
        import re
        
        # 尝试提取```json...```格式
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
        if json_match:
            return json_match.group(1)
        
        # 尝试直接查找JSON对象
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_content, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return None
    
    async def _search_wikipedia_for_entity(self, entity: Dict[str, Any], entity_type: str) -> Dict[str, Any]:
        """为单个实体搜索Wikipedia"""
        try:
            search_result = self.wikipedia_server.search_entity(
                entity_name=entity["name"],
                entity_type=entity_type
            )
            return search_result
        except Exception as e:
            logger.error(f"Wikipedia搜索失败: {entity['name']}, 错误: {str(e)}")
            return {
                "entity_name": entity["name"],
                "found": False,
                "error": str(e)
            }
    
    def _validate_merge_decisions_ultra_conservative(self, merge_groups: List[Dict[str, Any]], 
                                                   state: EntityDeduplicationState) -> List[Dict[str, Any]]:
        """超保守的合并决策验证（优化版）"""
        
        # 🔍 详细日志：超保守验证开始
        logger.info("=" * 80)
        logger.info(f"🔍 超保守验证开始（优化版）- {state.get('entity_type', 'Unknown')} 类型")
        logger.info("=" * 80)
        logger.info(f"待验证的合并组数量: {len(merge_groups)}")
        logger.info("验证标准层次:")
        logger.info("  🚀 强制合并层级:")
        logger.info("    - 完全相同的名称（忽略大小写和空格）")
        logger.info("    - 明显的别名映射（如 Tim Cook ↔ Timothy Cook）")
        logger.info("    - 跨语言同实体（如 Tim Cook ↔ 蒂姆·库克）")
        logger.info("  📊 标准验证层级:")
        logger.info("    - 置信度 >= 0.95 (95%)")
        logger.info("    - 必须有Wikipedia证据")
        logger.info("    - 证据包含 'redirect', 'alias', 或 'same' 关键词")
        logger.info("-" * 40)
        
        validated_groups = []
        
        def safe_int_conversion(value, default=None):
            """安全地将值转换为整数"""
            if isinstance(value, int):
                return value
            elif isinstance(value, (str, float)):
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default
            else:
                return default
        
        def should_force_merge(group: Dict[str, Any], state: EntityDeduplicationState) -> Tuple[bool, str]:
            """判断是否应该强制合并（明显重复的实体）"""
            
            try:
                # 获取实体名称
                primary_entity_idx = safe_int_conversion(group.get("primary_entity", "1"), 1) - 1
                duplicate_indices = []
                for dup in group.get("duplicates", []):
                    dup_idx = safe_int_conversion(dup, 1) - 1
                    if dup_idx >= 0:
                        duplicate_indices.append(dup_idx)
                
                if primary_entity_idx < 0 or not duplicate_indices:
                    return False, "无效的实体索引"
                
                entities = state.get("entities_ready_for_analysis") or state.get("entities", [])
                if primary_entity_idx >= len(entities):
                    return False, "主实体索引超出范围"
                
                primary_name = entities[primary_entity_idx].get("name", "").strip()
                duplicate_names = []
                for dup_idx in duplicate_indices:
                    if dup_idx < len(entities):
                        duplicate_names.append(entities[dup_idx].get("name", "").strip())
                
                if not primary_name or not duplicate_names:
                    return False, "实体名称为空"
                
                # 强制合并规则检查
                for dup_name in duplicate_names:
                    
                    # 1. 完全相同的标准化名称
                    if primary_name.lower().replace(" ", "").replace("-", "").replace(".", "") == \
                       dup_name.lower().replace(" ", "").replace("-", "").replace(".", ""):
                        return True, f"完全相同的标准化名称: '{primary_name}' ≡ '{dup_name}'"
                    
                    # 2. 明显的英文别名模式
                    eng_aliases = [
                        ("Timothy Cook", "Tim Cook"),
                        ("Timothy D. Cook", "Tim Cook"), 
                        ("Jeffrey Bezos", "Jeff Bezos"),
                        ("Jeffrey P. Bezos", "Jeff Bezos"),
                        ("Steven Jobs", "Steve Jobs"),
                        ("Steven P. Jobs", "Steve Jobs"),
                        ("William Gates", "Bill Gates"),
                        ("William H. Gates", "Bill Gates"),
                        ("Mark Zuckerberg", "Mark Elliot Zuckerberg"),
                        ("Sundar Pichai", "Pichai Sundararajan"),
                        ("Elon Musk", "Elon Reeve Musk")
                    ]
                    
                    for full_name, short_name in eng_aliases:
                        if (primary_name.lower() == full_name.lower() and dup_name.lower() == short_name.lower()) or \
                           (primary_name.lower() == short_name.lower() and dup_name.lower() == full_name.lower()):
                            return True, f"明显的英文别名: '{primary_name}' ↔ '{dup_name}'"
                    
                    # 3. 跨语言同实体模式（中英文）
                    cross_lang_pairs = [
                        ("Tim Cook", "蒂姆·库克"),
                        ("Timothy Cook", "蒂姆·库克"),
                        ("Jeff Bezos", "杰夫·贝索斯"),
                        ("Jeffrey Bezos", "杰夫·贝索斯"),
                        ("Steve Jobs", "史蒂夫·乔布斯"),
                        ("Steven Jobs", "史蒂夫·乔布斯"),
                        ("Bill Gates", "比尔·盖茨"),
                        ("William Gates", "比尔·盖茨"),
                        ("Mark Zuckerberg", "马克·扎克伯格"),
                        ("Elon Musk", "埃隆·马斯克"),
                        ("Sundar Pichai", "桑达尔·皮查伊"),
                        ("Apple", "苹果公司"),
                        ("Apple Inc", "苹果公司"),
                        ("Microsoft", "微软公司"),
                        ("Google", "谷歌公司"),
                        ("Amazon", "亚马逊公司")
                    ]
                    
                    for eng_name, chn_name in cross_lang_pairs:
                        if (primary_name.lower() == eng_name.lower() and dup_name == chn_name) or \
                           (primary_name == chn_name and dup_name.lower() == eng_name.lower()):
                            return True, f"跨语言同实体: '{primary_name}' ↔ '{dup_name}'"
                    
                    # 4. 公司名称后缀变体
                    if state.get('entity_type') in ['组织', 'Organization']:
                        # 移除常见公司后缀进行比较
                        def normalize_company_name(name):
                            suffixes = [" Inc", " Inc.", " Corporation", " Corp", " Corp.", " Company", " Co", " Co.", 
                                       " Limited", " Ltd", " Ltd.", " LLC", "公司", "集团", "有限公司"]
                            normalized = name
                            for suffix in suffixes:
                                if normalized.endswith(suffix):
                                    normalized = normalized[:-len(suffix)].strip()
                            return normalized.lower()
                        
                        if normalize_company_name(primary_name) == normalize_company_name(dup_name):
                            return True, f"公司名称后缀变体: '{primary_name}' ↔ '{dup_name}'"
                    
                    # 5. 检查是否是高置信度的明显重复
                    confidence = group.get("confidence", 0.0)
                    if confidence >= 0.98:  # 98%以上置信度
                        # 检查名称相似度
                        similarity_indicators = [
                            primary_name.lower() in dup_name.lower(),
                            dup_name.lower() in primary_name.lower(),
                            len(set(primary_name.lower().split()) & set(dup_name.lower().split())) >= 2
                        ]
                        
                        if any(similarity_indicators):
                            return True, f"超高置信度相似实体: '{primary_name}' ↔ '{dup_name}' (置信度: {confidence})"
                
                return False, "不符合强制合并条件"
                
            except Exception as e:
                logger.warning(f"强制合并检查失败: {str(e)}")
                return False, f"检查异常: {str(e)}"
        
        for i, group in enumerate(merge_groups):
            if not isinstance(group, dict):
                logger.warning(f"  合并组 {i+1}: 无效格式，跳过")
                continue
                
            # 提取验证信息
            confidence = group.get("confidence", 0.0)
            wikipedia_evidence = group.get("wikipedia_evidence", "")
            merged_name = group.get("merged_name", "Unknown")
            primary_entity = group.get("primary_entity", "Unknown")
            duplicates = group.get("duplicates", [])
            reason = group.get("reason", "")
            
            # 🔍 详细日志：单个合并组验证
            logger.info(f"  验证合并组 {i+1}: {merged_name}")
            logger.info(f"    - 主实体: {primary_entity}")
            logger.info(f"    - 重复实体: {duplicates}")
            logger.info(f"    - 置信度: {confidence}")
            logger.info(f"    - 理由: {reason[:100]}..." if reason else "    - 理由: 无")
            logger.info(f"    - Wikipedia证据: {wikipedia_evidence[:100]}..." if wikipedia_evidence else "    - Wikipedia证据: 无")
            
            # 首先检查是否应该强制合并
            should_force, force_reason = should_force_merge(group, state)
            
            if should_force:
                logger.info(f"    🚀 强制合并触发: {force_reason}")
                validated_groups.append(group)
                logger.info(f"    🎉 合并决策通过强制合并: {merged_name}")
                continue
            
            # 标准验证流程
            validation_results = []
            
            # 1. 置信度验证
            confidence_ok = confidence >= 0.95
            validation_results.append(("置信度 >= 0.95", confidence_ok, f"实际值: {confidence}"))
            
            # 2. Wikipedia证据存在验证
            evidence_exists = bool(wikipedia_evidence)
            validation_results.append(("Wikipedia证据存在", evidence_exists, f"长度: {len(wikipedia_evidence)}"))
            
            # 3. 证据关键词验证 - 放宽标准
            evidence_keywords = evidence_exists and (
                any(keyword in wikipedia_evidence.lower() for keyword in ["redirect", "alias", "same"]) or
                # 新增的宽松关键词
                any(keyword in wikipedia_evidence.lower() for keyword in ["also known", "commonly called", "refers to", "identical", "equivalent"])
            )
            validation_results.append(("证据包含相关关键词", evidence_keywords, f"检查: redirect, alias, same, also known, etc."))
            
            # 4. 放宽的验证标准
            passes_validation = confidence_ok and evidence_exists and evidence_keywords
            
            logger.info(f"    验证结果:")
            for criterion, passed, detail in validation_results:
                status = "✅ 通过" if passed else "❌ 失败"
                logger.info(f"      - {criterion}: {status} ({detail})")
            
            if passes_validation:
                validated_groups.append(group)
                logger.info(f"    🎉 合并决策通过标准验证: {merged_name}")
            else:
                logger.warning(f"    ⚠️ 合并决策未通过验证: {merged_name}")
                
                # 详细说明拒绝原因
                rejection_reasons = []
                if not confidence_ok:
                    rejection_reasons.append(f"置信度不足 ({confidence} < 0.95)")
                if not evidence_exists:
                    rejection_reasons.append("缺少Wikipedia证据")
                if not evidence_keywords:
                    rejection_reasons.append("证据不包含相关关键词")
                
                logger.warning(f"    拒绝理由: {'; '.join(rejection_reasons)}")
                
                # 将被拒绝的合并添加到独立实体列表（安全类型转换）
                primary_idx = safe_int_conversion(group.get("primary_entity_index"))
                duplicate_indices = group.get("duplicate_indices", [])
                
                if primary_idx is not None and primary_idx not in state["independent_entities"]:
                    state["independent_entities"].append(primary_idx)
                    logger.info(f"    → 将主实体 {primary_idx} 标记为独立")
                    
                if isinstance(duplicate_indices, list):
                    for dup_idx in duplicate_indices:
                        safe_dup_idx = safe_int_conversion(dup_idx)
                        if safe_dup_idx is not None and safe_dup_idx not in state["independent_entities"]:
                            state["independent_entities"].append(safe_dup_idx)
                            logger.info(f"    → 将重复实体 {safe_dup_idx} 标记为独立")
            
            logger.info("")  # 空行分隔
        
        # 🔍 详细日志：验证总结
        logger.info("📊 超保守验证总结（优化版）:")
        logger.info(f"  - 输入合并组: {len(merge_groups)}")
        logger.info(f"  - 通过验证: {len(validated_groups)}")
        logger.info(f"  - 被拒绝: {len(merge_groups) - len(validated_groups)}")
        logger.info(f"  - 验证通过率: {len(validated_groups) / len(merge_groups) * 100:.1f}%" if merge_groups else "  - 验证通过率: 0%")
        
        if validated_groups:
            logger.info("✅ 通过验证的合并组:")
            for i, group in enumerate(validated_groups):
                logger.info(f"  {i+1}. {group.get('merged_name', 'Unknown')} (置信度: {group.get('confidence', 0.0)})")
        else:
            logger.warning("⚠️ 没有合并组通过验证")
            
        logger.info("=" * 80)
        
        return validated_groups


# === 全局实例和工厂函数 ===

_langgraph_agent_instance = None

def get_langgraph_entity_deduplication_agent(config: Optional[Dict[str, Any]] = None) -> LangGraphEntityDeduplicationAgent:
    """获取LangGraph实体去重Agent实例（单例模式）"""
    global _langgraph_agent_instance
    if _langgraph_agent_instance is None:
        _langgraph_agent_instance = LangGraphEntityDeduplicationAgent(config)
    return _langgraph_agent_instance