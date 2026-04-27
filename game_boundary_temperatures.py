from datetime import datetime

from game_config import *


class GameBoundaryTemperatureMixin:
    def _boundary_temperature_label(self, relation: dict) -> dict:
        score = int(relation.get("score", 0) or 0)
        trust = int(relation.get("tradeTrust", 0) or 0)
        pressure = int(relation.get("warPressure", 0) or 0)
        explicit = relation.get("temperatureTone")
        if explicit == "warm":
            return {"key": "warm", "label": "热络", "summary": "这条边界正在被讲成互市、援助和来往频繁的口风。"}
        if explicit == "awe":
            return {"key": "awe", "label": "敬畏", "summary": "双方都看见了对方的守边威望，冲突不必立刻爆发。"}
        if explicit == "cool":
            return {"key": "cool", "label": "冷淡", "summary": "这条边界暂时降温，口风克制但仍保持距离。"}
        if pressure >= 3 or score <= -5:
            return {"key": "suspicious", "label": "猜疑", "summary": "旧怨和压力让这条边界容易把传闻讲坏。"}
        if pressure > 0 or score < 0:
            return {"key": "cold", "label": "冷淡", "summary": "双方仍有戒心，外交动作会显得谨慎。"}
        if trust >= 5 or score >= 5:
            return {"key": "warm", "label": "热络", "summary": "贸易信任和善意让这条边界更容易被讲成好消息。"}
        if trust >= 2 or score >= 2:
            return {"key": "open", "label": "松动", "summary": "这条边界开始能谈，但还没有完全热起来。"}
        return {"key": "quiet", "label": "平静", "summary": "这条边界暂时没有强烈口风。"}

    def _boundary_temperature_suggestion(self, temperature_key: str) -> dict:
        suggestions = {
            "warm": {"actionKey": "warm_words", "label": "趁热互市", "effectHint": "外交、信使和互助更容易沉淀贸易信誉。"},
            "open": {"actionKey": "warm_words", "label": "续上口风", "effectHint": "公开往来会额外提高一点信任。"},
            "suspicious": {"actionKey": "clear_suspicion", "label": "先澄清猜疑", "effectHint": "互助或信使会优先削减战争压力。"},
            "cold": {"actionKey": "clear_suspicion", "label": "慢慢解冻", "effectHint": "外交结果会偏向关系修复。"},
            "awe": {"actionKey": "awe_watch", "label": "以敬畏守望", "effectHint": "守边类公开行动会额外稳定压力。"},
            "cool": {"actionKey": "cool_mark", "label": "保持冷处理", "effectHint": "公开传闻会更克制，减少误判。"}
        }
        return suggestions.get(temperature_key, {"actionKey": "warm_words", "label": "观察口风", "effectHint": "暂无额外倾向。"})

    def _temperature_relation(self, tribe: dict, other_tribe_id: str) -> dict:
        return tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})

    def _apply_boundary_temperature_channel_bonus(self, tribe: dict, other_tribe_id: str, channel: str) -> list:
        if not tribe or not other_tribe_id:
            return []
        relation = self._temperature_relation(tribe, other_tribe_id)
        temp = self._boundary_temperature_label(relation)
        key = temp.get("key")
        parts = []
        if channel in ("diplomacy", "messenger", "mutual_aid"):
            if key in ("warm", "open"):
                if channel == "diplomacy":
                    tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + 1
                    parts.append(f"{temp.get('label')}口风贸易信誉+1")
                else:
                    relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + 1))
                    parts.append(f"{temp.get('label')}口风信任+1")
            elif key in ("suspicious", "cold", "cool"):
                before = int(relation.get("warPressure", 0) or 0)
                relation["warPressure"] = max(0, before - 1)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                if before != int(relation.get("warPressure", 0) or 0):
                    parts.append(f"{temp.get('label')}口风战争压力-1")
                elif channel != "diplomacy":
                    relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + 1))
                    parts.append(f"{temp.get('label')}口风关系+1")
            elif key == "awe":
                tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
                parts.append("敬畏口风声望+1")
        if parts:
            relation["lastTemperatureBonus"] = {
                "channel": channel,
                "temperatureKey": key,
                "temperatureLabel": temp.get("label"),
                "rewardParts": parts,
                "createdAt": datetime.now().isoformat()
            }
        return parts

    def _boundary_temperature_rumor_text(self, text: str, related: dict | None = None) -> tuple[str, dict]:
        related = dict(related or {})
        tribe_id = related.get("tribeId")
        other_id = related.get("otherTribeId") or related.get("targetTribeId") or related.get("sourceTribeId")
        tribe = self.tribes.get(tribe_id) if tribe_id and hasattr(self, "tribes") else None
        if not tribe or not other_id:
            return text, related
        relation = (tribe.get("boundary_relations", {}) or {}).get(other_id)
        if not isinstance(relation, dict):
            return text, related
        temp = self._boundary_temperature_label(relation)
        key = temp.get("key")
        phrase = {
            "warm": "热络口风把这条消息讲得更像互市佳讯。",
            "open": "松动口风让这条消息更容易被双方接住。",
            "suspicious": "猜疑口风让这条消息带着试探意味。",
            "cold": "冷淡口风让这条消息显得克制谨慎。",
            "cool": "冷处理口风压低了这条消息里的火气。",
            "awe": "敬畏口风让这条消息多了一层守边分量。"
        }.get(key, "")
        if not phrase:
            return text, related
        related["boundaryTemperature"] = {"key": key, "label": temp.get("label")}
        return f"{text} {phrase}", related

    def _public_boundary_temperatures(self, tribe: dict) -> list:
        if not tribe:
            return []
        items = []
        for other_id, relation in (tribe.get("boundary_relations", {}) or {}).items():
            if not isinstance(relation, dict):
                continue
            other = self.tribes.get(other_id) if hasattr(self, "tribes") else None
            temp = self._boundary_temperature_label(relation)
            items.append({
                "otherTribeId": other_id,
                "otherTribeName": (other or {}).get("name", relation.get("otherTribeName", "邻近部落")),
                "temperatureKey": temp["key"],
                "temperatureLabel": temp["label"],
                "summary": temp["summary"],
                "suggestedAction": self._boundary_temperature_suggestion(temp["key"]),
                "score": int(relation.get("score", 0) or 0),
                "tradeTrust": int(relation.get("tradeTrust", 0) or 0),
                "warPressure": int(relation.get("warPressure", 0) or 0),
                "lastAction": relation.get("lastAction", ""),
                "lastActionAt": relation.get("lastActionAt", ""),
                "lastTemperatureAction": relation.get("lastTemperatureAction", "")
            })
        order = {"suspicious": 0, "cold": 1, "cool": 2, "quiet": 3, "open": 4, "warm": 5, "awe": 6}
        items.sort(key=lambda item: (order.get(item.get("temperatureKey"), 9), -abs(item.get("score", 0))))
        return items

    def _public_boundary_temperature_records(self, tribe: dict) -> list:
        return list(tribe.get("boundary_temperature_records", []) or [])[-TRIBE_BOUNDARY_TEMPERATURE_RECENT_LIMIT:]

    def _apply_boundary_temperature_reward(self, tribe: dict, relation: dict, action: dict) -> list:
        parts = []
        food_cost = int(action.get("foodCost", 0) or 0)
        if food_cost:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) - food_cost)
            parts.append(f"食物-{food_cost}")
        renown = int(action.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            parts.append(f"声望+{renown}")
        trade = int(action.get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            parts.append(f"贸易信誉+{trade}")
        relation_delta = int(action.get("relationDelta", 0) or 0)
        if relation_delta:
            relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            parts.append(f"关系{relation_delta:+d}")
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        if trust_delta:
            relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            parts.append(f"信任{trust_delta:+d}")
        pressure_relief = int(action.get("warPressureRelief", 0) or 0)
        if pressure_relief:
            before = int(relation.get("warPressure", 0) or 0)
            relation["warPressure"] = max(0, before - pressure_relief)
            relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            if before != int(relation.get("warPressure", 0) or 0):
                parts.append(f"战争压力-{before - int(relation.get('warPressure', 0) or 0)}")
        relation["temperatureTone"] = action.get("tone", relation.get("temperatureTone", ""))
        return parts

    async def tune_boundary_temperature(self, player_id: str, other_tribe_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not other_tribe_id or other_tribe_id == tribe_id or other_tribe_id not in self.tribes:
            await self._send_tribe_error(player_id, "没有找到可整理口风的边界")
            return
        action = TRIBE_BOUNDARY_TEMPERATURE_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知边界口风动作")
            return
        food_cost = int(action.get("foodCost", 0) or 0)
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"整理边界口风需要公共食物 {food_cost}")
            return
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        other = self.tribes.get(other_tribe_id, {})
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        now_text = datetime.now().isoformat()
        reward_parts = self._apply_boundary_temperature_reward(tribe, relation, action)
        relation["lastTemperatureAction"] = action_key
        relation["lastAction"] = f"boundary_temperature_{action_key}"
        relation["lastActionAt"] = now_text
        temp = self._boundary_temperature_label(relation)
        record = {
            "id": f"boundary_temperature_{tribe_id}_{other_tribe_id}_{int(datetime.now().timestamp() * 1000)}",
            "otherTribeId": other_tribe_id,
            "otherTribeName": other.get("name", "邻近部落"),
            "actionKey": action_key,
            "actionLabel": action.get("label", "整理口风"),
            "temperatureLabel": temp.get("label", "平静"),
            "memberName": member_name,
            "rewardParts": reward_parts,
            "createdAt": now_text
        }
        tribe.setdefault("boundary_temperature_records", []).append(record)
        tribe["boundary_temperature_records"] = tribe["boundary_temperature_records"][-TRIBE_BOUNDARY_TEMPERATURE_RECENT_LIMIT:]
        detail = f"{member_name} 为与 {record['otherTribeName']} 的边界整理口风为“{temp['label']}”：{'、'.join(reward_parts) or '传闻语气改变'}。"
        self._add_tribe_history(tribe, "diplomacy", "边界温度", detail, player_id, {"kind": "boundary_temperature", "record": record})
        await self._publish_world_rumor(
            "diplomacy",
            "边界温度",
            f"{tribe.get('name', '部落')} 与 {record['otherTribeName']} 的边界被讲成“{temp['label']}”，新的外交口风开始扩散。",
            {"tribeId": tribe_id, "otherTribeId": other_tribe_id, "temperature": temp.get("key"), "action": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
