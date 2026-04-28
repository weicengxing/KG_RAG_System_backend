from datetime import datetime, timedelta

from game_config import *


TRIBE_FESTIVAL_TRADITION_THRESHOLD = 2
TRIBE_FESTIVAL_TRADITION_LIMIT = 6
TRIBE_FESTIVAL_TRADITION_PROFILES = {
    "rescue_day": {"title": "救援日传统", "summary": "营地习惯把危急时刻讲成互助节日。", "visitorLine": "来访者会听见这里逢难互援的节日口风。", "newcomerContext": "forbidden_edge", "newcomerLine": "新人命运会更容易被护送和救援传统接住。", "seasonTitle": "救援日守望者"},
    "market_day": {"title": "互市日传统", "summary": "交换、账记和口信被部落固定成临时市集礼法。", "visitorLine": "来访者会把这里先讲成能交换、能还信的营地。", "newcomerContext": "diplomacy", "newcomerLine": "新人命运在外交接待里多一层互市解释。", "seasonTitle": "互市日掌摊者"},
    "border_night": {"title": "守边夜传统", "summary": "边界紧张被反复整理成守夜和巡望。", "visitorLine": "来访者进营前会先听见守边夜的规矩。", "newcomerContext": "forbidden_edge", "newcomerLine": "新人命运遇到禁地和边界时会多一层守夜支撑。", "seasonTitle": "守边夜巡火者"},
    "old_song_day": {"title": "旧歌日传统", "summary": "故事、曲牌和口述史会被固定到节日传唱里。", "visitorLine": "来访者会听见这里用旧歌解释新事。", "newcomerContext": "exploration", "newcomerLine": "新人命运里的小发现会更容易被旧歌接住。", "seasonTitle": "旧歌日传唱者"}
}


