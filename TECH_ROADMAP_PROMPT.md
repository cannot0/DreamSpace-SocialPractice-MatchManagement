# 技术路线图生成 Prompt

> 将以下 Prompt 交给大语言模型，即可生成一份完整的技术路线图文档。

---

## Prompt

```
请为以下项目生成一份详细的技术路线图文档（Markdown 格式）。

## 项目信息

**项目名称**：大学生返家乡实践活动推荐系统（DreamSpace Social Practice Match Management）

**项目简介**：基于 AI 的个性化活动匹配网站。大学生填写专业、技能、可用时间、地区等信息，系统调用千问大模型（Qwen）从 PostgreSQL 数据库中筛选并推荐最匹配的返家乡实践活动。

**仓库地址**：https://github.com/cannot0/DreamSpace-SocialPractice-MatchManagement

**线上地址**：https://dreamspace-socialpractice-matchmanagement-production.up.railway.app

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 单页 HTML + 原生 CSS/JS（无框架），Jinja2 模板引擎 |
| 后端 | Python 3 + Flask + Gunicorn |
| 数据库 | PostgreSQL（Railway 托管） |
| AI 推理 | 阿里云千问 qwen-turbo（DashScope OpenAI 兼容接口） |
| 部署 | Railway（PaaS），Procfile 启动 |
| 数据导入 | pandas + openpyxl 解析 Excel |

---

## 项目结构

```
recommender/
├── app.py                  # Flask 入口（认证路由 + 推荐路由 + 管理路由）
├── auth.py                 # 认证逻辑（登录验证、注册校验、路由装饰器、防暴力破解）
├── config.py               # 配置（DATABASE_URL、QWEN_API_KEY、SECRET_KEY 等）
├── recommend.py            # 推荐主逻辑（调用LLM + 解析响应 + dry_run降级）
├── prompt_template.py      # 千问 Prompt 模板（Jinja2）
├── input.py                # Excel 数据导入模块（数据清洗 + 入库）
├── requirements.txt        # Python 依赖
├── Procfile                # Railway 启动命令（gunicorn）
├── db/
│   ├── schema.sql          # PostgreSQL 建表脚本（7张表 + 1个视图）
│   ├── init_data.py        # 数据库初始化脚本
│   ├── query.py            # 活动数据查询（psycopg2）
│   └── user.py             # 用户数据操作（注册、登录、画像、历史）
├── templates/
│   ├── index.html          # 首页（推荐表单 + 结果展示）
│   ├── login.html          # 登录页
│   ├── register.html       # 注册页
│   ├── history.html        # 推荐历史页
│   └── admin.html          # 管理后台（Excel 上传 + 用户列表）
└── static/
    └── common.css          # 公共样式
```

---

## 核心模块详解

### 1. 认证系统（auth.py）
- 用户名/密码注册与登录
- werkzeug PBKDF2 密码哈希
- Flask Session 管理
- 路由保护装饰器：`@login_required`、`@admin_required`
- 登录频率限制（5次/5分钟锁定，内存计数）
- 管理员独立认证（环境变量配置）
- CSRF token 生成（当前因 Railway 兼容问题暂时跳过验证）

### 2. 推荐引擎（recommend.py + prompt_template.py）
- **数据查询层**：从 PostgreSQL 的 `v_activity_full` 视图查询候选活动，支持按省份、专业标签筛选，三级回退策略（省份+专业 → 仅省份 → 全量）
- **Prompt 工程**：Jinja2 模板渲染用户画像 + 候选活动 JSON，包含明确的评分维度权重（专业40%、时间30%、技能20%、偏好10%）和输出格式约束
- **LLM 调用**：通过 HTTP POST 调用千问 API（DashScope OpenAI 兼容接口），temperature=0，max_tokens=1500
- **容错机制**：最多重试 2 次；无 API Key 时自动降级为 dry_run 本地规则推荐
- **响应解析**：正则清理 Markdown 代码块包裹，JSON 解析

### 3. 数据导入（input.py）
- 读取 Excel 文件（pandas + openpyxl）
- 数据清洗：日期格式转换（2026.01.01 → YYYY-MM-DD）、地址解析（省/市/县）、活动类别智能推断（正则匹配标题+内容）、福利代码转中文、专业/技能标签深度提取
- 批量入库：activities + activity_details + activity_tags 三表联动，ON CONFLICT 去重
- 支持命令行和 Flask 两种调用方式

### 4. 数据库设计（schema.sql）
- **activities**：活动主表（project_id 主键，含省份/城市/类别/时间/名额等）
- **activity_details**：活动详情表（描述、要求、联系方式等）
- **activity_tags**：活动标签表（tag_type: major/skill，多值标签）
- **users**：用户表
- **user_profiles**：用户画像表
- **recommendation_history**：推荐历史表（存储画像快照 + 结果 JSON）
- **query_logs**：查询日志表
- **v_activity_full**：聚合视图（STRING_AGG 合并标签）

### 5. 前端（templates/ + static/）
- Jinja2 模板渲染，无前端框架
- 学生画像表单：专业、年级、技能标签、时间范围、省份城市、偏好
- 推荐结果卡片展示：匹配度进度条、Top3 特殊样式
- Loading / Empty / Error 状态切换
- 响应式布局

### 6. 管理后台
- Excel 文件上传导入（/admin/upload）
- 用户列表展示
- 数据库诊断接口（/debug/db）

---

## 系统架构流程

```
用户填写画像表单
       ↓
  POST /api/recommend
       ↓
  ┌─ 查询 PostgreSQL（v_activity_full 视图）
  │    按省份 + 专业筛选候选活动（≤20条）
  │    三级回退：省+专 → 仅省 → 全量
  └──────────────────────┐
                         ↓
  ┌─ Prompt 渲染（Jinja2）
  │    用户画像 + 候选活动 JSON + 评分规则
  └──────────────────────┐
                         ↓
  ┌─ 调用千问 API（qwen-turbo）
  │    system_prompt + user_prompt
  │    temperature=0, max_tokens=1500
  │    最多重试 2 次
  │    无 Key 时降级为本地规则（dry_run）
  └──────────────────────┐
                         ↓
  ┌─ 解析 LLM 响应
  │    清理 Markdown 包裹 → JSON 解析
  │    校验 recommendations 数组
  └──────────────────────┐
                         ↓
  保存推荐历史 → 返回 JSON 给前端 → 渲染结果卡片
