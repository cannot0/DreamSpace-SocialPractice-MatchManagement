# SQL Server 设置账号密码登录（SQL Server 身份验证）

> 目前数据库用的是 Windows 身份验证（Trusted_Connection=yes），但部署到云端（Railway）的 Linux 服务器无法使用这种方式，必须改成 SQL Server 身份验证（账号+密码）。

---

## 第一步：启用混合身份验证模式

1. 打开 **SQL Server Management Studio (SSMS)**，用 Windows 身份验证连接到你的数据库实例（服务器名填 `AIYU`）
2. 在左侧 **对象资源管理器** 中，右键点击最顶层的服务器节点（就是 `AIYU`） → 选择 **属性**
3. 左侧选 **安全性**
4. 在 **服务器身份验证** 那栏，把选项从 **Windows 身份验证模式** 改为 **SQL Server 和 Windows 身份验证模式**
5. 点 **确定**

```
截图参考位置：
服务器(AIYU) → 右键 → 属性 → 安全性 → 服务器身份验证 → 选第二个
```

## 第二步：重启 SQL Server 服务

改完身份验证模式后必须重启服务才能生效：

1. 按 `Win + R`，输入 `services.msc`，回车
2. 在服务列表里找到 **SQL Server (AIYU)**（名字可能是 `SQL Server (MSSQLSERVER)` 或 `SQL Server (AIYU)`，看你装的时候怎么命名的）
3. 右键 → **重启**
4. 等服务状态变回 **正在运行** 就好了

## 第三步：创建登录账号

回到 SSMS，点 **新建查询**，执行以下 SQL：

```sql
-- 创建一个新登录账号（用户名：recommender，密码自己改）
USE [hometown_practice];
GO

CREATE LOGIN recommender
    WITH PASSWORD = 'HtPractice2025!',
    DEFAULT_DATABASE = [hometown_practice],
    CHECK_POLICY = OFF;
GO

-- 在数据库里创建对应的用户
CREATE USER recommender FOR LOGIN recommender;
GO

-- 授予读写权限（推荐系统需要读取活动数据）
ALTER ROLE db_datareader ADD MEMBER recommender;
ALTER ROLE db_datawriter ADD MEMBER recommender;
GO
```

> **注意：** 把密码 `HtPractice2025!` 改成你自己设的强密码，记住它，后面要用。

## 第四步：测试新账号能否登录

1. 关掉当前的 SSMS 连接
2. 重新打开 SSMS，连接时：
   - 服务器名：`AIYU`
   - 身份验证：选 **SQL Server 身份验证**
   - 登录名：`recommender`
   - 密码：你刚才设的密码
3. 能连上就说明成功了

## 第五步：验证数据库访问

用新账号登录后，执行：

```sql
USE hometown_practice;
SELECT COUNT(*) FROM v_activity_full;
```

能返回活动数量就说明权限没问题。

## 第六步：把账号密码告诉我

完成后把以下信息发给我：

```
DB_SERVER=AIYU
DB_DATABASE=hometown_practice
DB_USER=recommender
DB_PASSWORD=你设的密码
```

我会更新 `.env` 文件和部署配置。

---

## 常见问题

**Q: 重启服务后连不上了？**
A: 确认服务已经重启完成（状态是"正在运行"），然后确认用的是 SQL Server 身份验证而不是 Windows 身份验证。

**Q: 报错 "Login failed for user"？**
A: 检查密码是否正确，注意大小写。如果密码策略（CHECK_POLICY）开着，密码需要满足复杂度要求。

**Q: 能登录但查不到表？**
A: 确认执行了 `CREATE USER` 和 `ALTER ROLE` 那两步，用户需要在 `hometown_practice` 数据库里有对应的映射。
