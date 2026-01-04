"""
音乐播放器路由
提供音乐列表、播放、图片等API接口
"""

import os
import base64
import json
import logging
import asyncio
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from database import driver
from auth_deps import get_current_user
from auth_deps import get_current_user, get_current_user_from_query
from pydantic import BaseModel
from typing import List, Dict
class BatchImageRequest(BaseModel):
    filenames: List[str]

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/music", tags=["音乐"])

# 音乐文件目录
MUSIC_DIR = Path("D:/高铁2/gao/public/music")
IMAGE_DIR = Path("D:/高铁2/gao/public/images")
LYRICS_DIR = Path("D:/Music")


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
                       s.created_at as created_at
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
                    "created_at": record.get("created_at", 0)
                })
            if songs:
                return songs
    except Exception as e:
        logger.warning(f"从Neo4j获取歌曲列表失败: {e}")

    # 如果Neo4j中没有数据，尝试从文件系统扫描
    return get_songs_from_filesystem()


def get_songs_from_filesystem():
    """从文件系统扫描歌曲列表（备用方案）"""
    songs = []
    if not MUSIC_DIR.exists():
        logger.error(f"音乐目录不存在: {MUSIC_DIR}")
        return songs

    # 支持的音频格式
    audio_extensions = {'.mp3', '.mp4', '.m4a', '.wav', '.flac', '.aac'}
    
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(MUSIC_DIR.glob(f"*{ext}"))
    
    audio_files = sorted(audio_files)
    
    for idx, file_path in enumerate(audio_files, 1):
        title = file_path.stem  # 文件名（不含扩展名）
        
        # 尝试查找对应的封面图片
        cover_image = None
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        for img_ext in image_extensions:
            img_path = IMAGE_DIR / f"{file_path.stem}{img_ext}"
            if img_path.exists():
                cover_image = img_path.name
                break
        
        songs.append({
            "id": idx,
            "title": title,
            "artist": "",
            "album": "",
            "duration": 0,  # 需要从文件元数据获取
            "file_path": str(file_path),
            "cover_image": cover_image or "",
            "created_at": int(file_path.stat().st_mtime * 1000)
        })
    
    return songs


@router.get("/songs")
async def get_song_list(
    current_user: str = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0
):
    """获取歌曲列表（支持分页）

    Args:
        current_user: 当前认证用户
        limit: 每页数量，默认20
        offset: 偏移量，默认0

    Returns:
        dict: 包含歌曲列表的响应
    """
    try:
        all_songs = get_songs_from_neo4j()
        total = len(all_songs)

        # 分页处理
        paginated_songs = all_songs[offset:offset + limit]
        has_more = (offset + limit) < total

        return {
            "success": True,
            "songs": paginated_songs,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": has_more
        }
    except Exception as e:
        logger.error(f"获取歌曲列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取歌曲列表失败")


