# app/dependencies/ws.py

from fastapi import Depends, Header, HTTPException, status, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from app.db.mysql import AsyncSessionLocal # <--- 导入 Session 工厂


from app.models.user import User, UserRole
from app.utils.security import decode_jwt_token
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload


# --- 获取数据库会话的 context manager (用于手动获取) ---
@asynccontextmanager
async def get_db_session_manual() -> AsyncGenerator[AsyncSession, None]:
    """
    手动获取异步数据库会话的 context manager。
    """
    async with AsyncSessionLocal() as session:
        yield session


# --- WebSocket 专用的获取当前用户依赖函数 (核心验证逻辑，手动获取 DB) ---
async def get_current_user_ws(
    required_role: Optional[UserRole] = None,
    token: Optional[str] = None
) -> User:
    # print(f"[WS Auth] Inside get_current_user_ws (Manual DB). required_role: {required_role}, token: {token is not None}")

    if not token:
        # print("[WS Auth] get_current_user_ws (Manual DB): Token missing")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization token missing")

    try:
        user_id = decode_jwt_token(token)
        # print(f"[WS Auth] get_current_user_ws (Manual DB): Decoded user_id: {user_id}")
    except ValueError as e:
        # print(f"[WS Auth] get_current_user_ws (Manual DB): Token validation failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token validation error: {e}")
    except Exception as e:
        # print(f"[WS Auth] get_current_user_ws (Manual DB): Unexpected error decoding token: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during token validation")

    # --- 在这里手动获取数据库会话 ---
    async with get_db_session_manual() as db: # <--- 使用手动 context manager 获取 db
        # print(f"[WS Auth] get_current_user_ws (Manual DB): Acquired DB session.") # <-- 添加日志
        try:
            user_result = await db.execute( # 现在 db 应该是 AsyncSession 了
                select(User)
                .filter(User.id == user_id)
                .options(selectinload(User.patient_profile), selectinload(User.doctor_profile))
            )
            user = user_result.scalars().first()
            # print(f"[WS Auth] get_current_user_ws (Manual DB): Fetched user: {user}, Role: {user.role if user else 'None'}")
        except Exception as e:
            #  print(f"[WS Auth] get_current_user_ws (Manual DB): Error fetching user: {e}")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error fetching user")
        # db 会话在这里随着 async with 块结束而关闭/释放

    if not user:
        # print(f"[WS Auth] get_current_user_ws (Manual DB): User ID {user_id} not found in database")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found associated with token")

    if required_role is not None and user.role != required_role:
        # print(f"[WS Auth] get_current_user_ws (Manual DB): Role mismatch! User role: {user.role}, Required: {required_role.value}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Operation requires {required_role.value} role")

    # print(f"[WS Auth] get_current_user_ws (Manual DB): User authenticated successfully: {user.id}")
    return user


# --- 依赖工厂函数 (在内部手动获取 token，调用 get_current_user_ws) ---
def get_current_user_ws_factory(required_role: Optional[UserRole] = None):
    # print(f"[WS Auth] get_current_user_ws_factory called. required_role: {required_role}")
    async def _get_current_user_ws_with_role(
        websocket: WebSocket,
    ) -> User:
        # print(f"[WS Auth] Inside _get_current_user_ws_with_role. required_role from closure: {required_role}")

        # 手动从 websocket 中获取 token
        token = websocket.query_params.get("token")
        # print(f"[WS Auth] Inside _get_current_user_ws_with_role: Manually got token: {token is not None}")

        try:
            user = await get_current_user_ws(required_role=required_role, token=token)
            return user

        except HTTPException as e:
            #  print(f"[WS Auth] _get_current_user_ws_with_role caught HTTPException from inner function: {e.detail}, status: {e.status_code}")
             ws_code = status.WS_1008_POLICY_VIOLATION
             reason = e.detail
             if e.status_code == status.HTTP_401_UNAUTHORIZED: ws_code = status.WS_1008_POLICY_VIOLATION
             elif e.status_code == status.HTTP_403_FORBIDDEN: ws_code = status.WS_1008_POLICY_VIOLATION
             elif e.status_code == status.HTTP_404_NOT_FOUND: ws_code = status.WS_1008_POLICY_VIOLATION
             elif e.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR: ws_code = status.WS_1011_INTERNAL_ERROR

             # 手动关闭 websocket
             await websocket.close(code=ws_code, reason=reason)
             # 重新抛出 HTTPException，让 FastAPI 处理
             raise e

        except Exception as e:
            #  print(f"[WS Auth] _get_current_user_ws_with_role caught unexpected exception: {e}")
             # 手动关闭 websocket
             await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
             # 重新抛出异常，让 FastAPI 处理
             raise e


    return _get_current_user_ws_with_role