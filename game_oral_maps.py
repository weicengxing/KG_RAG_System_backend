from datetime import datetime
import random

from game_config import *


class GameOralMapMixin:
    def _public_oral_map_actions(self) -> dict:
        return TRIBE_ORAL_MAP_ACTIONS

    def _public_oral_map_records(self, tribe: dict) -> list:
        return [item for item in tribe.get("oral_map_records", []) or [] if isinstance(item, dict)][-TRIBE_ORAL_MAP_RECORD_LIMIT:]

    def _active_oral_map_lineages(self, tribe: dict) -> list:
        if not tribe:
            return []
        active = []
        now = datetime.now()
        for lineage in tribe.get("oral_map_lineages", []) or []:
            if not isinstance(lineage, dict) or lineage.get("status", "active") != "active":
                continue
            active_until = lineage.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        lineage["status"] = "expired"
                        lineage["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    lineage["status"] = "expired"
                    lineage["expiredAt"] = now.isoformat()
                    continue
            active.append(lineage)
        tribe["oral_map_lineages"] = active[-TRIBE_ORAL_MAP_LINEAGE_LIMIT:]
        return tribe["oral_map_lineages"]

    def _public_oral_map_lineages(self, tribe: dict) -> list:
        return [
            {
                "id": lineage.get("id"),
                "label": lineage.get("label", "路线讲述谱系"),
                "summary": lineage.get("summary", ""),
                "actionKey": lineage.get("actionKey"),
                "actionLabel": lineage.get("actionLabel", "口述地图"),
                "bonusKind": lineage.get("bonusKind", "route"),
                "bonusLabel": lineage.get("bonusLabel", "轻量加成"),
                "useCount": int(lineage.get("useCount", 0) or 0),
                "target": TRIBE_ORAL_MAP_LINEAGE_TARGET,
                "sourceLabels": list(lineage.get("sourceLabels", []) or []),
                "createdAt": lineage.get("createdAt"),
                "activeUntil": lineage.get("activeUntil")
            }
            for lineage in self._active_oral_map_lineages(tribe)
        ]

    def _public_oral_map_references(self, tribe: dict) -> list:
        return [
            item for item in tribe.get("oral_map_references", []) or []
            if isinstance(item, dict)
        ][-TRIBE_ORAL_MAP_REFERENCE_LIMIT:]

    def _oral_map_used_source_ids(self, tribe: dict) -> set:
        return {
            item.get("sourceId")
            for item in tribe.get("oral_map_records", []) or []
            if isinstance(item, dict) and item.get("sourceId")
        }

    def _oral_map_source(self, kind: str, source_id: str, label: str, summary: str, source_label: str, item: dict | None = None) -> dict:
        item = item or {}
        return {
            "id": source_id,
            "kind": kind,
            "sourceId": source_id,
            "label": label or source_label or "可讲述旧痕",
            "summary": summary or "成员可以把这段旧痕整理成口述地图。",
            "sourceLabel": source_label,
            "caveLabel": item.get("caveLabel") or item.get("sourceTitle") or item.get("label") or "洞穴",
            "createdAt": item.get("createdAt") or item.get("completedAt"),
            "activeUntil": item.get("activeUntil")
        }

    def _oral_map_sources(self, tribe: dict) -> list:
        if not tribe:
            return []
        used = self._oral_map_used_source_ids(tribe)
        sources = []

        def add_source(source: dict):
            source_id = source.get("sourceId")
            if not source_id or source_id in used:
                return
            if any(item.get("sourceId") == source_id for item in sources):
                return
            sources.append(source)

        for record in reversed(tribe.get("cave_return_records", []) or []):
            if not isinstance(record, dict):
                continue
            source_id = f"cave_return_record:{record.get('id')}"
            add_source(self._oral_map_source(
                "cave_return",
                source_id,
                record.get("label", "洞穴归路"),
                record.get("summary", "完成的洞穴归路可被讲成口述地图。"),
                "洞穴归路",
                record
            ))

        for bonus in reversed(self._active_cave_route_bonuses(tribe) if hasattr(self, "_active_cave_route_bonuses") else tribe.get("cave_route_bonuses", []) or []):
            if not isinstance(bonus, dict):
                continue
            source_id = f"cave_route_bonus:{bonus.get('id')}"
            add_source(self._oral_map_source(
                "cave_route_bonus",
                source_id,
                bonus.get("label", "归路经验"),
                bonus.get("summary", "尚未使用的洞穴路线经验可被转讲成口述地图。"),
                "归路经验",
                bonus
            ))

        active_markers = self._active_trail_markers(tribe) if hasattr(self, "_active_trail_markers") else []
        for marker in list(active_markers) + list(reversed(tribe.get("trail_marker_history", []) or [])):
            if not isinstance(marker, dict):
                continue
            source_id = f"trail_marker:{marker.get('id')}"
            add_source(self._oral_map_source(
                "trail_marker",
                source_id,
                marker.get("label", "活路标"),
                marker.get("interpretation") or marker.get("summary", "活路标上的解释可整理成口述地图。"),
                "活路标",
                marker
            ))

        map_memories = self._active_map_memories(tribe) if hasattr(self, "_active_map_memories") else tribe.get("map_memories", []) or []
        for memory in reversed(map_memories):
            if not isinstance(memory, dict) or memory.get("kind") not in {"night_trace", "cave_return"}:
                continue
            source_id = f"map_memory:{memory.get('id')}"
            source_label = "夜行旧痕" if memory.get("kind") == "night_trace" else "活地图归路"
            add_source(self._oral_map_source(
                memory.get("kind", "map_memory"),
                source_id,
                memory.get("label", source_label),
                memory.get("summary", "活地图记忆可被整理成口述地图。"),
                source_label,
                memory
            ))

        return sources[:TRIBE_ORAL_MAP_SOURCE_LIMIT]

    def _public_oral_map_sources(self, tribe: dict) -> list:
        return self._oral_map_sources(tribe)

    def _oral_map_lineage_bonus_kind(self, action_key: str) -> str:
        return {
            "cave_route": "rescue",
            "riddle_route": "rumor",
            "puzzle_route": "puzzle"
        }.get(action_key, "route")

    def _oral_map_lineage_bonus_label(self, action_key: str) -> str:
        return {
            "cave_route": "救援/高风险探索+1",
            "riddle_route": "传闻辨认+1",
            "puzzle_route": "共享谜图/旧事辨认+1"
        }.get(action_key, "路线讲述+1")

    def _maybe_create_oral_map_lineage(self, tribe: dict, record: dict) -> dict | None:
        action_key = record.get("actionKey")
        if not action_key:
            return None
        active = self._active_oral_map_lineages(tribe)
        if any(item.get("actionKey") == action_key for item in active):
            return None
        records = [
            item for item in tribe.get("oral_map_records", []) or []
            if isinstance(item, dict) and item.get("actionKey") == action_key
        ][-TRIBE_ORAL_MAP_LINEAGE_TARGET:]
        if len(records) < TRIBE_ORAL_MAP_LINEAGE_TARGET:
            return None
        action = TRIBE_ORAL_MAP_ACTIONS.get(action_key, {})
        source_labels = []
        for item in records:
            label = item.get("sourceLabel") or item.get("sourceKind") or "旧痕"
            if label and label not in source_labels:
                source_labels.append(label)
        now = datetime.now()
        lineage = {
            "id": f"oral_map_lineage_{tribe.get('id')}_{action_key}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "actionKey": action_key,
            "actionLabel": action.get("label", "口述地图"),
            "label": f"{action.get('label', '口述地图')}谱系",
            "summary": f"{action.get('label', '口述地图')}已经被多次讲述，形成短时路线讲述谱系，后续救援、试探或辨认会引用这条来历。",
            "bonusKind": self._oral_map_lineage_bonus_kind(action_key),
            "bonusLabel": self._oral_map_lineage_bonus_label(action_key),
            "useCount": len(records),
            "sourceLabels": source_labels,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_ORAL_MAP_LINEAGE_BONUS_MINUTES * 60).isoformat()
        }
        tribe["oral_map_lineages"] = [*active, lineage][-TRIBE_ORAL_MAP_LINEAGE_LIMIT:]
        return lineage

    def _maybe_create_oral_map_lineage_from_references(self, tribe: dict, action_key: str) -> dict | None:
        if not action_key:
            return None
        active = self._active_oral_map_lineages(tribe)
        if any(item.get("actionKey") == action_key for item in active):
            return None
        refs = [
            item for item in tribe.get("oral_map_references", []) or []
            if isinstance(item, dict) and item.get("actionKey") == action_key
        ][-TRIBE_ORAL_MAP_LINEAGE_TARGET:]
        if len(refs) < TRIBE_ORAL_MAP_LINEAGE_TARGET:
            return None
        action = TRIBE_ORAL_MAP_ACTIONS.get(action_key, {})
        source_labels = []
        for ref in refs:
            label = ref.get("contextLabel") or ref.get("sourceLabel") or ref.get("actionLabel")
            if label and label not in source_labels:
                source_labels.append(label)
        now = datetime.now()
        lineage = {
            "id": f"oral_map_lineage_{tribe.get('id')}_{action_key}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "actionKey": action_key,
            "actionLabel": action.get("label", "口述地图"),
            "label": f"{action.get('label', '口述地图')}引用谱系",
            "summary": f"{action.get('label', '口述地图')}被洞穴、禁地或传闻多次引用，后来者开始按这条来历判断路线。",
            "bonusKind": self._oral_map_lineage_bonus_kind(action_key),
            "bonusLabel": self._oral_map_lineage_bonus_label(action_key),
            "useCount": len(refs),
            "sourceLabels": source_labels,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_ORAL_MAP_LINEAGE_BONUS_MINUTES * 60).isoformat()
        }
        tribe["oral_map_lineages"] = [*active, lineage][-TRIBE_ORAL_MAP_LINEAGE_LIMIT:]
        return lineage

    def _oral_map_lineage_for_kind(self, tribe: dict, bonus_kind: str) -> dict | None:
        for lineage in reversed(self._active_oral_map_lineages(tribe)):
            if lineage.get("bonusKind") == bonus_kind:
                return lineage
        return None

    def _oral_map_context_action_keys(self, context_key: str) -> list:
        if context_key in {"cave_race", "cave_rescue", "forbidden_edge"}:
            return ["cave_route", "riddle_route", "puzzle_route"]
        if context_key == "rumor_truth":
            return ["riddle_route", "puzzle_route", "cave_route"]
        return ["cave_route", "riddle_route", "puzzle_route"]

    def _oral_map_record_for_context(self, tribe: dict, context_key: str) -> dict | None:
        action_keys = self._oral_map_context_action_keys(context_key)
        for action_key in action_keys:
            for record in reversed(tribe.get("oral_map_records", []) or []):
                if isinstance(record, dict) and record.get("actionKey") == action_key:
                    return record
        return None

    def _oral_map_lineage_for_context(self, tribe: dict, context_key: str) -> dict | None:
        if context_key in {"cave_race", "cave_rescue", "forbidden_edge"}:
            return self._oral_map_lineage_for_kind(tribe, "rescue")
        if context_key == "rumor_truth":
            return self._oral_map_lineage_for_kind(tribe, "rumor") or self._oral_map_lineage_for_kind(tribe, "puzzle")
        return None

    def _oral_map_context_support(self, tribe: dict, context_key: str) -> tuple[int, list, dict | None, dict | None]:
        labels = []
        bonus = 0
        record = self._oral_map_record_for_context(tribe, context_key)
        if record:
            labels.append(record.get("actionLabel", "口述地图"))
            bonus += 1
        lineage = self._oral_map_lineage_for_context(tribe, context_key)
        if lineage:
            labels.append(lineage.get("label", "路线讲述谱系"))
            bonus += 1
        return bonus, labels, record, lineage

    def _record_oral_map_context_reference(self, tribe: dict, context_key: str, context_label: str, member_name: str, outcome_label: str = "") -> tuple[dict | None, dict | None]:
        record = self._oral_map_record_for_context(tribe, context_key)
        if not record:
            return None, None
        now = datetime.now()
        reference = {
            "id": f"oral_map_ref_{tribe.get('id')}_{context_key}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "oralMapRecordId": record.get("id"),
            "actionKey": record.get("actionKey"),
            "actionLabel": record.get("actionLabel", "口述地图"),
            "sourceLabel": record.get("sourceLabel", "归路旧痕"),
            "contextKey": context_key,
            "contextLabel": context_label,
            "memberName": member_name,
            "outcomeLabel": outcome_label,
            "createdAt": now.isoformat()
        }
        tribe.setdefault("oral_map_references", []).append(reference)
        tribe["oral_map_references"] = tribe["oral_map_references"][-TRIBE_ORAL_MAP_REFERENCE_LIMIT:]
        record["referenceCount"] = int(record.get("referenceCount", 0) or 0) + 1
        lineage = self._maybe_create_oral_map_lineage_from_references(tribe, record.get("actionKey", ""))
        if lineage:
            reference["lineageCreated"] = lineage
        return reference, lineage

    def _oral_map_lineage_rescue_bonus(self, tribe: dict) -> tuple[int, dict, str]:
        lineage = self._oral_map_lineage_for_kind(tribe, "rescue")
        if not lineage:
            return 0, {}, ""
        return 1, {"discoveryProgress": 1}, lineage.get("label", "路线讲述谱系")

    def _oral_map_lineage_forbidden_bonus(self, tribe: dict) -> tuple[int, str]:
        lineage = self._oral_map_lineage_for_kind(tribe, "rescue")
        if not lineage:
            return 0, ""
        return 1, lineage.get("label", "路线讲述谱系")

    def _oral_map_lineage_rumor_source(self, tribe: dict) -> dict | None:
        lineage = self._oral_map_lineage_for_kind(tribe, "rumor") or self._oral_map_lineage_for_kind(tribe, "puzzle")
        if not lineage:
            return None
        return {
            "sourceId": f"oral_map_lineage:{lineage.get('id')}",
            "sourceKind": "oral_map_lineage",
            "sourceLabel": "路线讲述谱系",
            "title": lineage.get("label", "路线讲述谱系"),
            "summary": lineage.get("summary", "这条路线讲述已经被多人复述，适合拿来辨认传闻和旧事。")
        }

    def _oral_map_lineage_rumor_bonus(self, tribe: dict) -> tuple[int, str]:
        lineage = self._oral_map_lineage_for_kind(tribe, "rumor") or self._oral_map_lineage_for_kind(tribe, "puzzle")
        if not lineage:
            return 0, ""
        return 1, lineage.get("label", "路线讲述谱系")

    def _apply_oral_map_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("tradeReputation", "贸易信誉", "trade_reputation")
        ):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        return parts

    def _create_oral_map_cave_bonus(self, tribe: dict, source: dict, action: dict, member_name: str) -> dict:
        now = datetime.now()
        bonus = {
            "id": f"oral_map_cave_bonus_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "label": "口述归路图",
            "summary": f"{member_name}把{source.get('label', '旧痕')}讲成可照走的口述地图，下一次洞穴远征更稳。",
            "caveLabel": source.get("caveLabel", "洞穴"),
            "findsBonus": max(0, int(action.get("findsBonus", 1) or 0)),
            "foodReduction": max(0, int(action.get("foodReduction", 0) or 0)),
            "sourceActionKey": action.get("key", "cave_route"),
            "sourceActionLabel": action.get("label", "讲成洞穴归路"),
            "createdAt": now.isoformat()
        }
        bonuses = self._active_cave_route_bonuses(tribe) if hasattr(self, "_active_cave_route_bonuses") else tribe.get("cave_route_bonuses", []) or []
        tribe["cave_route_bonuses"] = [*bonuses, bonus][-TRIBE_CAVE_RETURN_MARK_RECORD_LIMIT:]
        return bonus

    def _create_oral_map_riddle_influence(self, tribe: dict, source: dict, action: dict, member_name: str) -> dict:
        now = datetime.now()
        influence = {
            "id": f"oral_map_riddle_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "kind": action.get("influenceKind", "rare_ruin"),
            "label": action.get("influenceLabel", "口述地图牵引"),
            "summary": f"{member_name}把{source.get('label', '旧痕')}讲成石影规律，下一轮相关世界谜语和稀有遗迹更容易被牵引。",
            "sourceTitle": source.get("label", "口述地图"),
            "createdByName": member_name,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_ORAL_MAP_ACTIVE_MINUTES * 60).isoformat()
        }
        active = self._active_world_riddle_influences(tribe) if hasattr(self, "_active_world_riddle_influences") else tribe.get("world_riddle_influences", []) or []
        tribe["world_riddle_influences"] = [*active, influence][-TRIBE_WORLD_RIDDLE_INFLUENCE_LIMIT:]
        return influence

    def _create_oral_map_puzzle_fragment(self, tribe: dict, source: dict, action: dict, member_name: str) -> tuple[dict | None, list, bool]:
        source_key = action.get("puzzleSourceKey", "cave")
        fragments = tribe.setdefault("shared_puzzle_fragments", [])
        if any(item.get("sourceKey") == source_key for item in fragments if isinstance(item, dict)):
            return None, [], True
        config = TRIBE_SHARED_PUZZLE_SOURCES.get(source_key, {})
        reward_parts = self._apply_shared_puzzle_reward(tribe, config.get("reward", {})) if hasattr(self, "_apply_shared_puzzle_reward") else []
        fragment = {
            "id": f"puzzle_fragment_{tribe.get('id')}_oral_map_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "sourceKey": source_key,
            "sourceLabel": config.get("label", "洞穴碎片"),
            "summary": f"{source.get('label', '口述地图')}被抄成洞纹，补进共享谜图。",
            "memberName": member_name,
            "rewardParts": reward_parts,
            "oralMapSourceId": source.get("sourceId"),
            "createdAt": datetime.now().isoformat()
        }
        fragments.append(fragment)
        tribe["shared_puzzle_fragments"] = fragments[-TRIBE_SHARED_PUZZLE_TARGET:]
        return fragment, reward_parts, False

    async def compose_oral_map(self, player_id: str, source_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_ORAL_MAP_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知口述地图整理方式")
            return
        source = next((item for item in self._oral_map_sources(tribe) if item.get("sourceId") == source_id), None)
        if not source:
            await self._send_tribe_error(player_id, "这段旧痕已经不能整理成口述地图")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name") or self._get_player_name(player_id)
        reward_parts = self._apply_oral_map_reward(tribe, action.get("reward", {}))
        route_bonus = None
        influence = None
        puzzle_fragment = None
        puzzle_already_recorded = False

        if action_key == "cave_route":
            route_bonus = self._create_oral_map_cave_bonus(tribe, source, action, member_name)
            reward_parts.append(f"{route_bonus.get('label', '口述归路图')}生效")
        elif action_key == "riddle_route":
            influence = self._create_oral_map_riddle_influence(tribe, source, action, member_name)
            reward_parts.append(influence.get("label", "谜语牵引"))
        elif action_key == "puzzle_route":
            puzzle_fragment, puzzle_parts, puzzle_already_recorded = self._create_oral_map_puzzle_fragment(tribe, source, action, member_name)
            reward_parts.extend(puzzle_parts)
            reward_parts.append("洞穴碎片已存在" if puzzle_already_recorded else "共享谜图+洞穴碎片")

        now = datetime.now()
        record = {
            "id": f"oral_map_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "sourceId": source.get("sourceId"),
            "sourceKind": source.get("kind"),
            "sourceLabel": source.get("label"),
            "actionKey": action_key,
            "actionLabel": action.get("label", "整理口述地图"),
            "summary": f"{member_name}把{source.get('sourceLabel', '旧痕')}“{source.get('label', '路线')}”整理成口述地图。",
            "memberName": member_name,
            "rewardParts": reward_parts,
            "routeBonus": route_bonus,
            "riddleInfluence": influence,
            "puzzleFragmentCreated": bool(puzzle_fragment),
            "puzzleAlreadyRecorded": puzzle_already_recorded,
            "createdAt": now.isoformat()
        }
        tribe.setdefault("oral_map_records", []).append(record)
        tribe["oral_map_records"] = tribe["oral_map_records"][-TRIBE_ORAL_MAP_RECORD_LIMIT:]
        lineage = self._maybe_create_oral_map_lineage(tribe, record)
        if lineage:
            record["lineageCreated"] = lineage

        detail = f"{member_name}整理口述地图：{source.get('label', '旧痕')} -> {action.get('label', '整理')}。"
        if reward_parts:
            detail += f" 收获：{'、'.join(reward_parts)}。"
        if lineage:
            detail += f" 形成了{lineage.get('label', '路线讲述谱系')}。"
        self._add_tribe_history(tribe, "cave", "归路口述地图", detail, player_id, {"kind": "oral_map", "record": record})
        await self._publish_world_rumor(
            "cave",
            "归路被讲成口述地图",
            f"{tribe.get('name', '部落')}把洞穴归路、路标和夜行旧痕讲成了可传给后来者的地图。",
            {"tribeId": tribe_id, "recordId": record.get("id")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
