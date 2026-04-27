from datetime import datetime
from typing import Optional

from game_config import *


class GameEmergencyChoiceMixin:
    def _active_emergency_world_event(self) -> Optional[dict]:
        env = self._get_current_environment()
        now = datetime.now()
        events = [event for event in (env.get("worldEvents", []) or []) if isinstance(event, dict)]
        for event in events:
            active_until = event.get("activeUntil")
            if not active_until:
                continue
            try:
                if datetime.fromisoformat(active_until) <= now:
                    continue
            except (TypeError, ValueError):
                continue
            return event
        return None

    def _emergency_contest_signal(self, tribe: dict) -> Optional[dict]:
        now = datetime.now()
        for conflict in tribe.get("small_conflicts", []) or []:
            if not isinstance(conflict, dict) or conflict.get("status") != "active":
                continue
            active_until = conflict.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    pass
            return {
                "id": conflict.get("id"),
                "kind": "small_conflict",
                "title": conflict.get("title", "小规模争夺"),
                "summary": f"{conflict.get('siteLabel', '争夺点')} 正在集结，{conflict.get('otherTribeName', '其他部落')} 也在回应。",
                "otherTribeId": conflict.get("otherTribeId"),
                "otherTribeName": conflict.get("otherTribeName", "其他部落")
            }
        for outcome in tribe.get("boundary_outcomes", []) or []:
            if not isinstance(outcome, dict) or outcome.get("status") != "pending":
                continue
            if outcome.get("kind") not in {"resource_site_contest", "cave_contest"} and outcome.get("state") != "hostile":
                continue
            return {
                "id": outcome.get("id"),
                "kind": outcome.get("kind", "boundary_outcome"),
                "title": outcome.get("title", "边界争夺"),
                "summary": outcome.get("summary", "边界出现需要公开回应的争夺。"),
                "otherTribeId": outcome.get("otherTribeId"),
                "otherTribeName": outcome.get("otherTribeName", "其他部落")
            }
        for pressure in tribe.get("war_pressure", []) or []:
            if not isinstance(pressure, dict) or int(pressure.get("pressure", 0) or 0) <= 0:
                continue
            return {
                "id": pressure.get("id") or f"war_pressure_{pressure.get('otherTribeId', '')}_{pressure.get('createdAt', '')}",
                "kind": "war_pressure",
                "title": "战争压力",
                "summary": f"与 {pressure.get('otherTribeName', '其他部落')} 的战争压力正在升高。",
                "otherTribeId": pressure.get("otherTribeId"),
                "otherTribeName": pressure.get("otherTribeName", "其他部落")
            }
        for pressure in tribe.get("boundary_pressures", []) or []:
            if not isinstance(pressure, dict):
                continue
            active_until = pressure.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    pass
            return {
                "id": pressure.get("id"),
                "kind": "boundary_pressure",
                "title": pressure.get("title", "边界压力"),
                "summary": pressure.get("summary", "边界压力仍在持续。"),
                "otherTribeId": pressure.get("otherTribeId"),
                "otherTribeName": pressure.get("otherTribeName", "其他部落")
            }
        return None

    def _active_emergency_choice(self, tribe: dict) -> Optional[dict]:
        if not tribe:
            return None
        now = datetime.now()
        choices = []
        active_choice = None
        for choice in tribe.get("emergency_choices", []) or []:
            if not isinstance(choice, dict):
                continue
            if choice.get("status") == "pending":
                try:
                    if datetime.fromisoformat(choice.get("activeUntil", "")) <= now:
                        choice["status"] = "expired"
                        choice["expiredAt"] = now.isoformat()
                    else:
                        active_choice = choice
                except (TypeError, ValueError):
                    choice["status"] = "expired"
                    choice["expiredAt"] = now.isoformat()
            choices.append(choice)
        tribe["emergency_choices"] = choices[-TRIBE_EMERGENCY_CHOICE_LIMIT:]
        if active_choice:
            return active_choice

        event = self._active_emergency_world_event()
        signal = self._emergency_contest_signal(tribe)
        if not event or not signal:
            return None
        signal_id = signal.get("id") or f"{signal.get('kind', 'contest')}_{signal.get('otherTribeId', '')}"
        choice_id = f"emergency_{tribe.get('id')}_{event.get('id')}_{signal_id}"
        if any(item.get("id") == choice_id for item in tribe.get("emergency_choices", []) or [] if isinstance(item, dict)):
            return None
        active_until = datetime.fromtimestamp(now.timestamp() + TRIBE_EMERGENCY_CHOICE_MINUTES * 60).isoformat()
        choice = {
            "id": choice_id,
            "status": "pending",
            "title": "紧急二选一",
            "summary": f"{event.get('regionLabel', '附近区域')} 的 {event.get('title', '世界事件')} 与 {signal.get('title', '边界争夺')} 同时压到营地，首领或长老需要公开决定先后。",
            "rescue": {
                "eventId": event.get("id"),
                "eventKey": event.get("key"),
                "title": event.get("title", "世界事件"),
                "regionLabel": event.get("regionLabel", "附近区域"),
                "summary": event.get("summary", "")
            },
            "contest": signal,
            "activeUntil": active_until,
            "createdAt": now.isoformat()
        }
        tribe.setdefault("emergency_choices", []).append(choice)
        tribe["emergency_choices"] = tribe["emergency_choices"][-TRIBE_EMERGENCY_CHOICE_LIMIT:]
        return choice

    def _public_emergency_followup_tasks(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("emergency_followup_tasks", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-TRIBE_EMERGENCY_FOLLOWUP_LIMIT:]

    def _apply_emergency_rewards(self, tribe: dict, rewards: dict, other_tribe_id: Optional[str] = None) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(rewards.get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                reward_parts.append(f"{label}{amount:+d}")
        food_cost = int(rewards.get("foodCost", 0) or 0)
        if food_cost:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) - food_cost)
            reward_parts.append(f"食物-{food_cost}")
        food = int(rewards.get("food", rewards.get("foodReward", 0)) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        discovery = int(rewards.get("discoveryProgress", rewards.get("discoveryReward", 0)) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        renown = int(rewards.get("renown", rewards.get("renownReward", 0)) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        trade = int(rewards.get("tradeReputation", rewards.get("tradeReward", 0)) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        relation_delta = int(rewards.get("relationDelta", 0) or 0)
        pressure_relief = int(rewards.get("pressureRelief", 0) or 0)
        if other_tribe_id:
            relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
                reward_parts.append(f"关系{relation_delta:+d}")
            if pressure_relief:
                before = int(relation.get("warPressure", 0) or 0)
                relation["warPressure"] = max(0, before - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                after = int(relation.get("warPressure", 0) or 0)
                if before != after:
                    reward_parts.append(f"战争压力-{before - after}")
        return reward_parts

    async def resolve_emergency_choice(self, player_id: str, choice_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以决定紧急优先级")
            return
        action = TRIBE_EMERGENCY_CHOICE_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知紧急选择")
            return
        choice = next((
            item for item in (tribe.get("emergency_choices", []) or [])
            if isinstance(item, dict) and item.get("id") == choice_id and item.get("status") == "pending"
        ), None)
        if not choice:
            await self._send_tribe_error(player_id, "这次紧急选择已经结束")
            return
        try:
            if datetime.fromisoformat(choice.get("activeUntil", "")) <= datetime.now():
                choice["status"] = "expired"
                await self._send_tribe_error(player_id, "这次紧急选择已经错过")
                return
        except (TypeError, ValueError):
            pass
        food_cost = int(action.get("foodCost", 0) or 0)
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"紧急处理需要食物 {food_cost}")
            return

        contest = choice.get("contest") or {}
        reward_parts = self._apply_emergency_rewards(tribe, action, contest.get("otherTribeId"))
        now_text = datetime.now().isoformat()
        choice["status"] = "resolved"
        choice["choice"] = action_key
        choice["choiceLabel"] = action.get("label", "紧急选择")
        choice["resolvedBy"] = player_id
        choice["resolvedByName"] = member.get("name", "管理者")
        choice["resolvedAt"] = now_text
        choice["rewardParts"] = reward_parts

        followup_plan = dict(action.get("followup") or {})
        followup = {
            "id": f"emergency_followup_{choice_id}_{action_key}",
            "status": "pending",
            "kind": f"emergency_{action_key}_aftermath",
            "title": action.get("abandonedTitle", "紧急补救"),
            "summary": action.get("abandonedSummary", "部落公开选择了一个方向，另一个方向需要事后补救。"),
            "sourceChoiceId": choice_id,
            "chosenAction": action_key,
            "chosenLabel": action.get("label", "紧急选择"),
            "otherTribeId": contest.get("otherTribeId"),
            "otherTribeName": contest.get("otherTribeName", "其他部落"),
            "createdAt": now_text,
            **followup_plan
        }
        tribe.setdefault("emergency_followup_tasks", []).append(followup)
        tribe["emergency_followup_tasks"] = tribe["emergency_followup_tasks"][-TRIBE_EMERGENCY_FOLLOWUP_LIMIT:]
        detail = f"{member.get('name', '管理者')} 在紧急二选一中选择{action.get('label', '优先处理')}：{'、'.join(reward_parts) or '局势暂稳'}。未优先处理的一侧转为“{followup['title']}”。"
        self._add_tribe_history(tribe, "governance", "紧急二选一", detail, player_id, {"kind": "emergency_choice", "choiceId": choice_id, "action": action_key, "followup": followup})
        await self._publish_world_rumor(
            "governance",
            "紧急二选一",
            f"{tribe.get('name', '部落')} 面对救援与争夺同时压来，公开选择{action.get('label', '优先处理')}。",
            {"tribeId": tribe_id, "choiceId": choice_id, "action": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_emergency_followup_task(self, player_id: str, task_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((
            item for item in (tribe.get("emergency_followup_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") == task_id and item.get("status") == "pending"
        ), None)
        if not task:
            await self._send_tribe_error(player_id, "没有找到可处理的紧急补救")
            return
        food_cost = int(task.get("foodCost", 0) or 0)
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"处理补救需要食物 {food_cost}")
            return
        reward_parts = self._apply_emergency_rewards(tribe, task, task.get("otherTribeId"))
        now_text = datetime.now().isoformat()
        task["status"] = "completed"
        task["completedBy"] = player_id
        task["completedAt"] = now_text
        member = tribe.get("members", {}).get(player_id, {})
        detail = f"{member.get('name', '成员')} 完成{task.get('title', '紧急补救')}：{'、'.join(reward_parts) or '部落情绪稳定'}。"
        self._add_tribe_history(tribe, "governance", "紧急补救", detail, player_id, {"kind": "emergency_followup", "taskId": task_id, "sourceChoiceId": task.get("sourceChoiceId")})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
