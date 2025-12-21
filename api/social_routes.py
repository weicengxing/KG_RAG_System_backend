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
import os
import base64
from typing import List, Literal, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Header, status
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClientSession

# 引入你的数据库管理器
from database_asy_mon_re import db_manager
# 引入之前写好的工具用来解密Token获取ID
from utils import decode_token_with_exp
# 引入 Neo4j 数据库操作模块（用于查询用户信息）
import database

# 基础日志配置
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/social", tags=["Social"])

# 头像目录路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVATAR_DIR = os.path.join(project_root, "assets", "avatars")

# ==================== 辅助函数 ====================

async def get_avatar_base64(avatar_filename: str) -> Optional[str]:
    """读取头像文件并转换为 base64"""
    if not avatar_filename:
        logger.info("❌ 头像文件名为空")
        return None

    # 如果是 URL，直接返回 None（让前端用原 URL）
    if avatar_filename.startswith('http://') or avatar_filename.startswith('https://'):
        logger.info(f"⚠️ 头像是 URL，跳过转换: {avatar_filename}")
        return None

    try:
        file_path = os.path.join(AVATAR_DIR, avatar_filename)
        logger.info(f"📂 尝试读取头像: {file_path}")

        if not os.path.exists(file_path):
            logger.warning(f"❌ 头像文件不存在: {file_path}")
            return None

        with open(file_path, 'rb') as f:
            avatar_bytes = f.read()
            avatar_base64 = base64.b64encode(avatar_bytes).decode('utf-8')

            # 判断文件类型
            if avatar_filename.lower().endswith('.png'):
                mime_type = 'image/png'
            elif avatar_filename.lower().endswith('.jpg') or avatar_filename.lower().endswith('.jpeg'):
                mime_type = 'image/jpeg'
            elif avatar_filename.lower().endswith('.gif'):
                mime_type = 'image/gif'
            else:
                mime_type = 'image/jpeg'  # 默认

            data_url = f"data:{mime_type};base64,{avatar_base64}"
            logger.info(f"✅ 头像转换成功，大小: {len(avatar_base64)} 字符, MIME: {mime_type}")
            return data_url
    except Exception as e:
        logger.error(f"❌ 读取头像失败: {avatar_filename}, {e}")
        return None

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

    # 兼容新旧两种 token 格式
    # 新格式: {"user_id": "xxx", "username": "xxx"}
    # 旧格式: {"sub": "username"}
    username = payload.get("username") or payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # 从 MongoDB 查询用户获取 _id (雪花ID)
    db = db_manager.db
    user = await db.users.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return str(user["_id"])

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
    # 1. 查找目标用户详细信息
    # 去除首尾空格，进行精确匹配
    target_username = data.target_username.strip()
    

    target_user = await db.users.find_one({"username": target_username})
    
    # 调试：如果找不到，尝试模糊搜索看看库里有什么
    if not target_user:
        logger.warning(f"❌ 精确匹配失败，尝试模糊搜索...")
        cursor = db.users.find({"username": {"$regex": target_username, "$options": "i"}})
        similar_users = await cursor.to_list(length=5)
        logger.info(f"📋 相似用户: {[u.get('username') for u in similar_users]}")
        raise HTTPException(
            status_code=404,
            detail=f"User not found. Similar users: {[u.get('username') for u in similar_users]}"
        )

    target_id = str(target_user["_id"])
    if target_id == current_user_id:
        raise HTTPException(status_code=400, detail="Cannot add yourself")

    # 2. 再次校验是否已是好友
    exists = await db.contacts.find_one({"owner_id": current_user_id, "friend_id": target_id})
    if exists:
        return {"message": "Already friends"}

    # 3. 获取当前用户信息 (冗余存储，方便接收者直接查看列表)
    myself = await db.users.find_one({"_id": current_user_id})
    if not myself:
        raise HTTPException(status_code=404, detail="Current user not found in database")

    request_doc = {
        "from_user_id": current_user_id,
        "to_user_id": target_id,
        "from_username": myself.get("username", "Unknown"),  # 冗余字段
        "from_avatar": myself.get("avatar", ""),             # 冗余字段
        "request_msg": data.request_msg,
        "status": "pending",
        "create_time": time.time(),
        "update_time": time.time()
    }

    # 4. 写入 MongoDB (使用 upsert 防止重复多条记录)
    await db.friend_requests.update_one(
        {"from_user_id": current_user_id, "to_user_id": target_id},
        {"$set": request_doc},
        upsert=True
    )

    # 5. 【关键】通过 Redis 发送实时通知
    notification_payload = json.dumps({
        "type": "new_friend_request",
        "data": {
            "from_user": myself.get("username", "Unknown"),
            "msg": data.request_msg
        }
    })

    # 推送到接收者的 Redis 频道
    await redis.publish(f"chat:user:{target_id}", notification_payload)

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

    # === 同意逻辑 (无事务版本，按顺序写入) ===
    # 注意：因为没有事务保护，理论上可能出现部分写入成功的情况
    # 实际生产环境建议使用消息队列或者开启MongoDB副本集来支持事务

    try:
        ts = time.time()

        # A. 更新请求状态
        await db.friend_requests.update_one(
            {"_id": req_oid},
            {"$set": {"status": "accepted", "update_time": ts}}
        )

        # B. 写入联系人 (Double Entry)
        # 我 -> 对方
        await db.contacts.update_one(
            {"owner_id": current_user_id, "friend_id": partner_id},
            {"$set": {
                "created_at": ts,
                "remark": request_doc.get("from_username", "") # 默认备注设为对方昵称
            }},
            upsert=True
        )

        # 对方 -> 我
        await db.contacts.update_one(
            {"owner_id": partner_id, "friend_id": current_user_id},
            {"$set": {
                "created_at": ts,
                "remark": "" # 对方那边备注暂时留空
            }},
            upsert=True
        )

        # C. 插入一条打招呼消息到 Chat History 分桶（使用申请人的打招呼内容）
        chat_id = get_chat_id(current_user_id, partner_id)
        greeting_msg = {
            "msg_id": str(uuid.uuid4()),
            "sender_id": partner_id,  # 发送者是申请人
            "receiver_id": current_user_id,  # 接收者是当前用户
            "content": request_doc.get("request_msg", "Hi, I'd like to be your friend."),  # 使用打招呼内容
            "ts": ts,
            "type": "text",  # 正常文本消息类型
        }

        # 尝试插入到未满的桶，如果没有则创建新桶
        result = await db.chat_history.update_one(
            {"chat_id": chat_id, "count": {"$lt": 50}},
            {
                "$push": {"messages": greeting_msg},
                "$inc": {"count": 1},
                "$set": {"last_updated": ts}
            }
        )

        # 如果没有找到未满的桶，创建新桶
        if result.matched_count == 0:
            await db.chat_history.insert_one({
                "chat_id": chat_id,
                "count": 1,
                "messages": [greeting_msg],
                "last_updated": ts,
                "created_at": ts
            })

        # === 写入完成后执行非关键操作 (Redis) ===

        # 1. 更新 Redis 缓存 Set (快速判断好友关系)
        pipeline = redis.pipeline()
        pipeline.sadd(f"friends:{current_user_id}", partner_id)
        pipeline.sadd(f"friends:{partner_id}", current_user_id)
        await pipeline.execute()

        # 2. 获取双方用户信息（用于前端增量更新好友列表）
        # 从 Neo4j 查询用户信息（与 chat_routes.py 的 contacts 接口保持一致）
        current_user_info = database.get_user_by_id(current_user_id)
        partner_user_info = database.get_user_by_id(partner_id)
        
        

        if not current_user_info:
            logger.error(f"❌ 查询当前用户信息失败: {current_user_id}")
        if not partner_user_info:
            logger.error(f"❌ 查询对方用户信息失败: {partner_id}")

        # 3. 发送好友通过事件（包含完整用户信息、头像 base64 和打招呼消息）
        greeting_content = request_doc.get("request_msg", "Hi, I'd like to be your friend.")

        # 读取双方头像并转换为 base64（如果是本地文件）
        current_user_avatar_base64 = await get_avatar_base64(current_user_info.get("avatar", "") if current_user_info else "")
        partner_user_avatar_base64 = await get_avatar_base64(partner_user_info.get("avatar", "") if partner_user_info else "")

        logger.info(f"🖼️ 当前用户头像 base64: {'有数据' if current_user_avatar_base64 else '无数据（可能是URL）'}")
        logger.info(f"🖼️ 对方用户头像 base64: {'有数据' if partner_user_avatar_base64 else '无数据（可能是URL）'}")

        # 发送给发起人（partner_id）的通知
        partner_data = {
             "friend_id": str(current_user_id),  # 确保是字符串格式
             "username": current_user_info.get("username", "Unknown") if current_user_info else "Unknown",
             "avatar": current_user_info.get("avatar", "") if current_user_info else "",
             "avatar_base64": current_user_avatar_base64,  # base64 数据（如果有）
             "lastMessage": greeting_content,  # 添加打招呼内容
             "lastTime": ts
        }
        event_payload_for_partner = json.dumps({
             "type": "friend_accepted",
             "data": partner_data
        })

        # 发送给接收者（当前用户）的通知
        current_data = {
             "friend_id": str(partner_id),  # 确保是字符串格式
             "username": partner_user_info.get("username", "Unknown") if partner_user_info else "Unknown",
             "avatar": partner_user_info.get("avatar", "") if partner_user_info else "",
             "avatar_base64": partner_user_avatar_base64,  # base64 数据（如果有）
             "lastMessage": greeting_content,  # 添加打招呼内容
             "lastTime": ts
        }
        event_payload_for_current = json.dumps({
             "type": "friend_accepted",
             "data": current_data
        })

        logger.info(f"📤 发送给 {partner_id} 的通知数据: avatar_base64={'有' if partner_data.get('avatar_base64') else '无'}")
        logger.info(f"📤 发送给 {current_user_id} 的通知数据: avatar_base64={'有' if current_data.get('avatar_base64') else '无'}")

        # 发送通知到Redis
        await redis.publish(f"chat:user:{partner_id}", event_payload_for_partner)
        await redis.publish(f"chat:user:{current_user_id}", event_payload_for_current)

        logger.info(f"✅ 好友关系已建立，通知已发送: {current_user_id} <-> {partner_id}")

        return {"message": "Friend accepted"}
        
    except Exception as e:
        logger.error(f"Handle Friend Transaction Failed: {e}")
        raise HTTPException(status_code=500, detail="Transaction failed, please try again")


