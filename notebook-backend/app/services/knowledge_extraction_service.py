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

logger = logging.getLogger(__name__)

@dataclass
class Entity:
    """实体数据类"""
    id: str
    name: str
    type: str
    description: str
    properties: Dict[str, Any]
    confidence: float
    source_text: str
    start_pos: int
    end_pos: int
    chunk_neo4j_id: Optional[str] = None
    document_postgresql_id: Optional[int] = None
    document_neo4j_id: Optional[str] = None
    chunk_index: int = 0
    entity_index: int = 0

@dataclass
class Relationship:
    """关系数据类"""
    id: str
    source_entity_id: str
    target_entity_id: str
    source_entity_name: str
    target_entity_name: str
    relationship_type: str
    description: str
    properties: Dict[str, Any]
    confidence: float
    source_text: str
    context: str
    chunk_neo4j_id: Optional[str] = None
    document_postgresql_id: Optional[int] = None
    document_neo4j_id: Optional[str] = None

@dataclass
class KnowledgeExtractionResult:
    """知识抽取结果"""
    entities: List[Entity]
    relationships: List[Relationship]
    chunk_id: str
    chunk_index: int
    success: bool
    error_message: Optional[str] = None

class KnowledgeExtractionService:
    """知识抽取服务
    
    使用大语言模型从文档分块中同时抽取实体和关系
    """
    
    def __init__(self):
        """初始化知识抽取服务"""
        self.llm_service = LLMClientService()
        self.entity_types = self._load_entity_types()
        self.relationship_types = self._load_relationship_types()
        logger.info("知识抽取服务已初始化")
    
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
            
            # 去重和标准化
            deduplicated_entities, entity_chunk_mapping = self._deduplicate_entities_with_chunk_mapping(all_entities)
            filtered_relationships = self._filter_relationships(all_relationships, deduplicated_entities)
            
            # 将chunk映射信息添加到实体属性中
            for entity in deduplicated_entities:
                entity_key = (self._normalize_entity_name(entity.name), entity.type)
                chunk_ids = entity_chunk_mapping.get(entity_key, [])
                entity.properties['chunk_ids'] = chunk_ids
                entity.properties['appears_in_chunks_count'] = len(chunk_ids)
            
            logger.info(f"知识抽取完成：实体 {len(all_entities)} -> {len(deduplicated_entities)}，关系 {len(all_relationships)} -> {len(filtered_relationships)}")
            
            return deduplicated_entities, filtered_relationships
            
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
                document_neo4j_id=None
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
    
    def _deduplicate_entities_with_chunk_mapping(self, entities: List[Entity]) -> Tuple[List[Entity], Dict[str, List[str]]]:
        """去重实体但保留chunk映射信息
        
        Returns:
            - 去重后的实体列表（每个唯一实体只有一个实例）
            - 实体到chunk的映射字典 {entity_key: [chunk_id1, chunk_id2, ...]}
        """
        logger.info(f"开始去重 {len(entities)} 个实体并保留chunk映射")
        
        # 按名称和类型分组
        entity_groups = {}
        entity_chunk_mapping = {}
        
        for entity in entities:
            # 标准化实体名称
            normalized_name = self._normalize_entity_name(entity.name)
            key = (normalized_name, entity.type)
            
            if key not in entity_groups:
                entity_groups[key] = []
                entity_chunk_mapping[key] = []
            
            entity_groups[key].append(entity)
            
            # 从实体ID中提取chunk_id
            chunk_id = self._extract_chunk_id_from_entity_id(entity.id)
            if chunk_id and chunk_id not in entity_chunk_mapping[key]:
                entity_chunk_mapping[key].append(chunk_id)
        
        # 每组选择最佳实体
        deduplicated = []
        
        for key, group in entity_groups.items():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # 选择置信度最高的实体
                best_entity = max(group, key=lambda x: x.confidence)
                
                # 合并属性
                merged_properties = {}
                for entity in group:
                    merged_properties.update(entity.properties)
                
                best_entity.properties = merged_properties
                deduplicated.append(best_entity)
        
        logger.info(f"实体去重完成：{len(deduplicated)} 个唯一实体，保留了 {len(entity_chunk_mapping)} 个实体-chunk映射")
        return deduplicated, entity_chunk_mapping
    
    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """去重和标准化实体（保留向后兼容性）"""
        deduplicated, _ = self._deduplicate_entities_with_chunk_mapping(entities)
        return deduplicated
    
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