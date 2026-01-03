"""
Neo4j数据库操作模块
提供用户认证和统计信息相关的数据库操作
"""

from datetime import datetime, timedelta
from neo4j import GraphDatabase

from config import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD
)

# 导入Redis工具函数和布隆过滤器
try:
    from redis_utils import (
        get_qr_login_status_cache,
        set_qr_login_status_cache,
        delete_qr_login_status_cache,
        delayed_delete_cache
    )
    from bloom_utils import is_cache_key_exists, is_cache_key_exists_with_warmup, mark_cache_key_exists
except ImportError:
    # 如果导入失败，使用空函数
    def get_qr_login_status_cache(username): return None
    def set_qr_login_status_cache(username, enabled): return False
    def delete_qr_login_status_cache(username): return False
    def delayed_delete_cache(username, delay_seconds=1.0): pass
    def is_cache_key_exists(key): return False
    def is_cache_key_exists_with_warmup(key, fallback_to_db=False): return (False, False)
    def mark_cache_key_exists(key): pass

# --- 初始化驱动 ---
try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("✅ Neo4j 数据库连接成功")
except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
    driver = None


def close_driver():
    """关闭数据库连接"""
    if driver:
        driver.close()


def get_user_by_email(email):
    """根据邮箱查找用户
    
    Args:
        email: 邮箱地址
        
    Returns:
        dict: 用户信息，如果不存在则返回None
    """
    with driver.session() as session:
        query = "MATCH (u:User {email: $email}) RETURN u.username as username, u.email as email"
        result = session.run(query, email=email).single()
        if result:
            return {
                "username": result["username"], 
                "email": result["email"]
            }
    return None



def create_user(user_id, username, password_hash, email, password_strength=2): # <--- 增加 user_id 参数
    """创建新用户
    
    Args:
        user_id: 雪花算法生成的唯一ID (String)
        username: 用户名
        ...
    """
    with driver.session() as session:
        # 1. 检查用户名是否存在
        check_user = "MATCH (u:User {username: $username}) RETURN u"
        if session.run(check_user, username=username).single():
            return "USERNAME_EXISTS"
        
        # 2. 检查邮箱是否存在
        check_email = "MATCH (u:User {email: $email}) RETURN u"
        if session.run(check_email, email=email).single():
            return "EMAIL_EXISTS"
        
        # 3. 创建新用户 (核心修改：添加 id 属性)
        query = """
        CREATE (u:User {
            id: $user_id,             // <--- 这里的 user_id 是最重要的唯一标识
            username: $username,
            password: $password,
            email: $email,
            password_strength: $password_strength,
            created_at: timestamp(),
            last_activity: timestamp(),
            request_count: 0,
            is_vip: false,
            avatar: "https://i.pravatar.cc/150?u=" + $user_id
        }) RETURN u
        """
        session.run(
            query, 
            user_id=user_id,          # <--- 传参
            username=username, 
            password=password_hash, 
            email=email, 
            password_strength=password_strength
        )
    return "SUCCESS"


def get_user(username):
    """获取用户信息（支持用户名或邮箱）

    Args:
        username: 用户名或邮箱

    Returns:
        dict: 用户信息，如果不存在则返回None
    """
    with driver.session() as session:
        query = """
        MATCH (u:User)
        WHERE u.username = $uid OR u.email = $uid
        RETURN u.id as id, u.username as username, u.password as password, u.email as email,
               u.last_activity as last_activity, u.created_at as created_at,
               u.request_count as request_count,
               u.twofa_enabled as twofa_enabled,
                u.twofa_filename as twofa_filename,  
               u.twofa_hash as twofa_hash,          
               u.password_strength as password_strength
        """
        result = session.run(query, uid=username).single()
        if result:
            return {
                "id": result.get("id", ""),
                "username": result["username"],
                "password": result["password"],
                "email": result.get("email", ""),
                "last_activity": result.get("last_activity"),
                "created_at": result.get("created_at"),
                "request_count": result.get("request_count", 0),
                "twofa_enabled": result.get("twofa_enabled", False) or False,
                "twofa_filename": result.get("twofa_filename", ""),
                "twofa_hash": result.get("twofa_hash", ""),
                "password_strength": result.get("password_strength", 2) or 2
            }
    return None

