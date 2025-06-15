"""
文档处理模块

提供RAG和图谱构建两种处理模式
"""

from .rag_processor import run as rag_processor_run
from .graph_processor import run as graph_processor_run

__all__ = [
    "rag_processor_run",
    "graph_processor_run"
] 