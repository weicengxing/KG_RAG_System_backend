"""
认证依赖模块
提供 FastAPI 依赖注入函数，避免循环导入
"""

from fastapi import Request, HTTPException


async def get_current_user(request: Request) -> str:
    """获取当前认证用户

    Args:
        request: FastAPI请求对象

    Returns:
        str: 当前用户名

    Raises:
        HTTPException: 如果用户未认证
    """
    if not hasattr(request.state, "current_user"):
        raise HTTPException(status_code=401, detail="未认证")
    return request.state.current_user
