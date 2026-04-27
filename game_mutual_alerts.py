from datetime import datetime
from typing import Optional

from game_config import *


class GameMutualAidAlertMixin:
    def _active_mutual_aid_alerts(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for alert in tribe.get("mutual_aid_alerts", []) or []:
            if not isinstance(alert, dict) or alert.get("status") != "pending":
                continue
            active_until = alert.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        alert["status"] = "expired"
                        alert["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    alert["status"] = "expired"
                    alert["expiredAt"] = now.isoformat()
                    continue
            active.append(alert)
        if len(active) != len(tribe.get("mutual_aid_alerts", []) or []):
            tribe["mutual_aid_alerts"] = active[-TRIBE_MUTUAL_AID_ALERT_LIMIT:]
        return active[-TRIBE_MUTUAL_AID_ALERT_LIMIT:]

    def _mutual_aid_camp_point(self, tribe: dict) -> dict:
        camp = tribe.get("camp") or {}
        center = camp.get("center") or camp.get("spawn") or {}
        return {
            "x": float(center.get("x", 0) or 0),
            "z": float(center.get("z", 0) or 0)
        }

    def _mutual_aid_source_signals(self, tribe: dict) -> list:
        if not tribe:
            return []
        point = self._mutual_aid_camp_point(tribe)
        signals = []
        for task in self._public_emergency_followup_tasks(tribe) if hasattr(self, "_public_emergency_followup_tasks") else []:
            signals.append({
                "sourceKind": "emergency_followup",
                "sourceId": task.get("id"),
                "title": task.get("title", "紧急补救"),
                "summary": task.get("summary", "营地有一项紧急补救需要友好部落支援。"),
                "x": float(task.get("x", point["x"]) or point["x"]),
                "z": float(task.get("z", point["z"]) or point["z"])
            })
        choice = self._active_emergency_choice(tribe) if hasattr(self, "_active_emergency_choice") else None
        if choice:
            signals.append({
                "sourceKind": "emergency_choice",
                "sourceId": choice.get("id"),
                "title": choice.get("title", "紧急抉择"),
                "summary": choice.get("summary", "营地正同时承受救援与争夺压力，可以向友好部落发出火烟警报。"),
                "x": point["x"],
                "z": point["z"]
            })
        event = self._active_emergency_world_event() if hasattr(self, "_active_emergency_world_event") else None
        if event:
            signals.append({
                "sourceKind": "world_event",
                "sourceId": event.get("id"),
                "title": event.get("title", "世界灾情"),
                "summary": event.get("summary", "附近区域出现灾情或失踪风险，友好部落可以循火烟接应。"),
                "x": float(event.get("x", point["x"]) or point["x"]),
                "z": float(event.get("z", point["z"]) or point["z"])
            })
        seen = set()
        unique = []
        for signal in signals:
            key = (signal.get("sourceKind"), signal.get("sourceId"))
            if not signal.get("sourceId") or key in seen:
                continue
            seen.add(key)
            unique.append(signal)
        return unique

    def _friendly_mutual_aid_targets(self, tribe: dict) -> list:
        tribe_id = tribe.get("id")
        if not tribe_id:
            return []
        targets = []
        for other_id, other in self.tribes.items():
            if other_id == tribe_id or not isinstance(other, dict):
                continue
            own_relation = (tribe.get("boundary_relations") or {}).get(other_id) or {}
            other_relation = (other.get("boundary_relations") or {}).get(tribe_id) or {}
            relation_score = max(
                int(own_relation.get("score", 0) or 0),
                int(other_relation.get("score", 0) or 0)
            )
            trade_trust = max(
                int(own_relation.get("tradeTrust", 0) or 0),
                int(other_relation.get("tradeTrust", 0) or 0)
            )
            if relation_score < TRIBE_MUTUAL_AID_MIN_RELATION and trade_trust < TRIBE_MUTUAL_AID_MIN_TRADE_TRUST:
                continue
            targets.append({
                "id": other_id,
                "name": other.get("name", "友好部落"),
                "relationScore": relation_score,
                "tradeTrust": trade_trust
            })
        return targets

    def _mutual_aid_send_options(self, tribe: dict) -> list:
        targets = self._friendly_mutual_aid_targets(tribe)
        if not targets:
            return []
        options = []
        active_alerts = self._active_mutual_aid_alerts(tribe)
        for signal in self._mutual_aid_source_signals(tribe):
            pending_targets = {
                alert.get("targetTribeId")
                for alert in active_alerts
                if alert.get("sourceKind") == signal.get("sourceKind")
                and alert.get("sourceId") == signal.get("sourceId")
                and alert.get("direction") == "outgoing"
            }
            available_targets = [target for target in targets if target.get("id") not in pending_targets]
            if available_targets:
                options.append({**signal, "targetTribes": available_targets})
        return options

    def _mutual_aid_reward_parts(self, tribe: dict, rewards: dict, other_tribe_id: Optional[str] = None) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(rewards.get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                reward_parts.append(f"{label}{amount:+d}")
        food_cost = int(rewards.get("foodCost", 0) or 0)
        if food_cost:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) - food_cost)
            reward_parts.append(f"食物-{food_cost}")
        food = int(rewards.get("food", rewards.get("foodReward", 0)) or 0)
        if food:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) + food)
            reward_parts.append(f"食物+{food}")
        discovery = int(rewards.get("discoveryProgress", rewards.get("discoveryReward", 0)) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        renown = int(rewards.get("renown", rewards.get("renownReward", 0)) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        trade = int(rewards.get("tradeReputation", rewards.get("tradeReward", 0)) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易声誉+{trade}")
        relation_delta = int(rewards.get("relationDelta", 0) or 0)
        trust_delta = int(rewards.get("tradeTrustDelta", 0) or 0)
        pressure_relief = int(rewards.get("pressureRelief", 0) or 0)
        if other_tribe_id:
            relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
                reward_parts.append(f"关系{relation_delta:+d}")
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
                reward_parts.append(f"信任+{trust_delta}")
            if pressure_relief:
                before = int(relation.get("warPressure", 0) or 0)
                relation["warPressure"] = max(0, before - pressure_relief)
                if before != relation["warPressure"]:
                    reward_parts.append(f"战争压力-{before - relation['warPressure']}")
            relation["lastAction"] = "mutual_aid_alert"
            relation["lastActionAt"] = datetime.now().isoformat()
            reward_parts.extend(self._apply_boundary_temperature_channel_bonus(tribe, other_tribe_id, "mutual_aid"))
            if hasattr(self, "_consume_alliance_signal_hint"):
                hint = self._consume_alliance_signal_hint(tribe, other_tribe_id, "mutual_aid")
                if hint:
                    reward_parts.append(hint)
        return reward_parts

    def _sync_shared_mutual_aid_progress(self, shared_id: str, participant_ids: list, participant_names: list, progress: int):
        for target_tribe in self.tribes.values():
            for alert in target_tribe.get("mutual_aid_alerts", []) or []:
                if isinstance(alert, dict) and alert.get("sharedAlertId") == shared_id and alert.get("status") == "pending":
                    alert["participantIds"] = list(participant_ids)
                    alert["participantNames"] = list(participant_names)
                    alert["progress"] = progress

    def _complete_shared_mutual_aid_alerts(self, shared_id: str, player_id: str, member_name: str, action_key: str, action_label: str, now_text: str) -> set:
        affected = set()
        for target_tribe in self.tribes.values():
            for alert in target_tribe.get("mutual_aid_alerts", []) or []:
                if not isinstance(alert, dict) or alert.get("sharedAlertId") != shared_id or alert.get("status") != "pending":
                    continue
                alert["status"] = "completed"
                alert["completedBy"] = player_id
                alert["completedByName"] = member_name
                alert["completedAt"] = now_text
                alert["resolvedAction"] = action_key
                alert["resolvedActionLabel"] = action_label
                affected.add(target_tribe.get("id"))
        return {item for item in affected if item}

    async def send_mutual_aid_alert(self, player_id: str, source_kind: str, source_id: str, target_tribe_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        target_tribe = self.tribes.get(target_tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以发出互助警报")
            return
        if not target_tribe or target_tribe_id == tribe_id:
            await self._send_tribe_error(player_id, "没有找到可以接收警报的友好部落")
            return
        options = self._mutual_aid_send_options(tribe)
        source = next((
            item for item in options
            if item.get("sourceKind") == source_kind
            and item.get("sourceId") == source_id
            and any(target.get("id") == target_tribe_id for target in item.get("targetTribes", []))
        ), None)
        if not source:
            await self._send_tribe_error(player_id, "当前没有可向该部落发出的互助警报")
            return
        now = datetime.now()
        now_text = now.isoformat()
        safe_source = str(source_id or f"{source_kind}_{int(now.timestamp())}").replace(" ", "_")
        shared_id = f"mutual_aid_{source_kind}_{safe_source}_{tribe_id}_{target_tribe_id}"
        active_until = datetime.fromtimestamp(now.timestamp() + TRIBE_MUTUAL_AID_ALERT_ACTIVE_MINUTES * 60).isoformat()
        title = "火烟互助警报"
        summary = f"{tribe.get('name', '部落')} 因“{source.get('title', '紧急事件')}”向 {target_tribe.get('name', '友好部落')} 发出火烟警报。"
        alert_base = {
            "sharedAlertId": shared_id,
            "status": "pending",
            "kind": "mutual_aid_alert",
            "type": "mutual_aid_alert",
            "sourceKind": source_kind,
            "sourceId": source_id,
            "sourceTitle": source.get("title", "紧急事件"),
            "sourceSummary": source.get("summary", ""),
            "title": title,
            "summary": summary,
            "sourceTribeId": tribe_id,
            "sourceTribeName": tribe.get("name", "求援部落"),
            "targetTribeId": target_tribe_id,
            "targetTribeName": target_tribe.get("name", "友好部落"),
            "progress": 0,
            "target": TRIBE_MUTUAL_AID_ALERT_PROGRESS_TARGET,
            "participantIds": [],
            "participantNames": [],
            "x": float(source.get("x", 0) or 0),
            "z": float(source.get("z", 0) or 0),
            "createdBy": player_id,
            "createdByName": member.get("name", "管理者"),
            "createdAt": now_text,
            "activeUntil": active_until
        }
        outgoing = {
            **alert_base,
            "id": f"{shared_id}_{tribe_id}",
            "direction": "outgoing",
            "otherTribeId": target_tribe_id,
            "otherTribeName": target_tribe.get("name", "友好部落")
        }
        incoming = {
            **alert_base,
            "id": f"{shared_id}_{target_tribe_id}",
            "direction": "incoming",
            "otherTribeId": tribe_id,
            "otherTribeName": tribe.get("name", "求援部落")
        }
        tribe.setdefault("mutual_aid_alerts", []).append(outgoing)
        target_tribe.setdefault("mutual_aid_alerts", []).append(incoming)
        tribe["mutual_aid_alerts"] = tribe["mutual_aid_alerts"][-TRIBE_MUTUAL_AID_ALERT_LIMIT:]
        target_tribe["mutual_aid_alerts"] = target_tribe["mutual_aid_alerts"][-TRIBE_MUTUAL_AID_ALERT_LIMIT:]
        detail = f"{member.get('name', '管理者')} 向 {target_tribe.get('name', '友好部落')} 发出火烟警报：{source.get('title', '紧急事件')}。"
        target_detail = f"{tribe.get('name', '邻近部落')} 的火烟升起，请求协助处理“{source.get('title', '紧急事件')}”。"
        self._add_tribe_history(tribe, "trade", "互助警报", detail, player_id, {"kind": "mutual_aid_alert", "alertId": outgoing["id"], "targetTribeId": target_tribe_id})
        self._add_tribe_history(target_tribe, "trade", "互助警报", target_detail, player_id, {"kind": "mutual_aid_alert", "alertId": incoming["id"], "sourceTribeId": tribe_id})
        await self._publish_world_rumor(
            "trade",
            "互助警报",
            f"{tribe.get('name', '部落')} 向 {target_tribe.get('name', '友好部落')} 放出求援火烟。",
            {"tribeId": tribe_id, "targetTribeId": target_tribe_id, "alertId": shared_id}
        )
        await self._notify_tribe(tribe_id, detail)
        await self._notify_tribe(target_tribe_id, target_detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.broadcast_tribe_state(target_tribe_id)
        await self._broadcast_current_map()

    async def answer_mutual_aid_alert(self, player_id: str, alert_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_MUTUAL_AID_ALERT_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知互助响应")
            return
        alert = next((
            item for item in self._active_mutual_aid_alerts(tribe)
            if isinstance(item, dict)
            and item.get("direction") == "incoming"
            and item.get("targetTribeId") == tribe_id
            and (item.get("id") == alert_id or item.get("sharedAlertId") == alert_id)
        ), None)
        if not alert:
            await self._send_tribe_error(player_id, "没有找到可响应的互助警报")
            return
        responder_rewards = dict(action.get("responder") or {})
        food_cost = int(responder_rewards.get("foodCost", 0) or 0)
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"响应互助需要公共食物 {food_cost}")
            return
        participant_ids = list(alert.get("participantIds") or [])
        if player_id in participant_ids:
            await self._send_tribe_error(player_id, "你已经响应过这次互助警报")
            return
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        participant_ids.append(player_id)
        participant_names = list(alert.get("participantNames") or [])
        participant_names.append(member_name)
        progress = int(alert.get("progress", 0) or 0) + 1
        self._sync_shared_mutual_aid_progress(alert.get("sharedAlertId"), participant_ids, participant_names, progress)
        target = int(alert.get("target", TRIBE_MUTUAL_AID_ALERT_PROGRESS_TARGET) or 1)
        source_tribe_id = alert.get("sourceTribeId")
        source_tribe = self.tribes.get(source_tribe_id) if source_tribe_id else None
        now_text = datetime.now().isoformat()
        if progress < target:
            detail = f"{member_name} 正在响应 {alert.get('sourceTribeName', '友好部落')} 的火烟警报，进度 {progress} / {target}。"
            self._add_tribe_history(tribe, "trade", "互助警报", detail, player_id, {"kind": "mutual_aid_alert", "alertId": alert_id})
            await self._notify_tribe(tribe_id, detail)
            await self.broadcast_tribe_state(tribe_id)
            return
        affected = self._complete_shared_mutual_aid_alerts(
            alert.get("sharedAlertId"),
            player_id,
            member_name,
            action_key,
            action.get("label", "互助响应"),
            now_text
        )
        responder_parts = self._mutual_aid_reward_parts(tribe, responder_rewards, source_tribe_id)
        source_parts = []
        if source_tribe:
            source_parts = self._mutual_aid_reward_parts(source_tribe, dict(action.get("source") or {}), tribe_id)
        detail = f"{member_name} 选择“{action.get('label', '互助响应')}”回应 {alert.get('sourceTribeName', '友好部落')} 的火烟警报：{'、'.join(responder_parts) or '人情被记住'}。"
        source_detail = f"{tribe.get('name', '友好部落')} 回应火烟警报并完成“{action.get('label', '互助响应')}”：{'、'.join(source_parts) or '局势稳定'}。"
        self._add_tribe_history(tribe, "trade", "互助警报", detail, player_id, {"kind": "mutual_aid_alert", "alertId": alert_id, "action": action_key})
        if source_tribe:
            self._add_tribe_history(source_tribe, "trade", "互助警报", source_detail, player_id, {"kind": "mutual_aid_alert", "alertId": alert_id, "responderTribeId": tribe_id, "action": action_key})
        await self._publish_world_rumor(
            "trade",
            "互助警报",
            f"{tribe.get('name', '友好部落')} 回应了 {alert.get('sourceTribeName', '邻近部落')} 的火烟警报。",
            {"tribeId": tribe_id, "sourceTribeId": source_tribe_id, "alertId": alert.get("sharedAlertId"), "action": action_key}
        )
        for target_tribe_id in affected or {tribe_id}:
            target_tribe = self.tribes.get(target_tribe_id)
            if not target_tribe:
                continue
            await self._notify_tribe(target_tribe_id, source_detail if target_tribe_id == source_tribe_id else detail)
            await self.broadcast_tribe_state(target_tribe_id)
        await self._broadcast_current_map()
