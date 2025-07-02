"""
文件处理工具函数
"""
import os
import tempfile
import logging
from fastapi import UploadFile
from typing import Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

async def save_upload_file_temp(upload_file: UploadFile) -> str:
    """
    保存上传的文件到临时目录
    
    参数:
        upload_file: 上传的文件对象
        
    返回:
        临时文件路径
    """
    try:
        # 创建临时文件
        suffix = os.path.splitext(upload_file.filename)[1] if upload_file.filename else ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            # 读取上传文件内容
            content = await upload_file.read()
            # 写入临时文件
            temp_file.write(content)
            # 返回临时文件路径
            logger.info(f"文件已保存到临时路径: {temp_file.name}")
            return temp_file.name
    except Exception as e:
        logger.error(f"保存上传文件失败: {str(e)}")
        raise Exception(f"保存上传文件失败: {str(e)}")

def get_file_extension(filename: str) -> str:
    """
    获取文件扩展名
    
    参数:
        filename: 文件名
        
    返回:
        文件扩展名（小写）
    """
    if not filename:
        return ""
    return os.path.splitext(filename)[1].lower().lstrip(".")

def parse_metadata(metadata_str: Optional[str]) -> dict:
    """
    解析元数据字符串
    
    参数:
        metadata_str: 元数据JSON字符串
        
    返回:
        解析后的元数据字典
    """
    if not metadata_str:
        return {}
    
    try:
        import json
        return json.loads(metadata_str)
    except Exception as e:
        logger.warning(f"解析元数据失败: {str(e)}")
        return {"notes": metadata_str}

def to_serializable(obj):
    """
    递归将pandas/numpy类型转换为原生Python类型，便于json序列化
    """
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_serializable(i) for i in obj]
    elif isinstance(obj, (np.integer, pd.Int64Dtype)):
        return int(obj)
    elif isinstance(obj, (np.floating, pd.Float64Dtype)):
        return float(obj)
    elif hasattr(obj, 'item') and callable(obj.item):  # numpy标量
        return obj.item()
    else:
        return obj 