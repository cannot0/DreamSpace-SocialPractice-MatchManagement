# 用户和管理员登录功能设计文档

> 日期：2026-06-30
> 状态：待审核

---

## 一、概述

为返家乡实践活动推荐系统添加完整的用户认证体系，包括：

- **用户端**：注册、登录、保存画像、查看推荐历史
- **管理端**：管理员登录、Excel 上传导入活动数据、查看用户列表

### 设计目标

- 用户自助注册，使用用户名/密码登录
- 单管理员通过环境变量配置，不存入数据库
- 用户画像和推荐历史保存到 SQL Server
- 管理员通过网页上传 Excel 导入活动数据（复用 input.py 逻辑）
- 使用 Flask Session 管理会话

---

## 二、数据库设计

在现有 `hometown_practice` 数据库中新建 3 张表。

### 2.1 `users` 用户表

```sql
CREATE TABLE users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    username NVARCHAR(50) NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    nickname NVARCHAR(50),
    created_at DATETIME DEFAULT GETDATE(),
    last_login DATETIME
);
```

### 2.2 `user_profiles` 用户画像表

```sql
CREATE TABLE user_profiles (
    id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id),
    major NVARCHAR(100),
    grade NVARCHAR(20),
    skills NVARCHAR(500),
    province NVARCHAR(50),
    city NVARCHAR(50),
    preference NVARCHAR(500),
    available_start DATE,
    available_end DATE,
    updated_at DATETIME DEFAULT GETDATE()
);
```

### 2.3 `recommendation_history` 推荐历史表

```sql
CREATE TABLE recommendation_history (
    id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id),
    profile_snapshot NVARCHAR(MAX),
    result_json NVARCHAR(MAX),
    created_at DATETIME DEFAULT GETDATE()
);
```

---

## 三、后端设计

### 3.1 项目结构变更

```
recommender/
├── app.py                  # 修改：新增认证路由、路由保护
├── auth.py                 # 新增：认证逻辑（登录、注册、装饰器）
├── config.py               # 修改：新增 ADMIN_USERNAME/PASSWORD、SECRET_KEY
├── db/
│   ├── query.py            # 不变
│   └── user.py             # 新增：用户表 CRUD 操作
├── templates/
│   ├── login.html          # 新增
│   ├── register.html       # 新增
│   ├── profile.html        # 新增
│   ├── history.html        # 新增
│   ├── admin.html          # 新增
│   └── index.html          # 修改：添加导航栏、登录状态
└── static/
    └── common.css          # 新增：公共样式
```

### 3.2 新增路由

