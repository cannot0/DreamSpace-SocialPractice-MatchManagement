"""活动数据查询模块。

从 PostgreSQL 数据库查询活动数据，支持省份、专业标签筛选。
"""

import logging

import psycopg2
import psycopg2.extras

from config import DATABASE_URL

logger = logging.getLogger(__name__)


def _get_connection():
    """获取 PostgreSQL 数据库连接。"""
    return psycopg2.connect(DATABASE_URL)


def _parse_tags(tags_str: str) -> list:
    """将逗号分隔的标签字符串解析为列表。"""
    if not tags_str:
        return []
    return [tag.strip() for tag in tags_str.split(",") if tag.strip()]


def _normalize_province(province: str) -> str:
    """规范化省份名称，去除常见后缀以便匹配。"""
    for suffix in ('省', '自治区', '壮族自治区', '回族自治区', '维吾尔自治区', '特别行政区'):
        if province.endswith(suffix):
            return province[:-len(suffix)]
    return province


def get_activities(province=None, major_tag=None, limit=20) -> list:
    """从数据库获取候选活动。

    使用 v_activity_full 视图查询，该视图已聚合活动主表、详情表和标签表。

    Args:
        province: 省份筛选条件
        major_tag: 专业标签筛选条件
        limit: 返回数量限制

    Returns:
        活动列表，每个活动为字典格式
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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
            normalized = _normalize_province(province)
            query += " AND province = %s"
            params.append(normalized)

        if major_tag:
            query += " AND (',' || major_tags || ',') LIKE %s"
            params.append(f"%,{major_tag},%")

        query += " ORDER BY crawled_at DESC LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # 如果按省份+专业筛选无结果，回退到只按省份筛选
        if not rows and major_tag and province:
            logger.info("按省份+专业筛选无结果，回退到只按省份筛选")
            fallback_query = """
                SELECT
                    project_id, activity_id, title, org_name,
                    province, city, district, category,
                    start_date, end_date, quota, source_url,
                    major_tags, skill_tags
                FROM v_activity_full
                WHERE province = %s
                ORDER BY crawled_at DESC LIMIT %s
            """
            cursor.execute(fallback_query, (normalized, limit))
            rows = cursor.fetchall()

        # 如果只按省份也无结果，返回不限省份的活动
        if not rows and province:
            logger.info("按省份筛选无结果，返回最新活动")
            cursor.execute("""
                SELECT
                    project_id, activity_id, title, org_name,
                    province, city, district, category,
                    start_date, end_date, quota, source_url,
                    major_tags, skill_tags
                FROM v_activity_full
                ORDER BY crawled_at DESC LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()

        activities = []
        for row in rows:
            activity = dict(row)
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

    except psycopg2.Error as e:
        logger.error("数据库查询失败: %s", e)
        return []
    finally:
        if "conn" in locals():
            conn.close()
