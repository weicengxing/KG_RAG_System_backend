"""
Redis工具模块
提供验证码存储和管理功能
"""

import json
import logging
import threading
from typing import Optional

import redis

from config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    REDIS_PASSWORD,
    VERIFICATION_CODE_EXPIRE_MINUTES
)


# ==================== 日志配置 ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Redis 连接 ====================

try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True  # 自动解码为字符串（用于文本数据）
    )
    # 测试连接
    redis_client.ping()
    logger.info(f"✅ Redis 连接成功: {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.error(f"❌ Redis 连接失败: {e}")
    redis_client = None

# ==================== 二进制数据专用Redis连接 ====================

try:
    redis_binary_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=False  # 不解码，保持bytes格式（用于二进制数据如布隆过滤器）
    )
    # 测试连接
    redis_binary_client.ping()
    logger.info(f"✅ Redis 二进制客户端连接成功: {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.error(f"❌ Redis 二进制客户端连接失败: {e}")
    redis_binary_client = None


# ==================== 验证码前缀 ====================

VERIFICATION_CODE_PREFIX = "verify_code:"
FORGOT_PASSWORD_CODE_PREFIX = "forgot_password_code:"


# ==================== 验证码操作函数 ====================

def save_verification_code(email: str, code: str) -> bool:
    """保存验证码到Redis

    Args:
        email: 邮箱地址
        code: 验证码

    Returns:
        bool: 是否保存成功
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法保存验证码")
        return False

    try:
        key = f"{VERIFICATION_CODE_PREFIX}{email}"
        expire_seconds = VERIFICATION_CODE_EXPIRE_MINUTES * 60

        # 使用 SETEX 设置带过期时间的键值
        redis_client.setex(key, expire_seconds, code)
        logger.info(f"✅ 验证码已保存: {email} (过期时间: {expire_seconds}秒)")
        return True

    except Exception as e:
        logger.error(f"❌ 保存验证码失败: {email}, 错误: {e}")
        return False


def get_verification_code(email: str) -> Optional[str]:
    """获取验证码

    Args:
        email: 邮箱地址

    Returns:
        Optional[str]: 验证码，不存在或已过期返回None
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法获取验证码")
        return None

    try:
        key = f"{VERIFICATION_CODE_PREFIX}{email}"
        code = redis_client.get(key)
        return code

    except Exception as e:
        logger.error(f"❌ 获取验证码失败: {email}, 错误: {e}")
        return None


def delete_verification_code(email: str) -> bool:
    """删除验证码（验证成功后调用）

    Args:
        email: 邮箱地址

    Returns:
        bool: 是否删除成功
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法删除验证码")
        return False

    try:
        key = f"{VERIFICATION_CODE_PREFIX}{email}"
        redis_client.delete(key)
        logger.info(f"🗑️ 验证码已删除: {email}")
        return True

    except Exception as e:
        logger.error(f"❌ 删除验证码失败: {email}, 错误: {e}")
        return False


def verify_code(email: str, code: str) -> tuple[bool, str]:
    """验证验证码

    Args:
        email: 邮箱地址
        code: 用户输入的验证码

    Returns:
        tuple[bool, str]: (是否验证成功, 错误信息)
    """
    stored_code = get_verification_code(email)

    if stored_code is None:
        return False, "请先获取验证码"

    if stored_code != code:
        return False, "验证码错误"

    return True, ""


def get_code_ttl(email: str) -> int:
    """获取验证码剩余有效时间

    Args:
        email: 邮箱地址

    Returns:
        int: 剩余秒数，-1表示不存在，-2表示无过期时间
    """
    if not redis_client:
        return -1

    try:
        key = f"{VERIFICATION_CODE_PREFIX}{email}"
        return redis_client.ttl(key)

    except Exception:
        return -1


def is_redis_available() -> bool:
    """检查Redis是否可用

    Returns:
        bool: Redis是否可用
    """
    if not redis_client:
        return False

    try:
        redis_client.ping()
        return True
    except Exception:
        return False


# ==================== 忘记密码验证码相关 ====================

def save_forgot_password_code(email: str, code: str) -> bool:
    """保存忘记密码验证码到Redis

    Args:
        email: 邮箱地址
        code: 验证码

    Returns:
        bool: 是否保存成功
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法保存验证码")
        return False

    try:
        key = f"{FORGOT_PASSWORD_CODE_PREFIX}{email}"
        expire_seconds = VERIFICATION_CODE_EXPIRE_MINUTES * 60

        # 使用 SETEX 设置带过期时间的键值
        redis_client.setex(key, expire_seconds, code)
        logger.info(f"✅ 忘记密码验证码已保存: {email} (过期时间: {expire_seconds}秒)")
        return True

    except Exception as e:
        logger.error(f"❌ 保存忘记密码验证码失败: {email}, 错误: {e}")
        return False


def get_forgot_password_code(email: str) -> Optional[str]:
    """获取忘记密码验证码

    Args:
        email: 邮箱地址

    Returns:
        Optional[str]: 验证码，不存在或已过期返回None
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法获取验证码")
        return None

    try:
        key = f"{FORGOT_PASSWORD_CODE_PREFIX}{email}"
        code = redis_client.get(key)
        return code

    except Exception as e:
        logger.error(f"❌ 获取忘记密码验证码失败: {email}, 错误: {e}")
        return None


def verify_forgot_password_code(email: str, code: str) -> tuple[bool, str]:
    """验证忘记密码验证码

    Args:
        email: 邮箱地址
        code: 用户输入的验证码

    Returns:
        tuple[bool, str]: (是否验证成功, 错误信息)
    """
    stored_code = get_forgot_password_code(email)

    if stored_code is None:
        return False, "验证码不存在或已过期，请重新获取"

    if stored_code != code:
        return False, "验证码错误"

    return True, ""


def delete_forgot_password_code(email: str) -> bool:
    """删除忘记密码验证码（验证成功后调用）

    Args:
        email: 邮箱地址

    Returns:
        bool: 是否删除成功
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法删除验证码")
        return False

    try:
        key = f"{FORGOT_PASSWORD_CODE_PREFIX}{email}"
        redis_client.delete(key)
        logger.info(f"🗑️ 忘记密码验证码已删除: {email}")
        return True

    except Exception as e:
        logger.error(f"❌ 删除忘记密码验证码失败: {email}, 错误: {e}")
        return False


# ==================== 二维码登录相关 ====================

QR_LOGIN_PREFIX = "qr_login:"
QR_LOGIN_EXPIRE_SECONDS = 300  # 二维码5分钟有效


def create_qr_session(qr_id: str) -> bool:
    """创建二维码登录会话

    Args:
        qr_id: 二维码唯一ID

    Returns:
        bool: 是否创建成功
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法创建二维码会话")
        return False

    try:
        key = f"{QR_LOGIN_PREFIX}{qr_id}"
        # 初始状态: pending (等待扫码)
        data = json.dumps({"status": "pending", "username": None, "token": None})
        redis_client.setex(key, QR_LOGIN_EXPIRE_SECONDS, data)
        logger.info(f"✅ 二维码会话已创建: {qr_id}")
        return True

    except Exception as e:
        logger.error(f"❌ 创建二维码会话失败: {qr_id}, 错误: {e}")
        return False


def get_qr_session(qr_id: str) -> Optional[dict]:
    """获取二维码登录会话状态

    Args:
        qr_id: 二维码唯一ID

    Returns:
        Optional[dict]: 会话数据，不存在返回None
    """
    if not redis_client:
        return None

    try:
        key = f"{QR_LOGIN_PREFIX}{qr_id}"
        data = redis_client.get(key)
        if data:
            return json.loads(data)
        return None

    except Exception as e:
        logger.error(f"❌ 获取二维码会话失败: {qr_id}, 错误: {e}")
        return None


def confirm_qr_login(qr_id: str, username: str, token: str) -> bool:
    """确认二维码登录（手机端调用）

    Args:
        qr_id: 二维码唯一ID
        username: 登录的用户名
        token: 生成的访问令牌

    Returns:
        bool: 是否确认成功
    """
    if not redis_client:
        return False

    try:
        key = f"{QR_LOGIN_PREFIX}{qr_id}"

        # 检查会话是否存在
        if not redis_client.exists(key):
            logger.warning(f"⚠️ 二维码会话不存在或已过期: {qr_id}")
            return False

        # 获取剩余过期时间
        ttl = redis_client.ttl(key)
        if ttl <= 0:
            return False

        # 更新状态为已确认
        data = json.dumps({
            "status": "confirmed",
            "username": username,
            "token": token
        })
        redis_client.setex(key, ttl, data)
        logger.info(f"✅ 二维码登录已确认: {qr_id}, 用户: {username}")
        return True

    except Exception as e:
        logger.error(f"❌ 确认二维码登录失败: {qr_id}, 错误: {e}")
        return False


def delete_qr_session(qr_id: str) -> bool:
    """删除二维码会话（登录完成后调用）

    Args:
        qr_id: 二维码唯一ID

    Returns:
        bool: 是否删除成功
    """
    if not redis_client:
        return False

    try:
        key = f"{QR_LOGIN_PREFIX}{qr_id}"
        redis_client.delete(key)
        logger.info(f"🗑️ 二维码会话已删除: {qr_id}")
        return True

    except Exception as e:
        logger.error(f"❌ 删除二维码会话失败: {qr_id}, 错误: {e}")
        return False


# ==================== 二维码登录状态缓存相关 ====================

QR_LOGIN_STATUS_PREFIX = "qr_login_status:"
QR_LOGIN_STATUS_EXPIRE_SECONDS = 3600  # 缓存1小时


def get_qr_login_status_cache(username: str) -> Optional[bool]:
    """从Redis获取用户二维码登录状态缓存

    Args:
        username: 用户名

    Returns:
        Optional[bool]: 缓存的状态值，不存在返回None
    """
    if not redis_client:
        return None

    try:
        key = f"{QR_LOGIN_STATUS_PREFIX}{username}"
        value = redis_client.get(key)
        if value is not None:
            # 将字符串转换为布尔值
            return value.lower() == "true"
        return None

    except Exception as e:
        logger.error(f"❌ 获取二维码登录状态缓存失败: {username}, 错误: {e}")
        return None


def set_qr_login_status_cache(username: str, enabled: bool) -> bool:
    """设置用户二维码登录状态缓存

    Args:
        username: 用户名
        enabled: 是否启用

    Returns:
        bool: 是否设置成功
    """
    if not redis_client:
        return False

    try:
        key = f"{QR_LOGIN_STATUS_PREFIX}{username}"
        value = "true" if enabled else "false"
        redis_client.setex(key, QR_LOGIN_STATUS_EXPIRE_SECONDS, value)
        logger.info(f"✅ 二维码登录状态缓存已设置: {username} = {enabled}")
        return True

    except Exception as e:
        logger.error(f"❌ 设置二维码登录状态缓存失败: {username}, 错误: {e}")
        return False


def delete_qr_login_status_cache(username: str) -> bool:
    """删除用户二维码登录状态缓存

    Args:
        username: 用户名

    Returns:
        bool: 是否删除成功
    """
    if not redis_client:
        return False

    try:
        key = f"{QR_LOGIN_STATUS_PREFIX}{username}"
        redis_client.delete(key)
        logger.info(f"🗑️ 二维码登录状态缓存已删除: {username}")
        return True

    except Exception as e:
        logger.error(f"❌ 删除二维码登录状态缓存失败: {username}, 错误: {e}")
        return False


def batch_set_qr_login_status_cache(users: list[tuple[str, bool]]) -> int:
    """批量设置用户二维码登录状态缓存（使用Redis Pipeline）

    Args:
        users: 用户列表，每个元素为 (username, enabled) 元组

    Returns:
        int: 成功写入的数量
    """
    if not redis_client:
        return 0

    if not users:
        return 0

    try:
        # 使用 Pipeline 批量写入
        pipe = redis_client.pipeline()
        
        for username, enabled in users:
            key = f"{QR_LOGIN_STATUS_PREFIX}{username}"
            value = "true" if enabled else "false"
            pipe.setex(key, QR_LOGIN_STATUS_EXPIRE_SECONDS, value)
        
        # 执行所有命令
        pipe.execute()
        
        logger.info(f"✅ 批量写入二维码登录状态缓存完成，共 {len(users)} 个用户")
        return len(users)

    except Exception as e:
        logger.error(f"❌ 批量写入二维码登录状态缓存失败: {e}")
        return 0


def delayed_delete_cache(username: str, delay_seconds: float = 0.3):
    """延迟删除缓存（用于延迟双删策略）

    Args:
        username: 用户名
        delay_seconds: 延迟秒数，默认0.3秒
    """
    def _delete():
        import time
        time.sleep(delay_seconds)
        delete_qr_login_status_cache(username)
        logger.info(f"⏰ 延迟删除缓存完成: {username}")

    thread = threading.Thread(target=_delete, daemon=True)
    thread.start()


# ==================== 分布式锁相关 ====================

DISTRIBUTED_LOCK_PREFIX = "dist_lock:"


class RedisDistributedLock:
    """Redis分布式锁
    
    使用Redis实现分布式锁，支持自动续期和锁竞争
    """
    
    def __init__(self, lock_name: str, expire_time: int = 30, auto_renew: bool = True):
        """初始化分布式锁
        
        Args:
            lock_name: 锁名称
            expire_time: 锁过期时间（秒），默认30秒
            auto_renew: 是否自动续期，默认True
        """
        self.lock_name = lock_name
        self.expire_time = expire_time
        self.auto_renew = auto_renew
        self.lock_key = f"{DISTRIBUTED_LOCK_PREFIX}{lock_name}"
        self.lock_value = None
        self.renew_thread = None
        self._stop_renew = threading.Event()
    
    def acquire(self, timeout: int = 10) -> bool:
        """获取分布式锁
        
        Args:
            timeout: 获取锁的超时时间（秒），默认10秒
        
        Returns:
            bool: 是否成功获取锁
        """
        if not redis_client:
            logger.error("❌ Redis 未连接，无法获取分布式锁")
            return False
        
        import uuid
        import time
        
        self.lock_value = str(uuid.uuid4())
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # 使用SETNX命令尝试获取锁
                if redis_client.setnx(self.lock_key, self.lock_value):
                    # 获取成功，设置过期时间
                    redis_client.expire(self.lock_key, self.expire_time)
                    logger.info(f"🔒 分布式锁获取成功: {self.lock_name}")
                    
                    # 如果需要自动续期，启动续期线程
                    if self.auto_renew:
                        self._start_renew_thread()
                    
                    return True
                
                # 锁已被占用，等待重试
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ 获取分布式锁失败: {self.lock_name}, 错误: {e}")
                time.sleep(0.5)
        
        logger.warning(f"⚠️ 获取分布式锁超时: {self.lock_name}, 超时时间: {timeout}秒")
        return False
    
    def _start_renew_thread(self):
        """启动锁续期线程"""
        def renew_lock():
            renew_interval = self.expire_time / 3  # 每1/3过期时间续期一次
            while not self._stop_renew.is_set():
                try:
                    # 检查锁是否仍然属于当前实例
                    current_value = redis_client.get(self.lock_key)
                    if current_value == self.lock_value:
                        # 续期锁
                        redis_client.expire(self.lock_key, self.expire_time)
                        logger.debug(f"🔄 分布式锁续期: {self.lock_name}")
                    else:
                        # 锁已不属于当前实例，停止续期
                        logger.warning(f"⚠️ 分布式锁所有权已变更: {self.lock_name}")
                        break
                    
                    # 等待下次续期
                    time.sleep(renew_interval)
                except Exception as e:
                    logger.error(f"❌ 分布式锁续期失败: {self.lock_name}, 错误: {e}")
                    break
        
        self.renew_thread = threading.Thread(target=renew_lock, daemon=True)
        self.renew_thread.start()
        logger.info(f"🔄 启动分布式锁自动续期: {self.lock_name}")
    
    def release(self) -> bool:
        """释放分布式锁
        
        Returns:
            bool: 是否成功释放锁
        """
        if not redis_client:
            logger.error("❌ Redis 未连接，无法释放分布式锁")
            return False
        
        # 停止续期线程
        if self.renew_thread:
            self._stop_renew.set()
            self.renew_thread.join(timeout=1.0)
        
        try:
            # 使用Lua脚本确保原子性：只有锁的值匹配时才删除
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            
            result = redis_client.eval(lua_script, 1, self.lock_key, self.lock_value)
            
            if result == 1:
                logger.info(f"🔓 分布式锁释放成功: {self.lock_name}")
                return True
            else:
                logger.warning(f"⚠️ 分布式锁释放失败（锁值不匹配或已过期）: {self.lock_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 释放分布式锁失败: {self.lock_name}, 错误: {e}")
            return False
    
    def __enter__(self):
        """上下文管理器入口"""
        if not self.acquire():
            raise RuntimeError(f"无法获取分布式锁: {self.lock_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()


def acquire_distributed_lock(lock_name: str, expire_time: int = 30, timeout: int = 10) -> Optional[RedisDistributedLock]:
    """获取分布式锁（快捷函数）

    Args:
        lock_name: 锁名称
        expire_time: 锁过期时间（秒）
        timeout: 获取锁的超时时间（秒）

    Returns:
        Optional[RedisDistributedLock]: 成功返回锁对象，失败返回None
    """
    lock = RedisDistributedLock(lock_name, expire_time)
    if lock.acquire(timeout):
        return lock
    return None


# ==================== 对话历史管理相关 ====================

CONVERSATION_HISTORY_PREFIX = "conversation_history:"
CONVERSATION_HISTORY_EXPIRE_SECONDS = 3600 * 2  # 对话历史保存2小时


def save_conversation_message(conversation_id: str, role: str, content: str) -> bool:
    """保存一条对话消息到Redis

    Args:
        conversation_id: 对话ID
        role: 角色 (user/assistant)
        content: 消息内容

    Returns:
        bool: 是否保存成功
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法保存对话消息")
        return False

    try:
        key = f"{CONVERSATION_HISTORY_PREFIX}{conversation_id}"

        # 获取当前历史记录
        history_json = redis_client.get(key)
        if history_json:
            history = json.loads(history_json)
        else:
            history = []

        # 添加新消息
        history.append({
            "role": role,
            "content": content
        })

        # 只保留最近20条消息（10轮对话）
        if len(history) > 20:
            history = history[-20:]

        # 保存到Redis
        redis_client.setex(key, CONVERSATION_HISTORY_EXPIRE_SECONDS, json.dumps(history, ensure_ascii=False))
        logger.info(f"✅ 对话消息已保存: {conversation_id}, role: {role}")
        return True

    except Exception as e:
        logger.error(f"❌ 保存对话消息失败: {conversation_id}, 错误: {e}")
        return False


def get_conversation_history(conversation_id: str) -> list:
    """获取对话历史

    Args:
        conversation_id: 对话ID

    Returns:
        list: 对话历史，格式为 [{"role": "user", "content": "..."}, ...]
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法获取对话历史")
        return []

    try:
        key = f"{CONVERSATION_HISTORY_PREFIX}{conversation_id}"
        history_json = redis_client.get(key)

        if history_json:
            history = json.loads(history_json)
            logger.info(f"✅ 获取对话历史: {conversation_id}, 共 {len(history)} 条消息")
            return history
        else:
            logger.info(f"📝 对话历史不存在，新建对话: {conversation_id}")
            return []

    except Exception as e:
        logger.error(f"❌ 获取对话历史失败: {conversation_id}, 错误: {e}")
        return []


def clear_conversation_history(conversation_id: str) -> bool:
    """清除对话历史

    Args:
        conversation_id: 对话ID

    Returns:
        bool: 是否清除成功
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法清除对话历史")
        return False

    try:
        key = f"{CONVERSATION_HISTORY_PREFIX}{conversation_id}"
        redis_client.delete(key)
        logger.info(f"🗑️ 对话历史已清除: {conversation_id}")
        return True

    except Exception as e:
        logger.error(f"❌ 清除对话历史失败: {conversation_id}, 错误: {e}")
        return False


# ==================== 音乐播放统计相关 ====================

MUSIC_PLAY_COUNT_PREFIX = "music:play_count:"
MUSIC_USER_HISTORY_PREFIX = "music:user:history:"
MUSIC_TRENDING_PREFIX = "music:trending:hot"
MUSIC_LAST_PLAY_PREFIX = "music:last_play:"  # 歌曲最后播放时间
MUSIC_UNIQUE_USERS_PREFIX = "music:unique_users:"  # 歌曲独立用户集合
MUSIC_RANK_HISTORY_QUEUE = "music:rank_history_queue"  # 排名历史快照队列（使用 Redis List）

# 过期时间设置
DAILY_EXPIRE_SECONDS = 30 * 24 * 60 * 60  # 30天
WEEKLY_EXPIRE_SECONDS = 90 * 24 * 60 * 60  # 90天
MONTHLY_EXPIRE_SECONDS = 365 * 24 * 60 * 60  # 365天
USER_HISTORY_EXPIRE_SECONDS = 30 * 24 * 60 * 60  # 30天
TRENDING_EXPIRE_SECONDS = 6 * 60 * 60  # 优化：增加到6小时，避免定时任务停止后数据过早消失


def get_current_time_keys():
    """获取当前时间的 key 后缀

    Returns:
        dict: 包含 daily, weekly, monthly 的 key 后缀
    """
    from datetime import datetime
    now = datetime.now()
    return {
        "daily": now.strftime("%Y%m%d"),  # 例如: 20260104
        "weekly": now.strftime("%Y%W"),   # 例如: 202601 (年份+周数)
        "monthly": now.strftime("%Y%m")   # 例如: 202601
    }


def increment_music_play_count(song_id: int, username: str = None) -> bool:
    """增加音乐播放计数（优化版：同时记录最后播放时间和独立用户）

    Args:
        song_id: 歌曲ID
        username: 用户名（必须，用于统计独立播放用户）

    Returns:
        bool: 是否成功
    
    Raises:
        ValueError: 当 username 为 None 时抛出异常（方案2修复）
    """
    # 验证 username 是否提供（方案2修复）
    if username is None:
        logger.error(f"❌ username 必须提供，用于统计独立播放用户: song_id={song_id}")
        raise ValueError("username 必须提供，用于统计独立播放用户。请确保在播放时传入用户名。")
    
    if not redis_client:
        logger.error("❌ Redis 未连接，无法增加播放计数")
        return False

    try:
        time_keys = get_current_time_keys()
        import time
        current_timestamp = int(time.time() * 1000)
        
        pipe = redis_client.pipeline()

        # 1. 全局播放计数（永久）
        pipe.zincrby(f"{MUSIC_PLAY_COUNT_PREFIX}global", 1, str(song_id))

        # 2. 每日播放计数（30天过期）
        daily_key = f"{MUSIC_PLAY_COUNT_PREFIX}daily:{time_keys['daily']}"
        pipe.zincrby(daily_key, 1, str(song_id))
        pipe.expire(daily_key, DAILY_EXPIRE_SECONDS)

        # 3. 每周播放计数（90天过期）
        weekly_key = f"{MUSIC_PLAY_COUNT_PREFIX}weekly:{time_keys['weekly']}"
        pipe.zincrby(weekly_key, 1, str(song_id))
        pipe.expire(weekly_key, WEEKLY_EXPIRE_SECONDS)

        # 4. 每月播放计数（365天过期）
        monthly_key = f"{MUSIC_PLAY_COUNT_PREFIX}monthly:{time_keys['monthly']}"
        pipe.zincrby(monthly_key, 1, str(song_id))
        pipe.expire(monthly_key, MONTHLY_EXPIRE_SECONDS)

        # 5. 记录歌曲最后播放时间（新优化）
        last_play_key = f"{MUSIC_LAST_PLAY_PREFIX}{song_id}"
        pipe.set(last_play_key, current_timestamp)
        pipe.expire(last_play_key, DAILY_EXPIRE_SECONDS)

        # 6. 用户播放历史和独立用户统计（如果提供了用户名）
        if username:
            user_history_key = f"{MUSIC_USER_HISTORY_PREFIX}{username}"
            # 使用当前时间戳作为分数，以便按时间排序
            pipe.zadd(user_history_key, {str(song_id): current_timestamp})
            pipe.expire(user_history_key, USER_HISTORY_EXPIRE_SECONDS)

            # 记录独立用户（使用Set，自动去重）
            unique_users_key = f"{MUSIC_UNIQUE_USERS_PREFIX}{song_id}"
            pipe.sadd(unique_users_key, username)
            pipe.expire(unique_users_key, DAILY_EXPIRE_SECONDS)

        # 执行所有命令
        pipe.execute()

        logger.info(f"✅ 播放计数已更新: song_id={song_id}, user={username}")
        return True

    except Exception as e:
        logger.error(f"❌ 增加播放计数失败: song_id={song_id}, 错误: {e}")
        return False


def get_music_rankings(limit: int = 100, time_range: str = "all") -> list:
    """获取音乐排行榜

    Args:
        limit: 返回的歌曲数量
        time_range: 时间范围 (all/daily/weekly/monthly)

    Returns:
        list: 排行榜列表，格式为 [{"song_id": int, "play_count": int, "rank": int}, ...]
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法获取排行榜")
        return []

    try:
        # 根据时间范围选择 key
        if time_range == "daily":
            time_keys = get_current_time_keys()
            key = f"{MUSIC_PLAY_COUNT_PREFIX}daily:{time_keys['daily']}"
        elif time_range == "weekly":
            time_keys = get_current_time_keys()
            key = f"{MUSIC_PLAY_COUNT_PREFIX}weekly:{time_keys['weekly']}"
        elif time_range == "monthly":
            time_keys = get_current_time_keys()
            key = f"{MUSIC_PLAY_COUNT_PREFIX}monthly:{time_keys['monthly']}"
        else:  # all
            key = f"{MUSIC_PLAY_COUNT_PREFIX}global"

        # 使用 ZREVRANGE 获取排行榜（从高到低）
        # withscores=True 返回分数（播放次数）
        result = redis_client.zrevrange(key, 0, limit - 1, withscores=True)

        # 格式化结果
        rankings = []
        for rank, (song_id, play_count) in enumerate(result, start=1):
            rankings.append({
                "song_id": int(song_id),
                "play_count": int(play_count),
                "rank": rank
            })

        logger.info(f"✅ 获取排行榜成功: time_range={time_range}, count={len(rankings)}")
        return rankings

    except Exception as e:
        logger.error(f"❌ 获取排行榜失败: time_range={time_range}, 错误: {e}")
        return []


def get_song_play_count(song_id: int, time_range: str = "all") -> int:
    """获取单曲播放次数

    Args:
        song_id: 歌曲ID
        time_range: 时间范围 (all/daily/weekly/monthly)

    Returns:
        int: 播放次数
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法获取播放次数")
        return 0

    try:
        # 根据时间范围选择 key
        if time_range == "daily":
            time_keys = get_current_time_keys()
            key = f"{MUSIC_PLAY_COUNT_PREFIX}daily:{time_keys['daily']}"
        elif time_range == "weekly":
            time_keys = get_current_time_keys()
            key = f"{MUSIC_PLAY_COUNT_PREFIX}weekly:{time_keys['weekly']}"
        elif time_range == "monthly":
            time_keys = get_current_time_keys()
            key = f"{MUSIC_PLAY_COUNT_PREFIX}monthly:{time_keys['monthly']}"
        else:  # all
            key = f"{MUSIC_PLAY_COUNT_PREFIX}global"

        # 使用 ZSCORE 获取分数（播放次数）
        score = redis_client.zscore(key, str(song_id))
        play_count = int(score) if score else 0

        return play_count

    except Exception as e:
        logger.error(f"❌ 获取播放次数失败: song_id={song_id}, 错误: {e}")
        return 0


def get_user_play_history(username: str, limit: int = 50) -> list:
    """获取用户播放历史

    Args:
        username: 用户名
        limit: 返回的歌曲数量

    Returns:
        list: 播放历史列表，格式为 [{"song_id": int, "played_at": int}, ...]
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法获取播放历史")
        return []

    try:
        key = f"{MUSIC_USER_HISTORY_PREFIX}{username}"

        # 使用 ZREVRANGE 获取最近播放（从新到旧）
        result = redis_client.zrevrange(key, 0, limit - 1, withscores=True)

        # 格式化结果
        history = []
        for song_id, timestamp in result:
            history.append({
                "song_id": int(song_id),
                "played_at": int(timestamp)
            })

        logger.info(f"✅ 获取播放历史成功: username={username}, count={len(history)}")
        return history

    except Exception as e:
        logger.error(f"❌ 获取播放历史失败: username={username}, 错误: {e}")
        return []


def get_trending_songs(limit: int = 20) -> list:
    """获取实时热门趋势

    Args:
        limit: 返回的歌曲数量

    Returns:
        list: 热门歌曲列表，格式为 [{"song_id": int, "hotness": float, "rank": int}, ...]
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法获取热门趋势")
        return []

    try:
        key = MUSIC_TRENDING_PREFIX

        # 使用 ZREVRANGE 获取热门趋势（从高到低）
        result = redis_client.zrevrange(key, 0, limit - 1, withscores=True)

        # 格式化结果
        trending = []
        for rank, (song_id, hotness) in enumerate(result, start=1):
            trending.append({
                "song_id": int(song_id),
                "hotness": float(hotness),
                "rank": rank
            })

        logger.info(f"✅ 获取热门趋势成功: count={len(trending)}")
        return trending

    except Exception as e:
        logger.error(f"❌ 获取热门趋势失败: 错误: {e}")
        return []


def update_trending_hotness(song_id: int, hotness: float) -> bool:
    """更新歌曲的热门趋势分数（供 Flink/Kafka 调用）

    Args:
        song_id: 歌曲ID
        hotness: 热度分数

    Returns:
        bool: 是否成功
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法更新热门趋势")
        return False

    try:
        key = MUSIC_TRENDING_PREFIX

        # 使用 ZADD 更新热度分数
        redis_client.zadd(key, {str(song_id): hotness})
        redis_client.expire(key, TRENDING_EXPIRE_SECONDS)

        logger.info(f"✅ 热门趋势已更新: song_id={song_id}, hotness={hotness}")
        return True

    except Exception as e:
        logger.error(f"❌ 更新热门趋势失败: song_id={song_id}, 错误: {e}")
        return False


def get_song_last_play_time(song_id: int) -> int:
    """获取歌曲最后播放时间（新优化）

    Args:
        song_id: 歌曲ID

    Returns:
        int: 最后播放时间（毫秒时间戳），不存在返回0
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法获取最后播放时间")
        return 0

    try:
        key = f"{MUSIC_LAST_PLAY_PREFIX}{song_id}"
        timestamp = redis_client.get(key)
        return int(timestamp) if timestamp else 0

    except Exception as e:
        logger.error(f"❌ 获取最后播放时间失败: song_id={song_id}, 错误: {e}")
        return 0


def get_song_unique_user_count(song_id: int) -> int:
    """获取歌曲的独立用户数（新优化）

    Args:
        song_id: 歌曲ID

    Returns:
        int: 独立用户数
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法获取独立用户数")
        return 0

    try:
        key = f"{MUSIC_UNIQUE_USERS_PREFIX}{song_id}"
        count = redis_client.scard(key)
        return count

    except Exception as e:
        logger.error(f"❌ 获取独立用户数失败: song_id={song_id}, 错误: {e}")
        return 0


def push_rank_snapshot_to_queue(snapshot: dict) -> bool:
    """将排名快照推送到队列头部
    
    每5分钟执行一次，将当前排名快照推送到队列头部。
    保持队列长度为300个元素（5分钟 * 300 = 25小时，足够对比1天前）。
    超过长度时，使用 ltrim 自动截断尾部最旧的数据。
    
    Args:
        snapshot: 快照数据，格式为 {"timestamp": int, "rankings": {song_id: rank}}
                  - timestamp: 毫秒时间戳
                  - rankings: 字典，key为song_id(str)，value为rank(int)
    
    Returns:
        bool: 是否成功推送
    """
    if not redis_client:
        logger.error("❌ Redis 未连接，无法推送排名快照")
        return False

    try:
        import json
        snapshot_json = json.dumps(snapshot, ensure_ascii=False)
        
        # 推送到队列头部
        redis_client.lpush(MUSIC_RANK_HISTORY_QUEUE, snapshot_json)
        
        # 保持队列长度为 300（5分钟 * 300 = 25小时）
        redis_client.ltrim(MUSIC_RANK_HISTORY_QUEUE, 0, 299)
        
        # 设置过期时间（30天）
        redis_client.expire(MUSIC_RANK_HISTORY_QUEUE, 30 * 24 * 60 * 60)
        
        logger.info(f"✅ 排名快照已推送到队列: timestamp={snapshot['timestamp']}")
        return True

    except Exception as e:
        logger.error(f"❌ 推送排名快照失败: {e}")
        return False


def get_rank_change(song_id: int, current_rank: int, compare_type: str = "update") -> dict:
    """获取歌曲的排名变化
    
    从排名历史队列中获取指定时间段的排名，计算排名变化。
    
    Args:
        song_id: 歌曲ID
        current_rank: 当前排名
        compare_type: 对比类型
            - "update": 对比5分钟前（默认）
            - "hourly": 对比1小时前
            - "daily": 对比1天前
    
    Returns:
        dict: 排名变化信息
            {
                "change": "up" | "down" | "same" | "new",
                "value": int,        // 变化值（正数=上升，负数=下降）
                "previous_rank": int // 上次排名
            }
    """
    if not redis_client:
        logger.warning("⚠️ Redis 未连接，返回默认排名变化")
        return {"change": "same", "value": 0, "previous_rank": current_rank}

    try:
        import json
        
        # 根据对比类型确定队列索引
        # 索引0是最新的快照，索引1是5分钟前的快照
        if compare_type == "hourly":
            index = 12  # 12个5分钟周期 = 1小时
        elif compare_type == "daily":
            index = 288  # 288个5分钟周期 = 24小时
        else:  # update
            index = 1  # 5分钟前
        
        # 从队列获取历史快照
        snapshot_list = redis_client.lrange(MUSIC_RANK_HISTORY_QUEUE, index, index)
        
        if not snapshot_list:
            # 没有历史数据，这是新歌曲
            return {"change": "new", "value": 0, "previous_rank": None}
        
        # 解析快照
        snapshot = json.loads(snapshot_list[0])
        previous_rank = snapshot["rankings"].get(str(song_id))
        
        if previous_rank is None:
            # 歌曲不在上次排名中，这是新上榜的歌曲
            return {"change": "new", "value": 0, "previous_rank": None}
        
        if previous_rank == current_rank:
            # 排名没有变化
            return {"change": "same", "value": 0, "previous_rank": previous_rank}
        else:
            # 计算排名变化
            rank_change = previous_rank - current_rank
            change_type = "up" if rank_change > 0 else "down"
            return {
                "change": change_type,
                "value": rank_change,
                "previous_rank": previous_rank
            }

    except Exception as e:
        logger.error(f"❌ 获取排名变化失败: song_id={song_id}, {e}")
        return {"change": "same", "value": 0, "previous_rank": current_rank}
