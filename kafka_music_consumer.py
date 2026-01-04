"""
Kafka 音乐播放事件消费者
用于消费播放事件并计算热门趋势
"""

import json
import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List
from confluent_kafka import Consumer, KafkaException, KafkaError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 配置参数 ====================

KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
MUSIC_PLAY_EVENTS_TOPIC = 'music-play-events'
CONSUMER_GROUP_ID = 'music-trending-consumer'

# 热度计算窗口配置
TRENDING_WINDOW_SECONDS = 3600  # 热度计算窗口：1小时
DECAY_AGE_SECONDS = 300  # 时间衰减影响范围：5分钟

# 全局消费者实例
_consumer = None

# ==================== 本地缓存 ====================

class HotnessCalculator:
    """热门趋势计算器（本地内存缓存）"""
    
    def __init__(self):
        """初始化计算器"""
        # 存储窗口内的播放事件 {song_id: [timestamps]}
        self.play_events: Dict[int, List[int]] = defaultdict(list)
        # 最后一次更新时间
        self.last_update_time = time.time()
        # 窗口长度（秒）
        self.window_seconds = TRENDING_WINDOW_SECONDS
        # 时间衰减影响范围（秒）
        self.decay_age_seconds = DECAY_AGE_SECONDS
    
    def add_play_event(self, song_id: int, timestamp: int):
        """添加播放事件
        
        Args:
            song_id: 歌曲ID
            timestamp: 播放时间戳（毫秒）
        """
        # 转换为秒
        timestamp_sec = timestamp / 1000.0
        self.play_events[song_id].append(timestamp_sec)
        logger.debug(f"添加播放事件: song_id={song_id}, timestamp={timestamp_sec}")
    
    def calculate_hotness(self, song_id: int) -> float:
        """计算单首歌曲的热度分数
        
        热度算法：热度 = 播放次数 × 时间衰减因子
        时间衰减因子 = (当前时间 - 平均播放时间) / 窗口长度
        
        Args:
            song_id: 歌曲ID
            
        Returns:
            float: 热度分数
        """
        if song_id not in self.play_events or not self.play_events[song_id]:
            return 0.0
        
        # 获取当前时间
        current_time = time.time()
        current_time_sec = current_time
        
        # 清理窗口外的旧数据
        self._clean_old_events(current_time_sec)
        
        # 获取窗口内的事件
        events = self.play_events[song_id]
        if not events:
            return 0.0
        
        # 计算播放次数
        play_count = len(events)
        
        # 计算平均播放时间
        avg_play_time = sum(events) / play_count
        
        # 计算时间衰减因子（越接近当前时间，衰减因子越大）
        # 衰减因子范围：[0, 1]，最近播放的歌曲接近1，很久前的接近0
        time_diff = current_time_sec - avg_play_time
        decay_factor = max(0, 1 - (time_diff / self.decay_age_seconds))
        
        # 热度 = 播放次数 × 时间衰减因子
        hotness = play_count * decay_factor
        
        # 添加时间衰减（窗口内平均时间越接近当前，热度越高）
        window_age = current_time_sec - (min(events) if events else current_time_sec)
        time_decay = max(0.1, 1 - (window_age / self.window_seconds))
        
        hotness = hotness * time_decay
        
        logger.debug(f"计算热度: song_id={song_id}, count={play_count}, decay={decay_factor:.3f}, hotness={hotness:.2f}")
        
        return hotness
    
    def get_all_hotness(self) -> Dict[int, float]:
        """计算所有歌曲的热度分数
        
        Returns:
            Dict[int, float]: {song_id: hotness}
        """
        current_time = time.time()
        self._clean_old_events(current_time)
        
        hotness_map = {}
        for song_id in self.play_events:
            hotness_map[song_id] = self.calculate_hotness(song_id)
        
        return hotness_map
    
    def _clean_old_events(self, current_time: float):
        """清理窗口外的旧事件
        
        Args:
            current_time: 当前时间（秒）
        """
        cutoff_time = current_time - self.window_seconds
        
        for song_id in list(self.play_events.keys()):
            # 保留窗口内的事件
            self.play_events[song_id] = [
                ts for ts in self.play_events[song_id]
                if ts >= cutoff_time
            ]
            
            # 如果没有事件了，删除该歌曲
            if not self.play_events[song_id]:
                del self.play_events[song_id]
    
    def clear_old_data(self):
        """清理所有旧数据（定期调用以释放内存）"""
        current_time = time.time()
        self._clean_old_events(current_time)
        logger.info(f"清理后缓存的歌曲数: {len(self.play_events)}")
    
    def get_stats(self) -> Dict:
        """获取统计信息
        
        Returns:
            Dict: 统计信息
        """
        total_events = sum(len(events) for events in self.play_events.values())
        return {
            "total_songs": len(self.play_events),
            "total_events": total_events,
            "last_update": self.last_update_time
        }


# 全局计算器实例
hotness_calculator = HotnessCalculator()


# ==================== Kafka 消费者 ====================

