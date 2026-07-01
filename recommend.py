"""寒暑假返家乡活动智能推荐主逻辑。"""

import json
import logging
import re
from datetime import date

import requests

from config import (
    BASE_URL,
    CANDIDATE_LIMIT,
    QWEN_API_KEY,
    MAX_RETRY,
    MODEL_NAME,
)
from db.query import get_activities
from prompt_template import SYSTEM_PROMPT, render_prompt


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)


def _call_llm(system_prompt, user_prompt) -> str:
    """调用千问API（OpenAI兼容接口，直接HTTP请求，无需openai库）。"""
    if not QWEN_API_KEY:
        logger.info("未检测到QWEN_API_KEY，使用dry_run示例结果")
        return _dry_run_response(user_prompt)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 1500,
        },
        timeout=60,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"] or ""
    logger.info("LLM调用成功，响应长度：%s", len(content))
    return content


def _parse_llm_response(raw: str) -> dict:
    """解析模型响应，兼容偶发Markdown代码块包裹。"""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def get_recommendations(user_profile: dict) -> dict:
    """获取活动推荐结果。"""
    logger.info("=== 推荐请求开始 ===")
    logger.info("用户画像: %s", user_profile)
    logger.info("QWEN_API_KEY 状态: %s", "已配置" if QWEN_API_KEY else "未配置（将使用 dry_run）")

    try:
        activities = get_activities(
            province=user_profile.get("province"),
            major_tag=user_profile.get("major"),
            limit=CANDIDATE_LIMIT,
        )
    except Exception as e:
        logger.error("获取活动失败: %s", e, exc_info=True)
        return {"error": f"数据库查询失败：{e}", "recommendations": []}

    logger.info("获取到 %d 个候选活动", len(activities))
    if not activities:
        logger.warning("候选活动为空，无法生成推荐")
        return {"error": "未找到候选活动", "recommendations": []}

    user_prompt = render_prompt(user_profile, activities)
    logger.info("Prompt 已渲染，长度: %d", len(user_prompt))

    last_error = ""
    for attempt in range(1, MAX_RETRY + 2):
        try:
            logger.info("开始第%s次推荐调用，候选活动数：%s", attempt, len(activities))
            raw = _call_llm(SYSTEM_PROMPT, user_prompt)
            logger.info("LLM 响应长度: %d", len(raw))
            result = _parse_llm_response(raw)

            if "recommendations" not in result or not isinstance(
                result["recommendations"], list
            ):
                raise ValueError("模型返回缺少recommendations数组")

            logger.info(
                "推荐解析成功，返回推荐数：%s", len(result.get("recommendations", []))
            )
            return result
        except Exception as exc:
            last_error = str(exc)
            logger.warning("第%s次推荐失败：%s", attempt, last_error)
            if attempt <= MAX_RETRY:
                logger.info("准备重试推荐调用")

    return {
        "error": f"推荐生成失败：{last_error}",
        "recommendations": [],
    }


def _dry_run_response(user_prompt: str) -> str:
    """本地调试模式：不请求外部API，按核心规则生成示例推荐。"""
    profile = _extract_profile_from_prompt(user_prompt)
    activities = _extract_activities_from_prompt(user_prompt)

    recommendations = []
    for activity in activities:
        if not _has_date_overlap(
            profile.get("available_start"),
            profile.get("available_end"),
            activity.get("start_date"),
            activity.get("end_date"),
        ):
            continue

        score = _score_activity(profile, activity)
        recommendations.append(
            {
                "activity_id": activity.get("activity_id"),
                "title": activity.get("title"),
                "match_score": score,
                "match_reason": _build_match_reason(profile, activity),
                "highlight": _build_highlight(profile, activity),
            }
        )

    recommendations.sort(key=lambda item: item["match_score"], reverse=True)
    for index, item in enumerate(recommendations, start=1):
        item["rank"] = index

    ordered_recommendations = [
        {
            "rank": item["rank"],
            "activity_id": item["activity_id"],
            "title": item["title"],
            "match_score": item["match_score"],
            "match_reason": item["match_reason"],
            "highlight": item["highlight"],
        }
        for item in recommendations
    ]
    return json.dumps({"recommendations": ordered_recommendations}, ensure_ascii=False)


