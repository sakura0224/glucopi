# app/utils/prediction_utils.py

# 这个文件包含血糖预测所需的工具函数：模型定义、数据处理、标准化及反标准化。

import math
import torch
import torch.nn as nn
import pandas as pd
import numpy as np
import datetime
from typing import List, Dict, Any, Tuple, Optional, Union

# --- 常量 ---
DATA_INTERVAL_MINUTES = 5  # 数据时间间隔，单位分钟 (与GluPred数据集一致)
MMOL_TO_MG_DL_FACTOR = 18.018  # 血糖单位转换因子: mmol/L -> mg/dL


# ==============================================================================
# 1. 模型定义 (从 GluPred/model 复制并调整导入)
# ==============================================================================

# --------------------------------------------------------------------------
# 复制自 GluPred/model/Prenorm_TransformerEncoder.py 的完整模型定义
# --------------------------------------------------------------------------

# 位置编码函数 (为序列注入位置信息)
def positional_encoding(length, d_model):
    """ Generate the positional encoding in the raw paper.
    Returns:
        (length, d_model)
    """
    pe = torch.zeros(length, d_model)
    pos = torch.arange(length).unsqueeze(1)

    pe[:, 0::2] = torch.sin(
        pos / torch.pow(10000, torch.arange(0, d_model, step=2, dtype=torch.float32) / d_model))
    pe[:, 1::2] = torch.cos(
        pos / torch.pow(10000, torch.arange(1, d_model, step=2, dtype=torch.float32) / d_model))

    return pe


# 因果掩码函数 (防止模型看到未来的信息)
def get_past_mask(l):
    """ Generate the past mask.
    Args:
        l: int
    Returns:
        (l, l)
            Row is query, col is key. True is not accessible.
            Ex: l=5.
                [[False,  True,  True,  True,  True],
                 [False, False,  True,  True,  True],
                 [False, False, False,  True,  True],
                 [False, False, False, False,  True],
                 [False, False, False, False, False]]
    """
    return torch.triu(torch.ones((l, l)), diagonal=1).bool()


# 多头注意力模块
class MultiHeadedAttention(nn.Module):
    """ The multihead attention module, including dot-product attention.

    Adapted from https://github.com/OpenNMT/OpenNMT-py/blob/master/onmt/modules/multi_headed_attn.py
    """

    def __init__(self, n_heads, d_model, dropout=0.1):
        super(MultiHeadedAttention, self).__init__()
        assert d_model % n_heads == 0
        self.dim_per_head = d_model // n_heads
        self.d_model = d_model
        self.n_heads = n_heads

        self.linear_keys = nn.Linear(d_model, n_heads * self.dim_per_head)
        self.linear_values = nn.Linear(d_model, n_heads * self.dim_per_head)
        self.linear_query = nn.Linear(d_model, n_heads * self.dim_per_head)

        self.softmax = nn.Softmax(dim=-1)
        self.dropout = nn.Dropout(dropout)
        self.final_linear = nn.Linear(d_model, d_model)

    def forward(self, key, value, query, mask=None):
        """
        Args:
            key: (N, l_key, d_model)
            value: (N, l_key, d_model)
            query: (N, l_query, d_model)
            mask: (N, l_query, l_key)
                binary mask 1/0
        """
        batch_size = key.size(0)
        dim_per_head = self.dim_per_head
        n_heads = self.n_heads
        key_len = key.size(1)
        query_len = query.size(1)

        def shape(x):
            """Projection."""
            return x.view(batch_size, -1, n_heads, dim_per_head).transpose(1, 2)

        def unshape(x):
            """Compute context."""
            return x.transpose(1, 2).contiguous().view(batch_size, -1, n_heads * dim_per_head)

        key = self.linear_keys(key)  # (N, l_key, d_model)
        value = self.linear_values(value)  # (N, l_key, d_model)
        query = self.linear_query(query)  # (N, l_query, l_key)
        key = shape(key)  # (N, n_heads, l_key, dim_per_head)
        value = shape(value)  # (N, n_heads, l_key, dim_per_head)
        query = shape(query)  # # (N, n_heads, l_query, dim_per_head)

        query = query / math.sqrt(dim_per_head)
        query_key = torch.matmul(query, key.transpose(2, 3))
        scores = query_key
        scores = scores.float()

        if mask is not None:
            mask = mask.unsqueeze(1)
            scores = scores.masked_fill(mask, -1e18)

        # (N, n_heads, l_query, l_key)
        attn = self.softmax(scores).to(query.dtype)
        drop_attn = self.dropout(attn)

        # (N, n_heads, l_query, dim_per_head)
        context_original = torch.matmul(drop_attn, value)
        context = unshape(context_original)  # (N, l_query, d_model)
        output = self.final_linear(context)  # (N, l_query, d_model)
        attns = attn.view(batch_size, n_heads, query_len, key_len)

        return output, attns


