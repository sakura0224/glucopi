from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


# 请求体 Schema
class PredictionRequest(BaseModel):
    # user_id 不需要在这里作为请求体参数，因为我们可以从认证依赖中获取当前用户ID
    # user_id: int # 如果需要预测其他用户，可以添加，但通常预测当前用户
    predict_minutes: int = Field(...,
                                 description="希望预测未来多久后的血糖，单位分钟 (目前支持 30 或 60)")


# 预测结果单个点 Schema
class PredictedGlucosePoint(BaseModel):
    timestamp: datetime = Field(..., description="预测时间点 (ISO8601 UTC)")
    # ✅ 血糖单位现在是 mg/dL
    glucose: float = Field(..., description="预测血糖值，单位 mg/dL")


# 预测响应 Schema
class PredictionResponse(BaseModel):
    predicted_glucose: List[PredictedGlucosePoint] = Field(
        ..., description="未来血糖预测结果列表")
    message: str = "Glucose prediction successful."  # 成功时的消息
    
    # ✅ 新增字段
    used_model_patient_id: str = Field(..., description="用于预测的预训练模型对应的病人ID")
    used_prediction_setting: str = Field(..., description="预测使用的Setting (例如 'Setting 1' 或 'Setting 2')")
    historical_valid_glucose_points: int = Field(..., description="用于预测的历史数据中，实际有效的血糖点数量")
