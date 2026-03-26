# app/services/chat_service.py

import asyncio
import time  # 导入 time 模块用于计算用时
import logging  # 导入 logging 模块用于日志记录
from bson import ObjectId  # 导入 ObjectId 处理 MongoDB _id
# 移除这里的导入，active_connections 将作为参数传递
# from app.api.v1.websocket.ws import active_connections
from app.models.user import User
from sqlalchemy import or_
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorCollection
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.utils.time import now_utc, to_iso_utc
# 只导入 LLMConversation 类，get_llm_response 将被移除
from app.services.llm_service import LLMConversation
from fastapi import HTTPException, WebSocket, status

# 配置 logger
logger = logging.getLogger(__name__)

# 在 chat_service 模块内部管理 LLM 会话实例，每个用户一个会话历史
_llm_conversations: Dict[str, LLMConversation] = {}


# 获取或创建指定用户的 LLM 会话实例
def _get_llm_conversation(user_id: str) -> LLMConversation:
    """为给定用户获取或创建一个 LLMConversation 实例"""
    key = str(user_id)  # 确保使用字符串 ID 作为字典键
    if key not in _llm_conversations:
        # 实例化 LLMConversation 时传递必要的配置和 API key
        _llm_conversations[key] = LLMConversation(
            initial_system_message=settings.SYSTEM_PROMPT,
            api_key=settings.DEEPSEEK_API_KEY,
            model=settings.LLM_MODEL_NAME
        )
    return _llm_conversations[key]


# 保存消息到 MongoDB，支持状态和用时
async def save_message(
    from_user_id: str,
    to_user_id: str,
    content: str,
    chat_collection: AsyncIOMotorCollection,
    timestamp: Optional[int] = None,
    is_llm: bool = False,
    read: bool = False,
    status: Optional[str] = None,  # 消息状态
    duration: Optional[int] = None,  # LLM 响应时间 (秒)
    _id: Optional[str] = None  # 可选，指定消息的 _id (用于流式完成)
):
    """保存消息到数据库"""
    # 确保用户 ID 为字符串并排序，生成 chat_id
    chat_id = "__".join(sorted([str(from_user_id), str(to_user_id)]))
    # 根据时间戳或当前时间确定消息时间
    ts = datetime.fromtimestamp(
        timestamp / 1000, tz=timezone.utc) if timestamp is not None else now_utc()

    message = {
        "chatId": chat_id,
        "from": str(from_user_id),  # 确保存储为字符串
        "to": str(to_user_id),     # 确保存储为字符串
        "content": content,
        "type": "text",  # 消息类型，如 text, markdown, etc.
        "isLLM": is_llm,  # LLM 消息标记
        "time": ts,
        "read": read,  # 已读标记
        "status": status,  # 消息状态
        "duration": duration  # LLM 消息用时
    }

    if _id:
        # 如果指定了 _id，使用它进行插入 (主要用于流式消息的最终保存)
        message['_id'] = ObjectId(_id)
        # 注意：这里默认是 insert_one，如果前端先保存了占位符，这里可能需要 update_one
        # 当前实现是前端不保存数据库占位符，后端在流式开始时发送 ID，结束后保存带有该 ID 的完整文档
        result = await chat_collection.insert_one(message)
    else:
        # 否则，由 MongoDB 生成 _id
        result = await chat_collection.insert_one(message)
        message["_id"] = str(result.inserted_id)  # 添加生成的 ID 并转为字符串

    # 将 time 字段格式化为 ISO 字符串返回
    if isinstance(message.get("time"), datetime):
        message["time"] = to_iso_utc(message["time"])

    return message


