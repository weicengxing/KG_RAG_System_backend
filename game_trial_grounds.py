import math
import random
from datetime import datetime

from game_config import *


class GameTrialGroundMixin:
    def _trial_ground_rng(self):
        return getattr(self, "_weather_rng", random)

    def _active_trial_grounds(self, tribe: dict) -> list:
        if not tribe:
            return []
        active = []
        now = datetime.now()
        for trial in tribe.get("trial_grounds", []) or []:
            if not isinstance(trial, dict) or trial.get("status", "active") != "active":
                continue
            active_until = trial.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        trial["status"] = "expired"
                        trial["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    trial["status"] = "expired"
                    trial["expiredAt"] = now.isoformat()
                    continue
            active.append(trial)
        tribe["trial_grounds"] = active[-TRIBE_TRIAL_GROUND_LIMIT:]
        return tribe["trial_grounds"]

    def _ensure_trial_ground(self, tribe: dict):
        if not tribe:
            return None
        active = self._active_trial_grounds(tribe)
        if active:
            return active[0]
        camp = tribe.get("camp") or {}
        center = camp.get("center") or {}
        if not center:
            return None
        rng = self._trial_ground_rng()
        angle = rng.random() * math.tau
        distance = 20 + rng.random() * 34
        now = datetime.now()
        trial = {
            "id": f"trial_ground_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{rng.randint(100, 999)}",
            "type": "trial_ground",
            "status": "active",
            "label": "营地试炼场",
            "summary": "一片被木牌、石线和火灰标出的非致命挑战场，成员可以选择不同试炼留下成绩。",
            "x": max(-490, min(490, float(center.get("x", 0) or 0) + math.cos(angle) * distance)),
            "z": max(-490, min(490, float(center.get("z", 0) or 0) + math.sin(angle) * distance)),
            "y": 0,
            "size": 1.0,
            "radius": TRIBE_TRIAL_GROUND_RADIUS,
            "participants": [],
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_TRIAL_GROUND_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["trial_grounds"] = [trial][-TRIBE_TRIAL_GROUND_LIMIT:]
        return trial

    def _public_trial_grounds(self, tribe: dict) -> list:
        self._ensure_trial_ground(tribe)
        return [dict(trial) for trial in self._active_trial_grounds(tribe)]

    def _public_trial_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("trial_ground_records", []) or [])
            if isinstance(record, dict)
        ][-TRIBE_TRIAL_GROUND_RECORD_LIMIT:]

    def _apply_trial_ground_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        return parts

    def _apply_trial_pressure_relief(self, tribe: dict, amount: int) -> int:
        if amount <= 0:
            return 0
        relieved = 0
        for relation in (tribe.get("boundary_relations", {}) or {}).values():
            if not isinstance(relation, dict):
                continue
            before = int(relation.get("warPressure", 0) or 0)
            after = max(0, before - amount)
            relation["warPressure"] = after
            relation["canDeclareWar"] = after >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relieved += before - after
        return relieved

    def _near_trial_ground(self, player_id: str, trial: dict) -> bool:
        player = self.players.get(player_id, {}) if hasattr(self, "players") else {}
        dx = float(player.get("x", 0) or 0) - float(trial.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(trial.get("z", 0) or 0)
        return math.sqrt(dx * dx + dz * dz) <= float(trial.get("radius", TRIBE_TRIAL_GROUND_RADIUS) or TRIBE_TRIAL_GROUND_RADIUS)

    async def complete_trial_ground(self, player_id: str, trial_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_TRIAL_GROUND_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知试炼")
            return
        trial = next((item for item in self._active_trial_grounds(tribe) if item.get("id") == trial_id), None)
        if not trial:
            await self._send_tribe_error(player_id, "这处试炼场已经撤下")
            return
        if any(item.get("memberId") == player_id for item in trial.get("participants", []) or []):
            await self._send_tribe_error(player_id, "你已经完成过这处试炼")
            return
        if not self._near_trial_ground(player_id, trial):
            await self._send_tribe_error(player_id, f"需要靠近试炼场 {TRIBE_TRIAL_GROUND_RADIUS} 步内")
            return

        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", self.players.get(player_id, {}).get("name", "成员"))
        reward_parts = self._apply_trial_ground_reward(tribe, action.get("reward", {}))
        relieved = self._apply_trial_pressure_relief(tribe, int(action.get("pressureRelief", 0) or 0))
        if relieved:
            reward_parts.append(f"战争压力-{relieved}")
        title = action.get("title", "试炼完成者")
        participant = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "试炼"),
            "title": title,
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        trial.setdefault("participants", []).append(participant)
        trial["lastActionLabel"] = action.get("label", "试炼")
        trial["lastActorName"] = member_name
        record = {
            "id": f"trial_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "trialId": trial.get("id"),
            "label": trial.get("label", "营地试炼场"),
            "actionKey": action_key,
            "actionLabel": action.get("label", "试炼"),
            "title": title,
            "memberId": player_id,
            "memberName": member_name,
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        tribe.setdefault("trial_ground_records", []).append(record)
        tribe["trial_ground_records"] = tribe["trial_ground_records"][-TRIBE_TRIAL_GROUND_RECORD_LIMIT:]
        detail = f"{member_name}在{trial.get('label', '试炼场')}完成{action.get('label', '试炼')}，被记为“{title}”。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "ritual", "营地试炼", detail, player_id, {"kind": "trial_ground", "record": record, "trial": trial})
        if int(action.get("pressureRelief", 0) or 0) or int((action.get("reward", {}) or {}).get("renown", 0) or 0) >= 2:
            await self._publish_world_rumor(
                "ritual",
                "营地试炼",
                f"{tribe.get('name', '某个部落')}在试炼场记下了“{title}”。",
                {"tribeId": tribe_id, "trialId": trial.get("id"), "actionKey": action_key}
            )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    def _active_camp_trial(self, tribe: dict) -> dict | None:
        trial = tribe.get("camp_trial_ground")
        if not isinstance(trial, dict) or trial.get("status") != "active":
            return None
        active_until = trial.get("activeUntil")
        if active_until:
            try:
                if datetime.fromisoformat(active_until) <= datetime.now():
                    trial["status"] = "expired"
                    trial["expiredAt"] = datetime.now().isoformat()
                    return None
            except (TypeError, ValueError):
                trial["status"] = "expired"
                trial["expiredAt"] = datetime.now().isoformat()
                return None
        return trial

    def _public_camp_trial(self, tribe: dict) -> dict | None:
        trial = self._active_camp_trial(tribe)
        if not trial:
            return None
        participants = list(trial.get("participants", []) or [])
        return {
            "id": trial.get("id"),
            "trialKey": trial.get("trialKey"),
            "label": trial.get("label"),
            "summary": trial.get("summary"),
            "createdByName": trial.get("createdByName"),
            "participants": participants[-8:],
            "participantCount": len(participants),
            "target": int(trial.get("target", TRIBE_CAMP_TRIAL_TARGET) or TRIBE_CAMP_TRIAL_TARGET),
            "minParticipants": TRIBE_CAMP_TRIAL_MIN_PARTICIPANTS,
            "createdAt": trial.get("createdAt"),
            "activeUntil": trial.get("activeUntil")
        }

    def _public_camp_trial_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("camp_trial_records", []) or [])
            if isinstance(record, dict)
        ][-TRIBE_CAMP_TRIAL_RECORD_LIMIT:]

    def _member_can_manage_camp_trial(self, tribe: dict, player_id: str) -> bool:
        member = (tribe.get("members", {}) or {}).get(player_id, {})
        return member.get("role") in ("leader", "elder")

    async def start_camp_trial(self, player_id: str, trial_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not self._member_can_manage_camp_trial(tribe, player_id):
            await self._send_tribe_error(player_id, "只有首领或长老可以开启营地试炼")
            return
        if self._active_camp_trial(tribe):
            await self._send_tribe_error(player_id, "当前已经有营地试炼正在进行")
            return
        option = TRIBE_CAMP_TRIAL_OPTIONS.get(trial_key)
        if not option:
            await self._send_tribe_error(player_id, "未知营地试炼")
            return

        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        trial = {
            "id": f"camp_trial_{tribe_id}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "trialKey": trial_key,
            "label": option.get("label", "营地试炼"),
            "summary": option.get("summary", ""),
            "participantIds": [],
            "participants": [],
            "target": TRIBE_CAMP_TRIAL_TARGET,
            "createdBy": player_id,
            "createdByName": member.get("name", "成员"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_CAMP_TRIAL_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["camp_trial_ground"] = trial
        detail = f"{trial['createdByName']} 开启了{trial['label']}：{trial['summary']} 需要 {TRIBE_CAMP_TRIAL_TARGET} 名成员报名，至少 {TRIBE_CAMP_TRIAL_MIN_PARTICIPANTS} 名可收束。"
        self._add_tribe_history(tribe, "ritual", "营地试炼开启", detail, player_id, {"kind": "camp_trial_start", "trial": trial})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def join_camp_trial(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        trial = self._active_camp_trial(tribe)
        if not trial:
            await self._send_tribe_error(player_id, "当前没有正在进行的营地试炼")
            return
        if player_id in (trial.get("participantIds", []) or []):
            await self._send_tribe_error(player_id, "你已经报名过这次营地试炼")
            return

        member = tribe.get("members", {}).get(player_id, {})
        player = self.players.get(player_id, {}) if hasattr(self, "players") else {}
        participant = {
            "playerId": player_id,
            "name": member.get("name", player.get("name", "成员")),
            "joinedAt": datetime.now().isoformat()
        }
        trial.setdefault("participantIds", []).append(player_id)
        trial.setdefault("participants", []).append(participant)
        progress = len(trial.get("participants", []) or [])
        detail = f"{participant['name']} 报名参加{trial.get('label', '营地试炼')}，进度 {progress}/{trial.get('target', TRIBE_CAMP_TRIAL_TARGET)}。"
        self._add_tribe_history(tribe, "ritual", "营地试炼报名", detail, player_id, {"kind": "camp_trial_join", "trialId": trial.get("id"), "participant": participant})
        if progress >= int(trial.get("target", TRIBE_CAMP_TRIAL_TARGET) or TRIBE_CAMP_TRIAL_TARGET):
            await self.complete_camp_trial(player_id, auto=True)
            return
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_camp_trial(self, player_id: str, auto: bool = False):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        trial = self._active_camp_trial(tribe)
        if not trial:
            await self._send_tribe_error(player_id, "当前没有可以收束的营地试炼")
            return
        if not auto and player_id != trial.get("createdBy") and not self._member_can_manage_camp_trial(tribe, player_id):
            await self._send_tribe_error(player_id, "只有开启者、首领或长老可以收束营地试炼")
            return
        participants = list(trial.get("participants", []) or [])
        if len(participants) < TRIBE_CAMP_TRIAL_MIN_PARTICIPANTS:
            await self._send_tribe_error(player_id, f"至少需要 {TRIBE_CAMP_TRIAL_MIN_PARTICIPANTS} 名成员报名")
            return
        option = TRIBE_CAMP_TRIAL_OPTIONS.get(trial.get("trialKey"), {})
        reward_parts = self._apply_trial_ground_reward(tribe, option.get("reward", {}))
        relieved = self._apply_trial_pressure_relief(tribe, int(option.get("pressureRelief", 0) or 0))
        if relieved:
            reward_parts.append(f"战争压力-{relieved}")

        now = datetime.now()
        trial["status"] = "completed"
        trial["completedAt"] = now.isoformat()
        trial["completedBy"] = player_id
        trial["rewardParts"] = reward_parts
        names = "、".join(item.get("name", "成员") for item in participants)
        record = {
            "id": f"camp_trial_record_{tribe_id}_{int(now.timestamp() * 1000)}",
            "trialId": trial.get("id"),
            "trialKey": trial.get("trialKey"),
            "label": trial.get("label", "营地试炼"),
            "summary": trial.get("summary", ""),
            "participants": participants,
            "participantNames": names,
            "rewardParts": reward_parts,
            "completedAt": trial["completedAt"]
        }
        tribe.setdefault("camp_trial_records", []).append(record)
        tribe["camp_trial_records"] = tribe["camp_trial_records"][-TRIBE_CAMP_TRIAL_RECORD_LIMIT:]
        detail = f"{names} 完成了{record['label']}，这次优秀试炼被写入部落历史。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "ritual", "营地试炼完成", detail, player_id, {"kind": "camp_trial_complete", "record": record})
        await self._publish_world_rumor(
            "ritual",
            "营地试炼",
            f"{tribe.get('name', '某个部落')} 完成了{record['label']}，{names}的表现被记进营地故事。",
            {"tribeId": tribe_id, "trialId": trial.get("id"), "trialKey": trial.get("trialKey")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
