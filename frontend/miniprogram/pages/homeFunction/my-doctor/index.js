const { request } = require('~/utils/request.js'); // 确认路径正确
import { Toast } from 'tdesign-miniprogram';

Page({
  data: {
    doctorList: [],
    isLoading: false,
    isEmpty: false,
    errorMsg: '' // 用于显示错误信息
  },

  onLoad() {
    this.fetchBoundDoctors();
  },

  onShow() {
    // 可选：当从添加医生页面返回时，刷新列表
    // 如果添加医生成功，可以考虑刷新此页面
    console.log('My doctor page onShow, refreshing list...');
    this.fetchBoundDoctors(); // 每次回到页面都刷新，确保列表最新
  },

  onPullDownRefresh() {
    // 下拉刷新
    this.fetchBoundDoctors(true); // true 表示是刷新操作
  },

  // 获取已绑定的医生列表
  async fetchBoundDoctors(isPullDown = false) { // 改为异步函数
    if (!isPullDown) {
      this.setData({ isLoading: true, isEmpty: false, errorMsg: '' });
    } else {
      this.setData({ errorMsg: '' }); // 下拉刷新时清除错误信息
    }

    try {
      const res = await request('/user/doctors', 'GET');

      console.log('获取我的医生列表成功:', res);

      // 假设后端返回的是医生对象列表，结构与 BoundDoctorOut Schema 兼容
      const doctorList = res || []; // 根据 request.js 封装方式调整，数据可能在 res.data 或 res.result 等

      this.setData({
        doctorList: doctorList,
        isEmpty: doctorList.length === 0,
        errorMsg: '' // 清除之前的错误
        // 如果有分页，这里需要更新 hasMore 和 page
        // hasMore: res.data.hasMore, // 假设后端返回分页信息
        // page: isPullDown ? 1 + 1 : this.data.page + 1, // 如果是加载更多，页码增加
      });

    } catch (err) {
      console.error('获取我的医生列表失败:', err);
      // 根据 request.js 封装方式，错误信息可能在 err.errMsg, err.data, err.statusCode 等
      const errorMessage = err.data?.detail || err.errMsg || '加载医生列表失败，请重试'; // 尝试获取后端返回的错误详情

      this.setData({
        doctorList: isPullDown ? [] : this.data.doctorList, // 下拉刷新失败清空列表，非刷新失败保留旧数据
        isEmpty: isPullDown ? true : this.data.doctorList.length === 0, // 如果清空了列表，则显示空状态
        errorMsg: errorMessage // 显示错误信息
      });
      Toast({
        context: this,
        selector: '#t-toast',
        message: errorMessage,
      });
    } finally {
      if (!isPullDown) {
        this.setData({ isLoading: false });
      } else {
        wx.stopPullDownRefresh(); // 停止下拉刷新动画
      }
    }
  },

  // 处理医生列表项点击事件 (跳转到聊天页)
  // 只有 status 为 'accepted' 的医生才能跳转聊天
  handleDoctorTap(e) {
    const doctor = e.currentTarget.dataset.doctor;
    console.log('点击了医生:', doctor);

    // 只有已绑定的医生可以聊天
    if (doctor.status === 'accepted') { // 根据后端返回的 status 字段判断

      // 将医生用户 ID 作为 URL 参数传递
      wx.navigateTo({
        url: `/pages/chat/index?userId=${doctor.id}`, // 将 doctorId 作为 URL 参数名，格式为 ?userId=...
        success: (res) => {
          console.log('跳转到聊天页面成功', res);
          const eventChannel = res.eventChannel; // 获取 eventChannel

          // 使用 eventChannel 将医生对象传递给聊天页
          // 'doctorInfo' 是你自定义的事件名称
          eventChannel.emit('doctorInfo', { doctor: doctor });

          console.log('通过 eventChannel 传递了医生信息:', doctor);

        },
        fail: (err) => {
          console.error('跳转到聊天页面失败:', err);
          Toast({
            context: this,
            selector: '#t-toast',
            message: err,
          });
        }
      });

      // TODO: 如果有相关的消息已读逻辑，在这里调用
      // 例如，如果这个页面显示了与医生聊天的未读消息数
      // this.setMessagesRead(doctor.id); // 假设你有这个函数

    } else if (doctor.status === 'pending') {
      // 如果是申请中的医生，点击可以有其他操作，例如查看申请状态详情
      console.log('点击了申请中的医生');
      Toast({
        context: this,
        selector: '#t-toast',
        message: '申请待医生确认',
      });
      // TODO: 可以导航到申请详情页，传递 doctor.id
    } else {
      // 其他状态（如 rejected, inactive），可能不应该出现在这个列表
      console.log(`点击了状态为 ${doctor.status} 的医生`);
      Toast({
        context: this,
        selector: '#t-toast',
        message: `该医生状态为 ${doctor.status}`,
      });
    }
  },

  /** 取消申请 */
  async cancelInvitation(e) {
    const bindingId = e.currentTarget.dataset.bindingId;
    if (!bindingId) return;

    this.setData({ isLoading: true });
    try {
      // 调用后端拒绝接口
      await request(`/bindings/cancel/${bindingId}`, 'PUT');
      Toast({
        context: this,
        selector: '#t-toast',
        message: '已取消申请'
      });
      // 从列表中取消这条申请（也可以改为标记状态为 rejected）
      const filtered = this.data.doctorList.filter(
        p => p.binding_id !== bindingId
      );
      this.setData({ doctorList: filtered });
    } catch (err) {
      console.error('取消失败', err);
      const msg = err.data?.detail || err.errMsg || '操作失败';
      Toast({
        context: this,
        selector: '#t-toast',
        message: msg
      });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  /** 解除绑定 */
  async deactivateBinding(e) {
    const bindingId = e.currentTarget.dataset.bindingId;
    if (!bindingId) return;

    this.setData({ isLoading: true });
    try {
      await request(`/bindings/${bindingId}`, 'DELETE');
      wx.showToast({ title: '解绑成功', icon: 'success' });

      // 从列表中移除
      const newList = this.data.doctorList.filter(item => item.binding_id !== bindingId);
      this.setData({ doctorList: newList });
    } catch (err) {
      wx.showToast({
        title: err.data?.detail || '解绑失败',
        icon: 'none'
      });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  // 跳转到添加医生页面
  navigateToAddDoctor() {
    console.log('跳转到添加医生页面');
    wx.navigateTo({
      url: '/pages/homeFunction/my-doctor/add-doctor/index',
      success: () => {
        console.log('跳转到添加医生页面成功');
      },
      fail: (err) => {
        console.error('跳转到添加医生页面失败:', err);
        wx.showToast({
          title: '跳转失败',
          icon: 'error'
        });
      }
    });
  }

  // TODO: 可选实现解除绑定功能 (左滑或长按)
  // handleUnbindDoctor(e) {
  //   const doctorId = e.currentTarget.dataset.doctorId;
  //   wx.showModal({
  //     title: '提示',
  //     content: '确定要解除与该医生的绑定关系吗？',
  //     success: (res) => {
  //       if (res.confirm) {
  //         console.log('用户点击确定解除绑定', doctorId);
  //         // 调用后端解除绑定 API
  //         // TODO: request({ url: `/api/v1/bindings/${doctorId}`, method: 'DELETE' })
  //         // .then(...) 成功后从列表中移除该医生并提示
  //         // .catch(...) 失败提示
  //       }
  //     }
  //   });
  // }

});