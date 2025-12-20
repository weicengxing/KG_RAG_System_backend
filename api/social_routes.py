"""
api/social_routes.py
社交/好友功能路由模块
负责处理：搜索用户、发送申请、处理申请（同意/拒绝）、获取申请列表
技术点：MongoDB 事务、Redis 实时通知、双写一致性
"""

import time
import logging
import uuid
import json
from typing import List, Literal, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Header, status
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClientSession

# 引入你的数据库管理器
from database_asy_mon_re import db_manager
# 引入之前写好的工具用来解密Token获取ID
from utils import decode_token_with_exp

# 基础日志配置
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/social", tags=["Social"])

# ==================== 依赖注入 (Helpers) ====================

async def get_current_user_id(authorization: str = Header(None)) -> str:
    """从 Header 获取 Token 并解析出 user_id"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")
    
    # 兼容 Bearer xxx 格式
    token = authorization.split(" ")[1] if " " in authorization else authorization
    
    payload, is_expired, error = decode_token_with_exp(token)
    if not payload or is_expired:
         raise HTTPException(status_code=401, detail="Token invalid or expired")
    
    # 假设 token 的 sub 字段存储的是 user_id
    # 如果存的是 username，这里需要查库转成 ID，或者直接用 username 做主键
    return payload.get("sub")

def get_chat_id(user_a: str, user_b: str) -> str:
    """生成唯一会话ID (min_max 规则)"""
    ids = sorted([str(user_a), str(user_b)])
    return f"{ids[0]}_{ids[1]}"

# ==================== Pydantic 模型定义 ====================
# 为了方便直接运行，将简单的模型写在这里。复杂项目建议放到 schemas/social.py

class FriendRequestInput(BaseModel):
    target_username: str  # 前端通常输入用户名搜索
    request_msg: str = "Hi, I'd like to be your friend."

class HandleRequestInput(BaseModel):
    request_id: str
    action: Literal["accept", "reject"]

class SearchResponse(BaseModel):
    user_id: str
    username: str
    avatar: str
    relation: str  # friend, stranger, myself, pending_sent, pending_received

class RequestItemResponse(BaseModel):
    id: str = Field(alias="_id")
    from_user_id: str
    from_username: str
    from_avatar: str
    request_msg: str
    create_time: float
    status: str

# ==================== API 路由实现 ====================

@router.post("/search", response_model=SearchResponse)
async def search_user(
    body: dict = {"username": ""}, # 简单的 Body 接收
    current_user_id: str = Depends(get_current_user_id)
):
    """
    搜索用户并返回关系状态
    """
    target_username = body.get("username", "").strip()
    if not target_username:
        raise HTTPException(status_code=400, detail="Username is required")

    db = db_manager.db

    # 1. 查找目标用户是否存在
    target_user = await db.users.find_one({"username": target_username})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_id = str(target_user["_id"])

    # 2. 如果是搜自己
    if target_id == current_user_id:
        return {
            "user_id": target_id,
            "username": target_user["username"],
            "avatar": target_user.get("avatar", ""),
            "relation": "myself"
        }

    # 3. 检查是否已经是好友 (查 contacts 表)
    is_friend = await db.contacts.find_one({
        "owner_id": current_user_id,
        "friend_id": target_id
    })
    
    if is_friend:
        return {
            "user_id": target_id,
            "username": target_user["username"],
            "avatar": target_user.get("avatar", ""),
            "relation": "friend"
        }

    # 4. 检查是否有待处理的申请 (查 friend_requests 表)
    # 情况A: 我发给他了，但他没回
    req_sent = await db.friend_requests.find_one({
        "from_user_id": current_user_id,
        "to_user_id": target_id,
        "status": "pending"
    })
    if req_sent:
        return {
            "user_id": target_id,
            "username": target_user["username"],
            "avatar": target_user.get("avatar", ""),
            "relation": "request_sent"
        }
    
    # 情况B: 他发给我了 (UI 应该直接显示"同意")
    req_received = await db.friend_requests.find_one({
        "from_user_id": target_id,
        "to_user_id": current_user_id,
        "status": "pending"
    })
    if req_received:
         return {
            "user_id": target_id,
            "username": target_user["username"],
            "avatar": target_user.get("avatar", ""),
            "relation": "request_received"
        }

    # 5. 陌生人
    return {
        "user_id": target_id,
        "username": target_user["username"],
        "avatar": target_user.get("avatar", ""),
        "relation": "stranger"
    }


@router.post("/request_add")
async def send_friend_request(
    data: FriendRequestInput,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    发送好友申请
    逻辑：Upsert 模式 (如果已存在 Rejected/Old Pending 记录则更新，不存在则插入)
    """
    db = db_manager.db
    redis = db_manager.redis
    
    # 1. 查找目标用户详细信息 (需要 ID 和 头像 冗余存入请求表)
    target_user = await db.users.find_one({"username": data.target_username})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_id = str(target_user["_id"])
    if target_id == current_user_id:
        raise HTTPException(status_code=400, detail="Cannot add yourself")

    # 2. 再次校验是否已是好友 (防止重复添加)
    # 也可以利用 Redis 缓存： sismember friends:{current_user_id} {target_id}
    exists = await db.contacts.find_one({"owner_id": current_user_id, "friend_id": target_id})
    if exists:
        return {"message": "Already friends"}

    # 3. 准备数据
    # 获取发送者信息 (冗余存储，方便接收者直接查看列表而无需 Join)
    myself = await db.users.find_one({"_id": current_user_id})
    
    request_doc = {
        "from_user_id": current_user_id,
        "to_user_id": target_id,
        "from_username": myself.get("username"), # 冗余字段
        "from_avatar": myself.get("avatar"),     # 冗余字段
        "request_msg": data.request_msg,
        "status": "pending",
        "create_time": time.time(),
        "update_time": time.time()
    }

    # 4. 写入 MongoDB (使用 upsert 防止重复多条记录)
    # 查询条件：from A -> to B
    await db.friend_requests.update_one(
        {"from_user_id": current_user_id, "to_user_id": target_id},
        {"$set": request_doc},
        upsert=True
    )

    # 5. 【关键】通过 Redis 发送实时通知
    # 前端 chat 组件会监听 "new_notification" 事件
    notification_payload = json.dumps({
        "type": "new_friend_request",
        "data": {
            "from_user": myself.get("username"),
            "msg": data.request_msg
        }
    })
    
    # 推送到接收者的 Redis 频道 (与 chat_routes 保持一致)
    await redis.publish(f"chat:user:{target_id}", notification_payload)

    # 还可以维护一个 Redis 计数器: incr user_stat:{target_id}:unread_requests

    return {"message": "Friend request sent"}


