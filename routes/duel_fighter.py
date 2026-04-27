import asyncio
import math
import random
import string
import time
import uuid
from copy import deepcopy
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

from auth_deps import get_current_user


router = APIRouter()


TICK_RATE = 30
DT = 1 / TICK_RATE
GRAVITY = 2200
FLOOR_FRICTION = 0.78
AIR_FRICTION = 0.92


CHARACTERS = {
    "blade": {
        "id": "blade",
        "name": "岚刃",
        "role": "均衡剑士",
        "color": "#38bdf8",
        "maxHp": 110,
        "speed": 360,
        "jump": 780,
        "width": 48,
        "height": 112,
        "attacks": {
            "light": {"damage": 7, "range": 88, "cooldown": 0.28, "stun": 0.14},
            "heavy": {"damage": 13, "range": 116, "cooldown": 0.58, "stun": 0.22},
            "special": {"damage": 18, "range": 145, "cooldown": 1.05, "stun": 0.3, "energy": 32},
        },
    },
    "fist": {
        "id": "fist",
        "name": "赤拳",
        "role": "近身爆发",
        "color": "#ef4444",
        "maxHp": 118,
        "speed": 330,
        "jump": 740,
        "width": 52,
        "height": 108,
        "attacks": {
            "light": {"damage": 8, "range": 72, "cooldown": 0.25, "stun": 0.16},
            "heavy": {"damage": 16, "range": 92, "cooldown": 0.68, "stun": 0.28},
            "special": {"damage": 22, "range": 106, "cooldown": 1.15, "stun": 0.34, "energy": 34},
        },
    },
    "shade": {
        "id": "shade",
        "name": "影步",
        "role": "高速拉扯",
        "color": "#a78bfa",
        "maxHp": 96,
        "speed": 420,
        "jump": 820,
        "width": 44,
        "height": 104,
        "attacks": {
            "light": {"damage": 6, "range": 82, "cooldown": 0.2, "stun": 0.12},
            "heavy": {"damage": 11, "range": 104, "cooldown": 0.5, "stun": 0.2},
            "special": {"damage": 16, "range": 170, "cooldown": 0.95, "stun": 0.24, "energy": 30},
        },
    },
    "guard": {
        "id": "guard",
        "name": "磐卫",
        "role": "重甲防守",
        "color": "#f59e0b",
        "maxHp": 138,
        "speed": 285,
        "jump": 680,
        "width": 58,
        "height": 118,
        "attacks": {
            "light": {"damage": 7, "range": 78, "cooldown": 0.3, "stun": 0.16},
            "heavy": {"damage": 15, "range": 104, "cooldown": 0.72, "stun": 0.3},
            "special": {"damage": 20, "range": 126, "cooldown": 1.18, "stun": 0.38, "energy": 28},
        },
    },
}


MAPS = {
    "stone": {
        "id": "stone",
        "name": "石台道场",
        "width": 960,
        "height": 540,
        "groundY": 420,
        "leftWall": 54,
        "rightWall": 906,
        "sky": "#172033",
        "floor": "#6b7280",
        "platforms": [
            {"x": 190, "y": 330, "width": 170, "height": 16},
            {"x": 600, "y": 330, "width": 170, "height": 16},
            {"x": 405, "y": 270, "width": 150, "height": 16},
        ],
        "hazards": [],
    },
    "bamboo": {
        "id": "bamboo",
        "name": "竹林雨夜",
        "width": 960,
        "height": 540,
        "groundY": 430,
        "leftWall": 42,
        "rightWall": 918,
        "sky": "#10231f",
        "floor": "#3f7a5b",
        "platforms": [
            {"x": 100, "y": 360, "width": 150, "height": 14},
            {"x": 345, "y": 300, "width": 130, "height": 14},
            {"x": 620, "y": 345, "width": 180, "height": 14},
        ],
        "hazards": [
            {"x": 470, "y": 430, "width": 90, "height": 18, "damage": 4},
        ],
    },
    "lava": {
        "id": "lava",
        "name": "熔岩断桥",
        "width": 960,
        "height": 540,
        "groundY": 410,
        "leftWall": 100,
        "rightWall": 860,
        "sky": "#261414",
        "floor": "#7c2d12",
        "platforms": [
            {"x": 110, "y": 382, "width": 230, "height": 16},
            {"x": 620, "y": 382, "width": 230, "height": 16},
            {"x": 400, "y": 300, "width": 160, "height": 16},
        ],
        "hazards": [
            {"x": 352, "y": 410, "width": 256, "height": 24, "damage": 7},
        ],
    },
}