# 位置前馈网络 (包含内部 Prenorm 和残差连接)
class PositionwiseFeedForward(nn.Module):
    """ A two layer FF with residual layer norm.
    Args:
        d_model: int
        d_ff: int
        dropout: float
    """

    def __init__(self, d_model, d_ff, dropout=0.1):
        super(PositionwiseFeedForward, self).__init__()
        self.w_1 = nn.Linear(d_model, d_ff)
        self.w_2 = nn.Linear(d_ff, d_model)
        self.layer_norm = nn.LayerNorm(d_model, eps=1e-6)
        self.dropout_1 = nn.Dropout(dropout)
        self.relu = nn.ReLU()
        self.dropout_2 = nn.Dropout(dropout)

    def forward(self, x):
        """
        Args:
            x: (N, input_len, d_model)
        Returns:
            (N, input_len, d_model)
        """
        inter = self.dropout_1(self.relu(self.w_1(self.layer_norm(x))))
        output = self.dropout_2(self.w_2(inter))
        return output + x


# Transformer 编码器层 (包含自注意力和前馈网络)
class EncoderLayer(nn.Module):
    def __init__(self, d_model, heads, d_ff, dropout, attention_dropout):
        super(EncoderLayer, self).__init__()

        self.self_attn = MultiHeadedAttention(
            heads, d_model, dropout=attention_dropout)
        self.feed_forward = PositionwiseFeedForward(d_model, d_ff, dropout)
        self.layer_norm = nn.LayerNorm(d_model, eps=1e-6)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        """
        Args:
            x: (N, l, d_model)
            mask: (N, l, l)
        Returns:
            (N, l, d_model)
        """
        input_norm = self.layer_norm(x)
        context, _ = self.self_attn(
            input_norm, input_norm, input_norm, mask=mask)
        out = self.dropout(context) + x
        return self.feed_forward(out)


# Transformer 编码器 (堆叠多个编码器层)
class Encoder(nn.Module):
    def __init__(self, num_layers, d_model, heads, d_ff, dropout, attention_dropout):
        super(Encoder, self).__init__()

        self.layers = nn.ModuleList(
            [EncoderLayer(d_model, heads, d_ff, dropout, attention_dropout)
             for _ in range(num_layers)]
        )
        self.layer_norm = nn.LayerNorm(d_model, eps=1e-6)

    def forward(self, x, mask=None):
        """
        Args:
            x: (N, l, d_model)
            mask: (N, l, l)
        Returns:
            (N, l, d_model)
        """
        x += positional_encoding(x.shape[1], x.shape[2]).to(x.device)
        out = x
        for layer in self.layers:
            out = layer(out, mask)
        out = self.layer_norm(out)

        return out.contiguous()

# --------------------------------------------------------------------------
# 复制自 GluPred/model/OhioModel.py 的完整模型定义
# --------------------------------------------------------------------------


