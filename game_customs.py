from datetime import datetime

from game_config import *


class GameCustomMixin:
    def _custom_tree_state(self, tribe: dict) -> dict:
        state = tribe.setdefault("custom_tree", {})
        scores = state.setdefault("scores", {})
        for key in TRIBE_CUSTOM_TREE_OPTIONS:
            scores[key] = int(scores.get(key, 0) or 0)
        state.setdefault("records", [])
        state.setdefault("bonus_records", [])
        state.setdefault("practice_marks", [])
        return state

    def _custom_reward_parts(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石材")):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + value)
                parts.append(f"{label}{value:+d}")
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
        pressure_relief = int((reward or {}).get("pressureRelief", 0) or 0)
        if pressure_relief:
            relieved = 0
            for relation in (tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                after = max(0, before - pressure_relief)
                relation["warPressure"] = after
                relation["canDeclareWar"] = after >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                relieved += before - after
            parts.append(f"战争压力-{relieved or pressure_relief}")
        return parts

    def _dominant_custom_key(self, tribe: dict) -> str:
        state = self._custom_tree_state(tribe)
        scores = state.get("scores", {})
        ranked = sorted(scores.items(), key=lambda item: (-int(item[1] or 0), item[0]))
        if not ranked or int(ranked[0][1] or 0) < TRIBE_CUSTOM_TREE_THRESHOLD:
            return ""
        return ranked[0][0]

    def _record_tribe_custom_choice(self, tribe: dict, custom_key: str, source_label: str, player_id: str = "", amount: int = 1) -> dict | None:
        option = TRIBE_CUSTOM_TREE_OPTIONS.get(custom_key)
        if not option:
            return None
        state = self._custom_tree_state(tribe)
        scores = state.setdefault("scores", {})
        before_key = self._dominant_custom_key(tribe)
        scores[custom_key] = int(scores.get(custom_key, 0) or 0) + max(1, int(amount or 1))
        member = (tribe.get("members", {}) or {}).get(player_id, {}) if player_id else {}
        record = {
            "id": f"custom_{custom_key}_{int(datetime.now().timestamp() * 1000)}",
            "key": custom_key,
            "label": option.get("label", "风俗"),
            "sourceLabel": source_label,
            "memberName": member.get("name", "成员") if player_id else "",
            "score": scores[custom_key],
            "createdAt": datetime.now().isoformat()
        }
        state.setdefault("records", []).append(record)
        state["records"] = state["records"][-TRIBE_CUSTOM_TREE_RECENT_LIMIT:]
        after_key = self._dominant_custom_key(tribe)
        if after_key and after_key != before_key:
            state["dominantKey"] = after_key
            record["becameDominant"] = True
        return record

    def _custom_keys_for_event(self, event_key: str) -> list:
        return [
            key for key, option in TRIBE_CUSTOM_TREE_OPTIONS.items()
            if event_key in (option.get("eventKeys") or [])
        ]

    def apply_tribe_custom_event_bonus(self, tribe: dict, event_key: str, source_label: str = "", player_id: str = "") -> list:
        if not tribe:
            return []
        for custom_key in self._custom_keys_for_event(event_key):
            self._record_tribe_custom_choice(tribe, custom_key, source_label or event_key, player_id)
        dominant_key = self._dominant_custom_key(tribe)
        option = TRIBE_CUSTOM_TREE_OPTIONS.get(dominant_key)
        if not option or event_key not in (option.get("eventKeys") or []):
            return []
        reward_parts = self._custom_reward_parts(tribe, option.get("reward", {}))
        if not reward_parts:
            return []
        state = self._custom_tree_state(tribe)
        bonus = {
            "id": f"custom_bonus_{dominant_key}_{int(datetime.now().timestamp() * 1000)}",
            "key": dominant_key,
            "label": option.get("label", "风俗"),
            "sourceLabel": source_label or event_key,
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        state.setdefault("bonus_records", []).append(bonus)
        state["bonus_records"] = state["bonus_records"][-TRIBE_CUSTOM_TREE_BONUS_LIMIT:]
        return [f"{bonus['label']}风俗:{part}" for part in reward_parts]

    def _public_tribe_customs(self, tribe: dict) -> dict:
        state = self._custom_tree_state(tribe)
        dominant_key = self._dominant_custom_key(tribe)
        tendencies = []
        for key, option in TRIBE_CUSTOM_TREE_OPTIONS.items():
            score = int((state.get("scores") or {}).get(key, 0) or 0)
            tendencies.append({
                "key": key,
                "label": option.get("label", "风俗"),
                "summary": option.get("summary", ""),
                "effectSummary": option.get("effectSummary", ""),
                "score": score,
                "target": TRIBE_CUSTOM_TREE_THRESHOLD,
                "active": key == dominant_key
            })
        tendencies.sort(key=lambda item: (-int(item["score"] or 0), item["key"]))
        dominant = next((item for item in tendencies if item["key"] == dominant_key), None)
        return {
            "dominant": dominant,
            "tendencies": tendencies,
            "records": list(state.get("records", []) or [])[-TRIBE_CUSTOM_TREE_RECENT_LIMIT:],
            "bonusRecords": list(state.get("bonus_records", []) or [])[-TRIBE_CUSTOM_TREE_BONUS_LIMIT:],
            "threshold": TRIBE_CUSTOM_TREE_THRESHOLD
        }

    def _public_tribe_custom_options(self, tribe: dict) -> dict:
        return {
            key: {
                "key": key,
                "label": option.get("label", "风俗"),
                "summary": option.get("practiceSummary", option.get("summary", "")),
                "practiceLabel": option.get("practiceLabel", "沉淀风俗"),
                "effectSummary": option.get("effectSummary", "")
            }
            for key, option in TRIBE_CUSTOM_TREE_OPTIONS.items()
        }

    async def commit_tribe_custom_practice(self, player_id: str, custom_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        option = TRIBE_CUSTOM_TREE_OPTIONS.get(custom_key)
        if not option:
            await self._send_tribe_error(player_id, "未知部落风俗")
            return
        state = self._custom_tree_state(tribe)
        mark = f"{player_id}:{custom_key}"
        if mark in (state.get("practice_marks", []) or []):
            await self._send_tribe_error(player_id, "你已经为这条风俗留下过一次实践")
            return
        state.setdefault("practice_marks", []).append(mark)
        member = tribe.get("members", {}).get(player_id, {})
        record = self._record_tribe_custom_choice(tribe, custom_key, option.get("practiceLabel", "沉淀风俗"), player_id)
        reward_parts = self._custom_reward_parts(tribe, {"renown": 1})
        detail = f"{member.get('name', '成员')} 选择“{option.get('practiceLabel', '沉淀风俗')}”，让部落的“{option.get('label', '风俗')}”倾向更清晰。{'、'.join(reward_parts)}。"
        if record and record.get("becameDominant"):
            detail += f" “{option.get('label', '风俗')}”成为当前主导风俗。"
            await self._publish_world_rumor(
                "governance",
                "部落风俗成形",
                f"{tribe.get('name', '部落')} 的长期选择沉淀成“{option.get('label', '风俗')}”，后来事件开始按这套规矩被讲述。",
                {"tribeId": tribe_id, "customKey": custom_key}
            )
        self._add_tribe_history(tribe, "governance", "部落风俗树", detail, player_id, {"kind": "tribe_custom", "customKey": custom_key, "record": record, "rewardParts": reward_parts})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
