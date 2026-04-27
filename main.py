from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from utils import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token, decode_token_with_exp, extract_user_info_from_payload, create_token_with_user_info
import database
from database_async import AsyncDatabaseManager
import email_utils # 引入刚才写的
from datetime import datetime, timedelta
import time
import os
import uuid
import shutil
from rate_limiter import check_rate_limit, is_rate_limiter_available
import logging
from snowflake import id_generator
from api import social_routes
from chat_routes import router as chat_router
from typing import Optional
from config import MONGO_DB_NAME
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from database_asy_mon_re import db_manager
import hashlib
import re
from redis_utils import (
    save_forgot_password_code,
    verify_forgot_password_code,
    delete_forgot_password_code,
    create_qr_session,
    get_qr_session,
    confirm_qr_login,
    delete_qr_session,
)

# 1. 定义更新资料的请求体模型
class ProfileUpdateSchema(BaseModel):
    username: str
    email: EmailStr
    job_title: Optional[str] = ""
    website: Optional[str] = ""
    bio: Optional[str] = ""

# 资料完成度计算
def calc_profile_completion(user_stats: dict) -> int:
    """根据填写字段数量计算资料完成度，范围 0-100"""
    if not user_stats:
        return 0
    fields = [
        user_stats.get("username"),
        user_stats.get("email"),
        user_stats.get("job_title"),
        user_stats.get("website"),
        user_stats.get("bio"),
        user_stats.get("avatar"),
    ]
    filled = sum(1 for f in fields if f not in (None, "", 0))
    # 至少有用户名邮箱两个基础字段，保持 0-100 的线性比例
    total = len(fields)
    return int((filled / total) * 100)


def evaluate_password_strength(password: str) -> int:
    """粗略评估密码复杂度，返回 1-4 等级"""
    if not password:
        return 1

    length = len(password)
    categories = sum([
        bool(re.search(r"[a-z]", password)),
        bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"[0-9]", password)),
        bool(re.search(r"[^\w\s]", password))
    ])

    score = 0
    if length >= 8:
        score += 1
    if length >= 12:
        score += 1
    if categories >= 3:
        score += 1
    if length >= 16 and categories == 4:
        score += 1

    # 限定范围 1-4
    return max(1, min(score, 4))


def build_security_rating(password_strength: int, twofa_enabled: bool) -> dict:
    """基于密码强度与2FA状态生成安全评级"""
    strength = password_strength or 2
    has_2fa = bool(twofa_enabled)

    if has_2fa and strength >= 4:
        return {"level": "top_secret", "label": "绝密", "color": "purple"}
    if strength >= 3:
        return {"level": "high", "label": "高", "color": "green"}
    if strength >= 2:
        return {"level": "medium", "label": "中", "color": "yellow"}
    return {"level": "low", "label": "低", "color": "red"}

# 导入TraceID中间件
from middleware.trace_middleware import TraceIDMiddleware

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jwt_auth")

app = FastAPI()

# 注册TraceID中间件（必须在其他中间件之前）
app.add_middleware(TraceIDMiddleware)
verification_codes = {}  # 格式: {email: {"code": "123456", "created_at": timestamp, "expires_at": timestamp}}
db_async_manager = AsyncDatabaseManager(max_workers=5)

