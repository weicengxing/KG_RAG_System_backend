import math
import random
from datetime import datetime

from game_config import *


class GameForbiddenEdgeMixin:
    def _forbidden_edge_rng(self):
        return getattr(self, "_weather_rng", random)

    def _active_forbidden_edges(self, tribe: dict) -> list:
        if not tribe:
            return []
        active = []
        now = datetime.now()
        for edge in tribe.get("forbidden_edges", []) or []:
            if not isinstance(edge, dict) or edge.get("status", "active") != "active":
                continue
            active_until = edge.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        edge["status"] = "expired"
                        edge["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    edge["status"] = "expired"
                    edge["expiredAt"] = now.isoformat()
                    continue
            active.append(edge)
        tribe["forbidden_edges"] = active[-TRIBE_FORBIDDEN_EDGE_LIMIT:]
        return tribe["forbidden_edges"]

    def _ensure_forbidden_edge(self, tribe: dict):
        if not tribe:
            return None
        active = self._active_forbidden_edges(tribe)
        if active:
            return active[0]
        camp = tribe.get("camp") or {}
        center = camp.get("center") or {}
        if not center:
            return None
        rng = self._forbidden_edge_rng()
        angle = rng.random() * math.tau
        distance = 48 + rng.random() * 58
        now = datetime.now()
        edge = {
            "id": f"forbidden_edge_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{rng.randint(100, 999)}",
            "type": "forbidden_edge",
            "status": "active",
            "label": "禁地边缘",
            "summary": "一片短时显露的高风险边缘，能带回发现和旧物，但逗留太久只会留下营救线索。",
            "x": max(-490, min(490, float(center.get("x", 0) or 0) + math.cos(angle) * distance)),
            "z": max(-490, min(490, float(center.get("z", 0) or 0) + math.sin(angle) * distance)),
            "y": 0,
            "size": 1.05,
            "radius": TRIBE_FORBIDDEN_EDGE_RADIUS,
            "participants": [],
            "dangerTarget": TRIBE_FORBIDDEN_EDGE_DANGER_TARGET,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_FORBIDDEN_EDGE_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["forbidden_edges"] = [edge][-TRIBE_FORBIDDEN_EDGE_LIMIT:]
        return edge

    def _public_forbidden_edges(self, tribe: dict) -> list:
        self._ensure_forbidden_edge(tribe)
        return [dict(edge) for edge in self._active_forbidden_edges(tribe)]

    def _public_forbidden_edge_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("forbidden_edge_records", []) or [])
            if isinstance(record, dict)
        ][-TRIBE_FORBIDDEN_EDGE_RECORD_LIMIT:]

    def _active_forbidden_edge_route_experiences(self, tribe: dict) -> list:
        active = []
        for experience in tribe.get("forbidden_edge_route_experiences", []) or []:
            if isinstance(experience, dict) and experience.get("status", "active") == "active":
                active.append(experience)
        tribe["forbidden_edge_route_experiences"] = active[-TRIBE_FORBIDDEN_EDGE_ROUTE_EXPERIENCE_LIMIT:]
        return tribe["forbidden_edge_route_experiences"]

    def _public_forbidden_edge_route_experiences(self, tribe: dict) -> list:
        return [
            {
                "id": item.get("id"),
                "label": item.get("label", "禁地回撤经验"),
                "summary": item.get("summary", ""),
                "safetyBonus": int(item.get("safetyBonus", TRIBE_FORBIDDEN_EDGE_ROUTE_EXPERIENCE_SAFETY) or 0),
                "sourceLabels": list(item.get("sourceLabels", []) or []),
                "createdAt": item.get("createdAt")
            }
            for item in self._active_forbidden_edge_route_experiences(tribe)
        ]

    def _consume_forbidden_edge_route_experience(self, tribe: dict, use_key: str = "forbidden_edge") -> dict | None:
        experiences = self._active_forbidden_edge_route_experiences(tribe)
        if not experiences:
            return None
        experience = experiences[0]
        experience["status"] = "used"
        experience["usedFor"] = use_key
        experience["usedAt"] = datetime.now().isoformat()
        tribe["forbidden_edge_route_experiences"] = [
            item for item in experiences[1:]
            if isinstance(item, dict) and item.get("status", "active") == "active"
        ]
        return experience

    def _create_forbidden_edge_route_experience(self, tribe: dict, edge: dict, record: dict, source_labels: list) -> dict:
        now = datetime.now()
        experience = {
            "id": f"forbidden_edge_route_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "label": "禁地回撤经验",
            "summary": f"{record.get('memberName', '成员')}连续安全回撤，把{edge.get('label', '禁地边缘')}的风向、火光和回路记成下一次高风险行动的经验。",
            "edgeId": edge.get("id"),
            "edgeLabel": edge.get("label", "禁地边缘"),
            "safetyBonus": TRIBE_FORBIDDEN_EDGE_ROUTE_EXPERIENCE_SAFETY,
            "sourceLabels": list(source_labels or []),
            "createdAt": now.isoformat()
        }
        experiences = self._active_forbidden_edge_route_experiences(tribe)
        tribe["forbidden_edge_route_experiences"] = [*experiences, experience][-TRIBE_FORBIDDEN_EDGE_ROUTE_EXPERIENCE_LIMIT:]
        return experience

    def _forbidden_edge_route_proof_source_key(self, source_kind: str, source_id: str) -> str:
        return f"{source_kind}:{source_id}"

    def _forbidden_edge_route_proof_source(self, tribe: dict, source_kind: str, source_id: str, label: str, summary: str, source_label: str, extra: dict | None = None) -> dict | None:
        if not source_id:
            return None
        return {
            "sourceKey": self._forbidden_edge_route_proof_source_key(source_kind, source_id),
            "sourceKind": source_kind,
            "sourceId": source_id,
            "label": label or "禁地路证",
            "summary": summary or "这段来源可以公开刻写成禁地路证。",
            "sourceLabel": source_label or "路证来源",
            **(extra or {})
        }

    def _forbidden_edge_route_proof_sources(self, tribe: dict) -> list:
        if not tribe:
            return []
        sources = []

        for experience in reversed(self._active_forbidden_edge_route_experiences(tribe)):
            if not isinstance(experience, dict):
                continue
            if str(experience.get("id", "")).startswith("forbidden_edge_route_proof_exp_"):
                continue
            source = self._forbidden_edge_route_proof_source(
                tribe,
                "forbidden_route_experience",
                experience.get("id", ""),
                experience.get("label", "禁地回撤经验"),
                experience.get("summary", "安全回撤经验可以公开刻写成禁地路证。"),
                "禁地回撤经验",
                {"sourceLabels": experience.get("sourceLabels", []), "safetyBonus": experience.get("safetyBonus", 0)}
            )
            if source:
                sources.append(source)

        for record in reversed(tribe.get("forbidden_edge_records", []) or []):
            if not isinstance(record, dict) or record.get("lost"):
                continue
            source = self._forbidden_edge_route_proof_source(
                tribe,
                "forbidden_edge_record",
                record.get("id", ""),
                record.get("label", "禁地安全回撤"),
                f"{record.get('memberName', '成员')}完成{record.get('actionLabel', '试探')}后安全回撤，可以把掷点、支撑和旧物来源刻成路证。",
                "安全回撤记录",
                {"sourceLabels": record.get("supportLabels", []), "rewardParts": record.get("rewardParts", [])}
            )
            if source:
                sources.append(source)

        for record in reversed(tribe.get("cave_rescue_records", []) or []):
            if not isinstance(record, dict):
                continue
            if record.get("sourceKind") not in {"forbidden_edge", "cave_rescue"} and "禁地" not in str(record.get("label", "")):
                continue
            source = self._forbidden_edge_route_proof_source(
                tribe,
                "forbidden_rescue_record",
                record.get("id", ""),
                record.get("label", "禁地营救归线"),
                record.get("summary") or f"{record.get('memberName', '成员')}把营救线索带回营地，这条归线可以成为禁地路证。",
                "营救完成记录",
                {"sourceLabels": record.get("supportLabels", []), "rewardParts": record.get("rewardParts", [])}
            )
            if source:
                sources.append(source)

        for record in reversed(tribe.get("old_camp_records", []) or []):
            if not isinstance(record, dict) or not record.get("collectionReady"):
                continue
            source = self._forbidden_edge_route_proof_source(
                tribe,
                "old_camp_record",
                record.get("id", ""),
                record.get("label", "旧营旧物"),
                f"{record.get('memberName', '成员')}从{record.get('sourceLabel', '旧营')}带回旧物，可以给禁地回路补上可触摸的旧证。",
                record.get("sourceLabel", "旧营旧物"),
                {"sourceLabels": [record.get("sourceLabel", "旧营旧物")], "rewardParts": record.get("rewardParts", [])}
            )
            if source:
                sources.append(source)

        for item in reversed(tribe.get("collection_wall", []) or []):
            if not isinstance(item, dict) or item.get("sourceKind") not in {"forbidden_edge", "old_camp_echo", "cave_return", "cave_rescue"}:
                continue
            source = self._forbidden_edge_route_proof_source(
                tribe,
                "collection_wall",
                item.get("id", ""),
                item.get("label", "收藏墙旧物"),
                f"{item.get('curatorName', '成员')}挂上的{item.get('sourceLabel', '旧物')}可以被重新系到禁地路证旁。",
                item.get("sourceLabel", "收藏墙"),
                {"sourceLabels": [item.get("displayLabel", "收藏墙")], "rewardParts": item.get("rewardParts", [])}
            )
            if source:
                sources.append(source)

        dispute_records = self._public_dispute_witness_evidence(tribe) if hasattr(self, "_public_dispute_witness_evidence") else tribe.get("dispute_witness_records", []) or []
        for record in reversed(dispute_records):
            if not isinstance(record, dict):
                continue
            evidence_id = record.get("evidenceId") or record.get("evidenceTag") or record.get("sourceId") or record.get("id", "")
            source = self._forbidden_edge_route_proof_source(
                tribe,
                "dispute_witness",
                evidence_id,
                record.get("lineageLabel") or record.get("label", "争端见证石"),
                f"{record.get('sourceLabel', '公开证据')}已经被见证石固定，可以给禁地路证提供可核对的来源链。",
                record.get("sourceLabel", "争端见证石"),
                {
                    "evidenceId": evidence_id,
                    "otherTribeId": record.get("otherTribeId", ""),
                    "otherTribeName": record.get("otherTribeName", ""),
                    "sourceLabels": record.get("sourceChain", [])[-3:],
                    "referenceCount": record.get("referenceCount", 0)
                }
            )
            if source:
                sources.append(source)

        return sources

    def _ensure_forbidden_edge_route_proofs(self, tribe: dict):
        if not tribe:
            return
        completed = {
            record.get("sourceKey")
            for record in (tribe.get("forbidden_edge_route_proof_records", []) or [])
            if isinstance(record, dict) and record.get("sourceKey")
        }
        active = [
            proof for proof in (tribe.get("forbidden_edge_route_proofs", []) or [])
            if isinstance(proof, dict) and proof.get("status", "active") == "active" and proof.get("sourceKey") not in completed
        ]
        existing = {proof.get("sourceKey") for proof in active if proof.get("sourceKey")}
        now = datetime.now()
        for source in self._forbidden_edge_route_proof_sources(tribe):
            source_key = source.get("sourceKey")
            if not source_key or source_key in existing or source_key in completed:
                continue
            proof = {
                "id": f"forbidden_route_proof_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
                "status": "active",
                "sourceKey": source_key,
                "sourceKind": source.get("sourceKind"),
                "sourceId": source.get("sourceId"),
                "label": f"{source.get('label', '禁地')}路证",
                "summary": source.get("summary", ""),
                "sourceLabel": source.get("sourceLabel", "路证来源"),
                "sourceLabels": source.get("sourceLabels", []),
                "otherTribeId": source.get("otherTribeId", ""),
                "otherTribeName": source.get("otherTribeName", ""),
                "evidenceId": source.get("evidenceId", ""),
                "progress": 0,
                "target": TRIBE_FORBIDDEN_EDGE_ROUTE_PROOF_TARGET,
                "participants": [],
                "createdAt": now.isoformat()
            }
            active.append(proof)
            existing.add(source_key)
        tribe["forbidden_edge_route_proofs"] = active[-TRIBE_FORBIDDEN_EDGE_ROUTE_PROOF_LIMIT:]

    def _public_forbidden_edge_route_proofs(self, tribe: dict) -> list:
        self._ensure_forbidden_edge_route_proofs(tribe)
        return [dict(proof) for proof in (tribe.get("forbidden_edge_route_proofs", []) or []) if isinstance(proof, dict) and proof.get("status") == "active"]

    def _public_forbidden_edge_route_proof_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("forbidden_edge_route_proof_records", []) or [])
            if isinstance(record, dict)
        ][-TRIBE_FORBIDDEN_EDGE_ROUTE_PROOF_RECORD_LIMIT:]

    def _public_forbidden_edge_route_proof_actions(self) -> dict:
        actions = {}
        for key, action in TRIBE_FORBIDDEN_EDGE_ROUTE_PROOF_ACTIONS.items():
            actions[key] = {
                **action,
                "rewardLabel": self._reward_summary_text(action.get("reward", {})) if hasattr(self, "_reward_summary_text") else ""
            }
        return actions

    def _apply_forbidden_edge_route_proof_relation(self, tribe: dict, proof: dict, action: dict) -> list:
        other_id = proof.get("otherTribeId")
        other = self.tribes.get(other_id) if other_id and hasattr(self, "tribes") else None
        if not other or other.get("id") == tribe.get("id"):
            return []
        relation_delta = int(action.get("relationDelta", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        if not relation_delta and not trust_delta:
            return []
        now_text = datetime.now().isoformat()
        for own, target in ((tribe, other), (other, tribe)):
            relation = own.setdefault("boundary_relations", {}).setdefault(target.get("id"), {})
            relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            relation["lastAction"] = "forbidden_edge_route_proof"
            relation["lastActionAt"] = now_text
        parts = []
        if relation_delta:
            parts.append(f"双方关系+{relation_delta}")
        if trust_delta:
            parts.append(f"双方信任+{trust_delta}")
        return parts

    def _create_forbidden_edge_route_proof_experience(self, tribe: dict, proof: dict, record: dict) -> dict:
        now = datetime.now()
        source_labels = [proof.get("sourceLabel", "禁地路证")]
        source_labels.extend(label for label in proof.get("sourceLabels", []) or [] if label)
        experience = {
            "id": f"forbidden_edge_route_proof_exp_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "label": "禁地路证",
            "summary": f"{record.get('memberName', '成员')}公开刻写{proof.get('label', '禁地路证')}，下一次逗留深探可以按路证降低迷失风险。",
            "edgeId": proof.get("sourceId"),
            "edgeLabel": proof.get("label", "禁地路证"),
            "safetyBonus": TRIBE_FORBIDDEN_EDGE_ROUTE_PROOF_SAFETY,
            "sourceLabels": source_labels[-4:],
            "createdAt": now.isoformat()
        }
        experiences = self._active_forbidden_edge_route_experiences(tribe)
        tribe["forbidden_edge_route_experiences"] = [*experiences, experience][-TRIBE_FORBIDDEN_EDGE_ROUTE_EXPERIENCE_LIMIT:]
        return experience

    def _public_forbidden_edge_actions(self, tribe: dict) -> dict:
        actions = {}
        for key, action in TRIBE_FORBIDDEN_EDGE_ACTIONS.items():
            available = True
            reason = ""
            if int(action.get("requiresMembers", 0) or 0) > len(tribe.get("members", {}) or {}):
                available = False
                reason = f"需要至少 {action.get('requiresMembers')} 名成员"
            support_bonus, support_labels = self._forbidden_edge_support_bonus(tribe, key)
            actions[key] = {
                **action,
                "available": available,
                "reason": reason,
                "supportBonus": support_bonus,
                "supportLabels": support_labels,
                "rewardLabel": self._reward_summary_text(action.get("reward", {})) if hasattr(self, "_reward_summary_text") else ""
            }
        return actions

    def _near_forbidden_edge(self, player_id: str, edge: dict) -> bool:
        player = self.players.get(player_id, {}) if hasattr(self, "players") else {}
        dx = float(player.get("x", 0) or 0) - float(edge.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(edge.get("z", 0) or 0)
        return math.sqrt(dx * dx + dz * dz) <= float(edge.get("radius", TRIBE_FORBIDDEN_EDGE_RADIUS) or TRIBE_FORBIDDEN_EDGE_RADIUS)

    def _apply_forbidden_edge_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("food", "食物", "food")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        return parts

    def _forbidden_edge_sacred_fire_active(self, tribe: dict) -> bool:
        relay = self._active_sacred_fire_relay(tribe) if hasattr(self, "_active_sacred_fire_relay") else None
        if relay:
            return True
        for record in reversed(tribe.get("sacred_fire_history", []) or []):
            if isinstance(record, dict):
                return True
        return False

    def _forbidden_edge_mentorship_active(self, tribe: dict) -> bool:
        mentorship = self._active_mentorship(tribe) if hasattr(self, "_active_mentorship") else None
        if mentorship and mentorship.get("focusKey") in {"trail", "cave", "gather"}:
            return True
        for record in reversed(tribe.get("mentorship_history", []) or []):
            if isinstance(record, dict) and record.get("focusKey") in {"trail", "cave", "gather"}:
                return True
        return False

    def _forbidden_edge_oral_map_active(self, tribe: dict) -> bool:
        bonuses = self._active_cave_route_bonuses(tribe) if hasattr(self, "_active_cave_route_bonuses") else tribe.get("cave_route_bonuses", []) or []
        if any(
            isinstance(item, dict)
            and item.get("status", "active") == "active"
            and (item.get("sourceActionKey") == "cave_route" or str(item.get("id", "")).startswith("oral_map"))
            for item in bonuses
        ):
            return True
        return any(
            isinstance(record, dict) and record.get("actionKey") == "cave_route"
            for record in (tribe.get("oral_map_records", []) or [])[-3:]
        )

    def _forbidden_edge_support_bonus(self, tribe: dict, action_key: str) -> tuple[int, list]:
        labels = []
        bonus = 0
        if action_key == "torch_probe" and self._forbidden_edge_sacred_fire_active(tribe):
            labels.append("圣火余烬")
            bonus += 1
        elif action_key == "torch_probe" and self._has_tribe_structure_type(tribe, "campfire"):
            labels.append("营火旧光")
            bonus += 1
        if action_key == "trail_probe" and (tribe.get("trail_markers") or tribe.get("trail_marker_history")):
            labels.append("活路标")
            bonus += 1
        if action_key in {"trail_probe", "linger"}:
            if hasattr(self, "_oral_map_context_support"):
                oral_bonus, oral_labels, _, _ = self._oral_map_context_support(tribe, "forbidden_edge")
                if oral_bonus:
                    bonus += oral_bonus
                    labels.extend(oral_labels)
            elif self._forbidden_edge_oral_map_active(tribe):
                labels.append("口述归路图")
                bonus += 1
        if action_key == "companion_probe" and len(tribe.get("members", {}) or {}) >= 3:
            labels.append("多人照应")
            bonus += 1
        if action_key in {"companion_probe", "linger"} and self._forbidden_edge_mentorship_active(tribe):
            labels.append("导师探路")
            bonus += 1
        if int(tribe.get("tamed_beasts", 0) or 0) > 0:
            labels.append("幼兽预警")
            bonus += 1
        return bonus, labels

    def _create_forbidden_edge_rescue(self, tribe: dict, edge: dict, player_id: str, member_name: str, action: dict) -> dict:
        now = datetime.now()
        race_id = f"forbidden_rescue_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}"
        rescue = {
            "id": race_id,
            "status": "rescue",
            "type": "cave_rescue_clue",
            "title": "禁地边缘营救",
            "label": f"{edge.get('label', '禁地边缘')}营救线索",
            "summary": "成员在禁地边缘逗留太久，留下了可循线救回的痕迹。",
            "caveLabel": edge.get("label", "禁地边缘"),
            "sourceKind": "forbidden_edge",
            "sourceId": edge.get("id"),
            "sourceTribeId": tribe.get("id"),
            "sourceTribeName": tribe.get("name", "部落"),
            "x": edge.get("x", 0),
            "z": edge.get("z", 0),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_CAVE_RACE_RESCUE_MINUTES * 60).isoformat(),
            "rescue": {
                "status": "missing",
                "missingPlayerId": player_id,
                "missingMemberName": member_name,
                "progress": 0,
                "target": TRIBE_FORBIDDEN_EDGE_RESCUE_TARGET,
                "helperIds": [],
                "steps": [],
                "supportLabels": [action.get("label", "禁地试探")],
                "createdAt": now.isoformat()
            }
        }
        races = self._active_cave_races(tribe) if hasattr(self, "_active_cave_races") else []
        tribe["cave_races"] = [*races, rescue][-TRIBE_CAVE_RACE_LIMIT:]
        return rescue

    async def mark_forbidden_edge_route_proof(self, player_id: str, proof_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        self._ensure_forbidden_edge_route_proofs(tribe)
        proof = next((
            item for item in (tribe.get("forbidden_edge_route_proofs", []) or [])
            if isinstance(item, dict) and item.get("id") == proof_id and item.get("status") == "active"
        ), None)
        if not proof:
            await self._send_tribe_error(player_id, "没有找到可刻写的禁地路证")
            return
        if any(item.get("memberId") == player_id for item in proof.get("participants", []) or []):
            await self._send_tribe_error(player_id, "你已经刻写过这份禁地路证")
            return
        action = TRIBE_FORBIDDEN_EDGE_ROUTE_PROOF_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知禁地路证刻写方式")
            return

        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", self.players.get(player_id, {}).get("name", "成员"))
        reward_parts = self._apply_forbidden_edge_reward(tribe, action.get("reward", {}))
        relation_parts = self._apply_forbidden_edge_route_proof_relation(tribe, proof, action)
        witness_parts = []
        if proof.get("evidenceId") and hasattr(self, "_record_dispute_witness_reference"):
            _, witness_parts = self._record_dispute_witness_reference(
                tribe,
                proof.get("evidenceId"),
                "forbidden_edge_route_proof",
                action.get("label", "禁地路证"),
                proof.get("otherTribeId", "")
            )
        participant = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "刻写路证"),
            "rewardParts": reward_parts + relation_parts + witness_parts,
            "createdAt": now.isoformat()
        }
        proof.setdefault("participants", []).append(participant)
        proof["progress"] = int(proof.get("progress", 0) or 0) + 1
        completed = proof["progress"] >= int(proof.get("target", TRIBE_FORBIDDEN_EDGE_ROUTE_PROOF_TARGET) or 1)
        detail = f"{member_name}在{proof.get('label', '禁地路证')}上{action.get('label', '刻写路证')}，进度 {proof['progress']} / {proof.get('target', 1)}。"
        if reward_parts or relation_parts or witness_parts:
            detail += f" {'、'.join(reward_parts + relation_parts + witness_parts)}。"
        record = None
        if completed:
            proof["status"] = "completed"
            proof["completedAt"] = now.isoformat()
            record = {
                "id": f"forbidden_route_proof_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
                "sourceKey": proof.get("sourceKey"),
                "sourceKind": proof.get("sourceKind"),
                "sourceId": proof.get("sourceId"),
                "label": proof.get("label", "禁地路证"),
                "sourceLabel": proof.get("sourceLabel", "路证来源"),
                "sourceLabels": proof.get("sourceLabels", []),
                "otherTribeId": proof.get("otherTribeId", ""),
                "otherTribeName": proof.get("otherTribeName", ""),
                "evidenceId": proof.get("evidenceId", ""),
                "memberId": player_id,
                "memberName": member_name,
                "actionKey": action_key,
                "actionLabel": action.get("label", "刻写路证"),
                "participantNames": [item.get("memberName", "成员") for item in proof.get("participants", [])],
                "rewardParts": reward_parts + relation_parts + witness_parts,
                "createdAt": proof["completedAt"]
            }
            created_experience = self._create_forbidden_edge_route_proof_experience(tribe, proof, record)
            record["routeProofCreated"] = created_experience
            tribe.setdefault("forbidden_edge_route_proof_records", []).append(record)
            tribe["forbidden_edge_route_proof_records"] = tribe["forbidden_edge_route_proof_records"][-TRIBE_FORBIDDEN_EDGE_ROUTE_PROOF_RECORD_LIMIT:]
            tribe["forbidden_edge_route_proofs"] = [
                item for item in (tribe.get("forbidden_edge_route_proofs", []) or [])
                if isinstance(item, dict) and item.get("status") == "active"
            ][-TRIBE_FORBIDDEN_EDGE_ROUTE_PROOF_LIMIT:]
            detail += f" 路证已公开，沉淀为{created_experience.get('label', '禁地路证')}，下次高风险禁地行动更不容易迷失。"
        self._add_tribe_history(tribe, "exploration", "禁地路证", detail, player_id, {"kind": "forbidden_edge_route_proof", "proof": proof, "record": record})
        await self._notify_tribe(tribe_id, detail)
        if completed:
            await self._publish_world_rumor(
                "exploration",
                "禁地路证公开",
                f"{tribe.get('name', '某个部落')}把{proof.get('sourceLabel', '禁地来源')}刻成禁地路证，后来者沿这条证据回路试探高风险边缘。",
                {"tribeId": tribe_id, "proofId": proof_id, "sourceKind": proof.get("sourceKind")}
            )
        await self.broadcast_tribe_state(tribe_id)
        other_id = proof.get("otherTribeId")
        if other_id and other_id != tribe_id and other_id in self.tribes:
            await self.broadcast_tribe_state(other_id)

    async def explore_forbidden_edge(self, player_id: str, edge_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_FORBIDDEN_EDGE_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知禁地试探方式")
            return
        if int(action.get("requiresMembers", 0) or 0) > len(tribe.get("members", {}) or {}):
            await self._send_tribe_error(player_id, f"{action.get('label', '试探')}需要至少 {action.get('requiresMembers')} 名成员")
            return
        edge = next((item for item in self._active_forbidden_edges(tribe) if item.get("id") == edge_id), None)
        if not edge:
            await self._send_tribe_error(player_id, "这片禁地边缘已经隐去")
            return
        if any(item.get("memberId") == player_id for item in edge.get("participants", []) or []):
            await self._send_tribe_error(player_id, "你已经试探过这片禁地边缘")
            return
        if not self._near_forbidden_edge(player_id, edge):
            await self._send_tribe_error(player_id, f"需要靠近禁地边缘 {TRIBE_FORBIDDEN_EDGE_RADIUS} 步内")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(action.get("woodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"{action.get('label', '试探')}需要公共木材{wood_cost}")
            return
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost

        now = datetime.now()
        rng = self._forbidden_edge_rng()
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", self.players.get(player_id, {}).get("name", "成员"))
        support_bonus, support_labels = self._forbidden_edge_support_bonus(tribe, action_key)
        consumed_experience = None
        if int(action.get("safety", 0) or 0) < 1:
            consumed_experience = self._consume_forbidden_edge_route_experience(tribe, "forbidden_edge_probe")
            if consumed_experience:
                support_bonus += int(consumed_experience.get("safetyBonus", TRIBE_FORBIDDEN_EDGE_ROUTE_EXPERIENCE_SAFETY) or 0)
                support_labels.append(consumed_experience.get("label", "禁地回撤经验"))
        roll = rng.randint(1, 6)
        total = roll + int(action.get("safety", 0) or 0) + support_bonus
        lost = total < TRIBE_FORBIDDEN_EDGE_DANGER_TARGET
        reward_parts = [] if lost else self._apply_forbidden_edge_reward(tribe, action.get("reward", {}))
        if lost:
            tribe["forbidden_edge_safe_streak"] = 0
        else:
            tribe["forbidden_edge_safe_streak"] = int(tribe.get("forbidden_edge_safe_streak", 0) or 0) + 1
        participant = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "禁地试探"),
            "roll": roll,
            "total": total,
            "lost": lost,
            "supportLabels": support_labels,
            "rewardParts": reward_parts,
            "routeExperienceLabel": consumed_experience.get("label") if consumed_experience else "",
            "createdAt": now.isoformat()
        }
        edge.setdefault("participants", []).append(participant)
        edge["lastActionLabel"] = action.get("label", "禁地试探")
        edge["lastActorName"] = member_name
        edge["lastOutcome"] = "rescue" if lost else "safe"
        record = {
            "id": f"forbidden_edge_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "edgeId": edge.get("id"),
            "label": edge.get("label", "禁地边缘"),
            "summary": edge.get("summary", ""),
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "禁地试探"),
            "lost": lost,
            "roll": roll,
            "total": total,
            "supportLabels": support_labels,
            "rewardParts": reward_parts,
            "routeExperienceUsed": consumed_experience,
            "collectionReady": bool(action.get("collectionReady")) and not lost,
            "createdAt": now.isoformat()
        }
        rescue = None
        created_experience = None
        if lost:
            rescue = self._create_forbidden_edge_rescue(tribe, edge, player_id, member_name, action)
            record["rescueId"] = rescue.get("id")
        elif int(tribe.get("forbidden_edge_safe_streak", 0) or 0) >= TRIBE_FORBIDDEN_EDGE_SAFE_STREAK_TARGET:
            created_experience = self._create_forbidden_edge_route_experience(tribe, edge, record, support_labels)
            tribe["forbidden_edge_safe_streak"] = 0
            record["routeExperienceCreated"] = created_experience
        oral_reference = None
        oral_lineage = None
        if hasattr(self, "_record_oral_map_context_reference"):
            oral_reference, oral_lineage = self._record_oral_map_context_reference(tribe, "forbidden_edge", edge.get("label", "禁地边缘"), member_name, "迷失" if lost else action.get("label", "试探"))
            record["oralMapReference"] = oral_reference
            record["oralMapLineage"] = oral_lineage
        tribe.setdefault("forbidden_edge_records", []).append(record)
        tribe["forbidden_edge_records"] = tribe["forbidden_edge_records"][-TRIBE_FORBIDDEN_EDGE_RECORD_LIMIT:]

        if lost:
            detail = f"{member_name}在{edge.get('label', '禁地边缘')}逗留过深，掷出{roll}，留下营救线索而非死亡。"
        else:
            detail = f"{member_name}在{edge.get('label', '禁地边缘')}完成{action.get('label', '试探')}，掷出{roll}+支撑{support_bonus}，{'、'.join(reward_parts) or '安全回撤'}。"
            if consumed_experience:
                detail += f" 消耗{consumed_experience.get('label', '禁地回撤经验')}稳住回路。"
            if created_experience:
                detail += f" 连续安全回撤沉淀为{created_experience.get('label', '禁地回撤经验')}。"
            if record.get("collectionReady"):
                detail += " 带回的边缘旧物可整理进收藏墙。"
        if oral_reference:
            detail += f" 引用了{oral_reference.get('actionLabel', '口述地图')}。"
        if oral_lineage:
            detail += f" 形成{oral_lineage.get('label', '路线讲述谱系')}。"
        self._add_tribe_history(tribe, "exploration", "禁地边缘", detail, player_id, {"kind": "forbidden_edge", "record": record, "edge": edge})
        await self._notify_tribe(tribe_id, detail)
        if lost:
            await self._publish_world_rumor(
                "exploration",
                "禁地边缘留下营救线索",
                f"{tribe.get('name', '某个部落')}在禁地边缘失去一名试探者的踪迹，但线索仍可循回。",
                {"tribeId": tribe_id, "edgeId": edge.get("id"), "rescueId": rescue.get("id") if rescue else ""}
            )
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
