from fastapi import APIRouter

# 导入你已有的功能模块路由
from app.api.v1.endpoints import auth, user, glucose, chat_api, insulin, diet, record, bindings, doctors, prediction
from app.api.v1.websocket import ws

api_router = APIRouter()

# 注册模块路由
api_router.include_router(auth.router, prefix="/auth", tags=["登录注册"])

# 用户模块路由
api_router.include_router(user.router, prefix="/user", tags=["用户信息"])

# 医生模块路由
api_router.include_router(doctors.router, prefix="/doctors", tags=["医生信息"])

# 绑定模块路由
api_router.include_router(bindings.router, prefix="/bindings", tags=["绑定关系"])

# 血糖模块路由
api_router.include_router(glucose.router, prefix="/glucose", tags=["血糖"])

# 胰岛素模块路由
api_router.include_router(insulin.router, prefix="/insulin", tags=["胰岛素"])

# 饮食模块路由
api_router.include_router(diet.router, prefix="/diet", tags=["饮食"])

# 记录模块路由
api_router.include_router(record.router, prefix="/record", tags=["记录"])

# 聊天模块路由
api_router.include_router(chat_api.router, prefix="/chat", tags=["聊天记录"])

# 预测模块路由
api_router.include_router(prediction.router, prefix="/prediction", tags=["预测"])

# WebSocket 聊天路由
api_router.include_router(ws.router, prefix="/ws", tags=["聊天 WebSocket"])
