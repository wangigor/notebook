from typing import Optional, Union
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request, WebSocket
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.models.user import User, TokenData
from app.database import get_db
from app.core.config import settings
import os
import logging

logger = logging.getLogger(__name__)

# 配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"

# 支持多种认证方式的依赖项函数
async def get_token_from_request(request: Request) -> Optional[str]:
    """从请求中获取令牌，支持多种方式：
    1. 标准Authorization头部
    2. URL查询参数
    3. Cookie
    """
    # 1. 尝试从Authorization头部获取
    authorization = request.headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ")[1]
    
    # 2. 尝试从URL查询参数获取
    token = request.query_params.get("token")
    if token:
        return token
    
    # 3. 尝试从Cookie获取
    token = request.cookies.get("token")
    if token:
        return token
        
    return None

# 从WebSocket查询参数中获取token
async def get_token_from_query(token: str) -> Optional[str]:
    """从WebSocket查询参数中获取token
    
    参数:
        token: 从查询参数中传递的token
        
    返回:
        验证过的token或None
    """
    if not token:
        return None
    return token

# 验证token并返回用户对象
async def get_user_from_token(token: str, db: Session) -> Optional[User]:
    """验证token并返回用户对象
    
    参数:
        token: JWT token
        db: 数据库会话
        
    返回:
        验证成功返回User对象，否则返回None
    """
    if not token:
        logger.warning("认证请求没有提供令牌")
        return None
        
    try:
        # 解码JWT令牌
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning("令牌中缺少用户ID")
            return None
    except JWTError as e:
        logger.warning(f"令牌解码失败: {str(e)}")
        return None
    
    # 从数据库中获取用户信息
    try:
        # 尝试将user_id转换为整数（如果是数字ID的情况）
        id_value = int(user_id)
        user = db.query(User).filter(User.id == id_value).first()
    except ValueError:
        # 如果转换失败，假设user_id是用户名
        logger.info(f"使用用户名 '{user_id}' 查询用户")
        user = db.query(User).filter(User.username == user_id).first()
    
    if user is None:
        logger.warning(f"找不到用户: {user_id}")
        return None
        
    logger.info(f"WebSocket用户认证成功: {user.username} (ID: {user.id})")
    return user

# 灵活的OAuth2方案，支持从多个位置获取令牌
class FlexibleOAuth2(OAuth2PasswordBearer):
    def __init__(self, tokenUrl: str):
        super().__init__(tokenUrl=tokenUrl, auto_error=False)
    
    async def __call__(self, request: Request) -> Optional[str]:
        token = await get_token_from_request(request)
        if not token:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未提供有效的认证凭据",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None
        return token

# 初始化灵活的OAuth2方案
oauth2_scheme = FlexibleOAuth2(tokenUrl="/api/auth/token")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证凭据无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        logger.warning("认证请求没有提供令牌")
        raise credentials_exception
        
    try:
        # 解码JWT令牌
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning("令牌中缺少用户ID")
            raise credentials_exception
    except JWTError as e:
        logger.warning(f"令牌解码失败: {str(e)}")
        raise credentials_exception
    
    # 从数据库中获取用户信息
    # 检查user_id是整数ID还是用户名
    try:
        # 尝试将user_id转换为整数（如果是数字ID的情况）
        id_value = int(user_id)
        user = db.query(User).filter(User.id == id_value).first()
    except ValueError:
        # 如果转换失败，假设user_id是用户名
        logger.info(f"使用用户名 '{user_id}' 查询用户")
        user = db.query(User).filter(User.username == user_id).first()
    
    if user is None:
        logger.warning(f"找不到用户: {user_id}")
        raise credentials_exception
        
    logger.info(f"用户认证成功: {user.username} (ID: {user.id})")
    return user