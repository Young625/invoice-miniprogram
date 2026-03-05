# 日志系统说明

## 日志文件结构

系统采用按日期轮转的日志系统,自动组织和压缩:

```
logs/
├── 2026-03/                          # 按月份组织
│   ├── application.log               # 当前应用日志(所有级别)
│   ├── application-error.log         # 当前错误日志(ERROR及以上)
│   ├── application-2026-03-01.0.log.zip      # 历史日志(压缩)
│   ├── application-2026-03-02.0.log.zip
│   ├── application-error-2026-03-01.0.log.zip
│   └── application-error-2026-03-02.0.log.zip
├── 2026-04/                          # 下个月的日志
│   └── ...
└── nohup.log                         # 启动日志(在logs根目录)
```

## 日志文件说明

### 应用日志 (application)
- **当前文件**: `logs/YYYY-MM/application.log`
- **历史文件**: `logs/YYYY-MM/application-YYYY-MM-DD.0.log.zip`
- **内容**: 所有级别的日志(DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **轮转**: 每天午夜自动轮转
- **压缩**: 自动压缩为ZIP格式

### 错误日志 (application-error)
- **当前文件**: `logs/YYYY-MM/application-error.log`
- **历史文件**: `logs/YYYY-MM/application-error-YYYY-MM-DD.0.log.zip`
- **内容**: 只记录ERROR和CRITICAL级别的日志
- **轮转**: 每天午夜自动轮转
- **压缩**: 自动压缩为ZIP格式

### 启动日志 (nohup.log)
- **位置**: `logs/nohup.log`
- **内容**: uvicorn服务的启动输出
- **特点**: 追加模式,保留历史记录

## 日志特性

### 1. 按日期轮转
- 每天午夜(00:00)自动轮转
- 昨天的日志自动重命名并压缩
- 新的一天开始使用新的日志文件

### 2. 按月份组织
- 每个月的日志存放在独立目录
- 格式: `logs/YYYY-MM/`
- 便于归档和管理

### 3. 自动压缩
- 历史日志自动压缩为ZIP格式
- 节省磁盘空间(通常压缩率70-90%)
- 保持原始文件名便于识别

### 4. 双日志文件
- **application.log**: 完整日志,包含所有信息
- **application-error.log**: 错误日志,便于快速定位问题

## 日志级别

当前日志级别: **INFO**

日志格式: `时间 - 模块名 - 级别 - 消息`

示例:
```
2026-03-05 18:28:46,920 - app.services.scheduler_service - INFO - 启动定时任务服务
2026-03-05 18:28:47,123 - app.api.invoice - ERROR - 发票处理失败: 文件不存在
```

## 查看日志

### 查看当前日志

```bash
# 查看当前应用日志
tail -f logs/$(date +%Y-%m)/application.log

# 查看当前错误日志
tail -f logs/$(date +%Y-%m)/application-error.log

# 查看最新50行
tail -n 50 logs/$(date +%Y-%m)/application.log
```

### 查看历史日志

```bash
# 解压历史日志
unzip logs/2026-03/application-2026-03-01.0.log.zip

# 直接查看压缩文件内容(不解压)
unzip -p logs/2026-03/application-2026-03-01.0.log.zip | less

# 搜索压缩日志中的内容
unzip -p logs/2026-03/application-2026-03-01.0.log.zip | grep "ERROR"
```

### 使用日志查看脚本

```bash
./view_logs.sh
```

### 搜索日志

```bash
# 搜索当前月份的错误
grep "ERROR" logs/$(date +%Y-%m)/application.log

# 搜索所有历史日志中的关键词
for file in logs/2026-03/*.zip; do
    echo "=== $file ==="
    unzip -p "$file" | grep "关键词"
done
```

## 日志管理

### 自动管理
- ✓ 每天自动轮转
- ✓ 自动压缩节省空间
- ✓ 按月份自动组织
- ✓ 无需手动干预

### 手动清理

清理旧月份的日志:

```bash
# 删除3个月前的日志
find logs/ -type d -name "2025-*" -mtime +90 -exec rm -rf {} \;

# 或使用清理脚本
./clean_logs.sh
```

### 磁盘空间监控

```bash
# 查看日志目录总大小
du -sh logs/

# 查看每个月的日志大小
du -sh logs/*/

# 查看压缩效果
ls -lh logs/2026-03/
```

## 日志配置

日志配置位于 `app/core/logging_config.py`:

```python
# 配置日志系统
setup_logging(
    base_dir='logs',           # 日志基础目录
    log_level=logging.INFO     # 日志级别
)
```

### 自定义配置

可以修改以下参数:

1. **日志级别**
   ```python
   log_level=logging.DEBUG  # 更详细的日志
   log_level=logging.WARNING  # 只记录警告和错误
   ```

2. **轮转时间**
   在 `logging_config.py` 中修改:
   ```python
   when='midnight'  # 每天午夜
   when='H'         # 每小时
   interval=1       # 间隔
   ```

3. **保留天数**
   ```python
   backupCount=30   # 只保留30天的日志
   backupCount=0    # 不限制(默认)
   ```

## 常见问题

### Q: 如何查看昨天的日志?

A: 历史日志已压缩,使用以下命令:
```bash
# 方法1: 解压后查看
unzip logs/2026-03/application-2026-03-04.0.log.zip
cat application-2026-03-04.0.log

# 方法2: 直接查看(不解压)
unzip -p logs/2026-03/application-2026-03-04.0.log.zip | less
```

### Q: 日志文件太多怎么办?

A:
1. 日志已自动压缩,占用空间很小
2. 可以定期删除旧月份的日志
3. 可以设置 `backupCount` 限制保留天数

### Q: 如何只查看错误日志?

A:
```bash
# 查看当前错误日志
tail -f logs/$(date +%Y-%m)/application-error.log

# 或从完整日志中筛选
grep "ERROR" logs/$(date +%Y-%m)/application.log
```

### Q: 日志轮转时间可以改吗?

A: 可以,在 `app/core/logging_config.py` 中修改 `when` 参数:
- `'midnight'`: 每天午夜
- `'H'`: 每小时
- `'D'`: 每天(可指定时间)
- `'W0'`-`'W6'`: 每周(0=周一)

### Q: 如何备份日志?

A:
```bash
# 备份整个月的日志
tar -czf logs_backup_2026-03.tar.gz logs/2026-03/

# 备份到远程服务器
rsync -av logs/ user@backup-server:/backup/logs/
```

## 监控建议

### 1. 错误监控

每天检查错误日志:
```bash
# 查看今天的错误
tail -n 100 logs/$(date +%Y-%m)/application-error.log

# 统计错误数量
grep -c "ERROR" logs/$(date +%Y-%m)/application.log
```

### 2. 磁盘空间监控

```bash
# 检查日志目录大小
du -sh logs/

# 设置告警(超过1GB)
size=$(du -sm logs/ | cut -f1)
if [ $size -gt 1024 ]; then
    echo "警告: 日志目录超过1GB"
fi
```

### 3. 日志分析

```bash
# 统计最常见的错误
unzip -p logs/2026-03/*.zip | grep "ERROR" | sort | uniq -c | sort -rn | head -10

# 分析访问量
grep "GET\|POST" logs/$(date +%Y-%m)/application.log | wc -l
```

### 4. 自动化脚本

创建定时任务(crontab):
```bash
# 每天凌晨1点备份昨天的日志
0 1 * * * /path/to/backup_logs.sh

# 每周日清理3个月前的日志
0 2 * * 0 find /path/to/logs/ -type d -mtime +90 -exec rm -rf {} \;
```

## 性能影响

- **CPU**: 日志压缩在轮转时进行,对运行时性能无影响
- **磁盘**: 压缩后日志大小通常为原始大小的10-30%
- **I/O**: 异步写入,不阻塞主线程

## 故障排查

### 日志文件未生成

1. 检查目录权限:
   ```bash
   ls -ld logs/
   ```

2. 检查磁盘空间:
   ```bash
   df -h
   ```

3. 查看错误信息:
   ```bash
   tail -f logs/nohup.log
   ```

### 日志未压缩

1. 检查是否到了轮转时间(午夜)
2. 查看是否有错误日志
3. 手动触发测试:
   ```python
   from app.core.logging_config import setup_logging
   logger = setup_logging()
   # 等待到午夜观察
   ```

### 无法解压日志

```bash
# 检查ZIP文件完整性
unzip -t logs/2026-03/application-2026-03-01.0.log.zip

# 如果损坏,尝试修复
zip -FF logs/2026-03/application-2026-03-01.0.log.zip --out fixed.zip
```
