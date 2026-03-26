from typing import List, Tuple, Dict
from datetime import datetime
import pytz


def group_by_hour_with_fixed(
    data: List[Dict],
    fixed_points: List[int] = [0, 6, 12, 18, 24],
    timezone_str: str = "Asia/Shanghai"
) -> Tuple[List[str], List[float]]:
    """
    将 UTC 时间的数据聚合到指定时区小时，并保留固定小时点位。

    :param data: 原始血糖记录列表，包含 timestamp (datetime或ISO字符串) 和 glucose 字段
    :param fixed_points: 固定展示的小时列表
    :param timezone_str: 用于转换的目标时区
    :return: (xAxis: List[str], series: List[float or None])
    """

    tz = pytz.timezone(timezone_str)
    hourly_dict = {}

    for d in data:
        # 支持字符串和 datetime 混用（保证函数健壮）
        ts_raw = d["timestamp"]
        if isinstance(ts_raw, str):
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))  # ISO -> aware datetime
        else:
            ts = ts_raw

        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=pytz.utc)  # 强制加上 UTC，避免误判

        ts_local = ts.astimezone(tz)
        hour = ts_local.hour

        if hour not in hourly_dict:
            hourly_dict[hour] = []
        hourly_dict[hour].append(d["glucose"])

    # 合并固定点与实际出现的小时
    all_hours = sorted(set(fixed_points).union(hourly_dict.keys()))

    xAxis = [f"{h}时" for h in all_hours]
    series = [
        round(sum(hourly_dict[h]) / len(hourly_dict[h]), 1)
        if h in hourly_dict else None
        for h in all_hours
    ]

    return xAxis, series
