from game_config import *


class GameBeastLinkMixin:
    def _public_beast_ritual_links(self, tribe: dict) -> list:
        links = []
        active_taboo = tribe.get("season_taboo")
        if isinstance(active_taboo, dict) and active_taboo.get("status") == "active":
            link = TRIBE_BEAST_RITUAL_LINKS.get(f"season:{active_taboo.get('key')}")
            if link:
                links.append({
                    "source": "season",
                    "sourceLabel": active_taboo.get("label", "季节禁忌"),
                    **link
                })

        for ritual in reversed(list(tribe.get("standing_ritual_history", []) or [])):
            if not isinstance(ritual, dict) or ritual.get("status") != "completed":
                continue
            link = TRIBE_BEAST_RITUAL_LINKS.get(f"ritual:{ritual.get('key')}")
            if not link:
                continue
            links.append({
                "source": "ritual",
                "sourceLabel": ritual.get("label", "站位仪式"),
                **link
            })
            if len(links) >= TRIBE_BEAST_RITUAL_LINK_LIMIT:
                break
        return links[:TRIBE_BEAST_RITUAL_LINK_LIMIT]

    def _apply_beast_ritual_link_rewards(self, tribe: dict, task_key: str) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for link in self._public_beast_ritual_links(tribe):
            if task_key not in (link.get("taskKeys", []) or []):
                continue
            reward = link.get("reward", {}) or {}
            for resource_key, label in (("wood", "木材"), ("stone", "石材")):
                amount = int(reward.get(resource_key, 0) or 0)
                if amount:
                    storage[resource_key] = int(storage.get(resource_key, 0) or 0) + amount
                    reward_parts.append(f"{link.get('label', '幼兽联动')}{label}+{amount}")
            food = int(reward.get("food", 0) or 0)
            if food:
                tribe["food"] = int(tribe.get("food", 0) or 0) + food
                reward_parts.append(f"{link.get('label', '幼兽联动')}食物+{food}")
            renown = int(reward.get("renown", 0) or 0)
            if renown:
                tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
                reward_parts.append(f"{link.get('label', '幼兽联动')}声望+{renown}")
            discovery = int(reward.get("discoveryProgress", 0) or 0)
            if discovery:
                tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
                reward_parts.append(f"{link.get('label', '幼兽联动')}发现+{discovery}")
            trade = int(reward.get("tradeReputation", 0) or 0)
            if trade:
                tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
                reward_parts.append(f"{link.get('label', '幼兽联动')}贸易信誉+{trade}")
        return reward_parts
