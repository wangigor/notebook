import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import logging
import secrets

# 加载.env文件
load_dotenv()

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # 应用基本配置
    PROJECT_NAME: str = "Notebook AI Backend"
    VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000/api")

    # 数据库配置
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/notebook_ai")

    # 认证配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a_very_secret_key_that_should_be_changed") # 生产环境务必修改
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # 内部API配置
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", secrets.token_urlsafe(32)) # 默认生成随机密钥

    # 跨域配置
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",") # 生产环境应指定明确的来源
    
    # WebSocket配置
    WS_MAX_CONNECTIONS_PER_TASK: int = int(os.getenv("WS_MAX_CONNECTIONS_PER_TASK", "5"))
    WS_PING_INTERVAL: float = float(os.getenv("WS_PING_INTERVAL", "30.0"))  # WebSocket心跳间隔（秒）
    WS_PING_TIMEOUT: float = float(os.getenv("WS_PING_TIMEOUT", "10.0"))    # WebSocket心跳超时（秒）

    # Qdrant 配置 (从环境变量或默认值获取)
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "documents")
    QDRANT_TIMEOUT: float = float(os.getenv("QDRANT_TIMEOUT", "30.0"))
    QDRANT_CHECK_VERSION: bool = os.getenv("QDRANT_CHECK_VERSION", "False").lower() in ("true", "1", "t")
    
    # 向量嵌入配置
    VECTOR_SIZE: int = 1536

    # DashScope 配置
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_EMBEDDING_MODEL: str = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v1")

    # Neo4j 配置
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")
    
    # 图谱构建配置
    GRAPH_NODE_LABELS: list[str] = os.getenv("GRAPH_NODE_LABELS", "Entity,Concept,Person,Organization").split(",")
    GRAPH_RELATIONSHIP_TYPES: list[str] = os.getenv("GRAPH_RELATIONSHIP_TYPES", "RELATES_TO,CONTAINS,MENTIONS").split(",")
    GRAPH_BATCH_SIZE: int = int(os.getenv("GRAPH_BATCH_SIZE", "100"))
    
    # 知识抽取配置
    KNOWLEDGE_EXTRACTION_BATCH_SIZE: int = int(os.getenv("KNOWLEDGE_EXTRACTION_BATCH_SIZE", "10"))
    KNOWLEDGE_EXTRACTION_MIN_CONFIDENCE: float = float(os.getenv("KNOWLEDGE_EXTRACTION_MIN_CONFIDENCE", "0.5"))
    KNOWLEDGE_EXTRACTION_MAX_RETRIES: int = int(os.getenv("KNOWLEDGE_EXTRACTION_MAX_RETRIES", "3"))
    KNOWLEDGE_EXTRACTION_DELAY_SECONDS: float = float(os.getenv("KNOWLEDGE_EXTRACTION_DELAY_SECONDS", "0.1"))
    
    # 实体抽取配置
    ENTITY_TYPES: list[str] = os.getenv("ENTITY_TYPES", "人物,组织,地点,事件,概念,技术,产品,时间,数字,法律条文,政策,项目,系统,方法,理论").split(",")
    ENTITY_MIN_LENGTH: int = int(os.getenv("ENTITY_MIN_LENGTH", "2"))
    ENTITY_MAX_LENGTH: int = int(os.getenv("ENTITY_MAX_LENGTH", "100"))
    
    # 关系抽取配置  
    RELATIONSHIP_TYPES: list[str] = os.getenv("RELATIONSHIP_TYPES", "属于,包含,位于,工作于,创立,管理,合作,提及,描述,引用,导致,影响,使用,依赖,实现,相关,连接,关联").split(",")
    RELATIONSHIP_MIN_CONFIDENCE: float = float(os.getenv("RELATIONSHIP_MIN_CONFIDENCE", "0.5"))

    # 社区检测配置
    COMMUNITY_MAX_LEVELS: int = int(os.getenv("COMMUNITY_MAX_LEVELS", "3"))
    COMMUNITY_MIN_SIZE: int = int(os.getenv("COMMUNITY_MIN_SIZE", "1"))
    COMMUNITY_MAX_WORKERS: int = int(os.getenv("COMMUNITY_MAX_WORKERS", "10"))
    COMMUNITY_LLM_MODEL: str = os.getenv("COMMUNITY_LLM_MODEL", "gpt-4o")
    COMMUNITY_EMBEDDING_MODEL: str = os.getenv("COMMUNITY_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    COMMUNITY_BATCH_SIZE: int = int(os.getenv("COMMUNITY_BATCH_SIZE", "100"))
    COMMUNITY_TIMEOUT_MINUTES: int = int(os.getenv("COMMUNITY_TIMEOUT_MINUTES", "30"))

    # MinIO 配置
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minio")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioxxx")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "False").lower() in ("true", "1", "t")
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "notebook-ai")
    DOCUMENT_BUCKET: str = os.getenv("DOCUMENT_BUCKET", os.getenv("MINIO_BUCKET_NAME", "notebook-ai"))

    # Agent 配置
    AGENT_MAX_TOKEN_LIMIT: int = int(os.getenv("AGENT_MAX_TOKEN_LIMIT", "2000"))
    AGENT_RETURN_MESSAGES: bool = os.getenv("AGENT_RETURN_MESSAGES", "True").lower() in ("true", "1", "t")
    AGENT_RETURN_SOURCE_DOCUMENTS: bool = os.getenv("AGENT_RETURN_SOURCE_DOCUMENTS", "True").lower() in ("true", "1", "t")
    AGENT_K: int = int(os.getenv("AGENT_K", "5")) # 相似文档数量
    
    # OpenAI 配置
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_API_BASE: str | None = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    
    # Redis 和 Celery 配置
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str | None = os.getenv("REDIS_PASSWORD")
    CELERY_BROKER_URL: str = f"redis://{':' + REDIS_PASSWORD + '@' if REDIS_PASSWORD else ''}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    CELERY_RESULT_BACKEND: str = CELERY_BROKER_URL
    
    # 服务器配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    model_config = {
        "case_sensitive": True,
        "env_file": ".env", 
        "env_file_encoding": "utf-8",
        "extra": "ignore"  # 允许额外字段
    }

