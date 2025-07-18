import os
from typing import Dict
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import logging
import secrets
from pydantic import Field

# 加载.env文件
load_dotenv()

# 设置SSL相关环境变量（用于开发环境）
if os.getenv("PYTHONHTTPSVERIFY") == "0":
    os.environ["PYTHONHTTPSVERIFY"] = "0"
    os.environ["REQUESTS_CA_BUNDLE"] = ""
    os.environ["CURL_CA_BUNDLE"] = ""
    import ssl
    import urllib3
    # 禁用SSL警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    WS_MAX_CONNECTIONS_PER_TASK: int = Field(default=10, description="每个任务的最大WebSocket连接数")
    WS_PING_INTERVAL: float = float(os.getenv("WS_PING_INTERVAL", "30.0"))  # WebSocket心跳间隔（秒）
    WS_PING_TIMEOUT: float = float(os.getenv("WS_PING_TIMEOUT", "10.0"))    # WebSocket心跳超时（秒）

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
    
    # 🆕 实体统一智能化配置
    # 相似度阈值配置
    ENTITY_UNIFICATION_HIGH_THRESHOLD: float = float(os.getenv("ENTITY_UNIFICATION_HIGH_THRESHOLD", "0.85"))  # 高置信度自动合并
    ENTITY_UNIFICATION_MEDIUM_THRESHOLD: float = float(os.getenv("ENTITY_UNIFICATION_MEDIUM_THRESHOLD", "0.65"))  # 中等置信度冲突检测
    ENTITY_UNIFICATION_LOW_THRESHOLD: float = float(os.getenv("ENTITY_UNIFICATION_LOW_THRESHOLD", "0.50"))  # 低置信度拒绝合并
    
    # 多维度相似度权重配置
    ENTITY_SIMILARITY_SEMANTIC_WEIGHT: float = float(os.getenv("ENTITY_SIMILARITY_SEMANTIC_WEIGHT", "0.4"))  # 语义相似度权重
    ENTITY_SIMILARITY_LEXICAL_WEIGHT: float = float(os.getenv("ENTITY_SIMILARITY_LEXICAL_WEIGHT", "0.3"))   # 词汇相似度权重
    ENTITY_SIMILARITY_CONTEXTUAL_WEIGHT: float = float(os.getenv("ENTITY_SIMILARITY_CONTEXTUAL_WEIGHT", "0.3"))  # 上下文相似度权重
    
    # 批量处理配置
    ENTITY_UNIFICATION_BATCH_SIZE: int = int(os.getenv("ENTITY_UNIFICATION_BATCH_SIZE", "100"))  # 批量处理大小
    ENTITY_EMBEDDING_BATCH_SIZE: int = int(os.getenv("ENTITY_EMBEDDING_BATCH_SIZE", "50"))  # embedding批量生成大小
    ENTITY_SIMILARITY_CACHE_SIZE: int = int(os.getenv("ENTITY_SIMILARITY_CACHE_SIZE", "1000"))  # 相似度缓存大小
    
    # 性能优化配置
    ENTITY_UNIFICATION_MAX_MATRIX_SIZE: int = int(os.getenv("ENTITY_UNIFICATION_MAX_MATRIX_SIZE", "10000"))  # 最大相似度矩阵大小
    ENTITY_UNIFICATION_PARALLEL_WORKERS: int = int(os.getenv("ENTITY_UNIFICATION_PARALLEL_WORKERS", "4"))  # 并行处理工作者数
    ENTITY_UNIFICATION_MEMORY_LIMIT_MB: int = int(os.getenv("ENTITY_UNIFICATION_MEMORY_LIMIT_MB", "2048"))  # 内存使用限制(MB)
    
    # 质量控制配置
    ENTITY_ALIAS_MAX_COUNT: int = int(os.getenv("ENTITY_ALIAS_MAX_COUNT", "20"))  # 每个实体最大别名数量
    ENTITY_QUALITY_MIN_SCORE: float = float(os.getenv("ENTITY_QUALITY_MIN_SCORE", "0.3"))  # 最低质量分数阈值
    
    # 🆕 类型分组统一配置
    ENTITY_UNIFICATION_ENABLE_TYPE_GROUPING: bool = os.getenv("ENTITY_UNIFICATION_ENABLE_TYPE_GROUPING", "True").lower() in ("true", "1", "t")  # 启用类型分组
    ENTITY_UNIFICATION_MAX_ENTITIES_PER_TYPE_BATCH: int = int(os.getenv("ENTITY_UNIFICATION_MAX_ENTITIES_PER_TYPE_BATCH", "50"))  # 每种类型的最大批处理大小
    
    # 📊 智能实体统一已全面启用（移除传统去重和开关配置）
    ENTITY_UNIFICATION_DEBUG_MODE: bool = os.getenv("ENTITY_UNIFICATION_DEBUG_MODE", "False").lower() in ("true", "1", "t")  # 调试模式
    
    # 🚀 增量统一专用配置
    INCREMENTAL_UNIFICATION_ENABLED: bool = os.getenv("INCREMENTAL_UNIFICATION_ENABLED", "True").lower() in ("true", "1", "t")
    INCREMENTAL_BATCH_SIZE: int = int(os.getenv("INCREMENTAL_BATCH_SIZE", "1000"))
    INCREMENTAL_PROCESSING_TIMEOUT: int = int(os.getenv("INCREMENTAL_PROCESSING_TIMEOUT", "300"))  # 5分钟
    INCREMENTAL_QUEUE_MAX_SIZE: int = int(os.getenv("INCREMENTAL_QUEUE_MAX_SIZE", "10000"))
    
    # 🏷️ 类型感知索引配置
    TYPE_AWARE_INDEX_ENABLED: bool = os.getenv("TYPE_AWARE_INDEX_ENABLED", "True").lower() in ("true", "1", "t")
    INDEX_CACHE_SIZE: int = int(os.getenv("INDEX_CACHE_SIZE", "10000"))
    INDEX_CACHE_TTL: int = int(os.getenv("INDEX_CACHE_TTL", "3600"))  # 1小时
    FUZZY_MATCH_NGRAM_SIZE: int = int(os.getenv("FUZZY_MATCH_NGRAM_SIZE", "3"))
    
    # 🎯 智能候选生成配置
    CANDIDATE_GENERATION_MAX_CANDIDATES: int = int(os.getenv("CANDIDATE_GENERATION_MAX_CANDIDATES", "50"))
    CANDIDATE_GENERATION_MIN_SCORE: float = float(os.getenv("CANDIDATE_GENERATION_MIN_SCORE", "0.1"))
    CANDIDATE_STRATEGY_WEIGHTS: Dict[str, float] = {
        'exact_match': float(os.getenv("EXACT_MATCH_WEIGHT", "1.0")),
        'fuzzy_match': float(os.getenv("FUZZY_MATCH_WEIGHT", "0.8")),
        'semantic_match': float(os.getenv("SEMANTIC_MATCH_WEIGHT", "0.9")),
        'graph_structure': float(os.getenv("GRAPH_STRUCTURE_WEIGHT", "0.7"))
    }
    
    # 🔍 实体指纹配置
    ENTITY_FINGERPRINT_ALGORITHM: str = os.getenv("ENTITY_FINGERPRINT_ALGORITHM", "md5")  # md5, sha1, sha256, xxhash
    ENTITY_FINGERPRINT_TYPE: str = os.getenv("ENTITY_FINGERPRINT_TYPE", "extended")  # basic, extended, semantic, full
    FINGERPRINT_CACHE_SIZE: int = int(os.getenv("FINGERPRINT_CACHE_SIZE", "5000"))
    FINGERPRINT_CACHE_TTL: int = int(os.getenv("FINGERPRINT_CACHE_TTL", "7200"))  # 2小时
    
    # 🛠️ 索引管理配置
    INDEX_MANAGEMENT_ENABLED: bool = os.getenv("INDEX_MANAGEMENT_ENABLED", "True").lower() in ("true", "1", "t")
    INDEX_MAINTENANCE_INTERVAL: int = int(os.getenv("INDEX_MAINTENANCE_INTERVAL", "14400"))  # 4小时
    INDEX_PERFORMANCE_THRESHOLD: float = float(os.getenv("INDEX_PERFORMANCE_THRESHOLD", "0.8"))
    INDEX_FRAGMENTATION_THRESHOLD: float = float(os.getenv("INDEX_FRAGMENTATION_THRESHOLD", "0.3"))
    INDEX_AUTO_OPTIMIZE_ENABLED: bool = os.getenv("INDEX_AUTO_OPTIMIZE_ENABLED", "True").lower() in ("true", "1", "t")
    INDEX_MAINTENANCE_WORKERS: int = int(os.getenv("INDEX_MAINTENANCE_WORKERS", "2"))
    
    # 📊 抽样检测配置
    SAMPLING_DETECTION_ENABLED: bool = os.getenv("SAMPLING_DETECTION_ENABLED", "True").lower() in ("true", "1", "t")
    SAMPLING_INTERVAL_HOURS: int = int(os.getenv("SAMPLING_INTERVAL_HOURS", "4"))
    SAMPLING_SIZE_PER_TYPE: int = int(os.getenv("SAMPLING_SIZE_PER_TYPE", "1000"))
    SAMPLING_STRATEGIES: Dict[str, float] = {
        'random': float(os.getenv("SAMPLING_RANDOM_RATIO", "0.3")),
        'quality_based': float(os.getenv("SAMPLING_QUALITY_RATIO", "0.4")),
        'time_based': float(os.getenv("SAMPLING_TIME_RATIO", "0.2")),
        'conflict_prone': float(os.getenv("SAMPLING_CONFLICT_RATIO", "0.1"))
    }
    
    # 🚀 全局语义统一配置 (v2)
    GLOBAL_SEMANTIC_UNIFICATION_ENABLED: bool = os.getenv("GLOBAL_SEMANTIC_UNIFICATION_ENABLED", "True").lower() in ("true", "1", "t")
    GLOBAL_UNIFICATION_MAX_SAMPLE_PER_TYPE: int = int(os.getenv("GLOBAL_UNIFICATION_MAX_SAMPLE_PER_TYPE", "50"))
    GLOBAL_UNIFICATION_MIN_ENTITIES: int = int(os.getenv("GLOBAL_UNIFICATION_MIN_ENTITIES", "2"))
    GLOBAL_UNIFICATION_LLM_CONFIDENCE_THRESHOLD: float = float(os.getenv("GLOBAL_UNIFICATION_LLM_CONFIDENCE_THRESHOLD", "0.7"))
    GLOBAL_UNIFICATION_MAX_BATCH_SIZE: int = int(os.getenv("GLOBAL_UNIFICATION_MAX_BATCH_SIZE", "20"))
    GLOBAL_UNIFICATION_ENABLE_QUALITY_BOOST: bool = os.getenv("GLOBAL_UNIFICATION_ENABLE_QUALITY_BOOST", "True").lower() in ("true", "1", "t")
    GLOBAL_UNIFICATION_ENABLE_CROSS_DOCUMENT: bool = os.getenv("GLOBAL_UNIFICATION_ENABLE_CROSS_DOCUMENT", "True").lower() in ("true", "1", "t")
    
    # 🤖 LLM语义去重配置
    LLM_DEDUPLICATION_MAX_RETRY: int = int(os.getenv("LLM_DEDUPLICATION_MAX_RETRY", "3"))
    LLM_DEDUPLICATION_TIMEOUT: int = int(os.getenv("LLM_DEDUPLICATION_TIMEOUT", "120"))  # 2分钟
    LLM_DEDUPLICATION_TEMPERATURE: float = float(os.getenv("LLM_DEDUPLICATION_TEMPERATURE", "0.1"))
    LLM_DEDUPLICATION_MAX_TOKENS: int = int(os.getenv("LLM_DEDUPLICATION_MAX_TOKENS", "4000"))
    
    # 🗄️ Neo4j采样配置
    NEO4J_SAMPLING_CONNECTION_POOL_SIZE: int = int(os.getenv("NEO4J_SAMPLING_CONNECTION_POOL_SIZE", "5"))
    NEO4J_SAMPLING_TIMEOUT: int = int(os.getenv("NEO4J_SAMPLING_TIMEOUT", "30"))
    NEO4J_SAMPLING_CACHE_SIZE: int = int(os.getenv("NEO4J_SAMPLING_CACHE_SIZE", "1000"))
    NEO4J_SAMPLING_CACHE_TTL: int = int(os.getenv("NEO4J_SAMPLING_CACHE_TTL", "1800"))  # 30分钟
    
    # 📋 图谱后处理配置
    POST_GRAPH_UNIFICATION_MODE: str = os.getenv("POST_GRAPH_UNIFICATION_MODE", "global_semantic")  # sampling, incremental, global_semantic
    
    # 🔄 实体生命周期配置
    ENTITY_LIFECYCLE_NEW_THRESHOLD_HOURS: int = int(os.getenv("ENTITY_LIFECYCLE_NEW_THRESHOLD_HOURS", "24"))
    ENTITY_LIFECYCLE_DEPRECATED_THRESHOLD_DAYS: int = int(os.getenv("ENTITY_LIFECYCLE_DEPRECATED_THRESHOLD_DAYS", "90"))
    ENTITY_LIFECYCLE_SUSPICIOUS_QUALITY_THRESHOLD: float = float(os.getenv("ENTITY_LIFECYCLE_SUSPICIOUS_QUALITY_THRESHOLD", "0.6"))
    
    # 📈 性能监控配置
    PERFORMANCE_MONITORING_ENABLED: bool = os.getenv("PERFORMANCE_MONITORING_ENABLED", "True").lower() in ("true", "1", "t")
    PERFORMANCE_HISTORY_RETENTION_DAYS: int = int(os.getenv("PERFORMANCE_HISTORY_RETENTION_DAYS", "7"))
    PERFORMANCE_METRICS_COLLECTION_INTERVAL: int = int(os.getenv("PERFORMANCE_METRICS_COLLECTION_INTERVAL", "300"))  # 5分钟
    
    # 🎛️ 调试和日志配置
    INCREMENTAL_UNIFICATION_VERBOSE_LOGGING: bool = os.getenv("INCREMENTAL_UNIFICATION_VERBOSE_LOGGING", "False").lower() in ("true", "1", "t")
    INDEX_PERFORMANCE_LOGGING: bool = os.getenv("INDEX_PERFORMANCE_LOGGING", "False").lower() in ("true", "1", "t")
    CANDIDATE_GENERATION_LOGGING: bool = os.getenv("CANDIDATE_GENERATION_LOGGING", "False").lower() in ("true", "1", "t")
    
    # 🚦 限流和保护配置
    ENTITY_PROCESSING_RATE_LIMIT: int = int(os.getenv("ENTITY_PROCESSING_RATE_LIMIT", "1000"))  # 每秒处理实体数
    MEMORY_USAGE_THRESHOLD_MB: int = int(os.getenv("MEMORY_USAGE_THRESHOLD_MB", "4096"))  # 4GB
    INDEX_SIZE_LIMIT_MB: int = int(os.getenv("INDEX_SIZE_LIMIT_MB", "1024"))  # 1GB

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

    # 搜索调试和性能监控配置
    SEARCH_DEBUG_MODE: bool = Field(default=False, description="搜索调试模式开关")
    SEARCH_LOG_LEVEL: str = Field(default="INFO", description="搜索日志级别")
    SEARCH_PERFORMANCE_LOG: bool = Field(default=True, description="启用搜索性能日志")
    SEARCH_NODE_DETAIL_LOG: bool = Field(default=False, description="启用节点详细日志")
    
    # 搜索性能阈值设置
    SEARCH_SLOW_QUERY_THRESHOLD: float = Field(default=2.0, description="慢查询阈值(秒)")
    SEARCH_MEMORY_WARNING_THRESHOLD: float = Field(default=100.0, description="内存使用警告阈值(MB)")
    SEARCH_RESULT_QUALITY_THRESHOLD: float = Field(default=0.7, description="搜索结果质量阈值")
    
    # 搜索指标收集配置
    SEARCH_METRICS_ENABLED: bool = Field(default=True, description="启用搜索指标收集")
    SEARCH_METRICS_HISTORY_SIZE: int = Field(default=100, description="搜索指标历史记录大小")
    SEARCH_METRICS_REPORT_INTERVAL: int = Field(default=10, description="搜索指标报告间隔(次数)")

    # 🆕 文档解析后实体统一配置
    ENABLE_POST_EXTRACTION_UNIFICATION: bool = True
    ENABLE_POST_GRAPH_UNIFICATION: bool = True
    DEFAULT_UNIFICATION_MODE: str = "incremental"  # 'incremental' 或 'sampling'
    POST_GRAPH_UNIFICATION_MODE: str = "sampling"  # 图谱构建后使用抽样模式

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