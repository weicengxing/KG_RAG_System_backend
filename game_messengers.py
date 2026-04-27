import random
from datetime import datetime

from game_config import *


class GameMessengerMixin:
    def _active_covenant_messenger_tasks(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for task in tribe.get("covenant_messenger_tasks", []) or []:
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
            active.append(task)
        if len(active) != len(tribe.get("covenant_messenger_tasks", []) or []):
            tribe["covenant_messenger_tasks"] = active[-TRIBE_COVENANT_MESSENGER_LIMIT:]
        return active[-TRIBE_COVENANT_MESSENGER_LIMIT:]

    def _messenger_source_label(self, source_kind: str) -> str:
        labels = {
            "market_pact": "互市信物",
            "war_truce": "停战信物",
            "boundary_truce": "停争信物",
            "disaster_relief": "救灾信物",
            "council": "议会信物",
            "atonement_token": "赎罪信物"
        }
        return labels.get(source_kind, "盟约信物")

    def _open_covenant_messenger_task_pair(
        self,
        tribe: dict,
        other_tribe: dict,
        source_kind: str,
        source_id: str,
        title: str,
        summary: str,
        now_text: str = "",
    ) -> list:
        if not tribe or not other_tribe:
            return []
        tribe_id = tribe.get("id")
        other_id = other_tribe.get("id")
        if not tribe_id or not other_id:
            return []
        now = datetime.now()
        now_text = now_text or now.isoformat()
        safe_source_id = (source_id or f"{source_kind}_{int(now.timestamp() * 1000)}").replace(" ", "_")
        shared_id = f"messenger_{source_kind}_{safe_source_id}_{tribe_id}_{other_id}"
        active_until = datetime.fromtimestamp(
            now.timestamp() + TRIBE_COVENANT_MESSENGER_ACTIVE_MINUTES * 60
        ).isoformat()
        created = []
        for source, target in ((tribe, other_tribe), (other_tribe, tribe)):
            existing = next((
                item for item in (source.get("covenant_messenger_tasks", []) or [])
                if isinstance(item, dict)
                and item.get("sharedTaskId") == shared_id
                and item.get("status") == "pending"
            ), None)
            if existing:
                created.append(existing)
                continue
            task = {
                "id": f"{shared_id}_{source.get('id')}",
                "sharedTaskId": shared_id,
                "status": "pending",
                "kind": "covenant_messenger",
                "sourceKind": source_kind,
                "sourceLabel": self._messenger_source_label(source_kind),
                "sourceId": safe_source_id,
                "title": title or "盟约信使",
                "summary": summary or f"把与 {target.get('name', '邻近部落')} 的新约定送成公开信物，避免只停在口头。",
                "otherTribeId": target.get("id"),
                "otherTribeName": target.get("name", "邻近部落"),
                "progress": 0,
                "target": TRIBE_COVENANT_MESSENGER_PROGRESS_TARGET,
                "participantIds": [],
                "participantNames": [],
                "renownReward": TRIBE_COVENANT_MESSENGER_RENOWN,
                "tradeReward": TRIBE_COVENANT_MESSENGER_TRADE,
                "relationDelta": TRIBE_COVENANT_MESSENGER_RELATION,
                "tradeTrustDelta": TRIBE_COVENANT_MESSENGER_TRUST,
                "createdAt": now_text,
                "activeUntil": active_until
            }
            source.setdefault("covenant_messenger_tasks", []).append(task)
            source["covenant_messenger_tasks"] = source["covenant_messenger_tasks"][-TRIBE_COVENANT_MESSENGER_LIMIT:]
            created.append(task)
        return created

    def _messenger_outcome(self) -> dict:
        options = list(TRIBE_COVENANT_MESSENGER_OUTCOMES.values())
        weights = [int(item.get("weight", 1) or 1) for item in options]
        return dict(random.choices(options, weights=weights, k=1)[0])

    def _apply_messenger_rewards(self, tribe: dict, other_tribe_id: str, task: dict, outcome: dict) -> list:
        reward_parts = []
        renown = int(task.get("renownReward", TRIBE_COVENANT_MESSENGER_RENOWN) or 0) + int(outcome.get("renownBonus", 0) or 0)
        trade = int(task.get("tradeReward", TRIBE_COVENANT_MESSENGER_TRADE) or 0) + int(outcome.get("tradeBonus", 0) or 0)
        relation_delta = int(task.get("relationDelta", TRIBE_COVENANT_MESSENGER_RELATION) or 0) + int(outcome.get("relationBonus", 0) or 0)
        trust_delta = int(task.get("tradeTrustDelta", TRIBE_COVENANT_MESSENGER_TRUST) or 0) + int(outcome.get("trustBonus", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        if other_tribe_id:
            relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
                reward_parts.append(f"关系{relation_delta:+d}")
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
                reward_parts.append(f"信任{trust_delta:+d}")
            relation["lastAction"] = f"covenant_messenger_{task.get('sourceKind', 'covenant')}"
            relation["lastActionAt"] = datetime.now().isoformat()
        return reward_parts

    def _mark_atonement_token_redeemed(self, tribe: dict, token_id: str, member_name: str, now_text: str, outcome: dict):
        if not tribe or not token_id:
            return
        for token in tribe.get("atonement_tokens", []) or []:
            if not isinstance(token, dict) or token.get("id") != token_id:
                continue
            if token.get("status") == "expired":
                return
            token["status"] = "redeemed"
            token["redeemedAt"] = now_text
            token["redeemedByName"] = member_name
            token["outcomeLabel"] = outcome.get("label", "")
            return

    def _complete_shared_messenger_tasks(self, shared_id: str, player_id: str, member_name: str, outcome: dict, now_text: str) -> set:
        affected = set()
        for target_tribe in self.tribes.values():
            for task in target_tribe.get("covenant_messenger_tasks", []) or []:
                if not isinstance(task, dict) or task.get("sharedTaskId") != shared_id or task.get("status") != "pending":
                    continue
                task["status"] = "completed"
                task["progress"] = int(task.get("target", TRIBE_COVENANT_MESSENGER_PROGRESS_TARGET) or 1)
                task["completedBy"] = player_id
                task["completedByName"] = member_name
                task["completedAt"] = now_text
                task["outcomeKey"] = outcome.get("key")
                task["outcomeLabel"] = outcome.get("label")
                if task.get("sourceKind") == "atonement_token":
                    self._mark_atonement_token_redeemed(target_tribe, task.get("sourceId", ""), member_name, now_text, outcome)
                affected.add(target_tribe.get("id"))
        return {item for item in affected if item}

    async def escort_covenant_messenger(self, player_id: str, task_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((
            item for item in self._active_covenant_messenger_tasks(tribe)
            if isinstance(item, dict) and item.get("id") == task_id
        ), None)
        if not task:
            await self._send_tribe_error(player_id, "没有找到可护送的盟约信物")
            return
        participant_ids = list(task.get("participantIds") or [])
        if player_id in participant_ids:
            await self._send_tribe_error(player_id, "你已经护送过这件信物")
            return
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        participant_ids.append(player_id)
        task["participantIds"] = participant_ids
        task.setdefault("participantNames", []).append(member_name)
        task["progress"] = int(task.get("progress", 0) or 0) + 1
        now_text = datetime.now().isoformat()
        target = int(task.get("target", TRIBE_COVENANT_MESSENGER_PROGRESS_TARGET) or 1)
        if int(task.get("progress", 0) or 0) < target:
            detail = f"{member_name} 护送{task.get('sourceLabel', '盟约信物')}，进度 {task.get('progress', 0)} / {target}。"
            self._add_tribe_history(tribe, "trade", "盟约信使", detail, player_id, {"kind": "covenant_messenger", "taskId": task_id})
            await self._notify_tribe(tribe_id, detail)
            await self.broadcast_tribe_state(tribe_id)
            return

        outcome = self._messenger_outcome()
        other_id = task.get("otherTribeId")
        other_tribe = self.tribes.get(other_id) if other_id else None
        affected = self._complete_shared_messenger_tasks(task.get("sharedTaskId"), player_id, member_name, outcome, now_text)
        reward_bits = self._apply_messenger_rewards(tribe, other_id, task, outcome)
        if other_tribe:
            mirror = next((
                item for item in other_tribe.get("covenant_messenger_tasks", []) or []
                if isinstance(item, dict) and item.get("sharedTaskId") == task.get("sharedTaskId")
            ), task)
            self._apply_messenger_rewards(other_tribe, tribe_id, mirror, outcome)
        if hasattr(self, "_schedule_far_reply"):
            shared_id = task.get("sharedTaskId") or task_id
            self._schedule_far_reply(
                tribe,
                "messenger",
                shared_id,
                "盟约信使的远方回信",
                f"{task.get('sourceLabel', '盟约信物')}送达后，远方可能托人带回感谢、误解或新的交易口风。",
                other_tribe,
                now_text
            )
            if other_tribe:
                self._schedule_far_reply(
                    other_tribe,
                    "messenger",
                    shared_id,
                    "盟约信使的远方回信",
                    f"{task.get('sourceLabel', '盟约信物')}送达后，远方可能托人带回感谢、误解或新的交易口风。",
                    tribe,
                    now_text
                )
        detail = (
            f"{member_name} 把{task.get('sourceLabel', '盟约信物')}送到 {task.get('otherTribeName', '邻近部落')}："
            f"{outcome.get('summary', '信物被双方承认')} {'、'.join(reward_bits) or '外交记忆稳定'}。"
        )
        related = {
            "kind": "covenant_messenger",
            "taskId": task_id,
            "sharedTaskId": task.get("sharedTaskId"),
            "sourceKind": task.get("sourceKind"),
            "otherTribeId": other_id,
            "outcome": outcome
        }
        for target_id in affected or {tribe_id}:
            target_tribe = self.tribes.get(target_id)
            if target_tribe:
                self._add_tribe_history(target_tribe, "trade", "盟约信使", detail, player_id, related)
                await self._notify_tribe(target_id, detail)
        await self._publish_world_rumor(
            "trade",
            "盟约信使",
            f"{tribe.get('name', '部落')} 与 {task.get('otherTribeName', '邻近部落')} 的{task.get('sourceLabel', '盟约信物')}被公开送达。",
            {"tribeId": tribe_id, "otherTribeId": other_id, "taskId": task_id, "outcome": outcome.get("key")}
        )
        for target_id in affected or {tribe_id}:
            await self.broadcast_tribe_state(target_id)
