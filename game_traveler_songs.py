from datetime import datetime
import random

from game_config import *


class GameTravelerSongMixin:
    def _active_traveler_songs(self, tribe: dict) -> list:
        now = datetime.now()
        active = []
        for song in tribe.get("traveler_songs", []) or []:
            if not isinstance(song, dict) or song.get("status") != "active":
                continue
            try:
                if datetime.fromisoformat(song.get("activeUntil", "")) <= now:
                    song["status"] = "expired"
                    song["expiredAt"] = now.isoformat()
                    continue
            except (TypeError, ValueError):
                pass
            active.append(song)
        tribe["traveler_songs"] = active[-TRIBE_TRAVELER_SONG_LIMIT:]
        return tribe["traveler_songs"]

    def _active_traveler_song_hints(self, tribe: dict) -> list:
        now = datetime.now()
        hints = []
        for hint in tribe.get("traveler_song_hints", []) or []:
            if not isinstance(hint, dict) or hint.get("status") == "used":
                continue
            try:
                if datetime.fromisoformat(hint.get("activeUntil", "")) <= now:
                    continue
            except (TypeError, ValueError):
                pass
            hints.append(hint)
        tribe["traveler_song_hints"] = hints[-TRIBE_TRAVELER_SONG_LIMIT:]
        return tribe["traveler_song_hints"]

    def _active_traveler_song_tunes(self, tribe: dict) -> list:
        now = datetime.now()
        tunes = []
        for tune in tribe.get("traveler_song_tunes", []) or []:
            if not isinstance(tune, dict) or tune.get("status", "active") != "active":
                continue
            try:
                if datetime.fromisoformat(tune.get("activeUntil", "")) <= now:
                    tune["status"] = "expired"
                    tune["expiredAt"] = now.isoformat()
                    continue
            except (TypeError, ValueError):
                pass
            tunes.append(tune)
        tribe["traveler_song_tunes"] = tunes[-TRIBE_TRAVELER_SONG_TUNE_LIMIT:]
        return tribe["traveler_song_tunes"]

    def _public_traveler_songs(self, tribe: dict) -> list:
        return self._active_traveler_songs(tribe)

    def _public_traveler_song_records(self, tribe: dict) -> list:
        return [item for item in tribe.get("traveler_song_records", []) or [] if isinstance(item, dict)][-TRIBE_TRAVELER_SONG_RECORD_LIMIT:]

    def _public_traveler_song_hints(self, tribe: dict) -> list:
        return self._active_traveler_song_hints(tribe)

    def _public_traveler_song_tunes(self, tribe: dict) -> list:
        return self._active_traveler_song_tunes(tribe)

    def _traveler_song_reward_parts(self, tribe: dict, action: dict, other_tribe_id: str = "") -> list:
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            value = int((action or {}).get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        relation = None
        if other_tribe_id:
            relation = tribe.setdefault("boundary_relations", {}).setdefault(other_tribe_id, {})
            relation_delta = int(action.get("relationDelta", 0) or 0)
            if relation_delta:
                relation["score"] = max(-9, min(9, int(relation.get("score", 0) or 0) + relation_delta))
                parts.append(f"关系{relation_delta:+d}")
            trust_delta = int(action.get("tradeTrustDelta", 0) or 0)
            if trust_delta:
                relation["tradeTrust"] = max(0, min(10, int(relation.get("tradeTrust", 0) or 0) + trust_delta))
                parts.append(f"信任{trust_delta:+d}")
            pressure_relief = int(action.get("warPressureRelief", 0) or 0)
            if pressure_relief:
                before = int(relation.get("warPressure", 0) or 0)
                relation["warPressure"] = max(0, before - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                if before != int(relation.get("warPressure", 0) or 0):
                    parts.append(f"战争压力-{before - int(relation.get('warPressure', 0) or 0)}")
            if action.get("temperatureTone"):
                relation["temperatureTone"] = action.get("temperatureTone")
                relation["lastTemperatureAction"] = f"traveler_song_{action.get('key', 'song')}"
                parts.append("边界口风改变")
        return parts

    def _schedule_traveler_song(self, tribe: dict, source_kind: str, source_id: str, source_label: str, summary: str = "", other_tribe_id: str = "") -> dict | None:
        if not tribe or not source_id:
            return None
        active = self._active_traveler_songs(tribe)
        dedupe_id = f"{source_kind}:{source_id}"
        if any(item.get("dedupeId") == dedupe_id for item in active):
            return None
        rng = getattr(self, "_weather_rng", None) or random
        if rng.random() > TRIBE_TRAVELER_SONG_CHANCE:
            return None
        now = datetime.now()
        source_titles = {
            "visitor": "旅人谣曲",
            "caravan": "商队谣曲",
            "far_reply": "回信谣曲"
        }
        song = {
            "id": f"traveler_song_{tribe.get('id')}_{int(now.timestamp() * 1000)}_{rng.randint(100, 999)}",
            "type": "traveler_song",
            "status": "active",
            "sourceKind": source_kind,
            "sourceId": source_id,
            "dedupeId": dedupe_id,
            "sourceLabel": source_label or "远方口信",
            "title": source_titles.get(source_kind, "旅人谣曲"),
            "label": f"{source_label or '远方口信'}谣曲",
            "summary": summary or "远方口信被唱成短句，可能影响贸易、边界口风和下一次来访。",
            "otherTribeId": other_tribe_id,
            "otherTribeName": self.tribes.get(other_tribe_id, {}).get("name", "邻近部落") if other_tribe_id and hasattr(self, "tribes") else "",
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_TRAVELER_SONG_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["traveler_songs"] = [*active, song][-TRIBE_TRAVELER_SONG_LIMIT:]
        return song

    def _add_traveler_song_hint(self, tribe: dict, song: dict, action_key: str, action: dict, member_name: str):
        now = datetime.now()
        hint = {
            "id": f"traveler_song_hint_{song.get('id')}_{action_key}",
            "songId": song.get("id"),
            "label": f"{song.get('label', '旅人谣曲')} · {action.get('label', '处理')}",
            "sourceLabel": song.get("sourceLabel", "远方口信"),
            "actionKey": action_key,
            "actionLabel": action.get("label", "处理"),
            "rumorTone": action.get("rumorTone", ""),
            "visitorWeight": float(action.get("visitorWeight", 0) or 0),
            "memberName": member_name,
            "status": "active",
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_TRAVELER_SONG_HINT_MINUTES * 60).isoformat()
        }
        tribe.setdefault("traveler_song_hints", []).append(hint)
        tribe["traveler_song_hints"] = tribe["traveler_song_hints"][-TRIBE_TRAVELER_SONG_LIMIT:]
        return hint

    def _traveler_song_visitor_bonus(self, tribe: dict) -> float:
        hint_bonus = sum(float(hint.get("visitorWeight", 0) or 0) for hint in self._active_traveler_song_hints(tribe))
        tune_bonus = sum(float(tune.get("visitorWeight", 0) or 0) for tune in self._active_traveler_song_tunes(tribe))
        return min(0.28, hint_bonus + tune_bonus)

    def _mark_traveler_song_visitor_hint_used(self, tribe: dict, label: str = "来访权重") -> bool:
        for hint in self._active_traveler_song_hints(tribe):
            if float(hint.get("visitorWeight", 0) or 0) <= 0:
                continue
            hint["status"] = "used"
            hint["usedLabel"] = label
            hint["usedAt"] = datetime.now().isoformat()
            return True
        for tune in self._active_traveler_song_tunes(tribe):
            if float(tune.get("visitorWeight", 0) or 0) <= 0 or tune.get("visitorHintUsed"):
                continue
            tune["visitorHintUsed"] = True
            tune["usedLabel"] = label
            tune["usedAt"] = datetime.now().isoformat()
            return True
        return False

    def _traveler_song_rumor_text(self, text: str, related: dict | None = None) -> tuple[str, dict]:
        related = dict(related or {})
        tribe_id = related.get("tribeId")
        tribe = self.tribes.get(tribe_id) if tribe_id and hasattr(self, "tribes") else None
        if not tribe:
            return text, related
        hint = next((item for item in self._active_traveler_song_hints(tribe) if item.get("rumorTone")), None)
        if not hint:
            tune = next((item for item in self._active_traveler_song_tunes(tribe) if item.get("rumorTone")), None)
            if not tune:
                return text, related
            phrase = {
                "warm": f"{tune.get('styleLabel', '公开曲牌')}让这条消息带上来访的亮声。",
                "open": f"{tune.get('styleLabel', '公开曲牌')}让这条消息更像可谈的口信。",
                "quiet": f"{tune.get('styleLabel', '公开曲牌')}让这条消息先被压成可考旧事。"
            }.get(tune.get("rumorTone"), "")
            if not phrase:
                return text, related
            related["travelerSongTune"] = {"id": tune.get("id"), "label": tune.get("label"), "style": tune.get("styleKey")}
            return f"{text} {phrase}", related
        phrase = {
            "warm": "旅人谣曲把这条消息唱得更亮。",
            "open": "改过词的谣曲让这条消息听起来更能谈。",
            "quiet": "被压下的谣曲让这条消息少了几分火气。"
        }.get(hint.get("rumorTone"), "")
        if not phrase:
            return text, related
        related["travelerSongTone"] = {"key": hint.get("rumorTone"), "label": hint.get("label")}
        return f"{text} {phrase}", related

    def _traveler_song_tune_style_key(self, record: dict) -> str:
        source_kind = record.get("sourceKind")
        action_key = record.get("actionKey")
        if source_kind == "caravan":
            return "trade"
        if source_kind == "far_reply" or action_key == "rewrite":
            return "diplomacy"
        if source_kind == "visitor" and action_key != "quiet":
            return "visitor"
        return "memory"

    def _traveler_song_tune_sources(self, tribe: dict) -> list:
        sources = []
        for tune in self._active_traveler_song_tunes(tribe):
            sources.append({
                "sourceId": tune.get("id"),
                "sourceKind": "traveler_song_tune",
                "sourceLabel": "旅人曲牌",
                "title": tune.get("label", "公开曲牌"),
                "summary": tune.get("summary", "这段曲牌已经公开流传，但真假与走向仍可被辨认。")
            })
        for hint in self._active_traveler_song_hints(tribe):
            if hint.get("status") == "used":
                continue
            sources.append({
                "sourceId": hint.get("id"),
                "sourceKind": "traveler_song_hint",
                "sourceLabel": "谣曲余音",
                "title": hint.get("label", "旅人谣曲余音"),
                "summary": f"{hint.get('memberName', '成员')}留下的谣曲余音还在影响传闻语气。"
            })
        return sources

    async def promote_traveler_song_tune(self, player_id: str, record_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        records = [item for item in tribe.get("traveler_song_records", []) or [] if isinstance(item, dict)]
        record = next((item for item in records if item.get("id") == record_id), None)
        if not record:
            await self._send_tribe_error(player_id, "找不到这段谣曲记录")
            return
        if record.get("promotedAt"):
            await self._send_tribe_error(player_id, "这段谣曲已经成为公开曲牌")
            return
        style_key = self._traveler_song_tune_style_key(record)
        style = TRIBE_TRAVELER_SONG_TUNE_STYLES.get(style_key, TRIBE_TRAVELER_SONG_TUNE_STYLES["memory"])
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        now = datetime.now()
        reward_parts = self._traveler_song_reward_parts(
            tribe,
            {"key": f"tune_{style_key}", **style, **(style.get("reward", {}) or {})},
            record.get("otherTribeId", "")
        )
        tune = {
            "id": f"traveler_tune_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "type": "traveler_song_tune",
            "status": "active",
            "sourceRecordId": record.get("id"),
            "sourceSongId": record.get("songId"),
            "sourceKind": record.get("sourceKind"),
            "sourceLabel": record.get("sourceLabel", "旅人谣曲"),
            "label": f"{record.get('sourceLabel', '旅人谣曲')}·{style.get('label', '公开曲牌')}",
            "styleKey": style_key,
            "styleLabel": style.get("label", "公开曲牌"),
            "summary": style.get("summary", "这段谣曲被整理成公开曲牌，后续传闻会引用它。"),
            "rumorTone": style.get("rumorTone", ""),
            "stageTone": style.get("stageTone", style_key),
            "visitorWeight": float(style.get("visitorWeight", 0) or 0),
            "rewardParts": reward_parts,
            "createdBy": player_id,
            "createdByName": member_name,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_TRAVELER_SONG_TUNE_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe.setdefault("traveler_song_tunes", []).append(tune)
        tribe["traveler_song_tunes"] = tribe["traveler_song_tunes"][-TRIBE_TRAVELER_SONG_TUNE_LIMIT:]
        record["promotedAt"] = now.isoformat()
        record["promotedByName"] = member_name
        record["promotedTuneLabel"] = tune.get("label")
        record["styleLabel"] = style.get("label", "公开曲牌")
        detail = f"{member_name}把“{record.get('sourceLabel', '旅人谣曲')}”整理成{style.get('label', '公开曲牌')}。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "trade", "公开曲牌", detail, player_id, {"kind": "traveler_song_tune", "record": record, "tune": tune})
        await self._publish_world_rumor(
            "traveler_song_tune",
            "公开曲牌",
            f"{tribe.get('name', '部落')}把一段旅人谣曲唱成了{style.get('label', '公开曲牌')}。",
            {"tribeId": tribe_id, "tuneId": tune.get("id"), "styleKey": style_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def resolve_traveler_song(self, player_id: str, song_id: str, action_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        action = TRIBE_TRAVELER_SONG_ACTIONS.get(action_key)
        if not action:
            await self._send_tribe_error(player_id, "未知谣曲处理方式")
            return
        song = next((item for item in self._active_traveler_songs(tribe) if item.get("id") == song_id), None)
        if not song:
            await self._send_tribe_error(player_id, "这段旅人谣曲已经散去")
            return
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        action = {"key": action_key, **action}
        now_text = datetime.now().isoformat()
        reward_parts = self._traveler_song_reward_parts(tribe, action, song.get("otherTribeId", ""))
        hint = self._add_traveler_song_hint(tribe, song, action_key, action, member_name)
        song["status"] = "resolved"
        song["resolvedAt"] = now_text
        song["resolvedBy"] = player_id
        song["actionKey"] = action_key
        record = {
            "id": f"traveler_song_record_{song_id}_{int(datetime.now().timestamp() * 1000)}",
            "songId": song_id,
            "sourceKind": song.get("sourceKind"),
            "sourceLabel": song.get("sourceLabel"),
            "actionKey": action_key,
            "actionLabel": action.get("label", "处理"),
            "memberName": member_name,
            "otherTribeName": song.get("otherTribeName", ""),
            "otherTribeId": song.get("otherTribeId", ""),
            "rewardParts": reward_parts,
            "hintLabel": hint.get("label"),
            "createdAt": now_text
        }
        tribe.setdefault("traveler_song_records", []).append(record)
        tribe["traveler_song_records"] = tribe["traveler_song_records"][-TRIBE_TRAVELER_SONG_RECORD_LIMIT:]
        tribe["traveler_songs"] = [item for item in self._active_traveler_songs(tribe) if item.get("id") != song_id]
        detail = f"{member_name} 将“{song.get('label', '旅人谣曲')}”选择{action.get('label', '处理')}：{'、'.join(reward_parts) or '留下新的传闻语气'}。"
        self._add_tribe_history(tribe, "trade", "旅人谣曲", detail, player_id, {"kind": "traveler_song", "record": record, "song": song})
        await self._publish_world_rumor(
            "traveler_song",
            "旅人谣曲",
            f"{tribe.get('name', '部落')} 把{song.get('sourceLabel', '远方口信')}唱成新的谣曲，并选择{action.get('label', '处理')}。",
            {"tribeId": tribe_id, "otherTribeId": song.get("otherTribeId"), "songId": song_id, "action": action_key}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
