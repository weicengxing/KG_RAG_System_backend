import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import time

MONGO_URI = "mongodb://localhost:27017" # 请确认地址
DB_NAME = "chat_app_db" 

async def add_dummy_friends():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    
    # 假设当前你是 user_1
    current_user_id = "user_1" # 请根据你JWT Debug里的 sub 修改，如果是 '没接'，就填 '没接'
    
    print(f"🤝 正在为 {current_user_id} 添加好友关系...")

    # 清空旧关系
    await db.friendships.delete_many({})

    # 1. 找到所有其他用户
    others = db.users.find({"_id": {"$ne": current_user_id}})
    
    async for friend in others:
        # 双向写入 (为了性能)
        # 1. 我 -> 朋友
        await db.friendships.insert_one({
            "user_id": current_user_id,
            "friend_id": friend["_id"],
            "status": "accepted",
            "created_at": time.time()
        })
        # 2. 朋友 -> 我 (防止以后登录朋友号看不到我)
        await db.friendships.insert_one({
            "user_id": friend["_id"],
            "friend_id": current_user_id,
            "status": "accepted",
            "created_at": time.time()
        })
        print(f"   ✅ 已添加好友: {friend.get('username')}")

    print("🎉 好友数据初始化完成")
    client.close()

if __name__ == "__main__":
    asyncio.run(add_dummy_friends())