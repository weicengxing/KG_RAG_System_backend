from datetime import datetime


ORAL_CONTRACT_ACTIVE_MINUTES = 30
ORAL_CONTRACT_LIMIT = 8
ORAL_CONTRACT_PENDING_LIMIT = 4
ORAL_CONTRACT_RECORD_LIMIT = 8
ORAL_CONTRACT_REMEDY_LIMIT = 6
ORAL_CONTRACT_OPTIONS = {
    "escort": {
        "label": "护送某人",
        "summary": "公开说好护送一名成员、来客或新手走过危险路段，兑现后留下可被记住的守护名声。",
        "targetLabel": "护送对象",
        "reward": {"renown": 1, "tradeReputation": 1},
        "personalRenown": 2,
        "contribution": 1,
        "remedyLabel": "补走护送路",
        "remedySummary": "把没护完的那段路补走一遍，向营火说明失约原因。"
    },
    "debt": {
        "label": "补齐某债",
        "summary": "把一笔公共债、旧人情或分配缺口说到明处，兑现后提高守誓声望和贸易信用。",
        "targetLabel": "债账对象",
        "reward": {"renown": 1, "tradeReputation": 1, "food": 1},
        "personalRenown": 2,
        "contribution": 2,
        "remedyLabel": "补上欠口",
        "remedySummary": "交出一点公共补给或劳作，把没兑现的债口补成可被原谅的记录。"
    },
    "route": {
        "label": "守住某路",
        "summary": "承诺守住一段边界、洞口或归路，兑现后推进发现并轻微缓和战争压力。",
        "targetLabel": "守路对象",
        "reward": {"renown": 1, "discoveryProgress": 1},
        "warPressureRelief": 1,
        "personalRenown": 2,
        "contribution": 1,
        "remedyLabel": "补守旧路",
        "remedySummary": "沿失约的路再巡一次，把污点补成守路记录。"
    }
}