@router.get("/songs/stream")
async def get_song_list_stream(
    current_user: str = Depends(get_current_user_from_query),
    fetch_size: int = 1  # 批次大小，1表示逐条返回，可以设置为更大的值如100来提高性能
):
    """流式获取歌曲列表（SSE）- 真正的异步边查边发

    使用真正的异步处理：
    - 使用 asyncio.run_in_executor 在线程池中执行 Neo4j 查询（替代 with 和 threading）
    - 使用 asyncio.Queue 实现异步生产者-消费者模式
    - Neo4j 驱动默认按批次（~1000条）从数据库获取，但我们可以控制每次发送的批次大小

    Args:
        current_user: 当前认证用户
        fetch_size: 控制每次发送给前端的记录数，默认1（逐条返回），可设置为100等更大值

    Returns:
        StreamingResponse: SSE 流式响应，逐条推送歌曲数据
    """
    async def generate_songs():
        # 使用异步队列替代 threading.Queue
        song_queue = asyncio.Queue()
        error_holder = {"error": None}
        total_holder = {"total": 0}
        is_done = {"done": False}

        async def query_songs_producer():
            """生产者：在线程池中执行 Neo4j 查询，查一条就发一条到队列（直接放入异步队列）"""
            try:
                loop = asyncio.get_event_loop()
                
                def query_db_sync():
                    """在线程池中执行的同步查询函数，查一条就放入异步队列一条"""
                    session = driver.session()
                    try:
                        # 先查询总数
                        count_result = session.run("MATCH (s:Song) RETURN count(s) as total")
                        total = count_result.single()["total"]
                        total_holder["total"] = total  # 更新总数
                        # 使用 run_coroutine_threadsafe 在同步函数中调用异步方法
                        asyncio.run_coroutine_threadsafe(
                            song_queue.put(("meta", {"total": total})), 
                            loop
                        )
                        
                        # 执行查询
                        result = session.run(
                            """
                            MATCH (s:Song)
                            RETURN s.id as id,
                                   s.title as title,
                                   s.artist as artist,
                                   s.album as album,
                                   s.duration as duration,
                                   s.file_path as file_path,
                                   s.cover_image as cover_image,
                                   s.created_at as created_at
                            ORDER BY s.created_at DESC
                            """
                        )
                        
                        # 逐条处理记录：查一条就放入队列一条（真正的边查边发）
                        for record in result:
                            song = {
                                "id": record["id"],
                                "title": record["title"],
                                "artist": record.get("artist", ""),
                                "album": record.get("album", ""),
                                "duration": record.get("duration", 0),
                                "file_path": record.get("file_path", ""),
                                "cover_image": record.get("cover_image", ""),
                                "created_at": record.get("created_at", 0)
                            }
                            # 查完一条就立即放入异步队列（生产者直接放，消费者直接取）
                            asyncio.run_coroutine_threadsafe(
                                song_queue.put(("song", song)), 
                                loop
                            )
                        
                        # 查询完成，放入结束信号
                        asyncio.run_coroutine_threadsafe(
                            song_queue.put(("done", None)), 
                            loop
                        )
                        
                    except Exception as e:
                        logger.error(f"查询数据库失败: {e}")
                        asyncio.run_coroutine_threadsafe(
                            song_queue.put(("error", str(e))), 
                            loop
                        )
                    finally:
                        # 手动关闭 session，不使用 with
                        session.close()
                
                # 在线程池中执行查询（它会边查边放入异步队列）
                await loop.run_in_executor(None, query_db_sync)
                is_done["done"] = True
                    
            except Exception as e:
                logger.error(f"查询歌曲列表失败: {e}")
                error_holder["error"] = str(e)
                await song_queue.put(("error", str(e)))
                is_done["done"] = True

        # 启动生产者任务（异步替代 threading.Thread）
        producer_task = asyncio.create_task(query_songs_producer())

        try:
            # 发送开始信号
            yield f"data: {json.dumps({'type': 'start'})}\n\n"

            # 消费者：从队列中取数据并发送
            while True:
                try:
                    # 使用超时避免无限等待
                    try:
                        msg_type, data = await asyncio.wait_for(
                            song_queue.get(), 
                            timeout=0.1
                        )
                    except asyncio.TimeoutError:
                        # 检查是否已完成
                        if is_done["done"]:
                            break
                        # 继续等待
                        await asyncio.sleep(0.01)
                        continue

                    if msg_type == "meta":
                        # 发送总数信息
                        yield f"data: {json.dumps({'type': 'meta', 'total': data['total']})}\n\n"
                        # 让出控制权，保持响应性
                        await asyncio.sleep(0)

                    elif msg_type == "song":
                        yield f"data: {json.dumps({'type': 'song', 'song': data})}\n\n"
                        # 让出控制权，保持响应性
                        await asyncio.sleep(0)

                    elif msg_type == "done":
                        yield f"data: {json.dumps({'type': 'done', 'total': total_holder['total']})}\n\n"
                        break

                    elif msg_type == "error":
                        yield f"data: {json.dumps({'type': 'error', 'message': data})}\n\n"
                        break

                except Exception as e:
                    logger.error(f"处理队列数据失败: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    break

        except Exception as e:
            logger.error(f"流式获取歌曲列表失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # 确保生产者任务完成或取消
            if not producer_task.done():
                producer_task.cancel()
                try:
                    await producer_task
                except asyncio.CancelledError:
                    pass

    return StreamingResponse(
        generate_songs(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/play/{song_id}")
async def play_song(
    song_id: int,
    current_user: str = Depends(get_current_user)
):
    """播放指定歌曲

    Args:
        song_id: 歌曲ID
        current_user: 当前认证用户

    Returns:
        StreamingResponse: 音频文件流
    """
    try:
        # 同步更新 Redis 播放计数（新增）
        from redis_utils import increment_music_play_count
        increment_music_play_count(song_id, current_user)

        # 异步发送播放事件到 Kafka（新增）
        try:
            from kafka_music_producer import send_play_event
            send_play_event(song_id, current_user)
        except Exception as kafka_err:
            # Kafka 发送失败不影响播放功能
            logger.warning(f"发送 Kafka 事件失败: {kafka_err}")

        # 从Neo4j获取歌曲信息
        songs = get_songs_from_neo4j()
        song = next((s for s in songs if s["id"] == song_id), None)
        
        if not song:
            raise HTTPException(status_code=404, detail="歌曲不存在")
        
        file_path = song.get("file_path")
        if not file_path:
            raise HTTPException(status_code=404, detail="歌曲文件路径不存在")
        
        file_path_obj = Path(file_path)
        
        # 如果路径不存在，尝试从MUSIC_DIR中查找
        if not file_path_obj.exists():
            # 尝试通过文件名查找
            audio_extensions = {'.mp3', '.mp4', '.m4a', '.wav', '.flac', '.aac'}
            found = False
            for ext in audio_extensions:
                potential_path = MUSIC_DIR / f"{song['title']}{ext}"
                if potential_path.exists():
                    file_path_obj = potential_path
                    found = True
                    break
            
            if not found:
                raise HTTPException(status_code=404, detail="歌曲文件不存在")
        
        # 确定MIME类型
        ext = file_path_obj.suffix.lower()
        mime_types = {
            '.mp3': 'audio/mpeg',
            '.mp4': 'audio/mp4',
            '.m4a': 'audio/mp4',
            '.wav': 'audio/wav',
            '.flac': 'audio/flac',
            '.aac': 'audio/aac'
        }
        media_type = mime_types.get(ext, 'audio/mpeg')
        
        # 返回文件流
        return FileResponse(
            path=str(file_path_obj),
            media_type=media_type,
            filename=file_path_obj.name,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable", # 缓存1年，文件不变
                "Accept-Ranges": "bytes" # 支持拖动进度条
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"播放歌曲失败: {e}")
        raise HTTPException(status_code=500, detail="播放歌曲失败")


@router.get("/image/{image_name}")
async def get_song_image(
    image_name: str,
    current_user: str = Depends(get_current_user)
):
    """获取歌曲封面图片
    
    Args:
        image_name: 图片文件名
        current_user: 当前认证用户
        
    Returns:
        FileResponse: 图片文件
    """
    try:
        # 安全检查：防止路径遍历攻击
        if '..' in image_name or '/' in image_name or '\\' in image_name:
            raise HTTPException(status_code=400, detail="无效的图片文件名")
        
        image_path = IMAGE_DIR / image_name
        
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="图片不存在")
        
        # 确定MIME类型
        ext = image_path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        media_type = mime_types.get(ext, 'image/jpeg')
        
        return FileResponse(
            path=str(image_path),
            media_type=media_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取图片失败: {e}")
        raise HTTPException(status_code=500, detail="获取图片失败")


@router.get("/search")
async def search_songs(
    keyword: str,
    current_user: str = Depends(get_current_user)
):
    """搜索歌曲
    
    Args:
        keyword: 搜索关键词
        current_user: 当前认证用户
        
    Returns:
        dict: 包含搜索结果
    """
    try:
        songs = get_songs_from_neo4j()
        keyword_lower = keyword.lower()
        
        filtered_songs = [
            song for song in songs
            if keyword_lower in song["title"].lower() or
               keyword_lower in song.get("artist", "").lower() or
               keyword_lower in song.get("album", "").lower()
        ]
        
        return {
            "success": True,
            "songs": filtered_songs,
            "total": len(filtered_songs),
            "keyword": keyword
        }
    except Exception as e:
        logger.error(f"搜索歌曲失败: {e}")
        raise HTTPException(status_code=500, detail="搜索歌曲失败")


@router.get("/lyrics/{song_id}")
async def get_song_lyrics(
    song_id: int,
    current_user: str = Depends(get_current_user)
):
    """获取歌曲歌词
    
    Args:
        song_id: 歌曲ID
        current_user: 当前认证用户
        
    Returns:
        dict: 包含歌词内容的响应
    """
    try:
        # 从Neo4j获取歌曲信息
        songs = get_songs_from_neo4j()
        song = next((s for s in songs if s["id"] == song_id), None)
        
        if not song:
            raise HTTPException(status_code=404, detail="歌曲不存在")
        
        # 尝试从数据库获取歌词文件名
        lyrics_filename = None
        try:
            with driver.session() as session:
                result = session.run("""
                    MATCH (s:Song {id: $song_id})
                    RETURN s.lyrics_file as lyrics_file
                """, song_id=song_id)
                record = result.single()
                if record and record.get("lyrics_file"):
                    lyrics_filename = record["lyrics_file"]
        except Exception as e:
            logger.warning(f"从数据库获取歌词文件名失败: {e}")
        
        # 如果数据库中没有，尝试根据歌曲标题查找
        if not lyrics_filename:
            # 尝试查找 LRC 文件
            song_title = song.get("title", "")
            if LYRICS_DIR.exists():
                # 尝试多种可能的文件名格式
                possible_names = [
                    f"{song_title}.lrc",
                    f"{song_title}.txt",
                ]
                # 如果标题包含艺术家信息，也尝试分离
                if " - " in song_title:
                    parts = song_title.split(" - ", 1)
                    possible_names.extend([
                        f"{parts[0]}.lrc",
                        f"{parts[1]}.lrc" if len(parts) > 1 else None,
                    ])
                    possible_names = [n for n in possible_names if n]
                
                for name in possible_names:
                    lyrics_path = LYRICS_DIR / name
                    if lyrics_path.exists():
                        lyrics_filename = name
                        break
        
        if not lyrics_filename:
            return {
                "success": False,
                "lyrics": "",
                "message": "未找到歌词文件"
            }
        
        # 读取歌词文件
        lyrics_path = LYRICS_DIR / lyrics_filename
        if not lyrics_path.exists():
            return {
                "success": False,
                "lyrics": "",
                "message": "歌词文件不存在"
            }
        
        # 读取文件内容
        try:
            with open(lyrics_path, 'r', encoding='utf-8') as f:
                lyrics_content = f.read()
        except UnicodeDecodeError:
            # 如果 UTF-8 失败，尝试其他编码
            try:
                with open(lyrics_path, 'r', encoding='gbk') as f:
                    lyrics_content = f.read()
            except Exception as e:
                logger.error(f"读取歌词文件失败: {e}")
                raise HTTPException(status_code=500, detail="读取歌词文件失败")
        
        return {
            "success": True,
            "lyrics": lyrics_content,
            "filename": lyrics_filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取歌词失败: {e}")
        raise HTTPException(status_code=500, detail="获取歌词失败")

@router.get("/songs/all")
async def get_all_songs(
    current_user: str = Depends(get_current_user)
):
    """
    [列表接口] 获取所有歌曲的基本信息
    注意：这里不返回 Base64 图片，保持响应轻量快速
    """
    try:
        songs = get_songs_from_neo4j()
        
        # 如果数据库没数据，可以保留你的文件系统扫描兜底逻辑(此处省略以保持简洁)
        
        # 简单处理：确保 created_at 用于排序
        songs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        
        return {
            "success": True,
            "songs": songs,
            "total": len(songs)
        }
    except Exception as e:
        logger.error(f"获取歌曲列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取列表失败")
    
# 额外新增简化接口：一次性获取所有歌曲列表（不分页、不流式），适用于简化版前端逻辑，一是比较性能差距，二是我的免费服务器不支持高并发场景
#算了还是改成懒加载吧
@router.post("/images/batch")
async def get_batch_images(
    req: BatchImageRequest,
    current_user: str = Depends(get_current_user)
):
    """
    [新增] 批量获取图片接口 (懒加载专用)
    接收文件名列表，返回 {filename: base64_string} 的字典
    """
    results = {}
    
    # 去重
    unique_filenames = set(req.filenames)
    
    for filename in unique_filenames:
        if not filename:
            continue
            
        # 安全检查
        if '..' in filename or '/' in filename or '\\' in filename:
            continue

        image_path = IMAGE_DIR / filename
        if image_path.exists():
            try:
                # 判断 MIME
                ext = image_path.suffix.lower()
                mime_type = "image/jpeg"
                if ext == ".png": mime_type = "image/png"
                elif ext == ".gif": mime_type = "image/gif"
                elif ext == ".webp": mime_type = "image/webp"

                with open(image_path, "rb") as img_file:
                    b64_data = base64.b64encode(img_file.read()).decode('utf-8')
                    results[filename] = f"data:{mime_type};base64,{b64_data}"
            except Exception as e:
                logger.error(f"批量读取图片失败 {filename}: {e}")
                results[filename] = "" # 失败返回空，前端显示默认
        else:
            results[filename] = "" # 文件不存在
            
    return {
        "success": True,
        "data": results
    }

# 使用流式，LRU，连接池（前端），边查边发，异步，队列，生产者消费者。
# 以后的改进点，可以引入CDN，懒加载，热点音乐Zset排序，一段时间清空一次重排，一是可以避免数值无限增长，而是实时反映热点。
# 另外可以考虑引入Elasticsearch等搜索引擎，提升搜索性能


# ==================== 音乐排行榜相关 API ====================

@router.get("/rankings")
async def get_music_rankings(
    current_user: str = Depends(get_current_user),
    limit: int = 100,
    time_range: str = "all",
    genre: str = None
):
    """获取音乐排行榜

    Args:
        current_user: 当前认证用户
        limit: 返回的歌曲数量，默认100
        time_range: 时间范围 (all/daily/weekly/monthly)，默认all
        genre: 音乐分类筛选（可选）

    Returns:
        dict: 包含排行榜数据的响应
    """
    try:
        from redis_utils import get_music_rankings, get_song_play_count, get_rank_change

        # 从 Redis 获取排行榜
        rankings = get_music_rankings(limit, time_range)

        if not rankings:
            return {
                "success": True,
                "rankings": [],
                "total": 0,
                "time_range": time_range
            }

        # 从 Neo4j 获取歌曲详细信息
        all_songs = get_songs_from_neo4j()
        song_dict = {song["id"]: song for song in all_songs}

        if not rankings:
            return {
                "success": True,
                "rankings": [],
                "total": 0,
                "time_range": time_range
            }

        # 合并排行榜数据和歌曲信息
        enriched_rankings = []
        for rank_item in rankings:
            song_id = rank_item["song_id"]
            song = song_dict.get(song_id)

            if song:
                # 如果指定了 genre，进行筛选
                if genre and song.get("genre") != genre:
                    continue

                # 计算所有时间段的排名变化
                rank_changes = {
                    "update": get_rank_change(song_id, rank_item["rank"], "update"),
                    "hourly": get_rank_change(song_id, rank_item["rank"], "hourly"),
                    "daily": get_rank_change(song_id, rank_item["rank"], "daily")
                }

                enriched_rankings.append({
                    "rank": rank_item["rank"],
                    "song_id": song_id,
                    "title": song.get("title", ""),
                    "artist": song.get("artist", ""),
                    "album": song.get("album", ""),
                    "duration": song.get("duration", 0),
                    "cover_image": song.get("cover_image", ""),
                    "play_count": rank_item["play_count"],
                    "rank_changes": rank_changes
                })

        return {
            "success": True,
            "rankings": enriched_rankings,
            "total": len(enriched_rankings),
            "time_range": time_range,
            "genre": genre
        }

    except Exception as e:
        logger.error(f"获取排行榜失败: {e}")
        raise HTTPException(status_code=500, detail="获取排行榜失败")


@router.get("/trending")
async def get_trending_songs(
    current_user: str = Depends(get_current_user),
    page: int = 1,
    page_size: int = 20
):
    """获取实时热门趋势（支持分页）

    Args:
        current_user: 当前认证用户
        page: 页码，从1开始，默认1
        page_size: 每页数量，默认20

    Returns:
        dict: 包含热门趋势数据的响应
    """
    try:
        from redis_utils import get_trending_songs as get_trending

        # 计算需要获取的总数（为了支持分页，获取更多数据）
        # 例如：第2页，每页20条，需要获取前40条
        total_needed = page * page_size
        
        # 从 Redis 获取热门趋势
        trending = get_trending(total_needed)

        if not trending:
            # 如果没有热门趋势数据，返回播放量最高的歌曲
            from redis_utils import get_music_rankings
            trending = get_music_rankings(total_needed, "daily")
            # 转换格式
            trending = [
                {"song_id": item["song_id"], "hotness": float(item["play_count"]), "rank": item["rank"]}
                for item in trending
            ]

        # 从 Neo4j 获取歌曲详细信息
        all_songs = get_songs_from_neo4j()
        song_dict = {song["id"]: song for song in all_songs}

        # 合并热门趋势数据和歌曲信息
        enriched_trending = []
        for trend_item in trending:
            song_id = trend_item["song_id"]
            song = song_dict.get(song_id)

            if song:
                enriched_trending.append({
                    "rank": trend_item["rank"],
                    "song_id": song_id,
                    "title": song.get("title", ""),
                    "artist": song.get("artist", ""),
                    "album": song.get("album", ""),
                    "cover_image": song.get("cover_image", ""),
                    "hotness": trend_item["hotness"]
                })

        # 分页处理
        total = len(enriched_trending)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_trending = enriched_trending[start_index:end_index]
        
        # 计算是否有下一页
        has_next = end_index < total

        return {
            "success": True,
            "songs": paginated_trending,  # 修复：改为 "songs" 以匹配前端期望
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": has_next
        }

    except Exception as e:
        logger.error(f"获取热门趋势失败: {e}")
        raise HTTPException(status_code=500, detail="获取热门趋势失败")


@router.get("/play-history")
async def get_play_history(
    current_user: str = Depends(get_current_user),
    limit: int = 50
):
    """获取用户播放历史

    Args:
        current_user: 当前认证用户
        limit: 返回的歌曲数量，默认50

    Returns:
        dict: 包含播放历史数据的响应
    """
    try:
        from redis_utils import get_user_play_history

        # 从 Redis 获取播放历史
        history = get_user_play_history(current_user, limit)

        if not history:
            return {
                "success": True,
                "history": [],
                "total": 0
            }

        # 从 Neo4j 获取歌曲详细信息
        all_songs = get_songs_from_neo4j()
        song_dict = {song["id"]: song for song in all_songs}

        # 合并播放历史数据和歌曲信息
        enriched_history = []
        for history_item in history:
            song_id = history_item["song_id"]
            song = song_dict.get(song_id)

            if song:
                enriched_history.append({
                    "song_id": song_id,
                    "title": song.get("title", ""),
                    "artist": song.get("artist", ""),
                    "album": song.get("album", ""),
                    "duration": song.get("duration", 0),
                    "cover_image": song.get("cover_image", ""),
                    "played_at": history_item["played_at"]
                })

        return {
            "success": True,
            "history": enriched_history,
            "total": len(enriched_history)
        }

    except Exception as e:
        logger.error(f"获取播放历史失败: {e}")
        raise HTTPException(status_code=500, detail="获取播放历史失败")


@router.post("/play-event")
async def post_play_event(
    event_data: Dict,
    current_user: str = Depends(get_current_user)
):
    """接收前端发送的播放事件并发送到Kafka

    Args:
        event_data: 播放事件数据，包含 song_id 和 timestamp
        current_user: 当前认证用户

    Returns:
        dict: 操作结果
    """
    try:
        # 验证事件数据
        if 'song_id' not in event_data:
            raise HTTPException(status_code=400, detail="缺少 song_id 参数")
        
        song_id = event_data['song_id']
        timestamp = event_data.get('timestamp', int(time.time() * 1000))
        
        # 增加播放计数到 Redis
        from redis_utils import increment_music_play_count
        increment_music_play_count(song_id, current_user)
        
        # 发送到 Kafka
        try:
            from kafka_music_producer import send_play_event
            send_play_event(song_id, current_user, timestamp)
            logger.info(f"✅ 播放事件已发送到 Kafka: song_id={song_id}, user={current_user}")
        except Exception as kafka_err:
            # Kafka 发送失败不影响播放功能
            logger.warning(f"⚠️ 发送 Kafka 事件失败: {kafka_err}")
        
        return {
            "success": True,
            "message": "播放事件已记录"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理播放事件失败: {e}")
        raise HTTPException(status_code=500, detail="处理播放事件失败")
