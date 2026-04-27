from datetime import datetime

from game_config import *


class GamePersonalOathMixin:
    def _public_personal_dark_oath(self, player: dict) -> dict | None:
        oath = player.get("personal_dark_oath")
        if not isinstance(oath, dict) or oath.get("status") != "hidden":
            return None
        try:
            expired = datetime.fromisoformat(oath.get("activeUntil", "")).timestamp() <= datetime.now().timestamp()
        except (TypeError, ValueError):
            expired = True
        return {
            "id": oath.get("id"),
            "key": oath.get("key"),
            "label": oath.get("label", "个人暗誓"),
            "summary": oath.get("summary", ""),
            "createdAt": oath.get("createdAt"),
            "activeUntil": oath.get("activeUntil"),
            "expired": expired
        }

    def _public_dark_oath_records(self, tribe: dict) -> list:
        return [
            item for item in tribe.get("personal_dark_oath_records", []) or []
            if isinstance(item, dict)
        ][-PLAYER_DARK_OATH_RECORD_LIMIT:]

    def _public_dark_oath_remedies(self, tribe: dict) -> list:
        return [
            item for item in tribe.get("personal_dark_oath_remedies", []) or []
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-PLAYER_DARK_OATH_REMEDY_LIMIT:]

    def _apply_dark_oath_reward(self, tribe: dict, player_id: str, member: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                storage[key] = int(storage.get(key, 0) or 0) + value
                parts.append(f"{label}+{value}")
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
        contribution = int((reward or {}).get("contribution", 0) or 0)
        if contribution and member is not None:
            member["contribution"] = int(member.get("contribution", 0) or 0) + contribution
            parts.append(f"贡献+{contribution}")
        personal = int((reward or {}).get("personalRenown", 0) or 0)
        if personal:
            player = self.players.setdefault(player_id, {})
            player["personal_renown"] = int(player.get("personal_renown", 0) or 0) + personal
            parts.append(f"个人声望+{personal}")
        pressure_relief = int((reward or {}).get("warPressureRelief", 0) or 0)
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

    async def start_personal_dark_oath(self, player_id: str, oath_key: str):
        player = self.players.get(player_id)
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        option = PLAYER_DARK_OATH_OPTIONS.get(oath_key)
        if not player or not tribe:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "请先加入一个部落"})
            return
        if not option:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "未知个人暗誓"})
            return
        if isinstance(player.get("personal_dark_oath"), dict) and player["personal_dark_oath"].get("status") == "hidden":
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "你已经有一条未揭示的个人暗誓"})
            return
        personal_renown = int(player.get("personal_renown", 0) or 0)
        if personal_renown < PLAYER_DARK_OATH_MIN_RENOWN:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": f"个人声望至少需要 {PLAYER_DARK_OATH_MIN_RENOWN} 才能立下暗誓"})
            return
        member = tribe.get("members", {}).get(player_id, {})
        now = datetime.now()
        oath = {
            "id": f"personal_dark_oath_{player_id}_{int(now.timestamp() * 1000)}",
            "status": "hidden",
            "key": oath_key,
            "label": option.get("label", "个人暗誓"),
            "summary": option.get("summary", ""),
            "memberId": player_id,
            "memberName": member.get("name", player.get("name", "成员")),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + PLAYER_DARK_OATH_ACTIVE_MINUTES * 60).isoformat()
        }
        player["personal_dark_oath"] = oath
        await self.send_personal_conflict_status(player_id)
        await self.send_personal_message(player_id, {
            "type": "personal_identity_result",
            "action": "dark_oath",
            "message": f"你在心里立下“{oath['label']}”，可在时限内揭示兑现。",
            "status": self._public_personal_conflict_status(player)
        })

    async def reveal_personal_dark_oath(self, player_id: str):
        player = self.players.get(player_id)
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not player or not tribe:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "请先加入一个部落"})
            return
        oath = player.get("personal_dark_oath")
        if not isinstance(oath, dict) or oath.get("status") != "hidden":
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "当前没有可揭示的个人暗誓"})
            return
        option = PLAYER_DARK_OATH_OPTIONS.get(oath.get("key"), {})
        expired = False
        try:
            expired = datetime.fromisoformat(oath.get("activeUntil", "")).timestamp() <= datetime.now().timestamp()
        except (TypeError, ValueError):
            expired = True
        if expired:
            await self._fail_personal_dark_oath(player_id, tribe_id, tribe, player, oath, option)
            return
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_dark_oath_reward(tribe, player_id, member, option)
        oath["status"] = "fulfilled"
        oath["revealedAt"] = datetime.now().isoformat()
        oath["rewardParts"] = reward_parts
        tribe.setdefault("personal_dark_oath_records", []).append(dict(oath))
        tribe["personal_dark_oath_records"] = tribe["personal_dark_oath_records"][-PLAYER_DARK_OATH_RECORD_LIMIT:]
        player["personal_dark_oath"] = None
        detail = f"{oath.get('memberName', '成员')} 揭示并兑现“{oath.get('label', '个人暗誓')}”：{'、'.join(reward_parts) or '个人名声被记住'}。"
        self._add_tribe_history(tribe, "governance", "个人暗誓兑现", detail, player_id, {"kind": "personal_dark_oath", "oath": oath})
        await self._publish_world_rumor(
            "governance",
            "个人暗誓兑现",
            f"{tribe.get('name', '部落')} 的 {oath.get('memberName', '成员')} 把藏在心里的誓言公开兑现。",
            {"tribeId": tribe_id, "oathId": oath.get("id"), "oathKey": oath.get("key")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.send_personal_conflict_status(player_id)

    async def _fail_personal_dark_oath(self, player_id: str, tribe_id: str, tribe: dict, player: dict, oath: dict, option: dict):
        now = datetime.now()
        player["personal_renown"] = max(0, int(player.get("personal_renown", 0) or 0) - PLAYER_DARK_OATH_FAILURE_PENALTY)
        member = tribe.get("members", {}).get(player_id, {})
        if member:
            member["renown_stains"] = int(member.get("renown_stains", 0) or 0) + 1
        oath["status"] = "failed"
        oath["failedAt"] = now.isoformat()
        remedy = {
            "id": f"dark_oath_remedy_{player_id}_{int(now.timestamp() * 1000)}",
            "status": "pending",
            "oathId": oath.get("id"),
            "memberId": player_id,
            "memberName": oath.get("memberName", member.get("name", "成员")),
            "label": option.get("remedyLabel", "补上暗誓"),
            "summary": option.get("remedySummary", "把没有兑现的暗誓补成公开行动。"),
            "woodCost": int(option.get("remedyWoodCost", 0) or 0),
            "foodCost": int(option.get("remedyFoodCost", 0) or 0),
            "reward": dict(option.get("remedyReward", {}) or {}),
            "createdAt": now.isoformat()
        }
        tribe.setdefault("personal_dark_oath_records", []).append(dict(oath))
        tribe["personal_dark_oath_records"] = tribe["personal_dark_oath_records"][-PLAYER_DARK_OATH_RECORD_LIMIT:]
        tribe.setdefault("personal_dark_oath_remedies", []).append(remedy)
        tribe["personal_dark_oath_remedies"] = tribe["personal_dark_oath_remedies"][-PLAYER_DARK_OATH_REMEDY_LIMIT:]
        player["personal_dark_oath"] = None
        detail = f"{oath.get('memberName', '成员')} 的“{oath.get('label', '个人暗誓')}”错过时限，留下“{remedy['label']}”。"
        self._add_tribe_history(tribe, "governance", "个人暗誓失约", detail, player_id, {"kind": "personal_dark_oath_failed", "oath": oath, "remedy": remedy})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.send_personal_conflict_status(player_id)
        await self.send_personal_message(player_id, {
            "type": "personal_identity_error",
            "message": f"暗誓已失约，留下可补救任务：{remedy['label']}"
        })

    async def complete_personal_dark_oath_remedy(self, player_id: str, remedy_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        remedy = next((item for item in self._public_dark_oath_remedies(tribe) if item.get("id") == remedy_id), None)
        if not remedy:
            await self._send_tribe_error(player_id, "没有找到可补救的个人暗誓")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(remedy.get("woodCost", 0) or 0)
        food_cost = int(remedy.get("foodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, "公共木材不足，无法完成赎誓")
            return
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, "公共食物不足，无法完成赎誓")
            return
        storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_dark_oath_reward(tribe, player_id, member, remedy.get("reward", {}))
        remedy["status"] = "completed"
        remedy["completedBy"] = player_id
        remedy["completedByName"] = member.get("name", "成员")
        remedy["completedAt"] = datetime.now().isoformat()
        remedy["rewardParts"] = reward_parts
        detail = f"{member.get('name', '成员')} 完成“{remedy.get('label', '赎誓')}”，补回{remedy.get('memberName', '成员')}的暗誓缺口：{'、'.join(reward_parts) or '部落承认了补救'}。"
        self._add_tribe_history(tribe, "governance", "个人暗誓补救", detail, player_id, {"kind": "personal_dark_oath_remedy", "remedy": remedy})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.send_personal_conflict_status(player_id)
