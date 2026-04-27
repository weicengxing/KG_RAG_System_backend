from datetime import datetime
import random

from game_config import *


class GameDreamOmenMixin:
    def _active_dream_omen(self, tribe: dict) -> dict | None:
        omen = tribe.get("dream_omen")
        if not isinstance(omen, dict) or omen.get("status") != "active":
            return None
        active_until = omen.get("activeUntil")
        if active_until:
            try:
                if datetime.fromisoformat(active_until) <= datetime.now():
                    omen["status"] = "expired"
                    omen["expiredAt"] = datetime.now().isoformat()
                    return None
            except (TypeError, ValueError):
                omen["status"] = "expired"
                omen["expiredAt"] = datetime.now().isoformat()
                return None
        return omen

    def _public_dream_omen(self, tribe: dict) -> dict | None:
        omen = self._active_dream_omen(tribe)
        if not omen:
            return None
        return {
            "id": omen.get("id"),
            "sourceId": omen.get("sourceId"),
            "sourceKind": omen.get("sourceKind"),
            "sourceLabel": omen.get("sourceLabel"),
            "title": omen.get("title"),
            "summary": omen.get("summary"),
            "createdByName": omen.get("createdByName"),
            "createdAt": omen.get("createdAt"),
            "activeUntil": omen.get("activeUntil")
        }

    def _dream_omen_used_source_ids(self, tribe: dict) -> set:
        used = set()
        active = self._active_dream_omen(tribe)
        if active and active.get("sourceId"):
            used.add(active.get("sourceId"))
        for record in tribe.get("dream_omen_records", []) or []:
            if isinstance(record, dict) and record.get("sourceId"):
                used.add(record.get("sourceId"))
        return used

    def _dream_omen_seed(self, kind: str, source_id: str, label: str, summary: str, event_bias: str = "") -> dict:
        return {
            "id": f"{kind}:{source_id}",
            "kind": kind,
            "sourceId": source_id,
            "label": label,
            "summary": summary,
            "eventBias": event_bias
        }

    def _public_dream_omen_sources(self, tribe: dict) -> list:
        used = self._dream_omen_used_source_ids(tribe)
        sources = []

        for record in reversed(tribe.get("night_outing_records", []) or []):
            if not isinstance(record, dict) or not record.get("success"):
                continue
            source_id = f"night:{record.get('id')}"
            if source_id in used:
                continue
            sources.append(self._dream_omen_seed(
                "night",
                source_id,
                f"{record.get('optionLabel', '夜行')}旧梦",
                f"{record.get('memberName', '成员')}在{record.get('weatherLabel', '夜色')}留下的夜路，被族人梦成另一条小径。",
                "ruin_clue"
            ))

        for record in reversed(tribe.get("celestial_records", []) or []):
            if not isinstance(record, dict):
                continue
            source_id = f"celestial:{record.get('id')}"
            if source_id in used:
                continue
            sources.append(self._dream_omen_seed(
                "celestial",
                source_id,
                f"{record.get('windowTitle', '天象')}共梦",
                f"{record.get('branchLabel', '天象解读')}在夜里反复出现，像是在催促部落确认下一条线索。",
                "ruin_clue"
            ))

        for effect in tribe.get("nomad_visitor_aftereffects", []) or []:
            if not isinstance(effect, dict) or effect.get("status", "active") not in {"active", "used"}:
                continue
            source_id = f"visitor:{effect.get('id')}"
            if source_id in used:
                continue
            sources.append(self._dream_omen_seed(
                "visitor",
                source_id,
                f"{effect.get('label', '来访余音')}入梦",
                f"{effect.get('visitorLabel', '神秘旅人')}留下的余音钻进同一个梦里，梦路带着远方口音。",
                "herd"
            ))

        ritual_sources = [
            ("standing", tribe.get("standing_ritual_history", []) or []),
            ("drum", tribe.get("drum_rhythm_history", []) or []),
            ("sacred_fire", tribe.get("sacred_fire_history", []) or []),
            ("celebration", tribe.get("celebration_echo_records", []) or [])
        ]
        for kind, records in ritual_sources:
            for record in reversed(records):
                if not isinstance(record, dict):
                    continue
                source_id = f"{kind}:{record.get('id')}"
                if source_id in used:
                    continue
                label = record.get("label") or record.get("title") or record.get("optionLabel") or "共同仪式"
                sources.append(self._dream_omen_seed(
                    kind,
                    source_id,
                    f"{label}梦痕",
                    f"{label}之后，营地里有人梦见同一圈火光和同一段脚步声。",
                    "herd"
                ))
                break

        return sources[:TRIBE_DREAM_OMEN_SOURCE_LIMIT]

    def _public_dream_omen_actions(self) -> dict:
        return TRIBE_DREAM_OMEN_ACTIONS

    def _public_dream_omen_records(self, tribe: dict) -> list:
        records = [item for item in tribe.get("dream_omen_records", []) or [] if isinstance(item, dict)]
        return records[-TRIBE_DREAM_OMEN_RECORD_LIMIT:]

    def _apply_dream_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石材")):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                storage[key] = int(storage.get(key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        pressure_relief = int((reward or {}).get("pressureRelief", 0) or 0)
        if pressure_relief:
            relieved = 0
            for relation in (tribe.get("boundary_relations") or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                after = max(0, before - pressure_relief)
                relation["warPressure"] = after
                relation["canDeclareWar"] = after >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                relieved += before - after
            parts.append(f"战争压力-{relieved or pressure_relief}")
        return parts

    async def start_dream_omen(self, player_id: str, source_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if self._active_dream_omen(tribe):
            await self._send_tribe_error(player_id, "当前已有一段共梦预兆尚未处理")
            return
        source = next((item for item in self._public_dream_omen_sources(tribe) if item.get("id") == source_id), None)
        if not source:
            await self._send_tribe_error(player_id, "这段梦兆来源已经散去")
            return
        member = tribe.get("members", {}).get(player_id, {})
        now = datetime.now()
        omen = {
            "id": f"dream_omen_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "sourceId": source.get("id"),
            "sourceKind": source.get("kind"),
            "sourceLabel": source.get("label"),
            "sourceEventBias": source.get("eventBias"),
            "title": f"共梦：{source.get('label', '梦兆')}",
            "summary": source.get("summary", "营地里有人梦见同一段路。"),
            "createdBy": player_id,
            "createdByName": member.get("name", "成员"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_DREAM_OMEN_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["dream_omen"] = omen
        detail = f"{member.get('name', '成员')}把{source.get('label', '梦兆')}讲给营地听，形成短时共梦预兆。"
        self._add_tribe_history(tribe, "world_event", "共梦预兆", detail, player_id, {"kind": "dream_omen", "omen": omen})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def resolve_dream_omen(self, player_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        omen = self._active_dream_omen(tribe)
        if not omen:
            await self._send_tribe_error(player_id, "当前没有可处理的共梦预兆")
            return
        action = TRIBE_DREAM_OMEN_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知解梦方式")
            return
        member = tribe.get("members", {}).get(player_id, {})
        reward_parts = self._apply_dream_reward(tribe, action.get("reward", {}))
        event_bias = action.get("eventBias") or omen.get("sourceEventBias")
        if event_bias:
            tribe.setdefault("dream_omen_event_biases", []).append({
                "id": f"dream_bias_{omen.get('id')}_{action_key}",
                "eventKey": event_bias,
                "eventLabel": action.get("eventBiasLabel", event_bias),
                "sourceLabel": omen.get("sourceLabel"),
                "uses": TRIBE_DREAM_OMEN_EVENT_BIAS_USES,
                "createdAt": datetime.now().isoformat()
            })
            tribe["dream_omen_event_biases"] = tribe["dream_omen_event_biases"][-TRIBE_DREAM_OMEN_RECORD_LIMIT:]
            reward_parts.append(f"下次事件偏向：{action.get('eventBiasLabel', event_bias)}")
        omen["status"] = "resolved"
        omen["resolvedAt"] = datetime.now().isoformat()
        omen["resolvedBy"] = player_id
        omen["resolvedByName"] = member.get("name", "成员")
        omen["actionKey"] = action_key
        omen["actionLabel"] = action.get("label", "解梦")
        omen["rewardParts"] = reward_parts
        tribe.setdefault("dream_omen_records", []).append(dict(omen))
        tribe["dream_omen_records"] = tribe["dream_omen_records"][-TRIBE_DREAM_OMEN_RECORD_LIMIT:]
        tribe["dream_omen"] = None
        detail = f"{member.get('name', '成员')}选择{action.get('label', '解梦')}处理{omen.get('sourceLabel', '共梦预兆')}，{'、'.join(reward_parts) or '营地记住了这段梦'}。"
        self._add_tribe_history(tribe, "world_event", "共梦预兆处理", detail, player_id, {"kind": "dream_omen_resolve", "omen": omen})
        await self._publish_world_rumor(
            "world_event",
            "共梦预兆",
            f"{tribe.get('name', '部落')}把{omen.get('sourceLabel', '一段梦兆')}处理成{action.get('label', '解梦')}，营地开始按梦里的方向解释下一次异象。",
            {"tribeId": tribe_id, "omenId": omen.get("id"), "action": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    def _apply_dream_omen_world_event_bias(self, event_pool: list) -> list:
        if not event_pool:
            return event_pool
        pool = list(event_pool)
        events_by_key = {event.get("key"): event for event in event_pool if isinstance(event, dict)}
        changed = False
        for tribe in getattr(self, "tribes", {}).values():
            biases = []
            for bias in tribe.get("dream_omen_event_biases", []) or []:
                if not isinstance(bias, dict) or int(bias.get("uses", 0) or 0) <= 0:
                    continue
                event = events_by_key.get(bias.get("eventKey"))
                if not event:
                    continue
                pool.extend([event, event])
                bias["uses"] = max(0, int(bias.get("uses", 0) or 0) - 1)
                bias["usedAt"] = datetime.now().isoformat()
                changed = True
                biases.append(bias)
            if changed:
                tribe["dream_omen_event_biases"] = [
                    item for item in (tribe.get("dream_omen_event_biases", []) or [])
                    if isinstance(item, dict) and int(item.get("uses", 0) or 0) > 0
                ][-TRIBE_DREAM_OMEN_RECORD_LIMIT:]
        if changed and hasattr(self, "_save_tribe_state"):
            self._save_tribe_state()
        return pool
