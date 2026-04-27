import math
from datetime import datetime

from game_config import *


class GameStandingRitualMixin:
    def _active_standing_ritual(self, tribe: dict) -> dict | None:
        ritual = tribe.get("standing_ritual")
        if not isinstance(ritual, dict) or ritual.get("status") != "active":
            return None
        try:
            if datetime.fromisoformat(ritual.get("activeUntil", "")) <= datetime.now():
                ritual["status"] = "expired"
                ritual["expiredAt"] = datetime.now().isoformat()
                return None
        except (TypeError, ValueError):
            ritual["status"] = "expired"
            ritual["expiredAt"] = datetime.now().isoformat()
            return None
        return ritual

    def _public_standing_ritual(self, tribe: dict) -> dict | None:
        ritual = self._active_standing_ritual(tribe)
        if not ritual:
            return None
        config = TRIBE_STANDING_RITUAL_OPTIONS.get(ritual.get("key"), {})
        participants = list(ritual.get("participants", []) or [])
        return {
            "id": ritual.get("id"),
            "key": ritual.get("key"),
            "label": ritual.get("label") or config.get("label", "站位仪式"),
            "summary": ritual.get("summary") or config.get("summary", ""),
            "participants": participants[-6:],
            "participantCount": len(participants),
            "target": int(ritual.get("target", TRIBE_STANDING_RITUAL_TARGET_PARTICIPANTS) or TRIBE_STANDING_RITUAL_TARGET_PARTICIPANTS),
            "minParticipants": TRIBE_STANDING_RITUAL_MIN_PARTICIPANTS,
            "landmarkRadius": TRIBE_STANDING_RITUAL_LANDMARK_RADIUS,
            "landmarkBonuses": TRIBE_STANDING_RITUAL_LANDMARK_BONUSES,
            "createdAt": ritual.get("createdAt"),
            "activeUntil": ritual.get("activeUntil")
        }

    def _standing_ritual_landmark_kind(self, tribe_id: str | None, landmark: dict) -> str | None:
        landmark_type = landmark.get("type")
        label = str(landmark.get("label", ""))
        landmark_tribe_id = landmark.get("tribeId")
        if landmark_type == "tribe_totem" and (not landmark_tribe_id or landmark_tribe_id == tribe_id):
            return "totem"
        if landmark_type == "cave_entrance":
            return "cave"
        if landmark_type == "diplomacy_council_site":
            return "council"
        if landmark_type == "trade_route_site" and (landmark.get("isBorderMarket") or "边市" in label):
            return "market"
        return None

    def _standing_ritual_location_bonus(self, tribe: dict, player_id: str) -> dict | None:
        player = self.players.get(player_id, {}) if hasattr(self, "players") else {}
        try:
            player_x = float(player.get("x", 0) or 0)
            player_z = float(player.get("z", 0) or 0)
        except (TypeError, ValueError):
            return None

        tribe_id = tribe.get("id")
        landmarks = []
        if hasattr(self, "_get_base_landmarks"):
            landmarks.extend(self._get_base_landmarks())
        if hasattr(self, "_get_dynamic_tribe_landmarks"):
            landmarks.extend(self._get_dynamic_tribe_landmarks())

        nearest = None
        nearest_distance = float("inf")
        for landmark in landmarks:
            if not isinstance(landmark, dict):
                continue
            kind = self._standing_ritual_landmark_kind(tribe_id, landmark)
            if not kind:
                continue
            try:
                dx = float(landmark.get("x", 0) or 0) - player_x
                dz = float(landmark.get("z", 0) or 0) - player_z
            except (TypeError, ValueError):
                continue
            distance = math.sqrt(dx * dx + dz * dz)
            if distance < nearest_distance:
                nearest = (kind, landmark, distance)
                nearest_distance = distance

        if not nearest or nearest_distance > TRIBE_STANDING_RITUAL_LANDMARK_RADIUS:
            return None
        kind, landmark, distance = nearest
        config = TRIBE_STANDING_RITUAL_LANDMARK_BONUSES.get(kind, {})
        if not config:
            return None
        return {
            "kind": kind,
            "label": config.get("label", "地标站位"),
            "summary": config.get("summary", ""),
            "landmarkId": landmark.get("id"),
            "landmarkLabel": landmark.get("label", "附近地标"),
            "distance": round(distance, 1),
            "reward": dict(config.get("reward", {}))
        }

    def _apply_standing_ritual_reward(self, tribe: dict, reward: dict) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石材")):
            value = int(reward.get(key, 0) or 0)
            if value:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + value)
                reward_parts.append(f"{label}{value:+d}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            value = int(reward.get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                reward_parts.append(f"{label}+{value}")
        return reward_parts

    async def start_standing_ritual(self, player_id: str, ritual_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以发起站位仪式")
            return
        if self._active_standing_ritual(tribe):
            await self._send_tribe_error(player_id, "当前已经有站位仪式正在进行")
            return
        config = TRIBE_STANDING_RITUAL_OPTIONS.get(ritual_key)
        if not config:
            await self._send_tribe_error(player_id, "未知站位仪式")
            return

        now = datetime.now()
        ritual = {
            "id": f"standing_ritual_{tribe_id}_{int(now.timestamp() * 1000)}",
            "key": ritual_key,
            "label": config.get("label", "站位仪式"),
            "summary": config.get("summary", ""),
            "status": "active",
            "participants": [],
            "participantIds": [],
            "target": TRIBE_STANDING_RITUAL_TARGET_PARTICIPANTS,
            "createdBy": player_id,
            "createdByName": member.get("name", "管理者"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_STANDING_RITUAL_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["standing_ritual"] = ritual
        detail = f"{member.get('name', '管理者')} 发起{ritual['label']}：{ritual['summary']} 成员可以选择站位并携带少量资源。"
        self._add_tribe_history(tribe, "ritual", "发起站位仪式", detail, player_id, {"kind": "standing_ritual", "ritual": ritual})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def join_standing_ritual(self, player_id: str, stance_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        ritual = self._active_standing_ritual(tribe)
        if not ritual:
            await self._send_tribe_error(player_id, "当前没有可以加入的站位仪式")
            return
        if player_id in (ritual.get("participantIds", []) or []):
            await self._send_tribe_error(player_id, "你已经在这次仪式中站位")
            return
        stance = TRIBE_STANDING_RITUAL_STANCES.get(stance_key)
        if not stance:
            await self._send_tribe_error(player_id, "未知站位")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(stance.get("woodCost", 0) or 0)
        stone_cost = int(stance.get("stoneCost", 0) or 0)
        food_cost = int(stance.get("foodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"站位需要木材 {wood_cost}")
            return
        if stone_cost and int(storage.get("stone", 0) or 0) < stone_cost:
            await self._send_tribe_error(player_id, f"站位需要石材 {stone_cost}")
            return
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"站位需要食物 {food_cost}")
            return
        storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        storage["stone"] = int(storage.get("stone", 0) or 0) - stone_cost
        tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost

        member = tribe.get("members", {}).get(player_id, {})
        participant = {
            "playerId": player_id,
            "name": member.get("name", "成员"),
            "role": member.get("role", "member"),
            "stanceKey": stance_key,
            "stanceLabel": stance.get("label", "见证者"),
            "joinedAt": datetime.now().isoformat()
        }
        ritual.setdefault("participantIds", []).append(player_id)
        reward_parts = self._apply_standing_ritual_reward(tribe, stance)
        location_bonus = self._standing_ritual_location_bonus(tribe, player_id)
        if location_bonus:
            bonus_parts = self._apply_standing_ritual_reward(tribe, location_bonus.get("reward", {}))
            reward_parts.extend(bonus_parts)
            participant["locationBonus"] = {
                "kind": location_bonus.get("kind"),
                "label": location_bonus.get("label"),
                "landmarkLabel": location_bonus.get("landmarkLabel"),
                "distance": location_bonus.get("distance"),
                "rewardParts": bonus_parts
            }
        ritual.setdefault("participants", []).append(participant)
        detail = f"{participant['name']} 以{participant['stanceLabel']}加入{ritual.get('label', '站位仪式')}，当前 {len(ritual.get('participants', []))} / {ritual.get('target', 0)}。"
        if location_bonus:
            detail += f" 靠近{location_bonus.get('landmarkLabel', '地标')}触发{location_bonus.get('label', '地标加成')}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(
            tribe,
            "ritual",
            "加入站位仪式",
            detail,
            player_id,
            {
                "kind": "standing_ritual_join",
                "ritualId": ritual.get("id"),
                "stanceKey": stance_key,
                "locationBonus": participant.get("locationBonus")
            }
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_standing_ritual(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        ritual = self._active_standing_ritual(tribe)
        if not ritual:
            await self._send_tribe_error(player_id, "当前没有可以完成的站位仪式")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以收束站位仪式")
            return
        participants = list(ritual.get("participants", []) or [])
        if len(participants) < TRIBE_STANDING_RITUAL_MIN_PARTICIPANTS:
            await self._send_tribe_error(player_id, f"至少需要 {TRIBE_STANDING_RITUAL_MIN_PARTICIPANTS} 名成员站位")
            return
        config = TRIBE_STANDING_RITUAL_OPTIONS.get(ritual.get("key"), {})
        reward_parts = self._apply_standing_ritual_reward(tribe, config.get("reward", {}))
        if len(participants) >= int(ritual.get("target", TRIBE_STANDING_RITUAL_TARGET_PARTICIPANTS) or TRIBE_STANDING_RITUAL_TARGET_PARTICIPANTS):
            reward_parts.extend(self._apply_standing_ritual_reward(tribe, config.get("fullReward", {})))
        ritual["status"] = "completed"
        ritual["completedAt"] = datetime.now().isoformat()
        ritual["completedBy"] = player_id
        tribe.setdefault("standing_ritual_history", []).append(ritual)
        tribe["standing_ritual_history"] = tribe["standing_ritual_history"][-TRIBE_STANDING_RITUAL_HISTORY_LIMIT:]

        stance_labels = "、".join([item.get("stanceLabel", "见证者") for item in participants])
        detail = f"{member.get('name', '管理者')} 收束{ritual.get('label', '站位仪式')}，{len(participants)} 名成员完成站位：{stance_labels}。{'、'.join(reward_parts) or '仪式已写入历史'}。"
        self._add_tribe_history(tribe, "ritual", "完成站位仪式", detail, player_id, {"kind": "standing_ritual_complete", "ritual": ritual, "rewardParts": reward_parts})
        if hasattr(self, "_create_celebration_echo"):
            self._create_celebration_echo(tribe, "ritual", ritual.get("label", "站位仪式"), player_id, ritual.get("id", ""))
        await self._publish_world_rumor(
            "ritual",
            "多人站位仪式",
            f"{tribe.get('name', '部落')} 完成{ritual.get('label', '站位仪式')}，把{stance_labels}写进了共同传闻。",
            {"tribeId": tribe_id, "ritualKey": ritual.get("key")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
