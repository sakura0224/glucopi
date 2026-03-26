# app/api/v1/endpoints/chat_api.py

from fastapi import APIRouter, Depends, Query
from app.db.mongo import get_chat_collection  # 导入提供集合的依赖函数
from app.db.mysql import get_db_http # 导入 get_db_http
from app.dependencies.auth import get_current_user # 导入认证依赖
from app.models.user import User # 导入 User 模型
from sqlalchemy.ext.asyncio import AsyncSession # 导入 AsyncSession
from motor.motor_asyncio import AsyncIOMotorCollection # 导入 AsyncIOMotorCollection
# --- 导入 chat_service 模块 ---
from app.services import chat_service # 导入 chat_service 模块
# --- 导入 Schema ---
from app.schemas.chat import ReadRequest # 导入 ReadRequest Schema
# TODO: 如果需要返回 Schema，导入 Schema，例如 ChatHistoryItemOut, ChatSummaryItemOut
# from app.schemas.chat import ChatHistoryItemOut, ChatSummaryItemOut


router = APIRouter()


# --- 获取聊天历史端点 (调用 service 层函数) ---
# @router.get("/history", summary="分页获取聊天记录", response_model=List[ChatHistoryItemOut]) # 示例 response_model
@router.get("/history", summary="分页获取聊天记录")
async def get_chat_history_endpoint(
    other_id: str = Query(..., description="聊天对象的 userId"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, gt=0),
    user: User = Depends(get_current_user()), # 获取当前用户
    chat_collection: AsyncIOMotorCollection = Depends(get_chat_collection) # 获取 MongoDB 集合依赖
):
    """
    获取当前用户与指定聊天对象的聊天历史记录。
    """
    # --- 调用 chat_service 中的历史记录函数 ---
    history = await chat_service.get_chat_history(
        user_id1=str(user.id), # 确保传递字符串 ID
        user_id2=other_id,
        chat_collection=chat_collection, # 传递 MongoDB 集合依赖
        skip=skip,
        limit=limit
    )
    # --- 调用结束 ---

    # TODO: 根据需要格式化返回数据，例如转换为 Pydantic Schema
    return {
        "code": 200, # code 字段通常不需要在 REST API 中返回，状态码即可
        "data": history # history 已经是列表，包含处理后的消息字典
    }


# --- 获取聊天摘要端点 (调用 service 层函数) ---
# @router.get("/summary", summary="获取聊天摘要", response_model=List[ChatSummaryItemOut]) # 示例 response_model
@router.get("/summary", summary="获取聊天摘要")
async def get_chat_summary_endpoint(
    user: User = Depends(get_current_user()),
    db: AsyncSession = Depends(get_db_http), # MySQL DB session 依赖
    chat_collection: AsyncIOMotorCollection = Depends(get_chat_collection) # MongoDB 集合依赖
):
    """
    获取当前用户的聊天会话摘要列表。
    """
    # --- 调用 chat_service 中的聊天摘要函数 ---
    summary = await chat_service.get_chat_summary(
        user_id=str(user.id), # 确保传递字符串 ID
        chat_collection=chat_collection, # 传递 MongoDB 集合依赖
        db=db # 传递 MySQL DB session 依赖
    )
    # --- 调用结束 ---

    # TODO: 根据需要格式化返回数据，例如转换为 Pydantic Schema
    return {
        "code": 200, # code 字段通常不需要在 REST API 中返回，状态码即可
        "data": summary # summary 已经是列表，包含处理后的摘要字典
    }


# --- 标记与某人的消息为已读端点 (调用 service 层函数) ---
@router.post("/read", summary="标记与某人的消息为已读")
async def mark_as_read_endpoint(
    data: ReadRequest, # 请求体包含 from_user
    user: User = Depends(get_current_user()),
    chat_collection: AsyncIOMotorCollection = Depends(get_chat_collection) # 获取 MongoDB 集合依赖
):
    """
    标记当前用户与指定对象之间的消息为已读。
    """
    # 假设 ReadRequest 中包含 other_user_id 或 from_user_id (消息发送者)
    # 根据 ReadRequest 的定义，它包含 from_user，这应该是消息的发送者，也就是对话的另一方 ID
    target_user_id = str(data.from_user) # 对话的另一方 ID

    # --- 调用 chat_service 中的标记已读函数 ---
    modified_count = await chat_service.mark_messages_read(
        user_id=str(user.id), # 当前用户 ID
        target_user_id=target_user_id,
        chat_collection=chat_collection # 传递 MongoDB 集合依赖
    )
    # --- 调用结束 ---

    return {"updated": modified_count}