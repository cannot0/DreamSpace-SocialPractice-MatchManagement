# 核心技术流程详解

---

## 一、Excel 活动数据导入流程

### 1.1 入口

管理员在 `/admin` 页面上传 Excel 文件，或命令行执行：

```bash
python input.py db/活动详情_3000.xlsx
```

两种方式最终都调用 `input.py` 中的 `import_excel(excel_path)` 函数。

### 1.2 Excel 原始数据结构

Excel 中每行是一条活动记录，包含以下关键列：

| 列名 | 内容 | 示例 |
|------|------|------|
| `project` | Python 字典字符串，包含活动主体信息 | `{"projectId":"A001","projectName":"智慧社区实践",...}` |
| `postSetting` | 岗位设置（嵌套 JSON），包含专业和技能要求 | `{"unitList":[{"childList":[...]}]}` |
| `contactList` | 联系人列表 | `[{"contactName":"张三","contactTel":"138xxx"}]` |
| `attachmentList` | 附件列表 | `[{"filename":"说明.pdf","url":"..."}]` |

其中 `project` 字段内部包含：

```
projectId        → 活动唯一ID
projectName      → 活动标题
enterpriseName   → 组织单位
areaList         → 地址数组，如 ["云南省昆明市五华区"]
startDate        → 活动开始日期（格式 2026.01.01）
endDate          → 活动结束日期
joinStartDate    → 报名开始日期
joinEndDate      → 报名结束日期
enrollNum        → 招募名额
projectContent   → 活动详情描述（HTML/文本）
projectJoinTip   → 参加要求
companyProfile   → 企业/单位简介
welfare          → 福利代码（"1,2,3" → "食宿,保险,交通"）
```

### 1.3 数据清洗过程（`_process_row` 函数）

对每一行数据，依次执行以下清洗步骤：

**第一步：解析嵌套 JSON**

Excel 中的 `project`、`postSetting` 等列存储的是 Python 字典字符串（单引号），不是标准 JSON。`parse_dict_or_json` 函数按顺序尝试三种解析方式：

```
json.loads(val)              → 标准 JSON（双引号）
ast.literal_eval(val)        → Python 字面量（单引号）
json.loads(val.replace("'", '"'))  → 兜底：替换单引号后解析
```

**第二步：地址解析**

`areaList` 是 `["云南省昆明市五华区"]` 这样的数组，`parse_address` 用正则提取三级地址：

```
正则匹配顺序：
1. 省级：匹配 "省" 或 "自治区" 结尾 → 提取 "云南"
2. 市级：从剩余部分匹配 "市" 或 "自治州" 结尾 → 提取 "昆明"
3. 县级：剩余部分 → 提取 "五华"
```

**第三步：日期格式转换**

原始格式 `2026.01.01` 转换为数据库要求的 `YYYY-MM-DD`：

```python
date_str.replace('.', '-')  →  "2026-01-01"
datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
```

**第四步：活动类别推断**

`infer_category` 函数通过正则匹配标题和内容中的关键词，自动归类：

```
匹配 "企业|公司|银行|产业园"     → 企业实习
匹配 "文化|博物馆|融媒体|文旅"   → 文化传播
匹配 "科研|调研|检测|实验室"     → 科研调研
匹配 "志愿|公益|托管|支教"       → 公益志愿
以上都不匹配                    → 政务实践（默认）
```

**第五步：标签提取**

`extract_tags` 函数从两个来源提取标签：

- **专业标签（major）**：从 `projectContent` 正则匹配 `专业要求：xxx` 或 `xx专业优先`，按逗号/顿号分隔
- **技能标签（skill）**：从 `postSetting` 的嵌套结构中递归提取岗位名称：
  ```
  postSetting.unitList → 每个 unit.childList → 每个 dept.childList → 叶子节点的 name
  ```

**第六步：福利代码转换**

```
代码映射：{'1': '食宿', '2': '保险', '3': '交通', '4': '补贴'}
"1,2,3" → "食宿,保险,交通"
```

### 1.4 入库过程

一条活动清洗完成后，分别写入三张表：

