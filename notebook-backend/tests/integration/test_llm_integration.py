"""
LLM 集成测试
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.llm_client_service import LLMClientService
from app.agents.knowledge_agent import KnowledgeAgent
from app.services.entity_extraction_service import EntityExtractionService
from app.services.relationship_service import RelationshipService


class TestLLMIntegration:
    """LLM 集成测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        # 清理单例实例
        LLMClientService._instance = None
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    @patch('app.agents.knowledge_agent.MemoryService')
    def test_knowledge_agent_integration(self, mock_memory_service, mock_chat_openai):
        """测试与 Knowledge Agent 的集成"""
        # 设置mock
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # 设置memory service mock
        mock_memory = MagicMock()
        mock_memory_service.return_value = mock_memory
        mock_memory.get_context_for_query.return_value = {
            "history": "测试历史",
            "documents": []
        }
        
        # 创建Knowledge Agent
        agent = KnowledgeAgent()
        
        # 验证LLM服务被正确集成
        # 检查非流式LLM是否被创建
        assert mock_chat_openai.call_count >= 1
        
        # 检查是否有流式和非流式的调用
        streaming_calls = []
        for call in mock_chat_openai.call_args_list:
            if call[1].get('streaming') is not None:
                streaming_calls.append(call[1]['streaming'])
        
        # 应该有非流式调用（在_build_agent_graph中）
        assert False in streaming_calls
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    @pytest.mark.asyncio
    async def test_entity_extraction_integration(self, mock_chat_openai):
        """测试与实体抽取服务的集成"""
        # 设置mock LLM
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '''
        ```json
        {
            "entities": [
                {
                    "name": "测试实体",
                    "type": "概念",
                    "description": "这是一个测试实体",
                    "properties": {},
                    "confidence": 0.9,
                    "start_pos": 0,
                    "end_pos": 4
                }
            ]
        }
        ```
        '''
        mock_llm.ainvoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm
        
        # 创建实体抽取服务
        entity_service = EntityExtractionService()
        
        # 测试数据
        chunks = [
            {
                'id': 'chunk_0',
                'content': '测试实体是一个重要的概念。'
            }
        ]
        
        # 执行实体抽取
        entities = await entity_service.extract_entities_from_chunks(chunks)
        
        # 验证结果
        assert len(entities) == 1
        assert entities[0].name == "测试实体"
        assert entities[0].type == "概念"
        
        # 验证LLM被正确调用
        mock_chat_openai.assert_called_once()
        call_args = mock_chat_openai.call_args[1]
        assert call_args['streaming'] is False  # 实体抽取应该使用非流式
        
        # 验证LLM的ainvoke方法被调用
        mock_llm.ainvoke.assert_called_once()
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    @pytest.mark.asyncio
    async def test_relationship_service_integration(self, mock_chat_openai):
        """测试与关系识别服务的集成"""
        # 设置mock LLM
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '''
        ```json
        {
            "relationships": [
                {
                    "source_entity": "实体A",
                    "target_entity": "实体B",
                    "relationship_type": "关联",
                    "description": "实体A与实体B相关联",
                    "confidence": 0.8
                }
            ]
        }
        ```
        '''
        mock_llm.ainvoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm
        
        # 创建关系识别服务
        relationship_service = RelationshipService()
        
        # 创建测试实体
        from app.services.entity_extraction_service import Entity
        entities = [
            Entity(
                id="entity_1",
                name="实体A",
                type="概念",
                description="测试实体A",
                properties={},
                confidence=0.9,
                source_text="实体A是一个概念",
                start_pos=0,
                end_pos=3
            ),
            Entity(
                id="entity_2",
                name="实体B",
                type="概念",
                description="测试实体B",
                properties={},
                confidence=0.9,
                source_text="实体B是另一个概念",
                start_pos=10,
                end_pos=13
            )
        ]
        
        # 测试数据
        chunks = [
            {
                'id': 'chunk_0',
                'content': '实体A与实体B有密切的关联关系。'
            }
        ]
        
        # 执行关系抽取
        relationships = await relationship_service.extract_relationships_from_entities(entities, chunks)
        
        # 验证LLM被正确调用
        mock_chat_openai.assert_called_once()
        call_args = mock_chat_openai.call_args[1]
        assert call_args['streaming'] is False  # 关系抽取应该使用非流式
        
        # 验证LLM的ainvoke方法被调用
        mock_llm.ainvoke.assert_called_once()
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    @pytest.mark.asyncio
    async def test_concurrent_llm_usage(self, mock_chat_openai):
        """测试并发使用LLM的场景"""
        # 设置mock
        mock_llm_streaming = AsyncMock()
        mock_llm_non_streaming = AsyncMock()
        
        # 根据streaming参数返回不同的mock
        def create_llm(**kwargs):
            if kwargs.get('streaming', False):
                return mock_llm_streaming
            else:
                return mock_llm_non_streaming
        
        mock_chat_openai.side_effect = create_llm
        
        # 创建服务实例
        service = LLMClientService()
        
        # 并发获取不同类型的LLM实例
        async def get_chat_llm():
            return service.get_chat_llm(streaming=True)
        
        async def get_processing_llm():
            return service.get_processing_llm(streaming=False)
        
        # 并发执行
        results = await asyncio.gather(
            get_chat_llm(),
            get_processing_llm(),
            get_chat_llm(),  # 应该从缓存获取
            get_processing_llm()  # 应该从缓存获取
        )
        
        # 验证结果
        assert len(results) == 4
        assert results[0] is mock_llm_streaming  # 第一个chat LLM
        assert results[1] is mock_llm_non_streaming  # 第一个processing LLM
        assert results[2] is mock_llm_streaming  # 缓存的chat LLM
        assert results[3] is mock_llm_non_streaming  # 缓存的processing LLM
        
        # 验证只创建了两个不同的LLM实例
        assert mock_chat_openai.call_count == 2
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_thread_safety(self, mock_chat_openai):
        """测试线程安全性"""
        import threading
        import time
        
        # 设置mock
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # 用于收集创建的服务实例
        services = []
        
        def create_service():
            service = LLMClientService()
            services.append(service)
            time.sleep(0.01)  # 模拟一些处理时间
        
        # 创建多个线程同时创建服务实例
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_service)
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证所有服务实例都是同一个（单例模式）
        assert len(services) == 10
        first_service = services[0]
        for service in services[1:]:
            assert service is first_service
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    @pytest.mark.asyncio
    async def test_error_propagation(self, mock_chat_openai):
        """测试错误传播"""
        # 设置mock抛出异常
        mock_chat_openai.side_effect = Exception("LLM初始化失败")
        
        # 创建实体抽取服务
        entity_service = EntityExtractionService()
        
        # 测试数据
        chunks = [
            {
                'id': 'chunk_0',
                'content': '测试内容'
            }
        ]
        
        # 执行实体抽取，应该捕获并处理异常
        entities = await entity_service.extract_entities_from_chunks(chunks)
        
        # 验证在LLM初始化失败时，返回空列表而不是抛出异常
        assert entities == []
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_configuration_consistency(self, mock_chat_openai):
        """测试配置一致性"""
        # 设置mock
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # 创建服务实例
        service = LLMClientService()
        
        # 获取不同类型的LLM实例
        chat_llm = service.get_chat_llm()
        processing_llm = service.get_processing_llm()
        
        # 验证调用次数
        assert mock_chat_openai.call_count == 2
        
        # 验证配置参数
        calls = mock_chat_openai.call_args_list
        
        # 第一个调用（chat LLM）应该是流式的
        chat_call_args = calls[0][1]
        assert chat_call_args['streaming'] is True
        
        # 第二个调用（processing LLM）应该是非流式的
        processing_call_args = calls[1][1]
        assert processing_call_args['streaming'] is False
        
        # 其他配置应该一致
        assert chat_call_args['model'] == processing_call_args['model']
        assert chat_call_args['temperature'] == processing_call_args['temperature'] 