AI_DIFFICULTIES = {
    "easy": {
        "id": "easy",
        "name": "新手",
        "reaction": 0.34,
        "idealRange": 132,
        "attackChance": 0.34,
        "heavyChance": 0.08,
        "specialChance": 0.04,
        "blockChance": 0.16,
        "jumpChance": 0.03,
    },
    "normal": {
        "id": "normal",
        "name": "标准",
        "reaction": 0.2,
        "idealRange": 112,
        "attackChance": 0.58,
        "heavyChance": 0.18,
        "specialChance": 0.1,
        "blockChance": 0.34,
        "jumpChance": 0.07,
    },
    "hard": {
        "id": "hard",
        "name": "高手",
        "reaction": 0.1,
        "idealRange": 96,
        "attackChance": 0.78,
        "heavyChance": 0.28,
        "specialChance": 0.18,
        "blockChance": 0.54,
        "jumpChance": 0.12,
    },
}


class RoomCodeRequest(BaseModel):
    room_code: str


class AiRoomRequest(BaseModel):
    difficulty: str = "normal"


class SimpleResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict | list] = None


def now_ms() -> int:
    return int(time.time() * 1000)


def room_code() -> str:
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))


def empty_input() -> dict:
    return {
        "left": False,
        "right": False,
        "up": False,
        "down": False,
        "block": False,
    }


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


