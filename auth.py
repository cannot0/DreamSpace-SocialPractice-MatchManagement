"""认证逻辑模块。

提供用户注册、登录验证、路由保护装饰器等功能。
"""

import re
import logging
from functools import wraps

from flask import session, redirect, url_for, request
from werkzeug.security import generate_password_hash, check_password_hash

from .config import ADMIN_USERNAME, ADMIN_PASSWORD

logger = logging.getLogger(__name__)

# 登录失败计数（内存中，防暴力破解）
_login_failures = {}  # key: ip, value: {"count": int, "last_fail": datetime}


def validate_username(username: str) -> str:
    """验证用户名格式。

    Returns:
        错误信息，验证通过返回空字符串
    """
    if not username:
        return "用户名不能为空"
    if len(username) < 3 or len(username) > 50:
        return "用户名长度需在 3-50 个字符之间"
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return "用户名只能包含字母、数字和下划线"
    return ""


def validate_password(password: str) -> str:
    """验证密码格式。

    Returns:
        错误信息，验证通过返回空字符串
    """
    if not password:
        return "密码不能为空"
    if len(password) < 6 or len(password) > 50:
        return "密码长度需在 6-50 个字符之间"
    return ""


def validate_nickname(nickname: str) -> str:
    """验证昵称格式。

    Returns:
        错误信息，验证通过返回空字符串
    """
    if not nickname:
        return "昵称不能为空"
    if len(nickname) > 50:
        return "昵称长度不能超过 50 个字符"
    return ""


def hash_password(password: str) -> str:
    """生成密码哈希。"""
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码。"""
    return check_password_hash(password_hash, password)


def check_login_rate_limit(ip: str) -> bool:
    """检查登录频率限制。

    5 分钟内失败 5 次则锁定。

    Returns:
        True: 允许登录，False: 已锁定
    """
    import time

    if ip not in _login_failures:
        return True

    record = _login_failures[ip]
    # 超过 5 分钟，重置计数
    if time.time() - record["last_fail"] > 300:
        del _login_failures[ip]
        return True

    return record["count"] < 5


def record_login_failure(ip: str):
    """记录登录失败。"""
    import time

    if ip not in _login_failures:
        _login_failures[ip] = {"count": 0, "last_fail": 0}

    _login_failures[ip]["count"] += 1
    _login_failures[ip]["last_fail"] = time.time()


def clear_login_failures(ip: str):
    """清除登录失败记录（登录成功时调用）。"""
    if ip in _login_failures:
        del _login_failures[ip]


def authenticate_admin(username: str, password: str) -> bool:
    """验证管理员账号。

    通过环境变量配置的管理员用户名和密码进行比对。

    Returns:
        是否验证成功
    """
    if not ADMIN_PASSWORD:
        # 未配置管理员密码，不允许管理员登录
        return False

    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def login_required(f):
    """路由装饰器：要求用户登录。"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """路由装饰器：要求管理员权限。"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated
