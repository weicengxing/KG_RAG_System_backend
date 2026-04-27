from datetime import datetime
import random

from game_config import *


class GameSharedPuzzleMixin:
    def _shared_puzzle_source_available(self, tribe: dict, source_key: str) -> bool:
        if source_key == "cave":
            discoveries = " ".join(str(item) for item in (tribe.get("discoveries", []) or []))
            history_text = " ".join(f"{item.get('title', '')} {item.get('detail', '')}" for item in (tribe.get("history", []) or [])[-20:] if isinstance(item, dict))
            return bool("cave" in discoveries or "洞" in history_text or "远征" in history_text)
        if source_key == "ruin":
            if int(tribe.get("ruin_clue_chain", 0) or 0) > 0:
                return True
            memories = tribe.get("map_memories", []) or []
            remnants = tribe.get("world_event_remnants", []) or []
            text = " ".join(f"{item.get('label', '')} {item.get('summary', '')}" for item in [*memories, *remnants] if isinstance(item, dict))
            return bool("遗迹" in text or "旧石" in text or "刻痕" in text)
        if source_key == "traveler":
            return bool(
                tribe.get("nomad_visitor_aftereffects")
                or tribe.get("nomad_visitors")
                or tribe.get("far_return_tasks")
                or tribe.get("far_return_records")
            )
        if source_key == "market":
            return bool(
                tribe.get("market_pacts")
                or tribe.get("trade_route_sites")
                or tribe.get("caravan_routes")
                or int(tribe.get("trade_reputation", 0) or 0) >= 2
            )
        return False

    def _public_shared_puzzle_options(self, tribe: dict) -> dict:
        fragments = tribe.get("shared_puzzle_fragments", []) or []
        recorded = {item.get("sourceKey") for item in fragments if isinstance(item, dict)}
        options = {}
        for key, config in TRIBE_SHARED_PUZZLE_SOURCES.items():
            available = self._shared_puzzle_source_available(tribe, key)
            options[key] = {
                **config,
                "available": available and key not in recorded,
                "recorded": key in recorded,
                "rewardLabel": self._reward_summary_text(config.get("reward", {})) if hasattr(self, "_reward_summary_text") else ""
            }
        return options

    def _public_shared_puzzle(self, tribe: dict) -> dict:
        fragments = [item for item in (tribe.get("shared_puzzle_fragments", []) or []) if isinstance(item, dict)]
        source_keys = list(dict.fromkeys(item.get("sourceKey") for item in fragments if item.get("sourceKey")))
        return {
            "fragments": fragments[-TRIBE_SHARED_PUZZLE_TARGET:],
            "fragmentCount": len(source_keys),
            "target": TRIBE_SHARED_PUZZLE_TARGET,
            "ready": len(source_keys) >= TRIBE_SHARED_PUZZLE_TARGET,
            "missingLabels": [
                config.get("label", key)
                for key, config in TRIBE_SHARED_PUZZLE_SOURCES.items()
                if key not in source_keys
            ]
        }

    def _public_shared_puzzle_records(self, tribe: dict) -> list:
        return [item for item in tribe.get("shared_puzzle_records", []) or [] if isinstance(item, dict)][-TRIBE_SHARED_PUZZLE_RECORD_LIMIT:]

    def _apply_shared_puzzle_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        renown = int((reward or {}).get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            parts.append(f"声望+{renown}")
        discovery = int((reward or {}).get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            parts.append(f"发现+{discovery}")
        trade = int((reward or {}).get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            parts.append(f"贸易信誉+{trade}")
        food = int((reward or {}).get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            parts.append(f"食物+{food}")
        return parts

    async def record_shared_puzzle_fragment(self, player_id: str, source_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        config = TRIBE_SHARED_PUZZLE_SOURCES.get(source_key)
        if not config:
            await self._send_tribe_error(player_id, "未知谜图碎片来源")
            return
        fragments = tribe.setdefault("shared_puzzle_fragments", [])
        if any(item.get("sourceKey") == source_key for item in fragments if isinstance(item, dict)):
            await self._send_tribe_error(player_id, "这类图案碎片已经记录过")
            return
        if not self._shared_puzzle_source_available(tribe, source_key):
            await self._send_tribe_error(player_id, "部落还没有这种碎片来源")
            return
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_shared_puzzle_reward(tribe, config.get("reward", {}))
        fragment = {
            "id": f"puzzle_fragment_{tribe_id}_{source_key}_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "sourceKey": source_key,
            "sourceLabel": config.get("label", source_key),
            "summary": config.get("summary", ""),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        echo_item = next((
            item for item in reversed(tribe.get("echo_items", []) or [])
            if isinstance(item, dict) and item.get("memories")
        ), None)
        if echo_item:
            last_memory = (echo_item.get("memories", []) or [])[-1]
            fragment["echoItemHint"] = {
                "itemId": echo_item.get("id"),
                "itemLabel": echo_item.get("label", "回声物品"),
                "memoryLabel": last_memory.get("experienceLabel", "旧经历") if isinstance(last_memory, dict) else "旧经历"
            }
        fragments.append(fragment)
        tribe["shared_puzzle_fragments"] = fragments[-TRIBE_SHARED_PUZZLE_TARGET:]
        detail = f"{fragment['memberName']} 记录“{fragment['sourceLabel']}”：{'、'.join(reward_parts) or '谜图多了一角'}。"
        if fragment.get("echoItemHint"):
            hint = fragment["echoItemHint"]
            detail += f" {hint.get('itemLabel', '回声物品')}的{hint.get('memoryLabel', '旧经历')}也成了旁注。"
        self._add_tribe_history(tribe, "world_event", "记录共享谜图", detail, player_id, {"kind": "shared_puzzle_fragment", "fragment": fragment})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_shared_puzzle(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        puzzle = self._public_shared_puzzle(tribe)
        if not puzzle.get("ready"):
            await self._send_tribe_error(player_id, f"共享谜图还差{len(puzzle.get('missingLabels', []))}类碎片")
            return
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_shared_puzzle_reward(tribe, TRIBE_SHARED_PUZZLE_COMPLETE_REWARD)
        record = {
            "id": f"shared_puzzle_{tribe_id}_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "title": "共享谜图拼合",
            "summary": "洞穴、遗迹、旅人和边市图案被拼成一张共同谜图，新的路线和传闻开始交叉。",
            "fragmentLabels": [item.get("sourceLabel", "碎片") for item in puzzle.get("fragments", [])],
            "completedByName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("shared_puzzle_records", []).append(record)
        tribe["shared_puzzle_records"] = tribe["shared_puzzle_records"][-TRIBE_SHARED_PUZZLE_RECORD_LIMIT:]
        tribe["shared_puzzle_fragments"] = []
        detail = f"{record['completedByName']} 拼合共享谜图：{'、'.join(reward_parts) or '部落获得新的共同线索'}。"
        self._add_tribe_history(tribe, "world_event", "共享谜图拼合", detail, player_id, {"kind": "shared_puzzle_complete", "record": record})
        await self._publish_world_rumor(
            "world_event",
            "共享谜图拼合",
            f"{tribe.get('name', '部落')} 把洞穴、遗迹、旅人和边市的图案拼成共同谜图。",
            {"tribeId": tribe_id, "recordId": record.get("id")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
