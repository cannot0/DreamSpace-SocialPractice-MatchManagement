# SQL Server 账号密码登录配置指南

> 当前数据库使用的是 Windows 身份验证（`Trusted_Connection=yes`），Railway 部署在 Linux 上无法使用。
> 需要开启 **SQL Server 身份验证**，创建一个带密码的登录账号。

---

## 第一步：开启混合认证模式

SQL Server 默认只允许 Windows 身份验证，需要先开启混合模式。

1. 打开 **SQL Server Management Studio (SSMS)**，用 Windows 身份验证连接到服务器
2. 在左侧 **对象资源管理器** 中，右键点击最顶层的服务器名称（如 `AIYU`）
3. 选择 **属性(Properties)**
4. 左侧选择 **安全性(Security)**
5. 在 **服务器身份验证(Server authentication)** 下，选择 **SQL Server 和 Windows 身份验证模式(SQL Server and Windows Authentication mode)**
6. 点击 **确定(OK)**

```
┌─────────────────────────────────────────┐
│  服务器属性 → 安全性                      │
│                                         │
│  ○ Windows 身份验证模式                   │
│  ● SQL Server 和 Windows 身份验证模式     │
│                                         │
│                    [确定]  [取消]         │
└─────────────────────────────────────────┘
```

> ⚠️ **修改后需要重启 SQL Server 服务才能生效！**

---

## 第二步：重启 SQL Server 服务

两种方式任选一种：

### 方式 A：通过 SSMS 重启
1. 在对象资源管理器中右键服务器名称
2. 选择 **重新启动(Restart)**
3. 等待服务重启完成

### 方式 B：通过服务管理器重启
1. 按 `Win + R`，输入 `services.msc`，回车
2. 找到 **SQL Server (MSSQLSERVER)**（或你的实例名，如 `AIYU`）
3. 右键 → **重新启动**

```
服务列表中找到：
├── SQL Server (MSSQLSERVER)        ← 重启这个
├── SQL Server Agent (MSSQLSERVER)
├── SQL Server Browser
└── ...
```

---

## 第三步：创建 SQL Server 登录账号

重启后，在 SSMS 中执行以下 SQL：

```sql
-- 1. 创建登录名（LOGIN 是服务器级别的）
USE master;
GO

CREATE LOGIN recommender_app WITH PASSWORD = 'YourStrongPassword123!';
GO

-- 2. 切换到业务数据库
USE hometown_practice;
GO

-- 3. 创建数据库用户（USER 是数据库级别的）
CREATE USER recommender_app FOR LOGIN recommender_app;
GO

-- 4. 授予读取权限（只需要查询，不需要写入）
ALTER ROLE db_datareader ADD MEMBER recommender_app;
GO
```

> 💡 **说明：**
> - `recommender_app` 是登录名，你可以改成任意名字
> - `YourStrongPassword123!` 是密码，请改成你自己的强密码
> - `db_datareader` 角色只允许 SELECT 查询，权限最小化，更安全
> - 如果还需要写入权限，用 `db_datawriter`

---

## 第四步：确认 SQL Server 允许远程连接

### 4.1 开启 TCP/IP 协议
1. 打开 **SQL Server 配置管理器**（开始菜单搜索 `SQL Server Configuration Manager`）
2. 左侧展开 **SQL Server 网络配置** → **MSSQLSERVER 的协议**
3. 确认 **TCP/IP** 状态是 **已启用(Enabled)**
4. 如果是"已禁用"，右键 → **启用**
5. 双击 TCP/IP，切到 **IP 地址** 选项卡，确认 **TCP 端口** 是 **1433**

```
SQL Server 配置管理器
└── SQL Server 网络配置
    └── MSSQLSERVER 的协议
        ├── 共享内存    已启用
        ├── 命名管道    已禁用
        ├── TCP/IP      已启用    ← 确认这个
        └── VIA         已禁用
```

### 4.2 重启 SQL Server 服务
改完协议后需要再次重启服务（同第二步）。

### 4.3 Windows 防火墙放行 1433 端口
1. 打开 **Windows Defender 防火墙** → **高级设置**
2. 左侧点 **入站规则(Inbound Rules)** → 右侧点 **新建规则(New Rule)**
3. 选择 **端口(Port)** → 下一步
4. 输入端口 `1433` → 下一步
5. 选择 **允许连接(Allow the connection)** → 下一步
6. 勾选 **域、专用、公用** 全部 → 下一步
7. 名称填 `SQL Server 1433` → 完成

---

## 第五步：测试新账号连接

在 SSMS 中断开当前连接，重新连接：

1. **服务器名称：** `AIYU`（或 `localhost`）
2. **身份验证：** 选择 **SQL Server 身份验证**
3. **登录名：** `recommender_app`
4. **密码：** `YourStrongPassword123!`

能连上就说明配置成功。

### 用命令行测试（可选）

```bash
# 安装 pyodbc 后测试
python -c "
import pyodbc
conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=AIYU;'
    'DATABASE=hometown_practice;'
    'UID=recommender_app;'
    'PWD=YourStrongPassword123!;'
)
print('连接成功！')
conn.close()
"
```

---

## 第六步：更新项目配置

测试通过后，更新 `.env` 文件：

```env
QWEN_API_KEY=你的千问API密钥

# SQL Server 数据库配置
DB_SERVER=你的服务器IP或域名
DB_DATABASE=hometown_practice
DB_TRUSTED_CONNECTION=no
DB_USER=recommender_app
DB_PASSWORD=YourStrongPassword123!
```

同时需要修改 `config.py` 和 `db/query.py` 来支持账号密码登录（代码改动由项目组完成）。

---

## 常见问题

### Q: 忘记了 SA 密码怎么办？
用 Windows 身份验证登录 SSMS，在安全性 → 登录名 → sa 上右键重置密码。

### Q: 连接时报 "Login failed for user"？
- 确认混合认证模式已开启
- 确认 SQL Server 服务已重启
- 确认用户名密码正确（注意大小写）

### Q: 连接时报 "无法连接到服务器"？
- 确认 TCP/IP 协议已启用
- 确认 1433 端口已放行
- 确认 SQL Server Browser 服务在运行

### Q: Railway 部署后连不上数据库？
- 确认数据库服务器有公网 IP（Railway 的服务器在海外，连不到内网）
- 如果没有公网 IP，需要：
  - 使用云服务器上的 SQL Server，或
  - 使用 Railway 的 PostgreSQL 插件替代，或
  - 使用内网穿透工具（如 frp、ngrok）
