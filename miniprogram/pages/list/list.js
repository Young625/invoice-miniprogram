// pages/list/list.js
const app = getApp()

Page({
  data: {
    invoices: [],
    page: 1,
    pageSize: 20,
    total: 0,
    keyword: '',
    startDate: '',
    endDate: '',
    invoiceType: '',
    projectName: '',
    loading: false,
    hasMore: true,
    types: [
      { value: '', label: '全部类型' },
      { value: '电子发票（普通发票）', label: '电子发票（普通发票）' },
      { value: '电子发票（铁路电子客票）', label: '电子发票（铁路电子客票）' },
      { value: '电子发票（增值税专用发票）', label: '电子发票（增值税专用发票）' },
      { value: '通用（电子）发票', label: '通用（电子）发票' },
      { value: '增值税电子普通发票', label: '增值税电子普通发票' },
      { value: '其他', label: '其他' }
    ],
    typeIndex: 0,
    // 固定的项目列表
    projectNames: [
      { value: '', label: '全部项目' },
      { value: '餐饮服务', label: '餐饮服务' },
      { value: '运输服务', label: '运输服务' },
      { value: '住宿服务', label: '住宿服务' },
      { value: '办公用品', label: '办公用品' },
      { value: '金融服务', label: '金融服务' },
      { value: '通讯服务', label: '通讯服务' },
      { value: '会议服务', label: '会议服务' },
      { value: '培训服务', label: '培训服务' },
      { value: '咨询服务', label: '咨询服务' },
      { value: '租赁服务', label: '租赁服务' },
      { value: '维修服务', label: '维修服务' },
      { value: '其他', label: '其他' }
    ],
    projectIndex: 0,
    // 多选相关
    selectedIds: [],
    selectedMap: {}, // 新增：用对象来存储选中状态
    isAllSelected: false,
    isGuest: false  // 游客模式标识
  },

  onLoad() {
    // 优先检查 globalData，如果没有则检查 storage
    let token = app.globalData.token
    if (!token) {
      token = wx.getStorageSync('token')
      if (token) {
        app.globalData.token = token
      }
    }

    if (token) {
      this.setData({ isGuest: false })
      this.loadInvoices()
    } else {
      // 游客模式，显示空状态
      this.setData({
        isGuest: true,
        loading: false
      })
    }
  },

  onShow() {
    // 优先检查 globalData，如果没有则检查 storage
    let token = app.globalData.token
    if (!token) {
      token = wx.getStorageSync('token')
      if (token) {
        app.globalData.token = token
      }
    }

    if (token) {
      this.setData({ isGuest: false })
    } else {
      this.setData({ isGuest: true })
    }

    // 从报销包页面返回时，清空选择状态并刷新列表（已导出状态需要更新）
    if (this.data.selectedIds.length > 0 || app.globalData.needRefreshInvoiceList) {
      app.globalData.needRefreshInvoiceList = false
      this.setData({
        selectedIds: [],
        selectedMap: {},
        isAllSelected: false
      })
      this.refreshData()
    }
  },

  // 加载发票列表
  async loadInvoices() {
    if (this.data.loading || !this.data.hasMore) return

    // 游客模式，引导登录
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }

    this.setData({ loading: true })

    try {
      const res = await app.request({
        url: '/invoices',
        method: 'GET',
        data: {
          page: this.data.page,
          page_size: this.data.pageSize,
          keyword: this.data.keyword,
          start_date: this.data.startDate,
          end_date: this.data.endDate,
          invoice_type: this.data.invoiceType,
          project_name: this.data.projectName
        }
      })

      this.setData({
        invoices: this.data.invoices.concat(res.items),
        total: res.total,
        page: this.data.page + 1,
        hasMore: this.data.invoices.length + res.items.length < res.total,
        loading: false
      })
    } catch (err) {
      console.error('加载发票列表失败', err)
      this.setData({ loading: false })
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
    }
  },

  // 刷新数据
  refreshData() {
    this.setData({
      invoices: [],
      page: 1,
      hasMore: true
    })
    this.loadInvoices()
  },

  // 下拉刷新
  onPullDownRefresh() {
    this.refreshData()
    setTimeout(() => {
      wx.stopPullDownRefresh()
    }, 1000)
  },

  // 上拉加载更多
  onReachBottom() {
    this.loadInvoices()
  },

  // 搜索
  onSearch(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    this.setData({
      keyword: e.detail.value
    })
    this.refreshData()
  },

  // 清空搜索
  onClearSearch() {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    this.setData({ keyword: '' })
    this.refreshData()
  },

  // 日期筛选
  onStartDateChange(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    this.setData({ startDate: e.detail.value })
    this.refreshData()
  },

  onEndDateChange(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    this.setData({ endDate: e.detail.value })
    this.refreshData()
  },

  // 类型筛选
  onTypeChange(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    const index = e.detail.value
    this.setData({
      typeIndex: index,
      invoiceType: this.data.types[index].value
    })
    this.refreshData()
  },

  // 项目筛选
  onProjectChange(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    const index = e.detail.value
    this.setData({
      projectIndex: index,
      projectName: this.data.projectNames[index].value
    })
    this.refreshData()
  },

  // 查看详情
  viewDetail(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    const id = e.currentTarget.dataset.id
    wx.navigateTo({
      url: `/pages/detail/detail?id=${id}`
    })
  },

  // 导出发票
  async exportInvoice(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    const id = e.currentTarget.dataset.id

    try {
      await app.request({
        url: `/invoices/${id}/export`,
        method: 'POST'
      })

      wx.showToast({
        title: '已标记为已导出',
        icon: 'success'
      })

      // 刷新列表
      this.refreshData()
    } catch (err) {
      wx.showToast({
        title: '操作失败',
        icon: 'none'
      })
    }
  },

  // 选择单个发票
  onSelectInvoice(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }

    const id = e.currentTarget.dataset.id
    const isExported = e.currentTarget.dataset.exported

    // 如果发票已导出，不允许选择
    if (isExported) {
      wx.showToast({
        title: '该发票已导出',
        icon: 'none',
        duration: 1500
      })
      return
    }

    console.log('选择发票 ID:', id)
    console.log('当前选中列表:', this.data.selectedIds)

    const selectedIds = [...this.data.selectedIds]
    const selectedMap = {...this.data.selectedMap}
    const index = selectedIds.indexOf(id)

    if (index > -1) {
      // 取消选择
      selectedIds.splice(index, 1)
      delete selectedMap[id]
      console.log('取消选择后:', selectedIds)
    } else {
      // 添加选择
      selectedIds.push(id)
      selectedMap[id] = true
      console.log('添加选择后:', selectedIds)
    }

    this.setData({
      selectedIds: selectedIds,
      selectedMap: selectedMap,
      isAllSelected: selectedIds.length === this.data.invoices.filter(inv => !inv.is_exported).length
    }, () => {
      console.log('setData 完成，新的 selectedIds:', this.data.selectedIds)
      console.log('setData 完成，新的 selectedMap:', this.data.selectedMap)
    })
  },

  // 全选/取消全选
  toggleSelectAll() {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    if (this.data.isAllSelected) {
      // 取消全选
      this.setData({
        selectedIds: [],
        selectedMap: {},
        isAllSelected: false
      })
    } else {
      // 全选（只选择未导出的发票）
      const allIds = this.data.invoices
        .filter(item => !item.is_exported)
        .map(item => item.id)
      const selectedMap = {}
      allIds.forEach(id => {
        selectedMap[id] = true
      })
      this.setData({
        selectedIds: allIds,
        selectedMap: selectedMap,
        isAllSelected: true
      })
    }
  },

  // 取消选择
  cancelSelection() {
    this.setData({
      selectedIds: [],
      selectedMap: {},
      isAllSelected: false
    })
  },

  // 生成报销包
  generateReimbursement() {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    if (this.data.selectedIds.length === 0) {
      wx.showToast({
        title: '请先选择发票',
        icon: 'none'
      })
      return
    }

    // 检测选中的发票中是否有已导出的
    const exportedInvoices = this.data.invoices.filter(
      inv => this.data.selectedMap[inv.id] && inv.is_exported
    )

    if (exportedInvoices.length > 0) {
      const names = exportedInvoices.map(inv =>
        inv.seller_name || inv.invoice_number || '未知发票'
      ).join('、')
      wx.showModal({
        title: '包含已导出发票',
        content: `以下发票已导出过：${names}，是否继续生成？`,
        confirmText: '继续',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            this._navigateToReimbursement()
          }
        }
      })
      return
    }

    this._navigateToReimbursement()
  },

  _navigateToReimbursement() {
    const idsParam = this.data.selectedIds.join(',')
    wx.navigateTo({
      url: `/pages/reimbursement/reimbursement?ids=${idsParam}`
    })
  },

  // 显示登录引导
  showLoginGuide() {
    wx.showModal({
      title: '需要登录',
      content: '请先登录后使用完整功能',
      confirmText: '去登录',
      cancelText: '返回首页',
      success: (res) => {
        if (res.confirm) {
          wx.navigateTo({
            url: '/pages/login/login'
          })
        } else {
          wx.switchTab({
            url: '/pages/index/index'
          })
        }
      }
    })
  },

  // 分享小程序
  onShareAppMessage() {
    return {
      title: '发票管家 - 我的发票列表',
      path: '/pages/index/index'
    }
  }
})