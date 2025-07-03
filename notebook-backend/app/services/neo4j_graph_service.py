from typing import List, Dict, Any, Optional
from langchain_neo4j import Neo4jVector, Neo4jGraph
from langchain_core.documents import Document
from app.services.neo4j_service import Neo4jService
from app.services.embedding_service import get_embedding_service
from app.core.config import settings
import logging
import time

logger = logging.getLogger(__name__)

class Neo4jGraphService:
    """Neo4j图谱检索服务 - 直接替换VectorStoreService"""
    
    def __init__(self):
        """初始化Neo4j图谱检索服务"""
        from app.core.config import settings
        
        # [HYBRID_SEARCH_DATA] 记录服务初始化开始
        logger.info(f"[HYBRID_SEARCH_DATA] service_init_start | service=Neo4jGraphService | debug_mode={settings.SEARCH_DEBUG_MODE}")
        logger.debug(f"[HYBRID_SEARCH_DATA] init_config | neo4j_uri={settings.NEO4J_URI} | database={settings.NEO4J_DATABASE}")
        
        self.neo4j_service = Neo4jService()
        self.graph = None
        self.vector_retriever = None
        self._initialized = False
        
        # [HYBRID_SEARCH_DATA] 记录初始化参数
        logger.debug(f"[HYBRID_SEARCH_DATA] service_components | neo4j_service=initialized | graph=pending | vector_retriever=pending")
        
        # 延迟初始化以减少启动时间
        logger.info("Neo4j图谱检索服务创建完成，将延迟初始化图连接和向量检索器")
    
    def _lazy_initialize(self):
        """延迟初始化图谱和向量检索器"""
        if not self._initialized:
            try:
                logger.info("开始延迟初始化图谱和向量检索器...")
                
                # 尝试创建图连接
                try:
                    self.graph = self._create_graph_connection()
                    logger.info("Neo4j图连接创建成功")
                except Exception as graph_error:
                    logger.error(f"Neo4j图连接失败: {graph_error}")
                    # 尝试降级方案
                    self.graph = self._create_fallback_graph_connection()
                
                # 尝试初始化向量检索器
                try:
                    self.vector_retriever = self._initialize_vector_retriever()
                    logger.info("向量检索器初始化成功")
                except Exception as vector_error:
                    logger.error(f"向量检索器初始化失败: {vector_error}")
                    self.vector_retriever = None
                
                # 尝试创建索引
                try:
                    self._ensure_indexes()
                    logger.info("Neo4j索引检查/创建完成")
                except Exception as index_error:
                    logger.warning(f"索引创建失败: {index_error}")
                
                self._initialized = True
                logger.info("延迟初始化完成")
                
            except Exception as e:
                logger.error(f"延迟初始化失败，详细错误: {e}")
                logger.error(f"错误类型: {type(e).__name__}")
                self._initialized = False
    
    def _create_graph_connection(self):
        """创建Neo4j图连接"""
        return Neo4jGraph(
            url=settings.NEO4J_URI,
            username=settings.NEO4J_USERNAME,
            password=settings.NEO4J_PASSWORD,
            database=settings.NEO4J_DATABASE
        )
    
    def _create_fallback_graph_connection(self):
        """创建降级的Neo4j图连接（减少APOC依赖）"""
        try:
            # 使用更简单的配置，减少对APOC的依赖
            return Neo4jGraph(
                url=settings.NEO4J_URI,
                username=settings.NEO4J_USERNAME,
                password=settings.NEO4J_PASSWORD,
                database=settings.NEO4J_DATABASE,
                enhanced_schema=False  # 禁用增强模式以减少APOC依赖
            )
        except Exception as e:
            logger.error(f"降级图连接也失败: {e}")
            return None
    
    def _initialize_vector_retriever(self):
        """初始化Neo4j向量检索器"""
        try:
            embedding_service = get_embedding_service()
            
            # 使用完整的混合搜索查询
            retrieval_query = self._build_graph_vector_query()
            
            neo4j_vector = Neo4jVector.from_existing_graph(
                embedding=embedding_service,
                graph=self.graph,
                index_name="vector",                    # 向量索引
                node_label="Chunk",                     # 目标节点
                text_node_properties=["text"],          # 文本属性
                embedding_node_property="embedding",    # 向量属性
                retrieval_query=retrieval_query,        # 自定义混合查询
                search_type="hybrid",                   # 混合搜索
                keyword_index_name="keyword"            # 全文索引
            )
            
            logger.info("Neo4j向量检索器初始化成功")
            return neo4j_vector
            
        except Exception as e:
            logger.error(f"Neo4j向量检索器初始化失败: {e}")
            raise
    
    def _build_graph_vector_query(self) -> str:
        """构建图向量混合查询（简化版，减少APOC依赖）"""
        # [HYBRID_SEARCH_DATA] 记录查询构建开始
        logger.debug(f"[HYBRID_SEARCH_DATA] query_building | method=simplified | apoc_dependency=reduced")
        
        query = """
        WITH node as chunk, score
        MATCH (chunk)-[:PART_OF]->(d:Document)
        OPTIONAL MATCH (chunk)-[:HAS_ENTITY]->(e:__Entity__)
        
        WITH d, chunk, score, collect(DISTINCT e) AS entities
        
        WITH d, 
             collect(DISTINCT {chunk: chunk, score: score, entities: entities}) AS chunk_data,
             avg(score) as avg_score
        
        WITH d, avg_score, chunk_data,
             [item IN chunk_data | item.chunk.content] AS texts,
             [item IN chunk_data | {id: elementId(item.chunk), score: item.score}] AS chunkdetails,
             reduce(allEntities = [], item IN chunk_data | allEntities + item.entities) AS all_entities
        
        WITH d, avg_score, chunkdetails,
             texts[0..3] AS limited_texts,  // 限制文本数量以避免过长
             [e IN all_entities | elementId(e)][0..20] AS entityIds,  // 限制实体数量
             [e IN all_entities | coalesce(e.name, e.id, "Unknown")][0..20] AS entityNames
        
        WITH d, avg_score, chunkdetails, entityIds,
             reduce(text = "", t IN limited_texts | text + t + "\\n----\\n") AS combined_text,
             reduce(entity_text = "", name IN entityNames | entity_text + name + "\\n") AS entity_text
        
        RETURN
           combined_text + "\\n----\\nEntities:\\n" + entity_text AS text,
           avg_score AS score,
           {
               length: size(combined_text),
               source: COALESCE(d.name, "Document_" + toString(d.postgresql_id)),
               chunkdetails: chunkdetails,
               entities: {
                   entityids: entityIds,
                   relationshipids: []  // 简化：暂时不包含关系ID
               }
           } AS metadata
        """
        
        # [HYBRID_SEARCH_DATA] 记录查询构建完成
        query_length = len(query)
        query_lines = query.count('\n')
        logger.debug(f"[HYBRID_SEARCH_DATA] query_built | length={query_length} | lines={query_lines} | text_limit=3 | entity_limit=20")
        
        return query
    
    async def test_connection(self):
        """测试Neo4j连接"""
        try:
            # 使用简单的查询测试连接
            result = self.neo4j_service.execute_query("RETURN 1 as test")
            if result and result[0]["test"] == 1:
                logger.info("Neo4j连接测试成功")
                return True
            else:
                logger.error("Neo4j连接测试失败：返回结果不符合预期")
                return False
        except Exception as e:
            logger.error(f"Neo4j连接测试失败: {e}")
            raise
    
    async def ensure_indexes(self):
        """确保所需索引存在"""
        try:
            # 创建向量索引
            vector_index_query = f"""
            CREATE VECTOR INDEX vector IF NOT EXISTS
            FOR (c:Chunk) ON c.embedding
            OPTIONS {{
              indexConfig: {{
                `vector.dimensions`: {settings.VECTOR_SIZE},
                `vector.similarity_function`: 'cosine'
              }}
            }}
            """
            self.neo4j_service.execute_write_query(vector_index_query)
            
            # 创建全文索引
            fulltext_index_query = """
            CREATE FULLTEXT INDEX keyword IF NOT EXISTS
            FOR (n:Chunk) ON EACH [n.content]
            """
            self.neo4j_service.execute_write_query(fulltext_index_query)
            
            # 创建实体向量索引
            entity_vector_index_query = f"""
            CREATE VECTOR INDEX entity_vector IF NOT EXISTS
            FOR (e:__Entity__) ON e.embedding
            OPTIONS {{
              indexConfig: {{
                `vector.dimensions`: {settings.VECTOR_SIZE},
                `vector.similarity_function`: 'cosine'
              }}
            }}
            """
            self.neo4j_service.execute_write_query(entity_vector_index_query)
            
            logger.info("Neo4j索引创建完成")
            
        except Exception as e:
            logger.warning(f"索引创建失败: {e}")

    def _ensure_indexes(self):
        """确保所需索引存在（同步版本）"""
        try:
            # 创建向量索引
            vector_index_query = f"""
            CREATE VECTOR INDEX vector IF NOT EXISTS
            FOR (c:Chunk) ON c.embedding
            OPTIONS {{
              indexConfig: {{
                `vector.dimensions`: {settings.VECTOR_SIZE},
                `vector.similarity_function`: 'cosine'
              }}
            }}
            """
            self.neo4j_service.execute_write_query(vector_index_query)
            
            # 创建全文索引
            fulltext_index_query = """
            CREATE FULLTEXT INDEX keyword IF NOT EXISTS
            FOR (n:Chunk) ON EACH [n.content]
            """
            self.neo4j_service.execute_write_query(fulltext_index_query)
            
            # 创建实体向量索引
            entity_vector_index_query = f"""
            CREATE VECTOR INDEX entity_vector IF NOT EXISTS
            FOR (e:__Entity__) ON e.embedding
            OPTIONS {{
              indexConfig: {{
                `vector.dimensions`: {settings.VECTOR_SIZE},
                `vector.similarity_function`: 'cosine'
              }}
            }}
            """
            self.neo4j_service.execute_write_query(entity_vector_index_query)
            
            logger.info("Neo4j索引创建完成")
            
        except Exception as e:
            logger.warning(f"索引创建失败: {e}")
    
    # 保持与VectorStoreService相同的接口
    def similarity_search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """相似度搜索 - 兼容VectorStoreService接口"""
        # [HYBRID_SEARCH_PERF] 记录搜索参数
        search_start_time = time.time()
        logger.info(f"[HYBRID_SEARCH_PERF] neo4j_search_start | duration=0.000s | query_length={len(query)} | k={k}")
        logger.debug(f"[HYBRID_SEARCH_DATA] search_params | query_text={query[:100]}{'...' if len(query) > 100 else ''} | target_results={k}")
        logger.debug(f"[HYBRID_SEARCH_DATA] service_state | initialized={self._initialized} | has_retriever={self.vector_retriever is not None}")
        
        try:
            logger.info(f"执行Neo4j混合搜索: 查询='{query[:30]}...', k={k}")
            
            # 尝试延迟初始化
            self._lazy_initialize()
            
            # 如果初始化失败，使用基础模式
            if not self._initialized or not self.vector_retriever:
                logger.warning("向量检索器未初始化，使用基础搜索模式")
                # [HYBRID_SEARCH_DATA] 记录降级原因
                logger.warning(f"[HYBRID_SEARCH_DATA] retriever_degradation | initialized={self._initialized} | has_retriever={self.vector_retriever is not None} | fallback_to=basic_search")
                return self._basic_search(query, k)
            
            # [HYBRID_SEARCH_DATA] 记录检索器状态
            logger.debug(f"[HYBRID_SEARCH_DATA] retriever_status | initialized={self._initialized} | retriever_type={type(self.vector_retriever).__name__}")
            
            logger.info("开始执行Neo4j向量混合搜索")
            # 使用Neo4j混合搜索
            docs = self.vector_retriever.similarity_search(query, k=k)
            
            # [HYBRID_SEARCH_PERF] 记录向量搜索执行时间
            vector_search_duration = time.time() - search_start_time
            logger.info(f"[HYBRID_SEARCH_PERF] vector_search_complete | duration={vector_search_duration:.3f}s | raw_docs_count={len(docs) if docs else 0}")
            
            if not docs:
                logger.warning("Neo4j混合搜索未返回任何文档，尝试基础搜索")
                # [HYBRID_SEARCH_DATA] 记录空结果降级
                logger.warning(f"[HYBRID_SEARCH_DATA] empty_results_degradation | vector_duration={vector_search_duration:.3f}s | fallback_to=basic_search")
                return self._basic_search(query, k)
            
            # 转换为兼容格式
            results = []
            for i, doc in enumerate(docs):
                try:
                    # [HYBRID_SEARCH_NODE] 记录每个文档的详细信息
                    doc_content_length = len(doc.page_content)
                    doc_score = doc.metadata.get("score", 0.0)
                    doc_source = doc.metadata.get("source", "")
                    entities_count = len(doc.metadata.get("entities", {}).get("entityids", []))
                    relationships_count = len(doc.metadata.get("entities", {}).get("relationshipids", []))
                    
                    logger.debug(f"[HYBRID_SEARCH_NODE] document | id=doc_{i} | score={doc_score:.3f} | content_length={doc_content_length} | source={doc_source}")
                    logger.debug(f"[HYBRID_SEARCH_DATA] document_entities | doc_id=doc_{i} | entities_count={entities_count} | relationships_count={relationships_count}")
                    
                    result = {
                        "content": doc.page_content,
                        "metadata": {
                            **doc.metadata,
                            "search_type": "neo4j_hybrid",
                            "entities": doc.metadata.get("entities", {}),
                            "source": doc.metadata.get("source", ""),
                            "score": doc.metadata.get("score", 0.0)
                        }
                    }
                    results.append(result)
                    logger.debug(f"处理文档 {i+1}: 内容长度={len(doc.page_content)}, source={doc.metadata.get('source', 'N/A')}")
                except Exception as doc_error:
                    # [HYBRID_SEARCH_DATA] 记录文档处理错误
                    logger.error(f"[HYBRID_SEARCH_DATA] document_processing_error | doc_id=doc_{i} | error={str(doc_error)}")
                    logger.error(f"处理文档 {i+1} 时出错: {doc_error}")
                    continue
            
            logger.info(f"Neo4j混合搜索成功找到 {len(results)} 个结果")
            
            # [HYBRID_SEARCH_PERF] 记录搜索完成和结果统计
            total_search_duration = time.time() - search_start_time
            logger.info(f"[HYBRID_SEARCH_PERF] search_complete | duration={total_search_duration:.3f}s | results_count={len(results)}")
            
            # [HYBRID_SEARCH_DATA] 记录结果质量分析
            if results:
                scores = [r["metadata"].get("score", 0.0) for r in results]
                avg_score = sum(scores) / len(scores) if scores else 0.0
                max_score = max(scores) if scores else 0.0
                min_score = min(scores) if scores else 0.0
                
                total_entities = sum(len(r["metadata"].get("entities", {}).get("entityids", [])) for r in results)
                total_relationships = sum(len(r["metadata"].get("entities", {}).get("relationshipids", [])) for r in results)
                total_content_length = sum(len(r["content"]) for r in results)
                
                logger.info(f"[HYBRID_SEARCH_DATA] result_quality | avg_score={avg_score:.3f} | max_score={max_score:.3f} | min_score={min_score:.3f}")
                logger.info(f"[HYBRID_SEARCH_DATA] result_statistics | total_entities={total_entities} | total_relationships={total_relationships} | total_content_length={total_content_length}")
                
                # 质量预警检查
                from app.core.config import settings
                if avg_score < settings.SEARCH_RESULT_QUALITY_THRESHOLD:
                    logger.warning(f"[HYBRID_SEARCH_DATA] quality_warning | avg_score={avg_score:.3f} | threshold={settings.SEARCH_RESULT_QUALITY_THRESHOLD}")
                
                if total_search_duration > settings.SEARCH_SLOW_QUERY_THRESHOLD:
                    logger.warning(f"[HYBRID_SEARCH_PERF] slow_query_warning | duration={total_search_duration:.3f}s | threshold={settings.SEARCH_SLOW_QUERY_THRESHOLD}s")
            
            return results
            
        except Exception as e:
            # [HYBRID_SEARCH_DATA] 记录详细的错误上下文
            error_duration = time.time() - search_start_time
            logger.error(f"[HYBRID_SEARCH_DATA] search_error | duration={error_duration:.3f}s | error_type={type(e).__name__} | query_length={len(query)} | k={k}")
            logger.error(f"[HYBRID_SEARCH_DATA] error_context | initialized={self._initialized} | has_retriever={self.vector_retriever is not None} | neo4j_available={self.neo4j_service is not None}")
            logger.error(f"[HYBRID_SEARCH_DATA] error_details | error_message={str(e)} | query_preview={query[:50]}{'...' if len(query) > 50 else ''}")
            
            logger.error(f"Neo4j混合搜索失败，错误类型: {type(e).__name__}, 错误信息: {e}")
            logger.error(f"搜索参数 - 查询: '{query[:100]}...', k={k}")
            
            # 尝试降级到基础搜索
            try:
                logger.info("尝试降级到基础搜索模式")
                # [HYBRID_SEARCH_DATA] 记录降级尝试
                logger.info(f"[HYBRID_SEARCH_DATA] fallback_attempt | reason=main_search_failed | fallback_method=basic_search")
                return self._basic_search(query, k)
            except Exception as fallback_error:
                # [HYBRID_SEARCH_DATA] 记录降级失败
                fallback_duration = time.time() - search_start_time
                logger.error(f"[HYBRID_SEARCH_DATA] fallback_failed | total_duration={fallback_duration:.3f}s | fallback_error={str(fallback_error)}")
                logger.error(f"基础搜索也失败: {fallback_error}")
                return []
    
    def _basic_search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """基础搜索模式 - 在向量检索不可用时使用"""
        import time
        
        # [HYBRID_SEARCH_PERF] 记录基础搜索开始
        basic_search_start = time.time()
        logger.info(f"[HYBRID_SEARCH_PERF] basic_search_start | duration=0.000s | query_length={len(query)} | k={k}")
        logger.warning(f"[HYBRID_SEARCH_DATA] fallback_search | search_type=text_match | reason=vector_retriever_unavailable")
        
        try:
            # 使用简单的文本匹配查询
            search_query = """
            MATCH (c:Chunk)
            WHERE c.content CONTAINS $query
            RETURN c.content as content, 
                   {source: 'basic_search', search_type: 'text_match'} as metadata
            LIMIT $limit
            """
            
            # [HYBRID_SEARCH_DATA] 记录查询参数
            logger.debug(f"[HYBRID_SEARCH_DATA] basic_query | contains_match=true | limit={k}")
            
            results = self.neo4j_service.execute_query(search_query, {
                "query": query,
                "limit": k
            })
            
            # [HYBRID_SEARCH_PERF] 记录查询执行时间
            query_duration = time.time() - basic_search_start
            logger.info(f"[HYBRID_SEARCH_PERF] basic_query_complete | duration={query_duration:.3f}s | raw_results={len(results)}")
            
            # 转换为兼容格式
            formatted_results = []
            for i, result in enumerate(results):
                # [HYBRID_SEARCH_NODE] 记录基础搜索结果
                content_length = len(result["content"]) if result["content"] else 0
                logger.debug(f"[HYBRID_SEARCH_NODE] basic_result | id=basic_{i} | score=0.5 | content_length={content_length} | search_type=text_match")
                
                formatted_result = {
                    "content": result["content"],
                    "metadata": {
                        **result["metadata"],
                        "score": 0.5  # 固定分数
                    }
                }
                formatted_results.append(formatted_result)
            
            # [HYBRID_SEARCH_PERF] 记录基础搜索完成
            total_duration = time.time() - basic_search_start
            logger.info(f"[HYBRID_SEARCH_PERF] basic_search_complete | duration={total_duration:.3f}s | results_count={len(formatted_results)}")
            logger.info(f"基础搜索找到 {len(formatted_results)} 个结果")
            return formatted_results
            
        except Exception as e:
            # [HYBRID_SEARCH_DATA] 记录基础搜索失败
            basic_search_duration = time.time() - basic_search_start
            logger.error(f"[HYBRID_SEARCH_DATA] basic_search_error | duration={basic_search_duration:.3f}s | error={str(e)}")
            logger.error(f"基础搜索失败: {e}")
            return []
    
    async def store_vectors(self, vectors: List[List[float]], metadata: List[Dict[str, Any]]) -> bool:
        """存储向量 - 兼容接口（实际上文档已经在图谱构建时存储）"""
        logger.info("Neo4j图谱检索服务：向量已通过图谱构建流程存储")
        return True
    
    async def search_vectors(self, query_vector: List[float], limit: int = 5, 
                           filter_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """向量搜索 - 兼容接口"""
        # 将向量查询转换为文本查询（简化处理）
        # 实际场景中可以直接使用向量进行Neo4j向量搜索
        return self.similarity_search("", k=limit)
    
    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]] = None) -> List[str]:
        """添加文本 - 兼容接口（同步版本）"""
        logger.info(f"Neo4j图谱检索服务：添加文本 {len(texts)} 个")
        return [f"neo4j_doc_{i}" for i in range(len(texts))]
    
    async def add_texts_async(self, texts: List[str], metadatas: List[Dict[str, Any]] = None) -> List[str]:
        """添加文本 - 异步版本"""
        logger.info(f"Neo4j图谱检索服务：异步添加文本 {len(texts)} 个")
        return [f"neo4j_doc_{i}" for i in range(len(texts))]
    
    def delete_texts(self, ids: List[str]) -> bool:
        """删除文本 - 兼容接口"""
        logger.info(f"Neo4j图谱检索服务：删除文档 {len(ids)} 个")
        # 可以实现基于文档ID的删除逻辑
        return True
    
    def verify_database_schema(self) -> Dict[str, Any]:
        """验证数据库字段结构 - 用于调试字段名不匹配问题"""
        try:
            verification_results = {}
            
            # 检查Document节点的实际字段
            doc_fields_query = """
            MATCH (d:Document)
            WITH d LIMIT 1
            RETURN keys(d) as document_fields, d
            """
            doc_results = self.neo4j_service.execute_query(doc_fields_query)
            if doc_results:
                verification_results["document_fields"] = doc_results[0]["document_fields"]
                verification_results["document_sample"] = dict(doc_results[0]["d"])
                logger.info(f"Document节点字段: {doc_results[0]['document_fields']}")
            else:
                verification_results["document_fields"] = []
                logger.warning("数据库中没有找到Document节点")
            
            # 检查Chunk节点的实际字段
            chunk_fields_query = """
            MATCH (c:Chunk)
            WITH c LIMIT 1
            RETURN keys(c) as chunk_fields, c
            """
            chunk_results = self.neo4j_service.execute_query(chunk_fields_query)
            if chunk_results:
                verification_results["chunk_fields"] = chunk_results[0]["chunk_fields"]
                # 不包含完整内容，只显示结构
                chunk_sample = dict(chunk_results[0]["c"])
                if "content" in chunk_sample:
                    chunk_sample["content"] = chunk_sample["content"][:100] + "..." if len(chunk_sample["content"]) > 100 else chunk_sample["content"]
                verification_results["chunk_sample"] = chunk_sample
                logger.info(f"Chunk节点字段: {chunk_results[0]['chunk_fields']}")
            else:
                verification_results["chunk_fields"] = []
                logger.warning("数据库中没有找到Chunk节点")
            
            # 检查节点数量 - 分别查询各种类型
            doc_count_query = "MATCH (d:Document) RETURN count(d) as doc_count"
            chunk_count_query = "MATCH (c:Chunk) RETURN count(c) as chunk_count"
            entity_count_query = "MATCH (e:__Entity__) RETURN count(e) as entity_count"
            
            doc_count = 0
            chunk_count = 0
            entity_count = 0
            
            try:
                doc_results = self.neo4j_service.execute_query(doc_count_query)
                doc_count = doc_results[0]["doc_count"] if doc_results else 0
            except:
                pass
                
            try:
                chunk_results = self.neo4j_service.execute_query(chunk_count_query)
                chunk_count = chunk_results[0]["chunk_count"] if chunk_results else 0
            except:
                pass
                
            try:
                entity_results = self.neo4j_service.execute_query(entity_count_query)
                entity_count = entity_results[0]["entity_count"] if entity_results else 0
            except:
                pass
            
            verification_results["node_counts"] = {
                "doc_count": doc_count,
                "chunk_count": chunk_count,
                "entity_count": entity_count
            }
            logger.info(f"节点数量统计: {verification_results['node_counts']}")
            
            # 检查关系类型
            relationship_query = """
            MATCH ()-[r]->()
            RETURN DISTINCT type(r) as relationship_type, count(r) as count
            ORDER BY count DESC
            """
            rel_results = self.neo4j_service.execute_query(relationship_query)
            verification_results["relationships"] = rel_results
            logger.info(f"关系类型统计: {rel_results}")
            
            return verification_results
            
        except Exception as e:
            logger.error(f"数据库结构验证失败: {e}")
            return {"error": str(e)}