def get_user_by_id(user_id):
    """根据用户ID获取用户信息

    Args:
        user_id: 用户雪花ID

    Returns:
        dict: 用户信息，如果不存在则返回None
    """
    with driver.session() as session:
        query = """
        MATCH (u:User {id: $user_id})
        RETURN u.id as id, u.username as username, u.email as email,
               u.avatar as avatar, u.status as status,
               u.last_activity as last_activity, u.created_at as created_at
        """
        result = session.run(query, user_id=user_id).single()
        if result:
            return {
                "id": result.get("id", ""),
                "username": result["username"],
                "email": result.get("email", ""),
                "avatar": result.get("avatar", ""),
                "status": result.get("status", "offline"),
                "last_activity": result.get("last_activity"),
                "created_at": result.get("created_at")
            }
    return None

def set_user_2fa(username, enabled, filename, file_hash):
    """设置用户2FA状态及文件信息
    
    Args:
        username: 用户名
        enabled: 是否启用
        filename: 图片文件名
        file_hash: 图片哈希值
        
    Returns:
        bool: 操作是否成功
    """
    with driver.session() as session:
        query = """
        MATCH (u:User {username: $username})
        SET u.twofa_enabled = $enabled,
            u.twofa_filename = $filename,
            u.twofa_hash = $file_hash
        RETURN u.username as username
        """
        result = session.run(
            query, 
            username=username, 
            enabled=enabled, 
            filename=filename, 
            file_hash=file_hash
        ).single()
        return result is not None

def get_user_2fa_info(username):
    """获取用户2FA详细信息（用于删除旧文件等）
    
    Args:
        username: 用户名
        
    Returns:
        dict: 包含 filename 和 hash
    """
    with driver.session() as session:
        query = """
        MATCH (u:User {username: $username})
        RETURN u.twofa_filename as twofa_filename, u.twofa_hash as twofa_hash
        """
        result = session.run(query, username=username).single()
        if result:
            return {
                "twofa_filename": result.get("twofa_filename", ""),
                "twofa_hash": result.get("twofa_hash", "")
            }
    return {}


def update_last_activity(username):
    """更新用户的最后活动时间戳
    
    Args:
        username: 用户名
        
    Returns:
        bool: 更新是否成功
    """
    import time
    with driver.session() as session:
        current_timestamp = time.time() * 1000  # 转换为毫秒时间戳
        query = """
        MATCH (u:User {username: $username})
        SET u.last_activity = $timestamp
        RETURN u.username as username
        """
        result = session.run(query, username=username, timestamp=current_timestamp).single()
        return result is not None


def get_user_2fa_status(username):
    """获取用户2FA状态

    Args:
        username: 用户名

    Returns:
        bool: 2FA是否已启用
    """
    with driver.session() as session:
        query = """
        MATCH (u:User {username: $username})
        RETURN u.twofa_enabled as twofa_enabled
        """
        result = session.run(query, username=username).single()
        if result:
            return result.get("twofa_enabled", False) or False
    return False


