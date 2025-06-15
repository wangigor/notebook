"""
文档加载器测试模块
"""

import os
import pytest
from pathlib import Path
from app.services.document_loader import LangChainDocumentLoader

@pytest.fixture
def loader():
    return LangChainDocumentLoader()

@pytest.fixture
def test_files_dir():
    return Path(__file__).parent.parent / "test_files"

def test_pdf_loading(loader, test_files_dir):
    """测试PDF文件加载"""
    pdf_file = test_files_dir / "test.pdf"
    if not pdf_file.exists():
        pytest.skip("测试PDF文件不存在")
    
    result = loader.load(str(pdf_file))
    assert "content" in result
    assert "metadata" in result
    assert "page_count" in result
    assert isinstance(result["content"], str)
    assert len(result["content"]) > 0

def test_docx_loading(loader, test_files_dir):
    """测试DOCX文件加载"""
    docx_file = test_files_dir / "test.docx"
    if not docx_file.exists():
        pytest.skip("测试DOCX文件不存在")
    
    result = loader.load(str(docx_file))
    assert "content" in result
    assert "metadata" in result
    assert isinstance(result["content"], str)
    assert len(result["content"]) > 0

def test_txt_loading(loader, test_files_dir):
    """测试TXT文件加载"""
    txt_file = test_files_dir / "test.txt"
    if not txt_file.exists():
        pytest.skip("测试TXT文件不存在")
    
    result = loader.load(str(txt_file))
    assert "content" in result
    assert "metadata" in result
    assert isinstance(result["content"], str)
    assert len(result["content"]) > 0

def test_invalid_file(loader):
    """测试无效文件处理"""
    with pytest.raises(FileNotFoundError):
        loader.load("nonexistent_file.pdf")

def test_file_permission_error(loader, test_files_dir):
    """测试文件权限错误处理"""
    # 创建一个临时文件并设置只读权限
    temp_file = test_files_dir / "temp.txt"
    try:
        temp_file.write_text("test content")
        os.chmod(temp_file, 0o444)  # 只读权限
        
        with pytest.raises(Exception):
            loader.load(str(temp_file))
    finally:
        # 恢复权限并删除文件
        os.chmod(temp_file, 0o666)
        temp_file.unlink() 