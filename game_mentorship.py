from datetime import datetime

from game_config import *


class GameMentorshipMixin:
    def _active_mentorship(self, tribe: dict) -> dict | None:
        session = tribe.get("mentorship")
        if not isinstance(session, dict) or session.get("status") != "active":
            return None
        try:
            if datetime.fromisoformat(session.get("activeUntil", "")) <= datetime.now():
                session["status"] = "expired"
                session["expiredAt"] = datetime.now().isoformat()
                return None
        except (TypeError, ValueError):
            session["status"] = "expired"
            session["expiredAt"] = datetime.now().isoformat()
            return None
        return session

    def _mentor_candidates(self, tribe: dict) -> list:
        candidates = []
        for member_id, member in (tribe.get("members", {}) or {}).items():
            player = self.players.get(member_id, {}) if hasattr(self, "players") else {}
            personal_renown = int(player.get("personal_renown", 0) or 0)
            contribution = int(member.get("contribution", 0) or 0)
            if personal_renown < TRIBE_MENTORSHIP_MIN_PERSONAL_RENOWN and contribution < TRIBE_MENTORSHIP_MIN_CONTRIBUTION:
                continue
            candidates.append({
                "id": member_id,
                "name": member.get("name", player.get("name", "成员")),
                "role": member.get("role", "member"),
                "personalRenown": personal_renown,
                "contribution": contribution,
                "summary": f"个人声望 {personal_renown} / 贡献 {contribution}"
            })
        return sorted(candidates, key=lambda item: (item.get("personalRenown", 0), item.get("contribution", 0)), reverse=True)[:8]

    def _public_mentorship(self, tribe: dict) -> dict | None:
        session = self._active_mentorship(tribe)
        if not session:
            return None
        students = list(session.get("students", []) or [])
        return {
            "id": session.get("id"),
            "focusKey": session.get("focusKey"),
            "focusLabel": session.get("focusLabel"),
            "summary": session.get("summary"),
            "mentorId": session.get("mentorId"),
            "mentorName": session.get("mentorName"),
            "students": students[-6:],
            "studentCount": len(students),
            "target": int(session.get("target", TRIBE_MENTORSHIP_TARGET_STUDENTS) or TRIBE_MENTORSHIP_TARGET_STUDENTS),
            "minStudents": TRIBE_MENTORSHIP_MIN_STUDENTS,
            "createdAt": session.get("createdAt"),
            "activeUntil": session.get("activeUntil")
        }

    def _apply_mentorship_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("food", "食物", "food"),
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            value = int(reward.get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        pressure_relief = int(reward.get("pressureRelief", 0) or 0)
        if pressure_relief:
            relieved = 0
            for relation in (tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                if before <= 0:
                    continue
                after = max(0, before - pressure_relief)
                relation["warPressure"] = after
                relation["canDeclareWar"] = after >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                relieved += before - after
            if relieved:
                parts.append(f"战争压力-{relieved}")
        return parts

    def _member_is_mentor_ready(self, tribe: dict, player_id: str) -> bool:
        return any(candidate.get("id") == player_id for candidate in self._mentor_candidates(tribe))

    async def start_mentorship(self, player_id: str, focus_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if self._active_mentorship(tribe):
            await self._send_tribe_error(player_id, "当前已经有传承导师课程正在进行")
            return
        focus = TRIBE_MENTORSHIP_FOCUS_OPTIONS.get(focus_key)
        if not focus:
            await self._send_tribe_error(player_id, "未知传承方向")
            return
        if not self._member_is_mentor_ready(tribe, player_id):
            await self._send_tribe_error(
                player_id,
                f"需要个人声望 {TRIBE_MENTORSHIP_MIN_PERSONAL_RENOWN} 或部落贡献 {TRIBE_MENTORSHIP_MIN_CONTRIBUTION} 才能开课"
            )
            return

        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        session = {
            "id": f"mentorship_{tribe_id}_{int(now.timestamp() * 1000)}",
            "status": "active",
            "focusKey": focus_key,
            "focusLabel": focus.get("label", "传承导师"),
            "summary": focus.get("summary", ""),
            "mentorId": player_id,
            "mentorName": member.get("name", "导师"),
            "students": [],
            "studentIds": [],
            "target": TRIBE_MENTORSHIP_TARGET_STUDENTS,
            "createdAt": now.isoformat(),
            "activeUntil": datetime.fromtimestamp(now.timestamp() + TRIBE_MENTORSHIP_ACTIVE_MINUTES * 60).isoformat()
        }
        tribe["mentorship"] = session
        detail = f"{session['mentorName']} 开始传授“{session['focusLabel']}”：{session['summary']}"
        self._add_tribe_history(tribe, "ritual", "传承导师开课", detail, player_id, {"kind": "mentorship_start", "session": session})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def join_mentorship(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        session = self._active_mentorship(tribe)
        if not session:
            await self._send_tribe_error(player_id, "当前没有可以拜师的传承课程")
            return
        if player_id == session.get("mentorId"):
            await self._send_tribe_error(player_id, "导师不能拜自己的课")
            return
        if player_id in (session.get("studentIds", []) or []):
            await self._send_tribe_error(player_id, "你已经拜师学习过这次课程")
            return

        member = tribe.get("members", {}).get(player_id, {})
        student = {
            "playerId": player_id,
            "name": member.get("name", "成员"),
            "joinedAt": datetime.now().isoformat()
        }
        session.setdefault("studentIds", []).append(player_id)
        session.setdefault("students", []).append(student)
        focus = TRIBE_MENTORSHIP_FOCUS_OPTIONS.get(session.get("focusKey"), {})
        student_gain = int(focus.get("studentRenown", 1) or 0)
        if student_gain:
            self.players.setdefault(player_id, {})["personal_renown"] = int(self.players.get(player_id, {}).get("personal_renown", 0) or 0) + student_gain
        detail = f"{student['name']} 拜入{session.get('mentorName', '导师')}的“{session.get('focusLabel', '传承课')}”，进度 {len(session.get('students', []))}/{session.get('target', TRIBE_MENTORSHIP_TARGET_STUDENTS)}。"
        if student_gain:
            detail += f" 个人声望+{student_gain}。"
        self._add_tribe_history(tribe, "ritual", "传承导师拜师", detail, player_id, {"kind": "mentorship_join", "sessionId": session.get("id"), "student": student})
        await self._notify_tribe(tribe_id, detail)
        if len(session.get("students", []) or []) >= int(session.get("target", TRIBE_MENTORSHIP_TARGET_STUDENTS) or TRIBE_MENTORSHIP_TARGET_STUDENTS):
            await self.complete_mentorship(session.get("mentorId") or player_id)
            return
        await self.broadcast_tribe_state(tribe_id)

    async def complete_mentorship(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        session = self._active_mentorship(tribe)
        if not session:
            await self._send_tribe_error(player_id, "当前没有可以结课的传承课程")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if player_id != session.get("mentorId") and member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有导师、首领或长老可以结课")
            return
        students = list(session.get("students", []) or [])
        if len(students) < TRIBE_MENTORSHIP_MIN_STUDENTS:
            await self._send_tribe_error(player_id, f"至少需要 {TRIBE_MENTORSHIP_MIN_STUDENTS} 名成员拜师")
            return

        focus = TRIBE_MENTORSHIP_FOCUS_OPTIONS.get(session.get("focusKey"), {})
        reward_parts = self._apply_mentorship_reward(tribe, focus)
        mentor_gain = int(focus.get("mentorRenown", 1) or 0)
        if mentor_gain and session.get("mentorId"):
            mentor_player = self.players.setdefault(session.get("mentorId"), {})
            mentor_player["personal_renown"] = int(mentor_player.get("personal_renown", 0) or 0) + mentor_gain
            reward_parts.append(f"导师个人声望+{mentor_gain}")
        oral_reference = None
        oral_lineage = None
        if hasattr(self, "_record_oral_map_context_reference"):
            oral_reference, oral_lineage = self._record_oral_map_context_reference(
                tribe,
                "mentorship",
                session.get("focusLabel", "传承导师"),
                member.get("name", session.get("mentorName", "导师")),
                "导师结课"
            )
            if oral_reference:
                reward_parts.append(f"引用{oral_reference.get('actionLabel', '口述地图')}")
        route_proof_reference = None
        route_proof_guardian = None
        if session.get("focusKey") in {"trail", "cave", "gather"} and hasattr(self, "_record_forbidden_edge_route_proof_reference"):
            route_proof_reference, route_proof_guardian = self._record_forbidden_edge_route_proof_reference(
                tribe,
                "mentorship",
                session.get("focusLabel", "传承导师"),
                member.get("name", session.get("mentorName", "导师")),
                "导师结课"
            )
            if route_proof_reference:
                tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + 1
                reward_parts.append("路证课程+1")
        session["status"] = "completed"
        session["completedAt"] = datetime.now().isoformat()
        session["completedBy"] = player_id
        session["rewardParts"] = reward_parts
        session["oralMapReference"] = oral_reference
        session["oralMapLineage"] = oral_lineage
        session["routeProofReference"] = route_proof_reference
        session["routeProofGuardian"] = route_proof_guardian
        tribe.setdefault("mentorship_history", []).append(session)
        tribe["mentorship_history"] = tribe["mentorship_history"][-TRIBE_MENTORSHIP_HISTORY_LIMIT:]

        student_names = "、".join(item.get("name", "成员") for item in students)
        detail = f"{member.get('name', session.get('mentorName', '导师'))} 收束“{session.get('focusLabel', '传承课')}”，{student_names}完成拜师。{'、'.join(reward_parts) or '师徒故事写入部落历史'}。"
        if oral_reference and oral_reference.get("narratorTitle"):
            detail += f" {oral_reference['narratorTitle'].get('memberName', '成员')}获得短时“讲路师”称号。"
        if route_proof_reference:
            detail += f" 课程引用{route_proof_reference.get('label', '禁地路证')}来源链。"
        if route_proof_guardian:
            detail += f" {route_proof_guardian.get('memberName', '成员')}获得短时“路证守护者”称号。"
        old_song_adoption = None
        if hasattr(self, "_schedule_old_song_adoption"):
            old_song_adoption = self._schedule_old_song_adoption(
                tribe,
                "mentorship",
                session.get("id"),
                f"{session.get('focusLabel', '传承课')}结课",
                f"{session.get('mentorName', '导师')}的课程已经结课，可以借成谱旧歌决定这段传承该被采信、校订还是暂存。",
            )
        if old_song_adoption:
            detail += f" 生成旧歌采信：{old_song_adoption.get('label', '旧歌采信')}。"
        self._add_tribe_history(tribe, "ritual", "传承导师结课", detail, player_id, {"kind": "mentorship_complete", "session": session})
        await self._publish_world_rumor(
            "ritual",
            "传承导师",
            f"{tribe.get('name', '部落')} 的{session.get('mentorName', '导师')}把“{session.get('focusLabel', '传承课')}”传给了{student_names}。",
            {"tribeId": tribe_id, "focusKey": session.get("focusKey")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
