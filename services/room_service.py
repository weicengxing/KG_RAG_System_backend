"""
植物大战僵尸多人对战 - 房间管理服务（简化版）
"""

import redis.asyncio as redis
import json
import uuid
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD

logger = logging.getLogger(__name__)


class SimplePvZRoomManager:
    """简化版房间管理器 - 无服务器权威校验，直接转发客户端请求"""
    
    def __init__(self):
        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        self.ROOM_TTL = 3600  # 房间过期时间，1小时
    
    async def _generate_unique_room_code(self) -> str:
        """生成6位唯一房间码 (数字+大写字母)"""
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for _ in range(10):  # 最多尝试10次
            room_code = ''.join(random.choice(chars) for _ in range(6))
            # 检查房间码是否已存在
            existing = await self.redis.exists(f"pvz:room_code:{room_code}")
            if existing == 0:
                return room_code
        raise Exception("无法生成唯一房间码")
    
    async def create_room(self, user_id: str, username: str) -> Tuple[Optional[Dict], str]:
        """创建房间，并自动生成房间码"""
        # 检查用户是否已在其他房间
        existing_room_id = await self.redis.get(f"pvz:user_room:{user_id}")
        if existing_room_id:
            existing_room_data = await self.redis.get(f"pvz:room:{existing_room_id}")
            if existing_room_data:
                room = json.loads(existing_room_data)
                if room.get("status") in ["waiting", "playing", "ready"]:
                    return None, "您已在其他房间中，请先离开"
        
        # 生成唯一房间码
        try:
            room_code = await self._generate_unique_room_code()
        except Exception as e:
            logger.error(f"生成房间码失败: {e}")
            return None, "生成房间码失败，请重试"
        
        room_id = f"room_{uuid.uuid4().hex[:8]}"
        
        room_state = {
            "room_id": room_id,
            "room_code": room_code,
            "status": "waiting",
            "plant_player": user_id,
            "plant_player_username": username,
            "zombie_player": None,
            "zombie_player_username": None,
            "created_at": datetime.utcnow().isoformat(),
            "game_state": None
        }
        
        # 存储房间信息
        await self.redis.setex(
            f"pvz:room:{room_id}",
            self.ROOM_TTL,
            json.dumps(room_state)
        )
        
        # 存储房间码映射
        await self.redis.setex(
            f"pvz:room_code:{room_code}",
            self.ROOM_TTL,
            room_id
        )
        
        # 存储用户房间映射
        await self.redis.setex(
            f"pvz:user_room:{user_id}",
            self.ROOM_TTL,
            room_id
        )
        
        # 维护活跃房间索引 (ZSET)
        await self.redis.zadd("pvz:active_rooms", {room_id: datetime.utcnow().timestamp()})
        
        logger.info(f"房间创建成功: {room_id} by {user_id}")
        return room_state, "房间创建成功"
    
    async def join_room(self, room_code: str, user_id: str, username: str) -> Tuple[Optional[Dict], str]:
        """加入游戏房间"""
        # 检查用户是否已在其他房间
        existing_room_id = await self.redis.get(f"pvz:user_room:{user_id}")
        if existing_room_id:
            existing_room_data = await self.redis.get(f"pvz:room:{existing_room_id}")
            if existing_room_data:
                room = json.loads(existing_room_data)
                if room.get("status") in ["waiting", "playing", "ready"]:
                    return None, "您已在其他房间中，请先离开"
        
        room_id = await self.redis.get(f"pvz:room_code:{room_code}")
        if not room_id:
            return None, "房间不存在或已过期"
        
        room_data = await self.redis.get(f"pvz:room:{room_id}")
        if not room_data:
            return None, "房间不存在或已过期"
        
        room_state = json.loads(room_data)
        
        if room_state["status"] != "waiting":
            return None, "房间正在进行中或已结束"
        
        if room_state["plant_player"] == user_id:
            return room_state, "您是植物玩家，无需重复加入"
        if room_state["zombie_player"] is not None:
            return None, "房间已有僵尸玩家"
        
        # 原子更新房间状态
        pipe = self.redis.pipeline()
        pipe.watch(f"pvz:room:{room_id}")
        
        try:
            room_state["zombie_player"] = user_id
            room_state["zombie_player_username"] = username
            room_state["status"] = "ready"
            
            pipe.multi()
            pipe.setex(
                f"pvz:room:{room_id}",
                self.ROOM_TTL,
                json.dumps(room_state)
            )
            pipe.setex(
                f"pvz:user_room:{user_id}",
                self.ROOM_TTL,
                room_id
            )
            await pipe.execute()
            
            logger.info(f"玩家 {user_id} 加入房间 {room_id}")
            return room_state, "成功加入房间"
        except redis.WatchError:
            return None, "房间状态已被修改，请重试"
        finally:
            pipe.reset()
    
    async def leave_room(self, user_id: str) -> Tuple[bool, str]:
        """离开游戏房间"""
        room_id = await self.redis.get(f"pvz:user_room:{user_id}")
        if not room_id:
            return True, "未加入任何房间"
        
        room_data = await self.redis.get(f"pvz:room:{room_id}")
        if not room_data:
            # 房间可能已过期，删除用户映射即可
            await self.redis.delete(f"pvz:user_room:{user_id}")
            return True, "房间不存在或已过期"
        
        room_state = json.loads(room_data)
        
        is_plant = (room_state["plant_player"] == user_id)
        is_zombie = (room_state["zombie_player"] == user_id)

        if not (is_plant or is_zombie):
            return False, "您不是该房间的玩家"
        
        # 更新房间状态
        if is_plant:
            # 植物玩家（房主）离开，直接删除房间
            room_state["status"] = "finished"
            await self.redis.delete(f"pvz:room:{room_id}")
            await self.redis.delete(f"pvz:room_code:{room_state['room_code']}")
            await self.redis.zrem("pvz:active_rooms", room_id)
            
            # 同时删除僵尸玩家的房间映射
            if room_state["zombie_player"]:
                await self.redis.delete(f"pvz:user_room:{room_state['zombie_player']}")
            
            logger.info(f"房主 {user_id} 离开，房间 {room_id} 已删除")
        elif is_zombie:
            # 僵尸玩家离开，房间继续等待
            room_state["zombie_player"] = None
            room_state["zombie_player_username"] = None
            room_state["status"] = "waiting"
            
            await self.redis.setex(
                f"pvz:room:{room_id}",
                self.ROOM_TTL,
                json.dumps(room_state)
            )
        
        # 删除当前用户的房间映射
        await self.redis.delete(f"pvz:user_room:{user_id}")
        
        logger.info(f"玩家 {user_id} 离开房间 {room_id}，房间状态变为 {room_state['status']}")
        return True, "已离开房间"
    
    async def get_room(self, room_id: str) -> Optional[Dict]:
        """获取房间信息"""
        room_data = await self.redis.get(f"pvz:room:{room_id}")
        if room_data:
            return json.loads(room_data)
        return None
    
    async def get_user_room(self, user_id: str) -> Optional[Dict]:
        """获取用户的房间信息"""
        room_id = await self.redis.get(f"pvz:user_room:{user_id}")
        if room_id:
            return await self.get_room(room_id)
        return None
    
    async def update_room_state(self, room_id: str, game_state: Dict) -> bool:
        """更新房间游戏状态"""
        room_data = await self.redis.get(f"pvz:room:{room_id}")
        if not room_data:
            return False
        
        room_state = json.loads(room_data)
        room_state["game_state"] = game_state
        
        await self.redis.setex(
            f"pvz:room:{room_id}",
            self.ROOM_TTL,
            json.dumps(room_state)
        )
        return True
    
    async def update_room_status(self, room_id: str, status: str) -> bool:
        """更新房间状态"""
        room_data = await self.redis.get(f"pvz:room:{room_id}")
        if not room_data:
            return False
        
        room_state = json.loads(room_data)
        room_state["status"] = status
        
        await self.redis.setex(
            f"pvz:room:{room_id}",
            self.ROOM_TTL,
            json.dumps(room_state)
        )
        return True

    async def destroy_room(self, room_id: str) -> bool:
        """彻底解散房间，并清理房间码、用户映射和活跃房间索引"""
        room_data = await self.redis.get(f"pvz:room:{room_id}")
        if not room_data:
            await self.redis.zrem("pvz:active_rooms", room_id)
            return False

        room_state = json.loads(room_data)
        keys_to_delete = [
            f"pvz:room:{room_id}",
            f"pvz:room_code:{room_state.get('room_code')}",
        ]

        for player_key in ("plant_player", "zombie_player"):
            player_id = room_state.get(player_key)
            if player_id:
                keys_to_delete.append(f"pvz:user_room:{player_id}")

        await self.redis.delete(*keys_to_delete)
        await self.redis.zrem("pvz:active_rooms", room_id)

        logger.info(f"房间 {room_id} 已彻底解散")
        return True
    
    async def get_active_rooms(self, count: int = 50) -> List[Dict]:
        """获取活跃房间列表"""
        room_ids = await self.redis.zrevrange("pvz:active_rooms", 0, count - 1)
        
        if not room_ids:
            return []
        
        # 批量获取房间数据
        room_keys = [f"pvz:room:{rid}" for rid in room_ids]
        room_datas = await self.redis.mget(room_keys)
        
        rooms = []
        for data in room_datas:
            if data:
                room_state = json.loads(data)
                if room_state["status"] in ["waiting", "ready"]:
                    rooms.append(room_state)
        return rooms

# 全局实例
simple_room_manager = SimplePvZRoomManager()
