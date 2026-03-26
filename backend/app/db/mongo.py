# app/db/mongo.py

# 导入 AsyncIOMotorCollection 类型
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from app.core.config import settings
from fastapi import Depends

# 创建异步 MongoDB 客户端 (全局对象)
mongo_client = AsyncIOMotorClient(settings.MONGO_URI)

# 数据库 (全局对象)
mongo_db: AsyncIOMotorDatabase = mongo_client["glucopi"]

# 聊天消息集合 (全局对象，但推荐通过依赖注入获取)
chat_collection: AsyncIOMotorCollection = mongo_db["chat_messages"]


# --- 新增：提供 MongoDB 数据库对象的依赖函数 ---
async def get_mongo_db() -> AsyncIOMotorDatabase:
    """
    FastAPI 依赖项，提供异步 MongoDB 数据库对象。
    """
    return mongo_db  # 返回全局的数据库对象


# --- 新增：提供 MongoDB 聊天集合对象的依赖函数 ---
async def get_chat_collection() -> AsyncIOMotorCollection:
    """
    FastAPI 依赖项，提供异步 MongoDB 聊天消息集合对象。
    """
    # 可以在这里直接返回全局集合对象
    return chat_collection


# 导出依赖函数和全局对象 (根据需要在其他地方导入)
__all__ = ["mongo_client", "mongo_db", "chat_collection",
           "get_mongo_db", "get_chat_collection"]
