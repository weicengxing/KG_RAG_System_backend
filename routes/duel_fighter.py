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
EFFECT_TTL = 0.42
COMBO_WINDOW = 0.82
COMBO_FINISHER_BONUS = 5
ITEM_RESPAWN_SECONDS = 9.0
BOTTOM_FALL_DAMAGE = 22

COMBO_VARIANT_LABELS = {
    "sweep": "S+J low sweep",
    "launcher": "S+K launcher",
    "guard_crush": "S+L guard crush",
    "dash_light": "dash light",
    "air_light": "air slash",
    "air_heavy": "air smash",
}


CHARACTERS = {
    "blade": {
        "id": "blade",
        "name": "岚刃",
        "role": "均衡剑士",
        "style": "长距离控场剑士",
        "trait": "刀尖甜点命中会积攒 风势，满 3 层后重击或绝招释放额外风刃。",
        "comboHint": "保持刀尖距离，用冲刺 J 试探，S+K 挑空后接远端重击。",
        "resource": {"key": "windStacks", "name": "风势", "max": 3, "color": "#7dd3fc"},
        "stats": {"speed": 7, "range": 9, "damage": 6, "tempo": 6, "survival": 5},
        "color": "#38bdf8",
        "maxHp": 110,
        "speed": 370,
        "jump": 780,
        "width": 48,
        "height": 112,
        "attacks": {
            "light": {"damage": 7, "range": 108, "cooldown": 0.23, "stun": 0.13, "knockback": 250, "effect": "slash"},
            "heavy": {"damage": 14, "range": 148, "cooldown": 0.6, "stun": 0.25, "knockback": 410, "guardBreak": 14, "effect": "cleave"},
            "special": {"damage": 17, "range": 172, "cooldown": 1.0, "stun": 0.28, "energy": 32, "knockback": 340, "effect": "wind_arc"},
        },
    },
    "fist": {
        "id": "fist",
        "name": "赤拳",
        "role": "近身爆发",
        "style": "贴身压制爆发",
        "trait": "近身命中会积攒 怒气，连续轻拳和满怒绝招伤害更高。",
        "comboHint": "J-J-J 打出三连，再接 S+K 挑空，随后跳 K 或满怒绝招追击。",
        "resource": {"key": "fury", "name": "怒气", "max": 100, "color": "#fb7185"},
        "stats": {"speed": 7, "range": 3, "damage": 8, "tempo": 10, "survival": 6},
        "color": "#ef4444",
        "maxHp": 118,
        "speed": 345,
        "jump": 740,
        "width": 52,
        "height": 108,
        "attacks": {
            "light": {"damage": 6, "range": 64, "cooldown": 0.14, "stun": 0.11, "knockback": 190, "effect": "jab"},
            "heavy": {"damage": 18, "range": 88, "cooldown": 0.58, "stun": 0.31, "knockback": 500, "armor": 0.2, "effect": "haymaker"},
            "special": {"damage": 20, "range": 126, "cooldown": 1.0, "stun": 0.32, "energy": 30, "knockback": 600, "effect": "rush"},
        },
    },
    "shade": {
        "id": "shade",
        "name": "影步",
        "role": "高速拉扯",
        "style": "高速佯攻刺客",
        "trait": "背后命中和标记追击会积攒 影印，满 3 层后绝招变成双闪处决。",
        "comboHint": "用冲刺 J 穿插拉扯，重击上标记，再闪到身后触发影爆。",
        "resource": {"key": "shadowStacks", "name": "影印", "max": 3, "color": "#c084fc"},
        "stats": {"speed": 10, "range": 6, "damage": 6, "tempo": 8, "survival": 3},
        "color": "#a78bfa",
        "maxHp": 96,
        "speed": 435,
        "jump": 845,
        "width": 44,
        "height": 104,
        "attacks": {
            "light": {"damage": 5, "range": 88, "cooldown": 0.15, "stun": 0.1, "knockback": 170, "effect": "shadow_cut"},
            "heavy": {"damage": 10, "range": 128, "cooldown": 0.42, "stun": 0.2, "knockback": 250, "mark": 1.9, "effect": "shadow_mark"},
            "special": {"damage": 14, "range": 186, "cooldown": 0.86, "stun": 0.24, "energy": 28, "knockback": 310, "effect": "blink"},
        },
    },
    "guard": {
        "id": "guard",
        "name": "磐卫",
        "role": "重甲防守",
        "style": "重甲反击堡垒",
        "trait": "格挡会储存 壁垒，重击和破防会消耗层数扩大震地范围并强化护甲。",
        "comboHint": "先举盾蓄层，S+L 破防压制，再用重击震地封锁走位。",
        "resource": {"key": "bulwarkStacks", "name": "壁垒", "max": 3, "color": "#fbbf24"},
        "stats": {"speed": 2, "range": 6, "damage": 7, "tempo": 3, "survival": 10},
        "color": "#f59e0b",
        "maxHp": 142,
        "speed": 275,
        "jump": 660,
        "width": 58,
        "height": 118,
        "attacks": {
            "light": {"damage": 7, "range": 82, "cooldown": 0.27, "stun": 0.16, "knockback": 270, "effect": "shield_bash"},
            "heavy": {"damage": 15, "range": 124, "cooldown": 0.7, "stun": 0.34, "knockback": 450, "area": True, "effect": "quake"},
            "special": {"damage": 17, "range": 148, "cooldown": 1.08, "stun": 0.39, "energy": 26, "knockback": 530, "area": True, "fortify": 1.0, "effect": "bulwark"},
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

MAPS = {
    "stone": {
        "id": "stone",
        "name": "裂柱武台",
        "mechanic": "台阶压制 / 中央高点",
        "description": "标准竞技图，但中央高台和两侧断柱会改变追击路线。",
        "width": 960,
        "height": 540,
        "groundY": 426,
        "leftWall": 46,
        "rightWall": 914,
        "sky": "#172033",
        "floor": "#6b7280",
        "accent": "#e5e7eb",
        "spawns": {"p1": {"x": 176}, "p2": {"x": 734}},
        "groundSegments": [
            {"id": "stone-left", "x": 46, "y": 426, "width": 306, "height": 54},
            {"id": "stone-mid", "x": 394, "y": 426, "width": 172, "height": 54},
            {"id": "stone-right", "x": 608, "y": 426, "width": 306, "height": 54},
        ],
        "platforms": [
            {"id": "stone-step-left", "x": 155, "y": 348, "width": 188, "height": 16},
            {"id": "stone-step-right", "x": 617, "y": 348, "width": 188, "height": 16},
            {"id": "stone-crown", "x": 386, "y": 276, "width": 188, "height": 16},
            {"id": "stone-low-left", "x": 298, "y": 384, "width": 100, "height": 14},
            {"id": "stone-low-right", "x": 562, "y": 384, "width": 100, "height": 14},
        ],
        "hazards": [
            {"id": "stone-pit-left", "kind": "pit", "x": 352, "y": 438, "width": 42, "height": 42, "damage": 7},
            {"id": "stone-pit-right", "kind": "pit", "x": 566, "y": 438, "width": 42, "height": 42, "damage": 7},
        ],
    },
    "bamboo": {
        "id": "bamboo",
        "name": "竹雨风廊",
        "mechanic": "横风 / 水洼减速 / 弹竹",
        "description": "雨林地形会把双方推向中央，弹竹可快速换层。",
        "width": 960,
        "height": 540,
        "groundY": 432,
        "leftWall": 38,
        "rightWall": 922,
        "sky": "#10231f",
        "floor": "#3f7a5b",
        "accent": "#7dd3fc",
        "spawns": {"p1": {"x": 142}, "p2": {"x": 766}},
        "groundSegments": [
            {"id": "bamboo-ground-left", "x": 38, "y": 432, "width": 324, "height": 52, "friction": 0.7},
            {"id": "bamboo-water", "x": 362, "y": 444, "width": 236, "height": 40, "friction": 0.42},
            {"id": "bamboo-ground-right", "x": 598, "y": 432, "width": 324, "height": 52, "friction": 0.7},
        ],
        "platforms": [
            {"id": "bamboo-shelf-left", "x": 90, "y": 352, "width": 166, "height": 14},
            {"id": "bamboo-shelf-mid", "x": 380, "y": 298, "width": 196, "height": 14},
            {"id": "bamboo-shelf-right", "x": 704, "y": 352, "width": 166, "height": 14},
            {
                "id": "bamboo-swing",
                "x": 398,
                "y": 386,
                "width": 164,
                "height": 14,
                "move": {"axis": "x", "from": 330, "to": 466, "speed": 66, "phase": 0.35},
            },
        ],
        "hazards": [
            {"id": "bamboo-deep-water", "kind": "water", "x": 408, "y": 450, "width": 144, "height": 30, "damage": 2.5, "slow": 0.45},
        ],
        "forceZones": [
            {"id": "bamboo-left-wind", "kind": "wind", "x": 40, "y": 86, "width": 270, "height": 320, "fx": 430, "fy": -55},
            {"id": "bamboo-right-wind", "kind": "wind", "x": 650, "y": 86, "width": 270, "height": 320, "fx": -430, "fy": -55},
        ],
        "jumpPads": [
            {"id": "bamboo-pad-left", "x": 304, "y": 416, "width": 48, "height": 16, "boost": 980},
            {"id": "bamboo-pad-right", "x": 608, "y": 416, "width": 48, "height": 16, "boost": 980},
        ],
    },
    "lava": {
        "id": "lava",
        "name": "熔岩断桥",
        "mechanic": "裂谷 / 火舌 / 横移石台",
        "description": "中央是持续伤害的熔岩裂谷，移动石台决定越线时机。",
        "width": 960,
        "height": 540,
        "groundY": 414,
        "leftWall": 82,
        "rightWall": 878,
        "sky": "#261414",
        "floor": "#7c2d12",
        "accent": "#fb923c",
        "spawns": {"p1": {"x": 154}, "p2": {"x": 754}},
        "groundSegments": [
            {"id": "lava-left-island", "x": 82, "y": 414, "width": 288, "height": 58},
            {"id": "lava-right-island", "x": 590, "y": 414, "width": 288, "height": 58},
            {"id": "lava-top-left", "x": 192, "y": 350, "width": 136, "height": 18},
            {"id": "lava-top-right", "x": 632, "y": 350, "width": 136, "height": 18},
        ],
        "platforms": [
            {
                "id": "lava-ferry",
                "x": 394,
                "y": 362,
                "width": 172,
                "height": 16,
                "move": {"axis": "x", "from": 326, "to": 462, "speed": 72, "phase": 0},
            },
            {"id": "lava-crown", "x": 402, "y": 272, "width": 156, "height": 16},
        ],
        "hazards": [
            {"id": "lava-rift", "kind": "lava", "x": 370, "y": 452, "width": 220, "height": 88, "damage": 999, "lethal": True},
            {"id": "lava-left-flame", "kind": "flame", "x": 250, "y": 396, "width": 48, "height": 20, "damage": 7},
            {"id": "lava-right-flame", "kind": "flame", "x": 662, "y": 396, "width": 48, "height": 20, "damage": 7},
        ],
    },
    "sky": {
        "id": "sky",
        "name": "浮空风祠",
        "mechanic": "上升气流 / 无底坠落 / 多层追击",
        "description": "地面被打碎，依靠上升风柱和窄平台打空中压制。",
        "width": 960,
        "height": 540,
        "groundY": 468,
        "leftWall": 48,
        "rightWall": 912,
        "sky": "#0f2344",
        "floor": "#475569",
        "accent": "#93c5fd",
        "voidDamage": 18,
        "spawns": {"p1": {"x": 178}, "p2": {"x": 734}},
        "groundSegments": [
            {"id": "sky-left-root", "x": 76, "y": 456, "width": 170, "height": 38},
            {"id": "sky-right-root", "x": 714, "y": 456, "width": 170, "height": 38},
            {"id": "sky-mid-root", "x": 410, "y": 444, "width": 140, "height": 38},
        ],
        "platforms": [
            {"id": "sky-left-1", "x": 126, "y": 360, "width": 148, "height": 14},
            {"id": "sky-right-1", "x": 686, "y": 360, "width": 148, "height": 14},
            {"id": "sky-mid-1", "x": 382, "y": 308, "width": 196, "height": 14},
            {
                "id": "sky-lift-left",
                "x": 284,
                "y": 402,
                "width": 118,
                "height": 14,
                "move": {"axis": "y", "from": 360, "to": 434, "speed": 44, "phase": 0.2},
            },
            {
                "id": "sky-lift-right",
                "x": 558,
                "y": 402,
                "width": 118,
                "height": 14,
                "move": {"axis": "y", "from": 360, "to": 434, "speed": 44, "phase": 0.7},
            },
        ],
        "forceZones": [
            {"id": "sky-updraft-mid", "kind": "updraft", "x": 424, "y": 210, "width": 112, "height": 248, "fx": 0, "fy": -820},
            {"id": "sky-updraft-left", "kind": "updraft", "x": 252, "y": 292, "width": 84, "height": 168, "fx": 70, "fy": -520},
            {"id": "sky-updraft-right", "kind": "updraft", "x": 624, "y": 292, "width": 84, "height": 168, "fx": -70, "fy": -520},
        ],
        "hazards": [
            {"id": "sky-void", "kind": "void", "x": 0, "y": 506, "width": 960, "height": 40, "damage": 0},
        ],
    },
    "mirror": {
        "id": "mirror",
        "name": "镜门遗迹",
        "mechanic": "双传送门 / 中央尖刺 / 斜线绕后",
        "description": "两侧镜门可瞬移到对面高台，适合绕背和反打。",
        "width": 960,
        "height": 540,
        "groundY": 426,
        "leftWall": 50,
        "rightWall": 910,
        "sky": "#1e1b4b",
        "floor": "#57534e",
        "accent": "#c4b5fd",
        "spawns": {"p1": {"x": 162}, "p2": {"x": 746}},
        "groundSegments": [
            {"id": "mirror-left-floor", "x": 50, "y": 426, "width": 342, "height": 54},
            {"id": "mirror-right-floor", "x": 568, "y": 426, "width": 342, "height": 54},
        ],
        "platforms": [
            {"id": "mirror-left-high", "x": 108, "y": 326, "width": 158, "height": 15},
            {"id": "mirror-right-high", "x": 694, "y": 326, "width": 158, "height": 15},
            {"id": "mirror-mid-low", "x": 374, "y": 372, "width": 212, "height": 15},
            {"id": "mirror-mid-top", "x": 424, "y": 260, "width": 112, "height": 15},
        ],
        "hazards": [
            {"id": "mirror-spikes", "kind": "spikes", "x": 424, "y": 426, "width": 112, "height": 28, "damage": 10, "knockY": -420},
        ],
        "portals": [
            {"id": "mirror-gate-left", "pair": "mirror-gate-right", "x": 84, "y": 296, "width": 34, "height": 82, "exitX": 816, "exitY": 260, "exitFacing": -1},
            {"id": "mirror-gate-right", "pair": "mirror-gate-left", "x": 842, "y": 296, "width": 34, "height": 82, "exitX": 110, "exitY": 260, "exitFacing": 1},
        ],
        "forceZones": [
            {"id": "mirror-center-pull", "kind": "pull", "x": 392, "y": 86, "width": 176, "height": 320, "fxToCenter": 360, "fy": -40},
        ],
    },
    "reef": {
        "id": "reef",
        "name": "深海遗迹",
        "mechanic": "水下浮力 / 共同敌人 / 潮汐道具",
        "description": "整张图在水下，双方要一边游动抢道具，一边躲鲨鱼、鲸鱼和游泳猛虎。",
        "width": 960,
        "height": 540,
        "groundY": 472,
        "leftWall": 42,
        "rightWall": 918,
        "sky": "#082f49",
        "floor": "#155e75",
        "accent": "#67e8f9",
        "voidDamage": 20,
        "gravityScale": 0.28,
        "waterMap": True,
        "spawns": {"p1": {"x": 142, "y": 322}, "p2": {"x": 766, "y": 322}},
        "groundSegments": [
            {"id": "reef-left-ruin", "x": 42, "y": 462, "width": 220, "height": 42, "friction": 0.58},
            {"id": "reef-mid-ruin", "x": 364, "y": 474, "width": 232, "height": 42, "friction": 0.58},
            {"id": "reef-right-ruin", "x": 698, "y": 462, "width": 220, "height": 42, "friction": 0.58},
        ],
        "platforms": [
            {"id": "reef-coral-left", "x": 100, "y": 364, "width": 156, "height": 14},
            {"id": "reef-coral-right", "x": 704, "y": 364, "width": 156, "height": 14},
            {"id": "reef-altar", "x": 382, "y": 286, "width": 196, "height": 14},
            {
                "id": "reef-drift",
                "x": 398,
                "y": 402,
                "width": 164,
                "height": 14,
                "move": {"axis": "y", "from": 360, "to": 430, "speed": 36, "phase": 0.15},
            },
        ],
        "forceZones": [
            {"id": "reef-left-current", "kind": "current", "x": 42, "y": 112, "width": 250, "height": 300, "fx": 300, "fy": -80},
            {"id": "reef-right-current", "kind": "current", "x": 668, "y": 112, "width": 250, "height": 300, "fx": -300, "fy": -80},
            {"id": "reef-mid-up", "kind": "bubble", "x": 420, "y": 236, "width": 120, "height": 260, "fx": 0, "fy": -460},
        ],
        "hazards": [
            {"id": "reef-trench", "kind": "void", "x": 0, "y": 520, "width": 960, "height": 20, "damage": 0},
        ],
    },
}

MAP_PICKUPS = {
    "stone": [
        {"id": "stone-bell", "kind": "shock", "name": "震钟", "x": 460, "y": 238, "width": 34, "height": 34},
        {"id": "stone-herb", "kind": "heal", "name": "止血草", "x": 188, "y": 308, "width": 30, "height": 30},
        {"id": "stone-core", "kind": "energy", "name": "石心", "x": 744, "y": 308, "width": 30, "height": 30},
    ],
    "bamboo": [
        {"id": "bamboo-seed", "kind": "haste", "name": "风种", "x": 468, "y": 258, "width": 30, "height": 30},
        {"id": "bamboo-herb-left", "kind": "heal", "name": "雨露", "x": 140, "y": 314, "width": 30, "height": 30},
        {"id": "bamboo-herb-right", "kind": "heal", "name": "雨露", "x": 792, "y": 314, "width": 30, "height": 30},
    ],
    "lava": [
        {"id": "lava-ember", "kind": "energy", "name": "余烬核", "x": 464, "y": 232, "width": 32, "height": 32},
        {"id": "lava-blast-left", "kind": "shock", "name": "火爆石", "x": 238, "y": 310, "width": 32, "height": 32},
        {"id": "lava-blast-right", "kind": "shock", "name": "火爆石", "x": 690, "y": 310, "width": 32, "height": 32},
    ],
    "sky": [
        {"id": "sky-feather", "kind": "launch", "name": "风羽", "x": 466, "y": 268, "width": 30, "height": 30},
        {"id": "sky-core-left", "kind": "energy", "name": "云核", "x": 170, "y": 320, "width": 30, "height": 30},
        {"id": "sky-core-right", "kind": "energy", "name": "云核", "x": 760, "y": 320, "width": 30, "height": 30},
    ],
    "mirror": [
        {"id": "mirror-shard", "kind": "swap", "name": "镜片", "x": 464, "y": 330, "width": 32, "height": 32},
        {"id": "mirror-energy-left", "kind": "energy", "name": "紫晶", "x": 174, "y": 288, "width": 30, "height": 30},
        {"id": "mirror-energy-right", "kind": "energy", "name": "紫晶", "x": 756, "y": 288, "width": 30, "height": 30},
    ],
}

MAP_PICKUPS["reef"] = [
    {"id": "reef-pearl", "kind": "tide", "name": "潮汐珠", "x": 468, "y": 248, "width": 32, "height": 32},
    {"id": "reef-bubble", "kind": "shield", "name": "护身泡", "x": 168, "y": 326, "width": 30, "height": 30},
    {"id": "reef-ice", "kind": "freeze", "name": "寒流晶", "x": 760, "y": 326, "width": 30, "height": 30},
]

EXTRA_PICKUP_KINDS = {
    "stone": ["bomb", "shield", "freeze"],
    "bamboo": ["tide", "shield", "bomb"],
    "lava": ["shield", "anchor", "bomb"],
    "sky": ["tide", "freeze", "anchor"],
    "mirror": ["freeze", "bomb", "shield"],
    "reef": ["heal", "energy", "haste", "launch", "bomb", "anchor"],
}

ITEM_SPAWN_POINTS = {
    "stone": [(178, 310), (330, 344), (464, 236), (596, 344), (752, 310), (466, 382)],
    "bamboo": [(134, 314), (318, 382), (468, 256), (620, 382), (792, 314), (468, 404)],
    "lava": [(238, 310), (464, 232), (690, 310), (260, 378), (672, 378), (480, 326)],
    "sky": [(170, 320), (326, 356), (466, 268), (632, 356), (760, 320), (476, 404)],
    "mirror": [(174, 288), (464, 224), (756, 288), (464, 334), (230, 388), (700, 388)],
    "reef": [(164, 318), (286, 392), (468, 246), (650, 392), (774, 318), (480, 430), (480, 330)],
}

PICKUP_KIND_META = {
    "heal": {"name": "止血草", "width": 30, "height": 30},
    "energy": {"name": "能量核", "width": 30, "height": 30},
    "haste": {"name": "风种", "width": 30, "height": 30},
    "launch": {"name": "风羽", "width": 30, "height": 30},
    "shock": {"name": "震钟", "width": 34, "height": 34},
    "swap": {"name": "镜片", "width": 32, "height": 32},
    "shield": {"name": "护盾泡", "width": 32, "height": 32},
    "freeze": {"name": "寒流晶", "width": 32, "height": 32},
    "bomb": {"name": "爆裂果", "width": 34, "height": 34},
    "anchor": {"name": "重锚", "width": 34, "height": 34},
    "tide": {"name": "潮汐珠", "width": 32, "height": 32},
}

MAP_ENEMIES = {
    "reef": [
        {"id": "reef-shark", "kind": "shark", "name": "巡游鲨鱼", "x": 84, "y": 176, "width": 76, "height": 30, "from": 70, "to": 810, "speed": 176, "damage": 9, "stun": 0.18},
        {"id": "reef-whale", "kind": "whale", "name": "沉眠鲸", "x": 684, "y": 106, "width": 142, "height": 48, "from": 110, "to": 760, "speed": 58, "damage": 6, "stun": 0.16, "pulseEvery": 3.8},
        {"id": "reef-tiger", "kind": "tiger", "name": "游泳猛虎", "x": 778, "y": 382, "width": 82, "height": 34, "from": 96, "to": 806, "speed": 132, "damage": 11, "stun": 0.24},
    ],
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
            "padCooldown": 0,
            "portalCooldown": 0,
            "surfaceFriction": FLOOR_FRICTION,
            "attack": None,
            "attackVariant": None,
            "activeAttack": None,
            "attackTimer": 0,
            "lastHitAt": 0,
            "comboStep": 0,
            "comboTimer": 0,
            "comboName": "",
            "comboTextTimer": 0,
            "armorTimer": 0,
            "fortifyTimer": 0,
            "shadowMark": 0,
            "hasteTimer": 0,
            "windStacks": 0,
            "fury": 0,
            "shadowStacks": 0,
            "bulwarkStacks": 0,
            "resourceText": "",
            "resourceTextTimer": 0,
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
            "attackVariant": player.get("attackVariant"),
            "activeAttack": player.get("activeAttack"),
            "attackTimer": round(player["attackTimer"], 2),
            "comboStep": player.get("comboStep", 0),
            "comboName": player.get("comboName", ""),
            "comboTextTimer": round(player.get("comboTextTimer", 0), 2),
            "armorTimer": round(player.get("armorTimer", 0), 2),
            "fortifyTimer": round(player.get("fortifyTimer", 0), 2),
            "shadowMark": round(player.get("shadowMark", 0), 2),
            "hasteTimer": round(player.get("hasteTimer", 0), 2),
            "windStacks": int(player.get("windStacks", 0)),
            "fury": round(player.get("fury", 0), 1),
            "shadowStacks": int(player.get("shadowStacks", 0)),
            "bulwarkStacks": int(player.get("bulwarkStacks", 0)),
            "resourceText": player.get("resourceText", ""),
            "resourceTextTimer": round(player.get("resourceTextTimer", 0), 2),
        }

    def _moving_value(self, start: float, end: float, speed: float, elapsed: float, phase: float = 0) -> tuple[float, float]:
        distance = abs(end - start)
        if distance <= 0 or speed <= 0:
            return start, 0
        period = (distance * 2) / speed
        local_time = (elapsed + period * phase) % period
        if local_time <= period / 2:
            value = start + (end - start) * (local_time / (period / 2))
            direction = 1 if end >= start else -1
        else:
            value = end + (start - end) * ((local_time - period / 2) / (period / 2))
            direction = -1 if end >= start else 1
        return value, direction * speed

    def _runtime_platforms(self, map_data: dict, elapsed: float = 0) -> list:
        platforms = []
        for platform in map_data.get("platforms", []):
            item = deepcopy(platform)
            move = item.get("move")
            item["vx"] = 0
            item["vy"] = 0
            if move:
                axis = move.get("axis", "x")
                value, velocity = self._moving_value(
                    float(move.get("from", item.get(axis, 0))),
                    float(move.get("to", item.get(axis, 0))),
                    float(move.get("speed", 0)),
                    elapsed,
                    float(move.get("phase", 0)),
                )
                item[axis] = value
                item["vx" if axis == "x" else "vy"] = velocity
            platforms.append(item)
        return platforms

    def _map_for_room(self, room: dict) -> dict:
        map_data = deepcopy(MAPS[room["mapId"]])
        elapsed = float(room.get("matchTime", 0))
        map_data["platforms"] = self._runtime_platforms(map_data, elapsed)
        return map_data

    def _state_public(self, room: dict) -> dict:
        return {
            "roomId": room["roomId"],
            "roomCode": room["roomCode"],
            "status": room["status"],
            "mode": room.get("mode", "pvp"),
            "aiDifficulty": room.get("aiDifficulty"),
            "winner": room.get("winner"),
            "finishedReason": room.get("finishedReason"),
            "map": self._map_for_room(room),
            "mapId": room["mapId"],
            "characters": CHARACTERS,
            "difficulties": AI_DIFFICULTIES,
            "projectiles": room.get("projectiles", []),
            "effects": room.get("effects", []),
            "items": [
                item for item in room.get("items", [])
                if item.get("active", True)
            ],
            "enemies": room.get("enemies", []),
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
                "effects": [],
                "items": [],
                "enemies": [],
                "players": {
                    "p1": self._new_player(user_id, username, "p1"),
                    "p2": None,
                },
            }
            self._reset_items_locked(room)
            self._reset_enemies_locked(room)
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
                "effects": [],
                "items": [],
                "enemies": [],
                "players": {
                    "p1": self._new_player(user_id, username, "p1"),
                    "p2": ai_player,
                },
            }
            self._reset_items_locked(room)
            self._reset_enemies_locked(room)
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
                    self._reset_items_locked(room)
                    self._reset_enemies_locked(room)
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
        room["matchTime"] = 0
        self._reset_positions_locked(room)
        room["status"] = "playing"
        room["winner"] = None
        room["finishedReason"] = None
        room["projectiles"] = []
        room["effects"] = []
        self._reset_items_locked(room)
        self._reset_enemies_locked(room)

    def _keep_ai_ready_locked(self, room: dict) -> None:
        for player in room["players"].values():
            if player and player.get("isAI"):
                player["ready"] = True

    def _reset_items_locked(self, room: dict) -> None:
        map_id = room["mapId"]
        base_items = [deepcopy(item) for item in MAP_PICKUPS.get(map_id, [])]
        extra_kinds = random.sample(EXTRA_PICKUP_KINDS.get(map_id, []), k=min(2, len(EXTRA_PICKUP_KINDS.get(map_id, []))))
        for index, kind in enumerate(extra_kinds):
            meta = PICKUP_KIND_META[kind]
            base_items.append({
                "id": f"{map_id}-{kind}-{index}",
                "kind": kind,
                "name": meta["name"],
                "width": meta["width"],
                "height": meta["height"],
            })
        spawn_points = list(ITEM_SPAWN_POINTS.get(map_id, []))
        random.shuffle(spawn_points)
        room["items"] = []
        for index, item in enumerate(base_items):
            self._randomize_item_position(map_id, item, spawn_points, index)
            item["active"] = True
            item["respawnAt"] = 0
            room["items"].append(item)

    def _randomize_item_position(self, map_id: str, item: dict, spawn_points: Optional[list] = None, index: int = 0) -> None:
        points = spawn_points if spawn_points is not None else list(ITEM_SPAWN_POINTS.get(map_id, []))
        if points:
            x, y = random.choice(points) if spawn_points is None else points[index % len(points)]
            item["x"] = x + random.uniform(-18, 18)
            item["y"] = y + random.uniform(-12, 12)
            return
        item["x"] = float(item.get("x", 460)) + random.uniform(-36, 36)
        item["y"] = float(item.get("y", 300)) + random.uniform(-18, 18)

    def _reset_enemies_locked(self, room: dict) -> None:
        room["enemies"] = [
            {
                **deepcopy(enemy),
                "baseY": float(enemy.get("y", 0)),
                "vx": float(enemy.get("speed", 0)),
                "vy": 0,
                "facing": 1,
                "hitCooldown": 0,
                "pulseTimer": float(enemy.get("pulseEvery", 0)) if enemy.get("pulseEvery") else 0,
            }
            for enemy in MAP_ENEMIES.get(room["mapId"], [])
        ]

    def _landing_surfaces(self, map_data: dict) -> list:
        surfaces = []
        if map_data.get("groundSegments"):
            surfaces.extend(map_data.get("groundSegments", []))
        else:
            surfaces.append({
                "id": "fallback-ground",
                "x": map_data["leftWall"],
                "y": map_data["groundY"],
                "width": map_data["rightWall"] - map_data["leftWall"],
                "height": map_data.get("height", 540) - map_data["groundY"],
            })
        surfaces.extend(map_data.get("platforms", []))
        return surfaces

    def _spawn_y_for_x(self, map_data: dict, x: float, character: dict) -> float:
        candidate = map_data.get("groundY", 420)
        for surface in self._landing_surfaces(map_data):
            if surface["x"] <= x + character["width"] / 2 <= surface["x"] + surface["width"]:
                candidate = min(candidate, surface["y"])
        return candidate - character["height"]

    def _place_player_on_spawn(self, room: dict, player: dict, map_data: dict) -> None:
        character = CHARACTERS[player["characterId"]]
        spawn = map_data.get("spawns", {}).get(player["slot"], {})
        fallback_x = map_data["leftWall"] + 170 if player["slot"] == "p1" else map_data["rightWall"] - 170
        x = clamp(float(spawn.get("x", fallback_x)), map_data["leftWall"], map_data["rightWall"] - character["width"])
        y = float(spawn.get("y", self._spawn_y_for_x(map_data, x, character)))
        player.update({
            "x": x,
            "y": y,
            "vx": 0,
            "vy": 0,
            "facing": 1 if player["slot"] == "p1" else -1,
            "grounded": True,
            "blocking": False,
            "stun": 0,
            "cooldown": 0,
            "padCooldown": 0,
            "portalCooldown": 0,
            "surfaceFriction": FLOOR_FRICTION,
            "attack": None,
            "attackVariant": None,
            "activeAttack": None,
            "attackTimer": 0,
            "comboStep": 0,
            "comboTimer": 0,
            "comboName": "",
            "comboTextTimer": 0,
            "armorTimer": 0,
            "fortifyTimer": 0,
            "shadowMark": 0,
            "hasteTimer": 0,
            "windStacks": 0,
            "fury": 0,
            "shadowStacks": 0,
            "bulwarkStacks": 0,
            "resourceText": "",
            "resourceTextTimer": 0,
            "input": empty_input(),
            "pendingAction": None,
        })

    def _reset_positions_locked(self, room: dict) -> None:
        map_data = self._map_for_room(room)
        for slot, player in room["players"].items():
            if not player:
                continue
            character = CHARACTERS[player["characterId"]]
            self._place_player_on_spawn(room, player, map_data)
            player["hp"] = character["maxHp"]
            player["energy"] = 20

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
        room["effects"] = []
        room["matchTime"] = 0
        self._reset_items_locked(room)
        self._reset_enemies_locked(room)
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
        room["matchTime"] = float(room.get("matchTime", 0)) + dt
        map_data = self._map_for_room(room)
        for player in players:
            if player.get("isAI"):
                opponent = players[1] if player is players[0] else players[0]
                self._update_ai_input(player, opponent, dt)
        for player in players:
            opponent = players[1] if player is players[0] else players[0]
            self._tick_player(room, player, opponent, map_data, dt)
        self._tick_projectiles(room, players, map_data, dt)
        self._tick_effects(room, dt)
        self._tick_items(room, players, map_data)
        self._tick_enemies(room, players, map_data, dt)
        self._resolve_overlap(players[0], players[1])
        self._try_hit(room, players[0], players[1])
        self._try_hit(room, players[1], players[0])
        for player in players:
            opponent = players[1] if player is players[0] else players[0]
            if opponent["hp"] <= 0:
                room["status"] = "finished"
                room["winner"] = player["slot"]
                room["finishedReason"] = room.get("finishedReason") or "ko"
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
                if random.random() < (0.18 if difficulty["id"] == "easy" else 0.34):
                    ai["input"]["down"] = True
                    if opponent.get("blocking") and ai["energy"] >= 30:
                        action = "special"
                ai["pendingAction"] = action

    def _rect_overlap(self, x: float, y: float, width: float, height: float, rect: dict) -> bool:
        return (
            x + width > rect["x"]
            and x < rect["x"] + rect["width"]
            and y + height > rect["y"]
            and y < rect["y"] + rect["height"]
        )

    def _center_in_rect(self, player: dict, character: dict, rect: dict) -> bool:
        center_x = player["x"] + character["width"] / 2
        center_y = player["y"] + character["height"] / 2
        return (
            rect["x"] <= center_x <= rect["x"] + rect["width"]
            and rect["y"] <= center_y <= rect["y"] + rect["height"]
        )

    def _apply_force_zones(self, player: dict, character: dict, map_data: dict, dt: float) -> None:
        center_x = player["x"] + character["width"] / 2
        for zone in map_data.get("forceZones", []):
            if not self._center_in_rect(player, character, zone):
                continue
            fx = float(zone.get("fx", 0))
            if zone.get("fxToCenter"):
                zone_center = zone["x"] + zone["width"] / 2
                direction = 1 if center_x < zone_center else -1
                fx += direction * float(zone["fxToCenter"])
            player["vx"] += fx * dt
            player["vy"] += float(zone.get("fy", 0)) * dt
            player["vx"] = clamp(player["vx"], -760, 760)
            player["vy"] = clamp(player["vy"], -1120, 1200)

    def _apply_jump_pads(self, player: dict, character: dict, map_data: dict) -> None:
        if player.get("padCooldown", 0) > 0:
            return
        feet_y = player["y"] + character["height"] - 8
        for pad in map_data.get("jumpPads", []):
            if self._rect_overlap(player["x"], feet_y, character["width"], 12, pad):
                player["vy"] = -float(pad.get("boost", 900))
                player["grounded"] = False
                player["padCooldown"] = 0.45
                player["energy"] = min(100, player["energy"] + 6)
                return

    def _apply_portals(self, player: dict, character: dict, map_data: dict) -> None:
        if player.get("portalCooldown", 0) > 0:
            return
        for portal in map_data.get("portals", []):
            if not self._center_in_rect(player, character, portal):
                continue
            facing = int(portal.get("exitFacing", player["facing"]) or player["facing"])
            player["x"] = clamp(float(portal.get("exitX", player["x"])), map_data["leftWall"], map_data["rightWall"] - character["width"])
            player["y"] = float(portal.get("exitY", player["y"]))
            player["facing"] = facing
            player["vx"] = facing * 190
            player["vy"] = min(player["vy"], -120)
            player["portalCooldown"] = 0.75
            return

    def _apply_hazards(self, room: dict, player: dict, character: dict, map_data: dict, dt: float) -> None:
        for hazard in map_data.get("hazards", []):
            if not self._rect_overlap(player["x"], player["y"], character["width"], character["height"], hazard):
                continue
            if hazard.get("lethal"):
                player["hp"] = 0
                room["finishedReason"] = "lava_fall" if hazard.get("kind") == "lava" else "hazard"
                self._add_effect(room, "lava_burst", player["x"] - 20, hazard["y"] - 36, character["width"] + 40, 88, map_data.get("accent", "#fb923c"), player["facing"], ttl=0.7)
                return
            damage = float(hazard.get("damage", 3))
            if damage:
                player["hp"] = max(0, player["hp"] - damage * dt)
                player["energy"] = min(100, player["energy"] + 8 * dt)
            if hazard.get("knockY"):
                player["vy"] = min(player["vy"], float(hazard["knockY"]))
                player["grounded"] = False
            if hazard.get("slow"):
                player["vx"] *= float(hazard["slow"])

    def _resolve_terrain_collision(self, player: dict, character: dict, map_data: dict, previous_y: float, dt: float) -> None:
        landing_y = math.inf
        landed_surface = None
        for surface in self._landing_surfaces(map_data):
            surface_top = surface["y"] - character["height"]
            was_above = previous_y + character["height"] <= surface["y"] + 10
            is_falling = player["vy"] >= float(surface.get("vy", 0)) - 30
            overlaps_x = (
                player["x"] + character["width"] > surface["x"]
                and player["x"] < surface["x"] + surface["width"]
            )
            if was_above and is_falling and overlaps_x and player["y"] >= surface_top and surface_top < landing_y:
                landing_y = surface_top
                landed_surface = surface

        if landed_surface:
            player["y"] = landing_y
            player["vy"] = min(0, float(landed_surface.get("vy", 0)))
            player["grounded"] = True
            player["surfaceFriction"] = float(landed_surface.get("friction", FLOOR_FRICTION))
            player["x"] += float(landed_surface.get("vx", 0)) * dt
            player["y"] += float(landed_surface.get("vy", 0)) * dt
        else:
            player["surfaceFriction"] = FLOOR_FRICTION

    def _recover_from_void(self, room: dict, player: dict, character: dict, map_data: dict) -> bool:
        if player["y"] <= map_data.get("height", 540) + 120:
            return False
        if map_data.get("id") == "lava":
            player["hp"] = 0
            room["finishedReason"] = "lava_fall"
            self._add_effect(room, "lava_burst", player["x"] - 20, map_data.get("height", 540) - 90, character["width"] + 40, 88, map_data.get("accent", "#fb923c"), player["facing"], ttl=0.7)
            return True
        player["hp"] = max(0, player["hp"] - float(map_data.get("voidDamage", BOTTOM_FALL_DAMAGE)))
        energy = player["energy"]
        self._add_effect(room, "fall_return", player["x"] - 14, map_data.get("height", 540) - 86, character["width"] + 28, 72, map_data.get("accent", "#93c5fd"), player["facing"], ttl=0.5)
        self._place_player_on_spawn(room, player, map_data)
        player["energy"] = min(100, energy + 12)
        player["stun"] = 0.35
        return True

    def _tick_player(self, room: dict, player: dict, opponent: dict, map_data: dict, dt: float) -> None:
        character = CHARACTERS[player["characterId"]]
        player["cooldown"] = max(0, player["cooldown"] - dt)
        player["padCooldown"] = max(0, player.get("padCooldown", 0) - dt)
        player["portalCooldown"] = max(0, player.get("portalCooldown", 0) - dt)
        player["stun"] = max(0, player["stun"] - dt)
        player["attackTimer"] = max(0, player["attackTimer"] - dt)
        player["comboTimer"] = max(0, player.get("comboTimer", 0) - dt)
        player["comboTextTimer"] = max(0, player.get("comboTextTimer", 0) - dt)
        player["resourceTextTimer"] = max(0, player.get("resourceTextTimer", 0) - dt)
        player["armorTimer"] = max(0, player.get("armorTimer", 0) - dt)
        player["fortifyTimer"] = max(0, player.get("fortifyTimer", 0) - dt)
        player["shadowMark"] = max(0, player.get("shadowMark", 0) - dt)
        player["hasteTimer"] = max(0, player.get("hasteTimer", 0) - dt)
        if player["comboTimer"] == 0:
            player["comboStep"] = 0
        if player["comboTextTimer"] == 0:
            player["comboName"] = ""
        if player["resourceTextTimer"] == 0:
            player["resourceText"] = ""
        if player["attackTimer"] == 0:
            player["attack"] = None
            player["attackVariant"] = None
            player["activeAttack"] = None
        if player["stun"] <= 0:
            intent = player["input"]
            move = (1 if intent["right"] else 0) - (1 if intent["left"] else 0)
            player["blocking"] = intent["block"] and player["grounded"]
            if player["blocking"] and player["characterId"] == "guard":
                player["energy"] = min(100, player["energy"] + 5.5 * dt)
                if player["energy"] > 28:
                    before = player.get("bulwarkStacks", 0)
                    player["bulwarkStacks"] = min(3, before + dt * 0.75)
                    if int(player["bulwarkStacks"]) > int(before):
                        player["resourceText"] = "壁垒储存"
                        player["resourceTextTimer"] = 0.75
            if move:
                player["facing"] = move
                speed_bonus = 1.22 if player.get("hasteTimer", 0) > 0 else 1
                speed = character["speed"] * speed_bonus * (0.45 if player["blocking"] else 1)
                player["vx"] = move * speed
            else:
                player["vx"] *= player.get("surfaceFriction", FLOOR_FRICTION) if player["grounded"] else AIR_FRICTION
            if intent["up"] and player["grounded"] and not player["blocking"]:
                player["vy"] = -character["jump"]
                player["grounded"] = False
            if map_data.get("waterMap") and not player["blocking"]:
                if intent["up"]:
                    player["vy"] -= 780 * dt
                if intent["down"] and not player.get("pendingAction"):
                    player["vy"] += 520 * dt
            if player["pendingAction"]:
                self._start_attack(room, player, opponent, map_data, player["pendingAction"])
                player["pendingAction"] = None
        self._apply_force_zones(player, character, map_data, dt)
        previous_y = player["y"]
        gravity_scale = float(map_data.get("gravityScale", 1))
        player["vy"] += GRAVITY * gravity_scale * dt
        if map_data.get("waterMap"):
            player["vx"] *= 0.985
            player["vy"] *= 0.96
        player["x"] += player["vx"] * dt
        player["y"] += player["vy"] * dt
        player["grounded"] = False
        self._resolve_terrain_collision(player, character, map_data, previous_y, dt)
        player["x"] = clamp(player["x"], map_data["leftWall"], map_data["rightWall"] - character["width"])
        self._apply_jump_pads(player, character, map_data)
        self._apply_portals(player, character, map_data)
        self._apply_hazards(room, player, character, map_data, dt)
        if self._recover_from_void(room, player, character, map_data):
            return
        passive_energy = 3.4 if player["characterId"] == "shade" and not player["grounded"] else 2.5
        player["energy"] = clamp(player["energy"] + dt * passive_energy, 0, 100)

    def _combo_label(self, player: dict, variant: str, base_key: str) -> str:
        character_labels = {
            "blade": {
                "sweep": "岚刃 地刃扫",
                "launcher": "岚刃 挑云斩",
                "guard_crush": "岚刃 断风式",
                "dash_light": "岚刃 踏前刺",
                "air_light": "岚刃 落羽斩",
                "air_heavy": "岚刃 坠岚斩",
            },
            "fist": {
                "sweep": "赤拳 扫膝",
                "launcher": "赤拳 升龙肘",
                "guard_crush": "赤拳 崩山冲",
                "dash_light": "赤拳 贴身连拳",
                "air_light": "赤拳 空踏拳",
                "air_heavy": "赤拳 陨拳",
            },
            "shade": {
                "sweep": "影步 绊影",
                "launcher": "影步 月挑",
                "guard_crush": "影步 断影突",
                "dash_light": "影步 闪身刺",
                "air_light": "影步 飞影切",
                "air_heavy": "影步 影坠",
            },
            "guard": {
                "sweep": "磐卫 盾扫",
                "launcher": "磐卫 顶盾",
                "guard_crush": "磐卫 裂地盾",
                "dash_light": "磐卫 肩撞",
                "air_light": "磐卫 空盾拍",
                "air_heavy": "磐卫 落石压",
            },
        }
        return character_labels.get(player["characterId"], {}).get(variant, COMBO_VARIANT_LABELS.get(variant, base_key))

    def _derive_attack(self, player: dict, attack_key: str) -> tuple[str, dict]:
        character = CHARACTERS[player["characterId"]]
        base = deepcopy(character["attacks"][attack_key])
        intent = player["input"]
        variant = attack_key
        moving_forward = (
            (intent.get("right") and player["facing"] > 0) or
            (intent.get("left") and player["facing"] < 0)
        )

        if not player["grounded"] and attack_key == "light":
            variant = "air_light"
            base.update({"damage": max(5, base["damage"] - 1), "range": base["range"] + 10, "cooldown": 0.3, "stun": 0.16, "knockback": 300, "effect": "air_slice", "air": True})
        elif not player["grounded"] and attack_key == "heavy":
            variant = "air_heavy"
            base.update({"damage": base["damage"] + 2, "range": base["range"] + 6, "cooldown": base["cooldown"] + 0.08, "stun": base["stun"] + 0.04, "knockback": base.get("knockback", 360) + 80, "slam": True, "effect": "air_slam", "air": True})
        elif intent.get("down") and attack_key == "light":
            variant = "sweep"
            base.update({"damage": max(5, base["damage"] + 1), "range": base["range"] + 18, "cooldown": base["cooldown"] + 0.08, "stun": base["stun"] + 0.08, "knockback": 250, "low": True, "trip": True, "effect": "sweep"})
        elif intent.get("down") and attack_key == "heavy":
            variant = "launcher"
            base.update({"damage": max(8, base["damage"] - 2), "range": max(86, base["range"] - 8), "cooldown": base["cooldown"] + 0.1, "stun": base["stun"] + 0.04, "knockback": 160, "launch": -660, "effect": "launcher"})
        elif intent.get("down") and attack_key == "special":
            variant = "guard_crush"
            base.update({"damage": base["damage"] + 2, "range": base["range"] + 14, "cooldown": base["cooldown"] + 0.12, "stun": base["stun"] + 0.08, "knockback": base.get("knockback", 360) + 120, "guardBreak": base.get("guardBreak", 0) + 22, "area": True, "effect": "guard_crush"})
        elif moving_forward and attack_key == "light":
            variant = "dash_light"
            base.update({"damage": max(5, base["damage"]), "range": base["range"] + 24, "cooldown": base["cooldown"] + 0.06, "stun": base["stun"] + 0.02, "knockback": base.get("knockback", 260) + 70, "effect": "dash_light"})

        if player["characterId"] == "fist" and variant == "launcher":
            base["armor"] = max(base.get("armor", 0), 0.16)
        elif player["characterId"] == "shade" and variant == "dash_light":
            base["mark"] = max(base.get("mark", 0), 1.2)
        elif player["characterId"] == "guard" and variant == "guard_crush":
            base["fortify"] = max(base.get("fortify", 0), 0.55)
        elif player["characterId"] == "blade" and variant == "sweep":
            base["range"] += 12

        if player["characterId"] == "blade" and player.get("windStacks", 0) >= 3 and attack_key in {"heavy", "special"}:
            base["damage"] += 5
            base["range"] += 28
            base["guardBreak"] = base.get("guardBreak", 0) + 8
            base["windRelease"] = True
            base["effect"] = "wind_burst"
        elif player["characterId"] == "fist" and player.get("fury", 0) >= 60 and attack_key == "special":
            fury_scale = min(1.0, player.get("fury", 0) / 100)
            base["damage"] += 6 + fury_scale * 8
            base["range"] += 18
            base["knockback"] += 120
            base["armor"] = max(base.get("armor", 0), 0.34)
            base["furySpend"] = True
            base["effect"] = "fury_burst"
        elif player["characterId"] == "shade" and player.get("shadowStacks", 0) >= 3 and attack_key == "special":
            base["damage"] += 9
            base["range"] += 34
            base["stun"] += 0.08
            base["knockback"] += 110
            base["shadowExecute"] = True
            base["effect"] = "shadow_pop"
        elif player["characterId"] == "guard" and player.get("bulwarkStacks", 0) >= 1 and attack_key in {"heavy", "special"}:
            stacks = int(player.get("bulwarkStacks", 0))
            base["damage"] += stacks * 2.5
            base["range"] += stacks * 18
            base["knockback"] += stacks * 70
            base["fortify"] = max(base.get("fortify", 0), 0.45 + stacks * 0.18)
            base["bulwarkSpend"] = stacks
            if variant == "guard_crush" or attack_key == "special":
                base["effect"] = "bulwark_crash"

        return variant, base

    def _start_attack(self, room: dict, player: dict, opponent: dict, map_data: dict, attack_key: str) -> None:
        character = CHARACTERS[player["characterId"]]
        variant, attack = self._derive_attack(player, attack_key)
        if player["cooldown"] > 0:
            return
        energy_cost = attack.get("energy", 0)
        if player["energy"] < energy_cost:
            return
        player["energy"] -= energy_cost
        if attack.get("windRelease"):
            player["windStacks"] = 0
            player["resourceText"] = "风势爆发"
            player["resourceTextTimer"] = 1.0
        if attack.get("furySpend"):
            player["fury"] = max(0, player.get("fury", 0) - 70)
            player["resourceText"] = "怒气突进"
            player["resourceTextTimer"] = 1.0
        if attack.get("shadowExecute"):
            player["shadowStacks"] = 0
            player["resourceText"] = "影印处决"
            player["resourceTextTimer"] = 1.0
        if attack.get("bulwarkSpend"):
            player["bulwarkStacks"] = max(0, player.get("bulwarkStacks", 0) - attack.get("bulwarkSpend", 0))
            player["resourceText"] = "壁垒震裂"
            player["resourceTextTimer"] = 1.0
        if attack.get("armor"):
            player["armorTimer"] = max(player.get("armorTimer", 0), attack["armor"])
        if attack.get("fortify"):
            player["fortifyTimer"] = max(player.get("fortifyTimer", 0), attack["fortify"])
        player["attack"] = attack_key
        player["attackVariant"] = variant
        player["activeAttack"] = attack
        player["attackTimer"] = min(0.34, attack["cooldown"])
        player["cooldown"] = attack["cooldown"]
        player["lastHitAt"] = now_ms()
        if variant != attack_key:
            player["comboName"] = self._combo_label(player, variant, attack_key)
            player["comboTextTimer"] = 0.9
        if attack_key == "special":
            self._apply_special(room, player, opponent, map_data)
        self._add_attack_effect(room, player, attack_key)

    def _apply_special(self, room: dict, player: dict, opponent: dict, map_data: dict) -> None:
        character_id = player["characterId"]
        character = CHARACTERS[character_id]
        active_attack = player.get("activeAttack") or character["attacks"]["special"]
        if character_id == "blade":
            offsets = [(-24, 0.72), (-8, 1.0), (8, 1.0), (24, 0.72)] if active_attack.get("windRelease") else [(-20, 0.78), (0, 1), (20, 0.78)]
            for offset, scale in offsets:
                room.setdefault("projectiles", []).append({
                    "id": str(uuid.uuid4()),
                    "ownerSlot": player["slot"],
                    "kind": "blade_arc",
                    "x": player["x"] + character["width"] / 2,
                    "y": player["y"] + 42 + offset,
                    "vx": player["facing"] * (580 + abs(offset) * 3),
                    "width": 58 * scale,
                    "height": 18 * scale,
                    "damage": 9 * scale,
                    "stun": 0.18,
                    "ttl": 0.85,
                    "color": character["color"],
                })
            if active_attack.get("windRelease"):
                self._add_effect(room, "wind_burst", player["x"] - 22, player["y"] + 8, character["width"] + 44, character["height"] * 0.72, character["color"], player["facing"], ttl=0.64)
        elif character_id == "fist":
            fury_boosted = active_attack.get("furySpend")
            player["vx"] = player["facing"] * (920 if fury_boosted else 760)
            player["armorTimer"] = max(player.get("armorTimer", 0), 0.42 if fury_boosted else 0.28)
            if fury_boosted:
                self._add_effect(room, "fury_burst", player["x"] - 18, player["y"] + 28, character["width"] + 36, character["height"] * 0.42, character["color"], player["facing"], ttl=0.5)
        elif character_id == "shade":
            target_x = opponent["x"] - player["facing"] * 74
            self._add_effect(room, "afterimage", player["x"], player["y"], character["width"], character["height"], character["color"], player["facing"], ttl=0.5)
            player["x"] = clamp(target_x, map_data["leftWall"], map_data["rightWall"] - character["width"])
            player["y"] = min(player["y"], opponent["y"])
            player["facing"] = 1 if opponent["x"] > player["x"] else -1
            self._add_effect(room, "blink", player["x"], player["y"], character["width"], character["height"], character["color"], player["facing"], ttl=0.55)
            if active_attack.get("shadowExecute"):
                self._add_effect(room, "shadow_pop", opponent["x"] - 18, opponent["y"] + 10, character["width"] + 54, character["height"] * 0.7, character["color"], player["facing"], ttl=0.56)
        elif character_id == "guard":
            player["vx"] = -player["facing"] * 80
            player["fortifyTimer"] = max(player.get("fortifyTimer", 0), active_attack.get("fortify", 0.9))
            ring_type = "bulwark_crash" if active_attack.get("bulwarkSpend") else "guard_ring"
            self._add_effect(room, ring_type, player["x"] - 24, player["y"] - 18, character["width"] + 48, character["height"] + 34, character["color"], player["facing"], ttl=0.86)

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

    def _add_effect(
        self,
        room: dict,
        effect_type: str,
        x: float,
        y: float,
        width: float,
        height: float,
        color: str,
        direction: int = 1,
        *,
        ttl: float = EFFECT_TTL,
        extra: Optional[dict] = None,
    ) -> None:
        payload = {
            "id": str(uuid.uuid4()),
            "type": effect_type,
            "x": round(x, 2),
            "y": round(y, 2),
            "width": round(width, 2),
            "height": round(height, 2),
            "color": color,
            "direction": direction,
            "ttl": ttl,
            "maxTtl": ttl,
        }
        if extra:
            payload.update(extra)
        room.setdefault("effects", []).append(payload)

    def _add_attack_effect(self, room: dict, player: dict, attack_key: str) -> None:
        character = CHARACTERS[player["characterId"]]
        attack = player.get("activeAttack") or character["attacks"][attack_key]
        variant = player.get("attackVariant") or attack_key
        width = attack["range"]
        height = 56 if attack.get("area") else (42 if attack_key != "light" else 26)
        if attack.get("low"):
            height = 22
        x = player["x"] + character["width"] if player["facing"] > 0 else player["x"] - width
        y = player["y"] + character["height"] * (0.34 if attack_key != "special" else 0.24)
        if attack.get("low"):
            y = player["y"] + character["height"] * 0.72
        if attack.get("launch"):
            y = player["y"] + character["height"] * 0.16
            height = character["height"] * 0.62
        effect_type = attack.get("effect", "impact")
        if attack.get("area"):
            x = player["x"] + character["width"] / 2 - width / 2
            y = player["y"] + character["height"] * 0.48
        self._add_effect(room, effect_type, x, y, width, height, character["color"], player["facing"], ttl=0.54 if variant != attack_key else EFFECT_TTL)

    def _tick_effects(self, room: dict, dt: float) -> None:
        remaining = []
        for effect in room.get("effects", []):
            effect["ttl"] = round(effect.get("ttl", 0) - dt, 3)
            if effect["ttl"] > 0:
                remaining.append(effect)
        room["effects"] = remaining[-24:]

    def _tick_items(self, room: dict, players: list, map_data: dict) -> None:
        elapsed = float(room.get("matchTime", 0))
        for item in room.get("items", []):
            if not item.get("active", True):
                if elapsed >= float(item.get("respawnAt", 0)):
                    self._randomize_item_position(room["mapId"], item)
                    item["active"] = True
                else:
                    continue
            for player in players:
                character = CHARACTERS[player["characterId"]]
                if not self._rect_overlap(player["x"], player["y"], character["width"], character["height"], item):
                    continue
                opponent = next((other for other in players if other is not player), None)
                self._apply_item_effect(room, player, opponent, item, map_data)
                item["active"] = False
                item["respawnAt"] = elapsed + ITEM_RESPAWN_SECONDS
                break

    def _apply_item_effect(self, room: dict, player: dict, opponent: Optional[dict], item: dict, map_data: dict) -> None:
        character = CHARACTERS[player["characterId"]]
        kind = item.get("kind")
        cx = item["x"] + item["width"] / 2
        cy = item["y"] + item["height"] / 2
        color = {
            "heal": "#22c55e",
            "energy": "#38bdf8",
            "haste": "#facc15",
            "launch": "#93c5fd",
            "shock": "#fb923c",
            "swap": "#c084fc",
        }.get(kind, map_data.get("accent", "#f8fafc"))

        if kind == "heal":
            player["hp"] = min(character["maxHp"], player["hp"] + 20)
            player["stun"] = max(0, player["stun"] - 0.12)
        elif kind == "energy":
            player["energy"] = min(100, player["energy"] + 34)
        elif kind == "haste":
            player["hasteTimer"] = max(player.get("hasteTimer", 0), 4.0)
            player["energy"] = min(100, player["energy"] + 12)
        elif kind == "launch":
            player["vy"] = -980
            player["grounded"] = False
            player["energy"] = min(100, player["energy"] + 10)
        elif kind == "shock" and opponent:
            opponent_character = CHARACTERS[opponent["characterId"]]
            distance = abs((opponent["x"] + opponent_character["width"] / 2) - cx)
            if distance < 230:
                direction = 1 if opponent["x"] + opponent_character["width"] / 2 > cx else -1
                player["facing"] = direction
                self._apply_damage(player, opponent, 9, 0.22, 520, False)
                opponent["vx"] = direction * 520
                opponent["vy"] = min(opponent["vy"], -280)
            player["energy"] = min(100, player["energy"] + 8)
        elif kind == "swap" and opponent:
            px, py = player["x"], player["y"]
            player["x"], player["y"] = opponent["x"], opponent["y"]
            opponent["x"], opponent["y"] = px, py
            player["facing"] = 1 if opponent["x"] > player["x"] else -1
            opponent["facing"] = -player["facing"]
            player["portalCooldown"] = max(player.get("portalCooldown", 0), 0.45)
            opponent["portalCooldown"] = max(opponent.get("portalCooldown", 0), 0.45)
        elif kind == "shield":
            player["fortifyTimer"] = max(player.get("fortifyTimer", 0), 3.2)
            player["energy"] = min(100, player["energy"] + 10)
        elif kind == "freeze" and opponent:
            opponent["stun"] = max(opponent["stun"], 0.52)
            opponent["vx"] *= 0.18
            opponent["vy"] *= 0.35
        elif kind == "bomb":
            for target in [player, opponent]:
                if not target:
                    continue
                target_character = CHARACTERS[target["characterId"]]
                tx = target["x"] + target_character["width"] / 2
                ty = target["y"] + target_character["height"] / 2
                distance = math.hypot(tx - cx, ty - cy)
                if distance > 210:
                    continue
                direction = 1 if tx >= cx else -1
                blast_attacker = {"facing": direction}
                self._apply_damage(blast_attacker, target, 12 if target is opponent else 5, 0.22, 560, False)
                target["vy"] = min(target["vy"], -420)
        elif kind == "anchor" and opponent:
            opponent["vy"] = max(opponent["vy"], 820)
            opponent["stun"] = max(opponent["stun"], 0.2)
            opponent["energy"] = max(0, opponent["energy"] - 12)
        elif kind == "tide":
            player["hp"] = min(character["maxHp"], player["hp"] + 10)
            player["energy"] = min(100, player["energy"] + 22)
            player["vy"] = min(player["vy"], -360)
            if opponent:
                opponent["vx"] += -player["facing"] * 240

        self._add_effect(
            room,
            f"item_{kind}",
            cx - 34,
            cy - 34,
            68,
            68,
            color,
            player["facing"],
            ttl=0.64,
        )

    def _tick_enemies(self, room: dict, players: list, map_data: dict, dt: float) -> None:
        elapsed = float(room.get("matchTime", 0))
        for enemy in room.get("enemies", []):
            enemy["hitCooldown"] = max(0, float(enemy.get("hitCooldown", 0)) - dt)
            value, velocity = self._moving_value(
                float(enemy.get("from", enemy["x"])),
                float(enemy.get("to", enemy["x"])),
                float(enemy.get("speed", 0)),
                elapsed,
                float(enemy.get("phase", 0)),
            )
            enemy["x"] = value
            enemy["vx"] = velocity
            enemy["facing"] = 1 if velocity >= 0 else -1
            if enemy.get("kind") == "tiger":
                enemy["y"] = float(enemy.get("baseY", enemy.get("y", 360))) + math.sin(elapsed * 2.6) * 34
            elif enemy.get("kind") == "shark":
                enemy["y"] = float(enemy.get("baseY", enemy.get("y", 176))) + math.sin(elapsed * 1.8) * 20
            elif enemy.get("kind") == "whale":
                enemy["y"] = float(enemy.get("baseY", enemy.get("y", 106))) + math.sin(elapsed * 0.9) * 12
                enemy["pulseTimer"] = max(0, float(enemy.get("pulseTimer", 0)) - dt)
                if enemy["pulseTimer"] <= 0:
                    enemy["pulseTimer"] = float(enemy.get("pulseEvery", 3.8))
                    self._whale_pulse(room, enemy, players)

            for player in players:
                character = CHARACTERS[player["characterId"]]
                if enemy["hitCooldown"] > 0:
                    continue
                if self._rect_overlap(player["x"], player["y"], character["width"], character["height"], enemy):
                    direction = 1 if player["x"] + character["width"] / 2 >= enemy["x"] + enemy["width"] / 2 else -1
                    self._apply_enemy_hit(room, enemy, player, direction)
                    enemy["hitCooldown"] = 0.8

    def _whale_pulse(self, room: dict, enemy: dict, players: list) -> None:
        cx = enemy["x"] + enemy["width"] / 2
        cy = enemy["y"] + enemy["height"] / 2
        self._add_effect(room, "enemy_whale_pulse", cx - 130, cy - 80, 260, 160, "#67e8f9", enemy.get("facing", 1), ttl=0.75)
        for player in players:
            character = CHARACTERS[player["characterId"]]
            px = player["x"] + character["width"] / 2
            py = player["y"] + character["height"] / 2
            distance = math.hypot(px - cx, py - cy)
            if distance > 230:
                continue
            direction = 1 if px >= cx else -1
            player["vx"] += direction * 380
            player["vy"] = min(player["vy"], -260)
            player["stun"] = max(player["stun"], 0.12)

    def _apply_enemy_hit(self, room: dict, enemy: dict, player: dict, direction: int) -> None:
        attacker = {"facing": direction}
        self._apply_damage(attacker, player, float(enemy.get("damage", 8)), float(enemy.get("stun", 0.16)), 420, False)
        player["vy"] = min(player["vy"], -240)
        self._add_effect(
            room,
            f"enemy_{enemy.get('kind', 'hit')}",
            player["x"] - 16,
            player["y"] + 24,
            76,
            48,
            "#67e8f9" if enemy.get("kind") == "whale" else "#fef3c7",
            direction,
            ttl=0.36,
            extra={
                "damage": round(float(enemy.get("damage", 8)), 1),
                "blocked": False,
                "attackerSlot": "enemy",
                "defenderSlot": player["slot"],
                "hitStopMs": 58,
                "shake": 5,
                "flashWhiteMs": 55,
                "hitLevel": "enemy",
            },
        )

    def _apply_damage(self, attacker: dict, defender: dict, damage: float, stun: float, knockback: float, blocked: bool) -> None:
        if defender.get("armorTimer", 0) > 0:
            damage *= 0.72
            stun *= 0.55
        if defender.get("fortifyTimer", 0) > 0:
            damage *= 0.62
            stun *= 0.45
            knockback *= 0.45
        defender["hp"] = max(0, defender["hp"] - damage)
        if defender.get("characterId") == "fist" and not blocked and damage > 0:
            defender["fury"] = min(100, defender.get("fury", 0) + damage * 0.85)
            defender["resourceText"] = "怒气反燃"
            defender["resourceTextTimer"] = 0.65
        defender["stun"] = max(defender["stun"], stun)
        defender["vx"] = attacker["facing"] * (knockback * (0.55 if blocked else 1))

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
                    owner = next((item for item in players if item["slot"] == projectile["ownerSlot"]), None)
                    if not owner:
                        hit = True
                        break
                    blocked = player["blocking"] and player["energy"] >= 10
                    self._apply_damage(
                        owner,
                        player,
                        projectile["damage"] * (0.35 if blocked else 1),
                        projectile["stun"] * (0.4 if blocked else 1),
                        280,
                        blocked,
                    )
                    player["energy"] = max(0, player["energy"] - (10 if blocked else 0))
                    self._add_effect(
                        room,
                        "block_spark" if blocked else "projectile_hit",
                        player["x"] + character["width"] / 2 - 22,
                        projectile["y"] - 12,
                        44,
                        44,
                        projectile.get("color", "#38bdf8"),
                        owner["facing"],
                        ttl=0.32,
                        extra={
                            "damage": round(projectile["damage"] * (0.35 if blocked else 1), 1),
                            "blocked": blocked,
                            "attackerSlot": owner["slot"],
                            "defenderSlot": player["slot"],
                            "hitStopMs": 42 if blocked else 76,
                            "shake": 3 if blocked else 7,
                            "flashWhiteMs": 45 if not blocked else 0,
                        },
                    )
                    hit = True
                    break
            if not hit:
                remaining.append(projectile)
        room["projectiles"] = remaining

    def _try_hit(self, room: dict, attacker: dict, defender: dict) -> None:
        if not attacker["attack"] or attacker["attackTimer"] <= 0:
            return
        if now_ms() - attacker["lastHitAt"] > 90:
            return
        attacker_character = CHARACTERS[attacker["characterId"]]
        defender_character = CHARACTERS[defender["characterId"]]
        attack = attacker.get("activeAttack") or attacker_character["attacks"][attacker["attack"]]
        variant = attacker.get("attackVariant") or attacker["attack"]
        defender_width = defender_character["width"]
        ax = attacker["x"] + attacker_character["width"] / 2
        dx = defender["x"] + defender_width / 2
        hit_distance = abs(dx - ax)
        area_attack = bool(attack.get("area"))
        if not area_attack and math.copysign(1, dx - ax) != attacker["facing"]:
            return
        if hit_distance > attack["range"]:
            return
        attacker_mid_y = attacker["y"] + attacker_character["height"] * (0.82 if attack.get("low") else 0.46 if attack.get("launch") else 0.52)
        defender_mid_y = defender["y"] + defender_character["height"] * (0.76 if attack.get("low") else 0.52)
        vertical_reach = max(attacker_character["height"], defender_character["height"]) * (0.5 if attack.get("low") else 0.9 if attack.get("launch") else 0.74)
        if abs(defender_mid_y - attacker_mid_y) > vertical_reach:
            return
        defending_front = defender["facing"] == -attacker["facing"]
        low_guard = attack.get("low") and defender["input"].get("down")
        blocked = defender["blocking"] and defending_front and defender["energy"] >= 8 and (not attack.get("low") or low_guard)
        guard_break = attack.get("guardBreak", 0)
        if blocked and guard_break:
            defender["energy"] = max(0, defender["energy"] - guard_break)
            blocked = defender["energy"] >= 8
        damage = attack["damage"]
        stun = attack["stun"]
        knockback = attack.get("knockback", 360)
        if blocked and defender["characterId"] == "guard":
            defender["bulwarkStacks"] = min(3, defender.get("bulwarkStacks", 0) + 1)
            defender["resourceText"] = "壁垒反蓄"
            defender["resourceTextTimer"] = 0.9
        if attacker["characterId"] == "blade" and not blocked:
            sweet_spot = attack["range"] * 0.58
            if hit_distance >= sweet_spot:
                attacker["windStacks"] = min(3, attacker.get("windStacks", 0) + 1)
                damage += 2
                attacker["resourceText"] = "风势 +1" if attacker["windStacks"] < 3 else "风势已满"
                attacker["resourceTextTimer"] = 0.9
                self._add_effect(room, "wind_gain", defender["x"] + defender_width / 2 - 30, defender["y"] + 22, 60, 48, attacker_character["color"], attacker["facing"], ttl=0.42)
            if attack.get("windRelease"):
                stun += 0.06
                knockback += 90
        if attacker["characterId"] == "fist" and attacker["attack"] == "light" and not blocked:
            attacker["comboStep"] = min(3, attacker.get("comboStep", 0) + 1)
            attacker["comboTimer"] = 0.7
            damage += attacker["comboStep"] * 1.6
            close_hit = hit_distance <= max(72, attack["range"] * 0.82)
            attacker["fury"] = min(100, attacker.get("fury", 0) + (15 if close_hit else 9))
            attacker["resourceText"] = "怒气上升" if attacker["fury"] < 60 else "怒气可爆发"
            attacker["resourceTextTimer"] = 0.8
            if attacker.get("fury", 0) >= 60:
                damage += 2
            if attacker["comboStep"] >= 3:
                stun += 0.08
                knockback += 130
                attacker["fury"] = min(100, attacker.get("fury", 0) + 10)
                attacker["comboName"] = "赤拳 三连终击"
                attacker["comboTextTimer"] = 0.9
        elif attacker["characterId"] == "fist" and not blocked:
            attacker["fury"] = min(100, attacker.get("fury", 0) + (18 if attacker["attack"] == "heavy" else 12))
            if attack.get("furySpend"):
                stun += 0.06
        if attacker["characterId"] == "shade":
            behind = defender["facing"] == attacker["facing"]
            if behind and not blocked:
                damage *= 1.34
                stun += 0.06
                attacker["shadowStacks"] = min(3, attacker.get("shadowStacks", 0) + 1)
                attacker["resourceText"] = "影印 +1" if attacker["shadowStacks"] < 3 else "影印已满"
                attacker["resourceTextTimer"] = 0.9
            if attacker["attack"] == "heavy" and not blocked:
                defender["shadowMark"] = max(defender.get("shadowMark", 0), attack.get("mark", 1.5))
                attacker["shadowStacks"] = min(3, attacker.get("shadowStacks", 0) + 1)
            if attacker["attack"] == "special" and defender.get("shadowMark", 0) > 0 and not blocked:
                damage += 7
                stun += 0.08
                defender["shadowMark"] = 0
                attacker["shadowStacks"] = min(3, attacker.get("shadowStacks", 0) + 1)
            if attack.get("shadowExecute"):
                damage += 4
                defender["vy"] = min(defender.get("vy", 0), -360)
        if attacker["characterId"] == "guard" and not blocked:
            if attack.get("bulwarkSpend"):
                stun += 0.05 * attack.get("bulwarkSpend", 1)
            elif attacker["attack"] == "light":
                attacker["bulwarkStacks"] = min(3, attacker.get("bulwarkStacks", 0) + 0.35)
        if variant in {"launcher", "air_heavy", "guard_crush"} and attacker.get("comboStep", 0) >= 2 and not blocked:
            damage += COMBO_FINISHER_BONUS
            stun += 0.06
            attacker["comboName"] = f"{self._combo_label(attacker, variant, attacker['attack'])} · 追击"
            attacker["comboTextTimer"] = 1.0
        if blocked:
            damage *= 0.35
            stun *= 0.35
        if blocked:
            defender["energy"] = max(0, defender["energy"] - 8)
            attacker["energy"] = min(100, attacker["energy"] + 4)
        else:
            attacker["energy"] = min(100, attacker["energy"] + 10)
        self._apply_damage(attacker, defender, damage, stun, knockback, blocked)
        if attack.get("launch") and not blocked:
            defender["vy"] = min(defender.get("vy", 0), attack["launch"])
            defender["grounded"] = False
        if attack.get("trip") and not blocked and defender["grounded"]:
            defender["vy"] = min(defender.get("vy", 0), -240)
            defender["stun"] = max(defender["stun"], stun + 0.08)
        if attack.get("slam") and not blocked:
            defender["vy"] = max(defender.get("vy", 0), 520)
        if attack.get("mark") and not blocked:
            defender["shadowMark"] = max(defender.get("shadowMark", 0), attack.get("mark", 1.2))
        effect_type = "block_spark" if blocked else f"{attacker['characterId']}_hit"
        if not blocked and attack.get("windRelease"):
            effect_type = "wind_burst"
        elif not blocked and attack.get("furySpend"):
            effect_type = "fury_burst"
        elif not blocked and attack.get("shadowExecute"):
            effect_type = "shadow_pop"
        elif not blocked and attack.get("bulwarkSpend"):
            effect_type = "bulwark_crash"
        self._add_effect(
            room,
            effect_type,
            defender["x"] + defender_width / 2 - 24,
            defender["y"] + defender_character["height"] * 0.28,
            48,
            48,
            attacker_character["color"],
            attacker["facing"],
            ttl=0.36,
            extra={
                "damage": round(damage, 1),
                "blocked": blocked,
                "attackerSlot": attacker["slot"],
                "defenderSlot": defender["slot"],
                "comboStep": attacker.get("comboStep", 0),
                "hitStopMs": 44 if blocked else (112 if attacker["attack"] == "special" else 92 if attacker["attack"] == "heavy" or variant in {"guard_crush", "air_heavy"} else 62),
                "shake": 3 if blocked else (12 if attacker["attack"] == "special" else 9 if attacker["attack"] == "heavy" or variant in {"guard_crush", "air_heavy"} else 5),
                "flashWhiteMs": 0 if blocked else 70,
                "hitLevel": "blocked" if blocked else "heavy" if attacker["attack"] in {"heavy", "special"} or variant in {"guard_crush", "air_heavy"} else "light",
            },
        )
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

