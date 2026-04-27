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
        detail = f"{member.get('name', '成员')} 发起“{plan['label']}”，把{target_label}标成迁徙季的部落行动点。"
        self._add_tribe_history(tribe, "governance", "迁徙季计划", detail, player_id, {"kind": "migration_plan", "plan": plan})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
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
            tribe.setdefault("migration_plan_history", []).append({**plan, "rewardParts": reward_parts})
            tribe["migration_plan_history"] = tribe["migration_plan_history"][-TRIBE_MIGRATION_PLAN_HISTORY_LIMIT:]
            tribe["migration_plan"] = plan
            detail = f"{tribe.get('name', '部落')} 完成“{plan.get('label', '迁徙计划')}”，迁徙季行动点被写入部落记忆。"
            if reward_parts:
                detail += f" 收获：{'、'.join(reward_parts)}。"
            self._record_map_memory(
                tribe,
                "migration_plan",
                f"{plan.get('siteLabel', '迁徙标记')}旧迹",
                f"{plan.get('label', '迁徙计划')}曾在{plan.get('targetLabel', '迁徙路线上')}被完成，后来者还能重读这段迁徙路线。",
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