# 头像存储目录 - 改为存储在assets目录下
# 计算相对于项目根目录的绝对路径
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
AVATAR_DIR = os.path.join(current_dir, "assets", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

# 2FA 存储目录（按照需求存放在 venv 目录下）
TWOFA_DIR = os.path.join(os.path.dirname(current_dir), "2FA")
os.makedirs(TWOFA_DIR, exist_ok=True)

print(f"[AVATAR DEBUG] 头像存储目录: {AVATAR_DIR}")
print(f"[2FA DEBUG] 2FA存储目录: {TWOFA_DIR}")

# 挂载静态文件目录，用于提供头像访问
app.mount("/avatar", StaticFiles(directory=AVATAR_DIR), name="avatar")

class EmailSchema(BaseModel):
    email: EmailStr

class RegisterSchema(BaseModel):
    email: EmailStr
    code: str
    password: str
    username: str # 依然保留用户名作为昵称

class ForgotPasswordSendSchema(BaseModel):
    username: str
    email: EmailStr

class ForgotPasswordResetSchema(BaseModel):
    username: str
    email: EmailStr
    code: str
    new_password: str

class QRConfirmSchema(BaseModel):
    qr_id: str
    username: str
    password: str

class LoginSchema(BaseModel):
    username: str # 登录还是用用户名方便，或者你可以改成用邮箱登录

class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str
    # 前端已做强度校验，这里仅存储等级，默认中等
    password_strength: int = 2

# CORS 配置保持不变...
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "https://kg-rag-system-frontend.pages.dev",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_origin_regex=r"^(https://systemfrontend.*\.cool|http://(localhost|127\.0\.0\.1):\d+)$",
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流中间件（在JWT认证之前执行）
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """限流中间件：检查IP、接口和全局限流"""
    # 不需要限流的路径（健康检查、文档等）
    exempt_paths = ["/", "/docs", "/openapi.json", "/redoc"]
    path = request.url.path
    
    # 检查是否是豁免路径
    is_exempt = any(path == p or path.startswith(p) for p in exempt_paths)
    
    if not is_exempt and is_rate_limiter_available():
        # 获取客户端IP
        client_ip = request.client.host
        # 如果使用了代理，尝试从X-Forwarded-For获取真实IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        # 检查限流
        allowed, limit_type, remaining, retry_after = check_rate_limit(
            client_ip=client_ip,
            endpoint=path
        )
        
        if not allowed:
            # 构建限流响应
            error_detail = {
                "detail": "请求过于频繁，请稍后再试",
                "code": "RATE_LIMIT_EXCEEDED",
                "limit_type": limit_type,  # "ip", "endpoint", "global"
                "retry_after": retry_after  # 需要等待的秒数
            }
            
            # 添加限流相关的响应头
            response = JSONResponse(
                status_code=429,  # Too Many Requests
                content=error_detail
            )
            response.headers["X-RateLimit-Limit-Type"] = limit_type
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["Retry-After"] = str(retry_after)
            
            return response
    
    # 限流通过，继续处理请求
    response = await call_next(request)
    
    # 如果限流器可用，添加限流信息到响应头（用于调试）
    if is_rate_limiter_available() and not is_exempt:
        # 这里可以添加更多限流信息到响应头
        pass
    
    return response

# JWT 认证中间件
@app.middleware("http")
async def jwt_auth_middleware(request: Request, call_next):
    # 如果是OPTIONS请求（CORS预检），直接放行
    if request.method == "OPTIONS":
        print(f"[JWT DEBUG] OPTIONS请求，直接放行")
        response = await call_next(request)
        return response
    
    # 不需要认证的路径
    public_paths = ["/docs", "/openapi.json", "/redoc"]
    # 不需要认证的 auth 路径（精确匹配）
    public_auth_paths = [
        "/auth/login",
        "/auth/register",
        "/auth/send-code",
        "/auth/verify-2fa",
        "/auth/forgot-password/send-code",
        "/auth/forgot-password/reset",
    ]
    # 允许匿名访问的二维码相关前缀（生成/检查/状态/确认）
    qr_public_prefixes = [
        "/auth/qr/generate",
        "/auth/qr/check",
        "/auth/qr/status",
        "/auth/qr/confirm",
    ]
    # 音乐相关的公开路径（图片可以直接访问）
    music_public_prefixes = [
        "/api/music/image",
    ]

    # 检查是否是公开路径
    path = request.url.path
    if path.startswith("/api/chat/ws"):
        print(f"[JWT DEBUG] WebSocket路径，放行由内部鉴权: {path}")
        return await call_next(request)
    is_public = (
        any(path == p or (p != "/" and path.startswith(p)) for p in public_paths) or
        path in public_auth_paths or
        any(path.startswith(prefix) for prefix in qr_public_prefixes)
    )

    # 🔍 添加调试信息
    print(f"[JWT DEBUG] 请求路径: {path}")
    print(f"[JWT DEBUG] 是否公开路径: {is_public}")
    print(f"[JWT DEBUG] Authorization header: {request.headers.get('Authorization')}")
    print(f"[JWT DEBUG] 请求方法: {request.method}")

    # 如果是公开路径，直接放行
    if is_public:
        print(f"[JWT DEBUG] 公开路径，直接放行")
        response = await call_next(request)
        
        # 如果有新token，添加到响应header
        if hasattr(request.state, "new_token") and request.state.new_token:
            response.headers["X-New-Token"] = request.state.new_token
            
        return response

    # 需要认证的路径
    # 优先从 Authorization header 获取 token
    auth_header = request.headers.get("Authorization")
    token = None

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        print(f"[JWT DEBUG] 从header获取到token: {token[:20]}...")  # 只打印前20个字符
    else:
        # 备用：从 query 参数获取 token（用于 SSE 等不支持自定义 header 的场景）
        token = request.query_params.get("token")
        if token:
            print(f"[JWT DEBUG] 从query参数获取到token: {token[:20]}...")

    if not token:
        print(f"[JWT DEBUG] ❌ 未找到token，返回401")
        return JSONResponse(status_code=401, content={"detail": "未提供认证令牌"})

    try:
        print(f"[JWT DEBUG] 开始解码token...")
        # 使用新的decode函数区分过期和无效
        payload, is_expired, error_msg = decode_token_with_exp(token)
        print(f"[JWT DEBUG] Token解码结果: payload={payload}, expired={is_expired}, error={error_msg}")

        if payload is None:
            # Token完全无效，无法解码
            print(f"[JWT DEBUG] ❌ Token完全无效: {error_msg}")
            return JSONResponse(status_code=401, content={"detail": error_msg or "认证失败"})

        # 使用新的工具函数提取用户信息（支持新旧格式）
        user_id, username = extract_user_info_from_payload(payload)
        
        if not username:
            print(f"[JWT DEBUG] ❌ Token中缺少用户信息")
            return JSONResponse(status_code=401, content={"detail": "Token中缺少用户信息"})

        print(f"[JWT DEBUG] ✅ Token有效，用户ID: {user_id}, 用户名: {username}")

        # 存储用户信息到request.state（保持向后兼容）
        request.state.current_user = username
        request.state.current_user_id = user_id  # 新增：存储用户ID
        request.state.token_expired = is_expired
        request.state.new_token = None

        # 认证成功，更新用户的最后活动时间
        print(f"[JWT DEBUG] 更新用户最后活动时间: {username}")
        database.update_last_activity(username)

        # 如果token已过期，检查是否在24小时活动窗口内
        if is_expired:
            print(f"[JWT DEBUG] Token已过期，检查24小时窗口...")
            # 从数据库查询用户的last_activity
            db_user = database.get_user(username)
            print(f"[JWT DEBUG] 数据库用户信息: {db_user}")
            
            if not db_user:
                print(f"[JWT DEBUG] ❌ 用户不存在")
                return JSONResponse(status_code=401, content={"detail": "用户不存在"})

            last_activity = db_user.get("last_activity")
            if last_activity is None:
                # 如果没有last_activity，默认拒绝访问，强制重新登录
                print(f"[JWT DEBUG] ❌ 用户没有last_activity")
                return JSONResponse(status_code=401, content={"detail": "Token已过期，请重新登录"})

            # 计算时间差（last_activity通常是毫秒时间戳）
            current_time = time.time() * 1000  # 转换为毫秒
            time_diff_ms = current_time - last_activity
            time_diff_hours = time_diff_ms / (1000 * 60 * 60)
            print(f"[JWT DEBUG] 时间差: {time_diff_hours:.2f}小时")

            # 如果超过24小时，返回401并要求重新登录
            if time_diff_hours > 24:
                print(f"[JWT DEBUG] ❌ 超过24小时窗口")
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "活动已过期，请重新登录",
                        "code": "SESSION_EXPIRED"  # 前端可以用这个code来判断是否跳转登录页
                    }
                )

            # 在24小时内，创建新的access token并添加到响应header
            # 使用新的格式创建token（包含用户ID和用户名）
            if user_id:
                new_token = create_token_with_user_info(user_id, username)
            else:
                # 如果旧token没有user_id，需要从数据库获取
                db_user = database.get_user(username)
                if db_user and db_user.get("id"):
                    user_id = db_user.get("id")
                    new_token = create_token_with_user_info(user_id, username)
                else:
                    new_token = create_access_token(data={"sub": username})
                    
            request.state.new_token = new_token
            print(f"[JWT DEBUG] ✅ 生成新token成功")

    except Exception as e:
        # 记录错误详情
        print(f"[JWT DEBUG] ❌ 认证异常: {e}")
        logger.error(f"[JWT] 认证异常: {e}, path: {path}")
        return JSONResponse(status_code=401, content={"detail": "认证失败"})

    print(f"[JWT DEBUG] ✅ 认证通过，继续处理请求")
    response = await call_next(request)
    
    # 如果有新token，添加到响应header
    if hasattr(request.state, "new_token") and request.state.new_token:
        response.headers["X-New-Token"] = request.state.new_token
        print(f"[JWT DEBUG] 添加新token到响应头")
    
    return response

