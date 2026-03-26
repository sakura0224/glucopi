# app/services/binding_service.py

from app.models.bindings import BindingStatus  # 假设你有BindingStatus枚举
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, join, or_, and_, update, delete
from typing import List, Optional
from app.models import User, DoctorProfile, PatientProfile, Binding, BindingStatus
from app.models.user import UserRole
from app.schemas.bindings import BindingCreate, BoundPatientOut
from app.utils import time


# --- 患者端服务 (代码与之前提供的异步版本一致) ---
async def get_bound_doctors_for_patient(db: AsyncSession, patient_user_id: int) -> List[dict]:
    """
    获取患者已绑定的医生列表 (status='accepted') - 异步
    ... (查询和结果处理代码不变) ...
    """
    stmt = select(
        User.id, User.nickname, User.avatar_url,
        DoctorProfile.title, DoctorProfile.department, DoctorProfile.hospital, DoctorProfile.specialization,
        # 这些是 SQLAlchemy 字段，读取时通常是 datetime 对象
        Binding.id.label("binding_id"), Binding.status,
        # 如果需要，可以在这里也选择时间字段，并在返回前格式化
        # Binding.requested_at, Binding.accepted_at, Binding.rejected_at
    ).join(Binding, Binding.doctor_user_id == User.id) \
     .join(DoctorProfile, DoctorProfile.user_id == User.id) \
     .filter(
         Binding.patient_user_id == patient_user_id,
         Binding.status.in_(
             [BindingStatus.accepted, BindingStatus.pending])  # 使用 in_ 操作符
    )
    results = await db.execute(stmt)
    rows = results.all()

    # 将查询结果转换为字典列表
    # SQLAlchemy ORM 默认读取的 TIMESTAMP(timezone=True) 字段是时区感知的 datetime 对象 (UTC)
    # Pydantic 的 datetime 字段如果设置了 ConfigDict(from_attributes=True)，
    # 并且接收到的是时区感知的 datetime 对象，通常会自动序列化为 ISO8601 字符串，
    # 包括正确的时区信息或 Z 后缀。
    # 如果 Pydantic 没有自动处理，或者你想在服务层就格式化，可以使用 time.format_time_fields
    # formatted_rows = []
    # for row in rows:
    #     row_dict = row._asdict()
    #     time.format_time_fields(row_dict, ["requested_at", "accepted_at", "rejected_at"]) # 需要在 select 中加入这些字段
    #     formatted_rows.append(row_dict)
    # return formatted_rows
    # 假设 Pydantic Schema (BoundDoctorOut) 能处理，直接返回 SQLAlchemy Row 转的字典即可
    return [row._asdict() for row in rows]


async def search_doctors(db: AsyncSession, keyword: str, current_user_id: int) -> List[dict]:
    """
    搜索医生，并包含当前用户与该医生的绑定状态 - 异步
    ... (查询和结果处理代码不变) ...
    """
    search_stmt = select(User, DoctorProfile) \
        .join(DoctorProfile, DoctorProfile.user_id == User.id) \
        .filter(User.role == UserRole.doctor) \
        .filter(
            or_(
                User.nickname.ilike(f"%{keyword}%"),
                DoctorProfile.department.ilike(f"%{keyword}%"),
                DoctorProfile.hospital.ilike(f"%{keyword}%"),
                DoctorProfile.specialization.ilike(f"%{keyword}%")
            )
    )
    search_results_exec = await db.execute(search_stmt)
    search_results = search_results_exec.all()

    result_list = []
    for user, profile in search_results:
        binding_status: Optional[BindingStatus] = None
        # 可以在这里同时查询绑定信息，以避免 N+1 查询，例如使用 leftjoin 和 group by
        # 但为了与当前结构保持一致，继续使用 N+1 风格查询绑定状态
        binding_stmt = select(Binding) \
            .filter(
            and_(
                Binding.patient_user_id == current_user_id,
                Binding.doctor_user_id == user.id
            )
        )
        binding_result = await db.execute(binding_stmt)
        binding = binding_result.scalars().first()

        if binding:
            binding_status = binding.status

        result_list.append({
            "id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "title": profile.title,
            "department": profile.department,
            "hospital": profile.hospital,
            "specialization": profile.specialization,
            "binding_status": binding_status
        })
    return result_list


