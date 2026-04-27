import random
from datetime import datetime


LIVING_LEGEND_ACTIVE_MINUTES = 240
LIVING_LEGEND_CANDIDATE_LIMIT = 5
LIVING_LEGEND_RECORD_LIMIT = 8
LIVING_LEGEND_SUPPORT_TARGET = 3
LIVING_LEGEND_RENOWN_REWARD = 2
LIVING_LEGEND_PERSONAL_RENOWN_REWARD = 2
LIVING_LEGEND_TITLE_LIMIT = 3

LIVING_LEGEND_SOURCE_KEYWORDS = (
    ("rescue", ("营救", "救援", "救回", "救灾"), 3),
    ("mediation", ("调停", "停战", "裁判", "见证"), 3),
    ("atonement", ("补救", "赎", "破戒", "律令"), 2),
    ("discovery", ("首发现", "发现", "洞穴", "遗迹", "侦察", "探路", "探索"), 2),
    ("honor", ("史诗", "誓约", "图腾", "铭文", "传承", "胜利"), 2),
)

LIVING_LEGEND_ACTIONS = {
    "witness": {
        "label": "见证",
        "summary": "确认这段事迹值得被传唱",
        "bucket": "votes",
        "score": 1,
        "historyTitle": "见证活人传说",
    },
    "elaborate": {
        "label": "补述",
        "summary": "补上旁人遗漏的细节",
        "bucket": "elaborations",
        "score": 2,
        "historyTitle": "补述活人传说",
    },
    "question": {
        "label": "质疑",
        "summary": "要求这段传说先接受盘问",
        "bucket": "questions",
        "score": -1,
        "historyTitle": "质疑活人传说",
    },
}

LIVING_LEGEND_TITLE_META = {
    "rescue": ("火边救回者", "救援纹候选", "救援地名来源"),
    "mediation": ("停火见证者", "调停纹候选", "停战地名来源"),
    "atonement": ("补誓者", "赎誓纹候选", "补誓地名来源"),
    "discovery": ("深路认路者", "探路纹候选", "探路地名来源"),
    "honor": ("图腾传唱者", "传唱纹候选", "荣誉地名来源"),
    "world_event": ("风声记名者", "风声纹候选", "传闻地名来源"),
    "exploration": ("远路归来者", "远路纹候选", "归路地名来源"),
    "governance": ("议火立名者", "议火纹候选", "议火地名来源"),
    "ritual": ("火圈应声者", "火圈纹候选", "火圈地名来源"),
}


