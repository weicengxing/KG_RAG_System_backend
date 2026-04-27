import random
from datetime import datetime

from game_config import *


class GameStoryEventsMixin:
    def _normalize_oral_chain_line(self, text: str) -> str:
        line = " ".join(str(text or "").replace("\n", " ").replace("\r", " ").split())
        return line[:60]

    def _oral_chain_theme(self, text: str) -> tuple[str, dict]:
        lowered = str(text or "").lower()
        for theme_key, theme in TRIBE_ORAL_CHAIN_KEYWORDS.items():
            for keyword in theme.get("keywords", []):
                if keyword and str(keyword).lower() in lowered:
                    return theme_key, theme
        return "memory", {
            "label": "旧事",
            "summary": "接龙把零散旧事收成部落共同记忆。",
            "runeCandidate": "旧事纹候选",
            "reward": {"renown": 1}
        }

    def _current_oral_chain(self, tribe: dict) -> dict:
        chain = tribe.get("oral_chain")
        if not isinstance(chain, dict) or chain.get("status") == "completed":
            chain = {
                "id": f"oral_chain_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
                "title": f"{tribe.get('name', '部落')}接龙史诗",
                "status": "active",
                "lines": [],
                "themeCounts": {},
                "createdAt": datetime.now().isoformat()
            }
            tribe["oral_chain"] = chain
        chain.setdefault("lines", [])
        chain.setdefault("themeCounts", {})
        chain["target"] = TRIBE_ORAL_CHAIN_LINE_TARGET
        chain["maxLines"] = TRIBE_ORAL_CHAIN_MAX_LINES
        return chain

    def _public_oral_chain(self, tribe: dict) -> dict:
        chain = self._current_oral_chain(tribe)
        theme_counts = dict(chain.get("themeCounts", {}) or {})
        top_theme_key = max(theme_counts, key=theme_counts.get) if theme_counts else ""
        top_theme = TRIBE_ORAL_CHAIN_KEYWORDS.get(top_theme_key, {})
        lines = list(chain.get("lines", []) or [])
        return {
            "id": chain.get("id"),
            "title": chain.get("title", "接龙史诗"),
            "lines": lines,
            "themeCounts": theme_counts,
            "themeKey": top_theme_key,
            "themeLabel": top_theme.get("label", "旧事") if top_theme_key else "",
            "target": TRIBE_ORAL_CHAIN_LINE_TARGET,
            "maxLines": TRIBE_ORAL_CHAIN_MAX_LINES,
            "ready": len(lines) >= TRIBE_ORAL_CHAIN_LINE_TARGET,
            "createdAt": chain.get("createdAt")
        }

    def _apply_oral_chain_reward(self, tribe: dict, theme: dict) -> list:
        reward = dict(theme.get("reward") or {})
        reward_parts = []
        storage = tribe.setdefault("storage", {"wood": 0, "stone": 0})
        for key, label in (("wood", "木材"), ("stone", "石块")):
            amount = int(reward.get(key, 0) or 0)
            if amount:
                storage[key] = int(storage.get(key, 0) or 0) + amount
                reward_parts.append(f"{label}+{amount}")
        food = int(reward.get("food", 0) or 0)
        if food:
            tribe["food"] = int(tribe.get("food", 0) or 0) + food
            reward_parts.append(f"食物+{food}")
        discovery = int(reward.get("discoveryProgress", 0) or 0)
        if discovery:
            tribe["discovery_progress"] = int(tribe.get("discovery_progress", 0) or 0) + discovery
            reward_parts.append(f"发现+{discovery}")
        trade = int(reward.get("tradeReputation", 0) or 0)
        if trade:
            tribe["trade_reputation"] = int(tribe.get("trade_reputation", 0) or 0) + trade
            reward_parts.append(f"贸易信誉+{trade}")
        renown = TRIBE_ORAL_CHAIN_COMPLETE_RENOWN + int(reward.get("renown", 0) or 0)
        if renown:
            tribe["renown"] = int(tribe.get("renown", 0) or 0) + renown
            reward_parts.append(f"声望+{renown}")
        pressure_relief = int(reward.get("warPressureRelief", 0) or 0)
        if pressure_relief:
            relieved = 0
            for relation in (tribe.get("boundary_relations", {}) or {}).values():
                if not isinstance(relation, dict):
                    continue
                before = int(relation.get("warPressure", 0) or 0)
                if before <= 0:
                    continue
                relation["warPressure"] = max(0, before - pressure_relief)
                relation["canDeclareWar"] = int(relation.get("warPressure", 0) or 0) >= TRIBE_SKIRMISH_WAR_PRESSURE_THRESHOLD
                relieved += before - int(relation.get("warPressure", 0) or 0)
            if relieved:
                reward_parts.append(f"战争压力-{relieved}")
        return reward_parts

    async def add_oral_chain_line(self, player_id: str, text: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        line_text = self._normalize_oral_chain_line(text)
        if len(line_text) < 4:
            await self._send_tribe_error(player_id, "接龙句子至少需要 4 个字")
            return

        chain = self._current_oral_chain(tribe)
        lines = chain.setdefault("lines", [])
        if len(lines) >= TRIBE_ORAL_CHAIN_MAX_LINES:
            await self._send_tribe_error(player_id, "这轮接龙已经写满，请先整理成史诗")
            return
        if any(item.get("memberId") == player_id for item in lines if isinstance(item, dict)):
            await self._send_tribe_error(player_id, "每轮接龙每名成员只能补一句")
            return

        member = tribe.get("members", {}).get(player_id, {})
        player = self.players.get(player_id, {})
        theme_key, theme = self._oral_chain_theme(line_text)
        now_text = datetime.now().isoformat()
        line = {
            "id": f"oral_line_{int(datetime.now().timestamp() * 1000)}_{len(lines)}",
            "text": line_text,
            "memberId": player_id,
            "memberName": member.get("name") or player.get("name", "成员"),
            "themeKey": theme_key,
            "themeLabel": theme.get("label", "旧事"),
            "createdAt": now_text
        }
        lines.append(line)
        theme_counts = chain.setdefault("themeCounts", {})
        theme_counts[theme_key] = int(theme_counts.get(theme_key, 0) or 0) + 1
        player["personal_renown"] = int(player.get("personal_renown", 0) or 0) + TRIBE_ORAL_CHAIN_LINE_RENOWN
        member["oral_chain_lines"] = int(member.get("oral_chain_lines", 0) or 0) + 1

        detail = f"{line['memberName']} 接了一句“{line_text}”，接龙主题偏向{line['themeLabel']}，个人声望 +{TRIBE_ORAL_CHAIN_LINE_RENOWN}。"
        self._add_tribe_history(tribe, "ritual", "口述史接龙", detail, player_id, {"kind": "oral_chain_line", **line, "chainId": chain.get("id")})
        await self._notify_tribe(tribe_id, detail)
        await self.broadcast_tribe_state(tribe_id)
        await self.send_personal_conflict_status(player_id)

    async def complete_oral_chain(self, player_id: str):
        tribe_id = self.player_tribes.get(player_id)
        tribe = self.tribes.get(tribe_id)
        if not tribe:
            await self._send_tribe_error(player_id, "请先加入一个部落")
            return

        member = tribe.get("members", {}).get(player_id, {})
        if member.get("role") not in ("leader", "elder"):
            await self._send_tribe_error(player_id, "只有首领或长老可以整理接龙史诗")
            return

        chain = self._current_oral_chain(tribe)
        lines = list(chain.get("lines", []) or [])
        if len(lines) < TRIBE_ORAL_CHAIN_LINE_TARGET:
            await self._send_tribe_error(player_id, f"至少需要 {TRIBE_ORAL_CHAIN_LINE_TARGET} 句接龙才能整理史诗")
            return

        theme_counts = dict(chain.get("themeCounts", {}) or {})
        theme_key = max(theme_counts, key=theme_counts.get) if theme_counts else "memory"
        theme = TRIBE_ORAL_CHAIN_KEYWORDS.get(theme_key) or {
            "label": "旧事",
            "summary": "接龙把零散旧事收成部落共同记忆。",
            "runeCandidate": "旧事纹候选",
            "reward": {"renown": 1}
        }
        reward_parts = self._apply_oral_chain_reward(tribe, theme)
        excerpt = " / ".join([item.get("text", "") for item in lines[-3:] if isinstance(item, dict) and item.get("text")])
        epic = {
            "id": f"epic_{int(datetime.now().timestamp() * 1000)}_{random.randint(100, 999)}",
            "title": f"{tribe.get('name', '部落')}{theme.get('label', '旧事')}接龙史",
            "summary": f"{theme.get('summary', '部落把接龙整理成新的故事')} 最后传唱：“{excerpt}”。",
            "composedBy": member.get("name", "管理者"),
            "source": "oral_chain",
            "themeKey": theme_key,
            "themeLabel": theme.get("label", "旧事"),
            "runeCandidate": theme.get("runeCandidate", ""),
            "rewardParts": reward_parts,
            "lineCount": len(lines),
            "lines": lines,
            "createdAt": datetime.now().isoformat()
        }
        tribe.setdefault("oral_epics", []).append(epic)
        tribe["oral_epics"] = tribe["oral_epics"][-8:]
        chain["status"] = "completed"
        chain["completedAt"] = epic["createdAt"]
        chain["completedBy"] = player_id
        tribe.setdefault("oral_chain_archive", []).append(chain)
        tribe["oral_chain_archive"] = tribe["oral_chain_archive"][-5:]
        tribe["oral_chain"] = None
        camp_center = (tribe.get("camp") or {}).get("center") or {}
        self._record_map_memory(
            tribe,
            "oral_epic",
            f"{theme.get('label', '旧事')}接龙火痕",
            f"《{epic['title']}》曾在营火旁被整理，后来者可沿着故事重新辨认部落路线。",
            float(camp_center.get("x", 0) or 0),
            float(camp_center.get("z", 0) or 0),
            epic["id"],
            member.get("name", "管理者")
        )

        reward_text = f" {'、'.join(reward_parts)}。" if reward_parts else ""
        candidate_text = f" 图腾旁出现“{epic['runeCandidate']}”。" if epic.get("runeCandidate") else ""
        detail = f"{epic['composedBy']} 将 {len(lines)} 句接龙整理成《{epic['title']}》：{epic['summary']}{reward_text}{candidate_text}"
        self._add_tribe_history(tribe, "ritual", "整理接龙史诗", detail, player_id, {"kind": "oral_chain_epic", **epic})
        await self._publish_world_rumor(
            "epic",
            "口述史接龙",
            f"{tribe.get('name', '部落')} 传出新的接龙史诗：{epic['summary']}",
            {"tribeId": tribe_id, "epicId": epic["id"], "theme": theme_key, "rewardParts": reward_parts}
        )
        await self.broadcast_tribe_state(tribe_id)
        await self._broadcast_current_map()
