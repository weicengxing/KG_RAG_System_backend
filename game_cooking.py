from datetime import datetime

from game_config import *


class GameCookingMixin:
    def _active_communal_cook(self, tribe: dict) -> dict | None:
        cook = tribe.get("communal_cook")
        if not isinstance(cook, dict) or cook.get("status") != "active":
            return None
        active_until = cook.get("activeUntil")
        if active_until:
            try:
                if datetime.fromisoformat(active_until) <= datetime.now():
                    cook["status"] = "expired"
                    cook["expiredAt"] = datetime.now().isoformat()
                    return None
            except (TypeError, ValueError):
                cook["status"] = "expired"
                cook["expiredAt"] = datetime.now().isoformat()
                return None
        return cook

    def _public_communal_cook(self, tribe: dict) -> dict | None:
        cook = self._active_communal_cook(tribe)
        if not cook:
            return None
        contributions = list(cook.get("contributions", []) or [])
        return {
            "id": cook.get("id"),
            "recipeKey": cook.get("recipeKey"),
            "recipeLabel": cook.get("recipeLabel"),
            "summary": cook.get("summary"),
            "progress": len(contributions),
            "target": int(cook.get("target", TRIBE_COMMUNAL_COOK_TARGET) or TRIBE_COMMUNAL_COOK_TARGET),
            "contributions": contributions[-6:],
            "createdByName": cook.get("createdByName"),
            "createdAt": cook.get("createdAt"),
            "activeUntil": cook.get("activeUntil")
        }

    def _apply_communal_cook_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石材")):
            value = int(reward.get(key, 0) or 0)
            if value:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + value)
                parts.append(f"{label}{value:+d}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            value = int(reward.get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        return parts

    async def start_communal_cook(self, player_id: str, recipe_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if self._active_communal_cook(tribe):
            await self._send_tribe_error(player_id, "当前已经有一锅共同烹饪正在进行")
            return
        recipe = TRIBE_COMMUNAL_COOK_RECIPES.get(recipe_key)
        if not recipe:
            await self._send_tribe_error(player_id, "未知菜谱")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        food_cost = int(recipe.get("foodCost", 0) or 0)
        wood_cost = int(recipe.get("woodCost", 0) or 0)
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"开锅需要公共食物{food_cost}")
            return
        if int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"开锅需要公共木材{wood_cost}")
            return
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        cook = {
            "id": f"communal_cook_{tribe_id}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "recipeKey": recipe_key,
            "recipeLabel": recipe.get("label", "共同烹饪"),
            "summary": recipe.get("summary", ""),
            "target": TRIBE_COMMUNAL_COOK_TARGET,
            "contributionIds": [],
            "contributions": [],
            "createdBy": player_id,
            "createdByName": member.get("name", "成员"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_COMMUNAL_COOK_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["communal_cook"] = cook
        detail = f"{member.get('name', '成员')} 在营地开了一锅{cook['recipeLabel']}，需要 {TRIBE_COMMUNAL_COOK_TARGET} 次补料或讲述来完成。"
        self._add_tribe_history(tribe, "food", "共同烹饪开锅", detail, player_id, {"kind": "communal_cook", "cook": cook})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def contribute_communal_cook(self, player_id: str, ingredient_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        cook = self._active_communal_cook(tribe)
        if not cook:
            await self._send_tribe_error(player_id, "当前没有正在进行的共同烹饪")
            return
        if player_id in (cook.get("contributionIds", []) or []):
            await self._send_tribe_error(player_id, "你已经为这锅饭贡献过了")
            return
        ingredient = TRIBE_COMMUNAL_COOK_INGREDIENTS.get(ingredient_key)
        if not ingredient:
            await self._send_tribe_error(player_id, "未知补料方式")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        food_cost = int(ingredient.get("foodCost", 0) or 0)
        wood_cost = int(ingredient.get("woodCost", 0) or 0)
        stone_cost = int(ingredient.get("stoneCost", 0) or 0)
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"添粮需要公共食物{food_cost}")
            return
        if int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"补柴需要公共木材{wood_cost}")
            return
        if int(storage.get("stone", 0) or 0) < stone_cost:
            await self._send_tribe_error(player_id, f"立热石需要公共石块{stone_cost}")
            return
        tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        storage["stone"] = int(storage.get("stone", 0) or 0) - stone_cost

        member = tribe.get("members", {}).get(player_id, {})
        contribution = {
            "playerId": player_id,
            "name": member.get("name", "成员"),
            "ingredientKey": ingredient_key,
            "ingredientLabel": ingredient.get("label", "补料"),
            "joinedAt": datetime.now().isoformat()
        }
        cook.setdefault("contributionIds", []).append(player_id)
        cook.setdefault("contributions", []).append(contribution)
        self.players.setdefault(player_id, {})["personal_renown"] = int(self.players.get(player_id, {}).get("personal_renown", 0) or 0) + 1
        reward_parts = self._apply_communal_cook_reward(tribe, ingredient)
        detail = f"{contribution['name']} 为{cook.get('recipeLabel', '共同烹饪')}选择{contribution['ingredientLabel']}，进度 {len(cook.get('contributions', []))}/{cook.get('target', TRIBE_COMMUNAL_COOK_TARGET)}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "food", "共同烹饪补料", detail, player_id, {"kind": "communal_cook_contribute", "cookId": cook.get("id"), "ingredientKey": ingredient_key})
        completed = len(cook.get("contributions", []) or []) >= int(cook.get("target", TRIBE_COMMUNAL_COOK_TARGET) or TRIBE_COMMUNAL_COOK_TARGET)
        if completed:
            recipe = TRIBE_COMMUNAL_COOK_RECIPES.get(cook.get("recipeKey"), {})
            final_parts = self._apply_communal_cook_reward(tribe, recipe.get("reward", {}))
            cook["status"] = "completed"
            cook["completedAt"] = datetime.now().isoformat()
            cook["completedBy"] = player_id
            cook["rewardParts"] = final_parts
            tribe.setdefault("communal_cook_history", []).append(cook)
            tribe["communal_cook_history"] = tribe["communal_cook_history"][-TRIBE_COMMUNAL_COOK_HISTORY_LIMIT:]
            names = "、".join([item.get("name", "成员") for item in cook.get("contributions", [])])
            detail += f" 这锅{cook.get('recipeLabel', '共同烹饪')}完成了，{names}把食材与故事写进宴会记忆：{'、'.join(final_parts) or '部落记住了这锅饭'}。"
            self._add_tribe_history(tribe, "food", "共同烹饪完成", detail, player_id, {"kind": "communal_cook_complete", "cook": cook, "rewardParts": final_parts})
            if hasattr(self, "_create_celebration_echo"):
                self._create_celebration_echo(tribe, "cooking", cook.get("recipeLabel", "共同烹饪"), player_id, cook.get("id", ""))
            await self._publish_world_rumor(
                "food",
                "共同烹饪",
                f"{tribe.get('name', '部落')} 完成一锅{cook.get('recipeLabel', '共同烹饪')}，把{names}的贡献煮成了新的营地故事。",
                {"tribeId": tribe_id, "cookId": cook.get("id")}
            )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        if completed:
            await self._broadcast_current_map()
