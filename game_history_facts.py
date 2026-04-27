from datetime import datetime
import random

from game_config import *


class GameHistoryFactMixin:
    def _active_history_fact_records(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for claim in tribe.get("history_fact_claims", []) or []:
            if not isinstance(claim, dict) or claim.get("status") != "open":
                continue
            active_until = claim.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    pass
            active.append(claim)
        if len(active) != len(tribe.get("history_fact_claims", []) or []):
            tribe["history_fact_claims"] = active[-TRIBE_HISTORY_FACT_LIMIT:]
        return active[-TRIBE_HISTORY_FACT_LIMIT:]

    def _history_fact_records(self, claim: dict) -> list:
        dedupe_id = claim.get("dedupeId")
        if not dedupe_id:
            return []
        records = []
        for tribe in self.tribes.values():
            for item in self._active_history_fact_records(tribe):
                if item.get("dedupeId") == dedupe_id:
                    records.append((tribe, item))
        return records

    def _history_fact_versions(self, claim: dict) -> list:
        participant_ids = [item.get("id") for item in claim.get("participantTribes", []) or [] if isinstance(item, dict)]
        versions = claim.get("versions", {}) or {}
        result = []
        for participant in claim.get("participantTribes", []) or []:
            if not isinstance(participant, dict):
                continue
            key = f"tribe:{participant.get('id')}"
            version = versions.get(key, {}) or {}
            result.append({
                "key": key,
                "tribeId": participant.get("id"),
                "label": f"{participant.get('name', '部落')}叙事",
                "summary": participant.get("claimSummary") or "把这段冲突写成自己部落的正当版本。",
                "influence": int(version.get("influence", 0) or 0),
                "supporterNames": [item.get("name", "成员") for item in (version.get("supporters", []) or [])[-3:] if isinstance(item, dict)]
            })
        neutral = versions.get("neutral", {}) or {}
        result.append({
            "key": "neutral",
            "tribeId": "",
            "label": "中立编年",
            "summary": "把双方说法压成一份可被背书的中立记录，减少后续外交猜疑。",
            "influence": int(neutral.get("influence", 0) or 0),
            "supporterNames": [item.get("name", "成员") for item in (neutral.get("supporters", []) or [])[-3:] if isinstance(item, dict)]
        })
        if claim.get("shared"):
            records = self._history_fact_records(claim)
            for version in result:
                version["influence"] = sum(
                    int(((record.get("versions", {}) or {}).get(version["key"], {}) or {}).get("influence", 0) or 0)
                    for _, record in records
                )
                own_version = (versions.get(version["key"], {}) or {})
                version["ownInfluence"] = int(own_version.get("influence", 0) or 0)
                version["outsideInfluence"] = max(0, version["influence"] - version["ownInfluence"])
        version_map = {item.get("id"): item for item in claim.get("participantTribes", []) or []}
        for version in result:
            version["participant"] = version.get("tribeId") in participant_ids
            if version.get("tribeId") and version.get("tribeId") in version_map:
                version["participantName"] = version_map[version["tribeId"]].get("name", "部落")
        return result

    def _public_history_fact_claim(self, tribe: dict, claim: dict) -> dict:
        versions = self._history_fact_versions(claim)
        leader = max(versions, key=lambda item: item.get("influence", 0), default=None)
        tribe_id = tribe.get("id") if tribe else ""
        participant_ids = [item.get("id") for item in claim.get("participantTribes", []) or [] if isinstance(item, dict)]
        return {
            "id": claim.get("id"),
            "title": claim.get("title", "历史事实争夺"),
            "summary": claim.get("summary", ""),
            "sourceKind": claim.get("sourceKind", ""),
            "sourceLabel": claim.get("sourceLabel", ""),
            "participantTribes": list(claim.get("participantTribes", []) or []),
            "versions": versions,
            "influenceTarget": int(claim.get("influenceTarget", TRIBE_HISTORY_FACT_INFLUENCE_TARGET) or TRIBE_HISTORY_FACT_INFLUENCE_TARGET),
            "leaderLabel": leader.get("label") if leader and leader.get("influence", 0) > 0 else "",
            "leaderInfluence": leader.get("influence", 0) if leader else 0,
            "isParticipant": tribe_id in participant_ids,
            "canMediate": tribe_id not in participant_ids,
            "createdAt": claim.get("createdAt"),
            "activeUntil": claim.get("activeUntil")
        }

    def _public_history_fact_claims(self, tribe: dict) -> list:
        return [self._public_history_fact_claim(tribe, claim) for claim in self._active_history_fact_records(tribe)]

    def _accepted_history_facts(self, tribe: dict) -> list:
        return list(tribe.get("accepted_history_facts", []) or [])[-TRIBE_ACCEPTED_HISTORY_FACT_LIMIT:]

    def _open_history_fact_claim(self, participants: list, source_kind: str, source_label: str, summary: str, source_id: str = "") -> list:
        participant_tribes = []
        seen = set()
        for tribe in participants or []:
            if not isinstance(tribe, dict) or not tribe.get("id") or tribe.get("id") in seen:
                continue
            seen.add(tribe.get("id"))
            participant_tribes.append({
                "id": tribe.get("id"),
                "name": tribe.get("name", "部落"),
                "claimSummary": f"{tribe.get('name', '部落')} 可以把这件事写成自己的见证。"
            })
        if len(participant_tribes) < 2:
            return []
        dedupe_id = f"{source_kind}:{source_id or source_label}"
        now = datetime.now()
        all_targets = []
        for tribe in self.tribes.values():
            if isinstance(tribe, dict) and tribe.get("id"):
                all_targets.append(tribe)
        opened = []
        for tribe in all_targets:
            active = self._active_history_fact_records(tribe)
            existing = next((item for item in active if item.get("dedupeId") == dedupe_id), None)
            if existing:
                opened.append(self._public_history_fact_claim(tribe, existing))
                continue
            claim = {
                "id": f"history_fact_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
                "status": "open",
                "shared": True,
                "dedupeId": dedupe_id,
                "sourceKind": source_kind,
                "sourceLabel": source_label or "冲突旧事",
                "title": f"{source_label or '冲突旧事'}的事实版本",
                "summary": summary or "双方都可以提交叙述，中立部落也可以背书调停版本。",
                "participantTribes": participant_tribes,
                "versions": {},
                "influenceTarget": TRIBE_HISTORY_FACT_INFLUENCE_TARGET,
                "createdAt": now.isoformat(),
                "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_HISTORY_FACT_ACTIVE_MINUTES * 60).isoformat()
            }
            tribe["history_fact_claims"] = [*active, claim][-TRIBE_HISTORY_FACT_LIMIT:]
            opened.append(self._public_history_fact_claim(tribe, claim))
        return opened

    def _open_war_history_fact_claim(self, war: dict, winner: dict, loser: dict, source_kind: str = "formal_war"):
        if not war or not winner or not loser:
            return []
        goal = war.get("goal") or {}
        label = f"{goal.get('label') or war.get('targetLabel') or '正式战争'}"
        summary = f"{winner.get('name', '胜方')}与{loser.get('name', '败方')}都在争夺这场{label}该如何进入编年史。"
        return self._open_history_fact_claim(
            [winner, loser],
            source_kind,
            label,
            summary,
            war.get("id", "")
        )

    def _open_betrayal_history_fact_claim(self, record: dict):
        if not record:
            return []
        supporter = self.tribes.get(record.get("supporterTribeId"))
        old_side = self.tribes.get(record.get("sideTribeId"))
        if not supporter or not old_side:
            return []
        label = "战争背刺"
        summary = f"{supporter.get('name', '背刺者')}与{old_side.get('name', '旧盟友')}正在争夺这次转向到底是背弃、求存还是误会。"
        return self._open_history_fact_claim(
            [supporter, old_side],
            "war_betrayal",
            label,
            summary,
            record.get("id", "")
        )

    def _apply_history_fact_relation(self, participant_ids: list, accepted_key: str, final_tribe_id: str, now_text: str) -> list:
        if len(participant_ids) < 2:
            return []
        parts = []
        participant_set = set(participant_ids)
        accepted_tribe_id = accepted_key.split(":", 1)[1] if accepted_key.startswith("tribe:") else ""
        for source_id in participant_ids:
            source = self.tribes.get(source_id)
            if not source:
                continue
            for target_id in participant_set - {source_id}:
                relation = source.setdefault("boundary_relations", {}).setdefault(target_id, {})
                if accepted_key == "neutral":
                    relation["score"] = min(9, int(relation.get("score", 0) or 0) + 1)
                    relation["tradeTrust"] = min(10, int(relation.get("tradeTrust", 0) or 0) + 1)
                    relation["lastAction"] = "history_fact_neutral"
                elif accepted_tribe_id == source_id:
                    relation["score"] = max(-9, int(relation.get("score", 0) or 0) - 1)
                    relation["lastAction"] = "history_fact_claimed"
                else:
                    relation["tradeTrust"] = max(0, int(relation.get("tradeTrust", 0) or 0) - 1)
                    relation["lastAction"] = "history_fact_overruled"
                relation["lastActionAt"] = now_text
        if accepted_key == "neutral":
            parts.append("双方关系+1、贸易信任+1")
        elif accepted_tribe_id:
            accepted = self.tribes.get(accepted_tribe_id)
            if accepted:
                accepted["renown"] = int(accepted.get("renown", 0) or 0) + TRIBE_HISTORY_FACT_RENOWN
                parts.append(f"{accepted.get('name', '定稿方')}声望+{TRIBE_HISTORY_FACT_RENOWN}")
        final_tribe = self.tribes.get(final_tribe_id)
        if final_tribe and final_tribe_id not in participant_set:
            final_tribe["renown"] = int(final_tribe.get("renown", 0) or 0) + TRIBE_HISTORY_FACT_MEDIATOR_RENOWN
            final_tribe["trade_reputation"] = int(final_tribe.get("trade_reputation", 0) or 0) + TRIBE_HISTORY_FACT_MEDIATOR_TRADE
            parts.append(f"{final_tribe.get('name', '调停方')}调停声望+{TRIBE_HISTORY_FACT_MEDIATOR_RENOWN}、贸易信誉+{TRIBE_HISTORY_FACT_MEDIATOR_TRADE}")
        return parts

    async def support_history_fact_claim(self, player_id: str, claim_id: str, version_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        claim = next((item for item in self._active_history_fact_records(tribe) if item.get("id") == claim_id), None)
        if not claim:
            await self._send_tribe_error(player_id, "这次历史事实争夺已经结束")
            return
        valid_keys = {item.get("key") for item in self._history_fact_versions(claim)}
        if version_key not in valid_keys:
            await self._send_tribe_error(player_id, "未知的历史版本")
            return
        versions = claim.setdefault("versions", {})
        if any(
            player_id in [supporter.get("id") for supporter in (version.get("supporters", []) or []) if isinstance(supporter, dict)]
            for version in versions.values() if isinstance(version, dict)
        ):
            await self._send_tribe_error(player_id, "你已经参与过这次事实争夺")
            return
        participant_ids = [item.get("id") for item in claim.get("participantTribes", []) or [] if isinstance(item, dict)]
        member = tribe.get("members", {}).get(player_id, {})
        influence_gain = TRIBE_HISTORY_FACT_NEUTRAL_INFLUENCE if tribe_id not in participant_ids else 1
        version = versions.setdefault(version_key, {"supporters": [], "influence": 0})
        version.setdefault("supporters", []).append({
            "id": player_id,
            "name": member.get("name", "成员"),
            "tribeId": tribe_id,
            "tribeName": tribe.get("name", "部落"),
            "at": datetime.now().isoformat(),
            "influence": influence_gain
        })
        version["influence"] = int(version.get("influence", 0) or 0) + influence_gain
        records = self._history_fact_records(claim)
        total_influence = sum(
            int(((record.get("versions", {}) or {}).get(version_key, {}) or {}).get("influence", 0) or 0)
            for _, record in records
        )
        target = int(claim.get("influenceTarget", TRIBE_HISTORY_FACT_INFLUENCE_TARGET) or TRIBE_HISTORY_FACT_INFLUENCE_TARGET)
        if total_influence >= target:
            await self._complete_history_fact_claim(tribe_id, tribe, claim, version_key, player_id)
            return
        version_label = next((item.get("label") for item in self._history_fact_versions(claim) if item.get("key") == version_key), "事实版本")
        action_label = "调停背书" if tribe_id not in participant_ids else "提交叙述"
        detail = f"{member.get('name', '成员')} 为“{claim.get('sourceLabel', '旧事')}”{action_label}：{version_label}，影响 {total_influence} / {target}。"
        self._add_tribe_history(tribe, "governance", "历史事实升温", detail, player_id, {"kind": "history_fact_claim", "claimId": claim_id, "versionKey": version_key})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def _complete_history_fact_claim(self, tribe_id: str, tribe: dict, claim: dict, version_key: str, player_id: str):
        records = self._history_fact_records(claim)
        if not records:
            return
        versions = self._history_fact_versions(claim)
        accepted_version = next((item for item in versions if item.get("key") == version_key), {})
        participant_ids = [item.get("id") for item in claim.get("participantTribes", []) or [] if isinstance(item, dict)]
        now_text = datetime.now().isoformat()
        relation_parts = self._apply_history_fact_relation(participant_ids, version_key, tribe_id, now_text)
        member = tribe.get("members", {}).get(player_id, {})
        detail = f"“{claim.get('sourceLabel', '旧事')}”被写成“{accepted_version.get('label', '中立编年')}”，进入各部落编年史。"
        if relation_parts:
            detail += f" 影响：{'、'.join(relation_parts)}。"
        involved_ids = set()
        for target_tribe, target_claim in records:
            involved_ids.add(target_tribe.get("id"))
            chronicle = {
                "id": f"accepted_{target_claim.get('id')}",
                "sourceKind": target_claim.get("sourceKind"),
                "sourceLabel": target_claim.get("sourceLabel"),
                "versionKey": version_key,
                "versionLabel": accepted_version.get("label", "中立编年"),
                "summary": accepted_version.get("summary", ""),
                "completedBy": member.get("name", "成员"),
                "completedByTribeName": tribe.get("name", "部落"),
                "completedAt": now_text,
                "relationParts": relation_parts
            }
            target_tribe["accepted_history_facts"] = [*(target_tribe.get("accepted_history_facts", []) or []), chronicle][-TRIBE_ACCEPTED_HISTORY_FACT_LIMIT:]
            target_tribe["history_fact_claims"] = [
                item for item in self._active_history_fact_records(target_tribe)
                if item.get("dedupeId") != claim.get("dedupeId")
            ]
            self._add_tribe_history(
                target_tribe,
                "governance",
                "历史事实定稿",
                detail,
                player_id,
                {"kind": "history_fact_claim", "claimId": target_claim.get("id"), "versionKey": version_key}
            )
            await self._notify_tribe(target_tribe.get("id"), detail)
        await self._publish_world_rumor(
            "history_fact",
            "历史事实定稿",
            detail,
            {"tribeId": tribe_id, "claimId": claim.get("id"), "versionKey": version_key}
        )
        for target_id in involved_ids:
            await self.broadcast_tribe_state(target_id)
