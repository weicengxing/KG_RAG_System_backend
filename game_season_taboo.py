from datetime import datetime

from game_config import *


class GameSeasonTabooMixin:
    def _merge_season_taboo_rewards(self, base: dict | None, bonus: dict | None) -> dict:
        merged = dict(base or {})
        for key, value in (bonus or {}).items():
            merged[key] = int(merged.get(key, 0) or 0) + int(value or 0)
        return merged

    def _season_taboo_context_sources(self, tribe: dict) -> dict:
        memories = self._active_map_memories(tribe) if hasattr(self, "_active_map_memories") else []
        claims = self._active_myth_claim_records(tribe) if hasattr(self, "_active_myth_claim_records") else []
        myths = list(tribe.get("dominant_myths", []) or [])[-TRIBE_DOMINANT_MYTH_LIMIT:]
        return {
            "memories": [item for item in memories if isinstance(item, dict)],
            "claims": [item for item in claims if isinstance(item, dict)],
            "myths": [item for item in myths if isinstance(item, dict)]
        }

    def _season_taboo_context_match(self, context: dict, sources: dict) -> dict | None:
        memory_kinds = set(context.get("memoryKinds", []) or [])
        myth_kinds = set(context.get("mythSourceKinds", []) or [])
        interpretation_keys = set(context.get("interpretationKeys", []) or [])
        keywords = [str(item).lower() for item in (context.get("sourceKeywords", []) or []) if item]
        for memory in sources.get("memories", []):
            text = f"{memory.get('label', '')} {memory.get('summary', '')} {memory.get('sourceId', '')}".lower()
            if memory.get("kind") in memory_kinds or any(keyword in text for keyword in keywords):
                return memory
        for claim in sources.get("claims", []):
            text = f"{claim.get('sourceLabel', '')} {claim.get('summary', '')} {claim.get('sourceKind', '')}".lower()
            if claim.get("sourceKind") in myth_kinds or any(keyword in text for keyword in keywords):
                return claim
        for myth in sources.get("myths", []):
            text = f"{myth.get('sourceLabel', '')} {myth.get('summary', '')} {myth.get('interpretationLabel', '')}".lower()
            if myth.get("interpretationKey") in interpretation_keys or any(keyword in text for keyword in keywords):
                return myth
        return None

    def _season_taboo_context_for_key(self, tribe: dict, taboo_key: str) -> dict | None:
        weather_context = self._weather_temper_taboo_context(tribe, taboo_key) if hasattr(self, "_weather_temper_taboo_context") else None
        if weather_context:
            return weather_context
        sources = self._season_taboo_context_sources(tribe)
        for context_key, context in TRIBE_SEASON_TABOO_CONTEXTS.items():
            if context.get("tabooKey") != taboo_key:
                continue
            source = self._season_taboo_context_match(context, sources)
            if not source:
                continue
            source_x = source.get("x", 0)
            source_z = source.get("z", 0)
            camp_center = (tribe.get("camp") or {}).get("center") or {}
            return {
                "key": context_key,
                "label": context.get("label", "季节联动"),
                "summary": context.get("summary", ""),
                "sourceLabel": source.get("label") or source.get("sourceLabel") or context.get("label", "旧痕"),
                "sourceKind": source.get("kind") or source.get("sourceKind") or "",
                "sourceId": source.get("id") or source.get("sourceId") or "",
                "x": float(source_x if source_x is not None else camp_center.get("x", 0) or 0),
                "z": float(source_z if source_z is not None else camp_center.get("z", 0) or 0),
                "observeReward": dict(context.get("observeReward", {}) or {}),
                "blessing": dict(context.get("blessing", {}) or {}),
                "mythSummary": context.get("mythSummary", "")
            }
        return None

    def _public_season_taboo_options(self, tribe: dict) -> dict:
        options = {}
        for taboo_key, config in TRIBE_SEASON_TABOO_OPTIONS.items():
            option = dict(config)
            context = self._season_taboo_context_for_key(tribe, taboo_key)
            if context:
                observe_reward = self._merge_season_taboo_rewards(config.get("observeReward", {}), context.get("observeReward", {}))
                blessing = self._merge_season_taboo_rewards(config.get("blessing", {}), context.get("blessing", {}))
                option["contextLabel"] = context.get("label")
                option["contextSummary"] = context.get("summary")
                option["contextSourceLabel"] = context.get("sourceLabel")
                option["contextRewardLabel"] = self._reward_summary_text(self._merge_season_taboo_rewards(observe_reward, blessing))
            options[taboo_key] = option
        return options

    def _active_season_taboo(self, tribe: dict) -> dict | None:
        taboo = tribe.get("season_taboo")
        if not isinstance(taboo, dict) or taboo.get("status") != "active":
            return None
        try:
            if datetime.fromisoformat(taboo.get("activeUntil", "")) <= datetime.now():
                taboo["status"] = "expired"
                taboo["expiredAt"] = datetime.now().isoformat()
                return None
        except (TypeError, ValueError):
            taboo["status"] = "expired"
            taboo["expiredAt"] = datetime.now().isoformat()
            return None
        return taboo

    def _public_season_taboo(self, tribe: dict) -> dict | None:
        taboo = self._active_season_taboo(tribe)
        if not taboo:
            return None
        config = TRIBE_SEASON_TABOO_OPTIONS.get(taboo.get("key"), {})
        temptation_options = self._season_taboo_temptation_options(taboo, config)
        return {
            "id": taboo.get("id"),
            "key": taboo.get("key"),
            "label": taboo.get("label") or config.get("label", "季节禁忌"),
            "summary": taboo.get("summary") or config.get("summary", ""),
            "contextLabel": (taboo.get("context") or {}).get("label", ""),
            "contextSummary": (taboo.get("context") or {}).get("summary", ""),
            "contextSourceLabel": (taboo.get("context") or {}).get("sourceLabel", ""),
            "contextRewardLabel": taboo.get("contextRewardLabel", ""),
            "observeLabel": config.get("observeLabel", "践行禁忌"),
            "breakLabel": config.get("breakLabel", "破戒取急用"),
            "temptationOptions": temptation_options,
            "progress": int(taboo.get("progress", 0) or 0),
            "target": int(taboo.get("target", TRIBE_SEASON_TABOO_PROGRESS_TARGET) or TRIBE_SEASON_TABOO_PROGRESS_TARGET),
            "observerNames": list(taboo.get("observerNames", []) or [])[-4:],
            "blessed": bool(taboo.get("blessed")),
            "broken": bool(taboo.get("broken")),
            "createdAt": taboo.get("createdAt"),
            "activeUntil": taboo.get("activeUntil")
        }

    def _reward_summary_text(self, reward: dict | None) -> str:
        labels = {
            "wood": "木材",
            "stone": "石块",
            "food": "食物",
            "renown": "声望",
            "renownReward": "声望",
            "discoveryProgress": "发现",
            "discoveryReward": "发现",
            "tradeReputation": "贸易",
            "tradeReward": "贸易",
            "pressureRelief": "战争压力缓解",
            "warPressureRelief": "战争压力缓解"
        }
        parts = []
        for key, label in labels.items():
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                parts.append(f"{label}+{value}")
        return "、".join(parts)

    def _season_taboo_temptation_options(self, taboo: dict, config: dict) -> list[dict]:
        options = []
        for item in config.get("temptations", []) or []:
            if not isinstance(item, dict):
                continue
            reward = dict(item.get("reward", {}) or {})
            options.append({
                "key": item.get("key"),
                "label": item.get("label") or config.get("breakLabel", "破戒取急用"),
                "summary": item.get("summary") or config.get("breakSummary", ""),
                "rewardLabel": self._reward_summary_text(reward),
                "evidenceLabel": item.get("evidenceLabel") or item.get("label") or "破戒证据",
                "lawHint": "可能触发律令补救" if item.get("lawEventKey") else ""
            })
        if options:
            return options
        reward = dict(config.get("breakReward", {}) or {})
        return [{
            "key": "default",
            "label": config.get("breakLabel", "破戒取急用"),
            "summary": config.get("breakSummary", ""),
            "rewardLabel": self._reward_summary_text(reward),
            "evidenceLabel": "破戒证据"
        }]

    def _public_season_taboo_remedies(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("season_taboo_remedies", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-TRIBE_SEASON_ATONEMENT_TASK_LIMIT:]

    def _public_season_taboo_evidence(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for item in tribe.get("season_taboo_evidence", []) or []:
            if not isinstance(item, dict):
                continue
            if not self._active_until_still_valid(item, now):
                item["status"] = "expired"
                item["expiredAt"] = now.isoformat()
                continue
            active.append({
                "id": item.get("id"),
                "tabooId": item.get("tabooId", ""),
                "tabooLabel": item.get("tabooLabel", "季节禁忌"),
                "label": item.get("label", "破戒证据"),
                "summary": item.get("summary", ""),
                "status": item.get("status", "active"),
                "actorName": item.get("actorName", ""),
                "rewardLabel": item.get("rewardLabel", ""),
                "lawHint": item.get("lawHint", ""),
                "commonJudgeHint": item.get("commonJudgeHint", ""),
                "mythClaimId": item.get("mythClaimId", ""),
                "otherTribeId": item.get("otherTribeId", ""),
                "otherTribeName": item.get("otherTribeName", ""),
                "oldGrudgeHint": item.get("oldGrudgeHint", ""),
                "oldGrudgeWakeTaskId": item.get("oldGrudgeWakeTaskId", ""),
                "judgedByName": item.get("judgedByName", ""),
                "remediedByName": item.get("remediedByName", ""),
                "createdAt": item.get("createdAt"),
                "activeUntil": item.get("activeUntil")
            })
        tribe["season_taboo_evidence"] = [
            item for item in (tribe.get("season_taboo_evidence", []) or [])
            if isinstance(item, dict) and item.get("status") != "expired"
        ][-TRIBE_SEASON_TABOO_EVIDENCE_LIMIT:]
        return active[-TRIBE_SEASON_TABOO_EVIDENCE_LIMIT:]

    def _public_atonement_tokens(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for token in tribe.get("atonement_tokens", []) or []:
            if not isinstance(token, dict) or token.get("status") == "expired":
                continue
            active_until = token.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        token["status"] = "expired"
                        token["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    token["status"] = "expired"
                    token["expiredAt"] = now.isoformat()
                    continue
            active.append({
                "id": token.get("id"),
                "status": token.get("status", "acknowledged"),
                "kind": token.get("kind", "atonement_token"),
                "title": token.get("title", "赎罪信物"),
                "summary": token.get("summary", ""),
                "sourceKind": token.get("sourceKind", ""),
                "sourceLabel": token.get("sourceLabel", ""),
                "otherTribeId": token.get("otherTribeId", ""),
                "otherTribeName": token.get("otherTribeName", ""),
                "createdByName": token.get("createdByName", ""),
                "messengerReady": bool(token.get("messengerReady")),
                "messengerTaskIds": list(token.get("messengerTaskIds", []) or []),
                "redeemedByName": token.get("redeemedByName", ""),
                "outcomeLabel": token.get("outcomeLabel", ""),
                "createdAt": token.get("createdAt"),
                "activeUntil": token.get("activeUntil")
            })
        tribe["atonement_tokens"] = [
            item for item in (tribe.get("atonement_tokens", []) or [])
            if isinstance(item, dict) and item.get("status") != "expired"
        ][-TRIBE_ATONEMENT_TOKEN_LIMIT:]
        return active[-TRIBE_ATONEMENT_TOKEN_LIMIT:]

    def _create_atonement_token_from_remedy(self, tribe: dict, remedy: dict, player_id: str, member_name: str) -> dict | None:
        if not tribe or not remedy:
            return None
        now = datetime.now()
        other_tribe_id = remedy.get("otherTribeId", "")
        other_tribe = self.tribes.get(other_tribe_id) if other_tribe_id else None
        active_until = datetime.fromtimestamp(
            now.timestamp() + TRIBE_ATONEMENT_TOKEN_ACTIVE_MINUTES * 60
        ).isoformat()
        token = {
            "id": f"atonement_token_{tribe.get('id')}_{int(now.timestamp() * 1000)}",
            "status": "pending_messenger" if other_tribe else "acknowledged",
            "kind": "atonement_token",
            "sourceKind": remedy.get("sourceKind", ""),
            "sourceLabel": remedy.get("sourceLabel", ""),
            "sourceRemedyId": remedy.get("id", ""),
            "title": "赎罪信物" if other_tribe else "旧痕承认",
            "summary": (
                f"{member_name} 已完成{remedy.get('title', '公开赎罪')}，这件信物可以交给 {other_tribe.get('name', '邻近部落')} 护送承认。"
                if other_tribe else
                f"{member_name} 已完成{remedy.get('title', '公开赎罪')}，部落把{remedy.get('sourceLabel', '旧事')}记成可回看的旧痕承认。"
            ),
            "otherTribeId": other_tribe_id,
            "otherTribeName": other_tribe.get("name", remedy.get("otherTribeName", "")) if other_tribe else remedy.get("otherTribeName", ""),
            "createdBy": player_id,
            "createdByName": member_name,
            "createdAt": now.isoformat(),
            "activeUntil": active_until,
            "messengerReady": bool(other_tribe),
            "messengerTaskIds": []
        }
        tribe.setdefault("atonement_tokens", []).append(token)
        tribe["atonement_tokens"] = tribe["atonement_tokens"][-TRIBE_ATONEMENT_TOKEN_LIMIT:]
        if other_tribe and hasattr(self, "_open_covenant_messenger_task_pair"):
            tasks = self._open_covenant_messenger_task_pair(
                tribe,
                other_tribe,
                "atonement_token",
                token["id"],
                "护送赎罪信物",
                f"{tribe.get('name', '部落')} 已完成公开赎罪，需要成员把信物送到 {other_tribe.get('name', '邻近部落')}，让赔礼从结算变成可见承认。",
                token["createdAt"]
            )
            token["messengerTaskIds"] = [item.get("id") for item in tasks if isinstance(item, dict) and item.get("id")]
        return token

    def _season_atonement_profile_key(self, tribe: dict, source_kind: str) -> str:
        if source_kind in ("betrayal", "truce_grievance"):
            return source_kind
        active_memories = self._active_map_memories(tribe) if hasattr(self, "_active_map_memories") else []
        if active_memories:
            return "memory"
        if tribe.get("standing_ritual") or tribe.get("standing_ritual_history"):
            return "ritual"
        return "taboo_break"

    def _open_tribe_atonement_task(self, tribe: dict, source_kind: str, source_label: str, player_id: str = "", other_tribe_id: str = "", other_tribe_name: str = "", source_id: str = "") -> dict | None:
        if not tribe:
            return None
        profile_key = self._season_atonement_profile_key(tribe, source_kind)
        profile = dict(TRIBE_SEASON_ATONEMENT_TASKS.get(profile_key, TRIBE_SEASON_ATONEMENT_TASKS["taboo_break"]))
        dedupe_id = f"atonement:{source_kind}:{source_id or other_tribe_id or profile_key}"
        pending = [
            item for item in (tribe.get("season_taboo_remedies", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ]
        if any(item.get("dedupeId") == dedupe_id for item in pending):
            return None
        now_text = datetime.now().isoformat()
        source_text = source_label or "旧事"
        if other_tribe_name:
            source_text = f"{source_text} · {other_tribe_name}"
        task = {
            "id": f"season_atonement_{tribe.get('id')}_{int(datetime.now().timestamp() * 1000)}",
            "status": "pending",
            "kind": "season_atonement",
            "sourceKind": source_kind,
            "sourceLabel": source_text,
            "sourceId": source_id,
            "dedupeId": dedupe_id,
            "title": profile.get("title", "公开赎罪"),
            "summary": profile.get("summary", "这件事留下了公开裂痕，需要成员完成赎罪任务。"),
            "otherTribeId": other_tribe_id,
            "otherTribeName": other_tribe_name,
            "createdBy": player_id,
            "createdAt": now_text,
            **profile
        }
        tribe.setdefault("season_taboo_remedies", []).append(task)
        tribe["season_taboo_remedies"] = tribe["season_taboo_remedies"][-TRIBE_SEASON_ATONEMENT_TASK_LIMIT:]
        return task

    def _apply_season_taboo_reward(self, tribe: dict, reward: dict) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood = int(reward.get("wood", 0) or 0)
        if wood:
            storage["wood"] = max(0, int(storage.get("wood", 0) or 0) + wood)
            reward_parts.append(f"木材{wood:+d}")
        wood_cost = int(reward.get("woodCost", 0) or 0)
        if wood_cost:
            storage["wood"] = max(0, int(storage.get("wood", 0) or 0) - wood_cost)
            reward_parts.append(f"木材-{wood_cost}")
        stone = int(reward.get("stone", 0) or 0)
        if stone:
            storage["stone"] = max(0, int(storage.get("stone", 0) or 0) + stone)
            reward_parts.append(f"石块{stone:+d}")
        stone_cost = int(reward.get("stoneCost", 0) or 0)
        if stone_cost:
            storage["stone"] = max(0, int(storage.get("stone", 0) or 0) - stone_cost)
            reward_parts.append(f"石块-{stone_cost}")
        food_cost = int(reward.get("foodCost", 0) or 0)
        if food_cost:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) - food_cost)
            reward_parts.append(f"食物-{food_cost}")
        food = int(reward.get("food", reward.get("foodReward", 0)) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        discovery = int(reward.get("discoveryProgress", reward.get("discoveryReward", 0)) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        renown = int(reward.get("renown", reward.get("renownReward", 0)) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        trade = int(reward.get("tradeReputation", reward.get("tradeReward", 0)) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        pressure_relief = int(reward.get("warPressureRelief", 0) or 0)
        if pressure_relief:
            changed = 0
            for relation in (tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                if before <= 0:
                    continue
                relation["warPressure"] = max(0, before - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                changed += before - int(relation.get("warPressure", 0) or 0)
            if changed:
                reward_parts.append(f"战争压力-{changed}")
        return reward_parts

    def _complete_season_taboo_context(self, tribe: dict, taboo: dict, context: dict, member_name: str) -> list:
        if not context:
            return []
        x = float(context.get("x", 0) or 0)
        z = float(context.get("z", 0) or 0)
        memory = self._record_map_memory(
            tribe,
            "season_taboo",
            f"{context.get('label', taboo.get('label', '季节禁忌'))}祝福",
            f"{taboo.get('label', '季节禁忌')}在{context.get('sourceLabel', '旧痕')}旁形成祝福，后来者可重读这段季节承诺。",
            x,
            z,
            f"season_taboo:{taboo.get('id')}",
            member_name
        ) if hasattr(self, "_record_map_memory") else None
        myth_claim = self._open_myth_claim(
            tribe,
            "season_taboo",
            context.get("label") or taboo.get("label", "季节禁忌"),
            context.get("mythSummary") or f"{taboo.get('label', '季节禁忌')}形成祝福后，族人开始争论它应被讲成哪一种神话。",
            x,
            z,
            f"season_taboo:{taboo.get('id')}",
            member_name
        ) if hasattr(self, "_open_myth_claim") else None
        parts = []
        if memory:
            parts.append("留下活地图记忆")
        if myth_claim:
            parts.append("开启神话解释权")
        return parts

    async def choose_season_taboo(self, player_id: str, taboo_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以宣布季节禁忌")
            return
        if self._active_season_taboo(tribe):
            await self._send_tribe_error(player_id, "当前季节禁忌仍在持续")
            return
        config = TRIBE_SEASON_TABOO_OPTIONS.get(taboo_key)
        if not config:
            await self._send_tribe_error(player_id, "未知季节禁忌")
            return

        now = datetime.now()
        context = self._season_taboo_context_for_key(tribe, taboo_key)
        taboo = {
            "id": f"season_taboo_{tribe_id}_{int(now.timestamp() * 1000)}",
            "key": taboo_key,
            "label": context.get("label") if context else config.get("label", "季节禁忌"),
            "summary": context.get("summary") if context else config.get("summary", ""),
            "context": context,
            "status": "active",
            "progress": 0,
            "target": TRIBE_SEASON_TABOO_PROGRESS_TARGET,
            "observerIds": [],
            "observerNames": [],
            "createdBy": player_id,
            "createdByName": member.get("name", "管理者"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_SEASON_TABOO_ACTIVE_MINUTES * 60).isoformat()
        }
        if context:
            observe_reward = self._merge_season_taboo_rewards(config.get("observeReward", {}), context.get("observeReward", {}))
            blessing = self._merge_season_taboo_rewards(config.get("blessing", {}), context.get("blessing", {}))
            taboo["contextRewardLabel"] = self._reward_summary_text(self._merge_season_taboo_rewards(observe_reward, blessing))
        tribe["season_taboo"] = taboo
        tribe.setdefault("season_taboo_history", []).append(taboo)
        tribe["season_taboo_history"] = tribe["season_taboo_history"][-TRIBE_SEASON_TABOO_LIMIT:]
        detail = f"{member.get('name', '管理者')} 宣布{taboo['label']}：{taboo['summary']} 成员可以践行禁忌累积祝福，也可以公开破戒换取急用资源。"
        self._add_tribe_history(tribe, "ritual", "宣布季节禁忌", detail, player_id, {"kind": "season_taboo", "taboo": taboo})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def observe_season_taboo(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        taboo = self._active_season_taboo(tribe)
        if not taboo:
            await self._send_tribe_error(player_id, "当前没有可践行的季节禁忌")
            return
        if player_id in (taboo.get("observerIds", []) or []):
            await self._send_tribe_error(player_id, "你已经践行过这条季节禁忌")
            return
        config = TRIBE_SEASON_TABOO_OPTIONS.get(taboo.get("key"), {})
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        taboo.setdefault("observerIds", []).append(player_id)
        taboo.setdefault("observerNames", []).append(member_name)
        taboo["progress"] = int(taboo.get("progress", 0) or 0) + 1
        member["trust_marks"] = int(member.get("trust_marks", 0) or 0) + 1
        context = taboo.get("context") or {}
        reward_parts = self._apply_season_taboo_reward(
            tribe,
            self._merge_season_taboo_rewards(config.get("observeReward", {}), context.get("observeReward", {}))
        )
        reward_parts.append("守戒信用+1")
        reward_parts.extend(self._record_season_taboo_custom(tribe, player_id, taboo.get("label", "践行季节禁忌")))
        blessed_now = False
        if not taboo.get("blessed") and int(taboo.get("progress", 0) or 0) >= int(taboo.get("target", TRIBE_SEASON_TABOO_PROGRESS_TARGET) or TRIBE_SEASON_TABOO_PROGRESS_TARGET):
            taboo["blessed"] = True
            taboo["blessedAt"] = datetime.now().isoformat()
            blessing_parts = self._apply_season_taboo_reward(
                tribe,
                self._merge_season_taboo_rewards(config.get("blessing", {}), context.get("blessing", {}))
            )
            reward_parts.extend([f"祝福{part}" for part in blessing_parts])
            context_parts = self._complete_season_taboo_context(tribe, taboo, context, member_name)
            reward_parts.extend(context_parts)
            blessed_now = True
        detail = f"{member_name} {config.get('observeLabel', '践行禁忌')}，{taboo.get('label', '季节禁忌')}进度 {taboo.get('progress', 0)} / {taboo.get('target', 0)}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        if blessed_now:
            detail += " 季节祝福已经形成。"
            await self._publish_world_rumor(
                "season",
                "季节祝福",
                f"{tribe.get('name', '部落')} 遵守{taboo.get('label', '季节禁忌')}，把禁忌转成了公开祝福。",
                {"tribeId": tribe_id, "tabooKey": taboo.get("key")}
            )
        self._add_tribe_history(tribe, "ritual", "践行季节禁忌", detail, player_id, {"kind": "season_taboo_observe", "tabooId": taboo.get("id"), "rewardParts": reward_parts})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    def _season_taboo_temptation_config(self, config: dict, temptation_key: str = "") -> dict:
        temptations = [item for item in (config.get("temptations", []) or []) if isinstance(item, dict)]
        selected = next((item for item in temptations if item.get("key") == temptation_key), None)
        if selected:
            return selected
        if temptations:
            return temptations[0]
        return {
            "key": "default",
            "label": config.get("breakLabel", "破戒取急用"),
            "summary": config.get("breakSummary", ""),
            "reward": dict(config.get("breakReward", {}) or {}),
            "evidenceLabel": "破戒证据"
        }

    def _season_taboo_boundary_target(self, tribe: dict) -> tuple[str, dict | None]:
        relations = [
            (other_id, relation)
            for other_id, relation in (tribe.get("boundary_relations", {}) or {}).items()
            if isinstance(relation, dict) and other_id in getattr(self, "tribes", {})
        ]
        if not relations:
            return "", None
        relations.sort(key=lambda item: (-int(item[1].get("warPressure", 0) or 0), int(item[1].get("score", 0) or 0)))
        return relations[0]

    def _record_season_taboo_custom(self, tribe: dict, player_id: str, source_label: str) -> list[str]:
        if not hasattr(self, "_record_tribe_custom_choice"):
            return []
        record = self._record_tribe_custom_choice(tribe, "oathbound", source_label, player_id)
        if not record:
            return []
        return ["守誓风俗+1" + ("，成为主导风俗" if record.get("becameDominant") else "")]

    def _record_season_taboo_evidence(self, tribe: dict, taboo: dict, temptation: dict, member_name: str, reward_parts: list[str]) -> dict:
        now = datetime.now()
        evidence = {
            "id": f"season_taboo_evidence_{tribe.get('id')}_{int(now.timestamp() * 1000)}",
            "tabooId": taboo.get("id", ""),
            "tabooLabel": taboo.get("label", "季节禁忌"),
            "label": temptation.get("evidenceLabel") or temptation.get("label") or "破戒证据",
            "summary": f"{member_name} 选择“{temptation.get('label', '破戒取急用')}”，获得{'、'.join(reward_parts) if reward_parts else '短时优势'}。",
            "actorName": member_name,
            "temptationKey": temptation.get("key", ""),
            "rewardLabel": self._reward_summary_text(temptation.get("reward", {}) or {}),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_SEASON_TABOO_EVIDENCE_ACTIVE_MINUTES * 60).isoformat(),
            "status": "active"
        }
        tribe.setdefault("season_taboo_evidence", []).append(evidence)
        tribe["season_taboo_evidence"] = tribe["season_taboo_evidence"][-TRIBE_SEASON_TABOO_EVIDENCE_LIMIT:]
        return evidence

    async def break_season_taboo(self, player_id: str, temptation_key: str = ""):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        taboo = self._active_season_taboo(tribe)
        if not taboo:
            await self._send_tribe_error(player_id, "当前没有可破戒的季节禁忌")
            return
        if taboo.get("broken"):
            await self._send_tribe_error(player_id, "这条季节禁忌已经破戒，先完成补救")
            return
        config = TRIBE_SEASON_TABOO_OPTIONS.get(taboo.get("key"), {})
        member = tribe.get("members", {}).get(player_id, {})
        temptation = self._season_taboo_temptation_config(config, temptation_key)
        reward_parts = self._apply_season_taboo_reward(tribe, temptation.get("reward", config.get("breakReward", {})))
        now_text = datetime.now().isoformat()
        taboo["broken"] = True
        taboo["brokenAt"] = now_text
        taboo["brokenBy"] = player_id
        taboo["brokenByName"] = member.get("name", "成员")
        taboo["brokenTemptationKey"] = temptation.get("key", "")
        taboo["brokenTemptationLabel"] = temptation.get("label", config.get("breakLabel", "破戒取急用"))
        break_count = int(tribe.get("season_taboo_break_count", 0) or 0) + 1
        tribe["season_taboo_break_count"] = break_count
        evidence = self._record_season_taboo_evidence(tribe, taboo, temptation, member.get("name", "成员"), reward_parts)
        evidence["commonJudgeHint"] = "可由中立部落共同裁判"
        if hasattr(self, "_open_myth_claim"):
            camp_center = (tribe.get("camp") or {}).get("center") or {}
            myth = self._open_myth_claim(
                tribe,
                "taboo_break",
                evidence.get("label", "破戒证据"),
                f"{evidence.get('label', '破戒证据')}已经公开，族人可以把它解释为火种护佑、旧路显现、互市佳兆或守边誓言。",
                float(camp_center.get("x", 0) or 0),
                float(camp_center.get("z", 0) or 0),
                evidence.get("id", ""),
                member.get("name", "成员")
            )
            if myth:
                evidence["mythClaimId"] = myth.get("id", "")
        law_parts = []
        if temptation.get("lawEventKey") and hasattr(self, "apply_tribe_law_violation"):
            law_parts = self.apply_tribe_law_violation(
                tribe,
                player_id,
                temptation.get("lawEventKey"),
                temptation.get("label", "破戒诱惑")
            )
            if law_parts:
                evidence["lawHint"] = "、".join(law_parts)
        if temptation.get("lawEventKey") == "boundary_press":
            other_id, relation = self._season_taboo_boundary_target(tribe)
            if other_id and relation is not None:
                other = self.tribes.get(other_id, {})
                relation["warPressure"] = min(10, int(relation.get("warPressure", 0) or 0) + 1)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                relation["lastAction"] = "season_taboo_boundary_press"
                relation["lastActionAt"] = now_text
                evidence["otherTribeId"] = other_id
                evidence["otherTribeName"] = other.get("name", "邻近部落")
                evidence["oldGrudgeHint"] = f"边界战争压力+1，可进入旧怨封存"
                if hasattr(self, "_wake_old_grudge_after_pressure"):
                    wake = self._wake_old_grudge_after_pressure(tribe, other_id, evidence.get("label", "破戒证据"))
                    if wake:
                        evidence["oldGrudgeWakeTaskId"] = wake.get("id", "")
                        evidence["oldGrudgeHint"] = "边界压力触发旧怨苏醒"
        remedy_config = dict(config.get("remedy") or {})
        remedy = {
            "id": f"season_taboo_remedy_{taboo.get('id')}",
            "status": "pending",
            "kind": "season_taboo_remedy",
            "title": remedy_config.get("title", "季节补救"),
            "summary": remedy_config.get("summary", "破戒已经公开，需要成员完成补救任务。"),
            "tabooId": taboo.get("id"),
            "tabooLabel": taboo.get("label", "季节禁忌"),
            "temptationLabel": temptation.get("label", config.get("breakLabel", "破戒取急用")),
            "evidenceId": evidence.get("id"),
            "sourceLabel": evidence.get("label"),
            "createdAt": now_text,
            **remedy_config
        }
        tribe.setdefault("season_taboo_remedies", []).append(remedy)
        tribe["season_taboo_remedies"] = tribe["season_taboo_remedies"][-TRIBE_SEASON_ATONEMENT_TASK_LIMIT:]
        detail = f"{member.get('name', '成员')} 受诱惑选择“{temptation.get('label', config.get('breakLabel', '破戒取急用'))}”：{temptation.get('summary', config.get('breakSummary', ''))} {'、'.join(reward_parts) or '已记录'}，留下公开证据“{evidence.get('label', '破戒证据')}”。补救任务“{remedy['title']}”已公开。"
        if law_parts:
            detail += f" 律令也记下了：{'、'.join(law_parts)}。"
        if break_count >= TRIBE_SEASON_ATONEMENT_BREAK_THRESHOLD:
            atonement = self._open_tribe_atonement_task(
                tribe,
                "taboo_break",
                taboo.get("label", "季节破戒"),
                player_id,
                source_id=taboo.get("id", "")
            )
            if atonement:
                detail += f" 连续破戒已触发赎罪任务“{atonement.get('title', '公开赎罪')}”。"
        self._add_tribe_history(tribe, "governance", "禁忌破戒诱惑", detail, player_id, {"kind": "season_taboo_temptation", "tabooId": taboo.get("id"), "temptationKey": temptation.get("key"), "evidence": evidence, "remedy": remedy})
        await self._publish_world_rumor(
            "season",
            "破戒证据",
            f"{tribe.get('name', '部落')} 的{taboo.get('label', '季节禁忌')}留下破戒证据：{evidence.get('label', '证据')}。",
            {"tribeId": tribe_id, "tabooId": taboo.get("id"), "evidenceId": evidence.get("id")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_season_taboo_remedy(self, player_id: str, remedy_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        remedy = next((
            item for item in (tribe.get("season_taboo_remedies", []) or [])
            if isinstance(item, dict) and item.get("id") == remedy_id and item.get("status") == "pending"
        ), None)
        if not remedy:
            await self._send_tribe_error(player_id, "没有找到可完成的季节补救")
            return
        food_cost = int(remedy.get("foodCost", 0) or 0)
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"补救需要食物 {food_cost}")
            return
        wood_cost = int(remedy.get("woodCost", 0) or 0)
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"补救需要木材 {wood_cost}")
            return
        reward_parts = self._apply_season_taboo_reward(tribe, remedy)
        reward_parts.extend(self._record_season_taboo_custom(tribe, player_id, remedy.get("title", "季节补救")))
        other_tribe_id = remedy.get("otherTribeId")
        if other_tribe_id:
            relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
            relation_delta = int(remedy.get("relationDelta", 0) or 0)
            trust_delta = int(remedy.get("tradeTrustDelta", 0) or 0)
            pressure_relief = int(remedy.get("pressureRelief", 0) or 0)
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
                reward_parts.append(f"关系{relation_delta:+d}")
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
                reward_parts.append(f"贸易信任+{trust_delta}")
            if pressure_relief:
                before = int(relation.get("warPressure", 0) or 0)
                relation["warPressure"] = max(0, before - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                if before != int(relation.get("warPressure", 0) or 0):
                    reward_parts.append(f"战争压力-{before - int(relation.get('warPressure', 0) or 0)}")
            relation["lastAction"] = f"season_{remedy.get('kind', 'remedy')}"
            relation["lastActionAt"] = datetime.now().isoformat()
        remedy["status"] = "completed"
        remedy["completedAt"] = datetime.now().isoformat()
        remedy["completedBy"] = player_id
        remedy["completedByName"] = (tribe.get("members", {}).get(player_id, {}) or {}).get("name", "成员")
        evidence_id = remedy.get("evidenceId")
        for evidence in tribe.get("season_taboo_evidence", []) or []:
            if isinstance(evidence, dict) and evidence.get("id") == evidence_id:
                evidence["status"] = "remedied"
                evidence["remediedAt"] = remedy["completedAt"]
                evidence["remediedBy"] = player_id
                evidence["remediedByName"] = remedy["completedByName"]
                break
        taboo = tribe.get("season_taboo")
        if isinstance(taboo, dict) and taboo.get("id") == remedy.get("tabooId"):
            taboo["broken"] = False
            taboo["remediedAt"] = remedy["completedAt"]
        member = tribe.get("members", {}).get(player_id, {})
        is_atonement = remedy.get("kind") == "season_atonement"
        label = "公开赎罪" if is_atonement else "季节补救"
        detail = f"{member.get('name', '成员')} 完成{remedy.get('title', label)}：{'、'.join(reward_parts) or '禁忌重新被承认'}。"
        member_name = member.get("name", "成员")
        atonement_token = None
        if is_atonement:
            atonement_token = self._create_atonement_token_from_remedy(tribe, remedy, player_id, member_name)
            if atonement_token:
                if atonement_token.get("messengerReady"):
                    detail += f" 赎罪信物已生成，可通过盟约信使送往 {atonement_token.get('otherTribeName', '邻近部落')}。"
                else:
                    detail += " 旧痕承认已留下，短时间内会显示在部落面板。"
        self._add_tribe_history(
            tribe,
            "ritual",
            label,
            detail,
            player_id,
            {
                "kind": remedy.get("kind", "season_taboo_remedy"),
                "remedyId": remedy_id,
                "tabooId": remedy.get("tabooId"),
                "sourceKind": remedy.get("sourceKind"),
                "atonementTokenId": atonement_token.get("id") if atonement_token else ""
            }
        )
        if is_atonement:
            await self._publish_world_rumor(
                "season",
                "公开赎罪",
                f"{tribe.get('name', '部落')} 完成{remedy.get('title', '公开赎罪')}，把{remedy.get('sourceLabel', '旧事')}重新纳入共同承认。",
                {"tribeId": tribe_id, "sourceKind": remedy.get("sourceKind"), "remedyId": remedy_id, "atonementTokenId": atonement_token.get("id") if atonement_token else ""}
            )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        if atonement_token and atonement_token.get("otherTribeId"):
            await self.broadcast_tribe_state(atonement_token.get("otherTribeId"))
