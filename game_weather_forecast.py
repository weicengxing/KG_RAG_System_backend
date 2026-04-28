from datetime import datetime
import random

from game_config import *


WEATHER_TEMPER_MYTH_ACTIVE_MINUTES = 45
WEATHER_TEMPER_MYTH_LIMIT = 4
WEATHER_TEMPER_MYTH_PROFILES = {
    "rain": {"tabooKey": "no_hunt", "disasterKind": "flood", "interpretationKey": "trade", "effects": {"tabooObserveReward": {"food": 1}, "tabooBlessing": {"tradeReputation": 1}, "nightRiskRelief": 1, "caveFindsBonus": 1, "disasterProgress": 1}},
    "snow": {"tabooKey": "guard_fire", "disasterKind": "cold", "interpretationKey": "hearth", "effects": {"tabooObserveReward": {"wood": 1}, "tabooBlessing": {"renown": 1}, "nightRiskRelief": 1, "caveFindsBonus": 0, "disasterProgress": 1}},
    "fog": {"tabooKey": "harvest_dance", "disasterKind": "sickness", "interpretationKey": "trail", "effects": {"tabooObserveReward": {"discoveryProgress": 1}, "tabooBlessing": {"discoveryProgress": 1}, "nightRiskRelief": 2, "caveFindsBonus": 1, "disasterProgress": 0}},
    "sunny": {"tabooKey": "harvest_dance", "disasterKind": "wildfire", "interpretationKey": "trail", "effects": {"tabooObserveReward": {"renown": 1}, "tabooBlessing": {"food": 1}, "nightRiskRelief": 0, "caveFindsBonus": 1, "disasterProgress": 1}}
}


