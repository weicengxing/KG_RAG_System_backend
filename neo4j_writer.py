"""
Neo4j 数据写入工具
将 Spark 批处理结果写入 Neo4j 数据库
"""

import logging
from typing import List, Dict
from datetime import datetime, timedelta
from database import driver

logger = logging.getLogger(__name__)


def write_daily_rankings(song_rankings: List[Dict], date: str):
    """写入每日排行榜到 Neo4j

    Args:
        song_rankings: 歌曲排行榜数据，格式: [{'song_id': int, 'rank': int, 'play_count': int, 'growth_rate': float}, ...]
        date: 日期字符串，格式: '2026-01-04'
    """
    try:
        with driver.session() as session:
            # 批量更新歌曲节点
            update_query = """
                UNWIND $rankings AS ranking
                MATCH (s:Song {id: ranking.song_id})
                SET s.daily_play_count = ranking.play_count,
                    s.daily_rank = ranking.rank,
                    s.daily_growth_rate = ranking.growth_rate,
                    s.daily_rank_date = date($date),
                    s.updated_at = datetime()
                RETURN count(s) as updated
            """
            
            result = session.run(update_query, rankings=song_rankings, date=date)
            count = result.single()["updated"]
            
            logger.info(f"✅ 写入每日排行榜成功: date={date}, updated={count}首歌曲")
            
    except Exception as e:
        logger.error(f"❌ 写入每日排行榜失败: date={date}, {e}")
        raise


def write_weekly_rankings(song_rankings: List[Dict], week: str):
    """写入每周排行榜到 Neo4j

    Args:
        song_rankings: 歌曲排行榜数据，格式: [{'song_id': int, 'rank': int, 'play_count': int}, ...]
        week: 周字符串，格式: '2026-W01'
    """
    try:
        with driver.session() as session:
            # 批量更新歌曲节点
            # 注意：weekly_rank_date 存储为字符串（与 monthly 一样），便于查询
            update_query = """
                UNWIND $rankings AS ranking
                MATCH (s:Song {id: ranking.song_id})
                SET s.weekly_play_count = ranking.play_count,
                    s.weekly_rank = ranking.rank,
                    s.weekly_rank_date = $week,
                    s.updated_at = datetime()
                RETURN count(s) as updated
            """
            
            result = session.run(update_query, rankings=song_rankings, week=week)
            count = result.single()["updated"]
            
            logger.info(f"✅ 写入每周排行榜成功: week={week}, updated={count}首歌曲")
            
    except Exception as e:
        logger.error(f"❌ 写入每周排行榜失败: week={week}, {e}")
        raise


def write_monthly_rankings(song_rankings: List[Dict], month: str):
    """写入每月排行榜到 Neo4j

    Args:
        song_rankings: 歌曲排行榜数据，格式: [{'song_id': int, 'rank': int, 'play_count': int}, ...]
        month: 月字符串，格式: '2026-01'
    """
    try:
        with driver.session() as session:
            # 批量更新歌曲节点
            # 注意：monthly_rank_date 存储为字符串（与 weekly 一样），便于查询
            update_query = """
                UNWIND $rankings AS ranking
                MATCH (s:Song {id: ranking.song_id})
                SET s.monthly_play_count = ranking.play_count,
                    s.monthly_rank = ranking.rank,
                    s.monthly_rank_date = $month,
                    s.updated_at = datetime()
                RETURN count(s) as updated
            """
            
            result = session.run(update_query, rankings=song_rankings, month=month)
            count = result.single()["updated"]
            
            logger.info(f"✅ 写入每月排行榜成功: month={month}, updated={count}首歌曲")
            
    except Exception as e:
        logger.error(f"❌ 写入每月排行榜失败: month={month}, {e}")
        raise


