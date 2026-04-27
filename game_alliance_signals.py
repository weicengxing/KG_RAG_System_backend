import math
from datetime import datetime

from game_config import *


class GameAllianceSignalMixin:
    def _alliance_signal_now(self):
        return datetime.now()

    def _alliance_signal_expired(self, active_until: str | None) -> bool:
        if not active_until:
            return False
        try:
            return datetime.fromisoformat(active_until) <= self._alliance_signal_now()
        except (TypeError, ValueError):
            return True

    def _active_alliance_signals(self, tribe: dict) -> list:
        if not tribe:
            return []
        active = []
        changed = False
        now_text = self._alliance_signal_now().isoformat()
        for signal in tribe.get("alliance_signals", []) or []:
            if not isinstance(signal, dict):
                continue
            if signal.get("status") != "active":
                changed = True
                continue
            if self._alliance_signal_expired(signal.get("activeUntil")):
                signal["status"] = "expired"
                signal["expiredAt"] = now_text
                changed = True
                continue
            active.append(signal)
        if changed:
            tribe["alliance_signals"] = active[-TRIBE_ALLIANCE_SIGNAL_LIMIT:]
        return active[-TRIBE_ALLIANCE_SIGNAL_LIMIT:]

    def _public_alliance_signals(self, tribe: dict) -> list:
        return [self._public_alliance_signal(signal) for signal in self._active_alliance_signals(tribe)]

    def _public_alliance_signal_records(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("alliance_signal_records", []) or [])
            if isinstance(item, dict)
        ][-TRIBE_ALLIANCE_SIGNAL_RECORD_LIMIT:]

    def _public_alliance_signal_actions(self) -> dict:
        return TRIBE_ALLIANCE_SIGNAL_ACTIONS

    def _public_alliance_signal_influences(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = self._alliance_signal_now()
        active = []
        for item in tribe.get("alliance_signal_influences", []) or []:
            if not isinstance(item, dict):
                continue
            if item.get("status") == "consumed":
                continue
            active_until = item.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    continue
            active.append(item)
        tribe["alliance_signal_influences"] = active[-TRIBE_ALLIANCE_SIGNAL_RECORD_LIMIT:]
        return active[-TRIBE_ALLIANCE_SIGNAL_RECORD_LIMIT:]

    def _active_alliance_signal_hints(self, tribe: dict) -> list:
        return self._public_alliance_signal_influences(tribe)

    def _consume_alliance_signal_hint(self, tribe: dict, other_tribe_id: str, channel: str) -> str:
        if not tribe or not other_tribe_id or not channel:
            return ""
        for item in self._public_alliance_signal_influences(tribe):
            if item.get("otherTribeId") != other_tribe_id:
                continue
            if channel not in (item.get("channels") or []):
                continue
            item["status"] = "consumed"
            item["consumedAt"] = self._alliance_signal_now().isoformat()
            item["consumedByChannel"] = channel
            return f"旗语呼应：{item.get('summary', '先前联盟旗语被后续行动接上')}"
        return ""

    def _public_alliance_signal(self, signal: dict) -> dict:
        return {
            "id": signal.get("id"),
            "sharedSignalId": signal.get("sharedSignalId"),
            "direction": signal.get("direction"),
            "status": signal.get("status", "active"),
            "actionKey": signal.get("actionKey"),
            "actionLabel": signal.get("actionLabel", "联盟旗语"),
            "title": signal.get("title", "联盟旗语"),
            "summary": signal.get("summary", ""),
            "sourceTribeId": signal.get("sourceTribeId"),
            "sourceTribeName": signal.get("sourceTribeName"),
            "targetTribeId": signal.get("targetTribeId"),
            "targetTribeName": signal.get("targetTribeName"),
            "otherTribeId": signal.get("otherTribeId"),
            "otherTribeName": signal.get("otherTribeName"),
            "anchorLabel": signal.get("anchorLabel"),
            "anchorKind": signal.get("anchorKind"),
            "x": signal.get("x", 0),
            "z": signal.get("z", 0),
            "createdByName": signal.get("createdByName", ""),
            "rewardParts": list(signal.get("rewardParts", []) or []),
            "influenceLabel": signal.get("influenceLabel", ""),
            "createdAt": signal.get("createdAt"),
            "activeUntil": signal.get("activeUntil")
        }

    def _alliance_signal_relation(self, tribe: dict, other_tribe_id: str) -> dict:
        return (tribe.get("boundary_relations", {}) or {}).get(other_tribe_id, {}) or {}

    def _alliance_signal_relation_stats(self, tribe: dict, other_tribe: dict) -> dict:
        tribe_id = tribe.get("id")
        other_id = other_tribe.get("id")
        own_relation = self._alliance_signal_relation(tribe, other_id)
        other_relation = self._alliance_signal_relation(other_tribe, tribe_id)
        relation_score = max(
            int(own_relation.get("score", 0) or 0),
            int(other_relation.get("score", 0) or 0)
        )
        trade_trust = max(
            int(own_relation.get("tradeTrust", 0) or 0),
            int(other_relation.get("tradeTrust", 0) or 0)
        )
        temperature = self._boundary_temperature_label(own_relation) if hasattr(self, "_boundary_temperature_label") else {"key": "", "label": ""}
        other_temperature = self._boundary_temperature_label(other_relation) if hasattr(self, "_boundary_temperature_label") else {"key": "", "label": ""}
        temperature_key = temperature.get("key") or other_temperature.get("key") or ""
        if temperature_key not in ("warm", "open") and other_temperature.get("key") in ("warm", "open"):
            temperature = other_temperature
            temperature_key = other_temperature.get("key", "")
        eligible = (
            relation_score >= TRIBE_ALLIANCE_SIGNAL_MIN_RELATION
            or trade_trust >= TRIBE_ALLIANCE_SIGNAL_MIN_TRADE_TRUST
            or temperature_key in ("warm", "open")
        )
        return {
            "relationScore": relation_score,
            "tradeTrust": trade_trust,
            "temperatureKey": temperature_key,
            "temperatureLabel": temperature.get("label", ""),
            "eligible": eligible
        }

    def _alliance_signal_anchor(self, tribe: dict, target_tribe_id: str = "") -> dict:
        flags = [
            flag for flag in (tribe.get("territory_flags", []) or [])
            if isinstance(flag, dict)
        ]
        related_flag = next((
            flag for flag in reversed(flags)
            if (flag.get("boundaryRelation") or {}).get("otherTribeId") == target_tribe_id
        ), None)
        flag = related_flag or (flags[-1] if flags else None)
        if flag:
            return {
                "kind": "tribe_flag",
                "label": flag.get("label", "营地旗帜"),
                "x": float(flag.get("x", 0) or 0),
                "z": float(flag.get("z", 0) or 0)
            }
        for route in self._active_trade_route_sites(tribe) if hasattr(self, "_active_trade_route_sites") else []:
            if not target_tribe_id or route.get("partnerTribeId") == target_tribe_id:
                return {
                    "kind": "border_market",
                    "label": route.get("label", "边市通路"),
                    "x": float(route.get("x", 0) or 0),
                    "z": float(route.get("z", 0) or 0)
                }
        for site in self._active_diplomacy_council_sites(tribe) if hasattr(self, "_active_diplomacy_council_sites") else []:
            participants = set(site.get("participantTribeIds", []) or [])
            if not target_tribe_id or target_tribe_id in participants:
                return {
                    "kind": "diplomacy_council",
                    "label": site.get("label", "大议会会场"),
                    "x": float(site.get("x", 0) or 0),
                    "z": float(site.get("z", 0) or 0)
                }
        for trial in self._active_trial_grounds(tribe) if hasattr(self, "_active_trial_grounds") else []:
            return {
                "kind": "trial_ground",
                "label": trial.get("label", "试炼场"),
                "x": float(trial.get("x", 0) or 0),
                "z": float(trial.get("z", 0) or 0)
            }
        camp = tribe.get("camp") or {}
        center = camp.get("center") or camp.get("spawn") or {}
        return {
            "kind": "camp",
            "label": "营地中心",
            "x": float(center.get("x", 0) or 0),
            "z": float(center.get("z", 0) or 0)
        }

    def _public_alliance_signal_locations(self, tribe: dict) -> list:
        if not tribe:
            return []
        locations = []
        camp_anchor = self._alliance_signal_anchor(tribe, "")
        locations.append({
            "id": "camp_flag",
            "kind": camp_anchor.get("kind", "camp"),
            "label": camp_anchor.get("label", "营地旗帜"),
            "summary": "在营地旗帜或营地中心旁打出双方都能认出的短旗语。",
            "x": camp_anchor.get("x", 0),
            "z": camp_anchor.get("z", 0),
            "radius": TRIBE_ALLIANCE_SIGNAL_RADIUS
        })
        for route in self._active_trade_route_sites(tribe) if hasattr(self, "_active_trade_route_sites") else []:
            if not isinstance(route, dict) or not route.get("isBorderMarket"):
                continue
            locations.append({
                "id": f"border_market:{route.get('id')}",
                "kind": "border_market",
                "label": route.get("label", "边市旗语位"),
                "summary": "在边市摊位旁挥旗，让互市口信先走一步。",
                "x": float(route.get("x", 0) or 0),
                "z": float(route.get("z", 0) or 0),
                "radius": TRIBE_ALLIANCE_SIGNAL_RADIUS
            })
            break
        for trial in self._active_trial_grounds(tribe) if hasattr(self, "_active_trial_grounds") else []:
            if not isinstance(trial, dict):
                continue
            locations.append({
                "id": f"trial_ground:{trial.get('id')}",
                "kind": "trial_ground",
                "label": trial.get("label", "试炼场旗语位"),
                "summary": "在试炼场旁打出守望或庆功旗语。",
                "x": float(trial.get("x", 0) or 0),
                "z": float(trial.get("z", 0) or 0),
                "radius": TRIBE_ALLIANCE_SIGNAL_RADIUS
            })
            break
        return locations[:TRIBE_ALLIANCE_SIGNAL_LOCATION_LIMIT]

    def _alliance_signal_near_location(self, player_id: str, location: dict) -> bool:
        player = (getattr(self, "players", {}) or {}).get(player_id, {}) or {}
        dx = float(player.get("x", 0) or 0) - float(location.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(location.get("z", 0) or 0)
        return math.sqrt(dx * dx + dz * dz) <= float(location.get("radius", TRIBE_ALLIANCE_SIGNAL_RADIUS) or TRIBE_ALLIANCE_SIGNAL_RADIUS)

    def _public_alliance_signal_targets(self, tribe: dict) -> list:
        if not tribe:
            return []
        tribe_id = tribe.get("id")
        active_pairs = {
            (signal.get("otherTribeId"), signal.get("actionKey"))
            for signal in self._active_alliance_signals(tribe)
            if isinstance(signal, dict)
        }
        targets = []
        for other_id, other in (getattr(self, "tribes", {}) or {}).items():
            if other_id == tribe_id or not isinstance(other, dict):
                continue
            stats = self._alliance_signal_relation_stats(tribe, other)
            if not stats.get("eligible"):
                continue
            actions = [
                key for key in TRIBE_ALLIANCE_SIGNAL_ACTIONS.keys()
                if (other_id, key) not in active_pairs
            ]
            if not actions:
                continue
            anchor = self._alliance_signal_anchor(tribe, other_id)
            targets.append({
                "id": other_id,
                "name": other.get("name", "友好部落"),
                "otherTribeId": other_id,
                "otherTribeName": other.get("name", "友好部落"),
                "relationScore": stats.get("relationScore", 0),
                "score": stats.get("relationScore", 0),
                "tradeTrust": stats.get("tradeTrust", 0),
                "warPressure": int(self._alliance_signal_relation(tribe, other_id).get("warPressure", 0) or 0),
                "temperatureKey": stats.get("temperatureKey", ""),
                "temperatureLabel": stats.get("temperatureLabel", ""),
                "summary": "这条边界已有足够善意或热络口风，可以约定短时旗语。",
                "availableActions": actions,
                "anchorKind": anchor.get("kind"),
                "anchorLabel": anchor.get("label")
            })
        targets.sort(key=lambda item: (-item.get("relationScore", 0), -item.get("tradeTrust", 0), item.get("name", "")))
        return targets

    def _apply_alliance_signal_reward(self, tribe: dict, other_tribe_id: str, reward: dict, action_key: str) -> list:
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
        trade = int((reward or {}).get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            parts.append(f"贸易信誉+{trade}")
        discovery = int((reward or {}).get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            parts.append(f"发现+{discovery}")
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        relation_delta = int((reward or {}).get("relationDelta", 0) or 0)
        if relation_delta:
            relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            parts.append(f"关系{relation_delta:+d}")
        trust_delta = int((reward or {}).get("tradeTrustDelta", 0) or 0)
        if trust_delta:
            relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            parts.append(f"信任+{trust_delta}")
        pressure_relief = int((reward or {}).get("warPressureRelief", 0) or 0)
        if pressure_relief:
            before = int(relation.get("warPressure", 0) or 0)
            relation["warPressure"] = max(0, before - pressure_relief)
            relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            if before != relation["warPressure"]:
                parts.append(f"战争压力-{before - relation['warPressure']}")
        relation["lastAction"] = f"alliance_signal_{action_key}"
        relation["lastActionAt"] = self._alliance_signal_now().isoformat()
        if hasattr(self, "_apply_boundary_temperature_channel_bonus"):
            parts.extend(self._apply_boundary_temperature_channel_bonus(tribe, other_tribe_id, "messenger"))
        return parts

    def _append_alliance_signal_influence(self, tribe: dict, other_tribe_id: str, other_name: str, action: dict, now_text: str, active_until: str):
        influence = {
            "id": f"alliance_signal_influence_{tribe.get('id')}_{other_tribe_id}_{int(self._alliance_signal_now().timestamp() * 1000)}",
            "otherTribeId": other_tribe_id,
            "otherTribeName": other_name,
            "actionLabel": action.get("label", "联盟旗语"),
            "channels": list(action.get("channels", []) or []),
            "summary": action.get("influenceSummary") or action.get("followupText", "下一次信使、互助或边境戏台会引用这次旗语。"),
            "createdAt": now_text,
            "activeUntil": active_until
        }
        tribe.setdefault("alliance_signal_influences", []).append(influence)
        tribe["alliance_signal_influences"] = tribe["alliance_signal_influences"][-TRIBE_ALLIANCE_SIGNAL_RECORD_LIMIT:]

    async def send_alliance_signal(self, player_id: str, target_tribe_id: str, location_or_action_key: str, action_key: str = ""):
        location_id = ""
        if action_key:
            location_id = location_or_action_key
        else:
            action_key = location_or_action_key
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        target_tribe = self.tribes.get(target_tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not target_tribe or target_tribe_id == tribe_id:
            await self._send_tribe_error(player_id, "没有找到可发送旗语的友好部落")
            return
        action = TRIBE_ALLIANCE_SIGNAL_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知联盟旗语")
            return
        target = next((item for item in self._public_alliance_signal_targets(tribe) if item.get("id") == target_tribe_id), None)
        if not target or action_key not in (target.get("availableActions") or []):
            await self._send_tribe_error(player_id, "这条边界当前还不能约定该旗语")
            return

        selected_location = None
        if location_id:
            selected_location = next((item for item in self._public_alliance_signal_locations(tribe) if item.get("id") == location_id), None)
            if not selected_location:
                await self._send_tribe_error(player_id, "没有找到可发送旗语的位置")
                return
            if not self._alliance_signal_near_location(player_id, selected_location):
                await self._send_tribe_error(player_id, f"需要靠近 {selected_location.get('label', '旗语位置')} {TRIBE_ALLIANCE_SIGNAL_RADIUS} 步内")
                return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        now = self._alliance_signal_now()
        now_text = now.isoformat()
        active_until = datetime.fromtimestamp(now.timestamp() + TRIBE_ALLIANCE_SIGNAL_ACTIVE_MINUTES * 60).isoformat()
        anchor = selected_location or self._alliance_signal_anchor(tribe, target_tribe_id)
        shared_id = f"alliance_signal_{tribe_id}_{target_tribe_id}_{action_key}_{int(now.timestamp() * 1000)}"
        action_label = action.get("label", "联盟旗语")
        influence_label = action.get("influenceSummary") or action.get("followupText", "下一次信使/互助/边境戏台会带上这次旗语。")
        source_reward = dict(action.get("source") or action.get("senderReward") or {})
        target_reward = dict(action.get("target") or action.get("targetReward") or action.get("senderReward") or {})
        source_parts = self._apply_alliance_signal_reward(tribe, target_tribe_id, source_reward, action_key)
        target_parts = self._apply_alliance_signal_reward(target_tribe, tribe_id, target_reward, action_key)
        all_parts = source_parts + [f"对方{part}" for part in target_parts[:3]]
        title = f"{action_label}升起"
        summary = f"{tribe.get('name', '部落')} 在{anchor.get('label', '营地旗帜')}旁向 {target_tribe.get('name', '友好部落')} 发送{action_label}。"
        base = {
            "sharedSignalId": shared_id,
            "status": "active",
            "kind": "alliance_signal",
            "type": "alliance_signal",
            "actionKey": action_key,
            "actionLabel": action_label,
            "title": title,
            "summary": summary,
            "sourceTribeId": tribe_id,
            "sourceTribeName": tribe.get("name", "部落"),
            "targetTribeId": target_tribe_id,
            "targetTribeName": target_tribe.get("name", "友好部落"),
            "anchorKind": anchor.get("kind"),
            "anchorLabel": anchor.get("label"),
            "x": anchor.get("x", 0),
            "z": anchor.get("z", 0),
            "createdBy": player_id,
            "createdByName": member_name,
            "createdAt": now_text,
            "activeUntil": active_until,
            "influenceLabel": influence_label
        }
        outgoing = {
            **base,
            "id": f"{shared_id}_{tribe_id}",
            "direction": "outgoing",
            "otherTribeId": target_tribe_id,
            "otherTribeName": target_tribe.get("name", "友好部落"),
            "rewardParts": source_parts
        }
        incoming = {
            **base,
            "id": f"{shared_id}_{target_tribe_id}",
            "direction": "incoming",
            "otherTribeId": tribe_id,
            "otherTribeName": tribe.get("name", "部落"),
            "rewardParts": target_parts
        }
        tribe.setdefault("alliance_signals", []).append(outgoing)
        target_tribe.setdefault("alliance_signals", []).append(incoming)
        tribe["alliance_signals"] = tribe["alliance_signals"][-TRIBE_ALLIANCE_SIGNAL_LIMIT:]
        target_tribe["alliance_signals"] = target_tribe["alliance_signals"][-TRIBE_ALLIANCE_SIGNAL_LIMIT:]

        record = {
            "id": shared_id,
            "actionKey": action_key,
            "actionLabel": action_label,
            "sourceTribeId": tribe_id,
            "sourceTribeName": tribe.get("name", "部落"),
            "targetTribeId": target_tribe_id,
            "targetTribeName": target_tribe.get("name", "友好部落"),
            "anchorLabel": anchor.get("label"),
            "memberName": member_name,
            "rewardParts": all_parts,
            "influenceLabel": influence_label,
            "createdAt": now_text
        }
        tribe.setdefault("alliance_signal_records", []).append({**record, "direction": "outgoing"})
        target_tribe.setdefault("alliance_signal_records", []).append({**record, "direction": "incoming"})
        tribe["alliance_signal_records"] = tribe["alliance_signal_records"][-TRIBE_ALLIANCE_SIGNAL_RECORD_LIMIT:]
        target_tribe["alliance_signal_records"] = target_tribe["alliance_signal_records"][-TRIBE_ALLIANCE_SIGNAL_RECORD_LIMIT:]
        self._append_alliance_signal_influence(tribe, target_tribe_id, target_tribe.get("name", "友好部落"), action, now_text, active_until)
        self._append_alliance_signal_influence(target_tribe, tribe_id, tribe.get("name", "部落"), action, now_text, active_until)

        detail = f"{member_name} 向 {target_tribe.get('name', '友好部落')} 发送{action_label}：{'、'.join(source_parts) or '善意已被看见'}。"
        target_detail = f"{tribe.get('name', '邻近部落')} 的{action_label}抵达营地：{'、'.join(target_parts) or '边界口风变暖'}。"
        self._add_tribe_history(tribe, "diplomacy", "联盟旗语", detail, player_id, {"kind": "alliance_signal", "record": record})
        self._add_tribe_history(target_tribe, "diplomacy", "联盟旗语", target_detail, player_id, {"kind": "alliance_signal", "record": record})
        await self._publish_world_rumor(
            "diplomacy",
            "联盟旗语",
            f"{tribe.get('name', '部落')} 与 {target_tribe.get('name', '友好部落')} 在边界上约定了{action_label}。",
            {"tribeId": tribe_id, "targetTribeId": target_tribe_id, "signalId": shared_id, "action": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self._notify_tribe(target_tribe_id, target_detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.broadcast_tribe_state(target_tribe_id)
        await self._broadcast_current_map()
