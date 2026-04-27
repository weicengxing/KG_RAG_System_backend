from datetime import datetime

from game_config import *


class GamePersonalTokenMixin:
    def _active_personal_tokens(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        tokens = []
        changed = False
        for token in tribe.get("personal_tokens", []) or []:
            if not isinstance(token, dict):
                continue
            if token.get("status") == "pending":
                try:
                    if datetime.fromisoformat(token.get("activeUntil", "")) <= now:
                        token["status"] = "overdue"
                        token["overdueAt"] = now.isoformat()
                        self._append_personal_debt_task(tribe, token, now.isoformat(), "overdue")
                        changed = True
                except (TypeError, ValueError):
                    token["status"] = "overdue"
                    token["overdueAt"] = now.isoformat()
                    self._append_personal_debt_task(tribe, token, now.isoformat(), "overdue")
                    changed = True
            tokens.append(token)
        if changed or len(tokens) != len(tribe.get("personal_tokens", []) or []):
            tribe["personal_tokens"] = tokens[-TRIBE_PERSONAL_TOKEN_LIMIT:]
        return [
            token for token in tokens
            if token.get("status") in {"pending", "overdue"}
        ][-TRIBE_PERSONAL_TOKEN_LIMIT:]

    def _public_personal_token_records(self, tribe: dict) -> list:
        records = [
            token for token in (tribe.get("personal_tokens", []) or [])
            if isinstance(token, dict) and token.get("status") in {"redeemed", "debt_settled", "cancelled"}
        ]
        return records[-TRIBE_PERSONAL_TOKEN_RECENT_LIMIT:]

    def _public_personal_debt_tasks(self, tribe: dict) -> list:
        return [
            task for task in (tribe.get("personal_debt_tasks", []) or [])
            if isinstance(task, dict) and task.get("status") == "pending"
        ][-TRIBE_PERSONAL_DEBT_LIMIT:]

    def _personal_token_targets(self, tribe: dict) -> list:
        targets = [{"id": "tribe", "name": tribe.get("name", "本部落"), "summary": "把信物交给公共营火，由部落见证。"}]
        for member in (tribe.get("members", {}) or {}).values():
            if not isinstance(member, dict):
                continue
            targets.append({
                "id": member.get("id"),
                "name": member.get("name", "成员"),
                "summary": f"信任标记 {int(member.get('trust_marks', 0) or 0)}"
            })
        return targets

    def _append_personal_debt_task(self, tribe: dict, token: dict, now_text: str, reason: str):
        if not tribe or not token:
            return None
        task_id = f"personal_debt_{token.get('id')}"
        existing = next((
            item for item in (tribe.get("personal_debt_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") == task_id and item.get("status") == "pending"
        ), None)
        if existing:
            return existing
        task = {
            "id": task_id,
            "status": "pending",
            "kind": "personal_debt",
            "reason": reason,
            "title": "人情债补偿",
            "summary": f"{token.get('issuerName', '成员')} 的“{token.get('label', '信物')}”没有按时兑现，部落可以要求补偿或公开解释。",
            "tokenId": token.get("id"),
            "issuerId": token.get("issuerId"),
            "issuerName": token.get("issuerName", "成员"),
            "targetId": token.get("targetId"),
            "targetName": token.get("targetName", "本部落"),
            "woodCost": TRIBE_PERSONAL_DEBT_WOOD_COST,
            "foodCost": TRIBE_PERSONAL_DEBT_FOOD_COST,
            "renownReward": 1,
            "trustReward": 1,
            "createdAt": now_text
        }
        tribe.setdefault("personal_debt_tasks", []).append(task)
        tribe["personal_debt_tasks"] = tribe["personal_debt_tasks"][-TRIBE_PERSONAL_DEBT_LIMIT:]
        return task

    def _personal_token_by_id(self, tribe: dict, token_id: str) -> dict | None:
        return next((
            token for token in (tribe.get("personal_tokens", []) or [])
            if isinstance(token, dict) and token.get("id") == token_id
        ), None)

    def _apply_personal_token_rewards(self, tribe: dict, member: dict, token: dict, option: dict) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood = int(option.get("wood", 0) or 0)
        if wood:
            storage["wood"] = int(storage.get("wood", 0) or 0) + wood
            reward_parts.append(f"木材+{wood}")
        renown = int(option.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        discovery = int(option.get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        contribution = int(option.get("contribution", 0) or 0)
        if contribution:
            member["contribution"] = int(member.get("contribution", 0) or 0) + contribution
            reward_parts.append(f"贡献+{contribution}")
        trust = int(token.get("trustReward", TRIBE_PERSONAL_TOKEN_TRUST_REWARD) or 0)
        if trust:
            member["trust_marks"] = int(member.get("trust_marks", 0) or 0) + trust
            reward_parts.append(f"信任标记+{trust}")
        pressure_relief = int(option.get("warPressureRelief", 0) or 0)
        if pressure_relief:
            relieved = 0
            for relation in (tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                if before <= 0:
                    continue
                relation["warPressure"] = max(0, before - pressure_relief)
                relation["canDeclareWar"] = False
                relieved += before - int(relation.get("warPressure", 0) or 0)
            if relieved:
                reward_parts.append(f"战争压力-{relieved}")
        return reward_parts

    async def create_personal_token(self, player_id: str, token_key: str, target_id: str = "tribe"):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        option = TRIBE_PERSONAL_TOKEN_OPTIONS.get(token_key)
        if not option:
            await self._send_tribe_error(player_id, "未知信物类型")
            return
        member = tribe.get("members", {}).get(player_id)
        if not member:
            await self._send_tribe_error(player_id, "你还不是该部落成员")
            return
        pending_count = len([
            token for token in self._active_personal_tokens(tribe)
            if token.get("issuerId") == player_id and token.get("status") == "pending"
        ])
        if pending_count >= 2:
            await self._send_tribe_error(player_id, "你已经有太多未兑现信物")
            return
        target_name = tribe.get("name", "本部落")
        if target_id and target_id != "tribe":
            target_member = tribe.get("members", {}).get(target_id)
            if not target_member:
                await self._send_tribe_error(player_id, "信物对象必须是本部落成员")
                return
            target_name = target_member.get("name", "成员")
        now = datetime.now()
        token = {
            "id": f"personal_token_{tribe_id}_{int(now.timestamp() * 1000)}_{len(tribe.get('personal_tokens', []) or [])}",
            "status": "pending",
            "key": token_key,
            "label": option.get("label", "个人信物"),
            "summary": option.get("summary", ""),
            "issuerId": player_id,
            "issuerName": member.get("name", "成员"),
            "targetId": target_id or "tribe",
            "targetName": target_name,
            "trustReward": TRIBE_PERSONAL_TOKEN_TRUST_REWARD,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_PERSONAL_TOKEN_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("personal_tokens", []).append(token)
        tribe["personal_tokens"] = tribe["personal_tokens"][-TRIBE_PERSONAL_TOKEN_LIMIT:]
        detail = f"{member.get('name', '成员')} 交出“{token['label']}”给 {target_name}，承诺在火边兑现。"
        self._add_tribe_history(tribe, "governance", "个人信物", detail, player_id, {"kind": "personal_token", "token": token})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def redeem_personal_token(self, player_id: str, token_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        token = self._personal_token_by_id(tribe, token_id)
        if not token or token.get("status") not in {"pending", "overdue"}:
            await self._send_tribe_error(player_id, "没有找到可兑现的信物")
            return
        if token.get("issuerId") != player_id:
            await self._send_tribe_error(player_id, "只有立下信物的人可以兑现")
            return
        member = tribe.get("members", {}).get(player_id, {})
        option = TRIBE_PERSONAL_TOKEN_OPTIONS.get(token.get("key"), {})
        reward_parts = self._apply_personal_token_rewards(tribe, member, token, option)
        now_text = datetime.now().isoformat()
        token["status"] = "redeemed"
        token["redeemedAt"] = now_text
        token["rewardParts"] = reward_parts
        detail = f"{member.get('name', '成员')} 兑现“{token.get('label', '信物')}”：{'、'.join(reward_parts) or '部落信任回升'}。"
        self._add_tribe_history(tribe, "governance", "兑现信物", detail, player_id, {"kind": "personal_token_redeemed", "tokenId": token_id, "rewardParts": reward_parts})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def call_personal_debt(self, player_id: str, token_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        token = self._personal_token_by_id(tribe, token_id)
        if not token or token.get("status") not in {"pending", "overdue"}:
            await self._send_tribe_error(player_id, "没有找到可追记的人情信物")
            return
        member = tribe.get("members", {}).get(player_id, {})
        can_call = member.get("role") in ("leader", "elder") or token.get("targetId") == player_id
        if not can_call:
            await self._send_tribe_error(player_id, "只有首领、长老或信物对象可以追记人情债")
            return
        now_text = datetime.now().isoformat()
        token["status"] = "overdue"
        token["debtCalledAt"] = now_text
        issuer = tribe.get("members", {}).get(token.get("issuerId"), {})
        if issuer:
            issuer["trust_marks"] = max(0, int(issuer.get("trust_marks", 0) or 0) - TRIBE_PERSONAL_TOKEN_DEBT_TRUST_PENALTY)
        debt = self._append_personal_debt_task(tribe, token, now_text, "called")
        detail = f"{member.get('name', '成员')} 把 {token.get('issuerName', '成员')} 的“{token.get('label', '信物')}”追记为人情债，等待补偿。"
        self._add_tribe_history(tribe, "governance", "人情债", detail, player_id, {"kind": "personal_debt", "tokenId": token_id, "debtTask": debt})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def settle_personal_debt(self, player_id: str, task_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((
            item for item in (tribe.get("personal_debt_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") == task_id and item.get("status") == "pending"
        ), None)
        if not task:
            await self._send_tribe_error(player_id, "没有找到可补偿的人情债")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if player_id != task.get("issuerId") and member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有欠下信物的人或管理者可以处理这笔人情债")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(task.get("woodCost", TRIBE_PERSONAL_DEBT_WOOD_COST) or 0)
        food_cost = int(task.get("foodCost", TRIBE_PERSONAL_DEBT_FOOD_COST) or 0)
        if int(storage.get("wood", 0) or 0) < wood_cost or int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, "补偿人情债需要公共木材和食物")
            return
        storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        renown = int(task.get("renownReward", 1) or 0)
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
        issuer = tribe.get("members", {}).get(task.get("issuerId"), {})
        if issuer:
            issuer["trust_marks"] = int(issuer.get("trust_marks", 0) or 0) + int(task.get("trustReward", 1) or 0)
        now_text = datetime.now().isoformat()
        task["status"] = "completed"
        task["completedBy"] = player_id
        task["completedByName"] = member.get("name", "成员")
        task["completedAt"] = now_text
        token = self._personal_token_by_id(tribe, task.get("tokenId"))
        if token:
            token["status"] = "debt_settled"
            token["settledAt"] = now_text
        detail = f"{member.get('name', '成员')} 补偿“{task.get('title', '人情债')}”，木材-{wood_cost}、食物-{food_cost}、声望+{renown}。"
        self._add_tribe_history(tribe, "governance", "人情债补偿", detail, player_id, {"kind": "personal_debt_settled", "taskId": task_id})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
