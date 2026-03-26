# app/schemas/bindings.py

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional
from app.models.bindings import BindingStatus  # 从模型导入枚举


# Schemas for Binding model
class BindingBase(BaseModel):
    patient_user_id: int = Field(..., description="患者用户ID")
    doctor_user_id: int = Field(..., description="医生用户ID")
    status: BindingStatus = Field(BindingStatus.pending, description="绑定关系状态")


class BindingCreate(BaseModel):
    doctor_user_id: int = Field(..., description="要申请绑定的医生用户ID")
    # patient_user_id 由当前登录用户确定，不需要在请求体中


class BindingOut(BindingBase):
    id: int = Field(..., description="绑定记录ID")
    requested_at: datetime
    accepted_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- API 响应专用 Schemas ---

# 用于 GET /api/v1/user/doctors 响应的医生信息
class BoundDoctorOut(BaseModel):
    id: int = Field(..., description="医生用户ID")  # 注意这里是用户ID，不是绑定ID
    nickname: Optional[str] = Field(None, description="医生昵称/姓名")
    avatar_url: Optional[str] = Field(None, description="医生头像链接")
    # 包含医生档案信息
    title: Optional[str] = Field(None, description="医生的职称")
    department: Optional[str] = Field(None, description="医生所属科室")
    hospital: Optional[str] = Field(None, description="医生所属医院名称")
    specialization: Optional[str] = Field(None, description="医生的专长领域")
    # 可以选择是否包含绑定ID或其他绑定信息
    binding_id: int = Field(..., description="此医患绑定记录的ID")  # 方便后续可能的操作，比如解除绑定
    # 理论上这里应该是 accepted，但包含 status 字段更明确
    status: BindingStatus = Field(..., description="绑定关系状态")

    # 需要 from_attributes=True 来从 ORM 查询结果构建
    model_config = ConfigDict(from_attributes=True)


# 用于 GET /api/v1/doctors/search 响应的搜索结果医生信息
class DoctorSearchItem(BaseModel):
    id: int = Field(..., description="医生用户ID")
    nickname: Optional[str] = Field(None, description="医生昵称/姓名")
    avatar_url: Optional[str] = Field(None, description="医生头像链接")
    # 包含医生档案信息
    title: Optional[str] = Field(None, description="医生的职称")
    department: Optional[str] = Field(None, description="医生所属科室")
    hospital: Optional[str] = Field(None, description="医生所属医院名称")
    specialization: Optional[str] = Field(None, description="医生的专长领域")
    # 包含与当前用户的绑定状态
    binding_status: Optional[BindingStatus] = Field(
        None, description="当前用户与该医生的绑定关系状态 (如果存在)")
    # 可以选择是否包含绑定ID
    # binding_id: Optional[int] = Field(None, description="当前用户与该医生的绑定记录ID (如果存在)")

    # 需要 from_attributes=True 来从 ORM 查询结果构建
    model_config = ConfigDict(from_attributes=True)


class BoundPatientOut(BaseModel):
    id: int = Field(..., description="患者用户ID")
    nickname: str = Field(..., description="患者昵称")
    avatar_url: Optional[str] = Field(None, description="患者头像链接")
    binding_id: int = Field(..., description="本次绑定记录ID")
    status: BindingStatus = Field(...,
                                  description="绑定关系状态（pending / accepted）")