# 获取两个用户之间的聊天历史记录
async def get_chat_history(
    user_id1: str,
    user_id2: str,
    chat_collection: AsyncIOMotorCollection,
    limit: int = 20,
    skip: int = 0
) -> List[Dict[str, Any]]:
    """获取两个用户之间的聊天历史记录"""
    # 确保用户 ID 为字符串并排序，生成 chat_id
    uid1, uid2 = sorted([str(user_id1), str(user_id2)])
    chat_id = f"{uid1}__{uid2}"

    # 查找 chat_id 匹配的消息，按时间倒序排列，跳过/限制数量
    cursor = chat_collection.find({"chatId": chat_id}).sort(
        "time", -1).skip(skip).limit(limit)
    # to_list(length=limit) 异步获取结果
    messages = await cursor.to_list(length=limit)

    result = []
    for msg in messages[::-1]:  # 反转列表，让消息按时间正序
        msg["_id"] = str(msg["_id"])  # 确保 _id 为字符串
        if msg.get("time") and isinstance(msg.get("time"), datetime):
            msg["time"] = to_iso_utc(msg["time"])  # 格式化时间
        # 确保必要的字段存在，提供默认值
        if "isLLM" not in msg:
            msg["isLLM"] = False
        # 历史消息默认状态为 finished
        if "status" not in msg:
            msg["status"] = "finished"
        if "duration" not in msg:
            msg["duration"] = None

        result.append(msg)

    return result


# 标记消息已读
async def mark_messages_read(
    user_id: str,
    target_user_id: str,
    chat_collection: AsyncIOMotorCollection
):
    """标记与特定用户对话中发给当前用户的消息为已读"""
    # 确保用户 ID 为字符串并排序，生成 chat_id
    uid1, uid2 = sorted([str(user_id), str(target_user_id)])
    chat_id = f"{uid1}__{uid2}"

    # 将发给 user_id 且来自 target_user_id 的未读消息标记为已读
    result = await chat_collection.update_many(
        {"chatId": chat_id, "from": str(target_user_id), "to": str(
            user_id), "read": False},  # 确保查询条件中的 ID 是字符串
        {"$set": {"read": True}}
    )
    return result.modified_count  # 返回修改的文档数量


