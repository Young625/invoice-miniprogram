// pages/login/login.js
const app = getApp()

Page({
  data: {
    privacyAgreed: false
  },

  onLoad() {
    // 检查是否已登录
    if (app.globalData.token) {
      wx.switchTab({
        url: '/pages/index/index'
      })
    }
  },

  // 隐私协议勾选变化
  onPrivacyChange(e) {
    this.setData({
      privacyAgreed: e.detail.value.length > 0
    })
  },

  // 查看用户协议
  viewUserAgreement() {
    wx.navigateTo({
      url: '/pages/agreement/agreement?type=user_agreement'
    })
  },

  // 查看隐私政策
  viewPrivacyPolicy() {
    wx.navigateTo({
      url: '/pages/agreement/agreement?type=privacy_policy'
    })
  },

  // 处理登录 - 使用默认信息快速登录
  async handleLogin() {
    // 检查是否同意隐私政策
    if (!this.data.privacyAgreed) {
      wx.showToast({
        title: '请先同意隐私政策',
        icon: 'none'
      })
      return
    }

    wx.showLoading({
      title: '登录中...'
    })

    try {
      // 获取微信登录 code
      const loginRes = await wx.login()
      const code = loginRes.code

      // 使用默认用户信息快速登录
      const userInfo = {
        nickName: '微信用户',
        avatarUrl: '/images/default-avatar.png'
      }

      console.log('登录信息:', { code, userInfo })

      // 调用后端登录接口
      await app.login(code, userInfo)

      wx.hideLoading()
      wx.showToast({
        title: '登录成功',
        icon: 'success'
      })

      // 跳转到首页
      setTimeout(() => {
        wx.switchTab({
          url: '/pages/index/index'
        })
      }, 1500)

    } catch (err) {
      wx.hideLoading()
      wx.showToast({
        title: err.message || '登录失败',
        icon: 'none'
      })
      console.error('登录失败', err)
    }
  },

  // 分享小程序
  onShareAppMessage() {
    return {
      title: '发票管家 - 自动提取邮箱发票',
      path: '/pages/index/index'
    }
  }
})
