# -*- coding: utf-8 -*-
"""
Neo4j实体更新器服务
负责根据LLM分析结果更新Neo4j中的实体和关系
"""
import logging
from typing import List, Dict, Any, Optional, Set
from neo4j import GraphDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Neo4jEntityUpdater:
    """Neo4j实体更新器"""
    
    def __init__(self):
        """初始化Neo4j连接"""
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
        )
        logger.info("Neo4j实体更新器初始化完成（同步模式）")
    
    def apply_merge_operations(
        self,
        entities: List[Dict[str, Any]],
        merge_operations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        应用合并操作到Neo4j数据库
        
        Args:
            entities: 原始实体列表
            merge_operations: 合并操作列表
            
        Returns:
            更新结果统计
        """
        if not merge_operations:
            logger.info("没有合并操作需要执行")
            return {
                'merged_entities': 0,
                'deleted_entities': 0,
                'updated_relationships': 0,
                'errors': []
            }
        
        logger.info(f"开始应用 {len(merge_operations)} 个合并操作")
        
        results = {
            'merged_entities': 0,
            'deleted_entities': 0,
            'updated_relationships': 0,
            'errors': []
        }
        
        with self.driver.session() as session:
            for operation in merge_operations:
                try:
                    # 执行单个合并操作
                    operation_result = self._execute_single_merge(
                        session, entities, operation
                    )
                    
                    # 累加结果
                    results['merged_entities'] += operation_result.get('merged_entities', 0)
                    results['deleted_entities'] += operation_result.get('deleted_entities', 0)
                    results['updated_relationships'] += operation_result.get('updated_relationships', 0)
                    
                except Exception as e:
                    error_msg = f"合并操作失败: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
        
        logger.info(f"合并操作完成: {results}")
        return results
    
    def _execute_single_merge(
        self,
        session,
        entities: List[Dict[str, Any]],
        operation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行单个实体合并操作
        
        Args:
            session: Neo4j会话
            entities: 原始实体列表
            operation: 合并操作
            
        Returns:
            操作结果
        """
        primary_idx = operation['primary_entity_index']
        duplicate_indices = operation['duplicate_indices']
        
        # 获取主实体和重复实体
        primary_entity = entities[primary_idx]
        duplicate_entities = [entities[idx] for idx in duplicate_indices]
        
        logger.info(f"合并实体: {primary_entity.get('name')} <- {[e.get('name') for e in duplicate_entities]}")
        
        # 🔧 智能实体ID解析：区分Neo4j现有实体和新文档实体
        primary_entity_id = None
        duplicate_entity_ids = []
        
        # 处理主实体ID
        if primary_entity.get('source') == 'neo4j_existing':
            # Neo4j现有实体，直接使用其ID
            primary_entity_id = primary_entity.get('id') or primary_entity.get('node_id')
            if not primary_entity_id:
                # 如果没有直接ID，通过名称和类型查找
                primary_entity_id = self._find_entity_id_by_name_type(session, primary_entity)
        else:
            # 新文档实体，通过名称和类型查找对应的Neo4j实体
            primary_entity_id = self._find_entity_id_by_name_type(session, primary_entity)
        
        # 处理重复实体ID
        for duplicate_entity in duplicate_entities:
            if duplicate_entity.get('source') == 'neo4j_existing':
                # Neo4j现有实体，直接使用其ID
                dup_id = duplicate_entity.get('id') or duplicate_entity.get('node_id')
                if not dup_id:
                    # 如果没有直接ID，通过名称和类型查找
                    dup_id = self._find_entity_id_by_name_type(session, duplicate_entity)
                if dup_id and dup_id != primary_entity_id:
                    duplicate_entity_ids.append(dup_id)
            else:
                # 新文档实体，检查是否在Neo4j中有对应实体
                dup_id = self._find_entity_id_by_name_type(session, duplicate_entity)
                if dup_id and dup_id != primary_entity_id:
                    duplicate_entity_ids.append(dup_id)
        
        if not primary_entity_id:
            raise ValueError(f"主实体 {primary_entity.get('name')} ({primary_entity.get('type')}) 在Neo4j中未找到")
        
        # 🔧 特殊情况处理：如果主实体和重复实体指向同一个Neo4j实体，则只需更新，不需删除
        if not duplicate_entity_ids:
            logger.info(f"没有找到需要删除的重复实体，仅更新主实体信息")
            # 只更新主实体，不删除任何实体
            operation_with_entities = {**operation, 'entities': entities}
            self._update_primary_entity_by_id(session, primary_entity_id, operation_with_entities)
            return {'merged_entities': 1, 'deleted_entities': 0, 'updated_relationships': 0}
        
        # 🔧 去重：确保不会删除主实体自己
        duplicate_entity_ids = [dup_id for dup_id in duplicate_entity_ids if dup_id != primary_entity_id]
        
        if not duplicate_entity_ids:
            logger.info(f"经过去重后，没有需要删除的重复实体，仅更新主实体信息")
            operation_with_entities = {**operation, 'entities': entities}
            self._update_primary_entity_by_id(session, primary_entity_id, operation_with_entities)
            return {'merged_entities': 1, 'deleted_entities': 0, 'updated_relationships': 0}
        
        result = {
            'merged_entities': 0,
            'deleted_entities': 0,
            'updated_relationships': 0
        }
        
        # 1. 更新主实体信息（将entities列表添加到operation中）
        operation_with_entities = {**operation, 'entities': entities}
        self._update_primary_entity_by_id(session, primary_entity_id, operation_with_entities)
        result['merged_entities'] = 1
        
        # 2. 转移关系到主实体
        relationships_updated = self._transfer_relationships(
            session, primary_entity_id, duplicate_entity_ids
        )
        result['updated_relationships'] = relationships_updated
        
        # 3. 删除重复实体
        deleted_count = self._delete_duplicate_entities(session, duplicate_entity_ids)
        result['deleted_entities'] = deleted_count
        
        return result
    
    def _find_entity_id_by_name_type(self, session, entity: Dict[str, Any]) -> Optional[str]:
        """根据实体名称和类型查找Neo4j中的实际实体ID"""
        query = """
        MATCH (e:Entity)
        WHERE e.name = $name AND e.type = $type
        RETURN COALESCE(e.node_id, elementId(e), toString(id(e))) as entity_id
        LIMIT 1
        """
        
        params = {
            'name': entity.get('name'),
            'type': entity.get('type')
        }
        
        result = session.run(query, params)
        record = result.single()
        
        if record:
            return record['entity_id']
        else:
            logger.warning(f"实体 {entity.get('name')} ({entity.get('type')}) 在Neo4j中未找到")
            return None
    
    def _update_primary_entity_by_id(
        self,
        session,
        entity_id: str,
        operation: Dict[str, Any]
    ):
        """
        根据实际的entity_id更新主实体的信息
        
        Args:
            session: Neo4j会话
            entity_id: Neo4j中的实际实体ID
            operation: 合并操作信息
        """
        primary_idx = operation.get('primary_entity_index', 0)
        entities = operation.get('entities', [])
        
        if primary_idx < len(entities):
            primary_entity = entities[primary_idx]
            merged_name = operation.get('merged_name', primary_entity.get('name'))
            merged_description = operation.get('merged_description', primary_entity.get('description'))
        else:
            merged_name = operation.get('merged_name', '')
            merged_description = operation.get('merged_description', '')
        
        # 收集需要合并的别名
        duplicate_indices = operation.get('duplicate_indices', [])
        
        # 构建aliases列表
        new_aliases = []
        # 保持主实体原有的aliases
        if primary_idx < len(entities):
            primary_entity = entities[primary_idx]
            if primary_entity.get('aliases'):
                new_aliases.extend(primary_entity['aliases'])
        
        # 添加重复实体的名称作为别名
        for idx in duplicate_indices:
            if idx < len(entities):
                duplicate_entity = entities[idx]
                duplicate_name = duplicate_entity.get('name')
                if duplicate_name and duplicate_name != merged_name and duplicate_name not in new_aliases:
                    new_aliases.append(duplicate_name)
                
                # 添加重复实体的aliases
                if duplicate_entity.get('aliases'):
                    for alias in duplicate_entity['aliases']:
                        if alias != merged_name and alias not in new_aliases:
                            new_aliases.append(alias)
        
        # 构建更新查询
        query = """
        MATCH (e:Entity)
        WHERE e.node_id = $entity_id OR elementId(e) = $entity_id OR toString(id(e)) = $entity_id
        SET e.name = $merged_name,
            e.description = $merged_description,
            e.confidence = COALESCE(e.confidence, 0.0) + 0.1,
            e.importance_score = COALESCE(e.importance_score, 0.0) + 0.05,
            e.aliases = $new_aliases,
            e.updated_at = datetime(),
            e.merge_count = COALESCE(e.merge_count, 0) + $duplicate_count
        RETURN COALESCE(e.node_id, elementId(e), toString(id(e))) as updated_entity_id
        """
        
        params = {
            'entity_id': entity_id,
            'merged_name': merged_name,
            'merged_description': merged_description,
            'new_aliases': new_aliases,
            'duplicate_count': len(duplicate_indices)
        }
        
        result = session.run(query, params)
        updated_record = result.single()
        
        if updated_record:
            logger.debug(f"主实体 {entity_id} 更新成功，添加了 {len(new_aliases)} 个别名")
        else:
            raise ValueError(f"主实体 {entity_id} 未找到或更新失败")
    
    def _update_primary_entity(
        self,
        session,
        primary_entity: Dict[str, Any],
        operation: Dict[str, Any]
    ):
        """
        更新主实体的信息
        
        Args:
            session: Neo4j会话
            primary_entity: 主实体数据
            operation: 合并操作信息
        """
        entity_id = primary_entity.get('id') or primary_entity.get('node_id')
        merged_name = operation.get('merged_name', primary_entity.get('name'))
        merged_description = operation.get('merged_description', primary_entity.get('description'))
        
        # 收集需要合并的别名
        duplicate_indices = operation.get('duplicate_indices', [])
        entities = operation.get('entities', [])  # 从operation中获取实体列表
        
        # 构建aliases列表
        new_aliases = []
        # 保持主实体原有的aliases
        if primary_entity.get('aliases'):
            new_aliases.extend(primary_entity['aliases'])
        
        # 添加重复实体的名称作为别名
        for idx in duplicate_indices:
            if idx < len(entities):
                duplicate_entity = entities[idx]
                duplicate_name = duplicate_entity.get('name')
                if duplicate_name and duplicate_name != merged_name and duplicate_name not in new_aliases:
                    new_aliases.append(duplicate_name)
                
                # 添加重复实体的aliases
                if duplicate_entity.get('aliases'):
                    for alias in duplicate_entity['aliases']:
                        if alias != merged_name and alias not in new_aliases:
                            new_aliases.append(alias)
        
        # 构建更新查询（使用正确的属性名和更灵活的查询）
        query = """
        MATCH (e:Entity)
        WHERE e.node_id = $entity_id OR elementId(e) = $entity_id OR toString(id(e)) = $entity_id
        SET e.name = $merged_name,
            e.description = $merged_description,
            e.confidence = COALESCE(e.confidence, 0.0) + 0.1,
            e.importance_score = COALESCE(e.importance_score, 0.0) + 0.05,
            e.aliases = $new_aliases,
            e.updated_at = datetime(),
            e.merge_count = COALESCE(e.merge_count, 0) + $duplicate_count
        RETURN COALESCE(e.node_id, elementId(e), toString(id(e))) as updated_entity_id
        """
        
        params = {
            'entity_id': entity_id,
            'merged_name': merged_name,
            'merged_description': merged_description,
            'new_aliases': new_aliases,
            'duplicate_count': len(duplicate_indices)
        }
        
        result = session.run(query, params)
        updated_record = result.single()
        
        if updated_record:
            logger.debug(f"主实体 {entity_id} 更新成功，添加了 {len(new_aliases)} 个别名")
        else:
            raise ValueError(f"主实体 {entity_id} 未找到或更新失败")
    
    def _transfer_relationships(
        self,
        session,
        primary_entity_id: str,
        duplicate_entity_ids: List[str]
    ) -> int:
        """
        将重复实体的关系转移到主实体
        
        Args:
            session: Neo4j会话
            primary_entity_id: 主实体ID
            duplicate_entity_ids: 重复实体ID列表
            
        Returns:
            更新的关系数量
        """
        if not duplicate_entity_ids:
            return 0
        
        total_updated = 0
        
        # 转移出向关系（重复实体作为源实体的关系）
        outgoing_query = """
        MATCH (duplicate:Entity)-[r]->(target:Entity)
        WHERE (duplicate.node_id IN $duplicate_entity_ids OR elementId(duplicate) IN $duplicate_entity_ids OR toString(id(duplicate)) IN $duplicate_entity_ids)
        AND (target.node_id <> $primary_entity_id AND elementId(target) <> $primary_entity_id AND toString(id(target)) <> $primary_entity_id)
        MATCH (primary:Entity)
        WHERE primary.node_id = $primary_entity_id OR elementId(primary) = $primary_entity_id OR toString(id(primary)) = $primary_entity_id
        
        // 检查是否已存在相同的关系
        OPTIONAL MATCH (primary)-[existing_rel:RELATED]->(target)
        WHERE type(r) = 'RELATED' OR type(existing_rel) = 'RELATED'
        
        WITH duplicate, r, target, primary, existing_rel
        WHERE existing_rel IS NULL
        
        // 创建新关系并删除旧关系
        CREATE (primary)-[new_rel:RELATED]->(target)
        SET new_rel = properties(r)
        DELETE r
        
        RETURN count(new_rel) as transferred_count
        """
        
        result = session.run(outgoing_query, {
            'duplicate_entity_ids': duplicate_entity_ids,
            'primary_entity_id': primary_entity_id
        })
        
        outgoing_record = result.single()
        outgoing_count = outgoing_record['transferred_count'] if outgoing_record else 0
        total_updated += outgoing_count
        
        # 转移入向关系（重复实体作为目标实体的关系）  
        incoming_query = """
        MATCH (source:Entity)-[r]->(duplicate:Entity)
        WHERE (duplicate.node_id IN $duplicate_entity_ids OR elementId(duplicate) IN $duplicate_entity_ids OR toString(id(duplicate)) IN $duplicate_entity_ids)
        AND (source.node_id <> $primary_entity_id AND elementId(source) <> $primary_entity_id AND toString(id(source)) <> $primary_entity_id)
        MATCH (primary:Entity)
        WHERE primary.node_id = $primary_entity_id OR elementId(primary) = $primary_entity_id OR toString(id(primary)) = $primary_entity_id
        
        // 检查是否已存在相同的关系
        OPTIONAL MATCH (source)-[existing_rel:RELATED]->(primary)
        WHERE type(r) = 'RELATED' OR type(existing_rel) = 'RELATED'
        
        WITH source, r, duplicate, primary, existing_rel
        WHERE existing_rel IS NULL
        
        // 创建新关系并删除旧关系
        CREATE (source)-[new_rel:RELATED]->(primary)
        SET new_rel = properties(r)
        DELETE r
        
        RETURN count(new_rel) as transferred_count
        """
        
        result = session.run(incoming_query, {
            'duplicate_entity_ids': duplicate_entity_ids,
            'primary_entity_id': primary_entity_id
        })
        
        incoming_record = result.single()
        incoming_count = incoming_record['transferred_count'] if incoming_record else 0
        total_updated += incoming_count
        
        logger.debug(f"关系转移完成: 出向关系 {outgoing_count}, 入向关系 {incoming_count}")
        
        return total_updated
    
    def _delete_duplicate_entities(
        self,
        session,
        duplicate_entity_ids: List[str]
    ) -> int:
        """
        删除重复实体
        
        Args:
            session: Neo4j会话
            duplicate_entity_ids: 重复实体ID列表
            
        Returns:
            删除的实体数量
        """
        if not duplicate_entity_ids:
            return 0
        
        # 首先删除剩余的关系（如果有的话）
        delete_relationships_query = """
        MATCH (e:Entity)-[r]-(other)
        WHERE e.node_id IN $duplicate_entity_ids OR elementId(e) IN $duplicate_entity_ids OR toString(id(e)) IN $duplicate_entity_ids
        DELETE r
        """
        
        session.run(delete_relationships_query, {'duplicate_entity_ids': duplicate_entity_ids})
        
        # 然后删除实体
        delete_entities_query = """
        MATCH (e:Entity)
        WHERE e.node_id IN $duplicate_entity_ids OR elementId(e) IN $duplicate_entity_ids OR toString(id(e)) IN $duplicate_entity_ids
        DELETE e
        RETURN count(e) as deleted_count
        """
        
        result = session.run(delete_entities_query, {'duplicate_entity_ids': duplicate_entity_ids})
        record = result.single()
        deleted_count = record['deleted_count'] if record else 0
        
        logger.debug(f"删除了 {deleted_count} 个重复实体")
        
        return deleted_count
    
    def get_entity_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取实体信息
        
        Args:
            entity_id: 实体ID
            
        Returns:
            实体信息或None
        """
        with self.driver.session() as session:
            query = """
            MATCH (e:Entity)
            WHERE e.node_id = $entity_id OR elementId(e) = $entity_id OR toString(id(e)) = $entity_id
            RETURN COALESCE(e.node_id, elementId(e), toString(id(e))) as id,
                   e.name as name,
                   e.type as type,
                   e.description as description,
                   COALESCE(e.properties, {}) as properties,
                   COALESCE(e.confidence, 0.8) as quality_score,
                   COALESCE(e.importance_score, 0.5) as importance_score,
                   COALESCE(e.aliases, []) as aliases
            """
            
            result = session.run(query, {'entity_id': entity_id})
            record = result.single()
            
            if record:
                return dict(record)
            else:
                return None
    
    def update_entity_quality_scores(
        self,
        entity_updates: List[Dict[str, Any]]
    ) -> int:
        """
        批量更新实体质量分数
        
        Args:
            entity_updates: 更新列表，每项包含entity_id和新的质量分数
            
        Returns:
            更新的实体数量
        """
        if not entity_updates:
            return 0
        
        with self.driver.session() as session:
            query = """
            UNWIND $updates as update
            MATCH (e:Entity)
            WHERE e.node_id = update.entity_id OR elementId(e) = update.entity_id OR toString(id(e)) = update.entity_id
            SET e.confidence = update.quality_score,
                e.importance_score = COALESCE(update.importance_score, e.importance_score),
                e.updated_at = datetime()
            RETURN count(e) as updated_count
            """
            
            result = session.run(query, {'updates': entity_updates})
            record = result.single()
            updated_count = record['updated_count'] if record else 0
            
            logger.info(f"批量更新了 {updated_count} 个实体的质量分数")
            
            return updated_count
    
    def get_entity_statistics(self) -> Dict[str, Any]:
        """
        获取实体统计信息
        
        Returns:
            统计信息字典
        """
        with self.driver.session() as session:
            query = """
            MATCH (e:Entity)
            RETURN count(e) as total_entities,
                   count(DISTINCT e.type) as unique_types,
                   avg(e.confidence) as avg_quality_score,
                   avg(e.importance_score) as avg_importance_score,
                   count(CASE WHEN e.merge_count > 0 THEN 1 END) as merged_entities
            """
            
            result = session.run(query)
            record = result.single()
            
            if record:
                return {
                    'total_entities': record['total_entities'],
                    'unique_types': record['unique_types'],
                    'avg_quality_score': float(record['avg_quality_score'] or 0.0),
                    'avg_importance_score': float(record['avg_importance_score'] or 0.0),
                    'merged_entities': record['merged_entities']
                }
            else:
                return {
                    'total_entities': 0,
                    'unique_types': 0,
                    'avg_quality_score': 0.0,
                    'avg_importance_score': 0.0,
                    'merged_entities': 0
                }
    
    def close(self):
        """关闭Neo4j连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j实体更新器连接已关闭")


# 全局实例
_entity_updater_instance = None

def get_neo4j_entity_updater() -> Neo4jEntityUpdater:
    """获取Neo4j实体更新器实例（单例模式）"""
    global _entity_updater_instance
    if _entity_updater_instance is None:
        _entity_updater_instance = Neo4jEntityUpdater()
    return _entity_updater_instance