```

---

## 环境变量

| 变量名 | 说明 | 必填 |
|--------|------|------|
| DATABASE_URL | PostgreSQL 连接串 | ✅ |
| QWEN_API_KEY | 千问 API 密钥（DashScope） | 否（无则降级为 dry_run） |
| SECRET_KEY | Flask session 密钥 | 否（有默认值） |
| ADMIN_USERNAME | 管理员用户名 | 否（默认 admin） |
| ADMIN_PASSWORD | 管理员密码 | 否（未配置则禁止管理员登录） |
| MODEL_NAME | 千问模型名称 | 否（默认 qwen-turbo） |

---

## 已完成的功能

- ✅ 用户注册/登录/退出
- ✅ 管理员登录（共用 /login 页面）
- ✅ 路由保护装饰器
- ✅ 密码哈希（PBKDF2）
- ✅ 登录频率限制（防暴力破解）
- ✅ 学生画像表单（专业、年级、技能、时间、地区、偏好）
- ✅ 技能标签输入组件
- ✅ 表单验证
- ✅ 调用千问 API 生成推荐
- ✅ 自动重试机制
- ✅ dry_run 降级模式
- ✅ 推荐结果渲染（卡片 + 匹配度进度条 + Top3 特殊样式）
- ✅ 推荐历史自动保存与展示
- ✅ PostgreSQL 数据库（7张表 + 1个视图）
- ✅ Excel 数据导入（数据清洗 + 批量入库）
- ✅ 管理后台（Excel 上传 + 用户列表）
- ✅ Railway 部署成功
- ✅ 健康检查接口（/health）
- ✅ 数据库诊断接口（/debug/db）

---

## 待完成 / 可优化方向

- ⏳ 上传 Excel 导入活动数据（线上环境）
- ⏳ 测试完整推荐流程
- 🔧 CSRF 验证恢复（解决 Railway session 兼容问题）
- 🔧 登录频率限制改为 Redis 存储（当前内存存储，重启丢失）
- 🔧 前端框架化（Vue/React）提升交互体验
- 🔧 推荐算法优化（向量化检索、协同过滤）
- 🔧 用户画像持久化（自动填充上次画像）
- 🔧 活动收藏/对比功能
- 🔧 推荐结果缓存（相同画像不重复调用 LLM）
- 🔧 监控与告警（API 调用成功率、响应时间）
- 🔧 单元测试与集成测试

---

## 请输出的技术路线图应包含以下章节

1. **项目概述**：一句话描述项目目标和核心价值
2. **技术架构**：系统整体架构，各层之间的关系
3. **技术栈清单**：列出所有使用的技术及其用途
4. **核心模块说明**：每个模块的职责、关键实现方式、对外接口
5. **数据流**：从用户请求到推荐结果的完整处理流程
6. **数据库设计**：表结构及表之间的关系
7. **API 接口清单**：所有路由及其功能
8. **部署方案**：部署平台、启动方式、环境变量配置
9. **开发时间线**：按阶段划分的开发里程碑
10. **技术亮点与难点**：项目中的关键技术决策和解决方案
11. **未来演进方向**：可扩展的功能和技术优化路线

请用 Markdown 格式输出。图表、表格等形式根据内容自行选择，以清晰表达为准。
```
