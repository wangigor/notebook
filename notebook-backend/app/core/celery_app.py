from celery import Celery
from app.core.config import settings
from app.services.llm_client_service import LLMClientService
import logging
import sys
import os

logger = logging.getLogger(__name__)

# macOS fork 安全设置
if sys.platform == 'darwin':
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'

celery_app = Celery(
    "notebook_ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# macOS 特定配置
celery_config = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
}

# macOS 系统使用 solo 池避免 fork 问题
if sys.platform == 'darwin':
    celery_config.update({
        "worker_pool": "solo",
        "worker_concurrency": 1,
        "worker_prefetch_multiplier": 1,
        "task_acks_late": True,
        "worker_disable_rate_limits": True,
    })
else:
    celery_config.update({
        "worker_pool": "gevent",
        "worker_concurrency": 100,
    })

celery_app.conf.update(celery_config)

# 设置自动加载任务
celery_app.autodiscover_tasks(["app.worker", "app.tasks"])

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Celery 配置完成后执行的操作"""
    # 重新初始化 LLM 实例
    llm_service = LLMClientService()
    llm_service.reinitialize()
    logger.info("Celery worker 中的 LLM 实例重新初始化完成") 