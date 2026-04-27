from datetime import datetime

from game_config import *


class GameCraftLegacyMixin:
    def _active_craft_legacy_buffs(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for buff in tribe.get("craft_legacy_buffs", []) or []:
            if not isinstance(buff, dict) or buff.get("status") != "active":
                continue
            try:
                if datetime.fromisoformat(buff.get("activeUntil", "")) <= now:
                    buff["status"] = "expired"
                    buff["expiredAt"] = now.isoformat()
                    continue
            except (TypeError, ValueError):
                buff["status"] = "expired"
                buff["expiredAt"] = now.isoformat()
                continue
            active.append(buff)
        if len(active) != len(tribe.get("craft_legacy_buffs", []) or []):
            tribe["craft_legacy_buffs"] = active[-TRIBE_CRAFT_LEGACY_BUFF_LIMIT:]
        return active[-TRIBE_CRAFT_LEGACY_BUFF_LIMIT:]

    def _craft_legacy_build_discount(self, tribe: dict) -> int:
        return sum(int(buff.get("buildCostDiscountPercent", 0) or 0) for buff in self._active_craft_legacy_buffs(tribe))

    def _craft_legacy_ritual_gather_bonus(self, tribe: dict) -> int:
        return sum(int(buff.get("ritualGatherBonus", 0) or 0) for buff in self._active_craft_legacy_buffs(tribe))

    def _craft_legacy_trade_reputation_bonus(self, tribe: dict) -> int:
        return sum(int(buff.get("tradeReputationBonus", 0) or 0) for buff in self._active_craft_legacy_buffs(tribe))

    def _craft_legacy_cave_finds_bonus(self, tribe: dict) -> int:
        return sum(int(buff.get("caveFindsBonus", 0) or 0) for buff in self._active_craft_legacy_buffs(tribe))

    def _craft_legacy_source_candidates(self, tribe: dict) -> list:
        if not tribe:
            return []
        candidates = []
        seen = set()

        def add_candidate(kind: str, source: dict, label: str, summary: str, keeper_name: str = ""):
            source_id = source.get("id") or f"{kind}_{len(candidates)}"
            candidate_id = f"{kind}:{source_id}"
            if candidate_id in seen:
                return
            seen.add(candidate_id)
            candidates.append({
                "id": candidate_id,
                "kind": kind,
                "sourceId": source_id,
                "label": label,
                "summary": summary,
                "keeperName": keeper_name,
                "sourceLabel": source.get("label") or source.get("focusLabel") or source.get("displayLabel") or label,
                "createdAt": source.get("createdAt") or source.get("completedAt")
            })

        for buff in [*(tribe.get("lost_tech_buffs", []) or []), *(tribe.get("lost_tech_records", []) or [])]:
            if isinstance(buff, dict):
                add_candidate(
                    "lost_tech",
                    buff,
                    buff.get("label", "复原技艺"),
                    buff.get("summary", "复原技艺可以被整理成营地手艺名声。"),
                    buff.get("restoredByName", "")
                )

        for item in tribe.get("collection_wall", []) or []:
            if isinstance(item, dict):
                add_candidate(
                    "collection",
                    item,
                    item.get("displayLabel") or item.get("label", "收藏旧物"),
                    item.get("summary", "收藏墙上的旧物可以成为手艺传名来源。"),
                    item.get("curatorName", "")
                )

        for item in tribe.get("echo_items", []) or []:
            if isinstance(item, dict) and len(item.get("memories", []) or []) >= TRIBE_CRAFT_LEGACY_MIN_ECHO_MEMORIES:
                add_candidate(
                    "echo_item",
                    item,
                    item.get("label", "回声物品"),
                    f"{item.get('label', '回声物品')}已经有{len(item.get('memories', []) or [])}段经历，足以传成营地手艺。",
                    item.get("holderName", "")
                )

        for session in tribe.get("mentorship_history", []) or []:
            if isinstance(session, dict):
                add_candidate(
                    "mentorship",
                    session,
                    session.get("focusLabel", "导师课程"),
                    session.get("summary", "结课导师课程可以被整理成后来者继续沿用的方法。"),
                    session.get("mentorName", "")
                )

        return candidates[-TRIBE_CRAFT_LEGACY_SOURCE_LIMIT:]

    def _public_craft_legacy(self, tribe: dict) -> dict:
        return {
            "sources": self._craft_legacy_source_candidates(tribe),
            "buffs": self._active_craft_legacy_buffs(tribe),
            "records": [item for item in tribe.get("craft_legacy_records", []) or [] if isinstance(item, dict)][-TRIBE_CRAFT_LEGACY_RECORD_LIMIT:]
        }

    def _apply_craft_legacy_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        return parts

    async def establish_craft_legacy(self, player_id: str, candidate_id: str, style_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        style = TRIBE_CRAFT_LEGACY_STYLES.get(style_key)
        if not style:
            await self._send_tribe_error(player_id, "未知手艺传名方向")
            return
        candidates = self._craft_legacy_source_candidates(tribe)
        candidate = next((item for item in candidates if item.get("id") == candidate_id), None)
        if not candidate:
            await self._send_tribe_error(player_id, "这条手艺来源还不够稳，无法传名")
            return
        active = self._active_craft_legacy_buffs(tribe)
        if any(item.get("sourceCandidateId") == candidate_id and item.get("styleKey") == style_key for item in active):
            await self._send_tribe_error(player_id, "这条手艺已经按这个方向传名")
            return

        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        reward_parts = self._apply_craft_legacy_reward(tribe, style.get("reward", {}))
        buff = {
            "id": f"craft_legacy_{tribe_id}_{style_key}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "styleKey": style_key,
            "styleLabel": style.get("label", "手艺传名"),
            "label": f"{candidate.get('sourceLabel', candidate.get('label', '旧手艺'))}·{style.get('label', '传名')}",
            "summary": style.get("summary", ""),
            "sourceCandidateId": candidate_id,
            "sourceKind": candidate.get("kind"),
            "sourceLabel": candidate.get("sourceLabel") or candidate.get("label"),
            "keeperName": candidate.get("keeperName"),
            "createdBy": player_id,
            "createdByName": member_name,
            "rewardParts": reward_parts,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_CRAFT_LEGACY_ACTIVE_MINUTES * 60).isoformat()
        }
        for key in ("buildCostDiscountPercent", "ritualGatherBonus", "tradeReputationBonus", "caveFindsBonus"):
            amount = int(style.get(key, 0) or 0)
            if amount:
                buff[key] = amount
        tribe.setdefault("craft_legacy_buffs", []).append(buff)
        tribe["craft_legacy_buffs"] = tribe["craft_legacy_buffs"][-TRIBE_CRAFT_LEGACY_BUFF_LIMIT:]
        tribe.setdefault("craft_legacy_records", []).append(dict(buff))
        tribe["craft_legacy_records"] = tribe["craft_legacy_records"][-TRIBE_CRAFT_LEGACY_RECORD_LIMIT:]

        detail = f"{member_name}把“{candidate.get('sourceLabel', '旧手艺')}”整理成{style.get('label', '手艺传名')}，来源守护者：{candidate.get('keeperName') or '众人'}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "culture", "营地手艺传名", detail, player_id, {"kind": "craft_legacy", "buff": buff, "source": candidate})
        await self._publish_world_rumor(
            "culture",
            "营地手艺传名",
            f"{tribe.get('name', '部落')}把“{candidate.get('sourceLabel', '旧手艺')}”传成{style.get('label', '手艺名声')}，后来者有了可照做的方法。",
            {"tribeId": tribe_id, "styleKey": style_key, "sourceKind": candidate.get("kind")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
