from fastapi import APIRouter, Depends
from app.schemas.auth import *
from app.services.auth_service import *
from app.db.mysql import get_db_http
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post("/register", response_model=LoginResponse, summary="注册账号")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db_http)):
    return await wechat_register(data, db)


@router.post("/login", response_model=LoginResponse, summary="手机号登录")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db_http)):
    return await login_user(data, db)


@router.post("/wechatLogin", response_model=LoginResponse, summary="openid 登录")
async def login_by_wechat(code: str, db: AsyncSession = Depends(get_db_http)):
    return await wechat_login(code, db)


@router.post("/checkOpenid", response_model=OpenidCheckResponse, summary="检查 openid 是否注册")
async def check_openid(data: CodeRequest, db: AsyncSession = Depends(get_db_http)):
    return await check_openid_registered(data.code, db)


@router.get("/checkAccount", response_model=AccountCheckResponse, summary="检查手机号是否注册")
async def check_account(phone: str, db: AsyncSession = Depends(get_db_http)):
    return await check_phone_registered(phone, db)