# 注册音乐路由
from music_routes import router as music_router
app.include_router(music_router)

# 注册小说路由
from novel_routes import router as novel_router
app.include_router(novel_router)

# 注册社交路由
app.include_router(social_routes.router)
# 注册聊天室路由
from chat_routes import router as chat_router
app.include_router(chat_router)
from qa_web_routes import router as web_chat_router
app.include_router(web_chat_router)
# 注册群组路由
from api.group_routes import router as group_router
app.include_router(group_router)
# 注册知识图谱路由
from kg_routes import router as kg_router
app.include_router(kg_router)
# 注册游戏路由
from game_routes import router as game_router
app.include_router(game_router)
# 注册日志路由
from log_routes import router as log_router
app.include_router(log_router)
# 注册植物大战僵尸路由
from routes.pvz_routes import router as pvz_router
app.include_router(pvz_router, prefix="/api", tags=["植物大战僵尸"])

# 注册植物大战僵尸多人对战路由
from routes.pvz_multiplayer import router as pvz_multiplayer_router
app.include_router(pvz_multiplayer_router, prefix="/api", tags=["植物大战僵尸多人对战"])

# 注册双人格斗路由
from routes.duel_fighter import router as duel_fighter_router
app.include_router(duel_fighter_router, prefix="/api", tags=["双人格斗"])
# 定义请求体模型
class UserAuth(BaseModel):
    username: str
    password: str

@app.get("/")
def read_root():
    return {"message": "后端服务运行正常！", "status": "success"}

# --- 工具方法 ---

def compute_file_hash(content: bytes) -> str:
    """计算文件的 SHA256 哈希"""
    return hashlib.sha256(content).hexdigest()


async def build_login_response(username: str, request: Request):
    """统一生成登录成功返回，包含 token 与登录记录（新格式）"""
    # 更新最后活动时间
    database.update_last_activity(username)
    
    # 从数据库获取用户信息，包括雪花ID
    db_user = database.get_user(username)
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user_id = db_user.get("id", "")
    
    # 生成 token（新格式：包含用户ID和用户名）
    if user_id:
        # 使用新格式创建token
        access_token = create_token_with_user_info(user_id, username)
        refresh_token = create_refresh_token(data={"user_id": user_id, "username": username})
    else:
        # 向后兼容：如果没有用户ID，使用旧格式
        access_token = create_access_token(data={"sub": username})
        refresh_token = create_refresh_token(data={"sub": username})

    # 记录登录历史
    try:
        client_ip = request.headers.get("X-Forwarded-For")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        user_agent = request.headers.get("User-Agent", "")
        location = request.headers.get("X-Login-Location")
        if not location:
            location = "本地" if client_ip in ("127.0.0.1", "::1", "localhost") else "未知"

        now_ms = int(time.time() * 1000)
        last_login = database.get_user_last_login_record(username)
        if (last_login is None) or (now_ms - last_login >= 24 * 60 * 60 * 1000):
            asyncio.create_task(
                db_async_manager.submit_login_record(
                    username,
                    client_ip,
                    location,
                    user_agent,
                    now_ms
                )
            )
    except Exception as e:
        logger.error(f"记录登录历史失败: {e}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "username": username,
        "user_id": user_id if user_id else None
    }


