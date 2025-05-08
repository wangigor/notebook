from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import agents, auth, chat, documents, websockets, tasks
from app.database import engine, Base
from app.core.logging import setup_logging
from app.core.config import settings # 导入settings
import logging

# 设置日志系统
setup_logging()
logger = logging.getLogger(__name__)

# 创建所有表
try:
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建完成")
except Exception as e:
    logger.error(f"数据库表创建失败: {str(e)}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="基于LangGraph的知识库Agent系统API",
    version=settings.VERSION,
    debug=settings.DEBUG # 使用settings中的DEBUG配置
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(websockets.router, tags=["websockets"])

@app.get("/")
async def root():
    return {"message": f"欢迎使用 {settings.PROJECT_NAME} API"}

@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    # 可以在这里添加更详细的数据库或服务连接检查
    db_connected = True # 假设数据库连接正常
    try:
        # 尝试执行一个简单的查询
        engine.connect().close()
    except Exception as e:
        logger.error(f"健康检查：数据库连接失败 - {str(e)}")
        db_connected = False
        
    return {
        "status": "ok",
        "version": settings.VERSION,
        "database_status": "connected" if db_connected else "disconnected"
    } 