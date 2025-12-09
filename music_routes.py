"""
音乐播放器路由
提供音乐列表、播放、图片等API接口
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from database import driver
from auth_deps import get_current_user
from auth_deps import get_current_user, get_current_user_from_query

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/music", tags=["音乐"])

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
    

# 使用流式，LRU，连接池（前端），边查边发，异步，队列，生产者消费者。
# 以后的改进点，可以引入CDN，懒加载，热点音乐Zset排序，一段时间清空一次重排，一是可以避免数值无限增长，而是实时反映热点。
# 另外可以考虑引入Elasticsearch等搜索引擎，提升搜索性能
