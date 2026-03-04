# 发票管理小程序

[![Backend CI](https://github.com/Young625/invoice-miniprogram/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/Young625/invoice-miniprogram/actions/workflows/backend-ci.yml)
[![Code Quality](https://github.com/Young625/invoice-miniprogram/actions/workflows/code-quality.yml/badge.svg)](https://github.com/Young625/invoice-miniprogram/actions/workflows/code-quality.yml)
[![Release](https://github.com/Young625/invoice-miniprogram/actions/workflows/release.yml/badge.svg)](https://github.com/Young625/invoice-miniprogram/actions/workflows/release.yml)
[![GitHub release](https://img.shields.io/github/v/release/Young625/invoice-miniprogram)](https://github.com/Young625/invoice-miniprogram/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

完整的发票管理小程序，包含前端和后端。

## 项目结构

```
invoice-miniprogram/
├── miniprogram/          # 小程序前端
│   ├── pages/           # 页面
│   │   ├── login/      # 登录页
│   │   ├── index/      # 首页
│   │   ├── list/       # 列表页
│   │   ├── detail/     # 详情页
│   │   └── settings/   # 设置页
│   ├── app.js          # 小程序入口
│   ├── app.json        # 全局配置
│   └── app.wxss        # 全局样式
├── backend/             # 后端服务
│   └── (见 backend/README.md)
└── docs/                # 文档
```

## 快速开始

### 1. 后端启动

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 启动 MongoDB
brew services start mongodb-community
# 启动后端
uvicorn main:app --reload
```

### 2. 小程序开发

1. 下载并安装[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 打开微信开发者工具
3. 导入项目，选择 `miniprogram` 目录
4. 使用测试 AppID 或申请正式 AppID
5. 点击"编译"运行

### 3. 配置后端地址

修改 `miniprogram/app.js` 中的 `apiBase`：

```javascript
globalData: {
  apiBase: 'http://localhost:8000/api'  // 本地开发
  // apiBase: 'https://your-domain.com/api'  // 生产环境
}
```

## 功能特性

### 已完成功能 ✅

**用户端**：
- 微信登录
- 发票统计（本月/累计）
- 最近发票列表
- 发票详情查看
- 手动同步发票
- 发票搜索和筛选

**后端 API**：
- JWT 认证
- 用户管理
- 发票 CRUD
- 统计分析
- 分页查询

### 待完成功能 🚧

- 邮箱配置
- 定时任务集成
- PDF 预览
- Excel 导出
- 发票分享
- 通知推送

## 页面说明

### 登录页 (pages/login)
- 渐变背景设计
- 微信授权登录
- 功能特性展示

### 首页 (pages/index)
- 统计卡片（本月/累计数据）
- 快速操作（同步、查看全部）
- 最近发票列表
- 下拉刷新

### 列表页 (pages/list)
- 发票列表展示
- 搜索功能
- 日期/类型筛选
- 分页加载

### 详情页 (pages/detail)
- 完整发票信息
- PDF 预览
- 分享/导出功能

### 设置页 (pages/settings)
- 邮箱配置
- 通知设置
- 关于信息

## 设计规范

### 色彩
- 主色：#1989FA (蓝色)
- 成功：#07C160 (绿色)
- 警告：#FF976A (橙色)
- 错误：#EE0A24 (红色)

### 字体
- 标题：18px / bold
- 副标题：16px / medium
- 正文：14px / regular
- 辅助：12px / regular

## 开发说明

### 添加新页面

1. 在 `pages/` 创建页面目录
2. 创建 `.js`, `.wxml`, `.wxss`, `.json` 文件
3. 在 `app.json` 的 `pages` 数组中注册

### 网络请求

使用 `app.request()` 方法：

```javascript
const app = getApp()

// GET 请求
const data = await app.request({
  url: '/invoices',
  method: 'GET'
})

// POST 请求
await app.request({
  url: '/invoices/sync',
  method: 'POST',
  data: { key: 'value' }
})
```

### 认证处理

- Token 自动添加到请求头
- 401 自动跳转登录页
- 使用 `app.globalData.token` 检查登录状态

## 部署

### 小程序发布

1. 申请小程序 AppID
2. 配置服务器域名（需备案）
3. 上传代码到微信后台
4. 提交审核

### 后端部署

见 `backend/README.md`

## 注意事项

- 小程序要求 HTTPS
- 服务器域名需要备案
- 配置合法域名白名单
- 定期更新依赖版本

## License

MIT
