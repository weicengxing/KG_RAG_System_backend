from datetime import datetime
import random

from game_config import *


class GameAncestorQuestionMixin:
    def _active_ancestor_question(self, tribe: dict) -> dict | None:
        question = tribe.get("ancestor_question")
        if not isinstance(question, dict) or question.get("status") != "active":
            return None
        active_until = question.get("activeUntil")
        if active_until:
            try:
                if datetime.fromisoformat(active_until) <= datetime.now():
                    question["status"] = "expired"
                    question["expiredAt"] = datetime.now().isoformat()
                    return None
            except (TypeError, ValueError):
                question["status"] = "expired"
                question["expiredAt"] = datetime.now().isoformat()
                return None
        return question

    def _public_ancestor_question(self, tribe: dict) -> dict | None:
        question = self._active_ancestor_question(tribe)
        if not question:
            return None
        return {
            "id": question.get("id"),
            "key": question.get("key"),
            "label": question.get("label"),
            "summary": question.get("summary"),
            "startedByName": question.get("startedByName"),
            "progress": len(question.get("responses", []) or []),
            "target": question.get("target", TRIBE_ANCESTOR_QUESTION_TARGET),
            "responses": list(question.get("responses", []) or []),
            "eventBiasLabel": question.get("eventBiasLabel", ""),
            "activeUntil": question.get("activeUntil")
        }

    def _public_ancestor_question_options(self, tribe: dict) -> dict:
        if self._active_ancestor_question(tribe):
            return {}
        options = {}
        has_totem = True
        if hasattr(self, "_has_tribe_structure_type"):
            has_totem = self._has_tribe_structure_type(tribe, "tribe_totem")
        for key, option in TRIBE_ANCESTOR_QUESTIONS.items():
            options[key] = {
                "key": key,
                "label": option.get("label", key),
                "summary": option.get("summary", ""),
                "eventBiasLabel": option.get("eventBiasLabel", ""),
                "available": has_totem,
                "lockedReason": "" if has_totem else "需要先立起部落图腾"
            }
        return options

    def _public_ancestor_question_answers(self) -> dict:
        return TRIBE_ANCESTOR_QUESTION_ANSWERS

    def _public_ancestor_question_records(self, tribe: dict) -> list:
        return [
            item for item in tribe.get("ancestor_question_records", []) or []
            if isinstance(item, dict)
        ][-TRIBE_ANCESTOR_QUESTION_RECORD_LIMIT:]

    def _public_ancestor_question_biases(self, tribe: dict) -> list:
        active = []
        for item in tribe.get("ancestor_question_event_biases", []) or []:
            if not isinstance(item, dict) or int(item.get("uses", 0) or 0) <= 0:
                continue
            active.append({
                "id": item.get("id"),
                "eventLabel": item.get("eventLabel"),
                "sourceLabel": item.get("sourceLabel"),
                "uses": item.get("uses"),
                "createdByName": item.get("createdByName"),
                "createdAt": item.get("createdAt")
            })
        return active[-TRIBE_ANCESTOR_QUESTION_BIAS_LIMIT:]

    def _apply_ancestor_question_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                parts.append(f"{label}+{amount}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        pressure_relief = int((reward or {}).get("pressureRelief", 0) or 0)
        if pressure_relief:
            relieved = self._relieve_ancestor_question_pressure(tribe, pressure_relief)
            parts.append(f"战争压力-{relieved or pressure_relief}")
        return parts

    def _relieve_ancestor_question_pressure(self, tribe: dict, amount: int) -> int:
        relieved = 0
        for relation in (tribe.get("boundary_relations") or {}).values():
            if not isinstance(relation, dict):
                continue
            before = int(relation.get("warPressure", 0) or 0)
            after = max(0, before - amount)
            relation["warPressure"] = after
            relation["canDeclareWar"] = after >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relieved += before - after
        return relieved

    def _ancestor_question_target(self, tribe: dict) -> int:
        members = tribe.get("members", {}) or {}
        return max(1, min(TRIBE_ANCESTOR_QUESTION_TARGET, len(members) or 1))

    async def start_ancestor_question(self, player_id: str, question_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if self._active_ancestor_question(tribe):
            await self._send_tribe_error(player_id, "当前已有祖灵问答尚未收束")
            return
        option = TRIBE_ANCESTOR_QUESTIONS.get(question_key)
        if not option:
            await self._send_tribe_error(player_id, "未知祖灵问题")
            return
        if hasattr(self, "_has_tribe_structure_type") and not self._has_tribe_structure_type(tribe, "tribe_totem"):
            await self._send_tribe_error(player_id, "需要先立起部落图腾")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        now = datetime.now()
        recent_history = (tribe.get("history") or [])[-1] if isinstance(tribe.get("history"), list) and tribe.get("history") else {}
        question = {
            "id": f"ancestor_question_{tribe_id}_{question_key}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "key": question_key,
            "label": option.get("label", "祖灵问答"),
            "summary": option.get("summary", "图腾旁浮出一个只适合共同回答的问题。"),
            "recentHistoryTitle": recent_history.get("title", ""),
            "target": self._ancestor_question_target(tribe),
            "responses": [],
            "reward": dict(option.get("reward", {}) or {}),
            "pressureRelief": int(option.get("pressureRelief", 0) or 0),
            "eventBias": option.get("eventBias", ""),
            "eventBiasLabel": option.get("eventBiasLabel", ""),
            "startedBy": player_id,
            "startedByName": member_name,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_ANCESTOR_QUESTION_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["ancestor_question"] = question
        detail = f"{member_name}在图腾旁开启“{question.get('label')}”，等待族人共同回答。"
        self._add_tribe_history(tribe, "world_event", "祖灵问答开启", detail, player_id, {"kind": "ancestor_question", "question": question})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def answer_ancestor_question(self, player_id: str, answer_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        question = self._active_ancestor_question(tribe)
        if not question:
            await self._send_tribe_error(player_id, "当前没有可回答的祖灵问答")
            return
        answer = TRIBE_ANCESTOR_QUESTION_ANSWERS.get(answer_key)
        if not answer:
            await self._send_tribe_error(player_id, "未知祖灵回答")
            return
        responses = question.setdefault("responses", [])
        if any(item.get("memberId") == player_id for item in responses if isinstance(item, dict)):
            await self._send_tribe_error(player_id, "你已经回答过这次祖灵问答")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(answer.get("woodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, "公共木材不足，无法献木添火")
            return
        food_cost = int(answer.get("foodCost", 0) or 0)
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, "公共食物不足，无法完成这次回答")
            return
        if wood_cost:
            storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        reward_parts = self._apply_ancestor_question_reward(tribe, answer.get("reward", {}))
        pressure_relief = int(answer.get("pressureRelief", 0) or 0)
        if pressure_relief:
            relieved = self._relieve_ancestor_question_pressure(tribe, pressure_relief)
            reward_parts.append(f"战争压力-{relieved or pressure_relief}")
        response = {
            "memberId": player_id,
            "memberName": member_name,
            "answerKey": answer_key,
            "answerLabel": answer.get("label", answer_key),
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        responses.append(response)

        target = int(question.get("target", TRIBE_ANCESTOR_QUESTION_TARGET) or TRIBE_ANCESTOR_QUESTION_TARGET)
        if len(responses) >= target:
            await self._complete_ancestor_question(player_id, tribe_id, tribe, question, answer)
            return

        detail = f"{member_name}用“{answer.get('label', answer_key)}”回答祖灵问答，进度 {len(responses)} / {target}。"
        self._add_tribe_history(tribe, "world_event", "祖灵问答回应", detail, player_id, {"kind": "ancestor_question_answer", "response": response})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def _complete_ancestor_question(self, player_id: str, tribe_id: str, tribe: dict, question: dict, last_answer: dict):
        now = datetime.now()
        reward = dict(question.get("reward", {}) or {})
        if int(question.get("pressureRelief", 0) or 0):
            reward["pressureRelief"] = int(reward.get("pressureRelief", 0) or 0) + int(question.get("pressureRelief", 0) or 0)
        reward_parts = self._apply_ancestor_question_reward(tribe, reward)
        answer_counts = {}
        for response in question.get("responses", []) or []:
            key = response.get("answerKey")
            answer_counts[key] = answer_counts.get(key, 0) + 1
        dominant_key = max(answer_counts, key=answer_counts.get) if answer_counts else ""
        dominant_answer = TRIBE_ANCESTOR_QUESTION_ANSWERS.get(dominant_key, {}) or last_answer or {}
        event_bias = dominant_answer.get("eventBias") or question.get("eventBias")
        event_label = dominant_answer.get("eventBiasLabel") or question.get("eventBiasLabel") or event_bias
        influence = None
        if event_bias:
            influence = {
                "id": f"ancestor_bias_{question.get('id')}_{int(now.timestamp() * 1000)}",
                "eventKey": event_bias,
                "eventLabel": event_label,
                "sourceLabel": question.get("label", "祖灵问答"),
                "createdByName": tribe.get("members", {}).get(player_id, {}).get("name", "成员"),
                "uses": TRIBE_ANCESTOR_QUESTION_EVENT_BIAS_USES,
                "createdAt": now.isoformat()
            }
            tribe.setdefault("ancestor_question_event_biases", []).append(influence)
            tribe["ancestor_question_event_biases"] = tribe["ancestor_question_event_biases"][-TRIBE_ANCESTOR_QUESTION_BIAS_LIMIT:]
            reward_parts.append(f"下一次事件偏向：{event_label}")

        question["status"] = "resolved"
        question["resolvedAt"] = now.isoformat()
        question["rewardParts"] = reward_parts
        question["dominantAnswerLabel"] = dominant_answer.get("label", "")
        record = {
            "id": f"ancestor_question_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "label": question.get("label", "祖灵问答"),
            "summary": question.get("summary", ""),
            "startedByName": question.get("startedByName", ""),
            "dominantAnswerLabel": question.get("dominantAnswerLabel", ""),
            "responses": list(question.get("responses", []) or []),
            "rewardParts": reward_parts,
            "eventBiasLabel": event_label,
            "createdAt": now.isoformat()
        }
        tribe.setdefault("ancestor_question_records", []).append(record)
        tribe["ancestor_question_records"] = tribe["ancestor_question_records"][-TRIBE_ANCESTOR_QUESTION_RECORD_LIMIT:]
        tribe["ancestor_question"] = None

        detail = f"族人合力回答“{question.get('label', '祖灵问答')}”，祖灵把回答收成{event_label or '营地记忆'}。收获：{'、'.join(reward_parts) or '声望留存'}。"
        self._add_tribe_history(tribe, "world_event", "祖灵问答收束", detail, player_id, {"kind": "ancestor_question_complete", "record": record, "influence": influence})
        await self._publish_world_rumor(
            "world_event",
            "祖灵问答夜",
            f"{tribe.get('name', '部落')}在图腾旁完成“{question.get('label', '祖灵问答')}”，下一次异象更容易沿着{event_label or '祖灵提示'}出现。",
            {"tribeId": tribe_id, "recordId": record.get("id")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    def _apply_ancestor_question_world_event_bias(self, event_pool: list) -> list:
        if not event_pool:
            return event_pool
        pool = list(event_pool)
        events_by_key = {event.get("key"): event for event in event_pool if isinstance(event, dict)}
        changed = False
        for tribe in getattr(self, "tribes", {}).values():
            next_biases = []
            for bias in tribe.get("ancestor_question_event_biases", []) or []:
                if not isinstance(bias, dict) or int(bias.get("uses", 0) or 0) <= 0:
                    continue
                event = events_by_key.get(bias.get("eventKey"))
                if not event:
                    next_biases.append(bias)
                    continue
                pool.extend([event, event])
                bias["uses"] = max(0, int(bias.get("uses", 0) or 0) - 1)
                bias["usedAt"] = datetime.now().isoformat()
                changed = True
                if int(bias.get("uses", 0) or 0) > 0:
                    next_biases.append(bias)
            tribe["ancestor_question_event_biases"] = next_biases[-TRIBE_ANCESTOR_QUESTION_BIAS_LIMIT:]
        if changed and hasattr(self, "_save_tribe_state"):
            self._save_tribe_state()
        return pool
