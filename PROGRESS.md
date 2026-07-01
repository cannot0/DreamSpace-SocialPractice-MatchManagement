# 项目进度总结

> 更新时间：2026-06-30
> 仓库地址：https://github.com/cannot0/DreamSpace-SocialPractice-MatchManagement

---

## 一、项目概述

**大学生返家乡实践活动推荐系统** — 基于 AI 的个性化活动匹配网站。

用户填写专业、技能、时间、地区等信息，系统调用千问大模型从 SQL Server 数据库中筛选并推荐最匹配的返家乡实践活动。

---

## 二、技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 单页 HTML + 原生 CSS/JS（无框架） |
| 后端 | Python Flask |
| 数据库 | SQL Server（pyodbc） |
| AI 推理 | 千问 qwen3.6-flash（阿里云 DashScope） |
| 部署目标 | Railway |

---

## 三、项目结构

```
recommender/
├── app.py                  # Flask 后端入口，3个路由：首页、健康检查、推荐API
├── config.py               # 配置读取（环境变量）
├── recommend.py            # 推荐主逻辑（调用LLM + 解析响应 + dry_run降级）
├── prompt_template.py      # 千问 Prompt 模板
├── input.py                # 数据导入脚本（Excel → SQL Server，独立工具）
├── requirements.txt        # Python 依赖
├── Procfile                # Railway 启动命令（gunicorn）
├── runtime.txt             # Python 3.11.9
├── .env                    # 本地环境变量（已 gitignore，不上传）
├── .env.example            # 环境变量模板
├── .gitignore
├── db/
│   ├── __init__.py
│   └── query.py            # 数据库查询（pyodbc，查 v_activity_full 视图）
└── templates/
    └── index.html          # 前端页面（表单 + 结果展示，完整CSS/JS内联）
```

---

## 四、已完成的工作

### 4.1 前端（index.html）
- ✅ 学生画像表单：专业、年级、技能标签、时间、省份城市、偏好
- ✅ 技能标签输入组件（回车添加、点击删除、Backspace 回删）
- ✅ 表单验证（必填字段检查）
- ✅ API 调用层（fetch POST `/api/recommend`）
- ✅ 结果渲染：推荐卡片 + 匹配度进度条 + Top3 特殊样式
- ✅ Loading / Empty / Error 三种状态切换
- ✅ 响应式布局（适配手机）
- ✅ XSS 防护

### 4.2 后端（app.py）
- ✅ `GET /` — 渲染首页
- ✅ `GET /health` — 健康检查
- ✅ `POST /api/recommend` — 推荐接口（校验必填字段 → 调用推荐逻辑 → 返回JSON）

### 4.3 推荐逻辑（recommend.py）
- ✅ 调用千问 API（OpenAI 兼容接口，直接 HTTP 请求）
- ✅ 自动重试机制（MAX_RETRY=2）
- ✅ LLM 响应解析（兼容 Markdown 代码块包裹）
- ✅ dry_run 降级模式（无 API Key 时用本地规则生成推荐）
- ✅ dry_run 评分维度：专业40% + 时间30% + 技能20% + 偏好10%

### 4.4 数据库（db/query.py）
- ✅ pyodbc 连接 SQL Server
- ✅ 支持两种认证：Windows 认证（本地开发）/ 账号密码（部署）
- ✅ 查询 `v_activity_full` 视图（聚合活动主表+详情+标签）
- ✅ 支持省份、专业标签筛选

### 4.5 数据导入（input.py）
- ✅ 读取 Excel 文件（53000+ 条活动数据）
- ✅ 数据清洗：解析地址、推断类别、提取专业/技能标签、解析联系人
- ✅ 写入三张表：`activities`、`activity_details`、`activity_tags`

### 4.6 部署准备
- ✅ Git 仓库已初始化，代码已推送到 GitHub
- ✅ Procfile（gunicorn 启动命令）
- ✅ runtime.txt（Python 3.11.9）
- ✅ .env.example（环境变量模板）
- ✅ .gitignore（排除 .env、.venv、__pycache__ 等）

---

## 五、待完成的工作

### 5.1 部署到 Railway（阻塞中）
- ⏳ 等待队友提供 SQL Server 账号密码
- ⏳ Railway 创建项目并关联 GitHub 仓库
- ⏳ 设置环境变量（QWEN_API_KEY、DB_SERVER、DB_DATABASE、DB_USER、DB_PASSWORD）
- ⏳ Railway 部署 ODBC Driver 17（Linux 容器需要额外配置）

**Railway 环境变量配置：**

| 变量名 | 值 | 状态 |
|--------|-----|------|
| QWEN_API_KEY | sk-09ebd7c21204400aa7ca196175bf4fa0 | ✅ 已知 |
| DB_SERVER | 待定 | ⏳ 等队友 |
| DB_DATABASE | hometown_practice | ✅ 已知 |
| DB_USER | 待定 | ⏳ 等队友 |
| DB_PASSWORD | 待定 | ⏳ 等队友 |

### 5.2 可能需要处理的部署问题
- Railway Linux 容器需要安装 ODBC Driver 17 for SQL Server（可能需要 `nixpacks.toml` 或 Dockerfile）
- SQL Server 需要开放公网访问（或使用 Railway 内网连接）
- 数据库服务器防火墙需放行 Railway 的 IP

### 5.3 功能增强（可选）
- 🔲 添加加载动画优化
- 🔲 推荐结果缓存（避免重复调用 LLM）
- 🔲 用户反馈机制（推荐是否满意）
- 🔲 活动详情页面（点击卡片查看详情）
- 🔲 管理后台（活动数据管理）

---

## 六、本地运行方式

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（复制 .env.example 为 .env，填入真实值）
cp .env.example .env

# 3. 启动
python app.py
# 访问 http://localhost:5000
```

---

## 七、关键代码说明

### API 接口格式

**请求：** `POST /api/recommend`
```json
{
  "major": "计算机科学与技术",
  "grade": "大三",
  "skills": "Python，数据分析",
  "available_start": "2025-07-01",
  "available_end": "2025-08-31",
  "province": "广东",
  "city": "广州",
  "preference": "企业实习"
}
```

**响应：**
```json
{
  "recommendations": [
    {
      "rank": 1,
      "activity_id": "A002",
      "title": "深圳互联网企业暑期实习体验营",
      "match_score": 92,
      "match_reason": "专业和Python技能匹配，时间完全重叠",
      "highlight": "企业实习场景，适合积累证明材料"
    }
  ]
}
```

### 数据库表结构（队友设计）

- `activities` — 活动主表（project_id, title, province, city, category 等）
- `activity_details` — 活动详情（描述、要求、福利、联系人等）
- `activity_tags` — 标签表（project_id, tag_type, tag_value）
- `v_activity_full` — 聚合视图（JOIN 三张表，供查询使用）

---

## 八、Git 提交记录

```
99e2671 feat: 添加Railway部署配置
3c99437 feat: 接入SQL Server数据库查询
bb204af feat: 初始化返家乡活动推荐系统
```

---

## 九、团队分工

| 成员 | 负责内容 |
|------|----------|
| 你（tyl） | 网站设计、前端页面、推荐逻辑、部署 |
| 队友 | 数据库设计、SQL Server 建表、数据导入、账号密码配置 |

---

## 十、已知的 GitHub Token（需撤销）

之前使用了 Personal Access Token 进行推送，token 已暴露在对话中，**请立即去 GitHub 撤销并重新生成**：
- Settings → Developer settings → Personal access tokens → 删除旧的 → 生成新的
