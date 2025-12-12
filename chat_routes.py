"""
聊天系统路由模块
集成 MongoDB (Motor) 分桶存储与 Redis Pub/Sub 实时推送
实现极致性能的实时通讯接口
"""

import json
import time
import asyncio
import logging
from typing import List, Optional
from datetime import datetime
import database
from utils import decode_token_with_exp 
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, Depends,status
from pydantic import BaseModel

# 引入 Motor (MongoDB 异步驱动)
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as aioredis  # 需要异步 Redis 客户端支持 WebSocket

# 复用配置
from config import (
    MONGO_URI,          # 需要你在 config.py 添加 MongoDB 连接串
    MONGO_DB_NAME,      # 需要你在 config.py 添加 DB 名
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
    REDIS_DB
)

# ==================== 日志配置 ====================

logger = logging.getLogger(__name__)

# ==================== 路由与资源初始化 ====================

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# 全局单例管理器
mongo_client: Optional[AsyncIOMotorClient] = None
db = None
redis_async: Optional[aioredis.Redis] = None

# ==================== 数据模型 (Pydantic) ====================

class Message(BaseModel):
    msg_id: str
    sender_id: str
    content: str
    ts: float
    type: str = "text"  # text, image, file

class ChatSession(BaseModel):
    chat_id: str
    partner_id: str
    partner_name: str
    partner_avatar: str
    last_message: str
    last_time: str
    unread: int

# ==================== 核心服务类: ChatManager ====================

class ChatManager:
    """聊天核心服务管理器
    负责 WebSocket 连接管理、Redis 消息广播、MongoDB 分桶存储
    """
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.BUCKET_SIZE = 50  # 每个桶存储的消息数量
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"🔌 WebSocket 连接建立: {user_id}")
        
        # 用户上线，启动 Redis 订阅任务
        asyncio.create_task(self._subscribe_to_user_channel(user_id, websocket))

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"🔌 WebSocket 连接断开: {user_id}")

    async def _subscribe_to_user_channel(self, user_id: str, websocket: WebSocket):
        """订阅 Redis 频道，接收发给该用户的消息"""
        pubsub = redis_async.pubsub()
        channel = f"chat:user:{user_id}"
        await pubsub.subscribe(channel)
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    # 收到 Redis 广播的消息，通过 WebSocket 推送给前端
                    await websocket.send_text(message["data"])
        except Exception as e:
            logger.error(f"❌ Redis 订阅异常 {user_id}: {e}")
        finally:
            await pubsub.unsubscribe(channel)

    async def send_personal_message(self, msg_data: dict):
        """发送私聊消息流程:
        1. 存入 MongoDB (分桶)
        2. 推送给接收者 (Redis Pub/Sub)
        3. 推送给发送者 (多端同步)
        """
        sender = msg_data['sender_id']
        receiver = msg_data['receiver_id']
        
        # 1. 生成 chat_id (确保顺序一致，如 "min_max")
        ids = sorted([sender, receiver])
        chat_id = f"{ids[0]}_{ids[1]}"
        
        # 2. 存入 MongoDB (极速分桶写入)
        await self._save_to_mongodb(chat_id, msg_data)
        
        # 3. 序列化消息
        payload = json.dumps({
            "type": "new_message",
            "chat_id": chat_id,
            "data": msg_data
        })
        
        # 4. 广播消息 (无论用户是否在线，先推到 Redis)
        # 推送给接收者
        await redis_async.publish(f"chat:user:{receiver}", payload)
        # 推送给发送者 (为了多设备同步，或者简单的 ACK)
        await redis_async.publish(f"chat:user:{sender}", payload)

    async def _save_to_mongodb(self, chat_id: str, msg_data: dict):
        """MongoDB 分桶写入策略 (Atomic Update)"""
        try:
            # 尝试推送到最新的未满桶
            result = await db.chat_history.update_one(
                {
                    "chat_id": chat_id,
                    "count": {"$lt": self.BUCKET_SIZE}
                },
                {
                    "$push": {"messages": msg_data},
                    "$inc": {"count": 1},
                    "$set": {"last_updated": time.time()}
                },
                upsert=False 
                # 这里不使用 upsert=True，因为我们需要确保只有在找到符合条件的桶时才更新
                # 如果没找到，说明都满了或者没桶，需要 create
            )
            
            if result.matched_count == 0:
                # 没找到未满的桶，创建一个新的
                new_bucket = {
                    "chat_id": chat_id,
                    "count": 1,
                    "messages": [msg_data],
                    "last_updated": time.time(),
                    "created_at": time.time()
                }
                await db.chat_history.insert_one(new_bucket)
                # logger.debug(f"📦 创建新分桶: {chat_id}")
                
        except Exception as e:
            logger.error(f"❌ 消息持久化失败: {e}")
            raise e

    async def get_chat_history(self, chat_id: str, limit: int = 50, before_ts: float = None):
        """加载历史记录 (利用分桶索引)"""
        try:
            # 构建查询
            query = {"chat_id": chat_id}
            if before_ts:
                # 优化：如果提供了时间戳，可以过滤掉明显更新的桶
                # 但实际上只用 sort _id 倒序即可命中索引
                pass

            # 倒序查询桶 (最新的桶在前)
            # 假设一个桶 50 条，取 limit 条需要遍历 ceil(limit/50) 个桶
            # 这里简单处理，取最近的 5 个桶一般足够覆盖 250 条消息
            cursor = db.chat_history.find(query).sort("_id", -1).limit(5)
            
            all_messages = []
            async for bucket in cursor:
                # 桶内消息是正序的，我们需要将其反转或保持原样，取决于前端需求
                # 这里保持原样 (旧 -> 新)，但在合并桶时要注意顺序
                msgs = bucket.get("messages", [])
                
                # 如果有 before_ts 过滤 (游标分页)
                if before_ts:
                    msgs = [m for m in msgs if m['ts'] < before_ts]
                
                # 将当前桶的消息加到总列表的前面 (因为我们是倒序遍历桶)
                all_messages = msgs + all_messages
                
                if len(all_messages) >= limit:
                    break
            
            # 截取最后 limit 条
            return all_messages[-limit:]
            
        except Exception as e:
            logger.error(f"❌ 获取历史记录失败: {chat_id}, {e}")
            return []

