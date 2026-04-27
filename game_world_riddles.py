from datetime import datetime
import math
import random

from game_config import *


class GameWorldRiddleMixin:
    def _active_world_riddles(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for riddle in tribe.get("world_riddles", []) or []:
            if not isinstance(riddle, dict) or riddle.get("status") != "active":
                continue
            active_until = riddle.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        riddle["status"] = "expired"
                        riddle["expiredAt"] = now.isoformat()
                        continue
                except (TypeError, ValueError):
                    riddle["status"] = "expired"
                    riddle["expiredAt"] = now.isoformat()
                    continue
            active.append(riddle)
        if len(active) != len(tribe.get("world_riddles", []) or []):
            tribe["world_riddles"] = active[-TRIBE_WORLD_RIDDLE_LIMIT:]
        return active[-TRIBE_WORLD_RIDDLE_LIMIT:]

    def _active_world_riddle_influences(self, tribe: dict) -> list:
        if not tribe:
            return []
        now = datetime.now()
        active = []
        for influence in tribe.get("world_riddle_influences", []) or []:
            if not isinstance(influence, dict) or influence.get("used"):
                continue
            active_until = influence.get("activeUntil")
            if active_until:
                try:
                    if datetime.fromisoformat(active_until) <= now:
                        continue
                except (TypeError, ValueError):
                    continue
            active.append(influence)
        if len(active) != len(tribe.get("world_riddle_influences", []) or []):
            tribe["world_riddle_influences"] = active[-TRIBE_WORLD_RIDDLE_INFLUENCE_LIMIT:]
        return active[-TRIBE_WORLD_RIDDLE_INFLUENCE_LIMIT:]

    def _public_world_riddles(self, tribe: dict) -> list:
        riddles = []
        for riddle in self._active_world_riddles(tribe):
            riddles.append({
                "id": riddle.get("id"),
                "type": riddle.get("type", "world_riddle_site"),
                "title": riddle.get("title", "世界谜语"),
                "label": riddle.get("label", "世界谜语"),
                "summary": riddle.get("summary", ""),
                "patternLabel": riddle.get("patternLabel", ""),
                "regionLabel": riddle.get("regionLabel", ""),
                "x": riddle.get("x", 0),
                "z": riddle.get("z", 0),
                "radius": int(riddle.get("radius", TRIBE_WORLD_RIDDLE_RADIUS) or TRIBE_WORLD_RIDDLE_RADIUS),
                "rewardLabel": riddle.get("rewardLabel", ""),
                "activeUntil": riddle.get("activeUntil"),
                "observations": list(riddle.get("observations", []) or [])[-3:]
            })
        return riddles

    def _public_world_riddle_predictions(self) -> dict:
        return TRIBE_WORLD_RIDDLE_PREDICTIONS

    def _public_world_riddle_influences(self, tribe: dict) -> list:
        return self._active_world_riddle_influences(tribe)

    def _public_world_riddle_records(self, tribe: dict) -> list:
        return [item for item in tribe.get("world_riddle_records", []) or [] if isinstance(item, dict)][-TRIBE_WORLD_RIDDLE_RECORD_LIMIT:]

    def _apply_world_riddle_reward(self, tribe: dict, reward: dict) -> list:
        return self._apply_tribe_reward(tribe, reward)

    def _build_world_riddle(self, tribe: dict, env: dict) -> dict:
        rng = getattr(self, "_weather_rng", None) or random
        pattern = rng.choice(TRIBE_WORLD_RIDDLE_PATTERNS)
        regions = env.get("regions") or WORLD_REGIONS
        region = rng.choice(regions) if regions else {"id": "camp", "label": "营地外缘", "x": 0, "z": 0, "radius": 90}
        angle = rng.random() * math.tau
        distance = min(36, max(12, float(region.get("radius", 60) or 60) * 0.35))
        x = max(-490, min(490, float(region.get("x", 0) or 0) + math.cos(angle) * distance))
        z = max(-490, min(490, float(region.get("z", 0) or 0) + math.sin(angle) * distance))
        now = datetime.now()
        reward = dict(pattern.get("reward", {}) or {})
        return {
            "id": f"world_riddle_{tribe.get('id')}_{pattern.get('key')}_{int(now.timestamp() * 1000)}_{rng.randint(100, 999)}",
            "type": "world_riddle_site",
            "status": "active",
            "key": pattern.get("key", "riddle"),
            "title": pattern.get("title", "世界谜语"),
            "label": pattern.get("label", "世界谜语"),
            "summary": pattern.get("summary", "地面、风声和石影排成了短暂规律。"),
            "patternLabel": pattern.get("patternLabel", ""),
            "answerKey": pattern.get("answerKey", "sky"),
            "influenceKind": pattern.get("influenceKind", "celestial"),
            "influenceLabel": pattern.get("influenceLabel", "谜语牵引"),
            "regionId": region.get("id", "region"),
            "regionLabel": region.get("label", "附近区域"),
            "x": x,
            "z": z,
            "y": 0,
            "size": 0.95,
            "radius": TRIBE_WORLD_RIDDLE_RADIUS,
            "reward": reward,
            "rewardLabel": self._reward_summary_text(reward) if hasattr(self, "_reward_summary_text") else "",
            "observations": [],
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_WORLD_RIDDLE_ACTIVE_MINUTES * 60).isoformat()
        }

    async def _maybe_spawn_world_riddles(self) -> int:
        if not self.tribes:
            return 0
        rng = getattr(self, "_weather_rng", None) or random
        map_data = self.maps.get(self.current_map_name) or {}
        env = map_data.get("environment") or {}
        spawned = 0
        for tribe_id, tribe in self.tribes.items():
            if self._active_world_riddles(tribe):
                continue
            if rng.random() >= TRIBE_WORLD_RIDDLE_SPAWN_CHANCE:
                continue
            riddle = self._build_world_riddle(tribe, env)
            tribe["world_riddles"] = [*self._active_world_riddles(tribe), riddle][-TRIBE_WORLD_RIDDLE_LIMIT:]
            spawned += 1
            await self._notify_tribe(
                tribe_id,
                f"{riddle.get('regionLabel', '营地外缘')}出现{riddle.get('title', '世界谜语')}，靠近后可提交一次预测。"
            )
        return spawned

    def _world_riddle_chance_bonus(self, influence_kind: str) -> float:
        total = 0
        for tribe in self.tribes.values():
            total += sum(1 for item in self._active_world_riddle_influences(tribe) if item.get("kind") == influence_kind)
        return min(TRIBE_WORLD_RIDDLE_INFLUENCE_MAX_BONUS, total * TRIBE_WORLD_RIDDLE_INFLUENCE_BONUS)

    def _mark_world_riddle_influence_used(self, influence_kind: str, used_label: str):
        for tribe in self.tribes.values():
            for influence in self._active_world_riddle_influences(tribe):
                if influence.get("kind") != influence_kind:
                    continue
                influence["used"] = True
                influence["usedLabel"] = used_label
                influence["usedAt"] = datetime.now().isoformat()
                return influence
        return None

    async def solve_world_riddle(self, player_id: str, riddle_id: str, prediction_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        prediction = TRIBE_WORLD_RIDDLE_PREDICTIONS.get(prediction_key)
        if not prediction:
            await self._send_tribe_error(player_id, "未知谜语预测")
            return
        riddles = self._active_world_riddles(tribe)
        riddle = next((item for item in riddles if item.get("id") == riddle_id), None)
        if not riddle:
            await self._send_tribe_error(player_id, "这处世界谜语已经散去")
            return

        player = self.players.get(player_id, {})
        dx = float(player.get("x", 0) or 0) - float(riddle.get("x", 0) or 0)
        dz = float(player.get("z", 0) or 0) - float(riddle.get("z", 0) or 0)
        if math.sqrt(dx * dx + dz * dz) > float(riddle.get("radius", TRIBE_WORLD_RIDDLE_RADIUS) or TRIBE_WORLD_RIDDLE_RADIUS):
            await self._send_tribe_error(player_id, "需要靠近谜语地标才能提交预测")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name") or player.get("name") or "成员"
        success = prediction_key == riddle.get("answerKey")
        reward_parts = []
        memory = None
        influence = None
        if success:
            reward_parts = self._apply_world_riddle_reward(tribe, riddle.get("reward", {}))
            now = datetime.now()
            influence = {
                "id": f"world_riddle_influence_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
                "kind": riddle.get("influenceKind", "celestial"),
                "label": riddle.get("influenceLabel", "谜语牵引"),
                "summary": f"{member_name}读准了{riddle.get('title', '世界谜语')}，下一轮相关天象或稀有事件更容易被牵引。",
                "sourceRiddleId": riddle.get("id"),
                "sourceTitle": riddle.get("title"),
                "createdByName": member_name,
                "createdAt": now.isoformat(),
                "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_WORLD_RIDDLE_INFLUENCE_MINUTES * 60).isoformat()
            }
            tribe.setdefault("world_riddle_influences", []).append(influence)
            tribe["world_riddle_influences"] = tribe["world_riddle_influences"][-TRIBE_WORLD_RIDDLE_INFLUENCE_LIMIT:]
            reward_parts.append(influence.get("label", "谜语牵引"))
        else:
            memory = self._record_map_memory(
                tribe,
                "world_riddle_miss",
                f"{riddle.get('label', '世界谜语')}错读旧痕",
                f"{member_name}没有猜中{riddle.get('title', '世界谜语')}，但把符号、声响和石影的错路也留给后来者。",
                float(riddle.get("x", 0) or 0),
                float(riddle.get("z", 0) or 0),
                riddle.get("id", ""),
                member_name
            )
            if memory:
                reward_parts.append("活地图记忆+1")

        answer = TRIBE_WORLD_RIDDLE_PREDICTIONS.get(riddle.get("answerKey"), {})
        observation = {
            "memberId": player_id,
            "memberName": member_name,
            "predictionKey": prediction_key,
            "predictionLabel": prediction.get("label", prediction_key),
            "answerLabel": answer.get("label", riddle.get("answerKey")),
            "correct": success,
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        riddle.setdefault("observations", []).append(observation)
        riddle["status"] = "resolved"
        riddle["resolvedAt"] = datetime.now().isoformat()
        riddle["resolvedByName"] = member_name
        riddle["predictionLabel"] = prediction.get("label", prediction_key)
        tribe["world_riddles"] = [item for item in riddles if item.get("id") != riddle_id]

        record = {
            "id": f"world_riddle_record_{tribe_id}_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "title": riddle.get("title", "世界谜语"),
            "patternLabel": riddle.get("patternLabel", ""),
            "regionLabel": riddle.get("regionLabel", ""),
            "memberName": member_name,
            "predictionLabel": prediction.get("label", prediction_key),
            "answerLabel": answer.get("label", riddle.get("answerKey")),
            "correct": success,
            "rewardParts": reward_parts,
            "memoryId": memory.get("id") if memory else "",
            "influenceId": influence.get("id") if influence else "",
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("world_riddle_records", []).append(record)
        tribe["world_riddle_records"] = tribe["world_riddle_records"][-TRIBE_WORLD_RIDDLE_RECORD_LIMIT:]

        if success:
            detail = f"{member_name}读准{riddle.get('title', '世界谜语')}，把它预测为{prediction.get('label', prediction_key)}。收获：{'、'.join(reward_parts) or '新的牵引'}。"
            await self._publish_world_rumor(
                "world_event",
                "世界谜语被读准",
                f"{tribe.get('name', '部落')}在{riddle.get('regionLabel', '野地')}读准{riddle.get('title', '世界谜语')}，下一轮异象更容易被引来。",
                {"tribeId": tribe_id, "recordId": record.get("id")}
            )
        else:
            detail = f"{member_name}错读{riddle.get('title', '世界谜语')}，猜成{prediction.get('label', prediction_key)}；真正指向{answer.get('label', riddle.get('answerKey'))}。错路已留下活地图记忆。"
        self._add_tribe_history(tribe, "world_event", "世界谜语预测", detail, player_id, {"kind": "world_riddle", "record": record, "riddle": riddle})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
