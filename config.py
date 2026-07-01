import os

"""推荐模块配置。"""

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()

QWEN_API_KEY = os.getenv("QWEN_API_KEY")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = os.getenv("MODEL_NAME", "qwen-turbo-latest")
MAX_RETRY = 2
CANDIDATE_LIMIT = 20

# PostgreSQL 数据库配置
# Railway 会自动注入 DATABASE_URL 环境变量
# 格式: postgresql://user:password@host:port/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Session 密钥
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

# 管理员配置
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
