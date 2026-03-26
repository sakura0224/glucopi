const { request } = require('~/utils/request.js'); // 确认路径正确
import { Toast } from 'tdesign-miniprogram';
import { computeBindingButtonText } from './bind'; 

Page({
  data: {
    searchKeyword: '',
    searchResults: [],
    isSearching: false, // 是否正在搜索中
    searched: false, // 是否已经执行过搜索
    errorMsg: '' // 搜索错误信息
  },

  // 搜索关键词变化时更新数据
  handleKeywordChange(e) {
    this.setData({
      searchKeyword: e.detail.value,
      searched: false, // 关键词变化，重置搜索状态
      errorMsg: '' // 清除错误信息
    });
  },

  // 执行搜索
  async handleSearch() { // 改为异步函数
    const keyword = this.data.searchKeyword.trim();
    if (keyword === '') {
      this.setData({ searchResults: [], searched: true, errorMsg: '' }); // 关键词为空，清空列表，显示空状态或提示
      return;
    }

    this.setData({
      isSearching: true,
      searched: true, // 标记已搜索过
      searchResults: [], // 清空旧结果
      errorMsg: '' // 清空错误信息
    });

    try {
      const res = await request('/doctors/search', 'GET', { keyword: keyword });

      console.log('搜索医生成功:', res);

      // 假设后端返回的是医生对象列表，结构与 DoctorSearchItem Schema 兼容
      // DoctorSearchItem 应该包含 isBound 和 binding_status 字段
      const results = res || []; // 根据 request.js 封装方式调整
      // 后端返回的 DoctorSearchItem 应该已经包含了 binding_status
      // 前端不需要再自己计算 isBound/isBinding/isApplied，直接使用 binding_status
      const searchResults = results.map(doc => ({
        ...doc,
        buttonText: computeBindingButtonText(doc.binding_status, doc.isBinding),
        // 根据后端返回的 binding_status 字段，设置前端需要的 isBinding 状态用于按钮 loading
        isBinding: false // 默认不是正在申请中
      }));

      console.log(searchResults)

      this.setData({ searchResults: searchResults });

    } catch (err) {
      console.error('搜索医生失败:', err);
      const errorMessage = err.data?.detail || err.errMsg || '搜索医生失败，请重试';

      this.setData({
        searchResults: [],
        errorMsg: errorMessage // 显示错误信息
      });
      Toast({
        context: this,
        message: errorMessage,
        duration: 2000
      });

    } finally {
      this.setData({ isSearching: false });
    }
  },

  // 处理申请绑定按钮点击事件
  async handleRequestBinding(e) { // 改为异步函数
    const doctorId = e.currentTarget.dataset.doctorId;
    console.log('申请绑定医生:', doctorId);

    // 找到对应的医生项
    const index = this.data.searchResults.findIndex(doc => doc.id === doctorId);
    if (index === -1) {
      console.error('未找到医生信息');
      return;
    }

    const doctor = this.data.searchResults[index];

    // 根据后端返回的 binding_status 判断是否可点击
    if (doctor.binding_status === 'pending' || doctor.binding_status === 'accepted' || doctor.isBinding) { // isBinding 是前端状态
      console.log('医生已绑定或正在申请中，或前端已标记申请中');
      return;
    }

    // 更新前端状态为正在申请中 (isBinding)，禁用按钮
    const updatedResults = [...this.data.searchResults];
    updatedResults[index].isBinding = true;
    this.setData({ searchResults: updatedResults });

    try {
      const apiResponse = await request('/bindings/request', 'POST', { doctor_user_id: doctorId });

      console.log('申请绑定成功:', apiResponse);

      Toast({
        context: this,
        message: apiResponse.data?.message || '申请已发送',
        duration: 2000
      }); // 假设后端成功返回 message

      // 申请成功后，更新该医生项的绑定状态为 'pending'
      const resultsAfterRequest = [...this.data.searchResults];
      const updatedIndex = resultsAfterRequest.findIndex(doc => doc.id === doctorId);
      if (updatedIndex !== -1) {
        resultsAfterRequest[updatedIndex].isBinding = false; // 停止 loading
        resultsAfterRequest[updatedIndex].binding_status = 'pending'; // 更新绑定状态
        // resultsAfterRequest[updatedIndex].isApplied = true; // 如果前端需要这个标记可以保留
        this.setData({ searchResults: resultsAfterRequest });
      }

      // 可选：申请成功后提示用户并返回“我的医生”页面刷新列表
      // wx.navigateBack({ delta: 1 }); // 返回上一页

    } catch (err) {
      console.error('申请绑定失败:', err);
      const errorMessage = err.data?.detail || err.errMsg || '申请失败，请稍后再试';

      Toast({
        context: this,
        message: errorMessage,
        duration: 2000
      });

      // 申请失败后，将该医生状态的 isBinding 改回 false
      const resultsAfterRequest = [...this.data.searchResults];
      const updatedIndex = resultsAfterRequest.findIndex(doc => doc.id === doctorId);
      if (updatedIndex !== -1) {
        resultsAfterRequest[updatedIndex].isBinding = false;
        this.setData({ searchResults: resultsAfterRequest });
      }
    }
  }
});