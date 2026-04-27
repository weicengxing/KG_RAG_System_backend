from datetime import datetime

from game_config import *


class GameTrailMarkerMixin:
    def _active_trail_markers(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for marker in tribe.get("trail_markers", []) or []:
            if not isinstance(marker, dict) or marker.get("status") != "active":
                continue
            active_until = marker.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        marker["status"] = "expired"
                        marker["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    marker["status"] = "expired"
                    marker["expiredAt"] = now.isoformat()
                    continue
            active.append(marker)
        if len(active) != len(tribe.get("trail_markers", []) or []):
            tribe["trail_markers"] = active[-TRIBE_TRAIL_MARKER_LIMIT:]
        return active[-TRIBE_TRAIL_MARKER_LIMIT:]

    def _public_trail_markers(self, tribe: dict) -> list:
        markers = []
        for marker in self._active_trail_markers(tribe):
            edits = list(marker.get("edits", []) or [])
            markers.append({
                "id": marker.get("id"),
                "type": marker.get("type", "trail_marker"),
                "markerKey": marker.get("markerKey"),
                "label": marker.get("label", "活路标"),
                "summary": marker.get("summary", ""),
                "x": marker.get("x", 0),
                "z": marker.get("z", 0),
                "createdByName": marker.get("createdByName", "成员"),
                "durability": int(marker.get("durability", 1) or 1),
                "interpretation": marker.get("interpretation", ""),
                "editCount": len(edits),
                "lastEditLabel": edits[-1].get("actionLabel") if edits else "",
                "lastEditorName": edits[-1].get("memberName") if edits else "",
                "rewardLabel": marker.get("rewardLabel", ""),
                "createdAt": marker.get("createdAt"),
                "activeUntil": marker.get("activeUntil")
            })
        return markers

    def _public_trail_marker_actions(self) -> dict:
        return TRIBE_TRAIL_MARKER_ACTIONS

    def _apply_trail_marker_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                parts.append(f"{label}+{amount}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现进度", "discovery_progress")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        return parts

    def _trail_marker_position(self, x: float, z: float) -> tuple[float, float]:
        return (
            max(-490, min(490, float(x or 0))),
            max(-490, min(490, float(z or 0)))
        )

    async def create_trail_marker(self, player_id: str, marker_key: str, x: float, z: float):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        config = TRIBE_TRAIL_MARKER_TYPES.get(marker_key)
        if not config:
            await self._send_tribe_error(player_id, "未知路标类型")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        food_cost = int(config.get("foodCost", 0) or 0)
        wood_cost = int(config.get("woodCost", 0) or 0)
        stone_cost = int(config.get("stoneCost", 0) or 0)
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"立路标需要食物 {food_cost}")
            return
        if int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"立路标需要木材 {wood_cost}")
            return
        if int(storage.get("stone", 0) or 0) < stone_cost:
            await self._send_tribe_error(player_id, f"立路标需要石块 {stone_cost}")
            return

        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        if stone_cost:
            storage["stone"] = int(storage.get("stone", 0) or 0) - stone_cost

        marker_x, marker_z = self._trail_marker_position(x, z)
        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        reward = dict(config.get("reward", {}) or {})
        marker = {
            "id": f"trail_marker_{tribe_id}_{int(now.timestamp() * 1000)}",
            "type": "trail_marker",
            "status": "active",
            "markerKey": marker_key,
            "label": config.get("label", "活路标"),
            "summary": config.get("summary", "这里留下了一处可被同伴改写的路标。"),
            "x": marker_x,
            "z": marker_z,
            "y": 0,
            "size": 0.8,
            "durability": 1,
            "interpretation": config.get("summary", ""),
            "createdBy": player_id,
            "createdByName": member.get("name", "成员"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_TRAIL_MARKER_ACTIVE_MINUTES * 60).isoformat(),
            "reward": reward,
            "rewardLabel": self._reward_summary_text(reward),
            "edits": []
        }
        active = self._active_trail_markers(tribe)
        tribe["trail_markers"] = [*active, marker][-TRIBE_TRAIL_MARKER_LIMIT:]
        detail = f"{marker['createdByName']} 在当前位置留下{marker['label']}，让这段路可以被后来者修正、加固或拆除。"
        self._add_tribe_history(tribe, "exploration", "立下活路标", detail, player_id, {"kind": "trail_marker", "marker": marker})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def update_trail_marker(self, player_id: str, marker_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_TRAIL_MARKER_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知路标动作")
            return
        markers = self._active_trail_markers(tribe)
        marker = next((item for item in markers if item.get("id") == marker_id), None)
        if not marker:
            await self._send_tribe_error(player_id, "这处路标已经淡去")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        food_cost = int(action.get("foodCost", 0) or 0)
        wood_cost = int(action.get("woodCost", 0) or 0)
        stone_cost = int(action.get("stoneCost", 0) or 0)
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"改写路标需要食物 {food_cost}")
            return
        if int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"改写路标需要木材 {wood_cost}")
            return
        if int(storage.get("stone", 0) or 0) < stone_cost:
            await self._send_tribe_error(player_id, f"改写路标需要石块 {stone_cost}")
            return
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        if stone_cost:
            storage["stone"] = int(storage.get("stone", 0) or 0) - stone_cost

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        now = datetime.now()
        reward_parts = self._apply_trail_marker_reward(tribe, action.get("reward", {}))
        edit = {
            "playerId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "改写"),
            "createdAt": now.isoformat()
        }
        marker.setdefault("edits", []).append(edit)
        marker["updatedAt"] = now.isoformat()
        marker["lastEditorName"] = member_name
        if action_key == "reinterpret":
            marker["interpretation"] = f"{member_name}把它改读为：{marker.get('label', '路标')}仍指向一条可走的活路。"
        if action_key == "reinforce":
            marker["durability"] = int(marker.get("durability", 1) or 1) + 1
            extend = int(action.get("extendMinutes", 0) or 0)
            if extend:
                marker["activeUntil"] = datetime.fromtimestamp(now.timestamp() + (TRIBE_TRAIL_MARKER_ACTIVE_MINUTES + extend) * 60).isoformat()
        if action.get("resolve"):
            marker["status"] = "resolved"
            marker["resolvedAt"] = now.isoformat()
            tribe["trail_markers"] = [item for item in markers if item.get("id") != marker_id]
            tribe.setdefault("trail_marker_history", []).append(marker)
            tribe["trail_marker_history"] = tribe["trail_marker_history"][-TRIBE_TRAIL_MARKER_HISTORY_LIMIT:]

        detail = f"{member_name} 对{marker.get('label', '活路标')}执行{action.get('label', '改写')}。"
        if reward_parts:
            detail += f" 收获：{'、'.join(reward_parts)}。"
        if action.get("resolve"):
            detail += " 这处路标已从地图上撤下，但改写记录留进部落历史。"
        self._add_tribe_history(tribe, "exploration", "活路标改写", detail, player_id, {"kind": "trail_marker_update", "marker": marker, "actionKey": action_key, "rewardParts": reward_parts})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
