import pytest
import asyncio
import json
import httpx
from fastapi.testclient import TestClient
from app.main import app
from app.celery_tasks.document_processing import (
    validate_file, extract_text, split_text, 
    generate_embeddings, store_vectors
)

# 创建测试客户端
client = TestClient(app)

@pytest.fixture
def auth_headers():
    """获取认证头信息"""
    # 这里应该实现获取有效的认证token的逻辑
    # 在实际测试中，你可以使用测试数据库中的用户登录获取token
    token = "your_test_token_here"
    return {"Authorization": f"Bearer {token}"}

def test_document_processing_api(auth_headers):
    """测试文档处理API"""
    # 准备测试数据
    test_data = {
        "document_id": "test-doc-001",
        "file_path": "/tmp/test-document.pdf",
        "task_name": "测试文档处理任务"
    }
    
    # 调用API
    response = client.post(
        "/api/tasks/document_processing",
        json=test_data,
        headers=auth_headers
    )
    
    # 验证响应
    assert response.status_code == 202
    result = response.json()
    assert "task_id" in result
    assert result["document_id"] == test_data["document_id"]
    assert "message" in result

def test_task_chain_functions():
    """测试任务链中的各个函数"""
    # 这个测试应该在具有完整测试数据库和环境的情况下运行
    # 以下是模拟测试的示例框架
    
    document_id = "test-doc-001"
    task_id = "test-task-001"
    task_detail_id = 1
    file_path = "/tmp/test-document.pdf"
    
    # 测试validate_file函数
    result = validate_file(document_id, task_id, task_detail_id, file_path)
    assert result["document_id"] == document_id
    assert result["file_path"] == file_path
    assert result["validated"] is True
    
    # 测试extract_text函数
    result = extract_text(result, document_id, task_id, task_detail_id + 1)
    assert "extracted_text" in result
    
    # 测试split_text函数
    result = split_text(result, document_id, task_id, task_detail_id + 2)
    assert "chunks" in result
    assert len(result["chunks"]) > 0
    
    # 测试generate_embeddings函数
    result = generate_embeddings(result, document_id, task_id, task_detail_id + 3)
    assert "embeddings" in result
    assert len(result["embeddings"]) == len(result["chunks"])
    
    # 测试store_vectors函数
    result = store_vectors(result, document_id, task_id, task_detail_id + 4)
    assert result["status"] == "completed"
    assert result["document_id"] == document_id
    assert result["task_id"] == task_id

@pytest.mark.asyncio
async def test_websocket_connection():
    """测试WebSocket连接和消息推送"""
    # 使用httpx进行WebSocket连接测试
    # 这只是一个示例框架，实际测试需要有效的token和任务ID
    
    token = "your_test_token_here"
    task_id = "test-task-001"
    
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        async with client.websocket_connect(
            "/ws",
            headers={"Sec-WebSocket-Protocol": f"Bearer.{token}"}
        ) as websocket:
            # 发送任务ID
            await websocket.send_text(json.dumps({"task_id": task_id}))
            
            # 接收连接确认消息
            response = await websocket.receive_text()
            response_data = json.loads(response)
            assert response_data["event"] == "connection_established"
            assert response_data["task_id"] == task_id
            
            # 测试接收任务更新
            # 在实际测试中，你可能需要使用后台任务模拟任务更新
            
            # 关闭连接
            await websocket.close()

if __name__ == "__main__":
    # 简单的手动测试
    print("运行文档处理功能测试...")
    
    # 在这里可以添加手动测试逻辑
    # 例如，创建任务并观察WebSocket更新 