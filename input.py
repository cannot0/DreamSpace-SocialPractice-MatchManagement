"""Excel 数据导入模块。

将 Excel 活动数据清洗后导入 PostgreSQL 数据库。
支持命令行运行和 Flask 调用。
"""

import json
import ast
import re
import logging
from datetime import datetime

import pandas as pd
import psycopg2

logger = logging.getLogger(__name__)


def _get_connection():
    """获取 PostgreSQL 数据库连接。"""
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("未设置 DATABASE_URL 环境变量")
    return psycopg2.connect(database_url)


# ==========================================
# 辅助函数 (数据清洗与解析)
# ==========================================

def parse_dict_or_json(val):
    """解析 Python 字典字符串或 JSON 字符串 (兼容单引号和双引号)"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        val = val.strip()
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            pass
        try:
            return ast.literal_eval(val)
        except (ValueError, SyntaxError):
            pass
        try:
            return json.loads(val.replace("'", '"'))
        except json.JSONDecodeError:
            return None
    return None


def parse_date(date_str):
    """将 '2026.01.01' 转换为 'YYYY-MM-DD'"""
    if not date_str or (isinstance(date_str, float) and pd.isna(date_str)):
        return None
    date_str = str(date_str).replace('.', '-')
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError:
        return None


def parse_address(area_list):
    """从 ['云南省XX市XX县'] 中提取省、市、县"""
    if not area_list or not isinstance(area_list, list) or not area_list[0]:
        return None, None, None

    full_addr = str(area_list[0]).strip()
    if not full_addr:
        return None, None, None

    prov_match = re.search(r'(.*?(?:省|自治区))', full_addr)
    province = prov_match.group(1).replace('省', '').replace('自治区', '') if prov_match else None

    start_idx = len(prov_match.group(1)) if prov_match else 0
    city_match = re.search(r'(.*?(?:市|自治州|地区|盟))', full_addr[start_idx:])
    city = city_match.group(1).replace('市', '').replace('自治州', '').replace('地区', '').replace('盟',
                                                                                                   '') if city_match else None

    if city_match:
        start_idx += len(city_match.group(1))
    district_str = full_addr[start_idx:]
    district = district_str.replace('县', '').replace('区', '').replace('市', '').replace('旗',
                                                                                          '') if district_str else None

    return province, city, district


def infer_category(title, content):
    """根据标题和内容智能推断活动类别"""
    text = (title or '') + (content or '')
    if re.search(r'企业|公司|银行|移动|电信|联通|产业园|供销社', text): return '企业实习'
    if re.search(r'文化|宣传|博物馆|融媒体|文旅|图书馆|档案馆|文联', text): return '文化传播'
    if re.search(r'科研|调研|检测|检验|实验室|气象局', text): return '科研调研'
    if re.search(r'志愿|公益|托管|支教|关爱|敬老|扶贫|三下乡', text): return '公益志愿'
    return '政务实践'


def parse_welfare(code):
    """将福利代码 '1,2,3' 转换为中文 '食宿,保险,交通'"""
    if not code or (isinstance(code, float) and pd.isna(code)):
        return None
    mapping = {'1': '食宿', '2': '保险', '3': '交通', '4': '补贴'}
    res = [mapping[c] for c in str(code).split(',') if c in mapping]
    return ','.join(res) if res else None


def extract_tags(post_setting, content):
    """深度提取专业要求(major)和岗位技能(skill)"""
    major_tags, skill_tags = [], []

    if content and not (isinstance(content, float) and pd.isna(content)):
        m1 = re.search(r'专业(?:要求)?[：:]\s*([^\n。]+)', str(content))
        if m1:
            req = m1.group(1).strip()
            if req and '不限' not in req:
                for m in re.split(r'[，,、/]', req):
                    m = m.strip().replace('专业', '').replace('优先', '')
                    if m and len(m) < 20: major_tags.append(m)
        else:
            m2 = re.search(r'([a-zA-Z一-龥]{2,10}专业)(?:优先|人员)', str(content))
            if m2: major_tags.append(m2.group(1).replace('专业', ''))

    if post_setting and isinstance(post_setting, dict):
        lists = post_setting.get('unitList', []) + post_setting.get('departlist', [])
        for unit in lists:
            if not isinstance(unit, dict): continue
            for dept in unit.get('childList', []):
                if not isinstance(dept, dict): continue
                child_posts = dept.get('childList', [])
                if child_posts:
                    for post in child_posts:
                        if not isinstance(post, dict): continue
                        name = post.get('name')
                        if name and len(name) < 30: skill_tags.append(name)
                else:
                    name = dept.get('name')
                    if name and len(name) < 30: skill_tags.append(name)

    return list(set(major_tags)), list(set(skill_tags))


def _process_row(cursor, row):
    """处理单行数据并插入数据库。

    Returns:
        'success', 'skip', 或 'error'
    """
    project_data = parse_dict_or_json(row.get('project'))
    if not project_data or not isinstance(project_data, dict):
        return 'skip'

    project_id = str(project_data.get('projectId', '')).strip()
    if not project_id or project_id == 'nan':
        return 'skip'

    title = str(project_data.get('projectName', ''))[:200]
    org_name = str(project_data.get('enterpriseName', ''))[:100]
    area_list = project_data.get('areaList', [])

    start_date = parse_date(project_data.get('startDate'))
    end_date = parse_date(project_data.get('endDate'))
    reg_start = parse_date(project_data.get('joinStartDate'))
    reg_end = parse_date(project_data.get('joinEndDate'))

    quota = project_data.get('enrollNum')
    project_content = str(project_data.get('projectContent', ''))
    join_tip = str(project_data.get('projectJoinTip', ''))
    company_profile = str(project_data.get('companyProfile', ''))
    welfare = parse_welfare(project_data.get('welfare', ''))

    province, city, district = parse_address(area_list)
    province = str(province)[:20] if province else None
    city = str(city)[:30] if city else None
    district = str(district)[:30] if district else None

    category = infer_category(title, project_content)

    # 联系人信息
    contact_list = parse_dict_or_json(row.get('contactList'))
    contact_names = []
    contact_phones = []
    if contact_list and isinstance(contact_list, list):
        for c in contact_list:
            if isinstance(c, dict):
                name = str(c.get('contactName', '')).strip()
                phone = str(c.get('contactTel', '')).strip()
                if name: contact_names.append(name)
                if phone: contact_phones.append(phone)

    contact_person = ','.join(contact_names)[:100] if contact_names else None
    contact_phone = ','.join(contact_phones)[:100] if contact_phones else None
    full_requirements = join_tip or ''

    # 插入 activities 表
    cursor.execute("""
        INSERT INTO activities (
            project_id, activity_id, title, org_name, province, city, district,
            category, start_date, end_date, quota, source_url, crawled_at, is_active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 1)
        ON CONFLICT (project_id) DO NOTHING
    """, (
        project_id, f'hash_{project_id}', title, org_name, province, city, district,
        category, start_date, end_date, quota, f'https://www.51sdd.com/activity/{project_id}'
    ))

    # 插入 activity_details 表
    attachment_list = parse_dict_or_json(row.get('attachmentList'))
    att_name, att_url = None, None
    if attachment_list and isinstance(attachment_list, list) and len(attachment_list) > 0:
        first_att = attachment_list[0]
        if isinstance(first_att, dict):
            att_name = str(first_att.get('filename', ''))[:200]
            att_url = str(first_att.get('url', ''))

    cursor.execute("""
        INSERT INTO activity_details (
            project_id, registration_start, registration_end, description,
            requirements, org_description, benefits, attachment_name, attachment_url,
            contact_person, contact_phone
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (project_id) DO NOTHING
    """, (
        project_id, reg_start, reg_end, project_content, full_requirements,
        company_profile, welfare, att_name, att_url, contact_person, contact_phone
    ))

    # 插入 activity_tags 表
    post_setting = parse_dict_or_json(row.get('postSetting'))
    major_tags, skill_tags = extract_tags(post_setting, project_content)

    for tag in major_tags:
        tag = str(tag)[:50]
        cursor.execute("""
            INSERT INTO activity_tags (project_id, tag_type, tag_value)
            VALUES (%s, 'major', %s)
            ON CONFLICT DO NOTHING
        """, (project_id, tag))

    for tag in skill_tags:
        tag = str(tag)[:50]
        cursor.execute("""
            INSERT INTO activity_tags (project_id, tag_type, tag_value)
            VALUES (%s, 'skill', %s)
            ON CONFLICT DO NOTHING
        """, (project_id, tag))

    return 'success'


def import_excel(excel_path: str, sheet_name: str = 'Sheet1') -> dict:
    """导入 Excel 数据到数据库。

    Args:
        excel_path: Excel 文件路径
        sheet_name: 工作表名称

    Returns:
        导入结果统计 {"success": N, "skip": N, "error": N, "errors": [...]}
    """
    logger.info("正在读取 Excel 文件: %s", excel_path)

    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        logger.info("共读取 %d 条数据", len(df))
    except Exception as e:
        logger.error("读取 Excel 失败: %s", e)
        return {"success": 0, "skip": 0, "error": 1, "errors": [str(e)]}

    try:
        conn = _get_connection()
        cursor = conn.cursor()
        logger.info("数据库连接成功")
    except Exception as e:
        logger.error("数据库连接失败: %s", e)
        return {"success": 0, "skip": 0, "error": 1, "errors": [str(e)]}

    success_count = 0
    error_count = 0
    skip_count = 0
    errors = []

    for index, row in df.iterrows():
        try:
            result = _process_row(cursor, row)
            if result == 'success':
                success_count += 1
            elif result == 'skip':
                skip_count += 1

            if success_count % 100 == 0 and success_count > 0:
                conn.commit()
                logger.info("已处理并提交 %d 条...", success_count)

        except Exception as e:
            error_count += 1
            error_msg = f"第 {index} 行处理失败: {e}"
            errors.append(error_msg)
            logger.warning(error_msg)
            continue

    conn.commit()
    cursor.close()
    conn.close()

    result = {
        "success": success_count,
        "skip": skip_count,
        "error": error_count,
        "errors": errors[:10],  # 只返回前10个错误
    }
    logger.info("导入完成: 成功=%d, 跳过=%d, 错误=%d", success_count, skip_count, error_count)
    return result


def main():
    """命令行入口。"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    if len(sys.argv) < 2:
        print("用法: python input.py <excel文件路径> [工作表名]")
        print("示例: python input.py db/活动详情_530000.xlsx Sheet1")
        sys.exit(1)

    excel_path = sys.argv[1]
    sheet_name = sys.argv[2] if len(sys.argv) > 2 else 'Sheet1'

    result = import_excel(excel_path, sheet_name)

    print("\n" + "=" * 50)
    print("数据导入完成！")
    print(f"  成功写入: {result['success']} 条")
    print(f"  跳过: {result['skip']} 条")
    print(f"  错误: {result['error']} 条")
    if result['errors']:
        print("  错误详情:")
        for err in result['errors']:
            print(f"    - {err}")
    print("=" * 50)


if __name__ == '__main__':
    main()
