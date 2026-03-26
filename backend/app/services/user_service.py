from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
# from fastapi import HTTPException # 建议不要在服务层抛 HTTPException
from sqlalchemy.future import select  # 使用 future 风格的 select
from sqlalchemy.orm import selectinload  # 导入 selectinload

from app.models.profiles import PatientProfile
from app.models.user import User, UserRole  # 导入 User Model 和 UserRole
from app.schemas.profiles import PatientProfileUpdate
from app.schemas.user import UserUpdate  # 导入 UserUpdate Schema (用于接收更新数据)
# from app.schemas.user import UserCreate # 导入 UserCreate Schema (如果这里实现注册逻辑)
# from app.schemas.profiles import PatientProfileCreate, DoctorProfileCreate # 导入 Profile Create Schema


# --- 获取用户相关服务函数 ---
async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """根据ID获取用户，不加载档案。"""
    result = await db.execute(select(User).filter(User.id == user_id))
    return result.scalars().first()


async def get_user_with_profile(db: AsyncSession, user_id: int) -> Optional[User]:
    """根据ID获取用户，并加载档案。"""
    result = await db.execute(
        select(User)
        .filter(User.id == user_id)
        # 明确加载 patient_profile 和 doctor_profile 关系
        .options(selectinload(User.patient_profile), selectinload(User.doctor_profile))
    )
    return result.scalars().first()

# TODO: 根据其他需求添加获取用户的服务函数 (如 get_user_by_phone, get_user_by_openid 等)


# --- 用户更新服务函数 ---
async def update_user_info(user: User, data: UserUpdate, db: AsyncSession) -> User:
    """
    更新用户的基本信息字段。

    Args:
        user: 从数据库加载的当前用户 SQLAlchemy 对象。
        data: 用户更新数据的 Pydantic Schema (UserUpdate)。
        db: 异步数据库会话。

    Returns:
        更新并重新从数据库加载的 User SQLAlchemy 对象 (包含加载的 profile)。

    Raises:
        ValueError: 如果用户对象无效 (由调用方处理，或在依赖中确保)。
    """
    # user 对象通常是从依赖注入获取的，假设它是有效的数据库对象
    # 如果需要，可以在调用此服务函数前验证 user 对象

    # 使用 model_dump(exclude_unset=True) 只获取请求体中实际提供的字段
    user_data = data.model_dump(exclude_unset=True)

    # 遍历提供的更新字段，设置到用户对象上
    for field, value in user_data.items():
        # 确保只更新 User 模型中存在的且 UserUpdate Schema 允许更新的字段
        if hasattr(user, field):
            setattr(user, field, value)
        # 对于 phone 和 role 等敏感字段，它们不在 UserUpdate 中，所以不会被这里更新。

    await db.commit()  # 提交更改到数据库
    # await db.refresh(user) # 刷新 user 对象本身的基本字段 (可选，后续重新加载会获取最新值)

    # 在更新后重新从数据库加载用户对象，并明确加载 profile 关系，以便 API 端点返回 UserOut 时包含档案信息
    # 调用上面定义的函数重新加载
    updated_user_with_profile = await get_user_with_profile(db, user.id)

    if not updated_user_with_profile:
        # 理论上不会发生，除非并发操作导致用户被删除
        raise ValueError(
            f"Could not retrieve user with ID {user.id} after update")

    return updated_user_with_profile  # 返回包含 profile 的用户 SQLAlchemy 对象


