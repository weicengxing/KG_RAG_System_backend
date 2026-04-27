import random
from datetime import datetime

from game_config import *


class GameWonderMixin:
    def _active_wonder_project(self, tribe: dict) -> dict | None:
        if not tribe:
            return None
        project = tribe.get("wonder_project")
        now = datetime.now()
        if isinstance(project, dict) and project.get("status") == "active":
            try:
                if datetime.fromisoformat(project.get("activeUntil", "")) > now:
                    return project
            except (TypeError, ValueError):
                pass
            project["status"] = "expired"
            project["expiredAt"] = now.isoformat()
        if not tribe.get("members"):
            return None
        project = {
            "id": f"wonder_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "label": "未定形奇观",
            "summary": "同一座奇观正在营地旁成形，成员投入的来源会决定它最终成为观星台、议会环、祖灵门或火祭坛。",
            "target": min(TRIBE_WONDER_TARGET, max(1, len(tribe.get("members", {}) or {}) or 1)),
            "contributions": [],
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_WONDER_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["wonder_project"] = project
        return project

    def _public_wonder_project(self, tribe: dict) -> dict | None:
        project = self._active_wonder_project(tribe)
        if not project:
            return None
        contributions = [item for item in project.get("contributions", []) or [] if isinstance(item, dict)]
        counts = {}
        for item in contributions:
            outcome_key = item.get("outcomeKey")
            counts[outcome_key] = counts.get(outcome_key, 0) + 1
        leading_key = max(counts, key=counts.get) if counts else ""
        leading = TRIBE_WONDER_OUTCOMES.get(leading_key, {})
        return {
            "id": project.get("id"),
            "label": project.get("label"),
            "summary": project.get("summary"),
            "progress": len(contributions),
            "target": project.get("target", TRIBE_WONDER_TARGET),
            "contributions": contributions,
            "leadingOutcomeLabel": leading.get("label", "未定形"),
            "activeUntil": project.get("activeUntil")
        }

    def _public_wonder_actions(self, tribe: dict) -> dict:
        actions = {}
        storage = tribe.get("storage", {}) or {}
        for key, action in TRIBE_WONDER_ACTIONS.items():
            item = dict(action)
            wood_cost = int(item.get("woodCost", 0) or 0)
            item["available"] = not wood_cost or int(storage.get("wood", 0) or 0) >= wood_cost
            item["lockedReason"] = "" if item["available"] else "公共木材不足"
            outcome = TRIBE_WONDER_OUTCOMES.get(item.get("outcomeKey"), {})
            item["outcomeLabel"] = outcome.get("label", "")
            actions[key] = item
        return actions

    def _public_wonder_records(self, tribe: dict) -> list:
        return [
            item for item in tribe.get("wonder_records", []) or []
            if isinstance(item, dict)
        ][-TRIBE_WONDER_RECORD_LIMIT:]

    def _public_wonder_auras(self, tribe: dict) -> list:
        now = datetime.now()
        active = []
        for aura in tribe.get("wonder_auras", []) or []:
            if not isinstance(aura, dict):
                continue
            try:
                if datetime.fromisoformat(aura.get("activeUntil", "")) <= now:
                    continue
            except (TypeError, ValueError):
                continue
            active.append(aura)
        tribe["wonder_auras"] = active[-TRIBE_WONDER_AURA_LIMIT:]
        return tribe["wonder_auras"]

    def _merge_wonder_reward(self, target: dict, reward: dict):
        for key, amount in (reward or {}).items():
            target[key] = int(target.get(key, 0) or 0) + int(amount or 0)

    def _apply_wonder_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        pressure_relief = int((reward or {}).get("warPressureRelief", 0) or 0)
        if pressure_relief:
            relieved = 0
            for relation in (tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                after = max(0, before - pressure_relief)
                relation["warPressure"] = after
                relation["canDeclareWar"] = after >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                relieved += before - after
            if relieved:
                parts.append(f"战争压力-{relieved}")
        return parts

    async def contribute_wonder(self, player_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_WONDER_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知奇观投入")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(action.get("woodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, "公共木材不足，无法投入火种")
            return
        project = self._active_wonder_project(tribe)
        if not project:
            await self._send_tribe_error(player_id, "当前没有可塑形的奇观")
            return
        contributions = project.setdefault("contributions", [])
        if any(item.get("memberId") == player_id for item in contributions if isinstance(item, dict)):
            await self._send_tribe_error(player_id, "你已经为这座奇观投入过来源")
            return
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", self._get_player_name(player_id))
        outcome = TRIBE_WONDER_OUTCOMES.get(action.get("outcomeKey"), {})
        contribution = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", action_key),
            "outcomeKey": action.get("outcomeKey"),
            "outcomeLabel": outcome.get("label", ""),
            "createdAt": datetime.now().isoformat()
        }
        contributions.append(contribution)
        member["contribution"] = int(member.get("contribution", 0) or 0) + 2
        target = int(project.get("target", TRIBE_WONDER_TARGET) or TRIBE_WONDER_TARGET)
        if len(contributions) >= target:
            await self._complete_wonder(player_id, tribe_id, tribe, project)
            return

        detail = f"{member_name}为“{project.get('label', '未定形奇观')}”{action.get('label', '投入来源')}，奇观暂时偏向{outcome.get('label', '未定形')}，进度 {len(contributions)} / {target}。"
        self._add_tribe_history(tribe, "ritual", "奇观塑形", detail, player_id, {"kind": "wonder_contribution", "contribution": contribution})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def _complete_wonder(self, player_id: str, tribe_id: str, tribe: dict, project: dict):
        counts = {}
        reward = {}
        for contribution in project.get("contributions", []) or []:
            outcome_key = contribution.get("outcomeKey")
            counts[outcome_key] = counts.get(outcome_key, 0) + 1
            action = TRIBE_WONDER_ACTIONS.get(contribution.get("actionKey"), {})
            self._merge_wonder_reward(reward, action.get("reward", {}))
        outcome_key = max(counts, key=counts.get) if counts else "observatory"
        outcome = TRIBE_WONDER_OUTCOMES.get(outcome_key, TRIBE_WONDER_OUTCOMES["observatory"])
        self._merge_wonder_reward(reward, outcome.get("reward", {}))
        reward_parts = self._apply_wonder_reward(tribe, reward)
        now = datetime.now()
        aura = {
            "id": f"wonder_aura_{project.get('id')}_{int(now.timestamp() * 1000)}",
            "label": outcome.get("auraLabel", "奇观余韵"),
            "outcomeKey": outcome_key,
            "outcomeLabel": outcome.get("label", "奇观"),
            "effectHint": outcome.get("effectHint", ""),
            "contributors": [item.get("memberName", "成员") for item in project.get("contributions", []) or []],
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_WONDER_AURA_MINUTES * 60).isoformat()
        }
        tribe.setdefault("wonder_auras", []).append(aura)
        tribe["wonder_auras"] = tribe["wonder_auras"][-TRIBE_WONDER_AURA_LIMIT:]
        record = {
            "id": f"wonder_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "label": outcome.get("label", "奇观"),
            "summary": outcome.get("summary", ""),
            "auraLabel": aura.get("label"),
            "effectHint": aura.get("effectHint"),
            "contributions": list(project.get("contributions", []) or []),
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        tribe.setdefault("wonder_records", []).append(record)
        tribe["wonder_records"] = tribe["wonder_records"][-TRIBE_WONDER_RECORD_LIMIT:]
        tribe["wonder_project"] = None
        names = "、".join(aura.get("contributors", []) or [])
        detail = f"{names or '成员'}把未定形奇观塑成“{record['label']}”：{'、'.join(reward_parts) or '奇观余韵留在营地'}。"
        self._add_tribe_history(tribe, "ritual", "多结局奇观成形", detail, player_id, {"kind": "wonder_complete", "record": record, "aura": aura})
        await self._publish_world_rumor(
            "ritual",
            "多结局奇观",
            f"{tribe.get('name', '部落')} 的未定形奇观最终成为“{record['label']}”，{aura.get('label', '奇观余韵')}开始被族人反复提起。",
            {"tribeId": tribe_id, "recordId": record.get("id"), "outcomeKey": outcome_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
