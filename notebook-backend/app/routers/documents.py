from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import json
from datetime import datetime
from io import BytesIO
from pydantic import BaseModel, HttpUrl

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
    try:
        # 解析元数据
        parsed_metadata = {}
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except:
                parsed_metadata = {"notes": metadata}
        
        # 处理文件
        document = await document_service.process_file(
            file=file,
            user_id=current_user.id,
            metadata=parsed_metadata
        )
        
        return document
    except Exception as e:
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
        return document
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
        return documents
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
        return document
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
    documents, total = document_service.get_documents(current_user.id, skip, limit, search)
    return DocumentList(documents=documents, total=total)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    获取文档
    """
    document = document_service.get_document(document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return document


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: str,
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    获取文档原始内容（用于预览）
    """
    document = document_service.get_document(document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 如果是二进制文件，返回二进制内容
    if document.file_type in ['pdf', 'doc', 'docx', 'xls', 'xlsx']:
        try:
            content = document.content.encode('latin1') if isinstance(document.content, str) else document.content
            
            # 设置正确的Content-Type
            media_types = {
                'pdf': 'application/pdf',
                'doc': 'application/msword',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'xls': 'application/vnd.ms-excel',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
            
            content_type = media_types.get(document.file_type, 'application/octet-stream')
            
            return StreamingResponse(
                BytesIO(content),
                media_type=content_type,
                headers={"Content-Disposition": f'attachment; filename="{document.name}"'}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"无法提取文档内容: {str(e)}")
    
    # 其他文件返回文本内容
    return {"content": document.content}


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    下载文档
    """
    document = document_service.get_document(document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    try:
        # 获取文件内容
        content = document.content
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
        
        # 获取文件名（从元数据中或使用文档名称）
        filename = document.doc_metadata.get('filename', f"{document.name}.{document.file_type}") if document.doc_metadata else f"{document.name}.{document.file_type}"
        
        return StreamingResponse(
            BytesIO(content),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载文档失败: {str(e)}")


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    document_update: DocumentUpdate,
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    更新文档
    """
    updated_document = document_service.update_document(document_id, current_user.id, document_update)
    if not updated_document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return updated_document


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    permanent: bool = Query(False),
    db: Session = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user)
):
    """
    删除文档
    """
    success = document_service.delete_document(document_id, current_user.id, permanent)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return {"success": True, "message": "文档已删除"} 