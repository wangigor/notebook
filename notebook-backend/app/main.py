from fastapi import FastAPI, WebSocket, Depends, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from app.routers import agents, auth, chat, documents, websockets, tasks
from app.database import engine, Base, get_db
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

# 注册标准API路由
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])

# 注册WebSocket路由 - 保持原始路径，不添加任何前缀
# 这样WebSocket客户端可以通过ws://host/ws连接
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db = Depends(get_db)):
    await websockets.websocket_task_endpoint(websocket, db)

# 注册内部API端点 - 使用/api前缀
@app.post("/api/internal/ws/send/{task_id}", status_code=200, tags=["internal"])
async def internal_send_ws(task_id: str, data: dict = Body(...), request: Request = None):
    return await websockets.send_task_update_to_ws(task_id, data, request)

@app.post("/api/internal/task_update/{task_id}", status_code=200, tags=["internal"])
async def internal_task_update(task_id: str, task_service = Depends(websockets.get_task_service_dep), request: Request = None):
    return await websockets.push_task_update_to_websocket(task_id, task_service, request)

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