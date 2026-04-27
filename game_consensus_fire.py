from datetime import datetime

from game_config import TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD


CONSENSUS_FIRE_ACTIVE_MINUTES = 28
CONSENSUS_FIRE_RECORD_LIMIT = 6
CONSENSUS_FIRE_SOURCE_LIMIT = 6
CONSENSUS_FIRE_ACTIONS = {
    "guard": {
        "label": "守印",
        "summary": "把共识守在营火旁，下一次律令或营地议事更容易被认为可信。",
        "bonusTarget": "law",
        "bonusLabel": "律令可信",
        "reward": {"renown": 1},
        "animation": "guard"
    },
    "pass": {
        "label": "传印",
        "summary": "把共识传给边市、信使和戏台，后续外交叙事更容易得到善意回应。",
        "bonusTarget": "diplomacy",
        "bonusLabel": "外交传印",
        "reward": {"tradeReputation": 1},
        "animation": "cheer"
    },
    "extinguish": {
        "label": "熄印",
        "summary": "把争执留在灰里，不再扩散成新传闻，立刻压低边界紧绷。",
        "bonusTarget": "rumor",
        "bonusLabel": "传闻降温",
        "reward": {"discoveryProgress": 1},
        "pressureRelief": 1,
        "animation": "ritual"
    }
}


