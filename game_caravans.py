import random
from datetime import datetime

from game_config import *


class GameCaravanMixin:
    def _active_caravan_routes(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for route in tribe.get("caravan_routes", []) or []:
            if not isinstance(route, dict) or route.get("status") != "pending":
                continue
            active_until = route.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        route["status"] = "expired"
                        continue
                except (TypeError, ValueError):
                    route["status"] = "expired"
                    continue
            active.append(route)
        if len(active) != len(tribe.get("caravan_routes", []) or []):
            tribe["caravan_routes"] = active[-TRIBE_NOMAD_CARAVAN_LIMIT:]
        return active[-TRIBE_NOMAD_CARAVAN_LIMIT:]

    def _caravan_focus_label(self, site: dict) -> str:
        reward = dict(site.get("reward") or {})
        if int(reward.get("food", 0) or 0):
            return "盐肉与干鱼"
        if int(reward.get("stone", 0) or 0):
            return "石刃与磨石"
        if int(reward.get("wood", 0) or 0):
            return "木牌与树脂"
        if int(reward.get("discoveryProgress", 0) or 0):
            return "旧物与残图"
        return "杂货与口信"

    def _append_nomad_caravan_route(self, tribe: dict, site: dict, now: datetime):
        if not tribe or not site:
            return None
        route_id = f"nomad_caravan_{site.get('sharedRouteId')}_{tribe.get('id')}"
        existing = next((
            route for route in (tribe.get("caravan_routes", []) or [])
            if isinstance(route, dict) and route.get("id") == route_id and route.get("status") == "pending"
        ), None)
        if existing:
            return existing
        active_until = datetime.fromtimestamp(now.timestamp() + TRIBE_NOMAD_CARAVAN_ACTIVE_MINUTES * 60).isoformat()
        route = {
            "id": route_id,
            "status": "pending",
            "type": "nomad_caravan",
            "label": "游牧商队",
            "title": "游牧商队停靠",
            "summary": f"边市热度引来一支带着{self._caravan_focus_label(site)}的中立商队，部落可以护送、招待或争取停靠。",
            "focusLabel": self._caravan_focus_label(site),
            "otherTribeId": site.get("partnerTribeId"),
            "otherTribeName": site.get("partnerTribeName", "邻近部落"),
            "sourceTradeRouteId": site.get("id"),
            "sharedRouteId": site.get("sharedRouteId"),
            "x": float(site.get("x", 0) or 0) + random.choice([-2.5, 2.5]),
            "z": float(site.get("z", 0) or 0) + random.choice([-2.0, 2.0]),
            "createdAt": now.isoformat(),
            "activeUntil": active_until
        }
        tribe.setdefault("caravan_routes", []).append(route)
        tribe["caravan_routes"] = tribe["caravan_routes"][-TRIBE_NOMAD_CARAVAN_LIMIT:]
        return route

    async def resolve_caravan_route(self, player_id: str, route_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        route = next((
            item for item in self._active_caravan_routes(tribe)
            if isinstance(item, dict) and item.get("id") == route_id
        ), None)
        if not route:
            await self._send_tribe_error(player_id, "这支商队已经离开")
            return
        action = TRIBE_NOMAD_CARAVAN_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知商队行动")
            return
        food_cost = int(action.get("foodCost", 0) or 0)
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"招待商队需要公共食物{food_cost}")
            return
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost

        now_text = datetime.now().isoformat()
        food_reward = int(action.get("food", 0) or 0)
        renown_reward = int(action.get("renown", 0) or 0)
        trade_reward = int(action.get("tradeReputation", 0) or 0)
        tribe["food"] = int(tribe.get("food", 0) or 0) + food_reward
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown_reward
        tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_reward

        other_tribe_id = route.get("otherTribeId")
        relation_delta = int(action.get("relationDelta", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        if other_tribe_id:
            relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            relation["lastAction"] = f"nomad_caravan_{action_key}"
            relation["lastActionAt"] = now_text

        pact_created = None
        other_tribe = self.tribes.get(other_tribe_id) if other_tribe_id else None
        if action_key == "invite_stop" and other_tribe:
            pact_chance = min(0.95, self._market_pact_success_chance(tribe, other_tribe_id) + float(action.get("pactChanceBonus", 0) or 0))
            if random.random() <= pact_chance:
                pact_created = self._create_market_pact(tribe, other_tribe, route_id, now_text)

        route["status"] = "resolved"
        route["resolvedAt"] = now_text
        route["resolvedBy"] = player_id
        route["resolvedAction"] = action_key
        member = tribe.get("members", {}).get(player_id, {})
        reward_bits = []
        if food_cost:
            reward_bits.append(f"食物-{food_cost}")
        if food_reward:
            reward_bits.append(f"食物+{food_reward}")
        if renown_reward:
            reward_bits.append(f"声望+{renown_reward}")
        if trade_reward:
            reward_bits.append(f"贸易信誉+{trade_reward}")
        if relation_delta:
            reward_bits.append(f"关系{relation_delta:+d}")
        if trust_delta:
            reward_bits.append(f"信任+{trust_delta}")
        if pact_created:
            reward_bits.append(f"互市约定{TRIBE_MARKET_PACT_MINUTES}分钟")
        newcomer_influence = self._consume_newcomer_fate_influence(tribe, "diplomacy") if hasattr(self, "_consume_newcomer_fate_influence") else None
        if newcomer_influence:
            bonus = max(1, int(newcomer_influence.get("bonus", 1) or 1))
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + bonus
            reward_bits.append(f"{newcomer_influence.get('label', '新人关键')}贸易信誉+{bonus}")
            if other_tribe_id:
                relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + bonus))
        song = None
        if hasattr(self, "_schedule_traveler_song"):
            song = self._schedule_traveler_song(
                tribe,
                "caravan",
                route_id,
                route.get("label", "游牧商队"),
                f"游牧商队带着{route.get('focusLabel', '中立货物')}离开后，边市旁留下可传唱的短句。",
                other_tribe_id
            )
        if song:
            reward_bits.append("旅人谣曲+1")
        detail = f"{member.get('name', '成员')} 对游牧商队选择“{action.get('label', '商队行动')}”：{'、'.join(reward_bits) or '商队记住了这处边市'}。"
        self._add_tribe_history(tribe, "trade", "游牧商队", detail, player_id, {"kind": "nomad_caravan", "routeId": route_id, "actionKey": action_key, "marketPact": pact_created, "travelerSong": song, "newcomerFateInfluence": newcomer_influence})
        if pact_created and other_tribe:
            other_detail = f"{tribe.get('name', '部落')} 借游牧商队停靠，与本部落续上新的互市约定。"
            self._add_tribe_history(other_tribe, "trade", "商队互市约定", other_detail, player_id, {"kind": "nomad_caravan_pact", "otherTribeId": tribe_id})
            await self._notify_tribe(other_tribe_id, other_detail)
            await self.broadcast_tribe_state(other_tribe_id)
        await self._publish_world_rumor(
            "trade",
            "游牧商队",
            f"{tribe.get('name', '部落')} 在边市旁{action.get('label', '接待商队')}，让游牧商队把新的口信带向远处。",
            {"tribeId": tribe_id, "routeId": route_id, "action": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
