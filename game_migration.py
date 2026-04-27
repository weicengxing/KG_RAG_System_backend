from datetime import datetime

from game_config import *


class GameMigrationMixin:
    def _migration_environment(self) -> dict:
        map_data = self.maps.get(self.current_map_name) or {}
        return map_data.get("environment") or {}

    def _migration_season_context(self) -> dict | None:
        env = self._migration_environment()
        return self._active_migration_season(env)

    def _active_migration_plan(self, tribe: dict) -> dict | None:
        plan = tribe.get("migration_plan")
        if not isinstance(plan, dict) or plan.get("status") != "active":
            return None
        active_until = plan.get("activeUntil")
        if active_until:
            try:
                if datetime.fromisoformat(active_until) <= datetime.now():
                    plan["status"] = "expired"
                    plan["expiredAt"] = datetime.now().isoformat()
                    return None
            except (TypeError, ValueError):
                plan["status"] = "expired"
                plan["expiredAt"] = datetime.now().isoformat()
                return None
        return plan

    def _public_migration_plan_options(self, tribe: dict) -> dict:
        if self._active_migration_plan(tribe):
            return {}
        if not self._migration_season_context():
            return {}
        return {
            key: {
                **option,
                "rewardLabel": self._reward_summary_text(option.get("reward", {}))
            }
            for key, option in TRIBE_MIGRATION_PLAN_OPTIONS.items()
        }

    def _public_migration_plan(self, tribe: dict) -> dict | None:
        plan = self._active_migration_plan(tribe)
        if not plan:
            return None
        config = TRIBE_MIGRATION_PLAN_OPTIONS.get(plan.get("key"), {})
        return {
            "id": plan.get("id"),
            "key": plan.get("key"),
            "label": plan.get("label") or config.get("label", "迁徙计划"),
            "summary": plan.get("summary") or config.get("summary", ""),
            "siteLabel": plan.get("siteLabel") or config.get("siteLabel", "迁徙标记"),
            "siteType": plan.get("siteType") or config.get("siteType", "migration_site"),
            "x": plan.get("x", 0),
            "z": plan.get("z", 0),
            "progress": int(plan.get("progress", 0) or 0),
            "target": int(plan.get("target", TRIBE_MIGRATION_PLAN_PROGRESS_TARGET) or TRIBE_MIGRATION_PLAN_PROGRESS_TARGET),
            "participantNames": list(plan.get("participantNames", []) or [])[-5:],
            "rewardLabel": self._reward_summary_text(config.get("reward", {})),
            "createdAt": plan.get("createdAt"),
            "activeUntil": plan.get("activeUntil")
        }

    def _active_migration_encounters(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        changed = False
        for encounter in tribe.get("migration_encounters", []) or []:
            if not isinstance(encounter, dict):
                continue
            if encounter.get("status") != "pending":
                active.append(encounter)
                continue
            try:
                if datetime.fromisoformat(encounter.get("activeUntil", "")) <= now:
                    encounter["status"] = "expired"
                    encounter["expiredAt"] = now.isoformat()
                    changed = True
                    continue
            except (TypeError, ValueError):
                encounter["status"] = "expired"
                encounter["expiredAt"] = now.isoformat()
                changed = True
                continue
            active.append(encounter)
        if changed or len(active) != len(tribe.get("migration_encounters", []) or []):
            tribe["migration_encounters"] = active[-TRIBE_MIGRATION_ENCOUNTER_LIMIT:]
        return [
            item for item in active
            if item.get("status") == "pending"
        ][-TRIBE_MIGRATION_ENCOUNTER_LIMIT:]

    def _public_migration_encounters(self, tribe: dict) -> list:
        return [dict(item) for item in self._active_migration_encounters(tribe)]

    def _public_migration_encounter_records(self, tribe: dict) -> list:
        return list(tribe.get("migration_encounter_records", []) or [])[-TRIBE_MIGRATION_ENCOUNTER_RECORD_LIMIT:]

    def _active_migration_camp_traditions(self, tribe: dict) -> list:
        if not tribe:
            return []
        active = []
        now = datetime.now()
        for tradition in tribe.get("migration_camp_traditions", []) or []:
            if not isinstance(tradition, dict) or tradition.get("status", "active") != "active":
                continue
            active_until = tradition.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        tradition["status"] = "expired"
                        tradition["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    tradition["status"] = "expired"
                    tradition["expiredAt"] = now.isoformat()
                    continue
            active.append(tradition)
        tribe["migration_camp_traditions"] = active[-TRIBE_MIGRATION_PLAN_HISTORY_LIMIT:]
        return tribe["migration_camp_traditions"]

    def _public_migration_camp_traditions(self, tribe: dict) -> list:
        return [
            dict(tradition)
            for tradition in self._active_migration_camp_traditions(tribe)
        ]

    def _migration_tradition_profile(self, tribe: dict, plan: dict) -> dict:
        plan_key = plan.get("key")
        target_label = plan.get("targetLabel", "迁徙路线")
        if plan_key == "hold_camp":
            return {
                "key": "old_fire_legacy",
                "label": "旧火传承",
                "summary": "族人在迁徙季守住旧营火和仓库，新营地会把旧火、分粮和夜里守望当成传统。",
                "reward": {"renown": 2, "food": 2},
                "effectHint": "后续回归旧营、圣火接力和营地协作更容易引用这段旧火。"
            }
        if plan_key == "temporary_camp":
            label = "逐水而居" if any(word in str(target_label) for word in ("水", "潮", "岸", "溪", "河")) else "临营采种"
            return {
                "key": "water_dwelling" if label == "逐水而居" else "temporary_camp_seed",
                "label": label,
                "summary": f"族人在{target_label}旁扎下临时营点，新营地会记住水路、食物和短住营火的秩序。",
                "reward": {"discoveryProgress": 1, "food": 2},
                "effectHint": "后续雾区探路、采集和临时营点会更容易引用这段住营方法。"
            }
        if plan_key == "caravan" and (tribe.get("forbidden_edge_route_proof_records") or tribe.get("forbidden_edge_records")):
            return {
                "key": "forbidden_watch",
                "label": "禁地守望",
                "summary": "迁徙车队从高风险边缘和路证旁经过，新营地会把绕行、守望和归线讲成规矩。",
                "reward": {"renown": 2, "discoveryProgress": 1},
                "effectHint": "后续禁地边缘、洞穴营救和路证引用会更容易获得来源。"
            }
        return {
            "key": "border_route_market",
            "label": "边路商营",
            "summary": f"迁徙车队沿{target_label}公开远行，新营地会把边路互市、护送和口信当成传统。",
            "reward": {"tradeReputation": 1, "renown": 1},
            "effectHint": "后续商队、边界来访和客居会更容易引用这段迁徙车队路线。"
        }

    def _create_migration_camp_tradition(self, tribe: dict, plan: dict, member_name: str) -> dict:
        profile = self._migration_tradition_profile(tribe, plan)
        now = datetime.now()
        reward_parts = self._apply_migration_reward(tribe, profile.get("reward", {}))
        source_chain = [
            plan.get("label", "迁徙计划"),
            plan.get("siteLabel", "迁徙标记"),
            plan.get("targetLabel", "迁徙路线")
        ]
        tradition = {
            "id": f"migration_tradition_{tribe.get('id')}_{profile.get('key')}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "key": profile.get("key"),
            "label": profile.get("label", "新营地传统"),
            "summary": profile.get("summary", ""),
            "effectHint": profile.get("effectHint", ""),
            "planId": plan.get("id"),
            "planKey": plan.get("key"),
            "planLabel": plan.get("label", "迁徙计划"),
            "siteLabel": plan.get("siteLabel", "迁徙标记"),
            "targetLabel": plan.get("targetLabel", "迁徙路线"),
            "participantNames": list(plan.get("participantNames", []) or [])[-5:],
            "sourceChain": [item for item in source_chain if item],
            "rewardParts": reward_parts,
            "createdByName": member_name,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_MIGRATION_PLAN_ACTIVE_MINUTES * 3 * 60).isoformat()
        }
        active = [
            item for item in self._active_migration_camp_traditions(tribe)
            if item.get("key") != tradition.get("key")
        ]
        tribe["migration_camp_traditions"] = [*active, tradition][-TRIBE_MIGRATION_PLAN_HISTORY_LIMIT:]
        return tradition

    def _migration_plan_position(self, tribe: dict, plan_key: str) -> tuple[float, float, str]:
        env = self._migration_environment()
        camp_center = (tribe.get("camp") or {}).get("center") or {}
        camp_x = float(camp_center.get("x", 0) or 0)
        camp_z = float(camp_center.get("z", 0) or 0)
        if plan_key == "hold_camp":
            return camp_x, camp_z, "旧营地"

        objective = env.get("seasonObjective") if isinstance(env.get("seasonObjective"), dict) else None
        tide = env.get("resourceTide") if isinstance(env.get("resourceTide"), dict) else None
        target = objective or tide or {}
        target_x = float(target.get("x", camp_x + 10) or camp_x + 10)
        target_z = float(target.get("z", camp_z + 6) or camp_z + 6)
        target_label = target.get("title") or target.get("regionLabel") or "迁徙路线"

        if plan_key == "caravan":
            return round((camp_x + target_x) / 2, 2), round((camp_z + target_z) / 2, 2), target_label
        return target_x, target_z, target_label

    def _apply_migration_reward(self, tribe: dict, reward: dict) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = max(0, int(storage.get(key, 0) or 0) + amount)
                reward_parts.append(f"{label}+{amount}")
        food = int((reward or {}).get("food", 0) or 0)
        if food:
            tribe["food"] = max(0, int(tribe.get("food", 0) or 0) + food)
            reward_parts.append(f"食物+{food}")
        discovery = int((reward or {}).get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        trade = int((reward or {}).get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        renown = int((reward or {}).get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        return reward_parts

    def _migration_encounter_context(self, source: dict, responder: dict, plan: dict) -> dict:
        source_id = source.get("id")
        responder_id = responder.get("id")
        relation = (source.get("boundary_relations", {}) or {}).get(responder_id) or (responder.get("boundary_relations", {}) or {}).get(source_id) or {}
        if relation:
            return {"key": "boundary", "label": "边界路口", "summary": "车队擦过两部落边界，边界口风会记住这次选择。"}
        trade_sites = self._active_trade_route_sites(source) if hasattr(self, "_active_trade_route_sites") else []
        if trade_sites:
            site = trade_sites[-1]
            return {"key": "trade_route", "label": site.get("label", "商队旧路"), "summary": "车队借着商队路线经过，互市和路闻都会放大后果。"}
        if (source.get("forbidden_edges") or []) or (source.get("forbidden_edge_route_proofs") or []):
            return {"key": "forbidden", "label": "禁地边缘", "summary": "车队绕过禁地或危险路证，护送与收费都会留下更重的证据。"}
        return {"key": "open_route", "label": "荒路相逢", "summary": "车队从荒路经过，邻近部落仍可选择帮忙或把消息传开。"}

    def _ensure_migration_caravan_encounters(self, source_tribe: dict, plan: dict) -> list:
        if not source_tribe or plan.get("key") != "caravan":
            return []
        now = datetime.now()
        created = []
        source_id = source_tribe.get("id")
        existing_keys = set()
        for tribe in self.tribes.values():
            for encounter in self._active_migration_encounters(tribe):
                existing_keys.add((encounter.get("sourceTribeId"), encounter.get("planId"), encounter.get("responderTribeId")))
        for responder_id, responder in self.tribes.items():
            if not responder_id or responder_id == source_id or not responder.get("members"):
                continue
            marker = (source_id, plan.get("id"), responder_id)
            if marker in existing_keys:
                continue
            context = self._migration_encounter_context(source_tribe, responder, plan)
            encounter = {
                "id": f"migration_encounter_{source_id}_{responder_id}_{int(now.timestamp() * 1000)}",
                "status": "pending",
                "type": "migration_encounter",
                "planId": plan.get("id"),
                "planKey": plan.get("key"),
                "planLabel": plan.get("label", "迁徙车队"),
                "sourceTribeId": source_id,
                "sourceTribeName": source_tribe.get("name", "迁徙部落"),
                "responderTribeId": responder_id,
                "responderTribeName": responder.get("name", "邻近部落"),
                "contextKey": context.get("key"),
                "contextLabel": context.get("label"),
                "summary": context.get("summary"),
                "x": plan.get("x", 0),
                "z": plan.get("z", 0),
                "createdAt": now.isoformat(),
                "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_MIGRATION_ENCOUNTER_ACTIVE_MINUTES * 60).isoformat()
            }
            responder.setdefault("migration_encounters", []).append(encounter)
            responder["migration_encounters"] = responder["migration_encounters"][-TRIBE_MIGRATION_ENCOUNTER_LIMIT:]
            created.append(encounter)
        return created

    def _apply_migration_relation_delta(self, responder: dict, source: dict, action: dict, now_text: str) -> list:
        parts = []
        responder_id = responder.get("id")
        source_id = source.get("id")
        relation_delta = int(action.get("relationDelta", 0) or 0)
        trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
        pressure_delta = int(action.get("warPressureDelta", 0) or 0)
        for own, other_id in ((responder, source_id), (source, responder_id)):
            relation = own.setdefault("boundary_relations", {}).setdefault(other_id, {})
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            if pressure_delta:
                relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) + pressure_delta)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relation["lastAction"] = "migration_encounter"
            relation["lastActionAt"] = now_text
        if relation_delta:
            parts.append(f"关系{relation_delta:+d}")
        if trust_delta:
            parts.append(f"信任+{trust_delta}")
        if pressure_delta:
            parts.append(f"战争压力+{pressure_delta}")
        return parts

    async def start_migration_plan(self, player_id: str, plan_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以发起迁徙计划")
            return
        migration = self._migration_season_context()
        if not migration:
            await self._send_tribe_error(player_id, "当前还没有迁徙季节")
            return
        if self._active_migration_plan(tribe):
            await self._send_tribe_error(player_id, "部落已经有迁徙计划在进行")
            return
        config = TRIBE_MIGRATION_PLAN_OPTIONS.get(plan_key)
        if not config:
            await self._send_tribe_error(player_id, "未知的迁徙计划")
            return

        now = datetime.now()
        x, z, target_label = self._migration_plan_position(tribe, plan_key)
        plan = {
            "id": f"migration_plan_{tribe_id}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "key": plan_key,
            "label": config.get("label", "迁徙计划"),
            "summary": config.get("summary", ""),
            "siteLabel": config.get("siteLabel", "迁徙标记"),
            "siteType": config.get("siteType", "migration_site"),
            "x": x,
            "z": z,
            "targetLabel": target_label,
            "progress": 0,
            "target": TRIBE_MIGRATION_PLAN_PROGRESS_TARGET,
            "participantIds": [],
            "participantNames": [],
            "createdBy": player_id,
            "createdByName": member.get("name", "成员"),
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_MIGRATION_PLAN_ACTIVE_MINUTES * 60).isoformat(),
            "migrationSeasonId": migration.get("id")
        }
        tribe["migration_plan"] = plan
        tribe.setdefault("migration_plan_history", []).append({**plan, "status": "started"})
        tribe["migration_plan_history"] = tribe["migration_plan_history"][-TRIBE_MIGRATION_PLAN_HISTORY_LIMIT:]
        encounters = self._ensure_migration_caravan_encounters(tribe, plan)
        detail = f"{member.get('name', '成员')} 发起“{plan['label']}”，把{target_label}标成迁徙季的部落行动点。"
        if encounters:
            detail += f" 车队经过{len(encounters)}处他部落路口，等待邻近部落回应。"
        self._add_tribe_history(tribe, "governance", "迁徙季计划", detail, player_id, {"kind": "migration_plan", "plan": plan})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        for encounter in encounters:
            self._add_tribe_history(
                self.tribes.get(encounter.get("responderTribeId"), {}),
                "diplomacy",
                "迁徙车队过境",
                f"{tribe.get('name', '迁徙部落')} 的车队经过{encounter.get('contextLabel', '边路')}，可以选择护送、收留、收费或传播路闻。",
                "",
                {"kind": "migration_encounter", "encounter": encounter}
            )
            await self._notify_tribe(encounter.get("responderTribeId"), f"{tribe.get('name', '迁徙部落')} 的迁徙车队经过{encounter.get('contextLabel', '边路')}。")
            await self.broadcast_tribe_state(encounter.get("responderTribeId"))
        if hasattr(self, "_broadcast_current_map"):
            await self._broadcast_current_map()

    async def advance_migration_plan(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        plan = self._active_migration_plan(tribe)
        if not plan:
            await self._send_tribe_error(player_id, "当前没有可推进的迁徙计划")
            return
        if player_id in (plan.get("participantIds", []) or []):
            await self._send_tribe_error(player_id, "你已经参与过这次迁徙计划")
            return
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        plan.setdefault("participantIds", []).append(player_id)
        plan.setdefault("participantNames", []).append(member_name)
        plan["progress"] = int(plan.get("progress", 0) or 0) + 1
        target = int(plan.get("target", TRIBE_MIGRATION_PLAN_PROGRESS_TARGET) or TRIBE_MIGRATION_PLAN_PROGRESS_TARGET)
        detail = f"{member_name} 推进“{plan.get('label', '迁徙计划')}”，进度 {plan['progress']} / {target}。"

        if plan["progress"] >= target:
            config = TRIBE_MIGRATION_PLAN_OPTIONS.get(plan.get("key"), {})
            reward_parts = self._apply_migration_reward(tribe, config.get("reward", {}))
            plan["status"] = "completed"
            plan["completedAt"] = datetime.now().isoformat()
            plan["completedBy"] = player_id
            tradition = self._create_migration_camp_tradition(tribe, plan, member_name)
            plan["campTradition"] = tradition
            reward_parts.extend(tradition.get("rewardParts", []))
            tribe.setdefault("migration_plan_history", []).append({**plan, "rewardParts": reward_parts})
            tribe["migration_plan_history"] = tribe["migration_plan_history"][-TRIBE_MIGRATION_PLAN_HISTORY_LIMIT:]
            tribe["migration_plan"] = plan
            detail = f"{tribe.get('name', '部落')} 完成“{plan.get('label', '迁徙计划')}”，迁徙季行动点被写入部落记忆。"
            if reward_parts:
                detail += f" 收获：{'、'.join(reward_parts)}。"
            detail += f" 新营地传统形成：“{tradition.get('label', '新营地传统')}”。"
            self._record_map_memory(
                tribe,
                "migration_plan",
                f"{plan.get('siteLabel', '迁徙标记')}旧迹",
                f"{plan.get('label', '迁徙计划')}曾在{plan.get('targetLabel', '迁徙路线上')}被完成，后来者还能重读这段迁徙路线，并听见{tradition.get('label', '新营地传统')}的说法。",
                float(plan.get("x", 0) or 0),
                float(plan.get("z", 0) or 0),
                f"migration:{plan.get('id')}",
                member_name
            )
            await self._publish_world_rumor(
                "migration",
                "迁徙季计划完成",
                detail,
                {"tribeId": tribe_id, "planId": plan.get("id"), "planKey": plan.get("key")}
            )
        self._add_tribe_history(tribe, "governance", "迁徙季计划", detail, player_id, {"kind": "migration_plan_progress", "planId": plan.get("id"), "progress": plan.get("progress")})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        if hasattr(self, "_broadcast_current_map"):
            await self._broadcast_current_map()

    async def respond_migration_encounter(self, player_id: str, encounter_id: str, action_key: str):
        responder_id = self.player_tribes.get(player_id)
        responder = self.tribes.get(responder_id)
        if not responder:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        encounter = next((item for item in self._active_migration_encounters(responder) if item.get("id") == encounter_id), None)
        if not encounter:
            await self._send_tribe_error(player_id, "这支迁徙车队已经离开")
            return
        action = TRIBE_MIGRATION_ENCOUNTER_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知迁徙车队回应")
            return
        food_cost = int(action.get("foodCost", 0) or 0)
        if food_cost and int(responder.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"{action.get('label', '回应车队')}需要公共食物 {food_cost}")
            return
        source_id = encounter.get("sourceTribeId")
        source = self.tribes.get(source_id)
        if not source:
            await self._send_tribe_error(player_id, "车队来源已经不可用")
            return

        now_text = datetime.now().isoformat()
        if food_cost:
            responder["food"] = max(0, int(responder.get("food", 0) or 0) - food_cost)
        responder_parts = [f"食物-{food_cost}"] if food_cost else []
        responder_parts.extend(self._apply_migration_reward(responder, action.get("responderReward", {})))
        source_parts = self._apply_migration_reward(source, action.get("sourceReward", {}))
        relation_parts = self._apply_migration_relation_delta(responder, source, action, now_text)
        member = responder.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        encounter["status"] = "resolved"
        encounter["resolvedAt"] = now_text
        encounter["resolvedBy"] = player_id
        encounter["resolvedByName"] = member_name
        encounter["actionKey"] = action_key
        encounter["actionLabel"] = action.get("label", "回应车队")
        encounter["responderRewardParts"] = responder_parts
        encounter["sourceRewardParts"] = source_parts
        encounter["relationParts"] = relation_parts
        record = dict(encounter)
        responder.setdefault("migration_encounter_records", []).append(record)
        responder["migration_encounter_records"] = responder["migration_encounter_records"][-TRIBE_MIGRATION_ENCOUNTER_RECORD_LIMIT:]
        source.setdefault("migration_encounter_records", []).append({**record, "direction": "source"})
        source["migration_encounter_records"] = source["migration_encounter_records"][-TRIBE_MIGRATION_ENCOUNTER_RECORD_LIMIT:]

        detail = f"{member_name} 对 {source.get('name', '迁徙部落')} 的{encounter.get('planLabel', '迁徙车队')}选择“{action.get('label', '回应')}”：{'、'.join(responder_parts + relation_parts) or '留下路闻'}。"
        source_detail = f"{responder.get('name', '邻近部落')} 对迁徙车队选择“{action.get('label', '回应')}”：{'、'.join(source_parts + relation_parts) or '路线被记下'}。"
        self._add_tribe_history(responder, "diplomacy", "迁徙车队回应", detail, player_id, {"kind": "migration_encounter_resolved", "record": record})
        self._add_tribe_history(source, "governance", "迁徙车队过境", source_detail, "", {"kind": "migration_encounter_resolved", "record": record})
        await self._publish_world_rumor(
            "migration",
            "迁徙车队过境",
            f"{responder.get('name', '邻近部落')} 在{encounter.get('contextLabel', '边路')}对 {source.get('name', '迁徙部落')} 的车队选择“{action.get('label', '回应')}”。",
            {"tribeId": responder_id, "sourceTribeId": source_id, "encounterId": encounter_id, "action": action_key}
        )
        await self._notify_tribe(responder_id, detail)
        await self._notify_tribe(source_id, source_detail)
        await self.broadcast_tribe_state(responder_id)
        await self.broadcast_tribe_state(source_id)
