# app/services/prediction_service.py

import os
import json
import math
import torch
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple, Union  # 导入 Union

from fastapi import Depends

# 导入核心配置
from app.core.config import settings
from motor.motor_asyncio import AsyncIOMotorDatabase

# 导入数据库模型和 Schema (如果PredictionService自身不再直接访问DB，这些导入可能不再需要，但为了_fetch_recent_user_data暂时保留)
# from app.models.user import User, UserRole
# from app.models.profiles import PatientProfile # PatientDataService 可能需要这些
# from app.db.mysql import get_db_http # PatientDataService 需要
# PredictionService 仍然直接调用 _fetch_recent_user_data
from app.db.mongo import get_mongo_db

# 导入 PatientDataService 及其依赖函数
from app.services.patient_data_service import PatientDataService, get_patient_data_service

# 导入预测工具函数和模型定义
from app.utils import prediction_utils

# 导入日志工具
from app.core.logger import logger

# 定义模型缓存结构
ModelCache = Dict[Tuple[str, int], Dict[str, Any]]

# --- 预训练病人档案数据加载 (推荐在应用启动时全局加载一次) ---
# 可以在这里定义一个变量并在 get_prediction_service 中加载
_pretrained_patient_profiles_data_cache: Optional[Dict[str,
                                                       Dict[str, Any]]] = None


def _load_pretrained_profiles(profiles_path: str) -> Dict[str, Dict[str, Any]]:
    """
    从 JSON 文件加载预训练病人档案数据。
    Args:
        profiles_path: JSON 文件完整路径。
    Returns:
        字典 {patient_id: 档案信息字典}。
    Raises:
        FileNotFoundError: 文件不存在。
        json.JSONDecodeError: JSON 格式错误。
    """
    if not os.path.exists(profiles_path):
        logger.critical(f"预训练档案文件未找到: {profiles_path}")
        raise FileNotFoundError(f"预训练档案文件未找到: {profiles_path}")

    try:
        with open(profiles_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"成功加载 {len(data)} 个预训练病人档案从 {profiles_path}")
        # 检查关键字段是否存在 (简单检查，可以在数据准备阶段做更全面的验证)
        for patient_id, profile in data.items():
            if not all(k in profile for k in ['gender', 'age_mid', 'glucose_mean', 'glucose_std']):
                logger.warning(
                    f"预训练病人 {patient_id} 档案缺失关键字段 (gender, age_mid, glucose_mean, glucose_std)。该病人可能无法用于匹配。")
        return data
    except json.JSONDecodeError as e:
        logger.critical(f"解析预训练档案 JSON 文件 {profiles_path} 错误: {e}")
        raise
    except Exception as e:
        logger.critical(f"加载预训练档案时发生意外错误: {e}")
        raise


