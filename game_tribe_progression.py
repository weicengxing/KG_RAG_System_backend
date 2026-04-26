import random
import math
from datetime import datetime
from typing import Optional

from game_config import *


class GameTribeProgressionMixin:
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

        report = {
            "id": f"scout_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "memberName": member.get("name", "成员"),
            "regionLabel": env["resourceTide"].get("regionLabel", "未知区域"),
            "eventTitles": [event.get("title", "世界事件") for event in env["worldEvents"][-TRIBE_SCOUT_EVENT_COUNT:]],
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("scout_reports", []).append(report)
        tribe["scout_reports"] = tribe["scout_reports"][-8:]

        map_data = self.maps.get(self.current_map_name) or {}
        map_data["environment"] = env
        map_data["updated_at"] = datetime.now().isoformat()
        detail = f"{report['memberName']} 派出侦察队，标记了{report['regionLabel']}的大地馈赠，并发现 {'、'.join(report['eventTitles'])}。"
        self._add_tribe_history(tribe, "world_event", "派出侦察", detail, player_id, {"kind": "scout", **report})
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "scout",
            "侦察标记",
            f"{tribe.get('name', '部落')} 派出侦察队，远方资源与事件被重新标记。",
            {"tribeId": tribe_id, "reportId": report["id"]}
        )
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

    def _current_oath_task(self, tribe: dict) -> Optional[dict]:
        oath = self._tribe_oath(tribe)
        if not oath:
            return None
        oath_key = oath.get("key")
        plan = TRIBE_OATH_TASK_REWARDS.get(oath_key)
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
            "reward": dict(plan),
            "completed": completed
        }

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
        if task.get("oathKey") == "beast" and int(tribe.get("tamed_beasts", 0) or 0) <= 0:
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
            "createdAt": datetime.now().isoformat()
        }
        detail = f"{record['memberName']} 完成誓约任务「{record['title']}」：{record['summary']} {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "governance", "完成誓约任务", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "oath",
            "誓约任务",
            f"{tribe.get('name', '部落')} 完成了{record['oathLabel']}的轻量目标：{record['title']}。",
            {"tribeId": tribe_id, "taskId": task["id"], "oathKey": task.get("oathKey")}
        )
        await self.broadcast_tribe_state(tribe_id)
