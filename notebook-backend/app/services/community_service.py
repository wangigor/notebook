# -*- coding: utf-8 -*-
"""
社区检测服务
实现基于GDS Leiden算法的社区检测和生成功能
"""
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import pandas as pd
import numpy as np

from graphdatascience import GraphDataScience
from app.core.config import settings
from app.utils.file_utils import to_serializable
from app.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)

class CommunityService:
    """社区检测服务类"""
    
    def __init__(self, gds: GraphDataScience):
        """
        初始化社区服务
        
        Args:
            gds: GraphDataScience实例
        """
        self.gds = gds
        self.embedding_model = None
        self.llm_model = None
        
        # 配置参数
        self.max_community_levels = 3
        self.min_community_size = 1
        self.max_workers = 10
        self.llm_model_name = "openai_gpt_4o"
        
    def _init_models(self):
        """初始化嵌入模型和LLM模型"""
        if not self.embedding_model:
            # 使用统一的嵌入服务
            self.embedding_model = get_embedding_service()
        
        if not self.llm_model:
            from app.services.llm_client_service import LLMClientService
            llm_service = LLMClientService()
            # 使用处理专用的LLM实例，默认不使用流式响应
            self.llm_model = llm_service.get_processing_llm(streaming=False)
    
    def _safe_dataframe_length(self, df: pd.DataFrame) -> int:
        """安全获取DataFrame长度"""
        if df is None or df.empty:
            return 0
        return len(df.index)
    
    def _safe_dataframe_get(self, df: pd.DataFrame, index: int = 0, key: str = None, default: Any = 0) -> Any:
        """安全获取DataFrame中的值"""
        if df is None or df.empty:
            return default
        try:
            if key:
                return df.iloc[index].get(key, default)
            else:
                return df.iloc[index]
        except (IndexError, KeyError):
            return default
    
    def _is_dataframe_empty(self, df: pd.DataFrame) -> bool:
        """检查DataFrame是否为空"""
        return df is None or df.empty
    
    def _dataframe_to_records(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """安全地将DataFrame转换为记录列表"""
        if self._is_dataframe_empty(df):
            return []
        return df.to_dict('records')
    
    def clear_communities(self) -> Dict[str, Any]:
        """
        阶段1：数据清理
        删除所有现有社区节点和关系
        
        Returns:
            Dict[str, Any]: 包含状态、耗时和删除的社区数量的字典
                - status: 操作状态 ("success" 或 "failed")
                - duration: 操作耗时（秒）
                - deleted_communities: 删除的社区节点数量
        """
        logger.info("开始清理现有社区数据")
        start_time = time.time()
        
        try:
            # 删除所有社区节点和关系
            result = self.gds.run_cypher("""
                MATCH (c:`__Community__`) 
                DETACH DELETE c
            """)
            
            # 清除实体上的社区属性
            result2 = self.gds.run_cypher("""
                MATCH (e:Entity) 
                REMOVE e.communities
            """)
            
            duration = time.time() - start_time
            logger.info(f"社区数据清理完成，耗时: {duration:.2f}秒")
            
            return to_serializable({
                "status": "success",
                "duration": duration,
                "deleted_communities": self._safe_dataframe_length(result)
            })
            
        except Exception as e:
            logger.error(f"清理社区数据失败: {str(e)}")
            logger.error(f"DataFrame类型: {type(result) if 'result' in locals() else 'N/A'}")
            if 'result' in locals() and hasattr(result, 'shape'):
                logger.error(f"DataFrame形状: {result.shape}")
            raise
    
    def create_community_graph_projection(self) -> Dict[str, Any]:
        """
        创建用于社区检测的图投影（新版：使用Cypher聚合函数gds.graph.project，支持关系属性和无向图）
        """
        logger.info("开始创建社区检测图投影（新版：Cypher聚合函数）")
        start_time = time.time()
        
        # 检查可用内存
        memory_info = self.gds.debug.sysInfo()
        logger.info(f"可用内存: {memory_info.get('availableMemory', 'unknown')}")
        
        # 如果已存在同名图，先删除
        try:
            existing_graph = self.gds.graph.get("communities")
            if existing_graph:
                logger.info("检测到已存在同名图投影，先删除...")
                self.gds.graph.drop(existing_graph)
                logger.info("已删除同名图投影")
        except Exception as e:
            logger.info(f"未检测到同名图投影或删除时出错: {str(e)}")
        
        # 使用Cypher聚合函数gds.graph.project进行图投影，支持关系属性weight和无向图
        logger.info("使用Cypher聚合函数gds.graph.project进行图投影...")
        projection_result = self.gds.run_cypher("""
            MATCH (source:Entity)
            MATCH (source)-[r]->(target:Entity)
            WITH source, target, count(r) AS weight
            WITH gds.graph.project(
                'communities',
                source,
                target,
                { relationshipProperties: { weight: weight } },
                { undirectedRelationshipTypes: ['*'] }
            ) AS g
            RETURN g.graphName AS graphName, g.nodeCount AS nodeCount, g.relationshipCount AS relationshipCount, g.projectMillis AS projectMillis
        """)
        
        duration = time.time() - start_time
        logger.info(f"图投影创建完成，耗时: {duration:.2f}秒")
        
        if not self._is_dataframe_empty(projection_result):
            graph_info = projection_result.iloc[0]
            graph_info = to_serializable(graph_info.to_dict() if hasattr(graph_info, 'to_dict') else dict(graph_info))
            return to_serializable({
                "status": "success",
                "duration": duration,
                "graph_name": graph_info.get("graphName"),
                "node_count": graph_info.get("nodeCount"),
                "relationship_count": graph_info.get("relationshipCount"),
                "project_millis": graph_info.get("projectMillis"),
                "optimization_used": True
            })
        else:
            raise Exception("图投影创建失败，未返回结果")
                   
    def detect_communities(self) -> Dict[str, Any]:
        """
        阶段3：社区检测
        使用Leiden算法检测社区
        """
        logger.info("开始社区检测")
        start_time = time.time()
        
        try:
            # 获取图对象
            graph = self.gds.graph.get("communities")
            
            # 执行Leiden算法
            leiden_result = self.gds.leiden.write(
                graph,
                writeProperty="communities",
                includeIntermediateCommunities=True,
                relationshipWeightProperty="weight",
                maxLevels=self.max_community_levels,
                minCommunitySize=self.min_community_size
            )
            
            duration = time.time() - start_time
            logger.info(f"社区检测完成，耗时: {duration:.2f}秒")
            
            # 统计实际检测到的社区数量
            communities_count_result = self.gds.run_cypher("""
                MATCH (e:Entity)
                WHERE e.communities IS NOT NULL
                UNWIND e.communities AS community_id
                RETURN count(DISTINCT community_id) as unique_communities
            """)
            
            actual_communities = 0
            if not self._is_dataframe_empty(communities_count_result):
                actual_communities = communities_count_result.iloc[0]["unique_communities"]
            
            return to_serializable({
                "status": "success",
                "duration": duration,
                "communities_detected": actual_communities,
                "modularity": leiden_result.get("modularity", 0.0)
            })
            
        except Exception as e:
            logger.error(f"社区检测失败: {str(e)}")
            raise
    
    def create_community_nodes(self) -> Dict[str, Any]:
        """
        阶段4：社区节点创建
        创建社区节点和层级关系
        """
        logger.info("开始创建社区节点")
        start_time = time.time()
        
        try:
            # 创建社区节点和关系
            result = self.gds.run_cypher("""
                MATCH (e:Entity)
                WHERE e.communities is NOT NULL
                UNWIND range(0, size(e.communities) - 1, 1) AS index
                WITH e, index
                FOREACH (ignoreMe IN CASE WHEN index = 0 THEN [1] ELSE [] END |
                  MERGE (c:`__Community__` {id: toString(index) + '-' + toString(e.communities[index])})
                  ON CREATE SET c.level = index
                  MERGE (e)-[:IN_COMMUNITY]->(c)
                )
                FOREACH (ignoreMe IN CASE WHEN index > 0 THEN [1] ELSE [] END |
                  MERGE (current:`__Community__` {id: toString(index) + '-' + toString(e.communities[index])})
                  ON CREATE SET current.level = index
                  MERGE (previous:`__Community__` {id: toString(index - 1) + '-' + toString(e.communities[index - 1])})
                  MERGE (previous)-[:PARENT_COMMUNITY]->(current)
                )
                RETURN count(DISTINCT e) as total_processed
            """)
            
            duration = time.time() - start_time
            logger.info(f"社区节点创建完成，耗时: {duration:.2f}秒")
            
            return to_serializable({
                "status": "success",
                "duration": duration,
                "entities_processed": self._safe_dataframe_get(result, key="total_processed")
            })
            
        except Exception as e:
            logger.error(f"创建社区节点失败: {str(e)}")
            logger.error(f"result类型: {type(result) if 'result' in locals() else 'N/A'}")
            if 'result' in locals() and hasattr(result, 'shape'):
                logger.error(f"result形状: {result.shape}")
            raise
    
    def calculate_community_properties(self) -> Dict[str, Any]:
        """
        阶段5：属性计算
        计算社区权重和排名
        
        Returns:
            Dict[str, Any]: 包含状态、耗时和计算结果的字典
                - status: 操作状态 ("success" 或 "failed")
                - duration: 操作耗时（秒）
                - communities_with_weight: 计算权重的社区数量
                - communities_with_rank: 计算排名的社区数量
        """
        logger.info("开始计算社区属性")
        start_time = time.time()
        
        try:
            # 计算社区权重
            weight_result = self.gds.run_cypher("""
                MATCH (n:`__Community__`)<-[:IN_COMMUNITY]-()<-[:HAS_ENTITY]-(c)
                WITH n, count(distinct c) AS chunkCount
                SET n.weight = chunkCount
                RETURN count(*) as communities_updated
            """)
            
            # 计算社区排名
            rank_result = self.gds.run_cypher("""
                MATCH (c:__Community__)<-[:IN_COMMUNITY*]-(e:Entity)<-[:HAS_ENTITY]-(chunk:Chunk)-[:PART_OF]->(d:Document)
                WITH c, count(distinct d) AS rank
                SET c.community_rank = rank
                RETURN count(*) as communities_ranked
            """)
            
            duration = time.time() - start_time
            logger.info(f"社区属性计算完成，耗时: {duration:.2f}秒")
            
            return to_serializable({
                "status": "success",
                "duration": duration,
                "communities_with_weight": self._safe_dataframe_get(weight_result, key="communities_updated"),
                "communities_with_rank": self._safe_dataframe_get(rank_result, key="communities_ranked")
            })
            
        except Exception as e:
            logger.error(f"计算社区属性失败: {str(e)}")
            logger.error(f"weight_result类型: {type(weight_result) if 'weight_result' in locals() else 'N/A'}")
            logger.error(f"rank_result类型: {type(rank_result) if 'rank_result' in locals() else 'N/A'}")
            if 'weight_result' in locals() and hasattr(weight_result, 'shape'):
                logger.error(f"weight_result形状: {weight_result.shape}")
            if 'rank_result' in locals() and hasattr(rank_result, 'shape'):
                logger.error(f"rank_result形状: {rank_result.shape}")
            raise
    
    def generate_community_summaries(self) -> Dict[str, Any]:
        """
        阶段6：摘要生成
        使用LLM生成社区摘要
        """
        logger.info("开始生成社区摘要")
        start_time = time.time()
        
        try:
            self._init_models()
            
            # 获取需要生成摘要的社区
            communities = self.gds.run_cypher("""
                MATCH (c:`__Community__`)<-[:IN_COMMUNITY]-(e)
                WHERE c.level = 0
                WITH c, collect(e) AS nodes
                WHERE size(nodes) > 1
                CALL apoc.path.subgraphAll(nodes[0], {
                    whitelistNodes:nodes
                })
                YIELD relationships
                RETURN c.id AS communityId,
                    [n in nodes | {id: n.id, description: n.description, type: [el in labels(n) WHERE el <> '__Entity__'][0]}] AS nodes,
                    [r in relationships | {start: startNode(r).id, type: type(r), end: endNode(r).id}] AS rels
            """)
            
            if self._is_dataframe_empty(communities):
                logger.info("没有找到需要生成摘要的社区")
                return to_serializable({
                    "status": "success",
                    "duration": time.time() - start_time,
                    "summaries_generated": 0
                })
            
            # 并发生成摘要
            summaries = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [
                    executor.submit(self._generate_single_summary, community) 
                    for community in self._dataframe_to_records(communities)
                ]
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            summaries.append(result)
                    except Exception as e:
                        logger.error(f"生成摘要失败: {str(e)}")
            
            # 批量更新社区摘要
            if summaries:
                self._update_community_summaries(summaries)
            
            duration = time.time() - start_time
            logger.info(f"社区摘要生成完成，耗时: {duration:.2f}秒，生成了 {len(summaries)} 个摘要")
            
            return to_serializable({
                "status": "success",
                "duration": duration,
                "summaries_generated": len(summaries)
            })
            
        except Exception as e:
            logger.error(f"生成社区摘要失败: {str(e)}")
            raise
    
    def _generate_single_summary(self, community: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """生成单个社区的摘要"""
        try:
            community_id = community["communityId"]
            nodes = community["nodes"]
            rels = community["rels"]
            
            # 构建提示词
            prompt = self._build_summary_prompt(nodes, rels)
            
            # 调用LLM生成摘要
            response = self.llm_model.invoke(prompt)
            content = response.content
            
            # 解析响应
            title, summary = self._parse_summary_response(content)
            
            return {
                "community_id": community_id,
                "title": title,
                "summary": summary
            }
            
        except Exception as e:
            community_id = community.get('communityId', 'unknown') if isinstance(community, dict) else 'unknown'
            logger.error(f"生成社区 {community_id} 摘要失败: {str(e)}")
            return None
    
    def _build_summary_prompt(self, nodes: List[Dict], rels: List[Dict]) -> str:
        """构建摘要生成提示词"""
        nodes_text = "\n".join([
            f"id: {node['id']}, type: {node['type']}, description: {node.get('description', '')}"
            for node in nodes
        ])
        
        rels_text = "\n".join([
            f"({rel['start']})-[:{rel['type']}]->({rel['end']})"
            for rel in rels
        ])
        
        return f"""Based on the provided nodes and relationships that belong to the same graph community,
generate following output in exact format
title: A concise title, no more than 4 words,
summary: A natural language summary of the information

注意！！！使用中文返回。

Nodes are:
{nodes_text}

Relationships are:
{rels_text}
"""
    
    def _parse_summary_response(self, response: str) -> Tuple[str, str]:
        """解析LLM响应，提取标题和摘要"""
        lines = response.strip().split('\n')
        title = ""
        summary = ""
        
        for line in lines:
            if line.startswith('title:'):
                title = line.replace('title:', '').strip()
            elif line.startswith('summary:'):
                summary = line.replace('summary:', '').strip()
        
        return title, summary
    
    def _update_community_summaries(self, summaries: List[Dict[str, str]]):
        """批量更新社区摘要"""
        for summary in summaries:
            self.gds.run_cypher("""
                MATCH (c:`__Community__` {id: $community_id})
                SET c.title = $title, c.summary = $summary
            """, {
                "community_id": summary["community_id"],
                "title": summary["title"],
                "summary": summary["summary"]
            })
    
    def create_community_embeddings(self) -> Dict[str, Any]:
        """
        阶段7：向量化
        生成社区嵌入向量
        """
        logger.info("开始生成社区嵌入向量")
        start_time = time.time()
        
        try:
            self._init_models()
            
            # 获取需要向量化的社区
            communities = self.gds.run_cypher("""
                MATCH (c:`__Community__`)
                WHERE c.summary IS NOT NULL AND c.embedding IS NULL
                RETURN c.id as community_id, c.summary as summary
            """)
            
            if self._is_dataframe_empty(communities):
                logger.info("没有找到需要向量化的社区")
                return to_serializable({
                    "status": "success",
                    "duration": time.time() - start_time,
                    "embeddings_created": 0
                })
            
            # 批量生成嵌入向量
            batch_size = 100
            embeddings_created = 0
            
            for i in range(0, len(communities), batch_size):
                batch = communities.iloc[i:i + batch_size]
                summaries = [row["summary"] for _, row in batch.iterrows()]
                
                # 生成嵌入向量
                embeddings = self.embedding_model.embed_documents(summaries)
                
                # 批量更新数据库
                for j, (_, community) in enumerate(batch.iterrows()):
                    # embedding = embeddings[j].tolist()  # 原始代码保留注释
                    
                    # 类型检查和条件转换：处理list和numpy数组两种类型
                    embedding_raw = embeddings[j]
                    try:
                        if isinstance(embedding_raw, np.ndarray):
                            # 如果是numpy数组，调用tolist()转换
                            embedding = embedding_raw.tolist()
                            logger.debug(f"嵌入向量类型: numpy.ndarray, 长度: {len(embedding)}")
                        elif isinstance(embedding_raw, list):
                            # 如果已经是list，直接使用
                            embedding = embedding_raw
                            logger.debug(f"嵌入向量类型: list, 长度: {len(embedding)}")
                        else:
                            # 其他类型，尝试转换为list
                            embedding = list(embedding_raw)
                            logger.warning(f"嵌入向量类型未知: {type(embedding_raw)}, 已转换为list")
                        
                        # 验证嵌入向量有效性
                        if not embedding or len(embedding) == 0:
                            raise ValueError(f"嵌入向量为空")
                        
                    except Exception as type_error:
                        logger.error(f"嵌入向量类型处理失败: {str(type_error)}, 类型: {type(embedding_raw)}")
                        raise ValueError(f"嵌入向量类型处理失败: {str(type_error)}")
                    
                    self.gds.run_cypher("""
                        MATCH (c:`__Community__` {id: $community_id})
                        CALL db.create.setNodeVectorProperty(c, "embedding", $embedding)
                    """, {
                        "community_id": community["community_id"],
                        "embedding": embedding
                    })
                    embeddings_created += 1
            
            duration = time.time() - start_time
            logger.info(f"社区嵌入向量生成完成，耗时: {duration:.2f}秒，生成了 {embeddings_created} 个向量")
            
            return to_serializable({
                "status": "success",
                "duration": duration,
                "embeddings_created": embeddings_created
            })
            
        except Exception as e:
            logger.error(f"生成社区嵌入向量失败: {str(e)}")
            raise
    
    def create_community_indexes(self) -> Dict[str, Any]:
        """
        阶段8：索引创建
        创建向量和全文索引
        """
        logger.info("开始创建社区索引")
        start_time = time.time()
        
        try:
            # 创建向量索引
            vector_index_result = self.gds.run_cypher(f"""
                CREATE VECTOR INDEX community_vector IF NOT EXISTS 
                FOR (c:__Community__) ON c.embedding
                OPTIONS {{
                  indexConfig: {{
                    `vector.dimensions`: {settings.VECTOR_SIZE},
                    `vector.similarity_function`: 'cosine'
                  }}
                }}
            """)
            
            # 创建全文索引
            fulltext_index_result = self.gds.run_cypher("""
                CREATE FULLTEXT INDEX community_keyword IF NOT EXISTS
                FOR (n:`__Community__`) ON EACH [n.summary]
            """)
            
            duration = time.time() - start_time
            logger.info(f"社区索引创建完成，耗时: {duration:.2f}秒")
            
            return to_serializable({
                "status": "success",
                "duration": duration,
                "vector_index_created": not self._is_dataframe_empty(vector_index_result),
                "fulltext_index_created": not self._is_dataframe_empty(fulltext_index_result)
            })
            
        except Exception as e:
            logger.error(f"创建社区索引失败: {str(e)}")
            raise
    
    def run_full_community_detection(self) -> Dict[str, Any]:
        """
        执行完整的社区检测流程
        """
        logger.info("开始执行完整的社区检测流程")
        total_start_time = time.time()
        
        results = {}
        
        try:
            # 阶段1：数据清理
            results["clear_communities"] = self.clear_communities()
            
            # 阶段2：图投影
            results["create_projection"] = self.create_community_graph_projection()
            
            # 阶段3：社区检测
            results["detect_communities"] = self.detect_communities()
            
            # 阶段4：社区节点创建
            results["create_nodes"] = self.create_community_nodes()
            
            # 阶段5：属性计算
            results["calculate_properties"] = self.calculate_community_properties()
            
            # 阶段6：摘要生成
            results["generate_summaries"] = self.generate_community_summaries()
            
            # 阶段7：向量化
            results["create_embeddings"] = self.create_community_embeddings()
            
            # 阶段8：索引创建
            results["create_indexes"] = self.create_community_indexes()
            
            total_duration = time.time() - total_start_time
            logger.info(f"完整的社区检测流程执行完成，总耗时: {total_duration:.2f}秒")
            
            return to_serializable({
                "status": "success",
                "total_duration": total_duration,
                "stages": results
            })
            
        except Exception as e:
            logger.error(f"社区检测流程执行失败: {str(e)}")
            raise 