class GameOralContractMixin:
    def _public_oral_contract_options(self, tribe: dict) -> dict:
        return ORAL_CONTRACT_OPTIONS

    def _public_oral_contract_config(self) -> dict:
        return {
            "activeMinutes": ORAL_CONTRACT_ACTIVE_MINUTES,
            "pendingLimit": ORAL_CONTRACT_PENDING_LIMIT
        }

    def _active_oral_contracts(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        changed = False
        for contract in tribe.get("oral_contracts", []) or []:
            if not isinstance(contract, dict) or contract.get("status") != "pending":
                continue
            try:
                expired = datetime.fromisoformat(contract.get("activeUntil", "")).timestamp() <= now.timestamp()
            except (TypeError, ValueError):
                expired = True
            if expired:
                self._fail_oral_contract_record(tribe, contract, now, "错过时限")
                changed = True
        if changed:
            tribe["oral_contracts"] = list(tribe.get("oral_contracts", []) or [])[-ORAL_CONTRACT_LIMIT:]
        return [
            contract for contract in (tribe.get("oral_contracts", []) or [])
            if isinstance(contract, dict) and contract.get("status") == "pending"
        ][-ORAL_CONTRACT_PENDING_LIMIT:]

    def _public_oral_contract_records(self, tribe: dict) -> list:
        return [
            contract for contract in (tribe.get("oral_contracts", []) or [])
            if isinstance(contract, dict) and contract.get("status") in {"fulfilled", "failed", "remedied"}
        ][-ORAL_CONTRACT_RECORD_LIMIT:]

    def _public_oral_contract_remedies(self, tribe: dict) -> list:
        return [
            remedy for remedy in (tribe.get("oral_contract_remedies", []) or [])
            if isinstance(remedy, dict) and remedy.get("status") == "pending"
        ][-ORAL_CONTRACT_REMEDY_LIMIT:]

    def _oral_contract_target_name(self, tribe: dict, target_id: str, fallback: str = "") -> str:
        if target_id and target_id in (tribe.get("members", {}) or {}):
            return tribe["members"][target_id].get("name", fallback or "成员")
        return fallback or "营火旁的人"

    def _oral_contract_reward_parts(self, tribe: dict, player_id: str, member: dict, option: dict) -> list:
        labels = {"wood": "木材", "stone": "石块", "food": "食物", "renown": "声望", "discoveryProgress": "发现", "tradeReputation": "贸易信誉"}
        parts = self._apply_tribe_reward(tribe, option.get("reward", {}), labels=labels) if hasattr(self, "_apply_tribe_reward") else []
        contribution = int(option.get("contribution", 0) or 0)
        if contribution and member is not None:
            member["contribution"] = int(member.get("contribution", 0) or 0) + contribution
            parts.append(f"贡献+{contribution}")
        personal = int(option.get("personalRenown", 0) or 0)
        if personal:
            player = self.players.setdefault(player_id, {})
            player["personal_renown"] = int(player.get("personal_renown", 0) or 0) + personal
            parts.append(f"个人声望+{personal}")
        pressure_relief = int(option.get("warPressureRelief", 0) or 0)
        if pressure_relief:
            relieved = 0
            for relation in (tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                after = max(0, before - pressure_relief)
                relation["warPressure"] = after
                relation["canDeclareWar"] = False
                relieved += before - after
            if relieved:
                parts.append(f"战争压力-{relieved}")
        return parts

    def _fail_oral_contract_record(self, tribe: dict, contract: dict, now: datetime, reason: str):
        if contract.get("failureRecorded"):
            return None
        option = ORAL_CONTRACT_OPTIONS.get(contract.get("key"), {})
        contract["status"] = "failed"
        contract["failedAt"] = now.isoformat()
        contract["failureReason"] = reason
        contract["failureRecorded"] = True
        member = tribe.get("members", {}).get(contract.get("issuerId"), {})
        if member:
            member["renown_stains"] = int(member.get("renown_stains", 0) or 0) + 1
        remedy = {
            "id": f"oral_contract_remedy_{contract.get('id')}",
            "status": "pending",
            "contractId": contract.get("id"),
            "contractLabel": contract.get("label", option.get("label", "口头契约")),
            "memberId": contract.get("issuerId"),
            "memberName": contract.get("issuerName", "成员"),
            "label": option.get("remedyLabel", "补救契约"),
            "summary": option.get("remedySummary", "把没兑现的口头契约补成公开行动。"),
            "createdAt": now.isoformat()
        }
        tribe.setdefault("oral_contract_remedies", []).append(remedy)
        tribe["oral_contract_remedies"] = tribe["oral_contract_remedies"][-ORAL_CONTRACT_REMEDY_LIMIT:]
        detail = f"{contract.get('issuerName', '成员')} 的“{contract.get('label', '口头契约')}”失约，留下“{remedy['label']}”作为可补救污点。"
        if hasattr(self, "_add_tribe_history"):
            self._add_tribe_history(tribe, "governance", "口头契约失约", detail, contract.get("issuerId"), {"kind": "oral_contract_failed", "contract": contract, "remedy": remedy})
        return remedy

    async def start_oral_contract(self, player_id: str, contract_key: str, target_id: str = ""):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        option = ORAL_CONTRACT_OPTIONS.get(contract_key)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not option:
            await self._send_tribe_error(player_id, "未知口头契约")
            return
        member = tribe.get("members", {}).get(player_id)
        if not member:
            await self._send_tribe_error(player_id, "你还不是该部落成员")
            return
        active = self._active_oral_contracts(tribe)
        if any(contract.get("issuerId") == player_id for contract in active):
            await self._send_tribe_error(player_id, "你已经有一条未兑现的口头契约")
            return
        if len(active) >= ORAL_CONTRACT_PENDING_LIMIT:
            await self._send_tribe_error(player_id, "营火旁未兑现的口头契约已经太多")
            return
        now = datetime.now()
        target_name = self._oral_contract_target_name(tribe, target_id, option.get("targetLabel", "约定对象"))
        contract = {
            "id": f"oral_contract_{tribe_id}_{int(now.timestamp() * 1000)}",
            "status": "pending",
            "key": contract_key,
            "label": option.get("label", "口头契约"),
            "summary": option.get("summary", ""),
            "issuerId": player_id,
            "issuerName": member.get("name", "成员"),
            "targetId": target_id or "",
            "targetName": target_name,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + ORAL_CONTRACT_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("oral_contracts", []).append(contract)
        tribe["oral_contracts"] = tribe["oral_contracts"][-ORAL_CONTRACT_LIMIT:]
        detail = f"{contract['issuerName']} 在营火旁立下“{contract['label']}”，指向 {target_name}：{contract['summary']}"
        self._add_tribe_history(tribe, "governance", "立下口头契约", detail, player_id, {"kind": "oral_contract", "contract": contract})
        await self._publish_world_rumor("governance", "口头契约", f"{tribe.get('name', '部落')} 的 {contract['issuerName']} 公开说好要“{contract['label']}”。", {"tribeId": tribe_id, "contractId": contract["id"], "contractKey": contract_key})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def fulfill_oral_contract(self, player_id: str, contract_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        contract = next((item for item in self._active_oral_contracts(tribe) if item.get("id") == contract_id), None)
        if not contract:
            await self._send_tribe_error(player_id, "没有找到可兑现的口头契约")
            return
        if contract.get("issuerId") != player_id:
            await self._send_tribe_error(player_id, "只有立约者可以兑现这条口头契约")
            return
        option = ORAL_CONTRACT_OPTIONS.get(contract.get("key"), {})
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._oral_contract_reward_parts(tribe, player_id, member, option)
        contract["status"] = "fulfilled"
        contract["fulfilledAt"] = datetime.now().isoformat()
        contract["rewardParts"] = reward_parts
        detail = f"{contract.get('issuerName', '成员')} 兑现“{contract.get('label', '口头契约')}”：{'、'.join(reward_parts) or '营火记住了这句话'}。"
        self._add_tribe_history(tribe, "governance", "兑现口头契约", detail, player_id, {"kind": "oral_contract_fulfilled", "contract": contract})
        await self._publish_world_rumor("governance", "口头契约兑现", f"{tribe.get('name', '部落')} 的 {contract.get('issuerName', '成员')} 把一句口头契约兑现成了行动。", {"tribeId": tribe_id, "contractId": contract_id})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.send_personal_conflict_status(player_id)

    async def fail_oral_contract(self, player_id: str, contract_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        contract = next((item for item in self._active_oral_contracts(tribe) if item.get("id") == contract_id), None)
        if not contract:
            await self._send_tribe_error(player_id, "没有找到可公开失约的口头契约")
            return
        if contract.get("issuerId") != player_id:
            await self._send_tribe_error(player_id, "只有立约者可以公开失约")
            return
        remedy = self._fail_oral_contract_record(tribe, contract, datetime.now(), "主动公开失约")
        await self._notify_tribe(tribe_id, f"{contract.get('issuerName', '成员')} 公开承认“{contract.get('label', '口头契约')}”暂时失约，留下 {remedy.get('label', '补救契约') if remedy else '补救契约'}。")
        await self.broadcast_tribe_state(tribe_id)
        await self.send_personal_conflict_status(player_id)

    async def remedy_oral_contract(self, player_id: str, remedy_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        remedy = next((item for item in self._public_oral_contract_remedies(tribe) if item.get("id") == remedy_id), None)
        if not remedy:
            await self._send_tribe_error(player_id, "没有找到可补救的口头契约")
            return
        if remedy.get("memberId") != player_id:
            await self._send_tribe_error(player_id, "只有失约者可以补救自己的契约污点")
            return
        member = tribe.get("members", {}).get(player_id, {})
        member["renown_stains"] = max(0, int(member.get("renown_stains", 0) or 0) - 1)
        member["contribution"] = int(member.get("contribution", 0) or 0) + 1
        player = self.players.setdefault(player_id, {})
        player["personal_renown"] = int(player.get("personal_renown", 0) or 0) + 1
        remedy["status"] = "completed"
        remedy["completedAt"] = datetime.now().isoformat()
        remedy["completedBy"] = player_id
        remedy["rewardParts"] = ["污点-1", "贡献+1", "个人声望+1"]
        for contract in tribe.get("oral_contracts", []) or []:
            if isinstance(contract, dict) and contract.get("id") == remedy.get("contractId"):
                contract["status"] = "remedied"
                contract["remediedAt"] = remedy["completedAt"]
                contract["remedyRewardParts"] = remedy["rewardParts"]
        detail = f"{member.get('name', '成员')} 完成“{remedy.get('label', '补救契约')}”，把失约污点补成公开记录：{'、'.join(remedy['rewardParts'])}。"
        self._add_tribe_history(tribe, "governance", "补救口头契约", detail, player_id, {"kind": "oral_contract_remedy", "remedy": remedy})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.send_personal_conflict_status(player_id)

    async def handle_oral_contract_message(self, player_id: str, message: dict):
        action = message.get("action", "")
        if action == "start":
            await self.start_oral_contract(player_id, message.get("contractKey", ""), message.get("targetId", ""))
        elif action == "fulfill":
            await self.fulfill_oral_contract(player_id, message.get("contractId", ""))
        elif action == "fail":
            await self.fail_oral_contract(player_id, message.get("contractId", ""))
        elif action == "remedy":
            await self.remedy_oral_contract(player_id, message.get("remedyId", ""))
        else:
            await self._send_tribe_error(player_id, "未知口头契约动作")
