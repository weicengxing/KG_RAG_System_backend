import math
from datetime import datetime

from game_config import *


class GameCelebrationMixin:
    def _active_celebration_echoes(self, tribe: dict) -> list:
        now = datetime.now()
        active = []
        changed = False
        for echo in tribe.get("celebration_echoes", []) or []:
            if not isinstance(echo, dict) or echo.get("status") != "active":
                continue
            try:
                if datetime.fromisoformat(echo.get("activeUntil", "")) <= now:
                    echo["status"] = "expired"
                    echo["expiredAt"] = now.isoformat()
                    changed = True
                    continue
            except (TypeError, ValueError):
                echo["status"] = "expired"
                echo["expiredAt"] = now.isoformat()
                changed = True
                continue
            active.append(echo)
        if changed:
            tribe["celebration_echoes"] = active[-TRIBE_CELEBRATION_ECHO_LIMIT:]
        return active[-TRIBE_CELEBRATION_ECHO_LIMIT:]

    def _public_celebration_echoes(self, tribe: dict) -> list:
        echoes = []
        for echo in self._active_celebration_echoes(tribe):
            participants = list(echo.get("participants", []) or [])
            echoes.append({
                "id": echo.get("id"),
                "title": echo.get("title", "庆功余韵"),
                "label": echo.get("label", "庆功余韵"),
                "summary": echo.get("summary", ""),
                "sourceKind": echo.get("sourceKind"),
                "sourceLabel": echo.get("sourceLabel"),
                "anchorKey": echo.get("anchorKey"),
                "anchorLabel": echo.get("anchorLabel"),
                "x": echo.get("x", 0),
                "z": echo.get("z", 0),
                "rewardParts": self._celebration_reward_parts(echo.get("reward", {})),
                "participantCount": len(participants),
                "participants": participants[-6:],
                "createdAt": echo.get("createdAt"),
                "activeUntil": echo.get("activeUntil")
            })
        return echoes

    def _celebration_reward_parts(self, reward: dict) -> list:
        parts = []
        labels = {
            "renown": "声望",
            "tradeReputation": "贸易信誉",
            "discoveryProgress": "发现",
            "personalRenown": "个人声望"
        }
        for key, label in labels.items():
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                parts.append(f"{label}+{value}")
        return parts

    def _celebration_anchor(self, tribe: dict, anchor_key: str) -> dict:
        camp = tribe.get("camp") or {}
        buildings = list(camp.get("buildings", []) or [])
        wanted = {
            "totem": {"totem", "tribe_totem"},
            "campfire": {"campfire"},
            "road": {"road_marker", "tribe_road"}
        }.get(anchor_key, {"totem", "tribe_totem"})
        for building in buildings:
            if building.get("key") in wanted or building.get("type") in wanted:
                return building
        for building in buildings:
            if building.get("type") == "tribe_totem" or building.get("key") == "totem":
                return building
        return {
            "id": f"{tribe.get('id', 'tribe')}_camp",
            "label": camp.get("label") or f"{tribe.get('name', '部落')}营地",
            "x": camp.get("x", 0),
            "z": camp.get("z", 0)
        }

    def _create_celebration_echo(self, tribe: dict, source_kind: str, source_label: str = "", actor_id: str = "", source_id: str = "") -> dict | None:
        if not tribe:
            return None
        config = TRIBE_CELEBRATION_ECHO_SOURCES.get(source_kind)
        if not config:
            return None
        now = datetime.now()
        anchor = self._celebration_anchor(tribe, config.get("anchor", "totem"))
        echo = {
            "id": f"celebration_echo_{tribe.get('id')}_{source_kind}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "sourceKind": source_kind,
            "sourceId": source_id,
            "sourceLabel": source_label or config.get("title", "庆功"),
            "title": config.get("title", "庆功余韵"),
            "label": f"{config.get('title', '庆功余韵')} · {source_label or '营地记忆'}",
            "summary": config.get("summary", ""),
            "anchorKey": config.get("anchor", "totem"),
            "anchorLabel": anchor.get("label", "营地地标"),
            "x": anchor.get("x", 0),
            "z": anchor.get("z", 0),
            "reward": dict(config.get("reward", {})),
            "participants": [],
            "participantIds": [],
            "createdBy": actor_id,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_CELEBRATION_ECHO_ACTIVE_MINUTES * 60).isoformat()
        }
        echoes = [
            item for item in (tribe.get("celebration_echoes", []) or [])
            if isinstance(item, dict) and item.get("status") == "active"
        ]
        echoes.append(echo)
        tribe["celebration_echoes"] = echoes[-TRIBE_CELEBRATION_ECHO_LIMIT:]
        return echo

    def _near_celebration_echo(self, player_id: str, echo: dict) -> bool:
        player = self.players.get(player_id, {}) if hasattr(self, "players") else {}
        try:
            dx = float(player.get("x", 0) or 0) - float(echo.get("x", 0) or 0)
            dz = float(player.get("z", 0) or 0) - float(echo.get("z", 0) or 0)
        except (TypeError, ValueError):
            return False
        return math.sqrt(dx * dx + dz * dz) <= TRIBE_CELEBRATION_ECHO_RADIUS

    def _apply_celebration_echo_reward(self, tribe: dict, player_id: str, reward: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        personal = int((reward or {}).get("personalRenown", 0) or 0)
        if personal:
            player = self.players.setdefault(player_id, {})
            player["personal_renown"] = int(player.get("personal_renown", 0) or 0) + personal
            parts.append(f"个人声望+{personal}")
        return parts

    async def join_celebration_echo(self, player_id: str, echo_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        echo = next((item for item in self._active_celebration_echoes(tribe) if item.get("id") == echo_id), None)
        if not echo:
            await self._send_tribe_error(player_id, "这段庆功余韵已经散去")
            return
        if player_id in (echo.get("participantIds", []) or []):
            await self._send_tribe_error(player_id, "你已经加入过这段庆功余韵")
            return
        if not self._near_celebration_echo(player_id, echo):
            await self._send_tribe_error(player_id, f"需要靠近{echo.get('anchorLabel', '庆功地标')} {TRIBE_CELEBRATION_ECHO_RADIUS} 步内")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        reward_parts = self._apply_celebration_echo_reward(tribe, player_id, echo.get("reward", {}))
        participant = {
            "playerId": player_id,
            "memberName": member_name,
            "joinedAt": datetime.now().isoformat(),
            "rewardParts": reward_parts
        }
        echo.setdefault("participantIds", []).append(player_id)
        echo.setdefault("participants", []).append(participant)
        tribe.setdefault("celebration_echo_records", []).append({
            "id": f"celebration_record_{echo_id}_{player_id}",
            "echoId": echo_id,
            "title": echo.get("title", "庆功余韵"),
            "sourceLabel": echo.get("sourceLabel"),
            "memberName": member_name,
            "rewardParts": reward_parts,
            "createdAt": participant["joinedAt"]
        })
        tribe["celebration_echo_records"] = tribe["celebration_echo_records"][-TRIBE_CELEBRATION_ECHO_HISTORY_LIMIT:]

        detail = f"{member_name} 在{echo.get('anchorLabel', '营地地标')}加入{echo.get('label', '庆功余韵')}，{'、'.join(reward_parts) or '把名字留在庆功队列里'}。"
        self._add_tribe_history(tribe, "ritual", "庆功余韵", detail, player_id, {"kind": "celebration_echo", "echoId": echo_id, "sourceKind": echo.get("sourceKind")})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
