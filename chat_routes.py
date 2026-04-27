"""
聊天系统路由模块
集成 MongoDB (Motor) 分桶存储与 Redis Pub/Sub 实时推送
实现极致性能的实时通讯接口
"""

import json
import time
import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import database
from utils import decode_token_with_exp, extract_user_info_from_payload
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, Depends, status, UploadFile, File, Header
from fastapi.responses import FileResponse
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

# ==================== 文件存储配置 ====================

# 文件存储根路径
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

# 不同类型文件的存储路径
FILE_STORAGE = {
    "image": ASSETS_DIR / "chat_pic",
    "document": ASSETS_DIR / "chat_fil",
    "video": ASSETS_DIR / "chat_ved"
}

# 文件类型映射 (根据扩展名判断)
FILE_TYPE_MAP = {
    # 图片
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image",
    ".webp": "image", ".bmp": "image", ".svg": "image",
    # 文档
    ".pdf": "document", ".doc": "document", ".docx": "document",
    ".txt": "document", ".md": "document", ".xls": "document",
    ".xlsx": "document", ".ppt": "document", ".pptx": "document",
    # 视频
    ".mp4": "video", ".avi": "video", ".mov": "video",
    ".wmv": "video", ".flv": "video", ".mkv": "video"
}

# 每个子文件夹最多存储的文件数
MAX_FILES_PER_FOLDER = 500

# ==================== 数据模型 (Pydantic) ====================

class Message(BaseModel):
    msg_id: str
    sender_id: str
    content: str  # 文本消息时为文本内容,文件消息时为文件路径,群邀请卡片时为群组ID
    ts: float
    type: str = "text"  # text, image, document, video, group_invite_card
    filename: Optional[str] = None  # 文件消息时的原始文件名
    file_size: Optional[int] = None  # 文件大小(字节)
    group_data: Optional[dict] = None  # 群邀请卡片消息的群组数据
    sender_username: Optional[str] = None  # 群聊消息中发送者的用户名
    sender_avatar: Optional[str] = None  # 群聊消息中发送者的头像文件名
    sender_avatar_base64: Optional[str] = None  # 群聊消息中发送者的头像base64数据（后端直接返回）

    class Config:
        # 允许额外的字段（向后兼容）
        extra = "allow"

class ChatSession(BaseModel):
    chat_id: str
    partner_id: str
    partner_name: str
    partner_avatar: str
    last_message: str
    last_time: str
    unread: int

# ==================== 文件管理辅助函数 ====================

def get_file_type(filename: str) -> str:
    """根据文件扩展名判断文件类型"""
    ext = Path(filename).suffix.lower()
    return FILE_TYPE_MAP.get(ext, "document")  # 默认当做文档处理

def get_or_create_subfolder(file_type: str) -> Path:
    """
    获取或创建用于存储文件的子文件夹
    逻辑: 查找未满的最新子文件夹,如果都满了则创建新的
    """
    base_path = FILE_STORAGE[file_type]
    base_path.mkdir(parents=True, exist_ok=True)

    # 查找所有已存在的子文件夹
    subfolders = sorted([d for d in base_path.iterdir() if d.is_dir()])

    # 检查最新的子文件夹是否未满
    if subfolders:
        latest_folder = subfolders[-1]
        file_count = len(list(latest_folder.glob("*")))
        if file_count < MAX_FILES_PER_FOLDER:
            return latest_folder

    # 创建新的子文件夹 (命名规则: subfolder_0, subfolder_1, ...)
    new_index = len(subfolders)
    new_folder = base_path / f"subfolder_{new_index}"
    new_folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 创建新子文件夹: {new_folder}")

    return new_folder

