"""
TraceID 追踪中间件
为每个HTTP请求自动生成或提取TraceID，并在整个请求生命周期中跟踪
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging
from trace_utils import (
    get_or_generate_trace_id,
    set_trace_id,
    clear_trace_id
)

logger = logging.getLogger("trace_middleware")


class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    TraceID 中间件
    
    功能：
    1. 从请求头提取X-Trace-ID，如果不存在则生成新的
    2. 将TraceID存储到request.state供全局访问
    3. 将TraceID注入到context变量供异步任务使用
    4. 在响应头返回X-Trace-ID
    """
    
    async def dispatch(self, request: Request, call_next):
        # 1. 从请求头提取或生成TraceID
        trace_id = request.headers.get("X-Trace-ID")
        trace_id = get_or_generate_trace_id(trace_id)
        
        # 2. 存储到request.state供路由处理函数使用
        request.state.trace_id = trace_id
        
        # 3. 设置到上下文变量供异步使用
        token = set_trace_id(trace_id)
        
        try:
            # 4. 打印请求开始日志
            logger.info(f"{self._get_log_trace(trace_id)} 请求开始: {request.method} {request.url.path}")
            
            # 5. 处理请求
            response: Response = await call_next(request)
            
            # 6. 在响应头添加TraceID
            response.headers["X-Trace-ID"] = trace_id
            
            # 7. 打印请求结束日志
            logger.info(f"{self._get_log_trace(trace_id)} 请求完成: {request.method} {request.url.path} - {response.status_code}")
            
            return response
            
        except Exception as e:
            # 异常情况下也要记录日志
            logger.error(f"{self._get_log_trace(trace_id)} 请求异常: {request.method} {request.url.path} - {str(e)}")
            raise
            
        finally:
            # 8. 清理上下文变量
            clear_trace_id(token)
    
    def _get_log_trace(self, trace_id: str) -> str:
        """获取带TraceID的日志前缀"""
        return f"[TRACE_ID:{trace_id}]"