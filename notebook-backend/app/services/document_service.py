from typing import List, Optional, Dict, Any
import os
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from fastapi import UploadFile, HTTPException
from app.models.document import Document, DocumentCreate, DocumentUpdate
from app.services.vector_store import VectorStoreService
import requests
from io import BytesIO
import csv
import json
import base64
import logging


class DocumentService:
    """文档服务"""
    
    def __init__(self, db: Session, vector_store: VectorStoreService):
        self.db = db
        self.vector_store = vector_store
        
    async def create_document(self, 
                       user_id: int, 
                       name: str,
                       file_type: str,
                       content: str,
                       extracted_text: str,
                       metadata: Optional[Dict[str, Any]] = None) -> Document:
        """创建文档"""
        logger = logging.getLogger(__name__)
        
        # 生成唯一ID
        document_id = f"doc_{uuid.uuid4()}"
        
        # 确保metadata是字典类型
        if metadata is not None and not isinstance(metadata, dict):
            logger.warning(f"元数据不是字典类型，将转换为字典: {type(metadata)}")
            try:
                metadata = dict(metadata)
            except Exception as e:
                logger.error(f"转换元数据为字典失败，将使用空字典: {str(e)}")
                metadata = {}
        
        # 创建文档数据库记录
        db_document = Document(
            document_id=document_id,
            name=name,
            file_type=file_type,
            content=content,
            extracted_text=extracted_text,
            doc_metadata=metadata,
            user_id=user_id
        )
        
        self.db.add(db_document)
        self.db.commit()
        self.db.refresh(db_document)
        
        # 添加到向量存储
        if extracted_text:
            # 限制文本长度在2048字符以内
            max_length = 2048
            if len(extracted_text) > max_length:
                logger.warning(f"提取的文本超过{max_length}字符，将被截断 ({len(extracted_text)} -> {max_length})")
                text_for_vector = extracted_text[:max_length]
            else:
                text_for_vector = extracted_text
                
            # 确保metadata是字典类型
            vector_metadata = {
                "document_id": document_id,
                "name": name,
                "file_type": file_type
            }
            
            # 合并其他元数据
            if metadata and isinstance(metadata, dict):
                vector_metadata.update(metadata)
            
            vector_ids = self.vector_store.add_texts(
                texts=[text_for_vector],
                metadatas=[vector_metadata]
            )
            
            if vector_ids:
                # 更新向量ID
                db_document.vector_id = vector_ids[0]
                self.db.commit()
                self.db.refresh(db_document)
        
        return db_document
    
    def get_document(self, document_id: str, user_id: int) -> Optional[Document]:
        """获取文档"""
        return self.db.query(Document).filter(
            Document.document_id == document_id,
            Document.user_id == user_id,
            Document.deleted == False
        ).first()
    
    def get_documents(self, 
                     user_id: int, 
                     skip: int = 0, 
                     limit: int = 100, 
                     search: Optional[str] = None) -> tuple[List[Document], int]:
        """获取文档列表"""
        query = self.db.query(Document).filter(
            Document.user_id == user_id,
            Document.deleted == False
        )
        
        if search:
            query = query.filter(
                or_(
                    Document.name.ilike(f"%{search}%"),
                    Document.content.ilike(f"%{search}%") if Document.content is not None else False,
                    Document.extracted_text.ilike(f"%{search}%") if Document.extracted_text is not None else False
                )
            )
        
        total = query.count()
        documents = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
        
        return documents, total
    
    def update_document(self, 
                       document_id: str, 
                       user_id: int, 
                       document_update: DocumentUpdate) -> Optional[Document]:
        """更新文档"""
        logger = logging.getLogger(__name__)
        
        db_document = self.get_document(document_id, user_id)
        if not db_document:
            return None
        
        update_data = document_update.dict(exclude_unset=True)
        
        # 处理metadata字段
        if "metadata" in update_data:
            metadata = update_data["metadata"]
            # 确保metadata是字典类型
            if metadata is not None and not isinstance(metadata, dict):
                logger.warning(f"更新元数据不是字典类型，将转换为字典: {type(metadata)}")
                try:
                    metadata = dict(metadata)
                except Exception as e:
                    logger.error(f"转换更新元数据为字典失败，将使用空字典: {str(e)}")
                    metadata = {}
            update_data["metadata"] = metadata
        
        # 更新文档记录
        for key, value in update_data.items():
            # 处理metadata字段到doc_metadata的映射
            if key == "metadata":
                setattr(db_document, "doc_metadata", value)
            else:
                setattr(db_document, key, value)
        
        self.db.commit()
        self.db.refresh(db_document)
        
        # 如果更新了提取文本，也更新向量存储
        if "extracted_text" in update_data and db_document.extracted_text:
            if db_document.vector_id:
                # 删除旧向量
                self.vector_store.delete_texts([db_document.vector_id])
            
            # 限制文本长度在2048字符以内
            max_length = 2048
            extracted_text = db_document.extracted_text
            if len(extracted_text) > max_length:
                logger.warning(f"更新的提取文本超过{max_length}字符，将被截断 ({len(extracted_text)} -> {max_length})")
                text_for_vector = extracted_text[:max_length]
            else:
                text_for_vector = extracted_text
            
            # 确保metadata是字典类型
            metadata = db_document.doc_metadata
            if metadata is not None and not isinstance(metadata, dict):
                try:
                    metadata = dict(metadata)
                except Exception:
                    metadata = {}
            
            # 构建向量元数据
            vector_metadata = {
                "document_id": document_id,
                "name": db_document.name,
                "file_type": db_document.file_type
            }
            
            # 合并其他元数据
            if metadata:
                vector_metadata.update(metadata)
            
            # 添加新向量
            vector_ids = self.vector_store.add_texts(
                texts=[text_for_vector],
                metadatas=[vector_metadata]
            )
            
            if vector_ids:
                db_document.vector_id = vector_ids[0]
                self.db.commit()
                self.db.refresh(db_document)
        
        return db_document
    
    def delete_document(self, document_id: str, user_id: int, permanent: bool = False) -> bool:
        """删除文档"""
        db_document = self.get_document(document_id, user_id)
        if not db_document:
            return False
        
        if permanent:
            # 从向量存储中删除
            if db_document.vector_id:
                self.vector_store.delete_texts([db_document.vector_id])
            
            # 从数据库中删除
            self.db.delete(db_document)
        else:
            # 标记为已删除
            db_document.deleted = True
            
            # 从向量存储中删除
            if db_document.vector_id:
                self.vector_store.delete_texts([db_document.vector_id])
        
        self.db.commit()
        return True
    
    async def process_file(self, 
                    file: UploadFile, 
                    user_id: int,
                    metadata: Optional[Dict[str, Any]] = None) -> Document:
        """处理上传文件"""
        logger = logging.getLogger(__name__)
        
        # 记录开始处理文件
        logger.info(f"开始处理文件: {file.filename}, 内容类型: {file.content_type}")
        
        # 获取文件内容
        content = await file.read()
        
        # 记录文件大小
        logger.info(f"文件大小: {len(content)} 字节")
        
        # 提取文本
        extracted_text = await self._extract_text_from_file(file.filename, file.content_type, content)
        
        # 获取文件类型
        file_extension = os.path.splitext(file.filename)[1].lower() if file.filename else ""
        file_type = file_extension.lstrip(".") or file.content_type or "unknown"
        logger.info(f"文件类型识别为: {file_type}")
        
        # 判断是否为二进制文件
        binary_types = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar']
        is_binary = file_type in binary_types
        
        # 如果是二进制文件，使用Base64编码
        if is_binary:
            logger.info(f"检测到二进制文件类型: {file_type}，将进行Base64编码")
            try:
                # 检查是否包含NUL字符
                has_null = b'\x00' in content
                logger.info(f"文件是否包含NUL字符: {has_null}")
                
                # Base64编码
                encoded_content = base64.b64encode(content).decode('ascii')
                logger.info(f"Base64编码成功，编码后大小: {len(encoded_content)} 字符")
                
                # 添加标记表示这是Base64编码内容
                content_to_save = f"__BASE64__{encoded_content}"
            except Exception as e:
                logger.error(f"Base64编码失败: {str(e)}")
                # 出错时尝试忽略错误字符的普通解码
                content_to_save = content.decode('utf-8', errors='ignore')
        else:
            # 文本文件正常处理
            logger.info(f"文本文件类型: {file_type}，使用普通UTF-8解码")
            content_to_save = content.decode('utf-8', errors='ignore')
        
        # 创建元数据
        file_metadata = {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(content),
            "is_binary_encoded": is_binary,
            **(metadata or {})
        }
        
        # 创建文档
        logger.info("准备创建文档记录")
        return await self.create_document(
            user_id=user_id,
            name=file.filename or "Unnamed document",
            file_type=file_type,
            content=content_to_save,
            extracted_text=extracted_text,
            metadata=file_metadata
        )
    
    async def _extract_text_from_file(self, 
                               filename: Optional[str], 
                               content_type: Optional[str], 
                               content: bytes) -> str:
        """从文件中提取文本"""
        # 根据文件类型调用不同的提取方法
        if not filename:
            return content.decode('utf-8', errors='ignore')
            
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext in ['.txt']:
            # 纯文本文件
            return content.decode('utf-8', errors='ignore')
            
        elif file_ext in ['.pdf']:
            # PDF文件
            try:
                import PyPDF2
                from io import BytesIO
                
                pdf_reader = PyPDF2.PdfReader(BytesIO(content))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
            except Exception as e:
                print(f"PDF提取文本错误: {str(e)}")
                return content.decode('utf-8', errors='ignore')
                
        elif file_ext in ['.doc', '.docx']:
            # Word文档
            try:
                import docx
                from io import BytesIO
                
                doc = docx.Document(BytesIO(content))
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                return text
            except Exception as e:
                print(f"Word提取文本错误: {str(e)}")
                return content.decode('utf-8', errors='ignore')

        elif file_ext in ['.xls', '.xlsx']:
            # Excel文件
            try:
                import openpyxl
                from io import BytesIO
                
                workbook = openpyxl.load_workbook(BytesIO(content))
                text = ""
                for sheet in workbook:
                    text += f"Sheet: {sheet.title}\n"
                    for row in sheet.iter_rows(values_only=True):
                        text += "\t".join([str(cell) if cell is not None else "" for cell in row]) + "\n"
                return text
            except Exception as e:
                print(f"Excel提取文本错误: {str(e)}")
                return content.decode('utf-8', errors='ignore')
                
        elif file_ext in ['.csv']:
            # CSV文件
            try:
                csv_text = content.decode('utf-8', errors='ignore')
                reader = csv.reader(csv_text.splitlines())
                
                extracted_text = ""
                headers = next(reader, [])
                extracted_text += "Headers: " + ", ".join(headers) + "\n\n"
                
                for i, row in enumerate(reader):
                    if i < 1000:  # 限制行数，避免过大
                        extracted_text += "Row " + str(i+1) + ": " + ", ".join(row) + "\n"
                    else:
                        extracted_text += f"\n... (showing first 1000 rows out of more)"
                        break
                        
                return extracted_text
            except Exception as e:
                print(f"CSV提取文本错误: {str(e)}")
                return content.decode('utf-8', errors='ignore')

        elif file_ext in ['.json']:
            # JSON文件
            try:
                json_text = content.decode('utf-8', errors='ignore')
                json_data = json.loads(json_text)
                # 美化输出
                pretty_json = json.dumps(json_data, indent=2, ensure_ascii=False)
                return pretty_json
            except Exception as e:
                print(f"JSON提取文本错误: {str(e)}")
                return content.decode('utf-8', errors='ignore')
                
        elif file_ext in ['.md']:
            # Markdown文件
            try:
                md_text = content.decode('utf-8', errors='ignore')
                # 可以考虑将Markdown转换为纯文本，但简单起见，直接返回原始内容
                return md_text
            except Exception as e:
                print(f"Markdown提取文本错误: {str(e)}")
                return content.decode('utf-8', errors='ignore')
                
        elif file_ext in ['.htm', '.html']:
            # HTML文件
            try:
                from bs4 import BeautifulSoup
                
                html_text = content.decode('utf-8', errors='ignore')
                soup = BeautifulSoup(html_text, 'html.parser')
                
                # 移除脚本和样式
                for script in soup(["script", "style"]):
                    script.extract()
                
                # 获取文本
                text = soup.get_text(separator='\n')
                # 处理多余空白行
                lines = (line.strip() for line in text.splitlines())
                chunks = (line for line in lines if line)
                text = '\n'.join(chunks)
                return text
            except Exception as e:
                print(f"HTML提取文本错误: {str(e)}")
                return content.decode('utf-8', errors='ignore')
        
        # 默认尝试解码为文本
        return content.decode('utf-8', errors='ignore')
        
    async def load_from_web(self, url: str, user_id: int, metadata: Optional[Dict[str, Any]] = None) -> Document:
        """从网页加载文档"""
        try:
            # 获取网页内容
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 检测编码
            content_type = response.headers.get('Content-Type', '')
            if 'charset=' in content_type:
                encoding = content_type.split('charset=')[-1]
            else:
                encoding = response.apparent_encoding
                
            response.encoding = encoding
            
            # 创建文件名
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            path = parsed_url.path.strip('/')
            filename = f"{domain}_{path.replace('/', '_')}.html" if path else f"{domain}.html"
            
            # 使用BeautifulSoup提取文本
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取标题
            title = soup.title.string if soup.title else domain
            
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.extract()
                
            # 获取文本
            extracted_text = soup.get_text(separator='\n')
            lines = (line.strip() for line in extracted_text.splitlines())
            chunks = (line for line in lines if line)
            extracted_text = '\n'.join(chunks)
            
            # 创建元数据
            web_metadata = {
                "source_url": url,
                "domain": domain,
                "title": title,
                **(metadata or {})
            }
            
            # 创建文档
            return await self.create_document(
                user_id=user_id,
                name=title or "Web Page",
                file_type="html",
                content=response.text,
                extracted_text=extracted_text,
                metadata=web_metadata
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"从网页加载文档失败: {str(e)}")
            
    async def load_from_directory(self, directory_path: str, user_id: int, recursive: bool = True) -> List[Document]:
        """从目录加载文档"""
        documents = []
        
        try:
            # 获取目录下所有文件
            for root, dirs, files in os.walk(directory_path):
                for file_name in files:
                    # 文件完整路径
                    file_path = os.path.join(root, file_name)
                    
                    # 检查文件类型
                    file_ext = os.path.splitext(file_name)[1].lower()
                    supported_exts = ['.txt', '.pdf', '.doc', '.docx', '.csv', '.json', '.md', '.html', '.htm', '.xls', '.xlsx']
                    
                    if file_ext in supported_exts:
                        # 读取文件内容
                        with open(file_path, 'rb') as f:
                            content = f.read()
                        
                        # 创建UploadFile对象
                        file = UploadFile(
                            filename=file_name,
                            file=BytesIO(content),
                            size=len(content)
                        )
                        
                        # 创建元数据
                        relative_path = os.path.relpath(file_path, directory_path)
                        file_metadata = {
                            "source_path": file_path,
                            "relative_path": relative_path,
                            "directory": directory_path
                        }
                        
                        # 处理文件
                        document = await self.process_file(file, user_id, file_metadata)
                        documents.append(document)
                
                # 如果不递归，则只处理顶层目录
                if not recursive:
                    break
            
            return documents
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"从目录加载文档失败: {str(e)}")
            
    async def create_custom_document(self, 
                              user_id: int, 
                              name: str, 
                              content: str, 
                              file_type: str = "txt",
                              metadata: Optional[Dict[str, Any]] = None) -> Document:
        """创建自定义文档（不需要上传文件）"""
        try:
            # 提取文本与原始内容相同
            extracted_text = content
            
            # 创建元数据
            custom_metadata = {
                "source": "custom",
                "created_manually": True,
                **(metadata or {})
            }
            
            # 创建文档
            return await self.create_document(
                user_id=user_id,
                name=name,
                file_type=file_type,
                content=content,
                extracted_text=extracted_text,
                metadata=custom_metadata
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"创建自定义文档失败: {str(e)}") 