# --- 修改：更新患者档案服务函数，支持创建 ---
async def update_patient_profile(db: AsyncSession, user_id: int, profile_data: PatientProfileUpdate) -> PatientProfile:
    """
    更新患者的健康档案信息。如果档案不存在，则创建一个新的。

    Args:
        db: 异步数据库会话。
        user_id: 患者用户ID。
        profile_data: 患者档案更新数据的 Pydantic Schema (PatientProfileUpdate)。

    Returns:
        更新或创建并刷新后的 PatientProfile SQLAlchemy 对象。

    Raises:
        ValueError: 如果用户ID无效或用户不是患者 (尽管通常在依赖中验证)。
    """
    # 查找患者档案
    profile_result = await db.execute(select(PatientProfile).filter(PatientProfile.user_id == user_id))
    patient_profile = profile_result.scalars().first()

    # --- 修改这里：如果档案不存在，创建新档案 ---
    if not patient_profile:
        print(
            f"Patient profile not found for user ID {user_id}. Creating new profile.")
        # 创建一个新的 PatientProfile 实例
        patient_profile = PatientProfile(user_id=user_id)
        db.add(patient_profile)  # 将新创建的对象添加到会话
        # await db.flush() # 不需要 flush，commit 会处理插入并获取 ID

    # --- 不管是旧档案还是新档案，都应用更新数据 ---
    # 使用 model_dump(exclude_unset=True) 只获取请求体中实际提供的字段
    update_data = profile_data.model_dump(exclude_unset=True)

    # 遍历提供的更新字段，设置到档案对象上
    for field, value in update_data.items():
        # 确保只更新 PatientProfile 模型中存在的字段
        if hasattr(patient_profile, field):
            setattr(patient_profile, field, value)
        # else:
        #      print(f"Warning: Attempted to update non-existent field in PatientProfile: {field}")

    # updated_at 由数据库 ON UPDATE 自动更新 (或者手动设置)
    # patient_profile.updated_at = time.now_utc() # 如果数据库没有 ON UPDATE

    await db.commit()  # 提交更改 (如果是新档案则插入，如果是旧档案则更新)
    await db.refresh(patient_profile)  # 刷新档案对象以获取数据库自动填充的字段值和新档案的 ID

    return patient_profile  # 返回更新或创建后的 PatientProfile SQLAlchemy 对象

# --- 新增：根据用户 ID 获取用户基本信息服务函数 ---


async def get_user_basic_info_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """
    根据用户ID获取用户的基本公开信息 (不加载档案)。

    Args:
        db: 异步数据库会话。
        user_id: 用户ID。

    Returns:
        用户的 SQLAlchemy 对象 (包含基本信息)，如果用户不存在则返回 None。
    """
    # 直接查询 User 表，不加载关系
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    return user  # 返回 User 对象，API 层会将其转换为 UserBasicInfoOut Schema

# TODO: 用户注册服务函数 (通常在 auth_service 或 user_service)
# async def create_user_with_profile(db: AsyncSession, user_data: UserCreate) -> User:
#    """
#    创建用户并根据角色创建对应的档案 (如果角色是 patient 或 doctor)。
#    """
#    # 1. 检查 openid 或 phone 是否已存在 (异步查询)
#    existing_user = await db.execute(
#        select(User).filter(or_(User.openid == user_data.openid, User.phone == user_data.phone)).limit(1)
#    )
#    if existing_user.scalars().first():
#        raise ValueError("User with this openid or phone already exists")
#
#    # 2. 创建 User 对象
#    user = User(
#        openid=user_data.openid,
#        unionid=user_data.unionid,
#        nickname=user_data.nickname,
#        gender=user_data.gender,
#        avatar_url=user_data.avatar_url,
#        birthday=user_data.birthday,
#        phone=user_data.phone,
#        role=user_data.role or UserRole.patient # 默认患者
#    )
#    db.add(user)
#    await db.flush() # 获取 user.id
#
#    # 3. 根据角色创建档案
#    if user.role == UserRole.patient:
#        patient_profile = PatientProfile(user_id=user.id)
#        db.add(patient_profile)
#    elif user.role == UserRole.doctor:
#        doctor_profile_data = DoctorProfileCreate(...) # 需要从注册请求中获取医生特有信息
#        doctor_profile = DoctorProfile(user_id=user.id, **doctor_profile_data.model_dump())
#        db.add(doctor_profile)
#
#    await db.commit()
#    await db.refresh(user) # 刷新用户对象以获取数据库填充的字段和 profile 关系
#
#    # 确保加载 profile 以便返回 UserOut
#    user_with_profile = await get_user_with_profile(db, user.id)
#    return user_with_profile
