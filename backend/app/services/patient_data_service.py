from datetime import datetime, timedelta
import numpy as np
from typing import Dict, Any, Optional, Union, List
from fastapi import Depends

# 导入 SQLAlchemy 相关的类型
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

# 导入 Motor (MongoDB 异步驱动) 相关的类型
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection

# 导入配置和日志
from app.core.config import settings
from app.core.logger import logger

# 导入数据库依赖函数
from app.db.mysql import get_db_http  # 获取 MySQL AsyncSession
from app.db.mongo import get_mongo_db  # 获取 MongoDB AsyncIOMotorDatabase

# 导入 MySQL 模型
from app.models.user import User, UserRole  # 导入 User 模型
from app.models.profiles import PatientProfile  # 导入患者档案模型 (如果需要关联加载)


# 定义血糖数据的缺失值标记 (与你 CSV 示例一致)
GLUCOSE_MISSING_VALUE = -1


class PatientDataService:
    """
    提供获取用户健康档案和数据的业务服务。
    负责从 MySQL 获取静态档案，从 MongoDB 获取和计算健康数据统计量。
    """

    def __init__(
        self,
        mysql_db: AsyncSession,         # <-- 依赖于 MySQL AsyncSession
        mongo_db: AsyncIOMotorDatabase  # <-- 依赖于 MongoDB AsyncIOMotorDatabase
    ):
        """
        初始化用户数据服务。
        Args:
            mysql_db: 异步 MySQL 数据库会话。
            mongo_db: 异步 MongoDB 数据库对象。
        """
        self.mysql_db = mysql_db
        self.mongo_db = mongo_db
        self.settings = settings

        # 定义访问 MongoDB 集合的属性
        # 根据你的集合名调整
        self.glucose_readings_collection: AsyncIOMotorCollection = self.mongo_db[
            "blood_glucose"]
        # 根据你的集合名调整
        self.diet_records_collection: AsyncIOMotorCollection = self.mongo_db["diet_records"]
        # 根据你的集合名调整
        self.insulin_records_collection: AsyncIOMotorCollection = self.mongo_db[
            "insulin_records"]
        # self.users_collection_mongo: AsyncIOMotorCollection = self.mongo_db["users"] # 如果 MongoDB 也存有用户档案，但这里主要从 MySQL 获取

        # 定义计算血糖统计量的时间窗口 (例如，最近 90 天)
        self.stats_lookback_days = settings.GLUCOSE_STATS_LOOKBACK_DAYS  # 建议在 config 中定义

    async def get_user_profile_for_matching(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户用于相似度匹配的档案信息，包括 MySQL 中的静态信息和 MongoDB 中计算的血糖统计量。

        Args:
            user_id: 当前用户的 ID。

        Returns:
            包含用户档案信息的字典，包括 gender, age, glucose_mean, glucose_std, valid_glucose_count。
            如果信息缺失或数据不足，相应的字段可能为 None 或 0。
        Raises:
            ValueError: 如果无法获取用户的静态档案信息。
            Exception: 其他获取或计算过程中的错误。
        """
        logger.debug(f"开始获取用户 {user_id} 的档案信息用于匹配...")

        # 1. 从 MySQL 获取用户静态档案信息 (性别, 年龄)
        user_static_profile: Dict[str, Any] = {}
        try:
            # 使用 SQLAlchemy 从 MySQL 的 users 表查询用户
            # User 模型应该已经映射了 users 表和 id, gender, birthday 字段
            result = await self.mysql_db.execute(
                select(User).filter(User.id == user_id)
                # 如果 PatientProfile 包含年龄和性别，并且 User 模型通过 patient_profile_id 关联，
                # 你可能需要 selectinload(User.patient_profile) 并从 PatientProfile 对象获取信息
                # 但根据你的描述，年龄和性别直接在 User 表中，所以不需要 patient_profile_id 关联，直接 User 模型即可。
                # 示例中使用 User 模型获取 gender 和 birthday 来计算 age
            )
            user = result.scalars().first()

            if not user:
                logger.error(f"在 MySQL 中未找到用户 ID {user_id} 的记录。")
                raise ValueError(f"用户 ID {user_id} 未找到，无法获取档案。")

            # 计算用户年龄
            user_age: Optional[int] = None
            if user.birthday:
                today = datetime.today()
                # 计算年龄，考虑闰年
                user_age = today.year - user.birthday.year - \
                    ((today.month, today.day) <
                     (user.birthday.month, user.birthday.day))

            # 获取用户性别
            # User 模型有一个 gender 字段，假设存储的是 0, 1, 2
            user_gender_raw = user.gender  # 例如 0, 1, 2

            # 根据你的需求，可能需要将数值性别的存储转换为字符串表示，以便与预训练档案匹配
            # 或者你的预训练档案中的性别也使用数值 0/1/2
            # 假设你的预训练档案使用字符串 "Male", "Female", "Unknown"
            # 需要一个映射函数
            gender_map = {0: "Male", 1: "Female", 2: "Unknown"}
            user_gender_str = gender_map.get(user_gender_raw, "Unknown")

            # 存储获取的静态档案信息
            user_static_profile = {
                "gender": user_gender_raw,  # 例如 "Male", "Female"
                "age": user_age,           # 年龄 (整数)
                "raw_gender": user_gender_raw  # 如果需要保留原始数值
            }
            logger.debug(f"从 MySQL 获取用户 {user_id} 静态档案: {user_static_profile}")

        except ValueError:  # 捕获用户未找到的特定错误，重新抛出
            raise
        except Exception as e:
            logger.error(
                f"从 MySQL 获取用户 {user_id} 静态档案时出错: {e}", exc_info=True)
            raise Exception(f"获取用户静态档案失败：{e}")  # 抛出通用异常

        # 2. 从 MongoDB 获取用户近期血糖数据并计算统计量 (均值和标准差)
        glucose_stats: Dict[str, Union[float, str, int, None]] = {
            "glucose_mean": None,
            "glucose_std": None,
            "valid_glucose_count": 0
        }
        try:
            end_date = datetime.utcnow()  # 使用 UTC 时间
            start_date = end_date - timedelta(days=self.stats_lookback_days)

            print(f"查询时间范围为 {start_date} ~ {end_date}")

            logger.debug(
                f"获取用户 {user_id} 最近 {self.stats_lookback_days} 天的血糖数据...")

            # 查询 MongoDB 获取指定时间范围内的血糖读数
            # 确保 user_id 在 MongoDB 中存储的类型与你查询的类型一致 (例如都是字符串)
            # query_user_id = str(user_id) # 如果 MongoDB 中 user_id 是字符串
            query_user_id = str(user_id)  # 如果 MongoDB 中 user_id 是整数

            cursor = self.glucose_readings_collection.find(
                {
                    "user_id": query_user_id,
                    "timestamp": {"$gte": start_date, "$lte": end_date},
                    # 过滤掉缺失值标记 (-1) 和 None/NaN 值
                    "glucose": {"$ne": GLUCOSE_MISSING_VALUE, "$ne": None, "$exists": True}
                },
                {"_id": 0, "glucose": 1}  # 只投影 glucose 字段
            )

            # 将查询结果转换为列表
            glucose_readings = await cursor.to_list(length=None)

            # 提取血糖值
            # 再次过滤，确保值是数字类型
            glucose_values = [doc['glucose'] for doc in glucose_readings if isinstance(
                doc.get('glucose'), (int, float))]

            valid_count = len(glucose_values)
            glucose_stats["valid_glucose_count"] = valid_count

            if valid_count > 1:  # 需要至少2个点计算标准差
                # 使用 numpy 计算均值和标准差
                # .item() 将 numpy float 转换为 Python float
                glucose_stats["glucose_mean"] = np.mean(glucose_values).item()
                glucose_stats["glucose_std"] = np.std(
                    glucose_values, ddof=1).item()  # ddof=1 计算样本标准差
                logger.debug(
                    f"用户 {user_id} 血糖统计量: Mean={glucose_stats['glucose_mean']:.2f}, Std={glucose_stats['glucose_std']:.2f}, Count={valid_count}")
            elif valid_count == 1:  # 只有一个有效读数
                glucose_stats["glucose_mean"] = float(glucose_values[0])
                glucose_stats["glucose_std"] = None  # 标准差 N/A
                logger.warning(
                    f"用户 {user_id} 只有 1 个有效血糖读数。Mean={glucose_stats['glucose_mean']:.2f}, Std=N/A")
            else:  # 没有有效读数
                logger.warning(
                    f"用户 {user_id} 在最近 {self.stats_lookback_days} 天内没有有效血糖读数。")
                # 统计量保持 None 或 N/A

        except Exception as e:
            logger.error(f"计算用户 {user_id} 血糖统计量时出错: {e}", exc_info=True)
            # 如果计算失败，统计量保持为 None，继续返回档案和 None 的统计量
            # raise Exception(f"计算血糖统计量失败：{e}") # 选择是否在这里抛出

        # 3. 合并静态档案信息和血糖统计量，返回用于匹配的完整档案字典
        profile_for_matching = {
            **user_static_profile,  # 包含 gender, age
            **glucose_stats        # 包含 glucose_mean, glucose_std, valid_glucose_count
        }

        logger.info(f"获取用户 {user_id} 档案完成: {profile_for_matching}")
        return profile_for_matching


# ----------------------------------------------------------------------
# 依赖注入提供者 (Dependency Provider)
# ----------------------------------------------------------------------

_patient_data_service_instance: Optional[PatientDataService] = None

# 提供 PatientDataService 实例的依赖函数


async def get_patient_data_service(
    # PatientDataService 需要 MySQL 和 MongoDB 的依赖
    mysql_db: AsyncSession = Depends(get_db_http),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db)
) -> PatientDataService:
    """
    提供 PatientDataService 实例的 FastAPI 依赖。使用单例模式。
    """
    global _patient_data_service_instance

    if _patient_data_service_instance is None:
        # 第一次请求时创建服务实例
        try:
            _patient_data_service_instance = PatientDataService(
                mysql_db=mysql_db,  # 注入 MySQL 会话
                mongo_db=mongo_db  # 注入 MongoDB 数据库对象
            )
            logger.info("PatientDataService 实例创建成功。")
        except Exception as e:
            logger.critical(f"创建 PatientDataService 实例失败: {e}", exc_info=True)
            # 抛出异常，阻止应用继续或处理请求
            raise

    # 每次请求都返回同一个实例
    return _patient_data_service_instance
