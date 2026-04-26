import random
import math
from datetime import datetime, timedelta
from typing import Optional

from game_config import *


class GameTribeProgressionMixin:
    def _ensure_boundary_outcome_legacy(self, tribe: dict, relation: dict):
        if not tribe or not relation:
            return
        state = relation.get("state")
        if state not in TRIBE_BOUNDARY_OUTCOME_TEMPLATES:
            return
        other_tribe_id = relation.get("otherTribeId")
        if not other_tribe_id:
            return
        relation_records = tribe.setdefault("boundary_relations", {})
        progress = relation_records.setdefault(other_tribe_id, {})
        if progress.get("lastOutcomeState") == state:
            return
        pending = tribe.setdefault("boundary_outcomes", [])
        duplicate = next((
            item for item in pending
            if item.get("otherTribeId") == other_tribe_id and item.get("state") == state and item.get("status") == "pending"
        ), None)
        if duplicate:
            return
        template = TRIBE_BOUNDARY_OUTCOME_TEMPLATES.get(state, {})
        pending.append({
            "id": f"boundary_outcome_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "state": state,
            "title": template.get("title", "边界事件"),
            "summary": template.get("summary", ""),
            "otherTribeId": other_tribe_id,
            "otherTribeName": relation.get("otherTribeName", "其他部落"),
            "distance": relation.get("distance"),
            "reward": {
                "wood": int(template.get("wood", 0) or 0),
                "stone": int(template.get("stone", 0) or 0),
                "food": int(template.get("food", 0) or 0),
                "renown": int(template.get("renown", 0) or 0),
                "tradeReputation": int(template.get("tradeReputation", 0) or 0),
                "discoveryProgress": int(template.get("discoveryProgress", 0) or 0)
            },
            "status": "pending",
            "createdAt": datetime.now().isoformat()
        })
        tribe["boundary_outcomes"] = pending[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
        progress["lastOutcomeState"] = state

    def _ensure_boundary_outcome(self, tribe: dict, relation: dict):
        affected_tribe_ids = set()
        if not tribe or not relation:
            return affected_tribe_ids
        state = relation.get("state")
        if state not in TRIBE_BOUNDARY_OUTCOME_TEMPLATES:
            return affected_tribe_ids
        other_tribe_id = relation.get("otherTribeId")
        own_tribe_id = tribe.get("id")
        if not other_tribe_id:
            return affected_tribe_ids

        template = TRIBE_BOUNDARY_OUTCOME_TEMPLATES.get(state, {})
        pending = tribe.setdefault("boundary_outcomes", [])
        progress = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        if progress.get("lastOutcomeState") != state:
            duplicate = next((
                item for item in pending
                if item.get("otherTribeId") == other_tribe_id and item.get("state") == state and item.get("status") == "pending"
            ), None)
            if not duplicate:
                pending.append({
                    "id": f"boundary_outcome_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                    "state": state,
                    "title": template.get("title", "边界事件"),
                    "summary": template.get("summary", ""),
                    "otherTribeId": other_tribe_id,
                    "otherTribeName": relation.get("otherTribeName", "其他部落"),
                    "distance": relation.get("distance"),
                    "reward": {
                        "wood": int(template.get("wood", 0) or 0),
                        "stone": int(template.get("stone", 0) or 0),
                        "food": int(template.get("food", 0) or 0),
                        "renown": int(template.get("renown", 0) or 0),
                        "tradeReputation": int(template.get("tradeReputation", 0) or 0),
                        "discoveryProgress": int(template.get("discoveryProgress", 0) or 0)
                    },
                    "status": "pending",
                    "createdAt": datetime.now().isoformat()
                })
                tribe["boundary_outcomes"] = pending[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                if own_tribe_id:
                    affected_tribe_ids.add(own_tribe_id)
            progress["lastOutcomeState"] = state

        other_tribe = self.tribes.get(other_tribe_id)
        if own_tribe_id and other_tribe:
            other_progress = other_tribe.setdefault("boundary_relations", {}).setdefault(own_tribe_id, {})
            response_marker = f"response:{state}"
            if other_progress.get("lastOutcomeState") != response_marker:
                other_pending = other_tribe.setdefault("boundary_outcomes", [])
                other_duplicate = next((
                    item for item in other_pending
                    if item.get("otherTribeId") == own_tribe_id and item.get("state") == state and item.get("status") == "pending"
                ), None)
                if not other_duplicate:
                    other_pending.append({
                        "id": f"boundary_response_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                        "state": state,
                        "title": f"回应{template.get('title', '边界事件')}",
                        "summary": f"{tribe.get('name', '对方部落')} 已在边界上推进局势，营地可以选择回应这次变化。",
                        "otherTribeId": own_tribe_id,
                        "otherTribeName": tribe.get("name", "对方部落"),
                        "distance": relation.get("distance"),
                        "reward": {
                            "wood": max(0, int(template.get("wood", 0) or 0) // 2),
                            "stone": max(0, int(template.get("stone", 0) or 0) // 2),
                            "food": max(0, int(template.get("food", 0) or 0) // 2),
                            "renown": max(1, int(template.get("renown", 0) or 0) // 2),
                            "tradeReputation": max(0, int(template.get("tradeReputation", 0) or 0) // 2),
                            "discoveryProgress": max(0, int(template.get("discoveryProgress", 0) or 0) // 2)
                        },
                        "status": "pending",
                        "response": True,
                        "createdAt": datetime.now().isoformat()
                    })
                    other_tribe["boundary_outcomes"] = other_pending[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                    affected_tribe_ids.add(own_tribe_id)
                other_progress["lastOutcomeState"] = response_marker
        return affected_tribe_ids

    async def resolve_boundary_outcome(self, player_id: str, outcome_id: str, response_key: str = ""):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        outcomes = tribe.get("boundary_outcomes", []) or []
        outcome = next((item for item in outcomes if isinstance(item, dict) and item.get("id") == outcome_id), None)
        if not outcome or outcome.get("status") != "pending":
            await self._send_tribe_error(player_id, "这条边界结果已经处理过了")
            return

        reward = dict(outcome.get("reward") or {})
        if outcome.get("kind") == "resource_site_contest":
            response_key = response_key if response_key in {"hold", "cede", "trade_path"} else "hold"
            reward = self._apply_resource_contest_response(tribe, outcome, response_key)
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        for resource_key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(reward.get(resource_key, 0) or 0)
            if amount:
                storage[resource_key] = int(storage.get(resource_key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = int(reward.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        renown = int(reward.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        trade_rep = int(reward.get("tradeReputation", 0) or 0)
        if trade_rep:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_rep
            reward_parts.append(f"贸易信誉+{trade_rep}")
        progress = int(reward.get("discoveryProgress", 0) or 0)
        if progress:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + progress
            reward_parts.append(f"发现进度+{progress}")

        relation_records = tribe.setdefault("boundary_relations", {})
        relation_progress = relation_records.get(outcome.get("otherTribeId"), {})
        if outcome.get("kind") == "resource_site_contest":
            relation_delta = int(outcome.get("relationDelta", 0) or 0)
            trade_delta = int(outcome.get("tradeTrustDelta", 0) or 0)
            relation_progress["score"] = max(-9, min(9, int(relation_progress.get("score", 0) or 0) + relation_delta))
            if trade_delta:
                relation_progress["tradeTrust"] = max(0, min(9, int(relation_progress.get("tradeTrust", 0) or 0) + trade_delta))
        elif outcome.get("state") == "hostile":
            relation_progress["score"] = max(-9, int(relation_progress.get("score", 0) or 0) - 1)
        else:
            relation_progress["score"] = min(9, int(relation_progress.get("score", 0) or 0) + 1)
        relation_progress["lastResolvedAt"] = datetime.now().isoformat()
        relation_records[outcome.get("otherTribeId")] = relation_progress

        member = tribe.get("members", {}).get(player_id, {})
        outcome["status"] = "resolved"
        outcome["resolvedAt"] = datetime.now().isoformat()
        record = {
            "kind": "boundary_outcome",
            "title": outcome.get("title", "边界结果"),
            "summary": outcome.get("summary", ""),
            "state": outcome.get("state"),
            "responseKey": response_key,
            "responseLabel": outcome.get("responseLabel"),
            "otherTribeName": outcome.get("otherTribeName", "其他部落"),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "createdAt": outcome.get("createdAt"),
            "resolvedAt": outcome.get("resolvedAt")
        }
        detail = f"{record['memberName']} 处理了边界结果“{record['title']}”：{record['summary']} {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "governance", "处理边界结果", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "territory",
            record["title"],
            f"{tribe.get('name', '部落')} 在与 {record['otherTribeName']} 的边界上处理了“{record['title']}”。",
            {"tribeId": tribe_id, "outcomeId": outcome_id, "state": outcome.get("state")}
        )
        await self.broadcast_tribe_state(tribe_id)

    def _apply_resource_contest_response(self, tribe: dict, outcome: dict, response_key: str) -> dict:
        site_id = outcome.get("siteId")
        site = next((
            item for item in (tribe.get("scouted_resource_sites", []) or [])
            if isinstance(item, dict) and item.get("id") == site_id
        ), None)
        base_reward = dict(outcome.get("reward") or {})
        if response_key == "cede":
            outcome["responseLabel"] = "让渡"
            outcome["relationDelta"] = 2
            outcome["tradeTrustDelta"] = 1
            if site:
                site["status"] = "ceded"
                tribe["scouted_resource_sites"] = [
                    item for item in (tribe.get("scouted_resource_sites", []) or [])
                    if not (isinstance(item, dict) and item.get("id") == site_id)
                ]
            return {"tradeReputation": 1, "renown": 1}
        if response_key == "trade_path":
            outcome["responseLabel"] = "交换通路"
            outcome["relationDelta"] = 1
            outcome["tradeTrustDelta"] = 3
            if site:
                site["contested"] = False
                site["contestResolvedAs"] = "trade_path"
            return {
                "food": max(2, int(base_reward.get("food", 0) or 0) // 2),
                "wood": max(0, int(base_reward.get("wood", 0) or 0) // 2),
                "stone": max(0, int(base_reward.get("stone", 0) or 0) // 2),
                "tradeReputation": 2,
                "renown": 2
            }
        outcome["responseLabel"] = "守住"
        outcome["relationDelta"] = -2
        outcome["tradeTrustDelta"] = 0
        if site:
            site["contestResolvedAs"] = "hold"
        base_reward["renown"] = int(base_reward.get("renown", 0) or 0) + 2
        return base_reward

    async def claim_tribe_flag(self, player_id: str, x: float, z: float):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以插下领地旗帜")
            return

        flags = tribe.setdefault("territory_flags", [])
        if len(flags) >= TRIBE_FLAG_MAX:
            await self._send_tribe_error(player_id, f"最多只能保留 {TRIBE_FLAG_MAX} 面领地旗帜")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        if int(storage.get("wood", 0) or 0) < TRIBE_FLAG_WOOD_COST or int(storage.get("stone", 0) or 0) < TRIBE_FLAG_STONE_COST:
            await self._send_tribe_error(player_id, "仓库资源不足，插旗需要木材和石块")
            return

        safe_x = max(-490, min(490, float(x or 0)))
        safe_z = max(-490, min(490, float(z or 0)))
        storage["wood"] = int(storage.get("wood", 0) or 0) - TRIBE_FLAG_WOOD_COST
        storage["stone"] = int(storage.get("stone", 0) or 0) - TRIBE_FLAG_STONE_COST
        flag_id = f"{tribe_id}_flag_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}"
        flag = {
            "id": flag_id,
            "tribeId": tribe_id,
            "type": "tribe_flag",
            "label": f"{tribe.get('name', '部落')}领地旗帜",
            "x": safe_x,
            "z": safe_z,
            "size": 1.0,
            "claimedBy": member.get("name", "成员"),
            "claimedAt": datetime.now().isoformat(),
            "claimNote": "旗帜周围会成为部落公开宣告的资源活动区。"
        }
        flags.append(flag)
        tribe["renown"] = max(0, int(tribe.get("renown", 0) or 0)) + 2
        detail = f"{member.get('name', '成员')} 在 ({round(safe_x)}, {round(safe_z)}) 插下领地旗帜，消耗木材 {TRIBE_FLAG_WOOD_COST}、石块 {TRIBE_FLAG_STONE_COST}。"
        self._add_tribe_history(tribe, "governance", "插下领地旗帜", detail, player_id, {"kind": "territory_flag", **flag})
        await self._publish_world_rumor(
            "territory",
            "领地旗帜",
            f"{tribe.get('name', '部落')} 在新的资源点插下旗帜，公开宣告活动范围。",
            {"tribeId": tribe_id, "flagId": flag_id, "x": safe_x, "z": safe_z}
        )
        relation = self._flag_boundary_relation(tribe_id, flag)
        if relation:
            flag["boundaryRelation"] = relation
            await self._publish_world_rumor(
                "territory",
                relation.get("label", "旗帜边界"),
                f"{tribe.get('name', '部落')} 的新旗帜靠近 {relation.get('otherTribeName', '其他部落')}，形成{relation.get('label', '边界关系')}。",
                {"tribeId": tribe_id, "flagId": flag_id, "relation": relation}
            )
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()


    async def patrol_tribe_flag(self, player_id: str, flag_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        flags = tribe.get("territory_flags", []) or []
        flag = next((item for item in flags if isinstance(item, dict) and item.get("id") == flag_id), None)
        if not flag:
            await self._send_tribe_error(player_id, "这面旗帜不属于你的部落")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(flag.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(flag.get("z", 0) or 0)
        if dx * dx + dz * dz > 9 * 9:
            await self._send_tribe_error(player_id, "靠近领地旗帜后才能巡查")
            return

        last_patrolled = flag.get("lastPatrolledAt")
        if last_patrolled:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_patrolled)).total_seconds()
                if elapsed < TRIBE_FLAG_PATROL_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil((TRIBE_FLAG_PATROL_COOLDOWN_SECONDS - elapsed) / 60))
                    await self._send_tribe_error(player_id, f"这面旗帜刚巡查过，还需约 {remaining} 分钟")
                    return
            except (TypeError, ValueError):
                pass

        nearest_region = min(
            WORLD_REGIONS,
            key=lambda region: (float(flag.get("x", 0) or 0) - region["x"]) ** 2 + (float(flag.get("z", 0) or 0) - region["z"]) ** 2
        )
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        region_type = nearest_region.get("type")
        reward_parts = []
        if region_type == "region_forest":
            storage["wood"] = int(storage.get("wood", 0) or 0) + 5
            reward_parts.append("木材+5")
        elif region_type == "region_mountain":
            storage["stone"] = int(storage.get("stone", 0) or 0) + 5
            reward_parts.append("石块+5")
        elif region_type == "region_coast":
            tribe["food"] = int(tribe.get("food", 0) or 0) + 5
            reward_parts.append("食物+5")
        elif region_type == "region_ruin":
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + 1
            reward_parts.append("发现进度+1")
        else:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 2
            reward_parts.append("声望+2")

        tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
        reward_parts.append("巡查声望+1")
        member = tribe.get("members", {}).get(player_id, {})

        if self._has_tribe_structure_type(tribe, "tribe_road"):
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
            reward_parts.append("道路巡查声望+1")
        chain_regions = list(tribe.get("flag_patrol_chain_regions", []) or [])
        if region_type and region_type not in chain_regions:
            chain_regions.append(region_type)
        tribe["flag_patrol_chain_regions"] = chain_regions[-TRIBE_FLAG_PATROL_CHAIN_TARGET:]
        chain_unlocked = len(set(tribe["flag_patrol_chain_regions"])) >= TRIBE_FLAG_PATROL_CHAIN_TARGET
        tide_hint = None
        if chain_unlocked:
            tribe["flag_patrol_chain_regions"] = []
            env = self._get_current_environment()
            tide_hint = {
                "id": f"flag_tide_{nearest_region['id']}_{int(datetime.now().timestamp())}",
                "regionId": nearest_region["id"],
                "regionType": nearest_region["type"],
                "regionLabel": nearest_region["label"],
                "x": nearest_region["x"],
                "z": nearest_region["z"],
                "radius": nearest_region["radius"],
                "gatherBonus": RESOURCE_TIDE_GATHER_BONUS + 1,
                "seasonBoosted": False,
                "flagPatrolHint": True,
                "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + RESOURCE_TIDE_DURATION_MINUTES * 60).isoformat()
            }
            env["resourceTide"] = tide_hint
            map_data = self.maps.get(self.current_map_name) or {}
            map_data["environment"] = env
            map_data["updated_at"] = datetime.now().isoformat()
            reward_parts.append(f"旗帜连锁：{nearest_region.get('label', '附近区域')}资源潮汐")

        flag["lastPatrolledAt"] = datetime.now().isoformat()
        flag["lastPatrolledBy"] = member.get("name", "成员")
        flag["lastPatrolReward"] = reward_parts
        record = {
            "kind": "territory_flag_patrol",
            "flagId": flag.get("id"),
            "flagLabel": flag.get("label", "领地旗帜"),
            "regionLabel": nearest_region.get("label", "附近区域"),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "chainUnlocked": chain_unlocked,
            "chainTarget": TRIBE_FLAG_PATROL_CHAIN_TARGET,
            "tideHint": tide_hint,
            "createdAt": flag["lastPatrolledAt"]
        }
        detail = f"{record['memberName']} 巡查了{record['flagLabel']}，确认{record['regionLabel']}的活动范围：{'、'.join(reward_parts)}。"
        if chain_unlocked:
            detail += " 连续巡查不同区域的旗帜后，部落标记出新的资源潮汐线索。"
        self._add_tribe_history(tribe, "governance", "巡查领地旗帜", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()


    async def start_tribe_scout(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        food = int(tribe.get("food", 0) or 0)
        if food < TRIBE_SCOUT_FOOD_COST:
            await self._send_tribe_error(player_id, f"侦察需要食物 {TRIBE_SCOUT_FOOD_COST}")
            return

        env = self._get_current_environment()
        tribe["food"] = food - TRIBE_SCOUT_FOOD_COST
        env["resourceTide"] = self._pick_resource_tide(env)
        events = [event for event in (env.get("worldEvents", []) or []) if isinstance(event, dict)]
        for _ in range(TRIBE_SCOUT_EVENT_COUNT):
            events.append(self._pick_world_event(env))
        env["worldEvents"] = events[-4:]
        tide = env["resourceTide"]
        region_type = tide.get("regionType", "region_forest")
        site_reward = TRIBE_SCOUT_SITE_REWARDS.get(region_type, TRIBE_SCOUT_SITE_REWARDS["region_forest"])
        angle = random.random() * math.pi * 2
        distance = random.randint(10, max(14, int(tide.get("radius", 20) or 20)))
        site_x = max(-490, min(490, float(tide.get("x", 0) or 0) + math.cos(angle) * distance))
        site_z = max(-490, min(490, float(tide.get("z", 0) or 0) + math.sin(angle) * distance))
        site = {
            "id": f"scout_site_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "tribeId": tribe_id,
            "type": "scouted_resource_site",
            "label": site_reward.get("label", "侦察资源点"),
            "regionType": region_type,
            "regionLabel": tide.get("regionLabel", "未知区域"),
            "resourceLabel": site_reward.get("label", "资源点"),
            "x": site_x,
            "z": site_z,
            "size": 1.0,
            "reward": {key: value for key, value in site_reward.items() if key != "label"},
            "foundBy": member.get("name", "成员"),
            "status": "active",
            "createdAt": datetime.now().isoformat(),
            "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_SCOUT_SITE_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("scouted_resource_sites", []).append(site)
        tribe["scouted_resource_sites"] = tribe["scouted_resource_sites"][-TRIBE_SCOUT_SITE_LIMIT:]
        contested_tribe_ids = self._mark_scout_site_contests(tribe, site)

        report = {
            "id": f"scout_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "memberName": member.get("name", "成员"),
            "regionLabel": tide.get("regionLabel", "未知区域"),
            "siteId": site["id"],
            "siteLabel": site["label"],
            "eventTitles": [event.get("title", "世界事件") for event in env["worldEvents"][-TRIBE_SCOUT_EVENT_COUNT:]],
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("scout_reports", []).append(report)
        tribe["scout_reports"] = tribe["scout_reports"][-8:]

        map_data = self.maps.get(self.current_map_name) or {}
        map_data["environment"] = env
        map_data["updated_at"] = datetime.now().isoformat()
        contest_text = " 这处资源点靠近其他部落线索，已经形成争夺机会。" if contested_tribe_ids else ""
        detail = f"{report['memberName']} 派出侦察队，标记了{report['regionLabel']}的大地馈赠，发现{site['label']}，并发现 {'、'.join(report['eventTitles'])}。{contest_text}"
        self._add_tribe_history(tribe, "world_event", "派出侦察", detail, player_id, {"kind": "scout", **report})
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "scout",
            "侦察标记",
            f"{tribe.get('name', '部落')} 派出侦察队，远方资源与事件被重新标记。",
            {"tribeId": tribe_id, "reportId": report["id"]}
        )
        await self.broadcast_tribe_state(tribe_id)
        for affected_id in contested_tribe_ids:
            if affected_id != tribe_id:
                await self._notify_tribe(
                    affected_id,
                    f"{tribe.get('name', '其他部落')} 的侦察线索与你们的资源点重叠，部落面板出现了资源点争执。"
                )
                await self.broadcast_tribe_state(affected_id)
        await self._broadcast_current_map()

    def _mark_scout_site_contests(self, tribe: dict, site: dict) -> set:
        affected_tribe_ids = set()
        tribe_id = tribe.get("id")
        if not tribe_id or not site:
            return affected_tribe_ids
        sx = float(site.get("x", 0) or 0)
        sz = float(site.get("z", 0) or 0)
        for other_tribe in self.tribes.values():
            other_id = other_tribe.get("id")
            if not other_id or other_id == tribe_id:
                continue
            for other_site in self._active_scouted_resource_sites(other_tribe):
                dx = sx - float(other_site.get("x", 0) or 0)
                dz = sz - float(other_site.get("z", 0) or 0)
                if dx * dx + dz * dz > TRIBE_SCOUT_SITE_CONTEST_RADIUS * TRIBE_SCOUT_SITE_CONTEST_RADIUS:
                    continue
                self._flag_scout_site_contest(tribe, other_tribe, site, other_site)
                self._flag_scout_site_contest(other_tribe, tribe, other_site, site)
                affected_tribe_ids.update({tribe_id, other_id})
        return affected_tribe_ids

    def _flag_scout_site_contest(self, tribe: dict, other_tribe: dict, site: dict, other_site: dict):
        other_id = other_tribe.get("id")
        if not other_id:
            return
        site["contested"] = True
        site["contestedByTribeId"] = other_id
        site["contestedByTribeName"] = other_tribe.get("name", "其他部落")
        site["contestSiteId"] = other_site.get("id")

        progress = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
        progress["score"] = max(-9, int(progress.get("score", 0) or 0) - 2)
        progress["lastAction"] = "resource_site_contest"
        progress["lastActionAt"] = datetime.now().isoformat()

        pending = tribe.setdefault("boundary_outcomes", [])
        duplicate = next((
            item for item in pending
            if item.get("kind") == "resource_site_contest"
            and item.get("siteId") == site.get("id")
            and item.get("otherTribeId") == other_id
            and item.get("status") == "pending"
        ), None)
        if duplicate:
            return
        reward = {"renown": 4}
        site_reward = dict(site.get("reward") or {})
        if int(site_reward.get("wood", 0) or 0):
            reward["wood"] = 4
        if int(site_reward.get("stone", 0) or 0):
            reward["stone"] = 4
        if int(site_reward.get("food", 0) or 0):
            reward["food"] = 4
        if int(site_reward.get("discoveryProgress", 0) or 0):
            reward["discoveryProgress"] = 1
        pending.append({
            "id": f"resource_contest_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "kind": "resource_site_contest",
            "state": "hostile",
            "title": "资源点争执",
            "summary": f"{site.get('label', '侦察资源点')} 与 {other_tribe.get('name', '其他部落')} 的侦察线索重叠，边界关系变得紧张。",
            "siteId": site.get("id"),
            "siteLabel": site.get("label"),
            "otherSiteId": other_site.get("id"),
            "otherTribeId": other_id,
            "otherTribeName": other_tribe.get("name", "其他部落"),
            "reward": reward,
            "responseOptions": [
                {"key": "hold", "label": "守住"},
                {"key": "cede", "label": "让渡"},
                {"key": "trade_path", "label": "交换通路"}
            ],
            "status": "pending",
            "createdAt": datetime.now().isoformat()
        })
        tribe["boundary_outcomes"] = pending[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]

    async def secure_scouted_resource_site(self, player_id: str, site_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        sites = self._active_scouted_resource_sites(tribe)
        site = next((item for item in sites if item.get("id") == site_id), None)
        if not site:
            await self._send_tribe_error(player_id, "这个侦察资源点已经失效")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(site.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(site.get("z", 0) or 0)
        if dx * dx + dz * dz > TRIBE_SCOUT_SITE_INTERACT_DISTANCE * TRIBE_SCOUT_SITE_INTERACT_DISTANCE:
            await self._send_tribe_error(player_id, "靠近侦察资源点后才能确认")
            return

        reward = dict(site.get("reward") or {})
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        for resource_key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(reward.get(resource_key, 0) or 0)
            if amount:
                storage[resource_key] = int(storage.get(resource_key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = int(reward.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        discovery = int(reward.get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现进度+{discovery}")
        renown = int(reward.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        if site.get("contested"):
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 2
            reward_parts.append("争夺确认声望+2")
        shared_with_id = site.get("sharedWithTribeId")
        if site.get("jointWatchId") and shared_with_id:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + 1
            relation_progress = tribe.setdefault("boundary_relations", {}).setdefault(shared_with_id, {})
            relation_progress["tradeTrust"] = min(9, int(relation_progress.get("tradeTrust", 0) or 0) + 1)
            relation_progress["score"] = min(9, int(relation_progress.get("score", 0) or 0) + 1)
            relation_progress["lastAction"] = "joint_watch_confirmed"
            relation_progress["lastActionAt"] = datetime.now().isoformat()
            other_tribe = self.tribes.get(shared_with_id)
            if other_tribe:
                other_progress = other_tribe.setdefault("boundary_relations", {}).setdefault(tribe_id, {})
                other_progress["tradeTrust"] = min(9, int(other_progress.get("tradeTrust", 0) or 0) + 1)
                other_progress["score"] = min(9, int(other_progress.get("score", 0) or 0) + 1)
                other_progress["lastAction"] = "joint_watch_confirmed"
                other_progress["lastActionAt"] = relation_progress["lastActionAt"]
            reward_parts.append("联合守望信誉+1")

        linked_flag = next((
            flag for flag in (tribe.get("territory_flags", []) or [])
            if isinstance(flag, dict)
            and (float(flag.get("x", 0) or 0) - float(site.get("x", 0) or 0)) ** 2
            + (float(flag.get("z", 0) or 0) - float(site.get("z", 0) or 0)) ** 2
            <= TRIBE_SCOUT_SITE_FLAG_RADIUS * TRIBE_SCOUT_SITE_FLAG_RADIUS
        ), None)
        if linked_flag:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 2
            reward_parts.append("旗帜控制声望+2")
            linked_flag["linkedResourceSiteId"] = site.get("id")
            linked_flag["linkedResourceSiteLabel"] = site.get("label")
        if self._has_tribe_structure_type(tribe, "tribe_road"):
            storage["wood"] = int(storage.get("wood", 0) or 0) + 2
            storage["stone"] = int(storage.get("stone", 0) or 0) + 2
            reward_parts.append("道路驮运木材+2/石块+2")

        member = tribe.get("members", {}).get(player_id, {})
        site["status"] = "secured"
        site["securedAt"] = datetime.now().isoformat()
        site["securedBy"] = player_id
        controlled_site = {
            **site,
            "id": f"controlled_{site.get('id')}",
            "type": "controlled_resource_site",
            "status": "controlled",
            "level": 1,
            "yieldCount": 0,
            "patrolCount": 0,
            "relayCount": 0,
            "roadLinked": self._has_tribe_structure_type(tribe, "tribe_road"),
            "securedByName": member.get("name", "成员"),
            "controlledAt": site["securedAt"],
            "lastYieldAt": None,
            "lastPatrolledAt": None,
            "lastRelayedAt": None,
            "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_CONTROLLED_SITE_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("controlled_resource_sites", []).append(controlled_site)
        tribe["controlled_resource_sites"] = tribe["controlled_resource_sites"][-TRIBE_CONTROLLED_SITE_LIMIT:]
        tribe["scouted_resource_sites"] = [
            item for item in (tribe.get("scouted_resource_sites", []) or [])
            if not (isinstance(item, dict) and item.get("id") == site_id)
        ]

        record = {
            "kind": "scouted_resource_site",
            "siteId": site.get("id"),
            "siteLabel": site.get("label", "侦察资源点"),
            "regionLabel": site.get("regionLabel", "附近区域"),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "linkedFlagId": linked_flag.get("id") if linked_flag else None,
            "contested": bool(site.get("contested")),
            "contestedByTribeName": site.get("contestedByTribeName"),
            "createdAt": site["securedAt"]
        }
        detail = f"{record['memberName']} 确认了{record['siteLabel']}，带回{'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "world_event", "确认侦察资源点", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "territory",
            "资源点确认",
            f"{tribe.get('name', '部落')} 确认了{site.get('label', '侦察资源点')}，探索线索转化为领地收益。",
            {"tribeId": tribe_id, "siteId": site_id, "linkedFlagId": record["linkedFlagId"]}
        )
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def collect_controlled_resource_site(self, player_id: str, site_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        sites = self._active_controlled_resource_sites(tribe)
        site = next((item for item in sites if item.get("id") == site_id), None)
        if not site:
            await self._send_tribe_error(player_id, "这个控制资源点已经消散")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(site.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(site.get("z", 0) or 0)
        if dx * dx + dz * dz > TRIBE_SCOUT_SITE_INTERACT_DISTANCE * TRIBE_SCOUT_SITE_INTERACT_DISTANCE:
            await self._send_tribe_error(player_id, "靠近控制资源点后才能收取")
            return

        last_yield_at = site.get("lastYieldAt")
        if last_yield_at:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_yield_at)).total_seconds()
                if elapsed < TRIBE_CONTROLLED_SITE_YIELD_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil((TRIBE_CONTROLLED_SITE_YIELD_COOLDOWN_SECONDS - elapsed) / 60))
                    await self._send_tribe_error(player_id, f"这处资源点刚收取过，还需约 {remaining} 分钟")
                    return
            except (TypeError, ValueError):
                pass

        source_reward = dict(site.get("reward") or {})
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        site_level = max(1, int(site.get("level", 1) or 1))
        base_yield = 3 + site_level
        if int(source_reward.get("wood", 0) or 0):
            amount = base_yield
            storage["wood"] = int(storage.get("wood", 0) or 0) + amount
            reward_parts.append(f"木材+{amount}")
        if int(source_reward.get("stone", 0) or 0):
            amount = base_yield
            storage["stone"] = int(storage.get("stone", 0) or 0) + amount
            reward_parts.append(f"石块+{amount}")
        if int(source_reward.get("food", 0) or 0):
            amount = base_yield
            tribe["food"] = int(tribe.get("food", 0) or 0) + amount
            reward_parts.append(f"食物+{amount}")
        if int(source_reward.get("discoveryProgress", 0) or 0):
            progress_amount = 1 + (1 if site_level >= 3 else 0)
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + progress_amount
            reward_parts.append(f"发现进度+{progress_amount}")

        if site.get("linkedFlagId"):
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
            reward_parts.append("旗帜控制声望+1")
        if self._has_tribe_structure_type(tribe, "tribe_road"):
            road_bonus = 1 + (1 if site_level >= 2 else 0)
            storage["wood"] = int(storage.get("wood", 0) or 0) + road_bonus
            storage["stone"] = int(storage.get("stone", 0) or 0) + road_bonus
            reward_parts.append(f"道路运输木材+{road_bonus}/石块+{road_bonus}")

        if not reward_parts:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
            reward_parts.append("声望+1")

        site["lastYieldAt"] = datetime.now().isoformat()
        site["yieldCount"] = int(site.get("yieldCount", 0) or 0) + 1
        upgraded = False
        if site_level < TRIBE_CONTROLLED_SITE_MAX_LEVEL and site["yieldCount"] >= TRIBE_CONTROLLED_SITE_UPGRADE_COLLECTS:
            site["level"] = site_level + 1
            site["yieldCount"] = 0
            extend_from = datetime.now().timestamp()
            try:
                extend_from = max(extend_from, datetime.fromisoformat(site.get("activeUntil")).timestamp())
            except (TypeError, ValueError):
                pass
            site["activeUntil"] = datetime.fromtimestamp(
                extend_from + TRIBE_CONTROLLED_SITE_UPGRADE_EXTEND_MINUTES * 60
            ).isoformat()
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 2
            reward_parts.append(f"控制点升级Lv.{site['level']}")
            reward_parts.append("声望+2")
            upgraded = True
        member = tribe.get("members", {}).get(player_id, {})
        record = {
            "kind": "controlled_resource_site",
            "siteId": site.get("id"),
            "siteLabel": site.get("label", "控制资源点"),
            "siteLevel": site.get("level", 1),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "upgraded": upgraded,
            "createdAt": site["lastYieldAt"]
        }
        detail = f"{record['memberName']} 收取了{record['siteLabel']}的控制收益：{'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "world_event", "收取控制资源点", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def patrol_controlled_resource_site(self, player_id: str, site_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        sites = self._active_controlled_resource_sites(tribe)
        site = next((item for item in sites if item.get("id") == site_id), None)
        if not site:
            await self._send_tribe_error(player_id, "这个控制资源点已经消散")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(site.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(site.get("z", 0) or 0)
        if dx * dx + dz * dz > TRIBE_SCOUT_SITE_INTERACT_DISTANCE * TRIBE_SCOUT_SITE_INTERACT_DISTANCE:
            await self._send_tribe_error(player_id, "靠近控制资源点后才能巡守")
            return

        last_patrolled_at = site.get("lastPatrolledAt")
        if last_patrolled_at:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_patrolled_at)).total_seconds()
                if elapsed < TRIBE_CONTROLLED_SITE_PATROL_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil((TRIBE_CONTROLLED_SITE_PATROL_COOLDOWN_SECONDS - elapsed) / 60))
                    await self._send_tribe_error(player_id, f"这处资源点刚巡守过，还需约 {remaining} 分钟")
                    return
            except (TypeError, ValueError):
                pass

        site_level = max(1, int(site.get("level", 1) or 1))
        extend_minutes = TRIBE_CONTROLLED_SITE_PATROL_EXTEND_MINUTES + max(0, site_level - 1)
        extend_from = datetime.now().timestamp()
        try:
            extend_from = max(extend_from, datetime.fromisoformat(site.get("activeUntil")).timestamp())
        except (TypeError, ValueError):
            pass
        site["activeUntil"] = datetime.fromtimestamp(extend_from + extend_minutes * 60).isoformat()
        site["lastPatrolledAt"] = datetime.now().isoformat()
        site["patrolCount"] = int(site.get("patrolCount", 0) or 0) + 1

        reward_parts = [f"控制时间+{extend_minutes}分钟"]
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
        reward_parts.append("声望+1")
        if self._has_tribe_structure_type(tribe, "tribe_fence"):
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 1
            reward_parts.append("围栏巡守声望+1")
        if site.get("contestResolvedAs") == "trade_path":
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + 1
            reward_parts.append("通路信誉+1")
            other_id = site.get("contestedByTribeId")
            if other_id:
                progress = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
                progress["tradeTrust"] = max(0, min(9, int(progress.get("tradeTrust", 0) or 0) + 1))
                progress["lastAction"] = "controlled_site_patrol"
                progress["lastActionAt"] = site["lastPatrolledAt"]

        member = tribe.get("members", {}).get(player_id, {})
        site["lastPatrolledBy"] = member.get("name", "成员")
        record = {
            "kind": "controlled_resource_site_patrol",
            "siteId": site.get("id"),
            "siteLabel": site.get("label", "控制资源点"),
            "siteLevel": site.get("level", 1),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "createdAt": site["lastPatrolledAt"]
        }
        detail = f"{record['memberName']} 巡守了{record['siteLabel']}：{'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "governance", "巡守控制资源点", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()


    async def relay_controlled_resource_site(self, player_id: str, site_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not self._has_tribe_structure_type(tribe, "tribe_road"):
            await self._send_tribe_error(player_id, "需要先建造营地道路才能组织运输")
            return

        sites = self._active_controlled_resource_sites(tribe)
        site = next((item for item in sites if item.get("id") == site_id), None)
        if not site:
            await self._send_tribe_error(player_id, "这个控制资源点已经消散")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(site.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(site.get("z", 0) or 0)
        if dx * dx + dz * dz > TRIBE_SCOUT_SITE_INTERACT_DISTANCE * TRIBE_SCOUT_SITE_INTERACT_DISTANCE:
            await self._send_tribe_error(player_id, "靠近控制资源点后才能组织运输")
            return

        last_relayed_at = site.get("lastRelayedAt")
        if last_relayed_at:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_relayed_at)).total_seconds()
                if elapsed < TRIBE_CONTROLLED_SITE_RELAY_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil((TRIBE_CONTROLLED_SITE_RELAY_COOLDOWN_SECONDS - elapsed) / 60))
                    await self._send_tribe_error(player_id, f"这条运输路线刚整理过，还需约 {remaining} 分钟")
                    return
            except (TypeError, ValueError):
                pass

        source_reward = dict(site.get("reward") or {})
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        site_level = max(1, int(site.get("level", 1) or 1))
        relay_amount = 2 + site_level
        if int(source_reward.get("wood", 0) or 0):
            storage["wood"] = int(storage.get("wood", 0) or 0) + relay_amount
            reward_parts.append(f"木材+{relay_amount}")
        if int(source_reward.get("stone", 0) or 0):
            storage["stone"] = int(storage.get("stone", 0) or 0) + relay_amount
            reward_parts.append(f"石块+{relay_amount}")
        if int(source_reward.get("food", 0) or 0):
            tribe["food"] = int(tribe.get("food", 0) or 0) + relay_amount
            reward_parts.append(f"食物+{relay_amount}")
        if int(source_reward.get("discoveryProgress", 0) or 0):
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + 1
            reward_parts.append("发现进度+1")

        storage["wood"] = int(storage.get("wood", 0) or 0) + 1
        storage["stone"] = int(storage.get("stone", 0) or 0) + 1
        reward_parts.append("路线维护木材+1/石块+1")

        if site.get("contestResolvedAs") == "trade_path":
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + 1
            reward_parts.append("贸易信誉+1")

        extend_minutes = TRIBE_CONTROLLED_SITE_RELAY_EXTEND_MINUTES + max(0, site_level - 1)
        extend_from = datetime.now().timestamp()
        try:
            extend_from = max(extend_from, datetime.fromisoformat(site.get("activeUntil")).timestamp())
        except (TypeError, ValueError):
            pass
        site["activeUntil"] = datetime.fromtimestamp(extend_from + extend_minutes * 60).isoformat()
        site["lastRelayedAt"] = datetime.now().isoformat()
        site["relayCount"] = int(site.get("relayCount", 0) or 0) + 1
        site["roadLinked"] = True
        reward_parts.append(f"控制时间+{extend_minutes}分钟")

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        site["lastRelayedBy"] = member_name
        record = {
            "kind": "controlled_resource_site_relay",
            "siteId": site.get("id"),
            "siteLabel": site.get("label", "控制资源点"),
            "siteLevel": site.get("level", 1),
            "memberName": member_name,
            "rewardParts": reward_parts,
            "createdAt": site["lastRelayedAt"]
        }
        detail = f"{member_name} 组织了{record['siteLabel']}的道路运输：{'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "world_event", "控制点道路运输", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()


    async def compose_oral_epic(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以整理部落史诗")
            return

        history = [item for item in (tribe.get("history", []) or []) if isinstance(item, dict)]
        if len(history) < TRIBE_ORAL_EPIC_MIN_HISTORY:
            await self._send_tribe_error(player_id, f"至少需要 {TRIBE_ORAL_EPIC_MIN_HISTORY} 条部落日志才能整理史诗")
            return

        source_titles = [item.get("title", "部落记忆") for item in history[-5:]][-3:]
        epic = {
            "id": f"epic_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "title": f"{tribe.get('name', '部落')}口述史",
            "summary": f"长老把{'、'.join(source_titles)}编成夜火旁的故事。",
            "composedBy": member.get("name", "管理者"),
            "renownBonus": TRIBE_ORAL_EPIC_RENOWN_BONUS,
            "sourceTitles": source_titles,
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("oral_epics", []).append(epic)
        tribe["oral_epics"] = tribe["oral_epics"][-8:]
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + TRIBE_ORAL_EPIC_RENOWN_BONUS
        detail = f"{epic['composedBy']} 整理了《{epic['title']}》：{epic['summary']} 声望 +{TRIBE_ORAL_EPIC_RENOWN_BONUS}。"
        self._add_tribe_history(tribe, "ritual", "整理部落史诗", detail, player_id, {"kind": "oral_epic", **epic})
        await self._publish_world_rumor(
            "epic",
            "口述史诗",
            f"{tribe.get('name', '部落')} 的故事被传唱：{epic['summary']}",
            {"tribeId": tribe_id, "epicId": epic["id"], "renownBonus": TRIBE_ORAL_EPIC_RENOWN_BONUS}
        )
        await self.broadcast_tribe_state(tribe_id)


    async def choose_tribe_oath(self, player_id: str, oath_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以选择部落誓约")
            return
        if tribe.get("oath"):
            await self._send_tribe_error(player_id, "部落誓约已经确定")
            return
        oath = TRIBE_OATHS.get(oath_key)
        if not oath:
            await self._send_tribe_error(player_id, "未知部落誓约")
            return

        record = {
            "kind": "tribe_oath",
            "key": oath_key,
            "label": oath.get("label", "部落誓约"),
            "summary": oath.get("summary", ""),
            "chosenBy": member.get("name", "管理者"),
            "renownBonus": TRIBE_OATH_RENOWN_BONUS,
            "createdAt": datetime.now().isoformat()
        }
        tribe["oath"] = record
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + TRIBE_OATH_RENOWN_BONUS
        detail = f"{record['chosenBy']} 为部落立下{record['label']}：{record['summary']} 声望 +{TRIBE_OATH_RENOWN_BONUS}。"
        self._add_tribe_history(tribe, "governance", "立下部落誓约", detail, player_id, record)
        await self._publish_world_rumor(
            "oath",
            "部落誓约",
            f"{tribe.get('name', '部落')} 立下{record['label']}，此后的行动会围绕这条长期方向展开。",
            {"tribeId": tribe_id, "oathKey": oath_key, "renownBonus": TRIBE_OATH_RENOWN_BONUS}
        )
        await self.broadcast_tribe_state(tribe_id)

    def _dynamic_oath_task_plan(self, tribe: dict, oath_key: str) -> dict:
        env = self._get_current_environment()
        resource_tide = env.get("resourceTide") if isinstance(env.get("resourceTide"), dict) else None
        world_events = [item for item in (env.get("worldEvents", []) or []) if isinstance(item, dict)]
        season_objective = env.get("seasonObjective") if isinstance(env.get("seasonObjective"), dict) else None
        trade_requests = self._active_trade_requests_for_tribe(tribe.get("id"))
        boundary_outcomes = [item for item in (tribe.get("boundary_outcomes", []) or []) if isinstance(item, dict) and item.get("status") == "pending"]
        boundary_relations = dict(tribe.get("boundary_relations", {}) or {})

        variant_key = None
        if oath_key == "hearth":
            if int(tribe.get("food", 0) or 0) < 18:
                variant_key = "food_pressure"
            elif resource_tide:
                variant_key = "tide_harvest"
            else:
                variant_key = "camp_stock"
        elif oath_key == "trail":
            if season_objective:
                variant_key = "season_objective"
            elif world_events:
                variant_key = "world_event"
            else:
                variant_key = "cave_route"
        elif oath_key == "trade":
            if trade_requests:
                variant_key = "open_trade"
            elif boundary_outcomes or any(int((item or {}).get("tradeTrust", 0) or 0) >= 3 for item in boundary_relations.values()):
                variant_key = "border_trade"
            else:
                variant_key = "gift_pack"
        elif oath_key == "beast":
            if int(tribe.get("tamed_beasts", 0) or 0) <= 0:
                variant_key = "tame_young"
            elif any(int((item or {}).get("score", 0) or 0) <= -2 for item in boundary_relations.values()):
                variant_key = "border_guard"
            else:
                variant_key = "beast_haul" if resource_tide else "border_guard"

        variant_pool = TRIBE_OATH_TASK_VARIANTS.get(oath_key, [])
        variant = next((item for item in variant_pool if item.get("key") == variant_key), None)
        if variant:
            return dict(variant)
        return dict(TRIBE_OATH_TASK_REWARDS.get(oath_key, {}))

    def _current_oath_task(self, tribe: dict) -> Optional[dict]:
        oath = self._tribe_oath(tribe)
        if not oath:
            return None
        oath_key = oath.get("key")
        plan = self._dynamic_oath_task_plan(tribe, oath_key)
        if not plan:
            return None
        task_day = datetime.now().strftime("%Y-%m-%d")
        task_id = f"{task_day}:{oath_key}"
        completed = task_id in set(tribe.get("completed_oath_tasks", []) or [])
        return {
            "id": task_id,
            "oathKey": oath_key,
            "oathLabel": oath.get("label", "部落誓约"),
            "title": plan.get("title", "誓约任务"),
            "summary": plan.get("summary", ""),
            "sourceLabel": plan.get("sourceLabel", ""),
            "variantKey": plan.get("key", oath_key),
            "reward": dict(plan),
            "completed": completed,
            "streak": dict(tribe.get("oath_task_streak", {})),
            "streakTarget": TRIBE_OATH_TASK_STREAK_TARGET
        }

    def _update_oath_task_streak(self, tribe: dict, oath_key: str) -> tuple:
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        streak = tribe.get("oath_task_streak") if isinstance(tribe.get("oath_task_streak"), dict) else {}
        last_date_text = streak.get("lastDate")
        last_oath = streak.get("oathKey")
        count = 1
        if last_oath == oath_key and last_date_text == yesterday.isoformat():
            count = int(streak.get("count", 0) or 0) + 1
        tribe["oath_task_streak"] = {
            "oathKey": oath_key,
            "count": count,
            "lastDate": today.isoformat(),
            "target": TRIBE_OATH_TASK_STREAK_TARGET
        }
        return count, count >= TRIBE_OATH_TASK_STREAK_TARGET

    def _create_joint_watch_scout_sites(self, tribe: dict, other_tribe: dict, flag: dict, relation: dict, member_name: str) -> list:
        other_flag = next((
            item for item in (other_tribe.get("territory_flags", []) or [])
            if isinstance(item, dict) and item.get("id") == relation.get("otherFlagId")
        ), None)
        if not other_flag:
            return []

        own_x = float(flag.get("x", 0) or 0)
        own_z = float(flag.get("z", 0) or 0)
        other_x = float(other_flag.get("x", 0) or 0)
        other_z = float(other_flag.get("z", 0) or 0)
        mid_x = (own_x + other_x) / 2
        mid_z = (own_z + other_z) / 2
        nearest_region = min(
            WORLD_REGIONS,
            key=lambda region: (mid_x - region["x"]) ** 2 + (mid_z - region["z"]) ** 2
        )
        region_type = nearest_region.get("type", "region_forest")
        site_reward = TRIBE_SCOUT_SITE_REWARDS.get(region_type, TRIBE_SCOUT_SITE_REWARDS["region_forest"])
        angle = random.random() * math.pi * 2
        distance = random.randint(5, max(8, min(18, int(nearest_region.get("radius", 18) or 18))))
        site_x = max(-490, min(490, mid_x + math.cos(angle) * distance))
        site_z = max(-490, min(490, mid_z + math.sin(angle) * distance))
        now_text = datetime.now().isoformat()
        active_until = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_SCOUT_SITE_ACTIVE_MINUTES * 60).isoformat()
        shared_id = f"joint_watch_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}"
        shared_label = f"联合守望线索：{site_reward.get('label', '资源点')}"
        created_sites = []
        for target_tribe, partner_tribe in ((tribe, other_tribe), (other_tribe, tribe)):
            target_id = target_tribe.get("id")
            if not target_id:
                continue
            site = {
                "id": f"{shared_id}_{target_id}",
                "tribeId": target_id,
                "type": "scouted_resource_site",
                "label": shared_label,
                "regionType": region_type,
                "regionLabel": nearest_region.get("label", "边界地带"),
                "resourceLabel": site_reward.get("label", "资源点"),
                "x": site_x,
                "z": site_z,
                "size": 1.05,
                "reward": {key: value for key, value in site_reward.items() if key != "label"},
                "foundBy": member_name,
                "status": "active",
                "sharedByTribeId": tribe.get("id"),
                "sharedWithTribeId": partner_tribe.get("id"),
                "sharedWithTribeName": partner_tribe.get("name", "其他部落"),
                "jointWatchId": shared_id,
                "createdAt": now_text,
                "activeUntil": active_until
            }
            target_tribe.setdefault("scouted_resource_sites", []).append(site)
            target_tribe["scouted_resource_sites"] = target_tribe["scouted_resource_sites"][-TRIBE_SCOUT_SITE_LIMIT:]
            created_sites.append(site)
        return created_sites

    async def complete_oath_task(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = self._current_oath_task(tribe)
        if not task:
            await self._send_tribe_error(player_id, "部落还没有立下誓约")
            return
        if task.get("completed"):
            await self._send_tribe_error(player_id, "今天的誓约任务已经完成")
            return

        reward = dict(task.get("reward") or {})
        if task.get("oathKey") == "beast" and int(tribe.get("tamed_beasts", 0) or 0) <= 0 and int(reward.get("tamedBeasts", 0) or 0) <= 0:
            await self._send_tribe_error(player_id, "兽伴誓约任务需要先驯养幼兽")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        for resource_key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(reward.get(resource_key, 0) or 0)
            if amount:
                storage[resource_key] = int(storage.get(resource_key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = int(reward.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        renown = int(reward.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        progress = int(reward.get("discoveryProgress", 0) or 0)
        if progress:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + progress
            reward_parts.append(f"发现进度+{progress}")
        trade_rep = int(reward.get("tradeReputation", 0) or 0)
        if trade_rep:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_rep
            reward_parts.append(f"贸易信誉+{trade_rep}")
        beast_exp = int(reward.get("beastExperience", 0) or 0)
        if beast_exp:
            tribe["beast_experience"] = int(tribe.get("beast_experience", 0) or 0) + beast_exp
            reward_parts.append(f"幼兽熟练度+{beast_exp}")

        tamed_beasts = int(reward.get("tamedBeasts", 0) or 0)
        if tamed_beasts:
            tribe["tamed_beasts"] = int(tribe.get("tamed_beasts", 0) or 0) + tamed_beasts
            reward_parts.append(f"驯养幼兽+{tamed_beasts}")
        streak_count, streak_unlocked = self._update_oath_task_streak(tribe, task.get("oathKey"))
        if streak_unlocked:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + 8
            tribe["oath_task_streak"]["count"] = 0
            tribe["celebration_buff"] = {
                "type": "oath_streak",
                "title": "誓约连胜余韵",
                "gatherBonus": 1 if task.get("oathKey") == "hearth" else 0,
                "discoveryBonus": 1 if task.get("oathKey") == "trail" else 0,
                "tradeRenownBonus": 1 if task.get("oathKey") == "trade" else 0,
                "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + 8 * 60).isoformat()
            }
            if task.get("oathKey") == "beast":
                tribe["food"] = int(tribe.get("food", 0) or 0) + 8
                reward_parts.append("兽伴连胜食物+8")
            reward_parts.append("誓约连胜声望+8")

        completed = list(tribe.get("completed_oath_tasks", []) or [])
        completed.append(task["id"])
        tribe["completed_oath_tasks"] = completed[-14:]
        member = tribe.get("members", {}).get(player_id, {})
        record = {
            "kind": "oath_task",
            "taskId": task["id"],
            "oathKey": task.get("oathKey"),
            "oathLabel": task.get("oathLabel"),
            "title": task.get("title"),
            "summary": task.get("summary"),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "streakCount": streak_count,
            "streakUnlocked": streak_unlocked,
            "streakTarget": TRIBE_OATH_TASK_STREAK_TARGET,
            "createdAt": datetime.now().isoformat()
        }
        detail = f"{record['memberName']} 完成誓约任务「{record['title']}」：{record['summary']} {'、'.join(reward_parts)}。"
        if streak_unlocked:
            detail += " 连续践行誓约后，营地出现了短暂的庆祝余韵。"
        self._add_tribe_history(tribe, "governance", "完成誓约任务", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "oath",
            "誓约任务",
            f"{tribe.get('name', '部落')} 完成了{record['oathLabel']}的轻量目标：{record['title']}。",
            {"tribeId": tribe_id, "taskId": task["id"], "oathKey": task.get("oathKey")}
        )
        await self.broadcast_tribe_state(tribe_id)

    async def resolve_boundary_action(self, player_id: str, flag_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_BOUNDARY_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知边界行动")
            return
        flags = tribe.get("territory_flags", []) or []
        flag = next((item for item in flags if isinstance(item, dict) and item.get("id") == flag_id), None)
        if not flag:
            await self._send_tribe_error(player_id, "只能在本部落旗帜处理边界")
            return
        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(flag.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(flag.get("z", 0) or 0)
        if dx * dx + dz * dz > 10 * 10:
            await self._send_tribe_error(player_id, "靠近边界旗帜后才能行动")
            return
        relation = self._flag_boundary_relation(tribe_id, flag)
        if not relation:
            await self._send_tribe_error(player_id, "这面旗帜附近还没有形成边界关系")
            return
        other_tribe_id = relation.get("otherTribeId")
        allowed_states = action.get("allowedStates")
        if allowed_states and relation.get("state") not in allowed_states:
            await self._send_tribe_error(player_id, f"{action.get('label', '边界行动')}只能在紧张或敌意边界使用")
            return
        if action.get("pressure"):
            active_truce = next((
                item for item in self._active_boundary_truces(tribe)
                if isinstance(item, dict) and item.get("otherTribeId") == other_tribe_id
            ), None)
            if active_truce:
                await self._send_tribe_error(player_id, "停争保护仍在，暂时不能继续施压")
                return
        cooldowns = flag.setdefault("boundaryActionCooldowns", {})
        cooldown_key = f"{action_key}:{relation.get('otherTribeId')}"
        last_action_at = cooldowns.get(cooldown_key)
        if last_action_at:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(last_action_at)).total_seconds()
                if elapsed < TRIBE_BOUNDARY_ACTION_COOLDOWN_SECONDS:
                    remaining = max(1, math.ceil((TRIBE_BOUNDARY_ACTION_COOLDOWN_SECONDS - elapsed) / 60))
                    await self._send_tribe_error(player_id, f"这条边界刚处理过，还需约 {remaining} 分钟")
                    return
            except (TypeError, ValueError):
                pass

        food_cost = int(action.get("foodCost", 0) or 0)
        if action.get("pressure") and relation.get("state") == "hostile":
            food_cost += TRIBE_BOUNDARY_HOSTILE_FOOD_COST
        if food_cost and int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"{action.get('label')}需要食物 {food_cost}")
            return
        if food_cost:
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost

        reward_parts = []
        renown = int(action.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        trade_rep = int(action.get("tradeReputation", 0) or 0)
        if trade_rep:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_rep
            reward_parts.append(f"贸易信誉+{trade_rep}")
        if food_cost:
            reward_parts.append(f"食物-{food_cost}")

        boundary_progress = {}
        affected_tribe_ids = set()
        other_tribe = None
        pressure_chain_count = 0
        if action.get("clearIncomingPressure"):
            before_count = len(tribe.get("boundary_pressures", []) or [])
            tribe["boundary_pressures"] = [
                item for item in (tribe.get("boundary_pressures", []) or [])
                if not (
                    isinstance(item, dict)
                    and item.get("otherTribeId") == other_tribe_id
                    and item.get("state") == "pressured"
                )
            ]
            cleared_count = before_count - len(tribe.get("boundary_pressures", []) or [])
            if cleared_count:
                reward_parts.append("解除边界压力")
                if self._has_tribe_structure_type(tribe, "tribe_fence"):
                    tribe["renown"] = int(tribe.get("renown", 0) or 0) + 2
                    reward_parts.append("围栏守边声望+2")
        if action.get("clearOutgoingPressure"):
            before_count = len(tribe.get("boundary_pressures", []) or [])
            tribe["boundary_pressures"] = [
                item for item in (tribe.get("boundary_pressures", []) or [])
                if not (
                    isinstance(item, dict)
                    and item.get("otherTribeId") == other_tribe_id
                    and item.get("state") == "pressing"
                )
            ]
            cleared_count = before_count - len(tribe.get("boundary_pressures", []) or [])
            if cleared_count:
                reward_parts.append("撤回己方压力")
        if other_tribe_id:
            relation_records = tribe.setdefault("boundary_relations", {})
            boundary_progress = relation_records.setdefault(other_tribe_id, {})
            if action.get("pressure"):
                pressure_chain_count = sum(
                    1 for item in self._active_boundary_pressures(tribe)
                    if isinstance(item, dict)
                    and item.get("otherTribeId") == other_tribe_id
                    and item.get("state") == "pressing"
                )
            relation_delta = int(action.get("relationDelta", 0) or 0)
            if pressure_chain_count:
                relation_delta -= 1
            trade_delta = int(action.get("tradeTrustDelta", 0) or 0)
            if relation_delta:
                boundary_progress["score"] = max(-9, min(9, int(boundary_progress.get("score", 0) or 0) + relation_delta))
                reward_parts.append(f"关系{relation_delta:+d}")
            if trade_delta:
                boundary_progress["tradeTrust"] = max(0, min(9, int(boundary_progress.get("tradeTrust", 0) or 0) + trade_delta))
                reward_parts.append(f"信任+{trade_delta}")
            boundary_progress["lastAction"] = action_key
            boundary_progress["lastActionAt"] = datetime.now().isoformat()
            relation_records[other_tribe_id] = boundary_progress
            other_tribe = self.tribes.get(other_tribe_id)
            if other_tribe:
                other_progress = other_tribe.setdefault("boundary_relations", {}).setdefault(tribe_id, {})
                if relation_delta:
                    other_progress["score"] = max(-9, min(9, int(other_progress.get("score", 0) or 0) + relation_delta))
                if trade_delta:
                    other_progress["tradeTrust"] = max(0, min(9, int(other_progress.get("tradeTrust", 0) or 0) + trade_delta))
                other_progress["lastAction"] = f"incoming:{action_key}"
                other_progress["lastActionAt"] = boundary_progress["lastActionAt"]
                trade_disrupt = int(action.get("tradeDisrupt", 0) or 0)
                if trade_disrupt:
                    other_tribe["trade_reputation"] = max(0, int(other_tribe.get("trade_reputation", 0) or 0) - trade_disrupt)
                    reward_parts.append(f"扰乱对方信誉-{trade_disrupt}")
                renown_disrupt = int(action.get("renownDisrupt", 0) or 0)
                if renown_disrupt:
                    other_tribe["renown"] = max(0, int(other_tribe.get("renown", 0) or 0) - renown_disrupt)
                    reward_parts.append(f"压低对方声望-{renown_disrupt}")
                aid_food = int(action.get("aidFood", 0) or 0)
                if aid_food:
                    other_tribe["food"] = int(other_tribe.get("food", 0) or 0) + aid_food
                    affected_tribe_ids.add(other_tribe_id)
                    reward_parts.append(f"援助对方食物+{aid_food}")
                if action.get("clearOutgoingPressure"):
                    before_count = len(other_tribe.get("boundary_pressures", []) or [])
                    other_tribe["boundary_pressures"] = [
                        item for item in (other_tribe.get("boundary_pressures", []) or [])
                        if not (
                            isinstance(item, dict)
                            and item.get("otherTribeId") == tribe_id
                            and item.get("state") == "pressured"
                        )
                    ]
                    if before_count != len(other_tribe.get("boundary_pressures", []) or []):
                        affected_tribe_ids.add(other_tribe_id)
                if action.get("truce"):
                    active_until = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_BOUNDARY_TRUCE_MINUTES * 60).isoformat()
                    truce_record = {
                        "id": f"truce_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                        "state": "truce",
                        "title": action.get("label", "停争保护"),
                        "summary": f"与 {other_tribe.get('name', '其他部落')} 的边界进入短时停争，期间不能继续施压。",
                        "otherTribeId": other_tribe_id,
                        "otherTribeName": other_tribe.get("name", "其他部落"),
                        "activeUntil": active_until,
                        "createdAt": boundary_progress["lastActionAt"]
                    }
                    incoming_truce = {
                        **truce_record,
                        "id": f"incoming_truce_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                        "summary": f"{tribe.get('name', '对方部落')} 提出停争，边界进入短时保护。",
                        "otherTribeId": tribe_id,
                        "otherTribeName": tribe.get("name", "对方部落")
                    }
                    tribe.setdefault("boundary_truces", []).append(truce_record)
                    tribe["boundary_truces"] = tribe["boundary_truces"][-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                    other_tribe.setdefault("boundary_truces", []).append(incoming_truce)
                    other_tribe["boundary_truces"] = other_tribe["boundary_truces"][-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                    affected_tribe_ids.add(other_tribe_id)
                    reward_parts.append(f"停争保护{TRIBE_BOUNDARY_TRUCE_MINUTES}分钟")
                if action.get("pressure"):
                    active_until = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_BOUNDARY_PRESSURE_MINUTES * 60).isoformat()
                    pressure_title = action.get("label", "边界压力")
                    pressure_record = {
                        "id": f"pressure_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                        "state": "pressing",
                        "title": pressure_title,
                        "summary": f"对 {other_tribe.get('name', '其他部落')} 的边界行动正在施压。",
                        "otherTribeId": other_tribe_id,
                        "otherTribeName": other_tribe.get("name", "其他部落"),
                        "activeUntil": active_until,
                        "createdAt": boundary_progress["lastActionAt"]
                    }
                    incoming_record = {
                        "id": f"incoming_pressure_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                        "state": "pressured",
                        "title": f"遭遇{pressure_title}",
                        "summary": f"{tribe.get('name', '对方部落')} 正在边界施加压力，营地行动受到压迫。",
                        "otherTribeId": tribe_id,
                        "otherTribeName": tribe.get("name", "对方部落"),
                        "activeUntil": active_until,
                        "createdAt": boundary_progress["lastActionAt"]
                    }
                    tribe.setdefault("boundary_pressures", []).append(pressure_record)
                    tribe["boundary_pressures"] = tribe["boundary_pressures"][-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                    other_tribe.setdefault("boundary_pressures", []).append(incoming_record)
                    other_tribe["boundary_pressures"] = other_tribe["boundary_pressures"][-TRIBE_BOUNDARY_OUTCOME_LIMIT:]
                    affected_tribe_ids.add(other_tribe_id)
                    reward_parts.append(f"边界压制{TRIBE_BOUNDARY_PRESSURE_MINUTES}分钟")
            relation = self._flag_boundary_relation(tribe_id, flag) or relation
            affected_tribe_ids.update(self._ensure_boundary_outcome(tribe, relation))
            if action.get("pressure") and pressure_chain_count:
                reward_parts.append(f"压力连锁x{pressure_chain_count + 1}")

        member = tribe.get("members", {}).get(player_id, {})
        if action.get("sharedScout") and other_tribe:
            shared_sites = self._create_joint_watch_scout_sites(
                tribe,
                other_tribe,
                flag,
                relation,
                member.get("name", "成员")
            )
            if shared_sites:
                affected_tribe_ids.add(other_tribe_id)
                reward_parts.append("共享资源线索+1")
        record = {
            "kind": "boundary_action",
            "flagId": flag.get("id"),
            "flagLabel": flag.get("label", "领地旗帜"),
            "actionKey": action_key,
            "actionLabel": action.get("label", "边界行动"),
            "summary": action.get("summary", ""),
            "memberName": member.get("name", "成员"),
            "relation": relation,
            "relationProgress": dict(boundary_progress),
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        cooldowns[cooldown_key] = record["createdAt"]
        tribe.setdefault("boundary_actions", []).append(record)
        tribe["boundary_actions"] = tribe["boundary_actions"][-12:]
        detail = f"{record['memberName']} 在{record['flagLabel']}执行{record['actionLabel']}：{record['summary']} {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "governance", "边界行动", detail, player_id, record)
        await self._publish_world_rumor(
            "territory",
            f"边界{record['actionLabel']}",
            f"{tribe.get('name', '部落')} 在与 {relation.get('otherTribeName', '其他部落')} 的{relation.get('label', '边界')}上执行{record['actionLabel']}。",
            {"tribeId": tribe_id, "flagId": flag_id, "action": action_key, "relation": relation}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        if other_tribe_id and other_tribe_id in affected_tribe_ids:
            await self._notify_tribe(
                other_tribe_id,
                f"{tribe.get('name', '对方部落')} 在共同边界上执行了{record['actionLabel']}，部落面板出现了可回应的边界机会。"
            )
            await self.broadcast_tribe_state(other_tribe_id)
        if action.get("sharedScout") and reward_parts:
            await self._broadcast_current_map()
