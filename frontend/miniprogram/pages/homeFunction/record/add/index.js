const { request } = require('~/utils/request.js');
import { Toast } from 'tdesign-miniprogram';
const GlucoseConverter = require('~/pages/homeFunction/glucoseConverter.js');

Page({
  data: {
    // Glucose fields
    glucose: '',
    tag: 'fasting', // Default glucose tag

    // Insulin fields
    dose: '', // 剂量
    insulinType: '', // 胰岛素类型 (basal, bolus, mixed)

    // Diet fields
    carbs: '', // 碳水
    mealType: '', // 餐次类型 (breakfast, lunch, dinner, snack)
    dietDescription: '', // 饮食描述

    // General note
    note: '', // 通用备注

    // UI
    encouragementText: '',
  },

  onLoad(options) {
    // options.type might contain 'glucose', 'insulin', 'diet' if needed later,
    // but per requirement, we show all fields regardless.
    this.setData({
      encouragementText: this.getRandomEncouragement()
    });
  },

  getRandomEncouragement() {
    const list = [
      "记录一下，更健康 👍", "你在变好，加油 💪", "坚持，是最好的照顾",
      "健康，从记录开始 📝", "一点一滴，都算努力", "每次记录都值得鼓励",
      "继续坚持，很棒哦！✨", "你的健康，你做主 💚", "慢慢来，也在进步",
      "很棒，坚持住就对了",
    ];
    const index = Math.floor(Math.random() * list.length);
    return list[index];
  },

  // --- Event Handlers ---
  onGlucoseChange(e) { this.setData({ glucose: e.detail.value }); },
  onTagChange(e) { this.setData({ tag: e.detail.value }); },
  onDoseChange(e) { this.setData({ dose: e.detail.value }); },
  onInsulinTypeChange(e) { this.setData({ insulinType: e.detail.value }); },
  onCarbsChange(e) { this.setData({ carbs: e.detail.value }); },
  onMealTypeChange(e) { this.setData({ mealType: e.detail.value }); },
  onDietDescriptionChange(e) { this.setData({ dietDescription: e.detail.value }); },
  onNoteChange(e) { this.setData({ note: e.detail.value }); },

  // --- Navigation ---
  onNavigate() {
    // Consider using navigateBack if appropriate, or reLaunch as you have it
    wx.navigateBack({ delta: 1 }).catch(() => {
      wx.reLaunch({ url: '/pages/home/index' }); // Fallback if navigateBack fails
    });
    // wx.reLaunch({ url: '/pages/patient/record/index' }); // Or navigate back to the record list
  },

  // --- Form Submission ---
  async onSubmit() {
    const {
      glucose, tag,
      dose, insulinType,
      carbs, mealType, dietDescription,
      note
    } = this.data;

    // --- Validation ---
    if (!glucose) {
      this.showToast('请填写血糖值');
      return;
    }
    // Convert to numbers for validation and payload
    const glucoseValue = parseFloat(glucose);
    const doseValue = dose ? parseFloat(dose) : 0;
    const carbsValue = carbs ? parseFloat(carbs) : 0;

    if (isNaN(glucoseValue) || glucoseValue <= 0) {
      this.showToast('血糖值必须是有效的正数');
      return;
    }

    // --- Perform Conversion from mmol/L to mg/dL for Backend ---
    // 确保 GlucoseConverter 模块已正确加载且包含 mmolLToMgdl 方法
    if (!GlucoseConverter || typeof GlucoseConverter.mmolLToMgdl !== 'function') {
      console.error("GlucoseConverter module or mmolLToMgdl function not available!");
      this.showToast('血糖转换模块未加载或异常'); // 给用户提示，也方便排查问题
      return; // 阻止提交
    }

    const glucoseValueMgdl = GlucoseConverter.mmolLToMgdl(glucoseValue); // 调用转换函数

    if (dose && (isNaN(doseValue) || doseValue <= 0)) {
      this.showToast('胰岛素剂量必须是有效的正数');
      return;
    }
    if (carbs && (isNaN(carbsValue) || carbsValue < 0)) { // Carbs can be 0
      this.showToast('碳水值必须是有效的数字');
      return;
    }


    // Conditional validation
    if (doseValue > 0 && !insulinType) {
      this.showToast('请选择胰岛素类型');
      return;
    }
    if (carbsValue > 0 && !mealType) { // Allow carbs=0 without meal type
      this.showToast('请选择餐次类型');
      return;
    }

    // --- Construct Payload ---
    const payload = {
      // Always include timestamp and glucose
      timestamp: new Date().toISOString(),
      glucose: glucoseValueMgdl,
      tag: tag, // Glucose tag
    };

    // Add insulin data if dose is provided
    if (doseValue > 0 && insulinType) {
      payload.insulin = {
        dose: doseValue,
        type: insulinType,
      };
    }

    // Add diet data if carbs or description is provided
    // Only add mealType if carbs > 0
    if (carbsValue > 0 || dietDescription) {
      payload.diet = {};
      if (carbsValue >= 0) { // Include carbs if 0 or more
        payload.diet.carbs = carbsValue;
        if (mealType) { // Only include mealType if carbs were entered
          payload.diet.meal_type = mealType;
        }
      }
      if (dietDescription) {
        payload.diet.description = dietDescription;
      }
      // Ensure diet object is added only if it has content
      if (Object.keys(payload.diet).length === 0) {
        delete payload.diet;
      }
    }


    // Add general note if provided
    if (note) {
      payload.note = note;
    }

    console.log('Submitting Payload:', payload);

    // --- API Call ---
    // IMPORTANT: Replace '/api/v1/record/add' with your actual combined endpoint URL
    const endpoint = '/record/add'; // Placeholder for the combined endpoint

    wx.showLoading({ title: '提交中...' }); // Show loading indicator

    try {
      // Assuming your request function handles base URL and auth
      const res = await request(endpoint, 'POST', payload);
      wx.hideLoading(); // Hide loading
      Toast({
        context: this,
        selector: '#t-toast',
        message: res.message || '记录成功', // 使用后端返回的消息
        theme: 'success',
        duration: 1500,
      });
      setTimeout(() => {
        this.onNavigate();
      }, 1500);

    } catch (err) {
      wx.hideLoading(); // Hide loading
      console.error("Submission failed:", err);
      // Try to get error message from backend response if available
      const errorMessage = err?.data?.message || err?.errMsg || '提交失败，请重试';
      Toast({
        context: this,
        selector: '#t-toast',
        message: errorMessage,
        theme: 'error',
      });
    }
  },

  // Helper for Toast
  showToast(message) {
    Toast({
      context: this,
      selector: '#t-toast',
      message: message,
      theme: 'warning', // Use warning theme for validation errors
      duration: 2000,
    });
  }
});