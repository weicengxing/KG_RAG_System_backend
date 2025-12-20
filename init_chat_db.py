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
          {
    "username": "听安",  # 键用双引号包裹（Python 单引号/双引号均可）
    "email": "jiccao4lyk@witusp.com",
    "avatar": "听安_1765364810808_c067ea0f.jpg",
    "status": "online"
  },
  
  {
    "username": "故事",
    "email": "matjoo6pmy@obeamb.com",
    "avatar": None,  # 替换 null 为 None（Python 空值）
    "status": "online"
  },
 
  {
    "username": "双节",
    "email": "fuisazqt8o@obeamb.com",
    "avatar": "双节_1765200193252_83ab568a.jpg",
    "status": "online"
  },

  {
    "username": "张远昭",
    "email": "2997657261@qq.com",
    "avatar": None,  # 替换 null 为 None
    "status": "online"
  },
  
  {
    "username": "没接",
    "email": "dalkui3ls0@zorrag.com",
    "avatar": "没接_1765346499224_7cc7d43e.jpg",
    "status": "online"
  },
  
  {
    "username": "梅",
    "email": "1989697277@qq.com",
    "avatar": "梅_1765369848822_8b617dd7.png",
    "status": "online"
  },
  
  {
    "username": "哈哈哈",
    "email": "tifhuhet0l@obeamb.com",
    "avatar": "哈哈哈_1765439945029_c9a58189.jpg",
    "status": "online"
  },

  {
    "username": "测试000",
    "email": "vamlemlj6l@zorrag.com",
    "avatar": "default_avatar.png",
    "status": "online"
  },
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