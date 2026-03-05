# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 待添加的新功能

### Changed
- 待修改的功能

### Fixed
- 待修复的问题

## [2.0.4] - 2026-03-05

### Added
- 发票项目分类功能
  - 后端：发票模型添加 project_name 字段
  - 后端：发票列表 API 支持项目筛选
  - 后端：新增发票更新 API（支持更新项目名称）
  - 后端：邮件服务自动提取并分类发票项目（11个固定类别）
  - 前端：发票列表页面添加项目筛选器
  - 前端：发票详情页面显示项目类别
  - 前端：优化筛选器 UI 设计（卡片式布局）
- 日志系统
  - 日志配置模块（按日期轮转、自动压缩、按月份组织）
  - 日志管理脚本（clean_logs.sh、view_logs.sh）
  - 日志系统文档（LOGGING.md）
- 数据库迁移脚本
  - migrate_project_name.py
  - migrate_project_name_optimized.py
  - update_project_categories.py
  - verify_migration.py
- 用户邮箱配置功能
  - 后端 API 支持邮箱配置的保存和获取
  - 用户模型添加邮箱配置字段
- 安全配置文档（SECURITY.md）

### Changed
- 优化邮件服务
  - 改进邮件提取逻辑
  - 增强错误处理
  - 自动提取发票项目名称（支持星号格式解析）
- 优化报销服务
  - 改进中文字体注册逻辑
  - 优先使用 TTF 字体文件（避免 TTC 兼容性问题）
  - 增强字体加载的容错性
  - 改进 Excel 生成逻辑
- 优化小程序设置页面
  - 完善邮箱配置界面
  - 改进用户体验
  - 优化页面样式
- 优化小程序列表页面
  - 重新设计筛选器 UI（图标 + 卡片式布局）
  - 添加项目标签显示
  - 改进视觉效果和交互体验
- 优化小程序详情页面
  - 添加项目类别显示
  - 优化样式
- 优化小程序报销页面
  - 改进 UI 和交互
  - 优化样式和布局
- 更新小程序配置
  - 添加更新检查防抖（5分钟）
  - 版本号更新至 2.0.4
- 更新后端依赖包

### Security
- 从 Git 跟踪中移除敏感配置文件
  - .claude/settings.local.json
  - miniprogram/project.private.config.json
- 更新 .gitignore，排除敏感文件
- 添加安全配置指南

### Fixed
- 修复报销服务中文字体显示问题
- 修复小程序频繁检查更新的问题

## [0.2.0] - 2026-03-05

### Added
- GitHub Actions 自动化工作流
  - 后端 CI/CD 流程（测试、代码检查）
  - 代码质量检查流程
  - 自动发布流程
  - PR 自动检查流程
- Markdown 代码规范配置
- 测试框架和示例测试
  - pytest 配置
  - 配置模块测试
  - 安全模块测试
  - API 端点测试
  - 测试文档
- GitHub Actions 状态徽章
- MIT License

### Changed
- 更新 README.md，添加构建状态徽章

### Fixed
- 待修复的问题

## [0.1.0] - 2026-03-04

### Added
- 微信小程序前端
  - 用户登录和认证页面
  - 首页统计展示（本月/累计发票数据）
  - 发票列表页面（搜索、筛选、分页）
  - 发票详情页面
  - 用户设置页面
  - 报销管理页面
- Python FastAPI 后端
  - JWT 用户认证系统
  - 发票 CRUD API
  - 统计分析 API
  - 用户管理 API
  - 报销管理 API
- 发票处理功能
  - 邮件发票自动提取
  - PDF 发票解析
  - 发票去重机制
  - MongoDB 数据存储
- 项目配置
  - .gitignore 配置（排除缓存、日志、数据库文件）
  - 环境变量配置示例
  - README 项目文档
  - 开发文档

### Infrastructure
- 初始化 Git 仓库
- 创建 GitHub 远程仓库
- 建立分支管理策略（main/develop）
- 创建首个版本标签 v0.1.0

[Unreleased]: https://github.com/Young625/invoice-miniprogram/compare/v2.0.4...HEAD
[2.0.4]: https://github.com/Young625/invoice-miniprogram/compare/v0.2.0...v2.0.4
[0.2.0]: https://github.com/Young625/invoice-miniprogram/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Young625/invoice-miniprogram/releases/tag/v0.1.0
