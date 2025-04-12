from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import agents, auth, chat
from app.database import engine, Base

# 创建所有表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="知识库Agent API",
    description="基于LangGraph的知识库Agent系统API",
    version="0.1.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

@app.get("/")
async def root():
    return {"message": "欢迎使用知识库Agent API"} 