@app.post("/auth/send-code")
async def send_code(data: EmailSchema, background_tasks: BackgroundTasks):
    # 生成验证码
    db_user = database.get_user(data.email)
    if  db_user:
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    code = email_utils.generate_code()
    # 记录创建时间和过期时间 (5分钟后过期)
    current_time = time.time()
    expires_at = current_time + (5 * 60)  # 5分钟 = 300秒
    verification_codes[data.email] = {
        "code": code,
        "created_at": current_time,
        "expires_at": expires_at
    }
    # 发送邮件 (使用后台任务，不阻塞接口)
    background_tasks.add_task(email_utils.send_verification_email, data.email, code)
    return {"message": "验证码已发送，请在5分钟内使用"}

@app.post("/auth/register")
async def register(user: RegisterSchema):  # <--- 改成 async def
    code_data = verification_codes.get(user.email)
    if not code_data:
        raise HTTPException(status_code=400, detail="请先获取验证码")
    
    if time.time() > code_data["expires_at"]:
        del verification_codes[user.email]
        raise HTTPException(status_code=400, detail="验证码已过期")
    
    if code_data["code"] != user.code:
        raise HTTPException(status_code=400, detail="验证码错误")
    
    # 2. 生成雪花ID (所有系统通用的唯一标识)
    # 重点：为了前端兼容性，用字符串
    user_id = id_generator.next_id() 
    # 3. 创建用户 (加密密码)
    password_strength = evaluate_password_strength(user.password)
    hashed_pw = get_password_hash(user.password)
    
    # 4. Neo4j 存储 (这里是一个同步函数，可以直接调)
    # 如果 database.create_user 很慢，可以考虑放入 threadpool_executor 异步执行
    result = database.create_user(
        user_id=user_id,     # 传入 ID
        username=user.username, 
        password_hash=hashed_pw, 
        email=user.email, 
        password_strength=password_strength
    )
    
    if result == "USERNAME_EXISTS":
        raise HTTPException(status_code=400, detail="用户名已存在")
    if result == "EMAIL_EXISTS":
        raise HTTPException(status_code=400, detail="邮箱已注册")
    
    # 5. MongoDB 存储 (聊天系统副本) - 异步操作
    # 只有 Neo4j 成功了才存 Mongo
    try:
        await create_mongo_user(user_id, user.username, user.email)
    except Exception as e:
        # 极其罕见的情况：Neo4j 成功但 Mongo 失败
        # 实际生产中可能需要发消息队列做补偿，或者手动回滚 Neo4j
        print(f"Mongo create failed: {e}") 
        # 暂时只打印 log，不阻断注册流程，
        # 用户登录聊天时可以再做一个 'lazy check'：如果 Mongo 没号自动补一个
    
    # 6. 清除验证码
    del verification_codes[user.email]
    
    return {"message": "注册成功", "user_id": user_id}


async def create_mongo_user(user_id: str, username: str, email: str):
    """
    在 MongoDB 创建用户副本
    确保聊天系统能直接通过 _id 找到人
    """
    # 假设这里是你的 motor client，如果已在 config/main 初始化，直接 import 过来
    from chat_routes import mongo_client 
    if not mongo_client:
         # 还没连的情况 (fallback)
         from config import MONGO_URI
         client = AsyncIOMotorClient(MONGO_URI)
         db = client[MONGO_DB_NAME]
    else:
         db = mongo_client[MONGO_DB_NAME]
    
    await db.users.insert_one({
        "_id": user_id,       # 重点！Mongo 的 _id 直接使用雪花ID
        "username": username,
        "email": email,
        "avatar": "https://i.pravatar.cc/150?u=" + user_id, # 随机默认头像
        "status": "online",
        "created_at": time.time()
    })


async def sync_mongo_user_profile(user_id: str, profile_data: dict):
    """把 Neo4j 用户资料的关键展示字段同步到 Mongo 聊天用户副本。"""
    if not user_id or db_manager.db is None:
        return

    update = {"updated_at": time.time()}
    for key in ("username", "email", "avatar"):
        value = profile_data.get(key)
        if value is not None:
            update[key] = value

    try:
        await db_manager.db.users.update_one(
            {"_id": str(user_id)},
            {"$set": update}
        )
    except Exception as e:
        logger.warning(f"同步 Mongo 用户副本失败: user_id={user_id}, error={e}")


