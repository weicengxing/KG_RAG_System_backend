from datetime import datetime


class GameBoundaryOutcomeMixin:
    async def resolve_boundary_outcome(self, player_id: str, outcome_id: str, response_key: str = ""):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        outcomes = tribe.get("boundary_outcomes", []) or []
        outcome = next((item for item in outcomes if isinstance(item, dict) and item.get("id") == outcome_id), None)
        if not outcome or outcome.get("status") != "pending":
            await self._send_tribe_error(player_id, "这条边界结果已经处理过了")
            return

        reward = dict(outcome.get("reward") or {})
        if outcome.get("kind") == "resource_site_contest":
            response_key = response_key if response_key in {"hold", "cede", "trade_path"} else "hold"
            reward = self._apply_resource_contest_response(tribe, outcome, response_key)
        reward_parts = self._apply_tribe_reward(tribe, reward)

        relation_records = tribe.setdefault("boundary_relations", {})
        relation_progress = relation_records.get(outcome.get("otherTribeId"), {})
        if outcome.get("kind") == "resource_site_contest":
            relation_delta = int(outcome.get("relationDelta", 0) or 0)
            trade_delta = int(outcome.get("tradeTrustDelta", 0) or 0)
            relation_progress["score"] = max(-9, min(9, int(relation_progress.get("score", 0) or 0) + relation_delta))
            if trade_delta:
                relation_progress["tradeTrust"] = max(0, min(9, int(relation_progress.get("tradeTrust", 0) or 0) + trade_delta))
            if relation_delta:
                reward_parts.append(f"关系{relation_delta:+d}")
            if trade_delta:
                reward_parts.append(f"信任+{trade_delta}")
            if outcome.get("marketPact"):
                reward_parts.append("互市约定修正")
        elif outcome.get("state") == "hostile":
            relation_progress["score"] = max(-9, int(relation_progress.get("score", 0) or 0) - 1)
        else:
            relation_progress["score"] = min(9, int(relation_progress.get("score", 0) or 0) + 1)
        relation_progress["lastResolvedAt"] = datetime.now().isoformat()
        relation_records[outcome.get("otherTribeId")] = relation_progress

        observer_shift = self._apply_observer_outcome_shift(tribe, "boundary_outcome", outcome.get("id")) if hasattr(self, "_apply_observer_outcome_shift") else None
        if observer_shift:
            reward_parts.extend(observer_shift.get("rewardParts", []))

        member = tribe.get("members", {}).get(player_id, {})
        outcome["status"] = "resolved"
        outcome["resolvedAt"] = datetime.now().isoformat()
        record = {
            "kind": "boundary_outcome",
            "title": outcome.get("title", "边界结果"),
            "summary": outcome.get("summary", ""),
            "state": outcome.get("state"),
            "responseKey": response_key,
            "responseLabel": outcome.get("responseLabel"),
            "otherTribeName": outcome.get("otherTribeName", "其他部落"),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "observerShift": observer_shift,
            "createdAt": outcome.get("createdAt"),
            "resolvedAt": outcome.get("resolvedAt")
        }
        detail = f"{record['memberName']} 处理了边界结果“{record['title']}”：{record['summary']} {'、'.join(reward_parts)}。"
        if observer_shift:
            detail += f" {observer_shift.get('summary')}"
        self._add_tribe_history(tribe, "governance", "处理边界结果", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self._publish_world_rumor(
            "territory",
            record["title"],
            f"{tribe.get('name', '部落')} 在与 {record['otherTribeName']} 的边界上处理了“{record['title']}”。",
            {"tribeId": tribe_id, "outcomeId": outcome_id, "state": outcome.get("state")}
        )
        await self.broadcast_tribe_state(tribe_id)
        if outcome.get("kind") == "resource_site_contest" and response_key == "trade_path" and outcome.get("otherTribeId"):
            await self.broadcast_tribe_state(outcome.get("otherTribeId"))