```
activities 表 ← 活动主体（标题、地址、类别、时间、名额）
    ↓ project_id
activity_details 表 ← 活动详情（描述、要求、联系方式、附件）
    ↓ project_id
activity_tags 表 ← 标签（多条记录，tag_type = major 或 skill）
```

使用 `ON CONFLICT DO NOTHING` 保证幂等性，重复导入不会产生重复数据。

每 100 条执行一次 `conn.commit()`，平衡性能和安全性。

---

## 二、数据库活动筛选流程

### 2.1 核心视图

所有查询都基于 `v_activity_full` 视图，该视图将三张表合并为一张宽表：

```sql
SELECT
    a.project_id, a.title, a.province, a.city, a.category,
    a.start_date, a.end_date, a.quota,
    d.description, d.requirements, d.contact_person,
    -- 聚合标签为逗号分隔字符串
    STRING_AGG(tag_value, ',') WHERE tag_type = 'major' AS major_tags,
    STRING_AGG(tag_value, ',') WHERE tag_type = 'skill' AS skill_tags
FROM activities a
LEFT JOIN activity_details d ON a.project_id = d.project_id
LEFT JOIN activity_tags t ON ...
WHERE a.is_active = 1
```

### 2.2 查询入口

`recommend.py` 中的 `get_recommendations` 调用 `db/query.py` 的 `get_activities`：

```python
activities = get_activities(
    province=user_profile.get("province"),    # 如 "广东"
    major_tag=user_profile.get("major"),      # 如 "计算机"
    limit=CANDIDATE_LIMIT,                    # 默认 20
)
```

### 2.3 三级回退筛选策略

`get_activities` 函数实现三级回退，确保总能返回候选活动：

```
第一级：province + major_tag 联合筛选
    WHERE province = '广东' AND major_tags LIKE '%,计算机,%'
    ↓ 如果结果为空
第二级：仅按 province 筛选
    WHERE province = '广东'
    ↓ 如果结果仍为空
第三级：不限条件，返回最新活动
    ORDER BY crawled_at DESC LIMIT 20
```

### 2.4 省份名称规范化

用户输入的省份可能是 "广东省"，数据库中存储的是 "广东"，需要去掉后缀：

```python
def _normalize_province(province):
    for suffix in ('省', '自治区', '壮族自治区', '回族自治区', '维吾尔自治区', '特别行政区'):
        if province.endswith(suffix):
            return province[:-len(suffix)]
    return province
```

### 2.5 查询结果处理

数据库返回的原始行需要后处理：

```python
# 标签字符串转列表
"计算机,软件工程" → ["计算机", "软件工程"]

# 日期对象转字符串
datetime.date(2026, 1, 15) → "2026-01-15"
```

最终返回的 `activities` 是一个字典列表，每个元素包含：

```python
{
    "project_id": "A001",
    "activity_id": "hash_A001",
    "title": "智慧社区数据分析实践",
    "org_name": "XX科技有限公司",
    "province": "广东",
    "city": "广州",
    "district": "天河",
    "category": "企业实习",
    "start_date": "2026-07-01",
    "end_date": "2026-08-31",
    "quota": 20,
    "source_url": "https://www.51sdd.com/activity/A001",
    "major_tags": ["计算机", "软件工程"],
    "skill_tags": ["数据分析", "Python"]
}
```

---

## 三、调用千问模型的详细过程

### 3.1 整体流程

**是的，确实是把本地数据库筛选后的数据作为 Prompt 输入给千问模型。** 具体流程：

