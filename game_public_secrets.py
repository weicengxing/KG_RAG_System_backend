import random
from datetime import datetime

from game_config import *


class GamePublicSecretMixin:
    def _active_public_secrets(self, tribe: dict) -> list:
        return self._active_tribe_items(
            tribe,
            "public_secrets",
            TRIBE_PUBLIC_SECRET_LIMIT,
            inactive_statuses={"handled"}
        )

    def _public_public_secrets(self, tribe: dict) -> list:
        return [
            {
                "id": item.get("id"),
                "kind": item.get("kind"),
                "title": item.get("title", "未揭晓秘密"),
                "label": item.get("label", "公共秘密"),
                "summary": item.get("summary", ""),
                "sourceLabel": item.get("sourceLabel", "来源"),
                "discoveredByName": item.get("discoveredByName", "成员"),
                "activeUntil": item.get("activeUntil"),
                "createdAt": item.get("createdAt")
            }
            for item in self._active_public_secrets(tribe)
        ]

    def _public_secret_records(self, tribe: dict) -> list:
        self._refresh_public_secret_reveals(tribe)
        return [
            item for item in (tribe.get("public_secret_records", []) or [])
            if isinstance(item, dict)
        ][-TRIBE_PUBLIC_SECRET_RECORD_LIMIT:]

    def _public_secret_common_judge_cases(self, judge_tribe_id: str, recent_source_ids: set) -> list:
        cases = []
        for source_id, tribe in (getattr(self, "tribes", {}) or {}).items():
            if source_id == judge_tribe_id:
                continue
            for record in self._public_secret_records(tribe):
                if not record.get("judgeReady"):
                    continue
                source_case_id = record.get("id")
                if not source_case_id or source_case_id in recent_source_ids:
                    continue
                cases.append({
                    "id": self._common_judge_case_id("public_secret", source_case_id, source_id),
                    "kind": "public_secret",
                    "sourceCaseId": source_case_id,
                    "sourceTribeId": source_id,
                    "sourceTribeName": tribe.get("name", "邻近部落"),
                    "title": record.get("title", "未揭晓秘密待裁判"),
                    "summary": record.get("summary", "这个秘密被交给共同裁判，等待中立部落确认来源链。"),
                    "sourceLabel": record.get("sourceLabel", "公共秘密"),
                    "stakes": ["证据链", "声望", "传闻口风"]
                })
        return cases

    def _apply_public_secret_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(reward.get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        food = int(reward.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            parts.append(f"食物+{food}")
        renown = int(reward.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            parts.append(f"声望+{renown}")
        discovery = int(reward.get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            parts.append(f"发现进度+{discovery}")
        trade = int(reward.get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            parts.append(f"贸易信誉+{trade}")
        return parts

    def _public_secret_reveal_ready_at(self, now: datetime) -> str:
        return datetime.fromtimestamp(now.timestamp() + TRIBE_PUBLIC_SECRET_REVEAL_DELAY_MINUTES * 60).isoformat()

    def _append_public_secret_world_rumor(self, tribe: dict, record: dict, outcome: dict):
        if not hasattr(self, "world_rumors") or not hasattr(self, "_build_world_rumor"):
            return
        if record.get("revealRumorId"):
            return
        rumor = self._build_world_rumor(
            "public_secret_reveal",
            "公共秘密揭晓",
            f"{tribe.get('name', '某个部落')}早先处理的“{record.get('title', '未揭晓秘密')}”逐渐变成{outcome.get('label', '揭晓')}的说法。",
            {
                "tribeId": tribe.get("id"),
                "recordId": record.get("id"),
                "secretId": record.get("secretId"),
                "actionKey": record.get("actionKey"),
                "tone": outcome.get("rumorTone", "")
            }
        )
        self.world_rumors.append(rumor)
        self.world_rumors = self.world_rumors[-WORLD_RUMOR_LIMIT:]
        record["revealRumorId"] = rumor.get("id")

    def _create_public_secret_followup(self, tribe: dict, record: dict, outcome: dict, now: datetime) -> dict | None:
        if not outcome.get("followupLabel"):
            return None
        if record.get("followupTask"):
            return record.get("followupTask")
        task = {
            "id": f"public_secret_followup_{record.get('id')}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "truthState": outcome.get("truthState", "uncertain"),
            "sourceId": f"public_secret:{record.get('id')}",
            "sourceKind": "public_secret_reveal",
            "sourceLabel": outcome.get("followupLabel", "公共秘密后续"),
            "title": f"{record.get('title', '未揭晓秘密')}后续",
            "summary": outcome.get("summary", "秘密揭晓后留下了新的传闻后续。"),
            "toneLabel": outcome.get("rumorTone", "含混"),
            "riskLabel": "来自公共秘密揭晓",
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_RUMOR_TRUTH_ACTIVE_MINUTES * 60).isoformat()
        }
        if outcome.get("followupLabel") == "传闻真假":
            active = self._active_rumor_truth_tasks(tribe) if hasattr(self, "_active_rumor_truth_tasks") else []
            if not any(item.get("sourceId") == task["sourceId"] for item in active):
                tribe["rumor_truth_tasks"] = [*active, task][-TRIBE_RUMOR_TRUTH_LIMIT:]
        record["followupTask"] = {
            "id": task.get("id"),
            "label": outcome.get("followupLabel", "后续任务"),
            "title": task.get("title"),
            "summary": task.get("summary")
        }
        return record["followupTask"]

    def _apply_public_secret_judge_relations(self, tribe: dict, record: dict) -> list:
        parts = []
        for judge_record in tribe.get("common_judge_records", []) or []:
            if not isinstance(judge_record, dict) or judge_record.get("sourceCaseId") != record.get("id"):
                continue
            judge_id = judge_record.get("judgeTribeId")
            if not judge_id or judge_id == tribe.get("id"):
                continue
            relation = tribe.setdefault("boundary_relations", {}).setdefault(judge_id, {})
            relation["tradeTrust"] = min(10, int(relation.get("tradeTrust", 0) or 0) + 1)
            relation["lastAction"] = "public_secret_reveal_judged"
            relation["lastActionAt"] = datetime.now().isoformat()
            parts.append(f"{judge_record.get('judgeTribeName', '中立部落')}信任+1")
            break
        return parts

    def _refresh_public_secret_reveals(self, tribe: dict):
        if not tribe:
            return
        now = datetime.now()
        changed = False
        for record in tribe.get("public_secret_records", []) or []:
            if not isinstance(record, dict) or record.get("revealStatus") == "revealed":
                continue
            ready_at = record.get("revealReadyAt")
            if not ready_at:
                continue
            try:
                if datetime.fromisoformat(ready_at) > now:
                    continue
            except (TypeError, ValueError):
                continue
            outcome = TRIBE_PUBLIC_SECRET_REVEAL_OUTCOMES.get(record.get("actionKey"), {})
            reward_parts = self._apply_public_secret_reward(tribe, outcome.get("reward") or {})
            if outcome.get("evidenceChain"):
                record["evidenceChainReady"] = True
                reward_parts.extend(self._apply_public_secret_judge_relations(tribe, record))
            if outcome.get("storyHook"):
                record["storyHookReady"] = True
                if hasattr(self, "_record_oral_map_context_reference"):
                    oral_reference, oral_lineage = self._record_oral_map_context_reference(
                        tribe,
                        "rumor_truth",
                        record.get("title", "公共秘密揭晓"),
                        record.get("memberName", "讲述者"),
                        "公共秘密揭晓"
                    )
                    if oral_reference:
                        record["oralMapReference"] = oral_reference
                    if oral_lineage:
                        record["oralMapLineage"] = oral_lineage
            followup = self._create_public_secret_followup(tribe, record, outcome, now)
            record["revealStatus"] = "revealed"
            record["revealedAt"] = now.isoformat()
            record["revealLabel"] = outcome.get("label", "秘密揭晓")
            record["revealSummary"] = outcome.get("summary", "秘密的后续说法逐渐浮出水面。")
            record["revealTone"] = outcome.get("rumorTone", "")
            record["revealRewardParts"] = reward_parts
            if followup:
                record["followupLabel"] = followup.get("label")
            detail = f"“{record.get('title', '未揭晓秘密')}”后续揭晓为{record['revealLabel']}。"
            if reward_parts:
                detail += f" {'、'.join(reward_parts)}。"
            self._add_tribe_history(tribe, "world_event", "公共秘密揭晓", detail, "", {"kind": "public_secret_reveal", "record": record})
            self._append_public_secret_world_rumor(tribe, record, outcome)
            changed = True
        if changed and hasattr(self, "_save_tribe_state"):
            self._save_tribe_state()

    def _maybe_create_public_secret(self, tribe: dict, source_key: str, source_label: str, summary: str, x: float, z: float, source_id: str, actor_name: str = "") -> dict | None:
        if not tribe or source_key not in TRIBE_PUBLIC_SECRET_SOURCES:
            return None
        active = self._active_public_secrets(tribe)
        dedupe_id = f"{source_key}:{source_id}"
        existing = next((item for item in active if item.get("dedupeId") == dedupe_id), None)
        if existing:
            return existing
        plan = TRIBE_PUBLIC_SECRET_SOURCES[source_key]
        now = datetime.now()
        secret = {
            "id": f"public_secret_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "type": "public_secret",
            "status": "active",
            "kind": plan.get("kind", "unknown_secret"),
            "title": plan.get("title", "未揭晓秘密"),
            "label": plan.get("label", "公共秘密"),
            "summary": summary or plan.get("summary", "这段消息还没有被公开解释。"),
            "sourceKey": source_key,
            "sourceLabel": source_label or plan.get("label", "来源"),
            "sourceId": source_id,
            "dedupeId": dedupe_id,
            "x": max(-490, min(490, float(x or 0))),
            "z": max(-490, min(490, float(z or 0))),
            "discoveredByName": actor_name or "成员",
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_PUBLIC_SECRET_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["public_secrets"] = [*active, secret][-TRIBE_PUBLIC_SECRET_LIMIT:]
        return secret

    async def resolve_public_secret(self, player_id: str, secret_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_PUBLIC_SECRET_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知的秘密处理方式")
            return
        active = self._active_public_secrets(tribe)
        secret = next((item for item in active if item.get("id") == secret_id), None)
        if not secret:
            await self._send_tribe_error(player_id, "这个秘密已经揭晓或散去")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        reward_parts = self._apply_public_secret_reward(tribe, action.get("reward") or {})
        observer_shift = self._apply_observer_outcome_shift(tribe, "public_secret", secret.get("id")) if hasattr(self, "_apply_observer_outcome_shift") else None
        if observer_shift:
            reward_parts.extend(observer_shift.get("rewardParts", []))
        now = datetime.now()
        record = {
            "id": f"public_secret_record_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "secretId": secret.get("id"),
            "kind": secret.get("kind"),
            "title": secret.get("title", "未揭晓秘密"),
            "label": secret.get("label", "公共秘密"),
            "summary": secret.get("summary", ""),
            "sourceLabel": secret.get("sourceLabel", "来源"),
            "sourceId": secret.get("sourceId", ""),
            "actionKey": action_key,
            "actionLabel": action.get("label", "处理"),
            "memberId": player_id,
            "memberName": member_name,
            "rewardParts": reward_parts,
            "observerShift": observer_shift,
            "judgeReady": bool(action.get("judgeReady")),
            "storyReady": bool(action.get("storyReady")),
            "revealStatus": "pending",
            "revealReadyAt": self._public_secret_reveal_ready_at(now),
            "createdAt": now.isoformat()
        }
        secret["status"] = "handled"
        secret["handledByName"] = member_name
        secret["handledAt"] = now.isoformat()
        tribe["public_secrets"] = [item for item in active if item.get("id") != secret_id]
        records = [
            item for item in (tribe.get("public_secret_records", []) or [])
            if isinstance(item, dict)
        ]
        tribe["public_secret_records"] = [*records, record][-TRIBE_PUBLIC_SECRET_RECORD_LIMIT:]

        detail = f"{member_name}将“{record['title']}”{action.get('label', '处理')}，来源是{record['sourceLabel']}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        if observer_shift:
            detail += f" {observer_shift.get('summary')}"
        self._add_tribe_history(
            tribe,
            "world_event",
            "处理公共秘密",
            detail,
            player_id,
            {"kind": "public_secret", **record}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._publish_world_rumor(
            "public_secret",
            record["title"],
            f"{tribe.get('name', '某个部落')}把{record['sourceLabel']}中的秘密交给了“{action.get('label', '处理')}”。",
            {
                "tribeId": tribe_id,
                "secretId": record.get("secretId"),
                "recordId": record.get("id"),
                "tone": action.get("rumorTone", action.get("label", "处理"))
            }
        )
