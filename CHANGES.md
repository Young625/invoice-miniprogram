# 变更记录

## v2.0.6 (2026-03-19)

### Bug 修复

- **修复：重复发票邮件每次同步都重复扫描**
  - 根本原因：`email_uid` 只存在发票记录里，当邮件内所有发票均为重复时不会写入任何发票记录，导致该邮件的 UID 未被记录，下次同步重复处理
  - 新增 `processed_emails` 集合，统一记录所有已处理过的邮件（含无发票邮件、全重复发票邮件），去重逻辑从查 `invoices` 改为查 `processed_emails`

- **修复：更新邮箱配置会丢失同步游标**
  - `update_email_config` 整体替换配置时未保留 `last_sync_date`，导致游标重置，下次同步变为首次同步重新扫描 30 天邮件
  - 更新配置时保留原有 `last_sync_date`

- **修复：无用 import 可能导致启动失败**
  - 移除 `email_service.py` 中未使用的 `StorageManager`、`DedupManager` 导入

### 其他

- 小程序 `wx.request` 超时从默认 60 秒调整为 120 秒，避免邮件较多时同步请求超时报错
- 新增 `check_uid.py` 调试脚本，可查看邮箱中邮件的 UID、日期、标题

---

# 邮箱同步逻辑优化 — 变更记录

## 变更概述

本次重构优化了贴票侠的邮箱发票同步逻辑，解决了原有方案中的 Bug、性能瓶颈和逻辑缺陷，引入基于日期游标的增量同步机制。

---

## 变更文件

### 1. `backend/app/models/user.py`

**变更内容：** `EmailConfig` 新增 `last_sync_date` 字段

```python
last_sync_date: Optional[datetime] = None
```

**原因：**
- 原方案依赖 IMAP 已读/未读状态（`UNSEEN`）来判断是否处理过某封邮件。用户在手机端手动标记已读会导致下次同步跳过未提取的邮件，造成发票丢失。
- 新方案以时间游标替代已读状态，每次同步后记录"已检查到哪封邮件"，后续同步从该时间点向后推进，与已读/未读完全解耦。
- `last_sync_date` 存储在 `EmailConfig` 层（per-邮箱），支持用户绑定多个邮箱时各自独立推进游标。

---

### 2. `src/email_client.py`

**变更内容：** 全面重构，替换 `fetch_new_emails` 为 `fetch_emails`，新增多个辅助方法

#### 2.1 修复：序列号 → 真实 IMAP UID

**原代码：**
```python
status, data = self._conn.search(None, criteria)   # 返回序列号
self._conn.fetch(uid_bytes, "(RFC822)")             # 用序列号 fetch
```

**新代码：**
```python
status, data = self._conn.uid('search', None, criteria)   # 返回真实 UID
self._conn.uid('fetch', uid_bytes, '(BODY.PEEK[])')       # 用 UID fetch
```

**原因：**
- IMAP 序列号（Sequence Number）在其他邮件被删除时会重新排列，导致数据库中存储的 `email_uid` 与实际邮件不对应，email_uid 去重机制完全失效，同一封邮件可能被重复处理。
- IMAP UID 在同一 UIDVALIDITY 周期内保持稳定，邮件删除不影响其他邮件的 UID。

#### 2.2 修复：首次同步不再过滤已读邮件

**原代码：**
```python
criteria = f'UNSEEN SINCE {since_str}'   # 只搜索未读邮件
```

**新代码：**
```python
criteria = f'SINCE {since_str}'          # 搜索近 30 天所有邮件，不区分已读/未读
```

**原因：**
- 原方案首次同步使用 `UNSEEN` 过滤，用户在绑定邮箱之前已经读过的发票邮件会被直接跳过，导致漏同步。
- 去掉 `UNSEEN` 后，首次同步检查近 30 天所有邮件（读/未读均包含），取最新 50 封，靠 `email_uid` 去重防止重复处理，不依赖已读状态。

#### 2.3 修复：首次同步取最新 50 封而非最旧 50 封

