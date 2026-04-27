from datetime import datetime
import random

from game_config import (
    CELESTIAL_BRANCHES,
    CELESTIAL_WINDOW_DURATION_MINUTES,
    CELESTIAL_WINDOWS,
    SEASON_LEGEND_TITLES,
    TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD,
)


class GameCelestialMixin:
    def _active_celestial_window(self, env: dict) -> dict | None:
        window = env.get("celestialWindow") if isinstance(env, dict) else None
        if not isinstance(window, dict):
            return None
        active_until = window.get("activeUntil")
        if not active_until:
            return None
        try:
            if datetime.fromisoformat(active_until) <= datetime.now():
                return None
        except (TypeError, ValueError):
            return None
        return window

    def _build_celestial_window(self, env: dict | None = None) -> dict:
        plan = self._weather_rng.choice(CELESTIAL_WINDOWS)
        regions = (env or {}).get("regions") or []
        region = self._weather_rng.choice(regions) if regions else {"id": "sky", "label": "天空", "x": 0, "z": 0, "radius": 120}
        now = datetime.now()
        return {
            "id": f"celestial_{plan.get('key', 'sky')}_{int(now.timestamp())}_{self._weather_rng.randint(100, 999)}",
            "key": plan.get("key", "sky"),
            "title": plan.get("title", "罕见天象"),
            "summary": plan.get("summary", "天空出现短暂异象，所有部落都能把它写进本赛季传说。"),
            "branchKeys": list(plan.get("branchKeys") or CELESTIAL_BRANCHES.keys()),
            "regionId": region.get("id", "sky"),
            "regionLabel": region.get("label", "天空"),
            "x": region.get("x", 0),
            "z": region.get("z", 0),
            "radius": max(120, int(region.get("radius", 80) or 80)),
            "firstExplorerTribeId": "",
            "firstExplorerTribeName": "",
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + CELESTIAL_WINDOW_DURATION_MINUTES * 60).isoformat()
        }

    def _public_celestial_window(self, tribe: dict) -> dict | None:
        map_data = self.maps.get(self.current_map_name) or {}
        env = map_data.get("environment") or {}
        window = self._active_celestial_window(env)
        if not window:
            return None
        read_ids = set(tribe.get("celestial_window_ids", []) or [])
        branches = []
        for key in window.get("branchKeys", []) or []:
            branch = CELESTIAL_BRANCHES.get(key)
            if not branch:
                continue
            reward = dict(branch.get("reward") or {})
            if key == "first_explorer" and not window.get("firstExplorerTribeId"):
                for reward_key, amount in (branch.get("firstReward") or {}).items():
                    reward[reward_key] = int(reward.get(reward_key, 0) or 0) + int(amount or 0)
            branches.append({
                "key": key,
                "label": branch.get("label", key),
                "summary": branch.get("summary", ""),
                "rewardLabel": self._reward_summary_text(reward)
            })
        return {
            "id": window.get("id"),
            "key": window.get("key"),
            "title": window.get("title"),
            "summary": window.get("summary"),
            "regionLabel": window.get("regionLabel"),
            "activeUntil": window.get("activeUntil"),
            "alreadyRead": window.get("id") in read_ids,
            "firstExplorerTribeName": window.get("firstExplorerTribeName"),
            "branches": branches
        }

    def _public_celestial_records(self, tribe: dict) -> list:
        records = [record for record in tribe.get("celestial_records", []) or [] if isinstance(record, dict)]
        return records[-5:]

    def _public_season_legend_scores(self, tribe: dict) -> list:
        scores = tribe.get("season_legend_scores", {}) or {}
        public_scores = []
        for key, config in SEASON_LEGEND_TITLES.items():
            score = int(scores.get(key, {}).get("score", 0) if isinstance(scores.get(key), dict) else scores.get(key, 0) or 0)
            if score <= 0:
                continue
            actors = scores.get(key, {}).get("actors", []) if isinstance(scores.get(key), dict) else []
            public_scores.append({
                "key": key,
                "title": config.get("title", key),
                "summary": config.get("summary", ""),
                "score": score,
                "actors": list(actors or [])[-4:]
            })
        return sorted(public_scores, key=lambda item: item.get("score", 0), reverse=True)

    def _apply_celestial_reward(self, tribe: dict, reward: dict) -> list:
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
            tribe["trade_reputation"] = max(0, int(tribe.get("trade_reputation", 0) or 0) + trade)
            reward_parts.append(f"贸易信誉+{trade}")
        renown = int((reward or {}).get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        return reward_parts

    def _apply_celestial_relations(self, tribe: dict, branch: dict) -> list:
        relation_parts = []
        relation_delta = int(branch.get("relationDelta", 0) or 0)
        trust_delta = int(branch.get("tradeTrustDelta", 0) or 0)
        pressure_relief = int(branch.get("pressureRelief", 0) or 0)
        war_pressure = int(branch.get("warPressure", 0) or 0)
        if not any((relation_delta, trust_delta, pressure_relief, war_pressure)):
            return relation_parts
        now_text = datetime.now().isoformat()
        relations = tribe.setdefault("boundary_relations", {})
        if not relations and len(self.tribes) > 1:
            for other_id in self.tribes:
                if other_id != tribe.get("id"):
                    relations.setdefault(other_id, {})
        for other_id, relation in list(relations.items()):
            if not isinstance(relation, dict) or other_id == tribe.get("id"):
                continue
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
            if pressure_relief:
                relation["warPressure"] = max(0, int(relation.get("warPressure", 0) or 0) - pressure_relief)
            if war_pressure:
                relation["warPressure"] = min(
                    TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD,
                    int(relation.get("warPressure", 0) or 0) + war_pressure
                )
            relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
            relation["lastAction"] = f"celestial_{branch.get('legendKey', 'window')}"
            relation["lastActionAt"] = now_text
        if relation_delta:
            relation_parts.append(f"关系{relation_delta:+d}")
        if trust_delta:
            relation_parts.append(f"信任+{trust_delta}")
        if pressure_relief:
            relation_parts.append(f"战争压力-{pressure_relief}")
        if war_pressure:
            relation_parts.append(f"战争压力+{war_pressure}")
        return relation_parts

    def _record_season_legend_score(self, tribe: dict, legend_key: str, actor_name: str, amount: int = 1):
        if not legend_key:
            return
        scores = tribe.setdefault("season_legend_scores", {})
        record = scores.setdefault(legend_key, {"score": 0, "actors": []})
        record["score"] = int(record.get("score", 0) or 0) + max(1, int(amount or 1))
        if actor_name:
            actors = list(record.get("actors", []) or [])
            if actor_name not in actors:
                actors.append(actor_name)
            record["actors"] = actors[-5:]

    async def choose_celestial_branch(self, player_id: str, window_id: str, branch_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        map_data = self.maps.get(self.current_map_name) or {}
        env = map_data.get("environment") or {}
        window = self._active_celestial_window(env)
        if not window or window.get("id") != window_id:
            await self._send_tribe_error(player_id, "这次天象窗口已经结束")
            return
        if window_id in set(tribe.get("celestial_window_ids", []) or []):
            await self._send_tribe_error(player_id, "本部落已经解读过这次天象")
            return
        if branch_key not in (window.get("branchKeys") or []):
            await self._send_tribe_error(player_id, "这条天象分支不可用")
            return
        branch = CELESTIAL_BRANCHES.get(branch_key)
        if not branch:
            await self._send_tribe_error(player_id, "未知天象分支")
            return

        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        reward = dict(branch.get("reward") or {})
        first_explorer = False
        if branch_key == "first_explorer" and not window.get("firstExplorerTribeId"):
            first_explorer = True
            window["firstExplorerTribeId"] = tribe_id
            window["firstExplorerTribeName"] = tribe.get("name", "部落")
            for reward_key, amount in (branch.get("firstReward") or {}).items():
                reward[reward_key] = int(reward.get(reward_key, 0) or 0) + int(amount or 0)

        reward_parts = self._apply_celestial_reward(tribe, reward)
        relation_parts = self._apply_celestial_relations(tribe, branch)
        legend_key = branch.get("legendKey")
        self._record_season_legend_score(tribe, legend_key, member_name, 2 if first_explorer else 1)
        tribe.setdefault("celestial_window_ids", []).append(window_id)
        tribe["celestial_window_ids"] = list(dict.fromkeys(tribe["celestial_window_ids"]))[-12:]
        record = {
            "id": f"celestial_record_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "windowId": window_id,
            "windowTitle": window.get("title"),
            "branchKey": branch_key,
            "branchLabel": branch.get("label", branch_key),
            "legendKey": legend_key,
            "legendTitle": SEASON_LEGEND_TITLES.get(legend_key, {}).get("title", ""),
            "actorName": member_name,
            "rewardParts": reward_parts + relation_parts,
            "firstExplorer": first_explorer,
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("celestial_records", []).append(record)
        tribe["celestial_records"] = tribe["celestial_records"][-8:]
        map_data["environment"] = env
        map_data["updated_at"] = datetime.now().isoformat()

        first_text = "，抢先写下首探者记录" if first_explorer else ""
        reward_text = f" 收获：{'、'.join(record['rewardParts'])}。" if record["rewardParts"] else ""
        detail = f"{member_name} 在{window.get('title', '罕见天象')}下选择“{branch.get('label', branch_key)}”{first_text}。{reward_text}"
        self._add_tribe_history(tribe, "ritual", "天象解读", detail, player_id, {"kind": "celestial_window", **record})
        await self._publish_world_rumor(
            "celestial",
            f"{window.get('title', '天象')}被解读",
            f"{tribe.get('name', '部落')} 选择“{branch.get('label', branch_key)}”，本赛季传说出现新的说法。",
            {"tribeId": tribe_id, "windowId": window_id, "branchKey": branch_key, "legendKey": legend_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    def _history_keyword_score(self, tribe: dict, keywords: list) -> int:
        score = 0
        for item in tribe.get("history", []) or []:
            if not isinstance(item, dict):
                continue
            text = f"{item.get('title', '')} {item.get('detail', '')}"
            score += sum(1 for keyword in keywords if keyword and keyword in text)
        return score

    def _build_season_legend_awards(self) -> list:
        awards = []
        for legend_key, config in SEASON_LEGEND_TITLES.items():
            candidates = []
            for tribe in self.tribes.values():
                scores = tribe.get("season_legend_scores", {}) or {}
                record = scores.get(legend_key, {}) if isinstance(scores.get(legend_key), dict) else {"score": scores.get(legend_key, 0)}
                score = int(record.get("score", 0) or 0)
                score += self._history_keyword_score(tribe, config.get("keywords", []))
                if score <= 0:
                    continue
                candidates.append({
                    "titleKey": legend_key,
                    "title": config.get("title", legend_key),
                    "summary": config.get("summary", ""),
                    "tribeId": tribe.get("id"),
                    "tribeName": tribe.get("name", "部落"),
                    "score": score,
                    "actors": list(record.get("actors", []) or [])[-5:]
                })
            if candidates:
                candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
                awards.append(candidates[0])
        return awards
