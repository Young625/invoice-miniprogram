# 发票管理系统 - 后端 API

基于 FastAPI + MongoDB 的发票管理系统后端服务。

## 功能特性

- ✅ 用户认证（JWT）
- ✅ 发票列表（分页、搜索、筛选）
- ✅ 发票详情
- ✅ 发票统计
- ✅ 邮箱配置
- ✅ 自动发票提取（定时任务）

## 技术栈

- **框架**: FastAPI 0.109.0
- **数据库**: MongoDB
- **认证**: JWT (python-jose)
- **异步**: motor (MongoDB 异步驱动)
- **定时任务**: APScheduler

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# MongoDB 配置
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=invoice_db

# JWT 配置
SECRET_KEY=your-secret-key-change-in-production

# 微信小程序配置（后续填入）
WECHAT_APP_ID=
WECHAT_APP_SECRET=
```

### 3. 启动 MongoDB

```bash
# macOS
brew services start mongodb-community

# 或手动启动
mongod --config /usr/local/etc/mongod.conf
```

### 4. 启动服务

```bash
# 开发模式（自动重载）
uvicorn main:app --reload

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000
```

服务将在 http://localhost:8000 启动

## API 文档

启动服务后访问：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 接口

### 认证相关

```
POST   /api/auth/login          # 微信登录
GET    /api/auth/profile        # 获取用户信息
PUT    /api/auth/profile        # 更新用户信息
```

### 发票相关

```
GET    /api/invoices            # 获取发票列表
GET    /api/invoices/stats      # 获取统计数据
GET    /api/invoices/{id}       # 获取发票详情
POST   /api/invoices/sync       # 手动同步邮箱
POST   /api/invoices/{id}/export # 标记为已导出
```

## 项目结构

```
backend/
├── app/
│   ├── api/              # API 路由
│   │   ├── auth.py       # 认证接口
│   │   └── invoice.py    # 发票接口
│   ├── core/             # 核心功能
│   │   ├── config.py     # 配置
│   │   ├── database.py   # 数据库
│   │   └── security.py   # 安全
│   ├── models/           # 数据模型
│   │   ├── user.py       # 用户模型
│   │   └── invoice.py    # 发票模型
│   ├── schemas/          # 数据验证
│   │   ├── auth.py       # 认证模式
│   │   └── invoice.py    # 发票模式
│   └── services/         # 业务逻辑
├── main.py               # 应用入口
└── requirements.txt      # 依赖列表
```

## 开发说明

### 添加新的 API 接口

1. 在 `app/api/` 创建路由文件
2. 在 `main.py` 中注册路由
3. 定义数据模型和验证模式

### 数据库操作

使用 motor 异步驱动：

```python
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_database

async def example(db: AsyncIOMotorDatabase = Depends(get_database)):
    # 查询
    result = await db.collection.find_one({"key": "value"})

    # 插入
    await db.collection.insert_one({"key": "value"})

    # 更新
    await db.collection.update_one(
        {"key": "value"},
        {"$set": {"new_key": "new_value"}}
    )
```

## 部署

### Docker 部署

```bash
# 构建镜像
docker build -t invoice-api .

# 运行容器
docker run -d -p 8000:8000 invoice-api
```

### 云服务器部署

1. 安装 Python 3.11+
2. 安装 MongoDB
3. 克隆代码
4. 安装依赖
5. 配置环境变量
6. 使用 systemd 或 supervisor 管理进程

## 注意事项

- 生产环境务必修改 `SECRET_KEY`
- 配置 HTTPS
- 设置合适的 CORS 策略
- 定期备份 MongoDB 数据
- 监控服务运行状态

## License

MIT
