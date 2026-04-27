from datetime import datetime

from game_config import *


class GameOldGrudgeMixin:
    def _active_old_grudge_seals(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for seal in tribe.get("old_grudge_seals", []) or []:
            if not isinstance(seal, dict) or seal.get("status") not in ("active", "sealed"):
                continue
            active_until = seal.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        seal["status"] = "expired"
                        seal["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    seal["status"] = "expired"
                    seal["expiredAt"] = now.isoformat()
                    continue
            active.append(seal)
        return active

    def _old_grudge_source_parts(self, relation: dict) -> list:
        parts = []
        pressure = int(relation.get("warPressure", 0) or 0)
        score = int(relation.get("score", 0) or 0)
        last_action = str(relation.get("lastAction", ""))
        if pressure > 0:
            parts.append(f"战争压力 {pressure}")
        if score <= -4:
            parts.append(f"关系 {score}")
        if "betray" in last_action or "grievance" in last_action:
            parts.append("背刺旧账")
        elif "formal_war" in last_action:
            parts.append("战争余波")
        elif "boundary_press" in last_action or "blockade" in last_action or "drive_away" in last_action:
            parts.append("边界挑衅")
        return parts

    def _old_grudge_target_for_relation(self, tribe: dict, other_id: str, relation: dict) -> dict | None:
        other = self.tribes.get(other_id) if hasattr(self, "tribes") else None
        if not other:
            return None
        parts = self._old_grudge_source_parts(relation)
        if not parts:
            return None
        active = next((seal for seal in self._active_old_grudge_seals(tribe) if seal.get("otherTribeId") == other_id), None)
        return {
            "otherTribeId": other_id,
            "otherTribeName": other.get("name", relation.get("otherTribeName", "邻近部落")),
            "sourceLabel": "、".join(parts),
            "summary": "这条边界已经有足够旧怨，可以把它封在一个公开地标里，先让成员维护而不是继续升温。",
            "warPressure": int(relation.get("warPressure", 0) or 0),
            "score": int(relation.get("score", 0) or 0),
            "activeSealId": active.get("id") if active else "",
            "canSeal": not bool(active)
        }

    def _public_old_grudge_targets(self, tribe: dict) -> list:
        targets = []
        for other_id, relation in (tribe.get("boundary_relations", {}) or {}).items():
            if not isinstance(relation, dict):
                continue
            target = self._old_grudge_target_for_relation(tribe, other_id, relation)
            if target:
                targets.append(target)
        targets.sort(key=lambda item: (-int(item.get("warPressure", 0) or 0), int(item.get("score", 0) or 0)))
        return targets[-TRIBE_OLD_GRUDGE_RECENT_LIMIT:]

    def _public_old_grudge_seals(self, tribe: dict) -> list:
        return self._active_old_grudge_seals(tribe)[-TRIBE_OLD_GRUDGE_RECENT_LIMIT:]

    def _public_old_grudge_records(self, tribe: dict) -> list:
        return list(tribe.get("old_grudge_records", []) or [])[-TRIBE_OLD_GRUDGE_RECENT_LIMIT:]

    def _public_old_grudge_wake_tasks(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("old_grudge_wake_tasks", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-TRIBE_OLD_GRUDGE_WAKE_TASK_LIMIT:]

    def _can_manage_old_grudge(self, tribe: dict, player_id: str) -> bool:
        member = (tribe.get("members", {}) or {}).get(player_id, {})
        return member.get("role") in ("leader", "elder") or tribe.get("leader_id") == player_id

    def _apply_old_grudge_reward(self, tribe: dict, relation: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int((reward or {}).get("woodCost", 0) or 0)
        food_cost = int((reward or {}).get("foodCost", 0) or 0)
        if wood_cost:
            storage["wood"] = max(0, int(storage.get("wood", 0) or 0) - wood_cost)
            parts.append(f"木材-{wood_cost}")
        if food_cost:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) - food_cost)
            parts.append(f"食物-{food_cost}")
        renown = int((reward or {}).get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            parts.append(f"声望+{renown}")
        trade = int((reward or {}).get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            parts.append(f"贸易信誉+{trade}")
        relation_delta = int((reward or {}).get("relationDelta", 0) or 0)
        if relation_delta:
            relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            parts.append(f"关系{relation_delta:+d}")
        trust_delta = int((reward or {}).get("tradeTrustDelta", 0) or 0)
        if trust_delta:
            relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            parts.append(f"信任{trust_delta:+d}")
        relief = int((reward or {}).get("warPressureRelief", 0) or 0)
        if relief:
            before = int(relation.get("warPressure", 0) or 0)
            relation["warPressure"] = max(0, before - relief)
            relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            parts.append(f"战争压力-{before - int(relation.get('warPressure', 0) or 0) or relief}")
        return parts

    def _mirror_old_grudge_seal(self, source_id: str, patch: dict):
        if not source_id or not hasattr(self, "tribes"):
            return
        for tribe in self.tribes.values():
            for seal in tribe.get("old_grudge_seals", []) or []:
                if isinstance(seal, dict) and seal.get("sourceId") == source_id:
                    seal.update(patch)

    async def seal_old_grudge(self, player_id: str, other_tribe_id: str, anchor_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        other = self.tribes.get(other_tribe_id)
        if not tribe or not other:
            await self._send_tribe_error(player_id, "没有找到可封存的旧怨边界")
            return
        if not self._can_manage_old_grudge(tribe, player_id):
            await self._send_tribe_error(player_id, "只有首领或长老可以发起旧怨封存")
            return
        anchor = TRIBE_OLD_GRUDGE_ANCHORS.get(anchor_key)
        if not anchor:
            await self._send_tribe_error(player_id, "未知旧怨封存地点")
            return
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        target = self._old_grudge_target_for_relation(tribe, other_tribe_id, relation)
        if not target or not target.get("canSeal"):
            await self._send_tribe_error(player_id, "这条边界暂时不能发起新的旧怨封存")
            return
        now = datetime.now()
        source_id = f"old_grudge_{tribe_id}_{other_tribe_id}_{int(now.timestamp() * 1000)}"
        member = tribe.get("members", {}).get(player_id, {})
        active_until = datetime.fromtimestamp(now.timestamp() + TRIBE_OLD_GRUDGE_SEAL_ACTIVE_MINUTES * 60).isoformat()
        source_label = target.get("sourceLabel", "旧怨")
        for own, target_tribe in ((tribe, other), (other, tribe)):
            own_id = own.get("id")
            target_id = target_tribe.get("id")
            own_relation = own.setdefault("boundary_relations", {}).setdefault(target_id, {})
            own_relation["temperatureTone"] = "cool"
            before = int(own_relation.get("warPressure", 0) or 0)
            own_relation["warPressure"] = max(0, before - 1)
            own_relation["canDeclareWar"] = int(own_relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            seal = {
                "id": f"{source_id}_{own_id}",
                "sourceId": source_id,
                "status": "active",
                "otherTribeId": target_id,
                "otherTribeName": target_tribe.get("name", "邻近部落"),
                "anchorKey": anchor_key,
                "anchorLabel": anchor.get("label", "封存地"),
                "summary": anchor.get("summary", ""),
                "sourceLabel": source_label,
                "progress": 0,
                "target": TRIBE_OLD_GRUDGE_SEAL_TARGET,
                "participants": [],
                "createdBy": player_id,
                "createdByName": member.get("name", "成员"),
                "createdAt": now.isoformat(),
                "activeUntil": active_until
            }
            own.setdefault("old_grudge_seals", []).append(seal)
            own["old_grudge_seals"] = own["old_grudge_seals"][-TRIBE_OLD_GRUDGE_RECENT_LIMIT:]
        detail = f"{member.get('name', '成员')} 把与 {other.get('name', '邻近部落')} 的旧怨封在“{anchor.get('label', '封存地')}”：{source_label}。"
        self._add_tribe_history(tribe, "diplomacy", "旧怨封存", detail, player_id, {"kind": "old_grudge_seal", "sourceId": source_id, "otherTribeId": other_tribe_id})
        self._add_tribe_history(other, "diplomacy", "旧怨封存", detail, player_id, {"kind": "old_grudge_seal", "sourceId": source_id, "otherTribeId": tribe_id})
        await self._publish_world_rumor(
            "diplomacy",
            "旧怨封存",
            f"{tribe.get('name', '部落')} 与 {other.get('name', '邻近部落')} 把一段旧怨封在“{anchor.get('label', '封存地')}”，边境暂时降温。",
            {"tribeId": tribe_id, "otherTribeId": other_tribe_id, "sourceId": source_id}
        )
        await self._notify_tribe(tribe_id, detail)
        await self._notify_tribe(other_tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.broadcast_tribe_state(other_tribe_id)

    async def tend_old_grudge_seal(self, player_id: str, seal_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        seal = next((item for item in self._active_old_grudge_seals(tribe) if item.get("id") == seal_id), None)
        if not seal:
            await self._send_tribe_error(player_id, "这段旧怨封存已经结束")
            return
        action = TRIBE_OLD_GRUDGE_SEAL_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知旧怨维护方式")
            return
        if any(item.get("memberId") == player_id for item in seal.get("participants", []) or []):
            await self._send_tribe_error(player_id, "你已经维护过这段旧怨封存")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        if int(storage.get("wood", 0) or 0) < int(action.get("woodCost", 0) or 0):
            await self._send_tribe_error(player_id, f"{action.get('label', '维护')}需要公共木材{action.get('woodCost')}")
            return
        if int(tribe.get("food", 0) or 0) < int(action.get("foodCost", 0) or 0):
            await self._send_tribe_error(player_id, f"{action.get('label', '维护')}需要公共食物{action.get('foodCost')}")
            return
        other_id = seal.get("otherTribeId")
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
        reward_parts = self._apply_old_grudge_reward(tribe, relation, action)
        member = tribe.get("members", {}).get(player_id, {})
        participant = {
            "memberId": player_id,
            "memberName": member.get("name", "成员"),
            "actionKey": action_key,
            "actionLabel": action.get("label", "维护"),
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        seal.setdefault("participants", []).append(participant)
        seal["progress"] = int(seal.get("progress", 0) or 0) + 1
        completed = seal["progress"] >= int(seal.get("target", TRIBE_OLD_GRUDGE_SEAL_TARGET) or TRIBE_OLD_GRUDGE_SEAL_TARGET)
        if completed:
            seal["status"] = "sealed"
            seal["sealedAt"] = datetime.now().isoformat()
            record = {
                "id": f"old_grudge_record_{seal.get('sourceId')}_{tribe_id}",
                "sourceId": seal.get("sourceId"),
                "otherTribeId": other_id,
                "otherTribeName": seal.get("otherTribeName"),
                "anchorLabel": seal.get("anchorLabel"),
                "sourceLabel": seal.get("sourceLabel"),
                "participantNames": [item.get("memberName", "成员") for item in seal.get("participants", [])],
                "rewardParts": reward_parts,
                "createdAt": seal["sealedAt"]
            }
            tribe.setdefault("old_grudge_records", []).append(record)
            tribe["old_grudge_records"] = tribe["old_grudge_records"][-TRIBE_OLD_GRUDGE_RECENT_LIMIT:]
            self._mirror_old_grudge_seal(seal.get("sourceId"), {"status": "sealed", "sealedAt": seal["sealedAt"], "progress": seal["progress"]})
        else:
            self._mirror_old_grudge_seal(seal.get("sourceId"), {"progress": seal["progress"]})
        detail = f"{participant['memberName']} 在“{seal.get('anchorLabel', '封存地')}”执行{participant['actionLabel']}，维护与 {seal.get('otherTribeName', '邻近部落')} 的旧怨封存：{'、'.join(reward_parts) or '旧怨继续被压住'}。"
        if completed:
            detail += " 这段旧怨暂时封稳了。"
        self._add_tribe_history(tribe, "diplomacy", "维护旧怨封存", detail, player_id, {"kind": "old_grudge_tend", "sealId": seal_id, "actionKey": action_key, "completed": completed})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        if completed and other_id in self.tribes:
            await self.broadcast_tribe_state(other_id)

    def _wake_old_grudge_after_pressure(self, tribe: dict, other_tribe_id: str, source_label: str) -> dict | None:
        if not tribe or not other_tribe_id:
            return None
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        if int(relation.get("warPressure", 0) or 0) < TRIBE_OLD_GRUDGE_WAKE_PRESSURE:
            return None
        seal = next((item for item in self._active_old_grudge_seals(tribe) if item.get("otherTribeId") == other_tribe_id), None)
        if not seal:
            return None
        if any(task.get("sourceId") == seal.get("sourceId") and task.get("status") == "pending" for task in tribe.get("old_grudge_wake_tasks", []) or []):
            return None
        seal["status"] = "awakened"
        seal["awakenedAt"] = datetime.now().isoformat()
        other = self.tribes.get(other_tribe_id) if hasattr(self, "tribes") else {}
        task = {
            "id": f"old_grudge_wake_{seal.get('sourceId')}_{tribe.get('id')}",
            "status": "pending",
            "sourceId": seal.get("sourceId"),
            "otherTribeId": other_tribe_id,
            "otherTribeName": (other or {}).get("name", seal.get("otherTribeName", "邻近部落")),
            "title": "旧怨苏醒",
            "summary": f"{source_label} 让封在“{seal.get('anchorLabel', '封存地')}”的旧怨重新冒头，需要成员重新整理边界标记。",
            "woodCost": TRIBE_OLD_GRUDGE_WAKE_REPAIR["woodCost"],
            "foodCost": TRIBE_OLD_GRUDGE_WAKE_REPAIR["foodCost"],
            "renownReward": TRIBE_OLD_GRUDGE_WAKE_REPAIR["renown"],
            "pressureRelief": TRIBE_OLD_GRUDGE_WAKE_REPAIR["warPressureRelief"],
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("old_grudge_wake_tasks", []).append(task)
        tribe["old_grudge_wake_tasks"] = tribe["old_grudge_wake_tasks"][-TRIBE_OLD_GRUDGE_WAKE_TASK_LIMIT:]
        return task

    async def settle_old_grudge_wake_task(self, player_id: str, task_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((item for item in tribe.get("old_grudge_wake_tasks", []) or [] if isinstance(item, dict) and item.get("id") == task_id and item.get("status") == "pending"), None)
        if not task:
            await self._send_tribe_error(player_id, "没有找到可处理的旧怨苏醒任务")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(task.get("woodCost", 0) or 0)
        food_cost = int(task.get("foodCost", 0) or 0)
        if int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"处理旧怨苏醒需要公共木材{wood_cost}")
            return
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"处理旧怨苏醒需要公共食物{food_cost}")
            return
        other_id = task.get("otherTribeId")
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
        reward_parts = self._apply_old_grudge_reward(tribe, relation, {
            "woodCost": wood_cost,
            "foodCost": food_cost,
            "renown": int(task.get("renownReward", 0) or 0),
            "warPressureRelief": int(task.get("pressureRelief", 0) or 0),
            "relationDelta": 1
        })
        task["status"] = "completed"
        task["completedAt"] = datetime.now().isoformat()
        task["completedBy"] = player_id
        member = tribe.get("members", {}).get(player_id, {})
        record = {
            "id": f"old_grudge_wake_record_{task_id}",
            "sourceId": task.get("sourceId"),
            "otherTribeId": other_id,
            "otherTribeName": task.get("otherTribeName"),
            "anchorLabel": "苏醒补封",
            "sourceLabel": task.get("title", "旧怨苏醒"),
            "participantNames": [member.get("name", "成员")],
            "rewardParts": reward_parts,
            "createdAt": task["completedAt"]
        }
        tribe.setdefault("old_grudge_records", []).append(record)
        tribe["old_grudge_records"] = tribe["old_grudge_records"][-TRIBE_OLD_GRUDGE_RECENT_LIMIT:]
        self._mirror_old_grudge_seal(task.get("sourceId"), {"status": "sealed", "sealedAt": task["completedAt"]})
        detail = f"{member.get('name', '成员')} 处理“{task.get('title', '旧怨苏醒')}”：{'、'.join(reward_parts) or '旧怨重新封稳'}。"
        self._add_tribe_history(tribe, "diplomacy", "旧怨苏醒补封", detail, player_id, {"kind": "old_grudge_wake", "taskId": task_id, "record": record})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
