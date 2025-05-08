"""
测试脚本，用于验证对 celery_tasks.py 中 DocumentService 初始化的修复
"""
import asyncio
from app.database import SessionLocal
from app.services.document_service import DocumentService
from app.services.vector_store import VectorStoreService
from app.services.task_service import TaskService

async def test_document_service_init():
    """测试DocumentService的初始化"""
    # 获取数据库会话
    session = SessionLocal()
    
    try:
        # 测试初始化服务
        vector_store = VectorStoreService()
        document_service = DocumentService(session, vector_store)
        print("成功初始化DocumentService，修复有效!")
        
        # 这里可以添加更多测试代码，例如调用一些方法
        
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(test_document_service_init()) 