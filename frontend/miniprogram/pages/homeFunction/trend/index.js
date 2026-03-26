import * as echarts from 'ec-canvas/echarts'; // 你 echarts 路径可能不同
import dayjs from 'dayjs';
const { request } = require('~/utils/request');
const GlucoseConverter = require('~/pages/homeFunction/glucoseConverter.js');

let chartInstance = null;

Page({
  data: {
    activeTab: 'day',
    user_id: '',
    convertedSeries: [],
    ec: {
      lazyLoad: true // 延迟加载
    }
  },
  onLoad(options) {
    if (options) {
      const user_id = options.user_id;
      this.setData({
        user_id,
      });
    }
    this.initChart();
  },

  onTabChange(e) {
    const tab = e.detail.value;
    this.setData({ activeTab: tab }, () => {
      this.updateChart(tab);
    });
  },

  initChart() {
    this.selectComponent('#trendChart').init((canvas, width, height, dpr) => {
      const chart = echarts.init(canvas, null, {
        width,
        height,
        devicePixelRatio: dpr
      });
      canvas.setChart(chart);
      chartInstance = chart;
      this.updateChart(this.data.activeTab);
      return chart;
    });
  },

  async updateChart(tab) {
    if (!chartInstance) return;
    const user_id = this.data.user_id || '';

    const today = dayjs().format('YYYY-MM-DD');

    const params = {
      tab,
      date: today
    };

    if (user_id) {
      params.user_id = user_id;
    }

    const res = await request('/glucose/trend', 'GET', params);
    const { xAxis, series, dateRange } = res.data;

    // 确保 GlucoseConverter 模块存在
    if (!GlucoseConverter || typeof GlucoseConverter.mgdlToMmolL !== 'function') {
      console.error("GlucoseConverter module or mgdlToMmolL function not available! Cannot convert data.");
      // 在这里处理错误，比如显示提示，或者不进行转换
      const convertedSeries = series; // 或者返回一个空数组 []
    } else {
      // 使用 map 方法遍历数组并进行转换
      const convertedSeries = series.map(item => {
        // 检查当前元素是否是数字类型且不是 NaN (因为 null 的 typeof 是 'object')
        if (typeof item === 'number' && !isNaN(item)) {
          // 如果是数字，调用转换函数并返回转换后的值 (mmol/L)
          return GlucoseConverter.mgdlToMmolL(item);
        } else {
          // 如果不是数字 (比如 null)，则直接返回原始值
          return item;
        }
      });
      console.log("原始数组 (mg/dL):", series);
      console.log("转换后数组 (mmol/L):", convertedSeries);
      this.setData({ convertedSeries });
    }

    console.log("xAxis:", xAxis)
    console.log("dateRange", dateRange)

    chartInstance.setOption({
      title: {
        text: dateRange,
        left: 'center'
      },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: xAxis },
      yAxis: { type: 'value', name: 'mg/dL' },
      series: [{ name: '血糖', type: 'line', data: this.data.convertedSeries }]
    });
  }
});