class GameConsensusFireMixin:
    def _active_consensus_fire(self, tribe: dict) -> dict | None:
        seal = tribe.get("consensus_fire")
        if not isinstance(seal, dict) or seal.get("status") != "active":
            return None
        try:
            if datetime.fromisoformat(seal.get("activeUntil", "")) <= datetime.now():
                seal["status"] = "expired"
                seal["expiredAt"] = datetime.now().isoformat()
                return None
        except (TypeError, ValueError):
            seal["status"] = "expired"
            seal["expiredAt"] = datetime.now().isoformat()
            return None
        return seal

    def _consensus_fire_source_candidates(self, tribe: dict) -> list:
        used = set(tribe.get("consensus_fire_used_sources", []) or [])
        sources = []
        for record in tribe.get("camp_council_records", []) or []:
            if not isinstance(record, dict):
                continue
            source_id = f"camp_council:{record.get('id')}"
            if source_id in used:
                continue
            sources.append({
                "sourceId": source_id,
                "sourceKind": "camp_council",
                "sourceLabel": "营地议事圈",
                "label": record.get("resultLabel") or record.get("label") or "火边共识",
                "summary": record.get("summary", "营地议事留下了可继续守护的共识。"),
                "createdAt": record.get("createdAt", "")
            })
        for record in tribe.get("ancestor_question_records", []) or []:
            if not isinstance(record, dict):
                continue
            source_id = f"ancestor_question:{record.get('id')}"
            if source_id in used:
                continue
            label = record.get("dominantAnswerLabel") or record.get("eventBiasLabel") or record.get("label")
            sources.append({
                "sourceId": source_id,
                "sourceKind": "ancestor_question",
                "sourceLabel": "祖灵问答",
                "label": label or "祖灵回声",
                "summary": record.get("summary", "祖灵问答留下了可传递的营火回答。"),
                "createdAt": record.get("createdAt", "")
            })
        for record in tribe.get("old_grudge_records", []) or []:
            if not isinstance(record, dict):
                continue
            source_id = f"old_grudge:{record.get('id') or record.get('sourceId')}"
            if source_id in used:
                continue
            sources.append({
                "sourceId": source_id,
                "sourceKind": "old_grudge",
                "sourceLabel": "旧怨封存",
                "label": record.get("sourceLabel") or record.get("anchorLabel") or "旧怨封印",
                "summary": f"与{record.get('otherTribeName', '邻近部落')}的旧怨暂时压进了公开证据里。",
                "createdAt": record.get("createdAt", "")
            })
        return sorted(sources, key=lambda item: item.get("createdAt") or "", reverse=True)[:CONSENSUS_FIRE_SOURCE_LIMIT]

    def _ensure_consensus_fire(self, tribe: dict) -> dict | None:
        active = self._active_consensus_fire(tribe)
        if active:
            return active
        source = next(iter(self._consensus_fire_source_candidates(tribe)), None)
        if not source:
            return None
        now = datetime.now()
        seal = {
            "id": f"consensus_fire_{tribe.get('id')}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "sourceId": source.get("sourceId"),
            "sourceKind": source.get("sourceKind"),
            "sourceLabel": source.get("sourceLabel"),
            "label": source.get("label", "共识火印"),
            "summary": source.get("summary", ""),
            "participants": [],
            "participantIds": [],
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + CONSENSUS_FIRE_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["consensus_fire"] = seal
        used = list(tribe.get("consensus_fire_used_sources", []) or [])
        used.append(source.get("sourceId"))
        tribe["consensus_fire_used_sources"] = used[-20:]
        return seal

    def _public_consensus_fire(self, tribe: dict) -> dict | None:
        seal = self._ensure_consensus_fire(tribe)
        if not seal:
            return None
        return {
            "id": seal.get("id"),
            "sourceId": seal.get("sourceId"),
            "sourceKind": seal.get("sourceKind"),
            "sourceLabel": seal.get("sourceLabel"),
            "label": seal.get("label"),
            "summary": seal.get("summary"),
            "participants": list(seal.get("participants", []) or [])[-6:],
            "createdAt": seal.get("createdAt"),
            "activeUntil": seal.get("activeUntil")
        }

    def _public_consensus_fire_actions(self) -> dict:
        return CONSENSUS_FIRE_ACTIONS

    def _public_consensus_fire_bonuses(self, tribe: dict) -> list:
        bonuses = []
        for bonus in tribe.get("consensus_fire_bonuses", []) or []:
            if not isinstance(bonus, dict) or int(bonus.get("uses", 0) or 0) <= 0:
                continue
            bonuses.append(bonus)
        tribe["consensus_fire_bonuses"] = bonuses[-CONSENSUS_FIRE_RECORD_LIMIT:]
        return bonuses

    def _public_consensus_fire_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("consensus_fire_records", []) or [])
            if isinstance(record, dict)
        ][-CONSENSUS_FIRE_RECORD_LIMIT:]

    def _apply_consensus_fire_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("food", "食物", "food")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        return parts

    def _relieve_consensus_fire_pressure(self, tribe: dict, amount: int) -> int:
        if amount <= 0:
            return 0
        relieved = 0
        for relation in (tribe.get("boundary_relations", {}) or {}).values():
            if not isinstance(relation, dict):
                continue
            before = int(relation.get("warPressure", 0) or 0)
            after = max(0, before - amount)
            relation["warPressure"] = after
            relation["canDeclareWar"] = after >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relieved += before - after
        return relieved

    async def resolve_consensus_fire(self, player_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = CONSENSUS_FIRE_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知共识火印动作")
            return
        seal = self._active_consensus_fire(tribe) or self._ensure_consensus_fire(tribe)
        if not seal:
            await self._send_tribe_error(player_id, "暂时没有可处理的共识火印")
            return
        if player_id in (seal.get("participantIds", []) or []):
            await self._send_tribe_error(player_id, "你已经处理过这枚共识火印")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", self._get_player_name(player_id) if hasattr(self, "_get_player_name") else "成员")
        reward_parts = self._apply_consensus_fire_reward(tribe, action.get("reward", {}))
        relieved = self._relieve_consensus_fire_pressure(tribe, int(action.get("pressureRelief", 0) or 0))
        if relieved:
            reward_parts.append(f"战争压力-{relieved}")
        bonus = {
            "id": f"consensus_bonus_{seal.get('id')}_{action_key}",
            "sourceId": seal.get("id"),
            "sourceLabel": seal.get("sourceLabel"),
            "label": action.get("bonusLabel", action.get("label", "共识火印")),
            "target": action.get("bonusTarget"),
            "uses": 1,
            "createdByName": member_name,
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("consensus_fire_bonuses", []).append(bonus)
        tribe["consensus_fire_bonuses"] = tribe["consensus_fire_bonuses"][-CONSENSUS_FIRE_RECORD_LIMIT:]
        participant = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "处理"),
            "createdAt": datetime.now().isoformat()
        }
        seal.setdefault("participantIds", []).append(player_id)
        seal.setdefault("participants", []).append(participant)
        seal["status"] = "resolved"
        seal["resolvedAt"] = datetime.now().isoformat()
        seal["resolvedBy"] = player_id
        seal["actionLabel"] = action.get("label", "处理")
        record = {
            "id": f"consensus_fire_record_{tribe_id}_{int(datetime.now().timestamp() * 1000)}",
            "sourceId": seal.get("sourceId"),
            "sourceLabel": seal.get("sourceLabel"),
            "label": seal.get("label", "共识火印"),
            "summary": seal.get("summary", ""),
            "actionKey": action_key,
            "actionLabel": action.get("label", "处理"),
            "bonusLabel": bonus.get("label"),
            "bonusTarget": bonus.get("target"),
            "memberName": member_name,
            "rewardParts": reward_parts,
            "createdAt": seal["resolvedAt"]
        }
        tribe.setdefault("consensus_fire_records", []).append(record)
        tribe["consensus_fire_records"] = tribe["consensus_fire_records"][-CONSENSUS_FIRE_RECORD_LIMIT:]
        tribe["consensus_fire"] = None
        detail = f"{member_name}把“{record['label']}”处理为{record['actionLabel']}，留下“{record['bonusLabel']}”可供后续行动引用。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "governance", "共识火印", detail, player_id, {"kind": "consensus_fire", "record": record, "bonus": bonus})
        await self._publish_world_rumor(
            "governance",
            "共识火印",
            f"{tribe.get('name', '某个部落')}把{record.get('sourceLabel', '共识')}留下的火印处理为{record['actionLabel']}，后续传闻会记住这道火光。",
            {"tribeId": tribe_id, "recordId": record.get("id"), "bonusTarget": bonus.get("target")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
