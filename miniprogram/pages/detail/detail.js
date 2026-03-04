// pages/detail/detail.js
const app = getApp()

Page({
  data: {
    invoice: null,
    loading: true
  },

  onLoad(options) {
    const id = options.id
    if (id) {
      this.loadInvoiceDetail(id)
    }
  },

  // 加载发票详情
  async loadInvoiceDetail(id) {
    this.setData({ loading: true })

    try {
      const res = await app.request({
        url: `/invoices/${id}`,
        method: 'GET'
      })

      this.setData({
        invoice: res,
        loading: false
      })
    } catch (err) {
      console.error('加载发票详情失败', err)
      this.setData({ loading: false })
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
    }
  },

  // 复制发票号码
  copyInvoiceNumber() {
    wx.setClipboardData({
      data: this.data.invoice.invoice_number,
      success: () => {
        wx.showToast({
          title: '已复制',
          icon: 'success'
        })
      }
    })
  },

  // 标记为已导出
  async markAsExported() {
    const id = this.data.invoice.id

    try {
      await app.request({
        url: `/invoices/${id}/export`,
        method: 'POST'
      })

      wx.showToast({
        title: '已标记为已导出',
        icon: 'success'
      })

      // 更新本地数据
      this.setData({
        'invoice.is_exported': true
      })
    } catch (err) {
      wx.showToast({
        title: '操作失败',
        icon: 'none'
      })
    }
  },

  // 分享发票
  onShareAppMessage() {
    const invoice = this.data.invoice
    return {
      title: `发票详情 - ${invoice.seller_name}`,
      path: `/pages/detail/detail?id=${invoice.id}`
    }
  },

  // 预览 PDF
  async previewPDF() {
    if (!this.data.invoice.pdf_path) {
      wx.showToast({
        title: '暂无 PDF 文件',
        icon: 'none'
      })
      return
    }

    wx.showLoading({
      title: '加载中...'
    })

    try {
      const app = getApp()
      const id = this.data.invoice.id

      // 下载PDF文件
      const downloadTask = wx.downloadFile({
        url: `${app.globalData.apiBase}/invoices/${id}/pdf`,
        header: {
          'Authorization': `Bearer ${app.globalData.token}`
        },
        success: (res) => {
          wx.hideLoading()

          if (res.statusCode === 200) {
            const filePath = res.tempFilePath

            // 打开文档
            wx.openDocument({
              filePath: filePath,
              fileType: 'pdf',
              showMenu: true,
              success: () => {
                console.log('打开PDF成功')
              },
              fail: (err) => {
                console.error('打开PDF失败', err)
                wx.showToast({
                  title: '打开PDF失败',
                  icon: 'none'
                })
              }
            })
          } else {
            wx.showToast({
              title: '下载失败',
              icon: 'none'
            })
          }
        },
        fail: (err) => {
          wx.hideLoading()
          console.error('下载PDF失败', err)
          wx.showToast({
            title: '下载失败',
            icon: 'none'
          })
        }
      })

      // 监听下载进度
      downloadTask.onProgressUpdate((res) => {
        console.log('下载进度', res.progress)
        if (res.progress > 0) {
          wx.showLoading({
            title: `下载中 ${res.progress}%`
          })
        }
      })

    } catch (err) {
      wx.hideLoading()
      console.error('预览PDF失败', err)
      wx.showToast({
        title: '预览失败',
        icon: 'none'
      })
    }
  }
})