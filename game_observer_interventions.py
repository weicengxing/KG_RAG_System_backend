from datetime import datetime

from game_config import *


class GameObserverInterventionMixin:
    def _observer_event_candidates(self, tribe: dict) -> list:
        candidates = []
        if self._active_standing_ritual(tribe):
            ritual = self._active_standing_ritual(tribe)
            candidates.append({"id": f"standing_ritual:{ritual.get('id')}", "sourceId": ritual.get("id"), "sourceKind": "standing_ritual", "title": ritual.get("label", "站位仪式"), "summary": ritual.get("summary", ""), "status": "active", "createdAt": ritual.get("createdAt")})
        for debt in self._public_camp_debts(tribe) if hasattr(self, "_public_camp_debts") else []:
            candidates.append({"id": f"camp_debt:{debt.get('id')}", "sourceId": debt.get("id"), "sourceKind": "camp_debt", "title": debt.get("title", "营地债账"), "summary": debt.get("summary", ""), "status": "pending", "createdAt": debt.get("createdAt")})
        for secret in self._public_public_secrets(tribe) if hasattr(self, "_public_public_secrets") else []:
            candidates.append({"id": f"public_secret:{secret.get('id')}", "sourceId": secret.get("id"), "sourceKind": "public_secret", "title": secret.get("title", "公共秘密"), "summary": secret.get("summary", ""), "status": "pending", "createdAt": secret.get("createdAt")})
        for race in self._public_cave_races(tribe) if hasattr(self, "_public_cave_races") else []:
            if race.get("canClaim") or race.get("canRescue") or race.get("canRescueRival") or race.get("canLeaveMarker"):
                candidates.append({"id": f"cave_race:{race.get('id')}", "sourceId": race.get("id"), "sourceKind": "cave_race", "title": race.get("label") or race.get("title", "洞穴事件"), "summary": race.get("summary", ""), "status": race.get("status", "active"), "createdAt": race.get("createdAt")})
        for outcome in (tribe.get("boundary_outcomes", []) or []):
            if isinstance(outcome, dict) and outcome.get("status") == "pending":
                candidates.append({"id": f"boundary_outcome:{outcome.get('id')}", "sourceId": outcome.get("id"), "sourceKind": "boundary_outcome", "title": outcome.get("title", "边界结果"), "summary": outcome.get("summary", ""), "status": "pending", "createdAt": outcome.get("createdAt")})
        records = tribe.get("observer_intervention_records", []) or []
        for item in candidates:
            item["interventionCount"] = len([record for record in records if record.get("eventId") == item.get("id")])
            item["recentInterventions"] = [record for record in records if record.get("eventId") == item.get("id")][-3:]
        return candidates[:TRIBE_OBSERVER_OPPORTUNITY_LIMIT]

    def _public_observer_opportunities(self, tribe: dict) -> list:
        return self._observer_event_candidates(tribe)

    def _apply_observer_outcome_shift(self, tribe: dict, source_kind: str, source_id: str) -> dict | None:
        event_id = f"{source_kind}:{source_id}"
        records = [
            record for record in tribe.get("observer_intervention_records", []) or []
            if isinstance(record, dict) and record.get("eventId") == event_id and not record.get("outcomeAppliedAt")
        ]
        if not records:
            return None
        now_text = datetime.now().isoformat()
        reward_parts = []
        source_chain = []
        for record in records:
            reward = TRIBE_OBSERVER_OUTCOME_REWARDS.get(record.get("actionKey"), {})
            applied_parts = self._apply_tribe_reward(tribe, reward)
            record["outcomeAppliedAt"] = now_text
            record["outcomeRewardParts"] = applied_parts
            reward_parts.extend(applied_parts)
            source_chain.append({
                "memberName": record.get("memberName", "旁观者"),
                "roleLabel": (record.get("role") or {}).get("label", "旁观者"),
                "actionLabel": record.get("actionLabel", "补上一句"),
                "rewardParts": applied_parts
            })
        names = "、".join(f"{item['memberName']}-{item['actionLabel']}" for item in source_chain)
        return {
            "eventId": event_id,
            "sourceKind": source_kind,
            "sourceId": source_id,
            "sourceChain": source_chain,
            "rewardParts": reward_parts,
            "summary": f"旁观者让结局偏了一点：{names}。"
        }

    def _observer_role(self, player_id: str, target_tribe: dict, event: dict) -> dict:
        tribe_id = self.player_tribes.get(player_id)
        if tribe_id and tribe_id != target_tribe.get("id"):
            return {"key": "neutral", "label": "中立部落"}
        member = (target_tribe.get("members", {}) or {}).get(player_id, {})
        if int(member.get("contribution", 0) or 0) < 30:
            return {"key": "low_contribution", "label": "低贡献成员"}
        try:
            if member.get("joinedAt") and event.get("createdAt") and datetime.fromisoformat(member.get("joinedAt")) > datetime.fromisoformat(event.get("createdAt")):
                return {"key": "latecomer", "label": "迟到玩家"}
        except (TypeError, ValueError):
            pass
        return {"key": "witness", "label": "旁观者"}

    async def resolve_observer_intervention(self, player_id: str, target_tribe_id: str, event_id: str, action_key: str):
        actor_tribe_id = self.player_tribes.get(player_id)
        target_tribe = self.tribes.get(target_tribe_id or actor_tribe_id)
        if not target_tribe:
            await self._send_tribe_error(player_id, "没有可介入的部落事件")
            return
        action = TRIBE_OBSERVER_INTERVENTION_ACTIONS.get(action_key)
        event = next((item for item in self._observer_event_candidates(target_tribe) if item.get("id") == event_id), None)
        if not action or not event:
            await self._send_tribe_error(player_id, "这条旁观介入已经不可用")
            return
        records = target_tribe.setdefault("observer_intervention_records", [])
        if any(record.get("eventId") == event_id and record.get("playerId") == player_id for record in records):
            await self._send_tribe_error(player_id, "你已经介入过这条事件")
            return
        actor_tribe = self.tribes.get(actor_tribe_id) if actor_tribe_id else target_tribe
        storage = (actor_tribe or target_tribe).setdefault("storage", {"wood": 0, "stone": 0})
        if int(action.get("woodCost", 0) or 0) and int(storage.get("wood", 0) or 0) < int(action.get("woodCost", 0) or 0):
            await self._send_tribe_error(player_id, "介入需要木材")
            return
        if int(action.get("foodCost", 0) or 0) and int((actor_tribe or target_tribe).get("food", 0) or 0) < int(action.get("foodCost", 0) or 0):
            await self._send_tribe_error(player_id, "介入需要食物")
            return
        storage["wood"] = int(storage.get("wood", 0) or 0) - int(action.get("woodCost", 0) or 0)
        if int(action.get("foodCost", 0) or 0):
            actor_tribe["food"] = int(actor_tribe.get("food", 0) or 0) - int(action.get("foodCost", 0) or 0)
        member = ((actor_tribe or target_tribe).get("members", {}) or {}).get(player_id, {})
        role = self._observer_role(player_id, target_tribe, event)
        reward_parts = self._apply_tribe_reward(target_tribe, action.get("reward", {}))
        record = {"id": f"observer_{int(datetime.now().timestamp() * 1000)}", "eventId": event_id, "sourceKind": event.get("sourceKind"), "eventTitle": event.get("title"), "actionKey": action_key, "actionLabel": action.get("label"), "playerId": player_id, "memberName": member.get("name", "旁观者"), "role": role, "rewardParts": reward_parts, "createdAt": datetime.now().isoformat()}
        records.append(record)
        target_tribe["observer_intervention_records"] = records[-TRIBE_OBSERVER_INTERVENTION_LIMIT:]
        detail = f"{record['memberName']}以{role['label']}身份对“{event.get('title', '未结算事件')}”{action.get('label', '补上一句')}，{'、'.join(reward_parts) or '来源链已改写'}。"
        self._add_tribe_history(target_tribe, "world_event", "旁观者改写结局", detail, player_id, {"kind": "observer_intervention", "record": record})
        await self._publish_world_rumor("world_event", "旁观者介入", f"{target_tribe.get('name', '部落')}的{event.get('title', '事件')}被{role['label']}轻轻改写。", {"tribeId": target_tribe.get("id"), "eventId": event_id, "actionKey": action_key})
        await self._notify_tribe(target_tribe.get("id"), detail)
        await self.broadcast_tribe_state(target_tribe.get("id"))
