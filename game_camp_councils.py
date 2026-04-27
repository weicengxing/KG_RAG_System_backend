import random
from datetime import datetime

from game_config import *


class GameCampCouncilMixin:
    def _camp_council_issue_key(self, tribe: dict) -> str:
        relations = tribe.get("boundary_relations", {}) or {}
        if any(int(item.get("warPressure", 0) or 0) > 0 for item in relations.values() if isinstance(item, dict)):
            return "boundary"
        if tribe.get("rumor_truth_tasks") or tribe.get("rumor_truth_hints") or tribe.get("rumor_truth_records"):
            return "rumor"
        if tribe.get("shadow_task") or tribe.get("shadow_task_records"):
            return "shadow"
        if tribe.get("camp_shift") or tribe.get("camp_shift_records") or tribe.get("camp_trial_records"):
            return "shift"
        if tribe.get("tribe_law") or tribe.get("law_records") or tribe.get("law_remedies"):
            return "law"
        if hasattr(self, "_ash_ledger_sources") and self._ash_ledger_sources(tribe):
            return "ash"
        return random.choice(["hearth", "rumor", "shift", "boundary"])

    def _active_camp_council(self, tribe: dict) -> dict | None:
        if not tribe:
            return None
        council = tribe.get("camp_council")
        now = datetime.now()
        if isinstance(council, dict) and council.get("status") == "active":
            try:
                if datetime.fromisoformat(council.get("activeUntil", "")) > now:
                    return council
            except (TypeError, ValueError):
                pass
            council["status"] = "expired"
            council["expiredAt"] = now.isoformat()
        if not tribe.get("members"):
            return None
        issue_key = self._camp_council_issue_key(tribe)
        issue = TRIBE_CAMP_COUNCIL_LIBRARY.get(issue_key, TRIBE_CAMP_COUNCIL_LIBRARY["hearth"])
        council = {
            "id": f"camp_council_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "issueKey": issue_key,
            "label": issue.get("label", "营地议事圈"),
            "summary": issue.get("summary", "成员围着火边整理共同口径。"),
            "resultLabel": issue.get("resultLabel", "火边共识"),
            "target": min(TRIBE_CAMP_COUNCIL_TARGET, max(1, len(tribe.get("members", {}) or {}) or 1)),
            "responses": [],
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_CAMP_COUNCIL_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["camp_council"] = council
        return council

    def _public_camp_council(self, tribe: dict) -> dict | None:
        council = self._active_camp_council(tribe)
        if not council:
            return None
        responses = [item for item in council.get("responses", []) or [] if isinstance(item, dict)]
        return {
            "id": council.get("id"),
            "issueKey": council.get("issueKey"),
            "label": council.get("label"),
            "summary": council.get("summary"),
            "resultLabel": council.get("resultLabel"),
            "progress": len(responses),
            "target": council.get("target", TRIBE_CAMP_COUNCIL_TARGET),
            "responses": responses,
            "activeUntil": council.get("activeUntil")
        }

    def _public_camp_council_records(self, tribe: dict) -> list:
        return [
            item for item in tribe.get("camp_council_records", []) or []
            if isinstance(item, dict)
        ][-TRIBE_CAMP_COUNCIL_RECORD_LIMIT:]

    def _merge_camp_council_reward(self, target: dict, reward: dict):
        for key, amount in (reward or {}).items():
            target[key] = int(target.get(key, 0) or 0) + int(amount or 0)

    def _apply_camp_council_reward(self, tribe: dict, reward: dict) -> list:
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

    async def advance_camp_council(self, player_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_CAMP_COUNCIL_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知议事动作")
            return
        council = self._active_camp_council(tribe)
        if not council:
            await self._send_tribe_error(player_id, "当前没有可参与的营地议事圈")
            return
        responses = council.setdefault("responses", [])
        if any(item.get("memberId") == player_id for item in responses if isinstance(item, dict)):
            await self._send_tribe_error(player_id, "你已经参与过这次议事")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", self._get_player_name(player_id))
        response = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", action_key),
            "createdAt": datetime.now().isoformat()
        }
        responses.append(response)
        member["contribution"] = int(member.get("contribution", 0) or 0) + 1
        target = int(council.get("target", TRIBE_CAMP_COUNCIL_TARGET) or TRIBE_CAMP_COUNCIL_TARGET)
        if len(responses) >= target:
            await self._complete_camp_council(player_id, tribe_id, tribe, council)
            return

        detail = f"{member_name}在“{council.get('label', '营地议事圈')}”中选择{action.get('label', '听取')}，进度 {len(responses)} / {target}。"
        self._add_tribe_history(tribe, "governance", "营地议事圈", detail, player_id, {"kind": "camp_council", "response": response})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def _complete_camp_council(self, player_id: str, tribe_id: str, tribe: dict, council: dict):
        issue = TRIBE_CAMP_COUNCIL_LIBRARY.get(council.get("issueKey"), TRIBE_CAMP_COUNCIL_LIBRARY["hearth"])
        reward = {}
        self._merge_camp_council_reward(reward, issue.get("reward", {}))
        action_counts = {}
        for response in council.get("responses", []) or []:
            action_key = response.get("actionKey")
            action_counts[action_key] = action_counts.get(action_key, 0) + 1
            action = TRIBE_CAMP_COUNCIL_ACTIONS.get(action_key, {})
            self._merge_camp_council_reward(reward, action.get("reward", {}))
        dominant_key = max(action_counts, key=action_counts.get) if action_counts else "listen"
        dominant_action = TRIBE_CAMP_COUNCIL_ACTIONS.get(dominant_key, TRIBE_CAMP_COUNCIL_ACTIONS["listen"])
        reward_parts = self._apply_camp_council_reward(tribe, reward)
        now = datetime.now()
        council["status"] = "completed"
        council["completedAt"] = now.isoformat()
        council["dominantActionLabel"] = dominant_action.get("label", "听取")
        council["rewardParts"] = reward_parts
        record = {
            "id": f"camp_council_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "label": council.get("label", "营地议事圈"),
            "summary": council.get("summary", ""),
            "resultLabel": issue.get("resultLabel", council.get("resultLabel", "火边共识")),
            "dominantActionLabel": council.get("dominantActionLabel"),
            "responses": list(council.get("responses", []) or []),
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        tribe.setdefault("camp_council_records", []).append(record)
        tribe["camp_council_records"] = tribe["camp_council_records"][-TRIBE_CAMP_COUNCIL_RECORD_LIMIT:]
        tribe["camp_council"] = None
        names = "、".join(item.get("memberName", "成员") for item in record["responses"])
        detail = f"{names or '成员'}把“{record['label']}”议成{record['resultLabel']}：{'、'.join(reward_parts) or '共识留在火边'}。"
        self._add_tribe_history(tribe, "governance", "营地议事圈收束", detail, player_id, {"kind": "camp_council_complete", "record": record})
        await self._publish_world_rumor(
            "governance",
            "营地议事圈",
            f"{tribe.get('name', '部落')} 围火议定“{record['label']}”，传出去的话变成了{record['resultLabel']}。",
            {"tribeId": tribe_id, "recordId": record.get("id")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