@router.get("/requests", response_model=List[RequestItemResponse])
async def get_my_requests(current_user_id: str = Depends(get_current_user_id)):
    """获取别人发给我的待处理请求"""
    db = db_manager.db
    cursor = db.friend_requests.find({
        "to_user_id": current_user_id,
        "status": "pending"
    }).sort("update_time", -1)
    
    requests = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"]) # ObjectId -> str
        requests.append(doc)
        
    return requests


@router.post("/handle")
async def handle_request(
    data: HandleRequestInput,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    同意/拒绝 好友申请
    *** 核心：同意操作使用 MongoDB Transaction (Session) 保证一致性 ***
    """
    db = db_manager.db
    redis = db_manager.redis

    # 1. 查找该请求
    # 这里有个坑：ObjectId 需要转换，如果 id 是前端传的字符串
    from bson import ObjectId
    try:
        req_oid = ObjectId(data.request_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid request ID")

    request_doc = await db.friend_requests.find_one({"_id": req_oid})
    
    if not request_doc:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # 安全校验：确保这条请求是发给当前用户的
    if request_doc["to_user_id"] != current_user_id:
        raise HTTPException(status_code=403, detail="Permission denied")
        
    # 如果已经处理过
    if request_doc["status"] != "pending":
        return {"message": f"Request already {request_doc['status']}"}

    partner_id = request_doc["from_user_id"]

    # === 拒绝逻辑 (简单更新状态) ===
    if data.action == "reject":
        await db.friend_requests.update_one(
            {"_id": req_oid},
            {"$set": {"status": "rejected", "update_time": time.time()}}
        )
        return {"message": "Rejected"}

    # === 同意逻辑 (复杂事务) ===
    # 大厂标准：写联系人表A->B，写联系人表B->A，更新请求表，(可选)插入系统消息
    
    # Motor 支持 Session，需要 MongoDB 是 Replica Set 模式 (单节点开启 replSet 也可以)
    # 如果你的 Mongo 是完全单机且没开 replSet，session 会报错。
    # 这里为了健壮性，使用了 try-finally，实际部署建议 Mongo 开启副本集
    
    try:
        async with await db_manager.client.start_session() as session:
            async with session.start_transaction():
                # A. 更新请求状态
                await db.friend_requests.update_one(
                    {"_id": req_oid},
                    {"$set": {"status": "accepted", "update_time": time.time()}},
                    session=session
                )
                
                ts = time.time()
                
                # B. 写入联系人 (Double Entry)
                # 我 -> 对方
                await db.contacts.update_one(
                    {"owner_id": current_user_id, "friend_id": partner_id},
                    {"$set": {
                        "created_at": ts,
                        "remark": request_doc.get("from_username", "") # 默认备注设为对方昵称
                    }},
                    upsert=True,
                    session=session
                )
                
                # 对方 -> 我 (需要查一下我的名字存进去作为默认备注，或者留空)
                # 为了简单，直接存 ID，显示时 join user 表
                await db.contacts.update_one(
                    {"owner_id": partner_id, "friend_id": current_user_id},
                    {"$set": {
                        "created_at": ts, 
                        "remark": "" # 对方那边备注暂时留空
                    }},
                    upsert=True,
                    session=session
                )
                
                # C. 插入一条 System Message 到 Chat History 分桶
                # 这样用户点进聊天框就能看到“你们已经是好友了”
                chat_id = get_chat_id(current_user_id, partner_id)
                sys_msg = {
                    "msg_id": f"sys-{uuid.uuid4()}",
                    "sender_id": "system",
                    "receiver_id": "all", # 广播给该 Room
                    "content": "You are now connected. Say Hello! 👋",
                    "ts": ts,
                    "type": "system", # 前端特殊渲染
                }
                
                # 利用你之前的 chat 逻辑存入桶 (这里为了简化不引入 ChatManager，直接裸写 db update)
                # 实际上应该 call ChatManager.save_message，但在 transaction 里要注意
                await db.chat_history.update_one(
                    {"chat_id": chat_id, "count": {"$lt": 50}},
                    {
                        "$push": {"messages": sys_msg},
                        "$inc": {"count": 1},
                        "$set": {"last_updated": ts}
                    },
                    upsert=True, # 如果没有对话，创建新桶
                    session=session
                )

        # === 事务提交成功后执行非关键操作 (Redis) ===
        
        # 1. 更新 Redis 缓存 Set (快速判断好友关系)
        pipeline = redis.pipeline()
        pipeline.sadd(f"friends:{current_user_id}", partner_id)
        pipeline.sadd(f"friends:{partner_id}", current_user_id)
        await pipeline.execute()
        
        # 2. 通知发起人 (partner_id)
        msg_payload = json.dumps({
            "type": "new_message", # 复用 new_message 让聊天列表顶起来
            "data": sys_msg        # 直接推送那条系统消息
        })
        # 再发一个好友通过的事件
        event_payload = json.dumps({
             "type": "friend_accepted",
             "data": {"friend_id": current_user_id}
        })

        await redis.publish(f"chat:user:{partner_id}", msg_payload)
        await redis.publish(f"chat:user:{partner_id}", event_payload)
        # 通知自己刷新
        await redis.publish(f"chat:user:{current_user_id}", event_payload)

        return {"message": "Friend accepted"}
        
    except Exception as e:
        logger.error(f"Handle Friend Transaction Failed: {e}")
        raise HTTPException(status_code=500, detail="Transaction failed, please try again")