class PredictionService:
    """
    提供血糖预测功能的业务服务。
    负责病人匹配、模型加载与缓存、数据获取与处理、模型推理。
    依赖于 PatientDataService 获取用户数据。
    """

    def __init__(
        self,
        # 接收 PatientDataService 依赖
        patient_data_service: PatientDataService,
        # 接收预训练病人档案数据
        pretrained_profiles_data: Dict[str, Dict[str, Any]],
        # 仍然保留 mongo_db 以便直接调用 _fetch_recent_user_data (如果决定 PredictionService 自己获取近期数据)
        mongo_db: AsyncIOMotorDatabase
    ):
        """
        初始化预测服务。
        Args:
            patient_data_service: 负责获取用户数据的服务实例。
            pretrained_profiles_data: 已加载的预训练病人档案数据。
            mongo_db: 异步 MongoDB 数据库对象 (用于获取近期预测数据)。
        """
        self.patient_data_service = patient_data_service
        self._pretrained_patient_profiles_data = pretrained_profiles_data
        self.mongo_db = mongo_db  # 存储 MongoDB 客户端
        self.settings = settings

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu")

        # 初始化模型缓存
        self._model_cache: ModelCache = {}

        # 预训练病人ID列表
        self._pretrained_patient_ids = list(
            self._pretrained_patient_profiles_data.keys())

        # 计算整体特征统计量
        age_mids = [p.get("age_mid") for p in self._pretrained_patient_profiles_data.values(
        ) if p.get("age_mid") is not None]
        glucose_means = [p.get("glucose_mean") for p in self._pretrained_patient_profiles_data.values(
        ) if p.get("glucose_mean") is not None]
        glucose_stds = [p.get("glucose_std") for p in self._pretrained_patient_profiles_data.values(
        ) if p.get("glucose_std") is not None]

        # 确保列表非空以避免 numpy 错误
        if not age_mids or not glucose_means or not glucose_stds:
            logger.warning("部分数值特征在预训练档案中数据不足，无法计算整体统计量。")
            # 根据你的需求处理：可以抛错，或只使用有统计量的特征进行匹配，或设置默认统计量
            # 为了简单，这里假设数据是完整的
            pass  # 生产环境需要更健壮的处理

        self._pretrained_stats = {
            "age_mean": np.mean(age_mids),
            "age_std": np.std(age_mids),  # 默认是样本标准差 ddof=0 是总体标准差，选择一种即可
            "glucose_mean_mean": np.mean(glucose_means),
            "glucose_mean_std": np.std(glucose_means),
            "glucose_std_mean": np.mean(glucose_stds),
            "glucose_std_std": np.std(glucose_stds),
        }

        # 处理标准差为 0 的情况，避免除以零
        for key in list(self._pretrained_stats.keys()):
            if key.endswith("_std"):
                if self._pretrained_stats[key] < 1e-6:  # 如果标准差非常小或为0
                    self._pretrained_stats[key] = 1.0  # 设置一个默认值，避免除以零

        logger.info(f"计算得到预训练病人整体特征统计量: {self._pretrained_stats}")

        # 定义匹配时各特征的权重 (示例值，需要调优)
        self._gender_weight = 5.0  # 性别不匹配的惩罚值
        self._age_weight = 0.5     # 年龄平方差的权重
        self._mean_weight = 10.0    # 血糖均值平方差的权重
        self._std_weight = 1     # 血糖标准差平方差的权重
        # 定义相似度阈值：如果最小距离大于此值，认为没有找到足够相似的病人
        self._similarity_threshold = 100.0  # 示例阈值，需要根据实际分数分布调整

    # ✅ 修改 _find_most_similar_patient 函数，使用更全面的匹配逻辑

    async def _find_most_similar_patient(self, user_profile: Dict[str, Any]) -> str:
        """
        根据用户档案找到最相似的预训练病人 ID。
        匹配基于性别、年龄、血糖均值和标准差。

        Args:
            user_profile: 包含 'gender', 'age', 'glucose_mean', 'glucose_std', 'valid_glucose_count' 的字典。

        Returns:
            最相似的预训练病人 ID (字符串)。
        Raises:
            ValueError: 如果用户档案不完整，预训练病人档案不可用，或匹配失败。
        """
        logger.info(f"开始为用户档案匹配相似病人: {user_profile}")

        # 检查用户档案是否包含进行匹配所需的关键数据
        user_gender = user_profile.get("gender")
        user_age = user_profile.get("age")
        user_glucose_mean = user_profile.get("glucose_mean")
        user_glucose_std = user_profile.get("glucose_std")
        user_valid_count = user_profile.get("valid_glucose_count", 0)

        # 定义进行匹配的最低数据要求
        # 例如：需要性别、年龄、均值、标准差，并且至少有2个有效血糖读数才能计算标准差
        if user_gender is None or user_age is None or user_glucose_mean is None or user_glucose_std is None or user_valid_count < 2:
            error_msg = "用户档案数据不完整或血糖读数不足，无法匹配相似病人。"
            logger.error(f"病人相似度匹配失败: {error_msg} 用户档案: {user_profile}")
            raise ValueError(error_msg)

        # 获取预训练病人档案数据
        pretrained_profiles = self._pretrained_patient_profiles_data

        if not pretrained_profiles:
            raise ValueError("没有可用于匹配的预训练病人档案数据。")

        # --- 相似度距离计算函数 (越小越相似) ---
        def calculate_distance_score(user_p: Dict[str, Any], pretrained_p: Dict[str, Any]) -> float:
            """计算用户档案与预训练病人档案之间的距离分数。"""
            score = 0.0

            # 获取用于计算的特征
            p_gender = pretrained_p.get("gender")
            p_age = pretrained_p.get("age_mid")  # 假设键名
            p_mean = pretrained_p.get("glucose_mean")
            p_std = pretrained_p.get("glucose_std")

            # 在调用前已经检查了预训练病人档案的关键字段，这里无需重复检查

            # 1. 性别距离 (示例: 不匹配惩罚)
            if user_p["gender"] != p_gender:
                score += self._gender_weight

            # 2. 年龄距离 (添加标准化)
            # 假设 self._pretrained_stats 中有 age_mean 和 age_std
            # TODO: Check if std is zero to avoid division by zero
            scaled_user_age = (user_p["age"] - self._pretrained_stats["age_mean"]) / (
                self._pretrained_stats["age_std"] if self._pretrained_stats["age_std"] > 1e-6 else 1)  # Avoid div by zero
            scaled_pretrained_age = (p_age - self._pretrained_stats["age_mean"]) / (
                self._pretrained_stats["age_std"] if self._pretrained_stats["age_std"] > 1e-6 else 1)

            score += (scaled_user_age - scaled_pretrained_age)**2 * \
                self._age_weight

            # 3. 血糖均值距离 (添加标准化)
            # 假设 self._pretrained_stats 中有 glucose_mean_mean 和 glucose_mean_std
            scaled_user_mean = (user_p["glucose_mean"] - self._pretrained_stats["glucose_mean_mean"]) / (
                self._pretrained_stats["glucose_mean_std"] if self._pretrained_stats["glucose_mean_std"] > 1e-6 else 1)
            scaled_pretrained_mean = (p_mean - self._pretrained_stats["glucose_mean_mean"]) / (
                self._pretrained_stats["glucose_mean_std"] if self._pretrained_stats["glucose_mean_std"] > 1e-6 else 1)

            score += (scaled_user_mean - scaled_pretrained_mean)**2 * \
                self._mean_weight

            # 4. 血糖标准差距离 (添加标准化)
            # 假设 self._pretrained_stats 中有 glucose_std_mean 和 glucose_std_std
            scaled_user_std = (user_p["glucose_std"] - self._pretrained_stats["glucose_std_mean"]) / (
                self._pretrained_stats["glucose_std_std"] if self._pretrained_stats["glucose_std_std"] > 1e-6 else 1)
            scaled_pretrained_std = (p_std - self._pretrained_stats["glucose_std_mean"]) / (
                self._pretrained_stats["glucose_std_std"] if self._pretrained_stats["glucose_std_std"] > 1e-6 else 1)

            score += (scaled_user_std - scaled_pretrained_std)**2 * \
                self._std_weight

            return score

        best_match_patient_id = None
        min_score = float('inf')  # 初始化最小距离为无穷大

        # 遍历所有预训练病人进行比较
        for patient_id, profile_data in pretrained_profiles.items():
            try:
                # 再次检查预训练病人档案的关键字段，跳过不完整的
                if not all(k in profile_data for k in ['gender', 'age_mid', 'glucose_mean', 'glucose_std']):
                    logger.warning(f"跳过预训练病人 {patient_id}，其档案不完整。")
                    continue

                # 计算距离分数
                score = calculate_distance_score(user_profile, profile_data)
                
                print(f"用户与预训练病人 {patient_id} 的距离分数: {score:.2f}")

                # 更新最小距离和最佳匹配病人ID
                if score < min_score:
                    min_score = score
                    best_match_patient_id = patient_id
            except Exception as e:
                logger.warning(
                    f"计算预训练病人 {patient_id} 的相似度分数时出错: {e}", exc_info=True)
                # 忽略计算错误的病人，继续下一个

        # 检查是否找到最佳匹配，并且最小距离是否在阈值范围内
        if best_match_patient_id is None or min_score >= self._similarity_threshold:
            error_msg = f"未能找到足够相似的预训练病人。最佳距离分数: {min_score:.2f} (阈值: {self._similarity_threshold})。"
            logger.warning(f"病人相似度匹配失败: {error_msg}")
            raise ValueError(error_msg)  # 抛出匹配失败的错误

        logger.info(
            f"用户匹配到预训练病人 {best_match_patient_id} (距离分数: {min_score:.2f})")

        return best_match_patient_id

    def _get_checkpoint_path(self, patient_id: str, predict_minutes: int) -> str:
        """
        根据病人ID和预测时长确定模型检查点文件路径。
        Args:
            patient_id: 预训练病人ID。
            predict_minutes: 预测时长 (30或60分钟)。
        Returns:
            检查点文件完整路径。
        Raises:
            ValueError: 如果预测时长不受支持或配置错误。
        """
        # 使用配置中定义的检查点目录
        if predict_minutes == 30:
            ckpt_dir = self.settings.SET2_30M_DIR
        elif predict_minutes == 60:
            ckpt_dir = self.settings.SET2_60M_DIR
        else:
            raise ValueError(
                f"不支持的预测时长: {predict_minutes} 分钟。仅支持 30 或 60 分钟。")

        # 检查目录是否存在 (可选，但推荐)
        if not os.path.isdir(ckpt_dir):
            logger.critical(f"模型检查点目录未找到: {ckpt_dir}")
            raise FileNotFoundError(f"模型检查点目录未找到: {ckpt_dir}")

        ckpt_path = os.path.join(ckpt_dir, f"{patient_id}.ckpt")
        return ckpt_path

    def _load_model_for_patient(self, patient_id: str, predict_minutes: int) -> Dict[str, Any]:
        """
        加载指定病人ID和预测时长的模型检查点，并缓存。
        Args:
            patient_id: 预训练病人ID。
            predict_minutes: 预测时长 (30或60分钟)。
        Returns:
            包含模型、opt、mean、std、feature_order 的字典。
        Raises:
            FileNotFoundError: 如果检查点文件不存在或目录不存在。
            AttributeError: 如果检查点中缺少 mean 或 std。
            ValueError: 配置或模型结构不匹配。
            Exception: 其他加载或模型初始化错误。
        """
        cache_key = (patient_id, predict_minutes)

        # 1. 检查缓存
        if cache_key in self._model_cache:
            logger.debug(f"缓存命中，加载模型 {patient_id}_{predict_minutes}min")
            return self._model_cache[cache_key]

        logger.info(
            f"从磁盘加载模型 {patient_id}, 预测时长 {predict_minutes}min...")

        # 2. 确定检查点路径 (此步会检查目录和文件是否存在)
        ckpt_path = self._get_checkpoint_path(patient_id, predict_minutes)
        # 文件存在性已在 _get_checkpoint_path 中检查，但可以在此处再次检查以明确逻辑
        if not os.path.exists(ckpt_path):
            raise FileNotFoundError(f"模型检查点文件未找到: {ckpt_path}")

        # 3. 加载检查点
        try:
            # weights_only=False 是为了加载整个检查点字典，包括 opt, mean, std 等
            ckpt = torch.load(
                ckpt_path, map_location=self.device, weights_only=False)
            logger.debug(f"检查点加载成功从 {ckpt_path}")
        except Exception as e:
            logger.error(f"加载检查点 {ckpt_path} 失败: {e}")
            raise

        # 4. 提取 opt, state_dict, mean, std
        opt = ckpt.get("opt")
        state_dict = ckpt.get("state_dict")
        loaded_mean = ckpt.get("mean")  # 预期 mean 在顶层
        loaded_std = ckpt.get("std")   # 预期 std 在顶层

        # 检查必要键
        if opt is None or state_dict is None or loaded_mean is None or loaded_std is None:
            missing_keys = [k for k, v in {"opt": opt, "state_dict": state_dict,
                                           "mean": loaded_mean, "std": loaded_std}.items() if v is None]
            raise AttributeError(
                f"检查点 {ckpt_path} 缺少必要键: {', '.join(missing_keys)}。请确保训练脚本保存了 opt, state_dict, mean, 和 std。")

        # 确保 mean 和 std 是 numpy 数组以便后续计算
        loaded_mean = np.array(loaded_mean, dtype=np.float32)
        loaded_std = np.array(loaded_std, dtype=np.float32)

        # 5. 确定特征顺序 (从 opt 获取 unimodal 信息)
        # opt 是从检查点加载的 Options 类的实例
        try:
            feature_order = prediction_utils.get_feature_order(opt.unimodal)
            # 验证 mean/std 的长度与特征数匹配
            if len(loaded_mean) != len(feature_order) or len(loaded_std) != len(feature_order):
                raise ValueError(
                    f"特征数量不匹配。模型 opt.unimodal={opt.unimodal} 表示有 {len(feature_order)} 个特征，但 mean/std 长度分别为 {len(loaded_mean)}/{len(loaded_std)}。")
        except Exception as e:
            logger.error(f"从 opt 解析特征顺序或验证 mean/std 失败: {e}")
            raise ValueError(f"模型检查点配置错误：{e}")

        # 6. 实例化模型
        try:
            # 使用 opt 中的参数初始化模型
            model = prediction_utils.OhioModel(
                d_in=len(feature_order),  # 输入特征数根据 feature_order 确定
                num_layers=opt.num_layers,
                d_model=opt.d_model,
                heads=opt.heads,
                d_ff=opt.d_ff,
                dropout=opt.dropout,
                attention_dropout=opt.attention_dropout,
                single_pred=opt.single_pred  # 使用 opt 中的 single_pred
            )
            model.load_state_dict(state_dict)  # 加载模型参数
            model.to(self.device)  # 移动到设备 (CPU/GPU)
            model.eval()  # 设置为评估模式 (禁用 dropout 和 batch normalization 的训练行为)
            logger.info(
                f"模型 {patient_id}_{predict_minutes}min 初始化并成功加载权重。")
        except Exception as e:
            logger.error(
                f"初始化或加载模型 {ckpt_path} 失败: {e}")
            raise

        # 7. 存储到缓存
        loaded_components = {
            'model': model,
            'opt': opt,  # 存储原始 opt 对象
            'mean': loaded_mean,  # 存储为 numpy array
            'std': loaded_std,   # 存储为 numpy array
            'feature_order': feature_order  # 存储确定的特征顺序
        }
        self._model_cache[cache_key] = loaded_components
        logger.debug(
            f"模型 {patient_id}_{predict_minutes}min 已添加到缓存。")

        return loaded_components

    async def _fetch_recent_user_data(self, user_id: int, hours: int) -> Dict[str, List[Dict]]:
        """
        从 MongoDB 获取指定用户最近指定小时的血糖、饮食、胰岛素记录。
        Args:
            user_id: 用户 ID。
            hours: 获取数据的时间范围，单位小时。
        Returns:
            包含 'glucose_records', 'diet_records', 'insulin_records' 列表的字典。
            列表中是每个记录的字典表示 (不含 MongoDB 的 _id)。
        """
        # 使用传入的 mongo_db 数据库对象
        db = self.mongo_db

        # 使用 UTC 时间获取时间范围
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # 查询条件: 属于该用户且时间戳在范围内
        # MongoDB 中的 user_id 可能需要匹配你的 User 模型 ID 的类型 (string or int)
        # 如果你的 User 模型 ID 是 int，MongoDB 中存储为 str，需要转换：str(user_id)
        query = {"user_id": str(user_id), "timestamp": {
            "$gte": start_time, "$lte": end_time}}
        sort_key = "timestamp"  # 按时间戳升序排序

        try:
            # 定义需要从每个集合中取出的字段，与 Schema 对应
            glucose_fields = ['timestamp', 'glucose', 'tag', 'note']
            diet_fields = ['timestamp', 'carbs',
                           'meal_type', 'description', 'note']
            insulin_fields = ['timestamp', 'dose',
                              'type', 'note']  # 'type' 可能是 basal/bolus

            # 获取血糖数据
            # 使用 projection 参数只获取需要的字段
            glucose_cursor = db.blood_glucose.find(
                query, {f: 1 for f in glucose_fields}).sort(sort_key, 1)
            glucose_records = await glucose_cursor.to_list(length=None)

            # 获取饮食数据
            diet_cursor = db.diet_records.find(
                query, {f: 1 for f in diet_fields}).sort(sort_key, 1)
            diet_records = await diet_cursor.to_list(length=None)

            # 获取胰岛素数据
            insulin_cursor = db.insulin_records.find(
                query, {f: 1 for f in insulin_fields}).sort(sort_key, 1)
            insulin_records = await insulin_cursor.to_list(length=None)

            # 过滤掉 MongoDB 的 _id 字段（ projection 已经处理了）并确保字段存在
            # 使用 get 确保即使字段缺失也不会出错
            # 确保字段与 prediction_utils.integrate_and_align_data 的期望一致
            def clean_records(records: List[Dict], fields: List[str]) -> List[Dict]:
                # 仅保留需要的字段，忽略 _id
                return [{field: r.get(field) for field in fields} for r in records]

            cleaned_glucose = clean_records(glucose_records, glucose_fields)
            cleaned_diet = clean_records(diet_records, diet_fields)
            cleaned_insulin = clean_records(insulin_records, insulin_fields)

            logger.debug(
                f"为用户 {user_id} 获取最近数据: {len(cleaned_glucose)} 血糖, {len(cleaned_diet)} 饮食, {len(cleaned_insulin)} 胰岛素记录。")

            return {
                "glucose_records": cleaned_glucose,
                "diet_records": cleaned_diet,
                "insulin_records": cleaned_insulin
            }

        except Exception as e:
            logger.error(
                f"从 MongoDB 获取用户 {user_id} 近期数据失败: {e}", exc_info=True)
            raise

    async def predict_user_glucose(
        self,
        user_id: int,
        predict_minutes: int,
        # future_interventions: Optional[PredictionRequest.future_interventions] = None # ✅ 如果支持Setting 1，这里需要接收这个参数
    ) -> Dict[str, Any]:  # ✅ 修改返回类型提示为 Dict[str, Any] 以包含额外信息
        """
        为指定用户预测未来血糖。

        Args:
            user_id: 要预测血糖的用户 ID。
            predict_minutes: 要预测的未来时长 (例如 30 或 60)。
            # future_interventions: 未来计划的干预数据 (如果支持 Setting 1)。

       Returns:
            包含预测结果列表和额外信息的字典。例如：
            {
                "predicted_glucose": [...],
                "used_model_patient_id": "...",
                "used_prediction_setting": "...",
                "historical_valid_glucose_points": ...,
                "message": "..."
            }

        Raises:
            ValueError: 如果数据不足、病人匹配失败、预测时长不受支持或数据处理失败。
            FileNotFoundNotFoundError: 如果找不到匹配的模型检查点或目录。
            AttributeError: 如果加载的模型检查点损坏或不完整。
            Exception: 其他未知错误。
        """
        logger.info(
            f"开始为用户 {user_id} 进行血糖预测，预测时长 {predict_minutes} 分钟。")

        # ✅ 确定预测 Setting
        # 基于 future_interventions 是否提供来判断。目前只实现 Setting 2，所以硬编码为 Setting 2。
        # 如果支持 Setting 1，这里需要根据 future_interventions 是否为 None 或空来判断
        # used_prediction_setting = "Setting 1" if future_interventions else "Setting 2"
        used_prediction_setting = "Setting 2"  # ✅ 目前只支持 Setting 2

        # 1. 获取用户档案 (含统计量) 并进行病人相似度匹配
        try:
            # 调用 PatientDataService 获取用户档案和统计量
            # PatientDataService 负责从 MySQL 获取静态档案，从 MongoDB 计算统计量
            user_profile = await self.patient_data_service.get_user_profile_for_matching(user_id)
            logger.debug(f"为用户 {user_id} 获取的档案 (含统计量): {user_profile}")

            # 调用内部方法进行病人匹配
            similar_patient_id = await self._find_most_similar_patient(user_profile)
            logger.info(
                f"用户 {user_id} 匹配到预训练病人 {similar_patient_id} 进行预测。")
        except ValueError as e:
            logger.error(
                f"病人相似度匹配失败 (或获取用户档案失败) for user {user_id}: {e}")
            # 将匹配失败的原因包装后重新抛出，供 API 端点捕获
            raise ValueError(f"无法匹配相似病人进行预测：{e}")
        except Exception as e:
            logger.error(
                f"获取用户档案或匹配病人时发生意外错误 for user {user_id}: {e}", exc_info=True)
            raise Exception(f"获取用户档案或匹配病人时发生意外错误：{e}")

        # 2. 加载模型 (含缓存)
        try:
            # 这一步会根据病人ID和预测时长加载并缓存模型
            model_components = self._load_model_for_patient(
                similar_patient_id, predict_minutes)
            model = model_components['model']
            model_opt = model_components['opt']
            model_mean = model_components['mean']
            model_std = model_components['std']
            model_feature_order = model_components['feature_order']

            # 验证配置与模型匹配
            # 从模型 opt 中获取的 predict_minutes 可能与请求的 predict_minutes 不同
            # 实际预测的时间窗口由模型决定
            expected_predict_minutes_from_model = model_opt.missing_len * \
                self.settings.PREDICTION_DATA_INTERVAL_MINUTES
            if predict_minutes != expected_predict_minutes_from_model:
                logger.warning(
                    f"请求预测时长 ({predict_minutes} 分钟) 与加载模型的预测窗口 ({expected_predict_minutes_from_model} 分钟) 不匹配。预测将覆盖 {expected_predict_minutes_from_model} 分钟。")
                # 更新预测时长为模型实际支持的时长
                actual_predict_minutes = expected_predict_minutes_from_model
            else:
                actual_predict_minutes = predict_minutes

        except (FileNotFoundError, AttributeError, ValueError, Exception) as e:
            logger.error(
                f"为病人 {similar_patient_id}, {predict_minutes}min 加载或初始化模型失败: {e}")
            # 将模型加载相关的错误重新抛出
            raise e

        # 获取模型期望的输入/预测长度点数
        input_len_points = model_opt.left_len
        missing_len_points = model_opt.missing_len  # 模型的实际预测点数
        # 从你的config中获取最小数据点要求
        min_data_points_required = self.settings.MIN_PREDICTION_POINTS_REQUIRED

        # 3. 获取用户最近数据 (用于模型输入)
        # 需要获取足够的数据来形成至少一个 input_len_points 长的窗口
        # 推荐获取稍长时间的数据，以便 prepare_inference_input 可以处理填充和对齐
        # required_hours 计算示例：模型输入长度 (点) * 每个点的时间间隔 (分钟) / 60 (分钟/小时)
        required_hours_for_input = math.ceil(
            (input_len_points * self.settings.PREDICTION_DATA_INTERVAL_MINUTES) / 60)
        # 可以加一个缓冲区，确保能获取到最新的数据点
        required_hours_with_buffer = required_hours_for_input + 1  # 例如，多取1小时数据
        if required_hours_with_buffer < 2:  # 确保至少取2小时数据
            required_hours_with_buffer = 2

        try:
            # 调用内部方法 _fetch_recent_user_data 获取原始数据 (仍然从 MongoDB)
            recent_data_raw = await self._fetch_recent_user_data(user_id, hours=required_hours_with_buffer)
        except Exception as e:
            logger.error(
                f"获取用户 {user_id} 的近期原始数据失败: {e}")
            raise  # 重新抛出数据获取错误

        # 4. 数据整合与预处理 (为模型输入做准备)
        try:
            # 整合原始数据到 DataFrame
            processed_df = prediction_utils.integrate_and_align_data(
                recent_data_raw.get("glucose_records", []),
                recent_data_raw.get("diet_records", []),
                recent_data_raw.get("insulin_records", []),
                round2min=self.settings.PREDICTION_DATA_INTERVAL_MINUTES  # 使用配置的时间间隔
            )
            logger.debug(f"数据整合对齐后形状: {processed_df.shape}")

            if processed_df.empty:
                raise ValueError(
                    "数据整合和对齐后没有找到任何数据点。")

            # 获取处理后数据的最新时间戳 (用于计算预测结果的时间戳)
            latest_timestamp_in_data = processed_df.index.max()

            # 准备模型输入 Tensor (包括填充、标准化等)
            model_input_tensor, historical_valid_glucose_points = prediction_utils.prepare_inference_input(
                processed_df=processed_df,
                input_len_points=input_len_points,
                missing_len_points=missing_len_points,  # 传递 missing_len_points 以便工具函数确定整体长度
                min_data_points_required=min_data_points_required,
                standardization_mean=model_mean.tolist(),  # 转换为 list 给工具函数
                standardization_std=model_std.tolist(),   # 转换为 list 给工具函数
                feature_order=model_feature_order
                # 如果支持 Setting 1，还需要传递 future_interventions 给 prepare_inference_input
                # future_interventions=future_interventions
            )
            logger.debug(
                f"模型输入 Tensor 准备完成，形状: {model_input_tensor.shape}")
            logger.debug(
                f"插值前的历史有效血糖点数: {historical_valid_glucose_points}")

        except ValueError as e:
            logger.error(
                f"数据预处理失败 for user {user_id}: {e}")
            # 转换为更友好的错误信息
            raise ValueError(f"无法准备预测所需数据：{e}")
        except Exception as e:
            logger.error(
                f"数据预处理时发生意外错误 for user {user_id}: {e}", exc_info=True)
            raise ValueError(f"数据处理时发生意外错误：{e}")

        # 5. 执行模型推理
        try:
            with torch.no_grad():  # 推理时禁用梯度计算
                # 将输入 Tensor 移动到模型所在的设备
                model_input_tensor = model_input_tensor.to(self.device)
                # 执行模型前向传播
                predicted_output_tensor = model(
                    model_input_tensor, input_len=input_len_points)
                # 预测输出 Tensor 形状通常是 (batch_size, total_len, output_features)
                # 这里 batch_size 是 1
            logger.debug(
                f"模型推理完成。输出 Tensor 形状: {predicted_output_tensor.shape}")

        except Exception as e:
            logger.error(f"模型推理失败 for user {user_id}: {e}", exc_info=True)
            raise Exception(f"模型推理时发生错误：{e}")

        # 6. 提取并反标准化预测结果
        # 我们需要提取预测的未来 missing_len_points 个时间步的血糖值
        # 这些值位于 predicted_output_tensor 的形状 (1, total_len, len(predict_channels)) 中
        # 具体位置是 predicted_output_tensor[:, input_len_points:, self.predict_channels]
        # 因为 single_pred=True (通常)，self.predict_channels = [0]，所以取 output[:, input_len_points:, 0]
        # 形状 (1, missing_len_points, 1) -> (missing_len_points,) after squeeze()
        if not model.single_pred:
            logger.warning(
                "加载的模型不是 single_pred。仅提取第一个预测通道 (血糖)。")

        # 提取预测的未来 missing_len_points 个点，第一个通道
        # predicted_glucose_standardized 形状为 (missing_len_points,)
        predicted_glucose_standardized = predicted_output_tensor[0, input_len_points:, 0].squeeze(
        )

        # 反标准化血糖值到 mg/dL (或你的原始数据单位)
        # 假设模型输出的是标准化后的原始单位 (mg/dL) 的预测
        # prediction_utils.denormalize_glucose 使用 mean 和 std 进行反标准化
        predicted_glucose_raw = prediction_utils.denormalize_glucose(
            predicted_glucose_standardized,
            standardization_mean=model_mean.tolist(),  # 转换为 list
            standardization_std=model_std.tolist(),     # 转换为 list
            feature_order=model_feature_order  # 传递 feature_order 以找到血糖的索引
        )
        # 确保结果是 numpy 数组 (如果来自 torch tensor)
        if isinstance(predicted_glucose_raw, torch.Tensor):
            predicted_glucose_raw = predicted_glucose_raw.cpu().numpy()

        logger.debug(
            f"反标准化后的预测血糖值 (原始单位): {predicted_glucose_raw}")

        # 7. 格式化输出结果
        prediction_results_list = []  # 用于 predicted_glucose 字段的列表
        # 计算预测结果对应的时间戳
        round2min = self.settings.PREDICTION_DATA_INTERVAL_MINUTES
        # 预测时间戳从最新数据时间戳的下一个间隔开始
        # 例如，如果最新数据是 00:15，间隔 5 分钟，下一个时间戳是 00:20
        # 使用 pandas Timestamp 的 round 方法确保精确到分钟
        if isinstance(latest_timestamp_in_data, pd.Timestamp):
            # 找到下一个间隔的时间戳
            # latest_timestamp_in_data - timedelta(minutes=latest_timestamp_in_data.minute % round2min) + timedelta(minutes=round2min)
            # 更简单：找到最近的间隔，然后加一个间隔
            start_pred_timestamp = latest_timestamp_in_data.ceil(
                f'{round2min}min')
            if start_pred_timestamp <= latest_timestamp_in_data:
                start_pred_timestamp += timedelta(minutes=round2min)
            start_pred_timestamp = start_pred_timestamp.to_pydatetime()  # 转回 datetime 对象
        else:
            # 如果 latest_timestamp_in_data 不是 pandas Timestamp (尽管 align_data 返回的是)
            # 或者处理 None 情况 (数据为空时上面已抛错，这里假设非空)
            # Fallback 简单计算
            start_pred_timestamp = latest_timestamp_in_data + \
                timedelta(minutes=round2min)

        # 确保预测结果数量与 missing_len_points 匹配 (理论上应该匹配)
        if len(predicted_glucose_raw) != missing_len_points:
            logger.error(
                f"预测值数量 ({len(predicted_glucose_raw)}) 与模型预期的预测点数 ({missing_len_points}) 不匹配。")
            # 可以选择截断或填充，这里选择使用实际预测结果数量

        for i in range(len(predicted_glucose_raw)):
            # 计算当前预测值对应的时间戳
            predicted_timestamp = start_pred_timestamp + \
                timedelta(minutes=i * round2min)
            # 确保血糖值是 float 类型，四舍五入到小数点后两位
            predicted_glucose_value = round(float(predicted_glucose_raw[i]), 2)

            prediction_results_list.append({
                # 返回 UTC 时间戳
                "timestamp": predicted_timestamp,  # 假设时间戳是 datetime 对象
                "glucose": predicted_glucose_value
            })

        logger.info(
            f"用户 {user_id} 血糖预测完成。使用病人: {similar_patient_id}, 历史有效点数: {historical_valid_glucose_points}")
        final_result_dict = {
            "predicted_glucose": prediction_results_list,
            "used_model_patient_id": str(similar_patient_id),  # 确保是字符串
            "used_prediction_setting": used_prediction_setting,
            "historical_valid_glucose_points": historical_valid_glucose_points,
            "message": "血糖预测成功。"
        }

        # 返回符合 PredictionResponse Schema 的字典
        return final_result_dict

