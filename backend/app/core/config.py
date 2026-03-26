import os
from pydantic_settings import BaseSettings, SettingsConfigDict  # Pydantic V2
from pathlib import Path

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # 微信相关
    WX_APPID: str
    WX_SECRET: str

    # 数据库相关
    MYSQL_URI: str
    MONGO_URI: str

    # JWT相关
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7

    # LLM配置
    DEEPSEEK_API_KEY: str
    LLM_VIRTUAL_USER_ID: int
    LLM_MODEL_NAME: str
    LLM_API_BASE_URL: str
    LLM_AVATAR_URL: str = 'https://cdn.ayane.top/deepseek.png'  # LLM 头像 URL
    SYSTEM_PROMPT: str = (
        "你是一款名为“控糖派”的小程序的健康助手 AI，专注于帮助糖尿病患者和有血糖管理需求的用户。"
        "你熟悉血糖记录、趋势查看、未来血糖预测等功能，同时擅长提供饮食、运动、用药等健康建议。"
        "请始终以专业、亲切、易懂的方式回答用户的问题，帮助他们有效控制血糖、改善生活质量。"
    )

    # 聊天配置
    CHAT_HISTORY_LIMIT: int = 20  # 每次加载的历史消息数量

    # 血糖预测
    SET2_30M_DIR: str
    SET2_60M_DIR: str
    PREDICTION_INPUT_LEN_POINTS: int
    PREDICTION_MISSING_LEN_POINTS: int
    MIN_PREDICTION_POINTS_REQUIRED: int
    PREDICTION_DATA_INTERVAL_MINUTES: int
    GLUCOSE_STATS_LOOKBACK_DAYS: int = 90  # 计算血糖统计量的时间窗口

    # 预训练病人档案文件路径
    PRETRAINED_PROFILES_PATH: str = os.path.join(
        BASE_DIR, "app/core/pretrained_profiles.json")  # <-- 添加这行

    # 允许 .env 中有 Settings 类未定义的额外字段
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
