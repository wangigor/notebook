import logging
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
            "errors": []
        }
        
        try:
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])
            
            # 存储节点
            if nodes:
                node_result = await self._batch_store_nodes(nodes)
                result["nodes_created"] = node_result["created_count"]
                result["errors"].extend(node_result.get("errors", []))
            
            # 存储关系
            if edges and result["nodes_created"] > 0:
                edge_result = await self._batch_store_relationships(edges)
                result["relationships_created"] = edge_result["created_count"]
                result["errors"].extend(edge_result.get("errors", []))
            
            # 如果有错误，标记为部分成功
            if result["errors"]:
                result["success"] = False
                logger.warning(f"图谱存储完成但有错误: {len(result['errors'])} 个")
            else:
                logger.info(f"图谱存储成功: {result['nodes_created']} 个节点, {result['relationships_created']} 条关系")
            
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
            "errors": []
        }
        
        try:
            batch_size = getattr(settings, 'GRAPH_BATCH_SIZE', 50)
            
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i:i + batch_size]
                
                try:
                    # 简化的批量插入查询（不依赖APOC）
                    query = """
                    UNWIND $nodes AS nodeData
                    CREATE (n)
                    SET n = nodeData.properties
                    SET n.node_id = nodeData.id
                    RETURN count(n) as created_count
                    """
                    
                    # 准备节点数据
                    batch_data = []
                    for node in batch:
                        node_data = {
                            "id": node.get("id"),
                            "properties": {
                                **node.get("properties", {}),
                                "name": node.get("name", ""),
                                "type": node.get("type", ""),
                                "description": node.get("description", "")
                            }
                        }
                        batch_data.append(node_data)
                    
                    # 执行批量插入
                    batch_result = self.execute_write_query(query, {"nodes": batch_data})
                    batch_created = batch_result[0]["created_count"] if batch_result else 0
                    result["created_count"] += batch_created
                    
                    logger.info(f"节点批次 {i//batch_size + 1} 完成: {batch_created} 个节点")
                    
                except Exception as e:
                    error_msg = f"节点批次 {i//batch_size + 1} 存储失败: {str(e)}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
                    continue
            
        except Exception as e:
            error_msg = f"批量存储节点失败: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
        
        logger.info(f"节点存储完成: {result['created_count']} 个成功")
        return result
    
    async def _batch_store_relationships(self, edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量存储关系
        
        Args:
            edges: 关系列表
            
        Returns:
            存储结果
        """
        logger.info(f"开始批量存储 {len(edges)} 条关系")
        
        result = {
            "created_count": 0,
            "errors": []
        }
        
        try:
            batch_size = getattr(settings, 'GRAPH_BATCH_SIZE', 50)
            
            for i in range(0, len(edges), batch_size):
                batch = edges[i:i + batch_size]
                
                try:
                    # 构建批量插入查询
                    query = """
                    UNWIND $relationships AS relData
                    MATCH (source {node_id: relData.source_id})
                    MATCH (target {node_id: relData.target_id})
                    CREATE (source)-[r:RELATIONSHIP]->(target)
                    SET r = relData.properties
                    SET r.relationship_type = relData.type
                    RETURN count(r) as created_count
                    """
                    
                    # 准备关系数据
                    batch_data = []
                    for edge in batch:
                        rel_data = {
                            "source_id": edge.get("source_id"),
                            "target_id": edge.get("target_id"),
                            "type": edge.get("type", "RELATED"),
                            "properties": {
                                **edge.get("properties", {}),
                                "id": edge.get("id"),
                                "description": edge.get("description", "")
                            }
                        }
                        batch_data.append(rel_data)
                    
                    # 执行批量插入
                    batch_result = self.execute_write_query(query, {"relationships": batch_data})
                    batch_created = batch_result[0]["created_count"] if batch_result else 0
                    result["created_count"] += batch_created
                    
                    logger.info(f"关系批次 {i//batch_size + 1} 完成: {batch_created} 条关系")
                    
                except Exception as e:
                    error_msg = f"关系批次 {i//batch_size + 1} 存储失败: {str(e)}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
                    continue
            
        except Exception as e:
            error_msg = f"批量存储关系失败: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
        
        logger.info(f"关系存储完成: {result['created_count']} 条成功")
        return result
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """获取图数据库统计信息
        
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