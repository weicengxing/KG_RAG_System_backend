import random
from datetime import datetime

from game_config import *


class GameRouteTribeActionsMixin:
    def _active_until_still_valid(self, item: dict, now=None) -> bool:
        if not isinstance(item, dict):
            return False
        active_until = item.get("activeUntil")
        if not active_until:
            return False
        try:
            return datetime.fromisoformat(active_until) > (now or datetime.now())
        except (TypeError, ValueError):
            return False

    def _store_current_environment(self, env: dict):
        map_data = self.maps.get(self.current_map_name) or {}
        map_data["environment"] = env
        map_data["updated_at"] = datetime.now().isoformat()

    async def create_tribe(self, player_id: str, name: str):
        if player_id in self.player_tribes:
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "你已经属于一个部落"
            })
            return

        tribe_id = self._make_tribe_id()
        member = {
            "id": player_id,
            "name": self._get_player_name(player_id),
            "role": "leader",
            "contribution": 0,
            "allocation": {"wood": 0, "stone": 0},
            "joined_at": datetime.now().isoformat()
        }
        self.tribes[tribe_id] = {
            "id": tribe_id,
            "name": self._normalize_tribe_name(name),
            "leader_id": player_id,
            "elder_ids": [],
            "members": {player_id: member},
            "storage": {"wood": 0, "stone": 0},
            "target_index": 0,
            "target": {},
            "announcement": "欢迎来到部落营地。先采集木材和石块，送进公共仓库。",
            "announcement_updated_at": datetime.now().isoformat(),
            "announcement_updated_by": player_id,
            "vote_cooldowns": {},
            "punish_cooldowns": {},
            "punishments": [],
            "applications": {},
            "ritual": {},
            "runes": [],
            "discoveries": [],
            "discovery_progress": 0,
            "food": 0,
            "last_food_decay_at": datetime.now().isoformat(),
            "renown": 0,
            "history": [],
            "ritual_history": [],
            "created_at": datetime.now().isoformat(),
            "camp": self._build_tribe_camp(tribe_id, self._normalize_tribe_name(name))
        }
        self._refresh_tribe_target(self.tribes[tribe_id])
        self.player_tribes[player_id] = tribe_id
        await self._move_player_to_tribe_spawn(player_id, tribe_id)
        await self.broadcast_tribe_state(tribe_id)

    async def request_join_tribe(self, player_id: str, tribe_id: str, message: str = ""):
        if player_id in self.player_tribes:
            await self._send_tribe_error(player_id, "你已经属于一个部落")
            return

        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "部落不存在")
            return

        applications = tribe.setdefault("applications", {})
        existing = applications.get(player_id)
        if existing and existing.get("status") == "pending":
            await self._send_tribe_error(player_id, "你的加入申请正在等待首领或长老审核")
            return

        application = {
            "id": self._make_application_id(),
            "player_id": player_id,
            "player_name": self._get_player_name(player_id),
            "message": (message or "想加入部落").strip()[:80] or "想加入部落",
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        applications[player_id] = application
        await self.send_personal_message(player_id, {
            "type": "tribe_notice",
            "message": f"已向 {tribe.get('name', '部落')} 提交加入申请"
        })
        await self._notify_tribe(tribe_id, f"{application['player_name']} 申请加入部落，首领或长老可在部落面板审核。")
        self._add_tribe_history(tribe, "application", "收到加入申请", f"{application['player_name']}：{application['message']}", player_id)
        await self.broadcast_tribe_state(tribe_id)

    async def approve_tribe_application(self, actor_id: str, application_id: str, approved: bool):
        tribe_id = self.player_tribes.get(actor_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(actor_id, "请先加入一个部落")
            return

        actor = tribe.get("members", {}).get(actor_id, {})
        if not self._can_review_applications(actor):
            await self._send_tribe_error(actor_id, "只有首领或长老可以审核加入申请")
            return

        application = next((
            item
            for item in tribe.setdefault("applications", {}).values()
            if item.get("id") == application_id and item.get("status") == "pending"
        ), None)
        if not application:
            await self._send_tribe_error(actor_id, "申请不存在或已经处理")
            return

        target_id = application.get("player_id")
        if approved and target_id in self.player_tribes:
            application["status"] = "expired"
            application["reviewed_at"] = datetime.now().isoformat()
            application["reviewed_by"] = actor_id
            await self._send_tribe_error(actor_id, "该玩家已经加入其他部落")
            await self.broadcast_tribe_state(tribe_id)
            return

        application["status"] = "approved" if approved else "rejected"
        application["reviewed_at"] = datetime.now().isoformat()
        application["reviewed_by"] = actor_id

        if approved:
            tribe["members"][target_id] = {
                "id": target_id,
                "name": application.get("player_name") or self._get_player_name(target_id),
                "role": "member",
                "contribution": 0,
                "allocation": {"wood": 0, "stone": 0},
                "joined_at": datetime.now().isoformat()
            }
            self.player_tribes[target_id] = tribe_id
            await self._move_player_to_tribe_spawn(target_id, tribe_id)
            await self.send_personal_message(target_id, self.get_player_tribe_state(target_id))
            self._add_tribe_history(tribe, "application", "成员加入部落", f"{actor.get('name', '管理者')} 通过了 {application.get('player_name', '新成员')} 的申请。", actor_id)
            await self._notify_tribe(tribe_id, f"{application.get('player_name', '新成员')} 已通过审核，加入了部落。")
        else:
            await self.send_personal_message(target_id, {
                "type": "tribe_notice",
                "message": f"你加入 {tribe.get('name', '部落')} 的申请已被拒绝"
            })
            self._add_tribe_history(tribe, "application", "拒绝加入申请", f"{actor.get('name', '管理者')} 拒绝了 {application.get('player_name', '玩家')} 的申请。", actor_id)
            await self._notify_tribe(tribe_id, f"{application.get('player_name', '玩家')} 的加入申请已被拒绝。")

        await self.broadcast_tribe_state(tribe_id)

    async def contribute_to_tribe(self, player_id: str, resources: dict):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "请先加入一个部落"
            })
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        total_points = 0
        for key in ("wood", "stone"):
            try:
                amount = int(resources.get(key, 0))
            except (TypeError, ValueError):
                amount = 0
            amount = max(0, min(999, amount))
            if amount <= 0:
                continue
            storage[key] = storage.get(key, 0) + amount
            total_points += amount

        if total_points <= 0:
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "没有可上交的资源"
            })
            return

        member = tribe["members"].get(player_id)
        newcomer_moment = None
        if member:
            previous_contribution = int(member.get("contribution", 0) or 0)
            member["contribution"] = member.get("contribution", 0) + total_points
            newcomer_moment = self._maybe_create_newcomer_key_moment(
                player_id,
                tribe,
                member,
                previous_contribution,
                total_points
            )

        previous_target = self._build_target_state(tribe)
        self._refresh_tribe_target(tribe)
        current_target = tribe.get("target", {})

        if current_target.get("completed") and not previous_target.get("completed"):
            await self._notify_tribe(
                tribe_id,
                f"部落目标已完成：{current_target.get('title', '当前目标')}。前往石器台即可推进下一阶段。"
            )

        if newcomer_moment:
            player_name = member.get("name", "新人") if member else self._get_player_name(player_id)
            detail = f"{player_name} 触发新人关键时刻“{newcomer_moment.get('label', '新人关键时刻')}”：{newcomer_moment.get('summary', '')} 个人声望 +{TRIBE_NEWCOMER_KEY_RENOWN}。"
            self._add_tribe_history(
                tribe,
                "governance",
                "新人关键时刻",
                detail,
                player_id,
                {"kind": "newcomer_key_moment", **newcomer_moment}
            )
            await self._notify_tribe(tribe_id, detail)
            await self.send_personal_conflict_status(player_id)

        await self.broadcast_tribe_state(tribe_id)

    async def advance_tribe_target(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "请先加入一个部落"
            })
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "只有首领或长老可以推进部落目标"
            })
            return

        current_target = self._build_target_state(tribe)
        if not current_target.get("completed"):
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "当前目标还未完成，继续向仓库补给资源"
            })
            return

        if not self._advance_tribe_target_state(tribe):
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "当前已经是最终阶段目标"
            })
            return

        next_target = tribe.get("target", {})
        await self._notify_tribe(
            tribe_id,
            f"石器台已制定新目标：{next_target.get('title', '新的建设目标')}。"
        )
        await self.broadcast_tribe_state(tribe_id)

    async def build_tribe_structure(self, player_id: str, building_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以发起部落建造")
            return

        layout = self._tribe_building_layout_by_key(building_key)
        if not layout or layout.get("initial"):
            await self._send_tribe_error(player_id, "未知或不可建造的建筑")
            return

        if self._is_tribe_building_built(tribe, building_key):
            await self._send_tribe_error(player_id, "该建筑已经建成")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        cost = self._tribe_building_cost(tribe, layout)
        required_wood = cost["wood"]
        required_stone = cost["stone"]
        if int(storage.get("wood", 0) or 0) < required_wood or int(storage.get("stone", 0) or 0) < required_stone:
            await self._send_tribe_error(player_id, f"公共仓库资源不足：需要木材 {required_wood}、石块 {required_stone}")
            return

        storage["wood"] = int(storage.get("wood", 0) or 0) - required_wood
        storage["stone"] = int(storage.get("stone", 0) or 0) - required_stone
        camp = tribe.setdefault("camp", self._build_tribe_camp(tribe_id, tribe.get("name", "部落")))
        camp.setdefault("buildings", []).append(self._make_tribe_building(tribe, layout))
        self._add_tribe_history(
            tribe,
            "build",
            f"建成{layout.get('label', '建筑')}",
            f"{member.get('name', '管理者')} 消耗木材 {required_wood}、石块 {required_stone} 完成建设。",
            player_id
        )
        discount_text = ""
        if cost["woodDiscountPercent"] or cost["stoneDiscountPercent"]:
            discount_text = f" 图腾铭文节省后消耗木材 {required_wood}、石块 {required_stone}。"
        await self._notify_tribe(tribe_id, f"{member.get('name', '管理者')} 建成了{layout.get('label', '建筑')}。{discount_text}")
        await self.broadcast_tribe_state(tribe_id)

    async def set_tribe_announcement(self, player_id: str, announcement: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以更新部落公告")
            return

        text = (announcement or "").strip()[:120]
        if not text:
            await self._send_tribe_error(player_id, "公告不能为空")
            return

        tribe["announcement"] = text
        tribe["announcement_updated_at"] = datetime.now().isoformat()
        tribe["announcement_updated_by"] = player_id
        self._add_tribe_history(
            tribe,
            "announcement",
            "更新部落公告",
            text,
            player_id,
            {
                "kind": "announcement",
                "text": text,
                "updatedByName": member.get("name", "管理者"),
                "updatedAt": tribe["announcement_updated_at"]
            }
        )
        await self._notify_tribe(tribe_id, f"部落公告已更新：{text}")
        await self.broadcast_tribe_state(tribe_id)

    async def allocate_tribe_resources(self, player_id: str, target_id: str, resources: dict):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        members = tribe.get("members", {})
        actor = members.get(player_id, {})
        target = members.get(target_id)
        if not target:
            await self._send_tribe_error(player_id, "成员不存在")
            return
        if actor.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以预分配公共资源")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        allocation = target.setdefault("allocation", {"wood": 0, "stone": 0})
        assigned = {}
        for key in ("wood", "stone"):
            try:
                amount = int(resources.get(key, 0))
            except (TypeError, ValueError):
                amount = 0
            amount = max(0, min(amount, int(storage.get(key, 0) or 0), 999))
            if amount <= 0:
                continue
            storage[key] = int(storage.get(key, 0) or 0) - amount
            allocation[key] = int(allocation.get(key, 0) or 0) + amount
            assigned[key] = amount

        if not assigned:
            await self._send_tribe_error(player_id, "公共仓库资源不足，无法预分配")
            return

        await self._notify_tribe(
            tribe_id,
            f"{actor.get('name', '管理者')} 已向 {target.get('name', '成员')} 预分配资源：木材 {assigned.get('wood', 0)}，石块 {assigned.get('stone', 0)}。"
        )
        self._add_tribe_history(
            tribe,
            "allocation",
            "预分配公共资源",
            f"{actor.get('name', '管理者')} 向 {target.get('name', '成员')} 分配木材 {assigned.get('wood', 0)}、石块 {assigned.get('stone', 0)}。",
            player_id,
            {
                "kind": "allocation",
                "actorName": actor.get("name", "管理者"),
                "targetName": target.get("name", "成员"),
                "resources": {
                    "wood": assigned.get("wood", 0),
                    "stone": assigned.get("stone", 0)
                },
                "targetAllocation": dict(target.get("allocation", {"wood": 0, "stone": 0})),
                "storageAfter": {
                    "wood": int(storage.get("wood", 0) or 0),
                    "stone": int(storage.get("stone", 0) or 0)
                }
            }
        )
        await self.broadcast_tribe_state(tribe_id)

    async def create_tribe_trade(self, player_id: str, target_tribe_id: str, offer: dict, request: dict):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        target_tribe = self.tribes.get(target_tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not target_tribe or target_tribe_id == tribe_id:
            await self._send_tribe_error(player_id, "贸易目标无效")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以发布贸易请求")
            return

        active_count = len([
            trade for trade in self.tribe_trades.values()
            if trade.get("status") == "active" and trade.get("fromTribeId") == tribe_id
        ])
        if active_count >= TRIBE_TRADE_MAX_ACTIVE:
            await self._send_tribe_error(player_id, f"最多同时发布 {TRIBE_TRADE_MAX_ACTIVE} 条贸易请求")
            return

        offer_resource = (offer or {}).get("resource")
        request_resource = (request or {}).get("resource")
        offer_amount = max(0, min(999, int((offer or {}).get("amount", 0) or 0)))
        request_amount = max(0, min(999, int((request or {}).get("amount", 0) or 0)))
        if offer_resource not in {"wood", "stone", "food"} or request_resource not in {"wood", "stone", "food"}:
            await self._send_tribe_error(player_id, "只能交易木材、石块或食物")
            return
        if offer_amount <= 0 or request_amount <= 0:
            await self._send_tribe_error(player_id, "贸易数量必须大于 0")
            return
        market_pact = self._market_pact_between(tribe, target_tribe_id)
        market_pact_discount = 0
        if market_pact:
            market_pact_discount = min(
                request_amount - 1,
                int(market_pact.get("tradeDiscount", TRIBE_MARKET_PACT_TRADE_DISCOUNT) or 0)
            )
            request_amount = max(1, request_amount - market_pact_discount)
        trade_credit_effect = self._apply_trade_credit_on_create(tribe, target_tribe_id, request_amount)
        trade_credit = trade_credit_effect.get("credit")
        trade_credit_discount = int(trade_credit_effect.get("discount", 0) or 0)
        request_amount = int(trade_credit_effect.get("requestAmount", request_amount) or request_amount)
        if not self._deduct_trade_resource(tribe, offer_resource, offer_amount):
            await self._send_tribe_error(player_id, "部落资源不足，无法托管贸易物资")
            return

        trade_id = self._make_trade_id()
        trade = {
            "id": trade_id,
            "fromTribeId": tribe_id,
            "fromTribeName": tribe.get("name", "部落"),
            "toTribeId": target_tribe_id,
            "toTribeName": target_tribe.get("name", "部落"),
            "offer": {"resource": offer_resource, "amount": offer_amount},
            "request": {"resource": request_resource, "amount": request_amount},
            "status": "active",
            "createdBy": player_id,
            "createdAt": datetime.now().isoformat(),
            "marketPact": bool(market_pact),
            "marketPactTitle": market_pact.get("title") if market_pact else "",
            "marketPactActiveUntil": market_pact.get("activeUntil") if market_pact else None,
            "marketPactDiscount": market_pact_discount,
            "marketPactReputationBonus": int((market_pact or {}).get("tradeReputationBonus", 0) or 0),
            "tradeCredit": self._trade_credit_public_summary(trade_credit),
            "tradeCreditDiscount": trade_credit_discount
        }
        self.tribe_trades[trade_id] = trade
        pact_text = f" 互市约定让请求少要 {market_pact_discount} 份。" if market_pact_discount else ""
        credit_text = f" {trade_credit.get('label', '贸易信用')}让请求少要 {trade_credit_discount} 份。" if trade_credit_discount and trade_credit else ""
        detail = f"{member.get('name', '管理者')} 向 {target_tribe.get('name', '部落')} 发布贸易：出 {offer_amount} {offer_resource}，换 {request_amount} {request_resource}。{pact_text}{credit_text}"
        self._add_tribe_history(tribe, "trade", "发布部落贸易", detail, player_id, {"kind": "trade", **self._public_trade(trade)})
        await self._notify_tribe(target_tribe_id, f"{tribe.get('name', '部落')} 发来贸易请求：出 {offer_amount} {offer_resource}，换 {request_amount} {request_resource}。{pact_text}{credit_text}")
        await self.broadcast_tribe_state(tribe_id)
        await self.broadcast_tribe_state(target_tribe_id)

    async def resolve_tribe_trade(self, player_id: str, trade_id: str, action: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        trade = self.tribe_trades.get(trade_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if not trade or trade.get("status") != "active":
            await self._send_tribe_error(player_id, "贸易请求不存在或已结束")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以处理贸易请求")
            return

        from_tribe_id = trade.get("fromTribeId")
        to_tribe_id = trade.get("toTribeId")
        from_tribe = self.tribes.get(from_tribe_id)
        to_tribe = self.tribes.get(to_tribe_id)
        if not from_tribe or not to_tribe:
            trade["status"] = "expired"
            await self._send_tribe_error(player_id, "贸易相关部落不存在")
            return

        action = (action or "").strip()
        if action == "cancel":
            if tribe_id != from_tribe_id:
                await self._send_tribe_error(player_id, "只有发布方可以取消贸易")
                return
            self._add_trade_resource(from_tribe, trade["offer"]["resource"], trade["offer"]["amount"])
            trade["status"] = "cancelled"
            trade["resolvedAt"] = datetime.now().isoformat()
            credit_repair = self._open_trade_credit_repair_task(from_tribe, to_tribe, trade, "cancel", trade["resolvedAt"])
            detail = f"{member.get('name', '管理者')} 取消了对 {trade.get('toTribeName', '部落')} 的贸易请求，托管物资已返还。"
            if credit_repair:
                detail += f" 与 {to_tribe.get('name', '部落')} 的贸易信用需要保证人修复。"
            law_parts = self.apply_tribe_law_violation(from_tribe, player_id, "trade_cancel", "取消贸易")
            if law_parts:
                detail += f" 律令记录：{'、'.join(law_parts)}。"
            self._add_tribe_history(from_tribe, "trade", "取消部落贸易", detail, player_id, {"kind": "trade", **self._public_trade(trade)})
        elif action == "reject":
            if tribe_id != to_tribe_id:
                await self._send_tribe_error(player_id, "只有接收方可以拒绝贸易")
                return
            self._add_trade_resource(from_tribe, trade["offer"]["resource"], trade["offer"]["amount"])
            trade["status"] = "rejected"
            trade["resolvedAt"] = datetime.now().isoformat()
            credit_repair = self._open_trade_credit_repair_task(to_tribe, from_tribe, trade, "reject", trade["resolvedAt"])
            detail = f"{member.get('name', '管理者')} 拒绝了 {trade.get('fromTribeName', '部落')} 的贸易请求，托管物资已返还。"
            if credit_repair:
                detail += f" 与 {from_tribe.get('name', '部落')} 的贸易信用需要补交口信修复。"
            law_parts = self.apply_tribe_law_violation(to_tribe, player_id, "trade_reject", "拒绝贸易")
            if law_parts:
                detail += f" 律令记录：{'、'.join(law_parts)}。"
            self._add_tribe_history(to_tribe, "trade", "拒绝部落贸易", detail, player_id, {"kind": "trade", **self._public_trade(trade)})
            await self._notify_tribe(from_tribe_id, f"{to_tribe.get('name', '部落')} 拒绝了贸易请求，托管物资已返还。")
        elif action == "accept":
            if tribe_id != to_tribe_id:
                await self._send_tribe_error(player_id, "只有接收方可以接受贸易")
                return
            request_resource = trade["request"]["resource"]
            request_amount = int(trade["request"]["amount"] or 0)
            if not self._deduct_trade_resource(to_tribe, request_resource, request_amount):
                await self._send_tribe_error(player_id, "接收方资源不足，无法完成交换")
                return
            self._add_trade_resource(to_tribe, trade["offer"]["resource"], trade["offer"]["amount"])
            self._add_trade_resource(from_tribe, request_resource, request_amount)
            from_tribe["trade_reputation"] = max(0, int(from_tribe.get("trade_reputation", 0) or 0)) + 1
            to_tribe["trade_reputation"] = max(0, int(to_tribe.get("trade_reputation", 0) or 0)) + 1
            from_road_bonus = 1 if self._has_tribe_structure_type(from_tribe, "tribe_road") else 0
            to_road_bonus = 1 if self._has_tribe_structure_type(to_tribe, "tribe_road") else 0
            if from_road_bonus:
                from_tribe["trade_reputation"] += from_road_bonus
            if to_road_bonus:
                to_tribe["trade_reputation"] += to_road_bonus
            from_trade_bonus = int((self._active_celebration_buff(from_tribe) or {}).get("tradeRenownBonus", 0) or 0)
            to_trade_bonus = int((self._active_celebration_buff(to_tribe) or {}).get("tradeRenownBonus", 0) or 0)
            from_apprentice_trade_bonus = self._apprentice_trade_reputation_bonus(from_tribe)
            to_apprentice_trade_bonus = self._apprentice_trade_reputation_bonus(to_tribe)
            from_lost_tech_trade_bonus = self._lost_tech_trade_reputation_bonus(from_tribe)
            to_lost_tech_trade_bonus = self._lost_tech_trade_reputation_bonus(to_tribe)
            from_craft_legacy_trade_bonus = self._craft_legacy_trade_reputation_bonus(from_tribe)
            to_craft_legacy_trade_bonus = self._craft_legacy_trade_reputation_bonus(to_tribe)
            from_tune_trade_bonus = self._traveler_song_lineage_trade_reputation_bonus(from_tribe)
            to_tune_trade_bonus = self._traveler_song_lineage_trade_reputation_bonus(to_tribe)
            if from_apprentice_trade_bonus:
                from_tribe["trade_reputation"] += from_apprentice_trade_bonus
            if to_apprentice_trade_bonus:
                to_tribe["trade_reputation"] += to_apprentice_trade_bonus
            if from_lost_tech_trade_bonus:
                from_tribe["trade_reputation"] += from_lost_tech_trade_bonus
            if to_lost_tech_trade_bonus:
                to_tribe["trade_reputation"] += to_lost_tech_trade_bonus
            if from_craft_legacy_trade_bonus:
                from_tribe["trade_reputation"] += from_craft_legacy_trade_bonus
            if to_craft_legacy_trade_bonus:
                to_tribe["trade_reputation"] += to_craft_legacy_trade_bonus
            if from_tune_trade_bonus:
                from_tribe["trade_reputation"] += from_tune_trade_bonus
            if to_tune_trade_bonus:
                to_tribe["trade_reputation"] += to_tune_trade_bonus
            from_law_bonus = self.apply_tribe_law_event_bonus(from_tribe, "trade_accept", "部落贸易")
            to_law_bonus = self.apply_tribe_law_event_bonus(to_tribe, "trade_accept", "部落贸易")
            from_custom_bonus = self.apply_tribe_custom_event_bonus(from_tribe, "trade_accept", "部落贸易", player_id)
            to_custom_bonus = self.apply_tribe_custom_event_bonus(to_tribe, "trade_accept", "部落贸易", player_id)
            from_oath_bonus = self._oath_bonus(from_tribe, "tradeRenownBonus")
            to_oath_bonus = self._oath_bonus(to_tribe, "tradeRenownBonus")
            from_tribe["renown"] = max(0, int(from_tribe.get("renown", 0) or 0)) + TRIBE_TRADE_RENOWN_BONUS + from_trade_bonus
            to_tribe["renown"] = max(0, int(to_tribe.get("renown", 0) or 0)) + TRIBE_TRADE_RENOWN_BONUS + to_trade_bonus
            if from_oath_bonus:
                from_tribe["renown"] += from_oath_bonus
            if to_oath_bonus:
                to_tribe["renown"] += to_oath_bonus
            market_pact_bonus = int(trade.get("marketPactReputationBonus", 0) or 0)
            if market_pact_bonus:
                from_tribe["trade_reputation"] += market_pact_bonus
                to_tribe["trade_reputation"] += market_pact_bonus
                from_progress = from_tribe.setdefault("boundary_relations", {}).setdefault(to_tribe_id, {})
                to_progress = to_tribe.setdefault("boundary_relations", {}).setdefault(from_tribe_id, {})
                for progress in (from_progress, to_progress):
                    progress["score"] = max(-9, min(9, int(progress.get("score", 0) or 0) + 1))
                    progress["tradeTrust"] = max(0, min(10, int(progress.get("tradeTrust", 0) or 0) + 1))
                    progress["lastAction"] = "market_pact_trade"
                    progress["lastActionAt"] = datetime.now().isoformat()
            trade_credit_parts = self._apply_trade_credit_on_accept(from_tribe, to_tribe, trade)
            trade["status"] = "accepted"
            trade["resolvedAt"] = datetime.now().isoformat()
            trade_credit_result = self._record_trade_credit_success(from_tribe, to_tribe, trade, trade["resolvedAt"])
            from_ash_promise = self._apply_ash_ledger_promise_bonus(from_tribe, "部落贸易", to_tribe_id, trade["resolvedAt"])
            to_ash_promise = self._apply_ash_ledger_promise_bonus(to_tribe, "部落贸易", from_tribe_id, trade["resolvedAt"])
            trade["ashLedgerPromises"] = [
                item for item in (from_ash_promise, to_ash_promise)
                if item.get("parts")
            ]
            apprentice_detail = ""
            if from_apprentice_trade_bonus or to_apprentice_trade_bonus:
                apprentice_detail = f" 学徒账法让贸易信誉额外 +{from_apprentice_trade_bonus}/{to_apprentice_trade_bonus}。"
            lost_tech_detail = ""
            if from_lost_tech_trade_bonus or to_lost_tech_trade_bonus:
                lost_tech_detail = f" 复原技艺让贸易信誉额外 +{from_lost_tech_trade_bonus}/{to_lost_tech_trade_bonus}。"
            craft_legacy_detail = ""
            if from_craft_legacy_trade_bonus or to_craft_legacy_trade_bonus:
                craft_legacy_detail = f" 手艺传名让贸易信誉额外 +{from_craft_legacy_trade_bonus}/{to_craft_legacy_trade_bonus}。"
            pact_detail = f" 互市约定让双方贸易信誉额外 +{market_pact_bonus}。" if market_pact_bonus else ""
            law_detail = ""
            if from_law_bonus or to_law_bonus:
                law_detail = f" 律令加成：{'; '.join(from_law_bonus + to_law_bonus)}。"
            custom_detail = ""
            if from_custom_bonus or to_custom_bonus:
                custom_detail = f" 风俗加成：{'; '.join(from_custom_bonus + to_custom_bonus)}。"
            credit_detail = f" 贸易信用结算：{'、'.join(trade_credit_parts)}。" if trade_credit_parts else ""
            earned_credit = trade_credit_result.get("fromRecord")
            if earned_credit:
                credit_detail += f" 连续守约 {trade_credit_result.get('streak', 0)} 次，形成“{earned_credit.get('label', '贸易信用')}”。"
            ash_promise_parts = from_ash_promise.get("parts", []) + to_ash_promise.get("parts", [])
            ash_promise_detail = f" 灰烬账谱承诺：{'、'.join(ash_promise_parts)}。" if ash_promise_parts else ""
            detail = f"{member.get('name', '管理者')} 接受了 {trade.get('fromTribeName', '部落')} 的贸易：收到 {trade['offer']['amount']} {trade['offer']['resource']}，交付 {request_amount} {request_resource}。{pact_detail}"
            detail += apprentice_detail
            detail += lost_tech_detail
            detail += craft_legacy_detail
            detail += law_detail
            detail += custom_detail
            detail += credit_detail
            detail += ash_promise_detail
            self._add_tribe_history(to_tribe, "trade", "接受部落贸易", detail, player_id, {"kind": "trade", **self._public_trade(trade)})
            self._add_tribe_history(from_tribe, "trade", "完成部落贸易", f"{to_tribe.get('name', '部落')} 接受贸易，部落收到 {request_amount} {request_resource}。{pact_detail}{apprentice_detail}{lost_tech_detail}{craft_legacy_detail}{law_detail}{custom_detail}{credit_detail}{ash_promise_detail}", player_id, {"kind": "trade", **self._public_trade(trade)})
            await self._notify_tribe(from_tribe_id, f"{to_tribe.get('name', '部落')} 接受了贸易请求，交换已完成。")
            await self._publish_world_rumor(
                "trade",
                "贸易完成",
                f"{from_tribe.get('name', '部落')} 与 {to_tribe.get('name', '部落')} 完成资源交换，双方声望 +{TRIBE_TRADE_RENOWN_BONUS}。",
                {
                    "tradeId": trade.get("id"),
                    "fromTribeId": from_tribe_id,
                    "toTribeId": to_tribe_id,
                    "renownBonus": TRIBE_TRADE_RENOWN_BONUS,
                    "fromOathBonus": from_oath_bonus,
                    "toOathBonus": to_oath_bonus,
                    "fromRoadBonus": from_road_bonus,
                    "toRoadBonus": to_road_bonus,
                    "marketPactBonus": market_pact_bonus,
                    "tradeCreditParts": trade_credit_parts,
                    "tradeCreditStreak": trade_credit_result.get("streak", 0),
                    "fromApprenticeTradeBonus": from_apprentice_trade_bonus,
                    "toApprenticeTradeBonus": to_apprentice_trade_bonus,
                    "fromLostTechTradeBonus": from_lost_tech_trade_bonus,
                    "toLostTechTradeBonus": to_lost_tech_trade_bonus,
                    "fromCraftLegacyTradeBonus": from_craft_legacy_trade_bonus,
                    "toCraftLegacyTradeBonus": to_craft_legacy_trade_bonus,
                    "fromLawBonus": from_law_bonus,
                    "toLawBonus": to_law_bonus,
                    "ashLedgerPromises": trade.get("ashLedgerPromises", []),
                    "fromReputation": self._trade_reputation_state(from_tribe),
                    "toReputation": self._trade_reputation_state(to_tribe)
                }
            )
        else:
            await self._send_tribe_error(player_id, "未知贸易操作")
            return

        await self.broadcast_tribe_state(from_tribe_id)
        await self.broadcast_tribe_state(to_tribe_id)

    async def assign_beast_task(self, player_id: str, task_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        if int(tribe.get("tamed_beasts", 0) or 0) <= 0:
            await self._send_tribe_error(player_id, "部落还没有驯养幼兽")
            return
        task = TRIBE_BEAST_TASK_REWARDS.get(task_key)
        if not task:
            await self._send_tribe_error(player_id, "未知驯养任务")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        growth = self._beast_growth_state(tribe)
        reward_multiplier = float(growth.get("rewardMultiplier", 1) or 1)
        if self._oath_bonus(tribe, "beastRewardBonus"):
            reward_multiplier += 0.25
        reward_parts = []
        for resource_key, label in (("wood", "木材"), ("stone", "石块")):
            amount = math.floor(int(task.get(resource_key, 0) or 0) * reward_multiplier)
            if amount:
                storage[resource_key] = int(storage.get(resource_key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = math.floor(int(task.get("food", 0) or 0) * reward_multiplier)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        renown = math.floor(int(task.get("renown", 0) or 0) * reward_multiplier)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        discovery = math.floor(int(task.get("discoveryProgress", 0) or 0) * reward_multiplier)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        trade = math.floor(int(task.get("tradeReputation", 0) or 0) * reward_multiplier)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        specialty_key = tribe.get("beast_specialty")
        specialty = TRIBE_BEAST_SPECIALTIES.get(specialty_key)
        if specialty and specialty.get("taskKey") == task_key:
            for resource_key, label in (("woodBonus", "木材"), ("stoneBonus", "石块")):
                amount = int(specialty.get(resource_key, 0) or 0)
                if amount:
                    storage_key = "wood" if resource_key == "woodBonus" else "stone"
                    storage[storage_key] = int(storage.get(storage_key, 0) or 0) + amount
                    reward_parts.append(f"{specialty.get('label')}专长{label}+{amount}")
            food_bonus = int(specialty.get("foodBonus", 0) or 0)
            if food_bonus:
                tribe["food"] = int(tribe.get("food", 0) or 0) + food_bonus
                reward_parts.append(f"{specialty.get('label')}专长食物+{food_bonus}")
            renown_bonus = int(specialty.get("renownBonus", 0) or 0)
            if renown_bonus:
                tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown_bonus
                reward_parts.append(f"{specialty.get('label')}专长声望+{renown_bonus}")
        if specialty and specialty.get("taskKey") == task_key:
            discovery_bonus = int(specialty.get("discoveryBonus", 0) or 0)
            if discovery_bonus:
                tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery_bonus
                reward_parts.append(f"{specialty.get('label')}专长发现+{discovery_bonus}")
            trade_bonus = int(specialty.get("tradeBonus", 0) or 0)
            if trade_bonus:
                tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_bonus
                reward_parts.append(f"{specialty.get('label')}专长贸易信誉+{trade_bonus}")
        link_parts = self._apply_beast_ritual_link_rewards(tribe, task_key)
        reward_parts.extend(link_parts)
        tribe["beast_experience"] = int(tribe.get("beast_experience", 0) or 0) + 1
        new_growth = self._beast_growth_state(tribe)

        member = tribe.get("members", {}).get(player_id, {})
        record = {
            "id": f"beast_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "taskKey": task_key,
            "taskLabel": task.get("label", "驯养任务"),
            "summary": task.get("summary", ""),
            "memberName": member.get("name", "成员"),
            "rewardParts": reward_parts,
            "beastLevel": new_growth.get("level", 0),
            "beastTitle": new_growth.get("title", "尚未驯养"),
            "createdAt": datetime.now().isoformat()
        }
        tribe["active_beast_task"] = {
            "taskKey": task_key,
            "taskLabel": record["taskLabel"],
            "memberName": record["memberName"],
            "activeUntil": datetime.fromtimestamp(
                datetime.now().timestamp() + TRIBE_BEAST_TASK_FEEDBACK_SECONDS
            ).isoformat()
        }
        tribe.setdefault("beast_tasks", []).append(record)
        tribe["beast_tasks"] = tribe["beast_tasks"][-8:]
        detail = f"{record['memberName']} 派出驯养幼兽执行{record['taskLabel']}：{record['summary']} {'、'.join(reward_parts)}。幼兽熟练度提升为{record['beastTitle']}。"
        self._add_tribe_history(tribe, "food", "驯养幼兽任务", detail, player_id, {"kind": "beast_task", **record})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def complete_season_objective(self, player_id: str, objective_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        env = self._get_current_environment()
        objective = env.get("seasonObjective") if isinstance(env.get("seasonObjective"), dict) else None
        if not objective or objective.get("id") != objective_id:
            await self._send_tribe_error(player_id, "季节目标已经变化")
            return
        if not self._active_until_still_valid(objective):
            env["seasonObjective"] = None
            self._store_current_environment(env)
            await self._send_tribe_error(player_id, "季节目标已经结束")
            await self._broadcast_current_map()
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward = objective.get("reward") or {}
        reward_parts = []
        for resource_key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(reward.get(resource_key, 0) or 0)
            if amount:
                storage[resource_key] = int(storage.get(resource_key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = int(reward.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        renown = int(reward.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        discovery_buff_bonus = self._celebration_bonus(tribe, "discoveryBonus") + self._oath_bonus(tribe, "discoveryBonus")
        progress = int(reward.get("discoveryProgress", 0) or 0)
        if progress and discovery_buff_bonus:
            progress += discovery_buff_bonus
        if progress:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + progress
            reward_parts.append(f"发现进度+{progress}")

        member = tribe.get("members", {}).get(player_id, {})
        chain_regions = list(tribe.get("season_chain_regions", []) or [])
        region_type = objective.get("regionType")
        if region_type and region_type not in chain_regions:
            chain_regions.append(region_type)
        tribe["season_chain_regions"] = chain_regions[-SEASON_CHAIN_TARGET:]
        celebration_unlocked = len(set(tribe["season_chain_regions"])) >= SEASON_CHAIN_TARGET
        if celebration_unlocked:
            tribe["season_chain_regions"] = []
            tribe["pending_celebration"] = {
                "id": f"celebration_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                "title": "跨区域丰收庆典",
                "summary": "不同地形的季节目标连成庆典，等待部落选择庆典形式。",
                "createdAt": datetime.now().isoformat()
            }
            reward_parts.append("解锁跨区域庆典")
        detail = f"{member.get('name', '成员')} 完成了{objective.get('regionLabel', '未知区域')}的{objective.get('title', '季节目标')}：{'、'.join(reward_parts) or '无直接奖励'}。"
        if celebration_unlocked:
            detail += " 不同地形的季节目标连成庆典，部落举行了跨区域丰收庆祝。"
            await self._publish_world_rumor(
                "season",
                "庆典筹备",
                f"{tribe.get('name', '部落')} 连续完成多地季节目标，正在筹备跨区域庆典。",
                {"tribeId": tribe_id, "pending": True}
        )
        self._add_tribe_history(tribe, "world_event", "完成季节目标", detail, player_id, {"kind": "season_objective", **objective, "rewardParts": reward_parts, "memberName": member.get("name", "成员"), "celebrationUnlocked": celebration_unlocked})
        env["seasonObjective"] = None
        self._store_current_environment(env)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def choose_season_celebration(self, player_id: str, choice_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以决定庆典形式")
            return
        pending = tribe.get("pending_celebration")
        choice = SEASON_CELEBRATION_CHOICES.get(choice_key)
        if not pending:
            await self._send_tribe_error(player_id, "当前没有待举行的庆典")
            return
        if not choice:
            await self._send_tribe_error(player_id, "未知庆典形式")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        reward_parts = []
        for resource_key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(choice.get(resource_key, 0) or 0)
            if amount:
                storage[resource_key] = int(storage.get(resource_key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = int(choice.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        renown = int(choice.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        progress = int(choice.get("discoveryProgress", 0) or 0)
        if progress:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + progress
            reward_parts.append(f"发现进度+{progress}")
        buff_plan = choice.get("buff") or {}
        if buff_plan:
            buff = dict(buff_plan)
            buff["choiceKey"] = choice_key
            buff["activeUntil"] = datetime.fromtimestamp(datetime.now().timestamp() + SEASON_CELEBRATION_BUFF_MINUTES * 60).isoformat()
            tribe["celebration_buff"] = buff
            reward_parts.append(f"{buff.get('title', '庆典余韵')}持续{SEASON_CELEBRATION_BUFF_MINUTES}分钟")
        trade_rep = int(choice.get("tradeReputation", 0) or 0)
        if trade_rep:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_rep
            reward_parts.append(f"贸易信誉+{trade_rep}")

        tribe["pending_celebration"] = None
        record = {
            "kind": "season_celebration",
            "choiceKey": choice_key,
            "choiceLabel": choice.get("label", "庆典"),
            "summary": choice.get("summary", ""),
            "memberName": member.get("name", "管理者"),
            "rewardParts": reward_parts,
            "createdAt": datetime.now().isoformat()
        }
        detail = f"{record['memberName']} 将跨区域庆典办成{record['choiceLabel']}：{record['summary']} {'、'.join(reward_parts)}。"
        self._add_tribe_history(tribe, "ritual", "举行跨区域庆典", detail, player_id, record)
        await self._publish_world_rumor(
            "season",
            f"{record['choiceLabel']}庆典",
            f"{tribe.get('name', '部落')} 举行了{record['choiceLabel']}：{record['summary']}",
            {"tribeId": tribe_id, "choice": choice_key, "rewardParts": reward_parts}
        )
        await self.broadcast_tribe_state(tribe_id)

    async def choose_beast_specialty(self, player_id: str, specialty_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return
        growth = self._beast_growth_state(tribe)
        if int(growth.get("level", 0) or 0) < TRIBE_BEAST_SPECIALTY_LEVEL:
            await self._send_tribe_error(player_id, f"幼兽需要达到 {TRIBE_BEAST_SPECIALTY_LEVEL} 级才能选择专长")
            return
        if tribe.get("beast_specialty"):
            await self._send_tribe_error(player_id, "幼兽专长已经确定")
            return
        specialty = TRIBE_BEAST_SPECIALTIES.get(specialty_key)
        if not specialty:
            await self._send_tribe_error(player_id, "未知幼兽专长")
            return

        member = tribe.get("members", {}).get(player_id, {})
        tribe["beast_specialty"] = specialty_key
        record = {
            "kind": "beast_specialty",
            "specialtyKey": specialty_key,
            "specialtyLabel": specialty.get("label", "专长"),
            "summary": specialty.get("summary", ""),
            "memberName": member.get("name", "成员"),
            "createdAt": datetime.now().isoformat()
        }
        detail = f"{record['memberName']} 为驯养幼兽选择了{record['specialtyLabel']}专长：{record['summary']}"
        self._add_tribe_history(tribe, "food", "幼兽专长", detail, player_id, record)
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def unlock_tribe_rune(self, player_id: str, rune_key: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以刻写图腾铭文")
            return

        rune = next((item for item in TRIBE_RUNE_LIBRARY + RARE_TRIBE_RUNE_LIBRARY if item.get("key") == rune_key), None)
        if not rune:
            await self._send_tribe_error(player_id, "未知铭文")
            return
        if rune_key in self._unlocked_rune_keys(tribe):
            await self._send_tribe_error(player_id, "该铭文已经刻写")
            return
        if not self._rune_requirements_met(tribe, rune):
            await self._send_tribe_error(player_id, "铭文条件尚未达成")
            return

        record = {
            "key": rune["key"],
            "title": rune["title"],
            "summary": rune["summary"],
            "effectSummary": rune.get("effectSummary", ""),
            "rare": bool(rune.get("rare")),
            "unlockedAt": datetime.now().isoformat(),
            "unlockedBy": player_id,
            "unlockedByName": member.get("name", self._get_player_name(player_id))
        }
        tribe.setdefault("runes", []).append(record)
        self._add_tribe_history(
            tribe,
            "rune",
            f"刻下{rune['title']}",
            rune.get("effectSummary") or rune.get("summary", ""),
            player_id
        )
        notice = f"{member.get('name', '管理者')} 在图腾上刻下了{rune['title']}。"
        if rune.get("rare"):
            notice = f"稀有铭文觉醒：{notice} 图腾回响在整个营地扩散。"
        for member_id in list(tribe.get("members", {}).keys()):
            await self.send_personal_message(member_id, {
                "type": "tribe_rune_unlocked",
                "message": notice,
                "rune": record
            })
        await self.broadcast_tribe_state(tribe_id)

    async def start_tribe_ritual(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以点燃部落仪式")
            return

        if not self._is_tribe_building_built(tribe, "campfire"):
            await self._send_tribe_error(player_id, "需要先建成营火才能举行仪式")
            return

        active = self._active_tribe_ritual(tribe)
        if active:
            await self._send_tribe_error(player_id, "部落仪式仍在持续")
            return

        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        if int(storage.get("wood", 0) or 0) < TRIBE_RITUAL_WOOD_COST or int(storage.get("stone", 0) or 0) < TRIBE_RITUAL_STONE_COST:
            await self._send_tribe_error(player_id, f"仪式需要木材 {TRIBE_RITUAL_WOOD_COST}、石块 {TRIBE_RITUAL_STONE_COST}")
            return

        storage["wood"] = int(storage.get("wood", 0) or 0) - TRIBE_RITUAL_WOOD_COST
        storage["stone"] = int(storage.get("stone", 0) or 0) - TRIBE_RITUAL_STONE_COST
        ritual_config = self._ritual_config(tribe)
        duration_minutes = int(ritual_config.get("durationMinutes", TRIBE_RITUAL_DURATION_MINUTES) or TRIBE_RITUAL_DURATION_MINUTES)
        gather_bonus = int(ritual_config.get("gatherBonus", TRIBE_RITUAL_GATHER_BONUS) or TRIBE_RITUAL_GATHER_BONUS)
        active_until = datetime.fromtimestamp(datetime.now().timestamp() + duration_minutes * 60)
        tribe["ritual"] = {
            "type": "harvest",
            "title": "丰收篝火",
            "gatherBonus": gather_bonus,
            "activeUntil": active_until.isoformat(),
            "startedAt": datetime.now().isoformat(),
            "startedBy": player_id
        }
        self._add_tribe_history(
            tribe,
            "ritual",
            "点燃丰收篝火",
            f"持续 {duration_minutes} 分钟，采集额外 +{gather_bonus}。",
            player_id
        )
        await self._notify_tribe(tribe_id, f"{member.get('name', '管理者')} 点燃了丰收篝火：{duration_minutes} 分钟内采集额外 +{gather_bonus}。")
        await self.broadcast_tribe_state(tribe_id)

    async def start_tribe_feast(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以举办部落宴会")
            return

        if not self._is_tribe_building_built(tribe, "campfire"):
            await self._send_tribe_error(player_id, "需要先建成营火才能举办宴会")
            return

        active = self._active_tribe_ritual(tribe)
        if active:
            await self._send_tribe_error(player_id, "部落仪式仍在持续")
            return

        food = int(tribe.get("food", 0) or 0)
        if food < TRIBE_FEAST_FOOD_COST:
            await self._send_tribe_error(player_id, f"宴会需要食物 {TRIBE_FEAST_FOOD_COST}")
            return

        tribe["food"] = food - TRIBE_FEAST_FOOD_COST
        tribe["renown"] = int(tribe.get("renown", 0) or 0) + TRIBE_FEAST_RENOWN_BONUS
        active_until = datetime.fromtimestamp(datetime.now().timestamp() + TRIBE_FEAST_DURATION_MINUTES * 60)
        tribe["ritual"] = {
            "type": "feast",
            "title": "部落宴会",
            "gatherBonus": TRIBE_FEAST_GATHER_BONUS,
            "renownBonus": TRIBE_FEAST_RENOWN_BONUS,
            "activeUntil": active_until.isoformat(),
            "startedAt": datetime.now().isoformat(),
            "startedBy": player_id
        }
        self._add_tribe_history(
            tribe,
            "ritual",
            "举办部落宴会",
            f"消耗食物 {TRIBE_FEAST_FOOD_COST}，持续 {TRIBE_FEAST_DURATION_MINUTES} 分钟，采集额外 +{TRIBE_FEAST_GATHER_BONUS}，声望 +{TRIBE_FEAST_RENOWN_BONUS}。",
            player_id
        )
        await self._notify_tribe(tribe_id, f"{member.get('name', '管理者')} 举办了部落宴会：食物转化为士气，采集额外 +{TRIBE_FEAST_GATHER_BONUS}，声望 +{TRIBE_FEAST_RENOWN_BONUS}。")
        await self._publish_world_rumor(
            "feast",
            "营火宴会",
            f"{tribe.get('name', '部落')} 举办了部落宴会，附近都听见了歌声与鼓点。",
            {
                "tribeId": tribe_id,
                "tribeName": tribe.get("name", "部落")
            }
        )
        await self.broadcast_tribe_state(tribe_id)

    async def complete_cave_expedition(self, player_id: str, cave_label: str, depth: int, finds: int, food_supported: bool = True, route_key: str = "deep"):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        safe_label = (cave_label or "未知洞穴").strip()[:30]
        safe_depth = max(0, min(int(depth or 0), 999))
        safe_finds = max(0, min(int(finds or 0), 999))
        safe_route_key = route_key if route_key in TRIBE_CAVE_ROUTE_PLANS else "deep"
        route_plan = TRIBE_CAVE_ROUTE_PLANS[safe_route_key]
        route_food_cost = max(0, int(route_plan.get("foodCost", TRIBE_CAVE_FOOD_COST) or TRIBE_CAVE_FOOD_COST))
        cave_return_bonus = self._consume_cave_return_route_bonus(tribe, safe_route_key)
        if cave_return_bonus:
            route_food_cost = max(0, route_food_cost - int(cave_return_bonus.get("foodReduction", 0) or 0))
        rune_effects = self._tribe_rune_effects(tribe)
        cave_finds_bonus = max(0, int(rune_effects.get("caveFindsBonus", 0) or 0))
        food = max(0, int(tribe.get("food", 0) or 0))
        food_supported = bool(food_supported) and food >= route_food_cost
        if food_supported:
            tribe["food"] = food - route_food_cost
            route_multiplier = max(0, float(route_plan.get("findsMultiplier", 1) or 1))
            route_bonus = max(0, int(route_plan.get("findsBonus", 0) or 0))
            safe_finds = math.floor(safe_finds * route_multiplier) + route_bonus
            food_detail = f" 选择{route_plan.get('label', '深入路线')}，消耗食物 {route_food_cost}，远征补给充足。"
        else:
            safe_finds = math.floor(safe_finds * TRIBE_CAVE_LOW_FOOD_FINDS_MULTIPLIER)
            food_detail = f" 选择{route_plan.get('label', '深入路线')}，食物不足，远征收益下降。"
        if cave_finds_bonus > 0:
            safe_finds += cave_finds_bonus
            food_detail += f" 图腾稀有铭文共鸣，额外收获 +{cave_finds_bonus}。"
        cave_return_finds_bonus = max(0, int(cave_return_bonus.get("findsBonus", 0) or 0)) if cave_return_bonus else 0
        if cave_return_bonus:
            if cave_return_finds_bonus:
                safe_finds += cave_return_finds_bonus
            return_parts = []
            if cave_return_finds_bonus:
                return_parts.append(f"收获+{cave_return_finds_bonus}")
            if cave_return_bonus.get("foodReduction"):
                return_parts.append(f"食物消耗-{int(cave_return_bonus.get('foodReduction', 0) or 0)}")
            food_detail += f" 洞穴归路经验“{cave_return_bonus.get('label', '归路经验')}”生效：{'、'.join(return_parts) or '路线更稳'}。"
        lost_tech_cave_bonus = self._lost_tech_cave_finds_bonus(tribe)
        if lost_tech_cave_bonus > 0:
            safe_finds += lost_tech_cave_bonus
            food_detail += f" 复原洞灯护罩让队伍多带回 +{lost_tech_cave_bonus}。"
        craft_legacy_cave_bonus = self._craft_legacy_cave_finds_bonus(tribe)
        if craft_legacy_cave_bonus > 0:
            safe_finds += craft_legacy_cave_bonus
            food_detail += f" 洞路手艺传名让队伍多带回 +{craft_legacy_cave_bonus}。"
        oath_cave_bonus = self._oath_bonus(tribe, "caveFindsBonus")
        if oath_cave_bonus:
            safe_finds += oath_cave_bonus
            food_detail += f" 远行誓约让队伍多带回 +{oath_cave_bonus}。"
        weather_temper_cave_bonus = self._weather_temper_myth_bonus(tribe, "caveFindsBonus") if hasattr(self, "_weather_temper_myth_bonus") else 0
        if weather_temper_cave_bonus:
            safe_finds += weather_temper_cave_bonus
            food_detail += f" 天气脾气神话让洞口多回声 +{weather_temper_cave_bonus}。"
        discoveries = tribe.setdefault("discoveries", [])
        discovery_key = "deep_cave_echo"
        discovery_depth = max(1, int(route_plan.get("discoveryDepth", 4) or 4))
        discovery_unlocked = safe_depth >= discovery_depth and discovery_key not in discoveries
        if discovery_unlocked:
            discoveries.append(discovery_key)

        detail = f"{member.get('name', '成员')} 完成了 {safe_label} 远征：深度 {safe_depth}，收获 {safe_finds}。{food_detail}"
        if discovery_unlocked:
            detail += " 远征队发现了幽洞回声，可尝试刻写稀有铭文。"
        race_opened = await self._maybe_open_rare_cave_race(tribe, player_id, safe_label, safe_route_key, safe_depth, safe_finds)
        if race_opened:
            detail += f" 洞内风声改道，{race_opened.get('label', '短时稀有洞穴')}已经开启，多部落可抢首探。"
        self._record_map_memory(
            tribe,
            "cave_first",
            f"{safe_label}远征记号",
            f"{member.get('name', '成员')}带队深入{safe_label}，在洞口附近留下可供后来者辨认的路线记号。",
            float(self.players.get(player_id, {}).get("x", 0) or 0),
            float(self.players.get(player_id, {}).get("z", 0) or 0),
            f"cave:{safe_label}:{safe_route_key}",
            member.get("name", "成员")
        )
        self._add_tribe_history(
            tribe,
            "cave",
            f"完成{safe_label}远征",
            detail,
            player_id,
            {
                "kind": "cave",
                "memberName": member.get("name", "成员"),
                "caveLabel": safe_label,
                "depth": safe_depth,
                "finds": safe_finds,
                "routeKey": safe_route_key,
                "routeLabel": route_plan.get("label", "深入路线"),
                "foodSupported": food_supported,
                "foodCost": route_food_cost if food_supported else 0,
                "lowFoodMultiplier": TRIBE_CAVE_LOW_FOOD_FINDS_MULTIPLIER if not food_supported else 1,
                "routeFindsMultiplier": route_plan.get("findsMultiplier", 1) if food_supported else 1,
                "routeFindsBonus": route_plan.get("findsBonus", 0) if food_supported else 0,
                "runeFindsBonus": cave_finds_bonus,
                "caveReturnBonusId": cave_return_bonus.get("id") if cave_return_bonus else None,
                "caveReturnFindsBonus": cave_return_finds_bonus,
                "caveReturnFoodReduction": int(cave_return_bonus.get("foodReduction", 0) or 0) if cave_return_bonus else 0,
                "lostTechFindsBonus": lost_tech_cave_bonus,
                "craftLegacyFindsBonus": craft_legacy_cave_bonus,
                "oathFindsBonus": oath_cave_bonus,
                "weatherTemperFindsBonus": weather_temper_cave_bonus,
                "discoveryUnlocked": discovery_unlocked,
                "discoveryKey": discovery_key if discovery_unlocked else None,
                "caveRaceOpened": bool(race_opened),
                "caveRaceId": race_opened.get("id") if race_opened else None
            }
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)

    async def resolve_world_event(self, player_id: str, event_id: str, event_action: str = ""):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        env = self._get_current_environment()
        events = [event for event in (env.get("worldEvents", []) or []) if isinstance(event, dict)]
        now = datetime.now()
        active_events = [event for event in events if self._active_until_still_valid(event, now)]
        pruned_expired_events = len(active_events) != len(events)
        if pruned_expired_events:
            env["worldEvents"] = active_events
            self._store_current_environment(env)
        event = next((item for item in active_events if item.get("id") == event_id), None)
        if not event:
            await self._send_tribe_error(player_id, "世界事件已经结束")
            if pruned_expired_events:
                await self._broadcast_current_map()
            return

        member = tribe.get("members", {}).get(player_id, {})
        title = event.get("title", "世界事件")
        region_label = event.get("regionLabel", "未知区域")
        detail = f"{member.get('name', '成员')} 在{region_label}处理了{title}。"
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        event_key = event.get("key")
        reward = dict(WORLD_EVENT_REWARDS.get(event_key, {}))
        event_action_key = None
        event_action_label = None
        event_action_key, action_plan = self._world_event_action_plan(tribe, event, event_action)
        if action_plan:
            event_action_label = action_plan.get("label", "追猎")
            if "foodMultiplier" in action_plan:
                reward["food"] = math.floor(int(reward.get("food", 0) or 0) * float(action_plan.get("foodMultiplier", 1) or 1))
            reward["renown"] = int(reward.get("renown", 0) or 0) + int(action_plan.get("renownBonus", 0) or 0)
            for key, amount in (action_plan.get("reward") or {}).items():
                reward[key] = int(reward.get(key, 0) or 0) + int(amount or 0)
            if int(action_plan.get("tamedBeasts", 0) or 0) > 0:
                tribe["tamed_beasts"] = int(tribe.get("tamed_beasts", 0) or 0) + int(action_plan.get("tamedBeasts", 0) or 0)
        reward_parts = []
        region_event_bonus_labels = self._apply_world_event_region_bonuses(tribe, event_key, reward, reward_parts)
        law_event_bonus_parts = self.apply_tribe_law_event_bonus(tribe, event_key or "world_event", title)
        if law_event_bonus_parts:
            reward_parts.extend(law_event_bonus_parts)
        custom_event_bonus_parts = self.apply_tribe_custom_event_bonus(tribe, event_key or "world_event", title, player_id)
        if custom_event_bonus_parts:
            reward_parts.extend(custom_event_bonus_parts)
        for resource_key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(reward.get(resource_key, 0) or 0)
            if amount == 0:
                continue
            storage[resource_key] = max(0, int(storage.get(resource_key, 0) or 0) + amount)
            reward_parts.append(f"{label}{'+' if amount > 0 else ''}{amount}")
        food_reward = int(reward.get("food", 0) or 0)
        if food_reward > 0:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food_reward
            reward_parts.append(f"食物+{food_reward}")
        discovery_buff_bonus = self._celebration_bonus(tribe, "discoveryBonus") + self._oath_bonus(tribe, "discoveryBonus")
        discovery_progress = int(reward.get("discoveryProgress", 0) or 0)
        if discovery_progress > 0 and discovery_buff_bonus > 0:
            discovery_progress += discovery_buff_bonus
            reward["discoveryProgress"] = discovery_progress
        if discovery_progress > 0:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery_progress
            reward_parts.append(f"发现进度+{discovery_progress}")
        renown_reward = int(reward.get("renown", 0) or 0)
        if renown_reward > 0:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown_reward
            reward_parts.append(f"声望+{renown_reward}")
        trade_reward = int(reward.get("tradeReputation", 0) or 0)
        if trade_reward > 0:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade_reward
            reward_parts.append(f"贸易信誉+{trade_reward}")
        discovery_key = None
        if event_key == "ruin_clue":
            discovery_key = "deep_cave_echo"
            chain_count = int(tribe.get("ruin_clue_chain", 0) or 0) + 1 + int((action_plan or {}).get("ruinClueChainBonus", 0) or 0)
            tribe["ruin_clue_chain"] = chain_count
            discoveries = tribe.setdefault("discoveries", [])
            if discovery_key not in discoveries:
                discoveries.append(discovery_key)
                detail += " 遗迹线索指向幽洞回声，可尝试刻写稀有铭文。"
            else:
                detail += " 遗迹线索被再次记录，补充了部落发现进度。"
            remaining = max(0, WORLD_EVENT_RUIN_CHAIN_THRESHOLD - chain_count)
            if remaining > 0:
                detail += f" 还需连续记录 {remaining} 条遗迹线索，可能拼出稀有遗迹。"
        elif event_key == "herd":
            if event_action_key == "drive":
                detail += " 成员驱赶兽群远离营地，部落领地声明更有威慑。"
            elif event_action_key == "tame":
                detail += " 成员尝试驯养幼兽，部落留下了最早的驯养记录。"
            else:
                detail += " 成员追踪兽群后，部落带回了可储备的食物。"
        elif event_key == "storm":
            detail += " 成员加固了营火遮蔽，暴雨冲刷出可用石块。"
        elif event_key == "rare_ruin":
            tribe["ruin_clue_chain"] = 0
            discovery_key = "rare_ruin_memory"
            discoveries = tribe.setdefault("discoveries", [])
            if discovery_key not in discoveries:
                discoveries.append(discovery_key)
            detail += " 稀有遗迹被完整记录，部落获得了古老记忆，可继续发展更高阶铭文。"
        if action_plan and action_plan.get("detail"):
            detail += f" {action_plan.get('detail')}"
        if reward_parts:
            detail += f" 奖励：{'、'.join(reward_parts)}。"
        remnant = self._build_world_event_remnant(tribe, event, event_action_key, action_plan, member)
        if remnant:
            detail += f" {remnant.get('label', '事件余迹')}留在附近，成员可再次整理。"
        myth_claim = self._open_myth_claim(
            tribe,
            "world_event",
            event_action_label or title,
            f"{region_label}的{title}已经被处理，族人可以争论它究竟预示着火种、旧路、互市还是守边。",
            float(event.get("x", 0) or 0),
            float(event.get("z", 0) or 0),
            f"{event.get('id')}:{event_action_key or 'default'}",
            member.get("name", "成员")
        )
        if myth_claim:
            detail += " 这件事开始产生神话解释权。"
        public_secret = None
        if hasattr(self, "_maybe_create_public_secret"):
            public_secret = self._maybe_create_public_secret(
                tribe,
                event_key or "",
                event_action_label or title,
                f"{region_label}的{title}留下了一段还没有公开解释的消息。",
                float(event.get("x", 0) or 0),
                float(event.get("z", 0) or 0),
                event.get("id", ""),
                member.get("name", "成员")
            )
        if public_secret:
            detail += f" {public_secret.get('label', '公共秘密')}暂时压在部落面板中，成员可以决定公开、暂存或交给他人保管。"

        env["worldEvents"] = [item for item in active_events if item.get("id") != event_id]
        rare_spawned = False
        if event_key == "ruin_clue" and int(tribe.get("ruin_clue_chain", 0) or 0) >= WORLD_EVENT_RUIN_CHAIN_THRESHOLD:
            tribe["ruin_clue_chain"] = 0
            rare_event = self._build_rare_ruin_event()
            env["worldEvents"].append(rare_event)
            rare_spawned = True
            detail += f" 连续线索拼合完成，{rare_event['regionLabel']}出现了{rare_event['title']}！"
        self._store_current_environment(env)
        self._add_tribe_history(
            tribe,
            "world_event",
            title,
            detail,
            player_id,
            {
                "kind": "world_event",
                "eventId": event.get("id"),
                "eventKey": event_key,
                "title": title,
                "regionLabel": region_label,
                "memberName": member.get("name", "成员"),
                "reward": reward,
                "rewardParts": reward_parts,
                "regionEventBonusLabels": region_event_bonus_labels,
                "lawEventBonusParts": law_event_bonus_parts,
                "eventActionKey": event_action_key,
                "eventActionLabel": event_action_label,
                "discoveryKey": discovery_key,
                "celebrationDiscoveryBonus": discovery_buff_bonus if discovery_progress > 0 else 0,
                "rareSpawned": rare_spawned,
                "remnant": remnant,
                "publicSecret": public_secret
            }
        )
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()

    async def punish_tribe_member(self, player_id: str, target_id: str, reason: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        members = tribe.get("members", {})
        actor = members.get(player_id, {})
        target = members.get(target_id)
        if not target:
            await self._send_tribe_error(player_id, "成员不存在")
            return
        if not self._can_govern_member(actor, target):
            await self._send_tribe_error(player_id, "你不能惩罚该成员")
            return

        cooldowns = tribe.setdefault("punish_cooldowns", {})
        cooldown_key = f"{player_id}:{target_id}"
        hours_since = self._hours_since_iso(cooldowns.get(cooldown_key))
        if hours_since is not None and hours_since < TRIBE_PUNISH_COOLDOWN_HOURS:
            remaining = max(1, math.ceil(TRIBE_PUNISH_COOLDOWN_HOURS - hours_since))
            await self._send_tribe_error(player_id, f"惩罚冷却中，还需约 {remaining} 小时")
            return

        target["contribution"] = max(0, int(target.get("contribution", 0) or 0) - TRIBE_PUNISH_CONTRIBUTION_PENALTY)
        target["punish_count"] = int(target.get("punish_count", 0) or 0) + 1
        cooldowns[cooldown_key] = datetime.now().isoformat()
        record = {
            "targetId": target_id,
            "targetName": target.get("name", "成员"),
            "actorId": player_id,
            "actorName": actor.get("name", "管理者"),
            "reason": (reason or "行为不当").strip()[:80],
            "penalty": TRIBE_PUNISH_CONTRIBUTION_PENALTY,
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("punishments", []).append(record)
        tribe["punishments"] = tribe["punishments"][-20:]
        await self._notify_tribe(
            tribe_id,
            f"{record['actorName']} 已惩罚 {record['targetName']}：{record['reason']}，扣除 {record['penalty']} 贡献。"
        )
        self._add_tribe_history(
            tribe,
            "punishment",
            "执行部落惩罚",
            f"{record['actorName']} 惩罚 {record['targetName']}：{record['reason']}，扣除 {record['penalty']} 贡献。",
            player_id,
            {"kind": "punishment", **record}
        )
        await self.broadcast_tribe_state(tribe_id)

    async def start_tribe_vote(self, player_id: str, role: str, candidate_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        starter = tribe["members"].get(player_id, {})
        if starter.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以发起选举")
            return

        if role not in ("leader", "elder") or candidate_id not in tribe["members"]:
            await self._send_tribe_error(player_id, "候选人无效")
            return

        members = tribe.get("members", {})
        min_members = self._vote_min_members(role)
        if len(members) < min_members:
            role_label = "首领" if role == "leader" else "长老"
            await self._send_tribe_error(player_id, f"{role_label}选举至少需要 {min_members} 名成员")
            return

        candidate = members[candidate_id]
        min_contribution = self._vote_min_contribution(role)
        if int(candidate.get("contribution", 0) or 0) < min_contribution:
            role_label = "首领" if role == "leader" else "长老"
            await self._send_tribe_error(player_id, f"候选人贡献不足，竞选{role_label}至少需要 {min_contribution} 贡献")
            return

        active_duplicate = any(
            vote.get("tribe_id") == tribe_id
            and vote.get("status") == "active"
            and (vote.get("role") == role or vote.get("candidateId") == candidate_id)
            for vote in self.tribe_votes.values()
        )
        if active_duplicate:
            await self._send_tribe_error(player_id, "已有同职位或同候选人的进行中投票")
            return

        cooldowns = tribe.setdefault("vote_cooldowns", {})
        cooldown_hours = self._vote_cooldown_hours(role)
        hours_since = self._hours_since_iso(cooldowns.get(role))
        if hours_since is not None and hours_since < cooldown_hours:
            remaining = max(1, math.ceil(cooldown_hours - hours_since))
            role_label = "首领" if role == "leader" else "长老"
            await self._send_tribe_error(player_id, f"{role_label}投票冷却中，还需约 {remaining} 小时")
            return

        vote_id = self._make_vote_id()
        cooldowns[role] = datetime.now().isoformat()
        vote_record = {
            "id": vote_id,
            "tribe_id": tribe_id,
            "role": role,
            "candidateId": candidate_id,
            "candidateName": candidate.get("name", "玩家"),
            "starterId": player_id,
            "starterName": starter.get("name", "管理者"),
            "yes": [],
            "no": [],
            "status": "active",
            "createdAt": datetime.now().isoformat()
        }
        self.tribe_votes[vote_id] = vote_record
        role_label = "首领" if role == "leader" else "长老"
        self._add_tribe_history(
            tribe,
            "vote",
            f"发起{role_label}选举",
            f"{starter.get('name', '管理者')} 提名 {candidate.get('name', '玩家')} 竞选{role_label}。",
            player_id,
            {
                "kind": "vote",
                "voteId": vote_id,
                "role": role,
                "roleLabel": role_label,
                "candidateId": candidate_id,
                "candidateName": candidate.get("name", "玩家"),
                "starterName": starter.get("name", "管理者"),
                "status": "active",
                "yesCount": 0,
                "noCount": 0,
                "memberCount": len(members),
                "createdAt": vote_record["createdAt"]
            }
        )
        await self.broadcast_tribe_state(tribe_id)

    async def cast_tribe_vote(self, player_id: str, vote_id: str, approve: bool):
        vote = self.tribe_votes.get(vote_id)
        if not vote or vote.get("status") != "active":
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "投票不存在或已结束"
            })
            return

        tribe_id = vote.get("tribe_id")
        tribe = self.tribes.get(tribe_id)
        if not tribe or player_id not in tribe.get("members", {}):
            await self.send_personal_message(player_id, {
                "type": "tribe_error",
                "message": "你不属于该部落"
            })
            return

        vote["yes"] = [pid for pid in vote.get("yes", []) if pid != player_id]
        vote["no"] = [pid for pid in vote.get("no", []) if pid != player_id]
        vote["yes" if approve else "no"].append(player_id)

        member_count = len(tribe.get("members", {}))
        if len(vote["yes"]) > member_count / 2:
            candidate_id = vote.get("candidateId")
            candidate = tribe["members"].get(candidate_id)
            if candidate:
                if vote.get("role") == "leader":
                    old_leader = tribe["members"].get(tribe.get("leader_id"))
                    if old_leader:
                        old_leader["role"] = "member"
                    tribe["leader_id"] = candidate_id
                    candidate["role"] = "leader"
                elif vote.get("role") == "elder":
                    candidate["role"] = "elder"
                    if candidate_id not in tribe["elder_ids"]:
                        tribe["elder_ids"].append(candidate_id)
            vote["status"] = "passed"
            role_label = "首领" if vote.get("role") == "leader" else "长老"
            self._add_tribe_history(
                tribe,
                "vote",
                f"{role_label}选举通过",
                f"{vote.get('candidateName', '候选人')} 成为{role_label}。",
                player_id,
                {
                    "kind": "vote",
                    "voteId": vote_id,
                    "role": vote.get("role"),
                    "roleLabel": role_label,
                    "candidateId": candidate_id,
                    "candidateName": vote.get("candidateName", "候选人"),
                    "starterName": vote.get("starterName", "管理者"),
                    "status": "passed",
                    "yesCount": len(vote.get("yes", [])),
                    "noCount": len(vote.get("no", [])),
                    "memberCount": member_count,
                    "createdAt": vote.get("createdAt")
                }
            )
        elif len(vote["no"]) >= member_count / 2:
            vote["status"] = "rejected"
            role_label = "首领" if vote.get("role") == "leader" else "长老"
            self._add_tribe_history(
                tribe,
                "vote",
                f"{role_label}选举未通过",
                f"{vote.get('candidateName', '候选人')} 的竞选被否决。",
                player_id,
                {
                    "kind": "vote",
                    "voteId": vote_id,
                    "role": vote.get("role"),
                    "roleLabel": role_label,
                    "candidateId": vote.get("candidateId"),
                    "candidateName": vote.get("candidateName", "候选人"),
                    "starterName": vote.get("starterName", "管理者"),
                    "status": "rejected",
                    "yesCount": len(vote.get("yes", [])),
                    "noCount": len(vote.get("no", [])),
                    "memberCount": member_count,
                    "createdAt": vote.get("createdAt")
                }
            )

        await self.broadcast_tribe_state(tribe_id)
