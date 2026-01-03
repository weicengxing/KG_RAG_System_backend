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

        # 索引C: 群组成员查询优化 (members数组索引) - 保留用于群内成员验证
        await self.db.groups.create_index([("members", 1)])

        # 索引D: 群组所有者查询优化
        await self.db.groups.create_index([("owner_id", 1)])

        # 索引E: 用户-群组关系表 (数据冗余策略，提升查询效率)
        # user_groups 集合: {user_id, group_id, role, joined_at}
        await self.db.user_groups.create_index(
            [("user_id", 1), ("group_id", 1)],
            unique=True
        )
        # 反向索引：通过group_id查询所有成员
        await self.db.user_groups.create_index([("group_id", 1)])
        # 通过user_id查询所有群组（最常用的查询）
        await self.db.user_groups.create_index([("user_id", 1)])

        # 索引F: 群组邀请码索引
        await self.db.groups.create_index([("invite_code", 1)], unique=True, sparse=True)

        # 索引G: 知识图谱文档集合
        # G1: 基于 MD5 hash 的唯一索引，防止重复上传
        await self.db.documents.create_index([("file_hash", 1)], unique=True)
        # G2: 基于 doc_id 的唯一索引
        await self.db.documents.create_index([("doc_id", 1)], unique=True)
        # G3: 上传时间索引（用于按时间查询）
        await self.db.documents.create_index([("upload_time", -1)])
        # G4: 文件类型索引
        await self.db.documents.create_index([("file_extension", 1)])

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
