from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional, Dict, Any
import json
from datetime import datetime
from io import BytesIO
from pydantic import BaseModel, HttpUrl
import base64
import logging
import uuid
import os

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.document import DocumentUpdate, DocumentPreviewContent, DocumentPreview, DocumentResponse, DocumentList, DocumentStatus
from app.models.task import Task, TaskStatusResponse
from app.services.document_service import DocumentService
from app.services.task_service import TaskService
from app.services.vector_store import VectorStoreService
from app.models.memory import VectorStoreConfig
from app.worker.celery_tasks import process_document
from app.utils.file_utils import save_upload_file_temp  # 导入文件保存工具函数
from app.services.task_detail_service import TaskDetailService
from app.utils.http_utils import format_content_disposition  # 导入HTTP工具函数

router = APIRouter()


# 依赖项：获取文档服务
def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    vector_store = VectorStoreService()
    return DocumentService(db, vector_store)


# 依赖项：获取任务服务
def get_task_service(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db)


class WebDocumentRequest(BaseModel):
    url: HttpUrl
    metadata: Optional[Dict[str, Any]] = None


class DirectoryDocumentRequest(BaseModel):
    directory_path: str
    recursive: bool = True
    metadata: Optional[Dict[str, Any]] = None


class CustomDocumentRequest(BaseModel):
    name: str
    content: str
    file_type: str = "txt"
    metadata: Optional[Dict[str, Any]] = None


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    processing_mode: str = Form("graph"),
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    task_service: TaskService = Depends(get_task_service),
    current_user: User = Depends(get_current_user)
):
    """
    上传文档接口
    """
    # 生成一个唯一的任务ID
    task_id = str(uuid.uuid4())
    logger = logging.getLogger(__name__)
    
    logger.info(f"接收到文件上传请求: {file.filename}, 类型: {file.content_type}")
    
    # 验证处理模式
    if processing_mode not in ["rag", "graph"]:
        raise HTTPException(status_code=400, detail="处理模式必须是 'rag' 或 'graph'")
    
    logger.info(f"使用处理模式: {processing_mode}")
    
    # 处理元数据
    doc_metadata = {}
    if metadata:
        try:
            doc_metadata = json.loads(metadata)
            logger.info(f"解析元数据: {metadata[:100]}...")
        except Exception as e:
            logger.error(f"解析元数据失败: {str(e)}")
            
    logger.info("开始处理上传的文件")
    
    try:
        # 1. 保存上传的文件到临时目录
        temp_file_path = await save_upload_file_temp(file)
        logger.info(f"文件已保存到临时路径: {temp_file_path}")
        
        # 将文件指针重置到开始位置，以便后续处理
        file.file.seek(0)
        
        # 2. 处理文件并创建文档记录
        document = await document_service.process_file(file, current_user.id, doc_metadata)
        
        # 获取文档存储路径信息，确保与MinIO存储一致
        bucket_name = document.bucket_name
        object_key = document.object_key
        
        # 3. 创建异步任务进行后续处理
        task = task_service.create_task(
            name=f"处理文档: {file.filename}",
            task_type="DOCUMENT_PROCESSING",
            description=f"从文件 {file.filename} 中提取并处理文本",
            created_by=current_user.id,
            document_id=document.id,
            metadata={
                "filename": file.filename,
                "content_type": file.content_type,
                "upload_time": datetime.utcnow().isoformat(),
                "temp_file_path": temp_file_path,  # 添加临时文件路径到元数据
                "bucket_name": bucket_name,        # 添加存储桶名称
                "object_key": object_key,          # 添加对象键，确保路径一致性
                "processing_mode": processing_mode  # 添加处理模式
            }
        )
        
        # 更新文档关联的任务ID
        document_service.update_document_status(
            document.id, 
            DocumentStatus.PROCESSING,  # 使用枚举而不是字符串 "PROCESSING"
            message=f"已创建处理任务: {task.id}"
        )
        
        # 4. 触发后台处理任务，传递所有必需参数
        process_document.delay(document.id, task.id, temp_file_path, processing_mode)
        
        logger.info(f"文件处理成功，文档ID: {document.id}, 任务ID: {task.id}")
        
        # 5. 将SQLAlchemy模型转换为Pydantic模型
        doc_dict = {
            "id": document.id,
            "name": document.name,  # 使用原始name字段
            "content": getattr(document, 'content', '') or '',  # 确保为空字符串，而不是None
            "user_id": document.user_id,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
            "status": document.processing_status,
            "metadata": document.doc_metadata,
            "is_deleted": document.deleted,
            "file_type": document.file_type
        }
        
        return DocumentResponse.model_validate(doc_dict)
        
    except Exception as e:
        logger.error(f"上传文档失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"上传文档失败: {str(e)}")


@router.post("/from-web", response_model=DocumentResponse)
async def load_from_web(
    request: WebDocumentRequest,
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    从网页URL加载文档
    """
    try:
        document = await document_service.load_from_web(
            url=str(request.url),
            user_id=current_user.id,
            metadata=request.metadata
        )
        return DocumentResponse.model_validate(document)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"从网页加载文档失败: {str(e)}")


@router.post("/from-directory", response_model=List[DocumentResponse])
async def load_from_directory(
    request: DirectoryDocumentRequest,
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    从目录加载文档（需要服务器权限）
    """
    try:
        documents = await document_service.load_from_directory(
            directory_path=request.directory_path,
            user_id=current_user.id,
            recursive=request.recursive
        )
        # 将SQLAlchemy模型转换为Pydantic模型
        return [DocumentResponse.model_validate(doc) for doc in documents]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"从目录加载文档失败: {str(e)}")


@router.post("/custom", response_model=DocumentResponse)
async def create_custom_document(
    request: CustomDocumentRequest,
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    创建自定义文档（不需要上传文件）
    """
    try:
        document = await document_service.create_custom_document(
            user_id=current_user.id,
            name=request.name,
            content=request.content,
            file_type=request.file_type,
            metadata=request.metadata
        )
        # 将SQLAlchemy模型转换为Pydantic模型
        return DocumentResponse.model_validate(document)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建自定义文档失败: {str(e)}")


@router.get("/", response_model=DocumentList)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="文档处理状态过滤"),
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    获取文档列表
    """
    logger = logging.getLogger(__name__)
    
    try:
        # 构建过滤条件
        filters = {}
        if status:
            filters["processing_status"] = status
            
        documents, total = document_service.get_documents(
            current_user.id, 
            skip, 
            limit, 
            search,
            filters=filters
        )
        
        # 创建文档预览列表
        document_previews = []
        for doc in documents:
            try:
                # 安全地获取预览内容
                preview_content = ""
                if hasattr(doc, 'content') and doc.content is not None:
                    preview_content = str(doc.content)[:100]
                
                # 将ORM模型转换为与Pydantic模型兼容的字典
                doc_dict = {
                    "id": doc.id,
                    "name": doc.name,  # 使用原始name字段
                    "user_id": doc.user_id,
                    "created_at": doc.created_at,
                    "updated_at": doc.updated_at,
                    "status": doc.processing_status,  # 转换 processing_status -> status
                    "preview_content": preview_content,
                    "file_type": doc.file_type  # 添加文件类型字段
                }
                
                # 安全地处理标签数据
                if hasattr(doc, 'tags') and doc.tags is not None:
                    # 确保 tags 是列表类型
                    if isinstance(doc.tags, list):
                        doc_dict["tags"] = doc.tags
                    else:
                        # 尝试转换为列表，如果不是可迭代对象则使用空列表
                        try:
                            doc_dict["tags"] = list(doc.tags)
                        except (TypeError, ValueError):
                            doc_dict["tags"] = []
                            logger.warning(f"文档 {doc.id} 的标签不是列表类型，已转换为空列表")
                
                # 创建 DocumentPreview 对象
                document_previews.append(DocumentPreview.model_validate(doc_dict))
                
            except Exception as e:
                logger.error(f"处理文档 {doc.id} 失败: {str(e)}", exc_info=True)
                # 记录更详细的错误信息以便调试
                logger.debug(f"文档数据: {vars(doc)}")
                # 跳过有问题的文档
                continue
                
        return DocumentList(items=document_previews, total=total, page=skip//limit + 1, page_size=limit)
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """
    获取单个文档详情
    """
    logger = logging.getLogger(__name__)
    logger.info(f"获取文档ID: {document_id}")
    
    # 传入load_content=True参数
    document = await document_service.get_document(document_id, current_user.id, load_content=True)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 处理文档内容 - 特别处理二进制内容的情况
    content = document.content
    if isinstance(content, dict) and content.get("is_binary", False) and "binary_content" in content:
        logger.info(f"检测到二进制内容字典格式，将其序列化为JSON字符串")
        # 将二进制数据转换为base64字符串
        if "binary_content" in content and isinstance(content["binary_content"], bytes):
            content["binary_content"] = base64.b64encode(content["binary_content"]).decode('utf-8')
        # 将字典序列化为JSON字符串
        document.content = json.dumps(content)
    
    # 封装成Pydantic模型返回
    # 特别处理Document ORM模型和DocumentResponse Pydantic模型的字段差异
    doc_dict = {
        "id": document.id,
        "name": document.name,  # 使用原始name字段
        "content": document.content or '',  # 使用空字符串而非None
        "user_id": document.user_id,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "status": document.processing_status,  # 转换 processing_status -> status
        "metadata": document.doc_metadata,
        "is_deleted": document.deleted,  # 使用我们添加的计算属性
        "file_type": document.file_type
    }
    
    # 如果有标签数据，也添加上
    if hasattr(document, 'tags'):
        doc_dict["tags"] = document.tags
    
    try:
        return DocumentResponse.model_validate(doc_dict)
    except Exception as e:
        logger.error(f"转换文档响应模型失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理文档数据失败: {str(e)}")


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: int,
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    获取文档原始内容（用于预览）
    """
    logger = logging.getLogger(__name__)
    logger.info(f"请求获取文档内容: {document_id}")
    
    document = await document_service.get_document(document_id, current_user.id, load_content=True)
    if not document:
        logger.warning(f"文档不存在: {document_id}")
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 检查是否为Base64编码的二进制内容
    is_base64 = False
    content = document.content if hasattr(document, 'content') else None
    
    if content and isinstance(content, str) and content.startswith("__BASE64__"):
        logger.info(f"检测到Base64编码内容，准备解码")
        try:
            # 移除标记前缀并解码
            base64_content = content[10:]  # 去掉 "__BASE64__" 前缀
            binary_content = base64.b64decode(base64_content)
            is_base64 = True
            logger.info(f"Base64解码成功，解码后大小: {len(binary_content)} 字节")
        except Exception as e:
            logger.error(f"Base64解码失败: {str(e)}")
            # 解码失败时返回原始内容
            return {"content": content}
    
    # 处理二进制文件
    if is_base64 or document.file_type in ['pdf', 'doc', 'docx', 'xls', 'xlsx']:
        try:
            if is_base64:
                content = binary_content
            else:
                # 如果没有Base64编码但仍是二进制文件类型，尝试传统方式解码
                logger.info(f"尝试传统方式解码二进制内容")
                content = content.encode('latin1') if isinstance(content, str) else content
            
            # 设置正确的Content-Type
            media_types = {
                'pdf': 'application/pdf',
                'doc': 'application/msword',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'xls': 'application/vnd.ms-excel',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
            
            content_type = media_types.get(document.file_type, 'application/octet-stream')
            logger.info(f"返回二进制内容，类型: {content_type}")
            
            return StreamingResponse(
                BytesIO(content),
                media_type=content_type,
                headers={"Content-Disposition": f'attachment; filename="{document.name}"'}
            )
        except Exception as e:
            logger.error(f"处理二进制内容失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"无法提取文档内容: {str(e)}")
    
    # 其他文件返回文本内容
    logger.info(f"返回文本内容")
    return {"content": content}


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    下载文档
    """
    logger = logging.getLogger(__name__)
    logger.info(f"请求下载文档: {document_id}")
    
    document = await document_service.get_document(document_id, current_user.id, load_content=True)
    if not document:
        logger.warning(f"文档不存在: {document_id}")
        raise HTTPException(status_code=404, detail="文档不存在")
    
    try:
        # 获取文件内容
        content = document.content if hasattr(document, 'content') else None
        
        # 检查是否为Base64编码的二进制内容
        if content and isinstance(content, str) and content.startswith("__BASE64__"):
            logger.info(f"检测到Base64编码内容，准备解码")
            try:
                # 移除标记前缀并解码
                base64_content = content[10:]  # 去掉 "__BASE64__" 前缀
                content = base64.b64decode(base64_content)
                logger.info(f"Base64解码成功，解码后大小: {len(content)} 字节")
            except Exception as e:
                logger.error(f"Base64解码失败: {str(e)}，尝试传统方式处理")
                # 解码失败时尝试传统方式
                if isinstance(content, str):
                    try:
                        content = content.encode('latin1')
                    except:
                        content = content.encode('utf-8')
        else:
            # 非Base64编码内容的传统处理
            if isinstance(content, str):
                try:
                    content = content.encode('latin1')
                except:
                    content = content.encode('utf-8')
        
        # 设置正确的Content-Type
        media_types = {
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'json': 'application/json',
            'csv': 'text/csv',
            'txt': 'text/plain',
            'md': 'text/markdown',
            'html': 'text/html',
            'htm': 'text/html'
        }
        
        content_type = media_types.get(document.file_type, 'application/octet-stream')
        logger.info(f"文件内容类型设置为: {content_type}")
        
        # 获取文件名（从元数据中或使用文档名称）
        filename = document.doc_metadata.get('filename', f"{document.name}.{document.file_type}") if document.doc_metadata else f"{document.name}.{document.file_type}"
        logger.info(f"设置下载文件名: {filename}")
        
        # 使用工具函数正确处理Content-Disposition头，包括对中文文件名的处理
        content_disposition = format_content_disposition("attachment", filename)
        
        return StreamingResponse(
            BytesIO(content),
            media_type=content_type,
            headers={"Content-Disposition": content_disposition}
        )
    except Exception as e:
        logger.error(f"下载文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载文档失败: {str(e)}")


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    document: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """
    更新文档信息
    """
    try:
        updated_doc = await document_service.update_document(document_id, current_user.id, document)
        if not updated_doc:
            raise HTTPException(status_code=404, detail="文档不存在或无权限修改")
        return DocumentResponse.model_validate(updated_doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新文档失败: {str(e)}")


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    permanent: bool = False,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """
    删除文档
    """
    logger = logging.getLogger(__name__)
    logger.info(f"删除文档ID: {document_id}, 永久删除: {permanent}")
    
    success = document_service.delete_document(document_id, current_user.id, permanent)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return {"success": True, "message": "文档已删除"}


@router.get("/{document_id}/tasks", response_model=List[TaskStatusResponse])
async def get_document_tasks(
    document_id: int,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    task_service: TaskService = Depends(get_task_service),
    current_user: User = Depends(get_current_user)
):
    """获取文档相关的任务列表"""
    # 验证文档存在并属于当前用户
    document = await document_service.get_document(document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
        
    # 查询任务
    tasks = db.query(Task).filter(
        Task.document_id == document_id
    ).order_by(desc(Task.created_at)).limit(limit).all()
    
    # 获取任务详情服务
    task_detail_service = TaskDetailService(db)
    
    # 将SQLAlchemy对象转换为字典，然后创建Pydantic模型
    task_responses = []
    for task in tasks:
        # 创建基本任务字典
        task_dict = {
            "id": task.id,
            "name": task.name,
            "description": task.description,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "steps": task.steps or [],
            "document_id": str(task.document_id),  # 转换为字符串
            "metadata": task.task_metadata or {}
        }
        
        # 获取任务详情数据
        task_details = task_detail_service.get_task_details_by_task_id(task.id)
        task_details_data = []
        for td in task_details:
            task_details_data.append({
                "id": td.id,
                "task_id": td.task_id,
                "step_name": td.step_name,
                "step_order": td.step_order,
                "status": td.status,
                "progress": td.progress,
                "details": td.details,
                "error_message": td.error_message,
                "started_at": td.started_at,
                "completed_at": td.completed_at,
                "created_at": td.created_at
            })
        
        # 添加任务详情到任务数据
        task_dict["task_details"] = task_details_data
        
        # 添加到响应列表
        task_responses.append(TaskStatusResponse.model_validate(task_dict))
    
    return task_responses 


@router.get("/{document_id}/binary")
async def get_document_binary(
    document_id: int,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """
    获取文档的二进制内容流，适用于Word等文档
    直接从MinIO获取原始二进制流，不进行任何内容处理
    """
    logger = logging.getLogger(__name__)
    logger.info(f"请求获取文档二进制内容: {document_id}")
    
    try:
        # 获取文档元数据（不加载内容）
        document = await document_service.get_document(document_id, current_user.id, load_content=False)
        if not document:
            logger.warning(f"文档不存在: {document_id}")
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 目前仅实现对Word文档的支持
        supported_binary_types = ['doc', 'docx']
        if document.file_type not in supported_binary_types:
            logger.warning(f"不支持的文档类型: {document.file_type}")
            raise HTTPException(status_code=400, detail=f"此端点目前仅支持以下文档类型: {', '.join(supported_binary_types)}")
        
        # 从MinIO获取二进制内容流
        content_stream, content_type, content_length = await document_service.get_document_binary_stream(document_id)
        
        # 设置精确的MIME类型
        mime_types = {
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        precise_content_type = mime_types.get(document.file_type, content_type)
        
        # 获取文件名（从元数据中或使用文档名称）
        filename = document.doc_metadata.get('filename', f"{document.name}.{document.file_type}") if document.doc_metadata else f"{document.name}.{document.file_type}"
        logger.info(f"设置文档二进制流文件名: {filename}")
        
        # 使用工具函数正确处理Content-Disposition头，包括对中文文件名的处理
        content_disposition = format_content_disposition("inline", filename)
        
        # 设置响应头
        headers = {
            "Content-Disposition": content_disposition,
            "Content-Length": str(content_length) if content_length else None
        }
        
        logger.info(f"返回二进制流，内容类型: {precise_content_type}, 文件类型: {document.file_type}")
        
        return StreamingResponse(
            content_stream, 
            media_type=precise_content_type,
            headers={k: v for k, v in headers.items() if v is not None}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档二进制内容失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文档二进制内容失败: {str(e)}")


@router.get("/{document_id}/preview", response_model=DocumentPreviewContent)
async def get_document_preview(
    document_id: int,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """
    获取文档预览数据，返回统一格式的内容
    仅支持文本格式的文档预览，二进制文档请使用/binary端点
    """
    logger = logging.getLogger(__name__)
    logger.info(f"请求文档预览: {document_id}")
    
    document = await document_service.get_document(document_id, current_user.id, load_content=True)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 检查是否为不支持预览的二进制文档类型
    unsupported_binary_types = ['doc', 'docx']
    if document.file_type in unsupported_binary_types:
        logger.info(f"文档类型 {document.file_type} 不支持文本预览，请使用/binary端点")
        return {
            "content": f"此文档类型({document.file_type})不支持文本预览，请使用二进制查看或下载",
            "content_type": "text/plain"
        }
    
    # 获取内容
    content = document.content if hasattr(document, 'content') else None
    
    # 处理不同类型的文件内容 - 仅支持文本和Base64
    content_type = ""
    
    # 检查是否为已经Base64编码的二进制内容（PDF等支持base64预览的类型）
    if content and isinstance(content, str) and content.startswith("__BASE64__"):
        try:
            # 移除标记前缀并解码
            base64_content = content[10:]  # 去掉 "__BASE64__" 前缀
            
            # 设置MIME类型
            mime_types = {
                'pdf': 'application/pdf',
                'xls': 'application/vnd.ms-excel',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
            
            content_type = mime_types.get(document.file_type, 'application/octet-stream')
            
            # 添加data URL前缀
            content = f"data:{content_type};base64,{base64_content}"
            
        except Exception as e:
            logger.error(f"Base64解码失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"处理文档内容失败: {str(e)}")
    else:
        # 文本内容处理
        if document.file_type == 'md':
            content_type = 'text/markdown'
        elif document.file_type == 'txt':
            content_type = 'text/plain'
        else:
            content_type = 'text/plain'
    
    return {
        "content": content,
        "content_type": content_type
    } 