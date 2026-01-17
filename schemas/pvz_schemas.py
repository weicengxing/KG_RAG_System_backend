"""
植物大战僵尸游戏存档数据模型
"""

from pydantic import BaseModel
from typing import List, Dict, Optional


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


class GameStateSave(BaseModel):
    """游戏状态保存模型"""
    sunEnergy: int
    score: int
    wave: int
    plants: List[PlantData]
    zombies: List[ZombieData]
    plantCooldowns: Dict[str, float]


class GameStateResponse(BaseModel):
    """游戏状态响应模型"""
    success: bool
    message: str
    data: Optional[GameStateSave] = None