async def save_profile_update_payload(data: ProfileUpdateSchema, request: Request) -> dict:
    """统一处理个人资料保存，避免两个兼容接口各自维护一份逻辑。"""
    current_username = getattr(request.state, "current_user", None)
    if not current_username:
        raise HTTPException(status_code=401, detail="未认证")

    if data.username != current_username:
        existing = database.get_user(data.username)
        if existing:
            raise HTTPException(status_code=400, detail="该用户名已被占用")

    current_user_id = getattr(request.state, "current_user_id", None)
    if not current_user_id:
        current_user = database.get_user(current_username)
        current_user_id = current_user.get("id") if current_user else None

    success, updated_user_or_msg = await db_async_manager.submit_profile_update(
        current_username, data.dict()
    )
    if not success:
        raise HTTPException(status_code=400, detail=updated_user_or_msg or "保存失败，请稍后重试")

    updated_user = updated_user_or_msg
    if current_user_id:
        await sync_mongo_user_profile(str(current_user_id), updated_user)

    profile_completion = calc_profile_completion(updated_user)
    return {
        "message": "保存成功",
        "username": updated_user.get("username"),
        "email": updated_user.get("email"),
        "job_title": updated_user.get("job_title", ""),
        "website": updated_user.get("website", ""),
        "bio": updated_user.get("bio", ""),
        "avatar": updated_user.get("avatar", ""),
        "profile_completion": profile_completion
    }


