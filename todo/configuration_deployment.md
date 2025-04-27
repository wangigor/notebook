## 六、配置与部署

### 1. MinIO配置
```python
# settings.py
# MinIO配置
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_DOCUMENT_BUCKET = os.getenv("MINIO_DOCUMENT_BUCKET", "documents")
```

### 2. Qdrant配置（新增）
```python
# settings.py
# Qdrant配置
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
```

### 3. Redis配置
```python
# settings.py
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

CELERY_BROKER_URL = f"redis://{':' + REDIS_PASSWORD + '@' if REDIS_PASSWORD else ''}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
```

### 4. Celery配置
```python
# celery_config.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "document_processing",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.document_processing"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_time_limit=3600,  # 1小时超时
    worker_max_tasks_per_child=200,
    worker_prefetch_multiplier=4
)
```

### 5. Docker部署配置
```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: 
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - minio
      - qdrant
    environment:
      - DATABASE_URL=postgresql://user:password@postgres:5432/dbname
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
      - MINIO_SECURE=false
      - QDRANT_URL=http://qdrant:6333
      - QDRANT_API_KEY=
    volumes:
      - ./app:/app
    restart: always

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    depends_on:
      - redis
      - postgres
      - minio
      - qdrant
    environment:
      - DATABASE_URL=postgresql://user:password@postgres:5432/dbname
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
      - MINIO_SECURE=false
      - QDRANT_URL=http://qdrant:6333
      - QDRANT_API_KEY=
    volumes:
      - ./app:/app
    restart: always
    command: celery -A app.core.celery_app worker --loglevel=info

  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    volumes:
      - minio_data:/data
    command: server --console-address ":9001" /data
    restart: always

  redis:
    image: redis:7.0-alpine
    ports:
      - "6379:6379"
    restart: always
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=dbname
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always
    
  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    restart: always

volumes:
  redis_data:
  postgres_data:
  minio_data:
  qdrant_data:
``` 