async def request_binding(db: AsyncSession, patient_user_id: int, doctor_user_id: int):
    """
    患者发起绑定申请（自动复用已取消/解除的旧记录）
    """
    # 1. 校验目标医生存在且是医生
    doctor_user_result = await db.execute(
        select(User).filter(
            User.id == doctor_user_id,
            User.role == UserRole.doctor
        )
    )
    doctor_user = doctor_user_result.scalars().first()
    if not doctor_user:
        raise ValueError("Doctor not found or is not a doctor user")

    # 2. 查询是否已有绑定记录（任何状态）
    existing_binding_result = await db.execute(
        select(Binding).filter(
            and_(
                Binding.patient_user_id == patient_user_id,
                Binding.doctor_user_id == doctor_user_id
            )
        )
    )
    existing_binding = existing_binding_result.scalars().first()

    # 3. 处理已有记录的情况
    if existing_binding:
        if existing_binding.status in [BindingStatus.pending, BindingStatus.accepted]:
            # 如果是正在申请或已绑定，拒绝重复申请
            status_map = {
                BindingStatus.pending: "您已向该医生发送过申请",
                BindingStatus.accepted: "您已绑定该医生"
            }
            raise ValueError(status_map.get(
                existing_binding.status, "已存在绑定关系"))
        elif existing_binding.status in [BindingStatus.rejected, BindingStatus.cancelled, BindingStatus.inactive]:
            # 如果是被拒绝、自己取消、解绑，复用记录，改回 pending
            existing_binding.status = BindingStatus.pending
            existing_binding.accepted_at = None
            existing_binding.rejected_at = None
            # 如果有 requested_at 字段，可以重新设定 requested_at
            # existing_binding.requested_at = time.now_utc()  # 可选
            await db.commit()
            await db.refresh(existing_binding)
            return existing_binding

    # 4. 如果没有任何记录，新建一条
    new_binding = Binding(
        patient_user_id=patient_user_id,
        doctor_user_id=doctor_user_id,
        status=BindingStatus.pending,
        # requested_at=time.now_utc()  # 如果需要
    )
    db.add(new_binding)
    await db.commit()
    await db.refresh(new_binding)
    return new_binding


# --- 新增：医生接受绑定申请服务函数 ---
async def accept_binding_request(db: AsyncSession, binding_id: int, doctor_user_id: int):
    """
    医生接受患者的绑定申请 - 异步
    """
    binding_result = await db.execute(select(Binding).filter(Binding.id == binding_id))
    binding = binding_result.scalars().first()

    if not binding:
        raise ValueError("Binding request not found")

    if binding.doctor_user_id != doctor_user_id:
        raise ValueError("You are not authorized to accept this request")

    if binding.status != BindingStatus.pending:
        status_map = {
            BindingStatus.accepted: "Binding already accepted",
            BindingStatus.rejected: "Binding request was rejected",
            BindingStatus.inactive: "Binding was deactivated",
            BindingStatus.cancelled: "Binding request was cancelled"
        }
        raise ValueError(status_map.get(
            binding.status, f"Cannot accept binding in status: {binding.status.value}"))

    # --- 使用 time.now_utc() 设置时间字段 ---
    binding.status = BindingStatus.accepted
    binding.accepted_at = time.now_utc()
    # updated_at 应该由数据库的 ON UPDATE CURRENT_TIMESTAMP 自动更新
    # 如果数据库没有这个设置，或者你想手动控制，可以使用 binding.updated_at = time.now_utc()

    await db.commit()
    await db.refresh(binding)  # 如果API端点需要返回完整的binding对象，可能需要refresh
    return binding


