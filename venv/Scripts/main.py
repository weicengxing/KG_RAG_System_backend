from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from utils import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token, decode_token_with_exp
import database
import email_utils # 引入刚才写的
from datetime import datetime, timedelta
import time
import os
import uuid
import shutil
from rate_limiter import check_rate_limit, is_rate_limiter_available
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jwt_auth")

app = FastAPI()
verification_codes = {}  # 格式: {email: {"code": "123456", "created_at": timestamp, "expires_at": timestamp}}

# 头像存储目录 - 改为存储在assets目录下
# 计算相对于项目根目录的绝对路径
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
AVATAR_DIR = os.path.join(project_root, "assets", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

print(f"[AVATAR DEBUG] 头像存储目录: {AVATAR_DIR}")

# 挂载静态文件目录，用于提供头像访问
app.mount("/avatar", StaticFiles(directory=AVATAR_DIR), name="avatar")

class EmailSchema(BaseModel):
    email: EmailStr

class RegisterSchema(BaseModel):
    email: EmailStr
    code: str
    password: str
    username: str # 依然保留用户名作为昵称

class LoginSchema(BaseModel):
    username: str # 登录还是用用户名方便，或者你可以改成用邮箱登录

# CORS 配置保持不变...
origins = ["http://localhost:5173", "http://localhost:8080"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
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
    # 不需要认证的 auth 路径
    public_auth_paths = ["/auth/login", "/auth/register", "/auth/send-code"]

    # 检查是否是公开路径
    path = request.url.path
    is_public = (
        any(path == p or (p != "/" and path.startswith(p)) for p in public_paths) or
        path in public_auth_paths
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

        username = payload.get("sub")
        if not username:
            print(f"[JWT DEBUG] ❌ Token中缺少用户信息")
            return JSONResponse(status_code=401, content={"detail": "Token中缺少用户信息"})

        print(f"[JWT DEBUG] ✅ Token有效，用户: {username}")

        # 存储用户信息到request.state
        request.state.current_user = username
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

# 定义请求体模型
class UserAuth(BaseModel):
    username: str
    password: str

@app.get("/")
def read_root():
    return {"message": "后端服务运行正常！", "status": "success"}

# --- 新增 API ---

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
def register(user: RegisterSchema):
    # 1. 校验验证码是否存在
    code_data = verification_codes.get(user.email)
    if not code_data:
        raise HTTPException(status_code=400, detail="请先获取验证码")
    
    # 2. 校验验证码是否过期
    current_time = time.time()
    if current_time > code_data["expires_at"]:
        # 过期后删除该验证码
        del verification_codes[user.email]
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
    
    # 3. 校验验证码是否正确
    if code_data["code"] != user.code:
        raise HTTPException(status_code=400, detail="验证码错误")
    
    # 4. 校验是否已注册
    if database.get_user(user.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
        
    # 5. 创建用户 (加密密码)
    hashed_pw = get_password_hash(user.password)
    database.create_user(user.username, hashed_pw, user.email)
    
    # 6. 注册成功后清除验证码
    del verification_codes[user.email]
    
    return {"message": "注册成功"}

@app.post("/auth/login")
def login(user: UserAuth):
    # 1. 从数据库查用户
    db_user = database.get_user(user.username)
    if not db_user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    
    # 2. 验证密码
    if not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    
    # 3. 更新用户的最后活动时间
    database.update_last_activity(user.username)
    
    # 4. 生成 Access Token 和 Refresh Token
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "username": user.username
    }

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
    
    return {
        "username": user_stats.get("username", ""),
        "email": user_stats.get("email", ""),
        "avatar": user_stats.get("avatar", ""),
        "created_at": user_stats.get("created_at"),
        "last_activity": user_stats.get("last_activity"),
        "request_count": user_stats.get("request_count", 0),
        "online_days": user_stats.get("online_days", 0)
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
    
    # 保存头像文件
    file_path = os.path.join(AVATAR_DIR, unique_filename)
    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存头像失败: {str(e)}")
    
    # 删除旧头像
    if old_avatar:
        old_file_path = os.path.join(AVATAR_DIR, old_avatar)
        if os.path.exists(old_file_path):
            try:
                os.remove(old_file_path)
            except Exception:
                pass  # 删除失败不影响新头像保存
    
    # 更新数据库
    success = database.update_user_avatar(username, unique_filename)
    if not success:
        # 如果数据库更新失败，删除已保存的文件
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="更新头像信息失败")
    
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

if __name__ == "__main__":
    import uvicorn
    # 启动服务，端口8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
