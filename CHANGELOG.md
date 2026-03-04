# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Actions 自动化工作流
  - 后端 CI/CD 流程（测试、代码检查）
  - 代码质量检查流程
  - 自动发布流程
  - PR 自动检查流程
- Markdown 代码规范配置

### Changed
- 待修改的功能

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

[Unreleased]: https://github.com/Young625/invoice-miniprogram/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Young625/invoice-miniprogram/releases/tag/v0.1.0
