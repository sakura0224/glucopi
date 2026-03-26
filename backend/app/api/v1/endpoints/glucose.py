from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from app.dependencies.auth import get_current_user, get_optional_user
from app.db.mongo import mongo_db
from app.schemas.glucose import GlucoseRecordCreate, GlucoseRecordResponse
from app.models.user import User
from app.utils.chart import group_by_hour_with_fixed
from app.utils.time import to_utc, to_iso_utc, parse_local_date_as_utc, get_today_range_utc
import calendar
import pytz

router = APIRouter()
glucose_collection = mongo_db["blood_glucose"]


@router.get("/checkToday", summary="检查今天是否有血糖记录")
async def check_today_glucose(user: User = Depends(get_current_user())):
    start_utc, end_utc = get_today_range_utc()

    query = {
        "user_id": str(user.id),
        "timestamp": {"$gte": start_utc, "$lt": end_utc}
    }

    count = await glucose_collection.count_documents(query)
    return {"recorded": count > 0}


# 添加血糖记录，已废弃
@router.post("/", summary="添加血糖记录")
async def add_glucose_record(data: GlucoseRecordCreate, user: User = Depends(get_current_user())):
    record = data.model_dump()
    record["user_id"] = str(user.id)
    result = await glucose_collection.insert_one(record)
    record["_id"] = str(result.inserted_id)
    record["timestamp"] = to_iso_utc(record["timestamp"])
    return GlucoseRecordResponse(**record)


# 血糖趋势图接口（按日/周/月/半年/年）
@router.get("/trend", summary="获取血糖趋势")
async def get_glucose_trend(
    tab: str,
    date: str,
    user_id: Optional[int] = Query(None, description="可选，直接指定要查询的用户 ID"),
    # 如果你希望即使不传 token 也不报 401，就用 get_optional_user；否则直接用 get_current_user
    current_user: Optional[User] = Depends(get_optional_user),
):
    if user_id:
        print(f"get_paged_glucose_records: user_id={user_id}")
        uid = str(user_id)
    elif current_user:
        print(f"get_paged_glucose_records: current_user={current_user.id}")
        uid = str(current_user.id)
    else:
        # 既没传 user_id，又没登录
        raise HTTPException(status_code=401, detail="未提供 user_id，也未登录")

    local = pytz.timezone("Asia/Shanghai")
    base = parse_local_date_as_utc(date)  # date 是 yyyy-MM-dd，转为 UTC 0:00

    query = {"user_id": uid}

    # 日视图：按小时聚合
    if tab == "day":
        start = base
        end = start + timedelta(days=1)
        query["timestamp"] = {"$gte": start, "$lt": end}
        data = await glucose_collection.find(query).to_list(None)
        xAxis, result = group_by_hour_with_fixed(data)
        date_range = date

    else:
        bj = pytz.timezone("Asia/Shanghai")

        if tab == "week":
            start_bj = base.astimezone(
                bj) - timedelta(days=base.astimezone(bj).weekday())
            end_bj = start_bj + timedelta(days=7)
            xAxis = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            ranges_bj = [(start_bj + timedelta(days=i), start_bj +
                          timedelta(days=i+1)) for i in range(7)]

        elif tab == "month":
            start_bj = base.astimezone(bj).replace(day=1)
            last_day = calendar.monthrange(start_bj.year, start_bj.month)[1]
            end_bj = start_bj.replace(day=last_day)
            date_list = [start_bj + timedelta(days=i)
                         for i in range((end_bj - start_bj).days + 1)]
            mondays = [d for d in date_list if d.weekday() == 0]
            axis_dt = [start_bj] + mondays + \
                ([end_bj] if not mondays or mondays[-1] < end_bj else [])
            xAxis = [f"{d.month}-{d.day}" for d in axis_dt]
            ranges_bj = [(axis_dt[i], axis_dt[i+1])
                         for i in range(len(axis_dt)-1)]

        elif tab == "6months":
            base_bj = base.astimezone(bj)
            months = [(base_bj - relativedelta(months=i)).replace(day=1)
                      for i in range(5, -1, -1)]
            ranges_bj = [(m, m + relativedelta(months=1)) for m in months]
            xAxis = [f"{m.month}月" for m in months]

        elif tab == "year":
            base_bj = base.astimezone(bj)
            months = [(base_bj - relativedelta(months=i)).replace(day=1)
                      for i in range(11, -1, -2)]
            ranges_bj = [(m, m + relativedelta(months=2)) for m in months]
            xAxis = [f"{m.month}月" for m in months]

        else:
            return {"code": 400, "message": "invalid tab"}

        start = ranges_bj[0][0].astimezone(pytz.utc)
        end = ranges_bj[-1][1].astimezone(pytz.utc)
        query["timestamp"] = {"$gte": start, "$lt": end}
        data = await glucose_collection.find(query).to_list(None)

        # 聚合计算（支持“填补”功能）
        result = []
        today_bj = datetime.now(pytz.timezone("Asia/Shanghai")).date()
        for s_bj, e_bj in ranges_bj:
            bucket = []
            for d in data:
                ts = to_utc(d["timestamp"]).astimezone(bj)
                if s_bj <= ts < e_bj:
                    bucket.append(d["glucose"])

            # 判断这段时间是否是“未来”
            if s_bj.date() > today_bj:
                result.append(None)  # 未来数据，设为 null
            elif bucket:
                avg = round(sum(bucket) / len(bucket), 1)
                result.append(avg)
            else:
                result.append(None)  # 没数据，但不是未来，也显示 null

        date_range = f"{ranges_bj[0][0].strftime('%Y-%m-%d')} ~ {ranges_bj[-1][1].strftime('%Y-%m-%d')}"

    return {
        "code": 200,
        "data": {
            "xAxis": xAxis,
            "series": result,
            "dateRange": date_range
        }
    }


# 分页获取血糖记录（支持标签过滤与排序）
@router.get("/getPagedBloodRecords", summary="分页获取血糖记录")
async def get_paged_glucose_records(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1),
    tag: str = Query("all"),
    sort: str = Query("time_desc"),
    user_id: Optional[int] = Query(None, description="可选，直接指定要查询的用户 ID"),
    # 如果你希望即使不传 token 也不报 401，就用 get_optional_user；否则直接用 get_current_user
    current_user: Optional[User] = Depends(get_optional_user),
):
    if user_id:
        print(f"get_paged_glucose_records: user_id={user_id}")
        uid = str(user_id)
    elif current_user:
        print(f"get_paged_glucose_records: current_user={current_user.id}")
        uid = str(current_user.id)
    else:
        # 既没传 user_id，又没登录
        raise HTTPException(status_code=401, detail="未提供 user_id，也未登录")

    query = {"user_id": uid}
    if tag != "all":
        query["tag"] = tag

    sort_map = {
        "time_asc": ("timestamp", 1),
        "time_desc": ("timestamp", -1),
        "glucose_asc": ("glucose", 1),
        "glucose_desc": ("glucose", -1),
    }
    sort_field, sort_order = sort_map.get(sort, ("timestamp", -1))

    total = await glucose_collection.count_documents(query)
    cursor = (
        glucose_collection.find(query)
        .sort(sort_field, sort_order)
        .skip((page - 1) * size)
        .limit(size)
    )
    records = await cursor.to_list(length=size)

    for r in records:
        r["_id"] = str(r["_id"])
        if "timestamp" in r:
            r["timestamp"] = to_iso_utc(r["timestamp"])  # 返回统一 ISO 格式

    return {
        "total": total,
        "records": records
    }
