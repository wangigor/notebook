import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from app.core.config import settings
from app.services.neo4j_service import Neo4jService
from app.services.dashscope_singleton import get_dashscope_client

logger = logging.getLogger(__name__)

class GraphVectorService:
    """图谱向量化服务
    
    专门为知识图谱构建提供向量化功能，包括：
    - 分块文本向量化
    - 实体向量化
    - 向量存储到Neo4j
    - 向量相似度计算
    """
    
    def __init__(self):
        """初始化图谱向量化服务"""
        self.embedding_model = None
        self.neo4j_service = Neo4jService()
        self._initialize_embedding_model()
        logger.info("图谱向量化服务已初始化")
    
    def _initialize_embedding_model(self):
        """初始化嵌入模型 - 使用DashScope单例"""
        try:
            logger.info("🔧 GraphVectorService使用DashScope单例...")
            
            # 使用DashScope单例
            self.embedding_model = get_dashscope_client()
            
            # 测试嵌入模型
            test_text = "测试向量化"
            test_vector = self.embedding_model.embed_query(test_text)
            logger.info(f"✅ GraphVectorService嵌入模型初始化成功，向量维度: {len(test_vector)}")
            
        except Exception as e:
            logger.error(f"❌ GraphVectorService初始化嵌入模型失败: {str(e)}")
            self.embedding_model = None
    
    async def vectorize_chunks(self, chunks: List[Any]) -> List[Dict[str, Any]]:
        """向量化分块
        
        Args:
            chunks: 分块列表，每个分块包含content、metadata等
            
        Returns:
            带有向量的分块列表
        """
        logger.info(f"开始向量化 {len(chunks)} 个分块")
        
        vectorized_chunks = []
        
        try:
            # 提取所有文本内容
            texts = [chunk.content if hasattr(chunk, 'content') else chunk.get('content', '') for chunk in chunks]
            
            # 批量生成向量
            if self.embedding_model:
                try:
                    embeddings = self.embedding_model.embed_documents(texts)
                    logger.info(f"成功生成 {len(embeddings)} 个向量")
                except Exception as e:
                    logger.error(f"向量生成失败: {str(e)}")
                    # 使用随机向量作为备选
                    embeddings = [self._generate_random_vector() for _ in texts]
                    logger.warning("使用随机向量作为备选")
            else:
                # 使用随机向量
                embeddings = [self._generate_random_vector() for _ in texts]
                logger.warning("未配置嵌入模型，使用随机向量")
            
            # 将向量添加到分块中
            for i, chunk in enumerate(chunks):
                if hasattr(chunk, 'to_dict'):
                    chunk_dict = chunk.to_dict()
                else:
                    chunk_dict = chunk
                    
                vectorized_chunk = {
                    **chunk_dict,
                    'embedding': embeddings[i],
                    'vector_dimension': len(embeddings[i])
                }
                vectorized_chunks.append(vectorized_chunk)
            
            logger.info(f"分块向量化完成: {len(vectorized_chunks)} 个")
            return vectorized_chunks
            
        except Exception as e:
            logger.error(f"分块向量化失败: {str(e)}")
            raise
    
    async def vectorize_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """向量化实体
        
        Args:
            entities: 实体列表
            
        Returns:
            带有向量的实体列表
        """
        logger.info(f"开始向量化 {len(entities)} 个实体")
        
        vectorized_entities = []
        
        try:
            # 构建实体文本表示
            entity_texts = []
            for entity in entities:
                text_parts = []
                
                # 添加实体名称
                if entity.get('name'):
                    text_parts.append(entity['name'])
                
                # 添加实体类型
                if entity.get('type'):
                    text_parts.append(f"类型:{entity['type']}")
                
                # 添加实体描述
                if entity.get('description'):
                    text_parts.append(entity['description'])
                
                # 添加实体属性
                if entity.get('properties'):
                    for key, value in entity['properties'].items():
                        if isinstance(value, str) and value.strip():
                            text_parts.append(f"{key}:{value}")
                
                entity_text = " ".join(text_parts)
                entity_texts.append(entity_text)
            
            # 批量生成向量
            if self.embedding_model:
                try:
                    embeddings = self.embedding_model.embed_documents(entity_texts)
                    logger.info(f"成功生成 {len(embeddings)} 个实体向量")
                except Exception as e:
                    logger.error(f"实体向量生成失败: {str(e)}")
                    embeddings = [self._generate_random_vector() for _ in entity_texts]
            else:
                embeddings = [self._generate_random_vector() for _ in entity_texts]
            
            # 将向量添加到实体中
            for i, entity in enumerate(entities):
                vectorized_entity = {
                    **entity,
                    'embedding': embeddings[i],
                    'vector_dimension': len(embeddings[i]),
                    'text_representation': entity_texts[i]
                }
                vectorized_entities.append(vectorized_entity)
            
            logger.info(f"实体向量化完成: {len(vectorized_entities)} 个")
            return vectorized_entities
            
        except Exception as e:
            logger.error(f"实体向量化失败: {str(e)}")
            raise
    
    async def store_vectors_to_neo4j(self, vectorized_data: List[Dict[str, Any]], 
                                   node_label: str) -> Dict[str, Any]:
        """将向量数据存储到Neo4j
        
        Args:
            vectorized_data: 包含向量的数据列表
            node_label: Neo4j节点标签
            
        Returns:
            存储结果统计
        """
        logger.info(f"开始将 {len(vectorized_data)} 个{node_label}向量存储到Neo4j")
        
        try:
            stored_count = 0
            batch_size = settings.GRAPH_BATCH_SIZE
            
            # 分批处理
            for i in range(0, len(vectorized_data), batch_size):
                batch = vectorized_data[i:i + batch_size]
                
                # 构建批量插入查询
                query = f"""
                UNWIND $data AS item
                MERGE (n:{node_label} {{id: item.id}})
                SET n += item.properties,
                    n.embedding = item.embedding,
                    n.vector_dimension = item.vector_dimension,
                    n.updated_at = datetime()
                RETURN count(n) as created_count
                """
                
                # 准备数据
                batch_data = []
                for item in batch:
                    node_data = {
                        'id': item.get('id', f"{node_label}_{i}_{len(batch_data)}"),
                        'properties': {
                            'name': item.get('name', ''),
                            'type': item.get('type', ''),
                            'description': item.get('description', ''),
                            'content': item.get('content', ''),
                            **item.get('properties', {})
                        },
                        'embedding': item['embedding'],
                        'vector_dimension': item['vector_dimension']
                    }
                    batch_data.append(node_data)
                
                # 执行查询
                result = self.neo4j_service.execute_write_query(query, {'data': batch_data})
                batch_stored = result[0]['created_count'] if result else 0
                stored_count += batch_stored
                
                logger.info(f"批次 {i//batch_size + 1} 存储完成: {batch_stored} 个节点")
            
            # 创建向量索引（如果不存在）
            await self._ensure_vector_index(node_label)
            
            logger.info(f"向量存储完成: {stored_count} 个{node_label}节点")
            
            return {
                'stored_count': stored_count,
                'node_label': node_label,
                'vector_dimension': vectorized_data[0]['vector_dimension'] if vectorized_data else 0
            }
            
        except Exception as e:
            logger.error(f"向量存储到Neo4j失败: {str(e)}")
            raise
    
    async def _ensure_vector_index(self, node_label: str):
        """确保向量索引存在
        
        Args:
            node_label: 节点标签
        """
        try:
            index_name = f"{node_label.lower()}_vector_index"
            
            # 检查索引是否存在
            check_query = f"""
            SHOW INDEXES 
            WHERE name = '{index_name}'
            """
            
            existing = self.neo4j_service.execute_query(check_query)
            
            if not existing:
                # 创建向量索引
                create_query = f"""
                CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                FOR (n:{node_label}) ON n.embedding
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {settings.VECTOR_SIZE},
                        `vector.similarity_function`: 'cosine'
                    }}
                }}
                """
                
                self.neo4j_service.execute_write_query(create_query)
                logger.info(f"向量索引 {index_name} 创建成功")
            else:
                logger.info(f"向量索引 {index_name} 已存在")
                
        except Exception as e:
            logger.warning(f"创建向量索引失败: {str(e)}")
    
    def calculate_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """计算向量相似度
        
        Args:
            vector1: 第一个向量
            vector2: 第二个向量
            
        Returns:
            余弦相似度值
        """
        try:
            v1 = np.array(vector1)
            v2 = np.array(vector2)
            
            # 计算余弦相似度
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"计算相似度失败: {str(e)}")
            return 0.0
    
    async def find_similar_vectors(self, query_vector: List[float], 
                                 node_label: str, limit: int = 10,
                                 min_similarity: float = 0.7) -> List[Dict[str, Any]]:
        """在Neo4j中查找相似向量
        
        Args:
            query_vector: 查询向量
            node_label: 节点标签
            limit: 返回结果数量限制
            min_similarity: 最小相似度阈值
            
        Returns:
            相似节点列表
        """
        try:
            index_name = f"{node_label.lower()}_vector_index"
            
            query = f"""
            CALL db.index.vector.queryNodes('{index_name}', {limit}, $query_vector)
            YIELD node, score
            WHERE score >= $min_similarity
            RETURN node, score
            ORDER BY score DESC
            """
            
            result = self.neo4j_service.execute_query(query, {
                'query_vector': query_vector,
                'min_similarity': min_similarity
            })
            
            similar_nodes = []
            for record in result:
                similar_nodes.append({
                    'node': dict(record['node']),
                    'similarity': record['score']
                })
            
            logger.info(f"找到 {len(similar_nodes)} 个相似节点")
            return similar_nodes
            
        except Exception as e:
            logger.error(f"查找相似向量失败: {str(e)}")
            return []
    
    def _generate_random_vector(self) -> List[float]:
        """生成随机向量（备选方案）
        
        Returns:
            随机向量
        """
        return np.random.randn(settings.VECTOR_SIZE).tolist()
    
    async def get_vector_statistics(self) -> Dict[str, Any]:
        """获取向量化统计信息
        
        Returns:
            统计信息
        """
        try:
            query = """
            MATCH (n)
            WHERE n.embedding IS NOT NULL
            WITH labels(n) as node_labels, count(n) as count, 
                 avg(n.vector_dimension) as avg_dimension
            RETURN node_labels[0] as label, count, avg_dimension
            """
            
            result = self.neo4j_service.execute_query(query)
            
            statistics = {
                'total_vectorized_nodes': 0,
                'by_label': {}
            }
            
            for record in result:
                label = record['label']
                count = record['count']
                avg_dim = record['avg_dimension']
                
                statistics['by_label'][label] = {
                    'count': count,
                    'avg_dimension': avg_dim
                }
                statistics['total_vectorized_nodes'] += count
            
            statistics['embedding_model'] = settings.DASHSCOPE_EMBEDDING_MODEL
            statistics['vector_dimension'] = settings.VECTOR_SIZE
            
            return statistics
            
        except Exception as e:
            logger.error(f"获取向量统计失败: {str(e)}")
            return {'error': str(e)}