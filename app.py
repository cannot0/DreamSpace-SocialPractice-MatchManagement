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
    save_user_profile, get_user_profile,
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
    """验证 CSRF token。"""
    token = request.form.get('csrf_token', '')
    return token and token == session.get('csrf_token')


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


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """用户画像页面。"""
    user_id = session['user_id']

    if request.method == "GET":
        # 获取已保存的画像
        saved_profile = get_user_profile(user_id) if user_id != 0 else None
        return render_template("profile.html",
                               profile=saved_profile or {},
                               saved=request.args.get('saved') == '1',
                               username=session.get('username'),
                               nickname=session.get('nickname'),
                               is_admin=session.get('is_admin', False))

    # POST: 保存画像
    if not validate_csrf_token():
        return redirect(url_for('profile'))

    profile_data = {
        "major": request.form.get("major", "").strip(),
        "grade": request.form.get("grade", "").strip(),
        "skills": request.form.get("skills", "").strip(),
        "province": request.form.get("province", "").strip(),
        "city": request.form.get("city", "").strip(),
        "preference": request.form.get("preference", "").strip(),
        "available_start": request.form.get("available_start") or None,
        "available_end": request.form.get("available_end") or None,
    }

    if user_id != 0:
        save_user_profile(user_id, profile_data)

    # 保存成功后重定向，带上 saved 参数
    return redirect(url_for('profile', saved='1'))


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

        from input import import_excel

        result = import_excel(tmp.name)
        return jsonify({
            "message": f"导入完成：成功 {result['success']} 条，跳过 {result['skip']} 条，错误 {result['error']} 条",
            "result": result,
            "filename": file.filename,
        })
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

    result = get_recommendations(user_profile)

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
