import random
from datetime import datetime

from game_config import *


class GameVisitorMixin:
    def _active_nomad_visitors(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for visitor in tribe.get("nomad_visitors", []) or []:
            if not isinstance(visitor, dict) or visitor.get("status") != "pending":
                continue
            active_until = visitor.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        visitor["status"] = "expired"
                        continue
                except (TypeError, ValueError):
                    visitor["status"] = "expired"
                    continue
            active.append(visitor)
        if len(active) != len(tribe.get("nomad_visitors", []) or []):
            tribe["nomad_visitors"] = active[-TRIBE_NOMAD_VISITOR_LIMIT:]
        return active[-TRIBE_NOMAD_VISITOR_LIMIT:]

    def _active_nomad_visitor_aftereffects(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for effect in tribe.get("nomad_visitor_aftereffects", []) or []:
            if not isinstance(effect, dict):
                continue
            if effect.get("status", "active") not in {"active", "used"}:
                continue
            active_until = effect.get("activeUntil")
            if effect.get("status") == "active" and active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        effect["status"] = "expired"
                        continue
                except (TypeError, ValueError):
                    effect["status"] = "expired"
                    continue
            active.append(effect)
        if len(active) != len(tribe.get("nomad_visitor_aftereffects", []) or []):
            tribe["nomad_visitor_aftereffects"] = active[-TRIBE_NOMAD_VISITOR_AFTEREFFECT_LIMIT:]
        return active[-TRIBE_NOMAD_VISITOR_AFTEREFFECT_LIMIT:]

    def _public_nomad_visitor_aftereffects(self, tribe: dict) -> list:
        return self._active_nomad_visitor_aftereffects(tribe)

    def _visitor_aftereffect_followup_keys(self, visitor: dict, action_key: str) -> list:
        visitor_key = visitor.get("key")
        if action_key == "listen" or visitor_key == "omen_speaker":
            return ["preserve_prophecy"]
        if visitor_key == "lost_clan":
            return ["guest_lodge", "mediate_dispute"]
        if action_key == "mediate":
            return ["mediate_dispute"]
        return []

    def _visitor_aftereffect_bonus(self, kind: str) -> float:
        bonus = 0.0
        for tribe in self.tribes.values():
            for effect in self._active_nomad_visitor_aftereffects(tribe):
                if effect.get("status") != "active" or effect.get("actionKey") != "listen":
                    continue
                if kind == "celestial":
                    bonus += 0.22
                elif kind == "ruin":
                    bonus += 0.35
        return min(0.55, bonus)

    def _mark_visitor_aftereffect_used(self, kind: str, label: str) -> bool:
        for tribe in self.tribes.values():
            for effect in self._active_nomad_visitor_aftereffects(tribe):
                if effect.get("status") != "active" or effect.get("actionKey") != "listen":
                    continue
                effect["status"] = "used"
                effect["usedFor"] = kind
                effect["usedLabel"] = label
                effect["usedAt"] = datetime.now().isoformat()
                return True
        return False

    def _pick_visitor_hint_world_event(self):
        if self._visitor_aftereffect_bonus("ruin") <= 0:
            return None
        if self._weather_rng.random() > self._visitor_aftereffect_bonus("ruin"):
            return None
        self._mark_visitor_aftereffect_used("ruin", "遗迹线索")
        if self._weather_rng.random() < 0.35:
            return {**RARE_WORLD_EVENT_LIBRARY["rare_ruin"], "rare": True}
        return next((item for item in WORLD_EVENT_LIBRARY if item.get("key") == "ruin_clue"), None)

    def _nomad_visitor_edge_position(self, tribe: dict) -> tuple[float, float]:
        camp_center = (tribe.get("camp") or {}).get("center") or {}
        side = random.choice(("north", "south", "east", "west"))
        if side == "north":
            return random.uniform(-420, 420), -485.0
        if side == "south":
            return random.uniform(-420, 420), 485.0
        if side == "east":
            return 485.0, random.uniform(-420, 420)
        if side == "west":
            return -485.0, random.uniform(-420, 420)
        return float(camp_center.get("x", 0) or 0), float(camp_center.get("z", 0) or 0)

    def _build_nomad_visitor(self, tribe: dict, now: datetime) -> dict:
        visitor_keys = list(TRIBE_NOMAD_VISITOR_LIBRARY.keys())
        if hasattr(self, "_personality_weighted_visitor_key"):
            key = self._personality_weighted_visitor_key(tribe, visitor_keys)
        else:
            key = random.choice(visitor_keys)
        config = TRIBE_NOMAD_VISITOR_LIBRARY.get(key, {})
        x, z = self._nomad_visitor_edge_position(tribe)
        visitor = {
            "id": f"nomad_visitor_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "pending",
            "type": "nomad_visitor",
            "key": key,
            "label": config.get("label", "神秘旅人"),
            "title": config.get("title", "神秘旅人来访"),
            "summary": config.get("summary", "地图边缘来了一位带着故事和交易机会的旅人。"),
            "giftLabel": config.get("giftLabel", "口信"),
            "defaultAction": config.get("defaultAction", "barter"),
            "x": x,
            "z": z,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_NOMAD_VISITOR_ACTIVE_MINUTES * 60).isoformat()
        }
        if hasattr(self, "_personality_visitor_hint"):
            hint = self._personality_visitor_hint(tribe, key)
            if hint:
                visitor["personalityHint"] = hint
        if hasattr(self, "_festival_tradition_visitor_hint"):
            hint = self._festival_tradition_visitor_hint(tribe)
            if hint:
                visitor["festivalTraditionHint"] = hint
        return visitor

    async def _maybe_spawn_nomad_visitors(self) -> int:
        spawned = 0
        now = datetime.now()
        for tribe_id, tribe in list(self.tribes.items()):
            if not isinstance(tribe, dict) or not tribe.get("members"):
                continue
            if self._active_nomad_visitors(tribe):
                continue
            chance = TRIBE_NOMAD_VISITOR_CHANCE + min(0.18, max(0, int(tribe.get("trade_reputation", 0) or 0)) * 0.02)
            if hasattr(self, "_dominant_personality_effect") and self._dominant_personality_effect(tribe)[0]:
                chance += 0.04
            if hasattr(self, "_traveler_song_visitor_bonus"):
                chance += self._traveler_song_visitor_bonus(tribe)
            if self._weather_rng.random() > chance:
                continue
            if hasattr(self, "_mark_traveler_song_visitor_hint_used"):
                self._mark_traveler_song_visitor_hint_used(tribe, "下一次来访")
            visitor = self._build_nomad_visitor(tribe, now)
            tribe.setdefault("nomad_visitors", []).append(visitor)
            tribe["nomad_visitors"] = tribe["nomad_visitors"][-TRIBE_NOMAD_VISITOR_LIMIT:]
            detail = f"{visitor.get('title', '神秘旅人来访')}：{visitor.get('summary', '')}"
            self._add_tribe_history(tribe, "trade", "边缘来访者", detail, "", {"kind": "nomad_visitor", **visitor})
            await self._notify_tribe(tribe_id, detail)
            await self.broadcast_tribe_state(tribe_id)
            spawned += 1
        return spawned

    def _apply_nomad_visitor_reward(self, tribe: dict, action: dict, other_tribe_id: str = "") -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            cost = int(action.get(f"{key}Cost", 0) or 0)
            if cost:
                storage[key] = max(0, int(storage.get(key, 0) or 0) - cost)
                parts.append(f"{label}-{cost}")
            amount = int(action.get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        food_cost = int(action.get("foodCost", 0) or 0)
        if food_cost:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) - food_cost)
            parts.append(f"食物-{food_cost}")
        food = int(action.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            parts.append(f"食物+{food}")
        discovery = int(action.get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            parts.append(f"发现+{discovery}")
        renown = int(action.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            parts.append(f"声望+{renown}")
        trade = int(action.get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            parts.append(f"贸易信誉+{trade}")
        relation_delta = int(action.get("relationDelta", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        pressure_relief = int(action.get("pressureRelief", 0) or 0)
        relations = tribe.setdefault("boundary_relations", {})
        target_ids = [other_tribe_id] if other_tribe_id else list(relations.keys())[:2]
        for target_id in [item for item in target_ids if item]:
            relation = relations.setdefault(target_id, {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            if pressure_relief:
                relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relation["lastAction"] = "nomad_visitor"
            relation["lastActionAt"] = datetime.now().isoformat()
        if relation_delta:
            parts.append(f"关系{relation_delta:+d}")
        if trust_delta:
            parts.append(f"贸易信任+{trust_delta}")
        if pressure_relief:
            parts.append(f"战争压力-{pressure_relief}")
        return parts

    async def resolve_nomad_visitor(self, player_id: str, visitor_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        visitor = next((
            item for item in self._active_nomad_visitors(tribe)
            if isinstance(item, dict) and item.get("id") == visitor_id
        ), None)
        if not visitor:
            await self._send_tribe_error(player_id, "这位来访者已经离开")
            return
        action = TRIBE_NOMAD_VISITOR_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知来访者接待方式")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            cost = int(action.get(f"{key}Cost", 0) or 0)
            if cost and int(storage.get(key, 0) or 0) < cost:
                await self._send_tribe_error(player_id, f"接待来访者需要{label}{cost}")
                return
        food_cost = int(action.get("foodCost", 0) or 0)
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"接待来访者需要公共食物{food_cost}")
            return
        reward_parts = self._apply_nomad_visitor_reward(tribe, action)
        if hasattr(self, "_apply_personality_culture_reward"):
            reward_parts.extend(self._apply_personality_culture_reward(tribe, "visitor"))
        now_text = datetime.now().isoformat()
        visitor["status"] = "resolved"
        visitor["resolvedAt"] = now_text
        visitor["resolvedBy"] = player_id
        visitor["resolvedAction"] = action_key
        member = tribe.get("members", {}).get(player_id, {})
        aftereffect = {
            "id": f"visitor_after_{visitor.get('id')}_{action_key}",
            "status": "active",
            "visitorKey": visitor.get("key"),
            "actionKey": action_key,
            "visitorLabel": visitor.get("label", "神秘旅人"),
            "actionLabel": action.get("label", "接待"),
            "label": action.get("afterLabel", "来访余音"),
            "summary": f"{visitor.get('label', '旅人')}留下了{action.get('afterLabel', '来访余音')}，之后的贸易、神话或外交会记住这次接待。",
            "rewardParts": reward_parts,
            "followupKeys": self._visitor_aftereffect_followup_keys(visitor, action_key),
            "followupActions": [
                {"key": key, **TRIBE_NOMAD_VISITOR_AFTEREFFECT_ACTIONS[key]}
                for key in self._visitor_aftereffect_followup_keys(visitor, action_key)
                if key in TRIBE_NOMAD_VISITOR_AFTEREFFECT_ACTIONS
            ],
            "createdAt": now_text,
            "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_NOMAD_VISITOR_AFTEREFFECT_MINUTES * 60).isoformat()
        }
        tribe.setdefault("nomad_visitor_aftereffects", []).append(aftereffect)
        tribe["nomad_visitor_aftereffects"] = tribe["nomad_visitor_aftereffects"][-TRIBE_NOMAD_VISITOR_AFTEREFFECT_LIMIT:]
        song = None
        if hasattr(self, "_schedule_traveler_song"):
            song = self._schedule_traveler_song(
                tribe,
                "visitor",
                visitor.get("id", visitor_id),
                visitor.get("label", "神秘旅人"),
                f"{visitor.get('label', '旅人')}离开后，营地里开始流传关于{action.get('afterLabel', '口信')}的短歌。"
            )
        if hasattr(self, "_schedule_far_reply"):
            self._schedule_far_reply(
                tribe,
                "visitor",
                aftereffect.get("id") or visitor_id,
                "来访者的远方回信",
                f"{visitor.get('label', '神秘旅人')}离开后，旧路上可能带回谢意、求援或新的遗迹口风。",
                None,
                now_text
            )
        if action.get("openMyth") and hasattr(self, "_open_myth_claim"):
            self._open_myth_claim(
                tribe,
                "nomad_visitor",
                visitor.get("label", "神秘旅人"),
                f"{visitor.get('label', '神秘旅人')}带来的预兆正在被族人争论，可以讲成火种、旧路、互市或守边。",
                float(visitor.get("x", 0) or 0),
                float(visitor.get("z", 0) or 0),
                f"nomad_visitor:{visitor.get('id')}",
                member.get("name", "成员")
            )
            reward_parts.append("开启神话解释权")
        detail = f"{member.get('name', '成员')} 对{visitor.get('label', '神秘旅人')}选择“{action.get('label', '接待')}”：{'、'.join(reward_parts) or '留下口信'}。"
        if song:
            detail += f" 营地里出现了“{song.get('label', '旅人谣曲')}”。"
        self._add_tribe_history(tribe, "trade", "接待边缘来访者", detail, player_id, {"kind": "nomad_visitor", "visitor": visitor, "actionKey": action_key, "aftereffect": aftereffect, "travelerSong": song})
        await self._publish_world_rumor(
            "trade",
            "边缘来访者",
            f"{tribe.get('name', '部落')} 接待了{visitor.get('label', '神秘旅人')}，远方口信开始流入营地。",
            {"tribeId": tribe_id, "visitorId": visitor_id, "action": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def resolve_nomad_visitor_aftereffect(self, player_id: str, effect_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        effect = next((
            item for item in self._active_nomad_visitor_aftereffects(tribe)
            if isinstance(item, dict) and item.get("id") == effect_id and item.get("status") == "active"
        ), None)
        if not effect:
            await self._send_tribe_error(player_id, "这段来访余音已经散去")
            return
        if action_key not in (effect.get("followupKeys") or []):
            await self._send_tribe_error(player_id, "这段余音不能这样处理")
            return
        action = TRIBE_NOMAD_VISITOR_AFTEREFFECT_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知来访后续")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            cost = int(action.get(f"{key}Cost", 0) or 0)
            if cost and int(storage.get(key, 0) or 0) < cost:
                await self._send_tribe_error(player_id, f"{action.get('label', '来访后续')}需要{label}{cost}")
                return
        food_cost = int(action.get("foodCost", 0) or 0)
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"{action.get('label', '来访后续')}需要公共食物{food_cost}")
            return

        reward_parts = self._apply_nomad_visitor_reward(tribe, action)
        if hasattr(self, "_apply_personality_culture_reward"):
            reward_parts.extend(self._apply_personality_culture_reward(tribe, "visitor"))
        now_text = datetime.now().isoformat()
        member = tribe.get("members", {}).get(player_id, {})
        effect["status"] = "resolved"
        effect["resolvedAt"] = now_text
        effect["resolvedBy"] = player_id
        effect["resolvedAction"] = action_key
        effect["resolvedActionLabel"] = action.get("label", "来访后续")
        effect["resolvedRewardParts"] = reward_parts
        if action_key == "guest_lodge":
            effect["summary"] = "流浪氏族在营火边短期客居，留下补给、手艺和新的来往口碑。"
        elif action_key == "mediate_dispute":
            effect["summary"] = "来访者带来的纠纷被公开调停，边界误会被压低。"
        elif action_key == "preserve_prophecy":
            effect["status"] = "active"
            effect["followupKeys"] = []
            effect["followupActions"] = []
            effect["preserved"] = True
            effect["summary"] = "预言被刻成短句，下一轮天象或遗迹更容易被族人捕捉。"

        detail = f"{member.get('name', '成员')} 处理了{effect.get('label', '来访余音')}：{action.get('label', '来访后续')}。"
        if reward_parts:
            detail += f" 收获：{'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "trade", "来访余音后续", detail, player_id, {"kind": "nomad_visitor_aftereffect", "effect": effect, "actionKey": action_key})
        await self._publish_world_rumor(
            "trade",
            "来访余音",
            f"{tribe.get('name', '部落')} 把{effect.get('visitorLabel', '神秘旅人')}留下的余音处理成{action.get('label', '后续')}。",
            {"tribeId": tribe_id, "effectId": effect_id, "action": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
