# init_chat_db.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import time

# 配置你的 MongoDB 地址
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "chat_app_db" # 请确保和 config.py 里一致

async def init_data():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    
    print("🗑️ 清理旧数据...")
    await db.users.drop()
    await db.chat_history.drop()
    
    print("👤 创建测试用户...")
    users = [
        {"_id": "user_1", "username": "开发者 (我)", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Felix", "status": "online"},
        {"_id": "user_2", "username": "Sarah Chen", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Sarah", "status": "online"},
        {"_id": "user_3", "username": "Mike Design", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Mike", "status": "busy"},
    ]
    await db.users.insert_many(users)

    print("💬 创建一些历史聊天记录...")
    # 模拟 user_1 和 user_2 的聊天
    chat_id = "user_1_user_2" # 这里的ID必须是排序后的
    
    initial_messages = []
    for i in range(5):
        initial_messages.append({
            "msg_id": f"msg_init_{i}",
            "sender_id": "user_2" if i % 2 == 0 else "user_1",
            "content": f"这是第 {i+1} 条历史消息...",
            "ts": time.time() - (1000 - i*100),
            "type": "text"
        })

    bucket = {
        "chat_id": chat_id,
        "count": len(initial_messages),
        "messages": initial_messages,
        "last_updated": time.time()
    }
    await db.chat_history.insert_one(bucket)

    print("⚡ 创建索引...")
    # 确保唯一性和查询速度
    await db.chat_history.create_index([("chat_id", 1), ("_id", -1)])
    
    print("✅ 数据库初始化完成！")
    client.close()

if __name__ == "__main__":
    asyncio.run(init_data())