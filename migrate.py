"""部署时自动执行数据库迁移（idempotent，可重复运行）。"""
import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("DATABASE_URL 未设置，跳过迁移")
    exit(0)

MIGRATION_SQL = """
-- 添加 last_active 列到 users 表（用于在线状态追踪）
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active TIMESTAMP;

CREATE OR REPLACE VIEW v_activity_full AS
SELECT
    a.project_id, a.activity_id, a.title, a.org_name,
    a.province, a.city, a.district, a.category,
    a.start_date, a.end_date, a.quota, a.source_url,
    d.registration_start, d.registration_end,
    d.description, d.requirements, d.org_description,
    d.benefits, d.attachment_name, d.attachment_url,
    d.contact_person, d.contact_phone,
    a.crawled_at,
    COALESCE(
        (SELECT STRING_AGG(t.tag_value, ',')
         FROM activity_tags t
         WHERE t.project_id = a.project_id AND t.tag_type = 'major'), ''
    ) AS major_tags,
    COALESCE(
        (SELECT STRING_AGG(t.tag_value, ',')
         FROM activity_tags t
         WHERE t.project_id = a.project_id AND t.tag_type = 'skill'), ''
    ) AS skill_tags,
    CASE
        WHEN a.title LIKE a.province || '%'
            OR a.title LIKE a.province || '省%'
            OR a.title LIKE a.province || '自治区%'
            THEN a.title
        WHEN a.title LIKE a.city || '%'
            OR a.title LIKE a.city || '市%'
            OR a.title LIKE a.city || '自治州%'
            OR a.title LIKE a.city || '州%'
            THEN COALESCE(a.province, '') || a.title
        WHEN a.title LIKE a.district || '%'
            OR a.title LIKE a.district || '县%'
            OR a.title LIKE a.district || '区%'
            OR a.title LIKE a.district || '市%'
            THEN COALESCE(a.province, '') || COALESCE(a.city, '') || a.title
        ELSE COALESCE(a.province, '') || COALESCE(a.city, '') || COALESCE(a.district, '') || a.title
    END AS display_title
FROM activities a
LEFT JOIN activity_details d ON a.project_id = d.project_id
WHERE a.is_active = 1;
"""

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(MIGRATION_SQL)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ 迁移完成：users.last_active 列已添加，v_activity_full 视图已更新")
except Exception as e:
    print(f"⚠️ 迁移失败（不影响启动）: {e}")
