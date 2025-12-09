"""
小说阅读系统路由
提供小说列表、内容获取、VIP状态管理等API接口
"""

import os
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from database import driver

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/deal", tags=["小说"])

# 小说目录
NOVELS_DIR = Path("D:/创作")


def get_novels_from_filesystem():
    """从文件系统获取小说列表"""
    novels = []
    if not NOVELS_DIR.exists():
        logger.error(f"小说目录不存在: {NOVELS_DIR}")
        return novels

    txt_files = sorted(NOVELS_DIR.glob("*.txt"))
    for idx, file_path in enumerate(txt_files, 1):
        title = file_path.stem  # 文件名（不含扩展名）
        # 简单规则：偶数序号的小说为VIP专属
        quan = 1 if idx % 2 == 1 else 0
        novels.append({
            "id": idx,
            "title": title,
            "path": str(file_path),
            "quan": quan
        })
    return novels


def get_novels_from_neo4j():
    """从Neo4j获取小说列表"""
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (n:Novel)
                RETURN n.id as id, n.title as title, n.path as path, n.quan as quan
                ORDER BY n.id
            """)
            novels = []
            for record in result:
                novels.append({
                    "id": record["id"],
                    "title": record["title"],
                    "path": record["path"],
                    "quan": record["quan"]
                })
            if novels:
                return novels
    except Exception as e:
        logger.warning(f"从Neo4j获取小说列表失败: {e}")

    return get_novels_from_filesystem()


@router.post("/getnovelzong")
async def get_novel_list():
    """获取所有小说列表"""
    novels = get_novels_from_neo4j()
    return [{"title": n["title"], "path": n["path"], "quan": n["quan"]} for n in novels]


@router.post("/getnovel")
async def get_novel_content(
    a: int = Query(..., description="章节号/小说序号"),
    b: str = Query("", description="VIP状态标识，'1'表示VIP")
):
    """获取小说内容"""
    novels = get_novels_from_neo4j()

    if a < 1 or a > len(novels):
        raise HTTPException(status_code=404, detail="小说不存在")

    novel = novels[a - 1]
    is_vip = b == "1"

    try:
        file_path = Path(novel["path"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="小说文件不存在")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 如果是VIP专属小说且用户不是VIP，只返回40%内容
        if novel["quan"] == 0 and not is_vip:
            content_length = len(content)
            visible_length = int(content_length * 0.4)
            content = content[:visible_length]

        return content

    except Exception as e:
        logger.error(f"读取小说内容失败: {e}")
        raise HTTPException(status_code=500, detail="读取小说内容失败")


@router.post("/gethui")
async def get_vip_status(b: str = Query("", description="用户名")):
    """获取用户VIP状态"""
    if not b:
        return ""

    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (u:User {username: $username})
                RETURN u.is_vip as is_vip
            """, username=b)
            record = result.single()
            if record and record["is_vip"]:
                return "1"
    except Exception as e:
        logger.warning(f"从Neo4j获取VIP状态失败: {e}")

    return ""


@router.post("/setvip")
async def set_vip_status(
    username: str = Query(..., description="用户名"),
    is_vip: bool = Query(..., description="是否VIP")
):
    """设置用户VIP状态"""
    try:
        with driver.session() as session:
            session.run("""
                MATCH (u:User {username: $username})
                SET u.is_vip = $is_vip
            """, username=username, is_vip=is_vip)
        return {"success": True, "username": username, "is_vip": is_vip}
    except Exception as e:
        logger.error(f"保存VIP状态到Neo4j失败: {e}")
        raise HTTPException(status_code=500, detail="VIP状态更新失败")


@router.get("/getvip")
async def get_user_vip(username: str = Query(..., description="用户名")):
    """获取用户VIP状态（GET方式）"""
    is_vip = False

    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (u:User {username: $username})
                RETURN u.is_vip as is_vip
            """, username=username)
            record = result.single()
            if record and record["is_vip"] is not None:
                is_vip = record["is_vip"]
    except Exception as e:
        logger.warning(f"从Neo4j获取VIP状态失败: {e}")

    return {"is_vip": is_vip, "username": username}
