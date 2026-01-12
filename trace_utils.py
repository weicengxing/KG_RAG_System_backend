"""
TraceID 追踪工具模块
使用雪花算法生成全局唯一的TraceID，用于全链路请求追踪
"""

import contextvars
from typing import Optional
from snowflake import id_generator

# Context Variable 用于在异步环境中存储TraceID
# 这是Python 3.7+推荐的上下文变量管理方式
trace_id_context: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


def generate_trace_id() -> str:
    """
    生成新的TraceID
    使用雪花算法生成，保证全局唯一且趋势递增
    
    Returns:
        str: 64位雪花ID的字符串形式
    """
    return id_generator.next_id()


def get_trace_id() -> str:
    """
    获取当前上下文的TraceID
    
    Returns:
        str: 当前TraceID，如果不存在返回空字符串
    """
    return trace_id_context.get()


def set_trace_id(trace_id: str) -> contextvars.Token:
    """
    设置当前上下文的TraceID
    
    Args:
        trace_id: 要设置的TraceID
        
    Returns:
        contextvars.Token: 上下文变量token，用于恢复之前的状态
    """
    return trace_id_context.set(trace_id)


def clear_trace_id(token: contextvars.Token) -> None:
    """
    清除当前上下文的TraceID
    
    Args:
        token: 由set_trace_id返回的token
    """
    trace_id_context.reset(token)


def get_or_generate_trace_id(provided_trace_id: Optional[str] = None) -> str:
    """
    获取或生成TraceID
    如果提供了trace_id则使用，否则生成新的
    
    Args:
        provided_trace_id: 外部传入的TraceID（可选）
        
    Returns:
        str: TraceID
    """
    if provided_trace_id:
        return provided_trace_id
    return generate_trace_id()


class TraceContext:
    """
    TraceID 上下文管理器
    用于在特定代码块中设置和自动清理TraceID
    """
    
    def __init__(self, trace_id: str):
        """
        初始化TraceID上下文
        
        Args:
            trace_id: 要设置的TraceID
        """
        self.trace_id = trace_id
        self.token: Optional[contextvars.Token] = None
    
    def __enter__(self):
        """进入上下文时设置TraceID"""
        self.token = set_trace_id(self.trace_id)
        return self.trace_id
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时清理TraceID"""
        if self.token is not None:
            clear_trace_id(self.token)
        return False


def get_log_prefix() -> str:
    """
    获取带TraceID的日志前缀
    
    Returns:
        str: 日志前缀，格式如 [TRACE_ID:1234567890]
    """
    trace_id = get_trace_id()
    if trace_id:
        return f"[TRACE_ID:{trace_id}]"
    return ""