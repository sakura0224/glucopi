from fastapi import APIRouter, Depends, HTTPException, status, Path  # 导入 Path
from sqlalchemy.orm import Session  # 仍然需要 Session 类型用于Depends的db类型提示
from sqlalchemy.ext.asyncio import AsyncSession  # 导入 AsyncSession 用于实际 db 参数的类型提示

from app.db.mysql import get_db_http
from app.dependencies.auth import get_current_user  # 导入依赖项
from app.models.user import User, UserRole  # 导入 User 模型和角色枚举
from app.schemas.bindings import BindingCreate, BindingOut  # 导入 Schema
from app.services import binding_service  # 导入服务


router = APIRouter()

# --- 已有：POST /request 端点 (确保是 async def) ---


@router.post(
    "/request",
    response_model=BindingOut,
    status_code=status.HTTP_201_CREATED,
    summary="患者发起绑定医生申请"
)
async def request_doctor_binding(
    binding_in: BindingCreate,  # 请求体包含 doctor_user_id
    current_user: User = Depends(get_current_user(
        required_role=UserRole.patient)),  # 确保当前用户是患者
    db: AsyncSession = Depends(get_db_http)  # 实际依赖注入提供的是 AsyncSession
):
    """
    患者向指定医生发起绑定申请。
    当前用户必须是患者。
    """
    # --- 修改这里：将 binding_in.binding_id 改为 binding_in.doctor_user_id ---
    if current_user.id == binding_in.doctor_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot request binding with yourself"
        )
    # --- 修改结束 ---

    try:
        # 调用异步服务函数处理绑定申请逻辑
        new_binding = await binding_service.request_binding(
            db=db,
            patient_user_id=current_user.id,  # 患者ID从当前用户获取
            doctor_user_id=binding_in.doctor_user_id  # 医生ID从请求体获取
        )
        return new_binding
    except ValueError as e:  # 捕获服务层抛出的业务错误
        # 这里的 ValueError 通常来自 service.request_binding
        # 例如 "Doctor not found" 或 "已存在绑定关系"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,  # 或更合适的错误码，如 409 Conflict
            detail=str(e)  # 将服务层错误信息返回给客户端
        )
    except Exception as e:
        print(f"Error requesting binding: {e}")  # 记录详细错误日志在后端
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during binding request"  # 返回给客户端的通用错误信息
        )

# --- 新增：PUT /accept/{binding_id} 端点 (医生接受申请) ---


@router.put(
    "/accept/{binding_id}",
    response_model=BindingOut,  # 返回更新后的绑定信息
    summary="医生接受绑定申请"
)
async def accept_binding(
    binding_id: int = Path(..., description="要接受的绑定申请记录ID"),  # 使用 Path 明确是路径参数
    current_user: User = Depends(get_current_user(
        required_role=UserRole.doctor)),  # 只有医生可以接受
    db: AsyncSession = Depends(get_db_http)
):
    """
    医生接受患者发起的绑定申请。
    当前用户必须是医生，且是该申请的医生方。
    """
    try:
        # 调用异步服务函数
        updated_binding = await binding_service.accept_binding_request(
            db=db,
            binding_id=binding_id,
            doctor_user_id=current_user.id  # 传入当前医生ID进行验证
        )
        return updated_binding
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,  # 400 表示请求无效或状态不符
            detail=str(e)
        )
    except Exception as e:
        print(f"Error accepting binding {binding_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during binding acceptance"
        )


# --- 新增：PUT /reject/{binding_id} 端点 (医生拒绝申请) ---
@router.put(
    "/reject/{binding_id}",
    response_model=BindingOut,  # 可以返回更新后的绑定信息
    summary="医生拒绝绑定申请"
)
async def reject_binding(
    binding_id: int = Path(..., description="要拒绝的绑定申请记录ID"),
    current_user: User = Depends(get_current_user(
        required_role=UserRole.doctor)),  # 只有医生可以拒绝
    db: AsyncSession = Depends(get_db_http)
):
    """
    医生拒绝患者发起的绑定申请。
    当前用户必须是医生，且是该申请的医生方。
    """
    try:
        # 调用异步服务函数
        updated_binding = await binding_service.reject_binding_request(
            db=db,
            binding_id=binding_id,
            doctor_user_id=current_user.id  # 传入当前医生ID进行验证
        )
        return updated_binding
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"Error rejecting binding {binding_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during binding rejection"
        )


# --- 新增：PUT /cancel/{binding_id} 端点 (患者取消申请) ---
@router.put(
    "/cancel/{binding_id}",
    response_model=BindingOut,  # 可以返回更新后的绑定信息
    summary="患者取消绑定申请"
)
async def cancel_binding(
    binding_id: int = Path(..., description="要取消的绑定申请记录ID"),
    current_user: User = Depends(get_current_user(
        required_role=UserRole.patient)),  # 只有患者可以取消
    db: AsyncSession = Depends(get_db_http)
):
    """
    患者取消自己发起的绑定申请。
    当前用户必须是患者，且是该申请的患者方。
    """
    try:
        # 调用异步服务函数
        updated_binding = await binding_service.cancel_binding_request(
            db=db,
            binding_id=binding_id,
            patient_user_id=current_user.id  # 传入当前患者ID进行验证
        )
        return updated_binding
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"Error cancelling binding {binding_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during binding cancellation"
        )


# --- 新增：DELETE /{binding_id} 端点 (解除绑定) ---
@router.delete(
    "/{binding_id}",
    status_code=status.HTTP_200_OK,  # 可以返回 200 OK 或 204 No Content
    summary="解除绑定"
)
async def deactivate_binding(
    binding_id: int = Path(..., description="要解除的绑定记录ID"),
    current_user: User = Depends(get_current_user()),  # 患者或医生都可以发起解除
    db: AsyncSession = Depends(get_db_http)
):
    """
    解除已接受的绑定关系 (将状态设为 'inactive')。
    当前用户必须是该绑定关系中的一方（患者或医生）。
    """
    try:
        # 调用异步服务函数
        result = await binding_service.deactivate_binding(
            db=db,
            binding_id=binding_id,
            user_id=current_user.id  # 传入当前用户ID进行验证
        )
        return result  # 服务层返回的是一个字典 {"message": ...}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,  # 400 表示请求无效或状态不符
            detail=str(e)
        )
    except Exception as e:
        print(f"Error deactivating binding {binding_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during binding deactivation"
        )
