# scripts/insert_glucose_data.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta, timezone
from random import choice, uniform

MONGO_URI = "mongodb://localhost:27017"
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["glucopi"]
collection = db["blood_glucose"]

async def insert():
    user_id = "18"  # 改成你的测试用户 ID
    now = datetime.now(timezone.utc)  # 建议使用 UTC 时间（与你趋势查询一致）

    tags = ['fasting', 'postprandial', 'random']
    notes = ['调试用', '饭后1h', '睡前记录', '正常', '偏高']

    total = 120
    days_range = 365
    interval = days_range / total  # 平均间隔的天数（≈3.04天）

    docs = []
    for i in range(total):
        delta_days = i * interval
        timestamp = now - timedelta(days=days_range - delta_days)  # 均匀分布
        doc = {
            "user_id": user_id,
            "glucose": round(uniform(4.5, 9.8), 1),
            "tag": choice(tags),
            "timestamp": timestamp,
            "note": choice(notes)
        }
        docs.append(doc)

    result = await collection.insert_many(docs)
    print(f"✅ Inserted {len(result.inserted_ids)} 条血糖记录")

asyncio.run(insert())
