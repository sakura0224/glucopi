# app/dependencies.py

from fastapi import Depends, Header, HTTPException, status  # 导入 status
# 如果你的认证流程基于 OAuth2 Password Bearer
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional  # 导入 Optional

# 从你的数据库模块导入异步会话依赖
from app.db.mysql import get_db_http  # 如果 get_db_http 是你的依赖函数
# from app.db.mysql import get_db_session # 假设你有一个通用的 get_db_session 依赖函数

# 从你的模型导入 User 和 UserRole
from app.models.user import User, UserRole

# 从你的安全工具导入 JWT 解码函数
from app.utils.security import decode_jwt_token  # 假设这个函数存在

# 定义 OAuth2 Scheme (如果使用 Bearer Token)
# 这个 scheme 只是用于在 OpenAPI (Swagger UI) 中描述安全机制
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token") # 根据你的登录端点修改 tokenUrl

# --- 创建依赖工厂函数 ---


def get_current_user(required_role: Optional[UserRole] = None):
    async def _get_current_user(
        authorization: str = Header(..., description="Bearer Token"),
        db: AsyncSession = Depends(get_db_http)
    ) -> User:
        """
        解析 JWT Token 获取用户，并可选验证用户角色。
        """
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
        token = authorization.replace("Bearer ", "")

        try:
            # --- 修改这里：直接调用 decode_jwt_token 并获取用户 ID ---
            # <--- decode_jwt_token 直接返回 int (user_id)
            user_id = decode_jwt_token(token)
            # --- 修改结束 ---

        # --- 修改异常捕获：捕获 decode_jwt_token 抛出的 ValueError ---
        except ValueError as e:  # 捕获 decode_jwt_token 抛出的 ValueError
            # e 的内容会是 "Token 已过期" 或 "Token 无效" 或 "Token payload missing 'sub'" 等
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token validation error: {e}")
        # --- 修改异常捕获结束 ---
        except Exception as e:
            # 捕获其他可能的未知异常（如数据库连接问题等，虽然不太可能发生在这里）
            print(f"Unexpected error during token validation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred")

        # 从数据库获取用户对象 (异步)，加载 profile
        user_result = await db.execute(
            select(User)
            .filter(User.id == user_id)
            .options(selectinload(User.patient_profile), selectinload(User.doctor_profile))
        )
        user = user_result.scalars().first()

        if not user:
            # 如果用户不存在，说明 token 中的 user_id 是无效的
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="User not found associated with token")

        # --- 角色验证逻辑 ---
        if required_role is not None and user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires {required_role.value} role"
            )
        # --- 角色验证结束 ---

        return user  # 返回加载并验证后的用户 SQLAlchemy 对象 (包含 profile)

    return _get_current_user  # 工厂函数返回内部依赖函数


async def get_optional_user(current: User = Depends(get_current_user())) -> Optional[User]:
    try:
        return current
    except HTTPException:
        return None

# 为了兼容旧代码或者在不需要角色验证的地方方便使用，可以保留一个不带参数的别名
# 但更推荐总是使用 get_current_user() 或 get_current_user(required_role=...)
# get_user_no_role = get_current_user() # 示例：不带角色验证的版本

# 确保 get_db_session 也在这个文件或 app.db.mysql 中被正确定义和导出
# 如果 get_db_http 是你的依赖函数，请修改上面代码中使用 get_db_session 的地方为 get_db_http
