from datetime import datetime

from game_config import *


class GameCampDebtMixin:
    def _camp_debt_expired(self, debt: dict) -> bool:
        try:
            return datetime.fromisoformat(debt.get("activeUntil", "")) <= datetime.now()
        except (TypeError, ValueError):
            return False

    def _camp_debt_source_seen(self, tribe: dict, source_id: str) -> bool:
        if not source_id:
            return True
        for debt in tribe.get("camp_debts", []) or []:
            if isinstance(debt, dict) and debt.get("sourceId") == source_id:
                return True
        return False

    def _camp_debt_candidates(self, tribe: dict) -> list:
        candidates = []
        pressure = self._tribe_food_pressure_state(tribe)
        if pressure.get("active"):
            candidates.append({
                "sourceId": "food_pressure",
                "sourceKind": "food_pressure",
                "title": "公共食物债账",
                "summary": f"公共食物低于安全线 {pressure.get('safeLine', 0)}，需要有人补账或公开说明分配。",
                "sourceLabel": "食物压力",
                "otherTribeId": "",
                "otherTribeName": ""
            })

        for stay in (tribe.get("guest_stays", []) or [])[-TRIBE_CAMP_DEBT_SOURCE_SCAN_LIMIT:]:
            if not isinstance(stay, dict) or not stay.get("id"):
                continue
            if stay.get("actionKey") not in {"relief_help", "market_help", "build_help"}:
                continue
            other_name = stay.get("hostTribeName") if stay.get("direction") == "outgoing" else stay.get("sourceTribeName")
            other_id = stay.get("hostTribeId") if stay.get("direction") == "outgoing" else stay.get("sourceTribeId")
            candidates.append({
                "sourceId": f"guest:{stay.get('id')}",
                "sourceKind": "guest_stay",
                "title": "客居往来债账",
                "summary": f"{stay.get('guestName', '成员')} 的“{stay.get('label', '短期客居')}”留下了公共人情，可以补账、豁免或转成互市口信。",
                "sourceLabel": stay.get("label", "短期客居"),
                "otherTribeId": other_id or "",
                "otherTribeName": other_name or ""
            })
        return candidates

    def _ensure_camp_debts(self, tribe: dict):
        if not tribe:
            return
        now = datetime.now()
        debts = []
        for debt in tribe.get("camp_debts", []) or []:
            if not isinstance(debt, dict):
                continue
            if debt.get("status") == "pending" and self._camp_debt_expired(debt):
                debt["status"] = "stale"
                debt["staleAt"] = now.isoformat()
            debts.append(debt)
        tribe["camp_debts"] = debts[-TRIBE_CAMP_DEBT_LIMIT:]

        pending = [
            debt for debt in tribe.get("camp_debts", []) or []
            if isinstance(debt, dict) and debt.get("status") == "pending"
        ]
        if len(pending) >= TRIBE_CAMP_DEBT_PENDING_LIMIT:
            return
        for candidate in self._camp_debt_candidates(tribe):
            source_id = candidate.get("sourceId", "")
            if self._camp_debt_source_seen(tribe, source_id):
                continue
            active_until = datetime.fromtimestamp(now.timestamp() + TRIBE_CAMP_DEBT_ACTIVE_MINUTES * 60).isoformat()
            debt = {
                "id": f"camp_debt_{int(now.timestamp() * 1000)}_{len(tribe.get('camp_debts', []) or [])}",
                "status": "pending",
                "title": candidate.get("title", "营地债账"),
                "summary": candidate.get("summary", ""),
                "sourceId": source_id,
                "sourceKind": candidate.get("sourceKind", "camp"),
                "sourceLabel": candidate.get("sourceLabel", "公共消耗"),
                "otherTribeId": candidate.get("otherTribeId", ""),
                "otherTribeName": candidate.get("otherTribeName", ""),
                "activeUntil": active_until,
                "createdAt": now.isoformat()
            }
            tribe.setdefault("camp_debts", []).append(debt)
            pending.append(debt)
            if len(pending) >= TRIBE_CAMP_DEBT_PENDING_LIMIT:
                break
        tribe["camp_debts"] = tribe.get("camp_debts", [])[-TRIBE_CAMP_DEBT_LIMIT:]

    def _public_camp_debts(self, tribe: dict) -> list:
        self._ensure_camp_debts(tribe)
        return [
            debt for debt in (tribe.get("camp_debts", []) or [])
            if isinstance(debt, dict) and debt.get("status") == "pending"
        ][-TRIBE_CAMP_DEBT_PENDING_LIMIT:]

    def _public_camp_debt_records(self, tribe: dict) -> list:
        return [
            debt for debt in (tribe.get("camp_debts", []) or [])
            if isinstance(debt, dict) and debt.get("status") in {"settled", "forgiven", "market_note", "stale"}
        ][-TRIBE_CAMP_DEBT_RECORD_LIMIT:]

    def _camp_debt_by_id(self, tribe: dict, debt_id: str) -> dict | None:
        return next((
            debt for debt in (tribe.get("camp_debts", []) or [])
            if isinstance(debt, dict) and debt.get("id") == debt_id
        ), None)

    def _apply_camp_debt_relation(self, tribe: dict, debt: dict, action: dict, now_text: str) -> list:
        other_id = debt.get("otherTribeId")
        other = self.tribes.get(other_id) if other_id else None
        if not other:
            return []
        relation_delta = int(action.get("relationDelta", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        parts = []
        for source, target in ((tribe, other), (other, tribe)):
            relation = source.setdefault("boundary_relations", {}).setdefault(target.get("id"), {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            relation["lastAction"] = "camp_debt"
            relation["lastActionAt"] = now_text
        if relation_delta:
            parts.append(f"关系{relation_delta:+d}")
        if trust_delta:
            parts.append(f"信任+{trust_delta}")
        return parts

    def _apply_camp_debt_pressure_relief(self, tribe: dict, amount: int) -> int:
        relieved = 0
        for relation in (tribe.get("boundary_relations", {}) or {}).values():
            if not isinstance(relation, dict):
                continue
            before = int(relation.get("warPressure", 0) or 0)
            if before <= 0:
                continue
            relation["warPressure"] = max(0, before - amount)
            relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relieved += before - int(relation.get("warPressure", 0) or 0)
        return relieved

    async def resolve_camp_debt(self, player_id: str, debt_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        debt = self._camp_debt_by_id(tribe, debt_id)
        action = TRIBE_CAMP_DEBT_ACTIONS.get(action_key)
        if not debt or debt.get("status") != "pending":
            await self._send_tribe_error(player_id, "这条营地债账已经结束")
            return
        if not action:
            await self._send_tribe_error(player_id, "未知债账处理")
            return
        if self._camp_debt_expired(debt):
            debt["status"] = "stale"
            await self._send_tribe_error(player_id, "这条营地债账已经散去")
            await self.broadcast_tribe_state(tribe_id)
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(action.get("woodCost", 0) or 0)
        food_cost = int(action.get("foodCost", 0) or 0)
        if int(storage.get("wood", 0) or 0) < wood_cost or int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, "公共木材或食物不足，无法补这笔债账")
            return
        storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost

        reward_parts = []
        if wood_cost:
            reward_parts.append(f"木材-{wood_cost}")
        if food_cost:
            reward_parts.append(f"食物-{food_cost}")
        for key, label, field in (
            ("wood", "木材", "storage"),
            ("stone", "石块", "storage"),
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("tradeReputation", "贸易信誉", "trade_reputation")
        ):
            amount = int(action.get(key, 0) or 0)
            if not amount:
                continue
            if field == "storage":
                storage[key] = int(storage.get(key, 0) or 0) + amount
            else:
                tribe[field] = int(tribe.get(field, 0) or 0) + amount
            reward_parts.append(f"{label}+{amount}")
        pressure_relief = int(action.get("pressureRelief", 0) or 0)
        if pressure_relief:
            relieved = self._apply_camp_debt_pressure_relief(tribe, pressure_relief)
            if relieved:
                reward_parts.append(f"战争压力-{relieved}")
        now_text = datetime.now().isoformat()
        reward_parts.extend(self._apply_camp_debt_relation(tribe, debt, action, now_text))

        member = tribe.get("members", {}).get(player_id, {})
        debt["status"] = action.get("status", action_key)
        debt["actionKey"] = action_key
        debt["actionLabel"] = action.get("label", "处理债账")
        debt["resolvedBy"] = player_id
        debt["resolvedByName"] = member.get("name", self._get_player_name(player_id))
        debt["resolvedAt"] = now_text
        debt["rewardParts"] = reward_parts
        detail = f"{debt.get('resolvedByName', '成员')} 对“{debt.get('title', '营地债账')}”选择“{action.get('label', '处理')}”：{'、'.join(reward_parts) or '债账被公开记下'}。"
        self._add_tribe_history(tribe, "trade", "营地债账处理", detail, player_id, {"kind": "camp_debt", **debt})
        await self._publish_world_rumor(
            "trade",
            "营地债账处理",
            f"{tribe.get('name', '部落')} 把一笔{debt.get('sourceLabel', '公共消耗')}债账处理成了“{action.get('label', '公开记录')}”。",
            {"tribeId": tribe_id, "debtId": debt_id, "action": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
