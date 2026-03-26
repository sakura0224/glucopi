const { request } = require('../../utils/request');
import { Toast } from 'tdesign-miniprogram';

Page({
  data: {
    phoneNumber: '',
    sendCodeCount: 60,
    verifyCode: '',
    isLoading: false,
  },

  timer: null,

  onLoad(options) {
    const { phoneNumber } = options;
    if (phoneNumber) {
      this.setData({ phoneNumber });
    }
    this.countDown();
  },

  onVerifycodeChange(e) {
    this.setData({
      verifyCode: e.detail.value,
    });
  },

  countDown() {
    this.setData({ sendCodeCount: 60 });
    this.timer = setInterval(() => {
      if (this.data.sendCodeCount <= 0) {
        this.setData({ isSend: false, sendCodeCount: 0 });
        clearInterval(this.timer);
      } else {
        this.setData({ sendCodeCount: this.data.sendCodeCount - 1 });
      }
    }, 1000);
  },

  sendCode() {
    if (this.data.sendCodeCount === 0) {
      this.countDown();
    }
  },

  // 点击注册
  async onRegister() {
    const phone = this.data.phoneNumber
    this.setData({ isLoading: true })

    wx.login({
      success: async (res) => {
        const code = res.code
        if (!code) {
          wx.showToast({ title: '获取登录凭证失败', icon: 'none' })
          this.setData({ isLoading: false })
          return
        }

        try {
          // ① 查询手机号是否已注册
          const check = await request('/auth/checkAccount', 'GET', { phone })

          let api = ''
          let payload = { phone, code }

          if (check.registered) {
            // ② 已注册，走登录
            api = '/auth/login'
          } else {
            // ③ 未注册，走注册
            api = '/auth/register'
          }

          // ④ 发起登录或注册
          const res = await request(api, 'POST', payload)

          wx.setStorageSync('access_token', res.token)
          wx.setStorageSync('user_id', `${res.user_id}`)
          wx.setStorageSync('role', res.role)

          getApp().connect();

          if (check.registered) {
            Toast({
              context: this,
              selector: '#t-toast',
              message: '登录成功',
            });
            wx.reLaunch({
              url: '/pages/my/index',
            })
          } else {
            Toast({
              context: this,
              selector: '#t-toast',
              message: '注册成功',
            });
            // 跳转页面
            wx.redirectTo({
              url: '/pages/my/info-edit/index'
            })
          }
        } catch (err) {
          Toast({
            context: this,
            selector: '#t-toast',
            message: err.detail || '操作失败',
          });
        } finally {
          this.setData({ isLoading: false })
        }
      },
      fail: () => {
        Toast({
          context: this,
          selector: '#t-toast',
          message: '微信登录失败',
        });
        this.setData({ isLoading: false })
      }
    })
  }
});