| 路由 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/login` | GET | 登录页面 | 公开 |
| `/login` | POST | 登录接口 | 公开 |
| `/register` | GET | 注册页面 | 公开 |
| `/register` | POST | 注册接口 | 公开 |
| `/logout` | GET | 退出登录 | 已登录 |
| `/profile` | GET | 用户画像页面 | 已登录 |
| `/profile` | POST | 保存画像 | 已登录 |
| `/history` | GET | 推荐历史页面 | 已登录 |
| `/admin` | GET | 管理后台页面 | 管理员 |
| `/admin/upload` | POST | Excel 上传导入 | 管理员 |
| `/admin/users` | GET | 用户列表（JSON） | 管理员 |

### 3.3 修改现有路由

- `GET /` — 未登录时跳转到 `/login`
- `POST /api/recommend` — 登录后才能调用，同时自动保存推荐历史

### 3.4 认证装饰器

```python
from functools import wraps
from flask import session, redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated
```

### 3.5 管理员认证

管理员不存入数据库，通过环境变量配置：

```python
# config.py
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
```

登录流程：
1. 用户提交用户名和密码
2. 先检查是否匹配管理员账号（比对环境变量中的用户名，密码使用 `werkzeug.check_password_hash` 比对）
3. 如果不是管理员，再查数据库中的普通用户
4. 如果都不匹配，返回统一错误提示："用户名或密码错误"（不泄露用户名是否存在）

管理员登录成功后，session 中设置 `is_admin=True`，同时也有 `user_id`（管理员的 user_id 固定为 0）。

### 3.6 登录/注册接口细节

**POST /login 请求：**
```json
{ "username": "string", "password": "string" }
```
成功响应：重定向到 `/`（推荐页）
失败响应：渲染登录页，显示错误信息

**POST /register 请求：**
```json
{ "username": "string", "password": "string", "nickname": "string" }
```
验证规则：
- 用户名：3-50 字符，只允许字母、数字、下划线
- 密码：6-50 字符
- 昵称：1-50 字符
- 用户名唯一性检查（查数据库）

成功响应：自动登录，重定向到 `/`
失败响应：渲染注册页，显示错误信息

### 3.7 用户数据操作（db/user.py）

```python
# 核心函数：
create_user(username, password, nickname)  # 注册
get_user_by_username(username)             # 登录验证
update_last_login(user_id)                 # 更新登录时间
save_user_profile(user_id, profile)        # 保存画像
get_user_profile(user_id)                  # 获取画像
save_recommendation(user_id, profile, result)  # 保存推荐历史
get_recommendation_history(user_id)        # 获取推荐历史
get_all_users()                            # 管理员：获取所有用户
```

### 3.8 Excel 上传导入

管理员上传 Excel 文件后：

1. 保存到临时目录
2. 调用 `input.py` 的数据清洗逻辑
3. 写入 `activities`、`activity_details`、`activity_tags` 三张表
4. 返回导入结果（成功条数、失败条数、错误信息）

---

## 四、前端设计

### 4.1 页面一览

| 页面 | 文件 | 功能 |
|------|------|------|
| 登录页 | `templates/login.html` | 用户名/密码登录，链接到注册页 |
| 注册页 | `templates/register.html` | 用户名/密码/昵称注册 |
| 推荐页 | `templates/index.html` | 登录后使用，Header 显示用户名和退出按钮 |
| 画像页 | `templates/profile.html` | 查看/编辑保存的画像 |
| 历史页 | `templates/history.html` | 查看历史推荐记录 |
| 管理页 | `templates/admin.html` | Excel 上传 + 用户列表 |

### 4.2 样式方案

- 复用现有 CSS 变量体系（`--primary-color`、`--radius` 等）
- 提取公共样式到 `static/common.css`
- 各页面保持统一的视觉风格（蓝色主题、圆角卡片、阴影效果）

### 4.3 导航结构

- **登录/注册页**：无导航栏，简洁表单居中
- **用户页面**：顶部导航栏，左侧 Logo，右侧用户名 + 退出按钮
- **管理页面**：顶部导航栏，显示"管理后台"标识 + 退出按钮

### 4.4 页面流转

```
未登录 ──→ 登录页 ──→ 注册页（可选）
              │
              ↓
         推荐页（首页）← 画像页（自动填充）
              │
              ↓
         历史页（查看记录）

管理员 ──→ 登录页 ──→ 管理后台（Excel 上传 + 用户列表）
```

---

## 五、安全设计

| 措施 | 实现方式 |
|------|---------|
| 密码哈希 | `werkzeug.security.generate_password_hash`（PBKDF2 + 自动加盐） |
| CSRF 防护 | 表单提交添加 CSRF token（Flask-WTF 或手动实现） |
| XSS 防护 | 复用现有的 `_escape()` 函数 |
| SQL 注入 | 参数化查询（已有模式） |
| Session 安全 | `HttpOnly` cookie，生产环境启用 `Secure` |
| 登录限制 | 5 次失败后锁定 5 分钟（内存计数，防暴力破解） |

---

## 六、环境变量变更

在 `.env.example` 中新增：

```bash
# 管理员配置
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-admin-password

# Session 密钥
SECRET_KEY=your-secret-key-change-in-production
```

---

## 七、依赖变更

`requirements.txt` 不需要新增依赖，`werkzeug` 已随 Flask 一起安装。

---

## 八、实现优先级

按以下顺序实现：

1. 数据库建表（3 张新表）
2. 用户数据操作模块（`db/user.py`）
3. 认证逻辑模块（`auth.py`）
4. 配置更新（`config.py`）
5. 登录/注册页面和路由
6. 路由保护（装饰器）
7. 推荐历史保存
8. 用户画像页面
9. 历史记录页面
10. 管理后台页面
11. 公共样式提取
12. 导航栏更新
