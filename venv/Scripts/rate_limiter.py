"""
Redis令牌桶限流模块
支持IP级别、接口级别和全局级别的限流
"""

import time
import logging
from typing import Optional, Tuple
from enum import Enum

import redis

from config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    REDIS_PASSWORD,
    # 限流配置
    RATE_LIMIT_IP_CAPACITY,
    RATE_LIMIT_IP_REFILL_RATE,
    RATE_LIMIT_ENDPOINT_CAPACITY,
    RATE_LIMIT_ENDPOINT_REFILL_RATE,
    RATE_LIMIT_GLOBAL_CAPACITY,
    RATE_LIMIT_GLOBAL_REFILL_RATE
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
        decode_responses=True
    )
    redis_client.ping()
    logger.info(f"✅ Redis 限流模块连接成功: {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.error(f"❌ Redis 限流模块连接失败: {e}")
    redis_client = None


# ==================== 限流类型枚举 ====================

class RateLimitType(Enum):
    """限流类型"""
    IP = "ip"           # IP级别限流
    ENDPOINT = "ep"     # 接口级别限流
    GLOBAL = "global"   # 全局限流


# ==================== 令牌桶键前缀 ====================

BUCKET_PREFIX = "rate_limit:"


# ==================== 令牌桶 Lua 脚本 ====================

# 使用Lua脚本保证原子性
TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

-- 获取当前桶状态
local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

-- 初始化桶（首次访问）
if tokens == nil then
    tokens = capacity
    last_refill = now
end

-- 计算需要补充的令牌
local elapsed = now - last_refill
local refill = elapsed * refill_rate
tokens = math.min(capacity, tokens + refill)

-- 尝试获取令牌
local allowed = 0
local remaining = tokens
local retry_after = 0

if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
    remaining = tokens
else
    -- 计算需要等待的时间
    retry_after = math.ceil((requested - tokens) / refill_rate)
end

-- 更新桶状态
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
-- 设置过期时间（防止内存泄漏）
redis.call('EXPIRE', key, 3600)

return {allowed, remaining, retry_after}
"""


# ==================== 令牌桶限流器 ====================

class TokenBucketRateLimiter:
    """令牌桶限流器"""

    def __init__(self):
        """初始化限流器"""
        self._script_sha = None
        if redis_client:
            try:
                # 预加载Lua脚本
                self._script_sha = redis_client.script_load(TOKEN_BUCKET_SCRIPT)
                logger.info("✅ 令牌桶Lua脚本加载成功")
            except Exception as e:
                logger.error(f"❌ Lua脚本加载失败: {e}")

    def _get_bucket_key(self, limit_type: RateLimitType, identifier: str) -> str:
        """生成桶的Redis键

        Args:
            limit_type: 限流类型
            identifier: 标识符（IP/接口路径等）

        Returns:
            str: Redis键
        """
        return f"{BUCKET_PREFIX}{limit_type.value}:{identifier}"

    def _get_config(self, limit_type: RateLimitType) -> Tuple[int, float]:
        """获取限流配置

        Args:
            limit_type: 限流类型

        Returns:
            Tuple[int, float]: (容量, 填充速率)
        """
        if limit_type == RateLimitType.IP:
            return RATE_LIMIT_IP_CAPACITY, RATE_LIMIT_IP_REFILL_RATE
        elif limit_type == RateLimitType.ENDPOINT:
            return RATE_LIMIT_ENDPOINT_CAPACITY, RATE_LIMIT_ENDPOINT_REFILL_RATE
        else:  # GLOBAL
            return RATE_LIMIT_GLOBAL_CAPACITY, RATE_LIMIT_GLOBAL_REFILL_RATE

    def is_allowed(
        self,
        limit_type: RateLimitType,
        identifier: str,
        tokens_requested: int = 1
    ) -> Tuple[bool, int, int]:
        """检查请求是否被允许

        Args:
            limit_type: 限流类型
            identifier: 标识符
            tokens_requested: 请求的令牌数

        Returns:
            Tuple[bool, int, int]: (是否允许, 剩余令牌, 重试等待秒数)
        """
        if not redis_client or not self._script_sha:
            # Redis不可用时放行
            logger.warning("⚠️ Redis不可用，限流器放行请求")
            return True, -1, 0

        key = self._get_bucket_key(limit_type, identifier)
        capacity, refill_rate = self._get_config(limit_type)
        now = time.time()

        try:
            result = redis_client.evalsha(
                self._script_sha,
                1,  # 键数量
                key,
                capacity,
                refill_rate,
                now,
                tokens_requested
            )

            allowed = bool(int(result[0]))
            remaining = int(float(result[1]))
            retry_after = int(result[2])

            if not allowed:
                logger.warning(
                    f"🚫 限流触发 [{limit_type.value}] {identifier}: "
                    f"剩余={remaining}, 等待={retry_after}s"
                )

            return allowed, remaining, retry_after

        except redis.exceptions.NoScriptError:
            # 脚本被清除，重新加载
            self._script_sha = redis_client.script_load(TOKEN_BUCKET_SCRIPT)
            return self.is_allowed(limit_type, identifier, tokens_requested)

        except Exception as e:
            logger.error(f"❌ 限流检查失败: {e}")
            return True, -1, 0  # 出错时放行

    def check_all_limits(
        self,
        client_ip: str,
        endpoint: str
    ) -> Tuple[bool, Optional[str], int, int]:
        """检查所有限流层级

        Args:
            client_ip: 客户端IP
            endpoint: 接口路径

        Returns:
            Tuple[bool, Optional[str], int, int]:
                (是否允许, 被限制的类型, 剩余令牌, 重试等待秒数)
        """
        # 1. 检查全局限流
        allowed, remaining, retry_after = self.is_allowed(
            RateLimitType.GLOBAL, "all"
        )
        if not allowed:
            return False, "global", remaining, retry_after

        # 2. 检查IP限流
        allowed, remaining, retry_after = self.is_allowed(
            RateLimitType.IP, client_ip
        )
        if not allowed:
            return False, "ip", remaining, retry_after

        # 3. 检查接口限流
        allowed, remaining, retry_after = self.is_allowed(
            RateLimitType.ENDPOINT, endpoint
        )
        if not allowed:
            return False, "endpoint", remaining, retry_after

        return True, None, remaining, 0

    def get_bucket_status(
        self,
        limit_type: RateLimitType,
        identifier: str
    ) -> Optional[dict]:
        """获取桶状态（用于调试）

        Args:
            limit_type: 限流类型
            identifier: 标识符

        Returns:
            Optional[dict]: 桶状态信息
        """
        if not redis_client:
            return None

        key = self._get_bucket_key(limit_type, identifier)
        try:
            data = redis_client.hgetall(key)
            if data:
                capacity, refill_rate = self._get_config(limit_type)
                return {
                    "key": key,
                    "tokens": float(data.get("tokens", 0)),
                    "last_refill": float(data.get("last_refill", 0)),
                    "capacity": capacity,
                    "refill_rate": refill_rate
                }
        except Exception as e:
            logger.error(f"❌ 获取桶状态失败: {e}")

        return None


# ==================== 全局限流器实例 ====================

rate_limiter = TokenBucketRateLimiter()


# ==================== 便捷函数 ====================

def check_rate_limit(client_ip: str, endpoint: str) -> Tuple[bool, Optional[str], int, int]:
    """检查限流（便捷函数）

    Args:
        client_ip: 客户端IP
        endpoint: 接口路径

    Returns:
        Tuple[bool, Optional[str], int, int]:
            (是否允许, 被限制的类型, 剩余令牌, 重试等待秒数)
    """
    return rate_limiter.check_all_limits(client_ip, endpoint)


def is_rate_limiter_available() -> bool:
    """检查限流器是否可用

    Returns:
        bool: 限流器是否可用
    """
    return redis_client is not None and rate_limiter._script_sha is not None