# 获取聊天摘要列表
async def get_chat_summary(
    user_id: str,
    chat_collection: AsyncIOMotorCollection,
    db: AsyncSession
):
    """获取用户所有会话的最新消息和未读计数"""
    # 确保用户 ID 为字符串
    user_id_str = str(user_id)

    pipeline = [
        {
            "$match": {
                "$or": [
                    {"to": user_id_str},  # 消息发给当前用户
                    {"from": user_id_str}  # 消息来自当前用户
                ]
            }
        },
        {"$sort": {"time": -1}},  # 按时间倒序排序，以便分组时 $first 获取最新消息
        {
            "$group": {
                "_id": "$chatId",  # 按 chatId 分组
                "lastMessageContent": {"$first": "$content"},
                "lastMessageTime": {"$first": "$time"},
                "lastMessageFrom": {"$first": "$from"},
                "lastMessageTo": {"$first": "$to"},
                # 计算未读数：发给当前用户且未读的消息数量
                "unreadCount": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$eq": ["$to", user_id_str]},
                                    {"$eq": ["$read", False]}
                                ]
                            },
                            1,
                            0
                        ]
                    }
                }
            }
        },
        {
            "$project": {  # 投影出需要的字段，计算对话对方的 ID
                "_id": 0,  # 移除 _id
                "chatId": "$_id",  # 将 _id (chatId) 重新命名为 chatId
                "lastMessageContent": 1,
                "lastMessageTime": 1,
                "unreadCount": 1,
                "otherUserId": {  # 计算对话的另一个参与者 ID
                    "$cond": [
                        # 如果最后一条消息是当前用户发的
                        {"$eq": ["$lastMessageFrom", user_id_str]},
                        "$lastMessageTo",  # 那么对方就是接收者
                        "$lastMessageFrom"  # 否则对方就是发送者
                    ]
                }
            }
        },
        # 可选：如果需要按最近活跃时间排序，再加一个排序阶段
        # {"$sort": {"lastMessageTime": -1}}
    ]

    cursor = chat_collection.aggregate(pipeline)
    summary_data = await cursor.to_list(length=None)

    # 获取所有对话对方的用户信息
    other_user_ids = [item["otherUserId"] for item in summary_data]

    # 从 MySQL users 表获取用户信息
    user_dict = {}
    if other_user_ids:
        # 过滤掉 LLM 虚拟用户 ID 和其他非数字 ID，只查询 MySQL 中存在的用户
        valid_mysql_user_ids = [int(uid) for uid in other_user_ids if isinstance(
            uid, (int, str)) and str(uid).isdigit()]
        if valid_mysql_user_ids:
            # 使用 MySQL 异步会话进行查询
            stmt = select(User).where(User.id.in_(valid_mysql_user_ids))
            users_result = await db.execute(stmt)
            # 将查询结果转换为字典，方便通过 ID 查找用户，确保键是字符串
            user_dict = {
                str(user.id): user for user in users_result.scalars().all()}

    # 拼接最终结果
    result = []
    llm_virtual_user_id_str = str(settings.LLM_VIRTUAL_USER_ID)
    llm_avatar_url_str = str(
        settings.LLM_AVATAR_URL) if settings.LLM_AVATAR_URL else "https://cdn.ayane.top/deepseek.png"  # LLM 默认头像

    for item in summary_data:
        uid = item["otherUserId"]
        u = user_dict.get(uid)  # 从字典中获取用户信息
        is_llm_user = str(uid) == llm_virtual_user_id_str

        result.append({
            "userId": uid,
            # 如果用户不存在 (例如，LLM 用户)，使用默认名或 LLM 名
            "name": u.nickname if u else ("DeepSeek" if is_llm_user else f"用户{uid}"),
            # 使用用户头像或 LLM 头像或默认头像
            "avatar": u.avatar_url if u else (llm_avatar_url_str if is_llm_user else "https://cdn.ayane.top/deepseek.png"),
            "lastMessage": item["lastMessageContent"],
            "time": to_iso_utc(item["lastMessageTime"]),  # 确保 time 格式化
            "unread": item["unreadCount"]
        })

    return result


