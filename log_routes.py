"""
日志管理路由
提供日志查询和管理功能，使用Elasticsearch
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from auth_deps import get_current_user
from elasticsearch_utils import es_manager

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/logs", tags=["日志"])


@router.get("/search")
async def search_logs(
    query: Optional[str] = Query(None, description="搜索关键词"),
    level: Optional[str] = Query(None, description="日志级别：INFO/WARNING/ERROR"),
    user_id: Optional[str] = Query(None, description="用户ID"),
    module: Optional[str] = Query(None, description="模块名称"),
    trace_id: Optional[str] = Query(None, description="TraceID"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    size: int = Query(50, ge=1, le=100, description="返回数量"),
    from_: int = Query(0, ge=0, description="偏移量"),
    sort_by: str = Query("timestamp", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    current_user: str = Depends(get_current_user)
):
    """搜索系统日志"""
    try:
        result = es_manager.search_logs(
            query=query or "",
            level=level,
            user_id=user_id,
            module=module,
            trace_id=trace_id,
            start_time=start_time,
            end_time=end_time,
            size=size,
            from_=from_,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"搜索日志失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索日志失败: {str(e)}")


@router.get("/stats")
async def get_log_stats(
    current_user: str = Depends(get_current_user)
):
    """获取日志统计信息"""
    try:
        # 这里可以添加更多统计信息
        return {
            "success": True,
            "message": "日志统计功能开发中",
            "hint": "可按日志级别、模块、时间范围等维度统计"
        }
    except Exception as e:
        logger.error(f"获取日志统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取日志统计失败")


@router.get("/modules")
async def get_log_modules(
    current_user: str = Depends(get_current_user)
):
    """获取日志模块列表（用于筛选）"""
    try:
        # 这里可以从ES聚合查询获取模块列表
        common_modules = [
            "music_routes",
            "kg_routes",
            "chat_routes",
            "auth_routes",
            "elasticsearch_utils",
            "redis_utils",
            "trace_utils",
            "middleware"
        ]
        return {
            "success": True,
            "modules": common_modules
        }
    except Exception as e:
        logger.error(f"获取日志模块列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取日志模块列表失败")