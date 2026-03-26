// pages/message/message.js
const { request } = require('~/utils/request');
const { markMessagesRead } = require('~/utils/socket');
const app = getApp();

Page({
  data: {
    messageList: [],     // 列表数据
    loading: true,       // loading 状态
    _hasLoadedOnce: false // 标志：是否已拉过列表
  },

  /**
   * 生命周期函数—页面显示
   * - 只有第一次切到该 Tab 时拉一次接口
   * - 且保证登录态校验和 WebSocket 绑定都在这里
   */
  onShow() {
    // 1. 登录态拦截
    const token = wx.getStorageSync('access_token');
    if (!token) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }

    // 2. 第一次切到消息页时拉列表
    if (!this.data._hasLoadedOnce) {
      this.setData({ _hasLoadedOnce: true });
      this.getMessageList();
    }

    // 3. 绑定 WebSocket 回调（只绑定一次）
    const socket = app.globalData.socket;
    if (socket && !this._hasSocketBound) {
      this._hasSocketBound = true;
      socket.onMessage(res => {
        let msg;
        try {
          msg = JSON.parse(res.data);
        } catch {
          return;
        }
        if (msg.type !== 'message') return;

        const { userId, message } = msg.data;
        const result = this.getUserById(userId);
        if (!result) return;
        const { user, index } = result;

        // 更新会话摘要：最后一条内容、时间、未读数++
        user.lastMessage = message.content;
        user.time = message.time;
        user.unread = (user.unread || 0) + 1;

        // 将该会话移动到最前
        const list = this.data.messageList.slice();
        list.splice(index, 1);
        list.unshift(user);

        // 如果当前正打开这个聊天，就标记已读
        if (this.currentUserId === userId && this.currentEventChannel) {
          this.setMessagesRead(userId);
          this.currentEventChannel.emit('update', user);
        }

        // 更新 UI & 全局未读数
        this.setData({ messageList: list });
        app.setUnreadNum(this.computeUnreadNum());
      });
    }
  },

  /**
   * 拉取聊天摘要列表
   */
  getMessageList() {
    request('/chat/summary', 'GET')
      .then(({ data }) => {
        this.setData({
          messageList: data,
          loading: false
        });
        app.setUnreadNum(this.computeUnreadNum());
      })
      .catch(err => {
        console.error('消息列表加载失败', err);
        this.setData({ loading: false });
      });
  },

  /**
   * 根据 userId 找到会话对象和索引
   * @returns {{user: Object, index: number}|null}
   */
  getUserById(userId) {
    const list = this.data.messageList;
    for (let i = 0; i < list.length; i++) {
      if (list[i].userId === userId) {
        return { user: list[i], index: i };
      }
    }
    return null;
  },

  /**
   * 计算所有会话的未读总数
   */
  computeUnreadNum() {
    return this.data.messageList.reduce(
      (sum, item) => sum + (item.unread || 0),
      0
    );
  },

  /**
   * 点击会话行，跳转聊天页
   */
  toChat(evt) {
    const userId = evt.currentTarget.dataset.userId;
    wx.navigateTo({
      url: `/pages/chat/index?userId=${userId}`,
      success: ({ eventChannel }) => {
        this.currentUserId = userId;
        this.currentEventChannel = eventChannel;
        const res = this.getUserById(userId);
        if (res) eventChannel.emit('update', res.user);
      }
    });
    this.setMessagesRead(userId);
  },

  /**
   * 标记与某个用户的会话为已读
   */
  setMessagesRead(userId) {
    const res = this.getUserById(userId);
    if (!res) return;
    // 本地置 0
    res.user.unread = 0;
    this.setData({ messageList: this.data.messageList });
    app.setUnreadNum(this.computeUnreadNum());
    // 通知后端
    markMessagesRead(userId).catch(console.error);
  },

  /**
   * 预留的跳 LLM 聊天
   */
  handleClick() {
    const llmId = app.globalData.llmUserId || '-1';
    wx.navigateTo({ url: `/pages/chat/index?userId=${llmId}` });
  }
});
