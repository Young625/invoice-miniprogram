# 发票小程序后端开发文档汇总

> 本文档汇总了发票小程序后端开发过程中的所有重要文档和修复记录

**最后更新时间**: 2026-03-04

---

## 目录

1. [多邮箱功能](#1-多邮箱功能)
2. [Bug 修复记录](#2-bug-修复记录)
3. [数据迁移](#3-数据迁移)
4. [微信配置](#4-微信配置)
5. [登录实现](#5-登录实现)

---

## 1. 多邮箱功能

### 1.1 邮箱配置清理

**问题**: 旧的 `email_config` 字段与新的 `email_configs` 字段冲突

**修复内容**:
- 修改 `email_service.py` 支持多邮箱配置
- 遍历 `email_configs` 处理每个邮箱
- 发票记录添加 `email_account` 字段标识来源
- 清理数据库中的旧 `email_config` 字段

**数据迁移结果**:
- 总用户数: 3
- 清理前有旧 email_config 的用户: 2
- 清理后有旧 email_config 的用户: 0
- 有新 email_configs 的用户: 3

**关键代码**:
```python
# email_service.py - 支持多邮箱
for idx, email_config in enumerate(user.email_configs):
    client = EmailClient(...)
    emails = client.fetch_new_emails(...)
    # 处理每个邮箱的邮件
    invoice_dict["email_account"] = email_config.username
```

**相关文件**: `EMAIL_CONFIG_CLEANUP_REPORT.md`

---

### 1.2 多邮箱同步验证

**功能验证**:
- ✅ 用户可以配置最多 3 个邮箱
- ✅ 同步时会遍历所有邮箱
- ✅ 每个邮箱独立处理，互不影响
- ✅ 发票正确标记来源邮箱
- ✅ 去重逻辑正常工作（user_id + email_account + email_uid）

**测试数据**:
- 用户 3 配置了 2 个邮箱
- 成功从两个邮箱提取了 3 张发票
- 发票记录正确标记了来源邮箱
- 没有重复的邮件UID

**相关文档**: 见项目根目录 `MULTI_EMAIL_SYNC_VERIFICATION.md`

---

## 2. Bug 修复记录

### 2.1 发票金额字段解析错误

**问题**: 发票解析器返回空字符串，导致 Pydantic 验证失败

**错误信息**:
```
2 validation errors for Invoice
amount: Input should be a valid number, unable to parse string as a number
tax_amount: Input should be a valid number, unable to parse string as a number
```

**根本原因**:
- 发票解析器返回空字符串 `''` 而不是 `None`
- Invoice 模型期望 `float` 类型

**修复方案**:
```python
def parse_amount(value):
    """将金额字段转换为 float 或 None"""
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (ValueError, TypeError):
            return None
    return None

amount = parse_amount(info.amount)
tax_amount = parse_amount(info.tax_amount)
total_amount = parse_amount(info.total_amount)
```

**修复效果**:
- 即使金额解析失败，发票记录仍然可以保存
- 用户可以看到发票的其他信息
- 后续可以手动补充金额信息

**相关文件**: `INVOICE_AMOUNT_PARSING_FIX.md`

---

### 2.2 用户信息编辑功能修复

**问题**: 用户修改头像和昵称后，信息没有保存到数据库

**根本原因**: 后端接口参数定义错误
- 将请求体参数定义为查询参数
- 缺少 `avatar_url` 参数
- 返回值错误

**原代码（错误）**:
```python
@router.put("/profile")
async def update_profile(
    nickname: Optional[str] = None,  # ❌ 查询参数，不是请求体
    email: Optional[str] = None,
    ...
):
    return {"message": "更新成功"}  # ❌ 没有返回用户信息
```

**修复后**:
```python
@router.put("/profile", response_model=UserProfile)
async def update_profile(
    request: dict,  # ✅ 接收请求体
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    update_data = {}
    if "nickname" in request and request["nickname"]:
        update_data["nickname"] = request["nickname"]
    if "avatar_url" in request and request["avatar_url"]:
        update_data["avatar_url"] = request["avatar_url"]

    # 更新数据库并返回完整用户信息
    ...
    return UserProfile(...)
```

**相关文件**: `USER_PROFILE_UPDATE_FIX.md`

---

### 2.3 登录覆盖用户自定义信息

**问题**: 用户修改头像和昵称后，退出再登录，信息又变回默认的

**根本原因**: 登录接口每次都用微信信息覆盖数据库中的用户信息

**原代码（问题）**:
```python
else:
    # 已存在用户，更新昵称和头像
    update_data = {}
    if request.nickname:
        update_data["nickname"] = request.nickname  # ❌ 覆盖用户自定义
    if request.avatar_url:
        update_data["avatar_url"] = request.avatar_url  # ❌ 覆盖用户自定义

    await db.users.update_one(
        {"openid": openid},
        {"$set": update_data}
    )
```

**修复后**:
```python
else:
    # ✅ 已存在用户，不更新昵称和头像（用户可能已经自定义过）
    logger.info(f"用户已存在: openid={openid}，保留用户自定义信息")
    # 只更新最后登录时间
    await db.users.update_one(
        {"openid": openid},
        {"$set": {"updated_at": datetime.utcnow()}}
    )
```

**修复效果**:
- 首次登录时使用微信信息创建用户
- 再次登录时保留数据库中的信息，不覆盖
- 用户自定义的昵称和头像永久保存

**相关文件**: `LOGIN_OVERWRITE_FIX.md`

---

### 2.4 设置页面"未登录"问题

**问题**: 真机调试时，发票页面正常，但设置页面显示"未登录"

**根本原因**: `app.js` 中的 `getUserInfo()` 方法返回值错误

**原代码（错误）**:
```javascript
async getUserInfo() {
  const res = await this.request({ url: '/auth/profile' })
  this.globalData.userInfo = res.data  // ❌ 后端直接返回对象，不是 res.data
  return res.data
}
```

**修复后**:
```javascript
async getUserInfo() {
  const res = await this.request({ url: '/auth/profile' })
  this.globalData.userInfo = res  // ✅ 正确
  console.log('获取用户信息成功:', res)
  return res
}
```

**相关文档**: 见项目根目录 `USERINFO_SYNC_FIX.md`

---

## 3. 数据迁移

### 3.1 邮箱配置迁移

**目的**: 从单邮箱 `email_config` 迁移到多邮箱 `email_configs`

**迁移脚本**: `migrate_email_configs.py`

**迁移步骤**:
1. 查找所有有 `email_config` 的用户
2. 将 `email_config` 移动到 `email_configs` 数组
3. 保留 `email` 字段（主邮箱地址）
4. 支持回滚操作（`--rollback`）

**迁移结果**:
```
成功迁移 2 个用户:
- lshfapiao@163.com
- 4079194@qq.com
```

**相关文件**:
- `MIGRATION_GUIDE.md`
- `MIGRATION_REPORT.md`
- `migrate_email_configs.py`

---

### 3.2 邮件UID字段迁移

**目的**: 为旧发票记录添加 `email_uid` 字段用于去重

**迁移脚本**: `migrate_add_email_uid.py`

**迁移逻辑**:
- 为没有 `email_uid` 的发票生成唯一标识
- 使用 `user_id + invoice_number + created_at` 生成 hash

---

## 4. 微信配置

### 4.1 微信小程序配置说明

**配置文件**: `.env`

**必需配置**:
```env
WECHAT_APP_ID=your_app_id
WECHAT_APP_SECRET=your_app_secret
```

**开发模式**:
- 如果未配置微信参数，系统会使用开发模式
- 使用 `dev_{code}` 作为 openid
- 仅用于本地测试

**生产模式**:
- 配置真实的 AppID 和 AppSecret
- 调用微信 API 获取真实 openid
- 支持完整的微信登录流程

**相关文件**:
- `WECHAT_CONFIG_REPORT.md`
- `WECHAT_POLICY_EXPLANATION.md`

---

### 4.2 微信登录流程

**前端流程**:
1. 调用 `wx.login()` 获取 code
2. 调用 `wx.getUserProfile()` 获取用户信息
3. 发送 code + 用户信息到后端

**后端流程**:
1. 使用 code 换取 openid（调用微信 API）
2. 查找或创建用户
3. 生成 JWT token
4. 返回 token 和用户信息

**相关文件**: `LOGIN_IMPLEMENTATION.md`

---

## 5. 调试指南

### 5.1 常见问题排查

**问题1: 登录失败**
- 检查微信配置是否正确
- 查看后端日志中的错误信息
- 验证 code 是否有效（5分钟过期）

**问题2: 邮件同步失败**
- 检查邮箱配置是否正确
- 验证 IMAP 服务器和端口
- 确认授权码是否有效

**问题3: 发票解析失败**
- 查看日志中的错误信息
- 检查 PDF 格式是否支持
- 验证 OCR 服务是否正常

**相关文件**: `DEBUG_GUIDE.md`

---

### 5.2 Bug 记录

**历史 Bug 汇总**: `BUG_RECORDS.md`

**重要 Bug 修复**:
- Bug 9: 微信配置问题 (`BUG9_FIX_GUIDE.md`)
- Bug 10: 登录流程问题 (`BUG10_FIX_GUIDE.md`)
- Bug 11: 数据同步问题 (`BUG_11_SUMMARY.md`)

---

## 6. 代码变更检查清单

在部署前，请检查以下内容：

**环境配置**:
- [ ] `.env` 文件配置正确
- [ ] 数据库连接正常
- [ ] 微信配置已设置

**数据迁移**:
- [ ] 运行所有必要的迁移脚本
- [ ] 验证数据迁移结果
- [ ] 备份数据库

**功能测试**:
- [ ] 登录功能正常
- [ ] 邮箱配置功能正常
- [ ] 发票同步功能正常
- [ ] 用户信息编辑功能正常

**相关文件**: `CODE_CHANGES_CHECKLIST.md`

---

## 7. 项目结构

```
backend/
├── app/
│   ├── api/          # API 路由
│   │   ├── auth.py   # 认证相关
│   │   ├── user.py   # 用户相关
│   │   └── invoice.py # 发票相关
│   ├── models/       # 数据模型
│   ├── services/     # 业务逻辑
│   │   └── email_service.py  # 邮件服务
│   ├── core/         # 核心配置
│   └── schemas/      # Pydantic schemas
├── .env              # 环境配置
├── main.py           # 应用入口
└── requirements.txt  # 依赖包
```

---

## 8. 技术栈

**后端框架**:
- FastAPI - Web 框架
- Motor - 异步 MongoDB 驱动
- Pydantic - 数据验证
- JWT - 身份认证

**数据库**:
- MongoDB - 主数据库

**邮件处理**:
- imaplib - IMAP 协议
- email - 邮件解析

**发票解析**:
- PyPDF2 - PDF 解析
- OCR - 文字识别

---

## 9. API 文档

### 9.1 认证接口

**POST /auth/login**
- 功能: 微信登录
- 请求: `{code, nickname, avatar_url}`
- 响应: `{access_token, user}`

**GET /auth/profile**
- 功能: 获取用户信息
- 认证: Bearer Token
- 响应: `{openid, nickname, avatar_url, email}`

**PUT /auth/profile**
- 功能: 更新用户信息
- 认证: Bearer Token
- 请求: `{nickname, avatar_url, email}`
- 响应: `{openid, nickname, avatar_url, email}`

### 9.2 邮箱配置接口

**GET /user/email-configs**
- 功能: 获取所有邮箱配置
- 认证: Bearer Token
- 响应: `[{username, imap_server, ...}]`

**POST /user/email-configs**
- 功能: 添加邮箱配置
- 认证: Bearer Token
- 请求: `{username, auth_code, imap_server, ...}`

**PUT /user/email-configs/{index}**
- 功能: 更新邮箱配置
- 认证: Bearer Token

**DELETE /user/email-configs/{index}**
- 功能: 删除邮箱配置
- 认证: Bearer Token

**PUT /user/email-configs/set-primary/{index}**
- 功能: 设置主邮箱
- 认证: Bearer Token

### 9.3 发票接口

**GET /invoices**
- 功能: 获取发票列表
- 认证: Bearer Token
- 参数: `page, page_size, keyword, start_date, end_date`

**POST /invoices/sync**
- 功能: 手动同步发票
- 认证: Bearer Token
- 响应: `{message, invoice_count}`

**GET /invoices/stats**
- 功能: 获取发票统计
- 认证: Bearer Token
- 响应: `{total_count, total_amount, month_count, ...}`

---

## 10. 部署说明

### 10.1 环境要求

- Python 3.8+
- MongoDB 4.0+
- 微信小程序账号

### 10.2 部署步骤

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件
   ```

3. **运行数据迁移**
   ```bash
   python migrate_email_configs.py
   python cleanup_email_config.py
   ```

4. **启动服务**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

### 10.3 生产环境配置

- 使用 Gunicorn + Uvicorn 部署
- 配置 Nginx 反向代理
- 启用 HTTPS
- 配置日志轮转
- 设置进程守护

---

## 11. 维护建议

### 11.1 定期任务

- 每周备份数据库
- 每月检查日志文件大小
- 定期更新依赖包
- 监控服务器资源使用

### 11.2 性能优化

- 添加数据库索引
- 实现缓存机制
- 优化邮件同步频率
- 并发处理多个邮箱

### 11.3 安全建议

- 定期更新密钥
- 限制 API 请求频率
- 验证用户输入
- 加密敏感信息

---

## 12. 联系方式

如有问题，请查看相关文档或联系开发团队。

**文档版本**: v1.0
**最后更新**: 2026-03-04
