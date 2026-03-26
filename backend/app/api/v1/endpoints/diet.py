# app/api/v1/endpoints/diet.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Dict, Any, Optional
from datetime import datetime

# 根据你的项目结构调整导入路径
from app.dependencies.auth import get_current_user, get_optional_user
from app.db.mongo import mongo_db
from app.schemas.diet import (
    DietRecordCreate,
    DietRecordResponse,
    MealType  # 导入 Literal 类型
)
from app.models.user import User
from app.utils.time import to_iso_utc  # 假设时间转换工具在这里

router = APIRouter()

# 定义 MongoDB 集合
diet_collection = mongo_db["diet_records"]  # 饮食记录集合名称

# --- 添加饮食记录，已废弃 ---


@router.post(
    "/",
    response_model=DietRecordResponse,
    summary="添加饮食记录",
    status_code=status.HTTP_201_CREATED
)
async def add_diet_record(
    data: DietRecordCreate,
    user: User = Depends(get_current_user())
):
    """
    接收饮食记录数据并保存到数据库。

    - **timestamp**: 记录时间 (建议 ISO 8601 格式)
    - **carbs**: 碳水化合物克数
    - **meal_type**: 餐次类型 ("breakfast", "lunch", "dinner", "snack")
    - **description**: 食物描述 (可选)
    - **note**: 备注 (可选)
    """
    record_dict = data.model_dump()
    record_dict["user_id"] = str(user.id)

    # 确保 timestamp 存储为 datetime 对象 (Pydantic 已处理)
    # 可选：在此处强制转换为 UTC
    # record_dict["timestamp"] = ensure_utc(record_dict["timestamp"])

    try:
        result = await diet_collection.insert_one(record_dict)
        created_record = await diet_collection.find_one({"_id": result.inserted_id})

        if created_record:
            # 手动转换 timestamp 为 ISO UTC 字符串
            created_record["timestamp"] = to_iso_utc(
                created_record["timestamp"])
            return DietRecordResponse(**created_record)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve the created diet record."
            )

    except Exception as e:
        print(f"Error adding diet record: {e}")  # 记录日志
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while adding the diet record."
        )


# --- 分页获取饮食记录 ---
@router.get(
    "/getPagedDietRecords",
    response_model=Dict[str, Any],
    summary="分页获取饮食记录"
)
async def get_paged_diet_records(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(20, ge=1, le=100, description="每页记录数，最大 100"),
    meal_type: Optional[MealType] = Query(
        None, description="按餐次类型过滤"),  # 使用 Optional 和 Literal
    sort: str = Query(
        "time_desc",
        description="排序方式: time_desc, time_asc, carbs_desc, carbs_asc"
    ),
    user_id: Optional[int] = Query(None, description="可选，直接指定要查询的用户 ID"),
    # 如果你希望即使不传 token 也不报 401，就用 get_optional_user；否则直接用 get_current_user
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    分页获取当前用户的饮食记录，支持按餐次类型过滤和排序。
    """
    if user_id:
        uid = str(user_id)
    elif current_user:
        uid = str(current_user.id)
    else:
        # 既没传 user_id，又没登录
        raise HTTPException(status_code=401, detail="未提供 user_id，也未登录")

    query: Dict[str, Any] = {"user_id": uid}
    if meal_type:
        query["meal_type"] = meal_type

    sort_map = {
        "time_asc": ("timestamp", 1),
        "time_desc": ("timestamp", -1),
        "carbs_asc": ("carbs", 1),      # 按碳水升序
        "carbs_desc": ("carbs", -1),     # 按碳水降序
    }

    if sort not in sort_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sort parameter value. Use one of: " +
            ", ".join(sort_map.keys())
        )

    sort_field, sort_order = sort_map[sort]

    try:
        total = await diet_collection.count_documents(query)

        cursor = (
            diet_collection.find(query)
            .sort(sort_field, sort_order)
            .skip((page - 1) * size)
            .limit(size)
        )
        records_from_db = await cursor.to_list(length=size)

        response_records: List[Dict[str, Any]] = []
        for r in records_from_db:
            r["_id"] = str(r["_id"])
            if "timestamp" in r and isinstance(r["timestamp"], datetime):
                r["timestamp"] = to_iso_utc(r["timestamp"])
            else:
                r["timestamp"] = None  # 或其他错误处理

            response_records.append(r)

        return {
            "total": total,
            "records": response_records
        }

    except Exception as e:
        print(f"Error fetching paged diet records: {e}")  # Log the error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching diet records."
        )
