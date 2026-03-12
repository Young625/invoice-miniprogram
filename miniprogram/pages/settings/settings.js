// pages/settings/settings.js
const app = getApp()

// 邮箱类型配置
const EMAIL_PROVIDERS = {
  'qq': {
    name: 'QQ邮箱',
    imap_server: 'imap.qq.com',
    imap_port: 993,
    placeholder: '例：123456789@qq.com',
    authCodeHelp: '1. 登录QQ邮箱网页版\n2. 点击"设置" → "账户"\n3. 找到"POP3/IMAP/SMTP服务"\n4. 开启"IMAP/SMTP服务"\n5. 生成授权码并保存'
  },
  '163': {
    name: '163邮箱',
    imap_server: 'imap.163.com',
    imap_port: 993,
    placeholder: '例：xxx@163.com',
    authCodeHelp: '1. 登录163邮箱网页版\n2. 点击"设置" → "POP3/SMTP/IMAP"\n3. 开启"IMAP/SMTP服务"\n4. 设置授权码并保存'
  },
  '126': {
    name: '126邮箱',
    imap_server: 'imap.126.com',
    imap_port: 993,
    placeholder: '例：xxx@126.com',
    authCodeHelp: '1. 登录126邮箱网页版\n2. 点击"设置" → "POP3/SMTP/IMAP"\n3. 开启"IMAP/SMTP服务"\n4. 设置授权码并保存'
  },
  'gmail': {
    name: 'Gmail',
    imap_server: 'imap.gmail.com',
    imap_port: 993,
    placeholder: '例：xxx@gmail.com',
    authCodeHelp: '1. 登录Google账户\n2. 进入"安全性"设置\n3. 开启"两步验证"\n4. 生成"应用专用密码"\n5. 使用该密码作为授权码'
  },
  'outlook': {
    name: 'Outlook',
    imap_server: 'outlook.office365.com',
    imap_port: 993,
    placeholder: '例：xxx@outlook.com',
    authCodeHelp: '1. 登录Microsoft账户\n2. 进入"安全性"设置\n3. 开启"两步验证"\n4. 生成"应用密码"\n5. 使用该密码作为授权码'
  },
  'custom': {
    name: '自定义邮箱',
    imap_server: '',
    imap_port: 993,
    placeholder: '例：xxx@company.com',
    authCodeHelp: '请联系您的邮箱服务提供商获取IMAP服务器地址、端口和授权码信息'
  }
}