class DuelFighterManager:
    def __init__(self) -> None:
        self.rooms: Dict[str, dict] = {}
        self.user_room: Dict[str, str] = {}
        self.lobby_connections: Dict[str, WebSocket] = {}
        self.room_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.room_tasks: Dict[str, asyncio.Task] = {}
        self.lock = asyncio.Lock()

    def _new_player(
        self,
        user_id: str,
        username: str,
        slot: str,
        *,
        is_ai: bool = False,
        ai_difficulty: Optional[str] = None,
    ) -> dict:
        return {
            "userId": user_id,
            "username": username,
            "slot": slot,
            "isAI": is_ai,
            "aiDifficulty": ai_difficulty,
            "aiThinkTimer": 0,
            "connected": False,
            "ready": is_ai,
            "characterId": "blade" if slot == "p1" else "fist",
            "x": 220 if slot == "p1" else 740,
            "y": 0,
            "vx": 0,
            "vy": 0,
            "facing": 1 if slot == "p1" else -1,
            "hp": 100,
            "energy": 20,
            "grounded": True,
            "blocking": False,
            "stun": 0,
            "cooldown": 0,
            "attack": None,
            "attackTimer": 0,
            "lastHitAt": 0,
            "input": empty_input(),
            "pendingAction": None,
        }

    def _room_public(self, room: dict, include_state: bool = False) -> dict:
        payload = {
            "roomId": room["roomId"],
            "roomCode": room["roomCode"],
            "hostId": room["hostId"],
            "status": room["status"],
            "mode": room.get("mode", "pvp"),
            "aiDifficulty": room.get("aiDifficulty"),
            "mapId": room["mapId"],
            "createdAt": room["createdAt"],
            "updatedAt": room["updatedAt"],
            "players": {
                slot: self._player_public(player)
                for slot, player in room["players"].items()
                if player
            },
        }
        if include_state:
            payload["state"] = self._state_public(room)
        return payload

    def _player_public(self, player: dict) -> dict:
        return {
            "userId": player["userId"],
            "username": player["username"],
            "slot": player["slot"],
            "isAI": player.get("isAI", False),
            "aiDifficulty": player.get("aiDifficulty"),
            "connected": player["connected"],
            "ready": player["ready"],
            "characterId": player["characterId"],
            "x": round(player["x"], 2),
            "y": round(player["y"], 2),
            "vx": round(player["vx"], 2),
            "vy": round(player["vy"], 2),
            "facing": player["facing"],
            "hp": round(player["hp"], 1),
            "energy": round(player["energy"], 1),
            "grounded": player["grounded"],
            "blocking": player["blocking"],
            "stun": round(player["stun"], 2),
            "attack": player["attack"],
            "attackTimer": round(player["attackTimer"], 2),
        }

    def _state_public(self, room: dict) -> dict:
        return {
            "roomId": room["roomId"],
            "roomCode": room["roomCode"],
            "status": room["status"],
            "mode": room.get("mode", "pvp"),
            "aiDifficulty": room.get("aiDifficulty"),
            "winner": room.get("winner"),
            "finishedReason": room.get("finishedReason"),
            "map": MAPS[room["mapId"]],
            "mapId": room["mapId"],
            "characters": CHARACTERS,
            "difficulties": AI_DIFFICULTIES,
            "projectiles": room.get("projectiles", []),
            "players": {
                slot: self._player_public(player)
                for slot, player in room["players"].items()
                if player
            },
            "serverTime": now_ms(),
        }

    async def create_room(self, user_id: str, username: str) -> dict:
        async with self.lock:
            await self._leave_room_locked(user_id)
            code = room_code()
            while any(room["roomCode"] == code for room in self.rooms.values()):
                code = room_code()
            room_id = str(uuid.uuid4())
            room = {
                "roomId": room_id,
                "roomCode": code,
                "hostId": user_id,
                "status": "waiting",
                "mapId": "stone",
                "createdAt": now_ms(),
                "updatedAt": now_ms(),
                "winner": None,
                "finishedReason": None,
                "projectiles": [],
                "players": {
                    "p1": self._new_player(user_id, username, "p1"),
                    "p2": None,
                },
            }
            self.rooms[room_id] = room
            self.user_room[user_id] = room_id
            result = self._room_public(room, include_state=True)
        await self.broadcast_lobby()
        return result

    async def create_ai_room(self, user_id: str, username: str, difficulty: str) -> dict:
        difficulty = difficulty if difficulty in AI_DIFFICULTIES else "normal"
        async with self.lock:
            await self._leave_room_locked(user_id)
            code = room_code()
            while any(room["roomCode"] == code for room in self.rooms.values()):
                code = room_code()
            room_id = str(uuid.uuid4())
            ai_player = self._new_player(
                f"ai-{room_id}",
                f"AI-{AI_DIFFICULTIES[difficulty]['name']}",
                "p2",
                is_ai=True,
                ai_difficulty=difficulty,
            )
            ai_player["connected"] = True
            ai_player["characterId"] = random.choice(["fist", "shade", "guard"])
            room = {
                "roomId": room_id,
                "roomCode": code,
                "hostId": user_id,
                "status": "selecting",
                "mode": "ai",
                "aiDifficulty": difficulty,
                "mapId": "stone",
                "createdAt": now_ms(),
                "updatedAt": now_ms(),
                "winner": None,
                "finishedReason": None,
                "projectiles": [],
                "players": {
                    "p1": self._new_player(user_id, username, "p1"),
                    "p2": ai_player,
                },
            }
            self.rooms[room_id] = room
            self.user_room[user_id] = room_id
            result = self._room_public(room, include_state=True)
        await self.broadcast_lobby()
        return result

    async def join_room(self, room_code_value: str, user_id: str, username: str) -> dict:
        async with self.lock:
            room = next(
                (item for item in self.rooms.values() if item["roomCode"] == room_code_value.upper()),
                None,
            )
            if not room:
                raise HTTPException(status_code=404, detail="房间不存在")
            if room.get("mode") == "ai":
                raise HTTPException(status_code=400, detail="人机房间不能加入")
            if user_id in [p["userId"] for p in room["players"].values() if p]:
                self.user_room[user_id] = room["roomId"]
                return self._room_public(room, include_state=True)
            if room["players"]["p2"]:
                raise HTTPException(status_code=400, detail="房间已满")
            await self._leave_room_locked(user_id)
            room["players"]["p2"] = self._new_player(user_id, username, "p2")
            room["status"] = "selecting"
            room["updatedAt"] = now_ms()
            self.user_room[user_id] = room["roomId"]
            result = self._room_public(room, include_state=True)
        await self.broadcast_lobby()
        await self.broadcast_room_state(result["roomId"], "state.room")
        return result

    async def my_room(self, user_id: str) -> Optional[dict]:
        async with self.lock:
            room_id = self.user_room.get(user_id)
            room = self.rooms.get(room_id) if room_id else None
            return self._room_public(room, include_state=True) if room else None

    async def active_rooms(self) -> list:
        async with self.lock:
            return [
                self._room_public(room)
                for room in self.rooms.values()
                if room["status"] in {"waiting", "selecting", "playing", "finished"}
            ]

    async def leave_room(self, user_id: str) -> None:
        async with self.lock:
            await self._leave_room_locked(user_id)
        await self.broadcast_lobby()

    async def _leave_room_locked(self, user_id: str) -> None:
        room_id = self.user_room.pop(user_id, None)
        if not room_id:
            return
        room = self.rooms.get(room_id)
        if not room:
            return
        if room["hostId"] == user_id:
            self.rooms.pop(room_id, None)
            task = self.room_tasks.pop(room_id, None)
            if task:
                task.cancel()
            return
        for slot, player in room["players"].items():
            if player and player["userId"] == user_id:
                room["players"][slot] = None
        room["status"] = "waiting"
        room["updatedAt"] = now_ms()

    async def connect_lobby(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.lobby_connections[user_id] = websocket
        await self.send(websocket, "state.lobby", {"rooms": await self.active_rooms()})

    def disconnect_lobby(self, user_id: str) -> None:
        self.lobby_connections.pop(user_id, None)

    async def connect_room(self, websocket: WebSocket, room_id: str, user_id: str) -> str:
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                await websocket.close(code=4004, reason="Room not found")
                return ""
            slot = self._slot_for_user(room, user_id)
            if not slot:
                await websocket.close(code=4003, reason="Not in room")
                return ""
            await websocket.accept()
            room["players"][slot]["connected"] = True
            room["updatedAt"] = now_ms()
            self.room_connections.setdefault(room_id, {})[user_id] = websocket
        await self.send(websocket, "event.connected", {"slot": slot, "roomId": room_id})
        await self.broadcast_room_state(room_id, "state.room")
        await self.broadcast_lobby()
        return slot

    async def disconnect_room(self, room_id: str, user_id: str) -> None:
        async with self.lock:
            self.room_connections.get(room_id, {}).pop(user_id, None)
            room = self.rooms.get(room_id)
            if room:
                slot = self._slot_for_user(room, user_id)
                if slot:
                    room["players"][slot]["connected"] = False
                    room["players"][slot]["ready"] = False
                    room["updatedAt"] = now_ms()
        await self.broadcast_room_state(room_id, "state.room")
        await self.broadcast_lobby()

    def _slot_for_user(self, room: dict, user_id: str) -> Optional[str]:
        for slot, player in room["players"].items():
            if player and player["userId"] == user_id:
                return slot
        return None

    async def handle_message(self, room_id: str, user_id: str, message: dict) -> None:
        message_type = message.get("type")
        payload = message.get("payload") or {}
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                return
            slot = self._slot_for_user(room, user_id)
            if not slot:
                return
            player = room["players"][slot]
            if message_type == "select_character":
                character_id = payload.get("characterId")
                if character_id in CHARACTERS and room["status"] != "playing":
                    player["characterId"] = character_id
                    player["ready"] = False
                    self._keep_ai_ready_locked(room)
                    room["status"] = "selecting" if room["players"]["p2"] else "waiting"
            elif message_type == "select_map":
                map_id = payload.get("mapId")
                if user_id == room["hostId"] and map_id in MAPS and room["status"] != "playing":
                    room["mapId"] = map_id
                    for item in room["players"].values():
                        if item and not item.get("isAI"):
                            item["ready"] = False
                    self._keep_ai_ready_locked(room)
            elif message_type == "ready":
                player["ready"] = bool(payload.get("ready"))
                self._maybe_start_locked(room)
            elif message_type == "input":
                for key in empty_input().keys():
                    if key in payload:
                        player["input"][key] = bool(payload[key])
                action = payload.get("action")
                if action in {"light", "heavy", "special"}:
                    player["pendingAction"] = action
            elif message_type == "reset" and user_id == room["hostId"]:
                self._reset_room_locked(room)
            room["updatedAt"] = now_ms()
            needs_task = room["status"] == "playing" and room_id not in self.room_tasks
        await self.broadcast_room_state(room_id, "state.room")
        if needs_task:
            self.room_tasks[room_id] = asyncio.create_task(self.run_room(room_id))
        await self.broadcast_lobby()

    def _maybe_start_locked(self, room: dict) -> None:
        players = [player for player in room["players"].values() if player]
        if len(players) != 2 or not all(player["ready"] and player["characterId"] for player in players):
            return
        self._reset_positions_locked(room)
        room["status"] = "playing"
        room["winner"] = None
        room["finishedReason"] = None
        room["projectiles"] = []

    def _keep_ai_ready_locked(self, room: dict) -> None:
        for player in room["players"].values():
            if player and player.get("isAI"):
                player["ready"] = True

    def _reset_positions_locked(self, room: dict) -> None:
        map_data = MAPS[room["mapId"]]
        for slot, player in room["players"].items():
            if not player:
                continue
            character = CHARACTERS[player["characterId"]]
            player.update(
                {
                    "x": map_data["leftWall"] + 170 if slot == "p1" else map_data["rightWall"] - 170,
                    "y": map_data["groundY"] - character["height"],
                    "vx": 0,
                    "vy": 0,
                    "facing": 1 if slot == "p1" else -1,
                    "hp": character["maxHp"],
                    "energy": 20,
                    "grounded": True,
                    "blocking": False,
                    "stun": 0,
                    "cooldown": 0,
                    "attack": None,
                    "attackTimer": 0,
                    "input": empty_input(),
                    "pendingAction": None,
                }
            )

    def _reset_room_locked(self, room: dict) -> None:
        for player in room["players"].values():
            if player:
                player["ready"] = bool(player.get("isAI"))
                player["input"] = empty_input()
                player["pendingAction"] = None
        room["status"] = "selecting" if room["players"]["p2"] else "waiting"
        room["winner"] = None
        room["finishedReason"] = None
        room["projectiles"] = []
        self._reset_positions_locked(room)

    async def run_room(self, room_id: str) -> None:
        try:
            while True:
                await asyncio.sleep(DT)
                async with self.lock:
                    room = self.rooms.get(room_id)
                    if not room or room["status"] != "playing":
                        self.room_tasks.pop(room_id, None)
                        return
                    self._tick_locked(room, DT)
                    state = self._state_public(room)
                await self.broadcast_room(room_id, "state.tick", state)
        except asyncio.CancelledError:
            return

    def _tick_locked(self, room: dict, dt: float) -> None:
        players = [player for player in room["players"].values() if player]
        if len(players) != 2:
            return
        map_data = MAPS[room["mapId"]]
        for player in players:
            if player.get("isAI"):
                opponent = players[1] if player is players[0] else players[0]
                self._update_ai_input(player, opponent, dt)
        for player in players:
            opponent = players[1] if player is players[0] else players[0]
            self._tick_player(room, player, opponent, map_data, dt)
        self._tick_projectiles(room, players, map_data, dt)
        self._resolve_overlap(players[0], players[1])
        for player in players:
            opponent = players[1] if player is players[0] else players[0]
            if opponent["hp"] <= 0:
                room["status"] = "finished"
                room["winner"] = player["slot"]
                room["finishedReason"] = "ko"
                for item in players:
                    item["ready"] = False
                return

    def _update_ai_input(self, ai: dict, opponent: dict, dt: float) -> None:
        difficulty = AI_DIFFICULTIES.get(ai.get("aiDifficulty"), AI_DIFFICULTIES["normal"])
        ai["aiThinkTimer"] = max(0, ai.get("aiThinkTimer", 0) - dt)
        if ai["aiThinkTimer"] > 0:
            return

        ai["aiThinkTimer"] = difficulty["reaction"]
        character = CHARACTERS[ai["characterId"]]
        opponent_character = CHARACTERS[opponent["characterId"]]
        ai_center = ai["x"] + character["width"] / 2
        opponent_center = opponent["x"] + opponent_character["width"] / 2
        distance = opponent_center - ai_center
        abs_distance = abs(distance)
        direction = 1 if distance > 0 else -1

        wants_block = (
            opponent.get("attack")
            and abs_distance < 150
            and random.random() < difficulty["blockChance"]
        )
        target_range = difficulty["idealRange"]
        move_direction = 0
        if not wants_block:
            if abs_distance > target_range + 18:
                move_direction = direction
            elif abs_distance < target_range - 28:
                move_direction = -direction

        ai["input"] = {
            "left": move_direction < 0,
            "right": move_direction > 0,
            "up": ai["grounded"] and random.random() < difficulty["jumpChance"] and abs_distance < 140,
            "down": False,
            "block": bool(wants_block),
        }

        if ai["cooldown"] <= 0 and ai["stun"] <= 0 and abs_distance < 175:
            roll = random.random()
            if roll < difficulty["attackChance"]:
                action = "light"
                if ai["energy"] >= 30 and random.random() < difficulty["specialChance"]:
                    action = "special"
                elif random.random() < difficulty["heavyChance"]:
                    action = "heavy"
                ai["pendingAction"] = action

    def _tick_player(self, room: dict, player: dict, opponent: dict, map_data: dict, dt: float) -> None:
        character = CHARACTERS[player["characterId"]]
        player["cooldown"] = max(0, player["cooldown"] - dt)
        player["stun"] = max(0, player["stun"] - dt)
        player["attackTimer"] = max(0, player["attackTimer"] - dt)
        if player["attackTimer"] == 0:
            player["attack"] = None
        if player["stun"] <= 0:
            intent = player["input"]
            move = (1 if intent["right"] else 0) - (1 if intent["left"] else 0)
            player["blocking"] = intent["block"] and player["grounded"]
            if move:
                player["facing"] = move
                speed = character["speed"] * (0.45 if player["blocking"] else 1)
                player["vx"] = move * speed
            else:
                player["vx"] *= FLOOR_FRICTION if player["grounded"] else AIR_FRICTION
            if intent["up"] and player["grounded"] and not player["blocking"]:
                player["vy"] = -character["jump"]
                player["grounded"] = False
            if player["pendingAction"]:
                self._start_attack(room, player, opponent, map_data, player["pendingAction"])
                player["pendingAction"] = None
        previous_y = player["y"]
        player["vy"] += GRAVITY * dt
        player["x"] += player["vx"] * dt
        player["y"] += player["vy"] * dt
        player["grounded"] = False
        landing_y = map_data["groundY"] - character["height"]
        for platform in map_data.get("platforms", []):
            platform_top = platform["y"] - character["height"]
            was_above = previous_y + character["height"] <= platform["y"] + 10
            is_falling = player["vy"] >= 0
            overlaps_x = (
                player["x"] + character["width"] > platform["x"]
                and player["x"] < platform["x"] + platform["width"]
            )
            if was_above and is_falling and overlaps_x and player["y"] >= platform_top:
                landing_y = min(landing_y, platform_top)
        if player["y"] >= landing_y:
            player["y"] = landing_y
            player["vy"] = 0
            player["grounded"] = True
        player["x"] = clamp(player["x"], map_data["leftWall"], map_data["rightWall"] - character["width"])
        for hazard in map_data.get("hazards", []):
            if (
                player["x"] + character["width"] > hazard["x"]
                and player["x"] < hazard["x"] + hazard["width"]
                and player["y"] + character["height"] >= hazard["y"]
            ):
                player["hp"] = max(0, player["hp"] - hazard.get("damage", 3) * dt)
                player["energy"] = min(100, player["energy"] + 8 * dt)
        player["energy"] = clamp(player["energy"] + dt * 2.5, 0, 100)

    def _start_attack(self, room: dict, player: dict, opponent: dict, map_data: dict, attack_key: str) -> None:
        character = CHARACTERS[player["characterId"]]
        attack = character["attacks"][attack_key]
        if player["cooldown"] > 0:
            return
        energy_cost = attack.get("energy", 0)
        if player["energy"] < energy_cost:
            return
        player["energy"] -= energy_cost
        if attack_key == "special":
            self._apply_special(room, player, opponent, map_data)
        player["attack"] = attack_key
        player["attackTimer"] = min(0.34, attack["cooldown"])
        player["cooldown"] = attack["cooldown"]
        player["lastHitAt"] = now_ms()

    def _apply_special(self, room: dict, player: dict, opponent: dict, map_data: dict) -> None:
        character_id = player["characterId"]
        character = CHARACTERS[character_id]
        if character_id == "blade":
            room.setdefault("projectiles", []).append({
                "id": str(uuid.uuid4()),
                "ownerSlot": player["slot"],
                "x": player["x"] + character["width"] / 2,
                "y": player["y"] + 42,
                "vx": player["facing"] * 560,
                "width": 54,
                "height": 18,
                "damage": 12,
                "stun": 0.22,
                "ttl": 0.9,
                "color": character["color"],
            })
        elif character_id == "fist":
            player["vx"] = player["facing"] * 680
        elif character_id == "shade":
            target_x = opponent["x"] - player["facing"] * 74
            player["x"] = clamp(target_x, map_data["leftWall"], map_data["rightWall"] - character["width"])
            player["y"] = min(player["y"], opponent["y"])
        elif character_id == "guard":
            player["vx"] = -player["facing"] * 80

    def _resolve_overlap(self, a: dict, b: dict) -> None:
        aw = CHARACTERS[a["characterId"]]["width"]
        bw = CHARACTERS[b["characterId"]]["width"]
        center_a = a["x"] + aw / 2
        center_b = b["x"] + bw / 2
        distance = center_b - center_a
        min_distance = (aw + bw) / 2
        if abs(distance) < min_distance and distance != 0:
            push = (min_distance - abs(distance)) / 2
            direction = 1 if distance > 0 else -1
            a["x"] -= push * direction
            b["x"] += push * direction
        self._try_hit(a, b)
        self._try_hit(b, a)

    def _tick_projectiles(self, room: dict, players: list, map_data: dict, dt: float) -> None:
        remaining = []
        for projectile in room.get("projectiles", []):
            projectile["x"] += projectile["vx"] * dt
            projectile["ttl"] -= dt
            if (
                projectile["ttl"] <= 0
                or projectile["x"] < map_data["leftWall"] - 80
                or projectile["x"] > map_data["rightWall"] + 80
            ):
                continue
            hit = False
            for player in players:
                if player["slot"] == projectile["ownerSlot"]:
                    continue
                character = CHARACTERS[player["characterId"]]
                if (
                    projectile["x"] + projectile["width"] > player["x"]
                    and projectile["x"] < player["x"] + character["width"]
                    and projectile["y"] + projectile["height"] > player["y"]
                    and projectile["y"] < player["y"] + character["height"]
                ):
                    blocked = player["blocking"] and player["energy"] >= 10
                    player["hp"] = max(0, player["hp"] - projectile["damage"] * (0.35 if blocked else 1))
                    player["stun"] = max(player["stun"], projectile["stun"] * (0.4 if blocked else 1))
                    player["energy"] = max(0, player["energy"] - (10 if blocked else 0))
                    hit = True
                    break
            if not hit:
                remaining.append(projectile)
        room["projectiles"] = remaining

    def _try_hit(self, attacker: dict, defender: dict) -> None:
        if not attacker["attack"] or attacker["attackTimer"] <= 0:
            return
        if now_ms() - attacker["lastHitAt"] > 90:
            return
        attack = CHARACTERS[attacker["characterId"]]["attacks"][attacker["attack"]]
        defender_width = CHARACTERS[defender["characterId"]]["width"]
        ax = attacker["x"] + CHARACTERS[attacker["characterId"]]["width"] / 2
        dx = defender["x"] + defender_width / 2
        if math.copysign(1, dx - ax) != attacker["facing"]:
            return
        if abs(dx - ax) > attack["range"]:
            return
        defending_front = defender["facing"] == -attacker["facing"]
        blocked = defender["blocking"] and defending_front and defender["energy"] >= 8
        damage = attack["damage"] * (0.35 if blocked else 1)
        stun = attack["stun"] * (0.35 if blocked else 1)
        if blocked:
            defender["energy"] = max(0, defender["energy"] - 8)
            attacker["energy"] = min(100, attacker["energy"] + 4)
        else:
            attacker["energy"] = min(100, attacker["energy"] + 10)
        defender["hp"] = max(0, defender["hp"] - damage)
        defender["stun"] = max(defender["stun"], stun)
        defender["vx"] = attacker["facing"] * (220 if blocked else 360)
        attacker["lastHitAt"] = 0

    async def send(self, websocket: WebSocket, message_type: str, payload: dict) -> None:
        await websocket.send_json({"type": message_type, "payload": payload})

    async def broadcast_lobby(self) -> None:
        payload = {"rooms": await self.active_rooms()}
        disconnected = []
        for user_id, websocket in list(self.lobby_connections.items()):
            try:
                await self.send(websocket, "state.lobby", payload)
            except Exception:
                disconnected.append(user_id)
        for user_id in disconnected:
            self.disconnect_lobby(user_id)

    async def broadcast_room_state(self, room_id: str, message_type: str) -> None:
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                return
            payload = deepcopy(self._state_public(room))
        await self.broadcast_room(room_id, message_type, payload)

    async def broadcast_room(self, room_id: str, message_type: str, payload: dict) -> None:
        disconnected = []
        for user_id, websocket in list(self.room_connections.get(room_id, {}).items()):
            try:
                await self.send(websocket, message_type, payload)
            except Exception:
                disconnected.append(user_id)
        for user_id in disconnected:
            self.room_connections.get(room_id, {}).pop(user_id, None)


fighter_manager = DuelFighterManager()


@router.get("/fighter/catalog", response_model=SimpleResponse)
async def fighter_catalog():
    return SimpleResponse(
        success=True,
        message="ok",
        data={"characters": CHARACTERS, "maps": MAPS, "difficulties": AI_DIFFICULTIES},
    )


@router.get("/fighter/rooms", response_model=SimpleResponse)
async def fighter_rooms():
    return SimpleResponse(success=True, message="ok", data=await fighter_manager.active_rooms())


@router.post("/fighter/create-room", response_model=SimpleResponse)
async def fighter_create_room(current_user: str = Depends(get_current_user)):
    room = await fighter_manager.create_room(current_user, current_user)
    return SimpleResponse(success=True, message="房间已创建", data=room)


@router.post("/fighter/create-ai-room", response_model=SimpleResponse)
async def fighter_create_ai_room(
    request: AiRoomRequest,
    current_user: str = Depends(get_current_user),
):
    room = await fighter_manager.create_ai_room(current_user, current_user, request.difficulty)
    return SimpleResponse(success=True, message="人机房间已创建", data=room)


@router.post("/fighter/join-room", response_model=SimpleResponse)
async def fighter_join_room(
    request: RoomCodeRequest,
    current_user: str = Depends(get_current_user),
):
    room = await fighter_manager.join_room(request.room_code, current_user, current_user)
    return SimpleResponse(success=True, message="已加入房间", data=room)


@router.get("/fighter/my-room", response_model=SimpleResponse)
async def fighter_my_room(current_user: str = Depends(get_current_user)):
    room = await fighter_manager.my_room(current_user)
    return SimpleResponse(success=True, message="ok", data=room)


@router.post("/fighter/leave-room", response_model=SimpleResponse)
async def fighter_leave_room(current_user: str = Depends(get_current_user)):
    await fighter_manager.leave_room(current_user)
    return SimpleResponse(success=True, message="已离开房间")


@router.websocket("/ws/fighter/lobby")
async def fighter_lobby_websocket(websocket: WebSocket, user_id: str = Query(...)):
    await fighter_manager.connect_lobby(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "refresh":
                await fighter_manager.send(
                    websocket,
                    "state.lobby",
                    {"rooms": await fighter_manager.active_rooms()},
                )
    except WebSocketDisconnect:
        fighter_manager.disconnect_lobby(user_id)
    except Exception:
        fighter_manager.disconnect_lobby(user_id)


@router.websocket("/ws/fighter/room/{room_id}")
async def fighter_room_websocket(
    websocket: WebSocket,
    room_id: str,
    user_id: str = Query(...),
):
    slot = await fighter_manager.connect_room(websocket, room_id, user_id)
    if not slot:
        return
    try:
        while True:
            data = await websocket.receive_json()
            await fighter_manager.handle_message(room_id, user_id, data)
    except WebSocketDisconnect:
        await fighter_manager.disconnect_room(room_id, user_id)
    except Exception:
        await fighter_manager.disconnect_room(room_id, user_id)