# 处理用户发送的普通消息或 LLM 消息
async def handle_user_message(
    from_user_id: str,
    to_user_id: str,
    content: str,
    chat_collection: AsyncIOMotorCollection,
    websocket: WebSocket,  # 传递 websocket 对象用于流式推送
    active_connections: Dict[str, WebSocket],  # 传递活跃连接字典用于消息转发
    timestamp: Optional[int] = None,
    stream: bool = False,  # 控制是否进行流式回复
):
    """
    处理用户发送的消息：保存、转发，如果是发给 LLM 则生成回复。
    支持 LLM 流式或非流式回复。
    """
    # 确保用户 ID 为字符串以便比较
    from_user_id = str(from_user_id)
    to_user_id = str(to_user_id)
    llm_virtual_user_id = str(settings.LLM_VIRTUAL_USER_ID)

    # 1. 保存用户发送的消息到数据库
    user_doc = await save_message(
        from_user_id, to_user_id, content,
        chat_collection, timestamp, is_llm=False, status="finished"  # 用户消息发送后状态为 finished
    )

    # 2. 构造用户消息的 WebSocket payload
    user_payload = {
        "type": "message",  # 用户消息类型
        "data": {
            "message": user_doc  # 完整的用户消息文档
        }
    }

    # 3. 转发或回显用户消息
    recipients = [from_user_id]  # 默认回显给自己
    if to_user_id != llm_virtual_user_id:
        # 如果是发给其他用户 (医生)，则转发给对方
        recipients.append(to_user_id)

    # 使用 forward_message 发送消息
    await forward_message(
        user_payload,
        recipients=recipients,
        active_connections=active_connections  # 传递活跃连接字典
    )

    # 4. 如果消息是发给 LLM，处理 LLM 回复
    if to_user_id == llm_virtual_user_id:
        try:
            # 获取用户的 LLM 会话实例
            conv = _get_llm_conversation(from_user_id)

            # 为 LLM 回复生成一个唯一的消息 ID (在开始流式之前)
            llm_msg_id = str(ObjectId())

            # 记录 LLM 开始处理的时间
            start_time = time.monotonic()
            full_reply_content = ""  # 用于存储完整回复内容
            llm_msg_status = "finished"  # LLM 回复的最终状态，默认为 finished

            if stream:
                # --- LLM 流式回复逻辑 ---
                # 1. 发送流式开始消息给用户
                start_message = {
                    "_id": llm_msg_id,
                    "chatId": "__".join(sorted([from_user_id, to_user_id])),
                    "from": to_user_id,  # LLM 是发送者
                    "to": from_user_id,  # 用户是接收者
                    "content": "",  # 初始内容为空
                    "type": "text",
                    "isLLM": True,
                    "time": to_iso_utc(now_utc()),  # 使用服务器时间
                    "read": True,  # LLM 消息通常立即标记为已读
                    "status": "streaming",  # 状态为 streaming
                    "duration": None
                }
                # 直接通过发起请求的 websocket 发送
                await websocket.send_json({
                    "type": "llm_stream_start",
                    "data": {"message": start_message}
                })
                logger.info(f"用户 {from_user_id} LLM 流式开始 (_id: {llm_msg_id})")

                # 2. 调用 LLM 流式接口并迭代
                stream_generator = conv.chat_stream(user_message=content)
                try:
                    # 迭代生成器获取文本片段
                    for chunk in stream_generator:
                        full_reply_content += chunk
                        # 发送文本片段给用户
                        chunk_payload = {
                            "type": "llm_stream_chunk",
                            "data": {
                                "_id": llm_msg_id,  # 正在流式的消息 ID
                                "chunk": chunk,
                                # 可选：包含时间或其他信息
                                # "time": to_iso_utc(now_utc())
                            }
                        }
                        await websocket.send_json(chunk_payload)
                        # 可选：添加少量延迟模拟打字速度
                        # await asyncio.sleep(0.01)

                except Exception as e:
                    # 捕获流式过程中的 API 错误或其他异常
                    logger.error(
                        f"用户 {from_user_id} LLM 流式错误 (_id: {llm_msg_id}): {e}", exc_info=True)
                    # 将错误信息追加到内容末尾
                    full_reply_content += f"\n\n**AI 助手出错:** {e}"
                    llm_msg_status = "error"  # 设置状态为 error
                    # 发送流式错误消息给用户
                    error_payload = {
                        "type": "llm_stream_error",
                        "data": {
                            "_id": llm_msg_id,
                            "error": str(e),
                            "status": "error",
                            "content": full_reply_content,  # 发送当前为止的完整内容（包括错误）
                            "time": to_iso_utc(now_utc())
                        }
                    }
                    await websocket.send_json(error_payload)
                    # 注意：这里捕获异常后，循环会终止，后续会执行 finally 块或外层异常处理

            else:
                # --- LLM 非流式回复逻辑 ---
                # 1. 调用 LLM 非流式接口
                reply = conv.chat_non_stream(user_message=content)
                full_reply_content = reply
                llm_msg_status = "finished"  # 非流式完成后状态为 finished
                logger.info(f"用户 {from_user_id} LLM 非流式完成")

            # 3. 记录 LLM 结束处理的时间并计算用时
            end_time = time.monotonic()
            duration_sec = round(end_time - start_time)

            # 4. 将最终的 LLM 回复保存到数据库 (使用预生成的 ID 或新生成 ID)
            final_llm_doc = await save_message(
                from_user_id=to_user_id,  # LLM 是发送者
                to_user_id=from_user_id,  # 用户是接收者
                content=full_reply_content,
                chat_collection=chat_collection,
                is_llm=True,
                read=True,
                status=llm_msg_status,
                duration=duration_sec,
                _id=llm_msg_id if stream else None  # 流式使用预生成 ID，非流式由 DB 生成
            )

            # 5. 发送流式结束消息或完整的消息文档给用户
            if stream:
                # 发送流式结束消息
                end_payload = {
                    "type": "llm_stream_end",
                    "data": {
                        "_id": llm_msg_id,
                        "duration": duration_sec,
                        "status": llm_msg_status,
                        "content": full_reply_content,  # 发送最终的完整内容，用于前端校验或回填
                        # 使用从数据库保存文档中获取的服务器时间
                        "time": final_llm_doc.get("time")
                    }
                }
                await websocket.send_json(end_payload)
                logger.info(f"用户 {from_user_id} LLM 流式结束 (_id: {llm_msg_id})")

            else:
                # 非流式回复，发送完整的消息文档
                complete_payload = {
                    "type": "message",  # 使用 'message' 类型，前端按普通消息处理
                    "data": {
                        "message": final_llm_doc  # 发送完整的 LLM 消息文档
                    }
                }
                await websocket.send_json(complete_payload)
                logger.info(f"用户 {from_user_id} 非流式 LLM 回复已发送")

        except Exception as e:
            # 捕获处理 LLM 回复过程中的任何未预期异常
            logger.error(
                f"用户 {from_user_id} 处理 LLM 回复时发生未预期错误: {e}", exc_info=True)
            error_content = f"AI 助手发生未预期错误: {e}"
            # 确保有一个消息 ID 用于发送错误，如果是流式则使用已有的，否则生成新的
            err_msg_id = llm_msg_id if 'llm_msg_id' in locals() else str(ObjectId())

            # 保存一个错误消息到数据库
            error_doc = await save_message(
                from_user_id=llm_virtual_user_id,
                to_user_id=from_user_id,
                content=error_content,
                chat_collection=chat_collection,
                is_llm=True,  # 标记为 LLM 相关错误
                read=True,
                status="error",  # 状态为 error
                duration=None,
                _id=err_msg_id if stream else None  # 流式使用预生成 ID，非流式由 DB 生成
            )
            logger.info(f"用户 {from_user_id} LLM 错误消息已保存 (_id: {err_msg_id})")

            # 发送错误消息给用户
            # 如果是流式模式，发送 stream_error 消息；否则发送普通 message 消息
            error_payload = {
                "type": "message",
                "data": {
                    "message": error_doc
                }
            }
            if stream and 'llm_msg_id' in locals():
                error_payload = {
                    "type": "llm_stream_error",
                    "data": {
                        "_id": err_msg_id,
                        "error": str(e),
                        "status": "error",
                        "content": error_content,
                        "time": error_doc.get("time")
                    }
                }
            await websocket.send_json(error_payload)
            logger.info(f"用户 {from_user_id} LLM 错误消息已发送")


# 转发消息到指定收件人
async def forward_message(payload: dict, recipients: List[str], active_connections: Dict[str, WebSocket]):
    """将 payload 转发到指定的收件人用户 ID"""
    coros = []
    for uid in recipients:
        ws = active_connections.get(str(uid))  # 确保使用字符串 ID 查找连接
        if ws:
            # 检查 WebSocket 连接状态，尽量只发送给已连接的客户端
            # WebSocketState.CONNECTING=0, WebSocketState.CONNECTED=1, WebSocketState.DISCONNECTING=2, WebSocketState.DISCONNECTED=3
            if hasattr(ws, 'client_state') and ws.client_state == 1:
                coros.append(ws.send_json(payload))
            else:
                logger.warning(f"用户 {uid} 的 WebSocket 连接未处于连接状态，跳过转发")

    if not coros:
        logger.info("没有活跃连接需要转发消息")
        return

    # 并发执行发送操作，捕获单个发送过程中的异常
    results = await asyncio.gather(*coros, return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            logger.warning(f"消息转发失败: {res}")
            # 这里可以选择处理特定异常，例如如果是连接断开的异常，可以考虑清理 active_connections
            pass
