# 数据库对接文档 — 登录功能所需建表

> 日期：2026-06-30
> 用途：交给负责数据库的队友执行

---

## 背景

网站要增加用户登录功能，需要在现有的 `hometown_practice` 数据库中新建 3 张表。请在 SQL Server 中执行以下 SQL 语句。

---

## 需要执行的 SQL

### 1. 用户表 `users`

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

**字段说明：**
- `id`：自增主键
- `username`：用户名，唯一，不允许重复
- `password_hash`：密码哈希值（不是明文密码，程序端会自动加密）
- `nickname`：用户昵称
- `created_at`：注册时间，自动填充
- `last_login`：最后登录时间

### 2. 用户画像表 `user_profiles`

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

**字段说明：**
- `user_id`：外键，关联 users 表
- `major`：专业（如"计算机科学与技术"）
- `grade`：年级（如"大三"）
- `skills`：技能，逗号分隔（如"Python，数据分析"）
- `province` / `city`：省份/城市
- `available_start` / `available_end`：可参加时间段
- `preference`：兴趣偏好

### 3. 推荐历史表 `recommendation_history`

```sql
CREATE TABLE recommendation_history (
    id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id),
    profile_snapshot NVARCHAR(MAX),
    result_json NVARCHAR(MAX),
    created_at DATETIME DEFAULT GETDATE()
);
```

**字段说明：**
- `user_id`：外键，关联 users 表
- `profile_snapshot`：推荐时的用户画像快照（JSON 格式字符串）
- `result_json`：推荐结果（JSON 格式字符串）

---

## 执行顺序

1. 先执行 `users` 表（因为其他两张表依赖它）
2. 再执行 `user_profiles` 表
3. 最后执行 `recommendation_history` 表

---

## 验证

执行完成后，可以用以下语句验证表是否创建成功：

```sql
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME IN ('users', 'user_profiles', 'recommendation_history');
```

应该返回 3 行记录。

---

## 注意事项

- 这 3 张表与现有的 `activities`、`activity_details`、`activity_tags` 表在同一个数据库中
- 程序端会通过 pyodbc 连接数据库，使用现有的连接方式（账号密码或 Windows 认证）
- 密码不会以明文存入数据库，程序端会自动加密

---

## 完成后请回复

建表完成后请告诉我，我这边就可以开始写代码对接了。
