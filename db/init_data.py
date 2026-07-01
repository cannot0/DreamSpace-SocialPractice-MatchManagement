"""数据库初始化脚本。

执行 schema.sql 建表，然后调用 input.py 导入 Excel 数据。
用于 Railway 部署后的首次数据初始化。

用法:
    python -m db.init_data <excel文件路径>
"""

import os
import sys
import logging

import psycopg2

logger = logging.getLogger(__name__)


def get_connection():
    """获取 PostgreSQL 连接。"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("错误: 未设置 DATABASE_URL 环境变量")
        sys.exit(1)
    return psycopg2.connect(database_url)


def run_schema():
    """执行 schema.sql 建表。"""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        print(f"错误: 找不到 schema.sql ({schema_path})")
        sys.exit(1)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(schema_sql)
        conn.commit()
        print("数据库表创建成功！")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"建表失败: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


def ensure_tables():
    """确保数据库表已存在，不存在则自动建表。

    检查 activities 表是否存在，如果不存在则执行 schema.sql 建表。
    使用 CREATE TABLE IF NOT EXISTS，重复调用是安全的。
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 检查 activities 表是否存在
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'activities'
            )
        """)
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            logger.info("数据库表不存在，正在自动建表...")
            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            cursor.execute(schema_sql)
            conn.commit()
            logger.info("自动建表完成")
        else:
            logger.info("数据库表已存在，跳过建表")
    except psycopg2.Error as e:
        conn.rollback()
        logger.error("自动建表失败: %s", e)
        raise
    finally:
        cursor.close()
        conn.close()


def main():
    """主入口。"""
    if len(sys.argv) < 2:
        print("用法: python -m db.init_data <excel文件路径>")
        print("示例: python -m db.init_data db/活动详情_530000.xlsx")
        sys.exit(1)

    excel_path = sys.argv[1]
    if not os.path.exists(excel_path):
        print(f"错误: 文件不存在 ({excel_path})")
        sys.exit(1)

    print("=" * 50)
    print("步骤 1: 创建数据库表...")
    print("=" * 50)
    run_schema()

    print("\n" + "=" * 50)
    print("步骤 2: 导入 Excel 数据...")
    print("=" * 50)

    # 将项目根目录加入 path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from input import import_excel
    result = import_excel(excel_path)

    print(f"\n  成功写入: {result['success']} 条")
    print(f"  跳过: {result['skip']} 条")
    print(f"  错误: {result['error']} 条")

    print("\n" + "=" * 50)
    print("数据库初始化完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
