import math
import random
from datetime import datetime
from typing import Optional

from game_config import *


class GameRoutePersonalMixin:
    def _active_player_fatigue(self, player: dict) -> int:
        fatigue = int(player.get("conflict_fatigue", 0) or 0)
        until_text = player.get("conflict_fatigue_until")
        if fatigue and until_text:
            try:
                if datetime.fromisoformat(until_text).timestamp() < datetime.now().timestamp():
                    player["conflict_fatigue"] = 0
                    player.pop("conflict_fatigue_until", None)
                    return 0
            except (TypeError, ValueError):
                pass
        return max(0, min(PLAYER_CONFLICT_FATIGUE_MAX, fatigue))

    def _active_personal_guard(self, player: dict):
        guard = player.get("personal_guard") if isinstance(player.get("personal_guard"), dict) else None
        if not guard:
            return None
        try:
            if datetime.fromisoformat(guard.get("activeUntil")).timestamp() < datetime.now().timestamp():
                player.pop("personal_guard", None)
                return None
        except (TypeError, ValueError):
            player.pop("personal_guard", None)
            return None
        return guard

    def _active_personal_inspiration(self, player: dict):
        inspiration = player.get("personal_inspiration") if isinstance(player.get("personal_inspiration"), dict) else None
        if not inspiration:
            return None
        try:
            if datetime.fromisoformat(inspiration.get("activeUntil")).timestamp() < datetime.now().timestamp():
                player.pop("personal_inspiration", None)
                return None
        except (TypeError, ValueError):
            player.pop("personal_inspiration", None)
            return None
        return inspiration

    def _personal_renown_title(self, renown: int) -> dict:
        for title in PLAYER_RENOWN_TITLES:
            if renown >= int(title.get("min", 0) or 0):
                return dict(title)
        return dict(PLAYER_RENOWN_TITLES[-1])

    def _personal_title_bonus(self, player: dict, key: str) -> int:
        title = self._personal_renown_title(int(player.get("personal_renown", 0) or 0))
        return int(title.get(key, 0) or 0)

    def _personal_guard_radius(self, player: dict) -> int:
        return PLAYER_CONFLICT_GUARD_RADIUS + self._personal_title_bonus(player, "guardRadiusBonus")

    def _personal_fatigue_recovery_seconds(self, player: dict) -> int:
        return max(60, PLAYER_CONFLICT_FATIGUE_DECAY_SECONDS - self._personal_title_bonus(player, "fatigueRecoveryBonusSeconds"))

    def _active_personal_identity_cooldown(self, player: dict) -> str:
        cooldown_until = player.get("personal_identity_cooldown_until")
        if not cooldown_until:
            return ""
        try:
            if datetime.fromisoformat(cooldown_until).timestamp() <= datetime.now().timestamp():
                player.pop("personal_identity_cooldown_until", None)
                return ""
        except (TypeError, ValueError):
            player.pop("personal_identity_cooldown_until", None)
            return ""
        return cooldown_until

    def _personal_identity_state(self, player: dict, personal_renown: Optional[int] = None) -> dict:
        identity_key = player.get("personal_identity")
        identity = PLAYER_IDENTITY_OPTIONS.get(identity_key)
        renown = int(personal_renown if personal_renown is not None else player.get("personal_renown", 0) or 0)
        options = []
        for key, option in PLAYER_IDENTITY_OPTIONS.items():
            min_renown = int(option.get("minRenown", PLAYER_IDENTITY_MIN_RENOWN) or 0)
            options.append({
                "key": key,
                "label": option.get("label", key),
                "actionLabel": option.get("actionLabel", option.get("label", key)),
                "summary": option.get("summary", ""),
                "minRenown": min_renown,
                "available": renown >= min_renown
            })
        return {
            "key": identity_key if identity else "",
            "label": identity.get("label") if identity else "",
            "actionLabel": identity.get("actionLabel") if identity else "",
            "summary": identity.get("summary") if identity else "",
            "options": options,
            "cooldownUntil": self._active_personal_identity_cooldown(player),
            "cooldownSeconds": PLAYER_IDENTITY_ACTION_COOLDOWN_SECONDS,
            "minRenown": PLAYER_IDENTITY_MIN_RENOWN
        }

    def _personal_relation_label(self, score: int) -> str:
        if score >= PLAYER_RELATION_BEST_FRIEND_THRESHOLD:
            return "挚友"
        if score >= PLAYER_RELATION_FRIEND_THRESHOLD:
            return "可靠同伴"
        if score <= PLAYER_RELATION_NEMESIS_THRESHOLD:
            return "宿敌"
        if score <= PLAYER_RELATION_RIVAL_THRESHOLD:
            return "劲敌"
        if score > 0:
            return "熟人"
        if score < 0:
            return "嫌隙"
        return "陌生"

    def _public_personal_relations(self, player: dict) -> list:
        relations = []
        for target_id, relation in (player.get("personal_relations", {}) or {}).items():
            if not isinstance(relation, dict):
                continue
            score = int(relation.get("score", 0) or 0)
            relations.append({
                "targetId": target_id,
                "targetName": relation.get("targetName") or self.players.get(target_id, {}).get("name", "玩家"),
                "score": score,
                "label": self._personal_relation_label(score),
                "lastDelta": int(relation.get("lastDelta", 0) or 0),
                "lastSource": relation.get("lastSource", ""),
                "lastKind": relation.get("lastKind", ""),
                "updatedAt": relation.get("updatedAt", ""),
                "history": list(relation.get("history", []) or [])[-PLAYER_RELATION_HISTORY_LIMIT:]
            })
        return sorted(
            relations,
            key=lambda item: (abs(item.get("score", 0)), item.get("updatedAt", "")),
            reverse=True
        )[:PLAYER_RELATION_STATUS_LIMIT]

    def _record_player_relation(self, actor_id: str, target_id: str, delta: int, source_label: str, kind: str) -> Optional[dict]:
        if not actor_id or not target_id or actor_id == target_id or not delta:
            return None
        actor = self.players.get(actor_id)
        target = self.players.get(target_id)
        if not actor or not target:
            return None
        now_text = datetime.now().isoformat()

        def update(owner: dict, other_id: str, other_name: str) -> dict:
            relations = owner.setdefault("personal_relations", {})
            relation = relations.setdefault(other_id, {})
            before = int(relation.get("score", 0) or 0)
            score = max(PLAYER_RELATION_SCORE_MIN, min(PLAYER_RELATION_SCORE_MAX, before + int(delta)))
            label = self._personal_relation_label(score)
            event = {
                "targetId": other_id,
                "targetName": other_name,
                "delta": int(delta),
                "score": score,
                "label": label,
                "sourceLabel": source_label,
                "kind": kind,
                "createdAt": now_text
            }
            history = list(relation.get("history", []) or [])
            history.append(event)
            relation.update({
                "targetName": other_name,
                "score": score,
                "label": label,
                "lastDelta": int(delta),
                "lastSource": source_label,
                "lastKind": kind,
                "updatedAt": now_text,
                "history": history[-PLAYER_RELATION_HISTORY_LIMIT:]
            })
            return event

        actor_event = update(actor, target_id, target.get("name", "玩家"))
        update(target, actor_id, actor.get("name", "玩家"))
        return {
            "actorId": actor_id,
            "actorName": actor.get("name", "玩家"),
            "targetId": target_id,
            "targetName": target.get("name", "玩家"),
            "delta": int(delta),
            "score": actor_event.get("score", 0),
            "label": actor_event.get("label", "陌生"),
            "sourceLabel": source_label,
            "kind": kind,
            "createdAt": now_text
        }

    def _public_personal_conflict_status(self, player: dict) -> dict:
        fatigue = self._active_player_fatigue(player)
        guard = self._active_personal_guard(player)
        inspiration = self._active_personal_inspiration(player)
        personal_renown = int(player.get("personal_renown", 0) or 0)
        renown_title = self._personal_renown_title(personal_renown)
        return {
            "fatigue": fatigue,
            "fatigueMax": PLAYER_CONFLICT_FATIGUE_MAX,
            "fatigueUntil": player.get("conflict_fatigue_until") if fatigue else "",
            "guardUntil": guard.get("activeUntil") if guard else "",
            "guardTargetName": guard.get("targetName") if guard else "",
            "guardRadius": guard.get("radius", self._personal_guard_radius(player)) if guard else self._personal_guard_radius(player),
            "personalRenown": personal_renown,
            "renownTitle": renown_title,
            "inspirationUntil": inspiration.get("activeUntil") if inspiration else "",
            "inspirationSourceName": inspiration.get("sourceName") if inspiration else "",
            "inspirationContribution": int(inspiration.get("contributionBonus", 0) or 0) if inspiration else 0,
            "inspireMinRenown": PLAYER_CONFLICT_INSPIRE_MIN_RENOWN,
            "fatigueDecaySeconds": self._personal_fatigue_recovery_seconds(player),
            "fatigueRecoveryBonusSeconds": int(renown_title.get("fatigueRecoveryBonusSeconds", 0) or 0),
            "sparTrainingBonus": int(renown_title.get("sparTrainingBonus", 0) or 0),
            "skirmishContributionBonus": int(renown_title.get("skirmishContributionBonus", 0) or 0),
            "guardSeconds": PLAYER_CONFLICT_GUARD_SECONDS,
            "inspireSeconds": PLAYER_CONFLICT_INSPIRE_SECONDS,
            "personalRelations": self._public_personal_relations(player),
            "darkOath": self._public_personal_dark_oath(player),
            "identity": self._personal_identity_state(player, personal_renown)
        }

    async def choose_personal_identity(self, player_id: str, identity_key: str):
        player = self.players.get(player_id)
        option = PLAYER_IDENTITY_OPTIONS.get(identity_key)
        if not player or not option:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "没有找到这个身份"})
            return
        personal_renown = int(player.get("personal_renown", 0) or 0)
        min_renown = int(option.get("minRenown", PLAYER_IDENTITY_MIN_RENOWN) or 0)
        if personal_renown < min_renown:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": f"个人声望至少需要 {min_renown} 才能选择身份"})
            return
        player["personal_identity"] = identity_key
        status = self._public_personal_conflict_status(player)
        await self.send_personal_message(player_id, {
            "type": "personal_identity_result",
            "action": "choose",
            "identity": status.get("identity"),
            "message": f"已选择身份：{option.get('label', '身份')}",
            "status": status
        })
        await self.send_personal_conflict_status(player_id)

    def _apply_identity_task_discount(self, tribe: dict, discount: int) -> str:
        if discount <= 0:
            return ""
        task_groups = [
            ("war_repair_tasks", ("woodCost", "stoneCost")),
            ("war_revival_tasks", ("woodCost",))
        ]
        for group_key, cost_keys in task_groups:
            for task in tribe.get(group_key, []) or []:
                if not isinstance(task, dict) or task.get("status") != "pending":
                    continue
                changed = []
                for key in cost_keys:
                    before = int(task.get(key, 0) or 0)
                    if before <= 0:
                        continue
                    after = max(0, before - discount)
                    task[key] = after
                    if after != before:
                        changed.append(key)
                if changed:
                    task["identityBonusLabel"] = "石匠整修降低了后续消耗"
                    return task.get("title", "战后任务")
        return ""

    async def perform_personal_identity_action(self, player_id: str):
        player = self.players.get(player_id)
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not player or not tribe:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "请先加入一个部落"})
            return
        identity_key = player.get("personal_identity")
        option = PLAYER_IDENTITY_OPTIONS.get(identity_key)
        if not option:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "先选择一个身份"})
            return
        cooldown_until = self._active_personal_identity_cooldown(player)
        if cooldown_until:
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "身份动作还在冷却"})
            return
        if int(option.get("requiresHistory", 0) or 0) and len(tribe.get("history", []) or []) < int(option.get("requiresHistory", 0) or 0):
            await self.send_personal_message(player_id, {"type": "personal_identity_error", "message": "部落历史还不够讲述者复述"})
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(option.get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        discovery = int(option.get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现进度+{discovery}")
        renown = int(option.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"部落声望+{renown}")
        personal_renown = int(option.get("personalRenown", 0) or 0)
        if personal_renown:
            player["personal_renown"] = int(player.get("personal_renown", 0) or 0) + personal_renown
            reward_parts.append(f"个人声望+{personal_renown}")
        discounted_task = self._apply_identity_task_discount(tribe, int(option.get("taskDiscount", 0) or 0))
        if discounted_task:
            reward_parts.append(f"{discounted_task}消耗降低")

        now_text = datetime.now().isoformat()
        player["personal_identity_cooldown_until"] = datetime.fromtimestamp(datetime.now().timestamp() + PLAYER_IDENTITY_ACTION_COOLDOWN_SECONDS).isoformat()
        member = tribe.get("members", {}).get(player_id, {})
        detail = f"{member.get('name', player.get('name', '成员'))} 以{option.get('label', '身份')}身份执行{option.get('actionLabel', '身份动作')}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(
            tribe,
            "ritual",
            option.get("actionLabel", "身份动作"),
            detail,
            player_id,
            {
                "kind": "personal_identity",
                "identityKey": identity_key,
                "identityLabel": option.get("label"),
                "actionLabel": option.get("actionLabel"),
                "rewardParts": reward_parts,
                "memberName": member.get("name", player.get("name", "成员"))
            }
        )
        tribe.setdefault("personal_conflicts", []).append({
            "actionLabel": option.get("actionLabel", "身份动作"),
            "actorName": member.get("name", player.get("name", "成员")),
            "targetName": tribe.get("name", "部落"),
            "winnerName": option.get("label", "身份"),
            "identityLabel": option.get("label"),
            "identityActionLabel": option.get("actionLabel"),
            "identityRewardParts": reward_parts,
            "createdAt": now_text
        })
        tribe["personal_conflicts"] = tribe["personal_conflicts"][-8:]
        status = self._public_personal_conflict_status(player)
        await self.send_personal_message(player_id, {
            "type": "personal_identity_result",
            "action": "perform",
            "identity": status.get("identity"),
            "message": detail,
            "rewardParts": reward_parts,
            "status": status
        })
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.send_personal_conflict_status(player_id)

    def _find_personal_guardian(self, actor_id: str, target_id: str, target_tribe_id: str):
        if not actor_id or not target_id or not target_tribe_id:
            return None, None
        target = self.players.get(target_id)
        if not target:
            return None, None
        for guardian_id, guardian in self.players.items():
            if guardian_id in {actor_id, target_id}:
                continue
            if self.player_tribes.get(guardian_id) != target_tribe_id:
                continue
            guard = self._active_personal_guard(guardian)
            if not guard or guard.get("targetId") != actor_id:
                continue
            dx = float(guardian.get("x", 0) or 0) - float(target.get("x", 0) or 0)
            dz = float(guardian.get("z", 0) or 0) - float(target.get("z", 0) or 0)
            radius = float(guard.get("radius", self._personal_guard_radius(guardian)) or PLAYER_CONFLICT_GUARD_RADIUS)
            if dx * dx + dz * dz <= radius * radius:
                return guardian_id, guardian
        return None, None

    async def send_personal_conflict_status(self, player_id: str):
        player = self.players.get(player_id)
        if player:
            await self.send_personal_message(player_id, {
                "type": "personal_conflict_status",
                "status": self._public_personal_conflict_status(player)
            })

    async def resolve_personal_conflict(self, player_id: str, target_id: str, action_key: str):
        actor = self.players.get(player_id)
        target = self.players.get(target_id)
        action = PLAYER_CONFLICT_ACTIONS.get(action_key)
        if not actor or not target or not action or player_id == target_id:
            await self.send_personal_message(player_id, {"type": "personal_conflict_error", "message": "无法发起这次个人冲突"})
            return
        actor_tribe_id = self.player_tribes.get(player_id)
        target_tribe_id = self.player_tribes.get(target_id)
        if action.get("sameTribeOnly") and actor_tribe_id != target_tribe_id:
            await self.send_personal_message(player_id, {"type": "personal_conflict_error", "message": f"{action.get('label', '行动')}只能对同部落成员发起"})
            return

        dx = float(target.get("x", 0) or 0) - float(actor.get("x", 0) or 0)
        dz = float(target.get("z", 0) or 0) - float(actor.get("z", 0) or 0)
        if dx * dx + dz * dz > PLAYER_CONFLICT_DISTANCE * PLAYER_CONFLICT_DISTANCE:
            await self.send_personal_message(player_id, {"type": "personal_conflict_error", "message": "靠近目标玩家后才能发起冲突"})
            return

        if action.get("guard"):
            guard_radius = self._personal_guard_radius(actor)
            actor["personal_guard"] = {
                "targetId": target_id,
                "targetName": target.get("name", "玩家"),
                "protectTribeId": actor_tribe_id,
                "radius": guard_radius,
                "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + PLAYER_CONFLICT_GUARD_SECONDS).isoformat()
            }
            await self.send_personal_message(player_id, {
                "type": "personal_conflict_result",
                "actionKey": action_key,
                "actionLabel": action.get("label", "守势"),
                "actorId": player_id,
                "actorName": actor.get("name", "玩家"),
                "targetId": target_id,
                "targetName": target.get("name", "玩家"),
                "winnerId": player_id,
                "guardUntil": actor["personal_guard"]["activeUntil"],
                "guardRadius": guard_radius,
                "fatigue": actor.get("conflict_fatigue", 0),
                "status": self._public_personal_conflict_status(actor),
                "renownGain": 0
            })
            await self.send_personal_conflict_status(player_id)
            return

        if action.get("inspire"):
            personal_renown = int(actor.get("personal_renown", 0) or 0)
            if personal_renown < PLAYER_CONFLICT_INSPIRE_MIN_RENOWN:
                await self.send_personal_message(player_id, {
                    "type": "personal_conflict_error",
                    "message": f"个人声望至少需要 {PLAYER_CONFLICT_INSPIRE_MIN_RENOWN} 才能鼓舞同伴"
                })
                return
            title = self._personal_renown_title(personal_renown)
            target["personal_inspiration"] = {
                "sourceId": player_id,
                "sourceName": actor.get("name", "玩家"),
                "sourceTitle": title.get("title"),
                "contributionBonus": PLAYER_CONFLICT_INSPIRE_CONTRIBUTION,
                "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + PLAYER_CONFLICT_INSPIRE_SECONDS).isoformat()
            }
            relation_update = self._record_player_relation(
                player_id,
                target_id,
                PLAYER_RELATION_INSPIRE_DELTA,
                action.get("label", "鼓舞"),
                "inspire"
            )
            result = {
                "type": "personal_conflict_result",
                "actionKey": action_key,
                "actionLabel": action.get("label", "鼓舞"),
                "actorId": player_id,
                "actorName": actor.get("name", "玩家"),
                "targetId": target_id,
                "targetName": target.get("name", "玩家"),
                "winnerId": player_id,
                "inspirationUntil": target["personal_inspiration"]["activeUntil"],
                "inspirationContribution": PLAYER_CONFLICT_INSPIRE_CONTRIBUTION,
                "renownTitle": title,
                "status": self._public_personal_conflict_status(actor),
                "targetStatus": self._public_personal_conflict_status(target),
                "renownGain": 0,
                "relationship": relation_update
            }
            record = {
                "actionLabel": result["actionLabel"],
                "actorName": result["actorName"],
                "targetName": result["targetName"],
                "winnerName": result["actorName"],
                "renownTitle": title.get("title"),
                "inspirationContribution": PLAYER_CONFLICT_INSPIRE_CONTRIBUTION,
                "inspirationUntil": target["personal_inspiration"]["activeUntil"],
                "relationshipLabel": relation_update.get("label") if relation_update else "",
                "relationshipDelta": relation_update.get("delta") if relation_update else 0,
                "relationshipScore": relation_update.get("score") if relation_update else 0,
                "relationshipSource": relation_update.get("sourceLabel") if relation_update else "",
                "createdAt": datetime.now().isoformat()
            }
            tribe = self.tribes.get(actor_tribe_id)
            if tribe:
                tribe.setdefault("personal_conflicts", []).append(record)
                tribe["personal_conflicts"] = tribe["personal_conflicts"][-8:]
            nearby = set(self._players_in_range(player_id, self.aoi_radius)) | set(self._players_in_range(target_id, self.aoi_radius)) | {player_id, target_id}
            await self.broadcast(result, include=list(nearby))
            await self.send_personal_conflict_status(player_id)
            await self.send_personal_conflict_status(target_id)
            if actor_tribe_id:
                await self.broadcast_tribe_state(actor_tribe_id)
            return

        cooldowns = actor.setdefault("personal_conflict_cooldowns", {})
        last_action_at = cooldowns.get(target_id)
        if last_action_at:
            try:
                elapsed = datetime.now().timestamp() - datetime.fromisoformat(last_action_at).timestamp()
                if elapsed < PLAYER_CONFLICT_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil(PLAYER_CONFLICT_COOLDOWN_SECONDS - elapsed))
                    await self.send_personal_message(player_id, {"type": "personal_conflict_error", "message": f"刚刚冲突过，还需 {remaining} 秒"})
                    return
            except (TypeError, ValueError):
                pass

        actor_fatigue = self._active_player_fatigue(actor)
        target_fatigue = self._active_player_fatigue(target)
        actor_roll = random.randint(1, 6) + max(0, 3 - actor_fatigue)
        target_roll = random.randint(1, 6) + max(0, 3 - target_fatigue)
        target_guard = self._active_personal_guard(target)
        guardian_id = None
        guardian = None
        guard_active = False
        if target_guard and target_guard.get("targetId") == player_id:
            try:
                guard_active = datetime.fromisoformat(target_guard.get("activeUntil")).timestamp() >= datetime.now().timestamp()
            except (TypeError, ValueError):
                guard_active = False
        if not guard_active:
            guardian_id, guardian = self._find_personal_guardian(player_id, target_id, target_tribe_id)
            guard_active = bool(guardian)
        if guard_active:
            target_roll += 2
        actor_won = actor_roll >= target_roll
        fatigue_gain = int(action.get("fatigue", 1) or 1)
        if guard_active:
            fatigue_gain = max(0, fatigue_gain - 1)
            if guardian:
                guardian.pop("personal_guard", None)
            else:
                target.pop("personal_guard", None)
        target["conflict_fatigue"] = min(PLAYER_CONFLICT_FATIGUE_MAX, target_fatigue + fatigue_gain)
        target_recovery_seconds = self._personal_fatigue_recovery_seconds(target)
        actor_recovery_seconds = self._personal_fatigue_recovery_seconds(actor)
        target["conflict_fatigue_until"] = datetime.fromtimestamp(datetime.now().timestamp() + target_recovery_seconds).isoformat()
        if action_key == "challenge" and not actor_won:
            actor["conflict_fatigue"] = min(PLAYER_CONFLICT_FATIGUE_MAX, actor_fatigue + 1)
            actor["conflict_fatigue_until"] = datetime.fromtimestamp(datetime.now().timestamp() + actor_recovery_seconds).isoformat()

        renown_gain = int(action.get("renown", 0) or 0)
        if actor_won:
            actor["personal_renown"] = int(actor.get("personal_renown", 0) or 0) + renown_gain
        training_reward = int(action.get("trainingRenown", 0) or 0)
        training_bonus = 0
        if training_reward and actor_tribe_id == target_tribe_id:
            training_bonus = max(
                self._personal_title_bonus(actor, "sparTrainingBonus"),
                self._personal_title_bonus(target, "sparTrainingBonus")
            )
            training_reward += training_bonus
            actor["personal_renown"] = int(actor.get("personal_renown", 0) or 0) + training_reward
            target["personal_renown"] = int(target.get("personal_renown", 0) or 0) + training_reward
        cooldowns[target_id] = datetime.now().isoformat()

        if actor_tribe_id and target_tribe_id and actor_tribe_id != target_tribe_id:
            relation_delta = int(action.get("relationDelta", 0) or 0)
            actor_tribe = self.tribes.get(actor_tribe_id)
            target_tribe = self.tribes.get(target_tribe_id)
            if actor_tribe:
                progress = actor_tribe.setdefault("boundary_relations", {}).setdefault(target_tribe_id, {})
                progress["score"] = max(-9, min(9, int(progress.get("score", 0) or 0) + relation_delta))
                progress["lastAction"] = f"personal:{action_key}"
                progress["lastActionAt"] = cooldowns[target_id]
            if target_tribe:
                progress = target_tribe.setdefault("boundary_relations", {}).setdefault(actor_tribe_id, {})
                progress["score"] = max(-9, min(9, int(progress.get("score", 0) or 0) + relation_delta))
                progress["lastAction"] = f"incoming_personal:{action_key}"
                progress["lastActionAt"] = cooldowns[target_id]

        relation_update = self._record_player_relation(
            player_id,
            target_id,
            int(action.get("personalRelationDelta", 0) or 0),
            action.get("label", "个人互动"),
            action_key
        )

        knockback = float(action.get("knockback", 0) or 0)
        if knockback and actor_won:
            length = math.sqrt(dx * dx + dz * dz) or 0.001
            new_x = float(target.get("x", 0) or 0) + (dx / length) * knockback
            new_z = float(target.get("z", 0) or 0) + (dz / length) * knockback
            new_x, new_z, _ = self._clamp_to_shore(new_x, new_z, margin=PLAYER_RADIUS)
            target["x"] = new_x
            target["z"] = new_z
            await self.send_personal_message(target_id, {
                "type": "position_correction",
                "data": {"x": new_x, "y": target.get("y", 2), "z": new_z}
            })

        result = {
            "type": "personal_conflict_result",
            "actionKey": action_key,
            "actionLabel": action.get("label", "冲突"),
            "actorId": player_id,
            "actorName": actor.get("name", "玩家"),
            "targetId": target_id,
            "targetName": target.get("name", "玩家"),
            "winnerId": player_id if actor_won else target_id,
            "winnerName": actor.get("name", "玩家") if actor_won else target.get("name", "玩家"),
            "fatigue": target.get("conflict_fatigue", 0),
            "fatigueUntil": target.get("conflict_fatigue_until"),
            "fatigueGain": fatigue_gain,
            "actorRoll": actor_roll,
            "targetRoll": target_roll,
            "actorFatigue": actor.get("conflict_fatigue", 0),
            "targetFatigue": target.get("conflict_fatigue", 0),
            "cooldownSeconds": PLAYER_CONFLICT_COOLDOWN_SECONDS,
            "guarded": guard_active,
            "guardianId": guardian_id or (target_id if guard_active else ""),
            "guardianName": (guardian.get("name", "成员") if guardian else (target.get("name", "玩家") if guard_active else "")),
            "trainingReward": training_reward,
            "trainingBonus": training_bonus,
            "targetRecoverySeconds": target_recovery_seconds,
            "actorRecoverySeconds": actor_recovery_seconds,
            "renownGain": renown_gain if actor_won else 0,
            "relationship": relation_update
        }
        record = {
            "actionLabel": result["actionLabel"],
            "actorName": result["actorName"],
            "targetName": result["targetName"],
            "winnerName": result["actorName"] if actor_won else result["targetName"],
            "actorRoll": actor_roll,
            "targetRoll": target_roll,
            "fatigueGain": fatigue_gain,
            "targetFatigue": target.get("conflict_fatigue", 0),
            "fatigueUntil": target.get("conflict_fatigue_until"),
            "renownGain": renown_gain if actor_won else 0,
            "trainingReward": training_reward,
            "trainingBonus": training_bonus,
            "guarded": guard_active,
            "guardianName": result.get("guardianName", ""),
            "targetRecoverySeconds": target_recovery_seconds,
            "relationshipLabel": relation_update.get("label") if relation_update else "",
            "relationshipDelta": relation_update.get("delta") if relation_update else 0,
            "relationshipScore": relation_update.get("score") if relation_update else 0,
            "relationshipSource": relation_update.get("sourceLabel") if relation_update else "",
            "createdAt": cooldowns[target_id]
        }
        for tribe_id in {actor_tribe_id, target_tribe_id}:
            tribe = self.tribes.get(tribe_id)
            if tribe:
                tribe.setdefault("personal_conflicts", []).append(record)
                tribe["personal_conflicts"] = tribe["personal_conflicts"][-8:]
        nearby = set(self._players_in_range(player_id, self.aoi_radius)) | set(self._players_in_range(target_id, self.aoi_radius)) | {player_id, target_id}
        await self.broadcast(result, include=list(nearby))
        await self.broadcast({
            "type": "player_move",
            "playerId": target_id,
            "data": {
                "x": target.get("x", 0),
                "y": target.get("y", 2),
                "z": target.get("z", 0),
                "conflict_fatigue": target.get("conflict_fatigue", 0),
                "conflict_fatigue_until": target.get("conflict_fatigue_until"),
                "personal_renown": target.get("personal_renown", 0)
            }
        }, exclude=[target_id], include=list(nearby))
        await self.send_personal_conflict_status(player_id)
        await self.send_personal_conflict_status(target_id)
        if guardian_id:
            await self.send_personal_conflict_status(guardian_id)

        if actor_tribe_id:
            await self.broadcast_tribe_state(actor_tribe_id)
        if target_tribe_id and target_tribe_id != actor_tribe_id:
            await self.broadcast_tribe_state(target_tribe_id)
