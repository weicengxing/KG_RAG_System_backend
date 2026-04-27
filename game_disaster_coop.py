import math
import random
from datetime import datetime

from game_config import TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD


DISASTER_COOP_ACTIVE_MINUTES = 34
DISASTER_COOP_COOLDOWN_MINUTES = 26
DISASTER_COOP_TARGET = 3
DISASTER_COOP_RECORD_LIMIT = 6
DISASTER_COOP_TYPES = {
    "wildfire": {
        "label": "山火协作",
        "summary": "火线逼近营地外缘，成员需要分头救人、稳住粮柴，也可以冒险抢回物资。",
        "reward": {"renown": 2, "food": 1}
    },
    "flood": {
        "label": "洪水协作",
        "summary": "暴涨水线冲散旧路和库存，成员需要救援、垫高营地或趁退水寻找漂来的物资。",
        "reward": {"wood": 2, "tradeReputation": 1}
    },
    "cold": {
        "label": "寒潮协作",
        "summary": "冷风压住火堆和夜路，成员需要照看弱者、稳住营火或沿冰痕找补给。",
        "reward": {"food": 2, "renown": 1}
    },
    "sickness": {
        "label": "疫病协作",
        "summary": "营地传出病弱传闻，成员需要分药照看、隔开风险或趁乱换来稀缺物。",
        "reward": {"tradeReputation": 2}
    }
}
DISASTER_COOP_ACTIONS = {
    "rescue": {
        "label": "救援弱者",
        "summary": "把灾里最危险的人和物先救回来，增加声望并缓和边界口风。",
        "reward": {"renown": 1, "tradeReputation": 1},
        "pressureRelief": 1,
        "progress": 1,
        "animation": "guard"
    },
    "stabilize": {
        "label": "稳住营地",
        "summary": "加固营火、仓口和临时路，回收一点公共补给。",
        "reward": {"wood": 2, "food": 1},
        "progress": 1,
        "animation": "gather"
    },
    "profit": {
        "label": "趁机争利",
        "summary": "冒险把灾后物资和线索抢到本部落，但会让边界口风更紧。",
        "reward": {"food": 2, "discoveryProgress": 1},
        "pressureChange": 1,
        "progress": 1,
        "animation": "conflict"
    }
}


