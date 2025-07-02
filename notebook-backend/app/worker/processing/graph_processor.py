import logging
from app.database import SessionLocal
from app.services.task_service import TaskService
from app.services.task_detail_service import TaskDetailService
from app.services.document_parser import DocumentParser
from app.services.chunk_service import ChunkService
from app.services.graph_vector_service import GraphVectorService
from app.services.document_service import DocumentService
from app.services.vector_store import VectorStoreService

from app.services.graph_builder_service import GraphBuilderService
from app.services.knowledge_extraction_service import KnowledgeExtractionService
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
        knowledge_service = KnowledgeExtractionService()
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
                    "status": TaskStepStatus.PENDING,
                    "weight": 10.0
                },
                {
                    "name": "文档分块",
                    "description": "智能分块处理",
                    "status": TaskStepStatus.PENDING,
                    "weight": 15.0
                },
                {
                    "name": "向量化处理",
                    "description": "分块文本向量化",
                    "status": TaskStepStatus.PENDING,
                    "weight": 20.0
                },
                {
                    "name": "知识抽取",
                    "description": "同时抽取实体和关系",
                    "status": TaskStepStatus.PENDING,
                    "weight": 40.0
                },
                {
                    "name": "图谱构建",
                    "description": "构建知识图谱",
                    "status": TaskStepStatus.PENDING,
                    "weight": 10.0
                },
                {
                    "name": "图谱存储",
                    "description": "存储到Neo4j数据库",
                    "status": TaskStepStatus.PENDING,
                    "weight": 5.0
                }
            ]
            
            # 为每个步骤创建TaskDetail记录
            task_details = []
            for i, step in enumerate(steps):
                task_detail = task_detail_service.create_task_detail(
                    task_id=task_id,
                    step_name=step["name"],
                    step_order=i
                )
                task_details.append(task_detail)
            
            # 步骤1：文档解析
            logger.info(f"步骤1: 开始文档解析")
            task_detail_service.update_task_detail(
                task_detail_id=task_details[0].id,
                status=TaskStatus.RUNNING,
                progress=0,
                details=steps[0]
            )
            task_service.update_task_status_based_on_details(task_id)
            await push_task_update(task_id, task_service, task_detail_service)
            
            try:
                parse_result = document_parser.parse(file_path)
                content = parse_result.get('content', '')
                document_structure = parse_result.get('structure')
                
                logger.info(f"文档解析完成，内容长度: {len(content)} 字符")
                
                # 更新步骤状态
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[0].id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    details={
                        "content_length": len(content),
                        "word_count": len(content.split()),
                        "has_structure": document_structure is not None,
                        "duration_seconds": (datetime.utcnow() - task_details[0].started_at).total_seconds() if task_details[0].started_at else None
                    }
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                
            except Exception as e:
                logger.error(f"文档解析失败: {str(e)}")
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[0].id,
                    status=TaskStatus.FAILED,
                    error_message=str(e)
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                raise
            
            # 步骤2：文档分块
            logger.info(f"步骤2: 开始文档分块")
            task_detail_service.update_task_detail(
                task_detail_id=task_details[1].id,
                status=TaskStatus.RUNNING,
                progress=0,
                details=steps[1]
            )
            task_service.update_task_status_based_on_details(task_id)
            await push_task_update(task_id, task_service, task_detail_service)
            
            try:
                chunks = chunk_service.chunk_document(content, document_id=doc_id)
                # 为每个chunk添加postgresql_document_id
                for chunk in chunks:
                    chunk.metadata.postgresql_document_id = doc_id
                logger.info(f"文档分块完成，共 {len(chunks)} 个块")
                
                # 更新步骤状态
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[1].id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    details={
                        "total_chunks": len(chunks),
                        "average_chunk_size": sum(len(chunk.content) for chunk in chunks) / len(chunks),
                        "duration_seconds": (datetime.utcnow() - task_details[1].started_at).total_seconds() if task_details[1].started_at else None
                    }
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                
            except Exception as e:
                logger.error(f"文档分块失败: {str(e)}")
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[1].id,
                    status=TaskStatus.FAILED,
                    error_message=str(e)
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                raise
            
            # 步骤3：向量化处理
            logger.info(f"步骤3: 开始向量化处理")
            task_detail_service.update_task_detail(
                task_detail_id=task_details[2].id,
                status=TaskStatus.RUNNING,
                progress=0,
                details=steps[2]
            )
            task_service.update_task_status_based_on_details(task_id)
            await push_task_update(task_id, task_service, task_detail_service)
            
            try:
                vectors = await vector_service.vectorize_chunks(chunks)
                logger.info(f"向量化处理完成，共 {len(vectors)} 个向量")
                
                # 更新步骤状态
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[2].id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    details={
                        "total_vectors": len(vectors),
                        "vector_dimension": len(vectors[0]) if vectors else 0,
                        "duration_seconds": (datetime.utcnow() - task_details[2].started_at).total_seconds() if task_details[2].started_at else None
                    }
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                
            except Exception as e:
                logger.error(f"向量化处理失败: {str(e)}")
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[2].id,
                    status=TaskStatus.FAILED,
                    error_message=str(e)
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                raise
            
            # 步骤4：知识抽取（实体和关系）
            logger.info(f"步骤4: 开始知识抽取（实体和关系）")
            task_detail_service.update_task_detail(
                task_detail_id=task_details[3].id,
                status=TaskStatus.RUNNING,
                progress=0,
                details=steps[3]
            )
            task_service.update_task_status_based_on_details(task_id)
            await push_task_update(task_id, task_service, task_detail_service)
            
            try:
                # 准备chunk数据
                chunk_data = []
                for i, chunk in enumerate(chunks):
                    chunk_data.append({
                        'id': chunk.metadata.chunk_id,
                        'content': chunk.content,
                        'chunk_index': chunk.metadata.chunk_index,
                        'start_char': chunk.metadata.start_char,
                        'end_char': chunk.metadata.end_char,
                        'postgresql_document_id': chunk.metadata.postgresql_document_id
                    })
                
                entities, relationships = await knowledge_service.extract_knowledge_from_chunks(chunk_data)
                logger.info(f"知识抽取完成，共 {len(entities)} 个实体，{len(relationships)} 个关系")
                
                # 更新步骤状态
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[3].id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    details={
                        "total_entities": len(entities),
                        "total_relationships": len(relationships),
                        "entity_types": list(set(entity.type for entity in entities)),
                        "relationship_types": list(set(rel.relationship_type for rel in relationships)),
                        "duration_seconds": (datetime.utcnow() - task_details[3].started_at).total_seconds() if task_details[3].started_at else None
                    }
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                
            except Exception as e:
                logger.error(f"知识抽取失败: {str(e)}")
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[3].id,
                    status=TaskStatus.FAILED,
                    error_message=str(e)
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                raise
            
            # 步骤5：图谱构建
            logger.info(f"步骤5: 开始图谱构建（数据结构准备）")
            task_detail_service.update_task_detail(
                task_detail_id=task_details[4].id,
                status=TaskStatus.RUNNING,
                progress=0,
                details=steps[4]
            )
            task_service.update_task_status_based_on_details(task_id)
            await push_task_update(task_id, task_service, task_detail_service)
            
            try:
                # 获取Document信息
                vector_store = VectorStoreService()
                document_service = DocumentService(session, vector_store)
                document = document_service.get_document_by_id(doc_id)
                
                if not document:
                    raise Exception(f"找不到文档: {doc_id}")
                
                # 准备Document信息
                document_info = {
                    'name': document.name,
                    'file_type': document.file_type,
                    'file_size': document.file_size or 0,
                    'created_at': document.created_at
                }
                
                # 调用图谱构建，只准备数据结构，不执行Neo4j操作
                graph_data = await graph_builder.build_graph_from_extracted_data(
                    entities=entities, 
                    relationships=relationships, 
                    document_id=doc_id,
                    document_info=document_info,
                    chunks=chunks
                )
                
                logger.info(f"图谱数据结构构建完成：{graph_data['metadata']['total_nodes']} 个节点（{graph_data['metadata']['total_entities']} 个实体，{graph_data['metadata']['total_chunks']} 个Chunk），{graph_data['metadata']['total_edges']} 条关系（{graph_data['metadata']['total_chunk_entity_relationships']} 个Chunk-Entity关系）")
                
                # 更新步骤状态
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[4].id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    details={
                        "total_nodes": graph_data['metadata']['total_nodes'],
                        "total_edges": graph_data['metadata']['total_edges'],
                        "total_chunks": graph_data['metadata']['total_chunks'],
                        "total_entities": graph_data['metadata']['total_entities'],
                        "total_chunk_entity_relationships": graph_data['metadata']['total_chunk_entity_relationships'],
                        "quality_metrics": graph_data['metadata']['quality_metrics'],
                        "duration_seconds": (datetime.utcnow() - task_details[4].started_at).total_seconds() if task_details[4].started_at else None
                    }
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                
            except Exception as e:
                logger.error(f"图谱构建失败: {str(e)}")
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[4].id,
                    status=TaskStatus.FAILED,
                    error_message=str(e)
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                raise
            
            # 步骤6：图谱存储
            logger.info(f"步骤6: 开始图谱存储（统一存储所有节点和关系）")
            task_detail_service.update_task_detail(
                task_detail_id=task_details[5].id,
                status=TaskStatus.RUNNING,
                progress=0,
                details=steps[5]
            )
            task_service.update_task_status_based_on_details(task_id)
            await push_task_update(task_id, task_service, task_detail_service)
            
            try:
                # 统一存储所有图数据（节点+关系）
                store_result = await graph_builder.neo4j_service.store_graph_data(graph_data)
                
                success_msg = f"图谱存储完成：{store_result['nodes_created']} 个节点，{store_result['relationships_created']} 条关系"
                if store_result.get('chunk_entity_relationships_created', 0) > 0:
                    success_msg += f"（包含 {store_result['chunk_entity_relationships_created']} 个Chunk-Entity关系）"
                
                logger.info(success_msg)
                
                # 更新步骤状态
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[5].id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    details={
                        "nodes_created": store_result['nodes_created'],
                        "relationships_created": store_result['relationships_created'],
                        "chunk_entity_relationships_created": store_result.get('chunk_entity_relationships_created', 0),
                        "success": store_result['success'],
                        "errors": store_result.get('errors', []),
                        "duration_seconds": (datetime.utcnow() - task_details[5].started_at).total_seconds() if task_details[5].started_at else None
                    }
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                
            except Exception as e:
                logger.error(f"图谱存储失败: {str(e)}")
                task_detail_service.update_task_detail(
                    task_detail_id=task_details[5].id,
                    status=TaskStatus.FAILED,
                    error_message=str(e)
                )
                task_service.update_task_status_based_on_details(task_id)
                await push_task_update(task_id, task_service, task_detail_service)
                raise
            
            logger.info("图谱处理完成")
            
        except Exception as e:
            logger.error(f"图谱处理失败: {str(e)}")
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error_message=str(e)
            )
            await push_task_update(task_id, task_service, task_detail_service)
            raise
            
    finally:
        session.close()

async def push_task_update(task_id: str, task_service: TaskService, task_detail_service: TaskDetailService):
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