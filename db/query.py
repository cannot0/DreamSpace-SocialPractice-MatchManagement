"""mock活动数据查询。

实际接入MySQL时，可将本文件中的静态数据替换为数据库查询逻辑。
"""


MOCK_ACTIVITIES = [
    {
        "activity_id": "A001",
        "title": "广州智慧社区数据分析实践",
        "org_name": "广州市青年志愿服务中心",
        "province": "广东",
        "city": "广州",
        "category": "社会实践",
        "major_tags": ["计算机科学与技术", "软件工程", "数据科学"],
        "skill_tags": ["Python", "数据分析", "Excel"],
        "start_date": "2025-07-15",
        "end_date": "2025-08-10",
        "quota": 30,
        "source_url": "https://example.com/activities/A001",
    },
    {
        "activity_id": "A002",
        "title": "深圳互联网企业暑期实习体验营",
        "org_name": "深圳市创新创业服务协会",
        "province": "广东",
        "city": "深圳",
        "category": "企业实习",
        "major_tags": ["计算机科学与技术", "信息管理", "电子商务"],
        "skill_tags": ["Python", "产品调研", "数据分析"],
        "start_date": "2025-07-20",
        "end_date": "2025-08-15",
        "quota": 20,
        "source_url": "https://example.com/activities/A002",
    },
    {
        "activity_id": "A003",
        "title": "佛山制造业数字化转型调研",
        "org_name": "佛山市工信局实践基地",
        "province": "广东",
        "city": "佛山",
        "category": "基层调研",
        "major_tags": ["计算机科学与技术", "自动化", "工业工程"],
        "skill_tags": ["数据分析", "问卷设计", "报告写作"],
        "start_date": "2025-08-01",
        "end_date": "2025-08-25",
        "quota": 25,
        "source_url": "https://example.com/activities/A003",
    },
    {
        "activity_id": "A004",
        "title": "广州中小学编程公益课堂",
        "org_name": "广州市少年宫",
        "province": "广东",
        "city": "广州",
        "category": "志愿服务",
        "major_tags": ["计算机科学与技术", "教育技术学"],
        "skill_tags": ["Python", "Scratch", "沟通表达"],
        "start_date": "2025-07-01",
        "end_date": "2025-07-09",
        "quota": 40,
        "source_url": "https://example.com/activities/A004",
    },
    {
        "activity_id": "A005",
        "title": "杭州乡村文旅新媒体推广实践",
        "org_name": "杭州市乡村振兴实践中心",
        "province": "浙江",
        "city": "杭州",
        "category": "乡村振兴",
        "major_tags": ["新闻传播学", "旅游管理", "市场营销"],
        "skill_tags": ["短视频", "文案策划", "摄影"],
        "start_date": "2025-07-18",
        "end_date": "2025-08-05",
        "quota": 15,
        "source_url": "https://example.com/activities/A005",
    },
    {
        "activity_id": "A006",
        "title": "珠海政务数据治理见习项目",
        "org_name": "珠海市政务服务数据管理局",
        "province": "广东",
        "city": "珠海",
        "category": "政务见习",
        "major_tags": ["计算机科学与技术", "网络空间安全", "公共管理"],
        "skill_tags": ["数据分析", "SQL", "信息安全"],
        "start_date": "2025-08-16",
        "end_date": "2025-08-31",
        "quota": 12,
        "source_url": "https://example.com/activities/A006",
    },
]


def get_activities(province=None, major_tag=None, limit=20) -> list:
    """获取候选活动，当前为mock版本。"""
    activities = MOCK_ACTIVITIES

    if province:
        province_matched = [
            activity for activity in activities if activity.get("province") == province
        ]
        if province_matched:
            activities = province_matched

    if major_tag:
        major_matched = [
            activity
            for activity in activities
            if major_tag in activity.get("major_tags", [])
        ]
        if major_matched:
            activities = major_matched

    return activities[:limit]
