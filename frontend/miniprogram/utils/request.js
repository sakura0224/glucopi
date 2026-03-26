// utils/request.js

const { HTTP_BASE_URL } = require('./api-config')

const NO_AUTH_PATHS = new Set([
  '/auth/register',
  '/auth/login',
  '/auth/wechatLogin',
  '/auth/checkOpenid',
  '/auth/checkAccount'
])

function redirectToLogin() {
  wx.clearStorageSync()
  wx.showToast({ title: '请先登录', icon: 'none', duration: 1500 })
  wx.navigateTo({ url: '/pages/login/login' })
}

function request(url, method = 'GET', data = {}) {
  const fullUrl = HTTP_BASE_URL + url
  const needsAuth = !NO_AUTH_PATHS.has(url)

  const token = wx.getStorageSync('access_token')
  if (needsAuth && !token) {
    redirectToLogin()
    console.log('申请的url为', url);
    return Promise.reject({ msg: '未登录' })
  }

  const headers = { 'Content-Type': 'application/json' }
  if (needsAuth) headers['Authorization'] = `Bearer ${token}`

  let reqUrl = fullUrl
  let body = data
  method = method.toUpperCase()
  if (method === 'GET' && Object.keys(data).length) {
    const qs = Object.entries(data)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join('&')
    reqUrl += '?' + qs
    body = {}
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: reqUrl,
      method,
      data: body,
      header: headers,
      success(res) {
        const { statusCode } = res
        const body = res.data || {}  // 🔥重要：空data默认成{}

        if (needsAuth && (statusCode === 401 || statusCode === 403)) {
          redirectToLogin()
          return reject(body)
        }

        if (statusCode >= 200 && statusCode < 300) {
          return resolve(body)  // 🔥成功，无论有没有data
        }

        wx.showToast({
          title: body.detail || `请求失败 (${statusCode})`,
          icon: 'none'
        })
        reject(body)
      },
      fail(err) {
        const msg = (err.errMsg || '').includes('request:fail')
          ? '无法连接服务器，请检查网络或稍后重试'
          : '网络异常'
        wx.showToast({ title: msg, icon: 'none', duration: 2000 })
        reject(err)
      }
    })
  })
}

module.exports = { request }
