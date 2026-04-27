from datetime import datetime

from game_config import *


class GameApprenticeExchangeMixin:
    def _active_apprentice_buffs(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for buff in tribe.get("apprentice_buffs", []) or []:
            if not isinstance(buff, dict):
                continue
            active_until = buff.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        buff["status"] = "expired"
                        continue
                except (TypeError, ValueError):
                    buff["status"] = "expired"
                    continue
            active.append(buff)
        if len(active) != len(tribe.get("apprentice_buffs", []) or []):
            tribe["apprentice_buffs"] = active[-TRIBE_APPRENTICE_EXCHANGE_LIMIT:]
        return active[-TRIBE_APPRENTICE_EXCHANGE_LIMIT:]

    def _apprentice_build_discount(self, tribe: dict) -> int:
        return sum(
            int(buff.get("buildCostDiscountPercent", 0) or 0)
            for buff in self._active_apprentice_buffs(tribe)
        )

    def _apprentice_ritual_gather_bonus(self, tribe: dict) -> int:
        return sum(
            int(buff.get("ritualGatherBonus", 0) or 0)
            for buff in self._active_apprentice_buffs(tribe)
        )

    def _apprentice_trade_reputation_bonus(self, tribe: dict) -> int:
        return sum(
            int(buff.get("tradeReputationBonus", 0) or 0)
            for buff in self._active_apprentice_buffs(tribe)
        )

    def _apprentice_exchange_targets(self, tribe: dict) -> list:
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
            eligible = (
                score >= TRIBE_APPRENTICE_EXCHANGE_MIN_RELATION
                or trust >= TRIBE_APPRENTICE_EXCHANGE_MIN_TRADE_TRUST
                or market_pact
            )
            if not eligible:
                continue
            targets.append({
                "id": other_id,
                "name": other.get("name", "邻近部落"),
                "relationScore": score,
                "tradeTrust": trust,
                "marketPact": market_pact,
                "summary": f"关系 {score:+d} / 信任 +{trust}" + (" / 互市约定" if market_pact else "")
            })
        return targets

    def _append_apprentice_buff(self, tribe: dict, other_tribe: dict, action_key: str, action: dict, now_text: str):
        active_until = datetime.fromtimestamp(
            datetime.fromisoformat(now_text).timestamp() + TRIBE_APPRENTICE_EXCHANGE_ACTIVE_MINUTES * 60
        ).isoformat()
        buff = {
            "id": f"apprentice_buff_{action_key}_{other_tribe.get('id')}_{int(datetime.fromisoformat(now_text).timestamp() * 1000)}",
            "status": "active",
            "key": action_key,
            "label": action.get("buffLabel", action.get("label", "学徒交换")),
            "summary": action.get("buffSummary", action.get("summary", "")),
            "otherTribeId": other_tribe.get("id"),
            "otherTribeName": other_tribe.get("name", "邻近部落"),
            "activeUntil": active_until,
            "createdAt": now_text
        }
        for key in ("buildCostDiscountPercent", "ritualGatherBonus", "tradeReputationBonus"):
            amount = int(action.get(key, 0) or 0)
            if amount:
                buff[key] = amount
        tribe.setdefault("apprentice_buffs", []).append(buff)
        tribe["apprentice_buffs"] = tribe["apprentice_buffs"][-TRIBE_APPRENTICE_EXCHANGE_LIMIT:]
        return buff

    def _record_apprentice_exchange(self, tribe: dict, other_tribe: dict, action_key: str, action: dict, member_name: str, now_text: str, reward_parts: list):
        record = {
            "id": f"apprentice_exchange_{action_key}_{other_tribe.get('id')}_{int(datetime.fromisoformat(now_text).timestamp() * 1000)}",
            "key": action_key,
            "label": action.get("label", "学徒交换"),
            "summary": action.get("summary", ""),
            "otherTribeId": other_tribe.get("id"),
            "otherTribeName": other_tribe.get("name", "邻近部落"),
            "memberName": member_name,
            "rewardParts": reward_parts,
            "createdAt": now_text
        }
        tribe.setdefault("apprentice_exchanges", []).append(record)
        tribe["apprentice_exchanges"] = tribe["apprentice_exchanges"][-TRIBE_APPRENTICE_EXCHANGE_RECENT_LIMIT:]
        return record

    def _apply_apprentice_relation(self, tribe: dict, other_tribe: dict, action_key: str, action: dict, now_text: str):
        relation_delta = int(action.get("relationDelta", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        for source, target in ((tribe, other_tribe), (other_tribe, tribe)):
            relation = source.setdefault("boundary_relations", {}).setdefault(target.get("id"), {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            relation["lastAction"] = f"apprentice_exchange_{action_key}"
            relation["lastActionAt"] = now_text

    async def start_apprentice_exchange(self, player_id: str, target_tribe_id: str, focus_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        target_tribe = self.tribes.get(target_tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not target_tribe or target_tribe_id == tribe_id:
            await self._send_tribe_error(player_id, "找不到可交换学徒的部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以安排学徒交换")
            return
        action = TRIBE_APPRENTICE_EXCHANGE_ACTIONS.get(focus_key)
        if not action:
            await self._send_tribe_error(player_id, "未知学徒方向")
            return
        if not any(target.get("id") == target_tribe_id for target in self._apprentice_exchange_targets(tribe)):
            await self._send_tribe_error(player_id, "需要先通过示好、互市或边界信任建立友好关系")
            return

        now_text = datetime.now().isoformat()
        renown = int(action.get("renown", 0) or 0)
        trade = int(action.get("tradeReputation", 0) or 0)
        for item in (tribe, target_tribe):
            item["renown"] = int(item.get("renown", 0) or 0) + renown
            item["trade_reputation"] = int(item.get("trade_reputation", 0) or 0) + trade
        self._apply_apprentice_relation(tribe, target_tribe, focus_key, action, now_text)
        self._append_apprentice_buff(tribe, target_tribe, focus_key, action, now_text)
        self._append_apprentice_buff(target_tribe, tribe, focus_key, action, now_text)

        reward_parts = []
        if renown:
            reward_parts.append(f"声望+{renown}")
        if trade:
            reward_parts.append(f"贸易信誉+{trade}")
        if int(action.get("relationDelta", 0) or 0):
            reward_parts.append(f"关系{int(action.get('relationDelta', 0) or 0):+d}")
        if int(action.get("tradeTrustDelta", 0) or 0):
            reward_parts.append(f"信任+{int(action.get('tradeTrustDelta', 0) or 0)}")

        member_name = member.get("name", "管理者")
        record = self._record_apprentice_exchange(tribe, target_tribe, focus_key, action, member_name, now_text, reward_parts)
        self._record_apprentice_exchange(target_tribe, tribe, focus_key, action, member_name, now_text, reward_parts)
        if hasattr(self, "_schedule_far_reply"):
            self._schedule_far_reply(
                tribe,
                "apprentice",
                record.get("id") or f"{focus_key}_{target_tribe_id}",
                "学徒的远方回信",
                f"学习“{action.get('label', '学徒交换')}”的年轻成员离营后，可能带回新规矩、求问或误会。",
                target_tribe,
                now_text
            )
            self._schedule_far_reply(
                target_tribe,
                "apprentice",
                record.get("id") or f"{focus_key}_{tribe_id}",
                "学徒的远方回信",
                f"学习“{action.get('label', '学徒交换')}”的年轻成员离营后，可能带回新规矩、求问或误会。",
                tribe,
                now_text
            )
        detail = f"{member_name} 与 {target_tribe.get('name', '邻近部落')} 互派学徒，方向为“{action.get('label', '学徒交换')}”：{'、'.join(reward_parts) or '双方记下新的营地经验'}。"
        self._add_tribe_history(tribe, "trade", "学徒交换", detail, player_id, {"kind": "apprentice_exchange", **record})
        self._add_tribe_history(target_tribe, "trade", "学徒交换", f"{tribe.get('name', '部落')} 派来学徒学习“{action.get('label', '学徒交换')}”，双方关系更稳。", player_id, {"kind": "apprentice_exchange", "otherTribeId": tribe_id, "actionKey": focus_key})
        await self._publish_world_rumor(
            "trade",
            "学徒交换",
            f"{tribe.get('name', '部落')} 与 {target_tribe.get('name', '邻近部落')} 互派学徒，年轻成员把新的{action.get('label', '经验')}带回营地。",
            {"tribeId": tribe_id, "targetTribeId": target_tribe_id, "action": focus_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self._notify_tribe(target_tribe_id, f"{tribe.get('name', '部落')} 发起了学徒交换：{action.get('summary', '')}")
        await self.broadcast_tribe_state(tribe_id)
        await self.broadcast_tribe_state(target_tribe_id)