class GameTribeFestivalMixin:
    def _tribe_festival_expired(self, festival: dict) -> bool:
        try:
            return datetime.fromisoformat(festival.get("activeUntil", "")) <= datetime.now()
        except (TypeError, ValueError):
            return False

    def _tribe_festival_signature(self, source_ids: list) -> str:
        return "|".join([str(item) for item in source_ids[-5:] if item])

    def _tribe_festival_profile_score(self, tribe: dict, key: str, profile: dict) -> dict:
        event_types = set(profile.get("eventTypes", []) or [])
        keywords = [str(item) for item in (profile.get("keywords", []) or []) if item]
        sources = []
        for record in (tribe.get("history", []) or [])[-TRIBE_FESTIVAL_HISTORY_SCAN_LIMIT:]:
            if not isinstance(record, dict):
                continue
            haystack = f"{record.get('type', '')} {record.get('title', '')} {record.get('detail', '')}"
            type_match = record.get("type") in event_types
            keyword_match = any(keyword in haystack for keyword in keywords)
            if not type_match and not keyword_match:
                continue
            sources.append({
                "id": record.get("id", ""),
                "title": record.get("title", profile.get("sourceLabel", key)),
                "type": record.get("type", "")
            })
        return {
            "key": key,
            "profile": profile,
            "score": len(sources),
            "sources": sources,
            "signature": self._tribe_festival_signature([item.get("id", "") for item in sources])
        }

    def _ensure_tribe_festivals(self, tribe: dict):
        if not tribe:
            return
        now = datetime.now()
        festivals = []
        for festival in tribe.get("tribe_festivals", []) or []:
            if not isinstance(festival, dict):
                continue
            if festival.get("status") == "active" and self._tribe_festival_expired(festival):
                festival["status"] = "expired"
                festival["endedAt"] = now.isoformat()
            festivals.append(festival)
        tribe["tribe_festivals"] = festivals[-TRIBE_FESTIVAL_LIMIT:]

        active = [
            item for item in tribe.get("tribe_festivals", []) or []
            if isinstance(item, dict) and item.get("status") == "active"
        ]
        if len(active) >= 1:
            return

        marks = set(tribe.setdefault("festival_marks", []) or [])
        candidates = [
            self._tribe_festival_profile_score(tribe, key, profile)
            for key, profile in TRIBE_FESTIVAL_PROFILES.items()
        ]
        candidates.sort(key=lambda item: (-int(item.get("score", 0) or 0), item.get("key", "")))
        for candidate in candidates:
            if int(candidate.get("score", 0) or 0) < TRIBE_FESTIVAL_SOURCE_TARGET:
                return
            mark = f"{candidate.get('key')}:{candidate.get('signature')}"
            if not candidate.get("signature") or mark in marks:
                continue
            profile = candidate.get("profile", {})
            active_until = (now + timedelta(minutes=TRIBE_FESTIVAL_ACTIVE_MINUTES)).isoformat()
            festival = {
                "id": f"tribe_festival_{tribe.get('id', 'tribe')}_{int(now.timestamp() * 1000)}",
                "key": candidate.get("key", ""),
                "status": "active",
                "title": profile.get("title", "部落节日"),
                "summary": profile.get("summary", ""),
                "sourceLabel": profile.get("sourceLabel", "近期行为"),
                "activityLabel": profile.get("activityLabel", "参与节日"),
                "sourceScore": candidate.get("score", 0),
                "sourceTitles": [item.get("title", "") for item in candidate.get("sources", [])][-5:],
                "sourceSignature": candidate.get("signature", ""),
                "participants": {},
                "progress": 0,
                "target": TRIBE_FESTIVAL_ACTIVITY_TARGET,
                "reward": profile.get("reward", {}),
                "activeUntil": active_until,
                "createdAt": now.isoformat()
            }
            tribe.setdefault("tribe_festivals", []).append(festival)
            tribe.setdefault("festival_marks", []).append(mark)
            tribe["festival_marks"] = tribe["festival_marks"][-20:]
            self._add_tribe_history(
                tribe,
                "festival",
                f"{festival['title']}萌发",
                f"{festival.get('sourceLabel', '近期行为')}反复出现，营地临时把它讲成“{festival['title']}”。",
                "",
                {"kind": "tribe_festival", "festivalId": festival["id"], "sourceTitles": festival["sourceTitles"]}
            )
            if hasattr(self, "_save_tribe_state"):
                self._save_tribe_state()
            return

    def _public_tribe_festivals(self, tribe: dict) -> list:
        self._ensure_tribe_festivals(tribe)
        return [
            self._public_tribe_festival(item)
            for item in (tribe.get("tribe_festivals", []) or [])
            if isinstance(item, dict) and item.get("status") == "active"
        ][-TRIBE_FESTIVAL_LIMIT:]

    def _public_tribe_festival_records(self, tribe: dict) -> list:
        return [
            self._public_tribe_festival(item)
            for item in (tribe.get("tribe_festivals", []) or [])
            if isinstance(item, dict) and item.get("status") in {"completed", "expired"}
        ][-TRIBE_FESTIVAL_RECORD_LIMIT:]

    def _public_tribe_festival_traditions(self, tribe: dict) -> list:
        return [
            dict(item) for item in (tribe.get("tribe_festival_traditions", []) or [])
            if isinstance(item, dict) and item.get("status", "active") == "active"
        ][-TRIBE_FESTIVAL_TRADITION_LIMIT:]

    def _public_tribe_festival(self, festival: dict) -> dict:
        public = dict(festival)
        participants = list((festival.get("participants", {}) or {}).values())
        public["participants"] = participants[-8:]
        public["participantNames"] = [item.get("memberName", "成员") for item in participants[-6:]]
        public["rewardParts"] = self._tribe_festival_reward_parts(festival.get("reward", {}))
        return public

    def _festival_tradition_for_key(self, tribe: dict, key: str) -> dict | None:
        return next((
            item for item in (tribe.get("tribe_festival_traditions", []) or [])
            if isinstance(item, dict) and item.get("key") == key and item.get("status", "active") == "active"
        ), None)

    def _maybe_form_festival_tradition(self, tribe: dict, festival: dict, actor_id: str = "") -> dict | None:
        key = festival.get("key", "")
        profile = TRIBE_FESTIVAL_TRADITION_PROFILES.get(key)
        if not profile or self._festival_tradition_for_key(tribe, key):
            return None
        completed = [
            item for item in (tribe.get("tribe_festivals", []) or [])
            if isinstance(item, dict) and item.get("key") == key and item.get("status") == "completed"
        ]
        if len(completed) < TRIBE_FESTIVAL_TRADITION_THRESHOLD:
            return None
        now = datetime.now()
        tradition = {
            "id": f"festival_tradition_{tribe.get('id', 'tribe')}_{key}_{int(now.timestamp() * 1000)}",
            "key": key,
            "status": "active",
            "title": profile.get("title", festival.get("title", "部落节日传统")),
            "summary": profile.get("summary", ""),
            "visitorLine": profile.get("visitorLine", ""),
            "newcomerLine": profile.get("newcomerLine", ""),
            "newcomerContext": profile.get("newcomerContext", ""),
            "seasonTitle": profile.get("seasonTitle", profile.get("title", "节日传统")),
            "festivalCount": len(completed),
            "sourceFestivalTitles": [item.get("title", "部落节日") for item in completed][-4:],
            "createdAt": now.isoformat()
        }
        tribe.setdefault("tribe_festival_traditions", []).append(tradition)
        tribe["tribe_festival_traditions"] = tribe["tribe_festival_traditions"][-TRIBE_FESTIVAL_TRADITION_LIMIT:]
        self._add_tribe_history(tribe, "festival", tradition["title"], f"{tradition['title']}沉淀成传统：{tradition.get('summary', '')}", actor_id, {"kind": "tribe_festival_tradition", **tradition})
        return tradition

    def _festival_tradition_visitor_hint(self, tribe: dict) -> str:
        tradition = next(iter(self._public_tribe_festival_traditions(tribe)), None)
        return tradition.get("visitorLine", "") if tradition else ""

    def _festival_tradition_newcomer_hint(self, tribe: dict) -> str:
        tradition = next(iter(self._public_tribe_festival_traditions(tribe)), None)
        return tradition.get("newcomerLine", "") if tradition else ""

    def _festival_tradition_context_support(self, tribe: dict, context: str) -> tuple[int, list]:
        labels = [
            item.get("title", "节日传统")
            for item in self._public_tribe_festival_traditions(tribe)
            if item.get("newcomerContext") == context
        ]
        return (1 if labels else 0), labels[:2]

    def _festival_tradition_season_awards(self) -> list:
        awards = []
        for tribe in self.tribes.values():
            for tradition in self._public_tribe_festival_traditions(tribe):
                awards.append({
                    "titleKey": f"festival_{tradition.get('key')}",
                    "title": tradition.get("seasonTitle", tradition.get("title", "节日传统")),
                    "summary": tradition.get("summary", ""),
                    "tribeId": tribe.get("id"),
                    "tribeName": tribe.get("name", "部落"),
                    "score": int(tradition.get("festivalCount", 1) or 1),
                    "actors": tradition.get("sourceFestivalTitles", [])[-5:]
                })
        return awards

    def _tribe_festival_by_id(self, tribe: dict, festival_id: str) -> dict | None:
        return next((
            item for item in (tribe.get("tribe_festivals", []) or [])
            if isinstance(item, dict) and item.get("id") == festival_id
        ), None)

    def _tribe_festival_reward_parts(self, reward: dict) -> list:
        labels = {
            "wood": "木材",
            "stone": "石材",
            "food": "食物",
            "renown": "声望",
            "discoveryProgress": "发现",
            "tradeReputation": "贸易信誉",
            "warPressureRelief": "战争压力缓和"
        }
        parts = []
        for key, label in labels.items():
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                parts.append(f"{label}+{value}" if key != "warPressureRelief" else f"{label}+{value}")
        return parts

    def _apply_tribe_festival_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石材")):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("discoveryProgress", "发现", "discovery_progress"),
            ("tradeReputation", "贸易信誉", "trade_reputation")
        ):
            amount = int((reward or {}).get(key, 0) or 0)
            if amount:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + amount
                parts.append(f"{label}+{amount}")
        relief = int((reward or {}).get("warPressureRelief", 0) or 0)
        if relief and hasattr(self, "_apply_camp_debt_pressure_relief"):
            relieved = self._apply_camp_debt_pressure_relief(tribe, relief)
            if relieved:
                parts.append(f"战争压力-{relieved}")
        return parts

    async def join_tribe_festival(self, player_id: str, festival_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        self._ensure_tribe_festivals(tribe)
        festival = self._tribe_festival_by_id(tribe, festival_id)
        if not festival or festival.get("status") != "active":
            await self._send_tribe_error(player_id, "这个部落节日已经结束")
            return
        if self._tribe_festival_expired(festival):
            festival["status"] = "expired"
            await self._send_tribe_error(player_id, "这个部落节日已经散场")
            await self.broadcast_tribe_state(tribe_id)
            return
        participants = festival.setdefault("participants", {})
        if player_id in participants:
            await self._send_tribe_error(player_id, "你已经参加过这个节日活动")
            return
        member = tribe.get("members", {}).get(player_id, {})
        participants[player_id] = {
            "playerId": player_id,
            "memberName": member.get("name", self._get_player_name(player_id)),
            "actionLabel": festival.get("activityLabel", "参与节日"),
            "joinedAt": datetime.now().isoformat()
        }
        festival["progress"] = len(participants)
        player = self.players.get(player_id, {})
        player["renown"] = int(player.get("renown", 0) or 0) + TRIBE_FESTIVAL_PERSONAL_RENOWN
        if festival["progress"] < int(festival.get("target", TRIBE_FESTIVAL_ACTIVITY_TARGET) or 1):
            await self._notify_tribe(tribe_id, f"{participants[player_id]['memberName']} 参加了“{festival.get('title', '部落节日')}”，还需要更多成员接上。")
            await self.broadcast_tribe_state(tribe_id)
            return

        reward_parts = self._apply_tribe_festival_reward(tribe, festival.get("reward", {}))
        profile = TRIBE_FESTIVAL_PROFILES.get(festival.get("key"), {})
        if profile.get("customKey") and hasattr(self, "_record_tribe_custom_choice"):
            record = self._record_tribe_custom_choice(tribe, profile.get("customKey"), festival.get("title", "部落节日"), player_id)
            if record:
                reward_parts.append(f"{record.get('label', '风俗')}倾向+1")
        now_text = datetime.now().isoformat()
        festival["status"] = "completed"
        festival["completedAt"] = now_text
        festival["completedBy"] = player_id
        festival["completedByName"] = participants[player_id]["memberName"]
        festival["rewardParts"] = reward_parts
        tradition = self._maybe_form_festival_tradition(tribe, festival, player_id)
        if tradition:
            festival["traditionTitle"] = tradition.get("title")
        detail = f"{festival.get('title', '部落节日')}完成，{festival.get('activityLabel', '节日活动')}由 {', '.join([item.get('memberName', '成员') for item in participants.values()])} 接成。{'、'.join(reward_parts) or '营地气氛被记下'}。"
        if tradition:
            detail += f" {tradition.get('title')}开始成为部落传统。"
        self._add_tribe_history(tribe, "festival", festival.get("title", "部落节日"), detail, player_id, {"kind": "tribe_festival", **festival})
        await self._publish_world_rumor(
            "festival",
            festival.get("title", "部落节日"),
            f"{tribe.get('name', '部落')} 把近期的{festival.get('sourceLabel', '共同记忆')}过成了“{festival.get('title', '部落节日')}”。" + (f" 后来这成了“{tradition.get('title')}”。" if tradition else ""),
            {"tribeId": tribe_id, "festivalId": festival_id}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
