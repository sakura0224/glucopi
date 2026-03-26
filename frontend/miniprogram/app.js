// app.js
import createBus from './utils/eventBus';
import { connectSocket, fetchUnreadNum } from './utils/socket';

App({
  onLaunch() {
    const updateManager = wx.getUpdateManager();

    updateManager.onCheckForUpdate(() => { });
    updateManager.onUpdateReady(() => {
      wx.showModal({
        title: '更新提示',
        content: '新版本已经准备好，是否重启应用？',
        success(res) {
          if (res.confirm) {
            updateManager.applyUpdate();
          }
        }
      });
    });
    // —— 只在已登录（token & user_id 都有）时才拉未读、连接 socket —— 
    const token = wx.getStorageSync('access_token');
    const userId = wx.getStorageSync('user_id');
    if (token && userId) {
      this.getUnreadNum();
      this.connect();
    } else {
      console.log('[App] 未登录，跳过拉取未读 & 不建立 WebSocket');
    }
  },

  globalData: {
    userInfo: null,
    unreadNum: 0,
    socket: null,
    role: 'patient',
    llmUserId: '-1', // --- 新增：存储 LLM 虚拟用户 ID ---
  },

  eventBus: createBus(),

  connect() {
    const token = wx.getStorageSync('access_token');
    const userId = wx.getStorageSync('user_id');

    // 未登录，不连接 socket
    if (!token || !userId) {
      console.log('[Socket] 用户未登录，不建立连接');
      return;
    }

    // 如果 socket 已经存在且连接中，无需重复连接
    if (this.globalData.socket && this.globalData.socket.readyState === 1) {
      console.log('[Socket] 连接已存在且正常');
      return;
    }

    const socketTask = connectSocket(); // connectSocket 函数应返回 wx.SocketTask 实例

    // --- 新增：处理 WebSocket 收到 config 消息 (获取 LLM ID) ---
    socketTask.onMessage((res) => {
      const data = JSON.parse(res.data); // 小程序 onMessage 接收到的是字符串，需要手动解析

      if (data.type === 'config') {
        console.log('[Socket] 收到 config 消息:', data.data);
        if (data.data && data.data.llmUserId) {
          this.globalData.llmUserId = data.data.llmUserId;
          console.log('[Socket] LLM 用户 ID 已获取:', this.globalData.llmUserId);
        }
      }
      // --- 现有消息处理逻辑 ---
      else if (data.type === 'message' && !data.data.message.read) {
        // 这部分逻辑可能是用于在会话列表页显示总未读数
        // Chat 页的消息处理逻辑在页面 js 中实现
        // 只有当前页面不是正在聊天的会话时，才增加总未读数
        // 检查当前页面路径，如果不是 Chat 页面或 Chat 页面不是当前会话，则增加总未读数
        const pages = getCurrentPages();
        const currentPage = pages[pages.length - 1];
        // 检查页面路径和当前聊天的 targetUserId 是否匹配
        if (!currentPage || currentPage.route !== 'pages/chat/index' || String(currentPage.data.userId) !== String(data.data.userId)) {
          this.setUnreadNum(this.globalData.unreadNum + 1);
        }
      }
      // --- 现有消息处理逻辑结束 ---
    });

    // 监听其他 WebSocket 事件 (onOpen, onError, onClose) 在 utils/socket.js 中实现更合适
    this.globalData.socket = socketTask;
  },

  // TODO: 添加 disconnect 函数来关闭 WebSocket 连接
  disconnect: function () {
    if (this.globalData.socket && this.globalData.socket.readyState === 1) {
      this.globalData.socket.close({
        code: 1000, // 正常关闭码
        reason: '用户退出登录'
      });
      this.globalData.socket = null;
      console.log('[Socket] 连接已关闭');
    }
    this.globalData.llmUserId = null; // 清空 LLM ID
  },

  /**
   * 拉取未读数（仅在用户已登录时调用）
   */
  getUnreadNum() {
    // 再次防御：如果没登录就直接退
    const token = wx.getStorageSync('access_token');
    if (!token) {
      console.log('[App] 未登录，跳过 getUnreadNum');
      return;
    }
    fetchUnreadNum()
      .then(({ data }) => {
        this.globalData.unreadNum = data;
        this.eventBus.emit('unread-num-change', data);
      })
      .catch(err => {
        console.error('[App] getUnreadNum 失败', err);
      });
  },

  setUnreadNum(unreadNum) {
    this.globalData.unreadNum = unreadNum;
    this.eventBus.emit('unread-num-change', unreadNum);
  },
});
