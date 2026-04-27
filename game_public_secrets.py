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
        return parts

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
            "judgeReady": bool(action.get("judgeReady")),
            "storyReady": bool(action.get("storyReady")),
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
