import pytest
from app.core.celery_app import celery_app
import app.celery_config as celery_config

def test_celery_app_configuration():
    """测试Celery应用配置是否正确"""
    # 验证Celery应用是否已创建
    assert celery_app is not None
    
    # 验证Celery应用的配置
    assert celery_app.conf.task_serializer == 'json'
    assert celery_app.conf.result_serializer == 'json'
    assert celery_app.conf.accept_content == ['json']
    
    # 验证Celery配置模块
    assert hasattr(celery_config, 'broker_url')
    assert hasattr(celery_config, 'result_backend')

def test_celery_task_routes():
    """测试Celery任务路由配置"""
    # 验证任务路由配置
    assert hasattr(celery_config, 'task_routes')
    assert isinstance(celery_config.task_routes, dict)
    assert 'process_document' in celery_config.task_routes
    assert celery_config.task_routes['process_document'] == {'queue': 'document_processing'} 