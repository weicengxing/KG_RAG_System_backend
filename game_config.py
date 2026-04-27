from pathlib import Path

GAME_DATA_DIR = Path(__file__).resolve().parent / "data"
SEASON_HISTORY_PATH = GAME_DATA_DIR / "game_seasons.json"
TRIBE_STATE_PATH = GAME_DATA_DIR / "game_tribes.json"

WEATHER_TYPES = ["sunny", "rain", "snow", "fog"]
WEATHER_LABELS = {
    "sunny": "晴朗海风",
    "rain": "雨幕森林",
    "snow": "细雪海岸",
    "fog": "薄雾岛屿"
}
TRIBE_WEATHER_FORECAST_ACTIVE_MINUTES = 8
TRIBE_WEATHER_FORECAST_RECENT_LIMIT = 5
TRIBE_WEATHER_FORECAST_SIGNS = {
    "cloud": {
        "label": "看云脚",
        "summary": "云脚低压，族人猜下一阵会转成雨幕。",
        "predictWeather": "rain"
    },
    "smoke": {
        "label": "辨烟柱",
        "summary": "烟柱直立，族人猜海风会放晴。",
        "predictWeather": "sunny"
    },
    "frost": {
        "label": "摸霜痕",
        "summary": "草尖发白，族人猜细雪会压到海岸。",
        "predictWeather": "snow"
    },
    "tide": {
        "label": "听潮线",
        "summary": "潮声发闷，族人猜薄雾会从岸边升起。",
        "predictWeather": "fog"
    }
}
TRIBE_CUSTOM_TREE_THRESHOLD = 5
TRIBE_CUSTOM_TREE_RECENT_LIMIT = 8
TRIBE_CUSTOM_TREE_BONUS_LIMIT = 6
TRIBE_CUSTOM_TREE_OPTIONS = {
    "merchant": {
        "label": "重商",
        "summary": "部落把互市、商队和账记当成稳定秩序，后续贸易会更容易积累信誉。",
        "practiceLabel": "整理互市账",
        "practiceSummary": "把近期交易、信使和边市旧账整理成一条公开风俗。",
        "eventKeys": ["trade_accept", "caravan_trade", "market_pact_trade", "far_reply_trade"],
        "reward": {"tradeReputation": 1},
        "effectSummary": "贸易与边市类事件额外获得贸易信誉。"
    },
    "oathbound": {
        "label": "守誓",
        "summary": "部落把律令、誓约和补救看得很重，后续守约/补救会更能安定边界。",
        "practiceLabel": "重述旧誓",
        "practiceSummary": "把律令、誓约任务和赎罪记录讲给营火旁的人听。",
        "eventKeys": ["tribe_law_uphold", "law_remedy", "oath_task", "atonement", "season_taboo"],
        "reward": {"renown": 1, "pressureRelief": 1},
        "effectSummary": "律令、誓约和补救类事件额外获得声望并轻微缓解战争压力。"
    },
    "warlike": {
        "label": "好战",
        "summary": "部落习惯把边境、集结和胜负讲成荣耀，后续冲突会更容易沉淀声望。",
        "practiceLabel": "刻下战痕",
        "practiceSummary": "把一次守边、争夺或战争后的结果刻成可传述的战痕。",
        "eventKeys": ["personal_conflict", "small_conflict", "formal_war", "boundary_press", "war_aftermath"],
        "reward": {"renown": 1},
        "effectSummary": "冲突和战后类事件额外获得部落声望。"
    },
    "hearth": {
        "label": "敬火",
        "summary": "部落把营火、烹饪和共同动作当成核心礼节，后续火边事件会回补营地。",
        "practiceLabel": "护火讲礼",
        "practiceSummary": "把共同烹饪、群体动作和营火旁的规矩整理成火边礼法。",
        "eventKeys": ["communal_cook", "group_emote", "tribe_ritual", "herd", "storm"],
        "reward": {"food": 1, "renown": 1},
        "effectSummary": "烹饪、群体动作和火边事件额外获得食物与声望。"
    },
    "tidal": {
        "label": "逐潮",
        "summary": "部落习惯听天气、潮线和夜路旧痕，后续探索更容易转成发现。",
        "practiceLabel": "听潮记路",
        "practiceSummary": "把夜行、风向预判、洞穴和遗迹线索连成一条探路风俗。",
        "eventKeys": ["night_outing", "weather_forecast", "cave", "ruin_clue", "rare_ruin"],
        "reward": {"discoveryProgress": 1},
        "effectSummary": "夜行、天气、洞穴和遗迹类事件额外获得发现进度。"
    }
}
TRIBE_LAW_ACTIVE_MINUTES = 20
TRIBE_LAW_RECORD_LIMIT = 5
TRIBE_LAW_REMEDY_LIMIT = 5
TRIBE_LAW_OPTIONS = {
    "border_watch": {
        "label": "守边令",
        "summary": "短时要求成员优先整理边界标记和警戒路线，边境相关事件会更稳。",
        "upholdLabel": "巡边守令",
        "upholdReward": {"renown": 1},
        "eventBonus": {"renown": 1, "pressureRelief": 1},
        "breakLabel": "擅离边线",
        "remedyTitle": "补刻边界标记",
        "remedySummary": "成员用木牌和火灰把漏看的边线补回去，避免守边令留下新的压力。",
        "remedyCost": {"wood": 2},
        "remedyReward": {"renown": 1, "pressureRelief": 1}
    },
    "market_tally": {
        "label": "互市令",
        "summary": "短时要求交易和接待都留下木牌账记，贸易相关事件会更容易沉淀信任。",
        "upholdLabel": "记互市账",
        "upholdReward": {"tradeReputation": 1},
        "eventBonus": {"tradeReputation": 1},
        "breakLabel": "私换漏记",
        "remedyTitle": "补记互市账",
        "remedySummary": "成员补上漏记的口头账，让互市令不变成旧怨。",
        "remedyCost": {"food": 1},
        "remedyReward": {"tradeReputation": 1}
    },
    "fire_quiet": {
        "label": "禁火令",
        "summary": "短时要求夜里和雾里少用明火，只保留必要火种，探索和天气事件会更谨慎。",
        "upholdLabel": "护暗火",
        "upholdReward": {"discoveryProgress": 1},
        "eventBonus": {"discoveryProgress": 1},
        "breakLabel": "擅燃明火",
        "remedyTitle": "重护暗火",
        "remedySummary": "成员用泥灰压低火光，把禁火令从惊扰补回守望。",
        "remedyCost": {"wood": 1, "food": 1},
        "remedyReward": {"discoveryProgress": 1, "renown": 1}
    }
}
TRIBE_SHARED_PUZZLE_TARGET = 4
TRIBE_SHARED_PUZZLE_RECORD_LIMIT = 5
TRIBE_SHARED_PUZZLE_SOURCES = {
    "cave": {
        "label": "洞穴碎片",
        "summary": "从洞口回声、远征记录和深处刻痕里抄下一角图案。",
        "reward": {"discoveryProgress": 1}
    },
    "ruin": {
        "label": "遗迹碎片",
        "summary": "把遗迹线索、活地图记忆或旧石拓片补到同一张图上。",
        "reward": {"renown": 1}
    },
    "traveler": {
        "label": "旅人碎片",
        "summary": "从来访者口信、远方回信或流浪氏族故事中记下一枚符号。",
        "reward": {"tradeReputation": 1}
    },
    "market": {
        "label": "边市碎片",
        "summary": "从互市约定、商队货牌和交换通路账记里拼出边缘纹样。",
        "reward": {"tradeReputation": 1, "renown": 1}
    }
}
TRIBE_SHARED_PUZZLE_COMPLETE_REWARD = {
    "discoveryProgress": 2,
    "renown": 4,
    "tradeReputation": 2
}
TRIBE_RUMOR_TRUTH_ACTIVE_MINUTES = 30
TRIBE_RUMOR_TRUTH_LIMIT = 4
TRIBE_RUMOR_TRUTH_RECORD_LIMIT = 6
TRIBE_RUMOR_TRUTH_HINT_MINUTES = 24
TRIBE_RUMOR_TRUTH_ACTIONS = {
    "believe": {
        "label": "相信传闻",
        "summary": "把传闻当作可用线索，快速换取发现或声望；若传闻走偏，会留下轻量误导记录。",
        "reward": {"discoveryProgress": 1, "renown": 1},
        "trueBonus": {"discoveryProgress": 1},
        "falsePenalty": {"renown": -1},
        "hintLabel": "相信传闻"
    },
    "verify": {
        "label": "派人验证",
        "summary": "校对线索来源，收益更稳，并让下一次事件提示更可信。",
        "reward": {"discoveryProgress": 1},
        "trueBonus": {"renown": 2},
        "falseBonus": {"tradeReputation": 1},
        "hintLabel": "验证传闻"
    },
    "counter": {
        "label": "反向传闻",
        "summary": "公开修正或反制这条说法，换取贸易信誉，并可能降低边界战争压力。",
        "reward": {"tradeReputation": 1},
        "pressureRelief": 1,
        "hintLabel": "反向传闻"
    }
}
TRIBE_WORLD_RIDDLE_ACTIVE_MINUTES = 18
TRIBE_WORLD_RIDDLE_LIMIT = 4
TRIBE_WORLD_RIDDLE_RADIUS = 24
TRIBE_WORLD_RIDDLE_SPAWN_CHANCE = 0.28
TRIBE_WORLD_RIDDLE_RECORD_LIMIT = 6
TRIBE_WORLD_RIDDLE_INFLUENCE_MINUTES = 45
TRIBE_WORLD_RIDDLE_INFLUENCE_LIMIT = 5
TRIBE_WORLD_RIDDLE_INFLUENCE_BONUS = 0.12
TRIBE_WORLD_RIDDLE_INFLUENCE_MAX_BONUS = 0.32
TRIBE_WORLD_RIDDLE_PREDICTIONS = {
    "sky": {
        "label": "指向天象",
        "summary": "把符号读成星、月、云影的预兆，命中后提高天象窗口权重。"
    },
    "ruin": {
        "label": "指向遗迹",
        "summary": "把石影读成旧石和洞口的提示，命中后提高稀有遗迹权重。"
    },
    "tide": {
        "label": "指向潮汐",
        "summary": "把声响读成水线和兽群迁移，命中后牵引下一轮稀有事件。"
    }
}
TRIBE_WORLD_RIDDLE_PATTERNS = [
    {
        "key": "stone_circle",
        "title": "石阵错影",
        "label": "石阵谜语",
        "patternLabel": "三块石影轮流指向晨星",
        "summary": "短石、长影和碎光排成环，像是在等人判断它指向天空还是旧路。",
        "answerKey": "sky",
        "influenceKind": "celestial",
        "influenceLabel": "天象权重+",
        "reward": {"discoveryProgress": 1, "renown": 1}
    },
    {
        "key": "hollow_echo",
        "title": "空洞回声",
        "label": "回声谜语",
        "patternLabel": "空地回声在地下重复三次",
        "summary": "没有洞口的地方传出回声，像旧石遗迹在用地下声音报信。",
        "answerKey": "ruin",
        "influenceKind": "rare_ruin",
        "influenceLabel": "稀有遗迹权重+",
        "reward": {"discoveryProgress": 2}
    },
    {
        "key": "tide_notches",
        "title": "潮痕刻线",
        "label": "潮痕谜语",
        "patternLabel": "湿线和兽足印隔一段就重合",
        "summary": "泥地上水线、兽足和碎贝壳排成间隔规律，像潮汐把远处消息推回来。",
        "answerKey": "tide",
        "influenceKind": "rare_ruin",
        "influenceLabel": "稀有事件权重+",
        "reward": {"tradeReputation": 1, "renown": 1}
    }
]
TRIBE_NAMED_LANDMARK_LIMIT = 10
TRIBE_NAMED_LANDMARK_PROPOSAL_LIMIT = 6
TRIBE_NAMED_LANDMARK_RECORD_LIMIT = 8
TRIBE_NAMED_LANDMARK_SUPPORT_TARGET = 2
TRIBE_NAMED_LANDMARK_NAME_MIN = 2
TRIBE_NAMED_LANDMARK_NAME_MAX = 14
TRIBE_NAMED_LANDMARK_SOURCES = {
    "first_scout": {
        "label": "首探命名",
        "summary": "把侦察、洞穴或活地图记忆里发现的位置命成部落地名。",
        "reward": {"discoveryProgress": 1, "renown": 1}
    },
    "rescue": {
        "label": "救援命名",
        "summary": "救灾、补救或互助之后，把被救回来的地方写进地图。",
        "reward": {"renown": 2}
    },
    "war": {
        "label": "战后命名",
        "summary": "战争、边界冲突或停战之后，为旧战场或守边地命名。",
        "reward": {"renown": 2, "tradeReputation": 1}
    },
    "ritual": {
        "label": "祭典命名",
        "summary": "仪式、烹饪、鼓点或庆功之后，把营地余韵落成地名。",
        "reward": {"renown": 1, "tradeReputation": 1}
    }
}
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
PLAYER_RELATION_SCORE_MIN = -6
PLAYER_RELATION_SCORE_MAX = 6
PLAYER_RELATION_FRIEND_THRESHOLD = 3
PLAYER_RELATION_BEST_FRIEND_THRESHOLD = 5
PLAYER_RELATION_RIVAL_THRESHOLD = -3
PLAYER_RELATION_NEMESIS_THRESHOLD = -5
PLAYER_RELATION_HISTORY_LIMIT = 8
PLAYER_RELATION_STATUS_LIMIT = 4
PLAYER_RELATION_INSPIRE_DELTA = 2
PLAYER_RELATION_CELEBRATION_DELTA = 1
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
    "intimidate": {"label": "威慑", "summary": "靠近对方发出警告，提升个人声望并轻微影响部落关系。", "renown": 1, "fatigue": 1, "relationDelta": -1, "personalRelationDelta": -1},
    "challenge": {"label": "挑战", "summary": "进行一次短促的近身冲突，胜负只造成疲劳和击退，不造成死亡。", "renown": 2, "fatigue": 2, "relationDelta": -2, "personalRelationDelta": -2, "knockback": 2.4},
    "spar": {"label": "切磋", "summary": "同部落成员之间的练习冲突，只留下少量疲劳和个人声望。", "renown": 1, "fatigue": 1, "sameTribeOnly": True, "relationDelta": 0, "personalRelationDelta": 1, "knockback": 1.0, "trainingRenown": PLAYER_CONFLICT_SPARRING_RENOWN},
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
TRIBE_COMMUNAL_COOK_ACTIVE_MINUTES = 20
TRIBE_COMMUNAL_COOK_TARGET = 3
TRIBE_COMMUNAL_COOK_HISTORY_LIMIT = 6
TRIBE_COMMUNAL_COOK_RECIPES = {
    "hearth_stew": {
        "label": "围火杂炖",
        "summary": "把公共食物煮成一锅能让采集队继续出发的热汤。",
        "foodCost": 3,
        "woodCost": 2,
        "reward": {"food": 6, "renown": 3}
    },
    "market_broth": {
        "label": "边市香汤",
        "summary": "把剩余食材和边市口信一起煮开，让交换更容易被记住。",
        "foodCost": 4,
        "woodCost": 1,
        "reward": {"tradeReputation": 2, "renown": 2}
    },
    "trail_porridge": {
        "label": "寻路稠粥",
        "summary": "为远行者准备耐放的稠粥，把洞口和旧路故事揉进餐前分工。",
        "foodCost": 4,
        "woodCost": 2,
        "reward": {"discoveryProgress": 1, "renown": 2}
    }
}
TRIBE_COMMUNAL_COOK_INGREDIENTS = {
    "wood": {"label": "补柴", "summary": "消耗公共木材，让火势稳定。", "woodCost": 1, "renown": 1},
    "grain": {"label": "添粮", "summary": "消耗公共食物，让这锅饭更厚实。", "foodCost": 1, "food": 1},
    "stone": {"label": "立热石", "summary": "消耗公共石块，让锅边留下可复用的热石。", "stoneCost": 1, "discoveryProgress": 1},
    "story": {"label": "讲来历", "summary": "不消耗资源，把谁带来了什么写进宴会记忆。", "renown": 1, "tradeReputation": 1}
}
TRIBE_NIGHT_OUTING_RECENT_LIMIT = 6
TRIBE_NIGHT_OUTING_WEATHER_RISK = {
    "sunny": 0,
    "rain": 1,
    "snow": 2,
    "fog": 1
}
TRIBE_NIGHT_OUTING_OPTIONS = {
    "torch": {
        "label": "举火探路",
        "summary": "消耗一份公共木材，让夜路队用火把照出近处痕迹。",
        "woodCost": 1,
        "riskRelief": 2,
        "reward": {"discoveryProgress": 1, "renown": 1},
        "successMemory": True
    },
    "companions": {
        "label": "结伴守望",
        "summary": "至少两名成员在册时可组织同伴站位，靠人声和回望压低迷路风险。",
        "minMembers": 2,
        "riskRelief": 1,
        "reward": {"renown": 2},
        "successMemory": True
    },
    "totem_blessing": {
        "label": "问图腾火",
        "summary": "从部落图腾取火记方向，图腾或站位仪式会进一步降低夜行风险。",
        "riskRelief": 1,
        "reward": {"renown": 1, "discoveryProgress": 1},
        "successMemory": True
    },
    "read_weather": {
        "label": "按风向预判",
        "summary": "读取当前风向预判和天气记录，若近期命中过天气会让夜路更稳。",
        "riskRelief": 1,
        "reward": {"discoveryProgress": 1, "tradeReputation": 1},
        "successMemory": True
    }
}
TRIBE_DREAM_OMEN_ACTIVE_MINUTES = 18
TRIBE_DREAM_OMEN_SOURCE_LIMIT = 6
TRIBE_DREAM_OMEN_RECORD_LIMIT = 6
TRIBE_DREAM_OMEN_EVENT_BIAS_USES = 1
TRIBE_DREAM_OMEN_ACTIONS = {
    "interpret": {
        "label": "解梦",
        "summary": "把梦里的路、星和旧痕解释成可追踪的线索。",
        "reward": {"discoveryProgress": 1, "renown": 1},
        "eventBias": "ruin_clue",
        "eventBiasLabel": "遗迹线索"
    },
    "quiet": {
        "label": "压梦",
        "summary": "把惊醒和不安压回营火旁，避免边界旧怨被梦兆放大。",
        "reward": {"renown": 1, "pressureRelief": 1}
    },
    "share": {
        "label": "分享梦路",
        "summary": "把同一段梦路讲给外来者和邻近营地听，让梦兆变成可交换口信。",
        "reward": {"tradeReputation": 1, "renown": 1},
        "eventBias": "herd",
        "eventBiasLabel": "兽群经过"
    }
}
TRIBE_DRUM_RHYTHM_ACTIVE_MINUTES = 18
TRIBE_DRUM_RHYTHM_MIN_PARTICIPANTS = 2
TRIBE_DRUM_RHYTHM_TARGET_PARTICIPANTS = 3
TRIBE_DRUM_RHYTHM_HISTORY_LIMIT = 5
TRIBE_DRUM_RHYTHM_RADIUS = 16
TRIBE_DRUM_RHYTHM_OPTIONS = {
    "festival": {
        "label": "祭火慢拍",
        "summary": "在图腾或营火旁打出稳慢鼓点，把祭典余温留给采集和宴会。",
        "reward": {"renown": 3, "tradeReputation": 1},
        "fullReward": {"renown": 3}
    },
    "muster": {
        "label": "集结急拍",
        "summary": "用短促鼓声召回边境成员，压住冲突后的躁动与误判。",
        "reward": {"renown": 3, "warPressureRelief": 1},
        "fullReward": {"renown": 2}
    },
    "cave": {
        "label": "洞穴回声",
        "summary": "让鼓声在洞口故事里反复，给下一轮探路和嗅探留节奏。",
        "reward": {"discoveryProgress": 1, "renown": 2},
        "fullReward": {"discoveryProgress": 1}
    }
}
TRIBE_DRUM_RHYTHM_BEATS = {
    "steady": {"label": "稳拍", "summary": "稳住队列，给仪式留下清晰节奏。", "renown": 1},
    "answer": {"label": "应拍", "summary": "回应前一名成员的鼓声，让多人节奏连起来。", "tradeReputation": 1},
    "echo": {"label": "回拍", "summary": "把鼓点送向洞口和旧路，留下探索回声。", "discoveryProgress": 1},
    "watch": {"label": "守拍", "summary": "用警戒节奏安抚边境，轻微削减战争压力。", "warPressureRelief": 1}
}
TRIBE_GROUP_EMOTE_COOLDOWN_SECONDS = 45
TRIBE_GROUP_EMOTE_HISTORY_LIMIT = 8
TRIBE_GROUP_EMOTE_ACTIONS = {
    "sit_fire": {
        "label": "围火坐下",
        "summary": "成员在营火旁坐下，把疲惫和闲话压成稳定的营地声望。",
        "renown": 1,
        "personalRenown": 1,
        "animation": "sit"
    },
    "raise_torch": {
        "label": "举火",
        "summary": "举起火把照亮附近路径，让探索队更容易记住下一段线索。",
        "woodCost": 1,
        "renown": 1,
        "discoveryProgress": 1,
        "personalRenown": 1,
        "animation": "guard"
    },
    "offer_gift": {
        "label": "献礼",
        "summary": "拿出一点公共食物作为公开礼节，巩固来往与交换信誉。",
        "foodCost": 1,
        "tradeReputation": 1,
        "renown": 1,
        "personalRenown": 1,
        "animation": "cheer"
    },
    "watch": {
        "label": "警戒",
        "summary": "成员短暂摆出守望姿态，提醒边界队伍收束误判。",
        "renown": 1,
        "pressureRelief": 1,
        "personalRenown": 1,
        "animation": "guard"
    },
    "mourn": {
        "label": "默哀",
        "summary": "围住旧事低声默哀，把冲突后的余震整理成可承认的记忆。",
        "renown": 2,
        "pressureRelief": 1,
        "personalRenown": 1,
        "animation": "ritual"
    }
}
TRIBE_MENTORSHIP_ACTIVE_MINUTES = 24
TRIBE_MENTORSHIP_TARGET_STUDENTS = 2
TRIBE_MENTORSHIP_MIN_STUDENTS = 1
TRIBE_MENTORSHIP_HISTORY_LIMIT = 6
TRIBE_MENTORSHIP_MIN_PERSONAL_RENOWN = 7
TRIBE_MENTORSHIP_MIN_CONTRIBUTION = 40
TRIBE_MENTORSHIP_FOCUS_OPTIONS = {
    "gather": {
        "label": "采集门道",
        "summary": "导师把辨枝、分粮和回营路线教给新人，适合补足营地日常。",
        "renown": 2,
        "food": 2,
        "mentorRenown": 1,
        "studentRenown": 1,
        "animation": "gather"
    },
    "guard": {
        "label": "守边口令",
        "summary": "导师带新人记住边界呼应、退让和警戒姿势，降低误判余震。",
        "renown": 2,
        "pressureRelief": 1,
        "mentorRenown": 1,
        "studentRenown": 1,
        "animation": "guard"
    },
    "story": {
        "label": "讲述规矩",
        "summary": "导师示范如何把旧事讲成可被外人理解的礼节。",
        "renown": 2,
        "tradeReputation": 1,
        "mentorRenown": 1,
        "studentRenown": 1,
        "animation": "cheer"
    },
    "trail": {
        "label": "探路记号",
        "summary": "导师带新人辨认洞口、路标和旧痕，给下一轮探索留下方法。",
        "renown": 1,
        "discoveryProgress": 1,
        "mentorRenown": 1,
        "studentRenown": 1,
        "animation": "ritual"
    }
}
TRIBE_CELEBRATION_ECHO_ACTIVE_MINUTES = 14
TRIBE_CELEBRATION_ECHO_LIMIT = 5
TRIBE_CELEBRATION_ECHO_RADIUS = 18
TRIBE_CELEBRATION_ECHO_HISTORY_LIMIT = 8
TRIBE_CELEBRATION_ECHO_SOURCES = {
    "war": {
        "title": "凯旋余韵",
        "anchor": "road",
        "summary": "战争或停战后的队列沿营地道路走过，留下可被成员再次加入的庆功步伐。",
        "reward": {"renown": 2, "tradeReputation": 1, "personalRenown": 1}
    },
    "ritual": {
        "title": "仪式余韵",
        "anchor": "totem",
        "summary": "大型仪式散去后，图腾旁仍留着可见的站位回声。",
        "reward": {"renown": 2, "discoveryProgress": 1, "personalRenown": 1}
    },
    "cooking": {
        "title": "宴火余韵",
        "anchor": "campfire",
        "summary": "共同烹饪后的火边还留着香气和故事，后来者可以补上一段庆功。",
        "reward": {"renown": 1, "tradeReputation": 1, "personalRenown": 1}
    },
    "drum": {
        "title": "鼓点余韵",
        "anchor": "totem",
        "summary": "鼓点收束后，营地仍能听见一段适合回应的节奏。",
        "reward": {"renown": 1, "discoveryProgress": 1, "personalRenown": 1}
    }
}
TRIBE_SACRED_FIRE_RELAY_ACTIVE_MINUTES = 22
TRIBE_SACRED_FIRE_RELAY_MIN_PARTICIPANTS = 2
TRIBE_SACRED_FIRE_RELAY_TARGET_PARTICIPANTS = 3
TRIBE_SACRED_FIRE_RELAY_HISTORY_LIMIT = 5
TRIBE_SACRED_FIRE_RELAY_DESTINATIONS = {
    "cave": {
        "label": "洞口火种",
        "summary": "把旧营火护送到洞口，让下一段探索带着稳定火光。",
        "reward": {"renown": 3, "discoveryProgress": 1},
        "fullReward": {"discoveryProgress": 1}
    },
    "market": {
        "label": "边市暖火",
        "summary": "把火种带到边市路口，让交换从冷淡变成可围坐的礼节。",
        "reward": {"renown": 2, "tradeReputation": 2},
        "fullReward": {"food": 2, "tradeReputation": 1}
    },
    "wonder": {
        "label": "奇观献火",
        "summary": "把火种送向远处奇观或旧石记号，给部落传说留下新开端。",
        "reward": {"renown": 4, "discoveryProgress": 1},
        "fullReward": {"renown": 2}
    }
}
TRIBE_SACRED_FIRE_RELAY_STEPS = {
    "carry": {"label": "护火前行", "summary": "稳稳托住火种前进，给接力留下基础声望。", "renown": 1, "animation": "guard"},
    "shield": {"label": "挡风护焰", "summary": "消耗少量木材给火种挡风，也压低边界躁动。", "woodCost": 1, "renown": 1, "warPressureRelief": 1, "animation": "guard"},
    "share": {"label": "分暖同行", "summary": "消耗一点食物分给同行者，让火种成为互助礼节。", "foodCost": 1, "tradeReputation": 1, "animation": "cheer"},
    "chant": {"label": "唱路记号", "summary": "边走边唱出旧路和洞口名字，推动发现线索。", "discoveryProgress": 1, "animation": "ritual"}
}
TRIBE_SACRED_FIRE_RELAY_EVENTS = [
    {"key": "clear_wind", "label": "顺风护火", "summary": "风向短暂顺着队伍，火种更亮。", "reward": {"renown": 1}},
    {"key": "ash_rain", "label": "灰雨试炼", "summary": "细灰落下，队伍必须互相遮挡。", "reward": {"discoveryProgress": 1}},
    {"key": "shared_song", "label": "共歌回声", "summary": "同行者唱起同一段调子，路边的人愿意记住这次接力。", "reward": {"tradeReputation": 1}},
    {"key": "ember_falter", "label": "火星欲灭", "summary": "火星一度变暗，守火者稳住了惊慌。", "reward": {"warPressureRelief": 1}}
]
TRIBE_LOST_TECH_FRAGMENT_TARGET = 3
TRIBE_LOST_TECH_ACTIVE_MINUTES = 45
TRIBE_LOST_TECH_HISTORY_LIMIT = 6
TRIBE_LOST_TECH_SOURCES = {
    "rubbing": {
        "label": "遗迹拓片",
        "summary": "从遗迹线索、稀有发现或收藏墙上抄下旧纹样。",
        "renown": 1,
        "requires": "discovery_or_collection"
    },
    "cave": {
        "label": "洞穴发现",
        "summary": "把洞穴远征带回的回声和刻痕拼进技艺记忆。",
        "discoveryProgress": 1,
        "requires": "cave_memory"
    },
    "old_object": {
        "label": "旧物收藏",
        "summary": "拆看旧物、信物或回声物品，找到可复原的手法。",
        "tradeReputation": 1,
        "requires": "collection"
    },
    "elder_tale": {
        "label": "长者讲述",
        "summary": "让长者把旧故事复述成可操作的步骤。",
        "renown": 1,
        "requires": "history"
    }
}
TRIBE_LOST_TECH_OPTIONS = {
    "stone_joinery": {
        "label": "扣石榫法",
        "summary": "短时降低营地建筑木石消耗，适合扩建仓库、道路和工台。",
        "buildCostDiscountPercent": 8,
        "renown": 2
    },
    "ember_basket": {
        "label": "火篮编法",
        "summary": "让丰收篝火和采集队更容易携带余火。",
        "ritualGatherBonus": 1,
        "food": 3
    },
    "shell_tally": {
        "label": "贝筹记账",
        "summary": "短时提高部落贸易结算后的信誉收益。",
        "tradeReputationBonus": 1,
        "tradeReputation": 2
    },
    "cave_lamp": {
        "label": "洞灯护罩",
        "summary": "下一段洞穴远征更容易多带回发现。",
        "caveFindsBonus": 1,
        "discoveryProgress": 1
    }
}
TRIBE_TRADE_MAX_ACTIVE = 5
TRIBE_TRADE_RENOWN_BONUS = 3
TRIBE_TRADE_CREDIT_ACTIVE_MINUTES = 36
TRIBE_TRADE_CREDIT_RECORD_LIMIT = 8
TRIBE_TRADE_CREDIT_REPAIR_LIMIT = 6
TRIBE_TRADE_CREDIT_REPAIR_WOOD_COST = 2
TRIBE_TRADE_CREDIT_REPAIR_FOOD_COST = 2
TRIBE_TRADE_CREDIT_TIERS = [
    {
        "key": "credit",
        "label": "赊账",
        "minStreak": 2,
        "requestDiscount": 1,
        "reputationBonus": 0,
        "stockBonus": 0,
        "summary": "连续守约后，下一次贸易可以少要一点资源。"
    },
    {
        "key": "reservation",
        "label": "预订",
        "minStreak": 3,
        "requestDiscount": 1,
        "reputationBonus": 1,
        "stockBonus": 0,
        "summary": "双方愿意为对方留货，完成贸易后额外增加贸易信誉。"
    },
    {
        "key": "shared_stock",
        "label": "共同库存",
        "minStreak": 4,
        "requestDiscount": 2,
        "reputationBonus": 1,
        "stockBonus": 1,
        "summary": "长期守约形成共同库存，完成贸易后双方各回收一点交换物资。"
    }
]
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
TRIBE_NOMAD_CARAVAN_ACTIVE_MINUTES = 14
TRIBE_NOMAD_CARAVAN_LIMIT = 4
TRIBE_NOMAD_CARAVAN_ACTIONS = {
    "escort": {
        "label": "护送商队",
        "summary": "派人护送中立商队穿过边界，把边市热度转成安全名声。",
        "renown": 4,
        "tradeReputation": 1,
        "relationDelta": 1,
        "tradeTrustDelta": 1
    },
    "host": {
        "label": "招待商队",
        "summary": "拿出少量公共食物招待商队，换来沿途补给和互市口碑。",
        "foodCost": 2,
        "food": 5,
        "tradeReputation": 2,
        "relationDelta": 1
    },
    "invite_stop": {
        "label": "争取停靠",
        "summary": "把商队留在边市多停一晚，尝试沉淀新的互市约定。",
        "tradeReputation": 1,
        "renown": 2,
        "tradeTrustDelta": 2,
        "pactChanceBonus": 0.2
    }
}
TRIBE_NOMAD_VISITOR_ACTIVE_MINUTES = 18
TRIBE_NOMAD_VISITOR_LIMIT = 4
TRIBE_NOMAD_VISITOR_CHANCE = 0.28
TRIBE_NOMAD_VISITOR_AFTEREFFECT_MINUTES = 24
TRIBE_NOMAD_VISITOR_AFTEREFFECT_LIMIT = 6
TRIBE_NOMAD_VISITOR_LIBRARY = {
    "curio_trader": {
        "label": "贝壳行商",
        "title": "贝壳行商来访",
        "summary": "一名带着贝壳、干草药和远方口信的行商从地图边缘靠近营地。",
        "giftLabel": "奇货与口信",
        "defaultAction": "barter"
    },
    "omen_speaker": {
        "label": "预兆讲述者",
        "title": "预兆讲述者来访",
        "summary": "披着旧兽皮的讲述者声称看见天象与遗迹之间的联系。",
        "giftLabel": "预言与旧图",
        "defaultAction": "listen"
    },
    "lost_clan": {
        "label": "流浪氏族",
        "title": "流浪氏族停步",
        "summary": "一小支流浪氏族在边缘火堆旁停下，带来纠纷、手艺和交换机会。",
        "giftLabel": "纠纷与手艺",
        "defaultAction": "mediate"
    },
    "craft_keeper": {
        "label": "失落技艺守者",
        "title": "失落技艺守者来访",
        "summary": "年长的守者带来旧石器的修补方法，想换取食物和安全过夜。",
        "giftLabel": "失落手艺",
        "defaultAction": "learn_craft"
    }
}
TRIBE_NOMAD_VISITOR_ACTIONS = {
    "barter": {
        "label": "交换奇货",
        "summary": "拿出少量公共食物交换奇货和远方口信。",
        "foodCost": 2,
        "food": 3,
        "tradeReputation": 2,
        "renown": 1,
        "afterLabel": "奇货口信"
    },
    "listen": {
        "label": "听取预言",
        "summary": "请来访者讲述预兆，换取发现进度并开启可争论的解释。",
        "renown": 2,
        "discoveryProgress": 1,
        "openMyth": True,
        "afterLabel": "预言余音"
    },
    "mediate": {
        "label": "调解纠纷",
        "summary": "帮流浪者调解路上纠纷，把紧张故事转成部落名声。",
        "renown": 3,
        "pressureRelief": 1,
        "relationDelta": 1,
        "afterLabel": "调解口碑"
    },
    "learn_craft": {
        "label": "学习手艺",
        "summary": "用木石和食物换取失落修补手艺。",
        "foodCost": 1,
        "woodCost": 1,
        "stoneCost": 1,
        "wood": 3,
        "stone": 3,
        "renown": 2,
        "afterLabel": "手艺记号"
    }
}
TRIBE_NOMAD_VISITOR_AFTEREFFECT_ACTIONS = {
    "guest_lodge": {
        "label": "短期客居",
        "summary": "给流浪氏族留一处夜火，换来补给、手艺和友好口碑。",
        "foodCost": 2,
        "wood": 4,
        "stone": 2,
        "tradeReputation": 1,
        "renown": 2,
        "relationDelta": 1
    },
    "mediate_dispute": {
        "label": "纠纷调停",
        "summary": "公开调停来访者带来的路上纠纷，降低边界误会。",
        "renown": 3,
        "relationDelta": 1,
        "tradeTrustDelta": 1,
        "pressureRelief": 1
    },
    "preserve_prophecy": {
        "label": "保存预言",
        "summary": "把旅人的预兆刻成短句，提前牵引下一次天象或遗迹线索。",
        "stoneCost": 1,
        "discoveryProgress": 1,
        "renown": 1
    }
}
TRIBE_APPRENTICE_EXCHANGE_ACTIVE_MINUTES = 30
TRIBE_APPRENTICE_EXCHANGE_LIMIT = 6
TRIBE_APPRENTICE_EXCHANGE_RECENT_LIMIT = 5
TRIBE_APPRENTICE_EXCHANGE_MIN_RELATION = 2
TRIBE_APPRENTICE_EXCHANGE_MIN_TRADE_TRUST = 2
TRIBE_APPRENTICE_EXCHANGE_ACTIONS = {
    "customs": {
        "label": "学习风俗",
        "summary": "互派年轻成员记录对方的篝火礼节，短时提高仪式采集加成。",
        "renown": 3,
        "relationDelta": 1,
        "tradeTrustDelta": 1,
        "ritualGatherBonus": 1,
        "buffLabel": "风俗学徒",
        "buffSummary": "下一次丰收篝火采集加成额外 +1。"
    },
    "building": {
        "label": "学习建筑",
        "summary": "让学徒跟着对方修整营地，短时降低部落建造消耗。",
        "renown": 2,
        "relationDelta": 1,
        "buildCostDiscountPercent": 10,
        "buffLabel": "建筑学徒",
        "buffSummary": "部落建造木材和石块消耗降低 10%。"
    },
    "trade": {
        "label": "学习贸易",
        "summary": "交换边市口信和记账方式，短时提高完成贸易后的信誉。",
        "renown": 2,
        "tradeReputation": 1,
        "relationDelta": 1,
        "tradeTrustDelta": 2,
        "tradeReputationBonus": 1,
        "buffLabel": "贸易学徒",
        "buffSummary": "完成部落贸易时额外获得贸易信誉 +1。"
    }
}
TRIBE_GUEST_STAY_ACTIVE_MINUTES = 24
TRIBE_GUEST_STAY_RECORD_LIMIT = 8
TRIBE_GUEST_STAY_MIN_RELATION = 1
TRIBE_GUEST_STAY_MIN_TRADE_TRUST = 1
TRIBE_GUEST_STAY_WANDERER_TARGET_LIMIT = 8
TRIBE_GUEST_STAY_ACTIONS = {
    "build_help": {
        "label": "帮忙建设",
        "summary": "客居者帮忙搬木、垒石和修补营地，只留下故事，不获得核心权限。",
        "wood": 3,
        "stone": 2,
        "renown": 1,
        "contribution": 3,
        "guestRenown": 1,
        "relationDelta": 1
    },
    "relief_help": {
        "label": "帮忙救灾",
        "summary": "客居者协助分食、守夜和安顿伤者，把危急时刻变成可回忆的人情。",
        "food": 3,
        "renown": 2,
        "pressureRelief": 1,
        "contribution": 2,
        "relationDelta": 1
    },
    "market_help": {
        "label": "帮忙互市",
        "summary": "客居者替两个营地解释口风、搬运货物，短时提高贸易信誉与信任。",
        "tradeReputation": 2,
        "renown": 1,
        "contribution": 2,
        "relationDelta": 1,
        "tradeTrustDelta": 1
    },
    "story_help": {
        "label": "讲述来历",
        "summary": "客居者把远路、旧事和火边规矩讲给营地，留下发现线索与共同故事。",
        "discoveryProgress": 1,
        "renown": 2,
        "guestRenown": 1,
        "relationDelta": 1
    }
}
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
TRIBE_COVENANT_MESSENGER_ACTIVE_MINUTES = 16
TRIBE_COVENANT_MESSENGER_LIMIT = 6
TRIBE_COVENANT_MESSENGER_PROGRESS_TARGET = 1
TRIBE_COVENANT_MESSENGER_RENOWN = 2
TRIBE_COVENANT_MESSENGER_TRADE = 1
TRIBE_COVENANT_MESSENGER_RELATION = 1
TRIBE_COVENANT_MESSENGER_TRUST = 1
TRIBE_COVENANT_MESSENGER_OUTCOMES = {
    "clear_path": {
        "key": "clear_path",
        "label": "顺利送达",
        "summary": "信物被双方公开承认，口头约定落成了可回看的旧痕。",
        "weight": 5
    },
    "misunderstanding": {
        "key": "misunderstanding",
        "label": "途中误会",
        "summary": "信使在边界被误会拦下，解释清楚后反而让双方记住了这次承诺。",
        "renownBonus": 1,
        "relationBonus": -1,
        "weight": 2
    },
    "third_party_talk": {
        "key": "third_party_talk",
        "label": "第三方截谈",
        "summary": "路上遇到旁观部落截谈，消息传得更远，互市口碑也随之扩散。",
        "tradeBonus": 1,
        "weight": 2
    },
    "extra_gain": {
        "key": "extra_gain",
        "label": "额外外交收益",
        "summary": "信使顺路带回额外回礼，让这份约定比预想更热络。",
        "tradeBonus": 1,
        "trustBonus": 1,
        "weight": 2
    }
}
TRIBE_FAR_REPLY_DELAY_MINUTES = 2
TRIBE_FAR_REPLY_ACTIVE_MINUTES = 24
TRIBE_FAR_REPLY_LIMIT = 6
TRIBE_FAR_REPLY_RECENT_LIMIT = 5
TRIBE_FAR_REPLY_ACTIONS = {
    "welcome": {
        "label": "迎回口信",
        "summary": "把远方带回的感谢和故事讲给营火旁的人听。",
        "renown": 2,
        "tradeReputation": 1
    },
    "send_gift": {
        "label": "送出回礼",
        "summary": "拿出少量公共食物作为回礼，让旧约继续升温。",
        "foodCost": 2,
        "renown": 1,
        "relationDelta": 1,
        "tradeTrustDelta": 1
    },
    "clarify": {
        "label": "澄清误会",
        "summary": "公开解释远方回信里的误读，避免口信变成新怨。",
        "renown": 1,
        "relationDelta": 2,
        "warPressureRelief": 1
    },
    "open_trade": {
        "label": "接下新交易",
        "summary": "把回信里的新请求变成下一轮可兑现的互市线索。",
        "tradeReputation": 2,
        "tradeTrustDelta": 1,
        "discoveryProgress": 1
    }
}
TRIBE_FAR_REPLY_OUTCOMES = {
    "messenger": [
        {
            "key": "thanks",
            "label": "感谢回声",
            "summary": "送出的信物被远方公开承认，对方托人带回感谢。",
            "actions": ["welcome", "send_gift"],
            "renownBonus": 1,
            "tradeBonus": 1,
            "weight": 4
        },
        {
            "key": "misread_token",
            "label": "旧痕误读",
            "summary": "有人把旧信物讲成另一种版本，需要营地重新澄清。",
            "actions": ["clarify", "welcome"],
            "relationBonus": -1,
            "weight": 2
        },
        {
            "key": "new_trade",
            "label": "新交易口风",
            "summary": "远方把信物转成新的交换请求，等待部落接话。",
            "actions": ["open_trade", "send_gift"],
            "tradeBonus": 1,
            "weight": 3
        }
    ],
    "visitor": [
        {
            "key": "distant_thanks",
            "label": "旅人谢意",
            "summary": "离开的旅人托路人带回谢意，说营地的接待已经传到远处。",
            "actions": ["welcome", "open_trade"],
            "renownBonus": 1,
            "weight": 4
        },
        {
            "key": "help_request",
            "label": "远方求援",
            "summary": "旅人的旧路上又出现缺粮和迷路者，回信请求部落给出回应。",
            "actions": ["send_gift", "clarify"],
            "discoveryBonus": 1,
            "weight": 2
        },
        {
            "key": "rumor_map",
            "label": "旧图回片",
            "summary": "旅人寄回一片旧图，暗示新的遗迹或边路传闻。",
            "actions": ["open_trade", "welcome"],
            "discoveryBonus": 1,
            "weight": 3
        }
    ],
    "apprentice": [
        {
            "key": "lesson_return",
            "label": "学徒归信",
            "summary": "短期学徒把学到的规矩写成回信，双方都能继续引用这段经历。",
            "actions": ["welcome", "send_gift"],
            "relationBonus": 1,
            "weight": 4
        },
        {
            "key": "custom_request",
            "label": "风俗求问",
            "summary": "对方想继续请教营地风俗，回信可以转成新的信任。",
            "actions": ["welcome", "open_trade"],
            "trustBonus": 1,
            "weight": 3
        },
        {
            "key": "lesson_misread",
            "label": "学法误会",
            "summary": "学徒把一段规矩理解错了，双方需要公开澄清。",
            "actions": ["clarify", "welcome"],
            "relationBonus": -1,
            "weight": 2
        }
    ]
}
TRIBE_PERSONAL_TOKEN_ACTIVE_MINUTES = 45
TRIBE_PERSONAL_TOKEN_LIMIT = 8
TRIBE_PERSONAL_TOKEN_RECENT_LIMIT = 5
TRIBE_PERSONAL_DEBT_LIMIT = 6
TRIBE_PERSONAL_TOKEN_TRUST_REWARD = 1
TRIBE_PERSONAL_TOKEN_DEBT_TRUST_PENALTY = 1
TRIBE_PERSONAL_DEBT_WOOD_COST = 2
TRIBE_PERSONAL_DEBT_FOOD_COST = 1
TRIBE_PERSONAL_TOKEN_OPTIONS = {
    "camp_help": {
        "label": "营地帮手信物",
        "summary": "承诺帮营地补一把手，把私人承诺转成公共贡献。",
        "renown": 1,
        "contribution": 3,
        "wood": 2
    },
    "border_watch": {
        "label": "守边照看信物",
        "summary": "承诺替部落看一段边界，兑现后留下守望名声。",
        "renown": 2,
        "contribution": 2,
        "warPressureRelief": 1
    },
    "story_witness": {
        "label": "见证旧事信物",
        "summary": "承诺把一件旧事讲清楚，兑现后补进部落记忆。",
        "renown": 1,
        "contribution": 1,
        "discoveryProgress": 1
    }
}
TRIBE_RENOWN_PLEDGE_ACTIVE_MINUTES = 20
TRIBE_RENOWN_PLEDGE_LIMIT = 6
TRIBE_RENOWN_PLEDGE_RECENT_LIMIT = 6
TRIBE_RENOWN_PLEDGE_MIN_PERSONAL_RENOWN = 3
TRIBE_RENOWN_PLEDGE_STAKE = 1
TRIBE_RENOWN_PLEDGE_FAILURE_PENALTY = 1
TRIBE_RENOWN_PLEDGE_OPTIONS = {
    "gather": {
        "label": "采集承诺",
        "summary": "把个人名声押在营地补给上，兑现后带回木材与公共贡献。",
        "renown": 1,
        "wood": 5,
        "contribution": 3,
        "personalRenown": 3
    },
    "scout": {
        "label": "探路承诺",
        "summary": "公开承诺去找旧路、风声或遗迹线索，兑现后提高发现进度。",
        "renown": 1,
        "discoveryProgress": 2,
        "personalRenown": 3
    },
    "guard": {
        "label": "守边承诺",
        "summary": "把名声押在守住边界上，兑现后缓解战争压力并增加声望。",
        "renown": 2,
        "warPressureRelief": 1,
        "personalRenown": 3
    },
    "diplomacy": {
        "label": "外交承诺",
        "summary": "承诺把口信讲稳、把礼数做足，兑现后提高贸易信誉。",
        "tradeReputation": 2,
        "renown": 1,
        "personalRenown": 3
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
TRIBE_MUTUAL_AID_ALERT_ACTIVE_MINUTES = 14
TRIBE_MUTUAL_AID_ALERT_LIMIT = 6
TRIBE_MUTUAL_AID_ALERT_PROGRESS_TARGET = 1
TRIBE_MUTUAL_AID_MIN_RELATION = 2
TRIBE_MUTUAL_AID_MIN_TRADE_TRUST = 2
TRIBE_MUTUAL_AID_ALERT_ACTIONS = {
    "rescue_party": {
        "label": "派出救援",
        "summary": "派成员循着火烟赶去帮忙，把危急事件变成可被记住的人情。",
        "responder": {"renown": 3, "tradeReputation": 1, "relationDelta": 1, "tradeTrustDelta": 1},
        "source": {"food": 3, "renown": 1, "relationDelta": 1, "tradeTrustDelta": 1, "pressureRelief": 1}
    },
    "send_supplies": {
        "label": "送出补给",
        "summary": "消耗少量公共食物，把对方最缺的一口气补上。",
        "responder": {"foodCost": 2, "renown": 2, "tradeReputation": 1, "relationDelta": 1, "tradeTrustDelta": 2},
        "source": {"food": 6, "relationDelta": 1, "tradeTrustDelta": 2}
    },
    "night_watch": {
        "label": "守望接应",
        "summary": "在边缘守夜、举火、辨认脚印，降低后续冲突和失踪风险。",
        "responder": {"renown": 2, "discoveryProgress": 1, "relationDelta": 1, "tradeTrustDelta": 1},
        "source": {"renown": 1, "discoveryProgress": 1, "relationDelta": 1, "pressureRelief": 2}
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
TRIBE_BOUNDARY_TEMPERATURE_RECENT_LIMIT = 5
TRIBE_BOUNDARY_TEMPERATURE_ACTIONS = {
    "warm_words": {"label": "温热口风", "summary": "把互市、援助或共同守望讲成热络边界。", "foodCost": 1, "renown": 1, "tradeReputation": 1, "relationDelta": 1, "tradeTrustDelta": 1, "tone": "warm"},
    "clear_suspicion": {"label": "澄清猜疑", "summary": "公开解释边界误会，降低战争压力。", "renown": 2, "relationDelta": 1, "warPressureRelief": 1, "tone": "clear"},
    "awe_watch": {"label": "敬畏守望", "summary": "把守边声望讲成不轻启冲突的威望。", "renown": 2, "relationDelta": -1, "warPressureRelief": 1, "tone": "awe"},
    "cool_mark": {"label": "冷处理", "summary": "把敌意边界暂时降温，避免旧怨立刻滚成新战。", "tradeReputation": 1, "warPressureRelief": 2, "tone": "cool"}
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
TRIBE_BEAST_SPECIALTIES.update({
    "sniffer": {"label": "洞穴嗅探", "taskKey": "sniff", "summary": "洞穴嗅探任务额外推进发现。", "discoveryBonus": 1},
    "omen": {"label": "祭典吉兆", "taskKey": "omen", "summary": "祭典吉兆任务额外带来声望和贸易信誉。", "renownBonus": 2, "tradeBonus": 1}
})
TRIBE_BEAST_TASK_REWARDS.update({
    "sniff": {"label": "洞穴嗅探", "discoveryProgress": 1, "renown": 2, "summary": "幼兽沿着潮湿气味寻找洞口线索，推进部落发现。"},
    "omen": {"label": "祭典吉兆", "renown": 3, "tradeReputation": 1, "summary": "幼兽绕火与图腾巡行，把近期仪式转成公开吉兆。"}
})
TRIBE_BEAST_RITUAL_LINK_LIMIT = 4
TRIBE_BEAST_RITUAL_LINKS = {
    "season:no_hunt": {
        "label": "禁猎护群",
        "summary": "禁猎季让幼兽更会预警和守边。",
        "taskKeys": ["guard", "sniff"],
        "reward": {"renown": 2, "discoveryProgress": 1}
    },
    "season:guard_fire": {
        "label": "护火嗅烟",
        "summary": "护火季让幼兽记住火味，适合守营和祭典吉兆。",
        "taskKeys": ["guard", "omen"],
        "reward": {"renown": 2}
    },
    "season:harvest_dance": {
        "label": "丰收驮运",
        "summary": "丰收舞让幼兽偏向驮运和庆典巡行。",
        "taskKeys": ["haul", "omen"],
        "reward": {"food": 2, "tradeReputation": 1}
    },
    "ritual:totem": {
        "label": "图腾吉兆",
        "summary": "图腾站位后，幼兽的祭典吉兆更容易被族人承认。",
        "taskKeys": ["omen"],
        "reward": {"renown": 4}
    },
    "ritual:cave": {
        "label": "洞口嗅探",
        "summary": "洞口列队后，幼兽更容易记住洞穴气味。",
        "taskKeys": ["sniff"],
        "reward": {"discoveryProgress": 2, "renown": 1}
    },
    "ritual:market": {
        "label": "边市驮运",
        "summary": "边市迎客后，幼兽更适合驮运和辨认互市气味。",
        "taskKeys": ["haul", "omen"],
        "reward": {"tradeReputation": 1, "food": 2}
    },
    "ritual:council": {
        "label": "议场预警",
        "summary": "议场席位让幼兽更会守住营地秩序。",
        "taskKeys": ["guard"],
        "reward": {"renown": 3}
    }
}
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
TRIBE_CAVE_RACE_ACTIVE_MINUTES = 12
TRIBE_CAVE_RACE_RESCUE_MINUTES = 18
TRIBE_CAVE_RACE_LIMIT = 4
TRIBE_CAVE_RACE_DISCOVERY_DEPTH = 6
TRIBE_CAVE_RACE_FIRST_TARGET = 5
TRIBE_CAVE_RACE_RESCUE_TARGET = 2
TRIBE_CAVE_RACE_FIRST_REWARD = {"renown": 8, "discoveryProgress": 2, "tradeReputation": 1}
TRIBE_CAVE_RACE_RESCUE_REWARD = {"renown": 4, "discoveryProgress": 1}
TRIBE_CAVE_RACE_ACTIONS = {
    "first_explore": {
        "key": "first_explore",
        "label": "抢首探",
        "summary": "派出队伍争取短时稀有洞穴的首探，成功会写入世界传闻，失败会留下可营救线索。"
    },
    "rescue": {
        "key": "rescue",
        "label": "循线营救",
        "summary": "沿失踪线索逐步找回队友，完成后获得发现、声望或活地图记忆。"
    }
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
TRIBE_MIGRATION_PLAN_ACTIVE_MINUTES = 16
TRIBE_MIGRATION_PLAN_PROGRESS_TARGET = 3
TRIBE_MIGRATION_PLAN_HISTORY_LIMIT = 5
TRIBE_MIGRATION_PLAN_OPTIONS = {
    "hold_camp": {
        "label": "守旧营",
        "summary": "把迁徙季当成补给窗口，守住旧营火和仓库，整理柴草与食物。",
        "siteLabel": "旧营守火点",
        "siteType": "migration_hold_camp",
        "reward": {"wood": 6, "food": 4, "renown": 4}
    },
    "temporary_camp": {
        "label": "开临时营",
        "summary": "在迁徙路线附近立起短时营点，让成员围绕季节目标和大地馈赠收拢资源。",
        "siteLabel": "迁徙临时营",
        "siteType": "migration_temporary_camp",
        "reward": {"food": 8, "discoveryProgress": 1, "renown": 5}
    },
    "caravan": {
        "label": "迁徙车队",
        "summary": "组织成员沿着兽群和旧路护送物资，把迁徙季变成一次公开远行。",
        "siteLabel": "迁徙车队路线",
        "siteType": "migration_caravan",
        "reward": {"food": 4, "tradeReputation": 1, "discoveryProgress": 1, "renown": 5}
    }
}
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
    "cave_rescue": {"renown": 2, "discoveryProgress": 1},
    "war_aftermath": {"renown": 2},
    "border_market": {"tradeReputation": 1, "renown": 1},
    "oral_epic": {"renown": 2},
    "season_taboo": {"renown": 1, "discoveryProgress": 1},
    "night_trace": {"renown": 1, "discoveryProgress": 1},
    "world_riddle_miss": {"renown": 1, "discoveryProgress": 1}
}
TRIBE_TRAIL_MARKER_ACTIVE_MINUTES = 45
TRIBE_TRAIL_MARKER_LIMIT = 8
TRIBE_TRAIL_MARKER_HISTORY_LIMIT = 8
TRIBE_TRAIL_MARKER_TYPES = {
    "wood_sign": {
        "label": "木牌路标",
        "summary": "在附近插一块木牌，适合标记采集、洞口和回营路线。",
        "woodCost": 1,
        "reward": {"discoveryProgress": 1}
    },
    "stone_cairn": {
        "label": "石堆路标",
        "summary": "堆起石块，让商队、学徒或信使更容易认路。",
        "stoneCost": 1,
        "reward": {"tradeReputation": 1}
    },
    "bone_mark": {
        "label": "骨痕路标",
        "summary": "留下醒目的骨痕警示，适合边界、兽群或冲突后的现场。",
        "foodCost": 1,
        "reward": {"renown": 1}
    }
}
TRIBE_TRAIL_MARKER_ACTIONS = {
    "reinterpret": {
        "label": "修正解释",
        "summary": "把路标重新解释成更清楚的路线说明，增加发现进度。",
        "reward": {"discoveryProgress": 1, "renown": 1}
    },
    "reinforce": {
        "label": "加固",
        "summary": "补木或压石，让路标保留更久并提升贸易信誉。",
        "woodCost": 1,
        "reward": {"tradeReputation": 1, "renown": 1},
        "extendMinutes": 12
    },
    "break": {
        "label": "拆除",
        "summary": "拆掉已经误导族人的路标，回收少量材料并留下改写记录。",
        "reward": {"wood": 1, "renown": 1},
        "resolve": True
    }
}
TRIBE_NEUTRAL_SANCTUARY_ACTIVE_MINUTES = 36
TRIBE_NEUTRAL_SANCTUARY_LIMIT = 3
TRIBE_NEUTRAL_SANCTUARY_USE_TARGET = 3
TRIBE_NEUTRAL_SANCTUARY_RESTORE_TARGET = 3
TRIBE_NEUTRAL_SANCTUARY_BLESSING_MINUTES = 16
TRIBE_NEUTRAL_SANCTUARY_ACTIONS = {
    "pilgrimage": {
        "label": "朝圣",
        "summary": "成员前往中立圣地短暂祈愿，获得发现和声望；连续索取会让圣地沉寂。",
        "reward": {"discoveryProgress": 1, "renown": 1},
        "usePressure": 1,
        "blessingLabel": "朝圣祝福"
    },
    "offering": {
        "label": "献礼",
        "summary": "献上少量公共食物和木材，换取贸易信誉和声望；沉寂圣地会被更快唤回。",
        "foodCost": 1,
        "woodCost": 1,
        "reward": {"tradeReputation": 1, "renown": 1},
        "usePressure": 1,
        "restore": 2,
        "blessingLabel": "献礼祝福"
    },
    "quiet_guard": {
        "label": "守静",
        "summary": "成员在圣地附近守静，缓解战争压力并恢复沉寂进度。",
        "reward": {"renown": 1},
        "pressureRelief": 1,
        "restore": 1,
        "blessingLabel": "守静祝福"
    }
}
TRIBE_OLD_CAMP_ECHO_ACTIVE_MINUTES = 28
TRIBE_OLD_CAMP_ECHO_LIMIT = 3
TRIBE_OLD_CAMP_RECORD_LIMIT = 8
TRIBE_OLD_CAMP_ECHO_ACTIONS = {
    "repair_trace": {
        "label": "修复旧痕",
        "summary": "整理废弃营火、旧战场或旧边市留下的现场，让后来者知道这里发生过什么。",
        "woodCost": 1,
        "reward": {"renown": 2, "discoveryProgress": 1},
        "recordLabel": "修复旧痕"
    },
    "rewrite_story": {
        "label": "补写故事",
        "summary": "把旧营火边没讲完的故事补上，给部落历史留下一段可引用的旧话。",
        "reward": {"renown": 1, "tradeReputation": 1},
        "recordLabel": "补写故事"
    },
    "bring_relic": {
        "label": "带回旧物",
        "summary": "从旧营、旧战场或旧边市带回一件可被收藏墙整理的小物。",
        "foodCost": 1,
        "reward": {"renown": 1, "discoveryProgress": 1},
        "collectionReady": True,
        "recordLabel": "带回旧物"
    }
}
TRIBE_COLLECTION_WALL_LIMIT = 8
TRIBE_COLLECTION_CANDIDATE_LIMIT = 10
TRIBE_COLLECTION_INFLUENCE_LIMIT = 5
TRIBE_COLLECTION_INFLUENCE_MINUTES = 60
TRIBE_COLLECTION_ACTIONS = {
    "old_object": {
        "label": "旧物上墙",
        "summary": "把这段来源整理成营地旧物，强调谁把它带回了火边。",
        "renown": 2,
        "influenceLabel": "旧物传闻",
        "influenceSummary": "后续传闻会更容易引用这件旧物的来历。"
    },
    "rubbing": {
        "label": "拓片整理",
        "summary": "把来源刻成拓片或纹样，方便后来者从中认路。",
        "renown": 1,
        "discoveryProgress": 1,
        "influenceLabel": "拓片线索",
        "influenceSummary": "后续探索、遗迹和路标故事可以引用这份拓片。"
    },
    "mask": {
        "label": "面具陈列",
        "summary": "把来源讲成可展示的面具和仪式故事。",
        "renown": 1,
        "tradeReputation": 1,
        "influenceLabel": "面具口碑",
        "influenceSummary": "后续来访者和边市传闻会记住这面陈列。"
    },
    "token": {
        "label": "信物挂墙",
        "summary": "把信物、回信或承诺挂上收藏墙，给外交和互信留下证据。",
        "tradeReputation": 2,
        "influenceLabel": "信物旧痕",
        "influenceSummary": "后续信使、学徒和人情债故事可以引用这份旧痕。"
    }
}
TRIBE_ECHO_ITEM_LIMIT = 8
TRIBE_ECHO_ITEM_HISTORY_LIMIT = 8
TRIBE_ECHO_ITEM_MEMORY_LIMIT = 5
TRIBE_ECHO_ITEM_TYPES = {
    "torch": {
        "label": "旧火把",
        "summary": "一支适合记录夜路、守望和祭火的火把。",
        "woodCost": 2,
        "originLabel": "火边旧物"
    },
    "stone_axe": {
        "label": "石斧",
        "summary": "一把适合记录采集、修路和守边的石斧。",
        "woodCost": 1,
        "stoneCost": 2,
        "originLabel": "石器旧物"
    },
    "mask": {
        "label": "面具",
        "summary": "一面适合记录讲述、来访和仪式的面具。",
        "woodCost": 1,
        "originLabel": "讲述旧物"
    }
}
TRIBE_ECHO_ITEM_EXPERIENCES = {
    "gather": {"label": "采集经历", "summary": "把一次采集、补给或修造记进物品来历。", "renown": 1, "discoveryProgress": 1},
    "ritual": {"label": "仪式经历", "summary": "把一次祭典、鼓点、导师或庆功记成物品回声。", "renown": 2},
    "border": {"label": "守边经历", "summary": "把一次警戒、停争或边界误判记进物品来历。", "renown": 1, "pressureRelief": 1},
    "trade": {"label": "往来经历", "summary": "把一次来访、信使、互市或远方回信记进物品来历。", "tradeReputation": 1, "renown": 1}
}
TRIBE_REVERSE_VICTORY_RECORD_LIMIT = 8
TRIBE_REVERSE_VICTORY_COOLDOWN_MINUTES = 20
TRIBE_REVERSE_VICTORY_TARGETS = {
    "hold_border": {
        "label": "守住边界",
        "summary": "战争压力或恶劣关系没有变成大战，反而被守望者稳住。",
        "renown": 5,
        "pressureRelief": 1
    },
    "rescue_missing": {
        "label": "救回失踪者",
        "summary": "把洞穴竞速失败留下的失踪线索变成救援荣耀。",
        "renown": 4,
        "discoveryProgress": 1
    },
    "mediate": {
        "label": "成功调停",
        "summary": "在低关系边界里留下可承认的缓和口径。",
        "renown": 3,
        "tradeReputation": 1,
        "relationDelta": 1,
        "tradeTrustDelta": 1
    },
    "preserve_fire": {
        "label": "保存火种",
        "summary": "食物或声望低谷里保住营火，把弱势变成继续生活的荣耀。",
        "renown": 4,
        "food": 3,
        "discoveryProgress": 1
    }
}
TRIBE_MYTH_CLAIM_ACTIVE_MINUTES = 45
TRIBE_MYTH_CLAIM_LIMIT = 6
TRIBE_DOMINANT_MYTH_LIMIT = 5
TRIBE_MYTH_INFLUENCE_TARGET = 3
TRIBE_HISTORY_FACT_ACTIVE_MINUTES = 50
TRIBE_HISTORY_FACT_LIMIT = 6
TRIBE_ACCEPTED_HISTORY_FACT_LIMIT = 5
TRIBE_HISTORY_FACT_INFLUENCE_TARGET = 3
TRIBE_HISTORY_FACT_NEUTRAL_INFLUENCE = 2
TRIBE_HISTORY_FACT_RENOWN = 3
TRIBE_HISTORY_FACT_MEDIATOR_RENOWN = 2
TRIBE_HISTORY_FACT_MEDIATOR_TRADE = 1
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
CELESTIAL_WINDOW_DURATION_MINUTES = 14
CELESTIAL_WINDOW_CHANCE = 0.18
CELESTIAL_WINDOWS = [
    {
        "key": "comet_trail",
        "title": "彗尾横空",
        "summary": "长尾星划过天空，旧路、洞口和未被承认的故事短暂变亮。",
        "branchKeys": ["first_explorer", "mediator", "betrayer"]
    },
    {
        "key": "red_moon",
        "title": "赤月之夜",
        "summary": "月色压低营火，边境誓言、停战说法和暗处承诺都更容易被记住。",
        "branchKeys": ["mediator", "betrayer", "first_explorer"]
    },
    {
        "key": "star_rain",
        "title": "星雨落野",
        "summary": "细碎星光落在不同地貌上，所有部落都能借它写下一次赛季传说。",
        "branchKeys": ["first_explorer", "mediator", "betrayer"]
    }
]
CELESTIAL_BRANCHES = {
    "first_explorer": {
        "label": "观星探路",
        "summary": "把天象解释成远行信号，推进发现，并竞争本次天象的首探者记录。",
        "legendKey": "first_explorer",
        "reward": {"discoveryProgress": 2, "renown": 3},
        "firstReward": {"discoveryProgress": 1, "renown": 2}
    },
    "mediator": {
        "label": "星下调停",
        "summary": "借共同天象缓和边界压力，积累调停者传说。",
        "legendKey": "mediator",
        "reward": {"tradeReputation": 1, "renown": 3},
        "relationDelta": 1,
        "tradeTrustDelta": 1,
        "pressureRelief": 1
    },
    "betrayer": {
        "label": "暗星誓言",
        "summary": "把天象当作隐秘承诺，声望来得快，也会留下背刺者传说的影子。",
        "legendKey": "betrayer",
        "reward": {"renown": 6},
        "relationDelta": -1,
        "warPressure": 1
    }
}
SEASON_LEGEND_TITLES = {
    "first_explorer": {
        "title": "首探者",
        "summary": "最早把本赛季的天象、洞穴或远行线索带回部落的人。",
        "keywords": ["首探", "洞穴", "发现", "观星探路", "迁徙"]
    },
    "mediator": {
        "title": "调停者",
        "summary": "多次把战争、边境或争执转成可以共同承认的说法。",
        "keywords": ["调停", "停战", "议和", "星下调停", "互助"]
    },
    "betrayer": {
        "title": "背刺者",
        "summary": "在盟友、停战或暗处承诺之间留下危险名声。",
        "keywords": ["背刺", "暗星誓言", "追责", "旧怨"]
    }
}
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
TRIBE_SEASON_ATONEMENT_BREAK_THRESHOLD = 2
TRIBE_SEASON_ATONEMENT_TASK_LIMIT = 6
TRIBE_ATONEMENT_TOKEN_LIMIT = 6
TRIBE_ATONEMENT_TOKEN_ACTIVE_MINUTES = 18
TRIBE_SEASON_ATONEMENT_TASKS = {
    "taboo_break": {
        "title": "补火赎罪",
        "summary": "连续破戒让禁忌失去分量，成员可公开补火、赔礼并重新承认季节承诺。",
        "foodCost": 1,
        "woodCost": 2,
        "renownReward": 4,
        "discoveryReward": 1
    },
    "memory": {
        "title": "重访旧痕赎罪",
        "summary": "把破戒、背刺或追责带回活地图旧痕旁重新讲述，修补部落公开记忆。",
        "foodCost": 1,
        "woodCost": 1,
        "renownReward": 3,
        "discoveryReward": 1,
        "tradeReward": 1
    },
    "ritual": {
        "title": "共同仪式赎罪",
        "summary": "借最近的多人站位或祭典余韵公开赔礼，让冲突重新进入共同仪式秩序。",
        "foodCost": 2,
        "woodCost": 1,
        "renownReward": 4,
        "tradeReward": 1
    },
    "betrayal": {
        "title": "赔礼赎罪",
        "summary": "背刺留下了公开裂痕，成员可送出赔礼并重整旧盟友关系。",
        "foodCost": 3,
        "renownReward": 3,
        "tradeReward": 1,
        "relationDelta": 1,
        "tradeTrustDelta": 1,
        "pressureRelief": 1
    },
    "truce_grievance": {
        "title": "停战补誓",
        "summary": "停战追责留下新仇怨，成员可公开补誓，避免旧怨继续滚成大战。",
        "foodCost": 2,
        "woodCost": 1,
        "renownReward": 3,
        "relationDelta": 1,
        "tradeTrustDelta": 1,
        "pressureRelief": 1
    }
}
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
TRIBE_SEASON_TABOO_CONTEXTS = {
    "old_battlefield_no_hunt": {
        "tabooKey": "no_hunt",
        "label": "旧战场禁猎",
        "summary": "族人把旧战场附近暂时让给沉默与巡望，不在血痕未冷处追猎。",
        "memoryKinds": ["war_aftermath"],
        "mythSourceKinds": ["war_aftermath"],
        "sourceKeywords": ["战后", "旧战", "战场", "战争"],
        "observeReward": {"renown": 1},
        "blessing": {"renown": 2, "warPressureRelief": 1},
        "mythSummary": "旧战场禁猎形成祝福后，族人开始争论这究竟是火种护佑、守边誓言还是旧路显现。"
    },
    "border_market_harvest": {
        "tabooKey": "harvest_dance",
        "label": "边市丰收舞",
        "summary": "边市旧痕尚热，成员把丰收舞跳成互市前的欢迎与分食。",
        "memoryKinds": ["border_market"],
        "mythSourceKinds": ["border_market", "trade_route_market"],
        "sourceKeywords": ["边市", "互市", "贸易", "交换"],
        "interpretationKeys": ["trade"],
        "observeReward": {"tradeReputation": 1},
        "blessing": {"food": 3, "tradeReputation": 1},
        "mythSummary": "边市丰收舞让交换与收获绑在一起，族人可以继续争论这是否预示互市佳兆。"
    },
    "ruin_guard_fire": {
        "tabooKey": "guard_fire",
        "label": "遗迹护火",
        "summary": "遗迹、洞口或旧诗旁的火被认真看守，族人相信火光能照出下一段旧路。",
        "memoryKinds": ["cave_first", "oral_epic", "event_trace"],
        "mythSourceKinds": ["world_event", "rare_ruin", "oral_epic"],
        "sourceKeywords": ["遗迹", "稀有遗迹", "洞口", "洞穴", "旧事", "史诗"],
        "interpretationKeys": ["hearth", "trail"],
        "observeReward": {"discoveryProgress": 1},
        "blessing": {"discoveryProgress": 1, "renown": 2},
        "mythSummary": "遗迹护火把火种与旧路连在一起，族人可以把它讲成护佑、显现或守边誓言。"
    }
}
TRIBE_STANDING_RITUAL_ACTIVE_MINUTES = 25
TRIBE_STANDING_RITUAL_MIN_PARTICIPANTS = 2
TRIBE_STANDING_RITUAL_TARGET_PARTICIPANTS = 3
TRIBE_STANDING_RITUAL_HISTORY_LIMIT = 5
TRIBE_STANDING_RITUAL_LANDMARK_RADIUS = 18
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
TRIBE_STANDING_RITUAL_LANDMARK_BONUSES = {
    "totem": {
        "label": "图腾近旁",
        "summary": "靠近本部落图腾或公共图腾站位，额外沉淀共同声望。",
        "reward": {"renown": 2}
    },
    "cave": {
        "label": "洞口列阵",
        "summary": "靠近洞口站位，额外推进洞穴嗅探与发现线索。",
        "reward": {"discoveryProgress": 1, "renown": 1}
    },
    "market": {
        "label": "边市迎线",
        "summary": "靠近开放边市或交换通路站位，额外修复贸易信任。",
        "reward": {"tradeReputation": 1, "food": 1}
    },
    "council": {
        "label": "议场席边",
        "summary": "靠近大议会会场站位，额外巩固外交秩序。",
        "reward": {"tradeReputation": 1, "renown": 1}
    }
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
