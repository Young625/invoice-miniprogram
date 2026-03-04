// app.js
App({
  globalData: {
    userInfo: null,
    token: null,
    // 线上
     apiBase: 'https://invoice.zjugpt.com/api',

    // 开发
    // apiBase: 'http://192.168.0.17:8000/api',

    // 版本号（每次发版时更新）
    version: '2.0.1'
  },

  onLaunch() {
    console.log('小程序启动')

    // 检查版本更新
    this.checkUpdate()

    // 检查登录状态
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
      this.getUserInfo()
    }
  },

  // 检查小程序更新
  checkUpdate() {
    // 判断是否支持版本更新检测（基础库 1.9.90+ 支持）
    if (!wx.canIUse('getUpdateManager')) {
      console.log('当前微信版本过低，无法使用更新功能，请升级微信')
      return
    }

    const updateManager = wx.getUpdateManager()

    // 监听向后台请求完新版本信息的结果
    updateManager.onCheckForUpdate((res) => {
      console.log('检查更新结果:', res.hasUpdate)
      if (res.hasUpdate) {
        console.log('发现新版本，开始下载...')
      }
    })

    // 监听新版本下载成功事件
    updateManager.onUpdateReady(() => {
      wx.showModal({
        title: '更新提示',
        content: '新版本已经准备好，是否重启应用？',
        success: (res) => {
          if (res.confirm) {
            // 强制当前小程序使用新版本并重启
            updateManager.applyUpdate()
          }
        }
      })
    })

    // 监听新版本下载失败事件
    updateManager.onUpdateFailed(() => {
      console.error('新版本下载失败')
      wx.showModal({
        title: '更新提示',
        content: '新版本下载失败，请检查网络后重试，或删除小程序重新打开',
        showCancel: false
      })
    })
  },

  // 获取用户信息
  async getUserInfo() {
    try {
      const res = await this.request({
        url: '/auth/profile',
        method: 'GET'
      })
      // 后端直接返回用户信息对象，不需要 .data
      this.globalData.userInfo = res
      console.log('获取用户信息成功:', res)
      return res
    } catch (err) {
      console.error('获取用户信息失败', err)
      // 如果获取失败，清除 token
      if (err.message === '未授权') {
        this.globalData.token = null
        this.globalData.userInfo = null
        wx.removeStorageSync('token')
      }
      return null
    }
  },

  // 网络请求封装
  request(options) {
    return new Promise((resolve, reject) => {
      const requestConfig = {
        url: this.globalData.apiBase + options.url,
        method: options.method || 'GET',
        data: options.data || {},
        header: {
          'Content-Type': 'application/json',
          'Authorization': this.globalData.token ? `Bearer ${this.globalData.token}` : ''
        },
        success: (res) => {
          if (res.statusCode === 200) {
            resolve(res.data)
          } else if (res.statusCode === 401) {
            // 未授权，跳转登录
            wx.removeStorageSync('token')
            this.globalData.token = null
            wx.redirectTo({
              url: '/pages/login/login'
            })
            reject(new Error('未授权'))
          } else {
            reject(new Error(res.data.detail || '请求失败'))
          }
        },
        fail: (err) => {
          wx.showToast({
            title: '网络错误',
            icon: 'none'
          })
          reject(err)
        }
      }

      // 如果指定了 responseType，添加到配置中
      if (options.responseType) {
        requestConfig.responseType = options.responseType
      }

      wx.request(requestConfig)
    })
  },

  // 登录
  async login(code, userInfo) {
    try {
      console.log('app.login 被调用')
      console.log('code:', code)
      console.log('userInfo:', userInfo)
      console.log('userInfo.nickName:', userInfo.nickName)
      console.log('userInfo.avatarUrl:', userInfo.avatarUrl)

      const requestData = {
        code: code,
        nickname: userInfo.nickName,
        avatar_url: userInfo.avatarUrl
      }
      console.log('准备发送的请求数据:', requestData)

      const res = await this.request({
        url: '/auth/login',
        method: 'POST',
        data: requestData
      })

      console.log('登录接口返回:', res)

      // 保存 token
      this.globalData.token = res.access_token
      this.globalData.userInfo = res.user
      wx.setStorageSync('token', res.access_token)

      console.log('保存的用户信息:', res.user)

      return res
    } catch (err) {
      console.error('登录失败', err)
      throw err
    }
  },

  // 退出登录
  logout() {
    this.globalData.token = null
    this.globalData.userInfo = null
    wx.removeStorageSync('token')
    wx.redirectTo({
      url: '/pages/login/login'
    })
  }
})
