# -*- coding: utf-8 -*-
"""
LLM语义去重器服务
使用LLM进行实体语义去重分析，集成Agent模式
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

from app.prompts.entity_deduplication_prompts import EntityDeduplicationPrompts
from app.services.llm_client_service import LLMClientService
from app.services.entity_deduplication_agent import get_entity_deduplication_agent

logger = logging.getLogger(__name__)


class LLMSemanticDeduplicator:
    """LLM语义去重器 - 集成Agent模式"""
    
    def __init__(self):
        """初始化LLM语义去重器"""
        llm_service = LLMClientService()
        self.llm = llm_service.get_processing_llm(streaming=False)
        self.prompts = EntityDeduplicationPrompts()
        
        # 添加Agent支持
        self.agent = get_entity_deduplication_agent()
        self.enable_agent_mode = True  # 开关控制
        
        logger.info("LLM语义去重器初始化完成（支持Agent模式）")
    
    def deduplicate_entities(
        self,
        entities: List[Dict[str, Any]],
        entity_type: str
    ) -> Dict[str, Any]:
        """
        使用LLM对实体进行语义去重
        
        Args:
            entities: 实体列表
            entity_type: 实体类型
            
        Returns:
            LLM分析结果
        """
        
        logger.info("开始LLM语义去重分析，实体类型: " + entity_type + "，数量: " + str(len(entities)))
        
        # 根据配置选择处理模式
        if self.enable_agent_mode and len(entities) >= 2:
            # 使用Agent模式（同步调用）
            try:
                logger.info(f"使用Agent模式进行去重分析：{entity_type} 类型，{len(entities)} 个实体")
                
                # 直接调用Agent进行分析
                result = self.agent.deduplicate_entities(entities, entity_type)
                
                logger.info("Agent去重分析完成")
                return result
                
            except Exception as e:
                logger.error(f"Agent去重分析失败: {str(e)}")
                logger.info("回退到传统模式")
                return self._legacy_deduplicate(entities, entity_type)
        else:
            # 使用原有模式（向后兼容）
            return self._legacy_deduplicate(entities, entity_type)
    
    def _legacy_deduplicate(self, entities: List[Dict[str, Any]], entity_type: str) -> Dict[str, Any]:
        """
        使用传统模式进行去重（原有逻辑）
        
        Args:
            entities: 实体列表
            entity_type: 实体类型
            
        Returns:
            LLM分析结果
        """
        try:
            # 生成去重提示词
            prompt = self.prompts.generate_deduplication_prompt(entities, entity_type)
            
            # 调用LLM分析
            llm_response = self._call_llm_for_deduplication(prompt)
            
            # 解析LLM响应
            analysis_result = self._parse_llm_response(llm_response, entities)
            
            # 验证分析结果
            validated_result = self._validate_analysis_result(analysis_result, entities)
            
            logger.info("LLM语义去重完成，合并组数: " + str(len(validated_result.get('merge_groups', []))))
            
            return validated_result
            
        except Exception as e:
            logger.error("LLM语义去重失败: " + str(e))
            # 返回保守结果：不合并任何实体
            return self._create_no_merge_result(entities)
    
    def _call_llm_for_deduplication(self, prompt: str) -> str:
        """
        调用LLM进行去重分析
        
        Args:
            prompt: 分析提示词
            
        Returns:
            LLM响应文本
        """
        try:
            logger.debug("发送LLM去重分析请求")
            
            # 使用同步的LLM接口
            response = self.llm.invoke(prompt)
            
            if not response or not response.content:
                raise ValueError("LLM响应为空")
            
            response_content = response.content
            logger.debug("LLM响应长度: " + str(len(response_content)) + " 字符")
            
            return response_content
            
        except Exception as e:
            logger.error("LLM调用失败: " + str(e))
            raise
    
    def _parse_llm_response(self, llm_response: str, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        解析LLM响应为结构化数据
        
        Args:
            llm_response: LLM原始响应
            entities: 原始实体列表
            
        Returns:
            解析后的分析结果
        """
        try:
            # 提取JSON部分
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', llm_response, re.DOTALL)
            if not json_match:
                # 尝试直接查找JSON对象
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', llm_response, re.DOTALL)
            
            if not json_match:
                raise ValueError("无法在LLM响应中找到有效的JSON格式")
            
            json_str = json_match.group(1) if json_match.groups() else json_match.group(0)
            
            # 解析JSON
            parsed_result = json.loads(json_str)
            
            logger.debug("LLM响应JSON解析成功")
            return parsed_result
            
        except json.JSONDecodeError as e:
            logger.error("JSON解析失败: " + str(e))
            logger.debug("原始响应: " + llm_response[:500] + "...")
            # 尝试修复常见的JSON错误
            return self._attempt_json_repair(llm_response, entities)
        
        except Exception as e:
            logger.error("LLM响应解析失败: " + str(e))
            return self._create_no_merge_result(entities)
    
    def _attempt_json_repair(self, llm_response: str, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        尝试修复LLM响应中的JSON格式错误
        
        Args:
            llm_response: 原始LLM响应
            entities: 原始实体列表
            
        Returns:
            修复后的分析结果或保守结果
        """
        try:
            logger.info("尝试修复JSON格式错误")
            
            # 常见修复策略
            repaired_response = llm_response
            
            # 移除markdown标记
            repaired_response = re.sub(r'```json\s*', '', repaired_response)
            repaired_response = re.sub(r'\s*```', '', repaired_response)
            
            # 修复常见的尾随逗号问题
            repaired_response = re.sub(r',\s*}', '}', repaired_response)
            repaired_response = re.sub(r',\s*]', ']', repaired_response)
            
            # 尝试解析修复后的JSON
            parsed_result = json.loads(repaired_response)
            
            logger.info("JSON修复成功")
            return parsed_result
            
        except Exception as e:
            logger.warning(f"JSON修复失败: {str(e)}")
            # 返回保守结果
            return self._create_no_merge_result(entities)
    
    def _validate_analysis_result(
        self,
        analysis_result: Dict[str, Any],
        entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        验证LLM分析结果的有效性
        
        Args:
            analysis_result: LLM分析结果
            entities: 原始实体列表
            
        Returns:
            验证后的分析结果
        """
        try:
            entity_ids = set(str(i+1) for i in range(len(entities)))
            
            # 验证必需字段
            if not isinstance(analysis_result, dict):
                raise ValueError("分析结果不是字典格式")
            
            merge_groups = analysis_result.get('merge_groups', [])
            independent_entities = analysis_result.get('independent_entities', [])
            
            # 验证merge_groups格式
            validated_merge_groups = []
            used_entity_ids = set()
            
            for group in merge_groups:
                if not isinstance(group, dict):
                    continue
                
                primary_entity = str(group.get('primary_entity', ''))
                duplicates = [str(d) for d in group.get('duplicates', [])]
                confidence = float(group.get('confidence', 0.0))
                
                # 验证实体ID有效性
                all_group_ids = [primary_entity] + duplicates
                if not all(entity_id in entity_ids for entity_id in all_group_ids):
                    logger.warning(f"合并组包含无效实体ID: {all_group_ids}")
                    continue
                
                # 验证实体ID未重复使用
                if any(entity_id in used_entity_ids for entity_id in all_group_ids):
                    logger.warning(f"合并组包含重复使用的实体ID: {all_group_ids}")
                    continue
                
                # 验证置信度合理性
                if confidence < 0.5:
                    logger.warning(f"合并置信度过低({confidence})，跳过此组")
                    continue
                
                used_entity_ids.update(all_group_ids)
                validated_merge_groups.append({
                    'primary_entity': primary_entity,
                    'duplicates': duplicates,
                    'merged_name': group.get('merged_name', entities[int(primary_entity)-1].get('name', '')),
                    'merged_description': group.get('merged_description', ''),
                    'confidence': confidence,
                    'reason': group.get('reason', '')
                })
            
            # 处理独立实体
            validated_independent = [
                str(entity_id) for entity_id in independent_entities
                if str(entity_id) in entity_ids and str(entity_id) not in used_entity_ids
            ]
            
            # 添加未被处理的实体到独立实体列表
            unprocessed_entities = entity_ids - used_entity_ids - set(validated_independent)
            validated_independent.extend(list(unprocessed_entities))
            
            result = {
                'analysis_summary': analysis_result.get('analysis_summary', '语义去重分析完成'),
                'merge_groups': validated_merge_groups,
                'independent_entities': validated_independent,
                'uncertain_cases': analysis_result.get('uncertain_cases', [])
            }
            
            logger.info(f"分析结果验证完成，有效合并组: {len(validated_merge_groups)}，独立实体: {len(validated_independent)}")
            
            return result
            
        except Exception as e:
            logger.error(f"分析结果验证失败: {str(e)}")
            return self._create_no_merge_result(entities)
    
    def _create_no_merge_result(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        创建保守的不合并结果
        
        Args:
            entities: 实体列表
            
        Returns:
            保守分析结果
        """
        return {
            'analysis_summary': '保守策略：不合并任何实体',
            'merge_groups': [],
            'independent_entities': [str(i+1) for i in range(len(entities))],
            'uncertain_cases': []
        }
    
    def extract_merge_operations(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从分析结果中提取合并操作指令
        
        Args:
            analysis_result: LLM分析结果
            
        Returns:
            合并操作列表
        """
        merge_operations = []
        
        for group in analysis_result.get('merge_groups', []):
            try:
                primary_entity_idx = int(group['primary_entity']) - 1  # 转换为0索引
                duplicate_indices = [int(d) - 1 for d in group['duplicates']]  # 转换为0索引
                
                merge_operations.append({
                    'primary_entity_index': primary_entity_idx,
                    'duplicate_indices': duplicate_indices,
                    'merged_name': group.get('merged_name', ''),
                    'merged_description': group.get('merged_description', ''),
                    'confidence': group.get('confidence', 0.0),
                    'reason': group.get('reason', '')
                })
                
            except (ValueError, KeyError) as e:
                logger.warning(f"无效的合并组格式，跳过: {str(e)}")
                continue
        
        logger.info(f"提取了 {len(merge_operations)} 个合并操作")
        return merge_operations
    
    async def batch_deduplicate_by_type(
        self,
        entities_by_type: Dict[str, List[Dict[str, Any]]],
        max_batch_size: int = 20
    ) -> Dict[str, Dict[str, Any]]:
        """
        按类型批量进行语义去重
        
        Args:
            entities_by_type: 按类型分组的实体字典
            max_batch_size: 最大批次大小
            
        Returns:
            每种类型的分析结果
        """
        results = {}
        
        for entity_type, entities in entities_by_type.items():
            if len(entities) <= 1:
                logger.info(f"{entity_type} 类型实体数量不足，跳过去重")
                results[entity_type] = self._create_no_merge_result(entities)
                continue
            
            try:
                # 如果实体数量超过批次大小，进行分批处理
                if len(entities) > max_batch_size:
                    logger.info(f"{entity_type} 类型实体数量({len(entities)})超过批次大小，进行分批处理")
                    batch_results = await self._process_large_batch(entities, entity_type, max_batch_size)
                    results[entity_type] = batch_results
                else:
                    # 直接处理
                    analysis_result = await self.deduplicate_entities(entities, entity_type)
                    results[entity_type] = analysis_result
                
            except Exception as e:
                logger.error(f"{entity_type} 类型实体去重失败: {str(e)}")
                results[entity_type] = self._create_no_merge_result(entities)
        
        return results
    
    async def _process_large_batch(
        self,
        entities: List[Dict[str, Any]],
        entity_type: str,
        batch_size: int
    ) -> Dict[str, Any]:
        """
        处理大批次实体（分批处理策略）
        
        Args:
            entities: 实体列表
            entity_type: 实体类型
            batch_size: 批次大小
            
        Returns:
            合并后的分析结果
        """
        logger.info(f"开始分批处理 {entity_type} 类型的 {len(entities)} 个实体，批次大小: {batch_size}")
        
        # 简化策略：取前batch_size个实体进行分析
        # TODO: 实现更智能的分批策略（如基于相似性预聚类）
        sampled_entities = entities[:batch_size]
        
        logger.info(f"采样 {len(sampled_entities)} 个实体进行分析")
        
        return await self.deduplicate_entities(sampled_entities, entity_type)


# 全局实例
_llm_deduplicator_instance = None

def get_llm_semantic_deduplicator() -> LLMSemanticDeduplicator:
    """获取LLM语义去重器实例（单例模式）"""
    global _llm_deduplicator_instance
    if _llm_deduplicator_instance is None:
        _llm_deduplicator_instance = LLMSemanticDeduplicator()
    return _llm_deduplicator_instance