@router.post("/delete_friend")
async def delete_friend(
    body: dict,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    删除好友
    删除双方的contacts关系，并清空聊天记录
    """
    db = db_manager.db
    redis = db_manager.redis

    friend_id = body.get("friend_id", "").strip()
    if not friend_id:
        raise HTTPException(status_code=400, detail="friend_id is required")

    try:
        # 1. 检查好友关系是否存在
        exists = await db.contacts.find_one({
            "owner_id": current_user_id,
            "friend_id": friend_id
        })

        if not exists:
            raise HTTPException(status_code=404, detail="Friend relationship not found")

        # 2. 生成chat_id（用于删除聊天记录）
        chat_id = get_chat_id(current_user_id, friend_id)

        # 3. 删除聊天历史记录（所有相关的桶）
        delete_result = await db.chat_history.delete_many({"chat_id": chat_id})
        logger.info(f"删除了 {delete_result.deleted_count} 个聊天记录桶")

        # 4. 删除双方的contacts记录
        await db.contacts.delete_one({
            "owner_id": current_user_id,
            "friend_id": friend_id
        })

        await db.contacts.delete_one({
            "owner_id": friend_id,
            "friend_id": current_user_id
        })

        # 5. 更新 Redis 缓存
        pipeline = redis.pipeline()
        pipeline.srem(f"friends:{current_user_id}", friend_id)
        pipeline.srem(f"friends:{friend_id}", current_user_id)
        await pipeline.execute()

        logger.info(f"✅ 好友关系已删除: {current_user_id} <-> {friend_id}, 聊天记录已清空")

        return {
            "message": "Friend deleted successfully",
            "friend_id": friend_id,
            "deleted_messages": delete_result.deleted_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除好友失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete friend")