@app.post("/auth/forgot-password/send-code")
async def send_forgot_password_code(data: ForgotPasswordSendSchema, background_tasks: BackgroundTasks):
    """发送忘记密码验证码"""
    user = database.get_user(data.username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user_email = (user.get("email") or "").lower()
    if user_email != data.email.lower():
        raise HTTPException(status_code=400, detail="用户名与邮箱不匹配")

    code = email_utils.generate_code()
    # 保存到 Redis，5分钟有效（配置在 redis_utils 中）
    saved = save_forgot_password_code(data.email, code)
    if not saved:
        raise HTTPException(status_code=500, detail="验证码保存失败，请稍后重试")

    background_tasks.add_task(email_utils.send_forgot_password_email, data.email, code)
    return {"message": "验证码已发送，请在5分钟内使用"}


@app.post("/auth/forgot-password/reset")
async def reset_password(data: ForgotPasswordResetSchema):
    """校验验证码后重置密码"""
    # 验证验证码（包含存在性与正确性）
    ok, msg = verify_forgot_password_code(data.email, data.code)
    if not ok:
        raise HTTPException(status_code=400, detail=msg or "验证码校验失败")

    user = database.get_user(data.username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if (user.get("email") or "").lower() != data.email.lower():
        raise HTTPException(status_code=400, detail="用户名与邮箱不匹配")

    new_password_strength = evaluate_password_strength(data.new_password)
    new_password_hash = get_password_hash(data.new_password)
    success = await db_async_manager.submit_password_update(
        data.username,
        new_password_hash,
        new_password_strength
    )
    if not success:
        raise HTTPException(status_code=500, detail="密码重置失败，请稍后再试")

    # 删除验证码
    delete_forgot_password_code(data.email)
    return {"message": "密码重置成功，请使用新密码登录"}


# ==================== 二维码登录相关 API ====================


@app.get("/auth/qr-login-status")
async def get_qr_login_status(request: Request):
    """获取当前登录用户的二维码登录开关状态"""
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")

    enabled = database.get_user_qr_login_status(username)
    return {"qr_login_enabled": enabled}


@app.post("/auth/qr-login/enable")
async def enable_qr_login(request: Request):
    """启用二维码登录"""
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")

    updated = database.set_user_qr_login_status(username, True)
    if not updated:
        raise HTTPException(status_code=500, detail="启用失败，请稍后重试")
    return {"message": "二维码登录已启用"}


@app.post("/auth/qr-login/disable")
async def disable_qr_login(request: Request):
    """关闭二维码登录"""
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")

    updated = database.set_user_qr_login_status(username, False)
    if not updated:
        raise HTTPException(status_code=500, detail="禁用失败，请稍后重试")
    return {"message": "二维码登录已禁用"}


@app.get("/auth/qr/status/{username}")
async def public_qr_status(username: str):
    """登录页用：查询指定用户是否启用二维码登录"""
    enabled = database.get_user_qr_login_status(username)
    return {"qr_login_enabled": enabled}


@app.post("/auth/qr/generate")
async def generate_qr(request: Request):
    """生成二维码会话，返回二维码ID与扫码URL"""
    qr_id = uuid.uuid4().hex
    if not create_qr_session(qr_id):
        raise HTTPException(status_code=500, detail="二维码生成失败，请稍后重试")

    # 构造扫码URL，指向前端 h5.html
    base_url = str(request.base_url).rstrip("/")
    qr_url = f"https://kg-rag-system-frontend.pages.dev/h5.html?qr_id={qr_id}"

    return {
        "qr_id": qr_id,
        "qr_url": qr_url,
        "expires_in": 300
    }


@app.get("/auth/qr/check/{qr_id}")
async def check_qr_status(qr_id: str):
    """登录页轮询：检查二维码会话状态"""
    session = get_qr_session(qr_id)
    if not session:
        return {"status": "expired"}

    status = session.get("status", "pending")
    if status == "confirmed":
        # 取出令牌后删除会话，防止重复使用
        token = session.get("token")
        username = session.get("username")
        delete_qr_session(qr_id)
        return {
            "status": "confirmed",
            "access_token": token,
            "username": username
        }

    return {"status": status}


@app.post("/auth/qr/confirm")
async def confirm_qr_login_api(data: QRConfirmSchema, request: Request):
    """手机端 H5 提交账号密码确认登录"""
    # 检查会话是否存在
    session = get_qr_session(data.qr_id)
    if not session:
        raise HTTPException(status_code=400, detail="二维码不存在或已过期")
    if session.get("status") == "confirmed":
        return {"success": True}

    # 校验用户与密码
    user = database.get_user(data.username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    # 检查是否启用二维码登录
    if not database.get_user_qr_login_status(data.username):
        raise HTTPException(status_code=400, detail="该用户未启用二维码登录")

    # 从数据库获取用户信息，包括雪花ID
    user_id = user.get("id", "")
    
    # 生成 token（新格式：包含用户ID和用户名）
    if user_id:
        # 使用新格式创建token
        access_token = create_token_with_user_info(user_id, data.username)
    else:
        # 向后兼容：如果没有用户ID，使用旧格式
        access_token = create_access_token(data={"sub": data.username})
        
    if not confirm_qr_login(data.qr_id, data.username, access_token):
        raise HTTPException(status_code=500, detail="确认登录失败，请重试")

    # 更新活跃时间 & 登录记录（异步）
    try:
        database.update_last_activity(data.username)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "")
        location = request.headers.get("X-Login-Location") or "扫码端"
        now_ms = int(time.time() * 1000)
        asyncio.create_task(
            db_async_manager.submit_login_record(
                data.username,
                client_ip,
                location,
                user_agent,
                now_ms
            )
        )
    except Exception as e:
        logger.error(f"记录扫码登录历史失败: {e}")

    return {"success": True}

@app.post("/auth/login")
async def login(user: UserAuth, request: Request):
    # 1. 从数据库查用户
    db_user = database.get_user(user.username)
    if not db_user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    
    # 2. 验证密码
    if not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    
    # 3. 如果开启了两步验证，要求上传图片验证
    if db_user.get("twofa_enabled"):
        return {"requires_2fa": True, "username": user.username}
    
    # 4. 正常登录流程
    return await build_login_response(user.username, request)


@app.post("/auth/enable-2fa")
async def enable_twofa(request: Request, file: UploadFile = File(...)):
    """启用两步验证并上传验证图片"""
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只能上传图片文件")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过5MB")

    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    unique_filename = f"{username}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(TWOFA_DIR, unique_filename)

    # 获取旧文件以便清理
    info = database.get_user_2fa_info(username)
    old_filename = info.get("twofa_filename") if info else ""

    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存验证图片失败: {e}")

    file_hash = compute_file_hash(content)
    success = database.set_user_2fa(username, True, unique_filename, file_hash)
    if not success:
        # 回滚文件写入
        try:
            os.remove(file_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="更新2FA状态失败")

    # 清理旧文件
    if old_filename:
        old_path = os.path.join(TWOFA_DIR, old_filename)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    return {"message": "两步验证已启用"}


@app.post("/auth/disable-2fa")
async def disable_twofa(request: Request):
    """关闭两步验证并删除验证图片"""
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")

    info = database.get_user_2fa_info(username)
    if info.get("twofa_filename"):
        old_path = os.path.join(TWOFA_DIR, info["twofa_filename"])
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    if not database.set_user_2fa(username, False, "", ""):
        raise HTTPException(status_code=500, detail="关闭两步验证失败")

    return {"message": "两步验证已关闭"}


@app.post("/auth/verify-2fa")
async def verify_twofa(request: Request, username: str = Form(...), file: UploadFile = File(...)):
    """验证两步验证图片并完成登录"""
    db_user = database.get_user(username)
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not db_user.get("twofa_enabled"):
        raise HTTPException(status_code=400, detail="该用户未启用两步验证")

    stored_hash = db_user.get("twofa_hash") or ""
    stored_filename = db_user.get("twofa_filename") or ""

    # 兼容旧数据：如果哈希缺失但文件存在，尝试从文件补全哈希
    if (not stored_hash) and stored_filename:
        candidate_path = os.path.join(TWOFA_DIR, stored_filename)
        if os.path.exists(candidate_path):
            try:
                with open(candidate_path, "rb") as f:
                    stored_hash = hashlib.sha256(f.read()).hexdigest()
                    print(f"[2FA DEBUG] 补全哈希成功: {stored_filename}, hash={stored_hash[:12]}...")
            except Exception as e:
                print(f"[2FA DEBUG] 读取旧2FA文件失败: {candidate_path}, err={e}")
                stored_hash = ""
        else:
            print(f"[2FA DEBUG] 旧2FA文件不存在: {candidate_path}")

    # 如果依然不完整，要求重新设置
    if not stored_hash or not stored_filename:
        print(f"[2FA DEBUG] 信息不完整: hash={bool(stored_hash)}, filename={bool(stored_filename)}, user={username}")
        raise HTTPException(status_code=400, detail="两步验证信息不完整，请重新设置")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只能上传图片文件")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过5MB")

    upload_hash = compute_file_hash(content)
    if upload_hash != stored_hash:
        print(f"[2FA DEBUG] 哈希不匹配: stored={stored_hash[:12] if stored_hash else 'None'}, upload={upload_hash[:12]}..., user={username}")
        raise HTTPException(status_code=400, detail="验证图片不匹配，请重试")

    # 验证通过，完成登录
    return await build_login_response(username, request)

