"""
Worker 模块初始化文件
包含异步任务处理相关功能
"""

from app.worker.celery_tasks import process_document, cancel_document_process

__all__ = ["process_document", "cancel_document_process"] 