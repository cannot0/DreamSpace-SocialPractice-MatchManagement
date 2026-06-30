"""活动数据查询模块。

从SQL Server数据库查询活动数据，支持省份、专业标签筛选。
"""

import logging

import pyodbc

from ..config import DB_SERVER, DB_DATABASE, DB_TRUSTED_CONNECTION

logger = logging.getLogger(__name__)


def _get_connection():
    """获取数据库连接。"""
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        f"Trusted_Connection={DB_TRUSTED_CONNECTION};"
    )
    return pyodbc.connect(conn_str)


def _parse_tags(tags_str: str) -> list:
    """将逗号分隔的标签字符串解析为列表。"""
    if not tags_str:
        return []
    return [tag.strip() for tag in tags_str.split(",") if tag.strip()]


def get_activities(province=None, major_tag=None, limit=20) -> list:
    """从数据库获取候选活动。

    使用v_activity_full视图查询，该视图已聚合活动主表、详情表和标签表。

    Args:
        province: 省份筛选条件
        major_tag: 专业标签筛选条件
        limit: 返回数量限制

    Returns:
        活动列表，每个活动为字典格式
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # 构建查询语句
        query = """
            SELECT
                project_id, activity_id, title, org_name,
                province, city, district, category,
                start_date, end_date, quota, source_url,
                major_tags, skill_tags
            FROM v_activity_full
            WHERE 1=1
        """
        params = []

        if province:
            query += " AND province = ?"
            params.append(province)

        if major_tag:
            query += " AND (',' + major_tags + ',') LIKE ?"
            params.append(f"%,{major_tag},%")

        query += " ORDER BY crawled_at DESC OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY"
        params.append(limit)

        cursor.execute(query, params)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

        activities = []
        for row in rows:
            activity = dict(zip(columns, row))
            # 解析标签字符串为列表
            activity["major_tags"] = _parse_tags(activity.get("major_tags", ""))
            activity["skill_tags"] = _parse_tags(activity.get("skill_tags", ""))
            # 转换日期为字符串格式
            if activity.get("start_date"):
                activity["start_date"] = str(activity["start_date"])
            if activity.get("end_date"):
                activity["end_date"] = str(activity["end_date"])
            activities.append(activity)

        logger.info("查询到 %d 个活动", len(activities))
        return activities

    except pyodbc.Error as e:
        logger.error("数据库查询失败: %s", e)
        return []
    finally:
        if "conn" in locals():
            conn.close()
