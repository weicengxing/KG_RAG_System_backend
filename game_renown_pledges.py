from datetime import datetime

from game_config import *


class GameRenownPledgeMixin:
    def _active_renown_pledges(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        changed = False
        for pledge in tribe.get("renown_pledges", []) or []:
            if not isinstance(pledge, dict) or pledge.get("status") != "pending":
                continue
            try:
                if datetime.fromisoformat(pledge.get("activeUntil", "")) > now:
                    continue
            except (TypeError, ValueError):
                pass
            pledge["status"] = "failed"
            pledge["failedAt"] = now.isoformat()
            changed = True
            member = tribe.get("members", {}).get(pledge.get("issuerId"), {})
            if member:
                member["renown_stains"] = int(member.get("renown_stains", 0) or 0) + 1
            player = self.players.get(pledge.get("issuerId"))
            if player:
                player["personal_renown"] = max(
                    0,
                    int(player.get("personal_renown", 0) or 0) - TRIBE_RENOWN_PLEDGE_FAILURE_PENALTY
                )
        if changed:
            tribe["renown_pledges"] = list(tribe.get("renown_pledges", []) or [])[-TRIBE_RENOWN_PLEDGE_LIMIT:]
        return [
            pledge for pledge in (tribe.get("renown_pledges", []) or [])
            if isinstance(pledge, dict) and pledge.get("status") == "pending"
        ][-TRIBE_RENOWN_PLEDGE_LIMIT:]

    def _public_renown_pledge_records(self, tribe: dict) -> list:
        records = [
            pledge for pledge in (tribe.get("renown_pledges", []) or [])
            if isinstance(pledge, dict) and pledge.get("status") in {"fulfilled", "failed"}
        ]
        return records[-TRIBE_RENOWN_PLEDGE_RECENT_LIMIT:]

    def _apply_renown_pledge_rewards(self, tribe: dict, player_id: str, member: dict, option: dict) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood = int(option.get("wood", 0) or 0)
        if wood:
            storage["wood"] = int(storage.get("wood", 0) or 0) + wood
            reward_parts.append(f"木材+{wood}")
        food = int(option.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        renown = int(option.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        trade = int(option.get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        discovery = int(option.get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        contribution = int(option.get("contribution", 0) or 0)
        if contribution:
            member["contribution"] = int(member.get("contribution", 0) or 0) + contribution
            reward_parts.append(f"贡献+{contribution}")
        personal = int(option.get("personalRenown", 0) or 0)
        if personal:
            player = self.players.setdefault(player_id, {})
            player["personal_renown"] = int(player.get("personal_renown", 0) or 0) + personal
            reward_parts.append(f"个人声望+{personal}")
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

    async def start_renown_pledge(self, player_id: str, pledge_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        option = TRIBE_RENOWN_PLEDGE_OPTIONS.get(pledge_key)
        if not option:
            await self._send_tribe_error(player_id, "未知声望押注方向")
            return
        member = tribe.get("members", {}).get(player_id)
        if not member:
            await self._send_tribe_error(player_id, "你还不是该部落成员")
            return
        player = self.players.setdefault(player_id, {})
        personal_renown = int(player.get("personal_renown", 0) or 0)
        can_pledge = member.get("role") in ("leader", "elder") or personal_renown >= TRIBE_RENOWN_PLEDGE_MIN_PERSONAL_RENOWN
        if not can_pledge:
            await self._send_tribe_error(player_id, f"个人声望至少需要 {TRIBE_RENOWN_PLEDGE_MIN_PERSONAL_RENOWN}，或由首领/长老发起")
            return
        stake = int(TRIBE_RENOWN_PLEDGE_STAKE)
        if personal_renown < stake:
            await self._send_tribe_error(player_id, f"押注需要个人声望 {stake}")
            return
        pending = [
            pledge for pledge in self._active_renown_pledges(tribe)
            if pledge.get("issuerId") == player_id
        ]
        if pending:
            await self._send_tribe_error(player_id, "你已经有一个未兑现的声望押注")
            return
        now = datetime.now()
        player["personal_renown"] = personal_renown - stake
        pledge = {
            "id": f"renown_pledge_{tribe_id}_{int(now.timestamp() * 1000)}",
            "status": "pending",
            "key": pledge_key,
            "label": option.get("label", "声望押注"),
            "summary": option.get("summary", ""),
            "issuerId": player_id,
            "issuerName": member.get("name", "成员"),
            "stake": stake,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_RENOWN_PLEDGE_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("renown_pledges", []).append(pledge)
        tribe["renown_pledges"] = tribe["renown_pledges"][-TRIBE_RENOWN_PLEDGE_LIMIT:]
        detail = f"{member.get('name', '成员')} 把个人声望押在“{pledge['label']}”上，承诺在火边兑现。"
        self._add_tribe_history(tribe, "governance", "声望押注", detail, player_id, {"kind": "renown_pledge", "pledge": pledge})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.send_personal_conflict_status(player_id)

    async def fulfill_renown_pledge(self, player_id: str, pledge_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        pledge = next((
            item for item in self._active_renown_pledges(tribe)
            if isinstance(item, dict) and item.get("id") == pledge_id
        ), None)
        if not pledge:
            await self._send_tribe_error(player_id, "没有找到可兑现的声望押注")
            return
        if pledge.get("issuerId") != player_id:
            await self._send_tribe_error(player_id, "只有发起押注的人可以兑现")
            return
        option = TRIBE_RENOWN_PLEDGE_OPTIONS.get(pledge.get("key"), {})
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_renown_pledge_rewards(tribe, player_id, member, option)
        now_text = datetime.now().isoformat()
        pledge["status"] = "fulfilled"
        pledge["fulfilledAt"] = now_text
        pledge["rewardParts"] = reward_parts
        detail = f"{member.get('name', '成员')} 兑现“{pledge.get('label', '声望押注')}”：{'、'.join(reward_parts) or '个人名声被营火记住'}。"
        self._add_tribe_history(tribe, "governance", "兑现声望押注", detail, player_id, {"kind": "renown_pledge_fulfilled", "pledgeId": pledge_id, "rewardParts": reward_parts})
        await self._publish_world_rumor(
            "governance",
            "声望押注",
            f"{tribe.get('name', '部落')} 的 {member.get('name', '成员')} 兑现了公开押下的名声。",
            {"tribeId": tribe_id, "pledgeId": pledge_id, "pledgeKey": pledge.get("key")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.send_personal_conflict_status(player_id)
