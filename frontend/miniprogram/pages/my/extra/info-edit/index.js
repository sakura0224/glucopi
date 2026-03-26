const { request } = require('~/utils/request');

Page({
  data: {
    isLoading: false,
    personInfo: {
      avatar_url: '',
      nickname: '',
      gender: 0,
      birthday: '',
    },
    genderOptions: [
      {
        label: '男',
        value: 0,
      },
      {
        label: '女',
        value: 1,
      },
      {
        label: '保密',
        value: 2,
      },
    ],
    birthVisible: false,
    birthStart: '1970-01-01',
    birthEnd: '2025-03-01',
    birthTime: 0,
    birthFilter: (type, options) => (type === 'year' ? options.sort((a, b) => b.value - a.value) : options),
    addressText: '',
    addressVisible: false,
    provinces: [],
    cities: [],

    gridConfig: {
      column: 3,
      width: 160,
      height: 160,
    },
  },

  async onLoad() {
    await this.getPersonalInfo();
  },

  async getPersonalInfo() {
    await request('/user/me', 'GET').then((res) => {
      this.setData(
        {
          personInfo: res,
        },
      );
    })
  },

  showPicker(e) {
    const { mode } = e.currentTarget.dataset;
    this.setData({
      [`${mode}Visible`]: true,
    });
    if (mode === 'address') {
      const cities = this.getCities(this.data.personInfo.address[0]);
      this.setData({ cities });
    }
  },

  hidePicker(e) {
    const { mode } = e.currentTarget.dataset;
    this.setData({
      [`${mode}Visible`]: false,
    });
  },

  onPickerChange(e) {
    const { value, label } = e.detail;
    const { mode } = e.currentTarget.dataset;

    this.setData({
      [`personInfo.birthday`]: value,
    });
  },

  personInfoFieldChange(field, e) {
    const { value } = e.detail;
    this.setData({
      [`personInfo.${field}`]: value,
    });
  },

  onNameChange(e) {
    this.personInfoFieldChange('nickname', e);
  },

  onGenderChange(e) {
    this.personInfoFieldChange('gender', e);
  },
  // 辅助函数：上传图片到图床，并返回图片的公网 URL
  async uploadAvatarToCdn(localFilePath) {
    return new Promise((resolve, reject) => {
      wx.uploadFile({
        url: 'https://cdn.ayane.top/upload', // <-- 你的图床上传接口 URL
        filePath: localFilePath,
        name: 'file', // <-- 这个 'file' 必须和你的 FastAPI 上传接口参数名一致 (UploadFile = File(...))
        formData: {}, // 如果你的上传接口需要其他表单数据，可以在这里添加
        success: (res) => {
          // wx.uploadFile 的 res.data 是一个字符串，需要手动解析 JSON
          try {
            const result = JSON.parse(res.data);
            if (res.statusCode === 200 && result && result.url_path) {
              // 拼接完整的公网 URL
              const publicUrl = `https://cdn.ayane.top${result.url_path}`; // <-- 你的图床域名和返回的url_path拼接
              console.log("Avatar uploaded successfully:", publicUrl);
              resolve(publicUrl);
            } else {
              console.error("Upload failed or response format incorrect:", res);
              reject(new Error('Upload failed or response format incorrect.'));
            }
          } catch (e) {
            console.error("Failed to parse upload response:", e, res.data);
            reject(new Error('Failed to parse upload response.'));
          }
        },
        fail: (err) => {
          console.error("wx.uploadFile failed:", err);
          reject(err);
        }
      });
    });
  },

  onChooseAvatar(e) {
    // onChooseAvatar 返回的是一个临时文件路径
    const avatar = e.detail.avatarUrl; // 注意：这里是 avatarUrl，不是 avatar_url
    console.log(avatar)

    this.setData({
      // 暂时保存本地临时路径，等待保存时再上传
      "personInfo.avatar_url": avatar,
    });
    // 可以选择在这里预览本地图片
    // this.setData({ "previewAvatar": avatar });
  },

  async onSaveInfo() {
    const { nickname, gender, avatar_url, birthday } = this.data.personInfo;

    if (!nickname) {
      wx.showToast({ title: '请输入昵称', icon: 'none' });
      return;
    }

    this.setData({ isLoading: true });

    let final_avatar_url = avatar_url; // 默认使用当前 avatar_url (可能是旧的公网URL或未选择新头像)

    // 核心逻辑：检查 avatar_url 是否是本地临时路径，如果是，则先上传
    // 小程序 onChooseAvatar 返回的临时路径通常以 'wxfile://' 开头
    // 或者是一个长字符串表示临时文件。一个简单的判断方式是看它是否以 http(s) 开头。
    if (avatar_url && !avatar_url.startsWith('http://') && !avatar_url.startsWith('https://')) {
      console.log("Local avatar path detected, uploading:", avatar_url);
      try {
        // 调用上传辅助函数，等待上传完成并获取公网 URL
        final_avatar_url = await this.uploadAvatarToCdn(avatar_url);
        console.log("Got public avatar URL:", final_avatar_url);

        // 上传成功后，更新 personInfo 中的 avatar_url 为公网 URL
        this.setData({ "personInfo.avatar_url": final_avatar_url });

      } catch (uploadError) {
        console.error("Avatar upload failed:", uploadError);
        wx.showToast({ title: '头像上传失败，请重试', icon: 'none' });
        this.setData({ isLoading: false });
        // 如果头像上传失败，可以选择中断保存流程，或者只保存其他信息
        return; // 中断保存流程
        // 或者：继续保存其他信息，头像字段可能还是旧值或空值
        // final_avatar_url = this.data.personInfo.avatar_url; // 保留旧值或初始值
      }
    } else {
      console.log("Avatar URL is not a local path, skipping upload.");
    }


    // **使用最终确定的 avatar URL 调用后端接口**
    try {
      // 将 final_avatar_url 传递给后端
      await request('/user/profile', 'PUT', { nickname, gender, avatar_url: final_avatar_url, birthday });

      wx.showToast({ title: '修改成功', icon: 'success' });
      setTimeout(() => {
        // 根据你的实际页面跳转逻辑调整
        // wx.reLaunch({ url: '/pages/my/index' });
        wx.navigateBack(); // 修改成功后返回上一页通常是更好的用户体验
      }, 600);

    } catch (err) {
      console.error("Backend profile update failed:", err);
      wx.showToast({ title: '修改失败，请重试', icon: 'none' });
    } finally {
      this.setData({ isLoading: false });
    }
  }
});
