import random
from datetime import datetime

from game_config import *


class GameRumorTruthMixin:
    def _rumor_truth_rng(self):
        return getattr(self, "_weather_rng", random)

    def _active_rumor_truth_tasks(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for task in tribe.get("rumor_truth_tasks", []) or []:
            if not isinstance(task, dict) or task.get("status", "active") != "active":
                continue
            active_until = task.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        task["status"] = "expired"
                        task["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    task["status"] = "expired"
                    task["expiredAt"] = now.isoformat()
                    continue
            active.append(task)
        tribe["rumor_truth_tasks"] = active[-TRIBE_RUMOR_TRUTH_LIMIT:]
        return tribe["rumor_truth_tasks"]

    def _active_rumor_truth_hints(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        hints = []
        for hint in tribe.get("rumor_truth_hints", []) or []:
            if not isinstance(hint, dict):
                continue
            active_until = hint.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    continue
            hints.append(hint)
        tribe["rumor_truth_hints"] = hints[-TRIBE_RUMOR_TRUTH_LIMIT:]
        return tribe["rumor_truth_hints"]

    def _public_rumor_truth_tasks(self, tribe: dict) -> list:
        self._ensure_rumor_truth_task(tribe)
        return [
            {
                "id": task.get("id"),
                "title": task.get("title", "待辨认传闻"),
                "summary": task.get("summary", ""),
                "sourceLabel": task.get("sourceLabel", "传闻"),
                "toneLabel": task.get("toneLabel", "未辨"),
                "riskLabel": task.get("riskLabel", "可能有误"),
                "createdAt": task.get("createdAt"),
                "activeUntil": task.get("activeUntil")
            }
            for task in self._active_rumor_truth_tasks(tribe)
        ]

    def _public_rumor_truth_actions(self) -> dict:
        return TRIBE_RUMOR_TRUTH_ACTIONS

    def _public_rumor_truth_records(self, tribe: dict) -> list:
        return [item for item in tribe.get("rumor_truth_records", []) or [] if isinstance(item, dict)][-TRIBE_RUMOR_TRUTH_RECORD_LIMIT:]

    def _public_rumor_truth_hints(self, tribe: dict) -> list:
        return self._active_rumor_truth_hints(tribe)

    def _rumor_truth_source(self, tribe: dict) -> dict | None:
        if self.world_rumors:
            rumor = self.world_rumors[-1]
            return {
                "sourceId": rumor.get("id"),
                "sourceKind": rumor.get("type", "world_rumor"),
                "sourceLabel": "世界传闻",
                "title": rumor.get("title", "远处传来新说法"),
                "summary": rumor.get("text", "这条传闻还没有被部落确认。")
            }
        for key, label in (
            ("nomad_visitor_aftereffects", "来访余音"),
            ("map_memories", "活地图记忆"),
            ("world_event_remnants", "事件余迹"),
            ("weather_forecast_records", "风向记录")
        ):
            items = [item for item in tribe.get(key, []) or [] if isinstance(item, dict)]
            if items:
                item = items[-1]
                return {
                    "sourceId": item.get("id"),
                    "sourceKind": key,
                    "sourceLabel": label,
                    "title": item.get("title") or item.get("label") or label,
                    "summary": item.get("summary") or item.get("detail") or "这条线索被带回营地，但真假还没有说定。"
                }
        history = [item for item in tribe.get("history", []) or [] if isinstance(item, dict)]
        if history:
            item = history[-1]
            return {
                "sourceId": item.get("id"),
                "sourceKind": "history",
                "sourceLabel": "部落旧事",
                "title": item.get("title", "旧事传言"),
                "summary": item.get("detail", "旧事被再次提起，需要有人辨认它的走向。")
            }
        return None

    def _ensure_rumor_truth_task(self, tribe: dict):
        if not tribe or self._active_rumor_truth_tasks(tribe):
            return None
        source = self._rumor_truth_source(tribe)
        if not source:
            return None
        recent_sources = {
            item.get("sourceId")
            for item in (tribe.get("rumor_truth_records", []) or [])[-TRIBE_RUMOR_TRUTH_RECORD_LIMIT:]
            if isinstance(item, dict)
        }
        if source.get("sourceId") and source.get("sourceId") in recent_sources:
            return None
        rng = self._rumor_truth_rng()
        now = datetime.now()
        truth_state = rng.choice(["true", "true", "uncertain", "false"])
        task = {
            "id": f"rumor_truth_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{rng.randint(100, 999)}",
            "status": "active",
            "truthState": truth_state,
            "sourceId": source.get("sourceId"),
            "sourceKind": source.get("sourceKind"),
            "sourceLabel": source.get("sourceLabel", "传闻"),
            "title": source.get("title", "待辨认传闻"),
            "summary": source.get("summary", "这条传闻可能指向下一次机会，也可能只是路上的误会。"),
            "toneLabel": "可信" if truth_state == "true" else ("含混" if truth_state == "uncertain" else "可疑"),
            "riskLabel": "验证后收益更稳" if truth_state != "true" else "可直接转成线索",
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_RUMOR_TRUTH_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["rumor_truth_tasks"] = [task][-TRIBE_RUMOR_TRUTH_LIMIT:]
        return task

    def _apply_rumor_truth_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                parts.append(f"{label}{amount:+d}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = max(0, int(tribe.get(tribe_key, 0) or 0) + amount)
                parts.append(f"{label}{amount:+d}")
        return parts

    def _apply_rumor_pressure_relief(self, tribe: dict, amount: int) -> list:
        amount = int(amount or 0)
        if not amount:
            return []
        touched = 0
        for relation in tribe.setdefault("boundary_relations", {}).values():
            before = int(relation.get("warPressure", 0) or 0)
            if before <= 0:
                continue
            relation["warPressure"] = max(0, before - amount)
            relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relation["lastAction"] = "rumor_truth_counter"
            relation["lastActionAt"] = datetime.now().isoformat()
            touched += 1
        return [f"战争压力-{amount}"] if touched else []

    async def resolve_rumor_truth(self, player_id: str, rumor_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_RUMOR_TRUTH_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知传闻处理方式")
            return
        tasks = self._active_rumor_truth_tasks(tribe)
        task = next((item for item in tasks if item.get("id") == rumor_id), None)
        if not task:
            await self._send_tribe_error(player_id, "这条传闻已经散去")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        truth_state = task.get("truthState", "uncertain")
        reward_parts = self._apply_rumor_truth_reward(tribe, action.get("reward", {}))
        if truth_state == "true":
            reward_parts.extend(self._apply_rumor_truth_reward(tribe, action.get("trueBonus", {})))
        elif truth_state == "false":
            reward_parts.extend(self._apply_rumor_truth_reward(tribe, action.get("falseBonus", {})))
            reward_parts.extend(self._apply_rumor_truth_reward(tribe, action.get("falsePenalty", {})))
        else:
            reward_parts.extend(self._apply_rumor_truth_reward(tribe, action.get("uncertainBonus", {})))
        reward_parts.extend(self._apply_rumor_pressure_relief(tribe, action.get("pressureRelief", 0)))

        now = datetime.now()
        outcome_label = "坐实" if truth_state == "true" else ("存疑" if truth_state == "uncertain" else "走偏")
        hint = {
            "id": f"rumor_hint_{tribe_id}_{int(now.timestamp() * 1000)}",
            "sourceRumorId": task.get("id"),
            "sourceLabel": task.get("title", "传闻"),
            "actionKey": action_key,
            "actionLabel": action.get("label", "处理传闻"),
            "outcomeLabel": outcome_label,
            "summary": f"{member_name}把{task.get('sourceLabel', '传闻')}处理为{outcome_label}，后续事件会优先引用这条说法。",
            "rewardParts": reward_parts,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_RUMOR_TRUTH_HINT_MINUTES * 60).isoformat()
        }
        tribe.setdefault("rumor_truth_hints", []).append(hint)
        tribe["rumor_truth_hints"] = tribe["rumor_truth_hints"][-TRIBE_RUMOR_TRUTH_LIMIT:]
        record = {
            **hint,
            "id": f"rumor_record_{task.get('id')}_{int(now.timestamp())}",
            "sourceId": task.get("sourceId"),
            "truthState": truth_state,
            "toneLabel": task.get("toneLabel", ""),
            "memberName": member_name
        }
        tribe.setdefault("rumor_truth_records", []).append(record)
        tribe["rumor_truth_records"] = tribe["rumor_truth_records"][-TRIBE_RUMOR_TRUTH_RECORD_LIMIT:]
        task["status"] = "resolved"
        task["resolvedAt"] = now.isoformat()
        task["resolvedByName"] = member_name
        tribe["rumor_truth_tasks"] = [item for item in tasks if item.get("id") != rumor_id]

        detail = f"{member_name}对“{task.get('title', '传闻')}”选择{action.get('label', '处理')}，结果：{outcome_label}。"
        if reward_parts:
            detail += f" 收获：{'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "world_event", "辨认真伪", detail, player_id, {
            "kind": "rumor_truth",
            "record": record,
            "task": task
        })
        await self._publish_world_rumor(
            "rumor_truth",
            f"传闻被{outcome_label}",
            f"{tribe.get('name', '某个部落')}把“{task.get('title', '传闻')}”处理成了{outcome_label}的说法。",
            {"tribeId": tribe_id, "rumorId": task.get("id"), "actionKey": action_key, "truthState": truth_state}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
