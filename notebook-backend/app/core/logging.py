import logging
import sys
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    """设置日志配置"""
    
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    
    # 文件处理器
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    
    # 专门的搜索性能日志处理器
    search_perf_handler = RotatingFileHandler(
        os.path.join(log_dir, "search_performance.log"),
        maxBytes=20*1024*1024,  # 20MB
        backupCount=10
    )
    search_perf_handler.setLevel(logging.DEBUG)
    search_perf_format = logging.Formatter(
        '%(asctime)s - [SEARCH_PERF] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    search_perf_handler.setFormatter(search_perf_format)
    
    # 搜索数据日志处理器
    search_data_handler = RotatingFileHandler(
        os.path.join(log_dir, "search_data.log"),
        maxBytes=50*1024*1024,  # 50MB
        backupCount=5
    )
    search_data_handler.setLevel(logging.DEBUG)
    search_data_format = logging.Formatter(
        '%(asctime)s - [SEARCH_DATA] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    search_data_handler.setFormatter(search_data_format)
    
    # 节点级别日志处理器
    search_node_handler = RotatingFileHandler(
        os.path.join(log_dir, "search_nodes.log"),
        maxBytes=30*1024*1024,  # 30MB
        backupCount=3
    )
    search_node_handler.setLevel(logging.DEBUG)
    search_node_format = logging.Formatter(
        '%(asctime)s - [SEARCH_NODE] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    search_node_handler.setFormatter(search_node_format)
    
    # 添加处理器
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # 为搜索相关模块设置专门的日志处理器
    search_modules = [
        "app.services.neo4j_graph_service",
        "app.services.memory_service", 
        "app.agents.knowledge_agent",
        "app.utils.search_metrics"
    ]
    
    for module_name in search_modules:
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(logging.DEBUG)
        
        # 添加专门的搜索日志处理器（避免重复日志）
        if not any(isinstance(h, RotatingFileHandler) and "search_performance" in h.baseFilename for h in module_logger.handlers):
            module_logger.addHandler(search_perf_handler)
            module_logger.addHandler(search_data_handler)
            module_logger.addHandler(search_node_handler)
    
    # 专门为vector_store模块设置更详细的日志
    vector_logger = logging.getLogger("app.services.vector_store")
    vector_logger.setLevel(logging.DEBUG)
    
    # 其他第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    
    logging.info("日志系统初始化完成") 
    logging.info(f"搜索性能日志文件: {os.path.join(log_dir, 'search_performance.log')}")
    logging.info(f"搜索数据日志文件: {os.path.join(log_dir, 'search_data.log')}")
    logging.info(f"搜索节点日志文件: {os.path.join(log_dir, 'search_nodes.log')}") 