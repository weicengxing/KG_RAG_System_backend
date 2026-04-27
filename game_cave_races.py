from datetime import datetime
import random

from game_config import *


class GameCaveRaceMixin:
    def _active_cave_races(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        changed = False
        for race in tribe.get("cave_races", []) or []:
            if not isinstance(race, dict) or race.get("status") in {"resolved", "expired"}:
                continue
            active_until = race.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        race["status"] = "expired"
                        race["expiredAt"] = now.isoformat()
                        changed = True
                        continue
                except (TypeError, ValueError):
                    pass
            race["type"] = "cave_rescue_clue" if race.get("status") == "rescue" else "rare_cave_race"
            active.append(race)
        if changed:
            tribe["cave_races"] = active[-TRIBE_CAVE_RACE_LIMIT:]
        return active[-TRIBE_CAVE_RACE_LIMIT:]

    def _public_cave_races(self, tribe: dict) -> list:
        public = []
        for race in self._active_cave_races(tribe):
            rescue = race.get("rescue") or {}
            public.append({
                "id": race.get("id"),
                "type": "cave_rescue_clue" if race.get("status") == "rescue" else "rare_cave_race",
                "status": race.get("status", "active"),
                "title": race.get("title", "短时稀有洞穴"),
                "label": race.get("label", "短时稀有洞穴"),
                "summary": race.get("summary", ""),
                "caveLabel": race.get("caveLabel", "未知洞穴"),
                "sourceTribeName": race.get("sourceTribeName", "某个部落"),
                "firstExplorerTribeId": race.get("firstExplorerTribeId", ""),
                "firstExplorerTribeName": race.get("firstExplorerTribeName", ""),
                "firstExplorerName": race.get("firstExplorerName", ""),
                "x": race.get("x", 0),
                "z": race.get("z", 0),
                "activeUntil": race.get("activeUntil"),
                "rewardParts": self._cave_race_reward_parts(TRIBE_CAVE_RACE_FIRST_REWARD),
                "rescue": rescue if rescue else None,
                "canClaim": race.get("status") == "active" and not race.get("firstExplorerTribeId"),
                "canRescue": race.get("status") == "rescue" and rescue.get("status") == "missing"
            })
        return public

    def _cave_race_reward_parts(self, reward: dict) -> list:
        labels = {
            "renown": "声望",
            "discoveryProgress": "发现",
            "tradeReputation": "贸易信誉"
        }
        return [
            f"{label}+{int((reward or {}).get(key, 0) or 0)}"
            for key, label in labels.items()
            if int((reward or {}).get(key, 0) or 0)
        ]

    def _apply_cave_race_reward(self, tribe: dict, reward: dict) -> list:
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

    def _cave_race_supports(self, tribe: dict) -> tuple[list, int]:
        supports = []
        bonus = 0
        if "deep_cave_echo" in (tribe.get("discoveries", []) or []):
            supports.append({"label": "幽洞回声", "bonus": 1})
            bonus += 1
        if self._has_tribe_structure_type(tribe, "tribe_road"):
            supports.append({"label": "营地道路", "bonus": 1})
            bonus += 1
        if self._has_tribe_structure_type(tribe, "tribe_totem"):
            supports.append({"label": "公共图腾", "bonus": 1})
            bonus += 1
        if int(tribe.get("tamed_beasts", 0) or 0) > 0:
            supports.append({"label": "幼兽嗅探", "bonus": 1})
            bonus += 1
        return supports, bonus

    async def _maybe_open_rare_cave_race(self, tribe: dict, player_id: str, cave_label: str, route_key: str, depth: int, finds: int) -> dict | None:
        if not tribe or int(depth or 0) < TRIBE_CAVE_RACE_DISCOVERY_DEPTH:
            return None
        if route_key not in {"deep", "risky"} and int(finds or 0) < 3:
            return None
        active_races = [
            race
            for other in self.tribes.values()
            for race in self._active_cave_races(other)
            if race.get("caveLabel") == cave_label and not race.get("firstExplorerTribeId")
        ]
        if active_races:
            return None

        now = datetime.now()
        player = self.players.get(player_id, {})
        try:
            x = float(player.get("x", 0) or 0)
            z = float(player.get("z", 0) or 0)
        except (TypeError, ValueError):
            x, z = 0.0, 0.0
        race_id = f"cave_race_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}"
        base_race = {
            "id": race_id,
            "status": "active",
            "title": "短时稀有洞穴",
            "label": f"{cave_label}稀有岔洞",
            "summary": "洞内风声短暂改道，多部落都能争取首探；失败只会留下失踪线索，可逐步营救。",
            "caveLabel": cave_label,
            "sourceTribeId": tribe.get("id"),
            "sourceTribeName": tribe.get("name", "部落"),
            "x": max(-490, min(490, x)),
            "z": max(-490, min(490, z)),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_CAVE_RACE_ACTIVE_MINUTES * 60).isoformat()
        }
        for target in self.tribes.values():
            races = self._active_cave_races(target)
            target["cave_races"] = [*races, dict(base_race)][-TRIBE_CAVE_RACE_LIMIT:]
        await self._publish_world_rumor(
            "cave",
            "稀有洞穴短时开启",
            f"{tribe.get('name', '部落')}在{cave_label}听见了岔洞回声，多部落可以抢首探。",
            {"raceId": race_id, "sourceTribeId": tribe.get("id")}
        )
        await self._broadcast_all_cave_race_states()
        return base_race

    async def _broadcast_all_cave_race_states(self):
        for tribe_id in list(self.tribes.keys()):
            await self.broadcast_tribe_state(tribe_id)

    def _sync_cave_race_first_result(self, race_id: str, tribe: dict, member_name: str):
        for target in self.tribes.values():
            for race in target.get("cave_races", []) or []:
                if not isinstance(race, dict) or race.get("id") != race_id:
                    continue
                race["firstExplorerTribeId"] = tribe.get("id")
                race["firstExplorerTribeName"] = tribe.get("name", "部落")
                race["firstExplorerName"] = member_name
                race["firstExploredAt"] = datetime.now().isoformat()
                if race.get("status") == "active":
                    race["status"] = "claimed"

    async def claim_cave_race_first_explore(self, player_id: str, race_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        race = next((item for item in self._active_cave_races(tribe) if item.get("id") == race_id), None)
        if not race:
            await self._send_tribe_error(player_id, "这处稀有洞穴已经关闭")
            return
        if race.get("firstExplorerTribeId"):
            await self._send_tribe_error(player_id, f"首探已由{race.get('firstExplorerTribeName', '其他部落')}完成")
            return
        if race.get("status") == "rescue":
            await self._send_tribe_error(player_id, "先沿失踪线索救回队友")
            return

        rng = getattr(self, "_weather_rng", None) or random
        roll = rng.randint(1, 6)
        supports, support_bonus = self._cave_race_supports(tribe)
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name") or self._get_player_name(player_id)
        total = roll + support_bonus
        if total >= TRIBE_CAVE_RACE_FIRST_TARGET:
            reward_parts = self._apply_cave_race_reward(tribe, TRIBE_CAVE_RACE_FIRST_REWARD)
            self._sync_cave_race_first_result(race_id, tribe, member_name)
            self._record_map_memory(
                tribe,
                "cave_first",
                f"{race.get('caveLabel', '洞穴')}首探路线",
                f"{member_name}抢下短时稀有岔洞首探，洞壁上留下后来者可以重读的路线刻痕。",
                float(race.get("x", 0) or 0),
                float(race.get("z", 0) or 0),
                f"cave_race_first:{race_id}",
                member_name
            )
            detail = f"{member_name}抢下{race.get('label', '稀有洞穴')}首探：掷出{roll}+支撑{support_bonus}，{'、'.join(reward_parts)}。"
            self._add_tribe_history(tribe, "cave", "稀有洞穴首探", detail, player_id, {"kind": "cave_race_first", "raceId": race_id, "rewardParts": reward_parts, "supports": supports})
            await self._publish_world_rumor("cave", "稀有洞穴首探", f"{tribe.get('name', '部落')}由{member_name}抢下{race.get('caveLabel', '洞穴')}短时岔洞首探。", {"raceId": race_id, "tribeId": tribe_id})
            await self._notify_tribe(tribe_id, detail)
            await self._broadcast_all_cave_race_states()
            return

        race["status"] = "rescue"
        race["activeUntil"] = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_CAVE_RACE_RESCUE_MINUTES * 60).isoformat()
        target = max(1, min(TRIBE_CAVE_RACE_RESCUE_TARGET, len(tribe.get("members", {}) or {})))
        race["rescue"] = {
            "status": "missing",
            "missingPlayerId": player_id,
            "missingMemberName": member_name,
            "progress": 0,
            "target": target,
            "helperIds": [],
            "supportLabels": [item.get("label") for item in supports],
            "createdAt": datetime.now().isoformat()
        }
        detail = f"{member_name}抢探{race.get('label', '稀有洞穴')}失手：掷出{roll}+支撑{support_bonus}，没有重伤，只在洞口留下失踪线索，需要{target}步营救。"
        self._add_tribe_history(tribe, "cave", "洞穴失踪线索", detail, player_id, {"kind": "cave_race_missing", "raceId": race_id, "supports": supports})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def advance_cave_rescue(self, player_id: str, race_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        race = next((item for item in self._active_cave_races(tribe) if item.get("id") == race_id), None)
        rescue = race.get("rescue") if race else None
        if not race or race.get("status") != "rescue" or not rescue:
            await self._send_tribe_error(player_id, "没有可处理的洞穴营救线索")
            return
        if player_id in (rescue.get("helperIds", []) or []):
            await self._send_tribe_error(player_id, "你已经处理过这条营救线索")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name") or self._get_player_name(player_id)
        rescue.setdefault("helperIds", []).append(player_id)
        rescue.setdefault("helperNames", []).append(member_name)
        rescue["progress"] = int(rescue.get("progress", 0) or 0) + 1
        target = max(1, int(rescue.get("target", TRIBE_CAVE_RACE_RESCUE_TARGET) or TRIBE_CAVE_RACE_RESCUE_TARGET))
        if rescue["progress"] < target:
            detail = f"{member_name}沿{race.get('label', '稀有洞穴')}失踪线索找回一段回声，营救 {rescue['progress']} / {target}。"
            self._add_tribe_history(tribe, "cave", "推进洞穴营救", detail, player_id, {"kind": "cave_rescue_step", "raceId": race_id, "progress": rescue["progress"], "target": target})
            await self._notify_tribe(tribe_id, detail)
            await self.broadcast_tribe_state(tribe_id)
            return

        reward_parts = self._apply_cave_race_reward(tribe, TRIBE_CAVE_RACE_RESCUE_REWARD)
        memory = self._record_map_memory(
            tribe,
            "cave_rescue",
            f"{race.get('caveLabel', '洞穴')}营救旧痕",
            f"{member_name}和队友循着失踪线索救回{rescue.get('missingMemberName', '队友')}，洞口留下新的活地图记忆。",
            float(race.get("x", 0) or 0),
            float(race.get("z", 0) or 0),
            f"cave_rescue:{race_id}",
            member_name
        )
        race["status"] = "resolved"
        rescue["status"] = "rescued"
        rescue["completedAt"] = datetime.now().isoformat()
        detail = f"{member_name}完成{race.get('label', '稀有洞穴')}营救，救回{rescue.get('missingMemberName', '队友')}，{'、'.join(reward_parts) or '留下洞口记号'}。"
        if memory:
            detail += " 洞口多了一处可重访的活地图记忆。"
        self._add_tribe_history(tribe, "cave", "完成洞穴营救", detail, player_id, {"kind": "cave_rescue_complete", "raceId": race_id, "rewardParts": reward_parts, "memoryId": memory.get("id") if memory else ""})
        await self._publish_world_rumor("cave", "洞穴营救完成", f"{tribe.get('name', '部落')}循着短时岔洞的失踪线索救回了队友。", {"raceId": race_id, "tribeId": tribe_id})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
