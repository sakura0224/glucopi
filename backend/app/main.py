from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router

app = FastAPI(
    title="GlucoPI 控糖派 后端接口",
    description="糖尿病健康管理小程序后台",
    version="1.0.0"
)

# ✅ 允许跨域（小程序调试、Web 管理端等常用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 可以限制为 ["http://localhost:5173"] 等
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 挂载路由（如 /api/v1/auth/login）
app.include_router(api_router, prefix="/api/v1")
