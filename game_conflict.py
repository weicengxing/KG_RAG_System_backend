import random
from datetime import datetime

from game_config import *


class GameConflictMixin:
    def _small_conflict_record_for_tribe(self, conflict_id: str, tribe_id: str):
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            return None
        return next((
            item for item in tribe.get("small_conflicts", []) or []
            if isinstance(item, dict) and item.get("id") == conflict_id
        ), None)

    def _small_conflict_scout_site(self, tribe: dict, site_id: str):
        if not tribe or not site_id:
            return None
        return next((
            item for item in (tribe.get("scouted_resource_sites", []) or [])
            if isinstance(item, dict) and item.get("id") == site_id
        ), None)

    def _small_conflict_controlled_site(self, tribe: dict, site_id: str):
        if not tribe or not site_id:
            return None
        controlled_id = site_id if str(site_id).startswith("controlled_") else f"controlled_{site_id}"
        return next((
            item for item in (tribe.get("controlled_resource_sites", []) or [])
            if isinstance(item, dict) and item.get("id") in {site_id, controlled_id}
        ), None)

    def _small_conflict_target_site(self, tribe: dict, conflict: dict):
        if not tribe or not conflict:
            return None
        if conflict.get("targetKind") == "boundary_flag":
            flag_id = conflict.get("targetFlagId") or conflict.get("siteId")
            return next((
                item for item in (tribe.get("territory_flags", []) or [])
                if isinstance(item, dict) and item.get("id") == flag_id
            ), None)
        if conflict.get("targetKind") == "boundary_road":
            road_id = conflict.get("targetRoadId") or conflict.get("siteId")
            return next((
                item for item in (tribe.get("camp", {}).get("buildings", []) or [])
                if isinstance(item, dict) and item.get("id") == road_id
            ), None)
        if conflict.get("targetKind") == "cave_entrance":
            cave_id = conflict.get("targetCaveId") or conflict.get("siteId")
            return next((
                item for item in self._get_base_landmarks()
                if isinstance(item, dict) and item.get("id") == cave_id
            ), None)
        site_id = conflict.get("targetSiteId") or conflict.get("siteId")
        return (
            self._small_conflict_scout_site(tribe, site_id)
            or self._small_conflict_controlled_site(tribe, site_id)
        )

    def _small_conflict_boundary_target(self, tribe: dict, other_tribe: dict, outcome: dict):
        other_id = other_tribe.get("id") if other_tribe else outcome.get("otherTribeId")
        flag = None
        for item in tribe.get("territory_flags", []) or []:
            if not isinstance(item, dict):
                continue
            relation = self._flag_boundary_relation(tribe.get("id"), item)
            if relation and relation.get("otherTribeId") == other_id:
                flag = item
                break
        if not flag:
            flag = next((item for item in tribe.get("territory_flags", []) or [] if isinstance(item, dict)), None)
        if not flag:
            return None
        road = next((
            item for item in (tribe.get("camp", {}).get("buildings", []) or [])
            if isinstance(item, dict) and item.get("type") == "tribe_road"
        ), None)
        if road and outcome.get("state") == "hostile":
            return {
                "kind": "boundary_road",
                "id": road.get("id"),
                "label": road.get("label", "营地道路"),
                "x": float(road.get("x", flag.get("x", 0)) or 0),
                "z": float(road.get("z", flag.get("z", 0)) or 0),
                "flagId": flag.get("id")
            }
        return {
            "kind": "boundary_flag",
            "id": flag.get("id"),
            "label": flag.get("label", "领地旗帜"),
            "x": float(flag.get("x", 0) or 0),
            "z": float(flag.get("z", 0) or 0),
            "flagId": flag.get("id")
        }

    def _small_conflict_boundary_flags(self, tribe: dict, other_tribe: dict):
        if not tribe or not other_tribe:
            return None, None
        other_id = other_tribe.get("id")
        for flag in tribe.get("territory_flags", []) or []:
            if not isinstance(flag, dict):
                continue
            relation = self._flag_boundary_relation(tribe.get("id"), flag)
            if not relation or relation.get("otherTribeId") != other_id:
                continue
            other_flag = next((
                item for item in (other_tribe.get("territory_flags", []) or [])
                if isinstance(item, dict) and item.get("id") == relation.get("otherFlagId")
            ), None)
            if other_flag:
                return flag, other_flag
        return None, None

    def _small_conflict_cave_target(self, tribe: dict, other_tribe: dict, outcome: dict):
        if not tribe or not other_tribe or outcome.get("state") != "hostile":
            return None
        own_flag, other_flag = self._small_conflict_boundary_flags(tribe, other_tribe)
        if not own_flag or not other_flag:
            return None
        mid_x = (float(own_flag.get("x", 0) or 0) + float(other_flag.get("x", 0) or 0)) / 2
        mid_z = (float(own_flag.get("z", 0) or 0) + float(other_flag.get("z", 0) or 0)) / 2
        caves = [
            item for item in self._get_base_landmarks()
            if isinstance(item, dict) and item.get("type") == "cave_entrance"
        ]
        if not caves:
            return None
        cave = min(
            caves,
            key=lambda item: (mid_x - float(item.get("x", 0) or 0)) ** 2 + (mid_z - float(item.get("z", 0) or 0)) ** 2
        )
        dx = mid_x - float(cave.get("x", 0) or 0)
        dz = mid_z - float(cave.get("z", 0) or 0)
        if dx * dx + dz * dz > TRIBE_SKIRMISH_CAVE_RADIUS * TRIBE_SKIRMISH_CAVE_RADIUS:
            return None
        return {
            "kind": "cave_entrance",
            "id": cave.get("id"),
            "label": cave.get("label", "洞口"),
            "x": float(cave.get("x", 0) or 0),
            "z": float(cave.get("z", 0) or 0),
            "caveId": cave.get("id")
        }

    def _small_conflict_duplicate(self, tribe: dict, other_tribe: dict, outcome: dict):
        site_ids = {
            outcome.get("siteId"),
            outcome.get("otherSiteId"),
            outcome.get("contestSiteId"),
            outcome.get("targetId"),
            outcome.get("flagId"),
            outcome.get("roadId"),
            outcome.get("caveId")
        }
        site_ids = {item for item in site_ids if item}
        for target_tribe in (tribe, other_tribe):
            if not target_tribe:
                continue
            for item in self._active_small_conflicts(target_tribe):
                if item.get("outcomeId") == outcome.get("id"):
                    return item
                conflict_sites = {
                    item.get("siteId"),
                    item.get("otherSiteId"),
                    item.get("targetSiteId"),
                    item.get("targetFlagId"),
                    item.get("targetRoadId"),
                    item.get("targetCaveId")
                }
                if site_ids.intersection({site for site in conflict_sites if site}):
                    return item
        return None

    def _mark_small_conflict_outcomes(self, tribe: dict, other_tribe_id: str, site_ids: set, now_text: str):
        for outcome in tribe.get("boundary_outcomes", []) or []:
            if not isinstance(outcome, dict):
                continue
            outcome_sites = {
                outcome.get("siteId"),
                outcome.get("otherSiteId"),
                outcome.get("contestSiteId"),
                outcome.get("targetId"),
                outcome.get("flagId"),
                outcome.get("roadId"),
                outcome.get("caveId")
            }
            if outcome.get("otherTribeId") == other_tribe_id and site_ids.intersection({item for item in outcome_sites if item}):
                outcome["status"] = "resolved"
                outcome["responseLabel"] = "小规模冲突"
                outcome["resolvedAt"] = now_text

    def _promote_small_conflict_winner_site(self, tribe: dict, site_id: str, player_id: str, now_text: str) -> bool:
        site = self._small_conflict_scout_site(tribe, site_id)
        if not site:
            controlled = self._small_conflict_controlled_site(tribe, site_id)
            if controlled:
                controlled["contestResolvedAs"] = "small_conflict_win"
                extend_from = datetime.now().timestamp()
                try:
                    extend_from = max(extend_from, datetime.fromisoformat(controlled.get("activeUntil")).timestamp())
                except (TypeError, ValueError):
                    pass
                controlled["activeUntil"] = datetime.fromtimestamp(
                    extend_from + TRIBE_CONTROLLED_SITE_PATROL_EXTEND_MINUTES * 60
                ).isoformat()
            return False

        site["contested"] = False
        site["contestResolvedAs"] = "small_conflict_win"
        site["status"] = "secured"
        site["securedAt"] = now_text
        site["securedBy"] = player_id
        controlled_id = f"controlled_{site.get('id')}"
        if not self._small_conflict_controlled_site(tribe, site.get("id")):
            member = tribe.get("members", {}).get(player_id, {})
            controlled_site = {
                **site,
                "id": controlled_id,
                "type": "controlled_resource_site",
                "status": "controlled",
                "level": 1,
                "yieldCount": 0,
                "patrolCount": 0,
                "relayCount": 0,
                "roadLinked": self._has_tribe_structure_type(tribe, "tribe_road"),
                "securedByName": member.get("name", "集结成员"),
                "controlledAt": now_text,
                "lastYieldAt": None,
                "lastPatrolledAt": None,
                "lastRelayedAt": None,
                "activeUntil": datetime.fromtimestamp(
                    datetime.now().timestamp() + TRIBE_CONTROLLED_SITE_ACTIVE_MINUTES * 60
                ).isoformat()
            }
            tribe.setdefault("controlled_resource_sites", []).append(controlled_site)
            tribe["controlled_resource_sites"] = tribe["controlled_resource_sites"][-TRIBE_CONTROLLED_SITE_LIMIT:]
        tribe["scouted_resource_sites"] = [
            item for item in (tribe.get("scouted_resource_sites", []) or [])
            if not (isinstance(item, dict) and item.get("id") == site.get("id"))
        ]
        return True

    def _cede_small_conflict_loser_site(self, tribe: dict, site_id: str):
        if not tribe or not site_id:
            return False
        before_scouts = len(tribe.get("scouted_resource_sites", []) or [])
        tribe["scouted_resource_sites"] = [
            item for item in (tribe.get("scouted_resource_sites", []) or [])
            if not (isinstance(item, dict) and item.get("id") == site_id)
        ]
        before_controls = len(tribe.get("controlled_resource_sites", []) or [])
        controlled_id = site_id if str(site_id).startswith("controlled_") else f"controlled_{site_id}"
        tribe["controlled_resource_sites"] = [
            item for item in (tribe.get("controlled_resource_sites", []) or [])
            if not (isinstance(item, dict) and item.get("id") in {site_id, controlled_id})
        ]
        return (
            before_scouts != len(tribe.get("scouted_resource_sites", []) or [])
            or before_controls != len(tribe.get("controlled_resource_sites", []) or [])
        )

    def _apply_small_conflict_boundary_result(self, winner: dict, loser: dict, winner_record: dict):
        if not winner or not winner_record or winner_record.get("targetKind") not in {"boundary_flag", "boundary_road"}:
            return []
        result_parts = []
        target_kind = winner_record.get("targetKind")
        if target_kind == "boundary_road":
            winner["trade_reputation"] = int(winner.get("trade_reputation", 0) or 0) + TRIBE_SKIRMISH_ROAD_TRADE_REWARD
            result_parts.append(f"胜方道路通行权+{TRIBE_SKIRMISH_ROAD_TRADE_REWARD}")
            if loser:
                loser["trade_reputation"] = max(0, int(loser.get("trade_reputation", 0) or 0) - 1)
                result_parts.append("败方贸易信誉-1")
        else:
            winner["renown"] = int(winner.get("renown", 0) or 0) + TRIBE_SKIRMISH_FLAG_RENOWN_REWARD
            result_parts.append(f"胜方旗帜声望+{TRIBE_SKIRMISH_FLAG_RENOWN_REWARD}")
            flag_id = winner_record.get("targetFlagId") or winner_record.get("siteId")
            flag = next((
                item for item in (winner.get("territory_flags", []) or [])
                if isinstance(item, dict) and item.get("id") == flag_id
            ), None)
            if flag:
                flag["lastSkirmishWonAt"] = datetime.now().isoformat()
                flag["skirmishHold"] = int(flag.get("skirmishHold", 0) or 0) + 1
        return result_parts

    def _apply_small_conflict_cave_result(self, winner: dict, loser: dict, winner_record: dict):
        if not winner or not winner_record or winner_record.get("targetKind") != "cave_entrance":
            return []
        winner["discovery_progress"] = int(winner.get("discovery_progress", 0) or 0) + TRIBE_SKIRMISH_CAVE_DISCOVERY_REWARD
        winner["renown"] = int(winner.get("renown", 0) or 0) + TRIBE_SKIRMISH_FLAG_RENOWN_REWARD
        cave_record = {
            "id": f"cave_hold_{winner_record.get('targetCaveId') or winner_record.get('siteId')}",
            "caveId": winner_record.get("targetCaveId") or winner_record.get("siteId"),
            "label": winner_record.get("siteLabel", "洞口"),
            "wonAt": datetime.now().isoformat()
        }
        winner.setdefault("cave_holds", []).append(cave_record)
        winner["cave_holds"] = winner["cave_holds"][-3:]
        if loser:
            loser["discovery_progress"] = max(0, int(loser.get("discovery_progress", 0) or 0) - 1)
        return [f"胜方洞口发现进度+{TRIBE_SKIRMISH_CAVE_DISCOVERY_REWARD}", "胜方洞口声望+3"]

    def _record_small_conflict_war_pressure(self, winner_id: str, loser_id: str, conflict: dict, now_text: str):
        if not winner_id or not loser_id:
            return
        for tribe_id, other_id, state in ((winner_id, loser_id, "won"), (loser_id, winner_id, "lost")):
            tribe = self.tribes.get(tribe_id)
            if not tribe:
                continue
            progress = tribe.setdefault("boundary_relations", {}).setdefault(other_id, {})
            pressure = min(
                TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD,
                int(progress.get("warPressure", 0) or 0) + 1
            )
            progress["warPressure"] = pressure
            progress["lastWarPressureAt"] = now_text
            progress["canDeclareWar"] = pressure >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            progress["lastWarTargetKind"] = conflict.get("targetKind") or conflict.get("kind") or "border_front"
            progress["lastWarTargetLabel"] = conflict.get("siteLabel") or conflict.get("title") or "边境战线"
            record = {
                "id": f"war_pressure_{int(datetime.now().timestamp() * 1000)}_{tribe_id}",
                "otherTribeId": other_id,
                "otherTribeName": (self.tribes.get(other_id) or {}).get("name", "其他部落"),
                "pressure": pressure,
                "threshold": TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD,
                "state": state,
                "targetKind": conflict.get("targetKind") or conflict.get("kind"),
                "siteLabel": conflict.get("siteLabel"),
                "canDeclareWar": pressure >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD,
                "createdAt": now_text
            }
            tribe.setdefault("war_pressure", []).append(record)
            tribe["war_pressure"] = tribe["war_pressure"][-6:]

    def _public_war_pressure(self, tribe: dict):
        active = []
        for item in tribe.get("war_pressure", []) or []:
            if not isinstance(item, dict):
                continue
            active.append({
                "otherTribeId": item.get("otherTribeId"),
                "otherTribeName": item.get("otherTribeName", "其他部落"),
                "pressure": int(item.get("pressure", 0) or 0),
                "threshold": int(item.get("threshold", TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD) or TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD),
                "targetKind": item.get("targetKind"),
                "siteLabel": item.get("siteLabel"),
                "canDeclareWar": bool(item.get("canDeclareWar")),
                "createdAt": item.get("createdAt")
            })
        return active[-3:]

    def _active_small_conflicts(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for conflict in tribe.get("small_conflicts", []) or []:
            if not isinstance(conflict, dict) or conflict.get("status") != "active":
                continue
            active_until = conflict.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) < now:
                        conflict["status"] = "expired"
                        continue
                except (TypeError, ValueError):
                    pass
            active.append(conflict)
        if len(active) != len(tribe.get("small_conflicts", []) or []):
            tribe["small_conflicts"] = active[-TRIBE_SKIRMISH_LIMIT:]
        return active[-TRIBE_SKIRMISH_LIMIT:]

    def _public_small_conflicts(self, tribe: dict) -> list:
        tribe_id = tribe.get("id")
        result = []
        for conflict in self._active_small_conflicts(tribe):
            scores = dict(conflict.get("scores") or {})
            result.append({
                "id": conflict.get("id"),
                "kind": conflict.get("kind", "resource_site"),
                "title": conflict.get("title", "小规模冲突"),
                "summary": conflict.get("summary", ""),
                "siteLabel": conflict.get("siteLabel"),
                "otherTribeId": conflict.get("otherTribeId"),
                "otherTribeName": conflict.get("otherTribeName", "其他部落"),
                "ownScore": int(scores.get(tribe_id, 0) or 0),
                "otherScore": int(scores.get(conflict.get("otherTribeId"), 0) or 0),
                "scoreTarget": int(conflict.get("scoreTarget", TRIBE_SKIRMISH_SCORE_TARGET) or TRIBE_SKIRMISH_SCORE_TARGET),
                "warGoalKind": conflict.get("warGoalKind"),
                "echoLabel": conflict.get("echoLabel"),
                "echoContributionBonus": int(conflict.get("echoContributionBonus", 0) or 0),
                "participants": list(conflict.get("participants", {}).values())[-8:],
                "activeUntil": conflict.get("activeUntil"),
                "createdAt": conflict.get("createdAt")
            })
        return result

    def _find_small_conflict_pair(self, conflict_id: str):
        for tribe in self.tribes.values():
            for conflict in tribe.get("small_conflicts", []) or []:
                if isinstance(conflict, dict) and conflict.get("id") == conflict_id:
                    other_tribe = self.tribes.get(conflict.get("otherTribeId"))
                    other_conflict = None
                    if other_tribe:
                        other_conflict = next((
                            item for item in other_tribe.get("small_conflicts", []) or []
                            if isinstance(item, dict) and item.get("id") == conflict_id
                        ), None)
                    return tribe, conflict, other_tribe, other_conflict
        return None, None, None, None

    async def _start_small_conflict_resource_legacy(self, player_id: str, outcome_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        outcome = next((
            item for item in tribe.get("boundary_outcomes", []) or []
            if isinstance(item, dict)
            and item.get("id") == outcome_id
            and item.get("kind") == "resource_site_contest"
            and item.get("status") == "pending"
        ), None)
        if not outcome:
            await self._send_tribe_error(player_id, "只能围绕待处理的资源点争执发起小规模冲突")
            return
        other_tribe_id = outcome.get("otherTribeId")
        other_tribe = self.tribes.get(other_tribe_id)
        if not other_tribe:
            await self._send_tribe_error(player_id, "对方部落已经不在这片边界")
            return
        own_site = self._small_conflict_scout_site(tribe, outcome.get("siteId"))
        other_site = self._small_conflict_scout_site(other_tribe, outcome.get("otherSiteId") or outcome.get("contestSiteId"))
        if not own_site:
            await self._send_tribe_error(player_id, "这处争夺资源点已经失效，无法继续集结")
            return

        duplicate = self._small_conflict_duplicate(tribe, other_tribe, outcome)
        if duplicate:
            await self._send_tribe_error(player_id, "这场资源点争执已经进入集结")
            return

        now_text = datetime.now().isoformat()
        active_until = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_SKIRMISH_ACTIVE_MINUTES * 60).isoformat()
        conflict_id = f"skirmish_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}"
        base = {
            "id": conflict_id,
            "kind": "resource_site",
            "status": "active",
            "outcomeId": outcome_id,
            "siteId": outcome.get("siteId"),
            "otherSiteId": outcome.get("otherSiteId") or outcome.get("contestSiteId"),
            "x": float(own_site.get("x", 0) or 0),
            "z": float(own_site.get("z", 0) or 0),
            "siteLabel": outcome.get("siteLabel") or outcome.get("title", "资源点"),
            "title": "资源点集结争夺",
            "summary": f"围绕 {outcome.get('siteLabel', '资源点')} 的短时争夺已经开始，成员可报名参战。",
            "scoreTarget": TRIBE_SKIRMISH_SCORE_TARGET,
            "scores": {tribe_id: 0, other_tribe_id: 0},
            "participants": {},
            "createdBy": player_id,
            "createdAt": now_text,
            "activeUntil": active_until
        }
        own_record = {**base, "tribeId": tribe_id, "otherTribeId": other_tribe_id, "otherTribeName": other_tribe.get("name", "其他部落")}
        other_record = {**base, "tribeId": other_tribe_id, "otherTribeId": tribe_id, "otherTribeName": tribe.get("name", "其他部落")}
        own_record.update({
            "targetSiteId": outcome.get("siteId")
        })
        other_record.update({
            "targetSiteId": outcome.get("otherSiteId") or outcome.get("contestSiteId"),
            "siteId": outcome.get("otherSiteId") or outcome.get("contestSiteId"),
            "otherSiteId": outcome.get("siteId"),
            "x": float((other_site or own_site).get("x", own_site.get("x", 0)) or 0),
            "z": float((other_site or own_site).get("z", own_site.get("z", 0)) or 0)
        })
        tribe.setdefault("small_conflicts", []).append(own_record)
        tribe["small_conflicts"] = tribe["small_conflicts"][-TRIBE_SKIRMISH_LIMIT:]
        other_tribe.setdefault("small_conflicts", []).append(other_record)
        other_tribe["small_conflicts"] = other_tribe["small_conflicts"][-TRIBE_SKIRMISH_LIMIT:]

        member = tribe.get("members", {}).get(player_id, {})
        detail = f"{member.get('name', '成员')} 将 {outcome.get('siteLabel', '资源点争执')} 升级为小规模集结，双方成员可以报名参战。"
        self._add_tribe_history(tribe, "governance", "发起小规模冲突", detail, player_id, {"kind": "small_conflict", "conflictId": conflict_id})
        await self._notify_tribe(tribe_id, detail)
        await self._notify_tribe(other_tribe_id, f"{tribe.get('name', '其他部落')} 在边界资源点发起小规模集结，你们可以报名回应。")
        await self.broadcast_tribe_state(tribe_id)
        await self.broadcast_tribe_state(other_tribe_id)

    async def start_small_conflict(self, player_id: str, outcome_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        outcome = next((
            item for item in tribe.get("boundary_outcomes", []) or []
            if isinstance(item, dict)
            and item.get("id") == outcome_id
            and item.get("status") == "pending"
        ), None)
        if not outcome:
            await self._send_tribe_error(player_id, "只能围绕待处理的边境争端发起小规模冲突")
            return
        if outcome.get("kind") != "resource_site_contest" and outcome.get("state") != "hostile":
            await self._send_tribe_error(player_id, "只有资源点争执或敌意边境可以升级为小规模冲突")
            return
        other_tribe_id = outcome.get("otherTribeId")
        other_tribe = self.tribes.get(other_tribe_id)
        if not other_tribe:
            await self._send_tribe_error(player_id, "对方部落已经不在这片边境")
            return

        if outcome.get("kind") == "resource_site_contest":
            own_target = self._small_conflict_scout_site(tribe, outcome.get("siteId"))
            other_target = self._small_conflict_scout_site(other_tribe, outcome.get("otherSiteId") or outcome.get("contestSiteId"))
            if not own_target:
                await self._send_tribe_error(player_id, "这处争夺资源点已经失效，无法继续集结")
                return
            target_kind = "resource_site"
            title = "资源点集结争夺"
            site_label = outcome.get("siteLabel") or outcome.get("title", "资源点")
            summary = f"围绕 {site_label} 的短时争夺已经开始，成员可报名参战。"
            own_target_id = outcome.get("siteId")
            other_target_id = outcome.get("otherSiteId") or outcome.get("contestSiteId")
        elif outcome.get("kind") == "war_goal_echo":
            echo_target_kind = outcome.get("targetKind") or "boundary_flag"
            if echo_target_kind == "cave_entrance":
                own_target = self._small_conflict_cave_target(tribe, other_tribe, outcome)
                other_target = self._small_conflict_cave_target(other_tribe, tribe, outcome) if own_target else None
            else:
                own_target = self._small_conflict_boundary_target(tribe, other_tribe, outcome)
                other_target = self._small_conflict_boundary_target(other_tribe, tribe, outcome)
            if not own_target:
                await self._send_tribe_error(player_id, "需要靠近可争夺的边境目标，才能引燃战争余震")
                return
            target_kind = echo_target_kind
            title = outcome.get("echoLabel") or outcome.get("title") or "战争余波集结"
            site_label = own_target.get("label") or outcome.get("title", "战争余波")
            summary = outcome.get("summary") or f"{site_label} 的战后余波升级为短时集结。"
            own_target_id = own_target.get("id")
            other_target_id = (other_target or own_target).get("id")
            outcome["targetId"] = own_target_id
        else:
            own_target = self._small_conflict_boundary_target(tribe, other_tribe, outcome)
            other_target = self._small_conflict_boundary_target(other_tribe, tribe, outcome)
            if not own_target:
                await self._send_tribe_error(player_id, "需要先在这条敌意边境插下旗帜，才能发起集结")
                return
            target_kind = own_target.get("kind", "boundary_flag")
            title = "道路集结争夺" if target_kind == "boundary_road" else "旗帜集结争夺"
            site_label = own_target.get("label") or outcome.get("title", "边境")
            summary = f"{site_label} 的边境争执升级为短时集结，双方成员需要靠近己方目标参战。"
            own_target_id = own_target.get("id")
            other_target_id = (other_target or {}).get("id")
            outcome["targetId"] = own_target_id

        duplicate = self._small_conflict_duplicate(tribe, other_tribe, outcome)
        if duplicate:
            await self._send_tribe_error(player_id, "这场边境争端已经进入集结")
            return

        now_text = datetime.now().isoformat()
        active_until = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_SKIRMISH_ACTIVE_MINUTES * 60).isoformat()
        conflict_id = f"skirmish_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}"
        base = {
            "id": conflict_id,
            "kind": target_kind,
            "targetKind": target_kind,
            "status": "active",
            "outcomeId": outcome_id,
            "siteId": own_target_id,
            "otherSiteId": other_target_id,
            "x": float(own_target.get("x", 0) or 0),
            "z": float(own_target.get("z", 0) or 0),
            "siteLabel": site_label,
            "title": title,
            "summary": summary,
            "scoreTarget": max(3, TRIBE_SKIRMISH_SCORE_TARGET - 1) if outcome.get("kind") == "war_goal_echo" else TRIBE_SKIRMISH_SCORE_TARGET,
            "warGoalKind": outcome.get("warGoalKind"),
            "echoLabel": outcome.get("echoLabel"),
            "echoContributionBonus": int(outcome.get("echoContributionBonus", 0) or 0),
            "scores": {tribe_id: 0, other_tribe_id: 0},
            "participants": {},
            "createdBy": player_id,
            "createdAt": now_text,
            "activeUntil": active_until
        }
        own_record = {
            **base,
            "tribeId": tribe_id,
            "targetSiteId": own_target_id if target_kind == "resource_site" else None,
            "targetFlagId": own_target.get("flagId") if target_kind == "boundary_flag" else None,
            "targetRoadId": own_target_id if target_kind == "boundary_road" else None,
            "otherTribeId": other_tribe_id,
            "otherTribeName": other_tribe.get("name", "其他部落")
        }
        other_record = {
            **base,
            "tribeId": other_tribe_id,
            "targetSiteId": other_target_id if target_kind == "resource_site" else None,
            "targetFlagId": (other_target or {}).get("flagId") if target_kind == "boundary_flag" else None,
            "targetRoadId": other_target_id if target_kind == "boundary_road" else None,
            "siteId": other_target_id,
            "otherSiteId": own_target_id,
            "x": float((other_target or own_target).get("x", own_target.get("x", 0)) or 0),
            "z": float((other_target or own_target).get("z", own_target.get("z", 0)) or 0),
            "otherTribeId": tribe_id,
            "otherTribeName": tribe.get("name", "其他部落")
        }
        tribe.setdefault("small_conflicts", []).append(own_record)
        tribe["small_conflicts"] = tribe["small_conflicts"][-TRIBE_SKIRMISH_LIMIT:]
        other_tribe.setdefault("small_conflicts", []).append(other_record)
        other_tribe["small_conflicts"] = other_tribe["small_conflicts"][-TRIBE_SKIRMISH_LIMIT:]

        member = tribe.get("members", {}).get(player_id, {})
        detail = f"{member.get('name', '成员')} 将 {site_label} 升级为小规模集结，双方成员可以报名参战。"
        self._add_tribe_history(tribe, "governance", "发起小规模冲突", detail, player_id, {"kind": "small_conflict", "conflictId": conflict_id, "targetKind": target_kind})
        await self._notify_tribe(tribe_id, detail)
        await self._notify_tribe(other_tribe_id, f"{tribe.get('name', '其他部落')} 在边境发起小规模集结，你们可以报名回应。")
        await self.broadcast_tribe_state(tribe_id)
        await self.broadcast_tribe_state(other_tribe_id)

    async def join_small_conflict(self, player_id: str, conflict_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        own_tribe, conflict, other_tribe, other_conflict = self._find_small_conflict_pair(conflict_id)
        if not conflict or conflict.get("status") != "active":
            await self._send_tribe_error(player_id, "这场小规模冲突已经结束")
            return
        if tribe_id not in {conflict.get("tribeId"), conflict.get("otherTribeId")}:
            await self._send_tribe_error(player_id, "只有冲突双方成员可以参战")
            return

        local_conflict = self._small_conflict_record_for_tribe(conflict_id, tribe_id) or conflict
        target_site = self._small_conflict_target_site(tribe, local_conflict)
        player = self.players.get(player_id, {})
        target_x = float((target_site or local_conflict).get("x", 0) or 0)
        target_z = float((target_site or local_conflict).get("z", 0) or 0)
        dx = float(player.get("x", 0) or 0) - target_x
        dz = float(player.get("z", 0) or 0) - target_z
        if dx * dx + dz * dz > TRIBE_SKIRMISH_JOIN_DISTANCE * TRIBE_SKIRMISH_JOIN_DISTANCE:
            await self._send_tribe_error(player_id, "靠近争夺资源点后才能加入这场集结")
            return

        participants = conflict.setdefault("participants", {})
        if player_id in participants:
            await self._send_tribe_error(player_id, "你已经加入这场冲突")
            return
        member = tribe.get("members", {}).get(player_id, {})
        fatigue = self._active_player_fatigue(player)
        echo_bonus = int(local_conflict.get("echoContributionBonus", 0) or 0)
        inspiration = self._active_personal_inspiration(player)
        inspiration_bonus = int(inspiration.get("contributionBonus", 0) or 0) if inspiration else 0
        title_bonus = self._personal_title_bonus(player, "skirmishContributionBonus")
        contribution = max(1, 3 - fatigue) + min(2, int(player.get("personal_renown", 0) or 0) // 3) + echo_bonus + inspiration_bonus + title_bonus
        participant = {
            "playerId": player_id,
            "playerName": member.get("name") or player.get("name", "成员"),
            "tribeId": tribe_id,
            "contribution": contribution,
            "inspirationBonus": inspiration_bonus,
            "inspirationSourceName": inspiration.get("sourceName") if inspiration else "",
            "renownTitleBonus": title_bonus,
            "renownTitle": self._personal_renown_title(int(player.get("personal_renown", 0) or 0)).get("title"),
            "joinedAt": datetime.now().isoformat()
        }
        if inspiration_bonus:
            player.pop("personal_inspiration", None)
        for item in (conflict, other_conflict):
            if item:
                item.setdefault("participants", {})[player_id] = participant
                scores = item.setdefault("scores", {})
                scores[tribe_id] = int(scores.get(tribe_id, 0) or 0) + contribution

        bonus_text = f"（战争余震+{echo_bonus}）" if echo_bonus else ""
        inspire_text = f"（{participant['inspirationSourceName']}鼓舞+{inspiration_bonus}）" if inspiration_bonus else ""
        title_text = f"（{participant['renownTitle']}+{title_bonus}）" if title_bonus else ""
        await self._notify_tribe(tribe_id, f"{participant['playerName']} 加入了 {conflict.get('title', '小规模冲突')}，贡献 +{contribution}{bonus_text}{inspire_text}{title_text}。")
        if inspiration_bonus:
            await self.send_personal_conflict_status(player_id)
        score_target = int(conflict.get("scoreTarget", TRIBE_SKIRMISH_SCORE_TARGET) or TRIBE_SKIRMISH_SCORE_TARGET)
        if int(conflict.get("scores", {}).get(tribe_id, 0) or 0) >= score_target:
            await self.resolve_small_conflict(player_id, conflict_id)
            return
        await self.broadcast_tribe_state(conflict.get("tribeId"))
        await self.broadcast_tribe_state(conflict.get("otherTribeId"))

    async def resolve_small_conflict(self, player_id: str, conflict_id: str):
        tribe, conflict, other_tribe, other_conflict = self._find_small_conflict_pair(conflict_id)
        if not conflict or conflict.get("status") != "active":
            await self._send_tribe_error(player_id, "这场小规模冲突已经结束")
            return
        scores = dict(conflict.get("scores") or {})
        tribe_id = conflict.get("tribeId")
        other_tribe_id = conflict.get("otherTribeId")
        own_score = int(scores.get(tribe_id, 0) or 0)
        other_score = int(scores.get(other_tribe_id, 0) or 0)
        winner_id = tribe_id if own_score >= other_score else other_tribe_id
        loser_id = other_tribe_id if winner_id == tribe_id else tribe_id
        winner = self.tribes.get(winner_id)
        loser = self.tribes.get(loser_id)
        side_records = {
            item.get("tribeId"): item
            for item in (conflict, other_conflict)
            if isinstance(item, dict) and item.get("tribeId")
        }
        now_text = datetime.now().isoformat()
        for item in (conflict, other_conflict):
            if item:
                item["status"] = "resolved"
                item["winnerTribeId"] = winner_id
                item["resolvedAt"] = now_text
        if winner and winner_record.get("targetKind") in {"boundary_flag", "boundary_road"}:
            site_result_parts.extend(self._apply_small_conflict_boundary_result(winner, loser, winner_record))
        elif winner:
            winner["renown"] = int(winner.get("renown", 0) or 0) + TRIBE_SKIRMISH_RENOWN_REWARD
            winner["food"] = int(winner.get("food", 0) or 0) + TRIBE_SKIRMISH_FOOD_REWARD
        if loser and winner_record.get("targetKind") not in {"boundary_flag", "boundary_road"}:
            progress = loser.setdefault("boundary_relations", {}).setdefault(winner_id, {})
            progress["score"] = max(-9, int(progress.get("score", 0) or 0) - 1)
            progress["lastAction"] = "small_conflict_lost"
            progress["lastActionAt"] = now_text
        if winner:
            progress = winner.setdefault("boundary_relations", {}).setdefault(loser_id, {})
            progress["score"] = max(-9, int(progress.get("score", 0) or 0) - 1)
            progress["lastAction"] = "small_conflict_won"
            progress["lastActionAt"] = now_text
        detail = f"{winner.get('name', '部落') if winner else '一方'} 在 {conflict.get('siteLabel', '资源点')} 的小规模冲突中占上风，获得声望和补给。"
        site_result_parts = []
        winner_record = side_records.get(winner_id) or conflict
        loser_record = side_records.get(loser_id) or other_conflict or conflict
        if winner:
            promoted = self._promote_small_conflict_winner_site(
                winner,
                winner_record.get("targetSiteId") or winner_record.get("siteId"),
                player_id,
                now_text
            )
            site_result_parts.append("胜方获得短期控制点" if promoted else "胜方控制时间延长")
        if loser:
            ceded = self._cede_small_conflict_loser_site(
                loser,
                loser_record.get("targetSiteId") or loser_record.get("siteId")
            )
            if ceded:
                site_result_parts.append("败方让渡相关资源点")
        site_ids = {
            conflict.get("siteId"),
            conflict.get("otherSiteId"),
            conflict.get("targetSiteId"),
            conflict.get("targetFlagId"),
            conflict.get("targetRoadId"),
            (other_conflict or {}).get("siteId"),
            (other_conflict or {}).get("otherSiteId"),
            (other_conflict or {}).get("targetSiteId"),
            (other_conflict or {}).get("targetFlagId"),
            (other_conflict or {}).get("targetRoadId")
        }
        site_ids = {item for item in site_ids if item}
        if winner:
            self._mark_small_conflict_outcomes(winner, loser_id, site_ids, now_text)
        if loser:
            self._mark_small_conflict_outcomes(loser, winner_id, site_ids, now_text)
        if site_result_parts:
            detail += " " + "，".join(site_result_parts) + "。"

        for target_id in {tribe_id, other_tribe_id}:
            target = self.tribes.get(target_id)
            if target:
                self._add_tribe_history(target, "governance", "小规模冲突结算", detail, player_id, {"kind": "small_conflict", "conflictId": conflict_id, "winnerTribeId": winner_id})
                await self._notify_tribe(target_id, detail)
                await self.broadcast_tribe_state(target_id)
        await self._broadcast_current_map()

    def _active_formal_wars(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("formal_wars", []) or [])
            if isinstance(item, dict) and item.get("status") == "active"
        ][-3:]

    def _formal_war_stage(self, own_score: int, other_score: int, target: int) -> dict:
        lead = own_score - other_score
        high_score = max(own_score, other_score)
        if target and high_score >= max(1, target - 1):
            label = "压制"
            summary = "战线接近决胜，参战或谈判都会立刻改变结局。"
        elif abs(lead) >= 3:
            label = "突破" if lead > 0 else "受压"
            summary = "一方已经打出明显优势，另一方需要补人或寻求停战。"
        elif high_score >= max(2, target // 2):
            label = "拉锯"
            summary = "双方都投入了力量，战线还没有完全倒向一边。"
        else:
            label = "集结"
            summary = "战争刚进入正式动员，成员参战会快速改变战线。"
        return {"label": label, "summary": summary, "lead": lead}

    def _public_formal_wars(self, tribe: dict) -> list:
        tribe_id = tribe.get("id")
        result = []
        for war in self._active_formal_wars(tribe):
            scores = dict(war.get("scores") or {})
            own_score = int(scores.get(tribe_id, 0) or 0)
            other_score = int(scores.get(war.get("otherTribeId"), 0) or 0)
            score_target = int(war.get("scoreTarget", TRIBE_WAR_SCORE_TARGET) or TRIBE_WAR_SCORE_TARGET)
            stage = self._formal_war_stage(own_score, other_score, score_target)
            result.append({
                "id": war.get("id"),
                "title": war.get("title", "正式部落战争"),
                "summary": war.get("summary", ""),
                "otherTribeId": war.get("otherTribeId"),
                "otherTribeName": war.get("otherTribeName", "其他部落"),
                "ownScore": own_score,
                "otherScore": other_score,
                "scoreTarget": score_target,
                "targetLabel": war.get("targetLabel", "边境战线"),
                "goal": war.get("goal") or TRIBE_WAR_GOALS.get("border_front", {}),
                "stage": stage,
                "truceFoodCost": TRIBE_WAR_TRUCE_FOOD_COST,
                "participants": list((war.get("participants") or {}).values())[-10:],
                "declaredAt": war.get("declaredAt")
            })
        return result

    def _formal_war_goal_from_progress(self, progress: dict) -> dict:
        target_kind = progress.get("lastWarTargetKind") or "border_front"
        goal = dict(TRIBE_WAR_GOALS.get(target_kind) or TRIBE_WAR_GOALS.get("border_front", {}))
        goal["kind"] = target_kind if target_kind in TRIBE_WAR_GOALS else "border_front"
        return goal

    def _war_goal_skirmish_echo_profile(self, war: dict) -> dict:
        goal = war.get("goal") if isinstance(war.get("goal"), dict) else {}
        kind = goal.get("kind") or "border_front"
        profiles = {
            "resource_site": {
                "title": "粮草余震",
                "targetKind": "resource_site",
                "label": "粮草余波集结",
                "summary": "上一场粮草战争留下了补给线争执，新的小规模冲突更容易围绕粮草和搬运展开。",
                "bonus": 1
            },
            "boundary_flag": {
                "title": "边旗余震",
                "targetKind": "boundary_flag",
                "label": "边旗余波集结",
                "summary": "上一场边旗战争让旗帜附近仍有敌意标记，新的小规模冲突更容易围绕边旗声望展开。",
                "bonus": 1
            },
            "boundary_road": {
                "title": "通路余震",
                "targetKind": "boundary_road",
                "label": "通路余波集结",
                "summary": "上一场通路战争让道路通行权继续摇摆，新的小规模冲突更容易围绕贸易通路展开。",
                "bonus": 1
            },
            "cave_entrance": {
                "title": "洞口余震",
                "targetKind": "cave_entrance",
                "label": "洞口余波集结",
                "summary": "上一场洞口战争让远征权仍有争议，新的小规模冲突更容易围绕洞口巡守展开。",
                "bonus": 1
            },
            "border_front": {
                "title": "战线余震",
                "targetKind": "boundary_flag",
                "label": "边境余波集结",
                "summary": "上一场边境战争没有完全熄灭，新的小规模冲突更容易沿旧战线复燃。",
                "bonus": 1
            }
        }
        profile = dict(profiles.get(kind) or profiles["border_front"])
        profile["warGoalKind"] = kind
        profile["goalLabel"] = goal.get("label") or TRIBE_WAR_GOALS.get(kind, {}).get("label", "战争目标")
        return profile

    def _create_war_goal_echo_outcomes(self, tribe_id: str, other_tribe_id: str, war: dict, now_text: str):
        profile = self._war_goal_skirmish_echo_profile(war)
        for source_id, target_id in ((tribe_id, other_tribe_id), (other_tribe_id, tribe_id)):
            source = self.tribes.get(source_id)
            target = self.tribes.get(target_id)
            if not source:
                continue
            outcome = {
                "id": f"war_echo_{war.get('id')}_{source_id}",
                "status": "pending",
                "kind": "war_goal_echo",
                "state": "hostile",
                "otherTribeId": target_id,
                "otherTribeName": target.get("name", "其他部落") if target else "其他部落",
                "title": profile.get("title", "战争余震"),
                "summary": profile.get("summary", "上一场正式战争留下了新的边境争执，可升级为小规模集结。"),
                "targetKind": profile.get("targetKind", "boundary_flag"),
                "warGoalKind": profile.get("warGoalKind"),
                "goalLabel": profile.get("goalLabel"),
                "echoLabel": profile.get("label"),
                "echoContributionBonus": int(profile.get("bonus", 0) or 0),
                "warId": war.get("id"),
                "createdAt": now_text
            }
            outcomes = [
                item for item in (source.get("boundary_outcomes", []) or [])
                if not (isinstance(item, dict) and item.get("id") == outcome["id"])
            ]
            outcomes.append(outcome)
            source["boundary_outcomes"] = outcomes[-TRIBE_BOUNDARY_OUTCOME_LIMIT:]

    def _apply_formal_war_goal_reward(self, winner: dict, goal: dict) -> list:
        if not winner or not goal:
            return []
        parts = []
        renown_reward = int(goal.get("renownReward", 0) or 0)
        food_reward = int(goal.get("foodReward", 0) or 0)
        trade_reward = int(goal.get("tradeReward", 0) or 0)
        discovery_reward = int(goal.get("discoveryReward", 0) or 0)
        if renown_reward:
            winner["renown"] = int(winner.get("renown", 0) or 0) + renown_reward
            parts.append(f"{goal.get('label', '战争目标')}声望+{renown_reward}")
        if food_reward:
            winner["food"] = int(winner.get("food", 0) or 0) + food_reward
            parts.append(f"粮草+{food_reward}")
        if trade_reward:
            winner["trade_reputation"] = int(winner.get("trade_reputation", 0) or 0) + trade_reward
            parts.append(f"贸易信誉+{trade_reward}")
        if discovery_reward:
            winner["discovery_progress"] = int(winner.get("discovery_progress", 0) or 0) + discovery_reward
            parts.append(f"发现进度+{discovery_reward}")
        return parts

    def _public_war_repair_tasks(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("war_repair_tasks", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-3:]

    def _public_war_revival_tasks(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("war_revival_tasks", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-3:]

    def _public_war_diplomacy_tasks(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("war_diplomacy_tasks", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-3:]

    def _public_war_aftermath_tasks(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("war_aftermath_tasks", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-3:]

    def _public_war_ally_records(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("war_ally_records", []) or [])
            if isinstance(item, dict)
        ][-5:]

    def _public_war_ally_tasks(self, tribe: dict) -> list:
        return [
            item for item in (tribe.get("war_ally_tasks", []) or [])
            if isinstance(item, dict) and item.get("status") == "pending"
        ][-4:]

    def _public_war_intervention_targets(self, tribe: dict) -> list:
        tribe_id = tribe.get("id")
        seen = set()
        result = []
        for source in self.tribes.values():
            for war in source.get("formal_wars", []) or []:
                if not isinstance(war, dict) or war.get("status") != "active":
                    continue
                war_id = war.get("id")
                if not war_id or war_id in seen:
                    continue
                side_a = war.get("tribeId")
                side_b = war.get("otherTribeId")
                if tribe_id in {side_a, side_b}:
                    continue
                side_a_tribe = self.tribes.get(side_a)
                side_b_tribe = self.tribes.get(side_b)
                scores = dict(war.get("scores") or {})
                seen.add(war_id)
                result.append({
                    "id": war_id,
                    "title": war.get("title", "正式部落战争"),
                    "targetLabel": war.get("targetLabel", "边境战线"),
                    "goal": war.get("goal") or TRIBE_WAR_GOALS.get("border_front", {}),
                    "supportFoodCost": TRIBE_WAR_SUPPORT_FOOD_COST,
                    "supportScore": TRIBE_WAR_SUPPORT_SCORE,
                    "mediationFoodCost": TRIBE_WAR_MEDIATION_FOOD_COST,
                    "sides": [
                        {
                            "tribeId": side_a,
                            "name": side_a_tribe.get("name", "一方") if side_a_tribe else "一方",
                            "score": int(scores.get(side_a, 0) or 0)
                        },
                        {
                            "tribeId": side_b,
                            "name": side_b_tribe.get("name", "一方") if side_b_tribe else "一方",
                            "score": int(scores.get(side_b, 0) or 0)
                        }
                    ],
                    "scoreTarget": int(war.get("scoreTarget", TRIBE_WAR_SCORE_TARGET) or TRIBE_WAR_SCORE_TARGET),
                    "declaredAt": war.get("declaredAt")
                })
        return result[-3:]

    def _find_formal_war_pair(self, war_id: str):
        for tribe in self.tribes.values():
            for war in tribe.get("formal_wars", []) or []:
                if isinstance(war, dict) and war.get("id") == war_id:
                    other_tribe = self.tribes.get(war.get("otherTribeId"))
                    other_war = None
                    if other_tribe:
                        other_war = next((
                            item for item in other_tribe.get("formal_wars", []) or []
                            if isinstance(item, dict) and item.get("id") == war_id
                        ), None)
                    return tribe, war, other_tribe, other_war
        return None, None, None, None

    async def declare_formal_war(self, player_id: str, other_tribe_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        other_tribe = self.tribes.get(other_tribe_id)
        if not tribe or not other_tribe:
            await self._send_tribe_error(player_id, "需要两个有效部落才能宣战")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以宣战")
            return
        progress = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        if int(progress.get("warPressure", 0) or 0) < TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD:
            await self._send_tribe_error(player_id, "战争压力还不够，无法正式宣战")
            return
        duplicate = next((
            item for item in self._active_formal_wars(tribe)
            if item.get("otherTribeId") == other_tribe_id
        ), None)
        if duplicate:
            await self._send_tribe_error(player_id, "这条战线已经处于正式战争")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        if (
            int(storage.get("wood", 0) or 0) < TRIBE_WAR_WOOD_COST
            or int(storage.get("stone", 0) or 0) < TRIBE_WAR_STONE_COST
            or int(tribe.get("food", 0) or 0) < TRIBE_WAR_FOOD_COST
        ):
            await self._send_tribe_error(player_id, "宣战需要公共仓库木材、石块和食物作为战备")
            return
        storage["wood"] = int(storage.get("wood", 0) or 0) - TRIBE_WAR_WOOD_COST
        storage["stone"] = int(storage.get("stone", 0) or 0) - TRIBE_WAR_STONE_COST
        tribe["food"] = int(tribe.get("food", 0) or 0) - TRIBE_WAR_FOOD_COST

        now_text = datetime.now().isoformat()
        war_id = f"war_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}"
        target_label = progress.get("lastWarTargetLabel") or "边境战线"
        goal = self._formal_war_goal_from_progress(progress)
        base = {
            "id": war_id,
            "status": "active",
            "title": "正式部落战争",
            "summary": f"围绕{target_label}的长期敌意升级为正式部落战争。目标：{goal.get('label', '边境战线')}。",
            "targetLabel": target_label,
            "goal": goal,
            "scoreTarget": TRIBE_WAR_SCORE_TARGET,
            "scores": {tribe_id: 0, other_tribe_id: 0},
            "participants": {},
            "declaredBy": player_id,
            "declaredAt": now_text
        }
        own_record = {**base, "tribeId": tribe_id, "otherTribeId": other_tribe_id, "otherTribeName": other_tribe.get("name", "其他部落")}
        other_record = {**base, "tribeId": other_tribe_id, "otherTribeId": tribe_id, "otherTribeName": tribe.get("name", "其他部落")}
        tribe.setdefault("formal_wars", []).append(own_record)
        tribe["formal_wars"] = tribe["formal_wars"][-3:]
        other_tribe.setdefault("formal_wars", []).append(other_record)
        other_tribe["formal_wars"] = other_tribe["formal_wars"][-3:]
        for source, target_id in ((tribe, other_tribe_id), (other_tribe, tribe_id)):
            relation = source.setdefault("boundary_relations", {}).setdefault(target_id, {})
            relation["warPressure"] = 0
            relation["canDeclareWar"] = False
            relation["lastAction"] = "formal_war_declared"
            relation["lastActionAt"] = now_text
        detail = f"{member.get('name', '成员')} 代表 {tribe.get('name', '部落')} 向 {other_tribe.get('name', '其他部落')} 宣告正式部落战争，目标为{goal.get('label', '边境战线')}，消耗战备木材{TRIBE_WAR_WOOD_COST}、石块{TRIBE_WAR_STONE_COST}、食物{TRIBE_WAR_FOOD_COST}。"
        self._add_tribe_history(tribe, "governance", "正式宣战", detail, player_id, {"kind": "formal_war", "warId": war_id, "otherTribeId": other_tribe_id})
        self._add_tribe_history(other_tribe, "governance", "遭遇宣战", detail, player_id, {"kind": "formal_war", "warId": war_id, "otherTribeId": tribe_id})
        await self._notify_tribe(tribe_id, detail)
        await self._notify_tribe(other_tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.broadcast_tribe_state(other_tribe_id)

    async def join_formal_war(self, player_id: str, war_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        own_tribe, war, other_tribe, other_war = self._find_formal_war_pair(war_id)
        if not war or war.get("status") != "active":
            await self._send_tribe_error(player_id, "这场部落战争已经结束")
            return
        if tribe_id not in {war.get("tribeId"), war.get("otherTribeId")}:
            await self._send_tribe_error(player_id, "只有战争双方成员可以参战")
            return
        participants = war.setdefault("participants", {})
        if player_id in participants:
            await self._send_tribe_error(player_id, "你已经加入这场战争")
            return
        player = self.players.get(player_id, {})
        member = tribe.get("members", {}).get(player_id, {})
        fatigue = self._active_player_fatigue(player)
        contribution = max(1, 2 - min(1, fatigue)) + min(3, int(player.get("personal_renown", 0) or 0) // 3)
        if member.get("role") in ("leader", "elder"):
            contribution += 1
        goal = war.get("goal") or {}
        if goal.get("kind") == "boundary_road" and member.get("role") in ("leader", "elder"):
            contribution += 1
        elif goal.get("kind") == "cave_entrance" and int(player.get("personal_renown", 0) or 0) >= 3:
            contribution += 1
        elif goal.get("kind") == "resource_site" and int(tribe.get("food", 0) or 0) > 0:
            contribution += 1
        participant = {
            "playerId": player_id,
            "playerName": member.get("name") or player.get("name", "成员"),
            "tribeId": tribe_id,
            "contribution": contribution,
            "goalLabel": goal.get("label"),
            "joinedAt": datetime.now().isoformat()
        }
        for item in (war, other_war):
            if item:
                item.setdefault("participants", {})[player_id] = participant
                scores = item.setdefault("scores", {})
                scores[tribe_id] = int(scores.get(tribe_id, 0) or 0) + contribution
        await self._notify_tribe(tribe_id, f"{participant['playerName']} 加入正式部落战争，战线推进 +{contribution}。")
        if int(war.get("scores", {}).get(tribe_id, 0) or 0) >= int(war.get("scoreTarget", TRIBE_WAR_SCORE_TARGET) or TRIBE_WAR_SCORE_TARGET):
            await self.resolve_formal_war(player_id, war_id)
            return
        await self.broadcast_tribe_state(war.get("tribeId"))
        await self.broadcast_tribe_state(war.get("otherTribeId"))

    def _war_goal_followup_profile(self, source: dict) -> dict:
        goal = source.get("goal") if isinstance(source.get("goal"), dict) else {}
        kind = goal.get("kind") or source.get("warGoalKind") or "border_front"
        profiles = {
            "resource_site": {
                "label": "粮草战后",
                "repairWoodDelta": -1,
                "repairRenownDelta": 1,
                "granaryFoodBonus": 4,
                "marketFoodBonus": 3,
                "summary": "粮草目标让战后任务更偏向补粮与后勤。"
            },
            "boundary_flag": {
                "label": "边旗战后",
                "repairRenownDelta": 2,
                "oathRenownBonus": 2,
                "watchPressureRelief": 1,
                "summary": "边旗目标让战后任务更偏向声望与守边。"
            },
            "boundary_road": {
                "label": "通路战后",
                "repairStoneDelta": 1,
                "repairRenownDelta": 1,
                "granaryTradeBonus": 1,
                "marketTradeBonus": 1,
                "summary": "通路目标让战后任务更偏向道路修复与贸易。"
            },
            "cave_entrance": {
                "label": "洞口战后",
                "repairStoneDelta": 2,
                "repairRenownDelta": 1,
                "oathRenownBonus": 1,
                "revivalDiscoveryBonus": 2,
                "aftermathDiscoveryBonus": 1,
                "summary": "洞口目标让战后任务更偏向远征权和发现进度。"
            },
            "border_front": {
                "label": "边境战后",
                "repairRenownDelta": 1,
                "watchPressureRelief": 1,
                "summary": "边境目标让战后任务更偏向稳住关系和压力。"
            }
        }
        profile = dict(profiles.get(kind) or profiles["border_front"])
        profile["kind"] = kind
        profile["goalLabel"] = goal.get("label") or profile["label"]
        return profile

    def _create_war_repair_tasks(self, tribe_id: str, other_tribe_id: str, war: dict, now_text: str):
        goal_profile = self._war_goal_followup_profile(war)
        wood_cost = max(0, TRIBE_WAR_REPAIR_WOOD_COST + int(goal_profile.get("repairWoodDelta", 0) or 0))
        stone_cost = max(0, TRIBE_WAR_REPAIR_STONE_COST + int(goal_profile.get("repairStoneDelta", 0) or 0))
        renown_reward = max(0, TRIBE_WAR_REPAIR_RENOWN + int(goal_profile.get("repairRenownDelta", 0) or 0))
        goal_profile = self._war_goal_followup_profile(war)
        for source_id, target_id in ((tribe_id, other_tribe_id), (other_tribe_id, tribe_id)):
            source = self.tribes.get(source_id)
            target = self.tribes.get(target_id)
            if not source:
                continue
            task = {
                "id": f"war_repair_{war.get('id')}_{source_id}",
                "status": "pending",
                "otherTribeId": target_id,
                "otherTribeName": target.get("name", "其他部落") if target else "其他部落",
                "title": "战后修复",
                "summary": f"修补与 {target.get('name', '其他部落') if target else '其他部落'} 冲突后受损的边境设施与通路。",
                "woodCost": wood_cost,
                "stoneCost": stone_cost,
                "renownReward": renown_reward,
                "warGoalKind": goal_profile.get("kind"),
                "goalEffectLabel": goal_profile.get("summary"),
                "warId": war.get("id"),
                "createdAt": now_text
            }
            tasks = [
                item for item in (source.get("war_repair_tasks", []) or [])
                if isinstance(item, dict) and item.get("id") != task["id"]
            ]
            tasks.append(task)
            source["war_repair_tasks"] = tasks[-5:]

    def _apply_formal_war_fatigue(self, war: dict, winner_id: str, loser_id: str, now_text: str) -> int:
        participant_ids = set((war.get("participants") or {}).keys())
        fatigue_until = datetime.fromtimestamp(
            datetime.now().timestamp() + TRIBE_WAR_FATIGUE_SECONDS
        ).isoformat()
        applied = 0
        for player_id in participant_ids:
            player = self.players.get(player_id)
            if not player:
                continue
            player_tribe_id = self.player_tribes.get(player_id)
            gain = TRIBE_WAR_FATIGUE_WINNER if player_tribe_id == winner_id else TRIBE_WAR_FATIGUE_LOSER
            player["conflict_fatigue"] = min(
                PLAYER_CONFLICT_FATIGUE_MAX,
                int(player.get("conflict_fatigue", 0) or 0) + gain
            )
            player["conflict_fatigue_until"] = fatigue_until
            applied += 1
        return applied

    def _create_war_revival_task(self, loser_id: str, winner_id: str, war: dict, now_text: str):
        loser = self.tribes.get(loser_id)
        winner = self.tribes.get(winner_id)
        if not loser:
            return
        goal_profile = self._war_goal_followup_profile(war)
        task = {
            "id": f"war_revival_{war.get('id')}_{loser_id}",
            "status": "pending",
            "otherTribeId": winner_id,
            "otherTribeName": winner.get("name", "其他部落") if winner else "其他部落",
            "title": "战败复兴",
            "summary": f"安抚族人、整理粮木，帮助部落从与 {winner.get('name', '其他部落') if winner else '其他部落'} 的败势中恢复。",
            "foodCost": TRIBE_WAR_REVIVAL_FOOD_COST,
            "woodCost": TRIBE_WAR_REVIVAL_WOOD_COST,
            "renownReward": TRIBE_WAR_REVIVAL_RENOWN,
            "fatigueRelief": TRIBE_WAR_REVIVAL_FATIGUE_RELIEF,
            "warGoalKind": goal_profile.get("kind"),
            "goalEffectLabel": goal_profile.get("summary"),
            "discoveryReward": int(goal_profile.get("revivalDiscoveryBonus", 0) or 0),
            "warId": war.get("id"),
            "createdAt": now_text
        }
        tasks = [
            item for item in (loser.get("war_revival_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") != task["id"]
        ]
        tasks.append(task)
        loser["war_revival_tasks"] = tasks[-5:]

    def _tribe_has_building_type(self, tribe: dict, building_type: str) -> bool:
        return any(
            isinstance(item, dict) and item.get("type") == building_type
            for item in (tribe.get("camp", {}).get("buildings", []) or [])
        )

    def _create_war_revival_branch_tasks(self, tribe: dict, task: dict, now_text: str):
        other_tribe_id = task.get("otherTribeId")
        other_name = task.get("otherTribeName", "其他部落")
        branch_group = f"revival_branch_{task.get('warId')}_{tribe.get('id')}"
        goal_profile = self._war_goal_followup_profile(task)
        has_storage = self._tribe_has_building_type(tribe, "tribe_storage")
        has_road = self._tribe_has_building_type(tribe, "tribe_road")
        has_fence = self._tribe_has_building_type(tribe, "tribe_fence")
        has_flag = bool(tribe.get("territory_flags"))
        granary_food = TRIBE_WAR_REVIVAL_BRANCH_FOOD_REWARD + (TRIBE_WAR_REVIVAL_STORAGE_FOOD_BONUS if has_storage else 0) + int(goal_profile.get("granaryFoodBonus", 0) or 0)
        granary_trade = TRIBE_WAR_REVIVAL_BRANCH_TRADE_REWARD + (TRIBE_WAR_REVIVAL_ROAD_TRADE_BONUS if has_road else 0) + int(goal_profile.get("granaryTradeBonus", 0) or 0)
        oath_renown = TRIBE_WAR_REVIVAL_BRANCH_OATH_RENOWN + (TRIBE_WAR_REVIVAL_FLAG_RENOWN_BONUS if has_flag else 0) + int(goal_profile.get("oathRenownBonus", 0) or 0)
        oath_relief = 1 + (TRIBE_WAR_REVIVAL_FENCE_FATIGUE_BONUS if has_fence else 0)
        granary_bonus = []
        if has_storage:
            granary_bonus.append(f"仓库食物+{TRIBE_WAR_REVIVAL_STORAGE_FOOD_BONUS}")
        if has_road:
            granary_bonus.append(f"道路贸易+{TRIBE_WAR_REVIVAL_ROAD_TRADE_BONUS}")
        if int(goal_profile.get("granaryFoodBonus", 0) or 0):
            granary_bonus.append(f"{goal_profile.get('goalLabel')}食物+{goal_profile.get('granaryFoodBonus')}")
        if int(goal_profile.get("granaryTradeBonus", 0) or 0):
            granary_bonus.append(f"{goal_profile.get('goalLabel')}贸易+{goal_profile.get('granaryTradeBonus')}")
        oath_bonus = []
        if has_flag:
            oath_bonus.append(f"旗帜声望+{TRIBE_WAR_REVIVAL_FLAG_RENOWN_BONUS}")
        if has_fence:
            oath_bonus.append(f"围栏战疲缓解+{TRIBE_WAR_REVIVAL_FENCE_FATIGUE_BONUS}")
        if int(goal_profile.get("oathRenownBonus", 0) or 0):
            oath_bonus.append(f"{goal_profile.get('goalLabel')}声望+{goal_profile.get('oathRenownBonus')}")
        branches = [
            {
                "id": f"{branch_group}_granary",
                "status": "pending",
                "branchKind": "granary",
                "branchGroup": branch_group,
                "otherTribeId": other_tribe_id,
                "otherTribeName": other_name,
                "title": "粮仓复兴",
                "summary": f"把与 {other_name} 战后散乱的粮线重新收拢，优先恢复食物和贸易信誉。",
                "foodCost": 0,
                "woodCost": TRIBE_WAR_REVIVAL_WOOD_COST,
                "renownReward": 1,
                "fatigueRelief": 0,
                "foodReward": granary_food,
                "tradeReward": granary_trade,
                "buildingBonusLabel": "、".join(granary_bonus),
                "warId": task.get("warId"),
                "createdAt": now_text
            },
            {
                "id": f"{branch_group}_oath",
                "status": "pending",
                "branchKind": "oath",
                "branchGroup": branch_group,
                "otherTribeId": other_tribe_id,
                "otherTribeName": other_name,
                "title": "重立战誓",
                "summary": f"召集族人重述与 {other_name} 一战的教训，优先恢复声望并保留反击意志。",
                "foodCost": TRIBE_WAR_REVIVAL_FOOD_COST // 2,
                "woodCost": 0,
                "renownReward": oath_renown,
                "fatigueRelief": oath_relief,
                "warPressure": TRIBE_WAR_REVIVAL_BRANCH_PRESSURE,
                "buildingBonusLabel": "、".join(oath_bonus),
                "warId": task.get("warId"),
                "createdAt": now_text
            }
        ]
        existing = [
            item for item in (tribe.get("war_revival_tasks", []) or [])
            if not (isinstance(item, dict) and item.get("branchGroup") == branch_group)
        ]
        existing.extend(branches)
        tribe["war_revival_tasks"] = existing[-6:]

    def _create_war_revival_branch_tasks(self, tribe: dict, task: dict, now_text: str):
        other_tribe_id = task.get("otherTribeId")
        other_name = task.get("otherTribeName", "其他部落")
        branch_group = f"revival_branch_{task.get('warId')}_{tribe.get('id')}"
        goal_profile = self._war_goal_followup_profile(task)
        has_storage = self._tribe_has_building_type(tribe, "tribe_storage")
        has_road = self._tribe_has_building_type(tribe, "tribe_road")
        has_fence = self._tribe_has_building_type(tribe, "tribe_fence")
        has_flag = bool(tribe.get("territory_flags"))
        granary_food = (
            TRIBE_WAR_REVIVAL_BRANCH_FOOD_REWARD
            + (TRIBE_WAR_REVIVAL_STORAGE_FOOD_BONUS if has_storage else 0)
            + int(goal_profile.get("granaryFoodBonus", 0) or 0)
        )
        granary_trade = (
            TRIBE_WAR_REVIVAL_BRANCH_TRADE_REWARD
            + (TRIBE_WAR_REVIVAL_ROAD_TRADE_BONUS if has_road else 0)
            + int(goal_profile.get("granaryTradeBonus", 0) or 0)
        )
        oath_renown = (
            TRIBE_WAR_REVIVAL_BRANCH_OATH_RENOWN
            + (TRIBE_WAR_REVIVAL_FLAG_RENOWN_BONUS if has_flag else 0)
            + int(goal_profile.get("oathRenownBonus", 0) or 0)
        )
        oath_relief = 1 + (TRIBE_WAR_REVIVAL_FENCE_FATIGUE_BONUS if has_fence else 0)
        granary_bonus = []
        if has_storage:
            granary_bonus.append(f"仓库食物+{TRIBE_WAR_REVIVAL_STORAGE_FOOD_BONUS}")
        if has_road:
            granary_bonus.append(f"道路贸易+{TRIBE_WAR_REVIVAL_ROAD_TRADE_BONUS}")
        if int(goal_profile.get("granaryFoodBonus", 0) or 0):
            granary_bonus.append(f"{goal_profile.get('goalLabel')}食物+{goal_profile.get('granaryFoodBonus')}")
        if int(goal_profile.get("granaryTradeBonus", 0) or 0):
            granary_bonus.append(f"{goal_profile.get('goalLabel')}贸易+{goal_profile.get('granaryTradeBonus')}")
        oath_bonus = []
        if has_flag:
            oath_bonus.append(f"旗帜声望+{TRIBE_WAR_REVIVAL_FLAG_RENOWN_BONUS}")
        if has_fence:
            oath_bonus.append(f"围栏战疲缓解+{TRIBE_WAR_REVIVAL_FENCE_FATIGUE_BONUS}")
        if int(goal_profile.get("oathRenownBonus", 0) or 0):
            oath_bonus.append(f"{goal_profile.get('goalLabel')}声望+{goal_profile.get('oathRenownBonus')}")
        branches = [
            {
                "id": f"{branch_group}_granary",
                "status": "pending",
                "branchKind": "granary",
                "branchGroup": branch_group,
                "otherTribeId": other_tribe_id,
                "otherTribeName": other_name,
                "title": "粮仓复兴",
                "summary": f"把与 {other_name} 战后散乱的粮线重新收拢，优先恢复食物和贸易信誉。",
                "foodCost": 0,
                "woodCost": TRIBE_WAR_REVIVAL_WOOD_COST,
                "renownReward": 1,
                "fatigueRelief": 0,
                "foodReward": granary_food,
                "tradeReward": granary_trade,
                "buildingBonusLabel": "、".join(granary_bonus),
                "warGoalKind": goal_profile.get("kind"),
                "goalEffectLabel": goal_profile.get("summary"),
                "warId": task.get("warId"),
                "createdAt": now_text
            },
            {
                "id": f"{branch_group}_oath",
                "status": "pending",
                "branchKind": "oath",
                "branchGroup": branch_group,
                "otherTribeId": other_tribe_id,
                "otherTribeName": other_name,
                "title": "重立战誓",
                "summary": f"召集族人重述与 {other_name} 一战的教训，优先恢复声望并保留反击意志。",
                "foodCost": TRIBE_WAR_REVIVAL_FOOD_COST // 2,
                "woodCost": 0,
                "renownReward": oath_renown,
                "fatigueRelief": oath_relief,
                "warPressure": TRIBE_WAR_REVIVAL_BRANCH_PRESSURE,
                "buildingBonusLabel": "、".join(oath_bonus),
                "warGoalKind": goal_profile.get("kind"),
                "goalEffectLabel": goal_profile.get("summary"),
                "warId": task.get("warId"),
                "createdAt": now_text
            }
        ]
        existing = [
            item for item in (tribe.get("war_revival_tasks", []) or [])
            if not (isinstance(item, dict) and item.get("branchGroup") == branch_group)
        ]
        existing.extend(branches)
        tribe["war_revival_tasks"] = existing[-6:]

    def _create_war_diplomacy_tasks(self, tribe_id: str, other_tribe_id: str, war: dict, now_text: str, mode: str = "truce", mediator_id: str = ""):
        mode_labels = {
            "resolved": "战后停战",
            "truce": "主动停战",
            "mediated": "调停停战"
        }
        for source_id, target_id in ((tribe_id, other_tribe_id), (other_tribe_id, tribe_id)):
            source = self.tribes.get(source_id)
            target = self.tribes.get(target_id)
            if not source:
                continue
            task = {
                "id": f"war_diplomacy_{war.get('id')}_{source_id}_{mode}",
                "status": "pending",
                "mode": mode,
                "modeLabel": mode_labels.get(mode, "停战外交"),
                "otherTribeId": target_id,
                "otherTribeName": target.get("name", "其他部落") if target else "其他部落",
                "title": "停战外交",
                "summary": f"与 {target.get('name', '其他部落') if target else '其他部落'} 的战争已经停下，可以履约修好，也可以追责保留仇怨。",
                "foodCost": TRIBE_WAR_DIPLOMACY_FOOD_COST,
                "renownReward": TRIBE_WAR_DIPLOMACY_RENOWN,
                "grievanceRenown": TRIBE_WAR_GRIEVANCE_RENOWN,
                "goal": war.get("goal") or {},
                "warGoalKind": goal_profile.get("kind"),
                "goalEffectLabel": goal_profile.get("summary"),
                "warId": war.get("id"),
                "mediatorTribeId": mediator_id,
                "createdAt": now_text
            }
            tasks = [
                item for item in (source.get("war_diplomacy_tasks", []) or [])
                if isinstance(item, dict) and item.get("id") != task["id"]
            ]
            tasks.append(task)
            source["war_diplomacy_tasks"] = tasks[-5:]

    def _create_war_aftermath_task(self, tribe: dict, other_tribe_id: str, action: str, diplomacy_task: dict, now_text: str):
        if not tribe or action not in {"honor", "grievance"}:
            return
        other = self.tribes.get(other_tribe_id)
        other_name = diplomacy_task.get("otherTribeName") or (other.get("name", "其他部落") if other else "其他部落")
        goal_profile = self._war_goal_followup_profile(diplomacy_task)
        if action == "honor":
            task = {
                "id": f"war_aftermath_{diplomacy_task.get('id')}_{tribe.get('id')}_market",
                "status": "pending",
                "kind": "market",
                "otherTribeId": other_tribe_id,
                "otherTribeName": other_name,
                "title": "边市回暖",
                "summary": f"履行与 {other_name} 的停战约定后，族人可以整理边市信物，把战后的谨慎转成贸易往来。",
                "foodCost": TRIBE_WAR_AFTERMATH_FOOD_COST,
                "foodReward": TRIBE_WAR_AFTERMATH_FOOD_REWARD + int(goal_profile.get("marketFoodBonus", 0) or 0),
                "tradeReward": TRIBE_WAR_AFTERMATH_TRADE_REWARD + int(goal_profile.get("marketTradeBonus", 0) or 0),
                "renownReward": TRIBE_WAR_AFTERMATH_RENOWN,
                "warGoalKind": goal_profile.get("kind"),
                "goalEffectLabel": goal_profile.get("summary"),
                "warId": diplomacy_task.get("warId"),
                "diplomacyId": diplomacy_task.get("id"),
                "createdAt": now_text
            }
        else:
            task = {
                "id": f"war_aftermath_{diplomacy_task.get('id')}_{tribe.get('id')}_watch",
                "status": "pending",
                "kind": "watch",
                "otherTribeId": other_tribe_id,
                "otherTribeName": other_name,
                "title": "战后警戒",
                "summary": f"追责 {other_name} 的停战余恨后，族人可以重整边境守望，减少旧怨继续滚成新战事。",
                "foodCost": 0,
                "pressureRelief": TRIBE_WAR_AFTERMATH_PRESSURE_RELIEF + int(goal_profile.get("watchPressureRelief", 0) or 0),
                "renownReward": TRIBE_WAR_AFTERMATH_RENOWN,
                "discoveryReward": int(goal_profile.get("aftermathDiscoveryBonus", 0) or 0),
                "warGoalKind": goal_profile.get("kind"),
                "goalEffectLabel": goal_profile.get("summary"),
                "warId": diplomacy_task.get("warId"),
                "diplomacyId": diplomacy_task.get("id"),
                "createdAt": now_text
            }
        tasks = [
            item for item in (tribe.get("war_aftermath_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") != task["id"]
        ]
        tasks.append(task)
        tribe["war_aftermath_tasks"] = tasks[-5:]

    def _record_war_ally_memory(self, tribe: dict, record: dict):
        if not tribe:
            return
        records = [
            item for item in (tribe.get("war_ally_records", []) or [])
            if isinstance(item, dict)
        ]
        records.append(record)
        tribe["war_ally_records"] = records[-8:]

    def _append_war_ally_task(self, tribe: dict, task: dict):
        if not tribe or not task:
            return
        tasks = [
            item for item in (tribe.get("war_ally_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") != task.get("id")
        ]
        tasks.append(task)
        tribe["war_ally_tasks"] = tasks[-8:]

    def _create_war_ally_followup_tasks(self, record: dict, now_text: str):
        if not record:
            return
        supporter_id = record.get("supporterTribeId")
        side_id = record.get("sideTribeId")
        supporter = self.tribes.get(supporter_id)
        side = self.tribes.get(side_id)
        record_id = record.get("id")
        if record.get("kind") == "support":
            self._append_war_ally_task(supporter, {
                "id": f"war_ally_{record_id}_supply",
                "status": "pending",
                "kind": "support_supply",
                "recordId": record_id,
                "otherTribeId": side_id,
                "otherTribeName": record.get("sideTribeName", "盟友"),
                "title": "战盟补给线",
                "summary": f"把对 {record.get('sideTribeName', '盟友')} 的战争承诺落成一条短期补给线，巩固战后关系。",
                "foodCost": TRIBE_WAR_ALLY_SUPPLY_FOOD_COST,
                "renownReward": TRIBE_WAR_ALLY_SUPPLY_RENOWN,
                "tradeReward": TRIBE_WAR_ALLY_SUPPLY_TRADE,
                "relationDelta": 2,
                "tradeTrustDelta": 1,
                "createdAt": now_text
            })
            self._append_war_ally_task(side, {
                "id": f"war_ally_{record_id}_reception",
                "status": "pending",
                "kind": "support_reception",
                "recordId": record_id,
                "otherTribeId": supporter_id,
                "otherTribeName": record.get("supporterTribeName", "援助者"),
                "title": "接应盟友",
                "summary": f"接应 {record.get('supporterTribeName', '援助者')} 留下的战盟补给，转为食物、声望和长期信任。",
                "foodReward": TRIBE_WAR_ALLY_RECEPTION_FOOD,
                "renownReward": TRIBE_WAR_ALLY_RECEPTION_RENOWN,
                "relationDelta": 1,
                "tradeTrustDelta": 1,
                "createdAt": now_text
            })
        elif record.get("kind") == "betrayal":
            new_side_name = record.get("newSideTribeName", "另一方")
            self._append_war_ally_task(side, {
                "id": f"war_ally_{record_id}_grievance",
                "status": "pending",
                "kind": "betrayal_grievance",
                "recordId": record_id,
                "otherTribeId": supporter_id,
                "otherTribeName": record.get("supporterTribeName", "背刺者"),
                "title": "背刺追责",
                "summary": f"{record.get('supporterTribeName', '背刺者')} 转向 {new_side_name} 后，族人可以公开追责，把旧承诺变成边境压力。",
                "renownReward": TRIBE_WAR_ALLY_GRIEVANCE_RENOWN,
                "warPressure": TRIBE_WAR_ALLY_GRIEVANCE_PRESSURE,
                "relationDelta": -1,
                "createdAt": now_text
            })
            self._append_war_ally_task(supporter, {
                "id": f"war_ally_{record_id}_reparation",
                "status": "pending",
                "kind": "betrayal_reparation",
                "recordId": record_id,
                "otherTribeId": side_id,
                "otherTribeName": record.get("sideTribeName", "旧盟友"),
                "title": "赔礼修复",
                "summary": f"向 {record.get('sideTribeName', '旧盟友')} 送出赔礼，尽量压低背刺带来的长期敌意。",
                "foodCost": TRIBE_WAR_ALLY_REPARATION_FOOD_COST,
                "renownReward": TRIBE_WAR_ALLY_REPARATION_RENOWN,
                "pressureRelief": TRIBE_WAR_ALLY_REPARATION_PRESSURE_RELIEF,
                "relationDelta": 2,
                "tradeTrustDelta": 1,
                "createdAt": now_text
            })

    def _mark_war_betrayal(self, supporter: dict, war_id: str, old_side_id: str, new_side_id: str, now_text: str):
        old_side = self.tribes.get(old_side_id)
        new_side = self.tribes.get(new_side_id)
        if not supporter or not old_side:
            return ""
        for record in supporter.get("war_ally_records", []) or []:
            if (
                isinstance(record, dict)
                and record.get("warId") == war_id
                and record.get("sideTribeId") == old_side_id
                and record.get("kind") == "support"
                and record.get("status") == "promised"
            ):
                record["status"] = "betrayed"
                record["betrayedAt"] = now_text
                record["betrayedForTribeId"] = new_side_id
                record["betrayedForTribeName"] = new_side.get("name", "另一方") if new_side else "另一方"
        supporter["renown"] = int(supporter.get("renown", 0) or 0) + TRIBE_WAR_BETRAYAL_RENOWN
        supporter["trade_reputation"] = max(0, int(supporter.get("trade_reputation", 0) or 0) - 1)
        relation = supporter.setdefault("boundary_relations", {}).setdefault(old_side_id, {})
        relation["score"] = max(-9, int(relation.get("score", 0) or 0) - 3)
        relation["warPressure"] = min(
            TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD,
            int(relation.get("warPressure", 0) or 0) + TRIBE_WAR_BETRAYAL_PRESSURE
        )
        relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
        relation["lastAction"] = "formal_war_betrayal"
        relation["lastActionAt"] = now_text
        old_relation = old_side.setdefault("boundary_relations", {}).setdefault(supporter.get("id"), {})
        old_relation["score"] = max(-9, int(old_relation.get("score", 0) or 0) - 3)
        old_relation["lastAction"] = "formal_war_betrayed"
        old_relation["lastActionAt"] = now_text
        betrayal_record = {
            "id": f"war_betrayal_{war_id}_{supporter.get('id')}_{old_side_id}_{int(datetime.now().timestamp() * 1000)}",
            "kind": "betrayal",
            "status": "betrayed",
            "warId": war_id,
            "sideTribeId": old_side_id,
            "sideTribeName": old_side.get("name", "旧盟友"),
            "newSideTribeId": new_side_id,
            "newSideTribeName": new_side.get("name", "另一方") if new_side else "另一方",
            "supporterTribeId": supporter.get("id"),
            "supporterTribeName": supporter.get("name", "支援部落"),
            "createdAt": now_text
        }
        self._record_war_ally_memory(supporter, betrayal_record)
        self._record_war_ally_memory(old_side, betrayal_record)
        self._create_war_ally_followup_tasks(betrayal_record, now_text)
        if hasattr(self, "_open_tribe_atonement_task"):
            self._open_tribe_atonement_task(
                supporter,
                "betrayal",
                "战争背刺",
                "",
                old_side_id,
                old_side.get("name", "旧盟友"),
                betrayal_record.get("id", "")
            )
        if hasattr(self, "_open_betrayal_history_fact_claim"):
            self._open_betrayal_history_fact_claim(betrayal_record)
        return f" 但这也背弃了先前对 {old_side.get('name', '旧盟友')} 的战争承诺。"

    async def support_formal_war(self, player_id: str, war_id: str, side_tribe_id: str):
        supporter_id = self.player_tribes.get(player_id)
        supporter = self.tribes.get(supporter_id)
        if not supporter:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = supporter.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以代表部落支援战争")
            return
        tribe, war, other_tribe, other_war = self._find_formal_war_pair(war_id)
        if not war or war.get("status") != "active":
            await self._send_tribe_error(player_id, "这场部落战争已经结束")
            return
        war_sides = {war.get("tribeId"), war.get("otherTribeId")}
        if supporter_id in war_sides:
            await self._send_tribe_error(player_id, "战争双方不能作为第三方支援")
            return
        if side_tribe_id not in war_sides:
            await self._send_tribe_error(player_id, "只能支援战争中的一方")
            return
        if int(supporter.get("food", 0) or 0) < TRIBE_WAR_SUPPORT_FOOD_COST:
            await self._send_tribe_error(player_id, f"支援战争需要公共食物{TRIBE_WAR_SUPPORT_FOOD_COST}")
            return
        supporter["food"] = int(supporter.get("food", 0) or 0) - TRIBE_WAR_SUPPORT_FOOD_COST
        supporter["renown"] = int(supporter.get("renown", 0) or 0) + TRIBE_WAR_SUPPORT_RENOWN
        supporter["trade_reputation"] = int(supporter.get("trade_reputation", 0) or 0) + 1
        now_text = datetime.now().isoformat()
        betrayal_note = ""
        for old_side_id in war_sides:
            if old_side_id != side_tribe_id and any(
                isinstance(record, dict)
                and record.get("warId") == war_id
                and record.get("sideTribeId") == old_side_id
                and record.get("kind") == "support"
                and record.get("status") == "promised"
                for record in supporter.get("war_ally_records", []) or []
            ):
                betrayal_note = self._mark_war_betrayal(supporter, war_id, old_side_id, side_tribe_id, now_text)
        for item in (war, other_war):
            if item:
                scores = item.setdefault("scores", {})
                scores[side_tribe_id] = int(scores.get(side_tribe_id, 0) or 0) + TRIBE_WAR_SUPPORT_SCORE
                item.setdefault("interventions", []).append({
                    "kind": "support",
                    "supporterTribeId": supporter_id,
                    "supporterTribeName": supporter.get("name", "第三方部落"),
                    "sideTribeId": side_tribe_id,
                    "score": TRIBE_WAR_SUPPORT_SCORE,
                    "createdAt": now_text
                })
        supported = self.tribes.get(side_tribe_id)
        relation = supporter.setdefault("boundary_relations", {}).setdefault(side_tribe_id, {})
        relation["score"] = min(8, int(relation.get("score", 0) or 0) + 1)
        relation["lastAction"] = "formal_war_support"
        relation["lastActionAt"] = now_text
        support_record = {
            "id": f"war_support_{war_id}_{supporter_id}_{side_tribe_id}_{int(datetime.now().timestamp() * 1000)}",
            "kind": "support",
            "status": "promised",
            "warId": war_id,
            "sideTribeId": side_tribe_id,
            "sideTribeName": supported.get("name", "一方") if supported else "一方",
            "supporterTribeId": supporter_id,
            "supporterTribeName": supporter.get("name", "第三方部落"),
            "score": TRIBE_WAR_SUPPORT_SCORE,
            "createdAt": now_text
        }
        self._record_war_ally_memory(supporter, support_record)
        if supported:
            self._record_war_ally_memory(supported, support_record)
        self._create_war_ally_followup_tasks(support_record, now_text)
        detail = f"{member.get('name', '成员')} 代表 {supporter.get('name', '第三方部落')} 向 {supported.get('name', '一方') if supported else '一方'} 提供战争支援，食物-{TRIBE_WAR_SUPPORT_FOOD_COST}，战线+{TRIBE_WAR_SUPPORT_SCORE}。{betrayal_note}"
        for target_id in {supporter_id, *war_sides}:
            target = self.tribes.get(target_id)
            if target:
                self._add_tribe_history(target, "governance", "战争支援", detail, player_id, {"kind": "formal_war_support", "warId": war_id, "supporterTribeId": supporter_id, "sideTribeId": side_tribe_id})
                await self._notify_tribe(target_id, detail)
                await self.broadcast_tribe_state(target_id)
        if int(war.get("scores", {}).get(side_tribe_id, 0) or 0) >= int(war.get("scoreTarget", TRIBE_WAR_SCORE_TARGET) or TRIBE_WAR_SCORE_TARGET):
            await self.resolve_formal_war(player_id, war_id)

    async def mediate_formal_war(self, player_id: str, war_id: str):
        mediator_id = self.player_tribes.get(player_id)
        mediator = self.tribes.get(mediator_id)
        if not mediator:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = mediator.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以代表部落调停战争")
            return
        tribe, war, other_tribe, other_war = self._find_formal_war_pair(war_id)
        if not war or war.get("status") != "active":
            await self._send_tribe_error(player_id, "这场部落战争已经结束")
            return
        tribe_id = war.get("tribeId")
        other_tribe_id = war.get("otherTribeId")
        if mediator_id in {tribe_id, other_tribe_id}:
            await self._send_tribe_error(player_id, "战争双方不能作为第三方调停")
            return
        if int(mediator.get("food", 0) or 0) < TRIBE_WAR_MEDIATION_FOOD_COST:
            await self._send_tribe_error(player_id, f"调停战争需要公共食物{TRIBE_WAR_MEDIATION_FOOD_COST}")
            return
        mediator["food"] = int(mediator.get("food", 0) or 0) - TRIBE_WAR_MEDIATION_FOOD_COST
        mediator["renown"] = int(mediator.get("renown", 0) or 0) + TRIBE_WAR_MEDIATION_RENOWN
        now_text = datetime.now().isoformat()
        reduced_scores = {}
        for item in (war, other_war):
            if item:
                scores = item.setdefault("scores", {})
                for side_id in (tribe_id, other_tribe_id):
                    scores[side_id] = max(0, int(scores.get(side_id, 0) or 0) - TRIBE_WAR_MEDIATION_SCORE_REDUCTION)
                    reduced_scores[side_id] = scores[side_id]
                item.setdefault("interventions", []).append({
                    "kind": "mediation",
                    "mediatorTribeId": mediator_id,
                    "mediatorTribeName": mediator.get("name", "调停部落"),
                    "createdAt": now_text
                })
        for side_id in (tribe_id, other_tribe_id):
            relation = mediator.setdefault("boundary_relations", {}).setdefault(side_id, {})
            relation["score"] = min(8, int(relation.get("score", 0) or 0) + 1)
            relation["lastAction"] = "formal_war_mediation"
            relation["lastActionAt"] = now_text
        max_score = max(int(reduced_scores.get(tribe_id, 0) or 0), int(reduced_scores.get(other_tribe_id, 0) or 0))
        lead = abs(int(reduced_scores.get(tribe_id, 0) or 0) - int(reduced_scores.get(other_tribe_id, 0) or 0))
        truce = max_score <= 2 or lead <= 1
        if truce:
            for item in (war, other_war):
                if item:
                    item["status"] = "mediated_truce"
                    item["truceBy"] = player_id
                    item["resolvedAt"] = now_text
            for source_id, target_id in ((tribe_id, other_tribe_id), (other_tribe_id, tribe_id)):
                source = self.tribes.get(source_id)
                if source:
                    progress = source.setdefault("boundary_relations", {}).setdefault(target_id, {})
                    progress["score"] = min(6, int(progress.get("score", 0) or 0) + 1)
                    progress["warPressure"] = 0
                    progress["canDeclareWar"] = False
                    progress["lastAction"] = "formal_war_mediated_truce"
                    progress["lastActionAt"] = now_text
            self._create_war_repair_tasks(tribe_id, other_tribe_id, war, now_text)
            self._create_war_diplomacy_tasks(tribe_id, other_tribe_id, war, now_text, "mediated", mediator_id)
        detail = f"{member.get('name', '成员')} 代表 {mediator.get('name', '调停部落')} 调停正式部落战争，双方战线各降{TRIBE_WAR_MEDIATION_SCORE_REDUCTION}。"
        if truce:
            detail += " 双方接受调停，进入停战修复。"
        for target_id in {mediator_id, tribe_id, other_tribe_id}:
            target = self.tribes.get(target_id)
            if target:
                self._add_tribe_history(target, "governance", "战争调停", detail, player_id, {"kind": "formal_war_mediation", "warId": war_id, "mediatorTribeId": mediator_id, "truce": truce})
                await self._notify_tribe(target_id, detail)
                await self.broadcast_tribe_state(target_id)

    async def resolve_formal_war(self, player_id: str, war_id: str):
        tribe, war, other_tribe, other_war = self._find_formal_war_pair(war_id)
        if not war or war.get("status") != "active":
            await self._send_tribe_error(player_id, "这场部落战争已经结束")
            return
        scores = dict(war.get("scores") or {})
        tribe_id = war.get("tribeId")
        other_tribe_id = war.get("otherTribeId")
        own_score = int(scores.get(tribe_id, 0) or 0)
        other_score = int(scores.get(other_tribe_id, 0) or 0)
        winner_id = tribe_id if own_score >= other_score else other_tribe_id
        loser_id = other_tribe_id if winner_id == tribe_id else tribe_id
        winner = self.tribes.get(winner_id)
        loser = self.tribes.get(loser_id)
        now_text = datetime.now().isoformat()
        for item in (war, other_war):
            if item:
                item["status"] = "resolved"
                item["winnerTribeId"] = winner_id
                item["resolvedAt"] = now_text
        reward_parts = []
        if winner:
            winner["renown"] = int(winner.get("renown", 0) or 0) + TRIBE_WAR_RENOWN_REWARD
            reward_parts.append(f"胜方声望+{TRIBE_WAR_RENOWN_REWARD}")
            reward_parts.extend(self._apply_formal_war_goal_reward(winner, war.get("goal") or {}))
        if loser and winner:
            paid_food = min(TRIBE_WAR_REPARATION_FOOD, max(0, int(loser.get("food", 0) or 0)))
            if paid_food:
                loser["food"] = int(loser.get("food", 0) or 0) - paid_food
                winner["food"] = int(winner.get("food", 0) or 0) + paid_food
                reward_parts.append(f"战后赔付食物{paid_food}")
        for source_id, target_id in ((winner_id, loser_id), (loser_id, winner_id)):
            source = self.tribes.get(source_id)
            if source:
                progress = source.setdefault("boundary_relations", {}).setdefault(target_id, {})
                progress["score"] = max(-9, int(progress.get("score", 0) or 0) - 2)
                progress["warPressure"] = 0
                progress["canDeclareWar"] = False
                progress["lastAction"] = "formal_war_resolved"
                progress["lastActionAt"] = now_text
        self._create_war_repair_tasks(tribe_id, other_tribe_id, war, now_text)
        self._create_war_goal_echo_outcomes(tribe_id, other_tribe_id, war, now_text)
        fatigue_count = self._apply_formal_war_fatigue(war, winner_id, loser_id, now_text)
        self._create_war_revival_task(loser_id, winner_id, war, now_text)
        self._create_war_diplomacy_tasks(tribe_id, other_tribe_id, war, now_text, "resolved")
        history_fact_opened = False
        if hasattr(self, "_open_war_history_fact_claim"):
            history_fact_opened = bool(self._open_war_history_fact_claim(war, winner, loser, "formal_war"))
        if fatigue_count:
            reward_parts.append(f"参战者留下战疲{fatigue_count}人")
        detail = f"{winner.get('name', '一方') if winner else '一方'} 在正式部落战争中取得优势，双方进入短暂停战。{'、'.join(reward_parts)}。"
        if history_fact_opened:
            detail += " 双方开始争夺这场战争如何写入编年史。"
        for target_id in {tribe_id, other_tribe_id}:
            target = self.tribes.get(target_id)
            if target:
                if hasattr(self, "_create_celebration_echo"):
                    self._create_celebration_echo(target, "war", goal.get("label", "正式战争"), player_id, war_id)
                self._add_tribe_history(target, "governance", "正式战争结算", detail, player_id, {"kind": "formal_war", "warId": war_id, "winnerTribeId": winner_id})
                await self._notify_tribe(target_id, detail)
                await self.broadcast_tribe_state(target_id)
        await self._broadcast_current_map()

    async def request_war_truce(self, player_id: str, war_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以提出正式停战")
            return
        own_tribe, war, other_tribe, other_war = self._find_formal_war_pair(war_id)
        if not war or war.get("status") != "active":
            await self._send_tribe_error(player_id, "这场部落战争已经结束")
            return
        if tribe_id not in {war.get("tribeId"), war.get("otherTribeId")}:
            await self._send_tribe_error(player_id, "只有战争双方可以停战")
            return
        if int(tribe.get("food", 0) or 0) < TRIBE_WAR_TRUCE_FOOD_COST:
            await self._send_tribe_error(player_id, f"停战谈判需要公共食物{TRIBE_WAR_TRUCE_FOOD_COST}")
            return
        tribe["food"] = int(tribe.get("food", 0) or 0) - TRIBE_WAR_TRUCE_FOOD_COST
        now_text = datetime.now().isoformat()
        for item in (war, other_war):
            if item:
                item["status"] = "truce"
                item["truceBy"] = player_id
                item["resolvedAt"] = now_text
        other_tribe_id = war.get("otherTribeId") if war.get("tribeId") == tribe_id else war.get("tribeId")
        for source_id, target_id in ((tribe_id, other_tribe_id), (other_tribe_id, tribe_id)):
            source = self.tribes.get(source_id)
            if source:
                progress = source.setdefault("boundary_relations", {}).setdefault(target_id, {})
                progress["score"] = min(6, int(progress.get("score", 0) or 0) + 1)
                progress["warPressure"] = 0
                progress["canDeclareWar"] = False
                progress["lastAction"] = "formal_war_truce"
                progress["lastActionAt"] = now_text
        self._create_war_repair_tasks(tribe_id, other_tribe_id, war, now_text)
        self._create_war_goal_echo_outcomes(tribe_id, other_tribe_id, war, now_text)
        self._create_war_diplomacy_tasks(tribe_id, other_tribe_id, war, now_text, "truce")
        detail = f"{member.get('name', '成员')} 代表 {tribe.get('name', '部落')} 提出停战谈判，消耗食物{TRIBE_WAR_TRUCE_FOOD_COST}，双方转入战后修复。"
        for target_id in {tribe_id, other_tribe_id}:
            target = self.tribes.get(target_id)
            if target:
                self._add_tribe_history(target, "governance", "正式停战", detail, player_id, {"kind": "formal_war_truce", "warId": war_id})
                await self._notify_tribe(target_id, detail)
                await self.broadcast_tribe_state(target_id)

    async def complete_war_repair(self, player_id: str, repair_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((
            item for item in (tribe.get("war_repair_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") == repair_id and item.get("status") == "pending"
        ), None)
        if not task:
            await self._send_tribe_error(player_id, "没有找到可完成的战后修复任务")
            return
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(task.get("woodCost", TRIBE_WAR_REPAIR_WOOD_COST) or 0)
        stone_cost = int(task.get("stoneCost", TRIBE_WAR_REPAIR_STONE_COST) or 0)
        stone_discount = self._region_event_bonus_value(tribe, "warRepairStoneDiscount")
        if stone_discount:
            stone_cost = max(0, stone_cost - stone_discount)
        if int(storage.get("wood", 0) or 0) < wood_cost or int(storage.get("stone", 0) or 0) < stone_cost:
            await self._send_tribe_error(player_id, "战后修复需要公共木材和石块")
            return
        storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        storage["stone"] = int(storage.get("stone", 0) or 0) - stone_cost
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + int(task.get("renownReward", TRIBE_WAR_REPAIR_RENOWN) or 0)
        task["status"] = "completed"
        task["completedBy"] = player_id
        task["completedAt"] = datetime.now().isoformat()
        other_tribe_id = task.get("otherTribeId")
        if other_tribe_id:
            progress = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
            progress["score"] = min(8, int(progress.get("score", 0) or 0) + 1)
            progress["lastAction"] = "formal_war_repaired"
            progress["lastActionAt"] = task["completedAt"]
        member = tribe.get("members", {}).get(player_id, {})
        bonus_labels = [
            item.get("label")
            for item in self._active_region_event_bonus_summaries(tribe)
            if item.get("label")
        ]
        detail = f"{member.get('name', '成员')} 完成战后修复，消耗木材{wood_cost}、石块{stone_cost}，部落声望+{task.get('renownReward', TRIBE_WAR_REPAIR_RENOWN)}。"
        if stone_discount:
            detail += f" 山地采石坑节省石块{stone_discount}。"
        self._add_tribe_history(tribe, "governance", "战后修复", detail, player_id, {"kind": "war_repair", "repairId": repair_id, "otherTribeId": other_tribe_id, "regionEventBonusLabels": bonus_labels})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_war_revival(self, player_id: str, revival_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((
            item for item in (tribe.get("war_revival_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") == revival_id and item.get("status") == "pending"
        ), None)
        if not task:
            await self._send_tribe_error(player_id, "没有找到可完成的战败复兴任务")
            return
        food_cost = int(task.get("foodCost", TRIBE_WAR_REVIVAL_FOOD_COST) or 0)
        wood_cost = int(task.get("woodCost", TRIBE_WAR_REVIVAL_WOOD_COST) or 0)
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        if int(tribe.get("food", 0) or 0) < food_cost or int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, "战败复兴需要公共食物和木材")
            return
        tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + int(task.get("renownReward", TRIBE_WAR_REVIVAL_RENOWN) or 0)
        if int(task.get("foodReward", 0) or 0):
            tribe["food"] = int(tribe.get("food", 0) or 0) + int(task.get("foodReward", 0) or 0)
        if int(task.get("tradeReward", 0) or 0):
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + int(task.get("tradeReward", 0) or 0)
        if int(task.get("discoveryReward", 0) or 0):
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + int(task.get("discoveryReward", 0) or 0)
        relief = int(task.get("fatigueRelief", TRIBE_WAR_REVIVAL_FATIGUE_RELIEF) or 0)
        relieved = 0
        for member_id in (tribe.get("members", {}) or {}).keys():
            player = self.players.get(member_id)
            if not player:
                continue
            before = int(player.get("conflict_fatigue", 0) or 0)
            if before <= 0:
                continue
            after = max(0, before - relief)
            player["conflict_fatigue"] = after
            if after <= 0:
                player.pop("conflict_fatigue_until", None)
            relieved += 1
        task["status"] = "completed"
        task["completedBy"] = player_id
        task["completedAt"] = datetime.now().isoformat()
        other_tribe_id = task.get("otherTribeId")
        if other_tribe_id:
            progress = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
            progress["score"] = min(6, int(progress.get("score", 0) or 0) + 1)
            if int(task.get("warPressure", 0) or 0):
                progress["warPressure"] = min(
                    TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD,
                    int(progress.get("warPressure", 0) or 0) + int(task.get("warPressure", 0) or 0)
                )
                progress["canDeclareWar"] = int(progress.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            progress["lastAction"] = "formal_war_revival"
            progress["lastActionAt"] = task["completedAt"]
        if task.get("branchGroup"):
            for item in tribe.get("war_revival_tasks", []) or []:
                if isinstance(item, dict) and item.get("branchGroup") == task.get("branchGroup") and item.get("id") != task.get("id") and item.get("status") == "pending":
                    item["status"] = "cancelled"
                    item["cancelledAt"] = task["completedAt"]
        elif not task.get("branchKind"):
            self._create_war_revival_branch_tasks(tribe, task, task["completedAt"])
        member = tribe.get("members", {}).get(player_id, {})
        reward_bits = [f"声望+{task.get('renownReward', TRIBE_WAR_REVIVAL_RENOWN)}"]
        if int(task.get("foodReward", 0) or 0):
            reward_bits.append(f"食物+{task.get('foodReward')}")
        if int(task.get("tradeReward", 0) or 0):
            reward_bits.append(f"贸易信誉+{task.get('tradeReward')}")
        if int(task.get("discoveryReward", 0) or 0):
            reward_bits.append(f"鍙戠幇杩涘害+{task.get('discoveryReward')}")
        if int(task.get("warPressure", 0) or 0):
            reward_bits.append(f"反击意志+{task.get('warPressure')}")
        detail = f"{member.get('name', '成员')} 完成{task.get('title', '战败复兴')}，消耗食物{food_cost}、木材{wood_cost}，{ '、'.join(reward_bits) }，缓解{relieved}名成员战疲。"
        self._add_tribe_history(tribe, "governance", "战败复兴", detail, player_id, {"kind": "war_revival", "revivalId": revival_id, "otherTribeId": other_tribe_id})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def resolve_war_diplomacy(self, player_id: str, diplomacy_id: str, action: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((
            item for item in (tribe.get("war_diplomacy_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") == diplomacy_id and item.get("status") == "pending"
        ), None)
        if not task:
            await self._send_tribe_error(player_id, "没有找到可处理的停战外交任务")
            return
        if action not in {"honor", "grievance"}:
            await self._send_tribe_error(player_id, "未知的停战外交选择")
            return
        other_tribe_id = task.get("otherTribeId")
        now_text = datetime.now().isoformat()
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        member = tribe.get("members", {}).get(player_id, {})
        if action == "honor":
            food_cost = int(task.get("foodCost", TRIBE_WAR_DIPLOMACY_FOOD_COST) or 0)
            if int(tribe.get("food", 0) or 0) < food_cost:
                await self._send_tribe_error(player_id, f"履行停战需要公共食物{food_cost}")
                return
            tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + int(task.get("renownReward", TRIBE_WAR_DIPLOMACY_RENOWN) or 0)
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + 1
            relation["score"] = min(8, int(relation.get("score", 0) or 0) + 2)
            relation["tradeTrust"] = min(10, int(relation.get("tradeTrust", 0) or 0) + 1)
            relation["warPressure"] = 0
            relation["canDeclareWar"] = False
            relation["lastAction"] = "formal_war_truce_honored"
            label = "履行停战"
            detail = f"{member.get('name', '成员')} 代表 {tribe.get('name', '部落')} 履行停战约定，消耗食物{food_cost}，关系与贸易信任回升。"
            other_tribe = self.tribes.get(other_tribe_id)
            if other_tribe and hasattr(self, "_open_covenant_messenger_task_pair"):
                self._open_covenant_messenger_task_pair(
                    tribe,
                    other_tribe,
                    "war_truce",
                    diplomacy_id,
                    "停战信使",
                    f"与 {task.get('otherTribeName', '邻近部落')} 的停战已经履约，需要成员把信物送过边界，让这段停战不只停在公告里。",
                    now_text
                )
                detail += " 新的停战信使已经出发，成员可继续护送信物巩固这段约定。"
        else:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + int(task.get("grievanceRenown", TRIBE_WAR_GRIEVANCE_RENOWN) or 0)
            relation["score"] = max(-9, int(relation.get("score", 0) or 0) - 1)
            relation["warPressure"] = min(TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD, int(relation.get("warPressure", 0) or 0) + 1)
            relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relation["lastAction"] = "formal_war_grievance"
            label = "停战追责"
            detail = f"{member.get('name', '成员')} 代表 {tribe.get('name', '部落')} 公开追责停战余怨，声望上升但边境仇怨保留。"
            if hasattr(self, "_open_tribe_atonement_task"):
                atonement = self._open_tribe_atonement_task(
                    tribe,
                    "truce_grievance",
                    "停战追责",
                    player_id,
                    other_tribe_id,
                    task.get("otherTribeName", "停战对象"),
                    diplomacy_id
                )
                if atonement:
                    detail += f" 部落也留下了“{atonement.get('title', '停战补誓')}”赎罪任务，之后可再修复这段停战。"
        relation["lastActionAt"] = now_text
        task["status"] = action
        task["completedBy"] = player_id
        task["completedAt"] = now_text
        self._create_war_aftermath_task(tribe, other_tribe_id, action, task, now_text)
        self._add_tribe_history(tribe, "governance", label, detail, player_id, {"kind": "war_diplomacy", "diplomacyId": diplomacy_id, "action": action, "otherTribeId": other_tribe_id})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_war_aftermath(self, player_id: str, aftermath_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((
            item for item in (tribe.get("war_aftermath_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") == aftermath_id and item.get("status") == "pending"
        ), None)
        if not task:
            await self._send_tribe_error(player_id, "没有找到可处理的战后余波任务")
            return
        food_cost = int(task.get("foodCost", 0) or 0)
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"处理战后余波需要公共食物{food_cost}")
            return
        tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        food_reward = int(task.get("foodReward", 0) or 0)
        trade_reward = int(task.get("tradeReward", 0) or 0)
        pressure_relief = int(task.get("pressureRelief", 0) or 0)
        renown_reward = int(task.get("renownReward", TRIBE_WAR_AFTERMATH_RENOWN) or 0)
        discovery_reward = int(task.get("discoveryReward", 0) or 0)
        tribe["food"] = int(tribe.get("food", 0) or 0) + food_reward
        tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_reward
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown_reward
        tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery_reward
        other_tribe_id = task.get("otherTribeId")
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        if task.get("kind") == "market":
            relation["score"] = min(9, int(relation.get("score", 0) or 0) + 1)
            relation["tradeTrust"] = min(10, int(relation.get("tradeTrust", 0) or 0) + trade_reward)
            relation["lastAction"] = "formal_war_aftermath_market"
        else:
            relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - pressure_relief)
            relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relation["lastAction"] = "formal_war_aftermath_watch"
        now_text = datetime.now().isoformat()
        relation["lastActionAt"] = now_text
        task["status"] = "completed"
        task["completedBy"] = player_id
        task["completedAt"] = now_text
        member = tribe.get("members", {}).get(player_id, {})
        reward_bits = [f"声望+{renown_reward}"]
        if food_reward:
            reward_bits.append(f"食物+{food_reward}")
        if trade_reward:
            reward_bits.append(f"贸易信誉+{trade_reward}")
        if pressure_relief:
            reward_bits.append(f"战争压力-{pressure_relief}")
        if discovery_reward:
            reward_bits.append(f"发现进度+{discovery_reward}")
        detail = f"{member.get('name', '成员')} 处理{task.get('title', '战后余波')}，消耗食物{food_cost}，{ '、'.join(reward_bits) }。"
        self._record_map_memory(
            tribe,
            "war_aftermath",
            f"{task.get('title', '战后余波')}旧痕",
            f"与{task.get('otherTribeName', '其他部落')}的战后余波曾在这里被整理，边界故事还可被后来者重读。",
            float(self.players.get(player_id, {}).get("x", 0) or 0),
            float(self.players.get(player_id, {}).get("z", 0) or 0),
            f"war_after:{aftermath_id}",
            member.get("name", "成员")
        )
        other_tribe = self.tribes.get(other_tribe_id)
        myth_source_id = f"war_after:{task.get('warId') or task.get('diplomacyId') or aftermath_id}"
        self._open_shared_myth_claim(
            [item for item in (tribe, other_tribe) if item],
            "war_aftermath",
            task.get("title", "战后余波"),
            f"与{task.get('otherTribeName', '其他部落')}的战后余波被整理后，双方族人都可以争论这段旧事该成为守边誓言、互市佳兆还是火种护佑。",
            float(self.players.get(player_id, {}).get("x", 0) or 0),
            float(self.players.get(player_id, {}).get("z", 0) or 0),
            myth_source_id,
            member.get("name", "成员")
        )
        self._add_tribe_history(tribe, "governance", "战后余波", detail, player_id, {"kind": "war_aftermath", "aftermathId": aftermath_id, "otherTribeId": other_tribe_id})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        if other_tribe and other_tribe_id != tribe_id:
            other_detail = f"{tribe.get('name', '邻近部落')} 整理了与本部相关的{task.get('title', '战后余波')}，这段旧事开始进入同源神话争夺。"
            self._add_tribe_history(other_tribe, "governance", "同源神话争夺", other_detail, player_id, {"kind": "shared_myth_claim", "sourceId": myth_source_id, "otherTribeId": tribe_id})
            await self._notify_tribe(other_tribe_id, other_detail)
            await self.broadcast_tribe_state(other_tribe_id)
        await self._broadcast_current_map()

    async def complete_war_ally_task(self, player_id: str, task_id: str, action: str = ""):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        task = next((
            item for item in (tribe.get("war_ally_tasks", []) or [])
            if isinstance(item, dict) and item.get("id") == task_id and item.get("status") == "pending"
        ), None)
        if not task:
            await self._send_tribe_error(player_id, "没有找到可处理的战盟后续任务")
            return
        kind = task.get("kind")
        if kind == "betrayal_reparation" and action and action != "repair":
            await self._send_tribe_error(player_id, "赔礼修复只能选择修复")
            return
        if kind == "betrayal_grievance" and action and action != "grievance":
            await self._send_tribe_error(player_id, "背刺追责只能选择追责")
            return
        food_cost = int(task.get("foodCost", 0) or 0)
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"处理战盟后续需要公共食物{food_cost}")
            return
        tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost
        food_reward = int(task.get("foodReward", 0) or 0)
        renown_reward = int(task.get("renownReward", 0) or 0)
        trade_reward = int(task.get("tradeReward", 0) or 0)
        war_pressure = int(task.get("warPressure", 0) or 0)
        pressure_relief = int(task.get("pressureRelief", 0) or 0)
        relation_delta = int(task.get("relationDelta", 0) or 0)
        trade_trust_delta = int(task.get("tradeTrustDelta", 0) or 0)
        tribe["food"] = int(tribe.get("food", 0) or 0) + food_reward
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown_reward
        tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_reward
        other_tribe_id = task.get("otherTribeId")
        relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
        relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
        relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trade_trust_delta))
        relation["warPressure"] = max(0, min(
            TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD,
            int(relation.get("warPressure", 0) or 0) + war_pressure - pressure_relief
        ))
        relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
        now_text = datetime.now().isoformat()
        relation["lastAction"] = f"formal_war_ally_{kind}"
        relation["lastActionAt"] = now_text
        task["status"] = "completed"
        task["completedBy"] = player_id
        task["completedAt"] = now_text
        member = tribe.get("members", {}).get(player_id, {})
        reward_bits = [f"声望+{renown_reward}"]
        if food_cost:
            reward_bits.append(f"食物-{food_cost}")
        if food_reward:
            reward_bits.append(f"食物+{food_reward}")
        if trade_reward:
            reward_bits.append(f"贸易信誉+{trade_reward}")
        if war_pressure:
            reward_bits.append(f"战争压力+{war_pressure}")
        if pressure_relief:
            reward_bits.append(f"战争压力-{pressure_relief}")
        detail = f"{member.get('name', '成员')} 完成{task.get('title', '战盟后续')}，{'、'.join(reward_bits)}。"
        self._add_tribe_history(tribe, "governance", "战盟后续", detail, player_id, {"kind": "war_ally_task", "taskId": task_id, "otherTribeId": other_tribe_id})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def start_small_conflict(self, player_id: str, outcome_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        outcome = next((
            item for item in tribe.get("boundary_outcomes", []) or []
            if isinstance(item, dict)
            and item.get("id") == outcome_id
            and item.get("status") == "pending"
        ), None)
        if not outcome:
            await self._send_tribe_error(player_id, "只能围绕待处理的边境争端发起小规模冲突")
            return
        if outcome.get("kind") != "resource_site_contest" and outcome.get("state") != "hostile":
            await self._send_tribe_error(player_id, "只有资源点争执或敌意边境可以升级为小规模冲突")
            return
        other_tribe_id = outcome.get("otherTribeId")
        other_tribe = self.tribes.get(other_tribe_id)
        if not other_tribe:
            await self._send_tribe_error(player_id, "对方部落已经不在这片边境")
            return

        if outcome.get("kind") == "resource_site_contest":
            own_target = self._small_conflict_scout_site(tribe, outcome.get("siteId"))
            other_target = self._small_conflict_scout_site(other_tribe, outcome.get("otherSiteId") or outcome.get("contestSiteId"))
            if not own_target:
                await self._send_tribe_error(player_id, "这处争夺资源点已经失效，无法继续集结")
                return
            target_kind = "resource_site"
            title = "资源点集结争夺"
            site_label = outcome.get("siteLabel") or outcome.get("title", "资源点")
            summary = f"围绕 {site_label} 的短时争夺已经开始，成员可报名参战。"
            own_target_id = outcome.get("siteId")
            other_target_id = outcome.get("otherSiteId") or outcome.get("contestSiteId")
        else:
            own_target = self._small_conflict_cave_target(tribe, other_tribe, outcome)
            other_target = self._small_conflict_cave_target(other_tribe, tribe, outcome) if own_target else None
            if own_target:
                target_kind = "cave_entrance"
                title = "洞口集结争夺"
                site_label = own_target.get("label") or "洞口"
                summary = f"{site_label} 的洞口路线成为双方争夺点，成员需要赶到洞口附近参战。"
                own_target_id = own_target.get("id")
                other_target_id = (other_target or own_target).get("id")
                outcome["caveId"] = own_target_id
                outcome["targetId"] = own_target_id
            else:
                own_target = self._small_conflict_boundary_target(tribe, other_tribe, outcome)
                other_target = self._small_conflict_boundary_target(other_tribe, tribe, outcome)
                if not own_target:
                    await self._send_tribe_error(player_id, "需要先在这条敌意边境插下旗帜，才能发起集结")
                    return
                target_kind = own_target.get("kind", "boundary_flag")
                title = "道路集结争夺" if target_kind == "boundary_road" else "旗帜集结争夺"
                site_label = own_target.get("label") or outcome.get("title", "边境")
                summary = f"{site_label} 的边境争执升级为短时集结，双方成员需要靠近己方目标参战。"
                own_target_id = own_target.get("id")
                other_target_id = (other_target or {}).get("id")
                outcome["targetId"] = own_target_id

        duplicate = self._small_conflict_duplicate(tribe, other_tribe, outcome)
        if duplicate:
            await self._send_tribe_error(player_id, "这场边境争端已经进入集结")
            return

        now_text = datetime.now().isoformat()
        active_until = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_SKIRMISH_ACTIVE_MINUTES * 60).isoformat()
        conflict_id = f"skirmish_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}"
        base = {
            "id": conflict_id,
            "kind": target_kind,
            "targetKind": target_kind,
            "status": "active",
            "outcomeId": outcome_id,
            "siteId": own_target_id,
            "otherSiteId": other_target_id,
            "x": float(own_target.get("x", 0) or 0),
            "z": float(own_target.get("z", 0) or 0),
            "siteLabel": site_label,
            "title": title,
            "summary": summary,
            "scoreTarget": TRIBE_SKIRMISH_SCORE_TARGET,
            "scores": {tribe_id: 0, other_tribe_id: 0},
            "participants": {},
            "createdBy": player_id,
            "createdAt": now_text,
            "activeUntil": active_until
        }
        own_record = {
            **base,
            "tribeId": tribe_id,
            "targetSiteId": own_target_id if target_kind == "resource_site" else None,
            "targetFlagId": own_target.get("flagId") if target_kind == "boundary_flag" else None,
            "targetRoadId": own_target_id if target_kind == "boundary_road" else None,
            "targetCaveId": own_target_id if target_kind == "cave_entrance" else None,
            "otherTribeId": other_tribe_id,
            "otherTribeName": other_tribe.get("name", "其他部落")
        }
        other_record = {
            **base,
            "tribeId": other_tribe_id,
            "targetSiteId": other_target_id if target_kind == "resource_site" else None,
            "targetFlagId": (other_target or {}).get("flagId") if target_kind == "boundary_flag" else None,
            "targetRoadId": other_target_id if target_kind == "boundary_road" else None,
            "targetCaveId": other_target_id if target_kind == "cave_entrance" else None,
            "siteId": other_target_id,
            "otherSiteId": own_target_id,
            "x": float((other_target or own_target).get("x", own_target.get("x", 0)) or 0),
            "z": float((other_target or own_target).get("z", own_target.get("z", 0)) or 0),
            "otherTribeId": tribe_id,
            "otherTribeName": tribe.get("name", "其他部落")
        }
        tribe.setdefault("small_conflicts", []).append(own_record)
        tribe["small_conflicts"] = tribe["small_conflicts"][-TRIBE_SKIRMISH_LIMIT:]
        other_tribe.setdefault("small_conflicts", []).append(other_record)
        other_tribe["small_conflicts"] = other_tribe["small_conflicts"][-TRIBE_SKIRMISH_LIMIT:]

        member = tribe.get("members", {}).get(player_id, {})
        detail = f"{member.get('name', '成员')} 将 {site_label} 升级为小规模集结，双方成员可以报名参战。"
        self._add_tribe_history(tribe, "governance", "发起小规模冲突", detail, player_id, {"kind": "small_conflict", "conflictId": conflict_id, "targetKind": target_kind})
        await self._notify_tribe(tribe_id, detail)
        await self._notify_tribe(other_tribe_id, f"{tribe.get('name', '其他部落')} 在边境发起小规模集结，你们可以报名回应。")
        await self.broadcast_tribe_state(tribe_id)
        await self.broadcast_tribe_state(other_tribe_id)

    async def resolve_small_conflict(self, player_id: str, conflict_id: str):
        tribe, conflict, other_tribe, other_conflict = self._find_small_conflict_pair(conflict_id)
        if not conflict or conflict.get("status") != "active":
            await self._send_tribe_error(player_id, "这场小规模冲突已经结束")
            return
        scores = dict(conflict.get("scores") or {})
        tribe_id = conflict.get("tribeId")
        other_tribe_id = conflict.get("otherTribeId")
        own_score = int(scores.get(tribe_id, 0) or 0)
        other_score = int(scores.get(other_tribe_id, 0) or 0)
        winner_id = tribe_id if own_score >= other_score else other_tribe_id
        loser_id = other_tribe_id if winner_id == tribe_id else tribe_id
        winner = self.tribes.get(winner_id)
        loser = self.tribes.get(loser_id)
        side_records = {
            item.get("tribeId"): item
            for item in (conflict, other_conflict)
            if isinstance(item, dict) and item.get("tribeId")
        }
        winner_record = side_records.get(winner_id) or conflict
        loser_record = side_records.get(loser_id) or other_conflict or conflict
        target_kind = winner_record.get("targetKind") or winner_record.get("kind")
        now_text = datetime.now().isoformat()
        for item in (conflict, other_conflict):
            if item:
                item["status"] = "resolved"
                item["winnerTribeId"] = winner_id
                item["resolvedAt"] = now_text

        site_result_parts = []
        if winner:
            winner["renown"] = int(winner.get("renown", 0) or 0) + TRIBE_SKIRMISH_RENOWN_REWARD
            if target_kind == "resource_site":
                winner["food"] = int(winner.get("food", 0) or 0) + TRIBE_SKIRMISH_FOOD_REWARD
                promoted = self._promote_small_conflict_winner_site(
                    winner,
                    winner_record.get("targetSiteId") or winner_record.get("siteId"),
                    player_id,
                    now_text
                )
                site_result_parts.append("胜方获得短期控制点" if promoted else "胜方控制时间延长")
            elif target_kind in {"boundary_flag", "boundary_road"}:
                site_result_parts.extend(self._apply_small_conflict_boundary_result(winner, loser, winner_record))
            elif target_kind == "cave_entrance":
                site_result_parts.extend(self._apply_small_conflict_cave_result(winner, loser, winner_record))
        if loser and target_kind == "resource_site":
            ceded = self._cede_small_conflict_loser_site(
                loser,
                loser_record.get("targetSiteId") or loser_record.get("siteId")
            )
            if ceded:
                site_result_parts.append("败方让渡相关资源点")

        for source_id, target_id, action in (
            (winner_id, loser_id, "small_conflict_won"),
            (loser_id, winner_id, "small_conflict_lost")
        ):
            target_tribe = self.tribes.get(source_id)
            if not target_tribe:
                continue
            progress = target_tribe.setdefault("boundary_relations", {}).setdefault(target_id, {})
            progress["score"] = max(-9, int(progress.get("score", 0) or 0) - 1)
            progress["lastAction"] = action
            progress["lastActionAt"] = now_text

        site_ids = {
            conflict.get("siteId"),
            conflict.get("otherSiteId"),
            conflict.get("targetSiteId"),
            conflict.get("targetFlagId"),
            conflict.get("targetRoadId"),
            conflict.get("targetCaveId"),
            (other_conflict or {}).get("siteId"),
            (other_conflict or {}).get("otherSiteId"),
            (other_conflict or {}).get("targetSiteId"),
            (other_conflict or {}).get("targetFlagId"),
            (other_conflict or {}).get("targetRoadId"),
            (other_conflict or {}).get("targetCaveId")
        }
        site_ids = {item for item in site_ids if item}
        if winner:
            self._mark_small_conflict_outcomes(winner, loser_id, site_ids, now_text)
        if loser:
            self._mark_small_conflict_outcomes(loser, winner_id, site_ids, now_text)
        self._record_small_conflict_war_pressure(winner_id, loser_id, winner_record, now_text)

        detail = f"{winner.get('name', '部落') if winner else '一方'} 在 {conflict.get('siteLabel', '争夺点')} 的小规模冲突中占上风，获得声望。"
        if site_result_parts:
            detail += " " + "，".join(site_result_parts) + "。"
        pressure = ((winner or {}).get("boundary_relations") or {}).get(loser_id, {}).get("warPressure", 0)
        if pressure >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD:
            detail += " 连续冲突已经积累到正式宣战条件。"

        for target_id in {tribe_id, other_tribe_id}:
            target = self.tribes.get(target_id)
            if target:
                self._add_tribe_history(target, "governance", "小规模冲突结算", detail, player_id, {"kind": "small_conflict", "conflictId": conflict_id, "winnerTribeId": winner_id, "targetKind": target_kind})
                await self._notify_tribe(target_id, detail)
                await self.broadcast_tribe_state(target_id)
        await self._broadcast_current_map()
