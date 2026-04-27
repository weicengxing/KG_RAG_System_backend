import random
from datetime import datetime

from game_config import *


class GameFarReturnMixin:
    def _far_reply_source_label(self, source_kind: str) -> str:
        labels = {
            "messenger": "盟约信使",
            "visitor": "边缘来访者",
            "apprentice": "学徒交换",
            "lost_item": "归还失物"
        }
        return labels.get(source_kind, "远方口信")

    def _far_reply_outcome(self, source_kind: str) -> dict:
        options = TRIBE_FAR_REPLY_OUTCOMES.get(source_kind) or sum(TRIBE_FAR_REPLY_OUTCOMES.values(), [])
        weights = [int(item.get("weight", 1) or 1) for item in options]
        return dict(random.choices(options, weights=weights, k=1)[0])

    def _public_far_reply_tasks(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for task in tribe.get("far_reply_tasks", []) or []:
            if not isinstance(task, dict) or task.get("status") != "pending":
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
            public_task = dict(task)
            ready_at = public_task.get("readyAt")
            public_task["ready"] = True
            if ready_at:
                try:
                    public_task["ready"] = datetime.fromisoformat(ready_at) <= now
                except (TypeError, ValueError):
                    public_task["ready"] = True
            active.append(public_task)
        if len(active) != len([item for item in tribe.get("far_reply_tasks", []) or [] if isinstance(item, dict) and item.get("status") == "pending"]):
            tribe["far_reply_tasks"] = active[-TRIBE_FAR_REPLY_LIMIT:]
        return active[-TRIBE_FAR_REPLY_LIMIT:]

    def _recent_far_reply_records(self, tribe: dict) -> list:
        return list(tribe.get("far_reply_records", []) or [])[-TRIBE_FAR_REPLY_RECENT_LIMIT:]

    def _schedule_far_reply(
        self,
        tribe: dict,
        source_kind: str,
        source_id: str,
        title: str = "",
        summary: str = "",
        other_tribe: dict | None = None,
        now_text: str = "",
    ) -> dict | None:
        if not tribe:
            return None
        now = datetime.fromisoformat(now_text) if now_text else datetime.now()
        safe_source_id = (source_id or f"{source_kind}_{int(now.timestamp() * 1000)}").replace(" ", "_")
        other_id = other_tribe.get("id") if other_tribe else ""
        source_key = f"{source_kind}:{safe_source_id}:{other_id}"
        existing = next((
            item for item in tribe.get("far_reply_tasks", []) or []
            if isinstance(item, dict)
            and item.get("sourceKey") == source_key
            and item.get("status") == "pending"
        ), None)
        if existing:
            return existing
        outcome = self._far_reply_outcome(source_kind)
        ready_at = datetime.fromtimestamp(now.timestamp() + TRIBE_FAR_REPLY_DELAY_MINUTES * 60)
        active_until = datetime.fromtimestamp(ready_at.timestamp() + TRIBE_FAR_REPLY_ACTIVE_MINUTES * 60)
        task = {
            "id": f"far_reply_{source_kind}_{safe_source_id}_{tribe.get('id')}_{int(now.timestamp() * 1000)}",
            "sourceKey": source_key,
            "status": "pending",
            "sourceKind": source_kind,
            "sourceLabel": self._far_reply_source_label(source_kind),
            "sourceId": safe_source_id,
            "title": title or f"{self._far_reply_source_label(source_kind)}的远方回信",
            "summary": summary or outcome.get("summary", "远方托人带回一段新的口信。"),
            "outcomeKey": outcome.get("key"),
            "outcomeLabel": outcome.get("label", "远方回信"),
            "outcomeSummary": outcome.get("summary", ""),
            "availableActions": list(outcome.get("actions", TRIBE_FAR_REPLY_ACTIONS.keys())),
            "otherTribeId": other_id,
            "otherTribeName": other_tribe.get("name") if other_tribe else "",
            "createdAt": now.isoformat(),
            "readyAt": ready_at.isoformat(),
            "activeUntil": active_until.isoformat()
        }
        for key in ("renownBonus", "tradeBonus", "relationBonus", "trustBonus", "discoveryBonus"):
            if int(outcome.get(key, 0) or 0):
                task[key] = int(outcome.get(key, 0) or 0)
        tribe.setdefault("far_reply_tasks", []).append(task)
        tribe["far_reply_tasks"] = tribe["far_reply_tasks"][-TRIBE_FAR_REPLY_LIMIT:]
        return task

    def _apply_far_reply_rewards(self, tribe: dict, task: dict, action: dict) -> list:
        parts = []
        food_cost = int(action.get("foodCost", 0) or 0)
        if food_cost:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) - food_cost)
            parts.append(f"食物-{food_cost}")
        food = int(action.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            parts.append(f"食物+{food}")
        renown = int(action.get("renown", 0) or 0) + int(task.get("renownBonus", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            parts.append(f"声望+{renown}")
        trade = int(action.get("tradeReputation", 0) or 0) + int(task.get("tradeBonus", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            parts.append(f"贸易信誉+{trade}")
        discovery = int(action.get("discoveryProgress", 0) or 0) + int(task.get("discoveryBonus", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            parts.append(f"发现+{discovery}")
        other_id = task.get("otherTribeId")
        relation_delta = int(action.get("relationDelta", 0) or 0) + int(task.get("relationBonus", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0) + int(task.get("trustBonus", 0) or 0)
        pressure_relief = int(action.get("warPressureRelief", 0) or 0)
        if other_id:
            relation = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
                parts.append(f"关系{relation_delta:+d}")
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
                parts.append(f"信任{trust_delta:+d}")
            if pressure_relief:
                relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                parts.append(f"战争压力-{pressure_relief}")
            relation["lastAction"] = f"far_reply_{task.get('sourceKind', 'message')}"
            relation["lastActionAt"] = datetime.now().isoformat()
        return parts

    async def respond_far_reply(self, player_id: str, reply_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((
            item for item in self._public_far_reply_tasks(tribe)
            if isinstance(item, dict) and item.get("id") == reply_id
        ), None)
        if not task:
            await self._send_tribe_error(player_id, "没有找到可回应的远方回信")
            return
        if not task.get("ready"):
            await self._send_tribe_error(player_id, "这封远方回信还在路上")
            return
        action = TRIBE_FAR_REPLY_ACTIONS.get(action_key)
        if not action or action_key not in (task.get("availableActions") or []):
            await self._send_tribe_error(player_id, "这封回信不能这样回应")
            return
        food_cost = int(action.get("foodCost", 0) or 0)
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"回应远方回信需要公共食物 {food_cost}")
            return

        original = next((
            item for item in tribe.get("far_reply_tasks", []) or []
            if isinstance(item, dict) and item.get("id") == reply_id
        ), task)
        now_text = datetime.now().isoformat()
        original["status"] = "completed"
        original["completedAt"] = now_text
        original["completedBy"] = player_id
        original["actionKey"] = action_key
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        reward_parts = self._apply_far_reply_rewards(tribe, task, action)
        record = {
            "id": f"far_reply_record_{reply_id}_{int(datetime.now().timestamp() * 1000)}",
            "sourceKind": task.get("sourceKind"),
            "sourceLabel": task.get("sourceLabel"),
            "title": task.get("title"),
            "outcomeLabel": task.get("outcomeLabel"),
            "actionLabel": action.get("label", "回应"),
            "memberName": member_name,
            "otherTribeId": task.get("otherTribeId"),
            "otherTribeName": task.get("otherTribeName"),
            "rewardParts": reward_parts,
            "createdAt": now_text
        }
        tribe.setdefault("far_reply_records", []).append(record)
        tribe["far_reply_records"] = tribe["far_reply_records"][-TRIBE_FAR_REPLY_RECENT_LIMIT:]
        song = None
        if hasattr(self, "_schedule_traveler_song"):
            song = self._schedule_traveler_song(
                tribe,
                "far_reply",
                reply_id,
                task.get("outcomeLabel", "远方回信"),
                f"{task.get('sourceLabel', '远方')}的回信被火边的人唱成短句，可能改变下一次传闻口风。",
                task.get("otherTribeId", "")
            )
            if song:
                reward_parts.append("旅人谣曲+1")
        detail = (
            f"{member_name} 回应了“{task.get('outcomeLabel', '远方回信')}”，"
            f"选择“{action.get('label', '回应')}”：{'、'.join(reward_parts) or '远方口信被记入营地'}。"
        )
        self._add_tribe_history(tribe, "trade", "远方回信", detail, player_id, {"kind": "far_reply", "record": record, "task": task, "travelerSong": song})
        await self._publish_world_rumor(
            "trade",
            "远方回信",
            f"{tribe.get('name', '部落')} 收到并回应了来自{task.get('sourceLabel', '远方')}的口信，新的关系被写进营火旁的故事。",
            {"tribeId": tribe_id, "replyId": reply_id, "sourceKind": task.get("sourceKind"), "action": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
