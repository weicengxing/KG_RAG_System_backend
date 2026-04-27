from datetime import datetime

from game_config import *


class GameCollectionWallMixin:
    def _collection_source_keys(self, tribe: dict) -> set:
        return {
            item.get("sourceKey")
            for item in (tribe.get("collection_wall", []) or [])
            if isinstance(item, dict) and item.get("sourceKey")
        }

    def _collection_candidate(self, tribe: dict, source_kind: str, source_id: str, label: str, summary: str, source_label: str, extra: dict | None = None) -> dict | None:
        if not source_id:
            return None
        source_key = f"{source_kind}:{source_id}"
        if source_key in self._collection_source_keys(tribe):
            return None
        return {
            "id": f"collection_candidate_{source_kind}_{source_id}".replace(" ", "_"),
            "sourceKind": source_kind,
            "sourceId": source_id,
            "sourceKey": source_key,
            "label": label or source_label or "可收藏旧物",
            "summary": summary or "这段来源可以整理成部落收藏。",
            "sourceLabel": source_label or "旧物来源",
            **(extra or {})
        }

    def _collection_wall_candidates(self, tribe: dict) -> list:
        if not tribe:
            return []
        candidates = []

        for record in reversed(tribe.get("far_reply_records", []) or []):
            if not isinstance(record, dict):
                continue
            item = self._collection_candidate(
                tribe,
                "far_reply",
                record.get("id", ""),
                record.get("outcomeLabel") or record.get("title") or "远方回信",
                f"{record.get('sourceLabel', '远方口信')}经由{record.get('memberName', '成员')}回应，仍可挂成外交旧痕。",
                "远方回信",
                {"rewardParts": record.get("rewardParts", []), "otherTribeName": record.get("otherTribeName", "")}
            )
            if item:
                candidates.append(item)

        for token in reversed(tribe.get("personal_tokens", []) or []):
            if not isinstance(token, dict) or token.get("status") not in {"redeemed", "debt_settled"}:
                continue
            item = self._collection_candidate(
                tribe,
                "personal_token",
                token.get("id", ""),
                token.get("label", "个人信物"),
                f"{token.get('issuerName', '成员')} 给 {token.get('targetName', '本部落')} 的承诺已经留下结果。",
                "个人信物",
                {"rewardParts": token.get("rewardParts", []), "memberName": token.get("issuerName", "")}
            )
            if item:
                candidates.append(item)

        for effect in reversed(tribe.get("nomad_visitor_aftereffects", []) or []):
            if not isinstance(effect, dict):
                continue
            item = self._collection_candidate(
                tribe,
                "visitor_aftereffect",
                effect.get("id", ""),
                effect.get("label", "来访余音"),
                effect.get("summary", "来访者留下的口信可以整理成收藏。"),
                "来访余音",
                {"rewardParts": effect.get("rewardParts", []), "visitorLabel": effect.get("visitorLabel", "")}
            )
            if item:
                candidates.append(item)

        for marker in reversed(tribe.get("trail_marker_history", []) or []):
            if not isinstance(marker, dict):
                continue
            item = self._collection_candidate(
                tribe,
                "trail_marker",
                marker.get("id", ""),
                marker.get("label", "活路标碎片"),
                marker.get("interpretation") or marker.get("summary") or "撤下的路标碎片仍保留着改写痕迹。",
                "活路标碎片",
                {"editCount": len(marker.get("edits", []) or []), "memberName": marker.get("createdByName", "")}
            )
            if item:
                candidates.append(item)

        for fact in reversed(tribe.get("accepted_history_facts", []) or []):
            if not isinstance(fact, dict):
                continue
            item = self._collection_candidate(
                tribe,
                "history_fact",
                fact.get("id", ""),
                fact.get("title") or fact.get("versionLabel") or "历史事实拓片",
                fact.get("summary") or fact.get("detail") or "已经定稿的历史事实可以被拓成收藏。",
                "历史事实",
                {"memberName": fact.get("acceptedByName", "")}
            )
            if item:
                candidates.append(item)

        for record in reversed(tribe.get("old_camp_records", []) or []):
            if not isinstance(record, dict) or not record.get("collectionReady"):
                continue
            item = self._collection_candidate(
                tribe,
                "old_camp_echo",
                record.get("id", ""),
                record.get("label", "回归旧营旧物"),
                f"{record.get('memberName', '成员')} 在{record.get('sourceLabel', '旧营旧场')}完成{record.get('actionLabel', '带回旧物')}，这件旧物仍带着回归旧营的灰痕。",
                record.get("sourceLabel", "回归旧营"),
                {"rewardParts": record.get("rewardParts", []), "memberName": record.get("memberName", "")}
            )
            if item:
                candidates.append(item)

        for echo_item in reversed(tribe.get("echo_items", []) or []):
            if not isinstance(echo_item, dict) or len(echo_item.get("memories", []) or []) < 2:
                continue
            memory_labels = "、".join(memory.get("experienceLabel", "经历") for memory in (echo_item.get("memories", []) or [])[-3:] if isinstance(memory, dict))
            item = self._collection_candidate(
                tribe,
                "echo_item",
                echo_item.get("id", ""),
                echo_item.get("label", "回声物品"),
                f"{echo_item.get('holderName', '成员')} 手中的{echo_item.get('label', '回声物品')}已经留下{memory_labels or '多段经历'}，可以挂上收藏墙保留来历。",
                "回声物品",
                {"memberName": echo_item.get("holderName", ""), "memoryCount": len(echo_item.get("memories", []) or [])}
            )
            if item:
                candidates.append(item)

        return candidates[:TRIBE_COLLECTION_CANDIDATE_LIMIT]

    def _public_collection_wall(self, tribe: dict) -> list:
        return list(tribe.get("collection_wall", []) or [])[-TRIBE_COLLECTION_WALL_LIMIT:]

    def _active_collection_influences(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for item in tribe.get("collection_influences", []) or []:
            if not isinstance(item, dict):
                continue
            active_until = item.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    continue
            active.append(item)
        if len(active) != len(tribe.get("collection_influences", []) or []):
            tribe["collection_influences"] = active[-TRIBE_COLLECTION_INFLUENCE_LIMIT:]
        return active[-TRIBE_COLLECTION_INFLUENCE_LIMIT:]

    def _apply_collection_reward(self, tribe: dict, action: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            amount = int(action.get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        return parts

    async def curate_collection_wall_item(self, player_id: str, candidate_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        candidate = next((
            item for item in self._collection_wall_candidates(tribe)
            if isinstance(item, dict) and item.get("id") == candidate_id
        ), None)
        if not candidate:
            await self._send_tribe_error(player_id, "没有找到可整理的收藏来源")
            return
        action = TRIBE_COLLECTION_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知收藏整理方式")
            return

        now = datetime.now()
        now_text = now.isoformat()
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        reward_parts = self._apply_collection_reward(tribe, action)
        collection = {
            "id": f"collection_{tribe_id}_{int(now.timestamp() * 1000)}",
            "sourceKey": candidate.get("sourceKey"),
            "sourceKind": candidate.get("sourceKind"),
            "sourceLabel": candidate.get("sourceLabel"),
            "sourceId": candidate.get("sourceId"),
            "label": candidate.get("label", "隐秘收藏"),
            "displayLabel": action.get("label", "整理收藏"),
            "summary": candidate.get("summary", ""),
            "curatorId": player_id,
            "curatorName": member_name,
            "rewardParts": reward_parts,
            "createdAt": now_text
        }
        tribe.setdefault("collection_wall", []).append(collection)
        tribe["collection_wall"] = tribe["collection_wall"][-TRIBE_COLLECTION_WALL_LIMIT:]

        influence = {
            "id": f"collection_influence_{collection['id']}",
            "sourceKind": candidate.get("sourceKind"),
            "label": action.get("influenceLabel", "收藏余韵"),
            "summary": action.get("influenceSummary", "后续传闻会引用这段收藏。"),
            "collectionLabel": collection.get("label"),
            "createdAt": now_text,
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_COLLECTION_INFLUENCE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("collection_influences", []).append(influence)
        tribe["collection_influences"] = tribe["collection_influences"][-TRIBE_COLLECTION_INFLUENCE_LIMIT:]

        detail = f"{member_name} 把“{collection.get('label', '旧物')}”整理成{action.get('label', '收藏')}：{'、'.join(reward_parts) or '收藏墙新增一段来源'}。"
        self._add_tribe_history(tribe, "culture", "隐秘收藏墙", detail, player_id, {"kind": "collection_wall", "collection": collection, "influence": influence})
        await self._publish_world_rumor(
            "culture",
            "隐秘收藏墙",
            f"{tribe.get('name', '部落')} 把一段{candidate.get('sourceLabel', '旧事')}挂上收藏墙，后来者开始用它解释新的传闻。",
            {"tribeId": tribe_id, "collectionId": collection.get("id"), "sourceKind": candidate.get("sourceKind")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
