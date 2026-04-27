import math
import random
from datetime import datetime

from game_config import *


class GameSanctuaryMixin:
    def _neutral_sanctuary_rng(self):
        return getattr(self, "_weather_rng", random)

    def _active_neutral_sanctuaries(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for sanctuary in tribe.get("neutral_sanctuaries", []) or []:
            if not isinstance(sanctuary, dict):
                continue
            status = sanctuary.get("status", "active")
            active_until = sanctuary.get("activeUntil")
            if status == "active" and active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        sanctuary["status"] = "expired"
                        sanctuary["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    sanctuary["status"] = "expired"
                    sanctuary["expiredAt"] = now.isoformat()
                    continue
            if sanctuary.get("status") in {"active", "dormant"}:
                active.append(sanctuary)
        tribe["neutral_sanctuaries"] = active[-TRIBE_NEUTRAL_SANCTUARY_LIMIT:]
        return tribe["neutral_sanctuaries"]

    def _active_neutral_sanctuary_blessings(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        blessings = []
        for blessing in tribe.get("neutral_sanctuary_blessings", []) or []:
            if not isinstance(blessing, dict):
                continue
            active_until = blessing.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    continue
            blessings.append(blessing)
        tribe["neutral_sanctuary_blessings"] = blessings[-TRIBE_NEUTRAL_SANCTUARY_LIMIT:]
        return tribe["neutral_sanctuary_blessings"]

    def _public_neutral_sanctuaries(self, tribe: dict) -> list:
        self._ensure_neutral_sanctuary(tribe)
        sanctuaries = []
        for sanctuary in self._active_neutral_sanctuaries(tribe):
            sanctuaries.append({
                "id": sanctuary.get("id"),
                "type": sanctuary.get("type", "neutral_sanctuary"),
                "label": sanctuary.get("label", "中立圣地"),
                "summary": sanctuary.get("summary", ""),
                "regionLabel": sanctuary.get("regionLabel", ""),
                "x": sanctuary.get("x", 0),
                "z": sanctuary.get("z", 0),
                "status": sanctuary.get("status", "active"),
                "useCount": int(sanctuary.get("useCount", 0) or 0),
                "useTarget": int(sanctuary.get("useTarget", TRIBE_NEUTRAL_SANCTUARY_USE_TARGET) or TRIBE_NEUTRAL_SANCTUARY_USE_TARGET),
                "restoreProgress": int(sanctuary.get("restoreProgress", 0) or 0),
                "restoreTarget": int(sanctuary.get("restoreTarget", TRIBE_NEUTRAL_SANCTUARY_RESTORE_TARGET) or TRIBE_NEUTRAL_SANCTUARY_RESTORE_TARGET),
                "rewardLabel": sanctuary.get("rewardLabel", ""),
                "lastActionLabel": sanctuary.get("lastActionLabel", ""),
                "lastActorName": sanctuary.get("lastActorName", ""),
                "activeUntil": sanctuary.get("activeUntil"),
                "dormantAt": sanctuary.get("dormantAt")
            })
        return sanctuaries

    def _public_neutral_sanctuary_actions(self) -> dict:
        return TRIBE_NEUTRAL_SANCTUARY_ACTIONS

    def _public_neutral_sanctuary_blessings(self, tribe: dict) -> list:
        return list(self._active_neutral_sanctuary_blessings(tribe))

    def _ensure_neutral_sanctuary(self, tribe: dict):
        if not tribe:
            return None
        active = self._active_neutral_sanctuaries(tribe)
        if active:
            return active[0]
        rng = self._neutral_sanctuary_rng()
        region = rng.choice(WORLD_REGIONS) if WORLD_REGIONS else {"x": 0, "z": 0, "radius": 90, "label": "荒野"}
        angle = rng.random() * math.pi * 2
        distance = max(24, math.sqrt(rng.random()) * min(120, int(region.get("radius", 90) or 90)))
        now = datetime.now()
        sanctuary = {
            "id": f"neutral_sanctuary_{tribe.get('id')}_{int(now.timestamp() * 1000)}",
            "type": "neutral_sanctuary",
            "status": "active",
            "label": f"{region.get('label', '荒野')}圣地",
            "summary": "一处不属于任何部落的短时朝圣地点；索取太频繁会沉寂，需要守静或献礼唤回。",
            "regionId": region.get("id"),
            "regionType": region.get("type"),
            "regionLabel": region.get("label", "荒野"),
            "x": max(-490, min(490, float(region.get("x", 0) or 0) + math.cos(angle) * distance)),
            "z": max(-490, min(490, float(region.get("z", 0) or 0) + math.sin(angle) * distance)),
            "y": 0,
            "size": 1.0,
            "useCount": 0,
            "useTarget": TRIBE_NEUTRAL_SANCTUARY_USE_TARGET,
            "restoreProgress": 0,
            "restoreTarget": TRIBE_NEUTRAL_SANCTUARY_RESTORE_TARGET,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_NEUTRAL_SANCTUARY_ACTIVE_MINUTES * 60).isoformat(),
            "rewardLabel": ""
        }
        tribe["neutral_sanctuaries"] = [sanctuary][-TRIBE_NEUTRAL_SANCTUARY_LIMIT:]
        return sanctuary

    def _apply_neutral_sanctuary_reward(self, tribe: dict, action: dict) -> list:
        parts = []
        reward = dict(action.get("reward", {}) or {})
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(reward.get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                parts.append(f"{label}+{amount}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            amount = int(reward.get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        pressure_relief = int(action.get("pressureRelief", 0) or 0)
        if pressure_relief:
            for relation in tribe.setdefault("boundary_relations", {}).values():
                relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                relation["lastAction"] = "neutral_sanctuary"
                relation["lastActionAt"] = datetime.now().isoformat()
            parts.append(f"战争压力-{pressure_relief}")
        return parts

    async def visit_neutral_sanctuary(self, player_id: str, sanctuary_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_NEUTRAL_SANCTUARY_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知圣地行动")
            return
        sanctuaries = self._active_neutral_sanctuaries(tribe)
        sanctuary = next((item for item in sanctuaries if item.get("id") == sanctuary_id), None)
        if not sanctuary:
            sanctuary = self._ensure_neutral_sanctuary(tribe)
        if not sanctuary or sanctuary.get("id") != sanctuary_id:
            await self._send_tribe_error(player_id, "这处中立圣地已经远去")
            return
        status = sanctuary.get("status", "active")
        if status == "dormant" and action_key == "pilgrimage":
            await self._send_tribe_error(player_id, "圣地正在沉寂，需要先守静或献礼")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        food_cost = int(action.get("foodCost", 0) or 0)
        wood_cost = int(action.get("woodCost", 0) or 0)
        stone_cost = int(action.get("stoneCost", 0) or 0)
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"圣地献礼需要食物 {food_cost}")
            return
        if int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"圣地献礼需要木材 {wood_cost}")
            return
        if int(storage.get("stone", 0) or 0) < stone_cost:
            await self._send_tribe_error(player_id, f"圣地献礼需要石块 {stone_cost}")
            return
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        if stone_cost:
            storage["stone"] = int(storage.get("stone", 0) or 0) - stone_cost

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        now = datetime.now()
        reward_parts = self._apply_neutral_sanctuary_reward(tribe, action)
        if action.get("usePressure") and status == "active":
            sanctuary["useCount"] = int(sanctuary.get("useCount", 0) or 0) + int(action.get("usePressure", 0) or 0)
        if action.get("restore"):
            sanctuary["restoreProgress"] = int(sanctuary.get("restoreProgress", 0) or 0) + int(action.get("restore", 0) or 0)
        restored = False
        if status == "dormant" and int(sanctuary.get("restoreProgress", 0) or 0) >= int(sanctuary.get("restoreTarget", TRIBE_NEUTRAL_SANCTUARY_RESTORE_TARGET) or TRIBE_NEUTRAL_SANCTUARY_RESTORE_TARGET):
            sanctuary["status"] = "active"
            sanctuary["useCount"] = 0
            sanctuary["restoreProgress"] = 0
            sanctuary["activeUntil"] = datetime.fromtimestamp(now.timestamp() + TRIBE_NEUTRAL_SANCTUARY_ACTIVE_MINUTES * 60).isoformat()
            sanctuary["restoredAt"] = now.isoformat()
            restored = True
        dormant = False
        if sanctuary.get("status") == "active" and int(sanctuary.get("useCount", 0) or 0) >= int(sanctuary.get("useTarget", TRIBE_NEUTRAL_SANCTUARY_USE_TARGET) or TRIBE_NEUTRAL_SANCTUARY_USE_TARGET):
            sanctuary["status"] = "dormant"
            sanctuary["dormantAt"] = now.isoformat()
            sanctuary["restoreProgress"] = 0
            dormant = True

        blessing = {
            "id": f"sanctuary_blessing_{tribe_id}_{int(now.timestamp() * 1000)}",
            "sanctuaryId": sanctuary.get("id"),
            "label": action.get("blessingLabel", action.get("label", "圣地祝福")),
            "summary": f"{member_name}在{sanctuary.get('label', '中立圣地')}完成{action.get('label', '朝圣')}。",
            "rewardLabel": "、".join(reward_parts) if reward_parts else self._reward_summary_text(action.get("reward", {})),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_NEUTRAL_SANCTUARY_BLESSING_MINUTES * 60).isoformat()
        }
        tribe.setdefault("neutral_sanctuary_blessings", []).append(blessing)
        tribe["neutral_sanctuary_blessings"] = tribe["neutral_sanctuary_blessings"][-TRIBE_NEUTRAL_SANCTUARY_LIMIT:]
        sanctuary["lastActionLabel"] = action.get("label", "朝圣")
        sanctuary["lastActorName"] = member_name
        sanctuary["rewardLabel"] = blessing.get("rewardLabel", "")
        sanctuary["updatedAt"] = now.isoformat()

        detail = f"{member_name}在{sanctuary.get('label', '中立圣地')}完成{action.get('label', '朝圣')}。"
        if reward_parts:
            detail += f" 收获：{'、'.join(reward_parts)}。"
        if restored:
            detail += " 沉寂的圣地重新亮起。"
        if dormant:
            detail += " 连续索取让圣地暂时沉寂，需要守静或献礼恢复。"
        self._add_tribe_history(tribe, "exploration", "中立圣地回应", detail, player_id, {
            "kind": "neutral_sanctuary",
            "sanctuary": sanctuary,
            "actionKey": action_key,
            "rewardParts": reward_parts
        })
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "neutral_sanctuary",
            "中立圣地有了回声",
            f"{tribe.get('name', '某个部落')}在{sanctuary.get('regionLabel', '荒野')}完成{action.get('label', '朝圣')}。",
            {"tribeId": tribe_id, "sanctuaryId": sanctuary.get("id"), "actionKey": action_key}
        )
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