@app.put("/auth/change-password")
async def change_password(data: ChangePasswordSchema, request: Request):
    """校验旧密码后更新密码（前端已校验强度，这里只存储）"""
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")

    db_user = database.get_user(username)
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not verify_password(data.current_password, db_user["password"]):
        raise HTTPException(status_code=400, detail="当前密码不正确")

    new_password_strength = evaluate_password_strength(data.new_password)
    new_password_hash = get_password_hash(data.new_password)
    success = await db_async_manager.submit_password_update(
        username,
        new_password_hash,
        new_password_strength
    )
    if not success:
        raise HTTPException(status_code=500, detail="密码更新失败，请稍后重试")

    return {"message": "密码已更新，请重新登录"}

@app.get("/auth/login-history")
async def get_login_history(request: Request):
    """获取当前用户最近的登录历史"""
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")

    records = database.get_login_history(username, limit=50)
    return {"records": records}

@app.get("/auth/me")
def get_current_user(request: Request):
    """获取当前登录用户信息"""
    # 从中间件获取当前用户名
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")
    
    # 从数据库获取用户统计信息
    user_stats = database.get_user_stats(username)
    if not user_stats:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    profile_completion = calc_profile_completion(user_stats)
    
    return {
        "username": user_stats.get("username", ""),
        "email": user_stats.get("email", ""),
        "avatar": user_stats.get("avatar", ""),
        "job_title": user_stats.get("job_title", ""),
        "website": user_stats.get("website", ""),
        "bio": user_stats.get("bio", ""),
        "profile_completion": profile_completion,
        "created_at": user_stats.get("created_at"),
        "last_activity": user_stats.get("last_activity"),
        "request_count": user_stats.get("request_count", 0),
        "online_days": user_stats.get("online_days", 0),
        "twofa_enabled": user_stats.get("twofa_enabled", False)
    }


@app.get("/auth/security-rating")
def get_security_rating(request: Request):
    """返回账户安全评级（低/中/高/绝密）"""
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")

    user_stats = database.get_user(username)
    if not user_stats:
        raise HTTPException(status_code=404, detail="用户不存在")

    password_strength = user_stats.get("password_strength", 2) or 2
    twofa_enabled = user_stats.get("twofa_enabled", False) or False
    rating = build_security_rating(password_strength, twofa_enabled)

    return {
        "rating": rating,
        "password_strength": password_strength,
        "twofa_enabled": twofa_enabled
    }

@app.post("/auth/upload-avatar")
async def upload_avatar(request: Request, file: UploadFile = File(...)):
    """上传用户头像"""
    # 从中间件获取当前用户名
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")
    
    # 验证文件类型
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只能上传图片文件")
    
    # 读取文件内容
    content = await file.read()
    
    # 验证文件大小（5MB）
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过5MB")
    
    # 生成唯一文件名：用户名_时间戳_uuid.扩展名
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    unique_filename = f"{username}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{file_ext}"
    
    # 获取旧头像文件名（用于删除）
    user_stats = database.get_user_stats(username)
    old_avatar = user_stats.get("avatar", "") if user_stats else None
    
    # 使用线程池异步写文件并更新数据库
    success = await db_async_manager.submit_avatar_save(
        username=username,
        filename=unique_filename,
        content=content,
        avatar_dir=AVATAR_DIR,
        old_avatar=old_avatar
    )

    if not success:
        raise HTTPException(status_code=500, detail="更新头像信息失败")

    current_user_id = getattr(request.state, "current_user_id", None)
    if not current_user_id:
        db_user = database.get_user(username)
        current_user_id = db_user.get("id") if db_user else None
    if current_user_id:
        await sync_mongo_user_profile(str(current_user_id), {
            "username": username,
            "avatar": unique_filename
        })
    
    return {"avatar": unique_filename, "message": "头像上传成功"}

@app.get("/auth/avatar/{filename}")
async def get_avatar(request: Request, filename: str):
    """获取用户头像（二进制流）"""
    # 从中间件获取当前用户名
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")
    
    # 构建头像文件路径
    file_path = os.path.join(AVATAR_DIR, filename)
    
    # 验证文件是否存在
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="头像文件不存在")
    
    # 返回文件内容
    return FileResponse(file_path, media_type="image/jpeg")

