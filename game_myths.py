from datetime import datetime

from game_config import *


class GameMythMixin:
    def _active_myth_divergences(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for item in tribe.get("myth_divergences", []) or []:
            if not isinstance(item, dict):
                continue
            active_until = item.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    pass
            active.append(item)
        if len(active) != len(tribe.get("myth_divergences", []) or []):
            tribe["myth_divergences"] = active[-TRIBE_MYTH_DIVERGENCE_LIMIT:]
        return active[-TRIBE_MYTH_DIVERGENCE_LIMIT:]

    def _active_myth_claim_records(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for claim in tribe.get("myth_claims", []) or []:
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
        if len(active) != len(tribe.get("myth_claims", []) or []):
            tribe["myth_claims"] = active[-TRIBE_MYTH_CLAIM_LIMIT:]
        return active[-TRIBE_MYTH_CLAIM_LIMIT:]

    def _myth_claim_influence(self, claim: dict, interpretation_key: str) -> int:
        version = (claim.get("versions", {}) or {}).get(interpretation_key, {}) or {}
        supporters = version.get("supporters", []) or []
        return int(version.get("influence", 0) or len(supporters))

    def _shared_myth_claim_records(self, claim: dict) -> list:
        if not claim.get("shared") or not claim.get("dedupeId"):
            return []
        records = []
        for tribe in self.tribes.values():
            for item in self._active_myth_claim_records(tribe):
                if item.get("dedupeId") == claim.get("dedupeId"):
                    records.append((tribe, item))
        return records

    def _myth_claim_influence_target(self, claim: dict, shared_records: list | None = None) -> int:
        target = int(claim.get("influenceTarget", TRIBE_MYTH_INFLUENCE_TARGET) or TRIBE_MYTH_INFLUENCE_TARGET)
        if claim.get("shared"):
            count = len(shared_records or self._shared_myth_claim_records(claim))
            target += max(0, count - 1)
        return target

    def _public_myth_support_methods(self) -> list:
        return [
            {
                "key": key,
                "label": config.get("label", key),
                "summary": config.get("summary", ""),
                "influenceBonus": int(config.get("influenceBonus", 1) or 1)
            }
            for key, config in TRIBE_MYTH_SUPPORT_METHODS.items()
        ]

    def _public_myth_interpretations(self, claim: dict, shared_records: list | None = None) -> list:
        versions = claim.get("versions", {}) or {}
        result = []
        for key, config in TRIBE_MYTH_INTERPRETATIONS.items():
            version = versions.get(key, {}) or {}
            supporters = version.get("supporters", []) or []
            own_influence = int(version.get("influence", 0) or len(supporters))
            shared_influence = own_influence
            if claim.get("shared"):
                records = shared_records or self._shared_myth_claim_records(claim)
                shared_influence = sum(self._myth_claim_influence(item, key) for _, item in records)
            result.append({
                "key": key,
                "label": config.get("label", key),
                "symbol": config.get("symbol", key[:1]),
                "tone": config.get("tone", key),
                "summary": config.get("summary", ""),
                "rewardLabel": self._reward_summary_text(config.get("reward", {})),
                "influence": shared_influence,
                "ownInfluence": own_influence,
                "sharedInfluence": shared_influence,
                "rivalInfluence": max(0, shared_influence - own_influence),
                "methodSummary": "、".join(f"{TRIBE_MYTH_SUPPORT_METHODS.get(key, {}).get('label', key)}{value}" for key, value in (version.get("methods", {}) or {}).items()),
                "supporterCount": len(supporters),
                "supporterNames": [item.get("name", "成员") for item in supporters[-3:] if isinstance(item, dict)]
            })
        return result

    def _public_myth_claim(self, claim: dict) -> dict:
        shared_records = self._shared_myth_claim_records(claim)
        interpretations = self._public_myth_interpretations(claim, shared_records)
        leader = max(interpretations, key=lambda item: item.get("influence", 0), default=None)
        supported = [item for item in interpretations if int(item.get("influence", 0) or 0) > 0]
        rival_names = [
            item.get("name", "其他部落")
            for item in (claim.get("rivalTribes", []) or [])
            if isinstance(item, dict)
        ]
        influence_target = self._myth_claim_influence_target(claim, shared_records)
        return {
            "id": claim.get("id"),
            "title": claim.get("title", "神话解释权"),
            "summary": claim.get("summary", ""),
            "sourceKind": claim.get("sourceKind", ""),
            "sourceLabel": claim.get("sourceLabel", ""),
            "influenceTarget": influence_target,
            "leaderLabel": leader.get("label") if leader and leader.get("influence", 0) > 0 else "",
            "leaderInfluence": leader.get("influence", 0) if leader else 0,
            "interpretations": interpretations,
            "supportMethods": self._public_myth_support_methods(),
            "divergenceSymbols": " ".join(f"{item.get('symbol', '?')}{item.get('influence', 0)}" for item in supported),
            "divergenceSummary": " / ".join(f"{item.get('label')} {item.get('influence', 0)}" for item in supported),
            "hasDivergence": len(supported) > 1,
            "shared": bool(claim.get("shared")),
            "sharedSourceId": claim.get("sharedSourceId", ""),
            "rivalTribeNames": rival_names,
            "sharedSummary": f"同源争夺：{ '、'.join(rival_names) }也在解释这件事。" if rival_names else "",
            "createdAt": claim.get("createdAt"),
            "activeUntil": claim.get("activeUntil")
        }

    def _active_myth_claims(self, tribe: dict) -> list:
        return [self._public_myth_claim(claim) for claim in self._active_myth_claim_records(tribe)]

    def _active_dominant_myths(self, tribe: dict) -> list:
        return list(tribe.get("dominant_myths", []) or [])[-TRIBE_DOMINANT_MYTH_LIMIT:]

    def _public_myth_divergences(self, tribe: dict) -> list:
        return [dict(item) for item in self._active_myth_divergences(tribe)]

    def _myth_divergence_versions(self, claim: dict, shared_records: list | None = None) -> list:
        records = shared_records or self._shared_myth_claim_records(claim)
        versions = []
        for key, config in TRIBE_MYTH_INTERPRETATIONS.items():
            influence = self._myth_claim_influence(claim, key)
            method_counts = dict((claim.get("versions", {}) or {}).get(key, {}).get("methods", {}) or {})
            if claim.get("shared"):
                method_counts = {}
                influence = sum(self._myth_claim_influence(item, key) for _, item in records)
                for _, item in records:
                    for method_key, value in (((item.get("versions", {}) or {}).get(key, {}) or {}).get("methods", {}) or {}).items():
                        method_counts[method_key] = int(method_counts.get(method_key, 0) or 0) + int(value or 0)
            if influence <= 0:
                continue
            versions.append({
                "key": key,
                "label": config.get("label", key),
                "symbol": config.get("symbol", key[:1]),
                "tone": config.get("tone", key),
                "influence": influence,
                "methods": method_counts
            })
        return sorted(versions, key=lambda item: item.get("influence", 0), reverse=True)

    def _sync_myth_divergence(self, tribe: dict, claim: dict, winner_key: str = "") -> dict | None:
        versions = self._myth_divergence_versions(claim)
        if len(versions) < 2:
            return None
        now = datetime.now()
        active = self._active_myth_divergences(tribe)
        source_id = claim.get("dedupeId") or claim.get("id")
        existing = next((item for item in active if item.get("sourceId") == source_id), None)
        divergence = {
            "sourceId": source_id,
            "sourceKind": claim.get("sourceKind", "myth"),
            "sourceLabel": claim.get("sourceLabel", "大事"),
            "label": f"{claim.get('sourceLabel', '大事')}的分歧纹",
            "summary": " / ".join(f"{item.get('symbol')}{item.get('influence')}" for item in versions),
            "methodSummary": " / ".join(
                f"{item.get('symbol')}:" + "、".join(f"{TRIBE_MYTH_SUPPORT_METHODS.get(key, {}).get('label', key)}{value}" for key, value in (item.get("methods", {}) or {}).items())
                for item in versions
                if item.get("methods")
            ),
            "versions": versions,
            "winnerKey": winner_key,
            "winnerLabel": TRIBE_MYTH_INTERPRETATIONS.get(winner_key, {}).get("label", "") if winner_key else "",
            "x": float(claim.get("x", 0) or 0),
            "z": float(claim.get("z", 0) or 0),
            "createdAt": existing.get("createdAt") if existing else now.isoformat(),
            "refreshedAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_MYTH_DIVERGENCE_ACTIVE_MINUTES * 60).isoformat()
        }
        if existing:
            existing.update(divergence)
            result = existing
        else:
            result = {"id": f"myth_divergence_{tribe.get('id')}_{int(now.timestamp() * 1000)}", **divergence}
            active.append(result)
        tribe["myth_divergences"] = active[-TRIBE_MYTH_DIVERGENCE_LIMIT:]
        return result

    def _open_myth_claim(self, tribe: dict, source_kind: str, source_label: str, summary: str, x: float = 0, z: float = 0, source_id: str = "", actor_name: str = "", shared_tribes: list | None = None) -> dict | None:
        if not tribe:
            return None
        active = self._active_myth_claim_records(tribe)
        dedupe_id = f"{source_kind}:{source_id}" if source_id else ""
        participant_tribes = [item for item in (shared_tribes or []) if isinstance(item, dict) and item.get("id")]
        shared = len({item.get("id") for item in participant_tribes}) > 1
        rival_tribes = [
            {"id": item.get("id"), "name": item.get("name", "其他部落")}
            for item in participant_tribes
            if item.get("id") != tribe.get("id")
        ]
        if dedupe_id:
            existing = next((item for item in active if item.get("dedupeId") == dedupe_id), None)
            if existing:
                if shared:
                    existing["shared"] = True
                    existing["sharedSourceId"] = source_id or dedupe_id
                    existing["rivalTribes"] = rival_tribes
                return self._public_myth_claim(existing)
        now = datetime.now()
        claim = {
            "id": f"myth_{tribe.get('id')}_{int(now.timestamp() * 1000)}",
            "status": "open",
            "title": f"{source_label or '大事'}的解释权",
            "summary": summary or "这件事正在被不同说法争夺意义。",
            "sourceKind": source_kind,
            "sourceLabel": source_label or "大事",
            "dedupeId": dedupe_id,
            "ownerTribeId": tribe.get("id"),
            "shared": shared,
            "sharedSourceId": source_id or dedupe_id,
            "rivalTribes": rival_tribes,
            "x": float(x or 0),
            "z": float(z or 0),
            "actorName": actor_name,
            "versions": {},
            "influenceTarget": TRIBE_MYTH_INFLUENCE_TARGET,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_MYTH_CLAIM_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["myth_claims"] = [*active, claim][-TRIBE_MYTH_CLAIM_LIMIT:]
        return self._public_myth_claim(claim)

    def _open_shared_myth_claim(self, tribes: list, source_kind: str, source_label: str, summary: str, x: float = 0, z: float = 0, source_id: str = "", actor_name: str = "") -> list:
        participants = []
        seen = set()
        for tribe in tribes or []:
            if not isinstance(tribe, dict) or not tribe.get("id") or tribe.get("id") in seen:
                continue
            participants.append(tribe)
            seen.add(tribe.get("id"))
        if not participants:
            return []
        if len(participants) == 1:
            claim = self._open_myth_claim(participants[0], source_kind, source_label, summary, x, z, source_id, actor_name)
            return [claim] if claim else []
        opened = []
        for tribe in participants:
            claim = self._open_myth_claim(tribe, source_kind, source_label, summary, x, z, source_id, actor_name, participants)
            if claim:
                opened.append(claim)
        return opened

    def _apply_myth_reward(self, tribe: dict, reward: dict) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                reward_parts.append(f"{label}+{amount}")
        food = int((reward or {}).get("food", 0) or 0)
        if food:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) + food)
            reward_parts.append(f"食物+{food}")
        discovery = int((reward or {}).get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        trade = int((reward or {}).get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        renown = int((reward or {}).get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        return reward_parts

    async def support_myth_claim(self, player_id: str, claim_id: str, interpretation_key: str, method_key: str = ""):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        claims = self._active_myth_claim_records(tribe)
        claim = next((item for item in claims if item.get("id") == claim_id), None)
        if not claim:
            await self._send_tribe_error(player_id, "这次神话争夺已经结束")
            return
        config = TRIBE_MYTH_INTERPRETATIONS.get(interpretation_key)
        if not config:
            await self._send_tribe_error(player_id, "未知的神话解释")
            return
        method_key = method_key if method_key in TRIBE_MYTH_SUPPORT_METHODS else "ritual"
        method = TRIBE_MYTH_SUPPORT_METHODS.get(method_key, TRIBE_MYTH_SUPPORT_METHODS["ritual"])
        influence_bonus = max(1, int(method.get("influenceBonus", 1) or 1))
        versions = claim.setdefault("versions", {})
        if any(player_id in [supporter.get("id") for supporter in (version.get("supporters", []) or []) if isinstance(supporter, dict)] for version in versions.values() if isinstance(version, dict)):
            await self._send_tribe_error(player_id, "你已经支持过这次解释权争夺")
            return
        member = tribe.get("members", {}).get(player_id, {})
        version = versions.setdefault(interpretation_key, {"supporters": [], "influence": 0})
        version.setdefault("supporters", []).append({
            "id": player_id,
            "name": member.get("name", "成员"),
            "methodKey": method_key,
            "methodLabel": method.get("label", method_key),
            "influence": influence_bonus,
            "at": datetime.now().isoformat()
        })
        version.setdefault("methods", {})[method_key] = int((version.get("methods", {}) or {}).get(method_key, 0) or 0) + influence_bonus
        version["influence"] = int(version.get("influence", 0) or 0) + influence_bonus
        label = config.get("label", interpretation_key)
        shared_records = self._shared_myth_claim_records(claim)
        target = self._myth_claim_influence_target(claim, shared_records)
        influence = int(version.get("influence", 0) or 0)
        if claim.get("shared"):
            influence = sum(self._myth_claim_influence(item, interpretation_key) for _, item in shared_records)
        divergence = self._sync_myth_divergence(tribe, claim)
        if influence >= target:
            await self._complete_myth_claim(tribe_id, tribe, claim, interpretation_key, config, player_id)
            return
        if claim.get("shared"):
            rival_names = "、".join(item.get("name", "其他部落") for item in (claim.get("rivalTribes", []) or []) if isinstance(item, dict))
            detail = f"{member.get('name', '成员')} 用{method.get('label', '仪式')}支持把{claim.get('sourceLabel', '这件事')}解释为“{label}”，同源影响 {influence} / {target}。"
            if rival_names:
                detail += f" {rival_names}也在争夺这个源事件的说法。"
        else:
            detail = f"{member.get('name', '成员')} 用{method.get('label', '仪式')}支持把{claim.get('sourceLabel', '这件事')}解释为“{label}”，影响 {version['influence']} / {target}。"
        self._add_tribe_history(
            tribe,
            "world_event",
            "神话解释升温",
            detail,
            player_id,
            {"kind": "myth_claim", "claimId": claim_id, "interpretationKey": interpretation_key, "methodKey": method_key, "methodLabel": method.get("label", method_key), "divergence": divergence}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    def _apply_shared_myth_relation_effect(self, tribe_id: str, other_id: str, interpretation_key: str, now_text: str) -> list:
        tribe = self.tribes.get(tribe_id)
        other = self.tribes.get(other_id)
        if not tribe or not other:
            return []
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
        parts = []
        if interpretation_key == "trade":
            relation["score"] = min(9, int(relation.get("score", 0) or 0) + 1)
            relation["tradeTrust"] = min(10, int(relation.get("tradeTrust", 0) or 0) + 2)
            parts.append("关系+1")
            parts.append("贸易信任+2")
        elif interpretation_key == "border":
            relation["score"] = min(9, int(relation.get("score", 0) or 0) + 1)
            relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - 1)
            relation["canDeclareWar"] = False
            parts.append("关系+1")
            parts.append("战争压力-1")
        elif interpretation_key == "trail":
            relation["tradeTrust"] = min(10, int(relation.get("tradeTrust", 0) or 0) + 1)
            parts.append("贸易信任+1")
        else:
            relation["score"] = min(9, int(relation.get("score", 0) or 0) + 1)
            parts.append("关系+1")
        relation["lastAction"] = f"shared_myth_{interpretation_key}"
        relation["lastActionAt"] = now_text
        return parts

    async def _complete_shared_myth_claim(self, tribe_id: str, tribe: dict, claim: dict, interpretation_key: str, config: dict, player_id: str):
        records = self._shared_myth_claim_records(claim)
        if not records:
            return False
        member = tribe.get("members", {}).get(player_id, {})
        now_text = datetime.now().isoformat()
        reward_parts = self._apply_myth_reward(tribe, config.get("reward", {}))
        involved_ids = []
        for target_tribe, _ in records:
            if target_tribe.get("id") and target_tribe.get("id") not in involved_ids:
                involved_ids.append(target_tribe.get("id"))
        relation_parts = []
        for other_id in involved_ids:
            if other_id == tribe_id:
                continue
            relation_parts.extend(self._apply_shared_myth_relation_effect(tribe_id, other_id, interpretation_key, now_text))
            relation_parts.extend(self._apply_shared_myth_relation_effect(other_id, tribe_id, interpretation_key, now_text))
        relation_parts = list(dict.fromkeys(relation_parts))
        detail = f"{tribe.get('name', '部落')} 将同源事件“{claim.get('sourceLabel', '大事')}”讲成“{config.get('label', interpretation_key)}”，这个版本压过了其他部落的说法。"
        if reward_parts:
            detail += f" 收获：{'、'.join(reward_parts)}。"
        if relation_parts:
            detail += f" 边界回响：{'、'.join(relation_parts)}。"
        for target_tribe, target_claim in records:
            is_winner = target_tribe.get("id") == tribe_id
            myth = {
                "id": f"dominant_{target_claim.get('id')}",
                "title": f"{config.get('label', '主流神话')}成为同源主流",
                "sourceLabel": target_claim.get("sourceLabel", "大事"),
                "interpretationKey": interpretation_key,
                "interpretationLabel": config.get("label", interpretation_key),
                "summary": config.get("summary", ""),
                "rewardParts": reward_parts if is_winner else relation_parts,
                "completedBy": member.get("name", "成员"),
                "completedAt": now_text,
                "shared": True,
                "winnerTribeId": tribe_id,
                "winnerTribeName": tribe.get("name", "部落"),
                "divergence": self._sync_myth_divergence(target_tribe, target_claim, interpretation_key)
            }
            target_tribe["dominant_myths"] = [*(target_tribe.get("dominant_myths", []) or []), myth][-TRIBE_DOMINANT_MYTH_LIMIT:]
            target_tribe["myth_claims"] = [
                item for item in self._active_myth_claim_records(target_tribe)
                if item.get("dedupeId") != claim.get("dedupeId")
            ]
            self._add_tribe_history(
                target_tribe,
                "world_event",
                "同源神话定型",
                detail,
                player_id,
                {"kind": "shared_dominant_myth", **myth}
            )
            await self._notify_tribe(target_tribe.get("id"), detail)
        await self._publish_world_rumor(
            "myth",
            "同源神话定型",
            detail,
            {"tribeId": tribe_id, "claimId": claim.get("id"), "interpretationKey": interpretation_key, "shared": True}
        )
        for target_id in involved_ids:
            await self.broadcast_tribe_state(target_id)
        return True

    async def _complete_myth_claim(self, tribe_id: str, tribe: dict, claim: dict, interpretation_key: str, config: dict, player_id: str):
        if claim.get("shared") and await self._complete_shared_myth_claim(tribe_id, tribe, claim, interpretation_key, config, player_id):
            return
        reward_parts = self._apply_myth_reward(tribe, config.get("reward", {}))
        member = tribe.get("members", {}).get(player_id, {})
        myth = {
            "id": f"dominant_{claim.get('id')}",
            "title": f"{config.get('label', '主流神话')}成为主流",
            "sourceLabel": claim.get("sourceLabel", "大事"),
            "interpretationKey": interpretation_key,
            "interpretationLabel": config.get("label", interpretation_key),
            "summary": config.get("summary", ""),
            "rewardParts": reward_parts,
            "completedBy": member.get("name", "成员"),
            "completedAt": datetime.now().isoformat(),
            "divergence": self._sync_myth_divergence(tribe, claim, interpretation_key)
        }
        tribe["dominant_myths"] = [*(tribe.get("dominant_myths", []) or []), myth][-TRIBE_DOMINANT_MYTH_LIMIT:]
        tribe["myth_claims"] = [item for item in self._active_myth_claim_records(tribe) if item.get("id") != claim.get("id")]
        detail = f"{tribe.get('name', '部落')} 将{claim.get('sourceLabel', '大事')}讲成“{myth['interpretationLabel']}”，这个版本暂时成为主流神话。"
        if reward_parts:
            detail += f" 收获：{'、'.join(reward_parts)}。"
        self._add_tribe_history(
            tribe,
            "world_event",
            "主流神话成形",
            detail,
            player_id,
            {"kind": "dominant_myth", **myth}
        )
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "myth",
            "主流神话成形",
            detail,
            {"tribeId": tribe_id, "claimId": claim.get("id"), "interpretationKey": interpretation_key}
        )
        await self.broadcast_tribe_state(tribe_id)
