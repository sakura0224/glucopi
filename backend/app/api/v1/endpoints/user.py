# app/api/v1/endpoints/user.py

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path  # 导入 Path
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession  # 导入 AsyncSession
from typing import List, Optional  # 导入 Optional

from app.dependencies.auth import get_current_user
from app.db.mysql import get_db_http  # 导入异步数据库会话
from app.models.user import User, UserRole  # 导入 User 模型和 UserRole 枚举
from app.schemas.bindings import BoundPatientOut, BoundDoctorOut
from app.schemas.user import UserBasicInfoOut, UserOut, UserUpdate, UserProfileResponse
from app.schemas.profiles import PatientProfileOut, PatientProfileUpdate

# 从 app.services 导入用户和服务相关的服务函数
from app.services import user_service
from app.services import binding_service


router = APIRouter()


# --- 获取当前用户信息端点 (包含档案) ---
@router.get(
    "/me",
    response_model=UserOut,  # 返回 UserOut Schema，包含可能的 Profile
    summary="获取当前用户信息及档案"
)
async def read_user_me(
    current_user: User = Depends(get_current_user()),  # 获取当前用户，无需特定角色
    db: AsyncSession = Depends(get_db_http)  # 获取异步数据库会话
):
    """
    获取当前登录用户的基本信息和对应的档案信息（如果存在）。
    通过依赖注入获取的 current_user 通常是已经从数据库加载的，
    但为了确保 profile 已加载（如果依赖中没有加载），这里可以重新加载或在依赖中优化加载。
    这里调用服务层函数获取包含 profile 的用户。
    """
    # 调用服务层函数获取包含 profile 的用户对象
    user_with_profile = await user_service.get_user_with_profile(db, current_user.id)

    if not user_with_profile:
        # 理论上通过 get_current_user 获取的用户在数据库中应该存在
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="User not found in database")

    # 直接返回 SQLAlchemy Model 对象，Pydantic 会自动转换为 UserOut Schema
    return user_with_profile


# --- 更新用户信息端点 (通用字段) ---
@router.put(
    "/profile",  # 路径名 '/profile' 或 '/me' 都可以，选择一个
    response_model=UserOut,  # 返回更新后的完整 UserOut Schema (包含 Profile)
    summary="更新用户信息 (通用字段)"
)
async def update_profile(
    data: UserUpdate,  # 请求体使用 UserUpdate Schema
    user: User = Depends(get_current_user()),  # 获取当前用户 (SQLAlchemy 对象)
    db: AsyncSession = Depends(get_db_http)  # 获取异步数据库会话
):
    """
    更新当前登录用户的基本信息 (昵称, 性别, 头像, 生日)。
    档案信息 (身高体重, 职称医院等) 应通过其他特定端点更新。
    """
    try:
        # 调用服务层函数进行更新，它会返回更新并加载了 profile 的 User 对象
        updated_user = await user_service.update_user_info(user, data, db)

        # 直接返回 SQLAlchemy Model 对象
        # FastAPI 将使用 response_model=UserOut 和 UserOut 的 ConfigDict(from_attributes=True)
        # 自动将 updated_user 转换为 UserOut Schema 返回给客户端
        return updated_user
    except ValueError as e:  # 捕获服务层可能抛出的业务异常
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,  # 或 409 Conflict 等更合适的状态码
            detail=str(e)
        )
    except Exception as e:
        print(f"Error updating user profile for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during user profile update"
        )


# --- 获取患者已绑定的医生列表端点 ---
@router.get(
    "/doctors",
    response_model=List[BoundDoctorOut],  # 返回 BoundDoctorOut 列表
    summary="获取患者已绑定的医生列表"
)
async def get_my_doctors(
    current_user: User = Depends(get_current_user(
        required_role="patient")),  # 确保当前用户是患者
    db: AsyncSession = Depends(get_db_http)  # 获取异步数据库会话
):
    """
    获取当前患者用户已绑定的医生列表。
    只有患者用户可以访问。
    """
    try:
        # 调用服务层函数获取已绑定医生信息 (返回的是字典列表，与 BoundDoctorOut Schema 兼容)
        bound_doctors_data = await binding_service.get_bound_doctors_for_patient(
            db=db,
            patient_user_id=current_user.id
        )
        # FastAPI 将把字典列表转换为 BoundDoctorOut 模型列表
        return bound_doctors_data
    except Exception as e:
        print(
            f"Error getting bound doctors for patient {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching bound doctors"
        )


