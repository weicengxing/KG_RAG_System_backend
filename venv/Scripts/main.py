from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from utils import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token, decode_token_with_exp
import database
import email_utils # 引入刚才写的
from datetime import datetime, timedelta
import time
from rate_limiter import check_rate_limit, is_rate_limiter_available

app = FastAPI()
verification_codes = {}  # 格式: {email: {"code": "123456", "created_at": timestamp, "expires_at": timestamp}}

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
    # 不需要认证的路径
    public_paths = ["/", "/auth/", "/docs", "/openapi.json", "/redoc"]

    # 检查是否是公开路径
    path = request.url.path
    is_public = any(path == p or path.startswith(p) for p in public_paths)

    if not is_public:
        # 优先从 Authorization header 获取 token
        auth_header = request.headers.get("Authorization")
        token = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            # 备用：从 query 参数获取 token（用于 SSE 等不支持自定义 header 的场景）
            token = request.query_params.get("token")

        if not token:
            return JSONResponse(status_code=401, content={"detail": "未提供认证令牌"})

        try:
            # 使用新的decode函数区分过期和无效
            payload, is_expired, error_msg = decode_token_with_exp(token)
            
            if payload is None:
                # Token完全无效，无法解码
                return JSONResponse(status_code=401, content={"detail": error_msg or "认证失败"})
            
            username = payload.get("sub")
            if not username:
                return JSONResponse(status_code=401, content={"detail": "Token中缺少用户信息"})
            
            # 存储用户信息到request.state
            request.state.current_user = username
            request.state.token_expired = is_expired
            request.state.new_token = None
            
            # 认证成功，更新用户的最后活动时间
            database.update_last_activity(username)
            
            # 如果token已过期，检查是否在24小时活动窗口内
            if is_expired:
                # 从数据库查询用户的last_activity
                db_user = database.get_user(username)
                if not db_user:
                    return JSONResponse(status_code=401, content={"detail": "用户不存在"})
                
                last_activity = db_user.get("last_activity")
                if last_activity is None:
                    # 如果没有last_activity，默认拒绝访问，强制重新登录
                    return JSONResponse(status_code=401, content={"detail": "Token已过期，请重新登录"})
                
                # 计算时间差（last_activity通常是毫秒时间戳）
                current_time = time.time() * 1000  # 转换为毫秒
                time_diff_ms = current_time - last_activity
                time_diff_hours = time_diff_ms / (1000 * 60 * 60)
                
                # 如果超过24小时，返回401并要求重新登录
                if time_diff_hours > 24:
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
                
        except Exception as e:
            # 记录错误详情以便调试
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"JWT 认证失败: {e}, path: {path}")
            return JSONResponse(status_code=401, content={"detail": "认证失败"})

    response = await call_next(request)
    
    # 如果有新token，添加到响应header
    if hasattr(request.state, "new_token") and request.state.new_token:
        response.headers["X-New-Token"] = request.state.new_token
    
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
if __name__ == "__main__":
    import uvicorn
    # 启动服务，端口8000
    uvicorn.run(app, host="0.0.0.0", port=8000)