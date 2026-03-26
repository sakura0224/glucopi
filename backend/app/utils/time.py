# utils/time.py

from datetime import datetime, timezone, timedelta
from typing import Union, List
import pytz


# 获取当前 UTC 时间对象
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# 获取当前 UTC 的 ISO8601 字符串（标准输出）
def now_iso_utc() -> str:
    return now_utc().isoformat()


# 将 ISO 字符串或 datetime 统一解析为 tz-aware datetime（UTC）
def to_utc(dt: Union[str, datetime]) -> datetime:
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# 将 datetime 转为标准 ISO 字符串（UTC）
def to_iso_utc(dt: Union[str, datetime]) -> str:
    return to_utc(dt).isoformat()


# 将北京时间日期字符串解析为 UTC 开始时间
def parse_local_date_as_utc(date_str: str, local_tz: str = "Asia/Shanghai") -> datetime:
    tz = pytz.timezone(local_tz)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return tz.localize(dt).astimezone(timezone.utc)


# 批量处理 dict 中的时间字段
def format_time_fields(obj: dict, fields: List[str]):
    for key in fields:
        if key in obj and isinstance(obj[key], datetime):
            obj[key] = to_iso_utc(obj[key])


# 取“今天”在指定时区的 UTC 时间段
def get_today_range_utc(local_tz_str: str = "Asia/Shanghai"):
    local_tz = pytz.timezone(local_tz_str)
    now = datetime.now(local_tz)
    start_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)

    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
