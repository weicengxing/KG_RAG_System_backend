from pathlib import Path

GAME_DATA_DIR = Path(__file__).resolve().parent / "data"
SEASON_HISTORY_PATH = GAME_DATA_DIR / "game_seasons.json"
TRIBE_STATE_PATH = GAME_DATA_DIR / "game_tribes.json"

WEATHER_TYPES = ["sunny", "rain", "snow", "fog"]
DEFAULT_SHORE_RADIUS = 95.0
PLAYER_RADIUS = 0.7
TRIBE_LEADER_VOTE_MIN_MEMBERS = 5
TRIBE_ELDER_VOTE_MIN_MEMBERS = 3
TRIBE_LEADER_CANDIDATE_MIN_CONTRIBUTION = 50
TRIBE_ELDER_CANDIDATE_MIN_CONTRIBUTION = 20
TRIBE_LEADER_VOTE_COOLDOWN_HOURS = 72
TRIBE_ELDER_VOTE_COOLDOWN_HOURS = 24
TRIBE_PUNISH_COOLDOWN_HOURS = 24
TRIBE_PUNISH_CONTRIBUTION_PENALTY = 10
TRIBE_RITUAL_WOOD_COST = 30
TRIBE_RITUAL_STONE_COST = 15
TRIBE_RITUAL_DURATION_MINUTES = 10
TRIBE_RITUAL_GATHER_BONUS = 1
TRIBE_FEAST_FOOD_COST = 18
TRIBE_FEAST_DURATION_MINUTES = 8
TRIBE_FEAST_GATHER_BONUS = 1
TRIBE_FEAST_RENOWN_BONUS = 6
TRIBE_TRADE_MAX_ACTIVE = 5
TRIBE_TRADE_RENOWN_BONUS = 3
TRIBE_FLAG_MAX = 4
TRIBE_FLAG_WOOD_COST = 8
TRIBE_FLAG_STONE_COST = 4
TRIBE_FLAG_PATROL_COOLDOWN_SECONDS = 300
TRIBE_FLAG_PATROL_CHAIN_TARGET = 2
TRIBE_FLAG_BOUNDARY_TENSION_DISTANCE = 28
TRIBE_FLAG_BOUNDARY_NEAR_DISTANCE = 52
TRIBE_BOUNDARY_ACTION_COOLDOWN_SECONDS = 300
TRIBE_BOUNDARY_RELATION_STAGE_STEP = 6
TRIBE_BOUNDARY_OUTCOME_LIMIT = 4
TRIBE_BOUNDARY_PRESSURE_MINUTES = 12
TRIBE_OATH_TASK_STREAK_TARGET = 3
TRIBE_SCOUT_FOOD_COST = 4
TRIBE_SCOUT_EVENT_COUNT = 2
TRIBE_SCOUT_SITE_LIMIT = 4
TRIBE_SCOUT_SITE_ACTIVE_MINUTES = 15
TRIBE_SCOUT_SITE_INTERACT_DISTANCE = 6
TRIBE_SCOUT_SITE_FLAG_RADIUS = 34
TRIBE_SCOUT_SITE_CONTEST_RADIUS = 42
TRIBE_CONTROLLED_SITE_LIMIT = 3
TRIBE_CONTROLLED_SITE_ACTIVE_MINUTES = 20
TRIBE_CONTROLLED_SITE_YIELD_COOLDOWN_SECONDS = 300
TRIBE_ORAL_EPIC_RENOWN_BONUS = 7
TRIBE_ORAL_EPIC_MIN_HISTORY = 3
TRIBE_OATH_RENOWN_BONUS = 5
TRIBE_SCOUT_SITE_REWARDS = {
    "region_forest": {"wood": 12, "renown": 2, "label": "林缘木料点"},
    "region_mountain": {"stone": 12, "renown": 2, "label": "山脚石料点"},
    "region_coast": {"food": 12, "renown": 2, "label": "潮岸食物点"},
    "region_ruin": {"discoveryProgress": 2, "renown": 3, "label": "旧迹线索点"}
}
TRIBE_OATHS = {
    "hearth": {"label": "守火誓约", "summary": "优先保护食物、营火和新成员。"},
    "trail": {"label": "远行誓约", "summary": "优先探索洞穴、季节目标和远方事件。"},
    "trade": {"label": "互市誓约", "summary": "优先贸易、集市和跨部落信誉。"},
    "beast": {"label": "兽伴誓约", "summary": "优先驯养幼兽和营地守护。"}
}
TRIBE_OATH_TASK_REWARDS = {
    "hearth": {"title": "守火补粮", "summary": "围绕营火整理食物与柴草。", "food": 10, "renown": 3},
    "trail": {"title": "远行踏勘", "summary": "派人记录洞穴和远方路线。", "discoveryProgress": 1, "renown": 4},
    "trade": {"title": "互市邀约", "summary": "整理可交换物资并向外释放善意。", "tradeReputation": 1, "renown": 4},
    "beast": {"title": "兽伴训练", "summary": "训练幼兽熟悉营地号令。", "beastExperience": 1, "food": 4, "renown": 3}
}
TRIBE_OATH_TASK_VARIANTS = {
    "hearth": [
        {"key": "food_pressure", "title": "守火补粮", "summary": "部落食物紧张，先稳住火堆旁的储粮。", "food": 12, "renown": 3, "sourceLabel": "食物紧张"},
        {"key": "tide_harvest", "title": "潮汐补给", "summary": "趁资源潮汐还在，尽快把能吃的都带回营地。", "food": 10, "renown": 4, "sourceLabel": "资源潮汐"},
        {"key": "camp_stock", "title": "营地备柴", "summary": "给营火和棚屋补一轮木柴，让营地撑过接下来的天气。", "wood": 6, "food": 6, "renown": 3, "sourceLabel": "营地补给"}
    ],
    "trail": [
        {"key": "season_objective", "title": "远行踏勘", "summary": "季节目标已经出现，先去确认路线和附近地形。", "discoveryProgress": 2, "renown": 4, "sourceLabel": "季节目标"},
        {"key": "world_event", "title": "异象追踪", "summary": "远方世界事件正在发酵，需要有人记录并带回线索。", "discoveryProgress": 2, "renown": 5, "sourceLabel": "世界事件"},
        {"key": "cave_route", "title": "洞口记路", "summary": "给洞穴远征队补充路线标记，为下一次深入做准备。", "discoveryProgress": 1, "renown": 4, "food": 4, "sourceLabel": "洞穴远征"}
    ],
    "trade": [
        {"key": "open_trade", "title": "互市应答", "summary": "现有贸易请求需要尽快回应，别让边界商路冷下去。", "tradeReputation": 2, "renown": 4, "sourceLabel": "贸易请求"},
        {"key": "border_trade", "title": "边界试探", "summary": "趁边界气氛还算稳定，先送出一批轻便信物试探往来。", "tradeReputation": 2, "renown": 4, "food": 4, "sourceLabel": "边界关系"},
        {"key": "gift_pack", "title": "互市备礼", "summary": "整理仓库里适合交换的轻货，为下一次部落贸易做准备。", "tradeReputation": 1, "renown": 4, "wood": 4, "stone": 2, "sourceLabel": "仓库整备"}
    ],
    "beast": [
        {"key": "tame_young", "title": "寻幼兽踪迹", "summary": "部落还没有稳定兽伴，先循着营地周边的痕迹试着驯养。", "tamedBeasts": 1, "renown": 4, "sourceLabel": "尚无兽伴"},
        {"key": "border_guard", "title": "兽伴守边", "summary": "边界紧张起来了，让兽伴先熟悉守边号令。", "beastExperience": 2, "renown": 4, "food": 4, "sourceLabel": "边界警戒"},
        {"key": "beast_haul", "title": "兽伴驮运", "summary": "资源点活跃时让兽伴跟着搬运，顺便练熟营地路线。", "beastExperience": 1, "food": 6, "renown": 3, "sourceLabel": "资源潮汐"}
    ]
}
TRIBE_BOUNDARY_ACTIONS = {
    "greet": {"label": "示好", "summary": "向边界另一侧留下善意标记。", "renown": 3, "tradeReputation": 1, "relationDelta": 2, "tradeTrustDelta": 1},
    "guard": {"label": "警戒", "summary": "加强边界巡逻，提醒成员保持警惕，并清理本部落遭遇的边界压力。", "renown": 5, "relationDelta": -2, "clearIncomingPressure": True},
    "gift": {"label": "交换信物", "summary": "消耗少量食物换取跨部落信任。", "foodCost": 3, "renown": 2, "tradeReputation": 2, "relationDelta": 3, "tradeTrustDelta": 2},
    "press": {"label": "边界压制", "summary": "在紧张边界集结巡逻，短时间压迫对方营地行动。", "renown": 4, "relationDelta": -3, "allowedStates": ["tension", "hostile"], "pressure": True},
    "blockade": {"label": "资源封锁", "summary": "封住边界小路，扰乱对方的物资往来。", "renown": 4, "relationDelta": -4, "allowedStates": ["tension", "hostile"], "pressure": True, "tradeDisrupt": 1},
    "drive_away": {"label": "边界驱离", "summary": "把对方留下的巡路标记驱出边界，压低对方声望但让关系更快恶化。", "renown": 6, "relationDelta": -5, "allowedStates": ["hostile"], "pressure": True, "renownDisrupt": 2, "clearIncomingPressure": True}
}
TRIBE_BOUNDARY_OUTCOME_TEMPLATES = {
    "alliance": {
        "title": "边界互访",
        "summary": "边界守望者交换巡路见闻，营地之间形成更稳的互信。",
        "renown": 5,
        "discoveryProgress": 1,
        "food": 6
    },
    "trade": {
        "title": "贸易试探",
        "summary": "边界两侧先交换一批轻便物资，试探后续通路是否稳定。",
        "renown": 4,
        "tradeReputation": 2,
        "food": 4
    },
    "hostile": {
        "title": "边境纠纷",
        "summary": "边界巡逻升级成正面驱离，营地开始囤积守边物资。",
        "renown": 6,
        "wood": 6,
        "stone": 4
    }
}
TRIBE_BEAST_LEVEL_STEP = 3
TRIBE_BEAST_SPECIALTY_LEVEL = 3
TRIBE_BEAST_SPECIALTIES = {
    "guardian": {"label": "守卫", "taskKey": "guard", "summary": "守营任务额外获得声望。", "renownBonus": 3},
    "hunter": {"label": "猎伴", "taskKey": "hunt", "summary": "助猎任务额外带回食物。", "foodBonus": 6},
    "carrier": {"label": "驮兽", "taskKey": "haul", "summary": "驮运任务额外搬回木材和石块。", "woodBonus": 4, "stoneBonus": 4}
}
TRIBE_BEAST_TASK_REWARDS = {
    "guard": {"label": "守营", "renown": 4, "summary": "驯养幼兽守在营地边缘，提升部落威慑。"},
    "hunt": {"label": "助猎", "food": 10, "summary": "驯养幼兽协助追踪小型猎物，带回食物。"},
    "haul": {"label": "驮运", "wood": 6, "stone": 6, "summary": "驯养幼兽帮助搬运散落物资。"}
}
TRIBE_BEAST_TASK_FEEDBACK_SECONDS = 90
TRIBE_HERD_ACTIONS = {
    "drive": {"label": "驱赶", "foodMultiplier": 0.65, "renownBonus": 5, "summary": "驱赶兽群保护领地，声望更高。"},
    "hunt": {"label": "追猎", "foodMultiplier": 1.45, "renownBonus": 0, "summary": "追猎兽群换取更多食物。"},
    "tame": {"label": "驯养", "foodMultiplier": 0.85, "renownBonus": 2, "tamedBeasts": 1, "summary": "尝试驯养幼兽，留下长期记录。"}
}
TRIBE_CAVE_FOOD_COST = 6
TRIBE_CAVE_LOW_FOOD_FINDS_MULTIPLIER = 0.5
TRIBE_CAVE_ROUTE_PLANS = {
    "steady": {"label": "稳健路线", "foodCost": 5, "findsMultiplier": 0.9, "findsBonus": 0, "discoveryDepth": 5},
    "deep": {"label": "深入路线", "foodCost": 7, "findsMultiplier": 1.12, "findsBonus": 1, "discoveryDepth": 4},
    "risky": {"label": "冒险路线", "foodCost": 9, "findsMultiplier": 1.3, "findsBonus": 2, "discoveryDepth": 3}
}
TRIBE_FOOD_SAFE_BASE = 24
TRIBE_FOOD_SAFE_STORAGE_BONUS = 36
TRIBE_FOOD_DECAY_INTERVAL_MINUTES = 10
TRIBE_FOOD_DECAY_PERCENT = 0.08
TRIBE_FOOD_DECAY_MAX_PER_INTERVAL = 6
WORLD_RUMOR_LIMIT = 12
TRIBE_HISTORY_PREVIEW_LIMIT = 8
TRIBE_HISTORY_PAGE_SIZE = 8
TRIBE_RENOWN_LEVELS = [
    {"level": 1, "title": "无名营火", "min": 0, "next": 20, "badge": "新生部落"},
    {"level": 2, "title": "林地名声", "min": 20, "next": 50, "badge": "附近可闻"},
    {"level": 3, "title": "山海盟声", "min": 50, "next": 100, "badge": "远行者传颂"},
    {"level": 4, "title": "旧石传奇", "min": 100, "next": None, "badge": "世界记忆"}
]
RESOURCE_TIDE_DURATION_MINUTES = 8
RESOURCE_TIDE_GATHER_BONUS = 1
MIGRATION_SEASON_DURATION_MINUTES = 18
MIGRATION_SEASON_TIDE_BONUS = 1
MIGRATION_SEASON_HERD_WEIGHT = 4
WORLD_EVENT_DURATION_MINUTES = 7
WORLD_EVENT_RARE_RUIN_DURATION_MINUTES = 10
WORLD_EVENT_RUIN_CHAIN_THRESHOLD = 3
SEASON_OBJECTIVE_DURATION_MINUTES = 12
SEASON_CHAIN_TARGET = 3
SEASON_CELEBRATION_RENOWN_BONUS = 14
SEASON_CELEBRATION_FOOD_BONUS = 12
SEASON_CELEBRATION_CHOICES = {
    "feast": {"label": "宴饮", "summary": "把庆典办成共享食物的长席。", "food": 24, "renown": 6, "buff": {"type": "feast", "title": "宴饮余韵", "gatherBonus": 1}},
    "ritual": {"label": "祭祀", "summary": "把庆典献给图腾与旧日记忆。", "renown": 18, "discoveryProgress": 1, "buff": {"type": "ritual", "title": "祭祀余韵", "discoveryBonus": 1}},
    "market": {"label": "集市", "summary": "把庆典变成跨部落交换日。", "wood": 14, "stone": 14, "tradeReputation": 1, "renown": 8, "buff": {"type": "market", "title": "集市余韵", "tradeRenownBonus": 2}}
}
SEASON_CELEBRATION_BUFF_MINUTES = 10
SEASON_OBJECTIVES = {
    "region_forest": {"title": "林地采种", "summary": "采集迁徙季节留下的坚果与嫩枝。", "food": 8, "wood": 10, "renown": 4},
    "region_mountain": {"title": "山地试炼", "summary": "沿山脊寻找新露出的石脉。", "stone": 16, "renown": 5},
    "region_coast": {"title": "海岸拾潮", "summary": "趁退潮收集贝壳、漂木与鱼获。", "food": 10, "wood": 6, "renown": 4},
    "region_ruin": {"title": "遗迹听风", "summary": "在遗迹风声里记录新的旧日片段。", "discoveryProgress": 1, "renown": 8}
}
WORLD_EVENT_REWARDS = {
    "herd": {"wood": 8, "stone": 0, "food": 18, "discoveryProgress": 0, "renown": 4},
    "storm": {"wood": -10, "stone": 6, "food": 0, "discoveryProgress": 0, "renown": 6},
    "ruin_clue": {"wood": 0, "stone": 10, "food": 0, "discoveryProgress": 1, "renown": 8},
    "rare_ruin": {"wood": 0, "stone": 28, "food": 8, "discoveryProgress": 3, "renown": 24}
}
WORLD_EVENT_LIBRARY = [
    {"key": "herd", "title": "兽群经过", "summary": "兽群穿过林地，处理后可为部落带回食物和少量木材。"},
    {"key": "storm", "title": "暴雨将至", "summary": "暴雨压低视野，处理后会消耗护火木材并带回冲刷出的石块。"},
    {"key": "ruin_clue", "title": "遗迹线索", "summary": "遗迹附近出现新刻痕，处理后可推进稀有发现并带回石材。"}
]
RARE_WORLD_EVENT_LIBRARY = {
    "rare_ruin": {"key": "rare_ruin", "title": "稀有遗迹显现", "summary": "连续记录的刻痕拼出一处短暂显现的古遗迹，处理后可获得大量声望和发现进度。"}
}
TRIBE_CAMP_SLOTS = [
    {"x": 32.0, "z": 14.0, "angle": 0.15, "label": "东岸营地"},
    {"x": -30.0, "z": 20.0, "angle": -0.2, "label": "西岭营地"},
    {"x": 24.0, "z": -34.0, "angle": 0.8, "label": "南岸营地"},
    {"x": -22.0, "z": -32.0, "angle": -0.75, "label": "潮汐营地"},
    {"x": 4.0, "z": 42.0, "angle": 0.0, "label": "北境营地"},
    {"x": -4.0, "z": -48.0, "angle": 3.141592653589793, "label": "海岬营地"},
]
TRIBE_CAMP_BUILDING_LAYOUT = [
    {"key": "totem", "type": "tribe_totem", "dx": 0.0, "dz": 0.0, "size": 1.15, "initial": True},
    {"key": "campfire", "type": "campfire", "dx": 1.5, "dz": -4.8, "size": 1.0, "wood": 20, "stone": 10, "label": "营火"},
    {"key": "storage", "type": "tribe_storage", "dx": -4.6, "dz": -1.2, "size": 1.0, "wood": 45, "stone": 20, "label": "仓库"},
    {"key": "workbench", "type": "tribe_workbench", "dx": 4.2, "dz": 1.8, "size": 1.0, "wood": 70, "stone": 45, "label": "石器台"},
    {"key": "hut_a", "type": "tribe_hut", "dx": -5.8, "dz": 4.2, "size": 1.0, "wood": 35, "stone": 15, "label": "棚屋一"},
    {"key": "hut_b", "type": "tribe_hut", "dx": 6.2, "dz": 4.5, "size": 0.95, "wood": 35, "stone": 15, "label": "棚屋二"},
    {"key": "fence_ring", "type": "tribe_fence", "dx": 0.0, "dz": 8.2, "size": 1.0, "wood": 48, "stone": 12, "label": "营地围栏"},
    {"key": "road_marker", "type": "tribe_road", "dx": 0.0, "dz": -9.2, "size": 1.0, "wood": 24, "stone": 18, "label": "营地道路"},
]
TRIBE_TARGET_LIBRARY = [
    {
        "title": "点燃第一处营火",
        "wood": 20,
        "stone": 10,
        "summary": "先建立最基本的营地生活区。"
    },
    {
        "title": "搭起稳定仓库",
        "wood": 45,
        "stone": 20,
        "summary": "让公共仓库真正承担物资中转。"
    },
    {
        "title": "扩建石器台",
        "wood": 70,
        "stone": 45,
        "summary": "为更复杂的建造和探索做准备。"
    },
    {
        "title": "筹备第一次洞穴远征",
        "wood": 100,
        "stone": 70,
        "summary": "当营地稳定后，开始向山洞推进。"
    }
]
TRIBE_RUNE_LIBRARY = [
    {
        "key": "hearth",
        "title": "火种铭文",
        "summary": "部落建成营火，并完成第一次共同仪式?",
        "requires": {"building": "campfire", "rituals": 1},
        "effectSummary": "丰收篝火持续时间 +2 分钟。",
        "effects": {"ritualDurationBonusMinutes": 2}
    },
    {
        "key": "storehouse",
        "title": "丰仓铭文",
        "summary": "公共仓库累计贡献达到 150?象征稳定供给?",
        "requires": {"contribution": 150},
        "effectSummary": "营地建筑木材和石块消耗降低 10%。",
        "effects": {"buildCostDiscountPercent": 10}
    },
    {
        "key": "stonecraft",
        "title": "石工铭文",
        "summary": "部落建成石器台和至少三座营地建筑?",
        "requires": {"building": "workbench", "buildings": 3},
        "effectSummary": "营地建筑石块消耗额外降低 10%。",
        "effects": {"stoneBuildCostDiscountPercent": 10}
    },
    {
        "key": "circle",
        "title": "众声铭文",
        "summary": "部落达到 5 名成员，形成真正的议事圈?",
        "requires": {"members": 5},
        "effectSummary": "丰收篝火采集收益额外 +1。",
        "effects": {"ritualGatherBonus": 1}
    }
]
RARE_TRIBE_RUNE_LIBRARY = [
    {
        "key": "deep_cave_echo",
        "title": "幽洞回声铭文",
        "summary": "需要洞穴远征发现古老回声后才能刻写。",
        "effectSummary": "洞穴远征最终收获额外 +1。",
        "requires": {"discovery": "deep_cave_echo"},
        "effects": {"caveFindsBonus": 1},
        "rare": True
    },
    {
        "key": "rare_ruin_memory",
        "title": "古遗迹记忆铭文",
        "summary": "需要处理稀有遗迹显现并完整记录古老记忆后才能刻写。",
        "effectSummary": "洞穴远征最终收获额外 +2，叠加幽洞回声铭文。",
        "requires": {"discovery": "rare_ruin_memory"},
        "effects": {"caveFindsBonus": 2},
        "rare": True
    }
]

WORLD_REGIONS = [
    {
        "id": "region_forest_0",
        "type": "region_forest",
        "label": "鹿鸣森林",
        "x": -56,
        "z": -6,
        "radius": 24,
        "summary": "木材、草和果实更多，适合部落早期补给。"
    },
    {
        "id": "region_mountain_0",
        "type": "region_mountain",
        "label": "熊骨山地",
        "x": -72,
        "z": 62,
        "radius": 28,
        "summary": "石头、矿物和洞穴入口集中在这里。"
    },
    {
        "id": "region_coast_0",
        "type": "region_coast",
        "label": "潮声海岸",
        "x": 34,
        "z": -58,
        "radius": 22,
        "summary": "后续可扩展鱼、贝壳和水源。"
    },
    {
        "id": "region_ruin_0",
        "type": "region_ruin",
        "label": "旧石遗迹带",
        "x": -38,
        "z": 24,
        "radius": 18,
        "summary": "适合承载稀有物品、剧情和部落记忆。"
    }
]

# 玩家连接管理
