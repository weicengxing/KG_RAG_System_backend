"""
布隆过滤器工具模块
提供基于 pybloom 的布隆过滤器实现
支持启动时Warmup预加载
"""

import pickle
import logging
import time
import threading
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from pybloom_live import ScalableBloomFilter, BloomFilter

from redis_utils import redis_client, redis_binary_client

logger = logging.getLogger(__name__)

# ==================== Warmup 状态管理 ====================

BLOOM_WARMUP_COMPLETED = False  # Warmup完成标志
BLOOM_WARMUP_LOCK = threading.Lock()  # 线程安全锁


# ==================== Redis 存储的布隆过滤器 ====================

class RedisBloomFilter:
    """基于 Redis 存储的布隆过滤器（持久化）"""
    
    def __init__(
        self,
        key_name: str,
        initial_capacity: int = 100000,
        error_rate: float = 0.001,
        use_scalable: bool = True,
        batch_size: int = 100
    ):
        """
        初始化布隆过滤器
        
        Args:
            key_name: Redis 键名
            initial_capacity: 初始容量
            error_rate: 误判率 (0-1之间，越小越精准)
            use_scalable: 是否使用可扩展的布隆过滤器
            batch_size: 批量保存的阈值（达到此次数才保存到 Redis）
        """
        self.redis = redis_binary_client
        self.key_name = key_name
        self.initial_capacity = initial_capacity
        self.error_rate = error_rate
        self.use_scalable = use_scalable
        self.batch_size = batch_size
        self.bloom: Optional[ScalableBloomFilter] = None
        self._pending_count = 0  # 待保存的计数器
        
        self._load_bloom()
    
    def _load_bloom(self):
        """从 Redis 加载布隆过滤器"""
        try:
            data = self.redis.get(self.key_name)
            if data:
                # 确保数据是bytes类型（pickle需要bytes，不能是str）
                if isinstance(data, str):
                    logger.warning(f"⚠️ Redis返回了字符串类型，尝试编码为bytes: {self.key_name}")
                    try:
                        data = data.encode('utf-8')
                    except Exception as encode_error:
                        logger.error(f"❌ 字符串编码失败: {encode_error}")
                        # 编码失败，清除损坏的数据并重新初始化
                        self.redis.delete(self.key_name)
                        data = None
                
                if data:
                    self.bloom = pickle.loads(data)
                    logger.info(f"✅ 从 Redis 加载布隆过滤器: {self.key_name}")
                else:
                    logger.warning(f"⚠️ Redis中的布隆过滤器数据损坏，重新初始化: {self.key_name}")
                    if self.use_scalable:
                        self.bloom = ScalableBloomFilter(
                            initial_capacity=self.initial_capacity,
                            error_rate=self.error_rate
                        )
                    else:
                        self.bloom = BloomFilter(
                            capacity=self.initial_capacity,
                            error_rate=self.error_rate
                        )
            else:
                if self.use_scalable:
                    self.bloom = ScalableBloomFilter(
                        initial_capacity=self.initial_capacity,
                        error_rate=self.error_rate
                    )
                else:
                    self.bloom = BloomFilter(
                        capacity=self.initial_capacity,
                        error_rate=self.error_rate
                    )
                logger.info(f"✅ 创建新布隆过滤器: {self.key_name}")
        except pickle.UnpicklingError as e:
            logger.error(f"❌ Pickle反序列化失败: {e}")
            logger.error(f"🗑️ 清除损坏的布隆过滤器数据: {self.key_name}")
            self.redis.delete(self.key_name)
            # 重新初始化
            if self.use_scalable:
                self.bloom = ScalableBloomFilter(
                    initial_capacity=self.initial_capacity,
                    error_rate=self.error_rate
                )
            else:
                self.bloom = BloomFilter(
                    capacity=self.initial_capacity,
                    error_rate=self.error_rate
                )
        except Exception as e:
            logger.error(f"❌ 加载布隆过滤器失败: {e}")
            logger.error(f"🗑️ 清除损坏的布隆过滤器数据: {self.key_name}")
            self.redis.delete(self.key_name)
            self.bloom = ScalableBloomFilter(
                initial_capacity=self.initial_capacity,
                error_rate=self.error_rate
            )
    
    def _save_bloom(self):
        """保存布隆过滤器到 Redis"""
        try:
            if self.bloom:
                data = pickle.dumps(self.bloom)
                # 保存7天，过期后自动重建
                self.redis.setex(self.key_name, 7 * 24 * 3600, data)
        except Exception as e:
            logger.error(f"❌ 保存布隆过滤器失败: {e}")
    
    def add(self, item: str, force_save: bool = False) -> bool:
        """
        添加元素
        
        Args:
            item: 要添加的元素
            force_save: 是否强制保存到 Redis（默认使用批量保存）
        
        Returns:
            bool: True 表示添加成功，False 表示已存在
        """
        if not self.bloom:
            self._load_bloom()
        
        item = str(item)
        result = item not in self.bloom
        self.bloom.add(item)
        
        # 批量保存策略
        self._pending_count += 1
        if force_save or self._pending_count >= self.batch_size:
            self._save_bloom()
            self._pending_count = 0
        
        return result
    
    def exists(self, item: str) -> bool:
        """
        检查元素是否存在
        
        Args:
            item: 要检查的元素
        
        Returns:
            bool: 可能存在（注意：布隆过滤器有误判）
        """
        if not self.bloom:
            self._load_bloom()
        
        item = str(item)
        return item in self.bloom
    
    def multi_add(self, items: List[str]) -> List[bool]:
        """批量添加元素（优化版，只保存一次）"""
        if not self.bloom:
            self._load_bloom()
        
        results = []
        for item in items:
            item = str(item)
            result = item not in self.bloom
            self.bloom.add(item)
            results.append(result)
        
        # 批量保存一次
        self._pending_count += len(items)
        if self._pending_count >= self.batch_size:
            self._save_bloom()
            self._pending_count = 0
        
        return results
    
    def multi_exists(self, items: List[str]) -> List[bool]:
        """批量检查元素"""
        if not self.bloom:
            self._load_bloom()
        
        return [str(item) in self.bloom for item in items]
    
    def clear(self):
        """清空布隆过滤器"""
        self.redis.delete(self.key_name)
        self._pending_count = 0  # 重置计数器
        if self.use_scalable:
            self.bloom = ScalableBloomFilter(
                initial_capacity=self.initial_capacity,
                error_rate=self.error_rate
            )
        else:
            self.bloom = BloomFilter(
                capacity=self.initial_capacity,
                error_rate=self.error_rate
            )
        logger.info(f"🗑️ 布隆过滤器已清空: {self.key_name}")


