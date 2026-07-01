-- PostgreSQL 建表脚本
-- 从 SQL Server hometown_practice 数据库迁移

-- ==========================================
-- 1. 活动主表
-- ==========================================
CREATE TABLE IF NOT EXISTS activities (
    project_id VARCHAR(20) PRIMARY KEY,
    activity_id VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    org_name VARCHAR(100),
    province VARCHAR(20),
    city VARCHAR(30),
    district VARCHAR(30),
    category VARCHAR(20),
    start_date DATE,
    end_date DATE,
    quota INT,
    source_url TEXT,
    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active SMALLINT DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_activities_province ON activities(province);
CREATE INDEX IF NOT EXISTS idx_activities_category ON activities(category);
CREATE INDEX IF NOT EXISTS idx_activities_crawled_at ON activities(crawled_at);

-- ==========================================
-- 2. 活动详情表
-- ==========================================
CREATE TABLE IF NOT EXISTS activity_details (
    project_id VARCHAR(20) PRIMARY KEY REFERENCES activities(project_id),
    registration_start DATE,
    registration_end DATE,
    description TEXT,
    requirements TEXT,
    org_description TEXT,
    benefits VARCHAR(100),
    attachment_name VARCHAR(200),
    attachment_url TEXT,
    contact_person VARCHAR(100),
    contact_phone VARCHAR(100)
);

-- ==========================================
-- 3. 活动标签表
-- ==========================================
CREATE TABLE IF NOT EXISTS activity_tags (
    id SERIAL PRIMARY KEY,
    project_id VARCHAR(20) NOT NULL REFERENCES activities(project_id),
    tag_type VARCHAR(10) NOT NULL,
    tag_value VARCHAR(50) NOT NULL,
    UNIQUE (project_id, tag_type, tag_value)
);

CREATE INDEX IF NOT EXISTS idx_tags_project ON activity_tags(project_id);
CREATE INDEX IF NOT EXISTS idx_tags_type_value ON activity_tags(tag_type, tag_value);

-- ==========================================
-- 4. 用户表
-- ==========================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nickname VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- ==========================================
-- 5. 用户画像表
-- ==========================================
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id),
    major VARCHAR(100),
    grade VARCHAR(20),
    skills VARCHAR(500),
    province VARCHAR(50),
    city VARCHAR(50),
    preference VARCHAR(500),
    available_start DATE,
    available_end DATE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 6. 推荐历史表
-- ==========================================
CREATE TABLE IF NOT EXISTS recommendation_history (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id),
    profile_snapshot TEXT,
    result_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 7. 查询日志表
-- ==========================================
CREATE TABLE IF NOT EXISTS query_logs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100),
    user_profile TEXT,
    result_ids TEXT,
    queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 8. 活动全量视图（聚合标签）
-- ==========================================
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
    -- 智能拼接地区前缀（省份+市区+县城+原标题），避免重复
    -- province/city/district 存储时已去掉后缀，title 中可能带后缀
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