def get_kafka_consumer() -> Consumer | None:
    """获取 Kafka 消费者实例（单例模式）
    
    Returns:
        Optional[Consumer]: Kafka 消费者实例，连接失败返回 None
    """
    global _consumer

    if _consumer is not None:
        return _consumer

    try:
        # 创建消费者配置
        config = {
            'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
            'group.id': CONSUMER_GROUP_ID,
            'auto.offset.reset': 'earliest',  # 修复：从最早未消费的消息开始，避免丢失数据
            'enable.auto.commit': True,  # 自动提交偏移量
            'auto.commit.interval.ms': 5000,  # 5秒提交一次
            # 性能配置
            'fetch.min.bytes': 1024,  # 最小拉取1KB
            'fetch.wait.max.ms': 100,  # 最多等待100ms
            # 可靠性配置
            'enable.auto.commit': True
        }

        _consumer = Consumer(config)
        
        # 订阅主题
        _consumer.subscribe([MUSIC_PLAY_EVENTS_TOPIC])
        
        logger.info(f"✅ Kafka 消费者初始化成功: {KAFKA_BOOTSTRAP_SERVERS}")
        logger.info(f"✅ 订阅主题: {MUSIC_PLAY_EVENTS_TOPIC}")
        
        return _consumer

    except Exception as e:
        logger.error(f"❌ Kafka 消费者初始化失败: {e}")
        _consumer = None
        return None


def consume_play_events(max_messages: int = 100, timeout_seconds: float = 1.0) -> int:
    """消费播放事件并更新热度计算器
    
    Args:
        max_messages: 最大消费消息数（批量）
        timeout_seconds: 超时时间（秒）
        
    Returns:
        int: 实际消费的消息数
    """
    consumer = get_kafka_consumer()
    
    if consumer is None:
        logger.warning("⚠️ Kafka 消费者未连接，跳过消费")
        return 0

    consumed_count = 0
    start_time = time.time()
    
    try:
        while consumed_count < max_messages and (time.time() - start_time) < timeout_seconds:
            # 拉取消息
            msg = consumer.poll(timeout=0.1)
            
            if msg is None:
                break
            
            if msg.error():
                # 处理错误
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    # 到达分区末尾，继续消费
                    continue
                else:
                    logger.error(f"❌ Kafka 消费错误: {msg.error()}")
                    break
            
            # 解析消息
            try:
                event = json.loads(msg.value().decode('utf-8'))
                
                # 验证事件格式
                if 'song_id' not in event or 'timestamp' not in event:
                    logger.warning(f"⚠️ 无效的事件格式: {event}")
                    continue
                
                # 添加到计算器
                hotness_calculator.add_play_event(
                    event['song_id'],
                    event['timestamp']
                )
                
                consumed_count += 1
                
                # 每10条记录一条日志
                if consumed_count % 10 == 0:
                    logger.info(f"📥 已消费 {consumed_count} 条消息")
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON 解析失败: {e}")
                continue
            except Exception as e:
                logger.error(f"❌ 处理消息失败: {e}")
                continue
        
        if consumed_count > 0:
            logger.info(f"✅ 成功消费 {consumed_count} 条播放事件")
            # 自动提交偏移量（由 enable.auto.commit=True 自动完成）
        
        return consumed_count
        
    except Exception as e:
        logger.error(f"❌ 消费播放事件失败: {e}")
        return 0


def update_trending_to_redis() -> bool:
    """将热门趋势更新到 Redis（优化版：调用实时增量更新）

    现在直接在消费播放事件时进行实时更新
    这个方法保留是为了兼容性，实际不再需要批量更新

    Returns:
        bool: 是否成功
    """
    try:
        # 优化后：不再需要批量更新，播放时已经实时更新
        # 这个方法现在只清理旧缓存
        hotness_calculator.clear_old_data()
        
        logger.info("ℹ️ 热门趋势已在播放时实时更新，不需要批量更新")
        return True
        
    except Exception as e:
        logger.error(f"❌ 更新热门趋势到 Redis 失败: {e}")
        return False


def get_calculator_stats() -> Dict:
    """获取计算器统计信息
    
    Returns:
        Dict: 统计信息
    """
    return hotness_calculator.get_stats()


def clean_old_cache():
    """清理旧缓存（可定期调用）"""
    hotness_calculator.clear_old_data()


def close_consumer():
    """关闭 Kafka 消费者（应用关闭时调用）"""
    global _consumer

    if _consumer:
        try:
            _consumer.close()
            logger.info("🔒 Kafka 消费者已关闭")
            _consumer = None
        except Exception as e:
            logger.error(f"❌ 关闭 Kafka 消费者失败: {e}")


# 优雅关闭处理
import atexit
atexit.register(close_consumer)


# ==================== 测试函数 ====================

def test_consumer():
    """测试消费者功能
    
    Returns:
        bool: 测试是否成功
    """
    try:
        consumer = get_kafka_consumer()
        if consumer is None:
            logger.error("❌ Kafka 消费者初始化失败")
            return False
        
        logger.info("🔄 开始测试消费消息...")
        
        # 消费1条消息进行测试
        consumed = consume_play_events(max_messages=1, timeout_seconds=2.0)
        
        if consumed > 0:
            logger.info("✅ Kafka 消费者测试成功")
            stats = get_calculator_stats()
            logger.info(f"📊 统计信息: {stats}")
            return True
        else:
            logger.warning("⚠️ Kafka 测试未收到消息（可能没有播放事件）")
            return True
            
    except Exception as e:
        logger.error(f"❌ Kafka 消费者测试失败: {e}")
        return False


if __name__ == "__main__":
    # 测试消费者
    logger.info("开始测试 Kafka 消费者...")
    
    if test_consumer():
        logger.info("✅ Kafka 消费者连接正常")
        
        # 持续消费示例（运行1分钟）
        logger.info("🔄 开始持续消费（1分钟）...")
        start_time = time.time()
        
        while time.time() - start_time < 60:
            consume_play_events(max_messages=50, timeout_seconds=5.0)
            
            # 每10秒更新一次热门趋势
            if int(time.time() - start_time) % 10 == 0:
                update_trending_to_redis()
                clean_old_cache()
            
            time.sleep(1)
        
        logger.info("✅ 测试完成")
    else:
        logger.error("❌ Kafka 消费器连接失败，请检查 Kafka 服务是否启动")
