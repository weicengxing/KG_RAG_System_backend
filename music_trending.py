"""
音乐热门趋势计算模块（优化版）
基于播放量、独立用户数和时间衰减计算实时热度
"""

import logging
import math
import time
from typing import List, Dict

from redis_utils import (
    redis_client,
    get_music_rankings,
    update_trending_hotness,
    get_song_last_play_time,
    get_song_unique_user_count,
    MUSIC_TRENDING_PREFIX,
    push_rank_snapshot_to_queue
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 热度计算参数
TRENDING_TOP_N = 100  # 计算 Top 100 的热度
TIME_DECAY_HOURS = 24  # 24 小时衰减周期
DECAY_FACTOR = 0.5  # 衰减因子

# 权重配置
UV_WEIGHT = 0.7  # 独立用户数权重
PV_WEIGHT = 0.3  # 播放量权重


def calculate_hotness_optimized(song_id: int) -> float:
    """计算歌曲热度分数（优化版算法 - 多时间窗口加权）

    优化后的算法：
    热度 = (独立用户数 × UV权重 + sqrt(加权播放量) × PV权重) × 时间衰减因子
    
    播放量加权计算：
    - 今日播放量权重：50%
    - 本周播放量权重：30%
    - 本月播放量权重：20%

    优点：
    1. 避免scan操作，直接从Redis获取最后播放时间和独立用户数
    2. 使用多时间窗口加权，反映歌曲的真实热度趋势
    3. 使用sqrt压缩播放量，避免大号垄断
    4. UV权重高于PV权重，更关注推广度
    5. 时间衰减体现时效性

    Args:
        song_id: 歌曲ID

    Returns:
        float: 热度分数
    """
    try:
        # 1. 获取多时间窗口的播放量（方案1修复）
        daily_play_count = 0
        weekly_play_count = 0
        monthly_play_count = 0
        
        if redis_client:
            # 今日播放量
            daily_key = f"music:play_count:daily:{time.strftime('%Y%m%d')}"
            daily_score = redis_client.zscore(daily_key, str(song_id))
            daily_play_count = int(daily_score) if daily_score else 0
            
            # 本周播放量
            weekly_key = f"music:play_count:weekly:{time.strftime('%Y%W')}"
            weekly_score = redis_client.zscore(weekly_key, str(song_id))
            weekly_play_count = int(weekly_score) if weekly_score else 0
            
            # 本月播放量
            monthly_key = f"music:play_count:monthly:{time.strftime('%Y%m')}"
            monthly_score = redis_client.zscore(monthly_key, str(song_id))
            monthly_play_count = int(monthly_score) if monthly_score else 0
        
        # 2. 加权计算播放量（今日50% + 本周30% + 本月20%）
        weighted_play_count = daily_play_count * 0.5 + weekly_play_count * 0.3 + monthly_play_count * 0.2

        # 3. 获取独立用户数
        unique_user_count = get_song_unique_user_count(song_id)

        # 4. 获取最后播放时间
        last_play_time = get_song_last_play_time(song_id)

        # 如果没有播放记录，返回0
        if weighted_play_count == 0 and unique_user_count == 0:
            return 0.0

        # 5. 计算时间衰减因子
        time_decay_factor = calculate_time_decay(last_play_time)

        # 6. 计算播放量压缩（使用sqrt，给小爆款机会）
        play_count_compressed = math.sqrt(weighted_play_count)

        # 7. 计算热度 = (UV × 权重 + PV_sqrt × 权重) × 时间衰减
        hotness = (unique_user_count * UV_WEIGHT + play_count_compressed * PV_WEIGHT) * time_decay_factor

        return round(hotness, 2)

    except Exception as e:
        logger.error(f"计算热度失败: song_id={song_id}, {e}")
        return 0.0


def calculate_time_decay(last_play_time: int) -> float:
    """计算时间衰减因子（指数衰减）

    公式：decay = e^(-decay_rate × hours_since_last_play)
    其中 decay_rate = -ln(DECAY_FACTOR) / TIME_DECAY_HOURS

    Args:
        last_play_time: 最后播放时间（毫秒时间戳）

    Returns:
        float: 时间衰减因子（0-1之间）
    """
    try:
        # 当前时间（毫秒）
        current_time = int(time.time() * 1000)

        # 如果没有最后播放时间，使用当前时间（衰减为1）
        if last_play_time == 0:
            return 1.0

        # 计算距离最后播放的小时数
        hours_since_last_play = (current_time - last_play_time) / (1000 * 60 * 60)

        # 计算衰减率
        decay_rate = -math.log(DECAY_FACTOR) / TIME_DECAY_HOURS

        # 计算时间衰减因子（指数衰减）
        time_decay_factor = math.exp(-decay_rate * hours_since_last_play)

        # 确保衰减因子在合理范围内（0-1）
        time_decay_factor = max(0.0, min(1.0, time_decay_factor))

        return time_decay_factor

    except Exception as e:
        logger.error(f"计算时间衰减失败: {e}")
        return 1.0


def increment_hotness_on_play(song_id: int, username: str = None) -> bool:
    """播放时实时增量更新热度（新优化）

    在用户播放歌曲时，立即计算并更新该歌曲的热度
    这样可以避免定时任务全量计算，提升实时性

    Args:
        song_id: 歌曲ID
        username: 用户名（可选）

    Returns:
        bool: 是否成功
    """
    try:
        # 计算当前热度
        hotness = calculate_hotness_optimized(song_id)

        # 更新到Redis
        if update_trending_hotness(song_id, hotness):
            logger.info(f"✅ 播放时实时更新热度: song_id={song_id}, hotness={hotness}, user={username}")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ 播放时实时更新热度失败: song_id={song_id}, {e}")
        return False


def decay_all_trending_songs() -> int:
    """定时任务：对所有热度进行时间衰减

    每分钟执行一次，将所有歌曲的热度乘以衰减因子
    这样播放时只需要增量更新，定时任务只做衰减

    Returns:
        int: 更新的歌曲数量
    """
    try:
        if not redis_client:
            logger.error("❌ Redis 未连接，无法衰减热度")
            return 0

        logger.info("🔄 开始衰减所有歌曲的热度...")

        key = MUSIC_TRENDING_PREFIX

        # 获取所有歌曲的热度（使用ZREVRANGE获取全部）
        all_songs = redis_client.zrevrange(key, 0, -1, withscores=True)

        if not all_songs:
            logger.info("ℹ️ 没有需要衰减的歌曲")
            return 0

        # 计算每分钟的衰减因子（24小时衰减到0.5，所以每分钟衰减约0.0012）
        minute_decay = 1.0 - (1.0 - DECAY_FACTOR) / (TIME_DECAY_HOURS * 60)

        updated_count = 0
        pipe = redis_client.pipeline()

        for song_id_str, hotness in all_songs:
            song_id = int(song_id_str)

            # 应用衰减
            new_hotness = hotness * minute_decay

            # 如果热度太低，可以删除（可选）
            if new_hotness < 0.01:
                pipe.zrem(key, str(song_id))
            else:
                pipe.zadd(key, {str(song_id): new_hotness})

            updated_count += 1

        # 执行批量更新
        pipe.execute()

        # 设置过期时间
        redis_client.expire(key, 6 * 60 * 60)  # 6小时

        logger.info(f"✅ 热度衰减完成: {updated_count} 首歌曲 (衰减因子: {minute_decay:.6f})")

        return updated_count

    except Exception as e:
        logger.error(f"❌ 衰减热度失败: {e}")
        return 0


def update_trending_rankings_full():
    """全量更新热门趋势排行榜（带排名快照推送）
    
    每5分钟执行一次：
    1. 计算每首歌曲的热度
    2. 更新到Redis
    3. 将当前排名快照推送到队列（用于统计排名变化）
    """
    try:
        logger.info("🔄 开始全量更新热门趋势...")

        if not redis_client:
            logger.error("❌ Redis 未连接，无法更新热门趋势")
            return

        # 获取今日排行榜
        daily_rankings = get_music_rankings(limit=TRENDING_TOP_N, time_range="daily")

        if not daily_rankings:
            logger.warning("⚠️ 今日排行榜为空，跳过更新")
            return

        # 计算每首歌曲的热度
        updated_count = 0
        for rank_item in daily_rankings:
            song_id = rank_item["song_id"]

            # 使用优化后的算法计算热度
            hotness = calculate_hotness_optimized(song_id)

            # 更新到Redis
            if update_trending_hotness(song_id, hotness):
                updated_count += 1

        logger.info(f"✅ 热门趋势全量更新完成: {updated_count}/{len(daily_rankings)} 首歌曲")
        
        # 推送排名快照到队列（新增）
        import time
        current_time = int(time.time() * 1000)
        snapshot = {
            "timestamp": current_time,
            "rankings": {str(item["song_id"]): item["rank"] for item in daily_rankings}
        }
        
        if push_rank_snapshot_to_queue(snapshot):
            logger.info(f"✅ 排名快照已推送到队列")

    except Exception as e:
        logger.error(f"❌ 全量更新热门趋势失败: {e}")


# ==================== 定时任务 ====================

def start_trending_scheduler():
    """启动热门趋势定时任务（优化版）

    使用 APScheduler 定时衰减热度和更新热门趋势
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()

        # 每 1 分钟衰减一次所有热度
        scheduler.add_job(
            decay_all_trending_songs,
            'interval',
            minutes=1,
            id='decay_trending',
            name='衰减音乐热门趋势',
            max_instances=1  # 防止并发执行
        )

        # 每 5 分钟全量更新一次Top 100（作为补充，确保不遗漏）
        scheduler.add_job(
            update_trending_rankings_full,
            'interval',
            minutes=5,
            id='update_trending_full',
            name='全量更新热门趋势',
            max_instances=1  # 防止并发执行
        )

        scheduler.start()
        logger.info("✅ 热门趋势定时任务已启动（每分钟衰减 + 每5分钟全量更新）")

        # 启动时立即执行一次全量更新
        update_trending_rankings_full()

        return scheduler

    except Exception as e:
        logger.error(f"❌ 启动热门趋势定时任务失败: {e}")
        return None


# ==================== 测试函数 ====================

def test_hotness_calculation():
    """测试热度计算"""
    logger.info("开始测试热度计算...")

    # 测试时间衰减
    current_time = int(time.time() * 1000)
    test_time_cases = [
        (current_time, "刚刚播放"),
        (current_time - 3600 * 1000, "1小时前播放"),
        (current_time - 12 * 3600 * 1000, "12小时前播放"),
        (current_time - 24 * 3600 * 1000, "24小时前播放"),
    ]

    logger.info("=== 时间衰减测试 ===")
    for last_play_time, desc in test_time_cases:
        decay = calculate_time_decay(last_play_time)
        logger.info(f"{desc}: decay={decay:.4f}")

    # 测试热度计算（模拟数据）
    logger.info("\n=== 热度计算测试 ===")
    test_cases = [
        (100, 50, current_time, "100播放量, 50UV, 刚刚播放"),
        (1000, 100, current_time, "1000播放量, 100UV, 刚刚播放"),
        (100, 100, current_time - 3600 * 1000, "100播放量, 100UV, 1小时前播放"),
    ]

    # 临时模拟Redis数据
    if redis_client:
        # 注意：这只是测试代码，实际使用时Redis中应该有真实数据
        logger.info("提示：需要Redis中有实际播放数据才能测试完整热度计算")

    # 测试衰减
    logger.info("\n=== 测试衰减任务 ===")
    decay_count = decay_all_trending_songs()
    logger.info(f"衰减了 {decay_count} 首歌曲")

    # 测试全量更新
    logger.info("\n=== 测试全量更新 ===")
    update_trending_rankings_full()


if __name__ == "__main__":
    test_hotness_calculation()
