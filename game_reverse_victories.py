from datetime import datetime

from game_config import *


class GameReverseVictoryMixin:
    def _recent_reverse_victory_records(self, tribe: dict) -> list:
        return [item for item in (tribe.get("reverse_victory_records", []) or []) if isinstance(item, dict)][-TRIBE_REVERSE_VICTORY_RECORD_LIMIT:]

    def _reverse_victory_cooldown_active(self, tribe: dict, target_key: str) -> bool:
        now = datetime.now()
        for record in reversed(tribe.get("reverse_victory_records", []) or []):
            if not isinstance(record, dict) or record.get("targetKey") != target_key:
                continue
            try:
                elapsed = (now - datetime.fromisoformat(record.get("createdAt", ""))).total_seconds()
            except (TypeError, ValueError):
                return False
            return elapsed < TRIBE_REVERSE_VICTORY_COOLDOWN_MINUTES * 60
        return False

    def _reverse_victory_pressure_context(self, tribe: dict) -> dict | None:
        relations = []
        for other_id, relation in (tribe.get("boundary_relations", {}) or {}).items():
            if not isinstance(relation, dict):
                continue
            pressure = int(relation.get("warPressure", 0) or 0)
            score = int(relation.get("score", 0) or 0)
            if pressure > 0 or score <= -4:
                other = self.tribes.get(other_id, {}) if hasattr(self, "tribes") else {}
                relations.append({
                    "otherTribeId": other_id,
                    "otherTribeName": other.get("name", "边界另一侧"),
                    "warPressure": pressure,
                    "score": score
                })
        if not relations:
            return None
        return sorted(relations, key=lambda item: (item.get("warPressure", 0), -item.get("score", 0)), reverse=True)[0]

    def _reverse_victory_mediation_context(self, tribe: dict) -> dict | None:
        relations = []
        for other_id, relation in (tribe.get("boundary_relations", {}) or {}).items():
            if not isinstance(relation, dict):
                continue
            score = int(relation.get("score", 0) or 0)
            trust = int(relation.get("tradeTrust", 0) or 0)
            if -5 <= score <= 0 or (score < 2 and trust <= 1):
                other = self.tribes.get(other_id, {}) if hasattr(self, "tribes") else {}
                relations.append({
                    "otherTribeId": other_id,
                    "otherTribeName": other.get("name", "可调停部落"),
                    "score": score,
                    "tradeTrust": trust
                })
        if not relations:
            return None
        return sorted(relations, key=lambda item: (item.get("score", 0), -item.get("tradeTrust", 0)))[0]

    def _reverse_victory_rescue_context(self, tribe: dict) -> dict | None:
        for race in self._active_cave_races(tribe) if hasattr(self, "_active_cave_races") else []:
            rescue = race.get("rescue") or {}
            if race.get("status") == "rescue" and rescue.get("status") == "missing":
                return {
                    "raceId": race.get("id"),
                    "caveLabel": race.get("caveLabel", "洞穴"),
                    "missingMemberName": rescue.get("missingMemberName", "失踪者"),
                    "progress": int(rescue.get("progress", 0) or 0),
                    "target": int(rescue.get("target", 1) or 1)
                }
        return None

    def _reverse_victory_fire_context(self, tribe: dict) -> dict | None:
        low_food = int(tribe.get("food", 0) or 0) <= 4
        low_renown = int(tribe.get("renown", 0) or 0) <= 8
        has_campfire = self._has_tribe_structure_type(tribe, "campfire") if hasattr(self, "_has_tribe_structure_type") else False
        if not has_campfire or not (low_food or low_renown or tribe.get("sacred_fire_relay")):
            return None
        return {
            "lowFood": low_food,
            "lowRenown": low_renown,
            "hasSacredFire": bool(tribe.get("sacred_fire_relay")),
            "food": int(tribe.get("food", 0) or 0),
            "renown": int(tribe.get("renown", 0) or 0)
        }

    def _public_reverse_victory_targets(self, tribe: dict) -> list:
        checks = {
            "hold_border": self._reverse_victory_pressure_context,
            "rescue_missing": self._reverse_victory_rescue_context,
            "mediate": self._reverse_victory_mediation_context,
            "preserve_fire": self._reverse_victory_fire_context
        }
        targets = []
        for key, resolver in checks.items():
            config = TRIBE_REVERSE_VICTORY_TARGETS.get(key, {})
            context = resolver(tribe)
            available = bool(context) and not self._reverse_victory_cooldown_active(tribe, key)
            targets.append({
                "key": key,
                "label": config.get("label", key),
                "summary": config.get("summary", ""),
                "available": available,
                "context": context,
                "rewardLabel": self._reverse_victory_reward_label(config),
                "lockedReason": "" if available else ("刚刚完成过，需要等余波沉淀" if context else "还没有对应的弱势局面")
            })
        return targets

    def _reverse_victory_reward_label(self, reward: dict) -> str:
        parts = []
        for key, label in (("renown", "声望"), ("food", "食物"), ("discoveryProgress", "发现"), ("tradeReputation", "贸易信誉"), ("pressureRelief", "战争压力"), ("relationDelta", "关系"), ("tradeTrustDelta", "信任")):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                sign = "-" if key == "pressureRelief" else "+"
                parts.append(f"{label}{sign}{value}")
        return " / ".join(parts)

    def _apply_reverse_victory_reward(self, tribe: dict, target_key: str, context: dict | None) -> list:
        config = TRIBE_REVERSE_VICTORY_TARGETS.get(target_key, {})
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("food", "食物", "food"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("tradeReputation", "贸易信誉", "trade_reputation")
        ):
            value = int(config.get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        relation_id = (context or {}).get("otherTribeId")
        if relation_id:
            relation = tribe.setdefault("boundary_relations", {}).setdefault(relation_id, {})
            pressure_relief = int(config.get("pressureRelief", 0) or 0)
            if pressure_relief:
                relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                parts.append(f"战争压力-{pressure_relief}")
            relation_delta = int(config.get("relationDelta", 0) or 0)
            trust_delta = int(config.get("tradeTrustDelta", 0) or 0)
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
                parts.append(f"关系{relation_delta:+d}")
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
                parts.append(f"信任+{trust_delta}")
            relation["lastAction"] = f"reverse_victory_{target_key}"
            relation["lastActionAt"] = datetime.now().isoformat()
            other = self.tribes.get(relation_id) if hasattr(self, "tribes") else None
            if other and tribe.get("id"):
                other_relation = other.setdefault("boundary_relations", {}).setdefault(tribe.get("id"), {})
                if pressure_relief:
                    other_relation["warPressure"] = max(0, int(other_relation.get("warPressure", 0) or 0) - pressure_relief)
                    other_relation["canDeclareWar"] = int(other_relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                if relation_delta:
                    other_relation["score"] = max(-9, min(9, int(other_relation.get("score", 0) or 0) + relation_delta))
                if trust_delta:
                    other_relation["tradeTrust"] = max(0, min(10, int(other_relation.get("tradeTrust", 0) or 0) + trust_delta))
                other_relation["lastAction"] = f"incoming_reverse_victory_{target_key}"
                other_relation["lastActionAt"] = relation["lastActionAt"]
        return parts

    async def complete_reverse_victory(self, player_id: str, target_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        target = next((item for item in self._public_reverse_victory_targets(tribe) if item.get("key") == target_key), None)
        if not target or not target.get("available"):
            await self._send_tribe_error(player_id, target.get("lockedReason", "当前没有这个反向胜利机会") if target else "未知反向胜利目标")
            return
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_reverse_victory_reward(tribe, target_key, target.get("context"))
        record = {
            "id": f"reverse_victory_{tribe_id}_{target_key}_{int(datetime.now().timestamp() * 1000)}",
            "targetKey": target_key,
            "label": target.get("label", "反向胜利"),
            "summary": target.get("summary", ""),
            "memberName": member.get("name", "成员"),
            "context": target.get("context"),
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("reverse_victory_records", []).append(record)
        tribe["reverse_victory_records"] = tribe["reverse_victory_records"][-TRIBE_REVERSE_VICTORY_RECORD_LIMIT:]
        self.players.setdefault(player_id, {})["personal_renown"] = int(self.players.get(player_id, {}).get("personal_renown", 0) or 0) + 1
        detail = f"{record['memberName']} 完成“{record['label']}”：{record['summary']} {'、'.join(reward_parts) or '部落把弱势讲成荣耀'}。"
        self._add_tribe_history(tribe, "ritual", "反向胜利", detail, player_id, {"kind": "reverse_victory", "record": record})
        await self._publish_world_rumor(
            "ritual",
            "反向胜利",
            f"{tribe.get('name', '部落')} 在弱势中完成“{record['label']}”，把退路变成了荣耀。",
            {"tribeId": tribe_id, "targetKey": target_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