# ----------------------------------------------------------------------
# 依赖注入提供者 (Dependency Provider)
# ----------------------------------------------------------------------


_prediction_service_instance: Optional[PredictionService] = None


async def get_prediction_service(
    # PredictionService 依赖于 PatientDataService, 预训练档案数据, 和 MongoDB (用于获取近期数据)
    patient_data_service: PatientDataService = Depends(
        get_patient_data_service),  # PatientDataService 依赖于 DBs
    # PredictionService 直接依赖 MongoDB 获取近期数据
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db)
) -> PredictionService:
    """
    提供 PredictionService 实例的 FastAPI 依赖。使用单例模式。
    负责加载预训练病人档案并创建 PredictionService 实例。
    """
    global _prediction_service_instance
    global _pretrained_patient_profiles_data_cache

    # 1. 加载预训练病人档案 (只加载一次)
    if _pretrained_patient_profiles_data_cache is None:
        # ✅ 使用 settings 中定义的路径
        pretrained_profiles_path = settings.PRETRAINED_PROFILES_PATH  # 假设你在 settings 中添加了此配置
        if not pretrained_profiles_path:
            logger.critical(
                "未配置预训练病人档案文件路径 (settings.PRETRAINED_PROFILES_PATH)。")
            raise ValueError("预训练病人档案文件路径未配置。")

        try:
            _pretrained_patient_profiles_data_cache = _load_pretrained_profiles(
                pretrained_profiles_path)
        except Exception:  # 捕获所有加载错误，并让服务创建失败
            # 错误已经在 _load_pretrained_profiles 中记录
            raise  # 重新抛出以便调用方 (如 FastAPI lifespan) 捕获

    # 2. 创建 PredictionService 实例 (单例)
    if _prediction_service_instance is None:
        # 第一次请求或应用启动时创建服务实例
        try:
            _prediction_service_instance = PredictionService(
                patient_data_service=patient_data_service,  # 注入依赖
                pretrained_profiles_data=_pretrained_patient_profiles_data_cache,  # 注入加载的数据
                mongo_db=mongo_db  # 注入 MongoDB
            )
            logger.info("PredictionService 实例创建成功。")
        except Exception as e:
            # 记录创建服务的错误
            logger.critical(
                f"创建 PredictionService 实例失败: {e}", exc_info=True)
            # 抛出异常，阻止应用继续启动或处理请求
            raise

    # 每次请求都返回同一个实例
    return _prediction_service_instance
