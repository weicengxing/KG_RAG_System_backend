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
                "summary": layout.get("summary", ""),
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
            "tribe_hut",
            "tribe_fence",
            "tribe_road"
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

    def _flag_boundary_relation(self, tribe_id: Optional[str], flag: dict) -> Optional[dict]:
        if not tribe_id or not isinstance(flag, dict):
            return None
        flag_x = float(flag.get("x", 0) or 0)
        flag_z = float(flag.get("z", 0) or 0)
        nearest = None
        nearest_distance = None
        for other_tribe in self.tribes.values():
            other_id = other_tribe.get("id")
            if not other_id or other_id == tribe_id:
                continue
            for other_flag in other_tribe.get("territory_flags", []) or []:
                if not isinstance(other_flag, dict):
                    continue
                dx = flag_x - float(other_flag.get("x", 0) or 0)
                dz = flag_z - float(other_flag.get("z", 0) or 0)
                distance = math.sqrt(dx * dx + dz * dz)
                if nearest_distance is None or distance < nearest_distance:
                    nearest_distance = distance
                    nearest = (other_tribe, other_flag)
        if not nearest or nearest_distance is None or nearest_distance > TRIBE_FLAG_BOUNDARY_NEAR_DISTANCE:
            return None
        other_tribe, other_flag = nearest
        tribe = self.tribes.get(tribe_id) or {}
        own_oath = (self._tribe_oath(tribe) or {}).get("key")
        other_oath = (self._tribe_oath(other_tribe) or {}).get("key")
        progress = self._boundary_relation_progress(tribe_id, other_tribe.get("id"))
        if progress.get("score", 0) >= TRIBE_BOUNDARY_RELATION_STAGE_STEP:
            state, label = "alliance", "友好边界"
        elif progress.get("score", 0) <= -TRIBE_BOUNDARY_RELATION_STAGE_STEP:
            state, label = "hostile", "敌意边界"
        elif own_oath == "trade" or other_oath == "trade" or progress.get("tradeTrust", 0) >= TRIBE_BOUNDARY_RELATION_STAGE_STEP:
            state, label = "trade", "可贸易边界"
        elif nearest_distance <= TRIBE_FLAG_BOUNDARY_TENSION_DISTANCE:
            state, label = "tension", "紧张边界"
        else:
            state, label = "neighbor", "相邻边界"
        return {
            "state": state,
            "label": label,
            "distance": round(nearest_distance),
            "otherTribeId": other_tribe.get("id"),
            "otherTribeName": other_tribe.get("name", "部落"),
            "otherFlagId": other_flag.get("id"),
            "relationScore": progress.get("score", 0),
            "tradeTrust": progress.get("tradeTrust", 0),
            "lastAction": progress.get("lastAction"),
            "lastActionAt": progress.get("lastActionAt")
        }

    def _boundary_relation_progress(self, tribe_id: Optional[str], other_tribe_id: Optional[str]) -> dict:
        if not tribe_id or not other_tribe_id:
            return {"score": 0, "tradeTrust": 0}
        tribe = self.tribes.get(tribe_id) or {}
        own_record = (tribe.get("boundary_relations") or {}).get(other_tribe_id) or {}
        return {
            "score": int(own_record.get("score", 0) or 0),
            "tradeTrust": int(own_record.get("tradeTrust", 0) or 0),
            "lastAction": own_record.get("lastAction"),
            "lastActionAt": own_record.get("lastActionAt")
        }

    def _get_dynamic_tribe_decorations(self) -> List[dict]:
        decorations: List[dict] = []
        for tribe in self.tribes.values():
            oath = self._tribe_oath(tribe)
            camp = tribe.get("camp") or {}
            buildings = camp.get("buildings") or []
            for building in buildings:
                item = dict(building)
                if oath:
                    item["oathKey"] = oath.get("key")
                    item["oathLabel"] = oath.get("label")
                decorations.append(item)
            for flag in tribe.get("territory_flags", []) or []:
                if isinstance(flag, dict):
                    item = dict(flag)
                    if oath:
                        item["oathKey"] = oath.get("key")
                        item["oathLabel"] = oath.get("label")
                    item["boundaryRelation"] = self._flag_boundary_relation(tribe.get("id"), item)
                    decorations.append(item)
            beast_marker = self._tribe_beast_marker(tribe)
            if beast_marker:
                decorations.append(beast_marker)
            decorations.extend(self._active_scouted_resource_sites(tribe))
            decorations.extend(self._active_controlled_resource_sites(tribe))
            decorations.extend(self._active_trade_route_sites(tribe))
            if hasattr(self, "_active_caravan_routes"):
                decorations.extend(self._active_caravan_routes(tribe))
            if hasattr(self, "_active_nomad_visitors"):
                decorations.extend(self._active_nomad_visitors(tribe))
            decorations.extend(self._active_diplomacy_council_sites(tribe))
            decorations.extend(self._active_world_event_remnants(tribe))
            if hasattr(self, "_active_map_memories"):
                decorations.extend(self._active_map_memories(tribe))
            if hasattr(self, "_active_world_riddles"):
                decorations.extend(self._active_world_riddles(tribe))
            if hasattr(self, "_active_cave_races"):
                for race in self._active_cave_races(tribe):
                    race_marker = dict(race)
                    race_marker["raceId"] = race.get("id")
                    race_marker["id"] = f"{race.get('id')}_{tribe.get('id')}"
                    decorations.append(race_marker)
            if hasattr(self, "_active_trail_markers"):
                decorations.extend(self._active_trail_markers(tribe))
            if hasattr(self, "_active_named_landmarks"):
                decorations.extend(self._active_named_landmarks(tribe))
            if hasattr(self, "_active_neutral_sanctuaries"):
                decorations.extend(self._active_neutral_sanctuaries(tribe))
            if hasattr(self, "_active_standing_ritual"):
                ritual = self._active_standing_ritual(tribe)
                center = camp.get("center") or {}
                if ritual and center:
                    decorations.append({
                        "id": f"{tribe.get('id')}_standing_ritual_site",
                        "tribeId": tribe.get("id"),
                        "type": "standing_ritual_site",
                        "label": ritual.get("label", "站位仪式"),
                        "ritualKey": ritual.get("key"),
                        "participantCount": len(ritual.get("participants", []) or []),
                        "x": center.get("x", 0),
                        "z": center.get("z", 0),
                        "y": 0,
                        "size": 1.0
                    })
        return decorations

    def _active_scouted_resource_sites(self, tribe: dict) -> List[dict]:
        active = []
        now = datetime.now()
        for site in tribe.get("scouted_resource_sites", []) or []:
            if not isinstance(site, dict) or site.get("status") == "secured":
                continue
            active_until = site.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    pass
            active.append(site)
        if len(active) != len(tribe.get("scouted_resource_sites", []) or []):
            tribe["scouted_resource_sites"] = active[-TRIBE_SCOUT_SITE_LIMIT:]
        return active[-TRIBE_SCOUT_SITE_LIMIT:]

    def _active_controlled_resource_sites(self, tribe: dict) -> List[dict]:
        active = []
        now = datetime.now()
        for site in tribe.get("controlled_resource_sites", []) or []:
            if not isinstance(site, dict):
                continue
            active_until = site.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    pass
            active.append(site)
        if len(active) != len(tribe.get("controlled_resource_sites", []) or []):
            tribe["controlled_resource_sites"] = active[-TRIBE_CONTROLLED_SITE_LIMIT:]
        return active[-TRIBE_CONTROLLED_SITE_LIMIT:]

    def _active_trade_route_sites(self, tribe: dict) -> List[dict]:
        active = []
        now = datetime.now()
        for site in tribe.get("trade_route_sites", []) or []:
            if not isinstance(site, dict):
                continue
            active_until = site.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    pass
            market_until = site.get("marketUntil")
            site["isBorderMarket"] = False
            if market_until:
                try:
                    site["isBorderMarket"] = datetime.fromisoformat(market_until) > now
                except (TypeError, ValueError):
                    site["isBorderMarket"] = False
            if not site["isBorderMarket"] and site.get("label") == "交换通路边市":
                site["label"] = "交换通路贸易点"
            active.append(site)
        if len(active) != len(tribe.get("trade_route_sites", []) or []):
            tribe["trade_route_sites"] = active[-TRIBE_TRADE_ROUTE_SITE_LIMIT:]
        return active[-TRIBE_TRADE_ROUTE_SITE_LIMIT:]

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
            oath = self._tribe_oath(tribe)
            if tribe_id and center:
                landmarks.append({
                    "id": f"{tribe_id}_camp_center",
                    "tribeId": tribe_id,
                    "label": f"{tribe_name}营地",
                    "x": center.get("x", 0),
                    "z": center.get("z", 0),
                    "type": "tribe_camp",
                    "oathKey": oath.get("key") if oath else None,
                    "oathLabel": oath.get("label") if oath else None
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
                if building.get("type") in {"tribe_totem", "tribe_storage", "tribe_workbench", "tribe_fence", "tribe_road"}:
                    rune_summary = self._tribe_public_rune_summary(tribe)
                    renown_state = self._tribe_renown_state(tribe)
                    landmarks.append({
                        "id": building.get("id"),
                        "tribeId": tribe_id,
                        "label": building.get("label"),
                        "x": building.get("x", 0),
                        "z": building.get("z", 0),
                        "type": building.get("type"),
                        "oathKey": oath.get("key") if oath else None,
                        "oathLabel": oath.get("label") if oath else None,
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
                    "oathKey": oath.get("key") if oath else None,
                    "oathLabel": oath.get("label") if oath else None,
                    "claimedBy": flag.get("claimedBy"),
                    "claimedAt": flag.get("claimedAt"),
                    "lastPatrolledAt": flag.get("lastPatrolledAt"),
                    "lastPatrolledBy": flag.get("lastPatrolledBy"),
                    "boundaryRelation": self._flag_boundary_relation(tribe_id, flag),
                    "claimNote": flag.get("claimNote", "这里已经被部落宣告为活动区域。")
                })
            beast_marker = self._tribe_beast_marker(tribe)
            if beast_marker:
                landmarks.append(beast_marker)
            for site in self._active_scouted_resource_sites(tribe):
                landmarks.append({
                    "id": site.get("id"),
                    "tribeId": tribe_id,
                    "label": site.get("label", "侦察资源点"),
                    "x": site.get("x", 0),
                    "z": site.get("z", 0),
                    "type": "scouted_resource_site",
                    "regionType": site.get("regionType"),
                    "regionLabel": site.get("regionLabel"),
                    "resourceLabel": site.get("resourceLabel"),
                    "contested": bool(site.get("contested")),
                    "contestedByTribeName": site.get("contestedByTribeName"),
                    "sharedWithTribeName": site.get("sharedWithTribeName"),
                    "jointWatchId": site.get("jointWatchId"),
                    "claimedBy": site.get("foundBy"),
                    "claimedAt": site.get("createdAt"),
                    "activeUntil": site.get("activeUntil")
                })
            for site in self._active_controlled_resource_sites(tribe):
                landmarks.append({
                    "id": site.get("id"),
                    "tribeId": tribe_id,
                    "label": site.get("label", "控制资源点"),
                    "x": site.get("x", 0),
                    "z": site.get("z", 0),
                    "type": "controlled_resource_site",
                    "regionType": site.get("regionType"),
                    "resourceLabel": site.get("resourceLabel"),
                    "level": int(site.get("level", 1) or 1),
                    "yieldCount": int(site.get("yieldCount", 0) or 0),
                    "patrolCount": int(site.get("patrolCount", 0) or 0),
                    "relayCount": int(site.get("relayCount", 0) or 0),
                    "roadLinked": bool(site.get("roadLinked")),
                    "claimedBy": site.get("securedByName"),
                    "claimedAt": site.get("controlledAt"),
                    "activeUntil": site.get("activeUntil"),
                    "lastYieldAt": site.get("lastYieldAt"),
                    "lastPatrolledAt": site.get("lastPatrolledAt"),
                    "lastPatrolledBy": site.get("lastPatrolledBy"),
                    "lastRelayedAt": site.get("lastRelayedAt"),
                    "lastRelayedBy": site.get("lastRelayedBy"),
                    "contestResolvedAs": site.get("contestResolvedAs")
                })
            for site in self._active_trade_route_sites(tribe):
                landmarks.append({
                    "id": site.get("id"),
                    "tribeId": tribe_id,
                    "label": site.get("label", "交换通路贸易点"),
                    "x": site.get("x", 0),
                    "z": site.get("z", 0),
                    "type": "trade_route_site",
                    "resourceLabel": site.get("resourceLabel"),
                    "partnerTribeId": site.get("partnerTribeId"),
                    "partnerTribeName": site.get("partnerTribeName"),
                    "collectCount": int(site.get("collectCount", 0) or 0),
                    "marketCollectTarget": int(site.get("marketCollectTarget", TRIBE_TRADE_ROUTE_MARKET_COLLECTS) or TRIBE_TRADE_ROUTE_MARKET_COLLECTS),
                    "isBorderMarket": bool(site.get("isBorderMarket")),
                    "marketRewardLabel": site.get("marketRewardLabel"),
                    "claimedAt": site.get("createdAt"),
                    "activeUntil": site.get("activeUntil"),
                    "lastCollectedAt": site.get("lastCollectedAt"),
                    "lastCollectedBy": site.get("lastCollectedBy"),
                    "sharedRouteId": site.get("sharedRouteId")
                })
            if hasattr(self, "_active_caravan_routes"):
                for route in self._active_caravan_routes(tribe):
                    landmarks.append({
                        "id": route.get("id"),
                        "tribeId": tribe_id,
                        "label": route.get("label", "游牧商队"),
                        "x": route.get("x", 0),
                        "z": route.get("z", 0),
                        "type": "nomad_caravan",
                        "summary": route.get("summary"),
                        "focusLabel": route.get("focusLabel"),
                        "otherTribeId": route.get("otherTribeId"),
                        "otherTribeName": route.get("otherTribeName"),
                        "activeUntil": route.get("activeUntil"),
                        "claimedAt": route.get("createdAt")
                    })
            if hasattr(self, "_active_nomad_visitors"):
                for visitor in self._active_nomad_visitors(tribe):
                    landmarks.append({
                        "id": visitor.get("id"),
                        "tribeId": tribe_id,
                        "label": visitor.get("label", "神秘旅人"),
                        "x": visitor.get("x", 0),
                        "z": visitor.get("z", 0),
                        "type": "nomad_visitor",
                        "summary": visitor.get("summary"),
                        "giftLabel": visitor.get("giftLabel"),
                        "activeUntil": visitor.get("activeUntil"),
                        "claimedAt": visitor.get("createdAt")
                    })
            if hasattr(self, "_active_mutual_aid_alerts"):
                for alert in self._active_mutual_aid_alerts(tribe):
                    landmarks.append({
                        "id": alert.get("id"),
                        "tribeId": tribe_id,
                        "label": alert.get("title", "火烟互助警报"),
                        "x": alert.get("x", 0),
                        "z": alert.get("z", 0),
                        "type": "mutual_aid_alert",
                        "summary": alert.get("summary"),
                        "direction": alert.get("direction"),
                        "sourceTitle": alert.get("sourceTitle"),
                        "sourceTribeId": alert.get("sourceTribeId"),
                        "sourceTribeName": alert.get("sourceTribeName"),
                        "targetTribeId": alert.get("targetTribeId"),
                        "targetTribeName": alert.get("targetTribeName"),
                        "activeUntil": alert.get("activeUntil"),
                        "claimedAt": alert.get("createdAt")
                    })
            for site in self._active_diplomacy_council_sites(tribe):
                landmarks.append({
                    "id": site.get("id"),
                    "tribeId": tribe_id,
                    "label": site.get("label", "大议会与边市节"),
                    "x": site.get("x", 0),
                    "z": site.get("z", 0),
                    "type": "diplomacy_council_site",
                    "summary": site.get("summary"),
                    "signalCount": int(site.get("signalCount", 0) or 0),
                    "participantTribeNames": site.get("participantTribeNames", []),
                    "claimedAt": site.get("createdAt"),
                    "activeUntil": site.get("activeUntil")
                })
            for remnant in self._active_world_event_remnants(tribe):
                landmarks.append({
                    "id": remnant.get("id"),
                    "tribeId": tribe_id,
                    "label": remnant.get("label", "事件余迹"),
                    "x": remnant.get("x", 0),
                    "z": remnant.get("z", 0),
                    "type": "world_event_remnant",
                    "remnantKey": remnant.get("remnantKey"),
                    "summary": remnant.get("summary"),
                    "rewardLabel": remnant.get("rewardLabel"),
                    "regionType": remnant.get("regionType"),
                    "regionLabel": remnant.get("regionLabel"),
                    "sourceEventTitle": remnant.get("sourceEventTitle"),
                    "sourceActionLabel": remnant.get("sourceActionLabel"),
                    "claimedBy": remnant.get("createdBy"),
                    "claimedAt": remnant.get("createdAt"),
                    "activeUntil": remnant.get("activeUntil")
                })
            migration_plan = self._active_migration_plan(tribe) if hasattr(self, "_active_migration_plan") else None
            if migration_plan:
                landmarks.append({
                    "id": migration_plan.get("id"),
                    "tribeId": tribe_id,
                    "label": migration_plan.get("siteLabel") or migration_plan.get("label", "迁徙季行动点"),
                    "x": migration_plan.get("x", 0),
                    "z": migration_plan.get("z", 0),
                    "type": "migration_plan_site",
                    "planKey": migration_plan.get("key"),
                    "summary": migration_plan.get("summary"),
                    "progress": int(migration_plan.get("progress", 0) or 0),
                    "target": int(migration_plan.get("target", TRIBE_MIGRATION_PLAN_PROGRESS_TARGET) or TRIBE_MIGRATION_PLAN_PROGRESS_TARGET),
                    "activeUntil": migration_plan.get("activeUntil")
                })
            if hasattr(self, "_active_celebration_echoes"):
                for echo in self._active_celebration_echoes(tribe):
                    landmarks.append({
                        "id": echo.get("id"),
                        "tribeId": tribe_id,
                        "label": echo.get("label", "庆功余韵"),
                        "x": echo.get("x", 0),
                        "z": echo.get("z", 0),
                        "type": "celebration_echo",
                        "summary": echo.get("summary"),
                        "sourceKind": echo.get("sourceKind"),
                        "sourceLabel": echo.get("sourceLabel"),
                        "anchorKey": echo.get("anchorKey"),
                        "anchorLabel": echo.get("anchorLabel"),
                        "participantCount": len(echo.get("participants", []) or []),
                        "rewardLabel": "、".join(self._celebration_reward_parts(echo.get("reward", {}))) if hasattr(self, "_celebration_reward_parts") else "",
                        "activeUntil": echo.get("activeUntil"),
                        "claimedAt": echo.get("createdAt")
                    })
            for memory in self._active_map_memories(tribe):
                landmarks.append({
                    "id": memory.get("id"),
                    "tribeId": tribe_id,
                    "label": memory.get("label", "活地图记忆"),
                    "x": memory.get("x", 0),
                    "z": memory.get("z", 0),
                    "type": "map_memory_trace",
                    "memoryKind": memory.get("kind"),
                    "summary": memory.get("summary"),
                    "rewardLabel": memory.get("rewardLabel"),
                    "claimedBy": memory.get("actorName"),
                    "claimedAt": memory.get("createdAt"),
                    "activeUntil": memory.get("activeUntil")
                })
            if hasattr(self, "_active_world_riddles"):
                for riddle in self._active_world_riddles(tribe):
                    landmarks.append({
                        "id": riddle.get("id"),
                        "tribeId": tribe_id,
                        "label": riddle.get("label", "世界谜语"),
                        "x": riddle.get("x", 0),
                        "z": riddle.get("z", 0),
                        "type": "world_riddle_site",
                        "summary": riddle.get("summary"),
                        "patternLabel": riddle.get("patternLabel"),
                        "regionLabel": riddle.get("regionLabel"),
                        "rewardLabel": riddle.get("rewardLabel"),
                        "claimedAt": riddle.get("createdAt"),
                        "activeUntil": riddle.get("activeUntil")
                    })
            if hasattr(self, "_active_old_camp_echoes"):
                for echo in self._active_old_camp_echoes(tribe):
                    landmarks.append({
                        "id": echo.get("id"),
                        "tribeId": tribe_id,
                        "label": echo.get("label", "回归旧营"),
                        "x": echo.get("x", 0),
                        "z": echo.get("z", 0),
                        "type": "old_camp_echo",
                        "summary": echo.get("summary"),
                        "sourceLabel": echo.get("sourceLabel"),
                        "participantCount": len(echo.get("participants", []) or []),
                        "claimedAt": echo.get("createdAt"),
                        "activeUntil": echo.get("activeUntil")
                    })
            if hasattr(self, "_active_cave_races"):
                for race in self._active_cave_races(tribe):
                    rescue = race.get("rescue") or {}
                    landmarks.append({
                        "id": f"{race.get('id')}_{tribe_id}",
                        "raceId": race.get("id"),
                        "tribeId": tribe_id,
                        "label": race.get("label", "短时稀有洞穴"),
                        "x": race.get("x", 0),
                        "z": race.get("z", 0),
                        "type": "cave_rescue_clue" if race.get("status") == "rescue" else "rare_cave_race",
                        "summary": race.get("summary"),
                        "caveLabel": race.get("caveLabel"),
                        "status": race.get("status"),
                        "firstExplorerTribeName": race.get("firstExplorerTribeName"),
                        "missingMemberName": rescue.get("missingMemberName"),
                        "progress": int(rescue.get("progress", 0) or 0),
                        "target": int(rescue.get("target", 0) or 0),
                        "claimedAt": race.get("createdAt"),
                        "activeUntil": race.get("activeUntil")
                    })
            if hasattr(self, "_active_trail_markers"):
                for marker in self._active_trail_markers(tribe):
                    landmarks.append({
                        "id": marker.get("id"),
                        "tribeId": tribe_id,
                        "label": marker.get("label", "活路标"),
                        "x": marker.get("x", 0),
                        "z": marker.get("z", 0),
                        "type": "trail_marker",
                        "markerKey": marker.get("markerKey"),
                        "summary": marker.get("summary"),
                        "claimedBy": marker.get("createdByName"),
                        "claimedAt": marker.get("createdAt"),
                        "activeUntil": marker.get("activeUntil")
                    })
            if hasattr(self, "_active_named_landmarks"):
                for landmark in self._active_named_landmarks(tribe):
                    landmarks.append({
                        "id": landmark.get("id"),
                        "tribeId": tribe_id,
                        "label": landmark.get("label", "有名之地"),
                        "x": landmark.get("x", 0),
                        "z": landmark.get("z", 0),
                        "type": "named_landmark",
                        "sourceLabel": landmark.get("sourceLabel"),
                        "summary": landmark.get("summary"),
                        "rewardParts": landmark.get("rewardParts", [])
                    })
            if hasattr(self, "_active_neutral_sanctuaries"):
                for sanctuary in self._active_neutral_sanctuaries(tribe):
                    landmarks.append({
                        "id": sanctuary.get("id"),
                        "tribeId": tribe_id,
                        "label": sanctuary.get("label", "中立圣地"),
                        "x": sanctuary.get("x", 0),
                        "z": sanctuary.get("z", 0),
                        "type": "neutral_sanctuary",
                        "summary": sanctuary.get("summary"),
                        "regionLabel": sanctuary.get("regionLabel"),
                        "status": sanctuary.get("status", "active"),
                        "useCount": sanctuary.get("useCount", 0),
                        "useTarget": sanctuary.get("useTarget"),
                        "claimedAt": sanctuary.get("createdAt"),
                        "activeUntil": sanctuary.get("activeUntil")
                    })
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
        celestial_window = environment.get("celestialWindow") or {}
        celestial_until = celestial_window.get("activeUntil") if isinstance(celestial_window, dict) else None
        if celestial_until:
            try:
                if datetime.fromisoformat(celestial_until) <= datetime.now():
                    environment["celestialWindow"] = None
            except (TypeError, ValueError):
                environment["celestialWindow"] = None
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
        if hasattr(self, "_pick_visitor_hint_world_event"):
            hinted_event = self._pick_visitor_hint_world_event()
            if hinted_event:
                ruin_regions = [region for region in WORLD_REGIONS if region.get("type") == "region_ruin"] or WORLD_REGIONS
                duration = WORLD_EVENT_RARE_RUIN_DURATION_MINUTES if hinted_event.get("key") == "rare_ruin" else None
                return self._build_world_event(hinted_event, self._weather_rng.choice(ruin_regions), duration)
        if hasattr(self, "_world_riddle_chance_bonus"):
            bonus = self._world_riddle_chance_bonus("rare_ruin")
            if bonus and self._weather_rng.random() < bonus:
                if hasattr(self, "_mark_world_riddle_influence_used"):
                    self._mark_world_riddle_influence_used("rare_ruin", "牵引稀有遗迹")
                return self._build_rare_ruin_event()
        event_pool = list(WORLD_EVENT_LIBRARY)
        if self._active_migration_season(env or {}):
            herd_event = next((item for item in WORLD_EVENT_LIBRARY if item.get("key") == "herd"), None)
            if herd_event:
                event_pool.extend([herd_event] * max(0, MIGRATION_SEASON_HERD_WEIGHT - 1))
        if hasattr(self, "_apply_dream_omen_world_event_bias"):
            event_pool = self._apply_dream_omen_world_event_bias(event_pool)
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
                celestial_chance = CELESTIAL_WINDOW_CHANCE
                if hasattr(self, "_visitor_aftereffect_bonus"):
                    celestial_chance += self._visitor_aftereffect_bonus("celestial")
                if hasattr(self, "_world_riddle_chance_bonus"):
                    celestial_chance += self._world_riddle_chance_bonus("celestial")
                if not self._active_celestial_window(env) and self._weather_rng.random() < celestial_chance:
                    env["celestialWindow"] = self._build_celestial_window(env)
                    if hasattr(self, "_mark_visitor_aftereffect_used"):
                        self._mark_visitor_aftereffect_used("celestial", env["celestialWindow"].get("title", "罕见天象"))
                    if hasattr(self, "_mark_world_riddle_influence_used"):
                        self._mark_world_riddle_influence_used("celestial", env["celestialWindow"].get("title", "罕见天象"))
                env["weather"] = next_weather
                env["resourceTide"] = self._pick_resource_tide(env)
                env["seasonObjective"] = self._build_season_objective()
                event_count = 2 if self._active_migration_season(env) else 1
                env["worldEvents"] = [self._pick_world_event(env) for _ in range(event_count)]
                if hasattr(self, "_resolve_weather_forecasts"):
                    await self._resolve_weather_forecasts(next_weather, current)
                map_data["environment"] = env
                map_data["updated_at"] = datetime.now().isoformat()
                visitor_spawned = 0
                if hasattr(self, "_maybe_spawn_nomad_visitors"):
                    visitor_spawned = await self._maybe_spawn_nomad_visitors()
                riddle_spawned = 0
                if hasattr(self, "_maybe_spawn_world_riddles"):
                    riddle_spawned = await self._maybe_spawn_world_riddles()

                await self.broadcast({
                    "type": "environment_update",
                    "mapName": self.current_map_name,
                    "environment": env
                })
                if visitor_spawned or riddle_spawned:
                    await self._broadcast_current_map()
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
