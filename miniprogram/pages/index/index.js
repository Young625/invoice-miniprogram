// pages/index/index.js
const app = getApp()

Page({
  data: {
    stats: {
      total_count: 0,
      total_amount: 0,
      month_count: 0,
      month_amount: 0
    },
    recentInvoices: [],
    loading: true,
    isGuest: false  // 游客模式标识
  },

  onLoad() {
    // 不再强制检查登录，允许游客浏览
    this.checkLoginStatus()
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
      this.loadData()
    } else {
      // 游客模式，显示示例数据
      this.setData({
        isGuest: true,
        loading: false
      })
    }
  },

  // 检查登录状态（不强制跳转）
  checkLoginStatus() {
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
      this.loadData()
    } else {
      this.setData({
        isGuest: true,
        loading: false
      })
    }
  },

  // 加载数据
  async loadData() {
    this.setData({ loading: true })

    try {
      // 并行加载统计和最近发票
      const [stats, invoices] = await Promise.all([
        this.loadStats(),
        this.loadRecentInvoices()
      ])

      this.setData({
        stats: stats,
        recentInvoices: invoices,
        loading: false
      })
    } catch (err) {
      console.error('加载数据失败', err)
      this.setData({ loading: false })
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
    }
  },

  // 加载统计数据（本月发票/本月金额由后端按中国时区统计）
  async loadStats() {
    const res = await app.request({
      url: '/invoices/stats',
      method: 'GET'
    })
    return {
      total_count: res.total_count ?? 0,
      total_amount: res.total_amount ?? 0,
      month_count: res.month_count ?? 0,
      month_amount: res.month_amount ?? 0,
      exported_count: res.exported_count ?? 0,
      pending_count: res.pending_count ?? 0
    }
  },

  // 加载最近发票
  async loadRecentInvoices() {
    const res = await app.request({
      url: '/invoices?page=1&page_size=5',
      method: 'GET'
    })
    return res.items || []
  },

  // 下拉刷新
  onPullDownRefresh() {
    this.loadData().then(() => {
      wx.stopPullDownRefresh()
    })
  },

  // 查看全部发票
  viewAllInvoices() {
    wx.switchTab({
      url: '/pages/list/list'
    })
  },

  // 查看发票详情
  viewInvoiceDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({
      url: `/pages/detail/detail?id=${id}`
    })
  },

  // 手动同步
  async syncInvoices() {
    // 游客模式，引导登录
    if (this.data.isGuest) {
      wx.showModal({
        title: '需要登录',
        content: '请先登录后再使用同步功能',
        confirmText: '去登录',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({
              url: '/pages/login/login'
            })
          }
        }
      })
      return
    }

    wx.showLoading({
      title: '同步中...'
    })

    try {
      await app.request({
        url: '/invoices/sync',
        method: 'POST'
      })

      wx.hideLoading()
      wx.showToast({
        title: '同步成功',
        icon: 'success'
      })

      // 重新加载数据
      setTimeout(() => {
        this.loadData()
      }, 1500)
    } catch (err) {
      wx.hideLoading()
      wx.showToast({
        title: '同步失败',
        icon: 'none'
      })
    }
  },

  // 跳转登录页
  goToLogin() {
    wx.navigateTo({
      url: '/pages/login/login'
    })
  },

  // 分享小程序
  onShareAppMessage() {
    return {
      title: '发票管家 - 自动提取邮箱发票',
      path: '/pages/index/index',
      imageUrl: '' // 可选：自定义分享图片
    }
  }
})
