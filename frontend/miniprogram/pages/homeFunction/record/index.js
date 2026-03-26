const { request } = require('~/utils/request.js');
const { formatTimestamp } = require('./formatTimestamp');
const GlucoseConverter = require('~/pages/homeFunction/glucoseConverter.js');

Page({
  data: {
    activeTab: 0, // 0: 血糖, 1: 胰岛素, 2: 饮食
    // 各个 Tab 的配置信息 (核心修改区域)
    tabsConfig: [
      { // --- 血糖配置 (Index 0) ---
        name: 'glucose',
        apiEndpoint: '/glucose/getPagedBloodRecords', // API 端点
        filterParamName: 'tag', // API 用于过滤的参数名
        filters: {
          // value: 'all', // value 由 tabsDataState 管理
          options: [
            { value: 'all', label: '全部记录' },
            { value: 'fasting', label: '空腹' },
            { value: 'postprandial', label: '餐后' },
            { value: 'random', label: '随机' },
          ],
        },
        sorters: {
          // value: 'default', // value 由 tabsDataState 管理
          options: [
            // 注意：这里的 value 应该直接对应 API 的 sort 参数值
            { value: 'time_desc', label: '时间降序' }, // 'default' 映射到 'time_desc'
            { value: 'time_asc', label: '时间升序' },
            { value: 'glucose_desc', label: '血糖降序' },
            { value: 'glucose_asc', label: '血糖升序' },
          ],
        },
        tagMap: { // 用于将 API 返回的 tag 值映射为显示文本
          fasting: '空腹',
          postprandial: '餐后',
          random: '随机'
        },
        displayFormatter: (item) => {
          // 调用血糖转换函数，将 mg/dL 转换为 mmol/L
          const mmolLValue = GlucoseConverter.mgdlToMmolL(item.glucose);

          // 检查转换是否成功 (如果输入无效会返回 NaN)
          const displayGlucose = isNaN(mmolLValue) ? item.glucose : mmolLValue;
          const displayUnit = isNaN(mmolLValue) ? 'mg/dL' : 'mmol/L'; // 如果转换失败，仍然显示原始单位

          return {
            // 将 title 字符串更新为显示 mmol/L 值和单位
            title: `${displayGlucose} ${displayUnit}`,
            description: `${item.tagStr} ｜ ${item.timeStr}`,
            note: item.note,
          };
        },
      },
      { // --- 胰岛素配置 (Index 1) ---
        name: 'insulin',
        apiEndpoint: '/insulin/getPagedInsulinRecords', // API 端点
        filterParamName: 'type', // API 用于过滤的参数名 (根据后端是 type)
        filters: {
          options: [
            { value: 'all', label: '全部类型' },
            { value: 'basal', label: '基础' },
            { value: 'bolus', label: '餐时' },
            { value: 'mixed', label: '预混' },
          ],
        },
        sorters: {
          options: [
            { value: 'time_desc', label: '时间降序' },
            { value: 'time_asc', label: '时间升序' },
            { value: 'dose_desc', label: '剂量降序' },
            { value: 'dose_asc', label: '剂量升序' },
          ],
        },
        tagMap: { // 将 API 返回的 type 值映射为显示文本
          basal: '基础',
          bolus: '餐时',
          mixed: '预混'
        },
        displayFormatter: (item) => ({
          title: `${item.dose} U`, // 显示剂量
          // 假设 API 返回的字段是 type, 通过 tagMap 转换成 tagStr
          description: `${item.tagStr} ｜ ${item.timeStr}`,
          note: item.note,
        }),
      },
      { // --- 饮食配置 (Index 2) ---
        name: 'diet',
        apiEndpoint: '/diet/getPagedDietRecords', // API 端点
        filterParamName: 'meal_type', // API 用于过滤的参数名 (根据后端是 meal_type)
        filters: {
          options: [
            { value: 'all', label: '全部餐次' },
            { value: 'breakfast', label: '早餐' },
            { value: 'lunch', label: '午餐' },
            { value: 'dinner', label: '晚餐' },
            { value: 'snack', label: '加餐' },
          ],
        },
        sorters: {
          options: [
            { value: 'time_desc', label: '时间降序' },
            { value: 'time_asc', label: '时间升序' },
            { value: 'carbs_desc', label: '碳水降序' },
            { value: 'carbs_asc', label: '碳水升序' },
          ],
        },
        tagMap: { // 将 API 返回的 meal_type 值映射为显示文本
          breakfast: '早餐',
          lunch: '午餐',
          dinner: '晚餐',
          snack: '加餐'
        },
        displayFormatter: (item) => ({
          title: `${item.carbs} g 碳水`, // 显示碳水克数
          // 假设 API 返回的字段是 meal_type, 通过 tagMap 转换成 tagStr
          description: `${item.tagStr} ｜ ${item.timeStr}`,
          // 饮食记录可能用 description 字段记录食物详情，优先显示 description，否则显示 note
          note: item.description || item.note,
        }),
      },
    ],
    // 各个 Tab 的动态数据状态 (结构不变，但 filterValue 和 sorterValue 的初始值应与 config 对应)
    tabsDataState: [
      { // 血糖状态
        recordList: [], currentPage: 1, pageSize: 20, hasMore: true, isLoadingMore: false, filterValue: 'all', sorterValue: 'time_desc' // 默认值与 sorters[0].value 对应
      },
      { // 胰岛素状态
        recordList: [], currentPage: 1, pageSize: 20, hasMore: true, isLoadingMore: false, filterValue: 'all', sorterValue: 'time_desc'
      },
      { // 饮食状态
        recordList: [], currentPage: 1, pageSize: 20, hasMore: true, isLoadingMore: false, filterValue: 'all', sorterValue: 'time_desc'
      },
    ],
    scrollTop: 0,
    navbarHeight: 0,
    user_id: '',
  },

  /**
   * 生命周期函数--监听页面加载
   */
  onLoad(options) {
    if (options) {
      const user_id = options.user_id;
      this.setData({
        user_id,
        scrollTop: { type: Number, value: 0 },
        navbarHeight: {
          type: Number,
          value: 0,
        },
      });
    } else {
      this.setData({
        scrollTop: { type: Number, value: 0 },
        navbarHeight: {
          type: Number,
          value: 0,
        },
      });
    }
    this.loadTabData(this.data.activeTab, true);
  },

  /**
   * 生命周期函数--监听页面显示
   */
  onShow() {
    // 考虑从添加页返回时是否需要刷新当前列表
    this.loadTabData(this.data.activeTab, true);
  },

  // --- Tab 切换 ---
  onTabsChange(event) {
    const newTabIndex = parseInt(event.detail.value, 10); //确保是数字
    if (this.data.activeTab === newTabIndex) return; // 防止重复加载

    // console.log(`Change tab to index: ${newTabIndex}`);
    this.setData({ activeTab: newTabIndex }, () => {
      // 切换 Tab 后，检查是否已加载过数据，如果列表为空则加载第一页
      const currentTabData = this.getCurrentTabData();
      if (currentTabData && currentTabData.recordList.length === 0 && currentTabData.hasMore) {
        console.log(`Tab ${newTabIndex} is empty, loading initial data.`);
        this.loadTabData(newTabIndex, true);
      } else {
        console.log(`Tab ${newTabIndex} already has data or no more data.`);
      }
    });
  },

  // --- 数据加载核心逻辑 ---
  async loadTabData(tabIndex, reset = false) {
    // console.log(`loadTabData called for tab ${tabIndex} with reset=${reset}`); // <--- 添加日志
    const statePathPrefix = `tabsDataState[${tabIndex}]`;
    // 检查 tabsDataState[tabIndex] 是否存在
    if (!this.data.tabsDataState[tabIndex]) {
      console.error(`State for tab index ${tabIndex} does not exist.`);
      return;
    }

    if (reset) {
      // console.log(`Resetting data for tab ${tabIndex}`);
      this.setData({
        // --- 只重置这些 ---
        [`${statePathPrefix}.recordList`]: [],
        [`${statePathPrefix}.currentPage`]: 1,
        [`${statePathPrefix}.hasMore`]: true,
        [`${statePathPrefix}.isLoadingMore`]: false,
        // --- 不要重置 filterValue 和 sorterValue ---
      });
    }
    // 等待 setData 完成后再更新列表
    await this.updateRecordListForTab(tabIndex);
  },

  async updateRecordListForTab(tabIndex) {
    const user_id = this.data.user_id || '';
    const config = this.getCurrentTabConfig(tabIndex);
    const state = this.getCurrentTabData(tabIndex);
    const statePathPrefix = `tabsDataState[${tabIndex}]`;

    // 添加健壮性检查
    if (!config || !state) {
      console.error(`Config or state not found for tab index ${tabIndex}.`);
      return;
    }

    // // *** 打印关键状态 ***
    // console.log(`updateRecordListForTab - Tab ${tabIndex} State:`, JSON.stringify(state));

    if (state.isLoadingMore) {
      console.log(`Tab ${tabIndex}: Already loading more data.`);
      return;
    }
    if (!state.hasMore && state.currentPage > 1) {
      console.log(`Tab ${tabIndex}: No more data.`);
      return;
    }

    this.setData({ [`${statePathPrefix}.isLoadingMore`]: true });

    // 构造请求参数，动态使用 filterParamName
    const params = {
      page: state.currentPage,
      size: state.pageSize,
      sort: state.sorterValue // 直接使用 state 中的 sorterValue
    };
    // 添加过滤参数（如果不是 'all'）
    if (config.filterParamName && state.filterValue !== 'all') {
      params[config.filterParamName] = state.filterValue;
    }

    if (user_id) {
      params.user_id = user_id;
    }

    // console.log(`Fetching data for Tab ${tabIndex} (${config.name}) with params:`, params); // <--- 再次确认这里的 params

    try {
      // *** 注意：这里的 request 函数需要能正确处理 baseUrl ***
      // *** 确保 request 函数内部拼接了正确的 API 地址，例如 'https://yourdomain.com' + config.apiEndpoint ***
      const res = await request(config.apiEndpoint, 'GET', params);

      // 检查后端返回的数据结构是否符合预期
      if (!res || typeof res.total !== 'number' || !Array.isArray(res.records)) {
        console.error(`Tab ${tabIndex} (${config.name}) API response format error:`, res);
        wx.showToast({ title: '数据格式错误', icon: 'error' });
        this.setData({ [`${statePathPrefix}.isLoadingMore`]: false });
        return; // 提前返回，防止后续处理出错
      }

      const { total = 0, records = [] } = res;

      // 格式化数据
      const formattedRecords = records.map(item => {
        // 根据 filterParamName 找到对应的 tag 值进行映射
        const tagValue = item[config.filterParamName] || item.tag || item.type || item.meal_type; // 尝试多种可能的字段名
        const tagStr = this.mapTag(tagValue, config.tagMap);
        const timeStr = formatTimestamp(item.timestamp);
        // 使用配置中的 formatter 生成显示内容
        const displayData = config.displayFormatter({ ...item, tagStr, timeStr });

        // 确保返回的对象包含 id，用于 wx:key
        // 后端返回的是 _id，需要映射
        const id = item._id || item.id; // 优先使用 _id

        return {
          id: id, // 使用映射后的 id
          ...displayData, // 包含 title, description, note
        };
      });

      const newRecordList = state.currentPage === 1 ? formattedRecords : state.recordList.concat(formattedRecords);
      const hasMore = state.currentPage * state.pageSize < total;

      console.log(`Tab ${tabIndex} (${config.name}) fetched: ${formattedRecords.length} records. Total: ${total}. HasMore: ${hasMore}.`);

      this.setData({
        [`${statePathPrefix}.recordList`]: newRecordList,
        [`${statePathPrefix}.hasMore`]: hasMore,
        [`${statePathPrefix}.isLoadingMore`]: false,
        // 更新页码应该在请求成功后，并且是在加载更多时才增加
        // [`${statePathPrefix}.currentPage`]: state.currentPage // 页码在 onReachBottom 中更新
      });

    } catch (err) {
      console.error(`Tab ${tabIndex} (${config.name}) data request failed:`, err);
      wx.showToast({ title: '加载失败', icon: 'error' });
      this.setData({ [`${statePathPrefix}.isLoadingMore`]: false });
    }
  },

  // --- 辅助函数 ---
  getCurrentTabConfig(index = this.data.activeTab) {
    return this.data.tabsConfig[index];
  },
  getCurrentTabData(index = this.data.activeTab) {
    return this.data.tabsDataState[index];
  },
  mapTag(tagValue, tagMap) {
    return tagMap && tagMap[tagValue] ? tagMap[tagValue] : '未知'; // 添加 tagMap 存在的检查
  },
  // mapSortValue 不再需要，直接使用 state 中的 sorterValue

  // --- 事件处理 ---
  onReachBottom() {
    const currentTabData = this.getCurrentTabData();
    // 添加检查确保 currentTabData 存在
    if (!currentTabData) return;

    if (!currentTabData.hasMore || currentTabData.isLoadingMore) {
      console.log(`Tab ${this.data.activeTab}: Cannot load more now (hasMore: ${currentTabData.hasMore}, isLoadingMore: ${currentTabData.isLoadingMore}).`);
      return;
    }
    // console.log(`Tab ${this.data.activeTab}: Reached bottom, loading next page.`);
    const nextPage = currentTabData.currentPage + 1;
    const statePathPrefix = `tabsDataState[${this.data.activeTab}]`;
    this.setData({
      [`${statePathPrefix}.currentPage`]: nextPage // 先更新页码
    }, () => {
      this.updateRecordListForTab(this.data.activeTab); // 再请求数据
    });
  },

  onFilterChange(e) {
    // console.log('onFilterChange triggered:', e); // 打印整个事件对象
    // console.log('Filter value selected:', e.detail.value); // 打印选中的值
    const tabIndex = this.data.activeTab;
    const filterValue = e.detail.value;
    console.log(`Tab ${tabIndex} filter changed to:`, filterValue);
    const statePathPrefix = `tabsDataState[${tabIndex}]`;
    // 检查当前值是否已改变，避免不必要的请求
    if (this.data.tabsDataState[tabIndex]?.filterValue === filterValue) return;

    this.setData({
      [`${statePathPrefix}.filterValue`]: filterValue,
    }, () => {
      this.loadTabData(tabIndex, true); // 筛选变化，重置并加载第一页
    });
  },

  onSortChange(e) {
    // console.log('onSortChange triggered:', e); // 打印整个事件对象
    // console.log('Sorter value selected:', e.detail.value); // 打印选中的值
    const tabIndex = this.data.activeTab;
    const sorterValue = e.detail.value;
    console.log(`Tab ${tabIndex} sorter changed to:`, sorterValue);
    const statePathPrefix = `tabsDataState[${tabIndex}]`;
    // 检查当前值是否已改变
    if (this.data.tabsDataState[tabIndex]?.sorterValue === sorterValue) return;

    this.setData({
      [`${statePathPrefix}.sorterValue`]: sorterValue,
    }, () => {
      this.loadTabData(tabIndex, true); // 排序变化，重置并加载第一页
    });
  },

  handleClick(e) {
    // 跳转到添加页，并带上当前记录类型
    const currentTabConfig = this.getCurrentTabConfig();
    if (!currentTabConfig) return;
    const currentTabType = currentTabConfig.name; // 'glucose', 'insulin', 'diet'
    wx.navigateTo({
      // 假设你的添加页面路径是这个
      url: `/pages/homeFunction/record/add/index?type=${currentTabType}`,
    })
  },

  scrollToTop() {
    this.setData({ scrollTop: 0 });
  },

  onPullDownRefresh() {
    console.log('Pull down refresh triggered.');
    this.loadTabData(this.data.activeTab, true)
      .finally(() => { // 使用 finally 确保 stopPullDownRefresh 总被调用
        wx.stopPullDownRefresh();
      });
    // 可以在 loadTabData 成功或失败的回调里显示 Toast
  },

  onTabsClick(event) {
    // 通常不需要处理，除非有特殊逻辑
    // console.log(`Click tab, tab-panel value is ${event.detail.value}.`);
  },
})