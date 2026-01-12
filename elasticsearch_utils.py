"""
Elasticsearch 工具类
提供ES连接、索引管理、数据索引和搜索功能
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from config import ES_URL, ES_INDEX_LOGS, ES_INDEX_MUSIC

logger = logging.getLogger(__name__)


class ElasticsearchManager:
    """Elasticsearch 管理类"""
    
    def __init__(self):
        """初始化ES客户端"""
        self.client = None
        self.connect()
    
    def connect(self) -> bool:
        """连接Elasticsearch"""
        try:
            self.client = Elasticsearch(
                [ES_URL],
                request_timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )
            
            # 测试连接
            if self.client.ping():
                logger.info(f"✅ 成功连接到Elasticsearch: {ES_URL}")
                # 初始化索引
                self._init_logs_index()
                self._init_music_index()
                return True
            else:
                logger.error("❌ Elasticsearch连接失败：无法ping通服务器")
                return False
                
        except Exception as e:
            logger.error(f"❌ Elasticsearch连接失败: {e}")
            return False
    
    def _init_logs_index(self) -> bool:
        """初始化日志索引"""
        try:
            if not self.client.indices.exists(index=ES_INDEX_LOGS):
            # 创建日志索引映射
                logs_mapping = {
                    "mappings": {
                        "properties": {
                            "timestamp": {"type": "date"},
                            "level": {"type": "keyword"},
                            "trace_id": {"type": "keyword"},
                            "user_id": {"type": "keyword"},
                            "module": {"type": "keyword"},
                            "message": {"type": "text", "analyzer": "ik_smart"},
                            "request_method": {"type": "keyword"},
                            "request_path": {"type": "keyword"},
                            "request_params": {"type": "object"},
                            "response_status": {"type": "integer"},
                            "response_time": {"type": "float"},
                            "error": {"type": "text"},
                            "ip_address": {"type": "ip"},
                            "user_agent": {"type": "text"},
                            "extra_data": {"type": "object"}
                        }
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 1
                    }
                }
                
                self.client.indices.create(
                    index=ES_INDEX_LOGS,
                    body=logs_mapping
                )
                logger.info(f"✅ 创建日志索引成功: {ES_INDEX_LOGS}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 初始化日志索引失败: {e}")
            return False
    
    def _init_music_index(self) -> bool:
        """初始化音乐索引"""
        try:
            if not self.client.indices.exists(index=ES_INDEX_MUSIC):
                # 创建音乐索引映射
                music_mapping = {
                    "mappings": {
                        "properties": {
                            "id": {"type": "integer"},
                            "title": {
                                "type": "text",
                                "analyzer": "ik_max_word",
                                "fields": {
                                    "keyword": {"type": "keyword"},
                                    "pinyin": {"type": "text"}
                                }
                            },
                            "artist": {
                                "type": "text",
                                "analyzer": "ik_smart",
                                "fields": {
                                    "keyword": {"type": "keyword"}
                                }
                            },
                            "album": {
                                "type": "text",
                                "analyzer": "ik_smart"
                            },
                            "duration": {"type": "integer"},
                            "file_path": {"type": "keyword"},
                            "cover_image": {"type": "keyword"},
                            "created_at": {"type": "date"},
                            "genre": {"type": "keyword"},
                            "play_count": {"type": "integer"}
                        }
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 1
                    }
                }
                
                self.client.indices.create(
                    index=ES_INDEX_MUSIC,
                    body=music_mapping
                )
                logger.info(f"✅ 创建音乐索引成功: {ES_INDEX_MUSIC}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 初始化音乐索引失败: {e}")
            return False
    
    # ==================== 日志相关方法 ====================
    
    def index_log(self, log_data: Dict[str, Any]) -> bool:
        """索引单条日志"""
        try:
            # 添加时间戳
            if "timestamp" not in log_data:
                log_data["timestamp"] = datetime.now()
            
            result = self.client.index(
                index=ES_INDEX_LOGS,
                body=log_data
            )
            logger.debug(f"日志索引成功: {result['_id']}")
            return True
            
        except Exception as e:
            logger.error(f"索引日志失败: {e}")
            return False
    
    def bulk_index_logs(self, logs: List[Dict[str, Any]]) -> int:
        """批量索引日志"""
        try:
            if not logs:
                return 0
            
            # 准备批量数据
            actions = []
            for log in logs:
                if "timestamp" not in log:
                    log["timestamp"] = datetime.now()
                actions.append({
                    "_index": ES_INDEX_LOGS,
                    "_source": log
                })
            
            # 执行批量索引
            success, failed = bulk(
                self.client,
                actions,
                raise_on_error=False
            )
            
            logger.info(f"批量索引日志: 成功 {success}, 失败 {len(failed)}")
            return success
            
        except Exception as e:
            logger.error(f"批量索引日志失败: {e}")
            return 0
    
    def search_logs(
        self,
        query: str,
        level: Optional[str] = None,
        user_id: Optional[str] = None,
        module: Optional[str] = None,
        trace_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        size: int = 100,
        from_: int = 0,
        sort_by: str = "timestamp",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """搜索日志
        
        Args:
            query: 搜索关键词
            level: 日志级别过滤
            user_id: 用户ID过滤
            module: 模块过滤
            trace_id: TraceID过滤
            start_time: 开始时间
            end_time: 结束时间
            size: 返回数量
            from_: 偏移量
            sort_by: 排序字段
            sort_order: 排序方向 asc/desc
        
        Returns:
            dict: 包含搜索结果和统计信息
        """
        try:
            # 构建查询条件
            must_conditions = []
            
            # 关键词搜索
            if query:
                must_conditions.append({
                    "multi_match": {
                        "query": query,
                        "fields": ["message", "module", "error"],
                        "fuzziness": "AUTO"
                    }
                })
            
            # 过滤条件
            filter_conditions = []
            
            if level:
                filter_conditions.append({"term": {"level": level}})
            
            if user_id:
                filter_conditions.append({"term": {"user_id": user_id}})
            
            if module:
                filter_conditions.append({"term": {"module": module}})
            
            if trace_id:
                filter_conditions.append({"term": {"trace_id": trace_id}})
            
            # 时间范围
            if start_time or end_time:
                range_condition = {"range": {"timestamp": {}}}
                if start_time:
                    range_condition["range"]["timestamp"]["gte"] = start_time.isoformat()
                if end_time:
                    range_condition["range"]["timestamp"]["lte"] = end_time.isoformat()
                filter_conditions.append(range_condition)
            
            # 组合查询
            query_body = {"bool": {}}
            if must_conditions:
                query_body["bool"]["must"] = must_conditions
            if filter_conditions:
                query_body["bool"]["filter"] = filter_conditions
            
            # 如果没有条件，匹配所有
            if not must_conditions and not filter_conditions:
                query_body = {"match_all": {}}
            
            # 执行搜索
            result = self.client.search(
                index=ES_INDEX_LOGS,
                body={
                    "query": query_body,
                    "sort": [{sort_by: {"order": sort_order}}],
                    "from": from_,
                    "size": size,
                    "highlight": {
                        "fields": {
                            "message": {},
                            "error": {}
                        }
                    }
                }
            )
            
            # 格式化结果
            hits = result["hits"]["hits"]
            total = result["hits"]["total"]["value"]
            
            logs = []
            for hit in hits:
                log_data = hit["_source"]
                log_data["_id"] = hit["_id"]
                log_data["_score"] = hit["_score"]
                
                # 添加高亮
                if "highlight" in hit:
                    log_data["highlight"] = hit["highlight"]
                
                logs.append(log_data)
            
            return {
                "total": total,
                "from": from_,
                "size": size,
                "logs": logs,
                "has_more": (from_ + size) < total
            }
            
        except Exception as e:
            logger.error(f"搜索日志失败: {e}")
            return {
                "total": 0,
                "from": from_,
                "size": size,
                "logs": [],
                "has_more": False,
                "error": str(e)
            }
    
    # ==================== 音乐相关方法 ====================
    
    def index_music(self, music_data: Dict[str, Any]) -> bool:
        """索引单首音乐"""
        try:
            result = self.client.index(
                index=ES_INDEX_MUSIC,
                id=music_data.get("id"),
                body=music_data,
                refresh=True
            )
            logger.debug(f"音乐索引成功: {music_data.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"索引音乐失败: {e}")
            return False
    
    def bulk_index_music(self, songs: List[Dict[str, Any]]) -> int:
        """批量索引音乐"""
        try:
            if not songs:
                return 0
            
            # 准备批量数据
            actions = []
            for song in songs:
                actions.append({
                    "_index": ES_INDEX_MUSIC,
                    "_id": song.get("id"),
                    "_source": song
                })
            
            # 执行批量索引
            success, failed = bulk(
                self.client,
                actions,
                refresh=True,
                raise_on_error=False
            )
            
            logger.info(f"批量索引音乐: 成功 {success}, 失败 {len(failed)}")
            return success
            
        except Exception as e:
            logger.error(f"批量索引音乐失败: {e}")
            return 0
    
    def search_music(
        self,
        query: str,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        genre: Optional[str] = None,
        size: int = 20,
        from_: int = 0,
        min_score: float = 0.5
    ) -> Dict[str, Any]:
        """搜索音乐
        
        Args:
            query: 搜索关键词
            artist: 艺术家过滤
            album: 专辑过滤
            genre: 音乐类型过滤
            size: 返回数量
            from_: 偏移量
            min_score: 最小评分
        
        Returns:
            dict: 包含搜索结果和统计信息
        """
        try:
            # 构建查询条件
            must_conditions = []
            filter_conditions = []
            
            # 关键词搜索
            if query:
                must_conditions.append({
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "title^3",  # 标题权重最高
                            "artist^2",  # 艺术家权重次之
                            "album"  # 专辑权重
                        ],
                        "fuzziness": "AUTO",
                        "operator": "and"
                    }
                })
            
            # 过滤条件
            if artist:
                filter_conditions.append({"term": {"artist.keyword": artist}})
            
            if album:
                filter_conditions.append({"term": {"album": album}})
            
            if genre:
                filter_conditions.append({"term": {"genre": genre}})
            
            # 组合查询
            query_body = {"bool": {}}
            if must_conditions:
                query_body["bool"]["must"] = must_conditions
            if filter_conditions:
                query_body["bool"]["filter"] = filter_conditions
            
            # 如果没有查询条件，返回所有
            if not must_conditions:
                query_body = {"match_all": {}}
            
            # 执行搜索
            result = self.client.search(
                index=ES_INDEX_MUSIC,
                body={
                    "query": query_body,
                    "from": from_,
                    "size": size,
                    "min_score": min_score if query else None,
                    "sort": [
                        {"_score": {"order": "desc"}},  # 相关性优先
                        {"play_count": {"order": "desc"}}  # 播放量次之
                    ]
                }
            )
            
            # 格式化结果
            hits = result["hits"]["hits"]
            total = result["hits"]["total"]["value"]
            
            songs = []
            for hit in hits:
                song_data = hit["_source"]
                song_data["_score"] = hit["_score"]
                songs.append(song_data)
            
            return {
                "total": total,
                "from": from_,
                "size": size,
                "songs": songs,
                "has_more": (from_ + size) < total
            }
            
        except Exception as e:
            logger.error(f"搜索音乐失败: {e}")
            return {
                "total": 0,
                "from": from_,
                "size": size,
                "songs": [],
                "has_more": False,
                "error": str(e)
            }
    
    def delete_music(self, song_id: int) -> bool:
        """删除音乐索引"""
        try:
            self.client.delete(
                index=ES_INDEX_MUSIC,
                id=song_id,
                refresh=True
            )
            logger.info(f"删除音乐索引: {song_id}")
            return True
        except Exception as e:
            logger.error(f"删除音乐索引失败: {e}")
            return False
    
    def get_music_stats(self) -> Dict[str, Any]:
        """获取音乐统计信息"""
        try:
            # 获取总数
            total_result = self.client.count(index=ES_INDEX_MUSIC)
            total = total_result["count"]
            
            # 获取按艺术家分组统计
            aggs_result = self.client.search(
                index=ES_INDEX_MUSIC,
                body={
                    "size": 0,
                    "aggs": {
                        "by_artist": {
                            "terms": {
                                "field": "artist.keyword",
                                "size": 10
                            }
                        },
                        "by_genre": {
                            "terms": {
                                "field": "genre",
                                "size": 10
                            }
                        }
                    }
                }
            )
            
            artists = [
                {"name": bucket["key"], "count": bucket["doc_count"]}
                for bucket in aggs_result["aggregations"]["by_artist"]["buckets"]
            ]
            
            genres = [
                {"name": bucket["key"], "count": bucket["doc_count"]}
                for bucket in aggs_result["aggregations"]["by_genre"]["buckets"]
            ]
            
            return {
                "total": total,
                "top_artists": artists,
                "top_genres": genres
            }
            
        except Exception as e:
            logger.error(f"获取音乐统计失败: {e}")
            return {
                "total": 0,
                "top_artists": [],
                "top_genres": []
            }


# 全局ES管理器实例
es_manager = ElasticsearchManager()
