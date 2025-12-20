"""
database.py
数据库连接管理器 (单例模式)
统一管理 MongoDB (Motor) 和 Redis (Asyncio) 的生命周期
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as aioredis  # 异步Redis库

from config import (
    MONGO_URI, MONGO_DB_NAME,
    REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB
)

logger = logging.getLogger("System")

class DatabaseManager:
    client: AsyncIOMotorClient = None
    db = None
    redis: aioredis.Redis = None

    async def connect(self):
        """应用启动时调用：初始化所有连接"""
        
        # 1. MongoDB 初始化
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        
        # 创建好友模块必须的唯一索引 (幂等操作，由于是启动时运行，确保只执行一次)
        # 索引A: 确保好友请求不重复 (from -> to)
        await self.db.friend_requests.create_index(
            [("from_user_id", 1), ("to_user_id", 1)], 
            unique=True,
            partialFilterExpression={"status": "pending"} # 只限制 pending 状态的请求不重复
        )
        # 索引B: 好友关系双向查询优化 (owner -> friend)
        await self.db.contacts.create_index(
            [("owner_id", 1), ("friend_id", 1)],
            unique=True
        )
        logger.info("✅ Database (Mongo) connected & Indexes checked.")

        # 2. Redis 异步初始化
        # 构造 Redis URL (处理密码为空的情况)
        auth = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
        redis_url = f"redis://{auth}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
        
        self.redis = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=1000  # 连接池限制，根据机器配置调整
        )
        
        # 连通性测试
        try:
            await self.redis.ping()
            logger.info(f"✅ Redis (Async) connected pool created.")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise e

    async def close(self):
        """应用关闭时调用"""
        if self.client:
            self.client.close()
        if self.redis:
            await self.redis.close()
        logger.info("🛑 Database connections closed.")

# 全局单例
db_manager = DatabaseManager()

# 便捷获取 db 对象的依赖函数 (供 FastAPI Depends 使用)
async def get_db():
    return db_manager.db

async def get_redis_async():
    return db_manager.redis