"""大模型推荐 Prompt 模板。"""

import json

from jinja2 import Template


SYSTEM_PROMPT = """你是一个寒暑假“返家乡”活动推荐助理。
你的任务是根据学生画像和候选活动列表，筛选并排序最适合学生的活动。
你必须严格输出纯JSON，不允许包含Markdown代码块、解释文字、前后缀或任何非JSON内容。"""


USER_PROMPT_TEMPLATE = Template(
    """请根据以下学生画像和候选活动，输出个性化推荐清单。

学生画像：
- 专业：{{ major }}
- 年级：{{ grade }}
- 技能：{{ skills }}
- 可参加开始日期：{{ available_start }}
- 可参加结束日期：{{ available_end }}
- 省份：{{ province }}
- 城市：{{ city }}
- 偏好：{{ preference }}

候选活动JSON：
{{ activities_json }}

推荐规则：
1. 活动时间与学生可参加时间没有重叠的，必须直接排除。
2. 优先推荐省份、城市、专业方向、技能标签和偏好更匹配的活动。
3. 评分维度：
   - 专业匹配：40%
   - 时间可行性：30%
   - 技能适配：20%
   - 偏好：10%
4. match_score必须是0-100之间的整数。
5. match_reason不超过50字。
6. recommendations按match_score从高到低排序，rank从1开始。

请严格按以下JSON格式输出：
{
  "recommendations": [
    {
      "rank": 1,
      "activity_id": "A001",
      "title": "智慧社区数据分析实践",
      "match_score": 92,
      "match_reason": "专业和Python技能匹配，时间完全重叠",
      "highlight": "可获得实践证明"
    }
  ]
}
"""
)


def render_prompt(user_profile: dict, activities: list) -> str:
    """渲染用户 Prompt。"""
    activities_json = json.dumps(activities, ensure_ascii=False, indent=2)
    return USER_PROMPT_TEMPLATE.render(
        major=user_profile.get("major", ""),
        grade=user_profile.get("grade", ""),
        skills=user_profile.get("skills", ""),
        available_start=user_profile.get("available_start", ""),
        available_end=user_profile.get("available_end", ""),
        province=user_profile.get("province", ""),
        city=user_profile.get("city", ""),
        preference=user_profile.get("preference", ""),
        activities_json=activities_json,
    )
