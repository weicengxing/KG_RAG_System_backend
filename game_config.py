from pathlib import Path

GAME_DATA_DIR = Path(__file__).resolve().parent / "data"
SEASON_HISTORY_PATH = GAME_DATA_DIR / "game_seasons.json"
TRIBE_STATE_PATH = GAME_DATA_DIR / "game_tribes.json"

WEATHER_TYPES = ["sunny", "rain", "snow", "fog"]
DEFAULT_SHORE_RADIUS = 95.0
PLAYER_RADIUS = 0.7
PLAYER_CONFLICT_DISTANCE = 4.5
PLAYER_CONFLICT_COOLDOWN_SECONDS = 45
PLAYER_CONFLICT_FATIGUE_MAX = 6
PLAYER_CONFLICT_FATIGUE_DECAY_SECONDS = 180
PLAYER_CONFLICT_GUARD_SECONDS = 60
PLAYER_CONFLICT_GUARD_RADIUS = 6
PLAYER_CONFLICT_SPARRING_RENOWN = 1
PLAYER_CONFLICT_INSPIRE_MIN_RENOWN = 5
PLAYER_CONFLICT_INSPIRE_SECONDS = 180
PLAYER_CONFLICT_INSPIRE_CONTRIBUTION = 1
PLAYER_RENOWN_TITLES = [
    {"min": 12, "title": "守边名手", "summary": "在守边和集结中更容易带动同伴。", "guardRadiusBonus": 3, "sparTrainingBonus": 1, "fatigueRecoveryBonusSeconds": 90, "skirmishContributionBonus": 1},
    {"min": 7, "title": "营火勇名", "summary": "附近成员愿意听从他的短促号令。", "guardRadiusBonus": 2, "sparTrainingBonus": 1, "fatigueRecoveryBonusSeconds": 60, "skirmishContributionBonus": 1},
    {"min": 3, "title": "初露锋芒", "summary": "个人冲突记录开始被部落记住。", "guardRadiusBonus": 1, "sparTrainingBonus": 0, "fatigueRecoveryBonusSeconds": 30, "skirmishContributionBonus": 0},
    {"min": 0, "title": "无名成员", "summary": "还没有稳定的个人名声。", "guardRadiusBonus": 0, "sparTrainingBonus": 0, "fatigueRecoveryBonusSeconds": 0, "skirmishContributionBonus": 0}
]
PLAYER_IDENTITY_MIN_RENOWN = 3
PLAYER_IDENTITY_ACTION_COOLDOWN_SECONDS = 300
PLAYER_IDENTITY_OPTIONS = {
    "fire_dancer": {
        "label": "火舞者",
        "actionLabel": "火舞鼓舞",
        "summary": "用火舞提振营地气势，带来少量部落声望和个人声望。",
        "renown": 2,
        "personalRenown": 1
    },
    "pathfinder": {
        "label": "寻路者",
        "actionLabel": "标记捷径",
        "summary": "记录一条短路，让探索线索更快汇入部落记忆。",
        "discoveryProgress": 1,
        "renown": 1
    },
    "mason": {
        "label": "石匠",
        "actionLabel": "整修石器",
        "summary": "整理石木工具，略微降低一个战后修复或复兴任务的消耗。",
        "wood": 2,
        "stone": 2,
        "taskDiscount": 1,
        "renown": 1
    },
    "storyteller": {
        "label": "讲述者",
        "actionLabel": "复述旧事",
        "summary": "把最近的部落历史讲给营火旁的人听，强化历史回放奖励。",
        "renown": 3,
        "personalRenown": 1,
        "requiresHistory": 1
    }
}
PLAYER_CONFLICT_ACTIONS = {
    "intimidate": {"label": "威慑", "summary": "靠近对方发出警告，提升个人声望并轻微影响部落关系。", "renown": 1, "fatigue": 1, "relationDelta": -1},
    "challenge": {"label": "挑战", "summary": "进行一次短促的近身冲突，胜负只造成疲劳和击退，不造成死亡。", "renown": 2, "fatigue": 2, "relationDelta": -2, "knockback": 2.4},
    "spar": {"label": "切磋", "summary": "同部落成员之间的练习冲突，只留下少量疲劳和个人声望。", "renown": 1, "fatigue": 1, "sameTribeOnly": True, "relationDelta": 0, "knockback": 1.0, "trainingRenown": PLAYER_CONFLICT_SPARRING_RENOWN},
    "inspire": {"label": "鼓舞", "summary": "高个人声望成员可鼓舞附近同部落成员，使其下一次小规模集结贡献提高。", "sameTribeOnly": True, "inspire": True},
    "guard": {"label": "守势", "summary": "对靠近的目标摆出防备姿态，短时间内降低下一次个人冲突造成的疲劳，也能保护附近同部落成员。", "guard": True}
}
TRIBE_SKIRMISH_ACTIVE_MINUTES = 8
TRIBE_SKIRMISH_SCORE_TARGET = 4
TRIBE_SKIRMISH_RENOWN_REWARD = 6
TRIBE_SKIRMISH_FOOD_REWARD = 6
TRIBE_SKIRMISH_LIMIT = 3
TRIBE_SKIRMISH_JOIN_DISTANCE = 12
TRIBE_SKIRMISH_ROAD_TRADE_REWARD = 2
TRIBE_SKIRMISH_FLAG_RENOWN_REWARD = 3
TRIBE_SKIRMISH_CAVE_RADIUS = 170
TRIBE_SKIRMISH_CAVE_DISCOVERY_REWARD = 2
TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD = 3
TRIBE_WAR_WOOD_COST = 12
TRIBE_WAR_STONE_COST = 8
TRIBE_WAR_FOOD_COST = 10
TRIBE_WAR_SCORE_TARGET = 6
TRIBE_WAR_RENOWN_REWARD = 10
TRIBE_WAR_REPARATION_FOOD = 6
TRIBE_WAR_TRUCE_FOOD_COST = 6
TRIBE_WAR_REPAIR_WOOD_COST = 6
TRIBE_WAR_REPAIR_STONE_COST = 4
TRIBE_WAR_REPAIR_RENOWN = 3
TRIBE_WAR_FATIGUE_WINNER = 1
TRIBE_WAR_FATIGUE_LOSER = 2
TRIBE_WAR_FATIGUE_SECONDS = 900
TRIBE_WAR_REVIVAL_FOOD_COST = 8
TRIBE_WAR_REVIVAL_WOOD_COST = 4
TRIBE_WAR_REVIVAL_RENOWN = 4
TRIBE_WAR_REVIVAL_FATIGUE_RELIEF = 2
TRIBE_WAR_REVIVAL_BRANCH_FOOD_REWARD = 6
TRIBE_WAR_REVIVAL_BRANCH_TRADE_REWARD = 2
TRIBE_WAR_REVIVAL_BRANCH_OATH_RENOWN = 5
TRIBE_WAR_REVIVAL_BRANCH_PRESSURE = 1
TRIBE_WAR_REVIVAL_STORAGE_FOOD_BONUS = 4
TRIBE_WAR_REVIVAL_ROAD_TRADE_BONUS = 1
TRIBE_WAR_REVIVAL_FLAG_RENOWN_BONUS = 2
TRIBE_WAR_REVIVAL_FENCE_FATIGUE_BONUS = 1
TRIBE_WAR_SUPPORT_FOOD_COST = 5
TRIBE_WAR_SUPPORT_SCORE = 2
TRIBE_WAR_SUPPORT_RENOWN = 2
TRIBE_WAR_BETRAYAL_RENOWN = 3
TRIBE_WAR_BETRAYAL_PRESSURE = 1
TRIBE_WAR_ALLY_SUPPLY_FOOD_COST = 4
TRIBE_WAR_ALLY_SUPPLY_RENOWN = 3
TRIBE_WAR_ALLY_SUPPLY_TRADE = 1
TRIBE_WAR_ALLY_RECEPTION_FOOD = 5
TRIBE_WAR_ALLY_RECEPTION_RENOWN = 2
TRIBE_WAR_ALLY_GRIEVANCE_RENOWN = 3
TRIBE_WAR_ALLY_GRIEVANCE_PRESSURE = 1
TRIBE_WAR_ALLY_REPARATION_FOOD_COST = 5
TRIBE_WAR_ALLY_REPARATION_RENOWN = 2
TRIBE_WAR_ALLY_REPARATION_PRESSURE_RELIEF = 1
TRIBE_WAR_MEDIATION_FOOD_COST = 6
TRIBE_WAR_MEDIATION_SCORE_REDUCTION = 1
TRIBE_WAR_MEDIATION_RENOWN = 3
TRIBE_WAR_DIPLOMACY_FOOD_COST = 4
TRIBE_WAR_DIPLOMACY_RENOWN = 3
TRIBE_WAR_GRIEVANCE_RENOWN = 2
TRIBE_WAR_AFTERMATH_FOOD_COST = 3
TRIBE_WAR_AFTERMATH_FOOD_REWARD = 6
TRIBE_WAR_AFTERMATH_TRADE_REWARD = 2
TRIBE_WAR_AFTERMATH_PRESSURE_RELIEF = 1
TRIBE_WAR_AFTERMATH_RENOWN = 3
TRIBE_WAR_GOALS = {
    "resource_site": {
        "label": "粮草争夺",
        "summary": "围绕资源点爆发的正式战争，胜方额外取得粮草与仓储收益。",
        "rewardText": "胜方额外获得粮草",
        "foodReward": 8,
        "renownReward": 2
    },
    "boundary_flag": {
        "label": "边旗压制",
        "summary": "围绕边界旗帜爆发的正式战争，胜方额外取得部落声望。",
        "rewardText": "胜方边旗声望上升",
        "renownReward": 5
    },
    "boundary_road": {
        "label": "通路控制",
        "summary": "围绕营地道路爆发的正式战争，胜方额外取得贸易信誉。",
        "rewardText": "胜方通路与贸易信誉上升",
        "tradeReward": 4,
        "renownReward": 2
    },
    "cave_entrance": {
        "label": "洞口远征权",
        "summary": "围绕洞口爆发的正式战争，胜方额外取得发现进度。",
        "rewardText": "胜方洞口发现进度上升",
        "discoveryReward": 4,
        "renownReward": 2
    },
    "border_front": {
        "label": "边境战线",
        "summary": "围绕长期敌意边境爆发的正式战争，胜方获得稳定声望。",
        "rewardText": "胜方稳定边境声望",
        "renownReward": 3
    }
}
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
TRIBE_BOUNDARY_TRUCE_MINUTES = 10
TRIBE_BOUNDARY_HOSTILE_FOOD_COST = 2
TRIBE_BOUNDARY_FOLLOWUP_LIMIT = 6
TRIBE_BOUNDARY_PRESSURE_AFTERMATH_RENOWN = 3
TRIBE_BOUNDARY_PRESSURE_AFTERMATH_WOOD_COST = 2
TRIBE_BOUNDARY_TRUCE_TALK_FOOD_REWARD = 5
TRIBE_BOUNDARY_TRUCE_TALK_TRADE_REWARD = 1
TRIBE_BOUNDARY_HOSTILE_WEAR_FOOD_LOSS = 2
TRIBE_BOUNDARY_HOSTILE_WEAR_WOOD_LOSS = 2
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
TRIBE_CONTROLLED_SITE_UPGRADE_COLLECTS = 2
TRIBE_CONTROLLED_SITE_MAX_LEVEL = 3
TRIBE_CONTROLLED_SITE_UPGRADE_EXTEND_MINUTES = 8
TRIBE_CONTROLLED_SITE_PATROL_COOLDOWN_SECONDS = 240
TRIBE_CONTROLLED_SITE_PATROL_EXTEND_MINUTES = 5
TRIBE_CONTROLLED_SITE_RELAY_COOLDOWN_SECONDS = 300
TRIBE_CONTROLLED_SITE_RELAY_EXTEND_MINUTES = 4
TRIBE_TRADE_ROUTE_SITE_LIMIT = 3
TRIBE_TRADE_ROUTE_SITE_ACTIVE_MINUTES = 18
TRIBE_TRADE_ROUTE_SITE_COLLECT_COOLDOWN_SECONDS = 360
TRIBE_TRADE_ROUTE_MARKET_COLLECTS = 3
TRIBE_TRADE_ROUTE_MARKET_MINUTES = 10
TRIBE_TRADE_ROUTE_MARKET_RENOWN = 2
TRIBE_TRADE_ROUTE_MARKET_TRADE = 2
TRIBE_TRADE_ROUTE_MARKET_FOOD = 3
TRIBE_MARKET_PACT_MINUTES = 30
TRIBE_MARKET_PACT_LIMIT = 5
TRIBE_MARKET_PACT_CHANCE_BASE = 0.55
TRIBE_MARKET_PACT_TRUST_BONUS = 0.03
TRIBE_MARKET_PACT_RELATION_BONUS = 0.02
TRIBE_MARKET_PACT_TRADE_DISCOUNT = 1
TRIBE_MARKET_PACT_TRADE_REPUTATION_BONUS = 1
TRIBE_MARKET_PACT_JOINT_WATCH_TRADE_TRUST = 1
TRIBE_MARKET_PACT_CONTEST_RELIEF = 1
TRIBE_DIPLOMACY_COUNCIL_SIGNAL_TARGET = 2
TRIBE_DIPLOMACY_COUNCIL_MINUTES = 18
TRIBE_DIPLOMACY_COUNCIL_LIMIT = 3
TRIBE_DIPLOMACY_COUNCIL_ACTIONS = {
    "peace": {
        "label": "停战议和",
        "summary": "把多条停争与互市信号摆到同一处火圈里，公开压低战争压力。",
        "foodCost": 3,
        "renown": 4,
        "relationDelta": 2,
        "tradeTrustDelta": 1,
        "warPressureRelief": 2
    },
    "shared_cave": {
        "label": "共享洞口",
        "summary": "约定共同记录洞口与遗迹线索，各方获得发现进度并提升信任。",
        "foodCost": 2,
        "renown": 3,
        "discoveryProgress": 1,
        "tradeTrustDelta": 2
    },
    "seal_market": {
        "label": "封锁边市",
        "summary": "公开收拢边市信物，暂停不稳定互市，换取声望与边界降温。",
        "foodCost": 1,
        "renown": 5,
        "tradeReputation": 1,
        "relationDelta": -1,
        "tradeTrustDelta": -1,
        "warPressureRelief": 1,
        "closeMarketPacts": True
    }
}
PLAYER_NEWCOMER_KEY_RENOWN_MAX = 2
TRIBE_NEWCOMER_KEY_CONTRIBUTION_MAX = 5
TRIBE_NEWCOMER_KEY_MIN_DONATION = 2
TRIBE_NEWCOMER_KEY_RENOWN = 1
TRIBE_NEWCOMER_KEY_MOMENTS = [
    {
        "key": "first_find",
        "label": "第一发现",
        "summary": "新人把不起眼的石痕认成旧路标，部落发现进度上升。",
        "discoveryProgress": 1
    },
    {
        "key": "child_omen",
        "label": "童言预兆",
        "summary": "新人把路上的风声讲给营火旁的人听，部落声望上升。",
        "renown": 2
    },
    {
        "key": "lost_shortcut",
        "label": "误入捷径",
        "summary": "新人误打误撞走到一条近路，顺手带回额外木石。",
        "wood": 1,
        "stone": 1
    }
]
TRIBE_ORAL_EPIC_RENOWN_BONUS = 7
TRIBE_ORAL_EPIC_MIN_HISTORY = 3
TRIBE_ORAL_CHAIN_LINE_TARGET = 3
TRIBE_ORAL_CHAIN_MAX_LINES = 6
TRIBE_ORAL_CHAIN_LINE_RENOWN = 1
TRIBE_ORAL_CHAIN_COMPLETE_RENOWN = 4
TRIBE_ORAL_CHAIN_KEYWORDS = {
    "hearth": {
        "label": "火种",
        "keywords": ["火", "篝火", "营火", "暖", "灶", "宴"],
        "summary": "接龙里反复提到火与营地，新的传闻更像一段守住家园的火边歌。",
        "runeCandidate": "火种铭文候选",
        "reward": {"renown": 2, "food": 3}
    },
    "cave": {
        "label": "洞穴",
        "keywords": ["洞", "洞穴", "石", "回声", "深处", "遗迹", "旧"],
        "summary": "接龙把旧石、洞穴和回声连在一起，部落更容易把故事指向新发现。",
        "runeCandidate": "幽洞回声候选",
        "reward": {"renown": 1, "discoveryProgress": 2}
    },
    "trade": {
        "label": "互市",
        "keywords": ["贸易", "边市", "交换", "礼", "赠", "商", "路"],
        "summary": "接龙把交换和礼物讲成荣耀，外部部落更愿意听见友好的版本。",
        "runeCandidate": "行路信物候选",
        "reward": {"renown": 1, "tradeReputation": 1}
    },
    "guard": {
        "label": "守边",
        "keywords": ["守", "边", "旗", "战", "巡", "护", "敌"],
        "summary": "接龙把边界压力改写成守望故事，让营地暂时少一些战意翻涌。",
        "runeCandidate": "守边纹候选",
        "reward": {"renown": 2, "warPressureRelief": 1}
    }
}
TRIBE_EMERGENCY_CHOICE_MINUTES = 12
TRIBE_EMERGENCY_CHOICE_LIMIT = 4
TRIBE_EMERGENCY_FOLLOWUP_LIMIT = 5
TRIBE_EMERGENCY_CHOICE_ACTIONS = {
    "rescue": {
        "label": "先救援",
        "summary": "优先处理灾情、兽群或遗迹险情，稳定营地情绪，但争夺一侧会留下余怨。",
        "renown": 3,
        "food": 5,
        "discoveryProgress": 1,
        "abandonedTitle": "争夺余怨",
        "abandonedSummary": "部落选择先救援后，边境争夺没有立刻回应。成员可以补巡边界，避免余怨继续积累。",
        "followup": {"renownReward": 2, "pressureRelief": 1}
    },
    "contest": {
        "label": "先争夺",
        "summary": "优先压住边界或资源点争夺，给成员明确的集结方向，但救援一侧需要事后安抚。",
        "renown": 4,
        "tradeReputation": 1,
        "pressureRelief": 1,
        "abandonedTitle": "救援补救",
        "abandonedSummary": "部落选择先争夺后，救援没有第一时间赶到。成员可以补送食物和人手，把错过的善意补回来。",
        "followup": {"foodCost": 2, "renownReward": 3, "foodReward": 4, "discoveryReward": 1}
    }
}
TRIBE_OATH_RENOWN_BONUS = 5
TRIBE_SCOUT_SITE_REWARDS = {
    "region_forest": {"wood": 12, "renown": 2, "label": "林缘木料点"},
    "region_mountain": {"stone": 12, "renown": 2, "label": "山脚石料点"},
    "region_coast": {"food": 12, "renown": 2, "label": "潮岸食物点"},
    "region_ruin": {"discoveryProgress": 2, "renown": 3, "label": "旧迹线索点"}
}
TRIBE_REGION_BUILDING_BONUSES = {
    "region_forest": {
        "buildingKey": "woodland_rack",
        "label": "林地晾架",
        "secure": {"wood": 4},
        "yield": {"wood": 2},
        "summary": "林地侦察点确认和控制点收取额外带回木材。"
    },
    "region_mountain": {
        "buildingKey": "quarry_pit",
        "label": "山地采石坑",
        "secure": {"stone": 4},
        "yield": {"stone": 2},
        "summary": "山地侦察点确认和控制点收取额外带回石块。"
    },
    "region_coast": {
        "buildingKey": "fish_drying_rack",
        "label": "潮岸晒鱼架",
        "secure": {"food": 4},
        "yield": {"food": 2},
        "summary": "海岸侦察点确认和控制点收取额外带回食物。"
    },
    "region_ruin": {
        "buildingKey": "memory_stone",
        "label": "旧石记忆碑",
        "secure": {"discoveryProgress": 1, "renown": 2},
        "yield": {"discoveryProgress": 1},
        "summary": "遗迹侦察点确认额外获得声望和发现进度，控制点收取额外推进发现。"
    }
}
TRIBE_REGION_EVENT_BONUSES = {
    "woodland_rack": {
        "label": "林地晾架",
        "summary": "长期敌意损耗少掉1点木材，处理风暴/兽群世界事件时额外带回1点木材。",
        "hostileWearWoodRelief": 1,
        "worldEventKeys": ["storm", "herd"],
        "worldEventReward": {"wood": 1}
    },
    "quarry_pit": {
        "label": "山地采石坑",
        "summary": "战后修复少消耗1点石块，处理风暴世界事件时额外带回1点石块。",
        "warRepairStoneDiscount": 1,
        "worldEventKeys": ["storm"],
        "worldEventReward": {"stone": 1}
    },
    "fish_drying_rack": {
        "label": "潮岸晒鱼架",
        "summary": "停争谈判额外回收2点食物，处理兽群世界事件时额外带回2点食物。",
        "truceTalkFoodBonus": 2,
        "worldEventKeys": ["herd"],
        "worldEventReward": {"food": 2}
    },
    "memory_stone": {
        "label": "旧石记忆碑",
        "summary": "遗迹线索和稀有遗迹额外推进发现，并让遗迹余波更值得追。",
        "worldEventKeys": ["ruin_clue", "rare_ruin"],
        "worldEventReward": {"discoveryProgress": 1, "renown": 2}
    }
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
    "truce": {"label": "停争议和", "summary": "在紧张边界摆出停争标记，清理双方短时压力，把冲突拉回可谈判状态。", "foodCost": 4, "renown": 3, "tradeReputation": 1, "relationDelta": 4, "tradeTrustDelta": 1, "allowedStates": ["tension", "hostile"], "clearIncomingPressure": True, "clearOutgoingPressure": True, "truce": True},
    "relief": {"label": "互助补给", "summary": "向边界另一侧送出一批食物，缓和关系并显著提高贸易信任。", "foodCost": 6, "renown": 4, "tradeReputation": 3, "relationDelta": 3, "tradeTrustDelta": 3, "allowedStates": ["trade", "alliance", "tension"], "clearIncomingPressure": True, "aidFood": 4},
    "joint_watch": {"label": "联合守望", "summary": "约定两边旗帜共同观察资源路，降低误判并标出双方都能前往确认的共享资源线索。", "foodCost": 2, "renown": 5, "tradeReputation": 1, "relationDelta": 2, "tradeTrustDelta": 2, "allowedStates": ["neighbor", "trade", "alliance", "tension"], "clearIncomingPressure": True, "clearOutgoingPressure": True, "sharedScout": True},
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
WORLD_EVENT_ACTIONS = {
    "herd": {
        **TRIBE_HERD_ACTIONS,
        "coast_dry_fish": {
            "label": "潮岸晒鱼",
            "summary": "用潮岸晒鱼架快速处理兽群留下的肉获，食物和贸易信誉更高。",
            "requires": {"building": "fish_drying_rack", "regionTypes": ["region_coast"]},
            "reward": {"food": 8, "tradeReputation": 1},
            "remnant": {
                "key": "drying_yard",
                "label": "晒鱼场余迹",
                "summary": "潮风里还留着可整理的鱼干和盐草。",
                "reward": {"food": 5, "tradeReputation": 1, "renown": 1}
            },
            "detail": "潮岸晒鱼架把兽群肉获变成了更耐放的边市食物。"
        }
    },
    "storm": {
        "forest_firebreak": {
            "label": "林地救火",
            "summary": "用林地晾架和防火空地保护护火木材，减少暴雨前后的木材损耗。",
            "requires": {"building": "woodland_rack", "regionTypes": ["region_forest"]},
            "reward": {"wood": 8, "renown": 2},
            "remnant": {
                "key": "firebreak",
                "label": "防火带余迹",
                "summary": "清出的防火带边缘还能收拢焦枝和干木。",
                "reward": {"wood": 6, "renown": 1}
            },
            "detail": "林地晾架和清出的防火空地保住了一批护火木材。"
        },
        "mountain_channel": {
            "label": "山地引渠",
            "summary": "借山地采石坑引开水流，暴雨后带回更多石材。",
            "requires": {"building": "quarry_pit", "regionTypes": ["region_mountain"]},
            "reward": {"stone": 5, "renown": 2},
            "remnant": {
                "key": "water_channel",
                "label": "引水沟余迹",
                "summary": "浅沟里露出被水洗净的石片和少量山泉食材。",
                "reward": {"stone": 5, "food": 3, "renown": 1}
            },
            "detail": "山地采石坑把雨水引入浅沟，冲出了更多可用石料。"
        }
    },
    "ruin_clue": {
        "ruin_rubbing": {
            "label": "遗迹拓印",
            "summary": "用旧石记忆碑校对刻痕拓片，更快拼合稀有遗迹线索。",
            "requires": {"building": "memory_stone", "regionTypes": ["region_ruin"]},
            "reward": {"discoveryProgress": 2, "renown": 3},
            "ruinClueChainBonus": 1,
            "remnant": {
                "key": "rubbing_shard",
                "label": "拓印石片",
                "summary": "石片上还有未整理的刻痕，可补入部落发现记录。",
                "reward": {"stone": 3, "discoveryProgress": 1, "renown": 2}
            },
            "detail": "旧石记忆碑帮助族人拓印刻痕，线索之间的关系清楚了许多。"
        }
    },
    "rare_ruin": {
        "ruin_rubbing": {
            "label": "遗迹拓印",
            "summary": "用旧石记忆碑完整拓下稀有遗迹片段，获得更多发现和声望。",
            "requires": {"building": "memory_stone", "regionTypes": ["region_ruin"]},
            "reward": {"discoveryProgress": 2, "renown": 6},
            "remnant": {
                "key": "rare_rubbing_shard",
                "label": "稀有拓片余迹",
                "summary": "显现后的石面仍残留可再次拓下的古老纹路。",
                "reward": {"stone": 5, "discoveryProgress": 1, "renown": 4}
            },
            "detail": "旧石记忆碑让稀有遗迹的片段被完整拓下，成为部落可反复讲述的记忆。"
        }
    }
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
WORLD_EVENT_REMNANT_ACTIVE_MINUTES = 8
WORLD_EVENT_REMNANT_LIMIT = 6
TRIBE_MAP_MEMORY_ACTIVE_MINUTES = 40
TRIBE_MAP_MEMORY_LIMIT = 8
TRIBE_MAP_MEMORY_REWARDS = {
    "event_trace": {"renown": 1, "discoveryProgress": 1},
    "cave_first": {"renown": 2, "discoveryProgress": 1},
    "war_aftermath": {"renown": 2},
    "border_market": {"tradeReputation": 1, "renown": 1},
    "oral_epic": {"renown": 2}
}
TRIBE_MYTH_CLAIM_ACTIVE_MINUTES = 45
TRIBE_MYTH_CLAIM_LIMIT = 6
TRIBE_DOMINANT_MYTH_LIMIT = 5
TRIBE_MYTH_INFLUENCE_TARGET = 3
TRIBE_MYTH_INTERPRETATIONS = {
    "hearth": {
        "label": "火种护佑",
        "summary": "把这件事解释为营火、食物与部落守护的征兆。",
        "reward": {"food": 4, "renown": 2}
    },
    "trail": {
        "label": "旧路显现",
        "summary": "把这件事解释为旧路重新露面，适合继续探索。",
        "reward": {"discoveryProgress": 1, "renown": 2}
    },
    "trade": {
        "label": "互市佳兆",
        "summary": "把这件事解释为交换与信任正在靠近。",
        "reward": {"tradeReputation": 1, "renown": 1}
    },
    "border": {
        "label": "守边誓言",
        "summary": "把这件事解释为守住边界、整理标记的誓言。",
        "reward": {"wood": 4, "renown": 2}
    }
}
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
TRIBE_SEASON_TABOO_ACTIVE_MINUTES = 30
TRIBE_SEASON_TABOO_PROGRESS_TARGET = 3
TRIBE_SEASON_TABOO_LIMIT = 4
TRIBE_SEASON_TABOO_REMEDY_LIMIT = 5
TRIBE_SEASON_TABOO_OPTIONS = {
    "no_hunt": {
        "label": "禁猎季",
        "summary": "短时间不主动追猎，把兽群动向交给祭司和寻路者记录。",
        "observeLabel": "守禁猎",
        "observeReward": {"renown": 1, "discoveryProgress": 1},
        "blessing": {"renown": 5, "food": 4},
        "breakLabel": "急猎破戒",
        "breakSummary": "为了应急追猎兽群，立刻获得食物，但需要公开补偿禁猎承诺。",
        "breakReward": {"food": 8},
        "remedy": {"title": "兽骨赔礼", "summary": "把急猎所得的一部分送回图腾旁，重新解释禁猎季的意义。", "foodCost": 2, "renownReward": 3, "discoveryReward": 1}
    },
    "guard_fire": {
        "label": "护火季",
        "summary": "优先守住营火和遮蔽，不把公共木材随意拆走。",
        "observeLabel": "添柴守火",
        "observeReward": {"renown": 2},
        "blessing": {"renown": 4, "wood": 4},
        "breakLabel": "拆火取木",
        "breakSummary": "临时拆用护火木材，立刻得到木材，但营火边会留下责问。",
        "breakReward": {"wood": 8},
        "remedy": {"title": "补火赎誓", "summary": "补回被拆走的护火木材，让营地重新承认这条禁忌。", "woodCost": 3, "renownReward": 4}
    },
    "harvest_dance": {
        "label": "丰收舞",
        "summary": "成员轮流跳丰收舞，把采集收成转成共同庆典。",
        "observeLabel": "跳丰收舞",
        "observeReward": {"food": 2, "renown": 1},
        "blessing": {"food": 10, "renown": 3, "tradeReputation": 1},
        "breakLabel": "停舞抢收",
        "breakSummary": "中断丰收舞去抢收近处物资，立刻补给营地，但庆典情绪需要补救。",
        "breakReward": {"food": 4, "wood": 4},
        "remedy": {"title": "补跳丰收舞", "summary": "把被中断的舞步补完，让这次抢收重新回到共同庆典里。", "foodCost": 1, "renownReward": 3, "tradeReward": 1}
    }
}
TRIBE_STANDING_RITUAL_ACTIVE_MINUTES = 25
TRIBE_STANDING_RITUAL_MIN_PARTICIPANTS = 2
TRIBE_STANDING_RITUAL_TARGET_PARTICIPANTS = 3
TRIBE_STANDING_RITUAL_HISTORY_LIMIT = 5
TRIBE_STANDING_RITUAL_OPTIONS = {
    "totem": {
        "label": "图腾环站",
        "summary": "成员围住图腾分站火位、影位和守位，把近期神话变成可见仪式。",
        "reward": {"renown": 4, "wood": 2},
        "fullReward": {"renown": 5}
    },
    "cave": {
        "label": "洞口列队",
        "summary": "成员在洞口前分列，决定是探路、守绳还是携火，为下一次探索积势。",
        "reward": {"renown": 3, "discoveryProgress": 1},
        "fullReward": {"discoveryProgress": 1, "renown": 3}
    },
    "market": {
        "label": "边市迎客",
        "summary": "成员带着食物、木牌或石印排成迎客线，让边市节更像公开外交。",
        "reward": {"tradeReputation": 2, "food": 2},
        "fullReward": {"tradeReputation": 2, "renown": 2}
    },
    "council": {
        "label": "议场席位",
        "summary": "成员按首领、长老、见证者和携物者站位，让一次议会留下共同承认的秩序。",
        "reward": {"renown": 3, "tradeReputation": 1},
        "fullReward": {"renown": 4}
    }
}
TRIBE_STANDING_RITUAL_STANCES = {
    "witness": {"label": "见证者", "summary": "不携带资源，只用在场人数推动传闻。", "renown": 1},
    "fire": {"label": "持火者", "summary": "消耗少量木材，强化声望和守望意味。", "woodCost": 2, "renown": 2},
    "grain": {"label": "携粮者", "summary": "消耗少量食物，强化宴饮、边市或救援意味。", "foodCost": 2, "tradeReputation": 1},
    "stone": {"label": "立石者", "summary": "消耗少量石材，强化洞口、议场和历史记号。", "stoneCost": 2, "discoveryProgress": 1}
}
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
    {"key": "woodland_rack", "type": "tribe_storage", "dx": -8.2, "dz": -5.4, "size": 0.75, "wood": 34, "stone": 10, "label": "林地晾架", "summary": "林地侦察和控制点额外产出木材。"},
    {"key": "quarry_pit", "type": "tribe_workbench", "dx": 8.0, "dz": -5.0, "size": 0.75, "wood": 28, "stone": 26, "label": "山地采石坑", "summary": "山地侦察和控制点额外产出石块。"},
    {"key": "fish_drying_rack", "type": "tribe_hut", "dx": -8.6, "dz": 7.0, "size": 0.72, "wood": 32, "stone": 12, "label": "潮岸晒鱼架", "summary": "海岸侦察和控制点额外产出食物。"},
    {"key": "memory_stone", "type": "tribe_totem", "dx": 8.5, "dz": 7.2, "size": 0.72, "wood": 24, "stone": 34, "label": "旧石记忆碑", "summary": "遗迹侦察和控制点额外推进发现。"},
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
