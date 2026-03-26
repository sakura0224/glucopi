// pages/chat/index.js
const app = getApp();
const { request } = require('~/utils/request');
const { sendSocketMessage, markMessagesRead, fetchChatHistory } = require('~/utils/socket');
const { formatTime } = require('./formatTime');
const towxml = require('./towxml/index');

Page({
  data: {
    myAvatar: 'https://cdn.ayane.top/avatar/default.png',
    myId: null,
    userId: null,
    avatar: '',
    name: '',
    messages: [],          // 每条消息可含 mdText
    input: '',
    anchor: '',
    keyboardHeight: 0,
    llmUserId: null,
    isLLMResponding: false,  // 加载中开关
    llmStartTime: null,    // 记录何时开始“思考”
    llmDuration: 0,
    loadingMsgId: '', // 当前占位气泡的 _id
    loadingStartTs: 0,   // 开始“思考”的时间戳（ms）
    scrollHeight: 0,   // 用于绑定行内 style
  },

  onLoad(options) {
    console.log("🔧 onLoad 开始", options);
    const sys = wx.getWindowInfo();
    // ① 系统状态栏高度
    const statusBarH = sys.statusBarHeight;        // px
    // ② 你自定义的导航栏（t-navbar）本身的高度，例如 44px
    const customBarH = 96;
    const navHeightPx = statusBarH + customBarH;   // 总导航高 px

    // ③ 设定给 scroll-view 的可用高度
    const scrollH = sys.windowHeight - navHeightPx;

    this.setData({ scrollHeight: scrollH });

    // —— 1. 初始化数据 —— 
    const targetUserId = options.userId;
    const llmUserId = app.globalData.llmUserId || "-1";
    const myId = wx.getStorageSync("user_id");

    request('/user/me', 'GET').then(res => {
      this.setData({
        myAvatar: res.avatar_url,
        userId: targetUserId,
        llmUserId,
        myId: myId
      })
    });

    // —— 2. LLM 会话 —— 
    if (String(targetUserId) === llmUserId) {
      console.log("🧠 走 LLM 分支");
      this.setData({
        name: "DeepSeek",
        avatar: "https://cdn.ayane.top/deepseek.png",
      }, () => {
        wx.setNavigationBarTitle({ title: this.data.name });
        this.loadChatHistory();              // 拉历史
      });
      this._bindSocket();                    // 绑定实时推送
      return;
    }

    console.log("👩‍⚕️ 走医生分支");
    // —— 3. 医生会话：先等 eventChannel 传递 info —— 
    this.channel = this.getOpenerEventChannel();
    this.channel.on("doctorInfo", ({ doctor }) => {
      this.setData({
        userId: String(doctor.id),
        name: doctor.nickname || "医生",
        avatar: doctor.avatarUrl || "https://cdn.ayane.top/avatar/default.png",
      }, () => {
        wx.setNavigationBarTitle({ title: this.data.name });
        this.loadChatHistory();              // 拉历史
        this.markConversationAsRead(this.data.userId);
      });
    });

    // —— 4. 分享直连（无 doctorInfo） —— 
    if (!this.data.name && targetUserId) {
      wx.setNavigationBarTitle({ title: "加载聊天对象…" });
      this.fetchTargetUserInfo(targetUserId)
        .then(() => {
          this.loadChatHistory();
          this.markConversationAsRead(this.data.userId);
        });
    }

    // —— 5. 全局绑定 WebSocket 回调 —— 
    this._bindSocket();
  },

  /** 只处理普通和 LLM 的 message 消息，不再管流式 */
  _bindSocket() {
    const socket = app.globalData.socket;
    if (!socket) return app.connect();
    if (this._wsBound) return;
    this._wsBound = true;

    socket.onMessage(res => {
      const { type, data } = JSON.parse(res.data || '{}');
      if (type !== 'message') return;

      const msg = data.message;
      const isMyLLM = msg.isLLM && String(msg.from) === String(this.data.llmUserId);

      /* —— LLM 回复 —— */
      if (isMyLLM) {
        // ① 计算用时（秒），防御 loadingStartTs 不存在的情况
        const durationSec = this.data.loadingStartTs
          ? Math.round((Date.now() - this.data.loadingStartTs) / 1000)
          : 0;

        // ② 构造带 parsed markdown + duration 的消息对象
        const final = {
          ...msg,
          displayTime: formatTime(msg.time),
          timestamp: new Date(msg.time).getTime(),
          renderedContent: towxml(msg.content, 'markdown', { theme: 'light' }),
          duration: durationSec
        };

        // ③ 把占位删掉，push 真消息
        const newList = this.data.messages.filter(m => m._id !== this.data.loadingMsgId);
        newList.push(final);

        // ④ 更新列表并清空 loading 标记
        this.setData({
          messages: newList,
          loadingMsgId: '',
          loadingStartTs: 0
        });

        return;
      }

      /* —— 其他普通 / 医生 消息 —— */
      this.addAndRenderMessage(msg);
    });
  },

  /** 添加并渲染一条消息（新改：一次性 towxml 解析） */
  addAndRenderMessage(message) {
    const formatted = {
      ...message,
      displayTime: formatTime(message.time),
      timestamp: new Date(message.time).getTime(),
      // 如果是 LLM 消息，一次性解析 Markdown
      renderedContent: message.isLLM
        ? towxml(message.content, 'markdown', {
          base: '',      // 如需图片等资源前缀可设置
          theme: 'light', // 或 'dark'
          events: { tap: e => console.log('link tap', e) }
        })
        : null
    };

    this.setData({
      messages: [...this.data.messages, formatted]
    });
  },

  /** 发送消息保持不变，只是改了渲染流程 */
  sendMessage() {
    const content = this.data.input.trim();
    const to = this.data.userId;
    const meId = this.data.myId;
    if (!content) return;

    const msgs = [...this.data.messages];

    /* ➊ 先 push 我自己的消息 */
    msgs.push({
      _id: `temp_${Date.now()}`,
      from: meId,
      to,
      content,
      isLLM: false,
      time: new Date().toISOString(),
      displayTime: formatTime(new Date()),
      timestamp: Date.now()
    });

    /* ➋ 如果目标是 LLM，push 占位气泡 */
    if (String(to) === String(this.data.llmUserId)) {
      const loadingId = `loading_${Date.now()}`;
      msgs.push({
        _id: loadingId,
        from: this.data.llmUserId,
        to: meId,
        isLoading: true,
        timestamp: Date.now()
      });

      // ⚠️ 把两项写入 data，后面才能计算/删除
      this.setData({
        loadingMsgId: loadingId,
        loadingStartTs: Date.now()
      });
    }

    /* ➌ 一次 setData 更新 messages 和清空输入框 */
    this.setData({ messages: msgs, input: '' }, () => wx.nextTick(this.scrollToBottom));

    /* ➍ 发 WebSocket */
    const payload = { type: 'message', data: { to, content, time: Date.now() } };
    const socket = app.globalData.socket;
    if (socket && socket.readyState === 1) {
      sendSocketMessage(socket, payload);
    } else {
      wx.showToast({ title: '发送失败', icon: 'none' });
    }
  },

  /* ---------- 加载历史 ---------- */
  async loadChatHistory(skip = 0, limit = 20) {
    console.log('开始加载历史')
    try {
      const { data = [] } = await fetchChatHistory(this.data.userId, skip, limit);
      const processed = data.map(m => {
        const base = {
          ...m,
          displayTime: formatTime(m.time),
          timestamp: new Date(m.time).getTime()
        };
        // 非流式：一次性解析 Markdown
        if (m.isLLM) {
          base.renderedContent = towxml(
            m.content,
            'markdown',
            {
              base: '',      // 如有相对资源地址可设
              theme: 'light', // 或 'dark'
              events: { tap: e => console.log('link tap', e) }
            }
          );
        }
        return base;
      });
      console.log('处理数据', processed)
      this.setData({ messages: processed }, () => {
        wx.nextTick(this.scrollToBottom);
      });
    } catch (e) { console.error('历史消息加载失败', e); }
  },

  /** 新增：标记与特定用户对话为已读的函数 (只通知后端) */
  async markConversationAsRead(targetUserId) {
    if (!targetUserId) return;
    console.log(`正在通知后端标记与用户 ${targetUserId} 的对话为已读`);

    try {
      // 调用 markMessagesRead 函数 (异步) 通知后端
      // 假设 markMessagesRead 接受用户 ID 字符串
      const apiResponse = await markMessagesRead(targetUserId);
      console.log('通知后端标记已读成功:', apiResponse);

      // 注意：这里不进行本地 Message 页面的未读数更新，那部分是 Message 页面的职责
      // Message 页面应该在 onShow 或收到 read-done 事件时刷新其数据
    } catch (err) {
      console.error(`通知后端标记与用户 ${targetUserId} 的对话为已读失败:`, err);
      // 后端标记失败可能需要提示用户或重试
    }
  },


  /** 消息列表滚动到底部 */
  scrollToBottom() {
    // 小程序滚动到底部通常有两种方式：设置 scrollTop 或设置 scroll-into-view
    // 使用 scroll-into-view 需要确保对应的元素存在
    // 如果消息列表很长，需要确保 bottom 元素始终在最后
    this.setData({ anchor: 'bottom' });
    // 清空 anchor，避免重复滚动
    wx.nextTick(() => {
      this.setData({ anchor: '' });
    });
  },

  /** 新增：获取目标用户信息函数 (根据 ID 获取) */
  async fetchTargetUserInfo(userIdString) { // 接收用户 ID 字符串
    if (!userIdString) return;
    console.log(`Fetching target user info for ID: ${userIdString}`);

    try {
      const res = await request(`/user/${userIdString}/basic_info`, 'GET'); // 调用新的 API
      console.log('Fetched target user info:', res);

      // 假设 res 包含 UserBasicInfoOut Schema 对应的对象
      const targetUser = res;

      if (targetUser) {
        this.setData({
          userId: String(targetUser.id), // 确保更新 userId 为字符串
          name: targetUser.nickname || `用户${userIdString}`,
          avatar: targetUser.avatar_url || '/static/chat/avatar.png', // 使用后端返回的头像
        });
        wx.setNavigationBarTitle({ title: this.data.name });
        this.loadChatHistory();
      } else {
        console.warn(`User with ID ${userIdString} not found via API.`);
        // TODO: 提示用户或使用默认信息
        this.setData({
          name: `用户${userIdString}`,
          avatar: '/static/chat/avatar.png',
        });
        wx.setNavigationBarTitle({ title: this.data.name });
      }

    } catch (err) {
      console.error(`Failed to fetch target user info for ID ${userIdString}:`, err);
      wx.showToast({ title: '加载聊天对象信息失败', icon: 'none' });
      // TODO: 即使加载失败，也要设置默认昵称和头像，避免页面空白
      this.setData({
        name: `用户${userIdString}`,
        avatar: '/static/chat/avatar.png',
      });
      wx.setNavigationBarTitle({ title: this.data.name });
    }
  },

  /** 处理唤起键盘事件 */
  handleKeyboardHeightChange(event) {
    const { height } = event.detail;
    if (!height) return;
    this.setData({ keyboardHeight: height });
    wx.nextTick(this.scrollToBottom);
  },

  /** 处理收起键盘事件 */
  handleBlur() {
    this.setData({ keyboardHeight: 0 });
  },

  /** 处理输入事件 */
  handleInput(event) {
    this.setData({ input: event.detail.value });
  },
});