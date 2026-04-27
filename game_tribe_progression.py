import random
import math
from datetime import datetime, timedelta
from typing import Optional

from game_config import *


class GameTribeProgressionMixin:
    def _region_building_bonus(self, tribe: dict, region_type: str, phase: str) -> tuple[dict, str]:
        bonus = TRIBE_REGION_BUILDING_BONUSES.get(region_type or "")
        if not bonus or not self._is_tribe_building_built(tribe, bonus.get("buildingKey", "")):
            return {}, ""
        return dict(bonus.get(phase, {}) or {}), bonus.get("label", "")

    def _apply_region_bonus_rewards(self, tribe: dict, rewards: dict, label: str, reward_parts: list):
        if not rewards:
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, text in (("wood", "木材"), ("stone", "石块")):
            amount = int(rewards.get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                reward_parts.append(f"{label}{text}+{amount}")
        food = int(rewards.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"{label}食物+{food}")
        discovery = int(rewards.get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"{label}发现+{discovery}")
        renown = int(rewards.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"{label}声望+{renown}")

    def _active_region_event_bonuses(self, tribe: dict) -> list:
        bonuses = []
        for building_key, bonus in TRIBE_REGION_EVENT_BONUSES.items():
            if self._is_tribe_building_built(tribe, building_key):
                bonuses.append({"buildingKey": building_key, **bonus})
        return bonuses

    def _active_region_event_bonus_summaries(self, tribe: dict) -> list:
        return [
            {"label": bonus.get("label", ""), "summary": bonus.get("summary", "")}
            for bonus in self._active_region_event_bonuses(tribe)
        ]

    def _region_event_bonus_value(self, tribe: dict, key: str) -> int:
        return sum(int(bonus.get(key, 0) or 0) for bonus in self._active_region_event_bonuses(tribe))

    def _apply_world_event_region_bonuses(self, tribe: dict, event_key: str, reward: dict, reward_parts: list) -> list:
        labels = []
        for bonus in self._active_region_event_bonuses(tribe):
            if event_key not in (bonus.get("worldEventKeys") or []):
                continue
            bonus_reward = dict(bonus.get("worldEventReward") or {})
            if not bonus_reward:
                continue
            labels.append(bonus.get("label", "区域设施"))
            for key, amount in bonus_reward.items():
                reward[key] = int(reward.get(key, 0) or 0) + int(amount or 0)
            reward_parts.append(f"{bonus.get('label', '区域设施')}响应")
        return labels

    def _world_event_action_available(self, tribe: dict, event: dict, action: dict) -> bool:
        requires = dict(action.get("requires") or {})
        building_key = requires.get("building")
        if building_key and not self._is_tribe_building_built(tribe, building_key):
            return False
        region_types = requires.get("regionTypes") or []
        if region_types and event.get("regionType") not in region_types:
            return False
        return True

    def _world_event_action_options(self, tribe: dict) -> dict:
        result = {}
        for event_key, actions in WORLD_EVENT_ACTIONS.items():
            options = []
            for action_key, action in actions.items():
                requires = dict(action.get("requires") or {})
                building_key = requires.get("building")
                if building_key and not self._is_tribe_building_built(tribe, building_key):
                    continue
                options.append({
                    "key": action_key,
                    "label": action.get("label", action_key),
                    "summary": action.get("summary", ""),
                    "regionTypes": list(requires.get("regionTypes") or []),
                    "buildingKey": building_key
                })
            if options:
                result[event_key] = options
        return result

    def _world_event_action_plan(self, tribe: dict, event: dict, action_key: str) -> tuple[Optional[str], Optional[dict]]:
        event_key = event.get("key")
        actions = WORLD_EVENT_ACTIONS.get(event_key, {})
        default_key = "hunt" if event_key == "herd" else ""
        safe_key = action_key if action_key in actions else default_key
        if not safe_key:
            return None, None
        action = actions.get(safe_key)
        if not action or not self._world_event_action_available(tribe, event, action):
            if default_key and default_key in actions:
                return default_key, actions[default_key]
            return None, None
        return safe_key, action

    def _reward_summary_text(self, rewards: dict) -> str:
        labels = {
            "wood": "木材",
            "stone": "石块",
            "food": "食物",
            "discoveryProgress": "发现",
            "renown": "声望",
            "tradeReputation": "贸易信誉"
        }
        parts = []
        for key, label in labels.items():
            amount = int((rewards or {}).get(key, 0) or 0)
            if amount:
                parts.append(f"{label}+{amount}")
        return "、".join(parts)

    def _active_world_event_remnants(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for remnant in tribe.get("world_event_remnants", []) or []:
            if not isinstance(remnant, dict) or remnant.get("collectedAt"):
                continue
            active_until = remnant.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    pass
            remnant["rewardLabel"] = self._reward_summary_text(remnant.get("reward") or {})
            active.append(remnant)
        if len(active) != len(tribe.get("world_event_remnants", []) or []):
            tribe["world_event_remnants"] = active[-WORLD_EVENT_REMNANT_LIMIT:]
        return active[-WORLD_EVENT_REMNANT_LIMIT:]

    def _build_world_event_remnant(self, tribe: dict, event: dict, action_key: Optional[str], action_plan: Optional[dict], member: dict) -> Optional[dict]:
        remnant_plan = dict((action_plan or {}).get("remnant") or {})
        if not remnant_plan:
            return None

        now = datetime.now()
        active_until = now + timedelta(minutes=WORLD_EVENT_REMNANT_ACTIVE_MINUTES)
        angle = self._weather_rng.random() * math.pi * 2
        distance = 2.0 + self._weather_rng.random() * max(2.0, float(event.get("radius", 12) or 12) * 0.25)
        remnant = {
            "id": f"event_remnant_{tribe.get('id')}_{int(now.timestamp())}_{self._weather_rng.randint(100, 999)}",
            "tribeId": tribe.get("id"),
            "type": "world_event_remnant",
            "remnantKey": remnant_plan.get("key", action_key or "event_trace"),
            "label": remnant_plan.get("label", "事件余迹"),
            "summary": remnant_plan.get("summary", "刚刚处理过的事件在这里留下短时痕迹。"),
            "x": float(event.get("x", 0) or 0) + math.cos(angle) * distance,
            "z": float(event.get("z", 0) or 0) + math.sin(angle) * distance,
            "size": 0.9,
            "regionType": event.get("regionType"),
            "regionLabel": event.get("regionLabel"),
            "sourceEventTitle": event.get("title", "世界事件"),
            "sourceActionKey": action_key,
            "sourceActionLabel": (action_plan or {}).get("label", "处理"),
            "reward": dict(remnant_plan.get("reward") or {}),
            "rewardLabel": self._reward_summary_text(remnant_plan.get("reward") or {}),
            "createdAt": now.isoformat(),
            "activeUntil": active_until.isoformat(),
            "createdBy": member.get("name", "成员")
        }
        remnants = self._active_world_event_remnants(tribe)
        tribe["world_event_remnants"] = [*remnants, remnant][-WORLD_EVENT_REMNANT_LIMIT:]
        return remnant

    def _apply_world_event_remnant_rewards(self, tribe: dict, rewards: dict, reward_parts: list):
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((rewards or {}).get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                reward_parts.append(f"{label}+{amount}")
        food = int((rewards or {}).get("food", 0) or 0)
        if food:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) + food)
            reward_parts.append(f"食物+{food}")
        discovery = int((rewards or {}).get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现进度+{discovery}")
        renown = int((rewards or {}).get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        trade = int((rewards or {}).get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")

    async def collect_world_event_remnant(self, player_id: str, remnant_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        remnants = self._active_world_event_remnants(tribe)
        remnant = next((item for item in remnants if item.get("id") == remnant_id), None)
        if not remnant:
            await self._send_tribe_error(player_id, "事件余迹已经消散")
            return

        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = []
        rewards = dict(remnant.get("reward") or {})
        self._apply_world_event_remnant_rewards(tribe, rewards, reward_parts)
        tribe["world_event_remnants"] = [item for item in remnants if item.get("id") != remnant_id]

        detail = f"{member.get('name', '成员')} 整理了{remnant.get('regionLabel', '附近区域')}的{remnant.get('label', '事件余迹')}。"
        if reward_parts:
            detail += f" 收获：{'、'.join(reward_parts)}。"
        memory = self._record_map_memory(
            tribe,
            "event_trace",
            remnant.get("label", "事件余迹"),
            f"{member.get('name', '成员')}整理过这里，{remnant.get('sourceEventTitle', '世界事件')}留下的痕迹仍可被后来者辨认。",
            float(remnant.get("x", 0) or 0),
            float(remnant.get("z", 0) or 0),
            remnant.get("id"),
            member.get("name", "成员")
        )
        if memory:
            detail += " 这里被记入活地图。"
        self._add_tribe_history(
            tribe,
            "world_event",
            "整理事件余迹",
            detail,
            player_id,
            {
                "kind": "world_event_remnant",
                "remnantId": remnant.get("id"),
                "remnantKey": remnant.get("remnantKey"),
                "label": remnant.get("label"),
                "regionLabel": remnant.get("regionLabel"),
                "memberName": member.get("name", "成员"),
                "sourceEventTitle": remnant.get("sourceEventTitle"),
                "sourceActionLabel": remnant.get("sourceActionLabel"),
                "reward": rewards,
                "rewardParts": reward_parts
            }
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    def _active_map_memories(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for memory in tribe.get("map_memories", []) or []:
            if not isinstance(memory, dict) or memory.get("status") == "resolved":
                continue
            active_until = memory.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    pass
            active.append(memory)
        if len(active) != len(tribe.get("map_memories", []) or []):
            tribe["map_memories"] = active[-TRIBE_MAP_MEMORY_LIMIT:]
        return active[-TRIBE_MAP_MEMORY_LIMIT:]

    def _record_map_memory(self, tribe: dict, memory_kind: str, label: str, summary: str, x: float, z: float, source_id: str = "", actor_name: str = "") -> Optional[dict]:
        if not tribe:
            return None
        active = self._active_map_memories(tribe)
        dedupe_id = f"{memory_kind}:{source_id}" if source_id else ""
        if dedupe_id and any(item.get("dedupeId") == dedupe_id for item in active):
            return None
        now = datetime.now()
        reward = dict(TRIBE_MAP_MEMORY_REWARDS.get(memory_kind, TRIBE_MAP_MEMORY_REWARDS["event_trace"]))
        memory = {
            "id": f"map_memory_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "type": "map_memory_trace",
            "status": "active",
            "kind": memory_kind,
            "label": label or "活地图记忆",
            "summary": summary or "这里留下了可被后来者重新读取的痕迹。",
            "x": max(-490, min(490, float(x or 0))),
            "z": max(-490, min(490, float(z or 0))),
            "sourceId": source_id,
            "dedupeId": dedupe_id,
            "actorName": actor_name,
            "reward": reward,
            "rewardLabel": self._reward_summary_text(reward),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_MAP_MEMORY_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["map_memories"] = [*active, memory][-TRIBE_MAP_MEMORY_LIMIT:]
        return memory

    def _apply_map_memory_reward(self, tribe: dict, rewards: dict) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((rewards or {}).get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = int((rewards or {}).get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        discovery = int((rewards or {}).get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现进度+{discovery}")
        trade = int((rewards or {}).get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        renown = int((rewards or {}).get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        return reward_parts

    async def revisit_map_memory(self, player_id: str, memory_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        memories = self._active_map_memories(tribe)
        memory = next((item for item in memories if item.get("id") == memory_id), None)
        if not memory:
            await self._send_tribe_error(player_id, "这处地图记忆已经淡去")
            return
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_map_memory_reward(tribe, memory.get("reward") or {})
        memory["status"] = "resolved"
        memory["revisitedBy"] = member.get("name", "成员")
        memory["revisitedAt"] = datetime.now().isoformat()
        tribe["map_memories"] = [item for item in memories if item.get("id") != memory_id]
        detail = f"{member.get('name', '成员')} 重访了{memory.get('label', '活地图记忆')}，把旧痕迹重新读进部落路线。"
        if reward_parts:
            detail += f" 收获：{'、'.join(reward_parts)}。"
        self._add_tribe_history(
            tribe,
            "world_event",
            "重访活地图记忆",
            detail,
            player_id,
            {"kind": "map_memory", **memory, "rewardParts": reward_parts}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    def _create_trade_route_sites(self, tribe: dict, outcome: dict, site: Optional[dict]):
        other_id = outcome.get("otherTribeId")
        other_tribe = self.tribes.get(other_id) if other_id else None
        if not tribe or not other_tribe or not site:
            return []

        other_site_id = outcome.get("otherSiteId")
        other_site = next((
            item for item in (other_tribe.get("scouted_resource_sites", []) or [])
            if isinstance(item, dict) and item.get("id") == other_site_id
        ), None) or {}
        site_ids = sorted([str(site.get("id") or ""), str(other_site_id or "")])
        shared_id = f"trade_route_{abs(hash('|'.join(site_ids))) % 100000000}"
        now = datetime.now()
        now_text = now.isoformat()
        active_until = datetime.fromtimestamp(now.timestamp() + TRIBE_TRADE_ROUTE_SITE_ACTIVE_MINUTES * 60).isoformat()
        x1 = float(site.get("x", 0) or 0)
        z1 = float(site.get("z", 0) or 0)
        x2 = float(other_site.get("x", x1) or x1)
        z2 = float(other_site.get("z", z1) or z1)
        mid_x = (x1 + x2) / 2
        mid_z = (z1 + z2) / 2
        created = []

        for target_tribe, partner_tribe, source_site, offset in (
            (tribe, other_tribe, site, -2.2),
            (other_tribe, tribe, other_site or site, 2.2)
        ):
            target_id = target_tribe.get("id")
            if not target_id:
                continue
            existing = next((
                item for item in (target_tribe.get("trade_route_sites", []) or [])
                if isinstance(item, dict) and item.get("sharedRouteId") == shared_id
            ), None)
            if existing:
                continue
            resource_label = source_site.get("resourceLabel") or outcome.get("siteLabel") or "交换资源"
            reward = dict(source_site.get("reward") or outcome.get("reward") or {})
            route_site = {
                "id": f"{shared_id}_{target_id}",
                "tribeId": target_id,
                "type": "trade_route_site",
                "label": "交换通路贸易点",
                "resourceLabel": resource_label,
                "partnerTribeId": partner_tribe.get("id"),
                "partnerTribeName": partner_tribe.get("name", "邻近部落"),
                "x": max(-490, min(490, mid_x + offset)),
                "z": max(-490, min(490, mid_z - offset)),
                "size": 1.05,
                "reward": reward,
                "sharedRouteId": shared_id,
                "sourceOutcomeId": outcome.get("id"),
                "createdAt": now_text,
                "activeUntil": active_until,
                "lastCollectedAt": None,
                "collectCount": 0,
                "marketCollectTarget": TRIBE_TRADE_ROUTE_MARKET_COLLECTS
            }
            target_tribe.setdefault("trade_route_sites", []).append(route_site)
            target_tribe["trade_route_sites"] = target_tribe["trade_route_sites"][-TRIBE_TRADE_ROUTE_SITE_LIMIT:]
            created.append(route_site)
        return created

    def _trade_route_market_active(self, site: dict) -> bool:
        market_until = site.get("marketUntil")
        if not market_until:
            return False
        try:
            return datetime.fromisoformat(market_until) > datetime.now()
        except (TypeError, ValueError):
            return False

    def _trade_route_market_focus_label(self, site: dict) -> str:
        reward = dict(site.get("reward") or {})
        if int(reward.get("food", 0) or 0):
            return "食物互市"
        if int(reward.get("stone", 0) or 0):
            return "石料互市"
        if int(reward.get("wood", 0) or 0):
            return "木料互市"
        if int(reward.get("discoveryProgress", 0) or 0):
            return "旧物互市"
        return "杂货互市"

    def _append_trade_route_market_task(self, tribe: dict, site: dict, now_text: str):
        partner_id = site.get("partnerTribeId")
        if not tribe or not partner_id:
            return
        task = {
            "id": f"border_market_{site.get('sharedRouteId')}_{tribe.get('id')}",
            "status": "pending",
            "kind": "border_market",
            "title": "边市议价",
            "summary": f"与 {site.get('partnerTribeName', '邻近部落')} 的交换通路升成了短时边市，整理礼物和口头约定可把这轮互市转成更稳定的往来。",
            "otherTribeId": partner_id,
            "otherTribeName": site.get("partnerTribeName", "邻近部落"),
            "foodReward": TRIBE_TRADE_ROUTE_MARKET_FOOD,
            "tradeReward": TRIBE_TRADE_ROUTE_MARKET_TRADE,
            "renownReward": TRIBE_TRADE_ROUTE_MARKET_RENOWN,
            "relationDelta": 1,
            "tradeTrustDelta": 2,
            "pactChance": round(self._market_pact_success_chance(tribe, partner_id), 2),
            "pactMinutes": TRIBE_MARKET_PACT_MINUTES,
            "sourceTradeRouteId": site.get("id"),
            "createdAt": now_text
        }
        self._append_boundary_followup_task(tribe, task)

    def _activate_trade_route_market(self, site: dict, now: datetime) -> list:
        shared_id = site.get("sharedRouteId")
        if not shared_id:
            return []
        market_until = datetime.fromtimestamp(now.timestamp() + TRIBE_TRADE_ROUTE_MARKET_MINUTES * 60).isoformat()
        activated = []
        myth_tribes = []
        myth_x = float(site.get("x", 0) or 0)
        myth_z = float(site.get("z", 0) or 0)
        for target_tribe in self.tribes.values():
            route_site = next((
                item for item in (target_tribe.get("trade_route_sites", []) or [])
                if isinstance(item, dict) and item.get("sharedRouteId") == shared_id
            ), None)
            if not route_site:
                continue
            route_site["label"] = "交换通路边市"
            route_site["marketUntil"] = market_until
            route_site["marketStartedAt"] = now.isoformat()
            route_site["marketRewardLabel"] = self._trade_route_market_focus_label(route_site)
            route_site["marketCount"] = int(route_site.get("marketCount", 0) or 0) + 1
            route_site["collectCount"] = 0
            try:
                active_until = max(datetime.fromisoformat(route_site.get("activeUntil")), datetime.fromisoformat(market_until))
                route_site["activeUntil"] = active_until.isoformat()
            except (TypeError, ValueError):
                route_site["activeUntil"] = market_until
            partner_id = route_site.get("partnerTribeId")
            if partner_id:
                progress = target_tribe.setdefault("boundary_relations", {}).setdefault(partner_id, {})
                progress["tradeTrust"] = max(0, min(10, int(progress.get("tradeTrust", 0) or 0) + 1))
                progress["score"] = min(9, int(progress.get("score", 0) or 0) + 1)
                progress["lastAction"] = "border_market_open"
                progress["lastActionAt"] = now.isoformat()
            self._append_trade_route_market_task(target_tribe, route_site, now.isoformat())
            if hasattr(self, "_append_nomad_caravan_route"):
                self._append_nomad_caravan_route(target_tribe, route_site, now)
            self._record_map_memory(
                target_tribe,
                "border_market",
                "旧边市火圈",
                f"与{route_site.get('partnerTribeName', '邻近部落')}的短时边市曾在这里开张，路线仍带着互市口信。",
                float(route_site.get("x", 0) or 0),
                float(route_site.get("z", 0) or 0),
                f"market:{shared_id}:{target_tribe.get('id')}",
                "边市"
            )
            myth_tribes.append(target_tribe)
            myth_x = float(route_site.get("x", myth_x) or myth_x)
            myth_z = float(route_site.get("z", myth_z) or myth_z)
            activated.append(target_tribe.get("id"))
        self._open_shared_myth_claim(
            myth_tribes,
            "border_market",
            "边市开张",
            "同一处短时边市在边界两侧开张，相关部落都可以争论这是互市佳兆、旧路显现还是守边誓言。",
            myth_x,
            myth_z,
            f"market:{shared_id}",
            "边市"
        )
        return activated

    def _apply_trade_route_market_reward(self, tribe: dict, site: dict, reward_parts: list):
        if not self._trade_route_market_active(site):
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward = dict(site.get("reward") or {})
        if int(reward.get("wood", 0) or 0):
            storage["wood"] = int(storage.get("wood", 0) or 0) + 2
            tribe["food"] = int(tribe.get("food", 0) or 0) + 1
            reward_parts.extend(["边市木材+2", "边市食物+1"])
        elif int(reward.get("stone", 0) or 0):
            storage["stone"] = int(storage.get("stone", 0) or 0) + 2
            storage["wood"] = int(storage.get("wood", 0) or 0) + 1
            reward_parts.extend(["边市石块+2", "边市木材+1"])
        elif int(reward.get("food", 0) or 0):
            tribe["food"] = int(tribe.get("food", 0) or 0) + 3
            reward_parts.append("边市食物+3")
        elif int(reward.get("discoveryProgress", 0) or 0):
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + 1
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
            reward_parts.extend(["边市发现+1", "边市声望+1"])
        tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + 1
        reward_parts.append("边市贸易信誉+1")

    def _active_market_pacts(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for pact in tribe.get("market_pacts", []) or []:
            if not isinstance(pact, dict):
                continue
            active_until = pact.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    pass
            active.append(pact)
        if len(active) != len(tribe.get("market_pacts", []) or []):
            tribe["market_pacts"] = active[-TRIBE_MARKET_PACT_LIMIT:]
        return active[-TRIBE_MARKET_PACT_LIMIT:]

    def _market_pact_between(self, tribe: dict, other_tribe_id: str) -> Optional[dict]:
        if not tribe or not other_tribe_id:
            return None
        return next((
            pact for pact in self._active_market_pacts(tribe)
            if pact.get("otherTribeId") == other_tribe_id
        ), None)

    def _market_pact_success_chance(self, tribe: dict, other_tribe_id: str) -> float:
        relation = (tribe.get("boundary_relations", {}) or {}).get(other_tribe_id, {}) or {}
        trust = max(0, int(relation.get("tradeTrust", 0) or 0))
        score = max(0, int(relation.get("score", 0) or 0))
        chance = (
            TRIBE_MARKET_PACT_CHANCE_BASE
            + trust * TRIBE_MARKET_PACT_TRUST_BONUS
            + score * TRIBE_MARKET_PACT_RELATION_BONUS
        )
        return max(0.1, min(0.9, chance))

    def _create_market_pact(self, tribe: dict, other_tribe: dict, source_task_id: str, now_text: str) -> Optional[dict]:
        if not tribe or not other_tribe:
            return None
        tribe_id = tribe.get("id")
        other_tribe_id = other_tribe.get("id")
        if not tribe_id or not other_tribe_id:
            return None
        shared_id = f"market_pact_{source_task_id}".replace(" ", "_")
        active_until = datetime.fromtimestamp(
            datetime.now().timestamp() + TRIBE_MARKET_PACT_MINUTES * 60
        ).isoformat()
        summary = "边市议价沉淀成互市约定，短期内贸易、联合守望和资源点争执都会更容易转向合作。"
        created = None
        for target_tribe, partner_tribe in ((tribe, other_tribe), (other_tribe, tribe)):
            target_id = target_tribe.get("id")
            partner_id = partner_tribe.get("id")
            target_tribe["market_pacts"] = [
                pact for pact in (target_tribe.get("market_pacts", []) or [])
                if isinstance(pact, dict) and pact.get("otherTribeId") != partner_id
            ]
            pact = {
                "id": f"{shared_id}_{target_id}",
                "sharedPactId": shared_id,
                "title": "互市约定",
                "summary": summary,
                "otherTribeId": partner_id,
                "otherTribeName": partner_tribe.get("name", "邻近部落"),
                "sourceTaskId": source_task_id,
                "createdAt": now_text,
                "activeUntil": active_until,
                "tradeDiscount": TRIBE_MARKET_PACT_TRADE_DISCOUNT,
                "tradeReputationBonus": TRIBE_MARKET_PACT_TRADE_REPUTATION_BONUS,
                "jointWatchTradeTrust": TRIBE_MARKET_PACT_JOINT_WATCH_TRADE_TRUST,
                "contestRelief": TRIBE_MARKET_PACT_CONTEST_RELIEF
            }
            target_tribe.setdefault("market_pacts", []).append(pact)
            target_tribe["market_pacts"] = target_tribe["market_pacts"][-TRIBE_MARKET_PACT_LIMIT:]
            if target_id == tribe_id:
                created = pact
        if hasattr(self, "_open_covenant_messenger_task_pair"):
            self._open_covenant_messenger_task_pair(
                tribe,
                other_tribe,
                "market_pact",
                shared_id,
                "互市信使",
                f"{tribe.get('name', '部落')} 与 {other_tribe.get('name', '邻近部落')} 定下互市约定，需要成员把木牌、干鱼或石印送到对岸，让约定被双方承认。",
                now_text
            )
        return created

    def _diplomacy_council_signals(self, tribe: dict) -> list:
        signals = []
        for pact in self._active_market_pacts(tribe):
            other_id = pact.get("otherTribeId")
            if other_id:
                signals.append({
                    "kind": "market_pact",
                    "id": pact.get("id"),
                    "otherTribeId": other_id,
                    "otherTribeName": pact.get("otherTribeName", "邻近部落"),
                    "label": pact.get("title", "互市约定")
                })
        for truce in self._active_boundary_truces(tribe):
            other_id = truce.get("otherTribeId")
            if other_id:
                signals.append({
                    "kind": "boundary_truce",
                    "id": truce.get("id"),
                    "otherTribeId": other_id,
                    "otherTribeName": truce.get("otherTribeName", "邻近部落"),
                    "label": truce.get("title", "停争保护")
                })
        for task in tribe.get("war_diplomacy_tasks", []) or []:
            if not isinstance(task, dict) or task.get("status") != "pending":
                continue
            other_id = task.get("otherTribeId")
            if other_id:
                signals.append({
                    "kind": "war_diplomacy",
                    "id": task.get("id"),
                    "otherTribeId": other_id,
                    "otherTribeName": task.get("otherTribeName", "邻近部落"),
                    "label": task.get("modeLabel", "停战外交")
                })
        return signals

    def _diplomacy_council_position(self, tribe: dict, participant_ids: list) -> tuple[float, float]:
        points = []
        own_center = (tribe.get("camp") or {}).get("center") or {}
        if own_center:
            points.append((float(own_center.get("x", 0) or 0), float(own_center.get("z", 0) or 0)))
        for participant_id in participant_ids:
            other = self.tribes.get(participant_id) or {}
            center = (other.get("camp") or {}).get("center") or {}
            if center:
                points.append((float(center.get("x", 0) or 0), float(center.get("z", 0) or 0)))
        if not points:
            return 0, 0
        x = sum(point[0] for point in points) / len(points)
        z = sum(point[1] for point in points) / len(points)
        return max(-480, min(480, x)), max(-480, min(480, z))

    def _ensure_diplomacy_council_site(self, tribe: dict, now: datetime) -> Optional[dict]:
        if not tribe or not tribe.get("id"):
            return None
        signals = self._diplomacy_council_signals(tribe)
        if len(signals) < TRIBE_DIPLOMACY_COUNCIL_SIGNAL_TARGET:
            return None
        participant_ids = []
        for signal in signals:
            other_id = signal.get("otherTribeId")
            if other_id and other_id not in participant_ids:
                participant_ids.append(other_id)
        if not participant_ids:
            return None
        active = [
            site for site in (tribe.get("diplomacy_council_sites", []) or [])
            if isinstance(site, dict) and site.get("status") == "active"
        ]
        for site in active:
            try:
                if datetime.fromisoformat(site.get("activeUntil", "")) <= now:
                    continue
            except (TypeError, ValueError):
                pass
            if any(participant_id in (site.get("participantTribeIds") or []) for participant_id in participant_ids):
                return site
        x, z = self._diplomacy_council_position(tribe, participant_ids)
        active_until = datetime.fromtimestamp(now.timestamp() + TRIBE_DIPLOMACY_COUNCIL_MINUTES * 60).isoformat()
        participant_names = []
        for participant_id in participant_ids:
            other = self.tribes.get(participant_id) or {}
            participant_names.append(other.get("name", "邻近部落"))
        site = {
            "id": f"diplomacy_council_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "type": "diplomacy_council_site",
            "status": "active",
            "label": "大议会与边市节",
            "title": "大议会与边市节",
            "summary": f"{len(signals)} 条互市/停争信号聚到中立火圈，可以公开选择停战、共享洞口或封锁不稳边市。",
            "x": x,
            "z": z,
            "size": 1.15,
            "signalCount": len(signals),
            "signals": signals[-5:],
            "participantTribeIds": participant_ids,
            "participantTribeNames": participant_names,
            "createdAt": now.isoformat(),
            "activeUntil": active_until
        }
        tribe.setdefault("diplomacy_council_sites", []).append(site)
        tribe["diplomacy_council_sites"] = tribe["diplomacy_council_sites"][-TRIBE_DIPLOMACY_COUNCIL_LIMIT:]
        return site

    def _active_diplomacy_council_sites(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        self._ensure_diplomacy_council_site(tribe, now)
        active = []
        for site in tribe.get("diplomacy_council_sites", []) or []:
            if not isinstance(site, dict) or site.get("status") != "active":
                continue
            active_until = site.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        site["status"] = "expired"
                        continue
                except (TypeError, ValueError):
                    pass
            active.append(site)
        if len(active) != len(tribe.get("diplomacy_council_sites", []) or []):
            tribe["diplomacy_council_sites"] = [
                site for site in (tribe.get("diplomacy_council_sites", []) or [])
                if isinstance(site, dict) and site.get("status") == "active"
            ][-TRIBE_DIPLOMACY_COUNCIL_LIMIT:]
        return active[-TRIBE_DIPLOMACY_COUNCIL_LIMIT:]

    def _remove_market_pact_between(self, tribe: dict, other_tribe_id: str):
        if not tribe or not other_tribe_id:
            return
        tribe["market_pacts"] = [
            pact for pact in (tribe.get("market_pacts", []) or [])
            if isinstance(pact, dict) and pact.get("otherTribeId") != other_tribe_id
        ]

    def _append_boundary_followup_task(self, tribe: dict, task: dict):
        if not tribe or not task:
            return
        tasks = [
            item for item in (tribe.get("boundary_followup_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") != task.get("id")
        ]
        tasks.append(task)
        tribe["boundary_followup_tasks"] = tasks[-TRIBE_BOUNDARY_FOLLOWUP_LIMIT:]

    def _create_boundary_pressure_aftermath(self, tribe: dict, pressure: dict, now_text: str):
        if not tribe or not pressure:
            return
        pressure_id = pressure.get("id")
        if not pressure_id:
            return
        kind = "pressure_watch" if pressure.get("state") == "pressured" else "pressure_withdraw"
        task_id = f"boundary_followup_{pressure_id}_{tribe.get('id')}"
        title = "压力余波"
        summary = f"与 {pressure.get('otherTribeName', '其他部落')} 的短时边界压力已经散去，族人可以整理标记，避免余怨继续发酵。"
        relation_delta = 1 if pressure.get("state") == "pressured" else 0
        pressure_relief = 1 if pressure.get("state") == "pressured" else 0
        self._append_boundary_followup_task(tribe, {
            "id": task_id,
            "status": "pending",
            "kind": kind,
            "title": title,
            "summary": summary,
            "otherTribeId": pressure.get("otherTribeId"),
            "otherTribeName": pressure.get("otherTribeName", "其他部落"),
            "woodCost": TRIBE_BOUNDARY_PRESSURE_AFTERMATH_WOOD_COST,
            "renownReward": TRIBE_BOUNDARY_PRESSURE_AFTERMATH_RENOWN,
            "relationDelta": relation_delta,
            "pressureRelief": pressure_relief,
            "sourcePressureId": pressure_id,
            "createdAt": now_text
        })

    def _create_boundary_truce_talk_task(self, tribe: dict, truce: dict, now_text: str):
        if not tribe or not truce:
            return
        truce_id = truce.get("id")
        if not truce_id:
            return
        food_reward = TRIBE_BOUNDARY_TRUCE_TALK_FOOD_REWARD + self._region_event_bonus_value(tribe, "truceTalkFoodBonus")
        self._append_boundary_followup_task(tribe, {
            "id": f"boundary_truce_talk_{truce_id}_{tribe.get('id')}",
            "status": "pending",
            "kind": "truce_talk",
            "title": "停争谈判",
            "summary": f"趁与 {truce.get('otherTribeName', '其他部落')} 的停争标记仍在，整理边界礼物，把短暂停火转成真正的往来。",
            "otherTribeId": truce.get("otherTribeId"),
            "otherTribeName": truce.get("otherTribeName", "其他部落"),
            "foodReward": food_reward,
            "tradeReward": TRIBE_BOUNDARY_TRUCE_TALK_TRADE_REWARD,
            "renownReward": 2,
            "relationDelta": 1,
            "tradeTrustDelta": 1,
            "regionEventBonuses": self._active_region_event_bonus_summaries(tribe),
            "sourceTruceId": truce_id,
            "createdAt": now_text
        })

    def _create_boundary_hostile_wear_task(self, tribe: dict, other_tribe_id: str, other_name: str, now_text: str):
        if not tribe or not other_tribe_id:
            return
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        last_wear = relation.get("lastHostileWearAt")
        if last_wear:
            try:
                if (datetime.now() - datetime.fromisoformat(last_wear)).total_seconds() < TRIBE_BOUNDARY_ACTION_COOLDOWN_SECONDS:
                    return
            except (TypeError, ValueError):
                pass
        relation["lastHostileWearAt"] = now_text
        tribe["food"] = max(0, int(tribe.get("food", 0) or 0) - TRIBE_BOUNDARY_HOSTILE_WEAR_FOOD_LOSS)
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_loss = max(0, TRIBE_BOUNDARY_HOSTILE_WEAR_WOOD_LOSS - self._region_event_bonus_value(tribe, "hostileWearWoodRelief"))
        storage["wood"] = max(0, int(storage.get("wood", 0) or 0) - wood_loss)
        self._append_boundary_followup_task(tribe, {
            "id": f"boundary_hostile_wear_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "pending",
            "kind": "hostile_wear",
            "title": "敌意损耗",
            "summary": f"与 {other_name or '其他部落'} 的长期敌意拖慢了营地补给，已经损耗少量食物和木材；整理守边可换回声望并缓解战争压力。",
            "otherTribeId": other_tribe_id,
            "otherTribeName": other_name or "其他部落",
            "renownReward": 4,
            "pressureRelief": 1,
            "regionEventBonuses": self._active_region_event_bonus_summaries(tribe),
            "createdAt": now_text
        })

    def _public_boundary_followup_tasks(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("boundary_followup_tasks", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-TRIBE_BOUNDARY_FOLLOWUP_LIMIT:]

    async def complete_boundary_followup_task(self, player_id: str, task_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((
            item for item in (tribe.get("boundary_followup_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") == task_id and item.get("status") == "pending"
        ), None)
        if not task:
            await self._send_tribe_error(player_id, "没有找到可处理的边界后续")
            return
        wood_cost = int(task.get("woodCost", 0) or 0)
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        if int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"处理边界后续需要木材 {wood_cost}")
            return
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        food_reward = int(task.get("foodReward", 0) or 0)
        renown_reward = int(task.get("renownReward", 0) or 0)
        trade_reward = int(task.get("tradeReward", 0) or 0)
        tribe["food"] = int(tribe.get("food", 0) or 0) + food_reward
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown_reward
        tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_reward
        other_tribe_id = task.get("otherTribeId")
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        relation_delta = int(task.get("relationDelta", 0) or 0)
        trade_trust_delta = int(task.get("tradeTrustDelta", 0) or 0)
        pressure_relief = int(task.get("pressureRelief", 0) or 0)
        if relation_delta:
            relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
        if trade_trust_delta:
            relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trade_trust_delta))
        if pressure_relief:
            relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - pressure_relief)
            relation["canDeclareWar"] = False
        now_text = datetime.now().isoformat()
        relation["lastAction"] = f"boundary_followup_{task.get('kind')}"
        relation["lastActionAt"] = now_text
        pact_created = None
        pact_failed = False
        other_tribe = self.tribes.get(other_tribe_id) if other_tribe_id else None
        if task.get("kind") == "border_market" and other_tribe:
            pact_chance = self._market_pact_success_chance(tribe, other_tribe_id)
            if random.random() <= pact_chance:
                pact_created = self._create_market_pact(tribe, other_tribe, task_id, now_text)
            else:
                pact_failed = True
        if task.get("kind") == "truce_talk" and other_tribe and hasattr(self, "_open_covenant_messenger_task_pair"):
            self._open_covenant_messenger_task_pair(
                tribe,
                other_tribe,
                "boundary_truce",
                task_id,
                "停争信使",
                f"与 {task.get('otherTribeName', '邻近部落')} 的停争谈判已经整理出礼物和口信，需要成员亲自护送，免得短暂停火又退回猜疑。",
                now_text
            )
        task["status"] = "completed"
        task["completedBy"] = player_id
        task["completedAt"] = now_text
        member = tribe.get("members", {}).get(player_id, {})
        reward_bits = []
        if wood_cost:
            reward_bits.append(f"木材-{wood_cost}")
        if food_reward:
            reward_bits.append(f"食物+{food_reward}")
        if renown_reward:
            reward_bits.append(f"声望+{renown_reward}")
        if trade_reward:
            reward_bits.append(f"贸易信誉+{trade_reward}")
        if relation_delta:
            reward_bits.append(f"关系{relation_delta:+d}")
        if trade_trust_delta:
            reward_bits.append(f"信任+{trade_trust_delta}")
        if pressure_relief:
            reward_bits.append(f"战争压力-{pressure_relief}")
        if pact_created:
            reward_bits.append(f"互市约定{TRIBE_MARKET_PACT_MINUTES}分钟")
        elif pact_failed:
            reward_bits.append("互市约定未成")
        if task.get("kind") == "truce_talk" and other_tribe:
            reward_bits.append("停争信使待护送")
        detail = f"{member.get('name', '成员')} 处理{task.get('title', '边界后续')}：{'、'.join(reward_bits) or '边界局势稳定'}。"
        history_related = {"kind": "boundary_followup", "taskId": task_id, "otherTribeId": other_tribe_id}
        if pact_created:
            history_related["marketPact"] = pact_created
        self._add_tribe_history(tribe, "governance", "边界后续", detail, player_id, history_related)
        if pact_created and other_tribe:
            other_detail = f"{tribe.get('name', '部落')} 与本部落定下互市约定，贸易、联合守望和资源点争执会获得轻量修正。"
            self._add_tribe_history(other_tribe, "trade", "互市约定", other_detail, player_id, {"kind": "market_pact", "otherTribeId": tribe_id, "sourceTaskId": task_id})
            await self._notify_tribe(other_tribe_id, other_detail)
            await self._publish_world_rumor(
                "trade",
                "互市约定",
                f"{tribe.get('name', '部落')} 与 {other_tribe.get('name', '部落')} 把边市议价沉淀成了短期互市约定。",
                {"tribeId": tribe_id, "otherTribeId": other_tribe_id, "pactMinutes": TRIBE_MARKET_PACT_MINUTES}
            )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        if pact_created and other_tribe_id:
            await self.broadcast_tribe_state(other_tribe_id)

    async def resolve_diplomacy_council_site(self, player_id: str, council_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以主持大议会")
            return
        site = next((
            item for item in self._active_diplomacy_council_sites(tribe)
            if isinstance(item, dict) and item.get("id") == council_id
        ), None)
        if not site:
            await self._send_tribe_error(player_id, "这处大议会会场已经散场")
            return
        action = TRIBE_DIPLOMACY_COUNCIL_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知的大议会议题")
            return
        food_cost = int(action.get("foodCost", 0) or 0)
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"主持大议会需要公共食物{food_cost}")
            return

        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        renown_reward = int(action.get("renown", 0) or 0)
        trade_reward = int(action.get("tradeReputation", 0) or 0)
        discovery_reward = int(action.get("discoveryProgress", 0) or 0)
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown_reward
        tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_reward
        tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery_reward

        now_text = datetime.now().isoformat()
        participant_ids = list(site.get("participantTribeIds") or [])
        relation_delta = int(action.get("relationDelta", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        pressure_relief = int(action.get("warPressureRelief", 0) or 0)
        affected_tribe_ids = {tribe_id}
        for other_id in participant_ids:
            other_tribe = self.tribes.get(other_id)
            relation = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            if pressure_relief:
                relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - pressure_relief)
                relation["canDeclareWar"] = False
            relation["lastAction"] = f"diplomacy_council_{action_key}"
            relation["lastActionAt"] = now_text
            if action.get("closeMarketPacts"):
                self._remove_market_pact_between(tribe, other_id)
            if other_tribe:
                other_relation = other_tribe.setdefault("boundary_relations", {}).setdefault(tribe_id, {})
                if relation_delta:
                    other_relation["score"] = max(-9, min(9, int(other_relation.get("score", 0) or 0) + relation_delta))
                if trust_delta:
                    other_relation["tradeTrust"] = max(0, min(10, int(other_relation.get("tradeTrust", 0) or 0) + trust_delta))
                if pressure_relief:
                    other_relation["warPressure"] = max(0, int(other_relation.get("warPressure", 0) or 0) - pressure_relief)
                    other_relation["canDeclareWar"] = False
                other_relation["lastAction"] = f"incoming_diplomacy_council_{action_key}"
                other_relation["lastActionAt"] = now_text
                if discovery_reward:
                    other_tribe["discovery_progress"] = int(other_tribe.get("discovery_progress", 0) or 0) + discovery_reward
                if trade_reward:
                    other_tribe["trade_reputation"] = int(other_tribe.get("trade_reputation", 0) or 0) + trade_reward
                if action.get("closeMarketPacts"):
                    self._remove_market_pact_between(other_tribe, tribe_id)
                affected_tribe_ids.add(other_id)

        site["status"] = "resolved"
        site["resolvedBy"] = player_id
        site["resolvedAt"] = now_text
        site["resolvedAction"] = action_key
        reward_bits = []
        if food_cost:
            reward_bits.append(f"食物-{food_cost}")
        if renown_reward:
            reward_bits.append(f"声望+{renown_reward}")
        if trade_reward:
            reward_bits.append(f"贸易信誉+{trade_reward}")
        if discovery_reward:
            reward_bits.append(f"发现+{discovery_reward}")
        if relation_delta:
            reward_bits.append(f"关系{relation_delta:+d}")
        if trust_delta:
            reward_bits.append(f"信任{trust_delta:+d}")
        if pressure_relief:
            reward_bits.append(f"战争压力-{pressure_relief}")
        if action.get("closeMarketPacts"):
            reward_bits.append("互市约定封存")
        detail = f"{member.get('name', '成员')} 在{site.get('title', '大议会')}主持“{action.get('label', '议题')}”：{action.get('summary', '')} {'、'.join(reward_bits)}。"
        record = {
            "kind": "diplomacy_council",
            "councilId": council_id,
            "actionKey": action_key,
            "actionLabel": action.get("label"),
            "participantTribeIds": participant_ids,
            "participantTribeNames": site.get("participantTribeNames", []),
            "rewardParts": reward_bits,
            "createdAt": site.get("createdAt"),
            "resolvedAt": now_text
        }
        for target_id in affected_tribe_ids:
            target = self.tribes.get(target_id)
            if target:
                self._add_tribe_history(target, "governance", "大议会与边市节", detail, player_id, record)
                await self._notify_tribe(target_id, detail)
        await self._publish_world_rumor(
            "trade",
            "大议会与边市节",
            f"{tribe.get('name', '部落')} 在中立火圈主持“{action.get('label', '议题')}”，把多条互市/停争信号变成公开外交结果。",
            {"tribeId": tribe_id, "councilId": council_id, "action": action_key}
        )
        for target_id in affected_tribe_ids:
            await self.broadcast_tribe_state(target_id)
        await self._broadcast_current_map()

    def _ensure_boundary_outcome_legacy(self, tribe: dict, relation: dict):
        if not tribe or not relation:
            return
        state = relation.get("state")
        if state not in TRIBE_BOUNDARY_OUTCOME_TEMPLATES:
            return
        other_tribe_id = relation.get("otherTribeId")
        if not other_tribe_id:
            return
        relation_records = tribe.setdefault("boundary_relations", {})
        progress = relation_records.setdefault(other_tribe_id, {})
        if progress.get("lastOutcomeState") == state:
            return
        pending = tribe.setdefault("boundary_outcomes", [])
        duplicate = next((
            item for item in pending
            if item.get("otherTribeId") == other_tribe_id and item.get("state") == state and item.get("status") == "pending"
        ), None)
        if duplicate:
            return
        template = TRIBE_BOUNDARY_OUTCOME_TEMPLATES.get(state, {})
        pending.append({
            "id": f"boundary_outcome_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "state": state,
            "title": template.get("title", "边界事件"),
            "summary": template.get("summary", ""),
            "otherTribeId": other_tribe_id,
            "otherTribeName": relation.get("otherTribeName", "其他部落"),
            "distance": relation.get("distance"),
            "reward": {
                "wood": int(template.get("wood", 0) or 0),
                "stone": int(template.get("stone", 0) or 0),
                "food": int(template.get("food", 0) or 0),
                "renown": int(template.get("renown", 0) or 0),
                "tradeReputation": int(template.get("tradeReputation", 0) or 0),
                "discoveryProgress": int(template.get("discoveryProgress", 0) or 0)
            },
            "status": "pending",
            "createdAt": datetime.now().isoformat()
        })
        tribe["boundary_outcomes"] = pending[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
        progress["lastOutcomeState"] = state

    def _ensure_boundary_outcome(self, tribe: dict, relation: dict):
        affected_tribe_ids = set()
        if not tribe or not relation:
            return affected_tribe_ids
        state = relation.get("state")
        if state not in TRIBE_BOUNDARY_OUTCOME_TEMPLATES:
            return affected_tribe_ids
        other_tribe_id = relation.get("otherTribeId")
        own_tribe_id = tribe.get("id")
        if not other_tribe_id:
            return affected_tribe_ids

        template = TRIBE_BOUNDARY_OUTCOME_TEMPLATES.get(state, {})
        pending = tribe.setdefault("boundary_outcomes", [])
        progress = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        if progress.get("lastOutcomeState") != state:
            duplicate = next((
                item for item in pending
                if item.get("otherTribeId") == other_tribe_id and item.get("state") == state and item.get("status") == "pending"
            ), None)
            if not duplicate:
                pending.append({
                    "id": f"boundary_outcome_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                    "state": state,
                    "title": template.get("title", "边界事件"),
                    "summary": template.get("summary", ""),
                    "otherTribeId": other_tribe_id,
                    "otherTribeName": relation.get("otherTribeName", "其他部落"),
                    "distance": relation.get("distance"),
                    "reward": {
                        "wood": int(template.get("wood", 0) or 0),
                        "stone": int(template.get("stone", 0) or 0),
                        "food": int(template.get("food", 0) or 0),
                        "renown": int(template.get("renown", 0) or 0),
                        "tradeReputation": int(template.get("tradeReputation", 0) or 0),
                        "discoveryProgress": int(template.get("discoveryProgress", 0) or 0)
                    },
                    "status": "pending",
                    "createdAt": datetime.now().isoformat()
                })
                tribe["boundary_outcomes"] = pending[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                if own_tribe_id:
                    affected_tribe_ids.add(own_tribe_id)
            progress["lastOutcomeState"] = state

        other_tribe = self.tribes.get(other_tribe_id)
        if own_tribe_id and other_tribe:
            other_progress = other_tribe.setdefault("boundary_relations", {}).setdefault(own_tribe_id, {})
            response_marker = f"response:{state}"
            if other_progress.get("lastOutcomeState") != response_marker:
                other_pending = other_tribe.setdefault("boundary_outcomes", [])
                other_duplicate = next((
                    item for item in other_pending
                    if item.get("otherTribeId") == own_tribe_id and item.get("state") == state and item.get("status") == "pending"
                ), None)
                if not other_duplicate:
                    other_pending.append({
                        "id": f"boundary_response_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                        "state": state,
                        "title": f"回应{template.get('title', '边界事件')}",
                        "summary": f"{tribe.get('name', '对方部落')} 已在边界上推进局势，营地可以选择回应这次变化。",
                        "otherTribeId": own_tribe_id,
                        "otherTribeName": tribe.get("name", "对方部落"),
                        "distance": relation.get("distance"),
                        "reward": {
                            "wood": max(0, int(template.get("wood", 0) or 0) // 2),
                            "stone": max(0, int(template.get("stone", 0) or 0) // 2),
                            "food": max(0, int(template.get("food", 0) or 0) // 2),
                            "renown": max(1, int(template.get("renown", 0) or 0) // 2),
                            "tradeReputation": max(0, int(template.get("tradeReputation", 0) or 0) // 2),
                            "discoveryProgress": max(0, int(template.get("discoveryProgress", 0) or 0) // 2)
                        },
                        "status": "pending",
                        "response": True,
                        "createdAt": datetime.now().isoformat()
                    })
                    other_tribe["boundary_outcomes"] = other_pending[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                    affected_tribe_ids.add(own_tribe_id)
                other_progress["lastOutcomeState"] = response_marker
        return affected_tribe_ids

    async def resolve_boundary_outcome(self, player_id: str, outcome_id: str, response_key: str = ""):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        outcomes = tribe.get("boundary_outcomes", []) or []
        outcome = next((item for item in outcomes if isinstance(item, dict) and item.get("id") == outcome_id), None)
        if not outcome or outcome.get("status") != "pending":
            await self._send_tribe_error(player_id, "这条边界结果已经处理过了")
            return

        reward = dict(outcome.get("reward") or {})
        if outcome.get("kind") == "resource_site_contest":
            response_key = response_key if response_key in {"hold", "cede", "trade_path"} else "hold"
            reward = self._apply_resource_contest_response(tribe, outcome, response_key)
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
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
        trade_rep = int(reward.get("tradeReputation", 0) or 0)
        if trade_rep:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_rep
            reward_parts.append(f"贸易信誉+{trade_rep}")
        progress = int(reward.get("discoveryProgress", 0) or 0)
        if progress:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + progress
            reward_parts.append(f"发现进度+{progress}")

        relation_records = tribe.setdefault("boundary_relations", {})
        relation_progress = relation_records.get(outcome.get("otherTribeId"), {})
        if outcome.get("kind") == "resource_site_contest":
            relation_delta = int(outcome.get("relationDelta", 0) or 0)
            trade_delta = int(outcome.get("tradeTrustDelta", 0) or 0)
            relation_progress["score"] = max(-9, min(9, int(relation_progress.get("score", 0) or 0) + relation_delta))
            if trade_delta:
                relation_progress["tradeTrust"] = max(0, min(9, int(relation_progress.get("tradeTrust", 0) or 0) + trade_delta))
            if relation_delta:
                reward_parts.append(f"关系{relation_delta:+d}")
            if trade_delta:
                reward_parts.append(f"信任+{trade_delta}")
            if outcome.get("marketPact"):
                reward_parts.append("互市约定修正")
        elif outcome.get("state") == "hostile":
            relation_progress["score"] = max(-9, int(relation_progress.get("score", 0) or 0) - 1)
        else:
            relation_progress["score"] = min(9, int(relation_progress.get("score", 0) or 0) + 1)
        relation_progress["lastResolvedAt"] = datetime.now().isoformat()
        relation_records[outcome.get("otherTribeId")] = relation_progress

        member = tribe.get("members", {}).get(player_id, {})
        outcome["status"] = "resolved"
        outcome["resolvedAt"] = datetime.now().isoformat()
        record = {
            "kind": "boundary_outcome",
            "title": outcome.get("title", "边界结果"),
            "summary": outcome.get("summary", ""),
            "state": outcome.get("state"),
            "responseKey": response_key,
            "responseLabel": outcome.get("responseLabel"),
            "otherTribeName": outcome.get("otherTribeName", "其他部落"),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "createdAt": outcome.get("createdAt"),
            "resolvedAt": outcome.get("resolvedAt")
        }
        detail = f"{record['memberName']} 处理了边界结果“{record['title']}”：{record['summary']} {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "governance", "处理边界结果", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "territory",
            record["title"],
            f"{tribe.get('name', '部落')} 在与 {record['otherTribeName']} 的边界上处理了“{record['title']}”。",
            {"tribeId": tribe_id, "outcomeId": outcome_id, "state": outcome.get("state")}
        )
        await self.broadcast_tribe_state(tribe_id)
        if outcome.get("kind") == "resource_site_contest" and response_key == "trade_path" and outcome.get("otherTribeId"):
            await self.broadcast_tribe_state(outcome.get("otherTribeId"))

    def _apply_resource_contest_response(self, tribe: dict, outcome: dict, response_key: str) -> dict:
        site_id = outcome.get("siteId")
        site = next((
            item for item in (tribe.get("scouted_resource_sites", []) or [])
            if isinstance(item, dict) and item.get("id") == site_id
        ), None)
        base_reward = dict(outcome.get("reward") or {})
        if response_key == "cede":
            outcome["responseLabel"] = "让渡"
            outcome["relationDelta"] = 2
            outcome["tradeTrustDelta"] = 1
            if outcome.get("marketPact"):
                outcome["tradeTrustDelta"] += 1
            if site:
                site["status"] = "ceded"
                tribe["scouted_resource_sites"] = [
                    item for item in (tribe.get("scouted_resource_sites", []) or [])
                    if not (isinstance(item, dict) and item.get("id") == site_id)
                ]
            return {"tradeReputation": 1, "renown": 1}
        if response_key == "trade_path":
            outcome["responseLabel"] = "交换通路"
            outcome["relationDelta"] = 1
            outcome["tradeTrustDelta"] = 3
            if outcome.get("marketPact"):
                outcome["relationDelta"] += 1
                outcome["tradeTrustDelta"] += 1
            if site:
                site["contested"] = False
                site["contestResolvedAs"] = "trade_path"
                self._create_trade_route_sites(tribe, outcome, site)
            return {
                "food": max(2, int(base_reward.get("food", 0) or 0) // 2),
                "wood": max(0, int(base_reward.get("wood", 0) or 0) // 2),
                "stone": max(0, int(base_reward.get("stone", 0) or 0) // 2),
                "tradeReputation": 2,
                "renown": 2
            }
        outcome["responseLabel"] = "守住"
        outcome["relationDelta"] = -1 if outcome.get("marketPact") else -2
        outcome["tradeTrustDelta"] = 1 if outcome.get("marketPact") else 0
        if site:
            site["contestResolvedAs"] = "hold"
        base_reward["renown"] = int(base_reward.get("renown", 0) or 0) + 2
        return base_reward

    async def claim_tribe_flag(self, player_id: str, x: float, z: float):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以插下领地旗帜")
            return

        flags = tribe.setdefault("territory_flags", [])
        if len(flags) >= TRIBE_FLAG_MAX:
            await self._send_tribe_error(player_id, f"最多只能保留 {TRIBE_FLAG_MAX} 面领地旗帜")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        if int(storage.get("wood", 0) or 0) < TRIBE_FLAG_WOOD_COST or int(storage.get("stone", 0) or 0) < TRIBE_FLAG_STONE_COST:
            await self._send_tribe_error(player_id, "仓库资源不足，插旗需要木材和石块")
            return

        safe_x = max(-490, min(490, float(x or 0)))
        safe_z = max(-490, min(490, float(z or 0)))
        storage["wood"] = int(storage.get("wood", 0) or 0) - TRIBE_FLAG_WOOD_COST
        storage["stone"] = int(storage.get("stone", 0) or 0) - TRIBE_FLAG_STONE_COST
        flag_id = f"{tribe_id}_flag_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}"
        flag = {
            "id": flag_id,
            "tribeId": tribe_id,
            "type": "tribe_flag",
            "label": f"{tribe.get('name', '部落')}领地旗帜",
            "x": safe_x,
            "z": safe_z,
            "size": 1.0,
            "claimedBy": member.get("name", "成员"),
            "claimedAt": datetime.now().isoformat(),
            "claimNote": "旗帜周围会成为部落公开宣告的资源活动区。"
        }
        flags.append(flag)
        tribe["renown"] = max(0, int(tribe.get("renown", 0) or 0)) + 2
        detail = f"{member.get('name', '成员')} 在 ({round(safe_x)}, {round(safe_z)}) 插下领地旗帜，消耗木材 {TRIBE_FLAG_WOOD_COST}、石块 {TRIBE_FLAG_STONE_COST}。"
        self._add_tribe_history(tribe, "governance", "插下领地旗帜", detail, player_id, {"kind": "territory_flag", **flag})
        await self._publish_world_rumor(
            "territory",
            "领地旗帜",
            f"{tribe.get('name', '部落')} 在新的资源点插下旗帜，公开宣告活动范围。",
            {"tribeId": tribe_id, "flagId": flag_id, "x": safe_x, "z": safe_z}
        )
        relation = self._flag_boundary_relation(tribe_id, flag)
        if relation:
            flag["boundaryRelation"] = relation
            await self._publish_world_rumor(
                "territory",
                relation.get("label", "旗帜边界"),
                f"{tribe.get('name', '部落')} 的新旗帜靠近 {relation.get('otherTribeName', '其他部落')}，形成{relation.get('label', '边界关系')}。",
                {"tribeId": tribe_id, "flagId": flag_id, "relation": relation}
            )
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()


    async def patrol_tribe_flag(self, player_id: str, flag_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        flags = tribe.get("territory_flags", []) or []
        flag = next((item for item in flags if isinstance(item, dict) and item.get("id") == flag_id), None)
        if not flag:
            await self._send_tribe_error(player_id, "这面旗帜不属于你的部落")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(flag.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(flag.get("z", 0) or 0)
        if dx * dx + dz * dz > 9 * 9:
            await self._send_tribe_error(player_id, "靠近领地旗帜后才能巡查")
            return

        last_patrolled = flag.get("lastPatrolledAt")
        if last_patrolled:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_patrolled)).total_seconds()
                if elapsed < TRIBE_FLAG_PATROL_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil((TRIBE_FLAG_PATROL_COOLDOWN_SECONDS - elapsed) / 60))
                    await self._send_tribe_error(player_id, f"这面旗帜刚巡查过，还需约 {remaining} 分钟")
                    return
            except (TypeError, ValueError):
                pass

        nearest_region = min(
            WORLD_REGIONS,
            key=lambda region: (float(flag.get("x", 0) or 0) - region["x"]) ** 2 + (float(flag.get("z", 0) or 0) - region["z"]) ** 2
        )
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        region_type = nearest_region.get("type")
        reward_parts = []
        if region_type == "region_forest":
            storage["wood"] = int(storage.get("wood", 0) or 0) + 5
            reward_parts.append("木材+5")
        elif region_type == "region_mountain":
            storage["stone"] = int(storage.get("stone", 0) or 0) + 5
            reward_parts.append("石块+5")
        elif region_type == "region_coast":
            tribe["food"] = int(tribe.get("food", 0) or 0) + 5
            reward_parts.append("食物+5")
        elif region_type == "region_ruin":
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + 1
            reward_parts.append("发现进度+1")
        else:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 2
            reward_parts.append("声望+2")

        tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
        reward_parts.append("巡查声望+1")
        member = tribe.get("members", {}).get(player_id, {})

        if self._has_tribe_structure_type(tribe, "tribe_road"):
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
            reward_parts.append("道路巡查声望+1")
        chain_regions = list(tribe.get("flag_patrol_chain_regions", []) or [])
        if region_type and region_type not in chain_regions:
            chain_regions.append(region_type)
        tribe["flag_patrol_chain_regions"] = chain_regions[-TRIBE_FLAG_PATROL_CHAIN_TARGET:]
        chain_unlocked = len(set(tribe["flag_patrol_chain_regions"])) >= TRIBE_FLAG_PATROL_CHAIN_TARGET
        tide_hint = None
        if chain_unlocked:
            tribe["flag_patrol_chain_regions"] = []
            env = self._get_current_environment()
            tide_hint = {
                "id": f"flag_tide_{nearest_region['id']}_{int(datetime.now().timestamp())}",
                "regionId": nearest_region["id"],
                "regionType": nearest_region["type"],
                "regionLabel": nearest_region["label"],
                "x": nearest_region["x"],
                "z": nearest_region["z"],
                "radius": nearest_region["radius"],
                "gatherBonus": RESOURCE_TIDE_GATHER_BONUS + 1,
                "seasonBoosted": False,
                "flagPatrolHint": True,
                "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + RESOURCE_TIDE_DURATION_MINUTES * 60).isoformat()
            }
            env["resourceTide"] = tide_hint
            map_data = self.maps.get(self.current_map_name) or {}
            map_data["environment"] = env
            map_data["updated_at"] = datetime.now().isoformat()
            reward_parts.append(f"旗帜连锁：{nearest_region.get('label', '附近区域')}资源潮汐")

        flag["lastPatrolledAt"] = datetime.now().isoformat()
        flag["lastPatrolledBy"] = member.get("name", "成员")
        flag["lastPatrolReward"] = reward_parts
        record = {
            "kind": "territory_flag_patrol",
            "flagId": flag.get("id"),
            "flagLabel": flag.get("label", "领地旗帜"),
            "regionLabel": nearest_region.get("label", "附近区域"),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "chainUnlocked": chain_unlocked,
            "chainTarget": TRIBE_FLAG_PATROL_CHAIN_TARGET,
            "tideHint": tide_hint,
            "createdAt": flag["lastPatrolledAt"]
        }
        detail = f"{record['memberName']} 巡查了{record['flagLabel']}，确认{record['regionLabel']}的活动范围：{'、'.join(reward_parts)}。"
        if chain_unlocked:
            detail += " 连续巡查不同区域的旗帜后，部落标记出新的资源潮汐线索。"
        self._add_tribe_history(tribe, "governance", "巡查领地旗帜", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()


    async def start_tribe_scout(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        food = int(tribe.get("food", 0) or 0)
        if food < TRIBE_SCOUT_FOOD_COST:
            await self._send_tribe_error(player_id, f"侦察需要食物 {TRIBE_SCOUT_FOOD_COST}")
            return

        env = self._get_current_environment()
        tribe["food"] = food - TRIBE_SCOUT_FOOD_COST
        env["resourceTide"] = self._pick_resource_tide(env)
        events = [event for event in (env.get("worldEvents", []) or []) if isinstance(event, dict)]
        for _ in range(TRIBE_SCOUT_EVENT_COUNT):
            events.append(self._pick_world_event(env))
        env["worldEvents"] = events[-4:]
        tide = env["resourceTide"]
        region_type = tide.get("regionType", "region_forest")
        site_reward = TRIBE_SCOUT_SITE_REWARDS.get(region_type, TRIBE_SCOUT_SITE_REWARDS["region_forest"])
        _, region_bonus_label = self._region_building_bonus(tribe, region_type, "secure")
        angle = random.random() * math.pi * 2
        distance = random.randint(10, max(14, int(tide.get("radius", 20) or 20)))
        site_x = max(-490, min(490, float(tide.get("x", 0) or 0) + math.cos(angle) * distance))
        site_z = max(-490, min(490, float(tide.get("z", 0) or 0) + math.sin(angle) * distance))
        site = {
            "id": f"scout_site_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "tribeId": tribe_id,
            "type": "scouted_resource_site",
            "label": site_reward.get("label", "侦察资源点"),
            "regionType": region_type,
            "regionLabel": tide.get("regionLabel", "未知区域"),
            "resourceLabel": site_reward.get("label", "资源点"),
            "x": site_x,
            "z": site_z,
            "size": 1.0,
            "reward": {key: value for key, value in site_reward.items() if key != "label"},
            "regionBonusLabel": region_bonus_label,
            "foundBy": member.get("name", "成员"),
            "status": "active",
            "createdAt": datetime.now().isoformat(),
            "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_SCOUT_SITE_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("scouted_resource_sites", []).append(site)
        tribe["scouted_resource_sites"] = tribe["scouted_resource_sites"][-TRIBE_SCOUT_SITE_LIMIT:]
        contested_tribe_ids = self._mark_scout_site_contests(tribe, site)

        report = {
            "id": f"scout_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "memberName": member.get("name", "成员"),
            "regionLabel": tide.get("regionLabel", "未知区域"),
            "siteId": site["id"],
            "siteLabel": site["label"],
            "eventTitles": [event.get("title", "世界事件") for event in env["worldEvents"][-TRIBE_SCOUT_EVENT_COUNT:]],
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("scout_reports", []).append(report)
        tribe["scout_reports"] = tribe["scout_reports"][-8:]

        map_data = self.maps.get(self.current_map_name) or {}
        map_data["environment"] = env
        map_data["updated_at"] = datetime.now().isoformat()
        contest_text = " 这处资源点靠近其他部落线索，已经形成争夺机会。" if contested_tribe_ids else ""
        detail = f"{report['memberName']} 派出侦察队，标记了{report['regionLabel']}的大地馈赠，发现{site['label']}，并发现 {'、'.join(report['eventTitles'])}。{contest_text}"
        self._add_tribe_history(tribe, "world_event", "派出侦察", detail, player_id, {"kind": "scout", **report})
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "scout",
            "侦察标记",
            f"{tribe.get('name', '部落')} 派出侦察队，远方资源与事件被重新标记。",
            {"tribeId": tribe_id, "reportId": report["id"]}
        )
        await self.broadcast_tribe_state(tribe_id)
        for affected_id in contested_tribe_ids:
            if affected_id != tribe_id:
                await self._notify_tribe(
                    affected_id,
                    f"{tribe.get('name', '其他部落')} 的侦察线索与你们的资源点重叠，部落面板出现了资源点争执。"
                )
                await self.broadcast_tribe_state(affected_id)
        await self._broadcast_current_map()

    def _mark_scout_site_contests(self, tribe: dict, site: dict) -> set:
        affected_tribe_ids = set()
        tribe_id = tribe.get("id")
        if not tribe_id or not site:
            return affected_tribe_ids
        sx = float(site.get("x", 0) or 0)
        sz = float(site.get("z", 0) or 0)
        for other_tribe in self.tribes.values():
            other_id = other_tribe.get("id")
            if not other_id or other_id == tribe_id:
                continue
            for other_site in self._active_scouted_resource_sites(other_tribe):
                dx = sx - float(other_site.get("x", 0) or 0)
                dz = sz - float(other_site.get("z", 0) or 0)
                if dx * dx + dz * dz > TRIBE_SCOUT_SITE_CONTEST_RADIUS * TRIBE_SCOUT_SITE_CONTEST_RADIUS:
                    continue
                self._flag_scout_site_contest(tribe, other_tribe, site, other_site)
                self._flag_scout_site_contest(other_tribe, tribe, other_site, site)
                affected_tribe_ids.update({tribe_id, other_id})
        return affected_tribe_ids

    def _flag_scout_site_contest(self, tribe: dict, other_tribe: dict, site: dict, other_site: dict):
        other_id = other_tribe.get("id")
        if not other_id:
            return
        site["contested"] = True
        site["contestedByTribeId"] = other_id
        site["contestedByTribeName"] = other_tribe.get("name", "其他部落")
        site["contestSiteId"] = other_site.get("id")
        market_pact = self._market_pact_between(tribe, other_id)

        progress = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
        score_loss = max(0, 2 - (TRIBE_MARKET_PACT_CONTEST_RELIEF if market_pact else 0))
        progress["score"] = max(-9, int(progress.get("score", 0) or 0) - score_loss)
        progress["lastAction"] = "resource_site_contest"
        progress["lastActionAt"] = datetime.now().isoformat()

        pending = tribe.setdefault("boundary_outcomes", [])
        duplicate = next((
            item for item in pending
            if item.get("kind") == "resource_site_contest"
            and item.get("siteId") == site.get("id")
            and item.get("otherTribeId") == other_id
            and item.get("status") == "pending"
        ), None)
        if duplicate:
            return
        reward = {"renown": 4}
        site_reward = dict(site.get("reward") or {})
        if int(site_reward.get("wood", 0) or 0):
            reward["wood"] = 4
        if int(site_reward.get("stone", 0) or 0):
            reward["stone"] = 4
        if int(site_reward.get("food", 0) or 0):
            reward["food"] = 4
        if int(site_reward.get("discoveryProgress", 0) or 0):
            reward["discoveryProgress"] = 1
        summary = f"{site.get('label', '侦察资源点')} 与 {other_tribe.get('name', '其他部落')} 的侦察线索重叠，边界关系变得紧张。"
        if market_pact:
            summary += " 互市约定降低了误判，争执更容易转向交换通路。"
        pending.append({
            "id": f"resource_contest_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "kind": "resource_site_contest",
            "state": "hostile",
            "title": "资源点争执",
            "summary": summary,
            "siteId": site.get("id"),
            "siteLabel": site.get("label"),
            "otherSiteId": other_site.get("id"),
            "otherTribeId": other_id,
            "otherTribeName": other_tribe.get("name", "其他部落"),
            "marketPact": bool(market_pact),
            "marketPactTitle": market_pact.get("title") if market_pact else "",
            "reward": reward,
            "responseOptions": [
                {"key": "hold", "label": "守住"},
                {"key": "cede", "label": "让渡"},
                {"key": "trade_path", "label": "交换通路"}
            ],
            "status": "pending",
            "createdAt": datetime.now().isoformat()
        })
        tribe["boundary_outcomes"] = pending[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]

    async def secure_scouted_resource_site(self, player_id: str, site_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        sites = self._active_scouted_resource_sites(tribe)
        site = next((item for item in sites if item.get("id") == site_id), None)
        if not site:
            await self._send_tribe_error(player_id, "这个侦察资源点已经失效")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(site.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(site.get("z", 0) or 0)
        if dx * dx + dz * dz > TRIBE_SCOUT_SITE_INTERACT_DISTANCE * TRIBE_SCOUT_SITE_INTERACT_DISTANCE:
            await self._send_tribe_error(player_id, "靠近侦察资源点后才能确认")
            return

        reward = dict(site.get("reward") or {})
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
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
        discovery = int(reward.get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现进度+{discovery}")
        renown = int(reward.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        if site.get("contested"):
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 2
            reward_parts.append("争夺确认声望+2")
        shared_with_id = site.get("sharedWithTribeId")
        if site.get("jointWatchId") and shared_with_id:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + 1
            relation_progress = tribe.setdefault("boundary_relations", {}).setdefault(shared_with_id, {})
            relation_progress["tradeTrust"] = min(9, int(relation_progress.get("tradeTrust", 0) or 0) + 1)
            relation_progress["score"] = min(9, int(relation_progress.get("score", 0) or 0) + 1)
            relation_progress["lastAction"] = "joint_watch_confirmed"
            relation_progress["lastActionAt"] = datetime.now().isoformat()
            other_tribe = self.tribes.get(shared_with_id)
            if other_tribe:
                other_progress = other_tribe.setdefault("boundary_relations", {}).setdefault(tribe_id, {})
                other_progress["tradeTrust"] = min(9, int(other_progress.get("tradeTrust", 0) or 0) + 1)
                other_progress["score"] = min(9, int(other_progress.get("score", 0) or 0) + 1)
                other_progress["lastAction"] = "joint_watch_confirmed"
                other_progress["lastActionAt"] = relation_progress["lastActionAt"]
            reward_parts.append("联合守望信誉+1")

        linked_flag = next((
            flag for flag in (tribe.get("territory_flags", []) or [])
            if isinstance(flag, dict)
            and (float(flag.get("x", 0) or 0) - float(site.get("x", 0) or 0)) ** 2
            + (float(flag.get("z", 0) or 0) - float(site.get("z", 0) or 0)) ** 2
            <= TRIBE_SCOUT_SITE_FLAG_RADIUS * TRIBE_SCOUT_SITE_FLAG_RADIUS
        ), None)
        if linked_flag:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 2
            reward_parts.append("旗帜控制声望+2")
            linked_flag["linkedResourceSiteId"] = site.get("id")
            linked_flag["linkedResourceSiteLabel"] = site.get("label")
        if self._has_tribe_structure_type(tribe, "tribe_road"):
            storage["wood"] = int(storage.get("wood", 0) or 0) + 2
            storage["stone"] = int(storage.get("stone", 0) or 0) + 2
            reward_parts.append("道路驮运木材+2/石块+2")
        region_bonus, region_bonus_label = self._region_building_bonus(tribe, site.get("regionType"), "secure")
        self._apply_region_bonus_rewards(tribe, region_bonus, region_bonus_label, reward_parts)

        member = tribe.get("members", {}).get(player_id, {})
        site["status"] = "secured"
        site["securedAt"] = datetime.now().isoformat()
        site["securedBy"] = player_id
        controlled_site = {
            **site,
            "id": f"controlled_{site.get('id')}",
            "type": "controlled_resource_site",
            "status": "controlled",
            "level": 1,
            "yieldCount": 0,
            "patrolCount": 0,
            "relayCount": 0,
            "roadLinked": self._has_tribe_structure_type(tribe, "tribe_road"),
            "regionBonusLabel": region_bonus_label,
            "securedByName": member.get("name", "成员"),
            "controlledAt": site["securedAt"],
            "lastYieldAt": None,
            "lastPatrolledAt": None,
            "lastRelayedAt": None,
            "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_CONTROLLED_SITE_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("controlled_resource_sites", []).append(controlled_site)
        tribe["controlled_resource_sites"] = tribe["controlled_resource_sites"][-TRIBE_CONTROLLED_SITE_LIMIT:]
        tribe["scouted_resource_sites"] = [
            item for item in (tribe.get("scouted_resource_sites", []) or [])
            if not (isinstance(item, dict) and item.get("id") == site_id)
        ]

        record = {
            "kind": "scouted_resource_site",
            "siteId": site.get("id"),
            "siteLabel": site.get("label", "侦察资源点"),
            "regionLabel": site.get("regionLabel", "附近区域"),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "linkedFlagId": linked_flag.get("id") if linked_flag else None,
            "contested": bool(site.get("contested")),
            "contestedByTribeName": site.get("contestedByTribeName"),
            "createdAt": site["securedAt"]
        }
        detail = f"{record['memberName']} 确认了{record['siteLabel']}，带回{'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "world_event", "确认侦察资源点", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "territory",
            "资源点确认",
            f"{tribe.get('name', '部落')} 确认了{site.get('label', '侦察资源点')}，探索线索转化为领地收益。",
            {"tribeId": tribe_id, "siteId": site_id, "linkedFlagId": record["linkedFlagId"]}
        )
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def collect_controlled_resource_site(self, player_id: str, site_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        sites = self._active_controlled_resource_sites(tribe)
        site = next((item for item in sites if item.get("id") == site_id), None)
        if not site:
            await self._send_tribe_error(player_id, "这个控制资源点已经消散")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(site.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(site.get("z", 0) or 0)
        if dx * dx + dz * dz > TRIBE_SCOUT_SITE_INTERACT_DISTANCE * TRIBE_SCOUT_SITE_INTERACT_DISTANCE:
            await self._send_tribe_error(player_id, "靠近控制资源点后才能收取")
            return

        last_yield_at = site.get("lastYieldAt")
        if last_yield_at:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_yield_at)).total_seconds()
                if elapsed < TRIBE_CONTROLLED_SITE_YIELD_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil((TRIBE_CONTROLLED_SITE_YIELD_COOLDOWN_SECONDS - elapsed) / 60))
                    await self._send_tribe_error(player_id, f"这处资源点刚收取过，还需约 {remaining} 分钟")
                    return
            except (TypeError, ValueError):
                pass

        source_reward = dict(site.get("reward") or {})
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        site_level = max(1, int(site.get("level", 1) or 1))
        base_yield = 3 + site_level
        if int(source_reward.get("wood", 0) or 0):
            amount = base_yield
            storage["wood"] = int(storage.get("wood", 0) or 0) + amount
            reward_parts.append(f"木材+{amount}")
        if int(source_reward.get("stone", 0) or 0):
            amount = base_yield
            storage["stone"] = int(storage.get("stone", 0) or 0) + amount
            reward_parts.append(f"石块+{amount}")
        if int(source_reward.get("food", 0) or 0):
            amount = base_yield
            tribe["food"] = int(tribe.get("food", 0) or 0) + amount
            reward_parts.append(f"食物+{amount}")
        if int(source_reward.get("discoveryProgress", 0) or 0):
            progress_amount = 1 + (1 if site_level >= 3 else 0)
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + progress_amount
            reward_parts.append(f"发现进度+{progress_amount}")

        if site.get("linkedFlagId"):
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
            reward_parts.append("旗帜控制声望+1")
        if self._has_tribe_structure_type(tribe, "tribe_road"):
            road_bonus = 1 + (1 if site_level >= 2 else 0)
            storage["wood"] = int(storage.get("wood", 0) or 0) + road_bonus
            storage["stone"] = int(storage.get("stone", 0) or 0) + road_bonus
            reward_parts.append(f"道路运输木材+{road_bonus}/石块+{road_bonus}")
        region_bonus, region_bonus_label = self._region_building_bonus(tribe, site.get("regionType"), "yield")
        self._apply_region_bonus_rewards(tribe, region_bonus, region_bonus_label, reward_parts)
        if region_bonus_label:
            site["regionBonusLabel"] = region_bonus_label

        if not reward_parts:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
            reward_parts.append("声望+1")

        site["lastYieldAt"] = datetime.now().isoformat()
        site["yieldCount"] = int(site.get("yieldCount", 0) or 0) + 1
        upgraded = False
        if site_level < TRIBE_CONTROLLED_SITE_MAX_LEVEL and site["yieldCount"] >= TRIBE_CONTROLLED_SITE_UPGRADE_COLLECTS:
            site["level"] = site_level + 1
            site["yieldCount"] = 0
            extend_from = datetime.now().timestamp()
            try:
                extend_from = max(extend_from, datetime.fromisoformat(site.get("activeUntil")).timestamp())
            except (TypeError, ValueError):
                pass
            site["activeUntil"] = datetime.fromtimestamp(
                extend_from + TRIBE_CONTROLLED_SITE_UPGRADE_EXTEND_MINUTES * 60
            ).isoformat()
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 2
            reward_parts.append(f"控制点升级Lv.{site['level']}")
            reward_parts.append("声望+2")
            upgraded = True
        member = tribe.get("members", {}).get(player_id, {})
        record = {
            "kind": "controlled_resource_site",
            "siteId": site.get("id"),
            "siteLabel": site.get("label", "控制资源点"),
            "siteLevel": site.get("level", 1),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "upgraded": upgraded,
            "createdAt": site["lastYieldAt"]
        }
        detail = f"{record['memberName']} 收取了{record['siteLabel']}的控制收益：{'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "world_event", "收取控制资源点", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def collect_trade_route_site(self, player_id: str, site_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        sites = self._active_trade_route_sites(tribe)
        site = next((item for item in sites if item.get("id") == site_id), None)
        if not site:
            await self._send_tribe_error(player_id, "这条交换通路已经消散")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(site.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(site.get("z", 0) or 0)
        if dx * dx + dz * dz > TRIBE_SCOUT_SITE_INTERACT_DISTANCE * TRIBE_SCOUT_SITE_INTERACT_DISTANCE:
            await self._send_tribe_error(player_id, "靠近交换通路贸易点后才能收取")
            return

        last_collected_at = site.get("lastCollectedAt")
        if last_collected_at:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_collected_at)).total_seconds()
                if elapsed < TRIBE_TRADE_ROUTE_SITE_COLLECT_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil((TRIBE_TRADE_ROUTE_SITE_COLLECT_COOLDOWN_SECONDS - elapsed) / 60))
                    await self._send_tribe_error(player_id, f"这条交换通路刚整理过，还需约 {remaining} 分钟")
                    return
            except (TypeError, ValueError):
                pass

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward = dict(site.get("reward") or {})
        reward_parts = []
        if int(reward.get("wood", 0) or 0):
            storage["wood"] = int(storage.get("wood", 0) or 0) + 2
            reward_parts.append("木材+2")
        if int(reward.get("stone", 0) or 0):
            storage["stone"] = int(storage.get("stone", 0) or 0) + 2
            reward_parts.append("石块+2")
        if int(reward.get("food", 0) or 0):
            tribe["food"] = int(tribe.get("food", 0) or 0) + 2
            reward_parts.append("食物+2")
        if int(reward.get("discoveryProgress", 0) or 0):
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + 1
            reward_parts.append("发现+1")
        self._apply_trade_route_market_reward(tribe, site, reward_parts)

        tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + 1
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
        reward_parts.extend(["贸易信誉+1", "声望+1"])
        partner_id = site.get("partnerTribeId")
        if partner_id:
            progress = tribe.setdefault("boundary_relations", {}).setdefault(partner_id, {})
            progress["tradeTrust"] = max(0, min(9, int(progress.get("tradeTrust", 0) or 0) + 1))
            progress["score"] = min(9, int(progress.get("score", 0) or 0) + 1)
            progress["lastAction"] = "trade_route_collect"
            progress["lastActionAt"] = datetime.now().isoformat()

        site["lastCollectedAt"] = datetime.now().isoformat()
        site["collectCount"] = int(site.get("collectCount", 0) or 0) + 1
        market_started = False
        market_target = int(site.get("marketCollectTarget", TRIBE_TRADE_ROUTE_MARKET_COLLECTS) or TRIBE_TRADE_ROUTE_MARKET_COLLECTS)
        if not self._trade_route_market_active(site) and site["collectCount"] >= market_target:
            activated_tribes = self._activate_trade_route_market(site, datetime.now())
            market_started = bool(activated_tribes)
            if market_started:
                reward_parts.append(f"边市开启{TRIBE_TRADE_ROUTE_MARKET_MINUTES}分钟")
        member = tribe.get("members", {}).get(player_id, {})
        site["lastCollectedBy"] = member.get("name", "成员")
        record = {
            "kind": "trade_route_site",
            "siteId": site.get("id"),
            "siteLabel": site.get("label", "交换通路贸易点"),
            "partnerTribeName": site.get("partnerTribeName", "邻近部落"),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "marketStarted": market_started,
            "marketRewardLabel": site.get("marketRewardLabel"),
            "createdAt": site["lastCollectedAt"]
        }
        detail = f"{record['memberName']} 整理了与 {record['partnerTribeName']} 的交换通路：{'、'.join(reward_parts)}。"
        if market_started:
            detail += " 两边的交换通路升成短时边市，并留下了可处理的边市议价。"
        self._add_tribe_history(tribe, "trade", "收取交换通路", detail, player_id, record)
        if market_started:
            await self._publish_world_rumor(
                "trade",
                "边市开张",
                f"{tribe.get('name', '部落')} 与 {site.get('partnerTribeName', '邻近部落')} 的交换通路升成短时边市。",
                {"tribeId": tribe_id, "siteId": site_id, "sharedRouteId": site.get("sharedRouteId")}
            )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        if market_started:
            partner_id = site.get("partnerTribeId")
            if partner_id and partner_id in self.tribes:
                await self.broadcast_tribe_state(partner_id)
        await self._broadcast_current_map()

    async def patrol_controlled_resource_site(self, player_id: str, site_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        sites = self._active_controlled_resource_sites(tribe)
        site = next((item for item in sites if item.get("id") == site_id), None)
        if not site:
            await self._send_tribe_error(player_id, "这个控制资源点已经消散")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(site.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(site.get("z", 0) or 0)
        if dx * dx + dz * dz > TRIBE_SCOUT_SITE_INTERACT_DISTANCE * TRIBE_SCOUT_SITE_INTERACT_DISTANCE:
            await self._send_tribe_error(player_id, "靠近控制资源点后才能巡守")
            return

        last_patrolled_at = site.get("lastPatrolledAt")
        if last_patrolled_at:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_patrolled_at)).total_seconds()
                if elapsed < TRIBE_CONTROLLED_SITE_PATROL_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil((TRIBE_CONTROLLED_SITE_PATROL_COOLDOWN_SECONDS - elapsed) / 60))
                    await self._send_tribe_error(player_id, f"这处资源点刚巡守过，还需约 {remaining} 分钟")
                    return
            except (TypeError, ValueError):
                pass

        site_level = max(1, int(site.get("level", 1) or 1))
        extend_minutes = TRIBE_CONTROLLED_SITE_PATROL_EXTEND_MINUTES + max(0, site_level - 1)
        extend_from = datetime.now().timestamp()
        try:
            extend_from = max(extend_from, datetime.fromisoformat(site.get("activeUntil")).timestamp())
        except (TypeError, ValueError):
            pass
        site["activeUntil"] = datetime.fromtimestamp(extend_from + extend_minutes * 60).isoformat()
        site["lastPatrolledAt"] = datetime.now().isoformat()
        site["patrolCount"] = int(site.get("patrolCount", 0) or 0) + 1

        reward_parts = [f"控制时间+{extend_minutes}分钟"]
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
        reward_parts.append("声望+1")
        if self._has_tribe_structure_type(tribe, "tribe_fence"):
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
            reward_parts.append("围栏巡守声望+1")
        if site.get("contestResolvedAs") == "trade_path":
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + 1
            reward_parts.append("通路信誉+1")
            other_id = site.get("contestedByTribeId")
            if other_id:
                progress = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
                progress["tradeTrust"] = max(0, min(9, int(progress.get("tradeTrust", 0) or 0) + 1))
                progress["lastAction"] = "controlled_site_patrol"
                progress["lastActionAt"] = site["lastPatrolledAt"]

        member = tribe.get("members", {}).get(player_id, {})
        site["lastPatrolledBy"] = member.get("name", "成员")
        record = {
            "kind": "controlled_resource_site_patrol",
            "siteId": site.get("id"),
            "siteLabel": site.get("label", "控制资源点"),
            "siteLevel": site.get("level", 1),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "createdAt": site["lastPatrolledAt"]
        }
        detail = f"{record['memberName']} 巡守了{record['siteLabel']}：{'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "governance", "巡守控制资源点", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()


    async def relay_controlled_resource_site(self, player_id: str, site_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not self._has_tribe_structure_type(tribe, "tribe_road"):
            await self._send_tribe_error(player_id, "需要先建造营地道路才能组织运输")
            return

        sites = self._active_controlled_resource_sites(tribe)
        site = next((item for item in sites if item.get("id") == site_id), None)
        if not site:
            await self._send_tribe_error(player_id, "这个控制资源点已经消散")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(site.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(site.get("z", 0) or 0)
        if dx * dx + dz * dz > TRIBE_SCOUT_SITE_INTERACT_DISTANCE * TRIBE_SCOUT_SITE_INTERACT_DISTANCE:
            await self._send_tribe_error(player_id, "靠近控制资源点后才能组织运输")
            return

        last_relayed_at = site.get("lastRelayedAt")
        if last_relayed_at:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_relayed_at)).total_seconds()
                if elapsed < TRIBE_CONTROLLED_SITE_RELAY_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil((TRIBE_CONTROLLED_SITE_RELAY_COOLDOWN_SECONDS - elapsed) / 60))
                    await self._send_tribe_error(player_id, f"这条运输路线刚整理过，还需约 {remaining} 分钟")
                    return
            except (TypeError, ValueError):
                pass

        source_reward = dict(site.get("reward") or {})
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        site_level = max(1, int(site.get("level", 1) or 1))
        relay_amount = 2 + site_level
        if int(source_reward.get("wood", 0) or 0):
            storage["wood"] = int(storage.get("wood", 0) or 0) + relay_amount
            reward_parts.append(f"木材+{relay_amount}")
        if int(source_reward.get("stone", 0) or 0):
            storage["stone"] = int(storage.get("stone", 0) or 0) + relay_amount
            reward_parts.append(f"石块+{relay_amount}")
        if int(source_reward.get("food", 0) or 0):
            tribe["food"] = int(tribe.get("food", 0) or 0) + relay_amount
            reward_parts.append(f"食物+{relay_amount}")
        if int(source_reward.get("discoveryProgress", 0) or 0):
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + 1
            reward_parts.append("发现进度+1")

        storage["wood"] = int(storage.get("wood", 0) or 0) + 1
        storage["stone"] = int(storage.get("stone", 0) or 0) + 1
        reward_parts.append("路线维护木材+1/石块+1")

        if site.get("contestResolvedAs") == "trade_path":
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + 1
            reward_parts.append("贸易信誉+1")

        extend_minutes = TRIBE_CONTROLLED_SITE_RELAY_EXTEND_MINUTES + max(0, site_level - 1)
        extend_from = datetime.now().timestamp()
        try:
            extend_from = max(extend_from, datetime.fromisoformat(site.get("activeUntil")).timestamp())
        except (TypeError, ValueError):
            pass
        site["activeUntil"] = datetime.fromtimestamp(extend_from + extend_minutes * 60).isoformat()
        site["lastRelayedAt"] = datetime.now().isoformat()
        site["relayCount"] = int(site.get("relayCount", 0) or 0) + 1
        site["roadLinked"] = True
        reward_parts.append(f"控制时间+{extend_minutes}分钟")

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        site["lastRelayedBy"] = member_name
        record = {
            "kind": "controlled_resource_site_relay",
            "siteId": site.get("id"),
            "siteLabel": site.get("label", "控制资源点"),
            "siteLevel": site.get("level", 1),
            "memberName": member_name,
            "rewardParts": reward_parts,
            "createdAt": site["lastRelayedAt"]
        }
        detail = f"{member_name} 组织了{record['siteLabel']}的道路运输：{'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "world_event", "控制点道路运输", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def compose_oral_epic(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以整理部落史诗")
            return

        chain = tribe.get("oral_chain")
        if isinstance(chain, dict) and len(chain.get("lines", []) or []) >= TRIBE_ORAL_CHAIN_LINE_TARGET:
            await self.complete_oral_chain(player_id)
            return

        history = [item for item in (tribe.get("history", []) or []) if isinstance(item, dict)]
        if len(history) < TRIBE_ORAL_EPIC_MIN_HISTORY:
            await self._send_tribe_error(player_id, f"至少需要 {TRIBE_ORAL_EPIC_MIN_HISTORY} 条部落日志才能整理史诗")
            return

        source_titles = [item.get("title", "部落记忆") for item in history[-5:]][-3:]
        epic = {
            "id": f"epic_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "title": f"{tribe.get('name', '部落')}口述史",
            "summary": f"长老把{'、'.join(source_titles)}编成夜火旁的故事。",
            "composedBy": member.get("name", "管理者"),
            "renownBonus": TRIBE_ORAL_EPIC_RENOWN_BONUS,
            "sourceTitles": source_titles,
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("oral_epics", []).append(epic)
        tribe["oral_epics"] = tribe["oral_epics"][-8:]
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + TRIBE_ORAL_EPIC_RENOWN_BONUS
        camp_center = (tribe.get("camp") or {}).get("center") or {}
        self._record_map_memory(
            tribe,
            "oral_epic",
            "口述史火痕",
            f"《{epic['title']}》把近期部落历史编成故事，营火旁留下可被重读的记忆。",
            float(camp_center.get("x", 0) or 0),
            float(camp_center.get("z", 0) or 0),
            epic["id"],
            member.get("name", "管理者")
        )
        detail = f"{epic['composedBy']} 整理了《{epic['title']}》：{epic['summary']} 声望 +{TRIBE_ORAL_EPIC_RENOWN_BONUS}。"
        self._add_tribe_history(tribe, "ritual", "整理部落史诗", detail, player_id, {"kind": "oral_epic", **epic})
        await self._publish_world_rumor(
            "epic",
            "口述史诗",
            f"{tribe.get('name', '部落')} 的故事被传唱：{epic['summary']}",
            {"tribeId": tribe_id, "epicId": epic["id"], "renownBonus": TRIBE_ORAL_EPIC_RENOWN_BONUS}
        )
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()


    async def choose_tribe_oath(self, player_id: str, oath_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以选择部落誓约")
            return
        if tribe.get("oath"):
            await self._send_tribe_error(player_id, "部落誓约已经确定")
            return
        oath = TRIBE_OATHS.get(oath_key)
        if not oath:
            await self._send_tribe_error(player_id, "未知部落誓约")
            return

        record = {
            "kind": "tribe_oath",
            "key": oath_key,
            "label": oath.get("label", "部落誓约"),
            "summary": oath.get("summary", ""),
            "chosenBy": member.get("name", "管理者"),
            "renownBonus": TRIBE_OATH_RENOWN_BONUS,
            "createdAt": datetime.now().isoformat()
        }
        tribe["oath"] = record
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + TRIBE_OATH_RENOWN_BONUS
        detail = f"{record['chosenBy']} 为部落立下{record['label']}：{record['summary']} 声望 +{TRIBE_OATH_RENOWN_BONUS}。"
        self._add_tribe_history(tribe, "governance", "立下部落誓约", detail, player_id, record)
        await self._publish_world_rumor(
            "oath",
            "部落誓约",
            f"{tribe.get('name', '部落')} 立下{record['label']}，此后的行动会围绕这条长期方向展开。",
            {"tribeId": tribe_id, "oathKey": oath_key, "renownBonus": TRIBE_OATH_RENOWN_BONUS}
        )
        await self.broadcast_tribe_state(tribe_id)

    def _dynamic_oath_task_plan(self, tribe: dict, oath_key: str) -> dict:
        env = self._get_current_environment()
        resource_tide = env.get("resourceTide") if isinstance(env.get("resourceTide"), dict) else None
        world_events = [item for item in (env.get("worldEvents", []) or []) if isinstance(item, dict)]
        season_objective = env.get("seasonObjective") if isinstance(env.get("seasonObjective"), dict) else None
        trade_requests = self._active_trade_requests_for_tribe(tribe.get("id"))
        boundary_outcomes = [item for item in (tribe.get("boundary_outcomes", []) or []) if isinstance(item, dict) and item.get("status") == "pending"]
        boundary_relations = dict(tribe.get("boundary_relations", {}) or {})

        variant_key = None
        if oath_key == "hearth":
            if int(tribe.get("food", 0) or 0) < 18:
                variant_key = "food_pressure"
            elif resource_tide:
                variant_key = "tide_harvest"
            else:
                variant_key = "camp_stock"
        elif oath_key == "trail":
            if season_objective:
                variant_key = "season_objective"
            elif world_events:
                variant_key = "world_event"
            else:
                variant_key = "cave_route"
        elif oath_key == "trade":
            if trade_requests:
                variant_key = "open_trade"
            elif boundary_outcomes or any(int((item or {}).get("tradeTrust", 0) or 0) >= 3 for item in boundary_relations.values()):
                variant_key = "border_trade"
            else:
                variant_key = "gift_pack"
        elif oath_key == "beast":
            if int(tribe.get("tamed_beasts", 0) or 0) <= 0:
                variant_key = "tame_young"
            elif any(int((item or {}).get("score", 0) or 0) <= -2 for item in boundary_relations.values()):
                variant_key = "border_guard"
            else:
                variant_key = "beast_haul" if resource_tide else "border_guard"

        variant_pool = TRIBE_OATH_TASK_VARIANTS.get(oath_key, [])
        variant = next((item for item in variant_pool if item.get("key") == variant_key), None)
        if variant:
            return dict(variant)
        return dict(TRIBE_OATH_TASK_REWARDS.get(oath_key, {}))

    def _current_oath_task(self, tribe: dict) -> Optional[dict]:
        oath = self._tribe_oath(tribe)
        if not oath:
            return None
        oath_key = oath.get("key")
        plan = self._dynamic_oath_task_plan(tribe, oath_key)
        if not plan:
            return None
        task_day = datetime.now().strftime("%Y-%m-%d")
        task_id = f"{task_day}:{oath_key}"
        completed = task_id in set(tribe.get("completed_oath_tasks", []) or [])
        return {
            "id": task_id,
            "oathKey": oath_key,
            "oathLabel": oath.get("label", "部落誓约"),
            "title": plan.get("title", "誓约任务"),
            "summary": plan.get("summary", ""),
            "sourceLabel": plan.get("sourceLabel", ""),
            "variantKey": plan.get("key", oath_key),
            "reward": dict(plan),
            "completed": completed,
            "streak": dict(tribe.get("oath_task_streak", {})),
            "streakTarget": TRIBE_OATH_TASK_STREAK_TARGET
        }

    def _update_oath_task_streak(self, tribe: dict, oath_key: str) -> tuple:
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        streak = tribe.get("oath_task_streak") if isinstance(tribe.get("oath_task_streak"), dict) else {}
        last_date_text = streak.get("lastDate")
        last_oath = streak.get("oathKey")
        count = 1
        if last_oath == oath_key and last_date_text == yesterday.isoformat():
            count = int(streak.get("count", 0) or 0) + 1
        tribe["oath_task_streak"] = {
            "oathKey": oath_key,
            "count": count,
            "lastDate": today.isoformat(),
            "target": TRIBE_OATH_TASK_STREAK_TARGET
        }
        return count, count >= TRIBE_OATH_TASK_STREAK_TARGET

    def _create_joint_watch_scout_sites(self, tribe: dict, other_tribe: dict, flag: dict, relation: dict, member_name: str) -> list:
        other_flag = next((
            item for item in (other_tribe.get("territory_flags", []) or [])
            if isinstance(item, dict) and item.get("id") == relation.get("otherFlagId")
        ), None)
        if not other_flag:
            return []

        own_x = float(flag.get("x", 0) or 0)
        own_z = float(flag.get("z", 0) or 0)
        other_x = float(other_flag.get("x", 0) or 0)
        other_z = float(other_flag.get("z", 0) or 0)
        mid_x = (own_x + other_x) / 2
        mid_z = (own_z + other_z) / 2
        nearest_region = min(
            WORLD_REGIONS,
            key=lambda region: (mid_x - region["x"]) ** 2 + (mid_z - region["z"]) ** 2
        )
        region_type = nearest_region.get("type", "region_forest")
        site_reward = TRIBE_SCOUT_SITE_REWARDS.get(region_type, TRIBE_SCOUT_SITE_REWARDS["region_forest"])
        angle = random.random() * math.pi * 2
        distance = random.randint(5, max(8, min(18, int(nearest_region.get("radius", 18) or 18))))
        site_x = max(-490, min(490, mid_x + math.cos(angle) * distance))
        site_z = max(-490, min(490, mid_z + math.sin(angle) * distance))
        now_text = datetime.now().isoformat()
        active_until = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_SCOUT_SITE_ACTIVE_MINUTES * 60).isoformat()
        shared_id = f"joint_watch_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}"
        shared_label = f"联合守望线索：{site_reward.get('label', '资源点')}"
        created_sites = []
        for target_tribe, partner_tribe in ((tribe, other_tribe), (other_tribe, tribe)):
            target_id = target_tribe.get("id")
            if not target_id:
                continue
            _, region_bonus_label = self._region_building_bonus(target_tribe, region_type, "secure")
            site = {
                "id": f"{shared_id}_{target_id}",
                "tribeId": target_id,
                "type": "scouted_resource_site",
                "label": shared_label,
                "regionType": region_type,
                "regionLabel": nearest_region.get("label", "边界地带"),
                "resourceLabel": site_reward.get("label", "资源点"),
                "x": site_x,
                "z": site_z,
                "size": 1.05,
                "reward": {key: value for key, value in site_reward.items() if key != "label"},
                "regionBonusLabel": region_bonus_label,
                "foundBy": member_name,
                "status": "active",
                "sharedByTribeId": tribe.get("id"),
                "sharedWithTribeId": partner_tribe.get("id"),
                "sharedWithTribeName": partner_tribe.get("name", "其他部落"),
                "jointWatchId": shared_id,
                "createdAt": now_text,
                "activeUntil": active_until
            }
            target_tribe.setdefault("scouted_resource_sites", []).append(site)
            target_tribe["scouted_resource_sites"] = target_tribe["scouted_resource_sites"][-TRIBE_SCOUT_SITE_LIMIT:]
            created_sites.append(site)
        return created_sites

    async def complete_oath_task(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = self._current_oath_task(tribe)
        if not task:
            await self._send_tribe_error(player_id, "部落还没有立下誓约")
            return
        if task.get("completed"):
            await self._send_tribe_error(player_id, "今天的誓约任务已经完成")
            return

        reward = dict(task.get("reward") or {})
        if task.get("oathKey") == "beast" and int(tribe.get("tamed_beasts", 0) or 0) <= 0 and int(reward.get("tamedBeasts", 0) or 0) <= 0:
            await self._send_tribe_error(player_id, "兽伴誓约任务需要先驯养幼兽")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
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
        progress = int(reward.get("discoveryProgress", 0) or 0)
        if progress:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + progress
            reward_parts.append(f"发现进度+{progress}")
        trade_rep = int(reward.get("tradeReputation", 0) or 0)
        if trade_rep:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_rep
            reward_parts.append(f"贸易信誉+{trade_rep}")
        beast_exp = int(reward.get("beastExperience", 0) or 0)
        if beast_exp:
            tribe["beast_experience"] = int(tribe.get("beast_experience", 0) or 0) + beast_exp
            reward_parts.append(f"幼兽熟练度+{beast_exp}")

        tamed_beasts = int(reward.get("tamedBeasts", 0) or 0)
        if tamed_beasts:
            tribe["tamed_beasts"] = int(tribe.get("tamed_beasts", 0) or 0) + tamed_beasts
            reward_parts.append(f"驯养幼兽+{tamed_beasts}")
        streak_count, streak_unlocked = self._update_oath_task_streak(tribe, task.get("oathKey"))
        if streak_unlocked:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 8
            tribe["oath_task_streak"]["count"] = 0
            tribe["celebration_buff"] = {
                "type": "oath_streak",
                "title": "誓约连胜余韵",
                "gatherBonus": 1 if task.get("oathKey") == "hearth" else 0,
                "discoveryBonus": 1 if task.get("oathKey") == "trail" else 0,
                "tradeRenownBonus": 1 if task.get("oathKey") == "trade" else 0,
                "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + 8 * 60).isoformat()
            }
            if task.get("oathKey") == "beast":
                tribe["food"] = int(tribe.get("food", 0) or 0) + 8
                reward_parts.append("兽伴连胜食物+8")
            reward_parts.append("誓约连胜声望+8")

        completed = list(tribe.get("completed_oath_tasks", []) or [])
        completed.append(task["id"])
        tribe["completed_oath_tasks"] = completed[-14:]
        member = tribe.get("members", {}).get(player_id, {})
        record = {
            "kind": "oath_task",
            "taskId": task["id"],
            "oathKey": task.get("oathKey"),
            "oathLabel": task.get("oathLabel"),
            "title": task.get("title"),
            "summary": task.get("summary"),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "streakCount": streak_count,
            "streakUnlocked": streak_unlocked,
            "streakTarget": TRIBE_OATH_TASK_STREAK_TARGET,
            "createdAt": datetime.now().isoformat()
        }
        detail = f"{record['memberName']} 完成誓约任务「{record['title']}」：{record['summary']} {'、'.join(reward_parts)}。"
        if streak_unlocked:
            detail += " 连续践行誓约后，营地出现了短暂的庆祝余韵。"
        self._add_tribe_history(tribe, "governance", "完成誓约任务", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "oath",
            "誓约任务",
            f"{tribe.get('name', '部落')} 完成了{record['oathLabel']}的轻量目标：{record['title']}。",
            {"tribeId": tribe_id, "taskId": task["id"], "oathKey": task.get("oathKey")}
        )
        await self.broadcast_tribe_state(tribe_id)

    async def resolve_boundary_action(self, player_id: str, flag_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_BOUNDARY_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知边界行动")
            return
        flags = tribe.get("territory_flags", []) or []
        flag = next((item for item in flags if isinstance(item, dict) and item.get("id") == flag_id), None)
        if not flag:
            await self._send_tribe_error(player_id, "只能在本部落旗帜处理边界")
            return
        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(flag.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(flag.get("z", 0) or 0)
        if dx * dx + dz * dz > 10 * 10:
            await self._send_tribe_error(player_id, "靠近边界旗帜后才能行动")
            return
        relation = self._flag_boundary_relation(tribe_id, flag)
        if not relation:
            await self._send_tribe_error(player_id, "这面旗帜附近还没有形成边界关系")
            return
        other_tribe_id = relation.get("otherTribeId")
        allowed_states = action.get("allowedStates")
        if allowed_states and relation.get("state") not in allowed_states:
            await self._send_tribe_error(player_id, f"{action.get('label', '边界行动')}只能在紧张或敌意边界使用")
            return
        if action.get("pressure"):
            active_truce = next((
                item for item in self._active_boundary_truces(tribe)
                if isinstance(item, dict) and item.get("otherTribeId") == other_tribe_id
            ), None)
            if active_truce:
                await self._send_tribe_error(player_id, "停争保护仍在，暂时不能继续施压")
                return
        cooldowns = flag.setdefault("boundaryActionCooldowns", {})
        cooldown_key = f"{action_key}:{relation.get('otherTribeId')}"
        last_action_at = cooldowns.get(cooldown_key)
        if last_action_at:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_action_at)).total_seconds()
                if elapsed < TRIBE_BOUNDARY_ACTION_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil((TRIBE_BOUNDARY_ACTION_COOLDOWN_SECONDS - elapsed) / 60))
                    await self._send_tribe_error(player_id, f"这条边界刚处理过，还需约 {remaining} 分钟")
                    return
            except (TypeError, ValueError):
                pass

        food_cost = int(action.get("foodCost", 0) or 0)
        if action.get("pressure") and relation.get("state") == "hostile":
            food_cost += TRIBE_BOUNDARY_HOSTILE_FOOD_COST
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"{action.get('label')}需要食物 {food_cost}")
            return
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost

        reward_parts = []
        renown = int(action.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        trade_rep = int(action.get("tradeReputation", 0) or 0)
        if trade_rep:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_rep
            reward_parts.append(f"贸易信誉+{trade_rep}")
        if food_cost:
            reward_parts.append(f"食物-{food_cost}")
        law_event_key = f"boundary_{action_key}"
        law_bonus_parts = self.apply_tribe_law_event_bonus(tribe, law_event_key, action.get("label", "边界行动"))
        if law_bonus_parts:
            reward_parts.extend(law_bonus_parts)
        law_violation_parts = self.apply_tribe_law_violation(tribe, player_id, law_event_key, action.get("label", "边界行动"))
        if law_violation_parts:
            reward_parts.extend(law_violation_parts)

        boundary_progress = {}
        affected_tribe_ids = set()
        other_tribe = None
        pressure_chain_count = 0
        if action.get("clearIncomingPressure"):
            before_count = len(tribe.get("boundary_pressures", []) or [])
            tribe["boundary_pressures"] = [
                item for item in (tribe.get("boundary_pressures", []) or [])
                if not (
                    isinstance(item, dict)
                    and item.get("otherTribeId") == other_tribe_id
                    and item.get("state") == "pressured"
                )
            ]
            cleared_count = before_count - len(tribe.get("boundary_pressures", []) or [])
            if cleared_count:
                reward_parts.append("解除边界压力")
                if self._has_tribe_structure_type(tribe, "tribe_fence"):
                    tribe["renown"] = int(tribe.get("renown", 0) or 0) + 2
                    reward_parts.append("围栏守边声望+2")
        if action.get("clearOutgoingPressure"):
            before_count = len(tribe.get("boundary_pressures", []) or [])
            tribe["boundary_pressures"] = [
                item for item in (tribe.get("boundary_pressures", []) or [])
                if not (
                    isinstance(item, dict)
                    and item.get("otherTribeId") == other_tribe_id
                    and item.get("state") == "pressing"
                )
            ]
            cleared_count = before_count - len(tribe.get("boundary_pressures", []) or [])
            if cleared_count:
                reward_parts.append("撤回己方压力")
        if other_tribe_id:
            relation_records = tribe.setdefault("boundary_relations", {})
            boundary_progress = relation_records.setdefault(other_tribe_id, {})
            if action.get("pressure"):
                pressure_chain_count = sum(
                    1 for item in self._active_boundary_pressures(tribe)
                    if isinstance(item, dict)
                    and item.get("otherTribeId") == other_tribe_id
                    and item.get("state") == "pressing"
                )
            relation_delta = int(action.get("relationDelta", 0) or 0)
            if pressure_chain_count:
                relation_delta -= 1
            trade_delta = int(action.get("tradeTrustDelta", 0) or 0)
            if relation_delta:
                boundary_progress["score"] = max(-9, min(9, int(boundary_progress.get("score", 0) or 0) + relation_delta))
                reward_parts.append(f"关系{relation_delta:+d}")
            if trade_delta:
                boundary_progress["tradeTrust"] = max(0, min(9, int(boundary_progress.get("tradeTrust", 0) or 0) + trade_delta))
                reward_parts.append(f"信任+{trade_delta}")
            boundary_progress["lastAction"] = action_key
            boundary_progress["lastActionAt"] = datetime.now().isoformat()
            relation_records[other_tribe_id] = boundary_progress
            other_tribe = self.tribes.get(other_tribe_id)
            if other_tribe:
                other_progress = other_tribe.setdefault("boundary_relations", {}).setdefault(tribe_id, {})
                if relation_delta:
                    other_progress["score"] = max(-9, min(9, int(other_progress.get("score", 0) or 0) + relation_delta))
                if trade_delta:
                    other_progress["tradeTrust"] = max(0, min(9, int(other_progress.get("tradeTrust", 0) or 0) + trade_delta))
                other_progress["lastAction"] = f"incoming:{action_key}"
                other_progress["lastActionAt"] = boundary_progress["lastActionAt"]
                trade_disrupt = int(action.get("tradeDisrupt", 0) or 0)
                if trade_disrupt:
                    other_tribe["trade_reputation"] = max(0, int(other_tribe.get("trade_reputation", 0) or 0) - trade_disrupt)
                    reward_parts.append(f"扰乱对方信誉-{trade_disrupt}")
                renown_disrupt = int(action.get("renownDisrupt", 0) or 0)
                if renown_disrupt:
                    other_tribe["renown"] = max(0, int(other_tribe.get("renown", 0) or 0) - renown_disrupt)
                    reward_parts.append(f"压低对方声望-{renown_disrupt}")
                aid_food = int(action.get("aidFood", 0) or 0)
                if aid_food:
                    other_tribe["food"] = int(other_tribe.get("food", 0) or 0) + aid_food
                    affected_tribe_ids.add(other_tribe_id)
                    reward_parts.append(f"援助对方食物+{aid_food}")
                if action.get("clearOutgoingPressure"):
                    before_count = len(other_tribe.get("boundary_pressures", []) or [])
                    other_tribe["boundary_pressures"] = [
                        item for item in (other_tribe.get("boundary_pressures", []) or [])
                        if not (
                            isinstance(item, dict)
                            and item.get("otherTribeId") == tribe_id
                            and item.get("state") == "pressured"
                        )
                    ]
                    if before_count != len(other_tribe.get("boundary_pressures", []) or []):
                        affected_tribe_ids.add(other_tribe_id)
                if action.get("truce"):
                    active_until = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_BOUNDARY_TRUCE_MINUTES * 60).isoformat()
                    truce_record = {
                        "id": f"truce_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                        "state": "truce",
                        "title": action.get("label", "停争保护"),
                        "summary": f"与 {other_tribe.get('name', '其他部落')} 的边界进入短时停争，期间不能继续施压。",
                        "otherTribeId": other_tribe_id,
                        "otherTribeName": other_tribe.get("name", "其他部落"),
                        "activeUntil": active_until,
                        "createdAt": boundary_progress["lastActionAt"]
                    }
                    incoming_truce = {
                        **truce_record,
                        "id": f"incoming_truce_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                        "summary": f"{tribe.get('name', '对方部落')} 提出停争，边界进入短时保护。",
                        "otherTribeId": tribe_id,
                        "otherTribeName": tribe.get("name", "对方部落")
                    }
                    tribe.setdefault("boundary_truces", []).append(truce_record)
                    tribe["boundary_truces"] = tribe["boundary_truces"][-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                    other_tribe.setdefault("boundary_truces", []).append(incoming_truce)
                    other_tribe["boundary_truces"] = other_tribe["boundary_truces"][-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                    affected_tribe_ids.add(other_tribe_id)
                    reward_parts.append(f"停争保护{TRIBE_BOUNDARY_TRUCE_MINUTES}分钟")
                if action.get("pressure"):
                    active_until = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_BOUNDARY_PRESSURE_MINUTES * 60).isoformat()
                    pressure_title = action.get("label", "边界压力")
                    pressure_record = {
                        "id": f"pressure_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                        "state": "pressing",
                        "title": pressure_title,
                        "summary": f"对 {other_tribe.get('name', '其他部落')} 的边界行动正在施压。",
                        "otherTribeId": other_tribe_id,
                        "otherTribeName": other_tribe.get("name", "其他部落"),
                        "activeUntil": active_until,
                        "createdAt": boundary_progress["lastActionAt"]
                    }
                    incoming_record = {
                        "id": f"incoming_pressure_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                        "state": "pressured",
                        "title": f"遭遇{pressure_title}",
                        "summary": f"{tribe.get('name', '对方部落')} 正在边界施加压力，营地行动受到压迫。",
                        "otherTribeId": tribe_id,
                        "otherTribeName": tribe.get("name", "对方部落"),
                        "activeUntil": active_until,
                        "createdAt": boundary_progress["lastActionAt"]
                    }
                    tribe.setdefault("boundary_pressures", []).append(pressure_record)
                    tribe["boundary_pressures"] = tribe["boundary_pressures"][-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                    other_tribe.setdefault("boundary_pressures", []).append(incoming_record)
                    other_tribe["boundary_pressures"] = other_tribe["boundary_pressures"][-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                    affected_tribe_ids.add(other_tribe_id)
                    reward_parts.append(f"边界压制{TRIBE_BOUNDARY_PRESSURE_MINUTES}分钟")
                    if relation.get("state") == "hostile" and pressure_chain_count:
                        self._create_boundary_hostile_wear_task(
                            other_tribe,
                            tribe_id,
                            tribe.get("name", "对方部落"),
                            boundary_progress["lastActionAt"]
                        )
                        affected_tribe_ids.add(other_tribe_id)
                        reward_parts.append("长期敌意造成对方营地损耗")
            relation = self._flag_boundary_relation(tribe_id, flag) or relation
            affected_tribe_ids.update(self._ensure_boundary_outcome(tribe, relation))
            if action.get("pressure") and pressure_chain_count:
                reward_parts.append(f"压力连锁x{pressure_chain_count + 1}")

        member = tribe.get("members", {}).get(player_id, {})
        if action.get("sharedScout") and other_tribe:
            shared_sites = self._create_joint_watch_scout_sites(
                tribe,
                other_tribe,
                flag,
                relation,
                member.get("name", "成员")
            )
            if shared_sites:
                affected_tribe_ids.add(other_tribe_id)
                reward_parts.append("共享资源线索+1")
                market_pact = self._market_pact_between(tribe, other_tribe_id)
                if market_pact:
                    pact_bonus = TRIBE_MARKET_PACT_JOINT_WATCH_TRADE_TRUST
                    boundary_progress["tradeTrust"] = max(
                        0,
                        min(10, int(boundary_progress.get("tradeTrust", 0) or 0) + pact_bonus)
                    )
                    tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + TRIBE_MARKET_PACT_TRADE_REPUTATION_BONUS
                    if other_tribe:
                        other_progress = other_tribe.setdefault("boundary_relations", {}).setdefault(tribe_id, {})
                        other_progress["tradeTrust"] = max(
                            0,
                            min(10, int(other_progress.get("tradeTrust", 0) or 0) + pact_bonus)
                        )
                        other_tribe["trade_reputation"] = int(other_tribe.get("trade_reputation", 0) or 0) + TRIBE_MARKET_PACT_TRADE_REPUTATION_BONUS
                    reward_parts.append(f"互市约定守望信任+{pact_bonus}")
        record = {
            "kind": "boundary_action",
            "flagId": flag.get("id"),
            "flagLabel": flag.get("label", "领地旗帜"),
            "actionKey": action_key,
            "actionLabel": action.get("label", "边界行动"),
            "summary": action.get("summary", ""),
            "memberName": member.get("name", "成员"),
            "relation": relation,
            "relationProgress": dict(boundary_progress),
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        cooldowns[cooldown_key] = record["createdAt"]
        tribe.setdefault("boundary_actions", []).append(record)
        tribe["boundary_actions"] = tribe["boundary_actions"][-12:]
        detail = f"{record['memberName']} 在{record['flagLabel']}执行{record['actionLabel']}：{record['summary']} {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "governance", "边界行动", detail, player_id, record)
        await self._publish_world_rumor(
            "territory",
            f"边界{record['actionLabel']}",
            f"{tribe.get('name', '部落')} 在与 {relation.get('otherTribeName', '其他部落')} 的{relation.get('label', '边界')}上执行{record['actionLabel']}。",
            {"tribeId": tribe_id, "flagId": flag_id, "action": action_key, "relation": relation}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        if other_tribe_id and other_tribe_id in affected_tribe_ids:
            await self._notify_tribe(
                other_tribe_id,
                f"{tribe.get('name', '对方部落')} 在共同边界上执行了{record['actionLabel']}，部落面板出现了可回应的边界机会。"
            )
            await self.broadcast_tribe_state(other_tribe_id)
        if action.get("sharedScout") and reward_parts:
            await self._broadcast_current_map()