def get_user_qr_login_status(username):
    """获取用户二维码登录启用状态（使用布隆过滤器优化缓存穿透防护，支持Warmup降级）

    Args:
        username: 用户名

    Returns:
        bool: 二维码登录是否已启用
    """
    cache_key = f"qr_login_status:{username}"
    
    # 第一步：使用布隆过滤器快速判断（支持Warmup降级）
    key_exists, used_db_fallback = is_cache_key_exists_with_warmup(
        cache_key, 
        fallback_to_db=True  # Warmup未完成时降级到数据库查询
    )
    
    # 如果使用了降级查询，直接返回结果
    if used_db_fallback:
        # 已经在降级查询中从数据库获取了结果并返回
        return key_exists
    
    # 布隆过滤器说不存在，说明缓存中肯定没有
    # 直接查数据库，避免缓存穿透
    if not key_exists:
        with driver.session() as session:
            query = """
            MATCH (u:User {username: $username})
            RETURN u.qr_login_enabled as qr_login_enabled
            """
            result = session.run(query, username=username).single()
            if result:
                enabled = result.get("qr_login_enabled", False) or False
                # 标记到布隆过滤器
                mark_cache_key_exists(cache_key)
                # 写入缓存
                set_qr_login_status_cache(username, enabled)
                return enabled
        return False
    
    # 第二步：布隆过滤器说可能存在，继续查缓存
    cached_status = get_qr_login_status_cache(username)
    if cached_status is not None:
        return cached_status
    
    # 第三步：缓存未命中，查数据库
    with driver.session() as session:
        query = """
        MATCH (u:User {username: $username})
        RETURN u.qr_login_enabled as qr_login_enabled
        """
        result = session.run(query, username=username).single()
        if result:
            enabled = result.get("qr_login_enabled", False) or False
            # 标记到布隆过滤器
            mark_cache_key_exists(cache_key)
            # 异步写入缓存（不阻塞返回）
            try:
                from database_async import db_manager
                # 使用线程池异步写入缓存，不等待结果
                db_manager.executor.submit(set_qr_login_status_cache, username, enabled)
            except Exception:
                # 如果异步写入失败，尝试同步写入（降级处理）
                set_qr_login_status_cache(username, enabled)
            return enabled
    
    return False


def get_all_users_qr_login_status():
    """获取所有用户的二维码登录状态

    Returns:
        list: 用户列表，每个元素为 (username, qr_login_enabled) 元组
    """
    if not driver:
        return []
    
    users = []
    with driver.session() as session:
        query = """
        MATCH (u:User)
        RETURN u.username as username, u.qr_login_enabled as qr_login_enabled
        """
        results = session.run(query)
        for record in results:
            username = record.get("username")
            enabled = record.get("qr_login_enabled", False) or False
            if username:
                users.append((username, enabled))
    return users


def set_user_qr_login_status(username, enabled):
    """设置用户二维码登录启用状态（使用延迟双删策略）

    延迟双删策略：
    1. 先删除缓存
    2. 更新数据库
    3. 延迟一段时间后再次删除缓存（确保数据库更新完成后的脏数据被清除）

    Args:
        username: 用户名
        enabled: 是否启用

    Returns:
        bool: 操作是否成功
    """
    # 第一步：先删除缓存（防止旧数据干扰）
    delete_qr_login_status_cache(username)

    # 第二步：更新数据库
    with driver.session() as session:
        query = """
        MATCH (u:User {username: $username})
        SET u.qr_login_enabled = $enabled
        RETURN u.username as username
        """
        result = session.run(query, username=username, enabled=enabled).single()
        if result is None:
            return False

    # 第三步：延迟删除缓存（延迟双删策略）
    # 延迟1秒后再次删除缓存，确保数据库更新完成后的脏数据被清除
    delayed_delete_cache(username, delay_seconds=1.0)

    return True






def delete_user(username):
    """删除用户账户

    Args:
        username: 用户名

    Returns:
        bool: 删除是否成功
    """
    with driver.session() as session:
        # 删除用户节点及其所有关系
        query = """
        MATCH (u:User {username: $username})
        DETACH DELETE u
        RETURN count(u) as deleted
        """
        result = session.run(query, username=username).single()
        return result and result["deleted"] > 0


