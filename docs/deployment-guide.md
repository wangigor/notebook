# LLM图构建器部署指南

## 概述

本指南提供了LLM图构建器的完整部署方案，包括本地开发、Docker容器化、Kubernetes集群部署等多种环境配置。

## 系统要求

### 最低配置
- **CPU**: 4核心
- **内存**: 8GB RAM
- **存储**: 50GB可用空间
- **操作系统**: Linux (Ubuntu 20.04+), macOS 10.15+, Windows 10+

### 推荐配置
- **CPU**: 8核心
- **内存**: 16GB RAM
- **存储**: 100GB SSD
- **GPU**: NVIDIA GPU (可选，用于本地LLM)

### 依赖服务
- **Neo4j**: 5.0+
- **Redis**: 6.0+ (可选，用于缓存)
- **Python**: 3.9+
- **Node.js**: 18+

## 本地开发环境

### 1. 后端设置

```bash
# 克隆项目
git clone <repository-url>
cd llm-graph-builder

# 创建Python虚拟环境
cd backend
python -m venv myenv
source myenv/bin/activate  # Linux/macOS
# myenv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 环境变量配置
cp .env.example .env
# 编辑.env文件配置必要参数
```

**requirements.txt 示例**:
```txt
fastapi==0.104.1
uvicorn==0.24.0
neo4j==5.15.0
langchain==0.1.0
langchain-openai==0.0.2
langchain-google-vertexai==0.0.1
sentence-transformers==2.2.2
python-multipart==0.0.6
python-dotenv==1.0.0
redis==5.0.1
celery==5.3.4
prometheus-client==0.19.0
structlog==23.2.0
```

**环境变量配置 (.env)**:
```bash
# Neo4j配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

# LLM API配置
LLM_MODEL_CONFIG_openai=gpt-4,your_openai_api_key
LLM_MODEL_CONFIG_gemini=gemini-pro
LLM_MODEL_CONFIG_anthropic=claude-3-sonnet-20240229,your_anthropic_api_key

# 嵌入模型配置
EMBEDDING_MODEL=sentence_transformer
EMBEDDING_MODEL_PATH=all-MiniLM-L6-v2
IS_EMBEDDING=True

# 文件存储配置
UPLOAD_FOLDER=./uploads
MAX_FILE_SIZE=104857600  # 100MB
GCS_FILE_CACHE=False

# 处理配置
MAX_TOKEN_CHUNK_SIZE=10000
TOKEN_CHUNK_SIZE=512
CHUNK_OVERLAP=50
UPDATE_GRAPH_CHUNKS_PROCESSED=20

# 相似度配置
KNN_MIN_SCORE=0.94
DUPLICATE_SCORE_VALUE=0.95

# Redis配置 (可选)
REDIS_URL=redis://localhost:6379/0

# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=json

# 安全配置
JWT_SECRET=your_jwt_secret_key
API_RATE_LIMIT=100
```

### 2. 前端设置

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 环境变量配置
cp .env.example .env.local
# 编辑环境变量

# 启动开发服务器
npm run dev
```

**前端环境变量 (.env.local)**:
```bash
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000/ws
REACT_APP_VERSION=1.0.0
REACT_APP_ENV=development
```

### 3. Neo4j数据库设置

#### 使用Docker快速启动
```bash
docker run \
    --name neo4j-llm-graph \
    -p 7474:7474 -p 7687:7687 \
    -d \
    -v neo4j_data:/data \
    -v neo4j_logs:/logs \
    -v neo4j_import:/var/lib/neo4j/import \
    -v neo4j_plugins:/plugins \
    --env NEO4J_AUTH=neo4j/password \
    --env NEO4J_PLUGINS='["apoc","graph-data-science"]' \
    --env NEO4J_dbms_security_procedures_unrestricted=apoc.*,gds.* \
    --env NEO4J_dbms_security_procedures_allowlist=apoc.*,gds.* \
    neo4j:5.15
```

#### 手动安装配置
1. 下载Neo4j Desktop或Server版本
2. 安装APOC和GDS插件
3. 配置neo4j.conf:
```conf
# 内存配置
server.memory.heap.initial_size=2G
server.memory.heap.max_size=4G
server.memory.pagecache.size=1G

# 网络配置
server.default_listen_address=0.0.0.0
server.bolt.listen_address=:7687
server.http.listen_address=:7474

# 插件配置
server.directories.plugins=/var/lib/neo4j/plugins
dbms.security.procedures.unrestricted=apoc.*,gds.*
dbms.security.procedures.allowlist=apoc.*,gds.*

# 性能配置
cypher.runtime=slotted
```

### 4. 启动服务

```bash
# 启动后端服务
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端服务 (新终端)
cd frontend
npm start

# 启动Celery worker (可选，用于异步任务)
cd backend
celery -A main.celery worker --loglevel=info
```

## Docker容器化部署

### 1. 项目Docker配置

**后端Dockerfile**:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建非root用户
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**前端Dockerfile**:
```dockerfile
# 构建阶段
FROM node:18-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

# 生产阶段
FROM nginx:alpine

COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**Nginx配置 (nginx.conf)**:
```nginx
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    upstream backend {
        server backend:8000;
    }

    server {
        listen 80;
        server_name localhost;

        # 前端静态资源
        location / {
            root /usr/share/nginx/html;
            index index.html index.htm;
            try_files $uri $uri/ /index.html;
        }

        # API代理
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # WebSocket支持
        location /ws/ {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
        }
    }
}
```

### 2. Docker Compose配置

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  # 前端服务
  frontend:
    build: 
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    networks:
      - app-network

  # 后端服务
  backend:
    build: 
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USERNAME=neo4j
      - NEO4J_PASSWORD=password
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    networks:
      - app-network
    restart: unless-stopped

  # Neo4j数据库
  neo4j:
    image: neo4j:5.15
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_PLUGINS=["apoc","graph-data-science"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*,gds.*
      - NEO4J_dbms_memory_heap_initial__size=2G
      - NEO4J_dbms_memory_heap_max__size=4G
      - NEO4J_dbms_memory_pagecache_size=1G
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - neo4j_import:/var/lib/neo4j/import
      - neo4j_plugins:/plugins
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "password", "RETURN 1"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped

  # Redis缓存
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped

  # Celery Worker (可选)
  celery-worker:
    build: 
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A main.celery worker --loglevel=info
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USERNAME=neo4j
      - NEO4J_PASSWORD=password
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - neo4j
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    networks:
      - app-network
    restart: unless-stopped

networks:
  app-network:
    driver: bridge

volumes:
  neo4j_data:
  neo4j_logs:
  neo4j_import:
  neo4j_plugins:
  redis_data:
```

**生产环境Docker Compose (docker-compose.prod.yml)**:
```yaml
version: '3.8'

services:
  frontend:
    build: 
      context: ./frontend
      dockerfile: Dockerfile.prod
    environment:
      - NODE_ENV=production
    restart: always

  backend:
    build: 
      context: ./backend
      dockerfile: Dockerfile.prod
    environment:
      - ENV=production
      - LOG_LEVEL=WARNING
    restart: always
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend
    restart: always

  neo4j:
    image: neo4j:5.15-enterprise
    environment:
      - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 8G
        reservations:
          cpus: '1.0'
          memory: 4G
    restart: always
```

### 3. 启动Docker部署

```bash
# 开发环境
docker-compose up -d

# 生产环境
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend

# 停止服务
docker-compose down

# 完全清理
docker-compose down -v --remove-orphans
```

## Kubernetes集群部署

### 1. Kubernetes配置文件

**Namespace定义**:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: llm-graph-builder
```

**ConfigMap配置**:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: llm-graph-builder
data:
  NEO4J_URI: "bolt://neo4j-service:7687"
  NEO4J_DATABASE: "neo4j"
  REDIS_URL: "redis://redis-service:6379/0"
  LOG_LEVEL: "INFO"
  MAX_TOKEN_CHUNK_SIZE: "10000"
```

**Secret配置**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
  namespace: llm-graph-builder
type: Opaque
data:
  NEO4J_USERNAME: bmVvNGo=  # neo4j base64编码
  NEO4J_PASSWORD: cGFzc3dvcmQ=  # password base64编码
  OPENAI_API_KEY: eW91cl9vcGVuYWlfYXBpX2tleQ==
  JWT_SECRET: eW91cl9qd3Rfc2VjcmV0
```

**Neo4j部署**:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: neo4j
  namespace: llm-graph-builder
spec:
  serviceName: neo4j-service
  replicas: 1
  selector:
    matchLabels:
      app: neo4j
  template:
    metadata:
      labels:
        app: neo4j
    spec:
      containers:
      - name: neo4j
        image: neo4j:5.15
        ports:
        - containerPort: 7474
        - containerPort: 7687
        env:
        - name: NEO4J_AUTH
          value: "neo4j/password"
        - name: NEO4J_PLUGINS
          value: '["apoc","graph-data-science"]'
        - name: NEO4J_dbms_memory_heap_initial__size
          value: "2G"
        - name: NEO4J_dbms_memory_heap_max__size
          value: "4G"
        volumeMounts:
        - name: neo4j-storage
          mountPath: /data
        resources:
          requests:
            memory: "4Gi"
            cpu: "1000m"
          limits:
            memory: "8Gi"
            cpu: "2000m"
        readinessProbe:
          tcpSocket:
            port: 7687
          initialDelaySeconds: 30
          periodSeconds: 10
        livenessProbe:
          tcpSocket:
            port: 7687
          initialDelaySeconds: 60
          periodSeconds: 30
  volumeClaimTemplates:
  - metadata:
      name: neo4j-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi

---
apiVersion: v1
kind: Service
metadata:
  name: neo4j-service
  namespace: llm-graph-builder
spec:
  selector:
    app: neo4j
  ports:
  - name: http
    port: 7474
    targetPort: 7474
  - name: bolt
    port: 7687
    targetPort: 7687
  type: ClusterIP
```

**Backend部署**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: llm-graph-builder
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: llm-graph-builder-backend:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        volumeMounts:
        - name: upload-storage
          mountPath: /app/uploads
      volumes:
      - name: upload-storage
        persistentVolumeClaim:
          claimName: upload-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: backend-service
  namespace: llm-graph-builder
spec:
  selector:
    app: backend
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

**Frontend部署**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: llm-graph-builder
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: llm-graph-builder-frontend:latest
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"

---
apiVersion: v1
kind: Service
metadata:
  name: frontend-service
  namespace: llm-graph-builder
spec:
  selector:
    app: frontend
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
```

**Ingress配置**:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  namespace: llm-graph-builder
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
spec:
  tls:
  - hosts:
    - llm-graph-builder.example.com
    secretName: llm-graph-builder-tls
  rules:
  - host: llm-graph-builder.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: backend-service
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-service
            port:
              number: 80
```

### 2. 部署脚本

**deploy.sh**:
```bash
#!/bin/bash

set -e

# 配置变量
NAMESPACE="llm-graph-builder"
DOCKER_REGISTRY="your-registry.com"
VERSION="latest"

echo "部署LLM图构建器到Kubernetes..."

# 创建命名空间
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# 应用配置
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/pvc.yaml

# 部署数据库
kubectl apply -f k8s/neo4j.yaml
kubectl apply -f k8s/redis.yaml

# 等待数据库就绪
echo "等待数据库启动..."
kubectl wait --for=condition=ready pod -l app=neo4j -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n $NAMESPACE --timeout=300s

# 部署应用
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/ingress.yaml

# 等待部署完成
echo "等待应用部署完成..."
kubectl wait --for=condition=available deployment/backend -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=available deployment/frontend -n $NAMESPACE --timeout=300s

echo "部署完成！"
echo "应用地址: https://llm-graph-builder.example.com"

# 显示状态
kubectl get pods -n $NAMESPACE
```

### 3. 监控和日志

**Prometheus监控配置**:
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: backend-monitor
  namespace: llm-graph-builder
spec:
  selector:
    matchLabels:
      app: backend
  endpoints:
  - port: metrics
    path: /metrics
    interval: 30s
```

**日志收集配置**:
```yaml
apiVersion: logging.coreos.com/v1
kind: ClusterLogForwarder
metadata:
  name: llm-graph-builder-logs
spec:
  inputs:
  - name: backend-logs
    application:
      namespaces:
      - llm-graph-builder
      selector:
        matchLabels:
          app: backend
  outputs:
  - name: elasticsearch
    type: elasticsearch
    url: https://elasticsearch.example.com
  pipelines:
  - name: backend-pipeline
    inputRefs:
    - backend-logs
    outputRefs:
    - elasticsearch
```

## 性能调优

### 1. Neo4j优化

```conf
# neo4j.conf
server.memory.heap.initial_size=4G
server.memory.heap.max_size=8G
server.memory.pagecache.size=2G

# 并发配置
server.bolt.thread_pool_min_size=5
server.bolt.thread_pool_max_size=400

# 查询优化
cypher.runtime=slotted
cypher.forbid_exhaustive_shortestpath=true
cypher.forbid_shortestpath_common_nodes=true

# 事务配置
db.transaction.timeout=60s
db.transaction.concurrent.maximum=1000
```

### 2. 应用性能优化

```python
# 异步处理配置
CELERY_CONFIG = {
    'broker_url': 'redis://redis:6379/0',
    'result_backend': 'redis://redis:6379/0',
    'task_routes': {
        'app.tasks.process_document': {'queue': 'processing'},
        'app.tasks.generate_embeddings': {'queue': 'embeddings'},
    },
    'worker_prefetch_multiplier': 1,
    'task_acks_late': True,
}

# 连接池配置
NEO4J_CONFIG = {
    'max_connection_pool_size': 50,
    'connection_timeout': 30,
    'max_retry_time': 15,
    'keep_alive': True,
}

# 缓存配置
REDIS_CONFIG = {
    'max_connections': 50,
    'retry_on_timeout': True,
    'socket_keepalive': True,
    'socket_keepalive_options': {},
}
```

### 3. 容器资源优化

```yaml
# 生产环境资源配置
resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"
  limits:
    memory: "4Gi"
    cpu: "2000m"

# HPA自动伸缩
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## 故障排查

### 常见问题及解决方案

1. **Neo4j连接失败**
```bash
# 检查服务状态
kubectl logs -f deployment/neo4j -n llm-graph-builder

# 验证连接
kubectl exec -it neo4j-0 -n llm-graph-builder -- cypher-shell -u neo4j -p password
```

2. **内存不足错误**
```bash
# 增加内存限制
kubectl patch deployment backend -n llm-graph-builder -p '{"spec":{"template":{"spec":{"containers":[{"name":"backend","resources":{"limits":{"memory":"4Gi"}}}]}}}}'
```

3. **文件上传失败**
```bash
# 检查存储挂载
kubectl describe pvc upload-pvc -n llm-graph-builder

# 检查权限
kubectl exec -it backend-xxx -n llm-graph-builder -- ls -la /app/uploads
```

这个部署指南提供了从本地开发到生产环境的完整部署方案，确保LLM图构建器能够在不同环境中稳定运行。 