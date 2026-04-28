import random
from datetime import datetime

from game_config import *


class GameNewcomerFateMixin:
    def _newcomer_fate_active_until(self, now: datetime, minutes: int = 0) -> str:
        duration = minutes or TRIBE_NEWCOMER_FATE_ACTIVE_MINUTES
        return datetime.fromtimestamp(now.timestamp() + duration * 60).isoformat()

    def _active_newcomer_fate_moments(self, tribe: dict) -> list:
        return self._active_tribe_items(
            tribe,
            "newcomer_fate_moments",
            TRIBE_NEWCOMER_FATE_LIMIT,
            inactive_statuses={"resolved", "expired"}
        )

    def _active_newcomer_fate_influences(self, tribe: dict) -> list:
        return self._active_tribe_items(
            tribe,
            "newcomer_fate_influences",
            TRIBE_NEWCOMER_FATE_INFLUENCE_LIMIT,
            inactive_statuses={"consumed", "expired"}
        )

    def _public_newcomer_fate_moments(self, tribe: dict) -> list:
        hint = self._festival_tradition_newcomer_hint(tribe) if hasattr(self, "_festival_tradition_newcomer_hint") else ""
        return [{**dict(item), "festivalTraditionHint": hint} for item in self._active_newcomer_fate_moments(tribe)]

    def _public_newcomer_fate_records(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("newcomer_fate_records", []) or [])
            if isinstance(item, dict)
        ][-TRIBE_NEWCOMER_FATE_RECORD_LIMIT:]

    def _public_newcomer_fate_influences(self, tribe: dict) -> list:
        return [dict(item) for item in self._active_newcomer_fate_influences(tribe)]

    def _newcomer_fate_context_support(self, tribe: dict, context: str) -> tuple[int, list]:
        bonus = 0
        labels = []
        for influence in self._active_newcomer_fate_influences(tribe):
            if influence.get("context") != context:
                continue
            bonus += int(influence.get("bonus", 1) or 1)
            labels.append(influence.get("label", "新人关键"))
        if hasattr(self, "_festival_tradition_context_support"):
            extra_bonus, extra_labels = self._festival_tradition_context_support(tribe, context)
            bonus += extra_bonus
            labels.extend(extra_labels)
        return min(2, bonus), labels[-3:]

    def _consume_newcomer_fate_influence(self, tribe: dict, context: str) -> dict | None:
        now = datetime.now()
        for influence in self._active_newcomer_fate_influences(tribe):
            if influence.get("context") != context:
                continue
            influence["status"] = "consumed"
            influence["consumedAt"] = now.isoformat()
            return influence
        return None

    def _apply_newcomer_fate_reward(self, tribe: dict, reward: dict) -> list:
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
            ("discoveryProgress", "发现", "discovery_progress"),
            ("tradeReputation", "贸易信誉", "trade_reputation")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        return parts

    def _newcomer_fate_context(self, moment: dict) -> dict:
        key = moment.get("fateContext") or moment.get("key") or "first_find"
        return dict(TRIBE_NEWCOMER_FATE_CONTEXTS.get(key) or TRIBE_NEWCOMER_FATE_CONTEXTS["first_find"])

    def _create_newcomer_fate_moment(self, tribe: dict, player_id: str, member: dict, moment: dict, record: dict) -> dict | None:
        if not tribe or not member:
            return None
        active = self._active_newcomer_fate_moments(tribe)
        if len(active) >= TRIBE_NEWCOMER_FATE_LIMIT:
            return None
        now = datetime.now()
        context = self._newcomer_fate_context(moment)
        fate = {
            "id": f"newcomer_fate_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "momentKey": moment.get("key", "first_find"),
            "title": context.get("title", moment.get("label", "新人关键命运")),
            "label": moment.get("label", "新人关键时刻"),
            "summary": context.get("summary", moment.get("summary", "")),
            "stakes": context.get("stakes", "会改变下一次探索、禁地或外交事件。"),
            "newcomerId": player_id,
            "newcomerName": member.get("name", "新人"),
            "sourceRecord": record,
            "createdAt": now.isoformat(),
            "activeUntil": self._newcomer_fate_active_until(now)
        }
        tribe.setdefault("newcomer_fate_moments", []).append(fate)
        tribe["newcomer_fate_moments"] = tribe["newcomer_fate_moments"][-TRIBE_NEWCOMER_FATE_LIMIT:]
        return fate

    def _can_resolve_newcomer_fate(self, actor_id: str, actor: dict, fate: dict) -> bool:
        if not actor or actor_id == fate.get("newcomerId"):
            return False
        if actor.get("role") in ("leader", "elder"):
            return True
        return int(actor.get("contribution", 0) or 0) > TRIBE_NEWCOMER_KEY_CONTRIBUTION_MAX

    def _maybe_create_newcomer_key_moment(self, player_id: str, tribe: dict, member: dict, previous_contribution: int, donated_points: int):
        player = self.players.get(player_id, {})
        if not tribe or not member or donated_points < TRIBE_NEWCOMER_KEY_MIN_DONATION:
            return None
        if previous_contribution > TRIBE_NEWCOMER_KEY_CONTRIBUTION_MAX:
            return None
        if int(player.get("personal_renown", 0) or 0) > PLAYER_NEWCOMER_KEY_RENOWN_MAX:
            return None
        if player.get("newcomer_key_used") or member.get("newcomer_key_used"):
            return None
        moment = dict(random.choice(TRIBE_NEWCOMER_KEY_MOMENTS))
        reward_parts = self._apply_newcomer_fate_reward(tribe, moment)
        player["personal_renown"] = int(player.get("personal_renown", 0) or 0) + TRIBE_NEWCOMER_KEY_RENOWN
        player["newcomer_key_used"] = True
        member["newcomer_key_used"] = True
        record = {
            "key": moment.get("key"),
            "label": moment.get("label", "新人关键时刻"),
            "summary": moment.get("summary", ""),
            "personalRenown": TRIBE_NEWCOMER_KEY_RENOWN,
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        fate = self._create_newcomer_fate_moment(tribe, player_id, member, moment, record)
        if fate:
            record["fateId"] = fate.get("id")
            record["fateTitle"] = fate.get("title")
        member.setdefault("newcomer_moments", []).append(record)
        member["newcomer_moments"] = member["newcomer_moments"][-3:]
        return record

    async def resolve_newcomer_fate(self, player_id: str, moment_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_NEWCOMER_FATE_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知新人命运选择")
            return
        fate = next((item for item in self._active_newcomer_fate_moments(tribe) if item.get("id") == moment_id), None)
        if not fate:
            await self._send_tribe_error(player_id, "这段新人关键命运已经散去")
            return
        member = (tribe.get("members", {}) or {}).get(player_id, {}) or {}
        if not self._can_resolve_newcomer_fate(player_id, member, fate):
            await self._send_tribe_error(player_id, "需要由老成员、长老或首领处理新人命运")
            return

        now = datetime.now()
        actor_name = member.get("name", self.players.get(player_id, {}).get("name", "成员"))
        reward_parts = self._apply_newcomer_fate_reward(tribe, action.get("reward", {}))
        influence = None
        influence_context = action.get("influenceContext")
        if influence_context:
            influence = {
                "id": f"newcomer_fate_influence_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
                "status": "active",
                "context": influence_context,
                "label": action.get("supportLabel", action.get("label", "新人关键")),
                "summary": action.get("influenceSummary", action.get("summary", "")),
                "bonus": int(action.get("supportBonus", 1) or 1),
                "momentId": fate.get("id"),
                "momentTitle": fate.get("title"),
                "newcomerName": fate.get("newcomerName", "新人"),
                "actionKey": action_key,
                "actionLabel": action.get("label", "处理"),
                "createdByName": actor_name,
                "createdAt": now.isoformat(),
                "activeUntil": self._newcomer_fate_active_until(now, TRIBE_NEWCOMER_FATE_INFLUENCE_MINUTES)
            }
            tribe.setdefault("newcomer_fate_influences", []).append(influence)
            tribe["newcomer_fate_influences"] = tribe["newcomer_fate_influences"][-TRIBE_NEWCOMER_FATE_INFLUENCE_LIMIT:]

        fate["status"] = "resolved"
        fate["resolvedAt"] = now.isoformat()
        fate["resolvedBy"] = player_id
        fate["resolvedByName"] = actor_name
        fate["actionKey"] = action_key
        fate["actionLabel"] = action.get("label", "处理")
        record = {
            "id": f"newcomer_fate_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "momentId": fate.get("id"),
            "title": fate.get("title", "新人关键命运"),
            "newcomerName": fate.get("newcomerName", "新人"),
            "memberId": player_id,
            "memberName": actor_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "处理"),
            "summary": action.get("summary", ""),
            "influence": influence,
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        tribe.setdefault("newcomer_fate_records", []).append(record)
        tribe["newcomer_fate_records"] = tribe["newcomer_fate_records"][-TRIBE_NEWCOMER_FATE_RECORD_LIMIT:]

        detail = f"{actor_name}对{fate.get('newcomerName', '新人')}的“{fate.get('label', '新人关键')}”选择{action.get('label', '处理')}。"
        if influence:
            detail += f" 下一次{action.get('contextLabel', '事件')}会带上“{influence.get('label', '新人关键')}”。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "governance", "新人关键命运", detail, player_id, {"kind": "newcomer_fate", "record": record})
        await self._publish_world_rumor(
            "governance",
            "新人关键命运",
            f"{tribe.get('name', '某个部落')}把{fate.get('newcomerName', '新人')}的一次小发现交给老成员判断，选择了{action.get('label', '处理')}。",
            {"tribeId": tribe_id, "momentId": fate.get("id"), "actionKey": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
