"""
Spark 批处理定时任务调度器
使用 APScheduler 自动定时执行 Spark 作业
"""

import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from spark_music_analytics import (
    run_daily_stats,
    run_weekly_stats,
    run_monthly_stats,
    run_user_preference_analysis
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Spark Scheduler 类 ====================

class SparkScheduler:
    """Spark 批处理调度器"""
    
    def __init__(self):
        """初始化调度器"""
        self.scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        self.scheduler.add_listener(
            self._job_listener,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
        logger.info("✅ Spark Scheduler 初始化成功")
    
    def _job_listener(self, event):
        """任务执行监听器

        Args:
            event: 任务事件
        """
        if event.exception:
            logger.error(f"❌ 任务执行失败: job_id={event.job_id}, exception={event.exception}")
        else:
            job = self.scheduler.get_job(event.job_id)
            if job:
                logger.info(f"✅ 任务执行成功: job_id={event.job_id}, name={job.name}, next_run={job.next_run_time}")
    
    def _run_daily_stats_task(self):
        """执行每日统计任务的包装函数"""
        try:
            # 获取昨天的日期
            yesterday = datetime.now().strftime('%Y-%m-%d')
            logger.info(f"🚀 [DailyStatsTask] 开始执行: date={yesterday}")
            
            run_daily_stats(yesterday)
            
            logger.info(f"✅ [DailyStatsTask] 执行完成: date={yesterday}")
            
        except Exception as e:
            logger.error(f"❌ [DailyStatsTask] 执行失败: {e}")
            raise
    
    def _run_weekly_stats_task(self):
        """执行每周统计任务的包装函数"""
        try:
            # 获取上周的周数（ISO 周格式）
            from datetime import timedelta
            today = datetime.now()
            last_monday = today - timedelta(days=today.weekday(), weeks=1)
            year, week_num, _ = last_monday.isocalendar()
            week = f"{year}-W{week_num:02d}"
            
            logger.info(f"🚀 [WeeklyStatsTask] 开始执行: week={week}")
            
            run_weekly_stats(week)
            
            logger.info(f"✅ [WeeklyStatsTask] 执行完成: week={week}")
            
        except Exception as e:
            logger.error(f"❌ [WeeklyStatsTask] 执行失败: {e}")
            raise
    
    def _run_monthly_stats_task(self):
        """执行每月统计任务的包装函数"""
        try:
            # 获取上个月的月份
            from datetime import timedelta
            today = datetime.now()
            if today.month == 1:
                last_month_date = today.replace(year=today.year - 1, month=12)
            else:
                last_month_date = today.replace(month=today.month - 1)
            month = last_month_date.strftime('%Y-%m')
            
            logger.info(f"🚀 [MonthlyStatsTask] 开始执行: month={month}")
            
            run_monthly_stats(month)
            
            logger.info(f"✅ [MonthlyStatsTask] 执行完成: month={month}")
            
        except Exception as e:
            logger.error(f"❌ [MonthlyStatsTask] 执行失败: {e}")
            raise
    
    def _run_user_preference_task(self):
        """执行用户偏好分析任务的包装函数"""
        try:
            # 分析昨天的用户偏好
            yesterday = datetime.now().strftime('%Y-%m-%d')
            logger.info(f"🚀 [UserPreferenceTask] 开始执行: date={yesterday}")
            
            run_user_preference_analysis(yesterday)
            
            logger.info(f"✅ [UserPreferenceTask] 执行完成: date={yesterday}")
            
        except Exception as e:
            logger.error(f"❌ [UserPreferenceTask] 执行失败: {e}")
            raise
    
    def add_jobs(self):
        """添加所有定时任务"""
        try:
            # 1. 每日统计任务：每天凌晨 2:00 执行
            self.scheduler.add_job(
                self._run_daily_stats_task,
                CronTrigger(hour=2, minute=0),
                id='daily_stats_task',
                name='每日统计作业',
                max_instances=1,
                replace_existing=True,
                misfire_grace_time=3600  # 允许 1 小时的延迟执行
            )
            logger.info("✅ 添加每日统计任务: 每天 02:00")
            
            # 2. 每周统计任务：每周一凌晨 2:00 执行
            self.scheduler.add_job(
                self._run_weekly_stats_task,
                CronTrigger(day_of_week='mon', hour=2, minute=0),
                id='weekly_stats_task',
                name='每周统计作业',
                max_instances=1,
                replace_existing=True,
                misfire_grace_time=3600  # 允许 1 小时的延迟执行
            )
            logger.info("✅ 添加每周统计任务: 每周一 02:00")
            
            # 3. 每月统计任务：每月1日凌晨 2:00 执行
            self.scheduler.add_job(
                self._run_monthly_stats_task,
                CronTrigger(day=1, hour=2, minute=0),
                id='monthly_stats_task',
                name='每月统计作业',
                max_instances=1,
                replace_existing=True,
                misfire_grace_time=3600  # 允许 1 小时的延迟执行
            )
            logger.info("✅ 添加每月统计任务: 每月1日 02:00")
            
            # 4. 用户偏好分析任务：每天凌晨 3:00 执行
            self.scheduler.add_job(
                self._run_user_preference_task,
                CronTrigger(hour=3, minute=0),
                id='user_preference_task',
                name='用户偏好分析作业',
                max_instances=1,
                replace_existing=True,
                misfire_grace_time=3600  # 允许 1 小时的延迟执行
            )
            logger.info("✅ 添加用户偏好分析任务: 每天 03:00")
            
            logger.info("✅ 所有定时任务添加成功")
            
        except Exception as e:
            logger.error(f"❌ 添加定时任务失败: {e}")
            raise
    
    def start(self):
        """启动调度器"""
        try:
            self.scheduler.start()
            logger.info("✅ Spark Scheduler 启动成功")
            logger.info("📅 已配置的定时任务：")
            
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else '无'
                logger.info(f"   - {job.name}: {next_run}")
                
        except Exception as e:
            logger.error(f"❌ 启动 Spark Scheduler 失败: {e}")
            raise
    
    def shutdown(self):
        """关闭调度器"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                logger.info("✅ Spark Scheduler 已关闭")
        except Exception as e:
            logger.error(f"❌ 关闭 Spark Scheduler 失败: {e}")
    
    def get_jobs(self):
        """获取所有任务信息

        Returns:
            list: 任务信息列表
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs


# ==================== 全局调度器实例 ====================

spark_scheduler = None


def init_spark_scheduler():
    """初始化 Spark 调度器（全局单例）"""
    global spark_scheduler
    
    if spark_scheduler is None:
        spark_scheduler = SparkScheduler()
        spark_scheduler.add_jobs()
        spark_scheduler.start()
    
    return spark_scheduler


def get_spark_scheduler():
    """获取 Spark 调度器实例

    Returns:
        SparkScheduler: 调度器实例
    """
    return spark_scheduler


def shutdown_spark_scheduler():
    """关闭 Spark 调度器"""
    global spark_scheduler
    
    if spark_scheduler:
        spark_scheduler.shutdown()
        spark_scheduler = None


if __name__ == "__main__":
    """测试运行调度器"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 初始化调度器
        scheduler = SparkScheduler()
        scheduler.add_jobs()
        scheduler.start()
        
        logger.info("🎯 调度器已启动，按 Ctrl+C 退出...")
        
        # 持续运行
        import time
        while True:
            time.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("👋 收到退出信号，关闭调度器...")
        scheduler.shutdown()
    except Exception as e:
        logger.error(f"❌ 调度器运行失败: {e}")
        scheduler.shutdown()
