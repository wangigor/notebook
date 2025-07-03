import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from contextlib import contextmanager
from neo4j import GraphDatabase
from app.core.config import settings

logger = logging.getLogger(__name__)

class Neo4jService:
    """Neo4j数据访问层服务"""
    
    def __init__(self):
        """初始化Neo4j服务"""
        self.driver = None
        self._connect()
    
    def _connect(self):
        """建立与Neo4j数据库的连接"""
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
            )
            # 验证连接
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"成功连接到Neo4j数据库: {settings.NEO4J_URI}")
        except Exception as e:
            logger.error(f"连接Neo4j数据库失败: {str(e)}")
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j数据库连接已关闭")
    
    @contextmanager
    def get_session(self):
        """获取数据库会话的上下文管理器"""
        session = self.driver.session()
        try:
            yield session
        except Exception as e:
            logger.error(f"Neo4j会话操作失败: {str(e)}")
            raise
        finally:
            session.close()
    
    @contextmanager
    def get_transaction(self):
        """获取事务的上下文管理器"""
        with self.get_session() as session:
            tx = session.begin_transaction()
            try:
                yield tx
                tx.commit()
            except Exception as e:
                tx.rollback()
                logger.error(f"Neo4j事务执行失败，已回滚: {str(e)}")
                raise
    
    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行Cypher查询
        
        Args:
            query: Cypher查询语句
            parameters: 查询参数
            
        Returns:
            查询结果列表
        """
        try:
            with self.get_session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"执行Cypher查询失败: {query}, 参数: {parameters}, 错误: {str(e)}")
            raise
    
    def execute_write_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行写入查询（在事务中）
        
        Args:
            query: Cypher查询语句
            parameters: 查询参数
            
        Returns:
            查询结果列表
        """
        try:
            with self.get_transaction() as tx:
                result = tx.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"执行写入查询失败: {query}, 参数: {parameters}, 错误: {str(e)}")
            raise
    
    def create_node(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """创建节点
        
        Args:
            label: 节点标签
            properties: 节点属性
            
        Returns:
            创建的节点信息
        """
        query = f"CREATE (n:{label} $properties) RETURN n"
        result = self.execute_write_query(query, {"properties": properties})
        return result[0]["n"] if result else None
    
    def get_node_by_id(self, node_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取节点
        
        Args:
            node_id: 节点ID
            
        Returns:
            节点信息
        """
        query = "MATCH (n) WHERE ID(n) = $node_id RETURN n"
        result = self.execute_query(query, {"node_id": node_id})
        return result[0]["n"] if result else None
    
    def get_nodes_by_label(self, label: str, limit: int = 100) -> List[Dict[str, Any]]:
        """根据标签获取节点
        
        Args:
            label: 节点标签
            limit: 返回节点数量限制
            
        Returns:
            节点列表
        """
        query = f"MATCH (n:{label}) RETURN n LIMIT $limit"
        result = self.execute_query(query, {"limit": limit})
        return [record["n"] for record in result]
    
    def update_node_properties(self, node_id: int, properties: Dict[str, Any]) -> bool:
        """更新节点属性
        
        Args:
            node_id: 节点ID
            properties: 要更新的属性
            
        Returns:
            更新是否成功
        """
        query = "MATCH (n) WHERE ID(n) = $node_id SET n += $properties RETURN n"
        result = self.execute_write_query(query, {"node_id": node_id, "properties": properties})
        return len(result) > 0
    
    def delete_node(self, node_id: int) -> bool:
        """删除节点
        
        Args:
            node_id: 节点ID
            
        Returns:
            删除是否成功
        """
        query = "MATCH (n) WHERE ID(n) = $node_id DETACH DELETE n"
        self.execute_write_query(query, {"node_id": node_id})
        return True
    
    def create_relationship(self, from_node_id: int, to_node_id: int, 
                          relationship_type: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建关系
        
        Args:
            from_node_id: 起始节点ID
            to_node_id: 目标节点ID
            relationship_type: 关系类型
            properties: 关系属性
            
        Returns:
            创建的关系信息
        """
        properties = properties or {}
        query = f"""
        MATCH (a), (b) 
        WHERE ID(a) = $from_id AND ID(b) = $to_id 
        CREATE (a)-[r:{relationship_type} $properties]->(b) 
        RETURN r
        """
        result = self.execute_write_query(query, {
            "from_id": from_node_id,
            "to_id": to_node_id,
            "properties": properties
        })
        return result[0]["r"] if result else None
    
    def get_relationships(self, node_id: int, direction: str = "both") -> List[Dict[str, Any]]:
        """获取节点的关系
        
        Args:
            node_id: 节点ID
            direction: 关系方向 ("incoming", "outgoing", "both")
            
        Returns:
            关系列表
        """
        if direction == "incoming":
            query = "MATCH ()-[r]->(n) WHERE ID(n) = $node_id RETURN r"
        elif direction == "outgoing":
            query = "MATCH (n)-[r]->() WHERE ID(n) = $node_id RETURN r"
        else:  # both
            query = "MATCH (n)-[r]-() WHERE ID(n) = $node_id RETURN r"
        
        result = self.execute_query(query, {"node_id": node_id})
        return [record["r"] for record in result]
    
    def delete_relationship(self, relationship_id: int) -> bool:
        """删除关系
        
        Args:
            relationship_id: 关系ID
            
        Returns:
            删除是否成功
        """
        query = "MATCH ()-[r]-() WHERE ID(r) = $rel_id DELETE r"
        self.execute_write_query(query, {"rel_id": relationship_id})
        return True
    
    def batch_create_nodes(self, nodes_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量创建节点
        
        Args:
            nodes_data: 节点数据列表，每个元素包含label和properties
            
        Returns:
            创建的节点列表
        """
        query = """
        UNWIND $nodes AS nodeData
        CALL {
            WITH nodeData
            CALL apoc.create.node([nodeData.label], nodeData.properties) YIELD node
            RETURN node
        }
        RETURN collect(node) as nodes
        """
        
        # 简化版本（不依赖APOC）
        results = []
        with self.get_transaction() as tx:
            for node_data in nodes_data:
                label = node_data.get("label", "Node")
                properties = node_data.get("properties", {})
                query = f"CREATE (n:{label} $properties) RETURN n"
                result = tx.run(query, {"properties": properties})
                node = result.single()["n"]
                results.append(node)
        
        return results
    
    def batch_create_relationships(self, relationships_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量创建关系
        
        Args:
            relationships_data: 关系数据列表
            
        Returns:
            创建的关系列表
        """
        results = []
        with self.get_transaction() as tx:
            for rel_data in relationships_data:
                from_id = rel_data["from_node_id"]
                to_id = rel_data["to_node_id"]
                rel_type = rel_data["relationship_type"]
                properties = rel_data.get("properties", {})
                
                query = f"""
                MATCH (a), (b) 
                WHERE ID(a) = $from_id AND ID(b) = $to_id 
                CREATE (a)-[r:{rel_type} $properties]->(b) 
                RETURN r
                """
                result = tx.run(query, {
                    "from_id": from_id,
                    "to_id": to_id,
                    "properties": properties
                })
                if result.peek():
                    rel = result.single()["r"]
                    results.append(rel)
        
        return results
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息
        
        Returns:
            数据库统计信息
        """
        queries = {
            "node_count": "MATCH (n) RETURN count(n) as count",
            "relationship_count": "MATCH ()-[r]-() RETURN count(r) as count",
            "labels": "CALL db.labels() YIELD label RETURN collect(label) as labels",
            "relationship_types": "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as types"
        }
        
        info = {}
        try:
            for key, query in queries.items():
                result = self.execute_query(query)
                if key in ["node_count", "relationship_count"]:
                    info[key] = result[0]["count"] if result else 0
                else:
                    info[key] = result[0][key.replace("_", "")] if result else []
        except Exception as e:
            logger.error(f"获取数据库信息失败: {str(e)}")
            info = {"error": str(e)}
        
        return info
    
    def clear_database(self, confirm: bool = False) -> bool:
        """清空数据库（谨慎使用）
        
        Args:
            confirm: 确认标志
            
        Returns:
            操作是否成功
        """
        if not confirm:
            raise ValueError("必须明确确认才能清空数据库")
        
        try:
            query = "MATCH (n) DETACH DELETE n"
            self.execute_write_query(query)
            logger.warning("数据库已清空")
            return True
        except Exception as e:
            logger.error(f"清空数据库失败: {str(e)}")
            return False
    
    def create_document_node(self, postgresql_id: int, name: str, file_type: str, 
                            file_size: int, created_at: datetime) -> str:
        """创建Document节点
        
        Args:
            postgresql_id: PostgreSQL文档ID
            name: 文档名称
            file_type: 文件类型
            file_size: 文件大小
            created_at: 创建时间
            
        Returns:
            Neo4j节点ID
        """
        query = """
        CREATE (d:Document {
            postgresql_id: $postgresql_id,
            name: $name,
            file_type: $file_type,
            file_size: $file_size,
            created_at: $created_at,
            status: 'completed',
            node_count: 0,
            relationship_count: 0,
            processing_time: null
        })
        RETURN elementId(d) as node_id
        """
        
        result = self.execute_write_query(query, {
            "postgresql_id": postgresql_id,
            "name": name,
            "file_type": file_type,
            "file_size": file_size,
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at
        })
        
        if result:
            logger.info(f"Document节点创建成功: postgresql_id={postgresql_id}, name={name}")
            return result[0]["node_id"]
        else:
            raise Exception("Failed to create document node")
    
    def batch_create_chunk_nodes(self, chunks_data: List[Dict[str, Any]]) -> List[str]:
        """批量创建Chunk节点
        
        Args:
            chunks_data: 分块数据列表
            
        Returns:
            Neo4j节点ID列表
        """
        if not chunks_data:
            logger.warning("没有chunk数据需要创建")
            return []
            
        query = """
        UNWIND $chunks AS chunkData
        CREATE (c:Chunk {
            chunk_id: chunkData.chunk_id,
            content: chunkData.content,
            position: chunkData.position,
            chunk_index: chunkData.chunk_index,
            start_char: chunkData.start_char,
            end_char: chunkData.end_char,
            content_length: chunkData.content_length,
            word_count: chunkData.word_count,
            paragraph_count: chunkData.paragraph_count,
            chunk_type: chunkData.chunk_type,
            created_at: chunkData.created_at,
            postgresql_document_id: chunkData.postgresql_document_id
        })
        SET c.embedding = CASE WHEN chunkData.embedding IS NOT NULL THEN chunkData.embedding ELSE null END,
            c.vector_dimension = CASE WHEN chunkData.vector_dimension IS NOT NULL THEN chunkData.vector_dimension ELSE null END
        RETURN elementId(c) as node_id
        """
        
        try:
            result = self.execute_write_query(query, {"chunks": chunks_data})
            
            if result:
                node_ids = [record["node_id"] for record in result]
                logger.info(f"批量创建Chunk节点成功: {len(node_ids)} 个节点")
                return node_ids
            else:
                logger.warning("批量创建Chunk节点返回空结果")
                return []
                
        except Exception as e:
            logger.error(f"批量创建Chunk节点失败: {str(e)}")
            raise
    
    def create_chunk_document_relationships(self, chunk_neo4j_ids: List[str], 
                                          document_neo4j_id: str) -> int:
        """创建Chunk与Document的PART_OF关系
        
        Args:
            chunk_neo4j_ids: Chunk节点ID列表
            document_neo4j_id: Document节点ID
            
        Returns:
            创建的关系数量
        """
        query = """
        UNWIND $chunk_ids AS chunk_id
        MATCH (c:Chunk) WHERE elementId(c) = chunk_id
        MATCH (d:Document) WHERE elementId(d) = $document_id
        CREATE (c)-[:PART_OF]->(d)
        RETURN count(*) as relationship_count
        """
        
        result = self.execute_write_query(query, {
            "chunk_ids": chunk_neo4j_ids,
            "document_id": document_neo4j_id
        })
        
        if result:
            return result[0]["relationship_count"]
        else:
            return 0
    
    def create_chunk_entity_relationships(self, chunk_entity_pairs: List[Dict[str, str]]) -> int:
        """创建Chunk和Entity之间的HAS_ENTITY关系
        
        Args:
            chunk_entity_pairs: 包含chunk_id和entity_id的字典列表
            
        Returns:
            创建的关系数量
        """
        logger.info(f"准备创建 {len(chunk_entity_pairs)} 个Chunk-Entity关系")
        
        query = """
        UNWIND $pairs AS pair
        MATCH (c:Chunk {node_id: pair.chunk_id})
        MATCH (e:Entity {node_id: pair.entity_id})
        MERGE (c)-[:HAS_ENTITY]->(e)
        """
        
        try:
            self.execute_write_query(query, {"pairs": chunk_entity_pairs})
            logger.info(f"成功创建 {len(chunk_entity_pairs)} 个Chunk-Entity关系")
            return len(chunk_entity_pairs)
        except Exception as e:
            logger.error(f"创建Chunk-Entity关系失败: {str(e)}")
            return 0
    
    def create_document_chunk_first_relationships(self, document_first_chunk_pairs: List[Dict[str, str]]) -> int:
        """创建Document和第一个Chunk之间的FIRST_CHUNK关系
        
        Args:
            document_first_chunk_pairs: 包含document_id和first_chunk_id的字典列表
            
        Returns:
            创建的关系数量
        """
        logger.info(f"准备创建 {len(document_first_chunk_pairs)} 个Document-FIRST_CHUNK关系")
        
        query = """
        UNWIND $pairs AS pair
        MATCH (d:Document {node_id: pair.document_id})
        MATCH (c:Chunk {node_id: pair.first_chunk_id})
        MERGE (d)-[:FIRST_CHUNK]->(c)
        """
        
        try:
            self.execute_write_query(query, {"pairs": document_first_chunk_pairs})
            logger.info(f"成功创建 {len(document_first_chunk_pairs)} 个Document-FIRST_CHUNK关系")
            return len(document_first_chunk_pairs)
        except Exception as e:
            logger.error(f"创建Document-FIRST_CHUNK关系失败: {str(e)}")
            return 0
    
    def create_chunk_sequence_relationships(self, chunk_sequence_pairs: List[Dict[str, str]]) -> int:
        """创建Chunk之间的NEXT_CHUNK关系
        
        Args:
            chunk_sequence_pairs: 包含current_chunk_id和next_chunk_id的字典列表
            
        Returns:
            创建的关系数量
        """
        logger.info(f"准备创建 {len(chunk_sequence_pairs)} 个Chunk-NEXT_CHUNK关系")
        
        query = """
        UNWIND $pairs AS pair
        MATCH (c1:Chunk {node_id: pair.current_chunk_id})
        MATCH (c2:Chunk {node_id: pair.next_chunk_id})
        MERGE (c1)-[:NEXT_CHUNK]->(c2)
        """
        
        try:
            self.execute_write_query(query, {"pairs": chunk_sequence_pairs})
            logger.info(f"成功创建 {len(chunk_sequence_pairs)} 个Chunk-NEXT_CHUNK关系")
            return len(chunk_sequence_pairs)
        except Exception as e:
            logger.error(f"创建Chunk-NEXT_CHUNK关系失败: {str(e)}")
            return 0
    
    def cleanup_document_graph(self, document_neo4j_id: str) -> bool:
        """清理与特定文档相关的所有图数据
        
        Args:
            document_neo4j_id: Document节点ID
            
        Returns:
            是否成功清理
        """
        try:
            query = """
            MATCH (d:Document) WHERE elementId(d) = $document_id
            OPTIONAL MATCH (d)<-[:PART_OF]-(c:Chunk)
            OPTIONAL MATCH (c)-[:HAS_ENTITY]->(e)
            DETACH DELETE d, c, e
            RETURN count(*) as deleted_count
            """
            
            result = self.execute_write_query(query, {"document_id": document_neo4j_id})
            logger.info(f"清理文档图数据完成: {result[0]['deleted_count'] if result else 0} 个节点")
            return True
        except Exception as e:
            logger.error(f"清理文档图数据失败: {str(e)}")
            return False
    
    async def store_graph_data(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """存储完整的图谱数据到Neo4j
        
        Args:
            graph_data: 图谱数据，包含nodes和edges
            
        Returns:
            存储结果统计
        """
        logger.info("开始存储图谱数据到Neo4j")
        
        result = {
            "success": True,
            "nodes_created": 0,
            "relationships_created": 0,
            "chunk_entity_relationships_created": 0,
            "errors": []
        }
        
        try:
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])
            
            logger.info(f"准备存储: {len(nodes)} 个节点, {len(edges)} 条关系")
            
            # 第一阶段：存储所有节点
            if nodes:
                logger.info("第一阶段：开始存储所有节点")
                node_result = await self._batch_store_nodes(nodes)
                result["nodes_created"] = node_result["created_count"]
                result["errors"].extend(node_result.get("errors", []))
                
                if result["nodes_created"] + node_result["matched_count"] == 0:
                    logger.error("节点存储失败，跳过关系存储")
                    result["success"] = False
                    return result
                
                logger.info(f"节点存储完成: {result['nodes_created']} 个节点")
            
            # 第二阶段：存储所有关系
            if edges and result["nodes_created"] > 0:
                logger.info("第二阶段：开始存储所有关系")
                
                # 分离不同类型的关系
                chunk_entity_relationships = []
                first_chunk_relationships = []
                next_chunk_relationships = []
                other_relationships = []
                
                for edge in edges:
                    edge_type = edge.get("type")
                    if edge_type == "HAS_ENTITY":
                        chunk_entity_relationships.append(edge)
                    elif edge_type == "FIRST_CHUNK":
                        first_chunk_relationships.append(edge)
                    elif edge_type == "NEXT_CHUNK":
                        next_chunk_relationships.append(edge)
                    else:
                        other_relationships.append(edge)
                
                logger.info(f"关系分类: {len(chunk_entity_relationships)} 个HAS_ENTITY, {len(first_chunk_relationships)} 个FIRST_CHUNK, {len(next_chunk_relationships)} 个NEXT_CHUNK, {len(other_relationships)} 个其他关系")
                
                # 先存储其他关系
                if other_relationships:
                    edge_result = await self._batch_store_relationships(other_relationships)
                    result["relationships_created"] = edge_result["created_count"]
                    result["errors"].extend(edge_result.get("errors", []))
                
                # 存储FIRST_CHUNK关系
                if first_chunk_relationships:
                    logger.info(f"开始存储 {len(first_chunk_relationships)} 个Document-FIRST_CHUNK关系")
                    first_chunk_pairs = []
                    for rel in first_chunk_relationships:
                        first_chunk_pairs.append({
                            "document_id": rel["source_id"],
                            "first_chunk_id": rel["target_id"]
                        })
                    
                    first_chunk_count = self.create_document_chunk_first_relationships(first_chunk_pairs)
                    result["relationships_created"] += first_chunk_count
                
                # 存储NEXT_CHUNK关系
                if next_chunk_relationships:
                    logger.info(f"开始存储 {len(next_chunk_relationships)} 个Chunk-NEXT_CHUNK关系")
                    next_chunk_pairs = []
                    for rel in next_chunk_relationships:
                        next_chunk_pairs.append({
                            "current_chunk_id": rel["source_id"],
                            "next_chunk_id": rel["target_id"]
                        })
                    
                    next_chunk_count = self.create_chunk_sequence_relationships(next_chunk_pairs)
                    result["relationships_created"] += next_chunk_count
                
                # 存储chunk-entity关系（使用专门的方法）
                if chunk_entity_relationships:
                    logger.info(f"开始存储 {len(chunk_entity_relationships)} 个Chunk-Entity关系")
                    chunk_entity_pairs = []
                    for rel in chunk_entity_relationships:
                        chunk_entity_pairs.append({
                            "chunk_id": rel["source_id"],
                            "entity_id": rel["target_id"]
                        })
                    
                    chunk_entity_count = self.create_chunk_entity_relationships(chunk_entity_pairs)
                    result["chunk_entity_relationships_created"] = chunk_entity_count
                    result["relationships_created"] += chunk_entity_count
                
                logger.info(f"关系存储完成: {result['relationships_created']} 条关系")
            
            # 检查结果
            if result["errors"]:
                result["success"] = False
                logger.warning(f"图谱存储完成但有错误: {len(result['errors'])} 个错误")
            else:
                logger.info(f"图谱存储成功: {result['nodes_created']} 个节点, {result['relationships_created']} 条关系 (包含 {result['chunk_entity_relationships_created']} 个Chunk-Entity关系)")
            
        except Exception as e:
            logger.error(f"存储图谱数据失败: {str(e)}")
            result["success"] = False
            result["errors"].append(str(e))
        
        return result
    
    async def _batch_store_nodes(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量存储节点
        
        Args:
            nodes: 节点列表
            
        Returns:
            存储结果
        """
        logger.info(f"开始批量存储 {len(nodes)} 个节点")
        
        result = {
            "created_count": 0,
            "matched_count": 0,
            "errors": []
        }
        
        try:
            # 使用MERGE确保节点唯一性，并使用ON CREATE和ON MATCH更新属性
            query = """
            UNWIND $nodes AS nodeData
            MERGE (n {node_id: nodeData.id})
            ON CREATE SET 
                n += nodeData.properties,
                n.node_id = nodeData.id,
                n.name = nodeData.name,
                n.type = nodeData.type,
                n.description = nodeData.description,
                n.created_at = apoc.date.toISO8601(timestamp(), 'ms'),
                n.updated_at = apoc.date.toISO8601(timestamp(), 'ms')
            ON MATCH SET
                n += nodeData.properties,
                n.node_id = nodeData.id,
                n.name = nodeData.name,
                n.type = nodeData.type,
                n.description = nodeData.description,
                n.updated_at = apoc.date.toISO8601(timestamp(), 'ms')
            WITH n, nodeData,
                 CASE WHEN n.created_at = n.updated_at THEN 1 ELSE 0 END AS wasCreated
            CALL apoc.create.addLabels(n, nodeData.labels) YIELD node
            RETURN sum(wasCreated) as created_count, count(n) - sum(wasCreated) as matched_count
            """
            
            # 准备节点数据
            batch_data = []
            for node in nodes:
                properties = node.get("properties", {})
                properties.pop("created_at", None) # 由数据库生成
                properties.pop("updated_at", None)
                
                node_data = {
                    "id": node.get("id"),
                    "name": node.get("name", ""),
                    "type": node.get("type", ""),
                    "description": node.get("description", ""),
                    "labels": node.get("labels", [node.get("type", "Entity")]),
                    "properties": properties
                }
                batch_data.append(node_data)
            
            # 执行批量合并/创建
            query_result = self.execute_write_query(query, {"nodes": batch_data})
            
            if query_result:
                result["created_count"] = query_result[0].get("created_count", 0)
                result["matched_count"] = query_result[0].get("matched_count", 0)
            
            total_processed = result['created_count'] + result['matched_count']
            logger.info(f"节点批量存储完成: {total_processed} 个处理, {result['created_count']} 个创建, {result['matched_count']} 个匹配")

        except Exception as e:
            logger.error(f"批量存储节点失败: {str(e)}")
            result["errors"].append(str(e))
            
        return result
    
    async def _batch_store_relationships(self, edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量存储关系
        
        Args:
            edges: 边列表
            
        Returns:
            存储结果
        """
        logger.info(f"开始批量存储 {len(edges)} 条关系")
        
        result = {
            "created_count": 0,
            "matched_count": 0,
            "errors": []
        }
        
        if not edges:
            return result
        
        try:
            # 使用apoc.merge.relationship确保关系唯一性，添加节点存在性检查
            query = """
            UNWIND $edges AS edgeData
            MATCH (source {node_id: edgeData.source_id})
            MATCH (target {node_id: edgeData.target_id})
            WITH source, target, edgeData
            WHERE source IS NOT NULL AND target IS NOT NULL
            CALL apoc.merge.relationship(
                source, 
                edgeData.type, 
                {id: edgeData.id}, 
                edgeData.properties, 
                target
            ) YIELD rel
            RETURN count(rel) AS relationships_created, 
                   count(edgeData) AS relationships_attempted,
                   count(source) AS sources_found,
                   count(target) AS targets_found
            """
            
            # 准备关系数据
            batch_data = []
            for edge in edges:
                properties = edge.get("properties", {})
                properties["id"] = edge.get("id")
                properties["source_name"] = edge.get("source_name")
                properties["target_name"] = edge.get("target_name")
                properties["type"] = edge.get("type")
                properties["description"] = edge.get("description")
                
                batch_data.append({
                    "id": edge.get("id"),
                    "source_id": edge.get("source_id"),
                    "target_id": edge.get("target_id"),
                    "type": edge.get("type"),
                    "properties": properties
                })

            query_result = self.execute_write_query(query, {"edges": batch_data})
            
            if query_result:
                # 获取详细的关系创建统计信息
                relationships_created = query_result[0].get("relationships_created", 0)
                relationships_attempted = query_result[0].get("relationships_attempted", 0)
                sources_found = query_result[0].get("sources_found", 0)
                targets_found = query_result[0].get("targets_found", 0)
                
                result["created_count"] = relationships_created
                
                # 详细日志记录
                logger.info(f"关系批量存储完成: {relationships_created}/{relationships_attempted} 条关系成功创建")
                if relationships_created < relationships_attempted:
                    missing_sources = relationships_attempted - sources_found
                    missing_targets = relationships_attempted - targets_found
                    if missing_sources > 0:
                        logger.warning(f"缺少源节点: {missing_sources} 个")
                    if missing_targets > 0:
                        logger.warning(f"缺少目标节点: {missing_targets} 个")
            
        except Exception as e:
            logger.error(f"批量存储关系失败: {str(e)}")
            result["errors"].append(str(e))
            
        return result
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """获取图谱的统计信息
        
        Returns:
            统计信息
        """
        try:
            # 获取节点统计
            node_query = """
            MATCH (n)
            WHERE n.type IS NOT NULL
            WITH n.type as node_type, count(n) as count
            RETURN node_type, count
            ORDER BY count DESC
            """
            node_stats = self.execute_query(node_query)
            
            # 获取关系统计
            rel_query = """
            MATCH ()-[r]->()
            WHERE r.relationship_type IS NOT NULL
            WITH r.relationship_type as rel_type, count(r) as count
            RETURN rel_type, count
            ORDER BY count DESC
            """
            rel_stats = self.execute_query(rel_query)
            
            # 获取总体统计
            total_query = """
            MATCH (n)
            OPTIONAL MATCH ()-[r]->()
            RETURN count(DISTINCT n) as total_nodes, count(r) as total_relationships
            """
            total_stats = self.execute_query(total_query)[0]
            
            return {
                "total_nodes": total_stats["total_nodes"],
                "total_relationships": total_stats["total_relationships"],
                "node_types": {stat["node_type"]: stat["count"] for stat in node_stats if stat["node_type"]},
                "relationship_types": {stat["rel_type"]: stat["count"] for stat in rel_stats if stat["rel_type"]}
            }
            
        except Exception as e:
            logger.error(f"获取图统计信息失败: {str(e)}")
            return {"error": str(e)}
    
    def verify_chunk_entity_relationships(self, document_id: int) -> Dict[str, Any]:
        """验证指定文档的chunk-entity关系完整性
        
        Args:
            document_id: 文档ID
            
        Returns:
            验证结果统计
        """
        try:
            logger.info(f"开始验证文档 {document_id} 的chunk-entity关系")
            
            verification_result = {
                "document_id": document_id,
                "total_chunks": 0,
                "total_entities": 0,
                "chunk_entity_relationships": 0,
                "orphaned_entities": 0,
                "empty_chunks": 0,
                "success": True,
                "issues": []
            }
            
            # 查询文档的chunks
            chunks_query = """
            MATCH (d:Document {postgresql_id: $document_id})<-[:PART_OF]-(c:Chunk)
            RETURN count(c) as chunk_count, collect(c.node_id) as chunk_ids
            """
            chunks_result = self.execute_query(chunks_query, {"document_id": document_id})
            
            if chunks_result:
                verification_result["total_chunks"] = chunks_result[0]["chunk_count"]
                chunk_ids = chunks_result[0]["chunk_ids"]
            else:
                verification_result["issues"].append("未找到文档对应的chunks")
                verification_result["success"] = False
                return verification_result
            
            # 查询文档的实体
            entities_query = """
            MATCH (e) 
            WHERE e.document_id = $document_id AND e.type IS NOT NULL
            RETURN count(e) as entity_count, collect(e.node_id) as entity_ids
            """
            entities_result = self.execute_query(entities_query, {"document_id": document_id})
            
            if entities_result:
                verification_result["total_entities"] = entities_result[0]["entity_count"]
                entity_ids = entities_result[0]["entity_ids"]
            else:
                verification_result["issues"].append("未找到文档对应的实体")
                
            # 查询chunk-entity关系
            relationships_query = """
            MATCH (d:Document {postgresql_id: $document_id})<-[:PART_OF]-(c:Chunk)-[:HAS_ENTITY]->(e)
            RETURN count(*) as relationship_count,
                   collect(DISTINCT c.node_id) as chunks_with_entities,
                   collect(DISTINCT e.node_id) as entities_with_chunks
            """
            relationships_result = self.execute_query(relationships_query, {"document_id": document_id})
            
            if relationships_result:
                verification_result["chunk_entity_relationships"] = relationships_result[0]["relationship_count"]
                chunks_with_entities = set(relationships_result[0]["chunks_with_entities"])
                entities_with_chunks = set(relationships_result[0]["entities_with_chunks"])
                
                # 检查孤立实体
                if entities_result:
                    all_entity_ids = set(entity_ids)
                    orphaned_entities = all_entity_ids - entities_with_chunks
                    verification_result["orphaned_entities"] = len(orphaned_entities)
                    
                    if orphaned_entities:
                        verification_result["issues"].append(f"发现 {len(orphaned_entities)} 个孤立实体（未与chunk建立关系）")
                
                # 检查空chunks
                if chunks_result:
                    all_chunk_ids = set(chunk_ids)
                    empty_chunks = all_chunk_ids - chunks_with_entities
                    verification_result["empty_chunks"] = len(empty_chunks)
                    
                    if empty_chunks:
                        verification_result["issues"].append(f"发现 {len(empty_chunks)} 个空chunk（未包含实体）")
            
            # 评估整体状态
            if verification_result["issues"]:
                verification_result["success"] = False
            
            logger.info(f"验证完成: {verification_result['total_chunks']} 个chunks, {verification_result['total_entities']} 个实体, {verification_result['chunk_entity_relationships']} 个关系")
            
            return verification_result
            
        except Exception as e:
            logger.error(f"验证chunk-entity关系失败: {str(e)}")
            return {
                "document_id": document_id,
                "success": False,
                "error": str(e),
                "issues": [f"验证过程出错: {str(e)}"]
            } 