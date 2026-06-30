"""用户数据操作模块。

提供用户注册、登录验证、画像管理、推荐历史等数据库操作。
"""

import json
import logging
from datetime import datetime

import pyodbc

from ..config import DB_SERVER, DB_DATABASE, DB_TRUSTED_CONNECTION, DB_USER, DB_PASSWORD

logger = logging.getLogger(__name__)


def _get_connection():
    """获取数据库连接。优先使用账号密码，否则用 Windows 身份验证。"""
    if DB_USER and DB_PASSWORD:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_SERVER};"
            f"DATABASE={DB_DATABASE};"
            f"UID={DB_USER};"
            f"PWD={DB_PASSWORD};"
        )
    else:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_SERVER};"
            f"DATABASE={DB_DATABASE};"
            f"Trusted_Connection={DB_TRUSTED_CONNECTION};"
        )
    return pyodbc.connect(conn_str)


def create_user(username: str, password_hash: str, nickname: str = None) -> dict:
    """创建新用户。

    Args:
        username: 用户名
        password_hash: 密码哈希值
        nickname: 昵称（可选）

    Returns:
        创建成功返回用户信息字典，用户名已存在返回 None
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # 检查用户名是否已存在
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            logger.warning("用户名已存在: %s", username)
            return None

        # 插入新用户
        cursor.execute(
            "INSERT INTO users (username, password_hash, nickname) OUTPUT INSERTED.id VALUES (?, ?, ?)",
            (username, password_hash, nickname or username),
        )
        user_id = cursor.fetchone()[0]
        conn.commit()

        logger.info("用户注册成功: %s (id=%d)", username, user_id)
        return {"id": user_id, "username": username, "nickname": nickname or username}

    except pyodbc.Error as e:
        logger.error("创建用户失败: %s", e)
        return None
    finally:
        if "conn" in locals():
            conn.close()


def get_user_by_username(username: str) -> dict:
    """根据用户名查询用户。

    Args:
        username: 用户名

    Returns:
        用户信息字典，不存在返回 None
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, username, password_hash, nickname, created_at, last_login FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "nickname": row[3],
            "created_at": str(row[4]) if row[4] else None,
            "last_login": str(row[5]) if row[5] else None,
        }

    except pyodbc.Error as e:
        logger.error("查询用户失败: %s", e)
        return None
    finally:
        if "conn" in locals():
            conn.close()


def update_last_login(user_id: int) -> bool:
    """更新用户最后登录时间。

    Args:
        user_id: 用户ID

    Returns:
        是否更新成功
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET last_login = GETDATE() WHERE id = ?",
            (user_id,),
        )
        conn.commit()
        return True

    except pyodbc.Error as e:
        logger.error("更新登录时间失败: %s", e)
        return False
    finally:
        if "conn" in locals():
            conn.close()


def save_user_profile(user_id: int, profile: dict) -> bool:
    """保存用户画像（存在则更新，不存在则插入）。

    Args:
        user_id: 用户ID
        profile: 画像数据字典

    Returns:
        是否保存成功
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # 检查是否已有画像
        cursor.execute("SELECT id FROM user_profiles WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()

        if existing:
            # 更新
            cursor.execute(
                """UPDATE user_profiles SET
                    major = ?, grade = ?, skills = ?, province = ?, city = ?,
                    preference = ?, available_start = ?, available_end = ?, updated_at = GETDATE()
                WHERE user_id = ?""",
                (
                    profile.get("major", ""),
                    profile.get("grade", ""),
                    profile.get("skills", ""),
                    profile.get("province", ""),
                    profile.get("city", ""),
                    profile.get("preference", ""),
                    profile.get("available_start"),
                    profile.get("available_end"),
                    user_id,
                ),
            )
        else:
            # 插入
            cursor.execute(
                """INSERT INTO user_profiles
                    (user_id, major, grade, skills, province, city, preference, available_start, available_end)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    profile.get("major", ""),
                    profile.get("grade", ""),
                    profile.get("skills", ""),
                    profile.get("province", ""),
                    profile.get("city", ""),
                    profile.get("preference", ""),
                    profile.get("available_start"),
                    profile.get("available_end"),
                ),
            )

        conn.commit()
        logger.info("用户画像保存成功: user_id=%d", user_id)
        return True

    except pyodbc.Error as e:
        logger.error("保存用户画像失败: %s", e)
        return False
    finally:
        if "conn" in locals():
            conn.close()


def get_user_profile(user_id: int) -> dict:
    """获取用户画像。

    Args:
        user_id: 用户ID

    Returns:
        画像数据字典，不存在返回 None
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT major, grade, skills, province, city, preference, available_start, available_end FROM user_profiles WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "major": row[0] or "",
            "grade": row[1] or "",
            "skills": row[2] or "",
            "province": row[3] or "",
            "city": row[4] or "",
            "preference": row[5] or "",
            "available_start": str(row[6]) if row[6] else "",
            "available_end": str(row[7]) if row[7] else "",
        }

    except pyodbc.Error as e:
        logger.error("获取用户画像失败: %s", e)
        return None
    finally:
        if "conn" in locals():
            conn.close()


def save_recommendation(user_id: int, profile: dict, result: dict) -> bool:
    """保存推荐历史记录。

    Args:
        user_id: 用户ID
        profile: 用户画像（推荐时的快照）
        result: 推荐结果

    Returns:
        是否保存成功
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO recommendation_history (user_id, profile_snapshot, result_json) VALUES (?, ?, ?)",
            (user_id, json.dumps(profile, ensure_ascii=False), json.dumps(result, ensure_ascii=False)),
        )
        conn.commit()
        logger.info("推荐历史保存成功: user_id=%d", user_id)
        return True

    except pyodbc.Error as e:
        logger.error("保存推荐历史失败: %s", e)
        return False
    finally:
        if "conn" in locals():
            conn.close()


def get_recommendation_history(user_id: int, limit: int = 20) -> list:
    """获取用户推荐历史。

    Args:
        user_id: 用户ID
        limit: 返回数量限制

    Returns:
        历史记录列表，每条包含 profile_snapshot、result_json、created_at
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT profile_snapshot, result_json, created_at FROM recommendation_history WHERE user_id = ? ORDER BY created_at DESC OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY",
            (user_id, limit),
        )
        rows = cursor.fetchall()

        history = []
        for row in rows:
            history.append({
                "profile_snapshot": json.loads(row[0]) if row[0] else {},
                "result": json.loads(row[1]) if row[1] else {},
                "created_at": str(row[2]) if row[2] else "",
            })

        return history

    except pyodbc.Error as e:
        logger.error("获取推荐历史失败: %s", e)
        return []
    finally:
        if "conn" in locals():
            conn.close()


def get_all_users() -> list:
    """获取所有用户列表（管理员用）。

    Returns:
        用户列表，每个用户为字典格式（不含密码哈希）
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, username, nickname, created_at, last_login FROM users ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()

        users = []
        for row in rows:
            users.append({
                "id": row[0],
                "username": row[1],
                "nickname": row[2],
                "created_at": str(row[3]) if row[3] else "",
                "last_login": str(row[4]) if row[4] else "",
            })

        return users

    except pyodbc.Error as e:
        logger.error("获取用户列表失败: %s", e)
        return []
    finally:
        if "conn" in locals():
            conn.close()
