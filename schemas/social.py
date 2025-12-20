"""
schemas/social.py
定义好友、申请相关的 Pydantic 模型
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field
import time

# ========== 枚举状态 ==========
class RequestStatus:
    PENDING = "pending"     # 待处理
    ACCEPTED = "accepted"   # 已同意
    REJECTED = "rejected"   # 已拒绝
    
class RelationType:
    FRIEND = "friend"       # 好友
    STRANGER = "stranger"   # 陌生人
    MYSELF = "myself"       # 自己

# ========== 请求体 (Request Body) - 前端传给后端的 ==========

class SearchUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)

class SendFriendRequest(BaseModel):
    target_user_id: str
    request_msg: str = Field(default="Hello, I'd like to be your friend.")

class HandleFriendRequest(BaseModel):
    request_id: str
    action: Literal["accept", "reject"]

# ========== 数据库模型 / 响应体 ==========

class FriendRequestDB(BaseModel):
    """friend_requests 集合的文档结构"""
    id: str = Field(alias="_id") # Mongo ID
    from_user_id: str
    to_user_id: str
    from_username: str    # 冗余存储，避免查表，提高列表展示速度
    from_avatar: str      # 冗余存储
    request_msg: str
    status: str           # "pending" | "accepted" | "rejected"
    create_time: float
    update_time: float

    class Config:
        populate_by_name = True # 允许使用 alias (_id)

class UserSearchResult(BaseModel):
    """搜索结果返回卡片"""
    user_id: str
    username: str
    avatar: str
    relation: str # 告诉前端展示 "加好友" 按钮还是 "发消息" 按钮

class FriendContactDB(BaseModel):
    """contacts 集合的文档结构 (双向记录)"""
    owner_id: str    # 当前拥有者
    friend_id: str   # 朋友ID
    remark: Optional[str] = None
    created_at: float
    # 这里也可以冗余 friend_username/avatar, 但一般用户头像会变，
    # 建议关联查询或者前端缓存，这里只存ID最稳妥