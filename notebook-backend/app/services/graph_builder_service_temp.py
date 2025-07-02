import logging
import hashlib
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from dataclasses import asdict
from app.core.config import settings
from app.services.neo4j_service import Neo4jService
from app.services.entity_extraction_service import Entity
from app.services.relationship_service import Relationship
from app.services.chunk_service import DocumentChunk

logger = logging.getLogger(__name__)

class GraphBuilderService:
    """图谱构建服务
    
    负责将抽取的实体和关系构建成知识图谱并存储到Neo4j，包括：
    - 实体节点创建和去重
    - 关系边创建和验证
    - 图谱质量评估
    - 数据一致性保证
    """
    
    def __init__(self):
        """初始化图谱构建服务"""
        self.neo4j_service = Neo4jService()
        self.created_entities = set()  # 用于去重
        self.created_relationships = set()  # 用于去重
        self.created_documents = set()
        self.created_chunks = set()
        self.chunk_entity_mapping = []
        logger.info("图谱构建服务已初始化")
    
    def _create_document_node(self, document_id: int, name: str, file_type: str, 
                             file_size: int, created_at: datetime) -> str:
        """创建Document节点到Neo4j
        
        Args:
            document_id: PostgreSQL文档ID
            name: 文档名称
            file_type: 文件类型
            file_size: 文件大小
            created_at: 创建时间
            
        Returns:
            Neo4j节点ID
        """
        try:
            neo4j_node_id = self.neo4j_service.create_document_node(
                postgresql_id=document_id,
                name=name,
                file_type=file_type,
                file_size=file_size,
                created_at=created_at
            )
            self.created_documents.add(neo4j_node_id)
            logger.info(f"Document节点创建成功: {neo4j_node_id}")
            return neo4j_node_id
        except Exception as e:
            logger.error(f"创建Document节点失败: {str(e)}")
            raise
    
    def _create_chunk_nodes(self, chunks: List[DocumentChunk], 
                           document_neo4j_id: str) -> List[str]:
        """创建Chunk节点到Neo4j
        
        Args:
            chunks: 分块列表
            document_neo4j_id: Document的Neo4j节点ID
            
        Returns:
            Chunk节点ID列表
        """
        try:
            chunks_data = []
            for chunk in chunks:
                chunk_data = {
                    "chunk_id": chunk.metadata.chunk_id,
                    "content": chunk.content,
                    "position": f"{chunk.metadata.start_char}-{chunk.metadata.end_char}",
                    "chunk_index": chunk.metadata.chunk_index,
                    "start_char": chunk.metadata.start_char,
                    "end_char": chunk.metadata.end_char,
                    "content_length": chunk.metadata.content_length,
                    "word_count": chunk.metadata.word_count,
                    "paragraph_count": chunk.metadata.paragraph_count,
                    "chunk_type": chunk.metadata.chunk_type,
                    "created_at": chunk.metadata.created_at,
                    "postgresql_document_id": chunk.metadata.postgresql_document_id
                }
                chunks_data.append(chunk_data)
            
            chunk_neo4j_ids = self.neo4j_service.batch_create_chunk_nodes(chunks_data)
            
            # 创建PART_OF关系
            if chunk_neo4j_ids:
                self.neo4j_service.create_chunk_document_relationships(
                    chunk_neo4j_ids, document_neo4j_id
                )
            
            # 记录创建的chunks
            self.created_chunks.update(chunk_neo4j_ids)
            
            logger.info(f"Chunk节点创建成功: {len(chunk_neo4j_ids)} 个")
            return chunk_neo4j_ids
            
        except Exception as e:
            logger.error(f"创建Chunk节点失败: {str(e)}")
            raise
    
    def _link_entities_to_chunks(self, entities: List[Entity], 
                                chunk_neo4j_ids: List[str], chunks: List[DocumentChunk]) -> None:
        """关联实体到对应的chunk
        
        Args:
            entities: 实体列表
            chunk_neo4j_ids: Chunk的Neo4j节点ID列表
        """
        try:
            chunk_entity_pairs = []
            
            # 遍历实体，根据chunk_id建立关联
            for entity in entities:
                if hasattr(entity, 'chunk_neo4j_id') and entity.chunk_neo4j_id:
                    # 查找对应的chunk
                    chunk_neo4j_id = entity.chunk_neo4j_id
                    if chunk_neo4j_id in chunk_neo4j_ids:
                        # 查找entity的Neo4j节点ID
                        entity_neo4j_id = self._get_entity_neo4j_id(entity)
                        if entity_neo4j_id:
                            chunk_entity_pairs.append({
                                "chunk_id": chunk_neo4j_id,
                                "entity_id": entity_neo4j_id
                            })
            
            # 批量创建HAS_ENTITY关系
            if chunk_entity_pairs:
                relationship_count = self.neo4j_service.create_chunk_entity_relationships(
                    chunk_entity_pairs
                )
                logger.info(f"Chunk-Entity关系创建成功: {relationship_count} 个")
            
        except Exception as e:
            logger.error(f"关联实体到Chunk失败: {str(e)}")
            raise
    
    def _get_entity_neo4j_id(self, entity: Entity) -> Optional[str]:
        """根据实体获取其Neo4j节点ID
        
        Args:
            entity: 实体对象
            
        Returns:
            Neo4j节点ID或None
        """
        try:
            # 生成与_create_entity_nodes中相同的节点ID
            node_id = self._generate_node_id(entity.name, entity.type)
            return node_id
        except Exception as e:
            logger.warning(f"获取实体Neo4j ID失败: {entity.name}, 错误: {str(e)}")
            return None
    
    async def build_graph_from_extracted_data(self, entities: List[Entity], 
                                            relationships: List[Relationship],
                                            document_id: int,
                                            document_info: Optional[Dict[str, Any]] = None,
                                            chunks: Optional[List[DocumentChunk]] = None) -> Dict[str, Any]:
        """从抽取的实体和关系构建图谱
        
        Args:
            entities: 抽取的实体列表
            relationships: 抽取的关系列表
            document_id: 文档ID
            document_info: 文档信息字典，包含name, file_type, file_size, created_at等
            chunks: 文档分块列表
            
        Returns:
            构建结果
        """
        logger.info(f"开始构建文档{document_id}的知识图谱")
        
        try:
            # 0. 创建Document节点（如果提供了文档信息）
            document_neo4j_id = None
            if document_info:
                document_neo4j_id = self._create_document_node(
                    document_id=document_id,
                    name=document_info.get('name', f'Document_{document_id}'),
                    file_type=document_info.get('file_type', 'unknown'),
                    file_size=document_info.get('file_size', 0),
                    created_at=document_info.get('created_at', datetime.now())
                )
                logger.info(f"Document节点创建成功: {document_neo4j_id}")
            
            # 1. 创建Chunk节点（如果提供了chunks数据）
            chunk_neo4j_ids = []
            if chunks and document_neo4j_id:
                chunk_neo4j_ids = self._create_chunk_nodes(chunks, document_neo4j_id)
                logger.info(f"Chunk节点创建成功: {len(chunk_neo4j_ids)} 个")
            
            # 2. 创建实体节点
            entity_nodes = await self._create_entity_nodes(entities, document_id)
            
            # 3. 创建关系边
            relationship_edges = await self._create_relationship_edges(relationships, entity_nodes, document_id)
            
            # 4. 关联实体到Chunk（如果chunks和entities都存在）
            if chunks and entities and chunk_neo4j_ids:
                self._link_entities_to_chunks(entities, chunk_neo4j_ids, chunks)
            
            # 5. 评估图谱质量
            quality_metrics = self._evaluate_graph_quality(entity_nodes, relationship_edges)
            
            # 6. 准备图谱数据
            graph_data = {
                "document_id": document_id,
                "document_neo4j_id": document_neo4j_id,
                "chunk_neo4j_ids": chunk_neo4j_ids,
                "nodes": entity_nodes,
                "edges": relationship_edges,
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "total_nodes": len(entity_nodes),
                    "total_edges": len(relationship_edges),
                    "total_chunks": len(chunk_neo4j_ids),
                    "quality_metrics": quality_metrics
                }
            }
            
            logger.info(f"图谱构建完成：{len(entity_nodes)} 个实体节点，{len(relationship_edges)} 条关系边，{len(chunk_neo4j_ids)} 个Chunk节点")
            return graph_data
            
        except Exception as e:
            logger.error(f"图谱构建失败: {str(e)}")
            raise
    
    async def _create_entity_nodes(self, entities: List[Entity], document_id: int) -> List[Dict[str, Any]]:
        """创建实体节点
        
        Args:
            entities: 实体列表
            document_id: 文档ID
            
        Returns:
            节点列表
        """
        logger.info(f"开始创建 {len(entities)} 个实体节点")
        
        nodes = []
        entity_map = {}  # 实体名称到节点ID的映射
        
        for entity in entities:
            try:
                # 生成节点ID
                node_id = self._generate_node_id(entity.name, entity.type)
                
                # 检查去重
                if node_id in self.created_entities:
                    # 如果实体已存在，更新映射
                    entity_map[entity.name] = node_id
                    continue
                
                # 创建节点数据
                node_data = {
                    "id": node_id,
                    "name": entity.name,
                    "type": entity.type,
                    "description": entity.description,
                    "properties": {
                        **entity.properties,
                        "confidence": entity.confidence,
                        "source_text": entity.source_text,
                        "document_id": document_id,
                        "created_at": datetime.now().isoformat()
                    },
                    "labels": [entity.type, "Entity"],  # Neo4j标签
                    "embedding": getattr(entity, 'embedding', None)  # 如果有向量
                }
                
                nodes.append(node_data)
                entity_map[entity.name] = node_id
                self.created_entities.add(node_id)
                
            except Exception as e:
                logger.warning(f"创建实体节点失败: {entity.name}, 错误: {str(e)}")
                continue
        
        logger.info(f"成功创建 {len(nodes)} 个实体节点")
        return nodes
    
    async def _create_relationship_edges(self, relationships: List[Relationship], 
                                       entity_nodes: List[Dict[str, Any]], 
                                       document_id: int) -> List[Dict[str, Any]]:
        """创建关系边
        
        Args:
            relationships: 关系列表
            entity_nodes: 实体节点列表
            document_id: 文档ID
            
        Returns:
            边列表
        """
        logger.info(f"开始创建 {len(relationships)} 条关系边")
        
        edges = []
        # 创建实体名称到节点ID的映射
        entity_name_to_id = {}
        for node in entity_nodes:
            entity_name_to_id[node["name"]] = node["id"]
        
        for relationship in relationships:
            try:
                # 查找源和目标实体的节点ID
                source_node_id = entity_name_to_id.get(relationship.source_entity_name)
                target_node_id = entity_name_to_id.get(relationship.target_entity_name)
                
                if not source_node_id or not target_node_id:
                    logger.warning(f"关系中的实体未找到对应节点: {relationship.source_entity_name} -> {relationship.target_entity_name}")
                    continue
                
                # 生成边ID
                edge_id = self._generate_edge_id(source_node_id, target_node_id, relationship.relationship_type)
                
                # 检查去重
                if edge_id in self.created_relationships:
                    continue
                
                # 创建边数据
                edge_data = {
                    "id": edge_id,
                    "source_id": source_node_id,
                    "target_id": target_node_id,
                    "source_name": relationship.source_entity_name,
                    "target_name": relationship.target_entity_name,
                    "type": relationship.relationship_type,
                    "description": relationship.description,
                    "properties": {
                        **relationship.properties,
                        "confidence": relationship.confidence,
                        "context": relationship.context,
                        "source_text": relationship.source_text,
                        "document_id": document_id,
                        "created_at": datetime.now().isoformat()
                    }
                }
                
                edges.append(edge_data)
                self.created_relationships.add(edge_id)
                
            except Exception as e:
                logger.warning(f"创建关系边失败: {relationship.relationship_type}, 错误: {str(e)}")
                continue
        
        logger.info(f"成功创建 {len(edges)} 条关系边")
        return edges
    
    def _generate_node_id(self, entity_name: str, entity_type: str) -> str:
        """生成节点ID
        
        Args:
            entity_name: 实体名称
            entity_type: 实体类型
            
        Returns:
            节点ID
        """
        # 使用实体名称和类型生成唯一ID
        content = f"{entity_name.lower()}_{entity_type}"
        return f"entity_{hashlib.md5(content.encode()).hexdigest()[:8]}"
    
    def _generate_edge_id(self, source_id: str, target_id: str, relationship_type: str) -> str:
        """生成边ID
        
        Args:
            source_id: 源节点ID
            target_id: 目标节点ID
            relationship_type: 关系类型
            
        Returns:
            边ID
        """
        content = f"{source_id}_{target_id}_{relationship_type}"
        return f"rel_{hashlib.md5(content.encode()).hexdigest()[:8]}"
    
    def _evaluate_graph_quality(self, nodes: List[Dict[str, Any]], 
                               edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """评估图谱质量
        
        Args:
            nodes: 节点列表
            edges: 边列表
            
        Returns:
            质量指标
        """
        if not nodes:
            return {"quality_score": 0.0, "issues": ["无实体节点"]}
        
        metrics = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "density": 0.0,  # 图密度
            "avg_node_degree": 0.0,  # 平均节点度数
            "isolated_nodes": 0,  # 孤立节点数
            "entity_type_distribution": {},  # 实体类型分布
            "relationship_type_distribution": {},  # 关系类型分布
            "quality_score": 0.0,  # 总体质量分数
            "issues": []  # 质量问题
        }
        
        try:
            # 计算实体类型分布
            for node in nodes:
                entity_type = node.get("type", "未知")
                if entity_type not in metrics["entity_type_distribution"]:
                    metrics["entity_type_distribution"][entity_type] = 0
                metrics["entity_type_distribution"][entity_type] += 1
            
            # 计算关系类型分布
            for edge in edges:
                rel_type = edge.get("type", "未知")
                if rel_type not in metrics["relationship_type_distribution"]:
                    metrics["relationship_type_distribution"][rel_type] = 0
                metrics["relationship_type_distribution"][rel_type] += 1
            
            # 计算节点度数
            node_degrees = {}
            for edge in edges:
                source_id = edge.get("source_id")
                target_id = edge.get("target_id")
                
                if source_id:
                    node_degrees[source_id] = node_degrees.get(source_id, 0) + 1
                if target_id:
                    node_degrees[target_id] = node_degrees.get(target_id, 0) + 1
            
            # 计算孤立节点
            connected_nodes = set(node_degrees.keys())
            all_nodes = {node["id"] for node in nodes}
            isolated_nodes = all_nodes - connected_nodes
            metrics["isolated_nodes"] = len(isolated_nodes)
            
            # 计算平均度数
            if node_degrees:
                metrics["avg_node_degree"] = sum(node_degrees.values()) / len(node_degrees)
            
            # 计算图密度
            if len(nodes) > 1:
                max_edges = len(nodes) * (len(nodes) - 1)  # 有向图
                metrics["density"] = len(edges) / max_edges if max_edges > 0 else 0
            
            # 计算质量分数
            quality_factors = []
            
            # 因子1：连通性 (权重: 0.3)
            connectivity_score = 1.0 - (metrics["isolated_nodes"] / len(nodes))
            quality_factors.append(("connectivity", connectivity_score, 0.3))
            
            # 因子2：实体置信度 (权重: 0.3)
            entity_confidences = [
                node.get("properties", {}).get("confidence", 0.5) 
                for node in nodes
            ]
            avg_entity_confidence = sum(entity_confidences) / len(entity_confidences) if entity_confidences else 0
            quality_factors.append(("entity_confidence", avg_entity_confidence, 0.3))
            
            # 因子3：关系置信度 (权重: 0.2)
            if edges:
                relationship_confidences = [
                    edge.get("properties", {}).get("confidence", 0.5) 
                    for edge in edges
                ]
                avg_rel_confidence = sum(relationship_confidences) / len(relationship_confidences)
            else:
                avg_rel_confidence = 0
            quality_factors.append(("relationship_confidence", avg_rel_confidence, 0.2))
            
            # 因子4：图密度适中性 (权重: 0.2)
            # 密度在0.1-0.5之间认为是合理的
            density_score = 1.0 if 0.1 <= metrics["density"] <= 0.5 else max(0, 1 - abs(metrics["density"] - 0.3) / 0.3)
            quality_factors.append(("density", density_score, 0.2))
            
            # 计算加权总分
            weighted_score = sum(score * weight for _, score, weight in quality_factors)
            metrics["quality_score"] = round(weighted_score, 3)
            
            # 识别质量问题
            issues = []
            if metrics["isolated_nodes"] > len(nodes) * 0.3:
                issues.append(f"孤立节点过多: {metrics['isolated_nodes']}")
            if avg_entity_confidence < 0.6:
                issues.append(f"实体置信度较低: {avg_entity_confidence:.2f}")
            if avg_rel_confidence < 0.6:
                issues.append(f"关系置信度较低: {avg_rel_confidence:.2f}")
            if metrics["density"] < 0.05:
                issues.append("图谱连接稀疏")
            
            metrics["issues"] = issues
            
        except Exception as e:
            logger.error(f"图谱质量评估失败: {str(e)}")
            metrics["issues"].append(f"质量评估错误: {str(e)}")
        
        return metrics
    
    async def deduplicate_graph_data(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """去重图谱数据
        
        Args:
            graph_data: 原始图谱数据
            
        Returns:
            去重后的图谱数据
        """
        logger.info("开始图谱数据去重")
        
        try:
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])
            
            # 去重节点
            seen_nodes = set()
            deduplicated_nodes = []
            
            for node in nodes:
                node_key = (node.get("name", "").lower(), node.get("type", ""))
                if node_key not in seen_nodes:
                    seen_nodes.add(node_key)
                    deduplicated_nodes.append(node)
            
            # 去重边
            seen_edges = set()
            deduplicated_edges = []
            
            for edge in edges:
                edge_key = (
                    edge.get("source_name", "").lower(),
                    edge.get("target_name", "").lower(),
                    edge.get("type", "")
                )
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    deduplicated_edges.append(edge)
            
            # 更新图谱数据
            graph_data["nodes"] = deduplicated_nodes
            graph_data["edges"] = deduplicated_edges
            graph_data["metadata"]["total_nodes"] = len(deduplicated_nodes)
            graph_data["metadata"]["total_edges"] = len(deduplicated_edges)
            
            removed_nodes = len(nodes) - len(deduplicated_nodes)
            removed_edges = len(edges) - len(deduplicated_edges)
            
            logger.info(f"去重完成：移除 {removed_nodes} 个重复节点，{removed_edges} 条重复边")
            return graph_data
            
        except Exception as e:
            logger.error(f"图谱数据去重失败: {str(e)}")
            return graph_data
    
    async def validate_graph_integrity(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证图谱数据完整性
        
        Args:
            graph_data: 图谱数据
            
        Returns:
            验证结果
        """
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])
            
            # 检查节点
            node_ids = set()
            for i, node in enumerate(nodes):
                if not node.get("id"):
                    validation_result["errors"].append(f"节点 {i} 缺少ID")
                    validation_result["is_valid"] = False
                else:
                    if node["id"] in node_ids:
                        validation_result["errors"].append(f"重复的节点ID: {node['id']}")
                        validation_result["is_valid"] = False
                    node_ids.add(node["id"])
                
                if not node.get("name"):
                    validation_result["warnings"].append(f"节点 {node.get('id', i)} 缺少名称")
                
                if not node.get("type"):
                    validation_result["warnings"].append(f"节点 {node.get('id', i)} 缺少类型")
            
            # 检查边
            edge_ids = set()
            for i, edge in enumerate(edges):
                if not edge.get("id"):
                    validation_result["errors"].append(f"边 {i} 缺少ID")
                    validation_result["is_valid"] = False
                else:
                    if edge["id"] in edge_ids:
                        validation_result["errors"].append(f"重复的边ID: {edge['id']}")
                        validation_result["is_valid"] = False
                    edge_ids.add(edge["id"])
                
                # 检查边的节点引用
                source_id = edge.get("source_id")
                target_id = edge.get("target_id")
                
                if not source_id:
                    validation_result["errors"].append(f"边 {edge.get('id', i)} 缺少源节点ID")
                    validation_result["is_valid"] = False
                elif source_id not in node_ids:
                    validation_result["errors"].append(f"边 {edge.get('id', i)} 引用了不存在的源节点: {source_id}")
                    validation_result["is_valid"] = False
                
                if not target_id:
                    validation_result["errors"].append(f"边 {edge.get('id', i)} 缺少目标节点ID")
                    validation_result["is_valid"] = False
                elif target_id not in node_ids:
                    validation_result["errors"].append(f"边 {edge.get('id', i)} 引用了不存在的目标节点: {target_id}")
                    validation_result["is_valid"] = False
                
                if not edge.get("type"):
                    validation_result["warnings"].append(f"边 {edge.get('id', i)} 缺少关系类型")
            
        except Exception as e:
            validation_result["errors"].append(f"验证过程中发生错误: {str(e)}")
            validation_result["is_valid"] = False
        
        return validation_result 