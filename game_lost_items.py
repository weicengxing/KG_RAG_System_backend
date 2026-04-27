import random
from datetime import datetime

from game_config import *


class GameLostItemMixin:
    def _lost_item_active_until(self) -> str:
        return datetime.fromtimestamp(
            datetime.now().timestamp() + TRIBE_LOST_ITEM_ACTIVE_MINUTES * 60
        ).isoformat()

    def _lost_item_source_profile(self, record: dict) -> tuple[str, dict] | None:
        related_kind = str((record.get("related") or {}).get("kind", ""))
        if related_kind.startswith("lost_item"):
            return None
        text = " ".join([
            str(record.get("type", "")),
            str(record.get("title", "")),
            str(record.get("detail", "")),
            related_kind,
        ]).lower()
        for key, profile in TRIBE_LOST_ITEM_PROFILES.items():
            if any(str(keyword).lower() in text for keyword in profile.get("keywords", [])):
                return key, profile
        return None

    def _lost_item_position(self, tribe: dict, record: dict) -> tuple[float, float]:
        related = record.get("related") or {}
        x = record.get("x", related.get("x"))
        z = record.get("z", related.get("z"))
        if x is not None and z is not None:
            return float(x or 0), float(z or 0)
        center = ((tribe.get("camp") or {}).get("center") or {})
        base_x = float(center.get("x", 0) or 0)
        base_z = float(center.get("z", 0) or 0)
        offset_seed = len(str(record.get("id", ""))) + len(tribe.get("id", ""))
        rng = random.Random(offset_seed)
        return base_x + rng.randint(-22, 22), base_z + rng.randint(-22, 22)

    def _lost_item_source_chain(self, tribe: dict, record: dict | None, item: dict | None = None) -> list[str]:
        chain = []
        origin_name = (tribe or {}).get("name") or (item or {}).get("originTribeName")
        if origin_name:
            chain.append(origin_name)
        source_label = (item or {}).get("sourceLabel") or ((record or {}).get("title") if record else "")
        if source_label:
            chain.append(source_label)
        source_title = (item or {}).get("sourceTitle") or ((record or {}).get("detail") if record else "")
        if source_title and source_title not in chain:
            chain.append(str(source_title)[:36])
        return chain[:4]

    def _seed_lost_item_from_record(self, tribe: dict, record: dict) -> dict | None:
        if not tribe or not isinstance(record, dict) or not record.get("id"):
            return None
        source = self._lost_item_source_profile(record)
        if not source:
            return None
        source_key, profile = source
        source_id = str(record.get("id"))
        existing = [
            item for item in (tribe.get("lost_items", []) or [])
            if isinstance(item, dict) and item.get("sourceId") == source_id
        ]
        records = [
            item for item in (tribe.get("lost_item_records", []) or [])
            if isinstance(item, dict) and item.get("sourceId") == source_id
        ]
        if existing or records:
            return None
        x, z = self._lost_item_position(tribe, record)
        now = datetime.now()
        lost_item = {
            "id": f"lost_item_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "floating",
            "sourceKind": source_key,
            "sourceId": source_id,
            "sourceTitle": record.get("title") or profile.get("label", "旧事"),
            "sourceLabel": profile.get("label", "漂流旧物"),
            "sourceChain": self._lost_item_source_chain(tribe, record),
            "label": profile.get("label", "漂流失物"),
            "summary": profile.get("summary") or f"{record.get('title', profile.get('label', '旧事'))}之后，有一件失物在路边漂流，等待后来者处理。",
            "originTribeId": tribe.get("id"),
            "originTribeName": tribe.get("name", "部落"),
            "x": x,
            "z": z,
            "createdAt": now.isoformat(),
            "activeUntil": self._lost_item_active_until()
        }
        tribe.setdefault("lost_items", []).append(lost_item)
        tribe["lost_items"] = tribe["lost_items"][-TRIBE_LOST_ITEM_LIMIT:]
        return lost_item

    def _active_lost_items(self, tribe: dict) -> list[dict]:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for item in tribe.get("lost_items", []) or []:
            if not isinstance(item, dict) or item.get("status") != "floating":
                continue
            if not self._active_until_still_valid(item, now):
                item["status"] = "expired"
                item["expiredAt"] = now.isoformat()
                continue
            active.append(item)
        tribe["lost_items"] = active[-TRIBE_LOST_ITEM_LIMIT:]
        return tribe["lost_items"]

    def _refresh_lost_items(self, tribe: dict) -> list[dict]:
        active = self._active_lost_items(tribe)
        if len(active) >= TRIBE_LOST_ITEM_LIMIT:
            return active
        for record in list(tribe.get("history", []) or [])[-TRIBE_LOST_ITEM_SOURCE_SCAN_LIMIT:]:
            self._seed_lost_item_from_record(tribe, record)
            active = self._active_lost_items(tribe)
            if len(active) >= TRIBE_LOST_ITEM_LIMIT:
                break
        return active

    def _public_lost_items(self, tribe: dict) -> list[dict]:
        items = []
        for item in self._refresh_lost_items(tribe):
            public = dict(item)
            public.setdefault("sourceChain", self._lost_item_source_chain(tribe, None, item))
            items.append(public)
        return items

    def _public_lost_item_records(self, tribe: dict) -> list[dict]:
        return [
            item for item in (tribe.get("lost_item_records", []) or [])
            if isinstance(item, dict)
        ][-TRIBE_LOST_ITEM_RECORD_LIMIT:]

    def _find_lost_item(self, item_id: str) -> tuple[str, dict, dict] | tuple[None, None, None]:
        for tribe_id, tribe in self.tribes.items():
            for item in self._active_lost_items(tribe):
                if item.get("id") == item_id:
                    return tribe_id, tribe, item
        return None, None, None

    def _apply_lost_item_reward(self, tribe: dict, action: dict) -> list[str]:
        parts = []
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress"),
        ):
            amount = int(action.get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        pressure_relief = int(action.get("warPressureRelief", 0) or 0)
        if pressure_relief:
            changed = 0
            for relation in (tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                relation["warPressure"] = max(0, before - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                changed += before - int(relation.get("warPressure", 0) or 0)
            if changed:
                parts.append(f"战争压力-{changed}")
        return parts

    def _lost_item_relation_reward(self, actor_tribe: dict, owner_tribe: dict, action: dict) -> list[str]:
        if not actor_tribe or not owner_tribe or actor_tribe.get("id") == owner_tribe.get("id"):
            return []
        parts = []
        relation_delta = int(action.get("relationDelta", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        for own, target in ((actor_tribe, owner_tribe), (owner_tribe, actor_tribe)):
            relation = own.setdefault("boundary_relations", {}).setdefault(target.get("id"), {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            relation["lastAction"] = "lost_item_return"
            relation["lastActionAt"] = datetime.now().isoformat()
        if relation_delta:
            parts.append(f"双方关系{relation_delta:+d}")
        if trust_delta:
            parts.append(f"双方信任+{trust_delta}")
        return parts

    def _lost_item_hide_pressure(self, actor_tribe: dict, owner_tribe: dict, item: dict, now_text: str) -> tuple[list[str], list[str]]:
        if not actor_tribe or not owner_tribe or actor_tribe.get("id") == owner_tribe.get("id"):
            return [], []
        pressure = 2 if item.get("sourceKind") == "war" else 1
        parts = []
        wake_ids = []
        for own, target in ((actor_tribe, owner_tribe), (owner_tribe, actor_tribe)):
            relation = own.setdefault("boundary_relations", {}).setdefault(target.get("id"), {})
            relation["warPressure"] = min(
                TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD,
                int(relation.get("warPressure", 0) or 0) + pressure
            )
            relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relation["lastAction"] = "lost_item_hidden_revealed"
            relation["lastActionAt"] = now_text
            if hasattr(self, "_wake_old_grudge_after_pressure"):
                task = self._wake_old_grudge_after_pressure(own, target.get("id"), "私藏失物揭晓")
                if task:
                    wake_ids.append(task.get("id"))
        parts.append(f"旧怨压力+{pressure}")
        return parts, wake_ids

    def _lost_item_hidden_common_judge_cases(self, judge_tribe_id: str, recent_source_ids: set) -> list[dict]:
        cases = []
        for actor_id, tribe in (getattr(self, "tribes", {}) or {}).items():
            if actor_id == judge_tribe_id:
                continue
            for record in (tribe.get("lost_item_records", []) or [])[-TRIBE_LOST_ITEM_RECORD_LIMIT:]:
                if not isinstance(record, dict) or record.get("actionKey") != "hide":
                    continue
                if record.get("actorTribeId") != actor_id:
                    continue
                source_case_id = record.get("id")
                owner_id = record.get("originTribeId")
                if not source_case_id or source_case_id in recent_source_ids or owner_id == judge_tribe_id:
                    continue
                cases.append({
                    "id": self._common_judge_case_id("lost_item_hide", source_case_id, actor_id, owner_id) if hasattr(self, "_common_judge_case_id") else f"common_judge_lost_item_{source_case_id}",
                    "kind": "lost_item_hide",
                    "sourceCaseId": source_case_id,
                    "sourceTribeId": actor_id,
                    "sourceTribeName": tribe.get("name", "私藏部落"),
                    "otherTribeId": owner_id,
                    "otherTribeName": record.get("originTribeName", "来源部落"),
                    "title": "私藏失物待裁",
                    "summary": f"{record.get('actorTribeName', '部落')}私藏了来自{record.get('originTribeName', '来源部落')}的{record.get('label', '失物')}，中立部落可以决定它更像误收、贪藏还是旧怨证据。",
                    "sourceLabel": record.get("sourceChainLabel") or record.get("sourceLabel", "失物来源链"),
                    "activeUntil": record.get("activeUntil"),
                    "stakes": record.get("sourceChain", [])[-3:] or [record.get("sourceLabel", "失物")]
                })
        return cases

    def _collect_lost_item(self, tribe: dict, item: dict, player_id: str, member_name: str, now_text: str) -> tuple[dict, dict]:
        collection = {
            "id": f"collection_{tribe.get('id')}_{int(datetime.now().timestamp() * 1000)}",
            "sourceKey": f"lost_item:{item.get('id')}",
            "sourceKind": "lost_item",
            "sourceLabel": item.get("sourceLabel", "漂流失物"),
            "sourceId": item.get("id"),
            "label": item.get("label", "失物"),
            "displayLabel": "失物收藏",
            "summary": item.get("summary", ""),
            "curatorId": player_id,
            "curatorName": member_name,
            "rewardParts": ["声望+1"],
            "createdAt": now_text
        }
        tribe.setdefault("collection_wall", []).append(collection)
        tribe["collection_wall"] = tribe["collection_wall"][-TRIBE_COLLECTION_WALL_LIMIT:]
        influence = {
            "id": f"collection_influence_{collection['id']}",
            "sourceKind": "lost_item",
            "label": "漂流旧痕",
            "summary": "这件失物会让后续信物、旧怨和传闻更容易追问来源。",
            "collectionLabel": collection.get("label"),
            "createdAt": now_text,
            "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_COLLECTION_INFLUENCE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("collection_influences", []).append(influence)
        tribe["collection_influences"] = tribe["collection_influences"][-TRIBE_COLLECTION_INFLUENCE_LIMIT:]
        return collection, influence

    def _open_lost_item_witness_stone(self, tribe: dict, item: dict, now_text: str) -> dict:
        stone = {
            "id": f"dispute_witness_{tribe.get('id')}_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "sourceId": f"lost_item:{item.get('id')}",
            "sourceKind": "lost_item",
            "status": "active",
            "label": f"{item.get('label', '失物')}见证石",
            "sourceLabel": item.get("sourceLabel", "漂流失物"),
            "summary": f"{item.get('label', '失物')}被交给裁判，后来者可以围绕它核对来源和归属。",
            "otherTribeId": item.get("originTribeId", ""),
            "otherTribeName": item.get("originTribeName", ""),
            "progress": 0,
            "target": TRIBE_DISPUTE_WITNESS_STONE_TARGET,
            "participants": [],
            "x": float(item.get("x", 0) or 0),
            "z": float(item.get("z", 0) or 0),
            "createdAt": now_text,
            "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_DISPUTE_WITNESS_STONE_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("dispute_witness_stones", []).append(stone)
        tribe["dispute_witness_stones"] = tribe["dispute_witness_stones"][-TRIBE_DISPUTE_WITNESS_STONE_LIMIT:]
        return stone

    async def resolve_lost_item(self, player_id: str, item_id: str, action_key: str):
        actor_tribe_id = self.player_tribes.get(player_id)
        actor_tribe = self.tribes.get(actor_tribe_id)
        if not actor_tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        owner_tribe_id, owner_tribe, item = self._find_lost_item(item_id)
        if not item:
            await self._send_tribe_error(player_id, "这件失物已经漂走")
            return
        action = TRIBE_LOST_ITEM_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知失物处理方式")
            return
        now_text = datetime.now().isoformat()
        member = actor_tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        reward_parts = [] if action_key == "return" else self._apply_lost_item_reward(actor_tribe, action)
        extra = {}
        if action_key == "return":
            owner_tribe["renown"] = int(owner_tribe.get("renown", 0) or 0) + int(action.get("renown", 0) or 0)
            reward_parts.append(f"{owner_tribe.get('name', '来源部落')}声望+{int(action.get('renown', 0) or 0)}")
            if owner_tribe_id != actor_tribe_id:
                actor_tribe["trade_reputation"] = int(actor_tribe.get("trade_reputation", 0) or 0) + int(action.get("tradeReputation", 0) or 0)
                reward_parts.append(f"贸易信誉+{int(action.get('tradeReputation', 0) or 0)}")
                reward_parts.extend(self._lost_item_relation_reward(actor_tribe, owner_tribe, action))
                if hasattr(self, "_schedule_far_reply"):
                    reply = self._schedule_far_reply(
                        actor_tribe,
                        "lost_item",
                        item.get("id"),
                        "归还失物后的远方回信",
                        f"{owner_tribe.get('name', '来源部落')}收到{item.get('label', '失物')}后，可能托人带回谢意或新的请求。",
                        owner_tribe,
                        now_text
                    )
                    if reply:
                        extra["farReplyId"] = reply.get("id")
        elif action_key == "collect":
            collection, influence = self._collect_lost_item(actor_tribe, item, player_id, member_name, now_text)
            extra.update({"collection": collection, "influence": influence})
        elif action_key == "judge":
            extra["witnessStone"] = self._open_lost_item_witness_stone(actor_tribe, item, now_text)
        elif action_key == "hide":
            member["renown_stains"] = int(member.get("renown_stains", 0) or 0) + int(action.get("renownStain", 0) or 0)
            if int(action.get("renownStain", 0) or 0):
                reward_parts.append(f"名声污点+{int(action.get('renownStain', 0) or 0)}")
            pressure_parts, wake_ids = self._lost_item_hide_pressure(actor_tribe, owner_tribe, item, now_text)
            reward_parts.extend(pressure_parts)
            if wake_ids:
                extra["oldGrudgeWakeIds"] = wake_ids

        item["status"] = "hidden" if action_key == "hide" else "resolved"
        item["resolvedAt"] = now_text
        item["resolvedBy"] = player_id
        item["resolvedByName"] = member_name
        item["resolvedAction"] = action_key
        record = {
            "id": f"lost_item_record_{item.get('id')}_{int(datetime.now().timestamp() * 1000)}",
            "itemId": item.get("id"),
            "label": item.get("label", "失物"),
            "sourceKind": item.get("sourceKind"),
            "sourceId": item.get("sourceId"),
            "sourceLabel": item.get("sourceLabel", "漂流失物"),
            "sourceChain": item.get("sourceChain") or self._lost_item_source_chain(owner_tribe, None, item),
            "sourceChainLabel": " -> ".join(item.get("sourceChain") or self._lost_item_source_chain(owner_tribe, None, item)),
            "originTribeId": owner_tribe_id,
            "originTribeName": owner_tribe.get("name", "来源部落"),
            "actorTribeId": actor_tribe_id,
            "actorTribeName": actor_tribe.get("name", "部落"),
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "处理"),
            "rewardParts": reward_parts,
            "collectionReady": action_key in {"collect", "dedicate", "judge"},
            "commonJudgeReady": action_key == "hide",
            "oldGrudgeReady": bool(extra.get("oldGrudgeWakeIds")),
            "createdAt": now_text,
            **extra
        }
        for tribe in {id(owner_tribe): owner_tribe, id(actor_tribe): actor_tribe}.values():
            tribe.setdefault("lost_item_records", []).append(record)
            tribe["lost_item_records"] = tribe["lost_item_records"][-TRIBE_LOST_ITEM_RECORD_LIMIT:]
        detail = f"{member_name} 对“{item.get('label', '失物')}”选择{action.get('label', '处理')}：{'、'.join(reward_parts) or '来源被记录'}。"
        self._add_tribe_history(actor_tribe, "culture", "失物漂流", detail, player_id, {"kind": "lost_item", "record": record})
        await self._publish_world_rumor(
            "culture",
            "失物漂流",
            f"{actor_tribe.get('name', '部落')} 处理了来自{owner_tribe.get('name', '来源部落')}的{item.get('label', '失物')}：{action.get('label', '处理')}。",
            {"tribeId": actor_tribe_id, "originTribeId": owner_tribe_id, "itemId": item.get("id"), "action": action_key}
        )
        await self._notify_tribe(actor_tribe_id, detail)
        await self.broadcast_tribe_state(actor_tribe_id)
        if owner_tribe_id and owner_tribe_id != actor_tribe_id:
            await self.broadcast_tribe_state(owner_tribe_id)
