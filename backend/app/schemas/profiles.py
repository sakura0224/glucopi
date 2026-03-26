from pydantic import BaseModel, ConfigDict, Field
from datetime import date
from typing import Optional


class DoctorProfileBase(BaseModel):
    title: Optional[str] = Field(None, description="医生的职称")
    department: Optional[str] = Field(None, description="医生所属科室")
    hospital: Optional[str] = Field(None, description="医生所属医院名称")
    specialization: Optional[str] = Field(None, description="医生的专长领域")
    registration_number: Optional[str] = Field(None, description="医生执业证书编号")


class DoctorProfileCreate(DoctorProfileBase):
    # 创建时可能需要更多必填字段
    pass


class DoctorProfileUpdate(DoctorProfileBase):
    # 更新时所有字段都是可选的
    pass


class DoctorProfileOut(DoctorProfileBase):
    # 输出时包含创建/更新时间等
    # user_id: int # 通常在 profile 输出时不需要 user_id，因为它是嵌套在 UserOut 中的
    # created_at: datetime # 如果需要，可以添加
    # updated_at: datetime # 如果需要，可以添加

    # 允许从 SQLAlchemy 模型创建 Pydantic 模型
    model_config = ConfigDict(from_attributes=True)


class PatientProfileBase(BaseModel):
    height: Optional[float] = Field(None, description="身高 (cm)")
    weight: Optional[float] = Field(None, description="体重 (kg)")
    diagnosed_at: Optional[date] = Field(None, description="糖尿病等诊断日期")
    target_glucose_min: Optional[float] = Field(None, description="目标血糖范围下限")
    target_glucose_max: Optional[float] = Field(None, description="目标血糖范围上限")
    medication_plan: Optional[str] = Field(None, description="当前用药计划描述")


class PatientProfileCreate(PatientProfileBase):
    pass


class PatientProfileUpdate(PatientProfileBase):
    # 更新时所有字段都是可选的
    pass


class PatientProfileOut(PatientProfileBase):
    # user_id: int # 同样，通常不需要
    model_config = ConfigDict(from_attributes=True)
