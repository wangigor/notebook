import logging
import json
import re
import asyncio
from typing import List, Dict, Any, Optional, Set
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

class EntityExtractionService:
    """LLM实体抽取服务
    
    使用大语言模型从文档分块中抽取实体，包括：
    - 实体识别和类型分类
    - 实体去重和标准化
    - 实体属性提取
    - 置信度评估
    """
    
    def __init__(self):
        """初始化实体抽取服务"""
        self.llm_service = LLMClientService()
        self.entity_types = self._load_entity_types()
        self.extracted_entities = set()  # 用于去重
        logger.info("实体抽取服务已初始化")
    
    def _load_entity_types(self) -> List[str]:
        """加载实体类型配置
        
        Returns:
            实体类型列表
        """
        # 可配置的实体类型，后续可从配置文件或数据库加载
        return [
            "人物", "组织", "地点", "事件", "概念", 
            "技术", "产品", "时间", "数字", "法律条文",
            "政策", "项目", "系统", "方法", "理论"
        ]
    
    async def extract_entities_from_chunks(self, chunks: List[Dict[str, Any]]) -> List[Entity]:
        """从文档分块中抽取实体
        
        Args:
            chunks: 文档分块列表
            
        Returns:
            抽取的实体列表
        """
        logger.info(f"开始从 {len(chunks)} 个分块中抽取实体")
        
        all_entities = []
        
        try:
            # 处理每个分块
            for i, chunk in enumerate(chunks):
                chunk_content = chunk.get('content', '')
                if not chunk_content.strip():
                    continue
                
                logger.info(f"处理分块 {i+1}/{len(chunks)}")
                
                # 从单个分块抽取实体
                chunk_entities = await self._extract_entities_from_text(
                    text=chunk_content,
                    chunk_id=chunk.get('id', f'chunk_{i}'),
                    chunk_index=i
                )
                
                all_entities.extend(chunk_entities)
                
                # 避免过于频繁的API调用
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.1)
            
            # 去重和标准化
            deduplicated_entities = self._deduplicate_entities(all_entities)
            
            logger.info(f"实体抽取完成：原始 {len(all_entities)} 个，去重后 {len(deduplicated_entities)} 个")
            
            return deduplicated_entities
            
        except Exception as e:
            logger.error(f"实体抽取失败: {str(e)}")
            raise
    
    async def _extract_entities_from_text(self, text: str, chunk_id: str, 
                                        chunk_index: int) -> List[Entity]:
        """从单个文本中抽取实体
        
        Args:
            text: 文本内容
            chunk_id: 分块ID
            chunk_index: 分块索引
            
        Returns:
            实体列表
        """
        try:
            # 构建提示词
            prompt = self._build_entity_extraction_prompt(text)
            
            # 获取LLM实例（非流式）
            llm = self.llm_service.get_processing_llm(streaming=False)
            
            # 调用LLM
            message = HumanMessage(content=prompt)
            response = await llm.ainvoke([message])
            
            # 获取响应内容
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # 解析LLM响应
            entities = self._parse_llm_response(response_content, text, chunk_id, chunk_index)
            
            logger.info(f"从分块 {chunk_index} 抽取到 {len(entities)} 个实体")
            return entities
            
        except Exception as e:
            logger.error(f"从文本抽取实体失败: {str(e)}")
            return []
    
    def _build_entity_extraction_prompt(self, text: str) -> str:
        """构建实体抽取提示词
        
        Args:
            text: 要处理的文本
            
        Returns:
            提示词字符串
        """
        entity_types_str = "、".join(self.entity_types)
        
        prompt = f"""
请从以下文本中抽取实体信息。

支持的实体类型：{entity_types_str}

文本内容：
{text}

请按照以下JSON格式返回结果，每个实体包含以下字段：
- name: 实体名称（必须）
- type: 实体类型（从上述类型中选择）
- description: 实体描述（简短说明）
- properties: 实体属性（键值对，可选）
- confidence: 置信度（0.0-1.0）
- start_pos: 在文本中的起始位置
- end_pos: 在文本中的结束位置

返回格式：
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
    ]
}}
```

注意事项：
1. 只抽取重要的、有意义的实体
2. 确保实体名称准确完整
3. 实体类型必须从提供的类型中选择
4. 置信度要根据上下文合理评估
5. 位置信息要准确
6. 避免重复抽取相同实体
"""
        return prompt
    
    def _parse_llm_response(self, response: str, source_text: str, 
                          chunk_id: str, chunk_index: int) -> List[Entity]:
        """解析LLM响应
        
        Args:
            response: LLM响应内容
            source_text: 原始文本
            chunk_id: 分块ID
            chunk_index: 分块索引
            
        Returns:
            解析后的实体列表
        """
        entities = []
        
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
            
            if 'entities' in data and isinstance(data['entities'], list):
                for i, entity_data in enumerate(data['entities']):
                    try:
                        # 验证必需字段
                        if not entity_data.get('name') or not entity_data.get('type'):
                            continue
                        
                        # 验证实体类型
                        entity_type = entity_data.get('type')
                        if entity_type not in self.entity_types:
                            # 尝试匹配最相似的类型
                            entity_type = self._match_entity_type(entity_type)
                        
                        # 创建实体对象
                        entity = Entity(
                            id=f"{chunk_id}_entity_{i}",
                            name=entity_data.get('name', '').strip(),
                            type=entity_type,
                            description=entity_data.get('description', ''),
                            properties=entity_data.get('properties', {}),
                            confidence=float(entity_data.get('confidence', 0.8)),
                            source_text=source_text[:200] + '...' if len(source_text) > 200 else source_text,
                            start_pos=int(entity_data.get('start_pos', 0)),
                            end_pos=int(entity_data.get('end_pos', 0))
                        )
                        
                        # 验证实体有效性
                        if self._validate_entity(entity, source_text):
                            entities.append(entity)
                        
                    except Exception as e:
                        logger.warning(f"解析实体数据失败: {str(e)}")
                        continue
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            # 尝试使用正则表达式提取实体
            entities = self._fallback_entity_extraction(response, source_text, chunk_id)
        except Exception as e:
            logger.error(f"解析LLM响应失败: {str(e)}")
        
        return entities
    
    def _match_entity_type(self, entity_type: str) -> str:
        """匹配实体类型
        
        Args:
            entity_type: 原始实体类型
            
        Returns:
            匹配的标准实体类型
        """
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
    
    def _validate_entity(self, entity: Entity, source_text: str) -> bool:
        """验证实体有效性
        
        Args:
            entity: 实体对象
            source_text: 原始文本
            
        Returns:
            是否有效
        """
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
        
        # 检查实体名称是否在文本中
        extracted_text = source_text[entity.start_pos:entity.end_pos]
        if entity.name.lower() not in extracted_text.lower():
            # 尝试在整个文本中查找
            if entity.name.lower() not in source_text.lower():
                return False
        
        return True
    
    def _fallback_entity_extraction(self, response: str, source_text: str, 
                                  chunk_id: str) -> List[Entity]:
        """备选实体抽取方法
        
        Args:
            response: LLM响应
            source_text: 原始文本
            chunk_id: 分块ID
            
        Returns:
            实体列表
        """
        entities = []
        
        try:
            # 使用正则表达式寻找可能的实体
            lines = response.split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # 寻找包含实体信息的行
                if any(keyword in line for keyword in ['名称', 'name', '实体', '类型']):
                    # 提取可能的实体名称
                    name_match = re.search(r'[：:]\s*([^，,。.]+)', line)
                    if name_match:
                        entity_name = name_match.group(1).strip()
                        
                        if len(entity_name) >= 2:
                            entity = Entity(
                                id=f"{chunk_id}_fallback_{i}",
                                name=entity_name,
                                type='概念',  # 默认类型
                                description=f"通过备选方法抽取：{line}",
                                properties={},
                                confidence=0.5,  # 较低置信度
                                source_text=source_text[:100] + '...',
                                start_pos=0,
                                end_pos=len(entity_name)
                            )
                            entities.append(entity)
            
        except Exception as e:
            logger.error(f"备选实体抽取失败: {str(e)}")
        
        return entities
    
    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """去重和标准化实体
        
        Args:
            entities: 原始实体列表
            
        Returns:
            去重后的实体列表
        """
        logger.info(f"开始去重 {len(entities)} 个实体")
        
        # 按名称和类型分组
        entity_groups = {}
        
        for entity in entities:
            # 标准化实体名称
            normalized_name = self._normalize_entity_name(entity.name)
            key = (normalized_name, entity.type)
            
            if key not in entity_groups:
                entity_groups[key] = []
            entity_groups[key].append(entity)
        
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
        
        logger.info(f"去重完成：{len(deduplicated)} 个唯一实体")
        return deduplicated
    
    def _normalize_entity_name(self, name: str) -> str:
        """标准化实体名称
        
        Args:
            name: 原始名称
            
        Returns:
            标准化后的名称
        """
        # 移除多余空格
        normalized = re.sub(r'\s+', ' ', name.strip())
        
        # 移除特殊字符
        normalized = re.sub(r'[""''《》【】（）()]', '', normalized)
        
        # 转换为小写进行比较
        return normalized.lower()
    
    async def get_extraction_statistics(self, entities: List[Entity]) -> Dict[str, Any]:
        """获取抽取统计信息
        
        Args:
            entities: 实体列表
            
        Returns:
            统计信息
        """
        stats = {
            'total_entities': len(entities),
            'by_type': {},
            'confidence_distribution': {
                'high': 0,  # > 0.8
                'medium': 0,  # 0.5 - 0.8
                'low': 0  # < 0.5
            },
            'avg_confidence': 0.0
        }
        
        if not entities:
            return stats
        
        # 按类型统计
        for entity in entities:
            entity_type = entity.type
            if entity_type not in stats['by_type']:
                stats['by_type'][entity_type] = 0
            stats['by_type'][entity_type] += 1
            
            # 置信度分布
            if entity.confidence > 0.8:
                stats['confidence_distribution']['high'] += 1
            elif entity.confidence > 0.5:
                stats['confidence_distribution']['medium'] += 1
            else:
                stats['confidence_distribution']['low'] += 1
        
        # 平均置信度
        stats['avg_confidence'] = sum(e.confidence for e in entities) / len(entities)
        
        return stats