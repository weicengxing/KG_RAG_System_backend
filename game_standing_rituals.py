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
        puzzle = self._public_standing_ritual_puzzle(ritual)
        return {
            "id": ritual.get("id"),
            "key": ritual.get("key"),
            "label": ritual.get("label") or config.get("label", "站位仪式"),
            "summary": ritual.get("summary") or config.get("summary", ""),
            "puzzleSummary": config.get("puzzleSummary", ""),
            "puzzle": puzzle,
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
        if landmark_type == "tribe_camp" and landmark_tribe_id == tribe_id:
            return "camp"
        if landmark_type == "cave_entrance":
            return "cave"
        if landmark_type == "diplomacy_council_site":
            return "council"
        if landmark_type == "trade_route_site" and (landmark.get("isBorderMarket") or "边市" in label):
            return "market"
        return None

    def _standing_ritual_landmarks(self) -> list:
        landmarks = []
        if hasattr(self, "_get_base_landmarks"):
            landmarks.extend(self._get_base_landmarks())
        if hasattr(self, "_get_dynamic_tribe_landmarks"):
            landmarks.extend(self._get_dynamic_tribe_landmarks())
        return [item for item in landmarks if isinstance(item, dict)]

    def _standing_ritual_anchor(self, tribe: dict, ritual_key: str) -> dict:
        tribe_id = tribe.get("id")
        puzzle_config = TRIBE_STANDING_RITUAL_PUZZLES.get(ritual_key, {})
        anchor_kinds = set(puzzle_config.get("anchorKinds", []) or [])
        camp = tribe.get("camp") or {}
        center = camp.get("center") or {}
        fallback = {
            "id": f"{tribe_id}_standing_anchor",
            "label": f"{tribe.get('name', '部落')}营地",
            "x": float(center.get("x", 0) or 0),
            "z": float(center.get("z", 0) or 0),
            "kind": "camp"
        }
        if not anchor_kinds:
            return fallback
        best = None
        best_distance = float("inf")
        for landmark in self._standing_ritual_landmarks():
            kind = self._standing_ritual_landmark_kind(tribe_id, landmark)
            if kind not in anchor_kinds:
                continue
            try:
                dx = float(landmark.get("x", 0) or 0) - fallback["x"]
                dz = float(landmark.get("z", 0) or 0) - fallback["z"]
            except (TypeError, ValueError):
                continue
            distance = math.sqrt(dx * dx + dz * dz)
            if distance < best_distance:
                best = {
                    "id": landmark.get("id"),
                    "label": landmark.get("label", "仪式锚点"),
                    "x": float(landmark.get("x", 0) or 0),
                    "z": float(landmark.get("z", 0) or 0),
                    "kind": kind
                }
                best_distance = distance
        return best or fallback

    def _standing_ritual_context_hints(self, tribe: dict, ritual_key: str) -> list:
        hints = []
        env = self._current_environment() if hasattr(self, "_current_environment") else {}
        weather_key = env.get("weather", "sunny") if isinstance(env, dict) else "sunny"
        weather_label = self._weather_label(weather_key) if hasattr(self, "_weather_label") else WEATHER_LABELS.get(weather_key, weather_key)
        if weather_label:
            hints.append(f"天气提示：{weather_label}会让队列先确认{TRIBE_STANDING_RITUAL_DIRECTIONS['north']['label']}和火光方向。")
        celestial = env.get("celestialWindow") if isinstance(env, dict) and isinstance(env.get("celestialWindow"), dict) else None
        if ritual_key == "starwatch" and celestial:
            hints.append(f"天象提示：{celestial.get('title', '罕见天象')}把第一眼引向{TRIBE_STANDING_RITUAL_DIRECTIONS['north']['label']}。")
        memories = [item for item in tribe.get("map_memories", []) or [] if isinstance(item, dict)]
        if ritual_key == "cave" and memories:
            hints.append(f"地图记忆提示：{memories[-1].get('label', '旧路记号')}提醒队伍分守洞口两侧。")
        tunes = [item for item in tribe.get("traveler_song_tunes", []) or [] if isinstance(item, dict)]
        if tunes:
            hints.append(f"旧歌提示：{tunes[-1].get('title') or tunes[-1].get('label') or '公开曲牌'}把站位唱成先东后南。")
        return hints[:3]

    def _build_standing_ritual_puzzle(self, tribe: dict, ritual_key: str) -> dict | None:
        config = TRIBE_STANDING_RITUAL_PUZZLES.get(ritual_key)
        if not config:
            return None
        anchor = self._standing_ritual_anchor(tribe, ritual_key)
        slots = []
        for key in config.get("slots", []) or []:
            direction = TRIBE_STANDING_RITUAL_DIRECTIONS.get(key, {})
            slots.append({
                "key": key,
                "label": direction.get("label", key),
                "hint": direction.get("hint", "")
            })
        return {
            "hintLabel": config.get("hintLabel", "方位谜题"),
            "hintSummary": config.get("hintSummary", ""),
            "contextHints": self._standing_ritual_context_hints(tribe, ritual_key),
            "radius": TRIBE_STANDING_RITUAL_PUZZLE_RADIUS,
            "anchor": {
                "id": anchor.get("id"),
                "label": anchor.get("label"),
                "kind": anchor.get("kind"),
                "x": anchor.get("x", 0),
                "z": anchor.get("z", 0)
            },
            "slots": slots,
            "reward": dict(config.get("reward", {}))
        }

    def _standing_ritual_direction_key(self, anchor: dict, player_id: str) -> tuple[str, float] | tuple[None, None]:
        player = self.players.get(player_id, {}) if hasattr(self, "players") else {}
        try:
            dx = float(player.get("x", 0) or 0) - float(anchor.get("x", 0) or 0)
            dz = float(player.get("z", 0) or 0) - float(anchor.get("z", 0) or 0)
        except (TypeError, ValueError):
            return None, None
        distance = math.sqrt(dx * dx + dz * dz)
        if distance <= 0.5 or distance > TRIBE_STANDING_RITUAL_PUZZLE_RADIUS:
            return None, round(distance, 1)
        angle = (math.degrees(math.atan2(dz, dx)) + 360) % 360
        if 45 <= angle < 135:
            return "south", round(distance, 1)
        if 135 <= angle < 225:
            return "west", round(distance, 1)
        if 225 <= angle < 315:
            return "north", round(distance, 1)
        return "east", round(distance, 1)

    def _apply_standing_ritual_puzzle_slot(self, ritual: dict, player_id: str, participant: dict) -> None:
        puzzle = ritual.get("puzzle")
        if not isinstance(puzzle, dict):
            return
        anchor = puzzle.get("anchor") or {}
        direction_key, distance = self._standing_ritual_direction_key(anchor, player_id)
        participant["stationDistance"] = distance
        if not direction_key:
            return
        direction = TRIBE_STANDING_RITUAL_DIRECTIONS.get(direction_key, {})
        required = {slot.get("key") for slot in puzzle.get("slots", []) if isinstance(slot, dict)}
        participant["stationKey"] = direction_key
        participant["stationLabel"] = direction.get("label", direction_key)
        participant["stationMatched"] = direction_key in required

    def _standing_ritual_puzzle_result(self, ritual: dict) -> dict | None:
        puzzle = ritual.get("puzzle")
        if not isinstance(puzzle, dict):
            return None
        participants = [item for item in ritual.get("participants", []) or [] if isinstance(item, dict)]
        filled = {}
        for item in participants:
            key = item.get("stationKey")
            if key and item.get("stationMatched") and key not in filled:
                filled[key] = item
        slots = []
        missing = []
        for slot in puzzle.get("slots", []) or []:
            key = slot.get("key")
            occupant = filled.get(key)
            public_slot = dict(slot)
            if occupant:
                public_slot["filled"] = True
                public_slot["playerId"] = occupant.get("playerId")
                public_slot["name"] = occupant.get("name")
                public_slot["stanceLabel"] = occupant.get("stanceLabel")
            else:
                public_slot["filled"] = False
                missing.append(slot.get("label", key))
            slots.append(public_slot)
        return {
            "slots": slots,
            "filledCount": len(filled),
            "target": len(slots),
            "missingLabels": missing,
            "completed": bool(slots) and not missing
        }

    def _public_standing_ritual_puzzle(self, ritual: dict) -> dict | None:
        puzzle = ritual.get("puzzle")
        if not isinstance(puzzle, dict):
            return None
        result = self._standing_ritual_puzzle_result(ritual) or {}
        return {
            "hintLabel": puzzle.get("hintLabel", "方位谜题"),
            "hintSummary": puzzle.get("hintSummary", ""),
            "contextHints": list(puzzle.get("contextHints", []) or []),
            "radius": puzzle.get("radius", TRIBE_STANDING_RITUAL_PUZZLE_RADIUS),
            "anchor": puzzle.get("anchor"),
            "reward": dict(puzzle.get("reward", {})),
            **result
        }

    def _standing_ritual_location_bonus(self, tribe: dict, player_id: str) -> dict | None:
        player = self.players.get(player_id, {}) if hasattr(self, "players") else {}
        try:
            player_x = float(player.get("x", 0) or 0)
            player_z = float(player.get("z", 0) or 0)
        except (TypeError, ValueError):
            return None

        tribe_id = tribe.get("id")
        nearest = None
        nearest_distance = float("inf")
        for landmark in self._standing_ritual_landmarks():
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
            "target": len((TRIBE_STANDING_RITUAL_PUZZLES.get(ritual_key, {}) or {}).get("slots", []) or []) or TRIBE_STANDING_RITUAL_TARGET_PARTICIPANTS,
            "createdBy": player_id,
            "createdByName": member.get("name", "管理者"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_STANDING_RITUAL_ACTIVE_MINUTES * 60).isoformat()
        }
        puzzle = self._build_standing_ritual_puzzle(tribe, ritual_key)
        if puzzle:
            ritual["puzzle"] = puzzle
        tribe["standing_ritual"] = ritual
        detail = f"{member.get('name', '管理者')} 发起{ritual['label']}：{ritual['summary']} 成员可以选择站位并携带少量资源。"
        if puzzle:
            slot_labels = "、".join(slot.get("label", "") for slot in puzzle.get("slots", []))
            detail += f" 方位谜题需要围绕{puzzle.get('anchor', {}).get('label', '仪式锚点')}站满{slot_labels}。"
        self._add_tribe_history(tribe, "ritual", "发起站位仪式", detail, player_id, {"kind": "standing_ritual", "ritual": ritual})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

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
        self._apply_standing_ritual_puzzle_slot(ritual, player_id, participant)
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
        if participant.get("stationLabel"):
            if participant.get("stationMatched"):
                detail += f" 已站到{participant.get('stationLabel')}。"
            else:
                detail += f" 站在{participant.get('stationLabel')}，但不是本次提示方位。"
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
        puzzle_result = self._standing_ritual_puzzle_result(ritual)
        if puzzle_result and not puzzle_result.get("completed"):
            missing = "、".join(puzzle_result.get("missingLabels", []) or [])
            await self._send_tribe_error(player_id, f"方位谜题还缺：{missing or '正确方位'}")
            return
        config = TRIBE_STANDING_RITUAL_OPTIONS.get(ritual.get("key"), {})
        reward_parts = self._apply_standing_ritual_reward(tribe, config.get("reward", {}))
        if len(participants) >= int(ritual.get("target", TRIBE_STANDING_RITUAL_TARGET_PARTICIPANTS) or TRIBE_STANDING_RITUAL_TARGET_PARTICIPANTS):
            reward_parts.extend(self._apply_standing_ritual_reward(tribe, config.get("fullReward", {})))
        if puzzle_result:
            reward_parts.extend(self._apply_standing_ritual_reward(tribe, (ritual.get("puzzle") or {}).get("reward", {})))
        ritual["status"] = "completed"
        ritual["completedAt"] = datetime.now().isoformat()
        ritual["completedBy"] = player_id
        ritual["puzzleResult"] = puzzle_result
        tribe.setdefault("standing_ritual_history", []).append(ritual)
        tribe["standing_ritual_history"] = tribe["standing_ritual_history"][-TRIBE_STANDING_RITUAL_HISTORY_LIMIT:]

        stance_labels = "、".join([item.get("stanceLabel", "见证者") for item in participants])
        detail = f"{member.get('name', '管理者')} 收束{ritual.get('label', '站位仪式')}，{len(participants)} 名成员完成站位：{stance_labels}。{'、'.join(reward_parts) or '仪式已写入历史'}。"
        if puzzle_result:
            slot_labels = "、".join([slot.get("label", "") for slot in puzzle_result.get("slots", [])])
            detail += f" 方位谜题已对齐：{slot_labels}。"
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
