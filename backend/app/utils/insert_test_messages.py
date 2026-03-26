import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta, timezone
import random

# MongoDB 配置
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "glucopi"
COLLECTION_NAME = "chat_messages"

# 发送者 / 接收者 ID（务必都是 string 类型）
FROM_USER = "9"
TO_USER = "1"

# 插入的消息数量
NUM_MESSAGES = 5

# 是否设置为未读（read=False）
MARK_AS_UNREAD = True

# 内容列表（可随机选）
CONTENT_POOL = [
    "# 测试消息",
    "> 测试消息",
    "```python\nprint('Hello, World!')\n```",
    "**测试消息**",
    "$E = mc^2$",
]


async def insert_test_messages():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    base_time = datetime.now(timezone.utc)

    messages = []

    for i in range(NUM_MESSAGES):
        msg = {
            "chatId": "__".join(sorted([FROM_USER, TO_USER])),
            "from": FROM_USER,
            "to": TO_USER,
            "content": random.choice(CONTENT_POOL),
            "type": "text",
            "time": base_time - timedelta(minutes=i),
            "read": False  # 最后一条未读
        }
        messages.append(msg)

    result = await collection.insert_many(messages)
    print(f"✅ 插入成功，共 {len(result.inserted_ids)} 条消息。")


if __name__ == "__main__":
    asyncio.run(insert_test_messages())
