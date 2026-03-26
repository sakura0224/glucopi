// pages/my/profile/index.js

// --- 导入 request 工具函数 ---
const { request } = require('~/utils/request.js'); // 根据你的文件结构调整路径
// --- 导入 Toast ---
import { Toast } from 'tdesign-miniprogram';

// 简单的 ISO 字符串转 YYYY-MM-DD 格式显示函数
function formatDateString(isoString) {
  if (!isoString) return '';
  try {
    // --- 修改这里：使用兼容格式创建 Date 对象 ---
    // new Date() 可以解析 ISO 8601 字符串 (YYYY-MM-DDTHH:mm:ssZ 或 YYYY-MM-DDTHH:mm:ss+HH:mm)
    // 如果你的 ISO 字符串是纯 YYYY-MM-DD，也应该可以被 new Date() 解析 (但时间会是 00:00:00 当地时间)
    // 如果需要更健壮的解析，可以使用 time.to_utc() 或 date-fns 的 parseISO
    const dateObj = new Date(isoString); // <-- 确保这里的 isoString 是有效的 ISO 格式
    // --- 修改结束 ---
    if (isNaN(dateObj.getTime())) {
      console.warn("Invalid date object from ISO string:", isoString);
      return '无效日期';
    }
    const year = dateObj.getFullYear();
    const month = ('0' + (dateObj.getMonth() + 1)).slice(-2);
    const day = ('0' + dateObj.getDate()).slice(-2);
    return `${year}-${month}-${day}`;
  } catch (e) {
    console.error("Error formatting date string:", e);
    return '格式错误';
  }
}


