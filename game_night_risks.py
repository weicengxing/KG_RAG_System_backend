from datetime import datetime
import random

from game_config import *


class GameNightRiskMixin:
    def _night_outing_window_state(self) -> dict:
        now = datetime.now()
        hour = now.hour
        is_night = hour >= 18 or hour < 6
        return {
            "hour": hour,
            "isNight": is_night,
            "label": "夜色正深" if is_night else "薄暮试探",
            "riskModifier": 0 if is_night else -1,
            "summary": "夜路更容易发现旧痕，也更容易走偏。" if is_night else "天色未深，仍可先做一轮低风险探路。"
        }

    def _night_outing_weather_state(self) -> dict:
        env = self._get_current_environment() if hasattr(self, "_get_current_environment") else {}
        weather = env.get("weather", "sunny")
        risk = int(TRIBE_NIGHT_OUTING_WEATHER_RISK.get(weather, 0) or 0)
        label = self._weather_label(weather) if hasattr(self, "_weather_label") else WEATHER_LABELS.get(weather, weather)
        return {"weather": weather, "weatherLabel": label, "risk": risk}

    def _recent_correct_weather_record(self, tribe: dict) -> dict | None:
        records = [
            item for item in (tribe.get("weather_forecast_records", []) or [])
            if isinstance(item, dict) and item.get("correct")
        ]
        return records[-1] if records else None

    def _night_outing_supports(self, tribe: dict, option_key: str) -> tuple[list, int]:
        supports = []
        relief = 0
        option = TRIBE_NIGHT_OUTING_OPTIONS.get(option_key, {})
        option_relief = int(option.get("riskRelief", 0) or 0)
        if option_relief:
            supports.append({"label": option.get("label", "夜行准备"), "relief": option_relief})
            relief += option_relief

        forecast = self._active_weather_forecast(tribe) if hasattr(self, "_active_weather_forecast") else None
        forecast_confidence = len(forecast.get("observations", []) or []) if forecast else 0
        if forecast_confidence >= 2:
            supports.append({"label": "当前风向预判", "relief": 1})
            relief += 1

        recent_weather = self._recent_correct_weather_record(tribe)
        if recent_weather:
            supports.append({"label": f"近期命中{recent_weather.get('actualWeatherLabel', '天气')}", "relief": 1})
            relief += 1

        standing = self._active_standing_ritual(tribe) if hasattr(self, "_active_standing_ritual") else None
        if standing and len(standing.get("participants", []) or []) >= TRIBE_STANDING_RITUAL_MIN_PARTICIPANTS:
            supports.append({"label": standing.get("label", "站位仪式"), "relief": 1})
            relief += 1

        if option_key == "totem_blessing" and self._has_tribe_structure_type(tribe, "tribe_totem"):
            supports.append({"label": "部落图腾", "relief": 1})
            relief += 1
        return supports, relief

    def _public_night_outing_status(self, tribe: dict) -> dict:
        window = self._night_outing_window_state()
        weather = self._night_outing_weather_state()
        recent = self._recent_correct_weather_record(tribe)
        return {
            **window,
            **weather,
            "recentWeatherHit": {
                "actualWeatherLabel": recent.get("actualWeatherLabel"),
                "createdAt": recent.get("createdAt")
            } if recent else None
        }

    def _public_night_outing_options(self, tribe: dict) -> dict:
        member_count = len(tribe.get("members", {}) or {})
        options = {}
        for key, config in TRIBE_NIGHT_OUTING_OPTIONS.items():
            min_members = int(config.get("minMembers", 0) or 0)
            available = member_count >= min_members
            options[key] = {
                **config,
                "available": available,
                "lockedReason": "" if available else f"需要至少 {min_members} 名成员"
            }
        return options

    def _public_night_outing_records(self, tribe: dict) -> list:
        records = [item for item in tribe.get("night_outing_records", []) or [] if isinstance(item, dict)]
        return records[-TRIBE_NIGHT_OUTING_RECENT_LIMIT:]

    def _apply_night_outing_reward(self, tribe: dict, reward: dict) -> list:
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石材")):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                storage[key] = int(storage.get(key, 0) or 0) + value
                reward_parts.append(f"{label}+{value}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                reward_parts.append(f"{label}+{value}")
        return reward_parts

    async def start_night_outing(self, player_id: str, option_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        option = TRIBE_NIGHT_OUTING_OPTIONS.get(option_key)
        if not option:
            await self._send_tribe_error(player_id, "未知夜行方式")
            return
        min_members = int(option.get("minMembers", 0) or 0)
        if len(tribe.get("members", {}) or {}) < min_members:
            await self._send_tribe_error(player_id, f"{option.get('label', '夜行')}需要至少 {min_members} 名成员")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        wood_cost = int(option.get("woodCost", 0) or 0)
        stone_cost = int(option.get("stoneCost", 0) or 0)
        food_cost = int(option.get("foodCost", 0) or 0)
        if int(storage.get("wood", 0) or 0) < wood_cost:
            await self._send_tribe_error(player_id, f"{option.get('label', '夜行')}需要公共木材{wood_cost}")
            return
        if int(storage.get("stone", 0) or 0) < stone_cost:
            await self._send_tribe_error(player_id, f"{option.get('label', '夜行')}需要公共石材{stone_cost}")
            return
        if int(tribe.get("food", 0) or 0) < food_cost:
            await self._send_tribe_error(player_id, f"{option.get('label', '夜行')}需要公共食物{food_cost}")
            return
        storage["wood"] = int(storage.get("wood", 0) or 0) - wood_cost
        storage["stone"] = int(storage.get("stone", 0) or 0) - stone_cost
        tribe["food"] = int(tribe.get("food", 0) or 0) - food_cost

        window = self._night_outing_window_state()
        weather = self._night_outing_weather_state()
        supports, relief = self._night_outing_supports(tribe, option_key)
        base_risk = 3 + int(weather.get("risk", 0) or 0) + int(window.get("riskModifier", 0) or 0)
        final_risk = max(0, min(5, base_risk - relief))
        rng = getattr(self, "_weather_rng", None) or random
        roll = rng.randint(1, 6)
        success = roll > final_risk

        player = self.players.setdefault(player_id, {})
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name") or player.get("name") or "成员"
        reward_parts = []
        memory = None
        if success:
            reward_parts = self._apply_night_outing_reward(tribe, option.get("reward", {}))
            try:
                x = float(player.get("x", (tribe.get("camp") or {}).get("center", {}).get("x", 0)) or 0)
                z = float(player.get("z", (tribe.get("camp") or {}).get("center", {}).get("z", 0)) or 0)
            except (TypeError, ValueError):
                x = float((tribe.get("camp") or {}).get("center", {}).get("x", 0) or 0)
                z = float((tribe.get("camp") or {}).get("center", {}).get("z", 0) or 0)
            if option.get("successMemory"):
                memory = self._record_map_memory(
                    tribe,
                    "night_trace",
                    f"{option.get('label', '夜行')}旧痕",
                    f"{member_name}在{weather.get('weatherLabel', '夜色')}里走过这条夜路，后来者能沿着火光和脚印重读方向。",
                    x,
                    z,
                    f"night_outing_{tribe_id}_{int(datetime.now().timestamp() * 1000)}",
                    member_name
                )
                if memory:
                    reward_parts.append("活地图记忆+1")
        else:
            player["conflict_fatigue"] = int(player.get("conflict_fatigue", 0) or 0) + 1

        support_labels = [f"{item.get('label')} -{item.get('relief')}" for item in supports]
        record = {
            "id": f"night_outing_{tribe_id}_{int(datetime.now().timestamp() * 1000)}_{rng.randint(100, 999)}",
            "optionKey": option_key,
            "optionLabel": option.get("label", "夜行"),
            "memberId": player_id,
            "memberName": member_name,
            "weather": weather.get("weather"),
            "weatherLabel": weather.get("weatherLabel"),
            "windowLabel": window.get("label"),
            "roll": roll,
            "risk": final_risk,
            "baseRisk": base_risk,
            "relief": relief,
            "supportLabels": support_labels,
            "success": success,
            "rewardParts": reward_parts,
            "memoryId": memory.get("id") if memory else "",
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("night_outing_records", []).append(record)
        tribe["night_outing_records"] = tribe["night_outing_records"][-TRIBE_NIGHT_OUTING_RECENT_LIMIT:]
        if success:
            detail = f"{member_name}选择{option.get('label', '夜行')}，在{weather.get('weatherLabel', '夜色')}里掷出{roll}对风险{final_risk}，带回{'、'.join(reward_parts) or '新的夜路线索'}。"
            rumor_text = f"{tribe.get('name', '部落')}的夜行者用{option.get('label', '夜行')}穿过{weather.get('weatherLabel', '夜色')}，留下可被重读的夜路旧痕。"
            await self._publish_world_rumor("world_event", "夜行旧痕", rumor_text, {"tribeId": tribe_id, "recordId": record["id"]})
        else:
            detail = f"{member_name}选择{option.get('label', '夜行')}，在{weather.get('weatherLabel', '夜色')}里掷出{roll}对风险{final_risk}，只带回一次迷路教训，个人疲劳+1。"
        if support_labels:
            detail += f" 支撑：{'、'.join(support_labels)}。"
        self._add_tribe_history(tribe, "world_event", "夜行风险", detail, player_id, {"kind": "night_outing", **record})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
