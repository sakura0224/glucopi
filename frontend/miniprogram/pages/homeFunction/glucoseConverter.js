/**
 * 血糖单位转换模块 (mg/dL <-> mmol/L)
 * 常用的转换因子约为 18。
 * 1 mmol/L ≈ 18 mg/dL
 */
const GlucoseConverter = {

  // 血糖单位转换因子
  // 葡萄糖分子量约 180.156 g/mol。
  // 1 mmol/L = 1 millimole/L
  // 1 millimole 葡萄糖 = 180.156 mg
  // 1 mmol/L = 180.156 mg/L = 18.0156 mg/dL
  // 临床上常使用 18 作为简化因子。这里使用 18。
  CONVERSION_FACTOR: 18,

  /**
   * 将血糖值从 mg/dL 转换为 mmol/L。
   * 结果通常保留一位小数。
   * @param {number | string} mgdlValue - 以 mg/dL 为单位的血糖值。可以是数字或数字字符串。
   * @returns {number | NaN} 转换后以 mmol/L 为单位的值（保留一位小数），如果输入无效则返回 NaN。
   */
  mgdlToMmolL: function (mgdlValue) {
    // 尝试将输入转换为数字，以处理可能是字符串的情况
    const numValue = typeof mgdlValue === 'string' ? parseFloat(mgdlValue) : mgdlValue;

    // 验证输入是否为有效的非负数字
    if (typeof numValue !== 'number' || isNaN(numValue) || numValue === null || numValue < 0) {
      console.error("GlucoseConverter: 无效的 mg/dL 输入，无法转换:", mgdlValue);
      return NaN; // 返回 NaN 表示无效结果
    }

    const mmolL = numValue / this.CONVERSION_FACTOR;

    // 临床上 mmol/L 通常保留一位小数
    // 使用 toFixed(1) 保留一位小数，然后用 parseFloat 转换为数字
    return parseFloat(mmolL.toFixed(1));
  },

  /**
   * 将血糖值从 mmol/L 转换为 mg/dL。
   * 结果通常四舍五入到最接近的整数。
   * @param {number | string} mmolLValue - 以 mmol/L 为单位的血糖值。可以是数字或数字字符串。
   * @returns {number | NaN} 转换后以 mg/dL 为单位的值（四舍五入到整数），如果输入无效则返回 NaN。
   */
  mmolLToMgdl: function (mmolLValue) {
    // 尝试将输入转换为数字
    const numValue = typeof mmolLValue === 'string' ? parseFloat(mmolLValue) : mmolLValue;

    // 验证输入是否为有效的非负数字
    if (typeof numValue !== 'number' || isNaN(numValue) || numValue === null || numValue < 0) {
      console.error("GlucoseConverter: 无效的 mmol/L 输入，无法转换:", mmolLValue);
      return NaN; // 返回 NaN 表示无效结果
    }

    const mgdl = numValue * this.CONVERSION_FACTOR;

    // 临床上 mg/dL 通常使用整数
    // 使用 Math.round 四舍五入到最接近的整数
    return Math.round(mgdl);
  }
};

// 使用 CommonJS 规范导出模块，微信小程序默认支持
module.exports = GlucoseConverter;