def _extract_profile_from_prompt(user_prompt: str) -> dict:
    """从已渲染Prompt中提取画像，供dry_run使用。"""
    fields = {
        "major": "专业",
        "grade": "年级",
        "skills": "技能",
        "available_start": "可参加开始日期",
        "available_end": "可参加结束日期",
        "province": "省份",
        "city": "城市",
        "preference": "偏好",
    }
    profile = {}
    for key, label in fields.items():
        match = re.search(rf"- {label}：(.+)", user_prompt)
        profile[key] = match.group(1).strip() if match else ""
    return profile


def _extract_activities_from_prompt(user_prompt: str) -> list:
    """从Prompt中提取候选活动JSON，供dry_run使用。"""
    marker = "候选活动JSON："
    start = user_prompt.index(marker) + len(marker)
    end = user_prompt.index("推荐规则：")
    return json.loads(user_prompt[start:end].strip())


def _has_date_overlap(user_start, user_end, activity_start, activity_end) -> bool:
    """判断两个日期区间是否重叠。"""
    if not all([user_start, user_end, activity_start, activity_end]):
        return False
    user_start_date = _parse_date(user_start)
    user_end_date = _parse_date(user_end)
    activity_start_date = _parse_date(activity_start)
    activity_end_date = _parse_date(activity_end)
    return max(user_start_date, activity_start_date) <= min(
        user_end_date, activity_end_date
    )


def _score_activity(profile: dict, activity: dict) -> int:
    """按Prompt中的权重计算dry_run分数。"""
    major_score = 40 if profile.get("major") in activity.get("major_tags", []) else 15
    time_score = _time_score(
        profile.get("available_start"),
        profile.get("available_end"),
        activity.get("start_date"),
        activity.get("end_date"),
    )
    skill_score = _skill_score(profile.get("skills", ""), activity.get("skill_tags", []))
    preference_score = _preference_score(
        profile.get("preference", ""), activity.get("category", ""), activity.get("title", "")
    )
    city_bonus = 3 if profile.get("city") == activity.get("city") else 0
    return min(100, int(major_score + time_score + skill_score + preference_score + city_bonus))


def _time_score(user_start, user_end, activity_start, activity_end) -> int:
    user_start_date = _parse_date(user_start)
    user_end_date = _parse_date(user_end)
    activity_start_date = _parse_date(activity_start)
    activity_end_date = _parse_date(activity_end)
    overlap_days = (
        min(user_end_date, activity_end_date) - max(user_start_date, activity_start_date)
    ).days + 1
    activity_days = (activity_end_date - activity_start_date).days + 1
    if overlap_days >= activity_days:
        return 30
    return max(10, round(30 * overlap_days / activity_days))


def _skill_score(skills: str, skill_tags: list) -> int:
    normalized_skills = {skill.strip().lower() for skill in re.split(r"[,，]", skills)}
    normalized_tags = {tag.strip().lower() for tag in skill_tags}
    matched_count = len(normalized_skills & normalized_tags)
    if matched_count >= 2:
        return 20
    if matched_count == 1:
        return 12
    return 5


def _preference_score(preference: str, category: str, title: str) -> int:
    text = f"{category} {title}"
    score = 0
    if "企业" in preference and ("企业" in text or "实习" in text):
        score += 6
    if "实习证明" in preference and ("实习" in text or "见习" in text):
        score += 4
    return min(10, score)


def _build_match_reason(profile: dict, activity: dict) -> str:
    if profile.get("city") == activity.get("city"):
        return "本地活动，专业技能匹配，时间可参加"
    if activity.get("category") == "企业实习":
        return "企业实习偏好匹配，时间高度重叠"
    return "专业方向匹配，活动时间与假期重叠"


def _build_highlight(profile: dict, activity: dict) -> str:
    if activity.get("category") == "企业实习":
        return "企业实习场景，适合积累证明材料"
    if profile.get("city") == activity.get("city"):
        return "广州本地实践，通勤和参与成本较低"
    return f"{activity.get('category')}方向，适合补充返乡实践经历"


def _parse_date(value: str) -> date:
    """兼容Python 3.6的ISO日期解析。"""
    year, month, day = [int(part) for part in value.split("-")]
    return date(year, month, day)
