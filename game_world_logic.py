import asyncio
import logging
import math
import random
from datetime import datetime
from typing import List, Optional

from game_config import *

logger = logging.getLogger("game_server")


class GameWorldLogicMixin:
    def _generate_default_decorations(
        self,
        seed: int,
        tree_count: int = 250,
        rock_count: int = 120,
        radius: float = 90.0
    ) -> List[dict]:
        rng = random.Random(seed)
        decorations: List[dict] = []

        for i in range(tree_count):
            decorations.append({
                "id": f"tree_{i}",
                "type": "tree",
                "x": (rng.random() - 0.5) * (radius * 2),
                "z": (rng.random() - 0.5) * (radius * 2),
                "y": 0,
                "size": rng.random() * 0.7 + 0.85,
                "trunkColor": rng.choice([0x7a4a1f, 0x6b3f1a, 0x8b5a2b]),
                "foliageColor": rng.choice([0x1f7a2e, 0x228b22, 0x2e8b57])
            })

        for i in range(rock_count):
            decorations.append({
                "id": f"rock_{i}",
                "type": "rock",
                "x": (rng.random() - 0.5) * (radius * 2),
                "z": (rng.random() - 0.5) * (radius * 2),
                "y": 0,
                "size": rng.random() * 0.9 + 0.6,
                "color": rng.choice([0x6f6f6f, 0x7b7b7b, 0x888888])
            })

        for i in range(140):
            decorations.append({
                "id": f"grass_{i}",
                "type": "grass",
                "x": (rng.random() - 0.5) * (radius * 2),
                "z": (rng.random() - 0.5) * (radius * 2),
                "y": 0,
                "color": rng.choice([0x4f9f3c, 0x5fa645, 0x6aa84f])
            })

        for i in range(56):
            decorations.append({
                "id": f"flower_{i}",
                "type": "flower",
                "x": (rng.random() - 0.5) * (radius * 1.85),
                "z": (rng.random() - 0.5) * (radius * 1.85),
                "y": 0,
                "color": rng.choice([0xf4d35e, 0xff8fab, 0x80ed99, 0xbdb2ff])
            })

        forest = next((region for region in WORLD_REGIONS if region["id"] == "region_forest_0"), None)
        if forest:
            for i in range(70):
                angle = rng.random() * math.pi * 2
                distance = math.sqrt(rng.random()) * forest["radius"]
                decorations.append({
                    "id": f"forest_tree_{i}",
                    "type": "tree",
                    "x": forest["x"] + math.cos(angle) * distance,
                    "z": forest["z"] + math.sin(angle) * distance,
                    "y": 0,
                    "size": rng.random() * 0.55 + 1.0,
                    "trunkColor": rng.choice([0x6b3f1a, 0x7a4a1f]),
                    "foliageColor": rng.choice([0x1f7a2e, 0x2e8b57, 0x3a9d46])
                })

        mountain = next((region for region in WORLD_REGIONS if region["id"] == "region_mountain_0"), None)
        if mountain:
            for i in range(46):
                angle = rng.random() * math.pi * 2
                distance = math.sqrt(rng.random()) * mountain["radius"]
                decorations.append({
                    "id": f"mountain_rock_{i}",
                    "type": "rock",
                    "x": mountain["x"] + math.cos(angle) * distance,
                    "z": mountain["z"] + math.sin(angle) * distance,
                    "y": 0,
                    "size": rng.random() * 0.8 + 0.85,
                    "color": rng.choice([0x686868, 0x787878, 0x8a8178])
                })

        coast = next((region for region in WORLD_REGIONS if region["id"] == "region_coast_0"), None)
        if coast:
            for i in range(42):
                angle = rng.random() * math.pi * 2
                distance = math.sqrt(rng.random()) * coast["radius"]
                decorations.append({
                    "id": f"coast_grass_{i}",
                    "type": "grass",
                    "x": coast["x"] + math.cos(angle) * distance,
                    "z": coast["z"] + math.sin(angle) * distance,
                    "y": 0,
                    "color": rng.choice([0x7aa65a, 0x8ab661, 0x6b9f54])
                })

        landmarks = [
            ("tribe_totem", "tribe_totem_0", 0, 0, 1.0, "公共部落图腾"),
            ("campfire", "campfire_0", 18, -16, 1.0, "林间营火"),
            ("ruin", "ruin_0", -38, 24, 1.0, "旧石遗迹"),
            ("crystal", "crystal_0", 44, 38, 1.1, "蓝晶石柱"),
            ("campfire", "campfire_1", -18, -42, 0.9, "海风营地"),
            ("crystal", "crystal_1", 6, 56, 0.85, "北岸晶簇"),
            ("cave_entrance", "cave_entrance_0", -72, 66, 1.15, "熊骨山洞")
        ]
        for entity_type, entity_id, x, z, size, label in landmarks:
            decoration = {
                "id": entity_id,
                "type": entity_type,
                "x": x,
                "z": z,
                "y": 0,
                "size": size,
                "label": label
            }
            if entity_type == "crystal":
                decoration["color"] = rng.choice([0x65d6ff, 0x8be9fd, 0x9bdbff])
            decorations.append(decoration)

        return decorations

    def _generate_default_environment(self, seed: int) -> dict:
        rng = random.Random(seed + 999)

        weather = rng.choice(WEATHER_TYPES)
        sea_level = -0.8
        shore_radius = DEFAULT_SHORE_RADIUS

        mountains: List[dict] = []
        mountain_count = 18
        ring_radius = 120.0
        for i in range(mountain_count):
            angle = (i / mountain_count) * 6.283185307179586
            jitter = (rng.random() - 0.5) * 10.0
            x = (ring_radius + jitter) * math.cos(angle)
            z = (ring_radius + jitter) * math.sin(angle)
            mountains.append({
                "id": f"mountain_{i}",
                "type": "mountain",
                "x": x,
                "z": z,
                "y": 0,
                "radius": rng.random() * 8 + 10,
                "height": rng.random() * 25 + 18
            })

        return {
            "seaLevel": sea_level,
            "weather": weather,
            "shoreRadius": shore_radius,
            "regions": [dict(region) for region in WORLD_REGIONS],
            "landmarks": [
                *[
                    {
                        "id": region["id"],
                        "label": region["label"],
                        "x": region["x"],
                        "z": region["z"],
                        "type": region["type"],
                        "radius": region["radius"],
                        "summary": region["summary"]
                    }
                    for region in WORLD_REGIONS
                ],
                {"id": "tribe_totem_0", "label": "公共部落图腾", "x": 0, "z": 0, "type": "tribe_totem"},
                {"id": "campfire_0", "label": "林间营火", "x": 18, "z": -16, "type": "campfire"},
                {"id": "ruin_0", "label": "旧石遗迹", "x": -38, "z": 24, "type": "ruin"},
                {"id": "crystal_0", "label": "蓝晶石柱", "x": 44, "z": 38, "type": "crystal"},
                {"id": "campfire_1", "label": "海风营地", "x": -18, "z": -42, "type": "campfire"},
                {"id": "crystal_1", "label": "北岸晶簇", "x": 6, "z": 56, "type": "crystal"},
                {"id": "cave_entrance_0", "label": "熊骨山洞", "x": -72, "z": 66, "type": "cave_entrance"}
            ],
            "mountains": mountains
        }

    def _rotate_offset(self, dx: float, dz: float, angle: float):
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return (
            dx * cos_a - dz * sin_a,
            dx * sin_a + dz * cos_a
        )

    def _pick_available_camp_slot(self) -> dict:
        used_indices = {
            tribe.get("camp", {}).get("slotIndex")
            for tribe in self.tribes.values()
            if isinstance(tribe.get("camp"), dict)
        }
        for index, slot in enumerate(TRIBE_CAMP_SLOTS):
            if index not in used_indices:
                return {"slotIndex": index, **slot}

        overflow_index = len(self.tribes)
        angle = (overflow_index % 8) * (math.pi / 4)
        radius = 56 + (overflow_index // 8) * 12
        return {
            "slotIndex": overflow_index,
            "x": math.cos(angle) * radius,
            "z": math.sin(angle) * radius,
            "angle": angle,
            "label": f"远岸营地 {overflow_index + 1}"
        }

    def _tribe_building_layout_by_key(self, building_key: str) -> Optional[dict]:
        for layout in TRIBE_CAMP_BUILDING_LAYOUT:
            if layout.get("key") == building_key:
                return layout
        return None

    def _tribe_building_label(self, tribe_name: str, layout: dict) -> str:
        building_type = layout.get("type")
        if building_type == "tribe_totem":
            return f"{tribe_name}图腾"
        if building_type == "tribe_storage":
            return f"{tribe_name}仓库"
        if building_type == "tribe_workbench":
            return f"{tribe_name}石器台"
        if building_type == "tribe_hut":
            return f"{tribe_name}{layout.get('label', '棚屋')}"
        if building_type == "campfire":
            return f"{tribe_name}营火"
        return f"{tribe_name}{layout.get('label', '建筑')}"

    def _make_tribe_building(self, tribe: dict, layout: dict) -> dict:
        camp = tribe.get("camp") or {}
        center = camp.get("center") or {"x": 0, "z": 0}
        angle = float(camp.get("angle", 0.0) or 0.0)
        offset_x, offset_z = self._rotate_offset(layout["dx"], layout["dz"], angle)
        tribe_id = tribe.get("id")
        tribe_name = tribe.get("name", "部落")
        return {
            "id": f"{tribe_id}_{layout['key']}",
            "tribeId": tribe_id,
            "key": layout["key"],
            "type": layout["type"],
            "x": round(float(center.get("x", 0)) + offset_x, 2),
            "z": round(float(center.get("z", 0)) + offset_z, 2),
            "y": 0,
            "size": layout.get("size", 1.0),
            "label": self._tribe_building_label(tribe_name, layout)
        }

    def _is_tribe_building_built(self, tribe: dict, building_key: str) -> bool:
        tribe_id = tribe.get("id")
        expected_id = f"{tribe_id}_{building_key}"
        for building in tribe.get("camp", {}).get("buildings", []):
            if building.get("key") == building_key or building.get("id") == expected_id:
                return True
        return False

    def _get_tribe_build_options(self, tribe: dict) -> List[dict]:
        storage = tribe.get("storage", {}) or {}
        options = []
        for layout in TRIBE_CAMP_BUILDING_LAYOUT:
            if layout.get("initial"):
                continue
            cost = self._tribe_building_cost(tribe, layout)
            required_wood = cost["wood"]
            required_stone = cost["stone"]
            built = self._is_tribe_building_built(tribe, layout["key"])
            options.append({
                "key": layout["key"],
                "type": layout["type"],
                "label": layout.get("label") or self._tribe_building_label(tribe.get("name", "部落"), layout),
                "wood": required_wood,
                "stone": required_stone,
                "baseWood": cost["baseWood"],
                "baseStone": cost["baseStone"],
                "woodDiscountPercent": cost["woodDiscountPercent"],
                "stoneDiscountPercent": cost["stoneDiscountPercent"],
                "built": built,
                "affordable": not built and int(storage.get("wood", 0) or 0) >= required_wood and int(storage.get("stone", 0) or 0) >= required_stone
            })
        return options

    def _build_tribe_camp(self, tribe_id: str, tribe_name: str) -> dict:
        slot = self._pick_available_camp_slot()
        camp = {
            "id": f"{tribe_id}_camp",
            "slotIndex": slot["slotIndex"],
            "label": slot["label"],
            "center": {
                "x": float(slot["x"]),
                "z": float(slot["z"]),
                "y": 0
            },
            "spawn": {
                "x": float(slot["x"]),
                "z": float(slot["z"] - 6.5),
                "y": 2
            },
            "angle": float(slot.get("angle", 0.0)),
            "radius": 12.0,
            "buildings": []
        }

        for layout in TRIBE_CAMP_BUILDING_LAYOUT:
            offset_x, offset_z = self._rotate_offset(layout["dx"], layout["dz"], camp["angle"])
            building = {
                "id": f"{tribe_id}_{layout['key']}",
                "tribeId": tribe_id,
                "key": layout["key"],
                "type": layout["type"],
                "x": round(camp["center"]["x"] + offset_x, 2),
                "z": round(camp["center"]["z"] + offset_z, 2),
                "y": 0,
                "size": layout.get("size", 1.0),
                "label": f"{tribe_name}{'图腾' if layout['type'] == 'tribe_totem' else ''}".strip()
            }

            if layout["type"] == "tribe_totem":
                building["label"] = f"{tribe_name}图腾"
            elif layout["type"] == "tribe_storage":
                building["label"] = f"{tribe_name}仓库"
            elif layout["type"] == "tribe_workbench":
                building["label"] = f"{tribe_name}石器台"
            elif layout["type"] == "tribe_hut":
                building["label"] = f"{tribe_name}棚屋"
            elif layout["type"] == "campfire":
                building["label"] = f"{tribe_name}营火"

            if layout.get("initial"):
                camp["buildings"].append(building)

        return camp

    def _is_tribe_decoration(self, decoration: dict) -> bool:
        if not isinstance(decoration, dict):
            return False
        decoration_type = decoration.get("type")
        return bool(decoration.get("tribeId")) or decoration_type in {
            "tribe_totem",
            "tribe_storage",
            "tribe_workbench",
            "tribe_hut"
        }

    def _get_base_decorations(self, map_name: Optional[str] = None) -> List[dict]:
        name = map_name or self.current_map_name
        map_data = self.maps.get(name) or {}
        decorations = map_data.get("decorations") or []
        if not isinstance(decorations, list):
            return []
        return [item for item in decorations if not self._is_tribe_decoration(item)]

    def _get_base_landmarks(self, map_name: Optional[str] = None) -> List[dict]:
        name = map_name or self.current_map_name
        map_data = self.maps.get(name) or {}
        environment = map_data.get("environment") or {}
        landmarks = environment.get("landmarks") or []
        if not isinstance(landmarks, list):
            return []
        return [item for item in landmarks if not self._is_tribe_decoration(item)]

    def _get_dynamic_tribe_decorations(self) -> List[dict]:
        decorations: List[dict] = []
        for tribe in self.tribes.values():
            camp = tribe.get("camp") or {}
            buildings = camp.get("buildings") or []
            for building in buildings:
                decorations.append(dict(building))
            for flag in tribe.get("territory_flags", []) or []:
                if isinstance(flag, dict):
                    decorations.append(dict(flag))
            beast_marker = self._tribe_beast_marker(tribe)
            if beast_marker:
                decorations.append(beast_marker)
        return decorations

    def _tribe_beast_marker(self, tribe: dict) -> Optional[dict]:
        if int(tribe.get("tamed_beasts", 0) or 0) <= 0:
            return None
        specialty = tribe.get("beast_specialty") or "young"
        camp = tribe.get("camp") or {}
        center = camp.get("center") or {}
        if not center:
            return None
        offsets = {
            "guardian": (2.6, -2.6),
            "hunter": (-2.8, -2.2),
            "carrier": (0.4, 3.2),
            "young": (2.2, 2.2)
        }
        dx, dz = offsets.get(specialty, offsets["young"])
        behavior_map = {
            "guardian": {"behavior": "guard", "patrolRadius": 1.2, "workLabel": "守望营地"},
            "hunter": {"behavior": "patrol", "patrolRadius": 2.2, "workLabel": "巡查猎路"},
            "carrier": {"behavior": "carry", "patrolRadius": 1.6, "workLabel": "搬运物资"},
            "young": {"behavior": "rest", "patrolRadius": 0.8, "workLabel": "伏在火光边"}
        }
        behavior = behavior_map.get(specialty, behavior_map["young"])
        active_task = tribe.get("active_beast_task") if isinstance(tribe.get("active_beast_task"), dict) else None
        task_until = active_task.get("activeUntil") if active_task else None
        if task_until:
            try:
                if datetime.fromisoformat(task_until) > datetime.now():
                    task_behavior = {
                        "guard": {"behavior": "guard", "patrolRadius": 1.3},
                        "hunt": {"behavior": "patrol", "patrolRadius": 2.4},
                        "haul": {"behavior": "carry", "patrolRadius": 1.8}
                    }.get(active_task.get("taskKey"))
                    if task_behavior:
                        behavior = {
                            **behavior,
                            **task_behavior,
                            "workLabel": f"执行{active_task.get('taskLabel', '任务')}"
                        }
                else:
                    tribe["active_beast_task"] = None
                    active_task = None
            except (TypeError, ValueError):
                tribe["active_beast_task"] = None
                active_task = None
        label_map = {"guardian": "守卫幼兽", "hunter": "猎伴幼兽", "carrier": "驮兽幼兽", "young": "驯养幼兽"}
        return {
            "id": f"{tribe.get('id')}_beast_marker",
            "tribeId": tribe.get("id"),
            "type": "tribe_beast_marker",
            "label": f"{tribe.get('name', '部落')}{label_map.get(specialty, '驯养幼兽')}",
            "x": float(center.get("x", 0)) + dx,
            "z": float(center.get("z", 0)) + dz,
            "size": 1.0,
            "specialty": specialty,
            "behavior": behavior["behavior"],
            "patrolRadius": behavior["patrolRadius"],
            "workLabel": behavior["workLabel"],
            "activeTask": active_task,
            "growth": self._beast_growth_state(tribe)
        }

    def _get_dynamic_tribe_landmarks(self) -> List[dict]:
        landmarks: List[dict] = []
        for tribe in self.tribes.values():
            camp = tribe.get("camp") or {}
            center = camp.get("center") or {}
            spawn = camp.get("spawn") or {}
            tribe_name = tribe.get("name", "部落")
            tribe_id = tribe.get("id")
            if tribe_id and center:
                landmarks.append({
                    "id": f"{tribe_id}_camp_center",
                    "tribeId": tribe_id,
                    "label": f"{tribe_name}营地",
                    "x": center.get("x", 0),
                    "z": center.get("z", 0),
                    "type": "tribe_camp"
                })
            if tribe_id and spawn:
                landmarks.append({
                    "id": f"{tribe_id}_camp_spawn",
                    "tribeId": tribe_id,
                    "label": f"{tribe_name}出生点",
                    "x": spawn.get("x", 0),
                    "z": spawn.get("z", 0),
                    "type": "tribe_spawn"
                })

            for building in camp.get("buildings", []):
                if building.get("type") in {"tribe_totem", "tribe_storage", "tribe_workbench"}:
                    rune_summary = self._tribe_public_rune_summary(tribe)
                    renown_state = self._tribe_renown_state(tribe)
                    landmarks.append({
                        "id": building.get("id"),
                        "tribeId": tribe_id,
                        "label": building.get("label"),
                        "x": building.get("x", 0),
                        "z": building.get("z", 0),
                        "type": building.get("type"),
                        "runeSummary": rune_summary if building.get("type") == "tribe_totem" else None,
                        "renownState": renown_state if building.get("type") == "tribe_totem" else None
                    })
            for flag in tribe.get("territory_flags", []) or []:
                if not isinstance(flag, dict):
                    continue
                landmarks.append({
                    "id": flag.get("id"),
                    "tribeId": tribe_id,
                    "label": flag.get("label", f"{tribe_name}领地旗帜"),
                    "x": flag.get("x", 0),
                    "z": flag.get("z", 0),
                    "type": "tribe_flag",
                    "claimedBy": flag.get("claimedBy"),
                    "claimedAt": flag.get("claimedAt"),
                    "claimNote": flag.get("claimNote", "这里已经被部落宣告为活动区域。")
                })
            beast_marker = self._tribe_beast_marker(tribe)
            if beast_marker:
                landmarks.append(beast_marker)
        return landmarks

    def _compose_map_data(self, map_name: Optional[str] = None) -> Optional[dict]:
        name = map_name or self.current_map_name
        map_data = self.maps.get(name)
        if not map_data:
            return None

        environment = dict(map_data.get("environment") or {})
        resource_tide = environment.get("resourceTide") or {}
        active_until = resource_tide.get("activeUntil")
        if active_until:
            try:
                if datetime.fromisoformat(active_until) <= datetime.now():
                    environment["resourceTide"] = None
            except (TypeError, ValueError):
                environment["resourceTide"] = None
        migration_season = environment.get("migrationSeason") or {}
        migration_until = migration_season.get("activeUntil") if isinstance(migration_season, dict) else None
        if migration_until:
            try:
                if datetime.fromisoformat(migration_until) <= datetime.now():
                    environment["migrationSeason"] = None
            except (TypeError, ValueError):
                environment["migrationSeason"] = None
        active_events = []
        for event in environment.get("worldEvents", []) or []:
            active_until = event.get("activeUntil") if isinstance(event, dict) else None
            if not active_until:
                continue
            try:
                if datetime.fromisoformat(active_until) > datetime.now():
                    active_events.append(event)
            except (TypeError, ValueError):
                continue
        environment["worldEvents"] = active_events
        season_objective = environment.get("seasonObjective") or {}
        active_until = season_objective.get("activeUntil") if isinstance(season_objective, dict) else None
        if active_until:
            try:
                if datetime.fromisoformat(active_until) <= datetime.now():
                    environment["seasonObjective"] = None
            except (TypeError, ValueError):
                environment["seasonObjective"] = None
        environment["landmarks"] = self._get_base_landmarks(name) + self._get_dynamic_tribe_landmarks()

        return {
            **map_data,
            "environment": environment,
            "decorations": self._get_base_decorations(name) + self._get_dynamic_tribe_decorations()
        }

    async def _broadcast_current_map(self):
        map_data = self._compose_map_data(self.current_map_name)
        if not map_data:
            return
        await self.broadcast({
            "type": "map_loaded",
            "mapName": self.current_map_name,
            "mapData": map_data
        })

    def _get_tribe_spawn_position(self, tribe_id: Optional[str]):
        if not tribe_id:
            return None
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            return None
        camp = tribe.get("camp") or {}
        spawn = camp.get("spawn") or {}
        if "x" not in spawn or "z" not in spawn:
            return None
        return {
            "x": float(spawn.get("x", 0)),
            "y": float(spawn.get("y", 2)),
            "z": float(spawn.get("z", 0))
        }

    async def _move_player_to_tribe_spawn(self, player_id: str, tribe_id: Optional[str]):
        player = self.players.get(player_id)
        spawn = self._get_tribe_spawn_position(tribe_id)
        if not player or not spawn:
            return

        player.update(spawn)
        await self.send_personal_message(player_id, {
            "type": "position_correction",
            "data": spawn
        })
        await self.broadcast({
            "type": "player_move",
            "playerId": player_id,
            "data": spawn
        }, exclude=[player_id])
        await self.send_aoi_state(player_id)

    def _pick_next_weather(self, current: Optional[str]) -> str:
        candidates = [w for w in self.weather_types if w != current]
        if not candidates:
            return current or "sunny"
        return self._weather_rng.choice(candidates)

    def _active_migration_season(self, env: dict) -> Optional[dict]:
        season = env.get("migrationSeason") or {}
        active_until = season.get("activeUntil") if isinstance(season, dict) else None
        if not active_until:
            return None
        try:
            if datetime.fromisoformat(active_until) <= datetime.now():
                return None
        except (TypeError, ValueError):
            return None
        return season

    def _build_migration_season(self) -> dict:
        return {
            "id": f"migration_{int(datetime.now().timestamp())}_{self._weather_rng.randint(100, 999)}",
            "title": "迁徙季节",
            "summary": "兽群沿海岸与林地迁徙，大地馈赠更强，兽群事件更容易出现。",
            "tideBonus": MIGRATION_SEASON_TIDE_BONUS,
            "herdWeight": MIGRATION_SEASON_HERD_WEIGHT,
            "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + MIGRATION_SEASON_DURATION_MINUTES * 60).isoformat()
        }

    def _pick_resource_tide(self, env: Optional[dict] = None) -> dict:
        region = self._weather_rng.choice(WORLD_REGIONS)
        migration = self._active_migration_season(env or {})
        gather_bonus = RESOURCE_TIDE_GATHER_BONUS + (MIGRATION_SEASON_TIDE_BONUS if migration else 0)
        return {
            "id": f"tide_{region['id']}_{int(datetime.now().timestamp())}",
            "regionId": region["id"],
            "regionType": region["type"],
            "regionLabel": region["label"],
            "x": region["x"],
            "z": region["z"],
            "radius": region["radius"],
            "gatherBonus": gather_bonus,
            "seasonBoosted": bool(migration),
            "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + RESOURCE_TIDE_DURATION_MINUTES * 60).isoformat()
        }

    def _pick_world_event(self, env: Optional[dict] = None) -> dict:
        event_pool = list(WORLD_EVENT_LIBRARY)
        if self._active_migration_season(env or {}):
            herd_event = next((item for item in WORLD_EVENT_LIBRARY if item.get("key") == "herd"), None)
            if herd_event:
                event_pool.extend([herd_event] * max(0, MIGRATION_SEASON_HERD_WEIGHT - 1))
        event = self._weather_rng.choice(event_pool)
        region = self._weather_rng.choice(WORLD_REGIONS)
        return self._build_world_event(event, region)

    def _build_world_event(self, event: dict, region: dict, duration_minutes: Optional[int] = None) -> dict:
        event_key = event.get("key", "generic")
        active_minutes = duration_minutes or WORLD_EVENT_DURATION_MINUTES
        return {
            "id": f"event_{event_key}_{int(datetime.now().timestamp())}_{self._weather_rng.randint(100, 999)}",
            "key": event_key,
            "title": event.get("title", "世界事件"),
            "summary": event.get("summary", "新的动态事件正在发生。"),
            "regionId": region["id"],
            "regionType": region["type"],
            "regionLabel": region["label"],
            "x": region["x"],
            "z": region["z"],
            "radius": region["radius"],
            "reward": dict(WORLD_EVENT_REWARDS.get(event_key, {})),
            "rare": bool(event.get("rare") or event_key.startswith("rare_")),
            "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + active_minutes * 60).isoformat()
        }

    def _build_rare_ruin_event(self) -> dict:
        ruin_regions = [region for region in WORLD_REGIONS if region.get("type") == "region_ruin"] or WORLD_REGIONS
        return self._build_world_event(
            {**RARE_WORLD_EVENT_LIBRARY["rare_ruin"], "rare": True},
            self._weather_rng.choice(ruin_regions),
            WORLD_EVENT_RARE_RUIN_DURATION_MINUTES
        )

    def _build_season_objective(self) -> dict:
        region = self._weather_rng.choice(WORLD_REGIONS)
        objective = SEASON_OBJECTIVES.get(region.get("type"), SEASON_OBJECTIVES["region_forest"])
        return {
            "id": f"season_{region['id']}_{int(datetime.now().timestamp())}_{self._weather_rng.randint(100, 999)}",
            "regionId": region["id"],
            "regionType": region["type"],
            "regionLabel": region["label"],
            "title": objective.get("title", "季节目标"),
            "summary": objective.get("summary", "季节正在给这片区域留下短暂机会。"),
            "reward": {k: v for k, v in objective.items() if k in {"wood", "stone", "food", "renown", "discoveryProgress"}},
            "x": region["x"],
            "z": region["z"],
            "radius": region["radius"],
            "activeUntil": datetime.fromtimestamp(datetime.now().timestamp() + SEASON_OBJECTIVE_DURATION_MINUTES * 60).isoformat()
        }

    async def _weather_loop(self):
        try:
            while True:
                await asyncio.sleep(self.weather_change_interval)
                if not self.active_connections:
                    return

                map_data = self.maps.get(self.current_map_name) or {}
                env = map_data.get("environment") or {}
                current = env.get("weather")
                next_weather = self._pick_next_weather(current)
                if next_weather == current:
                    continue

                if not self._active_migration_season(env) and self._weather_rng.random() < 0.25:
                    env["migrationSeason"] = self._build_migration_season()
                env["weather"] = next_weather
                env["resourceTide"] = self._pick_resource_tide(env)
                env["seasonObjective"] = self._build_season_objective()
                event_count = 2 if self._active_migration_season(env) else 1
                env["worldEvents"] = [self._pick_world_event(env) for _ in range(event_count)]
                map_data["environment"] = env
                map_data["updated_at"] = datetime.now().isoformat()

                await self.broadcast({
                    "type": "environment_update",
                    "mapName": self.current_map_name,
                    "environment": env
                })
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"天气循环异常: {e}")

    def _ensure_weather_task(self):
        if self._weather_task and not self._weather_task.done():
            return
        self._weather_task = asyncio.create_task(self._weather_loop())

    async def _food_pressure_loop(self):
        try:
            while True:
                await asyncio.sleep(60)
                if not self.active_connections:
                    return

                changed_tribe_ids = self._apply_all_food_decay()
                if not changed_tribe_ids:
                    continue

                self._save_tribe_state()
                affected_members = set()
                for tribe_id in changed_tribe_ids:
                    tribe = self.tribes.get(tribe_id)
                    if not tribe:
                        continue
                    affected_members.update(tribe.get("members", {}).keys())

                for member_id in affected_members:
                    await self.send_personal_message(member_id, self.get_player_tribe_state(member_id))
                await self.broadcast(self.get_tribes_overview())
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"食物压力循环异常: {e}")

    def _ensure_food_task(self):
        if self._food_task and not self._food_task.done():
            return
        self._food_task = asyncio.create_task(self._food_pressure_loop())

    def _dist2(self, a: dict, b: dict) -> float:
        dx = float(a.get("x", 0)) - float(b.get("x", 0))
        dz = float(a.get("z", 0)) - float(b.get("z", 0))
        return dx * dx + dz * dz

    def _get_current_environment(self) -> dict:
        map_data = self.maps.get(self.current_map_name) or {}
        env = map_data.get("environment") or {}
        return env if isinstance(env, dict) else {}

    def _get_shore_radius(self) -> float:
        env = self._get_current_environment()
        value = env.get("shoreRadius", env.get("playableRadius", DEFAULT_SHORE_RADIUS))
        try:
            radius = float(value)
        except (TypeError, ValueError):
            radius = DEFAULT_SHORE_RADIUS
        return max(5.0, radius)

    def _clamp_to_shore(self, x: float, z: float, margin: float = 0.0):
        max_radius = self._get_shore_radius() - float(margin or 0.0)
        max_radius = max(0.5, max_radius)
        dist2 = x * x + z * z
        if dist2 <= max_radius * max_radius:
            return x, z, False

        dist = math.sqrt(dist2) or 0.0001
        scale = max_radius / dist
        return x * scale, z * scale, True

    def _players_in_range(self, center_player_id: str, radius: float) -> List[str]:
        center = self.players.get(center_player_id)
        if not center:
            return []

        r2 = radius * radius
        nearby: List[str] = []
        for pid, pdata in self.players.items():
            if pid == center_player_id:
                continue
            if self._dist2(center, pdata) <= r2:
                nearby.append(pid)
        return nearby

    async def send_aoi_state(self, player_id: str):
        """发送当前 AOI 内玩家状态给指定玩家（用于创建/移除远端玩家）"""
        nearby_ids = self._players_in_range(player_id, self.aoi_radius)
        await self.send_personal_message(player_id, {
            "type": "aoi_state",
            "radius": self.aoi_radius,
            "players": [
                {"id": pid, "data": self.players.get(pid, {})}
                for pid in nearby_ids
            ]
        })