# ==================== 全局布隆过滤器实例 ====================

# 1. 文档上传去重布隆过滤器
# 使用较小的 batch_size，因为文档上传相对低频，每次都强制保存更安全
document_bloom = RedisBloomFilter(
    key_name="bloom:uploaded_documents",
    initial_capacity=1000000,  # 预估100万文档
    error_rate=0.001,          # 0.1% 误判率
    batch_size=10              # 每10次操作保存一次，或使用 force_save=True 强制保存
)

# 2. 缓存穿透防护布隆过滤器
# 使用较大的 batch_size，因为高频操作，减少 Redis 写入压力
cache_keys_bloom = RedisBloomFilter(
    key_name="bloom:cache_keys",
    initial_capacity=10000000,  # 预估1000万缓存键
    error_rate=0.0001,          # 0.01% 误判率
    batch_size=1000             # 每1000次操作保存一次
)


# ==================== 便捷函数 ====================

def is_document_uploaded(doc_id: str) -> bool:
    """检查文档是否已上传"""
    return document_bloom.exists(doc_id)

def mark_document_uploaded(doc_id: str, force_save: bool = False):
    """
    标记文档已上传
    Args:
        doc_id: 文档ID（MD5 hash）
        force_save: 是否强制立即保存到 Redis（默认使用批量保存）
    """
    document_bloom.add(doc_id, force_save=force_save)

def is_cache_key_exists(key: str) -> bool:
    """检查缓存键是否存在"""
    return cache_keys_bloom.exists(key)

def mark_cache_key_exists(key: str, force_save: bool = False):
    """
    标记缓存键已存在
    Args:
        key: 缓存键名
        force_save: 是否强制立即保存到 Redis（默认使用批量保存）
    """
    cache_keys_bloom.add(key, force_save=force_save)