chat_manager = ChatManager()

# ==================== 生命周期事件 ====================

@router.on_event("startup")
async def startup_event():
    """初始化 MongoDB 和 Redis 连接"""
    global mongo_client, db, redis_async
    try:
        # Mongo Init
        mongo_client = AsyncIOMotorClient(MONGO_URI)
        db = mongo_client[MONGO_DB_NAME]
        
        # 1. 检查索引是否存在，不存在再创建（避免报错）
        # 这里不需要每次都 create_index，motor 会自动处理幂等性，但为了稳妥可以保留
        try:
            await db.chat_history.create_index([("chat_id", 1), ("_id", -1)])
            await db.chat_history.create_index([("chat_id", 1), ("count", 1)])
        except Exception:
            pass # 索引可能已存在
            
        logger.info("✅ MongoDB (Motor) 连接成功")
        
        # 2. Redis 连接逻辑修复 (Fix AuthenticationError)
        # 如果密码为空或 None，不要在 URL 里带 ":@" 结构
        if REDIS_PASSWORD:
            redis_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
        else:
            redis_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
            
        redis_async = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # 测试一下连接
        await redis_async.ping()
        logger.info("✅ Redis (Async) 连接成功")
        
    except Exception as e:
        logger.error(f"❌ 聊天服务初始化失败: {e}")
        # 这里建议抛出异常，否则服务起来了但数据库连不上
        raise e

@router.on_event("shutdown")
async def shutdown_event():
    if mongo_client:
        mongo_client.close()
    if redis_async:
        await redis_async.close()
    logger.info("🛑 聊天服务连接已关闭")


