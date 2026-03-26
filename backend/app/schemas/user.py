from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List  # 导入 List
from datetime import date, datetime

# 从 app.models.user 导入 UserRole 枚举
from app.models.user import UserRole

# 从 app.schemas.profiles 导入 Profile Schema
# 假设 app/schemas/profiles.py 中定义了 PatientProfileOut 和 DoctorProfileOut
try:
    from app.schemas.profiles import PatientProfileOut, DoctorProfileOut
except ImportError:
    # 提供一个占位符，以防 profiles.py 还没创建，但实际使用时必须存在并正确导入
    class PatientProfileOut(BaseModel):
        pass

    class DoctorProfileOut(BaseModel):
        pass


# 用于 API 响应用户基本信息（如果需要一个不含档案的简化 Schema）
class UserProfileResponse(BaseModel):
    id: int = Field(..., description="用户ID")  # 使用 id
    phone: Optional[str] = None
    nickname: Optional[str] = None
    gender: Optional[int] = Field(None, description="性别：0未知 1男 2女")
    avatar_url: Optional[str] = None
    birthday: Optional[date] = None
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


# 用于更新用户基本信息的请求体 (PUT /api/v1/user/profile)
class UserUpdate(BaseModel):
    nickname: Optional[str] = Field(None, description="用户昵称")
    gender: Optional[int] = Field(None, ge=0, le=2, description="性别：0未知 1男 2女")
    avatar_url: Optional[str] = Field(None, description="头像链接")
    birthday: Optional[date] = Field(None, description="出生日期")
    # 注意：phone 和 role 通常不在这里更新

    # 尽管是请求体，from_attributes 有时也方便内部转换
    model_config = ConfigDict(from_attributes=True)


# 用于 API 响应用户完整信息（包含档案）(GET /api/v1/user/me, PUT /api/v1/user/profile 返回)
class UserOut(BaseModel):
    id: int = Field(..., description="主键")
    openid: str
    unionid: Optional[str] = None
    nickname: Optional[str] = None
    gender: Optional[int] = Field(None, description="性别（0未知 1男 2女）")
    avatar_url: Optional[str] = None
    birthday: Optional[date] = None
    phone: Optional[str] = None
    role: UserRole

    created_at: datetime
    updated_at: datetime

    # 嵌套 Profile Schema
    patient_profile: Optional[PatientProfileOut] = None
    doctor_profile: Optional[DoctorProfileOut] = None

    # 必须！从 SQLAlchemy Model 创建 Pydantic Schema
    model_config = ConfigDict(from_attributes=True)


# 用于用户注册的请求体
class UserCreate(BaseModel):
    # 注册时通常需要提供这些信息
    openid: str = Field(..., description="微信 openid")
    unionid: Optional[str] = Field(None, description="微信 unionid")
    nickname: Optional[str] = Field(None, description="用户昵称")
    gender: Optional[int] = Field(None, ge=0, le=2, description="性别：0未知 1男 2女")
    avatar_url: Optional[str] = Field(None, description="头像链接")
    # birthday: Optional[date] = Field(None, description="出生日期") # 注册时可能不提供生日
    phone: Optional[str] = Field(None, description="手机号")  # 如果手机号是可选注册的话
    # role: UserRole = Field(UserRole.patient, description="用户角色") # 注册时可能不让用户选择角色

    # 如果注册时需要用户提供角色
    # role: UserRole = Field(..., description="用户角色")


class UserBasicInfoOut(BaseModel):
    id: int = Field(..., description="用户ID")
    nickname: Optional[str] = Field(None, description="用户昵称")
    avatar_url: Optional[str] = Field(None, description="头像链接")
    role: UserRole = Field(..., description="用户角色")  # 包含角色，方便前端判断类型

    # 兼容从 SQLAlchemy User Model 创建
    model_config = ConfigDict(from_attributes=True)

# 用于后端内部表示从数据库获取的 User 对象
# class UserInDB(UserBase): # 可以选择保留 UserInDB，但 UserOut 已经包含了所有信息且支持 from_attributes
#     id: int = Field(..., description="主键")
#     openid: str
#     unionid: Optional[str] = None
#     created_at: datetime
#     updated_at: datetime
#     # 可以选择不包含嵌套的 profile，如果它只用于内部且不涉及 profile 加载

# 可以定义其他认证相关的 Schema，例如：
# class Token(BaseModel):
#     access_token: str
#     token_type: str = "bearer"
#     user: UserOut # 可以在 Token 中也返回用户信息

# class LoginRequest(BaseModel):
#      phone: str
#      # password: str # 或者其他认证方式如微信code等

# class WechatLoginRequest(BaseModel):
#     code: str = Field(..., description="微信登录code")
#     userInfo: Optional[dict] = Field(None, description="微信获取的用户信息") # 包含 nickname, avatarUrl, gender 等
#     # 其他可能需要传递的信息
