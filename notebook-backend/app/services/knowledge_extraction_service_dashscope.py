#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识抽取服务 - DashScope版本
解决OpenAI网络连接问题，使用DashScope进行知识抽取
"""
import logging
import json
import re
import asyncio
import hashlib
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
import dashscope
from app.core.config import settings
from app.models.entity import Entity, Relationship, KnowledgeExtractionResult

logger = logging.getLogger(__name__)

class KnowledgeExtractionServiceDashScope:
    """知识抽取服务 - DashScope版本
    
    使用DashScope千问模型从文档分块中同时抽取实体和关系
    解决OpenAI网络连接问题
    """
    
    def __init__(self):
        """初始化知识抽取服务"""
        # 设置DashScope API
        dashscope.api_key = settings.DASHSCOPE_API_KEY
        
        self.entity_types = self._load_entity_types()
        self.relationship_types = self._load_relationship_types()
        self.model = "qwen-turbo"  # 使用千问turbo模型
        
        logger.info("知识抽取服务已初始化 - 使用DashScope千问模型")
    
    def _load_entity_types(self) -> List[str]:
        """加载实体类型配置"""
        return [
            "人物", "组织", "地点", "事件", "概念", 
            "技术", "产品", "时间", "数字", "法律条文",
            "政策", "项目", "系统", "方法", "理论"
        ]
    
    def _load_relationship_types(self) -> List[str]:
        """加载关系类型配置"""
        return [
            "属于", "包含", "位于", "工作于", "创立", "管理",
            "合作", "提及", "描述", "引用", "导致", "影响",
            "使用", "依赖", "实现", "相关", "连接", "关联"
        ]
    
    async def extract_knowledge_from_chunks(self, chunks: List[Dict[str, Any]]) -> Tuple[List[Entity], List[Relationship]]:
        """从文档分块中抽取知识（实体和关系）"""
        logger.info(f"开始从 {len(chunks)} 个分块中抽取知识（使用DashScope）")
        
        all_entities = []
        all_relationships = []
        
        try:
            # 处理每个分块
            for i, chunk in enumerate(chunks):
                chunk_content = chunk.get('content', '')
                if not chunk_content.strip():
                    continue
                
                logger.info(f"处理分块 {i+1}/{len(chunks)}（DashScope）")
                
                # 从单个分块抽取知识
                result = await self._extract_knowledge_from_text(
                    text=chunk_content,
                    chunk_id=chunk.get('id', f'chunk_{i}'),
                    chunk_index=i,
                    chunk_metadata=chunk
                )
                
                if result.success:
                    all_entities.extend(result.entities)
                    all_relationships.extend(result.relationships)
                else:
                    logger.warning(f"分块 {i} 知识抽取失败: {result.error_message}")
                
                # 避免过于频繁的API调用
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.5)  # DashScope需要稍长间隔
            
            # 使用智能实体统一
            logger.info("使用智能实体统一算法进行实体标准化")
            unified_entities = await self._unify_entities_intelligent(all_entities)
            
            # 为统一后的实体创建chunk映射
            entity_chunk_mapping = self._create_chunk_mapping_for_unified_entities(unified_entities)
            
            # 过滤关系
            filtered_relationships = self._filter_relationships(all_relationships, unified_entities)
            
            # 将chunk映射信息添加到实体属性中
            for entity in unified_entities:
                entity_key = (self._normalize_entity_name(entity.name), entity.type)
                chunk_ids = entity_chunk_mapping.get(entity_key, [])
                entity.properties['chunk_ids'] = chunk_ids
                entity.properties['appears_in_chunks_count'] = len(chunk_ids)
            
            logger.info(f"知识抽取完成：实体 {len(all_entities)} -> {len(unified_entities)}，关系 {len(all_relationships)} -> {len(filtered_relationships)}")
            
            return unified_entities, filtered_relationships
            
        except Exception as e:
            logger.error(f"知识抽取失败: {str(e)}")
            raise
    
    async def _extract_knowledge_from_text(self, text: str, chunk_id: str, 
                                         chunk_index: int, chunk_metadata: Dict[str, Any]) -> KnowledgeExtractionResult:
        """从单个文本中抽取知识"""
        try:
            # 构建提示词
            prompt = self._build_knowledge_extraction_prompt(text)
            
            # 调用DashScope API
            response = dashscope.Generation.call(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.0,
                max_tokens=2000,
                result_format='message'
            )
            
            if response.status_code != 200:
                raise Exception(f"DashScope API调用失败: {response.status_code}, {response.message}")
            
            # 获取响应内容
            response_content = response.output.choices[0].message.content
            
            # 解析响应
            entities, relationships = self._parse_knowledge_response(
                response_content, text, chunk_id, chunk_index, chunk_metadata
            )
            
            logger.info(f"从分块 {chunk_index} 抽取到 {len(entities)} 个实体，{len(relationships)} 个关系")
            
            return KnowledgeExtractionResult(
                entities=entities,
                relationships=relationships,
                chunk_id=chunk_id,
                chunk_index=chunk_index,
                success=True
            )
            
        except Exception as e:
            logger.error(f"从文本抽取知识失败: {str(e)}")
            return KnowledgeExtractionResult(
                entities=[],
                relationships=[],
                chunk_id=chunk_id,
                chunk_index=chunk_index,
                success=False,
                error_message=str(e)
            )
    
    def _build_knowledge_extraction_prompt(self, text: str) -> str:
        """构建知识抽取提示词（同时抽取实体和关系）"""
        entity_types_str = "、".join(self.entity_types)
        relationship_types_str = "、".join(self.relationship_types)
        
        prompt = f"""