# --- 新增：医生拒绝绑定申请服务函数 ---
async def reject_binding_request(db: AsyncSession, binding_id: int, doctor_user_id: int):
    """
    医生拒绝患者的绑定申请 - 异步
    """
    binding_result = await db.execute(select(Binding).filter(Binding.id == binding_id))
    binding = binding_result.scalars().first()

    if not binding:
        raise ValueError("Binding request not found")

    if binding.doctor_user_id != doctor_user_id:
        raise ValueError("You are not authorized to reject this request")

    if binding.status != BindingStatus.pending:
        raise ValueError(
            f"Cannot reject binding in status: {binding.status.value}")

    # --- 使用 time.now_utc() 设置时间字段 ---
    binding.status = BindingStatus.rejected
    binding.rejected_at = time.now_utc()

    await db.commit()
    await db.refresh(binding)
    return binding


# --- 新增：患者取消绑定申请服务函数 ---
async def cancel_binding_request(db: AsyncSession, binding_id: int, patient_user_id: int):
    """
    患者取消自己发起的绑定申请 - 异步
    """
    binding_result = await db.execute(select(Binding).filter(Binding.id == binding_id))
    binding = binding_result.scalars().first()

    if not binding:
        raise ValueError("Binding request not found")

    if binding.patient_user_id != patient_user_id:
        raise ValueError("You are not authorized to cancel this request")

    if binding.status != BindingStatus.pending:
        raise ValueError(
            f"Cannot cancel binding in status: {binding.status.value}")

    binding.status = BindingStatus.cancelled

    await db.commit()
    await db.refresh(binding)
    return binding


# --- 新增：解除绑定服务函数 (可由患者或医生发起) ---
async def deactivate_binding(db: AsyncSession, binding_id: int, user_id: int):
    """
    解除绑定关系 (将状态设为 'inactive') - 异步
    可由患者或医生发起，但必须是绑定关系中的一方
    """
    binding_result = await db.execute(select(Binding).filter(Binding.id == binding_id))
    binding = binding_result.scalars().first()

    if not binding:
        raise ValueError("Binding not found")

    if binding.patient_user_id != user_id and binding.doctor_user_id != user_id:
        raise ValueError("You are not part of this binding relationship")

    if binding.status != BindingStatus.accepted:
        raise ValueError(
            f"Cannot deactivate binding in status: {binding.status.value}")

    # --- updated_at 由数据库 ON UPDATE 自动更新 ---
    binding.status = BindingStatus.inactive
    # 可选：记录解除时间
    # binding.deactivated_at = time.now_utc() # 如果有这个字段的话
    # --- 修改结束 ---

    await db.commit()
    await db.refresh(binding)
    # 返回成功信息，而不是对象，因为对象状态已经改变，且解除通常不需要返回详情
    return {"message": "Binding deactivated successfully"}


async def get_bound_patients_for_doctor(
    db: AsyncSession,
    doctor_user_id: int
) -> List[BoundPatientOut]:
    """
    查询所有已接受邀请并绑定到当前医生的患者，
    返回 Pydantic 模型列表 BoundPatientOut。
    """
    # 筛选 status 为 pending 或 accepted
    stmt = (
        select(
            User.id.label("id"),
            User.nickname,
            User.avatar_url,
            Binding.id.label("binding_id"),
            Binding.status
        )
        .join(Binding, Binding.patient_user_id == User.id)
        .where(
            Binding.doctor_user_id == doctor_user_id,
            Binding.status.in_([BindingStatus.pending, BindingStatus.accepted])
        )
    )
    result = await db.execute(stmt)
    rows = result.all()  # list of Row(id=…, nickname=…, avatar_url=…, binding_id=…, status=…)

    # 转成 dict 并验证到 Pydantic
    patients = [dict(row._asdict()) for row in rows]
    return [BoundPatientOut.model_validate(p) for p in patients]
