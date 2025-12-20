"""
api/group_routes.py
群组聊天功能路由模块
负责处理：创建群组、加入群组、离开群组、群组消息
技术点：MongoDB、Redis 实时通知、复用分桶存储
"""

import time
import logging
import uuid
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Header, status
from pydantic import BaseModel, Field

# 引入数据库管理器
from database_asy_mon_re import db_manager
# 引入Token工具
from utils import decode_token_with_exp

# 基础日志配置
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/group", tags=["Group"])

# ==================== 依赖注入 ====================

async def get_current_user_id(authorization: str = Header(None)) -> str:
    """从 Header 获取 Token 并解析出 user_id"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")

    token = authorization.split(" ")[1] if " " in authorization else authorization
    payload, is_expired, error = decode_token_with_exp(token)

    if not payload or is_expired:
        raise HTTPException(status_code=401, detail="Token invalid or expired")

    # 兼容新旧两种 token 格式
    username = payload.get("username") or payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # 从 MongoDB 查询用户获取 _id
    db = db_manager.db
    user = await db.users.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return str(user["_id"])

# ==================== Pydantic 模型定义 ====================

class CreateGroupInput(BaseModel):
    group_name: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=200)
    member_ids: List[str] = Field(default_factory=list)  # 初始成员列表

class UpdateGroupInput(BaseModel):
    group_name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    group_avatar: Optional[str] = None

class AddMemberInput(BaseModel):
    group_id: str
    user_ids: List[str]

class RemoveMemberInput(BaseModel):
    group_id: str
    user_id: str

class JoinByInviteInput(BaseModel):
    invite_code: str

class GroupResponse(BaseModel):
    group_id: str = Field(alias="_id")
    group_name: str
    group_avatar: str
    owner_id: str
    members: List[str]
    member_count: int
    description: str
    created_at: float
    invite_code: Optional[str] = None

    class Config:
        populate_by_name = True

# ==================== API 路由实现 ====================

@router.post("/create", response_model=GroupResponse)
async def create_group(
    data: CreateGroupInput,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    创建群组
    """
    db = db_manager.db
    redis = db_manager.redis

    try:
        # 1. 生成群组ID和邀请码
        group_id = str(uuid.uuid4())
        invite_code = str(uuid.uuid4())[:8].upper()  # 8位邀请码

        # 2. 初始成员列表 (包括创建者)
        members = list(set([current_user_id] + data.member_ids))

        # 3. 构建群组文档
        group_doc = {
            "_id": group_id,
            "group_name": data.group_name,
            "group_avatar": "",  # 默认头像，后续可上传
            "owner_id": current_user_id,
            "members": members,
            "description": data.description,
            "invite_code": invite_code,
            "created_at": time.time(),
            "updated_at": time.time()
        }

        # 4. 插入数据库
        await db.groups.insert_one(group_doc)

        # 5. 插入user_groups关系表（数据冗余，提升查询效率）
        user_group_docs = []
        for member_id in members:
            user_group_docs.append({
                "user_id": member_id,
                "group_id": group_id,
                "role": "owner" if member_id == current_user_id else "member",
                "joined_at": time.time()
            })

        if user_group_docs:
            await db.user_groups.insert_many(user_group_docs)

        # 6. 通知所有成员（通过Redis）
        notification_payload = json.dumps({
            "type": "group_created",
            "data": {
                "group_id": group_id,
                "group_name": data.group_name,
                "owner_id": current_user_id
            }
        })

        for member_id in members:
            await redis.publish(f"chat:user:{member_id}", notification_payload)

        logger.info(f"✅ 群组创建成功: {group_id} by {current_user_id}")

        # 7. 返回群组信息
        group_doc["member_count"] = len(members)
        return group_doc

    except Exception as e:
        logger.error(f"❌ 创建群组失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create group: {str(e)}")