async def save_uploaded_file(file: UploadFile) -> dict:
    """
    保存上传的文件并返回文件信息
    返回格式: {"file_path": "相对路径", "file_type": "类型", "filename": "原始文件名", "size": 文件大小}
    """
    try:
        # 1. 判断文件类型
        file_type = get_file_type(file.filename)

        # 2. 获取存储文件夹
        storage_folder = get_or_create_subfolder(file_type)

        # 3. 生成唯一文件名 (保留原始扩展名)
        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        file_path = storage_folder / unique_filename

        # 4. 保存文件
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 5. 计算相对路径 (相对于 assets 目录)
        relative_path = file_path.relative_to(ASSETS_DIR)

        logger.info(f"✅ 文件已保存: {relative_path} ({len(content)} bytes)")

        return {
            "file_path": str(relative_path).replace("\\", "/"),  # 统一使用正斜杠
            "file_type": file_type,
            "filename": file.filename,
            "size": len(content)
        }

    except Exception as e:
        logger.error(f"❌ 保存文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


# ==================== 核心服务类: ChatManager ====================

class ChatManager:
    """聊天核心服务管理器
    负责 WebSocket 连接管理、Redis 消息广播、MongoDB 分桶存储
    """
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.BUCKET_SIZE = 50  # 每个桶存储的消息数量

    async def increment_unread_count(self, user_id: str, chat_id: str):
        """增加用户对指定会话的未读消息数"""
        try:
            await db.unread_counts.update_one(
                {"user_id": user_id, "chat_id": chat_id},
                {
                    "$inc": {"unread_count": 1},
                    "$set": {"last_updated": time.time()}
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"❌ 增加未读数失败 user={user_id}, chat={chat_id}: {e}")

    async def reset_unread_count(self, user_id: str, chat_id: str):
        """清零用户对指定会话的未读消息数"""
        try:
            await db.unread_counts.update_one(
                {"user_id": user_id, "chat_id": chat_id},
                {
                    "$set": {
                        "unread_count": 0,
                        "last_updated": time.time()
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"❌ 清零未读数失败 user={user_id}, chat={chat_id}: {e}")

    async def get_unread_count(self, user_id: str, chat_id: str) -> int:
        """获取用户对指定会话的未读消息数"""
        try:
            doc = await db.unread_counts.find_one(
                {"user_id": user_id, "chat_id": chat_id}
            )
            return doc.get("unread_count", 0) if doc else 0
        except Exception as e:
            logger.error(f"❌ 获取未读数失败 user={user_id}, chat={chat_id}: {e}")
            return 0
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"🔌 WebSocket 连接建立: {user_id}")

        # 将用户添加到Redis在线用户集合
        try:
            await redis_async.sadd("online_users", user_id)
            logger.info(f"✅ 用户已上线: {user_id}")
        except Exception as e:
            logger.error(f"❌ 添加在线用户失败: {user_id}, {e}")

        # 用户上线，启动 Redis 订阅任务
        asyncio.create_task(self._subscribe_to_user_channel(user_id, websocket))

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"🔌 WebSocket 连接断开: {user_id}")

            # 从Redis在线用户集合中移除用户
            try:
                asyncio.create_task(self._remove_online_user(user_id))
            except Exception as e:
                logger.error(f"❌ 移除在线用户失败: {user_id}, {e}")

    async def _remove_online_user(self, user_id: str):
        """从Redis在线集合中移除用户"""
        try:
            await redis_async.srem("online_users", user_id)
            logger.info(f"✅ 用户已下线: {user_id}")
        except Exception as e:
            logger.error(f"❌ 移除在线用户失败: {user_id}, {e}")

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
        4. 增加接收者的未读消息数
        """
        sender = msg_data['sender_id']
        receiver = msg_data['receiver_id']

        # 1. 生成 chat_id (确保顺序一致，如 "min_max")
        ids = sorted([sender, receiver])
        chat_id = f"{ids[0]}_{ids[1]}"

        # 2. 存入 MongoDB (极速分桶写入)
        await self._save_to_mongodb(chat_id, msg_data)

        # 3. 增加接收者的未读消息数
        await self.increment_unread_count(receiver, chat_id)

        # 4. 序列化消息
        payload = json.dumps({
            "type": "new_message",
            "chat_id": chat_id,
            "data": msg_data
        })

        # 5. 广播消息 (无论用户是否在线，先推到 Redis)
        # 推送给接收者
        await redis_async.publish(f"chat:user:{receiver}", payload)
        # 推送给发送者 (为了多设备同步，或者简单的 ACK)
        await redis_async.publish(f"chat:user:{sender}", payload)

    async def send_group_message(self, msg_data: dict):
        """发送群聊消息流程:
        1. 验证用户是否是群成员
        2. 获取发送者用户信息（头像、用户名）- 从 Neo4j 数据库读取
        3. 存入 MongoDB (分桶，chat_id格式为 group:群组ID)
        4. 增加所有群成员（除发送者外）的未读消息数
        5. 推送给所有群成员 (Redis Pub/Sub)
        """
        sender = str(msg_data['sender_id'])  # 🔧 统一转换为字符串
        group_id = msg_data['group_id']

        # 1. 验证群组存在且用户是成员
        group = await db.groups.find_one({"_id": group_id})
        if not group:
            logger.error(f"❌ 群组不存在: {group_id}")
            return

        if sender not in group.get("members", []):
            logger.error(f"❌ 用户 {sender} 不是群 {group_id} 的成员")
            return

        # 2. 从 Neo4j 获取发送者的用户信息（用于前端显示头像和名字）
        # 【修复】确保从 Neo4j 查询真实的头像路径，而不是用时间戳拼接
        sender_info = None
        try:
            # 从 Neo4j 获取完整的用户信息
            sender_info = database.get_user_by_id(sender)
            if sender_info:
                logger.info(f"✅ 成功从 Neo4j 获取发送者信息: {sender} -> username={sender_info.get('username')}, avatar={sender_info.get('avatar')}")
            else:
                logger.warning(f"⚠️ Neo4j 中找不到发送者: {sender}，将使用默认值")
        except Exception as e:
            logger.error(f"❌ 从 Neo4j 查询发送者信息失败: {sender}, 错误: {e}")

        # 将发送者信息附加到消息数据中
        if sender_info:
            msg_data['sender_username'] = sender_info.get('username', 'Unknown')
            avatar_filename = sender_info.get('avatar', '')
            msg_data['sender_avatar'] = avatar_filename  # 保留文件名用于存储

            # 将头像文件读取并转为 base64 发给前端
            if avatar_filename:
                # 如果是完整URL（默认头像），直接使用
                if avatar_filename.startswith('http://') or avatar_filename.startswith('https://'):
                    msg_data['sender_avatar_base64'] = avatar_filename
                else:
                    # 如果是文件名，从文件系统读取并转为 base64
                    try:
                        from pathlib import Path
                        import base64
                        avatar_path = Path(__file__).resolve().parent / "assets" / "avatars" / avatar_filename

                        if avatar_path.exists() and avatar_path.is_file():
                            with open(avatar_path, "rb") as f:
                                avatar_bytes = f.read()
                                ext = avatar_path.suffix.lower()
                                mime_type = {
                                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                                    '.png': 'image/png', '.gif': 'image/gif',
                                    '.webp': 'image/webp'
                                }.get(ext, 'image/jpeg')
                                msg_data['sender_avatar_base64'] = f"data:{mime_type};base64,{base64.b64encode(avatar_bytes).decode('utf-8')}"
                        else:
                            msg_data['sender_avatar_base64'] = ''
                    except Exception as e:
                        logger.error(f"❌ 读取发送者头像文件失败: {avatar_filename}, 错误: {e}")
                        msg_data['sender_avatar_base64'] = ''
            else:
                msg_data['sender_avatar_base64'] = ''

            logger.info(f"📎 群聊消息已附加发送者信息: msg_id={msg_data.get('msg_id')}, username={msg_data['sender_username']}, avatar={avatar_filename}, has_base64={bool(msg_data.get('sender_avatar_base64'))}")
        else:
            # 【修复】即使查询失败，也要设置默认值，确保字段存在
            msg_data['sender_username'] = 'Unknown'
            msg_data['sender_avatar'] = ''
            msg_data['sender_avatar_base64'] = ''
            logger.warning(f"⚠️ 群聊消息使用默认发送者信息: sender_id={sender}, msg_id={msg_data.get('msg_id')}")

        # 3. 生成 chat_id (群聊格式: group:群组ID)
        chat_id = f"group:{group_id}"

        # 4. 存入 MongoDB (复用分桶机制)
        await self._save_to_mongodb(chat_id, msg_data)

        # 5. 增加所有群成员（除发送者外）的未读消息数
        for member_id in group.get("members", []):
            if member_id != sender:
                await self.increment_unread_count(member_id, chat_id)

        # 6. 序列化消息
        # 【调试】打印消息数据，确认字段存在
        logger.info(f"🔍 准备广播群聊消息: msg_id={msg_data.get('msg_id')}, sender_id={sender}, "
                   f"sender_username={msg_data.get('sender_username')}, "
                   f"sender_avatar={msg_data.get('sender_avatar')}, "
                   f"has_avatar_base64={bool(msg_data.get('sender_avatar_base64'))}")

        try:
            payload = json.dumps({
                "type": "new_group_message",
                "chat_id": chat_id,
                "group_id": group_id,
                "data": msg_data
            })

            # 【检查】payload 大小
            payload_size_kb = len(payload) / 1024
            logger.info(f"📦 消息 payload 大小: {payload_size_kb:.2f}KB")

            if payload_size_kb > 1024:  # 超过 1MB
                logger.warning(f"⚠️ 消息 payload 过大: {payload_size_kb:.2f}KB，可能导致传输失败")

        except Exception as e:
            logger.error(f"❌ JSON 序列化失败: {e}")
            return

        # 7. 广播给所有群成员
        for member_id in group.get("members", []):
            try:
                await redis_async.publish(f"chat:user:{member_id}", payload)
            except Exception as e:
                logger.error(f"❌ Redis 发布失败 (member={member_id}): {e}")

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
        """
        极致优化版历史记录查询：
        1. 充分利用 (chat_id, created_at) 复合索引
        2. 使用 before_ts 在查询层过滤掉新桶，实现毫秒级响应
        3. 【新增】对于群聊消息，自动从 Neo4j 补充缺失的发送者信息
        """
        try:
            # --- 核心改进：查询条件 ---
            query = {"chat_id": chat_id}

            if before_ts:
                # 改进点：不再是在内存里 filter，而是直接告诉 Mongo：
                # "请给我找桶的【创建时间】早于我当前最老消息时间戳的那些桶"
                # 这样 Mongo 会直接通过 B-Tree 索引跳过所有新桶
                query["created_at"] = {"$lt": before_ts}

            # --- 核心改进：排序与性能 ---
            # 按照创建时间倒序排，每次拿 2 个桶（约100条消息），确保能凑够 limit=50 条
            cursor = db.chat_history.find(query).sort("created_at", -1).limit(2)

            all_messages = []
            async for bucket in cursor:
                msgs = bucket.get("messages", [])

                # 即使桶被定位到了，桶内消息数组中可能仍有部分消息比 before_ts 新（针对同一个桶内的分页）
                if before_ts:
                    msgs = [m for m in msgs if m['ts'] < before_ts]

                # 桶内是旧->新，我们要把旧桶的消息放在列表前面
                all_messages = msgs + all_messages

                # 如果凑够了用户需要的条数，就停下，不再读取更多文档
                if len(all_messages) >= limit:
                    break

            # 对于群聊消息，将头像文件读取并转为 base64 发给前端
            is_group_chat = chat_id.startswith("group:")
            if is_group_chat and all_messages:
                logger.info(f"📋 群聊历史消息加载: chat_id={chat_id}, 消息数={len(all_messages)}")

                # 收集需要加载头像的发送者（避免重复读取）
                avatar_cache = {}

                for msg in all_messages:
                    sender_id = msg.get('sender_id')
                    avatar_filename = msg.get('sender_avatar', '')

                    # 【调试】打印消息原始数据
                    logger.debug(f"🔍 处理历史消息: msg_id={msg.get('msg_id')}, sender_id={sender_id}, "
                                f"sender_username={msg.get('sender_username')}, sender_avatar={avatar_filename}")

                    # 如果已经缓存过这个头像，直接使用
                    if avatar_filename and avatar_filename in avatar_cache:
                        msg['sender_avatar_base64'] = avatar_cache[avatar_filename]
                        logger.debug(f"✅ 使用缓存头像: {avatar_filename}")
                        continue

                    # 如果是完整URL（默认头像），直接使用
                    if avatar_filename and (avatar_filename.startswith('http://') or avatar_filename.startswith('https://')):
                        msg['sender_avatar_base64'] = avatar_filename
                        avatar_cache[avatar_filename] = avatar_filename
                        logger.debug(f"✅ 使用URL头像: {avatar_filename}")
                        continue

                    # 如果是文件名，从文件系统读取并转为 base64
                    if avatar_filename:
                        try:
                            from pathlib import Path
                            import base64
                            # 头像文件存储在 backend/assets/avatars 目录
                            avatar_path = Path(__file__).resolve().parent / "assets" / "avatars" / avatar_filename

                            if avatar_path.exists() and avatar_path.is_file():
                                with open(avatar_path, "rb") as f:
                                    avatar_bytes = f.read()
                                    # 根据文件扩展名判断 MIME 类型
                                    ext = avatar_path.suffix.lower()
                                    mime_type = {
                                        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                                        '.png': 'image/png', '.gif': 'image/gif',
                                        '.webp': 'image/webp'
                                    }.get(ext, 'image/jpeg')

                                    avatar_base64 = f"data:{mime_type};base64,{base64.b64encode(avatar_bytes).decode('utf-8')}"

                                    # 【检查】base64 数据大小
                                    base64_size_kb = len(avatar_base64) / 1024
                                    if base64_size_kb > 500:  # 超过 500KB
                                        logger.warning(f"⚠️ 头像 base64 数据过大: {avatar_filename}, {base64_size_kb:.2f}KB，将使用文件名")
                                        msg['sender_avatar_base64'] = ''
                                    else:
                                        msg['sender_avatar_base64'] = avatar_base64
                                        avatar_cache[avatar_filename] = avatar_base64
                                        logger.info(f"✅ 加载头像文件成功: {avatar_filename} -> base64 {base64_size_kb:.2f}KB")
                            else:
                                logger.warning(f"⚠️ 头像文件不存在: {avatar_path}")
                                msg['sender_avatar_base64'] = ''
                        except Exception as e:
                            logger.error(f"❌ 读取头像文件失败: {avatar_filename}, 错误: {e}")
                            msg['sender_avatar_base64'] = ''
                    else:
                        msg['sender_avatar_base64'] = ''

                # 【调试】打印最终返回的消息数据样本
                if all_messages:
                    sample_msg = all_messages[0]
                    logger.info(f"🔍 历史消息样本: msg_id={sample_msg.get('msg_id')}, "
                               f"sender_username={sample_msg.get('sender_username')}, "
                               f"has_avatar_base64={bool(sample_msg.get('sender_avatar_base64'))}")

            # 返回最后 limit 条（最靠近当前时间的旧消息）
            return all_messages[-limit:]

        except Exception as e:
            logger.error(f"❌ 高效获取历史记录失败: {chat_id}, {e}")
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
            # 为未读消息数集合创建唯一索引
            await db.unread_counts.create_index([("user_id", 1), ("chat_id", 1)], unique=True)
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
        # 兼容新旧两种 token 格式
        # 新格式: {"user_id": "xxx", "username": "xxx"}
        # 旧格式: {"sub": "username"}
        token_user_id = payload.get("user_id") or payload.get("sub")
        token_username = payload.get("username") or payload.get("sub")

        # 前端传来的 URL 路径中的 user_id 必须等于 Token 中的 user_id
        # 为了兼容性,转字符串比较
        if str(token_user_id) != str(user_id):
            logger.warning(f"[WS] ❌ 连接拒绝: 身份不匹配 (Token user_id: {token_user_id} != URLPath: {user_id})")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # (可选) 更新活跃时间
        try:
            database.update_last_activity(str(token_user_id))
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
            
            # === Token检查逻辑（类似main.py中间件）===
            try:
                payload, is_expired, error_msg = decode_token_with_exp(token)
                
                if payload is None:
                    logger.warning(f"[WS] Token无效，断开连接: {user_id}")
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    break
                    
                if is_expired:
                    # 检查24小时窗口
                    exp_timestamp = payload.get("exp", 0)
                    current_timestamp = time.time()
                    grace_period_seconds = 24 * 60 * 60
                    
                    if current_timestamp > (exp_timestamp + grace_period_seconds):
                        logger.warning(f"[WS] Token彻底过期，断开连接: {user_id}")
                        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                        break
                    else:
                        # 在宽限期内，生成新token
                        from utils import create_token_with_user_info, create_access_token
                        
                        if payload.get("user_id"):
                            new_token = create_token_with_user_info(
                                payload["user_id"], 
                                payload.get("username", "")
                            )
                        else:
                            new_token = create_access_token(data={"sub": payload.get("sub")})
                        
                        # 通过WebSocket发送新token给前端
                        await websocket.send_text(json.dumps({
                            "type": "token_refresh",
                            "new_token": new_token
                        }))
                        
                        # 更新token变量和活跃时间
                        token = new_token
                        database.update_last_activity(user_id)
                        logger.info(f"[WS] Token已刷新: {user_id}")
            
            except Exception as e:
                logger.error(f"[WS] Token检查异常: {e}")
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                break
            
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
                msg_type = msg_obj.get("msg_type", "text")  # 消息类型: text, image, document, video, group_invite_card
                filename = msg_obj.get("filename")  # 文件消息时的原始文件名
                file_size = msg_obj.get("file_size")  # 文件大小

                if target_id and content:
                    current_ts = time.time()
                    msg_content = {
                        "msg_id": f"{user_id}-{int(current_ts * 1000)}",
                        "sender_id": user_id,
                        "receiver_id": target_id,
                        "content": content,
                        "ts": current_ts,
                        "type": msg_type
                    }

                    # 如果是文件消息,添加文件相关信息
                    if msg_type in ["image", "document", "video"]:
                        msg_content["filename"] = filename
                        msg_content["file_size"] = file_size

                    # 如果是群邀请卡片消息,添加群组信息
                    if msg_type == "group_invite_card":
                        msg_content["group_data"] = msg_obj.get("group_data", {})

                    await chat_manager.send_personal_message(msg_content)

            # 发送群聊消息
            if msg_obj.get("type") == "group_message":
                group_id = msg_obj.get("group_id")
                content = msg_obj.get("content")
                msg_type = msg_obj.get("msg_type", "text")
                filename = msg_obj.get("filename")
                file_size = msg_obj.get("file_size")

                if group_id and content:
                    current_ts = time.time()
                    msg_content = {
                        "msg_id": f"{user_id}-{int(current_ts * 1000)}",
                        "sender_id": user_id,
                        "group_id": group_id,
                        "content": content,
                        "ts": current_ts,
                        "type": msg_type
                    }

                    # 如果是文件消息,添加文件相关信息
                    if msg_type in ["image", "document", "video"]:
                        msg_content["filename"] = filename
                        msg_content["file_size"] = file_size

                    await chat_manager.send_group_message(msg_content)

            # ==================== WebRTC 信令转发 ====================
            # 处理通话 offer
            if msg_obj.get("type") == "call_offer":
                target_id = msg_obj.get("target_id")
                caller_name = msg_obj.get("caller_name")
                sdp = msg_obj.get("sdp")

                if target_id and sdp:
                    # 转发 offer 给目标用户
                    payload = {
                        "type": "call_offer",
                        "caller_id": user_id,
                        "caller_name": caller_name,
                        "sdp": sdp
                    }
                    if target_id in chat_manager.active_connections:
                        await chat_manager.active_connections[target_id].send_text(json.dumps(payload))
                        logger.info(f"[WebRTC] 转发 call_offer: {user_id} -> {target_id}")

            # 处理通话 answer
            if msg_obj.get("type") == "call_answer":
                target_id = msg_obj.get("target_id")
                sdp = msg_obj.get("sdp")

                if target_id and sdp:
                    # 转发 answer 给发起方（附加应答者的 ID）
                    payload = {
                        "type": "call_answer",
                        "caller_id": user_id,  # 添加应答者的 ID
                        "sdp": sdp
                    }
                    if target_id in chat_manager.active_connections:
                        await chat_manager.active_connections[target_id].send_text(json.dumps(payload))
                        logger.info(f"[WebRTC] 转发 call_answer: {user_id} -> {target_id}")

            # 处理 ICE candidate
            if msg_obj.get("type") == "ice_candidate":
                target_id = msg_obj.get("target_id")
                candidate = msg_obj.get("candidate")

                if target_id and candidate:
                    # 转发 ICE candidate 给对方（附加发送者的 ID）
                    payload = {
                        "type": "ice_candidate",
                        "caller_id": user_id,  # 添加发送者的 ID（关键修复！）
                        "target_id": target_id,  # 添加目标 ID（关键修复！）
                        "candidate": candidate
                    }
                    if target_id in chat_manager.active_connections:
                        await chat_manager.active_connections[target_id].send_text(json.dumps(payload))
                        logger.info(f"[WebRTC] 转发 ice_candidate: {user_id} -> {target_id}")

            # 处理挂断
            if msg_obj.get("type") == "call_hangup":
                target_id = msg_obj.get("target_id")

                if target_id:
                    # 转发挂断信号给对方
                    payload = {
                        "type": "call_hangup"
                    }
                    if target_id in chat_manager.active_connections:
                        await chat_manager.active_connections[target_id].send_text(json.dumps(payload))
                        logger.info(f"[WebRTC] 转发 call_hangup: {user_id} -> {target_id}")

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
    获取好友列表和群组列表（已合并）
    1. 从 MongoDB contacts 集合查询好友关系
    2. 从 MongoDB groups 集合查询用户加入的群组
    3. 从 Redis 查询在线用户状态
    4. 返回统一格式的联系人列表
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database uninitialized")

    contacts_list = []

    # 获取Redis中所有在线用户
    try:
        online_users = await redis_async.smembers("online_users")
        logger.info(f"📊 当前在线用户: {online_users}")
    except Exception as e:
        logger.error(f"❌ 获取在线用户列表失败: {e}")
        online_users = set()

    # 1. 获取好友列表
    friends_cursor = db.contacts.find({"owner_id": user_id})

    async for contact in friends_cursor:
        friend_id = contact["friend_id"]

        # 从 Neo4j 查询好友用户信息
        friend_user = database.get_user_by_id(friend_id)
        if not friend_user:
            continue

        # 计算 chat_id
        ids = sorted([user_id, friend_id])
        chat_id = f"{ids[0]}_{ids[1]}"

        # 查找最后一条消息
        last_bucket = await db.chat_history.find_one(
            {"chat_id": chat_id},
            sort=[("_id", -1)]
        )

        last_msg_text = ""
        last_time_ts = 0  # 返回时间戳而不是格式化字符串

        if last_bucket and last_bucket.get("messages"):
            last_msg_obj = last_bucket["messages"][-1]
            last_msg_text = last_msg_obj.get("content", "")
            last_time_ts = last_msg_obj.get("ts", 0)  # 直接返回时间戳

        # 判断好友是否在线
        friend_status = "online" if friend_id in online_users else "offline"

        # 获取未读消息数
        unread_count = await chat_manager.get_unread_count(user_id, chat_id)

        contacts_list.append({
            "id": friend_id,
            "username": friend_user.get("username", "Unknown"),
            "avatar": friend_user.get("avatar", "https://i.pravatar.cc/150?u=" + friend_id),
            "lastMessage": last_msg_text,
            "lastTime": last_time_ts,  # 返回时间戳
            "unread": unread_count,
            "active": False,
            "status": friend_status,  # 根据Redis在线集合设置状态
            "messages": [],
            "type": "private"  # 标识为私聊
        })

    # 2. 获取群组列表
    groups_cursor = db.groups.find({"members": user_id})

    async for group in groups_cursor:
        group_id = group["_id"]
        chat_id = f"group:{group_id}"

        # 查找群组最后一条消息
        last_bucket = await db.chat_history.find_one(
            {"chat_id": chat_id},
            sort=[("_id", -1)]
        )

        last_msg_text = ""
        last_time_ts = 0  # 返回时间戳而不是格式化字符串

        if last_bucket and last_bucket.get("messages"):
            last_msg_obj = last_bucket["messages"][-1]
            last_msg_text = last_msg_obj.get("content", "")
            last_time_ts = last_msg_obj.get("ts", 0)  # 直接返回时间戳

        # 获取未读消息数
        unread_count = await chat_manager.get_unread_count(user_id, chat_id)

        contacts_list.append({
            "id": group_id,
            "username": group.get("group_name", "未命名群组"),
            "avatar": group.get("group_avatar", ""),
            "lastMessage": last_msg_text,
            "lastTime": last_time_ts,  # 返回时间戳
            "unread": unread_count,
            "active": False,
            "status": "online",  # 群组总是显示为在线
            "messages": [],
            "type": "group",  # 标识为群聊
            "member_count": len(group.get("members", []))
        })

    return contacts_list

# ==================== 辅助函数 ====================

async def get_current_user_id(authorization: str = Header(None)) -> str:
    """从 Header 获取 Token 并解析出 user_id"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")
    if db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    token = authorization.split(" ")[1] if " " in authorization else authorization
    payload, is_expired, error = decode_token_with_exp(token)

    if not payload or is_expired:
        raise HTTPException(status_code=401, detail="Token invalid or expired")

    user_id, username = extract_user_info_from_payload(payload)
    if user_id:
        user_id = str(user_id)
        try:
            if database.get_user_by_id(user_id):
                return user_id
        except Exception as exc:
            logger.warning(f"Neo4j 用户校验失败，回退 Mongo 用户副本: {exc}")
        mongo_user = await db.users.find_one({"_id": user_id})
        if mongo_user:
            return user_id

    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        neo_user = database.get_user(username)
        if neo_user and neo_user.get("id"):
            return str(neo_user["id"])
    except Exception as exc:
        logger.warning(f"Neo4j 用户名查询失败，回退 Mongo 用户副本: {exc}")

    user = await db.users.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return str(user["_id"])

# ==================== API 接口 ====================

@router.get("/history", response_model=List[Message])
async def get_messages(
    chat_id: str = Query(..., description="会话ID"),
    limit: int = Query(50, description="获取条数"),
    before_ts: Optional[float] = Query(None, description="游标时间戳")
):
    """获取聊天历史记录 (懒加载)"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    msgs = await chat_manager.get_chat_history(chat_id, limit, before_ts)
    return msgs

@router.post("/mark_read")
async def mark_as_read(
    chat_id: str = Query(..., description="会话ID"),
    current_user_id: str = Depends(get_current_user_id)
):
    """标记会话为已读，清零未读消息数"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        await chat_manager.reset_unread_count(current_user_id, chat_id)
        logger.info(f"✅ 已标记为已读: user={current_user_id}, chat={chat_id}")
        return {"success": True, "message": "Marked as read"}
    except Exception as e:
        logger.error(f"❌ 标记已读失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark as read: {str(e)}")

# ==================== 文件上传与访问接口 ====================

@router.post("/upload_file")
async def upload_file(
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    上传聊天文件接口
    支持图片、文档、视频等多种格式
    返回文件信息供前端构造消息
    """
    # 检查文件大小 (限制50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

    # 先读取一小部分来检查
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    # 重置文件指针
    await file.seek(0)

    # 保存文件
    file_info = await save_uploaded_file(file)

    return {
        "success": True,
        "data": file_info
    }

@router.get("/files/{file_path:path}")
async def get_file(file_path: str):
    """
    获取聊天文件
    路径格式: chat_pic/subfolder_0/xxxxx.jpg
    """
    try:
        # 构建完整路径
        full_path = ASSETS_DIR / file_path

        # 安全检查: 确保路径在 assets 目录下 (防止路径遍历攻击)
        if not str(full_path.resolve()).startswith(str(ASSETS_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        # 检查文件是否存在
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        # 返回文件
        return FileResponse(
            path=str(full_path),
            filename=full_path.name,
            media_type="application/octet-stream"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取文件失败: {file_path}, {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve file")

# ==================== 消息撤回接口 ====================

class RecallMessageInput(BaseModel):
    msg_id: str
    chat_id: str

@router.post("/recall")
async def recall_message(
    data: RecallMessageInput,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    撤回消息接口
    1. 验证消息是否属于当前用户
    2. 验证消息是否在2分钟内
    3. 更新MongoDB中的消息状态
    4. 通过Redis通知双方
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        # 1. 查找包含该消息的桶
        bucket = await db.chat_history.find_one({
            "chat_id": data.chat_id,
            "messages.msg_id": data.msg_id
        })

        if not bucket:
            raise HTTPException(status_code=404, detail="Message not found")

        # 2. 查找具体的消息
        message = None
        for msg in bucket.get("messages", []):
            if msg["msg_id"] == data.msg_id:
                message = msg
                break

        if not message:
            raise HTTPException(status_code=404, detail="Message not found in bucket")

        # 3. 验证消息是否属于当前用户
        if message["sender_id"] != current_user_id:
            raise HTTPException(status_code=403, detail="You can only recall your own messages")

        # 4. 验证消息是否在2分钟内
        current_time = time.time()
        time_diff = current_time - message["ts"]
        if time_diff > 120:  # 120秒 = 2分钟
            raise HTTPException(status_code=400, detail="Message can only be recalled within 2 minutes")

        # 5. 更新MongoDB中的消息状态
        # 使用位置更新操作符 $ 来更新数组中匹配的元素
        result = await db.chat_history.update_one(
            {
                "chat_id": data.chat_id,
                "messages.msg_id": data.msg_id
            },
            {
                "$set": {
                    "messages.$.type": "recalled",
                    "messages.$.content": "撤回了一条消息"
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update message")

        # 6. 通过Redis Pub/Sub通知双方
        # 解析chat_id获取双方用户ID
        user_ids = data.chat_id.split("_")
        receiver_id = user_ids[0] if user_ids[1] == current_user_id else user_ids[1]

        recall_payload = json.dumps({
            "type": "message_recalled",
            "data": {
                "msg_id": data.msg_id,
                "chat_id": data.chat_id,
                "recaller_id": current_user_id
            }
        })

        # 通知接收者
        await redis_async.publish(f"chat:user:{receiver_id}", recall_payload)
        # 通知发送者（多端同步）
        await redis_async.publish(f"chat:user:{current_user_id}", recall_payload)

        logger.info(f"✅ 消息已撤回: {data.msg_id} by {current_user_id}")

        return {
            "success": True,
            "message": "Message recalled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 撤回消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to recall message: {str(e)}")


# 技术栈:
# WebSocket - FastAPI WebSocket处理实时通信
# MongoDB (Motor) - 分桶存储聊天历史(每桶50条消息)
# Redis Pub/Sub - 消息广播与多端同步
# Neo4j - 用户系统主数据库
# 核心流程:
# WebSocket鉴权 (chat_routes.py:261-329)
# 验证token有效性
# 支持24小时宽限期(即使token过期)
# 检查身份一致性(token中的sub必须等于URL中的user_id)
# 消息发送 (chat_routes.py:103-130)
# 生成chat_id: 两个用户ID排序后拼接(如user1_user2)
# 分桶存储到MongoDB
# 通过Redis Pub/Sub广播给发送者和接收者
# 分桶存储策略 (chat_routes.py:132-165)
# 每个桶最多50条消息
# 原子更新: 优先追加到未满的桶,满了就创建新桶
# 索引优化: (chat_id, _id) 和 (chat_id, count)
# 联系人列表 (chat_routes.py:381-435)
# 从MongoDB的users集合获取除自己外的所有用户
# 聚合查询每个会话的最后一条消息
# 返回格式化的联系人列表
# 高性能分桶设计,避免单文档过大
# Redis Pub/Sub实现多端实时同步
# 支持离线消息(存MongoDB,上线后拉取)
