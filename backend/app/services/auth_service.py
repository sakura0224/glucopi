# app/services/auth_service.py

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException
from app.db.mysql import get_db_http
from app.models.user import User
from app.schemas.auth import *
from app.utils.security import create_jwt_token
from app.utils.wechat import get_openid_from_code


# 微信 openid 登录
async def wechat_login(code: str, db: AsyncSession) -> LoginResponse:
    openid, _ = await get_openid_from_code(code)

    result = await db.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()

    if not user or not user.phone:
        # 没找到用户或者还未绑定手机号 → 视为未注册
        raise HTTPException(status_code=404, detail="用户尚未注册")

    return LoginResponse(
        token=create_jwt_token(user.id),
        user_id=user.id,
        role=user.role
    )


# 微信注册
async def wechat_register(data: RegisterRequest, db: AsyncSession) -> LoginResponse:
    openid, _ = await get_openid_from_code(data.code)

    result = await db.execute(select(User).where(User.phone == data.phone))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="手机号已注册")

    new_user = User(
        phone=data.phone,
        openid=openid,
        role="patient"
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    print("Token:", create_jwt_token(new_user.id))
    return LoginResponse(
        token=create_jwt_token(new_user.id),
        user_id=new_user.id,
        role=new_user.role
    )


# 登录
async def login_user(data: LoginRequest, db: AsyncSession = Depends(get_db_http)) -> LoginResponse:
    result = await db.execute(select(User).where(User.phone == data.phone))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return LoginResponse(
        token=create_jwt_token(user.id),
        user_id=user.id,
        role=user.role
    )


# 检查手机号是否注册
async def check_phone_registered(phone: str, db: AsyncSession) -> AccountCheckResponse:
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()

    return AccountCheckResponse(
        registered=bool(user),
        user_id=user.id if user else None
    )


# 检查 OpenID 是否注册
async def check_openid_registered(code: str, db: AsyncSession) -> OpenidCheckResponse:
    openid, _ = await get_openid_from_code(code)
    result = await db.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()

    if user and user.phone:
        # 已注册 + 已绑定手机号 → 可直接登录
        return OpenidCheckResponse(
            registered=True,
            token=create_jwt_token(user.id),
            user_id=user.id,
            role=user.role
        )
    else:
        return OpenidCheckResponse(
            registered=False,
            token=None,
            user_id=None,
            role='patient'
        )
