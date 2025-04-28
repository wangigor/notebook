from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import json
from datetime import datetime
from io import BytesIO
from pydantic import BaseModel, HttpUrl
import base64
import logging

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.document import DocumentUpdate, DocumentPreview, DocumentResponse, DocumentList
from app.services.document_service import DocumentService
from app.services.vector_store import VectorStoreService
from app.models.memory import VectorStoreConfig

router = APIRouter()


# 依赖项：获取文档服务
def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    vector_store = VectorStoreService()
    return DocumentService(db, vector_store)


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
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    上传文档
    """
    logger = logging.getLogger(__name__)
    logger.info(f"接收到文件上传请求: {file.filename}, 类型: {file.content_type}")
    
    try:
        # 解析元数据
        parsed_metadata = {}
        if metadata:
            try:
                logger.info(f"解析元数据: {metadata[:100]}...")
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError as e:
                logger.warning(f"元数据JSON解析失败，使用文本格式: {str(e)}")
                parsed_metadata = {"notes": metadata}
        
        # 处理文件
        logger.info(f"开始处理上传的文件")
        document = await document_service.process_file(
            file=file,
            user_id=current_user.id,
            doc_metadata=parsed_metadata
        )
        
        logger.info(f"文件处理成功，文档ID: {document.id}")
        # 将SQLAlchemy模型转换为Pydantic模型
        return DocumentResponse.model_validate(document)
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
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    获取文档列表
    """
    logger = logging.getLogger(__name__)
    
    try:
        documents, total = document_service.get_documents(current_user.id, skip, limit, search)
        
        # 创建文档预览列表
        document_previews = []
        for doc in documents:
            try:
                document_previews.append(DocumentPreview.model_validate(doc))
            except Exception as e:
                logger.error(f"处理文档 {doc.id} 失败: {str(e)}")
                # 跳过有问题的文档
                continue
                
        return DocumentList(documents=document_previews, total=total)
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
    
    document = document_service.get_document(document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return DocumentResponse.model_validate(document)


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
    
    document = document_service.get_document(document_id, current_user.id)
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
    
    document = document_service.get_document(document_id, current_user.id)
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
        
        return StreamingResponse(
            BytesIO(content),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
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
        updated_doc = document_service.update_document(document_id, current_user.id, document)
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