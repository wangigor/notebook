import logging
import json
import re
import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from langchain_core.messages import HumanMessage
from app.core.config import settings
from app.services.llm_client_service import LLMClientService

# 🆕 使用统一的Entity和Relationship模型
from app.models.entity import Entity, Relationship

logger = logging.getLogger(__name__)

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

class RelationshipService:
    """关系识别服务
    
    使用大语言模型识别实体间的关系，包括：
    - 关系类型识别
    - 关系方向判断
    - 关系置信度评估
    - 关系属性提取
    """
    
    def __init__(self):
        """初始化关系识别服务"""
        self.llm_service = LLMClientService()
        self.relationship_types = self._load_relationship_types()
        logger.info("关系识别服务已初始化")
    
    def _load_relationship_types(self) -> List[str]:
        """加载关系类型配置
        
        Returns:
            关系类型列表
        """
        # 可配置的关系类型，后续可从配置文件或数据库加载
        return [
            "包含", "属于", "关联", "依赖", "影响", "导致",
            "协作", "竞争", "继承", "实现", "使用", "管理",
            "参与", "负责", "位于", "发生在", "引用", "定义",
            "产生", "支持", "反对", "替代", "扩展", "组成",
            "相似", "相反", "前置", "后续", "并行", "互斥"
        ]
    
    async def extract_relationships_from_entities(self, entities: List[Entity], 
                                                chunks: List[Dict[str, Any]]) -> List[Relationship]:
        """从实体中抽取关系
        
        Args:
            entities: 实体列表
            chunks: 原始文档分块（提供上下文）
            
        Returns:
            关系列表
        """
        logger.info(f"开始从 {len(entities)} 个实体中抽取关系")
        
        all_relationships = []
        
        try:
            # 为每个分块抽取关系
            for i, chunk in enumerate(chunks):
                chunk_content = chunk.get('content', '')
                if not chunk_content.strip():
                    continue
                
                # 找到该分块中的实体
                chunk_entities = self._find_entities_in_chunk(entities, chunk, i)
                
                if len(chunk_entities) < 2:
                    continue  # 至少需要2个实体才能形成关系
                
                logger.info(f"分块 {i+1} 包含 {len(chunk_entities)} 个实体，开始抽取关系")
                
                # 从分块中抽取关系
                chunk_relationships = await self._extract_relationships_from_chunk(
                    chunk_entities, chunk_content, i
                )
                
                all_relationships.extend(chunk_relationships)
                
                # 避免过于频繁的API调用
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.1)
            
            # 去重和过滤
            filtered_relationships = self._filter_relationships(all_relationships)
            
            logger.info(f"关系抽取完成：原始 {len(all_relationships)} 个，过滤后 {len(filtered_relationships)} 个")
            
            return filtered_relationships
            
        except Exception as e:
            logger.error(f"关系抽取失败: {str(e)}")
            raise
    
    def _find_entities_in_chunk(self, entities: List[Entity], chunk: Dict[str, Any], 
                              chunk_index: int) -> List[Entity]:
        """找到分块中的实体
        
        Args:
            entities: 所有实体列表
            chunk: 分块信息
            chunk_index: 分块索引
            
        Returns:
            该分块中的实体列表
        """
        chunk_content = chunk.get('content', '').lower()
        chunk_entities = []
        
        for entity in entities:
            # 检查实体是否来自该分块
            if f"chunk_{chunk_index}" in entity.id:
                chunk_entities.append(entity)
            # 或者检查实体名称是否在分块内容中
            elif entity.name.lower() in chunk_content:
                chunk_entities.append(entity)
        
        return chunk_entities
    
    async def _extract_relationships_from_chunk(self, entities: List[Entity], 
                                              chunk_content: str, 
                                              chunk_index: int) -> List[Relationship]:
        """从分块中抽取关系
        
        Args:
            entities: 分块中的实体列表
            chunk_content: 分块内容
            chunk_index: 分块索引
            
        Returns:
            关系列表
        """
        try:
            # 构建提示词
            prompt = self._build_relationship_extraction_prompt(entities, chunk_content)
            
            # 获取LLM实例（非流式）
            llm = self.llm_service.get_processing_llm(streaming=False)
            
            # 调用LLM
            message = HumanMessage(content=prompt)
            response = await llm.ainvoke([message])
            
            # 获取响应内容
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # 解析LLM响应
            relationships = self._parse_relationship_response(
                response_content, entities, chunk_content, chunk_index
            )
            
            logger.info(f"从分块 {chunk_index} 抽取到 {len(relationships)} 个关系")
            return relationships
            
        except Exception as e:
            logger.error(f"从分块抽取关系失败: {str(e)}")
            return []
    
    def _build_relationship_extraction_prompt(self, entities: List[Entity], 
                                            chunk_content: str) -> str:
        """构建关系抽取提示词
        
        Args:
            entities: 实体列表
            chunk_content: 文本内容
            
        Returns:
            提示词字符串
        """
        # 构建实体列表
        entity_list = []
        for i, entity in enumerate(entities):
            entity_list.append(f"{i+1}. {entity.name} ({entity.type})")
        
        entity_list_str = "\n".join(entity_list)
        relationship_types_str = "、".join(self.relationship_types)
        
        prompt = f"""
请分析以下文本中实体之间的关系。

实体列表：
{entity_list_str}

支持的关系类型：{relationship_types_str}

文本内容：
{chunk_content}

请按照以下JSON格式返回结果，分析实体之间的关系：
- source_entity: 源实体名称（必须在上述实体列表中）
- target_entity: 目标实体名称（必须在上述实体列表中）
- relationship_type: 关系类型（从上述类型中选择）
- description: 关系描述（基于文本内容）
- properties: 关系属性（键值对，可选）
- confidence: 置信度（0.0-1.0）
- context: 支持该关系的文本片段

返回格式：
```json
{{
    "relationships": [
        {{
            "source_entity": "实体A",
            "target_entity": "实体B",
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
1. 只抽取文本中明确体现的关系
2. 确保源实体和目标实体都在提供的实体列表中
3. 关系类型必须从提供的类型中选择
4. 置信度要根据文本证据强度评估
5. 上下文要准确反映关系的文本依据
6. 避免重复或冗余的关系
7. 注意关系的方向性
"""
        return prompt
    
    def _parse_relationship_response(self, response: str, entities: List[Entity], 
                                   chunk_content: str, chunk_index: int) -> List[Relationship]:
        """解析关系抽取响应
        
        Args:
            response: LLM响应
            entities: 实体列表
            chunk_content: 分块内容
            chunk_index: 分块索引
            
        Returns:
            关系列表
        """
        relationships = []
        
        try:
            # 创建实体名称到实体对象的映射
            entity_map = {entity.name: entity for entity in entities}
            
            # 提取JSON部分
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response.strip()
            
            # 解析JSON
            data = json.loads(json_str)
            
            if 'relationships' in data and isinstance(data['relationships'], list):
                for i, rel_data in enumerate(data['relationships']):
                    try:
                        # 验证必需字段
                        source_name = rel_data.get('source_entity', '').strip()
                        target_name = rel_data.get('target_entity', '').strip()
                        rel_type = rel_data.get('relationship_type', '').strip()
                        
                        if not source_name or not target_name or not rel_type:
                            continue
                        
                        # 验证实体存在
                        if source_name not in entity_map or target_name not in entity_map:
                            continue
                        
                        # 验证关系类型
                        if rel_type not in self.relationship_types:
                            rel_type = self._match_relationship_type(rel_type)
                        
                        # 获取实体对象
                        source_entity = entity_map[source_name]
                        target_entity = entity_map[target_name]
                        
                        # 创建关系对象
                        relationship = Relationship(
                            id=f"chunk_{chunk_index}_rel_{i}",
                            source_entity_id=source_entity.id,
                            target_entity_id=target_entity.id,
                            source_entity_name=source_name,
                            target_entity_name=target_name,
                            relationship_type=rel_type,
                            description=rel_data.get('description', ''),
                            properties=rel_data.get('properties', {}),
                            confidence=float(rel_data.get('confidence', 0.7)),
                            source_text=chunk_content[:300] + '...' if len(chunk_content) > 300 else chunk_content,
                            context=rel_data.get('context', '')
                        )
                        
                        # 验证关系有效性
                        if self._validate_relationship(relationship, chunk_content):
                            relationships.append(relationship)
                        
                    except Exception as e:
                        logger.warning(f"解析关系数据失败: {str(e)}")
                        continue
            
        except json.JSONDecodeError as e:
            logger.error(f"关系JSON解析失败: {str(e)}")
            # 尝试使用备选方法
            relationships = self._fallback_relationship_extraction(
                response, entities, chunk_content, chunk_index
            )
        except Exception as e:
            logger.error(f"解析关系响应失败: {str(e)}")
        
        return relationships
    
    def _match_relationship_type(self, rel_type: str) -> str:
        """匹配关系类型
        
        Args:
            rel_type: 原始关系类型
            
        Returns:
            匹配的标准关系类型
        """
        rel_type_lower = rel_type.lower()
        
        # 关系类型映射表
        type_mapping = {
            'contain': '包含', 'include': '包含', '拥有': '包含',
            'belong': '属于', 'belongto': '属于', '隶属': '属于',
            'relate': '关联', 'connect': '关联', '相关': '关联',
            'depend': '依赖', 'dependency': '依赖', '依靠': '依赖',
            'affect': '影响', 'influence': '影响', '作用': '影响',
            'cause': '导致', 'lead': '导致', '引起': '导致',
            'collaborate': '协作', 'cooperate': '协作', '合作': '协作',
            'compete': '竞争', 'competition': '竞争', '对抗': '竞争',
            'inherit': '继承', 'extend': '继承', '扩展': '继承',
            'implement': '实现', 'realize': '实现', '执行': '实现',
            'use': '使用', 'utilize': '使用', '应用': '使用',
            'manage': '管理', 'control': '管理', '控制': '管理',
            'participate': '参与', 'join': '参与', '加入': '参与',
            'responsible': '负责', 'charge': '负责', '主管': '负责',
            'locate': '位于', 'position': '位于', '处于': '位于',
            'happen': '发生在', 'occur': '发生在', '出现': '发生在',
            'reference': '引用', 'cite': '引用', '提及': '引用',
            'define': '定义', 'definition': '定义', '规定': '定义',
            'generate': '产生', 'create': '产生', '生成': '产生',
            'support': '支持', 'back': '支持', '支撑': '支持',
            'oppose': '反对', 'against': '反对', '对立': '反对',
            'replace': '替代', 'substitute': '替代', '代替': '替代',
            'similar': '相似', 'like': '相似', '类似': '相似',
            'opposite': '相反', 'contrary': '相反', '对立': '相反',
            'before': '前置', 'precede': '前置', '先于': '前置',
            'after': '后续', 'follow': '后续', '随后': '后续',
            'parallel': '并行', 'concurrent': '并行', '同时': '并行',
            'exclusive': '互斥', 'conflict': '互斥', '冲突': '互斥'
        }
        
        # 查找匹配
        for key, value in type_mapping.items():
            if key in rel_type_lower:
                return value
        
        # 默认返回关联类型
        return '关联'
    
    def _validate_relationship(self, relationship: Relationship, source_text: str) -> bool:
        """验证关系有效性
        
        Args:
            relationship: 关系对象
            source_text: 原始文本
            
        Returns:
            是否有效
        """
        # 检查置信度
        if relationship.confidence < 0.3:
            return False
        
        # 检查实体不能是自身
        if relationship.source_entity_id == relationship.target_entity_id:
            return False
        
        # 检查实体名称
        if not relationship.source_entity_name or not relationship.target_entity_name:
            return False
        
        # 检查关系类型
        if not relationship.relationship_type:
            return False
        
        # 检查上下文是否在原文中
        if relationship.context and relationship.context.strip():
            if relationship.context.lower() not in source_text.lower():
                return False
        
        return True
    
    def _fallback_relationship_extraction(self, response: str, entities: List[Entity], 
                                        chunk_content: str, chunk_index: int) -> List[Relationship]:
        """备选关系抽取方法
        
        Args:
            response: LLM响应
            entities: 实体列表
            chunk_content: 分块内容
            chunk_index: 分块索引
            
        Returns:
            关系列表
        """
        relationships = []
        
        try:
            # 简单的模式匹配
            entity_names = [entity.name for entity in entities]
            entity_map = {entity.name: entity for entity in entities}
            
            lines = response.split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # 寻找包含实体关系的行
                found_entities = []
                for entity_name in entity_names:
                    if entity_name in line:
                        found_entities.append(entity_name)
                
                # 如果找到2个或更多实体，尝试抽取关系
                if len(found_entities) >= 2:
                    source_entity = entity_map[found_entities[0]]
                    target_entity = entity_map[found_entities[1]]
                    
                    # 简单的关系类型推断
                    rel_type = '关联'  # 默认关系类型
                    
                    relationship = Relationship(
                        id=f"chunk_{chunk_index}_fallback_rel_{i}",
                        source_entity_id=source_entity.id,
                        target_entity_id=target_entity.id,
                        source_entity_name=source_entity.name,
                        target_entity_name=target_entity.name,
                        relationship_type=rel_type,
                        description=f"通过备选方法抽取：{line}",
                        properties={},
                        confidence=0.4,  # 较低置信度
                        source_text=chunk_content[:200] + '...',
                        context=line
                    )
                    
                    relationships.append(relationship)
            
        except Exception as e:
            logger.error(f"备选关系抽取失败: {str(e)}")
        
        return relationships
    
    def _filter_relationships(self, relationships: List[Relationship]) -> List[Relationship]:
        """过滤和去重关系
        
        Args:
            relationships: 原始关系列表
            
        Returns:
            过滤后的关系列表
        """
        logger.info(f"开始过滤 {len(relationships)} 个关系")
        
        # 按关系键分组（源实体-目标实体-关系类型）
        relationship_groups = {}
        
        for relationship in relationships:
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
        
        logger.info(f"过滤完成：{len(high_confidence_relationships)} 个高质量关系")
        return high_confidence_relationships
    
    async def get_relationship_statistics(self, relationships: List[Relationship]) -> Dict[str, Any]:
        """获取关系统计信息
        
        Args:
            relationships: 关系列表
            
        Returns:
            统计信息
        """
        stats = {
            'total_relationships': len(relationships),
            'by_type': {},
            'confidence_distribution': {
                'high': 0,  # > 0.8
                'medium': 0,  # 0.5 - 0.8
                'low': 0  # < 0.5
            },
            'avg_confidence': 0.0,
            'entity_connectivity': {}
        }
        
        if not relationships:
            return stats
        
        # 按类型统计
        entity_connections = {}
        
        for relationship in relationships:
            # 关系类型统计
            rel_type = relationship.relationship_type
            if rel_type not in stats['by_type']:
                stats['by_type'][rel_type] = 0
            stats['by_type'][rel_type] += 1
            
            # 置信度分布
            if relationship.confidence > 0.8:
                stats['confidence_distribution']['high'] += 1
            elif relationship.confidence > 0.5:
                stats['confidence_distribution']['medium'] += 1
            else:
                stats['confidence_distribution']['low'] += 1
            
            # 实体连接度统计
            source = relationship.source_entity_name
            target = relationship.target_entity_name
            
            if source not in entity_connections:
                entity_connections[source] = 0
            if target not in entity_connections:
                entity_connections[target] = 0
            
            entity_connections[source] += 1
            entity_connections[target] += 1
        
        # 平均置信度
        stats['avg_confidence'] = sum(r.confidence for r in relationships) / len(relationships)
        
        # 实体连接度
        stats['entity_connectivity'] = entity_connections
        
        return stats 