# 完整的血糖预测模型
class OhioModel(nn.Module):
    def __init__(self, d_in, num_layers, d_model, heads, d_ff, dropout, attention_dropout, single_pred=True):
        """
        Args
            d_in: int
                num of features.
            single_pred: bool
                if True, means only predict CGM and make others known
                if False, means all channels are to be predicted
        """
        # 参数初始化，原始代码中未包含此项，但在实际使用中必须需要
        self.single_pred = single_pred
        self.d_in = d_in
        self.d_model = d_model

        super(OhioModel, self).__init__()
        if single_pred:
            predict_channels = [0]
        else:
            predict_channels = list(range(d_in))
        self.predict_channels = predict_channels
        self.encoder = Encoder(num_layers, d_model, heads,
                               d_ff, dropout, attention_dropout)
        self.emb = nn.Linear(d_in, d_model)
        self.final_linear = nn.Linear(d_model, len(predict_channels))

    def _transformer_forward(self, x):
        """
        Args:
            x: (N, l, d_in)
        Returns:
            (N, l, len(predict_channels))
        """
        x = self.emb(x)
        mask = get_past_mask(x.shape[1]).unsqueeze(
            0).expand(x.shape[0], -1, -1).to(x.device)
        out = self.final_linear(self.encoder(x, mask=mask))
        return out

    def forward(self, whole_example, input_len):
        """
        Args:
            whole_example: (N, l, d_in)
            input_len: int
        Returns:
            (N, l, d_in) where self.predict_channels on position [input_len: ] has been changed by the prediction
        """
        whole_example_clone = whole_example.clone().detach()
        total_len = whole_example_clone.shape[1]
        assert input_len < total_len

        while True:
            if input_len == total_len:
                return whole_example_clone
            x = whole_example_clone[:, :input_len, :]
            y_hat = self._transformer_forward(x)
            whole_example_clone[:, input_len,
                                self.predict_channels] = y_hat[:, -1, self.predict_channels]
            input_len += 1


# ==============================================================================
# 2. 数据处理函数 (整合 loader/linker/dataset 的部分逻辑)
# ==============================================================================

