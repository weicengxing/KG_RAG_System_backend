from datetime import datetime
import random

from game_config import *


class GameLawMixin:
    def _active_tribe_law(self, tribe: dict) -> dict | None:
        law = tribe.get("active_law") if isinstance(tribe, dict) else None
        if not isinstance(law, dict) or law.get("status") != "active":
            return None
        active_until = law.get("activeUntil")
        if active_until:
            try:
                if datetime.fromisoformat(active_until) <= datetime.now():
                    law["status"] = "expired"
                    return None
            except (TypeError, ValueError):
                law["status"] = "expired"
                return None
        return law

    def _public_tribe_law(self, tribe: dict) -> dict | None:
        law = self._active_tribe_law(tribe)
        if not law:
            return None
        return {
            "id": law.get("id"),
            "key": law.get("key"),
            "label": law.get("label"),
            "summary": law.get("summary"),
            "upholdLabel": law.get("upholdLabel"),
            "breakLabel": law.get("breakLabel"),
            "upholders": list(law.get("upholders", []) or [])[-8:],
            "breakers": list(law.get("breakers", []) or [])[-8:],
            "eventBonuses": list(law.get("eventBonuses", []) or [])[-5:],
            "activeUntil": law.get("activeUntil"),
            "createdAt": law.get("createdAt"),
            "createdByName": law.get("createdByName")
        }

    def _public_law_remedies(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("law_remedies", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-TRIBE_LAW_REMEDY_LIMIT:]

    def _public_law_records(self, tribe: dict) -> list:
        return [item for item in tribe.get("law_records", []) or [] if isinstance(item, dict)][-TRIBE_LAW_RECORD_LIMIT:]

    def _law_matches_event(self, law_key: str, event_key: str) -> bool:
        if law_key == "border_watch":
            return event_key in {
                "boundary_greet",
                "boundary_guard",
                "boundary_truce",
                "boundary_relief",
                "boundary_joint_watch"
            }
        if law_key == "market_tally":
            return event_key in {"trade_accept", "caravan_trade", "market_pact_trade"}
        if law_key == "fire_quiet":
            return event_key in {"world_event", "herd", "storm", "ruin_clue", "rare_ruin"}
        return False

    def _law_violation_matches_event(self, law_key: str, event_key: str) -> bool:
        if law_key == "border_watch":
            return event_key in {"boundary_press", "boundary_blockade", "boundary_drive_away"}
        if law_key == "market_tally":
            return event_key in {"trade_cancel", "trade_reject"}
        if law_key == "fire_quiet":
            return event_key in {"boundary_press", "boundary_blockade", "boundary_drive_away"}
        return False

    def _apply_law_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                parts.append(f"{label}+{amount}")
        food = int((reward or {}).get("food", 0) or 0)
        if food:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) + food)
            parts.append(f"食物+{food}")
        renown = int((reward or {}).get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            parts.append(f"声望+{renown}")
        discovery = int((reward or {}).get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            parts.append(f"发现+{discovery}")
        trade = int((reward or {}).get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            parts.append(f"贸易信誉+{trade}")
        pressure_relief = int((reward or {}).get("pressureRelief", 0) or 0)
        if pressure_relief:
            for relation in (tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            parts.append(f"战争压力-{pressure_relief}")
        return parts

    def _can_manage_law(self, tribe: dict, player_id: str) -> bool:
        return player_id == tribe.get("leader_id") or player_id in set(tribe.get("elder_ids", []) or [])

    async def enact_tribe_law(self, player_id: str, law_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not self._can_manage_law(tribe, player_id):
            await self._send_tribe_error(player_id, "只有首领或长老可以启用部落律令")
            return
        option = TRIBE_LAW_OPTIONS.get(law_key)
        if not option:
            await self._send_tribe_error(player_id, "未知部落律令")
            return
        if self._active_tribe_law(tribe):
            await self._send_tribe_error(player_id, "当前已有生效中的部落律令")
            return
        member = tribe.get("members", {}).get(player_id, {})
        now = datetime.now()
        law = {
            "id": f"law_{tribe_id}_{law_key}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "key": law_key,
            "label": option.get("label", "部落律令"),
            "summary": option.get("summary", ""),
            "upholdLabel": option.get("upholdLabel", "遵守律令"),
            "breakLabel": option.get("breakLabel", "违背律令"),
            "upholders": [],
            "breakers": [],
            "eventBonuses": [],
            "createdBy": player_id,
            "createdByName": member.get("name", "成员"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_LAW_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["active_law"] = law
        detail = f"{member.get('name', '成员')} 启用“{law['label']}”：{law['summary']}"
        self._add_tribe_history(tribe, "governance", "部落法律牌", detail, player_id, {"kind": "tribe_law", "law": law})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def uphold_tribe_law(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        law = self._active_tribe_law(tribe or {})
        if not tribe or not law:
            await self._send_tribe_error(player_id, "当前没有可以遵守的部落律令")
            return
        if any(item.get("memberId") == player_id for item in law.get("upholders", []) or []):
            await self._send_tribe_error(player_id, "你已经参与过这条律令")
            return
        option = TRIBE_LAW_OPTIONS.get(law.get("key"), {})
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_law_reward(tribe, option.get("upholdReward", {}))
        item = {
            "memberId": player_id,
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        law.setdefault("upholders", []).append(item)
        detail = f"{member.get('name', '成员')} 完成“{law.get('upholdLabel', '遵守律令')}”：{'、'.join(reward_parts) or '律令被记住'}。"
        self._add_tribe_history(tribe, "governance", "遵守部落律令", detail, player_id, {"kind": "tribe_law_uphold", "lawKey": law.get("key"), "rewardParts": reward_parts})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    def _record_law_violation(self, tribe: dict, player_id: str, event_key: str, source_label: str = "") -> dict | None:
        law = self._active_tribe_law(tribe)
        if not law or not self._law_violation_matches_event(law.get("key"), event_key):
            return None
        option = TRIBE_LAW_OPTIONS.get(law.get("key"), {})
        member = tribe.get("members", {}).get(player_id, {}) if isinstance(tribe, dict) else {}
        now = datetime.now()
        law.setdefault("breakers", []).append({
            "memberId": player_id,
            "memberName": member.get("name", "成员"),
            "eventKey": event_key,
            "sourceLabel": source_label,
            "createdAt": now.isoformat()
        })
        remedy = {
            "id": f"law_remedy_{law.get('id')}_{event_key}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "pending",
            "lawId": law.get("id"),
            "lawKey": law.get("key"),
            "lawLabel": law.get("label"),
            "title": option.get("remedyTitle", "律令补救"),
            "summary": option.get("remedySummary", "成员需要公开补救这次违令。"),
            "woodCost": int((option.get("remedyCost") or {}).get("wood", 0) or 0),
            "foodCost": int((option.get("remedyCost") or {}).get("food", 0) or 0),
            "createdBy": player_id,
            "createdByName": member.get("name", "成员"),
            "sourceLabel": source_label,
            "createdAt": now.isoformat()
        }
        tribe.setdefault("law_remedies", []).append(remedy)
        tribe["law_remedies"] = tribe["law_remedies"][-TRIBE_LAW_REMEDY_LIMIT:]
        return remedy

    def apply_tribe_law_violation(self, tribe: dict, player_id: str, event_key: str, source_label: str = "") -> list:
        remedy = self._record_law_violation(tribe, player_id, event_key, source_label)
        if not remedy:
            return []
        return [f"{remedy.get('lawLabel', '律令')}违令", f"留下{remedy.get('title', '补救')}"]

    async def break_tribe_law(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        law = self._active_tribe_law(tribe or {})
        if not tribe or not law:
            await self._send_tribe_error(player_id, "当前没有可以违背的部落律令")
            return
        option = TRIBE_LAW_OPTIONS.get(law.get("key"), {})
        member = tribe.get("members", {}).get(player_id, {})
        now = datetime.now()
        breaker = {"memberId": player_id, "memberName": member.get("name", "成员"), "createdAt": now.isoformat()}
        law.setdefault("breakers", []).append(breaker)
        remedy = {
            "id": f"law_remedy_{law.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "pending",
            "lawId": law.get("id"),
            "lawKey": law.get("key"),
            "lawLabel": law.get("label"),
            "title": option.get("remedyTitle", "律令补救"),
            "summary": option.get("remedySummary", "成员需要公开补救这次违令。"),
            "woodCost": int((option.get("remedyCost") or {}).get("wood", 0) or 0),
            "foodCost": int((option.get("remedyCost") or {}).get("food", 0) or 0),
            "createdBy": player_id,
            "createdByName": member.get("name", "成员"),
            "createdAt": now.isoformat()
        }
        tribe.setdefault("law_remedies", []).append(remedy)
        tribe["law_remedies"] = tribe["law_remedies"][-TRIBE_LAW_REMEDY_LIMIT:]
        detail = f"{member.get('name', '成员')} 违背“{law.get('label', '部落律令')}”，留下“{remedy['title']}”。"
        self._add_tribe_history(tribe, "governance", "违背部落律令", detail, player_id, {"kind": "tribe_law_break", "lawKey": law.get("key"), "remedy": remedy})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_law_remedy(self, player_id: str, remedy_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        remedy = next((item for item in tribe.get("law_remedies", []) or [] if isinstance(item, dict) and item.get("id") == remedy_id and item.get("status") == "pending"), None)
        if not remedy:
            await self._send_tribe_error(player_id, "这条律令补救已经结束")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(remedy.get("woodCost", 0) or 0)
        food_cost = int(remedy.get("foodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"律令补救需要木材{wood_cost}")
            return
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"律令补救需要公共食物{food_cost}")
            return
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        option = TRIBE_LAW_OPTIONS.get(remedy.get("lawKey"), {})
        reward_parts = []
        if wood_cost:
            reward_parts.append(f"木材-{wood_cost}")
        if food_cost:
            reward_parts.append(f"食物-{food_cost}")
        reward_parts.extend(self._apply_law_reward(tribe, option.get("remedyReward", {})))
        ash_promise = self._apply_ash_ledger_promise_bonus(tribe, "律令补救", "", datetime.now().isoformat())
        reward_parts.extend(ash_promise.get("parts", []))
        remedy["status"] = "completed"
        remedy["completedAt"] = datetime.now().isoformat()
        remedy["completedBy"] = player_id
        remedy["completedByName"] = (tribe.get("members", {}).get(player_id, {}) or {}).get("name", "成员")
        record = {
            "id": f"law_record_{remedy.get('id')}",
            "lawKey": remedy.get("lawKey"),
            "lawLabel": remedy.get("lawLabel"),
            "title": remedy.get("title"),
            "rewardParts": reward_parts,
            "sourceChain": ash_promise.get("sourceChain", []),
            "completedByName": remedy["completedByName"],
            "createdAt": remedy["completedAt"]
        }
        if ash_promise.get("parts"):
            remedy["ashLedgerPromise"] = ash_promise
        tribe.setdefault("law_records", []).append(record)
        tribe["law_records"] = tribe["law_records"][-TRIBE_LAW_RECORD_LIMIT:]
        detail = f"{record['completedByName']} 完成“{record['title']}”：{'、'.join(reward_parts) or '补救完成'}。"
        self._add_tribe_history(tribe, "governance", "律令补救完成", detail, player_id, {"kind": "tribe_law_remedy", "record": record})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    def apply_tribe_law_event_bonus(self, tribe: dict, event_key: str, source_label: str = "") -> list:
        law = self._active_tribe_law(tribe)
        if not law:
            return []
        if not self._law_matches_event(law.get("key"), event_key):
            return []
        option = TRIBE_LAW_OPTIONS.get(law.get("key"), {})
        reward = dict(option.get("eventBonus") or {})
        if not reward:
            return []
        reward_parts = self._apply_law_reward(tribe, reward)
        if not reward_parts:
            return []
        law.setdefault("eventBonuses", []).append({
            "eventKey": event_key,
            "sourceLabel": source_label,
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        })
        return [f"{law.get('label', '律令')}:{part}" for part in reward_parts]
