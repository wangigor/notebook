from celery import Celery
from app.core.config import settings

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