Page({
  data: {
    userInfo: null,
    emailConfig: null,  // 保留兼容
    emailConfigs: [],   // 新增：邮箱配置列表
    maxEmailConfigs: 3, // 最多支持3个邮箱
    autoSyncEnabled: false,  // 自动同步开关（默认关闭）
    notifications: {
      newInvoice: true,
      monthlySummary: true
    },
    showEmailModal: false,
    showAuthCodeHelp: false,
    showUserInfoModal: false,  // 新增：用户信息编辑弹窗
    tempUserInfo: {  // 新增：临时用户信息
      nickname: '',
      avatar_url: ''
    },
    editingIndex: -1,  // 新增：正在编辑的邮箱索引，-1表示新增
    emailForm: {
      email_type: 'qq',  // 默认QQ邮箱
      email_type_index: 0,  // 默认索引
      username: '',
      auth_code: '',
      folder: 'INBOX',
      custom_imap_server: '',  // 自定义IMAP服务器
      custom_imap_port: 993    // 自定义IMAP端口
    },
    emailProviders: Object.keys(EMAIL_PROVIDERS).map(key => ({
      value: key,
      label: EMAIL_PROVIDERS[key].name
    })),
    currentProvider: EMAIL_PROVIDERS['qq'],
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
      this.loadUserInfo()
      this.loadEmailConfig()
      this.loadAutoSyncStatus()
    } else {
      // 游客模式，显示默认界面
      this.setData({
        isGuest: true,
        userInfo: {
          nickname: '游客',
          avatar_url: '/images/default-avatar.png'
        }
      })
    }
  },

  onShow() {
    // 每次显示页面时检查登录状态
    let token = app.globalData.token
    if (!token) {
      token = wx.getStorageSync('token')
      if (token) {
        app.globalData.token = token
      }
    }

    if (token) {
      this.setData({ isGuest: false })
      // 重新加载用户信息和邮箱配置，确保数据最新
      this.loadUserInfo()
      this.loadEmailConfig()
      this.loadAutoSyncStatus()
    } else {
      // 没有 token，显示游客模式
      this.setData({
        isGuest: true,
        userInfo: {
          nickname: '游客',
          avatar_url: '/images/default-avatar.png'
        }
      })
    }
  },

  // 加载用户信息
  async loadUserInfo() {
    try {
      console.log('开始加载用户信息...')
      console.log('当前 token:', app.globalData.token ? '存在' : '不存在')
      console.log('globalData.userInfo:', app.globalData.userInfo)

      // 优先从 globalData 读取，如果没有则从后端获取
      let userInfo = app.globalData.userInfo
      if (!userInfo && app.globalData.token) {
        console.log('globalData 中没有用户信息，从后端获取...')
        userInfo = await app.getUserInfo()
        console.log('从后端获取的用户信息:', userInfo)
      }

      if (userInfo) {
        console.log('设置用户信息:', userInfo)
        this.setData({
          userInfo,
          isGuest: false
        })
      } else {
        // 如果获取失败，显示未登录状态
        console.warn('获取用户信息失败，可能 token 已过期')
        this.setData({
          isGuest: true,
          userInfo: {
            nickname: '未登录',
            avatar_url: '/images/default-avatar.png'
          }
        })
      }
    } catch (err) {
      console.error('加载用户信息失败:', err)
      // 出错时也显示未登录状态
      this.setData({
        isGuest: true,
        userInfo: {
          nickname: '未登录',
          avatar_url: '/images/default-avatar.png'
        }
      })
    }
  },

  // 加载邮箱配置
  async loadEmailConfig() {
    try {
      const response = await app.request({
        url: '/user/email-configs',
        method: 'GET'
      })

      this.setData({
        emailConfigs: response || [],
        emailConfig: response && response.length > 0 ? response[0] : null
      })
    } catch (err) {
      console.error('加载邮箱配置失败', err)
    }
  },

  // 加载自动同步状态
  async loadAutoSyncStatus() {
    try {
      const response = await app.request({
        url: '/user/auto-sync-status',
        method: 'GET'
      })

      this.setData({
        autoSyncEnabled: response.auto_sync_enabled !== undefined ? response.auto_sync_enabled : false
      })
    } catch (err) {
      console.error('加载自动同步状态失败', err)
    }
  },

  // 编辑用户信息
  editUserInfo() {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }

    // 复制当前用户信息到临时变量
    this.setData({
      showUserInfoModal: true,
      tempUserInfo: {
        nickname: this.data.userInfo.nickname || '微信用户',
        avatar_url: this.data.userInfo.avatar_url || '/images/default-avatar.png'
      }
    })
  },

  // 选择头像
  onChooseAvatar(e) {
    const { avatarUrl } = e.detail
    console.log('选择的头像临时路径:', avatarUrl)

    // 将图片转换为 base64
    wx.getFileSystemManager().readFile({
      filePath: avatarUrl,
      encoding: 'base64',
      success: (res) => {
        const base64 = 'data:image/jpeg;base64,' + res.data
        this.setData({
          'tempUserInfo.avatar_url': base64
        })
        console.log('头像已转换为 base64，长度:', base64.length)
      },
      fail: (err) => {
        console.error('读取头像文件失败:', err)
        wx.showToast({
          title: '头像读取失败',
          icon: 'none'
        })
      }
    })
  },

  // 昵称输入
  onNicknameChange(e) {
    this.setData({
      'tempUserInfo.nickname': e.detail.value
    })
  },

  // 保存用户信息
  async saveUserInfo() {
    const { tempUserInfo } = this.data

    // 验证昵称
    if (!tempUserInfo.nickname || tempUserInfo.nickname.trim() === '') {
      wx.showToast({
        title: '请输入昵称',
        icon: 'none'
      })
      return
    }

    wx.showLoading({ title: '保存中...' })

    try {
      const response = await app.request({
        url: '/auth/profile',
        method: 'PUT',
        data: {
          nickname: tempUserInfo.nickname.trim(),
          avatar_url: tempUserInfo.avatar_url
        }
      })

      console.log('更新用户信息成功:', response)

      // 更新本地用户信息
      const updatedUserInfo = {
        ...this.data.userInfo,
        nickname: tempUserInfo.nickname.trim(),
        avatar_url: tempUserInfo.avatar_url
      }

      this.setData({
        userInfo: updatedUserInfo,
        showUserInfoModal: false
      })

      // 同步更新 globalData
      app.globalData.userInfo = updatedUserInfo

      wx.hideLoading()
      wx.showToast({
        title: '保存成功',
        icon: 'success'
      })

    } catch (err) {
      console.error('保存用户信息失败:', err)
      wx.hideLoading()
      wx.showToast({
        title: err.data?.detail || err.message || '保存失败',
        icon: 'none'
      })
    }
  },

  // 隐藏用户信息编辑弹窗
  hideUserInfoModal() {
    this.setData({
      showUserInfoModal: false
    })
  },

  // 显示邮箱配置弹窗（新增）
  showAddEmailModal() {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }

    // 检查是否已达到上限
    if (this.data.emailConfigs.length >= this.data.maxEmailConfigs) {
      wx.showToast({
        title: `最多只能配置${this.data.maxEmailConfigs}个邮箱`,
        icon: 'none'
      })
      return
    }

    this.setData({
      showEmailModal: true,
      editingIndex: -1,  // -1 表示新增
      emailForm: {
        email_type: 'qq',
        email_type_index: 0,
        username: '',
        auth_code: '',
        folder: 'INBOX',
        custom_imap_server: '',
        custom_imap_port: 993
      },
      currentProvider: EMAIL_PROVIDERS['qq']
    })
  },

  // 显示邮箱配置弹窗（编辑）
  showEditEmailModal(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }

    const index = e.currentTarget.dataset.index
    const config = this.data.emailConfigs[index]

    if (!config) return

    // 识别邮箱类型
    let emailType = 'qq'
    let emailTypeIndex = 0
    let customImapServer = ''
    let customImapPort = 993
    let found = false

    // 尝试匹配预定义的邮箱类型
    for (let key in EMAIL_PROVIDERS) {
      if (key !== 'custom' && EMAIL_PROVIDERS[key].imap_server === config.imap_server) {
        emailType = key
        found = true
        break
      }
    }

    // 如果没有匹配到预定义类型，则为自定义邮箱
    if (!found) {
      emailType = 'custom'
      customImapServer = config.imap_server
      customImapPort = config.imap_port
    }

    // 找到对应的索引
    emailTypeIndex = this.data.emailProviders.findIndex(p => p.value === emailType)
    if (emailTypeIndex === -1) emailTypeIndex = 0

    this.setData({
      showEmailModal: true,
      editingIndex: index,  // 记录正在编辑的索引
      emailForm: {
        email_type: emailType,
        email_type_index: emailTypeIndex,
        username: config.username || '',
        auth_code: config.auth_code || '',
        folder: config.folder || 'INBOX',
        custom_imap_server: customImapServer,
        custom_imap_port: customImapPort
      },
      currentProvider: EMAIL_PROVIDERS[emailType]
    })
  },

  // 隐藏邮箱配置弹窗
  hideEmailConfigModal() {
    this.setData({ showEmailModal: false })
  },

  // 邮箱类型选择变化
  onEmailTypeChange(e) {
    const index = parseInt(e.detail.value)
    const emailType = this.data.emailProviders[index].value
    const provider = EMAIL_PROVIDERS[emailType]

    console.log('选择邮箱类型:', emailType, provider)

    this.setData({
      'emailForm.email_type': emailType,
      'emailForm.email_type_index': index,
      currentProvider: provider
    })
  },

  // 输入框变化
  onInputChange(e) {
    const field = e.currentTarget.dataset.field
    this.setData({
      [`emailForm.${field}`]: e.detail.value
    })
  },

  // 保存邮箱配置
  async saveEmailConfig() {
    const { emailForm, currentProvider, editingIndex } = this.data

    console.log('保存邮箱配置:', emailForm, currentProvider, '编辑索引:', editingIndex)

    // 验证必填项
    if (!emailForm.username || !emailForm.auth_code) {
      wx.showToast({
        title: '请填写完整信息',
        icon: 'none'
      })
      return
    }

    // 如果是自定义邮箱，验证自定义字段
    if (emailForm.email_type === 'custom') {
      if (!emailForm.custom_imap_server) {
        wx.showToast({
          title: '请填写IMAP服务器地址',
          icon: 'none'
        })
        return
      }
      if (!emailForm.custom_imap_port || emailForm.custom_imap_port <= 0) {
        wx.showToast({
          title: '请填写有效的IMAP端口',
          icon: 'none'
        })
        return
      }
    }

    wx.showLoading({ title: '验证邮箱中...' })

    try {
      // 构建完整的配置数据
      const configData = {
        email_type: emailForm.email_type,  // 添加邮箱类型
        imap_server: emailForm.email_type === 'custom'
          ? emailForm.custom_imap_server
          : currentProvider.imap_server,
        imap_port: emailForm.email_type === 'custom'
          ? parseInt(emailForm.custom_imap_port)
          : currentProvider.imap_port,
        username: emailForm.username,
        auth_code: emailForm.auth_code,
        folder: emailForm.folder || 'INBOX'
      }

      console.log('发送配置数据:', configData)

      // 根据 editingIndex 判断是新增还是编辑
      let response
      if (editingIndex === -1) {
        // 新增
        response = await app.request({
          url: '/user/email-configs',
          method: 'POST',
          data: configData
        })
      } else {
        // 编辑
        response = await app.request({
          url: `/user/email-configs/${editingIndex}`,
          method: 'PUT',
          data: configData
        })
      }

      console.log('保存成功:', response)

      wx.hideLoading()
      wx.showToast({
        title: '验证通过，保存成功',
        icon: 'success'
      })

      // 重新加载邮箱配置列表
      await this.loadEmailConfig()

      // 关闭弹窗
      this.setData({ showEmailModal: false })

      // 触发邮箱同步
      setTimeout(() => {
        this.syncInvoices()
      }, 1500)

    } catch (err) {
      console.error('保存邮箱配置失败:', err)
      wx.hideLoading()

      // 显示实际的错误信息
      // err.data.detail 是后端返回的详细错误信息
      // err.message 是封装后的错误消息
      const errorMsg = err.data?.detail || err.message || '保存失败，请检查网络连接'
      console.log('错误信息:', errorMsg)

      // 统一使用 Toast 显示错误信息
      wx.showToast({
        title: errorMsg,
        icon: 'none',
        duration: 3000
      })
    }
  },

  // 删除邮箱配置
  deleteEmailConfig(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }

    const index = e.currentTarget.dataset.index
    const config = this.data.emailConfigs[index]

    wx.showModal({
      title: '确认删除',
      content: `确定要删除邮箱 ${config.username} 吗？`,
      success: async (res) => {
        if (res.confirm) {
          wx.showLoading({ title: '删除中...' })

          try {
            await app.request({
              url: `/user/email-configs/${index}`,
              method: 'DELETE'
            })

            wx.hideLoading()
            wx.showToast({
              title: '删除成功',
              icon: 'success'
            })

            // 重新加载邮箱配置列表
            await this.loadEmailConfig()

          } catch (err) {
            console.error('删除邮箱配置失败:', err)
            wx.hideLoading()
            wx.showToast({
              title: '删除失败',
              icon: 'none'
            })
          }
        }
      }
    })
  },

  // 设置主邮箱
  setPrimaryEmail(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }

    const index = e.currentTarget.dataset.index

    // 如果已经是主邮箱，无需操作
    if (index === 0) {
      wx.showToast({
        title: '已经是主邮箱',
        icon: 'none'
      })
      return
    }

    const config = this.data.emailConfigs[index]

    wx.showModal({
      title: '设置主邮箱',
      content: `确定要将 ${config.username} 设为主邮箱吗？`,
      success: async (res) => {
        if (res.confirm) {
          wx.showLoading({ title: '设置中...' })

          try {
            await app.request({
              url: `/user/email-configs/set-primary/${index}`,
              method: 'PUT'
            })

            wx.hideLoading()
            wx.showToast({
              title: '设置成功',
              icon: 'success'
            })

            // 重新加载邮箱配置列表和用户信息
            await this.loadEmailConfig()
            await this.loadUserInfo()

          } catch (err) {
            console.error('设置主邮箱失败:', err)
            wx.hideLoading()
            wx.showToast({
              title: '设置失败',
              icon: 'none'
            })
          }
        }
      }
    })
  },

  // 同步发票
  async syncInvoices() {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }

    // 检查是否有邮箱配置
    if (!this.data.emailConfigs || this.data.emailConfigs.length === 0) {
      wx.showToast({
        title: '请先配置邮箱',
        icon: 'none'
      })
      return
    }

    wx.showLoading({ title: '同步中...' })

    try {
      const result = await app.request({
        url: '/invoices/sync',
        method: 'POST'
      })

      wx.hideLoading()

      const successCount = result.success_count || 0
      const duplicateCount = result.duplicate_count || 0
      const duplicateInvoices = result.duplicate_invoices || []

      // 构建提示消息
      let message = result.message || '同步完成'

      // 如果有重复发票，显示详细信息
      if (duplicateCount > 0 && duplicateInvoices.length > 0) {
        const duplicateDetails = duplicateInvoices.map(inv =>
          `发票号码：${inv.invoice_number}\n原因：${inv.reason}`
        ).join('\n\n')

        wx.showModal({
          title: '同步完成',
          content: `${message}\n\n重复发票详情：\n${duplicateDetails}`,
          showCancel: false,
          confirmText: '我知道了'
        })
      } else if (successCount > 0) {
        wx.showToast({
          title: message,
          icon: 'success',
          duration: 2000
        })
      } else {
        wx.showToast({
          title: message,
          icon: 'none',
          duration: 2000
        })
      }
    } catch (err) {
      console.error('同步失败:', err)
      wx.hideLoading()
      wx.showToast({
        title: err.data?.detail || err.message || '同步失败',
        icon: 'none',
        duration: 2000
      })
    }
  },

  // 切换自动同步
  async toggleAutoSync(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }

    const newValue = e.detail.value

    try {
      await app.request({
        url: '/user/auto-sync-status',
        method: 'PUT',
        data: {
          enabled: newValue
        }
      })

      this.setData({
        autoSyncEnabled: newValue
      })

      wx.showToast({
        title: newValue ? '已开启自动同步' : '已关闭自动同步',
        icon: 'success'
      })
    } catch (err) {
      console.error('更新自动同步状态失败', err)
      console.error('错误详情:', err.message || err)
      // 如果失败，恢复原值
      this.setData({
        autoSyncEnabled: !newValue
      })
      wx.showToast({
        title: err.message || '设置失败，请重试',
        icon: 'none',
        duration: 3000
      })
    }
  },

  // 切换通知设置
  toggleNotification(e) {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    const key = e.currentTarget.dataset.key
    this.setData({
      [`notifications.${key}`]: !this.data.notifications[key]
    })
  },

  // 退出登录
  logout() {
    if (this.data.isGuest) {
      this.showLoginGuide()
      return
    }
    wx.showModal({
      title: '确认退出',
      content: '退出登录后需要重新登录',
      success: (res) => {
        if (res.confirm) {
          app.logout()
        }
      }
    })
  },

  // 关于我们
  showAbout() {
    const version = app.globalData.version || '1.0.0'
    wx.showModal({
      title: '关于发票管家',
      content: '版本：' + version + '\n\n自动提取邮箱发票，智能统计分析，轻松管理每一张发票。',
      showCancel: false,
      confirmText: '知道了'
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

  // 显示授权码帮助
  showAuthCodeHelp() {
    this.setData({ showAuthCodeHelp: true })
  },

  // 隐藏授权码帮助
  hideAuthCodeHelp() {
    this.setData({ showAuthCodeHelp: false })
  },

  // 分享小程序
  onShareAppMessage() {
    return {
      title: '发票管家 - 自动提取邮箱发票',
      path: '/pages/index/index'
    }
  }
})