```
┌─────────────────────────────────────────────────────────────┐
│ 第一步：数据库筛选（本地）                                      │
│   从 PostgreSQL 查询 ≤20 条候选活动                            │
│   按省份 + 专业标签筛选                                        │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 第二步：Prompt 渲染（本地）                                     │
│   将用户画像 + 候选活动 JSON 填入 Jinja2 模板                    │
│   生成完整的 user_prompt 文本                                  │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 第三步：调用千问 API（远程）                                     │
│   将 system_prompt + user_prompt 发送给千问                    │
│   千问根据 Prompt 中的活动数据和规则进行推理                      │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 第四步：解析响应（本地）                                         │
│   提取 JSON，校验格式，返回推荐结果                               │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Prompt 模板结构

`prompt_template.py` 定义了两部分 Prompt：

**System Prompt（系统提示词）**：

```
你是一个寒暑假"返家乡"活动推荐助理。
你的任务是根据学生画像和候选活动列表，筛选并排序最适合学生的活动。
你必须严格输出纯JSON，不允许包含Markdown代码块、解释文字、前后缀或任何非JSON内容。
```

**User Prompt（用户提示词）** —— Jinja2 模板：

```
请根据以下学生画像和候选活动，输出个性化推荐清单。

学生画像：
- 专业：{{ major }}
- 年级：{{ grade }}
- 技能：{{ skills }}
- 可参加开始日期：{{ available_start }}
- 可参加结束日期：{{ available_end }}
- 省份：{{ province }}
- 城市：{{ city }}
- 偏好：{{ preference }}

候选活动JSON：
{{ activities_json }}

推荐规则：
1. 活动时间与学生可参加时间没有重叠的，必须直接排除。
2. 优先推荐省份、城市、专业方向、技能标签和偏好更匹配的活动。
3. 评分维度：
   - 专业匹配：40%
   - 时间可行性：30%
   - 技能适配：20%
   - 偏好：10%
4. match_score必须是0-100之间的整数。
5. match_reason不超过50字。
6. recommendations按match_score从高到低排序，rank从1开始。
```

### 3.3 Prompt 渲染示例

假设用户画像：

```json
{
    "major": "计算机科学与技术",
    "grade": "大二",
    "skills": "Python,数据分析",
    "available_start": "2026-07-01",
    "available_end": "2026-08-31",
    "province": "广东",
    "city": "广州",
    "preference": "企业实习"
}
```

从数据库筛选出 3 条候选活动后，`render_prompt` 函数将数据填入模板，生成的 `user_prompt` 长这样：

```
请根据以下学生画像和候选活动，输出个性化推荐清单。

学生画像：
- 专业：计算机科学与技术
- 年级：大二
- 技能：Python,数据分析
- 可参加开始日期：2026-07-01
- 可参加结束日期：2026-08-31
- 省份：广东
- 城市：广州
- 偏好：企业实习

候选活动JSON：
[
  {
    "project_id": "A001",
    "title": "智慧社区数据分析实践",
    "org_name": "XX科技有限公司",
    "province": "广东",
    "city": "广州",
    "category": "企业实习",
    "start_date": "2026-07-15",
    "end_date": "2026-08-15",
    "major_tags": ["计算机", "软件工程"],
    "skill_tags": ["数据分析", "Python"]
  },
  {
    "project_id": "A002",
    "title": "乡村文化传播志愿服务",
    "org_name": "XX文化局",
    "province": "广东",
    "city": "深圳",
    "category": "公益志愿",
    "start_date": "2026-07-01",
    "end_date": "2026-07-31",
    "major_tags": ["新闻传播"],
    "skill_tags": ["文案写作"]
  },
  ...
]

