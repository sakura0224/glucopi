// utils/socket.js
import { request } from '~/utils/request'
const { WS_BASE_URL } = require('./api-config')

let retryCount = 0
const MAX_RETRY = 5

/** 跳登录（同 request.js） */
function redirectToLogin() {
  wx.clearStorageSync()
  wx.showToast({ title: '请先登录', icon: 'none', duration: 1500 })
  wx.navigateTo({ url: '/pages/login/login' })
}

/** 建立 WebSocket 连接，带自动重连逻辑 */
export function connectSocket() {
  const token = wx.getStorageSync('access_token')
  if (!token) {
    // 未登录不连
    redirectToLogin()
    return null
  }

  const socket = wx.connectSocket({
    url: `${WS_BASE_URL}?token=${encodeURIComponent(token)}`
  })

  socket.onOpen(() => {
    console.log('[Socket] 连接成功')
    retryCount = 0
  })

  socket.onError(err => {
    console.error('[Socket] 连接失败', err)
    wx.showToast({
      title: '聊天服务器连接失败，正在重试…',
      icon: 'none',
      duration: 1500
    })
    // 指数退避
    if (retryCount < MAX_RETRY) {
      const delay = 1000 * Math.pow(2, retryCount)  // 1s,2s,4s,8s...
      retryCount++
      setTimeout(() => {
        connectSocket()
      }, delay)
    }
  })

  socket.onClose(() => {
    console.warn('[Socket] 已断开')
    if (retryCount >= MAX_RETRY) {
      wx.showModal({
        title: '连接中断',
        content: '与聊天服务器断开，请检查网络或稍后重试',
        showCancel: false
      })
    }
  })

  return socket
}

/** 发送 WebSocket 消息 */
export function sendSocketMessage(socket, payload) {
  console.log('[Socket] send:', payload)
  socket.send({ data: JSON.stringify(payload) })
}

/** 标记消息已读 */
export function markMessagesRead(fromUserId) {
  return request('/chat/read', 'POST', { from_user: fromUserId })
}

/** 拉聊天历史 */
export function fetchChatHistory(otherId, skip = 0, limit = 20) {
  return request('/chat/history', 'GET', { other_id: otherId, skip, limit })
    .then(res => {
      console.log('[API] Chat history:', res)
      return res
    })
}

/** 拉未读数 */
export function fetchUnreadNum() {
  return request('/chat/summary', 'GET')
    .then(res => {
      console.log('[API] Chat summary:', res)
      let cnt = 0
      if (Array.isArray(res.data)) {
        for (const chat of res.data) cnt += chat.unread || 0
      }
      return cnt
    })
}
