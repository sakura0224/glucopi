const { request } = require('~/utils/request');
const GlucoseConverter = require('~/pages/homeFunction/glucoseConverter.js');

Page({
  data: {
    /* 预测相关 */
    selected: '',            // 30 / 60
    isLoading: false,
    predictionResult: null,
    convertedGlucose: null,

    /* 免责声明 */
    showDisclaimer: true,
    marquee: { speed: 80, loop: -1, delay: 0 },
    content: '本预测结果仅供参考，不能替代专业医疗建议。如有紧急情况，请及时就医。'
  },

  /* ---------------- 事件 ---------------- */

  onIntervalChange(e) {
    this.setData({ selected: e.detail.value, predictionResult: null });
  },

  onCloseDisclaimer() { this.setData({ showDisclaimer: false }); },

  /* 主动作：发送预测请求 */
  async onPredict() {
    const { selected } = this.data;
    if (!selected) return;

    this.setData({ isLoading: true, predictionResult: null });

    try {
      const res = await request('/prediction/predict_glucose', 'POST', { predict_minutes: this.data.selected });
      // 服务器应返回 predicted_glucose 列表
      const idx = (selected / 5) - 1; // 与后端约定：每 5 min 一个点
      const glucoseMmol = GlucoseConverter.mgdlToMmolL(
        res.predicted_glucose[idx].glucose
      );

      console.log("收到血糖预测数据：\n", res)
      console.log("原始血糖数据为", res.predicted_glucose[idx].glucose)
      console.log("转换后血糖数据为", glucoseMmol.toFixed(1))

      this.setData({
        predictionResult: res,
        convertedGlucose: glucoseMmol.toFixed(1),
      });
    } catch (err) {
      wx.showToast({ title: err?.detail || '预测失败', icon: 'none' });
    } finally {
      this.setData({
        isLoading: false
      });
    }
  },

  /* 下拉刷新 */
  onPullDownRefresh() {
    this.setData({
      selected: '',
      isLoading: false,
      predictionResult: null,
      convertedGlucose: null,
      showDisclaimer: true
    });
    wx.stopPullDownRefresh();
  },
});
