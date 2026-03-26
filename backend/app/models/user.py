from sqlalchemy import Column, String, BigInteger, Enum, Date, UniqueConstraint, TIMESTAMP, func
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship # 导入 relationship
import enum

# 确保 Base 在这里定义或从您的数据库初始化文件导入
Base = declarative_base()

class UserRole(str, enum.Enum):
    patient = "patient"
    doctor = "doctor"
    ai_assistant = "ai_assistant"

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("openid", name="uniq_openid"),
        UniqueConstraint("phone", name="uniq_phone"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    openid = Column(String(64), nullable=False, comment="微信 openid")
    unionid = Column(String(64), nullable=True, comment="微信 unionid")
    nickname = Column(String(64), nullable=True, comment="用户昵称")
    gender = Column(TINYINT(1), default=0, nullable=True, comment="性别（0未知 1男 2女）")
    avatar_url = Column(String(255), nullable=True, comment="头像链接")
    birthday = Column(Date, nullable=True, comment="出生日期")
    phone = Column(String(20), nullable=True, unique=True, comment="手机号")
    role = Column(Enum(UserRole), default=UserRole.patient, nullable=False, comment="用户角色")

    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, comment="创建时间"
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间"
    )

    # ✅ 修改 backref 名称，避免冲突
    # PatientProfile 模型将在 models/profiles.py 中定义
    patient_profile = relationship("PatientProfile", backref="user_patient", uselist=False, cascade="all, delete-orphan") # <-- 改为 user_patient
    # DoctorProfile 模型将在 models/profiles.py 中定义
    doctor_profile = relationship("DoctorProfile", backref="user_doctor", uselist=False, cascade="all, delete-orphan") # <-- 改为 user_doctor


    # Binding 模型 backref 不在 User 模型，无需修改这里

    def __repr__(self):
        return f"<User(id={self.id}, nickname='{self.nickname}', role='{self.role}')>"