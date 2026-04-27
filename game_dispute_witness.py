from datetime import datetime
import random

from game_config import *


class GameDisputeWitnessMixin:
    def _active_dispute_witness_stones(self, tribe: dict) -> list:
        now = datetime.now()
        active = []
        for stone in tribe.get("dispute_witness_stones", []) or []:
            if not isinstance(stone, dict) or stone.get("status", "active") != "active":
                continue
            try:
                if datetime.fromisoformat(stone.get("activeUntil", "")) <= now:
                    stone["status"] = "expired"
                    stone["expiredAt"] = now.isoformat()
                    continue
            except (TypeError, ValueError):
                stone["status"] = "expired"
                stone["expiredAt"] = now.isoformat()
                continue
            active.append(stone)
        tribe["dispute_witness_stones"] = active[-TRIBE_DISPUTE_WITNESS_STONE_LIMIT:]
        return tribe["dispute_witness_stones"]

    def _dispute_witness_source_id(self, source_kind: str, record: dict) -> str:
        return f"{source_kind}:{record.get('id') or record.get('sourceId') or record.get('caseId')}"

    def _dispute_witness_source_records(self, tribe: dict) -> list:
        sources = []
        for record in (tribe.get("common_judge_records", []) or [])[-TRIBE_COMMON_JUDGE_RECORD_LIMIT:]:
            if isinstance(record, dict):
                sources.append({
                    "kind": "common_judge",
                    "record": record,
                    "label": record.get("title", "共同裁判"),
                    "sourceLabel": record.get("sourceLabel", "裁判证词"),
                    "summary": f"{record.get('judgeTribeName', '中立部落')}留下{record.get('actionLabel', '见证')}，这份裁判可以刻成公开证据。",
                    "otherTribeId": record.get("otherTribeId") or record.get("sourceTribeId") or "",
                    "otherTribeName": record.get("otherTribeName") or record.get("sourceTribeName") or ""
                })
        for record in (tribe.get("old_grudge_records", []) or [])[-TRIBE_OLD_GRUDGE_RECENT_LIMIT:]:
            if isinstance(record, dict):
                sources.append({
                    "kind": "old_grudge",
                    "record": record,
                    "label": record.get("anchorLabel", "旧怨封存"),
                    "sourceLabel": record.get("sourceLabel", "旧怨记录"),
                    "summary": f"与{record.get('otherTribeName', '邻近部落')}的旧怨已被压成记录，可以立石提醒后来者先看证据。",
                    "otherTribeId": record.get("otherTribeId", ""),
                    "otherTribeName": record.get("otherTribeName", "")
                })
        for record in (tribe.get("border_theater_records", []) or [])[-TRIBE_BORDER_THEATER_RECORD_LIMIT:]:
            if isinstance(record, dict):
                sources.append({
                    "kind": "border_theater",
                    "record": record,
                    "label": record.get("label", "边境戏台"),
                    "sourceLabel": record.get("sourceLabel", "边境会场"),
                    "summary": f"{record.get('winnerName', '成员')}在边境戏台胜出，这段公开结果可以刻成见证石。",
                    "otherTribeId": "",
                    "otherTribeName": ""
                })
        return sources[-TRIBE_DISPUTE_WITNESS_RECORD_LIMIT:]

    def _ensure_dispute_witness_stones(self, tribe: dict):
        if not tribe:
            return
        active = self._active_dispute_witness_stones(tribe)
        existing = {stone.get("sourceId") for stone in active if isinstance(stone, dict)}
        completed = {
            record.get("sourceId")
            for record in (tribe.get("dispute_witness_records", []) or [])
            if isinstance(record, dict) and record.get("sourceId")
        }
        now = datetime.now()
        for source in self._dispute_witness_source_records(tribe):
            record = source.get("record", {})
            source_id = self._dispute_witness_source_id(source.get("kind", "record"), record)
            if not source_id or source_id in existing or source_id in completed:
                continue
            stone = {
                "id": f"dispute_witness_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
                "sourceId": source_id,
                "sourceKind": source.get("kind"),
                "status": "active",
                "label": f"{source.get('label', '争端')}见证石",
                "sourceLabel": source.get("sourceLabel", "公开证据"),
                "summary": source.get("summary", ""),
                "otherTribeId": source.get("otherTribeId", ""),
                "otherTribeName": source.get("otherTribeName", ""),
                "progress": 0,
                "target": TRIBE_DISPUTE_WITNESS_STONE_TARGET,
                "participants": [],
                "x": float(record.get("x", tribe.get("center", {}).get("x", 0)) or 0),
                "z": float(record.get("z", tribe.get("center", {}).get("z", 0)) or 0),
                "createdAt": now.isoformat(),
                "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_DISPUTE_WITNESS_STONE_ACTIVE_MINUTES * 60).isoformat()
            }
            active.append(stone)
            existing.add(source_id)
        tribe["dispute_witness_stones"] = active[-TRIBE_DISPUTE_WITNESS_STONE_LIMIT:]

    def _public_dispute_witness_stones(self, tribe: dict) -> list:
        self._ensure_dispute_witness_stones(tribe)
        return [dict(stone) for stone in self._active_dispute_witness_stones(tribe)]

    def _public_dispute_witness_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("dispute_witness_records", []) or [])
            if isinstance(record, dict)
        ][-TRIBE_DISPUTE_WITNESS_RECORD_LIMIT:]

    def _dispute_witness_evidence_id(self, record: dict) -> str:
        return record.get("evidenceTag") or record.get("sourceId") or record.get("id", "")

    def _dispute_witness_enriched_record(self, record: dict) -> dict:
        evidence_id = self._dispute_witness_evidence_id(record)
        lineage = [
            item for item in (record.get("lineage", []) or [])
            if isinstance(item, dict)
        ][-TRIBE_DISPUTE_WITNESS_LINEAGE_LIMIT:]
        source_chain = [record.get("sourceLabel", "公开证据")]
        source_chain.extend(item.get("label", "引用") for item in lineage if item.get("label"))
        reference_count = int(record.get("referenceCount", len(lineage)) or 0)
        public_record = dict(record)
        public_record.update({
            "evidenceId": evidence_id,
            "referenceCount": reference_count,
            "lineage": lineage,
            "sourceChain": source_chain[-(TRIBE_DISPUTE_WITNESS_LINEAGE_LIMIT + 1):],
            "lineageLabel": record.get("lineageLabel") or (
                "证据谱系" if reference_count >= TRIBE_DISPUTE_WITNESS_LINEAGE_THRESHOLD else ""
            )
        })
        return public_record

    def _public_dispute_witness_evidence(self, tribe: dict) -> list:
        return [
            self._dispute_witness_enriched_record(record)
            for record in self._public_dispute_witness_records(tribe)
        ]

    def _public_dispute_witness_lineages(self, tribe: dict) -> list:
        return [
            record for record in self._public_dispute_witness_evidence(tribe)
            if int(record.get("referenceCount", 0) or 0) >= TRIBE_DISPUTE_WITNESS_LINEAGE_THRESHOLD
        ][-TRIBE_DISPUTE_WITNESS_LINEAGE_LIMIT:]

    def _find_dispute_witness_record(self, tribe: dict, evidence_id: str) -> dict | None:
        if not tribe or not evidence_id:
            return None
        for record in reversed(tribe.get("dispute_witness_records", []) or []):
            if not isinstance(record, dict):
                continue
            candidates = {
                record.get("id"),
                record.get("sourceId"),
                record.get("evidenceTag"),
                self._dispute_witness_evidence_id(record)
            }
            if evidence_id in candidates:
                return record
        return None

    def _record_dispute_witness_reference(self, tribe: dict, evidence_id: str, kind: str, label: str, other_tribe_id: str = "") -> tuple[int, list]:
        record = self._find_dispute_witness_record(tribe, evidence_id)
        if not record:
            return 0, []
        now = datetime.now()
        lineage = [
            item for item in (record.get("lineage", []) or [])
            if isinstance(item, dict)
        ]
        lineage.append({
            "kind": kind,
            "label": label,
            "createdAt": now.isoformat()
        })
        record["lineage"] = lineage[-TRIBE_DISPUTE_WITNESS_LINEAGE_LIMIT:]
        record["referenceCount"] = int(record.get("referenceCount", 0) or 0) + 1
        if record["referenceCount"] >= TRIBE_DISPUTE_WITNESS_LINEAGE_THRESHOLD:
            record["lineageLabel"] = "证据谱系"
        bonus_parts = []
        related_id = other_tribe_id or record.get("otherTribeId", "")
        if record["referenceCount"] >= TRIBE_DISPUTE_WITNESS_LINEAGE_THRESHOLD and related_id:
            other = self.tribes.get(related_id) if hasattr(self, "tribes") else None
            if other:
                for own, target in ((tribe, other), (other, tribe)):
                    relation = own.setdefault("boundary_relations", {}).setdefault(target.get("id"), {})
                    relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + 1))
                    relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + 1))
                    relation["lastAction"] = "dispute_witness_lineage"
                    relation["lastActionAt"] = now.isoformat()
                bonus_parts.extend(["证据谱系关系+1", "证据谱系信任+1"])
        return record["referenceCount"], bonus_parts

    def _dispute_witness_rumor_truth_source(self, tribe: dict) -> dict | None:
        evidence = self._public_dispute_witness_evidence(tribe)
        if not evidence:
            return None
        record = evidence[-1]
        chain_text = " -> ".join(record.get("sourceChain", [])[-3:])
        return {
            "sourceId": record.get("evidenceId"),
            "sourceKind": "dispute_witness",
            "sourceLabel": record.get("lineageLabel") or record.get("sourceLabel", "公开证据"),
            "title": f"{record.get('label', '见证石')}待辨",
            "summary": f"{record.get('sourceLabel', '公开证据')}已经被刻成见证石。{('来源链：' + chain_text) if chain_text else '后续传闻可以围绕它核对来源。'}"
        }

    def _dispute_witness_common_judge_cases(self, judge_tribe_id: str, recent_source_ids: set) -> list:
        cases = []
        for source_id, tribe in (getattr(self, "tribes", {}) or {}).items():
            if source_id == judge_tribe_id:
                continue
            for record in self._public_dispute_witness_evidence(tribe)[-2:]:
                evidence_id = record.get("evidenceId")
                if not evidence_id or evidence_id in recent_source_ids:
                    continue
                other_id = record.get("otherTribeId", "")
                if other_id == judge_tribe_id:
                    continue
                chain_text = " -> ".join(record.get("sourceChain", [])[-3:])
                cases.append({
                    "id": self._common_judge_case_id("dispute_witness", evidence_id, source_id, other_id) if hasattr(self, "_common_judge_case_id") else f"common_judge_dispute_witness_{source_id}_{evidence_id}",
                    "kind": "dispute_witness",
                    "sourceCaseId": evidence_id,
                    "sourceTribeId": source_id,
                    "sourceTribeName": tribe.get("name", "邻近部落"),
                    "otherTribeId": other_id,
                    "otherTribeName": record.get("otherTribeName", ""),
                    "title": record.get("lineageLabel") or record.get("label", "见证石证据"),
                    "summary": f"{record.get('sourceLabel', '公开证据')}已经留下见证石，第三方裁判可以继续引用来源链。{('来源链：' + chain_text) if chain_text else ''}",
                    "sourceLabel": record.get("sourceLabel", "见证石"),
                    "stakes": [f"引用 {record.get('referenceCount', 0)} 次", record.get("lineageLabel") or "未成谱系"]
                })
        return cases

    def _can_pay_dispute_witness_action(self, tribe: dict, action: dict) -> str:
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        if int(storage.get("wood", 0) or 0) < int(action.get("woodCost", 0) or 0):
            return f"{action.get('label', '见证石行动')}需要公共木材{action.get('woodCost')}"
        if int(tribe.get("food", 0) or 0) < int(action.get("foodCost", 0) or 0):
            return f"{action.get('label', '见证石行动')}需要公共食物{action.get('foodCost')}"
        return ""

    def _apply_dispute_witness_reward(self, tribe: dict, action: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(action.get("woodCost", 0) or 0)
        if wood_cost:
            storage["wood"] = max(0, int(storage.get("wood", 0) or 0) - wood_cost)
            parts.append(f"木材-{wood_cost}")
        food_cost = int(action.get("foodCost", 0) or 0)
        if food_cost:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) - food_cost)
            parts.append(f"食物-{food_cost}")
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            amount = int((action.get("reward", {}) or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = max(0, int(tribe.get(tribe_key, 0) or 0) + amount)
                parts.append(f"{label}+{amount}")
        return parts

    def _apply_dispute_witness_relation(self, tribe: dict, stone: dict, action: dict) -> list:
        other_id = stone.get("otherTribeId")
        other = self.tribes.get(other_id) if other_id and hasattr(self, "tribes") else None
        if not other:
            return []
        for own, target in ((tribe, other), (other, tribe)):
            relation = own.setdefault("boundary_relations", {}).setdefault(target.get("id"), {})
            relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + int(action.get("relationDelta", 0) or 0)))
            relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + int(action.get("tradeTrustDelta", 0) or 0)))
            relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - int(action.get("warPressureRelief", 0) or 0))
            relation["temperatureTone"] = action.get("tone", relation.get("temperatureTone", ""))
            relation["lastAction"] = "dispute_witness_stone"
            relation["lastActionAt"] = datetime.now().isoformat()
        parts = []
        if int(action.get("relationDelta", 0) or 0):
            parts.append(f"双方关系+{int(action.get('relationDelta', 0) or 0)}")
        if int(action.get("tradeTrustDelta", 0) or 0):
            parts.append(f"双方信任+{int(action.get('tradeTrustDelta', 0) or 0)}")
        if int(action.get("warPressureRelief", 0) or 0):
            parts.append(f"战争压力-{int(action.get('warPressureRelief', 0) or 0)}")
        return parts

    async def tend_dispute_witness_stone(self, player_id: str, stone_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        stone = next((item for item in self._active_dispute_witness_stones(tribe) if item.get("id") == stone_id), None)
        if not stone:
            await self._send_tribe_error(player_id, "这块见证石已经沉寂")
            return
        if any(item.get("memberId") == player_id for item in stone.get("participants", []) or []):
            await self._send_tribe_error(player_id, "你已经维护过这块见证石")
            return
        action = TRIBE_DISPUTE_WITNESS_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知见证石行动")
            return
        pay_error = self._can_pay_dispute_witness_action(tribe, action)
        if pay_error:
            await self._send_tribe_error(player_id, pay_error)
            return

        member_name = (tribe.get("members", {}).get(player_id, {}) or {}).get("name", "成员")
        reward_parts = self._apply_dispute_witness_reward(tribe, action)
        relation_parts = self._apply_dispute_witness_relation(tribe, stone, action)
        participant = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "维护"),
            "rewardParts": reward_parts + relation_parts,
            "createdAt": datetime.now().isoformat()
        }
        stone.setdefault("participants", []).append(participant)
        stone["progress"] = int(stone.get("progress", 0) or 0) + 1
        completed = stone["progress"] >= int(stone.get("target", TRIBE_DISPUTE_WITNESS_STONE_TARGET) or 1)
        detail = f"{member_name}在{stone.get('label', '争端见证石')}上{action.get('label', '维护证据')}，进度 {stone['progress']} / {stone.get('target', 1)}。"
        if reward_parts or relation_parts:
            detail += f" {'、'.join(reward_parts + relation_parts)}。"
        if completed:
            stone["status"] = "completed"
            stone["completedAt"] = datetime.now().isoformat()
            record = {
                "id": f"dispute_witness_record_{tribe_id}_{int(datetime.now().timestamp() * 1000)}",
                "sourceId": stone.get("sourceId"),
                "sourceKind": stone.get("sourceKind"),
                "label": stone.get("label", "争端见证石"),
                "sourceLabel": stone.get("sourceLabel", "公开证据"),
                "otherTribeId": stone.get("otherTribeId", ""),
                "otherTribeName": stone.get("otherTribeName", ""),
                "participantNames": [item.get("memberName", "成员") for item in stone.get("participants", [])],
                "rewardParts": reward_parts + relation_parts,
                "evidenceTag": f"public_evidence:{stone.get('sourceId')}",
                "referenceCount": 0,
                "lineage": [],
                "createdAt": stone["completedAt"]
            }
            tribe.setdefault("dispute_witness_records", []).append(record)
            tribe["dispute_witness_records"] = tribe["dispute_witness_records"][-TRIBE_DISPUTE_WITNESS_RECORD_LIMIT:]
            detail += " 这块见证石已经成为后续传闻和旧怨可引用的公开证据。"
        self._add_tribe_history(tribe, "diplomacy", "争端见证石", detail, player_id, {"kind": "dispute_witness_stone", "stone": stone, "actionKey": action_key})
        await self._publish_world_rumor(
            "diplomacy",
            "争端见证石",
            f"{tribe.get('name', '部落')}把{stone.get('sourceLabel', '争端记录')}刻成见证石，后来者可以围着它复述证据。",
            {"tribeId": tribe_id, "stoneId": stone_id, "sourceKind": stone.get("sourceKind")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
