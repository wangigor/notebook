import logging
import json
import re
import asyncio
import hashlib
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from langchain_core.messages import HumanMessage
from app.core.config import settings
from app.services.llm_client_service import LLMClientService

# 🆕 使用统一的Entity和Relationship模型
from app.models.entity import Entity, Relationship, KnowledgeExtractionResult

logger = logging.getLogger(__name__)

class KnowledgeExtractionService:
    """知识抽取服务
    
    使用大语言模型从文档分块中同时抽取实体和关系
    抽取后的实体直接入库，由后续全局统一任务进行去重处理
    """
    
    def __init__(self):
        """初始化知识抽取服务"""
        self.llm_service = LLMClientService()
        self.entity_types = self._load_entity_types()
        self.relationship_types = self._load_relationship_types()
        logger.info("知识抽取服务已初始化 - 实体直接入库模式")
    
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
        logger.info(f"开始从 {len(chunks)} 个分块中抽取知识")
        
        all_entities = []
        all_relationships = []
        
        try:
            # 处理每个分块
            for i, chunk in enumerate(chunks):
                chunk_content = chunk.get('content', '')
                if not chunk_content.strip():
                    continue
                
                logger.info(f"处理分块 {i+1}/{len(chunks)}")
                
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
                    await asyncio.sleep(0.1)
            
            # 🔄 移除文档内实体统一，实体直接准备入库
            logger.info("实体抽取完成，准备直接入库（由后续全局统一任务处理去重）")
            
            # 为原始实体创建chunk映射（不进行统一）
            entity_chunk_mapping = self._create_chunk_mapping_for_raw_entities(all_entities)
            
            # 过滤关系（基于原始实体）
            filtered_relationships = self._filter_relationships(all_relationships, all_entities)
            
            # 将chunk映射信息添加到实体属性中
            for entity in all_entities:
                entity_key = (self._normalize_entity_name(entity.name), entity.type)
                chunk_ids = entity_chunk_mapping.get(entity_key, [])
                entity.properties['chunk_ids'] = chunk_ids
                entity.properties['appears_in_chunks_count'] = len(chunk_ids)
            
            logger.info(f"知识抽取完成：实体 {len(all_entities)}，关系 {len(all_relationships)} -> {len(filtered_relationships)}")
            
            # 🆕 触发文档解析后的全局实体统一任务（使用LangGraph Agent）
            await self._trigger_post_extraction_unification(all_entities, chunks)
            
            return all_entities, filtered_relationships
            
        except Exception as e:
            logger.error(f"知识抽取失败: {str(e)}")
            raise
    
    async def _extract_knowledge_from_text(self, text: str, chunk_id: str, 
                                         chunk_index: int, chunk_metadata: Dict[str, Any]) -> KnowledgeExtractionResult:
        """从单个文本中抽取知识"""
        try:
            # 构建提示词
            prompt = self._build_knowledge_extraction_prompt(text)
            
            # 获取LLM实例
            llm = self.llm_service.get_processing_llm(streaming=False)
            
            # 调用LLM
            message = HumanMessage(content=prompt)
            response = await llm.ainvoke([message])
            
            # 获取响应内容
            response_content = response.content if hasattr(response, 'content') else str(response)
            
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
   - 只抽取文本中明确体现的关系
   - 确保源实体和目标实体都在抽取的实体列表中
   - 关系类型必须从提供的类型中选择
   - 置信度要根据文本证据强度评估
   - 上下文要准确反映关系的文本依据
   - 避免重复或冗余的关系
   - 注意关系的方向性

