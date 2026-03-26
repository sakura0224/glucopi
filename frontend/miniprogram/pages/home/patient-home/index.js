// components/patient-home/index.js
const { request } = require('~/utils/request');

const imageCdn = 'https://cdn.ayane.top';
const swiperList = [
  { value: `${imageCdn}/banner1.png`, ariaLabel: '图片1' },
  { value: `${imageCdn}/banner2.png`, ariaLabel: '图片2' },
  { value: `${imageCdn}/banner3.png`, ariaLabel: '图片3' }
];

Component({
  options: { addGlobalClass: true },

  data: {
    showGlucoseNotice: false,
    current: 0,
    autoplay: true,
    duration: 500,
    interval: 5000,
    swiperList
  },

  /** 当组件所在页面显示时触发 */
  pageLifetimes: {
    async show() {
      const token = wx.getStorageSync('access_token');
      if (token) {
        await this.showNotice();
      }
    }
  },

  methods: {
    /** 刷新页面 */
    async refreshScreen() {
      await this.showNotice();
    },

    /** 点击 t-grid 或其它可跳转项 */
    click(e) {
      const { url } = e.target.dataset;
      if (url) wx.navigateTo({ url });
    },

    /** 公告栏点击处理 */
    notice(e) {
      const { trigger } = e.detail;
      if (trigger === 'suffix-icon') {
        this.setData({ showGlucoseNotice: false });
      } else {
        wx.navigateTo({ url: '/pages/patient/record/add/index' });
      }
    },

    /** 检查当天血糖，决定是否显示 notice */
    async showNotice() {
      try {
        const res = await request('/glucose/checkToday', 'GET');
        this.setData({ showGlucoseNotice: !res.recorded });
      } catch (e) {
        this.setData({ showGlucoseNotice: false });
      }
    }
  }
});
