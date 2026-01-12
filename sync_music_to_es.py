"""
将Neo4j中的音乐数据同步到Elasticsearch
"""

import logging
from elasticsearch_utils import es_manager
from database import driver
from config import ES_INDEX_MUSIC

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_songs_from_neo4j():
    """从Neo4j获取歌曲列表"""
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Song)
                RETURN s.id as id, 
                       s.title as title, 
                       s.artist as artist,
                       s.album as album,
                       s.duration as duration,
                       s.file_path as file_path,
                       s.cover_image as cover_image,
                       s.created_at as created_at,
                       s.genre as genre,
                       s.play_count as play_count
                ORDER BY s.created_at DESC
            """)
            songs = []
            for record in result:
                songs.append({
                    "id": record["id"],
                    "title": record["title"],
                    "artist": record.get("artist", ""),
                    "album": record.get("album", ""),
                    "duration": record.get("duration", 0),
                    "file_path": record.get("file_path", ""),
                    "cover_image": record.get("cover_image", ""),
                    "created_at": record.get("created_at", 0),
                    "genre": record.get("genre", "流行"),
                    "play_count": record.get("play_count", 0)
                })
            logger.info(f"✅ 从Neo4j获取到 {len(songs)} 首歌曲")
            return songs
    except Exception as e:
        logger.error(f"❌ 从Neo4j获取歌曲列表失败: {e}")
        return []


def sync_music_to_elasticsearch():
    """将Neo4j中的音乐数据同步到Elasticsearch"""
    logger.info("🚀 开始同步音乐数据到Elasticsearch...")

    # 从Neo4j获取歌曲数据
    songs = get_songs_from_neo4j()

    if not songs:
        logger.warning("⚠️ 没有找到歌曲数据，同步终止")
        return

    # 批量索引到ES
    success_count = es_manager.bulk_index_music(songs)

    if success_count > 0:
        logger.info(f"✅ 成功同步 {success_count} 首歌曲到Elasticsearch")
        logger.info(f"📊 索引名称: {ES_INDEX_MUSIC}")
    else:
        logger.error("❌ 同步失败")


def update_music_in_elasticsearch(song_id: int):
    """更新单首歌曲到Elasticsearch

    Args:
        song_id: 歌曲ID
    """
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Song {id: $song_id})
                RETURN s.id as id, 
                       s.title as title, 
                       s.artist as artist,
                       s.album as album,
                       s.duration as duration,
                       s.file_path as file_path,
                       s.cover_image as cover_image,
                       s.created_at as created_at,
                       s.genre as genre,
                       s.play_count as play_count
            """, song_id=song_id)

            record = result.single()
            if not record:
                logger.warning(f"⚠️ 未找到ID为 {song_id} 的歌曲")
                return False

            song = {
                "id": record["id"],
                "title": record["title"],
                "artist": record.get("artist", ""),
                "album": record.get("album", ""),
                "duration": record.get("duration", 0),
                "file_path": record.get("file_path", ""),
                "cover_image": record.get("cover_image", ""),
                "created_at": record.get("created_at", 0),
                "genre": record.get("genre", "流行"),
                "play_count": record.get("play_count", 0)
            }

            # 更新到ES
            success = es_manager.index_music(song)
            if success:
                logger.info(f"✅ 成功更新歌曲 {song['title']} 到Elasticsearch")
                return True
            else:
                logger.error(f"❌ 更新歌曲 {song['title']} 到Elasticsearch失败")
                return False

    except Exception as e:
        logger.error(f"❌ 更新歌曲到Elasticsearch失败: {e}")
        return False


if __name__ == "__main__":
    sync_music_to_elasticsearch()