3. 整体要求：
   - 保持实体和关系的一致性
   - 优先抽取高置信度的信息
   - 确保JSON格式正确
   - 注意实体和关系的完整性
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
                json_str = response.strip()
            
            # 解析JSON
            data = json.loads(json_str)
            
            # 解析实体
            if 'entities' in data and isinstance(data['entities'], list):
                for i, entity_data in enumerate(data['entities']):
                    try:
                        entity = self._parse_entity_data(entity_data, source_text, chunk_id, i, chunk_metadata)
                        if entity and self._validate_entity(entity, source_text):
                            entities.append(entity)
                    except Exception as e:
                        logger.warning(f"解析实体数据失败: {str(e)}")
                        continue
            
            # 创建实体名称到实体对象的映射
            entity_map = {entity.name: entity for entity in entities}
            
            # 解析关系
            if 'relationships' in data and isinstance(data['relationships'], list):
                for i, rel_data in enumerate(data['relationships']):
                    try:
                        relationship = self._parse_relationship_data(
                            rel_data, entity_map, source_text, chunk_id, chunk_index, i, chunk_metadata
                        )
                        if relationship and self._validate_relationship(relationship, source_text):
                            relationships.append(relationship)
                    except Exception as e:
                        logger.warning(f"解析关系数据失败: {str(e)}")
                        continue
            
        except json.JSONDecodeError as e:
            logger.error(f"知识JSON解析失败: {str(e)}")
        except Exception as e:
            logger.error(f"解析知识响应失败: {str(e)}")
        
        return entities, relationships
    
    def _parse_entity_data(self, entity_data: Dict[str, Any], source_text: str, 
                          chunk_id: str, entity_index: int, chunk_metadata: Dict[str, Any]) -> Optional[Entity]:
        """解析实体数据"""
        try:
            name = entity_data.get('name', '').strip()
            entity_type = entity_data.get('type', '').strip()
            
            if not name or not entity_type:
                return None
            
            # 验证实体类型
            if entity_type not in self.entity_types:
                entity_type = self._match_entity_type(entity_type)
            
            # 获取位置信息
            start_pos = entity_data.get('start_pos', 0)
            end_pos = entity_data.get('end_pos', len(name))
            
            # 如果位置信息不准确，尝试在文本中查找
            if start_pos == 0 and end_pos == len(name):
                text_lower = source_text.lower()
                name_lower = name.lower()
                pos = text_lower.find(name_lower)
                if pos != -1:
                    start_pos = pos
                    end_pos = pos + len(name)
            
            # 获取chunk索引信息
            chunk_index = chunk_metadata.get('chunk_index', 0)
            
            # 🆕 支持增强字段的实体创建
            entity = Entity(
                id=f"{chunk_id}_entity_{entity_index}",
                name=name,
                type=entity_type,
                description=entity_data.get('description', ''),
                properties={
                    **entity_data.get('properties', {}),
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_index,
                    "entity_index": entity_index
                },
                confidence=float(entity_data.get('confidence', 0.7)),
                source_text=source_text[:300] + '...' if len(source_text) > 300 else source_text,
                start_pos=start_pos,
                end_pos=end_pos,
                chunk_neo4j_id=None,
                document_postgresql_id=chunk_metadata.get('postgresql_document_id'),
                document_neo4j_id=None,
                # 🆕 显式初始化增强字段，确保向前兼容
                aliases=entity_data.get('aliases', []),  # 支持从LLM响应中获取别名
                embedding=None,  # 将在后续步骤中生成
                quality_score=float(entity_data.get('quality_score', 0.8))  # 默认质量分数
            )
            
            # 添加chunk_index作为实体属性，便于后续关联
            entity.chunk_index = chunk_index
            
            return entity
            
        except Exception as e:
            logger.warning(f"解析实体数据失败: {str(e)}")
            return None
    
    def _parse_relationship_data(self, rel_data: Dict[str, Any], entity_map: Dict[str, Entity], 
                               source_text: str, chunk_id: str, chunk_index: int, 
                               rel_index: int, chunk_metadata: Dict[str, Any]) -> Optional[Relationship]:
        """解析关系数据"""
        try:
            source_name = rel_data.get('source_entity', '').strip()
            target_name = rel_data.get('target_entity', '').strip()
            rel_type = rel_data.get('relationship_type', '').strip()
            
            if not source_name or not target_name or not rel_type:
                return None
            
            # 验证实体存在
            if source_name not in entity_map or target_name not in entity_map:
                return None
            
            # 验证关系类型
            if rel_type not in self.relationship_types:
                rel_type = self._match_relationship_type(rel_type)
            
            # 获取实体对象
            source_entity = entity_map[source_name]
            target_entity = entity_map[target_name]
            
            relationship = Relationship(
                id=f"{chunk_id}_rel_{rel_index}",
                source_entity_id=source_entity.id,
                target_entity_id=target_entity.id,
                source_entity_name=source_name,
                target_entity_name=target_name,
                relationship_type=rel_type,
                description=rel_data.get('description', ''),
                properties=rel_data.get('properties', {}),
                confidence=float(rel_data.get('confidence', 0.7)),
                source_text=source_text[:300] + '...' if len(source_text) > 300 else source_text,
                context=rel_data.get('context', ''),
                chunk_neo4j_id=None,
                document_postgresql_id=chunk_metadata.get('postgresql_document_id'),
                document_neo4j_id=None
            )
            
            return relationship
            
        except Exception as e:
            logger.warning(f"解析关系数据失败: {str(e)}")
            return None
    
    def _match_entity_type(self, entity_type: str) -> str:
        """匹配实体类型"""
        entity_type_lower = entity_type.lower()
        
        # 类型映射表
        type_mapping = {
            'person': '人物', 'people': '人物', '人员': '人物', '人名': '人物',
            'organization': '组织', 'org': '组织', '机构': '组织', '公司': '组织',
            'location': '地点', 'place': '地点', '位置': '地点', '地名': '地点',
            'event': '事件', '活动': '事件', '会议': '事件',
            'concept': '概念', '观念': '概念', '想法': '概念',
            'technology': '技术', 'tech': '技术', '科技': '技术',
            'product': '产品', '商品': '产品', '货物': '产品',
            'time': '时间', 'date': '时间', '日期': '时间',
            'number': '数字', 'numeric': '数字', '数量': '数字',
            'law': '法律条文', 'legal': '法律条文', '法规': '法律条文',
            'policy': '政策', '方针': '政策', '规定': '政策',
            'project': '项目', '工程': '项目', '计划': '项目',
            'system': '系统', '体系': '系统', '制度': '系统',
            'method': '方法', '方式': '方法', '手段': '方法',
            'theory': '理论', '学说': '理论', '观点': '理论'
        }
        
        # 查找匹配
        for key, value in type_mapping.items():
            if key in entity_type_lower:
                return value
        
        # 默认返回概念类型
        return '概念'
    
    def _match_relationship_type(self, rel_type: str) -> str:
        """匹配关系类型"""
        rel_type_lower = rel_type.lower()
        
        # 关系类型映射表
        type_mapping = {
            'belongs': '属于', 'belong_to': '属于', '隶属': '属于',
            'contains': '包含', 'include': '包含', '包括': '包含',
            'located': '位于', 'location': '位于', '地处': '位于',
            'works': '工作于', 'work_for': '工作于', '任职': '工作于',
            'founded': '创立', 'establish': '创立', '建立': '创立',
            'manages': '管理', 'manage': '管理', '负责': '管理',
            'cooperate': '合作', 'collaborate': '合作', '协作': '合作',
            'mentions': '提及', 'mention': '提及', '涉及': '提及',
            'describes': '描述', 'describe': '描述', '说明': '描述',
            'references': '引用', 'reference': '引用', '参考': '引用',
            'causes': '导致', 'cause': '导致', '引起': '导致',
            'influences': '影响', 'influence': '影响', '作用': '影响',
            'uses': '使用', 'use': '使用', '利用': '使用',
            'depends': '依赖', 'depend': '依赖', '依靠': '依赖',
            'implements': '实现', 'implement': '实现', '执行': '实现',
            'relates': '相关', 'relate': '相关', '关系': '相关',
            'connects': '连接', 'connect': '连接', '连通': '连接',
            'associates': '关联', 'associate': '关联', '联系': '关联'
        }
        
        # 查找匹配
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
        
        # 检查位置信息
        if entity.start_pos < 0 or entity.end_pos <= entity.start_pos:
            return False
        
        if entity.end_pos > len(source_text):
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
        
        # 检查关系类型有效性
        if relationship.relationship_type not in self.relationship_types:
            return False
        
        return True
    
    # 传统去重方法已移除，全面使用智能实体统一
    
    def _extract_chunk_id_from_entity_id(self, entity_id: str) -> Optional[str]:
        """从实体ID中提取chunk_id
        
        实体ID格式：{chunk_id}_entity_{entity_index}
        
        Args:
            entity_id: 实体ID
            
        Returns:
            chunk_id，如果无法提取则返回None
        """
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
    
    def _normalize_entity_name(self, name: str) -> str:
        """标准化实体名称"""
        # 移除多余空格
        normalized = re.sub(r'\s+', ' ', name.strip())
        
        # 移除特殊字符
        normalized = re.sub(r'[""''《》【】（）()]', '', normalized)
        
        # 转换为小写进行比较
        return normalized.lower()
    
    # 🆕 智能实体统一方法
    # 🚫 DEPRECATED: 此方法已弃用，实体统一移至全局统一任务
    async def _unify_entities_intelligent(self, entities: List[Entity]) -> List[Entity]:
        """
        [已弃用] 使用智能实体统一算法进行实体标准化
        
        此方法已被移除，实体统一现在在全局统一任务中使用LangGraph Agent执行。
        文档处理中的实体直接入库，不再进行文档内统一。
        
        Args:
            entities: 原始实体列表
            
        Returns:
            统一后的实体列表
        """
        logger.warning("_unify_entities_intelligent方法已弃用，请使用全局统一任务")
        return entities  # 直接返回原实体，不进行统一
    
    def _create_chunk_mapping_for_raw_entities(self, raw_entities: List[Entity]) -> Dict[str, List[str]]:
        """
        为原始实体创建chunk映射（不统一）
        
        Args:
            raw_entities: 原始实体列表
            
        Returns:
            实体键到chunk ID列表的映射
        """
        entity_chunk_mapping = {}
        
        for entity in raw_entities:
            # 为原始实体创建键
            entity_key = (self._normalize_entity_name(entity.name), entity.type)
            
            # 从实体ID中提取chunk信息
            chunk_id = self._extract_chunk_id_from_entity_id(entity.id)
            
            if entity_key not in entity_chunk_mapping:
                entity_chunk_mapping[entity_key] = []
            
            if chunk_id and chunk_id not in entity_chunk_mapping[entity_key]:
                entity_chunk_mapping[entity_key].append(chunk_id)
        
        return entity_chunk_mapping
    
    def _create_chunk_mapping_for_unified_entities(self, unified_entities: List[Entity]) -> Dict[str, List[str]]:
        """
        为统一后的实体创建chunk映射
        
        Args:
            unified_entities: 统一后的实体列表
            
        Returns:
            实体键到chunk ID列表的映射
        """
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
            
            # 也检查实体属性中是否已有chunk_ids信息
            existing_chunk_ids = entity.properties.get('chunk_ids', [])
            for chunk_id in existing_chunk_ids:
                if chunk_id not in chunk_ids:
                    chunk_ids.append(chunk_id)
            
            entity_chunk_mapping[entity_key] = chunk_ids
        
        logger.debug(f"为 {len(unified_entities)} 个统一实体创建了chunk映射")
        return entity_chunk_mapping
    
    async def _trigger_post_extraction_unification(self, entities: List[Entity], chunks: List[Any]):
        """
        触发文档解析后的实体统一任务
        
        Args:
            entities: 统一后的实体列表
            chunks: 文档块列表
        """
        try:
            # 获取文档ID
            document_id = None
            if chunks and hasattr(chunks[0], 'metadata'):
                document_id = chunks[0].metadata.postgresql_document_id
            
            if not document_id:
                logger.warning("无法获取文档ID，跳过实体统一触发")
                return
            
            # 检查是否需要触发实体统一（基于配置）
            if not getattr(settings, 'ENABLE_POST_EXTRACTION_UNIFICATION', True):
                logger.info("文档解析后实体统一已禁用，跳过触发")
                return
            
            # 转换实体为字典格式
            entities_data = []
            for entity in entities:
                entity_data = {
                    'id': entity.id,
                    'name': entity.name,
                    'type': entity.type,
                    'entity_type': entity.entity_type,
                    'description': entity.description,
                    'properties': entity.properties,
                    'confidence': entity.confidence,
                    'source_text': entity.source_text,
                    'start_pos': entity.start_pos,
                    'end_pos': entity.end_pos,
                    'chunk_neo4j_id': entity.chunk_neo4j_id,
                    'document_postgresql_id': entity.document_postgresql_id,
                    'document_neo4j_id': entity.document_neo4j_id,
                    'aliases': entity.aliases,
                    'embedding': entity.embedding,
                    'quality_score': entity.quality_score,
                    'importance_score': entity.importance_score
                }
                entities_data.append(entity_data)
            
            # 触发异步实体统一任务
            from app.worker.celery_tasks import trigger_document_entity_unification
            
            # 🆕 使用全局语义统一模式，确保使用最新的LangGraph Agent
            unification_mode = getattr(settings, 'DEFAULT_UNIFICATION_MODE', 'global_semantic')
            
            result = trigger_document_entity_unification(
                document_id=document_id,
                extracted_entities=entities_data,
                unification_mode=unification_mode
            )
            
            logger.info(f"已触发文档解析后实体统一任务: {result['task_id']}, 模式: {unification_mode}")
            
        except Exception as e:
            logger.error(f"触发文档解析后实体统一失败: {str(e)}")
            # 不抛出异常，避免影响主流程 