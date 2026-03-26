// pages/my/profile-doctor/index.js

const { request } = require('~/utils/request.js'); // 根据你的文件结构调整路径
import { Toast } from 'tdesign-miniprogram';

Page({
  data: {
    isLoading: false,
    profileData: {
      title: '',
      department: '',
      hospital: '',
      specialization: '',
      registration_number: '',
    },
  },

  onLoad() {
    // 在页面加载时获取患者档案数据
    this.fetchPatientProfile();
  },

  onReady() {
  },

  async fetchPatientProfile() {
    this.setData({ isLoading: true });
    try {
      // 调用 GET /api/v1/user/me 获取用户完整信息，包括 doctor_profile
      const res = await request('/user/me', 'GET');
      console.log('获取用户档案信息成功:', res);

      // 假设后端返回的是 UserOut Schema，其中包含 doctor_profile 嵌套对象
      const user = res; // UserOut 对象

      if (user && user.role === 'doctor' && user.doctor_profile) {
        const profile = user.doctor_profile; // DoctorProfileOut 对象

        // 将获取到的数据设置到页面状态
        this.setData({
          profileData: {
            // 将数字转为字符串显示在 input，null 转为''
            title: profile.title !== null ? String(profile.title) : '未获取到信息，请联系管理员',
            department: profile.department !== null ? String(profile.department) : '未获取到信息，请联系管理员',
            hospital: profile.hospital !== null ? String(profile.hospital) : '未获取到信息，请联系管理员',
            specialization: profile.specialization !== null ? String(profile.specialization) : '未获取到信息，请联系管理员',
            registration_number: profile.registration_number !== null ? String(profile.registration_number) : '未获取到信息，请联系管理员',
          }
        });
      } else {
        console.error('获取用户档案信息失败：非医生用户或档案不存在');
        Toast({ context: this, selector: '#t-toast', message: '无法加载个人档案', icon: 'error' });
        // 可以导航回我的页面
        wx.navigateBack();
      }

    } catch (err) {
      console.error('获取用户档案信息失败:', err);
      Toast({ context: this, selector: '#t-toast', message: err.data?.detail || err.errMsg || '加载档案信息失败', icon: 'error' });
    } finally {
      this.setData({ isLoading: false });
    }
  },
});