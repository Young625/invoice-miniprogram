// pages/reimbursement/reimbursement.js
const app = getApp()

Page({
  data: {
    invoiceIds: [],
    invoices: [],
    totalAmount: 0,
    name: '',
    department: '',
    reason: '',
    loading: false
  },

  onLoad(options) {
    console.log('报销包页面 onLoad, options:', options)
    if (options.ids) {
      const ids = options.ids.split(',').filter(id => id && id.trim())
      console.log('解析后的 IDs:', ids)
      console.log('IDs 数量:', ids.length)
      this.setData({ invoiceIds: ids })
      this.loadInvoices(ids)
    } else {
      console.warn('未接收到发票 IDs')
    }
  },

  // 加载发票详情
  async loadInvoices(ids) {
    console.log('开始加载发票详情, IDs:', ids)
    try {
      // 获取所有发票详情
      const promises = ids.map(id =>
        app.request({
          url: `/invoices/${id}`,
          method: 'GET'
        })
      )

      const invoices = await Promise.all(promises)
      console.log('加载的发票数据:', invoices)

      const totalAmount = invoices.reduce((sum, inv) => {
        console.log('发票金额:', inv.total_amount)
        return sum + (inv.total_amount || 0)
      }, 0)

      console.log('计算的总金额:', totalAmount)

      this.setData({
        invoices: invoices,
        totalAmount: totalAmount.toFixed(2)
      }, () => {
        console.log('setData 完成, totalAmount:', this.data.totalAmount)
        console.log('setData 完成, invoices.length:', this.data.invoices.length)
      })
    } catch (err) {
      console.error('加载发票失败', err)
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
    }
  },

  // 输入事件
  onNameInput(e) {
    this.setData({ name: e.detail.value })
  },

  onDepartmentInput(e) {
    this.setData({ department: e.detail.value })
  },

  onReasonInput(e) {
    this.setData({ reason: e.detail.value })
  },

  // 生成报销包
  async generatePackage() {
    console.log('=== 开始生成报销包 ===')
    console.log('报销人:', this.data.name)
    console.log('部门:', this.data.department)
    console.log('发票IDs:', this.data.invoiceIds)

    if (!this.data.name) {
      wx.showToast({
        title: '请填写报销人',
        icon: 'none'
      })
      return
    }

    if (!this.data.department) {
      wx.showToast({
        title: '请填写部门',
        icon: 'none'
      })
      return
    }

    this.setData({ loading: true })
    console.log('开始请求后端API')

    try {
      const res = await app.request({
        url: '/reimbursement/generate',
        method: 'POST',
        data: {
          invoice_ids: this.data.invoiceIds,
          name: this.data.name,
          department: this.data.department,
          reason: this.data.reason
        },
        responseType: 'arraybuffer'
      })

      console.log('后端响应成功')
      console.log('响应数据类型:', typeof res)
      console.log('响应数据:', res)

      // 保存文件到本地
      const fs = wx.getFileSystemManager()
      const fileName = `报销包_${Date.now()}.zip`
      const filePath = `${wx.env.USER_DATA_PATH}/${fileName}`

      console.log('准备写入文件:', filePath)

      fs.writeFile({
        filePath: filePath,
        data: res,
        encoding: 'binary',
        success: () => {
          console.log('文件写入成功')
          this.setData({ loading: false })

          console.log('准备显示分享对话框')
          // 显示分享选项
          wx.showModal({
            title: '报销包已生成',
            content: '请选择操作方式',
            confirmText: '分享',
            cancelText: '保存',
            success: (modalRes) => {
              console.log('用户选择:', modalRes)
              if (modalRes.confirm) {
                console.log('用户选择分享')
                this.shareToWeChat(filePath)
              } else if (modalRes.cancel) {
                console.log('用户选择保存')
                this.saveToFavorites(filePath)
              }
            },
            fail: (err) => {
              console.error('showModal 失败:', err)
            }
          })
        },
        fail: (err) => {
          console.error('保存文件失败', err)
          this.setData({ loading: false })
          wx.showToast({
            title: '保存失败',
            icon: 'none'
          })
        }
      })
    } catch (err) {
      console.error('生成报销包失败', err)
      this.setData({ loading: false })
      wx.showToast({
        title: '生成失败',
        icon: 'none'
      })
    }
  },

  // 分享到微信
  shareToWeChat(filePath) {
    wx.shareFileMessage({
      filePath: filePath,
      success: () => {
        wx.showToast({
          title: '分享成功',
          icon: 'success'
        })
        // 返回列表页
        setTimeout(() => {
          wx.navigateBack()
        }, 1500)
      },
      fail: (err) => {
        console.error('分享失败', err)
        wx.showToast({
          title: '分享失败',
          icon: 'none'
        })
      }
    })
  },

  // 保存到收藏
  saveToFavorites(filePath) {
    // 获取系统信息，判断是iOS还是Android
    const systemInfo = wx.getSystemInfoSync()
    const isIOS = systemInfo.platform === 'ios'

    console.log('系统平台:', systemInfo.platform)
    console.log('是否为iOS:', isIOS)

    if (isIOS) {
      // iOS系统：使用 saveFileToDisk 保存到文件
      wx.saveFileToDisk({
        filePath: filePath,
        success: () => {
          wx.showToast({
            title: '保存成功',
            icon: 'success'
          })
          // 返回列表页
          setTimeout(() => {
            wx.navigateBack()
          }, 1500)
        },
        fail: (err) => {
          console.error('iOS保存文件失败', err)
          // 如果 saveFileToDisk 失败，尝试使用分享方式
          wx.showModal({
            title: '提示',
            content: 'iOS系统暂不支持直接保存zip文件，请使用分享功能发送到微信或其他应用',
            confirmText: '去分享',
            cancelText: '取消',
            success: (res) => {
              if (res.confirm) {
                this.shareToWeChat(filePath)
              }
            }
          })
        }
      })
    } else {
      // Android系统：使用 openDocument 打开文件
      wx.openDocument({
        filePath: filePath,
        fileType: 'zip',
        success: () => {
          wx.showToast({
            title: '已打开文件',
            icon: 'success'
          })
        },
        fail: (err) => {
          console.error('Android打开文件失败', err)
          // Android打开失败，尝试保存到磁盘
          wx.saveFileToDisk({
            filePath: filePath,
            success: () => {
              wx.showToast({
                title: '保存成功',
                icon: 'success'
              })
            },
            fail: (saveErr) => {
              console.error('保存到磁盘失败', saveErr)
              wx.showToast({
                title: '打开失败，请手动查找文件',
                icon: 'none'
              })
            }
          })
        }
      })
    }
  },

  // 分享小程序
  onShareAppMessage() {
    return {
      title: '发票管家 - 报销单生成',
      path: '/pages/index/index'
    }
  }
})
