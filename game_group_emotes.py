from datetime import datetime

from game_config import *


class GameGroupEmoteMixin:
    def _public_group_emote_records(self, tribe: dict) -> list:
        return list(tribe.get("group_emote_records", []) or [])[-TRIBE_GROUP_EMOTE_HISTORY_LIMIT:]

    def _apply_group_emote_reward(self, tribe: dict, action: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石材")):
            value = int(action.get(key, 0) or 0)
            if value:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + value)
                parts.append(f"{label}{value:+d}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            value = int(action.get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        return parts

    def _apply_group_emote_pressure_relief(self, tribe: dict, amount: int) -> int:
        if amount <= 0:
            return 0
        relieved = 0
        for relation in (tribe.get("boundary_relations", {}) or {}).values():
            if not isinstance(relation, dict):
                continue
            before = int(relation.get("warPressure", 0) or 0)
            if before <= 0:
                continue
            after = max(0, before - amount)
            relation["warPressure"] = after
            relation["canDeclareWar"] = after >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relieved += before - after
        return relieved

    async def perform_group_emote(self, player_id: str, emote_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_GROUP_EMOTE_ACTIONS.get(emote_key)
        if not action:
            await self._send_tribe_error(player_id, "未知群体动作")
            return

        now = datetime.now()
        cooldowns = tribe.setdefault("group_emote_cooldowns", {})
        last_text = cooldowns.get(player_id)
        if last_text:
            try:
                elapsed = (now - datetime.fromisoformat(last_text)).total_seconds()
                if elapsed < TRIBE_GROUP_EMOTE_COOLDOWN_SECONDS:
                    remaining = int(TRIBE_GROUP_EMOTE_COOLDOWN_SECONDS - elapsed)
                    await self._send_tribe_error(player_id, f"先让动作余韵沉一下，还需 {remaining} 秒")
                    return
            except (TypeError, ValueError):
                pass

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        food_cost = int(action.get("foodCost", 0) or 0)
        wood_cost = int(action.get("woodCost", 0) or 0)
        stone_cost = int(action.get("stoneCost", 0) or 0)
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"{action.get('label', '群体动作')}需要公共食物{food_cost}")
            return
        if int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"{action.get('label', '群体动作')}需要公共木材{wood_cost}")
            return
        if int(storage.get("stone", 0) or 0) < stone_cost:
            await self._send_tribe_error(player_id, f"{action.get('label', '群体动作')}需要公共石块{stone_cost}")
            return

        tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        storage["stone"] = int(storage.get("stone", 0) or 0) - stone_cost
        cooldowns[player_id] = now.isoformat()

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        reward_parts = self._apply_group_emote_reward(tribe, action)
        reward_parts.extend(self.apply_tribe_custom_event_bonus(tribe, "group_emote", action.get("label", "群体动作"), player_id))
        pressure_relief = self._apply_group_emote_pressure_relief(tribe, int(action.get("pressureRelief", 0) or 0))
        if pressure_relief:
            reward_parts.append(f"战争压力-{pressure_relief}")
        personal_renown = int(action.get("personalRenown", 0) or 0)
        if personal_renown:
            self.players.setdefault(player_id, {})["personal_renown"] = int(self.players.get(player_id, {}).get("personal_renown", 0) or 0) + personal_renown
            reward_parts.append(f"个人声望+{personal_renown}")

        record = {
            "id": f"group_emote_{emote_key}_{int(now.timestamp() * 1000)}",
            "key": emote_key,
            "label": action.get("label", "群体动作"),
            "summary": action.get("summary", ""),
            "memberName": member_name,
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        tribe.setdefault("group_emote_records", []).append(record)
        tribe["group_emote_records"] = tribe["group_emote_records"][-TRIBE_GROUP_EMOTE_HISTORY_LIMIT:]

        detail = f"{member_name} 发起“{record['label']}”，{action.get('summary', '营地短暂聚在一起')}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "ritual", "群体表情动作", detail, player_id, {"kind": "group_emote", **record})
        if pressure_relief or int(action.get("renown", 0) or 0) >= 2:
            await self._publish_world_rumor(
                "ritual",
                record["label"],
                f"{tribe.get('name', '部落')} 用“{record['label']}”把营地情绪公开地放进了共同记忆。",
                {"tribeId": tribe_id, "emoteKey": emote_key}
            )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
