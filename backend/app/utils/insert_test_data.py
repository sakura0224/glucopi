# app/utils/insert_test_data.py

# 使用方法：cd E:\graduation\backend\ 然后运行 python -m app.utils.insert_test_data

import asyncio
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import random
import pytz  # 导入时区库，用于处理UTC时间

# 导入你的 Schema 定义 (如果需要验证格式)
# from app.schemas.glucose import GlucoseRecordCreate
# from app.schemas.insulin import InsulinRecordBase, InsulinType
# from app.schemas.diet import DietRecordBase, MealType
# 注意：直接构建字典插入可能更简单，MongoDB会自动处理格式，
# 但如果需要严格验证，可以使用 Schema.model_dump()


async def insert_test_data(user_id: int, hours: int = 2):
    """
    生成模拟血糖、胰岛素、饮食数据并插入到 MongoDB。
    血糖数据将是非均匀分布的，模拟真实采集情况。

    Args:
        user_id: 数据所属的用户 ID。
        hours: 生成过去多少小时的数据。
    """
    # 连接 MongoDB
    client: AsyncIOMotorClient = None
    try:
        client = AsyncIOMotorClient(settings.MONGO_URI)
        db = client['glucopi']

        blood_glucose_collection = db["blood_glucose"]
        insulin_records_collection = db["insulin_records"]
        diet_records_collection = db["diet_records"]

        # --- 生成非均匀血糖数据 ---
        glucose_data = []
        now = datetime.utcnow().replace(second=0, microsecond=0)  # 当前UTC时间，秒和微秒归零
        start_time = now - timedelta(hours=hours)
        total_minutes = hours * 60

        # ✅ 修改生成血糖数据的方式：生成随机数量、随机时间戳的数据
        # 例如，过去两小时（120分钟）内，随机生成 20 到 30 个血糖点
        min_glucose_points = int(total_minutes / 10) # 假定平均每10分钟至少有一个点
        max_glucose_points = int(total_minutes / 4)  # 假定平均每4分钟最多一个点
        num_glucose_points = random.randint(min_glucose_points, max_glucose_points) # 随机数量的点

        for i in range(num_glucose_points):
            # 在时间范围内随机生成时间点
            # 时间范围是 [start_time, now]
            random_minute_offset = random.randint(0, total_minutes)
            timestamp = start_time + timedelta(minutes=random_minute_offset)

            # 模拟血糖值 (mg/dL)，可以在正常范围内或有波动
            simulated_glucose_mg_dl = random.uniform(80, 180)
            simulated_glucose_mg_dl = max(50.0, simulated_glucose_mg_dl) # 确保大于某个阈值

            glucose_data.append({
                "user_id": str(user_id),
                "timestamp": timestamp,
                "glucose": round(simulated_glucose_mg_dl, 2), # 保留两位小数
                "tag": random.choice(["fasting", "postprandial", "random"]),
                "note": f"Glucose {i+1}"
            })

        # 按照时间戳排序，虽然不影响MongoDB插入，但方便检查和理解
        glucose_data.sort(key=lambda x: x['timestamp'])


        if glucose_data:
            insert_result = await blood_glucose_collection.insert_many(glucose_data)
            print(
                f"Inserted {len(insert_result.inserted_ids)} simulated glucose records (non-uniform) for user {user_id}.")
        else:
            print(f"No glucose data generated for user {user_id}.")

        # --- 生成少量模拟胰岛素数据 (保持不变) ---
        insulin_data = []
        num_insulin_points = random.randint(2, 5)

        for _ in range(num_insulin_points):
            random_minute_offset = random.randint(0, total_minutes)
            timestamp = start_time + timedelta(minutes=random_minute_offset)
            insulin_type = random.choice(["basal", "bolus"])
            dose = random.uniform(1, 15) if insulin_type == "bolus" else random.uniform(0.5, 5)

            insulin_data.append({
                "user_id": str(user_id),
                "timestamp": timestamp,
                "dose": round(dose, 2),
                "type": insulin_type,
                "note": f"{insulin_type} dose"
            })

        if insulin_data:
            insert_result = await insulin_records_collection.insert_many(insulin_data)
            print(
                f"Inserted {len(insert_result.inserted_ids)} simulated insulin records for user {user_id}.")
        else:
            print(f"No insulin data generated for user {user_id}.")

        # --- 生成少量模拟饮食数据 (保持不变) ---
        diet_data = []
        num_diet_points = random.randint(1, 3)

        for _ in range(num_diet_points):
            random_minute_offset = random.randint(0, total_minutes)
            timestamp = start_time + timedelta(minutes=random_minute_offset)
            carbs = random.uniform(10, 100)
            meal_type = random.choice(["breakfast", "lunch", "dinner", "snack"])

            diet_data.append({
                "user_id": str(user_id),
                "timestamp": timestamp,
                "carbs": round(carbs, 2), # 保留两位小数
                "meal_type": meal_type,
                "description": "Simulated meal",
                "note": f"{meal_type}"
            })


        if diet_data:
            insert_result = await diet_records_collection.insert_many(diet_data)
            print(
                f"Inserted {len(insert_result.inserted_ids)} simulated diet records for user {user_id}.")
        else:
            print(f"No diet data generated for user {user_id}.")

    except Exception as e:
        print(f"An error occurred during data insertion: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭连接
        if client:
            client.close()


# --- 如何运行脚本 ---
if __name__ == '__main__':
    # 在这里指定要插入数据的用户 ID
    test_user_id = 1  # ✅ 替换为你想要测试的用户 ID

    # 运行异步函数
    print(f"Inserting simulated data for user ID: {test_user_id}")
    # 插入过去 2 小时数据
    # interval_minutes 参数现在只在 integrate_and_align_data 中用于对齐，不再控制数据生成间隔
    asyncio.run(insert_test_data(test_user_id, hours=2))
    print("Data insertion script finished.")