"""Flask接口服务。"""

import os
import sys

from flask import Flask, jsonify, render_template, request

try:
    from .recommend import get_recommendations
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from recommender.recommend import get_recommendations


app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))


@app.route("/", methods=["GET"])
def index():
    """推荐系统前端页面。"""
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    """健康检查。"""
    return jsonify({"status": "ok"})


@app.route("/api/recommend", methods=["POST"])
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

    return jsonify(get_recommendations(user_profile))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
