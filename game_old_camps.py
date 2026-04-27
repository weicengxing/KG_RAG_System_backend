import math
import random
from datetime import datetime

from game_config import *


class GameOldCampEchoMixin:
    def _old_camp_rng(self):
        return getattr(self, "_weather_rng", random)

    def _active_old_camp_echoes(self, tribe: dict) -> list:
        if not tribe:
            return []
        active = []
        now = datetime.now()
        for echo in tribe.get("old_camp_echoes", []) or []:
            if not isinstance(echo, dict) or echo.get("status", "active") != "active":
                continue
            active_until = echo.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        echo["status"] = "expired"
                        echo["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    echo["status"] = "expired"
                    echo["expiredAt"] = now.isoformat()
                    continue
            active.append(echo)
        tribe["old_camp_echoes"] = active[-TRIBE_OLD_CAMP_ECHO_LIMIT:]
        return tribe["old_camp_echoes"]

    def _old_camp_echo_kind(self, tribe: dict) -> dict:
        env = self._get_current_environment() if hasattr(self, "_get_current_environment") else {}
        weather = env.get("weather", "sunny")
        celestial = env.get("celestialWindow") if isinstance(env.get("celestialWindow"), dict) else None
        if celestial:
            return {
                "key": "star_old_camp",
                "label": "星下旧营",
                "summary": "天象照亮了一处旧营火圈，像是有人把未讲完的话留在灰烬里。",
                "sourceLabel": "天象旧营"
            }
        if weather in {"rainy", "storm", "fog"}:
            return {
                "key": "old_battlefield",
                "label": "雨中旧战场",
                "summary": "雨水冲开旧战场边缘的泥痕，能看见曾经撤退和救援的路线。",
                "sourceLabel": "旧战场"
            }
        if tribe.get("market_pacts") or tribe.get("trade_route_sites"):
            return {
                "key": "old_market",
                "label": "旧边市灰痕",
                "summary": "旧边市的石圈短时苏醒，残留的议价刻痕还能被重新读懂。",
                "sourceLabel": "旧边市"
            }
        return {
            "key": "abandoned_fire",
            "label": "废弃营火",
            "summary": "一处旧营火在风里露出灰白火痕，适合修复、补写或带回旧物。",
            "sourceLabel": "废弃营火"
        }

    def _ensure_old_camp_echo(self, tribe: dict):
        if not tribe:
            return None
        active = self._active_old_camp_echoes(tribe)
        if active:
            return active[0]
        camp = tribe.get("camp") or {}
        center = camp.get("center") or {}
        if not center:
            return None
        rng = self._old_camp_rng()
        kind = self._old_camp_echo_kind(tribe)
        angle = rng.random() * math.pi * 2
        distance = 18 + rng.random() * 42
        now = datetime.now()
        echo = {
            "id": f"old_camp_echo_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{rng.randint(100, 999)}",
            "type": "old_camp_echo",
            "status": "active",
            "kind": kind.get("key"),
            "label": kind.get("label", "回归旧营"),
            "summary": kind.get("summary", ""),
            "sourceLabel": kind.get("sourceLabel", "旧营"),
            "x": max(-490, min(490, float(center.get("x", 0) or 0) + math.cos(angle) * distance)),
            "z": max(-490, min(490, float(center.get("z", 0) or 0) + math.sin(angle) * distance)),
            "y": 0,
            "participants": [],
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_OLD_CAMP_ECHO_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["old_camp_echoes"] = [echo][-TRIBE_OLD_CAMP_ECHO_LIMIT:]
        return echo

    def _public_old_camp_echoes(self, tribe: dict) -> list:
        self._ensure_old_camp_echo(tribe)
        return [dict(echo) for echo in self._active_old_camp_echoes(tribe)]

    def _public_old_camp_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("old_camp_records", []) or [])
            if isinstance(record, dict)
        ][-TRIBE_OLD_CAMP_RECORD_LIMIT:]

    def _apply_old_camp_reward(self, tribe: dict, action: dict) -> list:
        parts = []
        reward = action.get("reward", {}) or {}
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("food", "食物", "food")
        ):
            amount = int(reward.get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(reward.get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        return parts

    async def revisit_old_camp_echo(self, player_id: str, echo_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_OLD_CAMP_ECHO_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知旧营行动")
            return
        echo = next((item for item in self._active_old_camp_echoes(tribe) if item.get("id") == echo_id), None)
        if not echo:
            await self._send_tribe_error(player_id, "这处旧营旧场已经沉寂")
            return
        if any(item.get("memberId") == player_id for item in echo.get("participants", []) or []):
            await self._send_tribe_error(player_id, "你已经处理过这处旧营旧场")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(action.get("woodCost", 0) or 0)
        food_cost = int(action.get("foodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"修复旧痕需要木材 {wood_cost}")
            return
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"带回旧物需要食物 {food_cost}")
            return
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost

        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        reward_parts = self._apply_old_camp_reward(tribe, action)
        participant = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "回归旧营"),
            "createdAt": now.isoformat()
        }
        echo.setdefault("participants", []).append(participant)
        echo["lastActionLabel"] = action.get("label", "回归旧营")
        echo["lastActorName"] = member_name
        echo["rewardLabel"] = "、".join(reward_parts)

        record = {
            "id": f"old_camp_record_{tribe_id}_{int(now.timestamp() * 1000)}_{len(tribe.get('old_camp_records', []) or [])}",
            "sourceKind": "old_camp_echo",
            "echoId": echo.get("id"),
            "echoKind": echo.get("kind"),
            "label": echo.get("label", "回归旧营"),
            "summary": echo.get("summary", ""),
            "sourceLabel": echo.get("sourceLabel", "旧营"),
            "actionKey": action_key,
            "actionLabel": action.get("recordLabel", action.get("label", "回归旧营")),
            "memberId": player_id,
            "memberName": member_name,
            "rewardParts": reward_parts,
            "collectionReady": bool(action.get("collectionReady")),
            "createdAt": now.isoformat()
        }
        tribe.setdefault("old_camp_records", []).append(record)
        tribe["old_camp_records"] = tribe["old_camp_records"][-TRIBE_OLD_CAMP_RECORD_LIMIT:]
        detail = f"{member_name}在{echo.get('label', '旧营旧场')}完成{action.get('label', '回归旧营')}：{'、'.join(reward_parts) or '旧事被重新记住'}。"
        if record.get("collectionReady"):
            detail += " 一件旧物可以整理进收藏墙。"
        self._add_tribe_history(tribe, "exploration", "回归旧营", detail, player_id, {"kind": "old_camp_echo", "record": record, "echo": echo})
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "exploration",
            "旧营旧场苏醒",
            f"{tribe.get('name', '某个部落')}在{echo.get('label', '旧营旧场')}重新整理了旧事。",
            {"tribeId": tribe_id, "echoId": echo.get("id"), "actionKey": action_key}
        )
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
