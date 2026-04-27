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
from pathlib import Path
from utils import decode_token
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("game_server")

router = APIRouter()

from game_config import *
from game_world_logic import GameWorldLogicMixin
from game_emergency_choices import GameEmergencyChoiceMixin
from game_mutual_alerts import GameMutualAidAlertMixin
from game_story_events import GameStoryEventsMixin
from game_myths import GameMythMixin
from game_season_taboo import GameSeasonTabooMixin
from game_standing_rituals import GameStandingRitualMixin
from game_beast_links import GameBeastLinkMixin
from game_migration import GameMigrationMixin
from game_celestial import GameCelestialMixin
from game_history_facts import GameHistoryFactMixin
from game_caravans import GameCaravanMixin
from game_cooking import GameCookingMixin
from game_drum_rhythms import GameDrumRhythmMixin
from game_group_emotes import GameGroupEmoteMixin
from game_sacred_fire import GameSacredFireMixin
from game_mentorship import GameMentorshipMixin
from game_celebrations import GameCelebrationMixin
from game_night_risks import GameNightRiskMixin
from game_trade_credit import GameTradeCreditMixin
from game_weather_forecast import GameWeatherForecastMixin
from game_laws import GameLawMixin
from game_shared_puzzles import GameSharedPuzzleMixin
from game_apprentices import GameApprenticeExchangeMixin
from game_messengers import GameMessengerMixin
from game_personal_tokens import GamePersonalTokenMixin
from game_visitors import GameVisitorMixin
from game_far_returns import GameFarReturnMixin
from game_trail_markers import GameTrailMarkerMixin
from game_sanctuaries import GameSanctuaryMixin
from game_collection_wall import GameCollectionWallMixin
from game_renown_pledges import GameRenownPledgeMixin
from game_cave_races import GameCaveRaceMixin
from game_named_landmarks import GameNamedLandmarkMixin
from game_tribe_progression import GameTribeProgressionMixin
from game_conflict import GameConflictMixin

