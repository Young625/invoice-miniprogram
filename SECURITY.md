# 安全配置说明

## ⚠️ 重要：敏感信息保护

本项目包含敏感配置信息，请务必遵循以下安全规范：

### 1. 环境变量配置

**永远不要**将以下信息提交到 Git：
- 数据库密码
- API 密钥和 Token
- JWT Secret Key
- 微信小程序 AppID 和 AppSecret
- 邮箱账号密码
- 任何生产环境的配置

### 2. 配置文件管理

#### 后端配置 (`backend/app/core/config.py`)
- `SECRET_KEY`: 使用强随机字符串，生产环境必须修改
- `WECHAT_APP_ID` 和 `WECHAT_APP_SECRET`: 从环境变量读取
- `MONGODB_URL`: 生产环境使用环境变量

#### 环境变量文件 (`.env`)
```bash
# 复制 .env.example 并修改
cp backend/.env.example backend/.env

# 在 .env 中配置真实的敏感信息
SECRET_KEY=your-strong-random-secret-key-here
WECHAT_APP_ID=your-wechat-app-id
WECHAT_APP_SECRET=your-wechat-app-secret
MONGODB_URL=mongodb://username:password@host:port/database
```

### 3. 小程序配置

#### API 地址 (`miniprogram/app.js`)
- 开发环境：使用本地地址
- 生产环境：使用 HTTPS 域名
- **不要**在代码中硬编码生产环境的敏感配置

#### 私有配置 (`miniprogram/project.private.config.json`)
- 此文件已添加到 `.gitignore`
- 包含本地开发配置，不应提交到 Git

### 4. 已忽略的敏感文件

以下文件/目录已在 `.gitignore` 中配置：
- `.env` - 环境变量配置
- `.claude/` - Claude 设置（可能包含敏感权限）
- `miniprogram/project.private.config.json` - 小程序私有配置
- `data/` - 生成的数据文件
- `backend/mongodb-data/` - 数据库文件

### 5. 生成强密钥

使用以下命令生成强随机密钥：

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL
openssl rand -base64 32
```

### 6. 检查敏感信息泄露

在提交前检查：
```bash
# 检查是否有敏感信息
git diff

# 检查暂存的文件
git diff --cached

# 搜索可能的密码/密钥
git grep -i "password\|secret\|key" -- '*.py' '*.js'
```

### 7. 如果不小心提交了敏感信息

```bash
# 从 Git 历史中删除文件
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/sensitive/file" \
  --prune-empty --tag-name-filter cat -- --all

# 强制推送（谨慎使用）
git push origin --force --all

# 立即更改泄露的密钥/密码
```

## 最佳实践

1. ✅ 使用环境变量存储敏感信息
2. ✅ 提供 `.env.example` 作为配置模板
3. ✅ 在 `.gitignore` 中排除敏感文件
4. ✅ 定期审查提交内容
5. ✅ 使用强随机密钥
6. ✅ 生产环境和开发环境分离配置
7. ✅ 定期更新密钥和密码

## 参考资源

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security)
- [12-Factor App](https://12factor.net/config)
