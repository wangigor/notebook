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
                                chunk_neo4j_ids: List[str],
                                chunks: Optional[List[DocumentChunk]] = None) -> None:
        """关联实体到对应的chunk
        
        Args:
            entities: 实体列表
            chunk_neo4j_ids: Chunk的Neo4j节点ID列表
            chunks: 文档分块列表（用于建立映射关系）
        """
        try:
            chunk_entity_pairs = []
            
            # 创建chunk_id到Neo4j ID的映射
            chunk_id_to_neo4j_id = {}
            if chunks:
                for i, chunk in enumerate(chunks):
                    if i < len(chunk_neo4j_ids):
                        # 主要使用chunk_id映射
                        chunk_id_to_neo4j_id[chunk.metadata.chunk_id] = chunk_neo4j_ids[i]
                        # 也支持chunk索引映射（备用）
                        chunk_id_to_neo4j_id[chunk.metadata.chunk_index] = chunk_neo4j_ids[i]
            else:
                # 如果没有chunks信息，假设顺序对应
                for i, chunk_neo4j_id in enumerate(chunk_neo4j_ids):
                    chunk_id_to_neo4j_id[i] = chunk_neo4j_id
            
            # 遍历实体，根据实体ID中的chunk信息建立关联
            for entity in entities:
                try:
                    # 从实体ID中提取chunk信息
                    chunk_id = self._extract_chunk_info_from_entity_id(entity.id)
                    
                    if chunk_id is not None:
                        # 查找对应的chunk Neo4j ID
                        chunk_neo4j_id = chunk_id_to_neo4j_id.get(chunk_id)
                        
                        if chunk_neo4j_id:
                            # 生成实体的Neo4j节点ID
                            entity_neo4j_id = self._get_entity_neo4j_id(entity)
                            
                            if entity_neo4j_id:
                                chunk_entity_pairs.append({
                                    "chunk_id": chunk_neo4j_id,
                                    "entity_id": entity_neo4j_id
                                })
                                logger.debug(f"关联实体 {entity.name} (ID: {entity_neo4j_id}) 到 chunk {chunk_id} (Neo4j ID: {chunk_neo4j_id})")
                            else:
                                logger.warning(f"无法生成实体 {entity.name} 的Neo4j节点ID")
                        else:
                            logger.warning(f"找不到chunk {chunk_id} 对应的Neo4j节点ID")
                    else:
                        logger.warning(f"无法从实体ID {entity.id} 中提取chunk信息")
                        
                except Exception as e:
                    logger.warning(f"处理实体 {entity.name} 的chunk关联时出错: {str(e)}")
                    continue
            
            # 批量创建HAS_ENTITY关系
            if chunk_entity_pairs:
                relationship_count = self.neo4j_service.create_chunk_entity_relationships(
                    chunk_entity_pairs
                )
                logger.info(f"Chunk-Entity关系创建成功: {relationship_count} 个关系，处理了 {len(chunk_entity_pairs)} 个配对")
            else:
                logger.warning("没有找到可以关联的chunk-entity配对")
            
        except Exception as e:
            logger.error(f"关联实体到Chunk失败: {str(e)}")
            raise
    
    def _extract_chunk_info_from_entity_id(self, entity_id: str) -> Optional[str]:
        """从实体ID中提取chunk信息
        
        实体ID格式：{chunk_id}_entity_{entity_index}
        chunk_id格式：doc{document_id}_chunk{chunk_index}_{content_hash}
        
        Args:
            entity_id: 实体ID
            
        Returns:
            完整的chunk_id，如果无法提取则返回None
        """
        try:
            # 实体ID格式：{chunk_id}_entity_{entity_index}
            if "_entity_" in entity_id:
                chunk_id = entity_id.split("_entity_")[0]
                
                # 验证chunk_id格式
                if "chunk" in chunk_id:
                    logger.debug(f"从实体ID {entity_id} 中提取到chunk_id: {chunk_id}")
                    return chunk_id
                else:
                    logger.warning(f"提取的chunk_id格式不正确: {chunk_id}")
                    return None
            
            logger.warning(f"实体ID格式不正确: {entity_id}")
            return None
            
        except Exception as e:
            logger.warning(f"解析实体ID {entity_id} 失败: {str(e)}")
            return None

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
                                            chunks: Optional[List[DocumentChunk]] = None,
                                            auto_store: bool = False) -> Dict[str, Any]:
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
            # 1. 准备Document节点数据（如果提供了文档信息）
            document_node_data = None
            if document_info:
                document_node_data = {
                    "id": f"doc_{document_id}",
                    "name": document_info.get('name', f'Document_{document_id}'),
                    "type": "Document",
                    "labels": ["Document"],
                    "properties": {
                        "postgresql_id": document_id,
                        "file_type": document_info.get('file_type', 'unknown'),
                        "file_size": document_info.get('file_size', 0),
                        "created_at": document_info.get('created_at', datetime.now()).isoformat() if isinstance(document_info.get('created_at'), datetime) else str(document_info.get('created_at', datetime.now()))
                    }
                }
                logger.info(f"准备Document节点数据: {document_node_data['id']}")
            
            # 2. 准备Chunk节点数据（如果提供了chunks数据）
            chunk_nodes_data = []
            if chunks:
                for i, chunk in enumerate(chunks):
                    chunk_node_data = {
                        "id": f"chunk_{chunk.metadata.chunk_id}",
                        "name": f"Chunk_{chunk.metadata.chunk_index}",
                        "type": "Chunk",
                        "labels": ["Chunk"],
                        "properties": {
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
                            "created_at": chunk.metadata.created_at.isoformat() if isinstance(chunk.metadata.created_at, datetime) else str(chunk.metadata.created_at),
                            "postgresql_document_id": chunk.metadata.postgresql_document_id
                        }
                    }
                    chunk_nodes_data.append(chunk_node_data)
                logger.info(f"准备Chunk节点数据: {len(chunk_nodes_data)} 个")
            
            # 3. 准备实体节点数据
            entity_nodes = await self._create_entity_nodes(entities, document_id)
            
            # 4. 准备关系边数据
            relationship_edges = await self._create_relationship_edges(relationships, entity_nodes, document_id)
            
            # 5. 准备Document-Chunk PART_OF关系数据
            document_chunk_relationships = []
            if document_node_data and chunk_nodes_data:
                for chunk_data in chunk_nodes_data:
                    document_chunk_relationships.append({
                        "id": f"rel_doc_chunk_{chunk_data['properties']['chunk_index']}",
                        "source_id": chunk_data["id"],
                        "target_id": document_node_data["id"],
                        "type": "PART_OF",
                        "properties": {
                            "created_at": datetime.now().isoformat()
                        }
                    })
                logger.info(f"准备Document-Chunk PART_OF关系数据: {len(document_chunk_relationships)} 个")
            
            # 6. 准备Document-FIRST_CHUNK关系数据
            document_first_chunk_relationships = []
            if document_node_data and chunks:
                document_first_chunk_relationships = self._prepare_document_chunk_relationships(chunks, document_node_data["id"])
                logger.info(f"准备Document-FIRST_CHUNK关系数据: {len(document_first_chunk_relationships)} 个")
            
            # 7. 准备Chunk-NEXT_CHUNK关系数据
            chunk_sequence_relationships = []
            if chunks:
                chunk_sequence_relationships = self._prepare_chunk_sequence_relationships(chunks)
                logger.info(f"准备Chunk-NEXT_CHUNK关系数据: {len(chunk_sequence_relationships)} 个")
            
            # 8. 准备多重Chunk-Entity关系数据
            chunk_entity_relationships = self._prepare_multi_chunk_entity_relationships(entities, chunk_nodes_data, chunks)
            logger.info(f"准备多重Chunk-Entity关系数据: {len(chunk_entity_relationships)} 个")
            
            # 9. 评估图谱质量
            quality_metrics = self._evaluate_graph_quality(entity_nodes, relationship_edges)
            
            # 10. 准备完整的图谱数据
            all_nodes = []
            all_relationships = []
            
            # 添加所有节点
            if document_node_data:
                all_nodes.append(document_node_data)
            all_nodes.extend(chunk_nodes_data)
            all_nodes.extend(entity_nodes)
            
            # 添加所有关系
            all_relationships.extend(document_chunk_relationships)          # PART_OF关系
            all_relationships.extend(document_first_chunk_relationships)    # FIRST_CHUNK关系
            all_relationships.extend(chunk_sequence_relationships)          # NEXT_CHUNK关系
            all_relationships.extend(chunk_entity_relationships)            # HAS_ENTITY关系
            all_relationships.extend(relationship_edges)                    # 实体间关系
            
            graph_data = {
                "document_id": document_id,
                "nodes": all_nodes,
                "edges": all_relationships,
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "total_nodes": len(all_nodes),
                    "total_edges": len(all_relationships),
                    "total_chunks": len(chunk_nodes_data),
                    "total_entities": len(entity_nodes),
                    "total_part_of_relationships": len(document_chunk_relationships),
                    "total_first_chunk_relationships": len(document_first_chunk_relationships),
                    "total_next_chunk_relationships": len(chunk_sequence_relationships),
                    "total_chunk_entity_relationships": len(chunk_entity_relationships),
                    "total_entity_relationships": len(relationship_edges),
                    "quality_metrics": quality_metrics
                }
            }
            
            logger.info(f"图谱构建完成：{len(all_nodes)} 个节点（{len(entity_nodes)} 个实体，{len(chunk_nodes_data)} 个Chunk），{len(all_relationships)} 条关系（{len(document_chunk_relationships)} 个PART_OF，{len(document_first_chunk_relationships)} 个FIRST_CHUNK，{len(chunk_sequence_relationships)} 个NEXT_CHUNK，{len(chunk_entity_relationships)} 个HAS_ENTITY，{len(relationship_edges)} 个实体间关系）")
            
            # 11. 自动存储到Neo4j（如果启用）
            if auto_store:
                logger.info("开始自动存储图谱数据到Neo4j")
                store_result = await self.neo4j_service.store_graph_data(graph_data)
                graph_data["store_result"] = store_result
                if store_result["success"]:
                    logger.info(f"图谱数据存储成功：{store_result['nodes_created']} 个节点，{store_result['relationships_created']} 条关系")
                else:
                    logger.error(f"图谱数据存储失败：{store_result.get('errors', [])}")
            
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
    
    def _prepare_multi_chunk_entity_relationships(self, entities: List[Entity], 
                                                 chunk_nodes_data: List[Dict[str, Any]],
                                                 chunks: Optional[List[DocumentChunk]] = None) -> List[Dict[str, Any]]:
        """基于实体的chunk映射信息创建多重HAS_ENTITY关系
        
        Args:
            entities: 去重后的实体列表（包含chunk_ids属性）
            chunk_nodes_data: Chunk节点数据列表
            chunks: 文档分块列表（用于建立映射关系）
            
        Returns:
            多重Chunk-Entity关系数据列表
        """
        try:
            chunk_entity_relationships = []
            
            # 创建chunk_id到节点ID的映射
            chunk_id_to_node_id = {}
            for chunk_node in chunk_nodes_data:
                chunk_id = chunk_node["properties"]["chunk_id"]
                chunk_index = chunk_node["properties"]["chunk_index"]
                chunk_id_to_node_id[chunk_id] = chunk_node["id"]
                # 也支持通过chunk_index映射（备用）
                chunk_id_to_node_id[chunk_index] = chunk_node["id"]
            
            # 遍历实体，为每个chunk创建关系
            for entity in entities:
                try:
                    # 获取实体出现的所有chunk_ids
                    chunk_ids = entity.properties.get('chunk_ids', [])
                    
                    if not chunk_ids:
                        # 如果没有chunk_ids属性，尝试从实体ID中提取（向后兼容）
                        chunk_id = self._extract_chunk_info_from_entity_id(entity.id)
                        if chunk_id:
                            chunk_ids = [chunk_id]
                    
                    # 为每个chunk创建HAS_ENTITY关系
                    for chunk_id in chunk_ids:
                        chunk_node_id = chunk_id_to_node_id.get(chunk_id)
                        
                        if chunk_node_id:
                            # 生成实体的节点ID
                            entity_node_id = self._generate_node_id(entity.name, entity.type)
                            
                            # 创建关系数据
                            relationship_data = {
                                "id": f"rel_chunk_entity_{chunk_id}_{entity_node_id}",
                                "source_id": chunk_node_id,
                                "target_id": entity_node_id,
                                "type": "HAS_ENTITY",
                                "properties": {
                                    "created_at": datetime.now().isoformat(),
                                    "entity_name": entity.name,
                                    "entity_type": entity.type,
                                    "confidence": entity.confidence,
                                    "chunk_id": chunk_id
                                }
                            }
                            chunk_entity_relationships.append(relationship_data)
                            
                            logger.debug(f"准备Chunk-Entity关系: {chunk_node_id} -> {entity_node_id} ({entity.name}) for chunk {chunk_id}")
                        else:
                            logger.warning(f"找不到chunk {chunk_id} 对应的节点ID")
                
                except Exception as e:
                    logger.warning(f"处理实体 {entity.name} 的多chunk关联时出错: {str(e)}")
                    continue
            
            logger.info(f"成功准备 {len(chunk_entity_relationships)} 个多重Chunk-Entity关系")
            return chunk_entity_relationships
            
        except Exception as e:
            logger.error(f"准备多重Chunk-Entity关系失败: {str(e)}")
            return []
    
    def _prepare_chunk_entity_relationships(self, entities: List[Entity], 
                                           chunk_nodes_data: List[Dict[str, Any]],
                                           chunks: Optional[List[DocumentChunk]] = None) -> List[Dict[str, Any]]:
        """准备Chunk-Entity关系数据
        
        Args:
            entities: 实体列表
            chunk_nodes_data: Chunk节点数据列表
            chunks: 文档分块列表（用于建立映射关系）
            
        Returns:
            Chunk-Entity关系数据列表
        """
        try:
            chunk_entity_relationships = []
            
            # 创建chunk_id到节点ID的映射
            chunk_id_to_node_id = {}
            for chunk_node in chunk_nodes_data:
                chunk_id = chunk_node["properties"]["chunk_id"]
                chunk_index = chunk_node["properties"]["chunk_index"]
                chunk_id_to_node_id[chunk_id] = chunk_node["id"]
                # 也支持通过chunk_index映射（备用）
                chunk_id_to_node_id[chunk_index] = chunk_node["id"]
            
            # 遍历实体，建立与chunk的关联
            for entity in entities:
                try:
                    # 从实体ID中提取chunk信息
                    chunk_id = self._extract_chunk_info_from_entity_id(entity.id)
                    
                    if chunk_id is not None:
                        # 查找对应的chunk节点ID
                        chunk_node_id = chunk_id_to_node_id.get(chunk_id)
                        
                        if chunk_node_id:
                            # 生成实体的节点ID
                            entity_node_id = self._generate_node_id(entity.name, entity.type)
                            
                            # 创建关系数据
                            relationship_data = {
                                "id": f"rel_chunk_entity_{chunk_id}_{entity_node_id}",
                                "source_id": chunk_node_id,
                                "target_id": entity_node_id,
                                "type": "HAS_ENTITY",
                                "properties": {
                                    "created_at": datetime.now().isoformat(),
                                    "entity_name": entity.name,
                                    "entity_type": entity.type,
                                    "confidence": entity.confidence
                                }
                            }
                            chunk_entity_relationships.append(relationship_data)
                            
                            logger.debug(f"准备Chunk-Entity关系: {chunk_node_id} -> {entity_node_id} ({entity.name})")
                        else:
                            logger.warning(f"找不到chunk {chunk_id} 对应的节点ID")
                    else:
                        logger.warning(f"无法从实体ID {entity.id} 中提取chunk信息")
                        
                except Exception as e:
                    logger.warning(f"处理实体 {entity.name} 的chunk关联时出错: {str(e)}")
                    continue
            
            logger.info(f"成功准备 {len(chunk_entity_relationships)} 个Chunk-Entity关系")
            return chunk_entity_relationships
            
        except Exception as e:
            logger.error(f"准备Chunk-Entity关系失败: {str(e)}")
            return []
    
    def _prepare_document_chunk_relationships(self, chunks: List[DocumentChunk], document_node_id: str) -> List[Dict[str, Any]]:
        """创建Document的FIRST_CHUNK关系数据
        
        Args:
            chunks: 文档分块列表
            document_node_id: Document节点的ID
            
        Returns:
            Document-Chunk关系数据列表
        """
        try:
            document_chunk_relationships = []
            
            if chunks:
                # 找到第一个chunk（chunk_index=0）
                first_chunk = None
                for chunk in chunks:
                    if chunk.metadata.chunk_index == 0:
                        first_chunk = chunk
                        break
                
                if first_chunk:
                    # 创建FIRST_CHUNK关系
                    first_chunk_node_id = f"chunk_{first_chunk.metadata.chunk_id}"
                    
                    relationship_data = {
                        "id": f"rel_first_chunk_{document_node_id}_{first_chunk_node_id}",
                        "source_id": document_node_id,
                        "target_id": first_chunk_node_id,
                        "type": "FIRST_CHUNK",
                        "properties": {
                            "created_at": datetime.now().isoformat(),
                            "chunk_index": first_chunk.metadata.chunk_index,
                            "chunk_id": first_chunk.metadata.chunk_id
                        }
                    }
                    document_chunk_relationships.append(relationship_data)
                    
                    logger.debug(f"准备Document-FIRST_CHUNK关系: {document_node_id} -> {first_chunk_node_id}")
                else:
                    logger.warning("未找到第一个chunk（chunk_index=0）")
            
            logger.info(f"成功准备 {len(document_chunk_relationships)} 个Document-FIRST_CHUNK关系")
            return document_chunk_relationships
            
        except Exception as e:
            logger.error(f"准备Document-FIRST_CHUNK关系失败: {str(e)}")
            return []
    
    def _prepare_chunk_sequence_relationships(self, chunks: List[DocumentChunk]) -> List[Dict[str, Any]]:
        """创建Chunk之间的NEXT_CHUNK关系数据
        
        Args:
            chunks: 文档分块列表（应该按chunk_index排序）
            
        Returns:
            Chunk序列关系数据列表
        """
        try:
            chunk_sequence_relationships = []
            
            if len(chunks) > 1:
                # 按chunk_index排序确保顺序正确
                sorted_chunks = sorted(chunks, key=lambda x: x.metadata.chunk_index)
                
                # 创建相邻chunk之间的NEXT_CHUNK关系
                for i in range(len(sorted_chunks) - 1):
                    current_chunk = sorted_chunks[i]
                    next_chunk = sorted_chunks[i + 1]
                    
                    current_chunk_node_id = f"chunk_{current_chunk.metadata.chunk_id}"
                    next_chunk_node_id = f"chunk_{next_chunk.metadata.chunk_id}"
                    
                    relationship_data = {
                        "id": f"rel_next_chunk_{current_chunk_node_id}_{next_chunk_node_id}",
                        "source_id": current_chunk_node_id,
                        "target_id": next_chunk_node_id,
                        "type": "NEXT_CHUNK",
                        "properties": {
                            "created_at": datetime.now().isoformat(),
                            "current_chunk_index": current_chunk.metadata.chunk_index,
                            "next_chunk_index": next_chunk.metadata.chunk_index,
                            "current_chunk_id": current_chunk.metadata.chunk_id,
                            "next_chunk_id": next_chunk.metadata.chunk_id
                        }
                    }
                    chunk_sequence_relationships.append(relationship_data)
                    
                    logger.debug(f"准备Chunk-NEXT_CHUNK关系: {current_chunk_node_id} -> {next_chunk_node_id}")
            
            logger.info(f"成功准备 {len(chunk_sequence_relationships)} 个Chunk-NEXT_CHUNK关系")
            return chunk_sequence_relationships
            
        except Exception as e:
            logger.error(f"准备Chunk-NEXT_CHUNK关系失败: {str(e)}")
            return [] 