# ==================== Bloom Filter Warmup 功能 ====================

def warmup_document_bloom_from_mongodb():
    """
    从MongoDB预热document_bloom (文档去重布隆过滤器)
    读取所有文档的file_hash并添加到布隆过滤器
    
    Returns:
        dict: 包含统计信息的字典
    """
    global BLOOM_WARMUP_COMPLETED
    
    logger.info("🚀 开始预热 document_bloom (从MongoDB)...")
    start_time = time.time()
    
    try:
        # 使用同步的pymongo客户端（因为是在后台线程中执行）
        from pymongo import MongoClient
        from config import MONGO_URI, MONGO_DB_NAME
        
        # 连接MongoDB
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB_NAME]
        
        # 查询所有文档的file_hash
        total_count = 0
        added_count = 0
        
        # 使用游标批量读取，避免内存溢出
        cursor = db.documents.find({}, {"file_hash": 1, "_id": 0})
        
        for doc in cursor:
            total_count += 1
            file_hash = doc.get("file_hash")
            if file_hash:
                document_bloom.add(file_hash, force_save=False)
                added_count += 1
            
            # 每1000条记录一次进度日志
            if total_count % 1000 == 0:
                logger.info(f"📦 已处理 {total_count} 条文档记录...")
        
        # Warmup完成后保存到Redis
        document_bloom._save_bloom()
        
        elapsed_time = time.time() - start_time
        logger.info(f"✅ document_bloom预热完成！")
        logger.info(f"   - 总文档数: {total_count}")
        logger.info(f"   - 成功添加: {added_count}")
        logger.info(f"   - 耗时: {elapsed_time:.2f}秒")
        
        client.close()
        
        return {
            "success": True,
            "total_count": total_count,
            "added_count": added_count,
            "elapsed_time": elapsed_time
        }
        
    except Exception as e:
        logger.error(f"❌ document_bloom预热失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def warmup_cache_keys_bloom_from_neo4j():
    """
    从Neo4j预热cache_keys_bloom (缓存键布隆过滤器)
    扫描所有用户的qr_login_status并生成缓存键
    
    Returns:
        dict: 包含统计信息的字典
    """
    global BLOOM_WARMUP_COMPLETED
    
    logger.info("🚀 开始预热 cache_keys_bloom (从Neo4j)...")
    start_time = time.time()
    
    try:
        from database import driver
        
        if not driver:
            logger.warning("⚠️ Neo4j连接未建立，跳过cache_keys_bloom预热")
            return {
                "success": True,
                "skipped": True,
                "reason": "Neo4j connection not available"
            }
        
        total_count = 0
        added_count = 0
        
        with driver.session() as session:
            query = """
            MATCH (u:User)
            WHERE u.qr_login_enabled IS NOT NULL
            RETURN u.username as username
            """
            results = session.run(query)
            
            for record in results:
                total_count += 1
                username = record.get("username")
                if username:
                    cache_key = f"qr_login_status:{username}"
                    cache_keys_bloom.add(cache_key, force_save=False)
                    added_count += 1
                
                # 每100条记录一次进度日志
                if total_count % 100 == 0:
                    logger.info(f"📦 已处理 {total_count} 个用户...")
        
        # Warmup完成后保存到Redis
        cache_keys_bloom._save_bloom()
        
        elapsed_time = time.time() - start_time
        logger.info(f"✅ cache_keys_bloom预热完成！")
        logger.info(f"   - 总用户数: {total_count}")
        logger.info(f"   - 成功添加: {added_count}")
        logger.info(f"   - 耗时: {elapsed_time:.2f}秒")
        
        return {
            "success": True,
            "total_count": total_count,
            "added_count": added_count,
            "elapsed_time": elapsed_time
        }
        
    except Exception as e:
        logger.error(f"❌ cache_keys_bloom预热失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def warmup_all_bloom_filters_async():
    """
    异步预热所有布隆过滤器（在后台线程池中并发执行）
    这个函数会在应用启动时调用，使用线程池避免阻塞启动
    使用 concurrent.futures 实现并发预热，提高热身效率
    """
    global BLOOM_WARMUP_COMPLETED, BLOOM_WARMUP_LOCK
    
    def _warmup_task():
        """Warmup任务的内部函数（并发执行）"""
        logger.info("=" * 60)
        logger.info("🔥 Bloom Filter Warmup 开始（并发模式）")
        logger.info("=" * 60)
        
        # 使用 ThreadPoolExecutor 并发执行两个预热任务
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="bloom-warmup") as executor:
            # 提交两个预热任务
            future_doc = executor.submit(warmup_document_bloom_from_mongodb)
            future_cache = executor.submit(warmup_cache_keys_bloom_from_neo4j)
            
            # 按完成顺序获取结果
            results = {}
            for future in as_completed([future_doc, future_cache]):
                try:
                    result = future.result()
                    # 根据任务类型标记结果
                    if 'file_hash' in str(result.get('error', '')) or 'document' in str(result):
                        results['document'] = result
                    else:
                        results['cache'] = result
                except Exception as e:
                    logger.error(f"❌ Warmup任务异常: {e}")
                    # 标记失败的结果
                    if future == future_doc:
                        results['document'] = {'success': False, 'error': str(e)}
                    else:
                        results['cache'] = {'success': False, 'error': str(e)}
            
            # 确保两个结果都存在（按提交顺序）
            if 'document' not in results:
                results['document'] = future_doc.result()
            if 'cache' not in results:
                results['cache'] = future_cache.result()
        
        elapsed_time = time.time() - start_time
        
        # 标记Warmup完成
        with BLOOM_WARMUP_LOCK:
            BLOOM_WARMUP_COMPLETED = True
        
        # 输出结果
        doc_result = results.get('document', {'success': False})
        cache_result = results.get('cache', {'success': False})
        
        logger.info("=" * 60)
        logger.info("🎉 Bloom Filter Warmup 全部完成！")
        logger.info("=" * 60)
        logger.info(f"📊 文档布隆过滤器: {'✅' if doc_result.get('success') else '❌'}")
        if doc_result.get('success'):
            logger.info(f"   - 处理文档数: {doc_result.get('total_count', 0)}")
        logger.info(f"📊 缓存布隆过滤器: {'✅' if cache_result.get('success') else '❌'}")
        if cache_result.get('success'):
            logger.info(f"   - 处理用户数: {cache_result.get('total_count', 0)}")
        logger.info(f"⚡ 总耗时: {elapsed_time:.2f}秒（并发模式）")
        logger.info("🔄 Warmup期间的业务请求已自动切换到布隆过滤器检查")
        logger.info("=" * 60)
    
    # 在后台线程中执行Warmup
    warmup_thread = threading.Thread(target=_warmup_task, daemon=True)
    warmup_thread.start()
    
    logger.info("📢 Bloom Filter Warmup 已在后台启动（并发模式）...")
    logger.info("⚠️  Warmup期间的两个任务将并发执行，互不阻塞")


def is_warmup_completed() -> bool:
    """
    检查Warmup是否完成
    
    Returns:
        bool: True表示Warmup已完成，False表示正在进行
    """
    return BLOOM_WARMUP_COMPLETED


def wait_for_warmup_completion(timeout: Optional[float] = None) -> bool:
    """
    等待Warmup完成（阻塞调用，一般用于测试）
    
    Args:
        timeout: 超时时间（秒），None表示不超时
    
    Returns:
        bool: True表示Warmup完成，False表示超时
    """
    global BLOOM_WARMUP_COMPLETED
    
    if BLOOM_WARMUP_COMPLETED:
        return True
    
    # 简单轮询检查
    import time
    start_time = time.time()
    
    while not BLOOM_WARMUP_COMPLETED:
        if timeout and (time.time() - start_time) > timeout:
            return False
        time.sleep(0.1)
    
    return True


# ==================== 支持Warmup降级的便捷函数 ====================

def is_document_uploaded_with_warmup(doc_id: str, fallback_to_db: bool = False) -> tuple:
    """
    检查文档是否已上传（支持Warmup降级）
    
    由于布隆过滤器存在误判（false positive），当布隆过滤器表示存在时，
    会进行双重验证：从数据库二次确认，避免误判导致用户无法上传新文档
    
    Args:
        doc_id: 文档ID（MD5 hash）
        fallback_to_db: 如果Warmup未完成，是否从数据库查询（降级策略）
    
    Returns:
        tuple: (exists: bool, used_db: bool)
            - exists: 是否存在
            - used_db: 是否使用了数据库查询（降级或双重验证）
    """
    # 如果Warmup已完成，使用布隆过滤器 + 双重验证
    if BLOOM_WARMUP_COMPLETED:
        exists_in_bloom = document_bloom.exists(doc_id)
        
        # 布隆过滤器说不存在，肯定不存在（无假阴性）
        if not exists_in_bloom:
            return False, False
        
        # 布隆过滤器说可能存在，需要双重验证（避免假阳性误判）
        # 从数据库确认是否真的存在
        try:
            from pymongo import MongoClient
            from config import MONGO_URI, MONGO_DB_NAME
            
            client = MongoClient(MONGO_URI)
            db = client[MONGO_DB_NAME]
            
            # 查询文档是否存在
            doc = db.documents.find_one({"file_hash": doc_id})
            exists = doc is not None
            
            client.close()
            return exists, True  # 使用了数据库双重验证
        except Exception as e:
            logger.error(f"❌ 双重验证文档失败: {e}")
            # 双重验证失败，保守处理：返回False（允许上传，后续会再次验证）
            return False, True
    
    # Warmup未完成，处理降级策略
    if fallback_to_db:
        # 从MongoDB查询（降级到数据库）
        try:
            from pymongo import MongoClient
            from config import MONGO_URI, MONGO_DB_NAME
            
            client = MongoClient(MONGO_URI)
            db = client[MONGO_DB_NAME]
            
            # 查询文档是否存在
            doc = db.documents.find_one({"file_hash": doc_id})
            exists = doc is not None
            
            client.close()
            return exists, True
        except Exception as e:
            logger.error(f"❌ 降级查询文档失败: {e}")
            # 降级失败，返回False（假设不存在）
            return False, True
    
    # 不使用降级，直接返回False（假设不存在）
    return False, False


def is_cache_key_exists_with_warmup(key: str, fallback_to_db: bool = False) -> tuple:
    """
    检查缓存键是否存在（支持Warmup降级）
    
    注意：这里的"缓存键"指的是qr_login_status等需要在Neo4j数据库中查询的实际数据，
    而不是Redis缓存。降级时会从Neo4j数据库查询真实数据
    
    Args:
        key: 缓存键名（格式如 "qr_login_status:username"）
        fallback_to_db: 如果Warmup未完成，是否从数据库查询（降级策略）
    
    Returns:
        tuple: (exists: bool, used_db: bool)
            - exists: 是否存在（对于qr_login_status:username，表示该用户启用了二维码登录）
            - used_db: 是否使用了数据库查询（降级）
    """
    # 如果Warmup已完成，使用布隆过滤器
    if BLOOM_WARMUP_COMPLETED:
        return cache_keys_bloom.exists(key), False
    
    # Warmup未完成，处理降级策略
    if fallback_to_db:
        # 从Neo4j数据库查询真实数据（而不是Redis缓存）
        try:
            from database import driver
            
            if not driver:
                logger.warning("⚠️ Neo4j连接未建立，降级失败")
                return False, True
            
            # 解析缓存键，提取username
            # 缓存键格式: "qr_login_status:username"
            if key.startswith("qr_login_status:"):
                username = key.split(":")[-1]
                
                with driver.session() as session:
                    query = """
                    MATCH (u:User {username: $username})
                    WHERE u.qr_login_enabled IS NOT NULL
                    RETURN u.qr_login_enabled as qr_login_enabled
                    """
                    result = session.run(query, username=username).single()
                    
                    if result:
                        qr_login_enabled = result.get("qr_login_enabled", False)
                        if qr_login_enabled:
                            # 标记到布隆过滤器（后续查询可以直接用布隆过滤器）
                            mark_cache_key_exists(key)
                            return True, True
            
            # 其他类型的缓存键暂不支持降级，返回False
            return False, True
            
        except Exception as e:
            logger.error(f"❌ 降级查询缓存键失败: {e}")
            # 降级失败，返回False（假设不存在）
            return False, True
    
    # 不使用降级，直接返回False（假设不存在）
    return False, False
