import math
import random
from datetime import datetime

from game_config import *


class GameFogTrailMixin:
    def _fog_trail_rng(self):
        return getattr(self, "_weather_rng", random)

    def _active_fog_trails(self, tribe: dict) -> list:
        if not tribe:
            return []
        active = []
        now = datetime.now()
        for trail in tribe.get("fog_trails", []) or []:
            if not isinstance(trail, dict) or trail.get("status", "active") != "active":
                continue
            active_until = trail.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        trail["status"] = "expired"
                        trail["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    trail["status"] = "expired"
                    trail["expiredAt"] = now.isoformat()
                    continue
            active.append(trail)
        tribe["fog_trails"] = active[-TRIBE_FOG_TRAIL_LIMIT:]
        return tribe["fog_trails"]

    def _fog_trail_source(self, tribe: dict) -> dict:
        env = self._get_current_environment() if hasattr(self, "_get_current_environment") else {}
        weather = env.get("weather", "sunny")
        forecast = self._active_weather_forecast(tribe) if hasattr(self, "_active_weather_forecast") else None
        if weather == "fog":
            return {
                "key": "current_fog",
                "label": "当前雾气",
                "summary": "薄雾遮住营地外缘，声音、火光和路标都比平时更重要。"
            }
        if forecast and forecast.get("predictedWeather") == "fog":
            return {
                "key": "forecast_fog",
                "label": "风向预判",
                "summary": "族人已经预判薄雾将起，可以提前把探路经验记成路线。"
            }
        if tribe.get("night_outing_records") or tribe.get("oral_map_records"):
            return {
                "key": "old_path_fog",
                "label": "旧路薄雾",
                "summary": "夜行旧痕和口述路线附近升起薄雾，适合把旧路重新讲清。"
            }
        return {
            "key": "low_mist",
            "label": "低地薄雾",
            "summary": "营地边缘出现一片低雾，遮住近路，也露出可被记住的声音和火光。"
        }

    def _ensure_fog_trail(self, tribe: dict):
        if not tribe:
            return None
        active = self._active_fog_trails(tribe)
        if active:
            return active[0]
        center = ((tribe.get("camp") or {}).get("center") or {})
        if not center:
            return None
        rng = self._fog_trail_rng()
        angle = rng.random() * math.tau
        distance = 34 + rng.random() * 46
        now = datetime.now()
        source = self._fog_trail_source(tribe)
        trail = {
            "id": f"fog_trail_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{rng.randint(100, 999)}",
            "type": "fog_trail",
            "status": "active",
            "label": "雾区探路",
            "summary": source.get("summary", "短时薄雾遮住路线，成员可以试探方向。"),
            "sourceKey": source.get("key", "low_mist"),
            "sourceLabel": source.get("label", "薄雾"),
            "x": max(-490, min(490, float(center.get("x", 0) or 0) + math.cos(angle) * distance)),
            "z": max(-490, min(490, float(center.get("z", 0) or 0) + math.sin(angle) * distance)),
            "y": 0,
            "radius": TRIBE_FOG_TRAIL_RADIUS,
            "participants": [],
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_FOG_TRAIL_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["fog_trails"] = [trail][-TRIBE_FOG_TRAIL_LIMIT:]
        return trail

    def _public_fog_trails(self, tribe: dict) -> list:
        self._ensure_fog_trail(tribe)
        return [dict(trail) for trail in self._active_fog_trails(tribe)]

    def _public_fog_trail_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("fog_trail_records", []) or [])
            if isinstance(record, dict)
        ][-TRIBE_FOG_TRAIL_RECORD_LIMIT:]

    def _public_fog_trail_actions(self, tribe: dict) -> dict:
        actions = {}
        for key, action in TRIBE_FOG_TRAIL_ACTIONS.items():
            support_labels = self._fog_trail_support_labels(tribe, key)
            actions[key] = {
                **action,
                "supportLabels": support_labels,
                "rewardLabel": self._reward_summary_text(action.get("reward", {})) if hasattr(self, "_reward_summary_text") else ""
            }
        return actions

    def _near_fog_trail(self, player_id: str, trail: dict) -> bool:
        player = self.players.get(player_id, {}) if hasattr(self, "players") else {}
        dx = float(player.get("x", 0) or 0) - float(trail.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(trail.get("z", 0) or 0)
        return math.sqrt(dx * dx + dz * dz) <= float(trail.get("radius", TRIBE_FOG_TRAIL_RADIUS) or TRIBE_FOG_TRAIL_RADIUS)

    def _fog_trail_support_labels(self, tribe: dict, action_key: str) -> list:
        labels = []
        if action_key == "listen" and tribe.get("night_outing_records"):
            labels.append("夜行旧痕")
        if action_key == "raise_fire":
            if self._has_tribe_structure_type(tribe, "campfire") if hasattr(self, "_has_tribe_structure_type") else False:
                labels.append("营火旧光")
            if tribe.get("sacred_fire_history"):
                labels.append("圣火余烬")
        if action_key == "mark_path" and (tribe.get("trail_markers") or tribe.get("trail_marker_history")):
            labels.append("活路标")
        if tribe.get("oral_map_records"):
            labels.append("口述地图")
        if tribe.get("world_riddle_records"):
            labels.append("谜语旧读")
        return labels[-4:]

    def _apply_fog_trail_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("food", "食物", "food")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        return parts

    async def explore_fog_trail(self, player_id: str, trail_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_FOG_TRAIL_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知雾区探路方式")
            return
        trail = next((item for item in self._active_fog_trails(tribe) if item.get("id") == trail_id), None)
        if not trail:
            await self._send_tribe_error(player_id, "这片雾区已经散去")
            return
        if any(item.get("memberId") == player_id for item in trail.get("participants", []) or []):
            await self._send_tribe_error(player_id, "你已经试探过这片雾区")
            return
        if not self._near_fog_trail(player_id, trail):
            await self._send_tribe_error(player_id, f"需要靠近雾区 {TRIBE_FOG_TRAIL_RADIUS} 步内")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(action.get("woodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"{action.get('label', '探路')}需要公共木材{wood_cost}")
            return
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost

        now = datetime.now()
        member = (tribe.get("members", {}) or {}).get(player_id, {}) or {}
        member_name = member.get("name", self.players.get(player_id, {}).get("name", "成员"))
        reward_parts = self._apply_fog_trail_reward(tribe, action.get("reward", {}))
        if wood_cost:
            reward_parts.insert(0, f"木材-{wood_cost}")
        support_labels = self._fog_trail_support_labels(tribe, action_key)
        memory = None
        if hasattr(self, "_record_map_memory"):
            memory = self._record_map_memory(
                tribe,
                "fog_trail",
                "雾中路线",
                f"{member_name}在{trail.get('sourceLabel', '薄雾')}里用“{action.get('label', '探路')}”记住了一段可重访的路线。",
                trail.get("x", 0),
                trail.get("z", 0),
                trail.get("id", ""),
                member_name
            )
            if memory:
                reward_parts.append("活地图记忆")
        participant = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "雾区探路"),
            "supportLabels": support_labels,
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        trail.setdefault("participants", []).append(participant)
        trail["lastActionLabel"] = action.get("label", "雾区探路")
        trail["lastActorName"] = member_name
        trail["rewardLabel"] = "、".join(reward_parts)
        record = {
            "id": f"fog_trail_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "trailId": trail.get("id"),
            "label": trail.get("label", "雾区探路"),
            "sourceLabel": trail.get("sourceLabel", "薄雾"),
            "summary": trail.get("summary", ""),
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "雾区探路"),
            "supportLabels": support_labels,
            "rewardParts": reward_parts,
            "mapMemoryId": memory.get("id") if memory else "",
            "createdAt": now.isoformat()
        }
        tribe.setdefault("fog_trail_records", []).append(record)
        tribe["fog_trail_records"] = tribe["fog_trail_records"][-TRIBE_FOG_TRAIL_RECORD_LIMIT:]
        detail = f"{member_name}在{trail.get('sourceLabel', '雾区')}完成{action.get('label', '雾区探路')}，{'、'.join(reward_parts) or '记住了一段雾中路线'}。"
        self._add_tribe_history(tribe, "exploration", "雾区探路", detail, player_id, {"kind": "fog_trail", "record": record, "trail": trail})
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "exploration",
            "雾区探路",
            f"{tribe.get('name', '某个部落')}在薄雾里重新确认了一条路线，后来的夜行、洞穴和谜语都多了一段可引用的说法。",
            {"tribeId": tribe_id, "trailId": trail.get("id"), "actionKey": action_key}
        )
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
