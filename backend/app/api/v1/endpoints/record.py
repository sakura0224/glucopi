# app/api/v1/endpoints/record.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

# 根据你的项目结构调整导入路径
from app.dependencies.auth import get_current_user
from app.db.mongo import mongo_db
from app.schemas.record import CombinedRecordAdd # 导入组合模型
from app.models.user import User
# 如果需要返回创建的记录 ID，可能需要导入其他 Response 模型，但这里简化处理

router = APIRouter()

# 获取各个集合的实例
glucose_collection = mongo_db["blood_glucose"]
insulin_collection = mongo_db["insulin_records"]
diet_collection = mongo_db["diet_records"]

@router.post(
    "/add",
    summary="添加组合记录 (血糖/胰岛素/饮食)",
    status_code=status.HTTP_201_CREATED,
    response_model=Dict[str, Any] # 返回一个简单的成功消息或创建的 ID 列表
)
async def add_combined_record(
    data: CombinedRecordAdd, # 使用新的组合模型
    user: User = Depends(get_current_user())
):
    """
    接收包含血糖（必填）、胰岛素（可选）、饮食（可选）的组合记录数据，
    并将它们分别存入对应的数据库集合。

    - **timestamp**: 统一的记录时间
    - **glucose**: 血糖值
    - **tag**: 血糖测量类型
    - **note**: 通用备注 (可选, 会附加到所有创建的记录上)
    - **insulin**: 包含 dose 和 type 的对象 (可选)
    - **diet**: 包含 carbs, meal_type, description 的对象 (可选)
    """
    user_id = str(user.id)
    timestamp = data.timestamp # 使用传入的统一时间戳
    common_note = data.note # 通用备注

    created_ids = {} # 用于存储创建记录的 ID (可选返回)
    errors = []      # 用于记录处理过程中的错误

    # --- 1. 处理血糖记录 (必填) ---
    glucose_record = {
        "user_id": user_id,
        "timestamp": timestamp,
        "glucose": data.glucose,
        "tag": data.tag,
    }
    if common_note:
        glucose_record["note"] = common_note

    try:
        result = await glucose_collection.insert_one(glucose_record)
        created_ids["glucose_id"] = str(result.inserted_id)
    except Exception as e:
        print(f"Error saving glucose record: {e}")
        errors.append("血糖记录保存失败")
        # 重要：由于非原子性，这里即使失败也继续尝试其他记录，或者直接抛出异常停止
        # 如果要求严格原子性，应使用 MongoDB Transactions (需要 Replica Set)
        # 这里选择继续，最后统一报告错误

    # --- 2. 处理胰岛素记录 (可选) ---
    if data.insulin:
        insulin_record = {
            "user_id": user_id,
            "timestamp": timestamp,
            "dose": data.insulin.dose,
            "type": data.insulin.type,
        }
        if common_note:
            insulin_record["note"] = common_note # 附加通用备注

        try:
            result = await insulin_collection.insert_one(insulin_record)
            created_ids["insulin_id"] = str(result.inserted_id)
        except Exception as e:
            print(f"Error saving insulin record: {e}")
            errors.append("胰岛素记录保存失败")

    # --- 3. 处理饮食记录 (可选) ---
    if data.diet:
        # 确保至少有 carbs 或 description
        if data.diet.carbs is not None or data.diet.description is not None:
            diet_record = {
                "user_id": user_id,
                "timestamp": timestamp,
            }
            if data.diet.carbs is not None:
                diet_record["carbs"] = data.diet.carbs
            if data.diet.meal_type is not None: # Pydantic 模型验证已确保 meal_type 在 carbs>0 时存在
                diet_record["meal_type"] = data.diet.meal_type
            if data.diet.description is not None:
                diet_record["description"] = data.diet.description
            if common_note:
                diet_record["note"] = common_note # 附加通用备注

            try:
                result = await diet_collection.insert_one(diet_record)
                created_ids["diet_id"] = str(result.inserted_id)
            except Exception as e:
                print(f"Error saving diet record: {e}")
                errors.append("饮食记录保存失败")
        else:
            # 这段理论上 Pydantic 验证会捕获，但作为保险
            print("Diet data provided but contains neither carbs nor description.")
            # errors.append("饮食数据无效")


    # --- 4. 处理结果和响应 ---
    if errors:
        # 如果有任何错误发生
        error_message = ", ".join(errors)
        # 根据业务逻辑决定返回什么状态码，500 表示服务器内部错误
        # 400 Bad Request 可能不太合适，因为请求格式可能正确，是存储时出错
        # 也可以选择返回 207 Multi-Status，并在响应体中详细说明哪些成功哪些失败
        # 这里简化处理，返回 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"部分记录保存失败: {error_message}. 已创建的记录ID: {created_ids}"
            # 注意：暴露 created_ids 可能不是最佳实践，取决于你的安全需求
        )
    else:
        # 所有操作都（看似）成功
        return {
            "message": "记录已成功添加",
            "created_ids": created_ids # 可以选择性返回创建的 ID
        }

    # --- 关于原子性的说明 ---
    # 上述实现不是原子性的。如果 MongoDB 配置了 Replica Set，
    # 可以使用 session.with_transaction() 来包装所有的 insert_one 调用，
    # 以确保要么所有记录都插入成功，要么在出错时全部回滚。
    # 示例 (需要调整):
    # async with await mongo_db.client.start_session() as session:
    #     async with session.with_transaction():
    #         # ... 在这里执行所有的 insert_one 操作，传入 session=session ...
    #         await glucose_collection.insert_one(glucose_record, session=session)
    #         if data.insulin:
    #             await insulin_collection.insert_one(insulin_record, session=session)
    #         if data.diet:
    #             await diet_collection.insert_one(diet_record, session=session)
