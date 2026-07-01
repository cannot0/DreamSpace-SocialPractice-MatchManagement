# 项目进度总结

> 更新时间：2026-07-01
> 仓库地址：https://github.com/cannot0/DreamSpace-SocialPractice-MatchManagement
> 网站地址：https://dreamspace-socialpractice-matchmanagement-production.up.railway.app

---

## 一、项目概述

**大学生返家乡实践活动推荐系统** — 基于 AI 的个性化活动匹配网站。

用户填写专业、技能、时间、地区等信息，系统调用千问大模型从 PostgreSQL 数据库中筛选并推荐最匹配的返家乡实践活动。

---

## 二、技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 单页 HTML + 原生 CSS/JS（无框架） |
| 后端 | Python Flask + Gunicorn |
| 数据库 | Railway PostgreSQL |
| AI 推理 | 千问 qwen3.6-flash（阿里云 DashScope） |
| 部署 | Railway（已部署成功） |

---

## 三、项目结构

```
recommender/
├── app.py                  # Flask 入口（认证路由 + 推荐路由 + 管理路由）
├── auth.py                 # 认证逻辑（登录验证、注册校验、路由装饰器、防暴力破解）
├── config.py               # 配置（DATABASE_URL、QWEN_API_KEY、SECRET_KEY 等）
├── recommend.py            # 推荐主逻辑（调用LLM + 解析响应 + dry_run降级）
├── prompt_template.py      # 千问 Prompt 模板
├── input.py                # Excel 数据导入模块（支持命令行和 Flask 调用）
├── requirements.txt        # Python 依赖
├── Procfile                # Railway 启动命令（gunicorn）
├── .env                    # 本地环境变量（已 gitignore）
├── .env.example            # 环境变量模板
├── .gitignore
├── db/
│   ├── __init__.py
│   ├── schema.sql          # PostgreSQL 建表脚本（6张表 + v_activity_full 视图）
│   ├── init_data.py        # 数据库初始化脚本（建表 + 导入 Excel）
│   ├── query.py            # 活动数据查询（psycopg2）
│   └── user.py             # 用户数据操作（注册、登录、画像、历史）
├── templates/
│   ├── index.html          # 首页（推荐表单 + 结果展示）
│   ├── login.html          # 登录页
│   ├── register.html       # 注册页
│   ├── profile.html        # 用户画像页
│   ├── history.html        # 推荐历史页
│   └── admin.html          # 管理后台（Excel 上传 + 用户列表）
├── static/
│   └── common.css          # 公共样式
└── docs/specs/             # 设计文档
```

---

## 四、已完成的工作

### 4.1 前端
- ✅ 学生画像表单：专业、年级、技能标签、时间、省份城市、偏好
- ✅ 技能标签输入组件
- ✅ 表单验证
- ✅ 推荐结果渲染（卡片 + 匹配度进度条 + Top3 特殊样式）
- ✅ Loading / Empty / Error 状态切换
- ✅ 响应式布局

### 4.2 认证系统
- ✅ 用户注册、登录、退出
- ✅ 管理员登录（共用 /login 页面）
- ✅ 路由保护装饰器（login_required、admin_required）
- ✅ 密码哈希（werkzeug PBKDF2）
- ✅ 登录频率限制（5次/5分钟锁定）
- ✅ CSRF 已临时禁用（Railway session 兼容问题）

### 4.3 推荐逻辑
- ✅ 调用千问 API（OpenAI 兼容接口）
- ✅ 自动重试机制
- ✅ dry_run 降级模式（无 API Key 时本地规则推荐）
- ✅ 推荐历史自动保存

### 4.4 数据库（PostgreSQL）
- ✅ schema.sql：完整建表脚本（activities、activity_details、activity_tags、users、user_profiles、recommendation_history、query_logs）
- ✅ v_activity_full 视图（STRING_AGG 聚合标签）
- ✅ db/query.py：活动查询
- ✅ db/user.py：用户数据操作

### 4.5 管理后台
- ✅ Excel 上传导入（/admin/upload）
- ✅ 用户列表展示
- ✅ input.py 数据清洗逻辑已对接

### 4.6 部署
- ✅ Railway 部署成功
- ✅ PostgreSQL 插件已添加
- ✅ 网站可访问：https://dreamspace-socialpractice-matchmanagement-production.up.railway.app
- ✅ 管理员登录正常（/admin）

---

## 五、当前状态

### ✅ 已完成
- 网站部署成功，可正常访问
- 管理员登录正常
- 数据库已创建（PostgreSQL）

### ⏳ 待完成
- **上传 Excel 导入活动数据** — 在 /admin 页面上传 `db/活动详情_3000.xlsx`
- **测试推荐功能** — 数据导入后，注册普通用户测试推荐流程

---

## 六、Railway 环境变量

| 变量名 | 说明 | 状态 |
|--------|------|------|
| DATABASE_URL | PostgreSQL 连接串 | ✅ Railway 自动注入 |
| QWEN_API_KEY | 千问 API 密钥 | ✅ 已配置 |
| SECRET_KEY | Flask session 密钥 | ✅ 已配置 |
| ADMIN_USERNAME | 管理员用户名 | ✅ 已配置 |
| ADMIN_PASSWORD | 管理员密码 | ✅ 已配置 |

---

## 七、本地运行方式

```bash
pip install -r requirements.txt
cp .env.example .env   # 编辑 .env 填入 DATABASE_URL 和 QWEN_API_KEY
python app.py
# 访问 http://localhost:5000
```

初始化数据库：
```bash
python -m db.init_data "db/活动详情_3000.xlsx"
```

---

## 八、团队分工

| 成员 | 负责内容 |
|------|----------|
| 你（tyl） | 网站设计、前端页面、推荐逻辑、部署 |
| 队友 | 数据库设计、SQL Server 建表、数据导入脚本（input.py 原始版本） |

---

## 九、已知问题

- CSRF 验证已临时禁用（Railway HTTPS 代理导致 session 不稳定）
- GitHub token 之前暴露在对话中，**请去 GitHub 撤销旧 token 并重新生成**
