"""
植物大战僵尸游戏存档数据模型
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime


class PlantData(BaseModel):
    """植物数据模型"""
    type: str
    col: int
    row: int
    hp: int


class ZombieData(BaseModel):
    """僵尸数据模型"""
    type: str
    x: float
    y: float
    hp: int
    shieldHp: Optional[int] = 0


class LawnMowerData(BaseModel):
    """小推车数据模型"""
    id: int
    state: str
    x: float


class GameStateSave(BaseModel):
    """游戏状态保存模型"""
    sunEnergy: int
    score: int
    wave: int
    plants: List[PlantData]
    zombies: List[ZombieData]
    plantCooldowns: Dict[str, float]
    lawnMowers: List[LawnMowerData] = []


class GameStateResponse(BaseModel):
    """游戏状态响应模型"""
    success: bool
    message: str
    data: Optional[GameStateSave] = None


class GameStatsData(BaseModel):
    """游戏统计数据模型"""
    highScore: int = 0
    totalKills: int = 0
    totalWaves: int = 0


class UpdateGameStatsRequest(BaseModel):
    """更新统计数据请求模型"""
    score: int = 0
    kills: int = 0
    waves: int = 0


class GameStatsResponse(BaseModel):
    """游戏统计响应模型"""
    success: bool
    message: str
    data: Optional[GameStatsData] = None


class PvZConfigPayload(BaseModel):
    """PVZ配置覆盖数据"""
    plants: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    zombies: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    game: Dict[str, Any] = Field(default_factory=dict)


class PvZConfigResponse(BaseModel):
    """PVZ配置响应"""
    success: bool
    message: str
    is_vip: bool = False
    data: PvZConfigPayload = Field(default_factory=PvZConfigPayload)


# ==================== 多人对战模式数据模型 ====================

class RoomJoin(BaseModel):
    """加入房间请求模型"""
    room_code: str


class SimpleSuccessResponse(BaseModel):
    """简单成功响应模型"""
    success: bool
    message: str
    data: Optional[Any] = None


class SimpleRoomState(BaseModel):
    """简化版房间状态模型（用于存储在Redis中）"""
    room_id: str
    room_code: str
    status: str  # waiting/playing/paused/finished
    plant_player: Optional[str]
    zombie_player: Optional[str]
    created_at: str  # ISO format datetime string
    game_state: Optional[Dict[str, Any]] = None


class StartGameRequest(BaseModel):
    """开始游戏请求模型"""
    room_id: str


class RoomInfoResponse(BaseModel):
    """房间信息响应模型"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
