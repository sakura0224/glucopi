const { request } = require('../../utils/request.js')

Page({
  data: {
    phoneNumber: '',
    isPhoneNumber: false,
    isCheck: false,
    isSubmit: false,
    isPasswordLogin: false,
    hasAccount: false,
    radioValue: '',
    // 图形验证
    riskType: '',
    useNativeButton: false,
    captchaId: '027c95d1392e2ca8a74e83efbc1cf188',
    loadCaptcha: false,
    styleConfig: {
      btnWidth: '100%'
    },
    scale: 1,
    mask: { outside: true, bgColor: "#0000004d" },
    offlineCb: function () {
      console.log('offlineCb')
    },
  },

  onLoad: function () {
    this.setData({
      useNativeButton: false,
      loadCaptcha: true
    })
  },

  // 图形验证码的相关函数：Validate, Success, Ready, Close, Fail, Error
  captchaValidate: function () {
    var self = this
    var data = self.data.result
    if (!data) {
      console.log('请先完成验证！')
      return
    }
    this.login();
  },

  captchaSuccess: function (result) {
    console.log('captcha-Success!', result)
    this.setData({
      result: result
    })
    this.captchaValidate();
  },

  captchaReady: function () {
    console.log('captcha-Ready!')
  },

  captchaClose: function () {
    console.log('captcha-Close!')
  },

  captchaFail() {
    console.log('captchaFail')
  },

  captchaError: function (e) {
    console.log('captcha-Error!', e.detail)
    // 这里对challenge9分钟过期的机制返回做一个监控，如果服务端返回code:21,tips:not proof，则重新调用api1重置
    if (e.detail.code === 21) {
      var self = this
      // 需要先将插件销毁
      self.setData({ loadCaptcha: false })
      // 重新调用api1
      self.reset()
    }
  },

  // 重置验证码
  reset: function () {
    const captcha = this.selectComponent('#captcha');
    captcha.reset();
  },

  btnSubmit: function () {
    // 进行业务逻辑处理
    console.log("用户密码效验完毕，打开验证码");
    // 唤起验证码
    this.verify();
  },

  // 非NativeButton下唤起
  verify: function () {
    const captcha = this.selectComponent('#captcha');
    captcha.showCaptcha();
  },

  /* 自定义功能函数 */
  changeSubmit() {
    if (this.data.isPhoneNumber && this.data.isCheck) {
      this.setData({ isSubmit: true });
    } else {
      this.setData({ isSubmit: false });
    }
  },

  // 手机号变更
  onPhoneInput(e) {
    const isPhoneNumber = /^[1][3,4,5,7,8,9][0-9]{9}$/.test(e.detail.value);
    this.setData({
      isPhoneNumber,
      phoneNumber: e.detail.value,
    });
    this.changeSubmit();
  },

  // 用户协议选择变更
  onCheckChange(e) {
    const { value } = e.detail;
    this.setData({
      radioValue: value,
      isCheck: value === 'agree',
    });
    this.changeSubmit();
  },

  async login() {
    wx.navigateTo({
      url: `/pages/loginCode/loginCode?phoneNumber=${this.data.phoneNumber}`,
    });
  },
});