class GameLivingLegendMixin:
    def _living_legend_active_until(self) -> str:
        return datetime.fromtimestamp(
            datetime.now().timestamp() + LIVING_LEGEND_ACTIVE_MINUTES * 60
        ).isoformat()

    def _living_legend_support_target(self, tribe: dict) -> int:
        member_count = len(tribe.get("members", {}) or {})
        return max(1, min(LIVING_LEGEND_SUPPORT_TARGET, max(1, member_count)))

    def _living_legend_source_meta(self, record: dict) -> dict | None:
        if str((record.get("related") or {}).get("kind", "")).startswith("living_legend"):
            return None
        text = " ".join([
            str(record.get("type", "")),
            str(record.get("title", "")),
            str(record.get("detail", "")),
            str((record.get("related") or {}).get("kind", "")),
        ])
        for source_key, keywords, weight in LIVING_LEGEND_SOURCE_KEYWORDS:
            if any(keyword in text for keyword in keywords):
                return {"sourceKey": source_key, "weight": weight}
        if record.get("type") in {"world_event", "exploration", "governance", "ritual"}:
            return {"sourceKey": record.get("type"), "weight": 1}
        return None

    def _living_legend_member_from_record(self, tribe: dict, record: dict) -> dict | None:
        members = tribe.get("members", {}) or {}
        related = record.get("related") or {}
        possible_ids = [
            record.get("actorId"),
            related.get("memberId"),
            related.get("playerId"),
            related.get("targetId"),
            related.get("rescuerId"),
            related.get("winnerId"),
        ]
        for member_id in possible_ids:
            if member_id and member_id in members:
                member = members[member_id]
                return {"id": member_id, "name": member.get("name") or self._get_player_name(member_id)}
        return None

    def _seed_living_legend_candidate(self, tribe: dict, record: dict) -> bool:
        if not tribe or not isinstance(record, dict):
            return False
        meta = self._living_legend_source_meta(record)
        member = self._living_legend_member_from_record(tribe, record)
        source_id = record.get("id")
        if not meta or not member or not source_id:
            return False

        candidates = tribe.setdefault("living_legend_candidates", [])
        if any(item.get("sourceId") == source_id and item.get("memberId") == member["id"] for item in candidates):
            return False

        detail = str(record.get("detail") or record.get("title") or "部落记忆")
        candidate = {
            "id": f"living_legend_{int(datetime.now().timestamp() * 1000)}_{random.randint(1000, 9999)}",
            "memberId": member["id"],
            "memberName": member["name"],
            "sourceId": source_id,
            "sourceType": meta["sourceKey"],
            "sourceTitle": record.get("title") or "部落记忆",
            "summary": detail[:120],
            "baseScore": int(meta["weight"]),
            "votes": {},
            "elaborations": {},
            "questions": {},
            "createdAt": datetime.now().isoformat(),
            "activeUntil": self._living_legend_active_until(),
            "status": "pending",
        }
        candidates.append(candidate)
        tribe["living_legend_candidates"] = candidates[-LIVING_LEGEND_CANDIDATE_LIMIT:]
        return True

    def _seed_living_legend_candidate_from_rumor(self, tribe: dict, rumor: dict) -> bool:
        if not tribe or not isinstance(rumor, dict):
            return False
        related = rumor.get("related") or {}
        if related.get("tribeId") != tribe.get("id"):
            return False
        actor_id = (
            related.get("memberId")
            or related.get("playerId")
            or related.get("actorId")
            or related.get("rescuerId")
            or related.get("winnerId")
        )
        record = {
            "id": rumor.get("id"),
            "type": "world_event",
            "title": rumor.get("title") or "世界传闻",
            "detail": rumor.get("text") or "",
            "actorId": actor_id,
            "createdAt": rumor.get("createdAt"),
            "related": {
                **related,
                "kind": related.get("kind") or rumor.get("type") or "world_rumor",
            },
        }
        return self._seed_living_legend_candidate(tribe, record)

    def _active_living_legend_candidates(self, tribe: dict) -> list[dict]:
        if not tribe:
            return []
        now = datetime.now()
        active = [
            item for item in (tribe.get("living_legend_candidates", []) or [])
            if isinstance(item, dict)
            and item.get("status") == "pending"
            and self._active_until_still_valid(item, now)
        ]
        tribe["living_legend_candidates"] = active[-LIVING_LEGEND_CANDIDATE_LIMIT:]
        return tribe["living_legend_candidates"]

    def _refresh_living_legend_candidates(self, tribe: dict) -> list[dict]:
        candidates = self._active_living_legend_candidates(tribe)
        if len(candidates) < LIVING_LEGEND_CANDIDATE_LIMIT:
            for record in list(tribe.get("history", []) or [])[-12:]:
                self._seed_living_legend_candidate(tribe, record)
                candidates = self._active_living_legend_candidates(tribe)
                if len(candidates) >= LIVING_LEGEND_CANDIDATE_LIMIT:
                    break
        if len(candidates) < LIVING_LEGEND_CANDIDATE_LIMIT:
            for rumor in list(getattr(self, "world_rumors", []) or [])[-12:]:
                self._seed_living_legend_candidate_from_rumor(tribe, rumor)
                candidates = self._active_living_legend_candidates(tribe)
                if len(candidates) >= LIVING_LEGEND_CANDIDATE_LIMIT:
                    break
        return sorted(candidates, key=lambda item: (self._living_legend_candidate_score(item), item.get("createdAt", "")), reverse=True)

    def _living_legend_entries(self, candidate: dict, bucket: str) -> list[dict]:
        entries = candidate.get(bucket, {}) or {}
        if isinstance(entries, dict):
            return [entry for entry in entries.values() if isinstance(entry, dict)]
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
        return []

    def _living_legend_names(self, candidate: dict, bucket: str) -> list[str]:
        return [
            entry.get("memberName", "成员")
            for entry in self._living_legend_entries(candidate, bucket)
            if entry.get("memberName")
        ][-5:]

    def _living_legend_positive_count(self, candidate: dict) -> int:
        return len(self._living_legend_entries(candidate, "votes")) + len(self._living_legend_entries(candidate, "elaborations"))

    def _living_legend_candidate_score(self, candidate: dict) -> int:
        score = int(candidate.get("baseScore", 0) or 0)
        for action in LIVING_LEGEND_ACTIONS.values():
            score += len(self._living_legend_entries(candidate, action["bucket"])) * int(action.get("score", 0) or 0)
        return score

    def _living_legend_member_responded(self, candidate: dict, player_id: str) -> bool:
        for action in LIVING_LEGEND_ACTIONS.values():
            entries = candidate.get(action["bucket"], {}) or {}
            if isinstance(entries, dict) and player_id in entries:
                return True
        return False

    def _living_legend_title_meta(self, candidate: dict) -> tuple[str, str, str]:
        return LIVING_LEGEND_TITLE_META.get(candidate.get("sourceType"), ("部落传名者", "活人传说纹候选", "传说地名来源"))

    def _living_legend_record_title(self, candidate: dict) -> str:
        title, _, _ = self._living_legend_title_meta(candidate)
        return f"争议中的{title}" if self._living_legend_entries(candidate, "questions") else title

    def _public_living_legend_candidates(self, tribe: dict) -> list[dict]:
        target = self._living_legend_support_target(tribe)
        public = []
        for item in self._refresh_living_legend_candidates(tribe):
            witness_count = len(self._living_legend_entries(item, "votes"))
            elaboration_count = len(self._living_legend_entries(item, "elaborations"))
            question_count = len(self._living_legend_entries(item, "questions"))
            positive_count = self._living_legend_positive_count(item)
            public.append({
                "id": item.get("id"),
                "memberId": item.get("memberId"),
                "memberName": item.get("memberName"),
                "sourceType": item.get("sourceType"),
                "sourceTitle": item.get("sourceTitle"),
                "summary": item.get("summary"),
                "supportCount": positive_count,
                "supportTarget": target,
                "witnessCount": witness_count,
                "elaborationCount": elaboration_count,
                "questionCount": question_count,
                "supporterNames": self._living_legend_names(item, "votes"),
                "elaborationNames": self._living_legend_names(item, "elaborations"),
                "questionNames": self._living_legend_names(item, "questions"),
                "score": self._living_legend_candidate_score(item),
                "actionSummary": f"传唱 {positive_count}/{target}，质疑 {question_count}",
                "actionOptions": [
                    {"key": key, "label": action["label"], "summary": action["summary"]}
                    for key, action in LIVING_LEGEND_ACTIONS.items()
                ],
                "activeUntil": item.get("activeUntil"),
                "createdAt": item.get("createdAt"),
            })
        return public

    def _public_living_legend_records(self, tribe: dict) -> list[dict]:
        return list(tribe.get("living_legend_records", []) or [])[-LIVING_LEGEND_RECORD_LIMIT:]

    async def support_living_legend(self, player_id: str, candidate_id: str):
        await self.respond_living_legend(player_id, candidate_id, "witness")

    async def respond_living_legend(self, player_id: str, candidate_id: str, action_key: str = "witness"):
        action = LIVING_LEGEND_ACTIONS.get(action_key) or LIVING_LEGEND_ACTIONS["witness"]
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id)
        if not member:
            await self._send_tribe_error(player_id, "只有部落成员可以见证传说")
            return

        candidates = self._refresh_living_legend_candidates(tribe)
        candidate = next((item for item in candidates if item.get("id") == candidate_id), None)
        if not candidate:
            await self._send_tribe_error(player_id, "传说候选已经散去")
            return

        if self._living_legend_member_responded(candidate, player_id):
            await self._send_tribe_error(player_id, "你已经对这段传说表态")
            return

        member_name = member.get("name") or self._get_player_name(player_id)
        bucket = action["bucket"]
        candidate.setdefault(bucket, {})[player_id] = {
            "memberId": player_id,
            "memberName": member_name,
            "actionKey": action_key,
            "note": action["summary"],
            "createdAt": datetime.now().isoformat(),
        }
        support_count = self._living_legend_positive_count(candidate)
        question_count = len(self._living_legend_entries(candidate, "questions"))
        target = self._living_legend_support_target(tribe)

        if support_count >= target and self._living_legend_candidate_score(candidate) > 0:
            await self._settle_living_legend(tribe_id, tribe, candidate)
        else:
            detail = f"{member_name} 对 {candidate.get('memberName', '某位成员')} 的传说候选选择“{action['label']}”：{candidate.get('sourceTitle', '部落记忆')}（传唱 {support_count}/{target}，质疑 {question_count}）。"
            self._add_tribe_history(
                tribe,
                "ritual",
                action["historyTitle"],
                detail,
                player_id,
                {"kind": "living_legend_response", "candidateId": candidate_id, "actionKey": action_key}
            )
            await self._notify_tribe(tribe_id, detail)

        await self.broadcast_tribe_state(tribe_id)

    async def _settle_living_legend(self, tribe_id: str, tribe: dict, candidate: dict):
        member_id = candidate.get("memberId")
        member_name = candidate.get("memberName") or self._get_player_name(member_id or "")
        legend_title = self._living_legend_record_title(candidate)
        _, rune_candidate, landmark_source = self._living_legend_title_meta(candidate)
        question_count = len(self._living_legend_entries(candidate, "questions"))
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + LIVING_LEGEND_RENOWN_REWARD
        if member_id and member_id in self.players:
            self.players[member_id]["personal_renown"] = int(self.players[member_id].get("personal_renown", 0) or 0) + LIVING_LEGEND_PERSONAL_RENOWN_REWARD
            titles = self.players[member_id].setdefault("legend_titles", [])
            titles.append({"title": legend_title, "sourceTitle": candidate.get("sourceTitle"), "createdAt": datetime.now().isoformat()})
            self.players[member_id]["legend_titles"] = titles[-LIVING_LEGEND_TITLE_LIMIT:]
        if member_id and member_id in (tribe.get("members", {}) or {}):
            member_titles = tribe["members"][member_id].setdefault("legend_titles", [])
            member_titles.append({"title": legend_title, "sourceTitle": candidate.get("sourceTitle"), "createdAt": datetime.now().isoformat()})
            tribe["members"][member_id]["legend_titles"] = member_titles[-LIVING_LEGEND_TITLE_LIMIT:]

        record = {
            "id": f"living_legend_record_{int(datetime.now().timestamp() * 1000)}_{random.randint(1000, 9999)}",
            "memberId": member_id,
            "memberName": member_name,
            "legendTitle": legend_title,
            "sourceTitle": candidate.get("sourceTitle"),
            "summary": candidate.get("summary"),
            "supportCount": self._living_legend_positive_count(candidate),
            "witnessCount": len(self._living_legend_entries(candidate, "votes")),
            "elaborationCount": len(self._living_legend_entries(candidate, "elaborations")),
            "questionCount": question_count,
            "supporterNames": self._living_legend_names(candidate, "votes"),
            "elaborationNames": self._living_legend_names(candidate, "elaborations"),
            "questionNames": self._living_legend_names(candidate, "questions"),
            "totemRuneCandidate": rune_candidate,
            "landmarkReference": f"{landmark_source}：后续地名可引用“{member_name}的{legend_title}”。",
            "contested": question_count > 0,
            "renownReward": LIVING_LEGEND_RENOWN_REWARD,
            "personalRenownReward": LIVING_LEGEND_PERSONAL_RENOWN_REWARD,
            "createdAt": datetime.now().isoformat(),
        }
        records = tribe.setdefault("living_legend_records", [])
        records.append(record)
        tribe["living_legend_records"] = records[-LIVING_LEGEND_RECORD_LIMIT:]
        tribe["living_legend_candidates"] = [
            item for item in (tribe.get("living_legend_candidates", []) or [])
            if item.get("id") != candidate.get("id")
        ]

        dispute_text = "，质疑也被一并刻进来源链" if question_count else ""
        detail = f"{member_name} 以“{legend_title}”被写入活人传说榜：{candidate.get('sourceTitle', '部落记忆')}{dispute_text}。图腾旁出现“{rune_candidate}”，部落声望 +{LIVING_LEGEND_RENOWN_REWARD}，个人声望 +{LIVING_LEGEND_PERSONAL_RENOWN_REWARD}。"
        self._add_tribe_history(tribe, "ritual", "活人传说定榜", detail, member_id, {"kind": "living_legend_record", "record": record})
        await self._notify_tribe(tribe_id, detail)
        rumor_text = f"{tribe.get('name', '某个部落')} 将 {member_name} 记为“{legend_title}”：{candidate.get('sourceTitle', '部落记忆')}。"
        record["worldRumorText"] = rumor_text
        await self._publish_world_rumor(
            "living_legend",
            "活人传说",
            rumor_text,
            {"tribeId": tribe_id, "memberId": member_id, "recordId": record["id"]}
        )