class ConnectionManager(GameConflictMixin, GameEmergencyChoiceMixin, GameMutualAidAlertMixin, GameStoryEventsMixin, GameSeasonTabooMixin, GameStandingRitualMixin, GameBeastLinkMixin, GameMigrationMixin, GameCelestialMixin, GameHistoryFactMixin, GameCaravanMixin, GameCookingMixin, GameDrumRhythmMixin, GameGroupEmoteMixin, GameSacredFireMixin, GameMentorshipMixin, GameCelebrationMixin, GameNightRiskMixin, GameTradeCreditMixin, GameWeatherForecastMixin, GameLawMixin, GameSharedPuzzleMixin, GameApprenticeExchangeMixin, GameMessengerMixin, GamePersonalTokenMixin, GameVisitorMixin, GameFarReturnMixin, GameTrailMarkerMixin, GameSanctuaryMixin, GameCollectionWallMixin, GameRenownPledgeMixin, GameCaveRaceMixin, GameNamedLandmarkMixin, GameMythMixin, GameTribeProgressionMixin, GameWorldLogicMixin):
    def __init__(self):
        # 活跃连接：{player_id: websocket}
        self.active_connections: Dict[str, WebSocket] = {}

        # 玩家数据：{player_id: player_data}
        self.players: Dict[str, dict] = {}
        self.tribes: Dict[str, dict] = {}
        self.player_tribes: Dict[str, str] = {}
        self.tribe_votes: Dict[str, dict] = {}
        self.tribe_trades: Dict[str, dict] = {}
        self.world_rumors: List[dict] = []
        self.season_key = self._current_season_key()
        self.season_started_at = datetime.now().isoformat()
        self.last_settlement: Optional[dict] = None
        self.settlement_history: List[dict] = []
        self._settlement_lock = asyncio.Lock()
        self._load_settlement_history()

        self.current_map_name = "默认地图"
        self.aoi_radius = 60.0

        # 地图数据存储（简单内存存储，实际可用 MongoDB）
        # 约定：地图为全局共享状态，所有在线玩家应看到一致的 decorations。
        default_seed = 20250101
        self.weather_types = list(WEATHER_TYPES)
        self.weather_change_interval = 45.0
        self._weather_task: Optional[asyncio.Task] = None
        self._food_task: Optional[asyncio.Task] = None
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
        self._load_tribe_state()

    def _current_season_key(self) -> str:
        return datetime.now().strftime("%Y-%m")

    def _load_settlement_history(self):
        try:
            if not SEASON_HISTORY_PATH.exists():
                return
            data = json.loads(SEASON_HISTORY_PATH.read_text(encoding="utf-8"))
            history = data.get("settlementHistory", [])
            if isinstance(history, list):
                self.settlement_history = history[-12:]
            last_settlement = data.get("lastSettlement")
            if isinstance(last_settlement, dict):
                self.last_settlement = last_settlement
            elif self.settlement_history:
                self.last_settlement = self.settlement_history[-1]
        except Exception as e:
            logger.error(f"加载赛季结算历史失败: {e}")

    def _save_settlement_history(self):
        try:
            GAME_DATA_DIR.mkdir(parents=True, exist_ok=True)
            payload = {
                "currentSeason": self.season_key,
                "seasonStartedAt": self.season_started_at,
                "lastSettlement": self.last_settlement,
                "settlementHistory": self.settlement_history[-12:],
                "updatedAt": datetime.now().isoformat()
            }
            SEASON_HISTORY_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"保存赛季结算历史失败: {e}")

    def _load_tribe_state(self):
        try:
            if not TRIBE_STATE_PATH.exists():
                return
            data = json.loads(TRIBE_STATE_PATH.read_text(encoding="utf-8"))
            tribes = data.get("tribes", {})
            player_tribes = data.get("playerTribes", {})
            tribe_votes = data.get("tribeVotes", {})
            tribe_trades = data.get("tribeTrades", {})
            world_rumors = data.get("worldRumors", [])
            if isinstance(tribes, dict):
                self.tribes = tribes
                for tribe in self.tribes.values():
                    if not isinstance(tribe, dict):
                        continue
                    tribe.setdefault("members", {})
                    tribe.setdefault("storage", {"wood": 0, "stone": 0})
                    tribe.setdefault("elder_ids", [])
                    tribe.setdefault("vote_cooldowns", {})
                    tribe.setdefault("punish_cooldowns", {})
                    tribe.setdefault("punishments", [])
                    tribe.setdefault("applications", {})
                    tribe.setdefault("ritual", {})
                    tribe.setdefault("runes", [])
                    tribe.setdefault("discoveries", [])
                    tribe.setdefault("discovery_progress", 0)
                    tribe.setdefault("food", 0)
                    tribe.setdefault("last_food_decay_at", datetime.now().isoformat())
                    tribe.setdefault("renown", 0)
                    tribe.setdefault("history", [])
                    tribe.setdefault("ritual_history", [])
                    if not tribe.get("camp"):
                        tribe["camp"] = self._build_tribe_camp(tribe.get("id", self._make_tribe_id()), tribe.get("name", "部落"))
                    self._refresh_tribe_target(tribe)
            if isinstance(player_tribes, dict):
                self.player_tribes = player_tribes
            if isinstance(tribe_votes, dict):
                self.tribe_votes = tribe_votes
            if isinstance(tribe_trades, dict):
                self.tribe_trades = tribe_trades
            if isinstance(world_rumors, list):
                self.world_rumors = [
                    rumor for rumor in world_rumors[-WORLD_RUMOR_LIMIT:]
                    if isinstance(rumor, dict)
                ]
            season_key = data.get("currentSeason")
            if isinstance(season_key, str) and season_key:
                self.season_key = season_key
            season_started_at = data.get("seasonStartedAt")
            if isinstance(season_started_at, str) and season_started_at:
                self.season_started_at = season_started_at
            logger.info(f"已加载部落状态?{len(self.tribes)} 个部落?{len(self.player_tribes)} 名成员映射")
        except Exception as e:
            logger.error(f"加载部落状态失败: {e}")

    def _normalize_loaded_tribe_buildings(self, tribe: dict):
        camp = tribe.get("camp") or {}
        buildings = camp.get("buildings") or []
        if not isinstance(buildings, list):
            camp["buildings"] = []
            tribe["camp"] = camp
            return
        for building in buildings:
            if not isinstance(building, dict):
                continue
            if building.get("key"):
                continue
            building_id = str(building.get("id", ""))
            for layout in TRIBE_CAMP_BUILDING_LAYOUT:
                suffix = f"_{layout['key']}"
                if building_id.endswith(suffix) or building.get("type") == layout.get("type"):
                    building["key"] = layout["key"]
                    break

    def _save_tribe_state(self):
        try:
            GAME_DATA_DIR.mkdir(parents=True, exist_ok=True)
            payload = {
                "currentSeason": self.season_key,
                "seasonStartedAt": self.season_started_at,
                "tribes": self.tribes,
                "playerTribes": self.player_tribes,
                "tribeVotes": self.tribe_votes,
                "tribeTrades": self.tribe_trades,
                "worldRumors": self.world_rumors[-WORLD_RUMOR_LIMIT:],
                "updatedAt": datetime.now().isoformat()
            }
            TRIBE_STATE_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"加载部落状态失败: {e}")

    def get_seasons_summary(self, limit: int = 12) -> dict:
        safe_limit = max(1, min(24, int(limit or 12)))
        history = self.settlement_history[-safe_limit:]
        return {
            "currentSeason": self.season_key,
            "seasonStartedAt": self.season_started_at,
            "lastSettlement": self.last_settlement,
            "settlementHistory": list(reversed(history)),
            "historyCount": len(self.settlement_history)
        }

    def _public_world_rumors(self) -> List[dict]:
        return list(reversed(self.world_rumors[-WORLD_RUMOR_LIMIT:]))

    def _build_world_rumor(self, rumor_type: str, title: str, text: str, related: Optional[dict] = None) -> dict:
        return {
            "id": f"rumor_{int(datetime.now().timestamp() * 1000)}_{random.randint(1000, 9999)}",
            "type": rumor_type,
            "title": title,
            "text": text,
            "createdAt": datetime.now().isoformat(),
            "related": related or {}
        }

    async def _publish_world_rumor(self, rumor_type: str, title: str, text: str, related: Optional[dict] = None):
        rumor = self._build_world_rumor(rumor_type, title, text, related)
        self.world_rumors.append(rumor)
        self.world_rumors = self.world_rumors[-WORLD_RUMOR_LIMIT:]
        self._save_tribe_state()
        await self.broadcast({
            "type": "world_rumor",
            "rumor": rumor,
            "rumors": self._public_world_rumors()
        })

    def get_world_rumors_message(self) -> dict:
        return {
            "type": "world_rumors",
            "rumors": self._public_world_rumors()
        }

    def _build_season_snapshot(self, closed_season: str) -> dict:
        tribes = []
        legend_awards = self._build_season_legend_awards()
        legend_by_tribe: Dict[str, List[dict]] = {}
        for award in legend_awards:
            award_tribe_id = award.get("tribeId")
            if award_tribe_id:
                legend_by_tribe.setdefault(award_tribe_id, []).append(award)
        for tribe in self.tribes.values():
            members = list(tribe.get("members", {}).values())
            total_contribution = sum(int(member.get("contribution", 0) or 0) for member in members)
            storage = tribe.get("storage", {}) or {}
            target = self._build_target_state(tribe)
            top_members = sorted(
                members,
                key=lambda member: int(member.get("contribution", 0) or 0),
                reverse=True
            )[:5]
            tribes.append({
                "id": tribe.get("id"),
                "name": tribe.get("name", "未命名部落"),
                "memberCount": len(members),
                "leaderName": self._public_member(tribe.get("members", {}).get(tribe.get("leader_id"), {})).get("name"),
                "totalContribution": total_contribution,
                "storage": {
                    "wood": int(storage.get("wood", 0) or 0),
                    "stone": int(storage.get("stone", 0) or 0)
                },
                "targetIndex": int(tribe.get("target_index", 0) or 0),
                "targetTitle": target.get("title", "部落目标"),
                "targetCompleted": bool(target.get("completed")),
                "seasonLegendTitles": legend_by_tribe.get(tribe.get("id"), []),
                "topMembers": [self._public_member(member) for member in top_members]
            })

        tribes.sort(key=lambda tribe: tribe.get("totalContribution", 0), reverse=True)
        return {
            "type": "season_settlement",
            "season": closed_season,
            "settledAt": datetime.now().isoformat(),
            "tribeCount": len(tribes),
            "tribes": tribes,
            "topTribes": tribes[:5],
            "legends": legend_awards
        }

    async def ensure_monthly_settlement(self):
        current_key = self._current_season_key()
        if current_key == self.season_key:
            return

        async with self._settlement_lock:
            current_key = self._current_season_key()
            if current_key == self.season_key:
                return

            settlement = self._build_season_snapshot(self.season_key)
            self.last_settlement = settlement
            self.settlement_history.append(settlement)
            self.settlement_history = self.settlement_history[-12:]

            self.tribes.clear()
            self.player_tribes.clear()
            self.tribe_votes.clear()
            self.tribe_trades.clear()
            self.season_key = current_key
            self.season_started_at = datetime.now().isoformat()
            self._save_settlement_history()
            self._save_tribe_state()

            await self.broadcast(settlement)
            top_tribe = settlement.get("topTribes", [None])[0] if settlement.get("topTribes") else None
            if top_tribe:
                await self._publish_world_rumor(
                    "season",
                    "月度冠军",
                    f"{settlement.get('season', '上月')} 结算完成，{top_tribe.get('name', '某个部落')} 以 {top_tribe.get('totalContribution', 0)} 贡献成为月度冠军。",
                    {
                        "season": settlement.get("season"),
                        "tribeId": top_tribe.get("id"),
                        "tribeName": top_tribe.get("name")
                    }
                )
            await self.broadcast({
                "type": "tribe_notice",
                "message": f"{current_key} 新赛季开始：上月部落数据已结算并清空，所有玩家可以重新创建部落。"
            })
            await self.broadcast(self.get_tribes_overview())
            for player_id in list(self.active_connections.keys()):
                await self.send_personal_message(player_id, self.get_player_tribe_state(player_id))
            await self._broadcast_current_map()
            logger.info(f"月度赛季结算完成：{settlement.get('season')} -> {current_key}")

    def _normalize_tribe_name(self, name: str) -> str:
        normalized = (name or "").strip()
        if not normalized:
            return "未命名部落"
        return normalized[:16]

    def _make_tribe_id(self) -> str:
        return f"tribe_{int(datetime.now().timestamp() * 1000)}_{random.randint(1000, 9999)}"

    def _make_vote_id(self) -> str:
        return f"vote_{int(datetime.now().timestamp() * 1000)}_{random.randint(1000, 9999)}"

    def _make_trade_id(self) -> str:
        return f"trade_{int(datetime.now().timestamp() * 1000)}_{random.randint(1000, 9999)}"

    def _make_application_id(self) -> str:
        return f"application_{int(datetime.now().timestamp() * 1000)}_{random.randint(1000, 9999)}"

    def _vote_rule_config(self) -> dict:
        return {
            "leaderMinMembers": TRIBE_LEADER_VOTE_MIN_MEMBERS,
            "elderMinMembers": TRIBE_ELDER_VOTE_MIN_MEMBERS,
            "leaderMinContribution": TRIBE_LEADER_CANDIDATE_MIN_CONTRIBUTION,
            "elderMinContribution": TRIBE_ELDER_CANDIDATE_MIN_CONTRIBUTION,
            "leaderCooldownHours": TRIBE_LEADER_VOTE_COOLDOWN_HOURS,
            "elderCooldownHours": TRIBE_ELDER_VOTE_COOLDOWN_HOURS
        }

    def _vote_min_members(self, role: str) -> int:
        return TRIBE_LEADER_VOTE_MIN_MEMBERS if role == "leader" else TRIBE_ELDER_VOTE_MIN_MEMBERS

    def _vote_min_contribution(self, role: str) -> int:
        return TRIBE_LEADER_CANDIDATE_MIN_CONTRIBUTION if role == "leader" else TRIBE_ELDER_CANDIDATE_MIN_CONTRIBUTION

    def _vote_cooldown_hours(self, role: str) -> int:
        return TRIBE_LEADER_VOTE_COOLDOWN_HOURS if role == "leader" else TRIBE_ELDER_VOTE_COOLDOWN_HOURS

    def _governance_rule_config(self) -> dict:
        return {
            "punishCooldownHours": TRIBE_PUNISH_COOLDOWN_HOURS,
            "punishContributionPenalty": TRIBE_PUNISH_CONTRIBUTION_PENALTY,
            "applicationReviewRoles": ["leader", "elder"],
            "allocationResourceTypes": ["wood", "stone"]
        }

    def _hours_since_iso(self, iso_value: Optional[str]) -> Optional[float]:
        if not iso_value:
            return None
        try:
            return (datetime.now() - datetime.fromisoformat(iso_value)).total_seconds() / 3600
        except (TypeError, ValueError):
            return None

    async def _send_tribe_error(self, player_id: str, message: str):
        await self.send_personal_message(player_id, {
            "type": "tribe_error",
            "message": message
        })

    def _can_govern_member(self, actor: dict, target: dict) -> bool:
        actor_role = actor.get("role", "member")
        target_role = target.get("role", "member")
        if not actor.get("id") or actor.get("id") == target.get("id"):
            return False
        if actor_role == "leader":
            return target_role in {"elder", "member"}
        if actor_role == "elder":
            return target_role == "member"
        return False

    def _can_review_applications(self, member: dict) -> bool:
        return member.get("role") in {"leader", "elder"}

    def _public_application(self, application: dict) -> dict:
        return {
            "id": application.get("id"),
            "playerId": application.get("player_id"),
            "playerName": application.get("player_name", "\u73a9\u5bb6"),
            "message": application.get("message", "想加入部落"),
            "status": application.get("status", "pending"),
            "createdAt": application.get("created_at"),
            "reviewedAt": application.get("reviewed_at"),
            "reviewedBy": application.get("reviewed_by")
        }

    def _build_target_state(self, tribe: dict, target_index: Optional[int] = None) -> dict:
        storage = tribe.get("storage", {})
        if not TRIBE_TARGET_LIBRARY:
            return {}

        if target_index is None:
            target_index = int(tribe.get("target_index", 0) or 0)

        target_index = max(0, min(target_index, len(TRIBE_TARGET_LIBRARY) - 1))
        template = TRIBE_TARGET_LIBRARY[target_index]
        current_wood = int(storage.get("wood", 0) or 0)
        current_stone = int(storage.get("stone", 0) or 0)
        required_wood = int(template.get("wood", 0) or 0)
        required_stone = int(template.get("stone", 0) or 0)
        progress_total = max(1, required_wood + required_stone)
        current_total = min(progress_total, current_wood + current_stone)

        return {
            "index": target_index,
            "title": template.get("title", "部落目标"),
            "summary": template.get("summary", ""),
            "wood": required_wood,
            "stone": required_stone,
            "currentWood": min(required_wood, current_wood),
            "currentStone": min(required_stone, current_stone),
            "progress": current_total,
            "progressTotal": progress_total,
            "completed": current_wood >= required_wood and current_stone >= required_stone,
            "isFinal": target_index >= len(TRIBE_TARGET_LIBRARY) - 1
        }

    async def _notify_tribe(self, tribe_id: str, text: str):
        tribe = self.tribes.get(tribe_id)
        if not tribe or not text:
            return

        for member_id in list(tribe.get("members", {}).keys()):
            await self.send_personal_message(member_id, {
                "type": "tribe_notice",
                "message": text
            })

    def _add_tribe_history(self, tribe: dict, event_type: str, title: str, detail: str = "", actor_id: Optional[str] = None, related: Optional[dict] = None):
        if not tribe:
            return
        history = tribe.setdefault("history", [])
        record = {
            "id": f"history_{int(datetime.now().timestamp() * 1000)}_{len(history)}",
            "type": event_type,
            "title": title,
            "detail": detail,
            "actorId": actor_id,
            "createdAt": datetime.now().isoformat()
        }
        if related:
            record["related"] = related
        history.append(record)
        tribe["history"] = history[-30:]

    def _tribe_renown_state(self, tribe: dict) -> dict:
        renown = int(tribe.get("renown", 0) or 0)
        current = TRIBE_RENOWN_LEVELS[0]
        for level in TRIBE_RENOWN_LEVELS:
            if renown >= int(level.get("min", 0) or 0):
                current = level
        next_value = current.get("next")
        current_min = int(current.get("min", 0) or 0)
        if next_value is None:
            progress = 100
            remaining = 0
        else:
            next_min = int(next_value or current_min)
            span = max(1, next_min - current_min)
            progress = max(0, min(100, round((renown - current_min) * 100 / span)))
            remaining = max(0, next_min - renown)
        return {
            "level": int(current.get("level", 1) or 1),
            "title": current.get("title", "无名营火"),
            "badge": current.get("badge", "新生部落"),
            "current": renown,
            "next": next_value,
            "progress": progress,
            "remaining": remaining
        }

    def _tribe_public_rune_summary(self, tribe: dict) -> dict:
        runes = list(tribe.get("runes", []) or [])
        rune_library = {rune.get("key"): rune for rune in TRIBE_RUNE_LIBRARY + RARE_TRIBE_RUNE_LIBRARY}
        public_runes = [
            {
                "key": rune.get("key"),
                "title": rune.get("title", "未知铭文"),
                "summary": rune.get("summary", ""),
                "effectSummary": rune_library.get(rune.get("key"), {}).get("effectSummary", ""),
                "rare": bool(rune_library.get(rune.get("key"), {}).get("rare")),
                "unlockedAt": rune.get("unlockedAt"),
                "unlockedBy": rune.get("unlockedBy"),
                "unlockedByName": self._get_player_name(rune.get("unlockedBy", "")) if rune.get("unlockedBy") else "未知成员"
            }
            for rune in runes[:8]
            if isinstance(rune, dict)
        ]
        return {
            "count": len(runes),
            "titles": [rune.get("title", "未知铭文") for rune in runes[:4] if isinstance(rune, dict)],
            "runes": public_runes,
            "text": "图腾尚未刻下铭文" if not runes else f"图腾铭文 {len(runes)} 枚：{'、'.join([rune.get('title', '未知铭文') for rune in runes[:3] if isinstance(rune, dict)])}{'…' if len(runes) > 3 else ''}"
        }

    def _refresh_tribe_target(self, tribe: dict):
        if not tribe:
            return
        tribe["target"] = self._build_target_state(tribe)

    def _advance_tribe_target_state(self, tribe: dict) -> bool:
        current_index = int(tribe.get("target_index", 0) or 0)
        if current_index >= len(TRIBE_TARGET_LIBRARY) - 1:
            self._refresh_tribe_target(tribe)
            return False

        tribe["target_index"] = current_index + 1
        self._refresh_tribe_target(tribe)
        return True

    def _tribe_total_contribution(self, tribe: dict) -> int:
        return sum(int(member.get("contribution", 0) or 0) for member in tribe.get("members", {}).values())

    def _has_tribe_structure_type(self, tribe: dict, structure_type: str) -> bool:
        buildings = tribe.get("camp", {}).get("buildings", []) or []
        return any(isinstance(building, dict) and building.get("type") == structure_type for building in buildings)

    def _unlocked_rune_keys(self, tribe: dict) -> Set[str]:
        runes = tribe.get("runes", [])
        if not isinstance(runes, list):
            return set()
        return {rune.get("key") for rune in runes if isinstance(rune, dict) and rune.get("key")}

    def _tribe_rune_effects(self, tribe: dict) -> dict:
        unlocked = self._unlocked_rune_keys(tribe)
        effects = {
            "ritualDurationBonusMinutes": 0,
            "ritualGatherBonus": 0,
            "buildCostDiscountPercent": 0,
            "stoneBuildCostDiscountPercent": 0,
            "caveFindsBonus": 0
        }
        for rune in TRIBE_RUNE_LIBRARY + RARE_TRIBE_RUNE_LIBRARY:
            if rune.get("key") not in unlocked:
                continue
            for key, value in (rune.get("effects") or {}).items():
                effects[key] = int(effects.get(key, 0) or 0) + int(value or 0)
        return effects

    def _tribe_building_cost(self, tribe: dict, layout: dict) -> dict:
        effects = self._tribe_rune_effects(tribe)
        apprentice_discount = self._apprentice_build_discount(tribe) if tribe else 0
        wood_discount = max(0, min(80, int(effects.get("buildCostDiscountPercent", 0) or 0) + apprentice_discount))
        stone_discount = max(0, min(80, wood_discount + int(effects.get("stoneBuildCostDiscountPercent", 0) or 0)))
        base_wood = int(layout.get("wood", 0) or 0)
        base_stone = int(layout.get("stone", 0) or 0)
        return {
            "wood": math.ceil(base_wood * (100 - wood_discount) / 100),
            "stone": math.ceil(base_stone * (100 - stone_discount) / 100),
            "baseWood": base_wood,
            "baseStone": base_stone,
            "woodDiscountPercent": wood_discount,
            "stoneDiscountPercent": stone_discount
        }

    def _rune_requirements_met(self, tribe: dict, rune: dict) -> bool:
        requires = rune.get("requires", {}) or {}
        discovery_key = requires.get("discovery")
        if discovery_key and discovery_key not in (tribe.get("discoveries", []) or []):
            return False
        building_key = requires.get("building")
        if building_key and not self._is_tribe_building_built(tribe, building_key):
            return False
        if int(requires.get("rituals", 0) or 0) > len(tribe.get("ritual_history", []) or []):
            return False
        if int(requires.get("contribution", 0) or 0) > self._tribe_total_contribution(tribe):
            return False
        if int(requires.get("buildings", 0) or 0) > len(tribe.get("camp", {}).get("buildings", []) or []):
            return False
        if int(requires.get("members", 0) or 0) > len(tribe.get("members", {}) or {}):
            return False
        return True

    def _get_tribe_rune_options(self, tribe: dict) -> List[dict]:
        unlocked = self._unlocked_rune_keys(tribe)
        return [
            {
                "key": rune["key"],
                "title": rune["title"],
                "summary": rune["summary"],
                "effectSummary": rune.get("effectSummary", ""),
                "rare": bool(rune.get("rare")),
                "unlocked": rune["key"] in unlocked,
                "available": rune["key"] not in unlocked and self._rune_requirements_met(tribe, rune)
            }
            for rune in TRIBE_RUNE_LIBRARY + RARE_TRIBE_RUNE_LIBRARY
        ]

    def _active_tribe_ritual(self, tribe: dict) -> Optional[dict]:
        ritual = tribe.get("ritual") or {}
        active_until = ritual.get("activeUntil")
        if not active_until:
            return None
        try:
            active_until_dt = datetime.fromisoformat(active_until)
        except (TypeError, ValueError):
            return None
        remaining_seconds = math.ceil((active_until_dt - datetime.now()).total_seconds())
        if remaining_seconds <= 0:
            tribe["ritual"] = {}
            return None
        return {
            "type": ritual.get("type", "harvest"),
            "title": ritual.get("title", "丰收篝火"),
            "gatherBonus": int(ritual.get("gatherBonus", TRIBE_RITUAL_GATHER_BONUS) or 0),
            "renownBonus": int(ritual.get("renownBonus", 0) or 0),
            "activeUntil": active_until,
            "remainingSeconds": remaining_seconds
        }

    def _ritual_config(self, tribe: Optional[dict] = None) -> dict:
        effects = self._tribe_rune_effects(tribe or {})
        duration_bonus = int(effects.get("ritualDurationBonusMinutes", 0) or 0)
        gather_bonus = int(effects.get("ritualGatherBonus", 0) or 0)
        gather_bonus += self._apprentice_ritual_gather_bonus(tribe or {})
        return {
            "wood": TRIBE_RITUAL_WOOD_COST,
            "stone": TRIBE_RITUAL_STONE_COST,
            "durationMinutes": TRIBE_RITUAL_DURATION_MINUTES + duration_bonus,
            "baseDurationMinutes": TRIBE_RITUAL_DURATION_MINUTES,
            "durationBonusMinutes": duration_bonus,
            "gatherBonus": TRIBE_RITUAL_GATHER_BONUS + gather_bonus,
            "baseGatherBonus": TRIBE_RITUAL_GATHER_BONUS,
            "extraGatherBonus": gather_bonus
        }

    def _feast_config(self) -> dict:
        return {
            "food": TRIBE_FEAST_FOOD_COST,
            "durationMinutes": TRIBE_FEAST_DURATION_MINUTES,
            "gatherBonus": TRIBE_FEAST_GATHER_BONUS,
            "renownBonus": TRIBE_FEAST_RENOWN_BONUS
        }

    def _tribe_food_safe_line(self, tribe: dict) -> int:
        safe_line = TRIBE_FOOD_SAFE_BASE
        if self._is_tribe_building_built(tribe, "storage"):
            safe_line += TRIBE_FOOD_SAFE_STORAGE_BONUS
        return safe_line

    def _tribe_food_pressure_state(self, tribe: dict) -> dict:
        food = max(0, int(tribe.get("food", 0) or 0))
        safe_line = self._tribe_food_safe_line(tribe)
        excess = max(0, food - safe_line)
        last_decay_at = tribe.get("last_food_decay_at")
        next_decay_at = None
        if last_decay_at:
            try:
                next_decay_at = datetime.fromtimestamp(
                    datetime.fromisoformat(last_decay_at).timestamp()
                    + TRIBE_FOOD_DECAY_INTERVAL_MINUTES * 60
                ).isoformat()
            except (TypeError, ValueError):
                next_decay_at = None
        return {
            "safeLine": safe_line,
            "baseSafeLine": TRIBE_FOOD_SAFE_BASE,
            "storageBonus": TRIBE_FOOD_SAFE_STORAGE_BONUS if self._is_tribe_building_built(tribe, "storage") else 0,
            "excess": excess,
            "active": excess > 0,
            "decayIntervalMinutes": TRIBE_FOOD_DECAY_INTERVAL_MINUTES,
            "decayPercent": int(TRIBE_FOOD_DECAY_PERCENT * 100),
            "maxDecayPerInterval": TRIBE_FOOD_DECAY_MAX_PER_INTERVAL,
            "lastDecayAt": last_decay_at,
            "nextDecayAt": next_decay_at
        }

    def _apply_tribe_food_decay(self, tribe: dict) -> int:
        now = datetime.now()
        food = max(0, int(tribe.get("food", 0) or 0))
        safe_line = self._tribe_food_safe_line(tribe)
        if food <= safe_line:
            tribe["last_food_decay_at"] = now.isoformat()
            return 0

        last_decay_at = tribe.get("last_food_decay_at")
        try:
            last_decay_dt = datetime.fromisoformat(last_decay_at) if last_decay_at else now
        except (TypeError, ValueError):
            last_decay_dt = now
        interval_seconds = TRIBE_FOOD_DECAY_INTERVAL_MINUTES * 60
        intervals = int((now - last_decay_dt).total_seconds() // interval_seconds)
        if intervals <= 0:
            tribe.setdefault("last_food_decay_at", now.isoformat())
            return 0

        decayed = 0
        for _ in range(min(intervals, 6)):
            excess = max(0, food - safe_line)
            if excess <= 0:
                break
            loss = min(
                excess,
                TRIBE_FOOD_DECAY_MAX_PER_INTERVAL,
                max(1, math.ceil(excess * TRIBE_FOOD_DECAY_PERCENT))
            )
            food -= loss
            decayed += loss

        tribe["food"] = max(0, food)
        tribe["last_food_decay_at"] = now.isoformat()
        if decayed > 0:
            self._add_tribe_history(
                tribe,
                "food",
                "食物缓慢腐坏",
                f"超过安全线的食物自然腐坏 {decayed}，当前安全线 {safe_line}。建成仓库可以提高安全线。"
            )
        return decayed

    def _apply_all_food_decay(self) -> List[str]:
        changed_tribe_ids = []
        for tribe in self.tribes.values():
            decayed = self._apply_tribe_food_decay(tribe)
            if decayed > 0 and tribe.get("id"):
                changed_tribe_ids.append(tribe["id"])
        return changed_tribe_ids

    def _trade_resource_amount(self, tribe: dict, resource: str) -> int:
        if resource == "food":
            return int(tribe.get("food", 0) or 0)
        if resource in {"wood", "stone"}:
            return int((tribe.get("storage", {}) or {}).get(resource, 0) or 0)
        return 0

    def _add_trade_resource(self, tribe: dict, resource: str, amount: int):
        amount = max(0, int(amount or 0))
        if resource == "food":
            tribe["food"] = int(tribe.get("food", 0) or 0) + amount
        elif resource in {"wood", "stone"}:
            storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
            storage[resource] = int(storage.get(resource, 0) or 0) + amount

    def _deduct_trade_resource(self, tribe: dict, resource: str, amount: int) -> bool:
        amount = max(0, int(amount or 0))
        if amount <= 0 or self._trade_resource_amount(tribe, resource) < amount:
            return False
        if resource == "food":
            tribe["food"] = int(tribe.get("food", 0) or 0) - amount
        elif resource in {"wood", "stone"}:
            storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
            storage[resource] = int(storage.get(resource, 0) or 0) - amount
        return True

    def _public_trade(self, trade: dict) -> dict:
        from_tribe_id = trade.get("fromTribeId")
        to_tribe_id = trade.get("toTribeId")
        market_pact = self._market_pact_between(self.tribes.get(from_tribe_id), to_tribe_id)
        trade_credit = self._trade_credit_between(self.tribes.get(from_tribe_id), to_tribe_id)
        saved_credit = trade.get("tradeCredit") if isinstance(trade.get("tradeCredit"), dict) else None
        return {
            "id": trade.get("id"),
            "fromTribeId": from_tribe_id,
            "fromTribeName": trade.get("fromTribeName", "部落"),
            "toTribeId": to_tribe_id,
            "toTribeName": trade.get("toTribeName", "部落"),
            "offer": dict(trade.get("offer", {})),
            "request": dict(trade.get("request", {})),
            "status": trade.get("status", "active"),
            "createdAt": trade.get("createdAt"),
            "resolvedAt": trade.get("resolvedAt"),
            "marketPact": bool(market_pact or trade.get("marketPact")),
            "marketPactTitle": (market_pact or {}).get("title") or trade.get("marketPactTitle"),
            "marketPactActiveUntil": (market_pact or {}).get("activeUntil") or trade.get("marketPactActiveUntil"),
            "marketPactDiscount": int(trade.get("marketPactDiscount", 0) or 0),
            "marketPactReputationBonus": int(trade.get("marketPactReputationBonus", 0) or 0),
            "tradeCredit": self._trade_credit_public_summary(saved_credit or trade_credit),
            "tradeCreditDiscount": int(trade.get("tradeCreditDiscount", 0) or 0),
            "tradeCreditReputationBonus": int((saved_credit or trade_credit or {}).get("reputationBonus", 0) or 0),
            "tradeCreditStockBonus": int((saved_credit or trade_credit or {}).get("stockBonus", 0) or 0),
            "earnedTradeCredit": trade.get("earnedTradeCredit")
        }

    def _active_boundary_pressures(self, tribe: dict) -> List[dict]:
        active = []
        now = datetime.now()
        now_text = now.isoformat()
        for item in tribe.get("boundary_pressures", []) or []:
            if not isinstance(item, dict):
                continue
            active_until = item.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) < now:
                        self._create_boundary_pressure_aftermath(tribe, item, now_text)
                        continue
                except (TypeError, ValueError):
                    pass
            active.append(item)
        if len(active) != len(tribe.get("boundary_pressures", []) or []):
            tribe["boundary_pressures"] = active[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
        return active[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]

    def _active_boundary_truces(self, tribe: dict) -> List[dict]:
        active = []
        now = datetime.now()
        now_text = now.isoformat()
        for item in tribe.get("boundary_truces", []) or []:
            if not isinstance(item, dict):
                continue
            active_until = item.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) < now:
                        continue
                except (TypeError, ValueError):
                    pass
            self._create_boundary_truce_talk_task(tribe, item, now_text)
            active.append(item)
        if len(active) != len(tribe.get("boundary_truces", []) or []):
            tribe["boundary_truces"] = active[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
        return active[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]

    def _active_trade_requests_for_tribe(self, tribe_id: str) -> List[dict]:
        return [
            self._public_trade(trade)
            for trade in self.tribe_trades.values()
            if trade.get("status") == "active"
            and (trade.get("fromTribeId") == tribe_id or trade.get("toTribeId") == tribe_id)
        ][-TRIBE_TRADE_MAX_ACTIVE:]

    def _trade_targets_for_tribe(self, tribe_id: str) -> List[dict]:
        own_tribe = self.tribes.get(tribe_id)
        return [
            {
                "id": tribe.get("id"),
                "name": tribe.get("name", "部落"),
                "tradeReputation": self._trade_reputation_state(tribe),
                "marketPact": bool(self._market_pact_between(own_tribe, tribe.get("id"))),
                "tradeCredit": self._trade_credit_public_summary(self._trade_credit_between(own_tribe, tribe.get("id")))
            }
            for tribe in self.tribes.values()
            if tribe.get("id") and tribe.get("id") != tribe_id
        ]

    def _trade_reputation_state(self, tribe: dict) -> dict:
        completed = max(0, int(tribe.get("trade_reputation", 0) or 0))
        if completed >= 8:
            title = "远近闻名"
            level = 3
            next_target = None
        elif completed >= 4:
            title = "可信伙伴"
            level = 2
            next_target = 8
        elif completed >= 1:
            title = "初有往来"
            level = 1
            next_target = 4
        else:
            title = "尚未建信"
            level = 0
            next_target = 1
        return {
            "completed": completed,
            "level": level,
            "title": title,
            "remaining": max(0, (next_target or completed) - completed) if next_target else 0
        }

    def _beast_growth_state(self, tribe: dict) -> dict:
        experience = max(0, int(tribe.get("beast_experience", 0) or 0))
        level = min(4, experience // TRIBE_BEAST_LEVEL_STEP + 1) if int(tribe.get("tamed_beasts", 0) or 0) > 0 else 0
        titles = {
            0: "尚未驯养",
            1: "初识火光",
            2: "听懂号令",
            3: "熟悉营路",
            4: "部落伙伴"
        }
        next_exp = level * TRIBE_BEAST_LEVEL_STEP if 0 < level < 4 else None
        return {
            "experience": experience,
            "level": level,
            "title": titles.get(level, "部落伙伴"),
            "rewardMultiplier": 1 + max(0, level - 1) * 0.25,
            "specialty": tribe.get("beast_specialty"),
            "specialtyOptions": TRIBE_BEAST_SPECIALTIES if level >= TRIBE_BEAST_SPECIALTY_LEVEL and not tribe.get("beast_specialty") else {},
            "remaining": max(0, (next_exp or experience) - experience) if next_exp else 0
        }

    def _active_celebration_buff(self, tribe: dict) -> Optional[dict]:
        buff = tribe.get("celebration_buff") or {}
        active_until = buff.get("activeUntil") if isinstance(buff, dict) else None
        if not active_until:
            return None
        try:
            if datetime.fromisoformat(active_until) <= datetime.now():
                tribe["celebration_buff"] = None
                return None
        except (TypeError, ValueError):
            tribe["celebration_buff"] = None
            return None
        return buff

    def _celebration_bonus(self, tribe: dict, key: str) -> int:
        buff = self._active_celebration_buff(tribe)
        if not buff:
            return 0
        return max(0, int(buff.get(key, 0) or 0))

    def _tribe_oath(self, tribe: dict) -> Optional[dict]:
        oath = tribe.get("oath") if isinstance(tribe.get("oath"), dict) else None
        if not oath:
            return None
        key = oath.get("key")
        if key not in TRIBE_OATHS:
            return None
        return {**TRIBE_OATHS[key], **oath}

    def _oath_bonus(self, tribe: dict, key: str) -> int:
        oath = self._tribe_oath(tribe)
        if not oath:
            return 0
        oath_key = oath.get("key")
        bonuses = {
            "hearth": {"gatherBonus": 1, "foodBonus": 2},
            "trail": {"caveFindsBonus": 1, "discoveryBonus": 1},
            "trade": {"tradeRenownBonus": 2},
            "beast": {"beastRewardBonus": 1}
        }
        return max(0, int(bonuses.get(oath_key, {}).get(key, 0) or 0))

    def _maybe_create_newcomer_key_moment(self, player_id: str, tribe: dict, member: dict, previous_contribution: int, donated_points: int):
        player = self.players.get(player_id, {})
        if not tribe or not member or donated_points < TRIBE_NEWCOMER_KEY_MIN_DONATION:
            return None
        if previous_contribution > TRIBE_NEWCOMER_KEY_CONTRIBUTION_MAX:
            return None
        if int(player.get("personal_renown", 0) or 0) > PLAYER_NEWCOMER_KEY_RENOWN_MAX:
            return None
        if player.get("newcomer_key_used") or member.get("newcomer_key_used"):
            return None
        moment = dict(random.choice(TRIBE_NEWCOMER_KEY_MOMENTS))
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key in ("wood", "stone"):
            amount = int(moment.get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
        food = int(moment.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
        renown = int(moment.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
        discovery = int(moment.get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
        player["personal_renown"] = int(player.get("personal_renown", 0) or 0) + TRIBE_NEWCOMER_KEY_RENOWN
        player["newcomer_key_used"] = True
        member["newcomer_key_used"] = True
        record = {
            "key": moment.get("key"),
            "label": moment.get("label", "新人关键时刻"),
            "summary": moment.get("summary", ""),
            "personalRenown": TRIBE_NEWCOMER_KEY_RENOWN,
            "createdAt": datetime.now().isoformat()
        }
        member.setdefault("newcomer_moments", []).append(record)
        member["newcomer_moments"] = member["newcomer_moments"][-3:]
        return record

    def _public_member(self, member: dict) -> dict:
        return {
            "id": member.get("id"),
            "name": member.get("name", "玩家"),
            "role": member.get("role", "member"),
            "contribution": member.get("contribution", 0),
            "allocation": dict(member.get("allocation", {"wood": 0, "stone": 0})),
            "newcomerMoments": list(member.get("newcomer_moments", []) or [])[-2:],
            "trustMarks": int(member.get("trust_marks", 0) or 0),
            "renownStains": int(member.get("renown_stains", 0) or 0),
            "punishCount": int(member.get("punish_count", 0) or 0)
        }

    def _public_tribe(self, tribe: dict, include_members: bool = False) -> dict:
        beast_marker = self._tribe_beast_marker(tribe)
        data = {
            "id": tribe.get("id"),
            "name": tribe.get("name"),
            "memberCount": len(tribe.get("members", {})),
            "leaderId": tribe.get("leader_id"),
            "elderIds": list(tribe.get("elder_ids", [])),
            "storage": dict(tribe.get("storage", {})),
            "target": self._build_target_state(tribe),
            "createdAt": tribe.get("created_at"),
            "announcement": tribe.get("announcement", "欢迎来到部落营地。"),
            "announcementUpdatedAt": tribe.get("announcement_updated_at"),
            "announcementUpdatedBy": tribe.get("announcement_updated_by"),
            "camp": tribe.get("camp"),
            "buildOptions": self._get_tribe_build_options(tribe),
            "ritual": self._active_tribe_ritual(tribe),
            "ritualConfig": self._ritual_config(tribe),
            "feastConfig": self._feast_config(),
            "runes": list(tribe.get("runes", [])),
            "runeOptions": self._get_tribe_rune_options(tribe),
            "runeEffects": self._tribe_rune_effects(tribe),
            "publicRuneSummary": self._tribe_public_rune_summary(tribe),
            "discoveries": list(tribe.get("discoveries", [])),
            "discoveryProgress": int(tribe.get("discovery_progress", 0) or 0),
            "ruinClueChain": int(tribe.get("ruin_clue_chain", 0) or 0),
            "ruinClueChainTarget": WORLD_EVENT_RUIN_CHAIN_THRESHOLD,
            "food": int(tribe.get("food", 0) or 0),
            "foodPressure": self._tribe_food_pressure_state(tribe),
            "renown": int(tribe.get("renown", 0) or 0),
            "renownState": self._tribe_renown_state(tribe),
            "tradeReputation": self._trade_reputation_state(tribe),
            "oath": self._tribe_oath(tribe),
            "oathOptions": TRIBE_OATHS if not tribe.get("oath") else {},
            "oathConfig": {"renownBonus": TRIBE_OATH_RENOWN_BONUS},
            "oathTask": self._current_oath_task(tribe),
            "oathTaskStreak": dict(tribe.get("oath_task_streak", {})),
            "celebrationBuff": self._active_celebration_buff(tribe),
            "scoutConfig": {
                "foodCost": TRIBE_SCOUT_FOOD_COST,
                "eventCount": TRIBE_SCOUT_EVENT_COUNT,
                "siteMinutes": TRIBE_SCOUT_SITE_ACTIVE_MINUTES,
                "siteFlagRadius": TRIBE_SCOUT_SITE_FLAG_RADIUS,
                "siteContestRadius": TRIBE_SCOUT_SITE_CONTEST_RADIUS,
                "controlledPatrolMinutes": TRIBE_CONTROLLED_SITE_PATROL_EXTEND_MINUTES,
                "controlledRelayMinutes": TRIBE_CONTROLLED_SITE_RELAY_EXTEND_MINUTES
            },
            "scoutReports": list(tribe.get("scout_reports", []) or [])[-3:],
            "scoutedResourceSites": self._active_scouted_resource_sites(tribe),
            "controlledResourceSites": self._active_controlled_resource_sites(tribe),
            "tradeRouteSites": self._active_trade_route_sites(tribe),
            "caravanRoutes": self._active_caravan_routes(tribe),
            "caravanActions": TRIBE_NOMAD_CARAVAN_ACTIONS,
            "nomadVisitors": self._active_nomad_visitors(tribe),
            "nomadVisitorActions": TRIBE_NOMAD_VISITOR_ACTIONS,
            "nomadVisitorAftereffectActions": TRIBE_NOMAD_VISITOR_AFTEREFFECT_ACTIONS,
            "nomadVisitorAftereffects": self._public_nomad_visitor_aftereffects(tribe),
            "apprenticeExchangeTargets": self._apprentice_exchange_targets(tribe),
            "apprenticeExchangeActions": TRIBE_APPRENTICE_EXCHANGE_ACTIONS,
            "apprenticeExchangeBuffs": self._active_apprentice_buffs(tribe),
            "apprenticeExchangeRecords": list(tribe.get("apprentice_exchanges", []) or [])[-TRIBE_APPRENTICE_EXCHANGE_RECENT_LIMIT:],
            "apprenticeExchangeConfig": {
                "activeMinutes": TRIBE_APPRENTICE_EXCHANGE_ACTIVE_MINUTES,
                "minRelation": TRIBE_APPRENTICE_EXCHANGE_MIN_RELATION,
                "minTradeTrust": TRIBE_APPRENTICE_EXCHANGE_MIN_TRADE_TRUST
            },
            "farReplyTasks": self._public_far_reply_tasks(tribe),
            "farReplyActions": TRIBE_FAR_REPLY_ACTIONS,
            "farReplyRecords": self._recent_far_reply_records(tribe),
            "regionEventBonuses": self._active_region_event_bonus_summaries(tribe),
            "worldEventActions": self._world_event_action_options(tribe),
            "worldEventRemnants": self._active_world_event_remnants(tribe),
            "mapMemories": self._active_map_memories(tribe),
            "caveRaces": self._public_cave_races(tribe),
            "caveRaceActions": TRIBE_CAVE_RACE_ACTIONS,
            "trailMarkers": self._public_trail_markers(tribe),
            "trailMarkerTypes": TRIBE_TRAIL_MARKER_TYPES,
            "trailMarkerActions": self._public_trail_marker_actions(),
            "neutralSanctuaries": self._public_neutral_sanctuaries(tribe),
            "neutralSanctuaryActions": self._public_neutral_sanctuary_actions(),
            "neutralSanctuaryBlessings": self._public_neutral_sanctuary_blessings(tribe),
            "collectionWall": self._public_collection_wall(tribe),
            "collectionCandidates": self._collection_wall_candidates(tribe),
            "collectionActions": TRIBE_COLLECTION_ACTIONS,
            "collectionInfluences": self._active_collection_influences(tribe),
            "mythClaims": self._active_myth_claims(tribe),
            "dominantMyths": self._active_dominant_myths(tribe),
            "historyFactClaims": self._public_history_fact_claims(tribe),
            "acceptedHistoryFacts": self._accepted_history_facts(tribe),
            "emergencyChoice": self._active_emergency_choice(tribe),
            "emergencyChoiceActions": TRIBE_EMERGENCY_CHOICE_ACTIONS,
            "emergencyFollowupTasks": self._public_emergency_followup_tasks(tribe),
            "mutualAidAlerts": self._active_mutual_aid_alerts(tribe),
            "mutualAidSendOptions": self._mutual_aid_send_options(tribe),
            "mutualAidActions": TRIBE_MUTUAL_AID_ALERT_ACTIONS,
            "mutualAidConfig": {
                "activeMinutes": TRIBE_MUTUAL_AID_ALERT_ACTIVE_MINUTES,
                "target": TRIBE_MUTUAL_AID_ALERT_PROGRESS_TARGET,
                "minRelation": TRIBE_MUTUAL_AID_MIN_RELATION,
                "minTradeTrust": TRIBE_MUTUAL_AID_MIN_TRADE_TRUST
            },
            "tamedBeasts": int(tribe.get("tamed_beasts", 0) or 0),
            "beastGrowth": self._beast_growth_state(tribe),
            "beastTaskConfig": TRIBE_BEAST_TASK_REWARDS,
            "beastRitualLinks": self._public_beast_ritual_links(tribe),
            "beastTasks": list(tribe.get("beast_tasks", []) or [])[-3:],
            "activeBeastTask": beast_marker.get("activeTask") if beast_marker else None,
            "seasonChain": {
                "regions": list(tribe.get("season_chain_regions", []) or []),
                "target": SEASON_CHAIN_TARGET,
                "celebrationRenown": SEASON_CELEBRATION_RENOWN_BONUS,
                "celebrationFood": SEASON_CELEBRATION_FOOD_BONUS,
                "pendingCelebration": tribe.get("pending_celebration"),
                "celebrationChoices": SEASON_CELEBRATION_CHOICES
            },
            "seasonTaboo": self._public_season_taboo(tribe),
            "seasonTabooOptions": {} if self._active_season_taboo(tribe) else self._public_season_taboo_options(tribe),
            "seasonTabooConfig": {
                "target": TRIBE_SEASON_TABOO_PROGRESS_TARGET,
                "minutes": TRIBE_SEASON_TABOO_ACTIVE_MINUTES
            },
            "seasonTabooRemedies": self._public_season_taboo_remedies(tribe),
            "atonementTokens": self._public_atonement_tokens(tribe),
            "standingRitual": self._public_standing_ritual(tribe),
            "standingRitualOptions": {} if self._active_standing_ritual(tribe) else TRIBE_STANDING_RITUAL_OPTIONS,
            "standingRitualStances": TRIBE_STANDING_RITUAL_STANCES,
            "standingRitualConfig": {
                "activeMinutes": TRIBE_STANDING_RITUAL_ACTIVE_MINUTES,
                "minParticipants": TRIBE_STANDING_RITUAL_MIN_PARTICIPANTS,
                "target": TRIBE_STANDING_RITUAL_TARGET_PARTICIPANTS,
                "landmarkRadius": TRIBE_STANDING_RITUAL_LANDMARK_RADIUS,
                "landmarkBonuses": TRIBE_STANDING_RITUAL_LANDMARK_BONUSES
            },
            "standingRitualHistory": list(tribe.get("standing_ritual_history", []) or [])[-TRIBE_STANDING_RITUAL_HISTORY_LIMIT:],
            "communalCook": self._public_communal_cook(tribe),
            "communalCookOptions": {} if self._active_communal_cook(tribe) else TRIBE_COMMUNAL_COOK_RECIPES,
            "communalCookIngredients": TRIBE_COMMUNAL_COOK_INGREDIENTS,
            "communalCookConfig": {
                "activeMinutes": TRIBE_COMMUNAL_COOK_ACTIVE_MINUTES,
                "target": TRIBE_COMMUNAL_COOK_TARGET
            },
            "communalCookHistory": list(tribe.get("communal_cook_history", []) or [])[-TRIBE_COMMUNAL_COOK_HISTORY_LIMIT:],
            "drumRhythm": self._public_drum_rhythm(tribe),
            "drumRhythmOptions": {} if self._active_drum_rhythm(tribe) else TRIBE_DRUM_RHYTHM_OPTIONS,
            "drumRhythmBeats": TRIBE_DRUM_RHYTHM_BEATS,
            "drumRhythmConfig": {
                "activeMinutes": TRIBE_DRUM_RHYTHM_ACTIVE_MINUTES,
                "minParticipants": TRIBE_DRUM_RHYTHM_MIN_PARTICIPANTS,
                "target": TRIBE_DRUM_RHYTHM_TARGET_PARTICIPANTS,
                "radius": TRIBE_DRUM_RHYTHM_RADIUS
            },
            "drumRhythmHistory": list(tribe.get("drum_rhythm_history", []) or [])[-TRIBE_DRUM_RHYTHM_HISTORY_LIMIT:],
            "groupEmoteActions": TRIBE_GROUP_EMOTE_ACTIONS,
            "groupEmoteRecords": self._public_group_emote_records(tribe),
            "groupEmoteConfig": {
                "cooldownSeconds": TRIBE_GROUP_EMOTE_COOLDOWN_SECONDS
            },
            "sacredFireRelay": self._public_sacred_fire_relay(tribe),
            "sacredFireDestinations": {} if self._active_sacred_fire_relay(tribe) else TRIBE_SACRED_FIRE_RELAY_DESTINATIONS,
            "sacredFireSteps": TRIBE_SACRED_FIRE_RELAY_STEPS,
            "sacredFireRecords": self._public_sacred_fire_records(tribe),
            "sacredFireConfig": {
                "activeMinutes": TRIBE_SACRED_FIRE_RELAY_ACTIVE_MINUTES,
                "minParticipants": TRIBE_SACRED_FIRE_RELAY_MIN_PARTICIPANTS,
                "target": TRIBE_SACRED_FIRE_RELAY_TARGET_PARTICIPANTS
            },
            "mentorship": self._public_mentorship(tribe),
            "mentorshipFocusOptions": {} if self._active_mentorship(tribe) else TRIBE_MENTORSHIP_FOCUS_OPTIONS,
            "mentorCandidates": self._mentor_candidates(tribe),
            "mentorshipConfig": {
                "activeMinutes": TRIBE_MENTORSHIP_ACTIVE_MINUTES,
                "target": TRIBE_MENTORSHIP_TARGET_STUDENTS,
                "minStudents": TRIBE_MENTORSHIP_MIN_STUDENTS,
                "minPersonalRenown": TRIBE_MENTORSHIP_MIN_PERSONAL_RENOWN,
                "minContribution": TRIBE_MENTORSHIP_MIN_CONTRIBUTION
            },
            "mentorshipHistory": list(tribe.get("mentorship_history", []) or [])[-TRIBE_MENTORSHIP_HISTORY_LIMIT:],
            "celebrationEchoes": self._public_celebration_echoes(tribe),
            "celebrationEchoRecords": list(tribe.get("celebration_echo_records", []) or [])[-TRIBE_CELEBRATION_ECHO_HISTORY_LIMIT:],
            "celebrationEchoConfig": {
                "activeMinutes": TRIBE_CELEBRATION_ECHO_ACTIVE_MINUTES,
                "radius": TRIBE_CELEBRATION_ECHO_RADIUS
            },
            "migrationPlan": self._public_migration_plan(tribe),
            "migrationPlanOptions": self._public_migration_plan_options(tribe),
            "migrationPlanConfig": {
                "activeMinutes": TRIBE_MIGRATION_PLAN_ACTIVE_MINUTES,
                "target": TRIBE_MIGRATION_PLAN_PROGRESS_TARGET
            },
            "migrationPlanHistory": list(tribe.get("migration_plan_history", []) or [])[-TRIBE_MIGRATION_PLAN_HISTORY_LIMIT:],
            "celestialWindow": self._public_celestial_window(tribe),
            "celestialRecords": self._public_celestial_records(tribe),
            "seasonLegendScores": self._public_season_legend_scores(tribe),
            "weatherForecast": self._public_weather_forecast(tribe),
            "weatherForecastSigns": self._public_weather_forecast_signs(),
            "weatherForecastRecords": self._public_weather_forecast_records(tribe),
            "nightOutingStatus": self._public_night_outing_status(tribe),
            "nightOutingOptions": self._public_night_outing_options(tribe),
            "nightOutingRecords": self._public_night_outing_records(tribe),
            "tribeLaw": self._public_tribe_law(tribe),
            "tribeLawOptions": {} if self._active_tribe_law(tribe) else TRIBE_LAW_OPTIONS,
            "tribeLawRemedies": self._public_law_remedies(tribe),
            "tribeLawRecords": self._public_law_records(tribe),
            "sharedPuzzle": self._public_shared_puzzle(tribe),
            "sharedPuzzleOptions": self._public_shared_puzzle_options(tribe),
            "sharedPuzzleRecords": self._public_shared_puzzle_records(tribe),
            "namedLandmarkOptions": self._public_named_landmark_options(tribe),
            "namedLandmarkProposals": self._public_named_landmark_proposals(tribe),
            "namedLandmarks": self._public_named_landmarks(tribe),
            "namedLandmarkConfig": {
                "supportTarget": self._named_landmark_support_target(tribe),
                "nameMin": TRIBE_NAMED_LANDMARK_NAME_MIN,
                "nameMax": TRIBE_NAMED_LANDMARK_NAME_MAX
            },
            "oralChain": self._public_oral_chain(tribe),
            "oralChainConfig": {
                "lineTarget": TRIBE_ORAL_CHAIN_LINE_TARGET,
                "maxLines": TRIBE_ORAL_CHAIN_MAX_LINES,
                "lineRenown": TRIBE_ORAL_CHAIN_LINE_RENOWN,
                "completeRenown": TRIBE_ORAL_CHAIN_COMPLETE_RENOWN
            },
            "oralEpics": list(tribe.get("oral_epics", []) or [])[-3:],
            "oralEpicConfig": {
                "renownBonus": TRIBE_ORAL_EPIC_RENOWN_BONUS,
                "minHistory": TRIBE_ORAL_EPIC_MIN_HISTORY
            },
            "tradeRequests": self._active_trade_requests_for_tribe(tribe.get("id")),
            "marketPacts": self._active_market_pacts(tribe),
            "tradeCreditRecords": [
                self._trade_credit_public_summary(record)
                for record in self._active_trade_credit_records(tribe)
            ],
            "tradeCreditRepairTasks": self._public_trade_credit_repairs(tribe),
            "tradeCreditConfig": self._public_trade_credit_config(),
            "covenantMessengerTasks": self._active_covenant_messenger_tasks(tribe),
            "personalTokenOptions": TRIBE_PERSONAL_TOKEN_OPTIONS,
            "personalTokenTargets": self._personal_token_targets(tribe),
            "personalTokens": self._active_personal_tokens(tribe),
            "personalTokenRecords": self._public_personal_token_records(tribe),
            "personalDebtTasks": self._public_personal_debt_tasks(tribe),
            "renownPledgeOptions": TRIBE_RENOWN_PLEDGE_OPTIONS,
            "renownPledges": self._active_renown_pledges(tribe),
            "renownPledgeRecords": self._public_renown_pledge_records(tribe),
            "renownPledgeConfig": {
                "activeMinutes": TRIBE_RENOWN_PLEDGE_ACTIVE_MINUTES,
                "minPersonalRenown": TRIBE_RENOWN_PLEDGE_MIN_PERSONAL_RENOWN,
                "stake": TRIBE_RENOWN_PLEDGE_STAKE,
                "failurePenalty": TRIBE_RENOWN_PLEDGE_FAILURE_PENALTY
            },
            "boundaryOutcomes": [
                item for item in (tribe.get("boundary_outcomes", []) or [])
                if isinstance(item, dict) and item.get("status") == "pending"
            ],
            "tradeTargets": self._trade_targets_for_tribe(tribe.get("id")),
            "tradeConfig": {
                "resources": ["wood", "stone", "food"],
                "maxAmount": 999,
                "maxActive": TRIBE_TRADE_MAX_ACTIVE
            },
            "territoryFlags": list(tribe.get("territory_flags", []) or []),
            "boundaryRelations": dict(tribe.get("boundary_relations", {}) or {}),
            "boundaryPressures": self._active_boundary_pressures(tribe),
            "boundaryTruces": self._active_boundary_truces(tribe),
            "boundaryFollowupTasks": self._public_boundary_followup_tasks(tribe),
            "diplomacyCouncilSites": self._active_diplomacy_council_sites(tribe),
            "diplomacyCouncilActions": TRIBE_DIPLOMACY_COUNCIL_ACTIONS,
            "personalConflicts": list(tribe.get("personal_conflicts", []) or [])[-5:],
            "smallConflicts": self._public_small_conflicts(tribe),
            "warPressure": self._public_war_pressure(tribe),
            "formalWars": self._public_formal_wars(tribe),
            "warRepairTasks": self._public_war_repair_tasks(tribe),
            "warRevivalTasks": self._public_war_revival_tasks(tribe),
            "warDiplomacyTasks": self._public_war_diplomacy_tasks(tribe),
            "warAftermathTasks": self._public_war_aftermath_tasks(tribe),
            "warAllyRecords": self._public_war_ally_records(tribe),
            "warAllyTasks": self._public_war_ally_tasks(tribe),
            "warInterventionTargets": self._public_war_intervention_targets(tribe),
            "flagPatrolChain": {
                "regions": list(tribe.get("flag_patrol_chain_regions", []) or []),
                "target": TRIBE_FLAG_PATROL_CHAIN_TARGET
            },
            "boundaryActions": TRIBE_BOUNDARY_ACTIONS,
            "flagConfig": {
                "max": TRIBE_FLAG_MAX,
                "woodCost": TRIBE_FLAG_WOOD_COST,
                "stoneCost": TRIBE_FLAG_STONE_COST
            },
            "history": list(tribe.get("history", []))[-TRIBE_HISTORY_PREVIEW_LIMIT:],
            "historyTotal": len(tribe.get("history", []) or []),
            "historyPageSize": TRIBE_HISTORY_PAGE_SIZE,
            "voteRules": self._vote_rule_config(),
            "voteCooldowns": dict(tribe.get("vote_cooldowns", {})),
            "governanceRules": self._governance_rule_config(),
            "pendingApplications": len([
                application
                for application in tribe.get("applications", {}).values()
                if application.get("status") == "pending"
            ]),
            "punishments": list(tribe.get("punishments", []))[-8:]
        }
        if include_members:
            data["members"] = [
                self._public_member(member)
                for member in tribe.get("members", {}).values()
            ]
            data["applications"] = [
                self._public_application(application)
                for application in tribe.get("applications", {}).values()
                if application.get("status") == "pending"
            ]
        return data

    def get_tribe_history_page(self, player_id: str, cursor: int = 0, limit: int = TRIBE_HISTORY_PAGE_SIZE) -> dict:
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            return {
                "type": "tribe_history_page",
                "history": [],
                "cursor": 0,
                "nextCursor": None,
                "total": 0
            }

        history = list(tribe.get("history", []) or [])
        ordered = list(reversed(history))
        safe_cursor = max(0, min(int(cursor or 0), len(ordered)))
        safe_limit = max(1, min(int(limit or TRIBE_HISTORY_PAGE_SIZE), 30))
        page = ordered[safe_cursor:safe_cursor + safe_limit]
        next_cursor = safe_cursor + len(page)
        return {
            "type": "tribe_history_page",
            "history": page,
            "cursor": safe_cursor,
            "nextCursor": next_cursor if next_cursor < len(ordered) else None,
            "total": len(ordered)
        }

    def _get_player_name(self, player_id: str) -> str:
        return self.players.get(player_id, {}).get("name", f"玩家{player_id[:6]}")

    def get_tribes_overview(self) -> dict:
        return {
            "type": "tribe_list",
            "tribes": [self._public_tribe(tribe) for tribe in self.tribes.values()]
        }

    def get_player_tribe_state(self, player_id: str) -> dict:
        tribe_id = self.player_tribes.get(player_id)
        active_votes = []
        if tribe_id:
            active_votes = [
                vote for vote in self.tribe_votes.values()
                if vote.get("tribe_id") == tribe_id and vote.get("status") == "active"
            ]

        if not tribe_id or tribe_id not in self.tribes:
            return {
                "type": "tribe_state",
                "tribe": None,
                "role": None,
                "contribution": 0,
                "votes": active_votes
            }

        tribe = self.tribes[tribe_id]
        member = tribe.get("members", {}).get(player_id, {})
        return {
            "type": "tribe_state",
            "tribe": self._public_tribe(tribe, include_members=True),
            "role": member.get("role", "member"),
            "contribution": member.get("contribution", 0),
            "votes": active_votes
        }

    async def broadcast_tribe_state(self, tribe_id: str):
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            return

        self._apply_tribe_food_decay(tribe)
        self._save_tribe_state()

        for member_id in list(tribe.get("members", {}).keys()):
            await self.send_personal_message(member_id, self.get_player_tribe_state(member_id))

        await self.broadcast(self.get_tribes_overview())
        await self._broadcast_current_map()

    async def create_tribe(self, player_id: str, name: str):
        if player_id in self.player_tribes:
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "你已经属于一个部落"
            })
            return

        tribe_id = self._make_tribe_id()
        member = {
            "id": player_id,
            "name": self._get_player_name(player_id),
            "role": "leader",
            "contribution": 0,
            "allocation": {"wood": 0, "stone": 0},
            "joined_at": datetime.now().isoformat()
        }
        self.tribes[tribe_id] = {
            "id": tribe_id,
            "name": self._normalize_tribe_name(name),
            "leader_id": player_id,
            "elder_ids": [],
            "members": {player_id: member},
            "storage": {"wood": 0, "stone": 0},
            "target_index": 0,
            "target": {},
            "announcement": "欢迎来到部落营地。先采集木材和石块，送进公共仓库。",
            "announcement_updated_at": datetime.now().isoformat(),
            "announcement_updated_by": player_id,
            "vote_cooldowns": {},
            "punish_cooldowns": {},
            "punishments": [],
            "applications": {},
            "ritual": {},
            "runes": [],
            "discoveries": [],
            "discovery_progress": 0,
            "food": 0,
            "last_food_decay_at": datetime.now().isoformat(),
            "renown": 0,
            "history": [],
            "ritual_history": [],
            "created_at": datetime.now().isoformat(),
            "camp": self._build_tribe_camp(tribe_id, self._normalize_tribe_name(name))
        }
        self._refresh_tribe_target(self.tribes[tribe_id])
        self.player_tribes[player_id] = tribe_id
        await self._move_player_to_tribe_spawn(player_id, tribe_id)
        await self.broadcast_tribe_state(tribe_id)

    async def request_join_tribe(self, player_id: str, tribe_id: str, message: str = ""):
        if player_id in self.player_tribes:
            await self._send_tribe_error(player_id, "你已经属于一个部落")
            return

        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "部落不存在")
            return

        applications = tribe.setdefault("applications", {})
        existing = applications.get(player_id)
        if existing and existing.get("status") == "pending":
            await self._send_tribe_error(player_id, "你的加入申请正在等待首领或长老审核")
            return

        application = {
            "id": self._make_application_id(),
            "player_id": player_id,
            "player_name": self._get_player_name(player_id),
            "message": (message or "想加入部落").strip()[:80] or "想加入部落",
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        applications[player_id] = application
        await self.send_personal_message(player_id, {
            "type": "tribe_notice",
            "message": f"已向 {tribe.get('name', '部落')} 提交加入申请"
        })
        await self._notify_tribe(tribe_id, f"{application['player_name']} 申请加入部落，首领或长老可在部落面板审核。")
        self._add_tribe_history(tribe, "application", "收到加入申请", f"{application['player_name']}：{application['message']}", player_id)
        await self.broadcast_tribe_state(tribe_id)

    async def approve_tribe_application(self, actor_id: str, application_id: str, approved: bool):
        tribe_id = self.player_tribes.get(actor_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(actor_id, "请先加入一个部落")
            return

        actor = tribe.get("members", {}).get(actor_id, {})
        if not self._can_review_applications(actor):
            await self._send_tribe_error(actor_id, "只有首领或长老可以审核加入申请")
            return

        application = next((
            item
            for item in tribe.setdefault("applications", {}).values()
            if item.get("id") == application_id and item.get("status") == "pending"
        ), None)
        if not application:
            await self._send_tribe_error(actor_id, "申请不存在或已经处理")
            return

        target_id = application.get("player_id")
        if approved and target_id in self.player_tribes:
            application["status"] = "expired"
            application["reviewed_at"] = datetime.now().isoformat()
            application["reviewed_by"] = actor_id
            await self._send_tribe_error(actor_id, "该玩家已经加入其他部落")
            await self.broadcast_tribe_state(tribe_id)
            return

        application["status"] = "approved" if approved else "rejected"
        application["reviewed_at"] = datetime.now().isoformat()
        application["reviewed_by"] = actor_id

        if approved:
            tribe["members"][target_id] = {
                "id": target_id,
                "name": application.get("player_name") or self._get_player_name(target_id),
                "role": "member",
                "contribution": 0,
                "allocation": {"wood": 0, "stone": 0},
                "joined_at": datetime.now().isoformat()
            }
            self.player_tribes[target_id] = tribe_id
            await self._move_player_to_tribe_spawn(target_id, tribe_id)
            await self.send_personal_message(target_id, self.get_player_tribe_state(target_id))
            self._add_tribe_history(tribe, "application", "成员加入部落", f"{actor.get('name', '管理者')} 通过了 {application.get('player_name', '新成员')} 的申请。", actor_id)
            await self._notify_tribe(tribe_id, f"{application.get('player_name', '新成员')} 已通过审核，加入了部落。")
        else:
            await self.send_personal_message(target_id, {
                "type": "tribe_notice",
                "message": f"你加入 {tribe.get('name', '部落')} 的申请已被拒绝"
            })
            self._add_tribe_history(tribe, "application", "拒绝加入申请", f"{actor.get('name', '管理者')} 拒绝了 {application.get('player_name', '玩家')} 的申请。", actor_id)
            await self._notify_tribe(tribe_id, f"{application.get('player_name', '玩家')} 的加入申请已被拒绝。")

        await self.broadcast_tribe_state(tribe_id)

    async def contribute_to_tribe(self, player_id: str, resources: dict):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "请先加入一个部落"
            })
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        total_points = 0
        for key in ("wood", "stone"):
            try:
                amount = int(resources.get(key, 0))
            except (TypeError, ValueError):
                amount = 0
            amount = max(0, min(999, amount))
            if amount <= 0:
                continue
            storage[key] = storage.get(key, 0) + amount
            total_points += amount

        if total_points <= 0:
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "没有可上交的资源"
            })
            return

        member = tribe["members"].get(player_id)
        newcomer_moment = None
        if member:
            previous_contribution = int(member.get("contribution", 0) or 0)
            member["contribution"] = member.get("contribution", 0) + total_points
            newcomer_moment = self._maybe_create_newcomer_key_moment(
                player_id,
                tribe,
                member,
                previous_contribution,
                total_points
            )

        previous_target = self._build_target_state(tribe)
        self._refresh_tribe_target(tribe)
        current_target = tribe.get("target", {})

        if current_target.get("completed") and not previous_target.get("completed"):
            await self._notify_tribe(
                tribe_id,
                f"部落目标已完成：{current_target.get('title', '当前目标')}。前往石器台即可推进下一阶段。"
            )

        if newcomer_moment:
            player_name = member.get("name", "新人") if member else self._get_player_name(player_id)
            detail = f"{player_name} 触发新人关键时刻“{newcomer_moment.get('label', '新人关键时刻')}”：{newcomer_moment.get('summary', '')} 个人声望 +{TRIBE_NEWCOMER_KEY_RENOWN}。"
            self._add_tribe_history(
                tribe,
                "governance",
                "新人关键时刻",
                detail,
                player_id,
                {"kind": "newcomer_key_moment", **newcomer_moment}
            )
            await self._notify_tribe(tribe_id, detail)
            await self.send_personal_conflict_status(player_id)

        await self.broadcast_tribe_state(tribe_id)

    async def advance_tribe_target(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "请先加入一个部落"
            })
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "只有首领或长老可以推进部落目标"
            })
            return

        current_target = self._build_target_state(tribe)
        if not current_target.get("completed"):
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "当前目标还未完成，继续向仓库补给资源"
            })
            return

        if not self._advance_tribe_target_state(tribe):
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "当前已经是最终阶段目标"
            })
            return

        next_target = tribe.get("target", {})
        await self._notify_tribe(
            tribe_id,
            f"石器台已制定新目标：{next_target.get('title', '新的建设目标')}。"
        )
        await self.broadcast_tribe_state(tribe_id)

    async def build_tribe_structure(self, player_id: str, building_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以发起部落建造")
            return

        layout = self._tribe_building_layout_by_key(building_key)
        if not layout or layout.get("initial"):
            await self._send_tribe_error(player_id, "未知或不可建造的建筑")
            return

        if self._is_tribe_building_built(tribe, building_key):
            await self._send_tribe_error(player_id, "该建筑已经建成")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        cost = self._tribe_building_cost(tribe, layout)
        required_wood = cost["wood"]
        required_stone = cost["stone"]
        if int(storage.get("wood", 0) or 0) < required_wood or int(storage.get("stone", 0) or 0) < required_stone:
            await self._send_tribe_error(player_id, f"公共仓库资源不足：需要木材 {required_wood}、石块 {required_stone}")
            return

        storage["wood"] = int(storage.get("wood", 0) or 0) - required_wood
        storage["stone"] = int(storage.get("stone", 0) or 0) - required_stone
        camp = tribe.setdefault("camp", self._build_tribe_camp(tribe_id, tribe.get("name", "部落")))
        camp.setdefault("buildings", []).append(self._make_tribe_building(tribe, layout))
        self._add_tribe_history(
            tribe,
            "build",
            f"建成{layout.get('label', '建筑')}",
            f"{member.get('name', '管理者')} 消耗木材 {required_wood}、石块 {required_stone} 完成建设。",
            player_id
        )
        discount_text = ""
        if cost["woodDiscountPercent"] or cost["stoneDiscountPercent"]:
            discount_text = f" 图腾铭文节省后消耗木材 {required_wood}、石块 {required_stone}。"
        await self._notify_tribe(tribe_id, f"{member.get('name', '管理者')} 建成了{layout.get('label', '建筑')}。{discount_text}")
        await self.broadcast_tribe_state(tribe_id)

    async def set_tribe_announcement(self, player_id: str, announcement: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以更新部落公告")
            return

        text = (announcement or "").strip()[:120]
        if not text:
            await self._send_tribe_error(player_id, "公告不能为空")
            return

        tribe["announcement"] = text
        tribe["announcement_updated_at"] = datetime.now().isoformat()
        tribe["announcement_updated_by"] = player_id
        self._add_tribe_history(
            tribe,
            "announcement",
            "更新部落公告",
            text,
            player_id,
            {
                "kind": "announcement",
                "text": text,
                "updatedByName": member.get("name", "管理者"),
                "updatedAt": tribe["announcement_updated_at"]
            }
        )
        await self._notify_tribe(tribe_id, f"部落公告已更新：{text}")
        await self.broadcast_tribe_state(tribe_id)

    async def allocate_tribe_resources(self, player_id: str, target_id: str, resources: dict):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        members = tribe.get("members", {})
        actor = members.get(player_id, {})
        target = members.get(target_id)
        if not target:
            await self._send_tribe_error(player_id, "成员不存在")
            return
        if actor.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以预分配公共资源")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        allocation = target.setdefault("allocation", {"wood": 0, "stone": 0})
        assigned = {}
        for key in ("wood", "stone"):
            try:
                amount = int(resources.get(key, 0))
            except (TypeError, ValueError):
                amount = 0
            amount = max(0, min(amount, int(storage.get(key, 0) or 0), 999))
            if amount <= 0:
                continue
            storage[key] = int(storage.get(key, 0) or 0) - amount
            allocation[key] = int(allocation.get(key, 0) or 0) + amount
            assigned[key] = amount

        if not assigned:
            await self._send_tribe_error(player_id, "公共仓库资源不足，无法预分配")
            return

        await self._notify_tribe(
            tribe_id,
            f"{actor.get('name', '管理者')} 已向 {target.get('name', '成员')} 预分配资源：木材 {assigned.get('wood', 0)}，石块 {assigned.get('stone', 0)}。"
        )
        self._add_tribe_history(
            tribe,
            "allocation",
            "预分配公共资源",
            f"{actor.get('name', '管理者')} 向 {target.get('name', '成员')} 分配木材 {assigned.get('wood', 0)}、石块 {assigned.get('stone', 0)}。",
            player_id,
            {
                "kind": "allocation",
                "actorName": actor.get("name", "管理者"),
                "targetName": target.get("name", "成员"),
                "resources": {
                    "wood": assigned.get("wood", 0),
                    "stone": assigned.get("stone", 0)
                },
                "targetAllocation": dict(target.get("allocation", {"wood": 0, "stone": 0})),
                "storageAfter": {
                    "wood": int(storage.get("wood", 0) or 0),
                    "stone": int(storage.get("stone", 0) or 0)
                }
            }
        )
        await self.broadcast_tribe_state(tribe_id)

    async def create_tribe_trade(self, player_id: str, target_tribe_id: str, offer: dict, request: dict):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        target_tribe = self.tribes.get(target_tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not target_tribe or target_tribe_id == tribe_id:
            await self._send_tribe_error(player_id, "贸易目标无效")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以发布贸易请求")
            return

        active_count = len([
            trade for trade in self.tribe_trades.values()
            if trade.get("status") == "active" and trade.get("fromTribeId") == tribe_id
        ])
        if active_count >= TRIBE_TRADE_MAX_ACTIVE:
            await self._send_tribe_error(player_id, f"最多同时发布 {TRIBE_TRADE_MAX_ACTIVE} 条贸易请求")
            return

        offer_resource = (offer or {}).get("resource")
        request_resource = (request or {}).get("resource")
        offer_amount = max(0, min(999, int((offer or {}).get("amount", 0) or 0)))
        request_amount = max(0, min(999, int((request or {}).get("amount", 0) or 0)))
        if offer_resource not in {"wood", "stone", "food"} or request_resource not in {"wood", "stone", "food"}:
            await self._send_tribe_error(player_id, "只能交易木材、石块或食物")
            return
        if offer_amount <= 0 or request_amount <= 0:
            await self._send_tribe_error(player_id, "贸易数量必须大于 0")
            return
        market_pact = self._market_pact_between(tribe, target_tribe_id)
        market_pact_discount = 0
        if market_pact:
            market_pact_discount = min(
                request_amount - 1,
                int(market_pact.get("tradeDiscount", TRIBE_MARKET_PACT_TRADE_DISCOUNT) or 0)
            )
            request_amount = max(1, request_amount - market_pact_discount)
        trade_credit_effect = self._apply_trade_credit_on_create(tribe, target_tribe_id, request_amount)
        trade_credit = trade_credit_effect.get("credit")
        trade_credit_discount = int(trade_credit_effect.get("discount", 0) or 0)
        request_amount = int(trade_credit_effect.get("requestAmount", request_amount) or request_amount)
        if not self._deduct_trade_resource(tribe, offer_resource, offer_amount):
            await self._send_tribe_error(player_id, "部落资源不足，无法托管贸易物资")
            return

        trade_id = self._make_trade_id()
        trade = {
            "id": trade_id,
            "fromTribeId": tribe_id,
            "fromTribeName": tribe.get("name", "部落"),
            "toTribeId": target_tribe_id,
            "toTribeName": target_tribe.get("name", "部落"),
            "offer": {"resource": offer_resource, "amount": offer_amount},
            "request": {"resource": request_resource, "amount": request_amount},
            "status": "active",
            "createdBy": player_id,
            "createdAt": datetime.now().isoformat(),
            "marketPact": bool(market_pact),
            "marketPactTitle": market_pact.get("title") if market_pact else "",
            "marketPactActiveUntil": market_pact.get("activeUntil") if market_pact else None,
            "marketPactDiscount": market_pact_discount,
            "marketPactReputationBonus": int((market_pact or {}).get("tradeReputationBonus", 0) or 0),
            "tradeCredit": self._trade_credit_public_summary(trade_credit),
            "tradeCreditDiscount": trade_credit_discount
        }
        self.tribe_trades[trade_id] = trade
        pact_text = f" 互市约定让请求少要 {market_pact_discount} 份。" if market_pact_discount else ""
        credit_text = f" {trade_credit.get('label', '贸易信用')}让请求少要 {trade_credit_discount} 份。" if trade_credit_discount and trade_credit else ""
        detail = f"{member.get('name', '管理者')} 向 {target_tribe.get('name', '部落')} 发布贸易：出 {offer_amount} {offer_resource}，换 {request_amount} {request_resource}。{pact_text}{credit_text}"
        self._add_tribe_history(tribe, "trade", "发布部落贸易", detail, player_id, {"kind": "trade", **self._public_trade(trade)})
        await self._notify_tribe(target_tribe_id, f"{tribe.get('name', '部落')} 发来贸易请求：出 {offer_amount} {offer_resource}，换 {request_amount} {request_resource}。{pact_text}{credit_text}")
        await self.broadcast_tribe_state(tribe_id)
        await self.broadcast_tribe_state(target_tribe_id)

    async def resolve_tribe_trade(self, player_id: str, trade_id: str, action: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        trade = self.tribe_trades.get(trade_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not trade or trade.get("status") != "active":
            await self._send_tribe_error(player_id, "贸易请求不存在或已结束")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以处理贸易请求")
            return

        from_tribe_id = trade.get("fromTribeId")
        to_tribe_id = trade.get("toTribeId")
        from_tribe = self.tribes.get(from_tribe_id)
        to_tribe = self.tribes.get(to_tribe_id)
        if not from_tribe or not to_tribe:
            trade["status"] = "expired"
            await self._send_tribe_error(player_id, "贸易相关部落不存在")
            return

        action = (action or "").strip()
        if action == "cancel":
            if tribe_id != from_tribe_id:
                await self._send_tribe_error(player_id, "只有发布方可以取消贸易")
                return
            self._add_trade_resource(from_tribe, trade["offer"]["resource"], trade["offer"]["amount"])
            trade["status"] = "cancelled"
            trade["resolvedAt"] = datetime.now().isoformat()
            credit_repair = self._open_trade_credit_repair_task(from_tribe, to_tribe, trade, "cancel", trade["resolvedAt"])
            detail = f"{member.get('name', '管理者')} 取消了对 {trade.get('toTribeName', '部落')} 的贸易请求，托管物资已返还。"
            if credit_repair:
                detail += f" 与 {to_tribe.get('name', '部落')} 的贸易信用需要保证人修复。"
            law_parts = self.apply_tribe_law_violation(from_tribe, player_id, "trade_cancel", "取消贸易")
            if law_parts:
                detail += f" 律令记录：{'、'.join(law_parts)}。"
            self._add_tribe_history(from_tribe, "trade", "取消部落贸易", detail, player_id, {"kind": "trade", **self._public_trade(trade)})
        elif action == "reject":
            if tribe_id != to_tribe_id:
                await self._send_tribe_error(player_id, "只有接收方可以拒绝贸易")
                return
            self._add_trade_resource(from_tribe, trade["offer"]["resource"], trade["offer"]["amount"])
            trade["status"] = "rejected"
            trade["resolvedAt"] = datetime.now().isoformat()
            credit_repair = self._open_trade_credit_repair_task(to_tribe, from_tribe, trade, "reject", trade["resolvedAt"])
            detail = f"{member.get('name', '管理者')} 拒绝了 {trade.get('fromTribeName', '部落')} 的贸易请求，托管物资已返还。"
            if credit_repair:
                detail += f" 与 {from_tribe.get('name', '部落')} 的贸易信用需要补交口信修复。"
            law_parts = self.apply_tribe_law_violation(to_tribe, player_id, "trade_reject", "拒绝贸易")
            if law_parts:
                detail += f" 律令记录：{'、'.join(law_parts)}。"
            self._add_tribe_history(to_tribe, "trade", "拒绝部落贸易", detail, player_id, {"kind": "trade", **self._public_trade(trade)})
            await self._notify_tribe(from_tribe_id, f"{to_tribe.get('name', '部落')} 拒绝了贸易请求，托管物资已返还。")
        elif action == "accept":
            if tribe_id != to_tribe_id:
                await self._send_tribe_error(player_id, "只有接收方可以接受贸易")
                return
            request_resource = trade["request"]["resource"]
            request_amount = int(trade["request"]["amount"] or 0)
            if not self._deduct_trade_resource(to_tribe, request_resource, request_amount):
                await self._send_tribe_error(player_id, "接收方资源不足，无法完成交换")
                return
            self._add_trade_resource(to_tribe, trade["offer"]["resource"], trade["offer"]["amount"])
            self._add_trade_resource(from_tribe, request_resource, request_amount)
            from_tribe["trade_reputation"] = max(0, int(from_tribe.get("trade_reputation", 0) or 0)) + 1
            to_tribe["trade_reputation"] = max(0, int(to_tribe.get("trade_reputation", 0) or 0)) + 1
            from_road_bonus = 1 if self._has_tribe_structure_type(from_tribe, "tribe_road") else 0
            to_road_bonus = 1 if self._has_tribe_structure_type(to_tribe, "tribe_road") else 0
            if from_road_bonus:
                from_tribe["trade_reputation"] += from_road_bonus
            if to_road_bonus:
                to_tribe["trade_reputation"] += to_road_bonus
            from_trade_bonus = int((self._active_celebration_buff(from_tribe) or {}).get("tradeRenownBonus", 0) or 0)
            to_trade_bonus = int((self._active_celebration_buff(to_tribe) or {}).get("tradeRenownBonus", 0) or 0)
            from_apprentice_trade_bonus = self._apprentice_trade_reputation_bonus(from_tribe)
            to_apprentice_trade_bonus = self._apprentice_trade_reputation_bonus(to_tribe)
            if from_apprentice_trade_bonus:
                from_tribe["trade_reputation"] += from_apprentice_trade_bonus
            if to_apprentice_trade_bonus:
                to_tribe["trade_reputation"] += to_apprentice_trade_bonus
            from_law_bonus = self.apply_tribe_law_event_bonus(from_tribe, "trade_accept", "部落贸易")
            to_law_bonus = self.apply_tribe_law_event_bonus(to_tribe, "trade_accept", "部落贸易")
            from_oath_bonus = self._oath_bonus(from_tribe, "tradeRenownBonus")
            to_oath_bonus = self._oath_bonus(to_tribe, "tradeRenownBonus")
            from_tribe["renown"] = max(0, int(from_tribe.get("renown", 0) or 0)) + TRIBE_TRADE_RENOWN_BONUS + from_trade_bonus
            to_tribe["renown"] = max(0, int(to_tribe.get("renown", 0) or 0)) + TRIBE_TRADE_RENOWN_BONUS + to_trade_bonus
            if from_oath_bonus:
                from_tribe["renown"] += from_oath_bonus
            if to_oath_bonus:
                to_tribe["renown"] += to_oath_bonus
            market_pact_bonus = int(trade.get("marketPactReputationBonus", 0) or 0)
            if market_pact_bonus:
                from_tribe["trade_reputation"] += market_pact_bonus
                to_tribe["trade_reputation"] += market_pact_bonus
                from_progress = from_tribe.setdefault("boundary_relations", {}).setdefault(to_tribe_id, {})
                to_progress = to_tribe.setdefault("boundary_relations", {}).setdefault(from_tribe_id, {})
                for progress in (from_progress, to_progress):
                    progress["score"] = max(-9, min(9, int(progress.get("score", 0) or 0) + 1))
                    progress["tradeTrust"] = max(0, min(10, int(progress.get("tradeTrust", 0) or 0) + 1))
                    progress["lastAction"] = "market_pact_trade"
                    progress["lastActionAt"] = datetime.now().isoformat()
            trade_credit_parts = self._apply_trade_credit_on_accept(from_tribe, to_tribe, trade)
            trade["status"] = "accepted"
            trade["resolvedAt"] = datetime.now().isoformat()
            trade_credit_result = self._record_trade_credit_success(from_tribe, to_tribe, trade, trade["resolvedAt"])
            apprentice_detail = ""
            if from_apprentice_trade_bonus or to_apprentice_trade_bonus:
                apprentice_detail = f" 学徒账法让贸易信誉额外 +{from_apprentice_trade_bonus}/{to_apprentice_trade_bonus}。"
            pact_detail = f" 互市约定让双方贸易信誉额外 +{market_pact_bonus}。" if market_pact_bonus else ""
            law_detail = ""
            if from_law_bonus or to_law_bonus:
                law_detail = f" 律令加成：{'; '.join(from_law_bonus + to_law_bonus)}。"
            credit_detail = f" 贸易信用结算：{'、'.join(trade_credit_parts)}。" if trade_credit_parts else ""
            earned_credit = trade_credit_result.get("fromRecord")
            if earned_credit:
                credit_detail += f" 连续守约 {trade_credit_result.get('streak', 0)} 次，形成“{earned_credit.get('label', '贸易信用')}”。"
            detail = f"{member.get('name', '管理者')} 接受了 {trade.get('fromTribeName', '部落')} 的贸易：收到 {trade['offer']['amount']} {trade['offer']['resource']}，交付 {request_amount} {request_resource}。{pact_detail}"
            detail += apprentice_detail
            detail += law_detail
            detail += credit_detail
            self._add_tribe_history(to_tribe, "trade", "接受部落贸易", detail, player_id, {"kind": "trade", **self._public_trade(trade)})
            self._add_tribe_history(from_tribe, "trade", "完成部落贸易", f"{to_tribe.get('name', '部落')} 接受贸易，部落收到 {request_amount} {request_resource}。{pact_detail}{apprentice_detail}{law_detail}{credit_detail}", player_id, {"kind": "trade", **self._public_trade(trade)})
            await self._notify_tribe(from_tribe_id, f"{to_tribe.get('name', '部落')} 接受了贸易请求，交换已完成。")
            await self._publish_world_rumor(
                "trade",
                "贸易完成",
                f"{from_tribe.get('name', '部落')} 与 {to_tribe.get('name', '部落')} 完成资源交换，双方声望 +{TRIBE_TRADE_RENOWN_BONUS}。",
                {
                    "tradeId": trade.get("id"),
                    "fromTribeId": from_tribe_id,
                    "toTribeId": to_tribe_id,
                    "renownBonus": TRIBE_TRADE_RENOWN_BONUS,
                    "fromOathBonus": from_oath_bonus,
                    "toOathBonus": to_oath_bonus,
                    "fromRoadBonus": from_road_bonus,
                    "toRoadBonus": to_road_bonus,
                    "marketPactBonus": market_pact_bonus,
                    "tradeCreditParts": trade_credit_parts,
                    "tradeCreditStreak": trade_credit_result.get("streak", 0),
                    "fromApprenticeTradeBonus": from_apprentice_trade_bonus,
                    "toApprenticeTradeBonus": to_apprentice_trade_bonus,
                    "fromLawBonus": from_law_bonus,
                    "toLawBonus": to_law_bonus,
                    "fromReputation": self._trade_reputation_state(from_tribe),
                    "toReputation": self._trade_reputation_state(to_tribe)
                }
            )
        else:
            await self._send_tribe_error(player_id, "未知贸易操作")
            return

        await self.broadcast_tribe_state(from_tribe_id)
        await self.broadcast_tribe_state(to_tribe_id)

    async def assign_beast_task(self, player_id: str, task_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if int(tribe.get("tamed_beasts", 0) or 0) <= 0:
            await self._send_tribe_error(player_id, "部落还没有驯养幼兽")
            return
        task = TRIBE_BEAST_TASK_REWARDS.get(task_key)
        if not task:
            await self._send_tribe_error(player_id, "未知驯养任务")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        growth = self._beast_growth_state(tribe)
        reward_multiplier = float(growth.get("rewardMultiplier", 1) or 1)
        if self._oath_bonus(tribe, "beastRewardBonus"):
            reward_multiplier += 0.25
        reward_parts = []
        for resource_key, label in (("wood", "木材"), ("stone", "石块")):
            amount = math.floor(int(task.get(resource_key, 0) or 0) * reward_multiplier)
            if amount:
                storage[resource_key] = int(storage.get(resource_key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = math.floor(int(task.get("food", 0) or 0) * reward_multiplier)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        renown = math.floor(int(task.get("renown", 0) or 0) * reward_multiplier)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        discovery = math.floor(int(task.get("discoveryProgress", 0) or 0) * reward_multiplier)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        trade = math.floor(int(task.get("tradeReputation", 0) or 0) * reward_multiplier)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        specialty_key = tribe.get("beast_specialty")
        specialty = TRIBE_BEAST_SPECIALTIES.get(specialty_key)
        if specialty and specialty.get("taskKey") == task_key:
            for resource_key, label in (("woodBonus", "木材"), ("stoneBonus", "石块")):
                amount = int(specialty.get(resource_key, 0) or 0)
                if amount:
                    storage_key = "wood" if resource_key == "woodBonus" else "stone"
                    storage[storage_key] = int(storage.get(storage_key, 0) or 0) + amount
                    reward_parts.append(f"{specialty.get('label')}专长{label}+{amount}")
            food_bonus = int(specialty.get("foodBonus", 0) or 0)
            if food_bonus:
                tribe["food"] = int(tribe.get("food", 0) or 0) + food_bonus
                reward_parts.append(f"{specialty.get('label')}专长食物+{food_bonus}")
            renown_bonus = int(specialty.get("renownBonus", 0) or 0)
            if renown_bonus:
                tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown_bonus
                reward_parts.append(f"{specialty.get('label')}专长声望+{renown_bonus}")
        if specialty and specialty.get("taskKey") == task_key:
            discovery_bonus = int(specialty.get("discoveryBonus", 0) or 0)
            if discovery_bonus:
                tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery_bonus
                reward_parts.append(f"{specialty.get('label')}专长发现+{discovery_bonus}")
            trade_bonus = int(specialty.get("tradeBonus", 0) or 0)
            if trade_bonus:
                tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_bonus
                reward_parts.append(f"{specialty.get('label')}专长贸易信誉+{trade_bonus}")
        link_parts = self._apply_beast_ritual_link_rewards(tribe, task_key)
        reward_parts.extend(link_parts)
        tribe["beast_experience"] = int(tribe.get("beast_experience", 0) or 0) + 1
        new_growth = self._beast_growth_state(tribe)

        member = tribe.get("members", {}).get(player_id, {})
        record = {
            "id": f"beast_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "taskKey": task_key,
            "taskLabel": task.get("label", "驯养任务"),
            "summary": task.get("summary", ""),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "beastLevel": new_growth.get("level", 0),
            "beastTitle": new_growth.get("title", "尚未驯养"),
            "createdAt": datetime.now().isoformat()
        }
        tribe["active_beast_task"] = {
            "taskKey": task_key,
            "taskLabel": record["taskLabel"],
            "memberName": record["memberName"],
            "activeUntil": datetime.fromtimestamp(
                datetime.now().timestamp() + TRIBE_BEAST_TASK_FEEDBACK_SECONDS
            ).isoformat()
        }
        tribe.setdefault("beast_tasks", []).append(record)
        tribe["beast_tasks"] = tribe["beast_tasks"][-8:]
        detail = f"{record['memberName']} 派出驯养幼兽执行{record['taskLabel']}：{record['summary']} {'、'.join(reward_parts)}。幼兽熟练度提升为{record['beastTitle']}。"
        self._add_tribe_history(tribe, "food", "驯养幼兽任务", detail, player_id, {"kind": "beast_task", **record})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_season_objective(self, player_id: str, objective_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        env = self._get_current_environment()
        objective = env.get("seasonObjective") if isinstance(env.get("seasonObjective"), dict) else None
        if not objective or objective.get("id") != objective_id:
            await self._send_tribe_error(player_id, "季节目标已经变化")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward = objective.get("reward") or {}
        reward_parts = []
        for resource_key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(reward.get(resource_key, 0) or 0)
            if amount:
                storage[resource_key] = int(storage.get(resource_key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = int(reward.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        renown = int(reward.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        discovery_buff_bonus = self._celebration_bonus(tribe, "discoveryBonus") + self._oath_bonus(tribe, "discoveryBonus")
        progress = int(reward.get("discoveryProgress", 0) or 0)
        if progress and discovery_buff_bonus:
            progress += discovery_buff_bonus
        if progress:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + progress
            reward_parts.append(f"发现进度+{progress}")

        member = tribe.get("members", {}).get(player_id, {})
        chain_regions = list(tribe.get("season_chain_regions", []) or [])
        region_type = objective.get("regionType")
        if region_type and region_type not in chain_regions:
            chain_regions.append(region_type)
        tribe["season_chain_regions"] = chain_regions[-SEASON_CHAIN_TARGET:]
        celebration_unlocked = len(set(tribe["season_chain_regions"])) >= SEASON_CHAIN_TARGET
        if celebration_unlocked:
            tribe["season_chain_regions"] = []
            tribe["pending_celebration"] = {
                "id": f"celebration_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                "title": "跨区域丰收庆典",
                "summary": "不同地形的季节目标连成庆典，等待部落选择庆典形式。",
                "createdAt": datetime.now().isoformat()
            }
            reward_parts.append("解锁跨区域庆典")
        detail = f"{member.get('name', '成员')} 完成了{objective.get('regionLabel', '未知区域')}的{objective.get('title', '季节目标')}：{'、'.join(reward_parts) or '无直接奖励'}。"
        if celebration_unlocked:
            detail += " 不同地形的季节目标连成庆典，部落举行了跨区域丰收庆祝。"
            await self._publish_world_rumor(
                "season",
                "庆典筹备",
                f"{tribe.get('name', '部落')} 连续完成多地季节目标，正在筹备跨区域庆典。",
                {"tribeId": tribe_id, "pending": True}
            )
        self._add_tribe_history(tribe, "world_event", "完成季节目标", detail, player_id, {"kind": "season_objective", **objective, "rewardParts": reward_parts, "memberName": member.get("name", "成员"), "celebrationUnlocked": celebration_unlocked})
        env["seasonObjective"] = None
        map_data = self.maps.get(self.current_map_name) or {}
        map_data["environment"] = env
        map_data["updated_at"] = datetime.now().isoformat()
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def choose_season_celebration(self, player_id: str, choice_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以决定庆典形式")
            return
        pending = tribe.get("pending_celebration")
        choice = SEASON_CELEBRATION_CHOICES.get(choice_key)
        if not pending:
            await self._send_tribe_error(player_id, "当前没有待举行的庆典")
            return
        if not choice:
            await self._send_tribe_error(player_id, "未知庆典形式")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        for resource_key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(choice.get(resource_key, 0) or 0)
            if amount:
                storage[resource_key] = int(storage.get(resource_key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = int(choice.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        renown = int(choice.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        progress = int(choice.get("discoveryProgress", 0) or 0)
        if progress:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + progress
            reward_parts.append(f"发现进度+{progress}")
        buff_plan = choice.get("buff") or {}
        if buff_plan:
            buff = dict(buff_plan)
            buff["choiceKey"] = choice_key
            buff["activeUntil"] = datetime.fromtimestamp(datetime.now().timestamp() + SEASON_CELEBRATION_BUFF_MINUTES * 60).isoformat()
            tribe["celebration_buff"] = buff
            reward_parts.append(f"{buff.get('title', '庆典余韵')}持续{SEASON_CELEBRATION_BUFF_MINUTES}分钟")
        trade_rep = int(choice.get("tradeReputation", 0) or 0)
        if trade_rep:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_rep
            reward_parts.append(f"贸易信誉+{trade_rep}")

        tribe["pending_celebration"] = None
        record = {
            "kind": "season_celebration",
            "choiceKey": choice_key,
            "choiceLabel": choice.get("label", "庆典"),
            "summary": choice.get("summary", ""),
            "memberName": member.get("name", "管理者"),
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        detail = f"{record['memberName']} 将跨区域庆典办成{record['choiceLabel']}：{record['summary']} {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "ritual", "举行跨区域庆典", detail, player_id, record)
        await self._publish_world_rumor(
            "season",
            f"{record['choiceLabel']}庆典",
            f"{tribe.get('name', '部落')} 举行了{record['choiceLabel']}：{record['summary']}",
            {"tribeId": tribe_id, "choice": choice_key, "rewardParts": reward_parts}
        )
        await self.broadcast_tribe_state(tribe_id)

    async def choose_beast_specialty(self, player_id: str, specialty_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        growth = self._beast_growth_state(tribe)
        if int(growth.get("level", 0) or 0) < TRIBE_BEAST_SPECIALTY_LEVEL:
            await self._send_tribe_error(player_id, f"幼兽需要达到 {TRIBE_BEAST_SPECIALTY_LEVEL} 级才能选择专长")
            return
        if tribe.get("beast_specialty"):
            await self._send_tribe_error(player_id, "幼兽专长已经确定")
            return
        specialty = TRIBE_BEAST_SPECIALTIES.get(specialty_key)
        if not specialty:
            await self._send_tribe_error(player_id, "未知幼兽专长")
            return

        member = tribe.get("members", {}).get(player_id, {})
        tribe["beast_specialty"] = specialty_key
        record = {
            "kind": "beast_specialty",
            "specialtyKey": specialty_key,
            "specialtyLabel": specialty.get("label", "专长"),
            "summary": specialty.get("summary", ""),
            "memberName": member.get("name", "成员"),
            "createdAt": datetime.now().isoformat()
        }
        detail = f"{record['memberName']} 为驯养幼兽选择了{record['specialtyLabel']}专长：{record['summary']}"
        self._add_tribe_history(tribe, "food", "幼兽专长", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def unlock_tribe_rune(self, player_id: str, rune_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以刻写图腾铭文")
            return

        rune = next((item for item in TRIBE_RUNE_LIBRARY + RARE_TRIBE_RUNE_LIBRARY if item.get("key") == rune_key), None)
        if not rune:
            await self._send_tribe_error(player_id, "未知铭文")
            return
        if rune_key in self._unlocked_rune_keys(tribe):
            await self._send_tribe_error(player_id, "该铭文已经刻写")
            return
        if not self._rune_requirements_met(tribe, rune):
            await self._send_tribe_error(player_id, "铭文条件尚未达成")
            return

        record = {
            "key": rune["key"],
            "title": rune["title"],
            "summary": rune["summary"],
            "effectSummary": rune.get("effectSummary", ""),
            "rare": bool(rune.get("rare")),
            "unlockedAt": datetime.now().isoformat(),
            "unlockedBy": player_id,
            "unlockedByName": member.get("name", self._get_player_name(player_id))
        }
        tribe.setdefault("runes", []).append(record)
        self._add_tribe_history(
            tribe,
            "rune",
            f"刻下{rune['title']}",
            rune.get("effectSummary") or rune.get("summary", ""),
            player_id
        )
        notice = f"{member.get('name', '管理者')} 在图腾上刻下了{rune['title']}。"
        if rune.get("rare"):
            notice = f"稀有铭文觉醒：{notice} 图腾回响在整个营地扩散。"
        for member_id in list(tribe.get("members", {}).keys()):
            await self.send_personal_message(member_id, {
                "type": "tribe_rune_unlocked",
                "message": notice,
                "rune": record
            })
        await self.broadcast_tribe_state(tribe_id)

    async def start_tribe_ritual(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以点燃部落仪式")
            return

        if not self._is_tribe_building_built(tribe, "campfire"):
            await self._send_tribe_error(player_id, "需要先建成营火才能举行仪式")
            return

        active = self._active_tribe_ritual(tribe)
        if active:
            await self._send_tribe_error(player_id, "部落仪式仍在持续")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        if int(storage.get("wood", 0) or 0) < TRIBE_RITUAL_WOOD_COST or int(storage.get("stone", 0) or 0) < TRIBE_RITUAL_STONE_COST:
            await self._send_tribe_error(player_id, f"仪式需要木材 {TRIBE_RITUAL_WOOD_COST}、石块 {TRIBE_RITUAL_STONE_COST}")
            return

        storage["wood"] = int(storage.get("wood", 0) or 0) - TRIBE_RITUAL_WOOD_COST
        storage["stone"] = int(storage.get("stone", 0) or 0) - TRIBE_RITUAL_STONE_COST
        ritual_config = self._ritual_config(tribe)
        duration_minutes = int(ritual_config.get("durationMinutes", TRIBE_RITUAL_DURATION_MINUTES) or TRIBE_RITUAL_DURATION_MINUTES)
        gather_bonus = int(ritual_config.get("gatherBonus", TRIBE_RITUAL_GATHER_BONUS) or TRIBE_RITUAL_GATHER_BONUS)
        active_until = datetime.fromtimestamp(datetime.now().timestamp() + duration_minutes * 60)
        tribe["ritual"] = {
            "type": "harvest",
            "title": "丰收篝火",
            "gatherBonus": gather_bonus,
            "activeUntil": active_until.isoformat(),
            "startedAt": datetime.now().isoformat(),
            "startedBy": player_id
        }
        self._add_tribe_history(
            tribe,
            "ritual",
            "点燃丰收篝火",
            f"持续 {duration_minutes} 分钟，采集额外 +{gather_bonus}。",
            player_id
        )
        await self._notify_tribe(tribe_id, f"{member.get('name', '管理者')} 点燃了丰收篝火：{duration_minutes} 分钟内采集额外 +{gather_bonus}。")
        await self.broadcast_tribe_state(tribe_id)

    async def start_tribe_feast(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以举办部落宴会")
            return

        if not self._is_tribe_building_built(tribe, "campfire"):
            await self._send_tribe_error(player_id, "需要先建成营火才能举办宴会")
            return

        active = self._active_tribe_ritual(tribe)
        if active:
            await self._send_tribe_error(player_id, "部落仪式仍在持续")
            return

        food = int(tribe.get("food", 0) or 0)
        if food < TRIBE_FEAST_FOOD_COST:
            await self._send_tribe_error(player_id, f"宴会需要食物 {TRIBE_FEAST_FOOD_COST}")
            return

        tribe["food"] = food - TRIBE_FEAST_FOOD_COST
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + TRIBE_FEAST_RENOWN_BONUS
        active_until = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_FEAST_DURATION_MINUTES * 60)
        tribe["ritual"] = {
            "type": "feast",
            "title": "部落宴会",
            "gatherBonus": TRIBE_FEAST_GATHER_BONUS,
            "renownBonus": TRIBE_FEAST_RENOWN_BONUS,
            "activeUntil": active_until.isoformat(),
            "startedAt": datetime.now().isoformat(),
            "startedBy": player_id
        }
        self._add_tribe_history(
            tribe,
            "ritual",
            "举办部落宴会",
            f"消耗食物 {TRIBE_FEAST_FOOD_COST}，持续 {TRIBE_FEAST_DURATION_MINUTES} 分钟，采集额外 +{TRIBE_FEAST_GATHER_BONUS}，声望 +{TRIBE_FEAST_RENOWN_BONUS}。",
            player_id
        )
        await self._notify_tribe(tribe_id, f"{member.get('name', '管理者')} 举办了部落宴会：食物转化为士气，采集额外 +{TRIBE_FEAST_GATHER_BONUS}，声望 +{TRIBE_FEAST_RENOWN_BONUS}。")
        await self._publish_world_rumor(
            "feast",
            "营火宴会",
            f"{tribe.get('name', '部落')} 举办了部落宴会，附近都听见了歌声与鼓点。",
            {
                "tribeId": tribe_id,
                "tribeName": tribe.get("name", "部落")
            }
        )
        await self.broadcast_tribe_state(tribe_id)

    async def complete_cave_expedition(self, player_id: str, cave_label: str, depth: int, finds: int, food_supported: bool = True, route_key: str = "deep"):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        safe_label = (cave_label or "未知洞穴").strip()[:30]
        safe_depth = max(0, min(int(depth or 0), 999))
        safe_finds = max(0, min(int(finds or 0), 999))
        safe_route_key = route_key if route_key in TRIBE_CAVE_ROUTE_PLANS else "deep"
        route_plan = TRIBE_CAVE_ROUTE_PLANS[safe_route_key]
        route_food_cost = max(0, int(route_plan.get("foodCost", TRIBE_CAVE_FOOD_COST) or TRIBE_CAVE_FOOD_COST))
        rune_effects = self._tribe_rune_effects(tribe)
        cave_finds_bonus = max(0, int(rune_effects.get("caveFindsBonus", 0) or 0))
        food = max(0, int(tribe.get("food", 0) or 0))
        food_supported = bool(food_supported) and food >= route_food_cost
        if food_supported:
            tribe["food"] = food - route_food_cost
            route_multiplier = max(0, float(route_plan.get("findsMultiplier", 1) or 1))
            route_bonus = max(0, int(route_plan.get("findsBonus", 0) or 0))
            safe_finds = math.floor(safe_finds * route_multiplier) + route_bonus
            food_detail = f" 选择{route_plan.get('label', '深入路线')}，消耗食物 {route_food_cost}，远征补给充足。"
        else:
            safe_finds = math.floor(safe_finds * TRIBE_CAVE_LOW_FOOD_FINDS_MULTIPLIER)
            food_detail = f" 选择{route_plan.get('label', '深入路线')}，食物不足，远征收益下降。"
        if cave_finds_bonus > 0:
            safe_finds += cave_finds_bonus
            food_detail += f" 图腾稀有铭文共鸣，额外收获 +{cave_finds_bonus}。"
        oath_cave_bonus = self._oath_bonus(tribe, "caveFindsBonus")
        if oath_cave_bonus:
            safe_finds += oath_cave_bonus
            food_detail += f" 远行誓约让队伍多带回 +{oath_cave_bonus}。"
        discoveries = tribe.setdefault("discoveries", [])
        discovery_key = "deep_cave_echo"
        discovery_depth = max(1, int(route_plan.get("discoveryDepth", 4) or 4))
        discovery_unlocked = safe_depth >= discovery_depth and discovery_key not in discoveries
        if discovery_unlocked:
            discoveries.append(discovery_key)

        detail = f"{member.get('name', '成员')} 完成了 {safe_label} 远征：深度 {safe_depth}，收获 {safe_finds}。{food_detail}"
        if discovery_unlocked:
            detail += " 远征队发现了幽洞回声，可尝试刻写稀有铭文。"
        race_opened = await self._maybe_open_rare_cave_race(tribe, player_id, safe_label, safe_route_key, safe_depth, safe_finds)
        if race_opened:
            detail += f" 洞内风声改道，{race_opened.get('label', '短时稀有洞穴')}已经开启，多部落可抢首探。"
        self._record_map_memory(
            tribe,
            "cave_first",
            f"{safe_label}远征记号",
            f"{member.get('name', '成员')}带队深入{safe_label}，在洞口附近留下可供后来者辨认的路线记号。",
            float(self.players.get(player_id, {}).get("x", 0) or 0),
            float(self.players.get(player_id, {}).get("z", 0) or 0),
            f"cave:{safe_label}:{safe_route_key}",
            member.get("name", "成员")
        )
        self._add_tribe_history(
            tribe,
            "cave",
            f"完成{safe_label}远征",
            detail,
            player_id,
            {
                "kind": "cave",
                "memberName": member.get("name", "成员"),
                "caveLabel": safe_label,
                "depth": safe_depth,
                "finds": safe_finds,
                "routeKey": safe_route_key,
                "routeLabel": route_plan.get("label", "深入路线"),
                "foodSupported": food_supported,
                "foodCost": route_food_cost if food_supported else 0,
                "lowFoodMultiplier": TRIBE_CAVE_LOW_FOOD_FINDS_MULTIPLIER if not food_supported else 1,
                "routeFindsMultiplier": route_plan.get("findsMultiplier", 1) if food_supported else 1,
                "routeFindsBonus": route_plan.get("findsBonus", 0) if food_supported else 0,
                "runeFindsBonus": cave_finds_bonus,
                "oathFindsBonus": oath_cave_bonus,
                "discoveryUnlocked": discovery_unlocked,
                "discoveryKey": discovery_key if discovery_unlocked else None,
                "caveRaceOpened": bool(race_opened),
                "caveRaceId": race_opened.get("id") if race_opened else None
            }
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def resolve_world_event(self, player_id: str, event_id: str, event_action: str = ""):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        env = self._get_current_environment()
        events = [event for event in (env.get("worldEvents", []) or []) if isinstance(event, dict)]
        event = next((item for item in events if item.get("id") == event_id), None)
        if not event:
            await self._send_tribe_error(player_id, "世界事件已经结束")
            return

        member = tribe.get("members", {}).get(player_id, {})
        title = event.get("title", "世界事件")
        region_label = event.get("regionLabel", "未知区域")
        detail = f"{member.get('name', '成员')} 在{region_label}处理了{title}。"
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        event_key = event.get("key")
        reward = dict(WORLD_EVENT_REWARDS.get(event_key, {}))
        event_action_key = None
        event_action_label = None
        event_action_key, action_plan = self._world_event_action_plan(tribe, event, event_action)
        if action_plan:
            event_action_label = action_plan.get("label", "追猎")
            if "foodMultiplier" in action_plan:
                reward["food"] = math.floor(int(reward.get("food", 0) or 0) * float(action_plan.get("foodMultiplier", 1) or 1))
            reward["renown"] = int(reward.get("renown", 0) or 0) + int(action_plan.get("renownBonus", 0) or 0)
            for key, amount in (action_plan.get("reward") or {}).items():
                reward[key] = int(reward.get(key, 0) or 0) + int(amount or 0)
            if int(action_plan.get("tamedBeasts", 0) or 0) > 0:
                tribe["tamed_beasts"] = int(tribe.get("tamed_beasts", 0) or 0) + int(action_plan.get("tamedBeasts", 0) or 0)
        reward_parts = []
        region_event_bonus_labels = self._apply_world_event_region_bonuses(tribe, event_key, reward, reward_parts)
        law_event_bonus_parts = self.apply_tribe_law_event_bonus(tribe, event_key or "world_event", title)
        if law_event_bonus_parts:
            reward_parts.extend(law_event_bonus_parts)
        for resource_key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(reward.get(resource_key, 0) or 0)
            if amount == 0:
                continue
            storage[resource_key] = max(0, int(storage.get(resource_key, 0) or 0) + amount)
            reward_parts.append(f"{label}{'+' if amount > 0 else ''}{amount}")
        food_reward = int(reward.get("food", 0) or 0)
        if food_reward > 0:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food_reward
            reward_parts.append(f"食物+{food_reward}")
        discovery_buff_bonus = self._celebration_bonus(tribe, "discoveryBonus") + self._oath_bonus(tribe, "discoveryBonus")
        discovery_progress = int(reward.get("discoveryProgress", 0) or 0)
        if discovery_progress > 0 and discovery_buff_bonus > 0:
            discovery_progress += discovery_buff_bonus
            reward["discoveryProgress"] = discovery_progress
        if discovery_progress > 0:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery_progress
            reward_parts.append(f"发现进度+{discovery_progress}")
        renown_reward = int(reward.get("renown", 0) or 0)
        if renown_reward > 0:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown_reward
            reward_parts.append(f"声望+{renown_reward}")
        trade_reward = int(reward.get("tradeReputation", 0) or 0)
        if trade_reward > 0:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_reward
            reward_parts.append(f"贸易信誉+{trade_reward}")
        discovery_key = None
        if event_key == "ruin_clue":
            discovery_key = "deep_cave_echo"
            chain_count = int(tribe.get("ruin_clue_chain", 0) or 0) + 1 + int((action_plan or {}).get("ruinClueChainBonus", 0) or 0)
            tribe["ruin_clue_chain"] = chain_count
            discoveries = tribe.setdefault("discoveries", [])
            if discovery_key not in discoveries:
                discoveries.append(discovery_key)
                detail += " 遗迹线索指向幽洞回声，可尝试刻写稀有铭文。"
            else:
                detail += " 遗迹线索被再次记录，补充了部落发现进度。"
            remaining = max(0, WORLD_EVENT_RUIN_CHAIN_THRESHOLD - chain_count)
            if remaining > 0:
                detail += f" 还需连续记录 {remaining} 条遗迹线索，可能拼出稀有遗迹。"
        elif event_key == "herd":
            if event_action_key == "drive":
                detail += " 成员驱赶兽群远离营地，部落领地声明更有威慑。"
            elif event_action_key == "tame":
                detail += " 成员尝试驯养幼兽，部落留下了最早的驯养记录。"
            else:
                detail += " 成员追踪兽群后，部落带回了可储备的食物。"
        elif event_key == "storm":
            detail += " 成员加固了营火遮蔽，暴雨冲刷出可用石块。"
        elif event_key == "rare_ruin":
            tribe["ruin_clue_chain"] = 0
            discovery_key = "rare_ruin_memory"
            discoveries = tribe.setdefault("discoveries", [])
            if discovery_key not in discoveries:
                discoveries.append(discovery_key)
            detail += " 稀有遗迹被完整记录，部落获得了古老记忆，可继续发展更高阶铭文。"
        if action_plan and action_plan.get("detail"):
            detail += f" {action_plan.get('detail')}"
        if reward_parts:
            detail += f" 奖励：{'、'.join(reward_parts)}。"
        remnant = self._build_world_event_remnant(tribe, event, event_action_key, action_plan, member)
        if remnant:
            detail += f" {remnant.get('label', '事件余迹')}留在附近，成员可再次整理。"
        myth_claim = self._open_myth_claim(
            tribe,
            "world_event",
            event_action_label or title,
            f"{region_label}的{title}已经被处理，族人可以争论它究竟预示着火种、旧路、互市还是守边。",
            float(event.get("x", 0) or 0),
            float(event.get("z", 0) or 0),
            f"{event.get('id')}:{event_action_key or 'default'}",
            member.get("name", "成员")
        )
        if myth_claim:
            detail += " 这件事开始产生神话解释权。"

        env["worldEvents"] = [item for item in events if item.get("id") != event_id]
        rare_spawned = False
        if event_key == "ruin_clue" and int(tribe.get("ruin_clue_chain", 0) or 0) >= WORLD_EVENT_RUIN_CHAIN_THRESHOLD:
            tribe["ruin_clue_chain"] = 0
            rare_event = self._build_rare_ruin_event()
            env["worldEvents"].append(rare_event)
            rare_spawned = True
            detail += f" 连续线索拼合完成，{rare_event['regionLabel']}出现了{rare_event['title']}！"
        map_data = self.maps.get(self.current_map_name) or {}
        map_data["environment"] = env
        map_data["updated_at"] = datetime.now().isoformat()
        self._add_tribe_history(
            tribe,
            "world_event",
            title,
            detail,
            player_id,
            {
                "kind": "world_event",
                "eventId": event.get("id"),
                "eventKey": event_key,
                "title": title,
                "regionLabel": region_label,
                "memberName": member.get("name", "成员"),
                "reward": reward,
                "rewardParts": reward_parts,
                "regionEventBonusLabels": region_event_bonus_labels,
                "lawEventBonusParts": law_event_bonus_parts,
                "eventActionKey": event_action_key,
                "eventActionLabel": event_action_label,
                "discoveryKey": discovery_key,
                "celebrationDiscoveryBonus": discovery_buff_bonus if discovery_progress > 0 else 0,
                "rareSpawned": rare_spawned,
                "remnant": remnant
            }
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def punish_tribe_member(self, player_id: str, target_id: str, reason: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        members = tribe.get("members", {})
        actor = members.get(player_id, {})
        target = members.get(target_id)
        if not target:
            await self._send_tribe_error(player_id, "成员不存在")
            return
        if not self._can_govern_member(actor, target):
            await self._send_tribe_error(player_id, "你不能惩罚该成员")
            return

        cooldowns = tribe.setdefault("punish_cooldowns", {})
        cooldown_key = f"{player_id}:{target_id}"
        hours_since = self._hours_since_iso(cooldowns.get(cooldown_key))
        if hours_since is not None and hours_since < TRIBE_PUNISH_COOLDOWN_HOURS:
            remaining = max(1, math.ceil(TRIBE_PUNISH_COOLDOWN_HOURS - hours_since))
            await self._send_tribe_error(player_id, f"惩罚冷却中，还需约 {remaining} 小时")
            return

        target["contribution"] = max(0, int(target.get("contribution", 0) or 0) - TRIBE_PUNISH_CONTRIBUTION_PENALTY)
        target["punish_count"] = int(target.get("punish_count", 0) or 0) + 1
        cooldowns[cooldown_key] = datetime.now().isoformat()
        record = {
            "targetId": target_id,
            "targetName": target.get("name", "成员"),
            "actorId": player_id,
            "actorName": actor.get("name", "管理者"),
            "reason": (reason or "行为不当").strip()[:80],
            "penalty": TRIBE_PUNISH_CONTRIBUTION_PENALTY,
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("punishments", []).append(record)
        tribe["punishments"] = tribe["punishments"][-20:]
        await self._notify_tribe(
            tribe_id,
            f"{record['actorName']} 已惩罚 {record['targetName']}：{record['reason']}，扣除 {record['penalty']} 贡献。"
        )
        self._add_tribe_history(
            tribe,
            "punishment",
            "执行部落惩罚",
            f"{record['actorName']} 惩罚 {record['targetName']}：{record['reason']}，扣除 {record['penalty']} 贡献。",
            player_id,
            {"kind": "punishment", **record}
        )
        await self.broadcast_tribe_state(tribe_id)

    async def start_tribe_vote(self, player_id: str, role: str, candidate_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        starter = tribe["members"].get(player_id, {})
        if starter.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以发起选举")
            return

        if role not in ("leader", "elder") or candidate_id not in tribe["members"]:
            await self._send_tribe_error(player_id, "候选人无效")
            return

        members = tribe.get("members", {})
        min_members = self._vote_min_members(role)
        if len(members) < min_members:
            role_label = "首领" if role == "leader" else "长老"
            await self._send_tribe_error(player_id, f"{role_label}选举至少需要 {min_members} 名成员")
            return

        candidate = members[candidate_id]
        min_contribution = self._vote_min_contribution(role)
        if int(candidate.get("contribution", 0) or 0) < min_contribution:
            role_label = "首领" if role == "leader" else "长老"
            await self._send_tribe_error(player_id, f"候选人贡献不足，竞选{role_label}至少需要 {min_contribution} 贡献")
            return

        active_duplicate = any(
            vote.get("tribe_id") == tribe_id
            and vote.get("status") == "active"
            and (vote.get("role") == role or vote.get("candidateId") == candidate_id)
            for vote in self.tribe_votes.values()
        )
        if active_duplicate:
            await self._send_tribe_error(player_id, "已有同职位或同候选人的进行中投票")
            return

        cooldowns = tribe.setdefault("vote_cooldowns", {})
        cooldown_hours = self._vote_cooldown_hours(role)
        hours_since = self._hours_since_iso(cooldowns.get(role))
        if hours_since is not None and hours_since < cooldown_hours:
            remaining = max(1, math.ceil(cooldown_hours - hours_since))
            role_label = "首领" if role == "leader" else "长老"
            await self._send_tribe_error(player_id, f"{role_label}投票冷却中，还需约 {remaining} 小时")
            return

        vote_id = self._make_vote_id()
        cooldowns[role] = datetime.now().isoformat()
        vote_record = {
            "id": vote_id,
            "tribe_id": tribe_id,
            "role": role,
            "candidateId": candidate_id,
            "candidateName": candidate.get("name", "玩家"),
            "starterId": player_id,
            "starterName": starter.get("name", "管理者"),
            "yes": [],
            "no": [],
            "status": "active",
            "createdAt": datetime.now().isoformat()
        }
        self.tribe_votes[vote_id] = vote_record
        role_label = "首领" if role == "leader" else "长老"
        self._add_tribe_history(
            tribe,
            "vote",
            f"发起{role_label}选举",
            f"{starter.get('name', '管理者')} 提名 {candidate.get('name', '玩家')} 竞选{role_label}。",
            player_id,
            {
                "kind": "vote",
                "voteId": vote_id,
                "role": role,
                "roleLabel": role_label,
                "candidateId": candidate_id,
                "candidateName": candidate.get("name", "玩家"),
                "starterName": starter.get("name", "管理者"),
                "status": "active",
                "yesCount": 0,
                "noCount": 0,
                "memberCount": len(members),
                "createdAt": vote_record["createdAt"]
            }
        )
        await self.broadcast_tribe_state(tribe_id)

    async def cast_tribe_vote(self, player_id: str, vote_id: str, approve: bool):
        vote = self.tribe_votes.get(vote_id)
        if not vote or vote.get("status") != "active":
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "投票不存在或已结束"
            })
            return

        tribe_id = vote.get("tribe_id")
        tribe = self.tribes.get(tribe_id)
        if not tribe or player_id not in tribe.get("members", {}):
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "你不属于该部落"
            })
            return

        vote["yes"] = [pid for pid in vote.get("yes", []) if pid != player_id]
        vote["no"] = [pid for pid in vote.get("no", []) if pid != player_id]
        vote["yes" if approve else "no"].append(player_id)

        member_count = len(tribe.get("members", {}))
        if len(vote["yes"]) > member_count / 2:
            candidate_id = vote.get("candidateId")
            candidate = tribe["members"].get(candidate_id)
            if candidate:
                if vote.get("role") == "leader":
                    old_leader = tribe["members"].get(tribe.get("leader_id"))
                    if old_leader:
                        old_leader["role"] = "member"
                    tribe["leader_id"] = candidate_id
                    candidate["role"] = "leader"
                elif vote.get("role") == "elder":
                    candidate["role"] = "elder"
                    if candidate_id not in tribe["elder_ids"]:
                        tribe["elder_ids"].append(candidate_id)
            vote["status"] = "passed"
            role_label = "首领" if vote.get("role") == "leader" else "长老"
            self._add_tribe_history(
                tribe,
                "vote",
                f"{role_label}选举通过",
                f"{vote.get('candidateName', '候选人')} 成为{role_label}。",
                player_id,
                {
                    "kind": "vote",
                    "voteId": vote_id,
                    "role": vote.get("role"),
                    "roleLabel": role_label,
                    "candidateId": candidate_id,
                    "candidateName": vote.get("candidateName", "候选人"),
                    "starterName": vote.get("starterName", "管理者"),
                    "status": "passed",
                    "yesCount": len(vote.get("yes", [])),
                    "noCount": len(vote.get("no", [])),
                    "memberCount": member_count,
                    "createdAt": vote.get("createdAt")
                }
            )
        elif len(vote["no"]) >= member_count / 2:
            vote["status"] = "rejected"
            role_label = "首领" if vote.get("role") == "leader" else "长老"
            self._add_tribe_history(
                tribe,
                "vote",
                f"{role_label}选举未通过",
                f"{vote.get('candidateName', '候选人')} 的竞选被否决。",
                player_id,
                {
                    "kind": "vote",
                    "voteId": vote_id,
                    "role": vote.get("role"),
                    "roleLabel": role_label,
                    "candidateId": vote.get("candidateId"),
                    "candidateName": vote.get("candidateName", "候选人"),
                    "starterName": vote.get("starterName", "管理者"),
                    "status": "rejected",
                    "yesCount": len(vote.get("yes", [])),
                    "noCount": len(vote.get("no", [])),
                    "memberCount": member_count,
                    "createdAt": vote.get("createdAt")
                }
            )

        await self.broadcast_tribe_state(tribe_id)

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

    def _active_player_fatigue(self, player: dict) -> int:
        fatigue = int(player.get("conflict_fatigue", 0) or 0)
        until_text = player.get("conflict_fatigue_until")
        if fatigue and until_text:
            try:
                if datetime.fromisoformat(until_text).timestamp() < datetime.now().timestamp():
                    player["conflict_fatigue"] = 0
                    player.pop("conflict_fatigue_until", None)
                    return 0
            except (TypeError, ValueError):
                pass
        return max(0, min(PLAYER_CONFLICT_FATIGUE_MAX, fatigue))

    def _active_personal_guard(self, player: dict):
        guard = player.get("personal_guard") if isinstance(player.get("personal_guard"), dict) else None
        if not guard:
            return None
        try:
            if datetime.fromisoformat(guard.get("activeUntil")).timestamp() < datetime.now().timestamp():
                player.pop("personal_guard", None)
                return None
        except (TypeError, ValueError):
            player.pop("personal_guard", None)
            return None
        return guard

    def _active_personal_inspiration(self, player: dict):
        inspiration = player.get("personal_inspiration") if isinstance(player.get("personal_inspiration"), dict) else None
        if not inspiration:
            return None
        try:
            if datetime.fromisoformat(inspiration.get("activeUntil")).timestamp() < datetime.now().timestamp():
                player.pop("personal_inspiration", None)
                return None
        except (TypeError, ValueError):
            player.pop("personal_inspiration", None)
            return None
        return inspiration

    def _personal_renown_title(self, renown: int) -> dict:
        for title in PLAYER_RENOWN_TITLES:
            if renown >= int(title.get("min", 0) or 0):
                return dict(title)
        return dict(PLAYER_RENOWN_TITLES[-1])

    def _personal_title_bonus(self, player: dict, key: str) -> int:
        title = self._personal_renown_title(int(player.get("personal_renown", 0) or 0))
        return int(title.get(key, 0) or 0)

    def _personal_guard_radius(self, player: dict) -> int:
        return PLAYER_CONFLICT_GUARD_RADIUS + self._personal_title_bonus(player, "guardRadiusBonus")

    def _personal_fatigue_recovery_seconds(self, player: dict) -> int:
        return max(60, PLAYER_CONFLICT_FATIGUE_DECAY_SECONDS - self._personal_title_bonus(player, "fatigueRecoveryBonusSeconds"))

    def _active_personal_identity_cooldown(self, player: dict) -> str:
        cooldown_until = player.get("personal_identity_cooldown_until")
        if not cooldown_until:
            return ""
        try:
            if datetime.fromisoformat(cooldown_until).timestamp() <= datetime.now().timestamp():
                player.pop("personal_identity_cooldown_until", None)
                return ""
        except (TypeError, ValueError):
            player.pop("personal_identity_cooldown_until", None)
            return ""
        return cooldown_until

    def _personal_identity_state(self, player: dict, personal_renown: Optional[int] = None) -> dict:
        identity_key = player.get("personal_identity")
        identity = PLAYER_IDENTITY_OPTIONS.get(identity_key)
        renown = int(personal_renown if personal_renown is not None else player.get("personal_renown", 0) or 0)
        options = []
        for key, option in PLAYER_IDENTITY_OPTIONS.items():
            min_renown = int(option.get("minRenown", PLAYER_IDENTITY_MIN_RENOWN) or 0)
            options.append({
                "key": key,
                "label": option.get("label", key),
                "actionLabel": option.get("actionLabel", option.get("label", key)),
                "summary": option.get("summary", ""),
                "minRenown": min_renown,
                "available": renown >= min_renown
            })
        return {
            "key": identity_key if identity else "",
            "label": identity.get("label") if identity else "",
            "actionLabel": identity.get("actionLabel") if identity else "",
            "summary": identity.get("summary") if identity else "",
            "options": options,
            "cooldownUntil": self._active_personal_identity_cooldown(player),
            "cooldownSeconds": PLAYER_IDENTITY_ACTION_COOLDOWN_SECONDS,
            "minRenown": PLAYER_IDENTITY_MIN_RENOWN
        }

    def _public_personal_conflict_status(self, player: dict) -> dict:
        fatigue = self._active_player_fatigue(player)
        guard = self._active_personal_guard(player)
        inspiration = self._active_personal_inspiration(player)
        personal_renown = int(player.get("personal_renown", 0) or 0)
        renown_title = self._personal_renown_title(personal_renown)
        return {
            "fatigue": fatigue,
            "fatigueMax": PLAYER_CONFLICT_FATIGUE_MAX,
            "fatigueUntil": player.get("conflict_fatigue_until") if fatigue else "",
            "guardUntil": guard.get("activeUntil") if guard else "",
            "guardTargetName": guard.get("targetName") if guard else "",
            "guardRadius": guard.get("radius", self._personal_guard_radius(player)) if guard else self._personal_guard_radius(player),
            "personalRenown": personal_renown,
            "renownTitle": renown_title,
            "inspirationUntil": inspiration.get("activeUntil") if inspiration else "",
            "inspirationSourceName": inspiration.get("sourceName") if inspiration else "",
            "inspirationContribution": int(inspiration.get("contributionBonus", 0) or 0) if inspiration else 0,
            "inspireMinRenown": PLAYER_CONFLICT_INSPIRE_MIN_RENOWN,
            "fatigueDecaySeconds": self._personal_fatigue_recovery_seconds(player),
            "fatigueRecoveryBonusSeconds": int(renown_title.get("fatigueRecoveryBonusSeconds", 0) or 0),
            "sparTrainingBonus": int(renown_title.get("sparTrainingBonus", 0) or 0),
            "skirmishContributionBonus": int(renown_title.get("skirmishContributionBonus", 0) or 0),
            "guardSeconds": PLAYER_CONFLICT_GUARD_SECONDS,
            "inspireSeconds": PLAYER_CONFLICT_INSPIRE_SECONDS,
            "identity": self._personal_identity_state(player, personal_renown)
        }

    async def choose_personal_identity(self, player_id: str, identity_key: str):
        player = self.players.get(player_id)
        option = PLAYER_IDENTITY_OPTIONS.get(identity_key)
        if not player or not option:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "没有找到这个身份"})
            return
        personal_renown = int(player.get("personal_renown", 0) or 0)
        min_renown = int(option.get("minRenown", PLAYER_IDENTITY_MIN_RENOWN) or 0)
        if personal_renown < min_renown:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": f"个人声望至少需要 {min_renown} 才能选择身份"})
            return
        player["personal_identity"] = identity_key
        status = self._public_personal_conflict_status(player)
        await self.send_personal_message(player_id, {
            "type": "personal_identity_result",
            "action": "choose",
            "identity": status.get("identity"),
            "message": f"已选择身份：{option.get('label', '身份')}",
            "status": status
        })
        await self.send_personal_conflict_status(player_id)

    def _apply_identity_task_discount(self, tribe: dict, discount: int) -> str:
        if discount <= 0:
            return ""
        task_groups = [
            ("war_repair_tasks", ("woodCost", "stoneCost")),
            ("war_revival_tasks", ("woodCost",))
        ]
        for group_key, cost_keys in task_groups:
            for task in tribe.get(group_key, []) or []:
                if not isinstance(task, dict) or task.get("status") != "pending":
                    continue
                changed = []
                for key in cost_keys:
                    before = int(task.get(key, 0) or 0)
                    if before <= 0:
                        continue
                    after = max(0, before - discount)
                    task[key] = after
                    if after != before:
                        changed.append(key)
                if changed:
                    task["identityBonusLabel"] = "石匠整修降低了后续消耗"
                    return task.get("title", "战后任务")
        return ""

    async def perform_personal_identity_action(self, player_id: str):
        player = self.players.get(player_id)
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not player or not tribe:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "请先加入一个部落"})
            return
        identity_key = player.get("personal_identity")
        option = PLAYER_IDENTITY_OPTIONS.get(identity_key)
        if not option:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "先选择一个身份"})
            return
        cooldown_until = self._active_personal_identity_cooldown(player)
        if cooldown_until:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "身份动作还在冷却"})
            return
        if int(option.get("requiresHistory", 0) or 0) and len(tribe.get("history", []) or []) < int(option.get("requiresHistory", 0) or 0):
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "部落历史还不够讲述者复述"})
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(option.get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        discovery = int(option.get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现进度+{discovery}")
        renown = int(option.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"部落声望+{renown}")
        personal_renown = int(option.get("personalRenown", 0) or 0)
        if personal_renown:
            player["personal_renown"] = int(player.get("personal_renown", 0) or 0) + personal_renown
            reward_parts.append(f"个人声望+{personal_renown}")
        discounted_task = self._apply_identity_task_discount(tribe, int(option.get("taskDiscount", 0) or 0))
        if discounted_task:
            reward_parts.append(f"{discounted_task}消耗降低")

        now_text = datetime.now().isoformat()
        player["personal_identity_cooldown_until"] = datetime.fromtimestamp(datetime.now().timestamp() + PLAYER_IDENTITY_ACTION_COOLDOWN_SECONDS).isoformat()
        member = tribe.get("members", {}).get(player_id, {})
        detail = f"{member.get('name', player.get('name', '成员'))} 以{option.get('label', '身份')}身份执行{option.get('actionLabel', '身份动作')}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(
            tribe,
            "ritual",
            option.get("actionLabel", "身份动作"),
            detail,
            player_id,
            {
                "kind": "personal_identity",
                "identityKey": identity_key,
                "identityLabel": option.get("label"),
                "actionLabel": option.get("actionLabel"),
                "rewardParts": reward_parts,
                "memberName": member.get("name", player.get("name", "成员"))
            }
        )
        tribe.setdefault("personal_conflicts", []).append({
            "actionLabel": option.get("actionLabel", "身份动作"),
            "actorName": member.get("name", player.get("name", "成员")),
            "targetName": tribe.get("name", "部落"),
            "winnerName": option.get("label", "身份"),
            "identityLabel": option.get("label"),
            "identityActionLabel": option.get("actionLabel"),
            "identityRewardParts": reward_parts,
            "createdAt": now_text
        })
        tribe["personal_conflicts"] = tribe["personal_conflicts"][-8:]
        status = self._public_personal_conflict_status(player)
        await self.send_personal_message(player_id, {
            "type": "personal_identity_result",
            "action": "perform",
            "identity": status.get("identity"),
            "message": detail,
            "rewardParts": reward_parts,
            "status": status
        })
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.send_personal_conflict_status(player_id)

    def _find_personal_guardian(self, actor_id: str, target_id: str, target_tribe_id: str):
        if not actor_id or not target_id or not target_tribe_id:
            return None, None
        target = self.players.get(target_id)
        if not target:
            return None, None
        for guardian_id, guardian in self.players.items():
            if guardian_id in {actor_id, target_id}:
                continue
            if self.player_tribes.get(guardian_id) != target_tribe_id:
                continue
            guard = self._active_personal_guard(guardian)
            if not guard or guard.get("targetId") != actor_id:
                continue
            dx = float(guardian.get("x", 0) or 0) - float(target.get("x", 0) or 0)
            dz = float(guardian.get("z", 0) or 0) - float(target.get("z", 0) or 0)
            radius = float(guard.get("radius", self._personal_guard_radius(guardian)) or PLAYER_CONFLICT_GUARD_RADIUS)
            if dx * dx + dz * dz <= radius * radius:
                return guardian_id, guardian
        return None, None

    async def send_personal_conflict_status(self, player_id: str):
        player = self.players.get(player_id)
        if player:
            await self.send_personal_message(player_id, {
                "type": "personal_conflict_status",
                "status": self._public_personal_conflict_status(player)
            })

    async def resolve_personal_conflict(self, player_id: str, target_id: str, action_key: str):
        actor = self.players.get(player_id)
        target = self.players.get(target_id)
        action = PLAYER_CONFLICT_ACTIONS.get(action_key)
        if not actor or not target or not action or player_id == target_id:
            await self.send_personal_message(player_id, {"type": "personal_conflict_error", "message": "无法发起这次个人冲突"})
            return
        actor_tribe_id = self.player_tribes.get(player_id)
        target_tribe_id = self.player_tribes.get(target_id)
        if action.get("sameTribeOnly") and actor_tribe_id != target_tribe_id:
            await self.send_personal_message(player_id, {"type": "personal_conflict_error", "message": f"{action.get('label', '行动')}只能对同部落成员发起"})
            return

        dx = float(target.get("x", 0) or 0) - float(actor.get("x", 0) or 0)
        dz = float(target.get("z", 0) or 0) - float(actor.get("z", 0) or 0)
        if dx * dx + dz * dz > PLAYER_CONFLICT_DISTANCE * PLAYER_CONFLICT_DISTANCE:
            await self.send_personal_message(player_id, {"type": "personal_conflict_error", "message": "靠近目标玩家后才能发起冲突"})
            return

        if action.get("guard"):
            guard_radius = self._personal_guard_radius(actor)
            actor["personal_guard"] = {
                "targetId": target_id,
                "targetName": target.get("name", "玩家"),
                "protectTribeId": actor_tribe_id,
                "radius": guard_radius,
                "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + PLAYER_CONFLICT_GUARD_SECONDS).isoformat()
            }
            await self.send_personal_message(player_id, {
                "type": "personal_conflict_result",
                "actionKey": action_key,
                "actionLabel": action.get("label", "守势"),
                "actorId": player_id,
                "actorName": actor.get("name", "玩家"),
                "targetId": target_id,
                "targetName": target.get("name", "玩家"),
                "winnerId": player_id,
                "guardUntil": actor["personal_guard"]["activeUntil"],
                "guardRadius": guard_radius,
                "fatigue": actor.get("conflict_fatigue", 0),
                "status": self._public_personal_conflict_status(actor),
                "renownGain": 0
            })
            await self.send_personal_conflict_status(player_id)
            return

        if action.get("inspire"):
            personal_renown = int(actor.get("personal_renown", 0) or 0)
            if personal_renown < PLAYER_CONFLICT_INSPIRE_MIN_RENOWN:
                await self.send_personal_message(player_id, {
                    "type": "personal_conflict_error",
                    "message": f"个人声望至少需要 {PLAYER_CONFLICT_INSPIRE_MIN_RENOWN} 才能鼓舞同伴"
                })
                return
            title = self._personal_renown_title(personal_renown)
            target["personal_inspiration"] = {
                "sourceId": player_id,
                "sourceName": actor.get("name", "玩家"),
                "sourceTitle": title.get("title"),
                "contributionBonus": PLAYER_CONFLICT_INSPIRE_CONTRIBUTION,
                "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + PLAYER_CONFLICT_INSPIRE_SECONDS).isoformat()
            }
            result = {
                "type": "personal_conflict_result",
                "actionKey": action_key,
                "actionLabel": action.get("label", "鼓舞"),
                "actorId": player_id,
                "actorName": actor.get("name", "玩家"),
                "targetId": target_id,
                "targetName": target.get("name", "玩家"),
                "winnerId": player_id,
                "inspirationUntil": target["personal_inspiration"]["activeUntil"],
                "inspirationContribution": PLAYER_CONFLICT_INSPIRE_CONTRIBUTION,
                "renownTitle": title,
                "status": self._public_personal_conflict_status(actor),
                "targetStatus": self._public_personal_conflict_status(target),
                "renownGain": 0
            }
            record = {
                "actionLabel": result["actionLabel"],
                "actorName": result["actorName"],
                "targetName": result["targetName"],
                "winnerName": result["actorName"],
                "renownTitle": title.get("title"),
                "inspirationContribution": PLAYER_CONFLICT_INSPIRE_CONTRIBUTION,
                "inspirationUntil": target["personal_inspiration"]["activeUntil"],
                "createdAt": datetime.now().isoformat()
            }
            tribe = self.tribes.get(actor_tribe_id)
            if tribe:
                tribe.setdefault("personal_conflicts", []).append(record)
                tribe["personal_conflicts"] = tribe["personal_conflicts"][-8:]
            nearby = set(self._players_in_range(player_id, self.aoi_radius)) | set(self._players_in_range(target_id, self.aoi_radius)) | {player_id, target_id}
            await self.broadcast(result, include=list(nearby))
            await self.send_personal_conflict_status(player_id)
            await self.send_personal_conflict_status(target_id)
            if actor_tribe_id:
                await self.broadcast_tribe_state(actor_tribe_id)
            return

        cooldowns = actor.setdefault("personal_conflict_cooldowns", {})
        last_action_at = cooldowns.get(target_id)
        if last_action_at:
            try:
                elapsed = datetime.now().timestamp() - datetime.fromisoformat(last_action_at).timestamp()
                if elapsed < PLAYER_CONFLICT_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil(PLAYER_CONFLICT_COOLDOWN_SECONDS - elapsed))
                    await self.send_personal_message(player_id, {"type": "personal_conflict_error", "message": f"刚刚冲突过，还需 {remaining} 秒"})
                    return
            except (TypeError, ValueError):
                pass

        actor_fatigue = self._active_player_fatigue(actor)
        target_fatigue = self._active_player_fatigue(target)
        actor_roll = random.randint(1, 6) + max(0, 3 - actor_fatigue)
        target_roll = random.randint(1, 6) + max(0, 3 - target_fatigue)
        target_guard = self._active_personal_guard(target)
        guardian_id = None
        guardian = None
        guard_active = False
        if target_guard and target_guard.get("targetId") == player_id:
            try:
                guard_active = datetime.fromisoformat(target_guard.get("activeUntil")).timestamp() >= datetime.now().timestamp()
            except (TypeError, ValueError):
                guard_active = False
        if not guard_active:
            guardian_id, guardian = self._find_personal_guardian(player_id, target_id, target_tribe_id)
            guard_active = bool(guardian)
        if guard_active:
            target_roll += 2
        actor_won = actor_roll >= target_roll
        fatigue_gain = int(action.get("fatigue", 1) or 1)
        if guard_active:
            fatigue_gain = max(0, fatigue_gain - 1)
            if guardian:
                guardian.pop("personal_guard", None)
            else:
                target.pop("personal_guard", None)
        target["conflict_fatigue"] = min(PLAYER_CONFLICT_FATIGUE_MAX, target_fatigue + fatigue_gain)
        target_recovery_seconds = self._personal_fatigue_recovery_seconds(target)
        actor_recovery_seconds = self._personal_fatigue_recovery_seconds(actor)
        target["conflict_fatigue_until"] = datetime.fromtimestamp(datetime.now().timestamp() + target_recovery_seconds).isoformat()
        if action_key == "challenge" and not actor_won:
            actor["conflict_fatigue"] = min(PLAYER_CONFLICT_FATIGUE_MAX, actor_fatigue + 1)
            actor["conflict_fatigue_until"] = datetime.fromtimestamp(datetime.now().timestamp() + actor_recovery_seconds).isoformat()

        renown_gain = int(action.get("renown", 0) or 0)
        if actor_won:
            actor["personal_renown"] = int(actor.get("personal_renown", 0) or 0) + renown_gain
        training_reward = int(action.get("trainingRenown", 0) or 0)
        training_bonus = 0
        if training_reward and actor_tribe_id == target_tribe_id:
            training_bonus = max(
                self._personal_title_bonus(actor, "sparTrainingBonus"),
                self._personal_title_bonus(target, "sparTrainingBonus")
            )
            training_reward += training_bonus
            actor["personal_renown"] = int(actor.get("personal_renown", 0) or 0) + training_reward
            target["personal_renown"] = int(target.get("personal_renown", 0) or 0) + training_reward
        cooldowns[target_id] = datetime.now().isoformat()

        if actor_tribe_id and target_tribe_id and actor_tribe_id != target_tribe_id:
            relation_delta = int(action.get("relationDelta", 0) or 0)
            actor_tribe = self.tribes.get(actor_tribe_id)
            target_tribe = self.tribes.get(target_tribe_id)
            if actor_tribe:
                progress = actor_tribe.setdefault("boundary_relations", {}).setdefault(target_tribe_id, {})
                progress["score"] = max(-9, min(9, int(progress.get("score", 0) or 0) + relation_delta))
                progress["lastAction"] = f"personal:{action_key}"
                progress["lastActionAt"] = cooldowns[target_id]
            if target_tribe:
                progress = target_tribe.setdefault("boundary_relations", {}).setdefault(actor_tribe_id, {})
                progress["score"] = max(-9, min(9, int(progress.get("score", 0) or 0) + relation_delta))
                progress["lastAction"] = f"incoming_personal:{action_key}"
                progress["lastActionAt"] = cooldowns[target_id]

        knockback = float(action.get("knockback", 0) or 0)
        if knockback and actor_won:
            length = math.sqrt(dx * dx + dz * dz) or 0.001
            new_x = float(target.get("x", 0) or 0) + (dx / length) * knockback
            new_z = float(target.get("z", 0) or 0) + (dz / length) * knockback
            new_x, new_z, _ = self._clamp_to_shore(new_x, new_z, margin=PLAYER_RADIUS)
            target["x"] = new_x
            target["z"] = new_z
            await self.send_personal_message(target_id, {
                "type": "position_correction",
                "data": {"x": new_x, "y": target.get("y", 2), "z": new_z}
            })

        result = {
            "type": "personal_conflict_result",
            "actionKey": action_key,
            "actionLabel": action.get("label", "冲突"),
            "actorId": player_id,
            "actorName": actor.get("name", "玩家"),
            "targetId": target_id,
            "targetName": target.get("name", "玩家"),
            "winnerId": player_id if actor_won else target_id,
            "winnerName": actor.get("name", "玩家") if actor_won else target.get("name", "玩家"),
            "fatigue": target.get("conflict_fatigue", 0),
            "fatigueUntil": target.get("conflict_fatigue_until"),
            "fatigueGain": fatigue_gain,
            "actorRoll": actor_roll,
            "targetRoll": target_roll,
            "actorFatigue": actor.get("conflict_fatigue", 0),
            "targetFatigue": target.get("conflict_fatigue", 0),
            "cooldownSeconds": PLAYER_CONFLICT_COOLDOWN_SECONDS,
            "guarded": guard_active,
            "guardianId": guardian_id or (target_id if guard_active else ""),
            "guardianName": (guardian.get("name", "成员") if guardian else (target.get("name", "玩家") if guard_active else "")),
            "trainingReward": training_reward,
            "trainingBonus": training_bonus,
            "targetRecoverySeconds": target_recovery_seconds,
            "actorRecoverySeconds": actor_recovery_seconds,
            "renownGain": renown_gain if actor_won else 0
        }
        record = {
            "actionLabel": result["actionLabel"],
            "actorName": result["actorName"],
            "targetName": result["targetName"],
            "winnerName": result["actorName"] if actor_won else result["targetName"],
            "actorRoll": actor_roll,
            "targetRoll": target_roll,
            "fatigueGain": fatigue_gain,
            "targetFatigue": target.get("conflict_fatigue", 0),
            "fatigueUntil": target.get("conflict_fatigue_until"),
            "renownGain": renown_gain if actor_won else 0,
            "trainingReward": training_reward,
            "trainingBonus": training_bonus,
            "guarded": guard_active,
            "guardianName": result.get("guardianName", ""),
            "targetRecoverySeconds": target_recovery_seconds,
            "createdAt": cooldowns[target_id]
        }
        for tribe_id in {actor_tribe_id, target_tribe_id}:
            tribe = self.tribes.get(tribe_id)
            if tribe:
                tribe.setdefault("personal_conflicts", []).append(record)
                tribe["personal_conflicts"] = tribe["personal_conflicts"][-8:]
        nearby = set(self._players_in_range(player_id, self.aoi_radius)) | set(self._players_in_range(target_id, self.aoi_radius)) | {player_id, target_id}
        await self.broadcast(result, include=list(nearby))
        await self.broadcast({
            "type": "player_move",
            "playerId": target_id,
            "data": {
                "x": target.get("x", 0),
                "y": target.get("y", 2),
                "z": target.get("z", 0),
                "conflict_fatigue": target.get("conflict_fatigue", 0),
                "conflict_fatigue_until": target.get("conflict_fatigue_until"),
                "personal_renown": target.get("personal_renown", 0)
            }
        }, exclude=[target_id], include=list(nearby))
        await self.send_personal_conflict_status(player_id)
        await self.send_personal_conflict_status(target_id)
        if guardian_id:
            await self.send_personal_conflict_status(guardian_id)

        if actor_tribe_id:
            await self.broadcast_tribe_state(actor_tribe_id)
        if target_tribe_id and target_tribe_id != actor_tribe_id:
            await self.broadcast_tribe_state(target_tribe_id)

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

        await manager.ensure_monthly_settlement()

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

                await manager.ensure_monthly_settlement()

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

                elif message_type == "personal_conflict":
                    await manager.resolve_personal_conflict(
                        player_id,
                        message.get("targetId", ""),
                        message.get("actionKey", "challenge")
                    )

                elif message_type == "personal_identity_choose":
                    await manager.choose_personal_identity(
                        player_id,
                        message.get("identityKey", "")
                    )

                elif message_type == "personal_identity_action":
                    await manager.perform_personal_identity_action(player_id)

                elif message_type == "tribe_start_skirmish":
                    await manager.start_small_conflict(
                        player_id,
                        message.get("outcomeId", "")
                    )

                elif message_type == "tribe_join_skirmish":
                    await manager.join_small_conflict(
                        player_id,
                        message.get("conflictId", "")
                    )

                elif message_type == "tribe_resolve_skirmish":
                    await manager.resolve_small_conflict(
                        player_id,
                        message.get("conflictId", "")
                    )

                elif message_type == "tribe_declare_war":
                    await manager.declare_formal_war(
                        player_id,
                        message.get("otherTribeId", "")
                    )

                elif message_type == "tribe_join_war":
                    await manager.join_formal_war(
                        player_id,
                        message.get("warId", "")
                    )

                elif message_type == "tribe_resolve_war":
                    await manager.resolve_formal_war(
                        player_id,
                        message.get("warId", "")
                    )

                elif message_type == "tribe_request_war_truce":
                    await manager.request_war_truce(
                        player_id,
                        message.get("warId", "")
                    )

                elif message_type == "tribe_complete_war_repair":
                    await manager.complete_war_repair(
                        player_id,
                        message.get("repairId", "")
                    )

                elif message_type == "tribe_complete_war_revival":
                    await manager.complete_war_revival(
                        player_id,
                        message.get("revivalId", "")
                    )

                elif message_type == "tribe_support_war":
                    await manager.support_formal_war(
                        player_id,
                        message.get("warId", ""),
                        message.get("sideTribeId", "")
                    )

                elif message_type == "tribe_mediate_war":
                    await manager.mediate_formal_war(
                        player_id,
                        message.get("warId", "")
                    )

                elif message_type == "tribe_resolve_war_diplomacy":
                    await manager.resolve_war_diplomacy(
                        player_id,
                        message.get("diplomacyId", ""),
                        message.get("action", "")
                    )

                elif message_type == "tribe_resolve_diplomacy_council":
                    await manager.resolve_diplomacy_council_site(
                        player_id,
                        message.get("councilId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_complete_war_aftermath":
                    await manager.complete_war_aftermath(
                        player_id,
                        message.get("aftermathId", "")
                    )

                elif message_type == "tribe_complete_war_ally_task":
                    await manager.complete_war_ally_task(
                        player_id,
                        message.get("taskId", ""),
                        message.get("action", "")
                    )

                elif message_type == "tribe_list":
                    await manager.send_personal_message(player_id, manager.get_tribes_overview())
                    await manager.send_personal_message(player_id, manager.get_player_tribe_state(player_id))

                elif message_type == "tribe_history_page":
                    await manager.send_personal_message(
                        player_id,
                        manager.get_tribe_history_page(
                            player_id,
                            message.get("cursor", 0),
                            message.get("limit", TRIBE_HISTORY_PAGE_SIZE)
                        )
                    )

                elif message_type == "tribe_create":
                    await manager.create_tribe(player_id, message.get("name", ""))

                elif message_type == "tribe_join":
                    await manager.request_join_tribe(
                        player_id,
                        message.get("tribeId", ""),
                        message.get("message", "")
                    )

                elif message_type == "tribe_review_application":
                    await manager.approve_tribe_application(
                        player_id,
                        message.get("applicationId", ""),
                        bool(message.get("approved", False))
                    )

                elif message_type == "tribe_contribute":
                    await manager.contribute_to_tribe(player_id, message.get("resources", {}))

                elif message_type == "tribe_advance_target":
                    await manager.advance_tribe_target(player_id)

                elif message_type == "tribe_set_announcement":
                    await manager.set_tribe_announcement(
                        player_id,
                        message.get("announcement", "")
                    )

                elif message_type == "tribe_build_structure":
                    await manager.build_tribe_structure(
                        player_id,
                        message.get("buildingKey", "")
                    )

                elif message_type == "tribe_allocate_resources":
                    await manager.allocate_tribe_resources(
                        player_id,
                        message.get("targetId", ""),
                        message.get("resources", {})
                    )

                elif message_type == "tribe_create_trade":
                    await manager.create_tribe_trade(
                        player_id,
                        message.get("targetTribeId", ""),
                        message.get("offer", {}),
                        message.get("request", {})
                    )

                elif message_type == "tribe_resolve_trade":
                    await manager.resolve_tribe_trade(
                        player_id,
                        message.get("tradeId", ""),
                        message.get("action", "")
                    )

                elif message_type == "tribe_complete_trade_credit_repair":
                    await manager.complete_trade_credit_repair(
                        player_id,
                        message.get("taskId", "")
                    )

                elif message_type == "tribe_claim_flag":
                    await manager.claim_tribe_flag(
                        player_id,
                        message.get("x", 0),
                        message.get("z", 0)
                    )

                elif message_type == "tribe_patrol_flag":
                    await manager.patrol_tribe_flag(
                        player_id,
                        message.get("flagId", "")
                    )

                elif message_type == "tribe_boundary_action":
                    await manager.resolve_boundary_action(
                        player_id,
                        message.get("flagId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_complete_boundary_followup":
                    await manager.complete_boundary_followup_task(
                        player_id,
                        message.get("taskId", "")
                    )

                elif message_type == "tribe_unlock_rune":
                    await manager.unlock_tribe_rune(
                        player_id,
                        message.get("runeKey", "")
                    )

                elif message_type == "tribe_start_ritual":
                    await manager.start_tribe_ritual(player_id)

                elif message_type == "tribe_start_feast":
                    await manager.start_tribe_feast(player_id)

                elif message_type == "tribe_start_communal_cook":
                    await manager.start_communal_cook(
                        player_id,
                        message.get("recipeKey", "")
                    )

                elif message_type == "tribe_contribute_communal_cook":
                    await manager.contribute_communal_cook(
                        player_id,
                        message.get("ingredientKey", "")
                    )

                elif message_type == "tribe_start_drum_rhythm":
                    await manager.start_drum_rhythm(
                        player_id,
                        message.get("rhythmKey", "")
                    )

                elif message_type == "tribe_join_drum_rhythm":
                    await manager.join_drum_rhythm(
                        player_id,
                        message.get("beatKey", "")
                    )

                elif message_type == "tribe_complete_drum_rhythm":
                    await manager.complete_drum_rhythm(player_id)

                elif message_type == "tribe_group_emote":
                    await manager.perform_group_emote(
                        player_id,
                        message.get("emoteKey", "")
                    )

                elif message_type == "tribe_start_sacred_fire":
                    await manager.start_sacred_fire_relay(
                        player_id,
                        message.get("destinationKey", "")
                    )

                elif message_type == "tribe_carry_sacred_fire":
                    await manager.carry_sacred_fire(
                        player_id,
                        message.get("stepKey", "")
                    )

                elif message_type == "tribe_complete_sacred_fire":
                    await manager.complete_sacred_fire_relay(player_id)

                elif message_type == "tribe_start_mentorship":
                    await manager.start_mentorship(
                        player_id,
                        message.get("focusKey", "")
                    )

                elif message_type == "tribe_join_mentorship":
                    await manager.join_mentorship(player_id)

                elif message_type == "tribe_complete_mentorship":
                    await manager.complete_mentorship(player_id)

                elif message_type == "tribe_join_celebration_echo":
                    await manager.join_celebration_echo(
                        player_id,
                        message.get("echoId", "")
                    )

                elif message_type == "tribe_start_night_outing":
                    await manager.start_night_outing(
                        player_id,
                        message.get("optionKey", "")
                    )

                elif message_type == "tribe_punish_member":
                    await manager.punish_tribe_member(
                        player_id,
                        message.get("targetId", ""),
                        message.get("reason", "")
                    )

                elif message_type == "tribe_start_vote":
                    await manager.start_tribe_vote(
                        player_id,
                        message.get("role", ""),
                        message.get("candidateId", "")
                    )

                elif message_type == "tribe_vote":
                    await manager.cast_tribe_vote(
                        player_id,
                        message.get("voteId", ""),
                        bool(message.get("approve", False))
                    )

                elif message_type == "tribe_return_to_camp":
                    await manager._move_player_to_tribe_spawn(
                        player_id,
                        manager.player_tribes.get(player_id)
                    )

                elif message_type == "tribe_complete_cave_expedition":
                    await manager.complete_cave_expedition(
                        player_id,
                        message.get("caveLabel", "未知洞穴"),
                        message.get("depth", 0),
                        message.get("finds", 0),
                        bool(message.get("foodSupported", True)),
                        message.get("routeKey", "deep")
                    )

                elif message_type == "tribe_claim_cave_race":
                    await manager.claim_cave_race_first_explore(
                        player_id,
                        message.get("raceId", "")
                    )

                elif message_type == "tribe_advance_cave_rescue":
                    await manager.advance_cave_rescue(
                        player_id,
                        message.get("raceId", "")
                    )

                elif message_type == "tribe_resolve_world_event":
                    await manager.resolve_world_event(
                        player_id,
                        message.get("eventId", ""),
                        message.get("eventAction", "")
                    )

                elif message_type == "tribe_start_scout":
                    await manager.start_tribe_scout(player_id)

                elif message_type == "tribe_secure_scout_site":
                    await manager.secure_scouted_resource_site(
                        player_id,
                        message.get("siteId", "")
                    )

                elif message_type == "tribe_collect_controlled_site":
                    await manager.collect_controlled_resource_site(
                        player_id,
                        message.get("siteId", "")
                    )

                elif message_type == "tribe_collect_trade_route_site":
                    await manager.collect_trade_route_site(
                        player_id,
                        message.get("siteId", "")
                    )

                elif message_type == "tribe_resolve_caravan_route":
                    await manager.resolve_caravan_route(
                        player_id,
                        message.get("routeId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_start_apprentice_exchange":
                    await manager.start_apprentice_exchange(
                        player_id,
                        message.get("targetTribeId", ""),
                        message.get("focusKey", "")
                    )

                elif message_type == "tribe_resolve_nomad_visitor":
                    await manager.resolve_nomad_visitor(
                        player_id,
                        message.get("visitorId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_resolve_nomad_visitor_aftereffect":
                    await manager.resolve_nomad_visitor_aftereffect(
                        player_id,
                        message.get("effectId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_escort_covenant_messenger":
                    await manager.escort_covenant_messenger(
                        player_id,
                        message.get("taskId", "")
                    )

                elif message_type == "tribe_create_personal_token":
                    await manager.create_personal_token(
                        player_id,
                        message.get("tokenKey", ""),
                        message.get("targetId", "tribe")
                    )

                elif message_type == "tribe_redeem_personal_token":
                    await manager.redeem_personal_token(
                        player_id,
                        message.get("tokenId", "")
                    )

                elif message_type == "tribe_call_personal_debt":
                    await manager.call_personal_debt(
                        player_id,
                        message.get("tokenId", "")
                    )

                elif message_type == "tribe_settle_personal_debt":
                    await manager.settle_personal_debt(
                        player_id,
                        message.get("taskId", "")
                    )

                elif message_type == "tribe_start_renown_pledge":
                    await manager.start_renown_pledge(
                        player_id,
                        message.get("pledgeKey", "")
                    )

                elif message_type == "tribe_fulfill_renown_pledge":
                    await manager.fulfill_renown_pledge(
                        player_id,
                        message.get("pledgeId", "")
                    )

                elif message_type == "tribe_respond_far_reply":
                    await manager.respond_far_reply(
                        player_id,
                        message.get("replyId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_collect_world_event_remnant":
                    await manager.collect_world_event_remnant(
                        player_id,
                        message.get("remnantId", "")
                    )

                elif message_type == "tribe_revisit_map_memory":
                    await manager.revisit_map_memory(
                        player_id,
                        message.get("memoryId", "")
                    )

                elif message_type == "tribe_create_trail_marker":
                    await manager.create_trail_marker(
                        player_id,
                        message.get("markerKey", ""),
                        message.get("x", 0),
                        message.get("z", 0)
                    )

                elif message_type == "tribe_update_trail_marker":
                    await manager.update_trail_marker(
                        player_id,
                        message.get("markerId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_propose_named_landmark":
                    await manager.propose_named_landmark(
                        player_id,
                        message.get("sourceKey", ""),
                        message.get("name", ""),
                        message.get("x", 0),
                        message.get("z", 0)
                    )

                elif message_type == "tribe_support_named_landmark":
                    await manager.support_named_landmark(
                        player_id,
                        message.get("proposalId", "")
                    )

                elif message_type == "tribe_visit_neutral_sanctuary":
                    await manager.visit_neutral_sanctuary(
                        player_id,
                        message.get("sanctuaryId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_curate_collection_wall":
                    await manager.curate_collection_wall_item(
                        player_id,
                        message.get("candidateId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_support_myth_claim":
                    await manager.support_myth_claim(
                        player_id,
                        message.get("claimId", ""),
                        message.get("interpretationKey", "")
                    )

                elif message_type == "tribe_support_history_fact":
                    await manager.support_history_fact_claim(
                        player_id,
                        message.get("claimId", ""),
                        message.get("versionKey", "")
                    )

                elif message_type == "tribe_resolve_emergency_choice":
                    await manager.resolve_emergency_choice(
                        player_id,
                        message.get("choiceId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_complete_emergency_followup":
                    await manager.complete_emergency_followup_task(
                        player_id,
                        message.get("taskId", "")
                    )

                elif message_type == "tribe_send_mutual_aid_alert":
                    await manager.send_mutual_aid_alert(
                        player_id,
                        message.get("sourceKind", ""),
                        message.get("sourceId", ""),
                        message.get("targetTribeId", "")
                    )

                elif message_type == "tribe_answer_mutual_aid_alert":
                    await manager.answer_mutual_aid_alert(
                        player_id,
                        message.get("alertId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_choose_season_taboo":
                    await manager.choose_season_taboo(
                        player_id,
                        message.get("tabooKey", "")
                    )

                elif message_type == "tribe_observe_season_taboo":
                    await manager.observe_season_taboo(player_id)

                elif message_type == "tribe_break_season_taboo":
                    await manager.break_season_taboo(player_id)

                elif message_type == "tribe_complete_season_taboo_remedy":
                    await manager.complete_season_taboo_remedy(
                        player_id,
                        message.get("remedyId", "")
                    )

                elif message_type == "tribe_start_standing_ritual":
                    await manager.start_standing_ritual(
                        player_id,
                        message.get("ritualKey", "")
                    )

                elif message_type == "tribe_join_standing_ritual":
                    await manager.join_standing_ritual(
                        player_id,
                        message.get("stanceKey", "")
                    )

                elif message_type == "tribe_complete_standing_ritual":
                    await manager.complete_standing_ritual(player_id)

                elif message_type == "tribe_start_migration_plan":
                    await manager.start_migration_plan(
                        player_id,
                        message.get("planKey", "")
                    )

                elif message_type == "tribe_advance_migration_plan":
                    await manager.advance_migration_plan(player_id)

                elif message_type == "tribe_patrol_controlled_site":
                    await manager.patrol_controlled_resource_site(
                        player_id,
                        message.get("siteId", "")
                    )

                elif message_type == "tribe_relay_controlled_site":
                    await manager.relay_controlled_resource_site(
                        player_id,
                        message.get("siteId", "")
                    )

                elif message_type == "tribe_choose_celestial_branch":
                    await manager.choose_celestial_branch(
                        player_id,
                        message.get("windowId", ""),
                        message.get("branchKey", "")
                    )

                elif message_type == "tribe_observe_weather_sign":
                    await manager.observe_weather_sign(
                        player_id,
                        message.get("signKey", "")
                    )

                elif message_type == "tribe_enact_law":
                    await manager.enact_tribe_law(
                        player_id,
                        message.get("lawKey", "")
                    )

                elif message_type == "tribe_uphold_law":
                    await manager.uphold_tribe_law(player_id)

                elif message_type == "tribe_break_law":
                    await manager.break_tribe_law(player_id)

                elif message_type == "tribe_complete_law_remedy":
                    await manager.complete_law_remedy(
                        player_id,
                        message.get("remedyId", "")
                    )

                elif message_type == "tribe_record_shared_puzzle_fragment":
                    await manager.record_shared_puzzle_fragment(
                        player_id,
                        message.get("sourceKey", "")
                    )

                elif message_type == "tribe_complete_shared_puzzle":
                    await manager.complete_shared_puzzle(player_id)

                elif message_type == "tribe_compose_epic":
                    await manager.compose_oral_epic(player_id)

                elif message_type == "tribe_add_oral_chain_line":
                    await manager.add_oral_chain_line(
                        player_id,
                        message.get("text", "")
                    )

                elif message_type == "tribe_complete_oral_chain":
                    await manager.complete_oral_chain(player_id)

                elif message_type == "tribe_choose_oath":
                    await manager.choose_tribe_oath(
                        player_id,
                        message.get("oathKey", "")
                    )

                elif message_type == "tribe_complete_oath_task":
                    await manager.complete_oath_task(player_id)

                elif message_type == "tribe_resolve_boundary_outcome":
                    await manager.resolve_boundary_outcome(
                        player_id,
                        message.get("outcomeId", ""),
                        message.get("responseKey", "")
                    )

                elif message_type == "tribe_beast_task":
                    await manager.assign_beast_task(
                        player_id,
                        message.get("taskKey", "")
                    )

                elif message_type == "tribe_complete_season_objective":
                    await manager.complete_season_objective(
                        player_id,
                        message.get("objectiveId", "")
                    )

                elif message_type == "tribe_choose_celebration":
                    await manager.choose_season_celebration(
                        player_id,
                        message.get("choiceKey", "")
                    )

                elif message_type == "tribe_choose_beast_specialty":
                    await manager.choose_beast_specialty(
                        player_id,
                        message.get("specialtyKey", "")
                    )

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
                await manager.ensure_monthly_settlement()

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


@router.get("/api/game/seasons")
async def get_game_seasons(limit: int = Query(12, ge=1, le=24)):
    """获取赛季结算历史和当前赛季信息"""
    return manager.get_seasons_summary(limit)


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
