from datetime import datetime
import random

from game_config import *


class GameCaveRaceMixin:
    def _active_cave_races(self, tribe: dict) -> list:
        now = datetime.now()
        active = self._active_tribe_items(
            tribe,
            "cave_races",
            TRIBE_CAVE_RACE_LIMIT,
            inactive_statuses={"resolved", "expired"},
            mark_expired_status="expired",
            on_expire=lambda race: race.setdefault("expiredAt", now.isoformat()),
            now=now
        )
        for race in active:
            race["type"] = "cave_rescue_clue" if race.get("status") == "rescue" else "rare_cave_race"
        return active

    def _public_cave_races(self, tribe: dict) -> list:
        public = []
        for race in self._active_cave_races(tribe):
            rescue = race.get("rescue") or {}
            rescue_methods = self._public_cave_rescue_methods(tribe) if race.get("status") == "rescue" else []
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
                "rescueMethods": rescue_methods,
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

    def _apply_cave_return_action_cost(self, tribe: dict, action: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(action.get("woodCost", 0) or 0)
        if wood_cost:
            storage["wood"] = max(0, int(storage.get("wood", 0) or 0) - wood_cost)
            parts.append(f"木材-{wood_cost}")
        return parts

    def _can_pay_cave_return_action(self, tribe: dict, action: dict) -> str:
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(action.get("woodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            return f"{action.get('label', '归路整理')}需要公共木材{wood_cost}"
        return ""

    def _create_cave_return_mark(self, tribe: dict, race: dict, rescue: dict, method: dict, member_name: str) -> dict:
        now = datetime.now()
        mark = {
            "id": f"cave_return_mark_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "raceId": race.get("id"),
            "caveLabel": race.get("caveLabel", "洞穴"),
            "label": f"{race.get('caveLabel', '洞穴')}归路标记",
            "summary": f"{member_name}救回{rescue.get('missingMemberName', '队友')}后，洞口留下可整理的归路绳、火把和洞壁刻痕。",
            "methodKey": method.get("key"),
            "methodLabel": method.get("label", "营救方式"),
            "x": race.get("x", 0),
            "z": race.get("z", 0),
            "progress": 0,
            "target": TRIBE_CAVE_RETURN_MARK_TARGET,
            "helperIds": [],
            "helperNames": [],
            "steps": [],
            "createdByName": member_name,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_CAVE_RETURN_MARK_ACTIVE_MINUTES * 60).isoformat()
        }
        marks = self._active_cave_return_marks(tribe)
        tribe["cave_return_marks"] = [*marks, mark][-TRIBE_CAVE_RETURN_MARK_LIMIT:]
        return mark

    def _public_cave_rescue_methods(self, tribe: dict) -> list:
        methods = []
        for key, config in TRIBE_CAVE_RACE_RESCUE_METHODS.items():
            _, bonuses, progress_bonus, reward_bonus = self._cave_rescue_method_state(tribe, key)
            methods.append({
                **config,
                "bonusLabels": [item.get("label", "") for item in bonuses if item.get("label")],
                "progressBonus": progress_bonus,
                "rewardLabel": self._reward_summary_text(reward_bonus) if hasattr(self, "_reward_summary_text") else "",
                "totalProgress": 1 + progress_bonus
            })
        return methods

    def _recent_cave_rescue_records(self, tribe: dict) -> list:
        return list(tribe.get("cave_rescue_records", []) or [])[-TRIBE_CAVE_RACE_RESCUE_RECORD_LIMIT:]

    def _active_cave_return_marks(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        changed = False
        for mark in tribe.get("cave_return_marks", []) or []:
            if not isinstance(mark, dict) or mark.get("status") != "active":
                continue
            try:
                if datetime.fromisoformat(mark.get("activeUntil", "")) <= now:
                    mark["status"] = "expired"
                    mark["expiredAt"] = now.isoformat()
                    changed = True
                    continue
            except (TypeError, ValueError):
                mark["status"] = "expired"
                mark["expiredAt"] = now.isoformat()
                changed = True
                continue
            active.append(mark)
        if changed:
            tribe["cave_return_marks"] = active[-TRIBE_CAVE_RETURN_MARK_LIMIT:]
        return active[-TRIBE_CAVE_RETURN_MARK_LIMIT:]

    def _public_cave_return_marks(self, tribe: dict) -> list:
        return [{
            "id": mark.get("id"),
            "type": "cave_return_mark",
            "label": mark.get("label", "洞穴归路标记"),
            "summary": mark.get("summary", ""),
            "caveLabel": mark.get("caveLabel", "未知洞穴"),
            "methodLabel": mark.get("methodLabel", "营救"),
            "x": mark.get("x", 0),
            "z": mark.get("z", 0),
            "progress": int(mark.get("progress", 0) or 0),
            "target": int(mark.get("target", TRIBE_CAVE_RETURN_MARK_TARGET) or TRIBE_CAVE_RETURN_MARK_TARGET),
            "helperNames": list(mark.get("helperNames", []) or [])[-4:],
            "activeUntil": mark.get("activeUntil"),
            "canOrganize": mark.get("status") == "active"
        } for mark in self._active_cave_return_marks(tribe)]

    def _recent_cave_return_records(self, tribe: dict) -> list:
        return list(tribe.get("cave_return_records", []) or [])[-TRIBE_CAVE_RETURN_MARK_RECORD_LIMIT:]

    def _public_cave_return_actions(self) -> dict:
        return TRIBE_CAVE_RETURN_MARK_ACTIONS

    def _cave_return_route_bonus_for_action(self, action_key: str, action: dict) -> dict:
        presets = {
            "tie_echo_rope": {"findsBonus": 1, "foodReduction": 0, "label": "回声绳归路线"},
            "cache_torches": {"findsBonus": 1, "foodReduction": 1, "label": "备用火把归路线"},
            "copy_wall_marks": {"findsBonus": 2, "foodReduction": 0, "label": "洞壁刻痕归路线"}
        }
        preset = presets.get(action_key, {"findsBonus": 1, "foodReduction": 0, "label": action.get("label", "洞穴归路经验")})
        return {
            "findsBonus": max(0, int(preset.get("findsBonus", 0) or 0)),
            "foodReduction": max(0, int(preset.get("foodReduction", 0) or 0)),
            "label": preset.get("label") or action.get("label", "洞穴归路经验")
        }

    def _active_cave_route_bonuses(self, tribe: dict) -> list:
        bonuses = []
        for bonus in tribe.get("cave_route_bonuses", []) or []:
            if isinstance(bonus, dict) and bonus.get("status", "active") == "active":
                bonuses.append(bonus)
        tribe["cave_route_bonuses"] = bonuses[-TRIBE_CAVE_RETURN_MARK_RECORD_LIMIT:]
        return tribe["cave_route_bonuses"]

    def _public_cave_route_bonuses(self, tribe: dict) -> list:
        public = []
        for bonus in self._active_cave_route_bonuses(tribe):
            public.append({
                "id": bonus.get("id"),
                "label": bonus.get("label", "洞穴归路经验"),
                "summary": bonus.get("summary", ""),
                "caveLabel": bonus.get("caveLabel", "洞穴"),
                "findsBonus": int(bonus.get("findsBonus", 0) or 0),
                "foodReduction": int(bonus.get("foodReduction", 0) or 0),
                "sourceActionLabel": bonus.get("sourceActionLabel", ""),
                "createdAt": bonus.get("createdAt")
            })
        return public[-TRIBE_CAVE_RETURN_MARK_RECORD_LIMIT:]

    def _create_cave_return_route_bonus(self, tribe: dict, mark: dict, action_key: str, action: dict, member_name: str) -> dict:
        bonus_values = self._cave_return_route_bonus_for_action(action_key, action)
        now = datetime.now()
        bonus = {
            "id": f"cave_route_bonus_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "active",
            "label": bonus_values["label"],
            "summary": f"{member_name}把{mark.get('caveLabel', '洞穴')}营救经验整理成下一次洞穴远征可用的路线加成。",
            "caveLabel": mark.get("caveLabel", "洞穴"),
            "findsBonus": bonus_values["findsBonus"],
            "foodReduction": bonus_values["foodReduction"],
            "sourceActionKey": action_key,
            "sourceActionLabel": action.get("label", "归路整理"),
            "createdAt": now.isoformat()
        }
        bonuses = self._active_cave_route_bonuses(tribe)
        tribe["cave_route_bonuses"] = [*bonuses, bonus][-TRIBE_CAVE_RETURN_MARK_RECORD_LIMIT:]
        return bonus

    def _consume_cave_return_route_bonus(self, tribe: dict, route_key: str) -> dict | None:
        bonuses = self._active_cave_route_bonuses(tribe)
        if not bonuses:
            return None
        bonus = bonuses[0]
        bonus["status"] = "used"
        bonus["usedRouteKey"] = route_key
        bonus["usedAt"] = datetime.now().isoformat()
        tribe["cave_route_bonuses"] = [item for item in bonuses[1:] if isinstance(item, dict) and item.get("status", "active") == "active"]
        return bonus

    def _mentorship_trail_bonus_active(self, tribe: dict) -> bool:
        mentorship = self._active_mentorship(tribe) if hasattr(self, "_active_mentorship") else None
        if mentorship and mentorship.get("focusKey") == "trail":
            return True
        for record in reversed(tribe.get("mentorship_history", []) or []):
            if isinstance(record, dict) and record.get("focusKey") == "trail":
                return True
        return False

    def _weather_forecast_bonus_active(self, tribe: dict) -> bool:
        forecast = self._active_weather_forecast(tribe) if hasattr(self, "_active_weather_forecast") else None
        if forecast:
            return True
        return any(isinstance(item, dict) for item in (tribe.get("weather_forecast_records", []) or [])[-2:])

    def _sacred_fire_cave_bonus_active(self, tribe: dict) -> bool:
        relay = self._active_sacred_fire_relay(tribe) if hasattr(self, "_active_sacred_fire_relay") else None
        if relay and relay.get("destinationKey") == "cave":
            return True
        for record in reversed(tribe.get("sacred_fire_history", []) or []):
            if isinstance(record, dict) and record.get("destinationKey") == "cave":
                return True
        return False

    def _trail_marker_bonus_active(self, tribe: dict) -> bool:
        markers = self._active_trail_markers(tribe) if hasattr(self, "_active_trail_markers") else []
        return bool(markers or tribe.get("trail_marker_history"))

    def _cave_rescue_method_state(self, tribe: dict, method_key: str) -> tuple[dict, list, int, dict]:
        method = TRIBE_CAVE_RACE_RESCUE_METHODS.get(method_key) or TRIBE_CAVE_RACE_RESCUE_METHODS["echo_locate"]
        bonuses = []
        reward_bonus = {}

        def add_bonus(label: str, reward: dict | None = None):
            bonuses.append({"label": label})
            for key, value in (reward or {}).items():
                reward_bonus[key] = int(reward_bonus.get(key, 0) or 0) + int(value or 0)

        if method_key == "echo_locate":
            if int(tribe.get("tamed_beasts", 0) or 0) > 0:
                add_bonus("幼兽嗅探", {"discoveryProgress": 1})
            if tribe.get("beast_specialty") in {"sniffer", "hunter"}:
                add_bonus("兽伴专长", {"renown": 1})
            if self._mentorship_trail_bonus_active(tribe):
                add_bonus("导师探路记号", {"discoveryProgress": 1})
        elif method_key == "torch_supply":
            if self._sacred_fire_cave_bonus_active(tribe):
                add_bonus("圣火洞口祝福", {"renown": 1})
            if self._weather_forecast_bonus_active(tribe):
                add_bonus("风向预判", {"discoveryProgress": 1})
        elif method_key == "wall_carving":
            if self._trail_marker_bonus_active(tribe):
                add_bonus("活路标参照", {"discoveryProgress": 1})
            if self._mentorship_trail_bonus_active(tribe):
                add_bonus("导师探路记号", {"renown": 1})
        return method, bonuses, min(2, len(bonuses)), reward_bonus

    def _apply_cave_rescue_method_cost(self, tribe: dict, method: dict) -> list:
        paid = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(method.get("woodCost", 0) or 0)
        food_cost = int(method.get("foodCost", 0) or 0)
        if wood_cost:
            storage["wood"] = max(0, int(storage.get("wood", 0) or 0) - wood_cost)
            paid.append(f"木材-{wood_cost}")
        if food_cost:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) - food_cost)
            paid.append(f"食物-{food_cost}")
        return paid

    def _can_pay_cave_rescue_method(self, tribe: dict, method: dict) -> str:
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(method.get("woodCost", 0) or 0)
        food_cost = int(method.get("foodCost", 0) or 0)
        if wood_cost and int(storage.get("wood", 0) or 0) < wood_cost:
            return f"{method.get('label', '营救方式')}需要公共木材{wood_cost}"
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            return f"{method.get('label', '营救方式')}需要公共食物{food_cost}"
        return ""

    def _record_cave_rescue_aftermath(self, tribe: dict, race: dict, rescue: dict, method: dict, member_name: str, reward_parts: list) -> dict:
        record = {
            "id": f"cave_rescue_record_{tribe.get('id')}_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "raceId": race.get("id"),
            "label": f"{race.get('caveLabel', '洞穴')}旧物",
            "methodKey": method.get("key"),
            "methodLabel": method.get("label", "营救方式"),
            "memberName": member_name,
            "missingMemberName": rescue.get("missingMemberName", "队友"),
            "summary": f"{member_name}用{method.get('label', '营救方式')}救回{rescue.get('missingMemberName', '队友')}后，洞口留下可整理的旧痕。",
            "rewardParts": list(reward_parts or []),
            "collectionReady": bool(method.get("collectionChance")),
            "puzzleFragmentCreated": False,
            "createdAt": datetime.now().isoformat()
        }
        if method.get("puzzleChance") and hasattr(self, "_shared_puzzle_source_available"):
            fragments = tribe.setdefault("shared_puzzle_fragments", [])
            if not any(item.get("sourceKey") == "cave" for item in fragments if isinstance(item, dict)):
                config = TRIBE_SHARED_PUZZLE_SOURCES.get("cave", {})
                puzzle_parts = self._apply_shared_puzzle_reward(tribe, config.get("reward", {})) if hasattr(self, "_apply_shared_puzzle_reward") else []
                fragment = {
                    "id": f"puzzle_fragment_{tribe.get('id')}_cave_rescue_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                    "sourceKey": "cave",
                    "sourceLabel": config.get("label", "洞穴碎片"),
                    "summary": f"{method.get('label', '营救方式')}把失踪线索整理成洞穴纹样。",
                    "memberName": member_name,
                    "rewardParts": puzzle_parts,
                    "rescueRecordId": record["id"],
                    "createdAt": datetime.now().isoformat()
                }
                fragments.append(fragment)
                tribe["shared_puzzle_fragments"] = fragments[-TRIBE_SHARED_PUZZLE_TARGET:]
                record["puzzleFragmentCreated"] = True
                record["puzzleRewardParts"] = puzzle_parts
        tribe.setdefault("cave_rescue_records", []).append(record)
        tribe["cave_rescue_records"] = tribe["cave_rescue_records"][-TRIBE_CAVE_RACE_RESCUE_RECORD_LIMIT:]
        return record

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
        if hasattr(self, "_oral_map_context_support"):
            oral_bonus, oral_labels, _, _ = self._oral_map_context_support(tribe, "cave_race")
            for label in oral_labels:
                supports.append({"label": label, "bonus": 1})
            bonus += oral_bonus
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
        route_experience = None
        if hasattr(self, "_consume_forbidden_edge_route_experience"):
            route_experience = self._consume_forbidden_edge_route_experience(tribe, "cave_race_first")
            if route_experience:
                safety_bonus = int(route_experience.get("safetyBonus", TRIBE_FORBIDDEN_EDGE_ROUTE_EXPERIENCE_SAFETY) or 0)
                support_bonus += safety_bonus
                supports.append({"label": route_experience.get("label", "禁地回撤经验"), "bonus": safety_bonus})
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name") or self._get_player_name(player_id)
        total = roll + support_bonus
        if total >= TRIBE_CAVE_RACE_FIRST_TARGET:
            oral_reference = None
            oral_lineage = None
            if hasattr(self, "_record_oral_map_context_reference"):
                oral_reference, oral_lineage = self._record_oral_map_context_reference(tribe, "cave_race", race.get("label", "稀有洞穴首探"), member_name, "首探成功")
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
            if oral_reference:
                detail += f" 引用了{oral_reference.get('actionLabel', '口述地图')}。"
            if oral_lineage:
                detail += f" 沉淀出{oral_lineage.get('label', '路线讲述谱系')}。"
            self._add_tribe_history(tribe, "cave", "稀有洞穴首探", detail, player_id, {"kind": "cave_race_first", "raceId": race_id, "rewardParts": reward_parts, "supports": supports, "oralMapReference": oral_reference, "oralMapLineage": oral_lineage})
            await self._publish_world_rumor("cave", "稀有洞穴首探", f"{tribe.get('name', '部落')}由{member_name}抢下{race.get('caveLabel', '洞穴')}短时岔洞首探。", {"raceId": race_id, "tribeId": tribe_id})
            await self._notify_tribe(tribe_id, detail)
            await self._broadcast_all_cave_race_states()
            return

        race["status"] = "rescue"
        race["activeUntil"] = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_CAVE_RACE_RESCUE_MINUTES * 60).isoformat()
        target = max(1, min(TRIBE_CAVE_RACE_RESCUE_TARGET, len(tribe.get("members", {}) or {}) or 1))
        race["rescue"] = {
            "status": "missing",
            "missingPlayerId": player_id,
            "missingMemberName": member_name,
            "progress": 0,
            "target": target,
            "helperIds": [],
            "steps": [],
            "supportLabels": [item.get("label") for item in supports],
            "createdAt": datetime.now().isoformat()
        }
        oral_reference = None
        oral_lineage = None
        if hasattr(self, "_record_oral_map_context_reference"):
            oral_reference, oral_lineage = self._record_oral_map_context_reference(tribe, "cave_race", race.get("label", "稀有洞穴首探"), member_name, "失踪线索")
        detail = f"{member_name}抢探{race.get('label', '稀有洞穴')}失手：掷出{roll}+支撑{support_bonus}，没有重伤，只在洞口留下失踪线索，需要{target}步营救。"
        if oral_reference:
            detail += f" 失踪线索旁引用了{oral_reference.get('actionLabel', '口述地图')}。"
        if oral_lineage:
            detail += f" 沉淀出{oral_lineage.get('label', '路线讲述谱系')}。"
        self._add_tribe_history(tribe, "cave", "洞穴失踪线索", detail, player_id, {"kind": "cave_race_missing", "raceId": race_id, "supports": supports, "oralMapReference": oral_reference, "oralMapLineage": oral_lineage})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def advance_cave_rescue(self, player_id: str, race_id: str, method_key: str = "echo_locate"):
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
        method, bonuses, progress_bonus, reward_bonus = self._cave_rescue_method_state(tribe, method_key)
        pay_error = self._can_pay_cave_rescue_method(tribe, method)
        if pay_error:
            await self._send_tribe_error(player_id, pay_error)
            return
        route_experience = None
        if int(rescue.get("progress", 0) or 0) <= 0 and hasattr(self, "_consume_forbidden_edge_route_experience"):
            route_experience = self._consume_forbidden_edge_route_experience(tribe, "cave_rescue")
            if route_experience:
                progress_bonus += 1
                bonuses.append({"label": route_experience.get("label", "禁地回撤经验")})
        if hasattr(self, "_oral_map_context_support"):
            oral_bonus, oral_labels, _, _ = self._oral_map_context_support(tribe, "cave_rescue")
            if oral_bonus:
                progress_bonus += oral_bonus
                bonuses.extend({"label": label} for label in oral_labels)

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name") or self._get_player_name(player_id)
        oral_reference = None
        oral_lineage = None
        if hasattr(self, "_record_oral_map_context_reference"):
            oral_reference, oral_lineage = self._record_oral_map_context_reference(tribe, "cave_rescue", race.get("label", "洞穴营救"), member_name, method.get("label", "营救"))
        paid_parts = self._apply_cave_rescue_method_cost(tribe, method)
        rescue.setdefault("helperIds", []).append(player_id)
        rescue.setdefault("helperNames", []).append(member_name)
        step_progress = 1 + progress_bonus
        rescue["progress"] = int(rescue.get("progress", 0) or 0) + step_progress
        rescue.setdefault("steps", []).append({
            "memberName": member_name,
            "methodKey": method.get("key"),
            "methodLabel": method.get("label"),
            "progress": step_progress,
            "bonusLabels": [item.get("label") for item in bonuses],
            "paidParts": paid_parts,
            "createdAt": datetime.now().isoformat()
        })
        target = max(1, int(rescue.get("target", TRIBE_CAVE_RACE_RESCUE_TARGET) or TRIBE_CAVE_RACE_RESCUE_TARGET))
        if rescue["progress"] < target:
            bonus_text = f"（{ '、'.join(item.get('label') for item in bonuses) }）" if bonuses else ""
            detail = f"{member_name}用{method.get('label', '营救方式')}推进{race.get('label', '稀有洞穴')}营救{bonus_text}，进度 {rescue['progress']} / {target}。"
            if oral_lineage:
                detail += f" 形成{oral_lineage.get('label', '路线讲述谱系')}。"
            self._add_tribe_history(tribe, "cave", "推进洞穴营救", detail, player_id, {"kind": "cave_rescue_step", "raceId": race_id, "progress": rescue["progress"], "target": target, "methodKey": method.get("key"), "bonuses": bonuses, "oralMapReference": oral_reference, "oralMapLineage": oral_lineage})
            await self._notify_tribe(tribe_id, detail)
            await self.broadcast_tribe_state(tribe_id)
            return

        reward = dict(TRIBE_CAVE_RACE_RESCUE_REWARD)
        for key, value in reward_bonus.items():
            reward[key] = int(reward.get(key, 0) or 0) + int(value or 0)
        reward_parts = self._apply_cave_race_reward(tribe, reward)
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
        record = self._record_cave_rescue_aftermath(tribe, race, rescue, method, member_name, reward_parts)
        return_mark = self._create_cave_return_mark(tribe, race, rescue, method, member_name)
        tile_trace = None
        if hasattr(self, "_record_map_tile_trace"):
            tile_trace = self._record_map_tile_trace(
                tribe,
                "safe_cave_path",
                float(race.get("x", 0) or 0),
                float(race.get("z", 0) or 0),
                f"cave_rescue:{race_id}",
                member_name
            )
        detail = f"{member_name}用{method.get('label', '营救方式')}完成{race.get('label', '稀有洞穴')}营救，救回{rescue.get('missingMemberName', '队友')}，{'、'.join(reward_parts) or '留下洞口记号'}。"
        if memory:
            detail += " 洞口多了一处可重访的活地图记忆。"
        if tile_trace:
            detail += " 洞口地块沉淀成一段安全洞路。"
        if record.get("puzzleFragmentCreated"):
            detail += " 失踪线索也补成了一片共享谜图。"
        if record.get("collectionReady"):
            detail += " 洞穴旧物可进入收藏墙。"
        if return_mark:
            detail += " 洞口同时留下了可整理的归路标记。"
        if oral_reference:
            detail += f" 营救复盘引用了{oral_reference.get('actionLabel', '口述地图')}。"
        if oral_lineage:
            detail += f" 形成{oral_lineage.get('label', '路线讲述谱系')}。"
        self._add_tribe_history(tribe, "cave", "完成洞穴营救", detail, player_id, {"kind": "cave_rescue_complete", "raceId": race_id, "rewardParts": reward_parts, "memoryId": memory.get("id") if memory else "", "methodKey": method.get("key"), "record": record, "returnMark": return_mark, "oralMapReference": oral_reference, "oralMapLineage": oral_lineage})
        await self._publish_world_rumor("cave", "洞穴营救完成", f"{tribe.get('name', '部落')}循着短时岔洞的失踪线索救回了队友。", {"raceId": race_id, "tribeId": tribe_id})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def organize_cave_return_mark(self, player_id: str, mark_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        mark = next((item for item in self._active_cave_return_marks(tribe) if item.get("id") == mark_id), None)
        if not mark:
            await self._send_tribe_error(player_id, "这处洞穴归路标记已经散去")
            return
        if player_id in (mark.get("helperIds", []) or []):
            await self._send_tribe_error(player_id, "你已经整理过这处归路标记")
            return
        action = TRIBE_CAVE_RETURN_MARK_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知归路整理方式")
            return
        pay_error = self._can_pay_cave_return_action(tribe, action)
        if pay_error:
            await self._send_tribe_error(player_id, pay_error)
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name") or self._get_player_name(player_id)
        paid_parts = self._apply_cave_return_action_cost(tribe, action)
        reward_parts = self._apply_cave_race_reward(tribe, action.get("reward", {}))
        mark.setdefault("helperIds", []).append(player_id)
        mark.setdefault("helperNames", []).append(member_name)
        mark["progress"] = int(mark.get("progress", 0) or 0) + 1
        mark.setdefault("steps", []).append({
            "memberName": member_name,
            "actionKey": action_key,
            "actionLabel": action.get("label", "归路整理"),
            "rewardParts": reward_parts,
            "paidParts": paid_parts,
            "createdAt": datetime.now().isoformat()
        })
        target = max(1, int(mark.get("target", TRIBE_CAVE_RETURN_MARK_TARGET) or TRIBE_CAVE_RETURN_MARK_TARGET))
        if mark["progress"] < target:
            detail = f"{member_name}在{mark.get('label', '洞穴归路标记')}上{action.get('label', '整理归路')}，进度 {mark['progress']} / {target}。"
            if reward_parts:
                detail += f" {'、'.join(reward_parts)}。"
            self._add_tribe_history(tribe, "cave", "整理洞穴归路", detail, player_id, {"kind": "cave_return_mark_step", "mark": mark, "actionKey": action_key, "rewardParts": reward_parts})
            await self._notify_tribe(tribe_id, detail)
            await self.broadcast_tribe_state(tribe_id)
            await self._broadcast_current_map()
            return

        mark["status"] = "resolved"
        mark["completedAt"] = datetime.now().isoformat()
        record = {
            "id": f"cave_return_record_{tribe_id}_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "markId": mark.get("id"),
            "label": mark.get("label", "洞穴归路标记"),
            "caveLabel": mark.get("caveLabel", "洞穴"),
            "actionLabel": action.get("label", "归路整理"),
            "summary": f"{member_name}和队友把{mark.get('caveLabel', '洞穴')}归路整理成稳定记号，后来者能沿绳、火把和刻痕回到洞口。",
            "helperNames": list(mark.get("helperNames", []) or []),
            "rewardParts": reward_parts,
            "collectionReady": bool(action.get("collectionReady")),
            "puzzleFragmentCreated": False,
            "createdAt": mark["completedAt"]
        }
        if action.get("puzzleChance") and hasattr(self, "_apply_shared_puzzle_reward"):
            fragments = tribe.setdefault("shared_puzzle_fragments", [])
            if not any(item.get("sourceKey") == "cave" for item in fragments if isinstance(item, dict)):
                config = TRIBE_SHARED_PUZZLE_SOURCES.get("cave", {})
                puzzle_parts = self._apply_shared_puzzle_reward(tribe, config.get("reward", {}))
                fragments.append({
                    "id": f"puzzle_fragment_{tribe_id}_cave_return_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                    "sourceKey": "cave",
                    "sourceLabel": config.get("label", "洞穴碎片"),
                    "summary": f"{action.get('label', '归路整理')}把回撤路线抄成洞穴纹样。",
                    "memberName": member_name,
                    "rewardParts": puzzle_parts,
                    "returnMarkId": mark.get("id"),
                    "createdAt": mark["completedAt"]
                })
                tribe["shared_puzzle_fragments"] = fragments[-TRIBE_SHARED_PUZZLE_TARGET:]
                record["puzzleFragmentCreated"] = True
                record["puzzleRewardParts"] = puzzle_parts
        route_bonus = self._create_cave_return_route_bonus(tribe, mark, action_key, action, member_name)
        record["routeBonus"] = route_bonus
        tribe.setdefault("cave_return_records", []).append(record)
        tribe["cave_return_records"] = tribe["cave_return_records"][-TRIBE_CAVE_RETURN_MARK_RECORD_LIMIT:]
        detail = f"{member_name}完成{mark.get('label', '洞穴归路标记')}整理：{'、'.join(reward_parts) or '归路已稳定'}。"
        if route_bonus:
            detail += f" 下一次洞穴远征获得{route_bonus.get('label', '归路经验')}加成。"
        if record.get("puzzleFragmentCreated"):
            detail += " 归路纹样也补入了共享谜图。"
        if record.get("collectionReady"):
            detail += " 抄下的洞壁刻痕可作为收藏墙来源。"
        self._record_map_memory(
            tribe,
            "cave_return",
            f"{mark.get('caveLabel', '洞穴')}归路",
            record.get("summary", ""),
            float(mark.get("x", 0) or 0),
            float(mark.get("z", 0) or 0),
            f"cave_return:{mark.get('id')}",
            member_name
        )
        self._add_tribe_history(tribe, "cave", "完成洞穴归路", detail, player_id, {"kind": "cave_return_mark_complete", "mark": mark, "record": record})
        await self._publish_world_rumor("cave", "洞穴归路稳定", f"{tribe.get('name', '部落')}把{mark.get('caveLabel', '洞穴')}的失踪归路整理成后来者能读懂的记号。", {"tribeId": tribe_id, "markId": mark.get("id")})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