@router.get("/list", response_model=List[GroupResponse])
async def get_my_groups(
    current_user_id: str = Depends(get_current_user_id)
):
    """
    获取我加入的所有群组（使用user_groups表，性能优化）
    """
    db = db_manager.db

    try:
        # 从user_groups表查询用户所有群组（性能优化）
        cursor = db.user_groups.find({"user_id": current_user_id})

        group_ids = []
        async for ug in cursor:
            group_ids.append(ug["group_id"])

        if not group_ids:
            return []

        # 批量查询群组信息
        groups_cursor = db.groups.find({"_id": {"$in": group_ids}})

        groups = []
        async for group in groups_cursor:
            group["member_count"] = len(group.get("members", []))
            groups.append(group)

        return groups

    except Exception as e:
        logger.error(f"❌ 获取群组列表失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to get groups")


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group_info(
    group_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    获取群组详细信息
    """
    db = db_manager.db

    try:
        group = await db.groups.find_one({"_id": group_id})

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # 验证用户是否是群成员
        if current_user_id not in group.get("members", []):
            raise HTTPException(status_code=403, detail="You are not a member of this group")

        group["member_count"] = len(group.get("members", []))
        return group

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取群组信息失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to get group info")


@router.post("/add_members")
async def add_members(
    data: AddMemberInput,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    添加群成员（仅群主可操作）
    """
    db = db_manager.db
    redis = db_manager.redis

    try:
        # 1. 查询群组
        group = await db.groups.find_one({"_id": data.group_id})

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # 2. 验证权限（仅群主）
        if group["owner_id"] != current_user_id:
            raise HTTPException(status_code=403, detail="Only group owner can add members")

        # 3. 添加新成员（去重）
        current_members = set(group.get("members", []))
        new_members = set(data.user_ids) - current_members

        if not new_members:
            return {"message": "All users are already members"}

        updated_members = list(current_members | new_members)

        # 4. 更新数据库
        await db.groups.update_one(
            {"_id": data.group_id},
            {
                "$set": {
                    "members": updated_members,
                    "updated_at": time.time()
                }
            }
        )

        # 5. 更新user_groups关系表
        user_group_docs = []
        for member_id in new_members:
            user_group_docs.append({
                "user_id": member_id,
                "group_id": data.group_id,
                "role": "member",
                "joined_at": time.time()
            })

        if user_group_docs:
            await db.user_groups.insert_many(user_group_docs)

        # 6. 通知新成员
        notification_payload = json.dumps({
            "type": "added_to_group",
            "data": {
                "group_id": data.group_id,
                "group_name": group["group_name"]
            }
        })

        for member_id in new_members:
            await redis.publish(f"chat:user:{member_id}", notification_payload)

        logger.info(f"✅ 添加群成员成功: {data.group_id}, 新增 {len(new_members)} 人")

        return {"message": f"Successfully added {len(new_members)} members"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 添加群成员失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to add members")


@router.post("/remove_member")
async def remove_member(
    data: RemoveMemberInput,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    移除群成员（群主可操作，或自己退出群组）
    """
    db = db_manager.db
    redis = db_manager.redis

    try:
        # 1. 查询群组
        group = await db.groups.find_one({"_id": data.group_id})

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # 2. 验证权限
        is_owner = group["owner_id"] == current_user_id
        is_self = data.user_id == current_user_id

        if not (is_owner or is_self):
            raise HTTPException(status_code=403, detail="Permission denied")

        # 3. 不能移除群主
        if data.user_id == group["owner_id"]:
            raise HTTPException(status_code=400, detail="Cannot remove group owner. Transfer ownership first.")

        # 4. 更新成员列表
        current_members = group.get("members", [])

        if data.user_id not in current_members:
            raise HTTPException(status_code=400, detail="User is not a member")

        updated_members = [m for m in current_members if m != data.user_id]

        await db.groups.update_one(
            {"_id": data.group_id},
            {
                "$set": {
                    "members": updated_members,
                    "updated_at": time.time()
                }
            }
        )

        # 5. 从user_groups关系表删除
        await db.user_groups.delete_one({
            "user_id": data.user_id,
            "group_id": data.group_id
        })

        # 6. 通知被移除的用户
        notification_payload = json.dumps({
            "type": "removed_from_group",
            "data": {
                "group_id": data.group_id,
                "group_name": group["group_name"]
            }
        })

        await redis.publish(f"chat:user:{data.user_id}", notification_payload)

        action = "left" if is_self else "removed"
        logger.info(f"✅ 群成员{action}: {data.group_id}, user: {data.user_id}")

        return {"message": f"User {action} successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 移除群成员失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove member")


@router.put("/{group_id}")
async def update_group(
    group_id: str,
    data: UpdateGroupInput,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    更新群组信息（仅群主）
    """
    db = db_manager.db

    try:
        # 1. 查询群组
        group = await db.groups.find_one({"_id": group_id})

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # 2. 验证权限
        if group["owner_id"] != current_user_id:
            raise HTTPException(status_code=403, detail="Only group owner can update group info")

        # 3. 构建更新字段
        update_fields = {"updated_at": time.time()}

        if data.group_name is not None:
            update_fields["group_name"] = data.group_name
        if data.description is not None:
            update_fields["description"] = data.description
        if data.group_avatar is not None:
            update_fields["group_avatar"] = data.group_avatar

        # 4. 更新数据库
        await db.groups.update_one(
            {"_id": group_id},
            {"$set": update_fields}
        )

        logger.info(f"✅ 群组信息更新成功: {group_id}")

        return {"message": "Group updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 更新群组失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to update group")


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    解散群组（仅群主）
    """
    db = db_manager.db
    redis = db_manager.redis

    try:
        # 1. 查询群组
        group = await db.groups.find_one({"_id": group_id})

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # 2. 验证权限
        if group["owner_id"] != current_user_id:
            raise HTTPException(status_code=403, detail="Only group owner can delete group")

        # 3. 删除群组
        await db.groups.delete_one({"_id": group_id})

        # 4. 通知所有成员
        notification_payload = json.dumps({
            "type": "group_deleted",
            "data": {
                "group_id": group_id,
                "group_name": group["group_name"]
            }
        })

        for member_id in group.get("members", []):
            await redis.publish(f"chat:user:{member_id}", notification_payload)

        logger.info(f"✅ 群组已解散: {group_id}")

        return {"message": "Group deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 解散群组失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete group")


@router.get("/{group_id}/members")
async def get_group_members(
    group_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    获取群成员列表（带详细信息）
    """
    db = db_manager.db

    try:
        # 1. 查询群组
        group = await db.groups.find_one({"_id": group_id})

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # 2. 验证权限
        if current_user_id not in group.get("members", []):
            raise HTTPException(status_code=403, detail="You are not a member of this group")

        # 3. 查询成员详细信息
        member_ids = group.get("members", [])
        members = []

        for member_id in member_ids:
            # 尝试从MongoDB users集合获取用户信息
            try:
                user_id_int = int(member_id)
                user = await db.users.find_one({"_id": user_id_int})
            except (ValueError, TypeError):
                user = await db.users.find_one({"_id": member_id})

            if user:
                members.append({
                    "user_id": member_id,
                    "username": user.get("username", "Unknown"),
                    "avatar": user.get("avatar", ""),
                    "is_owner": member_id == group["owner_id"]
                })

        return {
            "group_id": group_id,
            "members": members,
            "total": len(members)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取群成员列表失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to get members")


# ==================== 邀请功能 ====================

@router.post("/join")
async def join_by_invite(
    data: JoinByInviteInput,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    通过邀请码加入群组
    """
    db = db_manager.db
    redis = db_manager.redis

    try:
        # 1. 查找群组
        group = await db.groups.find_one({"invite_code": data.invite_code})

        if not group:
            raise HTTPException(status_code=404, detail="Invalid invite code")

        group_id = group["_id"]

        # 2. 检查是否已经是成员
        existing = await db.user_groups.find_one({
            "user_id": current_user_id,
            "group_id": group_id
        })

        if existing:
            return {"message": "You are already a member of this group"}

        # 3. 添加到群组
        await db.groups.update_one(
            {"_id": group_id},
            {
                "$addToSet": {"members": current_user_id},
                "$set": {"updated_at": time.time()}
            }
        )

        # 4. 添加到user_groups关系表
        await db.user_groups.insert_one({
            "user_id": current_user_id,
            "group_id": group_id,
            "role": "member",
            "joined_at": time.time()
        })

        # 5. 通知该用户
        notification_payload = json.dumps({
            "type": "added_to_group",
            "data": {
                "group_id": group_id,
                "group_name": group["group_name"]
            }
        })

        await redis.publish(f"chat:user:{current_user_id}", notification_payload)

        logger.info(f"✅ 用户 {current_user_id} 通过邀请码加入群组 {group_id}")

        return {
            "message": "Successfully joined the group",
            "group_id": group_id,
            "group_name": group["group_name"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 加入群组失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to join group")


@router.post("/join_by_id")
async def join_by_group_id(
    body: dict,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    通过群组ID直接加入群组（用于群邀请卡片）
    """
    db = db_manager.db
    redis = db_manager.redis

    group_id = body.get("group_id", "").strip()
    if not group_id:
        raise HTTPException(status_code=400, detail="group_id is required")

    try:
        # 1. 查找群组
        group = await db.groups.find_one({"_id": group_id})

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # 2. 检查是否已经是成员
        existing = await db.user_groups.find_one({
            "user_id": current_user_id,
            "group_id": group_id
        })

        if existing:
            return {
                "message": "You are already a member of this group",
                "already_member": True,
                "group_id": group_id,
                "group_name": group["group_name"]
            }

        # 3. 添加到群组
        await db.groups.update_one(
            {"_id": group_id},
            {
                "$addToSet": {"members": current_user_id},
                "$set": {"updated_at": time.time()}
            }
        )

        # 4. 添加到user_groups关系表
        await db.user_groups.insert_one({
            "user_id": current_user_id,
            "group_id": group_id,
            "role": "member",
            "joined_at": time.time()
        })

        # 5. 通知该用户（刷新群组列表）
        notification_payload = json.dumps({
            "type": "added_to_group",
            "data": {
                "group_id": group_id,
                "group_name": group["group_name"]
            }
        })

        await redis.publish(f"chat:user:{current_user_id}", notification_payload)

        logger.info(f"✅ 用户 {current_user_id} 通过群邀请卡片加入群组 {group_id}")

        return {
            "message": "Successfully joined the group",
            "already_member": False,
            "group_id": group_id,
            "group_name": group["group_name"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 加入群组失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to join group")


@router.get("/{group_id}/invite_link")
async def get_invite_link(
    group_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    获取群组邀请链接（仅群成员可获取）
    """
    db = db_manager.db

    try:
        # 1. 查询群组
        group = await db.groups.find_one({"_id": group_id})

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # 2. 验证用户是否是群成员
        is_member = await db.user_groups.find_one({
            "user_id": current_user_id,
            "group_id": group_id
        })

        if not is_member:
            raise HTTPException(status_code=403, detail="You are not a member of this group")

        # 3. 返回邀请码
        invite_code = group.get("invite_code")

        if not invite_code:
            # 如果没有邀请码，生成一个
            invite_code = str(uuid.uuid4())[:8].upper()
            await db.groups.update_one(
                {"_id": group_id},
                {"$set": {"invite_code": invite_code}}
            )

        return {
            "invite_code": invite_code,
            "invite_link": f"http://localhost:5173/chat?invite={invite_code}",  # 前端需要处理这个链接
            "group_name": group["group_name"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取邀请链接失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to get invite link")


@router.post("/{group_id}/refresh_invite")
async def refresh_invite_code(
    group_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    刷新群组邀请码（仅群主可操作）
    """
    db = db_manager.db

    try:
        # 1. 查询群组
        group = await db.groups.find_one({"_id": group_id})

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # 2. 验证权限（仅群主）
        if group["owner_id"] != current_user_id:
            raise HTTPException(status_code=403, detail="Only group owner can refresh invite code")

        # 3. 生成新的邀请码
        new_invite_code = str(uuid.uuid4())[:8].upper()

        await db.groups.update_one(
            {"_id": group_id},
            {"$set": {"invite_code": new_invite_code, "updated_at": time.time()}}
        )

        logger.info(f"✅ 群组 {group_id} 邀请码已刷新")

        return {
            "message": "Invite code refreshed successfully",
            "invite_code": new_invite_code,
            "invite_link": f"http://localhost:5173/chat?invite={new_invite_code}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 刷新邀请码失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh invite code")
