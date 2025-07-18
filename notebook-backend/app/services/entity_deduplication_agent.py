# -*- coding: utf-8 -*-
"""
实体去重Agent
使用LangGraph实现基于Wikipedia搜索的智能实体去重
"""
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.services.llm_client_service import LLMClientService
from app.services.wikipedia_mcp_server import get_wikipedia_mcp_server
from app.models.agent_state import EntityAnalysisState, AgentConfig, EntityPair, SearchResult, MergeDecision

logger = logging.getLogger(__name__)

class EntityDeduplicationAgent:
    """实体去重Agent"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """
        初始化实体去重Agent
        
        Args:
            config: Agent配置
        """
        self.config = config or AgentConfig()
        
        # 验证配置
        if not self.config.validate_config():
            raise ValueError("Agent配置无效")
        
        # 使用现有的LLM服务创建
        llm_service = LLMClientService()
        self.llm = llm_service.get_processing_llm(streaming=False)
        
        # 创建Wikipedia MCP服务器
        self.wikipedia_server = get_wikipedia_mcp_server()
        
        logger.info("实体去重Agent初始化完成")
    
    def deduplicate_entities(self, entities: List[Dict[str, Any]], entity_type: str) -> Dict[str, Any]:
        """
        执行实体去重分析
        
        Args:
            entities: 实体列表
            entity_type: 实体类型
            
        Returns:
            去重分析结果
        """
        # 初始化状态
        state = EntityAnalysisState(
            entities=entities,
            entity_type=entity_type,
            total_entities=len(entities),
            started_at=datetime.now()
        )
        
        try:
            logger.info(f"开始Agent去重分析：{entity_type} 类型，{len(entities)} 个实体")
            
            # 执行三阶段分析
            state = self._initial_analysis(state)
            state = self._search_verification(state)
            state = self._final_decision(state)
            
            # 计算处理时间
            state.processing_time = (datetime.now() - state.started_at).total_seconds()
            state.processing_step = "complete"
            
            # 返回标准格式结果
            return self._format_result(state)
            
        except Exception as e:
            error_msg = f"Agent去重分析失败: {str(e)}"
            logger.error(error_msg)
            state.add_error(error_msg)
            
            # 返回错误结果
            return self._format_error_result(state)
    
    def _initial_analysis(self, state: EntityAnalysisState) -> EntityAnalysisState:
        """
        第一阶段：初步相似性分析
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        try:
            state.processing_step = "initial"
            logger.info("开始初步相似性分析")
            
            # 构建初步分析Prompt
            prompt = self._build_initial_analysis_prompt(state.entities, state.entity_type)
            
            # 调用LLM进行分析
            response = self.llm.invoke(prompt)
            response_content = response.content
            
            # 解析响应
            analysis_result = self._parse_initial_analysis(response_content)
            state.initial_analysis = analysis_result
            
            # 提取实体对并强制更多进入验证
            if "entity_pairs" in analysis_result:
                for pair_data in analysis_result["entity_pairs"]:
                    original_confidence = pair_data["confidence"]
                    
                    # 强制更保守的验证策略：
                    # 只有极少数明显相同的才跳过验证
                    if original_confidence == "high":
                        # 进一步检查是否真的应该是high confidence
                        entity1_name = pair_data["entity1_name"]
                        entity2_name = pair_data["entity2_name"]
                        
                        # 只有这些情况才保持high confidence：
                        # 1. 完全相同的名称
                        # 2. 明显的缩写关系（如 IBM vs International Business Machines）
                        is_truly_high_confidence = (
                            entity1_name.lower() == entity2_name.lower() or
                            (len(entity1_name) <= 5 and entity1_name.upper() in entity2_name.upper()) or
                            (len(entity2_name) <= 5 and entity2_name.upper() in entity1_name.upper())
                        )
                        
                        if not is_truly_high_confidence:
                            # 降级到medium，强制进入Wikipedia验证
                            logger.info(f"降级置信度: {entity1_name} vs {entity2_name} 从 high -> medium")
                            original_confidence = "medium"
                    
                    entity_pair = EntityPair(
                        entity1_index=pair_data["entity1_index"],
                        entity2_index=pair_data["entity2_index"],
                        entity1_name=pair_data["entity1_name"],
                        entity2_name=pair_data["entity2_name"],
                        confidence=original_confidence,
                        similarity_score=pair_data.get("similarity_score", 0.0),
                        reason=pair_data.get("reason", ""),
                        needs_verification=original_confidence in ["medium", "low"]  # 使用调整后的置信度
                    )
                    state.entity_pairs.append(entity_pair)
            
            state.pairs_analyzed = len(state.entity_pairs)
            
            logger.info(f"初步分析完成：发现 {len(state.entity_pairs)} 个实体对")
            return state
            
        except Exception as e:
            error_msg = f"初步分析失败: {str(e)}"
            logger.error(error_msg)
            state.add_error(error_msg)
            return state
    
    def _search_verification(self, state: EntityAnalysisState) -> EntityAnalysisState:
        """
        第二阶段：Wikipedia搜索验证
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        try:
            state.processing_step = "search"
            logger.info("开始Wikipedia搜索验证")
            
            # 找出需要验证的实体对
            verification_pairs = [pair for pair in state.entity_pairs if pair.needs_verification]
            
            if not verification_pairs:
                logger.info("无需进行Wikipedia搜索验证")
                return state
            
            # 收集需要搜索的实体
            entities_to_search = set()
            for pair in verification_pairs:
                entities_to_search.add(pair.entity1_index)
                entities_to_search.add(pair.entity2_index)
            
            # 搜索实体信息
            search_results = {}
            for entity_index in entities_to_search:
                entity = state.get_entity_by_index(entity_index)
                if entity:
                    try:
                        result = self._search_entity_info(entity, state.entity_type)
                        search_results[entity_index] = result
                        state.searches_performed += 1
                    except Exception as e:
                        logger.warning(f"搜索实体 {entity_index} 失败: {str(e)}")
                        state.add_warning(f"搜索实体 {entity_index} 失败: {str(e)}")
            
            state.search_results = search_results
            
            logger.info(f"Wikipedia搜索完成：搜索了 {len(search_results)} 个实体")
            return state
            
        except Exception as e:
            error_msg = f"搜索验证失败: {str(e)}"
            logger.error(error_msg)
            state.add_error(error_msg)
            return state
    
    def _final_decision(self, state: EntityAnalysisState) -> EntityAnalysisState:
        """
        第三阶段：基于搜索结果的最终决策
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        try:
            state.processing_step = "decision"
            logger.info("开始最终决策分析")
            
            # 构建最终决策Prompt
            prompt = self._build_final_decision_prompt(state)
            
            # 调用LLM进行最终决策
            response = self.llm.invoke(prompt)
            response_content = response.content
            
            # 解析最终决策
            decision_result = self._parse_final_decision(response_content)
            state.final_decision = decision_result
            
            # 提取合并决策
            if "merge_groups" in decision_result:
                for group_data in decision_result["merge_groups"]:
                    merge_decision = MergeDecision(
                        primary_entity_index=group_data["primary_entity_index"],
                        duplicate_indices=group_data["duplicate_indices"],
                        merged_name=group_data["merged_name"],
                        merged_description=group_data["merged_description"],
                        confidence=group_data["confidence"],
                        reason=group_data["reason"],
                        wikipedia_evidence=group_data.get("wikipedia_evidence", "")
                    )
                    state.merge_groups.append(merge_decision)
            
            # 提取独立实体
            if "independent_entities" in decision_result:
                state.independent_entities = decision_result["independent_entities"]
            
            # 提取不确定案例
            if "uncertain_cases" in decision_result:
                state.uncertain_cases = decision_result["uncertain_cases"]
            
            logger.info(f"最终决策完成：{len(state.merge_groups)} 个合并组，{len(state.independent_entities)} 个独立实体")
            return state
            
        except Exception as e:
            error_msg = f"最终决策失败: {str(e)}"
            logger.error(error_msg)
            state.add_error(error_msg)
            return state
    
    def _search_entity_info(self, entity: Dict[str, Any], entity_type: str) -> SearchResult:
        """
        搜索单个实体的Wikipedia信息
        
        Args:
            entity: 实体数据
            entity_type: 实体类型
            
        Returns:
            搜索结果
        """
        try:
            # 调用Wikipedia搜索
            search_result = self.wikipedia_server.search_entity(
                entity_name=entity["name"],
                entity_type=entity_type
            )
            
            # 转换为SearchResult模型
            result = SearchResult(
                entity_name=entity["name"],
                found=search_result.get("found", False),
                title=search_result.get("title"),
                summary=search_result.get("summary"),
                url=search_result.get("url"),
                categories=search_result.get("categories", []),
                entity_type=search_result.get("entity_type"),
                type_relevance=search_result.get("type_relevance", 0.0),
                disambiguation=search_result.get("disambiguation", False),
                options=search_result.get("options", []),
                error=search_result.get("error")
            )
            
            return result
            
        except Exception as e:
            logger.error(f"搜索实体信息失败: {entity['name']}, 错误: {str(e)}")
            return SearchResult(
                entity_name=entity["name"],
                found=False,
                error=str(e)
            )
    
    def _build_initial_analysis_prompt(self, entities: List[Dict[str, Any]], entity_type: str) -> str:
        """构建初步分析Prompt - 极度保守的英文版本"""
        
        # 实体类型映射
        type_mapping = {
            "组织": "Organization", "人物": "Person", "地点": "Location", 
            "产品": "Product", "技术": "Technology", "时间": "Time", "事件": "Event"
        }
        english_type = type_mapping.get(entity_type, entity_type)
        
        prompt = f"""You are an EXTREMELY CONSERVATIVE {english_type} entity deduplication expert.

CRITICAL PRINCIPLE: Only suggest merging if you are 100% certain they refer to the EXACT SAME real-world object.

⛔ ABSOLUTELY NEVER MERGE:
- Different companies (Apple ≠ Google ≠ Microsoft ≠ Amazon ≠ Stanford University)
- Different people (Steve Jobs ≠ Tim Cook ≠ Sundar Pichai ≠ Satya Nadella)
- Competitors in same industry
- Different organization types (University ≠ Corporation ≠ Government)
- Similar but distinct entities
- Entities from different contexts without clear connection

✅ ONLY CONSIDER MERGING:
- Exact same entity with different language names (Apple Inc ↔ 苹果公司)
- Official name vs common abbreviation of SAME entity (International Business Machines ↔ IBM)
- Clear aliases of identical entity with Wikipedia confirmation

CONFIDENCE LEVELS:
- high: 100% certain same entity (e.g., "Apple Inc" vs "Apple Incorporated") - USE VERY RARELY
- medium: Possible same entity, needs Wikipedia verification (e.g., Chinese vs English names)
- low: Uncertain, needs deep research and verification

TARGET: Maximum 10% of pairs should be 'high' confidence. Be extremely conservative.

Entity List:
"""
        
        for i, entity in enumerate(entities):
            prompt += f"{i+1}. **{entity['name']}**\n"
            prompt += f"   - Description: {entity.get('description', 'No description')}\n"
            prompt += f"   - Source: {entity.get('source_text', 'No source')[:100]}...\n"
            prompt += f"   - Properties: {entity.get('properties', {})}\n\n"
        
        prompt += """
Return JSON format analysis results:
```json
{
  "analysis_summary": "Conservative analysis summary",
  "entity_pairs": [
    {
      "entity1_index": 0,
      "entity2_index": 1,
      "entity1_name": "Entity 1 name",
      "entity2_name": "Entity 2 name", 
      "confidence": "medium",
      "similarity_score": 0.7,
      "reason": "Reason for potential merge"
    }
  ]
}
```

IMPORTANT: 
- Only include pairs with genuine merge possibility
- Default to 'medium' or 'low' confidence
- When in doubt, DON'T include the pair
- Be extremely conservative - better to miss a merge than create a wrong one"""
        
        return prompt
    
    def _build_final_decision_prompt(self, state: EntityAnalysisState) -> str:
        """构建最终决策Prompt - 强化验证的英文版本"""
        
        # 实体类型映射
        type_mapping = {
            "组织": "Organization", "人物": "Person", "地点": "Location", 
            "产品": "Product", "技术": "Technology", "时间": "Time", "事件": "Event"
        }
        english_type = type_mapping.get(state.entity_type, state.entity_type)
        
        prompt = f"""Based on initial analysis and Wikipedia verification, make FINAL {english_type} entity merge decisions.

🚨 ULTRA-CONSERVATIVE MERGE POLICY 🚨

Initial Analysis Results:
{json.dumps(state.initial_analysis, ensure_ascii=False, indent=2)}

Wikipedia Verification Results:
"""
        
        for entity_index, search_result in state.search_results.items():
            prompt += f"\nEntity {entity_index} ({search_result.entity_name}) Wikipedia Info:\n"
            if search_result.found:
                prompt += f"- Title: {search_result.title}\n"
                prompt += f"- Summary: {search_result.summary[:200]}...\n"
                prompt += f"- URL: {search_result.url}\n"
                prompt += f"- Type Relevance: {search_result.type_relevance}\n"
            else:
                prompt += f"- No Wikipedia entry found\n"
                if search_result.error:
                    prompt += f"- Error: {search_result.error}\n"
        
        prompt += f"""
🔒 STRICT MERGE CONDITIONS - ALL MUST BE TRUE:
1. Wikipedia EXPLICITLY confirms they are the SAME entity
2. One redirects to the other OR explicitly states they are aliases
3. NO contradictory information found
4. Confidence ≥ 0.95 (95% certainty)
5. Common sense verification passes

❌ IMMEDIATELY REJECT IF:
- Different Wikipedia pages exist for both entities
- No Wikipedia confirmation found
- Any conflicting information
- Different organization types
- Competitors/rivals
- Different people with similar roles
- ANY doubt whatsoever

🔍 PERFORM CONTRADICTION CHECK:
Before suggesting any merge, actively look for reasons NOT to merge:
- Are they competitors?
- Do they have different roles/functions?
- Are they from different time periods?
- Do they belong to different categories?

⚖️ FINAL DECISION RULE:
When in doubt, KEEP SEPARATE. 
Better to have duplicates than wrong merges.

Return JSON format final decision:
```json
{{
  "decision_summary": "Ultra-conservative merge analysis with contradiction checks",
  "merge_groups": [
    {{
      "primary_entity_index": 0,
      "duplicate_indices": [1],
      "merged_name": "Verified merged name",
      "merged_description": "Verified merged description", 
      "confidence": 0.95,
      "reason": "Wikipedia explicitly confirms same entity",
      "wikipedia_evidence": "Specific Wikipedia evidence",
      "contradiction_check": "Verified no contradictions exist"
    }}
  ],
  "independent_entities": [2, 3, 4, 5],
  "uncertain_cases": [
    {{
      "entities": [6, 7], 
      "reason": "Insufficient evidence for safe merging"
    }}
  ]
}}
```

🎯 EXPECTED RESULT: Most entities should remain independent unless there is overwhelming evidence they are identical."""
        
        return prompt
    
    def _parse_initial_analysis(self, response_content: str) -> Dict[str, Any]:
        """解析初步分析响应"""
        try:
            # 提取JSON部分
            json_match = self._extract_json_from_response(response_content)
            if json_match:
                return json.loads(json_match)
            else:
                raise ValueError("无法找到有效的JSON响应")
                
        except Exception as e:
            logger.error(f"解析初步分析响应失败: {str(e)}")
            return {"analysis_summary": "解析失败", "entity_pairs": []}
    
    def _parse_final_decision(self, response_content: str) -> Dict[str, Any]:
        """解析最终决策响应"""
        try:
            # 提取JSON部分
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
                "independent_entities": list(range(len(self.entities))),
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
    
    def _format_result(self, state: EntityAnalysisState) -> Dict[str, Any]:
        """格式化最终结果"""
        return {
            "analysis_summary": state.final_decision.get("decision_summary", "Agent分析完成") if state.final_decision else "Agent分析完成",
            "merge_groups": [
                {
                    "primary_entity": str(group.primary_entity_index + 1),
                    "duplicates": [str(idx + 1) for idx in group.duplicate_indices],
                    "merged_name": group.merged_name,
                    "merged_description": group.merged_description,
                    "confidence": group.confidence,
                    "reason": group.reason
                }
                for group in state.merge_groups
            ],
            "independent_entities": [str(idx + 1) for idx in state.independent_entities],
            "uncertain_cases": state.uncertain_cases,
            "statistics": state.get_processing_summary(),
            "errors": state.errors,
            "warnings": state.warnings
        }
    
    def _format_error_result(self, state: EntityAnalysisState) -> Dict[str, Any]:
        """格式化错误结果"""
        return {
            "analysis_summary": "Agent分析失败",
            "merge_groups": [],
            "independent_entities": [str(i + 1) for i in range(len(state.entities))],
            "uncertain_cases": [],
            "statistics": state.get_processing_summary(),
            "errors": state.errors,
            "warnings": state.warnings
        }


# 全局实例
_agent_instance = None

def get_entity_deduplication_agent(config: Optional[AgentConfig] = None) -> EntityDeduplicationAgent:
    """获取实体去重Agent实例（单例模式）"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = EntityDeduplicationAgent(config)
    return _agent_instance