# ==================== API 接口实现 ====================

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    user_id: str, 
    token: str = Query(None)
):
    """
    WebSocket 长连接入口 (含24小时过期宽限期)
    """
    
    # --- 阶段一: 握手前鉴权 ---
    
    # 1. 检查 Token 是否提供
    if not token:
        logger.warning(f"[WS] ❌ 连接拒绝: 未提供 Token - 请求 User: {user_id}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        # 2. 解码并验证 Token
        # 假设 decode_token_with_exp 即使过期也会返回 payload，否则下面拿不到 exp
        payload, is_expired, error_msg = decode_token_with_exp(token)

        # 3. 处理无效 Token (格式错误/签名不对/Payload丢失)
        if payload is None:
            logger.warning(f"[WS] ❌ 连接拒绝: Token 无效/无法解析 ({error_msg}) - 请求 User: {user_id}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # 4. 处理过期逻辑 (修改处: 增加宽限期判断)
        if is_expired:
            exp_timestamp = payload.get("exp", 0)
            current_timestamp = time.time()
            grace_period_seconds = 24 * 60 * 60  # 24小时

            # 只有当 (当前时间 > 过期时间 + 24小时) 时，才强制拒绝
            if current_timestamp > (exp_timestamp + grace_period_seconds):
                logger.warning(f"[WS] ❌ 连接拒绝: Token 已彻底过期(超过宽限期) - 请求 User: {user_id}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            else:
                # 宽限期内，允许通过
                logger.warning(f"[WS] ⚠️ Token 已过期但处于宽限期(24h)内，允许连接 - User: {user_id}")

        # 5. 身份一致性检查 (防止 A 用户拿着 B 用户的 Token 连接)
        token_username = payload.get("sub")
        # 前端传来的 Token decoded 后显示的 username 必须等于 URL 里的 user_id
        # 这里你需要确认你的 JWT payload "sub" 字段存的是 username 还是 user_id
        # 如果 user_id 是数据库ID，而 sub 也是数据库ID，直接对比即可
        # 你的日志显示 sub 是 "\u6ca1..." 这种，看起来像中文名或ID
        
        # 为了兼容性，转字符串比较
        if str(token_username) != str(user_id):
            logger.warning(f"[WS] ❌ 连接拒绝: 身份不匹配 (TokenSub: {token_username} != URLPath: {user_id})")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # (可选) 更新活跃时间
        try:
            database.update_last_activity(str(token_username))
        except Exception:
            pass

    except Exception as e:
        logger.error(f"[WS] ❌ 鉴权过程发生未预期的错误: {str(e)}")
        # 1011 表示 Internal Error
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    # --- 阶段二: 建立连接 ---
    
    # 鉴权通过，接受连接
    try:
        # 在 chat_manager.connect 内部一般会有 websocket.accept()
        # 如果没有，请在这里加上 await websocket.accept()
        await chat_manager.connect(websocket, user_id)
        
        while True:
            data = await websocket.receive_text()
            
            try:
                msg_obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            
            # 心跳
            if msg_obj.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue
            
            # 发送消息
            if msg_obj.get("type") == "message":
                target_id = msg_obj.get("target_id")
                content = msg_obj.get("content")
                
                if target_id and content:
                    current_ts = time.time()
                    msg_content = {
                        "msg_id": f"{user_id}-{int(current_ts * 1000)}", 
                        "sender_id": user_id,
                        "receiver_id": target_id,
                        "content": content,
                        "ts": current_ts,
                        "type": "text"
                    }
                    await chat_manager.send_personal_message(msg_content)

    except WebSocketDisconnect:
        logger.info(f"[WS] 用户主动断开: {user_id}")
        chat_manager.disconnect(user_id)
        
    except Exception as e:
        # 如果这里报错 'RuntimeError: No response returned from the upstream'，
        # 通常是因为前面的 connect 还没 accept 也就是鉴权就挂了，
        # 或者 websocket 已经 close 了但代码还在跑
        # 只要日志里不疯狂刷屏就没事
        logger.warning(f"[WS] WebSocket 连接异常结束 ({user_id}): {str(e)}")
        chat_manager.disconnect(user_id)


@router.get("/contacts")
async def get_contacts(user_id: str = Query(..., description="当前用户ID")):
    """
    获取会话列表逻辑：
    1. 拿到所有用户
    2. 聚合查询最后一条聊天记录
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database uninitialized")

    contacts_list = []
    
    # 1. 获取除自己以外的所有用户 (简化版，实际可能是获取好友列表)
    users_cursor = db.users.find({"_id": {"$ne": user_id}})
    
    async for user in users_cursor:
        partner_id = user["_id"]
        
        # 2. 计算 chat_id
        ids = sorted([user_id, partner_id])
        chat_id = f"{ids[0]}_{ids[1]}"
        
        # 3. 查找该会话最新的一条消息
        # 技巧：按 _id 倒序取第一个桶，再取桶里最后一条消息
        last_bucket = await db.chat_history.find_one(
            {"chat_id": chat_id},
            sort=[("_id", -1)]
        )
        
        last_msg_text = ""
        last_time_display = ""
        
        if last_bucket and last_bucket.get("messages"):
            last_msg_obj = last_bucket["messages"][-1] # 取最后一条
            last_msg_text = last_msg_obj.get("content", "")
            # 格式化时间
            ts = last_msg_obj.get("ts", 0)
            import datetime
            dt = datetime.datetime.fromtimestamp(ts)
            last_time_display = dt.strftime("%H:%M")

        # 4. 组装数据
        contacts_list.append({
            "id": partner_id,
            "username": user.get("username", "Unknown"),
            "avatar": user.get("avatar", ""),
            "lastMessage": last_msg_text,
            "time": last_time_display,
            "unread": 0, # 这里后面可以用 Redis 计算
            "active": False,
            "status": user.get("status", "offline"),
            "messages": [] # 初始不加载历史，点击后再通过 /history 接口加载
        })
        
    return contacts_list

@router.get("/history", response_model=List[Message])
async def get_messages(
    chat_id: str = Query(..., description="会话ID"),
    limit: int = Query(50, description="获取条数"),
    before_ts: Optional[float] = Query(None, description="游标时间戳")
):
    """获取聊天历史记录 (懒加载)"""
    if not db:
        raise HTTPException(status_code=503, detail="Database not initialized")
        
    msgs = await chat_manager.get_chat_history(chat_id, limit, before_ts)
    return msgs