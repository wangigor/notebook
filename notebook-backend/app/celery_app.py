from celery import Celery

# 创建Celery实例
celery_app = Celery("notebook_app")

# 加载配置
celery_app.config_from_object("app.celery_config")

# 自动发现任务
celery_app.autodiscover_tasks(["app.celery_tasks"])

if __name__ == "__main__":
    celery_app.start() 