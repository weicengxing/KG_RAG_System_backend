from datetime import datetime
import random

from game_config import *


class GameSacredFireMixin:
    def _active_sacred_fire_relay(self, tribe: dict) -> dict | None:
        return self._active_tribe_item(
            tribe,
            "sacred_fire_relay",
            status="active",
            mark_expired_status="expired"
        )

    def _public_sacred_fire_relay(self, tribe: dict) -> dict | None:
        relay = self._active_sacred_fire_relay(tribe)
        if not relay:
            return None
        carriers = list(relay.get("carriers", []) or [])
        events = list(relay.get("routeEvents", []) or [])
        return {
            "id": relay.get("id"),
            "destinationKey": relay.get("destinationKey"),
            "destinationLabel": relay.get("destinationLabel"),
            "summary": relay.get("summary"),
            "carriers": carriers[-6:],
            "carrierCount": len(carriers),
            "routeEvents": events[-5:],
            "target": int(relay.get("target", TRIBE_SACRED_FIRE_RELAY_TARGET_PARTICIPANTS) or TRIBE_SACRED_FIRE_RELAY_TARGET_PARTICIPANTS),
            "minParticipants": TRIBE_SACRED_FIRE_RELAY_MIN_PARTICIPANTS,
            "createdByName": relay.get("createdByName"),
            "createdAt": relay.get("createdAt"),
            "activeUntil": relay.get("activeUntil")
        }

    def _public_sacred_fire_records(self, tribe: dict) -> list:
        return list(tribe.get("sacred_fire_history", []) or [])[-TRIBE_SACRED_FIRE_RELAY_HISTORY_LIMIT:]

    def _apply_sacred_fire_reward(self, tribe: dict, reward: dict) -> list:
        parts = self._apply_tribe_reward(tribe, reward)
        pressure_relief = int((reward or {}).get("warPressureRelief", 0) or 0)
        if pressure_relief:
            relieved = self._relieve_sacred_fire_pressure(tribe, pressure_relief)
            if relieved:
                parts.append(f"战争压力-{pressure_relief}（{relieved}条边界）")
        return parts

    def _relieve_sacred_fire_pressure(self, tribe: dict, amount: int) -> int:
        tribe_id = tribe.get("id")
        relieved = 0
        now_text = datetime.now().isoformat()
        for other_id, relation in list((tribe.get("boundary_relations") or {}).items()):
            if not isinstance(relation, dict):
                continue
            current = int(relation.get("warPressure", 0) or 0)
            if current <= 0:
                continue
            relation["warPressure"] = max(0, current - amount)
            relation["canDeclareWar"] = relation["warPressure"] >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relation["lastAction"] = "sacred_fire_relief"
            relation["lastActionAt"] = now_text
            other_tribe = self.tribes.get(other_id) if hasattr(self, "tribes") else None
            if other_tribe and tribe_id:
                other_relation = other_tribe.setdefault("boundary_relations", {}).setdefault(tribe_id, {})
                other_current = int(other_relation.get("warPressure", 0) or 0)
                if other_current > 0:
                    other_relation["warPressure"] = max(0, other_current - amount)
                    other_relation["canDeclareWar"] = other_relation["warPressure"] >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                    other_relation["lastAction"] = "incoming_sacred_fire_relief"
                    other_relation["lastActionAt"] = now_text
            relieved += 1
        return relieved

    async def start_sacred_fire_relay(self, player_id: str, destination_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以发起圣火接力")
            return
        if self._active_sacred_fire_relay(tribe):
            await self._send_tribe_error(player_id, "当前已有圣火接力正在路上")
            return
        destination = TRIBE_SACRED_FIRE_RELAY_DESTINATIONS.get(destination_key)
        if not destination:
            await self._send_tribe_error(player_id, "未知圣火目的地")
            return
        if not self._has_tribe_structure_type(tribe, "campfire"):
            await self._send_tribe_error(player_id, "需要先建成营火，才能从旧火里分出火种")
            return

        now = datetime.now()
        relay = {
            "id": f"sacred_fire_{tribe_id}_{destination_key}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "destinationKey": destination_key,
            "destinationLabel": destination.get("label", "圣火目的地"),
            "summary": destination.get("summary", ""),
            "carriers": [],
            "carrierIds": [],
            "routeEvents": [],
            "target": TRIBE_SACRED_FIRE_RELAY_TARGET_PARTICIPANTS,
            "createdBy": player_id,
            "createdByName": member.get("name", "成员"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_SACRED_FIRE_RELAY_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["sacred_fire_relay"] = relay
        detail = f"{member.get('name', '成员')} 从营火分出火种，准备把圣火接力送往“{relay['destinationLabel']}”。"
        self._add_tribe_history(tribe, "ritual", "圣火接力启程", detail, player_id, {"kind": "sacred_fire_relay", "relay": relay})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def carry_sacred_fire(self, player_id: str, step_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        relay = self._active_sacred_fire_relay(tribe)
        if not relay:
            await self._send_tribe_error(player_id, "当前没有正在路上的圣火接力")
            return
        if player_id in (relay.get("carrierIds", []) or []):
            await self._send_tribe_error(player_id, "你已经护送过这次火种")
            return
        step = TRIBE_SACRED_FIRE_RELAY_STEPS.get(step_key)
        if not step:
            await self._send_tribe_error(player_id, "未知护火方式")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(step.get("woodCost", 0) or 0)
        food_cost = int(step.get("foodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"{step.get('label', '护火')}需要公共木材{wood_cost}")
            return
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"{step.get('label', '护火')}需要公共食物{food_cost}")
            return
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost

        member = tribe.get("members", {}).get(player_id, {})
        event = random.choice(TRIBE_SACRED_FIRE_RELAY_EVENTS)
        reward_parts = self._apply_sacred_fire_reward(tribe, step)
        event_parts = self._apply_sacred_fire_reward(tribe, event.get("reward", {}))
        carrier = {
            "playerId": player_id,
            "name": member.get("name", "成员"),
            "stepKey": step_key,
            "stepLabel": step.get("label", "护火"),
            "eventKey": event.get("key"),
            "eventLabel": event.get("label"),
            "rewardParts": reward_parts + event_parts,
            "joinedAt": datetime.now().isoformat()
        }
        relay.setdefault("carrierIds", []).append(player_id)
        relay.setdefault("carriers", []).append(carrier)
        relay.setdefault("routeEvents", []).append({
            "key": event.get("key"),
            "label": event.get("label"),
            "summary": event.get("summary"),
            "rewardParts": event_parts,
            "createdAt": carrier["joinedAt"]
        })
        self.players.setdefault(player_id, {})["personal_renown"] = int(self.players.get(player_id, {}).get("personal_renown", 0) or 0) + 1
        detail = f"{carrier['name']} 选择“{carrier['stepLabel']}”护送圣火，途中遭遇“{event.get('label', '路上事件')}”。"
        reward_text = carrier["rewardParts"] + ["个人声望+1"]
        if reward_text:
            detail += f" {'、'.join(reward_text)}。"
        self._add_tribe_history(tribe, "ritual", "圣火接力护送", detail, player_id, {"kind": "sacred_fire_carry", "relayId": relay.get("id"), "carrier": carrier})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_sacred_fire_relay(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        relay = self._active_sacred_fire_relay(tribe)
        if not relay:
            await self._send_tribe_error(player_id, "当前没有可以收束的圣火接力")
            return
        carriers = list(relay.get("carriers", []) or [])
        if len(carriers) < TRIBE_SACRED_FIRE_RELAY_MIN_PARTICIPANTS:
            await self._send_tribe_error(player_id, f"至少需要 {TRIBE_SACRED_FIRE_RELAY_MIN_PARTICIPANTS} 名成员轮流护火")
            return
        destination = TRIBE_SACRED_FIRE_RELAY_DESTINATIONS.get(relay.get("destinationKey"), {})
        reward_parts = self._apply_sacred_fire_reward(tribe, destination.get("reward", {}))
        if len(carriers) >= int(relay.get("target", TRIBE_SACRED_FIRE_RELAY_TARGET_PARTICIPANTS) or TRIBE_SACRED_FIRE_RELAY_TARGET_PARTICIPANTS):
            reward_parts.extend(self._apply_sacred_fire_reward(tribe, destination.get("fullReward", {})))
        relay["status"] = "completed"
        relay["completedAt"] = datetime.now().isoformat()
        relay["completedBy"] = player_id
        relay["rewardParts"] = reward_parts
        tribe.setdefault("sacred_fire_history", []).append(relay)
        tribe["sacred_fire_history"] = tribe["sacred_fire_history"][-TRIBE_SACRED_FIRE_RELAY_HISTORY_LIMIT:]

        member = tribe.get("members", {}).get(player_id, {})
        carrier_names = "、".join([item.get("name", "成员") for item in carriers])
        event_names = "、".join([item.get("eventLabel", "路上事件") for item in carriers if item.get("eventLabel")])
        detail = f"{member.get('name', '成员')} 在“{relay.get('destinationLabel', '目的地')}”收束圣火接力，护火者：{carrier_names}。"
        if event_names:
            detail += f" 途中余波：{event_names}。"
        detail += f" {'、'.join(reward_parts) or '圣火被写入部落记忆'}。"
        self._add_tribe_history(tribe, "ritual", "圣火接力完成", detail, player_id, {"kind": "sacred_fire_complete", "relay": relay, "rewardParts": reward_parts})
        await self._publish_world_rumor(
            "ritual",
            "圣火接力",
            f"{tribe.get('name', '部落')} 将火种送到{relay.get('destinationLabel', '目的地')}，{carrier_names}把途中事件变成新的祝福。",
            {"tribeId": tribe_id, "destinationKey": relay.get("destinationKey")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
