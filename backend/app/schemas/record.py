# app/schemas/record.py
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Literal, Optional, Any

# 假设这些类型已在对应文件中定义好
GlucoseTag = Literal["fasting", "postprandial", "random"]  # 或者直接用 Literal["fasting", "postprandial", "random"]
from .insulin import InsulinType
from .diet import MealType

class InsulinAddData(BaseModel):
    """用于组合添加接口中的胰岛素数据"""
    dose: float = Field(..., gt=0, description="胰岛素剂量")
    type: InsulinType = Field(..., description="胰岛素类型")

class DietAddData(BaseModel):
    """用于组合添加接口中的饮食数据"""
    carbs: Optional[float] = Field(None, ge=0, description="碳水化合物克数")
    meal_type: Optional[MealType] = Field(None, description="餐次类型")
    description: Optional[str] = Field(None, max_length=500, description="食物描述")

    # 使用 Pydantic V2 的 model_validator 进行模型级别的验证
    # 如果使用 Pydantic V1, 可以用 @root_validator(pre=False)
    @model_validator(mode='after')
    def check_diet_consistency(self) -> 'DietAddData':
        # 规则1: 如果 carbs > 0，则 meal_type 必须提供
        if self.carbs is not None and self.carbs > 0 and self.meal_type is None:
            raise ValueError("餐次类型 (meal_type) 在碳水值 (carbs > 0) 输入时是必需的")
        # 规则 2: 如果只提供了 meal_type 但没有提供 carbs，这可能无效 (除非允许记录0碳水的餐次?)
        # 根据你的业务逻辑决定是否需要这条规则
        # if self.carbs is None and self.meal_type is not None:
        #     raise ValueError("不应在没有碳水值的情况下提供餐次类型")
        # 规则 3: 必须至少有 carbs 或 description 中的一个
        if self.carbs is None and self.description is None:
             raise ValueError("饮食记录中必须至少包含碳水值或食物描述")
        return self

class CombinedRecordAdd(BaseModel):
    """用于接收组合记录添加请求的模型"""
    timestamp: datetime = Field(..., description="记录的统一时间戳")
    glucose: float = Field(..., gt=0, description="血糖值 (必填)")
    # 假设 GlucoseTag 是 Literal["fasting", "postprandial", "random"]
    tag: GlucoseTag = Field(..., description="血糖测量类型 (必填)")
    note: Optional[str] = Field(None, max_length=200, description="通用备注 (可选)")

    # 可选的子记录数据
    insulin: Optional[InsulinAddData] = Field(None, description="胰岛素记录数据 (可选)")
    diet: Optional[DietAddData] = Field(None, description="饮食记录数据 (可选)")

    # 可选：添加顶层验证器，例如确保至少有一个记录被提交（虽然 glucose 已是必填）