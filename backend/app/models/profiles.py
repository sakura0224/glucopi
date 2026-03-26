# app/models/profiles.py

from sqlalchemy import Column, String, BigInteger, Date, DECIMAL, Text, ForeignKey, TIMESTAMP, func
# --- 导入 relationship，如果需要在 profiles 模型中定义指向 User 的关系 ---
from sqlalchemy.orm import relationship  # 添加 relationship 导入
# --- 修改导入结束 ---


# 确保 Base 是从正确的地方导入
from .user import Base  # 假设 Base 在 app.models.user 定义


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    user_id = Column(BigInteger, ForeignKey(
        'users.id', ondelete='CASCADE'), primary_key=True, comment="关联users表的用户ID")
    title = Column(String(64), comment="医生的职称")
    department = Column(String(128), comment="医生所属科室")
    hospital = Column(String(128), comment="医生所属医院名称")
    specialization = Column(String(128), comment="医生的专长领域")
    registration_number = Column(String(64), unique=True, comment="医生执业证书编号")
    created_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(
    ), onupdate=func.now(), comment="更新时间")

    # ✅ 不需要在这里定义 relationship 指向 User 并使用 backref="user_doctor"
    # 因为在 User 模型中定义 relationship("DoctorProfile", backref="user_doctor")
    # 已经自动在 DoctorProfile 模型上创建了 user_doctor 属性指向 User。
    # 如果你想在这里定义 user 关系，就不要用 backref 参数
    # 例如：
    # user_relation = relationship("User") # <--- 定义关系，但不指定 backref

    def __repr__(self):
        # 在 DoctorProfile 实例中访问 User 对象： self.user_doctor (因为 User 模型那边定义了 backref="user_doctor")
        return f"<DoctorProfile(user_id={self.user_id}, name={self.user_doctor.nickname if hasattr(self, 'user_doctor') and self.user_doctor else 'N/A'})>"


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    user_id = Column(BigInteger, ForeignKey(
        'users.id', ondelete='CASCADE'), primary_key=True, comment="关联users表的用户ID")
    height = Column(DECIMAL(5, 2), comment="身高 (cm)")
    weight = Column(DECIMAL(5, 2), comment="体重 (kg)")
    diagnosed_at = Column(Date, comment="糖尿病等诊断日期")
    target_glucose_min = Column(DECIMAL(5, 2), comment="目标血糖范围下限")
    target_glucose_max = Column(DECIMAL(5, 2), comment="目标血糖范围上限")
    medication_plan = Column(Text, comment="当前用药计划描述")
    created_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(
    ), onupdate=func.now(), comment="更新时间")

    # ✅ 不需要在这里定义 relationship 指向 User 并使用 backref="user_patient"
    # 因为在 User 模型中定义 relationship("PatientProfile", backref="user_patient")
    # 已经自动在 PatientProfile 模型上创建了 user_patient 属性指向 User。
    # 如果你想在这里定义 user 关系，就不要用 backref 参数
    # 例如：
    # user_relation = relationship("User") # <--- 定义关系，但不指定 backref

    def __repr__(self):
        # 在 PatientProfile 实例中访问 User 对象： self.user_patient (因为 User 模型那边定义了 backref="user_patient")
        return f"<PatientProfile(user_id={self.user_id}, name={self.user_patient.nickname if hasattr(self, 'user_patient') and self.user_patient else 'N/A'})>"
