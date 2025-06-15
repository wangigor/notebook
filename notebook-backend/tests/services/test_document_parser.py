"""
文档解析器测试模块
"""

import os
import pytest
from pathlib import Path
from app.services.document_parser import DocumentParser, DocumentStructure

@pytest.fixture
def parser():
    return DocumentParser()

@pytest.fixture
def test_files_dir():
    return Path(__file__).parent.parent / "test_files"

def test_pdf_parsing(parser, test_files_dir):
    """测试PDF文件解析"""
    pdf_file = test_files_dir / "test.pdf"
    if not pdf_file.exists():
        pytest.skip("测试PDF文件不存在")
    
    result = parser.parse(str(pdf_file))
    assert "content" in result
    assert "structure" in result
    assert "file_info" in result
    assert "parse_timestamp" in result
    assert isinstance(result["structure"], DocumentStructure)
    assert len(result["content"]) > 0

def test_docx_parsing(parser, test_files_dir):
    """测试DOCX文件解析"""
    docx_file = test_files_dir / "test.docx"
    if not docx_file.exists():
        pytest.skip("测试DOCX文件不存在")
    
    result = parser.parse(str(docx_file))
    assert "content" in result
    assert "structure" in result
    assert "file_info" in result
    assert "parse_timestamp" in result
    assert isinstance(result["structure"], DocumentStructure)
    assert len(result["content"]) > 0

def test_structure_analysis(parser):
    """测试文档结构分析"""
    content = """
    第一章 简介
    这是一个测试文档。
    
    1.1 背景
    这是背景部分。
    
    • 列表项1
    • 列表项2
    
    1.2 目标
    这是目标部分。
    """
    
    structure = parser._analyze_structure(content)
    assert isinstance(structure, DocumentStructure)
    assert len(structure.headings) > 0
    assert len(structure.paragraphs) > 0
    assert len(structure.lists) > 0

def test_heading_detection(parser):
    """测试标题检测"""
    # 测试全大写标题
    assert parser._is_likely_heading("INTRODUCTION")
    
    # 测试数字开头标题
    assert parser._is_likely_heading("1. 简介")
    
    # 测试章节标题
    assert parser._is_likely_heading("第一章 背景")
    
    # 测试普通文本
    assert not parser._is_likely_heading("这是一个普通的段落。")

def test_list_item_detection(parser):
    """测试列表项检测"""
    # 测试项目符号
    assert parser._is_list_item("• 列表项")
    assert parser._is_list_item("- 列表项")
    assert parser._is_list_item("* 列表项")
    
    # 测试数字列表
    assert parser._is_list_item("1. 列表项")
    assert parser._is_list_item("1) 列表项")
    
    # 测试普通文本
    assert not parser._is_list_item("这是一个普通的段落。")

def test_invalid_file(parser):
    """测试无效文件处理"""
    with pytest.raises(FileNotFoundError):
        parser.parse("nonexistent_file.pdf")

def test_file_permission_error(parser, test_files_dir):
    """测试文件权限错误处理"""
    # 创建一个临时文件并设置只读权限
    temp_file = test_files_dir / "temp.txt"
    try:
        temp_file.write_text("test content")
        os.chmod(temp_file, 0o444)  # 只读权限
        
        with pytest.raises(Exception):
            parser.parse(str(temp_file))
    finally:
        # 恢复权限并删除文件
        os.chmod(temp_file, 0o666)
        temp_file.unlink() 