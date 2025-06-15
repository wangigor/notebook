from celery import Celery
from app.core.config import settings
from app.services.llm_client_service import LLMClientService
import logging

logger = logging.getLogger(__name__)

celery_app = Celery(
    "notebook_ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# 设置自动加载任务
celery_app.autodiscover_tasks(["app.worker"])

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Celery 配置完成后执行的操作"""
    # 重新初始化 LLM 实例
    llm_service = LLMClientService()
    llm_service.reinitialize()
    logger.info("Celery worker 中的 LLM 实例重新初始化完成") 