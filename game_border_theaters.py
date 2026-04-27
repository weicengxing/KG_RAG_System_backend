import math
import random
from datetime import datetime

from game_config import *


class GameBorderTheaterMixin:
    def _border_theater_rng(self):
        return getattr(self, "_weather_rng", random)

    def _active_border_theaters(self, tribe: dict) -> list:
        if not tribe:
            return []
        active = []
        now = datetime.now()
        for theater in tribe.get("border_theaters", []) or []:
            if not isinstance(theater, dict) or theater.get("status", "active") != "active":
                continue
            active_until = theater.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        theater["status"] = "expired"
                        theater["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    theater["status"] = "expired"
                    theater["expiredAt"] = now.isoformat()
                    continue
            active.append(theater)
        tribe["border_theaters"] = active[-TRIBE_BORDER_THEATER_LIMIT:]
        return tribe["border_theaters"]

    def _border_theater_anchor(self, tribe: dict) -> dict | None:
        if not tribe:
            return None
        if hasattr(self, "_active_diplomacy_council_sites"):
            councils = self._active_diplomacy_council_sites(tribe)
            if councils:
                site = councils[0]
                return {
                    "kind": "diplomacy_council",
                    "sourceId": site.get("id"),
                    "sourceLabel": site.get("title") or site.get("label", "大议会与边市节"),
                    "label": "边境戏台",
                    "summary": "大议会火圈边腾出一片公开场地，成员可以用比试、旧事和献礼争取传闻里的胜出者。",
                    "x": site.get("x", 0),
                    "z": site.get("z", 0),
                    "participantTribeIds": list(site.get("participantTribeIds") or []),
                    "participantTribeNames": list(site.get("participantTribeNames") or [])
                }
        trade_sites = self._active_trade_route_sites(tribe) if hasattr(self, "_active_trade_route_sites") else []
        trade_sites = sorted(trade_sites, key=lambda item: 0 if item.get("isBorderMarket") else 1)
        if trade_sites:
            site = trade_sites[0]
            partner_id = site.get("partnerTribeId")
            partner_name = site.get("partnerTribeName")
            return {
                "kind": "border_market" if site.get("isBorderMarket") else "trade_route_site",
                "sourceId": site.get("id"),
                "sourceLabel": "边市" if site.get("isBorderMarket") else site.get("label", "交换通路贸易点"),
                "label": "边市戏台",
                "summary": "互市摊位旁围出一块临时戏台，公开比试、讲述和献礼会影响边境口风。",
                "x": site.get("x", 0),
                "z": site.get("z", 0),
                "participantTribeIds": [partner_id] if partner_id else [],
                "participantTribeNames": [partner_name] if partner_name else []
            }
        pacts = self._active_market_pacts(tribe) if hasattr(self, "_active_market_pacts") else []
        if pacts:
            pact = pacts[0]
            camp = tribe.get("camp") or {}
            center = camp.get("center") or {}
            other = self.tribes.get(pact.get("otherTribeId")) if hasattr(self, "tribes") else None
            other_center = ((other or {}).get("camp") or {}).get("center") or {}
            if center and other_center:
                x = (float(center.get("x", 0) or 0) + float(other_center.get("x", 0) or 0)) / 2
                z = (float(center.get("z", 0) or 0) + float(other_center.get("z", 0) or 0)) / 2
            else:
                rng = self._border_theater_rng()
                angle = rng.random() * math.pi * 2
                x = float(center.get("x", 0) or 0) + math.cos(angle) * 26
                z = float(center.get("z", 0) or 0) + math.sin(angle) * 26
            return {
                "kind": "market_pact",
                "sourceId": pact.get("id"),
                "sourceLabel": pact.get("title", "互市约定"),
                "label": "互市戏台",
                "summary": "互市约定旁有人摆出公开戏台，让承诺变成可被围观和传唱的行动。",
                "x": max(-480, min(480, x)),
                "z": max(-480, min(480, z)),
                "participantTribeIds": [pact.get("otherTribeId")] if pact.get("otherTribeId") else [],
                "participantTribeNames": [pact.get("otherTribeName")] if pact.get("otherTribeName") else []
            }
        return None

    def _ensure_border_theater(self, tribe: dict):
        active = self._active_border_theaters(tribe)
        if active:
            return active[0]
        anchor = self._border_theater_anchor(tribe)
        if not anchor:
            return None
        now = datetime.now()
        rng = self._border_theater_rng()
        theater = {
            "id": f"border_theater_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{rng.randint(100, 999)}",
            "type": "border_theater",
            "status": "active",
            "label": anchor.get("label", "边境戏台"),
            "summary": anchor.get("summary", "边境附近出现短时公开戏台。"),
            "sourceKind": anchor.get("kind"),
            "sourceId": anchor.get("sourceId"),
            "sourceLabel": anchor.get("sourceLabel", "边境会场"),
            "x": anchor.get("x", 0),
            "z": anchor.get("z", 0),
            "y": 0,
            "score": 0,
            "target": TRIBE_BORDER_THEATER_TARGET,
            "participants": [],
            "participantTribeIds": anchor.get("participantTribeIds", []),
            "participantTribeNames": anchor.get("participantTribeNames", []),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_BORDER_THEATER_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("border_theaters", []).append(theater)
        tribe["border_theaters"] = tribe["border_theaters"][-TRIBE_BORDER_THEATER_LIMIT:]
        return theater

    def _public_border_theaters(self, tribe: dict) -> list:
        self._ensure_border_theater(tribe)
        return [dict(theater) for theater in self._active_border_theaters(tribe)]

    def _public_border_theater_records(self, tribe: dict) -> list:
        return [
            record for record in (tribe.get("border_theater_records", []) or [])
            if isinstance(record, dict)
        ][-TRIBE_BORDER_THEATER_RECORD_LIMIT:]

    def _border_theater_action_score(self, tribe: dict, player_id: str, action_key: str, action: dict) -> tuple[int, list]:
        member = (tribe.get("members", {}) or {}).get(player_id, {}) or {}
        score = int(action.get("score", 1) or 1)
        reasons = [f"{action.get('label', '行动')}+{score}"]
        contribution = int(member.get("contribution", 0) or 0)
        if action_key == "contest" and contribution >= 6:
            bonus = min(2, contribution // 6)
            score += bonus
            reasons.append(f"贡献+{bonus}")
        if action_key == "story":
            history_count = sum(
                1 for item in tribe.get("history", []) or []
                if isinstance(item, dict) and item.get("actorId") == player_id
            )
            if history_count:
                bonus = min(2, max(1, history_count // 3))
                score += bonus
                reasons.append(f"旧史+{bonus}")
        if action_key == "gift":
            diplomacy = 0
            for other_id in (tribe.get("boundary_relations", {}) or {}).keys():
                relation = (tribe.get("boundary_relations", {}) or {}).get(other_id, {}) or {}
                diplomacy = max(diplomacy, int(relation.get("tradeTrust", 0) or 0) + max(0, int(relation.get("score", 0) or 0)))
            if diplomacy >= 3:
                bonus = 1 if diplomacy < 7 else 2
                score += bonus
                reasons.append(f"外交+{bonus}")
        tune_bonus = self._traveler_song_lineage_border_theater_score_bonus(tribe) if hasattr(self, "_traveler_song_lineage_border_theater_score_bonus") else 0
        if tune_bonus:
            score += tune_bonus
            reasons.append(f"曲牌+{tune_bonus}")
        return max(1, score), reasons

    def _apply_border_theater_rewards(self, tribe: dict, reward: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("food", "食物", "food")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        return parts

    def _apply_border_theater_relations(self, tribe: dict, theater: dict, action: dict, now_text: str) -> tuple[list, set]:
        tribe_id = tribe.get("id")
        affected = {tribe_id}
        parts = []
        relation_delta = int(action.get("relationDelta", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        if not relation_delta and not trust_delta:
            if hasattr(self, "_consume_alliance_signal_hint"):
                for other_id in theater.get("participantTribeIds", []) or []:
                    if not other_id or other_id == tribe_id:
                        continue
                    hint = self._consume_alliance_signal_hint(tribe, other_id, "border_theater")
                    if hint:
                        parts.append(hint)
            return parts, affected
        for other_id in theater.get("participantTribeIds", []) or []:
            if not other_id or other_id == tribe_id:
                continue
            relation = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            relation["lastAction"] = "border_theater"
            relation["lastActionAt"] = now_text
            other = self.tribes.get(other_id) if hasattr(self, "tribes") else None
            if other:
                other_relation = other.setdefault("boundary_relations", {}).setdefault(tribe_id, {})
                if relation_delta:
                    other_relation["score"] = max(-9, min(9, int(other_relation.get("score", 0) or 0) + relation_delta))
                if trust_delta:
                    other_relation["tradeTrust"] = max(0, min(10, int(other_relation.get("tradeTrust", 0) or 0) + trust_delta))
                other_relation["lastAction"] = "incoming_border_theater"
                other_relation["lastActionAt"] = now_text
                affected.add(other_id)
            if hasattr(self, "_consume_alliance_signal_hint"):
                hint = self._consume_alliance_signal_hint(tribe, other_id, "border_theater")
                if hint:
                    parts.append(hint)
        if relation_delta:
            parts.append(f"关系{relation_delta:+d}")
        if trust_delta:
            parts.append(f"信任{trust_delta:+d}")
        return parts, affected

    async def perform_border_theater(self, player_id: str, theater_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_BORDER_THEATER_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知边境戏台行动")
            return
        theater = next((item for item in self._active_border_theaters(tribe) if item.get("id") == theater_id), None)
        if not theater:
            await self._send_tribe_error(player_id, "这处边境戏台已经散场")
            return
        if any(item.get("memberId") == player_id for item in theater.get("participants", []) or []):
            await self._send_tribe_error(player_id, "你已经在这处边境戏台登场")
            return
        food_cost = int(action.get("foodCost", 0) or 0)
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"献礼需要公共食物 {food_cost}")
            return
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost

        now = datetime.now()
        now_text = now.isoformat()
        member = (tribe.get("members", {}) or {}).get(player_id, {}) or {}
        member_name = member.get("name", "成员")
        score, score_parts = self._border_theater_action_score(tribe, player_id, action_key, action)
        reward_parts = self._apply_border_theater_rewards(tribe, action.get("reward", {}))
        relation_parts, affected_tribe_ids = self._apply_border_theater_relations(tribe, theater, action, now_text)
        if food_cost:
            reward_parts.insert(0, f"食物-{food_cost}")
        reward_parts.extend(relation_parts)
        participant = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "登台"),
            "score": score,
            "scoreParts": score_parts,
            "rewardParts": reward_parts,
            "createdAt": now_text
        }
        theater.setdefault("participants", []).append(participant)
        theater["score"] = int(theater.get("score", 0) or 0) + score
        theater["lastActionLabel"] = action.get("label", "登台")
        theater["lastActorName"] = member_name
        theater["rewardLabel"] = "、".join(reward_parts)

        completed = int(theater.get("score", 0) or 0) >= int(theater.get("target", TRIBE_BORDER_THEATER_TARGET) or 1)
        if not completed:
            detail = f"{member_name}在{theater.get('label', '边境戏台')}完成{action.get('label', '登台')}，戏台声势 {theater.get('score')} / {theater.get('target')}。"
            self._add_tribe_history(tribe, "culture", "边境戏台", detail, player_id, {"kind": "border_theater", "theater": theater, "participant": participant})
            await self._notify_tribe(tribe_id, detail)
            await self.broadcast_tribe_state(tribe_id)
            await self._broadcast_current_map()
            return

        winner = max(theater.get("participants", []) or [participant], key=lambda item: int(item.get("score", 0) or 0))
        theater["status"] = "completed"
        theater["completedAt"] = now_text
        theater["winnerName"] = winner.get("memberName", member_name)
        theater["winnerActionLabel"] = winner.get("actionLabel", action.get("label", "登台"))
        final_reward = self._apply_border_theater_rewards(tribe, action.get("finalReward", {}))
        reward_parts.extend(final_reward)
        record = {
            "id": f"border_theater_record_{tribe_id}_{int(now.timestamp() * 1000)}",
            "theaterId": theater.get("id"),
            "label": theater.get("label", "边境戏台"),
            "sourceLabel": theater.get("sourceLabel", "边境会场"),
            "sourceKind": theater.get("sourceKind"),
            "winnerName": theater.get("winnerName"),
            "winnerActionLabel": theater.get("winnerActionLabel"),
            "score": int(theater.get("score", 0) or 0),
            "target": int(theater.get("target", TRIBE_BORDER_THEATER_TARGET) or 1),
            "participantTribeIds": list(theater.get("participantTribeIds", []) or []),
            "participantTribeNames": list(theater.get("participantTribeNames", []) or []),
            "participantNames": [item.get("memberName", "成员") for item in theater.get("participants", []) or []],
            "rewardParts": reward_parts,
            "rumorTone": action.get("rumorTone", "lively"),
            "createdAt": now_text
        }
        tribe.setdefault("border_theater_records", []).append(record)
        tribe["border_theater_records"] = tribe["border_theater_records"][-TRIBE_BORDER_THEATER_RECORD_LIMIT:]
        detail = f"{theater.get('label', '边境戏台')}在{theater.get('sourceLabel', '边境会场')}收束，{record['winnerName']}凭“{record['winnerActionLabel']}”成为这轮传唱的胜出者：{'、'.join(reward_parts) or '边境口风被重新点亮'}。"
        self._add_tribe_history(tribe, "culture", "边境戏台收束", detail, player_id, {"kind": "border_theater_completed", "record": record, "theater": theater})
        await self._publish_world_rumor(
            "culture",
            "边境戏台收束",
            f"{tribe.get('name', '某个部落')}在{theater.get('sourceLabel', '边境会场')}摆下戏台，{record['winnerName']}的{record['winnerActionLabel']}改变了边境传闻的语气。",
            {"tribeId": tribe_id, "theaterId": theater.get("id"), "rumorTone": record.get("rumorTone")}
        )
        await self._notify_tribe(tribe_id, detail)
        for target_id in affected_tribe_ids:
            if target_id:
                await self.broadcast_tribe_state(target_id)
        await self._broadcast_current_map()