**原代码：**
```python
uid_list = uid_list[:max_count]   # 取最旧 N 封
```

**新代码（首次同步）：**
```python
uid_list = uid_list[-max_count:]  # 取最新 N 封
```

**原因：**
- 原代码对未读邮件列表取前 50 个，即最旧的 50 封。若用户收件箱有数百封未读邮件，首次同步拿到的全是几个月前的旧邮件，用户最近收到的发票却无法及时同步。
- 首次同步应取最新 50 封，让用户立即看到最近的发票；后续同步取最旧 50 封，从游标往后逐步推进。

#### 2.3 优化：两阶段 FETCH，大幅减少带宽消耗**原方案：**
- 对每封邮件直接 `FETCH RFC822`，下载完整内容（含所有附件）
- 50 封邮件 × 平均 2-5 MB = 每次同步可能下载 100-250 MB

**新方案（两阶段）：**

**阶段 1 — 批量获取元数据（一次请求，几 KB）：**
```
UID FETCH 101,102,...,150 (UID INTERNALDATE BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])
```
- 获取每封邮件的 INTERNALDATE（服务器时间戳）
- 检查 BODYSTRUCTURE 中是否包含 PDF 相关标识
- 获取邮件主题，用于关键词辅助判断

**阶段 2 — 按需下载完整邮件：**
- 跳过条件：BODYSTRUCTURE 中无 PDF 标识，且主题不含发票关键词（`发票/invoice/报销/receipt` 等）
- 只对"可能含有发票"的邮件执行 `UID FETCH BODY.PEEK[]`

**原因：**
- 大多数收件箱邮件（广告、通知、普通往来）不含 PDF 附件，无需下载完整内容。
- 阶段 1 批量请求只需一次网络往返，阶段 2 只下载真正需要的邮件，带宽消耗可降低 80-90%。
- `BODY.PEEK[]` 等同于 `RFC822` 但不触发 `\Seen` 标记，不改变用户邮箱状态。

#### 2.4 优化：使用 INTERNALDATE 替代 Date 头

**原代码：**
```python
date=msg.get("Date", "")   # 邮件头 Date 字段
```

**新代码：**
```python
date=meta.get('internaldate_str') or msg.get("Date", "")
```

**原因：**
- `Date:` 头由发件方填写，可能伪造、缺失或时区混乱。
- `INTERNALDATE` 是邮件服务器收到邮件时打上的时间戳，不可伪造，是游标记录的可靠依据。

#### 2.5 新增：降级方案

当阶段 1 批量请求失败时，自动降级为逐封全量下载（`_fetch_full_fallback`），保证功能不中断。

---

### 3. `backend/app/services/email_service.py`

**变更内容：** 全面重构，引入游标管理，移除 while 循环和 mark_as_seen

#### 3.1 新增：游标初始化策略（`_get_since_date`）

项目重启时，对已有存量数据但尚无 `last_sync_date` 的邮箱，自动从数据库中最新一条发票的 `created_at` 初始化游标，避免对已处理邮件进行重复扫描。

```
last_sync_date 有值       → 后续同步，直接使用
last_sync_date 无值 + 有存量发票 → 用最新发票 created_at 初始化，走后续同步
last_sync_date 无值 + 无存量发票 → 首次同步（UNSEEN 近 30 天最新 50 封）
```

**原因：**
- 原代码每次启动都对所有邮箱走"全量未读"逻辑，存量用户会反复拉取已处理过的邮件（虽然 email_uid 去重能防止重复写入，但带来不必要的性能开销）。

#### 3.2 新增：游标更新策略（`_update_last_sync_date`）

- 无论本批邮件有没有提取到发票，只要有邮件被检查过，就将游标推进到本批最新一封邮件的 INTERNALDATE。
- 游标只前进不后退（单调递增保证）。

