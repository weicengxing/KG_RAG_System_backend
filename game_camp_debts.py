from datetime import datetime

from game_config import *


class GameCampDebtMixin:
    def _camp_debt_expired(self, debt: dict) -> bool:
        try:
            return datetime.fromisoformat(debt.get("activeUntil", "")) <= datetime.now()
        except (TypeError, ValueError):
            return False

    def _camp_debt_redeem_window_active(self, debt: dict) -> bool:
        try:
            created_at = datetime.fromisoformat(debt.get("createdAt", ""))
            active_until = datetime.fromisoformat(debt.get("activeUntil", ""))
        except (TypeError, ValueError):
            return False
        total = (active_until - created_at).total_seconds()
        remaining = (active_until - datetime.now()).total_seconds()
        if total <= 0 or remaining <= 0:
            return False
        elapsed = total - remaining
        return elapsed / total >= float(TRIBE_CAMP_DEBT_REDEEM_WINDOW_RATIO)

    def _camp_debt_available_action_keys(self, debt: dict) -> list:
        window_active = self._camp_debt_redeem_window_active(debt)
        return [
            key for key, action in TRIBE_CAMP_DEBT_ACTIONS.items()
            if not action.get("windowOnly") or window_active
        ]

    def _camp_debt_default_profile(self, debt: dict) -> dict:
        source_kind = debt.get("sourceKind", "")
        if source_kind in {"war_reparation", "war_ally_debt"}:
            return {"customKey": "warlike", "label": "好战", "tone": "守边和旧账会被讲得更硬。"}
        if source_kind in {"trade_credit", "guest_stay"}:
            return {"customKey": "merchant", "label": "重商", "tone": "互市口风会更在意欠账和履约。"}
        if source_kind in {"food_pressure", "disaster_relief"}:
            return {"customKey": "hearth", "label": "敬火", "tone": "营火旁的传闻会更常提到共同亏空。"}
        return {"customKey": "oathbound", "label": "守誓", "tone": "传闻会把这笔旧债挂到誓约和明账上。"}

    def _default_camp_debt(self, tribe: dict, debt: dict, now: datetime):
        if debt.get("defaultRecorded"):
            debt["status"] = "defaulted"
            return
        profile = self._camp_debt_default_profile(debt)
        debt["status"] = "defaulted"
        debt["staleAt"] = now.isoformat()
        debt["defaultedAt"] = now.isoformat()
        debt["actionLabel"] = "逾期未还"
        debt["defaultRecorded"] = True
        debt["personalityImpact"] = f"{profile.get('label')}倾向+1"
        debt["defaultConsequence"] = f"逾期未还，{profile.get('label')}性格倾向被推高，{profile.get('tone')}"
        debt["defaultRumorText"] = f"{tribe.get('name', '部落')} 没有赎回“{debt.get('title', '营地债账')}”，{profile.get('tone')}"
        if hasattr(self, "_record_tribe_custom_choice"):
            self._record_tribe_custom_choice(tribe, profile.get("customKey", ""), "营地债逾期", amount=1)
        if hasattr(self, "_add_tribe_history"):
            self._add_tribe_history(
                tribe,
                "trade",
                "营地债账逾期",
                debt["defaultRumorText"],
                "",
                {"kind": "camp_debt_default", **debt}
            )

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
                "otherTribeName": "",
                "sourceChain": ["公共食物", "安全线"]
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
                "title": "收留承诺公共债",
                "summary": f"{stay.get('guestName', '成员')} 的“{stay.get('label', '短期客居')}”留下了收留承诺，可以补账、豁免或转成互市口信。",
                "sourceLabel": stay.get("label", "短期客居"),
                "otherTribeId": other_id or "",
                "otherTribeName": other_name or "",
                "sourceChain": ["收留承诺", stay.get("label", "短期客居")]
            })
        for record in (tribe.get("disaster_coop_records", []) or [])[-TRIBE_CAMP_DEBT_SOURCE_SCAN_LIMIT:]:
            if not isinstance(record, dict) or not record.get("id"):
                continue
            candidates.append({
                "sourceId": f"disaster_debt:{record.get('id')}",
                "sourceKind": "disaster_relief",
                "title": "救灾欠粮公共债",
                "summary": f"{record.get('label', '大灾协作')}后还有粮柴、人手和口信需要公开补账，避免救灾消耗被忘掉。",
                "sourceLabel": record.get("label", "大灾协作"),
                "otherTribeId": "",
                "otherTribeName": "",
                "sourceChain": ["救灾欠粮", record.get("label", "大灾协作")]
            })
        for task in (tribe.get("war_diplomacy_tasks", []) or [])[-TRIBE_CAMP_DEBT_SOURCE_SCAN_LIMIT:]:
            if not isinstance(task, dict) or task.get("status") != "pending":
                continue
            candidates.append({
                "sourceId": f"war_diplomacy_debt:{task.get('id')}",
                "sourceKind": "war_reparation",
                "title": "战争赔偿公共债",
                "summary": f"与{task.get('otherTribeName', '其他部落')}的{task.get('modeLabel', '停战外交')}还未落定，可以先沉淀为公共债，标出补账、豁免或互市口信。",
                "sourceLabel": task.get("modeLabel", "战争赔偿"),
                "otherTribeId": task.get("otherTribeId", ""),
                "otherTribeName": task.get("otherTribeName", ""),
                "sourceChain": ["战争赔偿", task.get("modeLabel", "停战外交")]
            })
        for task in (tribe.get("war_ally_tasks", []) or [])[-TRIBE_CAMP_DEBT_SOURCE_SCAN_LIMIT:]:
            if not isinstance(task, dict) or task.get("status") != "pending":
                continue
            if task.get("kind") not in {"support_supply", "betrayal_reparation"}:
                continue
            candidates.append({
                "sourceId": f"war_ally_debt:{task.get('id')}",
                "sourceKind": "war_ally_debt",
                "title": "战盟承诺公共债",
                "summary": f"{task.get('title', '战盟后续')}还没有兑现，营地可以把它公开成可赎回的承诺债。",
                "sourceLabel": task.get("title", "战盟承诺"),
                "otherTribeId": task.get("otherTribeId", ""),
                "otherTribeName": task.get("otherTribeName", ""),
                "sourceChain": ["战争赔偿", task.get("title", "战盟承诺")]
            })
        for task in (tribe.get("trade_credit_repairs", []) or [])[-TRIBE_CAMP_DEBT_SOURCE_SCAN_LIMIT:]:
            if not isinstance(task, dict) or task.get("status") != "pending":
                continue
            candidates.append({
                "sourceId": f"trade_credit_debt:{task.get('id')}",
                "sourceKind": "trade_credit",
                "title": "商队信用公共债",
                "summary": f"与{task.get('otherTribeName', '邻近部落')}的{task.get('creditLabel', '贸易信用')}出现裂痕，需要把保证和补偿记成公共债。",
                "sourceLabel": task.get("creditLabel", "贸易信用"),
                "otherTribeId": task.get("otherTribeId", ""),
                "otherTribeName": task.get("otherTribeName", ""),
                "sourceChain": ["商队信用", task.get("creditLabel", "贸易信用")]
            })
        if hasattr(self, "_ash_ledger_sources"):
            for source in self._ash_ledger_sources(tribe):
                source_id = source.get("sourceId") or source.get("id")
                if not source_id:
                    continue
                candidates.append({
                    "sourceId": f"ash:{source.get('kind', 'ash')}:{source_id}",
                    "sourceKind": source.get("kind", "ash_count_record"),
                    "title": "灰烬明账债账",
                    "summary": f"{source.get('sourceLabel', '灰烬清点')}已经公开记账，营地可以据此补账、豁免或转成互市口信。",
                    "sourceLabel": source.get("label", "灰烬明账"),
                    "otherTribeId": "",
                    "otherTribeName": "",
                    "sourceChain": ["灰烬账谱", source.get("label", "灰烬明账")]
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
                self._default_camp_debt(tribe, debt, now)
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
                "sourceChain": candidate.get("sourceChain", []),
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
            self._public_camp_debt(debt)
            for debt in (tribe.get("camp_debts", []) or [])
            if isinstance(debt, dict) and debt.get("status") == "pending"
        ][-TRIBE_CAMP_DEBT_PENDING_LIMIT:]

    def _public_camp_debt_records(self, tribe: dict) -> list:
        return [
            self._public_camp_debt(debt)
            for debt in (tribe.get("camp_debts", []) or [])
            if isinstance(debt, dict) and debt.get("status") in {
                "settled", "forgiven", "market_note", "ritual_redeemed",
                "evidence_redeemed", "diplomatic_fulfilled", "stale", "defaulted"
            }
        ][-TRIBE_CAMP_DEBT_RECORD_LIMIT:]

    def _public_camp_debt(self, debt: dict) -> dict:
        public = dict(debt)
        public["sourceChain"] = [item for item in (debt.get("sourceChain", []) or []) if item]
        window_active = self._camp_debt_redeem_window_active(debt)
        available_keys = self._camp_debt_available_action_keys(debt) if debt.get("status") == "pending" else []
        public["redeemWindowActive"] = window_active
        public["redeemWindowLabel"] = "赎回窗口已开启：可用仪式、证据或外交履约偿还。" if window_active else "赎回窗口将在债账中后期出现。"
        public["defaultConsequence"] = debt.get("defaultConsequence") or "若到期仍未赎回，会改变部落性格倾向和后续传闻语气。"
        public["availableActionKeys"] = available_keys
        public["redeemOptions"] = [
            {
                "key": key,
                "label": action.get("label", key),
                "summary": action.get("summary", ""),
                "costParts": self._camp_debt_action_cost_parts(action),
                "rewardParts": self._camp_debt_action_reward_parts(action)
            }
            for key, action in TRIBE_CAMP_DEBT_ACTIONS.items()
            if debt.get("status") != "pending" or key in available_keys
        ]
        return public

    def _camp_debt_action_cost_parts(self, action: dict) -> list:
        parts = []
        if int(action.get("woodCost", 0) or 0):
            parts.append(f"木材-{int(action.get('woodCost', 0) or 0)}")
        if int(action.get("foodCost", 0) or 0):
            parts.append(f"食物-{int(action.get('foodCost', 0) or 0)}")
        return parts

    def _camp_debt_action_reward_parts(self, action: dict) -> list:
        labels = {
            "wood": "木材",
            "stone": "石块",
            "food": "食物",
            "renown": "声望",
            "discoveryProgress": "发现",
            "tradeReputation": "贸易信誉",
            "pressureRelief": "战争压力缓和",
            "relationDelta": "关系",
            "tradeTrustDelta": "信任"
        }
        parts = []
        for key, label in labels.items():
            value = int(action.get(key, 0) or 0)
            if not value:
                continue
            if key == "relationDelta":
                parts.append(f"{label}{value:+d}")
            elif key == "pressureRelief":
                parts.append(f"{label}+{value}")
            else:
                parts.append(f"{label}+{value}")
        return parts

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
            self._default_camp_debt(tribe, debt, datetime.now())
            await self._send_tribe_error(player_id, "这条营地债账已经逾期，部落口风已经受影响")
            await self.broadcast_tribe_state(tribe_id)
            return
        if action.get("windowOnly") and not self._camp_debt_redeem_window_active(debt):
            await self._send_tribe_error(player_id, "赎回窗口还没开启，先用补账、豁免或互市口信处理")
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
        if hasattr(self, "_apply_ash_ledger_distribution_bonus"):
            reward_parts.extend(self._apply_ash_ledger_distribution_bonus(tribe, debt.get("otherTribeId", ""), now_text))
        custom_key = action.get("customKey")
        custom_amount = int(action.get("customAmount", 0) or 0)
        if custom_key and custom_amount and hasattr(self, "_record_tribe_custom_choice"):
            custom_record = self._record_tribe_custom_choice(tribe, custom_key, action.get("label", "债账赎回"), player_id, custom_amount)
            if custom_record:
                reward_parts.append(f"{custom_record.get('label', '风俗')}倾向+{custom_amount}")
        observer_shift = self._apply_observer_outcome_shift(tribe, "camp_debt", debt.get("id")) if hasattr(self, "_apply_observer_outcome_shift") else None
        if observer_shift:
            reward_parts.extend(observer_shift.get("rewardParts", []))

        member = tribe.get("members", {}).get(player_id, {})
        debt["status"] = action.get("status", action_key)
        debt["actionKey"] = action_key
        debt["actionLabel"] = action.get("label", "处理债账")
        debt["redeemWindowUsed"] = bool(action.get("windowOnly"))
        debt["resolvedBy"] = player_id
        debt["resolvedByName"] = member.get("name", self._get_player_name(player_id))
        debt["resolvedAt"] = now_text
        debt["rewardParts"] = reward_parts
        debt["observerShift"] = observer_shift
        detail = f"{debt.get('resolvedByName', '成员')} 对“{debt.get('title', '营地债账')}”选择“{action.get('label', '处理')}”：{'、'.join(reward_parts) or '债账被公开记下'}。"
        if observer_shift:
            detail += f" {observer_shift.get('summary')}"
        self._add_tribe_history(tribe, "trade", "营地债账处理", detail, player_id, {"kind": "camp_debt", **debt})
        await self._publish_world_rumor(
            "trade",
            "营地债账处理",
            f"{tribe.get('name', '部落')} 把一笔{debt.get('sourceLabel', '公共消耗')}债账处理成了“{action.get('label', '公开记录')}”。",
            {"tribeId": tribe_id, "debtId": debt_id, "action": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
