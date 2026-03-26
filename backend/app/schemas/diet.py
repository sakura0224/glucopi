# app/schemas/diet.py
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Literal

# 定义餐次类型 - 使用 Literal 限制可选值
MealType = Literal["breakfast", "lunch", "dinner", "snack"]


class DietRecordBase(BaseModel):
    """饮食记录的基础模型"""
    timestamp: datetime = Field(..., description="记录时间戳")
    # 考虑 carbs 是否允许为 0，如果允许则用 ge=0
    carbs: float = Field(..., ge=0, description="碳水化合物含量 (克)，必须大于等于0")
    meal_type: MealType = Field(
        ..., description="餐次类型 (breakfast:早餐, lunch:午餐, dinner:晚餐, snack:加餐)")
    description: Optional[str] = Field(
        None, max_length=500, description="食物描述，可选，最多500字")
    note: Optional[str] = Field(
        None, max_length=200, description="备注信息，可选，最多200字")


class DietRecordCreate(DietRecordBase):
    """用于创建饮食记录的模型"""
    pass


class DietRecordResponse(DietRecordBase):
    """用于 API 响应的饮食记录模型"""
    id: str = Field(..., alias="_id", description="记录的唯一ID")
    user_id: str = Field(..., description="关联的用户ID")
    # 响应时转为字符串
    timestamp: str = Field(..., description="记录时间戳 (ISO 8601 UTC格式字符串)")

    # class Config:
    # populate_by_name = True  # 允许使用别名 "_id" 填充 "id"
    # json_encoders = {
    #     datetime: lambda v: v.isoformat().replace('+00:00', 'Z') if v else None
    # }
    # Pydantic V2:
    model_config = {
        "populate_by_name": True,
        "json_encoders": {datetime: lambda v: v.isoformat().replace('+00:00', 'Z') if v else None}
    }