**原因：**
- 原方案没有游标，靠已读状态过滤，19 封无发票邮件中间夹 1 封有发票，下次同步仍会重新检查那 19 封。
- 新方案检查过的邮件（无论有没有发票）都不会在下次同步中再次被检查，彻底消除重复扫描。

#### 3.3 移除：while 循环分页 + mark_as_seen

**原代码：**
- `while True` 循环分批拉取，单次上限 500 封
- 每封邮件处理完后 `client.mark_as_seen(email_msg.uid)`

**新代码：**
- 移除 while 循环，每次同步处理最多 50 封，游标自动推进，下次接续
- 移除所有 `mark_as_seen` 调用

**原因：**
- 后续同步不再依赖已读/未读状态，主动标记已读会修改用户邮箱状态（一种副作用）。
- 单次 500 封上限配合 while 循环可能导致单次同步耗时过长；改为每次固定 50 封、游标推进更可控。

#### 3.4 代码结构重构

将原来 300+ 行的 `process_user_emails` 拆分为：
- `process_user_emails` — 入口，遍历邮箱
- `_process_single_mailbox` — 处理单个邮箱（连接、fetch、游标更新）
- `_process_single_pdf` — 处理单个 PDF（去重、解析、存储）
- `_get_since_date` — 游标初始化
- `_update_last_sync_date` — 游标推进

---

### 4. `backend/app/api/user.py`

**变更内容：** `POST /api/user/email-configs` 绑定邮箱后触发首次同步

```python
async def add_email_config(
    config: EmailConfig,
    background_tasks: BackgroundTasks,   # 新增
    ...
):
    # ... 原有验证和保存逻辑 ...

    # 绑定成功后立即在后台触发首次同步
    background_tasks.add_task(_run_initial_sync)
```

**原因：**
- 原代码绑定邮箱后返回成功，但不触发任何同步，用户最多需要等 5 分钟（定时器下次触发）才能看到发票。
- 新方案使用 FastAPI `BackgroundTasks`，接口立即响应，首次同步在后台异步执行，不阻塞用户操作。

---

## 同步流程对比

### 原流程
```
触发同步
  → SEARCH UNSEEN SINCE {30天前}（序列号）
  → uid_list[:50]（最旧 50 封）
  → 逐封 FETCH RFC822（全量下载，含所有附件）
  → 检测发票 → 去重 → 存库
  → mark_as_seen（标记已读）
  → 若 < 50 封则结束，否则继续循环（上限 500 封）
  → 无游标，依赖已读状态
```

### 新流程
```
触发同步
  → 确定 since_date（游标初始化策略）
  ├─ 首次同步（since_date=None）：
  │     UID SEARCH UNSEEN SINCE {30天前}
  │     uid_list[-50:]（最新 50 封）
  └─ 后续同步（since_date 有值）：
        UID SEARCH SINCE {since_date - 1天}
        uid_list[:50]（最旧 50 封）

  → 阶段1: 批量 UID FETCH (INTERNALDATE BODYSTRUCTURE HEADERS)
  → 过滤：无 PDF 且无关键词 → 跳过
  → 阶段2: 仅对候选邮件 UID FETCH BODY.PEEK[]
  → 检测发票 → 去重 → 存库
  → 推进游标到本批最新 INTERNALDATE（无论有无发票）
  → 无 mark_as_seen
```

---

## 注意事项

### 存量数据过渡
已有数据的用户在首次更新后，`last_sync_date` 会自动从其最新一条发票的 `created_at` 初始化，无需手动迁移。

### email_uid 兼容性
原代码存储的是 IMAP 序列号（非真实 UID），新代码存储真实 IMAP UID。过渡期间，部分老记录的 `email_uid` 与新方案的 UID 不同，可能造成极少量邮件被重复检查（但不会重复写入，PDF 哈希和发票号去重会拦截）。

### IMAP SINCE 日期粒度
IMAP `SINCE` 命令精确到天，新方案在查询时对游标退 1 天（`since_date - 1 day`），确保不遗漏日期边界附近的邮件，靠 `email_uid` 去重跳过已处理的。
