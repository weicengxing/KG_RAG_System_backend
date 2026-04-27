from datetime import datetime
import random

from game_config import *


class GameWeatherForecastMixin:
    def _weather_label(self, weather_key: str) -> str:
        return WEATHER_LABELS.get(weather_key, weather_key or "未知天气")

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
