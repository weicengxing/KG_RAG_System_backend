"""
认证依赖模块
提供 FastAPI 依赖注入函数
"""
from fastapi import Request, HTTPException, Query, status
# 确保从你的 utils 文件导入 token 解码函数
from utils import decode_token_with_exp 

async def get_current_user(request: Request) -> str:
    """
    普通接口使用的依赖：
    从 Middleware 已经处理好的 request.state 中获取用户信息。
    """
    # 检查 request.state 是否有 current_user
    if not hasattr(request.state, "current_user") or not request.state.current_user:
        raise HTTPException(status_code=401, detail="未认证")
    return request.state.current_user

async def get_current_user_from_query(
    token: str = Query(..., description="SSE 专用 Token 参数")
) -> str:
    """
    SSE 专用认证依赖：
    直接从 URL query string (?token=...) 获取并验证 token。
    不依赖 Middleware 的 request.state，防止 SSE 长连接中的状态丢失或中间件逻辑冲突。
    """
    if not token:
        raise HTTPException(status_code=401, detail="未提供 Token")

    try:
        # 调用 utils 中的解码函数
        payload, is_expired, error_msg = decode_token_with_exp(token)
        
        if payload is None:
            raise HTTPException(status_code=401, detail=error_msg or "无效的 Token")
            
        if is_expired:
            # SSE 连接建立时如果 Token 已过期，直接拒绝
            # 注意：SSE 很难在流传输过程中刷新 Token，通常要求建立连接时 Token 有效
            raise HTTPException(status_code=401, detail="Token 已过期")
            
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Token 缺少用户信息")
            
        return username
        
    except Exception as e:
        print(f"[Auth Deps] SSE Token 验证失败: {e}")
        raise HTTPException(status_code=401, detail="认证失败")