from datetime import datetime

from game_config import *


class GameSeasonTabooMixin:
    def _active_season_taboo(self, tribe: dict) -> dict | None:
        taboo = tribe.get("season_taboo")
        if not isinstance(taboo, dict) or taboo.get("status") != "active":
            return None
        try:
            if datetime.fromisoformat(taboo.get("activeUntil", "")) <= datetime.now():
                taboo["status"] = "expired"
                taboo["expiredAt"] = datetime.now().isoformat()
                return None
        except (TypeError, ValueError):
            taboo["status"] = "expired"
            taboo["expiredAt"] = datetime.now().isoformat()
            return None
        return taboo

    def _public_season_taboo(self, tribe: dict) -> dict | None:
        taboo = self._active_season_taboo(tribe)
        if not taboo:
            return None
        config = TRIBE_SEASON_TABOO_OPTIONS.get(taboo.get("key"), {})
        return {
            "id": taboo.get("id"),
            "key": taboo.get("key"),
            "label": taboo.get("label") or config.get("label", "季节禁忌"),
            "summary": taboo.get("summary") or config.get("summary", ""),
            "observeLabel": config.get("observeLabel", "践行禁忌"),
            "breakLabel": config.get("breakLabel", "破戒取急用"),
            "progress": int(taboo.get("progress", 0) or 0),
            "target": int(taboo.get("target", TRIBE_SEASON_TABOO_PROGRESS_TARGET) or TRIBE_SEASON_TABOO_PROGRESS_TARGET),
            "observerNames": list(taboo.get("observerNames", []) or [])[-4:],
            "blessed": bool(taboo.get("blessed")),
            "broken": bool(taboo.get("broken")),
            "createdAt": taboo.get("createdAt"),
            "activeUntil": taboo.get("activeUntil")
        }

    def _public_season_taboo_remedies(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("season_taboo_remedies", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-TRIBE_SEASON_TABOO_REMEDY_LIMIT:]

    def _apply_season_taboo_reward(self, tribe: dict, reward: dict) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood = int(reward.get("wood", 0) or 0)
        if wood:
            storage["wood"] = max(0, int(storage.get("wood", 0) or 0) + wood)
            reward_parts.append(f"木材{wood:+d}")
        wood_cost = int(reward.get("woodCost", 0) or 0)
        if wood_cost:
            storage["wood"] = max(0, int(storage.get("wood", 0) or 0) - wood_cost)
            reward_parts.append(f"木材-{wood_cost}")
        stone = int(reward.get("stone", 0) or 0)
        if stone:
            storage["stone"] = max(0, int(storage.get("stone", 0) or 0) + stone)
            reward_parts.append(f"石块{stone:+d}")
        stone_cost = int(reward.get("stoneCost", 0) or 0)
        if stone_cost:
            storage["stone"] = max(0, int(storage.get("stone", 0) or 0) - stone_cost)
            reward_parts.append(f"石块-{stone_cost}")
        food_cost = int(reward.get("foodCost", 0) or 0)
        if food_cost:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) - food_cost)
            reward_parts.append(f"食物-{food_cost}")
        food = int(reward.get("food", reward.get("foodReward", 0)) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        discovery = int(reward.get("discoveryProgress", reward.get("discoveryReward", 0)) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        renown = int(reward.get("renown", reward.get("renownReward", 0)) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        trade = int(reward.get("tradeReputation", reward.get("tradeReward", 0)) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        return reward_parts

    async def choose_season_taboo(self, player_id: str, taboo_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以宣布季节禁忌")
            return
        if self._active_season_taboo(tribe):
            await self._send_tribe_error(player_id, "当前季节禁忌仍在持续")
            return
        config = TRIBE_SEASON_TABOO_OPTIONS.get(taboo_key)
        if not config:
            await self._send_tribe_error(player_id, "未知季节禁忌")
            return

        now = datetime.now()
        taboo = {
            "id": f"season_taboo_{tribe_id}_{int(now.timestamp() * 1000)}",
            "key": taboo_key,
            "label": config.get("label", "季节禁忌"),
            "summary": config.get("summary", ""),
            "status": "active",
            "progress": 0,
            "target": TRIBE_SEASON_TABOO_PROGRESS_TARGET,
            "observerIds": [],
            "observerNames": [],
            "createdBy": player_id,
            "createdByName": member.get("name", "管理者"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_SEASON_TABOO_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["season_taboo"] = taboo
        tribe.setdefault("season_taboo_history", []).append(taboo)
        tribe["season_taboo_history"] = tribe["season_taboo_history"][-TRIBE_SEASON_TABOO_LIMIT:]
        detail = f"{member.get('name', '管理者')} 宣布{taboo['label']}：{taboo['summary']} 成员可以践行禁忌累积祝福，也可以公开破戒换取急用资源。"
        self._add_tribe_history(tribe, "ritual", "宣布季节禁忌", detail, player_id, {"kind": "season_taboo", "taboo": taboo})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def observe_season_taboo(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        taboo = self._active_season_taboo(tribe)
        if not taboo:
            await self._send_tribe_error(player_id, "当前没有可践行的季节禁忌")
            return
        if player_id in (taboo.get("observerIds", []) or []):
            await self._send_tribe_error(player_id, "你已经践行过这条季节禁忌")
            return
        config = TRIBE_SEASON_TABOO_OPTIONS.get(taboo.get("key"), {})
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        taboo.setdefault("observerIds", []).append(player_id)
        taboo.setdefault("observerNames", []).append(member_name)
        taboo["progress"] = int(taboo.get("progress", 0) or 0) + 1
        reward_parts = self._apply_season_taboo_reward(tribe, config.get("observeReward", {}))
        blessed_now = False
        if not taboo.get("blessed") and int(taboo.get("progress", 0) or 0) >= int(taboo.get("target", TRIBE_SEASON_TABOO_PROGRESS_TARGET) or TRIBE_SEASON_TABOO_PROGRESS_TARGET):
            taboo["blessed"] = True
            taboo["blessedAt"] = datetime.now().isoformat()
            blessing_parts = self._apply_season_taboo_reward(tribe, config.get("blessing", {}))
            reward_parts.extend([f"祝福{part}" for part in blessing_parts])
            blessed_now = True
        detail = f"{member_name} {config.get('observeLabel', '践行禁忌')}，{taboo.get('label', '季节禁忌')}进度 {taboo.get('progress', 0)} / {taboo.get('target', 0)}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        if blessed_now:
            detail += " 季节祝福已经形成。"
            await self._publish_world_rumor(
                "season",
                "季节祝福",
                f"{tribe.get('name', '部落')} 遵守{taboo.get('label', '季节禁忌')}，把禁忌转成了公开祝福。",
                {"tribeId": tribe_id, "tabooKey": taboo.get("key")}
            )
        self._add_tribe_history(tribe, "ritual", "践行季节禁忌", detail, player_id, {"kind": "season_taboo_observe", "tabooId": taboo.get("id"), "rewardParts": reward_parts})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def break_season_taboo(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        taboo = self._active_season_taboo(tribe)
        if not taboo:
            await self._send_tribe_error(player_id, "当前没有可破戒的季节禁忌")
            return
        if taboo.get("broken"):
            await self._send_tribe_error(player_id, "这条季节禁忌已经破戒，先完成补救")
            return
        config = TRIBE_SEASON_TABOO_OPTIONS.get(taboo.get("key"), {})
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_season_taboo_reward(tribe, config.get("breakReward", {}))
        now_text = datetime.now().isoformat()
        taboo["broken"] = True
        taboo["brokenAt"] = now_text
        taboo["brokenBy"] = player_id
        remedy_config = dict(config.get("remedy") or {})
        remedy = {
            "id": f"season_taboo_remedy_{taboo.get('id')}",
            "status": "pending",
            "kind": "season_taboo_remedy",
            "title": remedy_config.get("title", "季节补救"),
            "summary": remedy_config.get("summary", "破戒已经公开，需要成员完成补救任务。"),
            "tabooId": taboo.get("id"),
            "tabooLabel": taboo.get("label", "季节禁忌"),
            "createdAt": now_text,
            **remedy_config
        }
        tribe.setdefault("season_taboo_remedies", []).append(remedy)
        tribe["season_taboo_remedies"] = tribe["season_taboo_remedies"][-TRIBE_SEASON_TABOO_REMEDY_LIMIT:]
        detail = f"{member.get('name', '成员')} {config.get('breakLabel', '破戒取急用')}：{config.get('breakSummary', '')} {'、'.join(reward_parts) or '已记录'}。补救任务“{remedy['title']}”已公开。"
        self._add_tribe_history(tribe, "governance", "季节破戒", detail, player_id, {"kind": "season_taboo_break", "tabooId": taboo.get("id"), "remedy": remedy})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_season_taboo_remedy(self, player_id: str, remedy_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        remedy = next((
            item for item in (tribe.get("season_taboo_remedies", []) or [])
            if isinstance(item, dict) and item.get("id") == remedy_id and item.get("status") == "pending"
        ), None)
        if not remedy:
            await self._send_tribe_error(player_id, "没有找到可完成的季节补救")
            return
        food_cost = int(remedy.get("foodCost", 0) or 0)
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"补救需要食物 {food_cost}")
            return
        wood_cost = int(remedy.get("woodCost", 0) or 0)
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"补救需要木材 {wood_cost}")
            return
        reward_parts = self._apply_season_taboo_reward(tribe, remedy)
        remedy["status"] = "completed"
        remedy["completedAt"] = datetime.now().isoformat()
        remedy["completedBy"] = player_id
        taboo = tribe.get("season_taboo")
        if isinstance(taboo, dict) and taboo.get("id") == remedy.get("tabooId"):
            taboo["broken"] = False
            taboo["remediedAt"] = remedy["completedAt"]
        member = tribe.get("members", {}).get(player_id, {})
        detail = f"{member.get('name', '成员')} 完成{remedy.get('title', '季节补救')}：{'、'.join(reward_parts) or '禁忌重新被承认'}。"
        self._add_tribe_history(tribe, "ritual", "季节补救", detail, player_id, {"kind": "season_taboo_remedy", "remedyId": remedy_id, "tabooId": remedy.get("tabooId")})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
