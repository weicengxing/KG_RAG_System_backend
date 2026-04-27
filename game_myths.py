from datetime import datetime

from game_config import *


class GameMythMixin:
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

    def _public_myth_interpretations(self, claim: dict) -> list:
        versions = claim.get("versions", {}) or {}
        result = []
        for key, config in TRIBE_MYTH_INTERPRETATIONS.items():
            version = versions.get(key, {}) or {}
            supporters = version.get("supporters", []) or []
            result.append({
                "key": key,
                "label": config.get("label", key),
                "summary": config.get("summary", ""),
                "rewardLabel": self._reward_summary_text(config.get("reward", {})),
                "influence": int(version.get("influence", 0) or len(supporters)),
                "supporterCount": len(supporters),
                "supporterNames": [item.get("name", "成员") for item in supporters[-3:] if isinstance(item, dict)]
            })
        return result

    def _public_myth_claim(self, claim: dict) -> dict:
        interpretations = self._public_myth_interpretations(claim)
        leader = max(interpretations, key=lambda item: item.get("influence", 0), default=None)
        return {
            "id": claim.get("id"),
            "title": claim.get("title", "神话解释权"),
            "summary": claim.get("summary", ""),
            "sourceKind": claim.get("sourceKind", ""),
            "sourceLabel": claim.get("sourceLabel", ""),
            "influenceTarget": int(claim.get("influenceTarget", TRIBE_MYTH_INFLUENCE_TARGET) or TRIBE_MYTH_INFLUENCE_TARGET),
            "leaderLabel": leader.get("label") if leader and leader.get("influence", 0) > 0 else "",
            "leaderInfluence": leader.get("influence", 0) if leader else 0,
            "interpretations": interpretations,
            "createdAt": claim.get("createdAt"),
            "activeUntil": claim.get("activeUntil")
        }

    def _active_myth_claims(self, tribe: dict) -> list:
        return [self._public_myth_claim(claim) for claim in self._active_myth_claim_records(tribe)]

    def _active_dominant_myths(self, tribe: dict) -> list:
        return list(tribe.get("dominant_myths", []) or [])[-TRIBE_DOMINANT_MYTH_LIMIT:]

    def _open_myth_claim(self, tribe: dict, source_kind: str, source_label: str, summary: str, x: float = 0, z: float = 0, source_id: str = "", actor_name: str = "") -> dict | None:
        if not tribe:
            return None
        active = self._active_myth_claim_records(tribe)
        dedupe_id = f"{source_kind}:{source_id}" if source_id else ""
        if dedupe_id and any(item.get("dedupeId") == dedupe_id for item in active):
            return None
        now = datetime.now()
        claim = {
            "id": f"myth_{tribe.get('id')}_{int(now.timestamp() * 1000)}",
            "status": "open",
            "title": f"{source_label or '大事'}的解释权",
            "summary": summary or "这件事正在被不同说法争夺意义。",
            "sourceKind": source_kind,
            "sourceLabel": source_label or "大事",
            "dedupeId": dedupe_id,
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

    async def support_myth_claim(self, player_id: str, claim_id: str, interpretation_key: str):
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
        versions = claim.setdefault("versions", {})
        if any(player_id in [supporter.get("id") for supporter in (version.get("supporters", []) or []) if isinstance(supporter, dict)] for version in versions.values() if isinstance(version, dict)):
            await self._send_tribe_error(player_id, "你已经支持过这次解释权争夺")
            return
        member = tribe.get("members", {}).get(player_id, {})
        version = versions.setdefault(interpretation_key, {"supporters": [], "influence": 0})
        version.setdefault("supporters", []).append({
            "id": player_id,
            "name": member.get("name", "成员"),
            "at": datetime.now().isoformat()
        })
        version["influence"] = int(version.get("influence", 0) or 0) + 1
        label = config.get("label", interpretation_key)
        target = int(claim.get("influenceTarget", TRIBE_MYTH_INFLUENCE_TARGET) or TRIBE_MYTH_INFLUENCE_TARGET)
        if int(version.get("influence", 0) or 0) >= target:
            await self._complete_myth_claim(tribe_id, tribe, claim, interpretation_key, config, player_id)
            return
        detail = f"{member.get('name', '成员')} 支持把{claim.get('sourceLabel', '这件事')}解释为“{label}”，影响 {version['influence']} / {target}。"
        self._add_tribe_history(
            tribe,
            "world_event",
            "神话解释升温",
            detail,
            player_id,
            {"kind": "myth_claim", "claimId": claim_id, "interpretationKey": interpretation_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def _complete_myth_claim(self, tribe_id: str, tribe: dict, claim: dict, interpretation_key: str, config: dict, player_id: str):
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
            "completedAt": datetime.now().isoformat()
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
