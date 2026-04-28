import math
import random
from datetime import datetime

from game_config import *


class GameMaskPerformanceMixin:
    def _active_mask_performances(self, tribe: dict) -> list:
        return self._active_tribe_items(
            tribe,
            "mask_performances",
            TRIBE_MASK_PERFORMANCE_LIMIT,
            inactive_statuses={"completed", "expired"}
        )

    def _public_mask_performances(self, tribe: dict) -> list:
        return [dict(item) for item in self._active_mask_performances(tribe)]

    def _public_mask_performance_records(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("mask_performance_records", []) or [])
            if isinstance(item, dict)
        ][-TRIBE_MASK_PERFORMANCE_RECORD_LIMIT:]

    def _active_mask_identity_titles(self, tribe: dict) -> list:
        return self._active_tribe_items(
            tribe,
            "mask_identity_titles",
            TRIBE_MASK_IDENTITY_TITLE_LIMIT,
            inactive_statuses={"expired"}
        )

    def _public_mask_identity_titles(self, tribe: dict) -> list:
        return [dict(item) for item in self._active_mask_identity_titles(tribe)]

    def _public_mask_identity_title_records(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("mask_identity_title_records", []) or [])
            if isinstance(item, dict)
        ][-TRIBE_MASK_IDENTITY_TITLE_RECORD_LIMIT:]

    def _public_mask_performance_types(self) -> dict:
        options = {}
        for key, profile in TRIBE_MASK_PERFORMANCE_TYPES.items():
            identity = PLAYER_IDENTITY_OPTIONS.get(key, {})
            options[key] = {
                "key": key,
                "label": profile.get("label") or identity.get("label", key),
                "summary": profile.get("summary", identity.get("summary", "")),
                "identityLabel": identity.get("label", key),
                "animation": profile.get("animation", "ritual")
            }
        return options

    def _near_mask_performance(self, player_id: str, performance: dict) -> bool:
        player = self.players.get(player_id, {}) if hasattr(self, "players") else {}
        dx = float(player.get("x", 0) or 0) - float(performance.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(performance.get("z", 0) or 0)
        return math.sqrt(dx * dx + dz * dz) <= float(performance.get("radius", TRIBE_MASK_PERFORMANCE_RADIUS) or TRIBE_MASK_PERFORMANCE_RADIUS)

    def _apply_mask_performance_reward(self, tribe: dict, reward: dict) -> list:
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

    def _grant_mask_performance_personal_renown(self, performance: dict) -> list:
        parts = []
        seen = set()
        for participant in performance.get("participants", []) or []:
            member_id = participant.get("memberId")
            if not member_id or member_id in seen:
                continue
            seen.add(member_id)
            player = self.players.setdefault(member_id, {})
            player["personal_renown"] = int(player.get("personal_renown", 0) or 0) + TRIBE_MASK_PERFORMANCE_RESPONSE_RENOWN
            parts.append(f"{participant.get('memberName', '成员')}个人声望+{TRIBE_MASK_PERFORMANCE_RESPONSE_RENOWN}")
        return parts

    def _mask_performance_action_records(self, performance: dict, closer_id: str) -> list:
        actions = []
        participants = performance.get("participants", []) or []
        for index, participant in enumerate(participants):
            member_id = participant.get("memberId")
            if member_id == performance.get("initiatorId"):
                action_label = "起势"
            elif member_id == closer_id:
                action_label = "收束"
            else:
                action_label = "接拍"
            actions.append({
                "memberId": member_id,
                "memberName": participant.get("memberName", "成员"),
                "actionLabel": action_label,
                "step": index + 1,
                "createdAt": participant.get("createdAt")
            })
        return actions

    def _create_mask_title_newcomer_influence(self, tribe_id: str, tribe: dict, title: dict, profile: dict, now: datetime) -> dict | None:
        context = profile.get("newcomerContext")
        if not context:
            return None
        influence = {
            "id": f"mask_title_influence_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "context": context,
            "label": profile.get("newcomerLabel", title.get("title", "面具称号")),
            "summary": f"{title.get('title', '面具称号')}会被下一次相关事件引用：{profile.get('summary', '')}",
            "bonus": 1,
            "sourceKind": "mask_identity_title",
            "titleId": title.get("id"),
            "identityKey": title.get("identityKey"),
            "identityLabel": title.get("identityLabel"),
            "createdByName": title.get("participantsText", "成员"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_NEWCOMER_FATE_INFLUENCE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("newcomer_fate_influences", []).append(influence)
        tribe["newcomer_fate_influences"] = tribe["newcomer_fate_influences"][-TRIBE_NEWCOMER_FATE_INFLUENCE_LIMIT:]
        return influence

    def _maybe_unlock_mask_identity_title(self, tribe_id: str, tribe: dict, performance: dict, record: dict, now: datetime) -> dict | None:
        identity_key = performance.get("identityKey")
        profile = TRIBE_MASK_IDENTITY_TITLE_PROFILES.get(identity_key)
        if not profile:
            return None
        identity_records = [
            item for item in (tribe.get("mask_performance_records", []) or [])
            if isinstance(item, dict) and item.get("identityKey") == identity_key and item.get("status") == "completed"
        ]
        if len(identity_records) < TRIBE_MASK_IDENTITY_TITLE_UNLOCK_COUNT:
            return None

        active_titles = self._active_mask_identity_titles(tribe)
        existing = next((item for item in active_titles if item.get("identityKey") == identity_key), None)
        participant_names = [
            item.get("memberName", "成员")
            for item in (performance.get("participants", []) or [])
            if isinstance(item, dict)
        ]
        base_title = {
            "status": "active",
            "identityKey": identity_key,
            "identityLabel": performance.get("identityLabel", "身份"),
            "title": profile.get("title", performance.get("identityLabel", "面具称号")),
            "summary": profile.get("summary", ""),
            "participants": list(performance.get("participants", []) or []),
            "participantsText": "、".join(participant_names[-4:]) or "成员",
            "performanceCount": len(identity_records),
            "lastPerformanceId": record.get("id"),
            "lastPerformanceLabel": performance.get("label", "面具身份表演"),
            "recordIds": [item.get("id") for item in identity_records[-3:] if item.get("id")],
            "createdAt": existing.get("createdAt") if existing else now.isoformat(),
            "refreshedAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_MASK_IDENTITY_TITLE_ACTIVE_MINUTES * 60).isoformat()
        }
        if existing:
            existing.update(base_title)
            title = existing
        else:
            title = {
                **base_title,
                "id": f"mask_identity_title_{tribe_id}_{identity_key}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}"
            }
            active_titles.append(title)
        tribe["mask_identity_titles"] = active_titles[-TRIBE_MASK_IDENTITY_TITLE_LIMIT:]

        title_record = {
            "id": f"mask_identity_title_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "titleId": title.get("id"),
            "title": title.get("title"),
            "summary": title.get("summary"),
            "identityKey": identity_key,
            "identityLabel": title.get("identityLabel"),
            "performanceId": record.get("id"),
            "performanceLabel": performance.get("label", "面具身份表演"),
            "participantsText": title.get("participantsText"),
            "actionRecords": record.get("actionRecords", []),
            "performanceCount": title.get("performanceCount", 0),
            "createdAt": now.isoformat()
        }
        tribe.setdefault("mask_identity_title_records", []).append(title_record)
        tribe["mask_identity_title_records"] = tribe["mask_identity_title_records"][-TRIBE_MASK_IDENTITY_TITLE_RECORD_LIMIT:]

        influence = self._create_mask_title_newcomer_influence(tribe_id, tribe, title, profile, now)
        if influence:
            title["newcomerInfluence"] = dict(influence)
            title_record["newcomerInfluence"] = dict(influence)

        if hasattr(self, "_open_myth_claim"):
            myth_claim = self._open_myth_claim(
                tribe,
                "mask_identity_title",
                title.get("title", "面具称号"),
                f"{title.get('identityLabel', '身份')}多次被公开表演接住，部落可以解释这段称号从哪里来。",
                float(performance.get("x", 0) or 0),
                float(performance.get("z", 0) or 0),
                title.get("id", ""),
                title.get("participantsText", "")
            )
            if myth_claim:
                title["mythClaimId"] = myth_claim.get("id")
                title_record["mythClaimId"] = myth_claim.get("id")
                record["mythClaimId"] = myth_claim.get("id")

        record["identityTitle"] = {
            "id": title.get("id"),
            "title": title.get("title"),
            "summary": title.get("summary"),
            "activeUntil": title.get("activeUntil"),
            "performanceCount": title.get("performanceCount", 0)
        }
        return title

    async def start_mask_identity_performance(self, player_id: str, identity_key: str = ""):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        player = self.players.get(player_id, {})
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        selected_key = identity_key or player.get("personal_identity", "")
        profile = TRIBE_MASK_PERFORMANCE_TYPES.get(selected_key)
        identity = PLAYER_IDENTITY_OPTIONS.get(selected_key)
        if not profile or not identity or player.get("personal_identity") != selected_key:
            await self._send_tribe_error(player_id, "需要先选择对应的面具身份")
            return
        if len(self._active_mask_performances(tribe)) >= TRIBE_MASK_PERFORMANCE_LIMIT:
            await self._send_tribe_error(player_id, "部落里正在表演的身份场景太多了")
            return
        now = datetime.now()
        cooldowns = tribe.setdefault("mask_performance_cooldowns", {})
        last_text = cooldowns.get(player_id)
        if last_text:
            try:
                elapsed = (now - datetime.fromisoformat(last_text)).total_seconds()
                if elapsed < TRIBE_MASK_PERFORMANCE_COOLDOWN_SECONDS:
                    await self._send_tribe_error(player_id, f"面具身份表演还需等待 {int(TRIBE_MASK_PERFORMANCE_COOLDOWN_SECONDS - elapsed)} 秒")
                    return
            except (TypeError, ValueError):
                pass
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", player.get("name", "成员"))
        performance = {
            "id": f"mask_performance_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "identityKey": selected_key,
            "identityLabel": identity.get("label", selected_key),
            "label": profile.get("label", identity.get("label", "身份表演")),
            "summary": profile.get("summary", identity.get("summary", "")),
            "initiatorId": player_id,
            "initiatorName": member_name,
            "participants": [{"memberId": player_id, "memberName": member_name, "role": "initiator", "createdAt": now.isoformat()}],
            "score": 1,
            "target": TRIBE_MASK_PERFORMANCE_TARGET,
            "radius": TRIBE_MASK_PERFORMANCE_RADIUS,
            "x": float(player.get("x", 0) or 0),
            "z": float(player.get("z", 0) or 0),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_MASK_PERFORMANCE_ACTIVE_MINUTES * 60).isoformat()
        }
        cooldowns[player_id] = now.isoformat()
        tribe.setdefault("mask_performances", []).append(performance)
        tribe["mask_performances"] = tribe["mask_performances"][-TRIBE_MASK_PERFORMANCE_LIMIT:]
        detail = f"{member_name}以{identity.get('label', '身份')}发起“{performance['label']}”，附近成员可以响应形成连携。"
        self._add_tribe_history(tribe, "culture", "面具身份表演", detail, player_id, {"kind": "mask_performance_started", "performance": performance})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def respond_mask_identity_performance(self, player_id: str, performance_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        performance = next((item for item in self._active_mask_performances(tribe) if item.get("id") == performance_id), None)
        if not performance:
            await self._send_tribe_error(player_id, "这场面具身份表演已经散去")
            return
        if any(item.get("memberId") == player_id for item in performance.get("participants", []) or []):
            await self._send_tribe_error(player_id, "你已经响应过这场表演")
            return
        if not self._near_mask_performance(player_id, performance):
            await self._send_tribe_error(player_id, f"需要靠近表演现场 {TRIBE_MASK_PERFORMANCE_RADIUS} 步内")
            return
        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", self.players.get(player_id, {}).get("name", "成员"))
        participant = {"memberId": player_id, "memberName": member_name, "role": "response", "createdAt": now.isoformat()}
        performance.setdefault("participants", []).append(participant)
        performance["score"] = len(performance.get("participants", []) or [])
        detail = f"{member_name}响应“{performance.get('label', '面具身份表演')}”，连携 {performance.get('score', 0)} / {performance.get('target', TRIBE_MASK_PERFORMANCE_TARGET)}。"
        if int(performance.get("score", 0) or 0) >= int(performance.get("target", TRIBE_MASK_PERFORMANCE_TARGET) or TRIBE_MASK_PERFORMANCE_TARGET):
            profile = TRIBE_MASK_PERFORMANCE_TYPES.get(performance.get("identityKey"), {})
            reward_parts = self._apply_mask_performance_reward(tribe, profile.get("reward", {}))
            reward_parts.extend(self._grant_mask_performance_personal_renown(performance))
            custom_record = self._record_tribe_custom_choice(tribe, profile.get("customKey", "hearth"), performance.get("label", "面具身份表演"), player_id, amount=2) if hasattr(self, "_record_tribe_custom_choice") else None
            if custom_record:
                reward_parts.append(f"{custom_record.get('label', '风俗')}倾向+2")
            performance["status"] = "completed"
            performance["completedAt"] = now.isoformat()
            performance["completedBy"] = player_id
            performance["rewardParts"] = reward_parts
            performance["actionRecords"] = self._mask_performance_action_records(performance, player_id)
            record = {**performance, "id": f"mask_performance_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}"}
            tribe.setdefault("mask_performance_records", []).append(record)
            tribe["mask_performance_records"] = tribe["mask_performance_records"][-TRIBE_MASK_PERFORMANCE_RECORD_LIMIT:]
            title = self._maybe_unlock_mask_identity_title(tribe_id, tribe, performance, record, now)
            if title:
                reward_parts.append(f"短时称号：{title.get('title', '面具称号')}")
            detail = f"“{performance.get('label', '面具身份表演')}”完成连携，{member_name}接住最后一拍。{'、'.join(reward_parts) or '表演被记入部落风俗'}。"
            await self._publish_world_rumor("culture", "面具身份表演", f"{tribe.get('name', '部落')}把{performance.get('identityLabel', '身份')}演成了公开场景，附近成员一起响应。", {"tribeId": tribe_id, "performanceId": performance.get("id")})
            if title:
                await self._publish_world_rumor(
                    "culture",
                    "面具身份称号",
                    f"{tribe.get('name', '部落')}连续接住{performance.get('identityLabel', '身份')}表演，短时称号“{title.get('title', '面具称号')}”开始流传。",
                    {"tribeId": tribe_id, "performanceId": performance.get("id"), "titleId": title.get("id"), "mythClaimId": title.get("mythClaimId")}
                )
        self._add_tribe_history(tribe, "culture", "面具身份表演", detail, player_id, {"kind": "mask_performance", "performance": performance, "participant": participant})
        await self.send_personal_conflict_status(player_id)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
