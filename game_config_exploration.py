# Exploration, cave, map memory, myth, season, and world library config.

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
TRIBE_CAVE_RACE_RESCUE_TARGET = 3
TRIBE_CAVE_RACE_FIRST_REWARD = {"renown": 8, "discoveryProgress": 2, "tradeReputation": 1}
TRIBE_CAVE_RACE_RESCUE_REWARD = {"renown": 4, "discoveryProgress": 1}
TRIBE_CAVE_RACE_MARK_REWARD = {"renown": 1, "discoveryProgress": 1}
TRIBE_CAVE_RACE_COOP_REWARD = {"renown": 2, "discoveryProgress": 1, "tradeReputation": 1}
TRIBE_CAVE_RACE_RESCUE_RECORD_LIMIT = 6
TRIBE_CAVE_RETURN_MARK_ACTIVE_MINUTES = 22
TRIBE_CAVE_RETURN_MARK_LIMIT = 5
TRIBE_CAVE_RETURN_MARK_TARGET = 2
TRIBE_CAVE_RETURN_MARK_RECORD_LIMIT = 6
TRIBE_CAVE_RACE_RESCUE_METHODS = {
    "echo_locate": {
        "key": "echo_locate",
        "label": "回声定位",
        "summary": "让成员听洞风、兽伴嗅湿痕，沿回声确认队友位置。",
        "animation": "ritual",
        "puzzleChance": 1
    },
    "torch_supply": {
        "key": "torch_supply",
        "label": "火把补给",
        "summary": "用公共木材和食物组织火把补给，圣火与风向预判会降低走偏风险。",
        "woodCost": 1,
        "foodCost": 1,
        "animation": "guard",
        "collectionChance": 1
    },
    "wall_carving": {
        "key": "wall_carving",
        "label": "洞壁刻痕",
        "summary": "沿路标和导师教过的探路记号在洞壁补刻，方便队友按痕迹回撤。",
        "animation": "gather",
        "puzzleChance": 1,
        "collectionChance": 1
    }
}
TRIBE_CAVE_RETURN_MARK_ACTIONS = {
    "tie_echo_rope": {
        "key": "tie_echo_rope",
        "label": "系回声绳",
        "summary": "把救援时听到的回声系成归路线，帮助后来者避开岔洞。",
        "reward": {"discoveryProgress": 1},
        "animation": "ritual"
    },
    "cache_torches": {
        "key": "cache_torches",
        "label": "藏备用火把",
        "summary": "在洞口和弯道藏下备用火把，让队友回撤时不至于摸黑。",
        "reward": {"renown": 1},
        "woodCost": 1,
        "animation": "guard"
    },
    "copy_wall_marks": {
        "key": "copy_wall_marks",
        "label": "抄洞壁刻痕",
        "summary": "把洞壁刻痕抄成可带回营地的路线片段，后续可转成旧物或谜图旁注。",
        "reward": {"discoveryProgress": 1, "renown": 1},
        "collectionReady": 1,
        "puzzleChance": 1,
        "animation": "gather"
    }
}
TRIBE_ORAL_MAP_ACTIVE_MINUTES = 45
TRIBE_ORAL_MAP_SOURCE_LIMIT = 6
TRIBE_ORAL_MAP_RECORD_LIMIT = 6
TRIBE_ORAL_MAP_REFERENCE_LIMIT = 8
TRIBE_ORAL_MAP_LINEAGE_TARGET = 3
TRIBE_ORAL_MAP_LINEAGE_LIMIT = 5
TRIBE_ORAL_MAP_LINEAGE_BONUS_MINUTES = 28
TRIBE_ORAL_MAP_NARRATOR_TARGET = 3
TRIBE_ORAL_MAP_NARRATOR_LIMIT = 6
TRIBE_ORAL_MAP_NARRATOR_ACTIVE_MINUTES = 35
TRIBE_ORAL_MAP_ACTIONS = {
    "cave_route": {
        "key": "cave_route",
        "label": "讲成洞穴归路",
        "summary": "把归路、路标和夜痕讲成下一次洞穴远征能照着走的口述地图。",
        "reward": {"discoveryProgress": 1},
        "findsBonus": 1,
        "foodReduction": 1,
        "animation": "ritual"
    },
    "riddle_route": {
        "key": "riddle_route",
        "label": "讲成石影规律",
        "summary": "把旧痕整理成世界谜语的预测口诀，短时牵引天象或稀有遗迹线索。",
        "reward": {"renown": 1},
        "influenceKind": "rare_ruin",
        "influenceLabel": "口述地图牵引",
        "animation": "ritual"
    },
    "puzzle_route": {
        "key": "puzzle_route",
        "label": "讲成洞纹谜图",
        "summary": "把口述路线抄成洞纹，尝试补入共享谜图的洞穴碎片。",
        "reward": {"discoveryProgress": 1, "renown": 1},
        "puzzleSourceKey": "cave",
        "animation": "gather"
    }
}
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
    },
    "leave_marker": {
        "key": "leave_marker",
        "label": "留竞速路标",
        "summary": "在同一洞穴路线留下本部落记号，其他部落可据此临时合作。",
        "animation": "gather"
    },
    "cooperate": {
        "key": "cooperate",
        "label": "借标合作",
        "summary": "沿其他部落留下的路标互认路线，换取发现、声望和短时信任。",
        "animation": "ritual"
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
TRIBE_MIGRATION_ENCOUNTER_ACTIVE_MINUTES = 18
TRIBE_MIGRATION_ENCOUNTER_LIMIT = 6
TRIBE_MIGRATION_ENCOUNTER_RECORD_LIMIT = 8
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
TRIBE_MIGRATION_ENCOUNTER_ACTIONS = {
    "escort": {
        "label": "护送车队",
        "summary": "派人护送对方迁徙车队穿过边界、旧路或危险路段。",
        "foodCost": 1,
        "responderReward": {"renown": 2, "tradeReputation": 1},
        "sourceReward": {"food": 2, "renown": 1},
        "relationDelta": 2,
        "tradeTrustDelta": 1,
        "tone": "warm"
    },
    "shelter": {
        "label": "收留歇脚",
        "summary": "给车队留一处短时夜火，交换补给、口信和安稳名声。",
        "foodCost": 2,
        "responderReward": {"renown": 2},
        "sourceReward": {"food": 3, "wood": 2},
        "relationDelta": 1,
        "tradeTrustDelta": 1,
        "tone": "shelter"
    },
    "toll": {
        "label": "拦路收费",
        "summary": "在边路索要过路补给，立刻获利但留下紧张口风。",
        "responderReward": {"wood": 3, "stone": 1, "renown": 1},
        "sourceReward": {"discoveryProgress": 1},
        "relationDelta": -2,
        "warPressureDelta": 1,
        "tone": "tense"
    },
    "rumor": {
        "label": "传播路闻",
        "summary": "不直接介入车队，只把他们经过的消息传给商队和边市。",
        "responderReward": {"tradeReputation": 2},
        "sourceReward": {"renown": 1},
        "relationDelta": -1,
        "tone": "rumor"
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
    "world_riddle_miss": {"renown": 1, "discoveryProgress": 1},
    "fog_trail": {"renown": 1, "discoveryProgress": 1}
}
TRIBE_MAP_TILE_TRACE_ACTIVE_MINUTES = 55
TRIBE_MAP_TILE_TRACE_LIMIT = 8
TRIBE_MAP_TILE_TRACE_RESOURCE_COLLECTS = 3
TRIBE_MAP_TILE_TRACE_EFFECT_RADIUS = 42
TRIBE_MAP_TILE_TRACE_REWARDS = {
    "exhausted_grove": {"wood": 1, "renown": 1},
    "old_battlefield": {"renown": 1, "warPressureRelief": 1},
    "safe_cave_path": {"discoveryProgress": 1, "renown": 1},
    "busy_market_site": {"tradeReputation": 1, "renown": 1}
}
TRIBE_MAP_TILE_TRACE_PROFILES = {
    "exhausted_grove": {
        "label": "枯林痕迹",
        "summary": "这里被连续采收，树根和兽道短时间内都记着部落的手脚。",
        "impactLabel": "附近控制资源点产出-1；雨雾更容易把枯枝味推回来。",
        "recoveryHint": "修复林根可逐步降低强度，完全恢复后获得木材和声望。",
        "resourceYieldDelta": -1,
        "eventBiasKeys": ["storm"],
        "weatherBias": ["rain", "fog"]
    },
    "old_battlefield": {
        "label": "旧战场痕迹",
        "summary": "短促冲突把这片地块压成旧战场，后来者可以整理战线和边界口风。",
        "impactLabel": "附近事件更容易偏向风暴和兽群惊动；边界压力在这里更显眼。",
        "recoveryHint": "巡守旧战场可压低强度，并缓和一点战争压力。",
        "eventBiasKeys": ["storm", "herd"],
        "weatherBias": ["fog", "snow"]
    },
    "safe_cave_path": {
        "label": "安全洞路",
        "summary": "营救队把失踪线索理成较稳的洞口归路，后来者还能辨认。",
        "impactLabel": "附近遗迹线索权重提高；晴朗天气更容易露出旧路。",
        "recoveryHint": "献礼洞路可把临时路标沉淀为发现进度。",
        "eventBiasKeys": ["ruin_clue", "rare_ruin"],
        "weatherBias": ["sunny"]
    },
    "busy_market_site": {
        "label": "热闹边市旧址",
        "summary": "边市刚开过，脚印、火灰和口头约定还没有散尽。",
        "impactLabel": "附近事件更容易偏向兽群和商路口风；晴天更适合清点旧约。",
        "recoveryHint": "清理边市旧址可回收贸易信誉和声望。",
        "eventBiasKeys": ["herd"],
        "weatherBias": ["sunny", "fog"]
    }
}
TRIBE_MAP_TILE_TRACE_ACTIONS = {
    "repair": {
        "label": "修复",
        "summary": "补回林根、路面和火灰边缘，让地块痕迹慢慢降温。",
        "traceKinds": ["exhausted_grove"],
        "woodCost": 1,
        "recovery": 2,
        "reward": {"wood": 1, "renown": 1},
        "animation": "gather"
    },
    "patrol": {
        "label": "巡守",
        "summary": "绕旧战场和边界口风巡一圈，把紧张痕迹压回可控范围。",
        "traceKinds": ["old_battlefield"],
        "recovery": 2,
        "reward": {"renown": 1, "warPressureRelief": 1},
        "animation": "guard"
    },
    "offer": {
        "label": "献礼",
        "summary": "给洞口或旧路留下一点食物与标记，让安全路线保留得更清楚。",
        "traceKinds": ["safe_cave_path"],
        "foodCost": 1,
        "recovery": 2,
        "reward": {"discoveryProgress": 1, "renown": 1},
        "animation": "ritual"
    },
    "clean": {
        "label": "清理",
        "summary": "收好旧摊位、火灰和脚印，把边市旧址整理成可再用的口碑。",
        "traceKinds": ["busy_market_site"],
        "recovery": 2,
        "reward": {"tradeReputation": 1, "renown": 1},
        "animation": "gather"
    }
}
TRIBE_PUBLIC_SECRET_ACTIVE_MINUTES = 45
TRIBE_PUBLIC_SECRET_REVEAL_DELAY_MINUTES = 12
TRIBE_PUBLIC_SECRET_LIMIT = 6
TRIBE_PUBLIC_SECRET_RECORD_LIMIT = 8
TRIBE_PUBLIC_SECRET_SOURCES = {
    "ruin_clue": {
        "kind": "cave_wall",
        "label": "洞穴壁画",
        "title": "壁画里的未揭晓秘密",
        "summary": "岩壁上的图案不像单纯记录路线，更像藏着一段还没公开的部落旧事。"
    },
    "rare_ruin": {
        "kind": "traveler_prophecy",
        "label": "旅人预言",
        "title": "遗迹预言的未揭晓秘密",
        "summary": "稀有遗迹的刻痕与旅人口信对上了，成员需要决定这段秘密先给谁看。"
    },
    "storm": {
        "kind": "betrayal_evidence",
        "label": "背刺证据",
        "title": "暴雨冲出的未揭晓秘密",
        "summary": "暴雨把旧脚印和断裂标记冲了出来，像是某次争执里被藏起的证据。"
    },
    "herd": {
        "kind": "traveler_prophecy",
        "label": "旅人预言",
        "title": "兽群带来的未揭晓秘密",
        "summary": "兽群路线和旅人说过的征兆重合，族人还没决定要不要公开这段预言。"
    }
}
TRIBE_PUBLIC_SECRET_ACTIONS = {
    "reveal": {
        "label": "公开",
        "summary": "把秘密公开给全族，立刻换来声望与清晰来源。",
        "reward": {"renown": 2},
        "rumorTone": "公开"
    },
    "hold": {
        "label": "暂存",
        "summary": "先把秘密压进部落记录，等待更合适的解释时机。",
        "reward": {"discoveryProgress": 1},
        "rumorTone": "暂存"
    },
    "judge": {
        "label": "交给裁判",
        "summary": "把秘密整理成可被中立者引用的证据链。",
        "reward": {"renown": 1},
        "judgeReady": True,
        "rumorTone": "待裁判"
    },
    "storyteller": {
        "label": "交给讲述者",
        "summary": "让讲述者先保管秘密，未来可接入口述地图或神话解释。",
        "reward": {"discoveryProgress": 1, "renown": 1},
        "storyReady": True,
        "rumorTone": "讲述者保管"
    }
}
TRIBE_PUBLIC_SECRET_REVEAL_OUTCOMES = {
    "reveal": {
        "label": "公开坐实",
        "summary": "秘密被公开后逐渐坐实，族人更容易把它转成可靠传闻。",
        "reward": {"renown": 1, "tradeReputation": 1},
        "rumorTone": "可信",
        "truthState": "true",
        "followupLabel": "传闻真假"
    },
    "hold": {
        "label": "暂存发酵",
        "summary": "被暂存的秘密没有立刻爆开，而是沉成一条需要再辨认的旧线索。",
        "reward": {"discoveryProgress": 1},
        "rumorTone": "含混",
        "truthState": "uncertain",
        "followupLabel": "传闻真假"
    },
    "judge": {
        "label": "证据链成形",
        "summary": "交给裁判的秘密形成更清楚的证据链，后续中立见证会更有分量。",
        "reward": {"tradeReputation": 1},
        "rumorTone": "待裁",
        "truthState": "uncertain",
        "evidenceChain": True,
        "followupLabel": "共同裁判"
    },
    "storyteller": {
        "label": "讲述伏笔",
        "summary": "讲述者保管的秘密变成后续故事伏笔，可继续牵引口述地图或神话解释。",
        "reward": {"renown": 1, "discoveryProgress": 1},
        "rumorTone": "伏笔",
        "truthState": "uncertain",
        "storyHook": True,
        "followupLabel": "讲述伏笔"
    }
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
TRIBE_LOST_ITEM_ACTIVE_MINUTES = 75
TRIBE_LOST_ITEM_LIMIT = 6
TRIBE_LOST_ITEM_RECORD_LIMIT = 8
TRIBE_LOST_ITEM_SOURCE_SCAN_LIMIT = 18
TRIBE_LOST_ITEM_PROFILES = {
    "disaster": {
        "label": "救灾遗落包",
        "summary": "灾难协作后留下的绳结、干粮袋或半截木牌，仍带着急救时的火灰。",
        "keywords": ["灾", "救灾", "风暴", "互助", "警讯"],
        "reward": {"food": 1, "renown": 1}
    },
    "migration": {
        "label": "迁徙遗落物",
        "summary": "迁徙车队或旧营回声留下的小包裹，里面夹着旧火和路线记号。",
        "keywords": ["迁徙", "车队", "旧营", "迁居"],
        "reward": {"discoveryProgress": 1, "tradeReputation": 1}
    },
    "cave": {
        "label": "洞口失物",
        "summary": "洞穴远征或归路营救后遗落的石片、绳扣和被磨亮的火把柄。",
        "keywords": ["洞穴", "洞口", "远征", "归路", "营救"],
        "reward": {"discoveryProgress": 1, "renown": 1}
    },
    "war": {
        "label": "撤退遗物",
        "summary": "战争、集结或战后修复里掉下的骨牌和破木柄，还带着边界口风。",
        "keywords": ["战争", "撤退", "战后", "集结", "冲突"],
        "reward": {"renown": 1, "warPressureRelief": 1}
    }
}
TRIBE_LOST_ITEM_ACTIONS = {
    "return": {
        "label": "归还",
        "summary": "把失物还给来源方或营地见证者，换取关系、信任和声望。",
        "renown": 2,
        "tradeReputation": 1,
        "relationDelta": 1,
        "tradeTrustDelta": 1
    },
    "collect": {
        "label": "收藏",
        "summary": "把失物挂进收藏墙来源链，换取发现和声望。",
        "renown": 1,
        "discoveryProgress": 1,
        "collectionReady": True
    },
    "dedicate": {
        "label": "献给图腾",
        "summary": "把失物放到图腾或营火旁，让失物变成部落共同记忆。",
        "renown": 3
    },
    "judge": {
        "label": "交给裁判",
        "summary": "把失物交给公共裁判保管，减少边界误会。",
        "tradeReputation": 1,
        "warPressureRelief": 1
    },
    "hide": {
        "label": "私藏",
        "summary": "偷偷留下失物换取一点物资，但会留下名声污点。",
        "food": 1,
        "renownStain": 1
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
TRIBE_BORDER_THEATER_ACTIVE_MINUTES = 26
TRIBE_BORDER_THEATER_LIMIT = 3
TRIBE_BORDER_THEATER_RECORD_LIMIT = 8
TRIBE_BORDER_THEATER_TARGET = 5
TRIBE_BORDER_THEATER_ACTIONS = {
    "contest": {
        "label": "公开比试",
        "summary": "用非致命技艺和胆量争取围观者喝彩，贡献越高越容易压住场面。",
        "score": 2,
        "reward": {"renown": 1},
        "finalReward": {"renown": 2},
        "rumorTone": "awe"
    },
    "story": {
        "label": "讲述旧事",
        "summary": "把部落历史、旧营和边界往来讲成一段能被传唱的说法。",
        "score": 1,
        "reward": {"discoveryProgress": 1, "renown": 1},
        "finalReward": {"discoveryProgress": 1},
        "rumorTone": "remembered"
    },
    "gift": {
        "label": "献礼",
        "summary": "拿出公共食物摆到戏台前，借礼数提高互市信誉和边界信任。",
        "foodCost": 1,
        "score": 1,
        "reward": {"tradeReputation": 1},
        "finalReward": {"tradeReputation": 1},
        "relationDelta": 1,
        "tradeTrustDelta": 1,
        "rumorTone": "warm"
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
TRIBE_SEASON_TABOO_EVIDENCE_LIMIT = 6
TRIBE_SEASON_TABOO_EVIDENCE_ACTIVE_MINUTES = 90
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
        "temptations": [
            {"key": "hunt_fat_beast", "label": "禁猎肥兽", "summary": "趁兽群靠近营地时围猎肥兽，立刻补足肉食。", "reward": {"food": 12}, "evidenceLabel": "肥兽骨堆"},
            {"key": "sell_hide", "label": "私换兽皮", "summary": "把禁猎期兽皮拿去边市换口碑，留下可追问的皮绳。", "reward": {"food": 5, "tradeReputation": 1}, "evidenceLabel": "私换皮绳"}
        ],
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
        "temptations": [
            {"key": "night_emergency_fire", "label": "禁火夜点火", "summary": "夜里强行点明火处理急事，获得木材与发现线索。", "reward": {"wood": 7, "discoveryProgress": 1}, "evidenceLabel": "夜火灰痕"},
            {"key": "strip_firewood", "label": "拆守火木", "summary": "拆走守火架补营地材料，马上补木但火边承诺受损。", "reward": {"wood": 11}, "evidenceLabel": "空火架"}
        ],
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
        "temptations": [
            {"key": "raid_near_harvest", "label": "停舞抢收", "summary": "中断舞步抢收近处资源，营地立刻得到食物和木材。", "reward": {"food": 6, "wood": 6}, "evidenceLabel": "断舞脚印"},
            {"key": "truce_road_grab", "label": "停战抢路", "summary": "借庆典空档抢占近路，换取发现与边界优势；若守边令或禁火令正生效，会同时留下律令补救。", "reward": {"discoveryProgress": 2, "renown": 1}, "evidenceLabel": "抢路木牌", "lawEventKey": "boundary_press"}
        ],
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
        "puzzleSummary": "按提示分站东、南、西三位，图腾影子才会合拢。",
        "reward": {"renown": 4, "wood": 2},
        "fullReward": {"renown": 5}
    },
    "cave": {
        "label": "洞口列队",
        "summary": "成员在洞口前分列，决定是探路、守绳还是携火，为下一次探索积势。",
        "puzzleSummary": "按提示守住北、东、西三位，洞口队列才算排稳。",
        "reward": {"renown": 3, "discoveryProgress": 1},
        "fullReward": {"discoveryProgress": 1, "renown": 3}
    },
    "starwatch": {
        "label": "星下观测",
        "summary": "成员在营地外沿对准星光、风向和旧路记号，给下一次夜行或探索定方位。",
        "puzzleSummary": "按提示分站北、东、南三位，把天气和天象读成同一张方向图。",
        "reward": {"renown": 3, "discoveryProgress": 1},
        "fullReward": {"discoveryProgress": 1, "renown": 4}
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
TRIBE_STANDING_RITUAL_DIRECTIONS = {
    "north": {"label": "北位", "hint": "面向冷风和星影，守住来路。"},
    "east": {"label": "东位", "hint": "面向晨光，最先读到新的迹象。"},
    "south": {"label": "南位", "hint": "面向火光和人声，稳住队列。"},
    "west": {"label": "西位", "hint": "面向余晖和旧痕，收住尾路。"}
}
TRIBE_STANDING_RITUAL_PUZZLE_RADIUS = 22
TRIBE_STANDING_RITUAL_PUZZLES = {
    "totem": {
        "anchorKinds": ["totem"],
        "slots": ["east", "south", "west"],
        "hintLabel": "图腾影子",
        "hintSummary": "看影子绕过图腾的方向：晨光先到东位，火光稳住南位，旧影收在西位。",
        "reward": {"renown": 4}
    },
    "cave": {
        "anchorKinds": ["cave"],
        "slots": ["north", "east", "west"],
        "hintLabel": "洞口风线",
        "hintSummary": "洞口风声会分成三股：北位守绳，东位探路，西位收尾。",
        "reward": {"discoveryProgress": 1, "renown": 3}
    },
    "starwatch": {
        "anchorKinds": ["camp", "totem"],
        "slots": ["north", "east", "south"],
        "hintLabel": "星下方位",
        "hintSummary": "先看北星，再看东边亮光，最后让南位火光把队列接住。",
        "reward": {"discoveryProgress": 1, "renown": 4}
    }
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
