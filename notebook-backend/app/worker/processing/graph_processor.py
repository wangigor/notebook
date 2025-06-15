import logging
from app.database import SessionLocal
from app.services.task_service import TaskService
from app.services.task_detail_service import TaskDetailService
from app.services.document_parser import DocumentParser
from app.services.chunk_service import ChunkService
from app.services.graph_vector_service import GraphVectorService
from app.services.entity_extraction_service import EntityExtractionService
from app.services.relationship_service import RelationshipService
from app.services.graph_builder_service import GraphBuilderService
from app.models.task import TaskStatus, TaskStepStatus
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

async def run(doc_id: int, task_id: str, file_path: str):
    """图谱处理器：处理文档的图谱构建模式实现"""
    logger.info(f"开始图谱处理模式：文档ID={doc_id}, 任务ID={task_id}, 文件路径={file_path}")
    
    # 获取数据库会话
    session = SessionLocal()
    try:
        # 获取服务实例
        task_service = TaskService(session)
        task_detail_service = TaskDetailService(session)
        document_parser = DocumentParser()
        chunk_service = ChunkService()
        vector_service = GraphVectorService()
        entity_service = EntityExtractionService()
        relationship_service = RelationshipService()
        graph_builder = GraphBuilderService()
        
        try:
            # 更新任务状态为运行中
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING
            )
            
            # 定义处理步骤
            steps = [
                {
                    "name": "文档解析",
                    "description": "解析文档内容和结构",
                    "status": TaskStepStatus.PENDING
                },
                {
                    "name": "文档分块",
                    "description": "智能分块处理",
                    "status": TaskStepStatus.PENDING
                },
                {
                    "name": "向量化处理",
                    "description": "分块文本向量化",
                    "status": TaskStepStatus.PENDING
                },
                {
                    "name": "实体抽取",
                    "description": "从文本中抽取实体",
                    "status": TaskStepStatus.PENDING
                },
                {
                    "name": "关系识别",
                    "description": "识别实体间关系",
                    "status": TaskStepStatus.PENDING
                },
                {
                    "name": "图谱构建",
                    "description": "构建知识图谱",
                    "status": TaskStepStatus.PENDING
                },
                {
                    "name": "图谱存储",
                    "description": "存储到Neo4j数据库",
                    "status": TaskStepStatus.PENDING
                }
            ]
            
            # 步骤1：文档解析
            logger.info(f"步骤1: 开始文档解析")
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                step_index=0,
                step_status=TaskStepStatus.RUNNING,
                step_metadata={"steps": steps}
            )
            await push_task_update(task_id, task_service)
            
            try:
                parse_result = document_parser.parse(file_path)
                content = parse_result.get('content', '')
                document_structure = parse_result.get('structure')
                
                logger.info(f"文档解析完成，内容长度: {len(content)} 字符")
                
                # 更新步骤状态
                steps[0]["status"] = TaskStepStatus.COMPLETED
                steps[0]["result"] = {
                    "content_length": len(content),
                    "word_count": len(content.split()),
                    "has_structure": document_structure is not None
                }
                
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.RUNNING,
                    step_index=0,
                    step_status=TaskStepStatus.COMPLETED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                
            except Exception as e:
                logger.error(f"文档解析失败: {str(e)}")
                steps[0]["status"] = TaskStepStatus.FAILED
                steps[0]["error"] = str(e)
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=f"文档解析失败: {str(e)}",
                    step_index=0,
                    step_status=TaskStepStatus.FAILED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                raise
            
            # 步骤2：文档分块
            logger.info(f"步骤2: 开始文档分块")
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                step_index=1,
                step_status=TaskStepStatus.RUNNING,
                step_metadata={"steps": steps}
            )
            await push_task_update(task_id, task_service)
            
            try:
                chunks = chunk_service.chunk_document(
                    content=content,
                    document_id=doc_id,
                    document_structure=document_structure,
                    strategy="adaptive"
                )
                
                logger.info(f"文档分块完成，共生成 {len(chunks)} 个分块")
                
                # 获取分块统计信息
                chunk_stats = chunk_service.get_chunk_statistics(chunks)
                
                # 更新步骤状态
                steps[1]["status"] = TaskStepStatus.COMPLETED
                steps[1]["result"] = {
                    "total_chunks": len(chunks),
                    "statistics": chunk_stats
                }
                
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.RUNNING,
                    step_index=1,
                    step_status=TaskStepStatus.COMPLETED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                
            except Exception as e:
                logger.error(f"文档分块失败: {str(e)}")
                steps[1]["status"] = TaskStepStatus.FAILED
                steps[1]["error"] = str(e)
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=f"文档分块失败: {str(e)}",
                    step_index=1,
                    step_status=TaskStepStatus.FAILED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                raise
            
            # 步骤3：向量化处理
            logger.info(f"步骤3: 开始向量化处理")
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                step_index=2,
                step_status=TaskStepStatus.RUNNING,
                step_metadata={"steps": steps}
            )
            await push_task_update(task_id, task_service)
            
            try:
                # 将分块转换为向量服务需要的格式
                chunks_for_vectorization = []
                for chunk in chunks:
                    chunk_dict = {
                        'id': f"chunk_{doc_id}_{chunk.metadata.chunk_index}",
                        'content': chunk.content,
                        'properties': {
                            'document_id': doc_id,
                            'chunk_index': chunk.metadata.chunk_index,
                            'start_char': chunk.metadata.start_char,
                            'end_char': chunk.metadata.end_char,
                            'word_count': chunk.metadata.word_count,
                            'paragraph_count': chunk.metadata.paragraph_count
                        }
                    }
                    chunks_for_vectorization.append(chunk_dict)
                
                # 执行向量化
                vectorized_chunks = await vector_service.vectorize_chunks(chunks_for_vectorization)
                
                # 存储向量到Neo4j
                store_result = await vector_service.store_vectors_to_neo4j(
                    vectorized_chunks, 
                    "DocumentChunk"
                )
                
                logger.info(f"向量化处理完成，存储了 {store_result['stored_count']} 个向量")
                
                # 更新步骤状态
                steps[2]["status"] = TaskStepStatus.COMPLETED
                steps[2]["result"] = {
                    "vectorized_chunks": len(vectorized_chunks),
                    "stored_count": store_result['stored_count'],
                    "vector_dimension": store_result['vector_dimension']
                }
                
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.RUNNING,
                    step_index=2,
                    step_status=TaskStepStatus.COMPLETED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                
            except Exception as e:
                logger.error(f"向量化处理失败: {str(e)}")
                steps[2]["status"] = TaskStepStatus.FAILED
                steps[2]["error"] = str(e)
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=f"向量化处理失败: {str(e)}",
                    step_index=2,
                    step_status=TaskStepStatus.FAILED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                raise
            
            # 步骤4：实体抽取
            logger.info(f"步骤4: 开始实体抽取")
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                step_index=3,
                step_status=TaskStepStatus.RUNNING,
                step_metadata={"steps": steps}
            )
            await push_task_update(task_id, task_service)
            
            try:
                # 执行实体抽取
                entities = await entity_service.extract_entities_from_chunks(chunks_for_vectorization)
                
                # 获取抽取统计信息
                entity_stats = await entity_service.get_extraction_statistics(entities)
                
                logger.info(f"实体抽取完成，共抽取 {len(entities)} 个实体")
                
                # 更新步骤状态
                steps[3]["status"] = TaskStepStatus.COMPLETED
                steps[3]["result"] = {
                    "total_entities": len(entities),
                    "statistics": entity_stats
                }
                
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.RUNNING,
                    step_index=3,
                    step_status=TaskStepStatus.COMPLETED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                
            except Exception as e:
                logger.error(f"实体抽取失败: {str(e)}")
                steps[3]["status"] = TaskStepStatus.FAILED
                steps[3]["error"] = str(e)
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=f"实体抽取失败: {str(e)}",
                    step_index=3,
                    step_status=TaskStepStatus.FAILED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                raise
            
            # 步骤5：关系识别
            logger.info(f"步骤5: 开始关系识别")
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                step_index=4,
                step_status=TaskStepStatus.RUNNING,
                step_metadata={"steps": steps}
            )
            await push_task_update(task_id, task_service)
            
            try:
                # 执行关系识别
                relationships = await relationship_service.extract_relationships_from_entities(
                    entities, chunks_for_vectorization
                )
                
                # 获取关系统计信息
                relationship_stats = await relationship_service.get_relationship_statistics(relationships)
                
                logger.info(f"关系识别完成，共识别 {len(relationships)} 个关系")
                
                # 更新步骤状态
                steps[4]["status"] = TaskStepStatus.COMPLETED
                steps[4]["result"] = {
                    "total_relationships": len(relationships),
                    "statistics": relationship_stats
                }
                
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.RUNNING,
                    step_index=4,
                    step_status=TaskStepStatus.COMPLETED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                
            except Exception as e:
                logger.error(f"关系识别失败: {str(e)}")
                steps[4]["status"] = TaskStepStatus.FAILED
                steps[4]["error"] = str(e)
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=f"关系识别失败: {str(e)}",
                    step_index=4,
                    step_status=TaskStepStatus.FAILED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                raise
            
            # 步骤6：图谱构建
            logger.info(f"步骤6: 开始图谱构建")
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                step_index=5,
                step_status=TaskStepStatus.RUNNING,
                step_metadata={"steps": steps}
            )
            await push_task_update(task_id, task_service)
            
            try:
                # 构建图谱数据
                graph_data = await graph_builder.build_graph_from_extracted_data(
                    entities, relationships, doc_id
                )
                
                # 去重和验证图谱数据
                graph_data = await graph_builder.deduplicate_graph_data(graph_data)
                validation_result = await graph_builder.validate_graph_integrity(graph_data)
                
                if not validation_result["is_valid"]:
                    logger.warning(f"图谱数据验证失败: {validation_result['errors']}")
                
                logger.info(f"图谱构建完成：{graph_data['metadata']['total_nodes']} 个节点，{graph_data['metadata']['total_edges']} 条边")
                
                # 更新步骤状态
                steps[5]["status"] = TaskStepStatus.COMPLETED
                steps[5]["result"] = {
                    "total_nodes": graph_data['metadata']['total_nodes'],
                    "total_edges": graph_data['metadata']['total_edges'],
                    "quality_metrics": graph_data['metadata']['quality_metrics'],
                    "validation": validation_result
                }
                
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.RUNNING,
                    step_index=5,
                    step_status=TaskStepStatus.COMPLETED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                
            except Exception as e:
                logger.error(f"图谱构建失败: {str(e)}")
                steps[5]["status"] = TaskStepStatus.FAILED
                steps[5]["error"] = str(e)
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=f"图谱构建失败: {str(e)}",
                    step_index=5,
                    step_status=TaskStepStatus.FAILED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                raise
            
            # 步骤7：图谱存储
            logger.info(f"步骤7: 开始图谱存储")
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                step_index=6,
                step_status=TaskStepStatus.RUNNING,
                step_metadata={"steps": steps}
            )
            await push_task_update(task_id, task_service)
            
            try:
                # 存储图谱到Neo4j
                store_result = await graph_builder.neo4j_service.store_graph_data(graph_data)
                
                # 获取存储统计
                graph_stats = graph_builder.neo4j_service.get_graph_statistics()
                
                logger.info(f"图谱存储完成：{store_result['nodes_created']} 个节点，{store_result['relationships_created']} 条关系")
                
                # 更新步骤状态
                steps[6]["status"] = TaskStepStatus.COMPLETED
                steps[6]["result"] = {
                    "store_result": store_result,
                    "graph_statistics": graph_stats
                }
                
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.RUNNING,
                    step_index=6,
                    step_status=TaskStepStatus.COMPLETED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                
            except Exception as e:
                logger.error(f"图谱存储失败: {str(e)}")
                steps[6]["status"] = TaskStepStatus.FAILED
                steps[6]["error"] = str(e)
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=f"图谱存储失败: {str(e)}",
                    step_index=6,
                    step_status=TaskStepStatus.FAILED,
                    step_metadata={"steps": steps}
                )
                await push_task_update(task_id, task_service)
                raise
            
            logger.info("图谱处理完成")
            
            # 更新任务状态为完成
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                step_metadata={"steps": steps}
            )
            await push_task_update(task_id, task_service)
            
            return True
            
        except Exception as e:
            logger.error(f"图谱处理失败: {str(e)}")
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error_message=str(e)
            )
            await push_task_update(task_id, task_service)
            return False
            
    finally:
        session.close()

async def push_task_update(task_id: str, task_service: TaskService):
    """推送任务更新到WebSocket"""
    try:
        from app.worker.websocket_manager import WebSocketManager
        ws_manager = WebSocketManager()
        
        # 获取任务数据
        task_data = await task_service.get_task_with_details(task_id)
        
        # 异步推送到WebSocket
        await ws_manager.send_update(task_id, {
            "event": "task_update",
            "data": task_data
        })
    except Exception as e:
        logger.error(f"推送任务更新失败: {str(e)}") 