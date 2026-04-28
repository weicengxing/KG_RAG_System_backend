"""
植物大战僵尸多人对战 - WebSocket管理器（简化版）
无服务器权威校验，直接转发客户端消息
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import logging
from datetime import datetime

from services.room_service import simple_room_manager

logger = logging.getLogger(__name__)


class SimplePvZWebSocketManager:
    """简化版WebSocket管理器 - 直接转发消息"""
    
    def __init__(self):
        # 活跃连接: {room_id: {user_id: websocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # 大厅连接: {user_id: websocket} - 用于未加入房间的用户监听房间列表变化
        self.lobby_connections: Dict[str, WebSocket] = {}
        # 房间选择状态: {room_id: {"plant_selection": [...], "zombie_selection": [...], "plant_ready": False, "zombie_ready": False}}
        self.room_selections: Dict[str, Dict] = {}
        # 当前序号
        self.sequence_number = 0
    
    async def connect(self, websocket: WebSocket, room_id: str, user_id: str):
        """建立WebSocket连接"""
        await websocket.accept()
        
        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}
        self.active_connections[room_id][user_id] = websocket
        
        logger.info(f"用户 {user_id} 加入房间 {room_id} 的WebSocket连接")
    
    async def connect_lobby(self, websocket: WebSocket, user_id: str):
        """建立大厅WebSocket连接（用于监听房间列表变化）"""
        await websocket.accept()
        self.lobby_connections[user_id] = websocket
        logger.info(f"用户 {user_id} 加入大厅WebSocket连接")
    
    def disconnect(self, room_id: str, user_id: str):
        """断开房间WebSocket连接"""
        if room_id in self.active_connections:
            if user_id in self.active_connections[room_id]:
                del self.active_connections[room_id][user_id]
                logger.info(f"用户 {user_id} 离开房间 {room_id} 的WebSocket连接")
            
            # 如果房间没有连接了，删除房间
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def close_room(self, room_id: str, code: int = 1000, reason: str = "Room closed"):
        """关闭房间内所有WebSocket连接并清理内存状态"""
        connections = list(self.active_connections.get(room_id, {}).values())

        for connection in connections:
            try:
                await connection.close(code=code, reason=reason)
            except Exception as e:
                logger.debug(f"关闭房间 {room_id} 连接失败: {e}")

        self.active_connections.pop(room_id, None)
        self.room_selections.pop(room_id, None)
    
    def disconnect_lobby(self, user_id: str):
        """断开大厅WebSocket连接"""
        if user_id in self.lobby_connections:
            del self.lobby_connections[user_id]
            logger.info(f"用户 {user_id} 离开大厅WebSocket连接")
    
    def get_next_sequence_number(self) -> int:
        """获取下一个序号"""
        self.sequence_number += 1
        return self.sequence_number
    
    async def broadcast_to_room(self, room_id: str, message_type: str, payload: dict):
        """向房间内所有用户广播消息"""
        if room_id not in self.active_connections:
            logger.warning(f"房间 {room_id} 没有活跃连接")
            return
        
        message = {
            "type": message_type,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "sequence_number": self.get_next_sequence_number(),
            "payload": payload
        }
        
        # 找出需要断开的连接
        disconnected_users = []
        
        for user_id, connection in self.active_connections[room_id].items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"向用户 {user_id} 发送消息失败: {e}")
                disconnected_users.append(user_id)
        
        # 清理断开的连接
        for user_id in disconnected_users:
            self.disconnect(room_id, user_id)
    
    async def broadcast_to_lobby(self, message_type: str, payload: dict):
        """向所有大厅用户广播消息（房间列表变化）"""
        if not self.lobby_connections:
            return
        
        message = {
            "type": message_type,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "sequence_number": self.get_next_sequence_number(),
            "payload": payload
        }
        
        # 找出需要断开的连接
        disconnected_users = []
        
        for user_id, connection in self.lobby_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"向大厅用户 {user_id} 发送消息失败: {e}")
                disconnected_users.append(user_id)
        
        # 清理断开的连接
        for user_id in disconnected_users:
            self.disconnect_lobby(user_id)
    
    async def broadcast_to_all(self, message_type: str, payload: dict):
        """向所有用户广播消息（房间用户 + 大厅用户）"""
        # 向房间用户广播
        for room_id in list(self.active_connections.keys()):
            await self.broadcast_to_room(room_id, message_type, payload)
        
        # 向大厅用户广播
        await self.broadcast_to_lobby(message_type, payload)
    
    async def send_to_user(self, room_id: str, user_id: str, message_type: str, payload: dict):
        """向指定用户发送消息"""
        if room_id not in self.active_connections:
            logger.warning(f"房间 {room_id} 没有活跃连接")
            return False
        
        if user_id not in self.active_connections[room_id]:
            logger.warning(f"用户 {user_id} 不在房间 {room_id} 中")
            return False
        
        message = {
            "type": message_type,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "sequence_number": self.get_next_sequence_number(),
            "payload": payload
        }
        
        try:
            await self.active_connections[room_id][user_id].send_json(message)
            return True
        except Exception as e:
            logger.error(f"向用户 {user_id} 发送消息失败: {e}")
            self.disconnect(room_id, user_id)
            return False
    
    async def send_to_lobby_user(self, user_id: str, message_type: str, payload: dict):
        """向指定大厅用户发送消息"""
        if user_id not in self.lobby_connections:
            logger.warning(f"大厅用户 {user_id} 没有活跃连接")
            return False
        
        message = {
            "type": message_type,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "sequence_number": self.get_next_sequence_number(),
            "payload": payload
        }
        
        try:
            await self.lobby_connections[user_id].send_json(message)
            return True
        except Exception as e:
            logger.error(f"向大厅用户 {user_id} 发送消息失败: {e}")
            self.disconnect_lobby(user_id)
            return False
    
    async def broadcast_to_others(self, room_id: str, exclude_user_id: str, message_type: str, payload: dict):
        """向房间内其他用户广播消息（排除指定用户）"""
        if room_id not in self.active_connections:
            logger.warning(f"房间 {room_id} 没有活跃连接")
            return
        
        message = {
            "type": message_type,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "sequence_number": self.get_next_sequence_number(),
            "payload": payload
        }
        
        # 找出需要断开的连接
        disconnected_users = []
        
        for user_id, connection in self.active_connections[room_id].items():
            if user_id == exclude_user_id:
                continue # 排除指定用户
            
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"向用户 {user_id} 发送消息失败: {e}")
                disconnected_users.append(user_id)
        
        # 清理断开的连接
        for user_id in disconnected_users:
            self.disconnect(room_id, user_id)
    
    def get_room_connections_count(self, room_id: str) -> int:
        """获取房间内的连接数"""
        if room_id not in self.active_connections:
            return 0
        return len(self.active_connections[room_id])
    
    def get_lobby_connections_count(self) -> int:
        """获取大厅的连接数"""
        return len(self.lobby_connections)
    
    def get_user_role(self, room_id: str, user_id: str) -> str:
        """获取用户在房间中的角色（植物/僵尸）"""
        return "unknown"
    
    async def handle_plant_selection(self, room_id: str, user_id: str, selected_plants: list):
        """处理植物选择完成"""
        if room_id not in self.room_selections:
            self.room_selections[room_id] = {
                "plant_selection": [],
                "zombie_selection": [],
                "plant_ready": False,
                "zombie_ready": False
            }
        
        # 保存植物选择
        self.room_selections[room_id]["plant_selection"] = selected_plants
        self.room_selections[room_id]["plant_ready"] = True
        
        logger.info(f"房间 {room_id} 植物玩家 {user_id} 完成选择: {selected_plants}")
        
        await self.send_to_user(room_id, user_id, "event.plant_selection_confirmed", {
            "room_id": room_id,
            "message": "植物选择已确认，等待僵尸玩家...",
            "plant_selection": selected_plants
        })

        await self.check_both_selections_ready(room_id)
    
    async def handle_zombie_selection(self, room_id: str, user_id: str, selected_zombies: list):
        """处理僵尸选择完成"""
        if room_id not in self.room_selections:
            self.room_selections[room_id] = {
                "plant_selection": [],
                "zombie_selection": [],
                "plant_ready": False,
                "zombie_ready": False
            }
        
        # 保存僵尸选择
        self.room_selections[room_id]["zombie_selection"] = selected_zombies
        self.room_selections[room_id]["zombie_ready"] = True
        
        logger.info(f"房间 {room_id} 僵尸玩家 {user_id} 完成选择: {selected_zombies}")
        
        await self.send_to_user(room_id, user_id, "event.zombie_selection_confirmed", {
            "room_id": room_id,
            "message": "僵尸选择已确认，等待植物玩家...",
            "zombie_selection": selected_zombies
        })

        await self.check_both_selections_ready(room_id)
    
    async def check_both_selections_ready(self, room_id: str):
        """检查双方是否都完成选择"""
        if room_id not in self.room_selections:
            return
        
        selections = self.room_selections[room_id]
        
        if selections["plant_ready"] and selections["zombie_ready"]:
            logger.info(f"房间 {room_id} 双方都完成选择，开始游戏")

            await simple_room_manager.update_room_status(room_id, "playing")
            
            # 广播游戏开始事件，包含选择信息
            await self.broadcast_to_room(room_id, "event.game_start", {
                "room_id": room_id,
                "message": "双方选择完成，游戏开始！",
                "plant_selection": selections["plant_selection"],
                "zombie_selection": selections["zombie_selection"]
            })
            
            # 清理选择状态
            del self.room_selections[room_id]


# 全局实例
ws_manager = SimplePvZWebSocketManager()
