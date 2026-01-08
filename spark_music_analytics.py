"""
Spark 音乐批处理作业
从 Kafka 读取播放事件，生成日榜/周榜/月榜，分析用户偏好
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, count, sum as spark_sum, 
    window, desc, rank, when, lit
)
from pyspark.sql.window import Window
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, LongType
)

from neo4j_writer import (
    write_daily_rankings,
    write_weekly_rankings,
    write_monthly_rankings,
    write_user_preferences,
    update_total_play_stats
)
from kafka_offset_utils import get_kafka_consumer, get_offsets_by_timestamp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置参数
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
MUSIC_PLAY_EVENTS_TOPIC = 'music-play-events'

# 播放事件 Schema
EVENT_SCHEMA = StructType([
    StructField("event_id", StringType(), True),
    StructField("song_id", IntegerType(), True),
    StructField("user_id", StringType(), True),
    StructField("timestamp", LongType(), True),
    StructField("event_type", StringType(), True)
])


def create_spark_session(app_name: str = "MusicAnalytics"):
    """创建 Spark Session（本地模式）

    Args:
        app_name: 应用名称

    Returns:
        SparkSession: Spark 会话对象
    """
    spark = SparkSession.builder \
        .appName(app_name) \
        .master("local[2]") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1") \
        .getOrCreate()
    
    # 设置日志级别
    spark.sparkContext.setLogLevel("WARN")
    
    logger.info(f"✅ Spark Session 创建成功: {app_name}")
    return spark


def read_kafka_events(spark: SparkSession, start_timestamp: int, end_timestamp: int):
    """从 Kafka 读取指定时间范围内的播放事件（使用优化后的 offset 查询）

    ✅ 性能优化说明:
    本函数使用 Kafka Consumer API 先查询精确的 offset 范围，然后让 Spark 只读取指定范围内的数据。
    这样可以避免读取大量历史数据，显著提升性能，特别是当 Kafka topic 保留时间长（7天+）时。

    Args:
        spark: Spark Session
        start_timestamp: 开始时间戳（毫秒）
        end_timestamp: 结束时间戳（毫秒）

    Returns:
        DataFrame: 播放事件数据
    """
    consumer = None
    try:
        # 1. 使用 Kafka Consumer API 查询精确的 offset 范围
        consumer = get_kafka_consumer()
        
        offset_info = get_offsets_by_timestamp(
            consumer,
            MUSIC_PLAY_EVENTS_TOPIC,
            start_timestamp,
            end_timestamp
        )
        
        # 2. 从 Kafka 读取数据（使用精确的 offset 范围）
        df = spark.read \
            .format("kafka") \
            .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
            .option("subscribe", MUSIC_PLAY_EVENTS_TOPIC) \
            .option("startingOffsets", offset_info['startingOffsets']) \
            .option("endingOffsets", offset_info['endingOffsets']) \
            .load()
        
        # 解析 JSON 值
        event_df = df.select(
            from_json(col("value").cast("string"), EVENT_SCHEMA).alias("event")
        ).select("event.*")
        
        # 过滤时间范围
        filtered_df = event_df.filter(
            (col("timestamp") >= start_timestamp) & 
            (col("timestamp") < end_timestamp)
        )
        
        count = filtered_df.count()
        logger.info(f"✅ 从 Kafka 读取事件: 时间范围=[{start_timestamp}, {end_timestamp}), 实际读取={count}条")
        
        return filtered_df
        
    except Exception as e:
        logger.error(f"❌ 从 Kafka 读取事件失败: {e}")
        raise
    
    finally:
        # 3. 关闭 Kafka Consumer
        if consumer:
            consumer.close()


def calculate_growth_rate(current_count: int, previous_count: int) -> float:
    """计算环比增长率

    Args:
        current_count: 当前播放次数
        previous_count: 上一次播放次数

    Returns:
        float: 增长率（百分比）
    """
    if previous_count == 0:
        return 100.0 if current_count > 0 else 0.0
    return ((current_count - previous_count) / previous_count) * 100


def run_daily_stats(date: str):
    """执行每日统计作业

    Args:
        date: 日期字符串，格式: '2026-01-04'
    """
    logger.info(f"🚀 开始执行每日统计作业: date={date}")
    
    spark = None
    try:
        # 1. 创建 Spark Session
        spark = create_spark_session("DailyStats")
        
        # 2. 计算时间范围
        date_dt = datetime.strptime(date, '%Y-%m-%d')
        start_timestamp = int(date_dt.timestamp() * 1000)
        end_timestamp = int((date_dt + timedelta(days=1)).timestamp() * 1000)
        
        # 3. 读取 Kafka 事件
        event_df = read_kafka_events(spark, start_timestamp, end_timestamp)
        
        if event_df.count() == 0:
            logger.warning(f"⚠️ 该日期没有播放事件: date={date}")
            return
        
        # 4. 按歌曲聚合统计播放次数
        song_stats = event_df.groupBy("song_id").agg(
            count("*").alias("play_count")
        ).orderBy(desc("play_count"))
        
        # 5. 计算排名
        window_spec = Window.orderBy(desc("play_count"))
        song_stats = song_stats.withColumn("rank", rank().over(window_spec))
        
        # 6. 获取前一天的播放次数（计算增长率）
        prev_date_dt = date_dt - timedelta(days=1)
        prev_date = prev_date_dt.strftime('%Y-%m-%d')
        
        # 从 Neo4j 读取前一天的数据
        from database import driver
        prev_stats = {}
        
        try:
            with driver.session() as session:
                query = """
                    MATCH (s:Song)
                    WHERE s.daily_rank_date = date($date)
                    RETURN s.id as song_id, s.daily_play_count as play_count
                """
                result = session.run(query, date=prev_date)
                for record in result:
                    prev_stats[record["song_id"]] = record["play_count"]
        except Exception as e:
            logger.warning(f"⚠️ 读取前一天数据失败: {e}")
        
        # 7. 收集结果并计算增长率
        rankings = []
        for row in song_stats.collect():
            song_id = row["song_id"]
            play_count = row["play_count"]
            rank = row["rank"]
            prev_count = prev_stats.get(song_id, 0)
            growth_rate = calculate_growth_rate(play_count, prev_count)
            
            rankings.append({
                "song_id": song_id,
                "rank": rank,
                "play_count": play_count,
                "growth_rate": round(growth_rate, 2)
            })
        
        # 8. 写入 Neo4j
        write_daily_rankings(rankings, date)
        
        # 9. 更新整体统计
        update_total_play_stats(date)
        
        logger.info(f"✅ 每日统计作业完成: date={date}, total_songs={len(rankings)}")
        
    except Exception as e:
        logger.error(f"❌ 每日统计作业失败: date={date}, {e}")
        raise
    finally:
        if spark:
            spark.stop()
            logger.info("🔒 Spark Session 已关闭")


def run_weekly_stats(week: str):
    """执行每周统计作业

    Args:
        week: 周字符串，格式: '2026-W01'（ISO 周格式）
    """
    logger.info(f"🚀 开始执行每周统计作业: week={week}")
    
    spark = None
    try:
        # 1. 创建 Spark Session
        spark = create_spark_session("WeeklyStats")
        
        # 2. 解析周范围
        year, week_num = week.split('-W')
        year = int(year)
        week_num = int(week_num)
        
        # 计算周的起止时间
        # ISO 周的第一天是周一
        start_date = datetime.fromisocalendar(year, week_num, 1)
        end_date = start_date + timedelta(days=7)
        
        start_timestamp = int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)
        
        # 3. 读取 Kafka 事件
        event_df = read_kafka_events(spark, start_timestamp, end_timestamp)
        
        if event_df.count() == 0:
            logger.warning(f"⚠️ 该周没有播放事件: week={week}")
            return
        
        # 4. 按歌曲聚合统计播放次数
        song_stats = event_df.groupBy("song_id").agg(
            count("*").alias("play_count")
        ).orderBy(desc("play_count"))
        
        # 5. 计算排名
        window_spec = Window.orderBy(desc("play_count"))
        song_stats = song_stats.withColumn("rank", rank().over(window_spec))
        
        # 6. 收集结果
        rankings = []
        for row in song_stats.collect():
            rankings.append({
                "song_id": row["song_id"],
                "rank": row["rank"],
                "play_count": row["play_count"]
            })
        
        # 7. 写入 Neo4j
        write_weekly_rankings(rankings, week)
        
        logger.info(f"✅ 每周统计作业完成: week={week}, total_songs={len(rankings)}")
        
    except Exception as e:
        logger.error(f"❌ 每周统计作业失败: week={week}, {e}")
        raise
    finally:
        if spark:
            spark.stop()
            logger.info("🔒 Spark Session 已关闭")


def run_monthly_stats(month: str):
    """执行每月统计作业

    Args:
        month: 月字符串，格式: '2026-01'
    """
    logger.info(f"🚀 开始执行每月统计作业: month={month}")
    
    spark = None
    try:
        # 1. 创建 Spark Session
        spark = create_spark_session("MonthlyStats")
        
        # 2. 解析月范围
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1)
        
        # 计算下个月的第一天
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month_num + 1, 1)
        
        start_timestamp = int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)
        
        # 3. 读取 Kafka 事件
        event_df = read_kafka_events(spark, start_timestamp, end_timestamp)
        
        if event_df.count() == 0:
            logger.warning(f"⚠️ 该月没有播放事件: month={month}")
            return
        
        # 4. 按歌曲聚合统计播放次数
        song_stats = event_df.groupBy("song_id").agg(
            count("*").alias("play_count")
        ).orderBy(desc("play_count"))
        
        # 5. 计算排名
        window_spec = Window.orderBy(desc("play_count"))
        song_stats = song_stats.withColumn("rank", rank().over(window_spec))
        
        # 6. 收集结果
        rankings = []
        for row in song_stats.collect():
            rankings.append({
                "song_id": row["song_id"],
                "rank": row["rank"],
                "play_count": row["play_count"]
            })
        
        # 7. 写入 Neo4j
        write_monthly_rankings(rankings, month)
        
        logger.info(f"✅ 每月统计作业完成: month={month}, total_songs={len(rankings)}")
        
    except Exception as e:
        logger.error(f"❌ 每月统计作业失败: month={month}, {e}")
        raise
    finally:
        if spark:
            spark.stop()
            logger.info("🔒 Spark Session 已关闭")


def run_user_preference_analysis(date: str):
    """执行用户偏好分析作业

    Args:
        date: 日期字符串，格式: '2026-01-04'
    """
    logger.info(f"🚀 开始执行用户偏好分析作业: date={date}")
    
    spark = None
    try:
        # 1. 创建 Spark Session
        spark = create_spark_session("UserPreferenceAnalysis")
        
        # 2. 计算时间范围（分析最近 30 天）
        date_dt = datetime.strptime(date, '%Y-%m-%d')
        start_date = date_dt - timedelta(days=30)
        
        start_timestamp = int(start_date.timestamp() * 1000)
        end_timestamp = int((date_dt + timedelta(days=1)).timestamp() * 1000)
        
        # 3. 读取 Kafka 事件
        event_df = read_kafka_events(spark, start_timestamp, end_timestamp)
        
        if event_df.count() == 0:
            logger.warning(f"⚠️ 该时间段没有播放事件: date={date}")
            return
        
        # 4. 按用户聚合统计
        user_stats = event_df.groupBy("user_id", "song_id").agg(
            count("*").alias("play_count")
        )
        
        # 5. 为每个用户计算 Top 5 歌曲
        user_window = Window.partitionBy("user_id").orderBy(desc("play_count"))
        user_stats = user_stats.withColumn("rank", rank().over(user_window))
        
        # 6. 过滤 Top 5
        top_songs = user_stats.filter(col("rank") <= 5)
        
        # 7. 计算用户总播放次数
        user_total_plays = event_df.groupBy("user_id").agg(
            count("*").alias("total_plays")
        )
        
        # 8. 按用户收集结果
        user_preference_dict = {}
        for row in user_total_plays.collect():
            user_id = row["user_id"]
            user_preference_dict[user_id] = {
                "username": user_id,
                "total_plays": row["total_plays"],
                "last_active_at": date,
                "top_songs": [],
                "genre_preferences": {}
            }
        
        # 9. 填充 Top 5 歌曲
        for row in top_songs.collect():
            user_id = row["user_id"]
            user_preference_dict[user_id]["top_songs"].append({
                "song_id": row["song_id"],
                "play_count": row["play_count"]
            })
        
        # TODO: 实现音乐类型偏好分析（需要从 Neo4j 获取歌曲的 genre 信息）
        # 这里暂时留空，后续可以扩展
        
        # 10. 写入 Neo4j（批处理）
        processed_count = 0
        for user_id, preference in user_preference_dict.items():
            try:
                write_user_preferences(preference, date)
                processed_count += 1
            except Exception as e:
                logger.error(f"❌ 写入用户偏好失败: user_id={user_id}, {e}")
        
        logger.info(f"✅ 用户偏好分析作业完成: date={date}, processed_users={processed_count}")
        
    except Exception as e:
        logger.error(f"❌ 用户偏好分析作业失败: date={date}, {e}")
        raise
    finally:
        if spark:
            spark.stop()
            logger.info("🔒 Spark Session 已关闭")


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 3:
        print("Usage: python spark_music_analytics.py <daily|weekly|monthly|user-preference> <date|week|month>")
        print("Example:")
        print("  python spark_music_analytics.py daily 2026-01-04")
        print("  python spark_music_analytics.py weekly 2026-W01")
        print("  python spark_music_analytics.py monthly 2026-01")
        print("  python spark_music_analytics.py user-preference 2026-01-04")
        sys.exit(1)
    
    task_type = sys.argv[1].lower()
    time_param = sys.argv[2]
    
    try:
        if task_type == "daily":
            run_daily_stats(time_param)
        elif task_type == "weekly":
            run_weekly_stats(time_param)
        elif task_type == "monthly":
            run_monthly_stats(time_param)
        elif task_type == "user-preference":
            run_user_preference_analysis(time_param)
        else:
            logger.error(f"❌ 未知的任务类型: {task_type}")
            sys.exit(1)
            
        logger.info("✅ 任务执行完成")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ 任务执行失败: {e}")
        sys.exit(1)
