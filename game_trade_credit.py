from datetime import datetime

from game_config import *


class GameTradeCreditMixin:
    def _trade_credit_tier_for_streak(self, streak: int) -> dict | None:
        streak = max(0, int(streak or 0))
        matched = None
        for tier in TRIBE_TRADE_CREDIT_TIERS:
            if streak >= int(tier.get("minStreak", 0) or 0):
                matched = tier
        return matched

    def _active_trade_credit_records(self, tribe: dict) -> list:
        if not tribe:
            return []
        active = []
        now = datetime.now()
        for record in tribe.get("trade_credit_records", []) or []:
            if not isinstance(record, dict):
                continue
            active_until = record.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        record["status"] = "expired"
                        continue
                except (TypeError, ValueError):
                    record["status"] = "expired"
                    continue
            if record.get("status", "active") == "active":
                active.append(record)
        if len(active) != len(tribe.get("trade_credit_records", []) or []):
            tribe["trade_credit_records"] = active[-TRIBE_TRADE_CREDIT_RECORD_LIMIT:]
        return active[-TRIBE_TRADE_CREDIT_RECORD_LIMIT:]

    def _trade_credit_between(self, tribe: dict, other_tribe_id: str) -> dict | None:
        if not tribe or not other_tribe_id:
            return None
        return next((
            record for record in self._active_trade_credit_records(tribe)
            if record.get("otherTribeId") == other_tribe_id
        ), None)

    def _public_trade_credit_repairs(self, tribe: dict) -> list:
        return [
            task for task in (tribe.get("trade_credit_repairs", []) or [])
            if isinstance(task, dict) and task.get("status") == "pending"
        ][-TRIBE_TRADE_CREDIT_REPAIR_LIMIT:]

    def _public_trade_credit_config(self) -> dict:
        return {
            "activeMinutes": TRIBE_TRADE_CREDIT_ACTIVE_MINUTES,
            "repairWoodCost": TRIBE_TRADE_CREDIT_REPAIR_WOOD_COST,
            "repairFoodCost": TRIBE_TRADE_CREDIT_REPAIR_FOOD_COST,
            "tiers": TRIBE_TRADE_CREDIT_TIERS
        }

    def _trade_credit_public_summary(self, record: dict | None) -> dict | None:
        if not record:
            return None
        return {
            "id": record.get("id"),
            "key": record.get("key"),
            "label": record.get("label"),
            "summary": record.get("summary"),
            "otherTribeId": record.get("otherTribeId"),
            "otherTribeName": record.get("otherTribeName"),
            "streak": int(record.get("streak", 0) or 0),
            "requestDiscount": int(record.get("requestDiscount", 0) or 0),
            "reputationBonus": int(record.get("reputationBonus", 0) or 0),
            "stockBonus": int(record.get("stockBonus", 0) or 0),
            "activeUntil": record.get("activeUntil"),
            "createdAt": record.get("createdAt")
        }

    def _upsert_trade_credit_record(self, tribe: dict, other_tribe: dict, shared_id: str, streak: int, now_text: str) -> dict | None:
        tier = self._trade_credit_tier_for_streak(streak)
        if not tier:
            return None
        other_id = other_tribe.get("id")
        active_until = datetime.fromtimestamp(
            datetime.now().timestamp() + TRIBE_TRADE_CREDIT_ACTIVE_MINUTES * 60
        ).isoformat()
        records = [
            record for record in (tribe.get("trade_credit_records", []) or [])
            if isinstance(record, dict) and record.get("otherTribeId") != other_id
        ]
        record = {
            "id": f"{shared_id}_{tribe.get('id')}",
            "status": "active",
            "key": tier.get("key"),
            "label": tier.get("label", "贸易信用"),
            "summary": tier.get("summary", ""),
            "otherTribeId": other_id,
            "otherTribeName": other_tribe.get("name", "邻近部落"),
            "streak": streak,
            "requestDiscount": int(tier.get("requestDiscount", 0) or 0),
            "reputationBonus": int(tier.get("reputationBonus", 0) or 0),
            "stockBonus": int(tier.get("stockBonus", 0) or 0),
            "createdAt": now_text,
            "activeUntil": active_until
        }
        records.append(record)
        tribe["trade_credit_records"] = records[-TRIBE_TRADE_CREDIT_RECORD_LIMIT:]
        return record

    def _record_trade_credit_success(self, from_tribe: dict, to_tribe: dict, trade: dict, now_text: str) -> dict:
        from_id = from_tribe.get("id")
        to_id = to_tribe.get("id")
        from_relation = from_tribe.setdefault("boundary_relations", {}).setdefault(to_id, {})
        to_relation = to_tribe.setdefault("boundary_relations", {}).setdefault(from_id, {})
        next_streak = max(
            int(from_relation.get("tradeCreditStreak", 0) or 0),
            int(to_relation.get("tradeCreditStreak", 0) or 0)
        ) + 1
        for relation in (from_relation, to_relation):
            relation["tradeCreditStreak"] = next_streak
            relation["lastAction"] = "trade_credit_success"
            relation["lastActionAt"] = now_text

        shared_id = f"trade_credit_{from_id}_{to_id}_{int(datetime.now().timestamp() * 1000)}"
        from_record = self._upsert_trade_credit_record(from_tribe, to_tribe, shared_id, next_streak, now_text)
        to_record = self._upsert_trade_credit_record(to_tribe, from_tribe, shared_id, next_streak, now_text)
        if from_record:
            trade["earnedTradeCredit"] = self._trade_credit_public_summary(from_record)
        return {
            "streak": next_streak,
            "fromRecord": from_record,
            "toRecord": to_record
        }

    def _apply_trade_credit_on_create(self, tribe: dict, target_tribe_id: str, request_amount: int) -> dict:
        credit = self._trade_credit_between(tribe, target_tribe_id)
        if not credit:
            return {"credit": None, "discount": 0, "requestAmount": request_amount}
        discount = min(
            max(0, request_amount - 1),
            max(0, int(credit.get("requestDiscount", 0) or 0))
        )
        return {
            "credit": credit,
            "discount": discount,
            "requestAmount": max(1, request_amount - discount)
        }

    def _apply_trade_credit_on_accept(self, from_tribe: dict, to_tribe: dict, trade: dict) -> list:
        credit = trade.get("tradeCredit") if isinstance(trade.get("tradeCredit"), dict) else None
        if not credit:
            return []
        parts = []
        reputation_bonus = int(credit.get("reputationBonus", 0) or 0)
        if reputation_bonus:
            from_tribe["trade_reputation"] = int(from_tribe.get("trade_reputation", 0) or 0) + reputation_bonus
            to_tribe["trade_reputation"] = int(to_tribe.get("trade_reputation", 0) or 0) + reputation_bonus
            parts.append(f"{credit.get('label', '贸易信用')}信誉+{reputation_bonus}")
        stock_bonus = int(credit.get("stockBonus", 0) or 0)
        if stock_bonus:
            self._add_trade_resource(from_tribe, trade.get("request", {}).get("resource"), stock_bonus)
            self._add_trade_resource(to_tribe, trade.get("offer", {}).get("resource"), stock_bonus)
            parts.append(f"{credit.get('label', '贸易信用')}共同库存+{stock_bonus}")
        return parts

    def _open_trade_credit_repair_task(self, acting_tribe: dict, other_tribe: dict, trade: dict, action: str, now_text: str) -> dict | None:
        credit = trade.get("tradeCredit") if isinstance(trade.get("tradeCredit"), dict) else None
        if not acting_tribe or not other_tribe or not credit:
            return None
        other_id = other_tribe.get("id")
        task_id = f"trade_credit_repair_{trade.get('id')}_{acting_tribe.get('id')}"
        existing = next((
            task for task in (acting_tribe.get("trade_credit_repairs", []) or [])
            if isinstance(task, dict) and task.get("id") == task_id and task.get("status") == "pending"
        ), None)
        if existing:
            return existing
        reason_label = "取消赊账" if action == "cancel" else "拒绝信用贸易"
        task = {
            "id": task_id,
            "status": "pending",
            "kind": "trade_credit_repair",
            "title": "贸易信用修复",
            "summary": f"{reason_label}让与 {other_tribe.get('name', '邻近部落')} 的“{credit.get('label', '贸易信用')}”出现裂痕，需要保证人和补偿重新稳住账目。",
            "otherTribeId": other_id,
            "otherTribeName": other_tribe.get("name", "邻近部落"),
            "tradeId": trade.get("id"),
            "creditLabel": credit.get("label", "贸易信用"),
            "woodCost": TRIBE_TRADE_CREDIT_REPAIR_WOOD_COST,
            "foodCost": TRIBE_TRADE_CREDIT_REPAIR_FOOD_COST,
            "createdAt": now_text
        }
        acting_tribe.setdefault("trade_credit_repairs", []).append(task)
        acting_tribe["trade_credit_repairs"] = acting_tribe["trade_credit_repairs"][-TRIBE_TRADE_CREDIT_REPAIR_LIMIT:]
        relation = acting_tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
        relation["tradeTrust"] = max(0, int(relation.get("tradeTrust", 0) or 0) - 1)
        relation["tradeCreditStreak"] = 0
        relation["lastAction"] = "trade_credit_breach"
        relation["lastActionAt"] = now_text
        other_relation = other_tribe.setdefault("boundary_relations", {}).setdefault(acting_tribe.get("id"), {})
        other_relation["tradeTrust"] = max(0, int(other_relation.get("tradeTrust", 0) or 0) - 1)
        other_relation["tradeCreditStreak"] = 0
        other_relation["lastAction"] = "trade_credit_breach"
        other_relation["lastActionAt"] = now_text
        return task

    async def complete_trade_credit_repair(self, player_id: str, task_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((
            item for item in (tribe.get("trade_credit_repairs", []) or [])
            if isinstance(item, dict) and item.get("id") == task_id and item.get("status") == "pending"
        ), None)
        if not task:
            await self._send_tribe_error(player_id, "这条贸易信用修复已经结束")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(task.get("woodCost", 0) or 0)
        food_cost = int(task.get("foodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"贸易信用修复需要木材 {wood_cost}")
            return
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"贸易信用修复需要公共食物 {food_cost}")
            return
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        other_id = task.get("otherTribeId")
        other_tribe = self.tribes.get(other_id)
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
        relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + 1))
        relation["lastAction"] = "trade_credit_repaired"
        relation["lastActionAt"] = datetime.now().isoformat()
        tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + 1
        ash_promise = self._apply_ash_ledger_promise_bonus(tribe, "贸易信用修复", other_id, relation["lastActionAt"])
        if other_tribe:
            other_relation = other_tribe.setdefault("boundary_relations", {}).setdefault(tribe_id, {})
            other_relation["tradeTrust"] = max(0, min(10, int(other_relation.get("tradeTrust", 0) or 0) + 1))
            other_relation["lastAction"] = "trade_credit_repaired"
            other_relation["lastActionAt"] = relation["lastActionAt"]
        task["status"] = "completed"
        task["completedAt"] = relation["lastActionAt"]
        task["completedBy"] = player_id
        task["completedByName"] = (tribe.get("members", {}).get(player_id, {}) or {}).get("name", "成员")
        if ash_promise.get("parts"):
            task["ashLedgerPromise"] = ash_promise
        ash_detail = f" 灰烬账谱承诺：{'、'.join(ash_promise.get('parts', []))}。" if ash_promise.get("parts") else ""
        detail = f"{task['completedByName']} 完成“{task.get('title', '贸易信用修复')}”，向 {task.get('otherTribeName', '邻近部落')} 补交保证与口信，贸易信誉+1。{ash_detail}"
        self._add_tribe_history(tribe, "trade", "贸易信用修复", detail, player_id, {"kind": "trade_credit_repair", "task": task})
        await self._notify_tribe(tribe_id, detail)
        if other_tribe:
            await self._notify_tribe(other_id, f"{tribe.get('name', '部落')} 修复了与本部落的贸易信用。")
            await self.broadcast_tribe_state(other_id)
        await self.broadcast_tribe_state(tribe_id)