def get_user_stats(username):
    """获取用户的统计信息，包括在线天数

    Args:
        username: 用户名

    Returns:
        dict: 用户统计信息
    """
    with driver.session() as session:
        query = """
        MATCH (u:User {username: $username})
        RETURN u.username as username, u.email as email,
               u.created_at as created_at, u.last_activity as last_activity,
               u.request_count as request_count, u.avatar as avatar,
               u.job_title as job_title, u.website as website, u.bio as bio,
               u.twofa_enabled as twofa_enabled 
        """
        result = session.run(query, username=username).single()
        if result:
            import time
            current_timestamp = time.time() * 1000  # 转换为毫秒
            created_at = result.get("created_at")
            request_count = result.get("request_count", 0)

            # 计算在线天数（从注册开始）
            online_days = 0
            if created_at:
                # 毫秒转天数，向上取整
                time_diff_ms = current_timestamp - created_at
                online_days = max(1, int((time_diff_ms / (1000 * 60 * 60 * 24)) + 0.999))

            return {
                "username": result["username"],
                "email": result.get("email", ""),
                "created_at": created_at,
                "last_activity": result.get("last_activity"),
                "request_count": request_count,
                "online_days": online_days,
                "avatar": result.get("avatar", ""),
                "job_title": result.get("job_title", ""),
                "website": result.get("website", ""),
                "bio": result.get("bio", ""),
                "twofa_enabled": result.get("twofa_enabled", False) or False
            }
    return None


def update_user_avatar(username, avatar_path):
    """更新用户头像路径

    Args:
        username: 用户名
        avatar_path: 头像文件路径

    Returns:
        bool: 更新是否成功
    """
    with driver.session() as session:
        query = """
        MATCH (u:User {username: $username})
        SET u.avatar = $avatar_path
        RETURN u.username as username
        """
        result = session.run(query, username=username, avatar_path=avatar_path).single()
        return result is not None


def update_user_profile(username, profile_data):
    """更新用户资料

    Args:
        username: 当前用户名
        profile_data: 资料数据字典，可包含:
            - new_username: 新用户名
            - email: 邮箱
            - job_title: 职位头衔
            - website: 个人网站
            - bio: 个人简介

    Returns:
        tuple: (成功标志, 错误信息或新用户名)
    """
    with driver.session() as session:
        new_username = profile_data.get("username", username)
        new_email = profile_data.get("email")

        # 如果要修改用户名，检查新用户名是否已存在
        if new_username != username:
            check_query = "MATCH (u:User {username: $new_username}) RETURN u"
            if session.run(check_query, new_username=new_username).single():
                return False, "用户名已被占用"

        # 如果要修改邮箱，检查新邮箱是否已存在
        if new_email:
            check_email_query = """
            MATCH (u:User {email: $email})
            WHERE u.username <> $username
            RETURN u
            """
            if session.run(check_email_query, email=new_email, username=username).single():
                return False, "邮箱已被占用"

        # 构建更新语句
        update_query = """
        MATCH (u:User {username: $username})
        SET u.username = $new_username,
            u.email = COALESCE($email, u.email),
            u.job_title = $job_title,
            u.website = $website,
            u.bio = $bio
        RETURN u.username as username
        """

        result = session.run(
            update_query,
            username=username,
            new_username=new_username,
            email=new_email,
            job_title=profile_data.get("job_title", ""),
            website=profile_data.get("website", ""),
            bio=profile_data.get("bio", "")
        ).single()

        if result:
            return True, result["username"]
        return False, "用户不存在"


def get_profile_completion(username):
    """计算用户资料完成度

    Args:
        username: 用户名

    Returns:
        int: 完成度百分比 (0-100)
    """
    user = get_user_stats(username)
    if not user:
        return 0

    # 定义字段权重
    fields = {
        "username": 20,
        "email": 20,
        "avatar": 20,
        "job_title": 15,
        "website": 10,
        "bio": 15
    }

    completion = 0
    for field, weight in fields.items():
        value = user.get(field, "")
        if value and str(value).strip():
            completion += weight

    return completion


