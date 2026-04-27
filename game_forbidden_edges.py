import math
import random
from datetime import datetime

from game_config import *


class GameForbiddenEdgeMixin:
    def _forbidden_edge_rng(self):
        return getattr(self, "_weather_rng", random)

    def _active_forbidden_edges(self, tribe: dict) -> list:
        if not tribe:
            return []
        active = []
        now = datetime.now()
        for edge in tribe.get("forbidden_edges", []) or []:
            if not isinstance(edge, dict) or edge.get("status", "active") != "active":
                continue
            active_until = edge.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        edge["status"] = "expired"
                        edge["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    edge["status"] = "expired"
                    edge["expiredAt"] = now.isoformat()
                    continue
            active.append(edge)
        tribe["forbidden_edges"] = active[-TRIBE_FORBIDDEN_EDGE_LIMIT:]
        return tribe["forbidden_edges"]

    def _ensure_forbidden_edge(self, tribe: dict):
        if not tribe:
            return None
        active = self._active_forbidden_edges(tribe)
        if active:
            return active[0]
        camp = tribe.get("camp") or {}
        center = camp.get("center") or {}
        if not center:
            return None
        rng = self._forbidden_edge_rng()
        angle = rng.random() * math.tau
        distance = 48 + rng.random() * 58
        now = datetime.now()
        edge = {
            "id": f"forbidden_edge_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{rng.randint(100, 999)}",
            "type": "forbidden_edge",
            "status": "active",
            "label": "禁地边缘",
            "summary": "一片短时显露的高风险边缘，能带回发现和旧物，但逗留太久只会留下营救线索。",
            "x": max(-490, min(490, float(center.get("x", 0) or 0) + math.cos(angle) * distance)),
            "z": max(-490, min(490, float(center.get("z", 0) or 0) + math.sin(angle) * distance)),
            "y": 0,
            "size": 1.05,
            "radius": TRIBE_FORBIDDEN_EDGE_RADIUS,
            "participants": [],
            "dangerTarget": TRIBE_FORBIDDEN_EDGE_DANGER_TARGET,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_FORBIDDEN_EDGE_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["forbidden_edges"] = [edge][-TRIBE_FORBIDDEN_EDGE_LIMIT:]
        return edge

    def _public_forbidden_edges(self, tribe: dict) -> list:
        self._ensure_forbidden_edge(tribe)
        return [dict(edge) for edge in self._active_forbidden_edges(tribe)]

    def _public_forbidden_edge_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("forbidden_edge_records", []) or [])
            if isinstance(record, dict)
        ][-TRIBE_FORBIDDEN_EDGE_RECORD_LIMIT:]

    def _public_forbidden_edge_actions(self, tribe: dict) -> dict:
        actions = {}
        for key, action in TRIBE_FORBIDDEN_EDGE_ACTIONS.items():
            available = True
            reason = ""
            if int(action.get("requiresMembers", 0) or 0) > len(tribe.get("members", {}) or {}):
                available = False
                reason = f"需要至少 {action.get('requiresMembers')} 名成员"
            actions[key] = {
                **action,
                "available": available,
                "reason": reason,
                "rewardLabel": self._reward_summary_text(action.get("reward", {})) if hasattr(self, "_reward_summary_text") else ""
            }
        return actions

    def _near_forbidden_edge(self, player_id: str, edge: dict) -> bool:
        player = self.players.get(player_id, {}) if hasattr(self, "players") else {}
        dx = float(player.get("x", 0) or 0) - float(edge.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(edge.get("z", 0) or 0)
        return math.sqrt(dx * dx + dz * dz) <= float(edge.get("radius", TRIBE_FORBIDDEN_EDGE_RADIUS) or TRIBE_FORBIDDEN_EDGE_RADIUS)

    def _apply_forbidden_edge_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("food", "食物", "food")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        return parts

    def _forbidden_edge_support_bonus(self, tribe: dict, action_key: str) -> tuple[int, list]:
        labels = []
        bonus = 0
        if action_key == "torch_probe" and self._has_tribe_structure_type(tribe, "campfire"):
            labels.append("营火旧光")
            bonus += 1
        if action_key == "trail_probe" and (tribe.get("trail_markers") or tribe.get("trail_marker_history")):
            labels.append("活路标")
            bonus += 1
        if action_key == "companion_probe" and len(tribe.get("members", {}) or {}) >= 3:
            labels.append("多人照应")
            bonus += 1
        if int(tribe.get("tamed_beasts", 0) or 0) > 0:
            labels.append("幼兽预警")
            bonus += 1
        return bonus, labels

    def _create_forbidden_edge_rescue(self, tribe: dict, edge: dict, player_id: str, member_name: str, action: dict) -> dict:
        now = datetime.now()
        race_id = f"forbidden_rescue_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}"
        rescue = {
            "id": race_id,
            "status": "rescue",
            "type": "cave_rescue_clue",
            "title": "禁地边缘营救",
            "label": f"{edge.get('label', '禁地边缘')}营救线索",
            "summary": "成员在禁地边缘逗留太久，留下了可循线救回的痕迹。",
            "caveLabel": edge.get("label", "禁地边缘"),
            "sourceKind": "forbidden_edge",
            "sourceId": edge.get("id"),
            "sourceTribeId": tribe.get("id"),
            "sourceTribeName": tribe.get("name", "部落"),
            "x": edge.get("x", 0),
            "z": edge.get("z", 0),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_CAVE_RACE_RESCUE_MINUTES * 60).isoformat(),
            "rescue": {
                "status": "missing",
                "missingPlayerId": player_id,
                "missingMemberName": member_name,
                "progress": 0,
                "target": TRIBE_FORBIDDEN_EDGE_RESCUE_TARGET,
                "helperIds": [],
                "steps": [],
                "supportLabels": [action.get("label", "禁地试探")],
                "createdAt": now.isoformat()
            }
        }
        races = self._active_cave_races(tribe) if hasattr(self, "_active_cave_races") else []
        tribe["cave_races"] = [*races, rescue][-TRIBE_CAVE_RACE_LIMIT:]
        return rescue

    async def explore_forbidden_edge(self, player_id: str, edge_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_FORBIDDEN_EDGE_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知禁地试探方式")
            return
        if int(action.get("requiresMembers", 0) or 0) > len(tribe.get("members", {}) or {}):
            await self._send_tribe_error(player_id, f"{action.get('label', '试探')}需要至少 {action.get('requiresMembers')} 名成员")
            return
        edge = next((item for item in self._active_forbidden_edges(tribe) if item.get("id") == edge_id), None)
        if not edge:
            await self._send_tribe_error(player_id, "这片禁地边缘已经隐去")
            return
        if any(item.get("memberId") == player_id for item in edge.get("participants", []) or []):
            await self._send_tribe_error(player_id, "你已经试探过这片禁地边缘")
            return
        if not self._near_forbidden_edge(player_id, edge):
            await self._send_tribe_error(player_id, f"需要靠近禁地边缘 {TRIBE_FORBIDDEN_EDGE_RADIUS} 步内")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(action.get("woodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"{action.get('label', '试探')}需要公共木材{wood_cost}")
            return
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost

        now = datetime.now()
        rng = self._forbidden_edge_rng()
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", self.players.get(player_id, {}).get("name", "成员"))
        support_bonus, support_labels = self._forbidden_edge_support_bonus(tribe, action_key)
        roll = rng.randint(1, 6)
        total = roll + int(action.get("safety", 0) or 0) + support_bonus
        lost = total < TRIBE_FORBIDDEN_EDGE_DANGER_TARGET
        reward_parts = [] if lost else self._apply_forbidden_edge_reward(tribe, action.get("reward", {}))
        participant = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "禁地试探"),
            "roll": roll,
            "total": total,
            "lost": lost,
            "supportLabels": support_labels,
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        edge.setdefault("participants", []).append(participant)
        edge["lastActionLabel"] = action.get("label", "禁地试探")
        edge["lastActorName"] = member_name
        edge["lastOutcome"] = "rescue" if lost else "safe"
        record = {
            "id": f"forbidden_edge_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "edgeId": edge.get("id"),
            "label": edge.get("label", "禁地边缘"),
            "summary": edge.get("summary", ""),
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "禁地试探"),
            "lost": lost,
            "roll": roll,
            "total": total,
            "supportLabels": support_labels,
            "rewardParts": reward_parts,
            "collectionReady": bool(action.get("collectionReady")) and not lost,
            "createdAt": now.isoformat()
        }
        rescue = None
        if lost:
            rescue = self._create_forbidden_edge_rescue(tribe, edge, player_id, member_name, action)
            record["rescueId"] = rescue.get("id")
        tribe.setdefault("forbidden_edge_records", []).append(record)
        tribe["forbidden_edge_records"] = tribe["forbidden_edge_records"][-TRIBE_FORBIDDEN_EDGE_RECORD_LIMIT:]

        if lost:
            detail = f"{member_name}在{edge.get('label', '禁地边缘')}逗留过深，掷出{roll}，留下营救线索而非死亡。"
        else:
            detail = f"{member_name}在{edge.get('label', '禁地边缘')}完成{action.get('label', '试探')}，掷出{roll}+支撑{support_bonus}，{'、'.join(reward_parts) or '安全回撤'}。"
            if record.get("collectionReady"):
                detail += " 带回的边缘旧物可整理进收藏墙。"
        self._add_tribe_history(tribe, "exploration", "禁地边缘", detail, player_id, {"kind": "forbidden_edge", "record": record, "edge": edge})
        await self._notify_tribe(tribe_id, detail)
        if lost:
            await self._publish_world_rumor(
                "exploration",
                "禁地边缘留下营救线索",
                f"{tribe.get('name', '某个部落')}在禁地边缘失去一名试探者的踪迹，但线索仍可循回。",
                {"tribeId": tribe_id, "edgeId": edge.get("id"), "rescueId": rescue.get("id") if rescue else ""}
            )
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
