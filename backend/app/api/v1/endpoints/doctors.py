from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.mysql import get_db_http  # 导入数据库会话
from app.dependencies.auth import get_current_user
from app.models import User  # 导入 User 模型
from app.schemas.bindings import DoctorSearchItem  # 导入 DoctorSearchItem Schema
from app.services import binding_service  # 导入 binding_service (搜索逻辑放在这里)

router = APIRouter()


@router.get(
    "/search",
    response_model=List[DoctorSearchItem],  # 返回 DoctorSearchItem 列表
    summary="搜索医生"
)
async def search_doctors_endpoint(
    keyword: str = Query(..., min_length=1, description="搜索关键词 (医生姓名、科室、医院等)"),
    current_user: User = Depends(get_current_user(
        required_role="patient")),  # 确保当前用户是患者，搜索通常是患者需求
    db: AsyncSession = Depends(get_db_http)
):
    """
    根据关键词搜索医生，并返回当前患者用户与搜索结果医生的绑定状态。
    只有患者用户可以访问此接口。
    """
    # 调用服务层函数执行搜索
    search_results_data = await binding_service.search_doctors(
        db=db,
        keyword=keyword,
        current_user_id=current_user.id  # 传递当前用户ID以检查绑定状态
    )
    # Pydantic 会将字典列表转换为 DoctorSearchItem 模型列表
    return search_results_data

# TODO: 根据需要添加其他医生相关的端点，例如获取单个医生详情（不含绑定状态）
# @router.get("/{doctor_user_id}", response_model=schemas.profiles.DoctorProfileOut, summary="获取医生档案详情")
# async def get_doctor_profile(doctor_user_id: int, db: AsyncSession = Depends(get_db_http)): ...
