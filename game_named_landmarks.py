from datetime import datetime
import random

from game_config import *


TRIBE_NAMED_LANDMARK_CONTEST_LIMIT = 4
TRIBE_NAMED_LANDMARK_CONTEST_OPTION_LIMIT = 6
TRIBE_NAMED_LANDMARK_CONTEST_KINDS = {
    "alias": {"label": "异名", "summary": "给他部落已定稿地名提出新的称呼。"},
    "old": {"label": "旧名", "summary": "声称这里早有旧名，应当压过新名。"},
    "mock": {"label": "讽名", "summary": "用带刺的外号争夺传闻里的称呼。"}
}


class GameNamedLandmarkMixin:
    def _named_landmark_support_target(self, tribe: dict) -> int:
        member_count = len(tribe.get("members", {}) or {})
        return min(TRIBE_NAMED_LANDMARK_SUPPORT_TARGET, max(1, member_count))

    def _named_landmark_position(self, x: float, z: float) -> tuple[float, float]:
        return (
            max(-490, min(490, float(x or 0))),
            max(-490, min(490, float(z or 0)))
        )

    def _active_named_landmarks(self, tribe: dict) -> list:
        if not tribe:
            return []
        landmarks = [
            item for item in (tribe.get("named_landmarks", []) or [])
            if isinstance(item, dict) and item.get("status", "active") == "active"
        ]
        tribe["named_landmarks"] = landmarks[-TRIBE_NAMED_LANDMARK_LIMIT:]
        return tribe["named_landmarks"]

    def _active_named_landmark_proposals(self, tribe: dict) -> list:
        if not tribe:
            return []
        proposals = [
            item for item in (tribe.get("named_landmark_proposals", []) or [])
            if isinstance(item, dict) and item.get("status", "open") == "open"
        ]
        tribe["named_landmark_proposals"] = proposals[-TRIBE_NAMED_LANDMARK_PROPOSAL_LIMIT:]
        return tribe["named_landmark_proposals"]

    def _tribe_id_for_named_landmark_state(self, tribe: dict) -> str | None:
        for tribe_id, candidate in (self.tribes or {}).items():
            if candidate is tribe:
                return tribe_id
        return None

    def _iter_named_landmarks_with_tribes(self):
        for tribe_id, tribe in (self.tribes or {}).items():
            for landmark in self._active_named_landmarks(tribe):
                yield tribe_id, tribe, landmark

    def _find_named_landmark(self, landmark_id: str):
        for tribe_id, tribe, landmark in self._iter_named_landmarks_with_tribes():
            if landmark.get("id") == landmark_id:
                return tribe_id, tribe, landmark
        return None, None, None

    def _active_named_landmark_contests(self, landmark: dict) -> list:
        contests = [
            item for item in (landmark.get("nameContests", []) or [])
            if isinstance(item, dict) and item.get("status", "open") == "open"
        ]
        landmark["nameContests"] = contests[-TRIBE_NAMED_LANDMARK_CONTEST_LIMIT:]
        return landmark["nameContests"]

    def _named_landmark_contest_source(self, source_key: str) -> tuple[str, str] | None:
        parts = str(source_key or "").split(":", 2)
        if len(parts) == 3 and parts[0] == "contest" and parts[2] in TRIBE_NAMED_LANDMARK_CONTEST_KINDS:
            return parts[1], parts[2]
        return None

    def _named_landmark_support_method(self, tribe: dict) -> dict:
        if tribe.get("dispute_witness_records") or tribe.get("common_judge_records"):
            return {"key": "witness", "label": "见证石", "score": 2}
        if tribe.get("traveler_song_records") or tribe.get("traveler_tune_lineages"):
            return {"key": "song", "label": "传唱", "score": 2}
        if tribe.get("history_facts") or tribe.get("map_memories") or tribe.get("living_legend_records"):
            return {"key": "evidence", "label": "证据", "score": 2}
        return {"key": "support", "label": "支持", "score": 1}

    def _named_landmark_support_entry(self, tribe: dict, player_id: str) -> dict:
        member = tribe.get("members", {}).get(player_id, {})
        method = self._named_landmark_support_method(tribe)
        return {
            "playerId": player_id,
            "memberName": member.get("name", "成员"),
            "methodKey": method.get("key"),
            "methodLabel": method.get("label"),
            "score": method.get("score", 1),
            "supportedAt": datetime.now().isoformat()
        }

    def _named_landmark_support_score(self, supporters: list) -> int:
        return sum(int(item.get("score", 1) or 1) for item in (supporters or []) if isinstance(item, dict))

    def _named_landmark_supporter_labels(self, supporters: list) -> list:
        labels = []
        for support in supporters or []:
            if not isinstance(support, dict):
                continue
            method = support.get("methodLabel") or "支持"
            labels.append(f"{support.get('memberName', '成员')}({method})")
        return labels

    def _named_landmark_source_available(self, tribe: dict, source_key: str) -> bool:
        history = " ".join(
            f"{item.get('type', '')} {item.get('title', '')} {item.get('detail', '')}"
            for item in (tribe.get("history", []) or [])[-40:]
            if isinstance(item, dict)
        )
        if source_key == "first_scout":
            return bool(
                int(tribe.get("discovery_progress", 0) or 0) > 0
                or tribe.get("discoveries")
                or tribe.get("map_memories")
                or tribe.get("scouted_resource_sites")
                or "洞" in history
                or "侦察" in history
                or "探索" in history
            )
        if source_key == "rescue":
            return bool(
                tribe.get("emergency_followup_tasks")
                or tribe.get("mutual_aid_alert_records")
                or "救" in history
                or "补救" in history
                or "互助" in history
            )
        if source_key == "war":
            has_pressure = any(
                int(relation.get("warPressure", 0) or 0) > 0
                for relation in (tribe.get("boundary_relations", {}) or {}).values()
                if isinstance(relation, dict)
            )
            return bool(
                has_pressure
                or tribe.get("war_records")
                or tribe.get("boundary_outcomes")
                or tribe.get("small_conflicts")
                or "战争" in history
                or "冲突" in history
                or "停战" in history
            )
        if source_key == "ritual":
            return bool(
                tribe.get("celebration_echo_records")
                or tribe.get("communal_cook_records")
                or tribe.get("drum_rhythm_records")
                or tribe.get("group_emote_records")
                or "仪式" in history
                or "庆功" in history
                or "烹饪" in history
                or "鼓点" in history
            )
        return False

    def _public_named_landmark_options(self, tribe: dict) -> dict:
        options = {}
        for key, config in TRIBE_NAMED_LANDMARK_SOURCES.items():
            options[key] = {
                **config,
                "available": self._named_landmark_source_available(tribe, key),
                "rewardLabel": self._reward_summary_text(config.get("reward", {})) if hasattr(self, "_reward_summary_text") else ""
            }
        tribe_id = self._tribe_id_for_named_landmark_state(tribe)
        contest_count = 0
        for owner_id, owner_tribe, landmark in self._iter_named_landmarks_with_tribes():
            if not tribe_id or owner_id == tribe_id:
                continue
            for kind, config in TRIBE_NAMED_LANDMARK_CONTEST_KINDS.items():
                if contest_count >= TRIBE_NAMED_LANDMARK_CONTEST_OPTION_LIMIT:
                    return options
                key = f"contest:{landmark.get('id')}:{kind}"
                options[key] = {
                    "label": f"{config.get('label')}：{landmark.get('name', '有名之地')}",
                    "summary": f"{config.get('summary')} 目标：{owner_tribe.get('name', '他部落')}的“{landmark.get('name', '有名之地')}”。",
                    "available": True,
                    "rewardLabel": "争名达标后写入双方历史和世界传闻"
                }
                contest_count += 1
        return options

    def _public_named_landmarks(self, tribe: dict) -> list:
        return [
            {
                "id": item.get("id"),
                "label": item.get("label", "有名之地"),
                "name": item.get("name", "未名地"),
                "sourceKey": item.get("sourceKey"),
                "sourceLabel": item.get("sourceLabel", "部落命名"),
                "summary": item.get("contestSummary") or item.get("summary", ""),
                "x": item.get("x", 0),
                "z": item.get("z", 0),
                "namedByName": item.get("namedByName", "成员"),
                "supportCount": len(item.get("supporters", []) or []),
                "rewardParts": item.get("rewardParts", []),
                "contestName": item.get("contestName"),
                "contestSummary": item.get("contestSummary"),
                "nameContests": [
                    {
                        "id": contest.get("id"),
                        "challengerTribeName": contest.get("challengerTribeName"),
                        "challengerName": contest.get("challengerName"),
                        "kindLabel": contest.get("kindLabel"),
                        "supportScore": self._named_landmark_support_score(contest.get("supporters", [])),
                        "defenseScore": self._named_landmark_support_score(contest.get("defenders", [])),
                        "supportTarget": contest.get("supportTarget", self._named_landmark_support_target(tribe)),
                        "status": contest.get("status", "open")
                    }
                    for contest in self._active_named_landmark_contests(item)
                ],
                "createdAt": item.get("createdAt")
            }
            for item in self._active_named_landmarks(tribe)
        ]

    def _public_named_landmark_proposals(self, tribe: dict) -> list:
        target = self._named_landmark_support_target(tribe)
        proposals = [
            {
                "id": item.get("id"),
                "name": item.get("name", "未名地"),
                "sourceKey": item.get("sourceKey"),
                "sourceLabel": item.get("sourceLabel", "部落命名"),
                "summary": item.get("summary", ""),
                "x": item.get("x", 0),
                "z": item.get("z", 0),
                "proposedByName": item.get("proposedByName", "成员"),
                "supportCount": self._named_landmark_support_score(item.get("supporters", [])) if item.get("contest") else len(item.get("supporters", []) or []),
                "supportTarget": item.get("supportTarget", target),
                "supporterNames": self._named_landmark_supporter_labels(item.get("supporters", [])) if item.get("contest") else [support.get("memberName", "成员") for support in (item.get("supporters", []) or [])],
                "createdAt": item.get("createdAt")
            }
            for item in self._active_named_landmark_proposals(tribe)
        ]
        for landmark in self._active_named_landmarks(tribe):
            for contest in self._active_named_landmark_contests(landmark):
                proposals.append({
                    "id": f"contest_defend::{contest.get('id')}",
                    "name": landmark.get("name", "有名之地"),
                    "sourceKey": "contest_defense",
                    "sourceLabel": "守名回应",
                    "summary": f"{contest.get('challengerTribeName', '他部落')} 提出{contest.get('kindLabel', '异名')}“{contest.get('challengerName', '新名')}”，可用支持、证据、传唱或见证石守住原名。",
                    "x": landmark.get("x", 0),
                    "z": landmark.get("z", 0),
                    "proposedByName": contest.get("challengerTribeName", "他部落"),
                    "supportCount": self._named_landmark_support_score(contest.get("defenders", [])),
                    "supportTarget": contest.get("supportTarget", target),
                    "supporterNames": self._named_landmark_supporter_labels(contest.get("defenders", [])),
                    "createdAt": contest.get("createdAt")
                })
        return proposals

    def _apply_named_landmark_reward(self, tribe: dict, reward: dict) -> list:
        parts = []
        for key, label, tribe_key in (
            ("renown", "声望", "renown"),
            ("tradeReputation", "贸易信誉", "trade_reputation"),
            ("discoveryProgress", "发现", "discovery_progress")
        ):
            value = int((reward or {}).get(key, 0) or 0)
            if value:
                tribe[tribe_key] = int(tribe.get(tribe_key, 0) or 0) + value
                parts.append(f"{label}+{value}")
        return parts

    def _clean_named_landmark_name(self, name: str) -> str:
        cleaned = " ".join(str(name or "").strip().split())
        cleaned = cleaned.replace("<", "").replace(">", "").replace("{", "").replace("}", "")
        return cleaned[:TRIBE_NAMED_LANDMARK_NAME_MAX]

    async def _propose_named_landmark_contest(self, player_id: str, source_key: str, name: str):
        contest_source = self._named_landmark_contest_source(source_key)
        if not contest_source:
            return False
        landmark_id, kind = contest_source
        challenger_tribe_id = self.player_tribes.get(player_id)
        challenger_tribe = self.tribes.get(challenger_tribe_id)
        owner_id, owner_tribe, landmark = self._find_named_landmark(landmark_id)
        if not challenger_tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return True
        if not owner_tribe or not landmark:
            await self._send_tribe_error(player_id, "这处地名已经找不到了")
            return True
        if owner_id == challenger_tribe_id:
            await self._send_tribe_error(player_id, "不能争夺自己部落已经定稿的地名")
            return True
        clean_name = self._clean_named_landmark_name(name)
        if len(clean_name) < TRIBE_NAMED_LANDMARK_NAME_MIN:
            await self._send_tribe_error(player_id, f"争夺地名至少需要 {TRIBE_NAMED_LANDMARK_NAME_MIN} 个字")
            return True
        if clean_name == landmark.get("name"):
            await self._send_tribe_error(player_id, "新称呼不能和原地名相同")
            return True

        now = datetime.now()
        kind_config = TRIBE_NAMED_LANDMARK_CONTEST_KINDS.get(kind, {})
        support_entry = self._named_landmark_support_entry(challenger_tribe, player_id)
        support_target = max(2, self._named_landmark_support_target(challenger_tribe))
        contest_id = f"named_landmark_contest_{challenger_tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}"
        contest = {
            "id": contest_id,
            "status": "open",
            "targetLandmarkId": landmark_id,
            "originalName": landmark.get("name", "有名之地"),
            "challengerName": clean_name,
            "kind": kind,
            "kindLabel": kind_config.get("label", "异名"),
            "challengerTribeId": challenger_tribe_id,
            "challengerTribeName": challenger_tribe.get("name", "他部落"),
            "ownerTribeId": owner_id,
            "ownerTribeName": owner_tribe.get("name", "原部落"),
            "supporters": [support_entry],
            "defenders": [],
            "supportTarget": support_target,
            "createdAt": now.isoformat()
        }
        proposal = {
            "id": contest_id,
            "status": "open",
            "name": clean_name,
            "sourceKey": source_key,
            "sourceLabel": f"地名争夺·{contest['kindLabel']}",
            "summary": f"争夺{owner_tribe.get('name', '他部落')}的“{contest['originalName']}”，可用支持、证据、传唱或见证石推进。",
            "x": landmark.get("x", 0),
            "z": landmark.get("z", 0),
            "proposedBy": player_id,
            "proposedByName": support_entry.get("memberName", "成员"),
            "supporters": [support_entry],
            "supportTarget": support_target,
            "contest": contest,
            "createdAt": now.isoformat()
        }
        proposals = self._active_named_landmark_proposals(challenger_tribe)
        proposals.append(proposal)
        challenger_tribe["named_landmark_proposals"] = proposals[-TRIBE_NAMED_LANDMARK_PROPOSAL_LIMIT:]
        contests = self._active_named_landmark_contests(landmark)
        contests.append(contest)
        landmark["nameContests"] = contests[-TRIBE_NAMED_LANDMARK_CONTEST_LIMIT:]

        detail = f"{support_entry.get('memberName', '成员')} 提出把“{contest['originalName']}”争称为“{clean_name}”（{contest['kindLabel']}）。"
        self._add_tribe_history(challenger_tribe, "world_event", "提出地名争夺", detail, player_id, {"kind": "named_landmark_contest", "contest": contest})
        self._add_tribe_history(owner_tribe, "world_event", "地名被争夺", f"{challenger_tribe.get('name', '他部落')} 想把“{contest['originalName']}”改称为“{clean_name}”。", player_id, {"kind": "named_landmark_contest", "contest": contest})
        await self._notify_tribe(challenger_tribe_id, detail)
        await self._notify_tribe(owner_id, f"{challenger_tribe.get('name', '他部落')} 正在争夺地名“{contest['originalName']}”。")
        await self.broadcast_tribe_state(challenger_tribe_id)
        await self.broadcast_tribe_state(owner_id)
        return True

    def _find_named_landmark_contest(self, contest_id: str):
        for owner_id, owner_tribe, landmark in self._iter_named_landmarks_with_tribes():
            for contest in self._active_named_landmark_contests(landmark):
                if contest.get("id") == contest_id:
                    challenger_tribe = self.tribes.get(contest.get("challengerTribeId"))
                    proposal = None
                    if challenger_tribe:
                        proposal = next((item for item in self._active_named_landmark_proposals(challenger_tribe) if item.get("id") == contest_id), None)
                    return owner_id, owner_tribe, landmark, contest, challenger_tribe, proposal
        return None, None, None, None, None, None

    def _sync_named_landmark_contest_support(self, contest: dict, proposal: dict | None):
        if proposal is not None:
            proposal["supporters"] = list(contest.get("supporters", []) or [])
            proposal["supportTarget"] = contest.get("supportTarget", proposal.get("supportTarget"))
            proposal["contest"] = contest

    async def _support_named_landmark_contest(self, player_id: str, contest_id: str, side: str):
        actor_tribe_id = self.player_tribes.get(player_id)
        actor_tribe = self.tribes.get(actor_tribe_id)
        owner_id, owner_tribe, landmark, contest, challenger_tribe, proposal = self._find_named_landmark_contest(contest_id)
        if not actor_tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return True
        if not contest:
            await self._send_tribe_error(player_id, "这场地名争夺已经结束")
            return True
        if side == "defend" and actor_tribe_id != owner_id:
            await self._send_tribe_error(player_id, "只有原地名部落能守名")
            return True
        if side == "challenge" and actor_tribe_id != contest.get("challengerTribeId"):
            await self._send_tribe_error(player_id, "只有提出争名的部落能推动这个新称呼")
            return True
        key = "defenders" if side == "defend" else "supporters"
        supporters = contest.setdefault(key, [])
        if any(item.get("playerId") == player_id for item in supporters):
            await self._send_tribe_error(player_id, "你已经回应过这场地名争夺")
            return True
        entry = self._named_landmark_support_entry(actor_tribe, player_id)
        supporters.append(entry)
        self._sync_named_landmark_contest_support(contest, proposal)
        action_text = "守住原名" if side == "defend" else "推动新名"
        detail = f"{entry.get('memberName', '成员')} 用{entry.get('methodLabel', '支持')}{action_text}：“{contest.get('challengerName', '新名')}”。"
        self._add_tribe_history(actor_tribe, "world_event", "回应地名争夺", detail, player_id, {"kind": "named_landmark_contest_support", "contestId": contest_id, "side": side})
        await self._notify_tribe(actor_tribe_id, detail)
        if self._named_landmark_support_score(supporters) >= int(contest.get("supportTarget", 1) or 1):
            await self._finalize_named_landmark_contest(owner_id, owner_tribe, landmark, contest, "challenge" if side == "challenge" else "defense", player_id, proposal)
            return True
        await self.broadcast_tribe_state(actor_tribe_id)
        if owner_id and owner_id != actor_tribe_id:
            await self.broadcast_tribe_state(owner_id)
        return True

    async def _finalize_named_landmark_contest(self, owner_id: str, owner_tribe: dict, landmark: dict, contest: dict, winner: str, actor_id: str, proposal: dict | None = None):
        now = datetime.now()
        contest["status"] = "finalized"
        contest["winner"] = winner
        contest["finalizedAt"] = now.isoformat()
        challenger_tribe = self.tribes.get(contest.get("challengerTribeId"))
        if proposal is not None:
            proposal["status"] = "finalized"
        if challenger_tribe:
            challenger_tribe["named_landmark_proposals"] = [
                item for item in (challenger_tribe.get("named_landmark_proposals", []) or [])
                if item.get("id") != contest.get("id")
            ]
        record = {
            **contest,
            "resolvedAt": now.isoformat()
        }
        if winner == "challenge":
            previous_name = landmark.get("name", contest.get("originalName", "有名之地"))
            landmark["previousName"] = previous_name
            landmark["name"] = contest.get("challengerName", previous_name)
            landmark["label"] = landmark["name"]
            landmark["contestName"] = landmark["name"]
            landmark["contestSummary"] = f"{contest.get('challengerTribeName', '他部落')} 争名成功，旧称“{previous_name}”。"
            detail = f"“{previous_name}”被{contest.get('challengerTribeName', '他部落')}争称为“{landmark['name']}”。"
            rumor_text = f"{contest.get('challengerTribeName', '他部落')} 用{contest.get('kindLabel', '异名')}把“{previous_name}”争成了“{landmark['name']}”。"
        else:
            landmark["contestSummary"] = f"{owner_tribe.get('name', '部落')} 守住了“{landmark.get('name', '有名之地')}”。"
            detail = f"{owner_tribe.get('name', '部落')} 守住了地名“{landmark.get('name', '有名之地')}”。"
            rumor_text = f"{owner_tribe.get('name', '部落')} 用回应守住了“{landmark.get('name', '有名之地')}”，{contest.get('challengerTribeName', '他部落')}的“{contest.get('challengerName', '新名')}”暂时只留在传闻里。"
        landmark["nameContests"] = [
            item for item in (landmark.get("nameContests", []) or [])
            if item.get("id") != contest.get("id")
        ]
        landmark.setdefault("nameContestRecords", []).append(record)
        landmark["nameContestRecords"] = landmark["nameContestRecords"][-TRIBE_NAMED_LANDMARK_CONTEST_LIMIT:]
        self._add_tribe_history(owner_tribe, "world_event", "地名争夺定稿", detail, actor_id, {"kind": "named_landmark_contest_result", "contest": record})
        if challenger_tribe:
            self._add_tribe_history(challenger_tribe, "world_event", "地名争夺定稿", detail, actor_id, {"kind": "named_landmark_contest_result", "contest": record})
        await self._publish_world_rumor("world_event", "地名争夺定稿", rumor_text, {"tribeId": owner_id, "landmarkId": landmark.get("id"), "contestId": contest.get("id")})
        await self._notify_tribe(owner_id, detail)
        if challenger_tribe:
            await self._notify_tribe(contest.get("challengerTribeId"), detail)
            await self.broadcast_tribe_state(contest.get("challengerTribeId"))
        await self.broadcast_tribe_state(owner_id)
        await self._broadcast_current_map()

    async def propose_named_landmark(self, player_id: str, source_key: str, name: str, x: float, z: float):
        if await self._propose_named_landmark_contest(player_id, source_key, name):
            return
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        config = TRIBE_NAMED_LANDMARK_SOURCES.get(source_key)
        if not config:
            await self._send_tribe_error(player_id, "未知命名来源")
            return
        if not self._named_landmark_source_available(tribe, source_key):
            await self._send_tribe_error(player_id, "部落还没有这类可命名的故事来源")
            return
        clean_name = self._clean_named_landmark_name(name)
        if len(clean_name) < TRIBE_NAMED_LANDMARK_NAME_MIN:
            await self._send_tribe_error(player_id, f"地名至少需要 {TRIBE_NAMED_LANDMARK_NAME_MIN} 个字")
            return
        if any(item.get("name") == clean_name for item in self._active_named_landmarks(tribe)):
            await self._send_tribe_error(player_id, "这个地名已经写进地图")
            return

        marker_x, marker_z = self._named_landmark_position(x, z)
        now = datetime.now()
        member = tribe.get("members", {}).get(player_id, {})
        member_name = member.get("name", "成员")
        proposal = {
            "id": f"named_landmark_proposal_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "status": "open",
            "name": clean_name,
            "sourceKey": source_key,
            "sourceLabel": config.get("label", "部落命名"),
            "summary": config.get("summary", ""),
            "x": marker_x,
            "z": marker_z,
            "proposedBy": player_id,
            "proposedByName": member_name,
            "supporters": [{
                "playerId": player_id,
                "memberName": member_name,
                "supportedAt": now.isoformat()
            }],
            "createdAt": now.isoformat()
        }
        proposals = self._active_named_landmark_proposals(tribe)
        proposals.append(proposal)
        tribe["named_landmark_proposals"] = proposals[-TRIBE_NAMED_LANDMARK_PROPOSAL_LIMIT:]

        detail = f"{member_name} 提议把当前位置命名为“{clean_name}”，来源是{config.get('label', '部落故事')}。"
        self._add_tribe_history(tribe, "world_event", "提名地标命名", detail, player_id, {"kind": "named_landmark_proposal", "proposal": proposal})
        await self._notify_tribe(tribe_id, detail)
        if len(proposal["supporters"]) >= self._named_landmark_support_target(tribe):
            await self._finalize_named_landmark(tribe_id, tribe, proposal, player_id)
            return
        await self.broadcast_tribe_state(tribe_id)

    async def support_named_landmark(self, player_id: str, proposal_id: str):
        if str(proposal_id or "").startswith("contest_defend::"):
            await self._support_named_landmark_contest(player_id, str(proposal_id).split("::", 1)[1], "defend")
            return
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        proposal = next((item for item in self._active_named_landmark_proposals(tribe) if item.get("id") == proposal_id), None)
        if not proposal:
            await self._support_named_landmark_contest(player_id, proposal_id, "challenge")
            return
        if proposal.get("contest"):
            await self._support_named_landmark_contest(player_id, proposal_id, "challenge")
            return
        supporters = proposal.setdefault("supporters", [])
        if any(item.get("playerId") == player_id for item in supporters):
            await self._send_tribe_error(player_id, "你已经支持过这个地名")
            return
        member = tribe.get("members", {}).get(player_id, {})
        supporters.append({
            "playerId": player_id,
            "memberName": member.get("name", "成员"),
            "supportedAt": datetime.now().isoformat()
        })
        detail = f"{member.get('name', '成员')} 支持把这里叫作“{proposal.get('name', '未名地')}”。"
        self._add_tribe_history(tribe, "world_event", "支持地标命名", detail, player_id, {"kind": "named_landmark_support", "proposalId": proposal_id})
        await self._notify_tribe(tribe_id, detail)
        if len(supporters) >= self._named_landmark_support_target(tribe):
            await self._finalize_named_landmark(tribe_id, tribe, proposal, player_id)
            return
        await self.broadcast_tribe_state(tribe_id)

    async def _finalize_named_landmark(self, tribe_id: str, tribe: dict, proposal: dict, actor_id: str):
        config = TRIBE_NAMED_LANDMARK_SOURCES.get(proposal.get("sourceKey"), {})
        reward_parts = self._apply_named_landmark_reward(tribe, config.get("reward", {}))
        now = datetime.now()
        landmark = {
            "id": f"named_landmark_{tribe_id}_{int(now.timestamp() * 1000)}_{random.randint(100, 999)}",
            "type": "named_landmark",
            "status": "active",
            "label": proposal.get("name", "有名之地"),
            "name": proposal.get("name", "有名之地"),
            "sourceKey": proposal.get("sourceKey"),
            "sourceLabel": proposal.get("sourceLabel", "部落命名"),
            "summary": proposal.get("summary", ""),
            "x": proposal.get("x", 0),
            "z": proposal.get("z", 0),
            "y": 0,
            "size": 0.85,
            "namedBy": actor_id,
            "namedByName": proposal.get("proposedByName", "成员"),
            "supporters": list(proposal.get("supporters", []) or []),
            "rewardParts": reward_parts,
            "createdAt": now.isoformat()
        }
        proposal["status"] = "finalized"
        proposal["finalizedAt"] = now.isoformat()
        tribe["named_landmark_proposals"] = [
            item for item in (tribe.get("named_landmark_proposals", []) or [])
            if item.get("id") != proposal.get("id")
        ]
        landmarks = self._active_named_landmarks(tribe)
        landmarks.append(landmark)
        tribe["named_landmarks"] = landmarks[-TRIBE_NAMED_LANDMARK_LIMIT:]
        tribe.setdefault("named_landmark_records", []).append(landmark)
        tribe["named_landmark_records"] = tribe["named_landmark_records"][-TRIBE_NAMED_LANDMARK_RECORD_LIMIT:]
        detail = f"“{landmark['name']}”成为{tribe.get('name', '部落')}的新地名。"
        if reward_parts:
            detail += f" {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "world_event", "地标命名定稿", detail, actor_id, {"kind": "named_landmark", "landmark": landmark})
        await self._publish_world_rumor(
            "world_event",
            "新地名写入地图",
            f"{tribe.get('name', '部落')} 把一处地方称作“{landmark['name']}”，以后传闻会用这个名字回望那里。",
            {"tribeId": tribe_id, "landmarkId": landmark.get("id")}
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