def get_user_last_login_record(username):
    """获取用户最后一次登录记录的时间

    Args:
        username: 用户名

    Returns:
        int: 最后登录记录的时间戳（毫秒），如果没有记录则返回None
    """
    with driver.session() as session:
        query = """
        MATCH (u:User {username: $username})-[:HAS_LOGIN]->(l:LoginHistory)
        RETURN l.login_time as login_time
        ORDER BY l.login_time DESC
        LIMIT 1
        """
        result = session.run(query, username=username).single()
        if result:
            return result.get("login_time")
    return None


def create_login_record(username, ip, location, user_agent, login_time):
    """创建登录历史记录

    Args:
        username: 用户名
        ip: 登录IP地址
        location: 登录地点
        user_agent: 浏览器代理信息
        login_time: 登录时间戳（毫秒）

    Returns:
        bool: 创建是否成功
    """
    with driver.session() as session:
        query = """
        MATCH (u:User {username: $username})
        CREATE (l:LoginHistory {
            ip: $ip,
            location: $location,
            user_agent: $user_agent,
            login_time: $login_time
        })
        CREATE (u)-[:HAS_LOGIN]->(l)
        RETURN l
        """
        result = session.run(
            query,
            username=username,
            ip=ip,
            location=location,
            user_agent=user_agent,
            login_time=login_time
        ).single()
        return result is not None


def format_login_time(login_time_ms):
    """格式化登录时间显示
    
    Args:
        login_time_ms: 登录时间戳（毫秒）
    
    Returns:
        str: 格式化后的时间字符串（今天/昨天/前天/具体日期）
    """
    if not login_time_ms:
        return "未知时间"
    
    # 将毫秒时间戳转换为本地时区的datetime对象
    login_time = datetime.fromtimestamp(login_time_ms / 1000)
    now = datetime.now()
    
    # 获取今天的开始时间（00:00:00）
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    day_before_yesterday_start = yesterday_start - timedelta(days=1)
    
    # 获取登录日期的开始时间
    login_date_start = login_time.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 格式化时间部分
    hours = login_time.hour
    minutes = login_time.minute
    time_str = f"{hours:02d}:{minutes:02d}"
    
    # 判断是今天、昨天、前天还是更早
    if login_date_start >= today_start:
        return f"今天 {time_str}"
    elif login_date_start >= yesterday_start:
        return f"昨天 {time_str}"
    elif login_date_start >= day_before_yesterday_start:
        return f"前天 {time_str}"
    else:
        # 更早的日期，显示具体日期
        year = login_time.year
        month = login_time.month
        day = login_time.day
        
        # 如果是今年，不显示年份
        if year == now.year:
            return f"{month:02d}-{day:02d} {time_str}"
        else:
            return f"{year}-{month:02d}-{day:02d} {time_str}"


def get_login_history(username, limit=50):
    """获取用户登录历史记录

    Args:
        username: 用户名
        limit: 最大返回数量

    Returns:
        list: 登录历史记录列表
    """
    with driver.session() as session:
        query = """
        MATCH (u:User {username: $username})-[:HAS_LOGIN]->(l:LoginHistory)
        RETURN l.ip as ip, l.location as location,
               l.user_agent as user_agent, l.login_time as login_time
        ORDER BY l.login_time DESC
        LIMIT $limit
        """
        results = session.run(query, username=username, limit=limit)
        records = []
        for record in results:
            login_time = record.get("login_time")
            records.append({
                "ip": record.get("ip", ""),
                "location": record.get("location", "未知"),
                "user_agent": record.get("user_agent", ""),
                "login_time": login_time,
                "formatted_time": format_login_time(login_time)
            })
        return records


if __name__ == "__main__":
    if driver:
        print("数据库驱动已就绪")
    else:
        print("数据库驱动初始化失败")
