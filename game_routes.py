"""
游戏 WebSocket 路由
支持多人在线游戏、实时位置同步、聊天和地图管理
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set, Optional, List
import json
import asyncio
import random
import math
from datetime import datetime
from utils import decode_token
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("game_server")

router = APIRouter()

WEATHER_TYPES = ["sunny", "rain", "snow", "fog"]
DEFAULT_SHORE_RADIUS = 95.0
PLAYER_RADIUS = 0.7

# 玩家连接管理
class ConnectionManager:
    def __init__(self):
        # 活跃连接：{player_id: websocket}
        self.active_connections: Dict[str, WebSocket] = {}

        # 玩家数据：{player_id: player_data}
        self.players: Dict[str, dict] = {}

        self.current_map_name = "默认地图"
        self.aoi_radius = 60.0

        # 地图数据存储（简单内存存储，实际可用 MongoDB）
        # 约定：地图为全局共享状态，所有在线玩家应看到一致的 decorations。
        default_seed = 20250101
        self.weather_types = list(WEATHER_TYPES)
        self.weather_change_interval = 45.0
        self._weather_task: Optional[asyncio.Task] = None
        self._weather_rng = random.Random(default_seed + 424242)
        self.maps: Dict[str, dict] = {
            self.current_map_name: {
                "name": self.current_map_name,
                "created_at": datetime.now().isoformat(),
                "seed": default_seed,
                "terrain": {
                    "type": "procedural_v1"
                },
                "environment": self._generate_default_environment(seed=default_seed),
                "decorations": self._generate_default_decorations(seed=default_seed)
            }
        }

    def _generate_default_decorations(
        self,
        seed: int,
        tree_count: int = 250,
        rock_count: int = 120,
        radius: float = 90.0
    ) -> List[dict]:
        rng = random.Random(seed)
        decorations: List[dict] = []

        for i in range(tree_count):
            decorations.append({
                "id": f"tree_{i}",
                "type": "tree",
                "x": (rng.random() - 0.5) * (radius * 2),
                "z": (rng.random() - 0.5) * (radius * 2),
                "y": 0,
                "size": rng.random() * 0.7 + 0.85,
                "trunkColor": rng.choice([0x7a4a1f, 0x6b3f1a, 0x8b5a2b]),
                "foliageColor": rng.choice([0x1f7a2e, 0x228b22, 0x2e8b57])
            })

        for i in range(rock_count):
            decorations.append({
                "id": f"rock_{i}",
                "type": "rock",
                "x": (rng.random() - 0.5) * (radius * 2),
                "z": (rng.random() - 0.5) * (radius * 2),
                "y": 0,
                "size": rng.random() * 0.9 + 0.6,
                "color": rng.choice([0x6f6f6f, 0x7b7b7b, 0x888888])
            })

        return decorations

    def _generate_default_environment(self, seed: int) -> dict:
        rng = random.Random(seed + 999)

        weather = rng.choice(WEATHER_TYPES)
        sea_level = -0.8
        shore_radius = DEFAULT_SHORE_RADIUS

        mountains: List[dict] = []
        mountain_count = 18
        ring_radius = 120.0
        for i in range(mountain_count):
            angle = (i / mountain_count) * 6.283185307179586
            jitter = (rng.random() - 0.5) * 10.0
            x = (ring_radius + jitter) * math.cos(angle)
            z = (ring_radius + jitter) * math.sin(angle)
            mountains.append({
                "id": f"mountain_{i}",
                "type": "mountain",
                "x": x,
                "z": z,
                "y": 0,
                "radius": rng.random() * 8 + 10,
                "height": rng.random() * 25 + 18
            })

        return {
            "seaLevel": sea_level,
            "weather": weather,
            "shoreRadius": shore_radius,
            "mountains": mountains
        }

    def _pick_next_weather(self, current: Optional[str]) -> str:
        candidates = [w for w in self.weather_types if w != current]
        if not candidates:
            return current or "sunny"
        return self._weather_rng.choice(candidates)

    async def _weather_loop(self):
        try:
            while True:
                await asyncio.sleep(self.weather_change_interval)
                if not self.active_connections:
                    return

                map_data = self.maps.get(self.current_map_name) or {}
                env = map_data.get("environment") or {}
                current = env.get("weather")
                next_weather = self._pick_next_weather(current)
                if next_weather == current:
                    continue

                env["weather"] = next_weather
                map_data["environment"] = env
                map_data["updated_at"] = datetime.now().isoformat()

                await self.broadcast({
                    "type": "environment_update",
                    "mapName": self.current_map_name,
                    "environment": env
                })
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"天气循环异常: {e}")

    def _ensure_weather_task(self):
        if self._weather_task and not self._weather_task.done():
            return
        self._weather_task = asyncio.create_task(self._weather_loop())

    def _dist2(self, a: dict, b: dict) -> float:
        dx = float(a.get("x", 0)) - float(b.get("x", 0))
        dz = float(a.get("z", 0)) - float(b.get("z", 0))
        return dx * dx + dz * dz

    def _get_current_environment(self) -> dict:
        map_data = self.maps.get(self.current_map_name) or {}
        env = map_data.get("environment") or {}
        return env if isinstance(env, dict) else {}

    def _get_shore_radius(self) -> float:
        env = self._get_current_environment()
        value = env.get("shoreRadius", env.get("playableRadius", DEFAULT_SHORE_RADIUS))
        try:
            radius = float(value)
        except (TypeError, ValueError):
            radius = DEFAULT_SHORE_RADIUS
        return max(5.0, radius)

    def _clamp_to_shore(self, x: float, z: float, margin: float = 0.0):
        max_radius = self._get_shore_radius() - float(margin or 0.0)
        max_radius = max(0.5, max_radius)
        dist2 = x * x + z * z
        if dist2 <= max_radius * max_radius:
            return x, z, False

        dist = math.sqrt(dist2) or 0.0001
        scale = max_radius / dist
        return x * scale, z * scale, True

    def _players_in_range(self, center_player_id: str, radius: float) -> List[str]:
        center = self.players.get(center_player_id)
        if not center:
            return []

        r2 = radius * radius
        nearby: List[str] = []
        for pid, pdata in self.players.items():
            if pid == center_player_id:
                continue
            if self._dist2(center, pdata) <= r2:
                nearby.append(pid)
        return nearby

    async def send_aoi_state(self, player_id: str):
        """发送当前 AOI 内玩家状态给指定玩家（用于创建/移除远端玩家）"""
        nearby_ids = self._players_in_range(player_id, self.aoi_radius)
        await self.send_personal_message(player_id, {
            "type": "aoi_state",
            "radius": self.aoi_radius,
            "players": [
                {"id": pid, "data": self.players.get(pid, {})}
                for pid in nearby_ids
            ]
        })

    async def connect(self, player_id: str, websocket: WebSocket, user_info: dict):
        """玩家连接"""
        await websocket.accept()
        self.active_connections[player_id] = websocket

        # 初始化玩家数据（随机出生位置）
        spawn_x = random.uniform(-50, 50)
        spawn_z = random.uniform(-50, 50)
        spawn_x, spawn_z, _ = self._clamp_to_shore(spawn_x, spawn_z, margin=PLAYER_RADIUS)

        self.players[player_id] = {
            "id": player_id,
            "name": user_info.get("username", f"玩家{player_id[:6]}"),
            "x": spawn_x,
            "y": 2,
            "z": spawn_z,
            "health": 100,
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

            self.maps[map_name] = {
                "name": map_name,
                "updated_at": datetime.now().isoformat(),
                **map_data
            }
            logger.info(f"地图 '{map_name}' 已保存")
            return True
        except Exception as e:
            logger.error(f"保存地图失败: {e}")
            return False

    def load_map(self, map_name: str) -> Optional[dict]:
        """加载地图数据"""
        return self.maps.get(map_name)

    def get_player_count(self) -> int:
        """获取在线玩家数"""
        return len(self.active_connections)


# 创建全局连接管理器
manager = ConnectionManager()


# 验证 Token 依赖
async def verify_game_token(token: str = Query(...)):
    """验证游戏连接的 Token"""
    try:
        payload = decode_token(token)
        if not payload:
            raise ValueError("无效的 token")
        return payload
    except Exception as e:
        logger.error(f"Token 验证失败: {e}")
        raise ValueError("Token 验证失败")


@router.websocket("/ws/game")
async def game_websocket(
    websocket: WebSocket,
    token: str = Query(...)
):
    """游戏 WebSocket 连接端点"""
    player_id = None

    try:
        # 验证 Token
        user_info = await verify_game_token(token)
        player_id = str(user_info.get("user_id", user_info.get("sub")))

        # 连接玩家
        await manager.connect(player_id, websocket, user_info)

        # 消息循环
        while True:
            try:
                # 接收消息（设置超时避免阻塞）
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=60.0  # 60秒超时
                )

                message = json.loads(data)
                message_type = message.get("type")

                # 处理不同类型的消息
                if message_type == "move":
                    # 玩家移动
                    move_data = message.get("data", {})
                    await manager.update_player_position(
                        player_id,
                        move_data.get("x", 0),
                        move_data.get("y", 2),
                        move_data.get("z", 0)
                    )

                elif message_type == "chat":
                    # 聊天消息
                    chat_message = message.get("message", "")
                    if chat_message.strip():
                        await manager.broadcast_chat(player_id, chat_message)

                elif message_type == "ping":
                    # 心跳检测
                    await manager.send_personal_message(player_id, {
                        "type": "pong",
                        "timestamp": message.get("timestamp", 0)
                    })

                elif message_type == "save_map":
                    # 保存地图
                    map_name = message.get("mapName", "默认地图")
                    map_data = message.get("mapData", {})

                    success = manager.save_map(map_name, map_data)
                    await manager.send_personal_message(player_id, {
                        "type": "map_saved",
                        "success": success,
                        "mapName": map_name
                    })

                    # 共享地图：保存成功后广播最新地图给所有在线玩家
                    if success:
                        manager.current_map_name = map_name
                        latest_map = manager.load_map(map_name)
                        if latest_map:
                            await manager.broadcast({
                                "type": "map_loaded",
                                "mapName": map_name,
                                "mapData": latest_map
                            })

                elif message_type == "load_map":
                    # 加载地图
                    map_name = message.get("mapName", "默认地图")
                    map_data = manager.load_map(map_name)

                    if map_data:
                        # 共享地图：加载即切换当前地图，并广播给所有在线玩家
                        manager.current_map_name = map_name
                        await manager.broadcast({
                            "type": "map_loaded",
                            "mapName": map_name,
                            "mapData": map_data
                        })
                    else:
                        await manager.send_personal_message(player_id, {
                            "type": "error",
                            "message": f"地图 '{map_name}' 不存在"
                        })

                else:
                    logger.warning(f"未知消息类型: {message_type}")

            except asyncio.TimeoutError:
                # 超时，发送心跳检测
                await manager.send_personal_message(player_id, {
                    "type": "ping",
                    "timestamp": datetime.now().timestamp()
                })

            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析错误: {e}")
                await manager.send_personal_message(player_id, {
                    "type": "error",
                    "message": "消息格式错误"
                })

    except WebSocketDisconnect:
        logger.info(f"玩家 {player_id} 主动断开连接")

    except ValueError as e:
        logger.error(f"认证错误: {e}")
        try:
            await websocket.close(code=4001, reason=str(e))
        except:
            pass

    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")

    finally:
        # 清理连接
        if player_id:
            await manager.disconnect(player_id)


@router.get("/api/game/stats")
async def get_game_stats():
    """获取游戏统计信息"""
    return {
        "online_players": manager.get_player_count(),
        "total_maps": len(manager.maps),
        "server_time": datetime.now().isoformat()
    }


@router.get("/api/game/maps")
async def get_maps_list():
    """获取所有地图列表"""
    return {
        "maps": [
            {
                "name": name,
                "updated_at": data.get("updated_at", data.get("created_at"))
            }
            for name, data in manager.maps.items()
        ]
    }