class GameDisasterCoopMixin:
    def _disaster_coop_rng(self):
        return getattr(self, "_weather_rng", random)

    def _disaster_coop_kind(self) -> str:
        weather = str(getattr(self, "current_weather", "") or "").lower()
        if "storm" in weather or "rain" in weather:
            return "flood"
        if "snow" in weather or "cold" in weather:
            return "cold"
        if "fog" in weather:
            return "sickness"
        return self._disaster_coop_rng().choice(list(DISASTER_COOP_TYPES.keys()))

    def _active_disaster_coop_tasks(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for task in tribe.get("disaster_coop_tasks", []) or []:
            if not isinstance(task, dict) or task.get("status", "active") != "active":
                continue
            try:
                if datetime.fromisoformat(task.get("activeUntil", "")) <= now:
                    task["status"] = "expired"
                    task["expiredAt"] = now.isoformat()
                    continue
            except (TypeError, ValueError):
                task["status"] = "expired"
                task["expiredAt"] = now.isoformat()
                continue
            active.append(task)
        tribe["disaster_coop_tasks"] = active[-1:]
        return tribe["disaster_coop_tasks"]

    def _ensure_disaster_coop_task(self, tribe: dict):
        if not tribe or self._active_disaster_coop_tasks(tribe):
            return None
        now = datetime.now()
        cooldown_until = tribe.get("disaster_coop_cooldown_until")
        if cooldown_until:
            try:
                if datetime.fromisoformat(cooldown_until) > now:
                    return None
            except (TypeError, ValueError):
                tribe["disaster_coop_cooldown_until"] = ""
        camp = tribe.get("camp") or {}
        center = camp.get("center") or {}
        if not center:
            return None
        rng = self._disaster_coop_rng()
        kind_key = self._disaster_coop_kind()
        kind = DISASTER_COOP_TYPES.get(kind_key, DISASTER_COOP_TYPES["wildfire"])
        angle = rng.random() * math.tau
        distance = 24 + rng.random() * 36
        task = {
            "id": f"disaster_coop_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{rng.randint(100, 999)}",
            "type": "disaster_coop_site",
            "status": "active",
            "kindKey": kind_key,
            "label": kind.get("label", "大灾协作"),
            "summary": kind.get("summary", ""),
            "x": max(-490, min(490, float(center.get("x", 0) or 0) + math.cos(angle) * distance)),
            "z": max(-490, min(490, float(center.get("z", 0) or 0) + math.sin(angle) * distance)),
            "y": 0,
            "size": 1.0,
            "target": DISASTER_COOP_TARGET,
            "progress": 0,
            "participants": [],
            "participantIds": [],
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + DISASTER_COOP_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["disaster_coop_tasks"] = [task]
        return task

    def _public_disaster_coop_tasks(self, tribe: dict) -> list:
        self._ensure_disaster_coop_task(tribe)
        return [dict(task) for task in self._active_disaster_coop_tasks(tribe)]

    def _public_disaster_coop_actions(self) -> dict:
        return DISASTER_COOP_ACTIONS

    def _public_disaster_coop_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("disaster_coop_records", []) or [])
            if isinstance(record, dict)
        ][-DISASTER_COOP_RECORD_LIMIT:]

    def _apply_disaster_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                storage[key] = int(storage.get(key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        return parts

    def _adjust_disaster_pressure(self, tribe: dict, delta: int) -> int:
        if not delta:
            return 0
        changed = 0
        for relation in (tribe.get("boundary_relations", {}) or {}).values():
            if not isinstance(relation, dict):
                continue
            before = int(relation.get("warPressure", 0) or 0)
            after = max(0, before + delta)
            relation["warPressure"] = after
            relation["canDeclareWar"] = after >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            changed += after - before
        return changed

    async def resolve_disaster_coop(self, player_id: str, task_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = DISASTER_COOP_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知大灾协作行动")
            return
        task = next((item for item in self._active_disaster_coop_tasks(tribe) if item.get("id") == task_id), None)
        if not task:
            await self._send_tribe_error(player_id, "这场大灾协作已经结束")
            return
        if player_id in (task.get("participantIds", []) or []):
            await self._send_tribe_error(player_id, "你已经参与过这场大灾协作")
            return

        member = tribe.get("members", {}).get(player_id, {})
        player = self.players.get(player_id, {}) if hasattr(self, "players") else {}
        member_name = member.get("name", player.get("name", "成员"))
        reward_parts = self._apply_disaster_reward(tribe, action.get("reward", {}))
        pressure_delta = int(action.get("pressureChange", 0) or 0) - int(action.get("pressureRelief", 0) or 0)
        pressure_changed = self._adjust_disaster_pressure(tribe, pressure_delta)
        if pressure_changed > 0:
            reward_parts.append(f"战争压力+{pressure_changed}")
        elif pressure_changed < 0:
            reward_parts.append(f"战争压力{pressure_changed}")
        participant = {
            "playerId": player_id,
            "name": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "协作"),
            "rewardParts": reward_parts,
            "joinedAt": datetime.now().isoformat()
        }
        task.setdefault("participantIds", []).append(player_id)
        task.setdefault("participants", []).append(participant)
        task["progress"] = int(task.get("progress", 0) or 0) + int(action.get("progress", 1) or 1)
        detail = f"{member_name}在{task.get('label', '大灾协作')}中选择{action.get('label', '协作')}，进度 {task['progress']}/{task.get('target', DISASTER_COOP_TARGET)}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "world_event", "大灾协作行动", detail, player_id, {"kind": "disaster_coop_action", "task": task, "participant": participant})

        if task["progress"] >= int(task.get("target", DISASTER_COOP_TARGET) or DISASTER_COOP_TARGET):
            await self._complete_disaster_coop(tribe_id, tribe, task, player_id)
            return
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        if hasattr(self, "_broadcast_current_map"):
            await self._broadcast_current_map()

    async def _complete_disaster_coop(self, tribe_id: str, tribe: dict, task: dict, player_id: str):
        now = datetime.now()
        kind = DISASTER_COOP_TYPES.get(task.get("kindKey"), {})
        final_parts = self._apply_disaster_reward(tribe, kind.get("reward", {}))
        task["status"] = "completed"
        task["completedAt"] = now.isoformat()
        task["completedBy"] = player_id
        task["finalRewardParts"] = final_parts
        names = "、".join(item.get("name", "成员") for item in (task.get("participants", []) or []))
        record = {
            "id": f"disaster_record_{tribe_id}_{int(now.timestamp() * 1000)}",
            "taskId": task.get("id"),
            "kindKey": task.get("kindKey"),
            "label": task.get("label", "大灾协作"),
            "summary": task.get("summary", ""),
            "participantNames": names,
            "participants": list(task.get("participants", []) or []),
            "rewardParts": final_parts,
            "completedAt": task["completedAt"]
        }
        tribe.setdefault("disaster_coop_records", []).append(record)
        tribe["disaster_coop_records"] = tribe["disaster_coop_records"][-DISASTER_COOP_RECORD_LIMIT:]
        tribe["disaster_coop_cooldown_until"] = datetime.fromtimestamp(
            now.timestamp() + DISASTER_COOP_COOLDOWN_MINUTES * 60
        ).isoformat()
        detail = f"{tribe.get('name', '部落')}完成了{record['label']}，{names}把大灾拆成了可处理的协作。"
        if final_parts:
            detail += f" {'、'.join(final_parts)}。"
        self._add_tribe_history(tribe, "world_event", "大灾协作完成", detail, player_id, {"kind": "disaster_coop_complete", "record": record})
        await self._publish_world_rumor(
            "world_event",
            "大灾协作",
            f"{tribe.get('name', '某个部落')}在{record['label']}中完成协作，{names}的选择被传成新的救灾故事。",
            {"tribeId": tribe_id, "taskId": task.get("id"), "kindKey": task.get("kindKey")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        if hasattr(self, "_broadcast_current_map"):
            await self._broadcast_current_map()