推荐规则：
1. 活动时间与学生可参加时间没有重叠的，必须直接排除。
...（后续规则同上）
```

### 3.4 API 调用细节

`_call_llm` 函数通过 HTTP 请求调用千问 API：

```python
requests.post(
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    headers={
        "Authorization": "Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "qwen-turbo",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0,       # 确定性输出，同输入同输出
        "max_tokens": 1500,     # 限制输出长度
    },
    timeout=60,                 # 60秒超时
)
```

关键参数说明：

| 参数 | 值 | 作用 |
|------|------|------|
| `model` | `qwen-turbo` | 千问轻量模型，响应快（约 0.6s） |
| `temperature` | `0` | 贪心解码，输出确定性最高 |
| `max_tokens` | `1500` | 限制输出 token 数，防止过长 |
| `timeout` | `60` | HTTP 请求超时时间 |

使用的是 DashScope 的 **OpenAI 兼容接口**，所以请求格式和 OpenAI 完全一致，只是 `base_url` 换成了阿里云的地址。

### 3.5 千问返回的原始响应

千问收到 Prompt 后，会根据其中的候选活动数据和推荐规则进行推理，返回类似：

```json
{
  "choices": [
    {
      "message": {
        "content": "{\"recommendations\":[{\"rank\":1,\"activity_id\":\"A001\",\"title\":\"智慧社区数据分析实践\",\"match_score\":92,\"match_reason\":\"计算机专业和Python技能完全匹配，时间重叠2个月\",\"highlight\":\"企业实习场景，可获得实习证明\"}]}"
      }
    }
  ]
}
```

**核心要点：千问不是从自己的知识库中推荐活动，而是根据 Prompt 中提供的候选活动列表进行筛选和排序。** 活动数据来自本地数据库，千问只负责「理解 + 打分 + 排序」。

### 3.6 响应解析与容错

`_parse_llm_response` 处理千问偶尔返回的 Markdown 包裹：

```
原始响应可能是：
  {"recommendations": [...]}           ← 纯 JSON（理想情况）
  ```json\n{"recommendations": [...]}\n```  ← Markdown 代码块包裹

清理逻辑：
  1. 去掉开头的 ```json 或 ```
  2. 去掉结尾的 ```
  3. json.loads() 解析
```

### 3.7 重试机制

```python
MAX_RETRY = 2  # 最多重试 2 次（总共尝试 3 次）

for attempt in range(1, MAX_RETRY + 2):  # 1, 2, 3
    try:
        raw = _call_llm(system_prompt, user_prompt)
        result = _parse_llm_response(raw)
        # 校验必须包含 recommendations 数组
        if "recommendations" not in result:
            raise ValueError("模型返回缺少recommendations数组")
        return result  # 成功则返回
    except Exception as exc:
        # 失败则重试
```

失败场景包括：网络超时、API 返回错误、JSON 解析失败、返回格式不合规。

### 3.8 无 API Key 时的降级模式

当环境变量 `QWEN_API_KEY` 未配置时，自动进入 `dry_run` 模式，**完全在本地用规则打分，不调用千问**：

```python
if not QWEN_API_KEY:
    return _dry_run_response(user_prompt)
```

`_dry_run_response` 的打分逻辑：

```python
总分 = 专业匹配分(40) + 时间重叠分(30) + 技能匹配分(20) + 偏好分(10) + 城市加分(3)

专业匹配：major 在活动 major_tags 中 → 40分，否则 15分
时间重叠：完全重叠 → 30分，部分重叠按比例
技能匹配：2个以上匹配 → 20分，1个 → 12分，0个 → 5分
偏好匹配：用户偏好含"企业"且活动类别含"企业实习" → +6分
城市加分：城市完全匹配 → +3分
```

这种设计保证了：开发调试时不需要 API Key，也能看到推荐效果。

---

## 四、总结：数据流向全景

```
                    ┌──────────────┐
                    │  Excel 文件   │
                    └──────┬───────┘
                           │ input.py
                           │ 数据清洗 + 入库
                           ↓
                    ┌──────────────┐
                    │  PostgreSQL   │
                    │  7张表 + 1视图 │
                    └──────┬───────┘
                           │ db/query.py
                           │ 按省份+专业筛选（≤20条）
                           ↓
                    ┌──────────────┐
                    │  候选活动列表  │
                    └──────┬───────┘
                           │ prompt_template.py
                           │ Jinja2 渲染
                           ↓
                    ┌──────────────┐
                    │  完整 Prompt  │
                    │ 画像 + 活动JSON │
                    │ + 评分规则     │
                    └──────┬───────┐
                           │ recommend.py
                           │ HTTP POST
                           ↓
                    ┌──────────────┐
                    │  千问 API     │
                    │  qwen-turbo   │
                    │  筛选+打分+排序 │
                    └──────┬───────┘
                           │ JSON 响应
                           ↓
                    ┌──────────────┐
                    │  推荐结果      │
                    │  前端渲染卡片   │
                    └──────────────┘
```

**一句话总结：本地数据库负责「存数据、筛候选」，千问模型负责「理解需求、打分排序」，两者通过 Prompt 拼接串联。**
