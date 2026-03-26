# app/api/v1/endpoints/prediction.py

from fastapi import APIRouter, Depends, HTTPException, status, Body

# 导入用户认证依赖
from app.dependencies.auth import get_current_user
from app.models.user import User  # 导入 User 模型 (用于 Depends)

# 导入预测服务
from app.schemas.prediction import PredictionRequest, PredictionResponse
from app.services.prediction_service import PredictionService, get_prediction_service

# 导入日志
from app.core.logger import logger

# --- 创建 APIRouter 实例 ---
router = APIRouter()


# --- 预测血糖端点 ---
@router.post(
    "/predict_glucose",
    response_model=PredictionResponse,
    summary="预测未来血糖",
    status_code=status.HTTP_200_OK
)
async def predict_glucose_endpoint(
    request_data: PredictionRequest,  # 请求体数据
    current_user: User = Depends(get_current_user()),  # 获取当前已认证用户
    prediction_service: PredictionService = Depends(
        get_prediction_service)  # 注入预测服务实例
):
    """
    接收用户请求，调用血糖预测服务，返回未来一段时间的血糖预测结果。
    - 需要用户认证。
    - 根据当前用户档案匹配最相似的预训练病人。
    - 加载对应的模型。
    - 获取用户最近两小时的血糖、饮食、胰岛素数据。
    - 处理数据并进行模型推理。
    - 返回预测的未来血糖值列表。
    """
    user_id = current_user.id  # 从认证依赖中获取当前用户ID
    predict_minutes = request_data.predict_minutes

    logger.info(
        f"Received prediction request for user {user_id}, predicting {predict_minutes} minutes.")

    # 校验预测时长是否支持
    if predict_minutes not in [30, 60]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported prediction duration. Only 30 or 60 minutes are supported."
        )

    try:
        # 调用 PredictionService 的核心预测方法
        # 这个方法返回一个字典，其结构已经与 PredictionResponse Schema 定义完全匹配
        service_result_dict = await prediction_service.predict_user_glucose(
            user_id=user_id,
            predict_minutes=predict_minutes
            # 如果支持 Setting 1，这里需要将 future_interventions 传递给 service
            # future_interventions = request_data.future_interventions # 从请求体获取
            # predicted_glucose_results = await prediction_service.predict_user_glucose(..., future_interventions=future_interventions)
        )

        # ✅ 直接返回 Service 返回的字典
        #    FastAPI 会根据 response_model=PredictionResponse
        #    自动对这个字典进行验证和序列化。
        return service_result_dict

    # 捕获 Service 可能抛出的特定业务异常
    except ValueError as e:
        # 例如数据不足、病人匹配失败、数据处理错误等 ValueError
        logger.warning(
            f"Prediction failed for user {user_id} due to data/matching error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,  # 数据或请求问题，用 400
            detail=f"Prediction failed: {e}"  # 返回 Service 中更友好的错误信息
        )
    except FileNotFoundError as e:
        # 模型检查点文件未找到
        logger.error(
            f"Prediction failed for user {user_id} due to model file not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # 服务器端模型问题
            detail=f"Prediction model not found: {e}"
        )
    except AttributeError as e:
        # 模型检查点损坏或不完整 (缺少 mean/std/opt/state_dict)
        logger.error(
            f"Prediction failed for user {user_id} due to incomplete model checkpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # 服务器端模型问题
            detail=f"Prediction model is corrupted or incomplete: {e}"
        )
    except Exception as e:
        # 捕获其他所有意外错误
        logger.error(
            f"An unexpected error occurred during prediction for user {user_id}: {e}", exc_info=True)  # 记录详细栈追踪
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # 服务器内部错误
            detail="An unexpected internal server error occurred during prediction."
        )
