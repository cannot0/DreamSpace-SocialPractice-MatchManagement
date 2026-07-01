# 登录功能开发总结

> 完成时间：2026-06-30

---

## 一、功能概述

为返家乡实践活动推荐系统添加了完整的用户认证体系，包括用户端和管理端。

---

## 二、已完成的工作

### 2.1 设计文档

| 文件 | 说明 |
|------|------|
| `docs/specs/2026-06-30-login-auth-design.md` | 完整设计文档（数据库、API、前端、安全） |
| `docs/specs/2026-06-30-db-handoff.md` | 数据库建表对接文档（发给队友执行） |

### 2.2 新增文件（8个）

| 文件 | 说明 |
|------|------|
| `auth.py` | 认证逻辑模块：登录验证、注册校验、路由装饰器、防暴力破解（5次/5分钟锁定） |
| `db/user.py` | 用户数据操作模块：用户 CRUD、画像管理、推荐历史 |
| `templates/login.html` | 登录页面：用户名/密码登录，链接到注册页 |
| `templates/register.html` | 注册页面：用户名/密码/昵称注册 |
| `templates/profile.html` | 用户画像页面：查看/编辑保存的画像，支持自动填充到推荐 |
| `templates/history.html` | 推荐历史页面：查看历史推荐记录列表 |
| `templates/admin.html` | 管理后台：Excel 上传导入 + 注册用户列表 |
| `static/common.css` | 公共样式：统一配色、导航栏、卡片、表单等 |

### 2.3 修改文件（4个）

| 文件 | 修改内容 |
|------|---------|
| `config.py` | 新增 `SECRET_KEY`、`ADMIN_USERNAME`、`ADMIN_PASSWORD` 配置 |
| `app.py` | 新增 11 个路由（登录、注册、退出、画像、历史、管理后台等）；路由保护装饰器；推荐历史自动保存 |
| `templates/index.html` | 添加导航栏，显示用户名和退出按钮 |
| `.env.example` | 新增管理员和密钥配置模板 |

### 2.4 Git 提交记录（12个 commit）

```
11ab4b1 feat: 为首页添加导航栏和登录状态显示
d15514f feat: 添加管理后台页面（Excel上传 + 用户列表）
02b232e feat: 添加推荐历史页面
efd6f97 feat: 添加用户画像页面
c740702 feat: 集成认证路由（登录、注册、退出、画像、历史、管理后台）
0dc351d feat: 添加注册页面
9a8c979 feat: 添加登录页面
26724ac feat: 添加认证逻辑模块（登录验证、注册校验、路由装饰器）
05ecf8a feat: 添加用户数据操作模块（注册、登录、画像、历史）
3404b30 feat: 添加认证相关配置（SECRET_KEY、管理员账号）
0c79f22 docs: 添加数据库建表对接文档
600139b docs: 添加用户和管理员登录功能设计文档
```

---

## 三、功能清单

### 用户端

| 功能 | 路由 | 状态 |
|------|------|------|
| 用户注册 | `POST /register` | ✅ 完成 |
| 用户登录 | `POST /login` | ✅ 完成 |
| 退出登录 | `GET /logout` | ✅ 完成 |
| 查看/保存画像 | `GET/POST /profile` | ✅ 完成 |
| 查看推荐历史 | `GET /history` | ✅ 完成 |
| 获取推荐（需登录） | `POST /api/recommend` | ✅ 完成 |
| 推荐历史自动保存 | `POST /api/recommend` | ✅ 完成 |

### 管理端

| 功能 | 路由 | 状态 |
|------|------|------|
| 管理员登录 | `POST /login` | ✅ 完成 |
| 管理后台页面 | `GET /admin` | ✅ 完成 |
| 查看注册用户列表 | `GET /admin/users` | ✅ 完成 |
| Excel 上传导入 | `POST /admin/upload` | ⏳ 框架完成，需对接 input.py |

### 安全措施

| 措施 | 状态 |
|------|------|
| 密码哈希（werkzeug PBKDF2） | ✅ 完成 |
| CSRF Token 防护 | ✅ 完成 |
| 登录频率限制（5次/5分钟） | ✅ 完成 |
| 路由保护装饰器 | ✅ 完成 |
| 统一错误提示（不泄露用户名是否存在） | ✅ 完成 |

---

## 四、数据库需求

需要在 SQL Server 中新建 3 张表（详见 `docs/specs/2026-06-30-db-handoff.md`）：

| 表名 | 用途 |
|------|------|
| `users` | 用户账号（用户名、密码哈希、昵称） |
| `user_profiles` | 用户画像（专业、年级、技能、地区等） |
| `recommendation_history` | 推荐历史（画像快照 + 推荐结果 JSON） |

---

## 五、待完成事项

| 事项 | 优先级 | 说明 |
|------|--------|------|
| 数据库建表 | 🔴 高 | 队友执行 `db-handoff.md` 中的 SQL |
| 配置环境变量 | 🔴 高 | 在 `.env` 中设置 `SECRET_KEY`、`ADMIN_USERNAME`、`ADMIN_PASSWORD` |
| Excel 上传对接 | 🟡 中 | `/admin/upload` 路由的 `TODO` 处对接 `input.py` 数据清洗逻辑 |
| 远程数据库测试 | 🟡 中 | 配置队友的 SQL Server 地址进行联调 |
| Railway 部署 | 🟢 低 | 等数据库就绪后部署到 Railway |

---

## 六、项目结构（更新后）

```
recommender/
├── app.py                  # Flask 入口（已更新：新增认证路由）
├── auth.py                 # 新增：认证逻辑
├── config.py               # 已更新：新增认证配置
├── recommend.py            # 推荐逻辑（不变）
├── prompt_template.py      # Prompt 模板（不变）
├── input.py                # 数据导入脚本（不变）
├── requirements.txt        # 依赖（不变）
├── db/
│   ├── __init__.py
│   ├── query.py            # 活动查询（不变）
│   └── user.py             # 新增：用户数据操作
├── templates/
│   ├── index.html          # 已更新：添加导航栏
│   ├── login.html          # 新增：登录页
│   ├── register.html       # 新增：注册页
│   ├── profile.html        # 新增：画像页
│   ├── history.html        # 新增：历史页
│   └── admin.html          # 新增：管理后台
├── static/
│   └── common.css          # 新增：公共样式
└── docs/specs/
    ├── 2026-06-30-login-auth-design.md    # 设计文档
    ├── 2026-06-30-db-handoff.md           # 数据库对接文档
    └── 2026-06-30-login-feature-summary.md # 本文档
```
