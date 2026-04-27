from datetime import datetime
from typing import List, Optional

from fastapi import WebSocket

from game_config import *


class GameRouteConnectionMixin:
    async def connect(self, player_id: str, websocket: WebSocket, user_info: dict):
        """玩家连接"""
        await websocket.accept()
        self.active_connections[player_id] = websocket

        # 初始化玩家数据（随机出生位置）
        spawn_x = random.uniform(-50, 50)
        spawn_z = random.uniform(-50, 50)
        spawn_x, spawn_z, _ = self._clamp_to_shore(spawn_x, spawn_z, margin=PLAYER_RADIUS)
        tribe_spawn = self._get_tribe_spawn_position(self.player_tribes.get(player_id))
        if tribe_spawn:
            spawn_x = tribe_spawn["x"]
            spawn_z = tribe_spawn["z"]

        self.players[player_id] = {
            "id": player_id,
            "name": user_info.get("username", f"玩家{player_id[:6]}"),
            "x": spawn_x,
            "y": 2,
            "z": spawn_z,
            "health": 100,
            "conflict_fatigue": 0,
            "personal_renown": 0,
            "personal_relations": {},
            "level": 1,
            "connected_at": datetime.now().isoformat()
        }

        logger.info(f"玩家 {player_id} ({self.players[player_id]['name']}) 已连接")

        # 发送欢迎消息
        await self.send_personal_message(player_id, {
            "type": "welcome",
            "playerId": player_id,
            "playerCount": len(self.active_connections),
            "data": self.players[player_id]
        })
        await self.send_personal_conflict_status(player_id)

        # 向新玩家发送当前所有玩家状态
        nearby_ids = set(self._players_in_range(player_id, self.aoi_radius))
        await self.send_personal_message(player_id, {
            "type": "players_state",
            "players": [
                {"id": pid, "data": pdata}
                for pid, pdata in self.players.items()
                if pid != player_id and pid in nearby_ids
            ]
        })

        # 下发当前共享地图状态，确保所有客户端看到一致地图
        map_data = self.load_map(self.current_map_name)
        if map_data:
            await self.send_personal_message(player_id, {
                "type": "map_loaded",
                "mapName": self.current_map_name,
                "mapData": map_data
            })

        await self.send_personal_message(player_id, self.get_tribes_overview())
        await self.send_personal_message(player_id, self.get_player_tribe_state(player_id))
        await self.send_personal_message(player_id, self.get_world_rumors_message())

        # 向 AOI 内玩家广播新玩家加入
        await self.broadcast({
            "type": "player_joined",
            "playerId": player_id,
            "playerCount": len(self.active_connections),
            "data": self.players[player_id]
        }, exclude=[player_id], include=self._players_in_range(player_id, self.aoi_radius))

        # 向新玩家发送一次 AOI 快照，便于客户端做 add/remove 一致性处理
        await self.send_aoi_state(player_id)
        self._ensure_weather_task()
        self._ensure_food_task()

    async def disconnect(self, player_id: str):
        """玩家断开连接"""
        # 断开前计算 AOI 影响范围，用于通知附近玩家移除
        nearby_before = self._players_in_range(player_id, self.aoi_radius)

        if player_id in self.active_connections:
            del self.active_connections[player_id]

        if player_id in self.players:
            player_name = self.players[player_id].get("name", "未知玩家")
            del self.players[player_id]
            logger.info(f"玩家 {player_id} ({player_name}) 已断开连接")

        # 向 AOI 内玩家广播玩家离开
        await self.broadcast({
            "type": "player_left",
            "playerId": player_id,
            "playerCount": len(self.active_connections)
        }, include=nearby_before)

        if not self.active_connections and self._weather_task:
            self._weather_task.cancel()
            self._weather_task = None

    async def send_personal_message(self, player_id: str, message: dict):
        """向特定玩家发送消息"""
        if player_id in self.active_connections:
            try:
                await self.active_connections[player_id].send_json(message)
            except Exception as e:
                logger.error(f"向玩家 {player_id} 发送消息失败: {e}")

    async def broadcast(self, message: dict, exclude: List[str] = None, include: Optional[List[str]] = None):
        """广播消息给玩家（可排除/限定特定玩家）"""
        exclude = exclude or []
        disconnected_players = []

        for player_id, websocket in self.active_connections.items():
            if include is not None and player_id not in include:
                continue
            if player_id not in exclude:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"向玩家 {player_id} 广播消息失败: {e}")
                    disconnected_players.append(player_id)

        # 清理断开的连接
        for player_id in disconnected_players:
            await self.disconnect(player_id)

    async def update_player_position(self, player_id: str, x: float, y: float, z: float):
        """更新玩家位置并广播"""
        if player_id in self.players:
            self.players[player_id].update({
                "x": x,
                "y": y,
                "z": z
            })

            # 仅广播给 AOI 内玩家
            nearby_ids = self._players_in_range(player_id, self.aoi_radius)
            await self.broadcast({
                "type": "player_move",
                "playerId": player_id,
                "data": {
                    "x": x,
                    "y": y,
                    "z": z
                }
            }, exclude=[player_id], include=nearby_ids)

            # 给自己回一个 AOI 快照，客户端可据此创建/移除远端玩家
            await self.send_aoi_state(player_id)

    async def broadcast_chat(self, player_id: str, message: str):
        """广播聊天消息"""
        sender_name = self.players.get(player_id, {}).get("name", "未知玩家")

        # 聊天也走 AOI：只发给附近玩家（可按需改为全服）
        nearby_ids = self._players_in_range(player_id, self.aoi_radius)
        await self.broadcast({
            "type": "chat",
            "playerId": player_id,
            "sender": sender_name,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }, include=nearby_ids + [player_id])

    def save_map(self, map_name: str, map_data: dict) -> bool:
        """保存地图数据"""
        try:
            if not isinstance(map_data, dict) or not map_data:
                raise ValueError("mapData 不能为空")

            decorations = map_data.get("decorations")
            if decorations is None or not isinstance(decorations, list):
                raise ValueError("mapData.decorations 必须是列表")

            environment = map_data.get("environment")
            if environment is not None and not isinstance(environment, dict):
                raise ValueError("mapData.environment 必须是对象")

            filtered_decorations = [
                item for item in decorations
                if not self._is_tribe_decoration(item)
            ]
            filtered_environment = dict(environment or {})
            filtered_environment["landmarks"] = [
                item for item in filtered_environment.get("landmarks", [])
                if not self._is_tribe_decoration(item)
            ]

            self.maps[map_name] = {
                "name": map_name,
                "updated_at": datetime.now().isoformat(),
                **map_data,
                "decorations": filtered_decorations,
                "environment": filtered_environment
            }
            logger.info(f"地图 '{map_name}' 已保存")
            return True
        except Exception as e:
            logger.error(f"保存地图失败: {e}")
            return False

    def load_map(self, map_name: str) -> Optional[dict]:
        """加载地图数据"""
        return self._compose_map_data(map_name)

    def get_player_count(self) -> int:
        """获取在线玩家数"""
        return len(self.active_connections)
