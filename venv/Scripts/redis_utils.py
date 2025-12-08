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
        decode_responses=True  # 自动解码为字符串
    )
    # 测试连接
    redis_client.ping()
    logger.info(f"✅ Redis 连接成功: {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.error(f"❌ Redis 连接失败: {e}")
    redis_client = None


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
