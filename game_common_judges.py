from datetime import datetime

from game_config import *


class GameCommonJudgeMixin:
    def _common_judge_now(self):
        return datetime.now()

    def _common_judge_recent_source_ids(self, judge_tribe: dict) -> set:
        return {
            item.get("sourceCaseId")
            for item in (judge_tribe.get("common_judge_records", []) or [])[-TRIBE_COMMON_JUDGE_RECORD_LIMIT:]
            if isinstance(item, dict) and item.get("sourceCaseId")
        }

    def _common_judge_case_id(self, kind: str, source_id: str, owner_id: str, other_id: str = "") -> str:
        suffix = f"{owner_id}_{other_id}" if other_id else owner_id
        return f"common_judge_{kind}_{source_id}_{suffix}"

    def _common_judge_expired(self, active_until: str | None) -> bool:
        if not active_until:
            return False
        try:
            return datetime.fromisoformat(active_until) <= self._common_judge_now()
        except (TypeError, ValueError):
            return True

    def _common_judge_case_public(self, case: dict) -> dict:
        return {
            "id": case.get("id"),
            "kind": case.get("kind"),
            "sourceCaseId": case.get("sourceCaseId"),
            "title": case.get("title", "共同裁判"),
            "summary": case.get("summary", ""),
            "sourceLabel": case.get("sourceLabel", "分歧"),
            "sourceTribeId": case.get("sourceTribeId"),
            "sourceTribeName": case.get("sourceTribeName", "邻近部落"),
            "otherTribeId": case.get("otherTribeId", ""),
            "otherTribeName": case.get("otherTribeName", ""),
            "activeUntil": case.get("activeUntil"),
            "stakes": list(case.get("stakes", []) or [])
        }

    def _common_judge_rumor_cases(self, judge_tribe_id: str, recent_source_ids: set) -> list:
        cases = []
        for source_id, tribe in (getattr(self, "tribes", {}) or {}).items():
            if source_id == judge_tribe_id:
                continue
            for task in self._active_rumor_truth_tasks(tribe) if hasattr(self, "_active_rumor_truth_tasks") else []:
                if not isinstance(task, dict):
                    continue
                if self._common_judge_expired(task.get("activeUntil")):
                    continue
                source_case_id = task.get("id")
                if source_case_id in recent_source_ids:
                    continue
                cases.append({
                    "id": self._common_judge_case_id("rumor", source_case_id, source_id),
                    "kind": "rumor",
                    "sourceCaseId": source_case_id,
                    "sourceTribeId": source_id,
                    "sourceTribeName": tribe.get("name", "邻近部落"),
                    "title": task.get("title", "待辨传闻"),
                    "summary": task.get("summary", "这条说法仍在部落间流传，需要外部见证压住偏词。"),
                    "sourceLabel": task.get("sourceLabel", "传闻真假"),
                    "activeUntil": task.get("activeUntil"),
                    "stakes": [task.get("toneLabel", "未辨"), task.get("riskLabel", "可能有误")]
                })
        return cases

    def _common_judge_boundary_cases(self, judge_tribe_id: str, recent_source_ids: set) -> list:
        cases = []
        seen = set()
        for source_id, tribe in (getattr(self, "tribes", {}) or {}).items():
            if source_id == judge_tribe_id:
                continue
            for other_id, relation in (tribe.get("boundary_relations", {}) or {}).items():
                if other_id == judge_tribe_id or source_id == other_id or other_id not in self.tribes:
                    continue
                if not isinstance(relation, dict):
                    continue
                score = int(relation.get("score", 0) or 0)
                pressure = int(relation.get("warPressure", 0) or 0)
                trust = int(relation.get("tradeTrust", 0) or 0)
                if pressure <= 0 and score >= 2:
                    continue
                pair = tuple(sorted([source_id, other_id]))
                if pair in seen:
                    continue
                seen.add(pair)
                source_case_id = f"boundary_{pair[0]}_{pair[1]}_{score}_{pressure}_{trust}"
                if source_case_id in recent_source_ids:
                    continue
                other = self.tribes.get(other_id, {})
                temp = self._boundary_temperature_label(relation) if hasattr(self, "_boundary_temperature_label") else {"label": "边界分歧"}
                cases.append({
                    "id": self._common_judge_case_id("boundary", source_case_id, source_id, other_id),
                    "kind": "boundary",
                    "sourceCaseId": source_case_id,
                    "sourceTribeId": source_id,
                    "sourceTribeName": tribe.get("name", "邻近部落"),
                    "otherTribeId": other_id,
                    "otherTribeName": other.get("name", "另一部落"),
                    "title": "边界分歧待裁",
                    "summary": f"双方边界关系 {score:+d}，贸易信任 +{trust}，战争压力 {pressure}，需要中立者给一句可被双方复述的见证。",
                    "sourceLabel": temp.get("label", "边界温度"),
                    "stakes": [f"关系 {score:+d}", f"信任 +{trust}", f"战争压力 {pressure}"]
                })
        return cases

    def _common_judge_old_grudge_cases(self, judge_tribe_id: str, recent_source_ids: set) -> list:
        cases = []
        seen = set()
        for source_id, tribe in (getattr(self, "tribes", {}) or {}).items():
            if source_id == judge_tribe_id:
                continue
            for seal in self._active_old_grudge_seals(tribe) if hasattr(self, "_active_old_grudge_seals") else []:
                if not isinstance(seal, dict):
                    continue
                other_id = seal.get("otherTribeId")
                if not other_id or other_id == judge_tribe_id or other_id not in self.tribes:
                    continue
                source_case_id = seal.get("sourceId") or seal.get("id")
                pair_key = (source_case_id, tuple(sorted([source_id, other_id])))
                if pair_key in seen or source_case_id in recent_source_ids:
                    continue
                seen.add(pair_key)
                other = self.tribes.get(other_id, {})
                cases.append({
                    "id": self._common_judge_case_id("old_grudge", source_case_id, source_id, other_id),
                    "kind": "old_grudge",
                    "sourceCaseId": source_case_id,
                    "sourceTribeId": source_id,
                    "sourceTribeName": tribe.get("name", "邻近部落"),
                    "otherTribeId": other_id,
                    "otherTribeName": other.get("name", seal.get("otherTribeName", "另一部落")),
                    "title": "旧怨封存见证",
                    "summary": seal.get("summary") or f"旧怨被系在{seal.get('anchorLabel', '封存地')}，第三方裁判可以确认它不是继续挑衅的理由。",
                    "sourceLabel": seal.get("sourceLabel", "旧怨"),
                    "activeUntil": seal.get("activeUntil"),
                    "stakes": [seal.get("anchorLabel", "封存地"), f"进度 {seal.get('progress', 0)}/{seal.get('target', TRIBE_OLD_GRUDGE_SEAL_TARGET)}"]
                })
        return cases

    def _common_judge_trial_cases(self, judge_tribe_id: str, recent_source_ids: set) -> list:
        cases = []
        for source_id, tribe in (getattr(self, "tribes", {}) or {}).items():
            if source_id == judge_tribe_id:
                continue
            records = [
                item for item in (tribe.get("trial_ground_records", []) or [])[-TRIBE_TRIAL_GROUND_RECORD_LIMIT:]
                if isinstance(item, dict)
            ]
            for record in records[-2:]:
                source_case_id = record.get("id") or record.get("trialId")
                if not source_case_id or source_case_id in recent_source_ids:
                    continue
                cases.append({
                    "id": self._common_judge_case_id("trial", source_case_id, source_id),
                    "kind": "trial",
                    "sourceCaseId": source_case_id,
                    "sourceTribeId": source_id,
                    "sourceTribeName": tribe.get("name", "邻近部落"),
                    "title": record.get("title", "试炼结果待证"),
                    "summary": f"{record.get('memberName', '成员')}完成了{record.get('actionLabel', '试炼')}，外部见证能让成绩更像公共记忆而非自夸。",
                    "sourceLabel": record.get("label", "营地试炼"),
                    "stakes": list(record.get("rewardParts", []) or [])
                })
        return cases

    def _common_judge_traveler_song_cases(self, judge_tribe_id: str, recent_source_ids: set) -> list:
        cases = []
        for source_id, tribe in (getattr(self, "tribes", {}) or {}).items():
            if source_id == judge_tribe_id:
                continue
            sources = self._traveler_song_tune_sources(tribe) if hasattr(self, "_traveler_song_tune_sources") else []
            for source in sources[-2:]:
                source_case_id = source.get("sourceId")
                if not source_case_id or source_case_id in recent_source_ids:
                    continue
                cases.append({
                    "id": self._common_judge_case_id("traveler_song", source_case_id, source_id),
                    "kind": "traveler_song",
                    "sourceCaseId": source_case_id,
                    "sourceTribeId": source_id,
                    "sourceTribeName": tribe.get("name", "邻近部落"),
                    "title": source.get("title", "旅人谣曲待证"),
                    "summary": source.get("summary", "这段谣曲已经流出营地，外部见证能决定它更像祝词、口信还是旧事。"),
                    "sourceLabel": source.get("sourceLabel", "旅人谣曲"),
                    "stakes": ["传闻语气", "贸易信任", "公共见证"]
                })
        return cases

    def _public_common_judge_cases(self, judge_tribe: dict) -> list:
        if not judge_tribe:
            return []
        judge_tribe_id = judge_tribe.get("id")
        recent_source_ids = self._common_judge_recent_source_ids(judge_tribe)
        cases = []
        cases.extend(self._common_judge_rumor_cases(judge_tribe_id, recent_source_ids))
        cases.extend(self._common_judge_boundary_cases(judge_tribe_id, recent_source_ids))
        cases.extend(self._common_judge_old_grudge_cases(judge_tribe_id, recent_source_ids))
        cases.extend(self._common_judge_trial_cases(judge_tribe_id, recent_source_ids))
        cases.extend(self._common_judge_traveler_song_cases(judge_tribe_id, recent_source_ids))
        if hasattr(self, "_dispute_witness_common_judge_cases"):
            cases.extend(self._dispute_witness_common_judge_cases(judge_tribe_id, recent_source_ids))
        cases = [
            case for case in cases
            if case.get("sourceTribeId") != judge_tribe_id and case.get("otherTribeId") != judge_tribe_id
        ]
        cases.sort(key=lambda item: (0 if item.get("otherTribeId") else 1, item.get("kind", ""), item.get("title", "")))
        return [self._common_judge_case_public(case) for case in cases[:TRIBE_COMMON_JUDGE_CASE_LIMIT]]

    def _public_common_judge_records(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("common_judge_records", []) or [])
            if isinstance(item, dict)
        ][-TRIBE_COMMON_JUDGE_RECORD_LIMIT:]

    def _apply_common_judge_stat_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                parts.append(f"{label}{amount:+d}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = max(0, int(tribe.get(tribe_key, 0) or 0) + amount)
                parts.append(f"{label}{amount:+d}")
        return parts

    def _apply_common_judge_relation(self, source_tribe: dict, other_tribe: dict, action: dict) -> list:
        if not source_tribe or not other_tribe:
            return []
        parts = []
        for own, target in ((source_tribe, other_tribe), (other_tribe, source_tribe)):
            relation = own.setdefault("boundary_relations", {}).setdefault(target.get("id"), {})
            relation_delta = int(action.get("relationDelta", 0) or 0)
            trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
            relief = int(action.get("warPressureRelief", 0) or 0)
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            if relief:
                relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relation["temperatureTone"] = action.get("tone", relation.get("temperatureTone", ""))
            relation["lastAction"] = f"common_judge_{action.get('tone', 'witness')}"
            relation["lastActionAt"] = self._common_judge_now().isoformat()
        if int(action.get("relationDelta", 0) or 0):
            parts.append(f"双方关系{int(action.get('relationDelta', 0) or 0):+d}")
        if int(action.get("tradeTrustDelta", 0) or 0):
            parts.append(f"双方信任{int(action.get('tradeTrustDelta', 0) or 0):+d}")
        if int(action.get("warPressureRelief", 0) or 0):
            parts.append(f"战争压力-{int(action.get('warPressureRelief', 0) or 0)}")
        return parts

    def _find_common_judge_case(self, judge_tribe: dict, case_id: str) -> dict | None:
        for case in self._public_common_judge_cases(judge_tribe):
            if case.get("id") == case_id:
                return case
        return None

    async def submit_common_judge(self, player_id: str, case_id: str, action_key: str):
        judge_tribe_id = self.player_tribes.get(player_id)
        judge_tribe = self.tribes.get(judge_tribe_id)
        if not judge_tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_COMMON_JUDGE_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知共同裁判方式")
            return
        case = self._find_common_judge_case(judge_tribe, case_id)
        if not case:
            await self._send_tribe_error(player_id, "这件分歧已经不适合共同裁判")
            return
        source_tribe = self.tribes.get(case.get("sourceTribeId"))
        other_tribe = self.tribes.get(case.get("otherTribeId")) if case.get("otherTribeId") else None
        if not source_tribe or source_tribe.get("id") == judge_tribe_id or (other_tribe and other_tribe.get("id") == judge_tribe_id):
            await self._send_tribe_error(player_id, "共同裁判必须由中立部落成员提交")
            return

        now = self._common_judge_now()
        member = judge_tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        reward_parts = []
        reward_parts.extend(self._apply_common_judge_stat_reward(judge_tribe, action.get("judgeReward", {})))
        reward_parts.extend(self._apply_common_judge_stat_reward(source_tribe, action.get("sourceReward", {})))
        if other_tribe:
            reward_parts.extend(self._apply_common_judge_stat_reward(other_tribe, action.get("otherReward", {})))
            reward_parts.extend(self._apply_common_judge_relation(source_tribe, other_tribe, action))
        else:
            relation = judge_tribe.setdefault("boundary_relations", {}).setdefault(source_tribe.get("id"), {})
            if int(action.get("tradeTrustDelta", 0) or 0):
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + int(action.get("tradeTrustDelta", 0) or 0)))
                reward_parts.append(f"见证信任{int(action.get('tradeTrustDelta', 0) or 0):+d}")
        if case.get("kind") == "dispute_witness" and hasattr(self, "_record_dispute_witness_reference"):
            _, witness_bonus = self._record_dispute_witness_reference(
                source_tribe,
                case.get("sourceCaseId", ""),
                "common_judge",
                "共同裁判",
                case.get("otherTribeId", "")
            )
            reward_parts.extend(witness_bonus)

        record = {
            "id": f"common_judge_record_{judge_tribe_id}_{int(now.timestamp() * 1000)}",
            "sourceCaseId": case.get("sourceCaseId"),
            "caseId": case_id,
            "kind": case.get("kind"),
            "title": case.get("title", "共同裁判"),
            "sourceLabel": case.get("sourceLabel", "分歧"),
            "sourceTribeId": case.get("sourceTribeId"),
            "sourceTribeName": case.get("sourceTribeName", "邻近部落"),
            "otherTribeId": case.get("otherTribeId", ""),
            "otherTribeName": case.get("otherTribeName", ""),
            "judgeTribeId": judge_tribe_id,
            "judgeTribeName": judge_tribe.get("name", "中立部落"),
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "提交见证"),
            "toneLabel": action.get("toneLabel", "见证口风"),
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        for tribe in [judge_tribe, source_tribe, other_tribe]:
            if not tribe:
                continue
            tribe.setdefault("common_judge_records", []).append(record)
            tribe["common_judge_records"] = tribe["common_judge_records"][-TRIBE_COMMON_JUDGE_RECORD_LIMIT:]

        target_text = case.get("sourceTribeName", "邻近部落")
        if case.get("otherTribeName"):
            target_text += f" 与 {case.get('otherTribeName')}"
        detail = f"{member_name}代表{judge_tribe.get('name', '中立部落')}为{target_text}的“{case.get('title', '分歧')}”提交{action.get('label', '见证')}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        for tribe, history_player in ((judge_tribe, player_id), (source_tribe, player_id), (other_tribe, player_id)):
            if tribe:
                self._add_tribe_history(tribe, "diplomacy", "共同裁判", detail, history_player, {"kind": "common_judge", "record": record})
        await self._publish_world_rumor(
            "diplomacy",
            "共同裁判",
            f"{judge_tribe.get('name', '中立部落')}为{target_text}留下共同裁判：{action.get('rumorText', action.get('summary', '见证让争端暂时有了可复述的说法'))}",
            {
                "tribeId": judge_tribe_id,
                "sourceTribeId": case.get("sourceTribeId"),
                "otherTribeId": case.get("otherTribeId", ""),
                "caseId": case_id,
                "actionKey": action_key
            }
        )
        touched_ids = {judge_tribe_id, case.get("sourceTribeId"), case.get("otherTribeId", "")}
        for tribe_id in [item for item in touched_ids if item]:
            await self._notify_tribe(tribe_id, detail)
            await self.broadcast_tribe_state(tribe_id)
