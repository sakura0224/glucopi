# app/schemas/insulin.py
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Literal

# 胰岛素类型 - 使用 Literal 来限制可选值
InsulinType = Literal["basal", "bolus", "mixed"]

class InsulinRecordBase(BaseModel):
    """胰岛素记录的基础模型，包含核心字段"""
    timestamp: datetime = Field(..., description="记录时间戳")
    dose: float = Field(..., gt=0, description="胰岛素剂量 (单位 U)，必须大于0")
    type: InsulinType = Field(..., description="胰岛素类型 (basal:基础, bolus:餐时, mixed:预混)")
    note: Optional[str] = Field(None, max_length=200, description="备注信息，可选，最多200字")

    @field_validator('timestamp')
    def ensure_datetime_is_aware(cls, v):
        # 确保时间戳是 aware datetime (包含时区信息) 或转换为 UTC
        # 这里假设输入可能是 naive datetime，并将其视为本地时间，然后转 UTC
        # 或者，你可以在 API 层面强制要求带时区的 ISO 格式字符串输入
        if v.tzinfo is None:
            # 如果没有时区信息，可以假设它是本地时间并转换为 UTC
            # 或者抛出错误要求客户端提供带时区的 ISO 格式
            # from app.utils.time import local_to_utc # 假设你有这样的工具函数
            # return local_to_utc(v)
            # 简单起见，这里先不强制转换，但实际项目中需要明确处理
            pass
        return v

class InsulinRecordCreate(InsulinRecordBase):
    """用于创建胰岛素记录的模型"""
    pass # 没有额外字段

# class InsulinRecordResponse(InsulinRecordBase):
#     """用于 API 响应的胰岛素记录模型"""
#     id: str = Field(..., alias="_id", description="记录的唯一ID")
#     user_id: str = Field(..., description="关联的用户ID")
#     timestamp: str = Field(..., description="记录时间戳 (ISO 8601 UTC格式字符串)") # 响应时转为字符串

#     class Config:
#         populate_by_name = True # 允许使用别名 "_id" 填充 "id"
#         json_encoders = {
#             # 虽然我们在返回前手动转换 timestamp 为 str,
#             # 保留这个 encoder 作为备用或用于其他 datetime 字段（如果未来添加）
#             datetime: lambda v: v.isoformat().replace('+00:00', 'Z') if v else None
#         }
        # Pydantic V2 中使用 serialization_alias 替代 alias in Config for response
        # 但 populate_by_name 适用于 V1/V2 的输入别名映射

# 如果使用 Pydantic V2，响应模型的别名处理可能如下：
class InsulinRecordResponse(InsulinRecordBase):
    """用于 API 响应的胰岛素记录模型"""
    id: str = Field(..., serialization_alias="_id", description="记录的唯一ID") # Use serialization_alias for output
    user_id: str = Field(..., description="关联的用户ID")
    timestamp: str = Field(..., description="记录时间戳 (ISO 8601 UTC格式字符串)") # 响应时转为字符串
    
    model_config = { # Pydantic V2 style config
        "populate_by_name": True, # Still needed if input uses _id
        "json_encoders": {
            datetime: lambda v: v.isoformat().replace('+00:00', 'Z') if v else None
        }
    }
