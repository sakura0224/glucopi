# app/routers/insulin.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.dependencies.auth import get_current_user, get_optional_user
from app.db.mongo import mongo_db  # 假设你的 MongoDB 实例在这个路径
from app.schemas.insulin import (
    InsulinRecordCreate,
    InsulinRecordResponse,
    InsulinType  # 导入 Literal 类型用于查询参数
)
from app.models.user import User  # 假设你的 User 模型在这个路径
from app.utils.time import to_iso_utc  # 导入时间转换工具

router = APIRouter()

# 定义 MongoDB 集合
insulin_collection = mongo_db["insulin_records"]  # 使用新的集合名称

# --- 添加胰岛素记录，已废弃 ---


@router.post(
    "/",
    response_model=InsulinRecordResponse,
    summary="添加胰岛素记录",
    status_code=status.HTTP_201_CREATED  # 指示资源创建成功
)
async def add_insulin_record(
    data: InsulinRecordCreate,
    user: User = Depends(get_current_user())
):
    """
    接收胰岛素记录数据并将其保存到数据库。

    - **timestamp**: 记录时间 (建议使用 ISO 8601 格式字符串，例如 "2023-10-27T10:30:00+08:00" 或 "2023-10-27T02:30:00Z")
    - **dose**: 胰岛素剂量 (单位 U)
    - **type**: 胰岛素类型 ("basal", "bolus", "mixed")
    - **note**: 备注 (可选)
    """
    record_dict = data.model_dump()
    record_dict["user_id"] = str(user.id)  # 关联用户 ID

    # 确保 timestamp 存储为 datetime 对象 (Pydantic 已处理转换)
    # 如果需要强制 UTC 存储，可以在这里转换:
    # record_dict["timestamp"] = ensure_utc(record_dict["timestamp"])

    try:
        result = await insulin_collection.insert_one(record_dict)
        # 查询刚插入的记录以返回完整信息，并处理 ObjectId
        created_record = await insulin_collection.find_one({"_id": result.inserted_id})

        if created_record:
            # 手动将 datetime 转换为 ISO UTC 字符串以匹配 Response Model
            created_record["timestamp"] = to_iso_utc(
                created_record["timestamp"])
            # 使用 Pydantic 模型进行验证和序列化 (包括 _id 到 id 的别名转换)
            return InsulinRecordResponse(**created_record)
        else:
            # 这种情况理论上不应该发生，但作为健壮性检查
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve the created record."
            )

    except Exception as e:
        # 更具体的错误处理会更好，例如处理数据库连接错误等
        print(f"Error adding insulin record: {e}")  # 记录错误日志
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while adding the insulin record."
        )


# --- 分页获取胰岛素记录 ---
@router.get(
    "/getPagedInsulinRecords",
    response_model=Dict[str, Any],  # 返回包含 total 和 records 的字典
    summary="分页获取胰岛素记录"
)
async def get_paged_insulin_records(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(20, ge=1, le=100, description="每页记录数，最大 100"),
    type: Optional[InsulinType] = Query(
        None, description="按胰岛素类型过滤 (basal, bolus, mixed)"),  # 使用 Optional 和 Literal
    sort: str = Query(
        "time_desc",
        description="排序方式: time_desc (时间降序), time_asc (时间升序), dose_desc (剂量降序), dose_asc (剂量升序)"
    ),
    user_id: Optional[int] = Query(None, description="可选，直接指定要查询的用户 ID"),
    # 如果你希望即使不传 token 也不报 401，就用 get_optional_user；否则直接用 get_current_user
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    分页获取当前用户的胰岛素记录，支持按类型过滤和排序。
    """
    if user_id:
        uid = str(user_id)
    elif current_user:
        uid = str(current_user.id)
    else:
        # 既没传 user_id，又没登录
        raise HTTPException(status_code=401, detail="未提供 user_id，也未登录")

    query: Dict[str, Any] = {"user_id": uid}
    if type:  # 如果 type 参数被提供且不为 None
        query["type"] = type

    sort_map = {
        "time_asc": ("timestamp", 1),
        "time_desc": ("timestamp", -1),
        "dose_asc": ("dose", 1),
        "dose_desc": ("dose", -1),
    }

    if sort not in sort_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sort parameter value."
        )

    sort_field, sort_order = sort_map[sort]

    try:
        # 计算总数
        total = await insulin_collection.count_documents(query)

        # 执行分页查询和排序
        cursor = (
            insulin_collection.find(query)
            .sort(sort_field, sort_order)
            .skip((page - 1) * size)
            .limit(size)
        )
        records_from_db = await cursor.to_list(length=size)

        # 格式化记录以匹配 InsulinRecordResponse
        response_records: List[Dict[str, Any]] = []
        for r in records_from_db:
            # 将 _id ObjectId 转换为字符串
            r["_id"] = str(r["_id"])
            # 将 timestamp datetime 对象转换为 ISO UTC 字符串
            if "timestamp" in r and isinstance(r["timestamp"], datetime):
                r["timestamp"] = to_iso_utc(r["timestamp"])
            else:
                # 处理可能的旧数据或错误数据
                r["timestamp"] = None  # 或者给一个默认值/错误提示

            # 可以选择性地用 Pydantic 模型验证每条记录，但会增加开销
            # response_records.append(InsulinRecordResponse(**r).model_dump(by_alias=True))
            response_records.append(r)  # 直接添加处理过的字典

        return {
            "total": total,
            "records": response_records
        }

    except Exception as e:
        print(f"Error fetching paged insulin records: {e}")  # Log the error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching insulin records."
        )
