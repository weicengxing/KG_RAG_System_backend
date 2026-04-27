import math
from datetime import datetime

from game_config import *


class GameDrumRhythmMixin:
    def _active_drum_rhythm(self, tribe: dict) -> dict | None:
        rhythm = tribe.get("drum_rhythm")
        if not isinstance(rhythm, dict) or rhythm.get("status") != "active":
            return None
        try:
            if datetime.fromisoformat(rhythm.get("activeUntil", "")) <= datetime.now():
                rhythm["status"] = "expired"
                rhythm["expiredAt"] = datetime.now().isoformat()
                return None
        except (TypeError, ValueError):
            rhythm["status"] = "expired"
            rhythm["expiredAt"] = datetime.now().isoformat()
            return None
        return rhythm

    def _public_drum_rhythm(self, tribe: dict) -> dict | None:
        rhythm = self._active_drum_rhythm(tribe)
        if not rhythm:
            return None
        participants = list(rhythm.get("participants", []) or [])
        return {
            "id": rhythm.get("id"),
            "key": rhythm.get("key"),
            "label": rhythm.get("label"),
            "summary": rhythm.get("summary"),
            "locationLabel": rhythm.get("locationLabel"),
            "participants": participants[-6:],
            "participantCount": len(participants),
            "target": int(rhythm.get("target", TRIBE_DRUM_RHYTHM_TARGET_PARTICIPANTS) or TRIBE_DRUM_RHYTHM_TARGET_PARTICIPANTS),
            "minParticipants": TRIBE_DRUM_RHYTHM_MIN_PARTICIPANTS,
            "radius": TRIBE_DRUM_RHYTHM_RADIUS,
            "createdByName": rhythm.get("createdByName"),
            "createdAt": rhythm.get("createdAt"),
            "activeUntil": rhythm.get("activeUntil")
        }

    def _nearby_drum_landmark(self, tribe: dict, player_id: str) -> dict | None:
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
        camp = tribe.get("camp") or {}
        for building in camp.get("buildings", []) or []:
            if building.get("type") in {"tribe_totem", "campfire"}:
                landmarks.append(building)

        nearest = None
        nearest_distance = float("inf")
        for landmark in landmarks:
            if not isinstance(landmark, dict):
                continue
            landmark_type = landmark.get("type")
            landmark_tribe_id = landmark.get("tribeId")
            if landmark_type not in {"tribe_totem", "campfire"}:
                continue
            if landmark_tribe_id and landmark_tribe_id != tribe_id:
                continue
            try:
                dx = float(landmark.get("x", 0) or 0) - player_x
                dz = float(landmark.get("z", 0) or 0) - player_z
            except (TypeError, ValueError):
                continue
            distance = math.sqrt(dx * dx + dz * dz)
            if distance < nearest_distance:
                nearest = landmark
                nearest_distance = distance

        if not nearest or nearest_distance > TRIBE_DRUM_RHYTHM_RADIUS:
            return None
        return {
            "id": nearest.get("id"),
            "type": nearest.get("type"),
            "label": nearest.get("label", "图腾或营火"),
            "distance": round(nearest_distance, 1)
        }

    def _apply_drum_rhythm_reward(self, tribe: dict, reward: dict) -> list:
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
        pressure_relief = int(reward.get("warPressureRelief", 0) or 0)
        if pressure_relief:
            relieved = self._relieve_drum_war_pressure(tribe, pressure_relief)
            if relieved:
                parts.append(f"战争压力-{pressure_relief}（{relieved}条边界）")
        return parts

    def _relieve_drum_war_pressure(self, tribe: dict, amount: int) -> int:
        tribe_id = tribe.get("id")
        relieved = 0
        for other_id, relation in list((tribe.get("boundary_relations") or {}).items()):
            if not isinstance(relation, dict):
                continue
            current = int(relation.get("warPressure", 0) or 0)
            if current <= 0:
                continue
            relation["warPressure"] = max(0, current - amount)
            relation["canDeclareWar"] = relation["warPressure"] >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relation["lastAction"] = "drum_rhythm_relief"
            relation["lastActionAt"] = datetime.now().isoformat()
            other_tribe = self.tribes.get(other_id) if hasattr(self, "tribes") else None
            if other_tribe and tribe_id:
                other_relation = other_tribe.setdefault("boundary_relations", {}).setdefault(tribe_id, {})
                other_current = int(other_relation.get("warPressure", 0) or 0)
                if other_current > 0:
                    other_relation["warPressure"] = max(0, other_current - amount)
                    other_relation["canDeclareWar"] = other_relation["warPressure"] >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                    other_relation["lastAction"] = "incoming_drum_rhythm_relief"
                    other_relation["lastActionAt"] = relation["lastActionAt"]
            relieved += 1
        return relieved

    async def start_drum_rhythm(self, player_id: str, rhythm_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if self._active_drum_rhythm(tribe):
            await self._send_tribe_error(player_id, "当前已经有鼓点节奏正在进行")
            return
        config = TRIBE_DRUM_RHYTHM_OPTIONS.get(rhythm_key)
        if not config:
            await self._send_tribe_error(player_id, "未知鼓点节奏")
            return
        landmark = self._nearby_drum_landmark(tribe, player_id)
        if not landmark:
            await self._send_tribe_error(player_id, f"需要靠近本部落图腾或营火 {TRIBE_DRUM_RHYTHM_RADIUS} 步内才能起鼓")
            return

        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        rhythm = {
            "id": f"drum_rhythm_{tribe_id}_{int(now.timestamp() * 1000)}",
            "key": rhythm_key,
            "label": config.get("label", "鼓点节奏"),
            "summary": config.get("summary", ""),
            "status": "active",
            "participants": [],
            "participantIds": [],
            "target": TRIBE_DRUM_RHYTHM_TARGET_PARTICIPANTS,
            "location": landmark,
            "locationLabel": landmark.get("label", "图腾或营火"),
            "createdBy": player_id,
            "createdByName": member.get("name", "成员"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_DRUM_RHYTHM_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["drum_rhythm"] = rhythm
        detail = f"{member.get('name', '成员')} 在{rhythm['locationLabel']}旁起了{rhythm['label']}，需要多人选择鼓拍回应。"
        self._add_tribe_history(tribe, "ritual", "起鼓", detail, player_id, {"kind": "drum_rhythm", "rhythm": rhythm})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def join_drum_rhythm(self, player_id: str, beat_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        rhythm = self._active_drum_rhythm(tribe)
        if not rhythm:
            await self._send_tribe_error(player_id, "当前没有可以加入的鼓点节奏")
            return
        if player_id in (rhythm.get("participantIds", []) or []):
            await self._send_tribe_error(player_id, "你已经回应过这次鼓点")
            return
        beat = TRIBE_DRUM_RHYTHM_BEATS.get(beat_key)
        if not beat:
            await self._send_tribe_error(player_id, "未知鼓拍")
            return
        landmark = self._nearby_drum_landmark(tribe, player_id)
        if not landmark:
            await self._send_tribe_error(player_id, f"需要靠近本部落图腾或营火 {TRIBE_DRUM_RHYTHM_RADIUS} 步内才能应鼓")
            return

        member = tribe.get("members", {}).get(player_id, {})
        participant = {
            "playerId": player_id,
            "name": member.get("name", "成员"),
            "beatKey": beat_key,
            "beatLabel": beat.get("label", "鼓拍"),
            "locationLabel": landmark.get("label", "图腾或营火"),
            "joinedAt": datetime.now().isoformat()
        }
        rhythm.setdefault("participantIds", []).append(player_id)
        rhythm.setdefault("participants", []).append(participant)
        self.players.setdefault(player_id, {})["personal_renown"] = int(self.players.get(player_id, {}).get("personal_renown", 0) or 0) + 1
        reward_parts = self._apply_drum_rhythm_reward(tribe, beat)
        detail = f"{participant['name']} 在{participant['locationLabel']}旁敲出{participant['beatLabel']}，鼓点进度 {len(rhythm.get('participants', []))}/{rhythm.get('target', TRIBE_DRUM_RHYTHM_TARGET_PARTICIPANTS)}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "ritual", "回应鼓点", detail, player_id, {"kind": "drum_rhythm_join", "rhythmId": rhythm.get("id"), "beatKey": beat_key})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_drum_rhythm(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        rhythm = self._active_drum_rhythm(tribe)
        if not rhythm:
            await self._send_tribe_error(player_id, "当前没有可以收束的鼓点节奏")
            return
        participants = list(rhythm.get("participants", []) or [])
        if len(participants) < TRIBE_DRUM_RHYTHM_MIN_PARTICIPANTS:
            await self._send_tribe_error(player_id, f"至少需要 {TRIBE_DRUM_RHYTHM_MIN_PARTICIPANTS} 名成员回应鼓点")
            return
        config = TRIBE_DRUM_RHYTHM_OPTIONS.get(rhythm.get("key"), {})
        reward_parts = self._apply_drum_rhythm_reward(tribe, config.get("reward", {}))
        if len(participants) >= int(rhythm.get("target", TRIBE_DRUM_RHYTHM_TARGET_PARTICIPANTS) or TRIBE_DRUM_RHYTHM_TARGET_PARTICIPANTS):
            reward_parts.extend(self._apply_drum_rhythm_reward(tribe, config.get("fullReward", {})))
        rhythm["status"] = "completed"
        rhythm["completedAt"] = datetime.now().isoformat()
        rhythm["completedBy"] = player_id
        rhythm["rewardParts"] = reward_parts
        tribe.setdefault("drum_rhythm_history", []).append(rhythm)
        tribe["drum_rhythm_history"] = tribe["drum_rhythm_history"][-TRIBE_DRUM_RHYTHM_HISTORY_LIMIT:]

        member = tribe.get("members", {}).get(player_id, {})
        beat_labels = "、".join([item.get("beatLabel", "鼓拍") for item in participants])
        detail = f"{member.get('name', '成员')} 收束{rhythm.get('label', '鼓点节奏')}，{len(participants)} 名成员完成鼓拍：{beat_labels}。{'、'.join(reward_parts) or '鼓声写入部落历史'}。"
        self._add_tribe_history(tribe, "ritual", "鼓点节奏完成", detail, player_id, {"kind": "drum_rhythm_complete", "rhythm": rhythm, "rewardParts": reward_parts})
        await self._publish_world_rumor(
            "ritual",
            "鼓点节奏",
            f"{tribe.get('name', '部落')} 在{rhythm.get('locationLabel', '图腾或营火')}旁完成{rhythm.get('label', '鼓点节奏')}，把{beat_labels}传进了共同记忆。",
            {"tribeId": tribe_id, "rhythmKey": rhythm.get("key")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