# --- 新增：更新患者档案端点 ---
@router.put(
    "/profile/patient",
    response_model=PatientProfileOut,  # 返回更新后的 PatientProfileOut Schema
    summary="更新患者档案信息"
)
async def update_patient_profile_endpoint(
    profile_data: PatientProfileUpdate,  # 请求体使用 PatientProfileUpdate Schema
    current_user: User = Depends(get_current_user(
        required_role=UserRole.patient)),  # 确保当前用户是患者
    db: AsyncSession = Depends(get_db_http)  # 获取异步数据库会话
):
    """
    更新当前登录患者的健康档案信息 (身高, 体重, 诊断日期等)。
    只有患者用户可以访问此接口。
    """
    try:
        # 调用服务层函数进行更新
        updated_profile = await user_service.update_patient_profile(
            db=db,
            user_id=current_user.id,  # 只需要当前用户ID
            profile_data=profile_data
        )
        # 服务函数返回 PatientProfile SQLAlchemy 对象，FastAPI 会自动转换为 PatientProfileOut Schema
        return updated_profile
    except ValueError as e:  # 捕获服务层可能抛出的业务异常 (如档案未找到)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,  # 或 404 Not Found 如果是档案未找到
            detail=str(e)
        )
    except Exception as e:
        print(
            f"Error updating patient profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during patient profile update"
        )


# --- 新增：获取单个用户基本信息端点 ---
@router.get(
    "/{user_id}/basic_info",  # 路径中包含用户ID
    response_model=UserBasicInfoOut,  # 返回 UserBasicInfoOut Schema
    summary="获取单个用户基本信息"
)
async def get_user_basic_info(
    user_id: int = Path(..., description="要获取基本信息的用户ID"),  # 从路径中获取用户ID
    current_user: User = Depends(get_current_user()),  # 需要用户认证，但无需特定角色
    db: AsyncSession = Depends(get_db_http)  # 获取异步数据库会话
):
    """
    获取指定用户ID的基本公开信息（昵称、头像、角色等）。
    任何已认证用户都可以调用此接口。
    """
    # 调用服务层函数获取用户基本信息
    user = await user_service.get_user_basic_info_by_id(db, user_id)

    if not user:
        # 如果用户不存在
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # 服务函数返回 User SQLAlchemy 对象，FastAPI 会自动转换为 UserBasicInfoOut Schema
    return user


@router.get(
    "/patients",
    response_model=List[BoundPatientOut],
    summary="获取当前医生已绑定的患者列表"
)
async def get_my_patients(
    current_user: User = Depends(get_current_user(required_role="doctor")),
    db: AsyncSession = Depends(get_db_http)
):
    """
    只有 doctor 角色可以访问。
    返回 BoundPatientOut 列表。
    """
    try:
        patients = await binding_service.get_bound_patients_for_doctor(
            db=db,
            doctor_user_id=current_user.id
        )
        return patients
    except Exception as e:
        # 日志记录
        print(
            f"Error getting bound patients for doctor {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取患者列表时发生意外错误"
        )

# TODO: 医生档案更新端点 (如果需要特定字段更新)
# @router.put(
#     "/profile/doctor",
#     response_model=schemas.profiles.DoctorProfileOut,
#     summary="更新医生档案信息"
# )
# async def update_doctor_profile(
#     data: schemas.profiles.DoctorProfileUpdate, # 需要定义这个 Schema
#     current_user: User = Depends(get_current_user(required_role=UserRole.doctor)),
#     db: AsyncSession = Depends(get_db_http)
# ):
#    # TODO: 实现服务函数 user_service.update_doctor_profile(db, current_user.id, data)
#    pass # 返回 DoctorProfile SQLAlchemy 对象或字典
