# app/api/v1/websocket/ws.py

import json
import logging  # 导入日志模块
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from typing import Dict, Optional  # 导入类型提示
from motor.motor_asyncio import AsyncIOMotorCollection  # 导入 MongoDB 集合类型
# from bson import ObjectId # 不在此文件直接处理 ObjectId

from app.models.user import User  # 导入用户模型
from app.dependencies.ws import get_current_user_ws_factory  # 导入 WebSocket 用户认证依赖
# 导入 chat_service 模块，包含消息处理服务
from app.services import chat_service
from app.db.mongo import get_chat_collection  # 导入提供 MongoDB 集合的依赖函数
# from app.utils.time import to_iso_utc # 不在此文件直接处理时间格式
from app.core.config import settings  # 导入配置 settings

# 配置 logger
logger = logging.getLogger(__name__)

router = APIRouter()
# 存储活跃的 WebSocket 连接: userId -> WebSocket 对象
active_connections: Dict[str, WebSocket] = {}


# WebSocket 端点定义
@router.websocket("/chat")
async def chat_websocket(
    websocket: WebSocket,
    # 依赖注入：获取当前认证用户 (WebSocket 连接时认证)
    current_user: User = Depends(get_current_user_ws_factory()),
    # 依赖注入：获取 MongoDB chat 集合
    mongo_chat_collection: AsyncIOMotorCollection = Depends(
        get_chat_collection),
):
    # 接受 WebSocket 连接
    await websocket.accept()

    # 将用户 ID 转换为字符串，存储连接
    user_id = str(current_user.id)
    active_connections[user_id] = websocket
    logger.info(f"用户 {user_id} ({current_user.nickname}) 已连接")

    try:
        # 1. 连接建立成功后：向客户端发送初始配置 (如 LLM 虚拟用户 ID, LLM 头像 URL)
        await websocket.send_json({
            "type": "config",
            "data": {
                "llmUserId": str(settings.LLM_VIRTUAL_USER_ID),  # LLM 虚拟用户 ID
                # LLM 头像 URL
                "llmAvatarUrl": str(settings.LLM_AVATAR_URL) if settings.LLM_AVATAR_URL else None
            }
        })
        logger.info(f"用户 {user_id} 已发送配置")

        # 2. 如果连接请求包含目标用户 ID，加载并发送历史消息
        target = websocket.query_params.get("target")
        if target:
            logger.info(f"用户 {user_id} 请求与 {target} 的历史消息")
            # 调用 chat_service 获取历史消息
            history = await chat_service.get_chat_history(
                user_id, target, mongo_chat_collection, limit=settings.CHAT_HISTORY_LIMIT)  # 使用配置的 limit
            # 发送历史消息，封装在 'messages' 键下
            await websocket.send_json({"type": "history", "data": {"messages": history}})
            logger.info(f"用户 {user_id} 已发送历史消息 ({len(history)} 条)")

        # 3. 循环接收客户端发送的消息
        while True:
            try:
                # 接收文本消息
                raw_message = await websocket.receive_text()
                # 解析 JSON 消息
                data = json.loads(raw_message)
                logger.info(f"收到用户 {user_id} 消息: {data}")

            except json.JSONDecodeError:
                # 处理 JSON 解析错误
                logger.warning(
                    f"用户 {user_id} 发送非法 JSON：{raw_message[:100]}...")
                await websocket.send_json({"type": "error", "message": "Invalid JSON format"})
                continue  # 继续接收下一条消息

            except RuntimeError as e:
                # 处理 WebSocket 连接相关的运行时错误 (如连接已断开)
                if "WebSocket is not connected" in str(e):
                    logger.info(f"用户 {user_id} WebSocket 已断开连接，退出接收循环")
                    break  # 退出接收循环
                else:
                    # 抛出其他运行时错误
                    logger.error(
                        f"用户 {user_id} WebSocket 接收时发生运行时错误: {e}", exc_info=True)
                    raise e  # 向上层抛出异常

            msg_type = data.get("type")  # 获取消息类型

            # 4. 根据消息类型处理
            if msg_type == "message":
                # 处理普通聊天消息
                msg_data = data.get("data")
                if not msg_data:
                    logger.warning(f"用户 {user_id} 发送消息数据为空")
                    await websocket.send_json({"type": "error", "message": "Message data is empty"})
                    continue

                # 提取消息内容和元数据
                to_user_raw = msg_data.get("to")  # 接收者用户 ID (可以是医生或 LLM ID)
                content = msg_data.get("content")  # 消息内容
                timestamp = msg_data.get("time")  # 客户端时间戳 (毫秒)
                # 提取是否需要流式回复的标志，默认为 False
                stream_flag = msg_data.get("stream", False)

                # 验证必要字段
                if not to_user_raw or not content:
                    logger.warning(f"用户 {user_id} 发送消息缺少收件人或内容")
                    await websocket.send_json({"type": "error", "message": "Recipient or content missing"})
                    continue

                to_user = str(to_user_raw)  # 确保目标用户 ID 为字符串

                try:
                    # 调用 chat_service 处理消息
                    # 传递所有必要的参数，包括 websocket 和 active_connections 用于转发和流式推送
                    await chat_service.handle_user_message(
                        from_user_id=user_id,
                        to_user_id=to_user,
                        content=content,
                        chat_collection=mongo_chat_collection,  # MongoDB 集合
                        websocket=websocket,  # 当前 WebSocket 连接 (用于流式回复)
                        active_connections=active_connections,  # 所有活跃连接 (用于转发)
                        timestamp=timestamp,  # 客户端时间戳
                        stream=stream_flag,  # 是否进行流式回复
                    )

                except Exception as e:
                    # 捕获 chat_service 层抛出的异常
                    logger.error(f"用户 {user_id} 处理消息失败: {e}", exc_info=True)
                    # 向客户端发送错误提示消息
                    await websocket.send_json({"type": "error", "message": f"Failed to process message: {e}"})

            # TODO: 根据需要处理其他消息类型 (如 "read_receipt", "typing", "presence" 等)
            # elif msg_type == "read_receipt":
            #     # ... 调用 chat_service.mark_messages_read 等
            #     pass

            else:
                # 处理未知的消息类型
                logger.warning(f"用户 {user_id} 发送未知消息类型: {msg_type}")
                await websocket.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})

    except WebSocketDisconnect as e:
        # 处理 WebSocket 断开连接事件
        logger.info(f"用户 {user_id} 离线 (Code: {e.code}, Reason: {e.reason})")
        # 从活跃连接中移除
        active_connections.pop(user_id, None)
    except Exception as e:
        # 捕获任何未预期的顶级异常
        logger.error(f"WebSocket 用户 {user_id} 发生未预期错误: {e}", exc_info=True)
        # 尝试从活跃连接中移除
        active_connections.pop(user_id, None)
        # 尝试关闭 WebSocket 连接
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
        except RuntimeError:
            # 可能连接已经断开，忽略关闭错误
            pass
