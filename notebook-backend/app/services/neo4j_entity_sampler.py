# -*- coding: utf-8 -*-
"""
Neo4j实体抽样服务
从Neo4j数据库中按类型随机抽取实体，用于LLM语义去重
"""
import logging
import random
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Neo4jEntitySampler:
    """Neo4j实体抽样器"""
    
    def __init__(self):
        """初始化Neo4j连接"""
        # 统一使用同步驱动
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
        )
        logger.info("Neo4j实体抽样器初始化完成（同步模式）")
    
    def sample_entities_by_type(
        self, 
        entity_type: str, 
        limit: int = 50, 
        exclude_document_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        按类型从Neo4j随机抽取实体
        
        Args:
            entity_type: 实体类型（如：人物、组织、技术等）
            limit: 抽取数量限制
            exclude_document_ids: 排除的文档ID列表
            
        Returns:
            标准化的实体数据列表
        """
        # 统一使用同步方法
        return self._sample_entities_sync(entity_type, limit, exclude_document_ids)
    
    def _sample_entities_sync(
        self, 
        entity_type: str, 
        limit: int = 50, 
        exclude_document_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """同步版本的实体抽样"""
        logger.info(f"开始从Neo4j抽样 {entity_type} 类型实体，数量限制: {limit}")
        
        exclude_document_ids = exclude_document_ids or []
        
        with self.driver.session() as session:
            # 构建查询语句
            query = """
            MATCH (e:Entity)
            WHERE e.type = $entity_type
            """
            
            params = {"entity_type": entity_type, "limit": limit}
            
            if exclude_document_ids:
                query += """
                AND NOT e.document_id IN $exclude_document_ids
                """
                params["exclude_document_ids"] = exclude_document_ids
            
            query += """
            WITH e, rand() as random_value
            ORDER BY random_value
            LIMIT $limit
            RETURN COALESCE(e.node_id, elementId(e), toString(id(e))) as id,
                   e.name as name,
                   e.type as type,
                   e.type as entity_type,
                   COALESCE(e.description, '') as description,
                   COALESCE(e.confidence, 0.8) as confidence,
                   COALESCE(e.source_text, '') as source_text,
                   COALESCE(e.confidence, 0.8) as quality_score,
                   COALESCE(e.importance_score, 0.5) as importance_score,
                   e.document_id as document_postgresql_id,
                   e.chunk_id as chunk_neo4j_id,
                   COALESCE(e.aliases, []) as aliases,
                   e.node_id as node_id,
                   elementId(e) as element_id,
                   id(e) as identity
            """
            
            try:
                result = session.run(query, params)
                records = list(result)
                
                # 🔍 详细日志：Neo4j实体采样详情
                logger.info("=" * 80)
                logger.info(f"🔍 Neo4j实体采样详情 - {entity_type} 类型")
                logger.info("=" * 80)
                logger.info(f"查询语句: {query}")
                logger.info(f"查询参数: {params}")
                logger.info(f"采样结果数量: {len(records)}")
                
                sampled_entities = []
                for i, record in enumerate(records):
                    try:
                        record_dict = dict(record)
                        entity_data = self._build_entity_data_from_record(record_dict)
                        
                        # 🔍 详细日志：采样实体详情（前10个）
                        if i < 10:
                            logger.info(f"  采样实体 {i+1}:")
                            logger.info(f"    - 名称: {entity_data.get('name', 'N/A')}")
                            logger.info(f"    - 类型: {entity_data.get('type', 'N/A')}")
                            logger.info(f"    - 描述: {entity_data.get('description', 'N/A')[:50]}..." if entity_data.get('description') else "    - 描述: 无")
                            logger.info(f"    - ID: {entity_data.get('id', 'N/A')}")
                            logger.info(f"    - 文档ID: {entity_data.get('document_postgresql_id', 'N/A')}")
                            logger.info(f"    - 质量分数: {entity_data.get('quality_score', 'N/A')}")
                            logger.info(f"    - 置信度: {entity_data.get('confidence', 'N/A')}")
                            logger.info(f"    - 别名: {entity_data.get('aliases', [])}")
                        
                        sampled_entities.append(entity_data)
                    except Exception as e:
                        logger.warning(f"处理采样实体记录失败: {str(e)}")
                        continue
                
                if len(records) > 10:
                    logger.info(f"  ... 还有 {len(records) - 10} 个实体")
                
                # 🔍 详细日志：采样统计信息
                logger.info(f"📊 采样统计信息:")
                logger.info(f"  - 总采样数量: {len(sampled_entities)}")
                logger.info(f"  - 请求限制: {limit}")
                logger.info(f"  - 排除文档: {exclude_document_ids}")
                logger.info(f"  - 采样率: {len(sampled_entities)}/{len(records)} 成功处理")
                
                logger.info(f"成功抽样 {len(sampled_entities)} 个 {entity_type} 类型实体")
                logger.info("=" * 80)
                return sampled_entities
                
            except Exception as e:
                logger.error(f"实体抽样查询失败: {str(e)}")
                return []
    
    def get_entity_count_by_type(self, entity_type: str) -> int:
        """
        获取指定类型的实体总数
        
        Args:
            entity_type: 实体类型
            
        Returns:
            实体总数
        """
        # 统一使用同步方法
        return self._get_entity_count_sync(entity_type)
    
    def _get_entity_count_sync(self, entity_type: str) -> int:
        """同步版本的实体数量获取"""
        with self.driver.session() as session:
            query = """
            MATCH (e:Entity)
            WHERE e.type = $entity_type
            RETURN count(e) as total_count
            """
            
            try:
                result = session.run(query, {"entity_type": entity_type})
                record = result.single()
                count = record["total_count"] if record else 0
                
                logger.debug(f"{entity_type} 类型实体总数: {count}")
                return count
                
            except Exception as e:
                logger.error(f"获取实体数量失败: {str(e)}")
                return 0
    
    def _build_entity_data_from_record(self, neo4j_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化Neo4j实体数据为LLM处理格式
        
        Args:
            neo4j_record: Neo4j查询结果记录
            
        Returns:
            标准化的实体数据
        """
        # 处理属性字段 - 设为空字典，因为数据库中没有properties字段
        properties = {}
        
        # 处理别名字段
        aliases = neo4j_record.get("aliases") or []
        if isinstance(aliases, str):
            try:
                import json
                aliases = json.loads(aliases)
            except:
                aliases = []
        
        # 安全地获取数值字段
        def safe_float(value, default=0.0):
            try:
                return float(value) if value is not None else default
            except (ValueError, TypeError):
                return default
        
        return {
            "id": neo4j_record.get("id") or neo4j_record.get("node_id"),
            "name": neo4j_record.get("name") or "",
            "type": neo4j_record.get("type") or "unknown",
            "entity_type": neo4j_record.get("entity_type") or neo4j_record.get("type") or "unknown",
            "description": neo4j_record.get("description") or "",
            "properties": properties,
            "confidence": safe_float(neo4j_record.get("confidence"), 0.8),
            "source_text": neo4j_record.get("source_text") or "",
            "quality_score": safe_float(neo4j_record.get("quality_score"), 0.8),
            "importance_score": safe_float(neo4j_record.get("importance_score"), 0.5),
            "document_postgresql_id": neo4j_record.get("document_postgresql_id"),
            "chunk_neo4j_id": neo4j_record.get("chunk_neo4j_id"),
            "aliases": aliases,
            "node_id": neo4j_record.get("node_id") or neo4j_record.get("id"),
            "source": "neo4j_existing"  # 标记为已存在的实体
        }
    
    def get_entity_types_with_counts(self, min_count: int = 1) -> Dict[str, int]:
        """
        获取所有实体类型及其数量
        
        Args:
            min_count: 最小实体数量过滤
            
        Returns:
            {实体类型: 数量} 字典
        """
        with self.driver.session() as session:
            query = """
            MATCH (e:Entity)
            WHERE e.type IS NOT NULL
            RETURN e.type as entity_type, count(e) as count
            ORDER BY count DESC
            """
            
            try:
                result = session.run(query)
                records = list(result)
                
                type_counts = {}
                for record in records:
                    entity_type = record["entity_type"]
                    count = record["count"]
                    if count >= min_count:
                        type_counts[entity_type] = count
                
                logger.info(f"发现 {len(type_counts)} 种实体类型: {type_counts}")
                return type_counts
                
            except Exception as e:
                logger.error(f"获取实体类型统计失败: {str(e)}")
                return {}
    
    def close(self):
        """关闭Neo4j连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j实体抽样器连接已关闭")


# 全局实例
_entity_sampler_instance = None

def get_neo4j_entity_sampler() -> Neo4jEntitySampler:
    """获取Neo4j实体抽样器实例（单例模式）"""
    global _entity_sampler_instance
    if _entity_sampler_instance is None:
        _entity_sampler_instance = Neo4jEntitySampler()
    return _entity_sampler_instance