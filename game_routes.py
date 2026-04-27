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
from game_dream_omens import GameDreamOmenMixin
from game_ancestor_questions import GameAncestorQuestionMixin
from game_camp_shifts import GameCampShiftMixin
from game_camp_councils import GameCampCouncilMixin
from game_wonders import GameWonderMixin
from game_consensus_fire import GameConsensusFireMixin, CONSENSUS_FIRE_ACTIVE_MINUTES
from game_disaster_coop import GameDisasterCoopMixin, DISASTER_COOP_ACTIVE_MINUTES, DISASTER_COOP_TARGET
from game_echo_items import GameEchoItemMixin
from game_lost_tech import GameLostTechMixin
from game_craft_legacy import GameCraftLegacyMixin
from game_sacred_fire import GameSacredFireMixin
from game_mentorship import GameMentorshipMixin
from game_celebrations import GameCelebrationMixin
from game_night_risks import GameNightRiskMixin
from game_old_camps import GameOldCampEchoMixin
from game_border_theaters import GameBorderTheaterMixin
from game_trade_credit import GameTradeCreditMixin
from game_weather_forecast import GameWeatherForecastMixin
from game_laws import GameLawMixin
from game_shared_puzzles import GameSharedPuzzleMixin
from game_rumor_truth import GameRumorTruthMixin
from game_world_riddles import GameWorldRiddleMixin
from game_trial_grounds import GameTrialGroundMixin
from game_forbidden_edges import GameForbiddenEdgeMixin
from game_fog_trails import GameFogTrailMixin
from game_reverse_victories import GameReverseVictoryMixin
from game_apprentices import GameApprenticeExchangeMixin
from game_guest_stays import GameGuestStayMixin
from game_camp_debts import GameCampDebtMixin
from game_ash_counts import GameAshCountMixin
from game_messengers import GameMessengerMixin
from game_personal_tokens import GamePersonalTokenMixin
from game_personal_oaths import GamePersonalOathMixin
from game_visitors import GameVisitorMixin
from game_far_returns import GameFarReturnMixin
from game_traveler_songs import GameTravelerSongMixin
from game_trail_markers import GameTrailMarkerMixin
from game_sanctuaries import GameSanctuaryMixin
from game_collection_wall import GameCollectionWallMixin
from game_lost_items import GameLostItemMixin
from game_public_secrets import GamePublicSecretMixin
from game_renown_pledges import GameRenownPledgeMixin
from game_customs import GameCustomMixin
from game_boundary_temperatures import GameBoundaryTemperatureMixin
from game_alliance_signals import GameAllianceSignalMixin
from game_common_judges import GameCommonJudgeMixin
from game_dispute_witness import GameDisputeWitnessMixin
from game_old_grudges import GameOldGrudgeMixin
from game_shadow_tasks import GameShadowTaskMixin
from game_cave_races import GameCaveRaceMixin
from game_oral_maps import GameOralMapMixin
from game_named_landmarks import GameNamedLandmarkMixin
from game_living_legends import GameLivingLegendMixin
from game_tribe_progression import GameTribeProgressionMixin
from game_conflict import GameConflictMixin
from game_routes_connection import GameRouteConnectionMixin
from game_routes_personal import GameRoutePersonalMixin
from game_routes_tribe_actions import GameRouteTribeActionsMixin

