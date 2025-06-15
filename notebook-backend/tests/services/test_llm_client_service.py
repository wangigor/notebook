"""
LLMClientService 单元测试
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_client_service import LLMClientService
from app.core.llm_config import LLMConfig, ModelType


class TestLLMClientService:
    """LLMClientService 测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        # 清理单例实例
        LLMClientService._instance = None
        
    def test_singleton_pattern(self):
        """测试单例模式"""
        # 创建两个实例
        service1 = LLMClientService()
        service2 = LLMClientService()
        
        # 验证是同一个实例
        assert service1 is service2
        assert id(service1) == id(service2)
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_get_llm_non_streaming(self, mock_chat_openai):
        """测试获取非流式LLM实例"""
        # 设置mock
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # 创建服务实例
        service = LLMClientService()
        
        # 获取LLM实例
        llm = service.get_llm(streaming=False)
        
        # 验证调用
        mock_chat_openai.assert_called_once()
        call_args = mock_chat_openai.call_args[1]
        assert call_args['streaming'] is False
        assert call_args['model'] == LLMConfig.DEFAULT_MODEL
        assert call_args['temperature'] == LLMConfig.DEFAULT_TEMPERATURE
        
        # 验证返回的是mock实例
        assert llm is mock_llm
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_get_llm_streaming(self, mock_chat_openai):
        """测试获取流式LLM实例"""
        # 设置mock
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # 创建服务实例
        service = LLMClientService()
        
        # 获取LLM实例
        llm = service.get_llm(streaming=True)
        
        # 验证调用
        mock_chat_openai.assert_called_once()
        call_args = mock_chat_openai.call_args[1]
        assert call_args['streaming'] is True
        
        # 验证返回的是mock实例
        assert llm is mock_llm
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_get_chat_llm_default_streaming(self, mock_chat_openai):
        """测试获取对话LLM实例（默认流式）"""
        # 设置mock
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # 创建服务实例
        service = LLMClientService()
        
        # 获取对话LLM实例
        llm = service.get_chat_llm()
        
        # 验证调用
        mock_chat_openai.assert_called_once()
        call_args = mock_chat_openai.call_args[1]
        assert call_args['streaming'] is True  # 对话默认为流式
        
        # 验证返回的是mock实例
        assert llm is mock_llm
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_get_processing_llm_default_non_streaming(self, mock_chat_openai):
        """测试获取处理LLM实例（默认非流式）"""
        # 设置mock
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # 创建服务实例
        service = LLMClientService()
        
        # 获取处理LLM实例
        llm = service.get_processing_llm()
        
        # 验证调用
        mock_chat_openai.assert_called_once()
        call_args = mock_chat_openai.call_args[1]
        assert call_args['streaming'] is False  # 处理默认为非流式
        
        # 验证返回的是mock实例
        assert llm is mock_llm
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_instance_caching(self, mock_chat_openai):
        """测试实例缓存机制"""
        # 设置mock
        mock_llm1 = MagicMock()
        mock_llm2 = MagicMock()
        mock_chat_openai.side_effect = [mock_llm1, mock_llm2]
        
        # 创建服务实例
        service = LLMClientService()
        
        # 第一次获取LLM实例
        llm1 = service.get_llm(streaming=False)
        
        # 第二次获取相同配置的LLM实例
        llm2 = service.get_llm(streaming=False)
        
        # 验证只调用了一次ChatOpenAI（第二次从缓存获取）
        assert mock_chat_openai.call_count == 1
        assert llm1 is llm2  # 应该是同一个实例
        
        # 获取不同配置的LLM实例
        llm3 = service.get_llm(streaming=True)
        
        # 验证调用了第二次ChatOpenAI
        assert mock_chat_openai.call_count == 2
        assert llm3 is not llm1  # 应该是不同的实例
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_custom_configuration(self, mock_chat_openai):
        """测试自定义配置"""
        # 设置mock
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # 创建服务实例
        service = LLMClientService()
        
        # 使用自定义配置获取LLM实例
        custom_config = {
            'model': 'gpt-4',
            'temperature': 0.5,
            'max_tokens': 1000
        }
        llm = service.get_llm(streaming=False, **custom_config)
        
        # 验证调用
        mock_chat_openai.assert_called_once()
        call_args = mock_chat_openai.call_args[1]
        assert call_args['model'] == 'gpt-4'
        assert call_args['temperature'] == 0.5
        assert call_args['max_tokens'] == 1000
        assert call_args['streaming'] is False
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_clear_cache(self, mock_chat_openai):
        """测试清空缓存"""
        # 设置mock
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # 创建服务实例
        service = LLMClientService()
        
        # 获取LLM实例
        service.get_llm(streaming=False)
        
        # 验证缓存中有实例
        cache_info = service.get_cache_info()
        assert cache_info['cached_instances'] == 1
        
        # 清空缓存
        service.clear_cache()
        
        # 验证缓存已清空
        cache_info = service.get_cache_info()
        assert cache_info['cached_instances'] == 0
        assert len(cache_info['cache_keys']) == 0
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_get_cache_info(self, mock_chat_openai):
        """测试获取缓存信息"""
        # 设置mock
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # 创建服务实例
        service = LLMClientService()
        
        # 初始状态
        cache_info = service.get_cache_info()
        assert cache_info['cached_instances'] == 0
        assert len(cache_info['cache_keys']) == 0
        
        # 获取不同配置的LLM实例
        service.get_llm(streaming=False)
        service.get_llm(streaming=True)
        
        # 验证缓存信息
        cache_info = service.get_cache_info()
        assert cache_info['cached_instances'] == 2
        assert len(cache_info['cache_keys']) == 2
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_error_handling(self, mock_chat_openai):
        """测试错误处理"""
        # 设置mock抛出异常
        mock_chat_openai.side_effect = Exception("API连接失败")
        
        # 创建服务实例
        service = LLMClientService()
        
        # 验证异常被正确抛出
        with pytest.raises(Exception) as exc_info:
            service.get_llm(streaming=False)
        
        assert "API连接失败" in str(exc_info.value)
    
    @patch('app.services.llm_client_service.ChatOpenAI')
    def test_parameter_filtering(self, mock_chat_openai):
        """测试参数过滤"""
        # 设置mock
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # 创建服务实例
        service = LLMClientService()
        
        # 传入包含无效参数的配置
        config_with_invalid_params = {
            'model': 'gpt-3.5-turbo',
            'temperature': 0.1,
            'streaming': False,
            'invalid_param': 'should_be_filtered',
            'another_invalid': 123
        }
        
        llm = service.get_llm(**config_with_invalid_params)
        
        # 验证只传递了有效参数
        mock_chat_openai.assert_called_once()
        call_args = mock_chat_openai.call_args[1]
        
        # 验证有效参数存在
        assert 'model' in call_args
        assert 'temperature' in call_args
        assert 'streaming' in call_args
        
        # 验证无效参数被过滤
        assert 'invalid_param' not in call_args
        assert 'another_invalid' not in call_args 