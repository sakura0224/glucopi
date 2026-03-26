import useToastBehavior from '~/behaviors/useToast';
const { request } = require('~/utils/request')
const { calcAge, formatGender } = require('~/utils/personInfo')
import { Toast } from 'tdesign-miniprogram';

Page({
  behaviors: [useToastBehavior],

  data: {
    loading: false,
    isLoad: false,
    service: [],
    personalInfo: {},
    role: '',

    copyright: 'Copyright © 2025 Yankai WANG.',

    settingList: [
      { name: '联系客服', icon: 'service', type: 'service' },
      { name: '设置', icon: 'setting', type: 'setting', url: '/pages/setting/index' },
      { name: '关于', icon: 'info-circle', type: 'info-circle' },
    ],

    // 对话框
    confirmBtn: { content: '确定', variant: 'base' },
    dialogKey: '',
    showConfirm: false,
    showWarnConfirm: false,
    showLightConfirm: false,
  },

  onLoad() {
    const role = wx.getStorageSync('role');
    this.setData({
      loading: false,
      role: role
    })
  },

  async onShow() {
    const Token = wx.getStorageSync('access_token');

    if (Token) {
      // 调用新的获取用户档案接口
      const personalInfo = await this.getPersonalInfo();

      if (personalInfo) { // 确保获取到用户信息
        const { birthday, gender } = personalInfo; // personalInfo 现在是 UserOut Schema 对应的对象
        // 检查 birthday 是否存在且是有效的日期格式
        const age = birthday ? calcAge(birthday) : ''; // 确保 birthday 存在再计算年龄
        const genderText = formatGender(gender);

        this.setData({
          isLoad: true, // 标记加载成功
          personalInfo, // 存储完整的 personalInfo 对象
          displayAge: age,
          displayGender: genderText
        });
      } else {
        // Token 存在但获取用户信息失败，可能 Token 无效或网络问题
        // 可以在 getPersonalInfo 的 catch 中处理 Token 无效的情况（例如清空 Token）
        this.setData({
          isLoad: false, // 标记加载失败
          personalInfo: null,
          displayAge: '',
          displayGender: '',
          // 可以显示错误提示
        });
      }

    } else {
      // Token 不存在，用户未登录状态
      this.setData({
        isLoad: false, // 未加载用户信息
        personalInfo: null, // 清空用户信息
        displayAge: '',
        displayGender: ''
      });
      // 可以在这里引导用户登录
      // 如果 my 页面是 tabbar 页面，不建议直接跳转登录页，可以在页面内显示登录提示
    }
  },

  // 获取用户个人信息及档案
  async getPersonalInfo() {
    try {
      const res = await request('/user/me', 'GET'); // GET 请求到 /api/v1/user/me

      console.log('获取用户信息成功：', res);
      // 假设 request.js 返回的是整个 res 对象，数据体在 res.data
      return res; // 返回后端返回的数据体 (对应 UserOut Schema)

    } catch (err) {
      console.error('获取用户信息失败：', err);
      // request.js 应该已经在失败时显示 Toast 了
      // 根据 request.js 的封装，err 对象可能包含 statusCode 或 data
      if (err.statusCode === 401) {
        console.log("Token 无效或已过期，请重新登录");
        // Token 失效，清空本地存储的 Token 并更新 UI
        wx.clearStorageSync()
        this.setData({
          isLoad: false,
          personalInfo: null,
          displayAge: '',
          displayGender: ''
        });
        // 可选：弹窗提示用户登录
        // wx.showModal({ title: '提示', content: '登录已过期，请重新登录', showCancel: false, success: () => { ... } });
      }
      return null; // 获取失败返回 null
    }
  },

  async checkAccount(e) {
    const _this = this; // 缓存 this，或者用箭头函数也可

    _this.setData({
      loading: true,
    })

    wx.login({
      success: (res) => {
        request('/auth/checkOpenid', 'POST', { code: res.code }).then(result => {
          if (result.registered) {
            console.log("用户已注册");
            // 存 token 备用
            _this.tempToken = result.token;
            _this.tempUserid = result.user_id;
            _this.tempRole = result.role
            // 弹窗提示快捷登录
            _this.setData({ loading: false });
            _this.showDialog(e);
          } else {
            console.log("用户未注册");
            wx.navigateTo({
              url: '/pages/login/login',
              complete: () => {
                _this.setData({ loading: false });
              }
            });
          }
        });
      }
    });
  },

  // 确认登录：保存 token，刷新页面
  autoLogin() {
    const { dialogKey } = this.data;
    this.setData({ [dialogKey]: false });
    const token = this.tempToken;
    const user_id = this.tempUserid;
    const role = this.tempRole;
    wx.setStorageSync('access_token', token);
    wx.setStorageSync('user_id', `${user_id}`)
    wx.setStorageSync('role', role)
    getApp().connect();

    Toast({
      context: this,
      selector: '#t-toast',
      message: '登录成功',
    });

    // 刷新当前页面（推荐用 reLaunch 回到 tab 页）
    wx.reLaunch({ url: '/pages/my/index' });
  },

  // 取消登录：跳转到登录页
  cancelAutoLogin() {
    const { dialogKey } = this.data;
    this.setData({ [dialogKey]: false });

    wx.navigateTo({ url: '/pages/login/login' });
  },

  onNavigateTo() {
    wx.navigateTo({ url: `/pages/my/extra/info-edit/index` });
  },

  toArchive() {
    if (this.data.role === 'doctor') {
      wx.navigateTo({ url: `/pages/my/extra/profile-doctor/index` });
    } else {
      wx.navigateTo({ url: `/pages/my/extra/profile/index` });
    }
  },

  onEleClick(e) {
    const { name, url } = e.currentTarget.dataset.data;
    if (url) return;
    this.onShowToast('#t-toast', name);
  },

  onLogin() {
    wx.navigateTo({
      url: '/pages/login/login',
    })
  },

  onLogout() {
    wx.clearStorageSync()
    wx.reLaunch({
      url: `/pages/my/index`,
    });
  },

  showDialog(e) {
    const { key } = e.currentTarget.dataset;
    this.setData({ [key]: true, dialogKey: key });
  },

  closeDialog() {
    const { dialogKey } = this.data;
    this.setData({ [dialogKey]: false });
  },

  changeAccount() {
    const { dialogKey } = this.data;
    this.setData({ [dialogKey]: false });
    this.onLogout();
  },
});