class ConnectionManager(GameRouteConnectionMixin, GameRoutePersonalMixin, GameRouteTribeActionsMixin, GameConflictMixin, GameEmergencyChoiceMixin, GameMutualAidAlertMixin, GameStoryEventsMixin, GameSeasonTabooMixin, GameStandingRitualMixin, GameBeastLinkMixin, GameMigrationMixin, GameCelestialMixin, GameHistoryFactMixin, GameCaravanMixin, GameCookingMixin, GameDrumRhythmMixin, GameGroupEmoteMixin, GameDreamOmenMixin, GameAncestorQuestionMixin, GameCampShiftMixin, GameCampCouncilMixin, GameWonderMixin, GameConsensusFireMixin, GameDisasterCoopMixin, GameEchoItemMixin, GameLostTechMixin, GameCraftLegacyMixin, GameSacredFireMixin, GameMentorshipMixin, GameCelebrationMixin, GameNightRiskMixin, GameOldCampEchoMixin, GameBorderTheaterMixin, GameTradeCreditMixin, GameWeatherForecastMixin, GameLawMixin, GameSharedPuzzleMixin, GameRumorTruthMixin, GameWorldRiddleMixin, GameTrialGroundMixin, GameForbiddenEdgeMixin, GameFogTrailMixin, GameReverseVictoryMixin, GameApprenticeExchangeMixin, GameGuestStayMixin, GameCampDebtMixin, GameAshCountMixin, GameMessengerMixin, GamePersonalTokenMixin, GamePersonalOathMixin, GameVisitorMixin, GameFarReturnMixin, GameTravelerSongMixin, GameTrailMarkerMixin, GameSanctuaryMixin, GameCollectionWallMixin, GameLostItemMixin, GamePublicSecretMixin, GameRenownPledgeMixin, GameCustomMixin, GameBoundaryTemperatureMixin, GameAllianceSignalMixin, GameCommonJudgeMixin, GameDisputeWitnessMixin, GameOldGrudgeMixin, GameShadowTaskMixin, GameCaveRaceMixin, GameOralMapMixin, GameNamedLandmarkMixin, GameLivingLegendMixin, GameMythMixin, GameTribeProgressionMixin, GameWorldLogicMixin):
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
                self._rebuild_player_tribe_index(player_tribes)
            else:
                self._rebuild_player_tribe_index({})
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

    def _rebuild_player_tribe_index(self, loaded_player_tribes: dict):
        memberships: Dict[str, List[str]] = {}
        corrections = 0

        for tribe_id, tribe in self.tribes.items():
            if not isinstance(tribe, dict):
                continue
            members = tribe.setdefault("members", {})
            if not isinstance(members, dict):
                tribe["members"] = {}
                corrections += 1
                continue

            for raw_member_id, member in list(members.items()):
                if not isinstance(member, dict):
                    members.pop(raw_member_id, None)
                    corrections += 1
                    continue

                member_id = str(member.get("id") or raw_member_id)
                if member_id != raw_member_id:
                    members.pop(raw_member_id, None)
                    members[member_id] = member
                    corrections += 1
                member["id"] = member_id
                memberships.setdefault(member_id, []).append(tribe_id)

        rebuilt: Dict[str, str] = {}
        loaded = loaded_player_tribes if isinstance(loaded_player_tribes, dict) else {}
        for member_id, tribe_ids in memberships.items():
            previous_tribe_id = loaded.get(member_id)
            chosen_tribe_id = previous_tribe_id if previous_tribe_id in tribe_ids else tribe_ids[0]
            rebuilt[member_id] = chosen_tribe_id

            if len(tribe_ids) > 1:
                corrections += len(tribe_ids) - 1
                for duplicate_tribe_id in tribe_ids:
                    if duplicate_tribe_id == chosen_tribe_id:
                        continue
                    duplicate_tribe = self.tribes.get(duplicate_tribe_id)
                    if isinstance(duplicate_tribe, dict):
                        duplicate_tribe.get("members", {}).pop(member_id, None)

        stale_mappings = [
            member_id for member_id, tribe_id in loaded.items()
            if rebuilt.get(member_id) != tribe_id
        ]
        corrections += len(stale_mappings)
        self.player_tribes = rebuilt
        if corrections:
            logger.warning(f"部落成员索引已从 members 重建，修正 {corrections} 处不一致映射")

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
        if hasattr(self, "_boundary_temperature_rumor_text"):
            text, related = self._boundary_temperature_rumor_text(text, related)
        if hasattr(self, "_traveler_song_rumor_text"):
            text, related = self._traveler_song_rumor_text(text, related)
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
        if hasattr(self, "_seed_living_legend_candidate"):
            self._seed_living_legend_candidate(tribe, record)

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
        lost_tech_discount = self._lost_tech_build_discount(tribe) if tribe else 0
        craft_discount = self._craft_legacy_build_discount(tribe) if tribe else 0
        wood_discount = max(0, min(80, int(effects.get("buildCostDiscountPercent", 0) or 0) + apprentice_discount + lost_tech_discount + craft_discount))
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
        gather_bonus += self._lost_tech_ritual_gather_bonus(tribe or {})
        gather_bonus += self._craft_legacy_ritual_gather_bonus(tribe or {})
        gather_bonus += self._traveler_song_lineage_ritual_gather_bonus(tribe or {})
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
        now = datetime.now()
        now_text = now.isoformat()
        return self._active_tribe_items(
            tribe,
            "boundary_pressures",
            TRIBE_BOUNDARY_OUTCOME_LIMIT,
            now=now,
            on_expire=lambda item: self._create_boundary_pressure_aftermath(tribe, item, now_text)
        )

    def _active_boundary_truces(self, tribe: dict) -> List[dict]:
        now = datetime.now()
        now_text = now.isoformat()
        active = self._active_tribe_items(
            tribe,
            "boundary_truces",
            TRIBE_BOUNDARY_OUTCOME_LIMIT,
            now=now
        )
        for item in active:
            self._create_boundary_truce_talk_task(tribe, item, now_text)
        return active

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
                "tribePersonality": self._public_tribe_personality(tribe),
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
            "legendTitles": list(member.get("legend_titles", []) or [])[-3:],
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
            "livingLegendCandidates": self._public_living_legend_candidates(tribe),
            "livingLegendRecords": self._public_living_legend_records(tribe),
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
            "guestStayTargets": self._guest_stay_targets(tribe),
            "guestStayActions": TRIBE_GUEST_STAY_ACTIONS,
            "guestStays": self._active_guest_stays(tribe),
            "guestStayConfig": {
                "activeMinutes": TRIBE_GUEST_STAY_ACTIVE_MINUTES,
                "minRelation": TRIBE_GUEST_STAY_MIN_RELATION,
                "minTradeTrust": TRIBE_GUEST_STAY_MIN_TRADE_TRUST
            },
            "campDebts": self._public_camp_debts(tribe),
            "campDebtActions": TRIBE_CAMP_DEBT_ACTIONS,
            "campDebtRecords": self._public_camp_debt_records(tribe),
            "campDebtConfig": {
                "activeMinutes": TRIBE_CAMP_DEBT_ACTIVE_MINUTES,
                "pendingLimit": TRIBE_CAMP_DEBT_PENDING_LIMIT
            },
            "ashCounts": self._public_ash_counts(tribe),
            "ashCountActions": TRIBE_ASH_COUNT_ACTIONS,
            "ashCountRecords": self._public_ash_count_records(tribe),
            "ashLedgers": self._public_ash_ledgers(tribe),
            "ashCountConfig": {
                "activeMinutes": TRIBE_ASH_COUNT_ACTIVE_MINUTES,
                "pendingLimit": TRIBE_ASH_COUNT_PENDING_LIMIT,
                "ledgerActiveMinutes": TRIBE_ASH_LEDGER_ACTIVE_MINUTES,
                "ledgerShareTarget": TRIBE_ASH_LEDGER_PUBLIC_SHARE_TARGET
            },
            "farReplyTasks": self._public_far_reply_tasks(tribe),
            "farReplyActions": TRIBE_FAR_REPLY_ACTIONS,
            "farReplyRecords": self._recent_far_reply_records(tribe),
            "travelerSongs": self._public_traveler_songs(tribe),
            "travelerSongActions": TRIBE_TRAVELER_SONG_ACTIONS,
            "travelerSongRecords": self._public_traveler_song_records(tribe),
            "travelerSongHints": self._public_traveler_song_hints(tribe),
            "travelerSongTunes": self._public_traveler_song_tunes(tribe),
            "travelerTuneLineageActions": TRIBE_TRAVELER_TUNE_LINEAGE_ACTIONS,
            "travelerTuneLineageRecords": self._public_traveler_tune_lineage_records(tribe),
            "regionEventBonuses": self._active_region_event_bonus_summaries(tribe),
            "worldEventActions": self._world_event_action_options(tribe),
            "worldEventRemnants": self._active_world_event_remnants(tribe),
            "rumorTruthTasks": self._public_rumor_truth_tasks(tribe),
            "rumorTruthActions": self._public_rumor_truth_actions(),
            "rumorTruthRecords": self._public_rumor_truth_records(tribe),
            "rumorTruthHints": self._public_rumor_truth_hints(tribe),
            "publicSecrets": self._public_public_secrets(tribe),
            "publicSecretActions": TRIBE_PUBLIC_SECRET_ACTIONS,
            "publicSecretRecords": self._public_secret_records(tribe),
            "mapMemories": self._active_map_memories(tribe),
            "mapTileTraces": self._active_map_tile_traces(tribe),
            "mapTileTraceActions": TRIBE_MAP_TILE_TRACE_ACTIONS,
            "oldCampEchoes": self._public_old_camp_echoes(tribe),
            "oldCampEchoActions": TRIBE_OLD_CAMP_ECHO_ACTIONS,
            "oldCampRecords": self._public_old_camp_records(tribe),
            "borderTheaters": self._public_border_theaters(tribe),
            "borderTheaterActions": TRIBE_BORDER_THEATER_ACTIONS,
            "borderTheaterRecords": self._public_border_theater_records(tribe),
            "caveRaces": self._public_cave_races(tribe),
            "caveRaceActions": TRIBE_CAVE_RACE_ACTIONS,
            "caveRescueRecords": self._recent_cave_rescue_records(tribe),
            "caveReturnMarks": self._public_cave_return_marks(tribe),
            "caveReturnActions": self._public_cave_return_actions(),
            "caveReturnRecords": self._recent_cave_return_records(tribe),
            "caveRouteBonuses": self._public_cave_route_bonuses(tribe),
            "oralMapSources": self._public_oral_map_sources(tribe),
            "oralMapActions": self._public_oral_map_actions(),
            "oralMapRecords": self._public_oral_map_records(tribe),
            "oralMapLineages": self._public_oral_map_lineages(tribe),
            "oralMapReferences": self._public_oral_map_references(tribe),
            "oralMapNarrators": self._public_oral_map_narrators(tribe),
            "fogTrails": self._public_fog_trails(tribe),
            "fogTrailActions": self._public_fog_trail_actions(tribe),
            "fogTrailRecords": self._public_fog_trail_records(tribe),
            "forbiddenEdges": self._public_forbidden_edges(tribe),
            "forbiddenEdgeActions": self._public_forbidden_edge_actions(tribe),
            "forbiddenEdgeRecords": self._public_forbidden_edge_records(tribe),
            "forbiddenEdgeRouteExperiences": self._public_forbidden_edge_route_experiences(tribe),
            "forbiddenEdgeRouteProofs": self._public_forbidden_edge_route_proofs(tribe),
            "forbiddenEdgeRouteProofActions": self._public_forbidden_edge_route_proof_actions(),
            "forbiddenEdgeRouteProofRecords": self._public_forbidden_edge_route_proof_records(tribe),
            "trailMarkers": self._public_trail_markers(tribe),
            "trailMarkerTypes": TRIBE_TRAIL_MARKER_TYPES,
            "trailMarkerActions": self._public_trail_marker_actions(),
            "neutralSanctuaries": self._public_neutral_sanctuaries(tribe),
            "neutralSanctuaryActions": self._public_neutral_sanctuary_actions(),
            "neutralSanctuaryBlessings": self._public_neutral_sanctuary_blessings(tribe),
            "echoItems": self._public_echo_items(tribe),
            "echoItemTypes": TRIBE_ECHO_ITEM_TYPES,
            "echoItemExperiences": TRIBE_ECHO_ITEM_EXPERIENCES,
            "echoItemRecords": self._public_echo_item_records(tribe),
            "collectionWall": self._public_collection_wall(tribe),
            "collectionCandidates": self._collection_wall_candidates(tribe),
            "collectionActions": TRIBE_COLLECTION_ACTIONS,
            "collectionInfluences": self._active_collection_influences(tribe),
            "lostItems": self._public_lost_items(tribe),
            "lostItemActions": TRIBE_LOST_ITEM_ACTIONS,
            "lostItemRecords": self._public_lost_item_records(tribe),
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
            "allianceSignals": self._public_alliance_signals(tribe),
            "allianceSignalInfluences": self._public_alliance_signal_influences(tribe),
            "allianceSignalConfig": {
                "activeMinutes": TRIBE_ALLIANCE_SIGNAL_ACTIVE_MINUTES,
                "minRelation": TRIBE_ALLIANCE_SIGNAL_MIN_RELATION,
                "minTradeTrust": TRIBE_ALLIANCE_SIGNAL_MIN_TRADE_TRUST
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
            "seasonTabooEvidence": self._public_season_taboo_evidence(tribe),
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
            "lostTech": self._public_lost_tech_state(tribe),
            "lostTechSources": self._public_lost_tech_sources(tribe),
            "lostTechOptions": TRIBE_LOST_TECH_OPTIONS,
            "lostTechConfig": {
                "fragmentTarget": TRIBE_LOST_TECH_FRAGMENT_TARGET,
                "activeMinutes": TRIBE_LOST_TECH_ACTIVE_MINUTES
            },
            "craftLegacy": self._public_craft_legacy(tribe),
            "craftLegacyStyles": TRIBE_CRAFT_LEGACY_STYLES,
            "craftLegacyConfig": {
                "activeMinutes": TRIBE_CRAFT_LEGACY_ACTIVE_MINUTES,
                "minEchoMemories": TRIBE_CRAFT_LEGACY_MIN_ECHO_MEMORIES
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
            "dreamOmen": self._public_dream_omen(tribe),
            "dreamOmenSources": self._public_dream_omen_sources(tribe),
            "dreamOmenActions": self._public_dream_omen_actions(),
            "dreamOmenRecords": self._public_dream_omen_records(tribe),
            "ancestorQuestion": self._public_ancestor_question(tribe),
            "ancestorQuestionOptions": self._public_ancestor_question_options(tribe),
            "ancestorQuestionAnswers": self._public_ancestor_question_answers(),
            "ancestorQuestionBiases": self._public_ancestor_question_biases(tribe),
            "ancestorQuestionRecords": self._public_ancestor_question_records(tribe),
            "campShift": self._active_camp_shift(tribe),
            "campShiftOptions": TRIBE_CAMP_SHIFT_OPTIONS if not self._active_camp_shift(tribe) else {},
            "campShiftRecords": self._public_camp_shift_records(tribe),
            "campShiftConfig": {
                "activeMinutes": TRIBE_CAMP_SHIFT_ACTIVE_MINUTES,
                "target": TRIBE_CAMP_SHIFT_TARGET,
                "memberContribution": TRIBE_CAMP_SHIFT_MEMBER_CONTRIBUTION
            },
            "campCouncil": self._public_camp_council(tribe),
            "campCouncilActions": TRIBE_CAMP_COUNCIL_ACTIONS,
            "campCouncilRecords": self._public_camp_council_records(tribe),
            "campCouncilConfig": {
                "activeMinutes": TRIBE_CAMP_COUNCIL_ACTIVE_MINUTES,
                "target": TRIBE_CAMP_COUNCIL_TARGET
            },
            "wonderProject": self._public_wonder_project(tribe),
            "wonderActions": self._public_wonder_actions(tribe),
            "wonderAuras": self._public_wonder_auras(tribe),
            "wonderRecords": self._public_wonder_records(tribe),
            "wonderConfig": {
                "activeMinutes": TRIBE_WONDER_ACTIVE_MINUTES,
                "target": TRIBE_WONDER_TARGET,
                "auraMinutes": TRIBE_WONDER_AURA_MINUTES
            },
            "consensusFire": self._public_consensus_fire(tribe),
            "consensusFireActions": self._public_consensus_fire_actions(),
            "consensusFireBonuses": self._public_consensus_fire_bonuses(tribe),
            "consensusFireRecords": self._public_consensus_fire_records(tribe),
            "consensusFireConfig": {
                "activeMinutes": CONSENSUS_FIRE_ACTIVE_MINUTES
            },
            "disasterCoopTasks": self._public_disaster_coop_tasks(tribe),
            "disasterCoopActions": self._public_disaster_coop_actions(),
            "disasterCoopRecords": self._public_disaster_coop_records(tribe),
            "disasterCoopConfig": {
                "activeMinutes": DISASTER_COOP_ACTIVE_MINUTES,
                "target": DISASTER_COOP_TARGET
            },
            "tribeLaw": self._public_tribe_law(tribe),
            "tribeLawOptions": {} if self._active_tribe_law(tribe) else TRIBE_LAW_OPTIONS,
            "tribeLawRemedies": self._public_law_remedies(tribe),
            "tribeLawRecords": self._public_law_records(tribe),
            "sharedPuzzle": self._public_shared_puzzle(tribe),
            "sharedPuzzleOptions": self._public_shared_puzzle_options(tribe),
            "sharedPuzzleRecords": self._public_shared_puzzle_records(tribe),
            "worldRiddles": self._public_world_riddles(tribe),
            "worldRiddlePredictions": self._public_world_riddle_predictions(),
            "worldRiddleInfluences": self._public_world_riddle_influences(tribe),
            "worldRiddleRecords": self._public_world_riddle_records(tribe),
            "trialGrounds": self._public_trial_grounds(tribe),
            "trialGroundActions": TRIBE_TRIAL_GROUND_ACTIONS,
            "trialGroundRecords": self._public_trial_records(tribe),
            "trialGroundConfig": {
                "activeMinutes": TRIBE_TRIAL_GROUND_ACTIVE_MINUTES,
                "radius": TRIBE_TRIAL_GROUND_RADIUS
            },
            "campTrial": self._public_camp_trial(tribe),
            "campTrialOptions": {} if self._active_camp_trial(tribe) else TRIBE_CAMP_TRIAL_OPTIONS,
            "campTrialRecords": self._public_camp_trial_records(tribe),
            "campTrialConfig": {
                "activeMinutes": TRIBE_CAMP_TRIAL_ACTIVE_MINUTES,
                "target": TRIBE_CAMP_TRIAL_TARGET,
                "minParticipants": TRIBE_CAMP_TRIAL_MIN_PARTICIPANTS
            },
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
            "personalDarkOathOptions": PLAYER_DARK_OATH_OPTIONS,
            "personalDarkOathRecords": self._public_dark_oath_records(tribe),
            "personalDarkOathRemedies": self._public_dark_oath_remedies(tribe),
            "personalDarkOathConfig": {
                "activeMinutes": PLAYER_DARK_OATH_ACTIVE_MINUTES,
                "minPersonalRenown": PLAYER_DARK_OATH_MIN_RENOWN,
                "failurePenalty": PLAYER_DARK_OATH_FAILURE_PENALTY
            },
            "renownPledgeOptions": TRIBE_RENOWN_PLEDGE_OPTIONS,
            "renownPledges": self._active_renown_pledges(tribe),
            "renownPledgeRecords": self._public_renown_pledge_records(tribe),
            "renownPledgeConfig": {
                "activeMinutes": TRIBE_RENOWN_PLEDGE_ACTIVE_MINUTES,
                "minPersonalRenown": TRIBE_RENOWN_PLEDGE_MIN_PERSONAL_RENOWN,
                "stake": TRIBE_RENOWN_PLEDGE_STAKE,
                "failurePenalty": TRIBE_RENOWN_PLEDGE_FAILURE_PENALTY
            },
            "tribeCustoms": self._public_tribe_customs(tribe),
            "tribeCustomOptions": self._public_tribe_custom_options(tribe),
            "tribePersonality": self._public_tribe_personality(tribe),
            "reverseVictoryTargets": self._public_reverse_victory_targets(tribe),
            "reverseVictoryRecords": self._recent_reverse_victory_records(tribe),
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
            "boundaryTemperatures": self._public_boundary_temperatures(tribe),
            "boundaryTemperatureActions": TRIBE_BOUNDARY_TEMPERATURE_ACTIONS,
            "boundaryTemperatureRecords": self._public_boundary_temperature_records(tribe),
            "allianceSignalTargets": self._public_alliance_signal_targets(tribe),
            "allianceSignalLocations": self._public_alliance_signal_locations(tribe),
            "allianceSignalActions": TRIBE_ALLIANCE_SIGNAL_ACTIONS,
            "allianceSignalHints": self._active_alliance_signal_hints(tribe),
            "allianceSignalRecords": self._public_alliance_signal_records(tribe),
            "commonJudgeCases": self._public_common_judge_cases(tribe),
            "commonJudgeActions": TRIBE_COMMON_JUDGE_ACTIONS,
            "commonJudgeRecords": self._public_common_judge_records(tribe),
            "disputeWitnessStones": self._public_dispute_witness_stones(tribe),
            "disputeWitnessActions": TRIBE_DISPUTE_WITNESS_ACTIONS,
            "disputeWitnessRecords": self._public_dispute_witness_records(tribe),
            "disputeWitnessEvidence": self._public_dispute_witness_evidence(tribe),
            "disputeWitnessLineages": self._public_dispute_witness_lineages(tribe),
            "oldGrudgeTargets": self._public_old_grudge_targets(tribe),
            "oldGrudgeAnchors": TRIBE_OLD_GRUDGE_ANCHORS,
            "oldGrudgeSeals": self._public_old_grudge_seals(tribe),
            "oldGrudgeSealActions": TRIBE_OLD_GRUDGE_SEAL_ACTIONS,
            "oldGrudgeWakeTasks": self._public_old_grudge_wake_tasks(tribe),
            "oldGrudgeRecords": self._public_old_grudge_records(tribe),
            "shadowTask": self._public_shadow_task(tribe),
            "shadowTaskActions": TRIBE_SHADOW_TASK_ACTIONS,
            "shadowTaskRecords": self._public_shadow_task_records(tribe),
            "boundaryPressures": self._active_boundary_pressures(tribe),
            "boundaryTruces": self._active_boundary_truces(tribe),
            "boundaryFollowupTasks": self._public_boundary_followup_tasks(tribe),
            "diplomacyCouncilSites": self._public_diplomacy_council_sites(tribe),
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
                "votes": active_votes,
                "guestStayTargets": self._wanderer_guest_stay_targets(),
                "guestStayActions": TRIBE_GUEST_STAY_ACTIONS,
                "guestStayConfig": {
                    "activeMinutes": TRIBE_GUEST_STAY_ACTIVE_MINUTES,
                    "minRelation": TRIBE_GUEST_STAY_MIN_RELATION,
                    "minTradeTrust": TRIBE_GUEST_STAY_MIN_TRADE_TRUST
                }
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
        self._cleanup_tribe_runtime_state(tribe)
        self._save_tribe_state()

        for member_id in list(tribe.get("members", {}).keys()):
            await self.send_personal_message(member_id, self.get_player_tribe_state(member_id))

        await self.broadcast(self.get_tribes_overview())
        await self._broadcast_current_map()




















































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

                elif message_type == "personal_dark_oath_start":
                    await manager.start_personal_dark_oath(
                        player_id,
                        message.get("oathKey", "")
                    )

                elif message_type == "personal_dark_oath_reveal":
                    await manager.reveal_personal_dark_oath(player_id)

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

                elif message_type == "tribe_support_living_legend":
                    await manager.support_living_legend(
                        player_id,
                        message.get("candidateId", "")
                    )

                elif message_type == "tribe_respond_living_legend":
                    await manager.respond_living_legend(
                        player_id,
                        message.get("candidateId", ""),
                        message.get("actionKey", "witness")
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

                elif message_type == "tribe_tune_boundary_temperature":
                    await manager.tune_boundary_temperature(
                        player_id,
                        message.get("otherTribeId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_send_alliance_signal":
                    await manager.send_alliance_signal(
                        player_id,
                        message.get("otherTribeId", "") or message.get("targetTribeId", ""),
                        message.get("locationId", "") or message.get("actionKey", ""),
                        message.get("signalKey", "")
                    )

                elif message_type == "tribe_submit_common_judge":
                    await manager.submit_common_judge(
                        player_id,
                        message.get("caseId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_tend_dispute_witness":
                    await manager.tend_dispute_witness_stone(
                        player_id,
                        message.get("stoneId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_seal_old_grudge":
                    await manager.seal_old_grudge(
                        player_id,
                        message.get("otherTribeId", ""),
                        message.get("anchorKey", "")
                    )

                elif message_type == "tribe_tend_old_grudge":
                    await manager.tend_old_grudge_seal(
                        player_id,
                        message.get("sealId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_settle_old_grudge_wake":
                    await manager.settle_old_grudge_wake_task(
                        player_id,
                        message.get("taskId", "")
                    )

                elif message_type == "tribe_advance_shadow_task":
                    await manager.advance_shadow_task(
                        player_id,
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

                elif message_type == "tribe_complete_reverse_victory":
                    await manager.complete_reverse_victory(
                        player_id,
                        message.get("targetKey", "")
                    )

                elif message_type == "tribe_create_echo_item":
                    await manager.create_echo_item(
                        player_id,
                        message.get("itemKey", "")
                    )

                elif message_type == "tribe_add_echo_item_memory":
                    await manager.add_echo_item_memory(
                        player_id,
                        message.get("itemId", ""),
                        message.get("experienceKey", "")
                    )

                elif message_type == "tribe_transfer_echo_item":
                    await manager.transfer_echo_item(
                        player_id,
                        message.get("itemId", ""),
                        message.get("targetId", "")
                    )

                elif message_type == "tribe_record_lost_tech":
                    await manager.record_lost_tech_fragment(
                        player_id,
                        message.get("sourceKey", "")
                    )

                elif message_type == "tribe_restore_lost_tech":
                    await manager.restore_lost_tech(
                        player_id,
                        message.get("techKey", "")
                    )

                elif message_type == "tribe_establish_craft_legacy":
                    await manager.establish_craft_legacy(
                        player_id,
                        message.get("candidateId", ""),
                        message.get("styleKey", "")
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

                elif message_type == "tribe_start_dream_omen":
                    await manager.start_dream_omen(
                        player_id,
                        message.get("sourceId", "")
                    )

                elif message_type == "tribe_resolve_dream_omen":
                    await manager.resolve_dream_omen(
                        player_id,
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_start_ancestor_question":
                    await manager.start_ancestor_question(
                        player_id,
                        message.get("questionKey", "")
                    )

                elif message_type == "tribe_answer_ancestor_question":
                    await manager.answer_ancestor_question(
                        player_id,
                        message.get("answerKey", "")
                    )

                elif message_type == "tribe_start_camp_shift":
                    await manager.start_camp_shift(
                        player_id,
                        message.get("shiftKey", "")
                    )

                elif message_type == "tribe_join_camp_shift":
                    await manager.join_camp_shift(player_id)

                elif message_type == "tribe_advance_camp_council":
                    await manager.advance_camp_council(
                        player_id,
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_contribute_wonder":
                    await manager.contribute_wonder(
                        player_id,
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_resolve_consensus_fire":
                    await manager.resolve_consensus_fire(
                        player_id,
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_resolve_disaster_coop":
                    await manager.resolve_disaster_coop(
                        player_id,
                        message.get("taskId", ""),
                        message.get("actionKey", "")
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
                        message.get("raceId", ""),
                        message.get("methodKey", "echo_locate")
                    )

                elif message_type == "tribe_organize_cave_return_mark":
                    await manager.organize_cave_return_mark(
                        player_id,
                        message.get("markId", ""),
                        message.get("actionKey", "tie_echo_rope")
                    )

                elif message_type == "tribe_compose_oral_map":
                    await manager.compose_oral_map(
                        player_id,
                        message.get("sourceId", ""),
                        message.get("actionKey", "cave_route")
                    )

                elif message_type == "tribe_explore_fog_trail":
                    await manager.explore_fog_trail(
                        player_id,
                        message.get("trailId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_explore_forbidden_edge":
                    await manager.explore_forbidden_edge(
                        player_id,
                        message.get("edgeId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_mark_forbidden_edge_route_proof":
                    await manager.mark_forbidden_edge_route_proof(
                        player_id,
                        message.get("proofId", ""),
                        message.get("actionKey", "")
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

                elif message_type == "tribe_start_guest_stay":
                    await manager.start_guest_stay(
                        player_id,
                        message.get("targetTribeId", ""),
                        message.get("actionKey", "")
                    )
                elif message_type == "tribe_resolve_camp_debt":
                    await manager.resolve_camp_debt(
                        player_id,
                        message.get("debtId", ""),
                        message.get("actionKey", "")
                    )
                elif message_type == "tribe_resolve_ash_count":
                    await manager.resolve_ash_count(
                        player_id,
                        message.get("ashId", ""),
                        message.get("actionKey", "")
                    )
                elif message_type == "tribe_endorse_ash_ledger":
                    await manager.endorse_ash_ledger(
                        player_id,
                        message.get("ledgerId", "")
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

                elif message_type == "tribe_complete_dark_oath_remedy":
                    await manager.complete_personal_dark_oath_remedy(
                        player_id,
                        message.get("remedyId", "")
                    )

                elif message_type == "tribe_respond_far_reply":
                    await manager.respond_far_reply(
                        player_id,
                        message.get("replyId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_resolve_traveler_song":
                    await manager.resolve_traveler_song(
                        player_id,
                        message.get("songId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_promote_traveler_song_tune":
                    await manager.promote_traveler_song_tune(
                        player_id,
                        message.get("recordId", "")
                    )

                elif message_type == "tribe_reference_traveler_tune":
                    await manager.reference_traveler_song_tune(
                        player_id,
                        message.get("tuneId", ""),
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

                elif message_type == "tribe_settle_map_tile_trace":
                    await manager.settle_map_tile_trace(
                        player_id,
                        message.get("traceId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_revisit_old_camp_echo":
                    await manager.revisit_old_camp_echo(
                        player_id,
                        message.get("echoId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_perform_border_theater":
                    await manager.perform_border_theater(
                        player_id,
                        message.get("theaterId", ""),
                        message.get("actionKey", "")
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

                elif message_type == "tribe_resolve_lost_item":
                    await manager.resolve_lost_item(
                        player_id,
                        message.get("itemId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_resolve_public_secret":
                    await manager.resolve_public_secret(
                        player_id,
                        message.get("secretId", ""),
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
                    await manager.break_season_taboo(
                        player_id,
                        message.get("temptationKey", "")
                    )

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

                elif message_type == "tribe_commit_custom_practice":
                    await manager.commit_tribe_custom_practice(
                        player_id,
                        message.get("customKey", "")
                    )

                elif message_type == "tribe_record_shared_puzzle_fragment":
                    await manager.record_shared_puzzle_fragment(
                        player_id,
                        message.get("sourceKey", "")
                    )

                elif message_type == "tribe_complete_shared_puzzle":
                    await manager.complete_shared_puzzle(player_id)

                elif message_type == "tribe_resolve_rumor_truth":
                    await manager.resolve_rumor_truth(
                        player_id,
                        message.get("rumorId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_solve_world_riddle":
                    await manager.solve_world_riddle(
                        player_id,
                        message.get("riddleId", ""),
                        message.get("predictionKey", "")
                    )

                elif message_type == "tribe_complete_trial_ground":
                    await manager.complete_trial_ground(
                        player_id,
                        message.get("trialId", ""),
                        message.get("actionKey", "")
                    )

                elif message_type == "tribe_start_camp_trial":
                    await manager.start_camp_trial(
                        player_id,
                        message.get("trialKey", "")
                    )

                elif message_type == "tribe_join_camp_trial":
                    await manager.join_camp_trial(player_id)

                elif message_type == "tribe_complete_camp_trial":
                    await manager.complete_camp_trial(player_id)

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