# 创建 Settings 实例
settings = Settings()

# 打印部分配置信息以供调试 (仅在 DEBUG 模式下)
if settings.DEBUG:
    logger.info("--- 应用配置 ---")
    logger.info(f"Project Name: {settings.PROJECT_NAME}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    logger.info(f"API Base URL: {settings.API_BASE_URL}")
    logger.info(f"Database URL (masked): {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else '...'}")
    logger.info(f"CORS Origins: {settings.CORS_ORIGINS}")
    logger.info(f"WebSocket Max Connections Per Task: {settings.WS_MAX_CONNECTIONS_PER_TASK}")
    logger.info(f"Qdrant URL: {settings.QDRANT_URL}")
    logger.info(f"Qdrant Collection: {settings.QDRANT_COLLECTION_NAME}")
    logger.info(f"Vector Size: {settings.VECTOR_SIZE}")
    logger.info(f"DashScope Embedding Model: {settings.DASHSCOPE_EMBEDDING_MODEL}")
    logger.info(f"Neo4j URI: {settings.NEO4J_URI}")
    logger.info(f"Neo4j Database: {settings.NEO4J_DATABASE}")
    logger.info(f"Graph Node Labels: {settings.GRAPH_NODE_LABELS}")
    logger.info(f"MinIO Endpoint: {settings.MINIO_ENDPOINT}")
    logger.info(f"MinIO Bucket: {settings.MINIO_BUCKET_NAME}")
    logger.info(f"Document Bucket: {settings.DOCUMENT_BUCKET}")
    logger.info(f"Redis URL: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    logger.info("----------------") 