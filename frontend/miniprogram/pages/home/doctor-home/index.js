// components/doctor-home/index.js
const { request } = require('~/utils/request');
import { Toast } from 'tdesign-miniprogram';
import ActionSheet, { ActionSheetTheme } from 'tdesign-miniprogram/action-sheet/index';

Component({
  /** 外部传入的属性，这里留空或根据需要添加 */
  properties: {},

  /** 组件内部状态 */
  data: {
    patientList: [],   // [{ id, nickname, avatar_url, binding_id, status, recent_glucose? }]
    isLoading: false,  // 加载状态
    errorMsg: '',       // 拉取失败时显示
    selectedPatientId: '',   // ← 新增，用来暂存点击哪位患者
  },

  /** 组件生命周期 */
  lifetimes: {
    attached() {
      // 组件一挂载就拉数据
      this.fetchPatients();
    }
  },

  methods: {
    /** 刷新页面 */
    async refreshPatients() {
      await this.fetchPatients();
    },

    /** 拉取 pending + accepted 的患者列表 */
    async fetchPatients() {
      this.setData({ isLoading: true, errorMsg: '' });
      try {
        const res = await request('/user/patients', 'GET');
        console.log(res)
        const list = res || [];
        this.setData({
          patientList: list,
          isLoading: false
        });
      } catch (err) {
        console.error('获取患者列表失败', err);
        const msg = err.data?.detail || err.errMsg || '加载失败';
        Toast({
          context: this,
          selector: '#t-toast',
          message: msg
        });
        this.setData({
          isLoading: false,
          errorMsg: msg
        });
      }
    },

    /** 接受患者申请 */
    async acceptInvitation(e) {
      const bindingId = e.currentTarget.dataset.bindingId;
      if (!bindingId) return;

      this.setData({ isLoading: true });
      try {
        // PUT /bindings/accept/{binding_id}
        await request(`/bindings/accept/${bindingId}`, 'PUT');
        Toast({
          context: this,
          selector: '#t-toast',
          message: '已接受邀请'
        });
        // 本地更新状态
        const updated = this.data.patientList.map(p =>
          p.binding_id === bindingId
            ? { ...p, status: 'accepted' }
            : p
        );
        this.setData({ patientList: updated, isLoading: false });
      } catch (err) {
        console.error('接受失败', err);
        const msg = err.data?.detail || err.errMsg || '操作失败';
        Toast({
          context: this,
          selector: '#t-toast',
          message: msg
        });
        this.setData({ isLoading: false });
      }
    },

    /** 拒绝患者申请 */
    async rejectInvitation(e) {
      const bindingId = e.currentTarget.dataset.bindingId;
      if (!bindingId) return;

      this.setData({ isLoading: true });
      try {
        // 调用后端拒绝接口
        await request(`/bindings/reject/${bindingId}`, 'PUT');
        Toast({
          context: this,
          selector: '#t-toast',
          message: '已拒绝申请'
        });
        // 从列表中移除这条申请（也可以改为标记状态为 rejected）
        const filtered = this.data.patientList.filter(
          p => p.binding_id !== bindingId
        );
        this.setData({ patientList: filtered });
      } catch (err) {
        console.error('拒绝失败', err);
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
        Toast({
          context: this,
          selector: '#t-toast',
          message: '解绑成功'
        });

        // 从列表中移除
        const newList = this.data.patientList.filter(item => item.binding_id !== bindingId);
        this.setData({ patientList: newList });
      } catch (err) {
        Toast({
          context: this,
          selector: '#t-toast',
          message: err.data?.detail || '解绑失败'
        });
      } finally {
        this.setData({ isLoading: false });
      }
    },

    /** 点击“聊天”按钮 */
    startChat(e) {
      const patientId = e.currentTarget.dataset.patientId;
      if (!patientId) return;
      wx.navigateTo({
        url: `/pages/chat/index?userId=${patientId}`
      });
    },

    // /** 点击整行（已接受状态也能点聊天） */
    // onCellTap(e) {
    //   const item = e.currentTarget.dataset.patient;
    //   if (item.status === 'accepted') {
    //     wx.navigateTo({
    //       url: `/pages/chat/index?userId=${item.id}`
    //     });
    //   }
    // },

    /** 患者详情 */
    onCellTap(e) {
      const item = e.currentTarget.dataset.patient;
      if (item.status !== 'accepted') {
        Toast({
          context: this,
          selector: '#t-toast',
          message: '尚未接受该用户'
        });
        return;
      }

      // 先把 patientId 存下来
      this.setData({ selectedPatientId: item.id });

      ActionSheet.show({
        theme: ActionSheetTheme.List,
        selector: '#t-action-sheet',
        context: this,
        description: '点击查看患者的数据',
        items: [
          {
            label: '每日记录',
          },
          {
            label: '血糖趋势',
          },
        ],
      });
    },

    /** 患者详情 */
    handleSelected(e) {
      const idx = e.detail.index;
      const pid = this.data.selectedPatientId;
      console.log(pid)
      if (!pid) return;

      switch (idx) {
        case 0:
          wx.navigateTo({
            url: `/pages/homeFunction/record/index?user_id=${pid}`
          });
          break;
        case 1:
          wx.navigateTo({
            url: `/pages/homeFunction/trend/index?user_id=${pid}`
          });
          break;
        default:
          break;
      }
    },
  }
});
