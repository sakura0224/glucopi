Page({
  data: {
    role: '',
  },

  onShow() {
  },

  onLoad() {
    const role = wx.getStorageSync('role') || getApp().globalData.role;
    this.setData({ role });
  },

  onPullDownRefresh() {
    const role = wx.getStorageSync('role') || getApp().globalData.role;
    if (role == 'doctor') {
      const doctorHome = this.selectComponent('#doctorHome');
      if (doctorHome) {
        doctorHome.refreshPatients?.()   // 安全调用
          .then(() => wx.stopPullDownRefresh())
          .catch(() => wx.stopPullDownRefresh());
      } else {
        wx.stopPullDownRefresh();
      }
    } else {
      const patientHome = this.selectComponent('#patientHome');
      if (patientHome) {
        patientHome.refreshScreen?.()   // 安全调用
          .then(() => wx.stopPullDownRefresh())
          .catch(() => wx.stopPullDownRefresh());
      } else {
        wx.stopPullDownRefresh();
      }
    }
  },
});