def round_minute_pandas(ts: datetime, round2min: int) -> datetime:
    """
    将 datetime 对象向下取整到指定分钟间隔。
    Args:
        ts: datetime 对象。
        round2min: 分钟间隔整数 (例如 5)。
    Returns:
        向下取整后的 datetime 对象。
    """
    # 如果时间戳带时区，转换为UTC处理以保持一致性
    if ts.tzinfo is not None:
        ts = ts.astimezone(datetime.timezone.utc)

    # 计算向下取整后的分钟数
    new_minute = (ts.minute // round2min) * round2min
    # 返回修改分钟、秒、微秒后的时间对象
    return ts.replace(minute=new_minute, second=0, microsecond=0)


def integrate_and_align_data(
    glucose_records: List[Dict],
    diet_records: List[Dict],
    insulin_records: List[Dict],
    round2min: int = DATA_INTERVAL_MINUTES
) -> pd.DataFrame:
    """
    整合血糖、饮食、胰岛素记录到单个按时间对齐的 DataFrame。

    Args:
        glucose_records: 血糖记录字典列表 (需包含 'timestamp', 'glucose'，可能还有 'tag')。
        diet_records: 饮食记录字典列表 (需包含 'timestamp', 'carbs', 可能还有 'meal_type', 'description', 'note')。
        insulin_records: 胰岛素记录字典列表 (需包含 'timestamp', 'dose', 'type', 可能还有 'note')。
        round2min: 时间戳取整分钟间隔 (默认 5)。

    Returns:
        一个带有 DatetimeIndex 的 Pandas DataFrame，包含 'glucose', 'carbs', 'basal', 'bolus' 等列。
        对齐后的缺失值表示为 NaN。
        注意：血糖单位会从 mmol/L 转换为 mg/dL。
        注意：只处理 type='basal' 和 'bolus' 的胰岛素记录。
    """
    dfs_to_merge = []  # 存储要合并的DataFrame列表

    # --- 处理血糖记录 ---
    if glucose_records:
        df_glucose = pd.DataFrame(glucose_records)
        # ✅ 重要: 将血糖单位从 mmol/L 转换为 mg/dL 以匹配GluPred数据集的可能单位
        # df_glucose['glucose'] = df_glucose['glucose'] * MMOL_TO_MG_DL_FACTOR
        df_glucose = df_glucose[['timestamp', 'glucose']]  # 只保留需要建模的列
        # 时间戳取整并按时间分组，如果同一时间多个血糖记录取平均值
        df_glucose['timestamp'] = df_glucose['timestamp'].apply(
            lambda ts: round_minute_pandas(ts, round2min))
        df_glucose = df_glucose.groupby(
            'timestamp')['glucose'].mean().reset_index()
        df_glucose = df_glucose.set_index('timestamp')  # 设置时间戳为索引
        dfs_to_merge.append(df_glucose)

    # --- 处理饮食记录 (碳水化合物) ---
    if diet_records:
        df_diet = pd.DataFrame(diet_records)
        df_diet = df_diet[['timestamp', 'carbs']]  # 只保留需要建模的列
        # 时间戳取整并按时间分组，如果同一时间多个饮食记录总和碳水化合物
        df_diet['timestamp'] = df_diet['timestamp'].apply(
            lambda ts: round_minute_pandas(ts, round2min))
        df_diet = df_diet.groupby('timestamp')['carbs'].sum().reset_index()
        df_diet = df_diet.set_index('timestamp')
        dfs_to_merge.append(df_diet)

    # --- 处理胰岛素记录 (基础胰岛素 basal 和 餐时胰岛素 bolus) ---
    # GluPred模型使用了 'basal' 和 'bolus' 特征。忽略 'mixed' 类型胰岛素。
    if insulin_records:
        df_insulin = pd.DataFrame(insulin_records)
        # 过滤出 basal 和 bolus 类型的记录
        df_basal_insulin = df_insulin[df_insulin['type'] == 'basal'][[
            'timestamp', 'dose']]
        df_bolus_insulin = df_insulin[df_insulin['type'] == 'bolus'][[
            'timestamp', 'dose']]

        # 处理基础胰岛素 (basal)
        if not df_basal_insulin.empty:
            df_basal = df_basal_insulin
            df_basal['timestamp'] = df_basal['timestamp'].apply(
                lambda ts: round_minute_pandas(ts, round2min))
            # 按时间分组，取同一时间 basal 剂量的平均值
            df_basal = df_basal.groupby('timestamp')[
                'dose'].mean().rename('basal').reset_index()
            df_basal = df_basal.set_index('timestamp')
            # ✅ GluPred linker 对 basal 应用了 ffill (前向填充)，假设 basal 速率会持续到下一个记录点
            df_basal = df_basal.ffill()
            dfs_to_merge.append(df_basal)

        # 处理餐时胰岛素 (bolus)
        if not df_bolus_insulin.empty:
            df_bolus = df_bolus_insulin
            df_bolus['timestamp'] = df_bolus['timestamp'].apply(
                lambda ts: round_minute_pandas(ts, round2min))
            # 按时间分组，取同一时间 bolus 剂量的总和 (视为瞬时事件的总量)
            df_bolus = df_bolus.groupby('timestamp')[
                'dose'].sum().rename('bolus').reset_index()
            df_bolus = df_bolus.set_index('timestamp')
            # bolus 视为瞬时事件，不需要 ffill
            dfs_to_merge.append(df_bolus)

    # --- 合并所有 DataFrame ---
    if not dfs_to_merge:
        print("Warning: No data records found (glucose, diet, or insulin) to merge.")
        return pd.DataFrame()  # 如果没有数据，返回空DataFrame

    # 找到所有数据的整体时间范围
    min_ts = min(df.index.min() for df in dfs_to_merge if not df.empty)
    max_ts = max(df.index.max() for df in dfs_to_merge if not df.empty)

    # 创建一个完整的时间索引，覆盖整个范围，按指定间隔
    # 确保索引包含最大时间点所在的完整间隔
    full_time_index = pd.date_range(start=round_minute_pandas(min_ts, round2min),
                                    end=round_minute_pandas(
                                        max_ts, round2min) + datetime.timedelta(minutes=round2min),
                                    freq=f'{round2min}min')

    # 将所有处理后的数据框按照完整时间索引进行左连接合并
    merged_df = pd.DataFrame(index=full_time_index)
    for df in dfs_to_merge:
        merged_df = merged_df.join(df, how='left')

    # 合并后 basal 可能仍有 NaNs (如果时间范围最开始没有 basal 记录)，再次进行 ffill
    if 'basal' in merged_df.columns:
        merged_df['basal'] = merged_df['basal'].ffill()

    # 其他列 (glucose, carbs, bolus) 合并后的 NaNs 表示在该时间点没有记录值。
    # 这些 NaNs 将在 prepare_inference_input 函数中进行处理 (插值/填充)。

    return merged_df


def prepare_inference_input(
    processed_df: pd.DataFrame,
    input_len_points: int,  # 模型所需历史数据点数 (例如 24)
    missing_len_points: int,  # 模型预测未来点数 (例如 6)
    min_data_points_required: int,  # 在【原始】历史窗口中最少需要的有效(非NaN)血糖点数【插值前的原始数据检查】
    standardization_mean: List[float],
    standardization_std: List[float],
    feature_order: List[str]
) -> Tuple[torch.Tensor, int]:  # 返回 Tensor 和原始有效点数
    """
    准备用于模型推理的 PyTorch Tensor 输入。
    选择最近的数据窗口，处理缺失值，进行标准化。支持数据不足时的插值扩充。

    Args:
        processed_df: 从 integrate_and_align_data 函数输出的 DataFrame。
        input_len_points: 模型输入历史窗口大小 (例如，5分钟间隔下 2小时数据是 24点)。
        missing_len_points: 模型预测未来窗口大小 (例如，5分钟间隔下 30分钟数据是 6点)。
        min_data_points_required: 在最近 input_len_points 个点中，【原始】数据至少有多少个非 NaN 的血糖点才允许进行预测。
        standardization_mean: 来自模型训练时用的均值列表。
        standardization_std: 来自模型训练时用的标准差列表。
        feature_order: 模型期望的特征列顺序。

    Returns:
        Tuple containing:
        - A PyTorch Tensor (1, input_len_points + missing_len_points, n_features).
        - An integer, the number of original valid glucose points in the historical window.

    Raises:
        ValueError: 如果原始有效数据点不足、处理后仍存在 NaN 或特征不匹配。
    """
    if processed_df.empty:
        raise ValueError(
            "Processed DataFrame is empty. Cannot prepare inference input.")

    # 获取原始 DataFrame 的总行数
    original_row_count = processed_df.shape[0]

    # 1. 确定目标历史窗口的时间索引
    # 窗口结束时间是原始数据的最新时间点 (已按间隔对齐)
    window_end_time = processed_df.index.max()
    # 窗口开始时间是结束时间向前回溯 input_len_points - 1 个间隔
    window_start_time = window_end_time - \
        datetime.timedelta(minutes=(input_len_points - 1)
                           * DATA_INTERVAL_MINUTES)

    # 创建包含 input_len_points 个时间点的完整时间索引
    full_window_time_index = pd.date_range(start=window_start_time,
                                           end=window_end_time,
                                           freq=f'{DATA_INTERVAL_MINUTES}min')

    # 2. 将原始数据合并到完整的窗口索引上
    recent_window_df = processed_df.reindex(
        full_window_time_index)  # 使用 reindex

    # 3. 检查【原始】数据在最近窗口中的有效点数 (使用 reindex 后的 DataFrame 进行检查，NaN表示原始缺失)
    if 'glucose' not in recent_window_df.columns:
        raise ValueError(
            "Glucose column ('glucose') not found after reindexing.")

    valid_glucose_points_original = recent_window_df['glucose'].dropna(
    ).shape[0]

    if valid_glucose_points_original < min_data_points_required:
        # 如果原始有效点数不足阈值，则抛错
        raise ValueError(
            f"Insufficient valid glucose data points ({valid_glucose_points_original} found) in the last "
            f"{input_len_points * DATA_INTERVAL_MINUTES} minutes before interpolation. "
            f"At least {min_data_points_required} points are required for reliable prediction."
        )

    # 4. 处理【扩充后】历史窗口中的缺失值 (NaN)
    # 对血糖进行线性插值 (处理因 reindex 引入的 NaN)
    if recent_window_df['glucose'].isnull().any():
        recent_window_df['glucose'] = recent_window_df['glucose'].interpolate(
            method='time', limit_direction='both')

    # 对于其他特征 (basal, bolus, carbs)，将因 reindex 引入的 NaN 填充为 0
    features_to_fill_zero = [f for f in feature_order if f != 'glucose']
    # 需要确保这些列在 DataFrame 中存在
    for col in features_to_fill_zero:
        if col not in recent_window_df.columns:
            recent_window_df[col] = np.nan  # 先添加列并用 NaN 填充

    fill_values = {f: 0.0 for f in features_to_fill_zero}
    # 填充所有剩余的 NaN (包括新加列的 NaN 和 basal ffill 后可能剩余的 NaN)
    recent_window_df = recent_window_df.fillna(fill_values)

    # 5. 确保所有模型期望的特征列都存在且顺序正确
    # 如果在 fillna(fill_values) 之前有些列因为原始数据完全没有而缺失，这里会添加
    for col in feature_order:
        if col not in recent_window_df.columns:
            recent_window_df[col] = 0.0  # 添加缺失列并用0填充

    # 按照 feature_order 列表重新索引列，确保顺序一致
    recent_window_df = recent_window_df[feature_order]

    # 最终检查：处理后历史窗口中不应再有任何 NaN
    if recent_window_df.isnull().values.any():
        raise ValueError(
            "NaN values remaining in historical data after interpolation and filling.")

    # 6. 转换为 NumPy 数组
    historical_data_np = recent_window_df.to_numpy(
        dtype=np.float32)  # 形状 (input_len_points, n_features)

    # 7. 标准化历史数据 (这部分逻辑不变)
    mean_np = np.array(standardization_mean, dtype=np.float32)
    std_np = np.array(standardization_std, dtype=np.float32)
    std_np[std_np == 0] = 1e-6
    standardized_data_np = (historical_data_np - mean_np) / std_np

    # 8. 准备最终输入 Tensor (这部分逻辑不变)
    total_len_points = input_len_points + missing_len_points
    n_features = len(feature_order)
    model_input_tensor = torch.zeros(
        (1, total_len_points, n_features), dtype=torch.float32)
    model_input_tensor[0, :input_len_points,
                       :] = torch.from_numpy(standardized_data_np)

    return model_input_tensor, valid_glucose_points_original


def denormalize_glucose(
    standardized_glucose_values: Union[torch.Tensor, np.ndarray, float],
    standardization_mean: List[float],
    standardization_std: List[float],
    feature_order: List[str]
) -> Union[torch.Tensor, np.ndarray, float]:
    """
    将标准化后的血糖值 (假定为通道0) 反标准化回 mg/dL，再转换为 mmol/L。

    Args:
        standardized_glucose_values: 标准化后的血糖值 (可以是 Tensor, NumPy 数组, 或 float)。
                                     通常是模型输出中血糖通道的值。
        standardization_mean: 来自模型训练时的均值列表。
        standardization_std: 来自模型训练时的标准差列表。
        feature_order: 特征的顺序列表，用于确定血糖在 mean/std 列表中的位置。

    Returns:
        反标准化并转换为 mmol/L 单位的血糖值。
    Raises:
        ValueError: 如果标准化参数无效。
    """
    if not standardization_mean or not standardization_std:
        raise ValueError("Standardization mean and std must be provided.")
    if len(standardization_mean) < 1 or len(standardization_std) < 1:
        raise ValueError(
            "Standardization parameters must contain values for glucose (channel 0).")

    # 找到血糖特征在 feature_order 中的索引
    try:
        glucose_feature_index = feature_order.index(
            'glucose')  # 假设血糖特征的键是 'glucose'
    except ValueError:
        raise ValueError("Feature order list does not contain 'glucose' key.")

    # 血糖假定为 feature_order 中的特征
    mean_glucose = standardization_mean[glucose_feature_index]
    std_glucose = standardization_std[glucose_feature_index]

    # 反标准化回 mg/dL 单位
    denormalized_mg_dl = standardized_glucose_values * std_glucose + mean_glucose

    return denormalized_mg_dl


# ==============================================================================
# 3. 辅助函数：获取模型期望的特征顺序
#    与 GluPred 的 OhioDataset._initial 逻辑一致
# ==============================================================================

def get_feature_order(unimodal: bool) -> List[str]:
    """
    根据单模态标志返回模型期望的特征顺序列表。
    Args:
        unimodal: 布尔值，如果为 True 表示只使用血糖。
    Returns:
        特征列名称列表。
    """
    if unimodal:
        return ['glucose']
    else:
        return ['glucose', 'basal', 'bolus', 'carbs']  # GluPred多模态特征顺序
