import enum
from sqlalchemy import Column, String, BigInteger, ForeignKey, TIMESTAMP, func, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from .user import Base  # 从 user.py 导入 Base


class BindingStatus(str, enum.Enum):
    pending = "pending"       # 申请中
    accepted = "accepted"     # 绑定成功
    rejected = "rejected"     # 对方拒绝了申请
    inactive = "inactive"     # 绑定已解除
    cancelled = "cancelled"   # 申请被发起方取消


class Binding(Base):
    __tablename__ = "bindings"
    __table_args__ = (
        UniqueConstraint('patient_user_id', 'doctor_user_id',
                         name='uniq_patient_doctor'),
    )

    id = Column(BigInteger, primary_key=True,
                autoincrement=True, comment="主键ID")
    patient_user_id = Column(BigInteger, ForeignKey(
        'users.id', ondelete='CASCADE'), nullable=False, comment="患者用户ID")
    doctor_user_id = Column(BigInteger, ForeignKey(
        'users.id', ondelete='CASCADE'), nullable=False, comment="医生用户ID")
    status = Column(Enum(BindingStatus), nullable=False,
                    default=BindingStatus.pending, comment="绑定关系状态")
    requested_at = Column(TIMESTAMP(timezone=True),
                          server_default=func.now(), comment="申请发起时间")
    accepted_at = Column(TIMESTAMP(timezone=True), comment="接受时间")
    rejected_at = Column(TIMESTAMP(timezone=True), comment="拒绝时间")
    created_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(
    ), onupdate=func.now(), comment="更新时间")

    # 定义与 User 表的关系
    # 注意这里需要 disambiguate (消歧), 因为有两个外键指向 users 表
    # 我们给关系起别名 patient 和 doctor
    patient = relationship("User", foreign_keys=[
                           patient_user_id], backref="patient_bindings")
    doctor = relationship("User", foreign_keys=[
                          doctor_user_id], backref="doctor_bindings")

    def __repr__(self):
        return f"<Binding(id={self.id}, patient_id={self.patient_user_id}, doctor_id={self.doctor_user_id}, status='{self.status}')>"
