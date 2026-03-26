from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class GlucoseRecordCreate(BaseModel):
    timestamp: datetime = Field(..., description="ISO8601 时间戳, UTC, 例如 2025-04-12T08:00:00Z")
    glucose: float = Field(..., gt=0, description="血糖值，单位 mg/dL")
    tag: str = Field(..., description="标签，如 fasting/postprandial/random")
    note: Optional[str] = None


class GlucoseRecordResponse(GlucoseRecordCreate):
    id: str = Field(..., alias="_id")
    user_id: str
