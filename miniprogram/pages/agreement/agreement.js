// pages/agreement/agreement.js
const { USER_AGREEMENT, PRIVACY_POLICY } = require('../../utils/agreementContent.js')

Page({
  data: {
    title: '用户协议',
    content: ''
  },

  onLoad(options) {
    const type = options.type || 'user_agreement'
    const title = type === 'privacy_policy' ? '隐私政策' : '用户协议'
    const content = type === 'privacy_policy' ? PRIVACY_POLICY : USER_AGREEMENT
    this.setData({ title, content })
    wx.setNavigationBarTitle({ title })
  }
})
