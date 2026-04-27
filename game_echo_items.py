from datetime import datetime
import random

from game_config import *


class GameEchoItemMixin:
    def _public_echo_items(self, tribe: dict) -> list:
        return [item for item in (tribe.get("echo_items", []) or []) if isinstance(item, dict)][-TRIBE_ECHO_ITEM_LIMIT:]

    def _public_echo_item_records(self, tribe: dict) -> list:
        return [item for item in (tribe.get("echo_item_records", []) or []) if isinstance(item, dict)][-TRIBE_ECHO_ITEM_HISTORY_LIMIT:]

    def _echo_item_by_id(self, tribe: dict, item_id: str) -> dict | None:
        return next((item for item in (tribe.get("echo_items", []) or []) if isinstance(item, dict) and item.get("id") == item_id), None)

    def _apply_echo_item_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("food", "食物", "food")
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
                if before <= 0:
                    continue
                after = max(0, before - pressure_relief)
                relation["warPressure"] = after
                relation["canDeclareWar"] = after >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                relieved += before - after
            if relieved:
                parts.append(f"战争压力-{relieved}")
        return parts

    async def create_echo_item(self, player_id: str, item_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        config = TRIBE_ECHO_ITEM_TYPES.get(item_key)
        if not config:
            await self._send_tribe_error(player_id, "未知回声物品")
            return
        active_items = self._public_echo_items(tribe)
        if len(active_items) >= TRIBE_ECHO_ITEM_LIMIT:
            await self._send_tribe_error(player_id, "部落可流转的回声物品已经太多")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(config.get("woodCost", 0) or 0)
        stone_cost = int(config.get("stoneCost", 0) or 0)
        if int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"{config.get('label', '回声物品')}需要公共木材{wood_cost}")
            return
        if int(storage.get("stone", 0) or 0) < stone_cost:
            await self._send_tribe_error(player_id, f"{config.get('label', '回声物品')}需要公共石材{stone_cost}")
            return
        storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        storage["stone"] = int(storage.get("stone", 0) or 0) - stone_cost

        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        item = {
            "id": f"echo_item_{tribe_id}_{item_key}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "key": item_key,
            "label": config.get("label", "回声物品"),
            "summary": config.get("summary", ""),
            "originLabel": config.get("originLabel", "营地旧物"),
            "holderId": player_id,
            "holderName": member.get("name", "成员"),
            "createdBy": player_id,
            "createdByName": member.get("name", "成员"),
            "createdAt": now.isoformat(),
            "memories": [],
            "transfers": []
        }
        tribe.setdefault("echo_items", []).append(item)
        tribe["echo_items"] = tribe["echo_items"][-TRIBE_ECHO_ITEM_LIMIT:]
        detail = f"{item['createdByName']} 做成“{item['label']}”，它会记录之后的经历与转手来历。"
        self._add_tribe_history(tribe, "ritual", "回声物品成形", detail, player_id, {"kind": "echo_item_create", "item": item})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def add_echo_item_memory(self, player_id: str, item_id: str, experience_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        item = self._echo_item_by_id(tribe, item_id)
        if not item:
            await self._send_tribe_error(player_id, "找不到这件回声物品")
            return
        if item.get("holderId") != player_id:
            await self._send_tribe_error(player_id, "只有当前持有人能为物品记录经历")
            return
        experience = TRIBE_ECHO_ITEM_EXPERIENCES.get(experience_key)
        if not experience:
            await self._send_tribe_error(player_id, "未知物品经历")
            return
        memories = item.setdefault("memories", [])
        if len(memories) >= TRIBE_ECHO_ITEM_MEMORY_LIMIT:
            await self._send_tribe_error(player_id, "这件物品的回声已经足够厚重，可以先挂上收藏墙")
            return
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_echo_item_reward(tribe, experience)
        memory = {
            "id": f"echo_memory_{experience_key}_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "experienceKey": experience_key,
            "experienceLabel": experience.get("label", "经历"),
            "summary": experience.get("summary", ""),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        memories.append(memory)
        item["memories"] = memories[-TRIBE_ECHO_ITEM_MEMORY_LIMIT:]
        item["lastMemoryLabel"] = memory["experienceLabel"]
        item["updatedAt"] = memory["createdAt"]
        self.players.setdefault(player_id, {})["personal_renown"] = int(self.players.get(player_id, {}).get("personal_renown", 0) or 0) + 1
        detail = f"{memory['memberName']} 给“{item.get('label', '回声物品')}”记下{memory['experienceLabel']}。{'、'.join(reward_parts) or '物品来历更清楚了'}。"
        self._add_tribe_history(tribe, "ritual", "回声物品记忆", detail, player_id, {"kind": "echo_item_memory", "itemId": item_id, "memory": memory})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def transfer_echo_item(self, player_id: str, item_id: str, target_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        item = self._echo_item_by_id(tribe, item_id)
        if not item:
            await self._send_tribe_error(player_id, "找不到这件回声物品")
            return
        if item.get("holderId") != player_id:
            await self._send_tribe_error(player_id, "只有当前持有人能转交物品")
            return
        if target_id not in (tribe.get("members", {}) or {}) or target_id == player_id:
            await self._send_tribe_error(player_id, "请选择同部落的另一名成员")
            return
        source = tribe.get("members", {}).get(player_id, {})
        target = tribe.get("members", {}).get(target_id, {})
        transfer = {
            "fromId": player_id,
            "fromName": source.get("name", "成员"),
            "toId": target_id,
            "toName": target.get("name", "成员"),
            "createdAt": datetime.now().isoformat()
        }
        item.setdefault("transfers", []).append(transfer)
        item["transfers"] = item["transfers"][-TRIBE_ECHO_ITEM_HISTORY_LIMIT:]
        item["holderId"] = target_id
        item["holderName"] = transfer["toName"]
        item["updatedAt"] = transfer["createdAt"]
        record = {
            "id": f"echo_transfer_{item_id}_{int(datetime.now().timestamp() * 1000)}",
            "itemId": item_id,
            "itemLabel": item.get("label", "回声物品"),
            **transfer
        }
        tribe.setdefault("echo_item_records", []).append(record)
        tribe["echo_item_records"] = tribe["echo_item_records"][-TRIBE_ECHO_ITEM_HISTORY_LIMIT:]
        detail = f"{transfer['fromName']} 把“{item.get('label', '回声物品')}”传给 {transfer['toName']}，来历也一起转手。"
        self._add_tribe_history(tribe, "ritual", "回声物品转手", detail, player_id, {"kind": "echo_item_transfer", "record": record})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
