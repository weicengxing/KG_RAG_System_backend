from datetime import datetime
import random

from game_config import *


class GameNamedLandmarkMixin:
    def _named_landmark_support_target(self, tribe: dict) -> int:
        member_count = len(tribe.get("members", {}) or {})
        return min(TRIBE_NAMED_LANDMARK_SUPPORT_TARGET, max(1, member_count))

    def _named_landmark_position(self, x: float, z: float) -> tuple[float, float]:
        return (
            max(-490, min(490, float(x or 0))),
            max(-490, min(490, float(z or 0)))
        )

    def _active_named_landmarks(self, tribe: dict) -> list:
        if not tribe:
            return []
        landmarks = [
            item for item in (tribe.get("named_landmarks", []) or [])
            if isinstance(item, dict) and item.get("status", "active") == "active"
        ]
        tribe["named_landmarks"] = landmarks[-TRIBE_NAMED_LANDMARK_LIMIT:]
        return tribe["named_landmarks"]

    def _active_named_landmark_proposals(self, tribe: dict) -> list:
        if not tribe:
            return []
        proposals = [
            item for item in (tribe.get("named_landmark_proposals", []) or [])
            if isinstance(item, dict) and item.get("status", "open") == "open"
        ]
        tribe["named_landmark_proposals"] = proposals[-TRIBE_NAMED_LANDMARK_PROPOSAL_LIMIT:]
        return tribe["named_landmark_proposals"]

    def _named_landmark_source_available(self, tribe: dict, source_key: str) -> bool:
        history = " ".join(
            f"{item.get('type', '')} {item.get('title', '')} {item.get('detail', '')}"
            for item in (tribe.get("history", []) or [])[-40:]
            if isinstance(item, dict)
        )
        if source_key == "first_scout":
            return bool(
                int(tribe.get("discovery_progress", 0) or 0) > 0
                or tribe.get("discoveries")
                or tribe.get("map_memories")
                or tribe.get("scouted_resource_sites")
                or "洞" in history
                or "侦察" in history
                or "探索" in history
            )
        if source_key == "rescue":
            return bool(
                tribe.get("emergency_followup_tasks")
                or tribe.get("mutual_aid_alert_records")
                or "救" in history
                or "补救" in history
                or "互助" in history
            )
        if source_key == "war":
            has_pressure = any(
                int(relation.get("warPressure", 0) or 0) > 0
                for relation in (tribe.get("boundary_relations", {}) or {}).values()
                if isinstance(relation, dict)
            )
            return bool(
                has_pressure
                or tribe.get("war_records")
                or tribe.get("boundary_outcomes")
                or tribe.get("small_conflicts")
                or "战争" in history
                or "冲突" in history
                or "停战" in history
            )
        if source_key == "ritual":
            return bool(
                tribe.get("celebration_echo_records")
                or tribe.get("communal_cook_records")
                or tribe.get("drum_rhythm_records")
                or tribe.get("group_emote_records")
                or "仪式" in history
                or "庆功" in history
                or "烹饪" in history
                or "鼓点" in history
            )
        return False

    def _public_named_landmark_options(self, tribe: dict) -> dict:
        options = {}
        for key, config in TRIBE_NAMED_LANDMARK_SOURCES.items():
            options[key] = {
                **config,
                "available": self._named_landmark_source_available(tribe, key),
                "rewardLabel": self._reward_summary_text(config.get("reward", {})) if hasattr(self, "_reward_summary_text") else ""
            }
        return options

    def _public_named_landmarks(self, tribe: dict) -> list:
        return [
            {
                "id": item.get("id"),
                "label": item.get("label", "有名之地"),
                "name": item.get("name", "未名地"),
                "sourceKey": item.get("sourceKey"),
                "sourceLabel": item.get("sourceLabel", "部落命名"),
                "summary": item.get("summary", ""),
                "x": item.get("x", 0),
                "z": item.get("z", 0),
                "namedByName": item.get("namedByName", "成员"),
                "supportCount": len(item.get("supporters", []) or []),
                "rewardParts": item.get("rewardParts", []),
                "createdAt": item.get("createdAt")
            }
            for item in self._active_named_landmarks(tribe)
        ]

    def _public_named_landmark_proposals(self, tribe: dict) -> list:
        target = self._named_landmark_support_target(tribe)
        return [
            {
                "id": item.get("id"),
                "name": item.get("name", "未名地"),
                "sourceKey": item.get("sourceKey"),
                "sourceLabel": item.get("sourceLabel", "部落命名"),
                "summary": item.get("summary", ""),
                "x": item.get("x", 0),
                "z": item.get("z", 0),
                "proposedByName": item.get("proposedByName", "成员"),
                "supportCount": len(item.get("supporters", []) or []),
                "supportTarget": target,
                "supporterNames": [support.get("memberName", "成员") for support in (item.get("supporters", []) or [])],
                "createdAt": item.get("createdAt")
            }
            for item in self._active_named_landmark_proposals(tribe)
        ]

    def _apply_named_landmark_reward(self, tribe: dict, reward: dict) -> list:
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
        return parts

    def _clean_named_landmark_name(self, name: str) -> str:
        cleaned = " ".join(str(name or "").strip().split())
        cleaned = cleaned.replace("<", "").replace(">", "").replace("{", "").replace("}", "")
        return cleaned[:TRIBE_NAMED_LANDMARK_NAME_MAX]

    async def propose_named_landmark(self, player_id: str, source_key: str, name: str, x: float, z: float):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        config = TRIBE_NAMED_LANDMARK_SOURCES.get(source_key)
        if not config:
            await self._send_tribe_error(player_id, "未知命名来源")
            return
        if not self._named_landmark_source_available(tribe, source_key):
            await self._send_tribe_error(player_id, "部落还没有这类可命名的故事来源")
            return
        clean_name = self._clean_named_landmark_name(name)
        if len(clean_name) < TRIBE_NAMED_LANDMARK_NAME_MIN:
            await self._send_tribe_error(player_id, f"地名至少需要 {TRIBE_NAMED_LANDMARK_NAME_MIN} 个字")
            return
        if any(item.get("name") == clean_name for item in self._active_named_landmarks(tribe)):
            await self._send_tribe_error(player_id, "这个地名已经写进地图")
            return

        marker_x, marker_z = self._named_landmark_position(x, z)
        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        proposal = {
            "id": f"named_landmark_proposal_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "open",
            "name": clean_name,
            "sourceKey": source_key,
            "sourceLabel": config.get("label", "部落命名"),
            "summary": config.get("summary", ""),
            "x": marker_x,
            "z": marker_z,
            "proposedBy": player_id,
            "proposedByName": member_name,
            "supporters": [{
                "playerId": player_id,
                "memberName": member_name,
                "supportedAt": now.isoformat()
            }],
            "createdAt": now.isoformat()
        }
        proposals = self._active_named_landmark_proposals(tribe)
        proposals.append(proposal)
        tribe["named_landmark_proposals"] = proposals[-TRIBE_NAMED_LANDMARK_PROPOSAL_LIMIT:]

        detail = f"{member_name} 提议把当前位置命名为“{clean_name}”，来源是{config.get('label', '部落故事')}。"
        self._add_tribe_history(tribe, "world_event", "提名地标命名", detail, player_id, {"kind": "named_landmark_proposal", "proposal": proposal})
        await self._notify_tribe(tribe_id, detail)
        if len(proposal["supporters"]) >= self._named_landmark_support_target(tribe):
            await self._finalize_named_landmark(tribe_id, tribe, proposal, player_id)
            return
        await self.broadcast_tribe_state(tribe_id)

    async def support_named_landmark(self, player_id: str, proposal_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        proposal = next((item for item in self._active_named_landmark_proposals(tribe) if item.get("id") == proposal_id), None)
        if not proposal:
            await self._send_tribe_error(player_id, "这条命名提案已经结束")
            return
        supporters = proposal.setdefault("supporters", [])
        if any(item.get("playerId") == player_id for item in supporters):
            await self._send_tribe_error(player_id, "你已经支持过这个地名")
            return
        member = tribe.get("members", {}).get(player_id, {})
        supporters.append({
            "playerId": player_id,
            "memberName": member.get("name", "成员"),
            "supportedAt": datetime.now().isoformat()
        })
        detail = f"{member.get('name', '成员')} 支持把这里叫作“{proposal.get('name', '未名地')}”。"
        self._add_tribe_history(tribe, "world_event", "支持地标命名", detail, player_id, {"kind": "named_landmark_support", "proposalId": proposal_id})
        await self._notify_tribe(tribe_id, detail)
        if len(supporters) >= self._named_landmark_support_target(tribe):
            await self._finalize_named_landmark(tribe_id, tribe, proposal, player_id)
            return
        await self.broadcast_tribe_state(tribe_id)

    async def _finalize_named_landmark(self, tribe_id: str, tribe: dict, proposal: dict, actor_id: str):
        config = TRIBE_NAMED_LANDMARK_SOURCES.get(proposal.get("sourceKey"), {})
        reward_parts = self._apply_named_landmark_reward(tribe, config.get("reward", {}))
        now = datetime.now()
        landmark = {
            "id": f"named_landmark_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "type": "named_landmark",
            "status": "active",
            "label": proposal.get("name", "有名之地"),
            "name": proposal.get("name", "有名之地"),
            "sourceKey": proposal.get("sourceKey"),
            "sourceLabel": proposal.get("sourceLabel", "部落命名"),
            "summary": proposal.get("summary", ""),
            "x": proposal.get("x", 0),
            "z": proposal.get("z", 0),
            "y": 0,
            "size": 0.85,
            "namedBy": actor_id,
            "namedByName": proposal.get("proposedByName", "成员"),
            "supporters": list(proposal.get("supporters", []) or []),
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        proposal["status"] = "finalized"
        proposal["finalizedAt"] = now.isoformat()
        tribe["named_landmark_proposals"] = [
            item for item in (tribe.get("named_landmark_proposals", []) or [])
            if item.get("id") != proposal.get("id")
        ]
        landmarks = self._active_named_landmarks(tribe)
        landmarks.append(landmark)
        tribe["named_landmarks"] = landmarks[-TRIBE_NAMED_LANDMARK_LIMIT:]
        tribe.setdefault("named_landmark_records", []).append(landmark)
        tribe["named_landmark_records"] = tribe["named_landmark_records"][-TRIBE_NAMED_LANDMARK_RECORD_LIMIT:]
        detail = f"“{landmark['name']}”成为{tribe.get('name', '部落')}的新地名。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "world_event", "地标命名定稿", detail, actor_id, {"kind": "named_landmark", "landmark": landmark})
        await self._publish_world_rumor(
            "world_event",
            "新地名写入地图",
            f"{tribe.get('name', '部落')} 把一处地方称作“{landmark['name']}”，以后传闻会用这个名字回望那里。",
            {"tribeId": tribe_id, "landmarkId": landmark.get("id")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
