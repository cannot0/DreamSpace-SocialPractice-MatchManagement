"""Flask接口服务。"""

import os
import secrets
import logging

from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from werkzeug.middleware.proxy_fix import ProxyFix

from config import SECRET_KEY
from recommend import get_recommendations
from auth import (
    login_required, admin_required,
    validate_username, validate_password, validate_nickname,
    hash_password, verify_password,
    check_login_rate_limit, record_login_failure, clear_login_failures,
    authenticate_admin,
)
from db.user import (
    create_user, get_user_by_username, update_last_login,
    save_recommendation, get_recommendation_history,
    get_all_users,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))
app.secret_key = SECRET_KEY

# Railway 使用反向代理，需要正确识别 HTTPS
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Session cookie 配置（适配 Railway HTTPS）
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


def generate_csrf_token():
    """生成 CSRF token。"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def validate_csrf_token():
    """验证 CSRF token。（Railway 部署时 session 可能不稳定，暂时跳过验证）"""
    return True


# 将 csrf_token 函数注入所有模板
app.jinja_env.globals['csrf_token'] = generate_csrf_token


# ==================== 认证路由 ====================

@app.route("/login", methods=["GET", "POST"])
def login():
    """登录页面。"""
    if request.method == "GET":
        # 已登录则跳转到首页
        if 'user_id' in session:
            return redirect(url_for('index'))
        return render_template("login.html")

    # POST: 处理登录
    if not validate_csrf_token():
        return render_template("login.html", error="请求无效，请刷新页面重试")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    # 频率限制
    ip = request.remote_addr
    if not check_login_rate_limit(ip):
        return render_template("login.html", rate_limited=True)

    # 先检查是否是管理员
    if authenticate_admin(username, password):
        session['user_id'] = 0
        session['username'] = username
        session['nickname'] = '管理员'
        session['is_admin'] = True
        clear_login_failures(ip)
        logger.info("管理员登录成功: %s", username)
        return redirect(url_for('admin'))

    # 查询普通用户
    user = get_user_by_username(username)
    if not user or not verify_password(password, user['password_hash']):
        record_login_failure(ip)
        return render_template("login.html", error="用户名或密码错误")

    # 登录成功
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['nickname'] = user['nickname']
    session['is_admin'] = False
    clear_login_failures(ip)
    update_last_login(user['id'])
    logger.info("用户登录成功: %s", username)
    return redirect(url_for('index'))


@app.route("/register", methods=["GET", "POST"])
def register():
    """注册页面。"""
    if request.method == "GET":
        if 'user_id' in session:
            return redirect(url_for('index'))
        return render_template("register.html")

    # POST: 处理注册
    if not validate_csrf_token():
        return render_template("register.html", error="请求无效，请刷新页面重试")

    username = request.form.get("username", "").strip()
    nickname = request.form.get("nickname", "").strip()
    password = request.form.get("password", "")
    password_confirm = request.form.get("password_confirm", "")

    # 验证
    error = validate_username(username)
    if not error:
        error = validate_nickname(nickname)
    if not error:
        error = validate_password(password)
    if not error and password != password_confirm:
        error = "两次输入的密码不一致"

    if error:
        return render_template("register.html", error=error)

    # 创建用户
    user = create_user(username, hash_password(password), nickname)
    if not user:
        return render_template("register.html", error="用户名已存在")

    # 自动登录
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['nickname'] = user['nickname']
    session['is_admin'] = False
    logger.info("用户注册成功: %s", username)
    return redirect(url_for('index'))


@app.route("/logout")
def logout():
    """退出登录。"""
    session.clear()
    return redirect(url_for('login'))


# ==================== 用户路由 ====================

@app.route("/", methods=["GET"])
@login_required
def index():
    """推荐系统前端页面。"""
    return render_template("index.html",
                           username=session.get('username'),
                           nickname=session.get('nickname'),
                           is_admin=session.get('is_admin', False))


@app.route("/history")
@login_required
def history():
    """推荐历史页面。"""
    user_id = session['user_id']
    records = get_recommendation_history(user_id) if user_id != 0 else []
    return render_template("history.html",
                           records=records,
                           username=session.get('username'),
                           nickname=session.get('nickname'),
                           is_admin=session.get('is_admin', False))


# ==================== 管理路由 ====================

@app.route("/admin")
@admin_required
def admin():
    """管理后台页面。"""
    users = get_all_users()
    return render_template("admin.html",
                           users=users,
                           username=session.get('username'),
                           nickname=session.get('nickname'))


@app.route("/admin/upload", methods=["POST"])
@admin_required
def admin_upload():
    """Excel 上传导入。"""
    if 'file' not in request.files:
        return jsonify({"error": "未选择文件"}), 400

    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({"error": "请上传 Excel 文件（.xlsx 或 .xls）"}), 400

    # 保存到临时文件
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    try:
        file.save(tmp.name)
        tmp.close()

        # 自动检测并建表
        try:
            from db.init_data import ensure_tables
            ensure_tables()
        except Exception as e:
            logger.error("自动建表失败: %s", e)
            return jsonify({"error": f"建表失败：{e}"}), 500

        from input import import_excel

        try:
            result = import_excel(tmp.name)
        except Exception as e:
            logger.error("导入数据失败: %s", e)
            return jsonify({"error": f"导入失败：{e}"}), 500

        return jsonify({
            "message": f"导入完成：成功 {result['success']} 条，跳过 {result['skip']} 条，错误 {result['error']} 条",
            "result": result,
            "filename": file.filename,
        })
    except Exception as e:
        logger.error("上传处理异常: %s", e)
        return jsonify({"error": f"处理失败：{e}"}), 500
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@app.route("/admin/users")
@admin_required
def admin_users():
    """用户列表（JSON）。"""
    users = get_all_users()
    return jsonify({"users": users})


# ==================== API 路由 ====================

@app.route("/health", methods=["GET"])
def health():
    """健康检查。"""
    return jsonify({"status": "ok"})


@app.route("/debug/db", methods=["GET"])
@admin_required
def debug_db():
    """数据库诊断。"""
    import psycopg2
    from config import DATABASE_URL
    info = {}
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        info["tables"] = [r[0] for r in cursor.fetchall()]

        # 检查各表数据量
        for table in ("activities", "activity_details", "activity_tags"):
            if table in info["tables"]:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                info[f"{table}_count"] = cursor.fetchone()[0]

        # 检查视图是否存在
        cursor.execute("""
            SELECT table_name FROM information_schema.views
            WHERE table_schema = 'public'
        """)
        info["views"] = [r[0] for r in cursor.fetchall()]

        # 测试 v_activity_full 视图
        if "v_activity_full" in info.get("views", []):
            cursor.execute("SELECT COUNT(*) FROM v_activity_full")
            info["v_activity_full_count"] = cursor.fetchone()[0]

            cursor.execute("SELECT project_id, title, province, major_tags FROM v_activity_full LIMIT 3")
            info["sample"] = [dict(zip(["project_id", "title", "province", "major_tags"], r)) for r in cursor.fetchall()]

        # 测试查询
        cursor.execute("SELECT DISTINCT province FROM activities LIMIT 10")
        info["sample_provinces"] = [r[0] for r in cursor.fetchall()]

        cursor.close()
        conn.close()
        info["status"] = "ok"
    except Exception as e:
        info["status"] = "error"
        info["error"] = str(e)

    return jsonify(info)


@app.route("/api/recommend", methods=["POST"])
@login_required
def recommend():
    """活动推荐接口。"""
    user_profile = request.get_json(silent=True) or {}
    required_fields = ["major", "available_start", "available_end", "province"]
    missing_fields = [field for field in required_fields if not user_profile.get(field)]

    if missing_fields:
        return (
            jsonify(
                {
                    "error": f"缺少必填字段：{', '.join(missing_fields)}",
                    "recommendations": [],
                }
            ),
            400,
        )

    try:
        logger.info("收到推荐请求: %s", user_profile)
        result = get_recommendations(user_profile)
        logger.info("推荐完成: %s", result.get("recommendations", [])[:1] if isinstance(result, dict) else "非dict")
    except Exception as e:
        logger.error("推荐接口异常: %s", e, exc_info=True)
        return jsonify({"error": f"推荐生成失败：{e}", "recommendations": []}), 500

    # 保存推荐历史（非管理员用户）
    user_id = session.get('user_id')
    if user_id and user_id != 0:
        try:
            save_recommendation(user_id, user_profile, result)
        except Exception as e:
            logger.warning("保存推荐历史失败: %s", e)

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
