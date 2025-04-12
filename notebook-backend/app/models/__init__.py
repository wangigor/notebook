# 数据模型初始化文件 
# 导入所有模型以便Alembic能够发现它们
# 注意：导入顺序很重要，避免循环依赖问题
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.models.memory import Message, ConversationHistory, EmbeddingConfig, VectorStoreConfig, MemoryConfig 