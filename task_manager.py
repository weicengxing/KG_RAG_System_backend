"""
任务管理器
使用 Redis 存储任务状态，支持 SSE 推送进度
"""

import json
import time
import logging
from typing import Optional, Dict, Any
from redis import Redis

# 从 config.py 导入 Redis 配置
from config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB

# 配置日志
logger = logging.getLogger(__name__)

class TaskManager:
    """任务状态管理器"""
    
    def __init__(self):
        """初始化 Redis 连接"""
        if REDIS_PASSWORD:
            self.redis = Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                db=REDIS_DB,
                decode_responses=True
            )
        else:
            self.redis = Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True
            )
    
    def create_task(self, task_id: str, user_id: str, task_type: str = "kb_build") -> Dict[str, Any]:
        """
        创建新任务
        
        Args:
            task_id: 任务唯一标识
            user_id: 用户ID
            task_type: 任务类型 (kb_build, doc_parse 等)
        
        Returns:
            任务信息字典
        """
        task_info = {
            "task_id": task_id,
            "user_id": user_id,
            "task_type": task_type,
            "status": "processing",  # processing, completed, failed
            "progress": 0,
            "stage": "initialized",
            "error_message": None,
            "created_at": time.time(),
            "updated_at": time.time(),
            "result": None
        }
        
        # 保存到 Redis，设置 2 小时过期
        self.redis.setex(f"task:{task_id}", 7200, json.dumps(task_info))
        
        return task_info
    
    def update_progress(
        self,
        task_id: str,
        progress: int,
        stage: str = "",
        message: str = ""
    ):
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度百分比 (0-100)
            stage: 当前处理阶段
            message: 进度描述消息
        """
        # 获取现有任务信息
        task_data = self.redis.get(f"task:{task_id}")
        if not task_data:
            return None
        
        task_info = json.loads(task_data)
        
        # 更新进度信息
        task_info["progress"] = progress
        task_info["updated_at"] = time.time()
        
        if stage:
            task_info["stage"] = stage
        if message:
            task_info["message"] = message
        
        # 保存回 Redis
        self.redis.setex(f"task:{task_id}", 7200, json.dumps(task_info))
        
        return task_info
    
    def complete_task(self, task_id: str, result: Dict[str, Any]):
        """
        标记任务为完成状态
        
        Args:
            task_id: 任务ID
            result: 任务结果数据
        """
        # 获取现有任务信息
        task_data = self.redis.get(f"task:{task_id}")
        if not task_data:
            return None
        
        task_info = json.loads(task_data)
        
        # 更新为完成状态
        task_info["status"] = "completed"
        task_info["progress"] = 100
        task_info["updated_at"] = time.time()
        task_info["result"] = result
        task_info["stage"] = "completed"
        
        # 保存回 Redis，延长过期时间到 24 小时
        self.redis.setex(f"task:{task_id}", 86400, json.dumps(task_info))
        
        return task_info
    
    def fail_task(self, task_id: str, error_message: str):
        """
        标记任务为失败状态
        
        Args:
            task_id: 任务ID
            error_message: 错误信息
        """
        # 获取现有任务信息
        task_data = self.redis.get(f"task:{task_id}")
        if not task_data:
            return None
        
        task_info = json.loads(task_data)
        
        # 更新为失败状态
        task_info["status"] = "failed"
        task_info["updated_at"] = time.time()
        task_info["error_message"] = error_message
        task_info["stage"] = "failed"
        
        # 保存回 Redis
        self.redis.setex(f"task:{task_id}", 7200, json.dumps(task_info))
        
        return task_info
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
        
        Returns:
            任务信息字典，如果任务不存在返回 None
        """
        task_data = self.redis.get(f"task:{task_id}")
        if task_data:
            return json.loads(task_data)
        return None
    
    def delete_task(self, task_id: str):
        """
        删除任务
        
        Args:
            task_id: 任务ID
        """
        self.redis.delete(f"task:{task_id}")
    
    def get_user_tasks(self, user_id: str, limit: int = 10) -> list:
        """
        获取用户的任务列表
        
        Args:
            user_id: 用户ID
            limit: 返回数量限制
        
        Returns:
            任务列表，按创建时间倒序
        """
        # 注意：这个方法需要扫描所有 task:* 键，在生产环境建议使用用户任务索引
        # 这里简单实现，如果你有大量任务，建议优化
        tasks = []
        
        # 这里使用 SCAN 遍历所有任务（实际生产中建议维护一个 user_tasks:{user_id} 的有序集合）
        for key in self.redis.scan_iter(match="task:*"):
            task_data = self.redis.get(key)
            if task_data:
                task_info = json.loads(task_data)
                if task_info.get("user_id") == user_id:
                    tasks.append(task_info)
        
        # 按创建时间倒序排序
        tasks.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        
        return tasks[:limit]


# 全局实例
task_manager = TaskManager()
