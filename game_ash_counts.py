from datetime import datetime

from game_config import *


class GameAshCountMixin:
    def _ash_count_expired(self, item: dict) -> bool:
        try:
            return datetime.fromisoformat(item.get("activeUntil", "")) <= datetime.now()
        except (TypeError, ValueError):
            return False

    def _ash_count_source_seen(self, tribe: dict, source_id: str) -> bool:
        if not source_id:
            return True
        for item in tribe.get("ash_counts", []) or []:
            if isinstance(item, dict) and item.get("sourceId") == source_id:
                return True
        for item in tribe.get("ash_count_records", []) or []:
            if isinstance(item, dict) and item.get("sourceId") == source_id:
                return True
        return False

    def _ash_count_candidates(self, tribe: dict) -> list:
        candidates = []
        for task in (tribe.get("war_aftermath_tasks", []) or [])[-TRIBE_ASH_COUNT_SOURCE_SCAN_LIMIT:]:
            if not isinstance(task, dict) or task.get("status") != "completed":
                continue
            candidates.append({
                "sourceId": f"war:{task.get('id')}",
                "sourceKind": "war_aftermath",
                "title": "战后灰烬清点",
                "summary": f"{task.get('title', '战后余波')}已经处理完，族人可以清点损耗、找回余材或公开分配。",
                "sourceLabel": task.get("title", "战后余波"),
                "otherTribeId": task.get("otherTribeId", ""),
                "otherTribeName": task.get("otherTribeName", "")
            })
        for record in (tribe.get("disaster_coop_records", []) or [])[-TRIBE_ASH_COUNT_SOURCE_SCAN_LIMIT:]:
            if not isinstance(record, dict):
                continue
            candidates.append({
                "sourceId": f"disaster:{record.get('id')}",
                "sourceKind": "disaster_coop",
                "title": "灾后灰烬清点",
                "summary": f"{record.get('label', '大灾协作')}之后还留着灰痕和散落补给，需要公开清点。",
                "sourceLabel": record.get("label", "大灾协作"),
                "otherTribeId": "",
                "otherTribeName": ""
            })
        for record in (tribe.get("old_camp_records", []) or [])[-TRIBE_ASH_COUNT_SOURCE_SCAN_LIMIT:]:
            if not isinstance(record, dict):
                continue
            candidates.append({
                "sourceId": f"old_camp:{record.get('id')}",
                "sourceKind": "old_camp",
                "title": "旧营灰烬清点",
                "summary": f"{record.get('label', '回归旧营')}被重新整理后，灰烬里还能清点旧物和余材。",
                "sourceLabel": record.get("sourceLabel", record.get("label", "旧营旧场")),
                "otherTribeId": "",
                "otherTribeName": ""
            })
        return candidates

    def _ensure_ash_counts(self, tribe: dict):
        if not tribe:
            return
        now = datetime.now()
        kept = []
        for item in tribe.get("ash_counts", []) or []:
            if not isinstance(item, dict):
                continue
            if item.get("status") == "pending" and self._ash_count_expired(item):
                item["status"] = "stale"
                item["staleAt"] = now.isoformat()
            kept.append(item)
        tribe["ash_counts"] = kept[-TRIBE_ASH_COUNT_LIMIT:]
        pending = [
            item for item in tribe.get("ash_counts", []) or []
            if isinstance(item, dict) and item.get("status") == "pending"
        ]
        if len(pending) >= TRIBE_ASH_COUNT_PENDING_LIMIT:
            return
        for candidate in self._ash_count_candidates(tribe):
            source_id = candidate.get("sourceId", "")
            if self._ash_count_source_seen(tribe, source_id):
                continue
            task = {
                "id": f"ash_count_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{len(tribe.get('ash_counts', []) or [])}",
                "status": "pending",
                "title": candidate.get("title", "灰烬清点"),
                "summary": candidate.get("summary", ""),
                "sourceId": source_id,
                "sourceKind": candidate.get("sourceKind", "ash"),
                "sourceLabel": candidate.get("sourceLabel", "灰烬旧痕"),
                "otherTribeId": candidate.get("otherTribeId", ""),
                "otherTribeName": candidate.get("otherTribeName", ""),
                "createdAt": now.isoformat(),
                "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_ASH_COUNT_ACTIVE_MINUTES * 60).isoformat()
            }
            tribe.setdefault("ash_counts", []).append(task)
            pending.append(task)
            if len(pending) >= TRIBE_ASH_COUNT_PENDING_LIMIT:
                break
        tribe["ash_counts"] = tribe.get("ash_counts", [])[-TRIBE_ASH_COUNT_LIMIT:]

    def _public_ash_counts(self, tribe: dict) -> list:
        self._ensure_ash_counts(tribe)
        return [
            item for item in (tribe.get("ash_counts", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-TRIBE_ASH_COUNT_PENDING_LIMIT:]

    def _public_ash_count_records(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("ash_count_records", []) or [])
            if isinstance(item, dict)
        ][-TRIBE_ASH_COUNT_RECORD_LIMIT:]

    def _ash_count_by_id(self, tribe: dict, ash_id: str) -> dict | None:
        return next((
            item for item in (tribe.get("ash_counts", []) or [])
            if isinstance(item, dict) and item.get("id") == ash_id
        ), None)

    def _apply_ash_count_relation(self, tribe: dict, task: dict, action: dict, now_text: str) -> list:
        other_id = task.get("otherTribeId")
        other = self.tribes.get(other_id) if other_id and hasattr(self, "tribes") else None
        if not other:
            return []
        parts = []
        relation_delta = int(action.get("relationDelta", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        relief = int(action.get("pressureRelief", 0) or 0)
        for source, target in ((tribe, other), (other, tribe)):
            relation = source.setdefault("boundary_relations", {}).setdefault(target.get("id"), {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            if relief:
                relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relation["lastAction"] = "ash_count"
            relation["lastActionAt"] = now_text
        if relation_delta:
            parts.append(f"关系{relation_delta:+d}")
        if trust_delta:
            parts.append(f"信任+{trust_delta}")
        if relief:
            parts.append(f"战争压力-{relief}")
        return parts

    async def resolve_ash_count(self, player_id: str, ash_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = self._ash_count_by_id(tribe, ash_id)
        action = TRIBE_ASH_COUNT_ACTIONS.get(action_key)
        if not task or task.get("status") != "pending":
            await self._send_tribe_error(player_id, "这条灰烬清点已经结束")
            return
        if not action:
            await self._send_tribe_error(player_id, "未知灰烬清点方式")
            return
        if self._ash_count_expired(task):
            task["status"] = "stale"
            await self._send_tribe_error(player_id, "这条灰烬清点已经散去")
            await self.broadcast_tribe_state(tribe_id)
            return
        now_text = datetime.now().isoformat()
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(action.get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        for key, label, field in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("tradeReputation", "贸易信誉", "trade_reputation")
        ):
            amount = int(action.get(key, 0) or 0)
            if amount:
                tribe[field] = int(tribe.get(field, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        reward_parts.extend(self._apply_ash_count_relation(tribe, task, action, now_text))
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", self.players.get(player_id, {}).get("name", "成员"))
        task["status"] = action.get("status", action_key)
        task["actionKey"] = action_key
        task["actionLabel"] = action.get("label", "清点")
        task["resolvedBy"] = player_id
        task["resolvedByName"] = member_name
        task["resolvedAt"] = now_text
        task["rewardParts"] = reward_parts
        record = {**task, "id": f"ash_record_{ash_id}_{int(datetime.now().timestamp())}"}
        tribe.setdefault("ash_count_records", []).append(record)
        tribe["ash_count_records"] = tribe["ash_count_records"][-TRIBE_ASH_COUNT_RECORD_LIMIT:]
        detail = f"{member_name}对“{task.get('title', '灰烬清点')}”选择{action.get('label', '清点')}：{'、'.join(reward_parts) or '灰烬被公开记下'}。"
        self._add_tribe_history(tribe, "world_event", "灰烬清点", detail, player_id, {"kind": "ash_count", "record": record})
        await self._publish_world_rumor(
            "world_event",
            "灰烬清点",
            f"{tribe.get('name', '部落')}把{task.get('sourceLabel', '灰烬旧痕')}清点成公开明账。",
            {"tribeId": tribe_id, "ashId": ash_id, "actionKey": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
