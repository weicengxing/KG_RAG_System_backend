from datetime import datetime

from game_config import *


class GameCampShiftMixin:
    def _active_camp_shift(self, tribe: dict) -> dict | None:
        shift = tribe.get("camp_shift")
        if not isinstance(shift, dict) or shift.get("status") != "active":
            return None
        try:
            if datetime.fromisoformat(shift.get("activeUntil", "")) <= datetime.now():
                shift["status"] = "expired"
                return None
        except (TypeError, ValueError):
            shift["status"] = "expired"
            return None
        return shift

    def _public_camp_shift_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("camp_shift_records", []) or [])
            if isinstance(record, dict)
        ][-TRIBE_CAMP_SHIFT_RECORD_LIMIT:]

    def _apply_camp_shift_reward(self, tribe: dict, reward: dict) -> list:
        reward_parts = self._apply_tribe_reward(tribe, reward)
        pressure_relief = int(reward.get("warPressureRelief", reward.get("pressureRelief", 0)) or 0)
        if pressure_relief:
            relieved = 0
            for relation in (tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                if before <= 0:
                    continue
                relation["warPressure"] = max(0, before - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                relieved += before - int(relation.get("warPressure", 0) or 0)
            if relieved:
                reward_parts.append(f"战争压力-{relieved}")
        return reward_parts

    async def start_camp_shift(self, player_id: str, shift_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以开启营地轮值")
            return
        option = TRIBE_CAMP_SHIFT_OPTIONS.get(shift_key)
        if not option:
            await self._send_tribe_error(player_id, "未知营地轮值")
            return
        if self._active_camp_shift(tribe):
            await self._send_tribe_error(player_id, "已经有一轮营地轮值正在进行")
            return

        now = datetime.now()
        active_until = datetime.fromtimestamp(now.timestamp() + TRIBE_CAMP_SHIFT_ACTIVE_MINUTES * 60).isoformat()
        shift = {
            "id": f"camp_shift_{shift_key}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "key": shift_key,
            "label": option.get("label", "营地轮值"),
            "summary": option.get("summary", ""),
            "target": TRIBE_CAMP_SHIFT_TARGET,
            "minParticipants": TRIBE_CAMP_SHIFT_MIN_PARTICIPANTS,
            "participants": [],
            "participantNames": [],
            "reward": option.get("reward", {}),
            "activeUntil": active_until,
            "createdAt": now.isoformat(),
            "startedBy": player_id,
            "startedByName": member.get("name", "管理者")
        }
        tribe["camp_shift"] = shift
        self._add_tribe_history(
            tribe,
            "ritual",
            "营地轮值开启",
            f"{member.get('name', '管理者')} 开启了“{shift['label']}”，成员可以报名轮值。",
            player_id,
            {"kind": "camp_shift", **shift}
        )
        await self._notify_tribe(tribe_id, f"营地轮值开启：{shift['label']}。")
        await self.broadcast_tribe_state(tribe_id)

    async def join_camp_shift(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        shift = self._active_camp_shift(tribe)
        if not shift:
            await self._send_tribe_error(player_id, "当前没有进行中的营地轮值")
            return
        if player_id in set(shift.get("participants", []) or []):
            await self._send_tribe_error(player_id, "你已经报名了这轮营地轮值")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", self._get_player_name(player_id))
        shift.setdefault("participants", []).append(player_id)
        shift.setdefault("participantNames", []).append(member_name)
        member["contribution"] = int(member.get("contribution", 0) or 0) + TRIBE_CAMP_SHIFT_MEMBER_CONTRIBUTION

        if len(shift.get("participants", []) or []) >= int(shift.get("target", TRIBE_CAMP_SHIFT_TARGET) or TRIBE_CAMP_SHIFT_TARGET):
            await self._complete_camp_shift(tribe_id, player_id)
        else:
            await self._notify_tribe(tribe_id, f"{member_name} 已加入“{shift.get('label', '营地轮值')}”。")
            await self.broadcast_tribe_state(tribe_id)

    async def _complete_camp_shift(self, tribe_id: str, actor_id: str):
        tribe = self.tribes.get(tribe_id)
        shift = self._active_camp_shift(tribe) if tribe else None
        if not shift:
            return
        option = TRIBE_CAMP_SHIFT_OPTIONS.get(shift.get("key"), {})
        reward_parts = self._apply_camp_shift_reward(tribe, option.get("reward", {}))
        shift["status"] = "completed"
        shift["completedAt"] = datetime.now().isoformat()
        shift["rewardParts"] = reward_parts
        record = {
            **shift,
            "participantCount": len(shift.get("participants", []) or [])
        }
        tribe.setdefault("camp_shift_records", []).append(record)
        tribe["camp_shift_records"] = tribe["camp_shift_records"][-TRIBE_CAMP_SHIFT_RECORD_LIMIT:]
        tribe["camp_shift"] = None
        participant_text = "、".join(shift.get("participantNames", []) or []) or "成员"
        detail = f"{participant_text} 完成了“{shift.get('label', '营地轮值')}”：{'、'.join(reward_parts) or '营地秩序更稳'}。"
        self._add_tribe_history(tribe, "ritual", "营地轮值完成", detail, actor_id, {"kind": "camp_shift", **record})
        await self._publish_world_rumor(
            "tribe",
            "营地轮值完成",
            f"{tribe.get('name', '部落')} 完成了{shift.get('label', '营地轮值')}，营地里的名单被写到火边。",
            {"tribeId": tribe_id, "shiftKey": shift.get("key")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