class GameWeatherForecastMixin:
    def _weather_label(self, weather_key: str) -> str:
        return WEATHER_LABELS.get(weather_key, weather_key or "未知天气")

    def _active_weather_tempers(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for temper in tribe.get("weather_tempers", []) or []:
            if not isinstance(temper, dict) or temper.get("status") not in ("active", "settled"):
                continue
            active_until = temper.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        temper["status"] = "expired"
                        continue
                except (TypeError, ValueError):
                    temper["status"] = "expired"
                    continue
            active.append(temper)
        tribe["weather_tempers"] = active[-TRIBE_WEATHER_TEMPER_LIMIT:]
        return tribe["weather_tempers"]

    def _active_weather_temper_biases(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for bias in tribe.get("weather_temper_biases", []) or []:
            if not isinstance(bias, dict) or bias.get("status") != "active":
                continue
            try:
                if datetime.fromisoformat(bias.get("activeUntil", "")) <= now:
                    bias["status"] = "expired"
                    continue
            except (TypeError, ValueError):
                bias["status"] = "expired"
                continue
            active.append(bias)
        tribe["weather_temper_biases"] = active[-TRIBE_WEATHER_TEMPER_LIMIT:]
        return tribe["weather_temper_biases"]

    def _public_weather_tempers(self, tribe: dict) -> list:
        return [dict(item) for item in self._active_weather_tempers(tribe)]

    def _public_weather_temper_actions(self) -> dict:
        return dict(TRIBE_WEATHER_TEMPER_ACTIONS)

    def _public_weather_temper_records(self, tribe: dict) -> list:
        records = [item for item in tribe.get("weather_temper_records", []) or [] if isinstance(item, dict)]
        return records[-TRIBE_WEATHER_TEMPER_RECORD_LIMIT:]

    def _active_weather_temper_myth_sources(self, tribe: dict) -> list:
        active = []
        now = datetime.now()
        for source in tribe.get("weather_temper_myth_sources", []) or []:
            if not isinstance(source, dict) or source.get("status", "active") != "active":
                continue
            try:
                if datetime.fromisoformat(source.get("activeUntil", "")) <= now:
                    source["status"] = "expired"
                    source["expiredAt"] = now.isoformat()
                    continue
            except (TypeError, ValueError):
                source["status"] = "expired"
                source["expiredAt"] = now.isoformat()
                continue
            active.append(source)
        tribe["weather_temper_myth_sources"] = active[-WEATHER_TEMPER_MYTH_LIMIT:]
        return tribe["weather_temper_myth_sources"]

    def _weather_temper_myth_source_for(self, tribe: dict, effect_key: str = "") -> dict | None:
        for source in reversed(self._active_weather_temper_myth_sources(tribe)):
            effects = source.get("effects", {}) or {}
            if not effect_key or effects.get(effect_key) or source.get(effect_key):
                return source
        return None

    def _weather_temper_myth_bonus(self, tribe: dict, effect_key: str) -> int:
        source = self._weather_temper_myth_source_for(tribe, effect_key)
        return max(0, int(((source or {}).get("effects", {}) or {}).get(effect_key, 0) or 0))

    def _weather_temper_taboo_context(self, tribe: dict, taboo_key: str) -> dict | None:
        for source in reversed(self._active_weather_temper_myth_sources(tribe)):
            if source.get("tabooKey") != taboo_key:
                continue
            effects = source.get("effects", {}) or {}
            return {
                "key": source.get("id"),
                "label": source.get("label", "天气脾气禁忌"),
                "summary": f"{source.get('summary', '')} 这段天气说法会改变禁忌践行的奖励。",
                "sourceLabel": source.get("label", "天气脾气"),
                "sourceKind": "weather_temper",
                "sourceId": source.get("id"),
                "x": source.get("x", 0),
                "z": source.get("z", 0),
                "observeReward": dict(effects.get("tabooObserveReward", {}) or {}),
                "blessing": dict(effects.get("tabooBlessing", {}) or {}),
                "mythSummary": f"{source.get('label', '天气脾气')}牵动禁忌后，族人开始争论这是火、路、市还是边界在借天气说话。"
            }
        return None

    def _maybe_awaken_weather_temper_myth(self, tribe: dict, temper: dict, member_name: str) -> list:
        if int(temper.get("score", 0) or 0) < int(temper.get("target", TRIBE_WEATHER_TEMPER_TARGET) or TRIBE_WEATHER_TEMPER_TARGET):
            return []
        weather = temper.get("weather", "sunny")
        profile = WEATHER_TEMPER_MYTH_PROFILES.get(weather, WEATHER_TEMPER_MYTH_PROFILES["sunny"])
        now = datetime.now()
        camp_center = (tribe.get("camp") or {}).get("center") or {}
        source_id = f"weather_temper:{weather}:{temper.get('label', '')}"
        active = self._active_weather_temper_myth_sources(tribe)
        source = next((item for item in active if item.get("sourceId") == source_id), None)
        base = {
            "status": "active",
            "sourceId": source_id,
            "sourceKind": "weather_temper",
            "label": f"{temper.get('label', '天气脾气')}神话源",
            "summary": f"{temper.get('label', '天气脾气')}被族人反复回应后，暂时成了禁忌、夜行、洞穴和灾后协作会引用的天气说法。",
            "weather": weather,
            "weatherLabel": temper.get("weatherLabel") or self._weather_label(weather),
            "tabooKey": profile.get("tabooKey"),
            "disasterKind": profile.get("disasterKind"),
            "interpretationKey": profile.get("interpretationKey", "trail"),
            "effects": dict(profile.get("effects", {}) or {}),
            "x": float(camp_center.get("x", 0) or 0),
            "z": float(camp_center.get("z", 0) or 0),
            "responseCount": int(temper.get("score", 0) or 0),
            "refreshedAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + WEATHER_TEMPER_MYTH_ACTIVE_MINUTES * 60).isoformat()
        }
        if source:
            source.update(base)
        else:
            source = {"id": f"weather_temper_myth_{tribe.get('id')}_{int(now.timestamp() * 1000)}", "createdAt": now.isoformat(), **base}
            active.append(source)
        tribe["weather_temper_myth_sources"] = active[-WEATHER_TEMPER_MYTH_LIMIT:]
        memory = self._record_map_memory(tribe, "weather_temper", source["label"], source["summary"], source["x"], source["z"], source["sourceId"], member_name) if hasattr(self, "_record_map_memory") else None
        claim = self._open_myth_claim(tribe, "weather_temper", source["label"], f"{source['label']}成为短时神话来源，族人争论它会怎样指向禁忌、夜路、洞口和灾后协作。", source["x"], source["z"], source["sourceId"], member_name) if hasattr(self, "_open_myth_claim") else None
        if claim:
            source["mythClaimId"] = claim.get("id")
        temper["mythSourceId"] = source.get("id")
        parts = ["天气神话来源+1"]
        if memory:
            parts.append("活地图记忆+1")
        if claim:
            parts.append("开启神话解释权")
        return parts

    def _active_weather_forecast(self, tribe: dict) -> dict | None:
        forecast = tribe.get("weather_forecast") if isinstance(tribe, dict) else None
        if not isinstance(forecast, dict) or forecast.get("status") != "pending":
            return None
        active_until = forecast.get("activeUntil")
        if active_until:
            try:
                if datetime.fromisoformat(active_until) <= datetime.now():
                    forecast["status"] = "expired"
                    return None
            except (TypeError, ValueError):
                forecast["status"] = "expired"
                return None
        return forecast

    def _public_weather_forecast(self, tribe: dict) -> dict | None:
        forecast = self._active_weather_forecast(tribe)
        if not forecast:
            return None
        observations = list(forecast.get("observations", []) or [])
        predicted_weather = forecast.get("predictedWeather", "")
        current_weather = forecast.get("currentWeather", "")
        return {
            "id": forecast.get("id"),
            "currentWeather": current_weather,
            "currentWeatherLabel": self._weather_label(current_weather),
            "predictedWeather": predicted_weather,
            "predictedWeatherLabel": self._weather_label(predicted_weather),
            "confidence": len(observations),
            "observationTarget": 2,
            "observerNames": [item.get("memberName", "成员") for item in observations][-6:],
            "signLabels": [item.get("signLabel", "迹象") for item in observations][-6:],
            "createdAt": forecast.get("createdAt"),
            "activeUntil": forecast.get("activeUntil")
        }

    def _public_weather_forecast_records(self, tribe: dict) -> list:
        records = [item for item in tribe.get("weather_forecast_records", []) or [] if isinstance(item, dict)]
        return records[-TRIBE_WEATHER_FORECAST_RECENT_LIMIT:]

    def _public_weather_forecast_signs(self) -> dict:
        return {
            key: {
                **config,
                "predictWeatherLabel": self._weather_label(config.get("predictWeather", ""))
            }
            for key, config in TRIBE_WEATHER_FORECAST_SIGNS.items()
        }

    def _forecast_prediction_from_observations(self, observations: list, fallback: str = "") -> str:
        counts = {}
        first_seen = {}
        for index, item in enumerate(observations or []):
            weather = item.get("predictWeather")
            if not weather:
                continue
            counts[weather] = counts.get(weather, 0) + 1
            first_seen.setdefault(weather, index)
        if not counts:
            return fallback
        return sorted(counts, key=lambda key: (-counts[key], first_seen.get(key, 999)))[0]

    def _apply_weather_temper_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        for key, label, tribe_key in (("food", "食物", "food"), ("renown", "声望", "renown"), ("discoveryProgress", "发现", "discovery_progress"), ("tradeReputation", "贸易信誉", "trade_reputation")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        return parts

    def _apply_weather_forecast_reward(self, tribe: dict, correct: bool, observer_count: int) -> list:
        reward_parts = []
        discovery = 1 if observer_count >= 1 else 0
        renown = 1 + min(2, observer_count // 2) if correct else 0
        trade = 1 if correct and observer_count >= 2 else 0
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        return reward_parts

    async def _maybe_spawn_weather_tempers(self, previous_weather: str, next_weather: str, ripple_label: str = "") -> int:
        if not ripple_label and previous_weather not in ("rain", "snow", "fog"):
            return 0
        profile = TRIBE_WEATHER_TEMPER_PROFILES.get(next_weather)
        if not profile:
            return 0
        created = 0
        now = datetime.now()
        for tribe_id, tribe in list(self.tribes.items()):
            if any(item.get("weather") == next_weather and item.get("status") == "active" for item in self._active_weather_tempers(tribe)):
                continue
            temper = {
                "id": f"weather_temper_{tribe_id}_{next_weather}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
                "status": "active",
                "weather": next_weather,
                "weatherLabel": self._weather_label(next_weather),
                "previousWeather": previous_weather,
                "previousWeatherLabel": self._weather_label(previous_weather),
                "label": profile.get("label", "天气脾气"),
                "summary": profile.get("summary", ""),
                "rippleLabel": ripple_label,
                "preferredWeather": profile.get("preferredWeather", "sunny"),
                "preferredWeatherLabel": self._weather_label(profile.get("preferredWeather", "sunny")),
                "responses": [],
                "score": 0,
                "target": TRIBE_WEATHER_TEMPER_TARGET,
                "createdAt": now.isoformat(),
                "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_WEATHER_TEMPER_ACTIVE_MINUTES * 60).isoformat()
            }
            tribe.setdefault("weather_tempers", []).append(temper)
            tribe["weather_tempers"] = tribe["weather_tempers"][-TRIBE_WEATHER_TEMPER_LIMIT:]
            detail = f"天气生出脾气：“{temper['label']}”。族人可用仪式或风向预判回应，影响下一轮天气叙事。"
            self._add_tribe_history(tribe, "world_event", "天气脾气", detail, "", {"kind": "weather_temper", "temper": temper})
            await self._notify_tribe(tribe_id, detail)
            await self.broadcast_tribe_state(tribe_id)
            created += 1
        return created

    def _apply_weather_temper_bias(self, candidates: list) -> list:
        biased = list(candidates)
        for tribe in self.tribes.values():
            for bias in self._active_weather_temper_biases(tribe):
                weather = bias.get("biasWeather")
                if weather in candidates:
                    biased.extend([weather] * max(1, int(bias.get("weight", 2) or 2)))
        return biased

    def _settle_weather_temper_biases(self, next_weather: str):
        now_text = datetime.now().isoformat()
        for tribe in self.tribes.values():
            for bias in self._active_weather_temper_biases(tribe):
                if bias.get("biasWeather") == next_weather:
                    bias["status"] = "used"
                    bias["usedAt"] = now_text

    async def respond_weather_temper(self, player_id: str, temper_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_WEATHER_TEMPER_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知天气回应")
            return
        temper = next((item for item in self._active_weather_tempers(tribe) if item.get("id") == temper_id and item.get("status") == "active"), None)
        if not temper:
            await self._send_tribe_error(player_id, "这段天气脾气已经散去")
            return
        responses = temper.setdefault("responses", [])
        if any(item.get("memberId") == player_id for item in responses):
            await self._send_tribe_error(player_id, "你已经回应过这段天气脾气")
            return
        member = tribe.get("members", {}).get(player_id, {})
        now = datetime.now()
        bias_weather = temper.get("preferredWeather") if action.get("usePreferredWeather") else action.get("biasWeather", "sunny")
        responses.append({"memberId": player_id, "memberName": member.get("name", "成员"), "actionKey": action_key, "actionLabel": action.get("label", "回应"), "biasWeather": bias_weather, "createdAt": now.isoformat()})
        temper["score"] = len(responses)
        reward_parts = self._apply_weather_temper_reward(tribe, action.get("reward", {}))
        detail = f"{member.get('name', '成员')}用{action.get('label', '回应')}回应“{temper.get('label', '天气脾气')}”，下一轮更可能转向{self._weather_label(bias_weather)}。"
        if int(temper.get("score", 0) or 0) >= int(temper.get("target", TRIBE_WEATHER_TEMPER_TARGET) or TRIBE_WEATHER_TEMPER_TARGET):
            temper["status"] = "settled"
            temper["settledAt"] = now.isoformat()
            bias = {"id": f"weather_temper_bias_{tribe_id}_{int(now.timestamp() * 1000)}", "status": "active", "temperId": temper_id, "label": temper.get("label"), "biasWeather": bias_weather, "biasWeatherLabel": self._weather_label(bias_weather), "weight": 3, "createdByName": member.get("name", "成员"), "createdAt": now.isoformat(), "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_WEATHER_TEMPER_ACTIVE_MINUTES * 60).isoformat()}
            tribe.setdefault("weather_temper_biases", []).append(bias)
            reward_parts.extend(self._maybe_awaken_weather_temper_myth(tribe, temper, member.get("name", "成员")))
            record = {**temper, "id": f"weather_temper_record_{tribe_id}_{int(now.timestamp() * 1000)}", "actionLabel": action.get("label"), "bias": bias, "rewardParts": reward_parts}
            tribe.setdefault("weather_temper_records", []).append(record)
            tribe["weather_temper_records"] = tribe["weather_temper_records"][-TRIBE_WEATHER_TEMPER_RECORD_LIMIT:]
            detail += f" 天气脾气被暂时安置。{'、'.join(reward_parts) if reward_parts else ''}"
            await self._publish_world_rumor("world_event", "天气脾气被回应", f"{tribe.get('name', '部落')}用{action.get('label', '回应')}回应了{temper.get('weatherLabel', '天气')}的脾气。", {"tribeId": tribe_id, "temperId": temper_id, "biasWeather": bias_weather})
        self._add_tribe_history(tribe, "world_event", "回应天气脾气", detail, player_id, {"kind": "weather_temper_response", "temper": temper, "actionKey": action_key, "biasWeather": bias_weather})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def observe_weather_sign(self, player_id: str, sign_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        sign = TRIBE_WEATHER_FORECAST_SIGNS.get(sign_key)
        if not sign:
            await self._send_tribe_error(player_id, "未知天气迹象")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        forecast = self._active_weather_forecast(tribe)
        now = datetime.now()
        if not forecast:
            env = self._get_current_environment() if hasattr(self, "_get_current_environment") else {}
            current_weather = env.get("weather", "sunny")
            forecast = {
                "id": f"weather_forecast_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
                "status": "pending",
                "currentWeather": current_weather,
                "predictedWeather": sign.get("predictWeather", "sunny"),
                "observations": [],
                "createdAt": now.isoformat(),
                "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_WEATHER_FORECAST_ACTIVE_MINUTES * 60).isoformat()
            }
            tribe["weather_forecast"] = forecast

        observations = forecast.setdefault("observations", [])
        if any(item.get("memberId") == player_id for item in observations):
            await self._send_tribe_error(player_id, "你已经参与了这轮风向预判")
            return
        observations.append({
            "memberId": player_id,
            "memberName": member_name,
            "signKey": sign_key,
            "signLabel": sign.get("label", "天气迹象"),
            "predictWeather": sign.get("predictWeather", "sunny"),
            "createdAt": now.isoformat()
        })
        forecast["predictedWeather"] = self._forecast_prediction_from_observations(observations, forecast.get("predictedWeather", "sunny"))
        forecast["updatedAt"] = now.isoformat()
        detail = f"{member_name} 观察“{sign.get('label', '天气迹象')}”，判断下一轮可能是{self._weather_label(forecast.get('predictedWeather'))}。"
        self._add_tribe_history(tribe, "world_event", "风向预判", detail, player_id, {"kind": "weather_forecast", "signKey": sign_key, "forecastId": forecast.get("id")})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def _resolve_weather_forecasts(self, next_weather: str, previous_weather: str = "") -> int:
        resolved = 0
        for tribe_id, tribe in list(self.tribes.items()):
            forecast = self._active_weather_forecast(tribe)
            if not forecast:
                continue
            observations = list(forecast.get("observations", []) or [])
            if not observations:
                forecast["status"] = "expired"
                continue
            predicted = forecast.get("predictedWeather") or self._forecast_prediction_from_observations(observations, "")
            correct = predicted == next_weather
            reward_parts = self._apply_weather_forecast_reward(tribe, correct, len(observations))
            if correct and hasattr(self, "apply_tribe_law_event_bonus"):
                reward_parts.extend(self.apply_tribe_law_event_bonus(tribe, "weather_forecast", "风向预判"))
            now_text = datetime.now().isoformat()
            record = {
                "id": f"weather_record_{forecast.get('id')}_{int(datetime.now().timestamp())}",
                "forecastId": forecast.get("id"),
                "predictedWeather": predicted,
                "predictedWeatherLabel": self._weather_label(predicted),
                "actualWeather": next_weather,
                "actualWeatherLabel": self._weather_label(next_weather),
                "previousWeather": previous_weather,
                "previousWeatherLabel": self._weather_label(previous_weather),
                "correct": correct,
                "observerNames": [item.get("memberName", "成员") for item in observations][-6:],
                "signLabels": [item.get("signLabel", "迹象") for item in observations][-6:],
                "rewardParts": reward_parts,
                "createdAt": now_text
            }
            forecast["status"] = "resolved"
            forecast["resolvedAt"] = now_text
            forecast["actualWeather"] = next_weather
            tribe["weather_forecast"] = None
            tribe.setdefault("weather_forecast_records", []).append(record)
            tribe["weather_forecast_records"] = tribe["weather_forecast_records"][-TRIBE_WEATHER_FORECAST_RECENT_LIMIT:]
            result_text = "命中" if correct else "偏离"
            reward_text = f" 收获：{'、'.join(reward_parts)}。" if reward_parts else ""
            detail = f"风向预判{result_text}：族人猜测{record['predictedWeatherLabel']}，实际转为{record['actualWeatherLabel']}。{reward_text}"
            self._add_tribe_history(tribe, "world_event", "风向预判结算", detail, "", {"kind": "weather_forecast_result", **record})
            if correct:
                await self._publish_world_rumor(
                    "world_event",
                    "风向预判命中",
                    f"{tribe.get('name', '部落')} 提前读懂了{record['actualWeatherLabel']}，天气记录开始被其他营地提起。",
                    {"tribeId": tribe_id, "forecastId": forecast.get("id"), "weather": next_weather}
                )
            await self._notify_tribe(tribe_id, detail)
            await self.broadcast_tribe_state(tribe_id)
            resolved += 1
        if resolved:
            self._save_tribe_state()
        return resolved