请从以下文本中抽取实体和关系信息。

支持的实体类型：{entity_types_str}
支持的关系类型：{relationship_types_str}

文本内容：
{text}

请按照以下JSON格式返回结果，同时包含实体和关系信息：

```json
{{
    "entities": [
        {{
            "name": "实体名称",
            "type": "实体类型",
            "description": "实体描述",
            "properties": {{}},
            "confidence": 0.95,
            "start_pos": 0,
            "end_pos": 10
        }}
    ],
    "relationships": [
        {{
            "source_entity": "源实体名称",
            "target_entity": "目标实体名称",
            "relationship_type": "关系类型",
            "description": "关系描述",
            "properties": {{}},
            "confidence": 0.85,
            "context": "支持关系的文本片段"
        }}
    ]
}}
```

注意事项：
1. 实体抽取：
   - 只抽取重要的、有意义的实体
   - 确保实体名称准确完整
   - 实体类型必须从提供的类型中选择
   - 置信度要根据上下文合理评估
   - 位置信息要准确
   - 避免重复抽取相同实体

2. 关系抽取：
   - 关系类型必须从提供的类型中选择
   - 源实体和目标实体必须在实体列表中存在
   - 提供支持关系的具体文本片段
   - 置信度要合理评估

请确保返回的JSON格式正确，所有字段都完整填写。
"""
        return prompt
    
    def _parse_knowledge_response(self, response: str, source_text: str, 
                                chunk_id: str, chunk_index: int, chunk_metadata: Dict[str, Any]) -> Tuple[List[Entity], List[Relationship]]:
        """解析知识抽取响应"""
        entities = []
        relationships = []
        
        try:
            # 提取JSON部分
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response.strip()
            
            # 解析JSON
            data = json.loads(json_str)
            
            # 解析实体
            if 'entities' in data and isinstance(data['entities'], list):
                for i, entity_data in enumerate(data['entities']):
                    entity = self._parse_entity_data(
                        entity_data, source_text, chunk_id, i, chunk_metadata
                    )
                    if entity:
                        entities.append(entity)
            
            # 解析关系
            if 'relationships' in data and isinstance(data['relationships'], list):
                # 创建实体名称映射
                entity_map = {entity.name: entity for entity in entities}
                
                for i, rel_data in enumerate(data['relationships']):
                    relationship = self._parse_relationship_data(
                        rel_data, entity_map, source_text, chunk_id, chunk_index, i, chunk_metadata
                    )
                    if relationship:
                        relationships.append(relationship)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
        except Exception as e:
            logger.error(f"解析响应失败: {str(e)}")
        
        return entities, relationships
    
    def _parse_entity_data(self, entity_data: Dict[str, Any], source_text: str, 
                          chunk_id: str, entity_index: int, chunk_metadata: Dict[str, Any]) -> Optional[Entity]:
        """解析实体数据"""
        try:
            # 验证必需字段
            if not entity_data.get('name') or not entity_data.get('type'):
                return None
            
            # 验证实体类型
            entity_type = entity_data.get('type')
            if entity_type not in self.entity_types:
                entity_type = self._match_entity_type(entity_type)
            
            # 创建实体
            entity = Entity(
                id=f"{chunk_id}_entity_{entity_index}",
                name=entity_data.get('name', '').strip(),
                type=entity_type,
                description=entity_data.get('description', ''),
                properties=entity_data.get('properties', {}),
                confidence=float(entity_data.get('confidence', 0.8)),
                source_text=source_text[:200] + '...' if len(source_text) > 200 else source_text,
                start_pos=int(entity_data.get('start_pos', 0)),
                end_pos=int(entity_data.get('end_pos', 0)),
                aliases=entity_data.get('aliases', []),
                embedding=None,
                quality_score=float(entity_data.get('quality_score', 0.8))
            )
            
            # 验证实体有效性
            if self._validate_entity(entity, source_text):
                return entity
            else:
                return None
                
        except Exception as e:
            logger.warning(f"解析实体数据失败: {str(e)}")
            return None
    
    def _parse_relationship_data(self, rel_data: Dict[str, Any], entity_map: Dict[str, Entity], 
                               source_text: str, chunk_id: str, chunk_index: int, 
                               rel_index: int, chunk_metadata: Dict[str, Any]) -> Optional[Relationship]:
        """解析关系数据"""
        try:
            source_name = rel_data.get('source_entity', '')
            target_name = rel_data.get('target_entity', '')
            rel_type = rel_data.get('relationship_type', '')
            
            # 验证关系类型
            if rel_type not in self.relationship_types:
                rel_type = self._match_relationship_type(rel_type)
            
            # 创建关系
            relationship = Relationship(
                id=f"{chunk_id}_relationship_{rel_index}",
                source_entity_id=entity_map.get(source_name, Entity(id="", name="", type="")).id if source_name in entity_map else "",
                target_entity_id=entity_map.get(target_name, Entity(id="", name="", type="")).id if target_name in entity_map else "",
                source_entity_name=source_name,
                target_entity_name=target_name,
                relationship_type=rel_type,
                description=rel_data.get('description', ''),
                properties=rel_data.get('properties', {}),
                confidence=float(rel_data.get('confidence', 0.8)),
                source_text=rel_data.get('context', source_text[:100]),
                context=rel_data.get('context', '')
            )
            
            # 验证关系有效性
            if self._validate_relationship(relationship, source_text):
                return relationship
            else:
                return None
                
        except Exception as e:
            logger.warning(f"解析关系数据失败: {str(e)}")
            return None
    
    def _match_entity_type(self, entity_type: str) -> str:
        """匹配实体类型"""
        entity_type_lower = entity_type.lower()
        
        # 映射规则
        type_mapping = {
            'person': '人物', 'people': '人物', '人': '人物',
            'organization': '组织', 'org': '组织', '机构': '组织', '公司': '组织',
            'location': '地点', 'place': '地点', '位置': '地点',
            'event': '事件', '活动': '事件',
            'concept': '概念', '观念': '概念',
            'technology': '技术', 'tech': '技术', '科技': '技术',
            'product': '产品', '商品': '产品',
            'time': '时间', 'date': '时间', '日期': '时间',
            'number': '数字', 'digit': '数字', '数量': '数字'
        }
        
        for key, value in type_mapping.items():
            if key in entity_type_lower:
                return value
        
        # 默认返回概念类型
        return '概念'
    
    def _match_relationship_type(self, rel_type: str) -> str:
        """匹配关系类型"""
        rel_type_lower = rel_type.lower()
        
        # 映射规则
        type_mapping = {
            'belong': '属于', 'belongs': '属于', '归属': '属于',
            'contain': '包含', 'contains': '包含', '包括': '包含',
            'locate': '位于', 'located': '位于', '坐落': '位于',
            'work': '工作于', 'works': '工作于', '就职': '工作于',
            'create': '创立', 'created': '创立', '建立': '创立',
            'manage': '管理', 'manages': '管理', '治理': '管理',
            'cooperate': '合作', 'collaborate': '合作', '协作': '合作',
            'mention': '提及', 'mentions': '提及', '涉及': '提及',
            'describe': '描述', 'describes': '描述', '叙述': '描述',
            'reference': '引用', 'references': '引用', '参考': '引用',
            'cause': '导致', 'causes': '导致', '引起': '导致',
            'influence': '影响', 'influences': '影响', '作用': '影响',
            'use': '使用', 'uses': '使用', '利用': '使用',
            'depend': '依赖', 'depends': '依赖', '依靠': '依赖',
            'implement': '实现', 'implements': '实现', '执行': '实现',
            'relate': '相关', 'relates': '相关', '关系': '相关',
            'connect': '连接', 'connects': '连接', '联接': '连接',
            'associate': '关联', 'associates': '关联', '联系': '关联'
        }
        
        for key, value in type_mapping.items():
            if key in rel_type_lower:
                return value
        
        # 默认返回关联类型
        return '关联'
    
    def _validate_entity(self, entity: Entity, source_text: str) -> bool:
        """验证实体有效性"""
        # 检查名称长度
        if len(entity.name) < 2 or len(entity.name) > 100:
            return False
        
        # 检查置信度
        if entity.confidence < 0.3:
            return False
        
        return True
    
    def _validate_relationship(self, relationship: Relationship, source_text: str) -> bool:
        """验证关系有效性"""
        # 检查置信度
        if relationship.confidence < 0.3:
            return False
        
        # 检查实体名称不能相同
        if relationship.source_entity_name == relationship.target_entity_name:
            return False
        
        return True
    
    def _normalize_entity_name(self, name: str) -> str:
        """标准化实体名称"""
        # 移除多余空格
        normalized = re.sub(r'\s+', ' ', name.strip())
        
        # 移除特殊字符
        normalized = re.sub(r'[""''《》【】（）()]', '', normalized)
        
        # 转换为小写进行比较
        return normalized.lower()
    
    async def _unify_entities_intelligent(self, entities: List[Entity]) -> List[Entity]:
        """使用智能实体统一算法进行实体标准化"""
        from app.services.entity_unification_service import get_entity_unification_service
        
        logger.info(f"开始智能实体统一，输入实体: {len(entities)}")
        
        # 获取统一服务实例
        unification_service = get_entity_unification_service()
        
        # 执行统一
        unification_result = await unification_service.unify_entities(entities)
        
        # 记录统一统计信息
        logger.info(f"智能实体统一完成:")
        logger.info(f"  - 输入实体: {unification_result.statistics['input_entity_count']}")
        logger.info(f"  - 输出实体: {unification_result.statistics['output_entity_count']}")
        logger.info(f"  - 合并操作: {unification_result.statistics['merge_operation_count']}")
        logger.info(f"  - 减少率: {unification_result.statistics['reduction_rate']:.2%}")
        logger.info(f"  - 处理时间: {unification_result.processing_time:.3f}秒")
        
        return unification_result.unified_entities
    
    def _create_chunk_mapping_for_unified_entities(self, unified_entities: List[Entity]) -> Dict[str, List[str]]:
        """为统一后的实体创建chunk映射"""
        entity_chunk_mapping = {}
        
        for entity in unified_entities:
            # 为统一后的实体创建键
            entity_key = (self._normalize_entity_name(entity.name), entity.type)
            
            # 从实体属性中提取chunk信息
            chunk_ids = []
            
            # 检查实体是否是合并的结果
            if hasattr(entity, 'merged_from') and entity.merged_from:
                # 如果是合并实体，从merged_from中提取chunk信息
                for original_entity_id in entity.merged_from:
                    chunk_id = self._extract_chunk_id_from_entity_id(original_entity_id)
                    if chunk_id and chunk_id not in chunk_ids:
                        chunk_ids.append(chunk_id)
            else:
                # 如果不是合并实体，从其ID中提取chunk信息
                chunk_id = self._extract_chunk_id_from_entity_id(entity.id)
                if chunk_id:
                    chunk_ids.append(chunk_id)
            
            entity_chunk_mapping[entity_key] = chunk_ids
        
        return entity_chunk_mapping
    
    def _extract_chunk_id_from_entity_id(self, entity_id: str) -> Optional[str]:
        """从实体ID中提取chunk_id"""
        try:
            if "_entity_" in entity_id:
                chunk_id = entity_id.split("_entity_")[0]
                if "chunk" in chunk_id:
                    return chunk_id
            return None
        except Exception as e:
            logger.warning(f"从实体ID {entity_id} 提取chunk_id失败: {str(e)}")
            return None
    
    def _filter_relationships(self, relationships: List[Relationship], 
                            entities: List[Entity]) -> List[Relationship]:
        """过滤和去重关系"""
        logger.info(f"开始过滤 {len(relationships)} 个关系")
        
        # 创建实体名称映射
        entity_names = {entity.name for entity in entities}
        
        # 过滤关系：确保关系的实体都存在
        valid_relationships = []
        for relationship in relationships:
            if (relationship.source_entity_name in entity_names and 
                relationship.target_entity_name in entity_names):
                valid_relationships.append(relationship)
        
        # 按关系键分组（源实体-目标实体-关系类型）
        relationship_groups = {}
        
        for relationship in valid_relationships:
            key = (
                relationship.source_entity_name,
                relationship.target_entity_name,
                relationship.relationship_type
            )
            
            if key not in relationship_groups:
                relationship_groups[key] = []
            relationship_groups[key].append(relationship)
        
        # 每组选择最佳关系
        filtered = []
        
        for key, group in relationship_groups.items():
            if len(group) == 1:
                filtered.append(group[0])
            else:
                # 选择置信度最高的关系
                best_relationship = max(group, key=lambda x: x.confidence)
                filtered.append(best_relationship)
        
        # 过滤低置信度关系
        high_confidence_relationships = [
            rel for rel in filtered if rel.confidence >= 0.5
        ]
        
        logger.info(f"关系过滤完成：{len(high_confidence_relationships)} 个高质量关系")
        return high_confidence_relationships 