Page({
  data: {
    isLoading: false,
    isSaving: false,
    profileData: {
      height: '',
      weight: '',
      diagnosed_at: null, // ISO 字符串或 null
      target_glucose_min: '',
      target_glucose_max: '',
      medication_plan: null, // 可以是字符串或 null
    },
    // 用于日期选择器
    showDatePicker: false,
    diagnosedDateValue: null, // 日期选择器绑定的值 (毫秒时间戳)

    // Toast 实例
    // toast: null,
  },

  onLoad() {
    // 在页面加载时获取患者档案数据
    this.fetchPatientProfile();
  },

  onReady() {
    // 获取 Toast 实例
    // this.toast = this.selectComponent('#t-toast');
  },

  // 提供一个 WXML 中使用的格式化函数
  formatDisplayDate(isoString) {
    return formatDateString(isoString);
  },

  async fetchPatientProfile() {
    this.setData({ isLoading: true });
    try {
      // 调用 GET /api/v1/user/me 获取用户完整信息，包括 patient_profile
      const res = await request('/user/me', 'GET');
      console.log('获取用户档案信息成功:', res);

      // 假设 request.js 返回整个 res 对象，数据体在 res.data
      // 假设后端返回的是 UserOut Schema，其中包含 patient_profile 嵌套对象
      const user = res; // UserOut 对象

      if (user && user.role === 'patient' && user.patient_profile) {
        const profile = user.patient_profile; // PatientProfileOut 对象

        // 将获取到的数据设置到页面状态
        this.setData({
          profileData: {
            // 将数字转为字符串显示在 input，null 转为''
            height: profile.height !== null ? String(profile.height) : '',
            weight: profile.weight !== null ? String(profile.weight) : '',
            diagnosed_at: profile.diagnosed_at || null, // 从后端获取的 ISO 字符串或 null
            target_glucose_min: profile.target_glucose_min !== null ? String(profile.target_glucose_min) : '',
            target_glucose_max: profile.target_glucose_max !== null ? String(profile.target_glucose_max) : '',
            // 确保 medication_plan 如果是 null 也显示为 '' 在 textarea 中
            medication_plan: profile.medication_plan !== null ? profile.medication_plan : '',
          }
        });

        // 如果 diagnosed_at 有值，将其转换为毫秒时间戳以便日期选择器初始化
        if (this.data.profileData.diagnosed_at) {
          try {
            // --- 修改这里：确保使用 Date 对象或时间戳初始化选择器 ---
            // new Date() 可以解析 ISO 8601 字符串
            const dateObj = new Date(this.data.profileData.diagnosed_at);
            if (!isNaN(dateObj.getTime())) {
              this.setData({
                diagnosedDateValue: dateObj.getTime() // 将 Date 对象转为毫秒时间戳
              });
            } else {
              console.warn("Invalid diagnosed_at date string from backend:", this.data.profileData.diagnosed_at);
              this.setData({ diagnosedDateValue: null }); // 无效日期，选择器值设为 null
            }
            // --- 修改结束 ---
          } catch (e) {
            console.error("Error parsing diagnosed_at date string from backend:", e);
            this.setData({ diagnosedDateValue: null }); // 解析错误，选择器值设为 null
          }
        } else {
          this.setData({ diagnosedDateValue: null }); // 后端返回 null，选择器值也设为 null
        }
      } else {
        console.error('获取用户档案信息失败：非患者用户或档案不存在');
        Toast({ context: this, selector: '#t-toast', message: '无法加载健康档案', icon: 'error' });
        // 可以导航回我的页面
        // wx.navigateBack();
      }


    } catch (err) {
      console.error('获取用户档案信息失败:', err);
      Toast({ context: this, selector: '#t-toast', message: err.data?.detail || err.errMsg || '加载档案信息失败', icon: 'error' });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  // 输入框值变化时更新 data
  onInputChange(e) {
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value;
    this.setData({
      [`profileData.${field}`]: value,
    });
  },

  // 打开诊断日期选择器
  onOpenDatePicker() {
    // 初始化选择器值
    const initialDate = this.data.profileData.diagnosed_at ? new Date(this.data.profileData.diagnosed_at) : new Date();
    const initialTimestamp = isNaN(initialDate.getTime()) ? new Date().getTime() : initialDate.getTime();

    this.setData({
      showDatePicker: true,
      diagnosedDateValue: initialTimestamp,
    });
  },

  // 关闭诊断日期选择器
  onCloseDatePicker() {
    this.setData({ showDatePicker: false });
  },

  // 诊断日期选择确认时
  onDiagnosedDateConfirm(e) {
    const dateValue = e.detail.value; // TDesign 传递的时间戳 (毫秒)
    console.log('日期选择确认 (时间戳):', dateValue);

    // 将选择的值转换为 YYYY-MM-DD 格式字符串
    let dateString = null;
    if (dateValue !== null && dateValue !== undefined) { // 确保选中了日期
      const dateObj = new Date(dateValue); // 将毫秒时间戳转为 Date 对象
      if (!isNaN(dateObj.getTime())) {
        // --- 修改这里：转为 YYYY-MM-DD 格式字符串 ---
        const year = dateObj.getFullYear();
        const month = ('0' + (dateObj.getMonth() + 1)).slice(-2);
        const day = ('0' + dateObj.getDate()).slice(-2);
        dateString = `${year}-${month}-${day}`; // <-- 生成 YYYY-MM-DD 字符串
        console.log('格式化为 YYYY-MM-DD:', dateString); // 添加日志确认格式
        // --- 修改结束 ---
      } else {
        console.error("Invalid date value from picker:", dateValue);
      }
    }

    this.setData({
      // --- 修改这里：存储 YYYY-MM-DD 字符串或 null ---
      'profileData.diagnosed_at': dateString, // <--- 存储 YYYY-MM-DD 字符串
      // --- 修改结束 ---
      diagnosedDateValue: dateValue, // 更新选择器绑定的值 (保持时间戳)
      showDatePicker: false, // 关闭选择器
    });
  },


  // 提交表单
  async onSubmit() {
    // --- 前端手动验证 ---
    // 例如，检查数字字段是否是有效数字
    const { height, weight, target_glucose_min, target_glucose_max } = this.data.profileData;
    if (height !== '' && (isNaN(parseFloat(height)) || parseFloat(height) <= 0)) {
      Toast({ context: this, selector: '#t-toast', message: '请输入有效的身高', icon: 'none' });
      return;
    }
    if (weight !== '' && (isNaN(parseFloat(weight)) || parseFloat(weight) <= 0)) {
      Toast({ context: this, selector: '#t-toast', message: '请输入有效的体重', icon: 'none' });
      return;
    }
    if ((target_glucose_min !== '' || target_glucose_max !== '') && (isNaN(parseFloat(target_glucose_min)) || isNaN(parseFloat(target_glucose_max)))) {
      Toast({ context: this, selector: '#t-toast', message: '请输入有效的目标血糖范围', icon: 'none' });
      return;
    }
    if (target_glucose_min !== '' && target_glucose_max !== '' && parseFloat(target_glucose_min) >= parseFloat(target_glucose_max)) {
      Toast({ context: this, selector: '#t-toast', message: '目标血糖最低值应小于最高值', icon: 'none' });
      return;
    }
    // TODO: 添加其他验证规则
    // --- 前端手动验证结束 ---


    console.log('提交档案数据:', this.data.profileData);


    this.setData({ isSaving: true });

    try {
      // 准备要提交的数据
      // 需要将输入框的字符串转为数字或 null (如果为空)
      // 如果字段允许为空，空字符串 "" 应该转为 null
      // 如果字段是数字类型，需要进行 parseFloat 转换
      const dataToSubmit = {
        height: this.data.profileData.height !== '' ? parseFloat(this.data.profileData.height) : null,
        weight: this.data.profileData.weight !== '' ? parseFloat(this.data.profileData.weight) : null,
        diagnosed_at: this.data.profileData.diagnosed_at || null, // ISO 字符串或 null
        target_glucose_min: this.data.profileData.target_glucose_min !== '' ? parseFloat(this.data.profileData.target_glucose_min) : null,
        target_glucose_max: this.data.profileData.target_glucose_max !== '' ? parseFloat(this.data.profileData.target_glucose_max) : null,
        medication_plan: this.data.profileData.medication_plan || null, // 文本域如果为空也转 null
      };

      console.log("待提交数据为：", dataToSubmit)

      // 调用 PUT /api/v1/user/profile/patient API 提交数据
      const res = await request('/user/profile/patient', 'PUT', dataToSubmit); // PUT 请求，数据在请求体
      console.log('保存档案信息成功:', res);

      Toast({ context: this, selector: '#t-toast', message: '档案信息保存成功', icon: 'success' });

      // 保存成功后，可以导航回去或者提示
      wx.navigateBack(); // 导航回我的页面，my 页面的 onShow 会刷新数据

    } catch (err) {
      console.error('保存档案信息失败:', err);
      Toast({ context: this, selector: '#t-toast', message: err.data?.detail || err.errMsg || '档案信息保存失败', icon: 'error' });
    } finally {
      this.setData({ isSaving: false });
    }
  },

});