def write_user_preferences(user_preferences: Dict, date: str):
    """写入用户偏好分析到 Neo4j

    Args:
        user_preferences: 用户偏好数据，格式: {
            'username': str,
            'total_plays': int,
            'last_active_at': str,
            'top_songs': [{'song_id': int, 'play_count': int}, ...],
            'genre_preferences': {str: float}  # {genre: weight}
        }
        date: 日期字符串，格式: '2026-01-04'
    """
    try:
        username = user_preferences['username']
        top_songs = user_preferences.get('top_songs', [])
        genre_prefs = user_preferences.get('genre_preferences', {})
        
        with driver.session() as session:
            # 1. 创建或更新 User 节点
            user_query = """
                MERGE (u:User {username: $username})
                SET u.total_plays = $total_plays,
                    u.last_active_at = datetime($last_active_at),
                    u.updated_at = datetime()
                RETURN u
            """
            
            session.run(user_query, 
                       username=username,
                       total_plays=user_preferences['total_plays'],
                       last_active_at=user_preferences['last_active_at'])
            
            # 2. 创建 PREFERS 关系（用户偏好歌曲 Top 5）
            if top_songs:
                prefers_query = """
                    MATCH (u:User {username: $username})
                    UNWIND $top_songs AS song
                    MATCH (s:Song {id: song.song_id})
                    MERGE (u)-[p:PREFERS]->(s)
                    SET p.play_count = song.play_count,
                        p.weight = toFloat(song.play_count),
                        p.updated_at = datetime()
                    RETURN count(p) as created
                """
                
                result = session.run(prefers_query, username=username, top_songs=top_songs[:5])
                count = result.single()["created"]
                logger.info(f"✅ 创建用户偏好关系: username={username}, created={count}个")
            
            # 3. 设置用户音乐类型偏好（作为 User 节点的属性）
            if genre_prefs:
                # 将字典转换为 Cypher MAP 格式
                genre_map_str = "{" + ", ".join([f"'{k}': {v}" for k, v in genre_prefs.items()]) + "}"
                genre_query = f"""
                    MATCH (u:User {{username: $username}})
                    SET u.genre_preferences = {genre_map_str}
                    RETURN u
                """
                
                session.run(genre_query, username=username)
                logger.info(f"✅ 更新用户音乐类型偏好: username={username}, genres={list(genre_prefs.keys())}")
            
            logger.info(f"✅ 写入用户偏好成功: username={username}, date={date}")
            
    except Exception as e:
        logger.error(f"❌ 写入用户偏好失败: username={user_preferences.get('username')}, date={date}, {e}")
        raise


def update_total_play_stats(date: str):
    """更新整体播放统计数据（总播放量、活跃用户数等）

    Args:
        date: 日期字符串，格式: '2026-01-04'
    """
    try:
        with driver.session() as session:
            # 1. 统计总播放量
            total_plays_query = """
                MATCH (s:Song)
                RETURN sum(s.daily_play_count) as total_plays
            """
            result = session.run(total_plays_query)
            total_plays = result.single()["total_plays"] or 0
            
            # 2. 统计活跃用户数（有播放记录的用户）
            active_users_query = """
                MATCH (u:User)
                WHERE u.last_active_at >= date($date)
                RETURN count(u) as active_users
            """
            result = session.run(active_users_query, date=date)
            active_users = result.single()["active_users"] or 0
            
            # 3. 创建或更新统计节点
            stats_query = """
                MERGE (d:DailyStats {date: $date})
                SET d.total_plays = $total_plays,
                    d.active_users = $active_users,
                    d.updated_at = datetime()
                RETURN d
            """
            
            session.run(stats_query, date=date, total_plays=total_plays, active_users=active_users)
            
            logger.info(f"✅ 更新播放统计数据成功: date={date}, total_plays={total_plays}, active_users={active_users}")
            
    except Exception as e:
        logger.error(f"❌ 更新播放统计数据失败: date={date}, {e}")
        raise


def get_song_total_play_count(song_id: int) -> int:
    """获取歌曲的总播放量（从 Redis 读取）

    Args:
        song_id: 歌曲ID

    Returns:
        int: 总播放量
    """
    try:
        import redis
        from config import REDIS_HOST, REDIS_PORT, REDIS_DB
        
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=False
        )
        
        # 从全局播放量 ZSET 获取
        play_count = redis_client.zscore("music:play_count:global", song_id) or 0
        return int(play_count)
        
    except Exception as e:
        logger.error(f"❌ 获取歌曲总播放量失败: song_id={song_id}, {e}")
        return 0
