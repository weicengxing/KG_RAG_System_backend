import random
from datetime import datetime

from game_config import *


class GameShadowTaskMixin:
    def _shadow_task_key(self, tribe: dict) -> str:
        relations = tribe.get("boundary_relations", {}) or {}
        has_pressure = any(int(item.get("warPressure", 0) or 0) > 0 for item in relations.values() if isinstance(item, dict))
        if has_pressure:
            return "border"
        if int(tribe.get("trade_reputation", 0) or 0) >= 5:
            return "trade"
        if int(tribe.get("discovery_progress", 0) or 0) >= 4:
            return "explore"
        return random.choice(["hearth", "trade", "border", "explore"])

    def _active_shadow_task(self, tribe: dict) -> dict | None:
        if not tribe:
            return None
        task = tribe.get("shadow_task") or {}
        now = datetime.now()
        if isinstance(task, dict) and task.get("status") == "pending":
            try:
                if datetime.fromisoformat(task.get("activeUntil", "")) > now:
                    return task
            except (TypeError, ValueError):
                pass
            task["status"] = "expired"
            task["expiredAt"] = now.isoformat()
        if not tribe.get("members"):
            return None
        key = self._shadow_task_key(tribe)
        config = TRIBE_SHADOW_TASK_LIBRARY.get(key, TRIBE_SHADOW_TASK_LIBRARY["hearth"])
        task = {
            "id": f"shadow_task_{tribe.get('id')}_{int(now.timestamp() * 1000)}",
            "status": "pending",
            "key": key,
            "publicTitle": config.get("publicTitle", "部落影子任务"),
            "publicSummary": config.get("publicSummary", "成员可以推进一个看似普通的公共目标。"),
            "hiddenLabel": config.get("hiddenLabel", "隐藏倾向"),
            "revealSummary": config.get("revealSummary", "完成后会揭晓这件事真正指向什么。"),
            "progress": 0,
            "target": TRIBE_SHADOW_TASK_TARGET,
            "participantIds": [],
            "participantNames": [],
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_SHADOW_TASK_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["shadow_task"] = task
        return task

    def _public_shadow_task(self, tribe: dict) -> dict | None:
        task = self._active_shadow_task(tribe)
        if not task:
            return None
        public = dict(task)
        public.pop("revealSummary", None)
        public["hiddenHint"] = "真正意义会在完成后揭晓"
        return public

    def _public_shadow_task_records(self, tribe: dict) -> list:
        return list(tribe.get("shadow_task_records", []) or [])[-TRIBE_SHADOW_TASK_RECORD_LIMIT:]

    def _apply_shadow_task_rewards(self, tribe: dict, config: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            amount = int(config.get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        pressure_relief = int(config.get("warPressureRelief", 0) or 0)
        if pressure_relief:
            relieved = 0
            for relation in (tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                relation["warPressure"] = max(0, before - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                relieved += before - int(relation.get("warPressure", 0) or 0)
            if relieved:
                parts.append(f"战争压力-{relieved}")
        return parts

    async def advance_shadow_task(self, player_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if action_key not in TRIBE_SHADOW_TASK_ACTIONS:
            await self._send_tribe_error(player_id, "未知影子任务动作")
            return
        task = self._active_shadow_task(tribe)
        if not task:
            await self._send_tribe_error(player_id, "当前没有可推进的影子任务")
            return
        participant_ids = list(task.get("participantIds") or [])
        if player_id in participant_ids:
            await self._send_tribe_error(player_id, "你已经推进过这次影子任务")
            return
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        participant_ids.append(player_id)
        task["participantIds"] = participant_ids
        task.setdefault("participantNames", []).append(member_name)
        task["progress"] = int(task.get("progress", 0) or 0) + 1
        action = TRIBE_SHADOW_TASK_ACTIONS[action_key]
        now_text = datetime.now().isoformat()
        if int(task.get("progress", 0) or 0) < int(task.get("target", TRIBE_SHADOW_TASK_TARGET) or 1):
            detail = f"{member_name} 为“{task.get('publicTitle', '影子任务')}”{action.get('label', '出力')}，进度 {task.get('progress')} / {task.get('target')}。"
            self._add_tribe_history(tribe, "governance", "部落影子任务", detail, player_id, {"kind": "shadow_task", "taskId": task.get("id"), "action": action_key})
            await self._notify_tribe(tribe_id, detail)
            await self.broadcast_tribe_state(tribe_id)
            return

        config = TRIBE_SHADOW_TASK_LIBRARY.get(task.get("key"), TRIBE_SHADOW_TASK_LIBRARY["hearth"])
        reward_parts = self._apply_shadow_task_rewards(tribe, config)
        task["status"] = "completed"
        task["completedAt"] = now_text
        task["completedBy"] = player_id
        record = {
            "id": f"shadow_record_{task.get('id')}",
            "publicTitle": task.get("publicTitle"),
            "hiddenLabel": config.get("hiddenLabel", task.get("hiddenLabel")),
            "revealSummary": config.get("revealSummary", task.get("revealSummary", "")),
            "participantNames": list(task.get("participantNames") or []),
            "completedByName": member_name,
            "rewardParts": reward_parts,
            "createdAt": now_text
        }
        tribe.setdefault("shadow_task_records", []).append(record)
        tribe["shadow_task_records"] = tribe["shadow_task_records"][-TRIBE_SHADOW_TASK_RECORD_LIMIT:]
        tribe["shadow_task"] = {}
        detail = f"{member_name} 完成“{record['publicTitle']}”，揭晓为“{record['hiddenLabel']}”：{'、'.join(reward_parts) or '部落倾向被记录'}。"
        self._add_tribe_history(tribe, "governance", "部落影子任务揭晓", detail, player_id, {"kind": "shadow_task_completed", "record": record})
        await self._publish_world_rumor(
            "governance",
            "部落影子任务",
            f"{tribe.get('name', '部落')} 的一个公开目标揭晓为“{record['hiddenLabel']}”，族人开始重新理解这段共同劳动。",
            {"tribeId": tribe_id, "shadowTaskId": task.get("id"), "hiddenLabel": record["hiddenLabel"]}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