@app.delete("/auth/delete-account")
def delete_account(request: Request):
    """删除用户账户"""
    # 从中间件获取当前用户名
    username = getattr(request.state, "current_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="未认证")
    
    # 获取用户信息（用于删除头像文件）
    user_stats = database.get_user_stats(username)
    avatar = user_stats.get("avatar", "") if user_stats else None
    
    # 删除用户
    success = database.delete_user(username)
    if not success:
        raise HTTPException(status_code=500, detail="删除账户失败")
    
    # 删除用户头像文件
    if avatar:
        avatar_path = os.path.join(AVATAR_DIR, avatar)
        if os.path.exists(avatar_path):
            try:
                os.remove(avatar_path)
            except Exception:
                pass  # 删除失败不影响账户删除
    
    return {"message": "账户已成功删除"}

@app.put("/auth/update-profile")
async def update_profile(data: ProfileUpdateSchema, request: Request):
    """保存更改：更新个人资料"""
    return await save_profile_update_payload(data, request)

@app.post("/auth/save-profile")
async def save_profile(data: ProfileUpdateSchema, request: Request):
    """新接口：保存用户在资料页的编辑信息"""
    return await save_profile_update_payload(data, request)

@app.on_event("startup")
async def startup():
    """统一的启动事件：初始化所有服务和定时任务"""
    
    #  初始化 Mongo 和 Async Redis
    await db_manager.connect()
    
    # 2. 启动音乐热门趋势定时任务（Kafka消费）
    try:
        from task_manager import setup_music_trending_scheduler, start_scheduler
        
        # 设置音乐热门趋势定时任务
        setup_music_trending_scheduler()
        
        # 启动调度器
        start_scheduler()
        
        logging.info("✅ 音乐热门趋势定时任务已启动（每分钟消费Kafka事件）")
    except Exception as e:
        logging.warning(f"⚠️ 启动热门趋势定时任务失败（Kafka未连接或APScheduler未安装？）: {e}")
    
    # 3. 启动音乐热门趋势调度器（带排名快照推送）
    try:
        from music_trending import start_trending_scheduler
        
        # 启动调度器（每1分钟衰减热度 + 每5分钟全量更新并推送排名快照）
        start_trending_scheduler()
        
        logging.info("✅ 音乐热门趋势调度器已启动（带排名快照，每5分钟更新）")
    except Exception as e:
        logging.warning(f"⚠️ 启动音乐热门趋势调度器失败: {e}")
    
    # 4. 启动布隆过滤器Warmup（后台异步执行）
    try:
        from bloom_utils import warmup_all_bloom_filters_async
        warmup_all_bloom_filters_async()
        
        # 结构化日志输出 - Warmup启动成功
        logger.info("📊 [MONITOR] Bloom Filter Warmup 启动状态: SUCCESS")
        logger.info("   - 执行模式: 后台异步执行")
        logger.info("   - 布隆过滤器: document_bloom, cache_keys_bloom")
        logger.info("   - Warmup完成前: 业务请求将使用降级策略（直接查数据库）")
        
    except ImportError as e:
        # 导入失败（缺少依赖）
        logger.error("❌ [MONITOR] Bloom Filter Warmup 启动失败: IMPORT_ERROR")
        logger.error(f"   - 错误详情: {e}")
        logger.error("   - 影响: 文档去重和缓存穿透防护功能不可用")
        logger.warning("⚠️  应用仍可正常运行，但性能可能受影响")
        
    except Exception as e:
        # 其他异常
        logger.error("❌ [MONITOR] Bloom Filter Warmup 启动失败: UNKNOWN_ERROR")
        logger.error(f"   - 错误详情: {type(e).__name__}: {e}")
        logger.error("   - 导入堆栈:", exc_info=True)
        logger.warning("⚠️  Warmup未启动，但应用仍可正常运行（将使用降级策略）")
    
    # 5. 启动 Spark 批处理定时任务调度器
    try:
        from spark_scheduler import init_spark_scheduler
        
        # 初始化并启动 Spark Scheduler
        spark_scheduler = init_spark_scheduler()
        
        logging.info("✅ Spark 批处理定时任务调度器已启动")
        logging.info("📅 已配置的 Spark 定时任务：")
        logging.info("   - 每日统计作业: 每天 02:00")
        logging.info("   - 每周统计作业: 每周一 02:00")
        logging.info("   - 每月统计作业: 每月1日 02:00")
        logging.info("   - 用户偏好分析: 每天 03:00")
        
    except ImportError as e:
        # 导入失败（缺少依赖）
        logger.error("❌ [MONITOR] Spark Scheduler 启动失败: IMPORT_ERROR")
        logger.error(f"   - 错误详情: {e}")
        logger.error("   - 影响: Spark 批处理功能不可用（日榜/周榜/月榜/用户偏好分析）")
        logger.warning("⚠️  应用仍可正常运行，但批处理功能将不可用")
        
    except Exception as e:
        # 其他异常
        logger.error("❌ [MONITOR] Spark Scheduler 启动失败: UNKNOWN_ERROR")
        logger.error(f"   - 错误详情: {type(e).__name__}: {e}")
        logger.error("   - 导入堆栈:", exc_info=True)
        logger.warning("⚠️  Spark Scheduler未启动，但应用仍可正常运行")

@app.on_event("shutdown")
async def shutdown():
    # 释放 Mongo 和 Async Redis 连接
    await db_manager.close()
    
    # 关闭 Spark 批处理定时任务调度器
    try:
        from spark_scheduler import shutdown_spark_scheduler
        shutdown_spark_scheduler()
        logging.info("✅ Spark Scheduler 已关闭")
    except ImportError:
        pass  # 未安装 PySpark,忽略
    except Exception as e:
        logging.error(f"❌ 关闭 Spark Scheduler 失败: {e}")

if __name__ == "__main__":
    import uvicorn
    # 启动服务，端口8000
    uvicorn.run(app, host="0.0.0.0", port=8000)





# 这个系统实现了：

# ✅ 分布式唯一ID生成（雪花算法）
# ✅ 完整的认证体系（密码、2FA、二维码登录）
# ✅ 安全机制（密码强度评估、登录历史、限流）
# ✅ 24小时活动窗口（无感续期token）
# ✅ 双数据库架构（Neo4j + MongoDB）
# ✅ 异步性能优化（线程池处理慢操作）
