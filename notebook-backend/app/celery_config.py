from app.core.config import settings

# Celery配置
broker_url = settings.CELERY_BROKER_URL
result_backend = settings.CELERY_RESULT_BACKEND

# 任务序列化格式
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# 任务执行设置
task_acks_late = True
worker_prefetch_multiplier = 1
task_track_started = True

# 日志配置
worker_redirect_stdouts = False
worker_redirect_stdouts_level = 'INFO'

# 任务路由
task_routes = {
    'process_document': {'queue': 'document_processing'},
    'validate_file': {'queue': 'document_processing'},
    'extract_text': {'queue': 'document_processing'},
    'split_text': {'queue': 'document_processing'},
    'generate_embeddings': {'queue': 'document_processing'},
    'store_vectors': {'queue': 'document_processing'},
}

# 任务软时间限制 (秒)
task_soft_time_limit = 600
# 任务硬时间限制 (秒)
task_time_limit = 1200

# 预定任务设置
beat_schedule = {} 