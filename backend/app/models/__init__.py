# app/models/__init__.py
# from .user import User # 如果User在这个文件定义的话
from .user import User, Base # 导入 User 和 Base

from .profiles import DoctorProfile, PatientProfile
from .bindings import Binding, BindingStatus

# 在这里导入所有模型，以便在数据库创建时被 Base.metadata 发现
__all__ = [
    "User",
    "UserRole",
    "DoctorProfile",
    "PatientProfile",
    "Binding",
    "BindingStatus",
    "Base"
]