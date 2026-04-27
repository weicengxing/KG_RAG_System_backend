from datetime import datetime

from game_config import *


class GameLostTechMixin:
    def _lost_tech_fragments(self, tribe: dict) -> list:
        return [item for item in (tribe.get("lost_tech_fragments", []) or []) if isinstance(item, dict)]

    def _active_lost_tech_buffs(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for buff in tribe.get("lost_tech_buffs", []) or []:
            if not isinstance(buff, dict):
                continue
            try:
                if datetime.fromisoformat(buff.get("activeUntil", "")) <= now:
                    buff["status"] = "expired"
                    continue
            except (TypeError, ValueError):
                buff["status"] = "expired"
                continue
            active.append(buff)
        if len(active) != len(tribe.get("lost_tech_buffs", []) or []):
            tribe["lost_tech_buffs"] = active[-TRIBE_LOST_TECH_HISTORY_LIMIT:]
        return active[-TRIBE_LOST_TECH_HISTORY_LIMIT:]

    def _lost_tech_build_discount(self, tribe: dict) -> int:
        return sum(int(buff.get("buildCostDiscountPercent", 0) or 0) for buff in self._active_lost_tech_buffs(tribe))

    def _lost_tech_ritual_gather_bonus(self, tribe: dict) -> int:
        return sum(int(buff.get("ritualGatherBonus", 0) or 0) for buff in self._active_lost_tech_buffs(tribe))

    def _lost_tech_trade_reputation_bonus(self, tribe: dict) -> int:
        return sum(int(buff.get("tradeReputationBonus", 0) or 0) for buff in self._active_lost_tech_buffs(tribe))

    def _lost_tech_cave_finds_bonus(self, tribe: dict) -> int:
        return sum(int(buff.get("caveFindsBonus", 0) or 0) for buff in self._active_lost_tech_buffs(tribe))

    def _lost_tech_source_available(self, tribe: dict, source_key: str) -> bool:
        source = TRIBE_LOST_TECH_SOURCES.get(source_key, {})
        requirement = source.get("requires")
        if requirement == "discovery_or_collection":
            return bool(tribe.get("discoveries") or tribe.get("collection_wall") or tribe.get("map_memories"))
        if requirement == "cave_memory":
            return any(
                isinstance(item, dict) and item.get("type") in {"cave_first", "rare_cave_race", "night_trace"}
                for item in (tribe.get("map_memories", []) or [])
            ) or any(
                isinstance(item, dict) and item.get("type") == "cave"
                for item in (tribe.get("history", []) or [])
            ) or bool(tribe.get("discoveries"))
        if requirement == "collection":
            return bool(tribe.get("collection_wall") or tribe.get("personal_tokens") or tribe.get("echo_items"))
        if requirement == "history":
            return len(tribe.get("history", []) or []) >= 3
        return True

    def _public_lost_tech_sources(self, tribe: dict) -> list:
        return {
            key: {
                "key": key,
                "label": source.get("label", key),
                "summary": source.get("summary", ""),
                "available": self._lost_tech_source_available(tribe, key)
            }
            for key, source in TRIBE_LOST_TECH_SOURCES.items()
        }

    def _public_lost_tech_state(self, tribe: dict) -> dict:
        fragments = self._lost_tech_fragments(tribe)
        return {
            "fragments": fragments[-TRIBE_LOST_TECH_FRAGMENT_TARGET:],
            "fragmentCount": len(fragments),
            "fragmentTarget": TRIBE_LOST_TECH_FRAGMENT_TARGET,
            "ready": len(fragments) >= TRIBE_LOST_TECH_FRAGMENT_TARGET,
            "buffs": self._active_lost_tech_buffs(tribe),
            "records": list(tribe.get("lost_tech_records", []) or [])[-TRIBE_LOST_TECH_HISTORY_LIMIT:]
        }

    def _apply_lost_tech_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石材")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                parts.append(f"{label}{amount:+d}")
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
        return parts

    async def record_lost_tech_fragment(self, player_id: str, source_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        source = TRIBE_LOST_TECH_SOURCES.get(source_key)
        if not source:
            await self._send_tribe_error(player_id, "未知技艺来源")
            return
        if not self._lost_tech_source_available(tribe, source_key):
            await self._send_tribe_error(player_id, "当前还没有足够旧事支撑这个技艺来源")
            return

        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_lost_tech_reward(tribe, source)
        fragment = {
            "id": f"lost_tech_fragment_{source_key}_{int(now.timestamp() * 1000)}",
            "sourceKey": source_key,
            "sourceLabel": source.get("label", "技艺来源"),
            "memberId": player_id,
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        tribe.setdefault("lost_tech_fragments", []).append(fragment)
        detail = f"{fragment['memberName']} 记录“{fragment['sourceLabel']}”，失落技艺碎片 {len(self._lost_tech_fragments(tribe))}/{TRIBE_LOST_TECH_FRAGMENT_TARGET}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "culture", "记录失落技艺", detail, player_id, {"kind": "lost_tech_fragment", "fragment": fragment})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def restore_lost_tech(self, player_id: str, tech_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        fragments = self._lost_tech_fragments(tribe)
        if len(fragments) < TRIBE_LOST_TECH_FRAGMENT_TARGET:
            await self._send_tribe_error(player_id, f"至少需要 {TRIBE_LOST_TECH_FRAGMENT_TARGET} 枚技艺碎片")
            return
        tech = TRIBE_LOST_TECH_OPTIONS.get(tech_key)
        if not tech:
            await self._send_tribe_error(player_id, "未知复原技艺")
            return

        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        used_fragments = fragments[:TRIBE_LOST_TECH_FRAGMENT_TARGET]
        tribe["lost_tech_fragments"] = fragments[TRIBE_LOST_TECH_FRAGMENT_TARGET:]
        reward_parts = self._apply_lost_tech_reward(tribe, tech)
        buff = {
            "id": f"lost_tech_buff_{tech_key}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "key": tech_key,
            "label": tech.get("label", "复原技艺"),
            "summary": tech.get("summary", ""),
            "restoredBy": player_id,
            "restoredByName": member.get("name", "成员"),
            "sourceLabels": [item.get("sourceLabel", "旧事") for item in used_fragments],
            "rewardParts": reward_parts,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_LOST_TECH_ACTIVE_MINUTES * 60).isoformat()
        }
        for key in ("buildCostDiscountPercent", "ritualGatherBonus", "tradeReputationBonus", "caveFindsBonus"):
            amount = int(tech.get(key, 0) or 0)
            if amount:
                buff[key] = amount
        tribe.setdefault("lost_tech_buffs", []).append(buff)
        tribe["lost_tech_buffs"] = tribe["lost_tech_buffs"][-TRIBE_LOST_TECH_HISTORY_LIMIT:]
        record = dict(buff)
        tribe.setdefault("lost_tech_records", []).append(record)
        tribe["lost_tech_records"] = tribe["lost_tech_records"][-TRIBE_LOST_TECH_HISTORY_LIMIT:]

        detail = f"{member.get('name', '成员')} 用{'、'.join(buff['sourceLabels'])}复原“{buff['label']}”：{'、'.join(reward_parts) or '短时技艺已生效'}。"
        self._add_tribe_history(tribe, "culture", "复原失落技艺", detail, player_id, {"kind": "lost_tech_restore", "buff": buff})
        await self._publish_world_rumor(
            "culture",
            "失落技艺复原",
            f"{tribe.get('name', '部落')} 从旧事里复原“{buff['label']}”，营地又多了一种短时手艺。",
            {"tribeId": tribe_id, "techKey": tech_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
