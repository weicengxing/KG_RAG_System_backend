from datetime import datetime

from game_config import *


class GameGuestStayMixin:
    def _active_guest_stays(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        changed = False
        for stay in tribe.get("guest_stays", []) or []:
            if not isinstance(stay, dict):
                continue
            active_until = stay.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        stay["status"] = "completed"
                        changed = True
                except (TypeError, ValueError):
                    stay["status"] = "completed"
                    changed = True
            active.append(stay)
        if changed or len(active) != len(tribe.get("guest_stays", []) or []):
            tribe["guest_stays"] = active[-TRIBE_GUEST_STAY_RECORD_LIMIT:]
        return [
            stay for stay in active
            if stay.get("status") in {"active", "completed"}
        ][-TRIBE_GUEST_STAY_RECORD_LIMIT:]

    def _guest_stay_targets(self, tribe: dict) -> list:
        tribe_id = tribe.get("id")
        targets = []
        for other in self.tribes.values():
            other_id = other.get("id")
            if not other_id or other_id == tribe_id:
                continue
            relation = (tribe.get("boundary_relations", {}) or {}).get(other_id, {}) or {}
            score = int(relation.get("score", 0) or 0)
            trust = int(relation.get("tradeTrust", 0) or 0)
            market_pact = bool(self._market_pact_between(tribe, other_id))
            if (
                score < TRIBE_GUEST_STAY_MIN_RELATION
                and trust < TRIBE_GUEST_STAY_MIN_TRADE_TRUST
                and not market_pact
            ):
                continue
            targets.append({
                "id": other_id,
                "name": other.get("name", "邻近部落"),
                "relationScore": score,
                "tradeTrust": trust,
                "marketPact": market_pact,
                "tribePersonality": self._public_tribe_personality(other) if hasattr(self, "_public_tribe_personality") else None,
                "summary": f"关系 {score:+d} / 信任 +{trust}" + (" / 互市约定" if market_pact else "")
            })
        return targets

    def _wanderer_guest_stay_targets(self) -> list:
        targets = []
        for tribe in self.tribes.values():
            tribe_id = tribe.get("id")
            if not tribe_id:
                continue
            targets.append({
                "id": tribe_id,
                "name": tribe.get("name", "部落营地"),
                "tribePersonality": self._public_tribe_personality(tribe) if hasattr(self, "_public_tribe_personality") else None,
                "summary": f"{len(tribe.get('members', {}) or {})} 人 / 声望 {int(tribe.get('renown', 0) or 0)}"
            })
        return targets[:TRIBE_GUEST_STAY_WANDERER_TARGET_LIMIT]

    def _apply_guest_stay_relation(self, source_tribe: dict | None, host_tribe: dict, action: dict, now_text: str):
        if not source_tribe:
            return
        relation_delta = int(action.get("relationDelta", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        for source, target in ((source_tribe, host_tribe), (host_tribe, source_tribe)):
            relation = source.setdefault("boundary_relations", {}).setdefault(target.get("id"), {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            relation["lastAction"] = "guest_stay"
            relation["lastActionAt"] = now_text

    def _apply_guest_stay_reward(self, host_tribe: dict, source_member: dict | None, action: dict) -> list:
        reward_parts = []
        storage = host_tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for resource, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(action.get(resource, 0) or 0)
            if amount:
                storage[resource] = int(storage.get(resource, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = int(action.get("food", 0) or 0)
        if food:
            host_tribe["food"] = int(host_tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        renown = int(action.get("renown", 0) or 0)
        if renown:
            host_tribe["renown"] = int(host_tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        discovery = int(action.get("discoveryProgress", 0) or 0)
        if discovery:
            host_tribe["discovery_progress"] = int(host_tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        trade = int(action.get("tradeReputation", 0) or 0)
        if trade:
            host_tribe["trade_reputation"] = int(host_tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        pressure_relief = int(action.get("pressureRelief", 0) or 0)
        if pressure_relief:
            relieved = 0
            for relation in (host_tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                if before <= 0:
                    continue
                relation["warPressure"] = max(0, before - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                relieved += before - int(relation.get("warPressure", 0) or 0)
            if relieved:
                reward_parts.append(f"战争压力-{relieved}")
        contribution = int(action.get("contribution", 0) or 0)
        if source_member and contribution:
            source_member["contribution"] = int(source_member.get("contribution", 0) or 0) + contribution
            reward_parts.append(f"贡献+{contribution}")
        return reward_parts

    def _record_guest_stay(self, tribe: dict, record: dict):
        tribe.setdefault("guest_stays", []).append(record)
        tribe["guest_stays"] = tribe["guest_stays"][-TRIBE_GUEST_STAY_RECORD_LIMIT:]

    async def start_guest_stay(self, player_id: str, target_tribe_id: str, action_key: str):
        host_tribe = self.tribes.get(target_tribe_id)
        if not host_tribe:
            await self._send_tribe_error(player_id, "找不到可客居的部落")
            return
        action = TRIBE_GUEST_STAY_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知客居行动")
            return

        source_tribe_id = self.player_tribes.get(player_id)
        source_tribe = self.tribes.get(source_tribe_id) if source_tribe_id else None
        if source_tribe_id == target_tribe_id:
            await self._send_tribe_error(player_id, "客居需要前往另一个营地")
            return
        if source_tribe and not any(target.get("id") == target_tribe_id for target in self._guest_stay_targets(source_tribe)):
            await self._send_tribe_error(player_id, "需要先建立友好关系、贸易信任或互市约定")
            return

        player = self.players.get(player_id, {})
        source_member = (source_tribe.get("members", {}) or {}).get(player_id) if source_tribe else None
        guest_name = (source_member or player).get("name", self._get_player_name(player_id))
        source_name = source_tribe.get("name", "无部落旅人") if source_tribe else "无部落旅人"
        now_text = datetime.now().isoformat()
        active_until = datetime.fromtimestamp(
            datetime.fromisoformat(now_text).timestamp() + TRIBE_GUEST_STAY_ACTIVE_MINUTES * 60
        ).isoformat()

        reward_parts = self._apply_guest_stay_reward(host_tribe, source_member, action)
        personality_parts = []
        if hasattr(self, "_apply_personality_culture_reward"):
            personality_parts = self._apply_personality_culture_reward(host_tribe, "guest", source_tribe_id or "")
            reward_parts.extend(personality_parts)
        self._apply_guest_stay_relation(source_tribe, host_tribe, action, now_text)
        if source_tribe and int(action.get("guestRenown", 0) or 0):
            source_tribe["renown"] = int(source_tribe.get("renown", 0) or 0) + int(action.get("guestRenown", 0) or 0)
            reward_parts.append(f"本部声望+{int(action.get('guestRenown', 0) or 0)}")

        base_record = {
            "id": f"guest_stay_{player_id}_{target_tribe_id}_{int(datetime.fromisoformat(now_text).timestamp() * 1000)}",
            "status": "active",
            "actionKey": action_key,
            "label": action.get("label", "短期客居"),
            "summary": action.get("summary", ""),
            "guestId": player_id,
            "guestName": guest_name,
            "sourceTribeId": source_tribe_id,
            "sourceTribeName": source_name,
            "hostTribeId": target_tribe_id,
            "hostTribeName": host_tribe.get("name", "部落营地"),
            "rewardParts": reward_parts,
            "personalityHint": "、".join(personality_parts),
            "activeUntil": active_until,
            "createdAt": now_text
        }
        host_record = {**base_record, "direction": "incoming"}
        self._record_guest_stay(host_tribe, host_record)
        if source_tribe:
            self._record_guest_stay(source_tribe, {**base_record, "direction": "outgoing"})

        detail = f"{guest_name} 以{source_name}身份在 {host_tribe.get('name', '部落营地')} 短期客居，选择“{action.get('label', '帮忙')}”：{'、'.join(reward_parts) or '留下了一段共同故事'}。"
        self._add_tribe_history(host_tribe, "trade", "短期客居", detail, player_id, {"kind": "guest_stay", **host_record})
        if source_tribe:
            self._add_tribe_history(source_tribe, "trade", "外出客居", detail, player_id, {"kind": "guest_stay", **base_record})
        await self._publish_world_rumor(
            "trade",
            "短期客居",
            f"{guest_name} 在 {host_tribe.get('name', '部落营地')} 客居帮忙，两个营地之间多了一段可被讲述的来往。",
            {"tribeId": source_tribe_id, "targetTribeId": target_tribe_id, "action": action_key}
        )
        await self._notify_tribe(target_tribe_id, detail)
        if source_tribe_id:
            await self._notify_tribe(source_tribe_id, detail)
        await self.broadcast_tribe_state(target_tribe_id)
        if source_tribe_id:
            await self.broadcast_tribe_state(source_tribe_id)
        elif player_id in self.active_connections:
            await self.send_personal_message(player_id, self.get_player_tribe_state(player_id))
